"""
Copilot Integration Tests

Tests for the GitHub Copilot SDK integration with Forge.
These tests use mocks since the actual Copilot SDK requires
a GitHub Copilot subscription and CLI installation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCopilotConfig:
    """Tests for CopilotConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        from forge.copilot.agent import CopilotConfig

        config = CopilotConfig()

        assert config.model == "gpt-5"
        assert config.streaming is True
        assert config.use_stdio is True
        assert config.auto_restart is True
        assert config.timeout_seconds == 120

    def test_custom_config(self):
        """Test custom configuration."""
        from forge.copilot.agent import CopilotConfig

        config = CopilotConfig(
            model="gpt-4-turbo",
            streaming=False,
            system_prompt="Custom system prompt",
            timeout_seconds=60,
        )

        assert config.model == "gpt-4-turbo"
        assert config.streaming is False
        assert config.system_prompt == "Custom system prompt"
        assert config.timeout_seconds == 60


class TestForgeToolRegistry:
    """Tests for ForgeToolRegistry."""

    @pytest.fixture
    def tool_registry(self):
        """Create a tool registry instance."""
        from forge.copilot.tools import ForgeToolRegistry

        return ForgeToolRegistry()

    @pytest.mark.asyncio
    async def test_initialize(self, tool_registry):
        """Test registry initialization."""
        mock_db = MagicMock()
        mock_search = MagicMock()

        await tool_registry.initialize(
            db_client=mock_db,
            search_service=mock_search,
        )

        assert tool_registry._initialized is True
        assert tool_registry._db_client == mock_db
        assert tool_registry._search_service == mock_search

    def test_get_copilot_tools_without_sdk(self, tool_registry):
        """Test getting tools when SDK is not installed."""
        # The method should return empty list if SDK not installed
        tools = tool_registry.get_copilot_tools()
        # Will return empty list since copilot SDK isn't installed
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_handle_knowledge_query_no_client(self, tool_registry):
        """Test knowledge query without initialized client."""
        result = await tool_registry._handle_knowledge_query(
            {"arguments": {"query": "test", "limit": 10}}
        )

        assert result["resultType"] == "error"
        assert "not initialized" in result["textResultForLlm"]

    @pytest.mark.asyncio
    async def test_handle_semantic_search_no_service(self, tool_registry):
        """Test semantic search without initialized service."""
        result = await tool_registry._handle_semantic_search(
            {"arguments": {"query": "test", "top_k": 5, "threshold": 0.7}}
        )

        assert result["resultType"] == "error"
        assert "not initialized" in result["textResultForLlm"]

    @pytest.mark.asyncio
    async def test_handle_governance_query(self, tool_registry):
        """Test governance query (doesn't require services)."""
        result = await tool_registry._handle_governance_query(
            {"arguments": {"query_type": "proposals", "status": None}}
        )

        assert result["resultType"] == "success"
        assert "governance" in result["sessionLog"].lower()


class TestToolParameterModels:
    """Tests for tool parameter validation."""

    def test_knowledge_query_params_valid(self):
        """Test valid knowledge query parameters."""
        from forge.copilot.tools import KnowledgeQueryParams

        params = KnowledgeQueryParams(
            query="Find AI capsules",
            limit=20,
        )

        assert params.query == "Find AI capsules"
        assert params.limit == 20
        assert params.filters is None

    def test_knowledge_query_params_limit_bounds(self):
        """Test limit bounds validation."""
        from forge.copilot.tools import KnowledgeQueryParams

        # Valid limits
        params_min = KnowledgeQueryParams(query="test", limit=1)
        assert params_min.limit == 1

        params_max = KnowledgeQueryParams(query="test", limit=100)
        assert params_max.limit == 100

        # Invalid limits should raise
        with pytest.raises(ValueError):
            KnowledgeQueryParams(query="test", limit=0)

        with pytest.raises(ValueError):
            KnowledgeQueryParams(query="test", limit=101)

    def test_semantic_search_params(self):
        """Test semantic search parameters."""
        from forge.copilot.tools import SemanticSearchParams

        params = SemanticSearchParams(
            query="machine learning",
            top_k=10,
            threshold=0.8,
            capsule_types=["note", "document"],
        )

        assert params.query == "machine learning"
        assert params.top_k == 10
        assert params.threshold == 0.8
        assert params.capsule_types == ["note", "document"]

    def test_create_capsule_params(self):
        """Test capsule creation parameters."""
        from forge.copilot.tools import CreateCapsuleParams

        params = CreateCapsuleParams(
            title="Test Capsule",
            content="Test content",
            capsule_type="note",
            tags=["test", "example"],
        )

        assert params.title == "Test Capsule"
        assert params.content == "Test content"
        assert params.capsule_type == "note"
        assert params.tags == ["test", "example"]


