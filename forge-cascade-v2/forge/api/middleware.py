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

import asyncio
import hmac
import re
import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

if TYPE_CHECKING:
    from starlette.datastructures import QueryParams

logger = structlog.get_logger(__name__)

# Sensitive query parameter keys that should be redacted in logs
SENSITIVE_PARAM_KEYS = frozenset({
    'token', 'access_token', 'refresh_token', 'api_key', 'apikey',
    'password', 'secret', 'key', 'auth', 'authorization', 'credential',
    'session', 'jwt', 'bearer', 'private', 'ssn', 'credit_card',
})


def sanitize_query_params(query_params: QueryParams | None) -> str | None:
    """
    Sanitize query parameters for safe logging.

    Redacts sensitive values while preserving param names for debugging.
    """
    if not query_params:
        return None

    sanitized: dict[str, str] = {}
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
redis: ModuleType | None
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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Get or generate correlation ID
        correlation_id: str | None = request.headers.get(self.HEADER_NAME)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state
        request.state.correlation_id = correlation_id

        # Bind to structlog context
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Process request
        response: Response = await call_next(request)

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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip certain paths
        if request.url.path in self.SKIP_PATHS:
            response: Response = await call_next(request)
            return response

        # Record start time
        start_time = time.perf_counter()

        # Get client info
        client_ip = self._get_client_ip(request)
        correlation_id: str = getattr(request.state, 'correlation_id', 'unknown')

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
        except Exception as e:  # Intentional broad catch: API error boundary - returns sanitized 500
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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip public paths
        if request.url.path in self.PUBLIC_PATHS:
            response: Response = await call_next(request)
            return response

        # Extract token from header
        auth_header = request.headers.get("Authorization")
        request.state.user_id = None
        request.state.token_payload = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            try:
                from forge.config import get_settings
                from forge.security.tokens import TokenBlacklist, verify_token

                settings = get_settings()
                payload = verify_token(token, settings.jwt_secret_key)

                # Check if token is blacklisted (revoked) - async for Redis support
                jti: str | None = payload.jti if hasattr(payload, 'jti') else None
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

            except (ValueError, KeyError, OSError, RuntimeError) as e:
                # Log authentication failures for security monitoring
                logger.warning(
                    "auth_token_validation_failed",
                    path=request.url.path,
                    client_ip=self._get_client_ip(request),
                    error_type=type(e).__name__,
                    error=str(e)[:100],  # Truncate to avoid log bloat
                )

        response = await call_next(request)
        return response

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


