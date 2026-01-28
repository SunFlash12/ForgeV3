"""
Tests for the Cross-Chain Bridge Service Implementation.

This module tests bridging functionality for VIRTUAL tokens between
Base, Ethereum, and Solana networks.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.bridge.service import (
    BRIDGE_ABI,
    WORMHOLE_CHAIN_IDS,
    BridgeError,
    BridgeRequest,
    BridgeRoute,
    BridgeService,
    BridgeStatus,
    get_bridge_service,
)
from forge.virtuals.config import ChainNetwork


# ==================== Fixtures ====================


@pytest.fixture
def mock_chain_manager():
    """Create a mock chain manager."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()

    # Mock EVM client
    mock_evm_client = MagicMock()
    mock_evm_client.approve_tokens = AsyncMock()
    mock_evm_client.execute_contract = AsyncMock(
        return_value=MagicMock(tx_hash="0x" + "a" * 64)
    )

    # Mock Solana client
    mock_solana_client = MagicMock()
    mock_solana_client.execute_contract = AsyncMock(
        return_value=MagicMock(tx_hash="sol_" + "a" * 60)
    )

    def get_client(chain):
        if chain == ChainNetwork.SOLANA:
            return mock_solana_client
        return mock_evm_client

    manager.get_client = MagicMock(side_effect=get_client)
    return manager


@pytest.fixture
def bridge_service(mock_chain_manager):
    """Create a BridgeService for testing."""
    return BridgeService(chain_manager=mock_chain_manager)


@pytest.fixture(autouse=True)
async def reset_global_service():
    """Reset global bridge service before and after each test."""
    import forge.virtuals.bridge.service as bridge_module
    original = bridge_module._bridge_service
    bridge_module._bridge_service = None
    yield
    bridge_module._bridge_service = original


# ==================== BridgeStatus Tests ====================


class TestBridgeStatus:
    """Tests for the BridgeStatus enum."""

    def test_all_statuses_exist(self):
        """Test that all expected statuses exist."""
        assert BridgeStatus.PENDING == "pending"
        assert BridgeStatus.SOURCE_CONFIRMED == "source_confirmed"
        assert BridgeStatus.IN_TRANSIT == "in_transit"
        assert BridgeStatus.DESTINATION_PENDING == "destination_pending"
        assert BridgeStatus.COMPLETED == "completed"
        assert BridgeStatus.FAILED == "failed"
        assert BridgeStatus.REFUNDED == "refunded"


# ==================== BridgeRoute Tests ====================


class TestBridgeRoute:
    """Tests for the BridgeRoute enum."""

    def test_all_routes_exist(self):
        """Test that all expected routes exist."""
        assert BridgeRoute.BASE_TO_ETHEREUM == "base_to_ethereum"
        assert BridgeRoute.ETHEREUM_TO_BASE == "ethereum_to_base"
        assert BridgeRoute.BASE_TO_SOLANA == "base_to_solana"
        assert BridgeRoute.SOLANA_TO_BASE == "solana_to_base"
        assert BridgeRoute.ETHEREUM_TO_SOLANA == "ethereum_to_solana"
        assert BridgeRoute.SOLANA_TO_ETHEREUM == "solana_to_ethereum"

    def test_route_count(self):
        """Test the number of routes."""
        assert len(BridgeRoute) == 6


# ==================== BridgeRequest Tests ====================


