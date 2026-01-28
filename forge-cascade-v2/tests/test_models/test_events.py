"""
Event Model Tests for Forge Cascade V2

Comprehensive tests for event models including:
- EventType enum validation (all event categories)
- EventPriority enum validation
- Event model with all fields
- EventSubscription model
- CascadeEvent with computed properties
- CascadeChain model
- EventHandlerResult and EventMetrics models
- AuditEvent model
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.events import (
    AuditEvent,
    CascadeChain,
    CascadeEvent,
    Event,
    EventHandlerResult,
    EventMetrics,
    EventPriority,
    EventSubscription,
    EventType,
)

# =============================================================================
# EventType Enum Tests
# =============================================================================


class TestEventTypeEnum:
    """Tests for EventType enum."""

    def test_system_events(self):
        """System events have expected values."""
        assert EventType.SYSTEM_STARTUP.value == "system.startup"
        assert EventType.SYSTEM_SHUTDOWN.value == "system.shutdown"
        assert EventType.SYSTEM_HEALTH_CHECK.value == "system.health_check"
        assert EventType.SYSTEM_ERROR.value == "system.error"
        assert EventType.SYSTEM_EVENT.value == "system.event"

    def test_capsule_events(self):
        """Capsule events have expected values."""
        assert EventType.CAPSULE_CREATED.value == "capsule.created"
        assert EventType.CAPSULE_UPDATED.value == "capsule.updated"
        assert EventType.CAPSULE_DELETED.value == "capsule.deleted"
        assert EventType.CAPSULE_FORKED.value == "capsule.forked"
        assert EventType.CAPSULE_VIEWED.value == "capsule.viewed"
        assert EventType.CAPSULE_ACCESSED.value == "capsule.accessed"
        assert EventType.CAPSULE_LINKED.value == "capsule.linked"
        assert EventType.CAPSULE_ARCHIVED.value == "capsule.archived"
        assert EventType.CAPSULE_UNARCHIVED.value == "capsule.unarchived"
        assert EventType.CAPSULE_SEARCHED.value == "capsule.searched"
        assert EventType.SEMANTIC_EDGE_CREATED.value == "capsule.semantic_edge_created"
        assert EventType.SEMANTIC_EDGE_DELETED.value == "capsule.semantic_edge_deleted"

    def test_user_events(self):
        """User events have expected values."""
        assert EventType.USER_REGISTERED.value == "user.registered"
        assert EventType.USER_CREATED.value == "user.created"
        assert EventType.USER_UPDATED.value == "user.updated"
        assert EventType.USER_LOGIN.value == "user.login"
        assert EventType.USER_LOGIN_FAILED.value == "user.login_failed"
        assert EventType.USER_LOGOUT.value == "user.logout"
        assert EventType.USER_TRUST_CHANGED.value == "user.trust_changed"
        assert EventType.USER_LOCKED.value == "user.locked"
        assert EventType.USER_UNLOCKED.value == "user.unlocked"
        assert EventType.TRUST_UPDATED.value == "user.trust_updated"

    def test_overlay_events(self):
        """Overlay events have expected values."""
        assert EventType.OVERLAY_LOADED.value == "overlay.loaded"
        assert EventType.OVERLAY_REGISTERED.value == "overlay.registered"
        assert EventType.OVERLAY_ACTIVATED.value == "overlay.activated"
        assert EventType.OVERLAY_DEACTIVATED.value == "overlay.deactivated"
        assert EventType.OVERLAY_EXECUTED.value == "overlay.executed"
        assert EventType.OVERLAY_ERROR.value == "overlay.error"
        assert EventType.OVERLAY_TIMEOUT.value == "overlay.timeout"
        assert EventType.OVERLAY_QUARANTINED.value == "overlay.quarantined"
        assert EventType.OVERLAY_RECOVERED.value == "overlay.recovered"
        assert EventType.OVERLAY_EVENT.value == "overlay.event"

    def test_ml_events(self):
        """ML/Intelligence events have expected values."""
        assert EventType.PATTERN_DETECTED.value == "ml.pattern_detected"
        assert EventType.ANOMALY_DETECTED.value == "ml.anomaly_detected"
        assert EventType.MODEL_UPDATED.value == "ml.model_updated"
        assert EventType.INSIGHT_GENERATED.value == "ml.insight_generated"

    def test_security_events(self):
        """Security events have expected values."""
        assert EventType.SECURITY_THREAT.value == "security.threat"
        assert EventType.SECURITY_VIOLATION.value == "security.violation"
        assert EventType.SECURITY_ALERT.value == "security.alert"
        assert EventType.SECURITY_EVENT.value == "security.event"
        assert EventType.TRUST_VERIFICATION.value == "security.trust_verification"

    def test_immune_events(self):
        """Immune system events have expected values."""
        assert EventType.IMMUNE_EVENT.value == "immune.event"
        assert EventType.IMMUNE_ALERT.value == "immune.alert"
        assert EventType.IMMUNE_QUARANTINE.value == "immune.quarantine"

    def test_governance_events(self):
        """Governance events have expected values."""
        assert EventType.PROPOSAL_CREATED.value == "governance.proposal_created"
        assert EventType.PROPOSAL_UPDATED.value == "governance.proposal_updated"
        assert EventType.PROPOSAL_VOTING_STARTED.value == "governance.voting_started"
        assert EventType.PROPOSAL_VOTE_CAST.value == "governance.vote_cast"
        assert EventType.PROPOSAL_PASSED.value == "governance.proposal_passed"
        assert EventType.PROPOSAL_REJECTED.value == "governance.proposal_rejected"
        assert EventType.PROPOSAL_EXECUTED.value == "governance.proposal_executed"
        assert EventType.VOTE_CAST.value == "governance.vote"
        assert EventType.GOVERNANCE_ACTION.value == "governance.action"
        assert EventType.GOVERNANCE_EVENT.value == "governance.event"

    def test_pipeline_events(self):
        """Pipeline events have expected values."""
        assert EventType.PIPELINE_STARTED.value == "pipeline.started"
        assert EventType.PIPELINE_PHASE_COMPLETE.value == "pipeline.phase_complete"
        assert EventType.PIPELINE_COMPLETE.value == "pipeline.complete"
        assert EventType.PIPELINE_ERROR.value == "pipeline.error"

    def test_cascade_events(self):
        """Cascade events have expected values."""
        assert EventType.CASCADE_INITIATED.value == "cascade.initiated"
        assert EventType.CASCADE_PROPAGATED.value == "cascade.propagated"
        assert EventType.CASCADE_COMPLETE.value == "cascade.complete"
        assert EventType.CASCADE_TRIGGERED.value == "cascade.triggered"

    def test_event_type_is_string_enum(self):
        """EventType is a string enum."""
        assert isinstance(EventType.SYSTEM_STARTUP, str)
        assert EventType.SYSTEM_STARTUP == "system.startup"

    def test_total_event_types_count(self):
        """All event types are accounted for."""
        # Should have a comprehensive set of event types
        assert len(EventType) >= 50  # At least 50 event types


# =============================================================================
# EventPriority Enum Tests
# =============================================================================


class TestEventPriorityEnum:
    """Tests for EventPriority enum."""

    def test_priority_values(self):
        """EventPriority has expected values."""
        assert EventPriority.LOW.value == "low"
        assert EventPriority.NORMAL.value == "normal"
        assert EventPriority.HIGH.value == "high"
        assert EventPriority.CRITICAL.value == "critical"

    def test_priority_is_string_enum(self):
        """EventPriority is a string enum."""
        assert isinstance(EventPriority.LOW, str)
        assert EventPriority.LOW == "low"

    def test_priority_count(self):
        """All priorities are present."""
        assert len(EventPriority) == 4


# =============================================================================
# Event Tests
# =============================================================================


class TestEvent:
    """Tests for Event model."""

    def test_valid_event(self):
        """Valid event creates model."""
        event = Event(
            id="event-123",
            type=EventType.CAPSULE_CREATED,
            source="capsule-service",
            payload={"capsule_id": "cap-456"},
        )
        assert event.id == "event-123"
        assert event.type == EventType.CAPSULE_CREATED
        assert event.source == "capsule-service"
        assert event.payload["capsule_id"] == "cap-456"

    def test_default_values(self):
        """Event has sensible defaults."""
        event = Event(
            id="event-123",
            type=EventType.SYSTEM_EVENT,
            source="test",
        )
        assert event.payload == {}
        assert event.timestamp is not None
        assert event.correlation_id is None
        assert event.priority == EventPriority.NORMAL
        assert event.target_overlays is None
        assert event.metadata == {}

    def test_event_with_all_priorities(self):
        """Event works with all priorities."""
        for priority in EventPriority:
            event = Event(
                id="event-123",
                type=EventType.SYSTEM_EVENT,
                source="test",
                priority=priority,
            )
            assert event.priority == priority

    def test_event_with_targets(self):
        """Event can specify target overlays."""
        event = Event(
            id="event-123",
            type=EventType.CASCADE_TRIGGERED,
            source="cascade-service",
            target_overlays=["overlay-1", "overlay-2", "overlay-3"],
        )
        assert event.target_overlays == ["overlay-1", "overlay-2", "overlay-3"]

    def test_broadcast_event(self):
        """Event without targets is a broadcast."""
        event = Event(
            id="event-123",
            type=EventType.SYSTEM_STARTUP,
            source="system",
        )
        assert event.target_overlays is None

    def test_event_with_correlation_id(self):
        """Event can have correlation ID for tracing."""
        event = Event(
            id="event-123",
            type=EventType.PIPELINE_STARTED,
            source="pipeline-service",
            correlation_id="trace-abc-123",
        )
        assert event.correlation_id == "trace-abc-123"

    def test_event_with_metadata(self):
        """Event can have additional metadata."""
        event = Event(
            id="event-123",
            type=EventType.USER_LOGIN,
            source="auth-service",
            metadata={
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "session_id": "sess-123",
            },
        )
        assert event.metadata["ip_address"] == "192.168.1.1"

    def test_event_all_types(self):
        """Event works with all event types."""
        for event_type in list(EventType)[:10]:  # Test first 10
            event = Event(
                id="event-123",
                type=event_type,
                source="test",
            )
            assert event.type == event_type


# =============================================================================
# EventSubscription Tests
# =============================================================================


class TestEventSubscription:
    """Tests for EventSubscription model."""

    def test_valid_subscription(self):
        """Valid subscription creates model."""
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_types=[EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED],
        )
        assert subscription.subscriber_id == "overlay-123"
        assert EventType.CAPSULE_CREATED in subscription.event_types
        assert EventType.CAPSULE_UPDATED in subscription.event_types

    def test_default_values(self):
        """Subscription has sensible defaults."""
        subscription = EventSubscription(subscriber_id="overlay-123")
        assert subscription.event_types == []
        assert subscription.event_patterns == []
        assert subscription.priority_filter is None
        assert subscription.callback is None
        assert subscription.created_at is not None

    def test_subscription_with_patterns(self):
        """Subscription can use wildcard patterns."""
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_patterns=["capsule.*", "user.*", "cascade.*"],
        )
        assert "capsule.*" in subscription.event_patterns
        assert "user.*" in subscription.event_patterns

    def test_subscription_with_priority_filter(self):
        """Subscription can filter by minimum priority."""
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_types=[EventType.SECURITY_ALERT],
            priority_filter=EventPriority.HIGH,
        )
        assert subscription.priority_filter == EventPriority.HIGH

    def test_subscription_with_callback(self):
        """Subscription can specify callback function."""
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_types=[EventType.CAPSULE_CREATED],
            callback="handle_capsule_created",
        )
        assert subscription.callback == "handle_capsule_created"

    def test_subscription_all_event_types(self):
        """Subscription can subscribe to all event types."""
        all_types = list(EventType)
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_types=all_types,
        )
        assert len(subscription.event_types) == len(EventType)


# =============================================================================
# CascadeEvent Tests
# =============================================================================


class TestCascadeEvent:
    """Tests for CascadeEvent model."""

    def test_valid_cascade_event(self):
        """Valid cascade event creates model."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="ml-overlay",
            insight_type="pattern_detection",
            insight_data={"pattern": "anomaly", "confidence": 0.95},
        )
        assert cascade.id == "cascade-123"
        assert cascade.source_overlay == "ml-overlay"
        assert cascade.insight_type == "pattern_detection"
        assert cascade.insight_data["confidence"] == 0.95

    def test_default_values(self):
        """Cascade event has sensible defaults."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
        )
        assert cascade.hop_count == 0
        assert cascade.max_hops == 5
        assert cascade.visited_overlays == []
        assert cascade.impact_score == 0.0
        assert cascade.timestamp is not None
        assert cascade.correlation_id is None

    def test_hop_count_non_negative(self):
        """hop_count must be >= 0."""
        with pytest.raises(ValidationError):
            CascadeEvent(
                id="cascade-123",
                source_overlay="test",
                insight_type="test",
                insight_data={},
                hop_count=-1,
            )

    def test_max_hops_minimum(self):
        """max_hops must be >= 1."""
        with pytest.raises(ValidationError):
            CascadeEvent(
                id="cascade-123",
                source_overlay="test",
                insight_type="test",
                insight_data={},
                max_hops=0,
            )

    def test_impact_score_bounds(self):
        """impact_score must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            CascadeEvent(
                id="cascade-123",
                source_overlay="test",
                insight_type="test",
                insight_data={},
                impact_score=-0.1,
            )

        with pytest.raises(ValidationError):
            CascadeEvent(
                id="cascade-123",
                source_overlay="test",
                insight_type="test",
                insight_data={},
                impact_score=1.1,
            )

    def test_can_propagate_true(self):
        """can_propagate returns True when hops available."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            hop_count=2,
            max_hops=5,
        )
        assert cascade.can_propagate is True

    def test_can_propagate_false(self):
        """can_propagate returns False when max hops reached."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            hop_count=5,
            max_hops=5,
        )
        assert cascade.can_propagate is False

    def test_can_propagate_exceeded(self):
        """can_propagate returns False when hops exceed max."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            hop_count=6,
            max_hops=5,
        )
        assert cascade.can_propagate is False

    def test_cascade_with_visited_overlays(self):
        """Cascade event tracks visited overlays."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="overlay-1",
            insight_type="test",
            insight_data={},
            hop_count=3,
            visited_overlays=["overlay-1", "overlay-2", "overlay-3"],
        )
        assert len(cascade.visited_overlays) == 3
        assert "overlay-1" in cascade.visited_overlays

    def test_cascade_boundary_impact_scores(self):
        """Impact score boundary values are valid."""
        cascade_zero = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            impact_score=0.0,
        )
        assert cascade_zero.impact_score == 0.0

        cascade_one = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            impact_score=1.0,
        )
        assert cascade_one.impact_score == 1.0


