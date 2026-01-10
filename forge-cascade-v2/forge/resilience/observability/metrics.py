"""
Metrics Collection with OpenTelemetry
=====================================

Provides Prometheus-compatible metrics for Forge operations.
Tracks key performance indicators and system health metrics.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)

# Try to import OpenTelemetry metrics, but allow graceful degradation
try:
    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    OTEL_METRICS_AVAILABLE = True
except ImportError:
    OTEL_METRICS_AVAILABLE = False
    metrics = None
    MeterProvider = None
    PeriodicExportingMetricReader = None
    OTLPMetricExporter = None


class MetricType(Enum):
    """Types of metrics collected."""

    # Capsule metrics
    CAPSULE_CREATED = "capsule_created_total"
    CAPSULE_UPDATED = "capsule_updated_total"
    CAPSULE_DELETED = "capsule_deleted_total"
    CAPSULE_SEARCH_LATENCY = "capsule_search_latency_seconds"

    # Lineage metrics
    LINEAGE_DEPTH = "lineage_depth"
    LINEAGE_QUERY_LATENCY = "lineage_query_latency_seconds"

    # Cache metrics
    CACHE_HIT = "cache_hit_total"
    CACHE_MISS = "cache_miss_total"
    CACHE_INVALIDATION = "cache_invalidation_total"

    # Governance metrics
    PROPOSAL_CREATED = "proposal_created_total"
    VOTE_CAST = "vote_cast_total"
    GHOST_COUNCIL_DELIBERATION = "ghost_council_deliberation_total"

    # Auth metrics
    LOGIN_SUCCESS = "login_success_total"
    LOGIN_FAILURE = "login_failure_total"

    # Pipeline metrics
    PIPELINE_EXECUTION_LATENCY = "pipeline_execution_latency_seconds"
    PIPELINE_PHASE_LATENCY = "pipeline_phase_latency_seconds"

    # System metrics
    DB_QUERY_LATENCY = "db_query_latency_seconds"
    REQUEST_LATENCY = "http_request_latency_seconds"
    REQUEST_COUNT = "http_request_total"
    ERROR_COUNT = "error_total"


@dataclass
class MetricValue:
    """Represents a metric measurement."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class NoOpCounter:
    """No-op counter for when OpenTelemetry is not available."""

    def add(self, value: int, attributes: dict | None = None) -> None:
        pass


class NoOpHistogram:
    """No-op histogram for when OpenTelemetry is not available."""

    def record(self, value: float, attributes: dict | None = None) -> None:
        pass


class NoOpGauge:
    """No-op gauge for when OpenTelemetry is not available."""

    def set(self, value: float, attributes: dict | None = None) -> None:
        pass


class NoOpMeter:
    """No-op meter for when OpenTelemetry is not available."""

    def create_counter(self, name: str, **kwargs) -> NoOpCounter:
        return NoOpCounter()

    def create_histogram(self, name: str, **kwargs) -> NoOpHistogram:
        return NoOpHistogram()

    def create_up_down_counter(self, name: str, **kwargs) -> NoOpCounter:
        return NoOpCounter()


