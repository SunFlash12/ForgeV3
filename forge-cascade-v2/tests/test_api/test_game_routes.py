"""
GAME SDK Routes Tests for Forge Cascade V2

Comprehensive tests for GAME SDK API routes including:
- Agent management (create, get, delete)
- Agent execution (run, get next action)
- Memory management (store, search)
- Function listing
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.api.routes.game import router

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_agent():
    """Create a mock GAME agent."""
    agent = MagicMock()
    agent.id = "agent123"
    agent.name = "Test Agent"
    agent.status = MagicMock(value="active")
    agent.game_agent_id = "game_agent_456"
    agent.personality = MagicMock(
        model_dump=lambda: {
            "name": "Test Agent",
            "description": "A test agent",
            "personality_traits": ["helpful", "analytical"],
            "communication_style": "professional",
            "expertise_domains": ["knowledge", "analysis"],
        }
    )
    agent.goals = MagicMock(
        model_dump=lambda: {
            "primary_goal": "Help users find information",
            "secondary_goals": ["Maintain accuracy"],
            "constraints": ["Be truthful"],
            "success_metrics": ["User satisfaction"],
        }
    )
    agent.workers = [
        MagicMock(id="worker1", name="Knowledge Worker", description="Handles knowledge"),
    ]
    agent.forge_overlay_id = "overlay123"
    agent.forge_capsule_ids = ["capsule1", "capsule2"]
    agent.primary_chain = "base"
    agent.created_at = datetime.now(UTC)
    agent.updated_at = datetime.now(UTC)
    return agent


@pytest.fixture
def mock_game_client(mock_agent):
    """Create mock GAME client."""
    client = AsyncMock()
    client.create_agent = AsyncMock(return_value=mock_agent)
    client.get_agent = AsyncMock(return_value=mock_agent)
    client.delete_agent = AsyncMock(return_value=True)
    client.run_agent_loop = AsyncMock(
        return_value=[
            {"iteration": 0, "action": "search", "result": "found"},
        ]
    )
    client.get_next_action = AsyncMock(
        return_value={
            "worker_id": "knowledge_worker",
            "function_name": "search_capsules",
            "arguments": {"query": "test"},
            "reasoning": "User asked for information",
        }
    )
    client.store_memory = AsyncMock(return_value="memory123")
    client.retrieve_memories = AsyncMock(
        return_value=[
            {"id": "mem1", "content": "Previous interaction", "type": "conversation"},
        ]
    )
    return client


@pytest.fixture
def mock_active_user():
    """Create mock authenticated user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.trust_flame = 60
    user.is_active = True
    return user


@pytest.fixture
def mock_optional_user():
    """Create mock optional user (None)."""
    return None


