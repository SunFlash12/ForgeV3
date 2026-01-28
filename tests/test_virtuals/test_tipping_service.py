"""
Tests for FROWG Tipping Service.

This module tests the tipping functionality using the $FROWG token on Solana.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.config import ChainNetwork, VirtualsEnvironment
from forge.virtuals.tipping.service import (
    FrowgTippingService,
    TipCategory,
    TipError,
    TipRecord,
    TipStatus,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_config():
    """Create a mock Virtuals config."""
    config = MagicMock()
    config.environment = VirtualsEnvironment.LOCAL
    return config


@pytest.fixture
def mock_chain_manager():
    """Create a mock chain manager."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()

    mock_client = MagicMock()
    mock_client.get_token_info = AsyncMock(
        return_value=MagicMock(symbol="FROWG", name="Rise of Frowg")
    )
    mock_client.get_wallet_balance = AsyncMock(return_value=1000.0)
    mock_client.transfer_tokens = AsyncMock(
        return_value=MagicMock(tx_hash="abc123sig")
    )
    mock_client.wait_for_transaction = AsyncMock(
        return_value=MagicMock(status="success", tx_hash="abc123sig")
    )

    manager.get_client = MagicMock(return_value=mock_client)

    return manager


@pytest.fixture
def tipping_service(mock_chain_manager):
    """Create a FrowgTippingService with mock chain manager."""
    service = FrowgTippingService(chain_manager=mock_chain_manager)
    return service


# ==================== TipStatus Tests ====================


class TestTipStatus:
    """Tests for TipStatus enum."""

    def test_all_statuses(self):
        """Test all tip statuses exist."""
        assert TipStatus.PENDING == "pending"
        assert TipStatus.CONFIRMED == "confirmed"
        assert TipStatus.FAILED == "failed"


# ==================== TipCategory Tests ====================


class TestTipCategory:
    """Tests for TipCategory enum."""

    def test_all_categories(self):
        """Test all tip categories exist."""
        assert TipCategory.AGENT_REWARD == "agent_reward"
        assert TipCategory.CAPSULE_CONTRIBUTION == "capsule_contribution"
        assert TipCategory.GOVERNANCE_VOTE == "governance_vote"
        assert TipCategory.KNOWLEDGE_QUERY == "knowledge_query"
        assert TipCategory.SERVICE_PAYMENT == "service_payment"
        assert TipCategory.COMMUNITY_GIFT == "community_gift"


# ==================== TipRecord Tests ====================


class TestTipRecord:
    """Tests for TipRecord model."""

    def test_tip_record_creation(self):
        """Test creating a tip record."""
        record = TipRecord(
            sender_address="7B8xLj" + "a" * 30,
            recipient_address="9Y3kMn" + "b" * 30,
            amount=Decimal("10.0"),
            category=TipCategory.AGENT_REWARD,
        )

        assert record.amount == Decimal("10.0")
        assert record.status == TipStatus.PENDING
        assert record.id is not None

    def test_tip_record_with_memo(self):
        """Test tip record with memo."""
        record = TipRecord(
            sender_address="7B8xLj" + "a" * 30,
            recipient_address="9Y3kMn" + "b" * 30,
            amount=Decimal("5.0"),
            category=TipCategory.CAPSULE_CONTRIBUTION,
            memo="Great capsule!",
        )

        assert record.memo == "Great capsule!"


# ==================== Initialization Tests ====================