class TestBridgeRequest:
    """Tests for the BridgeRequest model."""

    def test_bridge_request_creation(self):
        """Test creating a BridgeRequest."""
        request = BridgeRequest(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            source_chain=ChainNetwork.BASE,
            destination_chain=ChainNetwork.ETHEREUM,
            token_address="0x" + "1" * 40,
            amount=Decimal("100.0"),
            sender_address="0x" + "2" * 40,
            recipient_address="0x" + "3" * 40,
        )

        assert request.id is not None
        assert request.route == BridgeRoute.BASE_TO_ETHEREUM
        assert request.amount == Decimal("100.0")
        assert request.status == BridgeStatus.PENDING
        assert request.created_at is not None
        assert request.estimated_completion_minutes == 15

    def test_bridge_request_defaults(self):
        """Test BridgeRequest default values."""
        request = BridgeRequest(
            route=BridgeRoute.BASE_TO_SOLANA,
            source_chain=ChainNetwork.BASE,
            destination_chain=ChainNetwork.SOLANA,
            token_address="0x123",
            amount=Decimal("50"),
            sender_address="0xsender",
            recipient_address="recipient",
        )

        assert request.source_tx_hash is None
        assert request.destination_tx_hash is None
        assert request.wormhole_sequence is None
        assert request.vaa_bytes is None
        assert request.completed_at is None
        assert request.fee_amount == Decimal("0")
        assert request.metadata == {}


# ==================== BridgeService Initialization Tests ====================


class TestBridgeServiceInit:
    """Tests for BridgeService initialization."""

    @pytest.mark.asyncio
    async def test_initialize(self, bridge_service):
        """Test service initialization."""
        await bridge_service.initialize()

        assert bridge_service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, bridge_service):
        """Test that initialization is idempotent."""
        await bridge_service.initialize()
        await bridge_service.initialize()

        assert bridge_service._initialized is True

    @pytest.mark.asyncio
    async def test_close(self, bridge_service, mock_chain_manager):
        """Test closing the service."""
        await bridge_service.initialize()
        await bridge_service.close()

        assert bridge_service._initialized is False
        mock_chain_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_chain_manager(self):
        """Test initialization creates chain manager if not provided."""
        with patch("forge.virtuals.bridge.service.ChainManager") as MockChainManager:
            mock_manager = MagicMock()
            mock_manager.initialize = AsyncMock()
            MockChainManager.return_value = mock_manager

            service = BridgeService(chain_manager=None)
            await service.initialize()

            MockChainManager.assert_called_once()
            mock_manager.initialize.assert_called_once()


# ==================== Route Mapping Tests ====================


class TestRouteMapping:
    """Tests for route to chain mapping."""

    def test_get_chain_from_route_base_to_ethereum(self, bridge_service):
        """Test BASE_TO_ETHEREUM route mapping."""
        source, dest = bridge_service._get_chain_from_route(BridgeRoute.BASE_TO_ETHEREUM)
        assert source == ChainNetwork.BASE
        assert dest == ChainNetwork.ETHEREUM

    def test_get_chain_from_route_ethereum_to_base(self, bridge_service):
        """Test ETHEREUM_TO_BASE route mapping."""
        source, dest = bridge_service._get_chain_from_route(BridgeRoute.ETHEREUM_TO_BASE)
        assert source == ChainNetwork.ETHEREUM
        assert dest == ChainNetwork.BASE

    def test_get_chain_from_route_base_to_solana(self, bridge_service):
        """Test BASE_TO_SOLANA route mapping."""
        source, dest = bridge_service._get_chain_from_route(BridgeRoute.BASE_TO_SOLANA)
        assert source == ChainNetwork.BASE
        assert dest == ChainNetwork.SOLANA

    def test_get_chain_from_route_solana_to_base(self, bridge_service):
        """Test SOLANA_TO_BASE route mapping."""
        source, dest = bridge_service._get_chain_from_route(BridgeRoute.SOLANA_TO_BASE)
        assert source == ChainNetwork.SOLANA
        assert dest == ChainNetwork.BASE


# ==================== Fee Estimation Tests ====================


