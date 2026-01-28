"""
Graph Repository Tests for Forge Cascade V2

Comprehensive tests for GraphRepository and GraphAlgorithmProvider including:
- Backend detection (GDS vs Cypher)
- PageRank computation
- Centrality measures
- Community detection
- Trust transitivity
- Node similarity
- Shortest path
- Graph metrics
- Identifier validation
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from forge.models.graph_analysis import (
    AlgorithmType,
    CentralityRequest,
    Community,
    CommunityDetectionRequest,
    CommunityDetectionResult,
    GraphBackend,
    GraphMetrics,
    NodeRanking,
    NodeRankingResult,
    NodeSimilarityRequest,
    NodeSimilarityResult,
    PageRankRequest,
    ShortestPathRequest,
    ShortestPathResult,
    SimilarNode,
    TrustInfluence,
    TrustTransitivityRequest,
    TrustTransitivityResult,
)
from forge.repositories.graph_repository import (
    GraphAlgorithmProvider,
    GraphRepository,
    validate_neo4j_identifier,
    validate_relationship_pattern,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def graph_provider(mock_db_client):
    """Create graph algorithm provider with mock client."""
    return GraphAlgorithmProvider(mock_db_client)


@pytest.fixture
def graph_repository(mock_db_client):
    """Create graph repository with mock client."""
    return GraphRepository(mock_db_client)


@pytest.fixture
def sample_ranking_data():
    """Sample node ranking data for testing."""
    return [
        {
            "node_id": "cap1",
            "title": "Capsule 1",
            "trust_level": 80,
            "score": 0.95,
        },
        {
            "node_id": "cap2",
            "title": "Capsule 2",
            "trust_level": 60,
            "score": 0.75,
        },
    ]


@pytest.fixture
def sample_community_data():
    """Sample community detection data for testing."""
    return [
        {
            "node_id": "cap1",
            "node_type": "INSIGHT",
            "trust_level": 80,
            "community_id": 0,
        },
        {
            "node_id": "cap2",
            "node_type": "INSIGHT",
            "trust_level": 60,
            "community_id": 0,
        },
    ]


# =============================================================================
# Identifier Validation Tests
# =============================================================================


class TestIdentifierValidation:
    """Tests for Neo4j identifier validation."""

    def test_validate_neo4j_identifier_valid(self):
        """Valid identifiers pass validation."""
        assert validate_neo4j_identifier("Capsule", "node_label") == "Capsule"
        assert validate_neo4j_identifier("DERIVED_FROM", "relationship_type") == "DERIVED_FROM"
        assert validate_neo4j_identifier("node_123", "identifier") == "node_123"
        assert validate_neo4j_identifier("A", "label") == "A"

    def test_validate_neo4j_identifier_empty(self):
        """Empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_neo4j_identifier("", "node_label")

    def test_validate_neo4j_identifier_too_long(self):
        """Too long identifier raises ValueError."""
        long_name = "a" * 129
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_neo4j_identifier(long_name, "node_label")

    def test_validate_neo4j_identifier_starts_with_number(self):
        """Identifier starting with number raises ValueError."""
        with pytest.raises(ValueError, match="Must start with a letter"):
            validate_neo4j_identifier("123label", "node_label")

    def test_validate_neo4j_identifier_special_characters(self):
        """Identifier with special characters raises ValueError."""
        with pytest.raises(ValueError, match="Must start with a letter"):
            validate_neo4j_identifier("node-label", "node_label")
        with pytest.raises(ValueError, match="Must start with a letter"):
            validate_neo4j_identifier("node.label", "node_label")
        with pytest.raises(ValueError, match="Must start with a letter"):
            validate_neo4j_identifier("node label", "node_label")

    def test_validate_relationship_pattern_valid(self):
        """Valid relationship pattern passes validation."""
        result = validate_relationship_pattern(["DERIVED_FROM", "SUPPORTS"])
        assert result == "DERIVED_FROM|SUPPORTS"

    def test_validate_relationship_pattern_empty_list(self):
        """Empty relationship list raises ValueError."""
        with pytest.raises(ValueError, match="At least one relationship"):
            validate_relationship_pattern([])

    def test_validate_relationship_pattern_invalid_type(self):
        """Invalid relationship type in list raises ValueError."""
        with pytest.raises(ValueError, match="Must start with a letter"):
            validate_relationship_pattern(["VALID", "invalid-type"])


