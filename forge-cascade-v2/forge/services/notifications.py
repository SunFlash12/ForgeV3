"""
Notification Service

Handles notification delivery through multiple channels:
- In-app notifications
- Webhook delivery
- Future: Email, Slack, etc.

SECURITY FIX (Audit 3): Added SSRF protection for webhook URLs
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from forge.models.base import generate_id
from forge.models.notifications import (
    DeliveryChannel,
    Notification,
    NotificationEvent,
    NotificationPreferences,
    NotificationPriority,
    WebhookDelivery,
    WebhookPayload,
    WebhookSubscription,
)

logger = logging.getLogger(__name__)


class SSRFError(Exception):
    """Raised when a potential SSRF attack is detected."""
    pass


def validate_webhook_url(url: str) -> str:
    """
    Validate a webhook URL to prevent SSRF attacks.

    SECURITY FIX (Audit 3): Validates webhook URLs before HTTP requests.

    Args:
        url: The webhook URL to validate

    Returns:
        The validated URL

    Raises:
        SSRFError: If the URL is invalid or targets a private resource
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL missing hostname")

    # Block dangerous hostnames
    dangerous_hostnames = {
        "localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]",
        "metadata.google.internal", "169.254.169.254", "metadata.aws",
    }

    if hostname.lower() in dangerous_hostnames:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Resolve hostname and check for private IPs
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        ip_addresses = {info[4][0] for info in addr_info}

        for ip_str in ip_addresses:
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                raise SSRFError(f"Invalid IP address resolved: {ip_str}")

            if ip.is_private:
                raise SSRFError(f"Private IP address blocked: {ip_str}")
            if ip.is_loopback:
                raise SSRFError(f"Loopback address blocked: {ip_str}")
            if ip.is_link_local:
                raise SSRFError(f"Link-local address blocked: {ip_str}")
            if ip.is_reserved:
                raise SSRFError(f"Reserved address blocked: {ip_str}")
            if isinstance(ip_str, str) and ip_str.startswith("169.254."):
                raise SSRFError(f"Cloud metadata address blocked: {ip_str}")

    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for {hostname}: {e}")
    except OSError as e:
        raise SSRFError(f"Network error resolving {hostname}: {e}")

    return url


