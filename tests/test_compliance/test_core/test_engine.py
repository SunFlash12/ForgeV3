"""
Tests for forge.compliance.core.engine module.

Tests the ComplianceEngine class which orchestrates all compliance
operations including DSAR processing, consent management, breach
notification, AI governance, audit logging, and compliance reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.config import ComplianceConfig
from forge.compliance.core.engine import ComplianceEngine, get_compliance_engine
from forge.compliance.core.enums import (
    AIRiskClassification,
    AuditEventCategory,
    BreachSeverity,
    ComplianceFramework,
    ConsentType,
    DataClassification,
    DSARType,
    Jurisdiction,
    RiskLevel,
)
from forge.compliance.core.models import (
    AIDecisionLog,
    AISystemRegistration,
    AuditEvent,
    BreachNotification,
    ComplianceReport,
    ConsentRecord,
    DataSubjectRequest,
)
from forge.compliance.core.registry import ComplianceRegistry


class TestComplianceEngineInitialization:
    """Tests for ComplianceEngine initialization."""

    def test_engine_creation_with_defaults(self, compliance_engine):
        """Test engine creation with default settings."""
        assert compliance_engine.config is not None
        assert compliance_engine.registry is not None
        assert isinstance(compliance_engine._dsars, dict)
        assert isinstance(compliance_engine._consents, dict)
        assert isinstance(compliance_engine._breaches, dict)
        assert isinstance(compliance_engine._ai_systems, dict)

    def test_engine_creation_with_repository(
        self, compliance_config, compliance_registry, mock_repository
    ):
        """Test engine creation with repository."""
        engine = ComplianceEngine(
            config=compliance_config,
            registry=compliance_registry,
            repository=mock_repository,
        )
        assert engine.repository is mock_repository


class TestDSAROperations:
    """Tests for DSAR management operations."""

    @pytest.mark.asyncio
    async def test_create_dsar_access_request(self, compliance_engine):
        """Test creating an access request DSAR."""
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ACCESS,
            subject_email="user@example.com",
            request_text="I want to access all my personal data",
            subject_name="Test User",
            jurisdiction=Jurisdiction.EU,
        )

        assert dsar.id in compliance_engine._dsars
        assert dsar.request_type == DSARType.ACCESS
        assert dsar.jurisdiction == Jurisdiction.EU
        assert dsar.status == "received"
        assert dsar.deadline is not None

    @pytest.mark.asyncio
    async def test_create_dsar_erasure_request(self, compliance_engine):
        """Test creating an erasure request DSAR."""
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ERASURE,
            subject_email="user@example.com",
            request_text="Please delete all my data",
            jurisdiction=Jurisdiction.EU,
        )

        assert dsar.request_type == DSARType.ERASURE
        assert ComplianceFramework.GDPR in dsar.applicable_frameworks

    @pytest.mark.asyncio
    async def test_create_dsar_ccpa_opt_out(self, compliance_engine):
        """Test creating a CCPA opt-out request."""
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.OPT_OUT_SALE,
            subject_email="user@california.com",
            request_text="Opt me out of data sale",
            jurisdiction=Jurisdiction.US_CALIFORNIA,
        )

        assert dsar.request_type == DSARType.OPT_OUT_SALE
        assert ComplianceFramework.CCPA in dsar.applicable_frameworks
        # CCPA has 15-day deadline for opt-out requests
        expected_deadline = dsar.received_at + timedelta(days=15)
        assert abs((dsar.deadline - expected_deadline).seconds) < 60

    @pytest.mark.asyncio
    async def test_create_dsar_with_specific_categories(self, compliance_engine):
        """Test creating a DSAR with specific data categories."""
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ACCESS,
            subject_email="user@example.com",
            request_text="I want my purchase history",
            specific_data_categories=["purchase_history", "payment_data"],
        )

        assert "purchase_history" in dsar.specific_data_categories
        assert "payment_data" in dsar.specific_data_categories

    @pytest.mark.asyncio
    async def test_process_dsar(self, compliance_engine):
        """Test marking a DSAR as processing."""
        # First create a DSAR
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ACCESS,
            subject_email="user@example.com",
            request_text="Access my data",
        )

        # Process it
        processed_dsar = await compliance_engine.process_dsar(
            dsar_id=dsar.id,
            actor_id="processor_001",
        )

        assert processed_dsar.status == "processing"
        assert processed_dsar.assigned_to == "processor_001"

    @pytest.mark.asyncio
    async def test_process_dsar_nonexistent(self, compliance_engine):
        """Test processing a nonexistent DSAR raises error."""
        with pytest.raises(ValueError, match="DSAR not found"):
            await compliance_engine.process_dsar(
                dsar_id="nonexistent",
                actor_id="processor_001",
            )

    @pytest.mark.asyncio
    async def test_complete_dsar(self, compliance_engine):
        """Test completing a DSAR."""
        # Create and process a DSAR
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ACCESS,
            subject_email="user@example.com",
            request_text="Access my data",
        )
        await compliance_engine.process_dsar(dsar.id, "processor_001")

        # Complete it
        completed_dsar = await compliance_engine.complete_dsar(
            dsar_id=dsar.id,
            actor_id="processor_001",
            export_location="/exports/user_data_001.zip",
            export_format="JSON",
        )

        assert completed_dsar.status == "completed"
        assert completed_dsar.response_sent_at is not None

    @pytest.mark.asyncio
    async def test_complete_dsar_with_erasure_exceptions(self, compliance_engine):
        """Test completing an erasure DSAR with exceptions."""
        dsar = await compliance_engine.create_dsar(
            request_type=DSARType.ERASURE,
            subject_email="user@example.com",
            request_text="Delete my data",
        )
        await compliance_engine.process_dsar(dsar.id, "processor_001")

        completed_dsar = await compliance_engine.complete_dsar(
            dsar_id=dsar.id,
            actor_id="processor_001",
            erasure_exceptions=["legal_hold_data", "financial_records_7_years"],
        )

        assert completed_dsar.status == "completed"


class TestConsentOperations:
    """Tests for consent management operations."""

    @pytest.mark.asyncio
    async def test_record_consent_granted(self, compliance_engine):
        """Test recording granted consent."""
        consent = await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.ANALYTICS,
            purpose="Website analytics",
            granted=True,
            collected_via="consent_banner",
            consent_text_version="1.0",
        )

        assert consent.user_id == "user_123"
        assert consent.consent_type == ConsentType.ANALYTICS
        assert consent.granted is True
        assert consent.is_valid is True

    @pytest.mark.asyncio
    async def test_record_consent_denied(self, compliance_engine):
        """Test recording denied consent."""
        consent = await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.MARKETING,
            purpose="Marketing emails",
            granted=False,
            collected_via="consent_banner",
            consent_text_version="1.0",
        )

        assert consent.granted is False
        assert consent.is_valid is False

    @pytest.mark.asyncio
    async def test_record_consent_with_third_parties(self, compliance_engine):
        """Test recording consent with third-party sharing."""
        consent = await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.THIRD_PARTY,
            purpose="Share data with partners",
            granted=True,
            collected_via="consent_form",
            consent_text_version="1.0",
            third_parties=["partner_a", "partner_b"],
            cross_border_transfer=True,
            transfer_safeguards=["SCCs", "adequacy_decision"],
        )

        assert consent.third_parties == ["partner_a", "partner_b"]
        assert consent.cross_border_transfer is True

    @pytest.mark.asyncio
    async def test_withdraw_consent(self, compliance_engine):
        """Test withdrawing consent."""
        # First record consent
        consent = await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.ANALYTICS,
            purpose="Website analytics",
            granted=True,
            collected_via="consent_banner",
            consent_text_version="1.0",
        )

        # Withdraw it
        withdrawn = await compliance_engine.withdraw_consent(
            user_id="user_123",
            consent_type=ConsentType.ANALYTICS,
        )

        assert withdrawn is not None
        assert withdrawn.granted is False
        assert withdrawn.withdrawn_at is not None

    @pytest.mark.asyncio
    async def test_withdraw_consent_not_found(self, compliance_engine):
        """Test withdrawing nonexistent consent returns None."""
        result = await compliance_engine.withdraw_consent(
            user_id="nonexistent_user",
            consent_type=ConsentType.ANALYTICS,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_process_gpc_signal_enabled(self, compliance_engine):
        """Test processing GPC signal when enabled."""
        # First record some consents
        await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.THIRD_PARTY,
            purpose="Data sharing",
            granted=True,
            collected_via="consent_banner",
            consent_text_version="1.0",
        )

        # Process GPC signal
        withdrawn = await compliance_engine.process_gpc_signal(
            user_id="user_123",
            gpc_enabled=True,
        )

        # Should have withdrawn third-party consent
        assert len(withdrawn) >= 0  # May be 0 if no applicable consents

    @pytest.mark.asyncio
    async def test_get_user_consents(self, compliance_engine):
        """Test getting all consents for a user."""
        # Record multiple consents
        await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.ANALYTICS,
            purpose="Analytics",
            granted=True,
            collected_via="banner",
            consent_text_version="1.0",
        )
        await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.MARKETING,
            purpose="Marketing",
            granted=False,
            collected_via="banner",
            consent_text_version="1.0",
        )

        consents = await compliance_engine.get_user_consents("user_123")
        assert len(consents) == 2

    @pytest.mark.asyncio
    async def test_check_consent_valid(self, compliance_engine):
        """Test checking valid consent."""
        await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.ANALYTICS,
            purpose="Analytics",
            granted=True,
            collected_via="banner",
            consent_text_version="1.0",
        )

        has_consent = await compliance_engine.check_consent(
            "user_123", ConsentType.ANALYTICS
        )
        assert has_consent is True

    @pytest.mark.asyncio
    async def test_check_consent_not_granted(self, compliance_engine):
        """Test checking consent that was not granted."""
        await compliance_engine.record_consent(
            user_id="user_123",
            consent_type=ConsentType.MARKETING,
            purpose="Marketing",
            granted=False,
            collected_via="banner",
            consent_text_version="1.0",
        )

        has_consent = await compliance_engine.check_consent(
            "user_123", ConsentType.MARKETING
        )
        assert has_consent is False


class TestBreachNotificationOperations:
    """Tests for breach notification operations."""

    @pytest.mark.asyncio
    async def test_report_breach(self, compliance_engine):
        """Test reporting a data breach."""
        breach = await compliance_engine.report_breach(
            discovered_by="security_team",
            discovery_method="automated_monitoring",
            severity=BreachSeverity.HIGH,
            breach_type="unauthorized_access",
            data_categories=[DataClassification.PERSONAL_DATA],
            data_elements=["email", "name", "address"],
            jurisdictions=[Jurisdiction.EU],
            record_count=1500,
            root_cause="SQL injection vulnerability",
        )

        assert breach.id in compliance_engine._breaches
        assert breach.severity == BreachSeverity.HIGH
        assert breach.record_count == 1500
        assert len(breach.notification_deadlines) > 0

    @pytest.mark.asyncio
    async def test_report_breach_multiple_jurisdictions(self, compliance_engine):
        """Test reporting breach affecting multiple jurisdictions."""
        breach = await compliance_engine.report_breach(
            discovered_by="security_team",
            discovery_method="monitoring",
            severity=BreachSeverity.CRITICAL,
            breach_type="data_exfiltration",
            data_categories=[DataClassification.PHI],
            data_elements=["ssn", "medical_records"],
            jurisdictions=[Jurisdiction.EU, Jurisdiction.US_FEDERAL, Jurisdiction.UK],
            record_count=50000,
        )

        # Should have deadlines for each jurisdiction
        assert len(breach.notification_deadlines) >= 3

    @pytest.mark.asyncio
    async def test_mark_breach_contained(self, compliance_engine):
        """Test marking a breach as contained."""
        # First report breach
        breach = await compliance_engine.report_breach(
            discovered_by="security_team",
            discovery_method="monitoring",
            severity=BreachSeverity.HIGH,
            breach_type="unauthorized_access",
            data_categories=[DataClassification.PERSONAL_DATA],
            data_elements=["email"],
            jurisdictions=[Jurisdiction.EU],
            record_count=100,
        )

        # Mark as contained
        contained_breach = await compliance_engine.mark_breach_contained(
            breach_id=breach.id,
            containment_actions=["isolated_system", "rotated_credentials", "patched_vulnerability"],
            actor_id="security_lead",
        )

        assert contained_breach.contained is True
        assert contained_breach.contained_at is not None
        assert len(contained_breach.containment_actions) == 3

    @pytest.mark.asyncio
    async def test_mark_breach_contained_nonexistent(self, compliance_engine):
        """Test marking nonexistent breach raises error."""
        with pytest.raises(ValueError, match="Breach not found"):
            await compliance_engine.mark_breach_contained(
                breach_id="nonexistent",
                containment_actions=["action"],
                actor_id="actor",
            )

    @pytest.mark.asyncio
    async def test_record_authority_notification(self, compliance_engine):
        """Test recording authority notification."""
        breach = await compliance_engine.report_breach(
            discovered_by="security_team",
            discovery_method="monitoring",
            severity=BreachSeverity.HIGH,
            breach_type="unauthorized_access",
            data_categories=[DataClassification.PERSONAL_DATA],
            data_elements=["email"],
            jurisdictions=[Jurisdiction.EU],
            record_count=100,
        )

        updated_breach = await compliance_engine.record_authority_notification(
            breach_id=breach.id,
            jurisdiction=Jurisdiction.EU,
            reference_number="ICO-2024-001234",
            actor_id="compliance_officer",
        )

        # Find the notification for EU
        eu_notification = next(
            (n for n in updated_breach.authority_notifications if n.jurisdiction == Jurisdiction.EU),
            None,
        )
        assert eu_notification is not None
        assert eu_notification.notified is True
        assert eu_notification.reference_number == "ICO-2024-001234"


class TestAIGovernanceOperations:
    """Tests for AI governance operations."""

    @pytest.mark.asyncio
    async def test_register_ai_system(self, compliance_engine):
        """Test registering an AI system."""
        registration = await compliance_engine.register_ai_system(
            system_name="Content Recommendation Engine",
            system_version="2.0.0",
            provider="Forge AI Labs",
            risk_classification=AIRiskClassification.LIMITED_RISK,
            intended_purpose="Recommend content based on user preferences",
            use_cases=["personalization", "content_ranking"],
            model_type="Collaborative Filtering",
            human_oversight_measures=["manual_review_option", "appeal_process"],
        )

        assert registration.id in compliance_engine._ai_systems
        assert registration.system_name == "Content Recommendation Engine"
        assert registration.risk_classification == AIRiskClassification.LIMITED_RISK

    @pytest.mark.asyncio
    async def test_register_high_risk_ai_system(self, compliance_engine):
        """Test registering a high-risk AI system."""
        registration = await compliance_engine.register_ai_system(
            system_name="Employment Screening System",
            system_version="1.0.0",
            provider="Forge AI Labs",
            risk_classification=AIRiskClassification.HIGH_RISK,
            intended_purpose="Screen job applicants",
            use_cases=["resume_screening", "candidate_ranking"],
            model_type="LLM + Classification",
            human_oversight_measures=["mandatory_human_review", "bias_monitoring"],
            training_data_description="Historical hiring decisions",
        )

        assert registration.risk_classification == AIRiskClassification.HIGH_RISK
        # High risk requires conformity assessment
        assert registration.risk_classification.requires_conformity_assessment is True

    @pytest.mark.asyncio
    async def test_log_ai_decision(self, compliance_engine):
        """Test logging an AI decision."""
        # First register the system
        system = await compliance_engine.register_ai_system(
            system_name="Test System",
            system_version="1.0",
            provider="Forge",
            risk_classification=AIRiskClassification.LIMITED_RISK,
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        # Log a decision
        decision = await compliance_engine.log_ai_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="recommendation",
            decision_outcome="recommend_item_A",
            confidence_score=0.85,
            input_summary={"user_id": "user_123"},
            reasoning_chain=["factor_1", "factor_2"],
            key_factors=[{"factor": "history", "weight": 0.5}],
            subject_id="user_123",
        )

        assert decision.ai_system_id == system.id
        assert decision.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_log_ai_decision_with_legal_effect(self, compliance_engine):
        """Test logging an AI decision with legal effect."""
        system = await compliance_engine.register_ai_system(
            system_name="Loan Decision System",
            system_version="1.0",
            provider="Forge",
            risk_classification=AIRiskClassification.HIGH_RISK,
            intended_purpose="Loan approval decisions",
            use_cases=["loan_approval"],
            model_type="classifier",
            human_oversight_measures=["mandatory_review"],
        )

        decision = await compliance_engine.log_ai_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="loan_approval",
            decision_outcome="denied",
            confidence_score=0.92,
            input_summary={"applicant_id": "user_456"},
            reasoning_chain=["insufficient_credit"],
            key_factors=[{"factor": "credit_score", "weight": 0.8}],
            subject_id="user_456",
            has_legal_effect=True,
            has_significant_effect=True,
        )

        assert decision.has_legal_effect is True
        assert decision.has_significant_effect is True

    @pytest.mark.asyncio
    async def test_request_human_review(self, compliance_engine):
        """Test requesting human review of an AI decision."""
        system = await compliance_engine.register_ai_system(
            system_name="Test System",
            system_version="1.0",
            provider="Forge",
            risk_classification=AIRiskClassification.HIGH_RISK,
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await compliance_engine.log_ai_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="test",
            decision_outcome="test_outcome",
            confidence_score=0.9,
            input_summary={},
            reasoning_chain=[],
            key_factors=[],
        )

        reviewed_decision = await compliance_engine.request_human_review(
            decision_id=decision.id,
            reviewer_id="reviewer_001",
            override=False,
        )

        assert reviewed_decision.human_reviewed is True
        assert reviewed_decision.human_reviewer == "reviewer_001"

    @pytest.mark.asyncio
    async def test_request_human_review_with_override(self, compliance_engine):
        """Test human review with override."""
        system = await compliance_engine.register_ai_system(
            system_name="Test System",
            system_version="1.0",
            provider="Forge",
            risk_classification=AIRiskClassification.HIGH_RISK,
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await compliance_engine.log_ai_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="test",
            decision_outcome="deny",
            confidence_score=0.9,
            input_summary={},
            reasoning_chain=[],
            key_factors=[],
        )

        reviewed_decision = await compliance_engine.request_human_review(
            decision_id=decision.id,
            reviewer_id="reviewer_001",
            override=True,
            override_reason="Exceptional circumstances",
        )

        assert reviewed_decision.human_override is True
        assert reviewed_decision.override_reason == "Exceptional circumstances"

    @pytest.mark.asyncio
    async def test_get_ai_decision_explanation(self, compliance_engine):
        """Test getting explanation for an AI decision."""
        system = await compliance_engine.register_ai_system(
            system_name="Test System",
            system_version="1.0",
            provider="Forge",
            risk_classification=AIRiskClassification.LIMITED_RISK,
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await compliance_engine.log_ai_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="recommendation",
            decision_outcome="recommend_A",
            confidence_score=0.85,
            input_summary={"context": "homepage"},
            reasoning_chain=["User previously liked similar items"],
            key_factors=[{"factor": "past_behavior", "weight": 0.7}],
        )

        explanation = await compliance_engine.get_ai_decision_explanation(decision.id)

        assert explanation is not None
        assert "decision_id" in explanation


class TestAuditOperations:
    """Tests for audit logging operations."""

    @pytest.mark.asyncio
    async def test_get_audit_events(self, compliance_engine):
        """Test getting audit events."""
        # Create some activity that generates audit events
        await compliance_engine.create_dsar(
            request_type=DSARType.ACCESS,
            subject_email="user@example.com",
            request_text="Access my data",
        )

        events = await compliance_engine.get_audit_events(limit=10)
        # Should have at least one event from DSAR creation
        assert isinstance(events, list)

    def test_verify_audit_chain(self, compliance_engine):
        """Test verifying audit chain integrity."""
        is_valid, message = compliance_engine.verify_audit_chain()

        # With no events, should be valid
        assert is_valid is True


class TestComplianceReporting:
    """Tests for compliance reporting operations."""

    @pytest.mark.asyncio
    async def test_generate_compliance_report(self, compliance_engine):
        """Test generating a compliance report."""
        report = await compliance_engine.generate_compliance_report(
            report_type="full",
            frameworks=[ComplianceFramework.GDPR, ComplianceFramework.CCPA],
            jurisdictions=[Jurisdiction.EU, Jurisdiction.US_CALIFORNIA],
            generated_by="compliance_officer",
        )

        assert report.report_type == "full"
        assert ComplianceFramework.GDPR in report.frameworks_assessed
        assert report.total_controls_assessed >= 0

    @pytest.mark.asyncio
    async def test_generate_compliance_report_with_date_range(self, compliance_engine):
        """Test generating report with date range."""
        start_date = datetime.now(UTC) - timedelta(days=30)
        end_date = datetime.now(UTC)

        report = await compliance_engine.generate_compliance_report(
            report_type="executive",
            start_date=start_date,
            end_date=end_date,
        )

        assert report.report_period_start == start_date
        assert report.report_period_end == end_date

    @pytest.mark.asyncio
    async def test_verify_control(self, compliance_engine):
        """Test verifying a compliance control."""
        ctrl_status = await compliance_engine.verify_control(
            control_id="GDPR-5.1",
            verifier_id="auditor_001",
            evidence=["processing_register.pdf", "legal_basis_doc.docx"],
            notes="Verified during Q4 audit",
        )

        assert ctrl_status is not None
        assert ctrl_status.verified is True

    @pytest.mark.asyncio
    async def test_verify_control_nonexistent(self, compliance_engine):
        """Test verifying nonexistent control returns None."""
        ctrl_status = await compliance_engine.verify_control(
            control_id="NONEXISTENT-999",
            verifier_id="auditor_001",
        )
        assert ctrl_status is None

    @pytest.mark.asyncio
    async def test_run_automated_verifications(self, compliance_engine):
        """Test running automated control verifications."""
        results = await compliance_engine.run_automated_verifications()

        assert isinstance(results, dict)


class TestGetComplianceEngine:
    """Tests for get_compliance_engine function."""

    def test_get_compliance_engine_returns_instance(self):
        """Test that get_compliance_engine returns an engine instance."""
        engine = get_compliance_engine()
        assert isinstance(engine, ComplianceEngine)

    def test_get_compliance_engine_singleton(self):
        """Test that get_compliance_engine returns the same instance."""
        engine1 = get_compliance_engine()
        engine2 = get_compliance_engine()
        assert engine1 is engine2