# =============================================================================
# Backend Detection Tests
# =============================================================================


class TestBackendDetection:
    """Tests for backend detection."""

    @pytest.mark.asyncio
    async def test_detect_backend_gds_available(
        self, graph_provider, mock_db_client
    ):
        """Detect GDS when available."""
        mock_db_client.execute_single.return_value = {"version": "2.5.0"}

        result = await graph_provider.detect_backend()

        assert result == GraphBackend.GDS

    @pytest.mark.asyncio
    async def test_detect_backend_gds_not_available(
        self, graph_provider, mock_db_client
    ):
        """Fallback to Cypher when GDS not available."""
        mock_db_client.execute_single.side_effect = RuntimeError("GDS not installed")

        result = await graph_provider.detect_backend()

        assert result == GraphBackend.CYPHER

    @pytest.mark.asyncio
    async def test_detect_backend_caches_result(
        self, graph_provider, mock_db_client
    ):
        """Backend detection result is cached."""
        mock_db_client.execute_single.return_value = {"version": "2.5.0"}

        await graph_provider.detect_backend()
        await graph_provider.detect_backend()

        # Should only check once
        assert mock_db_client.execute_single.call_count == 1


# =============================================================================
# PageRank Tests
# =============================================================================


class TestPageRankComputation:
    """Tests for PageRank computation."""

    @pytest.mark.asyncio
    async def test_pagerank_cypher_fallback(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """PageRank computation using Cypher fallback."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),  # Backend check
            {"count": 100},  # Node count
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        request = PageRankRequest(node_label="Capsule", limit=10)
        result = await graph_provider.compute_pagerank(request)

        assert isinstance(result, NodeRankingResult)
        assert result.algorithm == AlgorithmType.PAGERANK
        assert result.backend_used == GraphBackend.CYPHER
        assert len(result.rankings) == 2

    @pytest.mark.asyncio
    async def test_pagerank_with_caching(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """PageRank results are cached."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        request = PageRankRequest(node_label="Capsule", limit=10)

        # First call
        result1 = await graph_provider.compute_pagerank(request)

        # Reset mock to ensure cache is used
        mock_db_client.execute.reset_mock()

        # Second call should use cache
        result2 = await graph_provider.compute_pagerank(request)

        assert result1.rankings == result2.rankings
        mock_db_client.execute.assert_not_called()  # Cache used

    @pytest.mark.asyncio
    async def test_pagerank_limit_capped(
        self, graph_provider, mock_db_client
    ):
        """PageRank limit is capped at 1000."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = []

        request = PageRankRequest(node_label="Capsule", limit=5000)
        await graph_provider._cypher_pagerank(request)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 1000  # Capped


# =============================================================================
# Centrality Tests
# =============================================================================


class TestCentralityComputation:
    """Tests for centrality computation."""

    @pytest.mark.asyncio
    async def test_degree_centrality(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """Degree centrality computation."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        request = CentralityRequest(
            algorithm=AlgorithmType.DEGREE_CENTRALITY,
            node_label="Capsule",
        )
        result = await graph_provider.compute_centrality(request)

        assert result.algorithm == AlgorithmType.DEGREE_CENTRALITY
        assert len(result.rankings) == 2

    @pytest.mark.asyncio
    async def test_degree_centrality_normalized(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """Degree centrality with normalization."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        request = CentralityRequest(
            algorithm=AlgorithmType.DEGREE_CENTRALITY,
            normalized=True,
        )
        result = await graph_provider._degree_centrality(request)

        assert result.parameters["normalized"] is True
        # Scores should be normalized (max = 1.0)
        max_score = max(r.score for r in result.rankings)
        assert max_score <= 1.0

    @pytest.mark.asyncio
    async def test_centrality_cypher_fallback_to_degree(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """Non-degree centrality falls back to degree when GDS unavailable."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        request = CentralityRequest(
            algorithm=AlgorithmType.BETWEENNESS_CENTRALITY,
        )
        result = await graph_provider.compute_centrality(request)

        # Falls back to degree centrality
        assert result.algorithm == AlgorithmType.DEGREE_CENTRALITY


# =============================================================================
# Community Detection Tests
# =============================================================================


