"""
Graph Algorithms Overlay for Forge Cascade V2

Provides graph-theoretic algorithms for analyzing the knowledge graph:
- PageRank for influence/importance ranking
- Centrality metrics (betweenness, closeness, degree)
- Community detection (Louvain, connected components)
- Trust transitivity computation

Uses a layered backend approach:
1. Neo4j GDS (best performance)
2. Pure Cypher (works everywhere)
3. NetworkX fallback (full algorithm support)
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from ..models.events import Event, EventType
from ..models.graph_analysis import (
    AlgorithmType,
    CentralityRequest,
    CommunityDetectionRequest,
    GraphBackend,
    GraphMetrics,
    PageRankRequest,
)
from ..models.overlay import Capability
from ..repositories.graph_repository import GraphRepository
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


class GraphAlgorithmError(OverlayError):
    """Graph algorithm execution error."""
    pass


@dataclass
class CachedResult:
    """Cached algorithm result with TTL."""
    key: str
    data: dict[str, Any]
    computed_at: datetime
    ttl_seconds: int = 300  # 5 minutes default

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now(UTC) > self.computed_at + timedelta(seconds=self.ttl_seconds)


@dataclass
class AlgorithmConfig:
    """Configuration for graph algorithms."""
    # PageRank
    pagerank_damping: float = 0.85
    pagerank_iterations: int = 20
    pagerank_tolerance: float = 1e-6

    # Centrality
    centrality_sample_size: int | None = None  # None = use all nodes

    # Community detection
    community_algorithm: str = "louvain"  # or "label_propagation"
    community_min_size: int = 2

    # Trust transitivity
    trust_max_hops: int = 5
    trust_decay_factor: float = 0.9

    # Caching
    cache_ttl_seconds: int = 300  # 5 minutes
    enable_caching: bool = True


class GraphAlgorithmsOverlay(BaseOverlay):
    """
    Graph algorithms overlay for knowledge graph analysis.

    Provides PageRank, centrality, community detection, and
    trust transitivity calculations on the capsule/user graph.
    """

    NAME = "graph_algorithms"
    VERSION = "1.0.0"
    DESCRIPTION = "Computes graph algorithms (PageRank, centrality, communities)"

    SUBSCRIBED_EVENTS = {
        EventType.CASCADE_TRIGGERED,
        EventType.SYSTEM_EVENT,
    }

    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
    }

    # SECURITY FIX (Audit 4 - M): Add cache size limit to prevent memory exhaustion
    MAX_CACHE_SIZE = 500  # Max cached algorithm results

    def __init__(
        self,
        graph_repository: GraphRepository | None = None,
        config: AlgorithmConfig | None = None
    ):
        """
        Initialize the graph algorithms overlay.

        Args:
            graph_repository: Repository for graph algorithm execution
            config: Algorithm configuration
        """
        super().__init__()

        self._graph_repository = graph_repository
        self._config = config or AlgorithmConfig()

        # Results cache
        self._cache: dict[str, CachedResult] = {}

        # Backend detection
        self._detected_backend: GraphBackend | None = None

        # Statistics
        self._stats: dict[str, int] = {
            "pagerank_computations": 0,
            "centrality_computations": 0,
            "community_detections": 0,
            "trust_calculations": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

        self._logger = logger.bind(overlay=self.NAME)

    def set_repository(self, repository: GraphRepository) -> None:
        """Set the graph repository (for dependency injection)."""
        self._graph_repository = repository

    async def initialize(self) -> bool:
        """Initialize the overlay and detect backend."""
        if self._graph_repository:
            provider = self._graph_repository.provider
            self._detected_backend = await provider.detect_backend()
            self._logger.info(
                "graph_algorithms_initialized",
                backend=self._detected_backend.value if self._detected_backend else "none"
            )
        return await super().initialize()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute graph algorithm operations.

        Supports multiple operations based on input:
        - operation: "pagerank" | "centrality" | "communities" | "trust_transitivity"
        """
        if not self._graph_repository:
            return OverlayResult.fail("Graph repository not configured")

        data = input_data or {}
        if event:
            data.update(event.payload or {})

        operation = data.get("operation", "metrics")

        try:
            if operation == "pagerank":
                result = await self._compute_pagerank(data, context)
            elif operation == "centrality":
                result = await self._compute_centrality(data, context)
            elif operation == "communities":
                result = await self._detect_communities(data, context)
            elif operation == "trust_transitivity":
                result = await self._compute_trust_transitivity(data, context)
            elif operation == "metrics":
                result = await self._get_graph_metrics(data, context)
            elif operation == "refresh":
                result = await self._refresh_all(data, context)
            else:
                return OverlayResult.fail(f"Unknown operation: {operation}")

            # Emit analysis complete event if significant
            events_to_emit: list[dict[str, Any]] = []
            if operation in ("pagerank", "communities"):
                events_to_emit.append(
                    self.create_event_emission(
                        EventType.SYSTEM_EVENT,
                        {
                            "type": "analysis_complete",
                            "operation": operation,
                            "node_count": result.get("count", 0)
                        }
                    )
                )

            return OverlayResult.ok(
                data=result,
                events_to_emit=events_to_emit,
                metrics={
                    "backend": self._detected_backend.value if self._detected_backend else "unknown",
                    "cache_hits": self._stats["cache_hits"],
                    "cache_misses": self._stats["cache_misses"]
                }
            )

        except Exception as e:
            self._logger.error(
                "graph_algorithm_error",
                operation=operation,
                error=str(e)
            )
            return OverlayResult.fail(f"Algorithm error: {str(e)}")

    async def _compute_pagerank(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Compute PageRank for nodes."""
        assert self._graph_repository is not None

        # Check cache
        cache_key = f"pagerank:{data.get('node_label', 'Capsule')}:{data.get('relationship_type', 'DERIVED_FROM')}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        request = PageRankRequest(
            node_label=data.get("node_label", "Capsule"),
            relationship_type=data.get("relationship_type", "DERIVED_FROM"),
            damping_factor=data.get("damping_factor", self._config.pagerank_damping),
            max_iterations=data.get("max_iterations", self._config.pagerank_iterations),
            tolerance=data.get("tolerance", self._config.pagerank_tolerance)
        )

        ranking_result = await self._graph_repository.provider.compute_pagerank(request)
        self._stats["pagerank_computations"] += 1

        result: dict[str, Any] = {
            "operation": "pagerank",
            "count": len(ranking_result.rankings),
            "rankings": [
                {
                    "node_id": r.node_id,
                    "node_type": r.node_type,
                    "score": round(r.score, 6),
                    "rank": r.rank
                }
                for r in ranking_result.rankings[:data.get("limit", 100)]
            ],
            "backend": self._detected_backend.value if self._detected_backend else "unknown"
        }

        self._set_cached(cache_key, result)
        return result

    async def _compute_centrality(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Compute centrality metrics."""
        assert self._graph_repository is not None

        centrality_type = data.get("centrality_type", "degree")
        cache_key = f"centrality:{centrality_type}:{data.get('node_label', 'Capsule')}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Map centrality_type string to AlgorithmType
        algo_map: dict[str, AlgorithmType] = {
            "degree": AlgorithmType.DEGREE_CENTRALITY,
            "betweenness": AlgorithmType.BETWEENNESS_CENTRALITY,
            "closeness": AlgorithmType.CLOSENESS_CENTRALITY,
            "eigenvector": AlgorithmType.EIGENVECTOR_CENTRALITY,
        }
        algorithm = algo_map.get(centrality_type, AlgorithmType.DEGREE_CENTRALITY)

        request = CentralityRequest(
            algorithm=algorithm,
            node_label=data.get("node_label", "Capsule"),
            relationship_type=data.get("relationship_type", "DERIVED_FROM"),
        )

        ranking_result = await self._graph_repository.provider.compute_centrality(request)
        self._stats["centrality_computations"] += 1

        result: dict[str, Any] = {
            "operation": "centrality",
            "centrality_type": centrality_type,
            "count": len(ranking_result.rankings),
            "rankings": [
                {
                    "node_id": r.node_id,
                    "node_type": r.node_type,
                    "score": round(r.score, 6),
                    "rank": r.rank
                }
                for r in ranking_result.rankings[:data.get("limit", 100)]
            ],
            "backend": self._detected_backend.value if self._detected_backend else "unknown"
        }

        self._set_cached(cache_key, result)
        return result

    async def _detect_communities(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Detect communities in the graph."""
        assert self._graph_repository is not None

        algorithm = data.get("algorithm", self._config.community_algorithm)
        cache_key = f"communities:{algorithm}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        request = CommunityDetectionRequest(
            node_label=data.get("node_label", "Capsule"),
            relationship_type=data.get("relationship_type", "DERIVED_FROM"),
            algorithm=AlgorithmType.COMMUNITY_LOUVAIN if algorithm == "louvain" else AlgorithmType.COMMUNITY_LABEL_PROPAGATION,
            min_community_size=data.get("min_size", self._config.community_min_size)
        )

        community_result = await self._graph_repository.provider.detect_communities(request)
        self._stats["community_detections"] += 1

        communities = community_result.communities

        result: dict[str, Any] = {
            "operation": "communities",
            "algorithm": algorithm,
            "count": len(communities),
            "communities": [
                {
                    "community_id": c.community_id,
                    "size": c.size,
                    "density": round(c.density, 4),
                    "dominant_type": c.dominant_type,
                    "node_ids": [m.node_id for m in c.members[:20]]  # Limit for response size
                }
                for c in communities[:data.get("limit", 50)]
            ],
            "total_nodes": sum(c.size for c in communities),
            "backend": self._detected_backend.value if self._detected_backend else "unknown"
        }

        self._set_cached(cache_key, result)
        return result

    async def _compute_trust_transitivity(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Compute transitive trust between two nodes."""
        assert self._graph_repository is not None

        source_id = data.get("source_id")
        target_id = data.get("target_id")

        if not source_id or not target_id:
            return {"error": "source_id and target_id are required"}

        from ..models.graph_analysis import TrustTransitivityRequest

        request = TrustTransitivityRequest(
            source_id=str(source_id),
            target_id=str(target_id),
            max_hops=data.get("max_hops", self._config.trust_max_hops),
            decay_rate=data.get("decay_factor", self._config.trust_decay_factor),
        )

        trust_result = await self._graph_repository.provider.compute_trust_transitivity(request)
        self._stats["trust_calculations"] += 1

        return {
            "operation": "trust_transitivity",
            "source_id": source_id,
            "target_id": target_id,
            "trust_score": round(trust_result.transitive_trust, 4),
            "path_count": trust_result.paths_found,
            "best_path": trust_result.best_path.path_nodes if trust_result.best_path else [],
            "best_path_length": trust_result.best_path.path_length if trust_result.best_path else 0,
            "computation_time_ms": 0.0,
        }

    async def _get_graph_metrics(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Get overall graph metrics."""
        assert self._graph_repository is not None

        cache_key = "metrics:overall"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        metrics: GraphMetrics = await self._graph_repository.get_graph_metrics()

        result: dict[str, Any] = {
            "operation": "metrics",
            "total_nodes": metrics.total_nodes,
            "total_edges": metrics.total_edges,
            "density": round(metrics.density, 6),
            "avg_clustering": round(metrics.avg_clustering, 4),
            "connected_components": metrics.connected_components,
            "diameter": metrics.diameter,
            "node_distribution": metrics.nodes_by_type,
            "edge_distribution": metrics.edges_by_type,
        }

        self._set_cached(cache_key, result)
        return result

    async def _refresh_all(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> dict[str, Any]:
        """Refresh all cached computations."""
        self._cache.clear()

        # Recompute key metrics
        metrics = await self._get_graph_metrics(data, context)
        pagerank = await self._compute_pagerank({"limit": 10}, context)
        communities = await self._detect_communities({"limit": 5}, context)

        return {
            "operation": "refresh",
            "refreshed_at": datetime.now(UTC).isoformat(),
            "metrics": metrics,
            "top_10_pagerank": pagerank.get("rankings", []),
            "top_5_communities": communities.get("communities", [])
        }

    def _get_cached(self, key: str) -> dict[str, Any] | None:
        """Get cached result if not expired."""
        if not self._config.enable_caching:
            self._stats["cache_misses"] += 1
            return None

        cached = self._cache.get(key)
        if cached and not cached.is_expired:
            self._stats["cache_hits"] += 1
            return cached.data

        self._stats["cache_misses"] += 1
        return None

    def _set_cached(self, key: str, data: dict[str, Any]) -> None:
        """Cache a result."""
        if not self._config.enable_caching:
            return

        # SECURITY FIX (Audit 4 - M): Evict oldest entry if cache is full
        if len(self._cache) >= self.MAX_CACHE_SIZE:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = CachedResult(
            key=key,
            data=data,
            computed_at=datetime.now(UTC),
            ttl_seconds=self._config.cache_ttl_seconds
        )

    def clear_cache(self) -> int:
        """Clear all cached results."""
        count = len(self._cache)
        self._cache.clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get algorithm execution statistics."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "backend": self._detected_backend.value if self._detected_backend else "unknown"
        }


# Convenience function
def create_graph_algorithms_overlay(
    graph_repository: GraphRepository | None = None,
    cache_ttl: int = 300,
    **kwargs: Any
) -> GraphAlgorithmsOverlay:
    """
    Create a graph algorithms overlay.

    Args:
        graph_repository: Repository for graph operations
        cache_ttl: Cache TTL in seconds
        **kwargs: Additional configuration

    Returns:
        Configured GraphAlgorithmsOverlay
    """
    config = AlgorithmConfig(cache_ttl_seconds=cache_ttl, **kwargs)
    return GraphAlgorithmsOverlay(graph_repository=graph_repository, config=config)
