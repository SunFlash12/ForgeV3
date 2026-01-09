"""
Forge WebSocket Handlers

Provides WebSocket endpoints for:
- /ws/events: Real-time system event streaming
- /ws/dashboard: Live dashboard metrics and updates
- /ws/chat/{room_id}: Collaborative chat rooms
"""

import asyncio
import json
import structlog
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from pydantic import BaseModel, Field

from forge.security.tokens import verify_token


logger = structlog.get_logger(__name__)

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
        user_id: Optional[str] = None,
        subscriptions: Optional[set[str]] = None
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.user_id = user_id
        self.subscriptions = subscriptions or set()
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping = datetime.now(timezone.utc)
        self.message_count = 0
    
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
    
    # -------------------------------------------------------------------------
    # Event Stream Connections
    # -------------------------------------------------------------------------
    
    async def connect_events(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
        subscriptions: Optional[list[str]] = None
    ) -> WebSocketConnection:
        """Accept a new event stream connection."""
        
        await websocket.accept()
        
        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id,
            subscriptions=set(subscriptions or [])
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
        topic: Optional[str] = None
    ):
        """Broadcast an event to subscribed connections."""
        
        message = {
            "type": "event",
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
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
        user_id: Optional[str] = None
    ) -> WebSocketConnection:
        """Accept a new dashboard connection."""
        
        await websocket.accept()
        
        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
        display_name: Optional[str] = None
    ) -> WebSocketConnection:
        """Accept a new chat room connection."""
        
        await websocket.accept()
        
        connection_id = str(uuid4())
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            user_id=user_id
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
        exclude_connection: Optional[str] = None
    ):
        """Broadcast a message to all connections in a chat room."""
        
        if room_id not in self._chat_connections:
            return
        
        message = {
            "type": message_type,
            "data": data,
            "room_id": room_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
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
    
    def _find_chat_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
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
        
        return list(set(
            conn.user_id 
            for conn in self._chat_connections[room_id].values()
            if conn.user_id
        ))


# Global connection manager instance
connection_manager = ConnectionManager()


# ============================================================================
# Authentication Helper
# ============================================================================


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = None
) -> Optional[str]:
    """
    Authenticate a WebSocket connection.

    Authentication methods (in order of preference):
    1. Cookie-based (access_token cookie) - Most secure, recommended
    2. Authorization header - Secure for programmatic clients
    3. Query parameter - DEPRECATED, logged for security monitoring

    Returns user_id if authenticated, None otherwise.

    SECURITY FIX (Audit 2): Prioritize secure auth methods, warn on query param usage
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
    if not token:
        query_token = websocket.query_params.get("token")
        if query_token:
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
        return None

    try:
        payload = verify_token(token, expected_type="access")
        user_id = payload.get("sub")

        if user_id:
            logger.debug(
                "websocket_authenticated",
                user_id=user_id,
                auth_method=token_source,
            )

        return user_id
    except Exception as e:
        logger.warning(
            "websocket_auth_failed",
            auth_method=token_source,
            error=str(e)[:100],
        )
        return None


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@websocket_router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    topics: Optional[str] = Query(default=None, description="Comma-separated topic list")
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

    # SECURITY FIX (Audit 3): Require authentication for all WebSocket endpoints
    user_id = await authenticate_websocket(websocket, token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Parse initial subscriptions
    subscriptions = []
    if topics:
        subscriptions = [t.strip() for t in topics.split(",") if t.strip()]

    # Accept connection
    connection = await connection_manager.connect_events(
        websocket=websocket,
        user_id=user_id,
        subscriptions=subscriptions
    )
    
    try:
        while True:
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
            
            msg_type = data.get("type")
            
            if msg_type == "ping":
                connection.last_ping = datetime.now(timezone.utc)
                await connection.send_json({"type": "pong"})
            
            elif msg_type == "subscribe":
                new_topics = data.get("topics", [])
                for topic in new_topics:
                    connection.subscriptions.add(topic)
                    connection_manager._topic_subscribers[topic].add(connection.connection_id)
                await connection.send_json({
                    "type": "subscribed",
                    "topics": new_topics,
                    "all_subscriptions": list(connection.subscriptions)
                })
            
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
    token: Optional[str] = Query(default=None)
):
    """
    WebSocket endpoint for live dashboard metrics.

    Receives periodic metrics updates from the server.
    Supports ping/pong for keepalive.

    Message Format (outgoing):
    - {"type": "metrics_update", "metrics": {...}, "timestamp": "..."}
    - {"type": "connected", "connection_id": "..."}
    """

    # SECURITY FIX (Audit 3): Require authentication for all WebSocket endpoints
    user_id = await authenticate_websocket(websocket, token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection
    connection = await connection_manager.connect_dashboard(
        websocket=websocket,
        user_id=user_id
    )
    
    try:
        while True:
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
                connection.last_ping = datetime.now(timezone.utc)
                await connection.send_json({"type": "pong"})
            
            elif msg_type == "request_metrics":
                # Client can request immediate metrics update
                # In a real implementation, gather current metrics
                await connection.send_json({
                    "type": "metrics_update",
                    "metrics": {},  # Would be populated from metrics service
                    "timestamp": datetime.now(timezone.utc).isoformat()
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
    token: Optional[str] = Query(default=None),
    display_name: Optional[str] = Query(default=None)
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
    
    # Authenticate - required for chat
    user_id = await authenticate_websocket(websocket, token)
    
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Accept connection
    connection = await connection_manager.connect_chat(
        websocket=websocket,
        room_id=room_id,
        user_id=user_id,
        display_name=display_name
    )
    
    # Send current participants
    participants = connection_manager.get_room_participants(room_id)
    await connection.send_json({
        "type": "participants",
        "data": {"users": participants}
    })
    
    try:
        while True:
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
                connection.last_ping = datetime.now(timezone.utc)
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
async def get_websocket_stats() -> dict[str, Any]:
    """Get WebSocket connection statistics."""
    return connection_manager.get_stats()