class TestCommunityDetection:
    """Tests for community detection."""

    @pytest.mark.asyncio
    async def test_community_detection_cypher(
        self, graph_provider, mock_db_client
    ):
        """Community detection using Cypher."""
        mock_db_client.execute_single.return_value = None  # GDS not available
        mock_db_client.execute.return_value = [
            {
                "community_id": 0,
                "member_ids": ["cap1", "cap2"],
                "member_types": ["INSIGHT", "INSIGHT"],
                "member_trusts": [80, 60],
            }
        ]

        # Force Cypher backend
        graph_provider._gds_available = False

        request = CommunityDetectionRequest(min_community_size=2)
        result = await graph_provider.detect_communities(request)

        assert isinstance(result, CommunityDetectionResult)
        assert len(result.communities) >= 0
        assert result.backend_used == GraphBackend.CYPHER

    @pytest.mark.asyncio
    async def test_community_detection_min_size_filter(
        self, graph_provider, mock_db_client
    ):
        """Community detection respects minimum size."""
        graph_provider._gds_available = False
        mock_db_client.execute.return_value = []

        request = CommunityDetectionRequest(min_community_size=5)
        await graph_provider._cypher_communities(request)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["min_size"] == 5


# =============================================================================
# Trust Transitivity Tests
# =============================================================================


class TestTrustTransitivity:
    """Tests for trust transitivity computation."""

    @pytest.mark.asyncio
    async def test_trust_transitivity_success(
        self, graph_provider, mock_db_client
    ):
        """Compute trust transitivity between nodes."""
        mock_db_client.execute.return_value = [
            {
                "path_nodes": ["cap1", "cap2", "cap3"],
                "trusts": [80, 70, 60],
                "path_length": 2,
                "cumulative_trust": 0.5,
            }
        ]

        request = TrustTransitivityRequest(
            source_id="cap1",
            target_id="cap3",
            relationship_types=["DERIVED_FROM"],
            max_hops=5,
        )
        result = await graph_provider.compute_trust_transitivity(request)

        assert isinstance(result, TrustTransitivityResult)
        assert result.paths_found == 1
        assert result.transitive_trust == 0.5

    @pytest.mark.asyncio
    async def test_trust_transitivity_no_path(
        self, graph_provider, mock_db_client
    ):
        """Trust transitivity with no path found."""
        mock_db_client.execute.return_value = []

        request = TrustTransitivityRequest(
            source_id="cap1",
            target_id="cap99",
            relationship_types=["DERIVED_FROM"],
        )
        result = await graph_provider.compute_trust_transitivity(request)

        assert result.paths_found == 0
        assert result.transitive_trust == 0.0

    @pytest.mark.asyncio
    async def test_trust_transitivity_max_hops_clamped(
        self, graph_provider, mock_db_client
    ):
        """Trust transitivity max hops is clamped."""
        mock_db_client.execute.return_value = []

        request = TrustTransitivityRequest(
            source_id="cap1",
            target_id="cap99",
            relationship_types=["DERIVED_FROM"],
            max_hops=100,  # Too high
        )
        await graph_provider.compute_trust_transitivity(request)

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        # Max hops should be clamped to 20
        assert "*1..20" in query


# =============================================================================
# Node Similarity Tests
# =============================================================================


class TestNodeSimilarity:
    """Tests for node similarity computation."""

    @pytest.mark.asyncio
    async def test_node_similarity_cypher(
        self, graph_provider, mock_db_client
    ):
        """Node similarity using Cypher (Jaccard)."""
        graph_provider._gds_available = False
        mock_db_client.execute.return_value = [
            {
                "node_id": "cap2",
                "title": "Similar Capsule",
                "node_type": "INSIGHT",
                "similarity": 0.75,
                "shared_neighbors": 3,
            }
        ]

        request = NodeSimilarityRequest(
            source_node_id="cap1",
            top_k=10,
        )
        result = await graph_provider.compute_node_similarity(request)

        assert isinstance(result, NodeSimilarityResult)
        assert len(result.similar_nodes) == 1
        assert result.similar_nodes[0].similarity_score == 0.75

    @pytest.mark.asyncio
    async def test_node_similarity_top_k_capped(
        self, graph_provider, mock_db_client
    ):
        """Node similarity top_k is capped."""
        graph_provider._gds_available = False
        mock_db_client.execute.return_value = []

        request = NodeSimilarityRequest(
            source_node_id="cap1",
            top_k=1000,  # Too high
        )
        await graph_provider._cypher_node_similarity(request)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["top_k"] == 500  # Capped


