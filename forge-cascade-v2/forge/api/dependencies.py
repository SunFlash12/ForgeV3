"""
Forge Cascade V2 - FastAPI Dependencies
Dependency injection for API routes.

Provides:
- Database client injection
- Current user extraction from JWT
- Repository instances
- Kernel component access
- Immune system access
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, HTTPException, Request, status

if TYPE_CHECKING:
    from forge.api.app import ForgeApp
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from forge.config import Settings, get_settings
from forge.database.client import Neo4jClient
from forge.immune import (
    CanaryManager,
    CircuitBreakerRegistry,
    ForgeAnomalySystem,
    ForgeHealthChecker,
)
from forge.kernel.event_system import EventSystem
from forge.kernel.overlay_manager import OverlayManager
from forge.kernel.pipeline import CascadePipeline
from forge.models.base import TrustLevel
from forge.models.user import TokenPayload, User
from forge.repositories.audit_repository import AuditRepository
from forge.repositories.capsule_repository import CapsuleRepository
from forge.repositories.governance_repository import GovernanceRepository
from forge.repositories.graph_repository import GraphRepository
from forge.repositories.overlay_repository import OverlayRepository
from forge.repositories.session_repository import SessionRepository
from forge.repositories.temporal_repository import TemporalRepository
from forge.repositories.user_repository import UserRepository
from forge.security.auth_service import AuthService
from forge.security.authorization import (
    CapabilityAuthorizer,
    RoleAuthorizer,
    TrustAuthorizer,
)
from forge.security.session_binding import SessionBindingService
from forge.security.tokens import verify_token
from forge.services.embedding import EmbeddingService, get_embedding_service

# Security scheme
security = HTTPBearer(auto_error=False)


# =============================================================================
# Settings
# =============================================================================

def get_app_settings() -> Settings:
    """Get application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


# =============================================================================
# Forge App Access
# =============================================================================

def get_forge_app(request: Request) -> ForgeApp:
    """Get the ForgeApp instance from request state."""
    if not hasattr(request.app.state, 'forge'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forge application not initialized",
        )
    forge: ForgeApp = request.app.state.forge
    return forge


# =============================================================================
# Database
# =============================================================================

async def get_db_client(request: Request) -> Neo4jClient:
    """Get database client."""
    forge = get_forge_app(request)
    if not forge.db_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected",
        )
    return forge.db_client


DbClientDep = Annotated[Neo4jClient, Depends(get_db_client)]


# =============================================================================
# Repositories
# =============================================================================

async def get_capsule_repository(db: DbClientDep) -> CapsuleRepository:
    """Get capsule repository."""
    return CapsuleRepository(db)


async def get_user_repository(db: DbClientDep) -> UserRepository:
    """Get user repository."""
    return UserRepository(db)


async def get_governance_repository(db: DbClientDep) -> GovernanceRepository:
    """Get governance repository."""
    return GovernanceRepository(db)


async def get_overlay_repository(db: DbClientDep) -> OverlayRepository:
    """Get overlay repository."""
    return OverlayRepository(db)


async def get_audit_repository(db: DbClientDep) -> AuditRepository:
    """Get audit repository."""
    return AuditRepository(db)


async def get_graph_repository(db: DbClientDep) -> GraphRepository:
    """Get graph repository for graph algorithms and analysis."""
    return GraphRepository(db)


async def get_temporal_repository(db: DbClientDep) -> TemporalRepository:
    """Get temporal repository for version history and trust snapshots."""
    return TemporalRepository(db)


async def get_session_repository(db: DbClientDep) -> SessionRepository:
    """Get session repository for session tracking with IP/User-Agent binding."""
    return SessionRepository(db)


CapsuleRepoDep = Annotated[CapsuleRepository, Depends(get_capsule_repository)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
GovernanceRepoDep = Annotated[GovernanceRepository, Depends(get_governance_repository)]
OverlayRepoDep = Annotated[OverlayRepository, Depends(get_overlay_repository)]
AuditRepoDep = Annotated[AuditRepository, Depends(get_audit_repository)]
GraphRepoDep = Annotated[GraphRepository, Depends(get_graph_repository)]
TemporalRepoDep = Annotated[TemporalRepository, Depends(get_temporal_repository)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repository)]


# =============================================================================
# Services
# =============================================================================

def get_embedding_svc() -> EmbeddingService:
    """Get embedding service."""
    return get_embedding_service()


