"""
Notification Model Tests for Forge Cascade V2

Comprehensive tests for notification models including:
- NotificationEvent enum with all event types
- NotificationPriority, DeliveryChannel, DigestFrequency enums
- WebhookSubscription model
- Notification model
- WebhookDelivery model
- NotificationPreferences model
- WebhookPayload model
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from forge.models.notifications import (
    DeliveryChannel,
    DigestFrequency,
    Notification,
    NotificationEvent,
    NotificationPreferences,
    NotificationPriority,
    WebhookDelivery,
    WebhookPayload,
    WebhookSubscription,
)


# =============================================================================
# NotificationEvent Enum Tests
# =============================================================================


class TestNotificationEvent:
    """Tests for NotificationEvent enum."""

    def test_proposal_events(self):
        """Proposal-related events exist."""
        assert NotificationEvent.PROPOSAL_CREATED.value == "proposal.created"
        assert NotificationEvent.PROPOSAL_PASSED.value == "proposal.passed"
        assert NotificationEvent.PROPOSAL_REJECTED.value == "proposal.rejected"
        assert NotificationEvent.PROPOSAL_NEEDS_VOTE.value == "proposal.needs_vote"
        assert NotificationEvent.PROPOSAL_EXPIRING.value == "proposal.expiring"

    def test_ghost_council_events(self):
        """Ghost Council-related events exist."""
        assert NotificationEvent.ISSUE_DETECTED.value == "issue.detected"
        assert NotificationEvent.ISSUE_CRITICAL.value == "issue.critical"
        assert NotificationEvent.COUNCIL_RECOMMENDATION.value == "council.recommendation"
        assert NotificationEvent.COUNCIL_VOTE_COMPLETE.value == "council.vote_complete"

    def test_capsule_events(self):
        """Capsule-related events exist."""
        assert NotificationEvent.CAPSULE_CREATED.value == "capsule.created"
        assert NotificationEvent.CAPSULE_UPDATED.value == "capsule.updated"
        assert NotificationEvent.CAPSULE_CONTRADICTION.value == "capsule.contradiction"
        assert NotificationEvent.CAPSULE_TRUST_CHANGE.value == "capsule.trust_change"
        assert NotificationEvent.CAPSULE_CITED.value == "capsule.cited"

    def test_federation_events(self):
        """Federation-related events exist."""
        assert NotificationEvent.PEER_CONNECTED.value == "peer.connected"
        assert NotificationEvent.PEER_DISCONNECTED.value == "peer.disconnected"
        assert NotificationEvent.SYNC_COMPLETED.value == "sync.completed"
        assert NotificationEvent.SYNC_CONFLICT.value == "sync.conflict"

    def test_system_events(self):
        """System-related events exist."""
        assert NotificationEvent.ANOMALY_DETECTED.value == "anomaly.detected"
        assert NotificationEvent.SYSTEM_DEGRADED.value == "system.degraded"
        assert NotificationEvent.SYSTEM_RECOVERED.value == "system.recovered"

    def test_user_events(self):
        """User-related events exist."""
        assert NotificationEvent.TRUST_FLAME_CHANGE.value == "user.trust_flame_change"
        assert NotificationEvent.MENTION.value == "user.mention"

    def test_event_from_string(self):
        """Events can be created from string values."""
        assert NotificationEvent("proposal.created") == NotificationEvent.PROPOSAL_CREATED
        assert NotificationEvent("capsule.updated") == NotificationEvent.CAPSULE_UPDATED

    def test_invalid_event(self):
        """Invalid event string raises ValueError."""
        with pytest.raises(ValueError):
            NotificationEvent("invalid.event")


# =============================================================================
# NotificationPriority Enum Tests
# =============================================================================


class TestNotificationPriority:
    """Tests for NotificationPriority enum."""

    def test_priority_values(self):
        """NotificationPriority has expected values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.CRITICAL.value == "critical"

    def test_priority_count(self):
        """NotificationPriority has exactly four levels."""
        assert len(NotificationPriority) == 4

    def test_priority_from_string(self):
        """Priority can be created from string values."""
        assert NotificationPriority("low") == NotificationPriority.LOW
        assert NotificationPriority("critical") == NotificationPriority.CRITICAL


# =============================================================================
# DeliveryChannel Enum Tests
# =============================================================================


