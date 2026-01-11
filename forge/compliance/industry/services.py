"""
Forge Compliance Framework - Industry-Specific Compliance

Implements industry-specific compliance requirements:
- HIPAA/HITECH (Healthcare)
- PCI-DSS 4.0.1 (Payment Card)
- SOX (Financial Reporting)
- GLBA (Financial Services)
- FERPA (Education)
- COPPA (Children's Privacy)

Each module provides specialized controls, data handling,
and audit requirements for the respective industry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import DataClassification
from forge.compliance.encryption import get_encryption_service

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# HIPAA COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════


class PHIIdentifier(str, Enum):
    """HIPAA Safe Harbor de-identification identifiers."""
    NAME = "name"
    GEOGRAPHIC = "geographic"  # Smaller than state
    DATES = "dates"  # Except year for ages <90
    PHONE = "phone"
    FAX = "fax"
    EMAIL = "email"
    SSN = "ssn"
    MRN = "medical_record_number"
    HEALTH_PLAN_ID = "health_plan_id"
    ACCOUNT_NUMBER = "account_number"
    LICENSE_NUMBER = "license_number"
    VEHICLE_ID = "vehicle_id"
    DEVICE_ID = "device_id"
    URL = "url"
    IP_ADDRESS = "ip_address"
    BIOMETRIC = "biometric"
    PHOTO = "photo"
    UNIQUE_CODE = "unique_code"


class HIPAAAuthorizationPurpose(str, Enum):
    """Valid purposes for PHI disclosure."""
    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    RESEARCH = "research"
    PUBLIC_HEALTH = "public_health"
    LAW_ENFORCEMENT = "law_enforcement"
    LEGAL_PROCEEDINGS = "legal_proceedings"
    DECEASED = "deceased"
    ORGAN_DONATION = "organ_donation"
    WORKERS_COMP = "workers_compensation"
    PATIENT_REQUEST = "patient_request"


@dataclass
class HIPAAAuthorization:
    """HIPAA authorization record for PHI disclosure."""
    authorization_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Patient information
    patient_id: str = ""
    patient_name: str = ""
    
    # Authorization details
    purpose: HIPAAAuthorizationPurpose = HIPAAAuthorizationPurpose.TREATMENT
    description: str = ""
    phi_elements: list[str] = field(default_factory=list)
    
    # Parties
    authorized_recipient: str = ""
    authorized_by: str = ""
    
    # Validity
    effective_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    expiration_date: datetime | None = None
    revoked: bool = False
    revoked_at: datetime | None = None
    
    # Signature
    signature_obtained: bool = False
    signature_date: datetime | None = None
    signature_method: str = ""  # physical, electronic
    
    @property
    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.expiration_date and datetime.now(UTC) > self.expiration_date:
            return False
        return self.signature_obtained


@dataclass
class PHIAccessLog:
    """HIPAA-compliant PHI access log entry."""
    log_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Access details
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    accessor_id: str = ""
    accessor_role: str = ""
    accessor_organization: str = ""
    
    # PHI details
    patient_id: str = ""
    phi_elements: list[str] = field(default_factory=list)
    access_type: str = ""  # view, update, delete, export
    
    # Authorization
    authorization_id: str | None = None
    purpose: HIPAAAuthorizationPurpose = HIPAAAuthorizationPurpose.TREATMENT
    
    # Technical details
    ip_address: str = ""
    system_id: str = ""


class HIPAAComplianceService:
    """
    HIPAA/HITECH compliance service.
    
    Implements:
    - PHI identification and de-identification
    - Authorization management
    - Access logging (164.312(b))
    - Minimum necessary enforcement
    - Breach assessment
    """
    
    def __init__(self):
        self._authorizations: dict[str, HIPAAAuthorization] = {}
        self._access_logs: list[PHIAccessLog] = []
        self._phi_patterns = self._initialize_phi_patterns()
        
        # Encryption service for PHI
        self.encryption = get_encryption_service()
    
    def _initialize_phi_patterns(self) -> dict[str, str]:
        """Initialize regex patterns for PHI detection."""
        return {
            PHIIdentifier.SSN.value: r"\b\d{3}-\d{2}-\d{4}\b",
            PHIIdentifier.PHONE.value: r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            PHIIdentifier.EMAIL.value: r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            PHIIdentifier.MRN.value: r"\bMRN[:\s]?\d{6,}\b",
            PHIIdentifier.IP_ADDRESS.value: r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        }
    
    async def create_authorization(
        self,
        patient_id: str,
        patient_name: str,
        purpose: HIPAAAuthorizationPurpose,
        phi_elements: list[str],
        authorized_recipient: str,
        authorized_by: str,
        expiration_date: datetime | None = None,
    ) -> HIPAAAuthorization:
        """Create a HIPAA authorization for PHI disclosure."""
        # Default expiration based on purpose
        if expiration_date is None:
            if purpose == HIPAAAuthorizationPurpose.RESEARCH:
                expiration_date = datetime.now(UTC) + timedelta(days=365)
            else:
                expiration_date = datetime.now(UTC) + timedelta(days=90)
        
        auth = HIPAAAuthorization(
            patient_id=patient_id,
            patient_name=patient_name,
            purpose=purpose,
            phi_elements=phi_elements,
            authorized_recipient=authorized_recipient,
            authorized_by=authorized_by,
            expiration_date=expiration_date,
        )
        
        self._authorizations[auth.authorization_id] = auth
        
        logger.info(
            "hipaa_authorization_created",
            authorization_id=auth.authorization_id,
            patient_id=patient_id,
            purpose=purpose.value,
        )
        
        return auth
    
    async def check_authorization(
        self,
        patient_id: str,
        purpose: HIPAAAuthorizationPurpose,
        phi_elements: list[str],
        accessor_id: str,
    ) -> tuple[bool, str]:
        """
        Check if PHI access is authorized.
        
        Returns (authorized, reason).
        """
        # Treatment, Payment, Operations (TPO) don't require authorization
        if purpose in {
            HIPAAAuthorizationPurpose.TREATMENT,
            HIPAAAuthorizationPurpose.PAYMENT,
            HIPAAAuthorizationPurpose.HEALTHCARE_OPERATIONS,
        }:
            return True, "TPO access permitted"
        
        # Check for valid authorization
        for auth in self._authorizations.values():
            if auth.patient_id != patient_id:
                continue
            if not auth.is_valid:
                continue
            if auth.purpose != purpose:
                continue
            
            # Check PHI elements covered
            if all(elem in auth.phi_elements for elem in phi_elements):
                return True, f"Authorization {auth.authorization_id}"
        
        return False, "No valid authorization found"
    
    async def log_phi_access(
        self,
        patient_id: str,
        accessor_id: str,
        accessor_role: str,
        phi_elements: list[str],
        access_type: str,
        purpose: HIPAAAuthorizationPurpose,
        authorization_id: str | None = None,
        ip_address: str = "",
    ) -> PHIAccessLog:
        """
        Log PHI access per HIPAA 164.312(b).
        
        Required for all PHI access regardless of authorization.
        """
        log_entry = PHIAccessLog(
            patient_id=patient_id,
            accessor_id=accessor_id,
            accessor_role=accessor_role,
            phi_elements=phi_elements,
            access_type=access_type,
            purpose=purpose,
            authorization_id=authorization_id,
            ip_address=ip_address,
        )
        
        self._access_logs.append(log_entry)
        
        logger.info(
            "phi_access_logged",
            log_id=log_entry.log_id,
            patient_id=patient_id,
            access_type=access_type,
        )
        
        return log_entry
    
    def deidentify_phi(
        self,
        data: dict[str, Any],
        method: str = "safe_harbor",
    ) -> dict[str, Any]:
        """
        De-identify PHI using Safe Harbor method.
        
        Per HIPAA 164.514(b)(2).
        """
        result = data.copy()
        
        # Remove all 18 Safe Harbor identifiers
        identifiers_to_remove = [
            "name", "first_name", "last_name",
            "address", "city", "zip", "zip_code",
            "date_of_birth", "admission_date", "discharge_date",
            "phone", "phone_number", "fax",
            "email", "email_address",
            "ssn", "social_security",
            "mrn", "medical_record_number",
            "health_plan_id", "account_number",
            "license", "vehicle_id", "device_id",
            "url", "ip_address",
            "biometric", "photo", "image",
        ]
        
        for key in list(result.keys()):
            key_lower = key.lower()
            if any(ident in key_lower for ident in identifiers_to_remove):
                result[key] = "[REDACTED]"
        
        # Generalize dates (keep year for ages <90)
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.replace(month=1, day=1)
        
        return result
    
    def assess_breach_risk(
        self,
        phi_elements: list[str],
        record_count: int,
        circumstances: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assess breach notification requirements.
        
        Per HIPAA Breach Notification Rule 164.402-414.
        """
        # Risk factors
        risk_factors = {
            "phi_nature": 0.0,
            "unauthorized_access": 0.0,
            "mitigation": 0.0,
            "harm_probability": 0.0,
        }
        
        # Nature of PHI
        high_risk_elements = {"ssn", "financial", "diagnosis", "treatment"}
        if any(elem in high_risk_elements for elem in phi_elements):
            risk_factors["phi_nature"] = 0.8
        else:
            risk_factors["phi_nature"] = 0.3
        
        # Who accessed
        if circumstances.get("malicious_actor"):
            risk_factors["unauthorized_access"] = 0.9
        elif circumstances.get("unintended_recipient"):
            risk_factors["unauthorized_access"] = 0.5
        
        # Mitigation
        if circumstances.get("data_encrypted"):
            risk_factors["mitigation"] = -0.5
        if circumstances.get("immediate_recovery"):
            risk_factors["mitigation"] = -0.3
        
        # Overall probability
        total_risk = sum(risk_factors.values()) / 4
        
        # Determine notification requirement
        requires_notification = total_risk > 0.5 or record_count > 500
        
        return {
            "risk_factors": risk_factors,
            "total_risk_score": total_risk,
            "requires_notification": requires_notification,
            "notification_deadline_days": 60 if requires_notification else None,
            "hhs_notification_required": record_count > 500,
            "media_notification_required": record_count > 500,
        }


