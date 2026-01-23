"""
Tests for Agent Commerce Protocol (ACP) Service

Tests cover:
- Job lifecycle (creation, negotiation, delivery, evaluation)
- Offering management
- Nonce store functionality
- State transitions
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from forge.virtuals.acp.nonce_store import NonceStore
from forge.virtuals.models.acp import (
    ACPDeliverable,
    ACPEvaluation,
    ACPJob,
    ACPJobStatus,
    ACPMemo,
    ACPNegotiationTerms,
    ACPPhase,
    JobOffering,
    PaymentToken,
    TokenPayment,
)


class TestNonceStore:
    """Tests for the nonce store."""

    def test_create_nonce_store(self):
        store = NonceStore()
        assert store is not None

    def test_generate_nonce(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        nonce1 = store.get_next_nonce(wallet)
        nonce2 = store.get_next_nonce(wallet)

        assert nonce1 == 0
        assert nonce2 == 1

    def test_different_wallets_have_separate_nonces(self):
        store = NonceStore()
        wallet1 = "0x1111111111111111111111111111111111111111"
        wallet2 = "0x2222222222222222222222222222222222222222"

        nonce1 = store.get_next_nonce(wallet1)
        nonce2 = store.get_next_nonce(wallet2)

        assert nonce1 == 0
        assert nonce2 == 0  # Each wallet starts at 0

    def test_increment_nonce(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        for expected in range(5):
            nonce = store.get_next_nonce(wallet)
            assert nonce == expected


class TestJobOffering:
    """Tests for job offering model."""

    def test_create_offering(self):
        offering = JobOffering(
            id=str(uuid4()),
            provider_address="0xprovider",
            service_type="knowledge_query",
            description="Knowledge graph queries",
            price_min=Decimal("10.0"),
            price_max=Decimal("100.0"),
            currency=PaymentToken.VIRTUAL,
            capabilities=["cypher", "semantic_search"],
        )

        assert offering.provider_address == "0xprovider"
        assert offering.service_type == "knowledge_query"
        assert offering.price_min == Decimal("10.0")

    def test_offering_price_validation(self):
        """Min price should be <= max price."""
        with pytest.raises(ValueError):
            JobOffering(
                id=str(uuid4()),
                provider_address="0xprovider",
                service_type="test",
                description="Test",
                price_min=Decimal("100.0"),
                price_max=Decimal("10.0"),  # Less than min
                currency=PaymentToken.VIRTUAL,
            )


class TestACPJob:
    """Tests for ACP job model."""

    @pytest.fixture
    def sample_job(self):
        return ACPJob(
            id=str(uuid4()),
            buyer_address="0xbuyer",
            provider_address="0xprovider",
            service_type="knowledge_query",
            phase=ACPPhase.NEGOTIATION,
            status=ACPJobStatus.PENDING,
            payment=TokenPayment(
                token=PaymentToken.VIRTUAL,
                amount=Decimal("50.0"),
            ),
            escrow_amount=Decimal("50.0"),
        )

    def test_job_creation(self, sample_job):
        assert sample_job.buyer_address == "0xbuyer"
        assert sample_job.phase == ACPPhase.NEGOTIATION
        assert sample_job.status == ACPJobStatus.PENDING

    def test_job_phase_transition(self, sample_job):
        """Test valid phase transitions."""
        assert sample_job.phase == ACPPhase.NEGOTIATION

        # Simulate progression
        sample_job.phase = ACPPhase.EXECUTION
        assert sample_job.phase == ACPPhase.EXECUTION

        sample_job.phase = ACPPhase.EVALUATION
        assert sample_job.phase == ACPPhase.EVALUATION

        sample_job.phase = ACPPhase.COMPLETED
        assert sample_job.phase == ACPPhase.COMPLETED

    def test_job_to_dict(self, sample_job):
        """Test serialization."""
        data = sample_job.model_dump()

        assert data["buyer_address"] == "0xbuyer"
        assert data["provider_address"] == "0xprovider"
        assert "phase" in data
        assert "status" in data


class TestACPMemo:
    """Tests for ACP memo model."""

    def test_create_memo(self):
        memo = ACPMemo(
            job_id=str(uuid4()),
            sender_address="0xsender",
            content="Test memo content",
            memo_type="status_update",
        )

        assert memo.content == "Test memo content"
        assert memo.memo_type == "status_update"

    def test_memo_timestamp(self):
        """Memo should have a timestamp."""
        memo = ACPMemo(
            job_id=str(uuid4()),
            sender_address="0xsender",
            content="Test",
        )

        assert memo.created_at is not None


class TestACPNegotiationTerms:
    """Tests for negotiation terms."""

    def test_create_terms(self):
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("75.0"),
            proposed_deadline=datetime.utcnow() + timedelta(hours=24),
            requirements=["Fast response", "High accuracy"],
            acceptance_criteria=["95% accuracy", "Response within 1 hour"],
        )

        assert terms.proposed_price == Decimal("75.0")
        assert len(terms.requirements) == 2

    def test_terms_deadline_in_future(self):
        """Deadline should be in the future."""
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.utcnow() + timedelta(days=7),
        )

        assert terms.proposed_deadline > datetime.utcnow()


class TestACPDeliverable:
    """Tests for deliverable model."""

    def test_create_deliverable(self):
        deliverable = ACPDeliverable(
            job_id=str(uuid4()),
            content_type="application/json",
            content={"result": "test data", "confidence": 0.95},
            metadata={"processing_time_ms": 150},
        )

        assert deliverable.content_type == "application/json"
        assert deliverable.content["confidence"] == 0.95

    def test_deliverable_timestamp(self):
        deliverable = ACPDeliverable(
            job_id=str(uuid4()),
            content_type="text/plain",
            content="Result",
        )

        assert deliverable.submitted_at is not None


class TestACPEvaluation:
    """Tests for evaluation model."""

    def test_create_evaluation(self):
        evaluation = ACPEvaluation(
            job_id=str(uuid4()),
            evaluator_address="0xbuyer",
            rating=4,
            passed=True,
            feedback="Good quality work",
        )

        assert evaluation.rating == 4
        assert evaluation.passed is True

    def test_evaluation_rating_bounds(self):
        """Rating should be 1-5."""
        # Valid rating
        eval1 = ACPEvaluation(
            job_id=str(uuid4()),
            evaluator_address="0xbuyer",
            rating=5,
            passed=True,
        )
        assert eval1.rating == 5

        # Rating validation (if implemented)
        with pytest.raises(ValueError):
            ACPEvaluation(
                job_id=str(uuid4()),
                evaluator_address="0xbuyer",
                rating=6,  # Out of bounds
                passed=True,
            )


class TestJobLifecycle:
    """Tests for complete job lifecycle."""

    def test_job_lifecycle_happy_path(self):
        """Test a complete successful job lifecycle."""
        # 1. Create job
        job = ACPJob(
            id=str(uuid4()),
            buyer_address="0xbuyer",
            provider_address="0xprovider",
            service_type="knowledge_query",
            phase=ACPPhase.NEGOTIATION,
            status=ACPJobStatus.PENDING,
            payment=TokenPayment(
                token=PaymentToken.VIRTUAL,
                amount=Decimal("50.0"),
            ),
            escrow_amount=Decimal("50.0"),
        )
        assert job.phase == ACPPhase.NEGOTIATION

        # 2. Terms agreed
        job.phase = ACPPhase.EXECUTION
        job.status = ACPJobStatus.IN_PROGRESS
        assert job.status == ACPJobStatus.IN_PROGRESS

        # 3. Delivery
        job.phase = ACPPhase.EVALUATION
        assert job.phase == ACPPhase.EVALUATION

        # 4. Evaluation passed
        job.phase = ACPPhase.COMPLETED
        job.status = ACPJobStatus.COMPLETED
        assert job.status == ACPJobStatus.COMPLETED

    def test_job_cancellation(self):
        """Test job cancellation."""
        job = ACPJob(
            id=str(uuid4()),
            buyer_address="0xbuyer",
            provider_address="0xprovider",
            service_type="test",
            phase=ACPPhase.NEGOTIATION,
            status=ACPJobStatus.PENDING,
            payment=TokenPayment(
                token=PaymentToken.VIRTUAL,
                amount=Decimal("50.0"),
            ),
        )

        # Cancel the job
        job.status = ACPJobStatus.CANCELLED
        assert job.status == ACPJobStatus.CANCELLED

    def test_job_dispute(self):
        """Test job dispute."""
        job = ACPJob(
            id=str(uuid4()),
            buyer_address="0xbuyer",
            provider_address="0xprovider",
            service_type="test",
            phase=ACPPhase.EVALUATION,
            status=ACPJobStatus.IN_PROGRESS,
            payment=TokenPayment(
                token=PaymentToken.VIRTUAL,
                amount=Decimal("50.0"),
            ),
        )

        # File dispute
        job.phase = ACPPhase.DISPUTE
        job.status = ACPJobStatus.DISPUTED
        assert job.phase == ACPPhase.DISPUTE
        assert job.status == ACPJobStatus.DISPUTED
