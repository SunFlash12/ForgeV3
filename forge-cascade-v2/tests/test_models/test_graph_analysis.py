"""
Graph Analysis Model Tests for Forge Cascade V2

Comprehensive tests for graph analysis models including:
- GraphBackend and AlgorithmType enums
- Node ranking models (NodeRanking, NodeRankingResult)
- Community detection models (CommunityMember, Community, CommunityDetectionResult)
- Trust analysis models (TrustPath, TrustTransitivityResult, TrustInfluence)
- Graph metrics (GraphMetrics)
- Algorithm request models
- Similarity and path models
"""

import pytest
from pydantic import ValidationError

from forge.models.graph_analysis import (
    AlgorithmType,
    CentralityRequest,
    Community,
    CommunityDetectionRequest,
    CommunityDetectionResult,
    CommunityMember,
    GraphAlgorithmConfig,
    GraphBackend,
    GraphMetrics,
    NodeRanking,
    NodeRankingResult,
    NodeSimilarityRequest,
    NodeSimilarityResult,
    PageRankRequest,
    PathNode,
    ShortestPathRequest,
    ShortestPathResult,
    SimilarNode,
    TrustInfluence,
    TrustPath,
    TrustTransitivityRequest,
    TrustTransitivityResult,
)

# =============================================================================
# GraphBackend Enum Tests
# =============================================================================


class TestGraphBackend:
    """Tests for GraphBackend enum."""

    def test_graph_backend_values(self):
        """GraphBackend has expected values."""
        assert GraphBackend.GDS.value == "gds"
        assert GraphBackend.CYPHER.value == "cypher"
        assert GraphBackend.NETWORKX.value == "networkx"

    def test_graph_backend_count(self):
        """GraphBackend has expected number of values."""
        assert len(GraphBackend) == 3

    def test_graph_backend_is_string_enum(self):
        """GraphBackend values are strings."""
        for backend in GraphBackend:
            assert isinstance(backend.value, str)


# =============================================================================
# AlgorithmType Enum Tests
# =============================================================================


class TestAlgorithmType:
    """Tests for AlgorithmType enum."""

    def test_algorithm_type_values(self):
        """AlgorithmType has expected values."""
        assert AlgorithmType.PAGERANK.value == "pagerank"
        assert AlgorithmType.BETWEENNESS_CENTRALITY.value == "betweenness_centrality"
        assert AlgorithmType.CLOSENESS_CENTRALITY.value == "closeness_centrality"
        assert AlgorithmType.DEGREE_CENTRALITY.value == "degree_centrality"
        assert AlgorithmType.EIGENVECTOR_CENTRALITY.value == "eigenvector_centrality"
        assert AlgorithmType.COMMUNITY_LOUVAIN.value == "community_louvain"
        assert AlgorithmType.COMMUNITY_LABEL_PROPAGATION.value == "community_label_propagation"
        assert AlgorithmType.TRUST_TRANSITIVITY.value == "trust_transitivity"
        assert AlgorithmType.SHORTEST_PATH.value == "shortest_path"

    def test_algorithm_type_count(self):
        """AlgorithmType has expected number of values."""
        assert len(AlgorithmType) == 9


# =============================================================================
# NodeRanking Tests
# =============================================================================


class TestNodeRanking:
    """Tests for NodeRanking model."""

    def test_valid_node_ranking(self):
        """Valid NodeRanking data creates model."""
        ranking = NodeRanking(
            node_id="node123",
            node_type="Capsule",
            score=0.85,
            rank=1,
        )

        assert ranking.node_id == "node123"
        assert ranking.node_type == "Capsule"
        assert ranking.score == 0.85
        assert ranking.rank == 1

    def test_node_ranking_defaults(self):
        """NodeRanking has sensible defaults."""
        ranking = NodeRanking(
            node_id="node123",
            node_type="Capsule",
            score=0.5,
            rank=5,
        )

        assert ranking.title is None
        assert ranking.trust_level is None
        assert ranking.metadata == {}

    def test_node_ranking_with_optional_fields(self):
        """NodeRanking can include optional fields."""
        ranking = NodeRanking(
            node_id="node123",
            node_type="Capsule",
            score=0.75,
            rank=2,
            title="Test Capsule",
            trust_level=80,
            metadata={"domain": "testing"},
        )

        assert ranking.title == "Test Capsule"
        assert ranking.trust_level == 80
        assert ranking.metadata == {"domain": "testing"}

    def test_node_ranking_score_minimum(self):
        """Score must be >= 0."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            NodeRanking(
                node_id="node123",
                node_type="Capsule",
                score=-0.1,
                rank=1,
            )

    def test_node_ranking_rank_minimum(self):
        """Rank must be >= 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            NodeRanking(
                node_id="node123",
                node_type="Capsule",
                score=0.5,
                rank=0,
            )