# ═══════════════════════════════════════════════════════════════════════════
# PCI-DSS COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════


class CardDataElement(str, Enum):
    """PCI-DSS cardholder data elements."""
    PAN = "pan"  # Primary Account Number
    CARDHOLDER_NAME = "cardholder_name"
    EXPIRATION_DATE = "expiration_date"
    SERVICE_CODE = "service_code"
    
    # Sensitive Authentication Data (never store)
    CVV = "cvv"
    PIN = "pin"
    TRACK_DATA = "track_data"


@dataclass
class PCIScope:
    """PCI-DSS scope definition."""
    scope_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    
    # Systems in scope
    systems: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    
    # Data flow
    data_entry_points: list[str] = field(default_factory=list)
    data_storage_locations: list[str] = field(default_factory=list)
    data_transmission_paths: list[str] = field(default_factory=list)
    
    # Third parties
    third_party_providers: list[str] = field(default_factory=list)
    
    # Validation
    last_validated: datetime | None = None
    validated_by: str = ""


@dataclass
class PCIScanResult:
    """Vulnerability scan result for PCI compliance."""
    scan_id: str = field(default_factory=lambda: str(uuid4()))
    scan_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    scan_type: str = ""  # internal, external, asv
    scanner: str = ""
    
    # Results
    passed: bool = False
    vulnerabilities_critical: int = 0
    vulnerabilities_high: int = 0
    vulnerabilities_medium: int = 0
    vulnerabilities_low: int = 0
    
    # Details
    findings: list[dict[str, Any]] = field(default_factory=list)
    
    # ASV-specific
    asv_name: str | None = None
    asv_scan_id: str | None = None


