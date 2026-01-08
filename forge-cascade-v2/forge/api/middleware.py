"""
Forge Cascade V2 - API Middleware
Custom middleware for cross-cutting concerns.

Provides:
- Correlation ID tracking for request tracing
- Request/response logging
- Authentication context
- Rate limiting (Redis-backed with in-memory fallback)
- Security headers (HSTS, CSP, etc.)
- Request size limiting
"""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = structlog.get_logger(__name__)

# Sensitive query parameter keys that should be redacted in logs
SENSITIVE_PARAM_KEYS = frozenset({
    'token', 'access_token', 'refresh_token', 'api_key', 'apikey',
    'password', 'secret', 'key', 'auth', 'authorization', 'credential',
    'session', 'jwt', 'bearer', 'private', 'ssn', 'credit_card',
})


def sanitize_query_params(query_params) -> str | None:
    """
    Sanitize query parameters for safe logging.

    Redacts sensitive values while preserving param names for debugging.
    """
    if not query_params:
        return None

    sanitized = {}
    for key, value in query_params.items():
        key_lower = key.lower()
        # Check if key contains any sensitive keyword
        if any(sensitive in key_lower for sensitive in SENSITIVE_PARAM_KEYS):
            sanitized[key] = "[REDACTED]"
        else:
            # Truncate long values to prevent log bloat
            str_value = str(value)
            if len(str_value) > 100:
                sanitized[key] = str_value[:100] + "...[truncated]"
            else:
                sanitized[key] = str_value

    return str(sanitized) if sanitized else None


# Optional Redis import
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


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
        
        # Log request with sanitized query params
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=sanitize_query_params(request.query_params),
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
    4. Logs authentication failures for security monitoring

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
                from forge.security.tokens import verify_token, TokenBlacklist

                settings = get_settings()
                payload = verify_token(token, settings.jwt_secret_key)

                # Check if token is blacklisted (revoked) - async for Redis support
                jti = payload.jti if hasattr(payload, 'jti') else None
                if await TokenBlacklist.is_blacklisted_async(jti):
                    logger.warning(
                        "blacklisted_token_used",
                        path=request.url.path,
                        client_ip=self._get_client_ip(request),
                    )
                    # Token is revoked, don't authenticate
                else:
                    request.state.user_id = payload.sub
                    request.state.token_payload = payload

            except Exception as e:
                # Log authentication failures for security monitoring
                logger.warning(
                    "auth_token_validation_failed",
                    path=request.url.path,
                    client_ip=self._get_client_ip(request),
                    error_type=type(e).__name__,
                    error=str(e)[:100],  # Truncate to avoid log bloat
                )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"


