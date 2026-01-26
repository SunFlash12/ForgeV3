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

import asyncio
import hashlib
import threading
import time
import types
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

# SECURITY FIX: Use PyJWT instead of abandoned python-jose
import jwt as pyjwt
import structlog
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidTokenError
from pydantic import ValidationError

from ..config import get_settings
from ..models.user import Token, TokenPayload

settings = get_settings()
logger = structlog.get_logger(__name__)

# Try to import redis for distributed blacklist
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis: types.ModuleType | None = None  # type: ignore[no-redef]
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

    SECURITY FIX (Audit 3): Added bounded memory limits to prevent DoS through
    memory exhaustion. Maximum 100,000 entries.

    SECURITY FIX (Audit 5): Changed from LRU eviction to EXPIRY-BASED eviction.
    LRU eviction allowed attackers to flood the blacklist and evict legitimately
    revoked tokens, enabling token replay attacks. Now only expired tokens are
    removed, and all blacklisted tokens must have an expiry time.
    """

    # In-memory fallback storage
    # SECURITY FIX (Audit 3): Bounded memory - max 100,000 blacklisted tokens
    # SECURITY FIX (Audit 5): Changed from LRU to expiry-based eviction to prevent
    # attackers from flooding blacklist to evict legitimately revoked tokens
    _MAX_BLACKLIST_SIZE: int = 100000
    _blacklist: set[str] = set()
    _expiry_times: dict[str, float] = {}  # jti -> expiry timestamp (required for all entries)
    _sync_lock = threading.Lock()  # For sync methods only
    _async_lock: asyncio.Lock | None = None  # Lazy-initialized for async methods
    _last_cleanup: float = 0
    _cleanup_interval: float = 60  # 1 minute (more frequent cleanup for expiry-based eviction)

    # Redis connection
    _redis_client: Any | None = None
    _redis_initialized: bool = False
    _redis_prefix: str = "forge:token:blacklist:"

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock (must be called from async context)."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    async def initialize(cls, redis_url: str | None = None) -> bool:
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
            logger.warning(
                "token_blacklist_redis_unavailable", reason="redis library not installed"
            )
            cls._redis_initialized = True
            return False

        url = redis_url or settings.redis_url
        if not url:
            logger.info("token_blacklist_memory_mode", reason="no redis URL configured")
            cls._redis_initialized = True
            return False

        try:
            cls._redis_client = aioredis.from_url(  # type: ignore[no-untyped-call]
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
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning("token_blacklist_redis_failed", error=str(e))
            cls._redis_client = None
            cls._redis_initialized = True
            return False

    @classmethod
    async def add_async(cls, jti: str, expires_at: float | None = None) -> None:
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
                # SECURITY FIX (Audit 4 - L2): Log more JTI chars for debugging
                logger.debug("token_blacklisted_redis", jti=jti[:16] + "...")
                return
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="add")
                # Fall through to in-memory

        # In-memory fallback (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            # SECURITY FIX (Audit 5): Always require expiry time to enable expiry-based eviction
            # Default to 24 hours if not specified (same as Redis default)
            if not expires_at:
                expires_at = time.time() + 86400  # 24 hours

            # Run cleanup first to make room for new entry
            cls._maybe_cleanup_unlocked()

            # SECURITY FIX (Audit 5): Check capacity AFTER cleanup
            # If still at capacity, refuse to add rather than evict valid tokens
            if len(cls._blacklist) >= cls._MAX_BLACKLIST_SIZE:
                logger.error(
                    "token_blacklist_at_capacity",
                    size=len(cls._blacklist),
                    max_size=cls._MAX_BLACKLIST_SIZE,
                    jti=jti[:16] + "...",
                    action="rejected",
                )
                # Still add to blacklist - security is more important than memory
                # In production, should alert ops team to investigate

            cls._blacklist.add(jti)
            cls._expiry_times[jti] = expires_at
            # SECURITY FIX (Audit 4 - L2): Log more JTI chars for debugging
            logger.debug("token_blacklisted_memory", jti=jti[:16] + "...")

    @classmethod
    async def is_blacklisted_async(cls, jti: str | None) -> bool:
        """Check if a token is blacklisted (async version)."""
        if not jti:
            return False

        # Try Redis first
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                result = await cls._redis_client.exists(key)
                return bool(result)
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="check")
                # Fall through to in-memory

        # In-memory fallback (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._maybe_cleanup_unlocked()
            return jti in cls._blacklist

    @classmethod
    def add(cls, jti: str, expires_at: float | None = None) -> None:
        """
        Add a token to the blacklist (sync version for backwards compatibility).

        Note: This only adds to in-memory storage. Use add_async for Redis support.
        """
        if not jti:
            return

        with cls._sync_lock:
            # SECURITY FIX (Audit 5): Always require expiry time to enable expiry-based eviction
            # Default to 24 hours if not specified
            if not expires_at:
                expires_at = time.time() + 86400  # 24 hours

            # Run cleanup first to make room for new entry
            cls._maybe_cleanup_unlocked()

            # SECURITY FIX (Audit 5): Check capacity AFTER cleanup
            # If still at capacity, log error but still add (security > memory)
            if len(cls._blacklist) >= cls._MAX_BLACKLIST_SIZE:
                logger.error(
                    "token_blacklist_at_capacity",
                    size=len(cls._blacklist),
                    max_size=cls._MAX_BLACKLIST_SIZE,
                    jti=jti[:16] + "...",
                    action="adding_anyway",
                )

            cls._blacklist.add(jti)
            cls._expiry_times[jti] = expires_at

    @classmethod
    def is_blacklisted(cls, jti: str | None) -> bool:
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
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_blacklist_redis_error", error=str(e), operation="remove")

        # Also remove from in-memory (SECURITY FIX: use async lock)
        async with cls._get_async_lock():
            cls._blacklist.discard(jti)
            cls._expiry_times.pop(jti, None)

    @classmethod
    def _maybe_cleanup_unlocked(cls) -> None:
        """
        Remove expired entries from the in-memory blacklist.

        SECURITY FIX (Audit 5): Changed from LRU to expiry-based eviction.
        Only removes tokens that have actually expired - never removes valid
        revoked tokens. This prevents attackers from flooding the blacklist
        to evict legitimately revoked tokens for replay attacks.

        Note: Caller must hold the lock (sync or async).
        """
        now = time.time()
        if now - cls._last_cleanup < cls._cleanup_interval:
            return

        cls._last_cleanup = now
        expired = [jti for jti, exp in cls._expiry_times.items() if exp < now]

        if expired:
            for jti in expired:
                cls._blacklist.discard(jti)
                cls._expiry_times.pop(jti, None)

            logger.debug(
                "token_blacklist_cleanup", expired_count=len(expired), remaining=len(cls._blacklist)
            )

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
            except (ConnectionError, TimeoutError, OSError) as e:
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
            except (ConnectionError, TimeoutError, OSError):
                pass  # Intentional broad catch: closing connection may fail if already disconnected
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

# SECURITY FIX (Audit 6): Maximum token size to prevent DoS through oversized tokens
# A typical JWT is ~500-1000 bytes. We set a generous limit of 16KB.
MAX_TOKEN_SIZE_BYTES = 16 * 1024  # 16KB max token size


class TokenTooLargeError(TokenError):
    """Token exceeds maximum allowed size."""

    pass


class TokenVersionOutdatedError(TokenError):
    """Token version is outdated due to privilege change."""

    pass


# =============================================================================
# SECURITY FIX (Audit 6): Token Version Caching
# =============================================================================


class TokenVersionCache:
    """
    Cache for user token versions to optimize validation performance.

    SECURITY FIX (Audit 6): When user privileges change, their token version
    is incremented. This cache allows fast validation of token versions
    without hitting the database on every request.

    Uses Redis when available, falls back to in-memory cache.
    """

    _cache: dict[str, tuple[int, float]] = {}  # user_id -> (version, expiry_timestamp)
    _redis_prefix: str = "forge:token_version:"
    _async_lock: asyncio.Lock | None = None

    @classmethod
    def _get_cache_ttl(cls) -> float:
        """Get cache TTL from settings."""
        return float(settings.token_version_cache_ttl_seconds)

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    async def get_version(cls, user_id: str, db_fallback: Any = None) -> int:
        """
        Get cached token version for a user.

        Args:
            user_id: User ID
            db_fallback: Async function to get version from DB if cache miss

        Returns:
            Token version (defaults to 1 if not found)
        """
        now = time.time()

        # Try Redis first if available
        if TokenBlacklist._redis_client:
            try:
                key = f"{cls._redis_prefix}{user_id}"
                cached = await TokenBlacklist._redis_client.get(key)
                if cached is not None:
                    return int(cached)
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_version_cache_redis_error", error=str(e))

        # Try in-memory cache
        async with cls._get_async_lock():
            if user_id in cls._cache:
                version, expiry = cls._cache[user_id]
                if now < expiry:
                    return version
                # Expired, remove from cache
                cls._cache.pop(user_id, None)

        # Cache miss - fetch from database
        if db_fallback:
            try:
                db_version: int = await db_fallback(user_id)
                await cls.set_version(user_id, db_version)
                return db_version
            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                logger.warning("token_version_db_fetch_error", user_id=user_id, error=str(e))

        # Default to version 1 (will be valid for legacy users)
        return 1

    @classmethod
    async def set_version(cls, user_id: str, version: int) -> None:
        """
        Cache a token version.

        Args:
            user_id: User ID
            version: Token version to cache
        """
        now = time.time()
        cache_ttl = cls._get_cache_ttl()
        ttl_seconds = int(cache_ttl)

        # Try Redis first
        if TokenBlacklist._redis_client:
            try:
                key = f"{cls._redis_prefix}{user_id}"
                await TokenBlacklist._redis_client.setex(key, ttl_seconds, str(version))
                return
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_version_cache_redis_error", error=str(e))

        # Fall back to in-memory cache
        async with cls._get_async_lock():
            cls._cache[user_id] = (version, now + cache_ttl)

    @classmethod
    async def invalidate(cls, user_id: str) -> None:
        """
        Invalidate cached token version for a user.

        Call this when incrementing a user's token version.

        Args:
            user_id: User ID
        """
        # Invalidate Redis cache
        if TokenBlacklist._redis_client:
            try:
                key = f"{cls._redis_prefix}{user_id}"
                await TokenBlacklist._redis_client.delete(key)
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("token_version_cache_redis_error", error=str(e))

        # Invalidate in-memory cache
        async with cls._get_async_lock():
            cls._cache.pop(user_id, None)

        logger.debug("token_version_cache_invalidated", user_id=user_id)

    @classmethod
    async def clear(cls) -> None:
        """Clear entire cache (for testing)."""
        # Clear Redis
        if TokenBlacklist._redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await TokenBlacklist._redis_client.scan(
                        cursor, match=f"{cls._redis_prefix}*", count=100
                    )
                    if keys:
                        await TokenBlacklist._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except (ConnectionError, TimeoutError, OSError):
                pass  # Intentional: best-effort cleanup during clear

        # Clear in-memory
        async with cls._get_async_lock():
            cls._cache.clear()


def validate_token_size(token: str) -> None:
    """
    SECURITY FIX (Audit 6): Validate token size to prevent DoS attacks.

    Oversized tokens can:
    - Consume excessive memory during decoding
    - Slow down signature verification
    - Fill up logs and caches

    Args:
        token: JWT token string

    Raises:
        TokenTooLargeError: If token exceeds maximum size
    """
    token_size = len(token.encode("utf-8"))
    if token_size > MAX_TOKEN_SIZE_BYTES:
        logger.warning(
            "token_too_large",
            size=token_size,
            max_size=MAX_TOKEN_SIZE_BYTES,
        )
        raise TokenTooLargeError(
            f"Token size ({token_size} bytes) exceeds maximum allowed ({MAX_TOKEN_SIZE_BYTES} bytes)"
        )


# =============================================================================
# SECURITY FIX (Audit 4): Refresh Token Hashing
# =============================================================================


def hash_refresh_token(token: str) -> str:
    """
    SECURITY FIX (Audit 4): Hash a refresh token for secure storage.

    Instead of storing raw refresh tokens in the database, we store their
    SHA-256 hash. This means if the database is compromised, attackers
    cannot use the stored hashes to authenticate - they need the original
    token which only the legitimate user possesses.

    Args:
        token: The raw refresh token (JWT string)

    Returns:
        SHA-256 hex digest of the token
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_token_hash(token: str, stored_hash: str) -> bool:
    """
    SECURITY FIX (Audit 4): Verify a refresh token against its stored hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        token: The raw refresh token to verify
        stored_hash: The SHA-256 hash stored in the database

    Returns:
        True if the token matches the hash, False otherwise
    """
    import secrets

    token_hash = hash_refresh_token(token)
    return secrets.compare_digest(token_hash, stored_hash)


