"""
Audit Repository Tests for Forge Cascade V2

Comprehensive tests for the AuditRepository including:
- Core audit logging operations
- Specialized logging methods (capsule, user, governance, etc.)
- Query operations
- Analytics and reporting
- Maintenance operations
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.database.client import Neo4jClient
from forge.models.base import TrustLevel
from forge.models.events import AuditEvent, EventPriority, EventType
from forge.repositories.audit_repository import AuditRepository, get_audit_repository


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock(spec=Neo4jClient)
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def audit_repository(mock_db_client):
    """Create AuditRepository with mock client."""
    return AuditRepository(mock_db_client)


@pytest.fixture
def sample_audit_node():
    """Sample audit node data from Neo4j."""
    return {
        "id": "audit-123",
        "event_type": "capsule.created",
        "actor_id": "user-001",
        "action": "Capsule create",
        "resource_type": "capsule",
        "resource_id": "capsule-001",
        "details": json.dumps({"title": "Test Capsule"}),
        "old_value": None,
        "new_value": json.dumps({"title": "Test Capsule", "content": "Test content"}),
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0",
        "correlation_id": "corr-123",
        "priority": "normal",
        "trust_level_required": 60,
        "timestamp": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Core Audit Logging Tests
# =============================================================================


class TestAuditRepositoryLog:
    """Tests for core log method."""

    @pytest.mark.asyncio
    async def test_log_creates_audit_event(self, audit_repository, mock_db_client, sample_audit_node):
        """Log creates an audit event."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log(
            event_type=EventType.CAPSULE_CREATED,
            actor_id="user-001",
            action="Capsule create",
            resource_type="capsule",
            resource_id="capsule-001",
        )

        assert isinstance(result, AuditEvent)
        assert result.action == "Capsule create"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_with_details(self, audit_repository, mock_db_client, sample_audit_node):
        """Log includes details as JSON."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        await audit_repository.log(
            event_type=EventType.CAPSULE_CREATED,
            actor_id="user-001",
            action="Create",
            resource_type="capsule",
            details={"title": "Test", "tags": ["a", "b"]},
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        details = json.loads(params["details"])
        assert details["title"] == "Test"
        assert details["tags"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_log_with_old_new_values(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log includes old and new values."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        await audit_repository.log(
            event_type=EventType.CAPSULE_UPDATED,
            actor_id="user-001",
            action="Update",
            resource_type="capsule",
            old_value={"title": "Old Title"},
            new_value={"title": "New Title"},
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert json.loads(params["old_value"]) == {"title": "Old Title"}
        assert json.loads(params["new_value"]) == {"title": "New Title"}

    @pytest.mark.asyncio
    async def test_log_generates_correlation_id(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log generates correlation_id if not provided."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        await audit_repository.log(
            event_type=EventType.SYSTEM_EVENT,
            actor_id="user-001",
            action="Test",
            resource_type="test",
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["correlation_id"] is not None

    @pytest.mark.asyncio
    async def test_log_raises_on_failure(self, audit_repository, mock_db_client):
        """Log raises RuntimeError on failure."""
        mock_db_client.execute_single.return_value = None

        with pytest.raises(RuntimeError, match="Failed to create audit event"):
            await audit_repository.log(
                event_type=EventType.SYSTEM_EVENT,
                actor_id="user-001",
                action="Test",
                resource_type="test",
            )


# =============================================================================
# Specialized Logging Tests
# =============================================================================


class TestCapsuleActionLogging:
    """Tests for log_capsule_action method."""

    @pytest.mark.asyncio
    async def test_log_capsule_create(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log capsule create action."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_capsule_action(
            actor_id="user-001",
            capsule_id="capsule-001",
            action="create",
        )

        assert result.event_type == EventType.CAPSULE_CREATED

    @pytest.mark.asyncio
    async def test_log_capsule_update(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log capsule update action."""
        sample_audit_node["event_type"] = "capsule.updated"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_capsule_action(
            actor_id="user-001",
            capsule_id="capsule-001",
            action="update",
            old_value={"title": "Old"},
            new_value={"title": "New"},
        )

        assert result.event_type == EventType.CAPSULE_UPDATED

    @pytest.mark.asyncio
    async def test_log_capsule_fork(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log capsule fork action."""
        sample_audit_node["event_type"] = "capsule.forked"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_capsule_action(
            actor_id="user-001",
            capsule_id="capsule-001",
            action="fork",
        )

        assert result.event_type == EventType.CAPSULE_FORKED

    @pytest.mark.asyncio
    async def test_log_capsule_unknown_action(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log unknown capsule action defaults to SYSTEM_EVENT."""
        sample_audit_node["event_type"] = "system.event"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_capsule_action(
            actor_id="user-001",
            capsule_id="capsule-001",
            action="unknown_action",
        )

        assert result.event_type == EventType.SYSTEM_EVENT


class TestUserActionLogging:
    """Tests for log_user_action method."""

    @pytest.mark.asyncio
    async def test_log_user_login(self, audit_repository, mock_db_client, sample_audit_node):
        """Log user login action."""
        sample_audit_node["event_type"] = "user.login"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_user_action(
            actor_id="user-001",
            target_user_id="user-001",
            action="login",
            ip_address="192.168.1.1",
        )

        assert result.event_type == EventType.USER_LOGIN

    @pytest.mark.asyncio
    async def test_log_user_login_failed_high_priority(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log failed login with high priority."""
        sample_audit_node["event_type"] = "user.login_failed"
        sample_audit_node["priority"] = "high"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_user_action(
            actor_id="user-001",
            target_user_id="user-001",
            action="login_failed",
        )

        assert result.event_type == EventType.USER_LOGIN_FAILED


class TestGovernanceActionLogging:
    """Tests for log_governance_action method."""

    @pytest.mark.asyncio
    async def test_log_proposal_created(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log proposal creation."""
        sample_audit_node["event_type"] = "governance.proposal_created"
        sample_audit_node["priority"] = "high"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_governance_action(
            actor_id="user-001",
            proposal_id="proposal-001",
            action="proposal_created",
        )

        assert result.event_type == EventType.PROPOSAL_CREATED

    @pytest.mark.asyncio
    async def test_log_vote_cast(self, audit_repository, mock_db_client, sample_audit_node):
        """Log vote cast action."""
        sample_audit_node["event_type"] = "governance.vote"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_governance_action(
            actor_id="user-001",
            proposal_id="proposal-001",
            action="vote_cast",
            details={"vote": "yes", "weight": 100},
        )

        assert result.event_type == EventType.VOTE_CAST


class TestOverlayActionLogging:
    """Tests for log_overlay_action method."""

    @pytest.mark.asyncio
    async def test_log_overlay_registered(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log overlay registration."""
        sample_audit_node["event_type"] = "overlay.registered"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_overlay_action(
            actor_id="system",
            overlay_id="overlay-001",
            action="registered",
        )

        assert result.event_type == EventType.OVERLAY_REGISTERED

    @pytest.mark.asyncio
    async def test_log_overlay_error_high_priority(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log overlay error with high priority."""
        sample_audit_node["event_type"] = "overlay.error"
        sample_audit_node["priority"] = "high"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_overlay_action(
            actor_id="system",
            overlay_id="overlay-001",
            action="error",
            details={"error": "Connection failed"},
        )

        assert result.event_type == EventType.OVERLAY_ERROR


class TestSecurityEventLogging:
    """Tests for log_security_event method."""

    @pytest.mark.asyncio
    async def test_log_security_event(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log security event with critical priority."""
        sample_audit_node["event_type"] = "security.event"
        sample_audit_node["priority"] = "critical"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_security_event(
            actor_id="system:immune",
            event_name="Suspicious activity detected",
            details={"threat_level": "high", "source": "192.168.1.100"},
        )

        assert result.event_type == EventType.SECURITY_EVENT


class TestImmuneEventLogging:
    """Tests for log_immune_event method."""

    @pytest.mark.asyncio
    async def test_log_immune_event(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log immune system event."""
        sample_audit_node["event_type"] = "immune.event"
        sample_audit_node["actor_id"] = "system:immune"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_immune_event(
            event_name="Anomaly detected",
            details={"anomaly_type": "rate_limit", "threshold": 100},
        )

        assert result.event_type == EventType.IMMUNE_EVENT


class TestCascadeActionLogging:
    """Tests for log_cascade_action method."""

    @pytest.mark.asyncio
    async def test_log_cascade_triggered(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log cascade triggered action."""
        sample_audit_node["event_type"] = "cascade.initiated"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_cascade_action(
            actor_id="overlay-001",
            cascade_id="cascade-001",
            action="triggered",
        )

        assert result.event_type == EventType.CASCADE_INITIATED


class TestGenericActionLogging:
    """Tests for log_action method."""

    @pytest.mark.asyncio
    async def test_log_action_routes_to_capsule(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """log_action routes capsule entity to log_capsule_action."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_action(
            action="create",
            entity_type="capsule",
            entity_id="capsule-001",
            user_id="user-001",
        )

        assert result.resource_type == "capsule"

    @pytest.mark.asyncio
    async def test_log_action_routes_to_user(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """log_action routes user entity to log_user_action."""
        sample_audit_node["resource_type"] = "user"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_action(
            action="login",
            entity_type="user",
            entity_id="user-001",
            user_id="user-001",
        )

        assert result.resource_type == "user"

    @pytest.mark.asyncio
    async def test_log_action_generic_entity(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """log_action handles unknown entity types."""
        sample_audit_node["resource_type"] = "custom"
        sample_audit_node["event_type"] = "system.event"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_action(
            action="custom_action",
            entity_type="custom",
            entity_id="custom-001",
            user_id="user-001",
        )

        assert result.event_type == EventType.SYSTEM_EVENT


# =============================================================================
# Query Operations Tests
# =============================================================================


class TestAuditRepositoryQueries:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_get_by_id(self, audit_repository, mock_db_client, sample_audit_node):
        """Get audit event by ID."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.get_by_id("audit-123")

        assert result is not None
        assert result.id == "audit-123"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, audit_repository, mock_db_client):
        """Get by ID returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await audit_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_correlation_id(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get events by correlation ID."""
        mock_db_client.execute.return_value = [
            {"a": sample_audit_node},
            {"a": {**sample_audit_node, "id": "audit-456"}},
        ]

        result = await audit_repository.get_by_correlation_id("corr-123")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_actor(self, audit_repository, mock_db_client, sample_audit_node):
        """Get events by actor ID."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        result = await audit_repository.get_by_actor("user-001")

        assert len(result) == 1
        assert result[0].actor_id == "user-001"

    @pytest.mark.asyncio
    async def test_get_by_actor_with_since(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get events by actor with time filter."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]
        since = datetime.now(UTC) - timedelta(hours=1)

        await audit_repository.get_by_actor("user-001", since=since)

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "datetime($since)" in query
        assert "since" in params

    @pytest.mark.asyncio
    async def test_get_by_actor_caps_limit(self, audit_repository, mock_db_client):
        """Get by actor caps limit at 1000."""
        mock_db_client.execute.return_value = []

        await audit_repository.get_by_actor("user-001", limit=5000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 1000

    @pytest.mark.asyncio
    async def test_get_by_resource(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get events by resource."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        result = await audit_repository.get_by_resource("capsule", "capsule-001")

        assert len(result) == 1
        assert result[0].resource_id == "capsule-001"

    @pytest.mark.asyncio
    async def test_get_by_event_type(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get events by event type."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        result = await audit_repository.get_by_event_type(EventType.CAPSULE_CREATED)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_by_event_type_with_time_range(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get events by type with time range."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]
        since = datetime.now(UTC) - timedelta(days=1)
        until = datetime.now(UTC)

        await audit_repository.get_by_event_type(
            EventType.CAPSULE_CREATED, since=since, until=until
        )

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "datetime($since)" in query
        assert "datetime($until)" in query


class TestAuditRepositorySearch:
    """Tests for search operation."""

    @pytest.mark.asyncio
    async def test_search_by_query_text(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Search by query text."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        result = await audit_repository.search("Capsule")

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "a.action CONTAINS" in query

    @pytest.mark.asyncio
    async def test_search_with_event_types_filter(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Search with event types filter."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        await audit_repository.search(
            "test",
            event_types=[EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED],
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert "capsule.created" in params["event_types"]
        assert "capsule.updated" in params["event_types"]

    @pytest.mark.asyncio
    async def test_search_with_actor_filter(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Search with actor IDs filter."""
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        await audit_repository.search("test", actor_ids=["user-001", "user-002"])

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "a.actor_id IN $actor_ids" in query
        assert params["actor_ids"] == ["user-001", "user-002"]

    @pytest.mark.asyncio
    async def test_search_with_pagination(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Search with pagination."""
        mock_db_client.execute.return_value = []

        await audit_repository.search("test", limit=50, offset=100)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 50
        assert params["offset"] == 100


# =============================================================================
# Analytics Tests
# =============================================================================


class TestAuditRepositoryAnalytics:
    """Tests for analytics operations."""

    @pytest.mark.asyncio
    async def test_get_activity_summary(self, audit_repository, mock_db_client):
        """Get activity summary."""
        mock_db_client.execute_single.return_value = {
            "total_events": 100,
            "unique_actors": 10,
            "unique_resources": 50,
            "event_types": ["capsule.created", "user.login"],
            "resource_types": ["capsule", "user"],
        }
        since = datetime.now(UTC) - timedelta(days=7)

        result = await audit_repository.get_activity_summary(since)

        assert result["total_events"] == 100
        assert result["unique_actors"] == 10
        assert "period_start" in result
        assert "period_end" in result

    @pytest.mark.asyncio
    async def test_get_activity_summary_empty(self, audit_repository, mock_db_client):
        """Get activity summary returns defaults when empty."""
        mock_db_client.execute_single.return_value = None
        since = datetime.now(UTC) - timedelta(days=7)

        result = await audit_repository.get_activity_summary(since)

        assert result["total_events"] == 0
        assert result["unique_actors"] == 0

    @pytest.mark.asyncio
    async def test_get_event_counts_by_type(self, audit_repository, mock_db_client):
        """Get event counts by type."""
        mock_db_client.execute.return_value = [
            {"event_type": "capsule.created", "count": 50},
            {"event_type": "user.login", "count": 30},
        ]
        since = datetime.now(UTC) - timedelta(days=7)

        result = await audit_repository.get_event_counts_by_type(since)

        assert result["capsule.created"] == 50
        assert result["user.login"] == 30

    @pytest.mark.asyncio
    async def test_get_actor_activity(self, audit_repository, mock_db_client):
        """Get most active actors."""
        mock_db_client.execute.return_value = [
            {"actor_id": "user-001", "event_count": 100},
            {"actor_id": "user-002", "event_count": 50},
        ]
        since = datetime.now(UTC) - timedelta(days=7)

        result = await audit_repository.get_actor_activity(since)

        assert len(result) == 2
        assert result[0]["actor_id"] == "user-001"
        assert result[0]["event_count"] == 100

    @pytest.mark.asyncio
    async def test_get_actor_activity_caps_limit(self, audit_repository, mock_db_client):
        """Get actor activity caps limit at 500."""
        mock_db_client.execute.return_value = []
        since = datetime.now(UTC) - timedelta(days=7)

        await audit_repository.get_actor_activity(since, limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 500

    @pytest.mark.asyncio
    async def test_get_failed_logins(self, audit_repository, mock_db_client):
        """Get actors with failed logins above threshold."""
        mock_db_client.execute.return_value = [
            {
                "actor_id": "user-001",
                "attempt_count": 5,
                "ip_addresses": ["192.168.1.1", "192.168.1.2"],
                "last_attempt": datetime.now(UTC),
            }
        ]
        since = datetime.now(UTC) - timedelta(hours=1)

        result = await audit_repository.get_failed_logins(since, threshold=3)

        assert len(result) == 1
        assert result[0]["attempt_count"] == 5

    @pytest.mark.asyncio
    async def test_get_security_events(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Get security events."""
        sample_audit_node["event_type"] = "security.event"
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]
        since = datetime.now(UTC) - timedelta(days=1)

        result = await audit_repository.get_security_events(since)

        assert len(result) == 1


# =============================================================================
# Maintenance Operations Tests
# =============================================================================


class TestAuditRepositoryMaintenance:
    """Tests for maintenance operations."""

    @pytest.mark.asyncio
    async def test_purge_old_events(self, audit_repository, mock_db_client):
        """Purge old events."""
        mock_db_client.execute_single.return_value = {"deleted_count": 100}
        older_than = datetime.now(UTC) - timedelta(days=90)

        result = await audit_repository.purge_old_events(older_than)

        assert result == 100

    @pytest.mark.asyncio
    async def test_purge_keeps_security_events(self, audit_repository, mock_db_client):
        """Purge keeps security events when configured."""
        mock_db_client.execute_single.return_value = {"deleted_count": 50}
        older_than = datetime.now(UTC) - timedelta(days=90)

        await audit_repository.purge_old_events(
            older_than, keep_security_events=True, keep_critical=True
        )

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "a.event_type <> $security_type" in query
        assert "a.priority < $critical_priority" in query

    @pytest.mark.asyncio
    async def test_archive_events(self, audit_repository, mock_db_client):
        """Archive old events."""
        mock_db_client.execute_single.return_value = {"archived_count": 500}
        older_than = datetime.now(UTC) - timedelta(days=30)

        result = await audit_repository.archive_events(older_than)

        assert result == 500

    @pytest.mark.asyncio
    async def test_archive_events_validates_label(self, audit_repository, mock_db_client):
        """Archive events validates archive label."""
        older_than = datetime.now(UTC) - timedelta(days=30)

        with pytest.raises(ValueError, match="archive_label"):
            await audit_repository.archive_events(older_than, archive_label="Invalid-Label!")

    @pytest.mark.asyncio
    async def test_archive_events_rejects_too_long_label(
        self, audit_repository, mock_db_client
    ):
        """Archive events rejects label over 100 chars."""
        older_than = datetime.now(UTC) - timedelta(days=30)

        with pytest.raises(ValueError, match="1-100 characters"):
            await audit_repository.archive_events(
                older_than, archive_label="A" * 101
            )

    @pytest.mark.asyncio
    async def test_count_events(self, audit_repository, mock_db_client):
        """Count total events."""
        mock_db_client.execute_single.return_value = {"total": 1000}

        result = await audit_repository.count_events()

        assert result == 1000

    @pytest.mark.asyncio
    async def test_count_events_with_time_range(self, audit_repository, mock_db_client):
        """Count events with time range."""
        mock_db_client.execute_single.return_value = {"total": 500}
        since = datetime.now(UTC) - timedelta(days=7)
        until = datetime.now(UTC)

        result = await audit_repository.count_events(since=since, until=until)

        assert result == 500


# =============================================================================
# List Events Tests
# =============================================================================


class TestAuditRepositoryListEvents:
    """Tests for list_events method."""

    @pytest.mark.asyncio
    async def test_list_events(self, audit_repository, mock_db_client, sample_audit_node):
        """List events with pagination."""
        mock_db_client.execute_single.return_value = {"total": 100}
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        events, total = await audit_repository.list_events(offset=0, limit=50)

        assert len(events) == 1
        assert total == 100

    @pytest.mark.asyncio
    async def test_list_events_with_filters(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """List events with filters."""
        mock_db_client.execute_single.return_value = {"total": 10}
        mock_db_client.execute.return_value = [{"a": sample_audit_node}]

        events, total = await audit_repository.list_events(
            filters={"action": "create", "entity_type": "capsule", "user_id": "user-001"}
        )

        assert len(events) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["action"] == "create"
        assert params["entity_type"] == "capsule"
        assert params["user_id"] == "user-001"

    @pytest.mark.asyncio
    async def test_list_events_caps_limit(self, audit_repository, mock_db_client):
        """List events caps limit at 1000."""
        mock_db_client.execute_single.return_value = {"total": 0}
        mock_db_client.execute.return_value = []

        await audit_repository.list_events(limit=5000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 1000


# =============================================================================
# Bulk and Export Logging Tests
# =============================================================================


class TestBulkAndExportLogging:
    """Tests for bulk operation and data export logging."""

    @pytest.mark.asyncio
    async def test_log_bulk_operation(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log bulk operation."""
        sample_audit_node["priority"] = "high"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_bulk_operation(
            actor_id="user-001",
            operation="bulk_delete",
            resource_type="capsule",
            resource_count=50,
            resource_ids=["cap-1", "cap-2", "cap-3"],
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_log_bulk_operation_truncates_ids(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log bulk operation truncates IDs if over 100."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}
        many_ids = [f"cap-{i}" for i in range(150)]

        await audit_repository.log_bulk_operation(
            actor_id="user-001",
            operation="bulk_delete",
            resource_type="capsule",
            resource_count=150,
            resource_ids=many_ids,
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        details = json.loads(params["details"])
        assert len(details["resource_ids"]) == 100
        assert details["ids_truncated"] is True

    @pytest.mark.asyncio
    async def test_log_data_export(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log data export operation."""
        sample_audit_node["priority"] = "high"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_data_export(
            actor_id="user-001",
            export_type="user_data",
            resource_type="user",
            record_count=1000,
            format="csv",
            filters_applied={"status": "active"},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_log_maintenance_mode(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log maintenance mode change."""
        sample_audit_node["priority"] = "critical"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_maintenance_mode(
            actor_id="admin-001",
            action="enabled",
            reason="Scheduled maintenance",
            duration_minutes=60,
            affected_services=["api", "database"],
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_log_self_audit(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """Log self-audit operation."""
        sample_audit_node["event_type"] = "security.event"
        sample_audit_node["priority"] = "critical"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.log_self_audit(
            actor_id="admin-001",
            action="purge",
            target_audit_ids=["audit-1", "audit-2"],
            details={"reason": "Data retention policy"},
        )

        assert result.event_type == EventType.SECURITY_EVENT


# =============================================================================
# Model Conversion Tests
# =============================================================================


class TestAuditEventConversion:
    """Tests for _to_audit_event conversion."""

    @pytest.mark.asyncio
    async def test_to_audit_event_parses_json_details(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """_to_audit_event parses JSON details."""
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.get_by_id("audit-123")

        assert result is not None
        assert isinstance(result.details, dict)

    @pytest.mark.asyncio
    async def test_to_audit_event_handles_invalid_json(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """_to_audit_event handles invalid JSON gracefully."""
        sample_audit_node["details"] = "invalid json{"
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.get_by_id("audit-123")

        assert result is not None
        assert "raw" in result.details

    @pytest.mark.asyncio
    async def test_to_audit_event_handles_neo4j_datetime(
        self, audit_repository, mock_db_client, sample_audit_node
    ):
        """_to_audit_event handles Neo4j datetime objects."""
        # Simulate Neo4j DateTime with to_native method
        neo4j_dt = MagicMock()
        neo4j_dt.to_native.return_value = datetime.now(UTC)
        sample_audit_node["timestamp"] = neo4j_dt
        mock_db_client.execute_single.return_value = {"a": sample_audit_node}

        result = await audit_repository.get_by_id("audit-123")

        assert result is not None
        assert isinstance(result.timestamp, datetime)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for get_audit_repository factory function."""

    def test_get_audit_repository(self, mock_db_client):
        """get_audit_repository creates repository instance."""
        repo = get_audit_repository(mock_db_client)

        assert isinstance(repo, AuditRepository)

    def test_get_audit_repository_always_creates_new(self, mock_db_client):
        """get_audit_repository creates new instance each time."""
        repo1 = get_audit_repository(mock_db_client)
        repo2 = get_audit_repository(mock_db_client)

        # Factory creates new instances (not singleton)
        assert repo1 is not repo2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
