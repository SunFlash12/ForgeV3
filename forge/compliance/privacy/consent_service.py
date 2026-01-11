"""
Forge Compliance Framework - Consent Management Service

Comprehensive consent management implementing:
- GDPR Article 7 (Conditions for consent)
- CCPA/CPRA opt-out rights
- IAB TCF 2.2 (Transparency & Consent Framework)
- Global Privacy Control (GPC) signal handling
- ePrivacy Directive (cookie consent)

Features:
- Granular purpose-based consent
- Consent versioning and audit trail
- Preference center management
- TCF string encoding/decoding
- Cross-device consent sync
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import Jurisdiction

logger = structlog.get_logger(__name__)


class ConsentPurpose(str, Enum):
    """Standard consent purposes (IAB TCF 2.2 aligned)."""
    # TCF Standard Purposes
    STORE_ACCESS = "store_access"  # Purpose 1
    BASIC_ADS = "basic_ads"  # Purpose 2
    PERSONALIZED_ADS = "personalized_ads"  # Purpose 3
    AD_MEASUREMENT = "ad_measurement"  # Purpose 4
    CONTENT_PERSONALIZATION = "content_personalization"  # Purpose 5
    CONTENT_MEASUREMENT = "content_measurement"  # Purpose 6
    MARKET_RESEARCH = "market_research"  # Purpose 7
    PRODUCT_DEVELOPMENT = "product_development"  # Purpose 8
    PERSONALIZED_CONTENT = "personalized_content"  # Purpose 9
    AD_PERFORMANCE = "ad_performance"  # Purpose 10
    
    # Special Purposes (no consent needed, legitimate interest)
    SECURITY = "security"
    DELIVERY = "delivery"
    
    # Custom Forge purposes
    AI_TRAINING = "ai_training"
    AI_PROCESSING = "ai_processing"
    ANALYTICS = "analytics"
    MARKETING_EMAIL = "marketing_email"
    MARKETING_SMS = "marketing_sms"
    THIRD_PARTY_SHARING = "third_party_sharing"
    DATA_SALE = "data_sale"  # CCPA specific
    CROSS_CONTEXT_ADVERTISING = "cross_context_advertising"  # CPRA specific
    SENSITIVE_DATA_PROCESSING = "sensitive_data_processing"
    PROFILING = "profiling"
    AUTOMATED_DECISIONS = "automated_decisions"


class ConsentStatus(str, Enum):
    """Consent status values."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"


class ConsentSource(str, Enum):
    """Source of consent collection."""
    CONSENT_BANNER = "consent_banner"
    PREFERENCE_CENTER = "preference_center"
    SIGNUP_FORM = "signup_form"
    ACCOUNT_SETTINGS = "account_settings"
    API = "api"
    GPC_SIGNAL = "gpc_signal"
    DO_NOT_SELL_LINK = "do_not_sell_link"
    OFFLINE = "offline"
    IMPORTED = "imported"


class LegalBasis(str, Enum):
    """Legal basis for processing (GDPR Article 6)."""
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTEREST = "legitimate_interest"


@dataclass
class ConsentRecord:
    """Individual consent record for a specific purpose."""
    record_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    purpose: ConsentPurpose = ConsentPurpose.ANALYTICS
    
    # Status
    status: ConsentStatus = ConsentStatus.PENDING
    granted_at: datetime | None = None
    denied_at: datetime | None = None
    withdrawn_at: datetime | None = None
    
    # Collection context
    source: ConsentSource = ConsentSource.CONSENT_BANNER
    jurisdiction: Jurisdiction = Jurisdiction.GLOBAL
    legal_basis: LegalBasis = LegalBasis.CONSENT
    
    # Consent details
    consent_text_version: str = ""
    consent_text_hash: str = ""
    collected_via: str = ""  # Banner version, form ID, etc.
    
    # IAB TCF
    tcf_purpose_id: int | None = None
    tcf_vendor_consents: list[int] = field(default_factory=list)
    
    # Audit
    ip_address: str = ""
    user_agent: str = ""
    
    @property
    def is_valid(self) -> bool:
        """Check if consent is currently valid."""
        return self.status == ConsentStatus.GRANTED
    
    @property
    def timestamp(self) -> datetime | None:
        """Get the timestamp when consent was recorded (granted, denied, or withdrawn)."""
        if self.granted_at:
            return self.granted_at
        elif self.denied_at:
            return self.denied_at
        elif self.withdrawn_at:
            return self.withdrawn_at
        return None


