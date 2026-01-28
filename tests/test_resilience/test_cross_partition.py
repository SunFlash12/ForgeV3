"""
Tests for Cross-Partition Query Execution
==========================================

Tests for forge/resilience/partitioning/cross_partition.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.partitioning.cross_partition import (
    AggregationType,
    CrossPartitionQueryExecutor,
    CrossPartitionQueryResult,
    PartitionQueryResult,
    PartitionRouter,
    QueryScope,
    execute_cross_partition_search,
)


class TestQueryScope:
    """Tests for QueryScope enum."""

    def test_scope_values(self):
        """Test all scope values."""
        assert QueryScope.SINGLE_PARTITION.value == "single"
        assert QueryScope.MULTI_PARTITION.value == "multi"
        assert QueryScope.GLOBAL.value == "global"


class TestAggregationType:
    """Tests for AggregationType enum."""

    def test_aggregation_values(self):
        """Test all aggregation type values."""
        assert AggregationType.UNION.value == "union"
        assert AggregationType.INTERSECT.value == "intersect"
        assert AggregationType.MERGE.value == "merge"
        assert AggregationType.FIRST.value == "first"


class TestPartitionQueryResult:
    """Tests for PartitionQueryResult dataclass."""

    def test_result_creation(self):
        """Test creating a partition query result."""
        result = PartitionQueryResult(
            partition_id="p_123",
            results=[{"id": "cap_1"}, {"id": "cap_2"}],
            execution_time_ms=50.5,
            capsule_count=2,
            success=True,
        )

        assert result.partition_id == "p_123"
        assert len(result.results) == 2
        assert result.execution_time_ms == 50.5
        assert result.capsule_count == 2
        assert result.success is True
        assert result.error is None

    def test_result_with_error(self):
        """Test result with error."""
        result = PartitionQueryResult(
            partition_id="p_456",
            results=[],
            execution_time_ms=10.0,
            capsule_count=0,
            success=False,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"


class TestCrossPartitionQueryResult:
    """Tests for CrossPartitionQueryResult dataclass."""

    def test_result_creation(self):
        """Test creating a cross-partition query result."""
        partition_results = [
            PartitionQueryResult(
                partition_id="p_1",
                results=[{"id": "cap_1"}],
                execution_time_ms=30.0,
                capsule_count=1,
                success=True,
            ),
            PartitionQueryResult(
                partition_id="p_2",
                results=[{"id": "cap_2"}],
                execution_time_ms=40.0,
                capsule_count=1,
                success=True,
            ),
        ]

        result = CrossPartitionQueryResult(
            partition_results=partition_results,
            aggregated_results=[{"id": "cap_1"}, {"id": "cap_2"}],
            total_execution_time_ms=100.0,
            partitions_queried=2,
            partitions_succeeded=2,
            aggregation_type=AggregationType.UNION,
        )

        assert len(result.partition_results) == 2
        assert len(result.aggregated_results) == 2
        assert result.total_execution_time_ms == 100.0
        assert result.partitions_queried == 2
        assert result.partitions_succeeded == 2
        assert result.aggregation_type == AggregationType.UNION


class TestPartitionRouter:
    """Tests for PartitionRouter class."""

    @pytest.fixture
    def mock_partition_manager(self):
        """Create mock partition manager."""
        manager = MagicMock()
        manager.get_capsule_partition.return_value = None
        manager.list_partitions.return_value = []
        return manager

    @pytest.fixture
    def router(self, mock_partition_manager):
        """Create a router instance."""
        return PartitionRouter(mock_partition_manager)

    def test_route_by_capsule_id(self, router, mock_partition_manager):
        """Test routing by capsule ID."""
        mock_partition_manager.get_capsule_partition.return_value = "p_specific"

        scope, partitions = router.route_query("get", {"capsule_id": "cap_123"})

        assert scope == QueryScope.SINGLE_PARTITION
        assert partitions == ["p_specific"]

    def test_route_by_domain_tags_single(self, router, mock_partition_manager):
        """Test routing by domain tags to single partition."""
        mock_partition = MagicMock()
        mock_partition.partition_id = "p_science"
        mock_partition.domain_tags = {"science", "biology"}
        mock_partition_manager.list_partitions.return_value = [mock_partition]

        scope, partitions = router.route_query("search", {"domain_tags": ["science"]})

        assert scope == QueryScope.SINGLE_PARTITION
        assert partitions == ["p_science"]

    def test_route_by_domain_tags_multiple(self, router, mock_partition_manager):
        """Test routing by domain tags to multiple partitions."""
        mock_p1 = MagicMock()
        mock_p1.partition_id = "p_science"
        mock_p1.domain_tags = {"science", "biology"}

        mock_p2 = MagicMock()
        mock_p2.partition_id = "p_tech"
        mock_p2.domain_tags = {"technology", "science"}

        mock_partition_manager.list_partitions.return_value = [mock_p1, mock_p2]

        scope, partitions = router.route_query("search", {"domain_tags": ["science"]})

        assert scope == QueryScope.MULTI_PARTITION
        assert "p_science" in partitions
        assert "p_tech" in partitions

    def test_route_by_user_id(self, router, mock_partition_manager):
        """Test routing by user ID."""
        mock_partition = MagicMock()
        mock_partition.partition_id = "p_user"
        mock_partition.domain_tags = set()
        mock_partition.user_ids = {"user_123"}
        mock_partition_manager.list_partitions.return_value = [mock_partition]

        scope, partitions = router.route_query("search", {"user_id": "user_123"})

        assert scope == QueryScope.SINGLE_PARTITION
        assert partitions == ["p_user"]

    def test_route_global(self, router, mock_partition_manager):
        """Test global routing when no predicates match."""
        mock_p1 = MagicMock()
        mock_p1.partition_id = "p_1"
        mock_p1.state = MagicMock()
        mock_p1.state.value = "active"
        mock_p1.domain_tags = set()
        mock_p1.user_ids = set()

        mock_p2 = MagicMock()
        mock_p2.partition_id = "p_2"
        mock_p2.state = MagicMock()
        mock_p2.state.value = "active"
        mock_p2.domain_tags = set()
        mock_p2.user_ids = set()

        mock_partition_manager.list_partitions.return_value = [mock_p1, mock_p2]

        scope, partitions = router.route_query("search", {})

        assert scope == QueryScope.GLOBAL
        assert "p_1" in partitions
        assert "p_2" in partitions


class TestCrossPartitionQueryExecutor:
    """Tests for CrossPartitionQueryExecutor class."""

    @pytest.fixture
    def mock_partition_manager(self):
        """Create mock partition manager."""
        manager = MagicMock()
        mock_partition = MagicMock()
        mock_partition.partition_id = "default"
        mock_partition.state = MagicMock()
        mock_partition.state.value = "active"
        mock_partition.domain_tags = set()
        mock_partition.user_ids = set()
        manager.list_partitions.return_value = [mock_partition]
        manager.get_capsule_partition.return_value = None
        return manager

    @pytest.fixture
    def executor(self, mock_partition_manager):
        """Create an executor instance."""
        with patch("forge.resilience.partitioning.cross_partition.get_resilience_config") as mock:
            mock_config = MagicMock()
            mock_config.partitioning.enabled = True
            mock.return_value = mock_config
            return CrossPartitionQueryExecutor(mock_partition_manager)

    def test_executor_creation(self, executor):
        """Test executor creation."""
        assert executor._query_callback is None
        assert executor._stats["queries_executed"] == 0

    def test_set_query_callback(self, executor):
        """Test setting query callback."""
        callback = AsyncMock()
        executor.set_query_callback(callback)
        assert executor._query_callback == callback

    @pytest.mark.asyncio
    async def test_execute_single_partition(self, executor):
        """Test executing query on single partition."""
        callback = AsyncMock(return_value=[{"id": "cap_1"}])
        executor.set_query_callback(callback)

        result = await executor.execute(
            query="MATCH (c:Capsule) RETURN c",
            params={"capsule_id": "cap_1"},
            aggregation=AggregationType.UNION,
        )

        assert result.partitions_queried >= 1
        assert executor._stats["queries_executed"] == 1

    @pytest.mark.asyncio
    async def test_execute_no_callback(self, executor):
        """Test executing without callback returns empty results."""
        result = await executor.execute(
            query="MATCH (c:Capsule) RETURN c",
            params={},
            aggregation=AggregationType.UNION,
        )

        assert result.aggregated_results == []

    @pytest.mark.asyncio
    async def test_execute_with_aggregation_union(self, executor):
        """Test union aggregation."""
        async def mock_callback(partition_id, query, params):
            if partition_id == "p_1":
                return [{"id": "cap_1"}]
            return [{"id": "cap_2"}]

        executor.set_query_callback(mock_callback)

        # Manually test aggregation
        partition_results = [
            PartitionQueryResult(
                partition_id="p_1",
                results=[{"id": "cap_1"}],
                execution_time_ms=10.0,
                capsule_count=1,
                success=True,
            ),
            PartitionQueryResult(
                partition_id="p_2",
                results=[{"id": "cap_2"}],
                execution_time_ms=10.0,
                capsule_count=1,
                success=True,
            ),
        ]

        aggregated = executor._aggregate_results(partition_results, AggregationType.UNION)
        assert len(aggregated) == 2

    @pytest.mark.asyncio
    async def test_execute_with_aggregation_merge(self, executor):
        """Test merge aggregation (deduplication)."""
        partition_results = [
            PartitionQueryResult(
                partition_id="p_1",
                results=[{"id": "cap_1"}, {"id": "cap_2"}],
                execution_time_ms=10.0,
                capsule_count=2,
                success=True,
            ),
            PartitionQueryResult(
                partition_id="p_2",
                results=[{"id": "cap_1"}, {"id": "cap_3"}],  # cap_1 is duplicate
                execution_time_ms=10.0,
                capsule_count=2,
                success=True,
            ),
        ]

        aggregated = executor._aggregate_results(partition_results, AggregationType.MERGE)
        assert len(aggregated) == 3
        ids = [r["id"] for r in aggregated]
        assert "cap_1" in ids
        assert "cap_2" in ids
        assert "cap_3" in ids

    @pytest.mark.asyncio
    async def test_execute_with_aggregation_first(self, executor):
        """Test first aggregation."""
        partition_results = [
            PartitionQueryResult(
                partition_id="p_1",
                results=[{"id": "cap_1"}, {"id": "cap_2"}],
                execution_time_ms=10.0,
                capsule_count=2,
                success=True,
            ),
        ]

        aggregated = executor._aggregate_results(partition_results, AggregationType.FIRST)
        assert len(aggregated) == 1
        assert aggregated[0]["id"] == "cap_1"

    @pytest.mark.asyncio
    async def test_execute_with_aggregation_intersect(self, executor):
        """Test intersect aggregation."""
        partition_results = [
            PartitionQueryResult(
                partition_id="p_1",
                results=[{"id": "cap_1"}, {"id": "cap_2"}],
                execution_time_ms=10.0,
                capsule_count=2,
                success=True,
            ),
            PartitionQueryResult(
                partition_id="p_2",
                results=[{"id": "cap_1"}, {"id": "cap_3"}],
                execution_time_ms=10.0,
                capsule_count=2,
                success=True,
            ),
        ]

        aggregated = executor._aggregate_results(partition_results, AggregationType.INTERSECT)
        # Only cap_1 is in both partitions
        ids = [r["id"] for r in aggregated]
        assert "cap_1" in ids
        assert "cap_2" not in ids
        assert "cap_3" not in ids

    def test_detect_query_type_cypher(self, executor):
        """Test detecting Cypher query type."""
        query_type = executor._detect_query_type("MATCH (c:Capsule) RETURN c")
        assert query_type == "cypher"

    def test_detect_query_type_search(self, executor):
        """Test detecting search query type."""
        query_type = executor._detect_query_type("search for capsules about AI")
        assert query_type == "search"

    def test_detect_query_type_lineage(self, executor):
        """Test detecting lineage query type."""
        query_type = executor._detect_query_type("get lineage for capsule")
        assert query_type == "lineage"

    def test_detect_query_type_unknown(self, executor):
        """Test detecting unknown query type."""
        query_type = executor._detect_query_type("some random query")
        assert query_type == "unknown"

    def test_get_stats(self, executor):
        """Test getting statistics."""
        stats = executor.get_stats()

        assert "queries_executed" in stats
        assert "cross_partition_queries" in stats
        assert "total_partitions_queried" in stats
        assert "avg_execution_time_ms" in stats


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_execute_cross_partition_search(self):
        """Test convenience function for cross-partition search."""
        mock_manager = MagicMock()
        mock_partition = MagicMock()
        mock_partition.partition_id = "default"
        mock_partition.state = MagicMock()
        mock_partition.state.value = "active"
        mock_partition.domain_tags = set()
        mock_partition.user_ids = set()
        mock_manager.list_partitions.return_value = [mock_partition]
        mock_manager.get_capsule_partition.return_value = None

        with patch("forge.resilience.partitioning.cross_partition.get_resilience_config") as mock:
            mock_config = MagicMock()
            mock_config.partitioning.enabled = True
            mock.return_value = mock_config

            results = await execute_cross_partition_search(
                query="test query",
                filters={},
                partition_manager=mock_manager,
                max_results=10,
            )

            assert isinstance(results, list)
