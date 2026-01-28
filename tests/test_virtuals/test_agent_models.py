"""
Tests for Agent Models for GAME Framework Integration.

This module tests the models for representing AI agents within the
Virtuals Protocol GAME framework.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from forge.virtuals.models.agent import (
    AgentGoals,
    AgentListResponse,
    AgentMemoryConfig,
    AgentPersonality,
    AgentStats,
    AgentUpdate,
    ForgeAgent,
    ForgeAgentCreate,
    WorkerDefinition,
)
from forge.virtuals.models.base import (
    AgentStatus,
    TokenInfo,
    TokenizationStatus,
    WalletInfo,
)


# ==================== AgentPersonality Tests ====================


class TestAgentPersonality:
    """Tests for AgentPersonality model."""

    def test_personality_creation(self):
        """Test creating an agent personality."""
        personality = AgentPersonality(
            name="Knowledge Agent",
            description="An AI agent specialized in knowledge retrieval",
            personality_traits=["analytical", "helpful", "precise"],
            communication_style="professional",
            expertise_domains=["science", "technology"],
        )

        assert personality.name == "Knowledge Agent"
        assert len(personality.personality_traits) == 3
        assert personality.communication_style == "professional"

    def test_personality_defaults(self):
        """Test default values for personality."""
        personality = AgentPersonality(
            name="Test Agent",
            description="A test agent",
        )

        assert personality.personality_traits == []
        assert personality.communication_style == "professional"
        assert personality.expertise_domains == []
        assert personality.response_guidelines == ""

    def test_to_game_prompt(self):
        """Test conversion to GAME framework prompt."""
        personality = AgentPersonality(
            name="Analyst",
            description="Expert data analyst",
            personality_traits=["analytical", "thorough"],
            communication_style="academic",
            expertise_domains=["data analysis", "statistics"],
            response_guidelines="Always cite sources.",
        )

        prompt = personality.to_game_prompt()

        assert "Analyst" in prompt
        assert "Expert data analyst" in prompt
        assert "analytical" in prompt
        assert "academic" in prompt
        assert "data analysis" in prompt
        assert "Always cite sources" in prompt

    def test_to_game_prompt_defaults(self):
        """Test GAME prompt with default values."""
        personality = AgentPersonality(
            name="Simple Agent",
            description="A simple agent",
        )

        prompt = personality.to_game_prompt()

        assert "Simple Agent" in prompt
        assert "helpful and professional" in prompt
        assert "general knowledge" in prompt

    def test_description_max_length(self):
        """Test description max length validation."""
        with pytest.raises(ValidationError):
            AgentPersonality(
                name="Test",
                description="X" * 2001,  # Exceeds 2000 char limit
            )


# ==================== WorkerDefinition Tests ====================


class TestWorkerDefinition:
    """Tests for WorkerDefinition model."""

    def test_worker_creation(self):
        """Test creating a worker definition."""
        worker = WorkerDefinition(
            name="QueryWorker",
            description="Handles knowledge queries",
            function_names=["query_capsule", "search_knowledge"],
        )

        assert worker.name == "QueryWorker"
        assert len(worker.function_names) == 2
        assert worker.id is not None  # Auto-generated

    def test_worker_defaults(self):
        """Test worker default values."""
        worker = WorkerDefinition(
            name="DefaultWorker",
            description="A default worker",
        )

        assert worker.function_names == []
        assert worker.state_schema == {}
        assert worker.max_concurrent_tasks == 5

    def test_worker_custom_concurrency(self):
        """Test worker with custom concurrency."""
        worker = WorkerDefinition(
            name="HighCapacity",
            description="High capacity worker",
            max_concurrent_tasks=20,
        )

        assert worker.max_concurrent_tasks == 20

    def test_worker_min_concurrency(self):
        """Test min concurrency validation."""
        with pytest.raises(ValidationError):
            WorkerDefinition(
                name="Invalid",
                description="Invalid worker",
                max_concurrent_tasks=0,
            )


# ==================== AgentGoals Tests ====================


class TestAgentGoals:
    """Tests for AgentGoals model."""

    def test_goals_creation(self):
        """Test creating agent goals."""
        goals = AgentGoals(
            primary_goal="Provide accurate knowledge responses",
            secondary_goals=["Minimize response time", "Maximize user satisfaction"],
            constraints=["Never share private data", "Stay within expertise"],
            success_metrics=["accuracy > 95%", "response time < 2s"],
        )

        assert goals.primary_goal == "Provide accurate knowledge responses"
        assert len(goals.secondary_goals) == 2
        assert len(goals.constraints) == 2

    def test_goals_minimal(self):
        """Test goals with only primary goal."""
        goals = AgentGoals(primary_goal="Help users")

        assert goals.primary_goal == "Help users"
        assert goals.secondary_goals == []
        assert goals.constraints == []
        assert goals.success_metrics == []


# ==================== AgentMemoryConfig Tests ====================


class TestAgentMemoryConfig:
    """Tests for AgentMemoryConfig model."""

    def test_memory_config_defaults(self):
        """Test default memory configuration."""
        config = AgentMemoryConfig()

        assert config.enable_long_term_memory is True
        assert config.memory_retention_days == 365
        assert config.max_working_memory_items == 100
        assert config.enable_cross_platform_sync is True
        assert config.vector_embedding_model == "text-embedding-3-small"

    def test_memory_config_custom(self):
        """Test custom memory configuration."""
        config = AgentMemoryConfig(
            enable_long_term_memory=False,
            memory_retention_days=30,
            max_working_memory_items=50,
            enable_cross_platform_sync=False,
            vector_embedding_model="custom-embedding-model",
        )

        assert config.enable_long_term_memory is False
        assert config.memory_retention_days == 30
        assert config.vector_embedding_model == "custom-embedding-model"


# ==================== ForgeAgentCreate Tests ====================


class TestForgeAgentCreate:
    """Tests for ForgeAgentCreate model."""

    def test_agent_create_minimal(self):
        """Test creating agent with minimal fields."""
        create = ForgeAgentCreate(
            name="TestAgent",
            personality=AgentPersonality(
                name="TestAgent",
                description="A test agent",
            ),
            goals=AgentGoals(primary_goal="Test goal"),
        )

        assert create.name == "TestAgent"
        assert create.enable_tokenization is False
        assert create.primary_chain == "base"

    def test_agent_create_with_tokenization(self):
        """Test creating agent with tokenization."""
        create = ForgeAgentCreate(
            name="TokenizedAgent",
            personality=AgentPersonality(
                name="TokenizedAgent",
                description="An agent to be tokenized",
            ),
            goals=AgentGoals(primary_goal="Generate revenue"),
            enable_tokenization=True,
            token_symbol="TKAGT",
            initial_virtual_stake=500.0,
        )

        assert create.enable_tokenization is True
        assert create.token_symbol == "TKAGT"
        assert create.initial_virtual_stake == 500.0

    def test_agent_create_name_validation(self):
        """Test name length validation."""
        with pytest.raises(ValidationError):
            ForgeAgentCreate(
                name="AB",  # Too short, min 3 chars
                personality=AgentPersonality(name="AB", description="Test"),
                goals=AgentGoals(primary_goal="Test"),
            )

    def test_token_symbol_validation_uppercase(self):
        """Test token symbol is uppercased."""
        create = ForgeAgentCreate(
            name="TestAgent",
            personality=AgentPersonality(name="TestAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            enable_tokenization=True,
            token_symbol="test",
        )

        assert create.token_symbol == "TEST"

    def test_token_symbol_validation_alphanumeric(self):
        """Test token symbol must be alphanumeric."""
        with pytest.raises(ValidationError):
            ForgeAgentCreate(
                name="TestAgent",
                personality=AgentPersonality(name="TestAgent", description="Test"),
                goals=AgentGoals(primary_goal="Test"),
                enable_tokenization=True,
                token_symbol="TEST-1",  # Invalid: contains dash
            )

    def test_initial_stake_minimum(self):
        """Test minimum initial stake validation."""
        with pytest.raises(ValidationError):
            ForgeAgentCreate(
                name="TestAgent",
                personality=AgentPersonality(name="TestAgent", description="Test"),
                goals=AgentGoals(primary_goal="Test"),
                initial_virtual_stake=50.0,  # Below minimum 100
            )


# ==================== ForgeAgent Tests ====================


class TestForgeAgent:
    """Tests for ForgeAgent model."""

    def test_agent_creation(self):
        """Test creating a forge agent."""
        agent = ForgeAgent(
            name="MyAgent",
            personality=AgentPersonality(name="MyAgent", description="Test agent"),
            goals=AgentGoals(primary_goal="Help users"),
        )

        assert agent.name == "MyAgent"
        assert agent.status == AgentStatus.PROTOTYPE
        assert agent.tokenization_status == TokenizationStatus.NOT_TOKENIZED
        assert agent.id is not None

    def test_agent_is_operational_prototype(self):
        """Test is_operational for prototype status."""
        agent = ForgeAgent(
            name="PrototypeAgent",
            personality=AgentPersonality(name="PrototypeAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            status=AgentStatus.PROTOTYPE,
        )

        assert agent.is_operational() is True

    def test_agent_is_operational_sentient(self):
        """Test is_operational for sentient status."""
        agent = ForgeAgent(
            name="SentientAgent",
            personality=AgentPersonality(name="SentientAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            status=AgentStatus.SENTIENT,
        )

        assert agent.is_operational() is True

    def test_agent_is_operational_suspended(self):
        """Test is_operational for suspended status."""
        agent = ForgeAgent(
            name="SuspendedAgent",
            personality=AgentPersonality(name="SuspendedAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            status=AgentStatus.SUSPENDED,
        )

        assert agent.is_operational() is False

    def test_agent_is_tokenized_not_tokenized(self):
        """Test is_tokenized for non-tokenized agent."""
        agent = ForgeAgent(
            name="NonTokenized",
            personality=AgentPersonality(name="NonTokenized", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            tokenization_status=TokenizationStatus.NOT_TOKENIZED,
        )

        assert agent.is_tokenized() is False

    def test_agent_is_tokenized_bonding(self):
        """Test is_tokenized for bonding status."""
        agent = ForgeAgent(
            name="BondingAgent",
            personality=AgentPersonality(name="BondingAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            tokenization_status=TokenizationStatus.BONDING,
        )

        assert agent.is_tokenized() is True

    def test_agent_is_tokenized_graduated(self):
        """Test is_tokenized for graduated status."""
        agent = ForgeAgent(
            name="GraduatedAgent",
            personality=AgentPersonality(name="GraduatedAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            tokenization_status=TokenizationStatus.GRADUATED,
        )

        assert agent.is_tokenized() is True

    def test_agent_get_wallet(self):
        """Test get_wallet method."""
        wallet = WalletInfo(
            address="0x" + "1" * 40,
            chain="base",
        )
        agent = ForgeAgent(
            name="WalletAgent",
            personality=AgentPersonality(name="WalletAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            wallets={"base": wallet},
        )

        retrieved = agent.get_wallet("base")
        assert retrieved is not None
        assert retrieved.address == wallet.address

    def test_agent_get_wallet_not_found(self):
        """Test get_wallet for non-existent chain."""
        agent = ForgeAgent(
            name="NoWalletAgent",
            personality=AgentPersonality(name="NoWalletAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
        )

        assert agent.get_wallet("ethereum") is None

    def test_agent_get_primary_wallet(self):
        """Test get_primary_wallet method."""
        wallet = WalletInfo(
            address="0x" + "2" * 40,
            chain="base",
        )
        agent = ForgeAgent(
            name="PrimaryWalletAgent",
            personality=AgentPersonality(name="PrimaryWalletAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
            primary_chain="base",
            wallets={"base": wallet},
        )

        primary = agent.get_primary_wallet()
        assert primary is not None
        assert primary.address == wallet.address


# ==================== AgentUpdate Tests ====================


class TestAgentUpdate:
    """Tests for AgentUpdate model."""

    def test_update_all_none(self):
        """Test update with all fields None."""
        update = AgentUpdate()

        assert update.personality is None
        assert update.goals is None
        assert update.workers is None

    def test_update_partial(self):
        """Test partial update."""
        new_personality = AgentPersonality(
            name="UpdatedAgent",
            description="Updated description",
        )
        update = AgentUpdate(personality=new_personality)

        assert update.personality is not None
        assert update.personality.description == "Updated description"

    def test_update_workers(self):
        """Test update with workers."""
        workers = [
            WorkerDefinition(name="Worker1", description="First worker"),
            WorkerDefinition(name="Worker2", description="Second worker"),
        ]
        update = AgentUpdate(workers=workers)

        assert update.workers is not None
        assert len(update.workers) == 2


# ==================== AgentStats Tests ====================


class TestAgentStats:
    """Tests for AgentStats model."""

    def test_stats_creation(self):
        """Test creating agent stats."""
        now = datetime.now(UTC)
        stats = AgentStats(
            agent_id="agent-123",
            period_start=now,
            period_end=now,
            queries_handled=100,
            tasks_completed=50,
            revenue_generated_virtual=500.0,
        )

        assert stats.agent_id == "agent-123"
        assert stats.queries_handled == 100
        assert stats.revenue_generated_virtual == 500.0

    def test_stats_defaults(self):
        """Test stats default values."""
        now = datetime.now(UTC)
        stats = AgentStats(
            agent_id="agent-456",
            period_start=now,
            period_end=now,
        )

        assert stats.queries_handled == 0
        assert stats.tasks_completed == 0
        assert stats.revenue_generated_virtual == 0.0
        assert stats.error_rate == 0.0


# ==================== AgentListResponse Tests ====================


class TestAgentListResponse:
    """Tests for AgentListResponse model."""

    def test_list_response_creation(self):
        """Test creating list response."""
        agent = ForgeAgent(
            name="TestAgent",
            personality=AgentPersonality(name="TestAgent", description="Test"),
            goals=AgentGoals(primary_goal="Test"),
        )

        response = AgentListResponse(
            agents=[agent],
            total=1,
        )

        assert len(response.agents) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.per_page == 20
        assert response.has_more is False

    def test_list_response_pagination(self):
        """Test list response with pagination."""
        response = AgentListResponse(
            agents=[],
            total=100,
            page=3,
            per_page=20,
            has_more=True,
        )

        assert response.total == 100
        assert response.page == 3
        assert response.has_more is True
