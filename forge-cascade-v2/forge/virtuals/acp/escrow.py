"""
ACP Escrow Contract Interface

This module provides the interface for interacting with the ACP escrow
smart contract on Base L2. The escrow contract holds VIRTUAL tokens
during ACP job execution to ensure trustless payment.

Contract Functions:
- createEscrow: Lock funds for a new job
- releaseToProvider: Release funds to provider on completion
- refundToBuyer: Return funds on cancellation/dispute
- extendDeadline: Extend escrow timeout

Escrow Lifecycle:
1. Buyer creates job and locks funds in escrow
2. Provider delivers work
3. Buyer evaluates:
   - Approve: Funds released to provider
   - Dispute: Arbitration process
   - Timeout: Auto-release to provider after deadline
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..chains import MultiChainManager as ChainManager
from ..config import ChainNetwork, get_virtuals_config
from ..models import TransactionRecord

logger = logging.getLogger(__name__)


class EscrowStatus(str, Enum):
    """Status of an escrow."""
    PENDING = "pending"       # Created, awaiting funding
    FUNDED = "funded"         # Funds locked in contract
    RELEASED = "released"     # Funds released to provider
    REFUNDED = "refunded"     # Funds returned to buyer
    DISPUTED = "disputed"     # Under dispute resolution
    EXPIRED = "expired"       # Deadline passed without resolution


class EscrowRecord(BaseModel):
    """Record of an escrow transaction."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str = Field(description="Associated ACP job ID")
    buyer_address: str = Field(description="Buyer's wallet address")
    provider_address: str = Field(description="Provider's wallet address")
    amount: Decimal = Field(description="Escrowed VIRTUAL amount")
    fee_amount: Decimal = Field(default=Decimal("0"), description="Platform fee")
    status: EscrowStatus = Field(default=EscrowStatus.PENDING)

    # Contract state
    escrow_id_onchain: int | None = Field(default=None, description="On-chain escrow ID")
    funding_tx_hash: str | None = Field(default=None)
    release_tx_hash: str | None = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    funded_at: datetime | None = Field(default=None)
    deadline: datetime | None = Field(default=None)
    resolved_at: datetime | None = Field(default=None)

    metadata: dict[str, Any] = Field(default_factory=dict)


# Escrow Contract ABI (simplified for ACP)
ESCROW_ABI = [
    {
        "inputs": [
            {"name": "provider", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
            {"name": "jobHash", "type": "bytes32"},
        ],
        "name": "createEscrow",
        "outputs": [{"name": "escrowId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "escrowId", "type": "uint256"}],
        "name": "releaseToProvider",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "escrowId", "type": "uint256"}],
        "name": "refundToBuyer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "escrowId", "type": "uint256"},
            {"name": "newDeadline", "type": "uint256"},
        ],
        "name": "extendDeadline",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "escrowId", "type": "uint256"}],
        "name": "getEscrow",
        "outputs": [
            {
                "components": [
                    {"name": "buyer", "type": "address"},
                    {"name": "provider", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                    {"name": "jobHash", "type": "bytes32"},
                ],
                "name": "escrow",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "escrowId", "type": "uint256"}],
        "name": "initiateDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "escrowId", "type": "uint256"},
            {"name": "buyerShare", "type": "uint256"},  # Basis points (0-10000)
        ],
        "name": "resolveDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "escrowId", "type": "uint256"},
            {"indexed": True, "name": "buyer", "type": "address"},
            {"indexed": True, "name": "provider", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "escrowId", "type": "uint256"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowReleased",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "escrowId", "type": "uint256"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowRefunded",
        "type": "event"
    },
]


