"""
Forge Compliance Framework - API Routes

REST API endpoints for compliance operations including:
- DSAR management
- Consent management
- Breach notification
- AI governance
- Audit logging
- Compliance reporting
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from forge.compliance.core.enums import (
    Jurisdiction,
    ComplianceFramework,
    DataClassification,
    ConsentType,
    DSARType,
    BreachSeverity,
    AIRiskClassification,
    AuditEventCategory,
)
from forge.compliance.core.engine import ComplianceEngine, get_compliance_engine
from forge.compliance.core.models import (
    DataSubjectRequest,
    ConsentRecord,
    BreachNotification,
    AISystemRegistration,
    AIDecisionLog,
    ComplianceReport,
    AuditEvent,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════


class DSARCreateRequest(BaseModel):
    """Request to create a DSAR."""
    request_type: DSARType
    subject_email: str
    request_text: str
    subject_name: str | None = None
    jurisdiction: Jurisdiction | None = None
    specific_data_categories: list[str] | None = None


class DSARProcessRequest(BaseModel):
    """Request to process a DSAR."""
    actor_id: str


class DSARCompleteRequest(BaseModel):
    """Request to complete a DSAR."""
    actor_id: str
    export_location: str | None = None
    export_format: str = "JSON"
    erasure_exceptions: list[str] | None = None


class ConsentCreateRequest(BaseModel):
    """Request to record consent."""
    user_id: str
    consent_type: ConsentType
    purpose: str
    granted: bool
    collected_via: str
    consent_text_version: str
    ip_address: str | None = None
    user_agent: str | None = None
    third_parties: list[str] | None = None
    cross_border_transfer: bool = False
    transfer_safeguards: list[str] | None = None
    tcf_string: str | None = None
    gpp_string: str | None = None


class ConsentWithdrawRequest(BaseModel):
    """Request to withdraw consent."""
    user_id: str
    consent_type: ConsentType


class GPCSignalRequest(BaseModel):
    """Request to process GPC signal."""
    user_id: str
    gpc_enabled: bool


class BreachReportRequest(BaseModel):
    """Request to report a breach."""
    discovered_by: str
    discovery_method: str
    severity: BreachSeverity
    breach_type: str
    data_categories: list[DataClassification]
    data_elements: list[str]
    jurisdictions: list[Jurisdiction]
    record_count: int = 0
    root_cause: str | None = None
    attack_vector: str | None = None


class BreachContainRequest(BaseModel):
    """Request to mark breach as contained."""
    containment_actions: list[str]
    actor_id: str


class AuthorityNotificationRequest(BaseModel):
    """Request to record authority notification."""
    jurisdiction: Jurisdiction
    reference_number: str | None = None
    actor_id: str | None = None


class AISystemRegisterRequest(BaseModel):
    """Request to register an AI system."""
    system_name: str
    system_version: str
    provider: str
    risk_classification: AIRiskClassification
    intended_purpose: str
    use_cases: list[str]
    model_type: str
    human_oversight_measures: list[str]
    training_data_description: str | None = None


class AIDecisionLogRequest(BaseModel):
    """Request to log an AI decision."""
    ai_system_id: str
    model_version: str
    decision_type: str
    decision_outcome: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    input_summary: dict[str, Any]
    reasoning_chain: list[str]
    key_factors: list[dict[str, Any]]
    subject_id: str | None = None
    has_legal_effect: bool = False
    has_significant_effect: bool = False


class HumanReviewRequest(BaseModel):
    """Request to record human review of AI decision."""
    decision_id: str
    reviewer_id: str
    override: bool = False
    override_reason: str | None = None


class ComplianceReportRequest(BaseModel):
    """Request to generate a compliance report."""
    report_type: str = "full"
    start_date: datetime | None = None
    end_date: datetime | None = None
    frameworks: list[ComplianceFramework] | None = None
    jurisdictions: list[Jurisdiction] | None = None
    generated_by: str = "system"


class ControlVerifyRequest(BaseModel):
    """Request to verify a control."""
    control_id: str
    verifier_id: str
    evidence: list[str] | None = None
    notes: str | None = None


# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════


async def get_engine() -> ComplianceEngine:
    """Get the compliance engine."""
    return get_compliance_engine()


# ═══════════════════════════════════════════════════════════════════════════
# DSAR ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/dsars", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_dsar(
    request: DSARCreateRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Create a new Data Subject Access Request.
    
    Automatically calculates deadline based on jurisdiction and request type.
    Uses the strictest deadline (LGPD 15 days) as baseline.
    """
    dsar = await engine.create_dsar(
        request_type=request.request_type,
        subject_email=request.subject_email,
        request_text=request.request_text,
        subject_name=request.subject_name,
        jurisdiction=request.jurisdiction,
        specific_data_categories=request.specific_data_categories,
    )
    
    return {
        "id": dsar.id,
        "request_type": dsar.request_type.value,
        "status": dsar.status,
        "deadline": dsar.deadline.isoformat() if dsar.deadline else None,
        "days_until_deadline": dsar.days_until_deadline,
    }


