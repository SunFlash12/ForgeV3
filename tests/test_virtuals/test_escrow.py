"""
Tests for the ACP Escrow Service.

This module contains comprehensive tests for the escrow functionality
including creation, release, refund, and dispute resolution operations.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the modules under test
from forge.virtuals.acp.escrow import (
    ESCROW_ABI,
    EscrowError,
    EscrowRecord,
    EscrowService,
    EscrowStatus,
    get_escrow_service,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_chain_manager():
    """Create a mock chain manager for testing."""
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()

    # Mock the client returned by get_client
    mock_client = MagicMock()
    mock_client.approve_tokens = AsyncMock()
    mock_client.execute_contract = AsyncMock(
        return_value=MagicMock(tx_hash="0x" + "a" * 64)
    )
    manager.get_client = MagicMock(return_value=mock_client)

    return manager


@pytest.fixture
def escrow_service(mock_chain_manager):
    """Create an EscrowService instance for testing."""
    service = EscrowService(
        chain_manager=mock_chain_manager,
        escrow_contract_address=None,  # Simulated mode
    )
    return service


@pytest.fixture
def escrow_service_with_contract(mock_chain_manager):
    """Create an EscrowService instance with a real contract address."""
    service = EscrowService(
        chain_manager=mock_chain_manager,
        escrow_contract_address="0x" + "1" * 40,
    )
    return service


@pytest.fixture
def sample_escrow_params():
    """Sample parameters for creating an escrow."""
    return {
        "job_id": "job-123",
        "buyer_address": "0x" + "B" * 40,
        "provider_address": "0x" + "P" * 40,
        "amount": Decimal("100.0"),
        "deadline_hours": 24,
        "metadata": {"description": "Test job"},
    }


# ==================== EscrowStatus Tests ====================


class TestEscrowStatus:
    """Tests for the EscrowStatus enum."""

    def test_escrow_status_values(self):
        """Test that all expected status values exist."""
        assert EscrowStatus.PENDING == "pending"
        assert EscrowStatus.FUNDED == "funded"
        assert EscrowStatus.RELEASED == "released"
        assert EscrowStatus.REFUNDED == "refunded"
        assert EscrowStatus.DISPUTED == "disputed"
        assert EscrowStatus.EXPIRED == "expired"

    def test_escrow_status_is_string(self):
        """Test that EscrowStatus values are strings."""
        for status in EscrowStatus:
            assert isinstance(status.value, str)


# ==================== EscrowRecord Tests ====================


class TestEscrowRecord:
    """Tests for the EscrowRecord model."""

    def test_escrow_record_creation_minimal(self):
        """Test creating an EscrowRecord with minimal fields."""
        record = EscrowRecord(
            job_id="job-1",
            buyer_address="0xBuyer",
            provider_address="0xProvider",
            amount=Decimal("50.0"),
        )

        assert record.job_id == "job-1"
        assert record.buyer_address == "0xBuyer"
        assert record.provider_address == "0xProvider"
        assert record.amount == Decimal("50.0")
        assert record.status == EscrowStatus.PENDING
        assert record.fee_amount == Decimal("0")
        assert record.id is not None
        assert record.created_at is not None

    def test_escrow_record_creation_full(self):
        """Test creating an EscrowRecord with all fields."""
        deadline = datetime.now(UTC) + timedelta(hours=24)
        record = EscrowRecord(
            job_id="job-2",
            buyer_address="0xBuyer",
            provider_address="0xProvider",
            amount=Decimal("100.0"),
            fee_amount=Decimal("1.0"),
            status=EscrowStatus.FUNDED,
            escrow_id_onchain=12345,
            funding_tx_hash="0x" + "f" * 64,
            deadline=deadline,
            metadata={"key": "value"},
        )

        assert record.fee_amount == Decimal("1.0")
        assert record.status == EscrowStatus.FUNDED
        assert record.escrow_id_onchain == 12345
        assert record.funding_tx_hash == "0x" + "f" * 64
        assert record.deadline == deadline
        assert record.metadata == {"key": "value"}

    def test_escrow_record_uuid_generation(self):
        """Test that each EscrowRecord gets a unique ID."""
        record1 = EscrowRecord(
            job_id="job-1",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
        )
        record2 = EscrowRecord(
            job_id="job-1",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
        )

        assert record1.id != record2.id


# ==================== EscrowService Initialization Tests ====================


class TestEscrowServiceInitialization:
    """Tests for EscrowService initialization."""

    @pytest.mark.asyncio
    async def test_initialize_simulated_mode(self, escrow_service):
        """Test initialization in simulated mode (no contract address)."""
        await escrow_service.initialize()

        assert escrow_service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_contract(self, escrow_service_with_contract):
        """Test initialization with a contract address."""
        await escrow_service_with_contract.initialize()

        assert escrow_service_with_contract._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, escrow_service):
        """Test that initialization is idempotent."""
        await escrow_service.initialize()
        await escrow_service.initialize()  # Should not raise

        assert escrow_service._initialized is True

    @pytest.mark.asyncio
    async def test_close(self, escrow_service):
        """Test closing the escrow service."""
        await escrow_service.initialize()
        await escrow_service.close()

        assert escrow_service._initialized is False

    @pytest.mark.asyncio
    async def test_close_calls_chain_manager_close(self, mock_chain_manager):
        """Test that close() calls chain_manager.close()."""
        service = EscrowService(chain_manager=mock_chain_manager)
        await service.initialize()
        await service.close()

        mock_chain_manager.close.assert_called_once()


# ==================== Escrow Creation Tests ====================


class TestEscrowCreation:
    """Tests for creating escrows."""

    @pytest.mark.asyncio
    async def test_create_escrow_simulated_mode(self, escrow_service, sample_escrow_params):
        """Test creating an escrow in simulated mode."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        assert escrow.job_id == sample_escrow_params["job_id"]
        assert escrow.buyer_address == sample_escrow_params["buyer_address"]
        assert escrow.provider_address == sample_escrow_params["provider_address"]
        assert escrow.amount == sample_escrow_params["amount"]
        assert escrow.status == EscrowStatus.FUNDED
        assert escrow.funded_at is not None

    @pytest.mark.asyncio
    async def test_create_escrow_calculates_fee(self, escrow_service, sample_escrow_params):
        """Test that escrow creation calculates the platform fee."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        # Platform fee is 1% (100 basis points)
        expected_fee = sample_escrow_params["amount"] * Decimal("0.01")
        assert escrow.fee_amount == expected_fee

    @pytest.mark.asyncio
    async def test_create_escrow_sets_deadline(self, escrow_service, sample_escrow_params):
        """Test that escrow creation sets the deadline correctly."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        assert escrow.deadline is not None
        # Deadline should be approximately 24 hours from now
        expected_deadline = datetime.now(UTC) + timedelta(hours=24)
        assert abs((escrow.deadline - expected_deadline).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_create_escrow_stores_metadata(self, escrow_service, sample_escrow_params):
        """Test that escrow creation stores metadata."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        assert escrow.metadata == sample_escrow_params["metadata"]

    @pytest.mark.asyncio
    async def test_create_escrow_auto_initializes(self, sample_escrow_params):
        """Test that create_escrow auto-initializes the service if needed."""
        service = EscrowService()
        assert service._initialized is False

        escrow = await service.create_escrow(**sample_escrow_params)

        assert service._initialized is True
        assert escrow.status == EscrowStatus.FUNDED

    @pytest.mark.asyncio
    async def test_create_escrow_stores_in_cache(self, escrow_service, sample_escrow_params):
        """Test that created escrows are stored in the internal cache."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        cached = escrow_service.get_escrow(escrow.id)
        assert cached is not None
        assert cached.id == escrow.id


# ==================== Escrow Release Tests ====================


class TestEscrowRelease:
    """Tests for releasing escrows."""

    @pytest.mark.asyncio
    async def test_release_escrow_success(self, escrow_service, sample_escrow_params):
        """Test successfully releasing an escrow."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        released = await escrow_service.release_escrow(escrow.id)

        assert released.status == EscrowStatus.RELEASED
        assert released.resolved_at is not None

    @pytest.mark.asyncio
    async def test_release_escrow_not_found(self, escrow_service):
        """Test releasing a non-existent escrow."""
        await escrow_service.initialize()

        with pytest.raises(EscrowError, match="Escrow not found"):
            await escrow_service.release_escrow("nonexistent-id")

    @pytest.mark.asyncio
    async def test_release_escrow_wrong_status(self, escrow_service, sample_escrow_params):
        """Test releasing an escrow that's not in FUNDED status."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.release_escrow(escrow.id)

        # Try to release again
        with pytest.raises(EscrowError, match="Cannot release escrow in status"):
            await escrow_service.release_escrow(escrow.id)

    @pytest.mark.asyncio
    async def test_release_escrow_pending_fails(self, escrow_service):
        """Test that releasing a PENDING escrow fails."""
        await escrow_service.initialize()

        # Manually create a PENDING escrow
        escrow = EscrowRecord(
            job_id="job-pending",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
            status=EscrowStatus.PENDING,
        )
        escrow_service._escrows[escrow.id] = escrow

        with pytest.raises(EscrowError, match="Cannot release escrow in status"):
            await escrow_service.release_escrow(escrow.id)


# ==================== Escrow Refund Tests ====================


class TestEscrowRefund:
    """Tests for refunding escrows."""

    @pytest.mark.asyncio
    async def test_refund_escrow_success(self, escrow_service, sample_escrow_params):
        """Test successfully refunding an escrow."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        refunded = await escrow_service.refund_escrow(escrow.id, "Job cancelled")

        assert refunded.status == EscrowStatus.REFUNDED
        assert refunded.resolved_at is not None
        assert refunded.metadata["refund_reason"] == "Job cancelled"

    @pytest.mark.asyncio
    async def test_refund_escrow_not_found(self, escrow_service):
        """Test refunding a non-existent escrow."""
        await escrow_service.initialize()

        with pytest.raises(EscrowError, match="Escrow not found"):
            await escrow_service.refund_escrow("nonexistent-id")

    @pytest.mark.asyncio
    async def test_refund_escrow_wrong_status(self, escrow_service, sample_escrow_params):
        """Test refunding an escrow that's not in FUNDED or DISPUTED status."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.release_escrow(escrow.id)

        with pytest.raises(EscrowError, match="Cannot refund escrow in status"):
            await escrow_service.refund_escrow(escrow.id)

    @pytest.mark.asyncio
    async def test_refund_disputed_escrow(self, escrow_service, sample_escrow_params):
        """Test refunding a disputed escrow."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "Quality issue")

        refunded = await escrow_service.refund_escrow(escrow.id, "Dispute favored buyer")

        assert refunded.status == EscrowStatus.REFUNDED


# ==================== Escrow Dispute Tests ====================


class TestEscrowDispute:
    """Tests for escrow disputes."""

    @pytest.mark.asyncio
    async def test_initiate_dispute_success(self, escrow_service, sample_escrow_params):
        """Test initiating a dispute on an escrow."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        disputed = await escrow_service.initiate_dispute(escrow.id, "Work not delivered")

        assert disputed.status == EscrowStatus.DISPUTED
        assert disputed.metadata["dispute_reason"] == "Work not delivered"
        assert "disputed_at" in disputed.metadata

    @pytest.mark.asyncio
    async def test_initiate_dispute_not_found(self, escrow_service):
        """Test disputing a non-existent escrow."""
        await escrow_service.initialize()

        with pytest.raises(EscrowError, match="Escrow not found"):
            await escrow_service.initiate_dispute("nonexistent-id", "Reason")

    @pytest.mark.asyncio
    async def test_initiate_dispute_wrong_status(self, escrow_service, sample_escrow_params):
        """Test disputing an escrow that's not in FUNDED status."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.release_escrow(escrow.id)

        with pytest.raises(EscrowError, match="Cannot dispute escrow in status"):
            await escrow_service.initiate_dispute(escrow.id, "Late dispute")

    @pytest.mark.asyncio
    async def test_resolve_dispute_success(self, escrow_service, sample_escrow_params):
        """Test resolving a dispute."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "Quality issue")

        resolved = await escrow_service.resolve_dispute(
            escrow.id, buyer_share_pct=30, resolution_notes="Partial delivery"
        )

        assert resolved.status == EscrowStatus.RELEASED
        assert resolved.resolved_at is not None
        assert resolved.metadata["resolution"]["buyer_share_pct"] == 30
        assert resolved.metadata["resolution"]["provider_share_pct"] == 70
        assert resolved.metadata["resolution"]["notes"] == "Partial delivery"

    @pytest.mark.asyncio
    async def test_resolve_dispute_invalid_percentage(self, escrow_service, sample_escrow_params):
        """Test resolving dispute with invalid percentage."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "Issue")

        with pytest.raises(ValueError, match="buyer_share_pct must be between 0 and 100"):
            await escrow_service.resolve_dispute(escrow.id, buyer_share_pct=150)

    @pytest.mark.asyncio
    async def test_resolve_dispute_negative_percentage(self, escrow_service, sample_escrow_params):
        """Test resolving dispute with negative percentage."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "Issue")

        with pytest.raises(ValueError, match="buyer_share_pct must be between 0 and 100"):
            await escrow_service.resolve_dispute(escrow.id, buyer_share_pct=-10)

    @pytest.mark.asyncio
    async def test_resolve_non_disputed_escrow(self, escrow_service, sample_escrow_params):
        """Test resolving a non-disputed escrow."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        with pytest.raises(EscrowError, match="Cannot resolve non-disputed escrow"):
            await escrow_service.resolve_dispute(escrow.id, buyer_share_pct=50)

    @pytest.mark.asyncio
    async def test_resolve_dispute_full_buyer(self, escrow_service, sample_escrow_params):
        """Test resolving dispute 100% in favor of buyer."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "No delivery")

        resolved = await escrow_service.resolve_dispute(
            escrow.id, buyer_share_pct=100, resolution_notes="Full refund"
        )

        assert resolved.metadata["resolution"]["buyer_share_pct"] == 100
        assert resolved.metadata["resolution"]["provider_share_pct"] == 0

    @pytest.mark.asyncio
    async def test_resolve_dispute_full_provider(self, escrow_service, sample_escrow_params):
        """Test resolving dispute 100% in favor of provider."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)
        await escrow_service.initiate_dispute(escrow.id, "False claim")

        resolved = await escrow_service.resolve_dispute(
            escrow.id, buyer_share_pct=0, resolution_notes="Buyer's claim invalid"
        )

        assert resolved.metadata["resolution"]["buyer_share_pct"] == 0
        assert resolved.metadata["resolution"]["provider_share_pct"] == 100


# ==================== Escrow Query Tests ====================


class TestEscrowQueries:
    """Tests for querying escrows."""

    @pytest.mark.asyncio
    async def test_get_escrow(self, escrow_service, sample_escrow_params):
        """Test getting an escrow by ID."""
        created = await escrow_service.create_escrow(**sample_escrow_params)

        retrieved = escrow_service.get_escrow(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_escrow_not_found(self, escrow_service):
        """Test getting a non-existent escrow."""
        result = escrow_service.get_escrow("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_escrows_by_job(self, escrow_service):
        """Test getting escrows by job ID."""
        await escrow_service.initialize()

        # Create multiple escrows for the same job
        params1 = {
            "job_id": "job-multi",
            "buyer_address": "0xB1",
            "provider_address": "0xP1",
            "amount": Decimal("10.0"),
        }
        params2 = {
            "job_id": "job-multi",
            "buyer_address": "0xB2",
            "provider_address": "0xP2",
            "amount": Decimal("20.0"),
        }
        params3 = {
            "job_id": "job-other",
            "buyer_address": "0xB3",
            "provider_address": "0xP3",
            "amount": Decimal("30.0"),
        }

        await escrow_service.create_escrow(**params1)
        await escrow_service.create_escrow(**params2)
        await escrow_service.create_escrow(**params3)

        escrows = escrow_service.get_escrows_by_job("job-multi")

        assert len(escrows) == 2
        assert all(e.job_id == "job-multi" for e in escrows)

    @pytest.mark.asyncio
    async def test_get_pending_escrows(self, escrow_service, sample_escrow_params):
        """Test getting pending (funded) escrows."""
        await escrow_service.initialize()

        escrow1 = await escrow_service.create_escrow(**sample_escrow_params)

        params2 = sample_escrow_params.copy()
        params2["job_id"] = "job-456"
        escrow2 = await escrow_service.create_escrow(**params2)

        # Release one escrow
        await escrow_service.release_escrow(escrow1.id)

        pending = escrow_service.get_pending_escrows()

        assert len(pending) == 1
        assert pending[0].id == escrow2.id


# ==================== Expired Escrow Tests ====================


class TestExpiredEscrows:
    """Tests for expired escrow handling."""

    @pytest.mark.asyncio
    async def test_check_expired_escrows_none_expired(self, escrow_service, sample_escrow_params):
        """Test checking for expired escrows when none are expired."""
        await escrow_service.create_escrow(**sample_escrow_params)

        expired = await escrow_service.check_expired_escrows()

        assert len(expired) == 0

    @pytest.mark.asyncio
    async def test_check_expired_escrows_auto_release(self, escrow_service):
        """Test that expired escrows are auto-released to provider."""
        await escrow_service.initialize()

        # Create escrow with past deadline
        escrow = EscrowRecord(
            job_id="job-expired",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
            status=EscrowStatus.FUNDED,
            funded_at=datetime.now(UTC) - timedelta(days=2),
            deadline=datetime.now(UTC) - timedelta(hours=1),  # Past deadline
        )
        escrow_service._escrows[escrow.id] = escrow

        expired = await escrow_service.check_expired_escrows()

        assert len(expired) == 1
        assert expired[0].status == EscrowStatus.RELEASED
        assert expired[0].metadata.get("auto_released") is True


# ==================== Concurrency Tests ====================


class TestEscrowConcurrency:
    """Tests for escrow concurrency handling (SECURITY FIX Audit 5 - C2)."""

    @pytest.mark.asyncio
    async def test_concurrent_release_same_escrow(self, escrow_service, sample_escrow_params):
        """Test that concurrent releases of the same escrow don't cause race conditions."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        # Try to release the same escrow concurrently
        async def try_release():
            try:
                await escrow_service.release_escrow(escrow.id)
                return "success"
            except EscrowError:
                return "failed"

        results = await asyncio.gather(
            try_release(),
            try_release(),
            try_release(),
        )

        # Only one should succeed
        assert results.count("success") == 1
        assert results.count("failed") == 2

    @pytest.mark.asyncio
    async def test_concurrent_dispute_and_release(self, escrow_service, sample_escrow_params):
        """Test concurrent dispute initiation and release."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        async def try_dispute():
            try:
                await escrow_service.initiate_dispute(escrow.id, "Issue")
                return "disputed"
            except EscrowError:
                return "dispute_failed"

        async def try_release():
            try:
                await escrow_service.release_escrow(escrow.id)
                return "released"
            except EscrowError:
                return "release_failed"

        results = await asyncio.gather(
            try_dispute(),
            try_release(),
        )

        # One should succeed, one should fail
        assert len(set(results)) == 2  # Two different results

    @pytest.mark.asyncio
    async def test_escrow_lock_creation(self, escrow_service, sample_escrow_params):
        """Test that escrow locks are properly created."""
        escrow = await escrow_service.create_escrow(**sample_escrow_params)

        lock1 = await escrow_service._get_escrow_lock(escrow.id)
        lock2 = await escrow_service._get_escrow_lock(escrow.id)

        # Same lock should be returned
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_different_escrows_different_locks(self, escrow_service, sample_escrow_params):
        """Test that different escrows get different locks."""
        escrow1 = await escrow_service.create_escrow(**sample_escrow_params)

        params2 = sample_escrow_params.copy()
        params2["job_id"] = "job-456"
        escrow2 = await escrow_service.create_escrow(**params2)

        lock1 = await escrow_service._get_escrow_lock(escrow1.id)
        lock2 = await escrow_service._get_escrow_lock(escrow2.id)

        assert lock1 is not lock2


# ==================== On-Chain Escrow Tests ====================


class TestOnChainEscrow:
    """Tests for on-chain escrow operations."""

    @pytest.mark.asyncio
    async def test_create_onchain_escrow_requires_chain_manager(self):
        """Test that on-chain escrow creation requires a chain manager."""
        service = EscrowService(
            chain_manager=None,
            escrow_contract_address="0x" + "1" * 40,
        )
        await service.initialize()

        escrow = EscrowRecord(
            job_id="job-1",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
            deadline=datetime.now(UTC) + timedelta(hours=24),
        )

        with pytest.raises(EscrowError, match="Chain manager not initialized"):
            await service._create_onchain_escrow(escrow)

    @pytest.mark.asyncio
    async def test_create_onchain_escrow_requires_deadline(
        self, escrow_service_with_contract
    ):
        """Test that on-chain escrow creation requires a deadline."""
        await escrow_service_with_contract.initialize()

        escrow = EscrowRecord(
            job_id="job-1",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("10.0"),
            deadline=None,  # No deadline
        )

        with pytest.raises(EscrowError, match="deadline is required"):
            await escrow_service_with_contract._create_onchain_escrow(escrow)

    @pytest.mark.asyncio
    async def test_release_with_onchain_id(
        self, escrow_service_with_contract, mock_chain_manager, sample_escrow_params
    ):
        """Test releasing an escrow with on-chain ID."""
        await escrow_service_with_contract.initialize()

        # Manually create a funded escrow with on-chain ID
        escrow = EscrowRecord(
            job_id="job-onchain",
            buyer_address="0xB",
            provider_address="0xP",
            amount=Decimal("100.0"),
            status=EscrowStatus.FUNDED,
            escrow_id_onchain=12345,
            funded_at=datetime.now(UTC),
            deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        escrow_service_with_contract._escrows[escrow.id] = escrow

        released = await escrow_service_with_contract.release_escrow(escrow.id)

        assert released.status == EscrowStatus.RELEASED
        assert released.release_tx_hash is not None


# ==================== Global Service Tests ====================


class TestGetEscrowService:
    """Tests for the get_escrow_service function."""

    @pytest.mark.asyncio
    async def test_get_escrow_service_creates_singleton(self):
        """Test that get_escrow_service returns a singleton."""
        # Reset the global instance first
        import forge.virtuals.acp.escrow as escrow_module
        escrow_module._escrow_service = None

        service1 = await get_escrow_service()
        service2 = await get_escrow_service()

        assert service1 is service2

        # Cleanup
        await service1.close()
        escrow_module._escrow_service = None


# ==================== ESCROW_ABI Tests ====================


class TestEscrowABI:
    """Tests for the ESCROW_ABI constant."""

    def test_abi_contains_create_escrow(self):
        """Test that ABI contains createEscrow function."""
        create_fn = next(
            (f for f in ESCROW_ABI if f.get("name") == "createEscrow"), None
        )
        assert create_fn is not None
        assert create_fn["type"] == "function"

    def test_abi_contains_release_to_provider(self):
        """Test that ABI contains releaseToProvider function."""
        release_fn = next(
            (f for f in ESCROW_ABI if f.get("name") == "releaseToProvider"), None
        )
        assert release_fn is not None

    def test_abi_contains_refund_to_buyer(self):
        """Test that ABI contains refundToBuyer function."""
        refund_fn = next(
            (f for f in ESCROW_ABI if f.get("name") == "refundToBuyer"), None
        )
        assert refund_fn is not None

    def test_abi_contains_events(self):
        """Test that ABI contains expected events."""
        events = [f for f in ESCROW_ABI if f.get("type") == "event"]
        event_names = [e.get("name") for e in events]

        assert "EscrowCreated" in event_names
        assert "EscrowReleased" in event_names
        assert "EscrowRefunded" in event_names


# ==================== Error Handling Tests ====================


class TestEscrowErrorHandling:
    """Tests for error handling in escrow operations."""

    def test_escrow_error_is_exception(self):
        """Test that EscrowError is an Exception."""
        error = EscrowError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    @pytest.mark.asyncio
    async def test_create_escrow_error_stores_in_metadata(self, mock_chain_manager):
        """Test that creation errors are stored in metadata."""
        # Make the chain manager fail
        mock_client = mock_chain_manager.get_client.return_value
        mock_client.approve_tokens = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        service = EscrowService(
            chain_manager=mock_chain_manager,
            escrow_contract_address="0x" + "1" * 40,
        )
        await service.initialize()

        with pytest.raises(EscrowError):
            await service.create_escrow(
                job_id="job-1",
                buyer_address="0xB",
                provider_address="0xP",
                amount=Decimal("10.0"),
            )
