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

from functools import lru_cache
from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from forge.config import Settings, get_settings
from forge.database.client import Neo4jClient
from forge.kernel.event_system import EventSystem
from forge.kernel.overlay_manager import OverlayManager
from forge.kernel.pipeline import CascadePipeline
from forge.models.user import User, TrustLevel
from forge.repositories.capsule_repository import CapsuleRepository
from forge.repositories.user_repository import UserRepository
from forge.repositories.governance_repository import GovernanceRepository
from forge.repositories.overlay_repository import OverlayRepository
from forge.repositories.audit_repository import AuditRepository
from forge.repositories.graph_repository import GraphRepository
from forge.repositories.temporal_repository import TemporalRepository
from forge.security.tokens import verify_token, TokenPayload
from forge.security.authorization import (
    TrustAuthorizer,
    RoleAuthorizer,
    CapabilityAuthorizer,
)
from forge.security.auth_service import AuthService
from forge.immune import (
    CircuitBreakerRegistry,
    ForgeHealthChecker,
    ForgeAnomalySystem,
    CanaryManager,
)
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

def get_forge_app(request: Request):
    """Get the ForgeApp instance from request state."""
    if not hasattr(request.app.state, 'forge'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forge application not initialized",
        )
    return request.app.state.forge


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


CapsuleRepoDep = Annotated[CapsuleRepository, Depends(get_capsule_repository)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
GovernanceRepoDep = Annotated[GovernanceRepository, Depends(get_governance_repository)]
OverlayRepoDep = Annotated[OverlayRepository, Depends(get_overlay_repository)]
AuditRepoDep = Annotated[AuditRepository, Depends(get_audit_repository)]
GraphRepoDep = Annotated[GraphRepository, Depends(get_graph_repository)]
TemporalRepoDep = Annotated[TemporalRepository, Depends(get_temporal_repository)]


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
    return forge.circuit_registry


async def get_health_checker(request: Request) -> ForgeHealthChecker:
    """Get health checker."""
    forge = get_forge_app(request)
    return forge.health_checker


async def get_anomaly_system(request: Request) -> ForgeAnomalySystem:
    """Get anomaly detection system."""
    forge = get_forge_app(request)
    return forge.anomaly_system


async def get_canary_manager(request: Request) -> CanaryManager:
    """Get canary deployment manager."""
    forge = get_forge_app(request)
    return forge.canary_manager


CircuitRegistryDep = Annotated[CircuitBreakerRegistry, Depends(get_circuit_registry)]
HealthCheckerDep = Annotated[ForgeHealthChecker, Depends(get_health_checker)]
AnomalySystemDep = Annotated[ForgeAnomalySystem, Depends(get_anomaly_system)]
CanaryManagerDep = Annotated[CanaryManager, Depends(get_canary_manager)]


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
    except Exception:
        return None


async def get_current_user_optional(
    token: Annotated[TokenPayload | None, Depends(get_token_payload)],
    user_repo: UserRepoDep,
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    if not token:
        return None
    
    try:
        user = await user_repo.get_by_id(token.sub)
        return user
    except Exception:
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

def require_trust_level(min_level: TrustLevel):
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


def require_roles(*roles: str):
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


def require_capabilities(*capabilities: str):
    """Dependency factory to require specific capabilities."""
    async def dependency(user: ActiveUserDep) -> User:
        from forge.models.user import Capability
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


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# =============================================================================
# Pagination
# =============================================================================

class PaginationParams:
    """Standard pagination parameters."""
    
    def __init__(
        self,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100,
    ):
        self.page = max(1, page)
        self.per_page = min(max(1, per_page), max_per_page)
        self.offset = (self.page - 1) * self.per_page


def get_pagination(
    page: int = 1,
    per_page: int = 20,
) -> PaginationParams:
    """Get pagination parameters from query."""
    return PaginationParams(page=page, per_page=per_page)


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


async def get_client_info(request: Request) -> ClientInfo:
    """Extract client IP and user agent from request."""
    # Get IP from various headers (proxy-aware)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            ip_address = real_ip
        elif request.client:
            ip_address = request.client.host
        else:
            ip_address = "unknown"

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
    
    # Pagination
    "PaginationParams",
    "PaginationDep",
    
    # Context
    "CorrelationIdDep",
    "ClientInfo",
    "ClientInfoDep",
]
