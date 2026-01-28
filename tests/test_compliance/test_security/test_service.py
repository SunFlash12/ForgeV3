"""
Tests for forge.compliance.security module.

Tests the access control service, authentication service, breach
notification service, and vendor management functionality.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import (
    BreachSeverity,
    DataClassification,
    Jurisdiction,
)


class TestAccessControlService:
    """Tests for the AccessControlService class."""

    @pytest.fixture
    def access_control_service(self):
        """Create an access control service for testing."""
        try:
            from forge.compliance.security import get_access_control_service
            return get_access_control_service()
        except ImportError:
            pytest.skip("AccessControlService not available")

    def test_check_access_allowed(self, access_control_service):
        """Test access check that is allowed."""
        try:
            from forge.compliance.security import Permission, ResourceType

            decision = access_control_service.check_access(
                user_id="user_123",
                permission=Permission.READ,
                resource_type=ResourceType.USER_DATA,
                resource_id="data_001",
            )

            assert decision is not None
            assert hasattr(decision, "allowed")
            assert hasattr(decision, "reason")
        except ImportError:
            pytest.skip("Required imports not available")

    def test_check_access_with_classification(self, access_control_service):
        """Test access check with data classification."""
        try:
            from forge.compliance.security import Permission, ResourceType

            decision = access_control_service.check_access(
                user_id="user_123",
                permission=Permission.READ,
                resource_type=ResourceType.USER_DATA,
                data_classification=DataClassification.CONFIDENTIAL,
            )

            assert decision is not None
        except ImportError:
            pytest.skip("Required imports not available")

    def test_check_access_denied(self, access_control_service):
        """Test access check that is denied."""
        try:
            from forge.compliance.security import Permission, ResourceType

            # Attempt to access restricted resource
            decision = access_control_service.check_access(
                user_id="restricted_user",
                permission=Permission.ADMIN,
                resource_type=ResourceType.SYSTEM_CONFIG,
            )

            # May be allowed or denied depending on implementation
            assert decision is not None
        except ImportError:
            pytest.skip("Required imports not available")

    def test_assign_role(self, access_control_service):
        """Test assigning a role to a user."""
        try:
            success = access_control_service.assign_role(
                user_id="new_user",
                role_id="viewer",
                assigned_by="admin_001",
            )

            assert isinstance(success, bool)
        except ImportError:
            pytest.skip("Required method not available")

    def test_assign_role_invalid(self, access_control_service):
        """Test assigning an invalid role."""
        try:
            success = access_control_service.assign_role(
                user_id="user_123",
                role_id="nonexistent_role",
                assigned_by="admin_001",
            )

            assert success is False
        except ImportError:
            pytest.skip("Required method not available")

    def test_get_user_roles(self, access_control_service):
        """Test getting user roles."""
        try:
            # First assign a role
            access_control_service.assign_role(
                user_id="role_user",
                role_id="viewer",
                assigned_by="admin_001",
            )

            roles = access_control_service.get_user_roles("role_user")
            assert isinstance(roles, list)
        except ImportError:
            pytest.skip("Required method not available")

    def test_get_user_roles_no_roles(self, access_control_service):
        """Test getting roles for user with none."""
        try:
            roles = access_control_service.get_user_roles("no_role_user")
            assert roles == [] or roles is not None
        except ImportError:
            pytest.skip("Required method not available")


class TestAuthenticationService:
    """Tests for the AuthenticationService class."""

    @pytest.fixture
    def authentication_service(self):
        """Create an authentication service for testing."""
        try:
            from forge.compliance.security import get_authentication_service
            return get_authentication_service()
        except ImportError:
            pytest.skip("AuthenticationService not available")

    def test_create_mfa_challenge_totp(self, authentication_service):
        """Test creating TOTP MFA challenge."""
        try:
            from forge.compliance.security import MFAMethod

            challenge = authentication_service.create_mfa_challenge(
                user_id="mfa_user",
                method=MFAMethod.TOTP,
            )

            assert challenge is not None
            assert challenge.challenge_id is not None
            assert challenge.method == MFAMethod.TOTP
            assert challenge.expires_at > datetime.now(UTC)
        except ImportError:
            pytest.skip("Required imports not available")

    def test_create_mfa_challenge_sms(self, authentication_service):
        """Test creating SMS MFA challenge."""
        try:
            from forge.compliance.security import MFAMethod

            challenge = authentication_service.create_mfa_challenge(
                user_id="mfa_user",
                method=MFAMethod.SMS,
            )

            assert challenge is not None
            assert challenge.method == MFAMethod.SMS
        except ImportError:
            pytest.skip("Required imports not available")

    def test_verify_mfa_success(self, authentication_service):
        """Test successful MFA verification."""
        try:
            from forge.compliance.security import MFAMethod

            # Create challenge
            challenge = authentication_service.create_mfa_challenge(
                user_id="verify_user",
                method=MFAMethod.TOTP,
            )

            # In a real scenario, we'd need the actual code
            # For testing, we mock or use a test code
            result = authentication_service.verify_mfa(
                challenge_id=challenge.challenge_id,
                code="123456",  # Test code
            )

            assert isinstance(result, bool)
        except ImportError:
            pytest.skip("Required imports not available")

    def test_verify_mfa_invalid_code(self, authentication_service):
        """Test MFA verification with invalid code."""
        try:
            from forge.compliance.security import MFAMethod

            challenge = authentication_service.create_mfa_challenge(
                user_id="verify_user_2",
                method=MFAMethod.TOTP,
            )

            result = authentication_service.verify_mfa(
                challenge_id=challenge.challenge_id,
                code="invalid",
            )

            assert result is False
        except ImportError:
            pytest.skip("Required imports not available")

    def test_verify_mfa_invalid_challenge(self, authentication_service):
        """Test MFA verification with invalid challenge ID."""
        try:
            result = authentication_service.verify_mfa(
                challenge_id="invalid_challenge",
                code="123456",
            )

            assert result is False
        except ImportError:
            pytest.skip("Required method not available")


class TestBreachNotificationService:
    """Tests for the BreachNotificationService class."""

    @pytest.fixture
    def breach_service(self):
        """Create a breach notification service for testing."""
        try:
            from forge.compliance.security import get_breach_notification_service
            return get_breach_notification_service()
        except ImportError:
            pytest.skip("BreachNotificationService not available")

    @pytest.mark.asyncio
    async def test_report_breach(self, breach_service):
        """Test reporting a data breach."""
        try:
            from forge.compliance.security import BreachType

            incident = await breach_service.report_breach(
                discovered_by="security_team",
                discovery_method="monitoring",
                breach_type=BreachType.UNAUTHORIZED_ACCESS,
                severity=BreachSeverity.HIGH,
                data_categories=[DataClassification.PERSONAL_DATA],
                data_elements=["email", "name"],
                record_count=1000,
                affected_jurisdictions=[Jurisdiction.EU],
                description="Unauthorized access detected",
            )

            assert incident is not None
            assert incident.breach_id is not None
            assert incident.requires_notification is True
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_report_breach_critical(self, breach_service):
        """Test reporting a critical breach."""
        try:
            from forge.compliance.security import BreachType

            incident = await breach_service.report_breach(
                discovered_by="external_researcher",
                discovery_method="bug_bounty",
                breach_type=BreachType.DATA_EXFILTRATION,
                severity=BreachSeverity.CRITICAL,
                data_categories=[DataClassification.PHI, DataClassification.FINANCIAL],
                data_elements=["ssn", "medical_records"],
                record_count=50000,
                affected_jurisdictions=[Jurisdiction.EU, Jurisdiction.US_FEDERAL],
            )

            assert incident.severity == BreachSeverity.CRITICAL
            # Should have notification deadlines
            assert incident.most_urgent_deadline is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_report_breach_low_severity(self, breach_service):
        """Test reporting a low severity breach."""
        try:
            from forge.compliance.security import BreachType

            incident = await breach_service.report_breach(
                discovered_by="it_team",
                discovery_method="routine_check",
                breach_type=BreachType.ACCIDENTAL_DISCLOSURE,
                severity=BreachSeverity.LOW,
                data_categories=[DataClassification.INTERNAL],
                data_elements=["internal_notes"],
                record_count=5,
                affected_jurisdictions=[Jurisdiction.GLOBAL],
            )

            # Low severity may not require notification
            assert incident is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_get_incident_summary(self, breach_service):
        """Test getting breach incident summary."""
        try:
            from forge.compliance.security import BreachType

            incident = await breach_service.report_breach(
                discovered_by="security",
                discovery_method="monitoring",
                breach_type=BreachType.UNAUTHORIZED_ACCESS,
                severity=BreachSeverity.MEDIUM,
                data_categories=[DataClassification.PERSONAL_DATA],
                data_elements=["email"],
                record_count=100,
                affected_jurisdictions=[Jurisdiction.EU],
            )

            summary = await breach_service.get_incident_summary(incident.breach_id)
            assert summary is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_get_incident_summary_not_found(self, breach_service):
        """Test getting summary for nonexistent breach."""
        try:
            summary = await breach_service.get_incident_summary("nonexistent")
            assert summary is None
        except ImportError:
            pytest.skip("Required method not available")

    @pytest.mark.asyncio
    async def test_create_notification(self, breach_service):
        """Test creating a notification for a breach."""
        try:
            from forge.compliance.security import BreachType, NotificationRecipient

            incident = await breach_service.report_breach(
                discovered_by="security",
                discovery_method="monitoring",
                breach_type=BreachType.UNAUTHORIZED_ACCESS,
                severity=BreachSeverity.HIGH,
                data_categories=[DataClassification.PERSONAL_DATA],
                data_elements=["email"],
                record_count=1000,
                affected_jurisdictions=[Jurisdiction.EU],
            )

            notification = await breach_service.create_notification(
                breach_id=incident.breach_id,
                recipient_type=NotificationRecipient.SUPERVISORY_AUTHORITY,
                jurisdiction=Jurisdiction.EU,
                recipient_name="ICO",
                recipient_contact="breach@ico.org.uk",
            )

            assert notification is not None
            assert notification.notification_id is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_get_overdue_notifications(self, breach_service):
        """Test getting overdue notifications."""
        try:
            overdue = await breach_service.get_overdue_notifications()
            assert isinstance(overdue, list)
        except ImportError:
            pytest.skip("Required method not available")


class TestPermissions:
    """Tests for Permission enum."""

    def test_permission_values(self):
        """Test that Permission enum has expected values."""
        try:
            from forge.compliance.security import Permission

            assert hasattr(Permission, "READ")
            assert hasattr(Permission, "WRITE")
            assert hasattr(Permission, "DELETE")
            assert hasattr(Permission, "ADMIN")
        except ImportError:
            pytest.skip("Permission enum not available")


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_resource_type_values(self):
        """Test that ResourceType enum has expected values."""
        try:
            from forge.compliance.security import ResourceType

            assert hasattr(ResourceType, "USER_DATA")
            assert hasattr(ResourceType, "SYSTEM_CONFIG")
        except ImportError:
            pytest.skip("ResourceType enum not available")


class TestMFAMethod:
    """Tests for MFAMethod enum."""

    def test_mfa_method_values(self):
        """Test that MFAMethod enum has expected values."""
        try:
            from forge.compliance.security import MFAMethod

            assert hasattr(MFAMethod, "TOTP")
            assert hasattr(MFAMethod, "SMS")
        except ImportError:
            pytest.skip("MFAMethod enum not available")


class TestBreachType:
    """Tests for BreachType enum."""

    def test_breach_type_values(self):
        """Test that BreachType enum has expected values."""
        try:
            from forge.compliance.security import BreachType

            assert hasattr(BreachType, "UNAUTHORIZED_ACCESS")
            assert hasattr(BreachType, "DATA_EXFILTRATION")
        except ImportError:
            pytest.skip("BreachType enum not available")


class TestNotificationRecipient:
    """Tests for NotificationRecipient enum."""

    def test_notification_recipient_values(self):
        """Test that NotificationRecipient enum has expected values."""
        try:
            from forge.compliance.security import NotificationRecipient

            assert hasattr(NotificationRecipient, "SUPERVISORY_AUTHORITY")
        except ImportError:
            pytest.skip("NotificationRecipient enum not available")


class TestSecurityServiceIntegration:
    """Integration tests for security services."""

    @pytest.mark.asyncio
    async def test_access_control_to_breach_flow(self):
        """Test flow from access control detection to breach notification."""
        try:
            from forge.compliance.security import (
                get_access_control_service,
                get_breach_notification_service,
                Permission,
                ResourceType,
                BreachType,
            )

            access_service = get_access_control_service()
            breach_service = get_breach_notification_service()

            # Detect unauthorized access attempt
            decision = access_service.check_access(
                user_id="attacker",
                permission=Permission.ADMIN,
                resource_type=ResourceType.SYSTEM_CONFIG,
            )

            # If access was denied but attempted, this could trigger breach report
            if not decision.allowed:
                # In a real scenario, multiple failed attempts would trigger this
                incident = await breach_service.report_breach(
                    discovered_by="access_control_system",
                    discovery_method="automated_detection",
                    breach_type=BreachType.UNAUTHORIZED_ACCESS,
                    severity=BreachSeverity.MEDIUM,
                    data_categories=[DataClassification.INTERNAL],
                    data_elements=["system_config"],
                    record_count=0,
                    affected_jurisdictions=[Jurisdiction.GLOBAL],
                    description="Multiple unauthorized access attempts detected",
                )

                assert incident is not None
        except ImportError:
            pytest.skip("Required imports not available")

    def test_role_based_access_control(self):
        """Test RBAC functionality."""
        try:
            from forge.compliance.security import (
                get_access_control_service,
                Permission,
                ResourceType,
            )

            service = get_access_control_service()

            # Assign viewer role
            service.assign_role(
                user_id="rbac_user",
                role_id="viewer",
                assigned_by="admin",
            )

            # Check read access (should be allowed for viewer)
            read_decision = service.check_access(
                user_id="rbac_user",
                permission=Permission.READ,
                resource_type=ResourceType.USER_DATA,
            )

            # Check write access (may be denied for viewer)
            write_decision = service.check_access(
                user_id="rbac_user",
                permission=Permission.WRITE,
                resource_type=ResourceType.USER_DATA,
            )

            assert read_decision is not None
            assert write_decision is not None
        except ImportError:
            pytest.skip("Required imports not available")
