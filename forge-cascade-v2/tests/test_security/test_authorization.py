"""
Authorization Tests for Forge Cascade V2

Comprehensive tests for authorization system including:
- Trust level hierarchy
- Role-based access control
- Capability-based access control
- Combined authorization context
"""

import pytest

from forge.models.base import TrustLevel
from forge.models.overlay import Capability
from forge.models.user import UserRole
from forge.security.authorization import (
    AuthorizationContext,
    AuthorizationError,
    CapabilityAuthorizer,
    InsufficientRoleError,
    InsufficientTrustError,
    MissingCapabilityError,
    RoleAuthorizer,
    ROLE_HIERARCHY,
    ROLE_PERMISSIONS,
    TrustAuthorizer,
    TRUST_LEVEL_CAPABILITIES,
    TRUST_LEVEL_PERMISSIONS,
    TRUST_LEVEL_VALUES,
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
    is_admin,
    normalize_role,
    require_capability,
    require_role,
    require_trust_level,
)


# =============================================================================
# Trust Level Tests
# =============================================================================

class TestTrustLevelHierarchy:
    """Tests for trust level hierarchy functions."""

    @pytest.mark.parametrize("score,expected_level", [
        (0, TrustLevel.QUARANTINE),
        (20, TrustLevel.QUARANTINE),
        (39, TrustLevel.QUARANTINE),
        (40, TrustLevel.SANDBOX),
        (50, TrustLevel.SANDBOX),
        (59, TrustLevel.SANDBOX),
        (60, TrustLevel.STANDARD),
        (70, TrustLevel.STANDARD),
        (79, TrustLevel.STANDARD),
        (80, TrustLevel.TRUSTED),
        (90, TrustLevel.TRUSTED),
        (99, TrustLevel.TRUSTED),
        (100, TrustLevel.CORE),
    ])
    def test_get_trust_level_from_score(self, score, expected_level):
        """Trust score maps to correct level."""
        assert get_trust_level_from_score(score) == expected_level

    def test_get_trust_level_clamps_negative(self):
        """Negative scores clamp to 0 (QUARANTINE)."""
        assert get_trust_level_from_score(-10) == TrustLevel.QUARANTINE

    def test_get_trust_level_clamps_over_100(self):
        """Scores over 100 clamp to 100 (CORE)."""
        assert get_trust_level_from_score(150) == TrustLevel.CORE

    @pytest.mark.parametrize("user_score,required_level,expected", [
        (60, TrustLevel.STANDARD, True),
        (60, TrustLevel.SANDBOX, True),
        (60, TrustLevel.TRUSTED, False),
        (80, TrustLevel.TRUSTED, True),
        (100, TrustLevel.CORE, True),
        (40, TrustLevel.STANDARD, False),
    ])
    def test_check_trust_level(self, user_score, required_level, expected):
        """Trust level check returns correct result."""
        assert check_trust_level(user_score, required_level) == expected

    def test_get_trust_permissions(self):
        """Get permissions for trust level."""
        # Standard user
        perms = get_trust_permissions(60)
        assert perms["can_read_public"] is True
        assert perms["can_vote"] is True
        assert perms["can_create_proposals"] is False

        # Trusted user
        perms = get_trust_permissions(80)
        assert perms["can_create_proposals"] is True

        # Quarantine user
        perms = get_trust_permissions(20)
        assert perms["can_create_capsules"] is False
        assert perms["can_access_api"] is False


# =============================================================================
# Role-Based Access Control Tests
# =============================================================================

