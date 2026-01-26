"""
Distributed Tracing with OpenTelemetry
======================================

Provides tracing capabilities for Forge operations.
Integrates with OpenTelemetry for distributed tracing across services.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)

# Type variables for generic decorators
F = TypeVar('F', bound=Callable[..., Any])

# Try to import OpenTelemetry, but allow graceful degradation
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    otel_trace = None
    TracerProvider = None
    BatchSpanProcessor = None
    Resource = None
    OTLPSpanExporter = None
    Status = None
    StatusCode = None
    SpanKind = None


class OperationType(Enum):
    """Types of operations for tracing categorization."""

    CAPSULE_CREATE = "capsule.create"
    CAPSULE_READ = "capsule.read"
    CAPSULE_UPDATE = "capsule.update"
    CAPSULE_DELETE = "capsule.delete"
    CAPSULE_SEARCH = "capsule.search"
    LINEAGE_QUERY = "lineage.query"
    LINEAGE_BUILD = "lineage.build"
    GOVERNANCE_VOTE = "governance.vote"
    GOVERNANCE_PROPOSE = "governance.propose"
    GHOST_COUNCIL = "ghost_council.deliberate"
    OVERLAY_ACTIVATE = "overlay.activate"
    OVERLAY_DEACTIVATE = "overlay.deactivate"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    PIPELINE_PROCESS = "pipeline.process"
    CACHE_GET = "cache.get"
    CACHE_SET = "cache.set"
    DB_QUERY = "db.query"
    DB_WRITE = "db.write"


@dataclass
class SpanContext:
    """Context information for a trace span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    attributes: dict[str, Any] = field(default_factory=dict)


class NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def __enter__(self) -> NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass


class NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        return NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        return NoOpSpan()


