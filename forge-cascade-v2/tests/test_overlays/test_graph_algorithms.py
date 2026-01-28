"""
Comprehensive tests for the GraphAlgorithmsOverlay.

Tests cover:
- Overlay initialization and configuration
- PageRank computation
- Centrality metrics (degree, betweenness, closeness, eigenvector)
- Community detection
- Trust transitivity computation
- Graph metrics retrieval
- Refresh operations
- Caching behavior
- Statistics tracking
- Event emission
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.models.events import EventType
from forge.models.graph_analysis import (
    GraphBackend,
    NodeRanking,
)
from forge.models.overlay import Capability
from forge.overlays.base import OverlayContext
from forge.overlays.graph_algorithms import (
    AlgorithmConfig,
    CachedResult,
    GraphAlgorithmsOverlay,
    create_graph_algorithms_overlay,
)

# =============================================================================
# Mock Classes
# =============================================================================


class MockCommunity:
    """Mock community object."""

    def __init__(
        self,
        community_id: int = 1,
        size: int = 10,
        density: float = 0.5,
        dominant_type: str = "Capsule",
    ):
        self.community_id = community_id
        self.size = size
        self.density = density
        self.dominant_type = dominant_type
        self.members = [MagicMock(node_id=f"node-{i}") for i in range(min(size, 5))]


class MockCommunityResult:
    """Mock community detection result."""

    def __init__(self, communities: list | None = None):
        self.communities = communities or [MockCommunity(), MockCommunity(community_id=2)]


class MockRankingResult:
    """Mock ranking result."""

    def __init__(self, rankings: list | None = None):
        self.rankings = rankings or [
            NodeRanking(node_id="node-1", node_type="Capsule", score=0.15, rank=1),
            NodeRanking(node_id="node-2", node_type="Capsule", score=0.12, rank=2),
            NodeRanking(node_id="node-3", node_type="Capsule", score=0.10, rank=3),
        ]


class MockTrustPath:
    """Mock trust path object."""

    def __init__(self):
        self.path_nodes = ["node-a", "node-b", "node-c"]
        self.path_length = 2


class MockTrustTransitivityResult:
    """Mock trust transitivity result."""

    def __init__(self, trust: float = 0.75, paths: int = 3):
        self.transitive_trust = trust
        self.paths_found = paths
        self.best_path = MockTrustPath()


class MockGraphMetrics:
    """Mock graph metrics object."""

    def __init__(self):
        self.total_nodes = 1000
        self.total_edges = 5000
        self.density = 0.01
        self.avg_clustering = 0.35
        self.connected_components = 5
        self.diameter = 8
        self.nodes_by_type = {"Capsule": 800, "User": 200}
        self.edges_by_type = {"DERIVED_FROM": 3000, "CONTRIBUTED": 2000}


class MockProvider:
    """Mock graph algorithm provider."""

    def __init__(self):
        self.detect_backend = AsyncMock(return_value=GraphBackend.CYPHER)
        self.compute_pagerank = AsyncMock(return_value=MockRankingResult())
        self.compute_centrality = AsyncMock(return_value=MockRankingResult())
        self.detect_communities = AsyncMock(return_value=MockCommunityResult())
        self.compute_trust_transitivity = AsyncMock(return_value=MockTrustTransitivityResult())


class MockGraphRepository:
    """Mock graph repository."""

    def __init__(self):
        self.provider = MockProvider()
        self.get_graph_metrics = AsyncMock(return_value=MockGraphMetrics())


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo() -> MockGraphRepository:
    """Create a mock graph repository."""
    return MockGraphRepository()


@pytest.fixture
def graph_overlay(mock_repo: MockGraphRepository) -> GraphAlgorithmsOverlay:
    """Create a GraphAlgorithmsOverlay with mock repository."""
    return GraphAlgorithmsOverlay(graph_repository=mock_repo)


@pytest.fixture
def graph_overlay_no_repo() -> GraphAlgorithmsOverlay:
    """Create a GraphAlgorithmsOverlay without repository."""
    return GraphAlgorithmsOverlay()


@pytest.fixture
async def initialized_overlay(
    graph_overlay: GraphAlgorithmsOverlay,
) -> GraphAlgorithmsOverlay:
    """Create and initialize a GraphAlgorithmsOverlay."""
    await graph_overlay.initialize()
    return graph_overlay


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="graph_algorithms",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ},
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestGraphAlgorithmsInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test default initialization values."""
        assert graph_overlay.NAME == "graph_algorithms"
        assert graph_overlay.VERSION == "1.0.0"
        assert graph_overlay._config is not None
        assert len(graph_overlay._cache) == 0

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = AlgorithmConfig(
            pagerank_damping=0.9,
            pagerank_iterations=30,
            community_algorithm="label_propagation",
            trust_max_hops=10,
            cache_ttl_seconds=600,
        )
        overlay = GraphAlgorithmsOverlay(config=config)

        assert overlay._config.pagerank_damping == 0.9
        assert overlay._config.pagerank_iterations == 30
        assert overlay._config.community_algorithm == "label_propagation"

    @pytest.mark.asyncio
    async def test_initialize(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test overlay initialization detects backend."""
        result = await graph_overlay.initialize()
        assert result is True
        assert graph_overlay._detected_backend is not None

    def test_subscribed_events(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test subscribed events."""
        assert EventType.CASCADE_TRIGGERED in graph_overlay.SUBSCRIBED_EVENTS
        assert EventType.SYSTEM_EVENT in graph_overlay.SUBSCRIBED_EVENTS

    def test_required_capabilities(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test required capabilities."""
        assert Capability.DATABASE_READ in graph_overlay.REQUIRED_CAPABILITIES

    def test_set_repository(self, graph_overlay_no_repo: GraphAlgorithmsOverlay) -> None:
        """Test setting repository."""
        mock_repo = MockGraphRepository()
        graph_overlay_no_repo.set_repository(mock_repo)

        assert graph_overlay_no_repo._graph_repository is not None


# =============================================================================
# Repository Requirement Tests
# =============================================================================


class TestRepositoryRequirement:
    """Tests for repository requirement."""

    @pytest.mark.asyncio
    async def test_execute_without_repository(
        self,
        graph_overlay_no_repo: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution without repository."""
        result = await graph_overlay_no_repo.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert result.success is False
        assert "not configured" in result.error


# =============================================================================
# PageRank Tests
# =============================================================================


class TestPageRank:
    """Tests for PageRank computation."""

    @pytest.mark.asyncio
    async def test_compute_pagerank(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test PageRank computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert result.success is True
        assert result.data["operation"] == "pagerank"
        assert "rankings" in result.data
        assert "count" in result.data
        mock_repo.provider.compute_pagerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_pagerank_with_custom_params(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test PageRank with custom parameters."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "pagerank",
                "node_label": "User",
                "relationship_type": "FOLLOWS",
                "damping_factor": 0.9,
                "max_iterations": 50,
            },
        )

        call_args = mock_repo.provider.compute_pagerank.call_args
        request = call_args[0][0]
        assert request.node_label == "User"
        assert request.relationship_type == "FOLLOWS"
        assert request.damping_factor == 0.9

    @pytest.mark.asyncio
    async def test_pagerank_caching(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test PageRank result caching."""
        # First call
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )
        cache_hits_before = initialized_overlay._stats["cache_hits"]

        # Second call - should hit cache
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )
        cache_hits_after = initialized_overlay._stats["cache_hits"]

        assert cache_hits_after == cache_hits_before + 1

    @pytest.mark.asyncio
    async def test_pagerank_stats_incremented(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test PageRank increments stats."""
        initialized_overlay._cache.clear()  # Ensure no cache hit

        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert initialized_overlay._stats["pagerank_computations"] >= 1


# =============================================================================
# Centrality Tests
# =============================================================================


class TestCentrality:
    """Tests for centrality computation."""

    @pytest.mark.asyncio
    async def test_compute_degree_centrality(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test degree centrality computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "centrality",
                "centrality_type": "degree",
            },
        )

        assert result.success is True
        assert result.data["operation"] == "centrality"
        assert result.data["centrality_type"] == "degree"

    @pytest.mark.asyncio
    async def test_compute_betweenness_centrality(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test betweenness centrality computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "centrality",
                "centrality_type": "betweenness",
            },
        )

        assert result.success is True
        assert result.data["centrality_type"] == "betweenness"

    @pytest.mark.asyncio
    async def test_compute_closeness_centrality(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test closeness centrality computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "centrality",
                "centrality_type": "closeness",
            },
        )

        assert result.success is True
        assert result.data["centrality_type"] == "closeness"

    @pytest.mark.asyncio
    async def test_compute_eigenvector_centrality(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test eigenvector centrality computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "centrality",
                "centrality_type": "eigenvector",
            },
        )

        assert result.success is True
        assert result.data["centrality_type"] == "eigenvector"

    @pytest.mark.asyncio
    async def test_centrality_stats_incremented(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test centrality increments stats."""
        initialized_overlay._cache.clear()

        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "centrality"},
        )

        assert initialized_overlay._stats["centrality_computations"] >= 1


# =============================================================================
# Community Detection Tests
# =============================================================================


class TestCommunityDetection:
    """Tests for community detection."""

    @pytest.mark.asyncio
    async def test_detect_communities_louvain(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test community detection with Louvain algorithm."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "communities",
                "algorithm": "louvain",
            },
        )

        assert result.success is True
        assert result.data["operation"] == "communities"
        assert result.data["algorithm"] == "louvain"
        assert "communities" in result.data
        mock_repo.provider.detect_communities.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_communities_label_propagation(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test community detection with label propagation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "communities",
                "algorithm": "label_propagation",
            },
        )

        assert result.success is True
        assert result.data["algorithm"] == "label_propagation"

    @pytest.mark.asyncio
    async def test_community_detection_includes_metadata(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test community detection includes metadata."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "communities"},
        )

        assert "count" in result.data
        assert "total_nodes" in result.data
        for community in result.data["communities"]:
            assert "community_id" in community
            assert "size" in community
            assert "density" in community

    @pytest.mark.asyncio
    async def test_community_stats_incremented(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test community detection increments stats."""
        initialized_overlay._cache.clear()

        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "communities"},
        )

        assert initialized_overlay._stats["community_detections"] >= 1