class TestCopilotForgeAgent:
    """Tests for CopilotForgeAgent."""

    @pytest.fixture
    def mock_copilot_sdk(self):
        """Mock the Copilot SDK."""
        with patch.dict("sys.modules", {"copilot": MagicMock()}):
            yield

    def test_agent_initial_state(self):
        """Test agent initial state."""
        from forge.copilot.agent import AgentState, CopilotForgeAgent

        agent = CopilotForgeAgent()

        assert agent.state == AgentState.STOPPED
        assert agent.is_running is False
        assert agent.history == []

    def test_agent_with_config(self):
        """Test agent with custom config."""
        from forge.copilot.agent import CopilotConfig, CopilotForgeAgent

        config = CopilotConfig(
            model="custom-model",
            streaming=False,
        )
        agent = CopilotForgeAgent(config=config)

        assert agent.config.model == "custom-model"
        assert agent.config.streaming is False

    def test_default_system_prompt(self):
        """Test that default system prompt is set."""
        from forge.copilot.agent import CopilotForgeAgent

        agent = CopilotForgeAgent()

        assert "Forge" in agent.DEFAULT_SYSTEM_PROMPT
        assert "knowledge" in agent.DEFAULT_SYSTEM_PROMPT.lower()

    @pytest.mark.asyncio
    async def test_chat_not_running_raises(self):
        """Test that chat raises when agent is not running."""
        from forge.copilot.agent import CopilotForgeAgent

        agent = CopilotForgeAgent()

        with pytest.raises(RuntimeError, match="not running"):
            await agent.chat("Hello")

    @pytest.mark.asyncio
    async def test_stream_chat_not_running_raises(self):
        """Test that stream_chat raises when agent is not running."""
        from forge.copilot.agent import CopilotForgeAgent

        agent = CopilotForgeAgent()

        with pytest.raises(RuntimeError, match="not running"):
            async for _ in agent.stream_chat("Hello"):
                pass

    def test_clear_history(self):
        """Test clearing conversation history."""
        from forge.copilot.agent import ChatMessage, CopilotForgeAgent

        agent = CopilotForgeAgent()
        agent._history.append(ChatMessage(role="user", content="test"))

        assert len(agent.history) == 1

        agent.clear_history()

        assert len(agent.history) == 0

    def test_event_handler_registration(self):
        """Test registering event handlers."""
        from forge.copilot.agent import CopilotForgeAgent

        agent = CopilotForgeAgent()

        def handler(event):
            pass

        agent.on_event(handler)

        assert handler in agent._event_handlers


class TestCopilotForgeAgentPool:
    """Tests for CopilotForgeAgentPool."""

    def test_pool_initialization(self):
        """Test pool configuration."""
        from forge.copilot.agent import CopilotConfig, CopilotForgeAgentPool

        config = CopilotConfig(model="test-model")
        pool = CopilotForgeAgentPool(
            config=config,
            min_agents=2,
            max_agents=10,
        )

        assert pool.config.model == "test-model"
        assert pool._min_agents == 2
        assert pool._max_agents == 10
        assert pool._initialized is False

    @pytest.mark.asyncio
    async def test_pool_acquire_not_initialized(self):
        """Test acquiring from uninitialized pool raises."""
        from forge.copilot.agent import CopilotForgeAgentPool

        pool = CopilotForgeAgentPool()

        with pytest.raises(RuntimeError, match="not initialized"):
            await pool.acquire()


class TestChatModels:
    """Tests for chat data models."""

    def test_chat_message(self):
        """Test ChatMessage model."""
        from forge.copilot.agent import ChatMessage

        msg = ChatMessage(
            role="user",
            content="Hello",
        )

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert msg.tool_calls == []

    def test_chat_response(self):
        """Test ChatResponse model."""
        from forge.copilot.agent import ChatResponse

        response = ChatResponse(
            content="Hi there!",
            tool_calls=[{"name": "test_tool"}],
            reasoning="Thinking...",
            latency_ms=150.5,
        )

        assert response.content == "Hi there!"
        assert len(response.tool_calls) == 1
        assert response.reasoning == "Thinking..."
        assert response.latency_ms == 150.5


