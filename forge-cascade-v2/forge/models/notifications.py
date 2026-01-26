"""
Notification Models

Data structures for the webhook and notification system.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from forge.models.base import ForgeModel, generate_id


class NotificationEvent(str, Enum):
    """Types of events that can trigger notifications."""

    # Proposals
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_PASSED = "proposal.passed"
    PROPOSAL_REJECTED = "proposal.rejected"
    PROPOSAL_NEEDS_VOTE = "proposal.needs_vote"
    PROPOSAL_EXPIRING = "proposal.expiring"

    # Ghost Council
    ISSUE_DETECTED = "issue.detected"
    ISSUE_CRITICAL = "issue.critical"
    COUNCIL_RECOMMENDATION = "council.recommendation"
    COUNCIL_VOTE_COMPLETE = "council.vote_complete"

    # Capsules
    CAPSULE_CREATED = "capsule.created"
    CAPSULE_UPDATED = "capsule.updated"
    CAPSULE_CONTRADICTION = "capsule.contradiction"
    CAPSULE_TRUST_CHANGE = "capsule.trust_change"
    CAPSULE_CITED = "capsule.cited"

    # Federation
    PEER_CONNECTED = "peer.connected"
    PEER_DISCONNECTED = "peer.disconnected"
    SYNC_COMPLETED = "sync.completed"
    SYNC_CONFLICT = "sync.conflict"

    # System
    ANOMALY_DETECTED = "anomaly.detected"
    SYSTEM_DEGRADED = "system.degraded"
    SYSTEM_RECOVERED = "system.recovered"

    # User
    TRUST_FLAME_CHANGE = "user.trust_flame_change"
    MENTION = "user.mention"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryChannel(str, Enum):
    """Delivery channels for notifications."""

    IN_APP = "in_app"
    WEBHOOK = "webhook"
    EMAIL = "email"  # Future
    SLACK = "slack"  # Future


class DigestFrequency(str, Enum):
    """Frequency for notification digests."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class WebhookSubscription(ForgeModel):
    """
    A webhook subscription for receiving notifications.
    """

    id: str = Field(default_factory=generate_id)
    user_id: str = Field(description="Owner of this subscription")

    # Webhook configuration
    url: str = Field(description="HTTPS URL to send notifications to")
    secret: str = Field(description="HMAC-SHA256 secret for signing payloads")

    # Event filtering
    events: list[NotificationEvent] = Field(
        default_factory=list, description="Events to subscribe to (empty = all events)"
    )
    filter_capsule_types: list[str] = Field(
        default_factory=list, description="Only capsule events for these types"
    )
    filter_min_priority: NotificationPriority = Field(
        default=NotificationPriority.LOW, description="Minimum priority to send"
    )

    # State
    active: bool = Field(default=True)
    verified: bool = Field(default=False, description="URL verified by ping")

    # Metadata
    name: str = Field(default="", description="Human-readable name")
    description: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_triggered_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None

    # Stats
    total_sent: int = Field(default=0)
    total_success: int = Field(default=0)
    total_failure: int = Field(default=0)
    consecutive_failures: int = Field(default=0)


class Notification(ForgeModel):
    """
    An in-app notification for a user.
    """

    id: str = Field(default_factory=generate_id)
    user_id: str = Field(description="Recipient user ID")

    # Content
    event_type: NotificationEvent
    title: str = Field(max_length=200)
    message: str = Field(max_length=2000)
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL)

    # Related data
    data: dict[str, Any] = Field(default_factory=dict)
    related_entity_id: str | None = None
    related_entity_type: str | None = None  # "capsule", "proposal", "user", etc.
    action_url: str | None = None

    # State
    read: bool = Field(default=False)
    read_at: datetime | None = None
    dismissed: bool = Field(default=False)
    dismissed_at: datetime | None = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Source
    source: str = Field(default="system", description="What triggered this")


class WebhookDelivery(ForgeModel):
    """
    Record of a webhook delivery attempt.
    """

    id: str = Field(default_factory=generate_id)
    webhook_id: str
    notification_id: str | None = None

    # Request
    event_type: NotificationEvent
    payload: dict[str, Any]
    signature: str

    # Response
    status_code: int | None = None
    response_body: str | None = None
    response_time_ms: float | None = None

    # State
    success: bool = Field(default=False)
    error: str | None = None
    retry_count: int = Field(default=0)
    next_retry_at: datetime | None = None

    # Timestamps
    attempted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class NotificationPreferences(ForgeModel):
    """
    User's notification preferences.
    """

    id: str = Field(default_factory=generate_id)
    user_id: str

    # Channel preferences per event type
    # {event_type: [channels]}
    channel_preferences: dict[str, list[DeliveryChannel]] = Field(default_factory=dict)

    # Global settings
    mute_all: bool = Field(default=False)
    mute_until: datetime | None = None

    # Quiet hours (UTC)
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)

    # Summary settings
    digest_enabled: bool = Field(default=False)
    digest_frequency: DigestFrequency = Field(default=DigestFrequency.DAILY)

    # Defaults for new event types
    default_channels: list[DeliveryChannel] = Field(
        default_factory=lambda: [DeliveryChannel.IN_APP]
    )

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookPayload(ForgeModel):
    """
    Standard webhook payload format.
    """

    event: str
    timestamp: datetime
    webhook_id: str
    delivery_id: str

    data: dict[str, Any]

    # For verification
    signature: str | None = None

    def to_dict_for_signing(self) -> dict[str, Any]:
        """Get dict representation for signature calculation."""
        return {
            "event": self.event,
            "timestamp": self.timestamp.isoformat(),
            "webhook_id": self.webhook_id,
            "delivery_id": self.delivery_id,
            "data": self.data,
        }
