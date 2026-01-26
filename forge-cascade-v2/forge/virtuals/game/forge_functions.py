"""
Pre-built Forge Functions for GAME Agents

This module provides ready-to-use function definitions that allow GAME agents
to interact with Forge's core capabilities: knowledge capsules, overlays,
governance, and compliance checking.

These functions form the bridge between Virtuals Protocol's autonomous agents
and Forge's institutional memory architecture. By exposing Forge capabilities
as GAME functions, agents can autonomously query knowledge, run analyses,
and participate in governance.

Usage:
    from forge.virtuals.game.forge_functions import (
        create_knowledge_worker,
        create_governance_worker,
    )

    # Create workers with Forge capabilities
    knowledge_worker = create_knowledge_worker(capsule_repository)
    governance_worker = create_governance_worker(governance_service)
"""

import json
import logging
from datetime import UTC, datetime
from typing import cast

from .protocols import (
    CapsuleRepositoryProtocol,
    GovernanceServiceProtocol,
    OverlayManagerProtocol,
)
from .sdk_client import FunctionDefinition, GAMEWorker

logger = logging.getLogger(__name__)


# ==================== Function Result Statuses ====================
# These constants match the GAME SDK's expected status values

STATUS_DONE = "DONE"        # Function completed successfully
STATUS_FAILED = "FAILED"    # Function encountered an error
STATUS_PENDING = "PENDING"  # Function started async operation


# ==================== Knowledge Capsule Functions ====================

def create_search_capsules_function(
    capsule_repository: CapsuleRepositoryProtocol,
) -> FunctionDefinition:
    """
    Create a function for searching knowledge capsules.

    This function allows agents to perform semantic search across the
    Forge knowledge base, finding relevant capsules based on natural
    language queries.

    Args:
        capsule_repository: The Forge CapsuleRepository instance

    Returns:
        FunctionDefinition for capsule search
    """
    async def search_capsules(
        query: str,
        capsule_types: str | None = None,
        limit: int = 10,
        min_trust_level: float = 0.0,
    ) -> tuple[str, object, dict[str, object]]:
        """
        Search knowledge capsules by semantic similarity.

        This performs a vector similarity search across all capsules,
        filtering by type and trust level as specified.
        """
        try:
            # Parse capsule types if provided
            types_list = None
            if capsule_types:
                types_list = [t.strip() for t in capsule_types.split(",")]

            # Perform the search using Forge's capsule repository
            results = await capsule_repository.search_semantic(
                query=query,
                capsule_types=types_list,
                limit=limit,
                min_trust_level=min_trust_level,
            )

            # Format results for agent consumption
            formatted_results = []
            for capsule in results:
                formatted_results.append({
                    "id": capsule.id,
                    "title": capsule.title,
                    "type": capsule.capsule_type,
                    "content_preview": capsule.content[:500] if capsule.content else "",
                    "trust_level": capsule.trust_level,
                    "created_at": capsule.created_at.isoformat(),
                    "relevance_score": capsule.relevance_score,
                })

            return STATUS_DONE, formatted_results, {
                "last_search_query": query,
                "results_count": len(formatted_results),
            }

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Capsule search failed: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="search_capsules",
        description=(
            "Search the Forge knowledge base for relevant information. "
            "Use this to find capsules containing knowledge, decisions, "
            "code, insights, or policies that match a query."
        ),
        arguments=[
            {
                "name": "query",
                "type": "string",
                "description": "Natural language search query describing what you're looking for",
            },
            {
                "name": "capsule_types",
                "type": "string",
                "description": (
                    "Optional comma-separated list of capsule types to filter by. "
                    "Options: KNOWLEDGE, CODE, DECISION, INSIGHT, CONFIG, POLICY"
                ),
            },
            {
                "name": "limit",
                "type": "integer",
                "description": "Maximum number of results to return (default: 10)",
            },
            {
                "name": "min_trust_level",
                "type": "number",
                "description": "Minimum trust level for results (0.0 to 1.0)",
            },
        ],
        executable=search_capsules,
        returns_description="List of matching capsules with metadata and content previews",
    )


