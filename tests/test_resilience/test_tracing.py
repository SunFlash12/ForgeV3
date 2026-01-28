"""
Tests for Distributed Tracing
=============================

Tests for forge/resilience/observability/tracing.py
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.observability.tracing import (
    ForgeTracer,
    NoOpSpan,
    NoOpTracer,
    OperationType,
    SpanContext,
    _sanitize_attributes,
    get_tracer,
    trace_operation,
)


class TestOperationType:
    """Tests for OperationType enum."""

    def test_capsule_operations(self):
        """Test capsule operation types."""
        assert OperationType.CAPSULE_CREATE.value == "capsule.create"
        assert OperationType.CAPSULE_READ.value == "capsule.read"
        assert OperationType.CAPSULE_UPDATE.value == "capsule.update"
        assert OperationType.CAPSULE_DELETE.value == "capsule.delete"
        assert OperationType.CAPSULE_SEARCH.value == "capsule.search"

    def test_lineage_operations(self):
        """Test lineage operation types."""
        assert OperationType.LINEAGE_QUERY.value == "lineage.query"
        assert OperationType.LINEAGE_BUILD.value == "lineage.build"

    def test_governance_operations(self):
        """Test governance operation types."""
        assert OperationType.GOVERNANCE_VOTE.value == "governance.vote"
        assert OperationType.GOVERNANCE_PROPOSE.value == "governance.propose"
        assert OperationType.GHOST_COUNCIL.value == "ghost_council.deliberate"

    def test_system_operations(self):
        """Test system operation types."""
        assert OperationType.AUTH_LOGIN.value == "auth.login"
        assert OperationType.CACHE_GET.value == "cache.get"
        assert OperationType.DB_QUERY.value == "db.query"


class TestSpanContext:
    """Tests for SpanContext dataclass."""

    def test_context_creation(self):
        """Test creating a span context."""
        context = SpanContext(
            trace_id="trace_123",
            span_id="span_456",
            parent_span_id="parent_789",
            operation="test.operation",
            attributes={"key": "value"},
        )

        assert context.trace_id == "trace_123"
        assert context.span_id == "span_456"
        assert context.parent_span_id == "parent_789"
        assert context.operation == "test.operation"
        assert context.attributes == {"key": "value"}
        assert context.start_time is not None


class TestNoOpSpan:
    """Tests for NoOpSpan class."""

    def test_context_manager(self):
        """Test NoOpSpan as context manager."""
        span = NoOpSpan()

        with span as s:
            assert s is span

    def test_set_attribute(self):
        """Test set_attribute does nothing."""
        span = NoOpSpan()

        # Should not raise
        span.set_attribute("key", "value")
        span.set_attribute("number", 42)

    def test_set_status(self):
        """Test set_status does nothing."""
        span = NoOpSpan()

        # Should not raise
        span.set_status(None)
        span.set_status({"status": "ok"})

    def test_record_exception(self):
        """Test record_exception does nothing."""
        span = NoOpSpan()

        # Should not raise
        span.record_exception(ValueError("test error"))

    def test_add_event(self):
        """Test add_event does nothing."""
        span = NoOpSpan()

        # Should not raise
        span.add_event("event_name")
        span.add_event("event_name", attributes={"key": "value"})


class TestNoOpTracer:
    """Tests for NoOpTracer class."""

    def test_start_as_current_span(self):
        """Test start_as_current_span returns NoOpSpan."""
        tracer = NoOpTracer()

        span = tracer.start_as_current_span("test_operation")

        assert isinstance(span, NoOpSpan)

    def test_start_span(self):
        """Test start_span returns NoOpSpan."""
        tracer = NoOpTracer()

        span = tracer.start_span("test_span")

        assert isinstance(span, NoOpSpan)


class TestSanitizeAttributes:
    """Tests for _sanitize_attributes function."""

    def test_removes_password(self):
        """Test password is removed."""
        attrs = {"username": "user", "password": "secret123"}

        result = _sanitize_attributes(attrs)

        assert "username" in result
        assert "password" not in result

    def test_removes_api_key(self):
        """Test API key is removed."""
        attrs = {"endpoint": "/api", "api_key": "key123"}

        result = _sanitize_attributes(attrs)

        assert "endpoint" in result
        assert "api_key" not in result

    def test_removes_token(self):
        """Test token is removed."""
        attrs = {"user_id": "123", "token": "jwt_token", "access_token": "token"}

        result = _sanitize_attributes(attrs)

        assert "user_id" in result
        assert "token" not in result
        assert "access_token" not in result

    def test_case_insensitive(self):
        """Test removal is case insensitive."""
        attrs = {"PASSWORD": "secret", "Api_Key": "key", "TOKEN": "t"}

        result = _sanitize_attributes(attrs)

        assert len(result) == 0

    def test_preserves_safe_attributes(self):
        """Test safe attributes are preserved."""
        attrs = {
            "operation": "test",
            "user_id": "123",
            "request_id": "req_456",
            "duration_ms": 100,
        }

        result = _sanitize_attributes(attrs)

        assert result == attrs


class TestForgeTracer:
    """Tests for ForgeTracer class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.enable_tracing = True
        config.otlp_endpoint = None
        config.service_name = "test-service"
        config.version = "1.0.0"
        config.environment = "test"
        return config

    @pytest.fixture
    def tracer(self, mock_config):
        """Create a ForgeTracer instance."""
        with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            return ForgeTracer()

    def test_tracer_creation(self, tracer):
        """Test tracer creation."""
        assert tracer._initialized is False
        assert tracer._tracer is None

    def test_initialize_disabled(self, mock_config):
        """Test initialization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            tracer = ForgeTracer()
            tracer.initialize()

            assert tracer._initialized is True
            assert isinstance(tracer._tracer, NoOpTracer)

    def test_initialize_no_otel(self, mock_config):
        """Test initialization without OpenTelemetry."""
        with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            with patch("forge.resilience.observability.tracing.OTEL_AVAILABLE", False):
                tracer = ForgeTracer()
                tracer.initialize()

                assert tracer._initialized is True
                assert isinstance(tracer._tracer, NoOpTracer)

    def test_span_context_manager(self, tracer):
        """Test span as context manager."""
        tracer.initialize()

        with tracer.span("test.operation") as span:
            assert span is not None

    def test_span_with_attributes(self, tracer):
        """Test span with attributes."""
        tracer.initialize()

        attrs = {"key": "value", "number": 42}

        with tracer.span("test.operation", attributes=attrs) as span:
            assert span is not None

    def test_span_sanitizes_sensitive_attributes(self, tracer):
        """Test span sanitizes sensitive attributes."""
        tracer.initialize()

        # This should not raise, even with sensitive data
        attrs = {"user_id": "123", "password": "secret"}

        with tracer.span("test.operation", attributes=attrs):
            pass

    def test_capsule_span(self, tracer):
        """Test capsule span."""
        tracer.initialize()

        with tracer.capsule_span(
            OperationType.CAPSULE_CREATE,
            capsule_id="cap_123",
            capsule_type="KNOWLEDGE",
        ) as span:
            assert span is not None

    def test_lineage_span(self, tracer):
        """Test lineage span."""
        tracer.initialize()

        with tracer.lineage_span("cap_123", depth=5) as span:
            assert span is not None

    def test_governance_span(self, tracer):
        """Test governance span."""
        tracer.initialize()

        with tracer.governance_span(
            OperationType.GOVERNANCE_VOTE, proposal_id="prop_123"
        ) as span:
            assert span is not None

    def test_db_span(self, tracer):
        """Test database span."""
        tracer.initialize()

        with tracer.db_span("query", query_type="cypher") as span:
            assert span is not None

    def test_extract_context_no_otel(self, tracer):
        """Test extract_context without OpenTelemetry."""
        tracer.initialize()

        headers = {"traceparent": "00-abc123-def456-01"}

        result = tracer.extract_context(headers)

        # With NoOpTracer, returns None
        assert result is None

    def test_inject_context_no_otel(self, tracer):
        """Test inject_context without OpenTelemetry."""
        tracer.initialize()

        headers = {}

        # Should not raise
        tracer.inject_context(headers)

    def test_get_current_trace_id_no_otel(self, tracer):
        """Test get_current_trace_id without OpenTelemetry."""
        with patch("forge.resilience.observability.tracing.OTEL_AVAILABLE", False):
            tracer.initialize()

            result = tracer.get_current_trace_id()

            assert result is None


class TestTraceOperationDecorator:
    """Tests for the trace_operation decorator."""

    def test_trace_sync_function(self):
        """Test decorator on sync function."""
        with patch("forge.resilience.observability.tracing._forge_tracer", None):
            with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_tracing = False
                mock.return_value = mock_config

                @trace_operation("test.operation")
                def sync_function():
                    return "result"

                result = sync_function()

                assert result == "result"

    @pytest.mark.asyncio
    async def test_trace_async_function(self):
        """Test decorator on async function."""
        with patch("forge.resilience.observability.tracing._forge_tracer", None):
            with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_tracing = False
                mock.return_value = mock_config

                @trace_operation("test.async_operation")
                async def async_function():
                    await asyncio.sleep(0.01)
                    return "async_result"

                result = await async_function()

                assert result == "async_result"

    def test_trace_with_attributes(self):
        """Test decorator with attributes."""
        with patch("forge.resilience.observability.tracing._forge_tracer", None):
            with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = False
                mock.return_value = mock_config

                @trace_operation("test.operation", attributes={"key": "value"})
                def function_with_attrs():
                    return "result"

                result = function_with_attrs()

                assert result == "result"


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_tracer(self):
        """Test getting global tracer instance."""
        with patch("forge.resilience.observability.tracing._forge_tracer", None):
            with patch("forge.resilience.observability.tracing.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_tracing = False
                mock.return_value = mock_config

                tracer = get_tracer()

                assert isinstance(tracer, ForgeTracer)
                assert tracer._initialized is True
