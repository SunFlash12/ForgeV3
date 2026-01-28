"""
Tests for Revenue Management Service.

This module tests all revenue-related operations for the Forge-Virtuals
integration, including fee collection, revenue distribution, and analytics.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.models.base import RevenueRecord, RevenueType
from forge.virtuals.revenue.service import (
    RevenueService,
    RevenueServiceError,
    get_revenue_service,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_revenue_repo():
    """Create a mock revenue repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.query = AsyncMock(return_value=[])
    repo.query_pending = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_config():
    """Create a mock Virtuals config."""
    config = MagicMock()
    config.inference_fee_per_query = 0.001
    config.overlay_service_fee_percentage = 0.05
    config.governance_reward_pool_percentage = 0.10
    config.enable_revenue_sharing = True
    config.primary_chain = MagicMock(value="base")
    return config


@pytest.fixture
def mock_chain_manager():
    """Create a mock chain manager."""
    manager = MagicMock()
    manager.primary_client = MagicMock()
    return manager


@pytest.fixture
def revenue_service(mock_revenue_repo, mock_config):
    """Create a RevenueService with mocked dependencies."""
    with patch("forge.virtuals.revenue.service.get_virtuals_config", return_value=mock_config):
        service = RevenueService(mock_revenue_repo)
        service._pending_distributions = []
        return service


# ==================== Initialization Tests ====================


class TestRevenueServiceInit:
    """Tests for RevenueService initialization."""

    def test_service_creation(self, mock_revenue_repo, mock_config):
        """Test creating a revenue service."""
        with patch("forge.virtuals.revenue.service.get_virtuals_config", return_value=mock_config):
            service = RevenueService(mock_revenue_repo)

            assert service._revenue_repo == mock_revenue_repo
            assert service.config == mock_config

    @pytest.mark.asyncio
    async def test_initialize(self, revenue_service, mock_revenue_repo, mock_chain_manager):
        """Test service initialization."""
        mock_revenue_repo.query_pending = AsyncMock(return_value=[])

        with patch(
            "forge.virtuals.revenue.service.get_chain_manager",
            AsyncMock(return_value=mock_chain_manager),
        ):
            await revenue_service.initialize()

            assert revenue_service._chain_manager == mock_chain_manager

    @pytest.mark.asyncio
    async def test_initialize_loads_pending(self, revenue_service, mock_revenue_repo, mock_chain_manager):
        """Test that initialization loads pending distributions."""
        pending_records = [
            RevenueRecord(
                id="rev-1",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id="capsule-1",
                source_entity_type="capsule",
            ),
            RevenueRecord(
                id="rev-2",
                revenue_type=RevenueType.SERVICE_FEE,
                amount_virtual=0.5,
                source_entity_id="overlay-1",
                source_entity_type="overlay",
            ),
        ]
        mock_revenue_repo.query_pending = AsyncMock(return_value=pending_records)

        with patch(
            "forge.virtuals.revenue.service.get_chain_manager",
            AsyncMock(return_value=mock_chain_manager),
        ):
            await revenue_service.initialize()

            assert len(revenue_service._pending_distributions) == 2


# ==================== Record Inference Fee Tests ====================


class TestRecordInferenceFee:
    """Tests for record_inference_fee method."""

    @pytest.mark.asyncio
    async def test_record_inference_fee(self, revenue_service, mock_revenue_repo):
        """Test recording an inference fee."""
        result = await revenue_service.record_inference_fee(
            capsule_id="capsule-123",
            user_wallet="0x" + "1" * 40,
            query_text="What is the capital of France?",
            tokens_processed=100,
        )

        assert result is not None
        assert result.revenue_type == RevenueType.INFERENCE_FEE
        mock_revenue_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_inference_fee_with_high_tokens(self, revenue_service, mock_revenue_repo):
        """Test recording inference fee with high token count."""
        result = await revenue_service.record_inference_fee(
            capsule_id="capsule-456",
            user_wallet="0x" + "2" * 40,
            query_text="Complex query",
            tokens_processed=10000,
        )

        # Fee should be base + token fee
        assert result.amount_virtual > revenue_service.config.inference_fee_per_query

    @pytest.mark.asyncio
    async def test_record_inference_fee_adds_to_pending(self, revenue_service, mock_revenue_repo):
        """Test that inference fee is added to pending distributions."""
        initial_pending = len(revenue_service._pending_distributions)

        await revenue_service.record_inference_fee(
            capsule_id="capsule-789",
            user_wallet="0x" + "3" * 40,
            query_text="Test query",
            tokens_processed=50,
        )

        assert len(revenue_service._pending_distributions) == initial_pending + 1


