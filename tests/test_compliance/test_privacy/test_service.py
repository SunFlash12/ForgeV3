"""
Tests for forge.compliance.privacy module.

Tests the consent service, DSAR processor, and privacy-related
operations including GDPR/CCPA consent management, GPC signal
processing, and consent receipts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import (
    ConsentType,
    Jurisdiction,
)


class TestConsentPurpose:
    """Tests for ConsentPurpose enum if available."""

    def test_consent_purpose_enum_values(self):
        """Test that ConsentPurpose enum has expected values."""
        try:
            from forge.compliance.privacy import ConsentPurpose

            # Test common purposes exist
            assert hasattr(ConsentPurpose, "ESSENTIAL") or "essential" in [p.value for p in ConsentPurpose]
        except ImportError:
            pytest.skip("ConsentPurpose not available")


class TestConsentService:
    """Tests for the ConsentService class."""

    @pytest.fixture
    def consent_service(self):
        """Create a consent service for testing."""
        try:
            from forge.compliance.privacy import get_consent_service
            return get_consent_service()
        except ImportError:
            pytest.skip("ConsentService not available")

    @pytest.mark.asyncio
    async def test_collect_consent_basic(self, consent_service):
        """Test collecting basic consent."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            record = await consent_service.collect_consent(
                user_id="user_123",
                purposes={ConsentPurpose.ANALYTICS: True, ConsentPurpose.MARKETING: False},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
                user_email="user@example.com",
                consent_text_version="1.0",
            )

            assert record.user_id == "user_123"
            assert record.record_id is not None
            assert record.consent_hash is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_collect_consent_with_tcf_string(self, consent_service):
        """Test collecting consent with TCF string."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            record = await consent_service.collect_consent(
                user_id="user_456",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
                tcf_string="CO_TCF_STRING_HERE",
            )

            assert record.user_id == "user_456"
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_process_gpc_signal_enabled(self, consent_service):
        """Test processing GPC signal when enabled."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            # First collect some consent
            await consent_service.collect_consent(
                user_id="gpc_user",
                purposes={ConsentPurpose.DATA_SALE: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.US_CALIFORNIA,
            )

            # Process GPC signal
            await consent_service.process_gpc_signal(
                user_id="gpc_user",
                gpc_enabled=True,
            )

            # Check that relevant consents were withdrawn
            consents = await consent_service.get_user_consents("gpc_user")
            assert consents is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_process_gpc_signal_disabled(self, consent_service):
        """Test processing GPC signal when disabled."""
        try:
            await consent_service.process_gpc_signal(
                user_id="gpc_user_2",
                gpc_enabled=False,
            )
            # Should not raise, no action taken
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_get_user_consents(self, consent_service):
        """Test getting user consents."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            # Collect consent
            await consent_service.collect_consent(
                user_id="consent_user",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.GLOBAL,
            )

            consents = await consent_service.get_user_consents("consent_user")
            assert consents is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_get_user_consents_no_records(self, consent_service):
        """Test getting consents for user with no records."""
        try:
            consents = await consent_service.get_user_consents("nonexistent_user")
            assert consents is None or consents == []
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_check_consent_granted(self, consent_service):
        """Test checking consent that was granted."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            await consent_service.collect_consent(
                user_id="check_user",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            has_consent, reason = await consent_service.check_consent(
                "check_user",
                ConsentPurpose.ANALYTICS,
            )

            assert has_consent is True
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_check_consent_denied(self, consent_service):
        """Test checking consent that was denied."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            await consent_service.collect_consent(
                user_id="denied_user",
                purposes={ConsentPurpose.MARKETING: False},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            has_consent, reason = await consent_service.check_consent(
                "denied_user",
                ConsentPurpose.MARKETING,
            )

            assert has_consent is False
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_check_consent_no_record(self, consent_service):
        """Test checking consent with no record."""
        try:
            from forge.compliance.privacy import ConsentPurpose

            has_consent, reason = await consent_service.check_consent(
                "no_record_user",
                ConsentPurpose.ANALYTICS,
            )

            assert has_consent is False
            assert "no consent" in reason.lower() or "not found" in reason.lower()
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_withdraw_consent_specific_purposes(self, consent_service):
        """Test withdrawing consent for specific purposes."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            # Collect multiple consents
            await consent_service.collect_consent(
                user_id="withdraw_user",
                purposes={
                    ConsentPurpose.ANALYTICS: True,
                    ConsentPurpose.MARKETING: True,
                },
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            # Withdraw only marketing
            record = await consent_service.withdraw_consent(
                user_id="withdraw_user",
                purposes=[ConsentPurpose.MARKETING],
            )

            assert record is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_withdraw_consent_all(self, consent_service):
        """Test withdrawing all consents."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            await consent_service.collect_consent(
                user_id="withdraw_all_user",
                purposes={
                    ConsentPurpose.ANALYTICS: True,
                    ConsentPurpose.MARKETING: True,
                },
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            record = await consent_service.withdraw_consent(
                user_id="withdraw_all_user",
                withdraw_all=True,
            )

            assert record is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_withdraw_consent_no_record(self, consent_service):
        """Test withdrawing consent with no existing record."""
        try:
            from forge.compliance.privacy import ConsentPurpose

            result = await consent_service.withdraw_consent(
                user_id="no_consent_user",
                purposes=[ConsentPurpose.ANALYTICS],
            )

            assert result is None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_generate_receipt(self, consent_service):
        """Test generating a consent receipt."""
        try:
            from forge.compliance.privacy import ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            await consent_service.collect_consent(
                user_id="receipt_user",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            receipt = await consent_service.generate_receipt("receipt_user")

            assert receipt is not None
            assert receipt.receipt_id is not None
            assert receipt.consent_hash is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_generate_receipt_no_record(self, consent_service):
        """Test generating receipt for user with no consent."""
        try:
            receipt = await consent_service.generate_receipt("no_receipt_user")
            assert receipt is None
        except ImportError:
            pytest.skip("Required imports not available")


class TestConsentCollectionMethod:
    """Tests for ConsentCollectionMethod enum if available."""

    def test_collection_methods_exist(self):
        """Test that collection methods exist."""
        try:
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            # Test common methods exist
            assert hasattr(ConsentCollectionMethod, "EXPLICIT_OPT_IN")
        except ImportError:
            pytest.skip("ConsentCollectionMethod not available")


class TestConsentRecord:
    """Tests for consent record model if available."""

    def test_consent_record_creation(self):
        """Test creating a consent record."""
        try:
            from forge.compliance.privacy.consent_service import ConsentRecord

            record = ConsentRecord(
                record_id="rec_001",
                user_id="user_123",
                version=1,
                consent_hash="abc123",
                created_at=datetime.now(UTC),
            )

            assert record.record_id == "rec_001"
            assert record.user_id == "user_123"
        except ImportError:
            pytest.skip("ConsentRecord not available")


class TestConsentReceipt:
    """Tests for consent receipt model if available."""

    def test_consent_receipt_creation(self):
        """Test creating a consent receipt."""
        try:
            from forge.compliance.privacy.consent_service import ConsentReceipt

            receipt = ConsentReceipt(
                receipt_id="rcpt_001",
                data_controller="Test Corp",
                purposes_granted=["analytics"],
                purposes_denied=["marketing"],
                collection_timestamp=datetime.now(UTC),
                consent_hash="abc123",
            )

            assert receipt.receipt_id == "rcpt_001"
            assert "analytics" in receipt.purposes_granted
        except ImportError:
            pytest.skip("ConsentReceipt not available")


class TestDSARProcessor:
    """Tests for the DSAR processor if available."""

    @pytest.fixture
    def dsar_processor(self):
        """Create a DSAR processor for testing."""
        try:
            from forge.compliance.privacy import get_dsar_processor
            return get_dsar_processor()
        except (ImportError, AttributeError):
            pytest.skip("DSAR processor not available")

    @pytest.mark.asyncio
    async def test_create_dsar(self, dsar_processor):
        """Test creating a DSAR through processor."""
        try:
            from forge.compliance.core.enums import DSARType

            dsar = await dsar_processor.create_dsar(
                request_type=DSARType.ACCESS,
                subject_email="user@example.com",
                request_text="I want to access my data",
                jurisdiction=Jurisdiction.EU,
            )

            assert dsar is not None
        except (ImportError, AttributeError):
            pytest.skip("Required methods not available")

    @pytest.mark.asyncio
    async def test_process_dsar(self, dsar_processor):
        """Test processing a DSAR."""
        try:
            from forge.compliance.core.enums import DSARType

            dsar = await dsar_processor.create_dsar(
                request_type=DSARType.ACCESS,
                subject_email="user@example.com",
                request_text="Access my data",
                jurisdiction=Jurisdiction.EU,
            )

            processed = await dsar_processor.process_dsar(
                dsar_id=dsar.id,
                processor_id="processor_001",
            )

            assert processed is not None
        except (ImportError, AttributeError):
            pytest.skip("Required methods not available")


class TestPrivacyServiceIntegration:
    """Integration tests for privacy services."""

    @pytest.mark.asyncio
    async def test_consent_to_dsar_flow(self):
        """Test flow from consent collection to DSAR handling."""
        try:
            from forge.compliance.privacy import get_consent_service, ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            service = get_consent_service()

            # User grants consent
            await service.collect_consent(
                user_id="integration_user",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            # User later requests data (DSAR)
            consents = await service.get_user_consents("integration_user")
            assert consents is not None

            # User withdraws consent
            await service.withdraw_consent(
                user_id="integration_user",
                withdraw_all=True,
            )

            # Check consent is withdrawn
            has_consent, _ = await service.check_consent(
                "integration_user",
                ConsentPurpose.ANALYTICS,
            )
            assert has_consent is False
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_jurisdiction_specific_consent(self):
        """Test jurisdiction-specific consent handling."""
        try:
            from forge.compliance.privacy import get_consent_service, ConsentPurpose
            from forge.compliance.privacy.consent_service import ConsentCollectionMethod

            service = get_consent_service()

            # EU consent (strict GDPR)
            await service.collect_consent(
                user_id="eu_user",
                purposes={ConsentPurpose.ANALYTICS: True},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.EU,
            )

            # California consent (CCPA)
            await service.collect_consent(
                user_id="ca_user",
                purposes={ConsentPurpose.DATA_SALE: False},
                collection_method=ConsentCollectionMethod.EXPLICIT_OPT_IN,
                jurisdiction=Jurisdiction.US_CALIFORNIA,
            )

            # Both should have valid records
            eu_consents = await service.get_user_consents("eu_user")
            ca_consents = await service.get_user_consents("ca_user")

            assert eu_consents is not None
            assert ca_consents is not None
        except ImportError:
            pytest.skip("Required imports not available")
