"""
Forge Tools for GitHub Copilot SDK

This module defines custom tools that expose Forge's capabilities to the
GitHub Copilot SDK. These tools allow Copilot to interact with Forge's
knowledge graph, capsules, overlays, and governance features.

Tool Categories:
1. Knowledge Operations - Query and search the knowledge graph
2. Capsule Operations - Create, read, update capsules
3. Overlay Operations - List and execute overlays
4. Governance Operations - View governance state and proposals

Each tool is defined using Pydantic models for automatic JSON schema
generation, ensuring type safety and clear documentation.
"""

from __future__ import annotations

import logging
from typing import Any

from copilot import Tool, ToolInvocation, ToolResult
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL PARAMETER MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeQueryParams(BaseModel):
    """Parameters for knowledge graph queries."""
    query: str = Field(
        description="Natural language query to search the knowledge graph"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional filters (e.g., {'type': 'note', 'created_after': '2024-01-01'})"
    )


class SemanticSearchParams(BaseModel):
    """Parameters for semantic search operations."""
    query: str = Field(
        description="Text query to search semantically"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of most similar results to return"
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold"
    )
    capsule_types: list[str] | None = Field(
        default=None,
        description="Filter by capsule types (e.g., ['note', 'document', 'code'])"
    )


class CreateCapsuleParams(BaseModel):
    """Parameters for capsule creation."""
    title: str = Field(
        description="Title of the new capsule"
    )
    content: str = Field(
        description="Main content of the capsule"
    )
    capsule_type: str = Field(
        default="note",
        description="Type of capsule: 'note', 'document', 'code', 'link', 'image'"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class GetCapsuleParams(BaseModel):
    """Parameters for retrieving a capsule."""
    capsule_id: str = Field(
        description="Unique identifier of the capsule to retrieve"
    )
    include_lineage: bool = Field(
        default=False,
        description="Include capsule lineage/provenance information"
    )
    include_relations: bool = Field(
        default=False,
        description="Include related capsules"
    )


class ListOverlaysParams(BaseModel):
    """Parameters for listing overlays."""
    active_only: bool = Field(
        default=True,
        description="Only return active overlays"
    )
    category: str | None = Field(
        default=None,
        description="Filter by overlay category"
    )


class ExecuteOverlayParams(BaseModel):
    """Parameters for executing an overlay."""
    overlay_id: str = Field(
        description="ID of the overlay to execute"
    )
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for the overlay"
    )


