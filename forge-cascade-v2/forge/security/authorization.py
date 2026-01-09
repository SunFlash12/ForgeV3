"""
Trust & Authorization for Forge Cascade V2

Implements trust hierarchy enforcement and capability-based access control.
Trust levels determine what actions users can perform and what resources
they can access.
"""

from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Set

from ..models.base import TrustLevel
from ..models.user import UserRole
from ..models.overlay import Capability


class AuthorizationError(Exception):
    """Base exception for authorization failures."""
    pass


class InsufficientTrustError(AuthorizationError):
    """User's trust level is insufficient for the operation."""
    pass


class InsufficientRoleError(AuthorizationError):
    """User's role is insufficient for the operation."""
    pass


class MissingCapabilityError(AuthorizationError):
    """Required capability is missing."""
    pass


# =============================================================================
# Trust Level Hierarchy
# =============================================================================

# Map trust levels to numeric values for comparison
TRUST_LEVEL_VALUES = {
    TrustLevel.QUARANTINE: 0,
    TrustLevel.SANDBOX: 40,
    TrustLevel.STANDARD: 60,
    TrustLevel.TRUSTED: 80,
    TrustLevel.CORE: 100
}

# What each trust level can do
TRUST_LEVEL_PERMISSIONS = {
    TrustLevel.QUARANTINE: {
        "can_read_public": True,
        "can_create_capsules": False,
        "can_vote": False,
        "can_create_proposals": False,
        "can_run_overlays": False,
        "can_access_api": False,
        "rate_limit_multiplier": 0.1
    },
    TrustLevel.SANDBOX: {
        "can_read_public": True,
        "can_create_capsules": True,
        "can_vote": False,
        "can_create_proposals": False,
        "can_run_overlays": False,
        "can_access_api": True,
        "rate_limit_multiplier": 0.5
    },
    TrustLevel.STANDARD: {
        "can_read_public": True,
        "can_create_capsules": True,
        "can_vote": True,
        "can_create_proposals": False,
        "can_run_overlays": True,
        "can_access_api": True,
        "rate_limit_multiplier": 1.0
    },
    TrustLevel.TRUSTED: {
        "can_read_public": True,
        "can_create_capsules": True,
        "can_vote": True,
        "can_create_proposals": True,
        "can_run_overlays": True,
        "can_access_api": True,
        "rate_limit_multiplier": 2.0
    },
    TrustLevel.CORE: {
        "can_read_public": True,
        "can_create_capsules": True,
        "can_vote": True,
        "can_create_proposals": True,
        "can_run_overlays": True,
        "can_access_api": True,
        "rate_limit_multiplier": 10.0,
        "immune_to_rate_limit": True
    }
}


def get_trust_level_from_score(trust_flame: int) -> TrustLevel:
    """
    Convert numeric trust score to TrustLevel enum.

    Args:
        trust_flame: Numeric trust score (0-100)

    Returns:
        Corresponding TrustLevel
    """
    # Clamp trust_flame to valid range [0, 100]
    trust_flame = max(0, min(100, trust_flame))

    if trust_flame < 40:
        return TrustLevel.QUARANTINE
    elif trust_flame < 60:
        return TrustLevel.SANDBOX
    elif trust_flame < 80:
        return TrustLevel.STANDARD
    elif trust_flame < 100:
        return TrustLevel.TRUSTED
    else:
        return TrustLevel.CORE


def normalize_role(role: Any) -> UserRole:
    """
    Normalize a role to UserRole enum.

    Handles both string and enum inputs consistently.

    Args:
        role: Role as string or UserRole enum

    Returns:
        UserRole enum value
    """
    if isinstance(role, UserRole):
        return role
    if isinstance(role, str):
        try:
            return UserRole(role)
        except ValueError:
            return UserRole.USER
    return UserRole.USER


def is_admin(user: Any) -> bool:
    """
    Check if user has admin role.

    Handles both string and enum role attributes.

    Args:
        user: User object with role attribute

    Returns:
        True if user is admin
    """
    role = getattr(user, 'role', None)
    if role is None:
        return False
    normalized = normalize_role(role)
    return normalized == UserRole.ADMIN


def check_trust_level(user_trust: int, required_level: TrustLevel) -> bool:
    """
    Check if user's trust level meets the required level.
    
    Args:
        user_trust: User's numeric trust score
        required_level: Minimum required trust level
        
    Returns:
        True if user has sufficient trust
    """
    user_level = get_trust_level_from_score(user_trust)
    return TRUST_LEVEL_VALUES[user_level] >= TRUST_LEVEL_VALUES[required_level]


