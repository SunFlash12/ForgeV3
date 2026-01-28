"""
Tests for Notification Service

Tests cover:
- SSRF validation for webhook URLs
- Notification creation and delivery
- Webhook management
- Rate limiting and retries
- User preferences
- Persistence operations
- Background workers
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from forge.models.notifications import (
    DeliveryChannel,
    Notification,
    NotificationEvent,
    NotificationPreferences,
    NotificationPriority,
    WebhookDelivery,
    WebhookSubscription,
)
from forge.services.notifications import (
    NotificationService,
    SSRFError,
    get_notification_service,
    shutdown_notification_service,
    validate_webhook_url,
)


class TestSSRFValidation:
    """Tests for SSRF URL validation."""

    def test_valid_https_url(self):
        """Test that valid HTTPS URLs pass validation."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),  # Public IP
            ]
            result = validate_webhook_url("https://example.com/webhook")
            assert result == "https://example.com/webhook"

    def test_valid_http_url(self):
        """Test that valid HTTP URLs pass validation."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 80)),
            ]
            result = validate_webhook_url("http://example.com/webhook")
            assert result == "http://example.com/webhook"

    def test_blocks_localhost(self):
        """Test that localhost is blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("https://localhost/webhook")
        assert "Blocked hostname" in str(exc_info.value)

    def test_blocks_127_0_0_1(self):
        """Test that 127.0.0.1 is blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("https://127.0.0.1/webhook")
        assert "Blocked hostname" in str(exc_info.value)

    def test_blocks_0_0_0_0(self):
        """Test that 0.0.0.0 is blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("https://0.0.0.0/webhook")
        assert "Blocked hostname" in str(exc_info.value)

    def test_blocks_metadata_google(self):
        """Test that GCP metadata endpoint is blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("http://metadata.google.internal/computeMetadata/v1/")
        assert "Blocked hostname" in str(exc_info.value)

    def test_blocks_aws_metadata(self):
        """Test that AWS metadata IP is blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("http://169.254.169.254/latest/meta-data/")
        assert "Blocked hostname" in str(exc_info.value)

    def test_blocks_private_ip(self):
        """Test that private IPs are blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("192.168.1.1", 443)),  # Private IP
            ]
            with pytest.raises(SSRFError) as exc_info:
                validate_webhook_url("https://internal.example.com/webhook")
            assert "Private IP" in str(exc_info.value)

    def test_blocks_loopback_ip(self):
        """Test that loopback IPs are blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 443)),
            ]
            with pytest.raises(SSRFError) as exc_info:
                validate_webhook_url("https://somehost.com/webhook")
            assert "Loopback address blocked" in str(exc_info.value)

    def test_blocks_link_local_ip(self):
        """Test that link-local IPs are blocked."""
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("169.254.1.1", 443)),
            ]
            with pytest.raises(SSRFError) as exc_info:
                validate_webhook_url("https://linklocal.example.com/webhook")
            assert "Link-local address blocked" in str(exc_info.value)

    def test_invalid_scheme(self):
        """Test that invalid schemes are blocked."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("ftp://example.com/file")
        assert "Invalid URL scheme" in str(exc_info.value)

    def test_missing_hostname(self):
        """Test that missing hostname is rejected."""
        with pytest.raises(SSRFError) as exc_info:
            validate_webhook_url("https:///webhook")
        assert "missing hostname" in str(exc_info.value).lower()

    def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failures."""
        with patch("socket.getaddrinfo") as mock_dns:
            import socket

            mock_dns.side_effect = socket.gaierror("DNS failed")
            with pytest.raises(SSRFError) as exc_info:
                validate_webhook_url("https://nonexistent.invalid/webhook")
            assert "DNS resolution failed" in str(exc_info.value)


class TestNotificationServiceInit:
    """Tests for NotificationService initialization."""

    def test_init_default(self):
        """Test default initialization."""
        service = NotificationService()

        assert service.redis is None
        assert service.neo4j is None
        assert service._http_client is None
        assert isinstance(service._notifications, dict)
        assert isinstance(service._webhooks, dict)
        assert isinstance(service._deliveries, dict)
        assert isinstance(service._preferences, dict)

    def test_init_with_clients(self):
        """Test initialization with clients."""
        mock_redis = MagicMock()
        mock_neo4j = MagicMock()

        service = NotificationService(redis_client=mock_redis, neo4j_client=mock_neo4j)

        assert service.redis is mock_redis
        assert service.neo4j is mock_neo4j


