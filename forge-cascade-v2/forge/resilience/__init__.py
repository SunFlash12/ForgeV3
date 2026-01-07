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

from forge.resilience.config import (
    ForgeResilienceConfig,
    DeploymentProfile,
    CacheConfig,
    ObservabilityConfig,
    ContentValidationConfig,
    LineageTierConfig,
    PartitionConfig,
    TenantIsolationConfig,
    PrivacyConfig,
    get_resilience_config,
    set_resilience_config,
)

# Caching
from forge.resilience.caching import QueryCache, CacheEntry, CacheInvalidator

# Observability
from forge.resilience.observability import (
    ForgeTracer,
    ForgeMetrics,
    trace_operation,
    get_tracer,
    get_metrics,
)

# Security
from forge.resilience.security import (
    ContentValidator,
    ValidationResult,
    ThreatLevel,
    validate_content,
    TenantContext,
    TenantIsolator,
    PrivacyManager,
    AnonymizationLevel,
)

# Lineage
from forge.resilience.lineage import (
    TieredLineageStorage,
    StorageTier,
    LineageEntry,
    DeltaCompressor,
    LineageDiff,
)

# Partitioning
from forge.resilience.partitioning import (
    PartitionManager,
    Partition,
    PartitionStrategy,
    CrossPartitionQueryExecutor,
    PartitionRouter,
)

# Migration
from forge.resilience.migration import (
    EmbeddingMigrationService,
    MigrationJob,
    MigrationStatus,
    EmbeddingVersionRegistry,
    EmbeddingVersion,
)

# Cold Start
from forge.resilience.cold_start import (
    StarterPackManager,
    StarterPack,
    PackCategory,
    ProgressiveProfiler,
    UserProfile,
)

# Profiles
from forge.resilience.profiles import (
    DeploymentProfileManager,
    apply_profile,
    get_current_profile,
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