# =============================================================================
# Trust Transitivity Tests
# =============================================================================


class TestTrustTransitivity:
    """Tests for trust transitivity computation."""

    @pytest.mark.asyncio
    async def test_compute_trust_transitivity(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test trust transitivity computation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "trust_transitivity",
                "source_id": "user-1",
                "target_id": "user-2",
            },
        )

        assert result.success is True
        assert result.data["operation"] == "trust_transitivity"
        assert "trust_score" in result.data
        assert "path_count" in result.data
        assert "best_path" in result.data

    @pytest.mark.asyncio
    async def test_trust_transitivity_missing_ids(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test trust transitivity with missing IDs."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "trust_transitivity",
                "source_id": "user-1",
            },
        )

        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_trust_transitivity_with_custom_params(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test trust transitivity with custom parameters."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "trust_transitivity",
                "source_id": "user-1",
                "target_id": "user-2",
                "max_hops": 10,
                "decay_factor": 0.8,
            },
        )

        call_args = mock_repo.provider.compute_trust_transitivity.call_args
        request = call_args[0][0]
        assert request.max_hops == 10
        assert request.decay_rate == 0.8

    @pytest.mark.asyncio
    async def test_trust_stats_incremented(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test trust computation increments stats."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "trust_transitivity",
                "source_id": "user-1",
                "target_id": "user-2",
            },
        )

        assert initialized_overlay._stats["trust_calculations"] >= 1


