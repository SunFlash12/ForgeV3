"""
Virtuals Protocol Integration Configuration

This module defines all configuration settings for integrating Forge with
Virtuals Protocol across multiple chains (Base, Ethereum, Solana).

Configuration is loaded from environment variables with sensible defaults
for development environments.

SECURITY NOTE: Private keys should be loaded from a secure secrets manager
in production. Set SECRETS_BACKEND=vault or SECRETS_BACKEND=aws_secrets_manager.
"""

import logging
import os
import warnings
from enum import Enum

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class SecurityWarning(UserWarning):
    """Warning for security-related issues (insecure configurations, etc.)."""

    pass


class ChainNetwork(str, Enum):
    """Supported blockchain networks for Virtuals Protocol integration."""

    BASE = "base"
    BASE_SEPOLIA = "base_sepolia"  # Testnet
    ETHEREUM = "ethereum"
    ETHEREUM_SEPOLIA = "ethereum_sepolia"  # Testnet
    SOLANA = "solana"
    SOLANA_DEVNET = "solana_devnet"  # Testnet


class VirtualsEnvironment(str, Enum):
    """Virtuals Protocol deployment environment."""

    PRODUCTION = "production"
    TESTNET = "testnet"
    LOCAL = "local"


# Contract addresses for each supported chain
# These are the official Virtuals Protocol contract addresses
CONTRACT_ADDRESSES = {
    ChainNetwork.BASE: {
        "virtual_token": "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
        "agent_factory": "0x...",  # To be filled with actual address
        "agent_nft": "0x...",
        "acp_registry": "0x...",
        "vault": "0xdAd686299FB562f89e55DA05F1D96FaBEb2A2E32",
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
    },
    ChainNetwork.ETHEREUM: {
        "virtual_token": "0x44ff8620b8cA30902395A7bD3F2407e1A091BF73",
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
    },
    ChainNetwork.SOLANA: {
        "virtual_token": "3iQL8BFS2vE7mww4ehAqQHAsbmRNCrPxizWAT2Zfyr9y",
    },
}

# RPC endpoints for each chain
RPC_ENDPOINTS = {
    ChainNetwork.BASE: "https://mainnet.base.org",
    ChainNetwork.BASE_SEPOLIA: "https://sepolia.base.org",
    ChainNetwork.ETHEREUM: "https://eth.llamarpc.com",
    ChainNetwork.ETHEREUM_SEPOLIA: "https://rpc.sepolia.org",
    ChainNetwork.SOLANA: "https://api.mainnet-beta.solana.com",
    ChainNetwork.SOLANA_DEVNET: "https://api.devnet.solana.com",
}