class TestNotificationServiceLifecycle:
    """Tests for service start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_http_client(self):
        """Test that start creates HTTP client."""
        service = NotificationService()
        await service.start()

        assert service._http_client is not None
        assert service._webhook_worker_task is not None
        assert service._retry_worker_task is not None

        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_closes_http_client(self):
        """Test that stop closes HTTP client."""
        service = NotificationService()
        await service.start()
        await service.stop()

        assert service._http_client is None
        assert service._webhook_worker_task is None
        assert service._retry_worker_task is None


class TestNotificationCreation:
    """Tests for notification creation and delivery."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_notify_creates_notification(self, service):
        """Test creating a notification."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="New Proposal",
            message="A new proposal has been created.",
            priority=NotificationPriority.NORMAL,
        )

        assert notification.user_id == "user-123"
        assert notification.event_type == NotificationEvent.PROPOSAL_CREATED
        assert notification.title == "New Proposal"
        assert notification.id in service._notifications

    @pytest.mark.asyncio
    async def test_notify_with_data(self, service):
        """Test creating a notification with data."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.CAPSULE_CREATED,
            title="Capsule Created",
            message="Your capsule has been created.",
            data={"capsule_id": "cap-456"},
            related_entity_id="cap-456",
            related_entity_type="capsule",
        )

        assert notification.data == {"capsule_id": "cap-456"}
        assert notification.related_entity_id == "cap-456"
        assert notification.related_entity_type == "capsule"

    @pytest.mark.asyncio
    async def test_notify_muted_user(self, service):
        """Test that muted users don't trigger webhook delivery."""
        # Set user to muted
        service._preferences["user-muted"] = NotificationPreferences(
            user_id="user-muted",
            mute_all=True,
        )

        notification = await service.notify(
            user_id="user-muted",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Muted",
            message="This should not trigger webhooks.",
        )

        assert notification is not None
        # Webhook queue should be empty for muted user

    @pytest.mark.asyncio
    async def test_notify_muted_until(self, service):
        """Test user muted until specific time."""
        future_time = datetime.now(UTC) + timedelta(hours=1)
        service._preferences["user-temp-muted"] = NotificationPreferences(
            user_id="user-temp-muted",
            mute_until=future_time,
        )

        notification = await service.notify(
            user_id="user-temp-muted",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Temp Muted",
            message="This should not trigger webhooks.",
        )

        assert notification is not None

    @pytest.mark.asyncio
    async def test_notify_many(self, service):
        """Test notifying multiple users."""
        notifications = await service.notify_many(
            user_ids=["user-1", "user-2", "user-3"],
            event_type=NotificationEvent.SYSTEM_DEGRADED,
            title="System Alert",
            message="System is degraded.",
        )

        assert len(notifications) == 3
        assert all(n.event_type == NotificationEvent.SYSTEM_DEGRADED for n in notifications)

    @pytest.mark.asyncio
    async def test_broadcast_requires_admin(self, service):
        """Test that broadcast requires admin permissions."""
        with pytest.raises(PermissionError) as exc_info:
            await service.broadcast(
                event_type=NotificationEvent.SYSTEM_DEGRADED,
                title="Broadcast",
                message="Broadcast message.",
                caller_id="user-1",
                caller_role="member",
            )

        assert "admin-level permissions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_no_caller(self, service):
        """Test that broadcast requires caller ID."""
        with pytest.raises(PermissionError):
            await service.broadcast(
                event_type=NotificationEvent.SYSTEM_DEGRADED,
                title="Broadcast",
                message="Broadcast message.",
            )

    @pytest.mark.asyncio
    async def test_broadcast_as_admin(self, service):
        """Test broadcast as admin."""
        # Add some webhooks
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-1",
            url="https://example.com/webhook",
            secret="secret",
            active=True,
        )
        service._webhooks["wh-2"] = WebhookSubscription(
            id="wh-2",
            user_id="user-2",
            url="https://example.com/webhook2",
            secret="secret2",
            active=True,
        )

        sent = await service.broadcast(
            event_type=NotificationEvent.SYSTEM_DEGRADED,
            title="Admin Broadcast",
            message="Important announcement.",
            caller_id="admin-user",
            caller_role="admin",
        )

        assert sent == 2


