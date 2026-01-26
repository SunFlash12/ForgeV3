"""
Forge Cascade V2 - Structured Logging

Production-grade logging configuration using structlog.

Features:
- JSON output for production
- Pretty console output for development
- Request correlation IDs
- Automatic context enrichment
- Log level filtering
- Performance metrics
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, MutableMapping

import structlog
from structlog.typing import EventDict, WrappedLogger

# =============================================================================
# Custom Processors
# =============================================================================

def add_timestamp(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add ISO8601 timestamp to log entry."""
    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def add_service_info(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add service identification info."""
    event_dict["service"] = "forge-cascade"
    event_dict["version"] = "2.0.0"
    return event_dict


def add_log_level(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add numeric log level for filtering."""
    level_map = {
        "debug": 10,
        "info": 20,
        "warning": 30,
        "error": 40,
        "critical": 50,
    }
    event_dict["level_number"] = level_map.get(method_name, 20)
    return event_dict


def sanitize_sensitive_data(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Remove or mask sensitive data from logs."""
    # SECURITY FIX: Expanded sensitive key patterns for better coverage
    sensitive_keys = {
        # Authentication credentials
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "bearer",
        "access_token",
        "refresh_token",
        "id_token",
        "session_id",
        "session_key",
        # Cryptographic keys
        "private_key",
        "privatekey",
        "secret_key",
        "secretkey",
        "signing_key",
        "encryption_key",
        # Personal data (PII)
        "cookie",
        "credit_card",
        "creditcard",
        "ssn",
        "social_security",
        # Database/service credentials
        "connection_string",
        "connectionstring",
        "db_password",
        "redis_password",
        "neo4j_password",
    }

    def _sanitize(obj: Any, depth: int = 0) -> Any:
        if depth > 10:  # Prevent infinite recursion
            return obj

        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if any(s in k.lower() for s in sensitive_keys) else _sanitize(v, depth + 1)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [_sanitize(item, depth + 1) for item in obj]
        return obj

    result: EventDict = _sanitize(event_dict)
    return result


def drop_color_codes(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Remove ANSI color codes for clean log output."""
    import re

    def _clean(obj: Any) -> Any:
        if isinstance(obj, str):
            return re.sub(r'\x1b\[[0-9;]*m', '', obj)
        elif isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_clean(item) for item in obj]
        return obj

    result: EventDict = _clean(event_dict)
    return result


# =============================================================================
# Logging Configuration
# =============================================================================

def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    include_timestamps: bool = True,
    include_service_info: bool = True,
    sanitize_logs: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Use JSON format (for production)
        include_timestamps: Add timestamps to logs
        include_service_info: Add service name/version
        sanitize_logs: Remove sensitive data
    """
    # Build processor chain
    processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Add custom processors
    if include_timestamps:
        processors.insert(0, add_timestamp)

    if include_service_info:
        processors.insert(0, add_service_info)

    processors.append(add_log_level)

    if sanitize_logs:
        processors.append(sanitize_sensitive_data)

    # Add format-specific processors
    if json_output:
        processors.append(drop_color_codes)
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Reduce noise from third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to module name)

    Returns:
        Configured structlog logger
    """
    bound_logger: structlog.BoundLogger = structlog.get_logger(name)
    return bound_logger


# =============================================================================
# Context Management
# =============================================================================

def bind_context(**kwargs: Any) -> None:
    """Bind context variables that will appear in all subsequent logs."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove context variables."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


# =============================================================================
# Request Context Middleware
# =============================================================================

class LoggingContextMiddleware:
    """
    FastAPI middleware to add request context to logs.

    Automatically binds:
    - correlation_id
    - request_id
    - user_id (if authenticated)
    - path
    - method
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from uuid import uuid4

        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode() or str(uuid4())

        # Bind context
        bind_context(
            correlation_id=correlation_id,
            path=scope.get("path", ""),
            method=scope.get("method", ""),
        )

        try:
            await self.app(scope, receive, send)
        finally:
            clear_context()


# =============================================================================
# Log Formatters for External Systems
# =============================================================================

class DatadogFormatter:
    """Format logs for Datadog ingestion."""

    @staticmethod
    def format(event_dict: EventDict) -> str:
        import json

        # Datadog expects specific field names
        dd_dict = {
            "message": event_dict.pop("event", ""),
            "level": event_dict.pop("level", "info").upper(),
            "timestamp": event_dict.pop("timestamp", ""),
            "service": event_dict.pop("service", "forge-cascade"),
            "dd.trace_id": event_dict.pop("correlation_id", ""),
        }

        # Add remaining fields as attributes
        dd_dict.update(event_dict)

        return json.dumps(dd_dict)


class CloudWatchFormatter:
    """Format logs for AWS CloudWatch."""

    @staticmethod
    def format(event_dict: EventDict) -> str:
        import json

        cw_dict = {
            "message": event_dict.pop("event", ""),
            "level": event_dict.pop("level", "info"),
            "timestamp": event_dict.pop("timestamp", ""),
            "extra": event_dict,
        }

        return json.dumps(cw_dict)


# =============================================================================
# Performance Logging
# =============================================================================

import time
from contextlib import contextmanager


@contextmanager
def log_duration(
    logger: structlog.BoundLogger,
    operation: str,
    level: str = "info",
    **extra_context: Any,
) -> Iterator[None]:
    """
    Context manager to log operation duration.

    Usage:
        with log_duration(logger, "database_query", table="users"):
            result = await db.query(...)
    """
    start_time = time.monotonic()
    log_method = getattr(logger, level)

    try:
        yield
        duration_ms = (time.monotonic() - start_time) * 1000
        log_method(
            f"{operation}_completed",
            duration_ms=round(duration_ms, 2),
            **extra_context,
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            f"{operation}_failed",
            duration_ms=round(duration_ms, 2),
            error=str(e),
            **extra_context,
        )
        raise


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_context",
    "unbind_context",
    "clear_context",
    "LoggingContextMiddleware",
    "log_duration",
    "DatadogFormatter",
    "CloudWatchFormatter",
]