class TestRoleBasedAccessControl:
    """Tests for role-based access control."""

    def test_normalize_role_from_string(self):
        """Role normalization from string."""
        assert normalize_role("user") == UserRole.USER
        assert normalize_role("admin") == UserRole.ADMIN
        assert normalize_role("moderator") == UserRole.MODERATOR

    def test_normalize_role_from_enum(self):
        """Role normalization from enum."""
        assert normalize_role(UserRole.ADMIN) == UserRole.ADMIN

    def test_normalize_role_invalid_defaults_to_user(self):
        """Invalid role defaults to USER."""
        assert normalize_role("invalid") == UserRole.USER
        assert normalize_role(123) == UserRole.USER

    def test_is_admin_true(self):
        """is_admin returns True for admin."""
        class MockUser:
            role = UserRole.ADMIN

        assert is_admin(MockUser()) is True

    def test_is_admin_false(self):
        """is_admin returns False for non-admin."""
        class MockUser:
            role = UserRole.USER

        assert is_admin(MockUser()) is False

    def test_is_admin_string_role(self):
        """is_admin handles string role."""
        class MockUser:
            role = "admin"

        assert is_admin(MockUser()) is True

    @pytest.mark.parametrize("user_role,required_role,expected", [
        (UserRole.USER, UserRole.USER, True),
        (UserRole.MODERATOR, UserRole.USER, True),
        (UserRole.ADMIN, UserRole.MODERATOR, True),
        (UserRole.USER, UserRole.MODERATOR, False),
        (UserRole.USER, UserRole.ADMIN, False),
        (UserRole.SYSTEM, UserRole.ADMIN, True),
    ])
    def test_check_role(self, user_role, required_role, expected):
        """Role check follows hierarchy."""
        assert check_role(user_role, required_role) == expected

    def test_get_role_permissions_user(self):
        """User role has basic permissions."""
        perms = get_role_permissions(UserRole.USER)
        assert perms["can_manage_own_content"] is True
        assert perms["can_view_public"] is True
        assert perms.get("can_manage_users", False) is False

    def test_get_role_permissions_admin(self):
        """Admin role has elevated permissions."""
        perms = get_role_permissions(UserRole.ADMIN)
        assert perms["can_manage_users"] is True
        assert perms["can_adjust_trust"] is True
        assert perms["can_view_audit_logs"] is True

    def test_get_role_permissions_system(self):
        """System role has all permissions explicitly defined."""
        perms = get_role_permissions(UserRole.SYSTEM)
        assert perms["can_execute_system_tasks"] is True
        assert perms["can_manage_federation"] is True
        assert perms["can_bypass_rate_limits"] is True

    def test_has_role_permission(self):
        """Check specific permission for role."""
        assert has_role_permission(UserRole.ADMIN, "can_manage_users") is True
        assert has_role_permission(UserRole.USER, "can_manage_users") is False


# =============================================================================
# Capability-Based Access Control Tests
# =============================================================================

class TestCapabilityBasedAccessControl:
    """Tests for capability-based access control."""

    def test_get_capabilities_for_trust_quarantine(self):
        """Quarantine has no capabilities."""
        caps = get_capabilities_for_trust(20)
        assert len(caps) == 0

    def test_get_capabilities_for_trust_sandbox(self):
        """Sandbox has read capability."""
        caps = get_capabilities_for_trust(50)
        assert Capability.CAPSULE_READ in caps

    def test_get_capabilities_for_trust_standard(self):
        """Standard has read/write capabilities."""
        caps = get_capabilities_for_trust(60)
        assert Capability.CAPSULE_READ in caps
        assert Capability.CAPSULE_WRITE in caps
        assert Capability.DATABASE_READ in caps

    def test_get_capabilities_for_trust_trusted(self):
        """Trusted has governance capabilities."""
        caps = get_capabilities_for_trust(80)
        assert Capability.GOVERNANCE_VOTE in caps
        assert Capability.GOVERNANCE_PROPOSE in caps

    def test_get_capabilities_for_trust_core(self):
        """Core has all capabilities."""
        caps = get_capabilities_for_trust(100)
        assert Capability.GOVERNANCE_EXECUTE in caps
        assert Capability.CAPSULE_DELETE in caps
        assert Capability.NETWORK_ACCESS in caps

    def test_check_capability(self):
        """Single capability check."""
        user_caps = {Capability.CAPSULE_READ, Capability.CAPSULE_WRITE}

        assert check_capability(user_caps, Capability.CAPSULE_READ) is True
        assert check_capability(user_caps, Capability.CAPSULE_DELETE) is False

    def test_check_all_capabilities(self):
        """All capabilities check."""
        user_caps = {Capability.CAPSULE_READ, Capability.CAPSULE_WRITE, Capability.DATABASE_READ}
        required = {Capability.CAPSULE_READ, Capability.DATABASE_READ}

        assert check_all_capabilities(user_caps, required) is True

        required_more = {Capability.CAPSULE_READ, Capability.CAPSULE_DELETE}
        assert check_all_capabilities(user_caps, required_more) is False

    def test_check_any_capability(self):
        """Any capability check."""
        user_caps = {Capability.CAPSULE_READ}
        required = {Capability.CAPSULE_READ, Capability.CAPSULE_DELETE}

        assert check_any_capability(user_caps, required) is True

        required_none = {Capability.CAPSULE_DELETE, Capability.NETWORK_ACCESS}
        assert check_any_capability(user_caps, required_none) is False