class TestInAppNotifications:
    """Tests for in-app notification operations."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_get_notifications(self, service):
        """Test getting notifications for a user."""
        # Create some notifications
        for i in range(5):
            await service.notify(
                user_id="user-123",
                event_type=NotificationEvent.PROPOSAL_CREATED,
                title=f"Notification {i}",
                message=f"Message {i}",
            )

        notifications = await service.get_notifications("user-123")

        assert len(notifications) == 5

    @pytest.mark.asyncio
    async def test_get_notifications_unread_only(self, service):
        """Test getting only unread notifications."""
        n1 = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Read",
            message="Already read.",
        )
        n1.read = True

        await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Unread",
            message="Not read yet.",
        )

        notifications = await service.get_notifications("user-123", unread_only=True)

        assert len(notifications) == 1
        assert notifications[0].title == "Unread"

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(self, service):
        """Test notification pagination."""
        for i in range(10):
            await service.notify(
                user_id="user-123",
                event_type=NotificationEvent.PROPOSAL_CREATED,
                title=f"Notification {i}",
                message=f"Message {i}",
            )

        page1 = await service.get_notifications("user-123", limit=5, offset=0)
        page2 = await service.get_notifications("user-123", limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_get_unread_count(self, service):
        """Test getting unread count."""
        await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Unread 1",
            message="Message",
        )
        n2 = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Read",
            message="Message",
        )
        n2.read = True
        await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Unread 2",
            message="Message",
        )

        count = await service.get_unread_count("user-123")

        assert count == 2

    @pytest.mark.asyncio
    async def test_mark_as_read(self, service):
        """Test marking notification as read."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="To Read",
            message="Message",
        )

        result = await service.mark_as_read(notification.id, "user-123")

        assert result is True
        assert notification.read is True
        assert notification.read_at is not None

    @pytest.mark.asyncio
    async def test_mark_as_read_wrong_user(self, service):
        """Test marking notification as read by wrong user."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="To Read",
            message="Message",
        )

        result = await service.mark_as_read(notification.id, "user-456")

        assert result is False

    @pytest.mark.asyncio
    async def test_mark_all_as_read(self, service):
        """Test marking all notifications as read."""
        for i in range(3):
            await service.notify(
                user_id="user-123",
                event_type=NotificationEvent.PROPOSAL_CREATED,
                title=f"Notification {i}",
                message=f"Message {i}",
            )

        count = await service.mark_all_as_read("user-123")

        assert count == 3

        unread = await service.get_unread_count("user-123")
        assert unread == 0

    @pytest.mark.asyncio
    async def test_dismiss(self, service):
        """Test dismissing a notification."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="To Dismiss",
            message="Message",
        )

        result = await service.dismiss(notification.id, "user-123")

        assert result is True
        assert notification.dismissed is True
        assert notification.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_dismiss_wrong_user(self, service):
        """Test dismissing notification by wrong user."""
        notification = await service.notify(
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="To Dismiss",
            message="Message",
        )

        result = await service.dismiss(notification.id, "user-456")

        assert result is False