@dataclass
class ConsentPreferences:
    """User's complete consent preferences."""
    preferences_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    
    # Purpose consents
    purposes: dict[str, ConsentStatus] = field(default_factory=dict)
    
    # Global flags
    gpc_enabled: bool = False  # Global Privacy Control
    do_not_sell: bool = False  # CCPA opt-out
    do_not_share: bool = False  # CPRA opt-out
    limit_sensitive_data: bool = False  # CPRA sensitive PI
    
    # TCF String
    tcf_string: str | None = None
    tcf_version: int = 2
    
    # Metadata
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    update_count: int = 0
    
    # Version tracking
    policy_version: str = ""
    preferences_version: int = 1


@dataclass
class ConsentTransaction:
    """Audit record of consent change."""
    transaction_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Change details
    action: str = ""  # grant, deny, withdraw, update
    purposes_affected: list[str] = field(default_factory=list)
    previous_status: dict[str, str] = field(default_factory=dict)
    new_status: dict[str, str] = field(default_factory=dict)
    
    # Context
    source: ConsentSource = ConsentSource.CONSENT_BANNER
    ip_address: str = ""
    user_agent: str = ""


@dataclass
class ConsentPolicy:
    """Consent policy configuration."""
    policy_id: str = field(default_factory=lambda: str(uuid4()))
    version: str = "1.0"
    effective_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    # Required purposes (cannot be opted out)
    required_purposes: list[ConsentPurpose] = field(default_factory=list)
    
    # Optional purposes (require consent)
    optional_purposes: list[ConsentPurpose] = field(default_factory=list)
    
    # Legitimate interest purposes
    legitimate_interest_purposes: list[ConsentPurpose] = field(default_factory=list)
    
    # Jurisdiction-specific rules
    jurisdiction_rules: dict[str, dict] = field(default_factory=dict)
    
    # Consent text
    consent_texts: dict[str, str] = field(default_factory=dict)


