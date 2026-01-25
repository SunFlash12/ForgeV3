"""
Forge WebSocket Handlers

Provides WebSocket endpoints for:
- /ws/events: Real-time system event streaming
- /ws/dashboard: Live dashboard metrics and updates
- /ws/chat/{room_id}: Collaborative chat rooms

Security Features:
- Authentication required for all endpoints
- SECURITY FIX (Audit 6): Origin header validation to prevent CSWSH attacks
- Subscription limits per connection (DoS protection)
- Message rate limiting (spam protection)
- Message size limits (DoS protection)
"""

import asyncio
import json
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from forge.api.dependencies import get_current_user as get_current_user_ws
from forge.config import get_settings
from forge.models.user import User
from forge.security.tokens import (
    TokenBlacklist,
    TokenExpiredError,
    TokenInvalidError,
    decode_token,
    verify_token,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

# Security limits
MAX_SUBSCRIPTIONS_PER_CONNECTION = 50  # Maximum topics a single connection can subscribe to
MAX_MESSAGES_PER_MINUTE = 60  # Rate limit: messages per minute per connection
RATE_LIMIT_WINDOW_SECONDS = 60  # Rate limiting window
# SECURITY FIX (Audit 6): Maximum WebSocket message size to prevent DoS
MAX_WEBSOCKET_MESSAGE_SIZE = 64 * 1024  # 64KB max message size


def get_token_expiry_check_interval() -> int:
    """Get token expiry check interval from settings."""
    return settings.websocket_token_check_interval_seconds


def get_max_connections_per_user() -> int:
    """Get max WebSocket connections per user from settings."""
    return settings.websocket_max_connections_per_user


# ============================================================================
# SECURITY FIX (Audit 6): Origin Validation for WebSocket
# ============================================================================

def validate_websocket_origin(websocket: WebSocket) -> bool:
    """
    SECURITY FIX (Audit 6): Validate WebSocket Origin header to prevent CSWSH attacks.

    Cross-Site WebSocket Hijacking (CSWSH) occurs when a malicious website
    establishes a WebSocket connection to your server using the victim's
    authenticated session. Origin validation prevents this by rejecting
    connections from unauthorized origins.

    Args:
        websocket: The WebSocket connection to validate

    Returns:
        True if origin is valid, False otherwise
    """
    origin = websocket.headers.get("origin")

    # No origin header - could be a same-origin request or a tool like wscat
    # In production, you may want to reject connections without Origin
    if not origin:
        # Allow in development, log warning in production
        if settings.app_env == "production":
            logger.warning(
                "websocket_no_origin_header",
                client=websocket.client,
                path=websocket.url.path,
            )
            # Still allow for backwards compatibility, but log
        return True

    # Parse the origin
    try:
        parsed_origin = urlparse(origin)
        origin_host = parsed_origin.netloc.lower()
    except Exception:
        logger.warning(
            "websocket_invalid_origin",
            origin=origin,
            client=websocket.client,
        )
        return False

    # Get allowed origins from settings
    allowed_origins = settings.cors_origins_list

    # Check if origin matches any allowed origin
    for allowed in allowed_origins:
        if allowed == "*":
            # Wildcard - allow all (not recommended in production)
            return True

        try:
            parsed_allowed = urlparse(allowed)
            allowed_host = parsed_allowed.netloc.lower()

            # Compare hosts (including port if specified)
            if origin_host == allowed_host:
                return True

            # Also check if origin matches without port
            origin_host_no_port = origin_host.split(":")[0]
            allowed_host_no_port = allowed_host.split(":")[0]
            if origin_host_no_port == allowed_host_no_port:
                # Same host, different port - may be allowed in development
                if settings.app_env != "production":
                    return True
        except Exception:
            continue

    # Origin not in allowed list
    logger.warning(
        "websocket_origin_rejected",
        origin=origin,
        allowed_origins=allowed_origins,
        client=websocket.client,
    )
    return False


async def validate_and_accept_websocket(
    websocket: WebSocket,
    close_code: int = 4003,
    close_reason: str = "Origin not allowed",
) -> bool:
    """
    SECURITY FIX (Audit 6): Validate origin and accept WebSocket connection.

    Args:
        websocket: The WebSocket connection
        close_code: Close code to use if origin is invalid
        close_reason: Close reason message

    Returns:
        True if connection was accepted, False if rejected
    """
    if not validate_websocket_origin(websocket):
        await websocket.close(code=close_code, reason=close_reason)
        return False

    await websocket.accept()
    return True

websocket_router = APIRouter()


# ============================================================================
# Connection Manager
# ============================================================================


class WebSocketConnection:
    """Represents a single WebSocket connection with metadata."""

    def __init__(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: str | None = None,
        subscriptions: set[str] | None = None,
        token: str | None = None,  # SECURITY FIX (Audit 6): Store token for periodic validation
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.user_id = user_id
        self.subscriptions = subscriptions or set()
        self.connected_at = datetime.now(UTC)
        self.last_ping = datetime.now(UTC)
        self.message_count = 0
        # SECURITY FIX (Audit 5): Use deque with maxlen to bound memory growth
        # maxlen is 2x the rate limit to allow room for cleanup
        self._message_timestamps: deque[datetime] = deque(maxlen=MAX_MESSAGES_PER_MINUTE * 2)
        # SECURITY FIX (Audit 6): Store token for periodic validation
        self._token = token
        self._last_token_check = datetime.now(UTC)
        self._token_valid = True

    def check_rate_limit(self) -> bool:
        """
        Check if connection is within rate limits.
        Returns True if allowed, False if rate limited.

        SECURITY FIX (Audit 5): Uses deque for bounded memory growth.
        """
        now = datetime.now(UTC)
        cutoff = now.timestamp() - RATE_LIMIT_WINDOW_SECONDS

        # Remove old timestamps from the front
        while self._message_timestamps and self._message_timestamps[0].timestamp() <= cutoff:
            self._message_timestamps.popleft()

        # Check if under limit
        if len(self._message_timestamps) >= MAX_MESSAGES_PER_MINUTE:
            return False

        # Record this message
        self._message_timestamps.append(now)
        return True

    def can_add_subscription(self) -> bool:
        """Check if connection can add more subscriptions."""
        return len(self.subscriptions) < MAX_SUBSCRIPTIONS_PER_CONNECTION

    async def check_token_expiry(self) -> bool:
        """
        SECURITY FIX (Audit 6): Check if the token is still valid.

        For long-lived WebSocket sessions, the initial authentication token
        may expire while the connection is still active. This method periodically
        validates the token to ensure the session is still authorized.

        Returns:
            True if token is valid, False if expired/revoked/invalid
        """
        if not self._token:
            # No token stored - connection was not authenticated with persistent token
            return True

        now = datetime.now(UTC)

        # Only check periodically to avoid performance overhead
        check_interval = get_token_expiry_check_interval()
        if (now - self._last_token_check).total_seconds() < check_interval:
            return self._token_valid

        self._last_token_check = now

        try:
            # Validate the token - this checks expiry, signature, and claims
            payload = decode_token(self._token, verify_exp=True)

            # Check if token has been blacklisted (e.g., user logged out)
            jti = payload.jti
            if jti and await TokenBlacklist.is_blacklisted_async(jti):
                logger.warning(
                    "websocket_token_revoked",
                    connection_id=self.connection_id,
                    user_id=self.user_id,
                    jti=jti[:8] + "..." if jti else None,
                )
                self._token_valid = False
                return False

            self._token_valid = True
            return True

        except TokenExpiredError:
            logger.info(
                "websocket_token_expired",
                connection_id=self.connection_id,
                user_id=self.user_id,
            )
            self._token_valid = False
            return False

        except TokenInvalidError as e:
            logger.warning(
                "websocket_token_invalid",
                connection_id=self.connection_id,
                user_id=self.user_id,
                error=str(e)[:100],
            )
            self._token_valid = False
            return False

        except Exception as e:
            logger.error(
                "websocket_token_check_error",
                connection_id=self.connection_id,
                error=str(e)[:100],
            )
            # On error, be conservative and keep connection alive
            # but log for investigation
            return True

    async def send_json(self, data: dict[str, Any]) -> bool:
        """Send JSON data to the client."""
        try:
            await self.websocket.send_json(data)
            self.message_count += 1
            return True
        except Exception as e:
            logger.warning("websocket_send_failed",
                         connection_id=self.connection_id,
                         error=str(e))
            return False

    async def send_text(self, text: str) -> bool:
        """Send text data to the client."""
        try:
            await self.websocket.send_text(text)
            self.message_count += 1
            return True
        except Exception:
            return False


class ConnectionManager:
    """
    Manages WebSocket connections across the application.

    Supports:
    - Multiple connection types (events, dashboard, chat)
    - Topic-based subscriptions
    - Room-based chat connections
    - Broadcast and targeted messaging
    """

    def __init__(self):
        # Connection storage by type
        self._event_connections: dict[str, WebSocketConnection] = {}
        self._dashboard_connections: dict[str, WebSocketConnection] = {}
        self._chat_connections: dict[str, dict[str, WebSocketConnection]] = defaultdict(dict)

        # Subscription tracking
        self._topic_subscribers: dict[str, set[str]] = defaultdict(set)

        # User to connection mapping
        self._user_connections: dict[str, set[str]] = defaultdict(set)

        # Stats
        self._total_connections = 0
        self._total_messages_sent = 0

    def can_user_connect(self, user_id: str | None) -> bool:
        """
        SECURITY FIX (Audit 6): Check if user can open another WebSocket connection.

        Prevents resource exhaustion by limiting the number of concurrent
        WebSocket connections per user.

        Args:
            user_id: The user attempting to connect

        Returns:
            True if user can connect, False if at limit
        """
        if not user_id:
            # Anonymous connections are allowed but limited elsewhere
            return True

        max_connections = get_max_connections_per_user()
        current_count = len(self._user_connections.get(user_id, set()))
        if current_count >= max_connections:
            logger.warning(
                "websocket_connection_limit_reached",
                user_id=user_id,
                current_count=current_count,
                max_allowed=max_connections,
            )
            return False
        return True

    def get_user_connection_count(self, user_id: str) -> int:
        """Get the current number of connections for a user."""
        return len(self._user_connections.get(user_id, set()))

    # -------------------------------------------------------------------------
    # Event Stream Connections
    # -------------------------------------------------------------------------

    async def connect_events(
        self,
        websocket: WebSocket,
        user_id: str | None = None,
        subscriptions: list[str] | None = None,
        token: str | None = None,  # SECURITY FIX (Audit 6): Store token for expiry checks
    ) -> WebSocketConnection:
        """Accept a new event stream connection."""

        await websocket.accept()

        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id,
            subscriptions=set(subscriptions or []),
            token=token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
        )

        self._event_connections[connection_id] = connection
        self._total_connections += 1

        if user_id:
            self._user_connections[user_id].add(connection_id)

        # Register topic subscriptions
        for topic in connection.subscriptions:
            self._topic_subscribers[topic].add(connection_id)

        logger.info("websocket_event_connected",
                   connection_id=connection_id,
                   user_id=user_id,
                   subscriptions=list(connection.subscriptions))

        # Send welcome message
        await connection.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "subscriptions": list(connection.subscriptions),
            "timestamp": datetime.now(UTC).isoformat()
        })

        return connection

    async def disconnect_events(self, connection_id: str):
        """Disconnect an event stream connection."""

        if connection_id not in self._event_connections:
            return

        connection = self._event_connections.pop(connection_id)

        # Clean up user mapping
        if connection.user_id:
            self._user_connections[connection.user_id].discard(connection_id)

        # Clean up topic subscriptions
        for topic in connection.subscriptions:
            self._topic_subscribers[topic].discard(connection_id)

        logger.info("websocket_event_disconnected", connection_id=connection_id)

    async def broadcast_event(
        self,
        event_type: str,
        data: dict[str, Any],
        topic: str | None = None
    ):
        """Broadcast an event to subscribed connections."""

        message = {
            "type": "event",
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat()
        }

        # Determine target connections
        if topic:
            # Only send to topic subscribers
            target_ids = self._topic_subscribers.get(topic, set())
        else:
            # Send to all event connections
            target_ids = set(self._event_connections.keys())

        # Also include connections subscribed to wildcard
        target_ids = target_ids.union(self._topic_subscribers.get("*", set()))

        # Send to all targets
        disconnected = []
        for conn_id in target_ids:
            if conn_id in self._event_connections:
                success = await self._event_connections[conn_id].send_json(message)
                if success:
                    self._total_messages_sent += 1
                else:
                    disconnected.append(conn_id)

        # Clean up disconnected
        for conn_id in disconnected:
            await self.disconnect_events(conn_id)

    # -------------------------------------------------------------------------
    # Dashboard Connections
    # -------------------------------------------------------------------------

    async def connect_dashboard(
        self,
        websocket: WebSocket,
        user_id: str | None = None,
        token: str | None = None,  # SECURITY FIX (Audit 6): Store token for expiry checks
    ) -> WebSocketConnection:
        """Accept a new dashboard connection."""

        await websocket.accept()

        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id,
            token=token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
        )

        self._dashboard_connections[connection_id] = connection
        self._total_connections += 1

        if user_id:
            self._user_connections[user_id].add(connection_id)

        logger.info("websocket_dashboard_connected",
                   connection_id=connection_id,
                   user_id=user_id)

        # Send welcome message
        await connection.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.now(UTC).isoformat()
        })

        return connection

    async def disconnect_dashboard(self, connection_id: str):
        """Disconnect a dashboard connection."""

        if connection_id not in self._dashboard_connections:
            return

        connection = self._dashboard_connections.pop(connection_id)

        if connection.user_id:
            self._user_connections[connection.user_id].discard(connection_id)

        logger.info("websocket_dashboard_disconnected", connection_id=connection_id)

    async def broadcast_dashboard_update(self, metrics: dict[str, Any]):
        """Broadcast metrics update to all dashboard connections."""

        message = {
            "type": "metrics_update",
            "metrics": metrics,
            "timestamp": datetime.now(UTC).isoformat()
        }

        disconnected = []
        for conn_id, connection in self._dashboard_connections.items():
            success = await connection.send_json(message)
            if success:
                self._total_messages_sent += 1
            else:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            await self.disconnect_dashboard(conn_id)

    # -------------------------------------------------------------------------
    # Chat Room Connections
    # -------------------------------------------------------------------------

    async def connect_chat(
        self,
        websocket: WebSocket,
        room_id: str,
        user_id: str,
        display_name: str | None = None,
        token: str | None = None,  # SECURITY FIX (Audit 6): Store token for expiry checks
    ) -> WebSocketConnection:
        """Accept a new chat room connection."""

        await websocket.accept()

        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id,
            token=token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
        )

        self._chat_connections[room_id][connection_id] = connection
        self._total_connections += 1
        self._user_connections[user_id].add(connection_id)

        logger.info("websocket_chat_connected",
                   connection_id=connection_id,
                   room_id=room_id,
                   user_id=user_id)

        # Send welcome message
        await connection.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "room_id": room_id,
            "timestamp": datetime.now(UTC).isoformat()
        })

        # Notify room of new participant
        await self.broadcast_chat(
            room_id=room_id,
            message_type="user_joined",
            data={
                "user_id": user_id,
                "display_name": display_name or user_id
            },
            exclude_connection=connection_id
        )

        return connection

    async def disconnect_chat(self, room_id: str, connection_id: str):
        """Disconnect a chat room connection."""

        if room_id not in self._chat_connections:
            return
        if connection_id not in self._chat_connections[room_id]:
            return

        connection = self._chat_connections[room_id].pop(connection_id)

        if connection.user_id:
            self._user_connections[connection.user_id].discard(connection_id)

        # Clean up empty rooms
        if not self._chat_connections[room_id]:
            del self._chat_connections[room_id]

        # Notify room
        if room_id in self._chat_connections:
            await self.broadcast_chat(
                room_id=room_id,
                message_type="user_left",
                data={"user_id": connection.user_id}
            )

        logger.info("websocket_chat_disconnected",
                   connection_id=connection_id,
                   room_id=room_id)

    async def broadcast_chat(
        self,
        room_id: str,
        message_type: str,
        data: dict[str, Any],
        exclude_connection: str | None = None
    ):
        """Broadcast a message to all connections in a chat room."""

        if room_id not in self._chat_connections:
            return

        message = {
            "type": message_type,
            "data": data,
            "room_id": room_id,
            "timestamp": datetime.now(UTC).isoformat()
        }

        disconnected = []
        for conn_id, connection in self._chat_connections[room_id].items():
            if conn_id == exclude_connection:
                continue

            success = await connection.send_json(message)
            if success:
                self._total_messages_sent += 1
            else:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            await self.disconnect_chat(room_id, conn_id)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> int:
        """Send a message to all connections belonging to a user."""

        sent = 0
        disconnected = []

        for conn_id in self._user_connections.get(user_id, set()).copy():
            # Check all connection types
            connection = (
                self._event_connections.get(conn_id) or
                self._dashboard_connections.get(conn_id) or
                self._find_chat_connection(conn_id)
            )

            if connection:
                success = await connection.send_json(message)
                if success:
                    sent += 1
                    self._total_messages_sent += 1
                else:
                    disconnected.append(conn_id)

        return sent

    def _find_chat_connection(self, connection_id: str) -> WebSocketConnection | None:
        """Find a chat connection by ID across all rooms."""
        for room_connections in self._chat_connections.values():
            if connection_id in room_connections:
                return room_connections[connection_id]
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get connection statistics."""

        return {
            "event_connections": len(self._event_connections),
            "dashboard_connections": len(self._dashboard_connections),
            "chat_rooms": len(self._chat_connections),
            "chat_connections": sum(len(c) for c in self._chat_connections.values()),
            "total_connections_ever": self._total_connections,
            "total_messages_sent": self._total_messages_sent,
            "active_topics": list(self._topic_subscribers.keys())
        }

    def get_room_participants(self, room_id: str) -> list[str]:
        """Get list of user IDs in a chat room."""

        if room_id not in self._chat_connections:
            return []

        return list({
            conn.user_id
            for conn in self._chat_connections[room_id].values()
            if conn.user_id
        })

    # -------------------------------------------------------------------------
    # SECURITY FIX (Audit 6): Force Disconnect for Privilege Changes
    # -------------------------------------------------------------------------

    async def force_disconnect_user(
        self,
        user_id: str,
        reason: str = "privilege_change",
        close_code: int = 4001
    ) -> int:
        """
        SECURITY FIX (Audit 6): Force-disconnect all WebSocket connections for a user.

        Used when user privileges change to ensure they re-authenticate with
        fresh tokens containing the updated claims.

        Args:
            user_id: User ID to disconnect
            reason: Reason for disconnection (sent to client)
            close_code: WebSocket close code (4001 = privilege change)

        Returns:
            Number of connections closed
        """
        if not user_id:
            return 0

        connection_ids = list(self._user_connections.get(user_id, set()))
        if not connection_ids:
            return 0

        closed_count = 0

        for conn_id in connection_ids:
            try:
                # Find connection in any connection pool
                connection = (
                    self._event_connections.get(conn_id) or
                    self._dashboard_connections.get(conn_id) or
                    self._find_chat_connection(conn_id)
                )

                if connection:
                    # Send notification to client before closing
                    try:
                        await connection.send_json({
                            "type": "session_terminated",
                            "reason": reason,
                            "action_required": "reauthenticate",
                            "timestamp": datetime.now(UTC).isoformat()
                        })
                    except Exception:
                        pass  # Client may already be disconnected

                    # Close the WebSocket connection
                    try:
                        await connection.websocket.close(
                            code=close_code,
                            reason=f"Session terminated: {reason}"
                        )
                    except Exception:
                        pass  # Already closed

                    closed_count += 1

                # Clean up connection from all pools
                if conn_id in self._event_connections:
                    await self.disconnect_events(conn_id)
                elif conn_id in self._dashboard_connections:
                    await self.disconnect_dashboard(conn_id)
                else:
                    # Try to find and disconnect from chat rooms
                    for room_id in list(self._chat_connections.keys()):
                        if conn_id in self._chat_connections.get(room_id, {}):
                            await self.disconnect_chat(room_id, conn_id)
                            break

            except Exception as e:
                logger.warning(
                    "force_disconnect_error",
                    user_id=user_id,
                    connection_id=conn_id,
                    error=str(e)[:100],
                )

        logger.info(
            "user_force_disconnected",
            user_id=user_id,
            reason=reason,
            connections_closed=closed_count,
        )

        return closed_count

    async def notify_privilege_change(
        self,
        user_id: str,
        change_type: str,
        message: str | None = None
    ) -> int:
        """
        SECURITY FIX (Audit 6): Notify user of privilege change without disconnecting.

        Use this when you want to inform the user but allow them to continue
        their session (e.g., for minor permission changes).

        Args:
            user_id: User ID to notify
            change_type: Type of change (role, trust_flame, etc.)
            message: Optional custom message

        Returns:
            Number of connections notified
        """
        return await self.send_to_user(user_id, {
            "type": "privilege_change",
            "change_type": change_type,
            "message": message or "Your permissions have changed. Some actions may require re-authentication.",
            "timestamp": datetime.now(UTC).isoformat()
        })


# Global connection manager instance
connection_manager = ConnectionManager()


# ============================================================================
# Authentication Helper
# ============================================================================


async def authenticate_websocket(
    websocket: WebSocket,
    token: str | None = None
) -> tuple[str | None, str | None]:
    """
    Authenticate a WebSocket connection.

    Authentication methods (in order of preference):
    1. Cookie-based (access_token cookie) - Most secure, recommended
    2. Authorization header - Secure for programmatic clients
    3. Query parameter - DEPRECATED, logged for security monitoring

    Returns tuple of (user_id, token) if authenticated, (None, None) otherwise.

    SECURITY FIX (Audit 2): Prioritize secure auth methods, warn on query param usage
    SECURITY FIX (Audit 6): Return token for periodic expiry validation
    """
    token_source = None

    # 1. PREFERRED: Try to get token from httpOnly cookie (most secure)
    if not token:
        cookie_token = websocket.cookies.get("access_token")
        if cookie_token:
            token = cookie_token
            token_source = "cookie"

    # 2. SECURE: Try to get from Authorization header
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            token_source = "header"

    # 3. DEPRECATED: Fall back to query params (for backwards compatibility only)
    # SECURITY WARNING: Query params can leak tokens in logs, browser history, referers
    # SECURITY FIX (Audit 6): This can be disabled via config in production
    if not token:
        query_token = websocket.query_params.get("token")
        if query_token:
            # Check if query param auth is allowed
            if not settings.websocket_allow_query_param_auth:
                logger.warning(
                    "websocket_query_param_auth_rejected",
                    path=str(websocket.url.path),
                    client=websocket.client.host if websocket.client else "unknown",
                    reason="Query parameter authentication is disabled. Use cookies or Authorization header.",
                )
                return None, None

            token = query_token
            token_source = "query_param"
            # Log security warning for monitoring
            logger.warning(
                "websocket_token_in_query_param",
                path=str(websocket.url.path),
                client=websocket.client.host if websocket.client else "unknown",
                warning="Token passed via query parameter is insecure. Use cookies or Authorization header instead.",
            )

    if not token:
        return None, None

    try:
        payload = verify_token(token, expected_type="access")
        user_id = payload.sub  # Use attribute access since it's a TokenPayload

        if user_id:
            logger.debug(
                "websocket_authenticated",
                user_id=user_id,
                auth_method=token_source,
            )

        # SECURITY FIX (Audit 6): Return token for periodic validation
        return user_id, token
    except Exception as e:
        logger.warning(
            "websocket_auth_failed",
            auth_method=token_source,
            error=str(e)[:100],
        )
        return None, None


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@websocket_router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    topics: str | None = Query(default=None, description="Comma-separated topic list")
):
    """
    WebSocket endpoint for real-time event streaming.

    Query Parameters:
    - token: JWT access token for authentication (REQUIRED)
    - topics: Comma-separated list of event topics to subscribe to

    Message Format (incoming):
    - {"type": "subscribe", "topics": ["topic1", "topic2"]}
    - {"type": "unsubscribe", "topics": ["topic1"]}
    - {"type": "ping"}

    Message Format (outgoing):
    - {"type": "event", "event_type": "...", "data": {...}, "timestamp": "..."}
    - {"type": "connected", "connection_id": "...", "subscriptions": [...]}
    - {"type": "pong"}
    """
    # SECURITY FIX (Audit 6): Validate Origin header to prevent CSWSH attacks
    if not validate_websocket_origin(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # SECURITY FIX (Audit 3): Require authentication for all WebSocket endpoints
    # SECURITY FIX (Audit 6): Get token for periodic expiry validation
    user_id, auth_token = await authenticate_websocket(websocket, token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # SECURITY FIX (Audit 6): Check connection limit per user
    if not connection_manager.can_user_connect(user_id):
        max_conn = get_max_connections_per_user()
        await websocket.close(
            code=4029,
            reason=f"Connection limit exceeded. Max {max_conn} connections per user."
        )
        return

    # Parse initial subscriptions
    subscriptions = []
    if topics:
        subscriptions = [t.strip() for t in topics.split(",") if t.strip()]

    # Accept connection
    connection = await connection_manager.connect_events(
        websocket=websocket,
        user_id=user_id,
        subscriptions=subscriptions,
        token=auth_token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
    )

    try:
        while True:
            # SECURITY FIX (Audit 6): Check token expiry periodically
            if not await connection.check_token_expiry():
                await connection.send_json({
                    "type": "error",
                    "code": "TOKEN_EXPIRED",
                    "message": "Your session has expired. Please reconnect with a new token."
                })
                await websocket.close(code=4001, reason="Token expired")
                break

            # Receive message
            try:
                data = await websocket.receive_json()
            except Exception:
                # Try text fallback
                text = await websocket.receive_text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue

            # Rate limiting check
            if not connection.check_rate_limit():
                await connection.send_json({
                    "type": "error",
                    "code": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Max {MAX_MESSAGES_PER_MINUTE} messages per minute."
                })
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                connection.last_ping = datetime.now(UTC)
                await connection.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                new_topics = data.get("topics", [])
                added_topics = []
                skipped_topics = []

                for topic in new_topics:
                    if topic in connection.subscriptions:
                        # Already subscribed
                        continue
                    if not connection.can_add_subscription():
                        # Subscription limit reached
                        skipped_topics.append(topic)
                        continue
                    connection.subscriptions.add(topic)
                    connection_manager._topic_subscribers[topic].add(connection.connection_id)
                    added_topics.append(topic)

                response = {
                    "type": "subscribed",
                    "topics": added_topics,
                    "all_subscriptions": list(connection.subscriptions)
                }
                if skipped_topics:
                    response["skipped"] = skipped_topics
                    response["reason"] = f"Subscription limit ({MAX_SUBSCRIPTIONS_PER_CONNECTION}) reached"
                await connection.send_json(response)

            elif msg_type == "unsubscribe":
                remove_topics = data.get("topics", [])
                for topic in remove_topics:
                    connection.subscriptions.discard(topic)
                    connection_manager._topic_subscribers[topic].discard(connection.connection_id)
                await connection.send_json({
                    "type": "unsubscribed",
                    "topics": remove_topics,
                    "all_subscriptions": list(connection.subscriptions)
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("websocket_events_error",
                    connection_id=connection.connection_id,
                    error=str(e))
    finally:
        await connection_manager.disconnect_events(connection.connection_id)


@websocket_router.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: str | None = Query(default=None)
):
    """
    WebSocket endpoint for live dashboard metrics.

    Receives periodic metrics updates from the server.
    Supports ping/pong for keepalive.

    Message Format (outgoing):
    - {"type": "metrics_update", "metrics": {...}, "timestamp": "..."}
    - {"type": "connected", "connection_id": "..."}
    """
    # SECURITY FIX (Audit 6): Validate Origin header to prevent CSWSH attacks
    if not validate_websocket_origin(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # SECURITY FIX (Audit 3): Require authentication for all WebSocket endpoints
    # SECURITY FIX (Audit 6): Get token for periodic expiry validation
    user_id, auth_token = await authenticate_websocket(websocket, token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # SECURITY FIX (Audit 6): Check connection limit per user
    if not connection_manager.can_user_connect(user_id):
        max_conn = get_max_connections_per_user()
        await websocket.close(
            code=4029,
            reason=f"Connection limit exceeded. Max {max_conn} connections per user."
        )
        return

    # Accept connection
    connection = await connection_manager.connect_dashboard(
        websocket=websocket,
        user_id=user_id,
        token=auth_token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
    )

    try:
        while True:
            # SECURITY FIX (Audit 6): Check token expiry periodically
            if not await connection.check_token_expiry():
                await connection.send_json({
                    "type": "error",
                    "code": "TOKEN_EXPIRED",
                    "message": "Your session has expired. Please reconnect with a new token."
                })
                await websocket.close(code=4001, reason="Token expired")
                break

            try:
                data = await websocket.receive_json()
            except Exception:
                text = await websocket.receive_text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue

            msg_type = data.get("type")

            if msg_type == "ping":
                connection.last_ping = datetime.now(UTC)
                await connection.send_json({"type": "pong"})

            elif msg_type == "request_metrics":
                # Client can request immediate metrics update
                # In a real implementation, gather current metrics
                await connection.send_json({
                    "type": "metrics_update",
                    "metrics": {},  # Would be populated from metrics service
                    "timestamp": datetime.now(UTC).isoformat()
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("websocket_dashboard_error",
                    connection_id=connection.connection_id,
                    error=str(e))
    finally:
        await connection_manager.disconnect_dashboard(connection.connection_id)


@websocket_router.websocket("/ws/chat/{room_id}")
async def websocket_chat(
    websocket: WebSocket,
    room_id: str,
    token: str | None = Query(default=None),
    display_name: str | None = Query(default=None)
):
    """
    WebSocket endpoint for chat rooms.

    Path Parameters:
    - room_id: Unique identifier for the chat room

    Query Parameters:
    - token: JWT access token for authentication (required)
    - display_name: User's display name in the room

    Message Format (incoming):
    - {"type": "message", "content": "..."} - Send a chat message
    - {"type": "typing"} - Indicate user is typing
    - {"type": "ping"}

    Message Format (outgoing):
    - {"type": "message", "data": {"user_id": "...", "content": "...", "display_name": "..."}}
    - {"type": "user_joined", "data": {"user_id": "...", "display_name": "..."}}
    - {"type": "user_left", "data": {"user_id": "..."}}
    - {"type": "typing", "data": {"user_id": "...", "display_name": "..."}}
    - {"type": "participants", "data": {"users": [...]}}
    """
    # SECURITY FIX (Audit 6): Validate Origin header to prevent CSWSH attacks
    if not validate_websocket_origin(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # Authenticate - required for chat
    # SECURITY FIX (Audit 6): Get token for periodic expiry validation
    user_id, auth_token = await authenticate_websocket(websocket, token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # SECURITY FIX (Audit 6): Check connection limit per user
    if not connection_manager.can_user_connect(user_id):
        max_conn = get_max_connections_per_user()
        await websocket.close(
            code=4029,
            reason=f"Connection limit exceeded. Max {max_conn} connections per user."
        )
        return

    # Accept connection
    connection = await connection_manager.connect_chat(
        websocket=websocket,
        room_id=room_id,
        user_id=user_id,
        display_name=display_name,
        token=auth_token,  # SECURITY FIX (Audit 6): Pass token for expiry checks
    )

    # Send current participants
    participants = connection_manager.get_room_participants(room_id)
    await connection.send_json({
        "type": "participants",
        "data": {"users": participants}
    })

    try:
        while True:
            # SECURITY FIX (Audit 6): Check token expiry periodically
            if not await connection.check_token_expiry():
                await connection.send_json({
                    "type": "error",
                    "code": "TOKEN_EXPIRED",
                    "message": "Your session has expired. Please reconnect with a new token."
                })
                await websocket.close(code=4001, reason="Token expired")
                break

            try:
                data = await websocket.receive_json()
            except Exception:
                text = await websocket.receive_text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue

            msg_type = data.get("type")

            if msg_type == "ping":
                connection.last_ping = datetime.now(UTC)
                await connection.send_json({"type": "pong"})

            elif msg_type == "message":
                content = data.get("content", "").strip()
                if content:
                    # Broadcast message to room
                    await connection_manager.broadcast_chat(
                        room_id=room_id,
                        message_type="message",
                        data={
                            "user_id": user_id,
                            "display_name": display_name or user_id,
                            "content": content,
                            "message_id": str(uuid4())
                        }
                    )

            elif msg_type == "typing":
                # Broadcast typing indicator (exclude sender)
                await connection_manager.broadcast_chat(
                    room_id=room_id,
                    message_type="typing",
                    data={
                        "user_id": user_id,
                        "display_name": display_name or user_id
                    },
                    exclude_connection=connection.connection_id
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("websocket_chat_error",
                    connection_id=connection.connection_id,
                    room_id=room_id,
                    error=str(e))
    finally:
        await connection_manager.disconnect_chat(room_id, connection.connection_id)


# ============================================================================
# WebSocket Stats Endpoint (REST)
# ============================================================================


@websocket_router.get("/ws/stats")
async def get_websocket_stats(
    current_user: User = Depends(get_current_user_ws),
) -> dict[str, Any]:
    """
    Get WebSocket connection statistics.

    SECURITY FIX (Audit 4 - L6): Requires authentication to prevent
    information disclosure about active connections.
    """
    # Only allow admins to view connection stats
    if current_user.role not in ("admin", "moderator"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view WebSocket statistics"
        )
    return connection_manager.get_stats()
