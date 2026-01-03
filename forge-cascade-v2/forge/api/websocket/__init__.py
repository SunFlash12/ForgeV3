"""
Forge WebSocket Module

Provides real-time communication capabilities:
- Event streaming for system events
- Dashboard updates with live metrics
- Chat functionality for collaborative features
"""

from forge.api.websocket.handlers import (
    ConnectionManager,
    websocket_router,
)

__all__ = [
    "ConnectionManager",
    "websocket_router",
]
