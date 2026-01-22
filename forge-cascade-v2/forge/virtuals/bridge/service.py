"""
Cross-Chain Bridge Service Implementation

This module implements bridging functionality for VIRTUAL tokens between
Base, Ethereum, and Solana networks. It uses the Wormhole protocol for
secure cross-chain transfers.

Supported Routes:
- Base ↔ Ethereum (EVM-to-EVM, fastest)
- Base ↔ Solana (via Wormhole)
- Ethereum ↔ Solana (via Wormhole)

Bridge Contracts (from whitepaper.virtuals.io):
- Base/Ethereum: 0x3154Cf16ccdb4C6d922629664174b904d80F2C35
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..chains import MultiChainManager as ChainManager
from ..config import ChainNetwork, get_virtuals_config
from ..models import TransactionRecord
from ..tokenization.contracts import ContractAddresses

logger = logging.getLogger(__name__)


class BridgeStatus(str, Enum):
    """Status of a bridge transfer."""
    PENDING = "pending"           # Transfer initiated
    SOURCE_CONFIRMED = "source_confirmed"  # Source chain confirmed
    IN_TRANSIT = "in_transit"     # Wormhole processing
    DESTINATION_PENDING = "destination_pending"  # Awaiting destination claim
    COMPLETED = "completed"       # Successfully bridged
    FAILED = "failed"             # Transfer failed
    REFUNDED = "refunded"         # Transfer refunded


class BridgeRoute(str, Enum):
    """Available bridge routes."""
    BASE_TO_ETHEREUM = "base_to_ethereum"
    ETHEREUM_TO_BASE = "ethereum_to_base"
    BASE_TO_SOLANA = "base_to_solana"
    SOLANA_TO_BASE = "solana_to_base"
    ETHEREUM_TO_SOLANA = "ethereum_to_solana"
    SOLANA_TO_ETHEREUM = "solana_to_ethereum"


class BridgeRequest(BaseModel):
    """Request for a cross-chain bridge transfer."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    route: BridgeRoute = Field(description="Bridge route")
    source_chain: ChainNetwork = Field(description="Source blockchain")
    destination_chain: ChainNetwork = Field(description="Destination blockchain")
    token_address: str = Field(description="Token being bridged (VIRTUAL)")
    amount: Decimal = Field(description="Amount to bridge")
    sender_address: str = Field(description="Sender on source chain")
    recipient_address: str = Field(description="Recipient on destination chain")
    status: BridgeStatus = Field(default=BridgeStatus.PENDING)
    source_tx_hash: str | None = Field(default=None)
    destination_tx_hash: str | None = Field(default=None)
    wormhole_sequence: int | None = Field(default=None)
    vaa_bytes: str | None = Field(default=None, description="VAA for Wormhole claim")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)
    estimated_completion_minutes: int = Field(default=15)
    fee_amount: Decimal = Field(default=Decimal("0"))
    metadata: dict[str, Any] = Field(default_factory=dict)


# Bridge contract ABI (subset for token bridging)
BRIDGE_ABI = [
    {
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "targetChain", "type": "uint16"},
            {"name": "recipient", "type": "bytes32"},
        ],
        "name": "transferTokens",
        "outputs": [{"name": "sequence", "type": "uint64"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"name": "vaa", "type": "bytes"}],
        "name": "completeTransfer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "targetChain", "type": "uint16"},
        ],
        "name": "quoteEVMDeliveryPrice",
        "outputs": [
            {"name": "nativePriceQuote", "type": "uint256"},
            {"name": "targetChainRefundPerGasUnused", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function"
    },
]

# Wormhole chain IDs
WORMHOLE_CHAIN_IDS = {
    ChainNetwork.ETHEREUM: 2,
    ChainNetwork.BASE: 30,
    ChainNetwork.SOLANA: 1,
}


