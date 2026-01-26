"""
Forge Resilience Configuration
==============================

Unified configuration for all resilience components.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class DeploymentProfile(Enum):
    """Predefined deployment configurations for different use cases."""

    LITE = "lite"  # Basic persistence, minimal overhead
    STANDARD = "standard"  # Full features, single-tenant
    ENTERPRISE = "enterprise"  # Multi-tenant, compliance, governance


@dataclass
class CacheConfig:
    """Configuration for query caching system."""

    enabled: bool = True
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    default_ttl_seconds: int = 300  # 5 minutes
    lineage_ttl_seconds: int = 3600  # 1 hour for stable lineage
    search_ttl_seconds: int = 600  # 10 minutes for search results
    max_cached_result_bytes: int = 1048576  # 1MB max per result

    # Cache key patterns
    lineage_key_pattern: str = "forge:lineage:{capsule_id}:{depth}"
    search_key_pattern: str = "forge:search:{query_hash}"
    partition_key_pattern: str = "forge:partition:{partition_id}:stats"
    capsule_key_pattern: str = "forge:capsule:{capsule_id}"


@dataclass
class ObservabilityConfig:
    """Configuration for observability stack."""

    enabled: bool = True
    otlp_endpoint: str = field(
        default_factory=lambda: os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
    )
    service_name: str = "forge-cascade"
    environment: str = field(default_factory=lambda: os.getenv("FORGE_ENV", "development"))
    version: str = "2.0.0"

    enable_tracing: bool = True
    enable_metrics: bool = True
    trace_sample_rate: float = 1.0  # 100% sampling by default


@dataclass
class ContentValidationConfig:
    """Configuration for content validation pipeline."""

    enabled: bool = True
    anomaly_threshold: float = 0.8
    max_content_length: int = 1_000_000  # 1MB
    enable_ml_classification: bool = True
    quarantine_on_threat: bool = True
    log_threats: bool = True


@dataclass
class LineageTierConfig:
    """Configuration for tiered lineage storage."""

    enabled: bool = True

    # Tier boundaries (days)
    tier1_max_age_days: int = 30
    tier2_max_age_days: int = 180

    # Trust level boundaries
    tier1_min_trust: int = 80  # TRUSTED
    tier2_min_trust: int = 60  # STANDARD

    # Storage locations
    hot_storage: str = "neo4j"  # Tier 1
    warm_storage: str = "neo4j"  # Tier 2 (compressed)
    cold_storage: str = "s3"  # Tier 3 archive
    cold_storage_bucket: str = field(
        default_factory=lambda: os.getenv("LINEAGE_S3_BUCKET", "forge-lineage-archive")
    )


@dataclass
class PartitionConfig:
    """Configuration for graph partitioning."""

    enabled: bool = True
    max_capsules_per_partition: int = 50000
    edge_density_threshold: float = 0.1
    auto_rebalance: bool = True
    rebalance_threshold: float = 0.2  # Rebalance if imbalance > 20%


@dataclass
class EmbeddingMigrationConfig:
    """Configuration for embedding migration service."""

    batch_size: int = 100
    delay_seconds: float = 1.0
    cleanup_old_embeddings: bool = True
    cleanup_grace_period_days: int = 30


@dataclass
class TenantIsolationConfig:
    """Configuration for tenant isolation."""

    enabled: bool = False  # Only enabled in Enterprise profile
    strict_mode: bool = True
    audit_cross_tenant_attempts: bool = True


@dataclass
class PrivacyConfig:
    """Configuration for privacy management."""

    enabled: bool = True
    gdpr_compliant: bool = True
    data_retention_days: int = 365 * 7  # 7 years default
    anonymization_enabled: bool = True


@dataclass
class StarterPackConfig:
    """Configuration for starter packs and cold start mitigation."""

    enabled: bool = True
    registry_url: str = "https://registry.forgeecosystem.io/packs"
    auto_import_dependencies: bool = True
    default_trust_level: int = 60  # STANDARD


@dataclass
class RunbookConfig:
    """Configuration for operational runbooks."""

    enabled: bool = True
    auto_execute_safe_steps: bool = False
    notification_channels: list[str] = field(default_factory=list)


@dataclass
class ForgeResilienceConfig:
    """Unified configuration for all resilience components."""

    # Deployment profile
    profile: DeploymentProfile = DeploymentProfile.STANDARD

    # Component configurations
    cache: CacheConfig = field(default_factory=CacheConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    content_validation: ContentValidationConfig = field(default_factory=ContentValidationConfig)
    lineage: LineageTierConfig = field(default_factory=LineageTierConfig)
    partitioning: PartitionConfig = field(default_factory=PartitionConfig)
    embedding_migration: EmbeddingMigrationConfig = field(default_factory=EmbeddingMigrationConfig)
    tenant_isolation: TenantIsolationConfig = field(default_factory=TenantIsolationConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    starter_packs: StarterPackConfig = field(default_factory=StarterPackConfig)
    runbooks: RunbookConfig = field(default_factory=RunbookConfig)

    @classmethod
    def from_environment(cls) -> ForgeResilienceConfig:
        """Load configuration from environment variables."""
        profile_str = os.getenv("FORGE_PROFILE", "standard").lower()
        profile = DeploymentProfile(profile_str)

        # Apply profile-specific defaults
        config = cls(profile=profile)
        config._apply_profile_defaults()

        return config

    def _apply_profile_defaults(self) -> None:
        """Apply defaults based on deployment profile."""
        if self.profile == DeploymentProfile.LITE:
            # Minimal configuration for Lite
            self.observability.enable_tracing = False
            self.content_validation.enable_ml_classification = False
            self.lineage.enabled = False
            self.partitioning.enabled = False
            self.tenant_isolation.enabled = False
            self.runbooks.enabled = False

        elif self.profile == DeploymentProfile.STANDARD:
            # Standard configuration
            self.tenant_isolation.enabled = False

        elif self.profile == DeploymentProfile.ENTERPRISE:
            # Full enterprise configuration
            self.tenant_isolation.enabled = True
            self.tenant_isolation.strict_mode = True
            self.runbooks.auto_execute_safe_steps = True


# Default global configuration
_default_config: ForgeResilienceConfig | None = None


def get_resilience_config() -> ForgeResilienceConfig:
    """Get the global resilience configuration."""
    global _default_config
    if _default_config is None:
        _default_config = ForgeResilienceConfig.from_environment()
    return _default_config


def set_resilience_config(config: ForgeResilienceConfig) -> None:
    """Set the global resilience configuration."""
    global _default_config
    _default_config = config