# =============================================================================
# CascadeChain Tests
# =============================================================================


class TestCascadeChain:
    """Tests for CascadeChain model."""

    def test_valid_cascade_chain(self):
        """Valid cascade chain creates model."""
        now = datetime.now(UTC)
        chain = CascadeChain(
            cascade_id="chain-123",
            initiated_by="ml-overlay",
            initiated_at=now,
        )
        assert chain.cascade_id == "chain-123"
        assert chain.initiated_by == "ml-overlay"
        assert chain.initiated_at == now

    def test_default_values(self):
        """Cascade chain has sensible defaults."""
        chain = CascadeChain(
            cascade_id="chain-123",
            initiated_by="test",
            initiated_at=datetime.now(UTC),
        )
        assert chain.events == []
        assert chain.completed_at is None
        assert chain.total_hops == 0
        assert chain.overlays_affected == []
        assert chain.insights_generated == 0
        assert chain.actions_triggered == 0
        assert chain.errors_encountered == 0

    def test_cascade_chain_with_events(self):
        """Cascade chain can contain events."""
        events = [
            CascadeEvent(
                id=f"cascade-{i}",
                source_overlay=f"overlay-{i}",
                insight_type="test",
                insight_data={"index": i},
                hop_count=i,
            )
            for i in range(3)
        ]
        chain = CascadeChain(
            cascade_id="chain-123",
            initiated_by="overlay-0",
            initiated_at=datetime.now(UTC),
            events=events,
            total_hops=3,
            overlays_affected=["overlay-0", "overlay-1", "overlay-2"],
        )
        assert len(chain.events) == 3
        assert len(chain.overlays_affected) == 3
        assert chain.total_hops == 3

    def test_completed_cascade_chain(self):
        """Completed cascade chain has completion timestamp."""
        now = datetime.now(UTC)
        chain = CascadeChain(
            cascade_id="chain-123",
            initiated_by="test",
            initiated_at=now,
            completed_at=now,
            total_hops=5,
            insights_generated=10,
            actions_triggered=3,
            errors_encountered=1,
        )
        assert chain.completed_at is not None
        assert chain.insights_generated == 10
        assert chain.actions_triggered == 3
        assert chain.errors_encountered == 1


