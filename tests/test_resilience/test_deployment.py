"""
Tests for Deployment Profile Management
=======================================

Tests for forge/resilience/profiles/deployment.py
"""

from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.config import DeploymentProfile
from forge.resilience.profiles.deployment import (
    ENTERPRISE_PROFILE,
    LITE_PROFILE,
    STANDARD_PROFILE,
    DeploymentProfileManager,
    DeploymentProfileSpec,
    ProfileCapabilities,
    ProfileLimits,
    apply_profile,
    get_current_profile,
    get_profile_manager,
)


class TestProfileCapabilities:
    """Tests for ProfileCapabilities dataclass."""

    def test_default_capabilities(self):
        """Test default capability values."""
        caps = ProfileCapabilities()

        assert caps.capsule_management is True
        assert caps.lineage_tracking is True
        assert caps.search is True
        assert caps.governance is True
        assert caps.ghost_council is True
        assert caps.overlays is True
        assert caps.custom_overlays is False
        assert caps.caching is True
        assert caps.observability is True
        assert caps.content_validation is True
        assert caps.tiered_storage is True
        assert caps.partitioning is True
        assert caps.multi_tenant is False
        assert caps.audit_logging is True
        assert caps.compliance_frameworks is False
        assert caps.advanced_privacy is False
        assert caps.runbooks is False
        assert caps.auto_remediation is False


class TestProfileLimits:
    """Tests for ProfileLimits dataclass."""

    def test_default_limits(self):
        """Test default limit values."""
        limits = ProfileLimits()

        assert limits.max_capsules == -1  # Unlimited
        assert limits.max_users == -1
        assert limits.max_storage_gb == -1
        assert limits.max_api_calls_per_day == -1
        assert limits.max_lineage_depth == 10
        assert limits.max_search_results == 100
        assert limits.max_concurrent_queries == 50

    def test_custom_limits(self):
        """Test custom limit values."""
        limits = ProfileLimits(
            max_capsules=10000,
            max_users=100,
            max_storage_gb=50,
        )

        assert limits.max_capsules == 10000
        assert limits.max_users == 100
        assert limits.max_storage_gb == 50


class TestDeploymentProfileSpec:
    """Tests for DeploymentProfileSpec dataclass."""

    def test_spec_creation(self):
        """Test creating a deployment profile spec."""
        spec = DeploymentProfileSpec(
            profile=DeploymentProfile.STANDARD,
            name="Test Profile",
            description="A test deployment profile",
            capabilities=ProfileCapabilities(),
            limits=ProfileLimits(),
        )

        assert spec.profile == DeploymentProfile.STANDARD
        assert spec.name == "Test Profile"
        assert spec.description == "A test deployment profile"


class TestPredefinedProfiles:
    """Tests for predefined profile configurations."""

    def test_lite_profile(self):
        """Test Lite profile configuration."""
        assert LITE_PROFILE.profile == DeploymentProfile.LITE
        assert LITE_PROFILE.name == "Forge Lite"
        assert LITE_PROFILE.capabilities.ghost_council is False
        assert LITE_PROFILE.capabilities.observability is False
        assert LITE_PROFILE.capabilities.tiered_storage is False
        assert LITE_PROFILE.capabilities.partitioning is False
        assert LITE_PROFILE.limits.max_capsules == 10000
        assert LITE_PROFILE.limits.max_users == 10

    def test_standard_profile(self):
        """Test Standard profile configuration."""
        assert STANDARD_PROFILE.profile == DeploymentProfile.STANDARD
        assert STANDARD_PROFILE.name == "Forge Standard"
        assert STANDARD_PROFILE.capabilities.ghost_council is True
        assert STANDARD_PROFILE.capabilities.observability is True
        assert STANDARD_PROFILE.capabilities.multi_tenant is False
        assert STANDARD_PROFILE.limits.max_capsules == 1000000
        assert STANDARD_PROFILE.limits.max_users == 1000

    def test_enterprise_profile(self):
        """Test Enterprise profile configuration."""
        assert ENTERPRISE_PROFILE.profile == DeploymentProfile.ENTERPRISE
        assert ENTERPRISE_PROFILE.name == "Forge Enterprise"
        assert ENTERPRISE_PROFILE.capabilities.ghost_council is True
        assert ENTERPRISE_PROFILE.capabilities.multi_tenant is True
        assert ENTERPRISE_PROFILE.capabilities.compliance_frameworks is True
        assert ENTERPRISE_PROFILE.capabilities.auto_remediation is True
        assert ENTERPRISE_PROFILE.limits.max_capsules == -1  # Unlimited


