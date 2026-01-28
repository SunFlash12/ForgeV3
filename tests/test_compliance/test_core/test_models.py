"""
Tests for forge.compliance.core.models module.

Tests all Pydantic models for compliance entities including
controls, audit events, DSARs, consent records, breaches,
AI governance, and compliance reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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
    AffectedIndividual,
    AIDecisionLog,
    AISystemRegistration,
    AuditChain,
    AuditEvent,
    BreachNotification,
    ComplianceModel,
    ComplianceReport,
    ComplianceStatus,
    ConsentRecord,
    ControlStatus,
    DataSubjectRequest,
    DSARVerification,
    generate_id,
    RegulatoryNotification,
    TimestampMixin,
)


class TestGenerateId:
    """Tests for the generate_id function."""

    def test_generates_unique_ids(self):
        """Test that generate_id creates unique IDs."""
        ids = [generate_id() for _ in range(100)]
        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_id_is_string(self):
        """Test that generated ID is a string."""
        id_value = generate_id()
        assert isinstance(id_value, str)

    def test_id_is_valid_uuid_format(self):
        """Test that generated ID is a valid UUID format."""
        from uuid import UUID
        id_value = generate_id()
        # Should not raise an exception
        UUID(id_value)


class TestComplianceModel:
    """Tests for the ComplianceModel base class."""

    def test_model_config(self):
        """Test that ComplianceModel has correct config."""
        config = ComplianceModel.model_config
        assert config.get("use_enum_values") is True
        assert config.get("populate_by_name") is True


class TestControlStatus:
    """Tests for the ControlStatus model."""

    def test_basic_control_status_creation(self, sample_control_status):
        """Test basic control status creation."""
        assert sample_control_status.control_id == "GDPR-5.1"
        assert sample_control_status.framework == ComplianceFramework.GDPR
        assert sample_control_status.implemented is True
        assert sample_control_status.verified is True

    def test_control_status_status_property_verified(self):
        """Test status property returns 'verified' when verified."""
        control = ControlStatus(
            control_id="TEST-001",
            framework=ComplianceFramework.GDPR,
            name="Test",
            description="Test control",
            implemented=True,
            verified=True,
        )
        assert control.status == "verified"

    def test_control_status_status_property_implemented(self):
        """Test status property returns 'implemented' when implemented but not verified."""
        control = ControlStatus(
            control_id="TEST-001",
            framework=ComplianceFramework.GDPR,
            name="Test",
            description="Test control",
            implemented=True,
            verified=False,
        )
        assert control.status == "implemented"

    def test_control_status_status_property_pending(self):
        """Test status property returns 'pending' when not implemented."""
        control = ControlStatus(
            control_id="TEST-001",
            framework=ComplianceFramework.GDPR,
            name="Test",
            description="Test control",
            implemented=False,
            verified=False,
        )
        assert control.status == "pending"

    def test_control_status_is_compliant_property(self):
        """Test is_compliant property."""
        # Compliant when both implemented and verified
        compliant = ControlStatus(
            control_id="TEST-001",
            framework=ComplianceFramework.GDPR,
            name="Test",
            description="Test",
            implemented=True,
            verified=True,
        )
        assert compliant.is_compliant is True

        # Not compliant when only implemented
        not_compliant = ControlStatus(
            control_id="TEST-002",
            framework=ComplianceFramework.GDPR,
            name="Test",
            description="Test",
            implemented=True,
            verified=False,
        )
        assert not_compliant.is_compliant is False


class TestComplianceStatus:
    """Tests for the ComplianceStatus model."""

    def test_basic_compliance_status_creation(self, sample_compliance_status):
        """Test basic compliance status creation."""
        assert sample_compliance_status.organization_id == "org_001"
        assert len(sample_compliance_status.active_jurisdictions) == 2
        assert sample_compliance_status.total_controls == 23

    def test_compliance_percentage_property(self):
        """Test compliance_percentage calculation."""
        status = ComplianceStatus(
            organization_id="test",
            total_controls=100,
            verified_controls=75,
        )
        assert status.compliance_percentage == 75.0

    def test_compliance_percentage_zero_controls(self):
        """Test compliance_percentage with zero total controls."""
        status = ComplianceStatus(
            organization_id="test",
            total_controls=0,
            verified_controls=0,
        )
        assert status.compliance_percentage == 0.0

    def test_implementation_percentage_property(self):
        """Test implementation_percentage calculation."""
        status = ComplianceStatus(
            organization_id="test",
            total_controls=100,
            implemented_controls=90,
        )
        assert status.implementation_percentage == 90.0

    def test_get_framework_status(self, sample_compliance_status):
        """Test get_framework_status method."""
        gdpr_status = sample_compliance_status.get_framework_status(
            ComplianceFramework.GDPR
        )
        assert gdpr_status["total"] == 18
        assert gdpr_status["verified"] == 12

    def test_get_framework_status_nonexistent(self, sample_compliance_status):
        """Test get_framework_status with nonexistent framework."""
        status = sample_compliance_status.get_framework_status(
            ComplianceFramework.HIPAA
        )
        assert status["total"] == 0


class TestAuditEvent:
    """Tests for the AuditEvent model."""

    def test_basic_audit_event_creation(self, sample_audit_event):
        """Test basic audit event creation."""
        assert sample_audit_event.category == AuditEventCategory.DATA_ACCESS
        assert sample_audit_event.action == "READ"
        assert sample_audit_event.success is True

    def test_audit_event_default_values(self):
        """Test audit event default values."""
        event = AuditEvent(
            category=AuditEventCategory.AUTHENTICATION,
            event_type="login",
            action="AUTHENTICATE",
        )
        assert event.actor_type == "user"
        assert event.success is True
        assert event.risk_level == RiskLevel.INFO
        assert event.id is not None
        assert event.correlation_id is not None

    def test_audit_event_retention_validator(self):
        """Test that retention is set based on category."""
        event = AuditEvent(
            category=AuditEventCategory.AUTHENTICATION,
            event_type="login",
            action="AUTHENTICATE",
        )
        # Should have retention set
        assert event.retention_until is not None
        # Authentication events should be retained for 7 years (SOX)
        expected_retention = datetime.now(UTC) + timedelta(days=7 * 365)
        # Allow for some time difference
        assert abs((event.retention_until - expected_retention).days) <= 1

    def test_audit_event_with_changes(self):
        """Test audit event with old/new values."""
        event = AuditEvent(
            category=AuditEventCategory.DATA_MODIFICATION,
            event_type="profile_update",
            action="UPDATE",
            actor_id="user_123",
            entity_type="UserProfile",
            entity_id="profile_456",
            old_value={"name": "Old Name"},
            new_value={"name": "New Name"},
        )
        assert event.old_value == {"name": "Old Name"}
        assert event.new_value == {"name": "New Name"}


class TestAuditChain:
    """Tests for the AuditChain model."""

    def test_basic_audit_chain_creation(self, sample_audit_chain):
        """Test basic audit chain creation."""
        assert sample_audit_chain.event_count == 100
        assert sample_audit_chain.is_valid is True
        assert sample_audit_chain.start_hash is not None
        assert sample_audit_chain.end_hash is not None


class TestDSARVerification:
    """Tests for the DSARVerification model."""

    def test_basic_verification_creation(self):
        """Test basic DSAR verification creation."""
        verification = DSARVerification(
            method="email_verification",
            verified_at=datetime.now(UTC),
            verified_by="system",
            evidence={"email_confirmed": True},
            confidence_score=0.95,
        )
        assert verification.method == "email_verification"
        assert verification.confidence_score == 0.95

    def test_verification_confidence_score_bounds(self):
        """Test confidence score is within valid bounds."""
        # Valid scores
        valid_verification = DSARVerification(
            method="test",
            verified_at=datetime.now(UTC),
            confidence_score=0.5,
        )
        assert valid_verification.confidence_score == 0.5


class TestDataSubjectRequest:
    """Tests for the DataSubjectRequest model."""

    def test_basic_dsar_creation(self, sample_dsar):
        """Test basic DSAR creation."""
        assert sample_dsar.request_type == DSARType.ACCESS
        assert sample_dsar.jurisdiction == Jurisdiction.EU
        assert sample_dsar.status == "received"

    def test_dsar_deadline_calculation(self):
        """Test that deadline is calculated based on jurisdiction."""
        # Brazil has 15-day deadline (LGPD)
        dsar_brazil = DataSubjectRequest(
            request_type=DSARType.ACCESS,
            jurisdiction=Jurisdiction.BRAZIL,
            subject_email="user@example.com",
            request_text="Access my data",
        )
        assert dsar_brazil.deadline is not None
        # Should be approximately 15 days from now
        expected_deadline = dsar_brazil.received_at + timedelta(days=15)
        assert abs((dsar_brazil.deadline - expected_deadline).seconds) < 60

    def test_dsar_is_overdue_property(self, overdue_dsar):
        """Test is_overdue property."""
        assert overdue_dsar.is_overdue is True

    def test_dsar_not_overdue_when_completed(self):
        """Test is_overdue returns False when status is completed."""
        dsar = DataSubjectRequest(
            request_type=DSARType.ACCESS,
            jurisdiction=Jurisdiction.EU,
            subject_email="user@example.com",
            request_text="Access my data",
            status="completed",
        )
        dsar.deadline = datetime.now(UTC) - timedelta(days=10)  # Past deadline
        assert dsar.is_overdue is False  # But completed, so not overdue

    def test_dsar_days_until_deadline_property(self, sample_dsar):
        """Test days_until_deadline property."""
        days = sample_dsar.days_until_deadline
        assert isinstance(days, int)
        assert days >= 0

    def test_dsar_add_processing_note(self, sample_dsar):
        """Test add_processing_note method."""
        sample_dsar.add_processing_note("Started processing", "processor_001")

        assert len(sample_dsar.processing_log) == 1
        note = sample_dsar.processing_log[0]
        assert note["actor"] == "processor_001"
        assert note["note"] == "Started processing"
        assert "timestamp" in note


class TestConsentRecord:
    """Tests for the ConsentRecord model."""

    def test_basic_consent_creation(self, sample_consent):
        """Test basic consent record creation."""
        assert sample_consent.user_id == "user_123"
        assert sample_consent.consent_type == ConsentType.ANALYTICS
        assert sample_consent.granted is True

    def test_consent_is_valid_property_granted(self, sample_consent):
        """Test is_valid property for granted consent."""
        assert sample_consent.is_valid is True

    def test_consent_is_valid_property_withdrawn(self, withdrawn_consent):
        """Test is_valid property for withdrawn consent."""
        assert withdrawn_consent.is_valid is False

    def test_consent_is_valid_property_expired(self, expired_consent):
        """Test is_valid property for expired consent."""
        assert expired_consent.is_valid is False

    def test_consent_is_valid_property_not_granted(self):
        """Test is_valid property for consent not granted."""
        consent = ConsentRecord(
            user_id="user_123",
            consent_type=ConsentType.MARKETING,
            purpose="Marketing emails",
            granted=False,
            collected_via="consent_banner",
            consent_text_version="1.0",
        )
        assert consent.is_valid is False

    def test_consent_withdraw_method(self, sample_consent):
        """Test withdraw method."""
        assert sample_consent.granted is True
        assert sample_consent.withdrawn_at is None

        sample_consent.withdraw()

        assert sample_consent.granted is False
        assert sample_consent.withdrawn_at is not None


class TestAffectedIndividual:
    """Tests for the AffectedIndividual model."""

    def test_basic_creation(self, sample_affected_individual):
        """Test basic affected individual creation."""
        assert sample_affected_individual.user_id == "affected_user_001"
        assert sample_affected_individual.email == "affected@example.com"
        assert sample_affected_individual.notified is False


class TestRegulatoryNotification:
    """Tests for the RegulatoryNotification model."""

    def test_basic_creation(self, sample_regulatory_notification):
        """Test basic regulatory notification creation."""
        assert sample_regulatory_notification.authority == "Information Commissioner's Office (ICO)"
        assert sample_regulatory_notification.jurisdiction == Jurisdiction.UK
        assert sample_regulatory_notification.required is True
        assert sample_regulatory_notification.notified is False


class TestBreachNotification:
    """Tests for the BreachNotification model."""

    def test_basic_breach_creation(self, sample_breach):
        """Test basic breach notification creation."""
        assert sample_breach.severity == BreachSeverity.HIGH
        assert sample_breach.record_count == 1500
        assert sample_breach.contained is False

    def test_breach_deadline_calculation(self, sample_breach):
        """Test that notification deadlines are calculated."""
        assert len(sample_breach.notification_deadlines) > 0
        # EU should have 72-hour deadline
        assert "eu" in sample_breach.notification_deadlines

    def test_breach_most_urgent_deadline_property(self, sample_breach):
        """Test most_urgent_deadline property."""
        deadline = sample_breach.most_urgent_deadline
        assert deadline is not None
        # Should be within 72 hours
        max_deadline = sample_breach.discovered_at + timedelta(hours=72)
        assert deadline <= max_deadline

    def test_breach_is_overdue_property(self):
        """Test is_overdue property."""
        breach = BreachNotification(
            discovered_by="security_team",
            discovery_method="monitoring",
            severity=BreachSeverity.HIGH,
            breach_type="unauthorized_access",
            data_categories=[DataClassification.PERSONAL_DATA],
            data_elements=["email"],
            jurisdictions=[Jurisdiction.EU],
        )
        # Initially not overdue
        assert breach.is_overdue is False


class TestAISystemRegistration:
    """Tests for the AISystemRegistration model."""

    def test_basic_ai_system_creation(self, sample_ai_system):
        """Test basic AI system registration creation."""
        assert sample_ai_system.system_name == "Content Recommendation Engine"
        assert sample_ai_system.risk_classification == AIRiskClassification.LIMITED_RISK
        assert sample_ai_system.override_capability is True

    def test_high_risk_ai_system(self, high_risk_ai_system):
        """Test high-risk AI system attributes."""
        assert high_risk_ai_system.risk_classification == AIRiskClassification.HIGH_RISK
        assert high_risk_ai_system.conformity_assessment_completed is False


class TestAIDecisionLog:
    """Tests for the AIDecisionLog model."""

    def test_basic_ai_decision_creation(self, sample_ai_decision):
        """Test basic AI decision log creation."""
        assert sample_ai_decision.ai_system_id == "ai_sys_001"
        assert sample_ai_decision.confidence_score == 0.85
        assert sample_ai_decision.has_legal_effect is False

    def test_legal_effect_ai_decision(self, legal_effect_ai_decision):
        """Test AI decision with legal effect."""
        assert legal_effect_ai_decision.has_legal_effect is True
        assert legal_effect_ai_decision.has_significant_effect is True
        assert legal_effect_ai_decision.human_reviewed is False

    def test_ai_decision_confidence_score_bounds(self):
        """Test confidence score is within valid bounds."""
        # Valid score
        decision = AIDecisionLog(
            ai_system_id="test",
            model_version="1.0",
            decision_type="test",
            decision_outcome="test",
            confidence_score=0.75,
            input_summary={},
        )
        assert decision.confidence_score == 0.75


class TestComplianceReport:
    """Tests for the ComplianceReport model."""

    def test_basic_report_creation(self, sample_compliance_report):
        """Test basic compliance report creation."""
        assert sample_compliance_report.report_type == "full"
        assert sample_compliance_report.overall_compliance_score == 69.5
        assert sample_compliance_report.total_controls_assessed == 23

    def test_report_compliance_percentage_property(self):
        """Test compliance_percentage property."""
        report = ComplianceReport(
            total_controls_assessed=100,
            controls_compliant=80,
            controls_non_compliant=15,
            controls_not_applicable=5,
        )
        # 80 compliant out of 95 applicable (100 - 5)
        expected_pct = (80 / 95) * 100
        assert abs(report.compliance_percentage - expected_pct) < 0.01

    def test_report_compliance_percentage_all_not_applicable(self):
        """Test compliance_percentage when all controls are not applicable."""
        report = ComplianceReport(
            total_controls_assessed=10,
            controls_compliant=0,
            controls_non_compliant=0,
            controls_not_applicable=10,
        )
        # All not applicable should return 100%
        assert report.compliance_percentage == 100.0

    def test_report_with_gaps(self, sample_compliance_report):
        """Test report with gap data."""
        assert len(sample_compliance_report.critical_gaps) == 1
        assert len(sample_compliance_report.high_risk_gaps) == 1
        assert sample_compliance_report.critical_gaps[0]["control_id"] == "GDPR-7"

    def test_report_metrics(self, sample_compliance_report):
        """Test report metrics sections."""
        # DSAR metrics
        assert sample_compliance_report.dsar_metrics["total_received"] == 15
        assert sample_compliance_report.dsar_metrics["completed"] == 12

        # Consent metrics
        assert sample_compliance_report.consent_metrics["users_with_consent"] == 5000

        # Breach metrics
        assert sample_compliance_report.breach_metrics["total_breaches"] == 2

        # AI metrics
        assert sample_compliance_report.ai_system_count == 3
        assert sample_compliance_report.ai_decisions_logged == 15000
