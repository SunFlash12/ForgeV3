"""
Tests for Agent Commerce Protocol (ACP) Models.

This module tests the data structures for implementing Virtuals Protocol's
Agent Commerce Protocol within Forge.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from forge.virtuals.models.acp import (
    ACPDeliverable,
    ACPDispute,
    ACPEvaluation,
    ACPJob,
    ACPJobCreate,
    ACPMemo,
    ACPNegotiationTerms,
    ACPRegistryEntry,
    ACPStats,
    JobOffering,
    PaymentToken,
    TokenPayment,
)
from forge.virtuals.models.base import ACPJobStatus, ACPPhase


# ==================== PaymentToken Tests ====================


class TestPaymentToken:
    """Tests for PaymentToken enum."""

    def test_virtual_token_properties(self):
        """Test VIRTUAL token properties."""
        token = PaymentToken.VIRTUAL

        assert token.chain == "base"
        assert token.decimals == 18
        assert token.default_address == "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"
        assert "VIRTUAL" in token.display_name

    def test_frowg_token_properties(self):
        """Test FROWG token properties."""
        token = PaymentToken.FROWG

        assert token.chain == "solana"
        assert token.decimals == 9
        assert token.default_address == "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump"
        assert "FROWG" in token.display_name

    def test_all_payment_tokens(self):
        """Test all payment token enum values."""
        assert PaymentToken.VIRTUAL.value == "VIRTUAL"
        assert PaymentToken.FROWG.value == "FROWG"


# ==================== TokenPayment Tests ====================


class TestTokenPayment:
    """Tests for TokenPayment model."""

    def test_default_payment(self):
        """Test default payment values."""
        payment = TokenPayment(amount=100.0)

        assert payment.token == PaymentToken.VIRTUAL
        assert payment.amount == 100.0
        assert payment.chain == "base"
        assert payment.exchange_rate_to_virtual == 1.0

    def test_frowg_payment(self):
        """Test FROWG payment."""
        payment = TokenPayment(
            token=PaymentToken.FROWG,
            amount=1000.0,
            chain="solana",
            exchange_rate_to_virtual=0.1,
        )

        assert payment.token == PaymentToken.FROWG
        assert payment.amount == 1000.0

    def test_to_virtual_equivalent(self):
        """Test conversion to VIRTUAL equivalent."""
        payment = TokenPayment(
            token=PaymentToken.FROWG,
            amount=1000.0,
            exchange_rate_to_virtual=0.1,
        )

        assert payment.to_virtual_equivalent() == 100.0

    def test_amount_validation(self):
        """Test that negative amount is rejected."""
        with pytest.raises(ValidationError):
            TokenPayment(amount=-10.0)


# ==================== JobOffering Tests ====================


class TestJobOffering:
    """Tests for JobOffering model."""

    def test_offering_creation(self):
        """Test creating a job offering."""
        offering = JobOffering(
            provider_agent_id="agent-123",
            provider_wallet="0x" + "1" * 40,
            service_type="knowledge_query",
            title="Knowledge Query Service",
            description="Query knowledge capsules for information",
            base_fee_virtual=0.01,
        )

        assert offering.provider_agent_id == "agent-123"
        assert offering.service_type == "knowledge_query"
        assert offering.base_fee_virtual == 0.01
        assert offering.is_active is True

    def test_offering_defaults(self):
        """Test default values for job offering."""
        offering = JobOffering(
            provider_agent_id="agent-123",
            provider_wallet="0x" + "1" * 40,
            service_type="analysis",
            title="Analysis Service",
            description="Analyze data",
            base_fee_virtual=1.0,
        )

        assert offering.fee_per_unit == 0.0
        assert offering.max_execution_time_seconds == 300
        assert offering.requires_escrow is True
        assert offering.min_buyer_trust_score == 0.0
        assert offering.available_capacity == 100
        assert PaymentToken.VIRTUAL in offering.accepted_tokens

    def test_offering_with_multi_token(self):
        """Test offering with multiple payment tokens."""
        offering = JobOffering(
            provider_agent_id="agent-123",
            provider_wallet="0x" + "1" * 40,
            service_type="generation",
            title="Content Generation",
            description="Generate content",
            base_fee_virtual=5.0,
            accepted_tokens=[PaymentToken.VIRTUAL, PaymentToken.FROWG],
            frowg_fee_equivalent=50.0,
        )

        assert len(offering.accepted_tokens) == 2
        assert offering.frowg_fee_equivalent == 50.0

    def test_offering_title_max_length(self):
        """Test title max length validation."""
        with pytest.raises(ValidationError):
            JobOffering(
                provider_agent_id="agent-123",
                provider_wallet="0x" + "1" * 40,
                service_type="test",
                title="X" * 201,  # Exceeds 200 char limit
                description="Test",
                base_fee_virtual=1.0,
            )


# ==================== ACPMemo Tests ====================


class TestACPMemo:
    """Tests for ACPMemo model."""

    def test_memo_creation(self):
        """Test creating an ACP memo."""
        memo = ACPMemo(
            memo_type="request",
            job_id="job-123",
            content={"query": "test query"},
            content_hash="abc123",
            nonce=1,
            sender_address="0x" + "1" * 40,
            sender_signature="sig123",
        )

        assert memo.memo_type == "request"
        assert memo.job_id == "job-123"
        assert memo.nonce == 1
        assert memo.is_on_chain is False

    def test_memo_with_on_chain_state(self):
        """Test memo with on-chain state."""
        memo = ACPMemo(
            memo_type="agreement",
            job_id="job-456",
            content={"agreed_fee": 100},
            content_hash="def456",
            nonce=2,
            sender_address="0x" + "2" * 40,
            sender_signature="sig456",
            tx_hash="0x" + "a" * 64,
            block_number=12345,
            is_on_chain=True,
        )

        assert memo.is_on_chain is True
        assert memo.tx_hash is not None
        assert memo.block_number == 12345


# ==================== ACPJob Tests ====================


class TestACPJob:
    """Tests for ACPJob model."""

    def test_job_creation(self):
        """Test creating an ACP job."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer-agent",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider-agent",
            provider_wallet="0x" + "2" * 40,
        )

        assert job.current_phase == ACPPhase.REQUEST
        assert job.status == ACPJobStatus.OPEN
        assert job.is_disputed is False

    def test_advance_to_phase_valid(self):
        """Test advancing to valid next phase."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider",
            provider_wallet="0x" + "2" * 40,
        )

        job.advance_to_phase(ACPPhase.NEGOTIATION)

        assert job.current_phase == ACPPhase.NEGOTIATION

    def test_advance_to_phase_invalid(self):
        """Test advancing to invalid phase raises error."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider",
            provider_wallet="0x" + "2" * 40,
        )

        with pytest.raises(ValueError, match="Cannot advance"):
            job.advance_to_phase(ACPPhase.EVALUATION)  # Skip phases

    def test_is_timed_out_request_phase(self):
        """Test timeout check in request phase."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider",
            provider_wallet="0x" + "2" * 40,
            request_timeout=datetime.now(UTC) - timedelta(hours=1),
        )

        assert job.is_timed_out() is True

    def test_is_timed_out_not_expired(self):
        """Test timeout check when not expired."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider",
            provider_wallet="0x" + "2" * 40,
            request_timeout=datetime.now(UTC) + timedelta(hours=24),
        )

        assert job.is_timed_out() is False

    def test_job_with_payment_token(self):
        """Test job with specific payment token."""
        job = ACPJob(
            job_offering_id="offering-123",
            buyer_agent_id="buyer",
            buyer_wallet="0x" + "1" * 40,
            provider_agent_id="provider",
            provider_wallet="0x" + "2" * 40,
            payment_token=PaymentToken.FROWG,
            payment_amount=1000.0,
            payment_chain="solana",
        )

        assert job.payment_token == PaymentToken.FROWG
        assert job.payment_amount == 1000.0