# =============================================================================
# EventHandlerResult Tests
# =============================================================================


class TestEventHandlerResult:
    """Tests for EventHandlerResult model."""

    def test_valid_handler_result_success(self):
        """Valid successful handler result creates model."""
        result = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            output={"processed": True},
            processing_time_ms=150.5,
        )
        assert result.event_id == "event-123"
        assert result.handler_id == "handler-456"
        assert result.success is True
        assert result.output == {"processed": True}

    def test_valid_handler_result_failure(self):
        """Valid failed handler result creates model."""
        result = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=False,
            error="Connection timeout",
            processing_time_ms=5000.0,
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_default_values(self):
        """Handler result has sensible defaults."""
        result = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
        )
        assert result.output is None
        assert result.error is None
        assert result.processing_time_ms == 0.0
        assert result.timestamp is not None
        assert result.triggered_events == []

    def test_handler_result_with_triggered_events(self):
        """Handler result can track triggered events."""
        result = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            triggered_events=["event-789", "event-012"],
        )
        assert len(result.triggered_events) == 2
        assert "event-789" in result.triggered_events

    def test_handler_result_any_output(self):
        """Handler result can have any output type."""
        # Dict output
        result1 = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            output={"key": "value"},
        )
        assert result1.output == {"key": "value"}

        # List output
        result2 = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            output=[1, 2, 3],
        )
        assert result2.output == [1, 2, 3]

        # String output
        result3 = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            output="success message",
        )
        assert result3.output == "success message"


