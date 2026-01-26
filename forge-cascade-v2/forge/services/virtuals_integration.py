"""
Virtuals Protocol Integration Service

This service integrates Forge with the Virtuals Protocol ecosystem,
providing Agent Commerce Protocol (ACP) and GAME SDK functionality.

It bridges Forge's knowledge capabilities with Virtuals' agent commerce
infrastructure, enabling:
- Service offering registration
- Agent-to-agent job transactions
- Escrow management with real blockchain settlement
- Trust-based pricing integration
"""

from dataclasses import dataclass
from typing import Any

import structlog

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.repositories.acp_repository import (
    ACPJobRepository,
    OfferingRepository,
    get_job_repository,
    get_offering_repository,
)
from forge.virtuals.acp.service import ACPService
from forge.virtuals.game.forge_functions import (
    create_analysis_worker,
    create_governance_worker,
    create_knowledge_worker,
)
from forge.virtuals.game.sdk_client import (
    GAMESDKClient,
    GAMEWorker,
)
from forge.virtuals.models.acp import (
    ACPDeliverable,
    ACPDispute,
    ACPEvaluation,
    ACPJob,
    ACPJobCreate,
    ACPNegotiationTerms,
    JobOffering,
)

logger = structlog.get_logger(__name__)


@dataclass
class VirtualsIntegrationConfig:
    """Configuration for Virtuals Protocol integration."""

    acp_enabled: bool = False
    game_enabled: bool = False
    primary_chain: str = "base"

    # Base L2 Configuration
    base_rpc_url: str = "https://mainnet.base.org"
    base_chain_id: int = 8453
    base_private_key: str | None = None
    acp_escrow_contract_address: str | None = None
    acp_registry_contract_address: str | None = None
    virtual_token_address: str = "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"

    # Solana Configuration
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    solana_private_key: str | None = None
    solana_acp_program_id: str | None = None
    frowg_token_address: str | None = None

    # Timeouts
    default_escrow_timeout_hours: int = 72
    evaluation_timeout_hours: int = 24
    max_job_fee_virtual: float = 10000.0

    # GAME SDK Configuration
    game_api_key: str | None = None
    game_api_base_url: str = "https://game.virtuals.io/api"
    game_api_rate_limit: int = 100
    game_max_agent_iterations: int = 50

    def __repr__(self) -> str:
        """Redact private keys in repr."""
        return (
            f"VirtualsIntegrationConfig("
            f"acp_enabled={self.acp_enabled}, "
            f"game_enabled={self.game_enabled}, "
            f"primary_chain={self.primary_chain}, "
            f"base_private_key={'[REDACTED]' if self.base_private_key else None}, "
            f"solana_private_key={'[REDACTED]' if self.solana_private_key else None}, "
            f"game_api_key={'[REDACTED]' if self.game_api_key else None}"
            f")"
        )


