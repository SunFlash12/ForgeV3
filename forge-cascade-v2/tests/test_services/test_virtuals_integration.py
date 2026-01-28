"""
Tests for Virtuals Protocol Integration Service

Tests the integration with Virtuals Protocol ecosystem including
Agent Commerce Protocol (ACP) and GAME SDK functionality.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.services.virtuals_integration import (
    VirtualsIntegrationConfig,
    VirtualsIntegrationService,
    get_virtuals_config,
    get_virtuals_service,
    init_virtuals_service,
    shutdown_virtuals_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def virtuals_config():
    """Create a test configuration."""
    return VirtualsIntegrationConfig(
        acp_enabled=True,
        game_enabled=True,
        primary_chain="base",
        base_rpc_url="https://mainnet.base.org",
        game_api_key="test-api-key",
    )


@pytest.fixture
def virtuals_config_acp_only():
    """Create a config with only ACP enabled."""
    return VirtualsIntegrationConfig(
        acp_enabled=True,
        game_enabled=False,
        primary_chain="base",
    )


@pytest.fixture
def virtuals_config_game_only():
    """Create a config with only GAME enabled."""
    return VirtualsIntegrationConfig(
        acp_enabled=False,
        game_enabled=True,
        primary_chain="base",
        game_api_key="test-api-key",
    )


@pytest.fixture
def mock_db_client():
    """Create a mock Neo4j database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_job_repository():
    """Create a mock job repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_by_buyer = AsyncMock(return_value=[])
    repo.list_by_provider = AsyncMock(return_value=[])
    repo.get_pending_jobs = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_offering_repository():
    """Create a mock offering repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_agent = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_acp_service():
    """Create a mock ACP service."""
    service = AsyncMock()
    service.initialize = AsyncMock()
    service.register_offering = AsyncMock()
    service.search_offerings = AsyncMock(return_value=[])
    service.create_job = AsyncMock()
    service.respond_to_request = AsyncMock()
    service.accept_terms = AsyncMock()
    service.submit_deliverable = AsyncMock()
    service.evaluate_deliverable = AsyncMock()
    service.file_dispute = AsyncMock()
    return service


@pytest.fixture
def mock_game_client():
    """Create a mock GAME SDK client."""
    client = AsyncMock()
    client.initialize = AsyncMock()
    client.close = AsyncMock()
    client.create_agent = AsyncMock()
    client.get_agent = AsyncMock(return_value=None)
    client.delete_agent = AsyncMock(return_value=True)
    client.run_agent_loop = AsyncMock(return_value=[])
    client.get_next_action = AsyncMock(return_value={})
    client.store_memory = AsyncMock(return_value="memory-123")
    client.retrieve_memories = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_capsule_repository():
    """Create a mock capsule repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.search = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_overlay_manager():
    """Create a mock overlay manager."""
    manager = AsyncMock()
    manager.run_overlay = AsyncMock()
    manager.list_overlays = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def mock_governance_service():
    """Create a mock governance service."""
    service = AsyncMock()
    service.get_proposals = AsyncMock(return_value=[])
    service.cast_vote = AsyncMock()
    return service


@pytest.fixture
def virtuals_service(
    virtuals_config,
    mock_db_client,
    mock_job_repository,
    mock_offering_repository,
):
    """Create a Virtuals integration service for testing."""
    return VirtualsIntegrationService(
        config=virtuals_config,
        db_client=mock_db_client,
        job_repository=mock_job_repository,
        offering_repository=mock_offering_repository,
    )


# =============================================================================
# Test VirtualsIntegrationConfig
# =============================================================================


class TestVirtualsIntegrationConfig:
    """Tests for VirtualsIntegrationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = VirtualsIntegrationConfig()

        assert config.acp_enabled is False
        assert config.game_enabled is False
        assert config.primary_chain == "base"
        assert config.base_chain_id == 8453
        assert config.default_escrow_timeout_hours == 72

    def test_custom_config(self):
        """Test custom configuration values."""
        config = VirtualsIntegrationConfig(
            acp_enabled=True,
            game_enabled=True,
            primary_chain="solana",
            base_private_key="0x123...",
            game_api_key="test-key",
        )

        assert config.acp_enabled is True
        assert config.game_enabled is True
        assert config.primary_chain == "solana"

    def test_repr_redacts_secrets(self):
        """Test that repr redacts sensitive information."""
        config = VirtualsIntegrationConfig(
            base_private_key="secret-key",
            solana_private_key="another-secret",
            game_api_key="api-secret",
        )

        repr_str = repr(config)

        assert "secret-key" not in repr_str
        assert "another-secret" not in repr_str
        assert "api-secret" not in repr_str
        assert "[REDACTED]" in repr_str