class ConsentManagementService:
    """
    Comprehensive consent management platform.
    
    Implements GDPR, CCPA/CPRA, and IAB TCF 2.2 requirements.
    """
    
    def __init__(self):
        self._preferences: dict[str, ConsentPreferences] = {}
        self._records: dict[str, list[ConsentRecord]] = {}  # user_id -> records
        self._transactions: list[ConsentTransaction] = []
        self._policies: dict[str, ConsentPolicy] = {}
        
        # Initialize default policy
        self._active_policy = self._create_default_policy()
        self._policies[self._active_policy.policy_id] = self._active_policy
    
    def _create_default_policy(self) -> ConsentPolicy:
        """Create default consent policy."""
        return ConsentPolicy(
            version="1.0",
            required_purposes=[
                ConsentPurpose.SECURITY,
                ConsentPurpose.DELIVERY,
            ],
            optional_purposes=[
                ConsentPurpose.ANALYTICS,
                ConsentPurpose.PERSONALIZED_ADS,
                ConsentPurpose.MARKETING_EMAIL,
                ConsentPurpose.AI_TRAINING,
                ConsentPurpose.AI_PROCESSING,
                ConsentPurpose.THIRD_PARTY_SHARING,
                ConsentPurpose.PROFILING,
            ],
            legitimate_interest_purposes=[
                ConsentPurpose.PRODUCT_DEVELOPMENT,
                ConsentPurpose.MARKET_RESEARCH,
            ],
            jurisdiction_rules={
                "eu": {
                    "default_consent": False,
                    "explicit_consent_required": True,
                    "granular_consent": True,
                },
                "us_ca": {
                    "default_consent": True,  # Opt-out model
                    "do_not_sell_required": True,
                    "limit_sensitive_required": True,
                },
                "br": {
                    "default_consent": False,
                    "explicit_consent_required": True,
                },
            },
        )
    
    # ───────────────────────────────────────────────────────────────
    # CONSENT COLLECTION
    # ───────────────────────────────────────────────────────────────
    
    async def record_consent(
        self,
        user_id: str,
        purpose: ConsentPurpose,
        granted: bool,
        source: ConsentSource,
        jurisdiction: Jurisdiction,
        consent_text_version: str = "",
        ip_address: str = "",
        user_agent: str = "",
        tcf_string: str | None = None,
    ) -> ConsentRecord:
        """
        Record a consent decision.
        
        Per GDPR Article 7 - requires demonstrable consent.
        """
        # Determine legal basis
        if purpose in self._active_policy.required_purposes:
            legal_basis = LegalBasis.CONTRACT
        elif purpose in self._active_policy.legitimate_interest_purposes:
            legal_basis = LegalBasis.LEGITIMATE_INTEREST
        else:
            legal_basis = LegalBasis.CONSENT
        
        # Create consent record
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            user_id=user_id,
            purpose=purpose,
            status=ConsentStatus.GRANTED if granted else ConsentStatus.DENIED,
            granted_at=now if granted else None,
            denied_at=now if not granted else None,
            source=source,
            jurisdiction=jurisdiction,
            legal_basis=legal_basis,
            consent_text_version=consent_text_version,
            consent_text_hash=hashlib.sha256(consent_text_version.encode()).hexdigest()[:16],
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Store record
        if user_id not in self._records:
            self._records[user_id] = []
        self._records[user_id].append(record)
        
        # Update preferences
        await self._update_preferences(user_id, purpose, record.status)
        
        # Log transaction
        self._log_transaction(
            user_id=user_id,
            action="grant" if granted else "deny",
            purposes=[purpose.value],
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            "consent_recorded",
            user_id=user_id,
            purpose=purpose.value,
            granted=granted,
        )
        
        return record
    
    async def record_bulk_consent(
        self,
        user_id: str,
        consents: dict[ConsentPurpose, bool],
        source: ConsentSource,
        jurisdiction: Jurisdiction,
        consent_text_version: str = "",
        ip_address: str = "",
        user_agent: str = "",
        tcf_string: str | None = None,
    ) -> list[ConsentRecord]:
        """Record multiple consent decisions at once."""
        records = []
        
        for purpose, granted in consents.items():
            record = await self.record_consent(
                user_id=user_id,
                purpose=purpose,
                granted=granted,
                source=source,
                jurisdiction=jurisdiction,
                consent_text_version=consent_text_version,
                ip_address=ip_address,
                user_agent=user_agent,
                tcf_string=tcf_string,
            )
            records.append(record)
        
        # Store TCF string if provided
        if tcf_string:
            prefs = await self.get_preferences(user_id)
            prefs.tcf_string = tcf_string
        
        return records
    
    async def withdraw_consent(
        self,
        user_id: str,
        purpose: ConsentPurpose,
        source: ConsentSource = ConsentSource.PREFERENCE_CENTER,
        ip_address: str = "",
        user_agent: str = "",
    ) -> ConsentRecord:
        """
        Withdraw previously granted consent.
        
        Per GDPR Article 7(3) - withdrawal must be as easy as giving consent.
        """
        # Create withdrawal record
        record = ConsentRecord(
            user_id=user_id,
            purpose=purpose,
            status=ConsentStatus.WITHDRAWN,
            withdrawn_at=datetime.now(UTC),
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Store record
        if user_id not in self._records:
            self._records[user_id] = []
        self._records[user_id].append(record)
        
        # Update preferences
        await self._update_preferences(user_id, purpose, ConsentStatus.WITHDRAWN)
        
        # Log transaction
        self._log_transaction(
            user_id=user_id,
            action="withdraw",
            purposes=[purpose.value],
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        logger.info(
            "consent_withdrawn",
            user_id=user_id,
            purpose=purpose.value,
        )
        
        return record
    
    # ───────────────────────────────────────────────────────────────
    # GPC / DO NOT SELL HANDLING
    # ───────────────────────────────────────────────────────────────
    
    async def process_gpc_signal(
        self,
        user_id: str,
        gpc_enabled: bool,
        ip_address: str = "",
        user_agent: str = "",
    ) -> ConsentPreferences:
        """
        Process Global Privacy Control (GPC) signal.
        
        Per CCPA regulations, GPC is a valid opt-out signal.
        """
        prefs = await self.get_preferences(user_id)
        prefs.gpc_enabled = gpc_enabled
        
        if gpc_enabled:
            # GPC implies opt-out of sale/sharing
            prefs.do_not_sell = True
            prefs.do_not_share = True
            
            # Opt out of relevant purposes
            opt_out_purposes = [
                ConsentPurpose.DATA_SALE,
                ConsentPurpose.THIRD_PARTY_SHARING,
                ConsentPurpose.CROSS_CONTEXT_ADVERTISING,
                ConsentPurpose.PERSONALIZED_ADS,
            ]
            
            for purpose in opt_out_purposes:
                prefs.purposes[purpose.value] = ConsentStatus.DENIED.value
                
                # Record the opt-out
                await self.record_consent(
                    user_id=user_id,
                    purpose=purpose,
                    granted=False,
                    source=ConsentSource.GPC_SIGNAL,
                    jurisdiction=Jurisdiction.US_CALIFORNIA,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        
        prefs.last_updated = datetime.now(UTC)
        prefs.update_count += 1
        
        logger.info(
            "gpc_signal_processed",
            user_id=user_id,
            gpc_enabled=gpc_enabled,
        )
        
        return prefs
    
    async def process_do_not_sell(
        self,
        user_id: str,
        opt_out: bool = True,
        ip_address: str = "",
        user_agent: str = "",
    ) -> ConsentPreferences:
        """
        Process "Do Not Sell My Personal Information" request.
        
        Per CCPA §1798.120.
        """
        prefs = await self.get_preferences(user_id)
        prefs.do_not_sell = opt_out
        
        if opt_out:
            # Record opt-out
            await self.record_consent(
                user_id=user_id,
                purpose=ConsentPurpose.DATA_SALE,
                granted=False,
                source=ConsentSource.DO_NOT_SELL_LINK,
                jurisdiction=Jurisdiction.US_CALIFORNIA,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        
        prefs.last_updated = datetime.now(UTC)
        
        logger.info(
            "do_not_sell_processed",
            user_id=user_id,
            opt_out=opt_out,
        )
        
        return prefs
    
    async def process_limit_sensitive_data(
        self,
        user_id: str,
        limit: bool = True,
        ip_address: str = "",
        user_agent: str = "",
    ) -> ConsentPreferences:
        """
        Process "Limit the Use of My Sensitive Personal Information" request.
        
        Per CPRA §1798.121.
        """
        prefs = await self.get_preferences(user_id)
        prefs.limit_sensitive_data = limit
        
        if limit:
            await self.record_consent(
                user_id=user_id,
                purpose=ConsentPurpose.SENSITIVE_DATA_PROCESSING,
                granted=False,
                source=ConsentSource.PREFERENCE_CENTER,
                jurisdiction=Jurisdiction.US_CALIFORNIA,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        
        prefs.last_updated = datetime.now(UTC)
        
        logger.info(
            "limit_sensitive_processed",
            user_id=user_id,
            limit=limit,
        )
        
        return prefs
    
    # ───────────────────────────────────────────────────────────────
    # CONSENT CHECKING
    # ───────────────────────────────────────────────────────────────
    
    async def check_consent(
        self,
        user_id: str,
        purpose: ConsentPurpose,
        jurisdiction: Jurisdiction | None = None,
    ) -> tuple[bool, str]:
        """
        Check if user has consented to a specific purpose.
        
        Returns (has_consent, reason).
        """
        prefs = await self.get_preferences(user_id)
        
        # Check if purpose requires consent
        if purpose in self._active_policy.required_purposes:
            return True, "Required for service delivery"
        
        # Check GPC/Do Not Sell for relevant purposes
        if purpose in {
            ConsentPurpose.DATA_SALE,
            ConsentPurpose.THIRD_PARTY_SHARING,
            ConsentPurpose.CROSS_CONTEXT_ADVERTISING,
        }:
            if prefs.gpc_enabled or prefs.do_not_sell:
                return False, "Opted out via GPC/Do Not Sell"
        
        if purpose == ConsentPurpose.SENSITIVE_DATA_PROCESSING:
            if prefs.limit_sensitive_data:
                return False, "Opted out of sensitive data processing"
        
        # Check purpose-specific consent
        status = prefs.purposes.get(purpose.value)
        
        if status == ConsentStatus.GRANTED.value:
            return True, "Consent granted"
        elif status == ConsentStatus.DENIED.value:
            return False, "Consent denied"
        elif status == ConsentStatus.WITHDRAWN.value:
            return False, "Consent withdrawn"
        
        # Check legitimate interest
        if purpose in self._active_policy.legitimate_interest_purposes:
            # Check for objection
            if status != ConsentStatus.DENIED.value:
                return True, "Legitimate interest (no objection)"
        
        # Default based on jurisdiction
        if jurisdiction:
            rules = self._active_policy.jurisdiction_rules.get(jurisdiction.value, {})
            default = rules.get("default_consent", False)
            if default:
                return True, "Default consent (opt-out jurisdiction)"
        
        return False, "No consent recorded"
    
    async def check_multiple_consents(
        self,
        user_id: str,
        purposes: list[ConsentPurpose],
    ) -> dict[str, tuple[bool, str]]:
        """Check consent for multiple purposes at once."""
        results = {}
        for purpose in purposes:
            has_consent, reason = await self.check_consent(user_id, purpose)
            results[purpose.value] = (has_consent, reason)
        return results
    
    # ───────────────────────────────────────────────────────────────
    # PREFERENCES MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    async def get_preferences(self, user_id: str) -> ConsentPreferences:
        """Get user's consent preferences."""
        if user_id not in self._preferences:
            self._preferences[user_id] = ConsentPreferences(
                user_id=user_id,
                policy_version=self._active_policy.version,
            )
        return self._preferences[user_id]
    
    async def _update_preferences(
        self,
        user_id: str,
        purpose: ConsentPurpose,
        status: ConsentStatus,
    ) -> None:
        """Update user preferences with new consent status."""
        prefs = await self.get_preferences(user_id)
        prefs.purposes[purpose.value] = status.value
        prefs.last_updated = datetime.now(UTC)
        prefs.update_count += 1
    
    async def get_consent_history(
        self,
        user_id: str,
        purpose: ConsentPurpose | None = None,
    ) -> list[ConsentRecord]:
        """Get consent history for a user."""
        records = self._records.get(user_id, [])
        
        if purpose:
            records = [r for r in records if r.purpose == purpose]
        
        return sorted(records, key=lambda r: r.granted_at or r.denied_at or datetime.min, reverse=True)
    
    # ───────────────────────────────────────────────────────────────
    # TCF STRING HANDLING
    # ───────────────────────────────────────────────────────────────
    
    def decode_tcf_string(self, tcf_string: str) -> dict[str, Any]:
        """
        Decode IAB TCF 2.2 consent string.
        
        Note: Simplified implementation. Production should use 
        official TCF SDK.
        """
        try:
            # TCF string is base64url encoded
            # This is a simplified decoder
            decoded = {
                "version": 2,
                "created": datetime.now(UTC).isoformat(),
                "last_updated": datetime.now(UTC).isoformat(),
                "cmp_id": 0,
                "cmp_version": 0,
                "consent_screen": 0,
                "consent_language": "EN",
                "vendor_list_version": 0,
                "policy_version": 2,
                "is_service_specific": False,
                "use_non_standard_stacks": False,
                "purpose_consents": {},
                "purpose_legitimate_interests": {},
                "vendor_consents": {},
                "vendor_legitimate_interests": {},
            }
            
            # Parse the actual TCF string here
            # For now, return placeholder structure
            
            return decoded
            
        except Exception as e:
            logger.error("tcf_decode_error", error=str(e))
            return {}
    
    def encode_tcf_string(
        self,
        purpose_consents: dict[int, bool],
        vendor_consents: dict[int, bool],
        cmp_id: int = 1,
    ) -> str:
        """
        Encode consent choices as IAB TCF 2.2 string.
        
        Note: Simplified implementation.
        """
        # Production implementation would use official TCF encoder
        # This returns a placeholder
        data = {
            "v": 2,
            "purposes": purpose_consents,
            "vendors": vendor_consents,
            "cmp": cmp_id,
            "ts": int(datetime.now(UTC).timestamp()),
        }
        
        # Base64url encode
        json_str = json.dumps(data)
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
        
        return f"CP{encoded}"
    
    # ───────────────────────────────────────────────────────────────
    # AUDIT / REPORTING
    # ───────────────────────────────────────────────────────────────
    
    def _log_transaction(
        self,
        user_id: str,
        action: str,
        purposes: list[str],
        source: ConsentSource,
        ip_address: str = "",
        user_agent: str = "",
    ) -> ConsentTransaction:
        """Log consent transaction for audit."""
        transaction = ConsentTransaction(
            user_id=user_id,
            action=action,
            purposes_affected=purposes,
            source=source,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self._transactions.append(transaction)
        
        return transaction
    
    def get_consent_metrics(self) -> dict[str, Any]:
        """Get consent metrics for reporting."""
        total_users = len(self._preferences)
        
        # Count by purpose
        purpose_counts = {}
        for prefs in self._preferences.values():
            for purpose, status in prefs.purposes.items():
                if purpose not in purpose_counts:
                    purpose_counts[purpose] = {"granted": 0, "denied": 0, "withdrawn": 0}
                if status == ConsentStatus.GRANTED.value:
                    purpose_counts[purpose]["granted"] += 1
                elif status == ConsentStatus.DENIED.value:
                    purpose_counts[purpose]["denied"] += 1
                elif status == ConsentStatus.WITHDRAWN.value:
                    purpose_counts[purpose]["withdrawn"] += 1
        
        # GPC / Do Not Sell counts
        gpc_count = sum(1 for p in self._preferences.values() if p.gpc_enabled)
        dns_count = sum(1 for p in self._preferences.values() if p.do_not_sell)
        
        return {
            "total_users_with_preferences": total_users,
            "gpc_enabled_count": gpc_count,
            "do_not_sell_count": dns_count,
            "purpose_breakdown": purpose_counts,
            "transactions_total": len(self._transactions),
        }
    
    async def export_consent_proof(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Export consent proof for regulatory compliance.
        
        Per GDPR requirement to demonstrate consent.
        """
        prefs = await self.get_preferences(user_id)
        records = self._records.get(user_id, [])
        
        return {
            "user_id": user_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "current_preferences": {
                "purposes": prefs.purposes,
                "gpc_enabled": prefs.gpc_enabled,
                "do_not_sell": prefs.do_not_sell,
                "do_not_share": prefs.do_not_share,
                "limit_sensitive_data": prefs.limit_sensitive_data,
                "tcf_string": prefs.tcf_string,
                "policy_version": prefs.policy_version,
                "last_updated": prefs.last_updated.isoformat(),
            },
            "consent_records": [
                {
                    "record_id": r.record_id,
                    "purpose": r.purpose.value,
                    "status": r.status.value,
                    "timestamp": (r.granted_at or r.denied_at or r.withdrawn_at).isoformat() if (r.granted_at or r.denied_at or r.withdrawn_at) else None,
                    "source": r.source.value,
                    "jurisdiction": r.jurisdiction.value,
                    "legal_basis": r.legal_basis.value,
                    "consent_text_version": r.consent_text_version,
                }
                for r in records
            ],
        }


# Global service instance
_consent_service: ConsentManagementService | None = None


def get_consent_service() -> ConsentManagementService:
    """Get the global consent management service."""
    global _consent_service
    if _consent_service is None:
        _consent_service = ConsentManagementService()
    return _consent_service