@router.get("/dsars/{dsar_id}")
async def get_dsar(
    dsar_id: str,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Get DSAR details."""
    dsar = engine._dsars.get(dsar_id)
    if not dsar:
        raise HTTPException(status_code=404, detail="DSAR not found")
    
    return dsar.model_dump()


@router.post("/dsars/{dsar_id}/process")
async def process_dsar(
    dsar_id: str,
    request: DSARProcessRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Mark DSAR as processing."""
    try:
        dsar = await engine.process_dsar(dsar_id, request.actor_id)
        return {"status": dsar.status, "assigned_to": dsar.assigned_to}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dsars/{dsar_id}/complete")
async def complete_dsar(
    dsar_id: str,
    request: DSARCompleteRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Complete a DSAR."""
    try:
        dsar = await engine.complete_dsar(
            dsar_id=dsar_id,
            actor_id=request.actor_id,
            export_location=request.export_location,
            export_format=request.export_format,
            erasure_exceptions=request.erasure_exceptions,
        )
        return {"status": dsar.status, "response_sent_at": dsar.response_sent_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/dsars")
async def list_dsars(
    status: str | None = Query(None),
    overdue_only: bool = Query(False),
    engine: ComplianceEngine = Depends(get_engine),
):
    """List DSARs with optional filters."""
    dsars = list(engine._dsars.values())
    
    if status:
        dsars = [d for d in dsars if d.status == status]
    
    if overdue_only:
        dsars = [d for d in dsars if d.is_overdue]
    
    return {
        "total": len(dsars),
        "dsars": [
            {
                "id": d.id,
                "request_type": d.request_type.value,
                "status": d.status,
                "subject_email": d.subject_email,
                "deadline": d.deadline.isoformat() if d.deadline else None,
                "is_overdue": d.is_overdue,
                "days_until_deadline": d.days_until_deadline,
            }
            for d in dsars
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# CONSENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/consents", response_model=dict, status_code=status.HTTP_201_CREATED)
async def record_consent(
    request: ConsentCreateRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Record a consent decision.
    
    Maintains full audit trail per GDPR Article 7.
    """
    consent = await engine.record_consent(
        user_id=request.user_id,
        consent_type=request.consent_type,
        purpose=request.purpose,
        granted=request.granted,
        collected_via=request.collected_via,
        consent_text_version=request.consent_text_version,
        ip_address=request.ip_address,
        user_agent=request.user_agent,
        third_parties=request.third_parties,
        cross_border_transfer=request.cross_border_transfer,
        transfer_safeguards=request.transfer_safeguards,
        tcf_string=request.tcf_string,
        gpp_string=request.gpp_string,
    )
    
    return {
        "id": consent.id,
        "consent_type": consent.consent_type.value,
        "granted": consent.granted,
        "is_valid": consent.is_valid,
    }


@router.post("/consents/withdraw")
async def withdraw_consent(
    request: ConsentWithdrawRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Withdraw consent."""
    consent = await engine.withdraw_consent(
        user_id=request.user_id,
        consent_type=request.consent_type,
    )
    
    if not consent:
        raise HTTPException(
            status_code=404,
            detail="Active consent not found for this type",
        )
    
    return {
        "id": consent.id,
        "consent_type": consent.consent_type.value,
        "withdrawn_at": consent.withdrawn_at.isoformat(),
    }


@router.post("/consents/gpc")
async def process_gpc_signal(
    request: GPCSignalRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Process Global Privacy Control signal.
    
    Per CCPA, GPC must be treated as opt-out of sale/sharing.
    """
    withdrawn = await engine.process_gpc_signal(
        user_id=request.user_id,
        gpc_enabled=request.gpc_enabled,
    )
    
    return {
        "gpc_enabled": request.gpc_enabled,
        "consents_withdrawn": len(withdrawn),
        "withdrawn_types": [c.consent_type.value for c in withdrawn],
    }


@router.get("/consents/{user_id}")
async def get_user_consents(
    user_id: str,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Get all consent records for a user."""
    consents = await engine.get_user_consents(user_id)
    
    return {
        "user_id": user_id,
        "total": len(consents),
        "consents": [
            {
                "id": c.id,
                "consent_type": c.consent_type.value,
                "purpose": c.purpose,
                "granted": c.granted,
                "is_valid": c.is_valid,
                "granted_at": c.granted_at.isoformat() if c.granted_at else None,
                "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            }
            for c in consents
        ],
    }


@router.get("/consents/{user_id}/check/{consent_type}")
async def check_consent(
    user_id: str,
    consent_type: ConsentType,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Check if user has valid consent for a specific type."""
    has_consent = await engine.check_consent(user_id, consent_type)
    return {"has_consent": has_consent}


# ═══════════════════════════════════════════════════════════════════════════
# BREACH NOTIFICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/breaches", response_model=dict, status_code=status.HTTP_201_CREATED)
async def report_breach(
    request: BreachReportRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Report a data breach.
    
    Automatically calculates notification deadlines per jurisdiction.
    """
    breach = await engine.report_breach(
        discovered_by=request.discovered_by,
        discovery_method=request.discovery_method,
        severity=request.severity,
        breach_type=request.breach_type,
        data_categories=request.data_categories,
        data_elements=request.data_elements,
        jurisdictions=request.jurisdictions,
        record_count=request.record_count,
        root_cause=request.root_cause,
        attack_vector=request.attack_vector,
    )
    
    return {
        "id": breach.id,
        "severity": breach.severity.value,
        "record_count": breach.record_count,
        "most_urgent_deadline": breach.most_urgent_deadline.isoformat() if breach.most_urgent_deadline else None,
        "notification_deadlines": {
            k: v.isoformat() for k, v in breach.notification_deadlines.items()
        },
        "authority_notifications_required": len(breach.authority_notifications),
    }


@router.post("/breaches/{breach_id}/contain")
async def contain_breach(
    breach_id: str,
    request: BreachContainRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Mark breach as contained."""
    try:
        breach = await engine.mark_breach_contained(
            breach_id=breach_id,
            containment_actions=request.containment_actions,
            actor_id=request.actor_id,
        )
        return {
            "contained": breach.contained,
            "contained_at": breach.contained_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/breaches/{breach_id}/notify-authority")
async def notify_authority(
    breach_id: str,
    request: AuthorityNotificationRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Record that authority has been notified."""
    try:
        breach = await engine.record_authority_notification(
            breach_id=breach_id,
            jurisdiction=request.jurisdiction,
            reference_number=request.reference_number,
            actor_id=request.actor_id,
        )
        
        notif = next(
            (n for n in breach.authority_notifications if n.jurisdiction == request.jurisdiction),
            None,
        )
        
        return {
            "notified": notif.notified if notif else False,
            "reference_number": notif.reference_number if notif else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/breaches/{breach_id}")
async def get_breach(
    breach_id: str,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Get breach details."""
    breach = engine._breaches.get(breach_id)
    if not breach:
        raise HTTPException(status_code=404, detail="Breach not found")
    
    return breach.model_dump()


@router.get("/breaches")
async def list_breaches(
    contained: bool | None = Query(None),
    overdue: bool | None = Query(None),
    engine: ComplianceEngine = Depends(get_engine),
):
    """List breaches with optional filters."""
    breaches = list(engine._breaches.values())
    
    if contained is not None:
        breaches = [b for b in breaches if b.contained == contained]
    
    if overdue is True:
        breaches = [b for b in breaches if b.is_overdue]
    
    return {
        "total": len(breaches),
        "breaches": [
            {
                "id": b.id,
                "severity": b.severity.value,
                "record_count": b.record_count,
                "contained": b.contained,
                "is_overdue": b.is_overdue,
                "discovered_at": b.discovered_at.isoformat(),
            }
            for b in breaches
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# AI GOVERNANCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/ai-systems", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_ai_system(
    request: AISystemRegisterRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Register an AI system for EU AI Act compliance.
    """
    registration = await engine.register_ai_system(
        system_name=request.system_name,
        system_version=request.system_version,
        provider=request.provider,
        risk_classification=request.risk_classification,
        intended_purpose=request.intended_purpose,
        use_cases=request.use_cases,
        model_type=request.model_type,
        human_oversight_measures=request.human_oversight_measures,
        training_data_description=request.training_data_description,
    )
    
    return {
        "id": registration.id,
        "system_name": registration.system_name,
        "risk_classification": registration.risk_classification.value,
        "requires_conformity": registration.risk_classification.requires_conformity_assessment,
        "requires_registration": registration.risk_classification.requires_registration,
    }


@router.post("/ai-decisions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def log_ai_decision(
    request: AIDecisionLogRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Log an AI decision for transparency and explainability.
    
    Per EU AI Act Article 12 and GDPR Article 22.
    """
    decision = await engine.log_ai_decision(
        ai_system_id=request.ai_system_id,
        model_version=request.model_version,
        decision_type=request.decision_type,
        decision_outcome=request.decision_outcome,
        confidence_score=request.confidence_score,
        input_summary=request.input_summary,
        reasoning_chain=request.reasoning_chain,
        key_factors=request.key_factors,
        subject_id=request.subject_id,
        has_legal_effect=request.has_legal_effect,
        has_significant_effect=request.has_significant_effect,
    )
    
    return {
        "id": decision.id,
        "decision_type": decision.decision_type,
        "confidence_score": decision.confidence_score,
        "human_review_available": True,
    }


@router.post("/ai-decisions/review")
async def request_human_review(
    request: HumanReviewRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Request or complete human review of an AI decision.
    
    Per GDPR Article 22 right to human intervention.
    """
    decision = await engine.request_human_review(
        decision_id=request.decision_id,
        reviewer_id=request.reviewer_id,
        override=request.override,
        override_reason=request.override_reason,
    )
    
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return {
        "id": decision.id,
        "human_reviewed": decision.human_reviewed,
        "human_override": decision.human_override,
    }


@router.get("/ai-decisions/{decision_id}/explanation")
async def get_ai_decision_explanation(
    decision_id: str,
    engine: ComplianceEngine = Depends(get_engine),
):
    """
    Get plain-language explanation of an AI decision.
    
    Per GDPR Article 22 and EU AI Act transparency requirements.
    """
    explanation = await engine.get_ai_decision_explanation(decision_id)
    
    if not explanation:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return explanation


@router.get("/ai-systems")
async def list_ai_systems(
    engine: ComplianceEngine = Depends(get_engine),
):
    """List all registered AI systems."""
    systems = list(engine._ai_systems.values())
    
    return {
        "total": len(systems),
        "high_risk_count": len([
            s for s in systems
            if s.risk_classification in {AIRiskClassification.HIGH_RISK, AIRiskClassification.GPAI_SYSTEMIC}
        ]),
        "systems": [
            {
                "id": s.id,
                "system_name": s.system_name,
                "risk_classification": s.risk_classification.value,
                "conformity_completed": s.conformity_assessment_completed,
                "eu_registered": s.eu_database_registered,
            }
            for s in systems
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT LOG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/audit-events")
async def get_audit_events(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    category: AuditEventCategory | None = Query(None),
    actor_id: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(100, le=1000),
    engine: ComplianceEngine = Depends(get_engine),
):
    """Query audit events with filters."""
    events = await engine.get_audit_events(
        start_date=start_date,
        end_date=end_date,
        category=category,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    
    return {
        "total": len(events),
        "events": [
            {
                "id": e.id,
                "category": e.category.value if hasattr(e.category, 'value') else e.category,
                "event_type": e.event_type,
                "action": e.action,
                "actor_id": e.actor_id,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "success": e.success,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


@router.get("/audit-chain/verify")
async def verify_audit_chain(
    engine: ComplianceEngine = Depends(get_engine),
):
    """Verify audit log chain integrity."""
    is_valid, message = engine.verify_audit_chain()
    return {
        "valid": is_valid,
        "message": message,
    }


# ═══════════════════════════════════════════════════════════════════════════
# REPORTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/reports", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_compliance_report(
    request: ComplianceReportRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Generate a compliance assessment report."""
    report = await engine.generate_compliance_report(
        report_type=request.report_type,
        start_date=request.start_date,
        end_date=request.end_date,
        frameworks=request.frameworks,
        jurisdictions=request.jurisdictions,
        generated_by=request.generated_by,
    )
    
    return {
        "id": report.id,
        "overall_compliance_score": report.overall_compliance_score,
        "total_controls_assessed": report.total_controls_assessed,
        "controls_compliant": report.controls_compliant,
        "controls_non_compliant": report.controls_non_compliant,
        "critical_gaps_count": len(report.critical_gaps),
        "high_risk_gaps_count": len(report.high_risk_gaps),
        "dsar_metrics": report.dsar_metrics,
        "breach_metrics": report.breach_metrics,
        "ai_system_count": report.ai_system_count,
    }


@router.post("/controls/verify")
async def verify_control(
    request: ControlVerifyRequest,
    engine: ComplianceEngine = Depends(get_engine),
):
    """Verify a compliance control."""
    status = await engine.verify_control(
        control_id=request.control_id,
        verifier_id=request.verifier_id,
        evidence=request.evidence,
        notes=request.notes,
    )
    
    if not status:
        raise HTTPException(status_code=404, detail="Control not found")
    
    return {
        "control_id": status.control_id,
        "implemented": status.implemented,
        "verified": status.verified,
        "status": status.status,
    }


@router.post("/controls/verify-all")
async def run_automated_verifications(
    engine: ComplianceEngine = Depends(get_engine),
):
    """Run all automated control verifications."""
    results = await engine.run_automated_verifications()
    
    return {
        "total": len(results),
        "passed": sum(1 for r in results.values() if r),
        "failed": sum(1 for r in results.values() if not r),
        "results": results,
    }


@router.get("/status")
async def get_compliance_status(
    engine: ComplianceEngine = Depends(get_engine),
):
    """Get overall compliance status."""
    frameworks = engine.config.frameworks_list
    
    status_by_framework = {}
    total_controls = 0
    total_compliant = 0
    
    for framework in frameworks:
        framework_status = engine.registry.get_framework_compliance_status(framework)
        status_by_framework[framework.value] = framework_status
        total_controls += framework_status["total"]
        total_compliant += framework_status["verified"]
    
    return {
        "overall_compliance_percentage": (total_compliant / total_controls * 100) if total_controls > 0 else 0,
        "total_controls": total_controls,
        "compliant_controls": total_compliant,
        "frameworks": status_by_framework,
        "active_jurisdictions": [j.value for j in engine.config.jurisdictions_list],
        "dsars_pending": len([d for d in engine._dsars.values() if d.status != "completed"]),
        "dsars_overdue": len([d for d in engine._dsars.values() if d.is_overdue]),
        "breaches_active": len([b for b in engine._breaches.values() if not b.contained]),
        "ai_systems_registered": len(engine._ai_systems),
    }