# =============================================================================
# Test VirtualsIntegrationService Initialization
# =============================================================================


class TestVirtualsIntegrationServiceInit:
    """Tests for VirtualsIntegrationService initialization."""

    def test_init_creates_service(self, virtuals_config, mock_db_client):
        """Test basic service initialization."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        assert service._config is virtuals_config
        assert service._db_client is mock_db_client
        assert service._initialized is False

    def test_init_with_repositories(
        self,
        virtuals_config,
        mock_db_client,
        mock_job_repository,
        mock_offering_repository,
    ):
        """Test initialization with custom repositories."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            job_repository=mock_job_repository,
            offering_repository=mock_offering_repository,
        )

        assert service._job_repo is mock_job_repository
        assert service._offering_repo is mock_offering_repository

    @pytest.mark.asyncio
    async def test_initialize_with_acp(
        self,
        virtuals_config_acp_only,
        mock_db_client,
        mock_acp_service,
    ):
        """Test initialization with ACP enabled."""
        service = VirtualsIntegrationService(
            config=virtuals_config_acp_only,
            db_client=mock_db_client,
        )

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await service.initialize()

        assert service._initialized is True
        mock_acp_service.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_game(
        self,
        virtuals_config_game_only,
        mock_db_client,
        mock_game_client,
    ):
        """Test initialization with GAME SDK enabled."""
        service = VirtualsIntegrationService(
            config=virtuals_config_game_only,
            db_client=mock_db_client,
        )

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

        assert service._initialized is True
        mock_game_client.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_without_game_api_key_raises(
        self,
        mock_db_client,
    ):
        """Test that initialization raises if GAME enabled but no API key."""
        config = VirtualsIntegrationConfig(
            game_enabled=True,
            game_api_key=None,
        )
        service = VirtualsIntegrationService(
            config=config,
            db_client=mock_db_client,
        )

        with pytest.raises(ValueError, match="GAME API key is required"):
            await service.initialize()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, virtuals_service, mock_acp_service):
        """Test that multiple initializations are idempotent."""
        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()
            await virtuals_service.initialize()

        # Should only initialize once
        assert mock_acp_service.initialize.call_count == 1


# =============================================================================
# Test Shutdown
# =============================================================================


class TestShutdown:
    """Tests for shutdown method."""

    @pytest.mark.asyncio
    async def test_shutdown(self, virtuals_service, mock_acp_service, mock_game_client):
        """Test service shutdown."""
        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            with patch("forge.services.virtuals_integration.VirtualsConfig"):
                with patch(
                    "forge.services.virtuals_integration.GAMESDKClient",
                    return_value=mock_game_client,
                ):
                    await virtuals_service.initialize()
                    await virtuals_service.shutdown()

        assert virtuals_service._initialized is False
        assert virtuals_service._acp_service is None
        mock_game_client.close.assert_called_once()


# =============================================================================
# Test Service Offerings
# =============================================================================


