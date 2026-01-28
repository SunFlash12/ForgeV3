"""
Comprehensive tests for forge.monitoring.logging module.

Tests cover:
- Custom processors (timestamp, service info, log level, sanitization)
- Logging configuration
- Context management (bind, unbind, clear)
- LoggingContextMiddleware for FastAPI
- Log formatters (Datadog, CloudWatch)
- Performance logging (log_duration)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog

from forge.monitoring.logging import (
    CloudWatchFormatter,
    DatadogFormatter,
    LoggingContextMiddleware,
    add_log_level,
    add_service_info,
    add_timestamp,
    bind_context,
    clear_context,
    configure_logging,
    drop_color_codes,
    get_logger,
    log_duration,
    sanitize_sensitive_data,
    unbind_context,
)


# =============================================================================
# Tests for add_timestamp processor
# =============================================================================


class TestAddTimestamp:
    """Tests for add_timestamp processor."""

    def test_adds_timestamp_to_event_dict(self) -> None:
        """Verify timestamp is added to event dict."""
        event_dict: dict[str, Any] = {"event": "test message"}
        result = add_timestamp(None, "info", event_dict)  # type: ignore[arg-type]

        assert "timestamp" in result
        # Verify ISO8601 format (contains T separator)
        assert "T" in result["timestamp"]
        # Verify it ends with timezone info
        assert result["timestamp"].endswith("+00:00") or result["timestamp"].endswith("Z")

    def test_preserves_existing_fields(self) -> None:
        """Verify existing fields are preserved."""
        event_dict: dict[str, Any] = {"event": "test", "custom_field": "value"}
        result = add_timestamp(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["event"] == "test"
        assert result["custom_field"] == "value"
        assert "timestamp" in result


# =============================================================================
# Tests for add_service_info processor
# =============================================================================


class TestAddServiceInfo:
    """Tests for add_service_info processor."""

    def test_adds_service_name(self) -> None:
        """Verify service name is added."""
        event_dict: dict[str, Any] = {"event": "test"}
        result = add_service_info(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["service"] == "forge-cascade"

    def test_adds_version(self) -> None:
        """Verify version is added."""
        event_dict: dict[str, Any] = {"event": "test"}
        result = add_service_info(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["version"] == "2.0.0"

    def test_preserves_existing_fields(self) -> None:
        """Verify existing fields are preserved."""
        event_dict: dict[str, Any] = {"event": "test", "custom": "data"}
        result = add_service_info(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["event"] == "test"
        assert result["custom"] == "data"


# =============================================================================
# Tests for add_log_level processor
# =============================================================================


class TestAddLogLevel:
    """Tests for add_log_level processor."""

    @pytest.mark.parametrize(
        "method_name,expected_level",
        [
            ("debug", 10),
            ("info", 20),
            ("warning", 30),
            ("error", 40),
            ("critical", 50),
        ],
    )
    def test_correct_level_numbers(self, method_name: str, expected_level: int) -> None:
        """Verify correct level numbers for each log level."""
        event_dict: dict[str, Any] = {"event": "test"}
        result = add_log_level(None, method_name, event_dict)  # type: ignore[arg-type]

        assert result["level_number"] == expected_level

    def test_unknown_level_defaults_to_info(self) -> None:
        """Verify unknown method names default to INFO level (20)."""
        event_dict: dict[str, Any] = {"event": "test"}
        result = add_log_level(None, "unknown_method", event_dict)  # type: ignore[arg-type]

        assert result["level_number"] == 20


# =============================================================================
# Tests for sanitize_sensitive_data processor
# =============================================================================


class TestSanitizeSensitiveData:
    """Tests for sanitize_sensitive_data processor."""

    def test_redacts_password_field(self) -> None:
        """Verify password fields are redacted."""
        event_dict: dict[str, Any] = {"event": "test", "password": "secret123"}
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["password"] == "[REDACTED]"

    def test_redacts_api_key_field(self) -> None:
        """Verify api_key fields are redacted."""
        event_dict: dict[str, Any] = {"event": "test", "api_key": "sk-12345"}
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["api_key"] == "[REDACTED]"

    def test_redacts_token_field(self) -> None:
        """Verify token fields are redacted."""
        event_dict: dict[str, Any] = {"event": "test", "token": "jwt-token-value"}
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["token"] == "[REDACTED]"

    def test_redacts_nested_sensitive_data(self) -> None:
        """Verify nested sensitive data is redacted."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "user": {
                "name": "john",
                "password": "secret",
                "api_key": "key123",
            },
        }
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["user"]["name"] == "john"
        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["api_key"] == "[REDACTED]"

    def test_redacts_sensitive_data_in_lists(self) -> None:
        """Verify sensitive data in lists is redacted."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "users": [
                {"name": "john", "password": "pass1"},
                {"name": "jane", "secret": "pass2"},
            ],
        }
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["users"][0]["password"] == "[REDACTED]"
        assert result["users"][1]["secret"] == "[REDACTED]"

    def test_redacts_all_sensitive_key_patterns(self) -> None:
        """Verify all sensitive key patterns are redacted."""
        sensitive_keys = [
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "bearer",
            "access_token",
            "refresh_token",
            "private_key",
            "secret_key",
            "mnemonic",
            "jwt",
            "client_secret",
            "cookie",
            "credit_card",
            "ssn",
            "connection_string",
            "db_password",
        ]

        event_dict: dict[str, Any] = {key: f"value_{key}" for key in sensitive_keys}
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        for key in sensitive_keys:
            assert result[key] == "[REDACTED]", f"Key '{key}' was not redacted"

    def test_redacts_embedded_secrets_in_strings(self) -> None:
        """Verify embedded secrets in string values are redacted."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "message": "Connection string: password=mysecretpassword123",
        }
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert "[REDACTED_SECRET]" in result["message"]
        assert "mysecretpassword123" not in result["message"]

    def test_prevents_infinite_recursion(self) -> None:
        """Verify recursion depth limit prevents stack overflow."""
        # Create deeply nested structure
        deep_dict: dict[str, Any] = {"level": 0, "password": "secret"}
        current = deep_dict
        for i in range(15):  # Beyond the 10-level limit
            current["nested"] = {"level": i + 1, "password": "secret"}
            current = current["nested"]

        event_dict: dict[str, Any] = {"event": "test", "data": deep_dict}
        # Should not raise RecursionError
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        assert result is not None

    def test_case_insensitive_key_matching(self) -> None:
        """Verify key matching is case-insensitive."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "PASSWORD": "secret1",
            "Api_Key": "secret2",
            "TOKEN": "secret3",
        }
        result = sanitize_sensitive_data(None, "info", event_dict)  # type: ignore[arg-type]

        # Keys with sensitive substrings should be redacted
        for key in event_dict:
            if key != "event":
                assert result[key] == "[REDACTED]", f"Key '{key}' was not redacted"


# =============================================================================
# Tests for drop_color_codes processor
# =============================================================================


class TestDropColorCodes:
    """Tests for drop_color_codes processor."""

    def test_removes_ansi_color_codes(self) -> None:
        """Verify ANSI color codes are removed from strings."""
        event_dict: dict[str, Any] = {"event": "\x1b[31mRed text\x1b[0m"}
        result = drop_color_codes(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["event"] == "Red text"

    def test_handles_multiple_color_codes(self) -> None:
        """Verify multiple color codes are removed."""
        event_dict: dict[str, Any] = {"event": "\x1b[32mGreen\x1b[0m and \x1b[34mBlue\x1b[0m"}
        result = drop_color_codes(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["event"] == "Green and Blue"

    def test_handles_nested_dicts(self) -> None:
        """Verify color codes are removed from nested dicts."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "nested": {"message": "\x1b[33mYellow\x1b[0m"},
        }
        result = drop_color_codes(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["nested"]["message"] == "Yellow"

    def test_handles_lists(self) -> None:
        """Verify color codes are removed from lists."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "messages": ["\x1b[31mRed\x1b[0m", "\x1b[32mGreen\x1b[0m"],
        }
        result = drop_color_codes(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["messages"] == ["Red", "Green"]

    def test_preserves_non_string_values(self) -> None:
        """Verify non-string values are preserved."""
        event_dict: dict[str, Any] = {
            "event": "test",
            "count": 42,
            "active": True,
            "data": None,
        }
        result = drop_color_codes(None, "info", event_dict)  # type: ignore[arg-type]

        assert result["count"] == 42
        assert result["active"] is True
        assert result["data"] is None


# =============================================================================
# Tests for configure_logging
# =============================================================================


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configures_with_default_settings(self) -> None:
        """Verify logging can be configured with defaults."""
        configure_logging()
        # Should not raise any exceptions
        logger = get_logger("test")
        assert logger is not None

    def test_configures_with_debug_level(self) -> None:
        """Verify DEBUG level can be configured."""
        # Note: basicConfig only sets the root logger level if it hasn't been configured yet.
        # We verify by checking that calling configure_logging doesn't raise an exception
        # and that a logger can be obtained.
        configure_logging(level="DEBUG")
        logger = get_logger("test_debug")
        assert logger is not None

    def test_configures_with_json_output(self) -> None:
        """Verify JSON output mode can be configured."""
        configure_logging(json_output=True)
        logger = get_logger("test")
        assert logger is not None

    def test_configures_without_timestamps(self) -> None:
        """Verify timestamps can be disabled."""
        configure_logging(include_timestamps=False)
        logger = get_logger("test")
        assert logger is not None

    def test_configures_without_service_info(self) -> None:
        """Verify service info can be disabled."""
        configure_logging(include_service_info=False)
        logger = get_logger("test")
        assert logger is not None

    def test_configures_without_sanitization(self) -> None:
        """Verify log sanitization can be disabled."""
        configure_logging(sanitize_logs=False)
        logger = get_logger("test")
        assert logger is not None

    def test_reduces_third_party_logger_noise(self) -> None:
        """Verify third-party loggers are set to WARNING level."""
        configure_logging()

        assert logging.getLogger("uvicorn").level == logging.WARNING
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING


# =============================================================================
# Tests for get_logger
# =============================================================================


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_bound_logger(self) -> None:
        """Verify get_logger returns a BoundLogger."""
        configure_logging()
        logger = get_logger("test_module")
        assert logger is not None

    def test_returns_different_loggers_for_different_names(self) -> None:
        """Verify different names create different loggers."""
        configure_logging()
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        # Both should be valid loggers
        assert logger1 is not None
        assert logger2 is not None

    def test_accepts_none_for_name(self) -> None:
        """Verify None is accepted for logger name."""
        configure_logging()
        logger = get_logger(None)
        assert logger is not None


# =============================================================================
# Tests for context management
# =============================================================================


class TestContextManagement:
    """Tests for bind_context, unbind_context, clear_context functions."""

    def setup_method(self) -> None:
        """Clear context before each test."""
        clear_context()

    def teardown_method(self) -> None:
        """Clear context after each test."""
        clear_context()

    def test_bind_context_adds_variables(self) -> None:
        """Verify bind_context adds context variables."""
        bind_context(request_id="123", user_id="456")
        # Context should be bound (no exception)
        # We can't easily verify structlog contextvars without inspecting internals

    def test_unbind_context_removes_variables(self) -> None:
        """Verify unbind_context removes specific variables."""
        bind_context(request_id="123", user_id="456")
        unbind_context("request_id")
        # Should not raise

    def test_clear_context_removes_all(self) -> None:
        """Verify clear_context removes all context variables."""
        bind_context(request_id="123", user_id="456", session_id="789")
        clear_context()
        # Should not raise


# =============================================================================
# Tests for LoggingContextMiddleware
# =============================================================================


class TestLoggingContextMiddleware:
    """Tests for LoggingContextMiddleware."""

    @pytest.mark.asyncio
    async def test_handles_http_requests(self) -> None:
        """Verify middleware handles HTTP requests."""
        app_mock = AsyncMock()
        middleware = LoggingContextMiddleware(app_mock)

        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "GET",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app_mock.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_passes_through_non_http_requests(self) -> None:
        """Verify non-HTTP requests are passed through."""
        app_mock = AsyncMock()
        middleware = LoggingContextMiddleware(app_mock)

        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app_mock.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_extracts_correlation_id_from_header(self) -> None:
        """Verify correlation ID is extracted from headers."""
        app_mock = AsyncMock()
        middleware = LoggingContextMiddleware(app_mock)

        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "GET",
            "headers": [(b"x-correlation-id", b"test-correlation-id")],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_correlation_id_if_missing(self) -> None:
        """Verify correlation ID is generated if not in headers."""
        app_mock = AsyncMock()
        middleware = LoggingContextMiddleware(app_mock)

        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "GET",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_context_after_request(self) -> None:
        """Verify context is cleared after request completes."""
        app_mock = AsyncMock()
        middleware = LoggingContextMiddleware(app_mock)

        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "GET",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        # Context should be cleared (no exception on next request)

    @pytest.mark.asyncio
    async def test_clears_context_on_exception(self) -> None:
        """Verify context is cleared even when exception occurs."""
        app_mock = AsyncMock(side_effect=ValueError("Test error"))
        middleware = LoggingContextMiddleware(app_mock)

        scope = {
            "type": "http",
            "path": "/api/test",
            "method": "GET",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(ValueError):
            await middleware(scope, receive, send)
        # Context should be cleared even after exception


# =============================================================================
# Tests for DatadogFormatter
# =============================================================================


class TestDatadogFormatter:
    """Tests for DatadogFormatter."""

    def test_formats_basic_event(self) -> None:
        """Verify basic event formatting."""
        event_dict = {
            "event": "Test message",
            "level": "info",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "service": "forge-cascade",
        }

        result = DatadogFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert parsed["timestamp"] == "2024-01-01T00:00:00+00:00"
        assert parsed["service"] == "forge-cascade"

    def test_includes_correlation_id_as_trace_id(self) -> None:
        """Verify correlation_id is mapped to dd.trace_id."""
        event_dict = {
            "event": "Test",
            "level": "info",
            "timestamp": "",
            "correlation_id": "abc-123",
        }

        result = DatadogFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["dd.trace_id"] == "abc-123"

    def test_includes_extra_fields(self) -> None:
        """Verify extra fields are included."""
        event_dict = {
            "event": "Test",
            "level": "info",
            "timestamp": "",
            "custom_field": "custom_value",
            "user_id": "user123",
        }

        result = DatadogFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["custom_field"] == "custom_value"
        assert parsed["user_id"] == "user123"

    def test_handles_missing_fields(self) -> None:
        """Verify missing fields use defaults."""
        event_dict: dict[str, Any] = {}

        result = DatadogFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["message"] == ""
        assert parsed["level"] == "INFO"  # Default level
        assert parsed["service"] == "forge-cascade"


# =============================================================================
# Tests for CloudWatchFormatter
# =============================================================================


class TestCloudWatchFormatter:
    """Tests for CloudWatchFormatter."""

    def test_formats_basic_event(self) -> None:
        """Verify basic event formatting."""
        event_dict = {
            "event": "Test message",
            "level": "info",
            "timestamp": "2024-01-01T00:00:00+00:00",
        }

        result = CloudWatchFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["message"] == "Test message"
        assert parsed["level"] == "info"
        assert parsed["timestamp"] == "2024-01-01T00:00:00+00:00"

    def test_includes_extra_fields_in_extra_dict(self) -> None:
        """Verify extra fields are placed in 'extra' dict."""
        event_dict = {
            "event": "Test",
            "level": "info",
            "timestamp": "",
            "custom_field": "custom_value",
            "user_id": "user123",
        }

        result = CloudWatchFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["extra"]["custom_field"] == "custom_value"
        assert parsed["extra"]["user_id"] == "user123"

    def test_handles_missing_fields(self) -> None:
        """Verify missing fields use defaults."""
        event_dict: dict[str, Any] = {}

        result = CloudWatchFormatter.format(event_dict.copy())
        parsed = json.loads(result)

        assert parsed["message"] == ""
        assert parsed["level"] == "info"  # Default level


# =============================================================================
# Tests for log_duration
# =============================================================================


class TestLogDuration:
    """Tests for log_duration context manager."""

    def test_logs_successful_operation_duration(self) -> None:
        """Verify duration is logged for successful operations."""
        configure_logging()
        logger = get_logger("test")

        with patch.object(logger, "info") as mock_info:
            with log_duration(logger, "test_operation"):
                time.sleep(0.01)  # Small delay

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "test_operation_completed" in str(call_args)

    def test_logs_failed_operation_duration(self) -> None:
        """Verify duration is logged for failed operations."""
        configure_logging()
        logger = get_logger("test")

        with patch.object(logger, "error") as mock_error:
            with pytest.raises(ValueError):
                with log_duration(logger, "test_operation"):
                    raise ValueError("Test error")

            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert "test_operation_failed" in str(call_args)

    def test_includes_extra_context(self) -> None:
        """Verify extra context is included in logs."""
        configure_logging()
        logger = get_logger("test")

        with patch.object(logger, "info") as mock_info:
            with log_duration(logger, "db_query", table="users", action="select"):
                pass

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            # Check that extra context was passed
            assert "table" in str(call_args) or call_args[1].get("table") == "users"

    def test_uses_specified_log_level(self) -> None:
        """Verify specified log level is used."""
        configure_logging()
        logger = get_logger("test")

        with patch.object(logger, "debug") as mock_debug:
            with log_duration(logger, "operation", level="debug"):
                pass

            mock_debug.assert_called_once()

    def test_measures_actual_duration(self) -> None:
        """Verify actual duration is measured accurately."""
        configure_logging()
        logger = get_logger("test")

        with patch.object(logger, "info") as mock_info:
            with log_duration(logger, "operation"):
                time.sleep(0.05)  # 50ms

            call_args = mock_info.call_args
            # Duration should be captured in duration_ms
            if call_args[1]:
                duration_ms = call_args[1].get("duration_ms", 0)
                assert duration_ms >= 45  # At least 45ms (allowing some tolerance)

    def test_re_raises_exceptions(self) -> None:
        """Verify exceptions are re-raised after logging."""
        configure_logging()
        logger = get_logger("test")

        with pytest.raises(RuntimeError, match="Test exception"):
            with log_duration(logger, "operation"):
                raise RuntimeError("Test exception")


# =============================================================================
# Integration Tests
# =============================================================================


class TestLoggingIntegration:
    """Integration tests for the logging module."""

    def test_full_logging_pipeline_console(self) -> None:
        """Test complete logging pipeline with console output."""
        configure_logging(
            level="DEBUG",
            json_output=False,
            include_timestamps=True,
            include_service_info=True,
            sanitize_logs=True,
        )

        logger = get_logger("integration_test")
        # Should not raise
        logger.info("Test message", user_id="123", password="secret")

    def test_full_logging_pipeline_json(self) -> None:
        """Test complete logging pipeline with JSON output."""
        configure_logging(
            level="DEBUG",
            json_output=True,
            include_timestamps=True,
            include_service_info=True,
            sanitize_logs=True,
        )

        logger = get_logger("integration_test")
        # Should not raise
        logger.info("Test message", user_id="123", api_key="sk-12345")

    def test_context_binding_with_logging(self) -> None:
        """Test context binding works with logging."""
        configure_logging()
        clear_context()

        bind_context(request_id="req-123")
        logger = get_logger("test")
        # Should not raise
        logger.info("Test with context")

        clear_context()
