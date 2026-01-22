"""
Virtuals Protocol Integration Models

This package contains all data models for integrating Forge with
Virtuals Protocol, including agent definitions, ACP transactions,
and tokenization structures.
"""

from .base import (
    # Enums
    TokenizationStatus,
    AgentStatus,
    ACPPhase,
    ACPJobStatus,
    RevenueType,
    # Base Models
    VirtualsBaseModel,
    WalletInfo,
    TokenInfo,
    TransactionRecord,
    RevenueRecord,
    BridgeRequest,
)

from .agent import (
    AgentPersonality,
    WorkerDefinition,
    AgentGoals,
    AgentMemoryConfig,
    ForgeAgentCreate,
    ForgeAgent,
    AgentUpdate,
    AgentStats,
    AgentListResponse,
)

from .acp import (
    # Payment tokens
    PaymentToken,
    TokenPayment,
    # ACP Models
    JobOffering,
    ACPMemo,
    ACPJob,
    ACPJobCreate,
    ACPNegotiationTerms,
    ACPDeliverable,
    ACPEvaluation,
    ACPDispute,
    ACPRegistryEntry,
    ACPStats,
)

from .tokenization import (
    TokenizableEntityType,
    TokenLaunchType,
    GenesisTier,
    TokenDistribution,
    RevenueShare,
    TokenizationRequest,
    TokenizedEntity,
    ContributionRecord,
    TokenHolderGovernanceVote,
    TokenHolderProposal,
    BondingCurveContribution,
)

from .tipping import (
    FROWG_TOKEN_MINT,
    FROWG_DECIMALS,
    TipTargetType,
    Tip,
    TipCreate,
    TipResponse,
    TipSummary,
    TipLeaderboard,
)

__all__ = [
    # Base Enums
    "TokenizationStatus",
    "AgentStatus",
    "ACPPhase",
    "ACPJobStatus",
    "RevenueType",
    # Base Models
    "VirtualsBaseModel",
    "WalletInfo",
    "TokenInfo",
    "TransactionRecord",
    "RevenueRecord",
    "BridgeRequest",
    # Agent Models
    "AgentPersonality",
    "WorkerDefinition",
    "AgentGoals",
    "AgentMemoryConfig",
    "ForgeAgentCreate",
    "ForgeAgent",
    "AgentUpdate",
    "AgentStats",
    "AgentListResponse",
    # Payment Tokens
    "PaymentToken",
    "TokenPayment",
    # ACP Models
    "JobOffering",
    "ACPMemo",
    "ACPJob",
    "ACPJobCreate",
    "ACPNegotiationTerms",
    "ACPDeliverable",
    "ACPEvaluation",
    "ACPDispute",
    "ACPRegistryEntry",
    "ACPStats",
    # Tokenization Models
    "TokenizableEntityType",
    "TokenLaunchType",
    "GenesisTier",
    "TokenDistribution",
    "RevenueShare",
    "TokenizationRequest",
    "TokenizedEntity",
    "ContributionRecord",
    "TokenHolderGovernanceVote",
    "TokenHolderProposal",
    "BondingCurveContribution",
    # Tipping Models
    "FROWG_TOKEN_MINT",
    "FROWG_DECIMALS",
    "TipTargetType",
    "Tip",
    "TipCreate",
    "TipResponse",
    "TipSummary",
    "TipLeaderboard",
]
