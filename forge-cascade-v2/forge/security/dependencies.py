"""
FastAPI Security Dependencies for Forge Cascade V2

Provides dependency injection for authentication and authorization
in FastAPI route handlers.
"""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..models.base import TrustLevel
from ..models.user import UserRole
from ..models.overlay import Capability
from .tokens import (
    verify_access_token,
    extract_token_from_header,
    TokenError,
    TokenExpiredError,
    TokenInvalidError
)
from .authorization import (
    AuthorizationContext,
    create_auth_context,
    check_trust_level,
    check_role,
    check_capability
)


# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> Optional[str]:
    """Extract bearer token from request."""
    if credentials is None:
        return None
    return credentials.credentials


async def get_optional_auth_context(
    token: Annotated[Optional[str], Depends(get_token)]
) -> Optional[AuthorizationContext]:
    """
    Get authorization context if token is present.
    
    Returns None if no token provided (for public endpoints).
    """
    if not token:
        return None
    
    try:
        payload = verify_access_token(token)
        return create_auth_context(
            user_id=payload.sub,
            trust_flame=payload.trust_flame or 60,
            role=payload.role or "user"
        )
    except TokenError:
        return None


async def get_auth_context(
    token: Annotated[Optional[str], Depends(get_token)]
) -> AuthorizationContext:
    """
    Get authorization context from token (required).
    
    Raises HTTPException if not authenticated.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        payload = verify_access_token(token)
        return create_auth_context(
            user_id=payload.sub,
            trust_flame=payload.trust_flame or 60,
            role=payload.role or "user"
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except TokenInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_id(
    auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
) -> str:
    """Get current authenticated user's ID."""
    return auth.user_id


# Type aliases for cleaner route signatures
AuthContext = Annotated[AuthorizationContext, Depends(get_auth_context)]
OptionalAuthContext = Annotated[Optional[AuthorizationContext], Depends(get_optional_auth_context)]
CurrentUserId = Annotated[str, Depends(get_current_user_id)]


# =============================================================================
# Trust Level Dependencies
# =============================================================================

def require_trust(required_level: TrustLevel):
    """
    Create dependency that requires minimum trust level.
    
    Usage:
        @app.post("/proposals")
        async def create_proposal(
            auth: AuthContext,
            _: Depends(require_trust(TrustLevel.TRUSTED))
        ):
            ...
    """
    async def dependency(
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> AuthorizationContext:
        if not auth.has_trust(required_level):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_level.name} trust level"
            )
        return auth
    
    return dependency


# Pre-built trust level dependencies
RequireSandboxTrust = Annotated[AuthorizationContext, Depends(require_trust(TrustLevel.SANDBOX))]
RequireStandardTrust = Annotated[AuthorizationContext, Depends(require_trust(TrustLevel.STANDARD))]
RequireTrustedTrust = Annotated[AuthorizationContext, Depends(require_trust(TrustLevel.TRUSTED))]
RequireCoreTrust = Annotated[AuthorizationContext, Depends(require_trust(TrustLevel.CORE))]


# =============================================================================
# Role Dependencies
# =============================================================================

def require_role_dep(required_role: UserRole):
    """
    Create dependency that requires minimum role.
    
    Usage:
        @app.delete("/users/{user_id}")
        async def delete_user(
            auth: AuthContext,
            _: Depends(require_role_dep(UserRole.ADMIN))
        ):
            ...
    """
    async def dependency(
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> AuthorizationContext:
        if not auth.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role.value} role"
            )
        return auth
    
    return dependency


# Pre-built role dependencies
RequireModerator = Annotated[AuthorizationContext, Depends(require_role_dep(UserRole.MODERATOR))]
RequireAdmin = Annotated[AuthorizationContext, Depends(require_role_dep(UserRole.ADMIN))]
RequireSystem = Annotated[AuthorizationContext, Depends(require_role_dep(UserRole.SYSTEM))]


# =============================================================================
# Capability Dependencies
# =============================================================================

def require_capability_dep(required_capability: Capability):
    """
    Create dependency that requires a specific capability.
    
    Usage:
        @app.post("/overlays/{overlay_id}/execute")
        async def execute_overlay(
            auth: AuthContext,
            _: Depends(require_capability_dep(Capability.OVERLAY_EXECUTE))
        ):
            ...
    """
    async def dependency(
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> AuthorizationContext:
        if not auth.has_capability(required_capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_capability.value} capability"
            )
        return auth
    
    return dependency


