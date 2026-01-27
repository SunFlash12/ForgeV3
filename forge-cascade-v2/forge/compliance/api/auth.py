"""
Forge Compliance Framework - Authentication

JWT-based authentication for the compliance API.
Standalone authentication that doesn't depend on the main Forge API.

SECURITY FIX (Audit 4): Added token blacklist support to prevent use of
revoked tokens. Uses Redis when available for distributed deployments.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Security scheme - auto_error=False to allow custom error handling
security = HTTPBearer(auto_error=False)

# Try to import redis for distributed blacklist
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore
    REDIS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════


class ComplianceTokenBlacklist:
    """
    Token blacklist for the compliance API.

    SECURITY FIX (Audit 4): Prevents use of revoked tokens in the compliance API.
    Uses Redis when available for distributed deployments across multiple API
    instances. Falls back to in-memory storage when Redis is unavailable.

    This is compatible with the main Forge API's TokenBlacklist - they share
    the same Redis prefix so tokens revoked in either system are rejected by both.
    """

    _MAX_BLACKLIST_SIZE: int = 50000  # Max in-memory entries
    _blacklist: set[str] = set()
    _expiry_times: dict[str, float] = {}
    _last_cleanup: float = 0
    _cleanup_interval: float = 300  # 5 minutes

    _redis_client: Any | None = None
    _redis_initialized: bool = False
    # Same prefix as main Forge API for cross-system compatibility
    _redis_prefix: str = "forge:token:blacklist:"

    @classmethod
    async def initialize(cls, redis_url: str | None = None) -> bool:
        """Initialize Redis connection for distributed blacklist."""
        if cls._redis_initialized:
            return cls._redis_client is not None

        if not REDIS_AVAILABLE:
            logger.warning("compliance_token_blacklist_redis_unavailable")
            cls._redis_initialized = True
            return False

        url = redis_url or os.getenv("REDIS_URL") or os.getenv("COMPLIANCE_REDIS_URL")
        if not url:
            logger.info("compliance_token_blacklist_memory_mode")
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
            await cls._redis_client.ping()
            cls._redis_initialized = True
            logger.info("compliance_token_blacklist_redis_connected")
            return True
        except Exception as e:
            logger.warning(f"compliance_token_blacklist_redis_failed: {e}")
            cls._redis_client = None
            cls._redis_initialized = True
            return False

    @classmethod
    async def is_blacklisted(cls, jti: str | None) -> bool:
        """Check if a token JTI is blacklisted."""
        if not jti:
            return False

        # Try Redis first (shared with main Forge API)
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                result = await cls._redis_client.exists(key)
                return bool(result)
            except Exception as e:
                logger.warning(f"compliance_token_blacklist_redis_error: {e}")
                # Fall through to in-memory

        # In-memory fallback
        cls._maybe_cleanup()
        return jti in cls._blacklist

    @classmethod
    async def add(cls, jti: str, expires_at: float | None = None) -> None:
        """Add a token JTI to the blacklist."""
        if not jti:
            return

        ttl = None
        if expires_at:
            ttl = int(expires_at - time.time())
            if ttl <= 0:
                return  # Already expired

        # Try Redis first
        if cls._redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                if ttl:
                    await cls._redis_client.setex(key, ttl, "1")
                else:
                    await cls._redis_client.setex(key, 86400, "1")  # 24h default
                logger.debug(f"compliance_token_blacklisted_redis: {jti[:16]}...")
                return
            except Exception as e:
                logger.warning(f"compliance_token_blacklist_redis_error: {e}")

        # In-memory fallback
        cls._blacklist.add(jti)
        if expires_at:
            cls._expiry_times[jti] = expires_at
        cls._maybe_cleanup()
        cls._evict_if_needed()
        logger.debug(f"compliance_token_blacklisted_memory: {jti[:16]}...")

    @classmethod
    def _maybe_cleanup(cls) -> None:
        """Remove expired entries from in-memory blacklist."""
        now = time.time()
        if now - cls._last_cleanup < cls._cleanup_interval:
            return

        cls._last_cleanup = now
        expired = [jti for jti, exp in cls._expiry_times.items() if exp < now]
        for jti in expired:
            cls._blacklist.discard(jti)
            cls._expiry_times.pop(jti, None)

    @classmethod
    def _evict_if_needed(cls) -> None:
        """Evict oldest entries if blacklist exceeds max size."""
        if len(cls._blacklist) <= cls._MAX_BLACKLIST_SIZE:
            return

        # Remove 10% of oldest entries
        to_remove = list(cls._expiry_times.keys())[: len(cls._blacklist) // 10]
        for jti in to_remove:
            cls._blacklist.discard(jti)
            cls._expiry_times.pop(jti, None)

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


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # User ID
    exp: datetime
    iat: datetime
    jti: str | None = None
    roles: list[str] = []
    permissions: list[str] = []


class ComplianceUser(BaseModel):
    """Authenticated user context for compliance operations."""

    id: str
    roles: list[str] = []
    permissions: list[str] = []
    is_admin: bool = False
    is_compliance_officer: bool = False


@lru_cache
def get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    secret = os.getenv("COMPLIANCE_JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise ValueError(
            "JWT secret not configured. Set COMPLIANCE_JWT_SECRET or JWT_SECRET_KEY environment variable."
        )
    return secret


def decode_token(token: str) -> TokenPayload | None:
    """
    Decode a JWT token without blacklist check.

    Use verify_token_async() for full verification including blacklist.
    """
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"]},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


async def verify_token_async(token: str) -> TokenPayload | None:
    """
    Verify and decode a JWT token with blacklist check.

    SECURITY FIX (Audit 4): Now checks token blacklist to prevent use of
    revoked tokens. Uses shared Redis prefix for cross-system compatibility.
    """
    payload = decode_token(token)
    if not payload:
        return None

    # SECURITY FIX: Check token blacklist
    if payload.jti and await ComplianceTokenBlacklist.is_blacklisted(payload.jti):
        logger.warning(f"compliance_blacklisted_token_rejected: jti={payload.jti[:8]}...")
        return None

    return payload


def verify_token(token: str) -> TokenPayload | None:
    """
    Verify and decode a JWT token (sync version - no blacklist check).

    DEPRECATED: Use verify_token_async() for full security including blacklist.
    This sync version is kept for backwards compatibility but does not check
    the token blacklist. Use verify_token_async() in async contexts.
    """
    return decode_token(token)


async def get_token_payload(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> TokenPayload | None:
    """
    Extract and verify token payload from cookie or Authorization header.

    SECURITY FIX (Audit 4): Now uses async verification with blacklist check.
    """
    token = None

    # Priority 1: Check httpOnly cookie
    access_token_cookie = request.cookies.get("access_token")
    if access_token_cookie:
        token = access_token_cookie

    # Priority 2: Fall back to Authorization header
    if not token and credentials:
        token = credentials.credentials

    if not token:
        return None

    # SECURITY FIX: Use async verification with blacklist check
    return await verify_token_async(token)


async def get_current_user_optional(
    token: Annotated[TokenPayload | None, Depends(get_token_payload)],
) -> ComplianceUser | None:
    """Get current user if authenticated, None otherwise."""
    if not token:
        return None

    return ComplianceUser(
        id=token.sub,
        roles=token.roles,
        permissions=token.permissions,
        is_admin="admin" in token.roles,
        is_compliance_officer="compliance_officer" in token.roles or "admin" in token.roles,
    )


async def get_current_user(
    user: Annotated[ComplianceUser | None, Depends(get_current_user_optional)],
) -> ComplianceUser:
    """Require authenticated user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_compliance_officer(
    user: Annotated[ComplianceUser, Depends(get_current_user)],
) -> ComplianceUser:
    """Require user to be a compliance officer or admin."""
    if not user.is_compliance_officer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compliance officer role required",
        )
    return user


