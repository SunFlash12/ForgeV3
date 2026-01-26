"""
Notification API Routes

Endpoints for managing notifications and webhooks.
"""

import logging
import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

from forge.api.dependencies import ActiveUserDep
from forge.models.notifications import (
    NotificationEvent,
    NotificationPriority,
)
from forge.services.notifications import NotificationService, get_notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateWebhookRequest(BaseModel):
    """Request to create a webhook."""

    url: HttpUrl = Field(description="HTTPS URL to receive notifications")
    name: str = Field(default="", max_length=100)
    events: list[NotificationEvent] = Field(
        default_factory=list, description="Events to subscribe to (empty = all)"
    )
    filter_min_priority: NotificationPriority = Field(default=NotificationPriority.LOW)


class UpdateWebhookRequest(BaseModel):
    """Request to update a webhook."""

    name: str | None = None
    events: list[NotificationEvent] | None = None
    filter_min_priority: NotificationPriority | None = None
    active: bool | None = None


class WebhookResponse(BaseModel):
    """Webhook information response."""

    id: str
    name: str
    url: str
    events: list[str]
    filter_min_priority: str
    active: bool
    verified: bool
    created_at: datetime
    last_triggered_at: datetime | None
    total_sent: int
    total_success: int
    total_failure: int
    # Secret only returned on creation
    secret: str | None = None


class NotificationResponse(BaseModel):
    """Notification response."""

    id: str
    event_type: str
    title: str
    message: str
    priority: str
    data: dict[str, Any]
    related_entity_id: str | None
    related_entity_type: str | None
    action_url: str | None
    read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """List of notifications."""

    notifications: list[NotificationResponse]
    unread_count: int
    total: int


class UpdatePreferencesRequest(BaseModel):
    """Request to update notification preferences."""

    mute_all: bool | None = None
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)
    digest_enabled: bool | None = None
    digest_frequency: str | None = None
    channel_preferences: dict[str, list[str]] | None = None


class PreferencesResponse(BaseModel):
    """Notification preferences response."""

    mute_all: bool
    mute_until: datetime | None
    quiet_hours_start: int | None
    quiet_hours_end: int | None
    digest_enabled: bool
    digest_frequency: str
    channel_preferences: dict[str, list[str]]
    default_channels: list[str]


# ============================================================================
# Dependencies
# ============================================================================


async def get_notification_svc() -> NotificationService:
    """Get notification service dependency."""
    return await get_notification_service()


NotificationSvcDep = Depends(get_notification_svc)


# ============================================================================
# Notification Endpoints
# ============================================================================


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    user: ActiveUserDep,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    svc: NotificationService = NotificationSvcDep,
) -> NotificationListResponse:
    """Get notifications for the current user."""
    notifications = await svc.get_notifications(
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = await svc.get_unread_count(user.id)

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                event_type=n.event_type.value,
                title=n.title,
                message=n.message,
                priority=n.priority.value,
                data=n.data,
                related_entity_id=n.related_entity_id,
                related_entity_type=n.related_entity_type,
                action_url=n.action_url,
                read=n.read,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        unread_count=unread_count,
        total=len(notifications),
    )


@router.get("/unread-count")
async def get_unread_count(
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, int]:
    """Get count of unread notifications."""
    count = await svc.get_unread_count(user.id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, bool]:
    """Mark a notification as read."""
    success = await svc.mark_as_read(notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, int]:
    """Mark all notifications as read."""
    count = await svc.mark_all_as_read(user.id)
    return {"marked_read": count}


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: str,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, bool]:
    """Dismiss a notification."""
    success = await svc.dismiss(notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


# ============================================================================
# Webhook Endpoints
# ============================================================================


@router.post("/webhooks", response_model=WebhookResponse)
async def create_webhook(
    request: CreateWebhookRequest,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> WebhookResponse:
    """
    Create a new webhook subscription.

    Returns the webhook with its secret (only shown once).
    """
    # Validate URL is HTTPS
    if not str(request.url).startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS")

    # Generate secret
    secret = secrets.token_urlsafe(32)

    webhook = await svc.create_webhook(
        user_id=user.id,
        url=str(request.url),
        secret=secret,
        events=request.events,  # Already list[NotificationEvent] from model
        name=request.name,
    )

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        filter_min_priority=webhook.filter_min_priority.value,
        active=webhook.active,
        verified=webhook.verified,
        created_at=webhook.created_at,
        last_triggered_at=webhook.last_triggered_at,
        total_sent=webhook.total_sent,
        total_success=webhook.total_success,
        total_failure=webhook.total_failure,
        secret=secret,  # Only returned on creation
    )


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> list[WebhookResponse]:
    """List all webhooks for the current user."""
    webhooks = await svc.get_webhooks(user.id)

    return [
        WebhookResponse(
            id=w.id,
            name=w.name,
            url=w.url,
            events=[e.value for e in w.events],
            filter_min_priority=w.filter_min_priority.value,
            active=w.active,
            verified=w.verified,
            created_at=w.created_at,
            last_triggered_at=w.last_triggered_at,
            total_sent=w.total_sent,
            total_success=w.total_success,
            total_failure=w.total_failure,
        )
        for w in webhooks
    ]


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> WebhookResponse:
    """Get details for a specific webhook."""
    webhook = await svc.get_webhook(webhook_id)

    if not webhook or webhook.user_id != user.id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        filter_min_priority=webhook.filter_min_priority.value,
        active=webhook.active,
        verified=webhook.verified,
        created_at=webhook.created_at,
        last_triggered_at=webhook.last_triggered_at,
        total_sent=webhook.total_sent,
        total_success=webhook.total_success,
        total_failure=webhook.total_failure,
    )


