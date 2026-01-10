"""
Forge Embedding Migration Service
=================================

Background service for migrating embeddings between model versions.
Ensures seamless transitions when upgrading embedding models.
"""

from forge.resilience.migration.embedding_migration import (
    EmbeddingMigrationService,
    MigrationJob,
    MigrationStatus,
)
from forge.resilience.migration.version_registry import (
    EmbeddingVersion,
    EmbeddingVersionRegistry,
)

__all__ = [
    "EmbeddingMigrationService",
    "MigrationJob",
    "MigrationStatus",
    "EmbeddingVersionRegistry",
    "EmbeddingVersion",
]
