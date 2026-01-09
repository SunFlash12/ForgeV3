"""
JWT Token Management for Forge Cascade V2

Handles creation, validation, and refresh of JWT tokens
for user authentication.

Includes:
- Token creation (access and refresh)
- Token validation
- Token blacklisting for revocation (Redis-backed for distributed deployments)

SECURITY FIXES (Audit 2):
- Replaced python-jose with PyJWT>=2.8.0 (CVE-2022-29217 fix)
- Replaced threading.Lock with asyncio.Lock for async methods
- Hardcoded algorithm list to prevent algorithm confusion attacks
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Set
from uuid import uuid4
import threading
import time
import asyncio

# SECURITY FIX: Use PyJWT instead of abandoned python-jose
import jwt as pyjwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, DecodeError
from pydantic import ValidationError
import structlog

from ..config import get_settings
from ..models.user import TokenPayload, Token

settings = get_settings()
logger = structlog.get_logger(__name__)

# Try to import redis for distributed blacklist
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False


class TokenBlacklist:
    """
    Hybrid token blacklist with Redis support for distributed deployments.

    Uses Redis when available for distributed token revocation across
    multiple API instances. Falls back to in-memory storage when Redis
    is unavailable.

    Tokens are identified by their JTI (JWT ID) claim.

    SECURITY FIX (Audit 2): Uses asyncio.Lock for async methods to prevent
    blocking the event loop. threading.Lock retained for sync methods only.
    """

    # In-memory fallback storage
    _blacklist: Set[str] = set()
    _expiry_times: dict[str, float] = {}
    _sync_lock = threading.Lock()  # For sync methods only
    _async_lock: Optional[asyncio.Lock] = None  # Lazy-initialized for async methods
    _last_cleanup: float = 0
    _cleanup_interval: float = 300  # 5 minutes

    # Redis connection
    _redis_client: Optional[Any] = None
    _redis_initialized: bool = False
    _redis_prefix: str = "forge:token:blacklist:"

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock (must be called from async context)."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    async def initialize(cls, redis_url: Optional[str] = None) -> bool:
        """
        Initialize Redis connection for distributed blacklist.

        Args:
            redis_url: Redis URL (uses settings if not provided)

        Returns:
            True if Redis connection successful, False otherwise
        """
        if cls._redis_initialized:
            return cls._redis_client is not None

        if not REDIS_AVAILABLE:
            logger.warning("token_blacklist_redis_unavailable", reason="redis library not installed")
            cls._redis_initialized = True
            return False

        url = redis_url or settings.redis_url
        if not url:
            logger.info("token_blacklist_memory_mode", reason="no redis URL configured")
            cls._redis_initialized = True
            return False

        try:
            cls._redis_client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # Test connection
            await cls._redis_client.ping()
            cls._redis_initialized = True
            logger.info("token_blacklist_redis_connected", redis_url=url[:20] + "...")
            return True
        except Exception as e:
            logger.warning("token_blacklist_redis_failed", error=str(e))
            cls._redis_client = None
            cls._redis_initialized = True
            return False

    @classmethod
    async def add_async(cls, jti: str, expires_at: Optional[float] = None) -> None:
        """
        Add a token to the blacklist (async version).

        Args:
            jti: JWT ID to blacklist
            expires_at: Unix timestamp when this entry can be removed
        """
        if not jti:
            return

        # Calculate TTL in seconds
        ttl = None
        if expires_at:
            ttl = int(expires_at - time.time())
            if ttl <= 0:
                return  # Already expired, no need to blacklist

        # Try Redis first
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                if ttl:
                    await cls._redis_client.setex(key, ttl, "1")
                else:
                    # Default 24 hour TTL if none specified
                    await cls._redis_client.setex(key, 86400, "1")
                logger.debug("token_blacklisted_redis", jti=jti[:8] + "...")
                return
            except Exception as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="add")
                # Fall through to in-memory

        # In-memory fallback (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._blacklist.add(jti)
            if expires_at:
                cls._expiry_times[jti] = expires_at
            cls._maybe_cleanup_unlocked()
            logger.debug("token_blacklisted_memory", jti=jti[:8] + "...")

    @classmethod
    async def is_blacklisted_async(cls, jti: Optional[str]) -> bool:
        """Check if a token is blacklisted (async version)."""
        if not jti:
            return False

        # Try Redis first
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                result = await cls._redis_client.exists(key)
                return bool(result)
            except Exception as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="check")
                # Fall through to in-memory

        # In-memory fallback (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._maybe_cleanup_unlocked()
            return jti in cls._blacklist

    @classmethod
    def add(cls, jti: str, expires_at: Optional[float] = None) -> None:
        """
        Add a token to the blacklist (sync version for backwards compatibility).

        Note: This only adds to in-memory storage. Use add_async for Redis support.
        """
        if not jti:
            return

        with cls._sync_lock:
            cls._blacklist.add(jti)
            if expires_at:
                cls._expiry_times[jti] = expires_at
            cls._maybe_cleanup_unlocked()

    @classmethod
    def is_blacklisted(cls, jti: Optional[str]) -> bool:
        """Check if a token is blacklisted (sync version)."""
        if not jti:
            return False

        with cls._sync_lock:
            cls._maybe_cleanup_unlocked()
            return jti in cls._blacklist

    @classmethod
    def remove(cls, jti: str) -> None:
        """Remove a token from the blacklist."""
        with cls._sync_lock:
            cls._blacklist.discard(jti)
            cls._expiry_times.pop(jti, None)

    @classmethod
    async def remove_async(cls, jti: str) -> None:
        """Remove a token from the blacklist (async version)."""
        # Remove from Redis if available
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                await cls._redis_client.delete(key)
            except Exception as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="remove")

        # Also remove from in-memory (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._blacklist.discard(jti)
            cls._expiry_times.pop(jti, None)

    @classmethod
    def _maybe_cleanup_unlocked(cls) -> None:
        """
        Remove expired entries from the in-memory blacklist.

        Note: Caller must hold the lock (sync or async).
        """
        now = time.time()
        if now - cls._last_cleanup < cls._cleanup_interval:
            return

        cls._last_cleanup = now
        expired = [
            jti for jti, exp in cls._expiry_times.items()
            if exp < now
        ]
        for jti in expired:
            cls._blacklist.discard(jti)
            del cls._expiry_times[jti]

    @classmethod
    def clear(cls) -> None:
        """Clear the entire blacklist (for testing)."""
        with cls._sync_lock:
            cls._blacklist.clear()
            cls._expiry_times.clear()

    @classmethod
    async def clear_async(cls) -> None:
        """Clear the entire blacklist including Redis (for testing)."""
        # Clear Redis keys with our prefix
        if cls._redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await cls._redis_client.scan(
                        cursor, match=f"{cls._redis_prefix}*", count=100
                    )
                    if keys:
                        await cls._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="clear")

        # Clear in-memory (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._blacklist.clear()
            cls._expiry_times.clear()

    @classmethod
    async def close(cls) -> None:
        """Close Redis connection."""
        if cls._redis_client:
            try:
                await cls._redis_client.close()
            except Exception:
                pass
            cls._redis_client = None
        cls._redis_initialized = False


class TokenError(Exception):
    """Base exception for token-related errors."""
    pass


class TokenExpiredError(TokenError):
    """Token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Token is invalid or malformed."""
    pass


# SECURITY FIX: Hardcoded allowed algorithms to prevent algorithm confusion attacks
ALLOWED_JWT_ALGORITHMS = ["HS256", "HS384", "HS512"]


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    trust_flame: int,
    additional_claims: Optional[dict[str, Any]] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role (user, moderator, admin, system)
        trust_flame: User's trust score (0-100)
        additional_claims: Extra claims to include in token

    Returns:
        Encoded JWT access token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "trust_flame": trust_flame,
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),  # JWT ID for token revocation
        "type": "access"
    }

    if additional_claims:
        payload.update(additional_claims)

    # SECURITY FIX: Use PyJWT instead of python-jose
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    username: str
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have longer expiration and are used to get new access tokens.

    Args:
        user_id: User's unique identifier
        username: User's username

    Returns:
        Encoded JWT refresh token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": now,
        "jti": str(uuid4()),
        "type": "refresh"
    }

    # SECURITY FIX: Use PyJWT instead of python-jose
    return pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(
    user_id: str,
    username: str,
    role: str,
    trust_flame: int
) -> Token:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role
        trust_flame: User's trust score
        
    Returns:
        Token model with both access and refresh tokens
    """
    access_token = create_access_token(user_id, username, role, trust_flame)
    refresh_token = create_refresh_token(user_id, username)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60  # Convert to seconds
    )