class ForgeMetrics:
    """
    Forge-specific metrics collector using OpenTelemetry.

    Provides counters, histograms, and gauges for key system metrics.
    """

    def __init__(self):
        self._config = get_resilience_config().observability
        self._meter = None
        self._initialized = False

        # Metric instruments
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}

        # In-memory stats for when OTEL is not available
        self._local_counters: dict[str, int] = {}
        self._local_histograms: dict[str, list] = {}

    def initialize(self) -> None:
        """Initialize the metrics collector."""
        if self._initialized:
            return

        if not self._config.enabled or not self._config.enable_metrics:
            logger.info("metrics_disabled")
            self._meter = NoOpMeter()
            self._initialized = True
            return

        if not OTEL_METRICS_AVAILABLE:
            logger.warning(
                "opentelemetry_metrics_not_available",
                fallback="local_metrics"
            )
            self._meter = NoOpMeter()
            self._initialized = True
            return

        try:
            # Create resource
            resource = Resource.create({
                SERVICE_NAME: self._config.service_name,
                SERVICE_VERSION: self._config.version,
                "deployment.environment": self._config.environment,
            })

            # Create metric exporter
            if self._config.otlp_endpoint:
                exporter = OTLPMetricExporter(
                    endpoint=self._config.otlp_endpoint,
                    insecure=True
                )
                reader = PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=60000  # Export every 60 seconds
                )
                provider = MeterProvider(
                    resource=resource,
                    metric_readers=[reader]
                )
            else:
                provider = MeterProvider(resource=resource)

            # Set as global provider
            metrics.set_meter_provider(provider)

            # Get meter
            self._meter = metrics.get_meter(
                self._config.service_name,
                self._config.version
            )

            # Initialize standard metrics
            self._init_standard_metrics()

            self._initialized = True
            logger.info(
                "metrics_initialized",
                endpoint=self._config.otlp_endpoint,
                service=self._config.service_name
            )

        except Exception as e:
            logger.error("metrics_init_error", error=str(e))
            self._meter = NoOpMeter()
            self._initialized = True

    def _init_standard_metrics(self) -> None:
        """Initialize standard Forge metrics."""
        # Counters
        self._counters["capsules_created"] = self._meter.create_counter(
            "forge_capsules_created_total",
            description="Total number of capsules created",
            unit="1"
        )
        self._counters["capsules_updated"] = self._meter.create_counter(
            "forge_capsules_updated_total",
            description="Total number of capsules updated",
            unit="1"
        )
        self._counters["capsules_deleted"] = self._meter.create_counter(
            "forge_capsules_deleted_total",
            description="Total number of capsules deleted",
            unit="1"
        )
        self._counters["cache_hits"] = self._meter.create_counter(
            "forge_cache_hits_total",
            description="Total cache hits",
            unit="1"
        )
        self._counters["cache_misses"] = self._meter.create_counter(
            "forge_cache_misses_total",
            description="Total cache misses",
            unit="1"
        )
        self._counters["proposals_created"] = self._meter.create_counter(
            "forge_proposals_created_total",
            description="Total governance proposals created",
            unit="1"
        )
        self._counters["votes_cast"] = self._meter.create_counter(
            "forge_votes_cast_total",
            description="Total votes cast",
            unit="1"
        )
        self._counters["logins"] = self._meter.create_counter(
            "forge_logins_total",
            description="Total login attempts",
            unit="1"
        )
        self._counters["errors"] = self._meter.create_counter(
            "forge_errors_total",
            description="Total errors",
            unit="1"
        )

        # Histograms
        self._histograms["request_latency"] = self._meter.create_histogram(
            "forge_http_request_duration_seconds",
            description="HTTP request latency in seconds",
            unit="s"
        )
        self._histograms["db_query_latency"] = self._meter.create_histogram(
            "forge_db_query_duration_seconds",
            description="Database query latency in seconds",
            unit="s"
        )
        self._histograms["search_latency"] = self._meter.create_histogram(
            "forge_search_duration_seconds",
            description="Search operation latency in seconds",
            unit="s"
        )
        self._histograms["pipeline_latency"] = self._meter.create_histogram(
            "forge_pipeline_duration_seconds",
            description="Pipeline execution latency in seconds",
            unit="s"
        )
        self._histograms["lineage_query_latency"] = self._meter.create_histogram(
            "forge_lineage_query_duration_seconds",
            description="Lineage query latency in seconds",
            unit="s"
        )

    def increment(
        self,
        metric_name: str,
        value: int = 1,
        labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric."""
        if not self._initialized:
            self.initialize()

        counter = self._counters.get(metric_name)
        if counter:
            counter.add(value, attributes=labels or {})

        # Also track locally
        key = f"{metric_name}:{labels}" if labels else metric_name
        self._local_counters[key] = self._local_counters.get(key, 0) + value

    def record_latency(
        self,
        metric_name: str,
        latency_seconds: float,
        labels: dict[str, str] | None = None
    ) -> None:
        """Record a latency measurement."""
        if not self._initialized:
            self.initialize()

        histogram = self._histograms.get(metric_name)
        if histogram:
            histogram.record(latency_seconds, attributes=labels or {})

        # Also track locally
        key = f"{metric_name}:{labels}" if labels else metric_name
        if key not in self._local_histograms:
            self._local_histograms[key] = []
        self._local_histograms[key].append(latency_seconds)

    # Convenience methods for common metrics

    def capsule_created(self, capsule_type: str) -> None:
        """Record capsule creation."""
        self.increment("capsules_created", labels={"type": capsule_type})

    def capsule_updated(self, capsule_type: str) -> None:
        """Record capsule update."""
        self.increment("capsules_updated", labels={"type": capsule_type})

    def capsule_deleted(self, capsule_type: str) -> None:
        """Record capsule deletion."""
        self.increment("capsules_deleted", labels={"type": capsule_type})

    def cache_hit(self, cache_type: str = "query") -> None:
        """Record cache hit."""
        self.increment("cache_hits", labels={"type": cache_type})

    def cache_miss(self, cache_type: str = "query") -> None:
        """Record cache miss."""
        self.increment("cache_misses", labels={"type": cache_type})

    def proposal_created(self, proposal_type: str) -> None:
        """Record proposal creation."""
        self.increment("proposals_created", labels={"type": proposal_type})

    def vote_cast(self, vote_type: str) -> None:
        """Record vote."""
        self.increment("votes_cast", labels={"choice": vote_type})

    def login_attempt(self, success: bool) -> None:
        """Record login attempt."""
        self.increment("logins", labels={"success": str(success).lower()})

    def error(self, error_type: str, endpoint: str = "") -> None:
        """Record error."""
        self.increment("errors", labels={"type": error_type, "endpoint": endpoint})

    def request_latency(
        self,
        latency: float,
        method: str,
        endpoint: str,
        status: int
    ) -> None:
        """Record HTTP request latency."""
        self.record_latency(
            "request_latency",
            latency,
            labels={
                "method": method,
                "endpoint": endpoint,
                "status": str(status)
            }
        )

    def db_query_latency(
        self,
        latency: float,
        operation: str,
        success: bool = True
    ) -> None:
        """Record database query latency."""
        self.record_latency(
            "db_query_latency",
            latency,
            labels={"operation": operation, "success": str(success).lower()}
        )

    def search_latency(
        self,
        latency: float,
        result_count: int = 0
    ) -> None:
        """Record search operation latency."""
        self.record_latency(
            "search_latency",
            latency,
            labels={"result_count": str(min(result_count, 100))}
        )

    def pipeline_latency(
        self,
        latency: float,
        phase: str = "total"
    ) -> None:
        """Record pipeline execution latency."""
        self.record_latency(
            "pipeline_latency",
            latency,
            labels={"phase": phase}
        )

    def lineage_query_latency(
        self,
        latency: float,
        depth: int
    ) -> None:
        """Record lineage query latency."""
        self.record_latency(
            "lineage_query_latency",
            latency,
            labels={"depth": str(min(depth, 10))}
        )

    def get_local_stats(self) -> dict[str, Any]:
        """Get locally tracked statistics."""
        return {
            "counters": dict(self._local_counters),
            "histograms": {
                k: {
                    "count": len(v),
                    "sum": sum(v) if v else 0,
                    "avg": sum(v) / len(v) if v else 0,
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self._local_histograms.items()
            }
        }


# Global metrics instance
_forge_metrics: ForgeMetrics | None = None


def get_metrics() -> ForgeMetrics:
    """Get or create the global Forge metrics instance."""
    global _forge_metrics
    if _forge_metrics is None:
        _forge_metrics = ForgeMetrics()
        _forge_metrics.initialize()
    return _forge_metrics


def timed(metric_name: str, labels: dict[str, str] | None = None) -> Callable:
    """
    Decorator to time function execution.

    Args:
        metric_name: Name of the latency metric
        labels: Additional metric labels

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            metrics_instance = get_metrics()
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                latency = time.perf_counter() - start
                metrics_instance.record_latency(metric_name, latency, labels)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            metrics_instance = get_metrics()
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                latency = time.perf_counter() - start
                metrics_instance.record_latency(metric_name, latency, labels)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