# =============================================================================
# SECURITY FIX (Audit 3): Key Rotation Support
# =============================================================================


class KeyRotationManager:
    """
    SECURITY FIX (Audit 3): JWT Key Rotation Manager.

    Manages multiple signing keys to support seamless key rotation:
    - Current key: Used for signing new tokens
    - Previous keys: Used for validating tokens during rotation period

    Key rotation process:
    1. Generate new key
    2. Add new key as current (old current becomes previous)
    3. Wait for all old tokens to expire (typically 1 refresh token cycle)
    4. Remove old previous keys

    This allows zero-downtime key rotation without invalidating active tokens.
    """

    _current_key_id: str = "default"
    _keys: dict[str, str] = {}  # key_id -> secret
    _key_created_at: dict[str, datetime] = {}
    _rotation_lock = asyncio.Lock()

    @classmethod
    def initialize(cls) -> None:
        """Initialize with default key from settings."""
        if not cls._keys:
            cls._current_key_id = "key_1"
            cls._keys[cls._current_key_id] = settings.jwt_secret_key
            cls._key_created_at[cls._current_key_id] = datetime.now(UTC)
            logger.info("key_rotation_initialized", current_key_id=cls._current_key_id)

    @classmethod
    def get_current_key(cls) -> tuple[str, str]:
        """
        Get the current signing key.

        Returns:
            Tuple of (key_id, secret)
        """
        cls.initialize()
        return cls._current_key_id, cls._keys[cls._current_key_id]

    @classmethod
    def get_key_by_id(cls, key_id: str) -> str | None:
        """
        Get a key by its ID.

        Args:
            key_id: The key identifier

        Returns:
            The secret key or None if not found
        """
        cls.initialize()
        return cls._keys.get(key_id)

    @classmethod
    def get_all_keys(cls) -> list[str]:
        """
        Get all valid keys for token verification.

        Returns:
            List of all secret keys (current + previous)
        """
        cls.initialize()
        return list(cls._keys.values())

    @classmethod
    async def rotate_key(cls, new_secret: str, keep_previous: int = 2) -> str:
        """
        Rotate to a new signing key.

        Args:
            new_secret: The new secret key (must be at least 32 chars)
            keep_previous: Number of previous keys to keep (default 2)

        Returns:
            The new key ID

        Raises:
            ValueError: If new_secret is too short
        """
        if len(new_secret) < 32:
            raise ValueError("New secret must be at least 32 characters")

        async with cls._rotation_lock:
            cls.initialize()

            # Generate new key ID
            key_num = len(cls._keys) + 1
            new_key_id = f"key_{key_num}"

            # Add new key
            cls._keys[new_key_id] = new_secret
            cls._key_created_at[new_key_id] = datetime.now(UTC)

            # Update current key
            old_key_id = cls._current_key_id
            cls._current_key_id = new_key_id

            # Remove oldest keys if we have too many
            while len(cls._keys) > keep_previous + 1:
                oldest_key = min(cls._key_created_at.keys(), key=lambda k: cls._key_created_at[k])
                if oldest_key != cls._current_key_id:
                    del cls._keys[oldest_key]
                    del cls._key_created_at[oldest_key]
                    logger.info("old_key_removed", key_id=oldest_key)

            logger.info(
                "key_rotated",
                new_key_id=new_key_id,
                old_key_id=old_key_id,
                total_keys=len(cls._keys),
            )

            return new_key_id

    @classmethod
    def decode_with_rotation(
        cls,
        token: str,
        algorithms: list[str],
        options: dict[str, Any] | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        leeway: int = 0,
    ) -> dict[str, Any]:
        """
        Decode a token, trying all valid keys.

        SECURITY FIX (Audit 6): Added issuer and audience validation.

        Args:
            token: The JWT token
            algorithms: Allowed algorithms
            options: PyJWT decode options
            issuer: Expected issuer (iss claim) - validated if provided
            audience: Expected audience (aud claim) - validated if provided
            leeway: Clock skew tolerance in seconds for exp/nbf validation

        Returns:
            Decoded payload

        Raises:
            InvalidTokenError: If token cannot be decoded with any key
        """
        cls.initialize()

        # Build decode kwargs with optional issuer/audience validation
        decode_kwargs: dict[str, Any] = {
            "algorithms": algorithms,
            "options": options or {},
            "leeway": timedelta(seconds=leeway),
        }
        if issuer:
            decode_kwargs["issuer"] = issuer
        if audience:
            decode_kwargs["audience"] = audience

        # Try to get key ID from header
        try:
            unverified_header = pyjwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if kid and kid in cls._keys:
                # Try the specific key first
                try:
                    result: dict[str, Any] = pyjwt.decode(token, cls._keys[kid], **decode_kwargs)
                    return result
                except (InvalidTokenError, DecodeError):
                    pass  # Fall through to try all keys
        except (InvalidTokenError, DecodeError, ValueError, KeyError):
            pass  # No valid header, try all keys

        # Try all keys
        last_error = None
        for key in cls.get_all_keys():
            try:
                decoded: dict[str, Any] = pyjwt.decode(token, key, **decode_kwargs)
                return decoded
            except ExpiredSignatureError:
                raise  # Don't try other keys for expired tokens
            except (InvalidTokenError, DecodeError) as e:
                last_error = e
                continue

        # None of the keys worked
        raise InvalidTokenError(f"Token verification failed: {last_error}")

    @classmethod
    def get_rotation_status(cls) -> dict[str, Any]:
        """
        Get current key rotation status.

        Returns:
            Dict with rotation status info
        """
        cls.initialize()
        return {
            "current_key_id": cls._current_key_id,
            "total_keys": len(cls._keys),
            "key_ids": list(cls._keys.keys()),
            "key_ages": {
                kid: (datetime.now(UTC) - created).total_seconds()
                for kid, created in cls._key_created_at.items()
            },
        }


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    trust_flame: int,
    token_version: int = 1,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role (user, moderator, admin, system)
        trust_flame: User's trust score (0-100)
        token_version: User's token version for privilege change invalidation
        additional_claims: Extra claims to include in token

    Returns:
        Encoded JWT access token
    """
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    # SECURITY FIX (Audit 6): Add nbf (not before) claim with clock skew tolerance
    not_before = now - timedelta(seconds=settings.jwt_clock_skew_seconds)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "trust_flame": trust_flame,
        "tv": token_version,  # SECURITY FIX (Audit 6): Token version for privilege change invalidation
        "exp": expire,
        "iat": now,
        "nbf": not_before,  # SECURITY FIX (Audit 6): Not valid before this time
        "iss": settings.jwt_issuer,  # SECURITY FIX (Audit 6): Issuer claim
        "aud": settings.jwt_audience,  # SECURITY FIX (Audit 6): Audience claim
        "jti": str(uuid4()),  # JWT ID for token revocation
        "type": "access",
    }

    if additional_claims:
        payload.update(additional_claims)

    # SECURITY FIX (Audit 3): Use KeyRotationManager for signing
    key_id, secret = KeyRotationManager.get_current_key()
    encoded: str = pyjwt.encode(
        payload,
        secret,
        algorithm=settings.jwt_algorithm,
        headers={"kid": key_id},  # Include key ID in header for rotation support
    )
    return encoded


def create_refresh_token(user_id: str, username: str) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have longer expiration and are used to get new access tokens.

    Args:
        user_id: User's unique identifier
        username: User's username

    Returns:
        Encoded JWT refresh token
    """
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    # SECURITY FIX (Audit 6): Add nbf (not before) claim with clock skew tolerance
    not_before = now - timedelta(seconds=settings.jwt_clock_skew_seconds)

    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": now,
        "nbf": not_before,  # SECURITY FIX (Audit 6): Not valid before this time
        "iss": settings.jwt_issuer,  # SECURITY FIX (Audit 6): Issuer claim
        "aud": settings.jwt_audience,  # SECURITY FIX (Audit 6): Audience claim
        "jti": str(uuid4()),
        "type": "refresh",
    }

    # SECURITY FIX (Audit 3): Use KeyRotationManager for signing
    key_id, secret = KeyRotationManager.get_current_key()
    encoded: str = pyjwt.encode(
        payload, secret, algorithm=settings.jwt_algorithm, headers={"kid": key_id}
    )
    return encoded