EmbeddingServiceDep = Annotated[EmbeddingService, Depends(get_embedding_svc)]


# =============================================================================
# Kernel Components
# =============================================================================

async def get_event_system(request: Request) -> EventSystem:
    """Get event system."""
    forge = get_forge_app(request)
    if not forge.event_system:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event system not initialized",
        )
    return forge.event_system


async def get_overlay_manager(request: Request) -> OverlayManager:
    """Get overlay manager."""
    forge = get_forge_app(request)
    if not forge.overlay_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Overlay manager not initialized",
        )
    return forge.overlay_manager


async def get_pipeline(request: Request) -> CascadePipeline:
    """Get cascade pipeline."""
    forge = get_forge_app(request)
    if not forge.pipeline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pipeline not initialized",
        )
    return forge.pipeline


EventSystemDep = Annotated[EventSystem, Depends(get_event_system)]
OverlayManagerDep = Annotated[OverlayManager, Depends(get_overlay_manager)]
PipelineDep = Annotated[CascadePipeline, Depends(get_pipeline)]


# =============================================================================
# Immune System
# =============================================================================

async def get_circuit_registry(request: Request) -> CircuitBreakerRegistry:
    """Get circuit breaker registry."""
    forge = get_forge_app(request)
    circuit_registry: CircuitBreakerRegistry | None = forge.circuit_registry
    if circuit_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Circuit breaker registry not initialized",
        )
    return circuit_registry


async def get_health_checker(request: Request) -> ForgeHealthChecker:
    """Get health checker."""
    forge = get_forge_app(request)
    health_checker: ForgeHealthChecker | None = forge.health_checker
    if health_checker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health checker not initialized",
        )
    return health_checker


async def get_anomaly_system(request: Request) -> ForgeAnomalySystem:
    """Get anomaly detection system."""
    forge = get_forge_app(request)
    anomaly_system: ForgeAnomalySystem | None = forge.anomaly_system
    if anomaly_system is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly detection system not initialized",
        )
    return anomaly_system


async def get_canary_manager(request: Request) -> CanaryManager[dict[str, Any]]:
    """Get canary deployment manager."""
    forge = get_forge_app(request)
    canary_manager: CanaryManager[dict[str, Any]] | None = forge.canary_manager
    if canary_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Canary deployment manager not initialized",
        )
    return canary_manager


CircuitRegistryDep = Annotated[CircuitBreakerRegistry, Depends(get_circuit_registry)]
HealthCheckerDep = Annotated[ForgeHealthChecker, Depends(get_health_checker)]
AnomalySystemDep = Annotated[ForgeAnomalySystem, Depends(get_anomaly_system)]
CanaryManagerDep = Annotated["CanaryManager[dict[str, Any]]", Depends(get_canary_manager)]


# =============================================================================
# Authentication
# =============================================================================

async def get_token_payload(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    settings: SettingsDep,
) -> TokenPayload | None:
    """
    Extract and verify token payload from cookie or Authorization header.

    Tries cookie first (more secure), then falls back to Authorization header
    for backwards compatibility and API clients.
    """
    from forge.security.tokens import TokenBlacklist

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

    try:
        payload = verify_token(token, settings.jwt_secret_key)

        # Check if token is blacklisted (logout) - async for Redis support
        if payload and payload.jti:
            if await TokenBlacklist.is_blacklisted_async(payload.jti):
                return None

        return payload
    except (ValueError, KeyError, OSError, RuntimeError):
        return None


async def get_current_user_optional(
    token: Annotated[TokenPayload | None, Depends(get_token_payload)],
    user_repo: UserRepoDep,
) -> User | None:
    """
    Get current user if authenticated, None otherwise.

    SECURITY FIX (Audit 6): Validates token version to ensure tokens
    are invalidated immediately when user privileges change.
    """
    import structlog
    logger = structlog.get_logger(__name__)

    if not token:
        return None

    try:
        user = await user_repo.get_by_id(token.sub)
        if not user:
            return None

        # SECURITY FIX (Audit 6): Validate token version
        # If user's token_version is higher than the token's version,
        # the token was issued before a privilege change and is invalid
        token_version = token.tv or 1  # Default to 1 for legacy tokens
        current_version = await user_repo.get_token_version(token.sub)

        if token_version < current_version:
            logger.warning(
                "token_version_outdated",
                user_id=token.sub,
                token_version=token_version,
                current_version=current_version,
            )
            return None

        return user
    except ValueError:
        # User not found - this is expected for deleted/invalid users
        return None
    except (KeyError, TypeError, OSError, RuntimeError) as e:
        # Log unexpected errors but don't expose them to avoid info leakage
        # This prevents silent failures that could mask database issues
        logger.warning(
            "user_lookup_failed",
            user_id=token.sub,
            error_type=type(e).__name__,
            error=str(e)[:100],  # Truncate to avoid log spam
        )
        return None


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Require authenticated user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require authenticated and active user."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return user


