"""
Tests for Virtuals Protocol Integration Configuration.

This module tests the configuration settings for integrating Forge with
Virtuals Protocol across multiple chains.
"""

import os
import warnings
from unittest.mock import patch

import pytest

from forge.virtuals.config import (
    CONTRACT_ADDRESSES,
    RPC_ENDPOINTS,
    ChainNetwork,
    SecurityWarning,
    VirtualsConfig,
    VirtualsEnvironment,
    configure_virtuals,
    get_virtuals_config,
)


# ==================== Fixtures ====================


@pytest.fixture(autouse=True)
def reset_global_config():
    """Reset global config before and after each test."""
    import forge.virtuals.config as config_module
    original = config_module._config
    config_module._config = None
    yield
    config_module._config = original


@pytest.fixture
def clean_env():
    """Clean environment variables for testing."""
    virtuals_vars = [k for k in os.environ if k.startswith("VIRTUALS_")]
    original_values = {k: os.environ.pop(k) for k in virtuals_vars}
    yield
    os.environ.update(original_values)


# ==================== ChainNetwork Tests ====================


class TestChainNetwork:
    """Tests for ChainNetwork enum."""

    def test_all_chains_exist(self):
        """Test that all expected chains exist."""
        assert ChainNetwork.BASE == "base"
        assert ChainNetwork.BASE_SEPOLIA == "base_sepolia"
        assert ChainNetwork.ETHEREUM == "ethereum"
        assert ChainNetwork.ETHEREUM_SEPOLIA == "ethereum_sepolia"
        assert ChainNetwork.SOLANA == "solana"
        assert ChainNetwork.SOLANA_DEVNET == "solana_devnet"

    def test_chain_count(self):
        """Test the number of supported chains."""
        assert len(ChainNetwork) == 6


# ==================== VirtualsEnvironment Tests ====================


class TestVirtualsEnvironment:
    """Tests for VirtualsEnvironment enum."""

    def test_all_environments_exist(self):
        """Test that all expected environments exist."""
        assert VirtualsEnvironment.PRODUCTION == "production"
        assert VirtualsEnvironment.TESTNET == "testnet"
        assert VirtualsEnvironment.LOCAL == "local"


# ==================== Contract Addresses Tests ====================


class TestContractAddresses:
    """Tests for contract addresses configuration."""

    def test_base_contracts(self):
        """Test Base chain contract addresses."""
        base_contracts = CONTRACT_ADDRESSES[ChainNetwork.BASE]

        assert "virtual_token" in base_contracts
        assert "vault" in base_contracts
        assert "bridge" in base_contracts

    def test_ethereum_contracts(self):
        """Test Ethereum chain contract addresses."""
        eth_contracts = CONTRACT_ADDRESSES[ChainNetwork.ETHEREUM]

        assert "virtual_token" in eth_contracts
        assert "bridge" in eth_contracts

    def test_solana_contracts(self):
        """Test Solana chain contract addresses."""
        solana_contracts = CONTRACT_ADDRESSES[ChainNetwork.SOLANA]

        assert "virtual_token" in solana_contracts


# ==================== RPC Endpoints Tests ====================


class TestRPCEndpoints:
    """Tests for RPC endpoints configuration."""

    def test_all_chains_have_endpoints(self):
        """Test that all chains have RPC endpoints."""
        for chain in ChainNetwork:
            assert chain in RPC_ENDPOINTS

    def test_mainnet_endpoints(self):
        """Test mainnet endpoint URLs."""
        assert "base.org" in RPC_ENDPOINTS[ChainNetwork.BASE]
        assert "solana.com" in RPC_ENDPOINTS[ChainNetwork.SOLANA]

    def test_testnet_endpoints(self):
        """Test testnet endpoint URLs."""
        assert "sepolia" in RPC_ENDPOINTS[ChainNetwork.BASE_SEPOLIA]
        assert "devnet" in RPC_ENDPOINTS[ChainNetwork.SOLANA_DEVNET]


# ==================== VirtualsConfig Tests ====================