async def require_admin(
    user: Annotated[ComplianceUser, Depends(get_current_user)],
) -> ComplianceUser:
    """Require user to be an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


# Type aliases for use in routes
OptionalUserDep = Annotated[ComplianceUser | None, Depends(get_current_user_optional)]
CurrentUserDep = Annotated[ComplianceUser, Depends(get_current_user)]
ComplianceOfficerDep = Annotated[ComplianceUser, Depends(require_compliance_officer)]
AdminUserDep = Annotated[ComplianceUser, Depends(require_admin)]


def require_permission(permission_name: str, resource_type: str | None = None):
    """
    Dependency factory to require a specific permission.

    Uses the AccessControlService for fine-grained access control.
    """
    from forge.compliance.security.access_control import (
        Permission,
        ResourceType,
        get_access_control_service,
    )

    async def dependency(user: CurrentUserDep) -> ComplianceUser:
        access_control = get_access_control_service()

        try:
            perm = Permission(permission_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown permission: {permission_name}",
            )

        res_type = None
        if resource_type:
            try:
                res_type = ResourceType(resource_type)
            except ValueError:
                pass

        decision = access_control.check_access(
            user_id=user.id,
            permission=perm,
            resource_type=res_type or ResourceType.SYSTEM_CONFIG,
        )

        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.reason,
            )

        return user

    return dependency


__all__ = [
    # Token blacklist
    "ComplianceTokenBlacklist",
    # Models
    "TokenPayload",
    "ComplianceUser",
    # Token verification
    "decode_token",
    "verify_token",
    "verify_token_async",
    # Dependencies
    "get_token_payload",
    "get_current_user_optional",
    "get_current_user",
    "require_compliance_officer",
    "require_admin",
    "require_permission",
    # Type aliases
    "OptionalUserDep",
    "CurrentUserDep",
    "ComplianceOfficerDep",
    "AdminUserDep",
]
