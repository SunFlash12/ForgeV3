"""
Base Models for Virtuals Protocol Integration

This module defines the fundamental data structures used throughout
the Virtuals Protocol integration layer. These models serve as the
foundation for agent management, tokenization, and commerce operations.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class TokenizationStatus(str, Enum):
    """
    Status of an entity's tokenization process.

    The tokenization lifecycle moves through these states:
    NOT_TOKENIZED -> PENDING -> BONDING -> GRADUATED -> (optionally) BRIDGED
    """

    NOT_TOKENIZED = "not_tokenized"  # Entity has not opted into tokenization
    PENDING = "pending"  # Tokenization requested, awaiting processing
    BONDING = "bonding"  # In bonding curve phase, accumulating VIRTUAL
    GRADUATED = "graduated"  # Reached threshold, full token with liquidity
    BRIDGED = "bridged"  # Token has been bridged to another chain
    FAILED = "failed"  # Tokenization failed
    REVOKED = "revoked"  # Tokenization revoked by owner


class AgentStatus(str, Enum):
    """
    Operational status of a Virtuals GAME agent.

    Agents can be in various states depending on their
    lifecycle and operational health.
    """

    PROTOTYPE = "prototype"  # Pre-graduation, limited functionality
    SENTIENT = "sentient"  # Graduated, full autonomous capabilities
    SUSPENDED = "suspended"  # Temporarily disabled
    TERMINATED = "terminated"  # Permanently shut down


class ACPPhase(str, Enum):
    """
    The four phases of the Agent Commerce Protocol.

    Each transaction progresses through these phases sequentially,
    with cryptographic verification at each transition.
    """

    REQUEST = "request"  # Initial job posting/discovery
    NEGOTIATION = "negotiation"  # Terms agreement and signing
    TRANSACTION = "transaction"  # Payment escrow and work execution
    EVALUATION = "evaluation"  # Delivery verification and fund release


class ACPJobStatus(str, Enum):
    """Status of an ACP job throughout its lifecycle."""

    OPEN = "open"  # Job posted, awaiting providers
    NEGOTIATING = "negotiating"  # In negotiation phase
    IN_PROGRESS = "in_progress"  # Work being performed
    DELIVERED = "delivered"  # Deliverables submitted
    EVALUATING = "evaluating"  # Under evaluation
    COMPLETED = "completed"  # Successfully completed
    DISPUTED = "disputed"  # Under dispute resolution
    CANCELLED = "cancelled"  # Cancelled before completion
    EXPIRED = "expired"  # Timed out


class RevenueType(str, Enum):
    """Types of revenue generated within the Forge-Virtuals ecosystem."""

    INFERENCE_FEE = "inference_fee"  # Per-query knowledge access
    SERVICE_FEE = "service_fee"  # Overlay-as-a-service
    GOVERNANCE_REWARD = "governance_reward"  # Voting participation
    TOKENIZATION_FEE = "tokenization_fee"  # Agent creation fee
    TRADING_FEE = "trading_fee"  # Sentient tax from trades
    BRIDGE_FEE = "bridge_fee"  # Cross-chain transfer fee


class VirtualsBaseModel(BaseModel):
    """
    Base model for all Virtuals-related entities.

    Provides common fields and configuration used across
    the integration layer.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique identifier for the entity"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of entity creation"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of last update"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible metadata storage"
    )

    model_config = {"json_schema_extra": {"examples": []}}


class WalletInfo(BaseModel):
    """
    Information about a blockchain wallet.

    Used to track wallets across different chains for
    multi-chain operations.
    """

    address: str = Field(description="Wallet address")
    chain: str = Field(description="Blockchain network identifier")
    wallet_type: str = Field(default="eoa", description="Type of wallet (eoa, tba, multisig)")
    is_token_bound: bool = Field(
        default=False, description="Whether this is an ERC-6551 token-bound account"
    )
    parent_nft_id: str | None = Field(
        default=None, description="If token-bound, the NFT ID that owns this wallet"
    )
    balance_virtual: float = Field(default=0.0, description="Current VIRTUAL token balance")

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str, info: ValidationInfo) -> str:
        """Basic validation of wallet address format."""
        # EVM addresses start with 0x and are 42 chars
        # Solana addresses are base58 encoded, typically 32-44 chars
        if v.startswith("0x"):
            if len(v) != 42:
                raise ValueError("Invalid EVM address length")
        elif len(v) < 32 or len(v) > 44:
            raise ValueError("Invalid Solana address length")
        return v


