"""
Knowledge Query Overlay for Forge Cascade V2

Provides natural language querying of the knowledge graph.
Users can ask questions in plain English, which are compiled
to Cypher queries and executed against Neo4j.

Pipeline:
1. Intent extraction (LLM parses question)
2. Schema mapping (entities → labels/properties)
3. Cypher generation (build parameterized query)
4. Query execution (run against Neo4j)
5. Answer synthesis (LLM creates human-readable response)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from ..models.events import Event
from ..models.overlay import Capability
from ..models.query import (
    CompiledQuery,
    GraphSchema,
    QueryResult,
    QueryResultRow,
    get_default_schema,
)
from ..services.query_compiler import (
    CypherSecurityError,
    CypherValidator,
    KnowledgeQueryService,
)
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


class QueryCompilationError(OverlayError):
    """Error during query compilation."""
    pass


class QueryExecutionError(OverlayError):
    """Error during query execution."""
    pass


class QuerySecurityError(OverlayError):
    """Error when query fails security validation."""
    pass


@dataclass
class QueryConfig:
    """Configuration for knowledge queries."""
    # Query limits
    max_results: int = 100
    default_limit: int = 20
    query_timeout_ms: int = 30000

    # Trust filtering
    apply_trust_filter: bool = True
    min_trust_level: int = 0

    # Response
    include_explanation: bool = True
    include_cypher: bool = False  # Debug mode
    synthesize_answer: bool = True

    # Caching
    cache_compiled_queries: bool = True
    cache_ttl_seconds: int = 600  # 10 minutes


@dataclass
class QueryHistoryEntry:
    """Record of a past query."""
    query_id: str
    question: str
    compiled_cypher: str
    result_count: int
    execution_time_ms: float
    user_id: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class KnowledgeQueryOverlay(BaseOverlay):
    """
    Knowledge query overlay for natural language graph queries.

    Allows users to ask questions like:
    - "What influenced the rate limiting decision?"
    - "Who contributed most to security knowledge?"
    - "Find contradictions in authentication docs"
    """

    NAME = "knowledge_query"
    VERSION = "1.0.0"
    DESCRIPTION = "Natural language queries on the knowledge graph"

    # Direct invocation - no event subscription needed
    SUBSCRIBED_EVENTS = set()

    # SECURITY FIX (Audit 4 - M): Add cache size limit to prevent memory exhaustion
    MAX_QUERY_CACHE_SIZE = 1000  # Maximum cached compiled queries

    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.LLM_ACCESS
    }

    def __init__(
        self,
        query_service: KnowledgeQueryService | None = None,
        config: QueryConfig | None = None,
        schema: GraphSchema | None = None
    ) -> None:
        """
        Initialize the knowledge query overlay.

        Args:
            query_service: Service for query compilation and execution
            config: Query configuration
            schema: Graph schema (defaults to Forge schema)
        """
        super().__init__()

        self._query_service = query_service
        self._config = config or QueryConfig()
        self._schema = schema or get_default_schema()

        # Query history
        self._history: list[QueryHistoryEntry] = []
        self._max_history = 100

        # Compiled query cache
        self._query_cache: dict[str, CompiledQuery] = {}

        # Statistics
        self._stats = {
            "queries_processed": 0,
            "queries_successful": 0,
            "queries_failed": 0,
            "avg_execution_time_ms": 0.0,
            "cache_hits": 0
        }

        self._logger = logger.bind(overlay=self.NAME)

    def set_query_service(self, service: KnowledgeQueryService) -> None:
        """Set the query service (for dependency injection)."""
        self._query_service = service

    async def initialize(self) -> bool:
        """Initialize the overlay."""
        self._logger.info(
            "knowledge_query_initialized",
            schema_labels=len(self._schema.nodes),
            schema_relationships=len(self._schema.relationships)
        )
        return await super().initialize()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute a knowledge query.

        Input data:
        - question: Natural language question (required)
        - limit: Max results to return
        - explain: Whether to include query explanation
        - raw_cypher: If true, execute raw cypher instead

        Returns query results and synthesized answer.
        """
        if not self._query_service:
            return OverlayResult.fail("Query service not configured")

        data = input_data or {}
        if event:
            data.update(event.payload or {})

        question = data.get("question")
        if not question:
            return OverlayResult.fail("No question provided")

        self._stats["queries_processed"] += 1

        try:
            # Check for cached compilation
            cache_key = self._get_cache_key(question, context.trust_flame)
            cached_query = self._query_cache.get(cache_key)

            if cached_query and self._config.cache_compiled_queries:
                self._stats["cache_hits"] += 1
                compiled = cached_query
            else:
                # Compile the question to Cypher
                compiled = await self._query_service.compiler.compile(
                    question=question,
                    user_trust=context.trust_flame,
                )

                # Cache the compiled query
                if self._config.cache_compiled_queries:
                    # SECURITY FIX (Audit 4 - M): Evict oldest entry if cache is full
                    if len(self._query_cache) >= self.MAX_QUERY_CACHE_SIZE:
                        oldest_key = next(iter(self._query_cache))
                        del self._query_cache[oldest_key]
                    self._query_cache[cache_key] = compiled

            # Apply limits
            limit = min(
                data.get("limit", self._config.default_limit),
                self._config.max_results
            )

            # Execute and get results
            start_time = datetime.now(UTC)
            result = await self._query_service.query(
                question=question,
                user_trust=context.trust_flame,
                synthesize_answer=self._config.synthesize_answer,
                max_results=limit,
            )
            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            # Update stats
            self._stats["queries_successful"] += 1
            self._update_avg_time(execution_time)

            # Record history
            self._record_history(
                question=question,
                cypher=compiled.cypher,
                result_count=result.total_count,
                execution_time=execution_time,
                user_id=context.user_id
            )

            # Build response
            response_data: dict[str, Any] = {
                "question": question,
                "answer": result.answer,
                "result_count": result.total_count,
                "execution_time_ms": round(execution_time, 2),
                "complexity": compiled.estimated_complexity.value,
            }

            # Include results if requested
            if data.get("include_results", True):
                response_data["results"] = [
                    row.data for row in result.rows[:limit]
                ]

            # Include explanation if configured
            if self._config.include_explanation:
                response_data["explanation"] = compiled.explanation

            # Include cypher if in debug mode
            if self._config.include_cypher or data.get("debug"):
                response_data["cypher"] = compiled.cypher
                response_data["parameters"] = compiled.parameters

            return OverlayResult.ok(
                data=response_data,
                metrics={
                    "execution_time_ms": execution_time,
                    "result_count": result.total_count,
                    "cache_hit": cache_key in self._query_cache
                }
            )

        except (QueryCompilationError, QueryExecutionError, OverlayError, ValueError, TypeError, KeyError, RuntimeError) as e:
            self._stats["queries_failed"] += 1
            self._logger.error(
                "query_execution_failed",
                question=question,
                error=str(e),
                error_type=type(e).__name__,
            )
            return OverlayResult.fail(f"Query failed: {str(e)}")

    async def compile_only(
        self,
        question: str,
        user_trust: int = 60
    ) -> CompiledQuery:
        """
        Compile a question without executing.

        Useful for debugging or query preview.
        """
        if not self._query_service:
            raise QueryCompilationError("Query service not configured")

        return await self._query_service.compiler.compile(
            question=question,
            user_trust=user_trust,
        )

    async def execute_raw(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        limit: int = 20
    ) -> QueryResult:
        """
        Execute raw Cypher query.

        For advanced users who want direct Cypher access.

        SECURITY: All raw queries are validated before execution.
        Only read operations are allowed. Write, delete, and
        administrative operations will be rejected.
        """
        if not self._query_service:
            raise QueryExecutionError("Query service not configured")

        # SECURITY: Validate raw Cypher before execution
        try:
            CypherValidator.validate(cypher, allow_writes=False)
            if parameters:
                CypherValidator.validate_parameters(parameters)
        except CypherSecurityError as e:
            self._logger.warning(
                "raw_query_rejected",
                reason=str(e),
                cypher_preview=cypher[:100] if cypher else ""
            )
            raise QuerySecurityError(f"Query rejected for security reasons: {e}") from e

        params = parameters or {}
        compiled = CompiledQuery(
            cypher=cypher,
            parameters=params,
            explanation="Raw Cypher query",
        )
        results: list[dict[str, Any]] = await self._query_service.db.execute(
            cypher, params
        )
        rows = [QueryResultRow(data=r) for r in results[:limit]]
        return QueryResult(
            query=compiled,
            original_question=cypher,
            rows=rows,
            total_count=len(results),
            truncated=len(results) > limit,
            execution_time_ms=0.0,
        )

    def get_query_history(
        self,
        user_id: str | None = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get recent query history."""
        history = self._history

        if user_id:
            history = [h for h in history if h.user_id == user_id]

        return [
            {
                "query_id": h.query_id,
                "question": h.question,
                "result_count": h.result_count,
                "execution_time_ms": h.execution_time_ms,
                "timestamp": h.timestamp.isoformat()
            }
            for h in history[-limit:]
        ]

    def get_suggested_queries(self) -> list[str]:
        """Get example queries to help users."""
        return [
            "What are the most influential capsules?",
            "Who created the most knowledge this month?",
            "Find all decisions about authentication",
            "What capsules contradict each other?",
            "Show the lineage of capsule X",
            "What knowledge is related to security?",
            "Who has the highest trust flame?",
            "Find all proposals pending approval",
            "What overlays are currently active?",
            "Show recent trust changes"
        ]

    def get_schema_info(self) -> dict[str, Any]:
        """Get information about the queryable schema."""
        return {
            "node_labels": [n.label for n in self._schema.nodes],
            "relationship_types": [r.type for r in self._schema.relationships],
            "node_properties": {
                n.label: [p.name for p in n.properties]
                for n in self._schema.nodes
            },
            "examples": self.get_suggested_queries()
        }

    def _get_cache_key(self, question: str, trust: int) -> str:
        """Generate cache key for a question."""
        # Normalize question
        normalized = question.lower().strip()
        # Include trust bracket (0-30, 30-60, 60-80, 80-100)
        trust_bracket = trust // 30
        return f"{normalized}:t{trust_bracket}"

    def _record_history(
        self,
        question: str,
        cypher: str,
        result_count: int,
        execution_time: float,
        user_id: str | None
    ) -> None:
        """Record query in history."""
        from uuid import uuid4

        entry = QueryHistoryEntry(
            query_id=str(uuid4()),
            question=question,
            compiled_cypher=cypher,
            result_count=result_count,
            execution_time_ms=execution_time,
            user_id=user_id
        )

        self._history.append(entry)

        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _update_avg_time(self, new_time: float) -> None:
        """Update rolling average execution time."""
        current = self._stats["avg_execution_time_ms"]
        count = self._stats["queries_successful"]

        if count == 1:
            self._stats["avg_execution_time_ms"] = new_time
        else:
            # Rolling average
            self._stats["avg_execution_time_ms"] = (
                current * (count - 1) + new_time
            ) / count

    def clear_cache(self) -> int:
        """Clear compiled query cache."""
        count = len(self._query_cache)
        self._query_cache.clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get query statistics."""
        return {
            **self._stats,
            "cache_size": len(self._query_cache),
            "history_size": len(self._history)
        }


# Convenience function
def create_knowledge_query_overlay(
    query_service: KnowledgeQueryService | None = None,
    **kwargs: Any,
) -> KnowledgeQueryOverlay:
    """
    Create a knowledge query overlay.

    Args:
        query_service: Service for query execution
        **kwargs: Additional configuration

    Returns:
        Configured KnowledgeQueryOverlay
    """
    config = QueryConfig(**kwargs)
    return KnowledgeQueryOverlay(query_service=query_service, config=config)
