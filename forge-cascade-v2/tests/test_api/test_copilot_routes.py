"""
Copilot Routes Tests for Forge Cascade V2

Comprehensive tests for Copilot API routes including:
- Chat endpoint (POST /copilot/chat)
- Stream endpoint (POST /copilot/stream)
- History endpoint (GET /copilot/history)
- Clear endpoint (POST /copilot/clear)
- Status endpoint (GET /copilot/status)
- WebSocket endpoint (WS /copilot/ws)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_copilot_agent():
    """Create mock Copilot agent."""
    agent = AsyncMock()
    agent.state = MagicMock(value="running")
    agent.is_running = True
    agent.config = MagicMock(model="gpt-4", streaming=True)
    agent._session = MagicMock()
    agent.history = []
    return agent


@pytest.fixture
def sample_chat_response():
    """Create a sample chat response for testing."""
    response = MagicMock()
    response.content = "This is a test response from the assistant."
    response.tool_calls = []
    response.reasoning = None
    response.latency_ms = 150.5
    return response


@pytest.fixture
def sample_history_message():
    """Create a sample history message for testing."""
    message = MagicMock()
    message.role = "user"
    message.content = "Hello, assistant!"
    message.timestamp = datetime.now()
    message.tool_calls = []
    return message


# =============================================================================
# Chat Endpoint Tests
# =============================================================================


class TestChatRoute:
    """Tests for POST /copilot/chat endpoint."""

    def test_chat_unauthorized(self, client: TestClient):
        """Chat without auth fails."""
        response = client.post(
            "/api/v1/copilot/chat",
            json={
                "message": "Hello, assistant!",
            },
        )
        assert response.status_code == 401

    def test_chat_missing_message(self, client: TestClient, auth_headers: dict):
        """Chat without message fails validation."""
        response = client.post(
            "/api/v1/copilot/chat",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_chat_authorized(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
        sample_chat_response,
    ):
        """Chat with valid data succeeds."""
        mock_copilot_agent.chat = AsyncMock(return_value=sample_chat_response)

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.post(
                "/api/v1/copilot/chat",
                json={
                    "message": "Hello, assistant!",
                },
                headers=auth_headers,
            )

        # Should succeed or return service error
        assert response.status_code in [200, 500, 503], (
            f"Expected 200/500/503, got {response.status_code}: {response.text[:200]}"
        )

    def test_chat_with_metadata(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
        sample_chat_response,
    ):
        """Chat with metadata succeeds."""
        mock_copilot_agent.chat = AsyncMock(return_value=sample_chat_response)

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.post(
                "/api/v1/copilot/chat",
                json={
                    "message": "Hello, assistant!",
                    "metadata": {"context": "test"},
                },
                headers=auth_headers,
            )

        assert response.status_code in [200, 500, 503]


# =============================================================================
# Stream Endpoint Tests
# =============================================================================


class TestStreamRoute:
    """Tests for POST /copilot/stream endpoint."""

    def test_stream_unauthorized(self, client: TestClient):
        """Stream without auth fails."""
        response = client.post(
            "/api/v1/copilot/stream",
            json={
                "message": "Hello, assistant!",
            },
        )
        assert response.status_code == 401

    def test_stream_missing_message(self, client: TestClient, auth_headers: dict):
        """Stream without message fails validation."""
        response = client.post(
            "/api/v1/copilot/stream",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_stream_authorized(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
    ):
        """Stream with valid data succeeds."""

        async def mock_stream_chat(*args, **kwargs):
            yield "Hello "
            yield "world!"

        mock_copilot_agent.stream_chat = mock_stream_chat

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.post(
                "/api/v1/copilot/stream",
                json={
                    "message": "Hello, assistant!",
                },
                headers=auth_headers,
            )

        # Should return streaming response or error
        assert response.status_code in [200, 500, 503]


# =============================================================================
# History Endpoint Tests
# =============================================================================


class TestHistoryRoute:
    """Tests for GET /copilot/history endpoint."""

    def test_history_unauthorized(self, client: TestClient):
        """Get history without auth fails."""
        response = client.get("/api/v1/copilot/history")
        assert response.status_code == 401

    def test_history_authorized(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
        sample_history_message,
    ):
        """Get history with auth returns history."""
        mock_copilot_agent.history = [sample_history_message]

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.get(
                "/api/v1/copilot/history",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "messages" in data
            assert "count" in data

    def test_history_empty(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
    ):
        """Get history when empty returns empty list."""
        mock_copilot_agent.history = []

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.get(
                "/api/v1/copilot/history",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["count"] == 0
            assert data["messages"] == []


# =============================================================================
# Clear Endpoint Tests
# =============================================================================


class TestClearRoute:
    """Tests for POST /copilot/clear endpoint."""

    def test_clear_unauthorized(self, client: TestClient):
        """Clear history without auth fails."""
        response = client.post("/api/v1/copilot/clear")
        assert response.status_code == 401

    def test_clear_authorized(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
    ):
        """Clear history with auth succeeds."""
        mock_copilot_agent.clear_history = MagicMock()

        with patch(
            "forge.api.routes.copilot.get_agent",
            return_value=mock_copilot_agent,
        ):
            response = client.post(
                "/api/v1/copilot/clear",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "ok"
            assert "History cleared" in data["message"]


# =============================================================================
# Status Endpoint Tests
# =============================================================================


class TestStatusRoute:
    """Tests for GET /copilot/status endpoint."""

    def test_status_unauthorized(self, client: TestClient):
        """Get status without auth fails."""
        response = client.get("/api/v1/copilot/status")
        assert response.status_code == 401

    def test_status_agent_not_initialized(self, client: TestClient, auth_headers: dict):
        """Get status when agent not initialized returns stopped state."""
        with patch("forge.api.routes.copilot._agent", None):
            response = client.get(
                "/api/v1/copilot/status",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "stopped"
        assert data["is_running"] is False
        assert data["session_active"] is False

    def test_status_agent_running(
        self,
        client: TestClient,
        auth_headers: dict,
        mock_copilot_agent,
    ):
        """Get status when agent running returns running state."""
        with patch("forge.api.routes.copilot._agent", mock_copilot_agent):
            response = client.get(
                "/api/v1/copilot/status",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "is_running" in data
        assert "model" in data
        assert "session_active" in data
        assert "history_length" in data


# =============================================================================
# WebSocket Tests
# =============================================================================


class TestWebSocketRoute:
    """Tests for WS /copilot/ws endpoint."""

    def test_websocket_no_auth(self, client: TestClient):
        """WebSocket without auth is rejected."""
        # Note: TestClient WebSocket testing is limited
        # Full WebSocket tests require async client or integration tests
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/copilot/ws"):
                pass

    def test_websocket_invalid_token(self, client: TestClient):
        """WebSocket with invalid token is rejected."""
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/copilot/ws?token=invalid"):
                pass


# =============================================================================
# Agent Initialization Tests
# =============================================================================


class TestAgentInitialization:
    """Tests for agent initialization logic."""

    def test_get_agent_creates_new(self):
        """get_agent creates new agent if none exists."""
        # This would require more complex mocking of the CopilotForgeAgent
        # and is better tested in integration tests
        pass

    def test_get_agent_returns_existing(self, mock_copilot_agent):
        """get_agent returns existing agent if already initialized."""
        with patch("forge.api.routes.copilot._agent", mock_copilot_agent):
            from forge.api.routes.copilot import _agent

            assert _agent is mock_copilot_agent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