# ==================== ACPJobCreate Tests ====================


class TestACPJobCreate:
    """Tests for ACPJobCreate model."""

    def test_job_create_minimal(self):
        """Test creating job with minimal fields."""
        create = ACPJobCreate(
            job_offering_id="offering-123",
            buyer_agent_id="buyer-agent",
            requirements="Test requirements",
            max_fee_virtual=100.0,
        )

        assert create.job_offering_id == "offering-123"
        assert create.payment_token == PaymentToken.VIRTUAL

    def test_job_create_with_frowg(self):
        """Test creating job with FROWG payment."""
        create = ACPJobCreate(
            job_offering_id="offering-123",
            buyer_agent_id="buyer-agent",
            requirements="Test requirements",
            max_fee_virtual=100.0,
            payment_token=PaymentToken.FROWG,
            max_fee_in_token=1000.0,
        )

        assert create.payment_token == PaymentToken.FROWG
        assert create.max_fee_in_token == 1000.0

    def test_job_create_requirements_max_length(self):
        """Test requirements max length validation."""
        with pytest.raises(ValidationError):
            ACPJobCreate(
                job_offering_id="offering-123",
                buyer_agent_id="buyer-agent",
                requirements="X" * 5001,  # Exceeds 5000 char limit
                max_fee_virtual=100.0,
            )


