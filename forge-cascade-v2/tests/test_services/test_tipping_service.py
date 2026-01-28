"""
Tests for FROWG Tipping Service

Tests the social tipping layer using $FROWG tokens on Solana.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.models.tipping import (
    FROWG_DECIMALS,
    Tip,
    TipLeaderboard,
    TipSummary,
    TipTargetType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock Neo4j database session."""
    session = AsyncMock()
    session.run = AsyncMock()
    return session


@pytest.fixture
def mock_neo4j_client(mock_db_session):
    """Create a mock Neo4j client."""
    client = MagicMock()

    # Create async context manager for session
    async def session_context():
        return mock_db_session

    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_db_session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    client.session = MagicMock(return_value=session_cm)

    return client


@pytest.fixture
def tipping_service(mock_neo4j_client):
    """Create a tipping service for testing."""
    from forge.services.tipping_service import TippingService

    return TippingService(db_client=mock_neo4j_client)


@pytest.fixture
def sample_tip():
    """Create a sample tip for testing."""
    return Tip(
        id="tip-123",
        sender_wallet="SenderWallet123456789012345678901234567890",
        sender_user_id="user-456",
        target_type=TipTargetType.CAPSULE,
        target_id="capsule-789",
        recipient_wallet="RecipientWallet12345678901234567890123",
        amount_frowg=100.0,
        amount_lamports=100_000_000_000,  # 100 * 10^9
        message="Great insight!",
        tx_signature=None,
        confirmed=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_tip_record():
    """Create a sample tip record as returned from Neo4j."""
    return {
        "id": "tip-123",
        "sender_wallet": "SenderWallet123456789012345678901234567890",
        "sender_user_id": "user-456",
        "target_type": "capsule",
        "target_id": "capsule-789",
        "recipient_wallet": "RecipientWallet12345678901234567890123",
        "amount_frowg": 100.0,
        "amount_lamports": 100_000_000_000,
        "message": "Great insight!",
        "tx_signature": None,
        "confirmed": False,
        "created_at": datetime.now(UTC),
        "confirmed_at": None,
    }


# =============================================================================
# Test Tip Model
# =============================================================================


class TestTipModel:
    """Tests for the Tip model."""

    def test_tip_creation(self):
        """Test basic tip creation."""
        tip = Tip(
            sender_wallet="TestWallet12345678901234567890123456",
            target_type=TipTargetType.AGENT,
            target_id="agent-123",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=50.0,
        )

        assert tip.id is not None
        assert tip.amount_frowg == 50.0
        assert tip.confirmed is False
        assert tip.created_at is not None

    def test_to_lamports(self):
        """Test conversion to lamports."""
        tip = Tip(
            sender_wallet="TestWallet12345678901234567890123456",
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-123",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=1.0,
        )

        expected_lamports = int(1.0 * (10 ** FROWG_DECIMALS))
        assert tip.to_lamports() == expected_lamports

    def test_to_lamports_fractional(self):
        """Test conversion to lamports with fractional amounts."""
        tip = Tip(
            sender_wallet="TestWallet12345678901234567890123456",
            target_type=TipTargetType.USER,
            target_id="user-123",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=0.5,
        )

        expected_lamports = int(0.5 * (10 ** FROWG_DECIMALS))
        assert tip.to_lamports() == expected_lamports

    def test_tip_target_types(self):
        """Test all tip target types."""
        for target_type in TipTargetType:
            tip = Tip(
                sender_wallet="TestWallet12345678901234567890123456",
                target_type=target_type,
                target_id="test-123",
                recipient_wallet="RecipientWallet12345678901234567890123",
                amount_frowg=10.0,
            )
            assert tip.target_type == target_type


# =============================================================================
# Test TippingService Initialization
# =============================================================================


class TestTippingServiceInit:
    """Tests for TippingService initialization."""

    def test_init(self, mock_neo4j_client):
        """Test service initialization."""
        from forge.services.tipping_service import TippingService

        service = TippingService(db_client=mock_neo4j_client)

        assert service._db is mock_neo4j_client
        assert service._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_creates_indexes(self, tipping_service, mock_db_session):
        """Test that initialize creates necessary indexes."""
        mock_result = AsyncMock()
        mock_db_session.run.return_value = mock_result

        await tipping_service.initialize()

        assert tipping_service._initialized is True
        # Should have created 3 indexes
        assert mock_db_session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, tipping_service, mock_db_session):
        """Test that multiple initializations don't create duplicate indexes."""
        mock_result = AsyncMock()
        mock_db_session.run.return_value = mock_result

        await tipping_service.initialize()
        await tipping_service.initialize()

        # Should still only create 3 indexes (once)
        assert mock_db_session.run.call_count == 3