# =============================================================================
# Graph Metrics Tests
# =============================================================================


class TestGraphMetrics:
    """Tests for graph metrics retrieval."""

    @pytest.mark.asyncio
    async def test_get_graph_metrics(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test getting graph metrics."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "metrics"},
        )

        assert result.success is True
        assert result.data["operation"] == "metrics"
        assert "total_nodes" in result.data
        assert "total_edges" in result.data
        assert "density" in result.data
        assert "avg_clustering" in result.data
        mock_repo.get_graph_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_caching(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test metrics are cached."""
        # First call
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "metrics"},
        )

        # Second call - should hit cache
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "metrics"},
        )

        assert initialized_overlay._stats["cache_hits"] >= 1


# =============================================================================
# Refresh Operation Tests
# =============================================================================


class TestRefreshOperation:
    """Tests for refresh operation."""

    @pytest.mark.asyncio
    async def test_refresh_all(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test refresh all operation."""
        # Pre-populate cache
        initialized_overlay._cache["test"] = CachedResult(
            key="test", data={}, computed_at=datetime.now(UTC)
        )

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "refresh"},
        )

        assert result.success is True
        assert result.data["operation"] == "refresh"
        assert "refreshed_at" in result.data
        assert "metrics" in result.data
        assert "top_10_pagerank" in result.data
        assert "top_5_communities" in result.data


# =============================================================================
# Caching Tests
# =============================================================================


