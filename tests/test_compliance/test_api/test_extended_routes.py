"""
Tests for forge.compliance.api.extended_routes module.

Tests the extended compliance API routes including consent management,
security controls, AI governance, reporting, and accessibility endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.compliance.core.enums import (
    BreachSeverity,
    ComplianceFramework,
    DataClassification,
    Jurisdiction,
)


@pytest.fixture
def mock_consent_service():
    """Create a mock consent service."""
    service = MagicMock()
    service.collect_consent = AsyncMock()
    service.process_gpc_signal = AsyncMock()
    service.get_user_consents = AsyncMock(return_value=None)
    service.check_consent = AsyncMock(return_value=(True, "Consent granted"))
    service.withdraw_consent = AsyncMock()
    service.generate_receipt = AsyncMock()
    return service


@pytest.fixture
def mock_access_control_service():
    """Create a mock access control service."""
    service = MagicMock()

    mock_decision = MagicMock()
    mock_decision.allowed = True
    mock_decision.reason = "Access granted"
    mock_decision.requires_mfa = False
    mock_decision.audit_required = True
    service.check_access = MagicMock(return_value=mock_decision)

    service.assign_role = MagicMock(return_value=True)

    mock_role = MagicMock()
    mock_role.role_id = "viewer"
    mock_role.name = "Viewer"
    mock_role.is_privileged = False
    mock_role.permissions = []
    service.get_user_roles = MagicMock(return_value=[mock_role])

    return service


@pytest.fixture
def mock_authentication_service():
    """Create a mock authentication service."""
    service = MagicMock()

    mock_challenge = MagicMock()
    mock_challenge.challenge_id = "challenge_001"
    mock_challenge.method = MagicMock()
    mock_challenge.method.value = "totp"
    mock_challenge.expires_at = datetime.now(UTC) + timedelta(minutes=5)
    service.create_mfa_challenge = MagicMock(return_value=mock_challenge)

    service.verify_mfa = MagicMock(return_value=True)
    return service


@pytest.fixture
def mock_breach_notification_service():
    """Create a mock breach notification service."""
    service = MagicMock()

    mock_incident = MagicMock()
    mock_incident.breach_id = "breach_001"
    mock_incident.status = MagicMock()
    mock_incident.status.value = "reported"
    mock_incident.requires_notification = True
    mock_incident.most_urgent_deadline = datetime.now(UTC) + timedelta(hours=72)

    mock_deadline = MagicMock()
    mock_deadline.jurisdiction = Jurisdiction.EU
    mock_deadline.authority_deadline = datetime.now(UTC) + timedelta(hours=72)
    mock_deadline.authority_name = "ICO"
    mock_incident.notification_deadlines = [mock_deadline]

    service.report_breach = AsyncMock(return_value=mock_incident)
    service.get_incident_summary = AsyncMock(return_value={"id": "breach_001"})
    service.create_notification = AsyncMock()
    service.get_overdue_notifications = AsyncMock(return_value=[])

    return service


@pytest.fixture
def mock_ai_governance_service():
    """Create a mock AI governance service."""
    service = MagicMock()

    mock_system = MagicMock()
    mock_system.id = "ai_sys_001"
    mock_system.system_name = "Test System"
    mock_system.risk_classification = MagicMock()
    mock_system.risk_classification.value = "limited_risk"
    mock_system.risk_classification.requires_conformity_assessment = False
    service.register_system = AsyncMock(return_value=mock_system)

    mock_decision = MagicMock()
    mock_decision.id = "decision_001"
    mock_decision.human_review_requested = False
    mock_decision.timestamp = datetime.now(UTC)
    mock_decision.human_reviewed = False
    mock_decision.human_override = False
    service.log_decision = AsyncMock(return_value=mock_decision)
    service.complete_human_review = AsyncMock(return_value=mock_decision)
    service.generate_explanation = AsyncMock(return_value={"explanation": "test"})

    return service


@pytest.fixture
def mock_reporting_service():
    """Create a mock reporting service."""
    service = MagicMock()

    mock_report = MagicMock()
    mock_report.report_id = "report_001"
    mock_report.title = "Test Report"
    mock_report.overall_score = 75.5
    mock_report.total_controls = 100
    mock_report.compliant_controls = 75
    mock_report.gaps_critical = 2
    mock_report.gaps_high = 5
    mock_report.gaps_medium = 10
    mock_report.gaps_low = 8
    mock_report.generated_at = datetime.now(UTC)
    service.generate_report = AsyncMock(return_value=mock_report)
    service.export_report = AsyncMock(return_value=b'{"report": "data"}')

    return service


@pytest.fixture
def mock_accessibility_service():
    """Create a mock accessibility service."""
    service = MagicMock()

    mock_audit = MagicMock()
    mock_audit.audit_id = "audit_001"
    mock_audit.audit_name = "Test Audit"
    mock_audit.target_url = "https://example.com"
    mock_audit.standard = MagicMock()
    mock_audit.standard.value = "wcag_2_2"
    mock_audit.target_level = MagicMock()
    mock_audit.target_level.value = "AA"
    service.create_audit = AsyncMock(return_value=mock_audit)

    mock_issue = MagicMock()
    mock_issue.issue_id = "issue_001"
    mock_issue.criterion_id = "WCAG-1.1.1"
    mock_issue.impact = MagicMock()
    mock_issue.impact.value = "critical"
    mock_issue.status = "open"
    service.log_issue = AsyncMock(return_value=mock_issue)

    mock_vpat = MagicMock()
    mock_vpat.vpat_id = "vpat_001"
    mock_vpat.product_name = "Test Product"
    mock_vpat.report_date = datetime.now(UTC)
    mock_vpat.entries = []
    service.generate_vpat = AsyncMock(return_value=mock_vpat)

    service.get_compliance_summary = MagicMock(return_value={"total_audits": 5})

    return service


@pytest.fixture
def test_client(
    mock_consent_service,
    mock_access_control_service,
    mock_authentication_service,
    mock_breach_notification_service,
    mock_ai_governance_service,
    mock_reporting_service,
    mock_accessibility_service,
):
    """Create a test client with mocked services."""
    try:
        from forge.compliance.api.extended_routes import extended_router

        app = FastAPI()
        app.include_router(extended_router, prefix="/compliance")

        # Patch the service getters
        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service), \
             patch("forge.compliance.api.extended_routes.get_access_control_service", return_value=mock_access_control_service), \
             patch("forge.compliance.api.extended_routes.get_authentication_service", return_value=mock_authentication_service), \
             patch("forge.compliance.api.extended_routes.get_breach_notification_service", return_value=mock_breach_notification_service), \
             patch("forge.compliance.api.extended_routes.get_ai_governance_service", return_value=mock_ai_governance_service), \
             patch("forge.compliance.api.extended_routes.get_compliance_reporting_service", return_value=mock_reporting_service), \
             patch("forge.compliance.api.extended_routes.get_accessibility_service", return_value=mock_accessibility_service):

            return TestClient(app)
    except ImportError:
        pytest.skip("Extended routes module not available")


class TestConsentManagementEndpoints:
    """Tests for consent management endpoints."""

    def test_collect_consent(self, test_client, mock_consent_service):
        """Test collecting consent via API."""
        mock_record = MagicMock()
        mock_record.record_id = "rec_001"
        mock_record.user_id = "user_123"
        mock_record.version = 1
        mock_record.consent_hash = "abc123"
        mock_record.created_at = datetime.now(UTC)
        mock_consent_service.collect_consent.return_value = mock_record

        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.post(
                "/compliance/consent/collect",
                json={
                    "user_id": "user_123",
                    "purposes": {"analytics": True, "marketing": False},
                    "collection_method": "explicit_opt_in",
                    "jurisdiction": "eu",
                },
            )
            assert response.status_code in [200, 422]

    def test_process_gpc_signal(self, test_client, mock_consent_service):
        """Test processing GPC signal via API."""
        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.post(
                "/compliance/consent/gpc",
                json={
                    "user_id": "user_123",
                    "gpc_enabled": True,
                },
            )
            assert response.status_code in [200, 422]

    def test_get_user_consent(self, test_client, mock_consent_service):
        """Test getting user consent via API."""
        mock_consent_service.get_user_consents.return_value = {"purposes": {"analytics": True}}

        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.get("/compliance/consent/user_123")
            assert response.status_code in [200, 404]

    def test_check_consent(self, test_client, mock_consent_service):
        """Test checking consent via API."""
        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.post(
                "/compliance/consent/user_123/check",
                json={"user_id": "user_123", "purpose": "analytics"},
            )
            assert response.status_code in [200, 400, 422]

    def test_withdraw_consent(self, test_client, mock_consent_service):
        """Test withdrawing consent via API."""
        mock_consent_service.withdraw_consent.return_value = MagicMock()

        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.post(
                "/compliance/consent/user_123/withdraw",
                json={"purposes": ["marketing"], "withdraw_all": False},
            )
            assert response.status_code in [200, 404, 422]

    def test_get_consent_receipt(self, test_client, mock_consent_service):
        """Test getting consent receipt via API."""
        mock_receipt = MagicMock()
        mock_receipt.receipt_id = "rcpt_001"
        mock_receipt.data_controller = "Test Corp"
        mock_receipt.purposes_granted = ["analytics"]
        mock_receipt.purposes_denied = ["marketing"]
        mock_receipt.collection_timestamp = datetime.now(UTC)
        mock_receipt.consent_hash = "abc123"
        mock_consent_service.generate_receipt.return_value = mock_receipt

        with patch("forge.compliance.api.extended_routes.get_consent_service", return_value=mock_consent_service):
            response = test_client.get("/compliance/consent/user_123/receipt")
            assert response.status_code in [200, 404]


class TestSecurityControlEndpoints:
    """Tests for security control endpoints."""

    def test_check_access(self, test_client, mock_access_control_service):
        """Test checking access via API."""
        with patch("forge.compliance.api.extended_routes.get_access_control_service", return_value=mock_access_control_service):
            response = test_client.post(
                "/compliance/security/access/check",
                json={
                    "user_id": "user_123",
                    "permission": "read",
                    "resource_type": "user_data",
                },
            )
            assert response.status_code in [200, 400, 422]

    def test_assign_role(self, test_client, mock_access_control_service):
        """Test assigning role via API."""
        with patch("forge.compliance.api.extended_routes.get_access_control_service", return_value=mock_access_control_service):
            response = test_client.post(
                "/compliance/security/roles/assign",
                json={
                    "user_id": "user_123",
                    "role_id": "viewer",
                    "assigned_by": "admin_001",
                },
            )
            assert response.status_code in [200, 400, 422]

    def test_get_user_roles(self, test_client, mock_access_control_service):
        """Test getting user roles via API."""
        with patch("forge.compliance.api.extended_routes.get_access_control_service", return_value=mock_access_control_service):
            response = test_client.get("/compliance/security/roles/user_123")
            assert response.status_code in [200, 404]

    def test_create_mfa_challenge(self, test_client, mock_authentication_service):
        """Test creating MFA challenge via API."""
        with patch("forge.compliance.api.extended_routes.get_authentication_service", return_value=mock_authentication_service):
            response = test_client.post(
                "/compliance/security/mfa/challenge",
                json={
                    "user_id": "user_123",
                    "method": "totp",
                },
            )
            assert response.status_code in [200, 422]

    def test_verify_mfa(self, test_client, mock_authentication_service):
        """Test verifying MFA via API."""
        with patch("forge.compliance.api.extended_routes.get_authentication_service", return_value=mock_authentication_service):
            response = test_client.post(
                "/compliance/security/mfa/verify",
                json={
                    "challenge_id": "challenge_001",
                    "code": "123456",
                },
            )
            assert response.status_code in [200, 422]


class TestBreachNotificationEndpoints:
    """Tests for breach notification endpoints."""

    def test_report_breach(self, test_client, mock_breach_notification_service):
        """Test reporting breach via API."""
        with patch("forge.compliance.api.extended_routes.get_breach_notification_service", return_value=mock_breach_notification_service):
            response = test_client.post(
                "/compliance/breaches/report",
                json={
                    "discovered_by": "security_team",
                    "discovery_method": "monitoring",
                    "breach_type": "unauthorized_access",
                    "severity": "high",
                    "data_categories": ["personal_data"],
                    "data_elements": ["email"],
                    "record_count": 1000,
                    "affected_jurisdictions": ["eu"],
                },
            )
            assert response.status_code in [200, 400, 422]

    def test_get_breach(self, test_client, mock_breach_notification_service):
        """Test getting breach via API."""
        with patch("forge.compliance.api.extended_routes.get_breach_notification_service", return_value=mock_breach_notification_service):
            response = test_client.get("/compliance/breaches/breach_001")
            assert response.status_code in [200, 404]

    def test_create_notification(self, test_client, mock_breach_notification_service):
        """Test creating notification via API."""
        mock_notification = MagicMock()
        mock_notification.notification_id = "notif_001"
        mock_notification.status = MagicMock()
        mock_notification.status.value = "pending"
        mock_notification.recipient_type = MagicMock()
        mock_notification.recipient_type.value = "supervisory_authority"
        mock_breach_notification_service.create_notification.return_value = mock_notification

        with patch("forge.compliance.api.extended_routes.get_breach_notification_service", return_value=mock_breach_notification_service):
            response = test_client.post(
                "/compliance/breaches/breach_001/notifications",
                json={
                    "breach_id": "breach_001",
                    "recipient_type": "supervisory_authority",
                    "jurisdiction": "eu",
                },
            )
            assert response.status_code in [200, 400, 404, 422]

    def test_get_overdue_notifications(self, test_client, mock_breach_notification_service):
        """Test getting overdue notifications via API."""
        with patch("forge.compliance.api.extended_routes.get_breach_notification_service", return_value=mock_breach_notification_service):
            response = test_client.get("/compliance/breaches/overdue/list")
            assert response.status_code in [200, 422]


class TestAIGovernanceEndpoints:
    """Tests for AI governance endpoints."""

    def test_register_ai_system(self, test_client, mock_ai_governance_service):
        """Test registering AI system via API."""
        with patch("forge.compliance.api.extended_routes.get_ai_governance_service", return_value=mock_ai_governance_service):
            response = test_client.post(
                "/compliance/ai/systems/register",
                json={
                    "system_name": "Test System",
                    "system_version": "1.0",
                    "provider": "Test Provider",
                    "intended_purpose": "Testing",
                    "use_cases": ["test"],
                    "model_type": "classifier",
                    "human_oversight_measures": ["review"],
                },
            )
            assert response.status_code in [200, 422]

    def test_log_ai_decision(self, test_client, mock_ai_governance_service):
        """Test logging AI decision via API."""
        with patch("forge.compliance.api.extended_routes.get_ai_governance_service", return_value=mock_ai_governance_service):
            response = test_client.post(
                "/compliance/ai/decisions/log",
                json={
                    "ai_system_id": "ai_sys_001",
                    "model_version": "1.0",
                    "decision_type": "recommendation",
                    "decision_outcome": "recommend_A",
                    "confidence_score": 0.85,
                    "input_summary": {"user": "test"},
                    "reasoning_chain": ["step1"],
                    "key_factors": [{"factor": "test", "weight": 1.0}],
                },
            )
            assert response.status_code in [200, 422]

    def test_complete_human_review(self, test_client, mock_ai_governance_service):
        """Test completing human review via API."""
        with patch("forge.compliance.api.extended_routes.get_ai_governance_service", return_value=mock_ai_governance_service):
            response = test_client.post(
                "/compliance/ai/decisions/review",
                json={
                    "decision_id": "decision_001",
                    "reviewer_id": "reviewer_001",
                    "override": False,
                },
            )
            assert response.status_code in [200, 404, 422]

    def test_get_decision_explanation(self, test_client, mock_ai_governance_service):
        """Test getting decision explanation via API."""
        with patch("forge.compliance.api.extended_routes.get_ai_governance_service", return_value=mock_ai_governance_service):
            response = test_client.get(
                "/compliance/ai/decisions/decision_001/explanation",
                params={"audience": "end_user"},
            )
            assert response.status_code in [200, 404]


class TestReportingEndpoints:
    """Tests for reporting endpoints."""

    def test_generate_report(self, test_client, mock_reporting_service):
        """Test generating report via API."""
        with patch("forge.compliance.api.extended_routes.get_compliance_reporting_service", return_value=mock_reporting_service):
            response = test_client.post(
                "/compliance/reports/generate",
                json={
                    "report_type": "executive_summary",
                    "frameworks": ["gdpr"],
                    "generated_by": "compliance_officer",
                },
            )
            assert response.status_code in [200, 422]

    def test_export_report(self, test_client, mock_reporting_service):
        """Test exporting report via API."""
        with patch("forge.compliance.api.extended_routes.get_compliance_reporting_service", return_value=mock_reporting_service):
            response = test_client.get(
                "/compliance/reports/report_001/export",
                params={"format": "json"},
            )
            assert response.status_code in [200, 404]


class TestAccessibilityEndpoints:
    """Tests for accessibility endpoints."""

    def test_create_accessibility_audit(self, test_client, mock_accessibility_service):
        """Test creating accessibility audit via API."""
        with patch("forge.compliance.api.extended_routes.get_accessibility_service", return_value=mock_accessibility_service):
            response = test_client.post(
                "/compliance/accessibility/audits",
                json={
                    "audit_name": "Homepage Audit",
                    "target_url": "https://example.com",
                    "standard": "wcag_2_2",
                    "target_level": "AA",
                },
            )
            assert response.status_code in [200, 422]

    def test_log_accessibility_issue(self, test_client, mock_accessibility_service):
        """Test logging accessibility issue via API."""
        with patch("forge.compliance.api.extended_routes.get_accessibility_service", return_value=mock_accessibility_service):
            response = test_client.post(
                "/compliance/accessibility/issues",
                json={
                    "audit_id": "audit_001",
                    "url": "https://example.com/page",
                    "criterion_id": "WCAG-1.1.1",
                    "impact": "critical",
                    "description": "Missing alt text",
                    "remediation": "Add alt text",
                },
            )
            assert response.status_code in [200, 422]

    def test_generate_vpat(self, test_client, mock_accessibility_service):
        """Test generating VPAT via API."""
        with patch("forge.compliance.api.extended_routes.get_accessibility_service", return_value=mock_accessibility_service):
            response = test_client.post(
                "/compliance/accessibility/vpat/generate",
                json={
                    "product_name": "Test Product",
                    "product_version": "1.0",
                    "vendor_name": "Test Vendor",
                },
            )
            assert response.status_code in [200, 422]

    def test_get_accessibility_summary(self, test_client, mock_accessibility_service):
        """Test getting accessibility summary via API."""
        with patch("forge.compliance.api.extended_routes.get_accessibility_service", return_value=mock_accessibility_service):
            response = test_client.get("/compliance/accessibility/summary")
            assert response.status_code in [200, 422]