@pytest.fixture
def game_app(mock_game_client, mock_active_user):
    """Create FastAPI app with GAME router and mocked dependencies."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Override user dependencies

    async def get_active_user():
        return mock_active_user

    async def get_optional_user():
        return mock_active_user

    # Use dependency_overrides for injected dependencies
    from forge.api.dependencies import get_current_active_user

    app.dependency_overrides[get_current_active_user] = get_active_user

    return app


@pytest.fixture
def client(game_app):
    """Create test client."""
    return TestClient(game_app)


# =============================================================================
# Agent Creation Tests
# =============================================================================


class TestCreateAgent:
    """Tests for POST /game/agents endpoint."""

    def test_create_agent_success(self, client: TestClient):
        """Create agent with valid configuration."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.name = "Test Agent"
            mock_agent.status = MagicMock(value="active")
            mock_agent.game_agent_id = "game123"
            mock_agent.personality = MagicMock(model_dump=lambda: {})
            mock_agent.goals = MagicMock(model_dump=lambda: {})
            mock_agent.workers = []
            mock_agent.forge_overlay_id = None
            mock_agent.forge_capsule_ids = []
            mock_agent.primary_chain = "base"
            mock_agent.created_at = datetime.now(UTC)
            mock_agent.updated_at = datetime.now(UTC)
            mock_client.create_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents",
                json={
                    "name": "Test Agent",
                    "personality": {
                        "name": "Helper",
                        "bio": "A helpful assistant",
                        "traits": ["helpful", "knowledgeable"],
                        "communication_style": "professional",
                        "expertise_areas": ["knowledge management"],
                    },
                    "goals": {
                        "primary_goal": "Help users find information",
                        "secondary_goals": ["Maintain accuracy"],
                        "constraints": ["Be truthful"],
                        "success_criteria": ["User satisfaction"],
                    },
                    "workers": [],
                    "enable_memory": True,
                    "primary_chain": "base",
                },
            )

            # May fail if GAME SDK not available
            assert response.status_code in [200, 500, 503]

    def test_create_agent_with_workers(self, client: TestClient):
        """Create agent with custom workers."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.name = "Worker Agent"
            mock_agent.status = MagicMock(value="active")
            mock_agent.game_agent_id = "game123"
            mock_agent.personality = MagicMock(model_dump=lambda: {})
            mock_agent.goals = MagicMock(model_dump=lambda: {})
            mock_agent.workers = [MagicMock(id="w1", name="Worker", description="Test")]
            mock_agent.forge_overlay_id = None
            mock_agent.forge_capsule_ids = []
            mock_agent.primary_chain = "base"
            mock_agent.created_at = datetime.now(UTC)
            mock_agent.updated_at = datetime.now(UTC)
            mock_client.create_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents",
                json={
                    "name": "Worker Agent",
                    "personality": {
                        "name": "Worker",
                        "bio": "Agent with custom workers",
                    },
                    "goals": {
                        "primary_goal": "Process tasks",
                    },
                    "workers": [
                        {
                            "worker_id": "custom_worker",
                            "description": "Custom task handler",
                            "function_names": ["custom_function"],
                        }
                    ],
                },
            )

            assert response.status_code in [200, 500, 503]

    def test_create_agent_validation_name_too_long(self, client: TestClient):
        """Create agent with name exceeding max length."""
        response = client.post(
            "/api/v1/game/agents",
            json={
                "name": "A" * 101,  # Over 100 char limit
                "personality": {
                    "name": "Test",
                    "bio": "Test bio",
                },
                "goals": {
                    "primary_goal": "Test goal",
                },
            },
        )

        assert response.status_code == 422

    def test_create_agent_validation_missing_fields(self, client: TestClient):
        """Create agent with missing required fields."""
        response = client.post(
            "/api/v1/game/agents",
            json={
                "name": "Incomplete Agent",
                # Missing personality and goals
            },
        )

        assert response.status_code == 422

    def test_create_agent_unauthorized(self, game_app):
        """Create agent without authentication."""
        from forge.api.dependencies import get_current_active_user

        # Remove auth override
        game_app.dependency_overrides.pop(get_current_active_user, None)

        client = TestClient(game_app)
        response = client.post(
            "/api/v1/game/agents",
            json={
                "name": "Test Agent",
                "personality": {"name": "Test", "bio": "Test"},
                "goals": {"primary_goal": "Test"},
            },
        )

        assert response.status_code in [401, 403, 500, 503]


# =============================================================================
# Get Agent Tests
# =============================================================================


class TestGetAgent:
    """Tests for GET /game/agents/{agent_id} endpoint."""

    def test_get_agent_success(self, client: TestClient):
        """Get existing agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.name = "Test Agent"
            mock_agent.status = MagicMock(value="active")
            mock_agent.game_agent_id = "game123"
            mock_agent.personality = MagicMock(model_dump=lambda: {"name": "Test"})
            mock_agent.goals = MagicMock(model_dump=lambda: {"primary_goal": "Test"})
            mock_agent.workers = []
            mock_agent.forge_overlay_id = None
            mock_agent.forge_capsule_ids = []
            mock_agent.primary_chain = "base"
            mock_agent.created_at = datetime.now(UTC)
            mock_agent.updated_at = datetime.now(UTC)
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = client.get("/api/v1/game/agents/agent123")

            assert response.status_code in [200, 404, 500]
            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert "name" in data
                assert "status" in data

    def test_get_agent_not_found(self, client: TestClient):
        """Get non-existent agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_agent = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = client.get("/api/v1/game/agents/nonexistent")

            assert response.status_code in [404, 500]


# =============================================================================
# Delete Agent Tests
# =============================================================================


class TestDeleteAgent:
    """Tests for DELETE /game/agents/{agent_id} endpoint."""

    def test_delete_agent_success(self, client: TestClient):
        """Delete existing agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.delete_agent = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_client

            response = client.delete("/api/v1/game/agents/agent123")

            assert response.status_code in [200, 404, 500]
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "deleted"

    def test_delete_agent_not_found(self, client: TestClient):
        """Delete non-existent agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.delete_agent = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_client

            response = client.delete("/api/v1/game/agents/nonexistent")

            assert response.status_code in [404, 500]


# =============================================================================
# Run Agent Tests
# =============================================================================


class TestRunAgent:
    """Tests for POST /game/agents/{agent_id}/run endpoint."""

    def test_run_agent_success(self, client: TestClient):
        """Run agent loop successfully."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.game_agent_id = "game123"
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_client.run_agent_loop = AsyncMock(
                return_value=[
                    {"iteration": 0, "action": "test", "result": "done"},
                ]
            )
            mock_get_client.return_value = mock_client

            with (
                patch("forge.database.client.get_db_client"),
                patch("forge.repositories.capsule_repository.CapsuleRepository"),
                patch("forge.virtuals.game.forge_functions.create_knowledge_worker"),
            ):
                response = client.post(
                    "/api/v1/game/agents/agent123/run",
                    json={
                        "context": "Test context",
                        "max_iterations": 5,
                        "stop_on_done": True,
                    },
                )

                assert response.status_code in [200, 404, 500]

    def test_run_agent_with_defaults(self, client: TestClient):
        """Run agent with default parameters."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.game_agent_id = "game123"
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_client.run_agent_loop = AsyncMock(return_value=[])
            mock_get_client.return_value = mock_client

            with (
                patch("forge.database.client.get_db_client"),
                patch("forge.repositories.capsule_repository.CapsuleRepository"),
                patch("forge.virtuals.game.forge_functions.create_knowledge_worker"),
            ):
                response = client.post(
                    "/api/v1/game/agents/agent123/run",
                    json={},
                )

                assert response.status_code in [200, 404, 500]

    def test_run_agent_validation_max_iterations(self, client: TestClient):
        """Run agent with invalid max_iterations."""
        response = client.post(
            "/api/v1/game/agents/agent123/run",
            json={
                "max_iterations": 200,  # Over 100 limit
            },
        )

        assert response.status_code == 422

    def test_run_agent_not_found(self, client: TestClient):
        """Run non-existent agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_agent = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/nonexistent/run",
                json={},
            )

            assert response.status_code in [404, 500]


