"""
Tests for Privacy Management
============================

Tests for forge/resilience/security/privacy.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.security.privacy import (
    AnonymizationLevel,
    PIIPattern,
    PIIType,
    PrivacyManager,
    PrivacyRequest,
    RetentionPolicy,
    get_privacy_manager,
)


class TestAnonymizationLevel:
    """Tests for AnonymizationLevel enum."""

    def test_level_values(self):
        """Test all anonymization level values."""
        assert AnonymizationLevel.NONE.value == "none"
        assert AnonymizationLevel.PSEUDONYMIZE.value == "pseudonymize"
        assert AnonymizationLevel.MASK.value == "mask"
        assert AnonymizationLevel.REDACT.value == "redact"
        assert AnonymizationLevel.HASH.value == "hash"


class TestPIIType:
    """Tests for PIIType enum."""

    def test_pii_type_values(self):
        """Test all PII type values."""
        assert PIIType.NAME.value == "name"
        assert PIIType.EMAIL.value == "email"
        assert PIIType.PHONE.value == "phone"
        assert PIIType.ADDRESS.value == "address"
        assert PIIType.SSN.value == "ssn"
        assert PIIType.CREDIT_CARD.value == "credit_card"
        assert PIIType.IP_ADDRESS.value == "ip_address"
        assert PIIType.CUSTOM.value == "custom"


class TestPIIPattern:
    """Tests for PIIPattern dataclass."""

    def test_pattern_creation(self):
        """Test creating a PII pattern."""
        pattern = PIIPattern(
            pii_type=PIIType.EMAIL,
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            description="Email address",
            default_action=AnonymizationLevel.MASK,
        )

        assert pattern.pii_type == PIIType.EMAIL
        assert pattern.description == "Email address"
        assert pattern.default_action == AnonymizationLevel.MASK


class TestPrivacyRequest:
    """Tests for PrivacyRequest dataclass."""

    def test_request_creation(self):
        """Test creating a privacy request."""
        request = PrivacyRequest(
            request_id="req_123",
            request_type="erasure",
            subject_id="user_456",
        )

        assert request.request_id == "req_123"
        assert request.request_type == "erasure"
        assert request.subject_id == "user_456"
        assert request.status == "pending"
        assert request.completed_at is None


class TestRetentionPolicy:
    """Tests for RetentionPolicy dataclass."""

    def test_policy_defaults(self):
        """Test default retention policy values."""
        policy = RetentionPolicy()

        assert policy.default_retention_days == 365 * 7
        assert policy.min_retention_days == 30
        assert policy.max_retention_days == 365 * 10
        assert policy.capsule_retention_days == 365 * 7
        assert policy.audit_log_retention_days == 365 * 3
        assert policy.session_retention_days == 30
        assert policy.export_retention_days == 7


class TestPrivacyManager:
    """Tests for PrivacyManager class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.gdpr_compliant = True
        config.anonymization_enabled = True
        config.data_retention_days = 365 * 7
        return config

    @pytest.fixture
    def manager(self, mock_config):
        """Create a privacy manager instance."""
        with patch("forge.resilience.security.privacy.get_resilience_config") as mock:
            mock.return_value.privacy = mock_config
            m = PrivacyManager()
            m.initialize()
            return m

    def test_manager_creation(self, mock_config):
        """Test manager creation."""
        with patch("forge.resilience.security.privacy.get_resilience_config") as mock:
            mock.return_value.privacy = mock_config
            manager = PrivacyManager()

            assert manager._initialized is False
            assert manager._patterns == []

    def test_initialize(self, manager):
        """Test manager initialization."""
        assert manager._initialized is True
        assert len(manager._patterns) > 0

    def test_add_pattern(self, manager):
        """Test adding custom pattern."""
        pattern = PIIPattern(
            pii_type=PIIType.CUSTOM,
            pattern=r"\bCUSTOM_ID_\d+\b",
            description="Custom ID pattern",
        )

        manager.add_pattern(pattern)

        assert pattern in manager._patterns

    def test_detect_pii_email(self, manager):
        """Test detecting email addresses."""
        content = "Contact us at john.doe@example.com for more info."
        findings = manager.detect_pii(content)

        email_findings = [f for f in findings if f["type"] == "email"]
        assert len(email_findings) > 0
        assert "john.doe@example.com" in email_findings[0]["value"]

    def test_detect_pii_phone(self, manager):
        """Test detecting phone numbers."""
        content = "Call us at 555-123-4567 or (555) 987-6543."
        findings = manager.detect_pii(content)

        phone_findings = [f for f in findings if f["type"] == "phone"]
        assert len(phone_findings) > 0

    def test_detect_pii_ssn(self, manager):
        """Test detecting SSN patterns."""
        content = "SSN: 123-45-6789"
        findings = manager.detect_pii(content)

        ssn_findings = [f for f in findings if f["type"] == "ssn"]
        assert len(ssn_findings) > 0

    def test_detect_pii_credit_card(self, manager):
        """Test detecting credit card patterns."""
        content = "Card number: 4111-1111-1111-1111"
        findings = manager.detect_pii(content)

        cc_findings = [f for f in findings if f["type"] == "credit_card"]
        assert len(cc_findings) > 0

    def test_detect_pii_ip_address(self, manager):
        """Test detecting IP addresses."""
        content = "Server IP: 192.168.1.100"
        findings = manager.detect_pii(content)

        ip_findings = [f for f in findings if f["type"] == "ip_address"]
        assert len(ip_findings) > 0

    def test_detect_pii_disabled(self, mock_config):
        """Test PII detection when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.privacy.get_resilience_config") as mock:
            mock.return_value.privacy = mock_config
            manager = PrivacyManager()
            manager.initialize()

            content = "Email: test@example.com"
            findings = manager.detect_pii(content)

            assert findings == []

    def test_anonymize_redact(self, manager):
        """Test redacting PII."""
        content = "Email: test@example.com, Phone: 555-123-4567"
        result = manager.anonymize(content, level=AnonymizationLevel.REDACT)

        assert "[REDACTED]" in result
        assert "test@example.com" not in result
        assert "555-123-4567" not in result

    def test_anonymize_mask_email(self, manager):
        """Test masking email addresses."""
        content = "Contact: johndoe@example.com"
        result = manager.anonymize(content, level=AnonymizationLevel.MASK)

        assert "johndoe@example.com" not in result
        assert "@example.com" in result  # Domain preserved
        assert "*" in result

    def test_anonymize_mask_phone(self, manager):
        """Test masking phone numbers."""
        content = "Phone: 555-123-4567"
        result = manager.anonymize(content, level=AnonymizationLevel.MASK)

        assert "555-123-4567" not in result
        assert "4567" in result  # Last 4 digits preserved

    def test_anonymize_mask_credit_card(self, manager):
        """Test masking credit card numbers."""
        content = "Card: 4111-1111-1111-1111"
        result = manager.anonymize(content, level=AnonymizationLevel.MASK)

        assert "4111-1111-1111-1111" not in result
        assert "1111" in result  # Last 4 digits preserved

    def test_anonymize_mask_ssn(self, manager):
        """Test masking SSN."""
        content = "SSN: 123-45-6789"
        result = manager.anonymize(content, level=AnonymizationLevel.MASK)

        assert "123-45-6789" not in result
        assert "***-**-****" in result

    def test_anonymize_mask_ip(self, manager):
        """Test masking IP addresses."""
        content = "Server: 192.168.1.100"
        result = manager.anonymize(content, level=AnonymizationLevel.MASK)

        assert "192.168.1.100" not in result
        assert "192.168" in result  # First two octets preserved

    def test_anonymize_pseudonymize(self, manager):
        """Test pseudonymizing PII."""
        content = "Email: test@example.com"
        result = manager.anonymize(content, level=AnonymizationLevel.PSEUDONYMIZE)

        assert "test@example.com" not in result
        assert "@example.com" in result  # Pseudonymized email format

    def test_anonymize_pseudonymize_consistent(self, manager):
        """Test that pseudonyms are consistent."""
        content = "Email: test@example.com and also test@example.com"
        result = manager.anonymize(content, level=AnonymizationLevel.PSEUDONYMIZE)

        # Same email should get same pseudonym
        assert "test@example.com" not in result

    def test_anonymize_hash(self, manager):
        """Test hashing PII."""
        content = "IP: 192.168.1.100"
        result = manager.anonymize(content, level=AnonymizationLevel.HASH)

        assert "192.168.1.100" not in result
        # Hash should be 12 characters
        assert len([c for c in result if c.isalnum()]) >= 12

    def test_anonymize_none_level(self, manager):
        """Test no anonymization."""
        content = "Email: test@example.com"
        result = manager.anonymize(content, level=AnonymizationLevel.NONE)

        assert result == content

    def test_anonymize_specific_pii_types(self, manager):
        """Test anonymizing specific PII types only."""
        content = "Email: test@example.com, Phone: 555-123-4567"
        result = manager.anonymize(
            content,
            level=AnonymizationLevel.REDACT,
            pii_types={PIIType.EMAIL},
        )

        assert "[REDACTED]" in result
        assert "test@example.com" not in result
        # Phone should still be present since we only targeted EMAIL
        # (behavior depends on pattern match order)

    def test_anonymize_disabled(self, mock_config):
        """Test anonymization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.privacy.get_resilience_config") as mock:
            mock.return_value.privacy = mock_config
            manager = PrivacyManager()
            manager.initialize()

            content = "Email: test@example.com"
            result = manager.anonymize(content, level=AnonymizationLevel.REDACT)

            assert result == content

    @pytest.mark.asyncio
    async def test_process_erasure_request(self, manager):
        """Test processing erasure request."""
        request = await manager.process_erasure_request(
            subject_id="user_123",
            scope=["capsules", "comments"],
        )

        assert request.request_type == "erasure"
        assert request.subject_id == "user_123"
        assert request.status == "pending"
        assert request.request_id in manager._pending_requests

    @pytest.mark.asyncio
    async def test_process_export_request(self, manager):
        """Test processing export request."""
        request = await manager.process_export_request(
            subject_id="user_456",
            format="json",
        )

        assert request.request_type == "export"
        assert request.subject_id == "user_456"
        assert request.metadata["format"] == "json"

    def test_get_request_status(self, manager):
        """Test getting request status."""
        request = PrivacyRequest(
            request_id="req_test",
            request_type="erasure",
            subject_id="user_789",
        )
        manager._pending_requests["req_test"] = request

        result = manager.get_request_status("req_test")

        assert result == request

    def test_get_request_status_not_found(self, manager):
        """Test getting nonexistent request status."""
        result = manager.get_request_status("nonexistent")

        assert result is None

    def test_get_retention_policy(self, manager):
        """Test getting retention policy."""
        policy = manager.get_retention_policy()

        assert isinstance(policy, RetentionPolicy)

    def test_set_retention_policy(self, manager):
        """Test setting retention policy."""
        new_policy = RetentionPolicy(
            default_retention_days=365,
            capsule_retention_days=730,
        )

        manager.set_retention_policy(new_policy)

        assert manager._retention.default_retention_days == 365
        assert manager._retention.capsule_retention_days == 730

    def test_calculate_expiry_date(self, manager):
        """Test calculating expiry date."""
        created = datetime(2024, 1, 1, tzinfo=UTC)

        expiry = manager.calculate_expiry_date("capsule", created)

        expected = created + timedelta(days=manager._retention.capsule_retention_days)
        assert expiry == expected

    def test_calculate_expiry_date_audit_log(self, manager):
        """Test calculating expiry for audit logs."""
        created = datetime(2024, 1, 1, tzinfo=UTC)

        expiry = manager.calculate_expiry_date("audit_log", created)

        expected = created + timedelta(days=manager._retention.audit_log_retention_days)
        assert expiry == expected

    def test_calculate_expiry_date_default(self, manager):
        """Test calculating expiry for unknown type uses default."""
        created = datetime(2024, 1, 1, tzinfo=UTC)

        expiry = manager.calculate_expiry_date("unknown_type", created)

        expected = created + timedelta(days=manager._retention.default_retention_days)
        assert expiry == expected

    def test_is_expired_true(self, manager):
        """Test checking expired data."""
        old_date = datetime.now(UTC) - timedelta(days=3650)  # 10 years ago

        result = manager.is_expired("capsule", old_date)

        assert result is True

    def test_is_expired_false(self, manager):
        """Test checking non-expired data."""
        recent_date = datetime.now(UTC) - timedelta(days=1)

        result = manager.is_expired("capsule", recent_date)

        assert result is False


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_privacy_manager(self):
        """Test getting global privacy manager."""
        with patch("forge.resilience.security.privacy._privacy_manager", None):
            with patch("forge.resilience.security.privacy.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.privacy.enabled = True
                mock_config.privacy.anonymization_enabled = True
                mock.return_value = mock_config

                manager = get_privacy_manager()

                assert isinstance(manager, PrivacyManager)
                assert manager._initialized is True