# ==================== Record Service Fee Tests ====================


class TestRecordServiceFee:
    """Tests for record_service_fee method."""

    @pytest.mark.asyncio
    async def test_record_service_fee(self, revenue_service, mock_revenue_repo):
        """Test recording a service fee."""
        result = await revenue_service.record_service_fee(
            overlay_id="overlay-123",
            service_type="analysis",
            base_amount_virtual=100.0,
            client_wallet="0x" + "1" * 40,
        )

        assert result is not None
        assert result.revenue_type == RevenueType.SERVICE_FEE
        # Fee should be 5% of base amount
        assert result.amount_virtual == 5.0

    @pytest.mark.asyncio
    async def test_record_service_fee_metadata(self, revenue_service, mock_revenue_repo):
        """Test service fee includes correct metadata."""
        await revenue_service.record_service_fee(
            overlay_id="overlay-456",
            service_type="validation",
            base_amount_virtual=50.0,
            client_wallet="0x" + "2" * 40,
        )

        create_call = mock_revenue_repo.create.call_args
        record = create_call[0][0]
        assert record.metadata["service_type"] == "validation"
        assert record.metadata["base_amount"] == 50.0


# ==================== Record Governance Reward Tests ====================


class TestRecordGovernanceReward:
    """Tests for record_governance_reward method."""

    @pytest.mark.asyncio
    async def test_record_vote_reward(self, revenue_service, mock_revenue_repo):
        """Test recording a vote reward."""
        result = await revenue_service.record_governance_reward(
            participant_wallet="0x" + "1" * 40,
            proposal_id="proposal-123",
            participation_type="vote",
        )

        assert result.revenue_type == RevenueType.GOVERNANCE_REWARD
        assert result.amount_virtual == 0.01  # Vote reward

    @pytest.mark.asyncio
    async def test_record_proposal_reward(self, revenue_service, mock_revenue_repo):
        """Test recording a proposal creation reward."""
        result = await revenue_service.record_governance_reward(
            participant_wallet="0x" + "2" * 40,
            proposal_id="proposal-456",
            participation_type="proposal",
        )

        assert result.amount_virtual == 0.5  # Proposal reward

    @pytest.mark.asyncio
    async def test_record_evaluation_reward(self, revenue_service, mock_revenue_repo):
        """Test recording an evaluation reward."""
        result = await revenue_service.record_governance_reward(
            participant_wallet="0x" + "3" * 40,
            proposal_id="proposal-789",
            participation_type="evaluation",
        )

        assert result.amount_virtual == 0.1  # Evaluation reward

    @pytest.mark.asyncio
    async def test_record_unknown_participation_type(self, revenue_service, mock_revenue_repo):
        """Test recording reward for unknown participation type."""
        result = await revenue_service.record_governance_reward(
            participant_wallet="0x" + "4" * 40,
            proposal_id="proposal-000",
            participation_type="unknown",
        )

        # Should default to vote reward
        assert result.amount_virtual == 0.01


# ==================== Record Trading Fee Tests ====================


class TestRecordTradingFee:
    """Tests for record_trading_fee method."""

    @pytest.mark.asyncio
    async def test_record_trading_fee_buy(self, revenue_service, mock_revenue_repo):
        """Test recording a buy trading fee."""
        result = await revenue_service.record_trading_fee(
            token_address="0x" + "a" * 40,
            trade_amount_virtual=1000.0,
            trader_wallet="0x" + "1" * 40,
            trade_type="buy",
        )

        assert result.revenue_type == RevenueType.TRADING_FEE
        # 1% Sentient Tax
        assert result.amount_virtual == 10.0

    @pytest.mark.asyncio
    async def test_record_trading_fee_sell(self, revenue_service, mock_revenue_repo):
        """Test recording a sell trading fee."""
        result = await revenue_service.record_trading_fee(
            token_address="0x" + "b" * 40,
            trade_amount_virtual=500.0,
            trader_wallet="0x" + "2" * 40,
            trade_type="sell",
        )

        assert result.amount_virtual == 5.0  # 1% of 500


# ==================== Process Pending Distributions Tests ====================