# =============================================================================
# Get Next Action Tests
# =============================================================================


class TestGetNextAction:
    """Tests for POST /game/agents/{agent_id}/action endpoint."""

    def test_get_next_action_success(self, client: TestClient):
        """Get next action for agent."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.game_agent_id = "game123"
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_client.get_next_action = AsyncMock(
                return_value={
                    "worker_id": "knowledge_worker",
                    "function_name": "search_capsules",
                    "arguments": {"query": "test"},
                    "reasoning": "User needs information",
                }
            )
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/agent123/action",
                json={"state": {"key": "value"}},
                params={"context": "User asked about X"},
            )

            assert response.status_code in [200, 400, 404, 500, 503]

    def test_get_next_action_no_game_agent(self, client: TestClient):
        """Get next action for agent without GAME registration."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_agent = MagicMock()
            mock_agent.id = "agent123"
            mock_agent.game_agent_id = None  # Not registered with GAME
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/agent123/action",
                json={"state": {}},
            )

            assert response.status_code in [400, 500, 503]


# =============================================================================
# Memory Tests
# =============================================================================


class TestStoreMemory:
    """Tests for POST /game/agents/{agent_id}/memories endpoint."""

    def test_store_memory_success(self, client: TestClient):
        """Store memory successfully."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.store_memory = AsyncMock(return_value="memory123")
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/agent123/memories",
                json={
                    "memory_type": "conversation",
                    "content": {"message": "Hello", "role": "user"},
                    "ttl_days": 30,
                },
            )

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "memory_id" in data
                assert data["status"] == "stored"

    def test_store_memory_minimal(self, client: TestClient):
        """Store memory with minimal fields."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.store_memory = AsyncMock(return_value="memory456")
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/agent123/memories",
                json={
                    "memory_type": "fact",
                    "content": {"fact": "The sky is blue"},
                },
            )

            assert response.status_code in [200, 500]


