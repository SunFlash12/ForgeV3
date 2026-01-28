"""
Comprehensive tests for the KnowledgeQueryOverlay.

Tests cover:
- Overlay initialization and configuration
- Query execution with natural language
- Query compilation
- Raw Cypher execution with security validation
- Query history management
- Query caching
- Schema information retrieval
- Suggested queries
- Statistics tracking
- Error handling
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from forge.models.events import Event, EventType
from forge.models.overlay import Capability
from forge.models.query import (
    CompiledQuery,
    QueryComplexity,
    QueryResult,
    QueryResultRow,
)
from forge.overlays.base import OverlayContext, OverlayResult
from forge.overlays.knowledge_query import (
    KnowledgeQueryOverlay,
    QueryCompilationError,
    QueryConfig,
    QueryExecutionError,
    QueryHistoryEntry,
    QuerySecurityError,
    create_knowledge_query_overlay,
)
from forge.services.query_compiler import CypherSecurityError


# =============================================================================
# Mock Classes
# =============================================================================


class MockCompiledQuery:
    """Mock compiled query object."""

    def __init__(
        self,
        cypher: str = "MATCH (n) RETURN n LIMIT 10",
        parameters: dict | None = None,
        explanation: str = "Test query explanation",
        complexity: QueryComplexity = QueryComplexity.SIMPLE,
    ):
        self.cypher = cypher
        self.parameters = parameters or {}
        self.explanation = explanation
        self.estimated_complexity = complexity


class MockQueryResult:
    """Mock query result object."""

    def __init__(
        self,
        rows: list | None = None,
        total_count: int = 1,
        answer: str = "Test answer",
    ):
        self.rows = rows or [QueryResultRow(data={"id": "test", "name": "Test Node"})]
        self.total_count = total_count
        self.answer = answer
        self.truncated = False


class MockCompiler:
    """Mock query compiler."""

    def __init__(self):
        self.compile = AsyncMock(return_value=MockCompiledQuery())


class MockDatabase:
    """Mock database client."""

    def __init__(self):
        self.execute = AsyncMock(return_value=[{"id": "test", "name": "Test Node"}])


class MockQueryService:
    """Mock knowledge query service."""

    def __init__(self):
        self.compiler = MockCompiler()
        self.db = MockDatabase()
        self.query = AsyncMock(return_value=MockQueryResult())


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_query_service() -> MockQueryService:
    """Create a mock query service."""
    return MockQueryService()


@pytest.fixture
def query_overlay(mock_query_service: MockQueryService) -> KnowledgeQueryOverlay:
    """Create a KnowledgeQueryOverlay with mock service."""
    return KnowledgeQueryOverlay(query_service=mock_query_service)


@pytest.fixture
def query_overlay_no_service() -> KnowledgeQueryOverlay:
    """Create a KnowledgeQueryOverlay without service."""
    return KnowledgeQueryOverlay()


@pytest.fixture
async def initialized_overlay(
    query_overlay: KnowledgeQueryOverlay,
) -> KnowledgeQueryOverlay:
    """Create and initialize a KnowledgeQueryOverlay."""
    await query_overlay.initialize()
    return query_overlay


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="knowledge_query",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ, Capability.LLM_ACCESS},
    )


@pytest.fixture
def high_trust_context() -> OverlayContext:
    """Create a high trust context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="knowledge_query",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=90,
        capabilities={Capability.DATABASE_READ, Capability.LLM_ACCESS},
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestKnowledgeQueryInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test default initialization values."""
        assert query_overlay.NAME == "knowledge_query"
        assert query_overlay.VERSION == "1.0.0"
        assert query_overlay._config is not None
        assert len(query_overlay._history) == 0
        assert len(query_overlay._query_cache) == 0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = QueryConfig(
            max_results=50,
            default_limit=10,
            query_timeout_ms=10000,
            apply_trust_filter=False,
            include_explanation=False,
        )
        overlay = KnowledgeQueryOverlay(config=config)

        assert overlay._config.max_results == 50
        assert overlay._config.default_limit == 10
        assert overlay._config.apply_trust_filter is False

    @pytest.mark.asyncio
    async def test_initialize(self, query_overlay: KnowledgeQueryOverlay) -> None:
        """Test overlay initialization."""
        result = await query_overlay.initialize()
        assert result is True

    def test_subscribed_events(self, query_overlay: KnowledgeQueryOverlay) -> None:
        """Test subscribed events are empty (direct invocation)."""
        assert len(query_overlay.SUBSCRIBED_EVENTS) == 0

    def test_required_capabilities(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test required capabilities."""
        assert Capability.DATABASE_READ in query_overlay.REQUIRED_CAPABILITIES
        assert Capability.LLM_ACCESS in query_overlay.REQUIRED_CAPABILITIES

    def test_set_query_service(
        self, query_overlay_no_service: KnowledgeQueryOverlay
    ) -> None:
        """Test setting query service."""
        mock_service = MockQueryService()
        query_overlay_no_service.set_query_service(mock_service)

        assert query_overlay_no_service._query_service is not None


