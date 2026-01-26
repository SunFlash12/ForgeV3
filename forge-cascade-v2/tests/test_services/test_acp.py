"""
Tests for Agent Commerce Protocol (ACP) Service

Tests cover:
- Job lifecycle (creation, negotiation, delivery, evaluation)
- Offering management
- Nonce store functionality
- State transitions
"""

from datetime import datetime, timedelta
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
)


class TestNonceStore:
    """Tests for the nonce store."""

    def test_create_nonce_store(self):
        store = NonceStore()
        assert store is not None

    @pytest.mark.asyncio
    async def test_get_highest_nonce_default(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        nonce = await store.get_highest_nonce(wallet)
        assert nonce == 0

    @pytest.mark.asyncio
    async def test_update_and_get_nonce(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        updated = await store.update_nonce(wallet, 1)
        assert updated is True

        nonce = await store.get_highest_nonce(wallet)
        assert nonce == 1

    @pytest.mark.asyncio
    async def test_different_wallets_have_separate_nonces(self):
        store = NonceStore()
        wallet1 = "0x1111111111111111111111111111111111111111"
        wallet2 = "0x2222222222222222222222222222222222222222"

        await store.update_nonce(wallet1, 5)
        await store.update_nonce(wallet2, 10)

        nonce1 = await store.get_highest_nonce(wallet1)
        nonce2 = await store.get_highest_nonce(wallet2)

        assert nonce1 == 5
        assert nonce2 == 10

    @pytest.mark.asyncio
    async def test_nonce_only_increases(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        await store.update_nonce(wallet, 5)
        result = await store.update_nonce(wallet, 3)  # Lower nonce
        assert result is False

        nonce = await store.get_highest_nonce(wallet)
        assert nonce == 5  # Should still be 5

    @pytest.mark.asyncio
    async def test_verify_and_consume_nonce(self):
        store = NonceStore()
        wallet = "0x1234567890abcdef1234567890abcdef12345678"

        valid, msg = await store.verify_and_consume_nonce(wallet, 1)
        assert valid is True
        assert msg == ""

        # Replay should fail
        valid, msg = await store.verify_and_consume_nonce(wallet, 1)
        assert valid is False
        assert "replay" in msg.lower() or "not greater" in msg.lower()


class TestJobOffering:
    """Tests for job offering model."""

    def test_create_offering(self):
        offering = JobOffering(
            id=str(uuid4()),
            provider_agent_id="agent-001",
            provider_wallet="0xprovider",
            service_type="knowledge_query",
            title="Knowledge Graph Queries",
            description="Knowledge graph queries",
            base_fee_virtual=10.0,
            accepted_tokens=[PaymentToken.VIRTUAL],
        )

        assert offering.provider_wallet == "0xprovider"
        assert offering.service_type == "knowledge_query"
        assert offering.base_fee_virtual == 10.0

    def test_offering_defaults(self):
        """Test that offerings have sensible defaults."""
        offering = JobOffering(
            provider_agent_id="agent-001",
            provider_wallet="0xprovider",
            service_type="test",
            title="Test Service",
            description="Test description",
            base_fee_virtual=5.0,
        )

        assert offering.is_active is True
        assert offering.requires_escrow is True
        assert offering.max_execution_time_seconds == 300
        assert PaymentToken.VIRTUAL in offering.accepted_tokens


class TestACPJob:
    """Tests for ACP job model."""

    @pytest.fixture
    def sample_job(self):
        return ACPJob(
            id=str(uuid4()),
            buyer_agent_id="buyer-agent-001",
            buyer_wallet="0xbuyer",
            provider_agent_id="provider-agent-001",
            provider_wallet="0xprovider",
            job_offering_id=str(uuid4()),
            current_phase=ACPPhase.NEGOTIATION,
            status=ACPJobStatus.NEGOTIATING,
            payment_token=PaymentToken.VIRTUAL,
            payment_amount=50.0,
            escrow_amount_virtual=50.0,
            requirements="Knowledge query with high accuracy",
        )

    def test_job_creation(self, sample_job):
        assert sample_job.buyer_wallet == "0xbuyer"
        assert sample_job.current_phase == ACPPhase.NEGOTIATION
        assert sample_job.status == ACPJobStatus.NEGOTIATING

    def test_job_phase_transition(self, sample_job):
        """Test valid phase transitions using advance_to_phase."""
        assert sample_job.current_phase == ACPPhase.NEGOTIATION

        # Advance to TRANSACTION phase
        sample_job.advance_to_phase(ACPPhase.TRANSACTION)
        assert sample_job.current_phase == ACPPhase.TRANSACTION

        # Advance to EVALUATION phase
        sample_job.advance_to_phase(ACPPhase.EVALUATION)
        assert sample_job.current_phase == ACPPhase.EVALUATION

    def test_job_invalid_phase_skip(self, sample_job):
        """Test that skipping phases raises an error."""
        assert sample_job.current_phase == ACPPhase.NEGOTIATION

        with pytest.raises(ValueError):
            sample_job.advance_to_phase(ACPPhase.EVALUATION)  # Skip TRANSACTION

    def test_job_to_dict(self, sample_job):
        """Test serialization."""
        data = sample_job.model_dump()

        assert data["buyer_wallet"] == "0xbuyer"
        assert data["provider_wallet"] == "0xprovider"
        assert "current_phase" in data
        assert "status" in data


class TestACPMemo:
    """Tests for ACP memo model."""

    def test_create_memo(self):
        memo = ACPMemo(
            job_id=str(uuid4()),
            sender_address="0xsender",
            content={"message": "Test memo content"},
            content_hash="abc123hash",
            memo_type="status_update",
            nonce=1,
            sender_signature="0xsig123",
        )

        assert memo.content["message"] == "Test memo content"
        assert memo.memo_type == "status_update"

    def test_memo_timestamp(self):
        """Memo should have a timestamp."""
        memo = ACPMemo(
            job_id=str(uuid4()),
            sender_address="0xsender",
            content={"message": "Test"},
            content_hash="hash123",
            memo_type="request",
            nonce=0,
            sender_signature="0xsig",
        )

        assert memo.created_at is not None


class TestACPNegotiationTerms:
    """Tests for negotiation terms."""

    def test_create_terms(self):
        terms = ACPNegotiationTerms(
            job_id=str(uuid4()),
            proposed_fee_virtual=75.0,
            proposed_deadline=datetime.utcnow() + timedelta(hours=24),
            deliverable_format="json",
            deliverable_description="Structured knowledge graph query results with confidence scores",
        )

        assert terms.proposed_fee_virtual == 75.0
        assert terms.deliverable_format == "json"

    def test_terms_deadline_in_future(self):
        """Deadline should be in the future."""
        terms = ACPNegotiationTerms(
            job_id=str(uuid4()),
            proposed_fee_virtual=50.0,
            proposed_deadline=datetime.utcnow() + timedelta(days=7),
            deliverable_format="text",
            deliverable_description="Plain text analysis report",
        )

        assert terms.proposed_deadline > datetime.utcnow()

    def test_terms_with_special_conditions(self):
        """Test terms with optional fields."""
        terms = ACPNegotiationTerms(
            job_id=str(uuid4()),
            proposed_fee_virtual=100.0,
            proposed_deadline=datetime.utcnow() + timedelta(hours=48),
            deliverable_format="json",
            deliverable_description="Full analysis with visualizations",
            special_conditions=["Priority processing", "Extended support"],
            requires_evaluator=True,
            suggested_evaluator_id="evaluator-agent-001",
        )

        assert len(terms.special_conditions) == 2
        assert terms.requires_evaluator is True


class TestACPDeliverable:
    """Tests for deliverable model."""

    def test_create_deliverable(self):
        deliverable = ACPDeliverable(
            job_id=str(uuid4()),
            content_type="json",
            content={"result": "test data", "confidence": 0.95},
            notes="Processing completed in 150ms",
        )

        assert deliverable.content_type == "json"
        assert deliverable.content["confidence"] == 0.95

    def test_deliverable_with_default_notes(self):
        deliverable = ACPDeliverable(
            job_id=str(uuid4()),
            content_type="text",
            content={"text": "Result"},
        )

        assert deliverable.notes == ""


class TestACPEvaluation:
    """Tests for evaluation model."""

    def test_create_evaluation(self):
        evaluation = ACPEvaluation(
            job_id=str(uuid4()),
            evaluator_agent_id="buyer-agent-001",
            result="approved",
            score=0.85,
            feedback="Good quality work",
        )

        assert evaluation.score == 0.85
        assert evaluation.result == "approved"

    def test_evaluation_score_bounds(self):
        """Score should be 0.0 to 1.0."""
        # Valid score
        eval1 = ACPEvaluation(
            job_id=str(uuid4()),
            evaluator_agent_id="buyer-agent-001",
            result="approved",
            score=1.0,
            feedback="Perfect work",
        )
        assert eval1.score == 1.0

        # Score out of bounds (> 1.0)
        with pytest.raises(ValueError):
            ACPEvaluation(
                job_id=str(uuid4()),
                evaluator_agent_id="buyer-agent-001",
                result="approved",
                score=1.5,  # Out of bounds
                feedback="Invalid score",
            )

    def test_evaluation_rejection(self):
        """Test a rejected evaluation."""
        evaluation = ACPEvaluation(
            job_id=str(uuid4()),
            evaluator_agent_id="buyer-agent-001",
            result="rejected",
            score=0.2,
            feedback="Did not meet accuracy requirements",
            unmet_requirements=["95% accuracy", "Response within 1 hour"],
        )

        assert evaluation.result == "rejected"
        assert len(evaluation.unmet_requirements) == 2


class TestJobLifecycle:
    """Tests for complete job lifecycle."""

    def test_job_lifecycle_happy_path(self):
        """Test a complete successful job lifecycle."""
        # 1. Create job in REQUEST phase
        job = ACPJob(
            id=str(uuid4()),
            buyer_agent_id="buyer-agent-001",
            buyer_wallet="0xbuyer",
            provider_agent_id="provider-agent-001",
            provider_wallet="0xprovider",
            job_offering_id=str(uuid4()),
            current_phase=ACPPhase.REQUEST,
            status=ACPJobStatus.OPEN,
            requirements="Knowledge query",
        )
        assert job.current_phase == ACPPhase.REQUEST

        # 2. Advance to negotiation
        job.advance_to_phase(ACPPhase.NEGOTIATION)
        job.status = ACPJobStatus.NEGOTIATING
        assert job.status == ACPJobStatus.NEGOTIATING

        # 3. Terms agreed, advance to transaction
        job.advance_to_phase(ACPPhase.TRANSACTION)
        job.status = ACPJobStatus.IN_PROGRESS
        assert job.status == ACPJobStatus.IN_PROGRESS

        # 4. Delivery and evaluation
        job.advance_to_phase(ACPPhase.EVALUATION)
        job.status = ACPJobStatus.EVALUATING
        assert job.status == ACPJobStatus.EVALUATING

        # 5. Evaluation passed
        job.status = ACPJobStatus.COMPLETED
        assert job.status == ACPJobStatus.COMPLETED

    def test_job_cancellation(self):
        """Test job cancellation."""
        job = ACPJob(
            id=str(uuid4()),
            buyer_agent_id="buyer-agent-001",
            buyer_wallet="0xbuyer",
            provider_agent_id="provider-agent-001",
            provider_wallet="0xprovider",
            job_offering_id=str(uuid4()),
            current_phase=ACPPhase.NEGOTIATION,
            status=ACPJobStatus.NEGOTIATING,
        )

        # Cancel the job
        job.status = ACPJobStatus.CANCELLED
        assert job.status == ACPJobStatus.CANCELLED

    def test_job_dispute(self):
        """Test job dispute."""
        job = ACPJob(
            id=str(uuid4()),
            buyer_agent_id="buyer-agent-001",
            buyer_wallet="0xbuyer",
            provider_agent_id="provider-agent-001",
            provider_wallet="0xprovider",
            job_offering_id=str(uuid4()),
            current_phase=ACPPhase.EVALUATION,
            status=ACPJobStatus.EVALUATING,
        )

        # File dispute
        job.is_disputed = True
        job.dispute_reason = "Deliverable does not meet requirements"
        job.status = ACPJobStatus.DISPUTED
        assert job.current_phase == ACPPhase.EVALUATION
        assert job.status == ACPJobStatus.DISPUTED
        assert job.is_disputed is True