# =============================================================================
# NodeRankingResult Tests
# =============================================================================


class TestNodeRankingResult:
    """Tests for NodeRankingResult model."""

    def test_valid_node_ranking_result(self):
        """Valid NodeRankingResult data creates model."""
        result = NodeRankingResult(
            algorithm=AlgorithmType.PAGERANK,
            backend_used=GraphBackend.GDS,
            total_nodes=100,
            computation_time_ms=150.5,
        )

        assert result.algorithm == AlgorithmType.PAGERANK.value
        assert result.backend_used == GraphBackend.GDS.value
        assert result.total_nodes == 100

    def test_node_ranking_result_defaults(self):
        """NodeRankingResult has sensible defaults."""
        result = NodeRankingResult(
            algorithm=AlgorithmType.PAGERANK,
            backend_used=GraphBackend.CYPHER,
            total_nodes=50,
            computation_time_ms=75.0,
        )

        assert result.rankings == []
        assert result.parameters == {}
        assert result.computed_at is not None

    def test_node_ranking_result_with_rankings(self):
        """NodeRankingResult with populated rankings."""
        rankings = [
            NodeRanking(node_id="n1", node_type="Capsule", score=0.9, rank=1),
            NodeRanking(node_id="n2", node_type="Capsule", score=0.8, rank=2),
        ]

        result = NodeRankingResult(
            algorithm=AlgorithmType.BETWEENNESS_CENTRALITY,
            backend_used=GraphBackend.NETWORKX,
            rankings=rankings,
            total_nodes=2,
            computation_time_ms=25.0,
        )

        assert len(result.rankings) == 2

    def test_node_ranking_result_total_nodes_minimum(self):
        """total_nodes must be >= 0."""
        with pytest.raises(ValidationError):
            NodeRankingResult(
                algorithm=AlgorithmType.PAGERANK,
                backend_used=GraphBackend.GDS,
                total_nodes=-1,
                computation_time_ms=0.0,
            )

    def test_node_ranking_result_computation_time_minimum(self):
        """computation_time_ms must be >= 0."""
        with pytest.raises(ValidationError):
            NodeRankingResult(
                algorithm=AlgorithmType.PAGERANK,
                backend_used=GraphBackend.GDS,
                total_nodes=10,
                computation_time_ms=-5.0,
            )


# =============================================================================
# CommunityMember Tests
# =============================================================================


class TestCommunityMember:
    """Tests for CommunityMember model."""

    def test_valid_community_member(self):
        """Valid CommunityMember data creates model."""
        member = CommunityMember(
            node_id="node123",
            node_type="User",
            centrality_in_community=0.75,
        )

        assert member.node_id == "node123"
        assert member.node_type == "User"
        assert member.centrality_in_community == 0.75

    def test_community_member_defaults(self):
        """CommunityMember has sensible defaults."""
        member = CommunityMember(
            node_id="node123",
            node_type="Capsule",
        )

        assert member.centrality_in_community == 0.0

    def test_community_member_centrality_minimum(self):
        """centrality_in_community must be >= 0."""
        with pytest.raises(ValidationError):
            CommunityMember(
                node_id="node123",
                node_type="User",
                centrality_in_community=-0.5,
            )


# =============================================================================
# Community Tests
# =============================================================================


