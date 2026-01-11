"""
Forge Cascade V2 Security Module

Provides authentication, authorization, and trust enforcement.
"""

from .auth_service import (
    AccountDeactivatedError,
    AccountLockedError,
    AccountNotVerifiedError,
    AuthenticationError,
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
    get_auth_service,
)
from .authorization import (
    # Role-Based
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    # Capability-Based
    TRUST_LEVEL_CAPABILITIES,
    TRUST_LEVEL_PERMISSIONS,
    # Trust Level
    TRUST_LEVEL_VALUES,
    # Combined
    AuthorizationContext,
    # Exceptions
    AuthorizationError,
    InsufficientRoleError,
    InsufficientTrustError,
    MissingCapabilityError,
    check_all_capabilities,
    check_any_capability,
    check_capability,
    check_role,
    check_trust_level,
    create_auth_context,
    get_capabilities_for_trust,
    get_role_permissions,
    get_trust_level_from_score,
    get_trust_permissions,
    has_role_permission,
    require_capabilities,
    require_capability,
    require_role,
    require_trust_level,
)
from .capsule_integrity import (
    CapsuleIntegrityService,
    ContentHashMismatchError,
    IntegrityError,
    MerkleChainError,
    SignatureVerificationError,
    get_integrity_service,
)
from .dependencies import (
    # Type aliases
    AuthContext,
    # Composite
    AuthenticatedRequest,
    ClientIP,
    CurrentUserId,
    OptionalAuthContext,
    RequireAdmin,
    RequireCoreTrust,
    RequireModerator,
    RequireSandboxTrust,
    RequireStandardTrust,
    RequireSystem,
    RequireTrustedTrust,
    # Resource access
    ResourceAccessChecker,
    UserAgent,
    get_auth_context,
    # Request info
    get_client_ip,
    get_current_user_id,
    get_optional_auth_context,
    # Core dependencies
    get_token,
    get_user_agent,
    require_all_capabilities_dep,
    require_any_capability_dep,
    # Capability dependencies
    require_capability_dep,
    # Role dependencies
    require_role_dep,
    # Trust dependencies
    require_trust,
)
from .key_management import (
    InvalidKeyError,
    KeyDecryptionError,
    KeyDerivationError,
    KeyManagementError,
    KeyManagementService,
    KeyNotFoundError,
    SigningKeyInfo,
    get_key_management_service,
)
from .mfa import (
    MFAService,
    MFASetupResult,
    MFAStatus,
)
from .password import (
    get_password_strength,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from .prompt_sanitization import (
    INJECTION_PATTERNS,
    create_safe_user_message,
    sanitize_dict_for_prompt,
    sanitize_for_prompt,
    validate_llm_output,
)
from .safe_regex import (
    RegexTimeoutError,
    RegexValidationError,
    safe_compile,
    safe_findall,
    safe_match,
    safe_search,
    safe_sub,
    validate_pattern,
)
from .secrets_manager import (
    AWSSecretsManager,
    BaseSecretsManager,
    EnvironmentSecretsManager,
    SecretNotFoundError,
    SecretsBackend,
    SecretsBackendError,
    VaultSecretsManager,
    configure_secrets_manager,
    create_secrets_manager,
    get_required_secret,
    get_secret,
    get_secrets_manager,
)
from .tokens import (
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    extract_token_from_header,
    get_token_claims,
    get_token_expiry,
    hash_refresh_token,
    is_token_expired,
    verify_access_token,
    verify_refresh_token,
    verify_refresh_token_hash,
)

__all__ = [
    # Capsule Integrity
    "CapsuleIntegrityService",
    "get_integrity_service",
    "IntegrityError",
    "ContentHashMismatchError",
    "SignatureVerificationError",
    "MerkleChainError",

    # Key Management
    "KeyManagementService",
    "get_key_management_service",
    "KeyManagementError",
    "KeyNotFoundError",
    "KeyDecryptionError",
    "KeyDerivationError",
    "InvalidKeyError",
    "SigningKeyInfo",

    # MFA
    "MFAService",
    "MFASetupResult",
    "MFAStatus",

    # Password
    "hash_password",
    "verify_password",
    "needs_rehash",
    "get_password_strength",
    "validate_password_strength",

    # Prompt Sanitization
    "sanitize_for_prompt",
    "sanitize_dict_for_prompt",
    "create_safe_user_message",
    "validate_llm_output",
    "INJECTION_PATTERNS",

    # Safe Regex
    "safe_compile",
    "safe_match",
    "safe_search",
    "safe_findall",
    "safe_sub",
    "validate_pattern",
    "RegexValidationError",
    "RegexTimeoutError",

    # Tokens
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
    "hash_refresh_token",
    "verify_refresh_token_hash",
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
    "AuthenticatedRequest",

    # Secrets Manager
    "BaseSecretsManager",
    "EnvironmentSecretsManager",
    "VaultSecretsManager",
    "AWSSecretsManager",
    "SecretsBackend",
    "SecretNotFoundError",
    "SecretsBackendError",
    "get_secrets_manager",
    "create_secrets_manager",
    "configure_secrets_manager",
    "get_secret",
    "get_required_secret",
]