class GovernanceQueryParams(BaseModel):
    """Parameters for governance queries."""
    query_type: str = Field(
        description="Type of query: 'proposals', 'votes', 'council', 'metrics'"
    )
    status: str | None = Field(
        default=None,
        description="Filter by status (e.g., 'active', 'passed', 'rejected')"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ForgeToolRegistry:
    """
    Registry for Forge tools that can be used with GitHub Copilot SDK.

    This class manages tool registration and provides a consistent interface
    for executing Forge operations from Copilot conversations.

    Example:
        ```python
        registry = ForgeToolRegistry()
        await registry.initialize(db_client, search_service)

        # Get tools for Copilot session
        tools = registry.get_copilot_tools()
        session = await client.create_session({"tools": tools})
        ```
    """

    def __init__(self) -> None:
        self._db_client: Any = None
        self._search_service: Any = None
        self._capsule_service: Any = None
        self._overlay_manager: Any = None
        self._initialized = False

    async def initialize(
        self,
        db_client: Any = None,
        search_service: Any = None,
        capsule_service: Any = None,
        overlay_manager: Any = None,
    ) -> None:
        """
        Initialize the tool registry with Forge services.

        Args:
            db_client: Database client for knowledge graph operations
            search_service: Semantic search service
            capsule_service: Capsule management service
            overlay_manager: Overlay execution manager
        """
        self._db_client = db_client
        self._search_service = search_service
        self._capsule_service = capsule_service
        self._overlay_manager = overlay_manager
        self._initialized = True
        logger.info("ForgeToolRegistry initialized")

    def get_copilot_tools(self) -> list[Tool]:
        """
        Get all Forge tools formatted for Copilot SDK.

        Returns:
            List of tool definitions with handlers
        """
        return [
            Tool(
                name="forge_knowledge_query",
                description="Query Forge's knowledge graph using natural language. "
                           "Returns capsules, relationships, and insights.",
                parameters=KnowledgeQueryParams.model_json_schema(),
                handler=self._handle_knowledge_query,
            ),
            Tool(
                name="forge_semantic_search",
                description="Perform semantic similarity search across all capsules. "
                           "Finds conceptually related content even without keyword matches.",
                parameters=SemanticSearchParams.model_json_schema(),
                handler=self._handle_semantic_search,
            ),
            Tool(
                name="forge_create_capsule",
                description="Create a new knowledge capsule in Forge. "
                           "Capsules are atomic units of knowledge that can be linked.",
                parameters=CreateCapsuleParams.model_json_schema(),
                handler=self._handle_create_capsule,
            ),
            Tool(
                name="forge_get_capsule",
                description="Retrieve a specific capsule by ID with optional "
                           "lineage and relationship information.",
                parameters=GetCapsuleParams.model_json_schema(),
                handler=self._handle_get_capsule,
            ),
            Tool(
                name="forge_list_overlays",
                description="List available overlays (knowledge processing pipelines) "
                           "that can be executed on capsules.",
                parameters=ListOverlaysParams.model_json_schema(),
                handler=self._handle_list_overlays,
            ),
            Tool(
                name="forge_execute_overlay",
                description="Execute an overlay to process knowledge. "
                           "Overlays can analyze, transform, or generate insights.",
                parameters=ExecuteOverlayParams.model_json_schema(),
                handler=self._handle_execute_overlay,
            ),
            Tool(
                name="forge_governance",
                description="Query Forge's governance system including proposals, "
                           "votes, and the Ghost Council.",
                parameters=GovernanceQueryParams.model_json_schema(),
                handler=self._handle_governance_query,
            ),
        ]

    async def _handle_knowledge_query(self, invocation: ToolInvocation) -> ToolResult:
        """Handle knowledge graph query tool invocation."""
        args = invocation.get("arguments", {})
        params = KnowledgeQueryParams(**args)

        if not self._db_client:
            return self._error_result("Database client not initialized")

        try:
            # Execute knowledge graph query
            results = await self._db_client.search_capsules(
                query=params.query,
                limit=params.limit,
                filters=params.filters,
            )

            return ToolResult(
                textResultForLlm=self._format_capsule_results(results),
                resultType="success",
                sessionLog=f"Found {len(results)} results for: {params.query}",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Knowledge query failed: {e}")
            return self._error_result(f"Query failed: {e}")

    async def _handle_semantic_search(self, invocation: ToolInvocation) -> ToolResult:
        """Handle semantic search tool invocation."""
        args = invocation.get("arguments", {})
        params = SemanticSearchParams(**args)

        if not self._search_service:
            return self._error_result("Search service not initialized")

        try:
            results = await self._search_service.semantic_search(
                query=params.query,
                top_k=params.top_k,
                threshold=params.threshold,
                capsule_types=params.capsule_types,
            )

            return ToolResult(
                textResultForLlm=self._format_search_results(results),
                resultType="success",
                sessionLog=f"Semantic search found {len(results)} matches",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Semantic search failed: {e}")
            return self._error_result(f"Search failed: {e}")

    async def _handle_create_capsule(self, invocation: ToolInvocation) -> ToolResult:
        """Handle capsule creation tool invocation."""
        args = invocation.get("arguments", {})
        params = CreateCapsuleParams(**args)

        if not self._capsule_service:
            return self._error_result("Capsule service not initialized")

        try:
            capsule = await self._capsule_service.create_capsule(
                title=params.title,
                content=params.content,
                capsule_type=params.capsule_type,
                tags=params.tags,
                metadata=params.metadata,
            )

            return ToolResult(
                textResultForLlm=f"Created capsule '{params.title}' with ID: {capsule.id}",
                resultType="success",
                sessionLog=f"Capsule created: {capsule.id}",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Capsule creation failed: {e}")
            return self._error_result(f"Creation failed: {e}")

    async def _handle_get_capsule(self, invocation: ToolInvocation) -> ToolResult:
        """Handle capsule retrieval tool invocation."""
        args = invocation.get("arguments", {})
        params = GetCapsuleParams(**args)

        if not self._capsule_service:
            return self._error_result("Capsule service not initialized")

        try:
            capsule = await self._capsule_service.get_capsule(
                capsule_id=params.capsule_id,
                include_lineage=params.include_lineage,
                include_relations=params.include_relations,
            )

            if not capsule:
                return self._error_result(f"Capsule not found: {params.capsule_id}")

            return ToolResult(
                textResultForLlm=self._format_capsule(capsule),
                resultType="success",
                sessionLog=f"Retrieved capsule: {params.capsule_id}",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Capsule retrieval failed: {e}")
            return self._error_result(f"Retrieval failed: {e}")

    async def _handle_list_overlays(self, invocation: ToolInvocation) -> ToolResult:
        """Handle overlay listing tool invocation."""
        args = invocation.get("arguments", {})
        params = ListOverlaysParams(**args)

        if not self._overlay_manager:
            return self._error_result("Overlay manager not initialized")

        try:
            overlays = await self._overlay_manager.list_overlays(
                active_only=params.active_only,
                category=params.category,
            )

            return ToolResult(
                textResultForLlm=self._format_overlays(overlays),
                resultType="success",
                sessionLog=f"Found {len(overlays)} overlays",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Overlay listing failed: {e}")
            return self._error_result(f"Listing failed: {e}")

    async def _handle_execute_overlay(self, invocation: ToolInvocation) -> ToolResult:
        """Handle overlay execution tool invocation."""
        args = invocation.get("arguments", {})
        params = ExecuteOverlayParams(**args)

        if not self._overlay_manager:
            return self._error_result("Overlay manager not initialized")

        try:
            result = await self._overlay_manager.execute_overlay(
                overlay_id=params.overlay_id,
                input_data=params.input_data,
            )

            return ToolResult(
                textResultForLlm=f"Overlay {params.overlay_id} executed successfully. "
                                 f"Output: {result.get('summary', 'Complete')}",
                resultType="success",
                sessionLog=f"Executed overlay: {params.overlay_id}",
            )
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Overlay execution failed: {e}")
            return self._error_result(f"Execution failed: {e}")

    async def _handle_governance_query(self, invocation: ToolInvocation) -> ToolResult:
        """Handle governance query tool invocation."""
        args = invocation.get("arguments", {})
        params = GovernanceQueryParams(**args)

        # Mock governance data for now
        governance_data = {
            "proposals": [
                {
                    "id": "prop-001",
                    "title": "Enable cross-chain bridging",
                    "status": "active",
                    "votes_for": 150,
                    "votes_against": 20,
                },
            ],
            "votes": {"total": 170, "participation_rate": 0.75},
            "council": {
                "members": 5,
                "active_session": True,
                "last_decision": "Approved security upgrade",
            },
            "metrics": {
                "total_proposals": 42,
                "passed_rate": 0.85,
                "avg_participation": 0.72,
            },
        }

        result = governance_data.get(params.query_type, {})

        return ToolResult(
            textResultForLlm=f"Governance {params.query_type}: {result}",
            resultType="success",
            sessionLog=f"Queried governance: {params.query_type}",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FORMATTING HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _format_capsule_results(self, results: list[Any]) -> str:
        """Format capsule search results for LLM consumption."""
        if not results:
            return "No capsules found matching the query."

        lines = [f"Found {len(results)} capsules:\n"]
        for i, capsule in enumerate(results, 1):
            lines.append(
                f"{i}. [{capsule.get('type', 'note')}] {capsule.get('title', 'Untitled')}\n"
                f"   ID: {capsule.get('id', 'N/A')}\n"
                f"   Preview: {capsule.get('content', '')[:200]}...\n"
            )
        return "\n".join(lines)

    def _format_search_results(self, results: list[Any]) -> str:
        """Format semantic search results for LLM consumption."""
        if not results:
            return "No semantically similar content found."

        lines = ["Semantic search results (sorted by relevance):\n"]
        for i, match in enumerate(results, 1):
            score = match.get("score", 0)
            lines.append(
                f"{i}. [Score: {score:.2f}] {match.get('title', 'Untitled')}\n"
                f"   {match.get('snippet', '')[:150]}...\n"
            )
        return "\n".join(lines)

    def _format_capsule(self, capsule: dict[str, Any]) -> str:
        """Format a single capsule for LLM consumption."""
        return (
            f"**{capsule.get('title', 'Untitled')}**\n"
            f"Type: {capsule.get('type', 'note')}\n"
            f"ID: {capsule.get('id', 'N/A')}\n"
            f"Created: {capsule.get('created_at', 'Unknown')}\n"
            f"Tags: {', '.join(capsule.get('tags', []))}\n\n"
            f"Content:\n{capsule.get('content', 'No content')}"
        )

    def _format_overlays(self, overlays: list[Any]) -> str:
        """Format overlay list for LLM consumption."""
        if not overlays:
            return "No overlays available."

        lines = ["Available overlays:\n"]
        for overlay in overlays:
            lines.append(
                f"- **{overlay.get('name', 'Unnamed')}** (ID: {overlay.get('id')})\n"
                f"  {overlay.get('description', 'No description')}\n"
            )
        return "\n".join(lines)

    def _error_result(self, message: str) -> ToolResult:
        """Create an error result for tool invocation."""
        return ToolResult(
            textResultForLlm=f"Error: {message}",
            resultType="failure",
            sessionLog=f"Tool error: {message}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TOOL FUNCTIONS (for @define_tool decorator usage)
# ═══════════════════════════════════════════════════════════════════════════════

# These can be used with the Copilot SDK's @define_tool decorator
# when you want simpler function-based tools

async def knowledge_query_tool(params: KnowledgeQueryParams) -> str:
    """
    Query Forge's knowledge graph using natural language.

    This tool searches across all capsules and their relationships
    to find relevant information based on the query.
    """
    # Placeholder - would be connected to actual Forge services
    return f"Searching for: {params.query} (limit: {params.limit})"


async def semantic_search_tool(params: SemanticSearchParams) -> str:
    """
    Perform semantic similarity search across Forge capsules.

    Unlike keyword search, this finds conceptually related content
    even when exact words don't match.
    """
    return f"Semantic search for: {params.query} (top_k: {params.top_k})"


async def create_capsule_tool(params: CreateCapsuleParams) -> str:
    """
    Create a new knowledge capsule in Forge.

    Capsules are the atomic units of knowledge in Forge that can
    be linked, tagged, and processed by overlays.
    """
    return f"Created capsule: {params.title}"


async def get_capsule_tool(params: GetCapsuleParams) -> str:
    """
    Retrieve a capsule by its unique identifier.

    Optionally includes lineage (provenance) and relationship data.
    """
    return f"Retrieved capsule: {params.capsule_id}"


async def list_overlays_tool(params: ListOverlaysParams) -> str:
    """
    List available overlays in Forge.

    Overlays are knowledge processing pipelines that can analyze,
    transform, or generate insights from capsules.
    """
    return f"Listing overlays (active_only: {params.active_only})"
