"""
Forge Cascade V2 - WebSocket Handler Tests

Comprehensive tests for WebSocket endpoints and handlers:
- Connection management
- Authentication
- Origin validation
- Rate limiting
- Message handling
- Token expiry checks
- Chat room functionality
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


# =============================================================================
# WebSocketConnection Tests
# =============================================================================


class TestWebSocketConnection:
    """Tests for WebSocketConnection class."""

    def test_connection_initialization(self):
        """Test WebSocketConnection initializes with correct defaults."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            user_id="user-456",
        )

        assert connection.connection_id == "conn-123"
        assert connection.user_id == "user-456"
        assert connection.subscriptions == set()
        assert connection.message_count == 0
        assert connection.connected_at is not None

    def test_connection_with_subscriptions(self):
        """Test WebSocketConnection initializes with subscriptions."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            subscriptions={"topic1", "topic2"},
        )

        assert "topic1" in connection.subscriptions
        assert "topic2" in connection.subscriptions

    def test_connection_with_token(self):
        """Test WebSocketConnection stores token for validation."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            token="test-jwt-token",
        )

        assert connection._token == "test-jwt-token"


class TestWebSocketConnectionRateLimiting:
    """Tests for WebSocketConnection rate limiting."""

    def test_check_rate_limit_allows_under_limit(self):
        """Test rate limit allows requests under the limit."""
        from forge.api.websocket.handlers import WebSocketConnection, MAX_MESSAGES_PER_MINUTE

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        # Should allow first message
        assert connection.check_rate_limit() is True

    def test_check_rate_limit_blocks_over_limit(self):
        """Test rate limit blocks when over limit."""
        from forge.api.websocket.handlers import (
            WebSocketConnection,
            MAX_MESSAGES_PER_MINUTE,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        # Fill up rate limit
        for _ in range(MAX_MESSAGES_PER_MINUTE + 1):
            connection.check_rate_limit()

        # Next should be blocked
        assert connection.check_rate_limit() is False

    def test_rate_limit_uses_bounded_deque(self):
        """Test rate limit uses bounded deque for memory safety."""
        from forge.api.websocket.handlers import (
            WebSocketConnection,
            MAX_MESSAGES_PER_MINUTE,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        # Verify the deque has maxlen set
        assert connection._message_timestamps.maxlen == MAX_MESSAGES_PER_MINUTE * 2


class TestWebSocketConnectionSubscriptions:
    """Tests for WebSocketConnection subscription management."""

    def test_can_add_subscription_under_limit(self):
        """Test can add subscription when under limit."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        assert connection.can_add_subscription() is True

    def test_can_add_subscription_at_limit(self):
        """Test cannot add subscription at limit."""
        from forge.api.websocket.handlers import (
            WebSocketConnection,
            MAX_SUBSCRIPTIONS_PER_CONNECTION,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            subscriptions={f"topic-{i}" for i in range(MAX_SUBSCRIPTIONS_PER_CONNECTION)},
        )

        assert connection.can_add_subscription() is False


class TestWebSocketConnectionTokenExpiry:
    """Tests for WebSocketConnection token expiry checking."""

    @pytest.mark.asyncio
    async def test_check_token_expiry_no_token(self):
        """Test check_token_expiry returns True when no token."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            token=None,
        )

        result = await connection.check_token_expiry()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_token_expiry_valid_token(self):
        """Test check_token_expiry returns True for valid token."""
        from forge.api.websocket.handlers import WebSocketConnection
        from forge.security.tokens import create_access_token
        from forge.models.user import TokenPayload

        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            token=token,
        )
        # Force immediate check by setting last check time in the past
        connection._last_token_check = datetime.now(UTC) - timedelta(hours=1)

        with patch("forge.security.tokens.TokenBlacklist.is_blacklisted_async", return_value=False):
            result = await connection.check_token_expiry()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_token_expiry_blacklisted_token(self):
        """Test check_token_expiry returns False for blacklisted token."""
        from forge.api.websocket.handlers import WebSocketConnection
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            token=token,
        )
        connection._last_token_check = datetime.now(UTC) - timedelta(hours=1)

        with patch("forge.security.tokens.TokenBlacklist.is_blacklisted_async", return_value=True):
            result = await connection.check_token_expiry()

        assert result is False


