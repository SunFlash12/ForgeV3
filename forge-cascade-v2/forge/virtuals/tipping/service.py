"""
FROWG Tipping Service Implementation

This module implements tipping functionality using the $FROWG token on Solana.
It provides a simple interface for sending tips to agents, capsule contributors,
and governance participants.

Token Details:
- Token: $FROWG
- Chain: Solana
- Mint Address: uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..chains import MultiChainManager as ChainManager
from ..config import ChainNetwork
from ..models import TransactionRecord
from ..tokenization.contracts import ContractAddresses

logger = logging.getLogger(__name__)


class TipStatus(str, Enum):
    """Status of a tip transaction."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class TipCategory(str, Enum):
    """Categories for tip allocation and analytics."""
    AGENT_REWARD = "agent_reward"           # Tip to an AI agent
    CAPSULE_CONTRIBUTION = "capsule_contribution"  # Reward for capsule creation
    GOVERNANCE_VOTE = "governance_vote"     # Reward for governance participation
    KNOWLEDGE_QUERY = "knowledge_query"     # Tip for valuable query response
    SERVICE_PAYMENT = "service_payment"     # Payment for ACP service
    COMMUNITY_GIFT = "community_gift"       # General community tip


class TipRecord(BaseModel):
    """Record of a tip transaction."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    sender_address: str = Field(description="Sender's Solana wallet address")
    recipient_address: str = Field(description="Recipient's Solana wallet address")
    amount: Decimal = Field(description="Amount of FROWG tokens")
    category: TipCategory = Field(description="Category of the tip")
    status: TipStatus = Field(default=TipStatus.PENDING)
    tx_hash: str | None = Field(default=None, description="Transaction signature")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confirmed_at: datetime | None = Field(default=None)
    memo: str | None = Field(default=None, description="Optional memo/message")
    related_entity_id: str | None = Field(
        default=None,
        description="ID of related entity (agent, capsule, etc.)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class FrowgTippingService:
    """
    Service for sending FROWG token tips on Solana.

    This service provides a simple interface for tipping functionality:
    - Send tips to agents, contributors, and community members
    - Track tip history and analytics
    - Validate tip amounts and recipients

    Example:
        ```python
        from forge.virtuals.tipping import FrowgTippingService

        service = FrowgTippingService()
        await service.initialize()

        tip = await service.send_tip(
            sender_address="7B8xLj...",
            recipient_address="9Y3kMn...",
            amount=Decimal("10.0"),
            category=TipCategory.AGENT_REWARD,
            memo="Great knowledge response!"
        )
        ```
    """

    # FROWG token address on Solana
    FROWG_TOKEN_ADDRESS: str = ContractAddresses.SOLANA_MAINNET.get(
        "frowg_token",
    ) or "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump"

    # Minimum and maximum tip amounts
    MIN_TIP_AMOUNT = Decimal("0.001")
    MAX_TIP_AMOUNT = Decimal("1000000")

    def __init__(
        self,
        chain_manager: ChainManager | None = None,
        tip_fee_percentage: Decimal = Decimal("0.01"),  # 1% platform fee
    ):
        """
        Initialize the FROWG tipping service.

        Args:
            chain_manager: Optional chain manager for Solana operations.
                          If not provided, one will be created.
            tip_fee_percentage: Platform fee percentage (default 1%)
        """
        self._chain_manager = chain_manager
        self._tip_fee_percentage = tip_fee_percentage
        self._initialized = False
        self._tip_history: list[TipRecord] = []

    def _get_chain_manager(self) -> ChainManager:
        """Get the chain manager, raising if not initialized."""
        if self._chain_manager is None:
            raise RuntimeError("Tipping service not initialized. Call initialize() first.")
        return self._chain_manager

    async def initialize(self) -> None:
        """Initialize the tipping service and Solana connection."""
        if self._initialized:
            return

        if self._chain_manager is None:
            self._chain_manager = ChainManager()
            await self._chain_manager.initialize()

        # Verify FROWG token is accessible
        try:
            client = self._get_chain_manager().get_client(ChainNetwork.SOLANA)
            token_info = await client.get_token_info(self.FROWG_TOKEN_ADDRESS)
            logger.info(f"FROWG tipping service initialized. Token: {token_info.symbol}")
        except Exception as e:
            logger.warning(f"Could not verify FROWG token: {e}")

        self._initialized = True

    async def close(self) -> None:
        """Close the tipping service and release resources."""
        if self._chain_manager:
            await self._chain_manager.close()
        self._initialized = False

    async def send_tip(
        self,
        sender_address: str,
        recipient_address: str,
        amount: Decimal,
        category: TipCategory = TipCategory.COMMUNITY_GIFT,
        memo: str | None = None,
        related_entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TipRecord:
        """
        Send a FROWG tip to a recipient.

        Args:
            sender_address: Sender's Solana wallet address
            recipient_address: Recipient's Solana wallet address
            amount: Amount of FROWG to tip
            category: Category for the tip
            memo: Optional message to include
            related_entity_id: Optional ID of related entity
            metadata: Additional metadata

        Returns:
            TipRecord with transaction details

        Raises:
            ValueError: If amount is invalid
            TipError: If transaction fails
        """
        if not self._initialized:
            await self.initialize()

        # Validate amount
        if amount < self.MIN_TIP_AMOUNT:
            raise ValueError(f"Tip amount must be at least {self.MIN_TIP_AMOUNT} FROWG")
        if amount > self.MAX_TIP_AMOUNT:
            raise ValueError(f"Tip amount cannot exceed {self.MAX_TIP_AMOUNT} FROWG")

        # Create tip record
        tip = TipRecord(
            sender_address=sender_address,
            recipient_address=recipient_address,
            amount=amount,
            category=category,
            memo=memo,
            related_entity_id=related_entity_id,
            metadata=metadata or {},
        )

        try:
            # Get Solana client
            client = self._get_chain_manager().get_client(ChainNetwork.SOLANA)

            # Execute token transfer
            tx_record: TransactionRecord = await client.transfer_tokens(
                token_address=self.FROWG_TOKEN_ADDRESS,
                to_address=recipient_address,
                amount=float(amount),
            )

            tip.tx_hash = tx_record.tx_hash
            tip.status = TipStatus.PENDING

            # Wait for confirmation
            confirmed_tx = await client.wait_for_transaction(
                tx_record.tx_hash,
                timeout_seconds=60
            )

            if confirmed_tx.status == "success":
                tip.status = TipStatus.CONFIRMED
                tip.confirmed_at = datetime.now(UTC)
                logger.info(
                    f"Tip confirmed: {amount} FROWG from {sender_address[:8]}... "
                    f"to {recipient_address[:8]}... (tx: {tip.tx_hash[:16]}...)"
                )
            else:
                tip.status = TipStatus.FAILED
                logger.error(f"Tip failed: {tip.tx_hash}")

        except Exception as e:
            tip.status = TipStatus.FAILED
            tip.metadata["error"] = str(e)
            logger.error(f"Failed to send tip: {e}")
            raise TipError(f"Failed to send tip: {e}") from e

        self._tip_history.append(tip)
        return tip

    async def get_balance(self, address: str) -> Decimal:
        """
        Get FROWG token balance for an address.

        Args:
            address: Solana wallet address

        Returns:
            FROWG token balance
        """
        if not self._initialized:
            await self.initialize()

        client = self._get_chain_manager().get_client(ChainNetwork.SOLANA)
        balance = await client.get_wallet_balance(
            address=address,
            token_address=self.FROWG_TOKEN_ADDRESS
        )
        return Decimal(str(balance))

    async def estimate_tip_fee(self, amount: Decimal) -> dict[str, Decimal]:
        """
        Estimate fees for a tip transaction.

        Args:
            amount: Tip amount in FROWG

        Returns:
            Dict with fee breakdown:
            - platform_fee: Platform's cut
            - network_fee: Solana transaction fee (in SOL)
            - total_deducted: Total amount deducted from tip
            - recipient_receives: Amount recipient receives
        """
        platform_fee = amount * self._tip_fee_percentage
        # Solana network fees are typically ~0.000005 SOL, negligible
        network_fee_sol = Decimal("0.000005")

        return {
            "platform_fee": platform_fee,
            "network_fee_sol": network_fee_sol,
            "recipient_receives": amount - platform_fee,
            "tip_amount": amount,
        }

    def get_tip_history(
        self,
        address: str | None = None,
        category: TipCategory | None = None,
        limit: int = 100,
    ) -> list[TipRecord]:
        """
        Get tip history with optional filters.

        Args:
            address: Filter by sender or recipient address
            category: Filter by tip category
            limit: Maximum number of records to return

        Returns:
            List of matching TipRecords
        """
        filtered = self._tip_history

        if address:
            filtered = [
                t for t in filtered
                if t.sender_address == address or t.recipient_address == address
            ]

        if category:
            filtered = [t for t in filtered if t.category == category]

        return sorted(
            filtered,
            key=lambda t: t.created_at,
            reverse=True
        )[:limit]

    async def get_tip_statistics(
        self,
        address: str | None = None,
    ) -> dict[str, Any]:
        """
        Get tipping statistics.

        Args:
            address: Optional address to filter by

        Returns:
            Statistics including total tips, amounts, categories
        """
        tips = self.get_tip_history(address=address, limit=10000)

        total_sent = sum(
            t.amount for t in tips
            if address is None or t.sender_address == address
        )
        total_received = sum(
            t.amount for t in tips
            if address is None or t.recipient_address == address
        )

        by_category = {}
        for cat in TipCategory:
            cat_tips = [t for t in tips if t.category == cat]
            by_category[cat.value] = {
                "count": len(cat_tips),
                "total": sum(t.amount for t in cat_tips),
            }

        return {
            "total_tips": len(tips),
            "total_sent": total_sent,
            "total_received": total_received,
            "confirmed_tips": len([t for t in tips if t.status == TipStatus.CONFIRMED]),
            "failed_tips": len([t for t in tips if t.status == TipStatus.FAILED]),
            "by_category": by_category,
        }


class TipError(Exception):
    """Error raised when a tip operation fails."""
    pass