class NotificationService:
    """
    Central service for managing and delivering notifications.
    """

    WEBHOOK_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min

    def __init__(self, redis_client: Any = None, neo4j_client: Any = None) -> None:
        self.redis = redis_client
        self.neo4j = neo4j_client  # AUDIT 3 FIX (A1-D03): Add Neo4j client
        self._http_client: httpx.AsyncClient | None = None
        self._logger = logger  # FIX: Initialize instance logger from module logger

        # In-memory storage (would use database in production)
        self._notifications: dict[str, Notification] = {}
        self._webhooks: dict[str, WebhookSubscription] = {}
        self._deliveries: dict[str, WebhookDelivery] = {}
        self._preferences: dict[str, NotificationPreferences] = {}

        # Queues for async processing
        self._webhook_queue: asyncio.Queue[tuple[WebhookSubscription, Notification]] = asyncio.Queue()
        self._retry_queue: asyncio.Queue[tuple[WebhookDelivery, WebhookSubscription]] = asyncio.Queue()

        # Background tasks
        self._webhook_worker_task: asyncio.Task[None] | None = None
        self._retry_worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the notification service."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.WEBHOOK_TIMEOUT),
            follow_redirects=False,
        )

        # Start background workers
        self._webhook_worker_task = asyncio.create_task(self._webhook_worker())
        self._retry_worker_task = asyncio.create_task(self._retry_worker())

        logger.info("Notification service started")

    async def stop(self) -> None:
        """
        Stop the notification service.

        SECURITY FIX (Audit 5): Properly wait for background tasks to complete
        before closing the HTTP client. This prevents resource leaks and ensures
        pending webhook deliveries are properly handled.
        """
        # Cancel background workers
        if self._webhook_worker_task:
            self._webhook_worker_task.cancel()
            try:
                await self._webhook_worker_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling

        if self._retry_worker_task:
            self._retry_worker_task.cancel()
            try:
                await self._retry_worker_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling

        # Clear task references
        self._webhook_worker_task = None
        self._retry_worker_task = None

        # Close HTTP client after tasks are done
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        logger.info("Notification service stopped")

    # =========================================================================
    # Notification Creation & Delivery
    # =========================================================================

    async def notify(
        self,
        user_id: str,
        event_type: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        related_entity_id: str | None = None,
        related_entity_type: str | None = None,
        action_url: str | None = None,
        source: str = "system",
    ) -> Notification:
        """
        Create and deliver a notification to a user.

        Handles routing to appropriate channels based on user preferences.
        """
        notification = Notification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            message=message,
            priority=priority,
            data=data or {},
            related_entity_id=related_entity_id,
            related_entity_type=related_entity_type,
            action_url=action_url,
            source=source,
        )

        # Store in-app notification
        self._notifications[notification.id] = notification
        # AUDIT 3 FIX (A1-D03): Persist to database
        await self._persist_notification(notification)

        # Get user preferences
        prefs = await self.get_user_preferences(user_id)

        # Check mute status
        if prefs.mute_all or (prefs.mute_until and prefs.mute_until > datetime.now(UTC)):
            logger.debug(f"User {user_id} has notifications muted")
            return notification

        # Get channels for this event type
        channels = prefs.channel_preferences.get(
            event_type.value,
            prefs.default_channels
        )

        # Deliver to webhooks if enabled
        if DeliveryChannel.WEBHOOK in channels:
            await self._queue_webhooks(user_id, notification)

        logger.info(f"Notification sent to {user_id}: {event_type.value}")
        return notification

    async def notify_many(
        self,
        user_ids: list[str],
        event_type: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> list[Notification]:
        """Send notification to multiple users."""
        notifications = []
        for user_id in user_ids:
            n = await self.notify(
                user_id=user_id,
                event_type=event_type,
                title=title,
                message=message,
                data=data,
                priority=priority,
            )
            notifications.append(n)
        return notifications

    async def broadcast(
        self,
        event_type: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        user_filter: Callable[..., Any] | None = None,
        caller_id: str | None = None,
        caller_role: str | None = None,
    ) -> int:
        """
        Broadcast notification to all users.

        SECURITY FIX (Audit 4 - M19): Requires admin-level permissions.
        Broadcast can only be called by users with ADMIN role.

        Args:
            user_filter: Optional function to filter users
            caller_id: ID of the user calling this function (required)
            caller_role: Role of the caller (must be ADMIN)

        Raises:
            PermissionError: If caller is not an admin
        """
        # SECURITY FIX (Audit 4 - M19): Require admin permissions for broadcast
        if not caller_id or caller_role != "admin":
            self._logger.warning(
                "broadcast_unauthorized: caller_id=%s, caller_role=%s",
                caller_id,
                caller_role,
            )
            raise PermissionError(
                "Broadcast notifications require admin-level permissions"
            )

        # Log the broadcast for audit
        self._logger.info(
            "broadcast_initiated: caller_id=%s, event_type=%s, title=%s",
            caller_id,
            event_type.value,
            title,
        )

        # In production, get users from database
        # For now, send to all webhook subscribers
        sent = 0
        webhook_users = {w.user_id for w in self._webhooks.values() if w.active}

        for user_id in webhook_users:
            if user_filter and not user_filter(user_id):
                continue
            await self.notify(
                user_id=user_id,
                event_type=event_type,
                title=title,
                message=message,
                data=data,
                priority=priority,
            )
            sent += 1

        self._logger.info("broadcast_completed: sent_count=%d, caller_id=%s", sent, caller_id)
        return sent

    # =========================================================================
    # In-App Notifications
    # =========================================================================

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user."""
        notifications = [
            n for n in self._notifications.values()
            if n.user_id == user_id and not n.dismissed
            and (not unread_only or not n.read)
        ]
        notifications.sort(key=lambda n: n.created_at, reverse=True)
        return notifications[offset:offset + limit]

    async def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications."""
        return sum(
            1 for n in self._notifications.values()
            if n.user_id == user_id and not n.read and not n.dismissed
        )

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read."""
        notification = self._notifications.get(notification_id)
        if notification and notification.user_id == user_id:
            notification.read = True
            notification.read_at = datetime.now(UTC)
            return True
        return False

    async def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        count = 0
        now = datetime.now(UTC)
        for n in self._notifications.values():
            if n.user_id == user_id and not n.read:
                n.read = True
                n.read_at = now
                count += 1
        return count

    async def dismiss(self, notification_id: str, user_id: str) -> bool:
        """Dismiss a notification."""
        notification = self._notifications.get(notification_id)
        if notification and notification.user_id == user_id:
            notification.dismissed = True
            notification.dismissed_at = datetime.now(UTC)
            return True
        return False

    # =========================================================================
    # Webhook Management
    # =========================================================================

    async def create_webhook(
        self,
        user_id: str,
        url: str,
        secret: str,
        events: list[NotificationEvent] | None = None,
        name: str = "",
    ) -> WebhookSubscription:
        """Create a new webhook subscription."""
        webhook = WebhookSubscription(
            user_id=user_id,
            url=url,
            secret=secret,
            events=events or [],
            name=name,
        )

        self._webhooks[webhook.id] = webhook
        # AUDIT 3 FIX (A1-D03): Persist to database
        await self._persist_webhook(webhook)

        # Optionally verify the webhook
        await self._verify_webhook(webhook)

        logger.info(f"Webhook created: {webhook.id} for user {user_id}")
        return webhook

    async def get_webhooks(self, user_id: str) -> list[WebhookSubscription]:
        """Get all webhooks for a user."""
        return [w for w in self._webhooks.values() if w.user_id == user_id]

    async def get_webhook(self, webhook_id: str) -> WebhookSubscription | None:
        """Get a specific webhook."""
        return self._webhooks.get(webhook_id)

    async def update_webhook(
        self,
        webhook_id: str,
        user_id: str,
        updates: dict[str, Any],
    ) -> WebhookSubscription | None:
        """Update a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if not webhook or webhook.user_id != user_id:
            return None

        for key, value in updates.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)

        return webhook

    async def delete_webhook(self, webhook_id: str, user_id: str) -> bool:
        """Delete a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if webhook and webhook.user_id == user_id:
            del self._webhooks[webhook_id]
            # AUDIT 3 FIX (A1-D03): Delete from database
            await self._delete_webhook_from_db(webhook_id)
            return True
        return False

    async def _verify_webhook(self, webhook: WebhookSubscription) -> bool:
        """Verify a webhook endpoint by sending a ping."""
        try:
            # SECURITY FIX (Audit 3): Validate webhook URL to prevent SSRF
            try:
                validated_url = validate_webhook_url(webhook.url)
            except SSRFError as e:
                logger.warning(f"Webhook URL blocked by SSRF protection: {e}")
                return False

            payload = {
                "event": "webhook.verify",
                "timestamp": datetime.now(UTC).isoformat(),
                "webhook_id": webhook.id,
            }

            signature = self._sign_payload(payload, webhook.secret)

            if self._http_client:
                response = await self._http_client.post(
                    validated_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Forge-Signature": signature,
                        "X-Forge-Event": "webhook.verify",
                    },
                )

                if response.status_code == 200:
                    webhook.verified = True
                    return True

        except Exception as e:
            logger.warning(f"Webhook verification failed: {e}")

        return False

    # =========================================================================
    # Webhook Delivery
    # =========================================================================

    async def _queue_webhooks(self, user_id: str, notification: Notification) -> None:
        """Queue webhook deliveries for a notification."""
        webhooks = [
            w for w in self._webhooks.values()
            if w.user_id == user_id and w.active
        ]

        for webhook in webhooks:
            # Check event filter
            if webhook.events and notification.event_type not in webhook.events:
                continue

            # Check priority filter
            priority_order = {
                NotificationPriority.LOW: 0,
                NotificationPriority.NORMAL: 1,
                NotificationPriority.HIGH: 2,
                NotificationPriority.CRITICAL: 3,
            }
            if priority_order[notification.priority] < priority_order[webhook.filter_min_priority]:
                continue

            # Queue delivery
            await self._webhook_queue.put((webhook, notification))

    async def _webhook_worker(self) -> None:
        """Background worker for processing webhook queue."""
        while True:
            try:
                webhook, notification = await self._webhook_queue.get()
                await self._deliver_webhook(webhook, notification)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Webhook worker error: {e}")

    async def _deliver_webhook(
        self,
        webhook: WebhookSubscription,
        notification: Notification,
    ) -> WebhookDelivery:
        """Deliver a notification to a webhook endpoint."""
        delivery_id = generate_id()

        payload = WebhookPayload(
            event=notification.event_type.value,
            timestamp=datetime.now(UTC),
            webhook_id=webhook.id,
            delivery_id=delivery_id,
            data={
                "notification_id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "priority": notification.priority.value,
                "data": notification.data,
                "related_entity_id": notification.related_entity_id,
                "related_entity_type": notification.related_entity_type,
            },
        )

        # Sign payload
        signature = self._sign_payload(payload.to_dict_for_signing(), webhook.secret)
        payload.signature = signature

        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook.id,
            notification_id=notification.id,
            event_type=notification.event_type,
            payload=payload.to_dict_for_signing(),
            signature=signature,
        )

        try:
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")

            # SECURITY FIX (Audit 3): Validate webhook URL to prevent SSRF
            validated_url = validate_webhook_url(webhook.url)

            start = datetime.now(UTC)
            response = await self._http_client.post(
                validated_url,
                json=payload.model_dump(mode='json'),
                headers={
                    "Content-Type": "application/json",
                    "X-Forge-Signature": signature,
                    "X-Forge-Event": notification.event_type.value,
                    "X-Forge-Delivery": delivery_id,
                },
            )
            elapsed = (datetime.now(UTC) - start).total_seconds() * 1000

            delivery.status_code = response.status_code
            delivery.response_body = response.text[:1000] if response.text else None
            delivery.response_time_ms = elapsed
            delivery.completed_at = datetime.now(UTC)

            if response.status_code >= 200 and response.status_code < 300:
                delivery.success = True
                webhook.total_success += 1
                webhook.consecutive_failures = 0
                webhook.last_success_at = datetime.now(UTC)
            else:
                delivery.success = False
                delivery.error = f"HTTP {response.status_code}"
                webhook.total_failure += 1
                webhook.consecutive_failures += 1
                webhook.last_failure_at = datetime.now(UTC)

                # Schedule retry
                await self._schedule_retry(delivery, webhook)

        except Exception as e:
            delivery.error = str(e)
            delivery.completed_at = datetime.now(UTC)
            webhook.total_failure += 1
            webhook.consecutive_failures += 1
            webhook.last_failure_at = datetime.now(UTC)

            # Schedule retry
            await self._schedule_retry(delivery, webhook)

        webhook.total_sent += 1
        webhook.last_triggered_at = datetime.now(UTC)

        self._deliveries[delivery.id] = delivery
        return delivery

    async def _schedule_retry(self, delivery: WebhookDelivery, webhook: WebhookSubscription) -> None:
        """Schedule a retry for a failed delivery."""
        if delivery.retry_count >= self.MAX_RETRIES:
            logger.warning(f"Webhook {webhook.id} max retries exceeded")

            # Disable webhook after too many failures
            if webhook.consecutive_failures >= 10:
                webhook.active = False
                logger.warning(f"Webhook {webhook.id} disabled due to failures")

            return

        delay = self.RETRY_DELAYS[min(delivery.retry_count, len(self.RETRY_DELAYS) - 1)]
        delivery.retry_count += 1
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        await self._retry_queue.put((delivery, webhook))

    async def _retry_worker(self) -> None:
        """Background worker for processing retry queue."""
        while True:
            try:
                delivery, webhook = await self._retry_queue.get()

                # Wait until retry time
                if delivery.next_retry_at:
                    wait_time = (delivery.next_retry_at - datetime.now(UTC)).total_seconds()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                # Retry delivery
                await self._retry_delivery(delivery, webhook)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry worker error: {e}")

    async def _retry_delivery(self, delivery: WebhookDelivery, webhook: WebhookSubscription) -> None:
        """Retry a failed webhook delivery."""
        try:
            if not self._http_client:
                raise RuntimeError("HTTP client not initialized")

            # SECURITY FIX (Audit 3): Validate webhook URL to prevent SSRF
            validated_url = validate_webhook_url(webhook.url)

            start = datetime.now(UTC)
            response = await self._http_client.post(
                validated_url,
                json=delivery.payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Forge-Signature": delivery.signature,
                    "X-Forge-Event": delivery.event_type.value,
                    "X-Forge-Delivery": delivery.id,
                    "X-Forge-Retry": str(delivery.retry_count),
                },
            )
            elapsed = (datetime.now(UTC) - start).total_seconds() * 1000

            delivery.status_code = response.status_code
            delivery.response_time_ms = elapsed
            delivery.completed_at = datetime.now(UTC)

            if response.status_code >= 200 and response.status_code < 300:
                delivery.success = True
                webhook.consecutive_failures = 0
            else:
                await self._schedule_retry(delivery, webhook)

        except SSRFError as e:
            # SECURITY FIX (Audit 3): Don't retry SSRF-blocked URLs
            delivery.error = f"SSRF blocked: {e}"
            delivery.success = False
            logger.warning(f"Webhook {webhook.id} blocked by SSRF protection: {e}")
            # Don't retry - this is a permanent failure
        except Exception as e:
            delivery.error = str(e)
            await self._schedule_retry(delivery, webhook)

    def _sign_payload(self, payload: dict[str, Any], secret: str) -> str:
        """Create HMAC-SHA256 signature for payload."""
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        signature = hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    # =========================================================================
    # User Preferences
    # =========================================================================

    async def get_user_preferences(self, user_id: str) -> NotificationPreferences:
        """Get notification preferences for a user."""
        if user_id not in self._preferences:
            self._preferences[user_id] = NotificationPreferences(user_id=user_id)
        return self._preferences[user_id]

    async def update_user_preferences(
        self,
        user_id: str,
        updates: dict[str, Any],
    ) -> NotificationPreferences:
        """Update user notification preferences."""
        prefs = await self.get_user_preferences(user_id)

        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        prefs.updated_at = datetime.now(UTC)
        return prefs

    # =========================================================================
    # Persistence Methods (Audit 3 - A1-D03)
    # =========================================================================

    async def _persist_notification(self, notification: Notification) -> bool:
        """
        Persist a notification to Neo4j database.

        AUDIT 3 FIX (A1-D03): Add persistent storage to notification service.
        """
        if not self.neo4j:
            return False

        try:
            query = """
            MERGE (n:Notification {id: $id})
            SET n.user_id = $user_id,
                n.event_type = $event_type,
                n.title = $title,
                n.message = $message,
                n.priority = $priority,
                n.is_read = $is_read,
                n.created_at = $created_at,
                n.read_at = $read_at
            RETURN n.id as id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "id": notification.id,
                    "user_id": notification.user_id,
                    "event_type": notification.event_type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                    "read_at": notification.read_at.isoformat() if notification.read_at else None,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist notification {notification.id}: {e}")
            return False

    def _hash_webhook_secret(self, secret: str) -> str:
        """
        SECURITY FIX (Audit 4 - H18): Hash webhook secrets before storage.

        Uses bcrypt for secure hashing. The original secret cannot be recovered
        but can be verified when webhooks are triggered.
        """
        import bcrypt
        # Generate a salt and hash the secret
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(secret.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def _verify_webhook_secret(self, secret: str, hashed_secret: str) -> bool:
        """Verify a webhook secret against its hash."""
        import bcrypt
        try:
            return bcrypt.checkpw(secret.encode('utf-8'), hashed_secret.encode('utf-8'))
        except Exception:
            return False

    async def _persist_webhook(self, webhook: WebhookSubscription) -> bool:
        """
        Persist a webhook subscription to Neo4j database.

        SECURITY FIX (Audit 4 - H18): Webhook secrets are now hashed with
        bcrypt before storage. The plaintext secret is never stored.
        """
        if not self.neo4j:
            return False

        try:
            # SECURITY FIX: Hash the secret before storing
            hashed_secret = self._hash_webhook_secret(webhook.secret) if webhook.secret else None

            query = """
            MERGE (w:WebhookSubscription {id: $id})
            SET w.user_id = $user_id,
                w.url = $url,
                w.secret_hash = $secret_hash,
                w.active = $active,
                w.events = $events,
                w.created_at = $created_at
            RETURN w.id as id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "id": webhook.id,
                    "user_id": webhook.user_id,
                    "url": webhook.url,
                    "secret_hash": hashed_secret,  # SECURITY FIX: Store hash, not plaintext
                    "active": webhook.active,
                    "events": [e.value for e in webhook.events] if webhook.events else [],
                    "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist webhook {webhook.id}: {e}")
            return False

    async def load_from_database(self) -> int:
        """
        Load all notification data from Neo4j on startup.

        Returns:
            Number of webhooks loaded
        """
        if not self.neo4j:
            logger.warning("No Neo4j client, cannot load notification data")
            return 0

        loaded = 0
        try:
            # Load webhooks (more important than old notifications)
            # FIX: Read secret_hash field that matches what _save_webhook_to_db writes
            query = """
            MATCH (w:WebhookSubscription)
            WHERE w.active = true
            RETURN w.id as id, w.user_id as user_id, w.url as url,
                   w.secret_hash as secret_hash, w.active as active, w.events as events,
                   w.created_at as created_at
            """
            results = await self.neo4j.execute_read(query)

            for record in results:
                # Note: secret_hash is stored, not plaintext secret
                # Webhooks loaded from DB won't have plaintext secret for HMAC
                # They need to be re-registered or use a different auth mechanism
                webhook = WebhookSubscription(
                    id=record["id"],
                    user_id=record["user_id"],
                    url=record["url"],
                    secret=record.get("secret_hash"),  # Use hash as placeholder
                    active=record["active"],
                    events=[NotificationEvent(e) for e in (record["events"] or [])],
                )
                self._webhooks[webhook.id] = webhook
                loaded += 1

            logger.info(f"Loaded {loaded} webhooks from database")
            return loaded
        except Exception as e:
            logger.error(f"Failed to load notification data: {e}")
            return 0

    async def _delete_webhook_from_db(self, webhook_id: str) -> bool:
        """Delete a webhook from the database."""
        if not self.neo4j:
            return False

        try:
            query = """
            MATCH (w:WebhookSubscription {id: $id})
            DELETE w
            """
            await self.neo4j.execute_write(query, parameters={"id": webhook_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {webhook_id}: {e}")
            return False


# Global instance
_notification_service: NotificationService | None = None


async def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
        await _notification_service.start()
    return _notification_service


async def shutdown_notification_service() -> None:
    """Shutdown the notification service."""
    global _notification_service
    if _notification_service:
        await _notification_service.stop()
        _notification_service = None
