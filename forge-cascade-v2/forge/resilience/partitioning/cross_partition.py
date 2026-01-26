"""
Cross-Partition Query Execution
===============================

Handles queries that span multiple partitions.
Provides query routing and result aggregation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from forge.resilience.config import get_resilience_config
from forge.resilience.partitioning.partition_manager import PartitionManager

logger = structlog.get_logger(__name__)


class QueryScope(Enum):
    """Scope of a query."""

    SINGLE_PARTITION = "single"  # Query targets one partition
    MULTI_PARTITION = "multi"  # Query spans multiple partitions
    GLOBAL = "global"  # Query searches all partitions


class AggregationType(Enum):
    """Types of result aggregation."""

    UNION = "union"  # Combine all results
    INTERSECT = "intersect"  # Only results in all partitions
    MERGE = "merge"  # Merge and deduplicate
    FIRST = "first"  # Return first match


@dataclass
class PartitionQueryResult:
    """Result from querying a single partition."""

    partition_id: str
    results: list[dict[str, Any]]
    execution_time_ms: float
    capsule_count: int
    success: bool
    error: str | None = None


@dataclass
class CrossPartitionQueryResult:
    """Aggregated result from cross-partition query."""

    partition_results: list[PartitionQueryResult]
    aggregated_results: list[dict[str, Any]]
    total_execution_time_ms: float
    partitions_queried: int
    partitions_succeeded: int
    aggregation_type: AggregationType


class PartitionRouter:
    """
    Routes queries to appropriate partitions.

    Determines which partitions need to be queried based on:
    - Query predicates (domain tags, user IDs)
    - Capsule ID targeting
    - Search scope
    """

    def __init__(self, partition_manager: PartitionManager) -> None:
        self._partition_manager = partition_manager

    def route_query(
        self, query_type: str, predicates: dict[str, Any]
    ) -> tuple[QueryScope, list[str]]:
        """
        Determine query routing.

        Args:
            query_type: Type of query (get, search, lineage, etc.)
            predicates: Query predicates

        Returns:
            Tuple of (query_scope, list of partition IDs)
        """
        # Check for specific capsule ID
        if "capsule_id" in predicates:
            partition_id = self._partition_manager.get_capsule_partition(predicates["capsule_id"])
            if partition_id:
                return QueryScope.SINGLE_PARTITION, [partition_id]

        # Check for domain tags
        if "domain_tags" in predicates:
            tags = set(predicates["domain_tags"])
            matching_partitions = self._find_partitions_by_tags(tags)
            if matching_partitions:
                scope = (
                    QueryScope.SINGLE_PARTITION
                    if len(matching_partitions) == 1
                    else QueryScope.MULTI_PARTITION
                )
                return scope, matching_partitions

        # Check for user filter
        if "user_id" in predicates:
            matching_partitions = self._find_partitions_by_user(predicates["user_id"])
            if matching_partitions:
                scope = (
                    QueryScope.SINGLE_PARTITION
                    if len(matching_partitions) == 1
                    else QueryScope.MULTI_PARTITION
                )
                return scope, matching_partitions

        # Global search - all partitions
        all_partitions = [
            p.partition_id
            for p in self._partition_manager.list_partitions()
            if p.state.value == "active"
        ]

        return QueryScope.GLOBAL, all_partitions

    def _find_partitions_by_tags(self, tags: set[str]) -> list[str]:
        """Find partitions that match domain tags."""
        matching = []

        for partition in self._partition_manager.list_partitions():
            if partition.domain_tags & tags:
                matching.append(partition.partition_id)

        return matching

    def _find_partitions_by_user(self, user_id: str) -> list[str]:
        """Find partitions that contain user's capsules."""
        matching = []

        for partition in self._partition_manager.list_partitions():
            if user_id in partition.user_ids:
                matching.append(partition.partition_id)

        return matching


