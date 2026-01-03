"""
Forge Cascade V2 Security Module

Provides authentication, authorization, and trust enforcement.
"""

from .password import (
    hash_password,
    verify_password,
    needs_rehash,
    get_password_strength
)

from .tokens import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_access_token,
    verify_refresh_token,
    get_token_expiry,
    is_token_expired,
    extract_token_from_header,
    get_token_claims,
    TokenError,
    TokenExpiredError,
    TokenInvalidError
)

from .authorization import (
    # Exceptions
    AuthorizationError,
    InsufficientTrustError,
    InsufficientRoleError,
    MissingCapabilityError,
    
    # Trust Level
    TRUST_LEVEL_VALUES,
    TRUST_LEVEL_PERMISSIONS,
    get_trust_level_from_score,
    check_trust_level,
    require_trust_level,
    get_trust_permissions,
    
    # Role-Based
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    check_role,
    require_role,
    get_role_permissions,
    has_role_permission,
    
    # Capability-Based
    TRUST_LEVEL_CAPABILITIES,
    get_capabilities_for_trust,
    check_capability,
    check_all_capabilities,
    check_any_capability,
    require_capability,
    require_capabilities,
    
    # Combined
    AuthorizationContext,
    create_auth_context
)

from .auth_service import (
    AuthService,
    get_auth_service,
    AuthenticationError,
    InvalidCredentialsError,
    AccountLockedError,
    AccountNotVerifiedError,
    AccountDeactivatedError,
    RegistrationError
)

from .dependencies import (
    # Core dependencies
    get_token,
    get_optional_auth_context,
    get_auth_context,
    get_current_user_id,
    
    # Type aliases
    AuthContext,
    OptionalAuthContext,
    CurrentUserId,
    
    # Trust dependencies
    require_trust,
    RequireSandboxTrust,
    RequireStandardTrust,
    RequireTrustedTrust,
    RequireCoreTrust,
    
    # Role dependencies
    require_role_dep,
    RequireModerator,
    RequireAdmin,
    RequireSystem,
    
    # Capability dependencies
    require_capability_dep,
    require_any_capability_dep,
    require_all_capabilities_dep,
    
    # Resource access
    ResourceAccessChecker,
    
    # Request info
    get_client_ip,
    get_user_agent,
    ClientIP,
    UserAgent,
    
    # Composite
    AuthenticatedRequest
)


__all__ = [
    # Password
    "hash_password",
    "verify_password",
    "needs_rehash",
    "get_password_strength",
    
    # Tokens
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
    "get_token_expiry",
    "is_token_expired",
    "extract_token_from_header",
    "get_token_claims",
    "TokenError",
    "TokenExpiredError",
    "TokenInvalidError",
    
    # Authorization
    "AuthorizationError",
    "InsufficientTrustError",
    "InsufficientRoleError",
    "MissingCapabilityError",
    "TRUST_LEVEL_VALUES",
    "TRUST_LEVEL_PERMISSIONS",
    "get_trust_level_from_score",
    "check_trust_level",
    "require_trust_level",
    "get_trust_permissions",
    "ROLE_HIERARCHY",
    "ROLE_PERMISSIONS",
    "check_role",
    "require_role",
    "get_role_permissions",
    "has_role_permission",
    "TRUST_LEVEL_CAPABILITIES",
    "get_capabilities_for_trust",
    "check_capability",
    "check_all_capabilities",
    "check_any_capability",
    "require_capability",
    "require_capabilities",
    "AuthorizationContext",
    "create_auth_context",
    
    # Auth Service
    "AuthService",
    "get_auth_service",
    "AuthenticationError",
    "InvalidCredentialsError",
    "AccountLockedError",
    "AccountNotVerifiedError",
    "AccountDeactivatedError",
    "RegistrationError",
    
    # Dependencies
    "get_token",
    "get_optional_auth_context",
    "get_auth_context",
    "get_current_user_id",
    "AuthContext",
    "OptionalAuthContext",
    "CurrentUserId",
    "require_trust",
    "RequireSandboxTrust",
    "RequireStandardTrust",
    "RequireTrustedTrust",
    "RequireCoreTrust",
    "require_role_dep",
    "RequireModerator",
    "RequireAdmin",
    "RequireSystem",
    "require_capability_dep",
    "require_any_capability_dep",
    "require_all_capabilities_dep",
    "ResourceAccessChecker",
    "get_client_ip",
    "get_user_agent",
    "ClientIP",
    "UserAgent",
    "AuthenticatedRequest"
]