OptionalUserDep = Annotated[User | None, Depends(get_current_user_optional)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
ActiveUserDep = Annotated[User, Depends(get_current_active_user)]


# =============================================================================
# Authorization
# =============================================================================

def require_trust_level(min_level: TrustLevel) -> Callable[[ActiveUserDep], Coroutine[object, object, User]]:
    """Dependency factory to require minimum trust level."""
    async def dependency(user: ActiveUserDep) -> User:
        authorizer = TrustAuthorizer(min_level)
        if not authorizer.authorize(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires trust level {min_level.name} or higher",
            )
        return user
    return dependency


def require_roles(*roles: str) -> Callable[[ActiveUserDep], Coroutine[object, object, User]]:
    """Dependency factory to require specific roles."""
    async def dependency(user: ActiveUserDep) -> User:
        authorizer = RoleAuthorizer(set(roles))
        if not authorizer.authorize(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user
    return dependency


def require_capabilities(*capabilities: str) -> Callable[[ActiveUserDep], Coroutine[object, object, User]]:
    """Dependency factory to require specific capabilities."""
    async def dependency(user: ActiveUserDep) -> User:
        from forge.models.overlay import Capability
        caps = {Capability(c) for c in capabilities}
        authorizer = CapabilityAuthorizer(caps)
        if not authorizer.authorize(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires capabilities: {', '.join(capabilities)}",
            )
        return user
    return dependency


# Convenience typed dependencies for common trust levels
SandboxUserDep = Annotated[User, Depends(require_trust_level(TrustLevel.SANDBOX))]
StandardUserDep = Annotated[User, Depends(require_trust_level(TrustLevel.STANDARD))]
TrustedUserDep = Annotated[User, Depends(require_trust_level(TrustLevel.TRUSTED))]
CoreUserDep = Annotated[User, Depends(require_trust_level(TrustLevel.CORE))]

# Role-based dependencies
AdminUserDep = Annotated[User, Depends(require_roles("admin"))]
ModeratorUserDep = Annotated[User, Depends(require_roles("admin", "moderator"))]


# =============================================================================
# Services
# =============================================================================

async def get_auth_service(
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
) -> AuthService:
    """Get authentication service."""
    return AuthService(user_repo, audit_repo)


async def get_session_service(
    session_repo: SessionRepoDep,
) -> SessionBindingService:
    """Get session binding service for IP/User-Agent tracking."""
    return SessionBindingService(session_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
SessionServiceDep = Annotated[SessionBindingService, Depends(get_session_service)]


# =============================================================================
# Pagination
# =============================================================================

class PaginationParams:
    """Standard pagination parameters."""

    # SECURITY FIX (Audit 6): Upper bound on page to prevent DoS via huge SKIP values
    MAX_PAGE = 10000

    def __init__(
        self,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100,
    ):
        # Bound page between 1 and MAX_PAGE to prevent expensive DB queries
        self.page = max(1, min(page, self.MAX_PAGE))
        self.per_page = min(max(1, per_page), max_per_page)
        self.offset = (self.page - 1) * self.per_page


def get_pagination(
    page: int = 1,
    per_page: int | None = None,
    page_size: int | None = None,  # Alias for per_page (frontend compatibility)
) -> PaginationParams:
    """Get pagination parameters from query.

    Accepts both per_page and page_size for frontend compatibility.
    page_size takes precedence if both are provided.
    """
    # Use page_size if provided, otherwise per_page, otherwise default to 20
    size = page_size if page_size is not None else (per_page if per_page is not None else 20)
    return PaginationParams(page=page, per_page=size)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination)]


# =============================================================================
# Request Context
# =============================================================================

async def get_correlation_id(request: Request) -> str:
    """Get request correlation ID."""
    return getattr(request.state, 'correlation_id', 'unknown')


CorrelationIdDep = Annotated[str, Depends(get_correlation_id)]


class ClientInfo:
    """Client information extracted from request."""

    def __init__(self, ip_address: str, user_agent: str | None):
        self.ip_address = ip_address
        self.user_agent = user_agent


# SECURITY FIX: Get trusted proxy ranges from settings/environment
# Default ranges cover Docker internal networks, localhost, common load balancers
import os as _os

_DEFAULT_PROXY_RANGES = "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.0.0/16"
TRUSTED_PROXY_RANGES = _os.getenv("TRUSTED_PROXY_RANGES", _DEFAULT_PROXY_RANGES).split(",")


def _is_valid_ip(ip: str) -> bool:
    """Validate IP address format."""
    if not ip:
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _is_trusted_proxy(ip: str) -> bool:
    """Check if IP is from a trusted proxy."""
    if not _is_valid_ip(ip):
        return False
    try:
        client_ip = ipaddress.ip_address(ip)
        for range_str in TRUSTED_PROXY_RANGES:
            if client_ip in ipaddress.ip_network(range_str, strict=False):
                return True
        return False
    except ValueError:
        return False


def _get_real_client_ip(request: Request) -> str:
    """
    Securely extract real client IP from request.

    Only trusts X-Forwarded-For and X-Real-IP when the direct client
    is a trusted proxy. Otherwise, uses the direct client IP.
    """
    # Get direct client IP
    direct_ip = request.client.host if request.client else None

    # If direct IP is not from a trusted proxy, use it directly
    # (don't trust forwarded headers from untrusted sources)
    if direct_ip and not _is_trusted_proxy(direct_ip):
        return direct_ip if _is_valid_ip(direct_ip) else "unknown"

    # Direct connection is from trusted proxy - check forwarded headers
    # Priority: X-Forwarded-For > X-Real-IP > direct connection

    forwarded_for: str | None = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2...
        # The first non-proxy IP (from the right) is the real client
        ips: list[str] = [ip.strip() for ip in forwarded_for.split(",")]

        # Walk from right to left, find the first IP that's not a trusted proxy
        for ip in reversed(ips):
            if _is_valid_ip(ip) and not _is_trusted_proxy(ip):
                return ip

        # If all are proxies, take the leftmost (original client)
        if ips and _is_valid_ip(ips[0]):
            return ips[0]

    # Check X-Real-IP header
    real_ip: str | None = request.headers.get("X-Real-IP")
    if real_ip and _is_valid_ip(real_ip):
        return real_ip

    # Fall back to direct connection
    return direct_ip if direct_ip and _is_valid_ip(direct_ip) else "unknown"


async def get_client_info(request: Request) -> ClientInfo:
    """
    Extract client IP and user agent from request.

    SECURITY: Only trusts proxy headers (X-Forwarded-For, X-Real-IP)
    when the direct connection is from a trusted proxy IP range.
    This prevents IP spoofing from untrusted clients.
    """
    ip_address = _get_real_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    return ClientInfo(ip_address=ip_address, user_agent=user_agent)


ClientInfoDep = Annotated[ClientInfo, Depends(get_client_info)]


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Settings
    "SettingsDep",
    "get_app_settings",

    # Database
    "DbClientDep",
    "get_db_client",

    # Repositories
    "CapsuleRepoDep",
    "UserRepoDep",
    "GovernanceRepoDep",
    "OverlayRepoDep",
    "AuditRepoDep",
    "GraphRepoDep",
    "TemporalRepoDep",
    "SessionRepoDep",

    # Kernel
    "EventSystemDep",
    "OverlayManagerDep",
    "PipelineDep",

    # Immune
    "CircuitRegistryDep",
    "HealthCheckerDep",
    "AnomalySystemDep",
    "CanaryManagerDep",

    # Auth
    "OptionalUserDep",
    "CurrentUserDep",
    "ActiveUserDep",

    # Authorization
    "SandboxUserDep",
    "StandardUserDep",
    "TrustedUserDep",
    "CoreUserDep",
    "AdminUserDep",
    "ModeratorUserDep",
    "require_trust_level",
    "require_roles",
    "require_capabilities",

    # Services
    "AuthServiceDep",
    "SessionServiceDep",

    # Pagination
    "PaginationParams",
    "PaginationDep",

    # Context
    "CorrelationIdDep",
    "ClientInfo",
    "ClientInfoDep",
]