# =============================================================================
# Authorization Context Tests
# =============================================================================

class TestAuthorizationContext:
    """Tests for AuthorizationContext class."""

    def test_create_context_basic(self):
        """Basic context creation."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.USER,
        )

        assert context.user_id == "user123"
        assert context.trust_flame == 60
        assert context.trust_level == TrustLevel.STANDARD
        assert context.role == UserRole.USER

    def test_create_context_auto_capabilities(self):
        """Context auto-populates capabilities from trust level."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=80,
            role=UserRole.USER,
        )

        assert Capability.GOVERNANCE_VOTE in context.capabilities
        assert Capability.GOVERNANCE_PROPOSE in context.capabilities

    def test_create_context_explicit_capabilities(self):
        """Context with explicit capabilities."""
        caps = {Capability.CAPSULE_READ}
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.USER,
            capabilities=caps,
        )

        assert context.capabilities == caps

    def test_context_has_trust(self):
        """Context trust level check."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=70,
            role=UserRole.USER,
        )

        assert context.has_trust(TrustLevel.STANDARD) is True
        assert context.has_trust(TrustLevel.SANDBOX) is True
        assert context.has_trust(TrustLevel.TRUSTED) is False

    def test_context_has_role(self):
        """Context role check."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.MODERATOR,
        )

        assert context.has_role(UserRole.USER) is True
        assert context.has_role(UserRole.MODERATOR) is True
        assert context.has_role(UserRole.ADMIN) is False

    def test_context_has_capability(self):
        """Context capability check."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.USER,
        )

        assert context.has_capability(Capability.CAPSULE_READ) is True
        assert context.has_capability(Capability.CAPSULE_DELETE) is False

    def test_context_has_permission(self):
        """Context permission check."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.ADMIN,
        )

        assert context.has_permission("can_manage_users") is True
        assert context.has_permission("can_execute_system_tasks") is False

    def test_context_can_access_resource_owner(self):
        """Owner can access their resource."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=40,  # Low trust
            role=UserRole.USER,
        )

        # Can access own resource regardless of trust
        assert context.can_access_resource(
            TrustLevel.TRUSTED,
            resource_owner_id="user123"
        ) is True

    def test_context_can_access_resource_moderator(self):
        """Moderator can access any resource."""
        context = AuthorizationContext(
            user_id="mod456",
            trust_flame=60,
            role=UserRole.MODERATOR,
        )

        assert context.can_access_resource(
            TrustLevel.CORE,
            resource_owner_id="user123"
        ) is True

    def test_context_can_access_resource_by_trust(self):
        """User can access resource if trust level sufficient."""
        context = AuthorizationContext(
            user_id="user789",
            trust_flame=80,  # TRUSTED
            role=UserRole.USER,
        )

        # Can access TRUSTED resource
        assert context.can_access_resource(TrustLevel.TRUSTED) is True
        # Cannot access CORE resource
        assert context.can_access_resource(TrustLevel.CORE) is False

    def test_context_can_modify_resource_owner(self):
        """Owner can modify their resource."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.USER,
        )

        assert context.can_modify_resource("user123") is True
        assert context.can_modify_resource("other456") is False

    def test_context_can_modify_resource_admin(self):
        """Admin can modify any resource."""
        context = AuthorizationContext(
            user_id="admin123",
            trust_flame=60,
            role=UserRole.ADMIN,
        )

        assert context.can_modify_resource("other456") is True

    def test_context_to_dict(self):
        """Context serialization."""
        context = AuthorizationContext(
            user_id="user123",
            trust_flame=60,
            role=UserRole.USER,
        )

        data = context.to_dict()
        assert data["user_id"] == "user123"
        assert data["trust_flame"] == 60
        assert data["trust_level"] == "STANDARD"
        assert data["role"] == "user"
        assert "capabilities" in data


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestCreateAuthContext:
    """Tests for create_auth_context factory function."""

    def test_create_from_strings(self):
        """Create context from string values."""
        context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
        )

        assert context.user_id == "user123"
        assert context.role == UserRole.USER

    def test_create_with_capability_strings(self):
        """Create context with capability strings."""
        context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
            capabilities=["capsule_read", "capsule_write"],
        )

        assert Capability.CAPSULE_READ in context.capabilities
        assert Capability.CAPSULE_WRITE in context.capabilities


