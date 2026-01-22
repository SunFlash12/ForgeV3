"""
FROWG Tipping Service

Optional social tipping layer for Forge using $FROWG tokens.
This is purely for social recognition - tips have no functional impact.

Usage:
    from forge.services.tipping_service import get_tipping_service

    service = get_tipping_service()
    tip = await service.create_tip(
        sender_wallet="...",
        target_type=TipTargetType.CAPSULE,
        target_id="capsule-123",
        recipient_wallet="...",
        amount_frowg=100.0,
        message="Great insight!"
    )
"""

import logging
from datetime import UTC, datetime
from typing import Optional

import structlog

from forge.database.client import Neo4jClient
from forge.virtuals.models.tipping import (
    FROWG_TOKEN_MINT,
    Tip,
    TipCreate,
    TipLeaderboard,
    TipResponse,
    TipSummary,
    TipTargetType,
)

logger = structlog.get_logger(__name__)


class TippingService:
    """
    Service for managing FROWG tips.

    Tips are stored in Neo4j and optionally verified on-chain.
    This is a social layer only - no impact on Forge functionality.
    """

    def __init__(self, db_client: Neo4jClient):
        self._db = db_client
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the tipping service and ensure indexes exist."""
        if self._initialized:
            return

        # Create indexes for tip queries
        async with self._db.session() as session:
            await session.run("""
                CREATE INDEX tip_target_idx IF NOT EXISTS
                FOR (t:Tip) ON (t.target_type, t.target_id)
            """)
            await session.run("""
                CREATE INDEX tip_sender_idx IF NOT EXISTS
                FOR (t:Tip) ON (t.sender_wallet)
            """)
            await session.run("""
                CREATE INDEX tip_confirmed_idx IF NOT EXISTS
                FOR (t:Tip) ON (t.confirmed)
            """)

        self._initialized = True
        logger.info("tipping_service_initialized")

    async def create_tip(
        self,
        sender_wallet: str,
        target_type: TipTargetType,
        target_id: str,
        recipient_wallet: str,
        amount_frowg: float,
        message: Optional[str] = None,
        sender_user_id: Optional[str] = None,
        tx_signature: Optional[str] = None,
    ) -> Tip:
        """
        Create a new tip record.

        The tip is stored in the database. If tx_signature is provided,
        it will be marked for confirmation tracking.

        Args:
            sender_wallet: Solana wallet sending the tip
            target_type: What is being tipped (agent/capsule/user)
            target_id: ID of the target
            recipient_wallet: Solana wallet receiving the tip
            amount_frowg: Amount of $FROWG tokens
            message: Optional message (max 280 chars)
            sender_user_id: Optional Forge user ID
            tx_signature: Optional Solana transaction signature

        Returns:
            The created Tip record
        """
        tip = Tip(
            sender_wallet=sender_wallet,
            sender_user_id=sender_user_id,
            target_type=target_type,
            target_id=target_id,
            recipient_wallet=recipient_wallet,
            amount_frowg=amount_frowg,
            amount_lamports=tip.to_lamports() if amount_frowg else 0,
            message=message,
            tx_signature=tx_signature,
            confirmed=False,
        )
        tip.amount_lamports = tip.to_lamports()

        # Store in Neo4j
        async with self._db.session() as session:
            await session.run(
                """
                CREATE (t:Tip {
                    id: $id,
                    sender_wallet: $sender_wallet,
                    sender_user_id: $sender_user_id,
                    target_type: $target_type,
                    target_id: $target_id,
                    recipient_wallet: $recipient_wallet,
                    amount_frowg: $amount_frowg,
                    amount_lamports: $amount_lamports,
                    message: $message,
                    tx_signature: $tx_signature,
                    confirmed: $confirmed,
                    created_at: datetime($created_at)
                })
                """,
                id=tip.id,
                sender_wallet=tip.sender_wallet,
                sender_user_id=tip.sender_user_id,
                target_type=tip.target_type.value,
                target_id=tip.target_id,
                recipient_wallet=tip.recipient_wallet,
                amount_frowg=tip.amount_frowg,
                amount_lamports=tip.amount_lamports,
                message=tip.message,
                tx_signature=tip.tx_signature,
                confirmed=tip.confirmed,
                created_at=tip.created_at.isoformat(),
            )

        logger.info(
            "tip_created",
            tip_id=tip.id,
            target_type=target_type.value,
            target_id=target_id,
            amount_frowg=amount_frowg,
        )

        return tip

    async def confirm_tip(self, tip_id: str, tx_signature: str) -> bool:
        """Mark a tip as confirmed on-chain."""
        async with self._db.session() as session:
            result = await session.run(
                """
                MATCH (t:Tip {id: $tip_id})
                SET t.confirmed = true,
                    t.tx_signature = $tx_signature,
                    t.confirmed_at = datetime()
                RETURN t.id as id
                """,
                tip_id=tip_id,
                tx_signature=tx_signature,
            )
            record = await result.single()
            return record is not None

    async def get_tip(self, tip_id: str) -> Optional[Tip]:
        """Get a tip by ID."""
        async with self._db.session() as session:
            result = await session.run(
                "MATCH (t:Tip {id: $tip_id}) RETURN t",
                tip_id=tip_id,
            )
            record = await result.single()
            if not record:
                return None
            return self._record_to_tip(record["t"])

    async def get_tips_for_target(
        self,
        target_type: TipTargetType,
        target_id: str,
        limit: int = 50,
        confirmed_only: bool = True,
    ) -> list[Tip]:
        """Get all tips for a specific target."""
        async with self._db.session() as session:
            query = """
                MATCH (t:Tip {target_type: $target_type, target_id: $target_id})
                WHERE $confirmed_only = false OR t.confirmed = true
                RETURN t
                ORDER BY t.created_at DESC
                LIMIT $limit
            """
            result = await session.run(
                query,
                target_type=target_type.value,
                target_id=target_id,
                confirmed_only=confirmed_only,
                limit=limit,
            )
            records = await result.data()
            return [self._record_to_tip(r["t"]) for r in records]

    async def get_tip_summary(
        self,
        target_type: TipTargetType,
        target_id: str,
    ) -> TipSummary:
        """Get aggregated tip statistics for a target."""
        async with self._db.session() as session:
            result = await session.run(
                """
                MATCH (t:Tip {target_type: $target_type, target_id: $target_id, confirmed: true})
                RETURN
                    count(t) as total_tips,
                    coalesce(sum(t.amount_frowg), 0) as total_frowg,
                    count(DISTINCT t.sender_wallet) as unique_tippers
                """,
                target_type=target_type.value,
                target_id=target_id,
            )
            record = await result.single()

            # Get recent tips
            recent = await self.get_tips_for_target(
                target_type, target_id, limit=5
            )

            return TipSummary(
                target_type=target_type,
                target_id=target_id,
                total_tips=record["total_tips"] if record else 0,
                total_frowg=record["total_frowg"] if record else 0.0,
                unique_tippers=record["unique_tippers"] if record else 0,
                recent_tips=recent,
            )

    async def get_tips_by_sender(
        self,
        sender_wallet: str,
        limit: int = 50,
    ) -> list[Tip]:
        """Get all tips sent by a wallet."""
        async with self._db.session() as session:
            result = await session.run(
                """
                MATCH (t:Tip {sender_wallet: $sender_wallet})
                RETURN t
                ORDER BY t.created_at DESC
                LIMIT $limit
                """,
                sender_wallet=sender_wallet,
                limit=limit,
            )
            records = await result.data()
            return [self._record_to_tip(r["t"]) for r in records]

    async def get_leaderboard(
        self,
        target_type: TipTargetType,
        limit: int = 10,
    ) -> TipLeaderboard:
        """Get top tipped targets of a given type."""
        async with self._db.session() as session:
            result = await session.run(
                """
                MATCH (t:Tip {target_type: $target_type, confirmed: true})
                WITH t.target_id as target_id,
                     sum(t.amount_frowg) as total_frowg,
                     count(t) as tip_count
                ORDER BY total_frowg DESC
                LIMIT $limit
                RETURN target_id, total_frowg, tip_count
                """,
                target_type=target_type.value,
                limit=limit,
            )
            records = await result.data()

            return TipLeaderboard(
                target_type=target_type,
                period="all_time",
                entries=[
                    {
                        "target_id": r["target_id"],
                        "total_frowg": r["total_frowg"],
                        "tip_count": r["tip_count"],
                    }
                    for r in records
                ],
            )

    def _record_to_tip(self, record: dict) -> Tip:
        """Convert a Neo4j record to a Tip model."""
        return Tip(
            id=record["id"],
            sender_wallet=record["sender_wallet"],
            sender_user_id=record.get("sender_user_id"),
            target_type=TipTargetType(record["target_type"]),
            target_id=record["target_id"],
            recipient_wallet=record["recipient_wallet"],
            amount_frowg=record["amount_frowg"],
            amount_lamports=record.get("amount_lamports", 0),
            message=record.get("message"),
            tx_signature=record.get("tx_signature"),
            confirmed=record.get("confirmed", False),
            created_at=record["created_at"] if isinstance(record["created_at"], datetime) else datetime.fromisoformat(str(record["created_at"])),
            confirmed_at=record.get("confirmed_at"),
        )


# Global service instance
_tipping_service: Optional[TippingService] = None


def get_tipping_service() -> Optional[TippingService]:
    """Get the global tipping service instance."""
    return _tipping_service


async def init_tipping_service(db_client: Neo4jClient) -> TippingService:
    """Initialize the global tipping service."""
    global _tipping_service
    _tipping_service = TippingService(db_client)
    await _tipping_service.initialize()
    return _tipping_service