# =============================================================================
# Test create_tip
# =============================================================================


class TestCreateTip:
    """Tests for create_tip method."""

    @pytest.mark.asyncio
    async def test_create_tip_basic(self, tipping_service, mock_db_session):
        """Test basic tip creation."""
        mock_db_session.run.return_value = AsyncMock()

        tip = await tipping_service.create_tip(
            sender_wallet="SenderWallet123456789012345678901234567890",
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-123",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=100.0,
        )

        assert tip.sender_wallet == "SenderWallet123456789012345678901234567890"
        assert tip.target_type == TipTargetType.CAPSULE
        assert tip.target_id == "capsule-123"
        assert tip.amount_frowg == 100.0
        assert tip.confirmed is False
        mock_db_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tip_with_message(self, tipping_service, mock_db_session):
        """Test tip creation with optional message."""
        mock_db_session.run.return_value = AsyncMock()

        tip = await tipping_service.create_tip(
            sender_wallet="SenderWallet123456789012345678901234567890",
            target_type=TipTargetType.AGENT,
            target_id="agent-456",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=50.0,
            message="Amazing agent!",
        )

        assert tip.message == "Amazing agent!"

    @pytest.mark.asyncio
    async def test_create_tip_with_tx_signature(self, tipping_service, mock_db_session):
        """Test tip creation with transaction signature."""
        mock_db_session.run.return_value = AsyncMock()

        tip = await tipping_service.create_tip(
            sender_wallet="SenderWallet123456789012345678901234567890",
            target_type=TipTargetType.USER,
            target_id="user-789",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=25.0,
            tx_signature="5UvKX8qG9F...",
        )

        assert tip.tx_signature == "5UvKX8qG9F..."

    @pytest.mark.asyncio
    async def test_create_tip_sets_lamports(self, tipping_service, mock_db_session):
        """Test that lamports is calculated from frowg amount."""
        mock_db_session.run.return_value = AsyncMock()

        tip = await tipping_service.create_tip(
            sender_wallet="SenderWallet123456789012345678901234567890",
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-123",
            recipient_wallet="RecipientWallet12345678901234567890123",
            amount_frowg=1.0,
        )

        assert tip.amount_lamports == int(1.0 * (10 ** FROWG_DECIMALS))


# =============================================================================
# Test confirm_tip
# =============================================================================


class TestConfirmTip:
    """Tests for confirm_tip method."""

    @pytest.mark.asyncio
    async def test_confirm_tip_success(self, tipping_service, mock_db_session):
        """Test successful tip confirmation."""
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"id": "tip-123"})
        mock_db_session.run.return_value = mock_result

        confirmed = await tipping_service.confirm_tip(
            tip_id="tip-123",
            tx_signature="5UvKX8qG9F...",
        )

        assert confirmed is True
        mock_db_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_tip_not_found(self, tipping_service, mock_db_session):
        """Test confirmation of non-existent tip."""
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_db_session.run.return_value = mock_result

        confirmed = await tipping_service.confirm_tip(
            tip_id="nonexistent-tip",
            tx_signature="5UvKX8qG9F...",
        )

        assert confirmed is False


# =============================================================================
# Test get_tip
# =============================================================================