# ==================== ACPNegotiationTerms Tests ====================


class TestACPNegotiationTerms:
    """Tests for ACPNegotiationTerms model."""

    def test_negotiation_terms(self):
        """Test creating negotiation terms."""
        terms = ACPNegotiationTerms(
            job_id="job-123",
            proposed_fee_virtual=50.0,
            proposed_deadline=datetime.now(UTC) + timedelta(days=7),
            deliverable_format="json",
            deliverable_description="Analysis results in JSON format",
        )

        assert terms.proposed_fee_virtual == 50.0
        assert terms.requires_evaluator is False

    def test_negotiation_terms_with_evaluator(self):
        """Test negotiation terms with evaluator."""
        terms = ACPNegotiationTerms(
            job_id="job-123",
            proposed_fee_virtual=100.0,
            proposed_deadline=datetime.now(UTC) + timedelta(days=7),
            deliverable_format="text",
            deliverable_description="Written report",
            requires_evaluator=True,
            suggested_evaluator_id="evaluator-agent",
        )

        assert terms.requires_evaluator is True
        assert terms.suggested_evaluator_id == "evaluator-agent"


# ==================== ACPDeliverable Tests ====================


class TestACPDeliverable:
    """Tests for ACPDeliverable model."""

    def test_deliverable_creation(self):
        """Test creating a deliverable."""
        deliverable = ACPDeliverable(
            job_id="job-123",
            content_type="json",
            content={"result": "analysis data"},
        )

        assert deliverable.content_type == "json"
        assert deliverable.notes == ""

    def test_deliverable_with_notes(self):
        """Test deliverable with notes."""
        deliverable = ACPDeliverable(
            job_id="job-123",
            content_type="url",
            content={"url": "https://example.com/result"},
            notes="Download available for 24 hours",
        )

        assert deliverable.notes == "Download available for 24 hours"


# ==================== ACPEvaluation Tests ====================