def decode_token(token: str, verify_exp: bool = True) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string
        verify_exp: Whether to verify expiration (default True)

    Returns:
        TokenPayload with decoded claims

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid
    """
    try:
        # SECURITY FIX: Use PyJWT with hardcoded algorithm whitelist
        # This prevents algorithm confusion attacks (CVE-2022-29217)
        algorithm = settings.jwt_algorithm
        if algorithm not in ALLOWED_JWT_ALGORITHMS:
            raise TokenInvalidError(f"Disallowed algorithm: {algorithm}")

        options = {}
        if not verify_exp:
            options["verify_exp"] = False

        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=ALLOWED_JWT_ALGORITHMS,  # Hardcoded whitelist
            options=options
        )

        return TokenPayload(
            sub=payload["sub"],
            username=payload.get("username"),
            role=payload.get("role"),
            trust_flame=payload.get("trust_flame"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            jti=payload.get("jti"),
            type=payload.get("type", "access")
        )

    except ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except (InvalidTokenError, DecodeError) as e:
        raise TokenInvalidError(f"Invalid token: {str(e)}")
    except ValidationError as e:
        raise TokenInvalidError(f"Token payload validation failed: {str(e)}")


def verify_access_token(token: str) -> TokenPayload:
    """
    Verify an access token (sync version).

    NOTE: This sync version only checks in-memory blacklist.
    For full Redis blacklist support, use verify_access_token_async().

    Args:
        token: JWT access token

    Returns:
        TokenPayload if valid

    Raises:
        TokenError: If token is invalid or not an access token
    """
    payload = decode_token(token)

    if payload.type != "access":
        raise TokenInvalidError("Not an access token")

    # SECURITY FIX: Check token blacklist (sync - in-memory only)
    # For Redis support, use verify_access_token_async()
    if TokenBlacklist.is_blacklisted(payload.jti):
        logger.warning(
            "blacklisted_token_rejected",
            jti=payload.jti[:8] + "..." if payload.jti else "none",
            user_id=payload.sub
        )
        raise TokenInvalidError("Token has been revoked")

    # SECURITY FIX: Require all essential claims to be present
    # This prevents attacks where claims are removed from token
    if not payload.sub:
        raise TokenInvalidError("Token missing required sub claim")

    if payload.trust_flame is None:
        raise TokenInvalidError("Token missing required trust_flame claim")

    if payload.role is None:
        raise TokenInvalidError("Token missing required role claim")

    # Validate trust_flame is within valid range
    if not (0 <= payload.trust_flame <= 100):
        raise TokenInvalidError("Invalid trust_flame value in token")

    return payload


async def verify_access_token_async(token: str) -> TokenPayload:
    """
    Verify an access token (async version with full blacklist support).

    This version checks both Redis and in-memory blacklists for
    token revocation. Use this in async API endpoints.

    Args:
        token: JWT access token

    Returns:
        TokenPayload if valid

    Raises:
        TokenError: If token is invalid, blacklisted, or not an access token
    """
    payload = decode_token(token)

    if payload.type != "access":
        raise TokenInvalidError("Not an access token")

    # SECURITY FIX: Check token blacklist (async - Redis + in-memory)
    if await TokenBlacklist.is_blacklisted_async(payload.jti):
        logger.warning(
            "blacklisted_token_rejected",
            jti=payload.jti[:8] + "..." if payload.jti else "none",
            user_id=payload.sub
        )
        raise TokenInvalidError("Token has been revoked")

    # SECURITY FIX: Require all essential claims to be present
    # This prevents attacks where claims are removed from token
    if not payload.sub:
        raise TokenInvalidError("Token missing required sub claim")

    if payload.trust_flame is None:
        raise TokenInvalidError("Token missing required trust_flame claim")

    if payload.role is None:
        raise TokenInvalidError("Token missing required role claim")

    # Validate trust_flame is within valid range
    if not (0 <= payload.trust_flame <= 100):
        raise TokenInvalidError("Invalid trust_flame value in token")

    return payload


def get_token_claims(token: str) -> dict[str, Any]:
    """
    Extract claims from a token without full validation.

    Used for blacklisting/logging purposes where we need JTI even from
    potentially invalid tokens.

    Args:
        token: JWT token string

    Returns:
        Dictionary of claims

    Raises:
        TokenInvalidError: If token cannot be decoded at all
    """
    try:
        # SECURITY FIX: Use PyJWT with algorithm whitelist even for extraction
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            options={"verify_exp": False}
        )
        return payload
    except (InvalidTokenError, DecodeError) as e:
        raise TokenInvalidError(f"Cannot decode token: {str(e)}")


def verify_refresh_token(token: str) -> TokenPayload:
    """
    Verify a refresh token.
    
    Args:
        token: JWT refresh token
        
    Returns:
        TokenPayload if valid
        
    Raises:
        TokenError: If token is invalid or not a refresh token
    """
    payload = decode_token(token)
    
    if payload.type != "refresh":
        raise TokenInvalidError("Not a refresh token")
    
    return payload


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get the expiration time of a token.
    
    Args:
        token: JWT token
        
    Returns:
        Datetime of expiration, or None if no expiration
    """
    try:
        payload = decode_token(token, verify_exp=False)
        if payload.exp:
            return datetime.fromtimestamp(payload.exp)
        return None
    except TokenError:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired.
    
    Args:
        token: JWT token
        
    Returns:
        True if expired, False otherwise
    """
    try:
        decode_token(token)
        return False
    except TokenExpiredError:
        return True
    except TokenError:
        return True  # Invalid tokens are considered "expired" for security


def extract_token_from_header(authorization: str) -> str:
    """
    Extract JWT token from Authorization header.
    
    Expected format: "Bearer <token>"
    
    Args:
        authorization: Authorization header value
        
    Returns:
        JWT token string
        
    Raises:
        TokenInvalidError: If header format is invalid
    """
    parts = authorization.split()
    
    if len(parts) != 2:
        raise TokenInvalidError("Invalid authorization header format")
    
    scheme, token = parts
    
    if scheme.lower() != "bearer":
        raise TokenInvalidError("Invalid authentication scheme")
    
    return token


def verify_token(token: str, secret_key: str = None, expected_type: str = "access") -> TokenPayload:
    """
    Verify a JWT token.
    
    This is a convenience function that wraps decode_token for API usage.
    
    Args:
        token: JWT token string
        secret_key: Secret key (uses settings if not provided)
        expected_type: Expected token type ('access' or 'refresh')
        
    Returns:
        TokenPayload if valid
        
    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid or wrong type
    """
    payload = decode_token(token)
    
    if expected_type and payload.type != expected_type:
        raise TokenInvalidError(f"Expected {expected_type} token, got {payload.type}")
    
    return payload


class TokenService:
    """
    Service class for token operations.
    
    Provides a class-based interface for token management.
    """
    
    @staticmethod
    def create_access_token(user_id: str, **kwargs) -> str:
        """Create an access token."""
        return create_access_token(user_id, **kwargs)
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create a refresh token."""
        return create_refresh_token(user_id)
    
    @staticmethod
    def create_token_pair(user_id: str, **kwargs) -> "Token":
        """Create an access/refresh token pair."""
        return create_token_pair(user_id, **kwargs)
    
    @staticmethod
    def verify_access_token(token: str) -> TokenPayload:
        """Verify an access token (sync - in-memory blacklist only)."""
        return verify_access_token(token)

    @staticmethod
    async def verify_access_token_async(token: str) -> TokenPayload:
        """Verify an access token (async - full Redis blacklist support)."""
        return await verify_access_token_async(token)

    @staticmethod
    def verify_refresh_token(token: str) -> TokenPayload:
        """Verify a refresh token."""
        return verify_refresh_token(token)
    
    @staticmethod
    def verify(token: str, expected_type: str = "access") -> TokenPayload:
        """Verify a token of expected type."""
        return verify_token(token, expected_type=expected_type)
    
    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        """Decode a token."""
        return decode_token(token, verify_exp)
    
    @staticmethod
    def is_expired(token: str) -> bool:
        """Check if token is expired."""
        return is_token_expired(token)