class TestFrowgTippingServiceInit:
    """Tests for FrowgTippingService initialization."""

    def test_service_creation(self, mock_chain_manager):
        """Test creating a tipping service."""
        service = FrowgTippingService(chain_manager=mock_chain_manager)

        assert service._chain_manager == mock_chain_manager
        assert service._initialized is False
        assert service._tip_fee_percentage == Decimal("0.01")

    def test_service_custom_fee(self, mock_chain_manager):
        """Test service with custom fee percentage."""
        service = FrowgTippingService(
            chain_manager=mock_chain_manager,
            tip_fee_percentage=Decimal("0.02"),
        )

        assert service._tip_fee_percentage == Decimal("0.02")

    @pytest.mark.asyncio
    async def test_initialize_local_mode(self, tipping_service, mock_config):
        """Test initialization in LOCAL mode."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            await tipping_service.initialize()

            assert tipping_service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_production_mode(self, mock_chain_manager):
        """Test initialization in production mode."""
        mock_config = MagicMock()
        mock_config.environment = VirtualsEnvironment.PRODUCTION

        service = FrowgTippingService(chain_manager=mock_chain_manager)

        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            await service.initialize()

            assert service._initialized is True
            mock_chain_manager.get_client.assert_called_with(ChainNetwork.SOLANA)

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, tipping_service, mock_config):
        """Test that double initialization is a no-op."""
        tipping_service._initialized = True

        await tipping_service.initialize()

        # Should not attempt to initialize again
        assert tipping_service._initialized is True

    @pytest.mark.asyncio
    async def test_close(self, tipping_service, mock_chain_manager):
        """Test closing the service."""
        tipping_service._initialized = True

        await tipping_service.close()

        assert tipping_service._initialized is False
        mock_chain_manager.close.assert_called_once()


# ==================== Send Tip Tests ====================


class TestSendTip:
    """Tests for send_tip method."""

    @pytest.mark.asyncio
    async def test_send_tip_local_mode(self, tipping_service, mock_config):
        """Test sending tip in LOCAL mode."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            tip = await tipping_service.send_tip(
                sender_address="7B8xLj" + "a" * 30,
                recipient_address="9Y3kMn" + "b" * 30,
                amount=Decimal("10.0"),
                category=TipCategory.AGENT_REWARD,
                memo="Great work!",
            )

            assert tip.status == TipStatus.CONFIRMED
            assert tip.amount == Decimal("10.0")
            assert tip.tx_hash is not None
            assert tip.tx_hash.startswith("sim_tip_")

    @pytest.mark.asyncio
    async def test_send_tip_production_mode(self, mock_chain_manager):
        """Test sending tip in production mode."""
        mock_config = MagicMock()
        mock_config.environment = VirtualsEnvironment.PRODUCTION

        service = FrowgTippingService(chain_manager=mock_chain_manager)
        service._initialized = True

        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            tip = await service.send_tip(
                sender_address="7B8xLj" + "a" * 30,
                recipient_address="9Y3kMn" + "b" * 30,
                amount=Decimal("10.0"),
            )

            assert tip.status == TipStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_send_tip_below_minimum(self, tipping_service, mock_config):
        """Test sending tip below minimum amount."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            with pytest.raises(ValueError, match="at least"):
                await tipping_service.send_tip(
                    sender_address="7B8xLj" + "a" * 30,
                    recipient_address="9Y3kMn" + "b" * 30,
                    amount=Decimal("0.0001"),  # Below minimum
                )

    @pytest.mark.asyncio
    async def test_send_tip_above_maximum(self, tipping_service, mock_config):
        """Test sending tip above maximum amount."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            with pytest.raises(ValueError, match="cannot exceed"):
                await tipping_service.send_tip(
                    sender_address="7B8xLj" + "a" * 30,
                    recipient_address="9Y3kMn" + "b" * 30,
                    amount=Decimal("1000001.0"),  # Above maximum
                )

    @pytest.mark.asyncio
    async def test_send_tip_with_related_entity(self, tipping_service, mock_config):
        """Test sending tip with related entity ID."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            tip = await tipping_service.send_tip(
                sender_address="7B8xLj" + "a" * 30,
                recipient_address="9Y3kMn" + "b" * 30,
                amount=Decimal("5.0"),
                category=TipCategory.CAPSULE_CONTRIBUTION,
                related_entity_id="capsule-123",
            )

            assert tip.related_entity_id == "capsule-123"

    @pytest.mark.asyncio
    async def test_send_tip_with_metadata(self, tipping_service, mock_config):
        """Test sending tip with metadata."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            metadata = {"reason": "helpful response", "context": "query-456"}

            tip = await tipping_service.send_tip(
                sender_address="7B8xLj" + "a" * 30,
                recipient_address="9Y3kMn" + "b" * 30,
                amount=Decimal("3.0"),
                metadata=metadata,
            )

            assert tip.metadata["reason"] == "helpful response"

    @pytest.mark.asyncio
    async def test_send_tip_failure_production(self, mock_chain_manager):
        """Test handling tip failure in production."""
        mock_config = MagicMock()
        mock_config.environment = VirtualsEnvironment.PRODUCTION

        # Make transfer fail
        mock_client = mock_chain_manager.get_client.return_value
        mock_client.transfer_tokens = AsyncMock(side_effect=ConnectionError("Network error"))

        service = FrowgTippingService(chain_manager=mock_chain_manager)
        service._initialized = True

        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            with pytest.raises(TipError, match="Failed to send tip"):
                await service.send_tip(
                    sender_address="7B8xLj" + "a" * 30,
                    recipient_address="9Y3kMn" + "b" * 30,
                    amount=Decimal("10.0"),
                )

    @pytest.mark.asyncio
    async def test_send_tip_adds_to_history(self, tipping_service, mock_config):
        """Test that sent tips are added to history."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            initial_history = len(tipping_service._tip_history)

            await tipping_service.send_tip(
                sender_address="7B8xLj" + "a" * 30,
                recipient_address="9Y3kMn" + "b" * 30,
                amount=Decimal("10.0"),
            )

            assert len(tipping_service._tip_history) == initial_history + 1


# ==================== Get Balance Tests ====================


class TestGetBalance:
    """Tests for get_balance method."""

    @pytest.mark.asyncio
    async def test_get_balance(self, tipping_service, mock_chain_manager, mock_config):
        """Test getting FROWG balance."""
        tipping_service._initialized = True

        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            balance = await tipping_service.get_balance("7B8xLj" + "a" * 30)

            assert balance == Decimal("1000.0")


# ==================== Estimate Tip Fee Tests ====================


class TestEstimateTipFee:
    """Tests for estimate_tip_fee method."""

    @pytest.mark.asyncio
    async def test_estimate_fee(self, tipping_service, mock_config):
        """Test estimating tip fees."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            fee_info = await tipping_service.estimate_tip_fee(Decimal("100.0"))

            assert fee_info["tip_amount"] == Decimal("100.0")
            assert fee_info["platform_fee"] == Decimal("1.0")  # 1%
            assert fee_info["recipient_receives"] == Decimal("99.0")
            assert "network_fee_sol" in fee_info