class TestVirtualsConfig:
    """Tests for VirtualsConfig class."""

    def test_config_defaults(self, clean_env):
        """Test default configuration values."""
        config = VirtualsConfig()

        assert config.environment == VirtualsEnvironment.TESTNET
        assert config.primary_chain == ChainNetwork.BASE
        assert config.enable_tokenization is True
        assert config.enable_acp is True

    def test_config_from_env(self, clean_env):
        """Test configuration from environment variables."""
        os.environ["VIRTUALS_ENVIRONMENT"] = "production"
        os.environ["VIRTUALS_ENABLE_TOKENIZATION"] = "false"

        config = VirtualsConfig()

        assert config.environment == VirtualsEnvironment.PRODUCTION
        assert config.enable_tokenization is False

    def test_api_key_warning(self, clean_env):
        """Test warning when API key is not set."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = VirtualsConfig()

            assert config.api_key == ""
            # Warning should be issued
            assert any("VIRTUALS_API_KEY" in str(warning.message) for warning in w)

    def test_api_key_set(self, clean_env):
        """Test when API key is set."""
        os.environ["VIRTUALS_API_KEY"] = "test-api-key-123"

        config = VirtualsConfig()

        assert config.api_key == "test-api-key-123"

    def test_enabled_chains_default(self, clean_env):
        """Test default enabled chains."""
        config = VirtualsConfig()

        assert ChainNetwork.BASE in config.enabled_chains
        assert ChainNetwork.ETHEREUM in config.enabled_chains
        assert ChainNetwork.SOLANA in config.enabled_chains

    def test_revenue_config_defaults(self, clean_env):
        """Test revenue configuration defaults."""
        config = VirtualsConfig()

        assert config.inference_fee_per_query == 0.001
        assert config.overlay_service_fee_percentage == 0.05
        assert config.governance_reward_pool_percentage == 0.10

    def test_acp_config_defaults(self, clean_env):
        """Test ACP configuration defaults."""
        config = VirtualsConfig()

        assert config.acp_escrow_timeout_hours == 24
        assert config.acp_evaluation_timeout_hours == 48

    def test_agent_config_defaults(self, clean_env):
        """Test agent configuration defaults."""
        config = VirtualsConfig()

        assert config.agent_creation_fee == 100
        assert config.graduation_threshold == 42000


# ==================== Private Key Security Tests ====================


class TestPrivateKeySecurity:
    """Tests for private key security validations."""

    def test_private_key_production_warning(self, clean_env):
        """Test warning for private key in production."""
        os.environ["VIRTUALS_ENVIRONMENT"] = "production"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["VIRTUALS_OPERATOR_PRIVATE_KEY"] = "0x" + "1" * 64

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            VirtualsConfig()

            security_warnings = [warning for warning in w if issubclass(warning.category, SecurityWarning)]
            assert len(security_warnings) > 0

    def test_private_key_development_no_error(self, clean_env):
        """Test that private key in development doesn't error."""
        os.environ["VIRTUALS_ENVIRONMENT"] = "testnet"
        os.environ["VIRTUALS_OPERATOR_PRIVATE_KEY"] = "0x" + "1" * 64

        # Should not raise
        config = VirtualsConfig()

        assert config.operator_private_key == "0x" + "1" * 64

    def test_private_key_with_secrets_backend(self, clean_env):
        """Test that using secrets backend avoids warning."""
        os.environ["VIRTUALS_ENVIRONMENT"] = "production"
        os.environ["ENVIRONMENT"] = "production"
        os.environ["SECRETS_BACKEND"] = "vault"
        os.environ["VIRTUALS_OPERATOR_PRIVATE_KEY"] = "0x" + "1" * 64

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            VirtualsConfig()

            security_warnings = [warning for warning in w if issubclass(warning.category, SecurityWarning)]
            # Should not have security warning with vault backend
            assert len(security_warnings) == 0


# ==================== RPC Endpoint Methods Tests ====================