def create_get_capsule_function(
    capsule_repository: CapsuleRepositoryProtocol,
) -> FunctionDefinition:
    """
    Create a function for retrieving a specific capsule's full content.

    This function allows agents to fetch the complete content of a capsule
    when they need more detail than the search preview provides.
    """
    async def get_capsule(capsule_id: str) -> tuple[str, object, dict[str, object]]:
        """Retrieve the full content and metadata of a specific capsule."""
        try:
            capsule = await capsule_repository.get_by_id(capsule_id)

            if not capsule:
                return STATUS_FAILED, f"Capsule {capsule_id} not found", {}

            result = {
                "id": capsule.id,
                "title": capsule.title,
                "type": capsule.capsule_type,
                "content": capsule.content,
                "trust_level": capsule.trust_level,
                "version": capsule.version,
                "created_at": capsule.created_at.isoformat(),
                "updated_at": capsule.updated_at.isoformat(),
                "tags": capsule.tags,
                "lineage": {
                    "parent_ids": capsule.parent_ids,
                    "derivation_type": capsule.derivation_type,
                },
                "metadata": capsule.metadata,
            }

            return STATUS_DONE, result, {"last_retrieved_capsule": capsule_id}

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Failed to get capsule {capsule_id}: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="get_capsule",
        description=(
            "Retrieve the full content and metadata of a specific knowledge capsule. "
            "Use this after searching to get complete details of a relevant capsule."
        ),
        arguments=[
            {
                "name": "capsule_id",
                "type": "string",
                "description": "The unique identifier of the capsule to retrieve",
            },
        ],
        executable=get_capsule,
        returns_description="Complete capsule content including metadata and lineage information",
    )


def create_create_capsule_function(
    capsule_repository: CapsuleRepositoryProtocol,
) -> FunctionDefinition:
    """
    Create a function for creating new knowledge capsules.

    This allows agents to contribute new knowledge to the Forge system,
    preserving insights and decisions as persistent institutional memory.
    """
    async def create_capsule(
        title: str,
        content: str,
        capsule_type: str,
        tags: str | None = None,
        parent_capsule_id: str | None = None,
    ) -> tuple[str, object, dict[str, object]]:
        """Create a new knowledge capsule in Forge."""
        try:
            # Parse tags if provided
            tags_list: list[str] = []
            if tags:
                tags_list = [t.strip() for t in tags.split(",")]

            # Create the capsule
            capsule = await capsule_repository.create(
                title=title,
                content=content,
                capsule_type=capsule_type,
                owner_id="system",
                tags=tags_list,
                parent_ids=[parent_capsule_id] if parent_capsule_id else [],
            )

            return STATUS_DONE, {
                "id": capsule.id,
                "message": f"Capsule '{title}' created successfully",
            }, {
                "created_capsule_id": capsule.id,
            }

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Failed to create capsule: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="create_capsule",
        description=(
            "Create a new knowledge capsule to store important information, "
            "decisions, code, or insights. The capsule becomes part of Forge's "
            "institutional memory and can be retrieved later."
        ),
        arguments=[
            {
                "name": "title",
                "type": "string",
                "description": "A clear, descriptive title for the capsule",
            },
            {
                "name": "content",
                "type": "string",
                "description": "The main content of the capsule",
            },
            {
                "name": "capsule_type",
                "type": "string",
                "description": (
                    "Type of capsule: KNOWLEDGE, CODE, DECISION, INSIGHT, CONFIG, or POLICY"
                ),
            },
            {
                "name": "tags",
                "type": "string",
                "description": "Optional comma-separated tags for categorization",
            },
            {
                "name": "parent_capsule_id",
                "type": "string",
                "description": (
                    "Optional ID of a parent capsule this derives from "
                    "(maintains lineage tracking)"
                ),
            },
        ],
        executable=create_capsule,
        returns_description="The ID of the newly created capsule",
    )


# ==================== Overlay Analysis Functions ====================