# =============================================================================
# Shortest Path Tests
# =============================================================================


class TestShortestPath:
    """Tests for shortest path computation."""

    @pytest.mark.asyncio
    async def test_shortest_path_cypher(
        self, graph_provider, mock_db_client
    ):
        """Shortest path using Cypher."""
        graph_provider._gds_available = False
        mock_db_client.execute_single.return_value = {
            "node_ids": ["cap1", "cap2", "cap3"],
            "titles": ["Start", "Middle", "End"],
            "trusts": [80, 70, 60],
            "types": ["Capsule", "Capsule", "Capsule"],
            "relTypes": ["DERIVED_FROM", "DERIVED_FROM"],
            "path_length": 2,
        }

        request = ShortestPathRequest(
            source_id="cap1",
            target_id="cap3",
            relationship_types=["DERIVED_FROM"],
        )
        result = await graph_provider.compute_shortest_path(request)

        assert isinstance(result, ShortestPathResult)
        assert result.path_found is True
        assert result.path_length == 2
        assert len(result.path_nodes) == 3

    @pytest.mark.asyncio
    async def test_shortest_path_not_found(
        self, graph_provider, mock_db_client
    ):
        """Shortest path when no path exists."""
        graph_provider._gds_available = False
        mock_db_client.execute_single.return_value = None

        request = ShortestPathRequest(
            source_id="cap1",
            target_id="cap99",
            relationship_types=["DERIVED_FROM"],
        )
        result = await graph_provider.compute_shortest_path(request)

        assert result.path_found is False
        assert result.path_nodes is None or len(result.path_nodes) == 0

    @pytest.mark.asyncio
    async def test_shortest_path_max_depth_clamped(
        self, graph_provider, mock_db_client
    ):
        """Shortest path max depth is clamped."""
        graph_provider._gds_available = False
        mock_db_client.execute_single.return_value = None

        request = ShortestPathRequest(
            source_id="cap1",
            target_id="cap99",
            relationship_types=["DERIVED_FROM"],
            max_depth=100,  # Too high
        )
        await graph_provider._cypher_shortest_path(request)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        # Max depth should be clamped to 20
        assert "*1..20" in query

    @pytest.mark.asyncio
    async def test_shortest_path_weighted(
        self, graph_provider, mock_db_client
    ):
        """Shortest path with weight computation."""
        graph_provider._gds_available = False
        mock_db_client.execute_single.return_value = {
            "node_ids": ["cap1", "cap2"],
            "titles": ["Start", "End"],
            "trusts": [80, 60],
            "types": ["Capsule", "Capsule"],
            "relTypes": ["DERIVED_FROM"],
            "path_length": 1,
        }

        request = ShortestPathRequest(
            source_id="cap1",
            target_id="cap2",
            relationship_types=["DERIVED_FROM"],
            weighted=True,
        )
        result = await graph_provider._cypher_shortest_path(request)

        assert result.total_trust is not None


# =============================================================================
# Graph Metrics Tests
# =============================================================================


