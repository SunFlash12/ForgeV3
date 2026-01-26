"""
Forge Cascade V2 - Prometheus Metrics

Production-grade metrics collection and export for monitoring.

Metrics Categories:
- HTTP request metrics (latency, status codes, throughput)
- Database metrics (query latency, connection pool)
- Pipeline metrics (execution time, phase breakdown)
- Overlay metrics (invocations, errors, fuel usage)
- Service metrics (LLM calls, embeddings, search)
- System metrics (memory, CPU)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, TypeVar, cast

import structlog

F = TypeVar("F", bound=Callable[..., Any])

logger = structlog.get_logger(__name__)


# =============================================================================
# Metric Types
# =============================================================================

@dataclass
class Counter:
    """A monotonically increasing counter."""
    name: str
    description: str
    labels: list[str] = field(default_factory=list)
    _values: dict[tuple[str, ...], float] = field(default_factory=dict)
    # SECURITY FIX: Limit label cardinality to prevent memory exhaustion
    _max_cardinality: int = 1000
    _cardinality_warned: bool = field(default=False, repr=False)

    def inc(self, value: float = 1.0, **labels: str) -> None:
        """Increment the counter with cardinality protection."""
        key = self._label_key(labels)

        # Check cardinality limit for new keys
        if key not in self._values:
            if len(self._values) >= self._max_cardinality:
                if not self._cardinality_warned:
                    logger.warning(
                        f"Metric {self.name} hit cardinality limit ({self._max_cardinality}). "
                        "New label combinations will be dropped."
                    )
                    self._cardinality_warned = True
                return  # Drop new high-cardinality labels

        self._values[key] = self._values.get(key, 0) + value

    def _label_key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(labels.get(l, "") for l in self.labels)

    def collect(self) -> list[dict[str, Any]]:
        """Collect all metric values."""
        return [
            {
                "name": self.name,
                "type": "counter",
                "labels": dict(zip(self.labels, key, strict=False)),
                "value": value,
            }
            for key, value in self._values.items()
        ]


@dataclass
class Gauge:
    """A metric that can go up and down."""
    name: str
    description: str
    labels: list[str] = field(default_factory=list)
    _values: dict[tuple[str, ...], float] = field(default_factory=dict)
    # SECURITY FIX: Limit label cardinality to prevent memory exhaustion
    _max_cardinality: int = 1000
    _cardinality_warned: bool = field(default=False, repr=False)

    def _check_cardinality(self, key: tuple[str, ...]) -> bool:
        """Check if we can add a new key. Returns False if at limit."""
        if key not in self._values and len(self._values) >= self._max_cardinality:
            if not self._cardinality_warned:
                logger.warning(
                    f"Metric {self.name} hit cardinality limit ({self._max_cardinality}). "
                    "New label combinations will be dropped."
                )
                self._cardinality_warned = True
            return False
        return True

    def set(self, value: float, **labels: str) -> None:
        """Set the gauge value with cardinality protection."""
        key = self._label_key(labels)
        if not self._check_cardinality(key):
            return
        self._values[key] = value

    def inc(self, value: float = 1.0, **labels: str) -> None:
        """Increment the gauge with cardinality protection."""
        key = self._label_key(labels)
        if not self._check_cardinality(key):
            return
        self._values[key] = self._values.get(key, 0) + value

    def dec(self, value: float = 1.0, **labels: str) -> None:
        """Decrement the gauge with cardinality protection."""
        key = self._label_key(labels)
        if not self._check_cardinality(key):
            return
        self._values[key] = self._values.get(key, 0) - value

    def _label_key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(labels.get(l, "") for l in self.labels)

    def collect(self) -> list[dict[str, Any]]:
        return [
            {
                "name": self.name,
                "type": "gauge",
                "labels": dict(zip(self.labels, key, strict=False)),
                "value": value,
            }
            for key, value in self._values.items()
        ]


@dataclass
class Histogram:
    """A metric that samples observations into buckets."""
    name: str
    description: str
    labels: list[str] = field(default_factory=list)
    buckets: list[float] = field(default_factory=lambda: [
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
    ])
    # FIX: Store running statistics instead of all observations to prevent unbounded memory
    _stats: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict)
    # Keep last N observations for percentile calculation (bounded)
    _recent_observations: dict[tuple[str, ...], list[float]] = field(default_factory=dict)
    _max_observations: int = 10000  # Limit stored observations per label set
    # SECURITY FIX: Limit label cardinality to prevent memory exhaustion
    _max_cardinality: int = 1000
    _cardinality_warned: bool = field(default=False, repr=False)

    def observe(self, value: float, **labels: str) -> None:
        """Observe a value with bounded memory and cardinality protection."""
        key = self._label_key(labels)

        # SECURITY FIX: Check cardinality limit for new keys
        if key not in self._stats:
            if len(self._stats) >= self._max_cardinality:
                if not self._cardinality_warned:
                    logger.warning(
                        f"Metric {self.name} hit cardinality limit ({self._max_cardinality}). "
                        "New label combinations will be dropped."
                    )
                    self._cardinality_warned = True
                return

            self._stats[key] = {"count": 0, "sum": 0.0, "bucket_counts": dict.fromkeys(self.buckets, 0)}
            self._stats[key]["bucket_counts"][float("inf")] = 0
            self._recent_observations[key] = []

        # Update running statistics
        self._stats[key]["count"] += 1
        self._stats[key]["sum"] += value

        # Update bucket counts
        for bucket in self.buckets:
            if value <= bucket:
                self._stats[key]["bucket_counts"][bucket] += 1
        self._stats[key]["bucket_counts"][float("inf")] += 1

        # Store recent observation with eviction
        obs = self._recent_observations[key]
        obs.append(value)
        if len(obs) > self._max_observations:
            obs.pop(0)  # Remove oldest

    def _label_key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(labels.get(l, "") for l in self.labels)

    def collect(self) -> list[dict[str, Any]]:
        """Collect histogram metrics using pre-computed statistics."""
        results: list[dict[str, Any]] = []
        for key, stats in self._stats.items():
            labels = dict(zip(self.labels, key, strict=False))

            results.append({
                "name": self.name,
                "type": "histogram",
                "labels": labels,
                "buckets": stats["bucket_counts"].copy(),
                "sum": stats["sum"],
                "count": stats["count"],
            })

        return results


@dataclass
class Summary:
    """A metric that calculates quantiles."""
    name: str
    description: str
    labels: list[str] = field(default_factory=list)
    quantiles: list[float] = field(default_factory=lambda: [0.5, 0.9, 0.99])
    # FIX: Bounded storage to prevent unbounded memory growth
    _observations: dict[tuple[str, ...], list[float]] = field(default_factory=dict)
    _stats: dict[tuple[str, ...], dict[str, Any]] = field(default_factory=dict)
    _max_observations: int = 10000  # Limit for quantile calculation
    # SECURITY FIX: Limit label cardinality to prevent memory exhaustion
    _max_cardinality: int = 1000
    _cardinality_warned: bool = field(default=False, repr=False)

    def observe(self, value: float, **labels: str) -> None:
        """Observe a value with bounded memory and cardinality protection."""
        key = self._label_key(labels)

        # SECURITY FIX: Check cardinality limit for new keys
        if key not in self._observations:
            if len(self._observations) >= self._max_cardinality:
                if not self._cardinality_warned:
                    logger.warning(
                        f"Metric {self.name} hit cardinality limit ({self._max_cardinality}). "
                        "New label combinations will be dropped."
                    )
                    self._cardinality_warned = True
                return

            self._observations[key] = []
            self._stats[key] = {"count": 0, "sum": 0.0}

        # Update running stats (unbounded but just two numbers)
        self._stats[key]["count"] += 1
        self._stats[key]["sum"] += value

        # Bounded observation storage for quantile calculation
        obs = self._observations[key]
        obs.append(value)
        if len(obs) > self._max_observations:
            obs.pop(0)  # Remove oldest

    def _label_key(self, labels: dict[str, str]) -> tuple[str, ...]:
        return tuple(labels.get(l, "") for l in self.labels)

    def collect(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for key, observations in self._observations.items():
            labels = dict(zip(self.labels, key, strict=False))
            sorted_obs = sorted(observations)
            recent_count = len(sorted_obs)
            stats = self._stats.get(key, {"count": 0, "sum": 0.0})

            quantile_values = {}
            for q in self.quantiles:
                if recent_count > 0:
                    idx = int(q * recent_count)
                    idx = min(idx, recent_count - 1)
                    quantile_values[q] = sorted_obs[idx]
                else:
                    quantile_values[q] = 0

            results.append({
                "name": self.name,
                "type": "summary",
                "labels": labels,
                "quantiles": quantile_values,
                "sum": stats["sum"],  # Use running total
                "count": stats["count"],  # Use running count
            })

        return results


# =============================================================================
# Metrics Registry
# =============================================================================

class MetricsRegistry:
    """
    Central registry for all application metrics.

    Usage:
        metrics = MetricsRegistry()

        # Define metrics
        http_requests = metrics.counter(
            "forge_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        # Use metrics
        http_requests.inc(method="GET", endpoint="/api/v1/capsules", status="200")
    """

    def __init__(self, prefix: str = "forge"):
        self.prefix = prefix
        self._metrics: dict[str, Counter | Gauge | Histogram | Summary] = {}
        self._start_time = time.time()

    def counter(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Counter:
        """Create or get a counter metric."""
        full_name = f"{self.prefix}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Counter(
                name=full_name,
                description=description,
                labels=labels or [],
            )
        return cast(Counter, self._metrics[full_name])

    def gauge(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create or get a gauge metric."""
        full_name = f"{self.prefix}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Gauge(
                name=full_name,
                description=description,
                labels=labels or [],
            )
        return cast(Gauge, self._metrics[full_name])

    def histogram(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """Create or get a histogram metric."""
        full_name = f"{self.prefix}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Histogram(
                name=full_name,
                description=description,
                labels=labels or [],
                buckets=buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )
        return cast(Histogram, self._metrics[full_name])

    def summary(
        self,
        name: str,
        description: str,
        labels: list[str] | None = None,
        quantiles: list[float] | None = None,
    ) -> Summary:
        """Create or get a summary metric."""
        full_name = f"{self.prefix}_{name}"
        if full_name not in self._metrics:
            self._metrics[full_name] = Summary(
                name=full_name,
                description=description,
                labels=labels or [],
                quantiles=quantiles or [0.5, 0.9, 0.99],
            )
        return cast(Summary, self._metrics[full_name])

    def collect_all(self) -> list[dict[str, Any]]:
        """Collect all metrics."""
        results = []
        for metric in self._metrics.values():
            results.extend(metric.collect())
        return results

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        for metric in self._metrics.values():
            # Add HELP and TYPE
            lines.append(f"# HELP {metric.name} {metric.description}")

            if isinstance(metric, Counter):
                lines.append(f"# TYPE {metric.name} counter")
                for item in metric.collect():
                    label_str = self._format_labels(item["labels"])
                    lines.append(f"{metric.name}{label_str} {item['value']}")

            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {metric.name} gauge")
                for item in metric.collect():
                    label_str = self._format_labels(item["labels"])
                    lines.append(f"{metric.name}{label_str} {item['value']}")

            elif isinstance(metric, Histogram):
                lines.append(f"# TYPE {metric.name} histogram")
                for item in metric.collect():
                    base_labels = item["labels"]
                    for bucket, count in item["buckets"].items():
                        bucket_labels = {**base_labels, "le": str(bucket)}
                        label_str = self._format_labels(bucket_labels)
                        lines.append(f"{metric.name}_bucket{label_str} {count}")

                    label_str = self._format_labels(base_labels)
                    lines.append(f"{metric.name}_sum{label_str} {item['sum']}")
                    lines.append(f"{metric.name}_count{label_str} {item['count']}")

            elif isinstance(metric, Summary):
                lines.append(f"# TYPE {metric.name} summary")
                for item in metric.collect():
                    base_labels = item["labels"]
                    for quantile, value in item["quantiles"].items():
                        q_labels = {**base_labels, "quantile": str(quantile)}
                        label_str = self._format_labels(q_labels)
                        lines.append(f"{metric.name}{label_str} {value}")

                    label_str = self._format_labels(base_labels)
                    lines.append(f"{metric.name}_sum{label_str} {item['sum']}")
                    lines.append(f"{metric.name}_count{label_str} {item['count']}")

            lines.append("")

        # Add process metrics
        lines.append(f"# HELP {self.prefix}_process_start_time_seconds Start time of the process")
        lines.append(f"# TYPE {self.prefix}_process_start_time_seconds gauge")
        lines.append(f"{self.prefix}_process_start_time_seconds {self._start_time}")

        return "\n".join(lines)

    def _format_labels(self, labels: dict[str, Any]) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in labels.items() if v]
        return "{" + ",".join(parts) + "}" if parts else ""