@router.patch("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    request: UpdateWebhookRequest,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> WebhookResponse:
    """Update a webhook."""
    updates = request.model_dump(exclude_none=True)

    webhook = await svc.update_webhook(webhook_id, user.id, updates)

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=webhook.id,
        name=webhook.name,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        filter_min_priority=webhook.filter_min_priority.value,
        active=webhook.active,
        verified=webhook.verified,
        created_at=webhook.created_at,
        last_triggered_at=webhook.last_triggered_at,
        total_sent=webhook.total_sent,
        total_success=webhook.total_success,
        total_failure=webhook.total_failure,
    )


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, bool]:
    """Delete a webhook."""
    success = await svc.delete_webhook(webhook_id, user.id)

    if not success:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {"deleted": True}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> dict[str, Any]:
    """Send a test notification to a webhook."""
    webhook = await svc.get_webhook(webhook_id)

    if not webhook or webhook.user_id != user.id:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Create test notification
    notification = await svc.notify(
        user_id=user.id,
        event_type=NotificationEvent.ISSUE_DETECTED,
        title="Test Notification",
        message="This is a test notification from Forge.",
        data={"test": True},
        priority=NotificationPriority.NORMAL,
        source="api.test",
    )

    return {
        "sent": True,
        "notification_id": notification.id,
    }


# ============================================================================
# Preferences Endpoints
# ============================================================================


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> PreferencesResponse:
    """Get notification preferences for the current user."""
    prefs = await svc.get_user_preferences(user.id)

    return PreferencesResponse(
        mute_all=prefs.mute_all,
        mute_until=prefs.mute_until,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
        digest_enabled=prefs.digest_enabled,
        digest_frequency=prefs.digest_frequency.value,
        channel_preferences={k: [c.value for c in v] for k, v in prefs.channel_preferences.items()},
        default_channels=[c.value for c in prefs.default_channels],
    )


@router.patch("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    user: ActiveUserDep,
    svc: NotificationService = NotificationSvcDep,
) -> PreferencesResponse:
    """Update notification preferences."""
    updates = request.model_dump(exclude_none=True)

    prefs = await svc.update_user_preferences(user.id, updates)

    return PreferencesResponse(
        mute_all=prefs.mute_all,
        mute_until=prefs.mute_until,
        quiet_hours_start=prefs.quiet_hours_start,
        quiet_hours_end=prefs.quiet_hours_end,
        digest_enabled=prefs.digest_enabled,
        digest_frequency=prefs.digest_frequency.value,
        channel_preferences={k: [c.value for c in v] for k, v in prefs.channel_preferences.items()},
        default_channels=[c.value for c in prefs.default_channels],
    )


# ============================================================================
# Event Types Info
# ============================================================================


@router.get("/events")
async def list_event_types() -> dict[str, list[dict[str, str]]]:
    """Get list of available notification event types."""
    events = []
    for event in NotificationEvent:
        category = event.value.split(".")[0]
        events.append(
            {
                "event": event.value,
                "category": category,
                "description": _get_event_description(event),
            }
        )

    return {"events": events}


def _get_event_description(event: NotificationEvent) -> str:
    """Get human-readable description for an event type."""
    descriptions = {
        NotificationEvent.PROPOSAL_CREATED: "New governance proposal created",
        NotificationEvent.PROPOSAL_PASSED: "Proposal passed voting",
        NotificationEvent.PROPOSAL_REJECTED: "Proposal rejected",
        NotificationEvent.PROPOSAL_NEEDS_VOTE: "Proposal needs your vote",
        NotificationEvent.PROPOSAL_EXPIRING: "Proposal voting ending soon",
        NotificationEvent.ISSUE_DETECTED: "Ghost Council detected an issue",
        NotificationEvent.ISSUE_CRITICAL: "Critical issue detected",
        NotificationEvent.COUNCIL_RECOMMENDATION: "Ghost Council made a recommendation",
        NotificationEvent.COUNCIL_VOTE_COMPLETE: "Ghost Council vote completed",
        NotificationEvent.CAPSULE_CREATED: "New capsule created",
        NotificationEvent.CAPSULE_UPDATED: "Capsule updated",
        NotificationEvent.CAPSULE_CONTRADICTION: "Contradiction detected in capsule",
        NotificationEvent.CAPSULE_TRUST_CHANGE: "Capsule trust level changed",
        NotificationEvent.CAPSULE_CITED: "Your capsule was cited",
        NotificationEvent.PEER_CONNECTED: "Federated peer connected",
        NotificationEvent.PEER_DISCONNECTED: "Federated peer disconnected",
        NotificationEvent.SYNC_COMPLETED: "Sync with peer completed",
        NotificationEvent.SYNC_CONFLICT: "Sync conflict detected",
        NotificationEvent.ANOMALY_DETECTED: "Anomaly detected in system",
        NotificationEvent.SYSTEM_DEGRADED: "System performance degraded",
        NotificationEvent.SYSTEM_RECOVERED: "System recovered",
        NotificationEvent.TRUST_FLAME_CHANGE: "Your trust flame changed",
        NotificationEvent.MENTION: "You were mentioned",
    }
    return descriptions.get(event, event.value)