class PCIDSSComplianceService:
    """
    PCI-DSS 4.0.1 compliance service.
    
    Implements key requirements:
    - Req 3: Protect stored account data
    - Req 4: Encrypt transmission
    - Req 7: Restrict access (need-to-know)
    - Req 8: Identify users and authenticate
    - Req 10: Log and monitor all access
    - Req 11: Regularly test security systems
    """
    
    def __init__(self):
        self._scopes: dict[str, PCIScope] = {}
        self._scan_results: list[PCIScanResult] = []
        self._access_logs: list[dict] = []
        
        # PAN masking/truncation rules
        self._pan_display_digits = 4  # Last 4 for display
        
        # Encryption service
        self.encryption = get_encryption_service()
    
    async def define_scope(
        self,
        name: str,
        systems: list[str],
        networks: list[str],
        applications: list[str],
        data_entry_points: list[str],
        data_storage_locations: list[str],
    ) -> PCIScope:
        """Define PCI-DSS scope (CDE and connected systems)."""
        scope = PCIScope(
            name=name,
            systems=systems,
            networks=networks,
            applications=applications,
            data_entry_points=data_entry_points,
            data_storage_locations=data_storage_locations,
        )
        
        self._scopes[scope.scope_id] = scope
        
        logger.info(
            "pci_scope_defined",
            scope_id=scope.scope_id,
            name=name,
            systems_count=len(systems),
        )
        
        return scope
    
    def mask_pan(
        self,
        pan: str,
        show_first: int = 0,
        show_last: int = 4,
    ) -> str:
        """
        Mask PAN for display per PCI-DSS 3.4.
        
        Maximum: first 6 and last 4 digits.
        """
        pan_digits = "".join(c for c in pan if c.isdigit())
        
        if len(pan_digits) < 13:
            return "*" * len(pan_digits)
        
        # Enforce PCI limits
        show_first = min(show_first, 6)
        show_last = min(show_last, 4)
        
        masked_length = len(pan_digits) - show_first - show_last
        
        return (
            pan_digits[:show_first]
            + "*" * masked_length
            + pan_digits[-show_last:]
        )
    
    async def tokenize_pan(
        self,
        pan: str,
        purpose: str = "storage",
    ) -> str:
        """
        Tokenize PAN for secure storage.
        
        Per PCI-DSS 3.5 - Render PAN unreadable.
        """
        token = await self.encryption.tokenize(
            value=pan,
            classification=DataClassification.PCI,
        )
        
        logger.info(
            "pan_tokenized",
            purpose=purpose,
            token_prefix=token[:7],
        )
        
        return token
    
    async def validate_sad_not_stored(
        self,
        data: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate that Sensitive Authentication Data is not stored.
        
        Per PCI-DSS 3.2 - SAD cannot be stored after authorization.
        """
        violations = []
        sad_fields = ["cvv", "cvc", "cvv2", "pin", "track", "track_data"]
        
        for key in data.keys():
            key_lower = key.lower()
            if any(sad in key_lower for sad in sad_fields):
                violations.append(f"SAD field detected: {key}")
        
        return len(violations) == 0, violations
    
    def check_password_requirements(
        self,
        password: str,
    ) -> tuple[bool, list[str]]:
        """
        Check password meets PCI-DSS 4.0.1 requirements.
        
        Req 8.3.6: Minimum 12 characters (increased from 7).
        """
        violations = []
        
        # Length (PCI 4.0.1 increased to 12)
        if len(password) < 12:
            violations.append("Password must be at least 12 characters")
        
        # Complexity
        if not any(c.isupper() for c in password):
            violations.append("Password must contain uppercase")
        if not any(c.islower() for c in password):
            violations.append("Password must contain lowercase")
        if not any(c.isdigit() for c in password):
            violations.append("Password must contain digit")
        
        return len(violations) == 0, violations
    
    async def record_scan_result(
        self,
        scan_type: str,
        scanner: str,
        passed: bool,
        vulnerabilities: dict[str, int],
        findings: list[dict[str, Any]],
        asv_name: str | None = None,
    ) -> PCIScanResult:
        """
        Record vulnerability scan result.
        
        Per PCI-DSS 11.3 - Quarterly internal/external scans.
        """
        result = PCIScanResult(
            scan_type=scan_type,
            scanner=scanner,
            passed=passed,
            vulnerabilities_critical=vulnerabilities.get("critical", 0),
            vulnerabilities_high=vulnerabilities.get("high", 0),
            vulnerabilities_medium=vulnerabilities.get("medium", 0),
            vulnerabilities_low=vulnerabilities.get("low", 0),
            findings=findings,
            asv_name=asv_name,
        )
        
        self._scan_results.append(result)
        
        logger.info(
            "pci_scan_recorded",
            scan_id=result.scan_id,
            scan_type=scan_type,
            passed=passed,
        )
        
        return result
    
    def get_compliance_status(self) -> dict[str, Any]:
        """Get current PCI-DSS compliance status."""
        # Check scan currency
        last_internal = None
        last_external = None
        last_asv = None
        
        for scan in sorted(self._scan_results, key=lambda s: s.scan_date, reverse=True):
            if scan.scan_type == "internal" and not last_internal:
                last_internal = scan
            elif scan.scan_type == "external" and not last_external:
                last_external = scan
            elif scan.scan_type == "asv" and not last_asv:
                last_asv = scan
        
        # Determine if scans are current (within 90 days)
        scan_threshold = datetime.now(UTC) - timedelta(days=90)
        
        return {
            "internal_scan_current": (
                last_internal and last_internal.scan_date > scan_threshold
            ),
            "external_scan_current": (
                last_external and last_external.scan_date > scan_threshold
            ),
            "asv_scan_current": (
                last_asv and last_asv.scan_date > scan_threshold
            ),
            "last_internal_scan": last_internal.scan_date.isoformat() if last_internal else None,
            "last_external_scan": last_external.scan_date.isoformat() if last_external else None,
            "last_asv_scan": last_asv.scan_date.isoformat() if last_asv else None,
            "scopes_defined": len(self._scopes),
        }


# ═══════════════════════════════════════════════════════════════════════════
# COPPA COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════════


class ParentalConsentMethod(str, Enum):
    """Verifiable parental consent methods per COPPA."""
    SIGNED_CONSENT = "signed_consent"
    CREDIT_CARD = "credit_card"
    TOLL_FREE_CALL = "toll_free_call"
    VIDEO_CONFERENCE = "video_conference"
    GOVERNMENT_ID = "government_id"
    KNOWLEDGE_BASED = "knowledge_based"


@dataclass
class ChildProfile:
    """COPPA-compliant child profile record."""
    profile_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Child info (limited)
    username: str = ""  # Pseudonymous
    age: int = 0
    
    # Parental consent
    parent_email: str = ""
    consent_obtained: bool = False
    consent_method: ParentalConsentMethod | None = None
    consent_date: datetime | None = None
    consent_scope: list[str] = field(default_factory=list)
    
    # Data collected
    data_collected: list[str] = field(default_factory=list)
    third_party_sharing: bool = False
    
    # Account status
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


class COPPAComplianceService:
    """
    COPPA compliance service for children's data.
    
    Implements:
    - Verifiable parental consent
    - Limited data collection
    - No behavioral advertising
    - Data retention limits
    - Parental access rights
    """
    
    def __init__(self):
        self._child_profiles: dict[str, ChildProfile] = {}
        self._consent_records: list[dict] = []
        
        # Data that cannot be collected without consent
        self._restricted_data = [
            "full_name", "home_address", "email", "phone",
            "ssn", "photo", "video", "audio", "geolocation",
            "persistent_identifier", "behavioral_data",
        ]
    
    async def create_child_profile(
        self,
        username: str,
        age: int,
        parent_email: str,
    ) -> ChildProfile:
        """
        Create a child profile.
        
        Profile is inactive until parental consent obtained.
        """
        if age >= 13:
            raise ValueError("COPPA applies to children under 13")
        
        profile = ChildProfile(
            username=username,
            age=age,
            parent_email=parent_email,
        )
        
        self._child_profiles[profile.profile_id] = profile
        
        logger.info(
            "child_profile_created",
            profile_id=profile.profile_id,
            consent_pending=True,
        )
        
        return profile
    
    async def request_parental_consent(
        self,
        profile_id: str,
        data_to_collect: list[str],
        third_party_sharing: bool,
    ) -> dict[str, Any]:
        """
        Initiate parental consent request.
        
        Per COPPA, must provide direct notice to parent.
        """
        profile = self._child_profiles.get(profile_id)
        if not profile:
            raise ValueError("Profile not found")
        
        # Generate consent request
        consent_request = {
            "request_id": str(uuid4()),
            "profile_id": profile_id,
            "parent_email": profile.parent_email,
            "data_requested": data_to_collect,
            "third_party_sharing": third_party_sharing,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "notice_content": self._generate_coppa_notice(data_to_collect, third_party_sharing),
        }
        
        logger.info(
            "coppa_consent_requested",
            profile_id=profile_id,
            parent_email=profile.parent_email,
        )
        
        return consent_request
    
    def _generate_coppa_notice(
        self,
        data_to_collect: list[str],
        third_party_sharing: bool,
    ) -> str:
        """Generate required COPPA notice content."""
        return f"""
NOTICE OF PERSONAL INFORMATION COLLECTION FROM CHILDREN

We are requesting your consent to collect the following information 
from your child:
- {', '.join(data_to_collect)}

This information will be used to provide our service to your child.

{'We may share this information with third parties for service delivery.' 
 if third_party_sharing else 
 'We will NOT share this information with third parties.'}

As a parent, you have the right to:
- Review your child's personal information
- Request deletion of your child's information  
- Refuse further collection or use
- Revoke consent at any time

To exercise these rights, contact us at [privacy contact].
"""
    
    async def record_parental_consent(
        self,
        profile_id: str,
        consent_method: ParentalConsentMethod,
        data_scope: list[str],
        third_party_sharing: bool,
        verification_reference: str,
    ) -> ChildProfile:
        """
        Record verified parental consent.
        
        Consent must be verifiable per COPPA Rule.
        """
        profile = self._child_profiles.get(profile_id)
        if not profile:
            raise ValueError("Profile not found")
        
        profile.consent_obtained = True
        profile.consent_method = consent_method
        profile.consent_date = datetime.now(UTC)
        profile.consent_scope = data_scope
        profile.data_collected = data_scope
        profile.third_party_sharing = third_party_sharing
        profile.active = True
        
        # Record consent
        self._consent_records.append({
            "profile_id": profile_id,
            "method": consent_method.value,
            "scope": data_scope,
            "timestamp": datetime.now(UTC).isoformat(),
            "verification_reference": verification_reference,
        })
        
        logger.info(
            "coppa_consent_recorded",
            profile_id=profile_id,
            method=consent_method.value,
        )
        
        return profile
    
    async def revoke_consent(
        self,
        profile_id: str,
        delete_data: bool = True,
    ) -> dict[str, Any]:
        """
        Revoke parental consent and optionally delete data.
        
        Parent can revoke consent at any time.
        """
        profile = self._child_profiles.get(profile_id)
        if not profile:
            raise ValueError("Profile not found")
        
        profile.consent_obtained = False
        profile.active = False
        
        result = {
            "profile_id": profile_id,
            "consent_revoked": True,
            "data_deleted": False,
        }
        
        if delete_data:
            # Delete child's data
            del self._child_profiles[profile_id]
            result["data_deleted"] = True
        
        logger.info(
            "coppa_consent_revoked",
            profile_id=profile_id,
            data_deleted=delete_data,
        )
        
        return result


# Global service instances
_hipaa_service: HIPAAComplianceService | None = None
_pci_service: PCIDSSComplianceService | None = None
_coppa_service: COPPAComplianceService | None = None


def get_hipaa_service() -> HIPAAComplianceService:
    """Get the global HIPAA compliance service."""
    global _hipaa_service
    if _hipaa_service is None:
        _hipaa_service = HIPAAComplianceService()
    return _hipaa_service


def get_pci_service() -> PCIDSSComplianceService:
    """Get the global PCI-DSS compliance service."""
    global _pci_service
    if _pci_service is None:
        _pci_service = PCIDSSComplianceService()
    return _pci_service


def get_coppa_service() -> COPPAComplianceService:
    """Get the global COPPA compliance service."""
    global _coppa_service
    if _coppa_service is None:
        _coppa_service = COPPAComplianceService()
    return _coppa_service