class TestACPEvaluation:
    """Tests for ACPEvaluation model."""

    def test_evaluation_approved(self):
        """Test approved evaluation."""
        evaluation = ACPEvaluation(
            job_id="job-123",
            evaluator_agent_id="evaluator-agent",
            result="approved",
            score=0.95,
            feedback="Excellent work, all requirements met.",
            met_requirements=["req1", "req2", "req3"],
        )

        assert evaluation.result == "approved"
        assert evaluation.score == 0.95
        assert len(evaluation.met_requirements) == 3

    def test_evaluation_rejected(self):
        """Test rejected evaluation."""
        evaluation = ACPEvaluation(
            job_id="job-123",
            evaluator_agent_id="evaluator-agent",
            result="rejected",
            score=0.3,
            feedback="Does not meet requirements.",
            unmet_requirements=["req2", "req3"],
            suggested_improvements=["Improve accuracy", "Add more details"],
        )

        assert evaluation.result == "rejected"
        assert len(evaluation.unmet_requirements) == 2
        assert len(evaluation.suggested_improvements) == 2

    def test_evaluation_score_validation(self):
        """Test score validation (0.0 to 1.0)."""
        with pytest.raises(ValidationError):
            ACPEvaluation(
                job_id="job-123",
                evaluator_agent_id="evaluator",
                result="approved",
                score=1.5,  # Invalid, exceeds 1.0
                feedback="Test",
            )


# ==================== ACPDispute Tests ====================


class TestACPDispute:
    """Tests for ACPDispute model."""

    def test_dispute_creation(self):
        """Test creating a dispute."""
        dispute = ACPDispute(
            job_id="job-123",
            filed_by="buyer",
            reason="Deliverable does not match agreed requirements",
            requested_resolution="full_refund",
        )

        assert dispute.filed_by == "buyer"
        assert dispute.requested_resolution == "full_refund"

    def test_dispute_with_evidence(self):
        """Test dispute with evidence."""
        dispute = ACPDispute(
            job_id="job-123",
            filed_by="provider",
            reason="Buyer refuses to approve valid deliverable",
            evidence=[
                {"type": "screenshot", "url": "https://example.com/evidence1"},
                {"type": "message_log", "content": "Chat history"},
            ],
            requested_resolution="arbitration",
        )

        assert len(dispute.evidence) == 2


# ==================== ACPRegistryEntry Tests ====================


class TestACPRegistryEntry:
    """Tests for ACPRegistryEntry model."""

    def test_registry_entry_creation(self):
        """Test creating a registry entry."""
        entry = ACPRegistryEntry(
            id="entry-123",
            agent_id="agent-123",
            wallet_address="0x" + "1" * 40,
        )

        assert entry.total_jobs_completed == 0
        assert entry.average_rating == 0.0
        assert entry.reputation_score == 0.5
        assert entry.is_verified is False

    def test_registry_entry_with_offerings(self):
        """Test registry entry with offerings."""
        offering = JobOffering(
            provider_agent_id="agent-123",
            provider_wallet="0x" + "1" * 40,
            service_type="analysis",
            title="Analysis Service",
            description="Analyze data",
            base_fee_virtual=1.0,
        )

        entry = ACPRegistryEntry(
            id="entry-123",
            agent_id="agent-123",
            wallet_address="0x" + "1" * 40,
            offerings=[offering],
            total_jobs_completed=50,
            average_rating=4.5,
            reputation_score=0.85,
            is_verified=True,
        )

        assert len(entry.offerings) == 1
        assert entry.is_verified is True


# ==================== ACPStats Tests ====================


class TestACPStats:
    """Tests for ACPStats model."""

    def test_stats_creation(self):
        """Test creating ACP stats."""
        now = datetime.now(UTC)
        stats = ACPStats(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_jobs_created=100,
            total_jobs_completed=85,
            total_jobs_disputed=5,
            total_volume_virtual=50000.0,
            total_volume_frowg=100000.0,
        )

        assert stats.total_jobs_created == 100
        assert stats.total_jobs_completed == 85
        assert stats.total_volume_frowg == 100000.0

    def test_stats_volume_by_token(self):
        """Test stats with volume by token."""
        now = datetime.now(UTC)
        stats = ACPStats(
            period_start=now - timedelta(days=7),
            period_end=now,
            volume_by_token={"VIRTUAL": 10000.0, "FROWG": 50000.0},
            jobs_by_token={"VIRTUAL": 50, "FROWG": 25},
        )

        assert stats.volume_by_token["VIRTUAL"] == 10000.0
        assert stats.jobs_by_token["FROWG"] == 25
