"""
Forge Cascade V2 - API Middleware
Custom middleware for cross-cutting concerns.

Provides:
- Correlation ID tracking for request tracing
- Request/response logging
- Authentication context
- Rate limiting
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = structlog.get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Add correlation ID to all requests for distributed tracing.
    
    The correlation ID is:
    1. Extracted from X-Correlation-ID header if present
    2. Generated as UUID if not present
    3. Added to response headers
    4. Stored in request.state for access in handlers
    """
    
    HEADER_NAME = "X-Correlation-ID"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(self.HEADER_NAME)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Store in request state
        request.state.correlation_id = correlation_id
        
        # Bind to structlog context
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers[self.HEADER_NAME] = correlation_id
        
        # Clear structlog context
        structlog.contextvars.unbind_contextvars("correlation_id")
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests and responses with timing information.
    
    Logs:
    - Request method, path, and client IP
    - Response status code
    - Request duration in milliseconds
    """
    
    # Paths to skip logging (health checks, etc.)
    SKIP_PATHS = {"/health", "/ready", "/favicon.ico"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip certain paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Record start time
        start_time = time.perf_counter()
        
        # Get client info
        client_ip = self._get_client_ip(request)
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=client_ip,
            correlation_id=correlation_id,
        )
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Log exception
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log response
        log_level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
        getattr(logger, log_level)(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First IP in the list is the client
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client
        if request.client:
            return request.client.host
        
        return "unknown"


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Extract authentication context from requests.
    
    This middleware:
    1. Extracts JWT token from Authorization header
    2. Decodes and validates token (without full user lookup)
    3. Stores user_id in request.state for downstream use
    
    Full user lookup is done lazily in dependencies.
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Extract token from header
        auth_header = request.headers.get("Authorization")
        request.state.user_id = None
        request.state.token_payload = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            try:
                from forge.config import get_settings
                from forge.security.tokens import verify_token
                
                settings = get_settings()
                payload = verify_token(token, settings.JWT_SECRET_KEY)
                
                request.state.user_id = payload.sub
                request.state.token_payload = payload
                
            except Exception:
                # Invalid token - let the route handlers deal with it
                pass
        
        return await call_next(request)


@dataclass
class RateLimitEntry:
    """Tracks rate limit for a key."""
    count: int = 0
    window_start: float = field(default_factory=time.time)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting.
    
    Limits requests per IP address with configurable:
    - Requests per minute
    - Requests per hour
    - Burst allowance
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_allowance: int = 10,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_allowance = burst_allowance
        
        # Rate limit storage (in production, use Redis)
        self._minute_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._hour_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/ready"}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Get rate limit key (IP or user ID)
        key = self._get_rate_limit_key(request)
        
        # Check rate limits
        now = time.time()
        
        # Minute limit
        minute_entry = self._minute_buckets[key]
        if now - minute_entry.window_start > 60:
            minute_entry.count = 0
            minute_entry.window_start = now
        
        if minute_entry.count >= self.requests_per_minute + self.burst_allowance:
            return self._rate_limit_response(
                "minute",
                60 - (now - minute_entry.window_start),
            )
        
        # Hour limit
        hour_entry = self._hour_buckets[key]
        if now - hour_entry.window_start > 3600:
            hour_entry.count = 0
            hour_entry.window_start = now
        
        if hour_entry.count >= self.requests_per_hour:
            return self._rate_limit_response(
                "hour",
                3600 - (now - hour_entry.window_start),
            )
        
        # Increment counters
        minute_entry.count += 1
        hour_entry.count += 1
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - minute_entry.count)
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(minute_entry.window_start + 60)
        )
        
        return response
    
    def _get_rate_limit_key(self, request: Request) -> str:
        """Get key for rate limiting (user ID or IP)."""
        # Prefer user ID if authenticated
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"
        
        if request.client:
            return f"ip:{request.client.host}"
        
        return "ip:unknown"
    
    def _rate_limit_response(self, window: str, retry_after: float) -> Response:
        """Create rate limit exceeded response."""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "window": window,
                "retry_after_seconds": int(retry_after),
            },
            headers={
                "Retry-After": str(int(retry_after)),
            },
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS (only in production)
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Handle response compression.
    
    Note: For production, use GZipMiddleware from starlette or nginx.
    This is a placeholder showing where compression would go.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if client accepts gzip
        accept_encoding = request.headers.get("Accept-Encoding", "")
        
        response = await call_next(request)
        
        # In production, actual compression would happen here
        # For now, just pass through
        
        return response


__all__ = [
    "CorrelationIdMiddleware",
    "RequestLoggingMiddleware",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "CompressionMiddleware",
]
