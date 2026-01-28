"""
Tests for forge.compliance.core.enums module.

Tests all compliance-related enumerations and their properties,
including jurisdictions, frameworks, data classifications, and risk levels.
"""

from __future__ import annotations

import pytest

from forge.compliance.core.enums import (
    AccessControlModel,
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


class TestJurisdiction:
    """Tests for the Jurisdiction enum."""

    def test_all_jurisdictions_have_values(self):
        """Test that all jurisdictions have string values."""
        for jurisdiction in Jurisdiction:
            assert isinstance(jurisdiction.value, str)
            assert len(jurisdiction.value) > 0

    def test_requires_localization_property(self):
        """Test the requires_localization property for relevant jurisdictions."""
        # These jurisdictions require data localization
        localization_required = [
            Jurisdiction.CHINA,
            Jurisdiction.RUSSIA,
            Jurisdiction.VIETNAM,
            Jurisdiction.INDONESIA,
        ]

        for jurisdiction in localization_required:
            assert jurisdiction.requires_localization is True, (
                f"{jurisdiction} should require localization"
            )

        # These should NOT require localization
        no_localization = [
            Jurisdiction.EU,
            Jurisdiction.US_FEDERAL,
            Jurisdiction.US_CALIFORNIA,
            Jurisdiction.GLOBAL,
            Jurisdiction.UK,
        ]

        for jurisdiction in no_localization:
            assert jurisdiction.requires_localization is False, (
                f"{jurisdiction} should not require localization"
            )

    def test_dsar_deadline_days_property(self):
        """Test DSAR deadline days for various jurisdictions."""
        # Brazil has the strictest deadline (15 days)
        assert Jurisdiction.BRAZIL.dsar_deadline_days == 15

        # South Korea also has strict deadline (10 days)
        assert Jurisdiction.SOUTH_KOREA.dsar_deadline_days == 10

        # EU GDPR is 30 days
        assert Jurisdiction.EU.dsar_deadline_days == 30

        # California CCPA is 45 days
        assert Jurisdiction.US_CALIFORNIA.dsar_deadline_days == 45

        # Default is 30 days
        assert Jurisdiction.GLOBAL.dsar_deadline_days == 30

    def test_breach_notification_hours_property(self):
        """Test breach notification deadlines for various jurisdictions."""
        # China has the strictest deadline (24 hours)
        assert Jurisdiction.CHINA.breach_notification_hours == 24

        # EU GDPR is 72 hours
        assert Jurisdiction.EU.breach_notification_hours == 72

        # Most jurisdictions have 72 hours
        assert Jurisdiction.UK.breach_notification_hours == 72
        assert Jurisdiction.BRAZIL.breach_notification_hours == 72
        assert Jurisdiction.SINGAPORE.breach_notification_hours == 72

    def test_jurisdiction_string_representation(self):
        """Test that jurisdiction values are valid strings."""
        assert Jurisdiction.EU.value == "eu"
        assert Jurisdiction.US_CALIFORNIA.value == "us_ca"
        assert Jurisdiction.GLOBAL.value == "global"


class TestComplianceFramework:
    """Tests for the ComplianceFramework enum."""

    def test_all_frameworks_have_values(self):
        """Test that all frameworks have string values."""
        for framework in ComplianceFramework:
            assert isinstance(framework.value, str)
            assert len(framework.value) > 0

    def test_category_property_privacy(self):
        """Test that privacy frameworks have correct category."""
        privacy_frameworks = [
            ComplianceFramework.GDPR,
            ComplianceFramework.CCPA,
            ComplianceFramework.CPRA,
            ComplianceFramework.LGPD,
            ComplianceFramework.PIPL,
            ComplianceFramework.PDPA_SG,
            ComplianceFramework.APPI,
            ComplianceFramework.DPDP,
            ComplianceFramework.PIPEDA,
        ]

        for framework in privacy_frameworks:
            assert framework.category == "privacy", (
                f"{framework} should be in 'privacy' category"
            )

    def test_category_property_security(self):
        """Test that security frameworks have correct category."""
        security_frameworks = [
            ComplianceFramework.SOC2,
            ComplianceFramework.ISO27001,
            ComplianceFramework.NIST_CSF,
            ComplianceFramework.NIST_800_53,
            ComplianceFramework.CIS_CONTROLS,
            ComplianceFramework.FEDRAMP,
            ComplianceFramework.CSA_CCM,
        ]

        for framework in security_frameworks:
            assert framework.category == "security", (
                f"{framework} should be in 'security' category"
            )

    def test_category_property_industry(self):
        """Test that industry-specific frameworks have correct category."""
        industry_frameworks = [
            ComplianceFramework.HIPAA,
            ComplianceFramework.HITECH,
            ComplianceFramework.PCI_DSS,
            ComplianceFramework.COPPA,
            ComplianceFramework.FERPA,
            ComplianceFramework.GLBA,
            ComplianceFramework.SOX,
            ComplianceFramework.FINRA,
        ]

        for framework in industry_frameworks:
            assert framework.category == "industry", (
                f"{framework} should be in 'industry' category"
            )

    def test_category_property_ai_governance(self):
        """Test that AI governance frameworks have correct category."""
        ai_frameworks = [
            ComplianceFramework.EU_AI_ACT,
            ComplianceFramework.COLORADO_AI,
            ComplianceFramework.NYC_LL144,
            ComplianceFramework.NIST_AI_RMF,
            ComplianceFramework.ISO_42001,
            ComplianceFramework.CA_AB2013,
            ComplianceFramework.IL_HB3773,
        ]

        for framework in ai_frameworks:
            assert framework.category == "ai_governance", (
                f"{framework} should be in 'ai_governance' category"
            )

    def test_category_property_accessibility(self):
        """Test that accessibility frameworks have correct category."""
        accessibility_frameworks = [
            ComplianceFramework.WCAG_22,
            ComplianceFramework.EAA,
            ComplianceFramework.EN_301_549,
            ComplianceFramework.ADA_DIGITAL,
            ComplianceFramework.SECTION_508,
        ]

        for framework in accessibility_frameworks:
            assert framework.category == "accessibility", (
                f"{framework} should be in 'accessibility' category"
            )


class TestDataClassification:
    """Tests for the DataClassification enum."""

    def test_all_classifications_have_values(self):
        """Test that all data classifications have string values."""
        for classification in DataClassification:
            assert isinstance(classification.value, str)
            assert len(classification.value) > 0

    def test_requires_encryption_at_rest_property(self):
        """Test encryption at rest requirements."""
        # Public data does not require encryption
        assert DataClassification.PUBLIC.requires_encryption_at_rest is False

        # All other classifications require encryption
        require_encryption = [
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
            DataClassification.RESTRICTED,
            DataClassification.PERSONAL_DATA,
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.PCI,
            DataClassification.FINANCIAL,
        ]

        for classification in require_encryption:
            assert classification.requires_encryption_at_rest is True, (
                f"{classification} should require encryption at rest"
            )

    def test_requires_explicit_consent_property(self):
        """Test explicit consent requirements."""
        require_consent = [
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.BIOMETRIC,
            DataClassification.GENETIC,
            DataClassification.CHILDREN,
            DataClassification.FINANCIAL,
        ]

        for classification in require_consent:
            assert classification.requires_explicit_consent is True, (
                f"{classification} should require explicit consent"
            )

        # Standard personal data doesn't require explicit consent
        assert DataClassification.PERSONAL_DATA.requires_explicit_consent is False

    def test_minimum_retention_years_property(self):
        """Test minimum retention period requirements."""
        assert DataClassification.PHI.minimum_retention_years == 6  # HIPAA
        assert DataClassification.PCI.minimum_retention_years == 1  # PCI-DSS
        assert DataClassification.FINANCIAL.minimum_retention_years == 7  # SOX
        assert DataClassification.EDUCATIONAL.minimum_retention_years == 5  # FERPA
        assert DataClassification.GOVERNMENT.minimum_retention_years == 10

    def test_maximum_retention_years_property(self):
        """Test maximum retention period requirements."""
        # Personal data should have a maximum retention
        assert DataClassification.PERSONAL_DATA.maximum_retention_years == 7
        assert DataClassification.SENSITIVE_PERSONAL.maximum_retention_years == 7

        # Non-personal data may not have a maximum
        assert DataClassification.GOVERNMENT.maximum_retention_years is None


class TestRiskLevel:
    """Tests for the RiskLevel enum."""

    def test_all_risk_levels_exist(self):
        """Test that all expected risk levels exist."""
        expected_levels = ["critical", "high", "medium", "low", "info"]
        for level in expected_levels:
            assert RiskLevel(level) is not None

    def test_risk_level_values(self):
        """Test risk level string values."""
        assert RiskLevel.CRITICAL.value == "critical"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.INFO.value == "info"


class TestConsentType:
    """Tests for the ConsentType enum."""

    def test_all_consent_types_have_values(self):
        """Test that all consent types have string values."""
        for consent_type in ConsentType:
            assert isinstance(consent_type.value, str)
            assert len(consent_type.value) > 0

    def test_requires_explicit_opt_in_property(self):
        """Test explicit opt-in requirements."""
        # Essential does not require opt-in
        assert ConsentType.ESSENTIAL.requires_explicit_opt_in is False

        # All other consent types require explicit opt-in
        require_opt_in = [
            ConsentType.ANALYTICS,
            ConsentType.MARKETING,
            ConsentType.PROFILING,
            ConsentType.THIRD_PARTY,
            ConsentType.AI_PROCESSING,
            ConsentType.AI_TRAINING,
        ]

        for consent_type in require_opt_in:
            assert consent_type.requires_explicit_opt_in is True, (
                f"{consent_type} should require explicit opt-in"
            )

    def test_parent_consent_required_property(self):
        """Test parental consent requirements."""
        # Only CHILDREN consent type requires parental consent
        assert ConsentType.CHILDREN.parent_consent_required is True

        # Other consent types do not require parental consent
        assert ConsentType.ANALYTICS.parent_consent_required is False
        assert ConsentType.MARKETING.parent_consent_required is False


class TestDSARType:
    """Tests for the DSARType enum."""

    def test_all_dsar_types_exist(self):
        """Test that all DSAR types exist."""
        expected_types = [
            "access", "rectification", "erasure", "restriction",
            "portability", "objection", "automated", "opt_out_sale",
            "limit_sensitive", "correct"
        ]

        for dsar_type in expected_types:
            assert DSARType(dsar_type) is not None

    def test_baseline_deadline_days_property(self):
        """Test DSAR baseline deadline days."""
        assert DSARType.ACCESS.baseline_deadline_days == 30
        assert DSARType.ERASURE.baseline_deadline_days == 30
        assert DSARType.PORTABILITY.baseline_deadline_days == 30
        assert DSARType.OPT_OUT_SALE.baseline_deadline_days == 15
        assert DSARType.LIMIT_SENSITIVE.baseline_deadline_days == 15


class TestBreachSeverity:
    """Tests for the BreachSeverity enum."""

    def test_all_severities_exist(self):
        """Test that all breach severities exist."""
        expected_severities = ["critical", "high", "medium", "low"]
        for severity in expected_severities:
            assert BreachSeverity(severity) is not None

    def test_requires_authority_notification_property(self):
        """Test authority notification requirements."""
        # Critical, High, and Medium require authority notification
        assert BreachSeverity.CRITICAL.requires_authority_notification is True
        assert BreachSeverity.HIGH.requires_authority_notification is True
        assert BreachSeverity.MEDIUM.requires_authority_notification is True

        # Low does not require notification
        assert BreachSeverity.LOW.requires_authority_notification is False

    def test_requires_individual_notification_property(self):
        """Test individual notification requirements."""
        # Critical and High require individual notification
        assert BreachSeverity.CRITICAL.requires_individual_notification is True
        assert BreachSeverity.HIGH.requires_individual_notification is True

        # Medium and Low do not require individual notification
        assert BreachSeverity.MEDIUM.requires_individual_notification is False
        assert BreachSeverity.LOW.requires_individual_notification is False


class TestAIRiskClassification:
    """Tests for the AIRiskClassification enum."""

    def test_all_risk_classifications_exist(self):
        """Test that all AI risk classifications exist."""
        expected_classifications = [
            "unacceptable", "high_risk", "limited_risk",
            "minimal_risk", "gpai", "gpai_systemic"
        ]

        for classification in expected_classifications:
            assert AIRiskClassification(classification) is not None

    def test_requires_conformity_assessment_property(self):
        """Test conformity assessment requirements."""
        # High risk and GPAI with systemic risk require assessment
        assert AIRiskClassification.HIGH_RISK.requires_conformity_assessment is True
        assert AIRiskClassification.GPAI_SYSTEMIC.requires_conformity_assessment is True

        # Others do not
        assert AIRiskClassification.LIMITED_RISK.requires_conformity_assessment is False
        assert AIRiskClassification.MINIMAL_RISK.requires_conformity_assessment is False
        assert AIRiskClassification.GPAI.requires_conformity_assessment is False

    def test_requires_registration_property(self):
        """Test EU database registration requirements."""
        # High risk, GPAI, and GPAI systemic require registration
        assert AIRiskClassification.HIGH_RISK.requires_registration is True
        assert AIRiskClassification.GPAI.requires_registration is True
        assert AIRiskClassification.GPAI_SYSTEMIC.requires_registration is True

        # Others do not
        assert AIRiskClassification.LIMITED_RISK.requires_registration is False
        assert AIRiskClassification.MINIMAL_RISK.requires_registration is False

    def test_max_penalty_percent_revenue_property(self):
        """Test maximum penalty percentages."""
        # Unacceptable has highest penalty (7%)
        assert AIRiskClassification.UNACCEPTABLE.max_penalty_percent_revenue == 7.0

        # High risk and GPAI systemic (3%)
        assert AIRiskClassification.HIGH_RISK.max_penalty_percent_revenue == 3.0
        assert AIRiskClassification.GPAI_SYSTEMIC.max_penalty_percent_revenue == 3.0

        # Limited risk (1.5%)
        assert AIRiskClassification.LIMITED_RISK.max_penalty_percent_revenue == 1.5


class TestEncryptionStandard:
    """Tests for the EncryptionStandard enum."""

    def test_all_standards_exist(self):
        """Test that all encryption standards exist."""
        expected_standards = [
            "aes_256_gcm", "aes_256_cbc", "chacha20",
            "rsa_4096", "ecdsa_p384", "tls_1_3", "tls_1_2"
        ]

        for standard in expected_standards:
            assert EncryptionStandard(standard) is not None


class TestKeyRotationPolicy:
    """Tests for the KeyRotationPolicy enum."""

    def test_all_policies_exist(self):
        """Test that all key rotation policies exist."""
        expected_policies = ["30d", "90d", "180d", "1y", "2y"]

        for policy in expected_policies:
            assert KeyRotationPolicy(policy) is not None


class TestAccessControlModel:
    """Tests for the AccessControlModel enum."""

    def test_all_models_exist(self):
        """Test that all access control models exist."""
        expected_models = [
            "rbac", "abac", "pbac", "dac", "mac", "zero_trust"
        ]

        for model in expected_models:
            assert AccessControlModel(model) is not None


class TestAuditEventCategory:
    """Tests for the AuditEventCategory enum."""

    def test_all_categories_exist(self):
        """Test that all audit event categories exist."""
        expected_categories = [
            "authentication", "authorization", "data_access",
            "data_modification", "system", "security",
            "privacy", "ai_decision", "compliance"
        ]

        for category in expected_categories:
            assert AuditEventCategory(category) is not None