class TestDeploymentProfileManager:
    """Tests for DeploymentProfileManager class."""

    @pytest.fixture
    def manager(self):
        """Create a profile manager instance."""
        return DeploymentProfileManager()

    def test_manager_creation(self, manager):
        """Test manager creation."""
        assert manager._current_profile is None
        assert manager._current_config is None
        assert len(manager._profiles) == 3

    def test_get_profile_spec(self, manager):
        """Test getting profile specification."""
        spec = manager.get_profile_spec(DeploymentProfile.LITE)

        assert spec == LITE_PROFILE

    def test_list_profiles(self, manager):
        """Test listing all profiles."""
        profiles = manager.list_profiles()

        assert len(profiles) == 3
        profile_types = [p.profile for p in profiles]
        assert DeploymentProfile.LITE in profile_types
        assert DeploymentProfile.STANDARD in profile_types
        assert DeploymentProfile.ENTERPRISE in profile_types

    def test_apply_lite_profile(self, manager):
        """Test applying Lite profile."""
        config = manager.apply_profile(DeploymentProfile.LITE)

        assert config.profile == DeploymentProfile.LITE
        assert config.observability.enable_tracing is False
        assert config.content_validation.enable_ml_classification is False
        assert config.lineage.tier1_max_age_days == 30

    def test_apply_standard_profile(self, manager):
        """Test applying Standard profile."""
        config = manager.apply_profile(DeploymentProfile.STANDARD)

        assert config.profile == DeploymentProfile.STANDARD
        assert config.observability.enable_tracing is True
        assert config.tenant_isolation.enabled is False

    def test_apply_enterprise_profile(self, manager):
        """Test applying Enterprise profile."""
        config = manager.apply_profile(DeploymentProfile.ENTERPRISE)

        assert config.profile == DeploymentProfile.ENTERPRISE
        assert config.tenant_isolation.enabled is True
        assert config.tenant_isolation.strict_mode is True
        assert config.observability.trace_sample_rate == 1.0

    def test_apply_profile_with_overrides(self, manager):
        """Test applying profile with custom overrides."""
        overrides = {
            "cache.enabled": False,
            "observability.enable_metrics": False,
        }

        config = manager.apply_profile(DeploymentProfile.STANDARD, custom_overrides=overrides)

        assert config.cache.enabled is False
        assert config.observability.enable_metrics is False

    def test_apply_profile_sets_current(self, manager):
        """Test that applying profile sets current."""
        manager.apply_profile(DeploymentProfile.STANDARD)

        assert manager._current_profile == DeploymentProfile.STANDARD
        assert manager._current_config is not None

    def test_get_current_profile(self, manager):
        """Test getting current profile."""
        assert manager.get_current_profile() is None

        manager.apply_profile(DeploymentProfile.ENTERPRISE)

        assert manager.get_current_profile() == DeploymentProfile.ENTERPRISE

    def test_get_current_config(self, manager):
        """Test getting current configuration."""
        assert manager.get_current_config() is None

        config = manager.apply_profile(DeploymentProfile.STANDARD)

        assert manager.get_current_config() == config

    def test_is_feature_enabled_no_profile(self, manager):
        """Test feature check when no profile is set."""
        result = manager.is_feature_enabled("ghost_council")

        assert result is False

    def test_is_feature_enabled(self, manager):
        """Test checking if feature is enabled."""
        manager.apply_profile(DeploymentProfile.ENTERPRISE)

        assert manager.is_feature_enabled("ghost_council") is True
        assert manager.is_feature_enabled("multi_tenant") is True
        assert manager.is_feature_enabled("auto_remediation") is True

    def test_is_feature_enabled_lite(self, manager):
        """Test feature check for Lite profile."""
        manager.apply_profile(DeploymentProfile.LITE)

        assert manager.is_feature_enabled("ghost_council") is False
        assert manager.is_feature_enabled("observability") is False

    def test_check_limit_no_profile(self, manager):
        """Test limit check when no profile is set."""
        result = manager.check_limit("max_capsules", 100)

        assert result is True

    def test_check_limit_within(self, manager):
        """Test limit check within bounds."""
        manager.apply_profile(DeploymentProfile.LITE)

        result = manager.check_limit("max_capsules", 5000)

        assert result is True

    def test_check_limit_exceeded(self, manager):
        """Test limit check when exceeded."""
        manager.apply_profile(DeploymentProfile.LITE)

        result = manager.check_limit("max_capsules", 15000)

        assert result is False

    def test_check_limit_unlimited(self, manager):
        """Test limit check for unlimited."""
        manager.apply_profile(DeploymentProfile.ENTERPRISE)

        result = manager.check_limit("max_capsules", 1000000)

        assert result is True  # -1 means unlimited

    def test_validate_profile_requirements_pass(self, manager):
        """Test validating requirements that pass."""
        system_resources = {
            "cpu_cores": 8,
            "memory_gb": 32,
        }

        result = manager.validate_profile_requirements(
            DeploymentProfile.STANDARD, system_resources
        )

        assert result["passed"] is True
        assert result["profile"] == "standard"

    def test_validate_profile_requirements_warnings(self, manager):
        """Test validating requirements with warnings."""
        system_resources = {
            "cpu_cores": 2,
            "memory_gb": 8,
        }

        result = manager.validate_profile_requirements(
            DeploymentProfile.STANDARD, system_resources
        )

        assert len(result["warnings"]) > 0

    def test_validate_profile_requirements_fail(self, manager):
        """Test validating requirements that fail."""
        system_resources = {
            "cpu_cores": 1,
            "memory_gb": 2,  # Below recommended
        }

        result = manager.validate_profile_requirements(
            DeploymentProfile.STANDARD, system_resources
        )

        assert result["passed"] is False


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_profile_manager(self):
        """Test getting global profile manager."""
        with patch("forge.resilience.profiles.deployment._profile_manager", None):
            manager = get_profile_manager()

            assert isinstance(manager, DeploymentProfileManager)

    def test_apply_profile_function(self):
        """Test apply_profile convenience function."""
        with patch("forge.resilience.profiles.deployment._profile_manager", None):
            config = apply_profile(DeploymentProfile.LITE)

            assert config.profile == DeploymentProfile.LITE

    def test_get_current_profile_function(self):
        """Test get_current_profile convenience function."""
        with patch("forge.resilience.profiles.deployment._profile_manager", None):
            # Initially no profile
            result = get_current_profile()
            assert result is None

            # After applying
            apply_profile(DeploymentProfile.STANDARD)
            result = get_current_profile()
            assert result == DeploymentProfile.STANDARD
