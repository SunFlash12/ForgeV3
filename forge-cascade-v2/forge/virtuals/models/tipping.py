"""
FROWG Tipping Models

Optional social tipping layer using $FROWG tokens on Solana.
Tips are purely for social recognition - no functional impact on Forge.

Token: $FROWG (Rise of Frowg)
Address: uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump
Chain: Solana
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

# FROWG token constants
FROWG_TOKEN_MINT = "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump"
FROWG_DECIMALS = 9


class TipTargetType(str, Enum):
    """What can be tipped."""
    AGENT = "agent"      # Tip a GAME agent
    CAPSULE = "capsule"  # Tip a knowledge capsule creator
    USER = "user"        # Tip a user directly


class Tip(BaseModel):
    """
    A FROWG tip record.

    Tips are optional social recognition - they don't affect
    rankings, trust scores, or any Forge functionality.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))

    # Sender
    sender_wallet: str = Field(description="Solana wallet that sent the tip")
    sender_user_id: str | None = Field(
        default=None,
        description="Forge user ID if logged in"
    )

    # Recipient
    target_type: TipTargetType
    target_id: str = Field(description="ID of agent/capsule/user being tipped")
    recipient_wallet: str = Field(description="Solana wallet receiving the tip")

    # Amount
    amount_frowg: float = Field(
        gt=0,
        description="Amount of $FROWG tokens"
    )
    amount_lamports: int = Field(
        default=0,
        description="Amount in smallest units (for precision)"
    )

    # Optional message
    message: str | None = Field(
        default=None,
        max_length=280,
        description="Optional tip message (tweet-length)"
    )

    # Transaction
    tx_signature: str | None = Field(
        default=None,
        description="Solana transaction signature"
    )
    confirmed: bool = Field(
        default=False,
        description="Whether the transaction is confirmed on-chain"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confirmed_at: datetime | None = None

    def to_lamports(self) -> int:
        """Convert FROWG amount to lamports (smallest unit)."""
        return int(self.amount_frowg * (10 ** FROWG_DECIMALS))


class TipCreate(BaseModel):
    """Request to create a new tip."""
    target_type: TipTargetType
    target_id: str
    amount_frowg: float = Field(gt=0, le=1_000_000)
    message: str | None = Field(default=None, max_length=280)


class TipResponse(BaseModel):
    """Response after creating a tip."""
    tip_id: str
    tx_signature: str | None = None
    status: str = Field(description="pending, confirmed, or failed")
    message: str


class TipSummary(BaseModel):
    """Summary of tips for a target."""
    target_type: TipTargetType
    target_id: str
    total_tips: int
    total_frowg: float
    unique_tippers: int
    recent_tips: list[Tip] = Field(default_factory=list)


class TipLeaderboard(BaseModel):
    """Leaderboard of top tipped targets."""
    target_type: TipTargetType
    period: str = Field(description="all_time, monthly, weekly")
    entries: list[dict] = Field(
        default_factory=list,
        description="List of {target_id, total_frowg, tip_count}"
    )
