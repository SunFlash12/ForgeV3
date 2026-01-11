"""
Forge Compliance Framework - Vendor Risk Management

Third-party risk management implementing:
- Vendor due diligence
- Contract compliance tracking
- Subprocessor management (GDPR Article 28)
- SLA monitoring
- Security assessment integration

Supports:
- SOC 2 vendor management requirements
- GDPR Data Processing Agreement tracking
- HIPAA Business Associate Agreements
- PCI-DSS third-party management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import (
    DataClassification,
    ComplianceFramework,
)

logger = structlog.get_logger(__name__)


class VendorCategory(str, Enum):
    """Vendor classification categories."""
    DATA_PROCESSOR = "data_processor"  # GDPR Article 28
    SUBPROCESSOR = "subprocessor"
    CLOUD_PROVIDER = "cloud_provider"
    SaaS_PROVIDER = "saas_provider"
    IT_SERVICE = "it_service"
    BUSINESS_ASSOCIATE = "business_associate"  # HIPAA
    PAYMENT_PROCESSOR = "payment_processor"  # PCI
    MARKETING_PARTNER = "marketing_partner"
    ANALYTICS_PROVIDER = "analytics_provider"
    CONSULTANT = "consultant"
    OTHER = "other"


class VendorRiskLevel(str, Enum):
    """Vendor risk classification."""
    CRITICAL = "critical"  # Failure severely impacts operations
    HIGH = "high"  # Failure significantly impacts operations
    MEDIUM = "medium"  # Failure moderately impacts operations
    LOW = "low"  # Minimal impact


class VendorStatus(str, Enum):
    """Vendor relationship status."""
    PROSPECTIVE = "prospective"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    ARCHIVED = "archived"


class AssessmentStatus(str, Enum):
    """Security assessment status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class VendorProfile:
    """Vendor profile with compliance information."""
    vendor_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Basic info
    name: str = ""
    legal_name: str = ""
    category: VendorCategory = VendorCategory.OTHER
    description: str = ""
    website: str = ""
    
    # Classification
    risk_level: VendorRiskLevel = VendorRiskLevel.MEDIUM
    status: VendorStatus = VendorStatus.PROSPECTIVE
    
    # Data handling
    data_classifications_accessed: list[DataClassification] = field(default_factory=list)
    data_processing_locations: list[str] = field(default_factory=list)
    subprocessors: list[str] = field(default_factory=list)  # Other vendor IDs
    
    # Compliance
    certifications: list[str] = field(default_factory=list)
    # e.g., ["SOC 2 Type II", "ISO 27001", "HIPAA"]
    frameworks_compliant: list[ComplianceFramework] = field(default_factory=list)
    
    # Contacts
    primary_contact_name: str = ""
    primary_contact_email: str = ""
    security_contact_email: str = ""
    dpo_contact_email: str = ""  # Data Protection Officer
    
    # Dates
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    last_assessment_date: datetime | None = None
    next_assessment_due: datetime | None = None
    
    # Internal tracking
    internal_owner: str = ""
    business_unit: str = ""
    notes: str = ""


@dataclass
class VendorContract:
    """Vendor contract/agreement tracking."""
    contract_id: str = field(default_factory=lambda: str(uuid4()))
    vendor_id: str = ""
    
    # Contract details
    contract_type: str = ""  # DPA, BAA, MSA, NDA, SLA
    contract_name: str = ""
    contract_reference: str = ""
    
    # Dates
    effective_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    expiration_date: datetime | None = None
    auto_renewal: bool = False
    renewal_notice_days: int = 30
    
    # Status
    status: str = "active"  # draft, active, expired, terminated
    signed_date: datetime | None = None
    
    # GDPR Article 28 requirements (for DPAs)
    includes_processing_instructions: bool = False
    includes_security_measures: bool = False
    includes_subprocessor_clause: bool = False
    includes_audit_rights: bool = False
    includes_data_deletion: bool = False
    includes_dpa_assistance: bool = False
    
    # HIPAA BAA requirements
    is_baa: bool = False
    baa_safeguards_specified: bool = False
    baa_breach_notification: bool = False
    
    # Document reference
    document_location: str = ""
    document_hash: str = ""