class TestServiceOfferings:
    """Tests for service offering methods."""

    @pytest.mark.asyncio
    async def test_register_offering(self, virtuals_service, mock_acp_service):
        """Test registering a service offering."""
        mock_offering = MagicMock()
        mock_acp_service.register_offering.return_value = mock_offering

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.register_offering(
                agent_id="agent-123",
                agent_wallet="0xWallet...",
                offering=mock_offering,
            )

        assert result is mock_offering
        mock_acp_service.register_offering.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_offering_acp_disabled_raises(self, mock_db_client):
        """Test that registering offering fails if ACP disabled."""
        config = VirtualsIntegrationConfig(acp_enabled=False)
        service = VirtualsIntegrationService(config=config, db_client=mock_db_client)

        with pytest.raises(RuntimeError, match="ACP is not enabled"):
            await service.register_offering(
                agent_id="agent-123",
                agent_wallet="0xWallet...",
                offering=MagicMock(),
            )

    @pytest.mark.asyncio
    async def test_search_offerings(self, virtuals_service, mock_acp_service):
        """Test searching service offerings."""
        mock_offerings = [MagicMock(), MagicMock()]
        mock_acp_service.search_offerings.return_value = mock_offerings

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            results = await virtuals_service.search_offerings(
                service_type="knowledge_query",
                max_fee=100.0,
            )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_offering(self, virtuals_service, mock_offering_repository):
        """Test getting a specific offering."""
        mock_offering = MagicMock()
        mock_offering_repository.get_by_id.return_value = mock_offering

        result = await virtuals_service.get_offering("offering-123")

        assert result is mock_offering

    @pytest.mark.asyncio
    async def test_get_agent_offerings(self, virtuals_service, mock_offering_repository):
        """Test getting offerings for an agent."""
        mock_offerings = [MagicMock(), MagicMock()]
        mock_offering_repository.get_by_agent.return_value = mock_offerings

        results = await virtuals_service.get_agent_offerings("agent-123")

        assert len(results) == 2


# =============================================================================
# Test Job Lifecycle
# =============================================================================


class TestJobLifecycle:
    """Tests for job lifecycle methods."""

    @pytest.mark.asyncio
    async def test_create_job(self, virtuals_service, mock_acp_service):
        """Test creating a new job."""
        mock_job = MagicMock()
        mock_acp_service.create_job.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.create_job(
                create_request=MagicMock(),
                buyer_wallet="0xBuyer...",
            )

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_respond_to_job(self, virtuals_service, mock_acp_service):
        """Test provider responding to a job."""
        mock_job = MagicMock()
        mock_acp_service.respond_to_request.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.respond_to_job(
                job_id="job-123",
                terms=MagicMock(),
                provider_wallet="0xProvider...",
            )

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_accept_terms(self, virtuals_service, mock_acp_service):
        """Test buyer accepting terms."""
        mock_job = MagicMock()
        mock_acp_service.accept_terms.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.accept_terms(
                job_id="job-123",
                buyer_wallet="0xBuyer...",
            )

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_submit_deliverable(self, virtuals_service, mock_acp_service):
        """Test provider submitting deliverable."""
        mock_job = MagicMock()
        mock_acp_service.submit_deliverable.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.submit_deliverable(
                job_id="job-123",
                deliverable=MagicMock(),
                provider_wallet="0xProvider...",
            )

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_evaluate_deliverable(self, virtuals_service, mock_acp_service):
        """Test evaluating a deliverable."""
        mock_job = MagicMock()
        mock_acp_service.evaluate_deliverable.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.evaluate_deliverable(
                job_id="job-123",
                evaluation=MagicMock(),
                evaluator_wallet="0xEvaluator...",
            )

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_file_dispute(self, virtuals_service, mock_acp_service):
        """Test filing a dispute."""
        mock_job = MagicMock()
        mock_acp_service.file_dispute.return_value = mock_job

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.file_dispute(
                job_id="job-123",
                dispute=MagicMock(),
                filer_wallet="0xFiler...",
            )

        assert result is mock_job


# =============================================================================
# Test Job Queries
# =============================================================================


