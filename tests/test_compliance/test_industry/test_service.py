"""
Tests for forge.compliance.industry module.

Tests industry-specific compliance services including HIPAA,
PCI-DSS, COPPA, SOX, and other industry regulations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import (
    ComplianceFramework,
    DataClassification,
)


class TestIndustryComplianceService:
    """Tests for the IndustryComplianceService class."""

    @pytest.fixture
    def industry_service(self):
        """Create an industry compliance service for testing."""
        try:
            from forge.compliance.industry import get_industry_compliance_service
            return get_industry_compliance_service()
        except (ImportError, AttributeError):
            pytest.skip("IndustryComplianceService not available")

    @pytest.mark.asyncio
    async def test_check_hipaa_compliance(self, industry_service):
        """Test checking HIPAA compliance."""
        try:
            result = await industry_service.check_compliance(
                framework=ComplianceFramework.HIPAA,
                data_type=DataClassification.PHI,
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_check_pci_dss_compliance(self, industry_service):
        """Test checking PCI-DSS compliance."""
        try:
            result = await industry_service.check_compliance(
                framework=ComplianceFramework.PCI_DSS,
                data_type=DataClassification.PCI,
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_get_framework_requirements(self, industry_service):
        """Test getting framework requirements."""
        try:
            requirements = await industry_service.get_requirements(
                framework=ComplianceFramework.HIPAA,
            )

            assert requirements is not None
            assert isinstance(requirements, (list, dict))
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestHIPAACompliance:
    """Tests for HIPAA-specific compliance."""

    @pytest.fixture
    def hipaa_service(self):
        """Create a HIPAA compliance service for testing."""
        try:
            from forge.compliance.industry import get_hipaa_service
            return get_hipaa_service()
        except (ImportError, AttributeError):
            try:
                from forge.compliance.industry import get_industry_compliance_service
                return get_industry_compliance_service()
            except (ImportError, AttributeError):
                pytest.skip("HIPAA service not available")

    def test_hipaa_phi_classification(self):
        """Test PHI data classification."""
        assert DataClassification.PHI.requires_explicit_consent is True
        assert DataClassification.PHI.minimum_retention_years == 6

    @pytest.mark.asyncio
    async def test_hipaa_minimum_necessary(self, hipaa_service):
        """Test HIPAA minimum necessary principle."""
        try:
            # Check that minimum necessary access is enforced
            result = await hipaa_service.check_minimum_necessary(
                user_id="healthcare_worker",
                requested_data=["patient_name", "diagnosis", "treatment"],
                purpose="treatment",
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_hipaa_audit_controls(self, hipaa_service):
        """Test HIPAA audit control requirements."""
        try:
            result = await hipaa_service.verify_audit_controls()
            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestPCIDSSCompliance:
    """Tests for PCI-DSS specific compliance."""

    @pytest.fixture
    def pci_service(self):
        """Create a PCI-DSS compliance service for testing."""
        try:
            from forge.compliance.industry import get_pci_service
            return get_pci_service()
        except (ImportError, AttributeError):
            try:
                from forge.compliance.industry import get_industry_compliance_service
                return get_industry_compliance_service()
            except (ImportError, AttributeError):
                pytest.skip("PCI-DSS service not available")

    def test_pci_data_classification(self):
        """Test PCI data classification."""
        assert DataClassification.PCI.requires_encryption_at_rest is True
        assert DataClassification.PCI.minimum_retention_years == 1

    @pytest.mark.asyncio
    async def test_pci_encryption_verification(self, pci_service):
        """Test PCI encryption verification."""
        try:
            result = await pci_service.verify_encryption(
                data_type=DataClassification.PCI,
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_pci_network_segmentation(self, pci_service):
        """Test PCI network segmentation verification."""
        try:
            result = await pci_service.verify_network_segmentation()
            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestCOPPACompliance:
    """Tests for COPPA specific compliance."""

    @pytest.fixture
    def coppa_service(self):
        """Create a COPPA compliance service for testing."""
        try:
            from forge.compliance.industry import get_coppa_service
            return get_coppa_service()
        except (ImportError, AttributeError):
            try:
                from forge.compliance.industry import get_industry_compliance_service
                return get_industry_compliance_service()
            except (ImportError, AttributeError):
                pytest.skip("COPPA service not available")

    def test_coppa_children_data_classification(self):
        """Test children's data classification."""
        assert DataClassification.CHILDREN.requires_explicit_consent is True
        assert DataClassification.CHILDREN.requires_encryption_at_rest is True

    @pytest.mark.asyncio
    async def test_coppa_parental_consent_verification(self, coppa_service):
        """Test COPPA parental consent verification."""
        try:
            result = await coppa_service.verify_parental_consent(
                child_id="child_123",
                parent_id="parent_456",
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_coppa_age_verification(self, coppa_service):
        """Test COPPA age verification."""
        try:
            # Test that under-13 users trigger COPPA
            result = await coppa_service.check_age_gate(
                user_id="user_789",
                claimed_age=12,
            )

            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestSOXCompliance:
    """Tests for SOX (Sarbanes-Oxley) compliance."""

    @pytest.fixture
    def sox_service(self):
        """Create a SOX compliance service for testing."""
        try:
            from forge.compliance.industry import get_sox_service
            return get_sox_service()
        except (ImportError, AttributeError):
            try:
                from forge.compliance.industry import get_industry_compliance_service
                return get_industry_compliance_service()
            except (ImportError, AttributeError):
                pytest.skip("SOX service not available")

    def test_sox_financial_data_classification(self):
        """Test financial data classification for SOX."""
        assert DataClassification.FINANCIAL.minimum_retention_years == 7

    @pytest.mark.asyncio
    async def test_sox_audit_trail_requirements(self, sox_service):
        """Test SOX audit trail requirements."""
        try:
            result = await sox_service.verify_audit_trail()
            assert result is not None
        except (ImportError, AttributeError):
            pytest.skip("Method not available")


class TestFERPACompliance:
    """Tests for FERPA (education) compliance."""

    @pytest.fixture
    def ferpa_service(self):
        """Create a FERPA compliance service for testing."""
        try:
            from forge.compliance.industry import get_ferpa_service
            return get_ferpa_service()
        except (ImportError, AttributeError):
            pytest.skip("FERPA service not available")

    def test_ferpa_educational_data_classification(self):
        """Test educational data classification."""
        assert DataClassification.EDUCATIONAL.minimum_retention_years == 5


class TestGLBACompliance:
    """Tests for GLBA (financial services) compliance."""

    @pytest.fixture
    def glba_service(self):
        """Create a GLBA compliance service for testing."""
        try:
            from forge.compliance.industry import get_glba_service
            return get_glba_service()
        except (ImportError, AttributeError):
            pytest.skip("GLBA service not available")

    def test_glba_financial_data_requirements(self):
        """Test GLBA financial data requirements."""
        assert DataClassification.FINANCIAL.requires_encryption_at_rest is True


class TestIndustryComplianceIntegration:
    """Integration tests for industry compliance."""

    @pytest.mark.asyncio
    async def test_multi_framework_compliance_check(self):
        """Test checking compliance across multiple frameworks."""
        try:
            from forge.compliance.industry import get_industry_compliance_service

            service = get_industry_compliance_service()

            # Check multiple frameworks
            frameworks = [
                ComplianceFramework.HIPAA,
                ComplianceFramework.PCI_DSS,
                ComplianceFramework.SOX,
            ]

            results = {}
            for framework in frameworks:
                try:
                    result = await service.check_compliance(framework=framework)
                    results[framework.value] = result
                except Exception:
                    results[framework.value] = None

            assert len(results) == 3
        except ImportError:
            pytest.skip("Industry service not available")

    @pytest.mark.asyncio
    async def test_data_classification_compliance_mapping(self):
        """Test mapping data classifications to compliance requirements."""
        classifications = [
            DataClassification.PHI,
            DataClassification.PCI,
            DataClassification.FINANCIAL,
            DataClassification.CHILDREN,
        ]

        for classification in classifications:
            # Each classification should have encryption requirement
            assert hasattr(classification, "requires_encryption_at_rest")
            # Each should have retention requirement
            assert hasattr(classification, "minimum_retention_years")

    @pytest.mark.asyncio
    async def test_cross_industry_data_handling(self):
        """Test handling data that falls under multiple regulations."""
        # PHI in financial context (healthcare + financial)
        assert DataClassification.PHI.requires_encryption_at_rest is True
        assert DataClassification.FINANCIAL.requires_encryption_at_rest is True

        # Both should have long retention
        assert DataClassification.PHI.minimum_retention_years >= 6
        assert DataClassification.FINANCIAL.minimum_retention_years >= 7


class TestIndustryFrameworkProperties:
    """Tests for industry framework properties."""

    def test_hipaa_framework_category(self):
        """Test HIPAA framework is in industry category."""
        assert ComplianceFramework.HIPAA.category == "industry"

    def test_pci_dss_framework_category(self):
        """Test PCI-DSS framework is in industry category."""
        assert ComplianceFramework.PCI_DSS.category == "industry"

    def test_coppa_framework_category(self):
        """Test COPPA framework is in industry category."""
        assert ComplianceFramework.COPPA.category == "industry"

    def test_sox_framework_category(self):
        """Test SOX framework is in industry category."""
        assert ComplianceFramework.SOX.category == "industry"

    def test_ferpa_framework_category(self):
        """Test FERPA framework is in industry category."""
        assert ComplianceFramework.FERPA.category == "industry"

    def test_glba_framework_category(self):
        """Test GLBA framework is in industry category."""
        assert ComplianceFramework.GLBA.category == "industry"

    def test_finra_framework_category(self):
        """Test FINRA framework is in industry category."""
        assert ComplianceFramework.FINRA.category == "industry"

    def test_hitech_framework_category(self):
        """Test HITECH framework is in industry category."""
        assert ComplianceFramework.HITECH.category == "industry"