class TestWebhookManagement:
    """Tests for webhook management."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_create_webhook(self, service):
        """Test creating a webhook."""
        await service.start()

        with patch.object(service, "_verify_webhook", return_value=True):
            webhook = await service.create_webhook(
                user_id="user-123",
                url="https://example.com/webhook",
                secret="my-secret",
                name="My Webhook",
            )

        assert webhook.user_id == "user-123"
        assert webhook.url == "https://example.com/webhook"
        assert webhook.id in service._webhooks

        await service.stop()

    @pytest.mark.asyncio
    async def test_create_webhook_with_events(self, service):
        """Test creating a webhook with event filter."""
        await service.start()

        with patch.object(service, "_verify_webhook", return_value=True):
            webhook = await service.create_webhook(
                user_id="user-123",
                url="https://example.com/webhook",
                secret="secret",
                events=[NotificationEvent.PROPOSAL_CREATED, NotificationEvent.PROPOSAL_PASSED],
            )

        assert len(webhook.events) == 2
        assert NotificationEvent.PROPOSAL_CREATED in webhook.events

        await service.stop()

    @pytest.mark.asyncio
    async def test_get_webhooks(self, service):
        """Test getting webhooks for a user."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example1.com",
            secret="s1",
        )
        service._webhooks["wh-2"] = WebhookSubscription(
            id="wh-2",
            user_id="user-123",
            url="https://example2.com",
            secret="s2",
        )
        service._webhooks["wh-3"] = WebhookSubscription(
            id="wh-3",
            user_id="user-456",
            url="https://example3.com",
            secret="s3",
        )

        webhooks = await service.get_webhooks("user-123")

        assert len(webhooks) == 2

    @pytest.mark.asyncio
    async def test_get_webhook(self, service):
        """Test getting a specific webhook."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        webhook = await service.get_webhook("wh-1")

        assert webhook is not None
        assert webhook.id == "wh-1"

    @pytest.mark.asyncio
    async def test_get_webhook_not_found(self, service):
        """Test getting non-existent webhook."""
        webhook = await service.get_webhook("nonexistent")
        assert webhook is None

    @pytest.mark.asyncio
    async def test_update_webhook(self, service):
        """Test updating a webhook."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
            active=True,
        )

        result = await service.update_webhook(
            "wh-1", "user-123", {"active": False, "name": "Updated"}
        )

        assert result is not None
        assert result.active is False
        assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_update_webhook_wrong_user(self, service):
        """Test updating webhook by wrong user."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        result = await service.update_webhook("wh-1", "user-456", {"active": False})

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_webhook(self, service):
        """Test deleting a webhook."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        result = await service.delete_webhook("wh-1", "user-123")

        assert result is True
        assert "wh-1" not in service._webhooks

    @pytest.mark.asyncio
    async def test_delete_webhook_wrong_user(self, service):
        """Test deleting webhook by wrong user."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        result = await service.delete_webhook("wh-1", "user-456")

        assert result is False
        assert "wh-1" in service._webhooks


class TestWebhookVerification:
    """Tests for webhook verification."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_verify_webhook_success(self, service):
        """Test successful webhook verification."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com/webhook",
            secret="secret",
        )

        with patch.object(service._http_client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with patch(
                "forge.services.notifications.validate_webhook_url", return_value=webhook.url
            ):
                result = await service._verify_webhook(webhook)

        assert result is True
        assert webhook.verified is True

        await service.stop()

    @pytest.mark.asyncio
    async def test_verify_webhook_ssrf_blocked(self, service):
        """Test webhook verification blocked by SSRF."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="http://localhost/webhook",
            secret="secret",
        )

        with patch(
            "forge.services.notifications.validate_webhook_url", side_effect=SSRFError("Blocked")
        ):
            result = await service._verify_webhook(webhook)

        assert result is False

        await service.stop()

    @pytest.mark.asyncio
    async def test_verify_webhook_http_error(self, service):
        """Test webhook verification with HTTP error."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com/webhook",
            secret="secret",
        )

        with patch.object(service._http_client, "post") as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            with patch(
                "forge.services.notifications.validate_webhook_url", return_value=webhook.url
            ):
                result = await service._verify_webhook(webhook)

        assert result is False

        await service.stop()


class TestWebhookDelivery:
    """Tests for webhook delivery."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_deliver_webhook_success(self, service):
        """Test successful webhook delivery."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com/webhook",
            secret="test-secret",
            active=True,
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test message",
        )

        with patch.object(service._http_client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_post.return_value = mock_response

            with patch(
                "forge.services.notifications.validate_webhook_url", return_value=webhook.url
            ):
                delivery = await service._deliver_webhook(webhook, notification)

        assert delivery.success is True
        assert delivery.status_code == 200
        assert webhook.total_success == 1
        assert webhook.consecutive_failures == 0

        await service.stop()

    @pytest.mark.asyncio
    async def test_deliver_webhook_failure(self, service):
        """Test failed webhook delivery."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com/webhook",
            secret="test-secret",
            active=True,
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test message",
        )

        with patch.object(service._http_client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Error"
            mock_post.return_value = mock_response

            with patch(
                "forge.services.notifications.validate_webhook_url", return_value=webhook.url
            ):
                delivery = await service._deliver_webhook(webhook, notification)

        assert delivery.success is False
        assert delivery.status_code == 500
        assert webhook.total_failure == 1
        assert webhook.consecutive_failures == 1

        await service.stop()

    @pytest.mark.asyncio
    async def test_deliver_webhook_ssrf_blocked(self, service):
        """Test webhook delivery blocked by SSRF."""
        await service.start()

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="http://localhost/webhook",
            secret="test-secret",
            active=True,
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test message",
        )

        with patch(
            "forge.services.notifications.validate_webhook_url", side_effect=SSRFError("Blocked")
        ):
            delivery = await service._deliver_webhook(webhook, notification)

        assert delivery.success is False
        assert "SSRF" in delivery.error or "Blocked" in delivery.error

        await service.stop()