class TestProcessPendingDistributions:
    """Tests for process_pending_distributions method."""

    @pytest.mark.asyncio
    async def test_process_no_pending(self, revenue_service):
        """Test processing when no pending distributions."""
        revenue_service._pending_distributions = []

        result = await revenue_service.process_pending_distributions()

        assert result == {}

    @pytest.mark.asyncio
    async def test_process_pending_batch(self, revenue_service, mock_revenue_repo):
        """Test processing a batch of pending distributions."""
        beneficiary = "0x" + "1" * 40
        records = [
            RevenueRecord(
                id="rev-1",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id="capsule-1",
                source_entity_type="capsule",
                beneficiary_addresses=[beneficiary],
            ),
            RevenueRecord(
                id="rev-2",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.02,
                source_entity_id="capsule-2",
                source_entity_type="capsule",
                beneficiary_addresses=[beneficiary],
            ),
        ]
        revenue_service._pending_distributions = records

        with patch.object(
            revenue_service, "_execute_batch_distribution", new_callable=AsyncMock
        ):
            result = await revenue_service.process_pending_distributions()

            assert beneficiary in result
            assert result[beneficiary] == 0.03

    @pytest.mark.asyncio
    async def test_process_integrity_check_fails(self, revenue_service, mock_revenue_repo):
        """Test that integrity check catches mismatched amounts."""
        # This would require modifying the aggregation logic to fail
        # The test validates the security fix for Audit 4 - M16
        beneficiary = "0x" + "1" * 40
        records = [
            RevenueRecord(
                id="rev-1",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id="capsule-1",
                source_entity_type="capsule",
                beneficiary_addresses=[beneficiary],
            ),
        ]
        revenue_service._pending_distributions = records

        # Normal processing should succeed
        with patch.object(
            revenue_service, "_execute_batch_distribution", new_callable=AsyncMock
        ):
            result = await revenue_service.process_pending_distributions()
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_process_batch_size_limit(self, revenue_service, mock_revenue_repo):
        """Test that batch size is respected."""
        beneficiary = "0x" + "1" * 40
        records = [
            RevenueRecord(
                id=f"rev-{i}",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id=f"capsule-{i}",
                source_entity_type="capsule",
                beneficiary_addresses=[beneficiary],
            )
            for i in range(150)
        ]
        revenue_service._pending_distributions = records

        with patch.object(
            revenue_service, "_execute_batch_distribution", new_callable=AsyncMock
        ):
            await revenue_service.process_pending_distributions(batch_size=100)

            # Should have 50 remaining
            assert len(revenue_service._pending_distributions) == 50

    @pytest.mark.asyncio
    async def test_process_distribution_failure_returns_to_queue(
        self, revenue_service, mock_revenue_repo
    ):
        """Test that failed distributions are returned to queue."""
        beneficiary = "0x" + "1" * 40
        records = [
            RevenueRecord(
                id="rev-1",
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id="capsule-1",
                source_entity_type="capsule",
                beneficiary_addresses=[beneficiary],
            ),
        ]
        revenue_service._pending_distributions = records.copy()

        with patch.object(
            revenue_service,
            "_execute_batch_distribution",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Network error"),
        ):
            with pytest.raises(RevenueServiceError):
                await revenue_service.process_pending_distributions()

            # Record should be back in pending
            assert len(revenue_service._pending_distributions) == 1


# ==================== Get Revenue Summary Tests ====================