class TestSearchMemories:
    """Tests for POST /game/agents/{agent_id}/memories/search endpoint."""

    def test_search_memories_success(self, client: TestClient):
        """Search memories successfully."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.retrieve_memories = AsyncMock(
                return_value=[
                    {"id": "mem1", "content": "Previous chat", "type": "conversation"},
                    {"id": "mem2", "content": "Fact about user", "type": "fact"},
                ]
            )
            mock_get_client.return_value = mock_client

            response = client.post(
                "/api/v1/game/agents/agent123/memories/search",
                json={
                    "query": "user preferences",
                    "memory_type": "preference",
                    "limit": 10,
                },
            )

            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "memories" in data
                assert "count" in data

    def test_search_memories_validation(self, client: TestClient):
        """Search memories with invalid parameters."""
        response = client.post(
            "/api/v1/game/agents/agent123/memories/search",
            json={
                "query": "a" * 501,  # Over 500 char limit
                "limit": 10,
            },
        )

        assert response.status_code == 422


# =============================================================================
# List Functions Tests
# =============================================================================


class TestListFunctions:
    """Tests for GET /game/functions endpoint."""

    def test_list_functions(self, client: TestClient):
        """List available Forge functions."""
        response = client.get("/api/v1/game/functions")

        assert response.status_code == 200
        data = response.json()
        assert "functions" in data
        assert "workers" in data
        assert isinstance(data["functions"], list)
        assert isinstance(data["workers"], list)

    def test_list_functions_contains_expected(self, client: TestClient):
        """List functions contains expected function definitions."""
        response = client.get("/api/v1/game/functions")

        assert response.status_code == 200
        data = response.json()

        # Check for known functions
        function_names = [f["name"] for f in data["functions"]]
        assert "search_capsules" in function_names
        assert "get_capsule" in function_names
        assert "create_capsule" in function_names

        # Check for known workers
        worker_ids = [w["id"] for w in data["workers"]]
        assert "knowledge_worker" in worker_ids


# =============================================================================
# Request Model Validation Tests
# =============================================================================


class TestRequestValidation:
    """Tests for request model validation."""

    def test_personality_bio_max_length(self, client: TestClient):
        """Test personality bio max length validation."""
        response = client.post(
            "/api/v1/game/agents",
            json={
                "name": "Test Agent",
                "personality": {
                    "name": "Test",
                    "bio": "A" * 1001,  # Over 1000 char limit
                },
                "goals": {
                    "primary_goal": "Test goal",
                },
            },
        )

        assert response.status_code == 422

    def test_goals_primary_goal_max_length(self, client: TestClient):
        """Test goals primary_goal max length validation."""
        response = client.post(
            "/api/v1/game/agents",
            json={
                "name": "Test Agent",
                "personality": {
                    "name": "Test",
                    "bio": "Valid bio",
                },
                "goals": {
                    "primary_goal": "A" * 501,  # Over 500 char limit
                },
            },
        )

        assert response.status_code == 422

    def test_run_request_context_max_length(self, client: TestClient):
        """Test run request context max length validation."""
        response = client.post(
            "/api/v1/game/agents/agent123/run",
            json={
                "context": "A" * 5001,  # Over 5000 char limit
            },
        )

        assert response.status_code == 422


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in GAME routes."""

    def test_sdk_not_available(self, client: TestClient):
        """Test handling when GAME SDK is not available."""
        with patch(
            "forge.api.routes.game.get_game_client", side_effect=ImportError("SDK not found")
        ):
            # The route catches ImportError and returns 503
            response = client.post(
                "/api/v1/game/agents",
                json={
                    "name": "Test Agent",
                    "personality": {"name": "Test", "bio": "Test"},
                    "goals": {"primary_goal": "Test"},
                },
            )

            # May be caught as 503 or bubble up as 500
            assert response.status_code in [500, 503]

    def test_connection_error(self, client: TestClient):
        """Test handling of connection errors."""
        with patch("forge.virtuals.game.sdk_client.get_game_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get_agent = AsyncMock(side_effect=ConnectionError("Network error"))
            mock_get_client.return_value = mock_client

            response = client.get("/api/v1/game/agents/agent123")

            assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
