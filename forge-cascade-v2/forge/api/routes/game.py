"""
GAME SDK API Routes

Endpoints for managing autonomous AI agents using Virtuals Protocol's
GAME (Generative Autonomous Multimodal Entities) framework.

GAME provides the decision-making engine that powers autonomous agents:
- Task Generator (High-Level Planner) - Determines what the agent should do
- Workers (Low-Level Planners) - Execute specific types of tasks
- Functions - The actual actions workers can take
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from forge.api.dependencies import ActiveUserDep, OptionalUserDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["GAME SDK"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AgentPersonalityRequest(BaseModel):
    """Agent personality configuration."""
    name: str = Field(max_length=100)
    bio: str = Field(max_length=1000)
    traits: list[str] = Field(default_factory=list, max_length=10)
    communication_style: str = Field(default="professional")
    expertise_areas: list[str] = Field(default_factory=list)


class AgentGoalsRequest(BaseModel):
    """Agent goals configuration."""
    primary_goal: str = Field(max_length=500)
    secondary_goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class WorkerConfig(BaseModel):
    """Worker configuration."""
    worker_id: str
    description: str
    function_names: list[str]


class CreateAgentRequest(BaseModel):
    """Request to create a GAME agent."""
    name: str = Field(max_length=100)
    personality: AgentPersonalityRequest
    goals: AgentGoalsRequest
    workers: list[WorkerConfig] = Field(default_factory=list)
    forge_overlay_id: str | None = None
    forge_capsule_ids: list[str] = Field(default_factory=list)
    enable_memory: bool = True
    primary_chain: str = Field(default="base")


class AgentResponse(BaseModel):
    """Agent information response."""
    id: str
    name: str
    status: str
    game_agent_id: str | None
    personality: dict[str, Any]
    goals: dict[str, Any]
    workers: list[dict[str, Any]]
    forge_overlay_id: str | None
    forge_capsule_ids: list[str]
    primary_chain: str
    created_at: datetime
    updated_at: datetime


class RunAgentRequest(BaseModel):
    """Request to run an agent loop."""
    context: str | None = Field(None, max_length=5000, description="Initial context or query")
    max_iterations: int = Field(default=10, ge=1, le=100)
    stop_on_done: bool = True


class AgentRunResponse(BaseModel):
    """Response from agent run."""
    agent_id: str
    run_id: str
    status: str
    iterations_completed: int
    results: list[dict[str, Any]]
    final_state: dict[str, Any]


class AgentActionResponse(BaseModel):
    """Single action result."""
    iteration: int
    worker_id: str
    function_name: str
    arguments: dict[str, Any]
    status: str
    result: Any
    reasoning: str


class StoreMemoryRequest(BaseModel):
    """Request to store agent memory."""
    memory_type: str = Field(description="Type: conversation, fact, preference, insight")
    content: dict[str, Any]
    ttl_days: int | None = None


class SearchMemoryRequest(BaseModel):
    """Request to search agent memories."""
    query: str = Field(max_length=500)
    memory_type: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


# ============================================================================
# Agent Management Endpoints
# ============================================================================

@router.post("/agents", response_model=AgentResponse)
async def create_agent(
    request: CreateAgentRequest,
    current_user: ActiveUserDep,
) -> AgentResponse:
    """
    Create a new GAME agent.

    This registers an agent with the GAME framework, setting up its
    personality, goals, and worker configuration. The agent can then
    be started to begin autonomous operation.
    """
    try:
        from forge.services.virtuals_integration import get_virtuals_service
        from forge.virtuals.game.sdk_client import GAMEWorker, get_game_client
        from forge.virtuals.models import (
            AgentGoals,
            AgentPersonality,
            ForgeAgentCreate,
        )

        # Build personality
        personality = AgentPersonality(
            name=request.personality.name,
            description=request.personality.bio,
            personality_traits=request.personality.traits,
            communication_style=request.personality.communication_style,
            expertise_domains=request.personality.expertise_areas,
        )

        # Build goals
        goals = AgentGoals(
            primary_goal=request.goals.primary_goal,
            secondary_goals=request.goals.secondary_goals,
            constraints=request.goals.constraints,
            success_metrics=request.goals.success_criteria,
        )

        # Create agent request
        create_request = ForgeAgentCreate(
            name=request.name,
            personality=personality,
            goals=goals,
            forge_overlay_id=request.forge_overlay_id,
            forge_capsule_ids=request.forge_capsule_ids,
            primary_chain=request.primary_chain,
        )

        # Get GAME client and create workers
        game_client = await get_game_client()

        # Create default Forge workers if none specified
        workers = []
        if not request.workers:
            # Create knowledge worker with Forge functions
            from forge.database.client import get_db_client
            from forge.repositories.capsule_repository import CapsuleRepository
            from forge.virtuals.game.forge_functions import (
                create_analysis_worker,
                create_knowledge_worker,
            )

            db_client = await get_db_client()
            capsule_repo = CapsuleRepository(db_client)

            workers.append(create_knowledge_worker(capsule_repo))  # type: ignore[arg-type]
        else:
            # Use specified worker configs
            for wc in request.workers:
                workers.append(GAMEWorker(
                    worker_id=wc.worker_id,
                    description=wc.description,
                    functions=[],  # Functions would be registered separately
                ))

        # Create agent via GAME SDK
        agent = await game_client.create_agent(create_request, workers)

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=agent.status.value,
            game_agent_id=agent.game_agent_id,
            personality=personality.model_dump(),
            goals=goals.model_dump(),
            workers=[{"id": w.id, "name": w.name, "description": w.description} for w in agent.workers],
            forge_overlay_id=agent.forge_overlay_id,
            forge_capsule_ids=agent.forge_capsule_ids,
            primary_chain=agent.primary_chain,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"GAME SDK not available: {e}")
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create agent")


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str) -> AgentResponse:
    """Get agent details by ID."""
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()
        agent = await game_client.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=agent.status.value,
            game_agent_id=agent.game_agent_id,
            personality=agent.personality.model_dump() if agent.personality else {},
            goals=agent.goals.model_dump() if agent.goals else {},
            workers=[{"id": w.id, "name": w.name, "description": w.description} for w in agent.workers],
            forge_overlay_id=agent.forge_overlay_id,
            forge_capsule_ids=agent.forge_capsule_ids,
            primary_chain=agent.primary_chain,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent")


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: ActiveUserDep,
) -> dict[str, str]:
    """Delete an agent."""
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()
        success = await game_client.delete_agent(agent_id)

        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")

        return {"status": "deleted", "agent_id": agent_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")


# ============================================================================
# Agent Execution Endpoints
# ============================================================================

@router.post("/agents/{agent_id}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_id: str,
    request: RunAgentRequest,
    background_tasks: BackgroundTasks,
    current_user: ActiveUserDep,
) -> AgentRunResponse:
    """
    Run the agent's autonomous decision loop.

    This starts the continuous planning-execution cycle:
    1. Gather current state from all workers
    2. Request next action from GAME API
    3. Execute the action via the appropriate worker
    4. Update state and repeat

    The loop continues until max_iterations is reached or
    the agent decides it has completed its task.
    """
    try:
        from uuid import uuid4

        from forge.database.client import get_db_client
        from forge.repositories.capsule_repository import CapsuleRepository
        from forge.virtuals.game.forge_functions import (
            create_knowledge_worker,
        )
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()
        agent = await game_client.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get database client and create workers
        db_client = await get_db_client()
        capsule_repo = CapsuleRepository(db_client)

        # Create Forge workers
        workers = {
            "knowledge_worker": create_knowledge_worker(capsule_repo),  # type: ignore[arg-type]
        }

        # Run the agent loop
        results = await game_client.run_agent_loop(
            agent=agent,
            workers=workers,
            context=request.context,
            max_iterations=request.max_iterations,
        )

        run_id = str(uuid4())

        return AgentRunResponse(
            agent_id=agent_id,
            run_id=run_id,
            status="completed",
            iterations_completed=len(results),
            results=results,
            final_state={w_id: w.get_state() for w_id, w in workers.items()},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run agent: {e}")


@router.post("/agents/{agent_id}/action", response_model=AgentActionResponse)
async def get_next_action(
    agent_id: str,
    current_state: dict[str, Any],
    context: str | None = None,
    current_user: OptionalUserDep = None,
) -> AgentActionResponse:
    """
    Get the next action for an agent without executing it.

    This is useful for debugging or when you want to control
    the execution manually.
    """
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()
        agent = await game_client.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        if not agent.game_agent_id:
            raise HTTPException(status_code=400, detail="Agent not registered with GAME framework")

        action = await game_client.get_next_action(
            agent.game_agent_id,
            current_state,
            context,
        )

        return AgentActionResponse(
            iteration=0,
            worker_id=action.get("worker_id", ""),
            function_name=action.get("function_name", ""),
            arguments=action.get("arguments", {}),
            status="pending",
            result=None,
            reasoning=action.get("reasoning", ""),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get next action: {e}")
        raise HTTPException(status_code=500, detail="Failed to get next action")


# ============================================================================
# Memory Endpoints
# ============================================================================

@router.post("/agents/{agent_id}/memories")
async def store_memory(
    agent_id: str,
    request: StoreMemoryRequest,
    current_user: ActiveUserDep,
) -> dict[str, str]:
    """
    Store a memory for an agent.

    Memories persist across sessions and can be retrieved by the agent
    during future interactions. This enables continuity and learning.
    """
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()

        memory_id = await game_client.store_memory(
            agent_id=agent_id,
            memory_type=request.memory_type,
            content=request.content,
            ttl_days=request.ttl_days,
        )

        return {
            "memory_id": memory_id,
            "agent_id": agent_id,
            "memory_type": request.memory_type,
            "status": "stored",
        }

    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to store memory")


@router.post("/agents/{agent_id}/memories/search")
async def search_memories(
    agent_id: str,
    request: SearchMemoryRequest,
) -> dict[str, Any]:
    """
    Search agent memories using semantic similarity.

    Returns memories relevant to the query, useful for providing
    context to the agent during interactions.
    """
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        game_client = await get_game_client()

        memories = await game_client.retrieve_memories(
            agent_id=agent_id,
            query=request.query,
            memory_type=request.memory_type,
            limit=request.limit,
        )

        return {
            "agent_id": agent_id,
            "query": request.query,
            "memories": memories,
            "count": len(memories),
        }

    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail="Failed to search memories")


# ============================================================================
# Worker Function Endpoints
# ============================================================================

@router.get("/functions")
async def list_available_functions() -> dict[str, Any]:
    """
    List all available Forge functions for GAME workers.

    These functions can be used when creating agents to define
    what actions the agent can take.
    """
    return {
        "functions": [
            {
                "name": "search_capsules",
                "description": "Search the Forge knowledge base for relevant information",
                "worker": "knowledge_worker",
                "arguments": [
                    {"name": "query", "type": "string", "required": True},
                    {"name": "capsule_types", "type": "string", "required": False},
                    {"name": "limit", "type": "integer", "required": False},
                    {"name": "min_trust_level", "type": "number", "required": False},
                ],
            },
            {
                "name": "get_capsule",
                "description": "Retrieve the full content of a specific capsule",
                "worker": "knowledge_worker",
                "arguments": [
                    {"name": "capsule_id", "type": "string", "required": True},
                ],
            },
            {
                "name": "create_capsule",
                "description": "Create a new knowledge capsule",
                "worker": "knowledge_worker",
                "arguments": [
                    {"name": "title", "type": "string", "required": True},
                    {"name": "content", "type": "string", "required": True},
                    {"name": "capsule_type", "type": "string", "required": True},
                    {"name": "tags", "type": "string", "required": False},
                    {"name": "parent_capsule_id", "type": "string", "required": False},
                ],
            },
            {
                "name": "run_overlay",
                "description": "Execute a Forge overlay for analysis",
                "worker": "analysis_worker",
                "arguments": [
                    {"name": "overlay_id", "type": "string", "required": True},
                    {"name": "input_data", "type": "string", "required": True},
                    {"name": "parameters", "type": "string", "required": False},
                ],
            },
            {
                "name": "list_overlays",
                "description": "List available analysis overlays",
                "worker": "analysis_worker",
                "arguments": [
                    {"name": "status_filter", "type": "string", "required": False},
                ],
            },
            {
                "name": "get_proposals",
                "description": "Get governance proposals",
                "worker": "governance_worker",
                "arguments": [
                    {"name": "status_filter", "type": "string", "required": False},
                    {"name": "limit", "type": "integer", "required": False},
                ],
            },
            {
                "name": "cast_vote",
                "description": "Cast a vote on a governance proposal",
                "worker": "governance_worker",
                "arguments": [
                    {"name": "proposal_id", "type": "string", "required": True},
                    {"name": "vote", "type": "string", "required": True},
                    {"name": "reasoning", "type": "string", "required": True},
                ],
            },
        ],
        "workers": [
            {
                "id": "knowledge_worker",
                "description": "Handles knowledge capsule operations",
                "functions": ["search_capsules", "get_capsule", "create_capsule"],
            },
            {
                "id": "analysis_worker",
                "description": "Runs overlay analyses",
                "functions": ["run_overlay", "list_overlays"],
            },
            {
                "id": "governance_worker",
                "description": "Participates in governance",
                "functions": ["get_proposals", "cast_vote"],
            },
        ],
    }