# =============================================================================
# Service Requirement Tests
# =============================================================================


class TestServiceRequirement:
    """Tests for service requirement."""

    @pytest.mark.asyncio
    async def test_execute_without_service(
        self,
        query_overlay_no_service: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution without query service."""
        result = await query_overlay_no_service.execute(
            context=overlay_context,
            input_data={"question": "What are the capsules?"},
        )

        assert result.success is False
        assert "not configured" in result.error


# =============================================================================
# Query Execution Tests
# =============================================================================


class TestQueryExecution:
    """Tests for query execution."""

    @pytest.mark.asyncio
    async def test_execute_with_question(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test execution with a question."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "What are the most influential capsules?"},
        )

        assert result.success is True
        assert "question" in result.data
        assert "answer" in result.data
        assert "result_count" in result.data
        mock_query_service.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_without_question(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution without question."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={},
        )

        assert result.success is False
        assert "No question provided" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_event(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution with event payload."""
        event = Event(
            id="test-event",
            type=EventType.SYSTEM_EVENT,
            source="test",
            payload={"question": "Find all decisions"},
        )

        result = await initialized_overlay.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_limit(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test execution with custom limit."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test query", "limit": 5},
        )

        call_args = mock_query_service.query.call_args
        assert call_args.kwargs["max_results"] == 5

    @pytest.mark.asyncio
    async def test_execute_respects_max_results(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test that limit respects max_results config."""
        # Request more than max_results (100 by default)
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test query", "limit": 200},
        )

        call_args = mock_query_service.query.call_args
        assert call_args.kwargs["max_results"] <= 100


# =============================================================================
# Query Caching Tests
# =============================================================================


class TestQueryCaching:
    """Tests for query caching."""

    @pytest.mark.asyncio
    async def test_query_cache_hit(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test query cache hit."""
        question = "What are the capsules?"

        # First execution
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": question},
        )
        cache_hits_before = initialized_overlay._stats["cache_hits"]

        # Second execution with same question
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": question},
        )
        cache_hits_after = initialized_overlay._stats["cache_hits"]

        assert cache_hits_after == cache_hits_before + 1

    @pytest.mark.asyncio
    async def test_cache_key_includes_trust(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        high_trust_context: OverlayContext,
    ) -> None:
        """Test cache key varies by trust level."""
        question = "Test question"

        # Execute with normal trust
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": question},
        )

        # Execute with high trust
        await initialized_overlay.execute(
            context=high_trust_context,
            input_data={"question": question},
        )

        # Should have two different cache entries
        cache_keys = list(initialized_overlay._query_cache.keys())
        assert len(cache_keys) == 2

    @pytest.mark.asyncio
    async def test_cache_eviction(
        self,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test cache eviction when full."""
        overlay = KnowledgeQueryOverlay(query_service=mock_query_service)
        overlay.MAX_QUERY_CACHE_SIZE = 3
        await overlay.initialize()

        for i in range(5):
            await overlay.execute(
                context=overlay_context,
                input_data={"question": f"Question {i}"},
            )

        assert len(overlay._query_cache) <= 3

    def test_clear_cache(self, query_overlay: KnowledgeQueryOverlay) -> None:
        """Test clearing cache."""
        query_overlay._query_cache["key1"] = MockCompiledQuery()
        query_overlay._query_cache["key2"] = MockCompiledQuery()

        cleared = query_overlay.clear_cache()

        assert cleared == 2
        assert len(query_overlay._query_cache) == 0

    def test_cache_disabled(self, mock_query_service: MockQueryService) -> None:
        """Test with caching disabled."""
        config = QueryConfig(cache_compiled_queries=False)
        overlay = KnowledgeQueryOverlay(
            query_service=mock_query_service, config=config
        )

        assert overlay._config.cache_compiled_queries is False


# =============================================================================
# Query History Tests
# =============================================================================


class TestQueryHistory:
    """Tests for query history."""

    @pytest.mark.asyncio
    async def test_history_recorded(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test query is recorded in history."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test question"},
        )

        history = initialized_overlay.get_query_history()
        assert len(history) == 1
        assert history[0]["question"] == "Test question"

    @pytest.mark.asyncio
    async def test_history_filtered_by_user(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test history filtering by user."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Question 1"},
        )

        # Create context with different user
        other_context = OverlayContext(
            overlay_id="test",
            overlay_name="test",
            execution_id="test",
            triggered_by="test",
            correlation_id="test",
            user_id="other-user",
            trust_flame=60,
            capabilities={Capability.DATABASE_READ, Capability.LLM_ACCESS},
        )
        await initialized_overlay.execute(
            context=other_context,
            input_data={"question": "Question 2"},
        )

        # Filter by original user
        history = initialized_overlay.get_query_history(user_id="test-user")
        assert len(history) == 1
        assert history[0]["question"] == "Question 1"

    @pytest.mark.asyncio
    async def test_history_limited(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test history respects limit."""
        for i in range(10):
            await initialized_overlay.execute(
                context=overlay_context,
                input_data={"question": f"Question {i}"},
            )

        history = initialized_overlay.get_query_history(limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_history_max_size(
        self,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test history respects max size."""
        overlay = KnowledgeQueryOverlay(query_service=mock_query_service)
        overlay._max_history = 5
        await overlay.initialize()

        for i in range(10):
            await overlay.execute(
                context=overlay_context,
                input_data={"question": f"Question {i}"},
            )

        assert len(overlay._history) == 5


# =============================================================================
# Compile Only Tests
# =============================================================================


class TestCompileOnly:
    """Tests for compile-only functionality."""

    @pytest.mark.asyncio
    async def test_compile_only(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test compiling without executing."""
        result = await initialized_overlay.compile_only(
            question="What are the capsules?",
            user_trust=60,
        )

        assert result is not None
        mock_query_service.compiler.compile.assert_called_once()

    @pytest.mark.asyncio
    async def test_compile_only_without_service(
        self,
        query_overlay_no_service: KnowledgeQueryOverlay,
    ) -> None:
        """Test compile-only without service raises."""
        with pytest.raises(QueryCompilationError):
            await query_overlay_no_service.compile_only("Test question")


# =============================================================================
# Raw Cypher Execution Tests
# =============================================================================


class TestRawCypherExecution:
    """Tests for raw Cypher execution."""

    @pytest.mark.asyncio
    async def test_execute_raw_read_query(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test executing raw read query."""
        result = await initialized_overlay.execute_raw(
            cypher="MATCH (n) RETURN n LIMIT 10",
        )

        assert result is not None
        assert result.total_count >= 0

    @pytest.mark.asyncio
    async def test_execute_raw_with_parameters(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test executing raw query with parameters."""
        result = await initialized_overlay.execute_raw(
            cypher="MATCH (n) WHERE n.id = $id RETURN n",
            parameters={"id": "test-123"},
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_raw_without_service(
        self,
        query_overlay_no_service: KnowledgeQueryOverlay,
    ) -> None:
        """Test raw execution without service raises."""
        with pytest.raises(QueryExecutionError):
            await query_overlay_no_service.execute_raw("MATCH (n) RETURN n")

    @pytest.mark.asyncio
    async def test_execute_raw_rejects_write_query(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
    ) -> None:
        """Test raw execution rejects write queries."""
        with patch(
            "forge.overlays.knowledge_query.CypherValidator.validate"
        ) as mock_validate:
            mock_validate.side_effect = CypherSecurityError("Write not allowed")

            with pytest.raises(QuerySecurityError):
                await initialized_overlay.execute_raw(
                    cypher="CREATE (n:Node {name: 'Test'})"
                )


# =============================================================================
# Schema Information Tests
# =============================================================================


class TestSchemaInformation:
    """Tests for schema information retrieval."""

    def test_get_schema_info(self, query_overlay: KnowledgeQueryOverlay) -> None:
        """Test getting schema information."""
        schema_info = query_overlay.get_schema_info()

        assert "node_labels" in schema_info
        assert "relationship_types" in schema_info
        assert "node_properties" in schema_info
        assert "examples" in schema_info

    def test_get_suggested_queries(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test getting suggested queries."""
        suggestions = query_overlay.get_suggested_queries()

        assert len(suggestions) > 0
        assert all(isinstance(s, str) for s in suggestions)


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_incremented_on_success(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test stats are incremented on successful query."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test question"},
        )

        stats = initialized_overlay.get_stats()
        assert stats["queries_processed"] >= 1
        assert stats["queries_successful"] >= 1

    @pytest.mark.asyncio
    async def test_stats_incremented_on_failure(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test stats are incremented on failed query."""
        mock_query_service.query.side_effect = ValueError("Test error")

        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test question"},
        )

        stats = initialized_overlay.get_stats()
        assert stats["queries_failed"] >= 1

    def test_get_stats_includes_cache_info(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test stats include cache information."""
        stats = query_overlay.get_stats()

        assert "cache_size" in stats
        assert "history_size" in stats
        assert "cache_hits" in stats

    @pytest.mark.asyncio
    async def test_avg_execution_time_updated(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test average execution time is updated."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test question"},
        )

        stats = initialized_overlay.get_stats()
        assert stats["avg_execution_time_ms"] > 0


# =============================================================================
# Response Data Tests
# =============================================================================


class TestResponseData:
    """Tests for response data formatting."""

    @pytest.mark.asyncio
    async def test_response_includes_results(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test response includes results by default."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test", "include_results": True},
        )

        assert "results" in result.data

    @pytest.mark.asyncio
    async def test_response_includes_explanation(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test response includes explanation when configured."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test"},
        )

        assert "explanation" in result.data

    @pytest.mark.asyncio
    async def test_response_includes_cypher_in_debug(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test response includes Cypher in debug mode."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test", "debug": True},
        )

        assert "cypher" in result.data
        assert "parameters" in result.data

    @pytest.mark.asyncio
    async def test_response_includes_metrics(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test response includes metrics."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test"},
        )

        assert "execution_time_ms" in result.metrics
        assert "result_count" in result.metrics


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_knowledge_query_overlay factory function."""

    def test_create_default(self) -> None:
        """Test creating default overlay."""
        overlay = create_knowledge_query_overlay()
        assert isinstance(overlay, KnowledgeQueryOverlay)

    def test_create_with_service(self) -> None:
        """Test creating with query service."""
        mock_service = MockQueryService()
        overlay = create_knowledge_query_overlay(query_service=mock_service)

        assert overlay._query_service is not None

    def test_create_with_config_kwargs(self) -> None:
        """Test creating with configuration kwargs."""
        overlay = create_knowledge_query_overlay(
            max_results=50,
            default_limit=10,
            include_explanation=False,
        )

        assert overlay._config.max_results == 50
        assert overlay._config.default_limit == 10
        assert overlay._config.include_explanation is False


# =============================================================================
# Cache Key Tests
# =============================================================================


class TestCacheKey:
    """Tests for cache key generation."""

    def test_cache_key_normalized(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test cache key is normalized."""
        key1 = query_overlay._get_cache_key("What is this?", 60)
        key2 = query_overlay._get_cache_key("WHAT IS THIS?", 60)

        assert key1 == key2

    def test_cache_key_includes_trust_bracket(
        self, query_overlay: KnowledgeQueryOverlay
    ) -> None:
        """Test cache key includes trust bracket."""
        key_low = query_overlay._get_cache_key("question", 20)
        key_high = query_overlay._get_cache_key("question", 90)

        assert key_low != key_high
        assert ":t" in key_low
        assert ":t" in key_high


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_compilation_error_handled(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test compilation errors are handled."""
        mock_query_service.compiler.compile.side_effect = ValueError(
            "Compilation failed"
        )

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test"},
        )

        assert result.success is False
        assert "Query failed" in result.error

    @pytest.mark.asyncio
    async def test_execution_error_handled(
        self,
        initialized_overlay: KnowledgeQueryOverlay,
        overlay_context: OverlayContext,
        mock_query_service: MockQueryService,
    ) -> None:
        """Test execution errors are handled."""
        mock_query_service.query.side_effect = RuntimeError("Execution failed")

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"question": "Test"},
        )

        assert result.success is False
        assert "Query failed" in result.error