class VirtualsIntegrationService:
    """
    Main service for Virtuals Protocol integration.

    Provides a unified interface for:
    - ACP service offering management
    - Job lifecycle management
    - Blockchain escrow operations
    - Agent Gateway bridge

    This service wraps the lower-level ACP service and connects it
    with Forge's repository and database infrastructure.
    """

    def __init__(
        self,
        config: VirtualsIntegrationConfig,
        db_client: Neo4jClient,
        job_repository: ACPJobRepository | None = None,
        offering_repository: OfferingRepository | None = None,
        capsule_repository: Any | None = None,
        overlay_manager: Any | None = None,
        governance_service: Any | None = None,
    ):
        """
        Initialize the Virtuals integration service.

        Args:
            config: Integration configuration
            db_client: Neo4j database client
            job_repository: Optional job repository (created if not provided)
            offering_repository: Optional offering repository (created if not provided)
            capsule_repository: Optional capsule repository (for GAME knowledge worker)
            overlay_manager: Optional overlay manager (for GAME analysis worker)
            governance_service: Optional governance service (for GAME governance worker)
        """
        self._config = config
        self._db_client = db_client
        self._job_repo = job_repository or get_job_repository(db_client)
        self._offering_repo = offering_repository or get_offering_repository(db_client)
        self._acp_service: ACPService | None = None
        self._initialized = False

        # GAME SDK components
        self._game_client: GAMESDKClient | None = None
        self._capsule_repo = capsule_repository
        self._overlay_manager = overlay_manager
        self._governance_service = governance_service

        # Active GAME agents and their workers
        self._agents: dict[str, Any] = {}
        self._agent_workers: dict[str, dict[str, GAMEWorker]] = {}

        logger.info(
            "virtuals_integration_service_created",
            acp_enabled=config.acp_enabled,
            game_enabled=config.game_enabled,
            primary_chain=config.primary_chain,
        )

    async def initialize(self) -> None:
        """
        Initialize the service and its dependencies.

        This sets up the ACP service with repositories and
        initializes blockchain connections. Also initializes
        the GAME SDK client if enabled.
        """
        if self._initialized:
            return

        if self._config.acp_enabled:
            # Initialize ACP service with repositories
            self._acp_service = ACPService(
                job_repository=self._job_repo,
                offering_repository=self._offering_repo,
            )
            await self._acp_service.initialize()

            logger.info("acp_service_initialized")

        if self._config.game_enabled:
            # Initialize GAME SDK client
            from forge.virtuals.config import VirtualsConfig

            if self._config.game_api_key is None:
                raise ValueError("GAME API key is required when game_enabled is True")
            game_config = VirtualsConfig(
                api_key=self._config.game_api_key,
                api_base_url=self._config.game_api_base_url,
                game_api_rate_limit=self._config.game_api_rate_limit,
            )
            self._game_client = GAMESDKClient(config=game_config)
            await self._game_client.initialize()

            logger.info("game_sdk_client_initialized")

        self._initialized = True
        logger.info("virtuals_integration_service_initialized")

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        # Shutdown GAME client
        if self._game_client:
            await self._game_client.close()
            self._game_client = None

        # Clear agent tracking
        self._agents.clear()
        self._agent_workers.clear()

        self._initialized = False
        self._acp_service = None
        logger.info("virtuals_integration_service_shutdown")

    # ==================== Service Offerings ====================

    async def register_offering(
        self,
        agent_id: str,
        agent_wallet: str,
        offering: JobOffering,
    ) -> JobOffering:
        """
        Register a new service offering.

        This makes the agent's service discoverable by other agents.
        The offering is stored in the database and optionally
        registered on-chain.

        Args:
            agent_id: ID of the agent offering the service
            agent_wallet: Wallet address of the agent
            offering: The service offering details

        Returns:
            The registered offering with IDs assigned
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.register_offering(
            agent_id=agent_id,
            agent_wallet=agent_wallet,
            offering=offering,
        )

    async def search_offerings(
        self,
        service_type: str | None = None,
        query: str | None = None,
        max_fee: float | None = None,
        min_provider_reputation: float = 0.0,
        limit: int = 20,
    ) -> list[JobOffering]:
        """
        Search available service offerings.

        Args:
            service_type: Filter by service type
            query: Natural language search query
            max_fee: Maximum acceptable fee
            min_provider_reputation: Minimum provider reputation
            limit: Maximum results to return

        Returns:
            List of matching offerings
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            return []
        offerings: list[JobOffering] = await self._acp_service.search_offerings(
            service_type=service_type,
            query=query,
            max_fee=max_fee,
            min_provider_reputation=min_provider_reputation,
            limit=limit,
        )
        return offerings

    async def get_offering(self, offering_id: str) -> JobOffering | None:
        """Get a specific offering by ID."""
        return await self._offering_repo.get_by_id(offering_id)

    async def get_agent_offerings(self, agent_id: str) -> list[JobOffering]:
        """Get all offerings for a specific agent."""
        offerings: list[JobOffering] = await self._offering_repo.get_by_agent(agent_id)
        return offerings

    # ==================== Job Lifecycle ====================

    async def create_job(
        self,
        create_request: ACPJobCreate,
        buyer_wallet: str,
    ) -> ACPJob:
        """
        Create a new ACP job from an offering.

        This initiates the Request phase of the ACP protocol.

        Args:
            create_request: Job creation details
            buyer_wallet: Buyer's wallet address

        Returns:
            The created job in REQUEST phase
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.create_job(
            create_request=create_request,
            buyer_wallet=buyer_wallet,
        )

    async def respond_to_job(
        self,
        job_id: str,
        terms: ACPNegotiationTerms,
        provider_wallet: str,
    ) -> ACPJob:
        """
        Provider responds to a job request with proposed terms.

        This transitions the job from REQUEST to NEGOTIATION phase.

        Args:
            job_id: ID of the job
            terms: Proposed terms
            provider_wallet: Provider's wallet address

        Returns:
            Updated job in NEGOTIATION phase
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.respond_to_request(
            job_id=job_id,
            terms=terms,
            provider_wallet=provider_wallet,
        )

    async def accept_terms(
        self,
        job_id: str,
        buyer_wallet: str,
    ) -> ACPJob:
        """
        Buyer accepts the proposed terms and initiates escrow.

        This transitions the job from NEGOTIATION to TRANSACTION phase
        and locks funds in escrow.

        Args:
            job_id: ID of the job
            buyer_wallet: Buyer's wallet address

        Returns:
            Updated job in TRANSACTION phase
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.accept_terms(
            job_id=job_id,
            buyer_wallet=buyer_wallet,
        )

    async def submit_deliverable(
        self,
        job_id: str,
        deliverable: ACPDeliverable,
        provider_wallet: str,
    ) -> ACPJob:
        """
        Provider submits deliverables for the job.

        This transitions the job to EVALUATION phase.

        Args:
            job_id: ID of the job
            deliverable: The deliverable content
            provider_wallet: Provider's wallet address

        Returns:
            Updated job awaiting evaluation
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.submit_deliverable(
            job_id=job_id,
            deliverable=deliverable,
            provider_wallet=provider_wallet,
        )

    async def evaluate_deliverable(
        self,
        job_id: str,
        evaluation: ACPEvaluation,
        evaluator_wallet: str,
    ) -> ACPJob:
        """
        Evaluate the deliverable and settle the transaction.

        This is the final phase - approval releases escrow to provider.

        Args:
            job_id: ID of the job
            evaluation: Evaluation result
            evaluator_wallet: Evaluator's wallet address

        Returns:
            Completed job with evaluation recorded
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.evaluate_deliverable(
            job_id=job_id,
            evaluation=evaluation,
            evaluator_wallet=evaluator_wallet,
        )

    async def file_dispute(
        self,
        job_id: str,
        dispute: ACPDispute,
        filer_wallet: str,
    ) -> ACPJob:
        """
        File a dispute for a job.

        Args:
            job_id: ID of the job
            dispute: Dispute details
            filer_wallet: Filer's wallet address

        Returns:
            Updated job with dispute recorded
        """
        self._ensure_acp_enabled()

        if self._acp_service is None:
            raise RuntimeError("ACP service not initialized")
        return await self._acp_service.file_dispute(
            job_id=job_id,
            dispute=dispute,
            filer_wallet=filer_wallet,
        )

    # ==================== Job Queries ====================

    async def get_job(self, job_id: str) -> ACPJob | None:
        """Get a job by ID."""
        return await self._job_repo.get_by_id(job_id)

    async def get_buyer_jobs(
        self,
        buyer_agent_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ACPJob]:
        """Get jobs where agent is the buyer."""
        from forge.virtuals.models.base import ACPJobStatus

        status_enum = ACPJobStatus(status) if status else None
        jobs: list[ACPJob] = await self._job_repo.list_by_buyer(
            buyer_agent_id=buyer_agent_id,
            status=status_enum,
            limit=limit,
        )
        return jobs

    async def get_provider_jobs(
        self,
        provider_agent_id: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ACPJob]:
        """Get jobs where agent is the provider."""
        from forge.virtuals.models.base import ACPJobStatus

        status_enum = ACPJobStatus(status) if status else None
        jobs: list[ACPJob] = await self._job_repo.list_by_provider(
            provider_agent_id=provider_agent_id,
            status=status_enum,
            limit=limit,
        )
        return jobs

    async def get_pending_jobs(self, agent_id: str) -> list[ACPJob]:
        """Get jobs pending action by an agent."""
        jobs: list[ACPJob] = await self._job_repo.get_pending_jobs(agent_id)
        return jobs

    # ==================== Agent Gateway Bridge ====================

    async def create_offering_from_agent_session(
        self,
        session_id: str,
        agent_gateway_service: Any,
        service_type: str,
        title: str,
        description: str,
        base_fee_virtual: float,
    ) -> JobOffering:
        """
        Create an ACP offering from an Agent Gateway session.

        This bridges the Agent Gateway's capabilities to ACP's
        service offering system.

        Args:
            session_id: Agent Gateway session ID
            agent_gateway_service: The Agent Gateway service instance
            service_type: Type of service
            title: Offering title
            description: Offering description
            base_fee_virtual: Base fee in VIRTUAL tokens

        Returns:
            Created offering
        """
        # Get session details from Agent Gateway
        session = await agent_gateway_service.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Create offering based on session capabilities
        offering = JobOffering(
            provider_agent_id=session.agent_id,
            provider_wallet=session.metadata.get("wallet_address", ""),
            service_type=service_type,
            title=title,
            description=description,
            base_fee_virtual=base_fee_virtual,
            input_schema=self._capabilities_to_input_schema(session.capabilities),
            output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
        )

        return await self.register_offering(
            agent_id=session.agent_id,
            agent_wallet=offering.provider_wallet,
            offering=offering,
        )

    def _capabilities_to_input_schema(self, capabilities: list[Any]) -> dict[str, Any]:
        """Convert Agent Gateway capabilities to JSON schema."""
        properties = {}

        for cap in capabilities:
            cap_value = cap.value if hasattr(cap, "value") else str(cap)

            if cap_value == "query_graph":
                properties["query_text"] = {
                    "type": "string",
                    "description": "Natural language query",
                }
            elif cap_value == "semantic_search":
                properties["query"] = {"type": "string", "description": "Semantic search query"}
            elif cap_value == "create_capsules":
                properties["capsule_data"] = {
                    "type": "object",
                    "description": "Capsule creation data",
                }

        return {"type": "object", "properties": properties}

    # ==================== Helpers ====================

    def _ensure_acp_enabled(self) -> None:
        """Ensure ACP is enabled and initialized."""
        if not self._config.acp_enabled:
            raise RuntimeError("ACP is not enabled")
        if not self._initialized or not self._acp_service:
            raise RuntimeError("Service not initialized - call initialize() first")

    def _ensure_game_enabled(self) -> None:
        """Ensure GAME is enabled and initialized."""
        if not self._config.game_enabled:
            raise RuntimeError("GAME SDK is not enabled")
        if not self._initialized or not self._game_client:
            raise RuntimeError("Service not initialized - call initialize() first")

    # ==================== GAME SDK: Agent Management ====================

    async def create_game_agent(
        self,
        name: str,
        primary_goal: str,
        description: str,
        worker_types: list[str] | None = None,
        agent_wallet: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new GAME agent with Forge capabilities.

        This creates an autonomous agent that can interact with Forge's
        knowledge base, run overlays, and participate in governance.

        Args:
            name: Unique name for the agent
            primary_goal: The agent's primary objective
            description: Agent personality/behavior description
            worker_types: List of worker types to enable
                         Options: knowledge, analysis, governance
            agent_wallet: Wallet address for governance votes
            metadata: Additional agent metadata

        Returns:
            Created agent details with ID
        """
        self._ensure_game_enabled()

        # Default to all workers if not specified
        if worker_types is None:
            worker_types = ["knowledge", "analysis"]

        # Create workers based on requested types
        workers: list[GAMEWorker] = []
        workers_dict: dict[str, GAMEWorker] = {}

        if "knowledge" in worker_types and self._capsule_repo:
            worker = create_knowledge_worker(self._capsule_repo)
            workers.append(worker)
            workers_dict[worker.worker_id] = worker

        if "analysis" in worker_types and self._overlay_manager:
            worker = create_analysis_worker(self._overlay_manager)
            workers.append(worker)
            workers_dict[worker.worker_id] = worker

        if "governance" in worker_types and self._governance_service and agent_wallet:
            worker = create_governance_worker(
                self._governance_service,
                agent_wallet,
            )
            workers.append(worker)
            workers_dict[worker.worker_id] = worker

        if not workers:
            raise ValueError(
                "No workers could be created. Ensure required repositories/services are provided."
            )

        # Create agent request
        from forge.virtuals.models import (
            AgentGoals,
            AgentPersonality,
            ForgeAgentCreate,
        )

        create_request = ForgeAgentCreate(
            name=name,
            personality=AgentPersonality(
                name=name,
                description=description,
                personality_traits=metadata.get("traits", []) if metadata else [],
            ),
            goals=AgentGoals(
                primary_goal=primary_goal,
                secondary_goals=metadata.get("secondary_goals", []) if metadata else [],
            ),
            primary_chain=self._config.primary_chain,
        )

        if self._game_client is None:
            raise RuntimeError("GAME SDK client not initialized")
        agent = await self._game_client.create_agent(create_request, workers)

        # Store agent and workers for later use
        self._agents[agent.id] = agent
        self._agent_workers[agent.id] = workers_dict

        logger.info(
            "game_agent_created",
            agent_id=agent.id,
            name=name,
            workers=list(workers_dict.keys()),
        )

        return {
            "id": agent.id,
            "name": agent.name,
            "game_agent_id": agent.game_agent_id,
            "status": agent.status.value if hasattr(agent.status, "value") else str(agent.status),
            "workers": list(workers_dict.keys()),
            "primary_goal": primary_goal,
            "created_at": agent.created_at.isoformat() if hasattr(agent, "created_at") else None,
        }

    async def get_game_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get a GAME agent by ID."""
        self._ensure_game_enabled()

        if agent_id in self._agents:
            agent = self._agents[agent_id]
            return {
                "id": agent.id,
                "name": agent.name,
                "game_agent_id": agent.game_agent_id,
                "status": agent.status.value
                if hasattr(agent.status, "value")
                else str(agent.status),
                "workers": list(self._agent_workers.get(agent_id, {}).keys()),
            }

        if self._game_client is None:
            return None
        agent_result = await self._game_client.get_agent(agent_id)
        if agent_result is None:
            return None
        # Convert ForgeAgent to dict format for API response
        return {
            "id": agent_result.id,
            "name": agent_result.name,
            "game_agent_id": agent_result.game_agent_id,
            "status": agent_result.status.value
            if hasattr(agent_result.status, "value")
            else str(agent_result.status),
            "workers": [],
        }

    async def delete_game_agent(self, agent_id: str) -> bool:
        """Delete a GAME agent."""
        self._ensure_game_enabled()

        if self._game_client is None:
            return False
        success: bool = await self._game_client.delete_agent(agent_id)
        if success:
            self._agents.pop(agent_id, None)
            self._agent_workers.pop(agent_id, None)
            logger.info("game_agent_deleted", agent_id=agent_id)
        return success

    async def list_game_agents(self) -> list[dict[str, Any]]:
        """List all registered GAME agents."""
        self._ensure_game_enabled()

        return [
            {
                "id": agent.id,
                "name": agent.name,
                "game_agent_id": agent.game_agent_id,
                "status": agent.status.value
                if hasattr(agent.status, "value")
                else str(agent.status),
                "workers": list(self._agent_workers.get(agent.id, {}).keys()),
            }
            for agent in self._agents.values()
        ]

    # ==================== GAME SDK: Agent Execution ====================

    async def run_game_agent(
        self,
        agent_id: str,
        context: str | None = None,
        max_iterations: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run a GAME agent's autonomous decision loop.

        This starts the agent's planning-execution cycle where it
        continuously decides and executes actions until completion.

        Args:
            agent_id: ID of the agent to run
            context: Initial context or user query
            max_iterations: Maximum action cycles (default from config)

        Returns:
            List of action results from each iteration
        """
        self._ensure_game_enabled()

        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]
        workers = self._agent_workers.get(agent_id, {})

        if not workers:
            raise ValueError(f"No workers configured for agent {agent_id}")

        max_iter = max_iterations or self._config.game_max_agent_iterations

        logger.info(
            "game_agent_run_starting",
            agent_id=agent_id,
            context_length=len(context) if context else 0,
            max_iterations=max_iter,
        )

        if self._game_client is None:
            return []
        results: list[dict[str, Any]] = await self._game_client.run_agent_loop(
            agent=agent,
            workers=workers,
            context=context,
            max_iterations=max_iter,
        )

        logger.info(
            "game_agent_run_completed",
            agent_id=agent_id,
            iterations=len(results),
        )

        return results

    async def get_agent_next_action(
        self,
        agent_id: str,
        current_state: dict[str, Any] | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Get the next action for an agent without executing it.

        This is useful for step-by-step execution or debugging.

        Args:
            agent_id: ID of the agent
            current_state: Optional override for current state
            context: Optional additional context

        Returns:
            The next action the agent would take
        """
        self._ensure_game_enabled()

        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]

        if current_state is None:
            current_state = {}
            workers = self._agent_workers.get(agent_id, {})
            for worker_id, worker in workers.items():
                current_state[worker_id] = worker.get_state()

        if self._game_client is None:
            return {}
        action: dict[str, Any] = await self._game_client.get_next_action(
            agent.game_agent_id,
            current_state,
            context,
        )
        return action

    # ==================== GAME SDK: Memory Operations ====================

    async def store_agent_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: dict[str, Any],
        ttl_days: int | None = None,
    ) -> str:
        """
        Store a memory for an agent.

        Memories persist across sessions and enable agent learning.

        Args:
            agent_id: The agent to store memory for
            memory_type: Category (conversation, fact, preference)
            content: The memory content
            ttl_days: Optional time-to-live

        Returns:
            The stored memory ID
        """
        self._ensure_game_enabled()

        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]

        if self._game_client is None:
            return ""
        memory_id: str = await self._game_client.store_memory(
            agent.game_agent_id,
            memory_type,
            content,
            ttl_days,
        )
        return memory_id

    async def search_agent_memories(
        self,
        agent_id: str,
        query: str,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search an agent's memories.

        Uses semantic search to find relevant memories.

        Args:
            agent_id: The agent to search memories for
            query: Search query
            memory_type: Optional filter by type
            limit: Maximum results

        Returns:
            List of matching memories
        """
        self._ensure_game_enabled()

        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]

        if self._game_client is None:
            return []
        memories: list[dict[str, Any]] = await self._game_client.retrieve_memories(
            agent.game_agent_id,
            query,
            memory_type,
            limit,
        )
        return memories

    # ==================== GAME SDK: Function Discovery ====================

    def get_available_functions(self) -> list[dict[str, Any]]:
        """
        Get all available Forge functions for GAME agents.

        Returns function definitions that can be used when creating agents.
        """
        functions = []

        if self._capsule_repo:
            functions.extend(
                [
                    {
                        "name": "search_capsules",
                        "worker": "knowledge_worker",
                        "description": "Search knowledge capsules by semantic similarity",
                    },
                    {
                        "name": "get_capsule",
                        "worker": "knowledge_worker",
                        "description": "Retrieve full capsule content by ID",
                    },
                    {
                        "name": "create_capsule",
                        "worker": "knowledge_worker",
                        "description": "Create a new knowledge capsule",
                    },
                ]
            )

        if self._overlay_manager:
            functions.extend(
                [
                    {
                        "name": "run_overlay",
                        "worker": "analysis_worker",
                        "description": "Execute a Forge overlay for analysis",
                    },
                    {
                        "name": "list_overlays",
                        "worker": "analysis_worker",
                        "description": "List available analysis overlays",
                    },
                ]
            )

        if self._governance_service:
            functions.extend(
                [
                    {
                        "name": "get_proposals",
                        "worker": "governance_worker",
                        "description": "Get governance proposals",
                    },
                    {
                        "name": "cast_vote",
                        "worker": "governance_worker",
                        "description": "Cast a vote on a proposal",
                    },
                ]
            )

        return functions