def create_run_overlay_function(
    overlay_manager: OverlayManagerProtocol,
) -> FunctionDefinition:
    """
    Create a function for running Forge overlays.

    Overlays are specialized analysis modules (security, compliance, ML, etc.)
    that can process data and provide insights. This function allows agents
    to invoke overlays and receive their analysis results.
    """
    async def run_overlay(
        overlay_id: str,
        input_data: str,
        parameters: str | None = None,
    ) -> tuple[str, object, dict[str, object]]:
        """
        Execute a Forge overlay with given input data.

        The overlay will process the input according to its specialized
        logic and return analysis results.
        """
        try:
            # Parse parameters if provided (JSON string)
            params_dict = {}
            if parameters:
                params_dict = json.loads(parameters)

            # Run the overlay
            result = await overlay_manager.execute(
                overlay_id=overlay_id,
                input_data=input_data,
                parameters=params_dict,
            )

            return STATUS_DONE, {
                "overlay_id": overlay_id,
                "status": result.status,
                "output": result.output,
                "execution_time_ms": result.execution_time_ms,
                "confidence_score": result.confidence_score,
            }, {
                "last_overlay_run": overlay_id,
                "last_overlay_result": result.status,
            }

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Overlay execution failed: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="run_overlay",
        description=(
            "Execute a Forge overlay to analyze data. Overlays are specialized "
            "modules for tasks like security validation, compliance checking, "
            "ML analysis, and performance optimization."
        ),
        arguments=[
            {
                "name": "overlay_id",
                "type": "string",
                "description": (
                    "ID of the overlay to run (e.g., 'security_validator', "
                    "'compliance_checker', 'ml_analyzer')"
                ),
            },
            {
                "name": "input_data",
                "type": "string",
                "description": "Data to process (content, query, or JSON)",
            },
            {
                "name": "parameters",
                "type": "string",
                "description": "Optional JSON string of additional parameters for the overlay",
            },
        ],
        executable=run_overlay,
        returns_description="Analysis results from the overlay including status and outputs",
    )


def create_list_overlays_function(
    overlay_manager: OverlayManagerProtocol,
) -> FunctionDefinition:
    """Create a function for listing available overlays."""
    async def list_overlays(
        status_filter: str | None = None,
    ) -> tuple[str, object, dict[str, object]]:
        """List all available Forge overlays with their status and capabilities."""
        try:
            overlays = await overlay_manager.list_overlays(
                status_filter=status_filter
            )

            formatted = []
            for overlay in overlays:
                formatted.append({
                    "id": overlay.id,
                    "name": overlay.name,
                    "description": overlay.description,
                    "status": overlay.status,
                    "capabilities": overlay.capabilities,
                    "trust_level": overlay.trust_level,
                })

            return STATUS_DONE, formatted, {}

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Failed to list overlays: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="list_overlays",
        description=(
            "List all available Forge overlays. Use this to discover what "
            "analysis capabilities are available before running specific overlays."
        ),
        arguments=[
            {
                "name": "status_filter",
                "type": "string",
                "description": "Optional filter by status (active, sandbox, quarantine)",
            },
        ],
        executable=list_overlays,
        returns_description="List of available overlays with their capabilities",
    )


# ==================== Governance Functions ====================

def create_get_proposals_function(
    governance_service: GovernanceServiceProtocol,
) -> FunctionDefinition:
    """Create a function for retrieving governance proposals."""
    async def get_proposals(
        status_filter: str | None = None,
        limit: int = 10,
    ) -> tuple[str, object, dict[str, object]]:
        """Get current governance proposals requiring attention."""
        try:
            proposals = await governance_service.list_proposals(
                status=status_filter,
                limit=limit,
            )

            formatted = []
            for prop in proposals:
                formatted.append({
                    "id": prop.id,
                    "title": prop.title,
                    "description": prop.description[:500],
                    "proposal_type": prop.proposal_type,
                    "status": prop.status,
                    "votes_for": prop.votes_for,
                    "votes_against": prop.votes_against,
                    "voting_ends": prop.voting_ends.isoformat(),
                    "quorum_reached": prop.quorum_reached,
                })

            return STATUS_DONE, formatted, {
                "active_proposals_count": len([p for p in formatted if p["status"] == "active"]),
            }

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Failed to get proposals: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="get_proposals",
        description=(
            "Get current governance proposals. Use this to see what decisions "
            "need to be made and participate in Forge's democratic governance."
        ),
        arguments=[
            {
                "name": "status_filter",
                "type": "string",
                "description": "Optional filter: active, passed, rejected, executed",
            },
            {
                "name": "limit",
                "type": "integer",
                "description": "Maximum proposals to return (default: 10)",
            },
        ],
        executable=get_proposals,
        returns_description="List of governance proposals with voting status",
    )


