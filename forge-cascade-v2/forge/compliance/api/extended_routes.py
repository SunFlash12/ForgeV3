"""
Forge Compliance Framework - Extended API Routes

Additional REST API endpoints for:
- Consent Management
- Security Controls
- AI Governance
- Industry Compliance
- Reporting
- Accessibility
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from forge.compliance.accessibility import (
    AccessibilityStandard,
    IssueImpact,
    WCAGLevel,
    get_accessibility_service,
)
from forge.compliance.ai_governance import get_ai_governance_service
from forge.compliance.core.enums import (
    BreachSeverity,
    ComplianceFramework,
    DataClassification,
    Jurisdiction,
)

# Import services
from forge.compliance.privacy import ConsentPurpose, get_consent_service
from forge.compliance.reporting import ReportFormat, ReportType, get_compliance_reporting_service
from forge.compliance.security import (
    BreachType,
    MFAMethod,
    NotificationRecipient,
    Permission,
    ResourceType,
    get_access_control_service,
    get_authentication_service,
    get_breach_notification_service,
)

extended_router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# CONSENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


class ConsentCollectionRequest(BaseModel):
    """Request to collect consent."""

    user_id: str
    user_email: str = ""
    purposes: dict[str, bool]  # purpose_name -> granted
    collection_method: str = "explicit_opt_in"
    jurisdiction: str = "global"
    consent_text_version: str = "1.0"
    tcf_string: str = ""


class GPCSignalRequest(BaseModel):
    """GPC signal processing request."""

    user_id: str
    gpc_enabled: bool


class ConsentCheckRequest(BaseModel):
    """Check consent for a specific purpose."""

    user_id: str
    purpose: str


@extended_router.post("/consent/collect")
async def collect_consent(request: ConsentCollectionRequest):
    """Collect consent from user with granular purposes."""
    service = get_consent_service()

    # Convert string purposes to enum
    purposes = {}
    for purpose_str, granted in request.purposes.items():
        try:
            purpose = ConsentPurpose(purpose_str)
            purposes[purpose] = granted
        except ValueError:
            pass  # Skip invalid purposes

    try:
        jurisdiction = Jurisdiction(request.jurisdiction)
    except ValueError:
        jurisdiction = Jurisdiction.GLOBAL

    from forge.compliance.privacy.consent_service import ConsentCollectionMethod

    try:
        method = ConsentCollectionMethod(request.collection_method)
    except ValueError:
        method = ConsentCollectionMethod.EXPLICIT_OPT_IN

    record = await service.collect_consent(
        user_id=request.user_id,
        purposes=purposes,
        collection_method=method,
        jurisdiction=jurisdiction,
        user_email=request.user_email,
        consent_text_version=request.consent_text_version,
        tcf_string=request.tcf_string,
    )

    return {
        "record_id": record.record_id,
        "user_id": record.user_id,
        "version": record.version,
        "consent_hash": record.consent_hash,
        "created_at": record.created_at.isoformat(),
    }


@extended_router.post("/consent/gpc")
async def process_gpc_signal(request: GPCSignalRequest):
    """Process Global Privacy Control signal."""
    service = get_consent_service()

    await service.process_gpc_signal(
        user_id=request.user_id,
        gpc_enabled=request.gpc_enabled,
    )

    return {
        "user_id": request.user_id,
        "gpc_processed": True,
        "gpc_enabled": request.gpc_enabled,
        "affected_purposes": [
            "data_sale",
            "third_party_sharing",
            "cross_context_advertising",
        ]
        if request.gpc_enabled
        else [],
    }


@extended_router.get("/consent/{user_id}")
async def get_user_consent(user_id: str):
    """Get user's consent preferences."""
    service = get_consent_service()
    consents = await service.get_user_consents(user_id)

    if not consents:
        raise HTTPException(status_code=404, detail="No consent record found")

    return consents