class TestRPCEndpointMethods:
    """Tests for get_rpc_endpoint method."""

    def test_get_rpc_endpoint_production(self, clean_env):
        """Test getting RPC endpoint in production."""
        os.environ["VIRTUALS_ENVIRONMENT"] = "production"
        config = VirtualsConfig()

        endpoint = config.get_rpc_endpoint(ChainNetwork.BASE)

        assert "mainnet.base.org" in endpoint

    def test_get_rpc_endpoint_testnet(self, clean_env):
        """Test getting RPC endpoint in testnet (uses sepolia)."""
        config = VirtualsConfig()  # Default is testnet

        endpoint = config.get_rpc_endpoint(ChainNetwork.BASE)

        assert "sepolia" in endpoint

    def test_get_rpc_endpoint_solana_devnet(self, clean_env):
        """Test getting Solana RPC endpoint in testnet."""
        config = VirtualsConfig()

        endpoint = config.get_rpc_endpoint(ChainNetwork.SOLANA)

        assert "devnet" in endpoint


# ==================== Contract Address Methods Tests ====================


class TestContractAddressMethods:
    """Tests for get_contract_address method."""

    def test_get_contract_address_exists(self, clean_env):
        """Test getting existing contract address."""
        config = VirtualsConfig()

        address = config.get_contract_address(ChainNetwork.BASE, "virtual_token")

        assert address is not None
        assert address.startswith("0x")

    def test_get_contract_address_not_found(self, clean_env):
        """Test getting non-existent contract address."""
        config = VirtualsConfig()

        address = config.get_contract_address(ChainNetwork.BASE, "nonexistent_contract")

        assert address is None

    def test_get_contract_address_chain_not_found(self, clean_env):
        """Test getting address for chain without contracts."""
        config = VirtualsConfig()

        # Testnet chains might not be in CONTRACT_ADDRESSES
        address = config.get_contract_address(ChainNetwork.BASE_SEPOLIA, "virtual_token")

        # Should return None gracefully
        assert address is None


# ==================== Chain Enabled Tests ====================


class TestChainEnabled:
    """Tests for is_chain_enabled method."""

    def test_is_chain_enabled_true(self, clean_env):
        """Test checking enabled chain."""
        config = VirtualsConfig()

        assert config.is_chain_enabled(ChainNetwork.BASE) is True

    def test_is_chain_enabled_false(self, clean_env):
        """Test checking disabled chain."""
        config = VirtualsConfig()

        # Testnets are not in default enabled_chains
        assert config.is_chain_enabled(ChainNetwork.BASE_SEPOLIA) is False


# ==================== Global Config Tests ====================


class TestGlobalConfig:
    """Tests for global config management."""

    def test_get_virtuals_config_singleton(self, clean_env):
        """Test that get_virtuals_config returns singleton."""
        config1 = get_virtuals_config()
        config2 = get_virtuals_config()

        assert config1 is config2

    def test_configure_virtuals(self, clean_env):
        """Test setting custom configuration."""
        custom_config = VirtualsConfig()
        custom_config.api_key = "custom-key"

        configure_virtuals(custom_config)

        retrieved = get_virtuals_config()
        assert retrieved is custom_config
        assert retrieved.api_key == "custom-key"


# ==================== Feature Flags Tests ====================


class TestFeatureFlags:
    """Tests for feature flag configuration."""

    def test_all_features_enabled_by_default(self, clean_env):
        """Test that all features are enabled by default."""
        config = VirtualsConfig()

        assert config.enable_tokenization is True
        assert config.enable_acp is True
        assert config.enable_cross_chain is True
        assert config.enable_revenue_sharing is True
        assert config.enable_privacy_layer is True

    def test_disable_feature_from_env(self, clean_env):
        """Test disabling feature from environment."""
        os.environ["VIRTUALS_ENABLE_CROSS_CHAIN"] = "false"

        config = VirtualsConfig()

        assert config.enable_cross_chain is False


# ==================== Model Config Tests ====================


class TestModelConfig:
    """Tests for Pydantic model configuration."""

    def test_env_prefix(self, clean_env):
        """Test that VIRTUALS_ prefix is used for env vars."""
        os.environ["VIRTUALS_GAME_API_RATE_LIMIT"] = "20"

        config = VirtualsConfig()

        assert config.game_api_rate_limit == 20

    def test_extra_fields_ignored(self, clean_env):
        """Test that extra fields are ignored."""
        os.environ["VIRTUALS_UNKNOWN_FIELD"] = "value"

        # Should not raise
        config = VirtualsConfig()

        assert not hasattr(config, "unknown_field")