class TestFormattingHelpers:
    """Tests for result formatting helpers."""

    @pytest.fixture
    def tool_registry(self):
        """Create a tool registry instance."""
        from forge.copilot.tools import ForgeToolRegistry

        return ForgeToolRegistry()

    def test_format_capsule_results_empty(self, tool_registry):
        """Test formatting empty results."""
        result = tool_registry._format_capsule_results([])
        assert "No capsules found" in result

    def test_format_capsule_results_with_data(self, tool_registry):
        """Test formatting capsule results."""
        results = [
            {"id": "cap-1", "title": "Test 1", "type": "note", "content": "Content 1"},
            {"id": "cap-2", "title": "Test 2", "type": "document", "content": "Content 2"},
        ]

        formatted = tool_registry._format_capsule_results(results)

        assert "Found 2 capsules" in formatted
        assert "Test 1" in formatted
        assert "Test 2" in formatted
        assert "[note]" in formatted
        assert "[document]" in formatted

    def test_format_search_results_empty(self, tool_registry):
        """Test formatting empty search results."""
        result = tool_registry._format_search_results([])
        assert "No semantically similar" in result

    def test_format_search_results_with_data(self, tool_registry):
        """Test formatting search results."""
        results = [
            {"title": "Match 1", "score": 0.95, "snippet": "First match snippet"},
            {"title": "Match 2", "score": 0.88, "snippet": "Second match snippet"},
        ]

        formatted = tool_registry._format_search_results(results)

        assert "Semantic search results" in formatted
        assert "Match 1" in formatted
        assert "0.95" in formatted
        assert "Match 2" in formatted

    def test_format_overlays_empty(self, tool_registry):
        """Test formatting empty overlay list."""
        result = tool_registry._format_overlays([])
        assert "No overlays available" in result

    def test_format_overlays_with_data(self, tool_registry):
        """Test formatting overlay list."""
        overlays = [
            {"id": "ov-1", "name": "Summarizer", "description": "Summarizes content"},
            {"id": "ov-2", "name": "Analyzer", "description": "Analyzes data"},
        ]

        formatted = tool_registry._format_overlays(overlays)

        assert "Available overlays" in formatted
        assert "Summarizer" in formatted
        assert "Analyzer" in formatted


class TestAPIModels:
    """Tests for API request/response models."""

    def test_chat_request_model(self):
        """Test ChatRequest-style model with Pydantic."""
        from typing import Any

        from pydantic import BaseModel, Field

        class ChatRequest(BaseModel):
            message: str = Field(description="User message")
            metadata: dict[str, Any] | None = Field(default=None)

        request = ChatRequest(
            message="Hello Forge",
            metadata={"source": "test"},
        )

        assert request.message == "Hello Forge"
        assert request.metadata == {"source": "test"}

    def test_chat_response_model(self):
        """Test ChatResponse-style model with Pydantic."""
        from pydantic import BaseModel, Field

        class ChatResponse(BaseModel):
            content: str
            tool_calls: list[dict] = Field(default_factory=list)
            reasoning: str | None = None
            latency_ms: float

        response = ChatResponse(
            content="Hello!",
            tool_calls=[],
            reasoning=None,
            latency_ms=100.0,
        )

        assert response.content == "Hello!"
        assert response.latency_ms == 100.0

    def test_status_response_model(self):
        """Test StatusResponse-style model with Pydantic."""
        from pydantic import BaseModel

        class StatusResponse(BaseModel):
            state: str
            is_running: bool
            model: str | None = None
            session_active: bool
            history_length: int

        status = StatusResponse(
            state="running",
            is_running=True,
            model="gpt-5",
            session_active=True,
            history_length=5,
        )

        assert status.state == "running"
        assert status.is_running is True
        assert status.model == "gpt-5"


class TestIntegrationWorkflow:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_mock_chat_workflow(self):
        """Test a complete chat workflow with mocks."""
        from forge.copilot.agent import CopilotConfig, CopilotForgeAgent
        from forge.copilot.tools import ForgeToolRegistry

        # Create mock tool registry
        registry = ForgeToolRegistry()
        mock_db = MagicMock()
        mock_db.search_capsules = AsyncMock(
            return_value=[{"id": "cap-1", "title": "AI Basics", "type": "note", "content": "..."}]
        )

        await registry.initialize(db_client=mock_db)

        # Verify registry is initialized
        assert registry._initialized is True

        # Test that tools are properly structured
        config = CopilotConfig(model="test")
        agent = CopilotForgeAgent(config=config, tool_registry=registry)

        # Verify agent configuration
        assert agent.config.model == "test"
        assert agent._tool_registry == registry

    def test_tool_parameter_json_schema(self):
        """Test that tool parameters generate valid JSON schema."""
        from forge.copilot.tools import KnowledgeQueryParams

        schema = KnowledgeQueryParams.model_json_schema()

        assert "properties" in schema
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"
