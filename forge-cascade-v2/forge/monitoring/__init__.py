"""
Forge Cascade V2 - Monitoring Module

Production monitoring components:
- Prometheus metrics
- Structured logging
- Health checks
- Alerting
"""

from .logging import configure_logging, get_logger
from .metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    Summary,
    add_metrics_middleware,
    create_metrics_endpoint,
    db_query_duration_seconds,
    get_metrics_registry,
    http_request_duration_seconds,
    http_requests_total,
    metrics,
    overlay_invocations_total,
    pipeline_executions_total,
    track_in_progress,
    track_time,
)

__all__ = [
    # Registry and types
    "MetricsRegistry",
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    # Global instance and factory
    "metrics",
    "get_metrics_registry",
    # Decorators
    "track_time",
    "track_in_progress",
    # Middleware and endpoints
    "add_metrics_middleware",
    "create_metrics_endpoint",
    # SECURITY FIX (Audit 4 - M): Export pre-defined metrics for external access
    "http_requests_total",
    "http_request_duration_seconds",
    "db_query_duration_seconds",
    "pipeline_executions_total",
    "overlay_invocations_total",
    # Logging
    "configure_logging",
    "get_logger",
]
