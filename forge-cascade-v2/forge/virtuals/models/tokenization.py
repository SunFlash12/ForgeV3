"""
Tokenization Models for Forge Entities

This module defines models for the opt-in tokenization of Forge entities
including Knowledge Capsules, Overlays, and Governance Proposals.

Tokenization transforms Forge assets into tradeable, revenue-generating
blockchain tokens with built-in incentive alignment through the Virtuals
Protocol bonding curve mechanism.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .base import TokenInfo, TokenizationStatus, VirtualsBaseModel


# FIX: Convert fake enum classes to proper Python Enum classes
class TokenizableEntityType(str, Enum):
    """Types of Forge entities that can be tokenized."""

    CAPSULE = "capsule"
    OVERLAY = "overlay"
    AGENT = "agent"
    CAPSULE_COLLECTION = "capsule_collection"
    GOVERNANCE_PROPOSAL = "governance_proposal"


class TokenLaunchType(str, Enum):
    """Launch type for tokenization."""

    STANDARD = "standard"  # Bonding curve with 42K graduation
    GENESIS = "genesis"  # Presale with tiers


class GenesisTier(str, Enum):
    """Tiers for Genesis launches."""

    TIER_1 = "tier_1"  # 21K VIRTUAL threshold
    TIER_2 = "tier_2"  # 42K VIRTUAL threshold
    TIER_3 = "tier_3"  # 100K VIRTUAL threshold


class TokenDistribution(BaseModel):
    """
    Distribution of token supply among stakeholders.

    Standard Virtuals distribution is:
    - 60% public circulation
    - 35% ecosystem treasury
    - 5% liquidity pool
    """

    public_circulation_percent: float = Field(default=60.0, ge=0, le=100)
    ecosystem_treasury_percent: float = Field(default=35.0, ge=0, le=100)
    liquidity_pool_percent: float = Field(default=5.0, ge=0, le=100)
    creator_allocation_percent: float = Field(
        default=0.0, ge=0, le=100, description="Optional creator allocation (reduces public %)"
    )

    @field_validator("creator_allocation_percent")
    @classmethod
    def validate_total(cls, v: float, info: ValidationInfo) -> float:
        """Ensure allocations don't exceed 100%."""
        data = info.data
        total = (
            data.get("public_circulation_percent", 60)
            + data.get("ecosystem_treasury_percent", 35)
            + data.get("liquidity_pool_percent", 5)
            + v
        )
        if total > 100:
            raise ValueError("Total allocation cannot exceed 100%")
        return v


class RevenueShare(BaseModel):
    """
    Configuration for revenue sharing from tokenized entity.

    Revenue from the entity flows back to token holders through
    buyback-and-burn mechanics and direct distributions.
    """

    creator_share_percent: float = Field(
        default=30.0, ge=0, le=100, description="Share to original creator/owner"
    )
    contributor_share_percent: float = Field(
        default=20.0, ge=0, le=100, description="Share to contributors (via Contribution Vault)"
    )
    treasury_share_percent: float = Field(
        default=50.0, ge=0, le=100, description="Share to entity treasury for operations"
    )
    buyback_burn_percent: float = Field(
        default=50.0, ge=0, le=100, description="Percent of treasury used for buyback-burn"
    )


