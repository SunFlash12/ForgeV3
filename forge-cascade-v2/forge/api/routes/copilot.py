"""
Copilot API Routes

This module provides REST and WebSocket endpoints for interacting with
the GitHub Copilot SDK integration in Forge.

Endpoints:
- POST /copilot/chat - Send a message and get a response
- POST /copilot/stream - Send a message and stream the response
- GET /copilot/history - Get conversation history
- POST /copilot/clear - Clear conversation history
- GET /copilot/status - Get agent status
- WebSocket /copilot/ws - Real-time chat interface
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from forge.api.dependencies import ActiveUserDep
from forge.security.tokens import TokenBlacklist, verify_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/copilot", tags=["copilot"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    """Request for chat endpoint."""

    message: str = Field(description="User message to send to the Copilot agent")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata to attach to the message"
    )


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    content: str = Field(description="Assistant's response")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="Tools that were called during response generation"
    )
    reasoning: str | None = Field(
        default=None, description="Optional reasoning trace from the model"
    )
    latency_ms: float = Field(description="Response latency in milliseconds")


class HistoryMessage(BaseModel):
    """A message in the conversation history."""

    role: str = Field(description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="ISO timestamp of the message")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    """Response containing conversation history."""

    messages: list[HistoryMessage]
    count: int


class StatusResponse(BaseModel):
    """Agent status response."""

    state: str = Field(description="Current agent state")
    is_running: bool
    model: str | None = Field(default=None)
    session_active: bool
    history_length: int


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

# Global agent instance (initialized on startup)
# SECURITY FIX (Audit 6): Use asyncio.Lock for thread-safe initialization
_agent = None
_agent_lock: asyncio.Lock | None = None


def _get_agent_lock() -> asyncio.Lock:
    """Get or create the agent lock (lazy initialization for event loop safety)."""
    global _agent_lock
    if _agent_lock is None:
        _agent_lock = asyncio.Lock()
    return _agent_lock


async def get_agent():
    """
    Get or create the Copilot agent.

    SECURITY FIX (Audit 6): Uses asyncio.Lock to prevent race conditions
    during concurrent initialization requests.
    """
    global _agent

    # Fast path: if already initialized, return immediately
    if _agent is not None:
        return _agent

    # Slow path: acquire lock and check again (double-check locking pattern)
    async with _get_agent_lock():
        # Check again after acquiring lock (another coroutine may have initialized)
        if _agent is not None:
            return _agent

        try:
            from forge.copilot import CopilotForgeAgent

            _agent = CopilotForgeAgent()
            await _agent.start()
            logger.info("Copilot agent initialized for API")
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="GitHub Copilot SDK not installed. "
                "Install with: pip install github-copilot-sdk",
            )
        except (RuntimeError, ConnectionError, OSError, ValueError) as e:
            logger.error(f"Failed to initialize Copilot agent: {e}")
            # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details
            raise HTTPException(
                status_code=503,
                detail="Failed to initialize Copilot agent. Please try again or contact support.",
            )

    return _agent


async def shutdown_agent():
    """Shutdown the Copilot agent on app shutdown."""
    global _agent
    async with _get_agent_lock():
        if _agent:
            await _agent.stop()
            _agent = None


# ═══════════════════════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: ActiveUserDep,
) -> ChatResponse:
    """
    Send a message to the Copilot agent and get a response.

    The agent has access to Forge tools including:
    - Knowledge graph queries
    - Semantic search
    - Capsule creation and retrieval
    - Overlay execution
    - Governance queries

    The agent may call these tools automatically based on the user's request.

    Requires authentication.
    """
    agent = await get_agent()  # type: ignore[no-untyped-call]

    try:
        response = await agent.chat(
            message=request.message,
            metadata=request.metadata,
        )

        return ChatResponse(
            content=response.content,
            tool_calls=response.tool_calls,
            reasoning=response.reasoning,
            latency_ms=response.latency_ms,
        )

    except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
        logger.error(f"Chat request failed: {e}")
        # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details
        raise HTTPException(
            status_code=500, detail="Chat request failed. Please try again or contact support."
        )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: ActiveUserDep,
) -> StreamingResponse:
    """
    Send a message and stream the response in real-time.

    Returns a streaming response where chunks are sent as they
    are generated by the model.

    Requires authentication.
    """
    agent = await get_agent()  # type: ignore[no-untyped-call]

    async def generate() -> Any:
        try:
            async for chunk in agent.stream_chat(
                message=request.message,
                metadata=request.metadata,
            ):
                yield chunk
        except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
            logger.error(f"Stream chat failed: {e}")
            # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details
            yield "\n[Error: Stream processing failed. Please try again.]"

    return StreamingResponse(
        generate(),
        media_type="text/plain",
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(current_user: ActiveUserDep) -> HistoryResponse:
    """
    Get the current conversation history.

    Returns all messages in the current session including
    user messages, assistant responses, and tool calls.

    Requires authentication.
    """
    agent = await get_agent()  # type: ignore[no-untyped-call]

    messages = [
        HistoryMessage(
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp.isoformat(),
            tool_calls=msg.tool_calls,
        )
        for msg in agent.history
    ]

    return HistoryResponse(
        messages=messages,
        count=len(messages),
    )


@router.post("/clear")
async def clear_history(current_user: ActiveUserDep) -> dict[str, str]:
    """
    Clear the conversation history.

    Resets the agent's memory of the current conversation.

    Requires authentication.
    """
    agent = await get_agent()  # type: ignore[no-untyped-call]
    agent.clear_history()

    return {"status": "ok", "message": "History cleared"}


@router.get("/status", response_model=StatusResponse)
async def get_status(current_user: ActiveUserDep) -> StatusResponse:
    """
    Get the current status of the Copilot agent.

    Returns information about the agent's state, model,
    and session status.

    Requires authentication.
    """
    global _agent

    if _agent is None:
        return StatusResponse(
            state="stopped",
            is_running=False,
            model=None,
            session_active=False,
            history_length=0,
        )

    return StatusResponse(
        state=_agent.state.value,
        is_running=_agent.is_running,
        model=_agent.config.model,
        session_active=_agent._session is not None,
        history_length=len(_agent.history),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time chat.

    Supports bidirectional communication:
    - Client sends: {"type": "message", "content": "..."}
    - Server sends: {"type": "chunk", "content": "..."} (streaming)
    - Server sends: {"type": "complete", "content": "..."} (final)
    - Server sends: {"type": "tool_call", "name": "...", "args": {...}}
    - Server sends: {"type": "error", "message": "..."}

    Requires authentication via token query parameter or cookie.
    """
    # SECURITY FIX (Audit 6): Validate Origin header to prevent CSWSH attacks
    from forge.api.websocket.handlers import validate_websocket_origin

    if not validate_websocket_origin(websocket):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # SECURITY FIX (Audit 6 - M1): Fix WebSocket authentication
    # The previous code incorrectly called get_current_active_user(token) with a string,
    # but that function expects a User object. This fix properly validates tokens.
    user_id: str | None = None
    try:
        # 1. PREFERRED: Try to get token from httpOnly cookie (most secure)
        token = websocket.cookies.get("access_token")

        # 2. SECURE: Try Authorization header
        if not token:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        # 3. DEPRECATED: Query params (for backwards compatibility)
        if not token:
            token = websocket.query_params.get("token")
            if token:
                logger.warning(
                    "websocket_token_in_query_param: path=/copilot/ws, "
                    "warning=Token via query param is insecure. Use cookies or Authorization header."
                )

        if not token:
            await websocket.close(code=4001, reason="Authentication required")
            return

        # Validate token properly using verify_token
        payload = verify_token(token, expected_type="access")
        if not payload or not payload.sub:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

        # Check if token is blacklisted (logged out)
        jti = payload.jti
        if jti and await TokenBlacklist.is_blacklisted_async(jti):
            await websocket.close(code=4001, reason="Token has been revoked")
            return

        user_id = payload.sub

    except (ValueError, KeyError, OSError, RuntimeError) as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()
    logger.info(f"WebSocket connection established for user {user_id}")

    try:
        agent = await get_agent()  # type: ignore[no-untyped-call]

        # Register event handler for tool calls
        def on_tool_call(event):
            if event.type.value == "tool.call":
                try:
                    import asyncio

                    asyncio.create_task(
                        websocket.send_json(
                            {
                                "type": "tool_call",
                                "name": event.data.name,
                                "arguments": event.data.arguments,
                            }
                        )
                    )
                except (WebSocketDisconnect, ConnectionError, OSError, RuntimeError):
                    pass

        agent.on_event(on_tool_call)

        while True:
            # Receive message from client
            data = await websocket.receive_json()

            if data.get("type") == "message":
                content = data.get("content", "")

                if agent.config.streaming:
                    # Stream response
                    full_response = []
                    async for chunk in agent.stream_chat(content):
                        full_response.append(chunk)
                        await websocket.send_json(
                            {
                                "type": "chunk",
                                "content": chunk,
                            }
                        )

                    # Send complete message
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "content": "".join(full_response),
                        }
                    )
                else:
                    # Non-streaming response
                    response = await agent.chat(content)
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "content": response.content,
                            "tool_calls": response.tool_calls,
                        }
                    )

            elif data.get("type") == "clear":
                agent.clear_history()
                await websocket.send_json(
                    {
                        "type": "cleared",
                    }
                )

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except (ConnectionError, asyncio.CancelledError, OSError, RuntimeError) as e:
        logger.error(f"WebSocket error: {e}")
        try:
            # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "An internal error occurred. Please reconnect.",
                }
            )
        except (WebSocketDisconnect, ConnectionError, OSError, RuntimeError):
            pass
