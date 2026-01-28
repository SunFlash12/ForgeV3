"""
Tests for Tenant Isolation
==========================

Tests for forge/resilience/security/tenant_isolation.py
"""

from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.security.tenant_isolation import (
    TenantContext,
    TenantIsolationError,
    TenantIsolator,
    TenantLimits,
    TenantQuotaExceededError,
    TenantTier,
    get_tenant_isolator,
    require_tenant,
    tenant_scope,
)


class TestTenantTier:
    """Tests for TenantTier enum."""

    def test_tier_values(self):
        """Test all tenant tier values."""
        assert TenantTier.FREE.value == "free"
        assert TenantTier.STANDARD.value == "standard"
        assert TenantTier.PROFESSIONAL.value == "professional"
        assert TenantTier.ENTERPRISE.value == "enterprise"


class TestTenantLimits:
    """Tests for TenantLimits dataclass."""

    def test_default_limits(self):
        """Test default limit values."""
        limits = TenantLimits()

        assert limits.max_capsules == 10000
        assert limits.max_users == 100
        assert limits.max_storage_mb == 1024
        assert limits.max_api_calls_per_hour == 10000
        assert limits.max_lineage_depth == 10
        assert limits.allow_custom_overlays is False
        assert limits.allow_ghost_council is False

    def test_for_tier_free(self):
        """Test limits for FREE tier."""
        limits = TenantLimits.for_tier(TenantTier.FREE)

        assert limits.max_capsules == 100
        assert limits.max_users == 5
        assert limits.max_storage_mb == 100

    def test_for_tier_standard(self):
        """Test limits for STANDARD tier."""
        limits = TenantLimits.for_tier(TenantTier.STANDARD)

        assert limits.max_capsules == 10000
        assert limits.max_users == 50

    def test_for_tier_professional(self):
        """Test limits for PROFESSIONAL tier."""
        limits = TenantLimits.for_tier(TenantTier.PROFESSIONAL)

        assert limits.max_capsules == 100000
        assert limits.max_users == 500
        assert limits.allow_custom_overlays is True

    def test_for_tier_enterprise(self):
        """Test limits for ENTERPRISE tier."""
        limits = TenantLimits.for_tier(TenantTier.ENTERPRISE)

        assert limits.max_capsules == -1  # Unlimited
        assert limits.max_users == -1
        assert limits.allow_custom_overlays is True
        assert limits.allow_ghost_council is True