def require_any_capability_dep(*capabilities: Capability):
    """
    Create dependency that requires ANY of the specified capabilities.
    """
    async def dependency(
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> AuthorizationContext:
        if not auth.has_any_capability(set(capabilities)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[c.value for c in capabilities]}"
            )
        return auth
    
    return dependency


def require_all_capabilities_dep(*capabilities: Capability):
    """
    Create dependency that requires ALL of the specified capabilities.
    """
    async def dependency(
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> AuthorizationContext:
        if not auth.has_all_capabilities(set(capabilities)):
            missing = set(capabilities) - auth.capabilities
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing capabilities: {[c.value for c in missing]}"
            )
        return auth
    
    return dependency


# =============================================================================
# Resource Access Dependencies
# =============================================================================

class ResourceAccessChecker:
    """
    Dependency factory for resource access checks.
    
    Usage:
        async def get_capsule(capsule_id: str) -> Capsule: ...
        
        @app.get("/capsules/{capsule_id}")
        async def read_capsule(
            capsule_id: str,
            auth: AuthContext,
            capsule: Capsule = Depends(get_capsule),
            _: bool = Depends(ResourceAccessChecker(
                get_owner_id=lambda c: c.owner_id,
                get_trust_level=lambda c: c.trust_level
            ))
        ):
            ...
    """
    
    def __init__(
        self,
        get_owner_id: callable,
        get_trust_level: callable = None,
        require_ownership: bool = False
    ):
        self.get_owner_id = get_owner_id
        self.get_trust_level = get_trust_level
        self.require_ownership = require_ownership
    
    async def __call__(
        self,
        resource: any,
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
    ) -> bool:
        owner_id = self.get_owner_id(resource)
        
        # If ownership is required, check that
        if self.require_ownership:
            if auth.user_id != owner_id and not auth.has_role(UserRole.ADMIN):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't own this resource"
                )
            return True
        
        # Otherwise check if user can access based on trust level
        trust_level = TrustLevel.STANDARD
        if self.get_trust_level:
            trust_level = self.get_trust_level(resource)
        
        if not auth.can_access_resource(trust_level, owner_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient access rights"
            )
        
        return True


# =============================================================================
# Request Info Extraction
# =============================================================================

async def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request."""
    # Check for forwarded headers (behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Direct connection
    if request.client:
        return request.client.host
    
    return None


async def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


# Type aliases
ClientIP = Annotated[Optional[str], Depends(get_client_ip)]
UserAgent = Annotated[Optional[str], Depends(get_user_agent)]


# =============================================================================
# Composite Dependencies
# =============================================================================

class AuthenticatedRequest:
    """
    Composite dependency that provides full request context.
    
    Usage:
        @app.post("/capsules")
        async def create_capsule(
            data: CapsuleCreate,
            ctx: AuthenticatedRequest = Depends()
        ):
            print(f"User {ctx.user_id} from {ctx.ip_address}")
    """
    
    def __init__(
        self,
        auth: Annotated[AuthorizationContext, Depends(get_auth_context)],
        ip_address: Annotated[Optional[str], Depends(get_client_ip)],
        user_agent: Annotated[Optional[str], Depends(get_user_agent)]
    ):
        self.auth = auth
        self.user_id = auth.user_id
        self.trust_flame = auth.trust_flame
        self.trust_level = auth.trust_level
        self.role = auth.role
        self.capabilities = auth.capabilities
        self.ip_address = ip_address
        self.user_agent = user_agent
    
    def has_trust(self, required: TrustLevel) -> bool:
        return self.auth.has_trust(required)
    
    def has_role(self, required: UserRole) -> bool:
        return self.auth.has_role(required)
    
    def has_capability(self, required: Capability) -> bool:
        return self.auth.has_capability(required)
    
    def can_access_resource(
        self,
        resource_trust_level: TrustLevel,
        resource_owner_id: Optional[str] = None
    ) -> bool:
        return self.auth.can_access_resource(resource_trust_level, resource_owner_id)
    
    def can_modify_resource(
        self,
        resource_owner_id: str,
        resource_trust_level: TrustLevel = TrustLevel.STANDARD
    ) -> bool:
        return self.auth.can_modify_resource(resource_owner_id, resource_trust_level)