class TestGetTip:
    """Tests for get_tip method."""

    @pytest.mark.asyncio
    async def test_get_tip_found(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting an existing tip."""
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"t": sample_tip_record})
        mock_db_session.run.return_value = mock_result

        tip = await tipping_service.get_tip("tip-123")

        assert tip is not None
        assert tip.id == "tip-123"
        assert tip.amount_frowg == 100.0

    @pytest.mark.asyncio
    async def test_get_tip_not_found(self, tipping_service, mock_db_session):
        """Test getting a non-existent tip."""
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)
        mock_db_session.run.return_value = mock_result

        tip = await tipping_service.get_tip("nonexistent")

        assert tip is None


# =============================================================================
# Test get_tips_for_target
# =============================================================================


class TestGetTipsForTarget:
    """Tests for get_tips_for_target method."""

    @pytest.mark.asyncio
    async def test_get_tips_for_target(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting tips for a specific target."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"t": sample_tip_record}])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_for_target(
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-789",
        )

        assert len(tips) == 1
        assert tips[0].target_id == "capsule-789"

    @pytest.mark.asyncio
    async def test_get_tips_for_target_with_limit(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting tips with custom limit."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"t": sample_tip_record}])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_for_target(
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-789",
            limit=10,
        )

        assert len(tips) == 1

    @pytest.mark.asyncio
    async def test_get_tips_for_target_empty(self, tipping_service, mock_db_session):
        """Test getting tips when none exist."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_for_target(
            target_type=TipTargetType.CAPSULE,
            target_id="no-tips",
        )

        assert len(tips) == 0

    @pytest.mark.asyncio
    async def test_get_tips_for_target_unconfirmed(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting tips including unconfirmed."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"t": sample_tip_record}])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_for_target(
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-789",
            confirmed_only=False,
        )

        assert len(tips) == 1


# =============================================================================
# Test get_tip_summary
# =============================================================================


class TestGetTipSummary:
    """Tests for get_tip_summary method."""

    @pytest.mark.asyncio
    async def test_get_tip_summary(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting tip summary for a target."""
        # Mock the aggregation query
        mock_agg_result = AsyncMock()
        mock_agg_result.single = AsyncMock(return_value={
            "total_tips": 5,
            "total_frowg": 500.0,
            "unique_tippers": 3,
        })

        # Mock the recent tips query
        mock_recent_result = AsyncMock()
        mock_recent_result.data = AsyncMock(return_value=[{"t": sample_tip_record}])

        mock_db_session.run.side_effect = [mock_agg_result, mock_recent_result]

        summary = await tipping_service.get_tip_summary(
            target_type=TipTargetType.CAPSULE,
            target_id="capsule-789",
        )

        assert isinstance(summary, TipSummary)
        assert summary.total_tips == 5
        assert summary.total_frowg == 500.0
        assert summary.unique_tippers == 3
        assert len(summary.recent_tips) == 1

    @pytest.mark.asyncio
    async def test_get_tip_summary_no_tips(self, tipping_service, mock_db_session):
        """Test getting tip summary when no tips exist."""
        mock_agg_result = AsyncMock()
        mock_agg_result.single = AsyncMock(return_value={
            "total_tips": 0,
            "total_frowg": 0.0,
            "unique_tippers": 0,
        })

        mock_recent_result = AsyncMock()
        mock_recent_result.data = AsyncMock(return_value=[])

        mock_db_session.run.side_effect = [mock_agg_result, mock_recent_result]

        summary = await tipping_service.get_tip_summary(
            target_type=TipTargetType.CAPSULE,
            target_id="no-tips",
        )

        assert summary.total_tips == 0
        assert summary.total_frowg == 0.0
        assert summary.unique_tippers == 0


# =============================================================================
# Test get_tips_by_sender
# =============================================================================


class TestGetTipsBySender:
    """Tests for get_tips_by_sender method."""

    @pytest.mark.asyncio
    async def test_get_tips_by_sender(self, tipping_service, mock_db_session, sample_tip_record):
        """Test getting tips sent by a specific wallet."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"t": sample_tip_record}])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_by_sender(
            sender_wallet="SenderWallet123456789012345678901234567890",
        )

        assert len(tips) == 1
        assert tips[0].sender_wallet == "SenderWallet123456789012345678901234567890"

    @pytest.mark.asyncio
    async def test_get_tips_by_sender_empty(self, tipping_service, mock_db_session):
        """Test getting tips when sender has none."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_db_session.run.return_value = mock_result

        tips = await tipping_service.get_tips_by_sender(
            sender_wallet="NoTipsSender",
        )

        assert len(tips) == 0


# =============================================================================
# Test get_leaderboard
# =============================================================================


class TestGetLeaderboard:
    """Tests for get_leaderboard method."""

    @pytest.mark.asyncio
    async def test_get_leaderboard(self, tipping_service, mock_db_session):
        """Test getting tip leaderboard."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[
            {"target_id": "capsule-1", "total_frowg": 1000.0, "tip_count": 10},
            {"target_id": "capsule-2", "total_frowg": 500.0, "tip_count": 5},
            {"target_id": "capsule-3", "total_frowg": 250.0, "tip_count": 3},
        ])
        mock_db_session.run.return_value = mock_result

        leaderboard = await tipping_service.get_leaderboard(
            target_type=TipTargetType.CAPSULE,
            limit=10,
        )

        assert isinstance(leaderboard, TipLeaderboard)
        assert leaderboard.target_type == TipTargetType.CAPSULE
        assert leaderboard.period == "all_time"
        assert len(leaderboard.entries) == 3
        assert leaderboard.entries[0]["total_frowg"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_leaderboard_empty(self, tipping_service, mock_db_session):
        """Test getting leaderboard when no tips exist."""
        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[])
        mock_db_session.run.return_value = mock_result

        leaderboard = await tipping_service.get_leaderboard(
            target_type=TipTargetType.AGENT,
        )

        assert len(leaderboard.entries) == 0