@dataclass
class SecurityAssessment:
    """Vendor security assessment record."""
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    vendor_id: str = ""
    
    # Assessment type
    assessment_type: str = ""  # questionnaire, audit, pentest, soc2_review
    assessment_name: str = ""
    
    # Status
    status: AssessmentStatus = AssessmentStatus.NOT_STARTED
    initiated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    
    # Scope
    frameworks_assessed: list[ComplianceFramework] = field(default_factory=list)
    areas_covered: list[str] = field(default_factory=list)
    # e.g., ["access_control", "encryption", "incident_response"]
    
    # Results
    overall_score: float | None = None  # 0-100
    risk_rating: VendorRiskLevel | None = None
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    
    # Documentation
    report_reference: str = ""
    evidence_references: list[str] = field(default_factory=list)
    
    # Review
    reviewed_by: str = ""
    review_notes: str = ""
    approval_status: str = ""  # pending, approved, rejected
    approved_by: str = ""
    approved_at: datetime | None = None


@dataclass
class VendorIncident:
    """Vendor-related security incident."""
    incident_id: str = field(default_factory=lambda: str(uuid4()))
    vendor_id: str = ""
    
    # Incident details
    incident_type: str = ""  # breach, outage, sla_violation, compliance_issue
    description: str = ""
    severity: VendorRiskLevel = VendorRiskLevel.MEDIUM
    
    # Timeline
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    
    # Impact
    data_affected: bool = False
    data_classifications: list[DataClassification] = field(default_factory=list)
    records_affected: int = 0
    
    # Response
    status: str = "open"  # open, investigating, resolved, closed
    root_cause: str = ""
    remediation_actions: list[str] = field(default_factory=list)
    
    # Follow-up
    reassessment_required: bool = False
    contract_review_required: bool = False


