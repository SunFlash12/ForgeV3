"""
Shared fixtures for compliance module tests.

Provides commonly used mocks, fixtures, and test data for testing
compliance frameworks, DSAR processing, consent management, breach
notification, AI governance, and audit logging.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from forge.compliance.core.config import ComplianceConfig
from forge.compliance.core.enums import (
    AIRiskClassification,
    AuditEventCategory,
    BreachSeverity,
    ComplianceFramework,
    ConsentType,
    DataClassification,
    DSARType,
    EncryptionStandard,
    Jurisdiction,
    KeyRotationPolicy,
    RiskLevel,
)
from forge.compliance.core.models import (
    AffectedIndividual,
    AIDecisionLog,
    AISystemRegistration,
    AuditChain,
    AuditEvent,
    BreachNotification,
    ComplianceReport,
    ComplianceStatus,
    ConsentRecord,
    ControlStatus,
    DataSubjectRequest,
    DSARVerification,
    RegulatoryNotification,
)
from forge.compliance.core.registry import ComplianceRegistry, ControlDefinition


# =============================================================================
# TEST DATA GENERATORS
# =============================================================================


def generate_test_id() -> str:
    """Generate a unique test ID."""
    return str(uuid4())


def generate_test_hash() -> str:
    """Generate a test hash value."""
    return hashlib.sha256(str(uuid4()).encode()).hexdigest()


# =============================================================================
# COMPLIANCE CONFIG FIXTURES
# =============================================================================


@pytest.fixture
def compliance_config() -> ComplianceConfig:
    """Create a ComplianceConfig with test defaults."""
    return ComplianceConfig(
        active_jurisdictions="global,eu,us_ca",
        primary_jurisdiction=Jurisdiction.EU,
        active_frameworks="gdpr,ccpa,soc2,hipaa,eu_ai_act",
        encryption_at_rest_standard=EncryptionStandard.AES_256_GCM,
        encryption_in_transit_minimum=EncryptionStandard.TLS_1_3,
        key_rotation_policy=KeyRotationPolicy.DAYS_90,
        hsm_enabled=False,
        data_residency_enabled=True,
        dsar_auto_verify_internal=True,
        dsar_default_response_days=15,
        consent_explicit_required=True,
        consent_gpc_enabled=True,
        breach_notification_hours=72,
        audit_log_retention_years=7,
        audit_immutable=True,
        eu_ai_act_enabled=True,
        ai_human_oversight_required=True,
        ai_decision_logging=True,
        mfa_required=True,
        password_min_length=12,
    )


@pytest.fixture
def minimal_config() -> ComplianceConfig:
    """Create a minimal ComplianceConfig for basic tests."""
    return ComplianceConfig(
        active_jurisdictions="global",
        primary_jurisdiction=Jurisdiction.GLOBAL,
        active_frameworks="gdpr",
        audit_immutable=False,
    )


# =============================================================================
# COMPLIANCE REGISTRY FIXTURES
# =============================================================================


@pytest.fixture
def compliance_registry() -> ComplianceRegistry:
    """Create a fresh ComplianceRegistry for testing."""
    return ComplianceRegistry()


@pytest.fixture
def sample_control_definition() -> ControlDefinition:
    """Create a sample control definition for testing."""
    return ControlDefinition(
        control_id="TEST-001",
        framework=ComplianceFramework.GDPR,
        name="Test Control",
        description="A test control for unit testing",
        category="security",
        implementation_guidance="Implement this test control",
        evidence_required=["test_evidence_1", "test_evidence_2"],
        risk_if_missing=RiskLevel.HIGH,
        automatable=True,
        verification_function="test_verify_func",
        depends_on=["OTHER-001"],
        related_controls=["TEST-002"],
        mappings={"ccpa": ["CCPA-100"]},
    )


@pytest.fixture
def sample_control_status() -> ControlStatus:
    """Create a sample control status for testing."""
    return ControlStatus(
        control_id="GDPR-5.1",
        framework=ComplianceFramework.GDPR,
        name="Lawfulness of Processing",
        description="Ensure all personal data processing has a valid legal basis",
        implemented=True,
        verified=True,
        automated=True,
        evidence_required=["processing_register", "legal_basis_documentation"],
        evidence_provided=["processing_register_v1", "legal_basis_doc"],
        risk_if_missing=RiskLevel.CRITICAL,
        last_audit_date=datetime.now(UTC),
        owner="compliance_team",
    )


# =============================================================================
# DSAR FIXTURES
# =============================================================================


@pytest.fixture
def sample_dsar() -> DataSubjectRequest:
    """Create a sample DSAR for testing."""
    return DataSubjectRequest(
        request_type=DSARType.ACCESS,
        jurisdiction=Jurisdiction.EU,
        applicable_frameworks=[ComplianceFramework.GDPR],
        subject_id="user_123",
        subject_email="user@example.com",
        subject_name="Test User",
        request_text="I want to access all my personal data",
        specific_data_categories=["profile", "transactions"],
        status="received",
    )


@pytest.fixture
def verified_dsar(sample_dsar: DataSubjectRequest) -> DataSubjectRequest:
    """Create a verified DSAR for testing."""
    sample_dsar.verified = True
    sample_dsar.status = "verified"
    sample_dsar.verification = DSARVerification(
        method="email_verification",
        verified_at=datetime.now(UTC),
        verified_by="system",
        evidence={"email_confirmed": True},
        confidence_score=0.95,
    )
    return sample_dsar


@pytest.fixture
def overdue_dsar() -> DataSubjectRequest:
    """Create an overdue DSAR for testing."""
    dsar = DataSubjectRequest(
        request_type=DSARType.ERASURE,
        jurisdiction=Jurisdiction.BRAZIL,  # LGPD has 15-day deadline
        applicable_frameworks=[ComplianceFramework.LGPD],
        subject_id="user_456",
        subject_email="user@brazil.com",
        request_text="Delete all my data",
        status="processing",
    )
    # Set deadline to past
    dsar.deadline = datetime.now(UTC) - timedelta(days=5)
    dsar.received_at = datetime.now(UTC) - timedelta(days=20)
    return dsar


# =============================================================================
# CONSENT FIXTURES
# =============================================================================


@pytest.fixture
def sample_consent() -> ConsentRecord:
    """Create a sample consent record for testing."""
    return ConsentRecord(
        user_id="user_123",
        consent_type=ConsentType.ANALYTICS,
        purpose="Website analytics to improve user experience",
        granted=True,
        granted_at=datetime.now(UTC),
        collected_via="consent_banner",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test",
        consent_text_version="1.0",
        consent_text_hash=generate_test_hash()[:16],
        third_parties=["analytics_provider"],
        cross_border_transfer=False,
    )


@pytest.fixture
def withdrawn_consent(sample_consent: ConsentRecord) -> ConsentRecord:
    """Create a withdrawn consent record for testing."""
    sample_consent.granted = False
    sample_consent.withdrawn_at = datetime.now(UTC)
    return sample_consent


@pytest.fixture
def expired_consent() -> ConsentRecord:
    """Create an expired consent record for testing."""
    return ConsentRecord(
        user_id="user_789",
        consent_type=ConsentType.MARKETING,
        purpose="Marketing emails",
        granted=True,
        granted_at=datetime.now(UTC) - timedelta(days=400),
        collected_via="signup_form",
        consent_text_version="1.0",
        expires_at=datetime.now(UTC) - timedelta(days=30),
    )


# =============================================================================
# BREACH NOTIFICATION FIXTURES
# =============================================================================


@pytest.fixture
def sample_breach() -> BreachNotification:
    """Create a sample breach notification for testing."""
    return BreachNotification(
        discovered_by="security_team",
        discovery_method="automated_monitoring",
        severity=BreachSeverity.HIGH,
        breach_type="unauthorized_access",
        data_categories=[DataClassification.PERSONAL_DATA, DataClassification.FINANCIAL],
        data_elements=["email", "name", "credit_card_last_4"],
        jurisdictions=[Jurisdiction.EU, Jurisdiction.US_CALIFORNIA],
        record_count=1500,
        affected_count=1500,
        root_cause="SQL injection vulnerability",
        attack_vector="web_application",
    )


@pytest.fixture
def critical_breach() -> BreachNotification:
    """Create a critical breach notification for testing."""
    return BreachNotification(
        discovered_by="external_researcher",
        discovery_method="bug_bounty",
        severity=BreachSeverity.CRITICAL,
        breach_type="data_exfiltration",
        data_categories=[DataClassification.PHI, DataClassification.SENSITIVE_PERSONAL],
        data_elements=["ssn", "medical_records", "biometric_data"],
        jurisdictions=[Jurisdiction.EU, Jurisdiction.US_FEDERAL],
        record_count=50000,
        affected_count=50000,
        root_cause="Advanced persistent threat",
        attack_vector="supply_chain",
    )


@pytest.fixture
def sample_regulatory_notification() -> RegulatoryNotification:
    """Create a sample regulatory notification for testing."""
    return RegulatoryNotification(
        authority="Information Commissioner's Office (ICO)",
        jurisdiction=Jurisdiction.UK,
        required=True,
        notified=False,
        deadline=datetime.now(UTC) + timedelta(hours=72),
    )


@pytest.fixture
def sample_affected_individual() -> AffectedIndividual:
    """Create a sample affected individual for testing."""
    return AffectedIndividual(
        user_id="affected_user_001",
        email="affected@example.com",
        name="Affected Person",
        data_types_exposed=["email", "address", "phone"],
        jurisdiction=Jurisdiction.EU,
        notified=False,
    )


# =============================================================================
# AI GOVERNANCE FIXTURES
# =============================================================================


@pytest.fixture
def sample_ai_system() -> AISystemRegistration:
    """Create a sample AI system registration for testing."""
    return AISystemRegistration(
        system_name="Content Recommendation Engine",
        system_version="2.1.0",
        provider="Forge AI Labs",
        risk_classification=AIRiskClassification.LIMITED_RISK,
        intended_purpose="Recommend content based on user preferences",
        use_cases=["personalization", "content_ranking"],
        model_type="Collaborative Filtering + Transformer",
        training_data_description="User interaction history and content metadata",
        human_oversight_measures=["manual_review_option", "appeal_process"],
        override_capability=True,
    )


@pytest.fixture
def high_risk_ai_system() -> AISystemRegistration:
    """Create a high-risk AI system registration for testing."""
    return AISystemRegistration(
        system_name="Employment Screening System",
        system_version="1.0.0",
        provider="Forge AI Labs",
        risk_classification=AIRiskClassification.HIGH_RISK,
        intended_purpose="Screen job applicants for eligibility",
        use_cases=["resume_screening", "candidate_ranking"],
        model_type="LLM + Classification",
        training_data_description="Historical hiring decisions",
        human_oversight_measures=[
            "mandatory_human_review",
            "bias_monitoring",
            "appeal_mechanism",
        ],
        override_capability=True,
        conformity_assessment_completed=False,
    )


@pytest.fixture
def sample_ai_decision() -> AIDecisionLog:
    """Create a sample AI decision log for testing."""
    return AIDecisionLog(
        ai_system_id="ai_sys_001",
        model_version="2.1.0",
        decision_type="content_recommendation",
        decision_outcome="recommend_items_A_B_C",
        confidence_score=0.85,
        input_summary={"user_id": "user_123", "context": "homepage"},
        reasoning_chain=[
            "User previously viewed similar items",
            "Items match user preference profile",
            "Items are trending in user's region",
        ],
        key_factors=[
            {"factor": "past_purchases", "weight": 0.4},
            {"factor": "browsing_history", "weight": 0.35},
            {"factor": "trending_score", "weight": 0.25},
        ],
        subject_id="user_123",
        has_legal_effect=False,
        has_significant_effect=False,
    )


@pytest.fixture
def legal_effect_ai_decision() -> AIDecisionLog:
    """Create an AI decision with legal effect for testing."""
    return AIDecisionLog(
        ai_system_id="ai_sys_002",
        model_version="1.0.0",
        decision_type="loan_approval",
        decision_outcome="denied",
        confidence_score=0.92,
        input_summary={
            "applicant_id": "user_456",
            "loan_amount": 50000,
            "income": 75000,
        },
        reasoning_chain=[
            "Debt-to-income ratio exceeds threshold",
            "Credit score below minimum requirement",
            "Recent payment history shows issues",
        ],
        key_factors=[
            {"factor": "debt_to_income", "weight": 0.5},
            {"factor": "credit_score", "weight": 0.3},
            {"factor": "payment_history", "weight": 0.2},
        ],
        subject_id="user_456",
        has_legal_effect=True,
        has_significant_effect=True,
        human_reviewed=False,
    )


# =============================================================================
# AUDIT FIXTURES
# =============================================================================


@pytest.fixture
def sample_audit_event() -> AuditEvent:
    """Create a sample audit event for testing."""
    return AuditEvent(
        category=AuditEventCategory.DATA_ACCESS,
        event_type="user_data_export",
        action="READ",
        actor_id="user_123",
        actor_type="user",
        actor_ip="192.168.1.1",
        entity_type="UserData",
        entity_id="data_export_001",
        success=True,
        risk_level=RiskLevel.INFO,
        data_classification=DataClassification.PERSONAL_DATA,
    )


@pytest.fixture
def security_audit_event() -> AuditEvent:
    """Create a security-related audit event for testing."""
    return AuditEvent(
        category=AuditEventCategory.SECURITY,
        event_type="failed_login_attempt",
        action="AUTHENTICATE",
        actor_id="unknown",
        actor_type="user",
        actor_ip="10.0.0.5",
        entity_type="User",
        entity_id="user_456",
        success=False,
        error_code="AUTH_FAILED",
        error_message="Invalid password",
        risk_level=RiskLevel.MEDIUM,
    )


@pytest.fixture
def sample_audit_chain() -> AuditChain:
    """Create a sample audit chain for testing."""
    return AuditChain(
        start_hash=generate_test_hash(),
        end_hash=generate_test_hash(),
        event_count=100,
        verified_at=datetime.now(UTC),
        is_valid=True,
    )


# =============================================================================
# COMPLIANCE REPORT FIXTURES
# =============================================================================


@pytest.fixture
def sample_compliance_status() -> ComplianceStatus:
    """Create a sample compliance status for testing."""
    return ComplianceStatus(
        organization_id="org_001",
        active_jurisdictions=[Jurisdiction.EU, Jurisdiction.US_CALIFORNIA],
        active_frameworks=[ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        controls_by_framework={
            "gdpr": {"total": 18, "implemented": 15, "verified": 12, "pending": 3},
            "ccpa": {"total": 5, "implemented": 4, "verified": 4, "pending": 1},
        },
        total_controls=23,
        implemented_controls=19,
        verified_controls=16,
        automated_controls=10,
        high_risk_pending=3,
        critical_findings=["GDPR-7", "GDPR-32"],
    )


@pytest.fixture
def sample_compliance_report(
    sample_compliance_status: ComplianceStatus,
) -> ComplianceReport:
    """Create a sample compliance report for testing."""
    return ComplianceReport(
        report_type="full",
        report_period_start=datetime.now(UTC) - timedelta(days=30),
        report_period_end=datetime.now(UTC),
        generated_by="compliance_officer",
        frameworks_assessed=[ComplianceFramework.GDPR, ComplianceFramework.CCPA],
        jurisdictions_assessed=[Jurisdiction.EU, Jurisdiction.US_CALIFORNIA],
        overall_compliance_score=69.5,
        status=sample_compliance_status,
        total_controls_assessed=23,
        controls_compliant=16,
        controls_non_compliant=7,
        critical_gaps=[
            {
                "control_id": "GDPR-7",
                "name": "Consent Requirements",
                "risk_level": "critical",
            }
        ],
        high_risk_gaps=[
            {
                "control_id": "GDPR-32",
                "name": "Security of Processing",
                "risk_level": "high",
            }
        ],
        dsar_metrics={
            "total_received": 15,
            "completed": 12,
            "pending": 3,
            "overdue": 1,
            "average_completion_days": 8.5,
        },
        consent_metrics={
            "users_with_consent": 5000,
            "active_consents": 4200,
            "withdrawn_consents": 800,
        },
        breach_metrics={
            "total_breaches": 2,
            "critical_breaches": 0,
            "contained": 2,
            "overdue_notifications": 0,
        },
        ai_system_count=3,
        high_risk_ai_systems=1,
        ai_decisions_logged=15000,
        ai_decisions_contested=12,
    )


# =============================================================================
# MOCK REPOSITORY FIXTURES
# =============================================================================


@pytest.fixture
def mock_neo4j_client() -> MagicMock:
    """Create a mock Neo4j client for testing."""
    client = MagicMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest_asyncio.fixture
async def mock_repository(mock_neo4j_client: MagicMock) -> AsyncGenerator[MagicMock, None]:
    """Create a mock ComplianceRepository for testing."""
    from forge.compliance.core.repository import ComplianceRepository

    repo = ComplianceRepository(mock_neo4j_client)
    repo._initialized = True

    # Mock all async methods
    repo.create_dsar = AsyncMock(return_value={})
    repo.update_dsar = AsyncMock(return_value={})
    repo.get_dsar = AsyncMock(return_value=None)
    repo.get_dsars_by_status = AsyncMock(return_value=[])
    repo.get_overdue_dsars = AsyncMock(return_value=[])

    repo.create_consent = AsyncMock(return_value={})
    repo.withdraw_consent = AsyncMock(return_value={})
    repo.get_user_consents = AsyncMock(return_value=[])
    repo.check_consent = AsyncMock(return_value=False)

    repo.create_breach = AsyncMock(return_value={})
    repo.update_breach = AsyncMock(return_value={})
    repo.get_breach = AsyncMock(return_value=None)
    repo.get_active_breaches = AsyncMock(return_value=[])

    repo.create_audit_event = AsyncMock(return_value={})
    repo.get_audit_events = AsyncMock(return_value=[])
    repo.get_last_audit_hash = AsyncMock(return_value=None)
    repo.verify_audit_chain = AsyncMock(return_value=(True, "Chain verified"))

    repo.create_ai_system = AsyncMock(return_value={})
    repo.get_ai_system = AsyncMock(return_value=None)
    repo.get_all_ai_systems = AsyncMock(return_value=[])

    repo.create_ai_decision = AsyncMock(return_value={})
    repo.update_ai_decision = AsyncMock(return_value={})
    repo.get_ai_decisions = AsyncMock(return_value=[])

    yield repo


# =============================================================================
# COMPLIANCE ENGINE FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def compliance_engine(
    compliance_config: ComplianceConfig,
    compliance_registry: ComplianceRegistry,
) -> AsyncGenerator[Any, None]:
    """Create a ComplianceEngine for testing without persistence."""
    from forge.compliance.core.engine import ComplianceEngine

    engine = ComplianceEngine(
        config=compliance_config,
        registry=compliance_registry,
        repository=None,  # No persistence in tests
    )
    yield engine


@pytest_asyncio.fixture
async def compliance_engine_with_mock_repo(
    compliance_config: ComplianceConfig,
    compliance_registry: ComplianceRegistry,
    mock_repository: MagicMock,
) -> AsyncGenerator[Any, None]:
    """Create a ComplianceEngine with mocked repository for testing."""
    from forge.compliance.core.engine import ComplianceEngine

    engine = ComplianceEngine(
        config=compliance_config,
        registry=compliance_registry,
        repository=mock_repository,
    )
    yield engine


# =============================================================================
# API TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_current_user() -> dict[str, Any]:
    """Create a mock current user for API tests."""
    return {
        "id": "user_123",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["user"],
    }


@pytest.fixture
def mock_compliance_officer() -> dict[str, Any]:
    """Create a mock compliance officer for API tests."""
    return {
        "id": "officer_001",
        "email": "compliance@example.com",
        "name": "Compliance Officer",
        "roles": ["user", "compliance_officer"],
    }


@pytest.fixture
def mock_admin_user() -> dict[str, Any]:
    """Create a mock admin user for API tests."""
    return {
        "id": "admin_001",
        "email": "admin@example.com",
        "name": "Admin User",
        "roles": ["user", "compliance_officer", "admin"],
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_audit_event_chain(count: int = 5) -> list[AuditEvent]:
    """Create a chain of audit events with proper hash linking."""
    events = []
    previous_hash = None

    for i in range(count):
        event = AuditEvent(
            category=AuditEventCategory.DATA_ACCESS,
            event_type=f"test_event_{i}",
            action="READ",
            actor_id=f"user_{i}",
            previous_hash=previous_hash,
        )

        # Calculate hash
        event_data = json.dumps(
            {
                "id": event.id,
                "category": event.category.value,
                "event_type": event.event_type,
                "action": event.action,
                "timestamp": event.created_at.isoformat(),
                "previous_hash": event.previous_hash,
            },
            sort_keys=True,
        )
        event.hash = hashlib.sha256(event_data.encode()).hexdigest()
        previous_hash = event.hash

        events.append(event)

    return events


def create_test_dsar_batch(count: int = 10) -> list[DataSubjectRequest]:
    """Create a batch of test DSARs with varied statuses."""
    statuses = ["received", "verified", "processing", "completed", "rejected"]
    dsars = []

    for i in range(count):
        dsar = DataSubjectRequest(
            request_type=DSARType.ACCESS if i % 2 == 0 else DSARType.ERASURE,
            jurisdiction=Jurisdiction.EU if i % 3 == 0 else Jurisdiction.US_CALIFORNIA,
            applicable_frameworks=[
                ComplianceFramework.GDPR
                if i % 3 == 0
                else ComplianceFramework.CCPA
            ],
            subject_id=f"user_{i}",
            subject_email=f"user{i}@example.com",
            request_text=f"Test request {i}",
            status=statuses[i % len(statuses)],
        )
        dsars.append(dsar)

    return dsars
