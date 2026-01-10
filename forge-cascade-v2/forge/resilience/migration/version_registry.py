"""
Embedding Version Registry
==========================

Tracks embedding model versions and their metadata.
Enables seamless transitions between embedding model generations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ModelProvider(Enum):
    """Embedding model providers."""

    OPENAI = "openai"
    COHERE = "cohere"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    CUSTOM = "custom"


class VersionStatus(Enum):
    """Status of an embedding version."""

    ACTIVE = "active"           # Currently in use
    DEPRECATED = "deprecated"   # Still supported but not recommended
    RETIRED = "retired"         # No longer supported
    TESTING = "testing"         # In testing phase


@dataclass
class EmbeddingVersion:
    """Represents a specific embedding model version."""

    version_id: str
    model_name: str
    provider: ModelProvider
    dimensions: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: VersionStatus = VersionStatus.ACTIVE

    # Model configuration
    max_tokens: int = 8192
    batch_size: int = 100
    normalize: bool = True

    # Performance characteristics
    avg_latency_ms: float = 50.0
    cost_per_1k_tokens: float = 0.0001

    # Compatibility
    compatible_versions: list[str] = field(default_factory=list)
    migration_path_from: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version_id": self.version_id,
            "model_name": self.model_name,
            "provider": self.provider.value,
            "dimensions": self.dimensions,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "max_tokens": self.max_tokens,
            "batch_size": self.batch_size,
            "normalize": self.normalize,
            "avg_latency_ms": self.avg_latency_ms,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "compatible_versions": self.compatible_versions,
            "migration_path_from": self.migration_path_from,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddingVersion:
        """Create from dictionary."""
        return cls(
            version_id=data["version_id"],
            model_name=data["model_name"],
            provider=ModelProvider(data["provider"]),
            dimensions=data["dimensions"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=VersionStatus(data.get("status", "active")),
            max_tokens=data.get("max_tokens", 8192),
            batch_size=data.get("batch_size", 100),
            normalize=data.get("normalize", True),
            avg_latency_ms=data.get("avg_latency_ms", 50.0),
            cost_per_1k_tokens=data.get("cost_per_1k_tokens", 0.0001),
            compatible_versions=data.get("compatible_versions", []),
            migration_path_from=data.get("migration_path_from", []),
            metadata=data.get("metadata", {}),
        )


class EmbeddingVersionRegistry:
    """
    Registry for tracking embedding model versions.

    Manages version lifecycle, compatibility, and migration paths.
    """

    def __init__(self):
        self._versions: dict[str, EmbeddingVersion] = {}
        self._active_version: str | None = None
        self._default_version: str | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize with default versions."""
        if self._initialized:
            return

        # Register default embedding versions
        default_versions = [
            EmbeddingVersion(
                version_id="text-embedding-ada-002",
                model_name="text-embedding-ada-002",
                provider=ModelProvider.OPENAI,
                dimensions=1536,
                status=VersionStatus.DEPRECATED,
                avg_latency_ms=30.0,
                cost_per_1k_tokens=0.0001,
                migration_path_from=[],
            ),
            EmbeddingVersion(
                version_id="text-embedding-3-small",
                model_name="text-embedding-3-small",
                provider=ModelProvider.OPENAI,
                dimensions=1536,
                status=VersionStatus.ACTIVE,
                avg_latency_ms=25.0,
                cost_per_1k_tokens=0.00002,
                migration_path_from=["text-embedding-ada-002"],
            ),
            EmbeddingVersion(
                version_id="text-embedding-3-large",
                model_name="text-embedding-3-large",
                provider=ModelProvider.OPENAI,
                dimensions=3072,
                status=VersionStatus.ACTIVE,
                avg_latency_ms=40.0,
                cost_per_1k_tokens=0.00013,
                migration_path_from=["text-embedding-ada-002", "text-embedding-3-small"],
            ),
            EmbeddingVersion(
                version_id="all-MiniLM-L6-v2",
                model_name="all-MiniLM-L6-v2",
                provider=ModelProvider.SENTENCE_TRANSFORMERS,
                dimensions=384,
                status=VersionStatus.ACTIVE,
                max_tokens=512,
                avg_latency_ms=10.0,
                cost_per_1k_tokens=0.0,  # Local model
            ),
        ]

        for version in default_versions:
            self.register(version)

        # Set defaults
        self._active_version = "text-embedding-3-small"
        self._default_version = "text-embedding-3-small"

        self._initialized = True
        logger.info(
            "embedding_registry_initialized",
            version_count=len(self._versions),
            active_version=self._active_version
        )

    def register(self, version: EmbeddingVersion) -> None:
        """
        Register a new embedding version.

        Args:
            version: Version to register
        """
        self._versions[version.version_id] = version
        logger.debug(
            "embedding_version_registered",
            version_id=version.version_id,
            model=version.model_name
        )

    def get(self, version_id: str) -> EmbeddingVersion | None:
        """Get a specific version by ID."""
        return self._versions.get(version_id)

    def get_active(self) -> EmbeddingVersion | None:
        """Get the currently active version."""
        if self._active_version:
            return self._versions.get(self._active_version)
        return None

    def get_default(self) -> EmbeddingVersion | None:
        """Get the default version."""
        if self._default_version:
            return self._versions.get(self._default_version)
        return None

    def set_active(self, version_id: str) -> bool:
        """
        Set the active embedding version.

        Args:
            version_id: Version to activate

        Returns:
            True if successfully activated
        """
        if version_id not in self._versions:
            logger.warning(
                "unknown_version_activation_attempt",
                version_id=version_id
            )
            return False

        version = self._versions[version_id]
        if version.status == VersionStatus.RETIRED:
            logger.warning(
                "retired_version_activation_attempt",
                version_id=version_id
            )
            return False

        self._active_version = version_id
        logger.info(
            "embedding_version_activated",
            version_id=version_id
        )
        return True

    def deprecate(self, version_id: str) -> bool:
        """Mark a version as deprecated."""
        if version_id not in self._versions:
            return False

        self._versions[version_id].status = VersionStatus.DEPRECATED
        logger.info(
            "embedding_version_deprecated",
            version_id=version_id
        )
        return True

    def retire(self, version_id: str) -> bool:
        """Mark a version as retired."""
        if version_id not in self._versions:
            return False

        if version_id == self._active_version:
            logger.warning(
                "cannot_retire_active_version",
                version_id=version_id
            )
            return False

        self._versions[version_id].status = VersionStatus.RETIRED
        logger.info(
            "embedding_version_retired",
            version_id=version_id
        )
        return True

    def list_all(self) -> list[EmbeddingVersion]:
        """List all registered versions."""
        return list(self._versions.values())

    def list_active(self) -> list[EmbeddingVersion]:
        """List all active versions."""
        return [
            v for v in self._versions.values()
            if v.status == VersionStatus.ACTIVE
        ]

    def get_migration_path(
        self,
        from_version: str,
        to_version: str
    ) -> list[str] | None:
        """
        Get the migration path between two versions.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            List of version IDs for migration path, or None if no path
        """
        if from_version not in self._versions or to_version not in self._versions:
            return None

        # Check if direct migration is possible
        target = self._versions[to_version]
        if from_version in target.migration_path_from:
            return [from_version, to_version]

        # Check for indirect paths (simple BFS)
        visited = set()
        queue = [[from_version]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current == to_version:
                return path

            if current in visited:
                continue

            visited.add(current)

            # Find versions that can be migrated to from current
            for v_id, version in self._versions.items():
                if current in version.migration_path_from and v_id not in visited:
                    queue.append(path + [v_id])

        return None

    def is_compatible(self, version1: str, version2: str) -> bool:
        """Check if two versions are compatible."""
        if version1 not in self._versions or version2 not in self._versions:
            return False

        v1 = self._versions[version1]
        v2 = self._versions[version2]

        # Same dimensions indicates compatibility
        if v1.dimensions == v2.dimensions:
            return True

        # Check explicit compatibility
        return version2 in v1.compatible_versions or version1 in v2.compatible_versions


# Global registry instance
_version_registry: EmbeddingVersionRegistry | None = None


def get_version_registry() -> EmbeddingVersionRegistry:
    """Get or create the global version registry instance."""
    global _version_registry
    if _version_registry is None:
        _version_registry = EmbeddingVersionRegistry()
        _version_registry.initialize()
    return _version_registry