# ==================== Get Tip History Tests ====================


class TestGetTipHistory:
    """Tests for get_tip_history method."""

    def test_get_history_empty(self, tipping_service):
        """Test getting empty history."""
        history = tipping_service.get_tip_history()

        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_with_tips(self, tipping_service, mock_config):
        """Test getting history with tips."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            # Send some tips
            await tipping_service.send_tip(
                sender_address="sender1" + "a" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("10.0"),
            )
            await tipping_service.send_tip(
                sender_address="sender2" + "c" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("20.0"),
            )

            history = tipping_service.get_tip_history()

            assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_history_filter_by_address(self, tipping_service, mock_config):
        """Test filtering history by address."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            sender = "sender1" + "a" * 30
            other = "sender2" + "c" * 30

            await tipping_service.send_tip(
                sender_address=sender,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("10.0"),
            )
            await tipping_service.send_tip(
                sender_address=other,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("20.0"),
            )

            history = tipping_service.get_tip_history(address=sender)

            assert len(history) == 1
            assert history[0].sender_address == sender

    @pytest.mark.asyncio
    async def test_get_history_filter_by_category(self, tipping_service, mock_config):
        """Test filtering history by category."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            await tipping_service.send_tip(
                sender_address="sender1" + "a" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("10.0"),
                category=TipCategory.AGENT_REWARD,
            )
            await tipping_service.send_tip(
                sender_address="sender2" + "c" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("20.0"),
                category=TipCategory.CAPSULE_CONTRIBUTION,
            )

            history = tipping_service.get_tip_history(category=TipCategory.AGENT_REWARD)

            assert len(history) == 1
            assert history[0].category == TipCategory.AGENT_REWARD

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, tipping_service, mock_config):
        """Test history with limit."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            for i in range(5):
                await tipping_service.send_tip(
                    sender_address=f"sender{i}" + "a" * 30,
                    recipient_address="recipient" + "b" * 30,
                    amount=Decimal("10.0"),
                )

            history = tipping_service.get_tip_history(limit=3)

            assert len(history) == 3


# ==================== Get Tip Statistics Tests ====================


class TestGetTipStatistics:
    """Tests for get_tip_statistics method."""

    @pytest.mark.asyncio
    async def test_get_statistics_empty(self, tipping_service, mock_config):
        """Test getting statistics with no tips."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            stats = await tipping_service.get_tip_statistics()

            assert stats["total_tips"] == 0
            assert stats["total_sent"] == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_statistics_with_tips(self, tipping_service, mock_config):
        """Test getting statistics with tips."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            await tipping_service.send_tip(
                sender_address="sender" + "a" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("10.0"),
                category=TipCategory.AGENT_REWARD,
            )
            await tipping_service.send_tip(
                sender_address="sender" + "a" * 30,
                recipient_address="recipient" + "b" * 30,
                amount=Decimal("20.0"),
                category=TipCategory.CAPSULE_CONTRIBUTION,
            )

            stats = await tipping_service.get_tip_statistics()

            assert stats["total_tips"] == 2
            assert stats["confirmed_tips"] == 2
            assert "by_category" in stats

    @pytest.mark.asyncio
    async def test_get_statistics_by_address(self, tipping_service, mock_config):
        """Test getting statistics filtered by address."""
        with patch(
            "forge.virtuals.tipping.service.get_virtuals_config",
            return_value=mock_config,
        ):
            sender = "sender" + "a" * 30

            await tipping_service.send_tip(
                sender_address=sender,
                recipient_address="recipient1" + "b" * 30,
                amount=Decimal("10.0"),
            )
            await tipping_service.send_tip(
                sender_address="other" + "c" * 30,
                recipient_address="recipient2" + "d" * 30,
                amount=Decimal("50.0"),
            )

            stats = await tipping_service.get_tip_statistics(address=sender)

            # Should only include tips involving the specified address
            assert stats["total_sent"] == Decimal("10.0")


# ==================== TipError Tests ====================


class TestTipError:
    """Tests for TipError exception."""

    def test_tip_error_creation(self):
        """Test creating a TipError."""
        error = TipError("Test error message")

        assert str(error) == "Test error message"

    def test_tip_error_inheritance(self):
        """Test TipError inherits from Exception."""
        error = TipError("Test")

        assert isinstance(error, Exception)
