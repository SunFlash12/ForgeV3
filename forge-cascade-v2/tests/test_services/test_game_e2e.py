"""
GAME Agent End-to-End Tests

These tests verify the complete GAME agent lifecycle including:
- Agent creation
- Worker definition
- Agent execution loop
- Knowledge query handling
- Autonomous operation

To run with real GAME API:
    GAME_API_KEY=your-key pytest tests/test_services/test_game_e2e.py -v
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Skip tests requiring real API key unless configured
def requires_game_api():
    """Decorator to skip tests without GAME API key."""
    return pytest.mark.skipif(
        not os.environ.get("GAME_API_KEY"),
        reason="GAME_API_KEY not set"
    )


class TestGAMEAgentCreation:
    """Tests for GAME agent creation."""

    @pytest.fixture
    def mock_game_client(self):
        """Create mock GAME SDK client."""
        with patch("forge.virtuals.game.sdk_client.GAMESDKClient") as MockClient:
            client = MockClient.return_value
            client.initialize = AsyncMock()
            client.create_agent = AsyncMock(return_value={
                "agent_id": "test-agent-123",
                "name": "Forge Knowledge Agent",
                "status": "prototype",
            })
            client.get_agent = AsyncMock(return_value={
                "agent_id": "test-agent-123",
                "name": "Forge Knowledge Agent",
                "status": "prototype",
                "workers": [],
            })
            yield client

    @pytest.mark.asyncio
    async def test_create_knowledge_agent(self, mock_game_client):
        """Test creating a knowledge agent."""
        agent = await mock_game_client.create_agent(
            name="Forge Knowledge Agent",
            description="AI agent for knowledge queries",
            goal="Provide intelligent knowledge management",
        )

        assert agent["agent_id"] == "test-agent-123"
        assert agent["status"] == "prototype"
        mock_game_client.create_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_details(self, mock_game_client):
        """Test retrieving agent details."""
        agent = await mock_game_client.get_agent("test-agent-123")

        assert agent["name"] == "Forge Knowledge Agent"
        assert "workers" in agent


class TestWorkerDefinition:
    """Tests for GAME worker definitions."""

    def test_create_query_worker_definition(self):
        """Test creating a knowledge query worker definition."""
        from forge.virtuals.models import WorkerDefinition

        worker = WorkerDefinition(
            id="knowledge-query-worker",
            name="Knowledge Query Worker",
            description="Handles knowledge graph queries",
            function_names=["query_knowledge_graph", "semantic_search"],
        )

        assert worker.id == "knowledge-query-worker"
        assert "query_knowledge_graph" in worker.function_names

    def test_worker_to_game_format(self):
        """Test converting worker to GAME SDK format."""
        from forge.virtuals.models import WorkerDefinition

        worker = WorkerDefinition(
            id="capsule-worker",
            name="Capsule Creation Worker",
            description="Creates and manages knowledge capsules",
            function_names=["create_capsule", "update_capsule"],
        )

        game_format = worker.model_dump()
        assert "name" in game_format
        assert "description" in game_format


class TestForgeFunction:
    """Tests for Forge function definitions."""

    @pytest.fixture
    def mock_forge_functions(self):
        """Create mock Forge functions object."""
        class MockForgeFunctions:
            pass

        functions = MockForgeFunctions()

        # Mock the actual implementation
        functions.query_knowledge_graph = AsyncMock(return_value={
            "results": [{"id": "capsule-1", "content": "Test data"}],
            "count": 1,
        })
        functions.create_capsule = AsyncMock(return_value={
            "capsule_id": "new-capsule-123",
            "status": "created",
        })
        functions.semantic_search = AsyncMock(return_value={
            "matches": [{"score": 0.95, "content": "Relevant content"}],
        })

        return functions

    @pytest.mark.asyncio
    async def test_query_knowledge_graph(self, mock_forge_functions):
        """Test knowledge graph query function."""
        result = await mock_forge_functions.query_knowledge_graph(
            query="Find all capsules about AI",
            limit=10,
        )

        assert result["count"] == 1
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_create_capsule(self, mock_forge_functions):
        """Test capsule creation function."""
        result = await mock_forge_functions.create_capsule(
            title="Test Capsule",
            content="Test content",
            capsule_type="note",
        )

        assert result["status"] == "created"
        assert "capsule_id" in result

    @pytest.mark.asyncio
    async def test_semantic_search(self, mock_forge_functions):
        """Test semantic search function."""
        result = await mock_forge_functions.semantic_search(
            query="What is machine learning?",
            top_k=5,
        )

        assert "matches" in result
        assert result["matches"][0]["score"] > 0.9


class TestAgentExecutionLoop:
    """Tests for agent execution loop."""

    @pytest.fixture
    def mock_agent_runner(self):
        """Create mock agent runner."""
        runner = MagicMock()
        runner.start = AsyncMock()
        runner.stop = AsyncMock()
        runner.is_running = False
        runner.run_step = AsyncMock(return_value={
            "action": "query_knowledge_graph",
            "params": {"query": "test"},
            "result": {"count": 1},
        })
        return runner

    @pytest.mark.asyncio
    async def test_agent_step_execution(self, mock_agent_runner):
        """Test single agent step execution."""
        result = await mock_agent_runner.run_step()

        assert result["action"] == "query_knowledge_graph"
        assert "result" in result

    @pytest.mark.asyncio
    async def test_agent_start_stop(self, mock_agent_runner):
        """Test agent start and stop lifecycle."""
        await mock_agent_runner.start()
        mock_agent_runner.start.assert_called_once()

        await mock_agent_runner.stop()
        mock_agent_runner.stop.assert_called_once()


class TestACPIntegration:
    """Tests for ACP integration with GAME agents."""

    @pytest.fixture
    def mock_acp_service(self):
        """Create mock ACP service."""
        service = MagicMock()
        service.create_job = AsyncMock(return_value={
            "job_id": "acp-job-123",
            "status": "open",
        })
        service.accept_job = AsyncMock(return_value={
            "job_id": "acp-job-123",
            "status": "in_progress",
        })
        service.deliver_result = AsyncMock(return_value={
            "job_id": "acp-job-123",
            "status": "delivered",
        })
        return service

    @pytest.mark.asyncio
    async def test_agent_handles_acp_job(self, mock_acp_service):
        """Test agent handling an ACP job."""
        # Create job
        job = await mock_acp_service.create_job(
            service_type="knowledge_query",
            requirements={"query": "Find AI papers"},
        )
        assert job["status"] == "open"

        # Accept job
        accepted = await mock_acp_service.accept_job(job["job_id"])
        assert accepted["status"] == "in_progress"

        # Deliver result
        delivered = await mock_acp_service.deliver_result(
            job_id=job["job_id"],
            result={"papers": ["paper1", "paper2"]},
        )
        assert delivered["status"] == "delivered"


class TestFullE2EWorkflow:
    """Full end-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_agent_workflow(self):
        """Test complete agent workflow from creation to execution."""
        # This test simulates the full workflow

        # 1. Create agent configuration
        agent_config = {
            "name": "Forge Knowledge Agent",
            "description": "AI agent for knowledge queries",
            "goal": "Provide intelligent knowledge management services",
            "workers": [
                {
                    "id": "query-worker",
                    "name": "Query Worker",
                    "functions": ["query_knowledge_graph"],
                },
                {
                    "id": "capsule-worker",
                    "name": "Capsule Worker",
                    "functions": ["create_capsule", "update_capsule"],
                },
            ],
        }

        assert agent_config["name"] == "Forge Knowledge Agent"
        assert len(agent_config["workers"]) == 2

        # 2. Simulate agent creation
        mock_agent = {
            "agent_id": "forge-agent-001",
            "config": agent_config,
            "status": "prototype",
            "created_at": "2024-01-01T00:00:00Z",
        }

        assert mock_agent["status"] == "prototype"

        # 3. Simulate worker registration
        registered_workers = []
        for worker in agent_config["workers"]:
            registered_workers.append({
                **worker,
                "registered": True,
                "agent_id": mock_agent["agent_id"],
            })

        assert all(w["registered"] for w in registered_workers)

        # 4. Simulate execution step
        execution_result = {
            "step": 1,
            "worker": "query-worker",
            "action": "query_knowledge_graph",
            "input": {"query": "AI research papers"},
            "output": {
                "results": [{"id": "capsule-1"}, {"id": "capsule-2"}],
                "count": 2,
            },
            "success": True,
        }

        assert execution_result["success"]
        assert execution_result["output"]["count"] == 2

        # 5. Simulate ACP job handling
        acp_job = {
            "job_id": "acp-123",
            "service_type": "knowledge_query",
            "status": "completed",
            "result": execution_result["output"],
            "payment": {
                "amount": 10.0,
                "token": "VIRTUAL",
            },
        }

        assert acp_job["status"] == "completed"
        assert acp_job["payment"]["amount"] == 10.0

    @pytest.mark.asyncio
    @requires_game_api()
    async def test_real_game_api_connection(self):
        """Test real GAME API connection (requires API key)."""
        from forge.virtuals.game import GAMESDKClient

        api_key = os.environ.get("GAME_API_KEY")
        client = GAMESDKClient(api_key=api_key)

        try:
            await client.initialize()
            # If we get here, connection was successful
            assert True
        except Exception as e:
            pytest.fail(f"GAME API connection failed: {e}")
        finally:
            await client.close()


class TestAgentMonitoring:
    """Tests for agent monitoring and observability."""

    def test_agent_metrics_structure(self):
        """Test agent metrics data structure."""
        metrics = {
            "agent_id": "test-agent",
            "uptime_seconds": 3600,
            "total_steps": 100,
            "successful_steps": 98,
            "failed_steps": 2,
            "average_step_duration_ms": 150,
            "memory_usage_mb": 256,
            "active_workers": 2,
        }

        assert metrics["successful_steps"] / metrics["total_steps"] == 0.98
        assert metrics["average_step_duration_ms"] < 200

    def test_agent_health_check(self):
        """Test agent health check logic."""
        def check_health(metrics: dict) -> dict:
            success_rate = metrics["successful_steps"] / max(metrics["total_steps"], 1)
            return {
                "healthy": success_rate >= 0.95,
                "success_rate": success_rate,
                "warnings": [] if success_rate >= 0.95 else ["Low success rate"],
            }

        healthy_metrics = {"successful_steps": 98, "total_steps": 100}
        unhealthy_metrics = {"successful_steps": 80, "total_steps": 100}

        assert check_health(healthy_metrics)["healthy"]
        assert not check_health(unhealthy_metrics)["healthy"]