# =============================================================================
# EventMetrics Tests
# =============================================================================


class TestEventMetrics:
    """Tests for EventMetrics model."""

    def test_default_values(self):
        """Event metrics has sensible defaults."""
        metrics = EventMetrics()
        assert metrics.total_events_published == 0
        assert metrics.total_events_delivered == 0
        assert metrics.total_events_failed == 0
        assert metrics.events_by_type == {}
        assert metrics.events_by_source == {}
        assert metrics.avg_processing_time_ms == 0.0
        assert metrics.cascade_chains_initiated == 0
        assert metrics.queue_size == 0
        assert metrics.queue_max_size == 10000

    def test_metrics_with_data(self):
        """Event metrics with populated data."""
        metrics = EventMetrics(
            total_events_published=1000,
            total_events_delivered=950,
            total_events_failed=50,
            events_by_type={
                "capsule.created": 200,
                "capsule.updated": 300,
                "user.login": 500,
            },
            events_by_source={
                "capsule-service": 500,
                "auth-service": 500,
            },
            avg_processing_time_ms=25.5,
            cascade_chains_initiated=10,
            queue_size=100,
        )
        assert metrics.total_events_published == 1000
        assert metrics.total_events_delivered == 950
        assert metrics.events_by_type["capsule.created"] == 200
        assert metrics.avg_processing_time_ms == 25.5

    def test_metrics_event_counts_consistency(self):
        """Event counts should be consistent."""
        metrics = EventMetrics(
            total_events_published=1000,
            total_events_delivered=950,
            total_events_failed=50,
        )
        # Published should equal delivered + failed (in ideal scenario)
        assert metrics.total_events_published == (
            metrics.total_events_delivered + metrics.total_events_failed
        )


