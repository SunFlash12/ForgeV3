"""
Forge Compliance Framework - Compliance Engine

Central orchestration engine for all compliance operations including:
- Control verification
- DSAR processing
- Consent management
- Breach notification
- Audit logging
- Reporting
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

import structlog

from forge.compliance.core.config import ComplianceConfig, get_compliance_config
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
)
from forge.compliance.core.models import (
    ComplianceStatus,
    ControlStatus,
    AuditEvent,
    DataSubjectRequest,
    ConsentRecord,
    BreachNotification,
    ComplianceReport,
    AISystemRegistration,
    AIDecisionLog,
    RegulatoryNotification,
    AffectedIndividual,
)
from forge.compliance.core.registry import ComplianceRegistry, get_compliance_registry

logger = structlog.get_logger(__name__)


class ComplianceEngine:
    """
    Central compliance orchestration engine.
    
    Manages all compliance operations and provides a unified interface
    for the Forge system to interact with compliance requirements.
    """
    
    def __init__(
        self,
        config: ComplianceConfig | None = None,
        registry: ComplianceRegistry | None = None,
        repository: "ComplianceRepository | None" = None,
    ):
        self.config = config or get_compliance_config()
        self.registry = registry or get_compliance_registry()

        # PERSISTENCE FIX: Use ComplianceRepository for Neo4j persistence
        # The repository provides persistence for all compliance data required
        # by regulatory retention requirements:
        #   - GDPR: Consent records for duration of processing + 7 years
        #   - SOX: Audit logs for 7 years minimum
        #   - HIPAA: 6 years for audit trails
        self._repository = repository
        self._persistence_enabled = repository is not None

        # In-memory caches (backed by database when repository is available)
        self._dsars: dict[str, DataSubjectRequest] = {}
        self._consents: dict[str, list[ConsentRecord]] = {}  # user_id -> consents
        self._breaches: dict[str, BreachNotification] = {}
        self._audit_events: list[AuditEvent] = []
        self._ai_systems: dict[str, AISystemRegistration] = {}
        self._ai_decisions: list[AIDecisionLog] = []

        # Last event hash for chain integrity
        self._last_audit_hash: str | None = None

        # Event handlers
        self._event_handlers: dict[str, list[Callable]] = {}

        logger.info(
            "compliance_engine_initialized",
            jurisdictions=len(self.config.jurisdictions_list),
            frameworks=len(self.config.frameworks_list),
            controls=self.registry.get_control_count(),
            persistence_enabled=self._persistence_enabled,
        )

    async def initialize_persistence(self) -> None:
        """
        Initialize persistence layer and load existing data.

        Call this after engine creation when repository is available.
        """
        if not self._repository:
            logger.warning("compliance_persistence_disabled", reason="No repository provided")
            return

        try:
            await self._repository.initialize()

            # Load last audit hash for chain integrity
            self._last_audit_hash = await self._repository.get_last_audit_hash()

            logger.info(
                "compliance_persistence_initialized",
                last_audit_hash=self._last_audit_hash[:16] if self._last_audit_hash else None,
            )
        except Exception as e:
            logger.error("compliance_persistence_init_failed", error=str(e))
            raise

    def set_repository(self, repository: "ComplianceRepository") -> None:
        """Set the repository for persistence (for dependency injection)."""
        self._repository = repository
        self._persistence_enabled = True
        logger.info("compliance_repository_set")
    
    # ═══════════════════════════════════════════════════════════════
    # AUDIT LOGGING
    # ═══════════════════════════════════════════════════════════════
    
    async def log_event(
        self,
        category: AuditEventCategory,
        event_type: str,
        action: str,
        actor_id: str | None = None,
        actor_type: str = "user",
        entity_type: str | None = None,
        entity_id: str | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
        risk_level: RiskLevel = RiskLevel.INFO,
        data_classification: DataClassification | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """
        Log an audit event with cryptographic integrity.
        
        All compliance-relevant events should be logged through this method.
        """
        # Create event
        event = AuditEvent(
            category=category,
            event_type=event_type,
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            entity_type=entity_type or "unknown",
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            success=success,
            error_message=error_message,
            risk_level=risk_level,
            data_classification=data_classification,
            correlation_id=correlation_id or str(uuid4()),
            previous_hash=self._last_audit_hash,
        )
        
        # Calculate hash for chain integrity
        if self.config.audit_immutable:
            event_data = json.dumps({
                "id": event.id,
                "category": event.category.value if hasattr(event.category, 'value') else event.category,
                "event_type": event.event_type,
                "action": event.action,
                "timestamp": event.created_at.isoformat(),
                "previous_hash": event.previous_hash,
            }, sort_keys=True)
            event.hash = hashlib.sha256(event_data.encode()).hexdigest()
            self._last_audit_hash = event.hash
        
        # Store event in memory cache
        self._audit_events.append(event)

        # PERSISTENCE FIX: Persist to database (append-only)
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_audit_event({
                    "id": event.id,
                    "category": event.category,
                    "event_type": event.event_type,
                    "action": event.action,
                    "actor_id": event.actor_id,
                    "actor_type": event.actor_type,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "old_value": event.old_value,
                    "new_value": event.new_value,
                    "success": event.success,
                    "error_message": event.error_message,
                    "risk_level": event.risk_level,
                    "data_classification": event.data_classification,
                    "correlation_id": event.correlation_id,
                    "previous_hash": event.previous_hash,
                    "hash": event.hash,
                })
            except Exception as e:
                logger.error("audit_event_persistence_failed", event_id=event.id, error=str(e))

        # Log to structlog
        log_method = getattr(logger, risk_level.value if hasattr(risk_level, 'value') else risk_level)
        log_method(
            "audit_event",
            event_id=event.id,
            category=category.value if hasattr(category, 'value') else category,
            event_type=event_type,
            action=action,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            success=success,
        )

        # Notify handlers
        await self._notify_handlers("audit_event", event)

        return event
    
    async def get_audit_events(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        category: AuditEventCategory | None = None,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        events = self._audit_events
        
        if start_date:
            events = [e for e in events if e.created_at >= start_date]
        if end_date:
            events = [e for e in events if e.created_at <= end_date]
        if category:
            events = [e for e in events if e.category == category]
        if actor_id:
            events = [e for e in events if e.actor_id == actor_id]
        if entity_type:
            events = [e for e in events if e.entity_type == entity_type]
        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]
        
        return events[-limit:]
    
    def verify_audit_chain(self) -> tuple[bool, str]:
        """Verify audit log chain integrity."""
        if not self._audit_events:
            return True, "No events to verify"
        
        previous_hash = None
        for event in self._audit_events:
            # Verify previous hash pointer
            if event.previous_hash != previous_hash:
                return False, f"Chain broken at event {event.id}"
            
            # Verify hash calculation
            event_data = json.dumps({
                "id": event.id,
                "category": event.category.value if hasattr(event.category, 'value') else event.category,
                "event_type": event.event_type,
                "action": event.action,
                "timestamp": event.created_at.isoformat(),
                "previous_hash": event.previous_hash,
            }, sort_keys=True)
            calculated_hash = hashlib.sha256(event_data.encode()).hexdigest()
            
            if event.hash != calculated_hash:
                return False, f"Hash mismatch at event {event.id}"
            
            previous_hash = event.hash
        
        return True, f"Chain verified: {len(self._audit_events)} events"
    
    # ═══════════════════════════════════════════════════════════════
    # DATA SUBJECT REQUESTS (DSAR)
    # ═══════════════════════════════════════════════════════════════
    
    async def create_dsar(
        self,
        request_type: DSARType,
        subject_email: str,
        request_text: str,
        subject_id: str | None = None,
        subject_name: str | None = None,
        jurisdiction: Jurisdiction | None = None,
        specific_data_categories: list[str] | None = None,
    ) -> DataSubjectRequest:
        """
        Create a new Data Subject Access Request.
        
        Automatically determines jurisdiction and applicable frameworks
        based on configuration and calculates appropriate deadline.
        """
        # Auto-detect jurisdiction if not provided
        if not jurisdiction:
            jurisdiction = self.config.primary_jurisdiction
        
        # Determine applicable frameworks
        applicable_frameworks = []
        if jurisdiction in {Jurisdiction.EU, Jurisdiction.UK, Jurisdiction.GERMANY, Jurisdiction.FRANCE}:
            applicable_frameworks.append(ComplianceFramework.GDPR)
        if jurisdiction in {Jurisdiction.US_CALIFORNIA}:
            applicable_frameworks.extend([ComplianceFramework.CCPA, ComplianceFramework.CPRA])
        if jurisdiction == Jurisdiction.BRAZIL:
            applicable_frameworks.append(ComplianceFramework.LGPD)
        if jurisdiction == Jurisdiction.CHINA:
            applicable_frameworks.append(ComplianceFramework.PIPL)
        
        # Create DSAR
        dsar = DataSubjectRequest(
            request_type=request_type,
            jurisdiction=jurisdiction,
            applicable_frameworks=applicable_frameworks,
            subject_id=subject_id,
            subject_email=subject_email,
            subject_name=subject_name,
            request_text=request_text,
            specific_data_categories=specific_data_categories or [],
            status="received",
        )
        
        # Auto-verify if internal user
        if subject_id and self.config.dsar_auto_verify_internal:
            dsar.verified = True
            dsar.status = "verified"

        # Store in memory cache
        self._dsars[dsar.id] = dsar

        # PERSISTENCE FIX: Persist to database
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_dsar({
                    "id": dsar.id,
                    "request_type": request_type.value,
                    "jurisdiction": jurisdiction.value,
                    "applicable_frameworks": [f.value for f in applicable_frameworks],
                    "subject_id": subject_id,
                    "subject_email": subject_email,
                    "subject_name": subject_name,
                    "request_text": request_text,
                    "specific_data_categories": specific_data_categories or [],
                    "status": dsar.status,
                    "verified": dsar.verified,
                    "deadline": dsar.deadline,
                    "assigned_to": dsar.assigned_to,
                    "processing_notes": [],
                })
            except Exception as e:
                logger.error("dsar_persistence_failed", dsar_id=dsar.id, error=str(e))

        # Log
        await self.log_event(
            category=AuditEventCategory.PRIVACY,
            event_type="dsar_created",
            action="CREATE",
            entity_type="DataSubjectRequest",
            entity_id=dsar.id,
            new_value={"type": request_type.value, "subject_email": subject_email},
            risk_level=RiskLevel.INFO,
        )
        
        logger.info(
            "dsar_created",
            dsar_id=dsar.id,
            request_type=request_type.value,
            jurisdiction=jurisdiction.value,
            deadline=dsar.deadline.isoformat() if dsar.deadline else None,
        )
        
        return dsar
    
    async def process_dsar(
        self,
        dsar_id: str,
        actor_id: str,
    ) -> DataSubjectRequest:
        """Mark DSAR as processing."""
        dsar = self._dsars.get(dsar_id)
        if not dsar:
            raise ValueError(f"DSAR not found: {dsar_id}")
        
        dsar.status = "processing"
        dsar.assigned_to = actor_id
        dsar.updated_at = datetime.utcnow()
        dsar.add_processing_note("Started processing", actor_id)
        
        await self.log_event(
            category=AuditEventCategory.PRIVACY,
            event_type="dsar_processing",
            action="UPDATE",
            actor_id=actor_id,
            entity_type="DataSubjectRequest",
            entity_id=dsar_id,
        )
        
        return dsar
    
    async def complete_dsar(
        self,
        dsar_id: str,
        actor_id: str,
        export_location: str | None = None,
        export_format: str = "JSON",
        erasure_exceptions: list[str] | None = None,
    ) -> DataSubjectRequest:
        """Complete a DSAR."""
        dsar = self._dsars.get(dsar_id)
        if not dsar:
            raise ValueError(f"DSAR not found: {dsar_id}")
        
        dsar.status = "completed"
        dsar.response_sent_at = datetime.utcnow()
        dsar.updated_at = datetime.utcnow()
        
        if dsar.request_type == DSARType.ACCESS or dsar.request_type == DSARType.PORTABILITY:
            dsar.data_exported = True
            dsar.export_format = export_format
            dsar.export_location = export_location
        elif dsar.request_type == DSARType.ERASURE:
            dsar.erasure_completed = True
            dsar.erasure_exceptions = erasure_exceptions or []
        
        dsar.add_processing_note("Completed", actor_id)
        
        await self.log_event(
            category=AuditEventCategory.PRIVACY,
            event_type="dsar_completed",
            action="UPDATE",
            actor_id=actor_id,
            entity_type="DataSubjectRequest",
            entity_id=dsar_id,
            risk_level=RiskLevel.INFO,
        )
        
        logger.info(
            "dsar_completed",
            dsar_id=dsar_id,
            request_type=dsar.request_type.value,
            days_to_complete=(datetime.utcnow() - dsar.received_at).days,
        )
        
        return dsar
    
    async def get_overdue_dsars(self) -> list[DataSubjectRequest]:
        """Get all overdue DSARs."""
        return [d for d in self._dsars.values() if d.is_overdue]
    
    async def get_dsars_by_status(self, status: str) -> list[DataSubjectRequest]:
        """Get DSARs by status."""
        return [d for d in self._dsars.values() if d.status == status]
    
    # ═══════════════════════════════════════════════════════════════
    # CONSENT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def record_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        purpose: str,
        granted: bool,
        collected_via: str,
        consent_text_version: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        third_parties: list[str] | None = None,
        cross_border_transfer: bool = False,
        transfer_safeguards: list[str] | None = None,
        tcf_string: str | None = None,
        gpp_string: str | None = None,
        expires_at: datetime | None = None,
    ) -> ConsentRecord:
        """
        Record a consent decision.
        
        Maintains full audit trail per GDPR Article 7 requirements.
        """
        consent = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            purpose=purpose,
            granted=granted,
            granted_at=datetime.utcnow() if granted else None,
            collected_via=collected_via,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text_version=consent_text_version,
            consent_text_hash=hashlib.sha256(consent_text_version.encode()).hexdigest()[:16],
            third_parties=third_parties or [],
            third_party_consent_given=bool(third_parties) and granted,
            cross_border_transfer=cross_border_transfer,
            transfer_safeguards=transfer_safeguards or [],
            tcf_string=tcf_string,
            gpp_string=gpp_string,
            expires_at=expires_at,
        )
        
        # Store in memory cache
        if user_id not in self._consents:
            self._consents[user_id] = []
        self._consents[user_id].append(consent)

        # PERSISTENCE FIX: Persist to database
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_consent({
                    "id": consent.id,
                    "user_id": user_id,
                    "consent_type": consent_type.value,
                    "purpose": purpose,
                    "granted": granted,
                    "granted_at": consent.granted_at,
                    "withdrawn_at": None,
                    "collected_via": collected_via,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "consent_text_version": consent_text_version,
                    "consent_text_hash": consent.consent_text_hash,
                    "third_parties": third_parties or [],
                    "cross_border_transfer": cross_border_transfer,
                    "transfer_safeguards": transfer_safeguards or [],
                    "tcf_string": tcf_string,
                    "gpp_string": gpp_string,
                    "expires_at": expires_at,
                })
            except Exception as e:
                logger.error("consent_persistence_failed", consent_id=consent.id, error=str(e))

        # Log
        await self.log_event(
            category=AuditEventCategory.PRIVACY,
            event_type="consent_recorded",
            action="CREATE",
            actor_id=user_id,
            entity_type="ConsentRecord",
            entity_id=consent.id,
            new_value={
                "consent_type": consent_type.value,
                "purpose": purpose,
                "granted": granted,
            },
            risk_level=RiskLevel.INFO,
        )
        
        return consent
    
    async def withdraw_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
    ) -> ConsentRecord | None:
        """Withdraw consent for a specific type."""
        consents = self._consents.get(user_id, [])
        
        for consent in consents:
            if consent.consent_type == consent_type and consent.is_valid:
                consent.withdraw()
                
                await self.log_event(
                    category=AuditEventCategory.PRIVACY,
                    event_type="consent_withdrawn",
                    action="UPDATE",
                    actor_id=user_id,
                    entity_type="ConsentRecord",
                    entity_id=consent.id,
                    old_value={"granted": True},
                    new_value={"granted": False, "withdrawn_at": consent.withdrawn_at.isoformat()},
                    risk_level=RiskLevel.INFO,
                )
                
                return consent
        
        return None
    
    async def check_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
    ) -> bool:
        """Check if user has valid consent for a specific type."""
        consents = self._consents.get(user_id, [])
        return any(
            c.consent_type == consent_type and c.is_valid
            for c in consents
        )
    
    async def get_user_consents(self, user_id: str) -> list[ConsentRecord]:
        """Get all consent records for a user."""
        return self._consents.get(user_id, [])
    
    async def process_gpc_signal(
        self,
        user_id: str,
        gpc_enabled: bool,
    ) -> list[ConsentRecord]:
        """
        Process Global Privacy Control signal.
        
        Per CCPA regulations, GPC must be treated as opt-out of sale/sharing.
        """
        if not gpc_enabled:
            return []
        
        results = []
        
        # Auto-withdraw sale/sharing and sensitive PI consents
        for consent_type in [ConsentType.THIRD_PARTY, ConsentType.PROFILING, ConsentType.MARKETING]:
            consent = await self.withdraw_consent(user_id, consent_type)
            if consent:
                results.append(consent)
        
        logger.info(
            "gpc_signal_processed",
            user_id=user_id,
            consents_withdrawn=len(results),
        )
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # BREACH NOTIFICATION
    # ═══════════════════════════════════════════════════════════════
    
    async def report_breach(
        self,
        discovered_by: str,
        discovery_method: str,
        severity: BreachSeverity,
        breach_type: str,
        data_categories: list[DataClassification],
        data_elements: list[str],
        jurisdictions: list[Jurisdiction],
        record_count: int = 0,
        root_cause: str | None = None,
        attack_vector: str | None = None,
    ) -> BreachNotification:
        """
        Report a data breach.
        
        Automatically calculates notification deadlines per jurisdiction.
        """
        breach = BreachNotification(
            discovered_by=discovered_by,
            discovery_method=discovery_method,
            severity=severity,
            breach_type=breach_type,
            data_categories=data_categories,
            data_elements=data_elements,
            jurisdictions=jurisdictions,
            record_count=record_count,
            affected_count=record_count,
            root_cause=root_cause,
            attack_vector=attack_vector,
            individual_notification_required=severity.requires_individual_notification,
        )
        
        # Create regulatory notification records
        for jurisdiction in jurisdictions:
            if severity.requires_authority_notification:
                notif = RegulatoryNotification(
                    authority=self._get_authority_for_jurisdiction(jurisdiction),
                    jurisdiction=jurisdiction,
                    required=True,
                    deadline=breach.notification_deadlines.get(jurisdiction.value),
                )
                breach.authority_notifications.append(notif)
        
        # Store in memory cache
        self._breaches[breach.id] = breach

        # PERSISTENCE FIX: Persist to database
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_breach({
                    "id": breach.id,
                    "discovered_by": discovered_by,
                    "discovery_method": discovery_method,
                    "severity": severity.value,
                    "breach_type": breach_type,
                    "status": "reported",
                    "data_categories": data_categories,
                    "data_elements": data_elements,
                    "jurisdictions": jurisdictions,
                    "record_count": record_count,
                    "affected_count": record_count,
                    "root_cause": root_cause,
                    "attack_vector": attack_vector,
                    "contained": False,
                    "contained_at": None,
                    "containment_actions": [],
                    "individual_notification_required": breach.individual_notification_required,
                    "authority_notifications": [
                        {"authority": n.authority, "jurisdiction": n.jurisdiction.value, "deadline": n.deadline.isoformat() if n.deadline else None}
                        for n in breach.authority_notifications
                    ],
                    "notification_deadlines": breach.notification_deadlines,
                })
            except Exception as e:
                logger.error("breach_persistence_failed", breach_id=breach.id, error=str(e))

        # Log as critical event
        await self.log_event(
            category=AuditEventCategory.SECURITY,
            event_type="breach_reported",
            action="CREATE",
            actor_id=discovered_by,
            entity_type="BreachNotification",
            entity_id=breach.id,
            new_value={
                "severity": severity.value,
                "breach_type": breach_type,
                "record_count": record_count,
                "jurisdictions": [j.value for j in jurisdictions],
            },
            risk_level=RiskLevel.CRITICAL,
        )
        
        logger.critical(
            "breach_reported",
            breach_id=breach.id,
            severity=severity.value,
            record_count=record_count,
            most_urgent_deadline=breach.most_urgent_deadline.isoformat() if breach.most_urgent_deadline else None,
        )
        
        # Notify handlers
        await self._notify_handlers("breach_reported", breach)
        
        return breach
    
    async def mark_breach_contained(
        self,
        breach_id: str,
        containment_actions: list[str],
        actor_id: str,
    ) -> BreachNotification:
        """Mark breach as contained."""
        breach = self._breaches.get(breach_id)
        if not breach:
            raise ValueError(f"Breach not found: {breach_id}")
        
        breach.contained = True
        breach.contained_at = datetime.utcnow()
        breach.containment_actions = containment_actions
        breach.updated_at = datetime.utcnow()
        
        await self.log_event(
            category=AuditEventCategory.SECURITY,
            event_type="breach_contained",
            action="UPDATE",
            actor_id=actor_id,
            entity_type="BreachNotification",
            entity_id=breach_id,
            new_value={"contained": True, "containment_actions": containment_actions},
            risk_level=RiskLevel.HIGH,
        )
        
        return breach
    
    async def record_authority_notification(
        self,
        breach_id: str,
        jurisdiction: Jurisdiction,
        reference_number: str | None = None,
        actor_id: str | None = None,
    ) -> BreachNotification:
        """Record that authority has been notified."""
        breach = self._breaches.get(breach_id)
        if not breach:
            raise ValueError(f"Breach not found: {breach_id}")
        
        for notif in breach.authority_notifications:
            if notif.jurisdiction == jurisdiction:
                notif.notified = True
                notif.notified_at = datetime.utcnow()
                notif.reference_number = reference_number
                break
        
        breach.updated_at = datetime.utcnow()
        
        await self.log_event(
            category=AuditEventCategory.COMPLIANCE,
            event_type="authority_notified",
            action="UPDATE",
            actor_id=actor_id,
            entity_type="BreachNotification",
            entity_id=breach_id,
            new_value={
                "jurisdiction": jurisdiction.value,
                "reference_number": reference_number,
            },
            risk_level=RiskLevel.HIGH,
        )
        
        return breach
    
    def _get_authority_for_jurisdiction(self, jurisdiction: Jurisdiction) -> str:
        """Get the name of the supervisory authority for a jurisdiction."""
        authorities = {
            Jurisdiction.EU: "Lead Supervisory Authority (per GDPR Art. 56)",
            Jurisdiction.UK: "Information Commissioner's Office (ICO)",
            Jurisdiction.FRANCE: "CNIL",
            Jurisdiction.GERMANY: "State Data Protection Authority",
            Jurisdiction.US_CALIFORNIA: "California Attorney General",
            Jurisdiction.BRAZIL: "ANPD",
            Jurisdiction.SINGAPORE: "PDPC",
            Jurisdiction.CHINA: "CAC",
        }
        return authorities.get(jurisdiction, "Relevant Supervisory Authority")
    
    # ═══════════════════════════════════════════════════════════════
    # AI GOVERNANCE
    # ═══════════════════════════════════════════════════════════════
    
    async def register_ai_system(
        self,
        system_name: str,
        system_version: str,
        provider: str,
        risk_classification: AIRiskClassification,
        intended_purpose: str,
        use_cases: list[str],
        model_type: str,
        human_oversight_measures: list[str],
        training_data_description: str | None = None,
    ) -> AISystemRegistration:
        """
        Register an AI system for EU AI Act compliance.
        """
        registration = AISystemRegistration(
            system_name=system_name,
            system_version=system_version,
            provider=provider,
            risk_classification=risk_classification,
            intended_purpose=intended_purpose,
            use_cases=use_cases,
            model_type=model_type,
            human_oversight_measures=human_oversight_measures,
            training_data_description=training_data_description,
            override_capability=True,
        )
        
        # Store in memory cache
        self._ai_systems[registration.id] = registration

        # PERSISTENCE FIX: Persist to database
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_ai_system({
                    "id": registration.id,
                    "system_name": system_name,
                    "system_version": system_version,
                    "provider": provider,
                    "risk_classification": risk_classification,
                    "intended_purpose": intended_purpose,
                    "use_cases": use_cases,
                    "model_type": model_type,
                    "human_oversight_measures": human_oversight_measures,
                    "training_data_description": training_data_description,
                    "override_capability": True,
                })
            except Exception as e:
                logger.error("ai_system_persistence_failed", system_id=registration.id, error=str(e))

        await self.log_event(
            category=AuditEventCategory.AI_DECISION,
            event_type="ai_system_registered",
            action="CREATE",
            entity_type="AISystemRegistration",
            entity_id=registration.id,
            new_value={
                "system_name": system_name,
                "risk_classification": risk_classification.value,
            },
            risk_level=RiskLevel.INFO,
        )

        logger.info(
            "ai_system_registered",
            system_id=registration.id,
            system_name=system_name,
            risk_classification=risk_classification.value,
            requires_conformity=risk_classification.requires_conformity_assessment,
        )

        return registration
    
    async def log_ai_decision(
        self,
        ai_system_id: str,
        model_version: str,
        decision_type: str,
        decision_outcome: str,
        confidence_score: float,
        input_summary: dict[str, Any],
        reasoning_chain: list[str],
        key_factors: list[dict[str, Any]],
        subject_id: str | None = None,
        has_legal_effect: bool = False,
        has_significant_effect: bool = False,
    ) -> AIDecisionLog:
        """
        Log an AI decision for transparency and explainability.
        
        Per EU AI Act Article 12 and GDPR Article 22.
        """
        decision = AIDecisionLog(
            ai_system_id=ai_system_id,
            model_version=model_version,
            decision_type=decision_type,
            decision_outcome=decision_outcome,
            confidence_score=confidence_score,
            input_summary=input_summary,
            reasoning_chain=reasoning_chain,
            key_factors=key_factors,
            subject_id=subject_id,
            has_legal_effect=has_legal_effect,
            has_significant_effect=has_significant_effect,
        )
        
        # Store in memory cache
        self._ai_decisions.append(decision)

        # PERSISTENCE FIX: Persist to database
        if self._persistence_enabled and self._repository:
            try:
                await self._repository.create_ai_decision({
                    "id": decision.id,
                    "ai_system_id": ai_system_id,
                    "model_version": model_version,
                    "decision_type": decision_type,
                    "decision_outcome": decision_outcome,
                    "confidence_score": confidence_score,
                    "input_summary": input_summary,
                    "reasoning_chain": reasoning_chain,
                    "key_factors": key_factors,
                    "alternative_outcomes": [],
                    "subject_id": subject_id,
                    "has_legal_effect": has_legal_effect,
                    "has_significant_effect": has_significant_effect,
                    "human_reviewed": False,
                    "human_reviewer": None,
                    "human_override": False,
                    "override_reason": None,
                    "contested": False,
                })
            except Exception as e:
                logger.error("ai_decision_persistence_failed", decision_id=decision.id, error=str(e))

        # Log to audit trail
        await self.log_event(
            category=AuditEventCategory.AI_DECISION,
            event_type="ai_decision_made",
            action="CREATE",
            actor_id=ai_system_id,
            actor_type="ai_system",
            entity_type="AIDecisionLog",
            entity_id=decision.id,
            new_value={
                "decision_type": decision_type,
                "decision_outcome": decision_outcome,
                "confidence_score": confidence_score,
                "has_legal_effect": has_legal_effect,
            },
            risk_level=RiskLevel.INFO if not has_legal_effect else RiskLevel.MEDIUM,
        )

        return decision
    
    async def request_human_review(
        self,
        decision_id: str,
        reviewer_id: str,
        override: bool = False,
        override_reason: str | None = None,
    ) -> AIDecisionLog | None:
        """
        Request or complete human review of an AI decision.
        
        Per GDPR Article 22 right to human intervention.
        """
        for decision in self._ai_decisions:
            if decision.id == decision_id:
                decision.human_reviewed = True
                decision.human_reviewer = reviewer_id
                if override:
                    decision.human_override = True
                    decision.override_reason = override_reason
                
                await self.log_event(
                    category=AuditEventCategory.AI_DECISION,
                    event_type="ai_decision_reviewed",
                    action="UPDATE",
                    actor_id=reviewer_id,
                    entity_type="AIDecisionLog",
                    entity_id=decision_id,
                    new_value={
                        "human_reviewed": True,
                        "human_override": override,
                        "override_reason": override_reason,
                    },
                    risk_level=RiskLevel.INFO,
                )
                
                return decision
        
        return None
    
    async def get_ai_decision_explanation(
        self,
        decision_id: str,
    ) -> dict[str, Any] | None:
        """
        Get plain-language explanation of an AI decision.
        
        Per GDPR Article 22 and EU AI Act transparency requirements.
        """
        for decision in self._ai_decisions:
            if decision.id == decision_id:
                return {
                    "decision_type": decision.decision_type,
                    "outcome": decision.decision_outcome,
                    "confidence": f"{decision.confidence_score * 100:.1f}%",
                    "key_factors": decision.key_factors,
                    "reasoning": decision.reasoning_chain,
                    "alternatives_considered": decision.alternative_outcomes,
                    "human_review_available": True,
                    "request_review_url": f"/api/v1/compliance/ai-decisions/{decision_id}/review",
                }
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # COMPLIANCE REPORTING
    # ═══════════════════════════════════════════════════════════════
    
    async def generate_compliance_report(
        self,
        report_type: str = "full",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        frameworks: list[ComplianceFramework] | None = None,
        jurisdictions: list[Jurisdiction] | None = None,
        generated_by: str = "system",
    ) -> ComplianceReport:
        """
        Generate a compliance assessment report.
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        if not frameworks:
            frameworks = self.config.frameworks_list
        if not jurisdictions:
            jurisdictions = self.config.jurisdictions_list
        
        # Calculate control status
        total_controls = 0
        compliant = 0
        non_compliant = 0
        
        controls_by_framework = {}
        critical_gaps = []
        high_risk_gaps = []
        medium_risk_gaps = []
        
        for framework in frameworks:
            status = self.registry.get_framework_compliance_status(framework)
            controls_by_framework[framework.value] = status
            total_controls += status["total"]
            compliant += status["verified"]
            non_compliant += status["pending"]
            
            # Identify gaps
            for control in self.registry.get_controls_by_framework(framework):
                control_status = self.registry.get_control_status(control.control_id)
                if not control_status or not control_status.is_compliant:
                    gap = {
                        "control_id": control.control_id,
                        "framework": framework.value,
                        "name": control.name,
                        "risk_level": control.risk_if_missing.value,
                        "implementation_guidance": control.implementation_guidance,
                    }
                    if control.risk_if_missing == RiskLevel.CRITICAL:
                        critical_gaps.append(gap)
                    elif control.risk_if_missing == RiskLevel.HIGH:
                        high_risk_gaps.append(gap)
                    elif control.risk_if_missing == RiskLevel.MEDIUM:
                        medium_risk_gaps.append(gap)
        
        # Calculate DSAR metrics
        all_dsars = list(self._dsars.values())
        period_dsars = [d for d in all_dsars if start_date <= d.created_at <= end_date]
        
        dsar_metrics = {
            "total_received": len(period_dsars),
            "completed": len([d for d in period_dsars if d.status == "completed"]),
            "pending": len([d for d in period_dsars if d.status in ("received", "verified", "processing")]),
            "overdue": len([d for d in period_dsars if d.is_overdue]),
            "average_completion_days": self._calculate_avg_dsar_days(period_dsars),
        }
        
        # Calculate consent metrics
        total_users = len(self._consents)
        consent_metrics = {
            "users_with_consent": total_users,
            "active_consents": sum(len([c for c in consents if c.is_valid]) for consents in self._consents.values()),
            "withdrawn_consents": sum(len([c for c in consents if c.withdrawn_at]) for consents in self._consents.values()),
        }
        
        # Calculate breach metrics
        period_breaches = [b for b in self._breaches.values() if start_date <= b.created_at <= end_date]
        breach_metrics = {
            "total_breaches": len(period_breaches),
            "critical_breaches": len([b for b in period_breaches if b.severity == BreachSeverity.CRITICAL]),
            "contained": len([b for b in period_breaches if b.contained]),
            "overdue_notifications": len([b for b in period_breaches if b.is_overdue]),
        }
        
        # Create compliance status
        status = ComplianceStatus(
            organization_id="default",
            active_jurisdictions=jurisdictions,
            active_frameworks=frameworks,
            controls_by_framework=controls_by_framework,
            total_controls=total_controls,
            implemented_controls=compliant,
            verified_controls=compliant,
            high_risk_pending=len(critical_gaps) + len(high_risk_gaps),
            critical_findings=[g["control_id"] for g in critical_gaps],
        )
        
        # Create report
        report = ComplianceReport(
            report_type=report_type,
            report_period_start=start_date,
            report_period_end=end_date,
            generated_by=generated_by,
            frameworks_assessed=frameworks,
            jurisdictions_assessed=jurisdictions,
            overall_compliance_score=status.compliance_percentage,
            status=status,
            total_controls_assessed=total_controls,
            controls_compliant=compliant,
            controls_non_compliant=non_compliant,
            critical_gaps=critical_gaps,
            high_risk_gaps=high_risk_gaps,
            medium_risk_gaps=medium_risk_gaps,
            dsar_metrics=dsar_metrics,
            consent_metrics=consent_metrics,
            breach_metrics=breach_metrics,
            ai_system_count=len(self._ai_systems),
            high_risk_ai_systems=len([s for s in self._ai_systems.values() if s.risk_classification in {AIRiskClassification.HIGH_RISK, AIRiskClassification.GPAI_SYSTEMIC}]),
            ai_decisions_logged=len(self._ai_decisions),
            ai_decisions_contested=len([d for d in self._ai_decisions if d.contested]),
        )
        
        await self.log_event(
            category=AuditEventCategory.COMPLIANCE,
            event_type="compliance_report_generated",
            action="CREATE",
            actor_id=generated_by,
            entity_type="ComplianceReport",
            entity_id=report.id,
            new_value={
                "report_type": report_type,
                "compliance_score": report.overall_compliance_score,
                "critical_gaps": len(critical_gaps),
            },
            risk_level=RiskLevel.INFO,
        )
        
        return report
    
    def _calculate_avg_dsar_days(self, dsars: list[DataSubjectRequest]) -> float:
        """Calculate average DSAR completion time in days."""
        completed = [d for d in dsars if d.status == "completed" and d.response_sent_at]
        if not completed:
            return 0.0
        
        total_days = sum(
            (d.response_sent_at - d.received_at).days
            for d in completed
        )
        return total_days / len(completed)
    
    # ═══════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable,
    ) -> None:
        """Register an event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def _notify_handlers(
        self,
        event_type: str,
        data: Any,
    ) -> None:
        """Notify all handlers for an event type."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(
                    "handler_error",
                    event_type=event_type,
                    error=str(e),
                )
    
    # ═══════════════════════════════════════════════════════════════
    # CONTROL VERIFICATION
    # ═══════════════════════════════════════════════════════════════
    
    async def verify_control(
        self,
        control_id: str,
        verifier_id: str,
        evidence: list[str] | None = None,
        notes: str | None = None,
    ) -> ControlStatus | None:
        """
        Verify a compliance control.
        
        If the control has an automated verification function, it will be executed.
        """
        control = self.registry.get_control(control_id)
        if not control:
            return None
        
        # Check for automated verification
        automated_result = True
        if control.verification_function:
            verify_fn = self.registry.get_verification_function(control.verification_function)
            if verify_fn:
                try:
                    automated_result = await verify_fn() if asyncio.iscoroutinefunction(verify_fn) else verify_fn()
                except Exception as e:
                    logger.error(
                        "verification_failed",
                        control_id=control_id,
                        error=str(e),
                    )
                    automated_result = False
        
        # Update status
        status = self.registry.set_control_status(
            control_id=control_id,
            implemented=True,
            verified=automated_result,
            evidence=evidence,
            notes=notes,
        )
        
        if status:
            await self.log_event(
                category=AuditEventCategory.COMPLIANCE,
                event_type="control_verified",
                action="UPDATE",
                actor_id=verifier_id,
                entity_type="ControlStatus",
                entity_id=control_id,
                new_value={
                    "verified": automated_result,
                    "evidence": evidence,
                },
                risk_level=RiskLevel.INFO,
            )
        
        return status
    
    async def run_automated_verifications(self) -> dict[str, bool]:
        """
        Run all automated control verifications.
        
        Returns a dict of control_id -> verification_result.
        """
        results = {}
        automatable = self.registry.get_automatable_controls()
        
        for control in automatable:
            if control.verification_function:
                verify_fn = self.registry.get_verification_function(control.verification_function)
                if verify_fn:
                    try:
                        result = await verify_fn() if asyncio.iscoroutinefunction(verify_fn) else verify_fn()
                        results[control.control_id] = result
                    except Exception:
                        results[control.control_id] = False
        
        logger.info(
            "automated_verifications_complete",
            total=len(results),
            passed=sum(1 for r in results.values() if r),
            failed=sum(1 for r in results.values() if not r),
        )
        
        return results


# Global engine instance
_engine: ComplianceEngine | None = None


def get_compliance_engine() -> ComplianceEngine:
    """Get the global compliance engine instance."""
    global _engine
    if _engine is None:
        _engine = ComplianceEngine()
    return _engine