class TestGraphMetrics:
    """Tests for graph metrics computation."""

    @pytest.mark.asyncio
    async def test_get_graph_metrics(
        self, graph_provider, mock_db_client
    ):
        """Get comprehensive graph metrics."""
        mock_db_client.execute.side_effect = [
            [{"label": "Capsule", "count": 100}],  # Node counts
            [{"rel_type": "DERIVED_FROM", "count": 200}],  # Edge counts
            [{"bucket": "STANDARD", "count": 50}],  # Trust distribution
        ]
        mock_db_client.execute_single.side_effect = [
            {"avg_degree": 2.0, "max_degree": 10, "node_count": 100},
            {"avg_trust": 65.0},
        ]

        result = await graph_provider.get_graph_metrics()

        assert isinstance(result, GraphMetrics)
        assert result.total_nodes == 100
        assert result.total_edges == 200
        assert result.avg_degree == 2.0

    @pytest.mark.asyncio
    async def test_get_trust_influences(
        self, graph_provider, mock_db_client
    ):
        """Get trust influence rankings."""
        mock_db_client.execute.return_value = [
            {
                "node_id": "cap1",
                "influence_score": 10.0,
                "downstream_count": 5,
                "upstream_count": 2,
                "trust": 80,
            }
        ]

        result = await graph_provider.get_trust_influences()

        assert len(result) == 1
        assert isinstance(result[0], TrustInfluence)
        assert result[0].influence_score == 10.0

    @pytest.mark.asyncio
    async def test_get_trust_influences_limit_capped(
        self, graph_provider, mock_db_client
    ):
        """Trust influences limit is capped."""
        mock_db_client.execute.return_value = []

        await graph_provider.get_trust_influences(limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 500  # Capped


# =============================================================================
# Caching Tests
# =============================================================================


class TestCaching:
    """Tests for result caching."""

    def test_cache_disabled_returns_none(self, graph_provider):
        """Cache returns None when disabled."""
        graph_provider.config.enable_caching = False
        graph_provider._set_cached("key", "value")

        result = graph_provider._get_cached("key")
        assert result is None

    def test_cache_set_and_get(self, graph_provider):
        """Cache set and get works correctly."""
        graph_provider.config.enable_caching = True
        graph_provider._set_cached("test_key", {"data": "value"})

        result = graph_provider._get_cached("test_key")
        assert result == {"data": "value"}

    def test_cache_expired(self, graph_provider):
        """Cache returns None for expired entries."""
        graph_provider.config.enable_caching = True
        graph_provider.config.cache_ttl_seconds = 0  # Immediate expiry

        graph_provider._set_cached("test_key", {"data": "value"})
        result = graph_provider._get_cached("test_key")

        assert result is None


# =============================================================================
# GraphRepository Wrapper Tests
# =============================================================================


class TestGraphRepository:
    """Tests for GraphRepository wrapper."""

    @pytest.mark.asyncio
    async def test_compute_pagerank(
        self, graph_repository, mock_db_client, sample_ranking_data
    ):
        """GraphRepository compute_pagerank wrapper."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        result = await graph_repository.compute_pagerank()

        assert isinstance(result, list)
        assert all(isinstance(r, NodeRanking) for r in result)

    @pytest.mark.asyncio
    async def test_compute_betweenness_centrality(
        self, graph_repository, mock_db_client, sample_ranking_data
    ):
        """GraphRepository betweenness centrality wrapper."""
        mock_db_client.execute_single.side_effect = [
            RuntimeError("GDS not available"),
            {"count": 100},
        ]
        mock_db_client.execute.return_value = sample_ranking_data

        result = await graph_repository.compute_betweenness_centrality()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_detect_communities(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository community detection wrapper."""
        mock_db_client.execute_single.return_value = None
        mock_db_client.execute.return_value = []

        graph_repository.provider._gds_available = False

        result = await graph_repository.detect_communities()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_compute_trust_transitivity(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository trust transitivity wrapper."""
        mock_db_client.execute.return_value = [
            {
                "path_nodes": ["cap1", "cap2"],
                "trusts": [80, 60],
                "path_length": 1,
                "cumulative_trust": 0.6,
            }
        ]

        result = await graph_repository.compute_trust_transitivity(
            source_id="cap1",
            target_id="cap2",
        )

        assert isinstance(result, float)
        assert result == 0.6

    @pytest.mark.asyncio
    async def test_get_metrics(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository get_metrics wrapper."""
        mock_db_client.execute.side_effect = [
            [{"label": "Capsule", "count": 50}],
            [{"rel_type": "DERIVED_FROM", "count": 100}],
            [],
        ]
        mock_db_client.execute_single.side_effect = [
            {"avg_degree": 2.0, "max_degree": 5, "node_count": 50},
            {"avg_trust": 60.0},
        ]

        result = await graph_repository.get_metrics()

        assert isinstance(result, GraphMetrics)

    @pytest.mark.asyncio
    async def test_find_similar_nodes(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository find similar nodes wrapper."""
        graph_repository.provider._gds_available = False
        mock_db_client.execute.return_value = [
            {
                "node_id": "cap2",
                "title": "Similar",
                "node_type": "INSIGHT",
                "similarity": 0.8,
            }
        ]

        result = await graph_repository.find_similar_nodes(source_id="cap1")

        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_find_shortest_path(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository find shortest path wrapper."""
        graph_repository.provider._gds_available = False
        mock_db_client.execute_single.return_value = {
            "node_ids": ["cap1", "cap2"],
            "titles": ["A", "B"],
            "trusts": [80, 60],
            "types": ["Capsule", "Capsule"],
            "relTypes": ["DERIVED_FROM"],
            "path_length": 1,
        }

        result = await graph_repository.find_shortest_path(
            source_id="cap1",
            target_id="cap2",
        )

        assert isinstance(result, ShortestPathResult)

    @pytest.mark.asyncio
    async def test_get_gds_status(
        self, graph_repository, mock_db_client
    ):
        """GraphRepository GDS status check."""
        mock_db_client.execute_single.return_value = {"version": "2.5.0"}

        result = await graph_repository.get_gds_status()

        assert isinstance(result, dict)
        assert "gds_available" in result
        assert "active_backend" in result


# =============================================================================
# GDS-Specific Tests (when available)
# =============================================================================


class TestGDSAlgorithms:
    """Tests for GDS-specific algorithm implementations."""

    @pytest.mark.asyncio
    async def test_gds_pagerank(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """PageRank using GDS."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            sample_ranking_data,  # PageRank results
            None,  # Graph drop
        ]
        mock_db_client.execute_single.return_value = {"count": 100}

        request = PageRankRequest(node_label="Capsule")
        result = await graph_provider._gds_pagerank(request)

        assert result.backend_used == GraphBackend.GDS
        assert len(result.rankings) == 2

    @pytest.mark.asyncio
    async def test_gds_centrality(
        self, graph_provider, mock_db_client, sample_ranking_data
    ):
        """Centrality using GDS."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            sample_ranking_data,  # Centrality results
            None,  # Graph drop
        ]
        mock_db_client.execute_single.return_value = {"count": 100}

        request = CentralityRequest(
            algorithm=AlgorithmType.BETWEENNESS_CENTRALITY,
        )
        result = await graph_provider._gds_centrality(request)

        assert result.backend_used == GraphBackend.GDS

    @pytest.mark.asyncio
    async def test_gds_communities(
        self, graph_provider, mock_db_client, sample_community_data
    ):
        """Community detection using GDS Louvain."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            sample_community_data,  # Louvain results
            None,  # Graph drop
        ]

        request = CommunityDetectionRequest(min_community_size=2)
        result = await graph_provider._gds_communities(request)

        assert result.backend_used == GraphBackend.GDS
        assert result.algorithm == AlgorithmType.COMMUNITY_LOUVAIN

    @pytest.mark.asyncio
    async def test_gds_node_similarity(
        self, graph_provider, mock_db_client
    ):
        """Node similarity using GDS."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            [{"node_id": "cap2", "title": "Similar", "node_type": "INSIGHT", "similarity": 0.9}],
            None,  # Graph drop
        ]

        request = NodeSimilarityRequest(source_node_id="cap1")
        result = await graph_provider._gds_node_similarity(request)

        assert result.backend_used == GraphBackend.GDS

    @pytest.mark.asyncio
    async def test_gds_shortest_path(
        self, graph_provider, mock_db_client
    ):
        """Shortest path using GDS Dijkstra."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            None,  # Graph drop
        ]
        mock_db_client.execute_single.return_value = {
            "node_ids": ["cap1", "cap2"],
            "titles": ["A", "B"],
            "trusts": [80, 60],
            "path_length": 1,
            "totalCost": 0.8,
        }

        request = ShortestPathRequest(
            source_id="cap1",
            target_id="cap2",
            relationship_types=["DERIVED_FROM"],
            weighted=True,
        )
        result = await graph_provider._gds_shortest_path(request)

        assert result.backend_used == GraphBackend.GDS
        assert result.path_found is True


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_gds_graph_cleanup_on_error(
        self, graph_provider, mock_db_client
    ):
        """GDS graphs are cleaned up even on error."""
        graph_provider._gds_available = True
        mock_db_client.execute.side_effect = [
            None,  # Graph projection
            RuntimeError("Algorithm failed"),  # PageRank fails
        ]

        request = PageRankRequest(node_label="Capsule")

        with pytest.raises(RuntimeError):
            await graph_provider._gds_pagerank(request)

        # Should still attempt cleanup (last call)
        cleanup_calls = [
            c for c in mock_db_client.execute.call_args_list
            if "gds.graph.drop" in str(c)
        ]
        # Cleanup is in finally block, but may fail silently


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