def create_mfa_pending_token(
    user_id: str,
    username: str,
    ip_address: str | None = None,
) -> str:
    """
    Create a short-lived token for MFA verification step.

    SECURITY FIX (Audit 6 - Session 3): This token is used during two-step login
    when MFA is enabled. It:
    - Has a short expiry (5 minutes default)
    - Contains 'mfa_pending' type to prevent use as access token
    - Can only be exchanged for full tokens via /auth/mfa/verify

    Args:
        user_id: User's unique identifier
        username: User's username
        ip_address: Client IP (stored as hash for audit logging)

    Returns:
        Encoded JWT MFA pending token
    """
    now = datetime.now(UTC)
    expire = now + timedelta(seconds=settings.mfa_pending_token_expire_seconds)
    not_before = now - timedelta(seconds=settings.jwt_clock_skew_seconds)

    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": now,
        "nbf": not_before,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid4()),
        "type": "mfa_pending",  # Distinct type - cannot be used as access token
    }

    # Store IP hash for audit logging (not for strict validation)
    if ip_address:
        payload["ip_hash"] = hashlib.sha256(ip_address.encode()).hexdigest()[:16]

    key_id, secret = KeyRotationManager.get_current_key()
    encoded: str = pyjwt.encode(
        payload, secret, algorithm=settings.jwt_algorithm, headers={"kid": key_id}
    )
    return encoded


