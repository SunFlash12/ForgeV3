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

import time
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from functools import wraps

import structlog

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
    _values: dict[tuple, float] = field(default_factory=dict)
    
    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment the counter."""
        key = self._label_key(labels)
        self._values[key] = self._values.get(key, 0) + value
    
    def _label_key(self, labels: dict) -> tuple:
        return tuple(labels.get(l, "") for l in self.labels)
    
    def collect(self) -> list[dict]:
        """Collect all metric values."""
        return [
            {
                "name": self.name,
                "type": "counter",
                "labels": dict(zip(self.labels, key)),
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
    _values: dict[tuple, float] = field(default_factory=dict)
    
    def set(self, value: float, **labels) -> None:
        """Set the gauge value."""
        key = self._label_key(labels)
        self._values[key] = value
    
    def inc(self, value: float = 1.0, **labels) -> None:
        """Increment the gauge."""
        key = self._label_key(labels)
        self._values[key] = self._values.get(key, 0) + value
    
    def dec(self, value: float = 1.0, **labels) -> None:
        """Decrement the gauge."""
        key = self._label_key(labels)
        self._values[key] = self._values.get(key, 0) - value
    
    def _label_key(self, labels: dict) -> tuple:
        return tuple(labels.get(l, "") for l in self.labels)
    
    def collect(self) -> list[dict]:
        return [
            {
                "name": self.name,
                "type": "gauge",
                "labels": dict(zip(self.labels, key)),
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
    _observations: dict[tuple, list[float]] = field(default_factory=dict)
    
    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        key = self._label_key(labels)
        if key not in self._observations:
            self._observations[key] = []
        self._observations[key].append(value)
    
    def _label_key(self, labels: dict) -> tuple:
        return tuple(labels.get(l, "") for l in self.labels)
    
    def collect(self) -> list[dict]:
        results = []
        for key, observations in self._observations.items():
            labels = dict(zip(self.labels, key))
            
            # Calculate bucket counts
            bucket_counts = {}
            for bucket in self.buckets:
                bucket_counts[bucket] = sum(1 for o in observations if o <= bucket)
            bucket_counts[float("inf")] = len(observations)
            
            # Sum and count
            total = sum(observations)
            count = len(observations)
            
            results.append({
                "name": self.name,
                "type": "histogram",
                "labels": labels,
                "buckets": bucket_counts,
                "sum": total,
                "count": count,
            })
        
        return results


@dataclass
class Summary:
    """A metric that calculates quantiles."""
    name: str
    description: str
    labels: list[str] = field(default_factory=list)
    quantiles: list[float] = field(default_factory=lambda: [0.5, 0.9, 0.99])
    _observations: dict[tuple, list[float]] = field(default_factory=dict)
    
    def observe(self, value: float, **labels) -> None:
        """Observe a value."""
        key = self._label_key(labels)
        if key not in self._observations:
            self._observations[key] = []
        self._observations[key].append(value)
    
    def _label_key(self, labels: dict) -> tuple:
        return tuple(labels.get(l, "") for l in self.labels)
    
    def collect(self) -> list[dict]:
        results = []
        for key, observations in self._observations.items():
            labels = dict(zip(self.labels, key))
            sorted_obs = sorted(observations)
            count = len(sorted_obs)
            
            quantile_values = {}
            for q in self.quantiles:
                if count > 0:
                    idx = int(q * count)
                    idx = min(idx, count - 1)
                    quantile_values[q] = sorted_obs[idx]
                else:
                    quantile_values[q] = 0
            
            results.append({
                "name": self.name,
                "type": "summary",
                "labels": labels,
                "quantiles": quantile_values,
                "sum": sum(observations),
                "count": count,
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
        return self._metrics[full_name]
    
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
        return self._metrics[full_name]
    
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
        return self._metrics[full_name]
    
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
        return self._metrics[full_name]
    
    def collect_all(self) -> list[dict]:
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
    
    def _format_labels(self, labels: dict) -> str:
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

def track_time(histogram: Histogram, **labels):
    """Decorator to track function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start, **labels)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start, **labels)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


@asynccontextmanager
async def track_in_progress(gauge: Gauge, **labels):
    """Context manager to track in-progress operations."""
    gauge.inc(**labels)
    try:
        yield
    finally:
        gauge.dec(**labels)


# =============================================================================
# FastAPI Integration
# =============================================================================

def add_metrics_middleware(app):
    """Add metrics middleware to FastAPI app."""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
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
                
                return response
            except Exception as e:
                http_requests_total.inc(method=method, endpoint=path, status="500")
                raise
            finally:
                http_requests_in_progress.dec(method=method)
    
    app.add_middleware(MetricsMiddleware)


def create_metrics_endpoint(app):
    """Create /metrics endpoint for Prometheus scraping."""
    from fastapi import Response
    
    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics():
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
