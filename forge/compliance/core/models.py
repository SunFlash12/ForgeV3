"""
Forge Compliance Framework - Core Models

Pydantic models for compliance controls, audit events, data subject requests,
consent records, breach notifications, and compliance reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Any, ClassVar
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from forge.compliance.core.enums import (
    Jurisdiction,
    ComplianceFramework,
    DataClassification,
    RiskLevel,
    ConsentType,
    DSARType,
    BreachSeverity,
    AIRiskClassification,
    AuditEventCategory,
    EncryptionStandard,
)


def generate_id() -> str:
    """Generate a unique identifier."""
    return str(uuid4())


# ═══════════════════════════════════════════════════════════════════════════
# BASE MODELS
# ═══════════════════════════════════════════════════════════════════════════


class ComplianceModel(BaseModel):
    """Base model for all compliance entities."""
    
    class Config:
        use_enum_values = True
        populate_by_name = True
        

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ═══════════════════════════════════════════════════════════════════════════
# CONTROL STATUS & COMPLIANCE STATUS
# ═══════════════════════════════════════════════════════════════════════════


class ControlStatus(ComplianceModel):
    """
    Status of a single compliance control.
    
    Controls are individual requirements from frameworks that must be
    implemented and verified.
    """
    control_id: str = Field(description="Unique control identifier (e.g., 'GDPR-15.1')")
    framework: ComplianceFramework
    name: str = Field(description="Human-readable control name")
    description: str = Field(description="Detailed control description")
    
    # Status
    implemented: bool = False
    verified: bool = False
    automated: bool = False
    
    # Evidence
    evidence_required: list[str] = Field(default_factory=list)
    evidence_provided: list[str] = Field(default_factory=list)
    
    # Risk
    risk_if_missing: RiskLevel = RiskLevel.HIGH
    compensating_controls: list[str] = Field(default_factory=list)
    
    # Audit
    last_audit_date: datetime | None = None
    next_audit_date: datetime | None = None
    auditor_notes: str | None = None
    
    # Metadata
    owner: str | None = None
    implementation_date: datetime | None = None
    
    @property
    def status(self) -> str:
        """Get overall status."""
        if self.verified:
            return "verified"
        elif self.implemented:
            return "implemented"
        else:
            return "pending"
    
    @property
    def is_compliant(self) -> bool:
        """Check if control is compliant."""
        return self.implemented and self.verified


class ComplianceStatus(ComplianceModel, TimestampMixin):
    """
    Overall compliance status across all frameworks.
    
    Aggregates control statuses and provides compliance percentages.
    """
    id: str = Field(default_factory=generate_id)
    organization_id: str
    
    # Jurisdictions enabled
    active_jurisdictions: list[Jurisdiction] = Field(default_factory=list)
    active_frameworks: list[ComplianceFramework] = Field(default_factory=list)
    
    # Control counts by framework
    controls_by_framework: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Framework -> {total, implemented, verified, pending}",
    )
    
    # Overall metrics
    total_controls: int = 0
    implemented_controls: int = 0
    verified_controls: int = 0
    automated_controls: int = 0
    
    # Risk metrics
    high_risk_pending: int = 0
    critical_findings: list[str] = Field(default_factory=list)
    
    # Audit status
    last_full_audit: datetime | None = None
    next_scheduled_audit: datetime | None = None
    
    @property
    def compliance_percentage(self) -> float:
        """Calculate overall compliance percentage."""
        if self.total_controls == 0:
            return 0.0
        return (self.verified_controls / self.total_controls) * 100
    
    @property
    def implementation_percentage(self) -> float:
        """Calculate implementation percentage."""
        if self.total_controls == 0:
            return 0.0
        return (self.implemented_controls / self.total_controls) * 100
    
    def get_framework_status(self, framework: ComplianceFramework) -> dict[str, Any]:
        """Get detailed status for a specific framework."""
        return self.controls_by_framework.get(framework.value, {
            "total": 0,
            "implemented": 0,
            "verified": 0,
            "pending": 0,
            "compliance_pct": 0.0,
        })


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOGGING
# ═══════════════════════════════════════════════════════════════════════════


class AuditEvent(ComplianceModel, TimestampMixin):
    """
    Immutable audit log entry.
    
    Captures all compliance-relevant events with cryptographic integrity.
    Per SOC 2 CC7.2, ISO 27001 A.8.15-16, NIST AU family.
    """
    id: str = Field(default_factory=generate_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Event identification
    category: AuditEventCategory
    event_type: str = Field(description="Specific event type within category")
    action: str = Field(description="Action performed (CREATE, READ, UPDATE, DELETE)")
    
    # Actor
    actor_id: str | None = Field(description="User or system performing action")
    actor_type: str = Field(default="user", description="user, system, overlay, api")
    actor_ip: str | None = None
    actor_user_agent: str | None = None
    
    # Target
    entity_type: str = Field(default="", description="Type of entity affected")
    entity_id: str | None = Field(default=None, description="ID of affected entity")
    
    # Context
    correlation_id: str = Field(default_factory=generate_id)
    session_id: str | None = None
    request_id: str | None = None
    
    # Change details
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    changes: dict[str, Any] | None = None
    
    # Outcome
    success: bool = True
    error_code: str | None = None
    error_message: str | None = None
    
    # Risk & Compliance
    risk_level: RiskLevel = RiskLevel.INFO
    compliance_flags: list[str] = Field(default_factory=list)
    data_classification: DataClassification | None = None
    
    # Integrity
    hash: str | None = Field(default=None, description="SHA-256 hash for integrity")
    previous_hash: str | None = Field(default=None, description="Hash of previous event (chain)")
    
    # Retention
    retention_until: datetime | None = None
    
    @model_validator(mode="after")
    def set_retention(self) -> "AuditEvent":
        """Set default retention based on category."""
        if not self.retention_until:
            retention_years = {
                AuditEventCategory.AUTHENTICATION: 7,    # SOX
                AuditEventCategory.AUTHORIZATION: 6,     # HIPAA
                AuditEventCategory.DATA_ACCESS: 6,
                AuditEventCategory.DATA_MODIFICATION: 6,
                AuditEventCategory.PRIVACY: 7,
                AuditEventCategory.AI_DECISION: 6,
                AuditEventCategory.SECURITY: 3,
                AuditEventCategory.SYSTEM: 1,
            }
            years = retention_years.get(self.category, 3)
            self.retention_until = datetime.now(UTC) + timedelta(days=years * 365)
        return self


class AuditChain(ComplianceModel):
    """
    Chain of audit events for immutability verification.
    
    Provides cryptographic linking of audit events.
    """
    id: str = Field(default_factory=generate_id)
    start_hash: str
    end_hash: str
    event_count: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified_at: datetime | None = None
    is_valid: bool | None = None


# ═══════════════════════════════════════════════════════════════════════════
# DATA SUBJECT REQUESTS (DSAR)
# ═══════════════════════════════════════════════════════════════════════════


class DSARVerification(ComplianceModel):
    """Identity verification for DSAR."""
    method: str = Field(description="Verification method used")
    verified_at: datetime
    verified_by: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(ge=0.0, le=1.0)


class DataSubjectRequest(ComplianceModel, TimestampMixin):
    """
    Data Subject Access Request (DSAR).
    
    Handles all types of data subject rights per GDPR Articles 15-22,
    CCPA §1798.100-135, LGPD Articles 17-18, and equivalents.
    """
    id: str = Field(default_factory=generate_id)
    
    # Request identification
    request_type: DSARType
    jurisdiction: Jurisdiction
    applicable_frameworks: list[ComplianceFramework] = Field(default_factory=list)
    
    # Data subject
    subject_id: str | None = Field(default=None, description="Internal user ID if known")
    subject_email: str = Field(default="", description="Email for correspondence")
    subject_name: str | None = None
    
    # Verification
    verified: bool = False
    verification: DSARVerification | None = None
    
    # Request details
    request_text: str = Field(default="", description="Original request text")
    specific_data_categories: list[str] = Field(default_factory=list)
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    
    # Processing
    status: str = Field(default="received")  # received, verified, processing, completed, rejected
    assigned_to: str | None = None
    
    # Deadlines
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deadline: datetime | None = None
    extended: bool = False
    extension_reason: str | None = None
    
    # Response
    response_sent_at: datetime | None = None
    response_method: str | None = None  # email, portal, mail
    data_exported: bool = False
    export_format: str | None = None  # JSON, CSV, PDF
    export_location: str | None = None
    
    # For erasure requests
    erasure_completed: bool = False
    erasure_exceptions: list[str] = Field(default_factory=list)
    third_party_notifications_sent: bool = False
    
    # Audit
    processing_log: list[dict[str, Any]] = Field(default_factory=list)
    
    @model_validator(mode="after")
    def calculate_deadline(self) -> "DataSubjectRequest":
        """Calculate deadline based on jurisdiction and type."""
        if not self.deadline:
            base_days = min(
                self.jurisdiction.dsar_deadline_days,
                self.request_type.baseline_deadline_days,
            )
            # Brazil LGPD is strictest at 15 days
            if Jurisdiction.BRAZIL in [self.jurisdiction]:
                base_days = 15
            self.deadline = self.received_at + timedelta(days=base_days)
        return self
    
    @property
    def is_overdue(self) -> bool:
        """Check if request is past deadline."""
        if self.status == "completed":
            return False
        return self.deadline and datetime.now(UTC) > self.deadline
    
    @property
    def days_until_deadline(self) -> int:
        """Get days remaining until deadline."""
        if not self.deadline:
            return 0
        delta = self.deadline - datetime.now(UTC)
        return max(0, delta.days)
    
    def add_processing_note(self, note: str, actor: str) -> None:
        """Add a processing log entry."""
        self.processing_log.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "actor": actor,
            "note": note,
        })
        self.updated_at = datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════
# CONSENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


class ConsentRecord(ComplianceModel, TimestampMixin):
    """
    Record of user consent.
    
    Per GDPR Article 7, ePrivacy Directive, IAB TCF 2.2.
    Maintains full audit trail of consent lifecycle.
    """
    id: str = Field(default_factory=generate_id)
    
    # Subject
    user_id: str
    
    # Consent details
    consent_type: ConsentType
    purpose: str = Field(description="Specific purpose for consent")
    
    # Status
    granted: bool
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    
    # Collection context
    collected_via: str = Field(description="How consent was collected")
    ip_address: str | None = None
    user_agent: str | None = None
    language: str = "en"
    
    # Consent string (IAB TCF 2.2 compatibility)
    tcf_string: str | None = None
    gpp_string: str | None = None  # Global Privacy Platform
    
    # Proof
    consent_text_version: str = Field(description="Version of consent text shown")
    consent_text_hash: str | None = None
    screenshot_url: str | None = None
    
    # Legal basis (GDPR)
    legal_basis: str = Field(
        default="consent",
        description="consent, contract, legal_obligation, vital_interests, public_task, legitimate_interests",
    )
    
    # Third-party sharing
    third_parties: list[str] = Field(default_factory=list)
    third_party_consent_given: bool = False
    
    # Cross-border
    cross_border_transfer: bool = False
    transfer_safeguards: list[str] = Field(default_factory=list)  # SCCs, BCRs, etc.
    
    # Parent consent (COPPA)
    parent_consent_required: bool = False
    parent_email: str | None = None
    parent_consent_verified: bool = False
    parent_verification_method: str | None = None
    
    # Expiry
    expires_at: datetime | None = None
    auto_renew: bool = False
    
    @property
    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        if not self.granted:
            return False
        if self.withdrawn_at:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True
    
    def withdraw(self) -> None:
        """Withdraw consent."""
        self.granted = False
        self.withdrawn_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


# ═══════════════════════════════════════════════════════════════════════════
# BREACH NOTIFICATION
# ═══════════════════════════════════════════════════════════════════════════


class AffectedIndividual(ComplianceModel):
    """Individual affected by a breach."""
    user_id: str | None = None
    email: str
    name: str | None = None
    data_types_exposed: list[str]
    jurisdiction: Jurisdiction
    notified: bool = False
    notified_at: datetime | None = None
    notification_method: str | None = None


class RegulatoryNotification(ComplianceModel):
    """Record of notification to regulatory authority."""
    authority: str = Field(description="Name of regulatory authority")
    jurisdiction: Jurisdiction
    required: bool = True
    notified: bool = False
    notified_at: datetime | None = None
    reference_number: str | None = None
    deadline: datetime | None = None
    acknowledgment_received: bool = False


class BreachNotification(ComplianceModel, TimestampMixin):
    """
    Data breach notification and management.
    
    Per GDPR Article 33-34, CCPA §1798.82, HIPAA Breach Notification Rule,
    and equivalent regulations across 25+ jurisdictions.
    """
    id: str = Field(default_factory=generate_id)
    
    # Discovery
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    discovered_by: str
    discovery_method: str
    
    # Classification
    severity: BreachSeverity
    breach_type: str = Field(description="unauthorized_access, theft, loss, disclosure, etc.")
    
    # Affected data
    data_categories: list[DataClassification]
    data_elements: list[str] = Field(description="Specific data elements exposed")
    record_count: int = 0
    
    # Affected individuals
    affected_individuals: list[AffectedIndividual] = Field(default_factory=list)
    affected_count: int = 0
    
    # Jurisdictions affected
    jurisdictions: list[Jurisdiction]
    
    # Root cause
    root_cause: str | None = None
    vulnerability_id: str | None = None
    attack_vector: str | None = None
    
    # Containment
    contained: bool = False
    contained_at: datetime | None = None
    containment_actions: list[str] = Field(default_factory=list)
    
    # Notification status
    authority_notifications: list[RegulatoryNotification] = Field(default_factory=list)
    individual_notification_required: bool = False
    individual_notification_sent: bool = False
    individual_notification_date: datetime | None = None
    
    # Deadlines (calculated per jurisdiction)
    notification_deadlines: dict[str, datetime] = Field(default_factory=dict)
    
    # Documentation
    incident_report_url: str | None = None
    forensic_report_url: str | None = None
    
    # Remediation
    remediation_plan: list[str] = Field(default_factory=list)
    remediation_completed: bool = False
    remediation_verified_by: str | None = None
    
    # Legal
    legal_counsel_engaged: bool = False
    law_enforcement_notified: bool = False
    insurance_claim_filed: bool = False
    
    @model_validator(mode="after")
    def calculate_deadlines(self) -> "BreachNotification":
        """Calculate notification deadlines per jurisdiction."""
        for jurisdiction in self.jurisdictions:
            hours = jurisdiction.breach_notification_hours
            deadline = self.discovered_at + timedelta(hours=hours)
            self.notification_deadlines[jurisdiction.value] = deadline
        return self
    
    @property
    def most_urgent_deadline(self) -> datetime | None:
        """Get the earliest notification deadline."""
        if not self.notification_deadlines:
            return None
        return min(self.notification_deadlines.values())
    
    @property
    def is_overdue(self) -> bool:
        """Check if any notification is overdue."""
        if self.authority_notifications:
            for notif in self.authority_notifications:
                if notif.required and not notif.notified and notif.deadline:
                    if datetime.now(UTC) > notif.deadline:
                        return True
        return False


# ═══════════════════════════════════════════════════════════════════════════
# AI GOVERNANCE MODELS
# ═══════════════════════════════════════════════════════════════════════════


class AISystemRegistration(ComplianceModel, TimestampMixin):
    """
    AI system registration for EU AI Act compliance.
    
    Per EU AI Act Article 60 (EU database for high-risk AI systems).
    """
    id: str = Field(default_factory=generate_id)
    
    # System identification
    system_name: str
    system_version: str
    provider: str
    
    # Classification
    risk_classification: AIRiskClassification
    intended_purpose: str
    use_cases: list[str]
    
    # Technical details
    model_type: str = Field(description="LLM, ML classifier, etc.")
    training_data_description: str | None = None
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    
    # Annex IV documentation (for high-risk)
    technical_documentation_url: str | None = None
    
    # Conformity assessment
    conformity_assessment_completed: bool = False
    conformity_assessment_date: datetime | None = None
    notified_body: str | None = None
    certificate_number: str | None = None
    
    # EU database registration
    eu_database_registered: bool = False
    eu_registration_number: str | None = None
    
    # Human oversight
    human_oversight_measures: list[str] = Field(default_factory=list)
    override_capability: bool = True
    
    # Monitoring
    performance_metrics: dict[str, Any] = Field(default_factory=dict)
    bias_audit_completed: bool = False
    bias_audit_date: datetime | None = None
    bias_audit_results: dict[str, Any] | None = None


class AIDecisionLog(ComplianceModel):
    """
    Log of AI-made decisions for explainability.
    
    Per GDPR Article 22, EU AI Act transparency requirements.
    """
    id: str = Field(default_factory=generate_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # System
    ai_system_id: str
    model_version: str
    
    # Decision
    decision_type: str
    decision_outcome: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    
    # Affected party
    subject_id: str | None = None
    has_legal_effect: bool = False
    has_significant_effect: bool = False
    
    # Explainability
    input_summary: dict[str, Any]
    reasoning_chain: list[str] = Field(default_factory=list)
    key_factors: list[dict[str, Any]] = Field(default_factory=list)
    alternative_outcomes: list[str] = Field(default_factory=list)
    
    # Human oversight
    human_reviewed: bool = False
    human_reviewer: str | None = None
    human_override: bool = False
    override_reason: str | None = None
    
    # Contestation
    contested: bool = False
    contestation_date: datetime | None = None
    contestation_outcome: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# COMPLIANCE REPORTING
# ═══════════════════════════════════════════════════════════════════════════


class ComplianceReport(ComplianceModel, TimestampMixin):
    """
    Compliance assessment report.
    
    Generated periodically or on-demand for audit purposes.
    """
    id: str = Field(default_factory=generate_id)
    
    # Report metadata
    report_type: str = Field(default="full", description="full, framework, jurisdiction, gap")
    report_period_start: datetime = Field(default_factory=lambda: datetime.now(UTC))
    report_period_end: datetime = Field(default_factory=lambda: datetime.now(UTC))
    generated_by: str = Field(default="system")
    
    # Scope
    frameworks_assessed: list[ComplianceFramework] = Field(default_factory=list)
    jurisdictions_assessed: list[Jurisdiction] = Field(default_factory=list)
    
    # Findings
    overall_compliance_score: float = Field(default=0.0, ge=0.0, le=100.0)
    status: ComplianceStatus | None = None
    
    # Controls
    total_controls_assessed: int = 0
    controls_compliant: int = 0
    controls_non_compliant: int = 0
    controls_not_applicable: int = 0
    
    # Gaps
    critical_gaps: list[dict[str, Any]] = Field(default_factory=list)
    high_risk_gaps: list[dict[str, Any]] = Field(default_factory=list)
    medium_risk_gaps: list[dict[str, Any]] = Field(default_factory=list)
    
    # Recommendations
    remediation_items: list[dict[str, Any]] = Field(default_factory=list)
    estimated_remediation_effort: str | None = None
    
    # Privacy metrics
    dsar_metrics: dict[str, Any] = Field(default_factory=dict)
    consent_metrics: dict[str, Any] = Field(default_factory=dict)
    breach_metrics: dict[str, Any] = Field(default_factory=dict)
    
    # AI governance metrics
    ai_system_count: int = 0
    high_risk_ai_systems: int = 0
    ai_decisions_logged: int = 0
    ai_decisions_contested: int = 0
    
    # Attachments
    evidence_urls: list[str] = Field(default_factory=list)
    
    # Sign-off
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    
    @property
    def compliance_percentage(self) -> float:
        """Calculate compliance percentage."""
        applicable = self.total_controls_assessed - self.controls_not_applicable
        if applicable == 0:
            return 100.0
        return (self.controls_compliant / applicable) * 100