class TestCaching:
    """Tests for caching behavior."""

    def test_cached_result_expiry(self) -> None:
        """Test CachedResult expiry detection."""
        old_result = CachedResult(
            key="test",
            data={"value": 1},
            computed_at=datetime.now(UTC) - timedelta(seconds=400),
            ttl_seconds=300,
        )
        assert old_result.is_expired is True

        fresh_result = CachedResult(
            key="test",
            data={"value": 1},
            computed_at=datetime.now(UTC),
            ttl_seconds=300,
        )
        assert fresh_result.is_expired is False

    @pytest.mark.asyncio
    async def test_cache_disabled(
        self,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test with caching disabled."""
        config = AlgorithmConfig(enable_caching=False)
        overlay = GraphAlgorithmsOverlay(graph_repository=mock_repo, config=config)
        await overlay.initialize()

        # First call
        await overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        # Second call - should not use cache
        await overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert overlay._stats["cache_misses"] >= 2

    @pytest.mark.asyncio
    async def test_cache_eviction(
        self,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test cache eviction when full."""
        overlay = GraphAlgorithmsOverlay(graph_repository=mock_repo)
        overlay.MAX_CACHE_SIZE = 2
        await overlay.initialize()

        # Fill cache with different operations
        await overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )
        await overlay.execute(
            context=overlay_context,
            input_data={"operation": "centrality", "centrality_type": "degree"},
        )
        await overlay.execute(
            context=overlay_context,
            input_data={
                "operation": "centrality",
                "centrality_type": "betweenness",
            },
        )

        assert len(overlay._cache) <= 2

    def test_clear_cache(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test clearing cache."""
        graph_overlay._cache["key1"] = CachedResult(
            key="key1", data={}, computed_at=datetime.now(UTC)
        )
        graph_overlay._cache["key2"] = CachedResult(
            key="key2", data={}, computed_at=datetime.now(UTC)
        )

        cleared = graph_overlay.clear_cache()

        assert cleared == 2
        assert len(graph_overlay._cache) == 0


# =============================================================================
# Event Emission Tests
# =============================================================================


class TestEventEmission:
    """Tests for event emission."""

    @pytest.mark.asyncio
    async def test_pagerank_emits_event(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test PageRank emits analysis complete event."""
        initialized_overlay._cache.clear()

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert len(result.events_to_emit) >= 1
        assert result.events_to_emit[0]["event_type"] == EventType.SYSTEM_EVENT.value

    @pytest.mark.asyncio
    async def test_community_detection_emits_event(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test community detection emits event."""
        initialized_overlay._cache.clear()

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "communities"},
        )

        assert len(result.events_to_emit) >= 1


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_get_stats(self, graph_overlay: GraphAlgorithmsOverlay) -> None:
        """Test getting statistics."""
        stats = graph_overlay.get_stats()

        assert "pagerank_computations" in stats
        assert "centrality_computations" in stats
        assert "community_detections" in stats
        assert "trust_calculations" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cache_size" in stats

    @pytest.mark.asyncio
    async def test_stats_include_backend(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
    ) -> None:
        """Test stats include backend info."""
        stats = initialized_overlay.get_stats()

        assert "backend" in stats


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_graph_algorithms_overlay factory function."""

    def test_create_default(self) -> None:
        """Test creating default overlay."""
        overlay = create_graph_algorithms_overlay()
        assert isinstance(overlay, GraphAlgorithmsOverlay)

    def test_create_with_repository(self) -> None:
        """Test creating with repository."""
        mock_repo = MockGraphRepository()
        overlay = create_graph_algorithms_overlay(graph_repository=mock_repo)

        assert overlay._graph_repository is not None

    def test_create_with_config(self) -> None:
        """Test creating with configuration."""
        overlay = create_graph_algorithms_overlay(
            cache_ttl=600,
            pagerank_damping=0.9,
            community_algorithm="label_propagation",
        )

        assert overlay._config.cache_ttl_seconds == 600
        assert overlay._config.pagerank_damping == 0.9
        assert overlay._config.community_algorithm == "label_propagation"


# =============================================================================
# Unknown Operation Tests
# =============================================================================


class TestUnknownOperation:
    """Tests for unknown operation handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test handling unknown operation."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "unknown_op"},
        )

        assert result.success is False
        assert "Unknown operation" in result.error


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_provider_error_handling(
        self,
        initialized_overlay: GraphAlgorithmsOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockGraphRepository,
    ) -> None:
        """Test handling provider errors."""
        mock_repo.provider.compute_pagerank.side_effect = RuntimeError("Provider error")
        initialized_overlay._cache.clear()

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"operation": "pagerank"},
        )

        assert result.success is False
        assert "Algorithm error" in result.error
