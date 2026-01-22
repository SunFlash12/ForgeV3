"""
k
Forge-Virtuals Protocol Integration Package

This package provides comprehensive integration between Forge's institutional
memory architecture and Virtuals Protocol's autonomous AI agent infrastructure.

The integration enables:
- Tokenized Knowledge Agents: Transform Forge overlays into revenue-generating AI agents
- Knowledge Monetization: Earn VIRTUAL tokens from capsule access fees
- Agent Commerce Protocol: Secure agent-to-agent transactions with escrow
- Multi-Chain Deployment: Operate on Base, Ethereum, and Solana
- Democratic Governance: Token holder voting on entity decisions

Architecture Overview:
┌─────────────────────────────────────────────────────────────────┐
│                         Forge Core                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │ Capsules  │  │ Overlays  │  │Governance │  │ Compliance│    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │              │           │
│        └──────────────┴──────────────┴──────────────┘           │
│                              │                                   │
├──────────────────────────────┼───────────────────────────────────┤
│                    Virtuals Integration Layer                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐    │
│  │   GAME    │  │    ACP    │  │Tokenization│  │  Revenue  │    │
│  │ Framework │  │ Commerce  │  │  Service   │  │  Service  │    │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘    │
│        │              │              │              │           │
│        └──────────────┴──────────────┴──────────────┘           │
│                              │                                   │
├──────────────────────────────┼───────────────────────────────────┤
│                     Multi-Chain Infrastructure                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                    │
│  │   Base    │  │ Ethereum  │  │  Solana   │                    │
│  │ (Primary) │  │ (Bridge)  │  │(Optional) │                    │
│  └───────────┘  └───────────┘  └───────────┘                    │
└─────────────────────────────────────────────────────────────────┘

Quick Start:
    # 1. Configure environment
    export VIRTUALS_API_KEY="your-game-api-key"
    export VIRTUALS_OPERATOR_PRIVATE_KEY="0x..."

    # 2. Initialize services
    from forge.virtuals import initialize_virtuals
    await initialize_virtuals()

    # 3. Create a knowledge agent
    from forge.virtuals.game import get_game_client, create_knowledge_worker

    client = await get_game_client()
    agent = await client.create_agent(...)

    # 4. Enable tokenization (opt-in)
    from forge.virtuals.tokenization import get_tokenization_service

    service = await get_tokenization_service()
    await service.request_tokenization(...)

For detailed documentation and examples, see:
- docs/virtuals-integration.md
- examples/knowledge_agent.py
- examples/tokenized_overlay.py
"""

__version__ = "0.1.0"

# Configuration
from .acp import ACPService, get_acp_service
from .bridge import BridgeRoute, BridgeService, BridgeStatus, get_bridge_service
from .chains import MultiChainManager, get_chain_manager
from .config import (
    ChainNetwork,
    VirtualsConfig,
    VirtualsEnvironment,
    configure_virtuals,
    get_virtuals_config,
)

# Service access functions
from .game import GAMESDKClient, get_game_client

# Models (re-export commonly used models)
from .models import (
    # ACP models
    ACPJob,
    ACPJobCreate,
    ACPJobStatus,
    ACPPhase,
    AgentGoals,
    AgentPersonality,
    AgentStatus,
    # Agent models
    ForgeAgent,
    ForgeAgentCreate,
    JobOffering,
    RevenueRecord,
    RevenueShare,
    RevenueType,
    TokenDistribution,
    TokenInfo,
    TokenizationRequest,
    TokenizationStatus,
    # Tokenization models
    TokenizedEntity,
    TransactionRecord,
    # Base models
    WalletInfo,
    WorkerDefinition,
)
from .revenue import RevenueService, get_revenue_service
from .tipping import FrowgTippingService, TipCategory, TipRecord, TipStatus
from .tokenization import TokenizationService, get_tokenization_service


async def initialize_virtuals() -> dict[str, any]:
    """
    Initialize all Virtuals Protocol integration services.

    This convenience function initializes all required services
    in the correct order, handling dependencies and configuration.

    Returns:
        Dict containing initialized service instances

    Example:
        services = await initialize_virtuals()
        game_client = services['game']
        chain_manager = services['chains']
    """
    config = get_virtuals_config()

    # Initialize in dependency order
    chain_manager = await get_chain_manager()
    game_client = await get_game_client()

    return {
        'config': config,
        'chains': chain_manager,
        'game': game_client,
        # ACP, tokenization, and revenue require repositories
        # which are provided by the Forge application
    }


__all__ = [
    # Version
    "__version__",
    # Configuration
    "VirtualsConfig",
    "VirtualsEnvironment",
    "ChainNetwork",
    "get_virtuals_config",
    "configure_virtuals",
    # Models
    "ForgeAgent",
    "ForgeAgentCreate",
    "AgentStatus",
    "AgentPersonality",
    "AgentGoals",
    "WorkerDefinition",
    "TokenizedEntity",
    "TokenizationRequest",
    "TokenizationStatus",
    "TokenDistribution",
    "RevenueShare",
    "ACPJob",
    "ACPJobCreate",
    "ACPPhase",
    "ACPJobStatus",
    "JobOffering",
    "WalletInfo",
    "TokenInfo",
    "TransactionRecord",
    "RevenueRecord",
    "RevenueType",
    # Services
    "get_game_client",
    "GAMESDKClient",
    "get_acp_service",
    "ACPService",
    "get_tokenization_service",
    "TokenizationService",
    "get_revenue_service",
    "RevenueService",
    "get_chain_manager",
    "MultiChainManager",
    # Tipping
    "FrowgTippingService",
    "TipRecord",
    "TipStatus",
    "TipCategory",
    # Bridge
    "BridgeService",
    "BridgeRoute",
    "BridgeStatus",
    "get_bridge_service",
    # Initialization
    "initialize_virtuals",
]