class TestFeeEstimation:
    """Tests for bridge fee estimation."""

    @pytest.mark.asyncio
    async def test_estimate_fee_evm_to_evm(self, bridge_service):
        """Test fee estimation for EVM-to-EVM bridge."""
        await bridge_service.initialize()

        estimate = await bridge_service.estimate_bridge_fee(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
        )

        assert estimate["route"] == "base_to_ethereum"
        assert estimate["amount"] == Decimal("100.0")
        assert estimate["bridge_fee_pct"] == 0.1  # 0.1% for EVM-to-EVM
        assert estimate["estimated_time_minutes"] == 10
        assert estimate["receive_amount"] == Decimal("99.9")  # 100 - 0.1

    @pytest.mark.asyncio
    async def test_estimate_fee_solana_route(self, bridge_service):
        """Test fee estimation for Solana route (higher fee)."""
        await bridge_service.initialize()

        estimate = await bridge_service.estimate_bridge_fee(
            route=BridgeRoute.BASE_TO_SOLANA,
            amount=Decimal("100.0"),
        )

        assert estimate["bridge_fee_pct"] == 0.3  # 0.3% for Solana routes
        assert estimate["estimated_time_minutes"] == 20

    @pytest.mark.asyncio
    async def test_estimate_fee_includes_gas(self, bridge_service):
        """Test that fee estimation includes gas fee."""
        await bridge_service.initialize()

        estimate = await bridge_service.estimate_bridge_fee(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("1000.0"),
        )

        assert estimate["gas_fee_virtual"] == Decimal("0.5")
        assert estimate["total_fee"] == estimate["bridge_fee"] + estimate["gas_fee_virtual"]

    @pytest.mark.asyncio
    async def test_estimate_fee_auto_initializes(self):
        """Test that fee estimation auto-initializes."""
        with patch("forge.virtuals.bridge.service.ChainManager") as MockChainManager:
            mock_manager = MagicMock()
            mock_manager.initialize = AsyncMock()
            MockChainManager.return_value = mock_manager

            service = BridgeService()
            await service.estimate_bridge_fee(BridgeRoute.BASE_TO_ETHEREUM, Decimal("100"))

            mock_manager.initialize.assert_called_once()


# ==================== Bridge Initiation Tests ====================


class TestBridgeInitiation:
    """Tests for initiating bridge transfers."""

    @pytest.mark.asyncio
    async def test_initiate_bridge_success(self, bridge_service):
        """Test successful bridge initiation."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        assert request.status == BridgeStatus.SOURCE_CONFIRMED
        assert request.source_tx_hash is not None
        assert request.id in bridge_service._pending_bridges

    @pytest.mark.asyncio
    async def test_initiate_bridge_amount_too_low(self, bridge_service):
        """Test that amounts below minimum are rejected."""
        await bridge_service.initialize()

        with pytest.raises(ValueError, match="Minimum bridge amount"):
            await bridge_service.initiate_bridge(
                route=BridgeRoute.BASE_TO_ETHEREUM,
                amount=Decimal("0.5"),  # Below minimum
                sender_address="0x1",
                recipient_address="0x2",
            )

    @pytest.mark.asyncio
    async def test_initiate_bridge_amount_too_high(self, bridge_service):
        """Test that amounts above maximum are rejected."""
        await bridge_service.initialize()

        with pytest.raises(ValueError, match="Maximum bridge amount"):
            await bridge_service.initiate_bridge(
                route=BridgeRoute.BASE_TO_ETHEREUM,
                amount=Decimal("2000000.0"),  # Above maximum
                sender_address="0x1",
                recipient_address="0x2",
            )

    @pytest.mark.asyncio
    async def test_initiate_bridge_approves_tokens(self, bridge_service, mock_chain_manager):
        """Test that bridge initiation approves token spending."""
        await bridge_service.initialize()

        await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        mock_client = mock_chain_manager.get_client(ChainNetwork.BASE)
        mock_client.approve_tokens.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_bridge_with_metadata(self, bridge_service):
        """Test bridge initiation with metadata."""
        await bridge_service.initialize()

        metadata = {"purpose": "test", "user_id": "123"}
        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
            metadata=metadata,
        )

        assert request.metadata["purpose"] == "test"
        assert request.metadata["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_initiate_bridge_failure(self, bridge_service, mock_chain_manager):
        """Test bridge initiation failure handling."""
        await bridge_service.initialize()

        mock_client = mock_chain_manager.get_client(ChainNetwork.BASE)
        mock_client.approve_tokens = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with pytest.raises(BridgeError, match="Failed to initiate bridge"):
            await bridge_service.initiate_bridge(
                route=BridgeRoute.BASE_TO_ETHEREUM,
                amount=Decimal("100.0"),
                sender_address="0x" + "1" * 40,
                recipient_address="0x" + "2" * 40,
            )


# ==================== Bridge Status Tests ====================


class TestBridgeStatus:
    """Tests for checking bridge status."""

    @pytest.mark.asyncio
    async def test_get_bridge_status_not_found(self, bridge_service):
        """Test getting status for non-existent bridge."""
        result = await bridge_service.get_bridge_status("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_bridge_status_found(self, bridge_service):
        """Test getting status for existing bridge."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        status = await bridge_service.get_bridge_status(request.id)

        assert status is not None
        assert status.id == request.id

    @pytest.mark.asyncio
    async def test_get_bridge_status_updates_in_transit(self, bridge_service):
        """Test that status updates to IN_TRANSIT after time passes."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        # Simulate time passing
        request.created_at = datetime.now(UTC) - timedelta(minutes=6)

        status = await bridge_service.get_bridge_status(request.id)

        assert status.status == BridgeStatus.IN_TRANSIT

    @pytest.mark.asyncio
    async def test_get_bridge_status_updates_destination_pending(self, bridge_service):
        """Test that status updates to DESTINATION_PENDING after completion time."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        # Simulate enough time passing
        request.created_at = datetime.now(UTC) - timedelta(minutes=20)

        status = await bridge_service.get_bridge_status(request.id)

        assert status.status == BridgeStatus.DESTINATION_PENDING