class TestCommunity:
    """Tests for Community model."""

    def test_valid_community(self):
        """Valid Community data creates model."""
        community = Community(
            community_id=1,
            size=10,
            density=0.8,
        )

        assert community.community_id == 1
        assert community.size == 10
        assert community.density == 0.8

    def test_community_defaults(self):
        """Community has sensible defaults."""
        community = Community(
            community_id=0,
            size=5,
            density=0.5,
        )

        assert community.members == []
        assert community.modularity_contribution == 0.0
        assert community.dominant_type is None
        assert community.dominant_tags == []
        assert community.avg_trust_level == 0.0

    def test_community_with_members(self):
        """Community with populated members."""
        members = [
            CommunityMember(node_id="n1", node_type="User", centrality_in_community=0.9),
            CommunityMember(node_id="n2", node_type="User", centrality_in_community=0.5),
        ]

        community = Community(
            community_id=2,
            members=members,
            size=2,
            density=0.75,
            dominant_type="User",
            dominant_tags=["machine-learning", "nlp"],
            avg_trust_level=75.0,
        )

        assert len(community.members) == 2
        assert community.dominant_type == "User"
        assert "machine-learning" in community.dominant_tags

    def test_community_density_bounds(self):
        """density must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Community(
                community_id=1,
                size=5,
                density=1.5,
            )

        with pytest.raises(ValidationError):
            Community(
                community_id=1,
                size=5,
                density=-0.1,
            )

    def test_community_avg_trust_level_bounds(self):
        """avg_trust_level must be between 0 and 100."""
        with pytest.raises(ValidationError):
            Community(
                community_id=1,
                size=5,
                density=0.5,
                avg_trust_level=150.0,
            )

        with pytest.raises(ValidationError):
            Community(
                community_id=1,
                size=5,
                density=0.5,
                avg_trust_level=-10.0,
            )


# =============================================================================
# CommunityDetectionResult Tests
# =============================================================================


class TestCommunityDetectionResult:
    """Tests for CommunityDetectionResult model."""

    def test_valid_community_detection_result(self):
        """Valid CommunityDetectionResult data creates model."""
        result = CommunityDetectionResult(
            algorithm=AlgorithmType.COMMUNITY_LOUVAIN,
            backend_used=GraphBackend.GDS,
            total_communities=5,
            modularity=0.65,
            coverage=0.95,
            computation_time_ms=200.0,
        )

        assert result.algorithm == AlgorithmType.COMMUNITY_LOUVAIN.value
        assert result.modularity == 0.65
        assert result.coverage == 0.95

    def test_community_detection_result_defaults(self):
        """CommunityDetectionResult has sensible defaults."""
        result = CommunityDetectionResult(
            algorithm=AlgorithmType.COMMUNITY_LABEL_PROPAGATION,
            backend_used=GraphBackend.CYPHER,
            total_communities=3,
            modularity=0.5,
            coverage=0.8,
            computation_time_ms=100.0,
        )

        assert result.communities == []
        assert result.parameters == {}
        assert result.computed_at is not None

    def test_community_detection_result_modularity_bounds(self):
        """modularity must be between -1 and 1."""
        with pytest.raises(ValidationError):
            CommunityDetectionResult(
                algorithm=AlgorithmType.COMMUNITY_LOUVAIN,
                backend_used=GraphBackend.GDS,
                total_communities=5,
                modularity=1.5,
                coverage=0.9,
                computation_time_ms=0.0,
            )

        # Negative modularity is valid (between -1 and 1)
        result = CommunityDetectionResult(
            algorithm=AlgorithmType.COMMUNITY_LOUVAIN,
            backend_used=GraphBackend.GDS,
            total_communities=5,
            modularity=-0.5,
            coverage=0.9,
            computation_time_ms=0.0,
        )
        assert result.modularity == -0.5

    def test_community_detection_result_coverage_bounds(self):
        """coverage must be between 0 and 1."""
        with pytest.raises(ValidationError):
            CommunityDetectionResult(
                algorithm=AlgorithmType.COMMUNITY_LOUVAIN,
                backend_used=GraphBackend.GDS,
                total_communities=5,
                modularity=0.5,
                coverage=1.5,
                computation_time_ms=0.0,
            )


# =============================================================================
# TrustPath Tests
# =============================================================================


class TestTrustPath:
    """Tests for TrustPath model."""

    def test_valid_trust_path(self):
        """Valid TrustPath data creates model."""
        path = TrustPath(
            path_nodes=["node1", "node2", "node3"],
            path_length=2,
            trust_at_each_hop=[0.9, 0.8],
            cumulative_trust=0.72,
            decay_applied=0.28,
        )

        assert len(path.path_nodes) == 3
        assert path.path_length == 2
        assert path.cumulative_trust == 0.72

    def test_trust_path_defaults(self):
        """TrustPath has sensible defaults."""
        path = TrustPath(
            path_nodes=["a", "b"],
            path_length=1,
            cumulative_trust=0.5,
            decay_applied=0.5,
        )

        assert path.trust_at_each_hop == []

    def test_trust_path_bounds(self):
        """cumulative_trust and decay_applied must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TrustPath(
                path_nodes=["a", "b"],
                path_length=1,
                cumulative_trust=1.5,
                decay_applied=0.5,
            )

        with pytest.raises(ValidationError):
            TrustPath(
                path_nodes=["a", "b"],
                path_length=1,
                cumulative_trust=0.5,
                decay_applied=-0.1,
            )

    def test_trust_path_length_minimum(self):
        """path_length must be >= 1."""
        with pytest.raises(ValidationError):
            TrustPath(
                path_nodes=["a"],
                path_length=0,
                cumulative_trust=1.0,
                decay_applied=0.0,
            )