@dataclass
class RateLimitEntry:
    """Tracks rate limit for a key."""
    count: int = 0
    window_start: float = field(default_factory=time.time)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting with Redis support.

    Features:
    - Redis-backed for distributed deployments (falls back to in-memory)
    - Stricter limits on authentication endpoints
    - Configurable per-minute and per-hour limits
    - Burst allowance for legitimate traffic spikes
    """

    # Stricter rate limits for sensitive endpoints
    AUTH_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/password",
    }

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/ready"}

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        requests_per_hour: int = 3000,
        burst_allowance: int = 30,
        auth_requests_per_minute: int = 30,  # More lenient for development
        auth_requests_per_hour: int = 200,
        redis_url: Optional[str] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_allowance = burst_allowance
        self.auth_requests_per_minute = auth_requests_per_minute
        self.auth_requests_per_hour = auth_requests_per_hour

        # Redis client for distributed rate limiting
        self._redis: Optional[redis.Redis] = None
        self._redis_url = redis_url
        self._use_redis = False

        # Fallback in-memory storage
        self._minute_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._hour_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

        # Initialize Redis if available
        if redis_url and REDIS_AVAILABLE:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._use_redis = True
                logger.info("rate_limit_redis_enabled", redis_url=redis_url[:20] + "...")
            except Exception as e:
                logger.warning("rate_limit_redis_failed", error=str(e))

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Get rate limit key (IP or user ID)
        key = self._get_rate_limit_key(request)
        is_auth_path = request.url.path in self.AUTH_PATHS

        # Use stricter limits for auth endpoints
        minute_limit = self.auth_requests_per_minute if is_auth_path else self.requests_per_minute
        hour_limit = self.auth_requests_per_hour if is_auth_path else self.requests_per_hour
        burst = 0 if is_auth_path else self.burst_allowance  # No burst for auth

        # Check rate limits
        if self._use_redis and self._redis:
            exceeded, retry_after, remaining = await self._check_redis_rate_limit(
                key, minute_limit, hour_limit, burst, is_auth_path
            )
        else:
            exceeded, retry_after, remaining = self._check_memory_rate_limit(
                key, minute_limit, hour_limit, burst
            )

        if exceeded:
            # Log rate limit hit for auth endpoints (potential brute force)
            if is_auth_path:
                logger.warning(
                    "auth_rate_limit_exceeded",
                    path=request.url.path,
                    client_ip=self._get_client_ip(request),
                    key=key,
                )
            return self._rate_limit_response(retry_after)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(minute_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    async def _check_redis_rate_limit(
        self,
        key: str,
        minute_limit: int,
        hour_limit: int,
        burst: int,
        is_auth: bool,
    ) -> tuple[bool, float, int]:
        """Check rate limit using Redis."""
        try:
            now = time.time()
            minute_key = f"ratelimit:{key}:minute:{int(now // 60)}"
            hour_key = f"ratelimit:{key}:hour:{int(now // 3600)}"

            pipe = self._redis.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)  # 2 min TTL
            pipe.incr(hour_key)
            pipe.expire(hour_key, 7200)  # 2 hour TTL
            results = await pipe.execute()

            minute_count = results[0]
            hour_count = results[2]

            if minute_count > minute_limit + burst:
                # Ensure retry_after is always a positive integer (min 1 second)
                return True, max(1, int(60 - (now % 60))), 0
            if hour_count > hour_limit:
                return True, max(1, int(3600 - (now % 3600))), 0

            return False, 0, max(0, minute_limit - minute_count)

        except Exception as e:
            logger.warning("redis_rate_limit_error", error=str(e))
            # Fallback to memory
            return self._check_memory_rate_limit(key, minute_limit, hour_limit, burst)

    def _check_memory_rate_limit(
        self,
        key: str,
        minute_limit: int,
        hour_limit: int,
        burst: int,
    ) -> tuple[bool, float, int]:
        """Check rate limit using in-memory storage."""
        now = time.time()

        # Minute limit
        minute_entry = self._minute_buckets[key]
        if now - minute_entry.window_start > 60:
            minute_entry.count = 0
            minute_entry.window_start = now

        if minute_entry.count >= minute_limit + burst:
            # Ensure retry_after is always a positive integer (min 1 second)
            return True, max(1, int(60 - (now - minute_entry.window_start))), 0

        # Hour limit
        hour_entry = self._hour_buckets[key]
        if now - hour_entry.window_start > 3600:
            hour_entry.count = 0
            hour_entry.window_start = now

        if hour_entry.count >= hour_limit:
            return True, max(1, int(3600 - (now - hour_entry.window_start))), 0

        # Increment counters
        minute_entry.count += 1
        hour_entry.count += 1

        return False, 0, max(0, minute_limit - minute_entry.count)

    def _get_rate_limit_key(self, request: Request) -> str:
        """Get key for rate limiting (user ID or IP)."""
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"

        return f"ip:{self._get_client_ip(request)}"

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _rate_limit_response(self, retry_after: float) -> Response:
        """Create rate limit exceeded response."""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "retry_after_seconds": int(retry_after),
            },
            headers={
                "Retry-After": str(int(retry_after)),
            },
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Includes:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Content-Security-Policy
    - Strict-Transport-Security (HSTS) - configurable
    """

    def __init__(self, app, enable_hsts: bool = False):
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy - strict for API responses
        # Note: Frontend should set its own CSP via meta tag or server config
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "  # Deny all by default for API
            "script-src 'none'; "   # No scripts in API responses
            "style-src 'none'; "    # No styles in API responses
            "img-src 'none'; "      # No images in API responses
            "font-src 'none'; "     # No fonts in API responses
            "connect-src 'none'; "  # No XHR/fetch from API responses
            "frame-ancestors 'none'; "
            "base-uri 'none'; "
            "form-action 'none'; "
            "upgrade-insecure-requests"
        )

        # HSTS (only in production)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Permissions Policy (formerly Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection using Double Submit Cookie pattern.

    For state-changing requests (POST, PUT, PATCH, DELETE):
    - Validates that X-CSRF-Token header matches csrf_token cookie
    - Exempts certain paths (login, public endpoints)

    This works because:
    1. Same-origin JavaScript can read the csrf_token cookie and set the header
    2. Cross-origin JavaScript cannot read cookies due to SameSite policy
    3. Cross-origin forms cannot set custom headers
    """

    # Methods that require CSRF validation
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths exempt from CSRF (login, public endpoints, API token auth)
    EXEMPT_PATHS = {
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
        "/health",
        "/ready",
        "/metrics",
    }

    # Paths that start with these prefixes are exempt
    EXEMPT_PREFIXES = [
        "/docs",
        "/openapi",
        "/redoc",
    ]

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Only check protected methods
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)

        # Check exempt paths
        path = request.url.path
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # If using Authorization header (API clients), skip CSRF check
        # API clients use tokens, not cookies, so CSRF doesn't apply
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return await call_next(request)

        # For cookie-based auth, validate CSRF token
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        # If no cookie auth is being used, skip CSRF check
        access_token_cookie = request.cookies.get("access_token")
        if not access_token_cookie:
            return await call_next(request)

        # Cookie auth is being used - require valid CSRF token
        if not csrf_cookie or not csrf_header:
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token missing"},
            )

        # Timing-safe comparison
        if not hmac.compare_digest(csrf_cookie, csrf_header):
            logger.warning(
                "csrf_validation_failed",
                path=path,
                method=request.method,
            )
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token invalid"},
            )

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit request body size to prevent DoS attacks.
    """

    def __init__(self, app, max_content_length: int = 10 * 1024 * 1024):
        """
        Args:
            max_content_length: Maximum request body size in bytes (default 10MB)
        """
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self.max_content_length:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "Request entity too large",
                            "max_size_bytes": self.max_content_length,
                        },
                    )
            except ValueError:
                pass  # Invalid Content-Length header

        return await call_next(request)