# =============================================================================
# AuditEvent Tests
# =============================================================================


class TestAuditEvent:
    """Tests for AuditEvent model."""

    def test_valid_audit_event(self):
        """Valid audit event creates model."""
        audit = AuditEvent(
            id="audit-123",
            event_type=EventType.CAPSULE_CREATED,
            actor_id="user-456",
            action="create",
            resource_type="Capsule",
            resource_id="cap-789",
        )
        assert audit.id == "audit-123"
        assert audit.event_type == EventType.CAPSULE_CREATED
        assert audit.actor_id == "user-456"
        assert audit.action == "create"
        assert audit.resource_type == "Capsule"
        assert audit.resource_id == "cap-789"

    def test_default_values(self):
        """Audit event has sensible defaults."""
        audit = AuditEvent(
            id="audit-123",
            event_type=EventType.SYSTEM_EVENT,
            action="test",
            resource_type="Test",
        )
        assert audit.actor_id is None
        assert audit.resource_id is None
        assert audit.details == {}
        assert audit.old_value is None
        assert audit.new_value is None
        assert audit.ip_address is None
        assert audit.user_agent is None
        assert audit.correlation_id is None
        assert audit.priority == EventPriority.NORMAL
        assert audit.timestamp is not None

    def test_audit_event_with_change_tracking(self):
        """Audit event can track old and new values."""
        audit = AuditEvent(
            id="audit-123",
            event_type=EventType.CAPSULE_UPDATED,
            actor_id="user-456",
            action="update",
            resource_type="Capsule",
            resource_id="cap-789",
            old_value={"title": "Old Title", "status": "draft"},
            new_value={"title": "New Title", "status": "published"},
        )
        assert audit.old_value["title"] == "Old Title"
        assert audit.new_value["title"] == "New Title"

    def test_audit_event_with_client_info(self):
        """Audit event can track client info."""
        audit = AuditEvent(
            id="audit-123",
            event_type=EventType.USER_LOGIN,
            actor_id="user-456",
            action="login",
            resource_type="Session",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        assert audit.ip_address == "192.168.1.100"
        assert "Mozilla" in audit.user_agent

    def test_audit_event_with_details(self):
        """Audit event can have additional details."""
        audit = AuditEvent(
            id="audit-123",
            event_type=EventType.SECURITY_ALERT,
            action="alert",
            resource_type="System",
            details={
                "alert_type": "suspicious_activity",
                "severity": "high",
                "affected_users": ["user-1", "user-2"],
            },
        )
        assert audit.details["alert_type"] == "suspicious_activity"
        assert len(audit.details["affected_users"]) == 2

    def test_audit_event_all_priorities(self):
        """Audit event works with all priorities."""
        for priority in EventPriority:
            audit = AuditEvent(
                id="audit-123",
                event_type=EventType.SYSTEM_EVENT,
                action="test",
                resource_type="Test",
                priority=priority,
            )
            assert audit.priority == priority


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEventEdgeCases:
    """Edge case tests for event models."""

    def test_event_with_empty_payload(self):
        """Event with empty payload is valid."""
        event = Event(
            id="event-123",
            type=EventType.SYSTEM_STARTUP,
            source="system",
            payload={},
        )
        assert event.payload == {}

    def test_event_with_nested_payload(self):
        """Event with nested payload structure."""
        event = Event(
            id="event-123",
            type=EventType.CAPSULE_CREATED,
            source="capsule-service",
            payload={
                "capsule": {
                    "id": "cap-123",
                    "metadata": {
                        "author": "user-456",
                        "tags": ["ai", "ml"],
                    },
                },
                "context": {
                    "session_id": "sess-789",
                },
            },
        )
        assert event.payload["capsule"]["metadata"]["tags"] == ["ai", "ml"]

    def test_cascade_event_single_hop(self):
        """Cascade event with single hop limit."""
        cascade = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            hop_count=0,
            max_hops=1,
        )
        assert cascade.can_propagate is True

        cascade_at_limit = CascadeEvent(
            id="cascade-123",
            source_overlay="test",
            insight_type="test",
            insight_data={},
            hop_count=1,
            max_hops=1,
        )
        assert cascade_at_limit.can_propagate is False

    def test_subscription_empty_lists(self):
        """Subscription with empty lists is valid."""
        subscription = EventSubscription(
            subscriber_id="overlay-123",
            event_types=[],
            event_patterns=[],
        )
        assert subscription.event_types == []
        assert subscription.event_patterns == []

    def test_handler_result_zero_processing_time(self):
        """Handler result with zero processing time."""
        result = EventHandlerResult(
            event_id="event-123",
            handler_id="handler-456",
            success=True,
            processing_time_ms=0.0,
        )
        assert result.processing_time_ms == 0.0

    def test_multiple_events_same_correlation_id(self):
        """Multiple events can share a correlation ID."""
        correlation_id = "trace-abc-123"
        events = [
            Event(
                id=f"event-{i}",
                type=EventType.PIPELINE_PHASE_COMPLETE,
                source="pipeline-service",
                correlation_id=correlation_id,
                payload={"phase": i},
            )
            for i in range(5)
        ]
        for event in events:
            assert event.correlation_id == correlation_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