class TokenizationRequest(BaseModel):
    """
    Request to tokenize a Forge entity.

    This initiates the tokenization process which requires:
    1. Entity owner authorization
    2. Initial VIRTUAL stake (minimum 100)
    3. Token configuration
    """

    # Entity Reference
    entity_type: str = Field(description="Type of entity being tokenized")
    entity_id: str = Field(description="ID of the Forge entity")

    # Token Configuration
    token_name: str = Field(max_length=64, description="Full name for the token")
    token_symbol: str = Field(max_length=10, description="Ticker symbol (e.g., FRGCAP)")
    token_description: str = Field(
        max_length=2000, description="Description shown on exchanges and explorers"
    )

    # Launch Configuration
    launch_type: str = Field(
        default=TokenLaunchType.STANDARD, description="standard or genesis launch"
    )
    genesis_tier: str | None = Field(default=None, description="If genesis launch, which tier")

    # Stake
    initial_stake_virtual: float = Field(ge=100.0, description="Initial VIRTUAL tokens to stake")

    # Distribution
    distribution: TokenDistribution = Field(default_factory=TokenDistribution)

    # Revenue Configuration
    revenue_share: RevenueShare = Field(default_factory=RevenueShare)

    # Governance
    enable_holder_governance: bool = Field(
        default=True, description="Allow token holders to vote on entity decisions"
    )
    governance_quorum_percent: float = Field(
        default=10.0, ge=1.0, le=100.0, description="Minimum participation for valid votes"
    )

    # Chain Selection
    primary_chain: str = Field(default="base", description="Primary chain for token deployment")
    enable_multichain: bool = Field(
        default=False, description="Whether to enable cross-chain bridging"
    )

    # Owner Authorization
    owner_wallet: str = Field(description="Wallet authorizing tokenization")
    owner_signature: str | None = Field(
        default=None, description="Signature authorizing the tokenization"
    )

    @field_validator("token_symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase alphanumeric."""
        v = v.upper()
        if not v.isalnum():
            raise ValueError("Symbol must be alphanumeric")
        return v


class TokenizedEntity(VirtualsBaseModel):
    """
    A Forge entity that has been tokenized on Virtuals Protocol.

    This represents the complete tokenization state including
    bonding curve progress, holder information, and revenue metrics.
    """

    # Entity Reference
    entity_type: str
    entity_id: str

    # Token Information
    token_info: TokenInfo

    # Launch Information
    launch_type: str
    genesis_tier: str | None = None

    # Distribution
    distribution: TokenDistribution
    revenue_share: RevenueShare

    # Status
    status: TokenizationStatus = Field(default=TokenizationStatus.PENDING)

    # Bonding Curve State (if not yet graduated)
    bonding_curve_virtual_accumulated: float = Field(default=0.0)
    bonding_curve_contributors: int = Field(default=0)
    estimated_graduation_date: datetime | None = None

    # Post-Graduation State
    graduation_tx_hash: str | None = None
    graduated_at: datetime | None = None
    liquidity_pool_address: str | None = None
    liquidity_locked_until: datetime | None = None

    # Holder Information
    total_holders: int = Field(default=0)
    top_holders: list[dict[str, Any]] = Field(default_factory=list)

    # Revenue Metrics
    total_revenue_generated: float = Field(default=0.0)
    total_buyback_burned: float = Field(default=0.0)
    total_distributed_to_holders: float = Field(default=0.0)

    # Governance State
    enable_holder_governance: bool = Field(default=True)
    governance_quorum_percent: float = Field(default=10.0)
    active_proposals: int = Field(default=0)
    total_proposals: int = Field(default=0)

    # Multi-chain State
    is_multichain: bool = Field(default=False)
    bridged_chains: list[str] = Field(default_factory=list)
    chain_token_addresses: dict[str, str] = Field(
        default_factory=dict, description="Token addresses by chain"
    )

    # Contribution Vault
    contribution_vault_address: str | None = None
    total_contributions: int = Field(default=0)

    # Transactions
    creation_tx_hash: str | None = None

    def is_graduated(self) -> bool:
        """Check if token has graduated from bonding curve."""
        return self.status in [TokenizationStatus.GRADUATED, TokenizationStatus.BRIDGED]

    def graduation_progress(self) -> float:
        """Calculate progress toward graduation (0.0 to 1.0)."""
        threshold = 42000  # Standard graduation threshold
        if self.genesis_tier == GenesisTier.TIER_1:
            threshold = 21000
        elif self.genesis_tier == GenesisTier.TIER_3:
            threshold = 100000
        return min(1.0, self.bonding_curve_virtual_accumulated / threshold)


class ContributionRecord(BaseModel):
    """
    Record of a contribution to a tokenized entity.

    Contributions are stored in the Immutable Contribution Vault
    and can earn ongoing rewards from the entity's revenue.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    tokenized_entity_id: str
    contributor_wallet: str

    # Contribution Details
    contribution_type: str = Field(description="Type: data, model, code, curation, etc.")
    contribution_description: str
    contribution_hash: str = Field(description="Hash of the contributed content")

    # Validation
    validated_by: str | None = Field(default=None, description="Agent or address that validated")
    validation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_approved: bool = Field(default=False)

    # Rewards
    reward_share_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of contributor pool this contribution earns",
    )
    total_rewards_earned: float = Field(default=0.0)

    # NFT Representation (ERC-1155 Service NFT)
    contribution_nft_id: str | None = None
    contribution_nft_tx_hash: str | None = None

    # Timestamps
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None


class TokenHolderGovernanceVote(BaseModel):
    """Vote cast by a token holder on a governance proposal."""

    voter_wallet: str
    tokenized_entity_id: str
    proposal_id: str
    vote: str = Field(description="for, against, or abstain")
    voting_power: float = Field(description="Voting power based on token holdings")
    voted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tx_hash: str | None = None


class TokenHolderProposal(BaseModel):
    """
    Governance proposal created by token holders.

    Proposals can modify entity parameters, allocate treasury funds,
    or make other decisions about the tokenized entity.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    tokenized_entity_id: str
    proposer_wallet: str

    # Proposal Content
    title: str = Field(max_length=200)
    description: str = Field(max_length=5000)
    proposal_type: str = Field(description="parameter_change, treasury_allocation, etc.")
    proposed_changes: dict[str, Any] = Field(description="Specific changes being proposed")

    # Voting State
    voting_starts: datetime
    voting_ends: datetime
    votes_for: float = Field(default=0.0)
    votes_against: float = Field(default=0.0)
    votes_abstain: float = Field(default=0.0)
    total_voters: int = Field(default=0)

    # Requirements
    quorum_required: float
    quorum_reached: bool = Field(default=False)

    # Outcome
    status: str = Field(
        default="active", description="active, passed, rejected, executed, cancelled"
    )
    execution_tx_hash: str | None = None
    executed_at: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BondingCurveContribution(BaseModel):
    """Record of a contribution to an entity's bonding curve."""

    contributor_wallet: str
    tokenized_entity_id: str
    amount_virtual: float
    tokens_received: float = Field(description="FERC20 placeholder tokens received")
    price_at_contribution: float = Field(description="Price per token at time of contribution")
    contributed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tx_hash: str