@dataclass
class IdempotencyEntry:
    """Cached response for idempotency."""
    status_code: int
    body: bytes
    headers: dict
    created_at: float


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Idempotency key support for safe request retries.

    When a client provides X-Idempotency-Key header:
    1. First request: Execute and cache response
    2. Duplicate requests: Return cached response

    This prevents duplicate side effects from retried requests.
    """

    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
    IDEMPOTENT_PATHS_PREFIX = {"/api/v1/capsules", "/api/v1/governance/proposals"}

    def __init__(self, app, ttl_seconds: int = 86400):  # 24 hour default
        super().__init__(app)
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, IdempotencyEntry] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only handle idempotent methods
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        # Check for idempotency key
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # Validate key format - must be alphanumeric/dashes, 8-64 chars
        if len(idempotency_key) < 8:
            return JSONResponse(
                status_code=400,
                content={"error": "Idempotency key too short (min 8 chars)"},
            )
        if len(idempotency_key) > 64:
            return JSONResponse(
                status_code=400,
                content={"error": "Idempotency key too long (max 64 chars)"},
            )
        # Only allow alphanumeric, dashes, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', idempotency_key):
            return JSONResponse(
                status_code=400,
                content={"error": "Idempotency key must be alphanumeric (with dashes/underscores only)"},
            )

        # Build cache key including user if authenticated
        user_id = getattr(request.state, 'user_id', 'anonymous')
        cache_key = f"{user_id}:{request.url.path}:{idempotency_key}"

        # Check cache
        with self._lock:
            self._cleanup_expired()
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                logger.info(
                    "idempotency_cache_hit",
                    key=idempotency_key[:8] + "...",
                    path=request.url.path,
                )
                return Response(
                    content=entry.body,
                    status_code=entry.status_code,
                    headers={**entry.headers, "X-Idempotency-Replayed": "true"},
                )

        # Execute request
        response = await call_next(request)

        # Cache successful responses (2xx, 4xx client errors)
        if 200 <= response.status_code < 500:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Store in cache
            with self._lock:
                self._cache[cache_key] = IdempotencyEntry(
                    status_code=response.status_code,
                    body=body,
                    headers=dict(response.headers),
                    created_at=time.time(),
                )

            # Return new response with body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.time()
        if now - self._last_cleanup < 300:  # Every 5 minutes
            return

        self._last_cleanup = now
        expired = [
            key for key, entry in self._cache.items()
            if now - entry.created_at > self.ttl_seconds
        ]
        for key in expired:
            del self._cache[key]


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
    "RequestSizeLimitMiddleware",
    "IdempotencyMiddleware",
    "CompressionMiddleware",
]
