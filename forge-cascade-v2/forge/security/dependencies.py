"""
FastAPI Security Dependencies for Forge Cascade V2

Provides dependency injection for authentication and authorization
in FastAPI route handlers.
"""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..models.base import TrustLevel
from ..models.overlay import Capability
from ..models.user import UserRole
from .authorization import (
    AuthorizationContext,
    create_auth_context,
)
from .tokens import (
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    verify_access_token,
)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
) -> str | None:
    """Extract bearer token from request."""
    if credentials is None:
        return None
    return credentials.credentials


async def get_optional_auth_context(
    token: Annotated[str | None, Depends(get_token)]
) -> AuthorizationContext | None:
    """
    Get authorization context if token is present.

    Returns None if no token provided (for public endpoints).

    SECURITY FIX (Audit 4 - H1): Reject tokens with missing required claims
    instead of defaulting to STANDARD trust. This prevents privilege escalation
    from malformed or tampered tokens.
    """
    if not token:
        return None

    try:
        payload = verify_access_token(token)

        # SECURITY FIX: Reject tokens missing required claims
        # Do NOT use default values - this prevents privilege escalation
        if payload.trust_flame is None or payload.role is None:
            import logging
            logging.getLogger(__name__).warning(
                "token_missing_claims: trust_flame or role claim missing"
            )
            return None

        return create_auth_context(
            user_id=payload.sub,
            trust_flame=payload.trust_flame,
            role=payload.role
        )
    except TokenError:
        return None


async def get_auth_context(
    token: Annotated[str | None, Depends(get_token)]
) -> AuthorizationContext:
    """
    Get authorization context from token (required).

    Raises HTTPException if not authenticated.

    SECURITY FIX (Audit 4 - H1): Reject tokens with missing required claims
    instead of defaulting to STANDARD trust. This prevents privilege escalation
    from malformed or tampered tokens.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = verify_access_token(token)

        # SECURITY FIX: Reject tokens missing required claims
        # Do NOT use default values - this prevents privilege escalation
        if payload.trust_flame is None:
            raise TokenInvalidError("Token missing required trust_flame claim")
        if payload.role is None:
            raise TokenInvalidError("Token missing required role claim")

        return create_auth_context(
            user_id=payload.sub,
            trust_flame=payload.trust_flame,
            role=payload.role
        )
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except TokenInvalidError as e:
        # SECURITY FIX (Audit 3): Generic message to prevent token format leakage
        import logging
        logging.getLogger(__name__).warning(f"token_validation_failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_id(
    auth: Annotated[AuthorizationContext, Depends(get_auth_context)]
) -> str:
    """Get current authenticated user's ID."""
    return auth.user_id


# Type aliases for cleaner route signatures
AuthContext = Annotated[AuthorizationContext, Depends(get_auth_context)]
OptionalAuthContext = Annotated[AuthorizationContext | None, Depends(get_optional_auth_context)]
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
        resource: Any,
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

# SECURITY FIX (Audit 4 - M7): Trusted proxy ranges
# Only trust X-Forwarded-For and X-Real-IP from these ranges
import ipaddress

TRUSTED_PROXY_RANGES = [
    "10.0.0.0/8",      # Private class A
    "172.16.0.0/12",   # Private class B
    "192.168.0.0/16",  # Private class C
    "127.0.0.0/8",     # Loopback
    "::1/128",         # IPv6 loopback
    "fd00::/8",        # IPv6 private
]


def _is_valid_ip(ip: str) -> bool:
    """Check if IP string is valid."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _is_trusted_proxy(ip: str) -> bool:
    """Check if IP is from a trusted proxy range."""
    if not _is_valid_ip(ip):
        return False
    try:
        client_ip = ipaddress.ip_address(ip)
        for range_str in TRUSTED_PROXY_RANGES:
            if client_ip in ipaddress.ip_network(range_str, strict=False):
                return True
    except ValueError:
        pass
    return False


async def get_client_ip(request: Request) -> str | None:
    """
    Extract client IP address from request.

    SECURITY FIX (Audit 4 - M7): Only trust X-Forwarded-For and X-Real-IP
    when the direct connection is from a trusted proxy. This prevents IP
    spoofing from untrusted clients setting these headers directly.
    """
    # Get direct client IP
    direct_ip = request.client.host if request.client else None

    # If direct IP is not from a trusted proxy, use it directly
    # (don't trust forwarded headers from untrusted sources)
    if direct_ip and not _is_trusted_proxy(direct_ip):
        return direct_ip if _is_valid_ip(direct_ip) else None

    # Direct connection is from trusted proxy - check forwarded headers
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2...
        # Walk from right to find the first non-proxy IP
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        for ip in reversed(ips):
            if _is_valid_ip(ip) and not _is_trusted_proxy(ip):
                return ip
        # If all are proxies, take the leftmost (original client)
        if ips and _is_valid_ip(ips[0]):
            return ips[0]

    real_ip = request.headers.get("X-Real-IP")
    if real_ip and _is_valid_ip(real_ip):
        return real_ip

    # Direct connection
    return direct_ip


async def get_user_agent(request: Request) -> str | None:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


# Type aliases
ClientIP = Annotated[str | None, Depends(get_client_ip)]
UserAgent = Annotated[str | None, Depends(get_user_agent)]


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
        ip_address: Annotated[str | None, Depends(get_client_ip)],
        user_agent: Annotated[str | None, Depends(get_user_agent)]
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
        resource_owner_id: str | None = None
    ) -> bool:
        return self.auth.can_access_resource(resource_trust_level, resource_owner_id)

    def can_modify_resource(
        self,
        resource_owner_id: str,
        resource_trust_level: TrustLevel = TrustLevel.STANDARD
    ) -> bool:
        return self.auth.can_modify_resource(resource_owner_id, resource_trust_level)