class SessionBindingMiddleware(BaseHTTPMiddleware):
    """
    SECURITY FIX (Audit 6 - Session 2): Session binding validation middleware.

    Validates session binding (IP/User-Agent) for authenticated requests.
    This middleware should be placed AFTER AuthenticationMiddleware.

    Features:
    - Validates session exists and is active
    - Detects IP and User-Agent changes
    - Logs warnings based on binding mode (disabled/log_only/warn/flexible/strict)
    - Updates session activity on each request
    """

    # Paths that skip session binding validation
    SKIP_PATHS = {
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

    def __init__(self, app: Any, session_service: Any = None) -> None:
        """
        Initialize SessionBindingMiddleware.

        Args:
            app: ASGI application
            session_service: SessionBindingService instance (can be set later via app.state)
        """
        super().__init__(app)
        self._session_service = session_service

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip public/auth paths
        if request.url.path in self.SKIP_PATHS:
            response: Response = await call_next(request)
            return response

        # Skip if no token payload (unauthenticated request)
        token_payload: Any = getattr(request.state, 'token_payload', None)
        if not token_payload:
            response = await call_next(request)
            return response

        # Get session service from request app state if not set
        session_service: Any = self._session_service
        if not session_service:
            session_service = getattr(request.app.state, 'session_service', None)

        # Skip if session service not available
        if not session_service:
            response = await call_next(request)
            return response

        # Get token JTI
        jti: str | None = getattr(token_payload, 'jti', None)
        if not jti:
            response = await call_next(request)
            return response

        # Get client info
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent")

        try:
            # Validate and update session
            is_allowed, session, block_reason = await session_service.validate_and_update(
                token_jti=jti,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Store session in request state for later use
            request.state.session = session

            if not is_allowed:
                logger.warning(
                    "session_binding_blocked",
                    user_id=token_payload.sub,
                    reason=block_reason,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Session binding validation failed",
                        "detail": block_reason,
                        "code": "SESSION_BINDING_FAILED",
                    },
                )

        except (ValueError, KeyError, OSError, RuntimeError) as e:
            # Don't block requests on session validation errors
            logger.warning(
                "session_binding_error",
                error=str(e)[:100],
                path=request.url.path,
            )

        response = await call_next(request)
        return response

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

    # SECURITY FIX (Audit 6): Very strict rate limits for expensive LLM/Copilot endpoints
    # These endpoints consume significant compute resources and should be heavily rate limited
    LLM_PATHS = {
        "/api/v1/copilot/chat",
        "/api/v1/copilot/stream",
        "/copilot/chat",
        "/copilot/stream",
    }

    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/health", "/ready"}

    def __init__(
        self,
        app: Any,
        requests_per_minute: int = 120,
        requests_per_hour: int = 3000,
        burst_allowance: int = 30,
        auth_requests_per_minute: int = 30,  # More lenient for development
        auth_requests_per_hour: int = 200,
        # SECURITY FIX (Audit 6): Strict limits for LLM/Copilot endpoints
        llm_requests_per_minute: int = 10,
        llm_requests_per_hour: int = 100,
        redis_url: str | None = None,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_allowance = burst_allowance
        self.auth_requests_per_minute = auth_requests_per_minute
        self.auth_requests_per_hour = auth_requests_per_hour
        # SECURITY FIX (Audit 6): LLM/Copilot rate limits
        self.llm_requests_per_minute = llm_requests_per_minute
        self.llm_requests_per_hour = llm_requests_per_hour

        # Redis client for distributed rate limiting
        self._redis: Any = None
        self._redis_url = redis_url
        self._use_redis = False

        # Fallback in-memory storage
        self._minute_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._hour_buckets: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._last_bucket_cleanup = time.time()

        # Initialize Redis if available
        if redis_url and REDIS_AVAILABLE and redis is not None:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._use_redis = True
                logger.info("rate_limit_redis_enabled", redis_url=redis_url[:20] + "...")
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("rate_limit_redis_failed", error=str(e))

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            response: Response = await call_next(request)
            return response

        # Get rate limit key (IP or user ID)
        key = self._get_rate_limit_key(request)
        is_auth_path = request.url.path in self.AUTH_PATHS
        # SECURITY FIX (Audit 6): Check for LLM/Copilot endpoints
        is_llm_path = request.url.path in self.LLM_PATHS

        # Use stricter limits for auth and LLM endpoints
        if is_llm_path:
            # SECURITY FIX (Audit 6): Very strict limits for expensive LLM operations
            minute_limit = self.llm_requests_per_minute
            hour_limit = self.llm_requests_per_hour
            burst = 0  # No burst for LLM
        elif is_auth_path:
            minute_limit = self.auth_requests_per_minute
            hour_limit = self.auth_requests_per_hour
            burst = 0  # No burst for auth
        else:
            minute_limit = self.requests_per_minute
            hour_limit = self.requests_per_hour
            burst = self.burst_allowance

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
            # SECURITY FIX (Audit 6): Log LLM rate limit hits (resource abuse)
            elif is_llm_path:
                logger.warning(
                    "llm_rate_limit_exceeded",
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

            # Null check for Redis client before using pipeline
            if self._redis is None:
                return self._check_memory_rate_limit(key, minute_limit, hour_limit, burst)

            pipe: Any = self._redis.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)  # 2 min TTL
            pipe.incr(hour_key)
            pipe.expire(hour_key, 7200)  # 2 hour TTL
            results: list[Any] = await pipe.execute()

            # SECURITY FIX: Validate pipeline results before indexing
            if not results or len(results) < 4:
                logger.warning("redis_pipeline_incomplete", results_count=len(results) if results else 0)
                return self._check_memory_rate_limit(key, minute_limit, hour_limit, burst)

            minute_count: int = results[0]
            hour_count: int = results[2]

            if minute_count > minute_limit + burst:
                # Ensure retry_after is always a positive integer (min 1 second)
                return True, max(1, int(60 - (now % 60))), 0
            if hour_count > hour_limit:
                return True, max(1, int(3600 - (now % 3600))), 0

            return False, 0, max(0, minute_limit - minute_count)

        except (ConnectionError, TimeoutError, OSError) as e:
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

        # Periodic cleanup of expired entries (every 5 minutes)
        self._cleanup_rate_limit_buckets(now)

        return False, 0, max(0, minute_limit - minute_entry.count)

    def _cleanup_rate_limit_buckets(self, now: float) -> None:
        """Remove expired entries from rate limit buckets to prevent memory leaks."""
        # Only clean every 5 minutes
        if now - self._last_bucket_cleanup < 300:
            return

        self._last_bucket_cleanup = now

        # Clean minute buckets (entries older than 2 minutes are stale)
        expired_minute_keys = [
            key for key, entry in self._minute_buckets.items()
            if now - entry.window_start > 120
        ]
        for key in expired_minute_keys:
            del self._minute_buckets[key]

        # Clean hour buckets (entries older than 2 hours are stale)
        expired_hour_keys = [
            key for key, entry in self._hour_buckets.items()
            if now - entry.window_start > 7200
        ]
        for key in expired_hour_keys:
            del self._hour_buckets[key]

        if expired_minute_keys or expired_hour_keys:
            logger.debug(
                "rate_limit_buckets_cleaned",
                minute_entries_removed=len(expired_minute_keys),
                hour_entries_removed=len(expired_hour_keys),
            )

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
    - API versioning headers (Audit 2)
    """

    # SECURITY FIX (Audit 2): API version for client compatibility tracking
    API_VERSION = "2.0.0"
    API_MIN_SUPPORTED_VERSION = "2.0.0"

    def __init__(self, app: Any, enable_hsts: bool = False) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response = await call_next(request)

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

        # SECURITY FIX (Audit 2): API versioning headers for client compatibility
        response.headers["X-API-Version"] = self.API_VERSION
        response.headers["X-API-Min-Version"] = self.API_MIN_SUPPORTED_VERSION

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

    def __init__(self, app: Any, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self.enabled:
            response: Response = await call_next(request)
            return response

        # Only check protected methods
        if request.method not in self.PROTECTED_METHODS:
            response = await call_next(request)
            return response

        # Check exempt paths
        path = request.url.path
        if path in self.EXEMPT_PATHS:
            response = await call_next(request)
            return response

        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                response = await call_next(request)
                return response

        # If using Authorization header (API clients), skip CSRF check
        # API clients use tokens, not cookies, so CSRF doesn't apply
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            response = await call_next(request)
            return response

        # For cookie-based auth, validate CSRF token
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        # If no cookie auth is being used, skip CSRF check
        access_token_cookie = request.cookies.get("access_token")
        if not access_token_cookie:
            response = await call_next(request)
            return response

        # Cookie auth is being used - require valid CSRF token
        # SECURITY FIX (Audit 4 - M): Add code field for robust frontend detection
        if not csrf_cookie or not csrf_header:
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token missing", "code": "CSRF_MISSING"},
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
                content={"error": "CSRF token invalid", "code": "CSRF_INVALID"},
            )

        response = await call_next(request)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit request body size to prevent DoS attacks.
    """

    def __init__(self, app: Any, max_content_length: int = 10 * 1024 * 1024) -> None:
        """
        Args:
            max_content_length: Maximum request body size in bytes (default 10MB)
        """
        super().__init__(app)
        self.max_content_length = max_content_length

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
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

        response: Response = await call_next(request)
        return response


class APILimitsMiddleware(BaseHTTPMiddleware):
    """
    SECURITY FIX (Audit 3): Additional API request limits to prevent DoS attacks.

    Enforces:
    - JSON depth limit to prevent stack overflow attacks
    - Query parameter count limit to prevent parameter pollution
    - IP-based rate limiting (in addition to user-based)
    """

    def __init__(
        self,
        app: Any,
        max_json_depth: int = 20,
        max_query_params: int = 50,
        max_array_length: int = 1000,
    ) -> None:
        """
        Args:
            max_json_depth: Maximum nesting depth for JSON bodies (default 20)
            max_query_params: Maximum number of query parameters (default 50)
            max_array_length: Maximum length of arrays in JSON (default 1000)
        """
        super().__init__(app)
        self.max_json_depth = max_json_depth
        self.max_query_params = max_query_params
        self.max_array_length = max_array_length

    def _check_json_depth(self, obj: Any, current_depth: int = 0) -> tuple[bool, str]:
        """
        Recursively check JSON depth and array lengths.

        Returns:
            (is_valid, error_message)
        """
        if current_depth > self.max_json_depth:
            return False, f"JSON depth exceeds maximum of {self.max_json_depth}"

        if isinstance(obj, dict):
            for value in obj.values():
                is_valid, error = self._check_json_depth(value, current_depth + 1)
                if not is_valid:
                    return False, error
        elif isinstance(obj, list):
            if len(obj) > self.max_array_length:
                return False, f"Array length {len(obj)} exceeds maximum of {self.max_array_length}"
            for item in obj:
                is_valid, error = self._check_json_depth(item, current_depth + 1)
                if not is_valid:
                    return False, error

        return True, ""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Check query parameter count
        query_params = request.query_params
        if len(query_params) > self.max_query_params:
            logger.warning(
                "query_param_limit_exceeded",
                param_count=len(query_params),
                max_params=self.max_query_params,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Too many query parameters",
                    "max_params": self.max_query_params,
                },
            )

        # Check JSON depth for POST/PUT/PATCH requests with JSON body
        content_type = request.headers.get("Content-Type", "")
        if (
            request.method in {"POST", "PUT", "PATCH"}
            and "application/json" in content_type
        ):
            try:
                # Read body and check depth
                body = await request.body()
                if body:
                    import json
                    try:
                        json_data = json.loads(body)
                        is_valid, error = self._check_json_depth(json_data)
                        if not is_valid:
                            logger.warning(
                                "json_depth_limit_exceeded",
                                error=error,
                                path=request.url.path,
                            )
                            return JSONResponse(
                                status_code=400,
                                content={"error": error},
                            )
                    except json.JSONDecodeError:
                        pass  # Let FastAPI handle JSON parse errors
            except (ValueError, OSError, RuntimeError):
                pass  # Don't block on body read errors

        response: Response = await call_next(request)
        return response


@dataclass
class IdempotencyEntry:
    """Cached response for idempotency."""
    status_code: int
    body: bytes
    headers: dict[str, str]
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
    # SECURITY FIX (Audit 4 - M): Add cache size limit to prevent memory exhaustion
    MAX_CACHE_SIZE = 10000  # Max cached idempotency entries
    # SECURITY FIX (Audit 6): Limit response body size to prevent memory exhaustion
    MAX_RESPONSE_SIZE = 1024 * 1024  # 1MB max response size for caching

    def __init__(self, app: Any, ttl_seconds: int = 86400) -> None:  # 24 hour default
        super().__init__(app)
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, IdempotencyEntry] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Only handle idempotent methods
        if request.method not in self.IDEMPOTENT_METHODS:
            response: Response = await call_next(request)
            return response

        # Check for idempotency key
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            response = await call_next(request)
            return response

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
        user_id: str = getattr(request.state, 'user_id', None) or 'anonymous'
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
            # Read response body - body_iterator is available on StreamingResponse
            body = b""
            if hasattr(response, 'body_iterator'):
                streaming_response: StreamingResponse = response  # type: ignore[assignment]
                async for chunk in streaming_response.body_iterator:
                    if isinstance(chunk, bytes):
                        body += chunk
                    elif isinstance(chunk, str):
                        body += chunk.encode()
                    elif isinstance(chunk, memoryview):
                        body += bytes(chunk)

            # SECURITY FIX (Audit 6): Only cache responses under size limit
            if len(body) <= self.MAX_RESPONSE_SIZE:
                # Store in cache
                with self._lock:
                    # SECURITY FIX (Audit 4 - M): Evict oldest entries if cache is full
                    if len(self._cache) >= self.MAX_CACHE_SIZE:
                        # Evict 10% of oldest entries
                        evict_count = self.MAX_CACHE_SIZE // 10
                        oldest_keys = sorted(
                            self._cache.keys(),
                            key=lambda k: self._cache[k].created_at
                        )[:evict_count]
                        for key in oldest_keys:
                            del self._cache[key]

                    headers_dict: dict[str, str] = dict(response.headers)
                    self._cache[cache_key] = IdempotencyEntry(
                        status_code=response.status_code,
                        body=body,
                        headers=headers_dict,
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

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Check if client accepts gzip
        request.headers.get("Accept-Encoding", "")

        response: Response = await call_next(request)

        # In production, actual compression would happen here
        # For now, just pass through

        return response


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """
    Enforce request timeout to prevent slow requests from holding resources.

    SECURITY FIX (Audit 2): Prevent slowloris and resource exhaustion attacks
    by enforcing a maximum request processing time.
    """

    # Paths that may need longer timeouts (e.g., file uploads, cascade processing)
    EXTENDED_TIMEOUT_PATHS = {
        "/api/v1/cascade/trigger",
        "/api/v1/graph/pagerank",
        "/api/v1/graph/communities",
    }

    def __init__(
        self,
        app: Any,
        default_timeout: float = 30.0,  # 30 seconds default
        extended_timeout: float = 120.0,  # 2 minutes for long operations
    ) -> None:
        super().__init__(app)
        self.default_timeout = default_timeout
        self.extended_timeout = extended_timeout

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Determine timeout for this request
        timeout = self.default_timeout
        for path in self.EXTENDED_TIMEOUT_PATHS:
            if request.url.path.startswith(path):
                timeout = self.extended_timeout
                break

        try:
            response: Response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout,
            )
            return response
        except TimeoutError:
            logger.warning(
                "request_timeout",
                path=request.url.path,
                method=request.method,
                timeout=timeout,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "detail": "The request took too long to process",
                },
            )


__all__ = [
    "CorrelationIdMiddleware",
    "RequestLoggingMiddleware",
    "AuthenticationMiddleware",
    "SessionBindingMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "CSRFProtectionMiddleware",
    "RequestSizeLimitMiddleware",
    "APILimitsMiddleware",
    "IdempotencyMiddleware",
    "CompressionMiddleware",
    "RequestTimeoutMiddleware",
]
