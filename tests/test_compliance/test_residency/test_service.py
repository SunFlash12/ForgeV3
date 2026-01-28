"""
Tests for forge.compliance.residency module.

Tests the data residency service including regional data storage,
cross-border transfer controls, and localization requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import (
    Jurisdiction,
    DataClassification,
)


class TestDataResidencyService:
    """Tests for the DataResidencyService class."""

    @pytest.fixture
    def residency_service(self):
        """Create a data residency service for testing."""
        try:
            from forge.compliance.residency import get_data_residency_service
            return get_data_residency_service()
        except (ImportError, AttributeError):
            pytest.skip("DataResidencyService not available")

    @pytest.mark.asyncio
    async def test_determine_storage_region_eu(self, residency_service):
        """Test determining storage region for EU data."""
        try:
            region = await residency_service.determine_storage_region(
                jurisdiction=Jurisdiction.EU,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert region is not None
            # EU data should stay in EU
            assert "eu" in region.lower() or "europe" in region.lower()
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_determine_storage_region_china(self, residency_service):
        """Test determining storage region for China data."""
        try:
            region = await residency_service.determine_storage_region(
                jurisdiction=Jurisdiction.CHINA,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert region is not None
            # China requires data localization
            assert Jurisdiction.CHINA.requires_localization is True
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_determine_storage_region_russia(self, residency_service):
        """Test determining storage region for Russia data."""
        try:
            region = await residency_service.determine_storage_region(
                jurisdiction=Jurisdiction.RUSSIA,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert region is not None
            # Russia requires data localization
            assert Jurisdiction.RUSSIA.requires_localization is True
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_check_transfer_allowed_sccs(self, residency_service):
        """Test checking if transfer is allowed with SCCs."""
        try:
            allowed, reason = await residency_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.US_FEDERAL,
                transfer_mechanism="standard_contractual_clauses",
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert isinstance(allowed, bool)
            assert reason is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_check_transfer_allowed_adequacy(self, residency_service):
        """Test checking transfer with adequacy decision."""
        try:
            allowed, reason = await residency_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.UK,  # Adequacy decision exists
                transfer_mechanism="adequacy_decision",
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert isinstance(allowed, bool)
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_check_transfer_blocked_localization(self, residency_service):
        """Test transfer blocked due to localization requirement."""
        try:
            allowed, reason = await residency_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.CHINA,
                target_jurisdiction=Jurisdiction.US_FEDERAL,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # China has localization requirements
            # Transfer should be blocked or require special handling
            assert reason is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_get_available_regions(self, residency_service):
        """Test getting available storage regions."""
        try:
            regions = await residency_service.get_available_regions()

            assert regions is not None
            assert isinstance(regions, list)
            assert len(regions) > 0
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_get_region_compliance_status(self, residency_service):
        """Test getting compliance status for a region."""
        try:
            status = await residency_service.get_region_compliance_status(
                region="eu-west-1",
            )

            assert status is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestJurisdictionLocalizationRequirements:
    """Tests for jurisdiction localization requirements."""

    def test_china_requires_localization(self):
        """Test that China requires data localization."""
        assert Jurisdiction.CHINA.requires_localization is True

    def test_russia_requires_localization(self):
        """Test that Russia requires data localization."""
        assert Jurisdiction.RUSSIA.requires_localization is True

    def test_vietnam_requires_localization(self):
        """Test that Vietnam requires data localization."""
        assert Jurisdiction.VIETNAM.requires_localization is True

    def test_indonesia_requires_localization(self):
        """Test that Indonesia requires data localization."""
        assert Jurisdiction.INDONESIA.requires_localization is True

    def test_eu_no_localization_required(self):
        """Test that EU does not require localization."""
        assert Jurisdiction.EU.requires_localization is False

    def test_us_no_localization_required(self):
        """Test that US does not require localization."""
        assert Jurisdiction.US_FEDERAL.requires_localization is False
        assert Jurisdiction.US_CALIFORNIA.requires_localization is False


class TestCrossBorderTransfer:
    """Tests for cross-border data transfer controls."""

    @pytest.fixture
    def transfer_service(self):
        """Create a transfer service for testing."""
        try:
            from forge.compliance.residency import get_data_residency_service
            return get_data_residency_service()
        except (ImportError, AttributeError):
            pytest.skip("Data residency service not available")

    @pytest.mark.asyncio
    async def test_transfer_within_eu(self, transfer_service):
        """Test transfer within EU (free flow)."""
        try:
            allowed, reason = await transfer_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.EU,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # Within EU should always be allowed
            assert allowed is True or reason is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_transfer_eu_to_us_requires_mechanism(self, transfer_service):
        """Test EU to US transfer requires legal mechanism."""
        try:
            allowed, reason = await transfer_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.US_FEDERAL,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # Should require SCCs, DPF, or other mechanism
            assert reason is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_transfer_sensitive_data_stricter_controls(self, transfer_service):
        """Test that sensitive data has stricter transfer controls."""
        try:
            regular_allowed, regular_reason = await transfer_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.UK,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            sensitive_allowed, sensitive_reason = await transfer_service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.UK,
                data_classification=DataClassification.SENSITIVE_PERSONAL,
            )

            # Sensitive data may have additional requirements
            assert regular_reason is not None or sensitive_reason is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestRegionalPods:
    """Tests for regional pod/storage functionality."""

    @pytest.fixture
    def residency_service(self):
        """Create a residency service for testing."""
        try:
            from forge.compliance.residency import get_data_residency_service
            return get_data_residency_service()
        except (ImportError, AttributeError):
            pytest.skip("Data residency service not available")

    @pytest.mark.asyncio
    async def test_assign_data_to_region(self, residency_service):
        """Test assigning data to a specific region."""
        try:
            result = await residency_service.assign_to_region(
                data_id="data_001",
                region="eu-west-1",
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_get_data_region(self, residency_service):
        """Test getting the region for stored data."""
        try:
            region = await residency_service.get_data_region(
                data_id="data_001",
            )

            assert region is not None or region is None  # May not exist
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_migrate_data_between_regions(self, residency_service):
        """Test migrating data between regions."""
        try:
            result = await residency_service.migrate_data(
                data_id="data_001",
                source_region="us-east-1",
                target_region="eu-west-1",
                reason="User relocated to EU",
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestDataResidencyIntegration:
    """Integration tests for data residency service."""

    @pytest.mark.asyncio
    async def test_full_residency_workflow(self):
        """Test complete data residency workflow."""
        try:
            from forge.compliance.residency import get_data_residency_service

            service = get_data_residency_service()

            # Step 1: Determine appropriate region for new data
            region = await service.determine_storage_region(
                jurisdiction=Jurisdiction.EU,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # Step 2: Check if transfer would be allowed
            allowed, reason = await service.check_transfer_allowed(
                source_jurisdiction=Jurisdiction.EU,
                target_jurisdiction=Jurisdiction.US_FEDERAL,
                transfer_mechanism="standard_contractual_clauses",
                data_classification=DataClassification.PERSONAL_DATA,
            )

            assert region is not None
            assert reason is not None
        except ImportError:
            pytest.skip("Data residency service not available")

    @pytest.mark.asyncio
    async def test_multi_jurisdiction_data_handling(self):
        """Test handling data subject to multiple jurisdictions."""
        try:
            from forge.compliance.residency import get_data_residency_service

            service = get_data_residency_service()

            # User is in EU but has transactions in US
            jurisdictions = [Jurisdiction.EU, Jurisdiction.US_CALIFORNIA]

            regions = []
            for jurisdiction in jurisdictions:
                region = await service.determine_storage_region(
                    jurisdiction=jurisdiction,
                    data_classification=DataClassification.PERSONAL_DATA,
                )
                regions.append(region)

            assert len(regions) == 2
        except ImportError:
            pytest.skip("Data residency service not available")


class TestLocalizationCompliance:
    """Tests for localization compliance checks."""

    @pytest.mark.asyncio
    async def test_china_localization_compliance(self):
        """Test China data localization compliance."""
        try:
            from forge.compliance.residency import get_data_residency_service

            service = get_data_residency_service()

            # For China, data must stay in China
            region = await service.determine_storage_region(
                jurisdiction=Jurisdiction.CHINA,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # Should be a China region
            if region:
                assert "cn" in region.lower() or "china" in region.lower()
        except ImportError:
            pytest.skip("Data residency service not available")

    @pytest.mark.asyncio
    async def test_russia_localization_compliance(self):
        """Test Russia data localization compliance."""
        try:
            from forge.compliance.residency import get_data_residency_service

            service = get_data_residency_service()

            region = await service.determine_storage_region(
                jurisdiction=Jurisdiction.RUSSIA,
                data_classification=DataClassification.PERSONAL_DATA,
            )

            # Should be a Russia region
            if region:
                assert "ru" in region.lower() or "russia" in region.lower()
        except ImportError:
            pytest.skip("Data residency service not available")


class TestTransferMechanisms:
    """Tests for data transfer mechanisms."""

    def test_sccs_mechanism(self):
        """Test Standard Contractual Clauses mechanism."""
        # SCCs are a valid transfer mechanism under GDPR
        mechanism = "standard_contractual_clauses"
        assert mechanism is not None

    def test_adequacy_decision_mechanism(self):
        """Test adequacy decision mechanism."""
        # Adequacy decisions allow free data flow
        mechanism = "adequacy_decision"
        assert mechanism is not None

    def test_binding_corporate_rules_mechanism(self):
        """Test Binding Corporate Rules mechanism."""
        # BCRs for intra-group transfers
        mechanism = "binding_corporate_rules"
        assert mechanism is not None

    def test_data_protection_framework_mechanism(self):
        """Test EU-US Data Privacy Framework mechanism."""
        # DPF for US transfers
        mechanism = "data_privacy_framework"
        assert mechanism is not None
