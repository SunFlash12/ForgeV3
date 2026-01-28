"""
Tests for forge.compliance.core.registry module.

Tests the ComplianceRegistry class and ControlDefinition dataclass,
including control registration, lookup, status tracking, and framework
compliance calculations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.compliance.core.enums import (
    ComplianceFramework,
    RiskLevel,
)
from forge.compliance.core.models import ControlStatus
from forge.compliance.core.registry import (
    ComplianceRegistry,
    ControlDefinition,
    get_compliance_registry,
)


class TestControlDefinition:
    """Tests for the ControlDefinition dataclass."""

    def test_basic_control_definition(self, sample_control_definition):
        """Test basic control definition creation."""
        assert sample_control_definition.control_id == "TEST-001"
        assert sample_control_definition.framework == ComplianceFramework.GDPR
        assert sample_control_definition.name == "Test Control"
        assert sample_control_definition.category == "security"
        assert sample_control_definition.automatable is True

    def test_control_definition_defaults(self):
        """Test control definition with default values."""
        control = ControlDefinition(
            control_id="TEST-002",
            framework=ComplianceFramework.CCPA,
            name="Minimal Control",
            description="A minimal control definition",
            category="privacy",
        )

        assert control.implementation_guidance == ""
        assert control.evidence_required == []
        assert control.risk_if_missing == RiskLevel.HIGH
        assert control.automatable is False
        assert control.verification_function is None
        assert control.depends_on == []
        assert control.related_controls == []
        assert control.mappings == {}

    def test_control_definition_with_mappings(self):
        """Test control definition with cross-framework mappings."""
        control = ControlDefinition(
            control_id="GDPR-15",
            framework=ComplianceFramework.GDPR,
            name="Right of Access",
            description="Enable data subjects to access their personal data",
            category="rights",
            mappings={
                "ccpa": ["CCPA-1798.100"],
                "lgpd": ["LGPD-18"],
            },
        )

        assert "ccpa" in control.mappings
        assert "CCPA-1798.100" in control.mappings["ccpa"]

    def test_control_definition_with_dependencies(self):
        """Test control definition with dependencies."""
        control = ControlDefinition(
            control_id="TEST-003",
            framework=ComplianceFramework.SOC2,
            name="Dependent Control",
            description="A control that depends on others",
            category="security",
            depends_on=["TEST-001", "TEST-002"],
            related_controls=["TEST-004"],
        )

        assert len(control.depends_on) == 2
        assert "TEST-001" in control.depends_on
        assert len(control.related_controls) == 1


class TestComplianceRegistry:
    """Tests for the ComplianceRegistry class."""

    def test_registry_initialization(self, compliance_registry):
        """Test that registry initializes with controls."""
        # Registry should have controls after initialization
        control_count = compliance_registry.get_control_count()
        assert control_count > 0

    def test_get_control_existing(self, compliance_registry):
        """Test getting an existing control."""
        control = compliance_registry.get_control("GDPR-5.1")
        assert control is not None
        assert control.control_id == "GDPR-5.1"
        assert control.framework == ComplianceFramework.GDPR

    def test_get_control_nonexistent(self, compliance_registry):
        """Test getting a nonexistent control returns None."""
        control = compliance_registry.get_control("NONEXISTENT-999")
        assert control is None

    def test_get_controls_by_framework_gdpr(self, compliance_registry):
        """Test getting controls for GDPR framework."""
        gdpr_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.GDPR
        )
        assert len(gdpr_controls) > 0
        for control in gdpr_controls:
            assert control.framework == ComplianceFramework.GDPR

    def test_get_controls_by_framework_ccpa(self, compliance_registry):
        """Test getting controls for CCPA framework."""
        ccpa_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.CCPA
        )
        assert len(ccpa_controls) > 0
        for control in ccpa_controls:
            assert control.framework == ComplianceFramework.CCPA

    def test_get_controls_by_framework_hipaa(self, compliance_registry):
        """Test getting controls for HIPAA framework."""
        hipaa_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.HIPAA
        )
        assert len(hipaa_controls) > 0
        for control in hipaa_controls:
            assert control.framework == ComplianceFramework.HIPAA

    def test_get_controls_by_framework_empty(self, compliance_registry):
        """Test getting controls for framework with no controls returns empty list."""
        # Create a new registry and try to get controls for an unusual framework
        controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.FINRA  # Might have no controls
        )
        # Should return empty list, not raise error
        assert isinstance(controls, list)

    def test_get_controls_by_category_security(self, compliance_registry):
        """Test getting controls by security category."""
        security_controls = compliance_registry.get_controls_by_category("security")
        assert len(security_controls) > 0
        for control in security_controls:
            assert control.category == "security"

    def test_get_controls_by_category_rights(self, compliance_registry):
        """Test getting controls by rights category."""
        rights_controls = compliance_registry.get_controls_by_category("rights")
        assert len(rights_controls) > 0
        for control in rights_controls:
            assert control.category == "rights"

    def test_get_controls_by_category_nonexistent(self, compliance_registry):
        """Test getting controls for nonexistent category returns empty list."""
        controls = compliance_registry.get_controls_by_category("nonexistent_category")
        assert controls == []

    def test_get_automatable_controls(self, compliance_registry):
        """Test getting automatable controls."""
        automatable = compliance_registry.get_automatable_controls()
        assert len(automatable) > 0
        for control in automatable:
            assert control.automatable is True

    def test_get_all_controls(self, compliance_registry):
        """Test getting all controls."""
        all_controls = compliance_registry.get_all_controls()
        assert len(all_controls) == compliance_registry.get_control_count()

    def test_get_control_count(self, compliance_registry):
        """Test getting control count."""
        count = compliance_registry.get_control_count()
        assert isinstance(count, int)
        assert count > 0

    def test_register_verification_function(self, compliance_registry):
        """Test registering a verification function."""
        def verify_test():
            return True

        compliance_registry.register_verification_function("verify_test", verify_test)
        retrieved = compliance_registry.get_verification_function("verify_test")
        assert retrieved is verify_test
        assert retrieved() is True

    def test_register_verification_function_async(self, compliance_registry):
        """Test registering an async verification function."""
        async def verify_async():
            return True

        compliance_registry.register_verification_function("verify_async", verify_async)
        retrieved = compliance_registry.get_verification_function("verify_async")
        assert retrieved is verify_async

    def test_get_verification_function_nonexistent(self, compliance_registry):
        """Test getting nonexistent verification function returns None."""
        func = compliance_registry.get_verification_function("nonexistent_func")
        assert func is None

    def test_set_control_status_new(self, compliance_registry):
        """Test setting status for a control."""
        # Get a known control
        control = compliance_registry.get_control("GDPR-5.1")
        assert control is not None

        status = compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=True,
            evidence=["evidence_doc_1.pdf", "screenshot.png"],
            notes="Control verified by external auditor",
        )

        assert status is not None
        assert status.control_id == "GDPR-5.1"
        assert status.implemented is True
        assert status.verified is True
        assert len(status.evidence_provided) == 2
        assert status.auditor_notes == "Control verified by external auditor"
        assert status.last_audit_date is not None

    def test_set_control_status_nonexistent_control(self, compliance_registry):
        """Test setting status for nonexistent control returns None."""
        status = compliance_registry.set_control_status(
            control_id="NONEXISTENT-999",
            implemented=True,
            verified=True,
        )
        assert status is None

    def test_set_control_status_not_verified_no_audit_date(self, compliance_registry):
        """Test that last_audit_date is not set when not verified."""
        status = compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=False,
        )
        assert status is not None
        assert status.last_audit_date is None

    def test_get_control_status_existing(self, compliance_registry):
        """Test getting status for a control that has been set."""
        # First set a status
        compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=True,
        )

        # Then retrieve it
        status = compliance_registry.get_control_status("GDPR-5.1")
        assert status is not None
        assert status.control_id == "GDPR-5.1"
        assert status.implemented is True

    def test_get_control_status_nonexistent(self, compliance_registry):
        """Test getting status for control without status returns None."""
        status = compliance_registry.get_control_status("UNSET-CONTROL")
        assert status is None

    def test_get_framework_compliance_status_all_pending(self, compliance_registry):
        """Test framework compliance status when all controls are pending."""
        # Get fresh registry where no statuses have been set
        status = compliance_registry.get_framework_compliance_status(
            ComplianceFramework.GDPR
        )

        assert status["framework"] == "gdpr"
        assert status["total"] > 0
        assert status["pending"] == status["total"]  # All pending
        assert status["implemented"] == 0
        assert status["verified"] == 0
        assert status["compliance_percentage"] == 0

    def test_get_framework_compliance_status_partial(self, compliance_registry):
        """Test framework compliance status with some controls set."""
        # Set status for a GDPR control
        compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=True,
        )

        status = compliance_registry.get_framework_compliance_status(
            ComplianceFramework.GDPR
        )

        assert status["verified"] >= 1
        assert status["implemented"] >= 1
        assert status["compliance_percentage"] > 0

    def test_get_framework_compliance_status_percentage_calculation(
        self, compliance_registry
    ):
        """Test that compliance percentage is calculated correctly."""
        # Get GDPR controls and set some as verified
        gdpr_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.GDPR
        )
        total_controls = len(gdpr_controls)

        # Set all controls as verified
        for control in gdpr_controls:
            compliance_registry.set_control_status(
                control_id=control.control_id,
                implemented=True,
                verified=True,
            )

        status = compliance_registry.get_framework_compliance_status(
            ComplianceFramework.GDPR
        )

        assert status["verified"] == total_controls
        assert status["compliance_percentage"] == 100


class TestComplianceRegistryControlCategories:
    """Tests for specific control categories in the registry."""

    def test_gdpr_controls_exist(self, compliance_registry):
        """Test that GDPR controls are properly initialized."""
        gdpr_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.GDPR
        )

        # Check for expected GDPR controls
        control_ids = [c.control_id for c in gdpr_controls]
        assert "GDPR-5.1" in control_ids  # Lawfulness
        assert "GDPR-7" in control_ids    # Consent
        assert "GDPR-15" in control_ids   # Right of Access
        assert "GDPR-17" in control_ids   # Right to Erasure
        assert "GDPR-33" in control_ids   # Breach Notification

    def test_soc2_controls_exist(self, compliance_registry):
        """Test that SOC 2 controls are properly initialized."""
        soc2_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.SOC2
        )

        control_ids = [c.control_id for c in soc2_controls]
        assert "SOC2-CC6.1" in control_ids  # Encryption
        assert "SOC2-CC7.2" in control_ids  # Audit Logging

    def test_hipaa_controls_exist(self, compliance_registry):
        """Test that HIPAA controls are properly initialized."""
        hipaa_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.HIPAA
        )

        control_ids = [c.control_id for c in hipaa_controls]
        assert "HIPAA-164.312a1" in control_ids  # Unique User ID
        assert "HIPAA-164.312b" in control_ids   # Audit Controls

    def test_pci_dss_controls_exist(self, compliance_registry):
        """Test that PCI-DSS controls are properly initialized."""
        pci_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.PCI_DSS
        )

        control_ids = [c.control_id for c in pci_controls]
        assert "PCI-DSS-3.5" in control_ids  # Strong Cryptography
        assert "PCI-DSS-8.4" in control_ids  # MFA for CDE

    def test_eu_ai_act_controls_exist(self, compliance_registry):
        """Test that EU AI Act controls are properly initialized."""
        ai_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.EU_AI_ACT
        )

        control_ids = [c.control_id for c in ai_controls]
        assert "EU-AI-6" in control_ids   # Risk Classification
        assert "EU-AI-14" in control_ids  # Human Oversight
        assert "EU-AI-12" in control_ids  # Automatic Logging

    def test_wcag_controls_exist(self, compliance_registry):
        """Test that WCAG controls are properly initialized."""
        wcag_controls = compliance_registry.get_controls_by_framework(
            ComplianceFramework.WCAG_22
        )

        control_ids = [c.control_id for c in wcag_controls]
        assert "WCAG-1.1.1" in control_ids  # Non-text Content
        assert "WCAG-2.1.1" in control_ids  # Keyboard


class TestGetComplianceRegistry:
    """Tests for the get_compliance_registry function."""

    def test_returns_registry_instance(self):
        """Test that get_compliance_registry returns a ComplianceRegistry."""
        registry = get_compliance_registry()
        assert isinstance(registry, ComplianceRegistry)

    def test_returns_same_instance(self):
        """Test that get_compliance_registry returns the same singleton instance."""
        # Note: This test may need adjustment based on how global state is managed
        registry1 = get_compliance_registry()
        registry2 = get_compliance_registry()
        assert registry1 is registry2


class TestControlStatusIntegration:
    """Integration tests for control status and registry."""

    def test_status_inherits_control_properties(self, compliance_registry):
        """Test that status inherits properties from control definition."""
        status = compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=True,
        )

        # Control definition values should be copied to status
        control = compliance_registry.get_control("GDPR-5.1")
        assert status.name == control.name
        assert status.description == control.description
        assert status.framework == control.framework
        assert status.evidence_required == control.evidence_required
        assert status.risk_if_missing == control.risk_if_missing

    def test_status_update_preserves_history(self, compliance_registry):
        """Test that updating status works correctly."""
        # Set initial status
        compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=False,
        )

        # Update to verified
        compliance_registry.set_control_status(
            control_id="GDPR-5.1",
            implemented=True,
            verified=True,
            evidence=["new_evidence.pdf"],
        )

        status = compliance_registry.get_control_status("GDPR-5.1")
        assert status.verified is True
        assert "new_evidence.pdf" in status.evidence_provided