class TestTenantContext:
    """Tests for TenantContext dataclass."""

    def test_context_creation(self):
        """Test creating a tenant context."""
        context = TenantContext(
            tenant_id="tenant_123",
            tenant_name="Test Tenant",
            tier=TenantTier.STANDARD,
        )

        assert context.tenant_id == "tenant_123"
        assert context.tenant_name == "Test Tenant"
        assert context.tier == TenantTier.STANDARD
        assert context.current_capsule_count == 0
        assert context.current_user_count == 0

    def test_can_create_capsule_within_limit(self):
        """Test capsule creation within limit."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            limits=TenantLimits(max_capsules=100),
        )
        context.current_capsule_count = 50

        assert context.can_create_capsule() is True

    def test_can_create_capsule_at_limit(self):
        """Test capsule creation at limit."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            limits=TenantLimits(max_capsules=100),
        )
        context.current_capsule_count = 100

        assert context.can_create_capsule() is False

    def test_can_create_capsule_unlimited(self):
        """Test capsule creation with unlimited."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            limits=TenantLimits(max_capsules=-1),
        )
        context.current_capsule_count = 1000000

        assert context.can_create_capsule() is True

    def test_can_add_user_within_limit(self):
        """Test user addition within limit."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            limits=TenantLimits(max_users=10),
        )
        context.current_user_count = 5

        assert context.can_add_user() is True

    def test_can_add_user_at_limit(self):
        """Test user addition at limit."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            limits=TenantLimits(max_users=10),
        )
        context.current_user_count = 10

        assert context.can_add_user() is False

    def test_has_feature(self):
        """Test feature check."""
        context = TenantContext(
            tenant_id="t1",
            tenant_name="Test",
            features={"ghost_council", "custom_overlays"},
        )

        assert context.has_feature("ghost_council") is True
        assert context.has_feature("custom_overlays") is True
        assert context.has_feature("nonexistent") is False


class TestTenantIsolator:
    """Tests for TenantIsolator class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.strict_mode = True
        config.audit_cross_tenant_attempts = True
        return config

    @pytest.fixture
    def isolator(self, mock_config):
        """Create an isolator instance."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            return TenantIsolator()

    @pytest.fixture
    def tenant_context(self):
        """Create a tenant context."""
        return TenantContext(
            tenant_id="tenant_test",
            tenant_name="Test Tenant",
            tier=TenantTier.STANDARD,
            limits=TenantLimits.for_tier(TenantTier.STANDARD),
        )

    def test_isolator_creation(self, isolator):
        """Test isolator creation."""
        assert isolator._tenants == {}
        assert isolator._cross_tenant_attempts == []

    def test_register_tenant(self, isolator, tenant_context):
        """Test registering a tenant."""
        isolator.register_tenant(tenant_context)

        assert tenant_context.tenant_id in isolator._tenants
        assert isolator._tenants[tenant_context.tenant_id] == tenant_context

    def test_get_tenant(self, isolator, tenant_context):
        """Test getting a tenant."""
        isolator.register_tenant(tenant_context)

        result = isolator.get_tenant(tenant_context.tenant_id)

        assert result == tenant_context

    def test_get_tenant_not_found(self, isolator):
        """Test getting nonexistent tenant."""
        result = isolator.get_tenant("nonexistent")

        assert result is None

    def test_set_current_tenant(self, isolator, tenant_context):
        """Test setting current tenant."""
        isolator.set_current_tenant(tenant_context)

        assert isolator.get_current_tenant() == tenant_context

    def test_clear_current_tenant(self, isolator, tenant_context):
        """Test clearing current tenant."""
        isolator.set_current_tenant(tenant_context)
        isolator.clear_current_tenant()

        assert isolator.get_current_tenant() is None

    def test_validate_access_same_tenant(self, isolator, tenant_context):
        """Test access validation for same tenant."""
        isolator.set_current_tenant(tenant_context)

        result = isolator.validate_access(tenant_context.tenant_id)

        assert result is True

    def test_validate_access_different_tenant_strict(self, isolator, mock_config, tenant_context):
        """Test access validation for different tenant in strict mode."""
        mock_config.strict_mode = True
        isolator.set_current_tenant(tenant_context)

        with pytest.raises(TenantIsolationError):
            isolator.validate_access("other_tenant")

    def test_validate_access_different_tenant_non_strict(self, mock_config, tenant_context):
        """Test access validation for different tenant in non-strict mode."""
        mock_config.strict_mode = False

        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            isolator = TenantIsolator()
            isolator.set_current_tenant(tenant_context)

            result = isolator.validate_access("other_tenant")

            assert result is False

    def test_validate_access_no_tenant_context_strict(self, isolator, mock_config):
        """Test access validation with no context in strict mode."""
        mock_config.strict_mode = True

        with pytest.raises(TenantIsolationError):
            isolator.validate_access("any_tenant")

    def test_validate_access_disabled(self, mock_config, tenant_context):
        """Test access validation when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            isolator = TenantIsolator()

            result = isolator.validate_access("any_tenant")

            assert result is True

    def test_check_quota_capsules_within(self, isolator, tenant_context):
        """Test quota check within limits."""
        tenant_context.current_capsule_count = 5000
        isolator.set_current_tenant(tenant_context)

        result = isolator.check_quota("capsules", 100)

        assert result is True

    def test_check_quota_capsules_exceeded(self, isolator, tenant_context):
        """Test quota check when exceeded."""
        tenant_context.current_capsule_count = 9900
        isolator.set_current_tenant(tenant_context)

        with pytest.raises(TenantQuotaExceededError):
            isolator.check_quota("capsules", 200)

    def test_check_quota_users_exceeded(self, isolator, tenant_context):
        """Test user quota exceeded."""
        tenant_context.current_user_count = 50
        isolator.set_current_tenant(tenant_context)

        with pytest.raises(TenantQuotaExceededError):
            isolator.check_quota("users", 5)

    def test_check_quota_storage_exceeded(self, isolator, tenant_context):
        """Test storage quota exceeded."""
        tenant_context.current_storage_mb = 1000
        isolator.set_current_tenant(tenant_context)

        with pytest.raises(TenantQuotaExceededError):
            isolator.check_quota("storage", 100)

    def test_check_quota_disabled(self, mock_config):
        """Test quota check when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            isolator = TenantIsolator()

            result = isolator.check_quota("capsules", 1000000)

            assert result is True

    def test_get_tenant_filter(self, isolator, tenant_context):
        """Test getting tenant filter."""
        isolator.set_current_tenant(tenant_context)

        filter_dict = isolator.get_tenant_filter()

        assert filter_dict == {"tenant_id": tenant_context.tenant_id}

    def test_get_tenant_filter_no_context(self, isolator):
        """Test getting tenant filter without context."""
        filter_dict = isolator.get_tenant_filter()

        assert filter_dict is None

    def test_get_tenant_filter_disabled(self, mock_config):
        """Test getting tenant filter when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            isolator = TenantIsolator()

            filter_dict = isolator.get_tenant_filter()

            assert filter_dict is None

    def test_apply_tenant_filter(self, isolator, tenant_context):
        """Test applying tenant filter to query."""
        isolator.set_current_tenant(tenant_context)

        query = "MATCH (n:Capsule) WHERE n.name = $name RETURN n"
        params = {"name": "test"}

        new_query, new_params = isolator.apply_tenant_filter(query, params)

        assert "__tenant_filter_id" in new_params
        assert new_params["__tenant_filter_id"] == tenant_context.tenant_id
        assert "tenant_id" in new_query.lower()

    def test_apply_tenant_filter_invalid_tenant_id(self, isolator, mock_config):
        """Test that invalid tenant ID format raises error."""
        bad_context = TenantContext(
            tenant_id="invalid; DROP TABLE users;",  # Invalid format
            tenant_name="Bad Tenant",
        )
        isolator.set_current_tenant(bad_context)

        with pytest.raises(TenantIsolationError, match="Invalid tenant ID format"):
            isolator.apply_tenant_filter("MATCH (n) RETURN n", {})

    def test_cross_tenant_audit_logging(self, isolator, mock_config, tenant_context):
        """Test that cross-tenant attempts are logged."""
        mock_config.strict_mode = False  # Don't raise exception
        isolator.set_current_tenant(tenant_context)

        isolator.validate_access("other_tenant", operation="read")

        audit_log = isolator.get_audit_log()
        assert len(audit_log) > 0
        assert audit_log[0]["source_tenant"] == tenant_context.tenant_id
        assert audit_log[0]["target_tenant"] == "other_tenant"

    def test_audit_log_bounded(self, isolator, mock_config, tenant_context):
        """Test that audit log is bounded."""
        mock_config.strict_mode = False
        isolator.set_current_tenant(tenant_context)

        # Generate many cross-tenant attempts
        for i in range(1100):
            isolator.validate_access(f"tenant_{i}", operation="read")

        audit_log = isolator.get_audit_log()
        assert len(audit_log) <= 1000