# =============================================================================
# TrustTransitivityResult Tests
# =============================================================================


class TestTrustTransitivityResult:
    """Tests for TrustTransitivityResult model."""

    def test_valid_trust_transitivity_result(self):
        """Valid TrustTransitivityResult data creates model."""
        result = TrustTransitivityResult(
            source_id="source123",
            target_id="target456",
            transitive_trust=0.65,
            paths_found=3,
            max_hops_searched=5,
        )

        assert result.source_id == "source123"
        assert result.target_id == "target456"
        assert result.transitive_trust == 0.65
        assert result.paths_found == 3

    def test_trust_transitivity_result_defaults(self):
        """TrustTransitivityResult has sensible defaults."""
        result = TrustTransitivityResult(
            source_id="s1",
            target_id="t1",
            transitive_trust=0.5,
            paths_found=1,
            max_hops_searched=3,
        )

        assert result.best_path is None
        assert result.all_paths == []
        assert result.computed_at is not None

    def test_trust_transitivity_result_with_paths(self):
        """TrustTransitivityResult with paths."""
        best_path = TrustPath(
            path_nodes=["s1", "m1", "t1"],
            path_length=2,
            trust_at_each_hop=[0.9, 0.8],
            cumulative_trust=0.72,
            decay_applied=0.28,
        )

        result = TrustTransitivityResult(
            source_id="s1",
            target_id="t1",
            transitive_trust=0.72,
            paths_found=1,
            best_path=best_path,
            all_paths=[best_path],
            max_hops_searched=5,
        )

        assert result.best_path is not None
        assert len(result.all_paths) == 1

    def test_trust_transitivity_result_bounds(self):
        """transitive_trust must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TrustTransitivityResult(
                source_id="s1",
                target_id="t1",
                transitive_trust=1.5,
                paths_found=1,
                max_hops_searched=3,
            )


# =============================================================================
# TrustInfluence Tests
# =============================================================================


class TestTrustInfluence:
    """Tests for TrustInfluence model."""

    def test_valid_trust_influence(self):
        """Valid TrustInfluence data creates model."""
        influence = TrustInfluence(
            node_id="node123",
            node_type="User",
            influence_score=0.85,
            downstream_reach=50,
            upstream_sources=10,
        )

        assert influence.node_id == "node123"
        assert influence.influence_score == 0.85
        assert influence.downstream_reach == 50

    def test_trust_influence_defaults(self):
        """TrustInfluence has sensible defaults."""
        influence = TrustInfluence(
            node_id="node123",
            node_type="Capsule",
            influence_score=0.5,
            downstream_reach=20,
            upstream_sources=5,
        )

        assert influence.trust_amplification == 1.0

    def test_trust_influence_score_minimum(self):
        """influence_score must be >= 0."""
        with pytest.raises(ValidationError):
            TrustInfluence(
                node_id="node123",
                node_type="User",
                influence_score=-0.5,
                downstream_reach=10,
                upstream_sources=5,
            )


# =============================================================================
# GraphMetrics Tests
# =============================================================================


class TestGraphMetrics:
    """Tests for GraphMetrics model."""

    def test_valid_graph_metrics(self):
        """Valid GraphMetrics data creates model."""
        metrics = GraphMetrics(
            total_nodes=1000,
            total_edges=5000,
            density=0.01,
            avg_degree=10.0,
            max_degree=100,
            avg_clustering=0.3,
            connected_components=1,
            largest_component_size=1000,
            avg_trust_level=65.0,
            computation_time_ms=500.0,
        )

        assert metrics.total_nodes == 1000
        assert metrics.total_edges == 5000
        assert metrics.density == 0.01

    def test_graph_metrics_defaults(self):
        """GraphMetrics has sensible defaults."""
        metrics = GraphMetrics(
            total_nodes=100,
            total_edges=200,
            density=0.04,
            avg_degree=4.0,
            max_degree=20,
            avg_clustering=0.2,
            connected_components=5,
            largest_component_size=80,
            avg_trust_level=60.0,
            computation_time_ms=100.0,
        )

        assert metrics.nodes_by_type == {}
        assert metrics.edges_by_type == {}
        assert metrics.diameter is None
        assert metrics.avg_path_length is None
        assert metrics.trust_distribution == {}
        assert metrics.computed_at is not None

    def test_graph_metrics_with_distributions(self):
        """GraphMetrics with distribution data."""
        metrics = GraphMetrics(
            total_nodes=500,
            total_edges=2000,
            nodes_by_type={"Capsule": 400, "User": 100},
            edges_by_type={"DERIVED_FROM": 1500, "RELATED_TO": 500},
            density=0.016,
            avg_degree=8.0,
            max_degree=50,
            avg_clustering=0.25,
            connected_components=2,
            largest_component_size=480,
            diameter=6,
            avg_path_length=3.5,
            avg_trust_level=70.0,
            trust_distribution={"0-20": 10, "20-40": 50, "40-60": 100, "60-80": 200, "80-100": 140},
            computation_time_ms=250.0,
        )

        assert metrics.nodes_by_type["Capsule"] == 400
        assert metrics.diameter == 6

    def test_graph_metrics_bounds(self):
        """GraphMetrics fields have proper bounds."""
        # density out of bounds
        with pytest.raises(ValidationError):
            GraphMetrics(
                total_nodes=100,
                total_edges=200,
                density=1.5,
                avg_degree=4.0,
                max_degree=20,
                avg_clustering=0.2,
                connected_components=5,
                largest_component_size=80,
                avg_trust_level=60.0,
                computation_time_ms=100.0,
            )

        # avg_clustering out of bounds
        with pytest.raises(ValidationError):
            GraphMetrics(
                total_nodes=100,
                total_edges=200,
                density=0.5,
                avg_degree=4.0,
                max_degree=20,
                avg_clustering=-0.1,
                connected_components=5,
                largest_component_size=80,
                avg_trust_level=60.0,
                computation_time_ms=100.0,
            )

        # avg_trust_level out of bounds
        with pytest.raises(ValidationError):
            GraphMetrics(
                total_nodes=100,
                total_edges=200,
                density=0.5,
                avg_degree=4.0,
                max_degree=20,
                avg_clustering=0.2,
                connected_components=5,
                largest_component_size=80,
                avg_trust_level=150.0,
                computation_time_ms=100.0,
            )


# =============================================================================
# PageRankRequest Tests
# =============================================================================


class TestPageRankRequest:
    """Tests for PageRankRequest model."""

    def test_valid_pagerank_request(self):
        """Valid PageRankRequest data creates model."""
        request = PageRankRequest(
            node_label="User",
            relationship_type="FOLLOWS",
            damping_factor=0.9,
            max_iterations=30,
        )

        assert request.node_label == "User"
        assert request.damping_factor == 0.9
        assert request.max_iterations == 30

    def test_pagerank_request_defaults(self):
        """PageRankRequest has sensible defaults."""
        request = PageRankRequest()

        assert request.node_label == "Capsule"
        assert request.relationship_type == "DERIVED_FROM"
        assert request.damping_factor == 0.85
        assert request.max_iterations == 20
        assert request.tolerance == 1e-7
        assert request.limit == 100
        assert request.include_trust_weighting is True

    def test_pagerank_request_damping_factor_bounds(self):
        """damping_factor must be between 0 and 1."""
        with pytest.raises(ValidationError):
            PageRankRequest(damping_factor=1.5)

        with pytest.raises(ValidationError):
            PageRankRequest(damping_factor=-0.1)

    def test_pagerank_request_max_iterations_bounds(self):
        """max_iterations must be between 1 and 100."""
        with pytest.raises(ValidationError):
            PageRankRequest(max_iterations=0)

        with pytest.raises(ValidationError):
            PageRankRequest(max_iterations=101)

    def test_pagerank_request_limit_bounds(self):
        """limit must be between 1 and 100."""
        with pytest.raises(ValidationError):
            PageRankRequest(limit=0)

        with pytest.raises(ValidationError):
            PageRankRequest(limit=101)


# =============================================================================
# CentralityRequest Tests
# =============================================================================


class TestCentralityRequest:
    """Tests for CentralityRequest model."""

    def test_valid_centrality_request(self):
        """Valid CentralityRequest data creates model."""
        request = CentralityRequest(
            algorithm=AlgorithmType.CLOSENESS_CENTRALITY,
            node_label="User",
        )

        assert request.algorithm == AlgorithmType.CLOSENESS_CENTRALITY.value
        assert request.node_label == "User"

    def test_centrality_request_defaults(self):
        """CentralityRequest has sensible defaults."""
        request = CentralityRequest()

        assert request.algorithm == AlgorithmType.BETWEENNESS_CENTRALITY.value
        assert request.node_label == "Capsule"
        assert request.relationship_type is None
        assert request.normalized is True
        assert request.limit == 100

    def test_centrality_request_limit_bounds(self):
        """limit must be between 1 and 100."""
        with pytest.raises(ValidationError):
            CentralityRequest(limit=0)

        with pytest.raises(ValidationError):
            CentralityRequest(limit=101)


# =============================================================================
# CommunityDetectionRequest Tests
# =============================================================================


class TestCommunityDetectionRequest:
    """Tests for CommunityDetectionRequest model."""

    def test_valid_community_detection_request(self):
        """Valid CommunityDetectionRequest data creates model."""
        request = CommunityDetectionRequest(
            algorithm=AlgorithmType.COMMUNITY_LABEL_PROPAGATION,
            node_label="User",
            min_community_size=5,
        )

        assert request.algorithm == AlgorithmType.COMMUNITY_LABEL_PROPAGATION.value
        assert request.min_community_size == 5

    def test_community_detection_request_defaults(self):
        """CommunityDetectionRequest has sensible defaults."""
        request = CommunityDetectionRequest()

        assert request.algorithm == AlgorithmType.COMMUNITY_LOUVAIN.value
        assert request.node_label is None
        assert request.relationship_type is None
        assert request.min_community_size == 2
        assert request.max_communities == 100
        assert request.include_characterization is True

    def test_community_detection_request_min_community_size_minimum(self):
        """min_community_size must be >= 1."""
        with pytest.raises(ValidationError):
            CommunityDetectionRequest(min_community_size=0)


# =============================================================================
# TrustTransitivityRequest Tests
# =============================================================================


class TestTrustTransitivityRequest:
    """Tests for TrustTransitivityRequest model."""

    def test_valid_trust_transitivity_request(self):
        """Valid TrustTransitivityRequest data creates model."""
        request = TrustTransitivityRequest(
            source_id="source123",
            target_id="target456",
            max_hops=3,
            decay_rate=0.15,
        )

        assert request.source_id == "source123"
        assert request.target_id == "target456"
        assert request.max_hops == 3
        assert request.decay_rate == 0.15

    def test_trust_transitivity_request_defaults(self):
        """TrustTransitivityRequest has sensible defaults."""
        request = TrustTransitivityRequest(
            source_id="s1",
            target_id="t1",
        )

        assert request.max_hops == 5
        assert request.decay_rate == 0.1
        assert request.relationship_types == ["DERIVED_FROM", "RELATED_TO"]
        assert request.return_all_paths is False

    def test_trust_transitivity_request_max_hops_bounds(self):
        """max_hops must be between 1 and 10."""
        with pytest.raises(ValidationError):
            TrustTransitivityRequest(
                source_id="s1",
                target_id="t1",
                max_hops=0,
            )

        with pytest.raises(ValidationError):
            TrustTransitivityRequest(
                source_id="s1",
                target_id="t1",
                max_hops=11,
            )

    def test_trust_transitivity_request_decay_rate_bounds(self):
        """decay_rate must be between 0 and 1."""
        with pytest.raises(ValidationError):
            TrustTransitivityRequest(
                source_id="s1",
                target_id="t1",
                decay_rate=-0.1,
            )

        with pytest.raises(ValidationError):
            TrustTransitivityRequest(
                source_id="s1",
                target_id="t1",
                decay_rate=1.5,
            )


# =============================================================================
# NodeSimilarityRequest Tests
# =============================================================================


class TestNodeSimilarityRequest:
    """Tests for NodeSimilarityRequest model."""

    def test_valid_node_similarity_request(self):
        """Valid NodeSimilarityRequest data creates model."""
        request = NodeSimilarityRequest(
            node_label="User",
            relationship_type="FOLLOWS",
            similarity_metric="cosine",
            top_k=20,
        )

        assert request.node_label == "User"
        assert request.similarity_metric == "cosine"
        assert request.top_k == 20

    def test_node_similarity_request_defaults(self):
        """NodeSimilarityRequest has sensible defaults."""
        request = NodeSimilarityRequest()

        assert request.node_label == "Capsule"
        assert request.relationship_type == "DERIVED_FROM"
        assert request.similarity_metric == "jaccard"
        assert request.top_k == 10
        assert request.similarity_cutoff == 0.1
        assert request.source_node_id is None

    def test_node_similarity_request_top_k_bounds(self):
        """top_k must be between 1 and 100."""
        with pytest.raises(ValidationError):
            NodeSimilarityRequest(top_k=0)

        with pytest.raises(ValidationError):
            NodeSimilarityRequest(top_k=101)

    def test_node_similarity_request_cutoff_bounds(self):
        """similarity_cutoff must be between 0 and 1."""
        with pytest.raises(ValidationError):
            NodeSimilarityRequest(similarity_cutoff=-0.1)

        with pytest.raises(ValidationError):
            NodeSimilarityRequest(similarity_cutoff=1.5)


# =============================================================================
# SimilarNode Tests
# =============================================================================


class TestSimilarNode:
    """Tests for SimilarNode model."""

    def test_valid_similar_node(self):
        """Valid SimilarNode data creates model."""
        node = SimilarNode(
            node_id="node123",
            node_type="Capsule",
            title="Test Capsule",
            similarity_score=0.85,
            shared_neighbors=15,
        )

        assert node.node_id == "node123"
        assert node.similarity_score == 0.85
        assert node.shared_neighbors == 15

    def test_similar_node_defaults(self):
        """SimilarNode has sensible defaults."""
        node = SimilarNode(
            node_id="node123",
            node_type="Capsule",
            similarity_score=0.5,
        )

        assert node.title is None
        assert node.shared_neighbors == 0

    def test_similar_node_similarity_score_bounds(self):
        """similarity_score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            SimilarNode(
                node_id="node123",
                node_type="Capsule",
                similarity_score=1.5,
            )

        with pytest.raises(ValidationError):
            SimilarNode(
                node_id="node123",
                node_type="Capsule",
                similarity_score=-0.1,
            )