# ==================== Bridge Completion Tests ====================


class TestBridgeCompletion:
    """Tests for completing bridge transfers."""

    @pytest.mark.asyncio
    async def test_complete_bridge_not_found(self, bridge_service):
        """Test completing a non-existent bridge."""
        await bridge_service.initialize()

        with pytest.raises(BridgeError, match="not found"):
            await bridge_service.complete_bridge("nonexistent-id")

    @pytest.mark.asyncio
    async def test_complete_bridge_success(self, bridge_service):
        """Test successful bridge completion."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        completed = await bridge_service.complete_bridge(request.id)

        assert completed.status == BridgeStatus.COMPLETED
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_bridge_already_completed(self, bridge_service):
        """Test completing an already completed bridge."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0x" + "1" * 40,
            recipient_address="0x" + "2" * 40,
        )

        await bridge_service.complete_bridge(request.id)
        result = await bridge_service.complete_bridge(request.id)

        assert result.status == BridgeStatus.COMPLETED


# ==================== Pending Bridges Tests ====================


class TestPendingBridges:
    """Tests for getting pending bridges."""

    @pytest.mark.asyncio
    async def test_get_pending_bridges_empty(self, bridge_service):
        """Test getting pending bridges when empty."""
        bridges = bridge_service.get_pending_bridges()
        assert bridges == []

    @pytest.mark.asyncio
    async def test_get_pending_bridges(self, bridge_service):
        """Test getting pending bridges."""
        await bridge_service.initialize()

        await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0xsender1",
            recipient_address="0xrecipient1",
        )
        await bridge_service.initiate_bridge(
            route=BridgeRoute.ETHEREUM_TO_BASE,
            amount=Decimal("200.0"),
            sender_address="0xsender2",
            recipient_address="0xrecipient2",
        )

        bridges = bridge_service.get_pending_bridges()

        assert len(bridges) == 2

    @pytest.mark.asyncio
    async def test_get_pending_bridges_filter_by_address(self, bridge_service):
        """Test filtering pending bridges by address."""
        await bridge_service.initialize()

        await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0xsender1",
            recipient_address="0xrecipient1",
        )
        await bridge_service.initiate_bridge(
            route=BridgeRoute.ETHEREUM_TO_BASE,
            amount=Decimal("200.0"),
            sender_address="0xsender2",
            recipient_address="0xrecipient2",
        )

        bridges = bridge_service.get_pending_bridges(address="0xsender1")

        assert len(bridges) == 1
        assert bridges[0].sender_address == "0xsender1"

    @pytest.mark.asyncio
    async def test_get_pending_bridges_excludes_completed(self, bridge_service):
        """Test that completed bridges are excluded."""
        await bridge_service.initialize()

        request = await bridge_service.initiate_bridge(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
            sender_address="0xsender",
            recipient_address="0xrecipient",
        )
        await bridge_service.complete_bridge(request.id)

        bridges = bridge_service.get_pending_bridges()

        assert len(bridges) == 0