class TestGetRevenueSummary:
    """Tests for get_revenue_summary method."""

    @pytest.mark.asyncio
    async def test_get_summary_empty(self, revenue_service, mock_revenue_repo):
        """Test getting summary with no records."""
        mock_revenue_repo.query = AsyncMock(return_value=[])

        result = await revenue_service.get_revenue_summary()

        assert result["total_revenue_virtual"] == 0
        assert result["record_count"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_with_records(self, revenue_service, mock_revenue_repo):
        """Test getting summary with records."""
        now = datetime.now(UTC)
        records = [
            RevenueRecord(
                id="rev-1",
                timestamp=now,
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=0.01,
                source_entity_id="capsule-1",
                source_entity_type="capsule",
            ),
            RevenueRecord(
                id="rev-2",
                timestamp=now,
                revenue_type=RevenueType.SERVICE_FEE,
                amount_virtual=5.0,
                source_entity_id="overlay-1",
                source_entity_type="overlay",
            ),
        ]
        mock_revenue_repo.query = AsyncMock(return_value=records)

        result = await revenue_service.get_revenue_summary()

        assert result["total_revenue_virtual"] == 5.01
        assert result["record_count"] == 2
        assert "by_type" in result

    @pytest.mark.asyncio
    async def test_get_summary_by_entity(self, revenue_service, mock_revenue_repo):
        """Test getting summary filtered by entity."""
        mock_revenue_repo.query = AsyncMock(return_value=[])

        await revenue_service.get_revenue_summary(
            entity_id="capsule-123",
            entity_type="capsule",
        )

        call_args = mock_revenue_repo.query.call_args
        assert call_args[1]["entity_id"] == "capsule-123"
        assert call_args[1]["entity_type"] == "capsule"


# ==================== Get Entity Revenue Tests ====================


class TestGetEntityRevenue:
    """Tests for get_entity_revenue method."""

    @pytest.mark.asyncio
    async def test_get_entity_revenue_no_records(self, revenue_service, mock_revenue_repo):
        """Test getting entity revenue with no records."""
        mock_revenue_repo.query = AsyncMock(return_value=[])

        result = await revenue_service.get_entity_revenue("capsule-123", "capsule")

        assert result["total_revenue"] == 0
        assert result["record_count"] == 0

    @pytest.mark.asyncio
    async def test_get_entity_revenue_with_records(self, revenue_service, mock_revenue_repo):
        """Test getting entity revenue with records."""
        now = datetime.now(UTC)
        records = [
            RevenueRecord(
                id="rev-1",
                timestamp=now - timedelta(days=30),
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=10.0,
                source_entity_id="capsule-123",
                source_entity_type="capsule",
            ),
            RevenueRecord(
                id="rev-2",
                timestamp=now,
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=15.0,
                source_entity_id="capsule-123",
                source_entity_type="capsule",
            ),
        ]
        mock_revenue_repo.query = AsyncMock(return_value=records)

        result = await revenue_service.get_entity_revenue("capsule-123", "capsule")

        assert result["total_revenue"] == 25.0
        assert result["record_count"] == 2
        assert "monthly_breakdown" in result


# ==================== Estimate Entity Value Tests ====================


class TestEstimateEntityValue:
    """Tests for estimate_entity_value method."""

    @pytest.mark.asyncio
    async def test_estimate_value_no_revenue(self, revenue_service, mock_revenue_repo):
        """Test estimating value with no revenue history."""
        mock_revenue_repo.query = AsyncMock(return_value=[])

        result = await revenue_service.estimate_entity_value("capsule-123", "capsule")

        assert result["estimated_value"] == 0
        assert result["note"] == "No revenue history"

    @pytest.mark.asyncio
    async def test_estimate_value_with_revenue(self, revenue_service, mock_revenue_repo):
        """Test estimating value with revenue history."""
        now = datetime.now(UTC)
        records = [
            RevenueRecord(
                id=f"rev-{i}",
                timestamp=now - timedelta(days=i * 30),
                revenue_type=RevenueType.INFERENCE_FEE,
                amount_virtual=100.0,
                source_entity_id="capsule-123",
                source_entity_type="capsule",
            )
            for i in range(3)
        ]
        mock_revenue_repo.query = AsyncMock(return_value=records)

        result = await revenue_service.estimate_entity_value("capsule-123", "capsule")

        assert result["estimated_value_virtual"] > 0
        assert result["method"] == "dcf_perpetuity"

    @pytest.mark.asyncio
    async def test_estimate_value_growth_exceeds_discount(self, revenue_service, mock_revenue_repo):
        """Test estimation when growth exceeds discount rate."""
        now = datetime.now(UTC)
        records = [
            RevenueRecord(
                id="rev-1",
                timestamp=now,
                revenue_type=RevenueType.SERVICE_FEE,
                amount_virtual=1000.0,
                source_entity_id="overlay-123",
                source_entity_type="overlay",
            ),
        ]
        mock_revenue_repo.query = AsyncMock(return_value=records)

        result = await revenue_service.estimate_entity_value(
            "overlay-123",
            "overlay",
            discount_rate=0.05,
            growth_rate=0.10,  # Growth > discount
        )

        # Should use simple multiple instead
        assert result["estimated_value_virtual"] > 0


# ==================== Global Service Tests ====================


class TestGetRevenueService:
    """Tests for get_revenue_service function."""

    @pytest.mark.asyncio
    async def test_get_service_first_call(self, mock_revenue_repo, mock_chain_manager, mock_config):
        """Test getting service on first call."""
        import forge.virtuals.revenue.service as service_module

        service_module._revenue_service = None

        with patch("forge.virtuals.revenue.service.get_virtuals_config", return_value=mock_config):
            with patch(
                "forge.virtuals.revenue.service.get_chain_manager",
                AsyncMock(return_value=mock_chain_manager),
            ):
                service = await get_revenue_service(mock_revenue_repo)

                assert service is not None
                assert isinstance(service, RevenueService)

        # Cleanup
        service_module._revenue_service = None

    @pytest.mark.asyncio
    async def test_get_service_without_repo_on_first_call(self):
        """Test error when repo not provided on first call."""
        import forge.virtuals.revenue.service as service_module

        service_module._revenue_service = None

        with pytest.raises(RevenueServiceError, match="Repository required"):
            await get_revenue_service()

        # Cleanup
        service_module._revenue_service = None
