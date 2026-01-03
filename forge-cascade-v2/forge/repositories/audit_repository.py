"""
Audit Repository for Forge Cascade V2

Provides comprehensive audit logging for all system actions,
changes, and events. Supports compliance, forensics, and
the Immune System's anomaly detection.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from ..models.base import TrustLevel
from ..models.events import AuditEvent, EventType, EventPriority
from ..database.client import Neo4jClient


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
        resource_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
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
        now = datetime.utcnow()
        
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
        details: Optional[dict[str, Any]] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None
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
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
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
        priority = EventPriority.HIGH if "login_failed" in action.lower() else EventPriority.MEDIUM
        
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
        details: Optional[dict[str, Any]] = None
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
        details: Optional[dict[str, Any]] = None
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
        priority = EventPriority.HIGH if action.lower() in ("error", "timeout") else EventPriority.MEDIUM
        
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
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None
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
        resource_id: Optional[str] = None
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
    
    # =========================================================================
    # Query Operations
    # =========================================================================
    
    async def get_by_id(self, event_id: str) -> Optional[AuditEvent]:
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
        since: Optional[datetime] = None
    ) -> list[AuditEvent]:
        """Get audit events for a specific actor."""
        since_clause = "AND a.timestamp >= datetime($since)" if since else ""
        
        query = f"""
        MATCH (a:AuditLog {{actor_id: $actor_id}})
        {f"WHERE a.timestamp >= datetime($since)" if since else ""}
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
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
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
        event_types: Optional[list[EventType]] = None,
        actor_ids: Optional[list[str]] = None,
        resource_types: Optional[list[str]] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        priority: Optional[EventPriority] = None,
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
        until: Optional[datetime] = None
    ) -> dict[str, Any]:
        """Get summary statistics for audit activity."""
        until = until or datetime.utcnow()
        
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
        until: Optional[datetime] = None
    ) -> dict[str, int]:
        """Get event counts grouped by type."""
        until = until or datetime.utcnow()
        
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
        until: Optional[datetime] = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get most active actors in time period."""
        until = until or datetime.utcnow()
        
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
                "ip_addresses": list(set(ip for ip in r["ip_addresses"] if ip)),
                "last_attempt": r["last_attempt"]
            }
            for r in records
        ]
    
    async def get_security_events(
        self,
        since: datetime,
        until: Optional[datetime] = None
    ) -> list[AuditEvent]:
        """Get all security-related events (for security review)."""
        security_types = [
            EventType.USER_LOGIN_FAILED,
            EventType.USER_LOCKED,
            EventType.SECURITY_EVENT,
            EventType.USER_TRUST_CHANGED
        ]
        
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
        """
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
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
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
    
    def _to_audit_event(self, node: dict) -> AuditEvent:
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
        timestamp = node.get("timestamp")
        if hasattr(timestamp, 'to_native'):
            timestamp = timestamp.to_native()
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        return AuditEvent(
            id=node["id"],
            event_type=EventType(node["event_type"]),
            actor_id=node["actor_id"],
            action=node["action"],
            resource_type=node["resource_type"],
            resource_id=node.get("resource_id"),
            details=details,
            old_value=old_value,
            new_value=new_value,
            ip_address=node.get("ip_address"),
            user_agent=node.get("user_agent"),
            correlation_id=node.get("correlation_id"),
            priority=EventPriority(node.get("priority", EventPriority.LOW.value)),
            timestamp=timestamp
        )


# Convenience factory
def get_audit_repository(db: Neo4jClient) -> AuditRepository:
    """Get audit repository instance."""
    return AuditRepository(db)

    async def list(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: dict | None = None,
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