class VirtualsConfig(BaseSettings):
    """
    Main configuration class for Virtuals Protocol integration.

    All settings can be overridden via environment variables prefixed with VIRTUALS_.
    For example, VIRTUALS_API_KEY sets the api_key field.
    """

    # API Configuration
    api_key: str = Field(
        default="", description="GAME API key obtained from console.game.virtuals.io"
    )
    api_base_url: str = Field(
        default="https://sdk.game.virtuals.io/v2", description="Base URL for GAME SDK API"
    )
    auth_url: str = Field(
        default="https://api.virtuals.io/api/accesses/tokens",
        description="URL for exchanging API key for access token",
    )

    # Environment Configuration
    environment: VirtualsEnvironment = Field(
        default=VirtualsEnvironment.TESTNET,
        description="Deployment environment (production, testnet, local)",
    )
    primary_chain: ChainNetwork = Field(
        default=ChainNetwork.BASE, description="Primary blockchain for agent deployment"
    )
    enabled_chains: list[ChainNetwork] = Field(
        default=[ChainNetwork.BASE, ChainNetwork.ETHEREUM, ChainNetwork.SOLANA],
        description="List of enabled chains for multi-chain operations",
    )

    # Wallet Configuration
    # SECURITY WARNING: In production, use SECRETS_BACKEND=vault or aws_secrets_manager
    # instead of loading private keys from environment variables.
    operator_private_key: str | None = Field(
        default=None,
        description="Private key for the Forge operator wallet (EVM hex format). "
        "SECURITY: Use secrets manager in production!",
    )
    solana_private_key: str | None = Field(
        default=None,
        description="Private key for Solana operations (base58 format). "
        "SECURITY: Use secrets manager in production!",
    )

    # Secrets Backend Configuration
    secrets_backend: str | None = Field(
        default=None, description="Secrets backend: environment, vault, aws_secrets_manager"
    )

    # Agent Configuration
    default_agent_goal: str = Field(
        default="Provide intelligent knowledge management and governance services",
        description="Default goal for Forge agents",
    )
    agent_creation_fee: int = Field(
        default=100, description="VIRTUAL tokens required to create an agent"
    )
    graduation_threshold: int = Field(
        default=42000, description="VIRTUAL tokens needed for agent to graduate from bonding curve"
    )

    # Revenue Configuration
    inference_fee_per_query: float = Field(
        default=0.001, description="VIRTUAL tokens charged per knowledge query"
    )
    overlay_service_fee_percentage: float = Field(
        default=0.05, description="Percentage fee for overlay-as-a-service (5% default)"
    )
    governance_reward_pool_percentage: float = Field(
        default=0.10, description="Percentage of revenue allocated to governance rewards"
    )

    # Contract Addresses (can override defaults from CONTRACT_ADDRESSES)
    bonding_curve_address: str | None = Field(
        default=None, description="BondingCurve contract address for token graduation"
    )
    multisend_address: str | None = Field(
        default="0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",
        description="Gnosis Safe MultiSend contract for batch transfers",
    )

    # ACP Configuration
    acp_escrow_timeout_hours: int = Field(
        default=24, description="Default timeout for ACP escrow transactions"
    )
    acp_evaluation_timeout_hours: int = Field(
        default=48, description="Timeout for evaluation phase in ACP"
    )

    # Rate Limiting
    game_api_rate_limit: int = Field(
        default=10, description="Maximum GAME API calls per 5 minutes (free tier)"
    )
    game_api_cost_per_call: float = Field(
        default=0.003, description="Cost per GAME API call in USD (paid tier)"
    )

    # Feature Flags
    enable_tokenization: bool = Field(
        default=True, description="Enable opt-in tokenization features"
    )
    enable_acp: bool = Field(default=True, description="Enable Agent Commerce Protocol features")
    enable_cross_chain: bool = Field(
        default=True, description="Enable cross-chain bridging features"
    )
    enable_revenue_sharing: bool = Field(
        default=True, description="Enable revenue sharing and buyback-burn mechanics"
    )

    # Privacy and Compliance
    enable_privacy_layer: bool = Field(
        default=True, description="Enable additional privacy protections for enterprise use"
    )
    kyc_required_for_tokenization: bool = Field(
        default=False, description="Require KYC verification before tokenization"
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Warn if API key is not set but don't fail."""
        if not v:
            warnings.warn(
                "VIRTUALS_API_KEY not set. Agent features will be disabled. "
                "Get your API key from https://console.game.virtuals.io",
                stacklevel=2,
            )
        return v

    @field_validator("operator_private_key", "solana_private_key")
    @classmethod
    def validate_private_key_security(cls, v: str | None, info: ValidationInfo) -> str | None:
        """
        Warn about insecure private key storage in production.

        SECURITY: Private keys loaded from environment variables are a security
        risk. In production, configure SECRETS_BACKEND to use Vault or AWS
        Secrets Manager instead.
        """
        if v is not None:
            environment = os.environ.get(
                "VIRTUALS_ENVIRONMENT", os.environ.get("ENVIRONMENT", "development")
            )
            secrets_backend = os.environ.get("SECRETS_BACKEND", "environment")

            if environment == "production" and secrets_backend == "environment":
                logger.critical(
                    f"SECURITY CRITICAL: {info.field_name} loaded from environment variable "
                    "in production! Configure SECRETS_BACKEND=vault or "
                    "SECRETS_BACKEND=aws_secrets_manager for secure secrets management."
                )
                warnings.warn(
                    f"Private key '{info.field_name}' loaded from environment variable "
                    "in production. This is insecure! Use a secrets manager.",
                    SecurityWarning,
                    stacklevel=2,
                )
            elif environment != "development":
                logger.warning(
                    f"Private key '{info.field_name}' loaded from environment variable. "
                    "Consider using a secrets manager in non-development environments."
                )
        return v

    def get_rpc_endpoint(self, chain: ChainNetwork) -> str:
        """Get the RPC endpoint for a specific chain."""
        # Use testnet endpoints in non-production environments
        if self.environment != VirtualsEnvironment.PRODUCTION:
            testnet_map = {
                ChainNetwork.BASE: ChainNetwork.BASE_SEPOLIA,
                ChainNetwork.ETHEREUM: ChainNetwork.ETHEREUM_SEPOLIA,
                ChainNetwork.SOLANA: ChainNetwork.SOLANA_DEVNET,
            }
            chain = testnet_map.get(chain, chain)
        return RPC_ENDPOINTS.get(chain, RPC_ENDPOINTS[ChainNetwork.BASE])

    def get_contract_address(self, chain: ChainNetwork, contract: str) -> str | None:
        """Get a contract address for a specific chain."""
        chain_contracts = CONTRACT_ADDRESSES.get(chain, {})
        return chain_contracts.get(contract)

    def is_chain_enabled(self, chain: ChainNetwork) -> bool:
        """Check if a specific chain is enabled."""
        return chain in self.enabled_chains

    model_config = {
        "env_prefix": "VIRTUALS_",
        "env_file": ".env",
        "extra": "ignore",
    }


# Singleton instance for global access
_config: VirtualsConfig | None = None


def get_virtuals_config() -> VirtualsConfig:
    """
    Get the global Virtuals configuration instance.

    This function implements a singleton pattern to ensure consistent
    configuration across the application.
    """
    global _config
    if _config is None:
        _config = VirtualsConfig()
    return _config


def configure_virtuals(config: VirtualsConfig) -> None:
    """
    Set a custom configuration instance.

    Useful for testing or when configuration needs to be loaded
    from a non-standard source.
    """
    global _config
    _config = config
