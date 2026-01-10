"""
Forge Resilience Layer
======================

This module implements the Forge Cascade Resilience Specification V1,
providing enterprise-grade reliability, scalability, and operational
resilience capabilities.

Components:
- caching: Query result caching with Redis
- observability: OpenTelemetry integration for tracing and metrics
- security: Content validation, tenant isolation, privacy management
- lineage: Tiered storage and delta-based diff compression
- partitioning: Domain-based graph partitioning and materialized views
- migration: Embedding version management and re-embedding services
- cold_start: Starter packs and progressive profiling
- profiles: Deployment profiles (Lite, Standard, Enterprise)
"""

# Caching
from forge.resilience.caching import CacheEntry, CacheInvalidator, QueryCache

# Cold Start
from forge.resilience.cold_start import (
    PackCategory,
    ProgressiveProfiler,
    StarterPack,
    StarterPackManager,
    UserProfile,
)
from forge.resilience.config import (
    CacheConfig,
    ContentValidationConfig,
    DeploymentProfile,
    ForgeResilienceConfig,
    LineageTierConfig,
    ObservabilityConfig,
    PartitionConfig,
    PrivacyConfig,
    TenantIsolationConfig,
    get_resilience_config,
    set_resilience_config,
)

# Lineage
from forge.resilience.lineage import (
    DeltaCompressor,
    LineageDiff,
    LineageEntry,
    StorageTier,
    TieredLineageStorage,
)

# Migration
from forge.resilience.migration import (
    EmbeddingMigrationService,
    EmbeddingVersion,
    EmbeddingVersionRegistry,
    MigrationJob,
    MigrationStatus,
)

# Observability
from forge.resilience.observability import (
    ForgeMetrics,
    ForgeTracer,
    get_metrics,
    get_tracer,
    trace_operation,
)

# Partitioning
from forge.resilience.partitioning import (
    CrossPartitionQueryExecutor,
    Partition,
    PartitionManager,
    PartitionRouter,
    PartitionStrategy,
)

# Profiles
from forge.resilience.profiles import (
    DeploymentProfileManager,
    apply_profile,
    get_current_profile,
)

# Security
from forge.resilience.security import (
    AnonymizationLevel,
    ContentValidator,
    PrivacyManager,
    TenantContext,
    TenantIsolator,
    ThreatLevel,
    ValidationResult,
    validate_content,
)

__all__ = [
    # Config
    "ForgeResilienceConfig",
    "DeploymentProfile",
    "CacheConfig",
    "ObservabilityConfig",
    "ContentValidationConfig",
    "LineageTierConfig",
    "PartitionConfig",
    "TenantIsolationConfig",
    "PrivacyConfig",
    "get_resilience_config",
    "set_resilience_config",
    # Caching
    "QueryCache",
    "CacheEntry",
    "CacheInvalidator",
    # Observability
    "ForgeTracer",
    "ForgeMetrics",
    "trace_operation",
    "get_tracer",
    "get_metrics",
    # Security
    "ContentValidator",
    "ValidationResult",
    "ThreatLevel",
    "validate_content",
    "TenantContext",
    "TenantIsolator",
    "PrivacyManager",
    "AnonymizationLevel",
    # Lineage
    "TieredLineageStorage",
    "StorageTier",
    "LineageEntry",
    "DeltaCompressor",
    "LineageDiff",
    # Partitioning
    "PartitionManager",
    "Partition",
    "PartitionStrategy",
    "CrossPartitionQueryExecutor",
    "PartitionRouter",
    # Migration
    "EmbeddingMigrationService",
    "MigrationJob",
    "MigrationStatus",
    "EmbeddingVersionRegistry",
    "EmbeddingVersion",
    # Cold Start
    "StarterPackManager",
    "StarterPack",
    "PackCategory",
    "ProgressiveProfiler",
    "UserProfile",
    # Profiles
    "DeploymentProfileManager",
    "apply_profile",
    "get_current_profile",
]