class ForgeTracer:
    """
    Forge-specific tracer wrapping OpenTelemetry.

    Provides convenient methods for tracing Forge operations
    with automatic attribute enrichment.
    """

    def __init__(self) -> None:
        self._config = get_resilience_config().observability
        self._tracer: NoOpTracer | Any = None
        self._initialized = False
        self._propagator: Any = None

    def initialize(self) -> None:
        """Initialize the OpenTelemetry tracer."""
        if self._initialized:
            return

        if not self._config.enabled or not self._config.enable_tracing:
            logger.info("tracing_disabled")
            self._tracer = NoOpTracer()
            self._initialized = True
            return

        if not OTEL_AVAILABLE:
            logger.warning(
                "opentelemetry_not_available",
                fallback="noop_tracer"
            )
            self._tracer = NoOpTracer()
            self._initialized = True
            return

        try:
            # Create resource with service information
            resource = Resource.create({
                SERVICE_NAME: self._config.service_name,
                SERVICE_VERSION: self._config.version,
                "deployment.environment": self._config.environment,
            })

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Add OTLP exporter
            if self._config.otlp_endpoint:
                exporter = OTLPSpanExporter(
                    endpoint=self._config.otlp_endpoint,
                    insecure=True  # For local development
                )
                provider.add_span_processor(
                    BatchSpanProcessor(exporter)
                )

            # Set as global provider
            otel_trace.set_tracer_provider(provider)

            # Get tracer
            self._tracer = otel_trace.get_tracer(
                self._config.service_name,
                self._config.version
            )

            # Initialize propagator for distributed tracing
            self._propagator = TraceContextTextMapPropagator()

            self._initialized = True
            logger.info(
                "tracing_initialized",
                endpoint=self._config.otlp_endpoint,
                service=self._config.service_name
            )

        except Exception as e:
            logger.error("tracing_init_error", error=str(e))
            self._tracer = NoOpTracer()
            self._initialized = True

    @contextmanager
    def span(
        self,
        operation: str,
        kind: Any | None = None,
        attributes: dict[str, Any] | None = None
    ) -> Generator[Any, None, None]:
        """
        Create a trace span for an operation.

        Args:
            operation: Name of the operation being traced
            kind: Span kind (server, client, internal, etc.)
            attributes: Additional span attributes

        Yields:
            The active span
        """
        if not self._initialized:
            self.initialize()

        span_kind = kind
        if OTEL_AVAILABLE and span_kind is None:
            span_kind = SpanKind.INTERNAL

        assert self._tracer is not None
        with self._tracer.start_as_current_span(
            operation,
            kind=span_kind,
            attributes=attributes or {}
        ) as active_span:
            try:
                yield active_span
            except Exception as e:
                if OTEL_AVAILABLE and hasattr(active_span, 'record_exception'):
                    active_span.record_exception(e)
                    active_span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    @contextmanager
    def capsule_span(
        self,
        operation_type: OperationType,
        capsule_id: str | None = None,
        capsule_type: str | None = None,
        **extra_attributes: Any
    ) -> Generator[Any, None, None]:
        """Create a span for capsule operations."""
        attributes: dict[str, Any] = {
            "forge.operation": operation_type.value,
            **extra_attributes
        }

        if capsule_id:
            attributes["forge.capsule.id"] = capsule_id
        if capsule_type:
            attributes["forge.capsule.type"] = capsule_type

        with self.span(operation_type.value, attributes=attributes) as active_span:
            yield active_span

    @contextmanager
    def lineage_span(
        self,
        capsule_id: str,
        depth: int,
        operation_type: OperationType = OperationType.LINEAGE_QUERY
    ) -> Generator[Any, None, None]:
        """Create a span for lineage operations."""
        attributes: dict[str, Any] = {
            "forge.operation": operation_type.value,
            "forge.capsule.id": capsule_id,
            "forge.lineage.depth": depth,
        }

        with self.span(operation_type.value, attributes=attributes) as active_span:
            yield active_span

    @contextmanager
    def governance_span(
        self,
        operation_type: OperationType,
        proposal_id: str | None = None,
        **extra_attributes: Any
    ) -> Generator[Any, None, None]:
        """Create a span for governance operations."""
        attributes: dict[str, Any] = {
            "forge.operation": operation_type.value,
            **extra_attributes
        }

        if proposal_id:
            attributes["forge.proposal.id"] = proposal_id

        with self.span(operation_type.value, attributes=attributes) as active_span:
            yield active_span

    @contextmanager
    def db_span(
        self,
        operation: str,
        query_type: str = "cypher",
        **extra_attributes: Any
    ) -> Generator[Any, None, None]:
        """Create a span for database operations."""
        attributes: dict[str, Any] = {
            "db.system": "neo4j",
            "db.operation": operation,
            "db.query.type": query_type,
            **extra_attributes
        }

        span_kind = SpanKind.CLIENT if OTEL_AVAILABLE else None

        with self.span(f"db.{operation}", kind=span_kind, attributes=attributes) as active_span:
            yield active_span

    def extract_context(self, headers: dict[str, str]) -> Any:
        """Extract trace context from HTTP headers."""
        if not OTEL_AVAILABLE or not self._propagator:
            return None

        result: Any = self._propagator.extract(carrier=headers)
        return result

    def inject_context(self, headers: dict[str, str]) -> None:
        """Inject trace context into HTTP headers."""
        if not OTEL_AVAILABLE or not self._propagator:
            return

        self._propagator.inject(carrier=headers)

    def get_current_trace_id(self) -> str | None:
        """Get the current trace ID."""
        if not OTEL_AVAILABLE:
            return None

        span: Any = otel_trace.get_current_span()
        if span:
            ctx = span.get_span_context()
            if ctx.is_valid:
                return format(ctx.trace_id, '032x')

        return None


# Global tracer instance
_forge_tracer: ForgeTracer | None = None


def get_tracer() -> ForgeTracer:
    """Get or create the global Forge tracer instance."""
    global _forge_tracer
    if _forge_tracer is None:
        _forge_tracer = ForgeTracer()
        _forge_tracer.initialize()
    return _forge_tracer


def trace_operation(
    operation: str,
    attributes: dict[str, Any] | None = None
) -> Callable[[F], F]:
    """
    Decorator to trace a function execution.

    Args:
        operation: Name of the operation
        attributes: Additional span attributes

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.span(operation, attributes=attributes):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.span(operation, attributes=attributes):
                return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