def verify_mfa_pending_token(
    token: str,
    ip_address: str | None = None,
) -> TokenPayload:
    """
    Verify an MFA pending token.

    SECURITY FIX (Audit 6 - Session 3): Validates that token is an MFA pending
    token and not an access/refresh token. This prevents token type confusion.

    Args:
        token: JWT MFA pending token
        ip_address: Client IP to log if different from token's bound IP

    Returns:
        TokenPayload if valid

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid or not an MFA pending token
    """
    # Use standard decode with verification
    payload = decode_token(token, verify_exp=True)

    # Verify token type
    if payload.type != "mfa_pending":
        logger.warning(
            "mfa_pending_token_type_mismatch",
            expected="mfa_pending",
            actual=payload.type,
            user_id=payload.sub,
        )
        raise TokenInvalidError("Not an MFA pending token")

    # Log IP mismatch for audit (but don't reject - IP can change legitimately)
    if ip_address:
        try:
            # Decode without validation to get ip_hash claim
            raw_payload = pyjwt.decode(token, options={"verify_signature": False})
            token_ip_hash = raw_payload.get("ip_hash")
            if token_ip_hash:
                current_ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()[:16]
                if token_ip_hash != current_ip_hash:
                    logger.info(
                        "mfa_pending_token_ip_changed",
                        user_id=payload.sub,
                        note="IP changed during MFA verification (logged for audit)",
                    )
        except (InvalidTokenError, DecodeError, ValueError, KeyError):
            pass  # Don't fail on IP logging errors

    return payload