# =============================================================================
# NodeSimilarityResult Tests
# =============================================================================


class TestNodeSimilarityResult:
    """Tests for NodeSimilarityResult model."""

    def test_valid_node_similarity_result(self):
        """Valid NodeSimilarityResult data creates model."""
        result = NodeSimilarityResult(
            source_id="source123",
            similarity_metric="jaccard",
            top_k=10,
            computation_time_ms=50.0,
        )

        assert result.source_id == "source123"
        assert result.similarity_metric == "jaccard"

    def test_node_similarity_result_defaults(self):
        """NodeSimilarityResult has sensible defaults."""
        result = NodeSimilarityResult(
            similarity_metric="cosine",
            top_k=5,
            computation_time_ms=25.0,
        )

        assert result.source_id is None
        assert result.similar_nodes == []
        assert result.backend_used == GraphBackend.CYPHER.value

    def test_node_similarity_result_with_nodes(self):
        """NodeSimilarityResult with similar nodes."""
        nodes = [
            SimilarNode(node_id="n1", node_type="Capsule", similarity_score=0.9),
            SimilarNode(node_id="n2", node_type="Capsule", similarity_score=0.8),
        ]

        result = NodeSimilarityResult(
            source_id="source123",
            similar_nodes=nodes,
            similarity_metric="overlap",
            top_k=10,
            computation_time_ms=30.0,
        )

        assert len(result.similar_nodes) == 2


