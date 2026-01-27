"""
Forge Compliance Framework - Configuration

Centralized configuration for all compliance frameworks, jurisdictions,
and control requirements.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field, BaseModel

# Try pydantic-settings first, fall back to pydantic BaseModel
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback for environments without pydantic-settings
    class BaseSettings(BaseModel):
        """Fallback BaseSettings using environment variables."""
        
        model_config = {"extra": "ignore"}
        
        def __init__(self, **data: Any):
            # Load from environment variables
            for field_name, field_info in self.model_fields.items():
                env_name = field_name.upper()
                if env_name in os.environ and field_name not in data:
                    data[field_name] = os.environ[env_name]
            super().__init__(**data)
    
    SettingsConfigDict = dict  # type: ignore

from forge.compliance.core.enums import (
    Jurisdiction,
    ComplianceFramework,
    EncryptionStandard,
    KeyRotationPolicy,
)


class ComplianceConfig(BaseSettings):
    """
    Compliance framework configuration.
    
    Loaded from environment variables with sensible defaults.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="FORGE_COMPLIANCE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # JURISDICTION CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    # Active jurisdictions (comma-separated)
    active_jurisdictions: str = Field(
        default="global,eu,us_federal,us_ca",
        description="Comma-separated list of active jurisdictions",
    )
    
    # Primary jurisdiction for default rules
    primary_jurisdiction: Jurisdiction = Field(
        default=Jurisdiction.GLOBAL,
        description="Primary jurisdiction for default rules",
    )
    
    @property
    def jurisdictions_list(self) -> list[Jurisdiction]:
        """Parse active jurisdictions."""
        result = []
        for j in self.active_jurisdictions.split(","):
            j = j.strip().lower()
            try:
                result.append(Jurisdiction(j))
            except ValueError:
                pass
        return result or [Jurisdiction.GLOBAL]
    
    # ═══════════════════════════════════════════════════════════════
    # FRAMEWORK CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    # Active frameworks (comma-separated)
    active_frameworks: str = Field(
        default="gdpr,ccpa,soc2,iso27001,hipaa,pci_dss,eu_ai_act,wcag_22",
        description="Comma-separated list of active compliance frameworks",
    )
    
    @property
    def frameworks_list(self) -> list[ComplianceFramework]:
        """Parse active frameworks."""
        result = []
        for f in self.active_frameworks.split(","):
            f = f.strip().lower()
            try:
                result.append(ComplianceFramework(f))
            except ValueError:
                pass
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # ENCRYPTION SETTINGS
    # ═══════════════════════════════════════════════════════════════
    
    # Encryption at rest
    encryption_at_rest_standard: EncryptionStandard = Field(
        default=EncryptionStandard.AES_256_GCM,
        description="Encryption standard for data at rest",
    )
    
    # Encryption in transit
    encryption_in_transit_minimum: EncryptionStandard = Field(
        default=EncryptionStandard.TLS_1_3,
        description="Minimum TLS version for data in transit",
    )
    
    # Key rotation
    key_rotation_policy: KeyRotationPolicy = Field(
        default=KeyRotationPolicy.DAYS_90,
        description="Key rotation frequency",
    )
    
    # HSM configuration
    hsm_enabled: bool = Field(
        default=False,
        description="Use Hardware Security Module for key management",
    )
    hsm_provider: str | None = Field(
        default=None,
        description="HSM provider (aws_cloudhsm, azure_dedicated, gcp_cloud_hsm, thales)",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # DATA RESIDENCY
    # ═══════════════════════════════════════════════════════════════
    
    # Enable data residency controls
    data_residency_enabled: bool = Field(
        default=True,
        description="Enable data residency controls",
    )
    
    # Regional data pods
    regional_pods: str = Field(
        default="us-east-1,eu-west-1,ap-southeast-1",
        description="Comma-separated list of regional data pod locations",
    )
    
    # Default data region
    default_data_region: str = Field(
        default="us-east-1",
        description="Default region for data storage",
    )
    
    # China data localization
    china_data_localization: bool = Field(
        default=False,
        description="Enable China PIPL data localization",
    )
    china_data_region: str = Field(
        default="cn-north-1",
        description="China data region",
    )
    
    # Russia data localization
    russia_data_localization: bool = Field(
        default=False,
        description="Enable Russia FZ-152 data localization",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # PRIVACY SETTINGS
    # ═══════════════════════════════════════════════════════════════
    
    # DSAR settings
    dsar_auto_verify_internal: bool = Field(
        default=True,
        description="Auto-verify DSARs from logged-in users",
    )
    dsar_default_response_days: int = Field(
        default=15,
        ge=1,
        le=30,
        description="Default DSAR response deadline (uses strictest: LGPD 15 days)",
    )
    dsar_extension_allowed: bool = Field(
        default=True,
        description="Allow DSAR deadline extensions",
    )
    dsar_max_extension_days: int = Field(
        default=30,
        description="Maximum extension period",
    )
    
    # Consent settings
    consent_explicit_required: bool = Field(
        default=True,
        description="Require explicit opt-in consent (strictest standard)",
    )
    consent_granular: bool = Field(
        default=True,
        description="Enable granular per-purpose consent",
    )
    consent_tcf_enabled: bool = Field(
        default=True,
        description="Enable IAB TCF 2.2 consent framework",
    )
    consent_gpc_enabled: bool = Field(
        default=True,
        description="Enable Global Privacy Control signal detection",
    )
    
    # Breach notification
    breach_notification_hours: int = Field(
        default=72,
        description="Maximum hours to notify authorities of breach",
    )
    breach_auto_detect: bool = Field(
        default=True,
        description="Enable automatic breach detection",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # AUDIT LOGGING
    # ═══════════════════════════════════════════════════════════════
    
    # Audit log retention (years)
    audit_log_retention_years: int = Field(
        default=7,
        ge=1,
        le=25,
        description="Audit log retention period (SOX requires 7 years)",
    )
    
    # Immutable logging
    audit_immutable: bool = Field(
        default=True,
        description="Enable cryptographic audit log chaining",
    )
    
    # Real-time SIEM integration
    siem_enabled: bool = Field(
        default=False,
        description="Enable SIEM integration",
    )
    siem_endpoint: str | None = Field(
        default=None,
        description="SIEM webhook endpoint",
    )
    
    # Audit event categories to log
    audit_categories: str = Field(
        default="authentication,authorization,data_access,data_modification,privacy,ai_decision,security,compliance",
        description="Comma-separated audit categories to log",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # AI GOVERNANCE
    # ═══════════════════════════════════════════════════════════════
    
    # EU AI Act compliance
    eu_ai_act_enabled: bool = Field(
        default=True,
        description="Enable EU AI Act compliance",
    )
    
    # Default AI risk classification
    default_ai_risk_classification: str = Field(
        default="high_risk",
        description="Default AI system risk classification",
    )
    
    # Human oversight
    ai_human_oversight_required: bool = Field(
        default=True,
        description="Require human oversight for AI decisions",
    )
    ai_decision_logging: bool = Field(
        default=True,
        description="Log all AI decisions",
    )
    ai_explainability_required: bool = Field(
        default=True,
        description="Require explainability for AI decisions",
    )
    
    # Bias audit
    ai_bias_audit_frequency_days: int = Field(
        default=365,
        description="Frequency of AI bias audits",
    )
    
    # Training data disclosure (CA AB 2013)
    ai_training_data_disclosure: bool = Field(
        default=True,
        description="Enable AI training data disclosure",
    )
    
    # Content labeling
    ai_content_labeling: bool = Field(
        default=True,
        description="Label AI-generated content",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # INDUSTRY-SPECIFIC
    # ═══════════════════════════════════════════════════════════════
    
    # HIPAA
    hipaa_enabled: bool = Field(
        default=True,
        description="Enable HIPAA compliance for PHI",
    )
    hipaa_minimum_necessary: bool = Field(
        default=True,
        description="Enforce minimum necessary standard",
    )
    hipaa_baa_required: bool = Field(
        default=True,
        description="Require BAAs with all PHI processors",
    )
    
    # PCI-DSS
    pci_dss_enabled: bool = Field(
        default=True,
        description="Enable PCI-DSS compliance for payment data",
    )
    pci_dss_version: str = Field(
        default="4.0.1",
        description="PCI-DSS version",
    )
    pci_dss_saq_level: str = Field(
        default="SAQ-A",
        description="PCI-DSS SAQ level",
    )
    
    # COPPA
    coppa_enabled: bool = Field(
        default=True,
        description="Enable COPPA compliance for children's data",
    )
    coppa_age_threshold: int = Field(
        default=13,
        description="Age threshold for COPPA",
    )
    coppa_vpc_methods: str = Field(
        default="id_face_match,credit_card,knowledge_auth",
        description="Verifiable Parental Consent methods",
    )
    
    # FERPA
    ferpa_enabled: bool = Field(
        default=True,
        description="Enable FERPA compliance for educational records",
    )
    
    # GLBA
    glba_enabled: bool = Field(
        default=True,
        description="Enable GLBA compliance for financial data",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # ACCESSIBILITY
    # ═══════════════════════════════════════════════════════════════
    
    # WCAG compliance level
    wcag_level: str = Field(
        default="AA",
        description="WCAG compliance level (A, AA, AAA)",
    )
    wcag_version: str = Field(
        default="2.2",
        description="WCAG version",
    )
    
    # Automated testing
    accessibility_auto_test: bool = Field(
        default=True,
        description="Enable automated accessibility testing",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # ACCESS CONTROL
    # ═══════════════════════════════════════════════════════════════
    
    # MFA requirements
    mfa_required: bool = Field(
        default=True,
        description="Require MFA for all users",
    )
    mfa_required_admin: bool = Field(
        default=True,
        description="Require MFA for admin access",
    )
    mfa_required_sensitive_data: bool = Field(
        default=True,
        description="Require MFA for sensitive data access",
    )
    
    # Password policy (PCI-DSS 4.0.1)
    password_min_length: int = Field(
        default=12,
        ge=12,
        description="Minimum password length (PCI-DSS 4.0.1 requires 12)",
    )
    password_require_complexity: bool = Field(
        default=True,
        description="Require password complexity",
    )
    password_expiry_days: int = Field(
        default=90,
        description="Password expiry period",
    )
    password_history_count: int = Field(
        default=12,
        description="Number of previous passwords to remember",
    )
    
    # Session management
    session_timeout_minutes: int = Field(
        default=30,
        description="Session timeout for sensitive operations",
    )
    session_max_concurrent: int = Field(
        default=3,
        description="Maximum concurrent sessions",
    )
    
    # Access reviews
    access_review_frequency_days: int = Field(
        default=90,
        description="Frequency of access reviews",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # VULNERABILITY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    # Scanning
    vulnerability_scan_frequency_days: int = Field(
        default=30,
        description="Vulnerability scan frequency",
    )
    vulnerability_remediation_days_critical: int = Field(
        default=7,
        description="Remediation SLA for critical vulnerabilities",
    )
    vulnerability_remediation_days_high: int = Field(
        default=30,
        description="Remediation SLA for high vulnerabilities",
    )
    
    # Penetration testing
    pentest_frequency_months: int = Field(
        default=12,
        description="Penetration testing frequency",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════════════════════════
    
    # Compliance report generation
    report_auto_generate: bool = Field(
        default=True,
        description="Auto-generate compliance reports",
    )
    report_frequency_days: int = Field(
        default=30,
        description="Report generation frequency",
    )
    report_recipients: str = Field(
        default="",
        description="Comma-separated report recipients",
    )
    
    # DPO contact
    dpo_email: str = Field(
        default="dpo@example.com",
        description="Data Protection Officer email",
    )
    dpo_name: str = Field(
        default="",
        description="Data Protection Officer name",
    )
    
    # ═══════════════════════════════════════════════════════════════
    # VENDOR MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    # Third-party risk
    vendor_assessment_required: bool = Field(
        default=True,
        description="Require security assessment for vendors",
    )
    vendor_review_frequency_months: int = Field(
        default=12,
        description="Vendor review frequency",
    )
    
    # Sub-processor management
    subprocessor_notification_days: int = Field(
        default=30,
        description="Days notice for sub-processor changes",
    )


@lru_cache
def get_compliance_config() -> ComplianceConfig:
    """Get cached compliance configuration."""
    return ComplianceConfig()