def create_cast_vote_function(
    governance_service: GovernanceServiceProtocol,
    agent_wallet: str,
) -> FunctionDefinition:
    """
    Create a function for casting governance votes.

    This enables agents to participate in Forge's democratic governance
    by voting on proposals according to their analysis and judgment.
    """
    async def cast_vote(
        proposal_id: str,
        vote: str,
        reasoning: str,
    ) -> tuple[str, object, dict[str, object]]:
        """
        Cast a vote on a governance proposal.

        The reasoning will be recorded on-chain as part of the vote,
        providing transparency into the agent's decision-making.
        """
        try:
            if vote not in ["for", "against", "abstain"]:
                return STATUS_FAILED, "Vote must be 'for', 'against', or 'abstain'", {}

            result = await governance_service.cast_vote(
                proposal_id=proposal_id,
                voter_id=agent_wallet,
                vote=vote,
                reasoning=reasoning,
                voter_address=agent_wallet,
            )

            return STATUS_DONE, {
                "proposal_id": proposal_id,
                "vote": vote,
                "tx_hash": result.tx_hash,
                "message": f"Vote '{vote}' recorded successfully",
            }, {
                "last_vote_proposal": proposal_id,
                "last_vote_direction": vote,
            }

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
            logger.error(f"Failed to cast vote: {e}")
            return STATUS_FAILED, str(e), {}

    return FunctionDefinition(
        name="cast_vote",
        description=(
            "Cast a vote on a governance proposal. Analyze the proposal carefully "
            "and provide clear reasoning for your vote. Your vote will be weighted "
            "by your trust level."
        ),
        arguments=[
            {
                "name": "proposal_id",
                "type": "string",
                "description": "ID of the proposal to vote on",
            },
            {
                "name": "vote",
                "type": "string",
                "description": "Your vote: 'for', 'against', or 'abstain'",
            },
            {
                "name": "reasoning",
                "type": "string",
                "description": (
                    "Explanation of why you're voting this way. "
                    "This will be recorded with your vote."
                ),
            },
        ],
        executable=cast_vote,
        returns_description="Confirmation of the recorded vote with transaction hash",
    )


# ==================== Worker Factory Functions ====================

def create_knowledge_worker(
    capsule_repository: CapsuleRepositoryProtocol,
    worker_id: str = "knowledge_worker",
) -> GAMEWorker:
    """
    Create a complete knowledge management worker.

    This worker provides all capsule-related functionality including
    search, retrieval, and creation. It's the primary interface for
    agents to interact with Forge's institutional memory.

    Args:
        capsule_repository: The Forge CapsuleRepository instance
        worker_id: Unique identifier for this worker

    Returns:
        Configured GAMEWorker with knowledge functions
    """
    functions = [
        create_search_capsules_function(capsule_repository),
        create_get_capsule_function(capsule_repository),
        create_create_capsule_function(capsule_repository),
    ]

    def get_state(function_result: object, current_state: dict[str, object]) -> dict[str, object]:
        """Track knowledge worker state across function calls."""
        state = current_state.copy()

        # Track search history
        if function_result and isinstance(function_result, dict):
            if "last_search_query" in function_result.get("state_update", {}):
                if "search_history" not in state:
                    state["search_history"] = []
                history = cast(list[dict[str, object]], state["search_history"])
                history.append({
                    "query": function_result["state_update"]["last_search_query"],
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                # Keep last 10 searches
                state["search_history"] = history[-10:]

        return state

    return GAMEWorker(
        worker_id=worker_id,
        description=(
            "Handles all knowledge management operations including searching, "
            "retrieving, and creating knowledge capsules. Use this worker to "
            "find information, store new insights, and maintain institutional memory."
        ),
        functions=functions,
        get_state_fn=get_state,
    )


def create_analysis_worker(
    overlay_manager: OverlayManagerProtocol,
    worker_id: str = "analysis_worker",
) -> GAMEWorker:
    """
    Create an analysis worker for running Forge overlays.

    This worker provides access to Forge's specialized analysis modules
    including security validation, compliance checking, and ML analysis.
    """
    functions = [
        create_run_overlay_function(overlay_manager),
        create_list_overlays_function(overlay_manager),
    ]

    return GAMEWorker(
        worker_id=worker_id,
        description=(
            "Performs specialized analysis using Forge overlays. Use this worker "
            "to run security checks, compliance validation, ML analysis, and "
            "other specialized processing on data or content."
        ),
        functions=functions,
    )


def create_governance_worker(
    governance_service: GovernanceServiceProtocol,
    agent_wallet: str,
    worker_id: str = "governance_worker",
) -> GAMEWorker:
    """
    Create a governance participation worker.

    This worker enables agents to participate in Forge's democratic
    governance system, viewing proposals and casting votes.
    """
    functions = [
        create_get_proposals_function(governance_service),
        create_cast_vote_function(governance_service, agent_wallet),
    ]

    return GAMEWorker(
        worker_id=worker_id,
        description=(
            "Participates in Forge governance by reviewing proposals and casting "
            "votes. Use this worker to engage in democratic decision-making "
            "about system changes, resource allocation, and policy updates."
        ),
        functions=functions,
    )