# ==================== Supported Routes Tests ====================


class TestSupportedRoutes:
    """Tests for getting supported routes."""

    def test_get_supported_routes(self, bridge_service):
        """Test getting supported routes."""
        with patch.object(bridge_service._config, "is_chain_enabled", return_value=True):
            routes = bridge_service.get_supported_routes()

            assert len(routes) > 0
            for route in routes:
                assert "route" in route
                assert "source_chain" in route
                assert "destination_chain" in route
                assert "fee_percentage" in route
                assert "estimated_time_minutes" in route

    def test_get_supported_routes_disabled_chain(self, bridge_service):
        """Test that disabled chains are excluded from routes."""
        def mock_is_enabled(chain):
            return chain != ChainNetwork.SOLANA

        with patch.object(bridge_service._config, "is_chain_enabled", side_effect=mock_is_enabled):
            routes = bridge_service.get_supported_routes()

            # Should not include Solana routes
            for route in routes:
                assert "solana" not in route["source_chain"]
                assert "solana" not in route["destination_chain"]


# ==================== Global Service Tests ====================


class TestGlobalService:
    """Tests for the global bridge service."""

    @pytest.mark.asyncio
    async def test_get_bridge_service_creates_singleton(self):
        """Test that get_bridge_service returns a singleton."""
        with patch("forge.virtuals.bridge.service.ChainManager") as MockChainManager:
            mock_manager = MagicMock()
            mock_manager.initialize = AsyncMock()
            mock_manager.get_client = MagicMock(return_value=MagicMock())
            MockChainManager.return_value = mock_manager

            service1 = await get_bridge_service()
            service2 = await get_bridge_service()

            assert service1 is service2


# ==================== Wormhole Chain IDs Tests ====================


class TestWormholeChainIds:
    """Tests for Wormhole chain ID mapping."""

    def test_wormhole_chain_ids(self):
        """Test Wormhole chain ID values."""
        assert WORMHOLE_CHAIN_IDS[ChainNetwork.ETHEREUM] == 2
        assert WORMHOLE_CHAIN_IDS[ChainNetwork.BASE] == 30
        assert WORMHOLE_CHAIN_IDS[ChainNetwork.SOLANA] == 1


# ==================== Bridge ABI Tests ====================


class TestBridgeABI:
    """Tests for the Bridge ABI."""

    def test_abi_contains_transfer_tokens(self):
        """Test that ABI contains transferTokens function."""
        transfer_fn = next(
            (f for f in BRIDGE_ABI if f.get("name") == "transferTokens"), None
        )
        assert transfer_fn is not None
        assert transfer_fn["type"] == "function"

    def test_abi_contains_complete_transfer(self):
        """Test that ABI contains completeTransfer function."""
        complete_fn = next(
            (f for f in BRIDGE_ABI if f.get("name") == "completeTransfer"), None
        )
        assert complete_fn is not None

    def test_abi_contains_quote_function(self):
        """Test that ABI contains quoteEVMDeliveryPrice function."""
        quote_fn = next(
            (f for f in BRIDGE_ABI if f.get("name") == "quoteEVMDeliveryPrice"), None
        )
        assert quote_fn is not None


# ==================== Error Handling Tests ====================


class TestBridgeErrorHandling:
    """Tests for error handling."""

    def test_bridge_error_is_exception(self):
        """Test that BridgeError is an Exception."""
        error = BridgeError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    @pytest.mark.asyncio
    async def test_chain_manager_not_initialized_error(self):
        """Test error when chain manager not initialized."""
        service = BridgeService(chain_manager=None)

        with pytest.raises(BridgeError, match="not initialized"):
            service._get_chain_manager()
