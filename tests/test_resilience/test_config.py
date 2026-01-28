"""
Tests for Forge Resilience Configuration
========================================

Tests for forge/resilience/config.py
"""

import os
from unittest.mock import patch

import pytest

from forge.resilience.config import (
    CacheConfig,
    ContentValidationConfig,
    DeploymentProfile,
    EmbeddingMigrationConfig,
    ForgeResilienceConfig,
    LineageTierConfig,
    ObservabilityConfig,
    PartitionConfig,
    PrivacyConfig,
    RunbookConfig,
    StarterPackConfig,
    TenantIsolationConfig,
    get_resilience_config,
    set_resilience_config,
)


class TestDeploymentProfile:
    """Tests for DeploymentProfile enum."""

    def test_profile_values(self):
        """Test all profile values."""
        assert DeploymentProfile.LITE.value == "lite"
        assert DeploymentProfile.STANDARD.value == "standard"
        assert DeploymentProfile.ENTERPRISE.value == "enterprise"


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_default_values(self):
        """Test default cache configuration."""
        config = CacheConfig()

        assert config.enabled is True
        assert config.default_ttl_seconds == 300
        assert config.lineage_ttl_seconds == 3600
        assert config.search_ttl_seconds == 600
        assert config.max_cached_result_bytes == 1048576

    def test_key_patterns(self):
        """Test key pattern defaults."""
        config = CacheConfig()

        assert "capsule_id" in config.lineage_key_pattern
        assert "query_hash" in config.search_key_pattern
        assert "partition_id" in config.partition_key_pattern
        assert "capsule_id" in config.capsule_key_pattern


class TestObservabilityConfig:
    """Tests for ObservabilityConfig dataclass."""

    def test_default_values(self):
        """Test default observability configuration."""
        config = ObservabilityConfig()

        assert config.enabled is True
        assert config.service_name == "forge-cascade"
        assert config.version == "2.0.0"
        assert config.enable_tracing is True
        assert config.enable_metrics is True
        assert config.trace_sample_rate == 1.0


class TestContentValidationConfig:
    """Tests for ContentValidationConfig dataclass."""

    def test_default_values(self):
        """Test default content validation configuration."""
        config = ContentValidationConfig()

        assert config.enabled is True
        assert config.anomaly_threshold == 0.8
        assert config.max_content_length == 1_000_000
        assert config.enable_ml_classification is True
        assert config.quarantine_on_threat is True
        assert config.log_threats is True


class TestLineageTierConfig:
    """Tests for LineageTierConfig dataclass."""

    def test_default_values(self):
        """Test default lineage tier configuration."""
        config = LineageTierConfig()

        assert config.enabled is True
        assert config.tier1_max_age_days == 30
        assert config.tier2_max_age_days == 180
        assert config.tier1_min_trust == 80
        assert config.tier2_min_trust == 60
        assert config.hot_storage == "neo4j"
        assert config.warm_storage == "neo4j"
        assert config.cold_storage == "s3"


class TestPartitionConfig:
    """Tests for PartitionConfig dataclass."""

    def test_default_values(self):
        """Test default partition configuration."""
        config = PartitionConfig()

        assert config.enabled is True
        assert config.max_capsules_per_partition == 50000
        assert config.edge_density_threshold == 0.1
        assert config.auto_rebalance is True
        assert config.rebalance_threshold == 0.2


class TestEmbeddingMigrationConfig:
    """Tests for EmbeddingMigrationConfig dataclass."""

    def test_default_values(self):
        """Test default embedding migration configuration."""
        config = EmbeddingMigrationConfig()

        assert config.batch_size == 100
        assert config.delay_seconds == 1.0
        assert config.cleanup_old_embeddings is True
        assert config.cleanup_grace_period_days == 30


class TestTenantIsolationConfig:
    """Tests for TenantIsolationConfig dataclass."""

    def test_default_values(self):
        """Test default tenant isolation configuration."""
        config = TenantIsolationConfig()

        assert config.enabled is False  # Only enabled in Enterprise
        assert config.strict_mode is True
        assert config.audit_cross_tenant_attempts is True


class TestPrivacyConfig:
    """Tests for PrivacyConfig dataclass."""

    def test_default_values(self):
        """Test default privacy configuration."""
        config = PrivacyConfig()

        assert config.enabled is True
        assert config.gdpr_compliant is True
        assert config.data_retention_days == 365 * 7
        assert config.anonymization_enabled is True


class TestStarterPackConfig:
    """Tests for StarterPackConfig dataclass."""

    def test_default_values(self):
        """Test default starter pack configuration."""
        config = StarterPackConfig()

        assert config.enabled is True
        assert "registry" in config.registry_url
        assert config.auto_import_dependencies is True
        assert config.default_trust_level == 60


class TestRunbookConfig:
    """Tests for RunbookConfig dataclass."""

    def test_default_values(self):
        """Test default runbook configuration."""
        config = RunbookConfig()

        assert config.enabled is True
        assert config.auto_execute_safe_steps is False
        assert config.notification_channels == []


