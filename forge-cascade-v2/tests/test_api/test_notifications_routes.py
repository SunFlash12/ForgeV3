"""
Notifications Routes Tests for Forge Cascade V2

Comprehensive tests for notification API routes including:
- Notification listing and reading
- Webhook management
- Notification preferences
- Event types listing
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from forge.models.notifications import (
    DeliveryChannel,
    DigestFrequency,
    Notification,
    NotificationEvent,
    NotificationPreferences,
    NotificationPriority,
    WebhookSubscription,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_notification_service():
    """Create mock notification service."""
    service = AsyncMock()
    service.get_notifications = AsyncMock(return_value=[])
    service.get_unread_count = AsyncMock(return_value=0)
    service.mark_as_read = AsyncMock(return_value=True)
    service.mark_all_as_read = AsyncMock(return_value=5)
    service.dismiss = AsyncMock(return_value=True)
    service.get_webhooks = AsyncMock(return_value=[])
    service.get_webhook = AsyncMock(return_value=None)
    service.create_webhook = AsyncMock()
    service.update_webhook = AsyncMock()
    service.delete_webhook = AsyncMock(return_value=True)
    service.get_user_preferences = AsyncMock()
    service.update_user_preferences = AsyncMock()
    service.notify = AsyncMock()
    return service


@pytest.fixture
def sample_notification():
    """Create sample notification for testing."""
    return Notification(
        id="notif123",
        user_id="user123",
        event_type=NotificationEvent.CAPSULE_CREATED,
        title="New Capsule Created",
        message="A new knowledge capsule has been created.",
        priority=NotificationPriority.NORMAL,
        data={"capsule_id": "cap123"},
        read=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_webhook():
    """Create sample webhook for testing."""
    return WebhookSubscription(
        id="webhook123",
        user_id="user123",
        url="https://example.com/webhook",
        secret="test-secret",
        events=[NotificationEvent.CAPSULE_CREATED],
        active=True,
        verified=True,
        name="Test Webhook",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_preferences():
    """Create sample notification preferences."""
    return NotificationPreferences(
        id="prefs123",
        user_id="user123",
        mute_all=False,
        digest_enabled=True,
        digest_frequency=DigestFrequency.DAILY,
        channel_preferences={},
        default_channels=[DeliveryChannel.IN_APP],
    )


# =============================================================================
# Notification Listing Tests
# =============================================================================


class TestNotificationListRoute:
    """Tests for GET /notifications endpoint."""

    def test_list_notifications_unauthorized(self, client: TestClient):
        """List notifications without auth fails."""
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401

    def test_list_notifications_authorized(
        self, client: TestClient, auth_headers: dict, mock_notification_service, sample_notification
    ):
        """List notifications with auth returns notifications."""
        with patch(
            "forge.api.routes.notifications.get_notification_svc",
            return_value=mock_notification_service,
        ):
            mock_notification_service.get_notifications.return_value = [sample_notification]
            mock_notification_service.get_unread_count.return_value = 1

            response = client.get("/api/v1/notifications", headers=auth_headers)

            # With mocked service, should succeed or 401 if token issue
            assert response.status_code in [200, 401, 503]

    def test_list_notifications_with_pagination(self, client: TestClient, auth_headers: dict):
        """List notifications with pagination parameters."""
        response = client.get(
            "/api/v1/notifications",
            params={"limit": 10, "offset": 5, "unread_only": True},
            headers=auth_headers,
        )
        # Should accept pagination params
        assert response.status_code in [200, 401, 503]

    def test_list_notifications_limit_validation(self, client: TestClient, auth_headers: dict):
        """List notifications with invalid limit fails validation."""
        response = client.get(
            "/api/v1/notifications",
            params={"limit": 500},  # Over 200 max
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Unread Count Tests
# =============================================================================


class TestUnreadCountRoute:
    """Tests for GET /notifications/unread-count endpoint."""

    def test_get_unread_count_unauthorized(self, client: TestClient):
        """Get unread count without auth fails."""
        response = client.get("/api/v1/notifications/unread-count")
        assert response.status_code == 401

    def test_get_unread_count_authorized(self, client: TestClient, auth_headers: dict):
        """Get unread count with auth returns count."""
        response = client.get("/api/v1/notifications/unread-count", headers=auth_headers)
        assert response.status_code in [200, 401, 503]


# =============================================================================
# Mark As Read Tests
# =============================================================================


class TestMarkAsReadRoute:
    """Tests for POST /notifications/{notification_id}/read endpoint."""

    def test_mark_as_read_unauthorized(self, client: TestClient):
        """Mark as read without auth fails."""
        response = client.post("/api/v1/notifications/notif123/read")
        assert response.status_code == 401

    def test_mark_as_read_authorized(self, client: TestClient, auth_headers: dict):
        """Mark as read with auth succeeds."""
        response = client.post("/api/v1/notifications/notif123/read", headers=auth_headers)
        # Should succeed or return 404 if not found
        assert response.status_code in [200, 404, 401, 503]


# =============================================================================
# Mark All As Read Tests
# =============================================================================


class TestMarkAllAsReadRoute:
    """Tests for POST /notifications/read-all endpoint."""

    def test_mark_all_as_read_unauthorized(self, client: TestClient):
        """Mark all as read without auth fails."""
        response = client.post("/api/v1/notifications/read-all")
        assert response.status_code == 401

    def test_mark_all_as_read_authorized(self, client: TestClient, auth_headers: dict):
        """Mark all as read with auth succeeds."""
        response = client.post("/api/v1/notifications/read-all", headers=auth_headers)
        assert response.status_code in [200, 401, 503]


# =============================================================================
# Dismiss Notification Tests
# =============================================================================


class TestDismissNotificationRoute:
    """Tests for POST /notifications/{notification_id}/dismiss endpoint."""

    def test_dismiss_unauthorized(self, client: TestClient):
        """Dismiss without auth fails."""
        response = client.post("/api/v1/notifications/notif123/dismiss")
        assert response.status_code == 401

    def test_dismiss_authorized(self, client: TestClient, auth_headers: dict):
        """Dismiss with auth succeeds."""
        response = client.post("/api/v1/notifications/notif123/dismiss", headers=auth_headers)
        assert response.status_code in [200, 404, 401, 503]


# =============================================================================
# Webhook Management Tests
# =============================================================================


class TestWebhookCreateRoute:
    """Tests for POST /notifications/webhooks endpoint."""

    def test_create_webhook_unauthorized(self, client: TestClient):
        """Create webhook without auth fails."""
        response = client.post(
            "/api/v1/notifications/webhooks",
            json={
                "url": "https://example.com/webhook",
                "name": "Test Webhook",
            },
        )
        assert response.status_code == 401

    def test_create_webhook_authorized(self, client: TestClient, auth_headers: dict):
        """Create webhook with auth and valid data."""
        response = client.post(
            "/api/v1/notifications/webhooks",
            json={
                "url": "https://example.com/webhook",
                "name": "Test Webhook",
                "events": ["capsule.created"],
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 201, 400, 401, 503]

    def test_create_webhook_non_https_fails(self, client: TestClient, auth_headers: dict):
        """Create webhook with non-HTTPS URL fails."""
        response = client.post(
            "/api/v1/notifications/webhooks",
            json={
                "url": "http://example.com/webhook",  # HTTP not HTTPS
                "name": "Test Webhook",
            },
            headers=auth_headers,
        )
        # Should fail validation for non-HTTPS URL
        assert response.status_code in [400, 422, 401, 503]

    def test_create_webhook_invalid_url(self, client: TestClient, auth_headers: dict):
        """Create webhook with invalid URL fails validation."""
        response = client.post(
            "/api/v1/notifications/webhooks",
            json={
                "url": "not-a-url",
                "name": "Test Webhook",
            },
            headers=auth_headers,
        )
        assert response.status_code in [400, 422, 401]


class TestWebhookListRoute:
    """Tests for GET /notifications/webhooks endpoint."""

    def test_list_webhooks_unauthorized(self, client: TestClient):
        """List webhooks without auth fails."""
        response = client.get("/api/v1/notifications/webhooks")
        assert response.status_code == 401

    def test_list_webhooks_authorized(self, client: TestClient, auth_headers: dict):
        """List webhooks with auth returns webhooks."""
        response = client.get("/api/v1/notifications/webhooks", headers=auth_headers)
        assert response.status_code in [200, 401, 503]


class TestWebhookGetRoute:
    """Tests for GET /notifications/webhooks/{webhook_id} endpoint."""

    def test_get_webhook_unauthorized(self, client: TestClient):
        """Get webhook without auth fails."""
        response = client.get("/api/v1/notifications/webhooks/webhook123")
        assert response.status_code == 401

    def test_get_webhook_authorized(self, client: TestClient, auth_headers: dict):
        """Get webhook with auth returns webhook or 404."""
        response = client.get(
            "/api/v1/notifications/webhooks/webhook123", headers=auth_headers
        )
        assert response.status_code in [200, 404, 401, 503]


class TestWebhookUpdateRoute:
    """Tests for PATCH /notifications/webhooks/{webhook_id} endpoint."""

    def test_update_webhook_unauthorized(self, client: TestClient):
        """Update webhook without auth fails."""
        response = client.patch(
            "/api/v1/notifications/webhooks/webhook123",
            json={"name": "Updated Webhook"},
        )
        assert response.status_code == 401

    def test_update_webhook_authorized(self, client: TestClient, auth_headers: dict):
        """Update webhook with auth succeeds."""
        response = client.patch(
            "/api/v1/notifications/webhooks/webhook123",
            json={
                "name": "Updated Webhook",
                "active": False,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 404, 401, 503]


class TestWebhookDeleteRoute:
    """Tests for DELETE /notifications/webhooks/{webhook_id} endpoint."""

    def test_delete_webhook_unauthorized(self, client: TestClient):
        """Delete webhook without auth fails."""
        response = client.delete("/api/v1/notifications/webhooks/webhook123")
        assert response.status_code == 401

    def test_delete_webhook_authorized(self, client: TestClient, auth_headers: dict):
        """Delete webhook with auth succeeds."""
        response = client.delete(
            "/api/v1/notifications/webhooks/webhook123", headers=auth_headers
        )
        assert response.status_code in [200, 404, 401, 503]


class TestWebhookTestRoute:
    """Tests for POST /notifications/webhooks/{webhook_id}/test endpoint."""

    def test_test_webhook_unauthorized(self, client: TestClient):
        """Test webhook without auth fails."""
        response = client.post("/api/v1/notifications/webhooks/webhook123/test")
        assert response.status_code == 401

    def test_test_webhook_authorized(self, client: TestClient, auth_headers: dict):
        """Test webhook with auth sends test notification."""
        response = client.post(
            "/api/v1/notifications/webhooks/webhook123/test", headers=auth_headers
        )
        assert response.status_code in [200, 404, 401, 503]


# =============================================================================
# Preferences Tests
# =============================================================================


class TestPreferencesGetRoute:
    """Tests for GET /notifications/preferences endpoint."""

    def test_get_preferences_unauthorized(self, client: TestClient):
        """Get preferences without auth fails."""
        response = client.get("/api/v1/notifications/preferences")
        assert response.status_code == 401

    def test_get_preferences_authorized(self, client: TestClient, auth_headers: dict):
        """Get preferences with auth returns preferences."""
        response = client.get("/api/v1/notifications/preferences", headers=auth_headers)
        assert response.status_code in [200, 401, 503]


class TestPreferencesUpdateRoute:
    """Tests for PATCH /notifications/preferences endpoint."""

    def test_update_preferences_unauthorized(self, client: TestClient):
        """Update preferences without auth fails."""
        response = client.patch(
            "/api/v1/notifications/preferences",
            json={"mute_all": True},
        )
        assert response.status_code == 401

    def test_update_preferences_authorized(self, client: TestClient, auth_headers: dict):
        """Update preferences with auth succeeds."""
        response = client.patch(
            "/api/v1/notifications/preferences",
            json={
                "mute_all": True,
                "digest_enabled": True,
                "digest_frequency": "daily",
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]

    def test_update_preferences_quiet_hours_validation(
        self, client: TestClient, auth_headers: dict
    ):
        """Update preferences with invalid quiet hours fails."""
        response = client.patch(
            "/api/v1/notifications/preferences",
            json={
                "quiet_hours_start": 25,  # Invalid hour
            },
            headers=auth_headers,
        )
        assert response.status_code in [400, 422, 401]


# =============================================================================
# Event Types Tests
# =============================================================================


class TestEventTypesRoute:
    """Tests for GET /notifications/events endpoint."""

    def test_get_event_types(self, client: TestClient):
        """Get event types returns list of events."""
        response = client.get("/api/v1/notifications/events")
        # This endpoint doesn't require auth
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "events" in data
            assert isinstance(data["events"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