class TestDeliveryChannel:
    """Tests for DeliveryChannel enum."""

    def test_channel_values(self):
        """DeliveryChannel has expected values."""
        assert DeliveryChannel.IN_APP.value == "in_app"
        assert DeliveryChannel.WEBHOOK.value == "webhook"
        assert DeliveryChannel.EMAIL.value == "email"
        assert DeliveryChannel.SLACK.value == "slack"

    def test_channel_count(self):
        """DeliveryChannel has exactly four channels."""
        assert len(DeliveryChannel) == 4


# =============================================================================
# DigestFrequency Enum Tests
# =============================================================================


class TestDigestFrequency:
    """Tests for DigestFrequency enum."""

    def test_frequency_values(self):
        """DigestFrequency has expected values."""
        assert DigestFrequency.HOURLY.value == "hourly"
        assert DigestFrequency.DAILY.value == "daily"
        assert DigestFrequency.WEEKLY.value == "weekly"

    def test_frequency_count(self):
        """DigestFrequency has exactly three frequencies."""
        assert len(DigestFrequency) == 3


# =============================================================================
# WebhookSubscription Tests
# =============================================================================


class TestWebhookSubscription:
    """Tests for WebhookSubscription model."""

    def test_valid_webhook_subscription(self):
        """Valid webhook subscription creation."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="my-secret-key",
        )
        assert subscription.user_id == "user123"
        assert subscription.url == "https://example.com/webhook"
        assert subscription.secret == "my-secret-key"
        assert subscription.id is not None  # Auto-generated

    def test_webhook_defaults(self):
        """Webhook subscription has sensible defaults."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
        )
        assert subscription.events == []
        assert subscription.filter_capsule_types == []
        assert subscription.filter_min_priority == NotificationPriority.LOW
        assert subscription.active is True
        assert subscription.verified is False
        assert subscription.name == ""
        assert subscription.description is None
        assert subscription.last_triggered_at is None
        assert subscription.last_success_at is None
        assert subscription.last_failure_at is None

    def test_webhook_stats_defaults(self):
        """Webhook subscription stats have default values."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
        )
        assert subscription.total_sent == 0
        assert subscription.total_success == 0
        assert subscription.total_failure == 0
        assert subscription.consecutive_failures == 0

    def test_webhook_with_events(self):
        """Webhook subscription with specific events."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
            events=[
                NotificationEvent.PROPOSAL_CREATED,
                NotificationEvent.PROPOSAL_PASSED,
            ],
        )
        assert len(subscription.events) == 2
        assert NotificationEvent.PROPOSAL_CREATED in subscription.events

    def test_webhook_with_filters(self):
        """Webhook subscription with capsule type filters."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
            filter_capsule_types=["INSIGHT", "DECISION"],
            filter_min_priority=NotificationPriority.HIGH,
        )
        assert subscription.filter_capsule_types == ["INSIGHT", "DECISION"]
        assert subscription.filter_min_priority == NotificationPriority.HIGH

    def test_webhook_id_generated(self):
        """Webhook ID is auto-generated."""
        sub1 = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
        )
        sub2 = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
        )
        assert sub1.id != sub2.id

    def test_webhook_created_at(self):
        """Webhook has created_at timestamp."""
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
        )
        assert subscription.created_at is not None
        assert isinstance(subscription.created_at, datetime)

    def test_webhook_with_all_fields(self):
        """Webhook with all optional fields set."""
        now = datetime.now(UTC)
        subscription = WebhookSubscription(
            user_id="user123",
            url="https://example.com/webhook",
            secret="secret",
            events=[NotificationEvent.CAPSULE_CREATED],
            filter_capsule_types=["INSIGHT"],
            filter_min_priority=NotificationPriority.NORMAL,
            active=False,
            verified=True,
            name="My Webhook",
            description="For testing",
            last_triggered_at=now,
            last_success_at=now,
            last_failure_at=now - timedelta(days=1),
            total_sent=100,
            total_success=95,
            total_failure=5,
            consecutive_failures=0,
        )
        assert subscription.active is False
        assert subscription.verified is True
        assert subscription.total_sent == 100


# =============================================================================
# Notification Tests
# =============================================================================


class TestNotification:
    """Tests for Notification model."""

    def test_valid_notification(self):
        """Valid notification creation."""
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="New Proposal",
            message="A new proposal has been created.",
        )
        assert notification.user_id == "user123"
        assert notification.event_type == NotificationEvent.PROPOSAL_CREATED
        assert notification.title == "New Proposal"
        assert notification.message == "A new proposal has been created."
        assert notification.id is not None

    def test_notification_defaults(self):
        """Notification has sensible defaults."""
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.CAPSULE_UPDATED,
            title="Update",
            message="Something was updated.",
        )
        assert notification.priority == NotificationPriority.NORMAL
        assert notification.data == {}
        assert notification.related_entity_id is None
        assert notification.related_entity_type is None
        assert notification.action_url is None
        assert notification.read is False
        assert notification.read_at is None
        assert notification.dismissed is False
        assert notification.dismissed_at is None
        assert notification.expires_at is None
        assert notification.source == "system"

    def test_notification_with_related_entity(self):
        """Notification with related entity."""
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.CAPSULE_CREATED,
            title="New Capsule",
            message="A new insight capsule was created.",
            related_entity_id="capsule456",
            related_entity_type="capsule",
            action_url="/capsules/capsule456",
        )
        assert notification.related_entity_id == "capsule456"
        assert notification.related_entity_type == "capsule"
        assert notification.action_url == "/capsules/capsule456"

    def test_notification_with_data(self):
        """Notification with additional data payload."""
        data: dict[str, Any] = {
            "proposal_id": "prop123",
            "votes_for": 10,
            "votes_against": 3,
        }
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.PROPOSAL_PASSED,
            title="Proposal Passed",
            message="Your proposal has passed!",
            data=data,
        )
        assert notification.data["proposal_id"] == "prop123"
        assert notification.data["votes_for"] == 10

    def test_notification_read_state(self):
        """Notification read state tracking."""
        now = datetime.now(UTC)
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.MENTION,
            title="Mentioned",
            message="You were mentioned.",
            read=True,
            read_at=now,
        )
        assert notification.read is True
        assert notification.read_at == now

    def test_notification_dismissed_state(self):
        """Notification dismissed state tracking."""
        now = datetime.now(UTC)
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.SYSTEM_DEGRADED,
            title="System Issue",
            message="System is degraded.",
            dismissed=True,
            dismissed_at=now,
        )
        assert notification.dismissed is True
        assert notification.dismissed_at == now

    def test_notification_title_max_length(self):
        """Title has maximum length constraint."""
        with pytest.raises(ValidationError):
            Notification(
                user_id="user123",
                event_type=NotificationEvent.ANOMALY_DETECTED,
                title="a" * 201,
                message="Test",
            )

    def test_notification_message_max_length(self):
        """Message has maximum length constraint."""
        with pytest.raises(ValidationError):
            Notification(
                user_id="user123",
                event_type=NotificationEvent.ANOMALY_DETECTED,
                title="Test",
                message="a" * 2001,
            )

    def test_notification_critical_priority(self):
        """Notification with critical priority."""
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.ISSUE_CRITICAL,
            title="Critical Issue",
            message="Immediate attention required.",
            priority=NotificationPriority.CRITICAL,
        )
        assert notification.priority == NotificationPriority.CRITICAL

    def test_notification_with_expiry(self):
        """Notification with expiration time."""
        expires = datetime.now(UTC) + timedelta(days=7)
        notification = Notification(
            user_id="user123",
            event_type=NotificationEvent.PROPOSAL_EXPIRING,
            title="Proposal Expiring",
            message="Vote now!",
            expires_at=expires,
        )
        assert notification.expires_at == expires


# =============================================================================
# WebhookDelivery Tests
# =============================================================================


class TestWebhookDelivery:
    """Tests for WebhookDelivery model."""

    def test_valid_webhook_delivery(self):
        """Valid webhook delivery creation."""
        delivery = WebhookDelivery(
            webhook_id="webhook123",
            event_type=NotificationEvent.CAPSULE_CREATED,
            payload={"capsule_id": "cap123"},
            signature="sha256=abcdef123456",
        )
        assert delivery.webhook_id == "webhook123"
        assert delivery.event_type == NotificationEvent.CAPSULE_CREATED
        assert delivery.payload == {"capsule_id": "cap123"}
        assert delivery.signature == "sha256=abcdef123456"
        assert delivery.id is not None

    def test_webhook_delivery_defaults(self):
        """Webhook delivery has sensible defaults."""
        delivery = WebhookDelivery(
            webhook_id="webhook123",
            event_type=NotificationEvent.SYNC_COMPLETED,
            payload={},
            signature="sha256=sig",
        )
        assert delivery.notification_id is None
        assert delivery.status_code is None
        assert delivery.response_body is None
        assert delivery.response_time_ms is None
        assert delivery.success is False
        assert delivery.error is None
        assert delivery.retry_count == 0
        assert delivery.next_retry_at is None
        assert delivery.completed_at is None

    def test_webhook_delivery_success(self):
        """Successful webhook delivery."""
        now = datetime.now(UTC)
        delivery = WebhookDelivery(
            webhook_id="webhook123",
            notification_id="notif456",
            event_type=NotificationEvent.PROPOSAL_PASSED,
            payload={"proposal_id": "prop123", "result": "passed"},
            signature="sha256=signature",
            status_code=200,
            response_body='{"ok": true}',
            response_time_ms=150.5,
            success=True,
            attempted_at=now,
            completed_at=now,
        )
        assert delivery.success is True
        assert delivery.status_code == 200
        assert delivery.response_time_ms == 150.5

    def test_webhook_delivery_failure(self):
        """Failed webhook delivery with error."""
        now = datetime.now(UTC)
        retry_at = now + timedelta(minutes=5)
        delivery = WebhookDelivery(
            webhook_id="webhook123",
            event_type=NotificationEvent.PEER_DISCONNECTED,
            payload={"peer_id": "peer456"},
            signature="sha256=sig",
            status_code=500,
            response_body="Internal Server Error",
            success=False,
            error="Server returned 500",
            retry_count=2,
            next_retry_at=retry_at,
            attempted_at=now,
        )
        assert delivery.success is False
        assert delivery.error == "Server returned 500"
        assert delivery.retry_count == 2
        assert delivery.next_retry_at == retry_at

    def test_webhook_delivery_timeout(self):
        """Webhook delivery timeout scenario."""
        delivery = WebhookDelivery(
            webhook_id="webhook123",
            event_type=NotificationEvent.SYNC_CONFLICT,
            payload={},
            signature="sha256=sig",
            success=False,
            error="Connection timeout after 30s",
            retry_count=1,
        )
        assert delivery.success is False
        assert "timeout" in delivery.error.lower()


# =============================================================================
# NotificationPreferences Tests
# =============================================================================


class TestNotificationPreferences:
    """Tests for NotificationPreferences model."""

    def test_valid_preferences(self):
        """Valid notification preferences creation."""
        preferences = NotificationPreferences(user_id="user123")
        assert preferences.user_id == "user123"
        assert preferences.id is not None

    def test_preferences_defaults(self):
        """Notification preferences have sensible defaults."""
        preferences = NotificationPreferences(user_id="user123")
        assert preferences.channel_preferences == {}
        assert preferences.mute_all is False
        assert preferences.mute_until is None
        assert preferences.quiet_hours_start is None
        assert preferences.quiet_hours_end is None
        assert preferences.digest_enabled is False
        assert preferences.digest_frequency == DigestFrequency.DAILY
        assert preferences.default_channels == [DeliveryChannel.IN_APP]

    def test_preferences_channel_mapping(self):
        """Preferences with channel mappings per event type."""
        channel_prefs: dict[str, list[DeliveryChannel]] = {
            "proposal.created": [DeliveryChannel.IN_APP, DeliveryChannel.WEBHOOK],
            "issue.critical": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
        }
        preferences = NotificationPreferences(
            user_id="user123",
            channel_preferences=channel_prefs,
        )
        assert len(preferences.channel_preferences) == 2
        assert DeliveryChannel.WEBHOOK in preferences.channel_preferences["proposal.created"]

    def test_preferences_mute_until(self):
        """Preferences with mute until timestamp."""
        mute_until = datetime.now(UTC) + timedelta(hours=2)
        preferences = NotificationPreferences(
            user_id="user123",
            mute_all=True,
            mute_until=mute_until,
        )
        assert preferences.mute_all is True
        assert preferences.mute_until == mute_until

    def test_preferences_quiet_hours(self):
        """Preferences with quiet hours."""
        preferences = NotificationPreferences(
            user_id="user123",
            quiet_hours_start=22,  # 10 PM
            quiet_hours_end=7,     # 7 AM
        )
        assert preferences.quiet_hours_start == 22
        assert preferences.quiet_hours_end == 7

    def test_quiet_hours_min_value(self):
        """Quiet hours start has minimum value constraint."""
        with pytest.raises(ValidationError):
            NotificationPreferences(
                user_id="user123",
                quiet_hours_start=-1,
            )

    def test_quiet_hours_max_value(self):
        """Quiet hours has maximum value constraint."""
        with pytest.raises(ValidationError):
            NotificationPreferences(
                user_id="user123",
                quiet_hours_start=24,
            )
        with pytest.raises(ValidationError):
            NotificationPreferences(
                user_id="user123",
                quiet_hours_end=24,
            )

    def test_preferences_digest_settings(self):
        """Preferences with digest settings."""
        preferences = NotificationPreferences(
            user_id="user123",
            digest_enabled=True,
            digest_frequency=DigestFrequency.WEEKLY,
        )
        assert preferences.digest_enabled is True
        assert preferences.digest_frequency == DigestFrequency.WEEKLY

    def test_preferences_custom_default_channels(self):
        """Preferences with custom default channels."""
        preferences = NotificationPreferences(
            user_id="user123",
            default_channels=[DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
        )
        assert len(preferences.default_channels) == 2
        assert DeliveryChannel.EMAIL in preferences.default_channels

    def test_preferences_updated_at(self):
        """Preferences have updated_at timestamp."""
        preferences = NotificationPreferences(user_id="user123")
        assert preferences.updated_at is not None
        assert isinstance(preferences.updated_at, datetime)


# =============================================================================
# WebhookPayload Tests
# =============================================================================


class TestWebhookPayload:
    """Tests for WebhookPayload model."""

    def test_valid_webhook_payload(self):
        """Valid webhook payload creation."""
        now = datetime.now(UTC)
        payload = WebhookPayload(
            event="proposal.created",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data={"proposal_id": "prop789"},
        )
        assert payload.event == "proposal.created"
        assert payload.timestamp == now
        assert payload.webhook_id == "webhook123"
        assert payload.delivery_id == "delivery456"
        assert payload.data["proposal_id"] == "prop789"

    def test_webhook_payload_signature_optional(self):
        """Signature is optional on payload."""
        now = datetime.now(UTC)
        payload = WebhookPayload(
            event="capsule.updated",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data={},
        )
        assert payload.signature is None

    def test_webhook_payload_with_signature(self):
        """Payload with signature included."""
        now = datetime.now(UTC)
        payload = WebhookPayload(
            event="sync.completed",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data={"sync_id": "sync789"},
            signature="sha256=abcdef123456789",
        )
        assert payload.signature == "sha256=abcdef123456789"

    def test_to_dict_for_signing(self):
        """to_dict_for_signing returns correct dict structure."""
        now = datetime.now(UTC)
        payload = WebhookPayload(
            event="proposal.passed",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data={"result": "approved"},
            signature="sha256=sig",  # Should NOT be in signing dict
        )

        signing_dict = payload.to_dict_for_signing()

        assert signing_dict["event"] == "proposal.passed"
        assert signing_dict["timestamp"] == now.isoformat()
        assert signing_dict["webhook_id"] == "webhook123"
        assert signing_dict["delivery_id"] == "delivery456"
        assert signing_dict["data"] == {"result": "approved"}
        assert "signature" not in signing_dict

    def test_to_dict_for_signing_empty_data(self):
        """to_dict_for_signing works with empty data."""
        now = datetime.now(UTC)
        payload = WebhookPayload(
            event="system.recovered",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data={},
        )

        signing_dict = payload.to_dict_for_signing()
        assert signing_dict["data"] == {}

    def test_webhook_payload_complex_data(self):
        """Payload with complex nested data."""
        now = datetime.now(UTC)
        data: dict[str, Any] = {
            "capsule": {
                "id": "cap123",
                "type": "INSIGHT",
                "trust_score": 0.85,
            },
            "changes": ["title", "content"],
            "metadata": {
                "version": 2,
                "previous_trust": 0.75,
            },
        }
        payload = WebhookPayload(
            event="capsule.trust_change",
            timestamp=now,
            webhook_id="webhook123",
            delivery_id="delivery456",
            data=data,
        )
        assert payload.data["capsule"]["type"] == "INSIGHT"
        assert payload.data["changes"] == ["title", "content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