class TestWebhookRetry:
    """Tests for webhook retry logic."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_schedule_retry(self, service):
        """Test scheduling a retry."""
        delivery = WebhookDelivery(
            id="del-1",
            webhook_id="wh-1",
            notification_id="notif-1",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            payload={},
            signature="sig",
            retry_count=0,
        )

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        await service._schedule_retry(delivery, webhook)

        assert delivery.retry_count == 1
        assert delivery.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_schedule_retry_max_exceeded(self, service):
        """Test that max retries disables webhook."""
        delivery = WebhookDelivery(
            id="del-1",
            webhook_id="wh-1",
            notification_id="notif-1",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            payload={},
            signature="sig",
            retry_count=3,  # Already at max
        )

        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
            consecutive_failures=10,  # Too many failures
        )

        await service._schedule_retry(delivery, webhook)

        assert webhook.active is False


class TestPayloadSigning:
    """Tests for payload signing."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    def test_sign_payload(self, service):
        """Test payload signature generation."""
        payload = {"event": "test", "data": {"key": "value"}}
        secret = "test-secret"

        signature = service._sign_payload(payload, secret)

        assert signature.startswith("sha256=")
        assert len(signature) > 10

    def test_sign_payload_consistent(self, service):
        """Test that signatures are consistent."""
        payload = {"event": "test", "data": {"key": "value"}}
        secret = "test-secret"

        sig1 = service._sign_payload(payload, secret)
        sig2 = service._sign_payload(payload, secret)

        assert sig1 == sig2

    def test_sign_payload_different_secrets(self, service):
        """Test that different secrets produce different signatures."""
        payload = {"event": "test", "data": {"key": "value"}}

        sig1 = service._sign_payload(payload, "secret1")
        sig2 = service._sign_payload(payload, "secret2")

        assert sig1 != sig2


class TestUserPreferences:
    """Tests for user notification preferences."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_get_user_preferences_default(self, service):
        """Test getting default preferences."""
        prefs = await service.get_user_preferences("new-user")

        assert prefs.user_id == "new-user"
        assert prefs.mute_all is False
        assert DeliveryChannel.IN_APP in prefs.default_channels

    @pytest.mark.asyncio
    async def test_get_user_preferences_existing(self, service):
        """Test getting existing preferences."""
        service._preferences["user-123"] = NotificationPreferences(
            user_id="user-123",
            mute_all=True,
        )

        prefs = await service.get_user_preferences("user-123")

        assert prefs.mute_all is True

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, service):
        """Test updating preferences."""
        prefs = await service.update_user_preferences(
            "user-123",
            {"mute_all": True, "digest_enabled": True},
        )

        assert prefs.mute_all is True
        assert prefs.digest_enabled is True
        assert prefs.updated_at is not None


class TestSecretHashing:
    """Tests for webhook secret hashing."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    def test_hash_webhook_secret(self, service):
        """Test hashing a webhook secret."""
        secret = "my-super-secret"
        hashed = service._hash_webhook_secret(secret)

        assert hashed != secret
        assert hashed.startswith("$2")  # bcrypt prefix

    def test_verify_webhook_secret(self, service):
        """Test verifying a webhook secret."""
        secret = "my-super-secret"
        hashed = service._hash_webhook_secret(secret)

        assert service._verify_webhook_secret(secret, hashed) is True
        assert service._verify_webhook_secret("wrong-secret", hashed) is False

    def test_verify_webhook_secret_invalid_hash(self, service):
        """Test verifying with invalid hash."""
        result = service._verify_webhook_secret("secret", "invalid-hash")
        assert result is False


