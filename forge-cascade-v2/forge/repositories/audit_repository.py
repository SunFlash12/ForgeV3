"""
Audit Repository for Forge Cascade V2

Provides comprehensive audit logging for all system actions,
changes, and events. Supports compliance, forensics, and
the Immune System's anomaly detection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ..database.client import Neo4jClient
from ..models.base import TrustLevel
from ..models.events import AuditEvent, EventPriority, EventType


class AuditRepository:
    """Repository for audit log operations."""

    def __init__(self, db: Neo4jClient):
        self.db = db

    # =========================================================================
    # Core Audit Operations
    # =========================================================================

    async def log(
        self,
        event_type: EventType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
        priority: EventPriority = EventPriority.LOW,
        trust_level_required: TrustLevel = TrustLevel.STANDARD
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event (from EventType enum)
            actor_id: ID of user/system performing action
            action: Human-readable action description
            resource_type: Type of resource affected (capsule, user, overlay, etc.)
            resource_id: ID of affected resource (if applicable)
            details: Additional event details
            old_value: Previous state (for changes)
            new_value: New state (for changes)
            ip_address: Client IP address
            user_agent: Client user agent
            correlation_id: For linking related events
            priority: Event priority level
            trust_level_required: Minimum trust to view this audit entry

        Returns:
            Created AuditEvent
        """
        event_id = str(uuid4())
        now = datetime.now(UTC)

        query = """
        CREATE (a:AuditLog {
            id: $id,
            event_type: $event_type,
            actor_id: $actor_id,
            action: $action,
            resource_type: $resource_type,
            resource_id: $resource_id,
            details: $details,
            old_value: $old_value,
            new_value: $new_value,
            ip_address: $ip_address,
            user_agent: $user_agent,
            correlation_id: $correlation_id,
            priority: $priority,
            trust_level_required: $trust_level_required,
            timestamp: datetime($timestamp),
            created_at: datetime($created_at)
        })
        RETURN a
        """

        # Serialize dicts to JSON strings for Neo4j storage
        import json
        details_json = json.dumps(details) if details else None
        old_value_json = json.dumps(old_value) if old_value else None
        new_value_json = json.dumps(new_value) if new_value else None

        params = {
            "id": event_id,
            "event_type": event_type.value,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details_json,
            "old_value": old_value_json,
            "new_value": new_value_json,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "correlation_id": correlation_id or str(uuid4()),
            "priority": priority.value,
            "trust_level_required": trust_level_required.value,
            "timestamp": now.isoformat(),
            "created_at": now.isoformat()
        }

        record = await self.db.execute_single(query, params)
        return self._to_audit_event(record["a"])

    async def log_capsule_action(
        self,
        actor_id: str,
        capsule_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correlation_id: str | None = None
    ) -> AuditEvent:
        """Log a capsule-related action."""
        event_type_map = {
            "create": EventType.CAPSULE_CREATED,
            "update": EventType.CAPSULE_UPDATED,
            "delete": EventType.CAPSULE_DELETED,
            "archive": EventType.CAPSULE_ARCHIVED,
            "fork": EventType.CAPSULE_FORKED,
            "view": EventType.CAPSULE_VIEWED,
            "search": EventType.CAPSULE_SEARCHED
        }

        event_type = event_type_map.get(action.lower(), EventType.SYSTEM_EVENT)

        return await self.log(
            event_type=event_type,
            actor_id=actor_id,
            action=f"Capsule {action}",
            resource_type="capsule",
            resource_id=capsule_id,
            details=details,
            old_value=old_value,
            new_value=new_value,
            correlation_id=correlation_id
        )

    async def log_user_action(
        self,
        actor_id: str,
        target_user_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> AuditEvent:
        """Log a user-related action."""
        event_type_map = {
            "login": EventType.USER_LOGIN,
            "logout": EventType.USER_LOGOUT,
            "login_failed": EventType.USER_LOGIN_FAILED,
            "created": EventType.USER_CREATED,
            "updated": EventType.USER_UPDATED,
            "trust_changed": EventType.USER_TRUST_CHANGED,
            "locked": EventType.USER_LOCKED,
            "unlocked": EventType.USER_UNLOCKED
        }

        event_type = event_type_map.get(action.lower(), EventType.SYSTEM_EVENT)
        priority = EventPriority.HIGH if "login_failed" in action.lower() else EventPriority.NORMAL

        return await self.log(
            event_type=event_type,
            actor_id=actor_id,
            action=f"User {action}",
            resource_type="user",
            resource_id=target_user_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            priority=priority
        )

    async def log_governance_action(
        self,
        actor_id: str,
        proposal_id: str,
        action: str,
        details: dict[str, Any] | None = None
    ) -> AuditEvent:
        """Log a governance-related action."""
        event_type_map = {
            "proposal_created": EventType.PROPOSAL_CREATED,
            "proposal_updated": EventType.PROPOSAL_UPDATED,
            "vote_cast": EventType.VOTE_CAST,
            "proposal_passed": EventType.PROPOSAL_PASSED,
            "proposal_rejected": EventType.PROPOSAL_REJECTED,
            "proposal_executed": EventType.PROPOSAL_EXECUTED
        }

        event_type = event_type_map.get(action.lower(), EventType.GOVERNANCE_EVENT)

        return await self.log(
            event_type=event_type,
            actor_id=actor_id,
            action=f"Governance: {action}",
            resource_type="proposal",
            resource_id=proposal_id,
            details=details,
            priority=EventPriority.HIGH
        )

    async def log_overlay_action(
        self,
        actor_id: str,
        overlay_id: str,
        action: str,
        details: dict[str, Any] | None = None
    ) -> AuditEvent:
        """Log an overlay-related action."""
        event_type_map = {
            "registered": EventType.OVERLAY_REGISTERED,
            "activated": EventType.OVERLAY_ACTIVATED,
            "deactivated": EventType.OVERLAY_DEACTIVATED,
            "executed": EventType.OVERLAY_EXECUTED,
            "error": EventType.OVERLAY_ERROR,
            "timeout": EventType.OVERLAY_TIMEOUT
        }

        event_type = event_type_map.get(action.lower(), EventType.OVERLAY_EVENT)
        priority = EventPriority.HIGH if action.lower() in ("error", "timeout") else EventPriority.NORMAL

        return await self.log(
            event_type=event_type,
            actor_id=actor_id,
            action=f"Overlay {action}",
            resource_type="overlay",
            resource_id=overlay_id,
            details=details,
            priority=priority
        )

    async def log_security_event(
        self,
        actor_id: str,
        event_name: str,
        details: dict[str, Any],
        resource_type: str = "security",
        resource_id: str | None = None,
        ip_address: str | None = None
    ) -> AuditEvent:
        """Log a security-related event (high priority)."""
        return await self.log(
            event_type=EventType.SECURITY_EVENT,
            actor_id=actor_id,
            action=f"Security: {event_name}",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            priority=EventPriority.CRITICAL,
            trust_level_required=TrustLevel.TRUSTED
        )

    async def log_immune_event(
        self,
        event_name: str,
        details: dict[str, Any],
        resource_type: str = "system",
        resource_id: str | None = None
    ) -> AuditEvent:
        """Log an immune system event."""
        return await self.log(
            event_type=EventType.IMMUNE_EVENT,
            actor_id="system:immune",
            action=f"Immune System: {event_name}",
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            priority=EventPriority.HIGH,
            trust_level_required=TrustLevel.TRUSTED
        )

    async def log_cascade_action(
        self,
        actor_id: str,
        cascade_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None
    ) -> AuditEvent:
        """Log a cascade-related action."""
        event_type_map = {
            "triggered": EventType.CASCADE_INITIATED,
            "propagated": EventType.CASCADE_PROPAGATED,
            "completed": EventType.CASCADE_COMPLETE
        }

        event_type = event_type_map.get(action.lower(), EventType.CASCADE_TRIGGERED)

        return await self.log(
            event_type=event_type,
            actor_id=actor_id,
            action=f"Cascade {action}",
            resource_type="cascade",
            resource_id=cascade_id,
            details=details,
            correlation_id=correlation_id,
            priority=EventPriority.NORMAL
        )

    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: str,
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None
    ) -> AuditEvent:
        """
        Generic action logging method.

        This is a convenience wrapper around the specific log methods.
        Routes to appropriate specialized logging based on entity_type.
        """
        if entity_type == "capsule":
            return await self.log_capsule_action(
                actor_id=user_id,
                capsule_id=entity_id,
                action=action,
                details=details,
                correlation_id=correlation_id
            )
        elif entity_type == "user":
            return await self.log_user_action(
                actor_id=user_id,
                target_user_id=entity_id,
                action=action,
                details=details
            )
        elif entity_type == "proposal":
            return await self.log_governance_action(
                actor_id=user_id,
                proposal_id=entity_id,
                action=action,
                details=details
            )
        elif entity_type == "overlay":
            return await self.log_overlay_action(
                actor_id=user_id,
                overlay_id=entity_id,
                action=action,
                details=details
            )
        elif entity_type == "cascade":
            return await self.log_cascade_action(
                actor_id=user_id,
                cascade_id=entity_id,
                action=action,
                details=details,
                correlation_id=correlation_id
            )
        else:
            # Generic logging for unknown entity types
            return await self.log(
                event_type=EventType.SYSTEM_EVENT,
                actor_id=user_id,
                action=action,
                resource_type=entity_type,
                resource_id=entity_id,
                details=details,
                correlation_id=correlation_id
            )

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_by_id(self, event_id: str) -> AuditEvent | None:
        """Get audit event by ID."""
        query = """
        MATCH (a:AuditLog {id: $id})
        RETURN a
        """
        record = await self.db.execute_single(query, {"id": event_id})
        return self._to_audit_event(record["a"]) if record else None

    async def get_by_correlation_id(self, correlation_id: str) -> list[AuditEvent]:
        """Get all events in a correlation chain."""
        query = """
        MATCH (a:AuditLog {correlation_id: $correlation_id})
        RETURN a
        ORDER BY a.timestamp ASC
        """
        records = await self.db.execute(query, {"correlation_id": correlation_id})
        return [self._to_audit_event(r["a"]) for r in records]

    async def get_by_actor(
        self,
        actor_id: str,
        limit: int = 100,
        offset: int = 0,
        since: datetime | None = None
    ) -> list[AuditEvent]:
        """Get audit events for a specific actor."""

        query = f"""
        MATCH (a:AuditLog {{actor_id: $actor_id}})
        {"WHERE a.timestamp >= datetime($since)" if since else ""}
        RETURN a
        ORDER BY a.timestamp DESC
        SKIP $offset
        LIMIT $limit
        """

        params = {
            "actor_id": actor_id,
            "limit": limit,
            "offset": offset
        }
        if since:
            params["since"] = since.isoformat()

        records = await self.db.execute(query, params)
        return [self._to_audit_event(r["a"]) for r in records]

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """Get audit events for a specific resource."""
        query = """
        MATCH (a:AuditLog {resource_type: $resource_type, resource_id: $resource_id})
        RETURN a
        ORDER BY a.timestamp DESC
        SKIP $offset
        LIMIT $limit
        """

        records = await self.db.execute(query, {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset
        })
        return [self._to_audit_event(r["a"]) for r in records]

    async def get_by_event_type(
        self,
        event_type: EventType,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100
    ) -> list[AuditEvent]:
        """Get audit events of a specific type within time range."""
        time_clauses = []
        if since:
            time_clauses.append("a.timestamp >= datetime($since)")
        if until:
            time_clauses.append("a.timestamp <= datetime($until)")

        where_clause = f"WHERE {' AND '.join(time_clauses)}" if time_clauses else ""

        query = f"""
        MATCH (a:AuditLog {{event_type: $event_type}})
        {where_clause}
        RETURN a
        ORDER BY a.timestamp DESC
        LIMIT $limit
        """

        params = {
            "event_type": event_type.value,
            "limit": limit
        }
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        records = await self.db.execute(query, params)
        return [self._to_audit_event(r["a"]) for r in records]

    async def search(
        self,
        query_text: str,
        event_types: list[EventType] | None = None,
        actor_ids: list[str] | None = None,
        resource_types: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        priority: EventPriority | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditEvent]:
        """
        Search audit logs with multiple filters.

        Full-text search on action field with optional filters.
        """
        conditions = ["a.action CONTAINS $query_text"]

        if event_types:
            conditions.append("a.event_type IN $event_types")
        if actor_ids:
            conditions.append("a.actor_id IN $actor_ids")
        if resource_types:
            conditions.append("a.resource_type IN $resource_types")
        if since:
            conditions.append("a.timestamp >= datetime($since)")
        if until:
            conditions.append("a.timestamp <= datetime($until)")
        if priority:
            conditions.append("a.priority >= $priority")

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (a:AuditLog)
        WHERE {where_clause}
        RETURN a
        ORDER BY a.timestamp DESC
        SKIP $offset
        LIMIT $limit
        """

        params = {
            "query_text": query_text,
            "limit": limit,
            "offset": offset
        }
        if event_types:
            params["event_types"] = [et.value for et in event_types]
        if actor_ids:
            params["actor_ids"] = actor_ids
        if resource_types:
            params["resource_types"] = resource_types
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        if priority:
            params["priority"] = priority.value

        records = await self.db.execute(query, params)
        return [self._to_audit_event(r["a"]) for r in records]

    # =========================================================================
    # Analytics & Reporting
    # =========================================================================

    async def get_activity_summary(
        self,
        since: datetime,
        until: datetime | None = None
    ) -> dict[str, Any]:
        """Get summary statistics for audit activity."""
        until = until or datetime.now(UTC)

        query = """
        MATCH (a:AuditLog)
        WHERE a.timestamp >= datetime($since) AND a.timestamp <= datetime($until)
        RETURN
            count(a) as total_events,
            count(DISTINCT a.actor_id) as unique_actors,
            count(DISTINCT a.resource_id) as unique_resources,
            collect(DISTINCT a.event_type) as event_types,
            collect(DISTINCT a.resource_type) as resource_types
        """

        record = await self.db.execute_single(query, {
            "since": since.isoformat(),
            "until": until.isoformat()
        })

        if not record:
            return {
                "total_events": 0,
                "unique_actors": 0,
                "unique_resources": 0,
                "event_types": [],
                "resource_types": [],
                "period_start": since.isoformat(),
                "period_end": until.isoformat()
            }

        return {
            "total_events": record["total_events"],
            "unique_actors": record["unique_actors"],
            "unique_resources": record["unique_resources"],
            "event_types": record["event_types"],
            "resource_types": record["resource_types"],
            "period_start": since.isoformat(),
            "period_end": until.isoformat()
        }

    async def get_event_counts_by_type(
        self,
        since: datetime,
        until: datetime | None = None
    ) -> dict[str, int]:
        """Get event counts grouped by type."""
        until = until or datetime.now(UTC)

        query = """
        MATCH (a:AuditLog)
        WHERE a.timestamp >= datetime($since) AND a.timestamp <= datetime($until)
        RETURN a.event_type as event_type, count(a) as count
        ORDER BY count DESC
        """

        records = await self.db.execute(query, {
            "since": since.isoformat(),
            "until": until.isoformat()
        })

        return {r["event_type"]: r["count"] for r in records}

    async def get_actor_activity(
        self,
        since: datetime,
        until: datetime | None = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get most active actors in time period."""
        until = until or datetime.now(UTC)

        query = """
        MATCH (a:AuditLog)
        WHERE a.timestamp >= datetime($since) AND a.timestamp <= datetime($until)
        RETURN a.actor_id as actor_id, count(a) as event_count
        ORDER BY event_count DESC
        LIMIT $limit
        """

        records = await self.db.execute(query, {
            "since": since.isoformat(),
            "until": until.isoformat(),
            "limit": limit
        })

        return [{"actor_id": r["actor_id"], "event_count": r["event_count"]} for r in records]

    async def get_failed_logins(
        self,
        since: datetime,
        threshold: int = 3
    ) -> list[dict[str, Any]]:
        """Get actors with multiple failed login attempts (security concern)."""
        query = """
        MATCH (a:AuditLog {event_type: $event_type})
        WHERE a.timestamp >= datetime($since)
        WITH a.actor_id as actor_id,
             count(a) as attempt_count,
             collect(a.ip_address) as ip_addresses,
             max(a.timestamp) as last_attempt
        WHERE attempt_count >= $threshold
        RETURN actor_id, attempt_count, ip_addresses, last_attempt
        ORDER BY attempt_count DESC
        """

        records = await self.db.execute(query, {
            "event_type": EventType.USER_LOGIN_FAILED.value,
            "since": since.isoformat(),
            "threshold": threshold
        })

        return [
            {
                "actor_id": r["actor_id"],
                "attempt_count": r["attempt_count"],
                "ip_addresses": list({ip for ip in r["ip_addresses"] if ip}),
                "last_attempt": r["last_attempt"]
            }
            for r in records
        ]

    async def get_security_events(
        self,
        since: datetime,
        until: datetime | None = None
    ) -> list[AuditEvent]:
        """Get all security-related events (for security review)."""

        return await self.get_by_event_type(
            event_type=EventType.SECURITY_EVENT,
            since=since,
            until=until,
            limit=1000
        )

    # =========================================================================
    # Maintenance Operations
    # =========================================================================

    async def purge_old_events(
        self,
        older_than: datetime,
        keep_security_events: bool = True,
        keep_critical: bool = True
    ) -> int:
        """
        Purge audit events older than specified date.

        Args:
            older_than: Delete events before this date
            keep_security_events: If True, keep security events regardless of age
            keep_critical: If True, keep CRITICAL priority events

        Returns:
            Number of deleted events
        """
        exclusions = []
        if keep_security_events:
            exclusions.append("a.event_type <> $security_type")
        if keep_critical:
            exclusions.append("a.priority < $critical_priority")

        exclusion_clause = f"AND ({' AND '.join(exclusions)})" if exclusions else ""

        query = f"""
        MATCH (a:AuditLog)
        WHERE a.timestamp < datetime($older_than)
        {exclusion_clause}
        WITH a LIMIT 10000
        DETACH DELETE a
        RETURN count(*) as deleted_count
        """

        params = {"older_than": older_than.isoformat()}
        if keep_security_events:
            params["security_type"] = EventType.SECURITY_EVENT.value
        if keep_critical:
            params["critical_priority"] = EventPriority.CRITICAL.value

        record = await self.db.execute_single(query, params)
        return record["deleted_count"] if record else 0

    async def archive_events(
        self,
        older_than: datetime,
        archive_label: str = "ArchivedAuditLog"
    ) -> int:
        """
        Archive old events by adding an archive label.

        Archived events can still be queried but are excluded from normal queries.

        SECURITY FIX (Audit 4 - M14): Validate archive_label to prevent label injection.
        """
        import re

        # SECURITY FIX (Audit 4 - M14): Validate label format
        # Labels must be alphanumeric with underscores only, max 100 chars
        if not archive_label or len(archive_label) > 100:
            raise ValueError("archive_label must be 1-100 characters")
        if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', archive_label):
            raise ValueError("archive_label must start with letter and contain only alphanumeric/underscore")

        query = f"""
        MATCH (a:AuditLog)
        WHERE a.timestamp < datetime($older_than)
        AND NOT a:{archive_label}
        WITH a LIMIT 10000
        SET a:{archive_label}
        RETURN count(a) as archived_count
        """

        record = await self.db.execute_single(query, {
            "older_than": older_than.isoformat()
        })
        return record["archived_count"] if record else 0

    async def count_events(
        self,
        since: datetime | None = None,
        until: datetime | None = None
    ) -> int:
        """Count total audit events in time range."""
        conditions = []
        if since:
            conditions.append("a.timestamp >= datetime($since)")
        if until:
            conditions.append("a.timestamp <= datetime($until)")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (a:AuditLog)
        {where_clause}
        RETURN count(a) as total
        """

        params = {}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        record = await self.db.execute_single(query, params)
        return record["total"] if record else 0

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _to_audit_event(self, node: dict[str, Any]) -> AuditEvent:
        """Convert Neo4j node to AuditEvent model."""
        import json

        # Parse JSON fields
        details = None
        if node.get("details"):
            try:
                details = json.loads(node["details"])
            except (json.JSONDecodeError, TypeError):
                details = {"raw": node["details"]}

        old_value = None
        if node.get("old_value"):
            try:
                old_value = json.loads(node["old_value"])
            except (json.JSONDecodeError, TypeError):
                old_value = {"raw": node["old_value"]}

        new_value = None
        if node.get("new_value"):
            try:
                new_value = json.loads(node["new_value"])
            except (json.JSONDecodeError, TypeError):
                new_value = {"raw": node["new_value"]}

        # Handle datetime conversion
        timestamp_raw = node.get("timestamp")
        timestamp: datetime
        if hasattr(timestamp_raw, 'to_native'):
            timestamp = timestamp_raw.to_native()  # type: ignore[union-attr]
        elif isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace('Z', '+00:00'))
        elif isinstance(timestamp_raw, datetime):
            timestamp = timestamp_raw
        else:
            timestamp = datetime.now(UTC)

        return AuditEvent(
            id=node["id"],
            event_type=EventType(node["event_type"]),
            actor_id=node["actor_id"],
            action=node["action"],
            resource_type=node["resource_type"],
            resource_id=node.get("resource_id"),
            details=details or {},
            old_value=old_value,
            new_value=new_value,
            ip_address=node.get("ip_address"),
            user_agent=node.get("user_agent"),
            correlation_id=node.get("correlation_id"),
            priority=EventPriority(node.get("priority", EventPriority.LOW.value)),
            timestamp=timestamp
        )

    async def list_events(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[AuditEvent], int]:
        """
        List audit events with filtering and pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum records to return
            filters: Optional filters (action, entity_type, user_id)

        Returns:
            Tuple of (events list, total count)
        """
        filters = filters or {}
        conditions = []
        params = {"offset": offset, "limit": limit}

        if filters.get("action"):
            conditions.append("a.action CONTAINS $action")
            params["action"] = filters["action"]

        if filters.get("entity_type"):
            conditions.append("a.resource_type = $entity_type")
            params["entity_type"] = filters["entity_type"]

        if filters.get("user_id"):
            conditions.append("a.actor_id = $user_id")
            params["user_id"] = filters["user_id"]

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Get count
        count_query = f"""
        MATCH (a:AuditLog)
        {where_clause}
        RETURN count(a) AS total
        """
        count_result = await self.db.execute_single(count_query, params)
        total = count_result["total"] if count_result else 0

        # Get events
        query = f"""
        MATCH (a:AuditLog)
        {where_clause}
        RETURN a
        ORDER BY a.timestamp DESC
        SKIP $offset
        LIMIT $limit
        """

        records = await self.db.execute(query, params)
        events = [self._to_audit_event(r["a"]) for r in records]

        return events, total

    # =========================================================================
    # SECURITY FIX (Audit 3): Bulk Operation & Data Export Logging
    # =========================================================================

    async def log_bulk_operation(
        self,
        actor_id: str,
        operation: str,
        resource_type: str,
        resource_count: int,
        resource_ids: list[str] | None = None,
        details: dict[str, Any] | None = None,
        correlation_id: str | None = None
    ) -> AuditEvent:
        """
        SECURITY FIX (Audit 3): Log bulk operations for audit compliance.

        Tracks operations that affect multiple resources at once,
        such as bulk delete, bulk update, or batch imports.

        Args:
            actor_id: User performing the bulk operation
            operation: Type of bulk operation (bulk_delete, bulk_update, batch_import)
            resource_type: Type of resources affected
            resource_count: Number of resources affected
            resource_ids: Optional list of affected resource IDs (truncated if >100)
            details: Additional operation details
            correlation_id: For linking related events

        Returns:
            Created AuditEvent
        """
        # Truncate resource_ids if too many
        truncated_ids = None
        if resource_ids:
            truncated_ids = resource_ids[:100] if len(resource_ids) > 100 else resource_ids

        full_details = {
            "operation": operation,
            "resource_count": resource_count,
            "resource_ids": truncated_ids,
            "ids_truncated": len(resource_ids) > 100 if resource_ids else False,
            **(details or {})
        }

        return await self.log(
            event_type=EventType.SYSTEM_EVENT,
            actor_id=actor_id,
            action=f"Bulk {operation}",
            resource_type=resource_type,
            resource_id=f"bulk:{resource_count}",
            details=full_details,
            correlation_id=correlation_id,
            priority=EventPriority.HIGH  # Bulk ops are high priority
        )

    async def log_data_export(
        self,
        actor_id: str,
        export_type: str,
        resource_type: str,
        record_count: int,
        format: str,
        filters_applied: dict[str, Any] | None = None,
        destination: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> AuditEvent:
        """
        SECURITY FIX (Audit 3): Log data export operations for compliance.

        Tracks all data exports for GDPR/compliance requirements.

        Args:
            actor_id: User performing the export
            export_type: Type of export (user_data, capsules, audit_logs, reports)
            resource_type: Type of data being exported
            record_count: Number of records exported
            format: Export format (csv, json, xlsx, pdf)
            filters_applied: Filters used to select the data
            destination: Where data was exported to (email, download, api)
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Created AuditEvent
        """
        details = {
            "export_type": export_type,
            "record_count": record_count,
            "format": format,
            "filters_applied": filters_applied or {},
            "destination": destination or "download"
        }

        return await self.log(
            event_type=EventType.SYSTEM_EVENT,
            actor_id=actor_id,
            action=f"Data export: {export_type}",
            resource_type=resource_type,
            resource_id=f"export:{record_count}",
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            priority=EventPriority.HIGH  # Data exports are high priority for compliance
        )

    async def log_maintenance_mode(
        self,
        actor_id: str,
        action: str,
        reason: str | None = None,
        duration_minutes: int | None = None,
        affected_services: list[str] | None = None
    ) -> AuditEvent:
        """
        SECURITY FIX (Audit 3): Log maintenance mode changes.

        Args:
            actor_id: User who changed maintenance mode
            action: Action taken (enabled, disabled, extended)
            reason: Reason for maintenance
            duration_minutes: Expected duration
            affected_services: List of affected services

        Returns:
            Created AuditEvent
        """
        details = {
            "reason": reason,
            "duration_minutes": duration_minutes,
            "affected_services": affected_services or ["all"]
        }

        return await self.log(
            event_type=EventType.SYSTEM_EVENT,
            actor_id=actor_id,
            action=f"Maintenance mode {action}",
            resource_type="system",
            resource_id="maintenance_mode",
            details=details,
            priority=EventPriority.CRITICAL  # Maintenance mode is critical
        )

    async def log_self_audit(
        self,
        actor_id: str,
        action: str,
        target_audit_ids: list[str] | None = None,
        details: dict[str, Any] | None = None
    ) -> AuditEvent:
        """
        SECURITY FIX (Audit 3): Self-audit logging for audit log operations.

        Tracks operations on the audit log itself (purge, archive, export).

        Args:
            actor_id: User performing the audit log operation
            action: Action on audit logs (purge, archive, export, query)
            target_audit_ids: IDs of affected audit entries
            details: Additional details

        Returns:
            Created AuditEvent
        """
        full_details = {
            "target_count": len(target_audit_ids) if target_audit_ids else 0,
            "target_sample": target_audit_ids[:10] if target_audit_ids else [],
            **(details or {})
        }

        return await self.log(
            event_type=EventType.SECURITY_EVENT,  # Use security event type
            actor_id=actor_id,
            action=f"Audit log {action}",
            resource_type="audit_log",
            resource_id="self",
            details=full_details,
            priority=EventPriority.CRITICAL  # Self-audit is critical
        )


# Convenience factory
def get_audit_repository(db: Neo4jClient) -> AuditRepository:
    """Get audit repository instance."""
    return AuditRepository(db)