def require_trust_level(required_level: TrustLevel):
    """
    Decorator to require minimum trust level for a function.
    
    The decorated function must receive trust_flame as a keyword argument.
    
    Usage:
        @require_trust_level(TrustLevel.TRUSTED)
        async def create_proposal(trust_flame: int, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            trust_flame = kwargs.get("trust_flame")
            if trust_flame is None:
                raise AuthorizationError("trust_flame not provided")
            
            if not check_trust_level(trust_flame, required_level):
                user_level = get_trust_level_from_score(trust_flame)
                raise InsufficientTrustError(
                    f"Operation requires {required_level.name} trust level, "
                    f"user has {user_level.name}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_trust_permissions(trust_flame: int) -> dict[str, Any]:
    """
    Get all permissions for a given trust level.
    
    Args:
        trust_flame: Numeric trust score
        
    Returns:
        Dictionary of permission flags
    """
    level = get_trust_level_from_score(trust_flame)
    return TRUST_LEVEL_PERMISSIONS[level].copy()


# =============================================================================
# Role-Based Access Control
# =============================================================================

# Role hierarchy (higher roles include lower role permissions)
ROLE_HIERARCHY = {
    UserRole.USER: 1,
    UserRole.MODERATOR: 2,
    UserRole.ADMIN: 3,
    UserRole.SYSTEM: 4
}

# Role-specific permissions
ROLE_PERMISSIONS = {
    UserRole.USER: {
        "can_manage_own_content": True,
        "can_view_public": True,
        "can_report": True
    },
    UserRole.MODERATOR: {
        "can_manage_own_content": True,
        "can_view_public": True,
        "can_report": True,
        "can_moderate_content": True,
        "can_warn_users": True,
        "can_view_reports": True,
        "can_quarantine_capsules": True
    },
    UserRole.ADMIN: {
        "can_manage_own_content": True,
        "can_view_public": True,
        "can_report": True,
        "can_moderate_content": True,
        "can_warn_users": True,
        "can_view_reports": True,
        "can_quarantine_capsules": True,
        "can_manage_users": True,
        "can_adjust_trust": True,
        "can_manage_overlays": True,
        "can_view_audit_logs": True,
        "can_manage_system_config": True
    },
    UserRole.SYSTEM: {
        # SECURITY FIX (Audit 3): Explicitly enumerate SYSTEM permissions instead of "all": True
        # This prevents accidental permission grants if new permissions are added
        "can_manage_own_content": True,
        "can_view_public": True,
        "can_report": True,
        "can_moderate_content": True,
        "can_warn_users": True,
        "can_view_reports": True,
        "can_quarantine_capsules": True,
        "can_manage_users": True,
        "can_adjust_trust": True,
        "can_manage_overlays": True,
        "can_view_audit_logs": True,
        "can_manage_system_config": True,
        # System-only permissions
        "can_execute_system_tasks": True,
        "can_manage_federation": True,
        "can_bypass_rate_limits": True,
        "can_access_internal_apis": True,
    }
}


def check_role(user_role: UserRole, required_role: UserRole) -> bool:
    """
    Check if user's role meets the required role.
    
    Args:
        user_role: User's current role
        required_role: Minimum required role
        
    Returns:
        True if user has sufficient role
    """
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def require_role(required_role: UserRole):
    """
    Decorator to require minimum role for a function.
    
    The decorated function must receive role as a keyword argument.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            role = kwargs.get("role")
            if role is None:
                raise AuthorizationError("role not provided")
            
            if isinstance(role, str):
                role = UserRole(role)
            
            if not check_role(role, required_role):
                raise InsufficientRoleError(
                    f"Operation requires {required_role.value} role, "
                    f"user has {role.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def get_role_permissions(role: UserRole) -> dict[str, bool]:
    """
    Get all permissions for a given role.

    Args:
        role: User's role

    Returns:
        Dictionary of permission flags
    """
    # SECURITY FIX (Audit 3): Return explicit permissions for all roles including SYSTEM
    return ROLE_PERMISSIONS.get(role, {}).copy()


def has_role_permission(role: UserRole, permission: str) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: User's role
        permission: Permission to check

    Returns:
        True if role has the permission
    """
    permissions = get_role_permissions(role)
    # SECURITY FIX (Audit 3): Removed "all" fallback - require explicit permission
    return permissions.get(permission, False)


# =============================================================================
# Capability-Based Access Control (for Overlays)
# =============================================================================

# Default capabilities for each trust level
TRUST_LEVEL_CAPABILITIES: dict[TrustLevel, Set[Capability]] = {
    TrustLevel.QUARANTINE: set(),
    TrustLevel.SANDBOX: {
        Capability.CAPSULE_READ
    },
    TrustLevel.STANDARD: {
        Capability.CAPSULE_READ,
        Capability.CAPSULE_WRITE,
        Capability.EVENT_SUBSCRIBE,
        Capability.DATABASE_READ
    },
    TrustLevel.TRUSTED: {
        Capability.CAPSULE_READ,
        Capability.CAPSULE_WRITE,
        Capability.EVENT_SUBSCRIBE,
        Capability.EVENT_PUBLISH,
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.GOVERNANCE_VOTE,
        Capability.GOVERNANCE_PROPOSE
    },
    TrustLevel.CORE: {
        Capability.NETWORK_ACCESS,
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_SUBSCRIBE,
        Capability.EVENT_PUBLISH,
        Capability.CAPSULE_READ,
        Capability.CAPSULE_WRITE,
        Capability.CAPSULE_DELETE,
        Capability.GOVERNANCE_VOTE,
        Capability.GOVERNANCE_PROPOSE,
        Capability.GOVERNANCE_EXECUTE
    }
}


def get_capabilities_for_trust(trust_flame: int) -> Set[Capability]:
    """
    Get capabilities available at a trust level.
    
    Args:
        trust_flame: Numeric trust score
        
    Returns:
        Set of available capabilities
    """
    level = get_trust_level_from_score(trust_flame)
    return TRUST_LEVEL_CAPABILITIES.get(level, set()).copy()


def check_capability(
    user_capabilities: Set[Capability],
    required_capability: Capability
) -> bool:
    """
    Check if user has a specific capability.
    
    Args:
        user_capabilities: Set of user's capabilities
        required_capability: Capability to check
        
    Returns:
        True if user has the capability
    """
    return required_capability in user_capabilities


def check_all_capabilities(
    user_capabilities: Set[Capability],
    required_capabilities: Set[Capability]
) -> bool:
    """
    Check if user has ALL required capabilities.
    
    Args:
        user_capabilities: Set of user's capabilities
        required_capabilities: Set of required capabilities
        
    Returns:
        True if user has all required capabilities
    """
    return required_capabilities.issubset(user_capabilities)


def check_any_capability(
    user_capabilities: Set[Capability],
    required_capabilities: Set[Capability]
) -> bool:
    """
    Check if user has ANY of the required capabilities.
    
    Args:
        user_capabilities: Set of user's capabilities
        required_capabilities: Set of required capabilities
        
    Returns:
        True if user has at least one required capability
    """
    return bool(required_capabilities.intersection(user_capabilities))


def require_capability(required_capability: Capability):
    """
    Decorator to require a specific capability.
    
    The decorated function must receive capabilities as a keyword argument.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            capabilities = kwargs.get("capabilities", set())
            
            if not check_capability(capabilities, required_capability):
                raise MissingCapabilityError(
                    f"Operation requires {required_capability.value} capability"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_capabilities(*required_capabilities: Capability):
    """
    Decorator to require multiple capabilities (ALL must be present).
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            capabilities = kwargs.get("capabilities", set())
            
            missing = set(required_capabilities) - capabilities
            if missing:
                raise MissingCapabilityError(
                    f"Operation requires capabilities: {[c.value for c in missing]}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# Combined Authorization
# =============================================================================

class AuthorizationContext:
    """
    Context for authorization decisions.
    
    Combines trust level, role, and capabilities for comprehensive
    authorization checks.
    """
    
    def __init__(
        self,
        user_id: str,
        trust_flame: int,
        role: UserRole,
        capabilities: Optional[Set[Capability]] = None
    ):
        self.user_id = user_id
        self.trust_flame = trust_flame
        self.trust_level = get_trust_level_from_score(trust_flame)
        self.role = role
        
        # Auto-populate capabilities from trust level if not provided
        if capabilities is None:
            self.capabilities = get_capabilities_for_trust(trust_flame)
        else:
            self.capabilities = capabilities
    
    def has_trust(self, required: TrustLevel) -> bool:
        """Check if user meets trust level requirement."""
        return check_trust_level(self.trust_flame, required)
    
    def has_role(self, required: UserRole) -> bool:
        """Check if user meets role requirement."""
        return check_role(self.role, required)
    
    def has_capability(self, required: Capability) -> bool:
        """Check if user has a specific capability."""
        return check_capability(self.capabilities, required)
    
    def has_all_capabilities(self, required: Set[Capability]) -> bool:
        """Check if user has all required capabilities."""
        return check_all_capabilities(self.capabilities, required)
    
    def has_any_capability(self, required: Set[Capability]) -> bool:
        """Check if user has any of the required capabilities."""
        return check_any_capability(self.capabilities, required)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific role permission."""
        return has_role_permission(self.role, permission)
    
    def get_trust_permissions(self) -> dict[str, Any]:
        """Get all trust-based permissions."""
        return get_trust_permissions(self.trust_flame)
    
    def get_role_permissions(self) -> dict[str, bool]:
        """Get all role-based permissions."""
        return get_role_permissions(self.role)
    
    def can_access_resource(
        self,
        resource_trust_level: TrustLevel,
        resource_owner_id: Optional[str] = None
    ) -> bool:
        """
        Check if user can access a resource.
        
        Users can access resources if:
        - They own the resource
        - Their trust level is >= the resource's required trust level
        - They are an admin or moderator
        """
        # Owner always has access
        if resource_owner_id and self.user_id == resource_owner_id:
            return True
        
        # Admins and moderators have elevated access
        if self.has_role(UserRole.MODERATOR):
            return True
        
        # Check trust level
        return self.has_trust(resource_trust_level)
    
    def can_modify_resource(
        self,
        resource_owner_id: str,
        resource_trust_level: TrustLevel = TrustLevel.STANDARD
    ) -> bool:
        """
        Check if user can modify a resource.
        
        Users can modify resources if:
        - They own the resource AND have sufficient trust
        - They are an admin
        """
        # Admins can modify anything
        if self.has_role(UserRole.ADMIN):
            return True
        
        # Owner can modify if they have sufficient trust
        if self.user_id == resource_owner_id:
            return self.has_trust(resource_trust_level)
        
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary (for logging/debugging)."""
        return {
            "user_id": self.user_id,
            "trust_flame": self.trust_flame,
            "trust_level": self.trust_level.name,
            "role": self.role.value,
            "capabilities": [c.value for c in self.capabilities]
        }


def create_auth_context(
    user_id: str,
    trust_flame: int,
    role: str,
    capabilities: Optional[list[str]] = None
) -> AuthorizationContext:
    """
    Factory function to create AuthorizationContext from raw values.
    
    Args:
        user_id: User's unique identifier
        trust_flame: Numeric trust score
        role: Role string
        capabilities: Optional list of capability strings
        
    Returns:
        AuthorizationContext instance
    """
    user_role = UserRole(role) if isinstance(role, str) else role
    
    caps = None
    if capabilities:
        caps = {Capability(c) for c in capabilities}
    
    return AuthorizationContext(
        user_id=user_id,
        trust_flame=trust_flame,
        role=user_role,
        capabilities=caps
    )


class TrustAuthorizer:
    """
    Authorizer that checks if a user meets minimum trust level requirements.
    """
    
    def __init__(self, min_level: TrustLevel):
        """
        Initialize with minimum required trust level.
        
        Args:
            min_level: Minimum trust level required for authorization
        """
        self.min_level = min_level
    
    def authorize(self, user: Any) -> bool:
        """
        Check if user meets trust level requirement.
        
        Args:
            user: User object with trust_score or trust_flame attribute
            
        Returns:
            True if user meets minimum trust level
        """
        trust_flame = getattr(user, 'trust_score', None) or getattr(user, 'trust_flame', 0)
        user_level = get_trust_level_from_score(trust_flame)
        return user_level.value >= self.min_level.value


class RoleAuthorizer:
    """
    Authorizer that checks if a user has one of the required roles.
    """
    
    def __init__(self, allowed_roles: Set[str]):
        """
        Initialize with set of allowed roles.
        
        Args:
            allowed_roles: Set of role names that are authorized
        """
        self.allowed_roles = allowed_roles
    
    def authorize(self, user: Any) -> bool:
        """
        Check if user has an allowed role.
        
        Args:
            user: User object with role attribute
            
        Returns:
            True if user has one of the allowed roles
        """
        user_role = getattr(user, 'role', None)
        if user_role is None:
            return False
        
        role_str = user_role.value if hasattr(user_role, 'value') else str(user_role)
        return role_str in self.allowed_roles


class CapabilityAuthorizer:
    """
    Authorizer that checks if a user has required capabilities.
    """
    
    def __init__(self, required_capabilities: Set[Capability]):
        """
        Initialize with set of required capabilities.
        
        Args:
            required_capabilities: Set of capabilities required for authorization
        """
        self.required_capabilities = required_capabilities
    
    def authorize(self, user: Any) -> bool:
        """
        Check if user has all required capabilities.
        
        Args:
            user: User object with trust_score/trust_flame and capabilities
            
        Returns:
            True if user has all required capabilities
        """
        trust_flame = getattr(user, 'trust_score', None) or getattr(user, 'trust_flame', 0)
        user_capabilities = get_capabilities_for_trust(trust_flame)
        
        # Also check explicit capabilities if set on user
        explicit_caps = getattr(user, 'capabilities', set())
        if explicit_caps:
            user_capabilities = user_capabilities | explicit_caps
        
        return self.required_capabilities.issubset(user_capabilities)