class CrossPartitionQueryExecutor:
    """
    Executes queries across multiple partitions.

    Features:
    - Parallel partition querying
    - Result aggregation
    - Timeout handling
    - Partial result support
    """

    def __init__(self, partition_manager: PartitionManager) -> None:
        self._partition_manager = partition_manager
        self._router = PartitionRouter(partition_manager)
        self._config = get_resilience_config().partitioning

        # Query execution callback (set by integration code)
        self._query_callback: (
            Callable[[str, str, dict[str, Any]], Awaitable[list[dict[str, Any]]]] | None
        ) = None

        # Statistics
        self._stats = {
            "queries_executed": 0,
            "cross_partition_queries": 0,
            "total_partitions_queried": 0,
            "avg_execution_time_ms": 0.0,
        }

    def set_query_callback(
        self, callback: Callable[[str, str, dict[str, Any]], Awaitable[list[dict[str, Any]]]]
    ) -> None:
        """
        Set callback for executing queries on a partition.

        Args:
            callback: Function(partition_id, query, params) -> results
        """
        self._query_callback = callback

    async def execute(
        self,
        query: str,
        params: dict[str, Any],
        aggregation: AggregationType = AggregationType.UNION,
        timeout_ms: int = 30000,
        max_results_per_partition: int = 100,
    ) -> CrossPartitionQueryResult:
        """
        Execute a query across partitions.

        Args:
            query: Query to execute (Cypher or search query)
            params: Query parameters
            aggregation: How to aggregate results
            timeout_ms: Timeout in milliseconds
            max_results_per_partition: Max results from each partition

        Returns:
            Aggregated query result
        """
        start_time = datetime.now(UTC)
        self._stats["queries_executed"] += 1

        # Route query to partitions
        scope, partition_ids = self._router.route_query(
            query_type=self._detect_query_type(query), predicates=params
        )

        if scope != QueryScope.SINGLE_PARTITION:
            self._stats["cross_partition_queries"] += 1

        self._stats["total_partitions_queried"] += len(partition_ids)

        logger.debug(
            "cross_partition_query_started", scope=scope.value, partitions=len(partition_ids)
        )

        # Execute queries in parallel
        partition_results = await self._execute_parallel(
            partition_ids, query, params, timeout_ms, max_results_per_partition
        )

        # Aggregate results
        aggregated = self._aggregate_results(partition_results, aggregation)

        execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

        # Update stats
        self._update_stats(execution_time)

        result = CrossPartitionQueryResult(
            partition_results=partition_results,
            aggregated_results=aggregated,
            total_execution_time_ms=execution_time,
            partitions_queried=len(partition_ids),
            partitions_succeeded=sum(1 for r in partition_results if r.success),
            aggregation_type=aggregation,
        )

        logger.debug(
            "cross_partition_query_completed",
            partitions=result.partitions_queried,
            results=len(result.aggregated_results),
            time_ms=execution_time,
        )

        return result

    async def _execute_parallel(
        self,
        partition_ids: list[str],
        query: str,
        params: dict[str, Any],
        timeout_ms: int,
        max_results: int,
    ) -> list[PartitionQueryResult]:
        """Execute query on multiple partitions in parallel."""
        async_tasks: list[asyncio.Task[PartitionQueryResult]] = [
            asyncio.create_task(
                self._execute_on_partition(partition_id, query, params, max_results)
            )
            for partition_id in partition_ids
        ]

        # Execute with timeout
        results: list[PartitionQueryResult | BaseException]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*async_tasks, return_exceptions=True), timeout=timeout_ms / 1000
            )
        except TimeoutError:
            logger.warning("cross_partition_query_timeout", partitions=len(partition_ids))
            # Return partial results
            results = []
            for task in async_tasks:
                if task.done():
                    try:
                        results.append(task.result())
                    except (RuntimeError, OSError, ConnectionError, ValueError, TypeError):
                        pass

        # Process results
        partition_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                partition_results.append(
                    PartitionQueryResult(
                        partition_id=partition_ids[i] if i < len(partition_ids) else "unknown",
                        results=[],
                        execution_time_ms=0,
                        capsule_count=0,
                        success=False,
                        error=str(result),
                    )
                )
            elif isinstance(result, PartitionQueryResult):
                partition_results.append(result)

        return partition_results

    async def _execute_on_partition(
        self, partition_id: str, query: str, params: dict[str, Any], max_results: int
    ) -> PartitionQueryResult:
        """Execute query on a single partition."""
        start_time = datetime.now(UTC)

        try:
            if self._query_callback:
                results = await self._query_callback(
                    partition_id, query, {**params, "limit": max_results}
                )
            else:
                # No callback - return empty
                results = []

            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return PartitionQueryResult(
                partition_id=partition_id,
                results=results[:max_results],
                execution_time_ms=execution_time,
                capsule_count=len(results),
                success=True,
            )

        except (RuntimeError, OSError, ConnectionError, TimeoutError, ValueError) as e:
            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return PartitionQueryResult(
                partition_id=partition_id,
                results=[],
                execution_time_ms=execution_time,
                capsule_count=0,
                success=False,
                error=str(e),
            )

    def _aggregate_results(
        self, partition_results: list[PartitionQueryResult], aggregation: AggregationType
    ) -> list[dict[str, Any]]:
        """Aggregate results from multiple partitions."""
        all_results = []
        for pr in partition_results:
            if pr.success:
                all_results.extend(pr.results)

        if aggregation == AggregationType.UNION:
            return all_results

        elif aggregation == AggregationType.MERGE:
            # Deduplicate by ID
            seen_ids = set()
            merged = []
            for result in all_results:
                result_id = result.get("id") or result.get("capsule_id")
                if result_id and result_id not in seen_ids:
                    seen_ids.add(result_id)
                    merged.append(result)
                elif not result_id:
                    merged.append(result)
            return merged

        elif aggregation == AggregationType.INTERSECT:
            # Only results present in all partitions
            if not partition_results:
                return []

            # Get IDs from first successful partition
            first_ids = None
            for pr in partition_results:
                if pr.success and pr.results:
                    first_ids = {
                        r.get("id") or r.get("capsule_id")
                        for r in pr.results
                        if r.get("id") or r.get("capsule_id")
                    }
                    break

            if not first_ids:
                return []

            # Intersect with other partitions
            for pr in partition_results:
                if pr.success:
                    partition_ids = {
                        r.get("id") or r.get("capsule_id")
                        for r in pr.results
                        if r.get("id") or r.get("capsule_id")
                    }
                    first_ids &= partition_ids

            # Return matching results
            return [r for r in all_results if (r.get("id") or r.get("capsule_id")) in first_ids]

        elif aggregation == AggregationType.FIRST:
            return all_results[:1] if all_results else []

        return all_results

    def _detect_query_type(self, query: str) -> str:
        """Detect the type of query."""
        query_lower = query.lower()

        if "match" in query_lower and "return" in query_lower:
            return "cypher"
        elif any(kw in query_lower for kw in ["search", "find", "query"]):
            return "search"
        elif "lineage" in query_lower:
            return "lineage"
        else:
            return "unknown"

    def _update_stats(self, execution_time_ms: float) -> None:
        """Update query statistics."""
        total_queries = self._stats["queries_executed"]
        current_avg = self._stats["avg_execution_time_ms"]

        # Running average
        self._stats["avg_execution_time_ms"] = (
            current_avg * (total_queries - 1) + execution_time_ms
        ) / total_queries

    def get_stats(self) -> dict[str, Any]:
        """Get query execution statistics."""
        return dict(self._stats)


# Utility functions


async def execute_cross_partition_search(
    query: str, filters: dict[str, Any], partition_manager: PartitionManager, max_results: int = 100
) -> list[dict[str, Any]]:
    """
    Convenience function for cross-partition search.

    Args:
        query: Search query
        filters: Search filters
        partition_manager: Partition manager instance
        max_results: Maximum results to return

    Returns:
        Search results from all relevant partitions
    """
    executor = CrossPartitionQueryExecutor(partition_manager)

    result = await executor.execute(
        query=query,
        params=filters,
        aggregation=AggregationType.MERGE,
        max_results_per_partition=max_results,
    )

    return result.aggregated_results[:max_results]