# =============================================================================
# ShortestPathRequest Tests
# =============================================================================


class TestShortestPathRequest:
    """Tests for ShortestPathRequest model."""

    def test_valid_shortest_path_request(self):
        """Valid ShortestPathRequest data creates model."""
        request = ShortestPathRequest(
            source_id="source123",
            target_id="target456",
            max_depth=15,
            weighted=True,
        )

        assert request.source_id == "source123"
        assert request.target_id == "target456"
        assert request.max_depth == 15
        assert request.weighted is True

    def test_shortest_path_request_defaults(self):
        """ShortestPathRequest has sensible defaults."""
        request = ShortestPathRequest(
            source_id="s1",
            target_id="t1",
        )

        assert request.relationship_types == ["DERIVED_FROM", "RELATED_TO", "SUPPORTS"]
        assert request.max_depth == 10
        assert request.weighted is False

    def test_shortest_path_request_max_depth_bounds(self):
        """max_depth must be between 1 and 50."""
        with pytest.raises(ValidationError):
            ShortestPathRequest(
                source_id="s1",
                target_id="t1",
                max_depth=0,
            )

        with pytest.raises(ValidationError):
            ShortestPathRequest(
                source_id="s1",
                target_id="t1",
                max_depth=51,
            )


# =============================================================================
# PathNode Tests
# =============================================================================