# =============================================================================
# Pre-defined Forge Metrics
# =============================================================================

# Global registry
metrics = MetricsRegistry()

# HTTP Metrics
http_requests_total = metrics.counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = metrics.histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

http_requests_in_progress = metrics.gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method"],
)

# Database Metrics
db_query_duration_seconds = metrics.histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
)

db_connections_active = metrics.gauge(
    "db_connections_active",
    "Active database connections",
)

db_errors_total = metrics.counter(
    "db_errors_total",
    "Total database errors",
    ["operation", "error_type"],
)

# Pipeline Metrics
pipeline_executions_total = metrics.counter(
    "pipeline_executions_total",
    "Total pipeline executions",
    ["status"],
)

pipeline_duration_seconds = metrics.histogram(
    "pipeline_duration_seconds",
    "Pipeline execution duration in seconds",
    ["phase"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Overlay Metrics
overlay_invocations_total = metrics.counter(
    "overlay_invocations_total",
    "Total overlay invocations",
    ["overlay", "status"],
)

overlay_fuel_consumed = metrics.counter(
    "overlay_fuel_consumed_total",
    "Total fuel consumed by overlays",
    ["overlay"],
)

overlay_errors_total = metrics.counter(
    "overlay_errors_total",
    "Total overlay errors",
    ["overlay", "error_type"],
)

# Service Metrics
llm_requests_total = metrics.counter(
    "llm_requests_total",
    "Total LLM requests",
    ["provider", "model", "status"],
)

llm_tokens_total = metrics.counter(
    "llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "model", "type"],
)

embedding_requests_total = metrics.counter(
    "embedding_requests_total",
    "Total embedding requests",
    ["provider", "status"],
)

search_requests_total = metrics.counter(
    "search_requests_total",
    "Total search requests",
    ["mode", "status"],
)

search_duration_seconds = metrics.histogram(
    "search_duration_seconds",
    "Search request duration in seconds",
    ["mode"],
)

# Capsule Metrics
capsules_created_total = metrics.counter(
    "capsules_created_total",
    "Total capsules created",
    ["type"],
)

capsules_active = metrics.gauge(
    "capsules_active_total",
    "Total active capsules",
    ["type"],
)

# Governance Metrics
proposals_created_total = metrics.counter(
    "proposals_created_total",
    "Total proposals created",
    ["type"],
)

votes_cast_total = metrics.counter(
    "votes_cast_total",
    "Total votes cast",
    ["choice"],
)

# Immune System Metrics
circuit_breaker_state = metrics.gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["circuit"],
)

health_check_status = metrics.gauge(
    "health_check_status",
    "Health check status (0=unhealthy, 1=healthy)",
    ["component"],
)

canary_traffic_percent = metrics.gauge(
    "canary_traffic_percent",
    "Current canary traffic percentage",
    ["overlay"],
)


# =============================================================================
# Decorators and Context Managers
# =============================================================================

def track_time(histogram: Histogram, **labels: str) -> Callable[[F], F]:
    """Decorator to track function execution time."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start, **labels)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start, **labels)

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)
    return decorator


@asynccontextmanager
async def track_in_progress(gauge: Gauge, **labels: str) -> AsyncIterator[None]:
    """Context manager to track in-progress operations."""
    gauge.inc(1.0, **labels)
    try:
        yield
    finally:
        gauge.dec(1.0, **labels)


# =============================================================================
# FastAPI Integration
# =============================================================================

def add_metrics_middleware(app: Any) -> None:
    """Add metrics middleware to FastAPI app."""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response as StarletteResponse

    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> StarletteResponse:
            method = request.method
            path = request.url.path

            # Track in-progress requests
            http_requests_in_progress.inc(method=method)
            start_time = time.time()

            try:
                response = await call_next(request)
                status = str(response.status_code)

                # Record metrics
                http_requests_total.inc(method=method, endpoint=path, status=status)
                http_request_duration_seconds.observe(
                    time.time() - start_time,
                    method=method,
                    endpoint=path,
                )

                return response  # type: ignore[no-any-return]
            except Exception:
                http_requests_total.inc(method=method, endpoint=path, status="500")
                raise
            finally:
                http_requests_in_progress.dec(method=method)

    app.add_middleware(MetricsMiddleware)


def create_metrics_endpoint(app: Any) -> None:
    """Create /metrics endpoint for Prometheus scraping."""
    from fastapi import Response

    @app.get("/metrics", include_in_schema=False)  # type: ignore[untyped-decorator]
    async def prometheus_metrics() -> Response:
        return Response(
            content=metrics.to_prometheus_format(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )


# =============================================================================
# Global Functions
# =============================================================================

def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return metrics


def reset_metrics() -> None:
    """Reset all metrics (for testing)."""
    global metrics
    metrics = MetricsRegistry()


__all__ = [
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    "metrics",
    "get_metrics_registry",
    "track_time",
    "track_in_progress",
    "add_metrics_middleware",
    "create_metrics_endpoint",
    # Pre-defined metrics
    "http_requests_total",
    "http_request_duration_seconds",
    "db_query_duration_seconds",
    "pipeline_executions_total",
    "pipeline_duration_seconds",
    "overlay_invocations_total",
    "llm_requests_total",
    "embedding_requests_total",
    "search_requests_total",
]