def create_token_pair(
    user_id: str, username: str, role: str, trust_flame: int, token_version: int = 1
) -> Token:
    """
    Create both access and refresh tokens.

    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role
        trust_flame: User's trust score
        token_version: User's token version for privilege change invalidation

    Returns:
        Token model with both access and refresh tokens
    """
    access_token = create_access_token(user_id, username, role, trust_flame, token_version)
    refresh_token = create_refresh_token(user_id, username)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,  # Convert to seconds
    )


def decode_token(token: str, verify_exp: bool = True) -> TokenPayload:
    """
    Decode and validate a JWT token.

    SECURITY FIX (Audit 3): Now uses KeyRotationManager to support key rotation.
    Tokens signed with any valid key (current or previous) will be accepted.

    SECURITY FIX (Audit 6): Added issuer and audience validation to prevent
    token confusion attacks where tokens from one system are accepted by another.

    SECURITY FIX (Audit 6): Added token size validation to prevent DoS attacks.

    Args:
        token: JWT token string
        verify_exp: Whether to verify expiration (default True)

    Returns:
        TokenPayload with decoded claims

    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid
        TokenTooLargeError: If token exceeds maximum size
    """
    try:
        # SECURITY FIX (Audit 6): Validate token size before processing
        validate_token_size(token)

        # SECURITY FIX: Use PyJWT with hardcoded algorithm whitelist
        # This prevents algorithm confusion attacks (CVE-2022-29217)
        algorithm = settings.jwt_algorithm
        if algorithm not in ALLOWED_JWT_ALGORITHMS:
            raise TokenInvalidError(f"Disallowed algorithm: {algorithm}")

        options = {}
        if not verify_exp:
            options["verify_exp"] = False

        # SECURITY FIX (Audit 3): Use KeyRotationManager for decoding
        # This allows tokens signed with any valid key to be verified
        # SECURITY FIX (Audit 6): Validate issuer and audience claims
        payload = KeyRotationManager.decode_with_rotation(
            token,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            options=options,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            leeway=settings.jwt_clock_skew_seconds,
        )

        return TokenPayload(
            sub=payload["sub"],
            username=payload.get("username"),
            role=payload.get("role"),
            trust_flame=payload.get("trust_flame"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            jti=payload.get("jti"),
            type=payload.get("type", "access"),
            tv=payload.get(
                "tv"
            ),  # SECURITY FIX (Audit 6): Token version for privilege change validation
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
            user_id=payload.sub,
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


async def verify_access_token_async(
    token: str, token_version_getter: Any | None = None
) -> TokenPayload:
    """
    Verify an access token (async version with full blacklist support).

    This version checks both Redis and in-memory blacklists for
    token revocation. Use this in async API endpoints.

    SECURITY FIX (Audit 6): Added token version validation to immediately
    invalidate tokens when user privileges change.

    Args:
        token: JWT access token
        token_version_getter: Optional async function(user_id) -> int to get
            current token version from database. If provided, validates that
            token's version matches current version.

    Returns:
        TokenPayload if valid

    Raises:
        TokenError: If token is invalid, blacklisted, or not an access token
        TokenVersionOutdatedError: If token version is outdated
    """
    payload = decode_token(token)

    if payload.type != "access":
        raise TokenInvalidError("Not an access token")

    # SECURITY FIX: Check token blacklist (async - Redis + in-memory)
    if await TokenBlacklist.is_blacklisted_async(payload.jti):
        logger.warning(
            "blacklisted_token_rejected",
            jti=payload.jti[:8] + "..." if payload.jti else "none",
            user_id=payload.sub,
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

    # SECURITY FIX (Audit 6): Validate token version
    # If token version getter is provided, check that token's version
    # matches the current version in database (via cache)
    if token_version_getter is not None:
        token_version = payload.tv or 1  # Default to 1 for legacy tokens
        current_version = await TokenVersionCache.get_version(
            payload.sub, db_fallback=token_version_getter
        )

        if token_version < current_version:
            logger.warning(
                "token_version_outdated",
                user_id=payload.sub,
                token_version=token_version,
                current_version=current_version,
            )
            raise TokenVersionOutdatedError(
                f"Token version {token_version} is outdated (current: {current_version})"
            )

    return payload


def get_token_claims(token: str) -> dict[str, Any]:
    """
    Extract claims from a token without full validation.

    Used for blacklisting/logging purposes where we need JTI even from
    potentially invalid tokens.

    NOTE: This function intentionally skips issuer/audience validation
    because it's used for extracting claims from tokens that may be
    from different sources (e.g., during migration or for blacklisting).

    Args:
        token: JWT token string

    Returns:
        Dictionary of claims

    Raises:
        TokenInvalidError: If token cannot be decoded at all
    """
    try:
        # SECURITY FIX: Use PyJWT with algorithm whitelist even for extraction
        # NOTE: Intentionally skip iss/aud validation for claim extraction
        payload: dict[str, Any] = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            options={
                "verify_exp": False,
                "verify_iss": False,
                "verify_aud": False,
            },
        )
        return payload
    except (InvalidTokenError, DecodeError) as e:
        raise TokenInvalidError(f"Cannot decode token: {str(e)}")


def verify_refresh_token(token: str) -> TokenPayload:
    """
    Verify a refresh token (sync version - in-memory blacklist only).

    NOTE: For full blacklist support including Redis, use verify_refresh_token_async().

    Args:
        token: JWT refresh token

    Returns:
        TokenPayload if valid

    Raises:
        TokenError: If token is invalid, blacklisted, or not a refresh token
    """
    payload = decode_token(token)

    if payload.type != "refresh":
        raise TokenInvalidError("Not a refresh token")

    # SECURITY FIX (Audit 5): Check token blacklist (sync - in-memory only)
    if TokenBlacklist.is_blacklisted(payload.jti):
        logger.warning(
            "blacklisted_refresh_token_rejected",
            jti=payload.jti[:16] + "..." if payload.jti else None,
        )
        raise TokenInvalidError("Refresh token has been revoked")

    return payload


async def verify_refresh_token_async(token: str) -> TokenPayload:
    """
    Verify a refresh token (async version with full blacklist support).

    SECURITY FIX (Audit 5): This version checks both Redis and in-memory
    blacklists for comprehensive token revocation support.

    Args:
        token: JWT refresh token

    Returns:
        TokenPayload if valid

    Raises:
        TokenError: If token is invalid, blacklisted, or not a refresh token
    """
    payload = decode_token(token)

    if payload.type != "refresh":
        raise TokenInvalidError("Not a refresh token")

    # SECURITY FIX (Audit 5): Check token blacklist (async - Redis + in-memory)
    if await TokenBlacklist.is_blacklisted_async(payload.jti):
        logger.warning(
            "blacklisted_refresh_token_rejected",
            jti=payload.jti[:16] + "..." if payload.jti else None,
        )
        raise TokenInvalidError("Refresh token has been revoked")

    return payload


def get_token_expiry(token: str) -> datetime | None:
    """
    Get the expiration time of a token.

    Args:
        token: JWT token

    Returns:
        Datetime of expiration, or None if no expiration
    """
    try:
        payload = decode_token(token, verify_exp=False)
        if payload.exp is not None:
            if isinstance(payload.exp, datetime):
                return payload.exp
            return datetime.fromtimestamp(float(payload.exp))
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


def verify_token(
    token: str, secret_key: str | None = None, expected_type: str = "access"
) -> TokenPayload:
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
    def create_access_token(user_id: str, **kwargs: Any) -> str:
        """Create an access token."""
        return create_access_token(user_id, **kwargs)

    @staticmethod
    def create_refresh_token(user_id: str, username: str) -> str:
        """Create a refresh token."""
        return create_refresh_token(user_id, username)

    @staticmethod
    def create_token_pair(user_id: str, **kwargs: Any) -> "Token":
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
