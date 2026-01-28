"""
Tests for Embedding Version Registry
====================================

Tests for forge/resilience/migration/version_registry.py
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from forge.resilience.migration.version_registry import (
    EmbeddingVersion,
    EmbeddingVersionRegistry,
    ModelProvider,
    VersionStatus,
    get_version_registry,
)


class TestModelProvider:
    """Tests for ModelProvider enum."""

    def test_provider_values(self):
        """Test all provider values."""
        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.COHERE.value == "cohere"
        assert ModelProvider.SENTENCE_TRANSFORMERS.value == "sentence_transformers"
        assert ModelProvider.CUSTOM.value == "custom"


class TestVersionStatus:
    """Tests for VersionStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert VersionStatus.ACTIVE.value == "active"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.RETIRED.value == "retired"
        assert VersionStatus.TESTING.value == "testing"


class TestEmbeddingVersion:
    """Tests for EmbeddingVersion dataclass."""

    def test_version_creation(self):
        """Test creating an embedding version."""
        version = EmbeddingVersion(
            version_id="test-v1",
            model_name="test-model",
            provider=ModelProvider.OPENAI,
            dimensions=1536,
        )

        assert version.version_id == "test-v1"
        assert version.model_name == "test-model"
        assert version.provider == ModelProvider.OPENAI
        assert version.dimensions == 1536
        assert version.status == VersionStatus.ACTIVE

    def test_version_defaults(self):
        """Test default values."""
        version = EmbeddingVersion(
            version_id="v1",
            model_name="model",
            provider=ModelProvider.CUSTOM,
            dimensions=768,
        )

        assert version.max_tokens == 8192
        assert version.batch_size == 100
        assert version.normalize is True
        assert version.compatible_versions == []
        assert version.migration_path_from == []

    def test_version_to_dict(self):
        """Test converting version to dictionary."""
        version = EmbeddingVersion(
            version_id="test-v1",
            model_name="test-model",
            provider=ModelProvider.OPENAI,
            dimensions=1536,
            avg_latency_ms=25.0,
            cost_per_1k_tokens=0.0001,
        )

        result = version.to_dict()

        assert result["version_id"] == "test-v1"
        assert result["model_name"] == "test-model"
        assert result["provider"] == "openai"
        assert result["dimensions"] == 1536
        assert result["status"] == "active"
        assert result["avg_latency_ms"] == 25.0
        assert result["cost_per_1k_tokens"] == 0.0001

    def test_version_from_dict(self):
        """Test creating version from dictionary."""
        data = {
            "version_id": "test-v2",
            "model_name": "test-model-2",
            "provider": "cohere",
            "dimensions": 768,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "deprecated",
            "max_tokens": 4096,
            "batch_size": 50,
            "normalize": False,
            "avg_latency_ms": 30.0,
            "cost_per_1k_tokens": 0.0002,
            "compatible_versions": ["v1"],
            "migration_path_from": ["v0"],
            "metadata": {"key": "value"},
        }

        version = EmbeddingVersion.from_dict(data)

        assert version.version_id == "test-v2"
        assert version.provider == ModelProvider.COHERE
        assert version.status == VersionStatus.DEPRECATED
        assert version.max_tokens == 4096
        assert version.batch_size == 50
        assert version.normalize is False
        assert version.compatible_versions == ["v1"]
        assert version.migration_path_from == ["v0"]


