"""
Virtuals Protocol Integration Models

This package contains all data models for integrating Forge with
Virtuals Protocol, including agent definitions, ACP transactions,
and tokenization structures.
"""

from .acp import (
    ACPDeliverable,
    ACPDispute,
    ACPEvaluation,
    ACPJob,
    ACPJobCreate,
    ACPMemo,
    ACPNegotiationTerms,
    ACPRegistryEntry,
    ACPStats,
    # ACP Models
    JobOffering,
    # Payment tokens
    PaymentToken,
    TokenPayment,
)
from .agent import (
    AgentGoals,
    AgentListResponse,
    AgentMemoryConfig,
    AgentPersonality,
    AgentStats,
    AgentUpdate,
    ForgeAgent,
    ForgeAgentCreate,
    WorkerDefinition,
)
from .base import (
    ACPJobStatus,
    ACPPhase,
    AgentStatus,
    BridgeRequest,
    RevenueRecord,
    RevenueType,
    TokenInfo,
    # Enums
    TokenizationStatus,
    TransactionRecord,
    # Base Models
    VirtualsBaseModel,
    WalletInfo,
)
from .tipping import (
    FROWG_DECIMALS,
    FROWG_TOKEN_MINT,
    Tip,
    TipCreate,
    TipLeaderboard,
    TipResponse,
    TipSummary,
    TipTargetType,
)
from .tokenization import (
    BondingCurveContribution,
    ContributionRecord,
    GenesisTier,
    RevenueShare,
    TokenDistribution,
    TokenHolderGovernanceVote,
    TokenHolderProposal,
    TokenizableEntityType,
    TokenizationRequest,
    TokenizedEntity,
    TokenLaunchType,
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