class TestRequireTenantDecorator:
    """Tests for require_tenant decorator."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.strict_mode = True
        return config

    def test_require_tenant_sync_no_context(self, mock_config):
        """Test sync function without tenant context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                @require_tenant
                def my_function():
                    return "result"

                with pytest.raises(TenantIsolationError):
                    my_function()

    def test_require_tenant_sync_with_context(self, mock_config):
        """Test sync function with tenant context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                isolator = get_tenant_isolator()
                context = TenantContext(tenant_id="t1", tenant_name="Test")
                isolator.set_current_tenant(context)

                @require_tenant
                def my_function():
                    return "result"

                result = my_function()
                assert result == "result"

                isolator.clear_current_tenant()

    @pytest.mark.asyncio
    async def test_require_tenant_async_no_context(self, mock_config):
        """Test async function without tenant context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                @require_tenant
                async def my_async_function():
                    return "async_result"

                with pytest.raises(TenantIsolationError):
                    await my_async_function()


class TestTenantScopeContextManager:
    """Tests for tenant_scope context manager."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.strict_mode = True
        return config

    def test_tenant_scope_sets_context(self, mock_config):
        """Test that tenant_scope sets context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                isolator = get_tenant_isolator()
                context = TenantContext(tenant_id="t1", tenant_name="Test")

                with tenant_scope(context) as ctx:
                    assert ctx == context
                    assert isolator.get_current_tenant() == context

    def test_tenant_scope_restores_previous(self, mock_config):
        """Test that tenant_scope restores previous context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                isolator = get_tenant_isolator()
                original = TenantContext(tenant_id="original", tenant_name="Original")
                nested = TenantContext(tenant_id="nested", tenant_name="Nested")

                isolator.set_current_tenant(original)

                with tenant_scope(nested):
                    assert isolator.get_current_tenant() == nested

                assert isolator.get_current_tenant() == original

    def test_tenant_scope_clears_if_no_previous(self, mock_config):
        """Test that tenant_scope clears if no previous context."""
        with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
            mock.return_value.tenant_isolation = mock_config
            with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
                isolator = get_tenant_isolator()
                context = TenantContext(tenant_id="t1", tenant_name="Test")

                with tenant_scope(context):
                    assert isolator.get_current_tenant() == context

                assert isolator.get_current_tenant() is None


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_tenant_isolator(self):
        """Test getting global tenant isolator."""
        with patch("forge.resilience.security.tenant_isolation._tenant_isolator", None):
            with patch("forge.resilience.security.tenant_isolation.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.tenant_isolation.enabled = True
                mock.return_value = mock_config

                isolator = get_tenant_isolator()

                assert isinstance(isolator, TenantIsolator)
