"""
GAME Framework Integration Package

This package provides the integration between Forge and Virtuals Protocol's
GAME (Generative Autonomous Multimodal Entities) framework.

The GAME framework is a modular agentic architecture that enables AI agents
to plan actions and make decisions autonomously. This package bridges that
capability with Forge's knowledge management, governance, and analysis systems.

Key Components:
    - GAMESDKClient: Client for communicating with the GAME API
    - GAMEWorker: Low-level planner that executes specific types of tasks
    - FunctionDefinition: Atomic actions that workers can perform
    - forge_functions: Pre-built functions for Forge capabilities

Example Usage:
    from forge.virtuals.game import (
        get_game_client,
        create_knowledge_worker,
        create_governance_worker,
    )

    async def create_knowledge_agent():
        client = await get_game_client()

        # Create workers with Forge capabilities
        knowledge_worker = create_knowledge_worker(capsule_repository)
        governance_worker = create_governance_worker(governance_service, wallet)

        # Create the agent
        agent = await client.create_agent(
            create_request=agent_config,
            workers=[knowledge_worker, governance_worker],
        )

        # Run the agent loop
        results = await client.run_agent_loop(
            agent=agent,
            workers={
                "knowledge_worker": knowledge_worker,
                "governance_worker": governance_worker,
            },
            context="Answer questions about our Q3 strategy",
        )
"""

from .forge_functions import (
    # Status constants
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    create_analysis_worker,
    create_cast_vote_function,
    create_create_capsule_function,
    create_get_capsule_function,
    create_get_proposals_function,
    create_governance_worker,
    # Worker factories
    create_knowledge_worker,
    create_list_overlays_function,
    create_run_overlay_function,
    # Function factories
    create_search_capsules_function,
)
from .sdk_client import (
    AgentNotFoundError,
    AuthenticationError,
    # Building blocks
    FunctionDefinition,
    # Exceptions
    GAMEClientError,
    # Main client
    GAMESDKClient,
    GAMEWorker,
    RateLimitError,
    get_game_client,
)

__all__ = [
    # Client
    "GAMESDKClient",
    "get_game_client",
    # Building blocks
    "FunctionDefinition",
    "GAMEWorker",
    # Exceptions
    "GAMEClientError",
    "AuthenticationError",
    "RateLimitError",
    "AgentNotFoundError",
    # Function factories
    "create_search_capsules_function",
    "create_get_capsule_function",
    "create_create_capsule_function",
    "create_run_overlay_function",
    "create_list_overlays_function",
    "create_get_proposals_function",
    "create_cast_vote_function",
    # Worker factories
    "create_knowledge_worker",
    "create_analysis_worker",
    "create_governance_worker",
    # Constants
    "STATUS_DONE",
    "STATUS_FAILED",
    "STATUS_PENDING",
]
