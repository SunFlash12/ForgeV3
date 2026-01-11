"""
Forge Compliance Framework - Repository Layer

Neo4j persistence for compliance data including:
- Data Subject Access Requests (DSARs)
- Consent records
- Breach notifications
- Audit events (immutable, hash-chained)
- AI system registrations
- AI decision logs

Implements regulatory data retention requirements:
- GDPR: Consent records for duration of processing + 7 years
- SOX: Audit logs for 7 years minimum
- HIPAA: 6 years for audit trails
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ComplianceRepository:
    """
    Neo4j repository for compliance data persistence.

    Provides CRUD operations for all compliance entities with
    proper audit trail and data integrity verification.
    """

    def __init__(self, neo4j_client):
        """
        Initialize repository with Neo4j client.

        Args:
            neo4j_client: Neo4j async client instance
        """
        self._db = neo4j_client
        self._initialized = False

    async def initialize(self) -> None:
        """Create required indexes and constraints."""
        if self._initialized:
            return

        constraints = [
            # DSAR constraints
            "CREATE CONSTRAINT dsar_id IF NOT EXISTS FOR (d:DSAR) REQUIRE d.id IS UNIQUE",
            "CREATE INDEX dsar_status IF NOT EXISTS FOR (d:DSAR) ON (d.status)",
            "CREATE INDEX dsar_subject IF NOT EXISTS FOR (d:DSAR) ON (d.subject_email)",

            # Consent constraints
            "CREATE CONSTRAINT consent_id IF NOT EXISTS FOR (c:ConsentRecord) REQUIRE c.id IS UNIQUE",
            "CREATE INDEX consent_user IF NOT EXISTS FOR (c:ConsentRecord) ON (c.user_id)",
            "CREATE INDEX consent_type IF NOT EXISTS FOR (c:ConsentRecord) ON (c.consent_type)",

            # Breach constraints
            "CREATE CONSTRAINT breach_id IF NOT EXISTS FOR (b:BreachNotification) REQUIRE b.id IS UNIQUE",
            "CREATE INDEX breach_status IF NOT EXISTS FOR (b:BreachNotification) ON (b.status)",
            "CREATE INDEX breach_severity IF NOT EXISTS FOR (b:BreachNotification) ON (b.severity)",

            # Audit event constraints - append-only with hash chain
            "CREATE CONSTRAINT audit_id IF NOT EXISTS FOR (a:AuditEvent) REQUIRE a.id IS UNIQUE",
            "CREATE INDEX audit_category IF NOT EXISTS FOR (a:AuditEvent) ON (a.category)",
            "CREATE INDEX audit_actor IF NOT EXISTS FOR (a:AuditEvent) ON (a.actor_id)",
            "CREATE INDEX audit_entity IF NOT EXISTS FOR (a:AuditEvent) ON (a.entity_type, a.entity_id)",
            "CREATE INDEX audit_timestamp IF NOT EXISTS FOR (a:AuditEvent) ON (a.created_at)",

            # AI system constraints
            "CREATE CONSTRAINT ai_system_id IF NOT EXISTS FOR (s:AISystemRegistration) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX ai_system_name IF NOT EXISTS FOR (s:AISystemRegistration) ON (s.system_name)",

            # AI decision constraints
            "CREATE CONSTRAINT ai_decision_id IF NOT EXISTS FOR (d:AIDecisionLog) REQUIRE d.id IS UNIQUE",
            "CREATE INDEX ai_decision_system IF NOT EXISTS FOR (d:AIDecisionLog) ON (d.ai_system_id)",
            "CREATE INDEX ai_decision_subject IF NOT EXISTS FOR (d:AIDecisionLog) ON (d.subject_id)",
        ]

        for constraint in constraints:
            try:
                await self._db.execute(constraint)
            except Exception as e:
                # Ignore if constraint already exists
                if "already exists" not in str(e).lower():
                    logger.warning("constraint_creation_warning", query=constraint[:50], error=str(e))

        self._initialized = True
        logger.info("compliance_repository_initialized")

    # ═══════════════════════════════════════════════════════════════
    # DSAR OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    async def create_dsar(self, dsar: dict[str, Any]) -> dict[str, Any]:
        """Create a new DSAR record."""
        query = """
        CREATE (d:DSAR {
            id: $id,
            request_type: $request_type,
            jurisdiction: $jurisdiction,
            applicable_frameworks: $applicable_frameworks,
            subject_id: $subject_id,
            subject_email: $subject_email,
            subject_name: $subject_name,
            request_text: $request_text,
            specific_data_categories: $specific_data_categories,
            status: $status,
            verified: $verified,
            deadline: $deadline,
            created_at: datetime(),
            updated_at: datetime(),
            assigned_to: $assigned_to,
            processing_notes: $processing_notes
        })
        RETURN d
        """

        params = {
            "id": dsar.get("id"),
            "request_type": dsar.get("request_type"),
            "jurisdiction": dsar.get("jurisdiction"),
            "applicable_frameworks": json.dumps(dsar.get("applicable_frameworks", [])),
            "subject_id": dsar.get("subject_id"),
            "subject_email": dsar.get("subject_email"),
            "subject_name": dsar.get("subject_name"),
            "request_text": dsar.get("request_text"),
            "specific_data_categories": json.dumps(dsar.get("specific_data_categories", [])),
            "status": dsar.get("status", "received"),
            "verified": dsar.get("verified", False),
            "deadline": dsar.get("deadline").isoformat() if dsar.get("deadline") else None,
            "assigned_to": dsar.get("assigned_to"),
            "processing_notes": json.dumps(dsar.get("processing_notes", [])),
        }

        result = await self._db.execute_single(query, params)
        logger.info("dsar_created", dsar_id=dsar.get("id"))
        return result["d"] if result else dsar

    async def update_dsar(self, dsar_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing DSAR."""
        # Build dynamic SET clause
        set_clauses = []
        params = {"id": dsar_id}

        for key, value in updates.items():
            if key in ["applicable_frameworks", "specific_data_categories", "processing_notes"]:
                set_clauses.append(f"d.{key} = ${key}")
                params[key] = json.dumps(value)
            elif key == "deadline" and value:
                set_clauses.append(f"d.{key} = ${key}")
                params[key] = value.isoformat() if hasattr(value, 'isoformat') else value
            else:
                set_clauses.append(f"d.{key} = ${key}")
                params[key] = value

        set_clauses.append("d.updated_at = datetime()")

        query = f"""
        MATCH (d:DSAR {{id: $id}})
        SET {", ".join(set_clauses)}
        RETURN d
        """

        result = await self._db.execute_single(query, params)
        return result["d"] if result else None

    async def get_dsar(self, dsar_id: str) -> dict[str, Any] | None:
        """Get a DSAR by ID."""
        query = "MATCH (d:DSAR {id: $id}) RETURN d"
        result = await self._db.execute_single(query, {"id": dsar_id})
        if result:
            dsar = dict(result["d"])
            # Parse JSON fields
            for field in ["applicable_frameworks", "specific_data_categories", "processing_notes"]:
                if dsar.get(field):
                    dsar[field] = json.loads(dsar[field])
            return dsar
        return None

    async def get_dsars_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get DSARs by status."""
        query = "MATCH (d:DSAR {status: $status}) RETURN d ORDER BY d.created_at DESC"
        results = await self._db.execute(query, {"status": status})
        return [dict(r["d"]) for r in results]

    async def get_overdue_dsars(self) -> list[dict[str, Any]]:
        """Get overdue DSARs."""
        query = """
        MATCH (d:DSAR)
        WHERE d.status IN ['received', 'verified', 'processing']
        AND d.deadline IS NOT NULL
        AND datetime(d.deadline) < datetime()
        RETURN d
        ORDER BY d.deadline ASC
        """
        results = await self._db.execute(query, {})
        return [dict(r["d"]) for r in results]

    # ═══════════════════════════════════════════════════════════════
    # CONSENT OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    async def create_consent(self, consent: dict[str, Any]) -> dict[str, Any]:
        """Create a new consent record."""
        query = """
        CREATE (c:ConsentRecord {
            id: $id,
            user_id: $user_id,
            consent_type: $consent_type,
            purpose: $purpose,
            granted: $granted,
            granted_at: $granted_at,
            withdrawn_at: $withdrawn_at,
            collected_via: $collected_via,
            ip_address: $ip_address,
            user_agent: $user_agent,
            consent_text_version: $consent_text_version,
            consent_text_hash: $consent_text_hash,
            third_parties: $third_parties,
            cross_border_transfer: $cross_border_transfer,
            transfer_safeguards: $transfer_safeguards,
            tcf_string: $tcf_string,
            gpp_string: $gpp_string,
            expires_at: $expires_at,
            created_at: datetime()
        })
        RETURN c
        """

        params = {
            "id": consent.get("id"),
            "user_id": consent.get("user_id"),
            "consent_type": consent.get("consent_type"),
            "purpose": consent.get("purpose"),
            "granted": consent.get("granted", False),
            "granted_at": consent.get("granted_at").isoformat() if consent.get("granted_at") else None,
            "withdrawn_at": consent.get("withdrawn_at").isoformat() if consent.get("withdrawn_at") else None,
            "collected_via": consent.get("collected_via"),
            "ip_address": consent.get("ip_address"),
            "user_agent": consent.get("user_agent"),
            "consent_text_version": consent.get("consent_text_version"),
            "consent_text_hash": consent.get("consent_text_hash"),
            "third_parties": json.dumps(consent.get("third_parties", [])),
            "cross_border_transfer": consent.get("cross_border_transfer", False),
            "transfer_safeguards": json.dumps(consent.get("transfer_safeguards", [])),
            "tcf_string": consent.get("tcf_string"),
            "gpp_string": consent.get("gpp_string"),
            "expires_at": consent.get("expires_at").isoformat() if consent.get("expires_at") else None,
        }

        result = await self._db.execute_single(query, params)
        logger.info("consent_created", consent_id=consent.get("id"), user_id=consent.get("user_id"))
        return result["c"] if result else consent

    async def withdraw_consent(self, consent_id: str) -> dict[str, Any] | None:
        """Mark a consent as withdrawn."""
        query = """
        MATCH (c:ConsentRecord {id: $id})
        SET c.granted = false,
            c.withdrawn_at = datetime()
        RETURN c
        """
        result = await self._db.execute_single(query, {"id": consent_id})
        return result["c"] if result else None

    async def get_user_consents(self, user_id: str) -> list[dict[str, Any]]:
        """Get all consent records for a user."""
        query = """
        MATCH (c:ConsentRecord {user_id: $user_id})
        RETURN c
        ORDER BY c.created_at DESC
        """
        results = await self._db.execute(query, {"user_id": user_id})
        return [dict(r["c"]) for r in results]

    async def check_consent(self, user_id: str, consent_type: str) -> bool:
        """Check if user has valid consent for a type."""
        query = """
        MATCH (c:ConsentRecord {user_id: $user_id, consent_type: $consent_type})
        WHERE c.granted = true
        AND c.withdrawn_at IS NULL
        AND (c.expires_at IS NULL OR datetime(c.expires_at) > datetime())
        RETURN count(c) > 0 AS has_consent
        """
        result = await self._db.execute_single(query, {
            "user_id": user_id,
            "consent_type": consent_type
        })
        return result["has_consent"] if result else False

    # ═══════════════════════════════════════════════════════════════
    # BREACH NOTIFICATION OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    async def create_breach(self, breach: dict[str, Any]) -> dict[str, Any]:
        """Create a new breach notification record."""
        query = """
        CREATE (b:BreachNotification {
            id: $id,
            discovered_by: $discovered_by,
            discovery_method: $discovery_method,
            severity: $severity,
            breach_type: $breach_type,
            status: $status,
            data_categories: $data_categories,
            data_elements: $data_elements,
            jurisdictions: $jurisdictions,
            record_count: $record_count,
            affected_count: $affected_count,
            root_cause: $root_cause,
            attack_vector: $attack_vector,
            contained: $contained,
            contained_at: $contained_at,
            containment_actions: $containment_actions,
            individual_notification_required: $individual_notification_required,
            authority_notifications: $authority_notifications,
            notification_deadlines: $notification_deadlines,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN b
        """

        params = {
            "id": breach.get("id"),
            "discovered_by": breach.get("discovered_by"),
            "discovery_method": breach.get("discovery_method"),
            "severity": breach.get("severity"),
            "breach_type": breach.get("breach_type"),
            "status": breach.get("status", "reported"),
            "data_categories": json.dumps([str(c) for c in breach.get("data_categories", [])]),
            "data_elements": json.dumps(breach.get("data_elements", [])),
            "jurisdictions": json.dumps([str(j) for j in breach.get("jurisdictions", [])]),
            "record_count": breach.get("record_count", 0),
            "affected_count": breach.get("affected_count", 0),
            "root_cause": breach.get("root_cause"),
            "attack_vector": breach.get("attack_vector"),
            "contained": breach.get("contained", False),
            "contained_at": breach.get("contained_at").isoformat() if breach.get("contained_at") else None,
            "containment_actions": json.dumps(breach.get("containment_actions", [])),
            "individual_notification_required": breach.get("individual_notification_required", False),
            "authority_notifications": json.dumps(breach.get("authority_notifications", [])),
            "notification_deadlines": json.dumps(breach.get("notification_deadlines", {})),
        }

        result = await self._db.execute_single(query, params)
        logger.critical("breach_created", breach_id=breach.get("id"), severity=breach.get("severity"))
        return result["b"] if result else breach

    async def update_breach(self, breach_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update a breach notification."""
        set_clauses = []
        params = {"id": breach_id}

        json_fields = ["data_categories", "data_elements", "jurisdictions",
                       "containment_actions", "authority_notifications", "notification_deadlines"]

        for key, value in updates.items():
            if key in json_fields:
                set_clauses.append(f"b.{key} = ${key}")
                params[key] = json.dumps(value)
            elif key.endswith("_at") and value:
                set_clauses.append(f"b.{key} = ${key}")
                params[key] = value.isoformat() if hasattr(value, 'isoformat') else value
            else:
                set_clauses.append(f"b.{key} = ${key}")
                params[key] = value

        set_clauses.append("b.updated_at = datetime()")

        query = f"""
        MATCH (b:BreachNotification {{id: $id}})
        SET {", ".join(set_clauses)}
        RETURN b
        """

        result = await self._db.execute_single(query, params)
        return result["b"] if result else None

    async def get_breach(self, breach_id: str) -> dict[str, Any] | None:
        """Get a breach by ID."""
        query = "MATCH (b:BreachNotification {id: $id}) RETURN b"
        result = await self._db.execute_single(query, {"id": breach_id})
        if result:
            breach = dict(result["b"])
            # Parse JSON fields
            for field in ["data_categories", "data_elements", "jurisdictions",
                          "containment_actions", "authority_notifications", "notification_deadlines"]:
                if breach.get(field):
                    breach[field] = json.loads(breach[field])
            return breach
        return None

    async def get_active_breaches(self) -> list[dict[str, Any]]:
        """Get all non-closed breaches."""
        query = """
        MATCH (b:BreachNotification)
        WHERE b.status <> 'closed'
        RETURN b
        ORDER BY b.severity DESC, b.created_at DESC
        """
        results = await self._db.execute(query, {})
        return [dict(r["b"]) for r in results]

    # ═══════════════════════════════════════════════════════════════
    # AUDIT EVENT OPERATIONS (APPEND-ONLY)
    # ═══════════════════════════════════════════════════════════════

    async def create_audit_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        Create an immutable audit event.

        Audit events are append-only and include hash chain for integrity.
        """
        query = """
        CREATE (a:AuditEvent {
            id: $id,
            category: $category,
            event_type: $event_type,
            action: $action,
            actor_id: $actor_id,
            actor_type: $actor_type,
            actor_ip: $actor_ip,
            entity_type: $entity_type,
            entity_id: $entity_id,
            correlation_id: $correlation_id,
            old_value: $old_value,
            new_value: $new_value,
            success: $success,
            error_message: $error_message,
            risk_level: $risk_level,
            data_classification: $data_classification,
            previous_hash: $previous_hash,
            hash: $hash,
            created_at: datetime()
        })
        RETURN a
        """

        params = {
            "id": event.get("id"),
            "category": str(event.get("category")),
            "event_type": event.get("event_type"),
            "action": event.get("action"),
            "actor_id": event.get("actor_id"),
            "actor_type": event.get("actor_type", "user"),
            "actor_ip": event.get("actor_ip"),
            "entity_type": event.get("entity_type"),
            "entity_id": event.get("entity_id"),
            "correlation_id": event.get("correlation_id"),
            "old_value": json.dumps(event.get("old_value")) if event.get("old_value") else None,
            "new_value": json.dumps(event.get("new_value")) if event.get("new_value") else None,
            "success": event.get("success", True),
            "error_message": event.get("error_message"),
            "risk_level": str(event.get("risk_level")),
            "data_classification": str(event.get("data_classification")) if event.get("data_classification") else None,
            "previous_hash": event.get("previous_hash"),
            "hash": event.get("hash"),
        }

        result = await self._db.execute_single(query, params)
        return result["a"] if result else event

    async def get_audit_events(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        category: str | None = None,
        actor_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit events with filters."""
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if start_date:
            conditions.append("a.created_at >= datetime($start_date)")
            params["start_date"] = start_date.isoformat()
        if end_date:
            conditions.append("a.created_at <= datetime($end_date)")
            params["end_date"] = end_date.isoformat()
        if category:
            conditions.append("a.category = $category")
            params["category"] = category
        if actor_id:
            conditions.append("a.actor_id = $actor_id")
            params["actor_id"] = actor_id
        if entity_type:
            conditions.append("a.entity_type = $entity_type")
            params["entity_type"] = entity_type
        if entity_id:
            conditions.append("a.entity_id = $entity_id")
            params["entity_id"] = entity_id

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (a:AuditEvent)
        {where_clause}
        RETURN a
        ORDER BY a.created_at DESC
        LIMIT $limit
        """

        results = await self._db.execute(query, params)
        return [dict(r["a"]) for r in results]

    async def get_last_audit_hash(self) -> str | None:
        """Get the hash of the most recent audit event for chain integrity."""
        query = """
        MATCH (a:AuditEvent)
        RETURN a.hash AS hash
        ORDER BY a.created_at DESC
        LIMIT 1
        """
        result = await self._db.execute_single(query, {})
        return result["hash"] if result else None

    async def verify_audit_chain(self) -> tuple[bool, str]:
        """Verify the integrity of the audit event chain."""
        query = """
        MATCH (a:AuditEvent)
        RETURN a
        ORDER BY a.created_at ASC
        """
        results = await self._db.execute(query, {})

        if not results:
            return True, "No events to verify"

        import hashlib

        previous_hash = None
        for r in results:
            event = dict(r["a"])

            # Verify previous hash pointer
            if event.get("previous_hash") != previous_hash:
                return False, f"Chain broken at event {event['id']}"

            # Verify hash calculation
            event_data = json.dumps({
                "id": event["id"],
                "category": event["category"],
                "event_type": event["event_type"],
                "action": event["action"],
                "timestamp": event["created_at"].isoformat() if hasattr(event["created_at"], 'isoformat') else event["created_at"],
                "previous_hash": event["previous_hash"],
            }, sort_keys=True)
            calculated_hash = hashlib.sha256(event_data.encode()).hexdigest()

            if event.get("hash") and event["hash"] != calculated_hash:
                return False, f"Hash mismatch at event {event['id']}"

            previous_hash = event.get("hash")

        return True, f"Chain verified: {len(results)} events"

    # ═══════════════════════════════════════════════════════════════
    # AI SYSTEM OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    async def create_ai_system(self, system: dict[str, Any]) -> dict[str, Any]:
        """Register an AI system."""
        query = """
        CREATE (s:AISystemRegistration {
            id: $id,
            system_name: $system_name,
            system_version: $system_version,
            provider: $provider,
            risk_classification: $risk_classification,
            intended_purpose: $intended_purpose,
            use_cases: $use_cases,
            model_type: $model_type,
            human_oversight_measures: $human_oversight_measures,
            training_data_description: $training_data_description,
            override_capability: $override_capability,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN s
        """

        params = {
            "id": system.get("id"),
            "system_name": system.get("system_name"),
            "system_version": system.get("system_version"),
            "provider": system.get("provider"),
            "risk_classification": str(system.get("risk_classification")),
            "intended_purpose": system.get("intended_purpose"),
            "use_cases": json.dumps(system.get("use_cases", [])),
            "model_type": system.get("model_type"),
            "human_oversight_measures": json.dumps(system.get("human_oversight_measures", [])),
            "training_data_description": system.get("training_data_description"),
            "override_capability": system.get("override_capability", True),
        }

        result = await self._db.execute_single(query, params)
        logger.info("ai_system_registered", system_id=system.get("id"), name=system.get("system_name"))
        return result["s"] if result else system

    async def get_ai_system(self, system_id: str) -> dict[str, Any] | None:
        """Get an AI system by ID."""
        query = "MATCH (s:AISystemRegistration {id: $id}) RETURN s"
        result = await self._db.execute_single(query, {"id": system_id})
        if result:
            system = dict(result["s"])
            for field in ["use_cases", "human_oversight_measures"]:
                if system.get(field):
                    system[field] = json.loads(system[field])
            return system
        return None

    async def get_all_ai_systems(self) -> list[dict[str, Any]]:
        """Get all registered AI systems."""
        query = "MATCH (s:AISystemRegistration) RETURN s ORDER BY s.created_at DESC"
        results = await self._db.execute(query, {})
        return [dict(r["s"]) for r in results]

    # ═══════════════════════════════════════════════════════════════
    # AI DECISION OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    async def create_ai_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Log an AI decision."""
        query = """
        CREATE (d:AIDecisionLog {
            id: $id,
            ai_system_id: $ai_system_id,
            model_version: $model_version,
            decision_type: $decision_type,
            decision_outcome: $decision_outcome,
            confidence_score: $confidence_score,
            input_summary: $input_summary,
            reasoning_chain: $reasoning_chain,
            key_factors: $key_factors,
            alternative_outcomes: $alternative_outcomes,
            subject_id: $subject_id,
            has_legal_effect: $has_legal_effect,
            has_significant_effect: $has_significant_effect,
            human_reviewed: $human_reviewed,
            human_reviewer: $human_reviewer,
            human_override: $human_override,
            override_reason: $override_reason,
            contested: $contested,
            created_at: datetime()
        })
        RETURN d
        """

        params = {
            "id": decision.get("id"),
            "ai_system_id": decision.get("ai_system_id"),
            "model_version": decision.get("model_version"),
            "decision_type": decision.get("decision_type"),
            "decision_outcome": decision.get("decision_outcome"),
            "confidence_score": decision.get("confidence_score"),
            "input_summary": json.dumps(decision.get("input_summary", {})),
            "reasoning_chain": json.dumps(decision.get("reasoning_chain", [])),
            "key_factors": json.dumps(decision.get("key_factors", [])),
            "alternative_outcomes": json.dumps(decision.get("alternative_outcomes", [])),
            "subject_id": decision.get("subject_id"),
            "has_legal_effect": decision.get("has_legal_effect", False),
            "has_significant_effect": decision.get("has_significant_effect", False),
            "human_reviewed": decision.get("human_reviewed", False),
            "human_reviewer": decision.get("human_reviewer"),
            "human_override": decision.get("human_override", False),
            "override_reason": decision.get("override_reason"),
            "contested": decision.get("contested", False),
        }

        result = await self._db.execute_single(query, params)
        return result["d"] if result else decision

    async def update_ai_decision(self, decision_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update an AI decision (for human review)."""
        set_clauses = []
        params = {"id": decision_id}

        for key, value in updates.items():
            set_clauses.append(f"d.{key} = ${key}")
            params[key] = value

        query = f"""
        MATCH (d:AIDecisionLog {{id: $id}})
        SET {", ".join(set_clauses)}
        RETURN d
        """

        result = await self._db.execute_single(query, params)
        return result["d"] if result else None

    async def get_ai_decisions(
        self,
        ai_system_id: str | None = None,
        subject_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get AI decisions with optional filters."""
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if ai_system_id:
            conditions.append("d.ai_system_id = $ai_system_id")
            params["ai_system_id"] = ai_system_id
        if subject_id:
            conditions.append("d.subject_id = $subject_id")
            params["subject_id"] = subject_id

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (d:AIDecisionLog)
        {where_clause}
        RETURN d
        ORDER BY d.created_at DESC
        LIMIT $limit
        """

        results = await self._db.execute(query, params)
        return [dict(r["d"]) for r in results]

    # ═══════════════════════════════════════════════════════════════
    # BULK LOADING FOR ENGINE INITIALIZATION
    # ═══════════════════════════════════════════════════════════════

    async def load_all_dsars(self) -> dict[str, Any]:
        """Load all DSARs into memory (for engine initialization)."""
        query = "MATCH (d:DSAR) RETURN d"
        results = await self._db.execute(query, {})
        return {dict(r["d"])["id"]: dict(r["d"]) for r in results}

    async def load_all_consents(self) -> dict[str, list[dict[str, Any]]]:
        """Load all consents grouped by user_id."""
        query = "MATCH (c:ConsentRecord) RETURN c ORDER BY c.user_id, c.created_at"
        results = await self._db.execute(query, {})

        consents: dict[str, list[dict[str, Any]]] = {}
        for r in results:
            consent = dict(r["c"])
            user_id = consent.get("user_id", "")
            if user_id not in consents:
                consents[user_id] = []
            consents[user_id].append(consent)

        return consents

    async def load_all_breaches(self) -> dict[str, Any]:
        """Load all breaches into memory."""
        query = "MATCH (b:BreachNotification) RETURN b"
        results = await self._db.execute(query, {})
        return {dict(r["b"])["id"]: dict(r["b"]) for r in results}

    async def load_all_ai_systems(self) -> dict[str, Any]:
        """Load all AI systems into memory."""
        query = "MATCH (s:AISystemRegistration) RETURN s"
        results = await self._db.execute(query, {})
        return {dict(r["s"])["id"]: dict(r["s"]) for r in results}


# Global repository instance
_compliance_repository: ComplianceRepository | None = None


def get_compliance_repository(neo4j_client=None) -> ComplianceRepository | None:
    """
    Get the global compliance repository instance.

    Args:
        neo4j_client: Neo4j client instance. Required on first call.

    Returns:
        ComplianceRepository instance or None if no client provided.
    """
    global _compliance_repository

    if _compliance_repository is None and neo4j_client is not None:
        _compliance_repository = ComplianceRepository(neo4j_client)

    return _compliance_repository


async def initialize_compliance_repository(neo4j_client) -> ComplianceRepository:
    """
    Initialize the compliance repository with database client.

    Creates necessary indexes and constraints.
    """
    global _compliance_repository

    _compliance_repository = ComplianceRepository(neo4j_client)
    await _compliance_repository.initialize()

    return _compliance_repository