class TestEmbeddingVersionRegistry:
    """Tests for EmbeddingVersionRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a registry instance."""
        return EmbeddingVersionRegistry()

    def test_registry_creation(self, registry):
        """Test registry creation."""
        assert registry._versions == {}
        assert registry._active_version is None
        assert registry._initialized is False

    def test_initialize(self, registry):
        """Test registry initialization."""
        registry.initialize()

        assert registry._initialized is True
        assert len(registry._versions) > 0
        assert registry._active_version is not None

    def test_initialize_idempotent(self, registry):
        """Test that initialize is idempotent."""
        registry.initialize()
        count = len(registry._versions)

        registry.initialize()

        assert len(registry._versions) == count

    def test_register(self, registry):
        """Test registering a version."""
        version = EmbeddingVersion(
            version_id="custom-v1",
            model_name="custom-model",
            provider=ModelProvider.CUSTOM,
            dimensions=512,
        )

        registry.register(version)

        assert "custom-v1" in registry._versions
        assert registry._versions["custom-v1"] == version

    def test_get(self, registry):
        """Test getting a version by ID."""
        registry.initialize()

        version = registry.get("text-embedding-3-small")

        assert version is not None
        assert version.model_name == "text-embedding-3-small"

    def test_get_not_found(self, registry):
        """Test getting nonexistent version."""
        version = registry.get("nonexistent")

        assert version is None

    def test_get_active(self, registry):
        """Test getting active version."""
        registry.initialize()

        active = registry.get_active()

        assert active is not None
        assert active.version_id == registry._active_version

    def test_get_active_not_set(self, registry):
        """Test getting active version when not set."""
        active = registry.get_active()

        assert active is None

    def test_get_default(self, registry):
        """Test getting default version."""
        registry.initialize()

        default = registry.get_default()

        assert default is not None

    def test_set_active(self, registry):
        """Test setting active version."""
        registry.initialize()

        result = registry.set_active("text-embedding-3-large")

        assert result is True
        assert registry._active_version == "text-embedding-3-large"

    def test_set_active_unknown_version(self, registry):
        """Test setting active to unknown version."""
        registry.initialize()

        result = registry.set_active("unknown")

        assert result is False

    def test_set_active_retired_version(self, registry):
        """Test setting active to retired version."""
        registry.initialize()
        registry._versions["text-embedding-3-small"].status = VersionStatus.RETIRED

        result = registry.set_active("text-embedding-3-small")

        assert result is False

    def test_deprecate(self, registry):
        """Test deprecating a version."""
        registry.initialize()

        result = registry.deprecate("text-embedding-3-small")

        assert result is True
        assert registry._versions["text-embedding-3-small"].status == VersionStatus.DEPRECATED

    def test_deprecate_not_found(self, registry):
        """Test deprecating nonexistent version."""
        result = registry.deprecate("nonexistent")

        assert result is False

    def test_retire(self, registry):
        """Test retiring a version."""
        registry.initialize()
        registry._active_version = "text-embedding-3-large"

        result = registry.retire("text-embedding-3-small")

        assert result is True
        assert registry._versions["text-embedding-3-small"].status == VersionStatus.RETIRED

    def test_retire_active_version(self, registry):
        """Test retiring active version fails."""
        registry.initialize()

        result = registry.retire(registry._active_version)

        assert result is False

    def test_retire_not_found(self, registry):
        """Test retiring nonexistent version."""
        result = registry.retire("nonexistent")

        assert result is False

    def test_list_all(self, registry):
        """Test listing all versions."""
        registry.initialize()

        versions = registry.list_all()

        assert len(versions) > 0
        assert all(isinstance(v, EmbeddingVersion) for v in versions)

    def test_list_active(self, registry):
        """Test listing active versions."""
        registry.initialize()

        versions = registry.list_active()

        assert len(versions) > 0
        assert all(v.status == VersionStatus.ACTIVE for v in versions)

    def test_get_migration_path_direct(self, registry):
        """Test getting direct migration path."""
        registry.initialize()

        path = registry.get_migration_path(
            "text-embedding-ada-002", "text-embedding-3-small"
        )

        assert path is not None
        assert path == ["text-embedding-ada-002", "text-embedding-3-small"]

    def test_get_migration_path_not_found(self, registry):
        """Test migration path not found."""
        registry.initialize()

        path = registry.get_migration_path("nonexistent", "text-embedding-3-small")

        assert path is None

    def test_get_migration_path_no_path(self, registry):
        """Test no migration path exists."""
        version1 = EmbeddingVersion(
            version_id="isolated-v1",
            model_name="isolated-1",
            provider=ModelProvider.CUSTOM,
            dimensions=512,
        )
        version2 = EmbeddingVersion(
            version_id="isolated-v2",
            model_name="isolated-2",
            provider=ModelProvider.CUSTOM,
            dimensions=768,
        )
        registry.register(version1)
        registry.register(version2)

        path = registry.get_migration_path("isolated-v1", "isolated-v2")

        assert path is None

    def test_is_compatible_same_dimensions(self, registry):
        """Test compatibility with same dimensions."""
        registry.initialize()

        # text-embedding-ada-002 and text-embedding-3-small both have 1536 dims
        result = registry.is_compatible(
            "text-embedding-ada-002", "text-embedding-3-small"
        )

        assert result is True

    def test_is_compatible_different_dimensions(self, registry):
        """Test compatibility with different dimensions."""
        registry.initialize()

        # text-embedding-3-small (1536) vs text-embedding-3-large (3072)
        result = registry.is_compatible(
            "text-embedding-3-small", "text-embedding-3-large"
        )

        assert result is False

    def test_is_compatible_explicit(self, registry):
        """Test explicit compatibility."""
        version1 = EmbeddingVersion(
            version_id="compat-v1",
            model_name="model-1",
            provider=ModelProvider.CUSTOM,
            dimensions=512,
            compatible_versions=["compat-v2"],
        )
        version2 = EmbeddingVersion(
            version_id="compat-v2",
            model_name="model-2",
            provider=ModelProvider.CUSTOM,
            dimensions=768,  # Different dimensions
        )
        registry.register(version1)
        registry.register(version2)

        result = registry.is_compatible("compat-v1", "compat-v2")

        assert result is True

    def test_is_compatible_not_found(self, registry):
        """Test compatibility with nonexistent version."""
        result = registry.is_compatible("nonexistent", "also-nonexistent")

        assert result is False


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_version_registry(self):
        """Test getting global version registry."""
        with patch(
            "forge.resilience.migration.version_registry._version_registry", None
        ):
            registry = get_version_registry()

            assert isinstance(registry, EmbeddingVersionRegistry)
            assert registry._initialized is True