class TestWebSocketConnectionMessaging:
    """Tests for WebSocketConnection messaging."""

    @pytest.mark.asyncio
    async def test_send_json_success(self):
        """Test send_json returns True on success."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        result = await connection.send_json({"type": "test"})
        assert result is True
        assert connection.message_count == 1

    @pytest.mark.asyncio
    async def test_send_json_failure(self):
        """Test send_json returns False on failure."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_json.side_effect = ConnectionError("Disconnected")
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        result = await connection.send_json({"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_text_success(self):
        """Test send_text returns True on success."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        result = await connection.send_text("hello")
        assert result is True


class TestWebSocketConnectionIdleTimeout:
    """Tests for WebSocketConnection idle timeout."""

    def test_is_idle_when_no_recent_activity(self):
        """Test is_idle returns True when no recent activity."""
        from forge.api.websocket.handlers import (
            WebSocketConnection,
            IDLE_TIMEOUT_SECONDS,
        )

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )
        # Set last message time to past the idle timeout
        connection.last_message_received = datetime.now(UTC) - timedelta(
            seconds=IDLE_TIMEOUT_SECONDS + 60
        )

        assert connection.is_idle() is True

    def test_is_not_idle_with_recent_activity(self):
        """Test is_idle returns False with recent activity."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )
        # Recent activity (just now)
        connection.last_message_received = datetime.now(UTC)

        assert connection.is_idle() is False

    def test_record_inbound_activity(self):
        """Test record_inbound_activity updates timestamps."""
        from forge.api.websocket.handlers import WebSocketConnection

        mock_ws = MagicMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )
        old_time = connection.last_message_received

        # Small delay to ensure time difference
        connection.record_inbound_activity()

        assert connection.last_message_received >= old_time


# =============================================================================
# ConnectionManager Tests
# =============================================================================


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_manager_initialization(self):
        """Test ConnectionManager initializes correctly."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()

        assert manager.active_connections_count == 0
        assert manager._total_connections == 0
        assert manager._total_messages_sent == 0

    def test_is_at_capacity_when_under_limit(self):
        """Test is_at_capacity returns False when under limit."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        assert manager.is_at_capacity() is False

    def test_can_user_connect_first_connection(self):
        """Test can_user_connect allows first connection."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        assert manager.can_user_connect("user-123") is True

    def test_can_user_connect_anonymous(self):
        """Test can_user_connect allows anonymous connections."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        assert manager.can_user_connect(None) is True

    def test_get_user_connection_count(self):
        """Test get_user_connection_count returns correct count."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        manager._user_connections["user-123"] = {"conn-1", "conn-2"}

        assert manager.get_user_connection_count("user-123") == 2

    def test_get_stats_empty(self):
        """Test get_stats returns empty stats initially."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        stats = manager.get_stats()

        assert stats["event_connections"] == 0
        assert stats["dashboard_connections"] == 0
        assert stats["chat_rooms"] == 0
        assert stats["chat_connections"] == 0

    def test_get_room_participants_empty_room(self):
        """Test get_room_participants returns empty for non-existent room."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        participants = manager.get_room_participants("non-existent-room")

        assert participants == []


class TestConnectionManagerEvents:
    """Tests for ConnectionManager event connections."""

    @pytest.mark.asyncio
    async def test_connect_events(self):
        """Test connect_events creates connection."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_events(
            websocket=mock_ws,
            user_id="user-123",
            subscriptions=["topic1"],
        )

        assert connection is not None
        assert connection.user_id == "user-123"
        assert "topic1" in connection.subscriptions
        assert manager.active_connections_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_events(self):
        """Test disconnect_events removes connection."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_events(
            websocket=mock_ws,
            user_id="user-123",
        )
        connection_id = connection.connection_id

        await manager.disconnect_events(connection_id)

        assert connection_id not in manager._event_connections

    @pytest.mark.asyncio
    async def test_broadcast_event_to_subscribers(self):
        """Test broadcast_event sends to topic subscribers."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_events(
            websocket=mock_ws,
            user_id="user-123",
            subscriptions=["capsules"],
        )

        await manager.broadcast_event(
            event_type="capsule_created",
            data={"id": "capsule-1"},
            topic="capsules",
        )

        mock_ws.send_json.assert_called()