@extended_router.post("/consent/{user_id}/check")
async def check_consent(user_id: str, request: ConsentCheckRequest):
    """Check if user has consented to a specific purpose."""
    service = get_consent_service()

    try:
        purpose = ConsentPurpose(request.purpose)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid purpose: {request.purpose}")

    has_consent, reason = await service.check_consent(user_id, purpose)

    return {
        "user_id": user_id,
        "purpose": request.purpose,
        "has_consent": has_consent,
        "reason": reason,
    }


@extended_router.post("/consent/{user_id}/withdraw")
async def withdraw_consent(
    user_id: str,
    purposes: list[str] = Body(None),
    withdraw_all: bool = Body(False),
):
    """Withdraw consent for specified purposes."""
    service = get_consent_service()

    purpose_enums = []
    if purposes:
        for p in purposes:
            try:
                purpose_enums.append(ConsentPurpose(p))
            except ValueError:
                pass

    record = await service.withdraw_consent(
        user_id=user_id,
        purposes=purpose_enums if purpose_enums else None,
        withdraw_all=withdraw_all,
    )

    if not record:
        raise HTTPException(status_code=404, detail="No consent record found")

    return {"user_id": user_id, "consent_withdrawn": True}


@extended_router.get("/consent/{user_id}/receipt")
async def get_consent_receipt(user_id: str):
    """Generate consent receipt for user."""
    service = get_consent_service()
    receipt = await service.generate_receipt(user_id)

    if not receipt:
        raise HTTPException(status_code=404, detail="No consent record found")

    return {
        "receipt_id": receipt.receipt_id,
        "data_controller": receipt.data_controller,
        "purposes_granted": receipt.purposes_granted,
        "purposes_denied": receipt.purposes_denied,
        "collection_timestamp": receipt.collection_timestamp.isoformat(),
        "consent_hash": receipt.consent_hash,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY CONTROLS
# ═══════════════════════════════════════════════════════════════════════════


class AccessCheckRequest(BaseModel):
    """Access control check request."""

    user_id: str
    permission: str
    resource_type: str
    resource_id: str = ""
    data_classification: str = ""


class RoleAssignmentRequest(BaseModel):
    """Role assignment request."""

    user_id: str
    role_id: str
    assigned_by: str


class MFAChallengeRequest(BaseModel):
    """MFA challenge creation request."""

    user_id: str
    method: str = "totp"


class MFAVerifyRequest(BaseModel):
    """MFA verification request."""

    challenge_id: str
    code: str


@extended_router.post("/security/access/check")
async def check_access(request: AccessCheckRequest):
    """Check if user has access to a resource."""
    service = get_access_control_service()

    try:
        permission = Permission(request.permission)
        resource_type = ResourceType(request.resource_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    classification = None
    if request.data_classification:
        try:
            classification = DataClassification(request.data_classification)
        except ValueError:
            pass

    decision = service.check_access(
        user_id=request.user_id,
        permission=permission,
        resource_type=resource_type,
        resource_id=request.resource_id or None,
        data_classification=classification,
    )

    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "requires_mfa": decision.requires_mfa,
        "audit_required": decision.audit_required,
    }


@extended_router.post("/security/roles/assign")
async def assign_role(request: RoleAssignmentRequest):
    """Assign a role to a user."""
    service = get_access_control_service()

    success = service.assign_role(
        user_id=request.user_id,
        role_id=request.role_id,
        assigned_by=request.assigned_by,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Role assignment failed")

    return {
        "user_id": request.user_id,
        "role_id": request.role_id,
        "assigned": True,
    }


@extended_router.get("/security/roles/{user_id}")
async def get_user_roles(user_id: str):
    """Get roles assigned to a user."""
    service = get_access_control_service()
    roles = service.get_user_roles(user_id)

    return {
        "user_id": user_id,
        "roles": [
            {
                "role_id": r.role_id,
                "name": r.name,
                "is_privileged": r.is_privileged,
                "permissions": [p.value for p in r.permissions],
            }
            for r in roles
        ],
    }


@extended_router.post("/security/mfa/challenge")
async def create_mfa_challenge(request: MFAChallengeRequest):
    """Create an MFA challenge for a user."""
    service = get_authentication_service()

    try:
        method = MFAMethod(request.method)
    except ValueError:
        method = MFAMethod.TOTP

    challenge = service.create_mfa_challenge(
        user_id=request.user_id,
        method=method,
    )

    return {
        "challenge_id": challenge.challenge_id,
        "method": challenge.method.value,
        "expires_at": challenge.expires_at.isoformat(),
    }


@extended_router.post("/security/mfa/verify")
async def verify_mfa(request: MFAVerifyRequest):
    """Verify MFA response."""
    service = get_authentication_service()

    success = service.verify_mfa(
        challenge_id=request.challenge_id,
        code=request.code,
    )

    return {"verified": success}


# ═══════════════════════════════════════════════════════════════════════════
# BREACH NOTIFICATION
# ═══════════════════════════════════════════════════════════════════════════


class BreachReportRequest(BaseModel):
    """Breach report request."""

    discovered_by: str
    discovery_method: str
    breach_type: str
    severity: str
    data_categories: list[str]
    data_elements: list[str]
    record_count: int
    affected_jurisdictions: list[str]
    description: str = ""


class NotificationCreateRequest(BaseModel):
    """Notification creation request."""

    breach_id: str
    recipient_type: str
    jurisdiction: str
    recipient_name: str = ""
    recipient_contact: str = ""


@extended_router.post("/breaches/report")
async def report_breach(request: BreachReportRequest):
    """Report a new security breach."""
    service = get_breach_notification_service()

    try:
        breach_type = BreachType(request.breach_type)
        severity = BreachSeverity(request.severity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    data_categories = []
    for cat in request.data_categories:
        try:
            data_categories.append(DataClassification(cat))
        except ValueError:
            pass

    jurisdictions = []
    for j in request.affected_jurisdictions:
        try:
            jurisdictions.append(Jurisdiction(j))
        except ValueError:
            pass

    incident = await service.report_breach(
        discovered_by=request.discovered_by,
        discovery_method=request.discovery_method,
        breach_type=breach_type,
        severity=severity,
        data_categories=data_categories,
        data_elements=request.data_elements,
        record_count=request.record_count,
        affected_jurisdictions=jurisdictions,
        description=request.description,
    )

    return {
        "breach_id": incident.breach_id,
        "status": incident.status.value,
        "requires_notification": incident.requires_notification,
        "most_urgent_deadline": incident.most_urgent_deadline.isoformat()
        if incident.most_urgent_deadline
        else None,
        "notification_deadlines": [
            {
                "jurisdiction": d.jurisdiction.value,
                "authority_deadline": d.authority_deadline.isoformat(),
                "authority_name": d.authority_name,
            }
            for d in incident.notification_deadlines
        ],
    }


@extended_router.get("/breaches/{breach_id}")
async def get_breach(breach_id: str):
    """Get breach incident details."""
    service = get_breach_notification_service()
    summary = await service.get_incident_summary(breach_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Breach not found")

    return summary


@extended_router.post("/breaches/{breach_id}/notifications")
async def create_notification(breach_id: str, request: NotificationCreateRequest):
    """Create a notification for a breach."""
    service = get_breach_notification_service()

    try:
        recipient_type = NotificationRecipient(request.recipient_type)
        jurisdiction = Jurisdiction(request.jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    notification = await service.create_notification(
        breach_id=breach_id,
        recipient_type=recipient_type,
        jurisdiction=jurisdiction,
        recipient_name=request.recipient_name,
        recipient_contact=request.recipient_contact,
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Breach not found")

    return {
        "notification_id": notification.notification_id,
        "status": notification.status.value,
        "recipient_type": notification.recipient_type.value,
    }


@extended_router.get("/breaches/overdue/list")
async def get_overdue_notifications():
    """Get list of overdue breach notifications."""
    service = get_breach_notification_service()
    overdue = await service.get_overdue_notifications()
    return {"overdue_notifications": overdue}


# ═══════════════════════════════════════════════════════════════════════════
# AI GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════


class AISystemRegisterRequest(BaseModel):
    """AI system registration request."""

    system_name: str
    system_version: str
    provider: str
    intended_purpose: str
    use_cases: list[str]
    model_type: str
    human_oversight_measures: list[str]
    training_data_description: str = ""


class AIDecisionLogRequest(BaseModel):
    """AI decision logging request."""

    ai_system_id: str
    model_version: str
    decision_type: str
    decision_outcome: str
    confidence_score: float
    input_summary: dict[str, Any]
    reasoning_chain: list[str]
    key_factors: list[dict[str, Any]]
    subject_id: str = ""
    has_legal_effect: bool = False
    has_significant_effect: bool = False


class HumanReviewRequest(BaseModel):
    """Human review request."""

    decision_id: str
    reviewer_id: str
    override: bool = False
    override_reason: str = ""
    new_outcome: str = ""


@extended_router.post("/ai/systems/register")
async def register_ai_system(request: AISystemRegisterRequest):
    """Register an AI system in the inventory."""
    service = get_ai_governance_service()

    registration = await service.register_system(
        system_name=request.system_name,
        system_version=request.system_version,
        provider=request.provider,
        intended_purpose=request.intended_purpose,
        use_cases=request.use_cases,
        model_type=request.model_type,
        human_oversight_measures=request.human_oversight_measures,
        training_data_description=request.training_data_description,
    )

    return {
        "system_id": registration.id,
        "system_name": registration.system_name,
        "risk_classification": registration.risk_classification.value,
        "conformity_required": registration.risk_classification.requires_conformity_assessment,
    }


@extended_router.post("/ai/decisions/log")
async def log_ai_decision(request: AIDecisionLogRequest):
    """Log an AI decision for transparency."""
    service = get_ai_governance_service()

    decision = await service.log_decision(
        ai_system_id=request.ai_system_id,
        model_version=request.model_version,
        decision_type=request.decision_type,
        decision_outcome=request.decision_outcome,
        confidence_score=request.confidence_score,
        input_summary=request.input_summary,
        reasoning_chain=request.reasoning_chain,
        key_factors=request.key_factors,
        subject_id=request.subject_id or None,
        has_legal_effect=request.has_legal_effect,
        has_significant_effect=request.has_significant_effect,
    )

    return {
        "decision_id": decision.id,
        "human_review_requested": decision.human_review_requested,
        "timestamp": decision.timestamp.isoformat(),
    }


@extended_router.post("/ai/decisions/review")
async def complete_human_review(request: HumanReviewRequest):
    """Complete human review of an AI decision."""
    service = get_ai_governance_service()

    decision = await service.complete_human_review(
        decision_id=request.decision_id,
        reviewer_id=request.reviewer_id,
        override=request.override,
        override_reason=request.override_reason or None,
        new_outcome=request.new_outcome or None,
    )

    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    return {
        "decision_id": decision.id,
        "human_reviewed": decision.human_reviewed,
        "human_override": decision.human_override,
    }


@extended_router.get("/ai/decisions/{decision_id}/explanation")
async def get_decision_explanation(
    decision_id: str,
    audience: str = Query("end_user", description="Audience: end_user, technical, regulatory"),
):
    """Get explanation for an AI decision."""
    service = get_ai_governance_service()

    explanation = await service.generate_explanation(
        decision_id=decision_id,
        audience=audience,
    )

    return explanation


# ═══════════════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════════════


class ReportGenerateRequest(BaseModel):
    """Report generation request."""

    report_type: str = "executive_summary"
    frameworks: list[str] = []
    jurisdictions: list[str] = []
    generated_by: str = "system"


@extended_router.post("/reports/generate")
async def generate_report(request: ReportGenerateRequest):
    """Generate a compliance report."""
    service = get_compliance_reporting_service()

    try:
        report_type = ReportType(request.report_type)
    except ValueError:
        report_type = ReportType.EXECUTIVE_SUMMARY

    frameworks = []
    for f in request.frameworks:
        try:
            frameworks.append(ComplianceFramework(f))
        except ValueError:
            pass

    jurisdictions = []
    for j in request.jurisdictions:
        try:
            jurisdictions.append(Jurisdiction(j))
        except ValueError:
            pass

    report = await service.generate_report(
        report_type=report_type,
        frameworks=frameworks or None,
        jurisdictions=jurisdictions or None,
        generated_by=request.generated_by,
    )

    return {
        "report_id": report.report_id,
        "title": report.title,
        "overall_score": report.overall_score,
        "total_controls": report.total_controls,
        "compliant_controls": report.compliant_controls,
        "gaps": {
            "critical": report.gaps_critical,
            "high": report.gaps_high,
            "medium": report.gaps_medium,
            "low": report.gaps_low,
        },
        "generated_at": report.generated_at.isoformat(),
    }


@extended_router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = Query("json", description="Export format: json, markdown, html"),
):
    """Export a report in specified format."""
    service = get_compliance_reporting_service()

    try:
        report_format = ReportFormat(format)
    except ValueError:
        report_format = ReportFormat.JSON

    try:
        content = await service.export_report(report_id, report_format)
        return {"content": content.decode("utf-8")}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# ACCESSIBILITY
# ═══════════════════════════════════════════════════════════════════════════


class AccessibilityAuditRequest(BaseModel):
    """Accessibility audit creation request."""

    audit_name: str
    target_url: str
    standard: str = "wcag_2_2"
    target_level: str = "AA"
    auditor: str = ""


class AccessibilityIssueRequest(BaseModel):
    """Accessibility issue logging request."""

    audit_id: str
    url: str
    criterion_id: str
    impact: str
    description: str
    remediation: str
    element_selector: str = ""
    component: str = ""


class VPATGenerateRequest(BaseModel):
    """VPAT generation request."""

    product_name: str
    product_version: str
    vendor_name: str
    audit_id: str = ""


@extended_router.post("/accessibility/audits")
async def create_accessibility_audit(request: AccessibilityAuditRequest):
    """Create an accessibility audit."""
    service = get_accessibility_service()

    try:
        standard = AccessibilityStandard(request.standard)
        level = WCAGLevel(request.target_level)
    except ValueError:
        standard = AccessibilityStandard.WCAG_22
        level = WCAGLevel.AA

    audit = await service.create_audit(
        audit_name=request.audit_name,
        target_url=request.target_url,
        standard=standard,
        target_level=level,
        auditor=request.auditor,
    )

    return {
        "audit_id": audit.audit_id,
        "audit_name": audit.audit_name,
        "target_url": audit.target_url,
        "standard": audit.standard.value,
        "target_level": audit.target_level.value,
    }


@extended_router.post("/accessibility/issues")
async def log_accessibility_issue(request: AccessibilityIssueRequest):
    """Log an accessibility issue."""
    service = get_accessibility_service()

    try:
        impact = IssueImpact(request.impact)
    except ValueError:
        impact = IssueImpact.MODERATE

    issue = await service.log_issue(
        audit_id=request.audit_id,
        url=request.url,
        criterion_id=request.criterion_id,
        impact=impact,
        description=request.description,
        remediation=request.remediation,
        element_selector=request.element_selector,
        component=request.component,
    )

    return {
        "issue_id": issue.issue_id,
        "criterion_id": issue.criterion_id,
        "impact": issue.impact.value,
        "status": issue.status,
    }


@extended_router.post("/accessibility/vpat/generate")
async def generate_vpat(request: VPATGenerateRequest):
    """Generate a VPAT document."""
    service = get_accessibility_service()

    vpat = await service.generate_vpat(
        product_name=request.product_name,
        product_version=request.product_version,
        vendor_name=request.vendor_name,
        audit_id=request.audit_id or None,
    )

    return {
        "vpat_id": vpat.vpat_id,
        "product_name": vpat.product_name,
        "report_date": vpat.report_date.isoformat(),
        "entries_count": len(vpat.entries),
    }


@extended_router.get("/accessibility/summary")
async def get_accessibility_summary():
    """Get accessibility compliance summary."""
    service = get_accessibility_service()
    summary = service.get_compliance_summary()
    return summary