class TestPathNode:
    """Tests for PathNode model."""

    def test_valid_path_node(self):
        """Valid PathNode data creates model."""
        node = PathNode(
            node_id="node123",
            node_type="Capsule",
            title="Test Capsule",
            trust_level=80,
        )

        assert node.node_id == "node123"
        assert node.node_type == "Capsule"
        assert node.title == "Test Capsule"
        assert node.trust_level == 80

    def test_path_node_defaults(self):
        """PathNode has sensible defaults."""
        node = PathNode(
            node_id="node123",
            node_type="User",
        )

        assert node.title is None
        assert node.trust_level is None


# =============================================================================
# ShortestPathResult Tests
# =============================================================================


class TestShortestPathResult:
    """Tests for ShortestPathResult model."""

    def test_valid_shortest_path_result(self):
        """Valid ShortestPathResult data creates model."""
        result = ShortestPathResult(
            source_id="source123",
            target_id="target456",
            path_found=True,
            path_length=3,
            computation_time_ms=25.0,
        )

        assert result.source_id == "source123"
        assert result.path_found is True
        assert result.path_length == 3

    def test_shortest_path_result_defaults(self):
        """ShortestPathResult has sensible defaults."""
        result = ShortestPathResult(
            source_id="s1",
            target_id="t1",
            computation_time_ms=10.0,
        )

        assert result.path_found is False
        assert result.path_length == 0
        assert result.path_nodes == []
        assert result.path_relationships == []
        assert result.total_trust is None
        assert result.backend_used == GraphBackend.CYPHER.value

    def test_shortest_path_result_with_path(self):
        """ShortestPathResult with path data."""
        path_nodes = [
            PathNode(node_id="s1", node_type="User"),
            PathNode(node_id="m1", node_type="Capsule", trust_level=80),
            PathNode(node_id="t1", node_type="User"),
        ]

        result = ShortestPathResult(
            source_id="s1",
            target_id="t1",
            path_found=True,
            path_length=2,
            path_nodes=path_nodes,
            path_relationships=["CREATED", "DERIVED_FROM"],
            total_trust=0.72,
            computation_time_ms=30.0,
        )

        assert len(result.path_nodes) == 3
        assert len(result.path_relationships) == 2
        assert result.total_trust == 0.72