# =============================================================================
# Test _record_to_tip
# =============================================================================


class TestRecordToTip:
    """Tests for _record_to_tip helper method."""

    def test_record_to_tip_basic(self, tipping_service, sample_tip_record):
        """Test converting Neo4j record to Tip model."""
        tip = tipping_service._record_to_tip(sample_tip_record)

        assert tip.id == "tip-123"
        assert tip.sender_wallet == "SenderWallet123456789012345678901234567890"
        assert tip.target_type == TipTargetType.CAPSULE
        assert tip.amount_frowg == 100.0

    def test_record_to_tip_with_datetime_string(self, tipping_service):
        """Test converting record with datetime as string."""
        record = {
            "id": "tip-456",
            "sender_wallet": "TestWallet",
            "sender_user_id": None,
            "target_type": "agent",
            "target_id": "agent-123",
            "recipient_wallet": "RecipientWallet",
            "amount_frowg": 50.0,
            "amount_lamports": 50_000_000_000,
            "message": None,
            "tx_signature": None,
            "confirmed": True,
            "created_at": "2024-01-01T12:00:00+00:00",
            "confirmed_at": None,
        }

        tip = tipping_service._record_to_tip(record)

        assert tip.id == "tip-456"
        assert tip.confirmed is True


# =============================================================================
# Test Module-Level Functions
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_tipping_service_uninitialized(self):
        """Test getting tipping service when not initialized."""
        from forge.services import tipping_service as ts_module

        # Reset global
        ts_module._tipping_service = None

        result = ts_module.get_tipping_service()

        assert result is None

    @pytest.mark.asyncio
    async def test_init_tipping_service(self, mock_neo4j_client, mock_db_session):
        """Test initializing the global tipping service."""
        from forge.services import tipping_service as ts_module

        # Reset global
        ts_module._tipping_service = None

        mock_db_session.run.return_value = AsyncMock()

        service = await ts_module.init_tipping_service(mock_neo4j_client)

        assert service is not None
        assert ts_module._tipping_service is service

        # Cleanup
        ts_module._tipping_service = None


# =============================================================================
# Test TipTargetType Enum
# =============================================================================


class TestTipTargetType:
    """Tests for TipTargetType enum."""

    def test_all_target_types(self):
        """Test that all expected target types exist."""
        assert TipTargetType.AGENT.value == "agent"
        assert TipTargetType.CAPSULE.value == "capsule"
        assert TipTargetType.USER.value == "user"

    def test_target_type_from_string(self):
        """Test creating target type from string value."""
        target_type = TipTargetType("capsule")
        assert target_type == TipTargetType.CAPSULE