class EscrowService:
    """
    Service for managing ACP escrow transactions.

    This service interacts with the escrow smart contract to:
    - Create and fund escrows for ACP jobs
    - Release funds to providers on successful completion
    - Handle refunds for cancelled/disputed jobs
    - Monitor escrow status and deadlines

    Example:
        ```python
        from forge.virtuals.acp.escrow import EscrowService

        escrow_service = EscrowService()
        await escrow_service.initialize()

        # Create escrow for a job
        escrow = await escrow_service.create_escrow(
            job_id="job-123",
            buyer_address="0xBuyer...",
            provider_address="0xProvider...",
            amount=Decimal("100.0"),
            deadline_hours=24,
        )

        # Release on completion
        await escrow_service.release_escrow(escrow.id)
        ```
    """

    # Default escrow contract address (to be deployed)
    # This is a placeholder - real address should come from deployment
    DEFAULT_ESCROW_CONTRACT = None

    # Platform fee percentage
    PLATFORM_FEE_BPS = 100  # 1% = 100 basis points

    def __init__(
        self,
        chain_manager: ChainManager | None = None,
        escrow_contract_address: str | None = None,
    ):
        """
        Initialize the escrow service.

        Args:
            chain_manager: Optional chain manager for blockchain ops
            escrow_contract_address: Address of deployed escrow contract
        """
        self._chain_manager = chain_manager
        self._escrow_contract = escrow_contract_address or self.DEFAULT_ESCROW_CONTRACT
        self._config = get_virtuals_config()
        self._initialized = False
        self._escrows: dict[str, EscrowRecord] = {}
        # SECURITY FIX (Audit 5 - C2): Add lock to prevent race conditions
        self._escrow_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the escrow service."""
        if self._initialized:
            return

        if self._chain_manager is None:
            self._chain_manager = ChainManager()
            await self._chain_manager.initialize(ChainNetwork.BASE)  # type: ignore[call-arg]

        if not self._escrow_contract:
            logger.warning(
                "No escrow contract address configured. "
                "Escrow operations will use simulated mode."
            )

        self._initialized = True
        logger.info("Escrow service initialized")

    async def close(self) -> None:
        """Close the escrow service."""
        if self._chain_manager:
            await self._chain_manager.close()
        self._initialized = False

    async def create_escrow(
        self,
        job_id: str,
        buyer_address: str,
        provider_address: str,
        amount: Decimal,
        deadline_hours: int = 24,
        metadata: dict[str, Any] | None = None,
    ) -> EscrowRecord:
        """
        Create a new escrow for an ACP job.

        Args:
            job_id: Associated ACP job ID
            buyer_address: Buyer's wallet address
            provider_address: Provider's wallet address
            amount: Amount to escrow in VIRTUAL
            deadline_hours: Hours until escrow expires
            metadata: Optional metadata

        Returns:
            EscrowRecord with escrow details
        """
        if not self._initialized:
            await self.initialize()

        # Calculate platform fee
        fee_amount = amount * Decimal(self.PLATFORM_FEE_BPS) / Decimal(10000)

        # Create escrow record
        escrow = EscrowRecord(
            job_id=job_id,
            buyer_address=buyer_address,
            provider_address=provider_address,
            amount=amount,
            fee_amount=fee_amount,
            deadline=datetime.now(UTC) + timedelta(hours=deadline_hours),
            metadata=metadata or {},
        )

        try:
            if self._escrow_contract:
                # On-chain escrow creation
                tx_record = await self._create_onchain_escrow(escrow)
                escrow.funding_tx_hash = tx_record.tx_hash
                escrow.status = EscrowStatus.FUNDED
                escrow.funded_at = datetime.now(UTC)
            else:
                # Simulated mode - just mark as funded
                escrow.status = EscrowStatus.FUNDED
                escrow.funded_at = datetime.now(UTC)
                logger.info(f"Simulated escrow created for job {job_id}")

        except (ValueError, ConnectionError, TimeoutError, OSError) as e:
            escrow.status = EscrowStatus.PENDING
            escrow.metadata["error"] = str(e)
            logger.error(f"Failed to create escrow: {e}")
            raise EscrowError(f"Escrow creation failed: {e}") from e

        self._escrows[escrow.id] = escrow
        return escrow

    async def _get_escrow_lock(self, escrow_id: str) -> asyncio.Lock:
        """
        Get or create a lock for a specific escrow.

        SECURITY FIX (Audit 5 - C2): Prevents race conditions on escrow operations.
        """
        async with self._global_lock:
            if escrow_id not in self._escrow_locks:
                self._escrow_locks[escrow_id] = asyncio.Lock()
            return self._escrow_locks[escrow_id]

    async def _create_onchain_escrow(self, escrow: EscrowRecord) -> TransactionRecord:
        """Create escrow on blockchain."""
        import hashlib

        if self._chain_manager is None:
            raise EscrowError("Chain manager not initialized")

        client = self._chain_manager.get_client(ChainNetwork.BASE)

        # Hash job ID for on-chain reference
        job_hash = hashlib.sha256(escrow.job_id.encode()).digest()

        # Convert deadline to Unix timestamp
        if escrow.deadline is None:
            raise EscrowError("Escrow deadline is required for on-chain creation")
        deadline_timestamp = int(escrow.deadline.timestamp())

        # Convert amount to wei (18 decimals)
        amount_wei = int(escrow.amount * Decimal("1e18"))

        # First approve escrow contract to spend VIRTUAL
        virtual_token = self._config.get_contract_address(
            ChainNetwork.BASE, "virtual_token"
        )
        if not self._escrow_contract:
            raise EscrowError("Escrow contract address not configured")
        await client.approve_tokens(
            token_address=virtual_token or "",
            spender_address=self._escrow_contract,
            amount=float(escrow.amount + escrow.fee_amount),
        )

        # Create the escrow
        escrow_abi: list[dict[str, Any]] = ESCROW_ABI  # type: ignore[assignment]
        tx_record = await client.execute_contract(
            contract_address=self._escrow_contract,
            function_name="createEscrow",
            args=[
                escrow.provider_address,
                amount_wei,
                deadline_timestamp,
                job_hash,
            ],
            abi=escrow_abi,
        )

        return tx_record

    async def release_escrow(self, escrow_id: str) -> EscrowRecord:
        """
        Release escrow funds to the provider.

        Args:
            escrow_id: Escrow record ID

        Returns:
            Updated EscrowRecord

        SECURITY FIX (Audit 5 - C2): Uses per-escrow locking to prevent race conditions
        """
        if not self._initialized:
            await self.initialize()

        # SECURITY FIX (Audit 5 - C2): Acquire lock before check-then-act
        lock = await self._get_escrow_lock(escrow_id)
        async with lock:
            escrow = self._escrows.get(escrow_id)
            if not escrow:
                raise EscrowError(f"Escrow not found: {escrow_id}")

            if escrow.status != EscrowStatus.FUNDED:
                raise EscrowError(f"Cannot release escrow in status: {escrow.status}")

            try:
                if self._escrow_contract and escrow.escrow_id_onchain:
                    if self._chain_manager is None:
                        raise EscrowError("Chain manager not initialized")
                    client = self._chain_manager.get_client(ChainNetwork.BASE)
                    escrow_abi: list[dict[str, Any]] = ESCROW_ABI  # type: ignore[assignment]
                    tx_record = await client.execute_contract(
                        contract_address=self._escrow_contract,
                        function_name="releaseToProvider",
                        args=[escrow.escrow_id_onchain],
                        abi=escrow_abi,
                    )
                    escrow.release_tx_hash = tx_record.tx_hash

                escrow.status = EscrowStatus.RELEASED
                escrow.resolved_at = datetime.now(UTC)
                logger.info(f"Escrow {escrow_id} released to provider")

            except (ValueError, ConnectionError, TimeoutError, OSError) as e:
                escrow.metadata["release_error"] = str(e)
                logger.error(f"Failed to release escrow: {e}")
                raise EscrowError(f"Escrow release failed: {e}") from e

            return escrow

    async def refund_escrow(self, escrow_id: str, reason: str = "") -> EscrowRecord:
        """
        Refund escrow funds to the buyer.

        Args:
            escrow_id: Escrow record ID
            reason: Reason for refund

        Returns:
            Updated EscrowRecord

        SECURITY FIX (Audit 5 - C2): Uses per-escrow locking to prevent race conditions
        """
        if not self._initialized:
            await self.initialize()

        # SECURITY FIX (Audit 5 - C2): Acquire lock before check-then-act
        lock = await self._get_escrow_lock(escrow_id)
        async with lock:
            escrow = self._escrows.get(escrow_id)
            if not escrow:
                raise EscrowError(f"Escrow not found: {escrow_id}")

            if escrow.status not in [EscrowStatus.FUNDED, EscrowStatus.DISPUTED]:
                raise EscrowError(f"Cannot refund escrow in status: {escrow.status}")

            try:
                if self._escrow_contract and escrow.escrow_id_onchain:
                    if self._chain_manager is None:
                        raise EscrowError("Chain manager not initialized")
                    client = self._chain_manager.get_client(ChainNetwork.BASE)
                    escrow_abi: list[dict[str, Any]] = ESCROW_ABI  # type: ignore[assignment]
                    tx_record = await client.execute_contract(
                        contract_address=self._escrow_contract,
                        function_name="refundToBuyer",
                        args=[escrow.escrow_id_onchain],
                        abi=escrow_abi,
                    )
                    escrow.release_tx_hash = tx_record.tx_hash

                escrow.status = EscrowStatus.REFUNDED
                escrow.resolved_at = datetime.now(UTC)
                escrow.metadata["refund_reason"] = reason
                logger.info(f"Escrow {escrow_id} refunded to buyer: {reason}")

            except (ValueError, ConnectionError, TimeoutError, OSError) as e:
                escrow.metadata["refund_error"] = str(e)
                logger.error(f"Failed to refund escrow: {e}")
                raise EscrowError(f"Escrow refund failed: {e}") from e

            return escrow

    async def initiate_dispute(self, escrow_id: str, reason: str) -> EscrowRecord:
        """
        Initiate a dispute for an escrow.

        Args:
            escrow_id: Escrow record ID
            reason: Dispute reason

        Returns:
            Updated EscrowRecord

        SECURITY FIX (Audit 5 - C2): Uses per-escrow locking to prevent race conditions
        """
        # SECURITY FIX (Audit 5 - C2): Acquire lock before check-then-act
        lock = await self._get_escrow_lock(escrow_id)
        async with lock:
            escrow = self._escrows.get(escrow_id)
            if not escrow:
                raise EscrowError(f"Escrow not found: {escrow_id}")

            if escrow.status != EscrowStatus.FUNDED:
                raise EscrowError(f"Cannot dispute escrow in status: {escrow.status}")

            escrow.status = EscrowStatus.DISPUTED
            escrow.metadata["dispute_reason"] = reason
            escrow.metadata["disputed_at"] = datetime.now(UTC).isoformat()

            logger.info(f"Dispute initiated for escrow {escrow_id}: {reason}")
            return escrow

    async def resolve_dispute(
        self,
        escrow_id: str,
        buyer_share_pct: int,
        resolution_notes: str = "",
    ) -> EscrowRecord:
        """
        Resolve a disputed escrow by splitting funds.

        Args:
            escrow_id: Escrow record ID
            buyer_share_pct: Percentage to return to buyer (0-100)
            resolution_notes: Notes about resolution

        Returns:
            Updated EscrowRecord

        SECURITY FIX (Audit 5 - C2): Uses per-escrow locking to prevent race conditions
        """
        # Validate input before acquiring lock
        if not 0 <= buyer_share_pct <= 100:
            raise ValueError("buyer_share_pct must be between 0 and 100")

        # SECURITY FIX (Audit 5 - C2): Acquire lock before check-then-act
        lock = await self._get_escrow_lock(escrow_id)
        async with lock:
            escrow = self._escrows.get(escrow_id)
            if not escrow:
                raise EscrowError(f"Escrow not found: {escrow_id}")

            if escrow.status != EscrowStatus.DISPUTED:
                raise EscrowError("Cannot resolve non-disputed escrow")

            try:
                if self._escrow_contract and escrow.escrow_id_onchain:
                    if self._chain_manager is None:
                        raise EscrowError("Chain manager not initialized")
                    client = self._chain_manager.get_client(ChainNetwork.BASE)
                    # Convert percentage to basis points
                    buyer_share_bps = buyer_share_pct * 100
                    escrow_abi: list[dict[str, Any]] = ESCROW_ABI  # type: ignore[assignment]
                    tx_record = await client.execute_contract(
                        contract_address=self._escrow_contract,
                        function_name="resolveDispute",
                        args=[escrow.escrow_id_onchain, buyer_share_bps],
                        abi=escrow_abi,
                    )
                    escrow.release_tx_hash = tx_record.tx_hash

                escrow.status = EscrowStatus.RELEASED
                escrow.resolved_at = datetime.now(UTC)
                escrow.metadata["resolution"] = {
                    "buyer_share_pct": buyer_share_pct,
                    "provider_share_pct": 100 - buyer_share_pct,
                    "notes": resolution_notes,
                }
                logger.info(
                    f"Dispute resolved for escrow {escrow_id}: "
                    f"buyer={buyer_share_pct}%, provider={100-buyer_share_pct}%"
                )

            except (ValueError, ConnectionError, TimeoutError, OSError) as e:
                escrow.metadata["resolution_error"] = str(e)
                logger.error(f"Failed to resolve dispute: {e}")
                raise EscrowError(f"Dispute resolution failed: {e}") from e

            return escrow

    def get_escrow(self, escrow_id: str) -> EscrowRecord | None:
        """Get escrow by ID."""
        return self._escrows.get(escrow_id)

    def get_escrows_by_job(self, job_id: str) -> list[EscrowRecord]:
        """Get all escrows for a job."""
        return [e for e in self._escrows.values() if e.job_id == job_id]

    def get_pending_escrows(self) -> list[EscrowRecord]:
        """Get all funded escrows awaiting resolution."""
        return [
            e for e in self._escrows.values()
            if e.status == EscrowStatus.FUNDED
        ]

    async def check_expired_escrows(self) -> list[EscrowRecord]:
        """
        Check for and handle expired escrows.

        Returns auto-released escrows where deadline passed.
        """
        now = datetime.now(UTC)
        expired = []

        for escrow in self._escrows.values():
            if escrow.status == EscrowStatus.FUNDED and escrow.deadline:
                if now > escrow.deadline:
                    # Auto-release to provider after deadline
                    await self.release_escrow(escrow.id)
                    escrow.metadata["auto_released"] = True
                    expired.append(escrow)

        return expired


class EscrowError(Exception):
    """Error raised when an escrow operation fails."""
    pass


# Singleton instance
_escrow_service: EscrowService | None = None


async def get_escrow_service() -> EscrowService:
    """Get the global escrow service instance."""
    global _escrow_service
    if _escrow_service is None:
        _escrow_service = EscrowService()
        await _escrow_service.initialize()
    return _escrow_service