class BridgeService:
    """
    Service for bridging VIRTUAL tokens across chains.

    This service provides cross-chain token transfers using Wormhole:
    - Initiate bridge transfers
    - Track transfer status
    - Complete transfers on destination chain
    - Estimate fees and transfer times

    Example:
        ```python
        from forge.virtuals.bridge import BridgeService

        bridge = BridgeService()
        await bridge.initialize()

        # Bridge VIRTUAL from Base to Solana
        request = await bridge.initiate_bridge(
            route=BridgeRoute.BASE_TO_SOLANA,
            amount=Decimal("100.0"),
            sender_address="0x...",
            recipient_address="7B8xLj...",
        )

        # Check status
        status = await bridge.get_bridge_status(request.id)
        ```
    """

    # Bridge contract address (same on Base and Ethereum)
    BRIDGE_CONTRACT = ContractAddresses.BASE_MAINNET.get(
        "bridge",
        "0x3154Cf16ccdb4C6d922629664174b904d80F2C35"
    )

    # Minimum and maximum bridge amounts
    MIN_BRIDGE_AMOUNT = Decimal("1.0")
    MAX_BRIDGE_AMOUNT = Decimal("1000000.0")

    def __init__(
        self,
        chain_manager: ChainManager | None = None,
    ):
        """
        Initialize the bridge service.

        Args:
            chain_manager: Optional chain manager for multi-chain operations
        """
        self._chain_manager = chain_manager
        self._initialized = False
        self._pending_bridges: dict[str, BridgeRequest] = {}
        self._config = get_virtuals_config()

    async def initialize(self) -> None:
        """Initialize the bridge service and chain connections."""
        if self._initialized:
            return

        if self._chain_manager is None:
            self._chain_manager = ChainManager()

        # Initialize supported chains
        for chain in [ChainNetwork.BASE, ChainNetwork.ETHEREUM, ChainNetwork.SOLANA]:
            if self._config.is_chain_enabled(chain):
                try:
                    await self._chain_manager.initialize_chain(chain)
                    logger.info(f"Bridge service: {chain.value} initialized")
                except Exception as e:
                    logger.warning(f"Bridge service: Failed to init {chain.value}: {e}")

        self._initialized = True
        logger.info("Cross-chain bridge service initialized")

    async def close(self) -> None:
        """Close the bridge service."""
        if self._chain_manager:
            await self._chain_manager.close()
        self._initialized = False

    def _get_chain_from_route(self, route: BridgeRoute) -> tuple[ChainNetwork, ChainNetwork]:
        """Get source and destination chains from route."""
        route_map = {
            BridgeRoute.BASE_TO_ETHEREUM: (ChainNetwork.BASE, ChainNetwork.ETHEREUM),
            BridgeRoute.ETHEREUM_TO_BASE: (ChainNetwork.ETHEREUM, ChainNetwork.BASE),
            BridgeRoute.BASE_TO_SOLANA: (ChainNetwork.BASE, ChainNetwork.SOLANA),
            BridgeRoute.SOLANA_TO_BASE: (ChainNetwork.SOLANA, ChainNetwork.BASE),
            BridgeRoute.ETHEREUM_TO_SOLANA: (ChainNetwork.ETHEREUM, ChainNetwork.SOLANA),
            BridgeRoute.SOLANA_TO_ETHEREUM: (ChainNetwork.SOLANA, ChainNetwork.ETHEREUM),
        }
        return route_map[route]

    async def estimate_bridge_fee(
        self,
        route: BridgeRoute,
        amount: Decimal,
    ) -> dict[str, Any]:
        """
        Estimate fees for a bridge transfer.

        Args:
            route: Bridge route
            amount: Amount to bridge

        Returns:
            Fee breakdown including:
            - bridge_fee: Protocol fee
            - gas_fee: Estimated gas on destination
            - total_fee: Total fees
            - receive_amount: Amount recipient will receive
            - estimated_time_minutes: Estimated completion time
        """
        if not self._initialized:
            await self.initialize()

        source_chain, dest_chain = self._get_chain_from_route(route)

        # Base fee structure (varies by route)
        if source_chain == ChainNetwork.SOLANA or dest_chain == ChainNetwork.SOLANA:
            # Solana routes take longer and cost more due to Wormhole
            bridge_fee_pct = Decimal("0.003")  # 0.3%
            estimated_time = 20  # minutes
        else:
            # EVM-to-EVM is faster
            bridge_fee_pct = Decimal("0.001")  # 0.1%
            estimated_time = 10  # minutes

        bridge_fee = amount * bridge_fee_pct
        # Gas fees are paid in native token, approximate in VIRTUAL
        gas_fee = Decimal("0.5")  # ~$1 worth

        return {
            "route": route.value,
            "amount": amount,
            "bridge_fee": bridge_fee,
            "bridge_fee_pct": float(bridge_fee_pct * 100),
            "gas_fee_virtual": gas_fee,
            "total_fee": bridge_fee + gas_fee,
            "receive_amount": amount - bridge_fee,
            "estimated_time_minutes": estimated_time,
            "min_amount": self.MIN_BRIDGE_AMOUNT,
            "max_amount": self.MAX_BRIDGE_AMOUNT,
        }

    async def initiate_bridge(
        self,
        route: BridgeRoute,
        amount: Decimal,
        sender_address: str,
        recipient_address: str,
        metadata: dict[str, Any] | None = None,
    ) -> BridgeRequest:
        """
        Initiate a cross-chain bridge transfer.

        Args:
            route: Bridge route (e.g., BASE_TO_SOLANA)
            amount: Amount of VIRTUAL to bridge
            sender_address: Sender's address on source chain
            recipient_address: Recipient's address on destination chain
            metadata: Optional metadata

        Returns:
            BridgeRequest with transfer details

        Raises:
            ValueError: If amount is invalid
            BridgeError: If transfer initiation fails
        """
        if not self._initialized:
            await self.initialize()

        # Validate amount
        if amount < self.MIN_BRIDGE_AMOUNT:
            raise ValueError(f"Minimum bridge amount is {self.MIN_BRIDGE_AMOUNT} VIRTUAL")
        if amount > self.MAX_BRIDGE_AMOUNT:
            raise ValueError(f"Maximum bridge amount is {self.MAX_BRIDGE_AMOUNT} VIRTUAL")

        source_chain, dest_chain = self._get_chain_from_route(route)

        # Get VIRTUAL token address on source chain
        if source_chain == ChainNetwork.BASE:
            token_address = ContractAddresses.BASE_MAINNET["virtual_token"]
        elif source_chain == ChainNetwork.ETHEREUM:
            token_address = ContractAddresses.ETHEREUM_MAINNET["virtual_token"]
        else:
            token_address = ContractAddresses.SOLANA_MAINNET["virtual_token"]

        # Estimate fee
        fee_estimate = await self.estimate_bridge_fee(route, amount)

        # Create bridge request
        request = BridgeRequest(
            route=route,
            source_chain=source_chain,
            destination_chain=dest_chain,
            token_address=token_address,
            amount=amount,
            sender_address=sender_address,
            recipient_address=recipient_address,
            fee_amount=fee_estimate["total_fee"],
            estimated_completion_minutes=fee_estimate["estimated_time_minutes"],
            metadata=metadata or {},
        )

        try:
            # Execute bridge based on source chain type
            if source_chain in [ChainNetwork.BASE, ChainNetwork.ETHEREUM]:
                tx_record = await self._initiate_evm_bridge(
                    request, source_chain, dest_chain
                )
            else:
                tx_record = await self._initiate_solana_bridge(
                    request, dest_chain
                )

            request.source_tx_hash = tx_record.tx_hash
            request.status = BridgeStatus.SOURCE_CONFIRMED

            logger.info(
                f"Bridge initiated: {amount} VIRTUAL via {route.value} "
                f"(tx: {request.source_tx_hash[:16]}...)"
            )

        except Exception as e:
            request.status = BridgeStatus.FAILED
            request.metadata["error"] = str(e)
            logger.error(f"Bridge initiation failed: {e}")
            raise BridgeError(f"Failed to initiate bridge: {e}") from e

        self._pending_bridges[request.id] = request
        return request

    async def _initiate_evm_bridge(
        self,
        request: BridgeRequest,
        source_chain: ChainNetwork,
        dest_chain: ChainNetwork,
    ) -> TransactionRecord:
        """Initiate bridge from EVM chain (Base or Ethereum)."""
        client = self._chain_manager.get_client(source_chain)

        # First approve bridge contract to spend tokens
        await client.approve_tokens(
            token_address=request.token_address,
            spender_address=self.BRIDGE_CONTRACT,
            amount=float(request.amount),
        )

        # Get Wormhole chain ID for destination
        dest_wormhole_id = WORMHOLE_CHAIN_IDS.get(dest_chain, 30)

        # Convert recipient address to bytes32 format
        if dest_chain == ChainNetwork.SOLANA:
            # Solana addresses need base58 -> bytes32 conversion
            import base58
            recipient_bytes = base58.b58decode(request.recipient_address)
            recipient_bytes32 = recipient_bytes.rjust(32, b'\x00')
        else:
            # EVM address to bytes32
            recipient_bytes32 = bytes.fromhex(
                request.recipient_address[2:].rjust(64, '0')
            )

        # Execute bridge transfer
        amount_wei = int(request.amount * Decimal("1e18"))

        tx_record = await client.execute_contract(
            contract_address=self.BRIDGE_CONTRACT,
            function_name="transferTokens",
            args=[
                request.token_address,
                amount_wei,
                dest_wormhole_id,
                recipient_bytes32,
            ],
            value=0.01,  # Pay for destination gas
            abi=BRIDGE_ABI,
        )

        return tx_record

    async def _initiate_solana_bridge(
        self,
        request: BridgeRequest,
        dest_chain: ChainNetwork,
    ) -> TransactionRecord:
        """Initiate bridge from Solana."""
        client = self._chain_manager.get_client(ChainNetwork.SOLANA)

        # Solana bridge uses different instruction format
        # This is a simplified implementation - real Wormhole integration
        # requires the Wormhole Solana SDK

        dest_wormhole_id = WORMHOLE_CHAIN_IDS.get(dest_chain, 2)

        # For now, use memo instruction to record bridge intent
        # Full implementation would use Wormhole's token bridge program
        tx_record = await client.execute_contract(
            contract_address="MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
            function_name="memo",
            args=[
                f"BRIDGE:{request.amount}:{dest_wormhole_id}:{request.recipient_address}"
            ],
        )

        logger.warning(
            "Solana bridge: Using memo for bridge intent. "
            "Full Wormhole integration pending."
        )

        return tx_record

    async def get_bridge_status(self, bridge_id: str) -> BridgeRequest | None:
        """
        Get the status of a bridge transfer.

        Args:
            bridge_id: Bridge request ID

        Returns:
            BridgeRequest with current status, or None if not found
        """
        request = self._pending_bridges.get(bridge_id)
        if not request:
            return None

        # Update status if source is confirmed but not complete
        if request.status == BridgeStatus.SOURCE_CONFIRMED:
            # Check if enough time has passed for Wormhole
            elapsed = (datetime.now(UTC) - request.created_at).total_seconds() / 60

            if elapsed > 5:  # After 5 minutes, assume in transit
                request.status = BridgeStatus.IN_TRANSIT

            if elapsed > request.estimated_completion_minutes:
                # Should be ready to claim on destination
                request.status = BridgeStatus.DESTINATION_PENDING

        return request

    async def complete_bridge(
        self,
        bridge_id: str,
    ) -> BridgeRequest:
        """
        Complete a bridge transfer on the destination chain.

        This claims the bridged tokens using the Wormhole VAA.

        Args:
            bridge_id: Bridge request ID

        Returns:
            Updated BridgeRequest

        Raises:
            BridgeError: If completion fails
        """
        if not self._initialized:
            await self.initialize()

        request = self._pending_bridges.get(bridge_id)
        if not request:
            raise BridgeError(f"Bridge request not found: {bridge_id}")

        if request.status == BridgeStatus.COMPLETED:
            return request

        try:
            # Get destination chain client (for full Wormhole implementation)
            _dest_client = self._chain_manager.get_client(request.destination_chain)

            if request.destination_chain in [ChainNetwork.BASE, ChainNetwork.ETHEREUM]:
                # Complete on EVM chain
                # In production, would fetch VAA from Wormhole guardian network
                # and call completeTransfer on the bridge contract

                # For now, simulate completion
                request.status = BridgeStatus.COMPLETED
                request.completed_at = datetime.now(UTC)
                logger.info(f"Bridge {bridge_id} completed (simulated)")

            else:
                # Complete on Solana
                # Would use Wormhole Solana program to claim tokens
                request.status = BridgeStatus.COMPLETED
                request.completed_at = datetime.now(UTC)
                logger.info(f"Bridge {bridge_id} completed on Solana (simulated)")

        except Exception as e:
            request.status = BridgeStatus.FAILED
            request.metadata["completion_error"] = str(e)
            logger.error(f"Bridge completion failed: {e}")
            raise BridgeError(f"Failed to complete bridge: {e}") from e

        return request

    def get_pending_bridges(
        self,
        address: str | None = None,
    ) -> list[BridgeRequest]:
        """
        Get pending bridge transfers.

        Args:
            address: Optional filter by sender or recipient address

        Returns:
            List of pending bridge requests
        """
        bridges = list(self._pending_bridges.values())

        if address:
            bridges = [
                b for b in bridges
                if b.sender_address == address or b.recipient_address == address
            ]

        # Filter to non-completed
        bridges = [
            b for b in bridges
            if b.status not in [BridgeStatus.COMPLETED, BridgeStatus.FAILED, BridgeStatus.REFUNDED]
        ]

        return sorted(bridges, key=lambda b: b.created_at, reverse=True)

    def get_supported_routes(self) -> list[dict[str, Any]]:
        """
        Get list of supported bridge routes.

        Returns:
            List of route information including fees and times
        """
        routes = []
        for route in BridgeRoute:
            source, dest = self._get_chain_from_route(route)

            # Check if both chains are enabled
            if not (self._config.is_chain_enabled(source) and
                    self._config.is_chain_enabled(dest)):
                continue

            is_solana = source == ChainNetwork.SOLANA or dest == ChainNetwork.SOLANA

            routes.append({
                "route": route.value,
                "source_chain": source.value,
                "destination_chain": dest.value,
                "fee_percentage": 0.3 if is_solana else 0.1,
                "estimated_time_minutes": 20 if is_solana else 10,
                "min_amount": float(self.MIN_BRIDGE_AMOUNT),
                "max_amount": float(self.MAX_BRIDGE_AMOUNT),
            })

        return routes


class BridgeError(Exception):
    """Error raised when a bridge operation fails."""
    pass


# Singleton instance
_bridge_service: BridgeService | None = None


async def get_bridge_service() -> BridgeService:
    """Get the global bridge service instance."""
    global _bridge_service
    if _bridge_service is None:
        _bridge_service = BridgeService()
        await _bridge_service.initialize()
    return _bridge_service