class VendorRiskManagementService:
    """
    Comprehensive vendor/third-party risk management.
    
    Manages vendor lifecycle from due diligence through
    ongoing monitoring and offboarding.
    """
    
    def __init__(self):
        self._vendors: dict[str, VendorProfile] = {}
        self._contracts: dict[str, list[VendorContract]] = {}
        self._assessments: dict[str, list[SecurityAssessment]] = {}
        self._incidents: dict[str, list[VendorIncident]] = {}
        
        # Assessment frequency by risk level (days)
        self._assessment_frequency = {
            VendorRiskLevel.CRITICAL: 180,  # Every 6 months
            VendorRiskLevel.HIGH: 365,  # Annual
            VendorRiskLevel.MEDIUM: 730,  # Every 2 years
            VendorRiskLevel.LOW: 1095,  # Every 3 years
        }
    
    # ───────────────────────────────────────────────────────────────
    # VENDOR MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    async def register_vendor(
        self,
        name: str,
        category: VendorCategory,
        description: str = "",
        data_classifications: list[DataClassification] | None = None,
        processing_locations: list[str] | None = None,
        internal_owner: str = "",
    ) -> VendorProfile:
        """Register a new vendor."""
        vendor = VendorProfile(
            name=name,
            category=category,
            description=description,
            data_classifications_accessed=data_classifications or [],
            data_processing_locations=processing_locations or [],
            internal_owner=internal_owner,
            status=VendorStatus.PROSPECTIVE,
        )
        
        # Auto-classify initial risk
        vendor.risk_level = self._assess_initial_risk(vendor)
        
        # Set next assessment due date
        frequency = self._assessment_frequency[vendor.risk_level]
        vendor.next_assessment_due = datetime.now(UTC) + timedelta(days=frequency)
        
        self._vendors[vendor.vendor_id] = vendor
        self._contracts[vendor.vendor_id] = []
        self._assessments[vendor.vendor_id] = []
        self._incidents[vendor.vendor_id] = []
        
        logger.info(
            "vendor_registered",
            vendor_id=vendor.vendor_id,
            name=name,
            category=category.value,
            risk_level=vendor.risk_level.value,
        )
        
        return vendor
    
    def _assess_initial_risk(self, vendor: VendorProfile) -> VendorRiskLevel:
        """Assess initial vendor risk level."""
        # High risk data access
        high_risk_data = {
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.PCI,
        }
        
        if any(d in high_risk_data for d in vendor.data_classifications_accessed):
            return VendorRiskLevel.CRITICAL
        
        # Category-based assessment
        critical_categories = {
            VendorCategory.DATA_PROCESSOR,
            VendorCategory.CLOUD_PROVIDER,
            VendorCategory.BUSINESS_ASSOCIATE,
            VendorCategory.PAYMENT_PROCESSOR,
        }
        
        if vendor.category in critical_categories:
            return VendorRiskLevel.HIGH
        
        # Personal data processing
        if DataClassification.PERSONAL_DATA in vendor.data_classifications_accessed:
            return VendorRiskLevel.HIGH
        
        return VendorRiskLevel.MEDIUM
    
    async def update_vendor_status(
        self,
        vendor_id: str,
        status: VendorStatus,
        notes: str = "",
        updated_by: str = "",
    ) -> VendorProfile:
        """Update vendor status."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        old_status = vendor.status
        vendor.status = status
        
        if status == VendorStatus.APPROVED:
            vendor.approved_at = datetime.now(UTC)
        
        if notes:
            vendor.notes += f"\n[{datetime.now(UTC).isoformat()}] Status: {status.value} - {notes}"
        
        logger.info(
            "vendor_status_updated",
            vendor_id=vendor_id,
            old_status=old_status.value,
            new_status=status.value,
            updated_by=updated_by,
        )
        
        return vendor
    
    async def add_subprocessor(
        self,
        vendor_id: str,
        subprocessor_id: str,
    ) -> VendorProfile:
        """
        Add a subprocessor to a vendor.
        
        Per GDPR Article 28(2) - written authorization for subprocessors.
        """
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        if subprocessor_id not in vendor.subprocessors:
            vendor.subprocessors.append(subprocessor_id)
        
        logger.info(
            "subprocessor_added",
            vendor_id=vendor_id,
            subprocessor_id=subprocessor_id,
        )
        
        return vendor
    
    # ───────────────────────────────────────────────────────────────
    # CONTRACT MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    async def add_contract(
        self,
        vendor_id: str,
        contract_type: str,
        contract_name: str,
        effective_date: datetime,
        expiration_date: datetime | None = None,
        is_dpa: bool = False,
        is_baa: bool = False,
        document_location: str = "",
    ) -> VendorContract:
        """Add a contract for a vendor."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        contract = VendorContract(
            vendor_id=vendor_id,
            contract_type=contract_type,
            contract_name=contract_name,
            effective_date=effective_date,
            expiration_date=expiration_date,
            document_location=document_location,
            is_baa=is_baa,
        )
        
        # Set DPA-specific flags if applicable
        if is_dpa or contract_type.upper() == "DPA":
            contract.includes_processing_instructions = True
            contract.includes_security_measures = True
            contract.includes_subprocessor_clause = True
            contract.includes_audit_rights = True
            contract.includes_data_deletion = True
            contract.includes_dpa_assistance = True
        
        self._contracts[vendor_id].append(contract)
        
        logger.info(
            "vendor_contract_added",
            vendor_id=vendor_id,
            contract_type=contract_type,
        )
        
        return contract
    
    async def verify_dpa_completeness(
        self,
        contract_id: str,
    ) -> tuple[bool, list[str]]:
        """
        Verify DPA meets GDPR Article 28 requirements.
        
        Returns (is_complete, missing_elements).
        """
        contract = None
        for contracts in self._contracts.values():
            for c in contracts:
                if c.contract_id == contract_id:
                    contract = c
                    break
        
        if not contract:
            return False, ["Contract not found"]
        
        missing = []
        
        # GDPR Article 28(3) requirements
        if not contract.includes_processing_instructions:
            missing.append("Processing instructions (Art 28(3)(a))")
        if not contract.includes_security_measures:
            missing.append("Security measures (Art 28(3)(c))")
        if not contract.includes_subprocessor_clause:
            missing.append("Subprocessor conditions (Art 28(3)(d))")
        if not contract.includes_audit_rights:
            missing.append("Audit rights (Art 28(3)(h))")
        if not contract.includes_data_deletion:
            missing.append("Data deletion requirements (Art 28(3)(g))")
        if not contract.includes_dpa_assistance:
            missing.append("DPA cooperation (Art 28(3)(e-f))")
        
        return len(missing) == 0, missing
    
    def get_expiring_contracts(
        self,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get contracts expiring within specified days."""
        expiring = []
        cutoff = datetime.now(UTC) + timedelta(days=days)
        
        for vendor_id, contracts in self._contracts.items():
            vendor = self._vendors.get(vendor_id)
            for contract in contracts:
                if contract.expiration_date and contract.expiration_date <= cutoff:
                    if contract.status == "active":
                        expiring.append({
                            "vendor_id": vendor_id,
                            "vendor_name": vendor.name if vendor else "Unknown",
                            "contract_id": contract.contract_id,
                            "contract_type": contract.contract_type,
                            "expiration_date": contract.expiration_date.isoformat(),
                            "days_remaining": (contract.expiration_date - datetime.now(UTC)).days,
                        })
        
        return sorted(expiring, key=lambda x: x["days_remaining"])
    
    # ───────────────────────────────────────────────────────────────
    # SECURITY ASSESSMENTS
    # ───────────────────────────────────────────────────────────────
    
    async def initiate_assessment(
        self,
        vendor_id: str,
        assessment_type: str,
        assessment_name: str,
        frameworks: list[ComplianceFramework] | None = None,
        initiated_by: str = "",
    ) -> SecurityAssessment:
        """Initiate a new security assessment."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        assessment = SecurityAssessment(
            vendor_id=vendor_id,
            assessment_type=assessment_type,
            assessment_name=assessment_name,
            frameworks_assessed=frameworks or [],
            status=AssessmentStatus.IN_PROGRESS,
        )
        
        self._assessments[vendor_id].append(assessment)
        
        logger.info(
            "vendor_assessment_initiated",
            vendor_id=vendor_id,
            assessment_type=assessment_type,
        )
        
        return assessment
    
    async def complete_assessment(
        self,
        assessment_id: str,
        overall_score: float,
        findings: dict[str, int],
        risk_rating: VendorRiskLevel,
        reviewed_by: str = "",
        report_reference: str = "",
    ) -> SecurityAssessment:
        """Complete a security assessment with results."""
        assessment = None
        vendor_id = None
        
        for vid, assessments in self._assessments.items():
            for a in assessments:
                if a.assessment_id == assessment_id:
                    assessment = a
                    vendor_id = vid
                    break
        
        if not assessment:
            raise ValueError(f"Assessment not found: {assessment_id}")
        
        assessment.status = AssessmentStatus.PENDING_REVIEW
        assessment.completed_at = datetime.now(UTC)
        assessment.overall_score = overall_score
        assessment.risk_rating = risk_rating
        assessment.findings_critical = findings.get("critical", 0)
        assessment.findings_high = findings.get("high", 0)
        assessment.findings_medium = findings.get("medium", 0)
        assessment.findings_low = findings.get("low", 0)
        assessment.reviewed_by = reviewed_by
        assessment.report_reference = report_reference
        
        # Set expiration (assessments valid for 1 year typically)
        assessment.expires_at = datetime.now(UTC) + timedelta(days=365)
        
        # Update vendor
        if vendor_id:
            vendor = self._vendors.get(vendor_id)
            if vendor:
                vendor.last_assessment_date = datetime.now(UTC)
                vendor.risk_level = risk_rating
                
                # Schedule next assessment
                frequency = self._assessment_frequency[risk_rating]
                vendor.next_assessment_due = datetime.now(UTC) + timedelta(days=frequency)
        
        logger.info(
            "vendor_assessment_completed",
            assessment_id=assessment_id,
            score=overall_score,
            risk_rating=risk_rating.value,
        )
        
        return assessment
    
    async def approve_assessment(
        self,
        assessment_id: str,
        approved_by: str,
        notes: str = "",
    ) -> SecurityAssessment:
        """Approve a completed assessment."""
        assessment = None
        vendor_id = None
        
        for vid, assessments in self._assessments.items():
            for a in assessments:
                if a.assessment_id == assessment_id:
                    assessment = a
                    vendor_id = vid
                    break
        
        if not assessment:
            raise ValueError(f"Assessment not found: {assessment_id}")
        
        assessment.status = AssessmentStatus.APPROVED
        assessment.approval_status = "approved"
        assessment.approved_by = approved_by
        assessment.approved_at = datetime.now(UTC)
        assessment.review_notes = notes
        
        # Update vendor status if not already active
        if vendor_id:
            vendor = self._vendors.get(vendor_id)
            if vendor and vendor.status in {VendorStatus.PROSPECTIVE, VendorStatus.UNDER_REVIEW}:
                vendor.status = VendorStatus.APPROVED
                vendor.approved_at = datetime.now(UTC)
        
        return assessment
    
    def get_overdue_assessments(self) -> list[dict[str, Any]]:
        """Get vendors with overdue security assessments."""
        overdue = []
        now = datetime.now(UTC)
        
        for vendor_id, vendor in self._vendors.items():
            if vendor.status not in {VendorStatus.ACTIVE, VendorStatus.APPROVED}:
                continue
            
            if vendor.next_assessment_due and now > vendor.next_assessment_due:
                overdue.append({
                    "vendor_id": vendor_id,
                    "vendor_name": vendor.name,
                    "risk_level": vendor.risk_level.value,
                    "last_assessment": vendor.last_assessment_date.isoformat() if vendor.last_assessment_date else None,
                    "due_date": vendor.next_assessment_due.isoformat(),
                    "days_overdue": (now - vendor.next_assessment_due).days,
                })
        
        return sorted(overdue, key=lambda x: x["days_overdue"], reverse=True)
    
    # ───────────────────────────────────────────────────────────────
    # INCIDENT TRACKING
    # ───────────────────────────────────────────────────────────────
    
    async def record_incident(
        self,
        vendor_id: str,
        incident_type: str,
        description: str,
        severity: VendorRiskLevel,
        data_affected: bool = False,
        data_classifications: list[DataClassification] | None = None,
        records_affected: int = 0,
    ) -> VendorIncident:
        """Record a vendor-related incident."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        incident = VendorIncident(
            vendor_id=vendor_id,
            incident_type=incident_type,
            description=description,
            severity=severity,
            data_affected=data_affected,
            data_classifications=data_classifications or [],
            records_affected=records_affected,
        )
        
        # Determine if reassessment needed
        if severity in {VendorRiskLevel.CRITICAL, VendorRiskLevel.HIGH}:
            incident.reassessment_required = True
            incident.contract_review_required = True
        
        self._incidents[vendor_id].append(incident)
        
        logger.warning(
            "vendor_incident_recorded",
            vendor_id=vendor_id,
            vendor_name=vendor.name,
            incident_type=incident_type,
            severity=severity.value,
        )
        
        return incident
    
    # ───────────────────────────────────────────────────────────────
    # REPORTING
    # ───────────────────────────────────────────────────────────────
    
    def get_vendor_summary(self, vendor_id: str) -> dict[str, Any]:
        """Get comprehensive vendor summary."""
        vendor = self._vendors.get(vendor_id)
        if not vendor:
            return {}
        
        contracts = self._contracts.get(vendor_id, [])
        assessments = self._assessments.get(vendor_id, [])
        incidents = self._incidents.get(vendor_id, [])
        
        # Get most recent assessment
        recent_assessment = None
        if assessments:
            approved = [a for a in assessments if a.status == AssessmentStatus.APPROVED]
            if approved:
                recent_assessment = max(approved, key=lambda a: a.completed_at or datetime.min)
        
        return {
            "vendor_id": vendor.vendor_id,
            "name": vendor.name,
            "category": vendor.category.value,
            "status": vendor.status.value,
            "risk_level": vendor.risk_level.value,
            "data_classifications": [d.value for d in vendor.data_classifications_accessed],
            "processing_locations": vendor.data_processing_locations,
            "certifications": vendor.certifications,
            "contracts": {
                "total": len(contracts),
                "active": len([c for c in contracts if c.status == "active"]),
                "has_dpa": any(c.includes_processing_instructions for c in contracts),
                "has_baa": any(c.is_baa for c in contracts),
            },
            "assessments": {
                "total": len(assessments),
                "last_assessment": recent_assessment.completed_at.isoformat() if recent_assessment else None,
                "last_score": recent_assessment.overall_score if recent_assessment else None,
                "next_due": vendor.next_assessment_due.isoformat() if vendor.next_assessment_due else None,
            },
            "incidents": {
                "total": len(incidents),
                "open": len([i for i in incidents if i.status == "open"]),
            },
            "subprocessors": len(vendor.subprocessors),
        }
    
    def get_metrics(self) -> dict[str, Any]:
        """Get vendor management metrics."""
        vendors = list(self._vendors.values())
        
        return {
            "total_vendors": len(vendors),
            "by_status": {
                status.value: len([v for v in vendors if v.status == status])
                for status in VendorStatus
            },
            "by_risk_level": {
                level.value: len([v for v in vendors if v.risk_level == level])
                for level in VendorRiskLevel
            },
            "by_category": {
                cat.value: len([v for v in vendors if v.category == cat])
                for cat in VendorCategory
            },
            "assessments_overdue": len(self.get_overdue_assessments()),
            "contracts_expiring_30d": len(self.get_expiring_contracts(30)),
            "total_incidents": sum(
                len(self._incidents.get(v.vendor_id, []))
                for v in vendors
            ),
        }


# Global service instance
_vendor_service: VendorRiskManagementService | None = None


def get_vendor_risk_service() -> VendorRiskManagementService:
    """Get the global vendor risk management service."""
    global _vendor_service
    if _vendor_service is None:
        _vendor_service = VendorRiskManagementService()
    return _vendor_service