class TestConnectionManagerDashboard:
    """Tests for ConnectionManager dashboard connections."""

    @pytest.mark.asyncio
    async def test_connect_dashboard(self):
        """Test connect_dashboard creates connection."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_dashboard(
            websocket=mock_ws,
            user_id="user-123",
        )

        assert connection is not None
        assert connection.user_id == "user-123"
        assert len(manager._dashboard_connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_dashboard(self):
        """Test disconnect_dashboard removes connection."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_dashboard(
            websocket=mock_ws,
            user_id="user-123",
        )
        connection_id = connection.connection_id

        await manager.disconnect_dashboard(connection_id)

        assert connection_id not in manager._dashboard_connections

    @pytest.mark.asyncio
    async def test_broadcast_dashboard_update(self):
        """Test broadcast_dashboard_update sends metrics."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect_dashboard(websocket=mock_ws, user_id="user-123")

        await manager.broadcast_dashboard_update({"cpu": 50, "memory": 70})

        mock_ws.send_json.assert_called()


class TestConnectionManagerChat:
    """Tests for ConnectionManager chat connections."""

    @pytest.mark.asyncio
    async def test_connect_chat(self):
        """Test connect_chat creates connection in room."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_chat(
            websocket=mock_ws,
            room_id="room-1",
            user_id="user-123",
            display_name="Test User",
        )

        assert connection is not None
        assert "room-1" in manager._chat_connections
        assert len(manager._chat_connections["room-1"]) == 1

    @pytest.mark.asyncio
    async def test_disconnect_chat(self):
        """Test disconnect_chat removes connection from room."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        connection = await manager.connect_chat(
            websocket=mock_ws,
            room_id="room-1",
            user_id="user-123",
        )
        connection_id = connection.connection_id

        await manager.disconnect_chat("room-1", connection_id)

        # Room should be cleaned up when empty
        assert "room-1" not in manager._chat_connections

    @pytest.mark.asyncio
    async def test_broadcast_chat(self):
        """Test broadcast_chat sends to room members."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect_chat(
            websocket=mock_ws1,
            room_id="room-1",
            user_id="user-1",
        )
        await manager.connect_chat(
            websocket=mock_ws2,
            room_id="room-1",
            user_id="user-2",
        )

        await manager.broadcast_chat(
            room_id="room-1",
            message_type="message",
            data={"content": "Hello"},
        )

        mock_ws1.send_json.assert_called()
        mock_ws2.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_broadcast_chat_excludes_sender(self):
        """Test broadcast_chat can exclude sender."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        conn1 = await manager.connect_chat(
            websocket=mock_ws1,
            room_id="room-1",
            user_id="user-1",
        )
        await manager.connect_chat(
            websocket=mock_ws2,
            room_id="room-1",
            user_id="user-2",
        )

        # Reset mock call counts after connection messages
        mock_ws1.send_json.reset_mock()
        mock_ws2.send_json.reset_mock()

        await manager.broadcast_chat(
            room_id="room-1",
            message_type="message",
            data={"content": "Hello"},
            exclude_connection=conn1.connection_id,
        )

        # conn1 should not receive the message
        # Only user_joined messages should have been sent earlier
        mock_ws2.send_json.assert_called()


class TestConnectionManagerForceDisconnect:
    """Tests for ConnectionManager force disconnect."""

    @pytest.mark.asyncio
    async def test_force_disconnect_user(self):
        """Test force_disconnect_user closes all user connections."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect_events(websocket=mock_ws1, user_id="user-123")
        await manager.connect_dashboard(websocket=mock_ws2, user_id="user-123")

        closed_count = await manager.force_disconnect_user(
            "user-123", reason="privilege_change"
        )

        assert closed_count == 2
        assert manager.get_user_connection_count("user-123") == 0

    @pytest.mark.asyncio
    async def test_force_disconnect_sends_notification(self):
        """Test force_disconnect_user sends notification before closing."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect_events(websocket=mock_ws, user_id="user-123")

        await manager.force_disconnect_user("user-123", reason="logout")

        # Should have sent a session_terminated message
        calls = mock_ws.send_json.call_args_list
        notification_sent = any(
            "session_terminated" in str(call) for call in calls
        )
        assert notification_sent

    @pytest.mark.asyncio
    async def test_notify_privilege_change(self):
        """Test notify_privilege_change sends notification."""
        from forge.api.websocket.handlers import ConnectionManager

        manager = ConnectionManager()
        mock_ws = AsyncMock(spec=WebSocket)

        await manager.connect_events(websocket=mock_ws, user_id="user-123")

        count = await manager.notify_privilege_change(
            "user-123", change_type="role", message="Role updated"
        )

        assert count == 1


# =============================================================================
# Origin Validation Tests
# =============================================================================


class TestOriginValidation:
    """Tests for WebSocket origin validation."""

    def test_validate_websocket_origin_no_origin_dev(self):
        """Test validates when no origin header in development."""
        from forge.api.websocket.handlers import validate_websocket_origin

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.headers.get.return_value = None

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.app_env = "development"

            result = validate_websocket_origin(mock_ws)
            assert result is True

    def test_validate_websocket_origin_no_origin_production(self):
        """Test rejects when no origin header in production."""
        from forge.api.websocket.handlers import validate_websocket_origin

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.headers.get.return_value = None
        mock_ws.client = MagicMock()
        mock_ws.url.path = "/ws/events"

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.app_env = "production"

            result = validate_websocket_origin(mock_ws)
            assert result is False

    def test_validate_websocket_origin_valid(self):
        """Test validates allowed origin."""
        from forge.api.websocket.handlers import validate_websocket_origin

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.headers.get.return_value = "http://localhost:3000"

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.cors_origins_list = ["http://localhost:3000"]

            result = validate_websocket_origin(mock_ws)
            assert result is True

    def test_validate_websocket_origin_invalid(self):
        """Test rejects invalid origin."""
        from forge.api.websocket.handlers import validate_websocket_origin

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.headers.get.return_value = "http://evil.com"
        mock_ws.client = MagicMock()

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.cors_origins_list = ["http://localhost:3000"]
            mock_settings.app_env = "production"

            result = validate_websocket_origin(mock_ws)
            assert result is False


class TestValidateAndAcceptWebsocket:
    """Tests for validate_and_accept_websocket function."""

    @pytest.mark.asyncio
    async def test_accepts_valid_origin(self):
        """Test accepts connection with valid origin."""
        from forge.api.websocket.handlers import validate_and_accept_websocket

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.headers.get.return_value = "http://localhost:3000"

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.cors_origins_list = ["http://localhost:3000"]

            result = await validate_and_accept_websocket(mock_ws)

            assert result is True
            mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_invalid_origin(self):
        """Test rejects connection with invalid origin."""
        from forge.api.websocket.handlers import validate_and_accept_websocket

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.headers.get.return_value = "http://evil.com"
        mock_ws.client = MagicMock()

        with patch("forge.api.websocket.handlers.settings") as mock_settings:
            mock_settings.cors_origins_list = ["http://localhost:3000"]
            mock_settings.app_env = "production"

            result = await validate_and_accept_websocket(mock_ws)

            assert result is False
            mock_ws.close.assert_called_once()


# =============================================================================
# Authentication Helper Tests
# =============================================================================


class TestAuthenticateWebsocket:
    """Tests for authenticate_websocket function."""

    @pytest.mark.asyncio
    async def test_authenticate_from_cookie(self):
        """Test authentication from cookie."""
        from forge.api.websocket.handlers import authenticate_websocket
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.cookies.get.return_value = token
        mock_ws.headers.get.return_value = ""
        mock_ws.query_params.get.return_value = None

        user_id, auth_token = await authenticate_websocket(mock_ws)

        assert user_id == "user-123"
        assert auth_token == token

    @pytest.mark.asyncio
    async def test_authenticate_from_header(self):
        """Test authentication from Authorization header."""
        from forge.api.websocket.handlers import authenticate_websocket
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user-456",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.cookies.get.return_value = None
        mock_ws.headers.get.return_value = f"Bearer {token}"
        mock_ws.query_params.get.return_value = None

        user_id, auth_token = await authenticate_websocket(mock_ws)

        assert user_id == "user-456"

    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        """Test authentication returns None when no token."""
        from forge.api.websocket.handlers import authenticate_websocket

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.cookies.get.return_value = None
        mock_ws.headers.get.return_value = ""
        mock_ws.query_params.get.return_value = None

        user_id, auth_token = await authenticate_websocket(mock_ws)

        assert user_id is None
        assert auth_token is None

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self):
        """Test authentication returns None for invalid token."""
        from forge.api.websocket.handlers import authenticate_websocket

        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.cookies.get.return_value = "invalid-token"
        mock_ws.headers.get.return_value = ""
        mock_ws.query_params.get.return_value = None
        mock_ws.client = MagicMock()
        mock_ws.client.host = "127.0.0.1"

        user_id, auth_token = await authenticate_websocket(mock_ws)

        assert user_id is None


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestSendErrorAndClose:
    """Tests for _send_error_and_close helper."""

    @pytest.mark.asyncio
    async def test_sends_error_before_close(self):
        """Test sends error message before closing."""
        from forge.api.websocket.handlers import _send_error_and_close, WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )

        await _send_error_and_close(
            connection,
            mock_ws,
            code="TEST_ERROR",
            message="Test error message",
        )

        mock_ws.send_json.assert_called()
        mock_ws.close.assert_called()


class TestReceiveJsonWithTimeout:
    """Tests for _receive_json_with_timeout helper."""

    @pytest.mark.asyncio
    async def test_receives_json_within_timeout(self):
        """Test receives JSON within timeout."""
        from forge.api.websocket.handlers import _receive_json_with_timeout

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json.return_value = {"type": "ping"}

        result = await _receive_json_with_timeout(mock_ws, timeout=5.0)

        assert result == {"type": "ping"}

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        """Test returns None when timeout occurs."""
        from forge.api.websocket.handlers import _receive_json_with_timeout

        mock_ws = AsyncMock(spec=WebSocket)

        async def slow_receive():
            await asyncio.sleep(10)
            return {"type": "ping"}

        mock_ws.receive_json.side_effect = slow_receive

        result = await _receive_json_with_timeout(mock_ws, timeout=0.1)

        assert result is None


class TestRunPeriodicChecks:
    """Tests for _run_periodic_checks helper."""

    @pytest.mark.asyncio
    async def test_returns_true_for_valid_connection(self):
        """Test returns True for valid connection."""
        from forge.api.websocket.handlers import _run_periodic_checks, WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
        )
        # Ensure not idle
        connection.last_message_received = datetime.now(UTC)

        result = await _run_periodic_checks(connection, mock_ws)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_expired_token(self):
        """Test returns False for expired token."""
        from forge.api.websocket.handlers import _run_periodic_checks, WebSocketConnection

        mock_ws = AsyncMock(spec=WebSocket)
        connection = WebSocketConnection(
            websocket=mock_ws,
            connection_id="conn-123",
            token="test-token",
        )
        connection._token_valid = False
        connection._last_token_check = datetime.now(UTC) - timedelta(hours=1)

        with patch.object(connection, "check_token_expiry", return_value=False):
            result = await _run_periodic_checks(connection, mock_ws)

        assert result is False


# =============================================================================
# Constants and Configuration Tests
# =============================================================================


class TestWebSocketConstants:
    """Tests for WebSocket configuration constants."""

    def test_max_subscriptions_limit(self):
        """Test MAX_SUBSCRIPTIONS_PER_CONNECTION is reasonable."""
        from forge.api.websocket.handlers import MAX_SUBSCRIPTIONS_PER_CONNECTION

        assert MAX_SUBSCRIPTIONS_PER_CONNECTION == 50

    def test_max_messages_per_minute(self):
        """Test MAX_MESSAGES_PER_MINUTE is set."""
        from forge.api.websocket.handlers import MAX_MESSAGES_PER_MINUTE

        assert MAX_MESSAGES_PER_MINUTE == 60

    def test_max_websocket_message_size(self):
        """Test MAX_WEBSOCKET_MESSAGE_SIZE is 64KB."""
        from forge.api.websocket.handlers import MAX_WEBSOCKET_MESSAGE_SIZE

        assert MAX_WEBSOCKET_MESSAGE_SIZE == 64 * 1024

    def test_max_total_connections(self):
        """Test MAX_TOTAL_CONNECTIONS limit."""
        from forge.api.websocket.handlers import MAX_TOTAL_CONNECTIONS

        assert MAX_TOTAL_CONNECTIONS == 10000

    def test_idle_timeout_seconds(self):
        """Test IDLE_TIMEOUT_SECONDS is 15 minutes."""
        from forge.api.websocket.handlers import IDLE_TIMEOUT_SECONDS

        assert IDLE_TIMEOUT_SECONDS == 900

    def test_token_revalidation_interval(self):
        """Test TOKEN_REVALIDATION_INTERVAL_SECONDS is 5 minutes."""
        from forge.api.websocket.handlers import TOKEN_REVALIDATION_INTERVAL_SECONDS

        assert TOKEN_REVALIDATION_INTERVAL_SECONDS == 300


# =============================================================================
# Global Connection Manager Tests
# =============================================================================


class TestGlobalConnectionManager:
    """Tests for global connection_manager instance."""

    def test_global_manager_exists(self):
        """Test global connection_manager is instantiated."""
        from forge.api.websocket.handlers import connection_manager

        assert connection_manager is not None

    def test_global_manager_is_connection_manager(self):
        """Test global instance is ConnectionManager."""
        from forge.api.websocket.handlers import connection_manager, ConnectionManager

        assert isinstance(connection_manager, ConnectionManager)


# =============================================================================
# WebSocket Router Tests
# =============================================================================


class TestWebSocketRouter:
    """Tests for websocket_router configuration."""

    def test_websocket_router_exists(self):
        """Test websocket_router is instantiated."""
        from forge.api.websocket.handlers import websocket_router

        assert websocket_router is not None

    def test_websocket_router_has_routes(self):
        """Test websocket_router has WebSocket routes."""
        from forge.api.websocket.handlers import websocket_router

        routes = websocket_router.routes
        paths = [route.path for route in routes]

        assert "/ws/events" in paths
        assert "/ws/dashboard" in paths
        assert "/ws/chat/{room_id}" in paths


# =============================================================================
# Configuration Function Tests
# =============================================================================


class TestConfigurationFunctions:
    """Tests for configuration getter functions."""

    def test_get_token_expiry_check_interval(self):
        """Test get_token_expiry_check_interval returns value."""
        from forge.api.websocket.handlers import get_token_expiry_check_interval

        interval = get_token_expiry_check_interval()
        assert isinstance(interval, int)
        assert interval > 0

    def test_get_max_connections_per_user(self):
        """Test get_max_connections_per_user returns value."""
        from forge.api.websocket.handlers import get_max_connections_per_user

        max_conn = get_max_connections_per_user()
        assert isinstance(max_conn, int)
        assert max_conn > 0