class TestForgeResilienceConfig:
    """Tests for ForgeResilienceConfig dataclass."""

    def test_default_values(self):
        """Test default resilience configuration."""
        config = ForgeResilienceConfig()

        assert config.profile == DeploymentProfile.STANDARD
        assert isinstance(config.cache, CacheConfig)
        assert isinstance(config.observability, ObservabilityConfig)
        assert isinstance(config.content_validation, ContentValidationConfig)
        assert isinstance(config.lineage, LineageTierConfig)
        assert isinstance(config.partitioning, PartitionConfig)
        assert isinstance(config.embedding_migration, EmbeddingMigrationConfig)
        assert isinstance(config.tenant_isolation, TenantIsolationConfig)
        assert isinstance(config.privacy, PrivacyConfig)
        assert isinstance(config.starter_packs, StarterPackConfig)
        assert isinstance(config.runbooks, RunbookConfig)

    def test_from_environment_standard(self):
        """Test loading standard profile from environment."""
        with patch.dict(os.environ, {"FORGE_PROFILE": "standard"}):
            config = ForgeResilienceConfig.from_environment()

            assert config.profile == DeploymentProfile.STANDARD
            assert config.tenant_isolation.enabled is False

    def test_from_environment_lite(self):
        """Test loading lite profile from environment."""
        with patch.dict(os.environ, {"FORGE_PROFILE": "lite"}):
            config = ForgeResilienceConfig.from_environment()

            assert config.profile == DeploymentProfile.LITE
            # Lite profile disables certain features
            assert config.observability.enable_tracing is False
            assert config.content_validation.enable_ml_classification is False
            assert config.lineage.enabled is False
            assert config.partitioning.enabled is False

    def test_from_environment_enterprise(self):
        """Test loading enterprise profile from environment."""
        with patch.dict(os.environ, {"FORGE_PROFILE": "enterprise"}):
            config = ForgeResilienceConfig.from_environment()

            assert config.profile == DeploymentProfile.ENTERPRISE
            assert config.tenant_isolation.enabled is True
            assert config.tenant_isolation.strict_mode is True
            assert config.runbooks.auto_execute_safe_steps is True

    def test_apply_profile_defaults_lite(self):
        """Test applying lite profile defaults."""
        config = ForgeResilienceConfig(profile=DeploymentProfile.LITE)
        config._apply_profile_defaults()

        assert config.observability.enable_tracing is False
        assert config.content_validation.enable_ml_classification is False
        assert config.lineage.enabled is False
        assert config.partitioning.enabled is False
        assert config.tenant_isolation.enabled is False
        assert config.runbooks.enabled is False

    def test_apply_profile_defaults_standard(self):
        """Test applying standard profile defaults."""
        config = ForgeResilienceConfig(profile=DeploymentProfile.STANDARD)
        config._apply_profile_defaults()

        assert config.tenant_isolation.enabled is False

    def test_apply_profile_defaults_enterprise(self):
        """Test applying enterprise profile defaults."""
        config = ForgeResilienceConfig(profile=DeploymentProfile.ENTERPRISE)
        config._apply_profile_defaults()

        assert config.tenant_isolation.enabled is True
        assert config.tenant_isolation.strict_mode is True
        assert config.runbooks.auto_execute_safe_steps is True


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_resilience_config(self):
        """Test getting global resilience config."""
        with patch("forge.resilience.config._default_config", None):
            with patch.dict(os.environ, {"FORGE_PROFILE": "standard"}):
                config = get_resilience_config()

                assert isinstance(config, ForgeResilienceConfig)
                assert config.profile == DeploymentProfile.STANDARD

    def test_get_resilience_config_cached(self):
        """Test that config is cached."""
        with patch("forge.resilience.config._default_config", None):
            config1 = get_resilience_config()
            config2 = get_resilience_config()

            assert config1 is config2

    def test_set_resilience_config(self):
        """Test setting global resilience config."""
        custom_config = ForgeResilienceConfig(profile=DeploymentProfile.ENTERPRISE)

        set_resilience_config(custom_config)

        result = get_resilience_config()
        assert result == custom_config
        assert result.profile == DeploymentProfile.ENTERPRISE

        # Clean up
        set_resilience_config(ForgeResilienceConfig())


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_redis_url_from_env(self):
        """Test Redis URL loaded from environment."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://custom:6380"}):
            config = CacheConfig()
            assert config.redis_url == "redis://custom:6380"

    def test_otlp_endpoint_from_env(self):
        """Test OTLP endpoint loaded from environment."""
        with patch.dict(os.environ, {"OTLP_ENDPOINT": "http://custom:4318"}):
            config = ObservabilityConfig()
            assert config.otlp_endpoint == "http://custom:4318"

    def test_environment_from_env(self):
        """Test environment loaded from environment variable."""
        with patch.dict(os.environ, {"FORGE_ENV": "production"}):
            config = ObservabilityConfig()
            assert config.environment == "production"

    def test_s3_bucket_from_env(self):
        """Test S3 bucket loaded from environment."""
        with patch.dict(os.environ, {"LINEAGE_S3_BUCKET": "my-custom-bucket"}):
            config = LineageTierConfig()
            assert config.cold_storage_bucket == "my-custom-bucket"