class TestJobQueries:
    """Tests for job query methods."""

    @pytest.mark.asyncio
    async def test_get_job(self, virtuals_service, mock_job_repository):
        """Test getting a job by ID."""
        mock_job = MagicMock()
        mock_job_repository.get_by_id.return_value = mock_job

        result = await virtuals_service.get_job("job-123")

        assert result is mock_job

    @pytest.mark.asyncio
    async def test_get_buyer_jobs(self, virtuals_service, mock_job_repository):
        """Test getting jobs where agent is buyer."""
        mock_jobs = [MagicMock(), MagicMock()]
        mock_job_repository.list_by_buyer.return_value = mock_jobs

        results = await virtuals_service.get_buyer_jobs(
            buyer_agent_id="agent-123",
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_provider_jobs(self, virtuals_service, mock_job_repository):
        """Test getting jobs where agent is provider."""
        mock_jobs = [MagicMock()]
        mock_job_repository.list_by_provider.return_value = mock_jobs

        results = await virtuals_service.get_provider_jobs(
            provider_agent_id="agent-456",
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, virtuals_service, mock_job_repository):
        """Test getting jobs pending action."""
        mock_jobs = [MagicMock(), MagicMock(), MagicMock()]
        mock_job_repository.get_pending_jobs.return_value = mock_jobs

        results = await virtuals_service.get_pending_jobs("agent-123")

        assert len(results) == 3


# =============================================================================
# Test Agent Gateway Bridge
# =============================================================================


class TestAgentGatewayBridge:
    """Tests for Agent Gateway bridge methods."""

    @pytest.mark.asyncio
    async def test_create_offering_from_session(self, virtuals_service, mock_acp_service):
        """Test creating offering from Agent Gateway session."""
        mock_session = MagicMock()
        mock_session.agent_id = "agent-123"
        mock_session.metadata = {"wallet_address": "0xWallet..."}
        mock_session.capabilities = []

        mock_gateway = AsyncMock()
        mock_gateway.get_session.return_value = mock_session

        mock_offering = MagicMock()
        mock_acp_service.register_offering.return_value = mock_offering

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            result = await virtuals_service.create_offering_from_agent_session(
                session_id="session-123",
                agent_gateway_service=mock_gateway,
                service_type="knowledge_query",
                title="Test Offering",
                description="A test offering",
                base_fee_virtual=10.0,
            )

        assert result is mock_offering

    @pytest.mark.asyncio
    async def test_create_offering_session_not_found(self, virtuals_service, mock_acp_service):
        """Test creating offering when session not found."""
        mock_gateway = AsyncMock()
        mock_gateway.get_session.return_value = None

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await virtuals_service.initialize()

            with pytest.raises(ValueError, match="Session .* not found"):
                await virtuals_service.create_offering_from_agent_session(
                    session_id="nonexistent",
                    agent_gateway_service=mock_gateway,
                    service_type="test",
                    title="Test",
                    description="Test",
                    base_fee_virtual=10.0,
                )

    def test_capabilities_to_input_schema(self, virtuals_service):
        """Test converting capabilities to JSON schema."""
        # Create mock capabilities
        cap1 = MagicMock()
        cap1.value = "query_graph"
        cap2 = MagicMock()
        cap2.value = "semantic_search"
        cap3 = MagicMock()
        cap3.value = "create_capsules"

        schema = virtuals_service._capabilities_to_input_schema([cap1, cap2, cap3])

        assert schema["type"] == "object"
        assert "query_text" in schema["properties"]
        assert "query" in schema["properties"]
        assert "capsule_data" in schema["properties"]


# =============================================================================
# Test GAME SDK: Agent Management
# =============================================================================


class TestGAMEAgentManagement:
    """Tests for GAME SDK agent management."""

    @pytest.mark.asyncio
    async def test_create_game_agent(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
        mock_capsule_repository,
    ):
        """Test creating a GAME agent."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            capsule_repository=mock_capsule_repository,
        )

        mock_agent = MagicMock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Test Agent"
        mock_agent.game_agent_id = "game-456"
        mock_agent.status = MagicMock(value="active")
        mock_agent.created_at = datetime.now(UTC)
        mock_game_client.create_agent.return_value = mock_agent

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                with patch(
                    "forge.services.virtuals_integration.create_knowledge_worker"
                ) as mock_kw:
                    mock_worker = MagicMock()
                    mock_worker.worker_id = "knowledge_worker"
                    mock_kw.return_value = mock_worker

                    await service.initialize()

                    result = await service.create_game_agent(
                        name="Test Agent",
                        primary_goal="Test knowledge queries",
                        description="A test agent",
                        worker_types=["knowledge"],
                    )

        assert result["id"] == "agent-123"
        assert result["name"] == "Test Agent"
        assert "knowledge_worker" in result["workers"]

    @pytest.mark.asyncio
    async def test_create_game_agent_no_workers_raises(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test that creating agent without workers raises error."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            # No repositories provided
        )

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                with pytest.raises(ValueError, match="No workers could be created"):
                    await service.create_game_agent(
                        name="Test Agent",
                        primary_goal="Test",
                        description="Test",
                        worker_types=["knowledge"],
                    )

    @pytest.mark.asyncio
    async def test_get_game_agent_from_cache(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test getting agent from local cache."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        # Pre-populate cache
        mock_agent = MagicMock()
        mock_agent.id = "agent-123"
        mock_agent.name = "Cached Agent"
        mock_agent.game_agent_id = "game-456"
        mock_agent.status = MagicMock(value="active")
        service._agents["agent-123"] = mock_agent
        service._agent_workers["agent-123"] = {"worker1": MagicMock()}

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                result = await service.get_game_agent("agent-123")

        assert result is not None
        assert result["name"] == "Cached Agent"
        # Should not call the client since agent is in cache
        mock_game_client.get_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_game_agent(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test deleting a GAME agent."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        # Pre-populate cache
        service._agents["agent-123"] = MagicMock()
        service._agent_workers["agent-123"] = {}

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                result = await service.delete_game_agent("agent-123")

        assert result is True
        assert "agent-123" not in service._agents

    @pytest.mark.asyncio
    async def test_list_game_agents(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test listing all GAME agents."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        # Pre-populate cache
        mock_agent1 = MagicMock()
        mock_agent1.id = "agent-1"
        mock_agent1.name = "Agent 1"
        mock_agent1.game_agent_id = "game-1"
        mock_agent1.status = MagicMock(value="active")

        mock_agent2 = MagicMock()
        mock_agent2.id = "agent-2"
        mock_agent2.name = "Agent 2"
        mock_agent2.game_agent_id = "game-2"
        mock_agent2.status = MagicMock(value="idle")

        service._agents = {"agent-1": mock_agent1, "agent-2": mock_agent2}
        service._agent_workers = {"agent-1": {}, "agent-2": {}}

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                results = await service.list_game_agents()

        assert len(results) == 2


# =============================================================================
# Test GAME SDK: Agent Execution
# =============================================================================


class TestGAMEAgentExecution:
    """Tests for GAME SDK agent execution."""

    @pytest.mark.asyncio
    async def test_run_game_agent(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test running a GAME agent loop."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        # Pre-populate cache
        mock_agent = MagicMock()
        mock_worker = MagicMock()
        service._agents["agent-123"] = mock_agent
        service._agent_workers["agent-123"] = {"worker1": mock_worker}

        mock_game_client.run_agent_loop.return_value = [
            {"action": "search", "result": "found"},
            {"action": "create", "result": "created"},
        ]

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                results = await service.run_game_agent(
                    agent_id="agent-123",
                    context="Search for knowledge",
                    max_iterations=10,
                )

        assert len(results) == 2
        mock_game_client.run_agent_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_game_agent_not_found(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test running non-existent agent raises error."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                with pytest.raises(ValueError, match="Agent .* not found"):
                    await service.run_game_agent("nonexistent")

    @pytest.mark.asyncio
    async def test_get_agent_next_action(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test getting next action for an agent."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        mock_agent = MagicMock()
        mock_agent.game_agent_id = "game-123"
        mock_worker = MagicMock()
        mock_worker.get_state.return_value = {"state": "ready"}

        service._agents["agent-123"] = mock_agent
        service._agent_workers["agent-123"] = {"worker1": mock_worker}

        mock_game_client.get_next_action.return_value = {
            "action": "search_capsules",
            "params": {"query": "test"},
        }

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                result = await service.get_agent_next_action("agent-123")

        assert result["action"] == "search_capsules"


# =============================================================================
# Test GAME SDK: Memory Operations
# =============================================================================


class TestGAMEMemoryOperations:
    """Tests for GAME SDK memory operations."""

    @pytest.mark.asyncio
    async def test_store_agent_memory(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test storing agent memory."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        mock_agent = MagicMock()
        mock_agent.game_agent_id = "game-123"
        service._agents["agent-123"] = mock_agent

        mock_game_client.store_memory.return_value = "memory-456"

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                result = await service.store_agent_memory(
                    agent_id="agent-123",
                    memory_type="fact",
                    content={"key": "value"},
                    ttl_days=30,
                )

        assert result == "memory-456"

    @pytest.mark.asyncio
    async def test_search_agent_memories(
        self,
        virtuals_config,
        mock_db_client,
        mock_game_client,
    ):
        """Test searching agent memories."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        mock_agent = MagicMock()
        mock_agent.game_agent_id = "game-123"
        service._agents["agent-123"] = mock_agent

        mock_game_client.retrieve_memories.return_value = [
            {"id": "mem-1", "content": "memory 1"},
            {"id": "mem-2", "content": "memory 2"},
        ]

        with patch("forge.services.virtuals_integration.VirtualsConfig"):
            with patch(
                "forge.services.virtuals_integration.GAMESDKClient", return_value=mock_game_client
            ):
                await service.initialize()

                results = await service.search_agent_memories(
                    agent_id="agent-123",
                    query="test query",
                    limit=5,
                )

        assert len(results) == 2


# =============================================================================
# Test GAME SDK: Function Discovery
# =============================================================================


class TestGAMEFunctionDiscovery:
    """Tests for GAME SDK function discovery."""

    def test_get_available_functions_empty(self, virtuals_config, mock_db_client):
        """Test getting functions when no repositories configured."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
        )

        functions = service.get_available_functions()

        assert len(functions) == 0

    def test_get_available_functions_with_capsule_repo(
        self,
        virtuals_config,
        mock_db_client,
        mock_capsule_repository,
    ):
        """Test getting functions with capsule repository."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            capsule_repository=mock_capsule_repository,
        )

        functions = service.get_available_functions()

        function_names = [f["name"] for f in functions]
        assert "search_capsules" in function_names
        assert "get_capsule" in function_names
        assert "create_capsule" in function_names

    def test_get_available_functions_with_overlay_manager(
        self,
        virtuals_config,
        mock_db_client,
        mock_overlay_manager,
    ):
        """Test getting functions with overlay manager."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            overlay_manager=mock_overlay_manager,
        )

        functions = service.get_available_functions()

        function_names = [f["name"] for f in functions]
        assert "run_overlay" in function_names
        assert "list_overlays" in function_names

    def test_get_available_functions_with_governance(
        self,
        virtuals_config,
        mock_db_client,
        mock_governance_service,
    ):
        """Test getting functions with governance service."""
        service = VirtualsIntegrationService(
            config=virtuals_config,
            db_client=mock_db_client,
            governance_service=mock_governance_service,
        )

        functions = service.get_available_functions()

        function_names = [f["name"] for f in functions]
        assert "get_proposals" in function_names
        assert "cast_vote" in function_names


# =============================================================================
# Test Module-Level Functions
# =============================================================================


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_virtuals_config(self):
        """Test getting config from settings."""
        with patch("forge.services.virtuals_integration.get_settings") as mock_settings:
            settings = MagicMock()
            settings.acp_enabled = True
            settings.game_enabled = True
            settings.virtuals_primary_chain = "base"
            settings.base_rpc_url = "https://test.base.org"
            settings.base_chain_id = 8453
            settings.base_private_key = "0x123"
            settings.acp_escrow_contract_address = "0xEscrow"
            settings.acp_registry_contract_address = "0xRegistry"
            settings.virtual_token_address = "0xVirtual"
            settings.solana_rpc_url = "https://api.solana.com"
            settings.solana_private_key = None
            settings.solana_acp_program_id = None
            settings.frowg_token_address = None
            settings.acp_default_escrow_timeout_hours = 72
            settings.acp_evaluation_timeout_hours = 24
            settings.acp_max_job_fee_virtual = 10000.0
            settings.game_api_key = "test-key"
            mock_settings.return_value = settings

            config = get_virtuals_config()

            assert config.acp_enabled is True
            assert config.game_enabled is True

    def test_get_virtuals_service_uninitialized(self):
        """Test getting service when not initialized raises error."""
        import forge.services.virtuals_integration as vi_module

        # Reset global
        vi_module._virtuals_service = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_virtuals_service()

    @pytest.mark.asyncio
    async def test_init_virtuals_service(self, mock_db_client, mock_acp_service):
        """Test initializing the global service."""
        import forge.services.virtuals_integration as vi_module

        # Reset global
        vi_module._virtuals_service = None

        config = VirtualsIntegrationConfig(acp_enabled=True)

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            service = await init_virtuals_service(mock_db_client, config)

            assert service is not None
            assert vi_module._virtuals_service is service

            # Cleanup
            vi_module._virtuals_service = None

    @pytest.mark.asyncio
    async def test_shutdown_virtuals_service(self, mock_db_client, mock_acp_service):
        """Test shutting down the global service."""
        import forge.services.virtuals_integration as vi_module

        config = VirtualsIntegrationConfig(acp_enabled=True)

        with patch("forge.services.virtuals_integration.ACPService", return_value=mock_acp_service):
            await init_virtuals_service(mock_db_client, config)
            await shutdown_virtuals_service()

            assert vi_module._virtuals_service is None


# =============================================================================
# Test Helper Methods
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_ensure_acp_enabled_raises_when_disabled(self, mock_db_client):
        """Test _ensure_acp_enabled raises when ACP disabled."""
        config = VirtualsIntegrationConfig(acp_enabled=False)
        service = VirtualsIntegrationService(config=config, db_client=mock_db_client)

        with pytest.raises(RuntimeError, match="ACP is not enabled"):
            service._ensure_acp_enabled()

    def test_ensure_acp_enabled_raises_when_not_initialized(self, virtuals_config, mock_db_client):
        """Test _ensure_acp_enabled raises when not initialized."""
        service = VirtualsIntegrationService(config=virtuals_config, db_client=mock_db_client)

        with pytest.raises(RuntimeError, match="not initialized"):
            service._ensure_acp_enabled()

    def test_ensure_game_enabled_raises_when_disabled(self, mock_db_client):
        """Test _ensure_game_enabled raises when GAME disabled."""
        config = VirtualsIntegrationConfig(game_enabled=False)
        service = VirtualsIntegrationService(config=config, db_client=mock_db_client)

        with pytest.raises(RuntimeError, match="GAME SDK is not enabled"):
            service._ensure_game_enabled()

    def test_ensure_game_enabled_raises_when_not_initialized(
        self,
        virtuals_config,
        mock_db_client,
    ):
        """Test _ensure_game_enabled raises when not initialized."""
        service = VirtualsIntegrationService(config=virtuals_config, db_client=mock_db_client)

        with pytest.raises(RuntimeError, match="not initialized"):
            service._ensure_game_enabled()