# =============================================================================
# GraphAlgorithmConfig Tests
# =============================================================================


class TestGraphAlgorithmConfig:
    """Tests for GraphAlgorithmConfig model."""

    def test_valid_graph_algorithm_config(self):
        """Valid GraphAlgorithmConfig data creates model."""
        config = GraphAlgorithmConfig(
            preferred_backend=GraphBackend.NETWORKX,
            cache_ttl_seconds=600,
            max_nodes_for_networkx=5000,
        )

        assert config.preferred_backend == GraphBackend.NETWORKX.value
        assert config.cache_ttl_seconds == 600
        assert config.max_nodes_for_networkx == 5000

    def test_graph_algorithm_config_defaults(self):
        """GraphAlgorithmConfig has sensible defaults."""
        config = GraphAlgorithmConfig()

        assert config.preferred_backend == GraphBackend.GDS.value
        assert config.cache_ttl_seconds == 300
        assert config.max_nodes_for_networkx == 10000
        assert config.gds_graph_name == "forge_graph"
        assert config.enable_caching is True

    def test_graph_algorithm_config_max_nodes_minimum(self):
        """max_nodes_for_networkx must be >= 100."""
        with pytest.raises(ValidationError):
            GraphAlgorithmConfig(max_nodes_for_networkx=50)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