# =============================================================================
# Decorator Tests
# =============================================================================

class TestAuthorizationDecorators:
    """Tests for authorization decorators."""

    @pytest.mark.asyncio
    async def test_require_trust_level_passes(self):
        """Trust level decorator passes with sufficient trust."""

        @require_trust_level(TrustLevel.STANDARD)
        async def protected_func(trust_flame: int):
            return "success"

        result = await protected_func(trust_flame=60)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_trust_level_fails(self):
        """Trust level decorator fails with insufficient trust."""

        @require_trust_level(TrustLevel.TRUSTED)
        async def protected_func(trust_flame: int):
            return "success"

        with pytest.raises(InsufficientTrustError):
            await protected_func(trust_flame=60)

    @pytest.mark.asyncio
    async def test_require_trust_level_no_param(self):
        """Trust level decorator fails without trust_flame param."""

        @require_trust_level(TrustLevel.STANDARD)
        async def protected_func():
            return "success"

        with pytest.raises(AuthorizationError, match="not provided"):
            await protected_func()

    @pytest.mark.asyncio
    async def test_require_role_passes(self):
        """Role decorator passes with sufficient role."""

        @require_role(UserRole.MODERATOR)
        async def protected_func(role: UserRole):
            return "success"

        result = await protected_func(role=UserRole.ADMIN)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_role_fails(self):
        """Role decorator fails with insufficient role."""

        @require_role(UserRole.ADMIN)
        async def protected_func(role: UserRole):
            return "success"

        with pytest.raises(InsufficientRoleError):
            await protected_func(role=UserRole.USER)

    @pytest.mark.asyncio
    async def test_require_capability_passes(self):
        """Capability decorator passes with required capability."""

        @require_capability(Capability.CAPSULE_READ)
        async def protected_func(capabilities: set):
            return "success"

        result = await protected_func(capabilities={Capability.CAPSULE_READ})
        assert result == "success"

    @pytest.mark.asyncio
    async def test_require_capability_fails(self):
        """Capability decorator fails without required capability."""

        @require_capability(Capability.CAPSULE_DELETE)
        async def protected_func(capabilities: set):
            return "success"

        with pytest.raises(MissingCapabilityError):
            await protected_func(capabilities={Capability.CAPSULE_READ})


# =============================================================================
# Authorizer Class Tests
# =============================================================================

class TestAuthorizers:
    """Tests for authorizer classes."""

    def test_trust_authorizer_passes(self):
        """TrustAuthorizer passes with sufficient trust."""

        class MockUser:
            trust_flame = 80

        authorizer = TrustAuthorizer(TrustLevel.STANDARD)
        assert authorizer.authorize(MockUser()) is True

    def test_trust_authorizer_fails(self):
        """TrustAuthorizer fails with insufficient trust."""

        class MockUser:
            trust_flame = 40

        authorizer = TrustAuthorizer(TrustLevel.STANDARD)
        assert authorizer.authorize(MockUser()) is False

    def test_role_authorizer_passes(self):
        """RoleAuthorizer passes with allowed role."""

        class MockUser:
            role = UserRole.ADMIN

        authorizer = RoleAuthorizer({"admin", "moderator"})
        assert authorizer.authorize(MockUser()) is True

    def test_role_authorizer_fails(self):
        """RoleAuthorizer fails with disallowed role."""

        class MockUser:
            role = UserRole.USER

        authorizer = RoleAuthorizer({"admin", "moderator"})
        assert authorizer.authorize(MockUser()) is False

    def test_capability_authorizer_passes(self):
        """CapabilityAuthorizer passes with required capabilities."""

        class MockUser:
            trust_flame = 100  # CORE level has all capabilities

        authorizer = CapabilityAuthorizer({Capability.CAPSULE_READ, Capability.CAPSULE_WRITE})
        assert authorizer.authorize(MockUser()) is True

    def test_capability_authorizer_fails(self):
        """CapabilityAuthorizer fails without required capabilities."""

        class MockUser:
            trust_flame = 50  # SANDBOX only has read

        authorizer = CapabilityAuthorizer({Capability.CAPSULE_READ, Capability.CAPSULE_WRITE})
        assert authorizer.authorize(MockUser()) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