class TokenInfo(BaseModel):
    """
    Information about a tokenized asset.

    Tracks both the agent/capsule token and its relationship
    to the VIRTUAL token ecosystem.
    """

    token_address: str = Field(description="Token contract address")
    chain: str = Field(description="Blockchain network")
    symbol: str = Field(description="Token ticker symbol")
    name: str = Field(description="Full token name")
    total_supply: int = Field(
        default=1_000_000_000, description="Total token supply (1 billion standard)"
    )
    circulating_supply: int = Field(default=0, description="Currently circulating supply")
    liquidity_pool_address: str | None = Field(
        default=None, description="Address of the Uniswap/DEX liquidity pool"
    )
    bonding_curve_progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Progress toward graduation (0.0 to 1.0)"
    )
    is_graduated: bool = Field(
        default=False, description="Whether token has graduated from bonding curve"
    )
    market_cap_virtual: float = Field(default=0.0, description="Market cap denominated in VIRTUAL")


class TransactionRecord(BaseModel):
    """
    Record of a blockchain transaction.

    Used for tracking all on-chain operations for audit
    and compliance purposes.
    """

    tx_hash: str = Field(description="Transaction hash")
    chain: str = Field(description="Blockchain network")
    block_number: int = Field(description="Block number containing transaction")
    timestamp: datetime = Field(description="Transaction timestamp")
    from_address: str = Field(description="Sender address")
    to_address: str = Field(description="Recipient address")
    value: float = Field(default=0.0, description="Value transferred")
    gas_used: int = Field(default=0, description="Gas consumed")
    status: str = Field(
        default="success", description="Transaction status (success, failed, pending)"
    )
    transaction_type: str = Field(
        description="Type of transaction (transfer, mint, burn, swap, etc.)"
    )
    related_entity_id: str | None = Field(
        default=None, description="ID of the Forge entity this transaction relates to"
    )
    error_message: str | None = Field(
        default=None, description="Error message if transaction failed"
    )


class RevenueRecord(BaseModel):
    """
    Record of revenue generated within the ecosystem.

    Tracks all revenue events for distribution and analytics.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revenue_type: RevenueType
    amount_virtual: float = Field(description="Amount in VIRTUAL tokens")
    amount_usd: float | None = Field(
        default=None, description="USD equivalent at time of transaction"
    )
    source_entity_id: str = Field(description="Entity that generated revenue")
    source_entity_type: str = Field(description="Type of source (capsule, overlay, agent)")
    beneficiary_addresses: list[str] = Field(
        default_factory=list, description="Addresses receiving revenue share"
    )
    distribution_complete: bool = Field(
        default=False, description="Whether revenue has been distributed"
    )
    tx_hash: str | None = Field(default=None, description="Transaction hash of distribution")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about revenue event"
    )


class BridgeRequest(BaseModel):
    """
    Request to bridge tokens between chains.

    Tracks cross-chain transfer operations using Wormhole
    or other bridge protocols.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_chain: str = Field(description="Origin blockchain")
    destination_chain: str = Field(description="Target blockchain")
    token_address: str = Field(description="Token being bridged")
    amount: float = Field(description="Amount to bridge")
    sender_address: str = Field(description="Sender on source chain")
    recipient_address: str = Field(description="Recipient on destination chain")
    status: str = Field(
        default="pending", description="Bridge status (pending, processing, completed, failed)"
    )
    source_tx_hash: str | None = Field(default=None)
    destination_tx_hash: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
    estimated_completion_minutes: int = Field(
        default=30, description="Estimated time for bridge completion"
    )