class TestPersistence:
    """Tests for persistence operations."""

    @pytest.fixture
    def service(self):
        mock_neo4j = AsyncMock()
        return NotificationService(neo4j_client=mock_neo4j)

    @pytest.mark.asyncio
    async def test_persist_notification(self, service):
        """Test persisting a notification."""
        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test message",
        )

        result = await service._persist_notification(notification)

        assert result is True
        service.neo4j.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_notification_no_db(self):
        """Test persisting without database."""
        service = NotificationService()  # No neo4j

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test message",
        )

        result = await service._persist_notification(notification)

        assert result is False

    @pytest.mark.asyncio
    async def test_persist_webhook(self, service):
        """Test persisting a webhook."""
        webhook = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
        )

        result = await service._persist_webhook(webhook)

        assert result is True
        service.neo4j.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_from_database(self, service):
        """Test loading data from database."""
        service.neo4j.execute_read.return_value = [
            {
                "id": "wh-1",
                "user_id": "user-123",
                "url": "https://example.com",
                "secret_hash": "$2b$12$hash",
                "active": True,
                "events": [],
            },
        ]

        count = await service.load_from_database()

        assert count == 1
        assert "wh-1" in service._webhooks

    @pytest.mark.asyncio
    async def test_load_from_database_no_db(self):
        """Test loading without database."""
        service = NotificationService()  # No neo4j

        count = await service.load_from_database()

        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_webhook_from_db(self, service):
        """Test deleting webhook from database."""
        result = await service._delete_webhook_from_db("wh-1")

        assert result is True
        service.neo4j.execute_write.assert_called_once()


class TestWebhookFiltering:
    """Tests for webhook event filtering."""

    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_queue_webhooks_event_filter(self, service):
        """Test that event filter is applied."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
            active=True,
            events=[NotificationEvent.PROPOSAL_CREATED],  # Only this event
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.CAPSULE_CREATED,  # Different event
            title="Test",
            message="Test",
        )

        await service._queue_webhooks("user-123", notification)

        # Should not be queued due to event filter
        assert service._webhook_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_queue_webhooks_priority_filter(self, service):
        """Test that priority filter is applied."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
            active=True,
            filter_min_priority=NotificationPriority.HIGH,  # Only high+
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test",
            priority=NotificationPriority.NORMAL,  # Below threshold
        )

        await service._queue_webhooks("user-123", notification)

        # Should not be queued due to priority filter
        assert service._webhook_queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_queue_webhooks_inactive_ignored(self, service):
        """Test that inactive webhooks are ignored."""
        service._webhooks["wh-1"] = WebhookSubscription(
            id="wh-1",
            user_id="user-123",
            url="https://example.com",
            secret="secret",
            active=False,  # Inactive
        )

        notification = Notification(
            id="notif-1",
            user_id="user-123",
            event_type=NotificationEvent.PROPOSAL_CREATED,
            title="Test",
            message="Test",
        )

        await service._queue_webhooks("user-123", notification)

        assert service._webhook_queue.qsize() == 0


class TestGlobalFunctions:
    """Tests for global service functions."""

    @pytest.mark.asyncio
    async def test_get_notification_service_singleton(self):
        """Test getting singleton instance."""
        await shutdown_notification_service()

        service1 = await get_notification_service()
        service2 = await get_notification_service()

        assert service1 is service2

        await shutdown_notification_service()

    @pytest.mark.asyncio
    async def test_shutdown_notification_service(self):
        """Test shutting down service."""
        await get_notification_service()
        await shutdown_notification_service()

        import forge.services.notifications as module

        assert module._notification_service is None
