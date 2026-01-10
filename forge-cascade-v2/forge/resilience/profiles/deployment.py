"""
Deployment Profile Management
=============================

Manages deployment profiles for Forge installations.
Provides pre-configured settings for different deployment scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from forge.resilience.config import (
    CacheConfig,
    ContentValidationConfig,
    DeploymentProfile,
    ForgeResilienceConfig,
    LineageTierConfig,
    ObservabilityConfig,
    PartitionConfig,
    PrivacyConfig,
    RunbookConfig,
    StarterPackConfig,
    TenantIsolationConfig,
)

logger = structlog.get_logger(__name__)


@dataclass
class ProfileCapabilities:
    """Capabilities enabled for a deployment profile."""

    # Core features
    capsule_management: bool = True
    lineage_tracking: bool = True
    search: bool = True

    # Advanced features
    governance: bool = True
    ghost_council: bool = True
    overlays: bool = True
    custom_overlays: bool = False

    # Resilience features
    caching: bool = True
    observability: bool = True
    content_validation: bool = True
    tiered_storage: bool = True
    partitioning: bool = True

    # Enterprise features
    multi_tenant: bool = False
    audit_logging: bool = True
    compliance_frameworks: bool = False
    advanced_privacy: bool = False

    # Operations
    runbooks: bool = False
    auto_remediation: bool = False


@dataclass
class ProfileLimits:
    """Resource limits for a deployment profile."""

    max_capsules: int = -1           # -1 = unlimited
    max_users: int = -1
    max_storage_gb: int = -1
    max_api_calls_per_day: int = -1
    max_lineage_depth: int = 10
    max_search_results: int = 100
    max_concurrent_queries: int = 50


@dataclass
class DeploymentProfileSpec:
    """Complete specification for a deployment profile."""

    profile: DeploymentProfile
    name: str
    description: str
    capabilities: ProfileCapabilities
    limits: ProfileLimits
    recommended_resources: dict[str, str] = field(default_factory=dict)


# Profile specifications
LITE_PROFILE = DeploymentProfileSpec(
    profile=DeploymentProfile.LITE,
    name="Forge Lite",
    description="Lightweight deployment for personal use or small teams. Minimal infrastructure requirements.",
    capabilities=ProfileCapabilities(
        ghost_council=False,
        custom_overlays=False,
        observability=False,
        tiered_storage=False,
        partitioning=False,
        multi_tenant=False,
        compliance_frameworks=False,
        advanced_privacy=False,
        runbooks=False,
        auto_remediation=False,
    ),
    limits=ProfileLimits(
        max_capsules=10000,
        max_users=10,
        max_storage_gb=10,
        max_api_calls_per_day=10000,
        max_lineage_depth=5,
        max_search_results=50,
        max_concurrent_queries=10,
    ),
    recommended_resources={
        "cpu": "2 cores",
        "memory": "4 GB",
        "storage": "20 GB SSD",
        "neo4j": "Community Edition",
    }
)

STANDARD_PROFILE = DeploymentProfileSpec(
    profile=DeploymentProfile.STANDARD,
    name="Forge Standard",
    description="Full-featured deployment for teams and organizations. Single-tenant with all core features.",
    capabilities=ProfileCapabilities(
        ghost_council=True,
        custom_overlays=True,
        observability=True,
        tiered_storage=True,
        partitioning=True,
        multi_tenant=False,
        compliance_frameworks=False,
        advanced_privacy=True,
        runbooks=True,
        auto_remediation=False,
    ),
    limits=ProfileLimits(
        max_capsules=1000000,
        max_users=1000,
        max_storage_gb=500,
        max_api_calls_per_day=1000000,
        max_lineage_depth=10,
        max_search_results=100,
        max_concurrent_queries=50,
    ),
    recommended_resources={
        "cpu": "8 cores",
        "memory": "32 GB",
        "storage": "500 GB SSD",
        "neo4j": "Enterprise Edition",
        "redis": "6 GB",
    }
)

ENTERPRISE_PROFILE = DeploymentProfileSpec(
    profile=DeploymentProfile.ENTERPRISE,
    name="Forge Enterprise",
    description="Enterprise deployment with multi-tenancy, compliance, and advanced governance.",
    capabilities=ProfileCapabilities(
        ghost_council=True,
        custom_overlays=True,
        observability=True,
        tiered_storage=True,
        partitioning=True,
        multi_tenant=True,
        compliance_frameworks=True,
        advanced_privacy=True,
        runbooks=True,
        auto_remediation=True,
    ),
    limits=ProfileLimits(
        max_capsules=-1,
        max_users=-1,
        max_storage_gb=-1,
        max_api_calls_per_day=-1,
        max_lineage_depth=-1,
        max_search_results=1000,
        max_concurrent_queries=500,
    ),
    recommended_resources={
        "cpu": "32+ cores",
        "memory": "128+ GB",
        "storage": "2+ TB NVMe",
        "neo4j": "Enterprise Edition (cluster)",
        "redis": "32+ GB (cluster)",
        "s3": "For cold storage",
    }
)


class DeploymentProfileManager:
    """
    Manages deployment profile configuration and validation.

    Features:
    - Profile selection and configuration
    - Feature flag management
    - Limit enforcement
    - Profile migration
    """

    def __init__(self):
        self._profiles: dict[DeploymentProfile, DeploymentProfileSpec] = {
            DeploymentProfile.LITE: LITE_PROFILE,
            DeploymentProfile.STANDARD: STANDARD_PROFILE,
            DeploymentProfile.ENTERPRISE: ENTERPRISE_PROFILE,
        }
        self._current_profile: DeploymentProfile | None = None
        self._current_config: ForgeResilienceConfig | None = None

    def get_profile_spec(
        self,
        profile: DeploymentProfile
    ) -> DeploymentProfileSpec:
        """Get specification for a profile."""
        return self._profiles[profile]

    def list_profiles(self) -> list[DeploymentProfileSpec]:
        """List all available profiles."""
        return list(self._profiles.values())

    def apply_profile(
        self,
        profile: DeploymentProfile,
        custom_overrides: dict[str, Any] | None = None
    ) -> ForgeResilienceConfig:
        """
        Apply a deployment profile.

        Args:
            profile: Profile to apply
            custom_overrides: Optional overrides for specific settings

        Returns:
            Configured ForgeResilienceConfig
        """
        spec = self._profiles[profile]

        # Build configuration based on profile
        config = ForgeResilienceConfig(profile=profile)

        # Apply profile-specific settings
        self._apply_cache_config(config, spec)
        self._apply_observability_config(config, spec)
        self._apply_validation_config(config, spec)
        self._apply_lineage_config(config, spec)
        self._apply_partition_config(config, spec)
        self._apply_tenant_config(config, spec)
        self._apply_privacy_config(config, spec)
        self._apply_starter_pack_config(config, spec)
        self._apply_runbook_config(config, spec)

        # Apply custom overrides
        if custom_overrides:
            self._apply_overrides(config, custom_overrides)

        self._current_profile = profile
        self._current_config = config

        logger.info(
            "deployment_profile_applied",
            profile=profile.value,
            name=spec.name
        )

        return config

    def _apply_cache_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply cache configuration for profile."""
        config.cache = CacheConfig(
            enabled=spec.capabilities.caching,
            default_ttl_seconds=300 if spec.profile == DeploymentProfile.LITE else 600,
        )

    def _apply_observability_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply observability configuration for profile."""
        config.observability = ObservabilityConfig(
            enabled=spec.capabilities.observability,
            enable_tracing=spec.profile != DeploymentProfile.LITE,
            enable_metrics=spec.capabilities.observability,
            trace_sample_rate=1.0 if spec.profile == DeploymentProfile.ENTERPRISE else 0.1,
        )

    def _apply_validation_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply content validation configuration for profile."""
        config.content_validation = ContentValidationConfig(
            enabled=spec.capabilities.content_validation,
            enable_ml_classification=spec.profile != DeploymentProfile.LITE,
            quarantine_on_threat=spec.profile == DeploymentProfile.ENTERPRISE,
        )

    def _apply_lineage_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply lineage configuration for profile."""
        config.lineage = LineageTierConfig(
            enabled=spec.capabilities.tiered_storage,
            tier1_max_age_days=30 if spec.profile == DeploymentProfile.LITE else 90,
            tier2_max_age_days=180 if spec.profile == DeploymentProfile.LITE else 365,
        )

    def _apply_partition_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply partitioning configuration for profile."""
        config.partitioning = PartitionConfig(
            enabled=spec.capabilities.partitioning,
            max_capsules_per_partition=50000 if spec.profile == DeploymentProfile.ENTERPRISE else 10000,
            auto_rebalance=spec.profile == DeploymentProfile.ENTERPRISE,
        )

    def _apply_tenant_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply tenant isolation configuration for profile."""
        config.tenant_isolation = TenantIsolationConfig(
            enabled=spec.capabilities.multi_tenant,
            strict_mode=spec.profile == DeploymentProfile.ENTERPRISE,
            audit_cross_tenant_attempts=spec.capabilities.multi_tenant,
        )

    def _apply_privacy_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply privacy configuration for profile."""
        config.privacy = PrivacyConfig(
            enabled=spec.capabilities.advanced_privacy,
            gdpr_compliant=spec.profile != DeploymentProfile.LITE,
            anonymization_enabled=spec.capabilities.advanced_privacy,
        )

    def _apply_starter_pack_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply starter pack configuration for profile."""
        config.starter_packs = StarterPackConfig(
            enabled=True,
            auto_import_dependencies=True,
        )

    def _apply_runbook_config(
        self,
        config: ForgeResilienceConfig,
        spec: DeploymentProfileSpec
    ) -> None:
        """Apply runbook configuration for profile."""
        config.runbooks = RunbookConfig(
            enabled=spec.capabilities.runbooks,
            auto_execute_safe_steps=spec.capabilities.auto_remediation,
        )

    def _apply_overrides(
        self,
        config: ForgeResilienceConfig,
        overrides: dict[str, Any]
    ) -> None:
        """Apply custom overrides to configuration."""
        for key, value in overrides.items():
            if '.' in key:
                # Nested key like "cache.enabled"
                parts = key.split('.')
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part, None)
                    if obj is None:
                        break
                if obj is not None:
                    setattr(obj, parts[-1], value)
            else:
                if hasattr(config, key):
                    setattr(config, key, value)

    def validate_profile_requirements(
        self,
        profile: DeploymentProfile,
        system_resources: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate system resources against profile requirements.

        Args:
            profile: Profile to validate
            system_resources: Available system resources

        Returns:
            Validation result with any warnings
        """
        spec = self._profiles[profile]
        warnings = []
        passed = True

        # Check CPU
        if "cpu_cores" in system_resources:
            recommended_cpu = int(spec.recommended_resources.get("cpu", "2").split()[0])
            if system_resources["cpu_cores"] < recommended_cpu:
                warnings.append(
                    f"CPU cores ({system_resources['cpu_cores']}) below recommended ({recommended_cpu})"
                )

        # Check memory
        if "memory_gb" in system_resources:
            recommended_mem = int(spec.recommended_resources.get("memory", "4").split()[0])
            if system_resources["memory_gb"] < recommended_mem:
                warnings.append(
                    f"Memory ({system_resources['memory_gb']} GB) below recommended ({recommended_mem} GB)"
                )
                passed = False

        return {
            "passed": passed,
            "warnings": warnings,
            "profile": profile.value,
            "recommended": spec.recommended_resources,
        }

    def get_current_profile(self) -> DeploymentProfile | None:
        """Get the currently applied profile."""
        return self._current_profile

    def get_current_config(self) -> ForgeResilienceConfig | None:
        """Get the current configuration."""
        return self._current_config

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled in current profile."""
        if not self._current_profile:
            return False

        spec = self._profiles[self._current_profile]
        return getattr(spec.capabilities, feature, False)

    def check_limit(self, limit_name: str, current_value: int) -> bool:
        """Check if a limit has been reached."""
        if not self._current_profile:
            return True

        spec = self._profiles[self._current_profile]
        limit_value = getattr(spec.limits, limit_name, -1)

        if limit_value < 0:
            return True  # Unlimited

        return current_value < limit_value


# Global instance
_profile_manager: DeploymentProfileManager | None = None


def get_profile_manager() -> DeploymentProfileManager:
    """Get or create the global profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = DeploymentProfileManager()
    return _profile_manager


def apply_profile(
    profile: DeploymentProfile,
    overrides: dict[str, Any] | None = None
) -> ForgeResilienceConfig:
    """Convenience function to apply a deployment profile."""
    manager = get_profile_manager()
    return manager.apply_profile(profile, overrides)


def get_current_profile() -> DeploymentProfile | None:
    """Get the currently applied profile."""
    manager = get_profile_manager()
    return manager.get_current_profile()
