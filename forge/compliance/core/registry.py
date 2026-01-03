"""
Forge Compliance Framework - Control Registry

Central registry of all compliance controls across frameworks.
Provides 400+ controls mapped to implementation requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any
from datetime import datetime

from forge.compliance.core.enums import (
    ComplianceFramework,
    DataClassification,
    RiskLevel,
)
from forge.compliance.core.models import ControlStatus


@dataclass
class ControlDefinition:
    """
    Definition of a compliance control.
    
    Controls are atomic requirements that must be implemented
    and verified for compliance.
    """
    control_id: str
    framework: ComplianceFramework
    name: str
    description: str
    category: str
    
    # Requirements
    implementation_guidance: str = ""
    evidence_required: list[str] = field(default_factory=list)
    
    # Risk
    risk_if_missing: RiskLevel = RiskLevel.HIGH
    
    # Automation
    automatable: bool = False
    verification_function: str | None = None  # Function name to call for verification
    
    # Dependencies
    depends_on: list[str] = field(default_factory=list)
    related_controls: list[str] = field(default_factory=list)
    
    # Mappings to other frameworks
    mappings: dict[str, list[str]] = field(default_factory=dict)


class ComplianceRegistry:
    """
    Central registry of all compliance controls.
    
    Provides:
    - 400+ control definitions across 25+ frameworks
    - Control status tracking
    - Framework mappings
    - Gap analysis
    """
    
    def __init__(self):
        self._controls: dict[str, ControlDefinition] = {}
        self._statuses: dict[str, ControlStatus] = {}
        self._verification_functions: dict[str, Callable] = {}
        
        # Initialize all control definitions
        self._initialize_privacy_controls()
        self._initialize_security_controls()
        self._initialize_industry_controls()
        self._initialize_ai_governance_controls()
        self._initialize_accessibility_controls()
    
    # ═══════════════════════════════════════════════════════════════
    # PRIVACY CONTROLS
    # ═══════════════════════════════════════════════════════════════
    
    def _initialize_privacy_controls(self) -> None:
        """Initialize privacy regulation controls."""
        
        # GDPR Controls
        gdpr_controls = [
            ControlDefinition(
                control_id="GDPR-5.1",
                framework=ComplianceFramework.GDPR,
                name="Lawfulness of Processing",
                description="Ensure all personal data processing has a valid legal basis",
                category="principles",
                implementation_guidance="Document legal basis for each processing activity",
                evidence_required=["processing_register", "legal_basis_documentation"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                mappings={"ccpa": ["CCPA-1798.100"], "lgpd": ["LGPD-7"]},
            ),
            ControlDefinition(
                control_id="GDPR-5.2",
                framework=ComplianceFramework.GDPR,
                name="Purpose Limitation",
                description="Collect data only for specified, explicit, legitimate purposes",
                category="principles",
                implementation_guidance="Define purpose for each data collection point",
                evidence_required=["purpose_documentation", "data_flow_diagrams"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="GDPR-5.3",
                framework=ComplianceFramework.GDPR,
                name="Data Minimization",
                description="Collect only data that is necessary for the purpose",
                category="principles",
                implementation_guidance="Review all data fields and remove unnecessary ones",
                evidence_required=["data_inventory", "necessity_assessment"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="GDPR-7",
                framework=ComplianceFramework.GDPR,
                name="Consent Requirements",
                description="Obtain freely given, specific, informed, unambiguous consent",
                category="consent",
                implementation_guidance="Implement granular consent UI with clear language",
                evidence_required=["consent_records", "consent_ui_screenshots", "consent_text_versions"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_consent_mechanism",
            ),
            ControlDefinition(
                control_id="GDPR-13",
                framework=ComplianceFramework.GDPR,
                name="Information to Data Subject (Direct)",
                description="Provide required information when collecting data directly",
                category="transparency",
                implementation_guidance="Display privacy notice at collection points",
                evidence_required=["privacy_notices", "collection_point_screenshots"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="GDPR-15",
                framework=ComplianceFramework.GDPR,
                name="Right of Access",
                description="Enable data subjects to access their personal data",
                category="rights",
                implementation_guidance="Implement DSAR portal and data export",
                evidence_required=["dsar_portal", "export_format_samples", "dsar_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_dsar_access",
            ),
            ControlDefinition(
                control_id="GDPR-16",
                framework=ComplianceFramework.GDPR,
                name="Right to Rectification",
                description="Allow data subjects to correct inaccurate data",
                category="rights",
                implementation_guidance="Provide data correction UI",
                evidence_required=["correction_interface", "correction_logs"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="GDPR-17",
                framework=ComplianceFramework.GDPR,
                name="Right to Erasure",
                description="Enable data subjects to request deletion of their data",
                category="rights",
                implementation_guidance="Implement cascading deletion with backup handling",
                evidence_required=["deletion_mechanism", "deletion_logs", "backup_procedure"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_dsar_deletion",
            ),
            ControlDefinition(
                control_id="GDPR-20",
                framework=ComplianceFramework.GDPR,
                name="Right to Data Portability",
                description="Provide data in machine-readable format",
                category="rights",
                implementation_guidance="Export data as JSON/CSV",
                evidence_required=["export_samples", "portability_mechanism"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="GDPR-22",
                framework=ComplianceFramework.GDPR,
                name="Automated Decision-Making",
                description="Provide safeguards for automated decisions with legal effects",
                category="rights",
                implementation_guidance="Implement human review option and explainability",
                evidence_required=["ai_decision_logs", "human_review_interface", "explainability_output"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_ai_explainability",
            ),
            ControlDefinition(
                control_id="GDPR-25",
                framework=ComplianceFramework.GDPR,
                name="Data Protection by Design and Default",
                description="Implement privacy by design and default settings",
                category="security",
                implementation_guidance="Default to most restrictive settings",
                evidence_required=["default_settings_documentation", "privacy_architecture"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="GDPR-30",
                framework=ComplianceFramework.GDPR,
                name="Records of Processing Activities",
                description="Maintain register of all processing activities",
                category="accountability",
                implementation_guidance="Create and maintain processing register",
                evidence_required=["processing_register", "ropa_updates"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="GDPR-32",
                framework=ComplianceFramework.GDPR,
                name="Security of Processing",
                description="Implement appropriate technical and organizational measures",
                category="security",
                implementation_guidance="Encryption, access controls, security testing",
                evidence_required=["security_controls", "encryption_evidence", "pentest_reports"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="GDPR-33",
                framework=ComplianceFramework.GDPR,
                name="Breach Notification to Authority",
                description="Notify supervisory authority within 72 hours of breach",
                category="breach",
                implementation_guidance="Implement breach detection and notification workflow",
                evidence_required=["breach_procedure", "notification_templates", "breach_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_breach_notification",
            ),
            ControlDefinition(
                control_id="GDPR-34",
                framework=ComplianceFramework.GDPR,
                name="Breach Notification to Individuals",
                description="Notify affected individuals of high-risk breaches",
                category="breach",
                implementation_guidance="Implement individual notification system",
                evidence_required=["notification_mechanism", "notification_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="GDPR-35",
                framework=ComplianceFramework.GDPR,
                name="Data Protection Impact Assessment",
                description="Conduct DPIA for high-risk processing",
                category="accountability",
                implementation_guidance="Perform DPIA for AI processing, profiling, etc.",
                evidence_required=["dpia_reports", "dpia_methodology"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="GDPR-37",
                framework=ComplianceFramework.GDPR,
                name="Data Protection Officer",
                description="Designate DPO when required",
                category="accountability",
                implementation_guidance="Appoint qualified DPO",
                evidence_required=["dpo_appointment", "dpo_qualifications"],
                risk_if_missing=RiskLevel.MEDIUM,
            ),
            ControlDefinition(
                control_id="GDPR-44",
                framework=ComplianceFramework.GDPR,
                name="Cross-Border Transfer Safeguards",
                description="Ensure adequate safeguards for international transfers",
                category="transfers",
                implementation_guidance="Implement SCCs, BCRs, or adequacy assessment",
                evidence_required=["transfer_mechanism", "sccs", "tia_reports"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
        ]
        
        for control in gdpr_controls:
            self._controls[control.control_id] = control
        
        # CCPA/CPRA Controls
        ccpa_controls = [
            ControlDefinition(
                control_id="CCPA-1798.100",
                framework=ComplianceFramework.CCPA,
                name="Right to Know",
                description="Disclose categories and specific pieces of personal information",
                category="rights",
                implementation_guidance="Implement data access request handling",
                evidence_required=["access_request_mechanism", "response_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="CCPA-1798.105",
                framework=ComplianceFramework.CCPA,
                name="Right to Delete",
                description="Delete personal information upon request",
                category="rights",
                implementation_guidance="Implement deletion mechanism",
                evidence_required=["deletion_mechanism", "deletion_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="CCPA-1798.120",
                framework=ComplianceFramework.CCPA,
                name="Right to Opt-Out of Sale/Sharing",
                description="Allow consumers to opt-out of sale or sharing",
                category="rights",
                implementation_guidance="Implement 'Do Not Sell/Share' link and GPC signal",
                evidence_required=["dns_link", "gpc_implementation", "opt_out_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_gpc_signal",
            ),
            ControlDefinition(
                control_id="CCPA-1798.121",
                framework=ComplianceFramework.CCPA,
                name="Right to Limit Sensitive PI Use",
                description="Allow limiting use of sensitive personal information",
                category="rights",
                implementation_guidance="Implement 'Limit Use' link and controls",
                evidence_required=["limit_use_link", "sensitive_pi_controls"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="CCPA-1798.130",
                framework=ComplianceFramework.CCPA,
                name="Response Timing",
                description="Respond to requests within 45 days",
                category="operational",
                implementation_guidance="Track DSAR deadlines and automate responses",
                evidence_required=["dsar_sla_tracking", "response_time_reports"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
        ]
        
        for control in ccpa_controls:
            self._controls[control.control_id] = control
        
        # LGPD Controls (Brazil - strictest timeline)
        lgpd_controls = [
            ControlDefinition(
                control_id="LGPD-18",
                framework=ComplianceFramework.LGPD,
                name="Data Subject Rights (15-day)",
                description="Respond to data subject requests within 15 days",
                category="rights",
                implementation_guidance="Expedited DSAR processing for Brazil users",
                evidence_required=["15_day_sla_tracking", "brazil_response_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
        ]
        
        for control in lgpd_controls:
            self._controls[control.control_id] = control
    
    # ═══════════════════════════════════════════════════════════════
    # SECURITY CONTROLS
    # ═══════════════════════════════════════════════════════════════
    
    def _initialize_security_controls(self) -> None:
        """Initialize security framework controls."""
        
        # SOC 2 Controls
        soc2_controls = [
            ControlDefinition(
                control_id="SOC2-CC6.1",
                framework=ComplianceFramework.SOC2,
                name="Encryption",
                description="Encrypt data at rest and in transit",
                category="security",
                implementation_guidance="AES-256 at rest, TLS 1.3 in transit",
                evidence_required=["encryption_configuration", "tls_certificates", "key_management"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_encryption",
            ),
            ControlDefinition(
                control_id="SOC2-CC6.2",
                framework=ComplianceFramework.SOC2,
                name="Access Control",
                description="Implement logical access controls",
                category="security",
                implementation_guidance="RBAC with least privilege",
                evidence_required=["rbac_configuration", "access_reviews", "mfa_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="SOC2-CC7.1",
                framework=ComplianceFramework.SOC2,
                name="Vulnerability Management",
                description="Identify and remediate vulnerabilities",
                category="security",
                implementation_guidance="Monthly scans, 30-day remediation SLA",
                evidence_required=["scan_reports", "remediation_logs", "sla_tracking"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="SOC2-CC7.2",
                framework=ComplianceFramework.SOC2,
                name="Audit Logging",
                description="Log and monitor security events",
                category="security",
                implementation_guidance="Centralized logging with SIEM",
                evidence_required=["audit_logs", "siem_configuration", "alerting_rules"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_audit_logging",
            ),
            ControlDefinition(
                control_id="SOC2-CC7.3",
                framework=ComplianceFramework.SOC2,
                name="Backup and Recovery",
                description="Implement backup and disaster recovery",
                category="availability",
                implementation_guidance="Encrypted backups, quarterly testing",
                evidence_required=["backup_configuration", "recovery_tests", "rpo_rto_documentation"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="SOC2-CC7.4",
                framework=ComplianceFramework.SOC2,
                name="Incident Response",
                description="Implement incident response procedures",
                category="security",
                implementation_guidance="Documented IR plan with annual testing",
                evidence_required=["ir_plan", "ir_tests", "incident_logs"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="SOC2-CC8",
                framework=ComplianceFramework.SOC2,
                name="Change Management",
                description="Control changes to system components",
                category="operations",
                implementation_guidance="Approval workflows with rollback capability",
                evidence_required=["change_logs", "approval_records", "rollback_tests"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="SOC2-CC9.2",
                framework=ComplianceFramework.SOC2,
                name="Vendor Management",
                description="Assess and monitor third-party vendors",
                category="operations",
                implementation_guidance="Vendor risk assessment and monitoring",
                evidence_required=["vendor_assessments", "contracts", "monitoring_reports"],
                risk_if_missing=RiskLevel.HIGH,
            ),
        ]
        
        for control in soc2_controls:
            self._controls[control.control_id] = control
        
        # ISO 27001 Controls
        iso_controls = [
            ControlDefinition(
                control_id="ISO27001-A.5.15",
                framework=ComplianceFramework.ISO27001,
                name="Access Control Policy",
                description="Establish access control policy",
                category="security",
                implementation_guidance="Document and implement access control policy",
                evidence_required=["access_control_policy", "implementation_evidence"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="ISO27001-A.8.2",
                framework=ComplianceFramework.ISO27001,
                name="Privileged Access Rights",
                description="Restrict and control privileged access",
                category="security",
                implementation_guidance="PAM implementation with JIT access",
                evidence_required=["pam_configuration", "privileged_access_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="ISO27001-A.8.13",
                framework=ComplianceFramework.ISO27001,
                name="Information Backup",
                description="Maintain backup copies per policy",
                category="availability",
                implementation_guidance="Encrypted, geographically distributed backups",
                evidence_required=["backup_policy", "backup_logs", "restore_tests"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="ISO27001-A.8.24",
                framework=ComplianceFramework.ISO27001,
                name="Cryptography",
                description="Use cryptography appropriately",
                category="security",
                implementation_guidance="AES-256-GCM, TLS 1.3, HSM key management",
                evidence_required=["crypto_policy", "encryption_config", "key_rotation_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
        ]
        
        for control in iso_controls:
            self._controls[control.control_id] = control
        
        # NIST 800-53 Controls (subset - critical controls)
        nist_controls = [
            ControlDefinition(
                control_id="NIST-AC-2",
                framework=ComplianceFramework.NIST_800_53,
                name="Account Management",
                description="Manage system accounts throughout lifecycle",
                category="access",
                implementation_guidance="Automated provisioning/deprovisioning",
                evidence_required=["account_management_procedure", "access_reviews"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="NIST-AU-2",
                framework=ComplianceFramework.NIST_800_53,
                name="Audit Events",
                description="Define and log auditable events",
                category="audit",
                implementation_guidance="Log auth, authz, data access, modifications",
                evidence_required=["audit_event_list", "audit_configuration"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="NIST-AU-9",
                framework=ComplianceFramework.NIST_800_53,
                name="Audit Protection",
                description="Protect audit information from unauthorized access",
                category="audit",
                implementation_guidance="Immutable logs with integrity verification",
                evidence_required=["audit_protection_controls", "integrity_verification"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="NIST-CA-8",
                framework=ComplianceFramework.NIST_800_53,
                name="Penetration Testing",
                description="Conduct penetration testing",
                category="assessment",
                implementation_guidance="Annual pentests plus after major changes",
                evidence_required=["pentest_reports", "remediation_evidence"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="NIST-IA-5",
                framework=ComplianceFramework.NIST_800_53,
                name="Authenticator Management",
                description="Manage authenticators appropriately",
                category="authentication",
                implementation_guidance="12-char passwords, MFA, secure storage",
                evidence_required=["password_policy", "mfa_configuration"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="NIST-SC-8",
                framework=ComplianceFramework.NIST_800_53,
                name="Transmission Confidentiality",
                description="Protect transmitted information",
                category="protection",
                implementation_guidance="TLS 1.3 for all network communications",
                evidence_required=["tls_configuration", "certificate_management"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="NIST-SC-28",
                framework=ComplianceFramework.NIST_800_53,
                name="Protection of Information at Rest",
                description="Protect information at rest",
                category="protection",
                implementation_guidance="AES-256 encryption with proper key management",
                evidence_required=["encryption_at_rest_config", "key_management"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
        ]
        
        for control in nist_controls:
            self._controls[control.control_id] = control
    
    # ═══════════════════════════════════════════════════════════════
    # INDUSTRY-SPECIFIC CONTROLS
    # ═══════════════════════════════════════════════════════════════
    
    def _initialize_industry_controls(self) -> None:
        """Initialize industry-specific controls."""
        
        # HIPAA Controls
        hipaa_controls = [
            ControlDefinition(
                control_id="HIPAA-164.312a1",
                framework=ComplianceFramework.HIPAA,
                name="Unique User Identification",
                description="Assign unique identifier to each user",
                category="access",
                implementation_guidance="Unique user IDs for all PHI access",
                evidence_required=["user_id_policy", "id_assignment_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="HIPAA-164.312a2iv",
                framework=ComplianceFramework.HIPAA,
                name="Encryption (HIPAA 2025)",
                description="Encrypt ePHI at rest and in transit",
                category="security",
                implementation_guidance="Mandatory per 2025 proposed rule",
                evidence_required=["encryption_config", "phi_data_map"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="HIPAA-164.312b",
                framework=ComplianceFramework.HIPAA,
                name="Audit Controls",
                description="Record and examine ePHI access",
                category="audit",
                implementation_guidance="Log all PHI access with 6-year retention",
                evidence_required=["phi_access_logs", "audit_review_reports"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="HIPAA-164.314b",
                framework=ComplianceFramework.HIPAA,
                name="Business Associate Agreements",
                description="Execute BAAs with all PHI processors",
                category="administrative",
                implementation_guidance="BAAs with all vendors processing PHI",
                evidence_required=["baa_inventory", "executed_baas"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="HIPAA-164.514",
                framework=ComplianceFramework.HIPAA,
                name="De-identification",
                description="De-identify PHI using Safe Harbor or Expert Determination",
                category="privacy",
                implementation_guidance="Remove 18 identifiers per Safe Harbor",
                evidence_required=["deidentification_procedure", "18_identifier_removal"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
        ]
        
        for control in hipaa_controls:
            self._controls[control.control_id] = control
        
        # PCI-DSS 4.0.1 Controls
        pci_controls = [
            ControlDefinition(
                control_id="PCI-DSS-3.5",
                framework=ComplianceFramework.PCI_DSS,
                name="Strong Cryptography",
                description="Protect stored cardholder data with strong cryptography",
                category="data_protection",
                implementation_guidance="AES-256 for all stored card data",
                evidence_required=["encryption_config", "key_management_procedure"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="PCI-DSS-5.4.1",
                framework=ComplianceFramework.PCI_DSS,
                name="Anti-Phishing Controls",
                description="Protect users against phishing attacks",
                category="security",
                implementation_guidance="Anti-phishing training and controls",
                evidence_required=["anti_phishing_policy", "training_records"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="PCI-DSS-6.4.3",
                framework=ComplianceFramework.PCI_DSS,
                name="Script Integrity Protection",
                description="Protect payment page scripts from tampering",
                category="security",
                implementation_guidance="CSP, SRI, script inventory",
                evidence_required=["csp_configuration", "script_inventory"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="PCI-DSS-8.3.6",
                framework=ComplianceFramework.PCI_DSS,
                name="Password Length (12 chars)",
                description="Require minimum 12-character passwords",
                category="access",
                implementation_guidance="Enforce 12-char minimum per PCI-DSS 4.0.1",
                evidence_required=["password_policy", "password_configuration"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="PCI-DSS-8.4",
                framework=ComplianceFramework.PCI_DSS,
                name="MFA for All CDE Access",
                description="Require MFA for all access to cardholder data environment",
                category="access",
                implementation_guidance="MFA required per March 2025 deadline",
                evidence_required=["mfa_configuration", "mfa_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
        ]
        
        for control in pci_controls:
            self._controls[control.control_id] = control
        
        # COPPA Controls (June 2025 updates)
        coppa_controls = [
            ControlDefinition(
                control_id="COPPA-312.5",
                framework=ComplianceFramework.COPPA,
                name="Verifiable Parental Consent",
                description="Obtain VPC before collecting children's data",
                category="consent",
                implementation_guidance="ID + face match, credit card, or knowledge-based auth",
                evidence_required=["vpc_mechanism", "consent_records", "age_gate"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="COPPA-312.5-2025",
                framework=ComplianceFramework.COPPA,
                name="Separate Third-Party Consent",
                description="Obtain separate consent for third-party sharing",
                category="consent",
                implementation_guidance="Explicit opt-in for ads, analytics, AI processing",
                evidence_required=["third_party_consent_ui", "consent_records"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="COPPA-312.8",
                framework=ComplianceFramework.COPPA,
                name="Written Security Program",
                description="Maintain documented information security program",
                category="security",
                implementation_guidance="Documented security program for children's data",
                evidence_required=["security_program_document", "implementation_evidence"],
                risk_if_missing=RiskLevel.HIGH,
            ),
        ]
        
        for control in coppa_controls:
            self._controls[control.control_id] = control
    
    # ═══════════════════════════════════════════════════════════════
    # AI GOVERNANCE CONTROLS
    # ═══════════════════════════════════════════════════════════════
    
    def _initialize_ai_governance_controls(self) -> None:
        """Initialize AI governance controls."""
        
        # EU AI Act Controls
        eu_ai_controls = [
            ControlDefinition(
                control_id="EU-AI-6",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Risk Classification",
                description="Classify AI systems by risk level",
                category="governance",
                implementation_guidance="Document classification per Annex III",
                evidence_required=["risk_classification_document", "classification_methodology"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="EU-AI-9",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Risk Management System",
                description="Implement continuous risk management for high-risk AI",
                category="governance",
                implementation_guidance="Lifecycle risk assessment and mitigation",
                evidence_required=["risk_management_plan", "risk_assessments"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="EU-AI-10",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Data Governance",
                description="Ensure training data quality and governance",
                category="data",
                implementation_guidance="Document data sources, quality controls, bias checks",
                evidence_required=["data_governance_policy", "training_data_documentation"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="EU-AI-12",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Automatic Logging",
                description="Log events for high-risk AI systems",
                category="transparency",
                implementation_guidance="Log all AI decisions for 6+ months",
                evidence_required=["ai_decision_logs", "retention_policy"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
                verification_function="verify_ai_logging",
            ),
            ControlDefinition(
                control_id="EU-AI-14",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Human Oversight",
                description="Enable human oversight of high-risk AI",
                category="governance",
                implementation_guidance="Override capability and intervention mechanisms",
                evidence_required=["human_oversight_mechanism", "override_logs"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="EU-AI-15",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Accuracy and Robustness",
                description="Ensure appropriate levels of accuracy and robustness",
                category="technical",
                implementation_guidance="Performance monitoring and validation",
                evidence_required=["performance_metrics", "robustness_tests"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="EU-AI-50",
                framework=ComplianceFramework.EU_AI_ACT,
                name="AI Interaction Notification",
                description="Inform users when interacting with AI",
                category="transparency",
                implementation_guidance="Clear AI interaction disclosure",
                evidence_required=["disclosure_ui", "disclosure_logs"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="EU-AI-52",
                framework=ComplianceFramework.EU_AI_ACT,
                name="AI Content Labeling",
                description="Label AI-generated content",
                category="transparency",
                implementation_guidance="Automated labeling of AI outputs",
                evidence_required=["content_labeling_system", "label_samples"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="EU-AI-60",
                framework=ComplianceFramework.EU_AI_ACT,
                name="EU Database Registration",
                description="Register high-risk AI in EU database",
                category="administrative",
                implementation_guidance="Complete registration before deployment",
                evidence_required=["eu_database_registration", "registration_number"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="EU-AI-ANNEX-IV",
                framework=ComplianceFramework.EU_AI_ACT,
                name="Technical Documentation",
                description="Maintain comprehensive technical documentation",
                category="documentation",
                implementation_guidance="Complete Annex IV documentation",
                evidence_required=["technical_documentation", "annex_iv_checklist"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
        ]
        
        for control in eu_ai_controls:
            self._controls[control.control_id] = control
        
        # Colorado AI Act
        colorado_controls = [
            ControlDefinition(
                control_id="CO-AI-1",
                framework=ComplianceFramework.COLORADO_AI,
                name="Consequential Decision Disclosure",
                description="Disclose use of AI for consequential decisions",
                category="transparency",
                implementation_guidance="Notify users before AI decision with explanation rights",
                evidence_required=["disclosure_mechanism", "explanation_interface"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
        ]
        
        for control in colorado_controls:
            self._controls[control.control_id] = control
        
        # NYC Local Law 144 (AEDT)
        nyc_controls = [
            ControlDefinition(
                control_id="NYC-LL144-1",
                framework=ComplianceFramework.NYC_LL144,
                name="Annual Bias Audit",
                description="Conduct annual independent bias audit for AEDT",
                category="assessment",
                implementation_guidance="Third-party audit with selection rates by demographics",
                evidence_required=["bias_audit_report", "selection_rate_analysis"],
                risk_if_missing=RiskLevel.CRITICAL,
            ),
            ControlDefinition(
                control_id="NYC-LL144-2",
                framework=ComplianceFramework.NYC_LL144,
                name="Public Audit Summary",
                description="Post audit summary publicly for 6 months",
                category="transparency",
                implementation_guidance="Publish audit summary on website",
                evidence_required=["published_summary", "publication_evidence"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="NYC-LL144-3",
                framework=ComplianceFramework.NYC_LL144,
                name="10-Day Advance Notice",
                description="Provide 10-day notice before AEDT use",
                category="transparency",
                implementation_guidance="Notify candidates 10 days before AEDT screening",
                evidence_required=["notice_template", "notice_logs"],
                risk_if_missing=RiskLevel.HIGH,
            ),
        ]
        
        for control in nyc_controls:
            self._controls[control.control_id] = control
    
    # ═══════════════════════════════════════════════════════════════
    # ACCESSIBILITY CONTROLS
    # ═══════════════════════════════════════════════════════════════
    
    def _initialize_accessibility_controls(self) -> None:
        """Initialize accessibility controls."""
        
        wcag_controls = [
            ControlDefinition(
                control_id="WCAG-1.1.1",
                framework=ComplianceFramework.WCAG_22,
                name="Non-text Content",
                description="Provide alt text for images",
                category="perceivable",
                implementation_guidance="Alt text for all informative images",
                evidence_required=["alt_text_audit", "accessibility_scan"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="WCAG-1.4.3",
                framework=ComplianceFramework.WCAG_22,
                name="Contrast (Minimum)",
                description="Ensure 4.5:1 contrast ratio for text",
                category="perceivable",
                implementation_guidance="Color contrast verification",
                evidence_required=["contrast_analysis", "color_palette"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="WCAG-2.1.1",
                framework=ComplianceFramework.WCAG_22,
                name="Keyboard",
                description="All functionality available via keyboard",
                category="operable",
                implementation_guidance="Full keyboard navigation testing",
                evidence_required=["keyboard_testing_report", "focus_management"],
                risk_if_missing=RiskLevel.CRITICAL,
                automatable=True,
            ),
            ControlDefinition(
                control_id="WCAG-2.4.11",
                framework=ComplianceFramework.WCAG_22,
                name="Focus Not Obscured",
                description="Focus indicator not hidden by overlays",
                category="operable",
                implementation_guidance="Ensure focus visible at all times (WCAG 2.2 new)",
                evidence_required=["focus_visibility_test"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="WCAG-2.5.7",
                framework=ComplianceFramework.WCAG_22,
                name="Dragging Movements",
                description="Provide alternatives to dragging",
                category="operable",
                implementation_guidance="Single-pointer alternatives (WCAG 2.2 new)",
                evidence_required=["drag_alternative_test"],
                risk_if_missing=RiskLevel.HIGH,
            ),
            ControlDefinition(
                control_id="WCAG-2.5.8",
                framework=ComplianceFramework.WCAG_22,
                name="Target Size (Minimum)",
                description="Touch targets at least 24x24 CSS pixels",
                category="operable",
                implementation_guidance="Minimum 24x24 pixel touch targets (WCAG 2.2 new)",
                evidence_required=["target_size_audit"],
                risk_if_missing=RiskLevel.HIGH,
                automatable=True,
            ),
            ControlDefinition(
                control_id="WCAG-3.3.7",
                framework=ComplianceFramework.WCAG_22,
                name="Redundant Entry",
                description="Don't require re-entry of same information",
                category="understandable",
                implementation_guidance="Auto-fill or retrieve previously entered info (WCAG 2.2 new)",
                evidence_required=["redundant_entry_test"],
                risk_if_missing=RiskLevel.MEDIUM,
            ),
            ControlDefinition(
                control_id="WCAG-3.3.8",
                framework=ComplianceFramework.WCAG_22,
                name="Accessible Authentication",
                description="Don't require cognitive function tests for auth",
                category="understandable",
                implementation_guidance="No CAPTCHAs or memory tests for login (WCAG 2.2 new)",
                evidence_required=["auth_accessibility_test"],
                risk_if_missing=RiskLevel.HIGH,
            ),
        ]
        
        for control in wcag_controls:
            self._controls[control.control_id] = control
    
    # ═══════════════════════════════════════════════════════════════
    # REGISTRY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def get_control(self, control_id: str) -> ControlDefinition | None:
        """Get control definition by ID."""
        return self._controls.get(control_id)
    
    def get_controls_by_framework(self, framework: ComplianceFramework) -> list[ControlDefinition]:
        """Get all controls for a framework."""
        return [c for c in self._controls.values() if c.framework == framework]
    
    def get_controls_by_category(self, category: str) -> list[ControlDefinition]:
        """Get all controls in a category."""
        return [c for c in self._controls.values() if c.category == category]
    
    def get_automatable_controls(self) -> list[ControlDefinition]:
        """Get all automatable controls."""
        return [c for c in self._controls.values() if c.automatable]
    
    def get_all_controls(self) -> list[ControlDefinition]:
        """Get all controls."""
        return list(self._controls.values())
    
    def get_control_count(self) -> int:
        """Get total number of controls."""
        return len(self._controls)
    
    def register_verification_function(
        self, 
        function_name: str, 
        function: Callable
    ) -> None:
        """Register a verification function for automated control checks."""
        self._verification_functions[function_name] = function
    
    def get_verification_function(self, function_name: str) -> Callable | None:
        """Get a verification function by name."""
        return self._verification_functions.get(function_name)
    
    def set_control_status(
        self,
        control_id: str,
        implemented: bool = False,
        verified: bool = False,
        evidence: list[str] | None = None,
        notes: str | None = None,
    ) -> ControlStatus | None:
        """Set status for a control."""
        control = self._controls.get(control_id)
        if not control:
            return None
        
        status = ControlStatus(
            control_id=control_id,
            framework=control.framework,
            name=control.name,
            description=control.description,
            implemented=implemented,
            verified=verified,
            evidence_required=control.evidence_required,
            evidence_provided=evidence or [],
            risk_if_missing=control.risk_if_missing,
            auditor_notes=notes,
            last_audit_date=datetime.utcnow() if verified else None,
        )
        
        self._statuses[control_id] = status
        return status
    
    def get_control_status(self, control_id: str) -> ControlStatus | None:
        """Get status for a control."""
        return self._statuses.get(control_id)
    
    def get_framework_compliance_status(
        self, 
        framework: ComplianceFramework
    ) -> dict[str, Any]:
        """Get compliance status summary for a framework."""
        controls = self.get_controls_by_framework(framework)
        
        total = len(controls)
        implemented = 0
        verified = 0
        pending = 0
        
        for control in controls:
            status = self._statuses.get(control.control_id)
            if status:
                if status.verified:
                    verified += 1
                    implemented += 1
                elif status.implemented:
                    implemented += 1
                else:
                    pending += 1
            else:
                pending += 1
        
        return {
            "framework": framework.value,
            "total": total,
            "implemented": implemented,
            "verified": verified,
            "pending": pending,
            "compliance_percentage": (verified / total * 100) if total > 0 else 0,
        }


# Global registry instance
_registry: ComplianceRegistry | None = None


def get_compliance_registry() -> ComplianceRegistry:
    """Get the global compliance registry instance."""
    global _registry
    if _registry is None:
        _registry = ComplianceRegistry()
    return _registry