# Global service instance
_virtuals_service: VirtualsIntegrationService | None = None


def get_virtuals_config() -> VirtualsIntegrationConfig:
    """Create config from settings."""
    settings = get_settings()
    return VirtualsIntegrationConfig(
        acp_enabled=settings.acp_enabled,
        game_enabled=settings.game_enabled,
        primary_chain=settings.virtuals_primary_chain,
        base_rpc_url=settings.base_rpc_url,
        base_chain_id=settings.base_chain_id,
        base_private_key=settings.base_private_key,
        acp_escrow_contract_address=settings.acp_escrow_contract_address,
        acp_registry_contract_address=settings.acp_registry_contract_address,
        virtual_token_address=settings.virtual_token_address,
        solana_rpc_url=settings.solana_rpc_url,
        solana_private_key=settings.solana_private_key,
        solana_acp_program_id=settings.solana_acp_program_id,
        frowg_token_address=settings.frowg_token_address,
        default_escrow_timeout_hours=settings.acp_default_escrow_timeout_hours,
        evaluation_timeout_hours=settings.acp_evaluation_timeout_hours,
        max_job_fee_virtual=settings.acp_max_job_fee_virtual,
        # GAME SDK settings
        game_api_key=settings.game_api_key,
        game_api_base_url=getattr(settings, "game_api_base_url", "https://game.virtuals.io/api"),
        game_api_rate_limit=getattr(settings, "game_api_rate_limit", 100),
        game_max_agent_iterations=getattr(settings, "game_max_agent_iterations", 50),
    )


async def init_virtuals_service(
    db_client: Neo4jClient,
    config: VirtualsIntegrationConfig | None = None,
) -> VirtualsIntegrationService:
    """
    Initialize the global Virtuals integration service.

    Args:
        db_client: Neo4j database client
        config: Optional configuration (uses settings if not provided)

    Returns:
        Initialized service instance
    """
    global _virtuals_service

    if config is None:
        config = get_virtuals_config()

    _virtuals_service = VirtualsIntegrationService(
        config=config,
        db_client=db_client,
    )
    await _virtuals_service.initialize()

    return _virtuals_service


def get_virtuals_service() -> VirtualsIntegrationService:
    """Get the global Virtuals integration service instance."""
    global _virtuals_service
    if _virtuals_service is None:
        raise RuntimeError("Virtuals service not initialized - call init_virtuals_service() first")
    return _virtuals_service


async def shutdown_virtuals_service() -> None:
    """Shutdown the global Virtuals integration service."""
    global _virtuals_service
    if _virtuals_service is not None:
        await _virtuals_service.shutdown()
    _virtuals_service = None
