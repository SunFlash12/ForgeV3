"""
Event Models

Event system for pub/sub messaging and cascade propagation.
Enables the Cascade Effect where insights propagate across overlays.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from forge.models.base import ForgeModel


class EventType(str, Enum):
    """Types of events in the Forge system."""

    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_HEALTH_CHECK = "system.health_check"
    SYSTEM_ERROR = "system.error"
    SYSTEM_EVENT = "system.event"  # Generic system event

    # Capsule Events
    CAPSULE_CREATED = "capsule.created"
    CAPSULE_UPDATED = "capsule.updated"
    CAPSULE_DELETED = "capsule.deleted"
    CAPSULE_FORKED = "capsule.forked"
    CAPSULE_VIEWED = "capsule.viewed"
    CAPSULE_ACCESSED = "capsule.accessed"
    CAPSULE_LINKED = "capsule.linked"

    # User Events
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_TRUST_CHANGED = "user.trust_changed"
    TRUST_UPDATED = "user.trust_updated"

    # Overlay Events
    OVERLAY_LOADED = "overlay.loaded"
    OVERLAY_ACTIVATED = "overlay.activated"
    OVERLAY_DEACTIVATED = "overlay.deactivated"
    OVERLAY_ERROR = "overlay.error"
    OVERLAY_QUARANTINED = "overlay.quarantined"
    OVERLAY_RECOVERED = "overlay.recovered"

    # ML/Intelligence Events
    PATTERN_DETECTED = "ml.pattern_detected"
    ANOMALY_DETECTED = "ml.anomaly_detected"
    MODEL_UPDATED = "ml.model_updated"
    INSIGHT_GENERATED = "ml.insight_generated"

    # Security Events
    SECURITY_THREAT = "security.threat"
    SECURITY_VIOLATION = "security.violation"
    SECURITY_ALERT = "security.alert"
    TRUST_VERIFICATION = "security.trust_verification"

    # Governance Events
    PROPOSAL_CREATED = "governance.proposal_created"
    PROPOSAL_VOTING_STARTED = "governance.voting_started"
    PROPOSAL_VOTE_CAST = "governance.vote_cast"
    PROPOSAL_PASSED = "governance.proposal_passed"
    PROPOSAL_REJECTED = "governance.proposal_rejected"
    PROPOSAL_EXECUTED = "governance.proposal_executed"
    VOTE_CAST = "governance.vote"
    GOVERNANCE_ACTION = "governance.action"

    # Pipeline Events
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_PHASE_COMPLETE = "pipeline.phase_complete"
    PIPELINE_COMPLETE = "pipeline.complete"
    PIPELINE_ERROR = "pipeline.error"

    # Cascade Events (for propagation)
    CASCADE_INITIATED = "cascade.initiated"
    CASCADE_PROPAGATED = "cascade.propagated"
    CASCADE_COMPLETE = "cascade.complete"
    CASCADE_TRIGGERED = "cascade.triggered"


class EventPriority(str, Enum):
    """Priority levels for event processing."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Event(ForgeModel):
    """Base event model for the pub/sub system."""

    id: str = Field(description="Unique event ID")
    type: EventType
    source: str = Field(description="Source component/overlay")
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = Field(
        default=None,
        description="For tracing related events",
    )
    priority: EventPriority = Field(default=EventPriority.NORMAL)
    
    # Targeting
    target_overlays: list[str] | None = Field(
        default=None,
        description="Specific targets (None = broadcast)",
    )
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventSubscription(ForgeModel):
    """Subscription to event types."""

    subscriber_id: str = Field(description="Overlay or component ID")
    event_types: list[EventType] = Field(
        default_factory=list,
        description="Event types to receive",
    )
    event_patterns: list[str] = Field(
        default_factory=list,
        description="Wildcard patterns (e.g., 'cascade.*')",
    )
    priority_filter: EventPriority | None = Field(
        default=None,
        description="Minimum priority to receive",
    )
    callback: str | None = Field(
        default=None,
        description="Function name to call",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# CASCADE EVENTS
# ═══════════════════════════════════════════════════════════════


class CascadeEvent(ForgeModel):
    """
    Event for the Cascade Effect.
    
    When one overlay has a breakthrough, the insight propagates
    across the ecosystem through cascade events.
    """

    id: str
    source_overlay: str
    insight_type: str = Field(description="Type of insight being cascaded")
    insight_data: dict[str, Any]
    
    # Propagation tracking
    hop_count: int = Field(
        default=0,
        ge=0,
        description="Number of hops in cascade chain",
    )
    max_hops: int = Field(
        default=5,
        ge=1,
        description="Maximum cascade depth",
    )
    visited_overlays: list[str] = Field(
        default_factory=list,
        description="Overlays that have processed this cascade",
    )
    
    # Impact
    impact_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Estimated impact of cascade",
    )
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None

    @property
    def can_propagate(self) -> bool:
        """Check if cascade can continue propagating."""
        return self.hop_count < self.max_hops


class CascadeChain(ForgeModel):
    """Complete record of a cascade propagation chain."""

    cascade_id: str
    initiated_by: str
    initiated_at: datetime
    
    # Chain of events
    events: list[CascadeEvent] = Field(default_factory=list)
    
    # Completion
    completed_at: datetime | None = None
    total_hops: int = 0
    overlays_affected: list[str] = Field(default_factory=list)
    
    # Outcomes
    insights_generated: int = 0
    actions_triggered: int = 0
    errors_encountered: int = 0


# ═══════════════════════════════════════════════════════════════
# EVENT HANDLERS
# ═══════════════════════════════════════════════════════════════


class EventHandlerResult(ForgeModel):
    """Result of processing an event."""

    event_id: str
    handler_id: str
    success: bool
    output: Any | None = None
    error: str | None = None
    processing_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Follow-up events
    triggered_events: list[str] = Field(
        default_factory=list,
        description="IDs of events triggered by this handler",
    )


class EventMetrics(ForgeModel):
    """Metrics for the event system."""

    total_events_published: int = 0
    total_events_delivered: int = 0
    total_events_failed: int = 0
    
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_source: dict[str, int] = Field(default_factory=dict)
    
    avg_processing_time_ms: float = 0.0
    cascade_chains_initiated: int = 0
    
    # Queue status
    queue_size: int = 0
    queue_max_size: int = 10000


# ═══════════════════════════════════════════════════════════════
# AUDIT EVENTS
# ═══════════════════════════════════════════════════════════════


class AuditEvent(ForgeModel):
    """Audit log entry as an event."""

    id: str
    operation: str = Field(description="CREATE, READ, UPDATE, DELETE, etc.")
    entity_type: str = Field(description="Capsule, User, Proposal, etc.")
    entity_id: str
    actor_id: str | None = Field(description="User or system ID")
    changes: dict[str, Any] = Field(
        default_factory=dict,
        description="Before/after values",
    )
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
