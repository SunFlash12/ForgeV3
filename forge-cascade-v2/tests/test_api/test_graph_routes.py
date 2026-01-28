"""
Graph Routes Tests for Forge Cascade V2

Comprehensive tests for graph API routes including:
- Graph explorer and navigation
- Graph algorithms (PageRank, centrality, community detection)
- Knowledge query endpoints
- Temporal endpoints (versions, trust timeline)
- Semantic edge management
- Contradiction analysis and resolution
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_capsule():
    """Create a mock capsule."""
    capsule = MagicMock()
    capsule.id = "capsule123"
    capsule.title = "Test Capsule"
    capsule.content = "Test content for the capsule"
    capsule.type = MagicMock(value="KNOWLEDGE")
    capsule.trust_level = 60
    capsule.pagerank_score = 0.5
    capsule.community_id = 1
    capsule.created_at = datetime.now(UTC)
    return capsule


@pytest.fixture
def mock_version():
    """Create a mock capsule version."""
    version = MagicMock()
    version.id = "version123"
    version.capsule_id = "capsule123"
    version.version_number = "1.0.0"
    version.snapshot_type = MagicMock(value="full")
    version.change_type = MagicMock(value="update")
    version.created_by = "user123"
    version.created_at = datetime.now(UTC)
    version.content_snapshot = "Version content"
    return version


@pytest.fixture
def mock_semantic_edge():
    """Create a mock semantic edge."""
    edge = MagicMock()
    edge.id = "edge123"
    edge.source_id = "capsule123"
    edge.target_id = "capsule456"
    edge.relationship_type = MagicMock(value="SUPPORTS")
    edge.properties = {"confidence": 0.8}
    edge.created_by = "user123"
    edge.created_at = datetime.now(UTC)
    edge.bidirectional = False
    edge.confidence = 0.8
    return edge


@pytest.fixture
def mock_graph_repo():
    """Create mock graph repository."""
    repo = AsyncMock()

    # Mock client
    repo.client = AsyncMock()
    repo.client.execute = AsyncMock(return_value=[
        {
            "id": "capsule123",
            "label": "Test Capsule",
            "type": "KNOWLEDGE",
            "trust_level": 60,
            "pagerank_score": 0.5,
            "community_id": 1,
        }
    ])
    repo.client.execute_single = AsyncMock(return_value={
        "id": "capsule123",
        "title": "Test Capsule",
        "type": "KNOWLEDGE",
        "content": "Test content",
        "trust_level": 60,
        "pagerank_score": 0.5,
        "community_id": 1,
    })

    # Mock graph metrics
    mock_metrics = MagicMock()
    mock_metrics.total_nodes = 100
    mock_metrics.total_edges = 200
    mock_metrics.density = 0.02
    mock_metrics.avg_clustering = 0.3
    mock_metrics.connected_components = 5
    mock_metrics.diameter = 10
    mock_metrics.nodes_by_type = {"KNOWLEDGE": 50, "DECISION": 30}
    mock_metrics.edges_by_type = {"SUPPORTS": 100, "CONTRADICTS": 50}
    mock_metrics.avg_degree = 4.0
    repo.get_graph_metrics = AsyncMock(return_value=mock_metrics)

    # Mock PageRank
    mock_ranking = MagicMock()
    mock_ranking.node_id = "capsule123"
    mock_ranking.node_type = "Capsule"
    mock_ranking.score = 0.85
    mock_ranking.rank = 1
    repo.compute_pagerank = AsyncMock(return_value=[mock_ranking])

    # Mock provider for centrality and communities
    repo.provider = AsyncMock()

    centrality_result = MagicMock()
    centrality_result.rankings = [mock_ranking]
    repo.provider.compute_centrality = AsyncMock(return_value=centrality_result)

    community = MagicMock()
    community.community_id = 1
    community.size = 10
    community.density = 0.5
    community.dominant_type = "KNOWLEDGE"
    community.members = [MagicMock(node_id="cap1"), MagicMock(node_id="cap2")]
    community_result = MagicMock()
    community_result.communities = [community]
    repo.provider.detect_communities = AsyncMock(return_value=community_result)

    trust_result = MagicMock()
    trust_result.transitive_trust = 0.7
    trust_result.paths_found = 3
    trust_result.best_path = MagicMock(path_nodes=["a", "b", "c"], path_length=2)
    repo.provider.compute_trust_transitivity = AsyncMock(return_value=trust_result)

    return repo


@pytest.fixture
def mock_capsule_repo(mock_capsule, mock_semantic_edge):
    """Create mock capsule repository."""
    repo = AsyncMock()
    repo.client = AsyncMock()
    repo.client.execute = AsyncMock(return_value=[])
    repo.client.execute_single = AsyncMock(return_value={"total": 0})

    repo.get_by_id = AsyncMock(return_value=mock_capsule)
    repo.create_semantic_edge = AsyncMock(return_value=mock_semantic_edge)
    repo.get_semantic_edge = AsyncMock(return_value=mock_semantic_edge)
    repo.get_semantic_edges = AsyncMock(return_value=[mock_semantic_edge])
    repo.delete_semantic_edge = AsyncMock()

    neighbor = MagicMock()
    neighbor.capsule_id = "capsule456"
    neighbor.title = "Neighbor Capsule"
    neighbor.capsule_type = "KNOWLEDGE"
    neighbor.relationship_type = MagicMock(value="SUPPORTS")
    neighbor.direction = "out"
    neighbor.confidence = 0.8
    repo.get_semantic_neighbors = AsyncMock(return_value=[neighbor])

    repo.find_contradictions = AsyncMock(return_value=[])

    cluster = MagicMock()
    cluster.cluster_id = "cluster1"
    cluster.capsule_ids = ["cap1", "cap2"]
    cluster.size = 2
    cluster.edges = [mock_semantic_edge]
    cluster.overall_severity = MagicMock(value="medium")
    cluster.resolution_status = MagicMock(value="unresolved")
    repo.find_contradiction_clusters = AsyncMock(return_value=[cluster])

    return repo


@pytest.fixture
def mock_temporal_repo(mock_version):
    """Create mock temporal repository."""
    repo = AsyncMock()
    repo.client = AsyncMock()
    repo.client.execute_single = AsyncMock(return_value={"version": {
        "id": "version123",
        "capsule_id": "capsule123",
        "version_number": "1.0.0",
        "snapshot_type": "full",
        "change_type": "update",
        "created_by": "user123",
        "created_at": datetime.now(UTC).isoformat(),
        "content_snapshot": "Version content",
    }})

    version_history = MagicMock()
    version_history.versions = [mock_version]
    repo.get_version_history = AsyncMock(return_value=version_history)

    repo.get_capsule_at_time = AsyncMock(return_value=mock_version)

    comparison = MagicMock()
    comparison.capsule_id = "capsule123"
    comparison.version_a_id = "v1"
    comparison.version_a_number = "1.0.0"
    comparison.version_b_id = "v2"
    comparison.version_b_number = "1.0.1"
    comparison.diff = MagicMock(
        added_lines=5,
        removed_lines=2,
        modified_sections=["intro"],
        summary="Minor updates",
    )
    repo.diff_versions = AsyncMock(return_value=comparison)

    trust_snapshot = MagicMock()
    trust_snapshot.trust_value = 60
    trust_snapshot.created_at = datetime.now(UTC)
    trust_snapshot.change_type = MagicMock(value="contribution")
    trust_snapshot.reason = "Good contribution"

    trust_timeline = MagicMock()
    trust_timeline.snapshots = [trust_snapshot]
    repo.get_trust_timeline = AsyncMock(return_value=trust_timeline)

    graph_snapshot = MagicMock()
    graph_snapshot.id = "snapshot123"
    graph_snapshot.created_at = datetime.now(UTC)
    graph_snapshot.total_nodes = 100
    graph_snapshot.total_edges = 200
    graph_snapshot.density = 0.02
    graph_snapshot.avg_degree = 4.0
    graph_snapshot.connected_components = 5
    graph_snapshot.nodes_by_type = {"KNOWLEDGE": 50}
    graph_snapshot.edges_by_type = {"SUPPORTS": 100}
    graph_snapshot.avg_trust = 55
    graph_snapshot.community_count = 10
    graph_snapshot.active_anomalies = 2
    repo.create_graph_snapshot = AsyncMock(return_value=graph_snapshot)
    repo.get_latest_graph_snapshot = AsyncMock(return_value=graph_snapshot)

    return repo


@pytest.fixture
def mock_overlay_manager():
    """Create mock overlay manager."""
    manager = MagicMock()
    manager.get_by_name = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_audit_repo():
    """Create mock audit repository."""
    repo = AsyncMock()
    repo.log_capsule_action = AsyncMock()
    return repo


@pytest.fixture
def mock_event_system():
    """Create mock event system."""
    system = AsyncMock()
    system.publish = AsyncMock()
    return system


@pytest.fixture
def mock_active_user():
    """Create mock active user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.trust_flame = 50
    user.trust_level = MagicMock(value=50)
    user.is_active = True
    return user


@pytest.fixture
def mock_standard_user():
    """Create mock standard user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "standarduser"
    user.trust_flame = 40
    user.trust_level = MagicMock(value=40)
    user.is_active = True
    return user


@pytest.fixture
def mock_trusted_user():
    """Create mock trusted user."""
    user = MagicMock()
    user.id = "user456"
    user.username = "trusteduser"
    user.trust_flame = 60
    user.trust_level = MagicMock(value=60)
    user.is_active = True
    return user


@pytest.fixture
def graph_app(
    mock_graph_repo,
    mock_capsule_repo,
    mock_temporal_repo,
    mock_overlay_manager,
    mock_audit_repo,
    mock_event_system,
    mock_active_user,
):
    """Create FastAPI app with graph router and mocked dependencies."""
    from forge.api.routes.graph import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/graph")

    # Override dependencies
    from forge.api.dependencies import (
        GraphRepoDep,
        CapsuleRepoDep,
        TemporalRepoDep,
        OverlayManagerDep,
        AuditRepoDep,
        EventSystemDep,
        ActiveUserDep,
        StandardUserDep,
        TrustedUserDep,
        CorrelationIdDep,
    )

    # Create override functions
    async def get_graph_repo():
        return mock_graph_repo

    async def get_capsule_repo():
        return mock_capsule_repo

    async def get_temporal_repo():
        return mock_temporal_repo

    async def get_overlay_manager():
        return mock_overlay_manager

    async def get_audit_repo():
        return mock_audit_repo

    async def get_event_system():
        return mock_event_system

    def get_correlation_id():
        return "test-correlation-id"

    # Apply overrides using actual dependency injection patterns
    from forge.api.dependencies import (
        get_graph_repository,
        get_capsule_repository,
        get_temporal_repository,
        get_overlay_manager as dep_get_overlay,
        get_audit_repository,
        get_event_system as dep_get_event,
        get_current_active_user,
        get_current_standard_user,
        get_current_trusted_user,
        get_correlation_id as dep_get_correlation_id,
    )

    app.dependency_overrides[get_graph_repository] = get_graph_repo
    app.dependency_overrides[get_capsule_repository] = get_capsule_repo
    app.dependency_overrides[get_temporal_repository] = get_temporal_repo
    app.dependency_overrides[dep_get_overlay] = get_overlay_manager
    app.dependency_overrides[get_audit_repository] = get_audit_repo
    app.dependency_overrides[dep_get_event] = get_event_system
    app.dependency_overrides[get_current_active_user] = lambda: mock_active_user
    app.dependency_overrides[get_current_standard_user] = lambda: mock_active_user
    app.dependency_overrides[get_current_trusted_user] = lambda: mock_active_user
    app.dependency_overrides[dep_get_correlation_id] = get_correlation_id

    return app


@pytest.fixture
def client(graph_app):
    """Create test client."""
    return TestClient(graph_app)


# =============================================================================
# Graph Explorer Tests
# =============================================================================


class TestGraphExplorer:
    """Tests for graph explorer endpoints."""

    def test_explore_graph(self, client: TestClient):
        """Explore graph with default parameters."""
        response = client.get("/api/v1/graph/explore")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "communities" in data
        assert "metrics" in data

    def test_explore_graph_filtered(self, client: TestClient):
        """Explore graph with filters."""
        response = client.get(
            "/api/v1/graph/explore?type=KNOWLEDGE&min_trust=40&limit=50"
        )

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data

    def test_explore_graph_by_community(self, client: TestClient):
        """Explore graph filtered by community."""
        response = client.get("/api/v1/graph/explore?community=1")

        assert response.status_code == 200

    def test_explore_graph_limit_validation(self, client: TestClient):
        """Explore graph with limit validation."""
        # Limit must be between 10 and 100
        response = client.get("/api/v1/graph/explore?limit=5")

        assert response.status_code == 422


class TestNodeNeighbors:
    """Tests for node neighbors endpoint."""

    def test_get_node_neighbors(self, client: TestClient):
        """Get neighbors of a node."""
        response = client.get("/api/v1/graph/node/capsule123/neighbors")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "neighbors" in data

    def test_get_node_neighbors_not_found(self, client: TestClient, mock_graph_repo):
        """Get neighbors of non-existent node."""
        mock_graph_repo.client.execute_single.return_value = None

        response = client.get("/api/v1/graph/node/nonexistent/neighbors")

        assert response.status_code == 404

    def test_get_node_neighbors_with_limit(self, client: TestClient):
        """Get neighbors with custom limit."""
        response = client.get("/api/v1/graph/node/capsule123/neighbors?limit=50")

        assert response.status_code == 200


class TestFindPaths:
    """Tests for path finding endpoint."""

    def test_find_paths(self, client: TestClient):
        """Find paths between two nodes."""
        response = client.get("/api/v1/graph/paths/capsule123/capsule456")

        assert response.status_code == 200
        data = response.json()
        assert "source_id" in data
        assert "target_id" in data
        assert "paths_found" in data
        assert "paths" in data

    def test_find_paths_with_options(self, client: TestClient):
        """Find paths with custom options."""
        response = client.get(
            "/api/v1/graph/paths/capsule123/capsule456?max_hops=3&limit=10"
        )

        assert response.status_code == 200


# =============================================================================
# Graph Algorithm Tests
# =============================================================================


class TestPageRank:
    """Tests for PageRank endpoint."""

    def test_compute_pagerank(self, client: TestClient):
        """Compute PageRank scores."""
        response = client.post(
            "/api/v1/graph/algorithms/pagerank",
            json={
                "node_label": "Capsule",
                "relationship_type": "DERIVED_FROM",
                "damping_factor": 0.85,
                "max_iterations": 20,
                "limit": 50,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "node_id" in data[0]
            assert "score" in data[0]
            assert "rank" in data[0]

    def test_compute_pagerank_minimal(self, client: TestClient):
        """Compute PageRank with defaults."""
        response = client.post("/api/v1/graph/algorithms/pagerank", json={})

        assert response.status_code == 200


class TestCentrality:
    """Tests for centrality computation endpoint."""

    def test_compute_degree_centrality(self, client: TestClient):
        """Compute degree centrality."""
        response = client.post(
            "/api/v1/graph/algorithms/centrality",
            json={
                "centrality_type": "degree",
                "node_label": "Capsule",
                "limit": 50,
            },
        )

        assert response.status_code == 200

    def test_compute_betweenness_centrality(self, client: TestClient):
        """Compute betweenness centrality."""
        response = client.post(
            "/api/v1/graph/algorithms/centrality",
            json={"centrality_type": "betweenness"},
        )

        assert response.status_code == 200

    def test_compute_closeness_centrality(self, client: TestClient):
        """Compute closeness centrality."""
        response = client.post(
            "/api/v1/graph/algorithms/centrality",
            json={"centrality_type": "closeness"},
        )

        assert response.status_code == 200


class TestCommunityDetection:
    """Tests for community detection endpoint."""

    def test_detect_communities_louvain(self, client: TestClient):
        """Detect communities using Louvain algorithm."""
        response = client.post(
            "/api/v1/graph/algorithms/communities",
            json={
                "algorithm": "louvain",
                "node_label": "Capsule",
                "min_community_size": 2,
                "limit": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "community_id" in data[0]
            assert "size" in data[0]
            assert "node_ids" in data[0]

    def test_detect_communities_label_propagation(self, client: TestClient):
        """Detect communities using label propagation."""
        response = client.post(
            "/api/v1/graph/algorithms/communities",
            json={"algorithm": "label_propagation"},
        )

        assert response.status_code == 200


class TestTrustTransitivity:
    """Tests for trust transitivity endpoint."""

    def test_compute_trust_transitivity(self, client: TestClient):
        """Compute transitive trust."""
        response = client.post(
            "/api/v1/graph/algorithms/trust-transitivity",
            json={
                "source_id": "capsule123",
                "target_id": "capsule456",
                "max_hops": 5,
                "decay_factor": 0.9,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "source_id" in data
        assert "target_id" in data
        assert "trust_score" in data
        assert "path_count" in data


class TestGraphMetrics:
    """Tests for graph metrics endpoint."""

    def test_get_graph_metrics(self, client: TestClient):
        """Get overall graph metrics."""
        response = client.get("/api/v1/graph/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "density" in data
        assert "connected_components" in data


# =============================================================================
# Knowledge Query Tests
# =============================================================================


class TestKnowledgeQuery:
    """Tests for knowledge query endpoints."""

    def test_query_knowledge(self, client: TestClient):
        """Query knowledge graph with natural language."""
        response = client.post(
            "/api/v1/graph/query",
            json={
                "question": "What are the most influential capsules?",
                "limit": 20,
                "include_results": True,
                "debug": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "question" in data
        assert "answer" in data
        assert "result_count" in data
        assert "execution_time_ms" in data

    def test_query_knowledge_with_debug(self, client: TestClient):
        """Query knowledge graph with debug info."""
        response = client.post(
            "/api/v1/graph/query",
            json={
                "question": "Find all decisions about authentication",
                "debug": True,
            },
        )

        assert response.status_code == 200

    def test_query_knowledge_validation(self, client: TestClient):
        """Query with too short question."""
        response = client.post(
            "/api/v1/graph/query",
            json={"question": "Hi"},  # Less than 5 chars
        )

        assert response.status_code == 422

    def test_get_query_suggestions(self, client: TestClient):
        """Get query suggestions."""
        response = client.get("/api/v1/graph/query/suggestions")

        assert response.status_code == 200
        data = response.json()
        assert "examples" in data
        assert isinstance(data["examples"], list)

    def test_get_queryable_schema(self, client: TestClient):
        """Get queryable schema."""
        response = client.get("/api/v1/graph/query/schema")

        assert response.status_code == 200
        data = response.json()
        assert "node_labels" in data
        assert "relationship_types" in data
        assert "queryable_properties" in data


# =============================================================================
# Temporal Tests
# =============================================================================


class TestCapsuleVersions:
    """Tests for capsule version endpoints."""

    def test_get_capsule_versions(self, client: TestClient):
        """Get capsule version history."""
        response = client.get("/api/v1/graph/capsules/capsule123/versions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "version_id" in data[0]
            assert "capsule_id" in data[0]
            assert "version_number" in data[0]

    def test_get_capsule_versions_not_found(self, client: TestClient, mock_capsule_repo):
        """Get versions of non-existent capsule."""
        mock_capsule_repo.get_by_id.return_value = None

        response = client.get("/api/v1/graph/capsules/nonexistent/versions")

        assert response.status_code == 404

    def test_get_specific_version(self, client: TestClient):
        """Get specific capsule version."""
        response = client.get("/api/v1/graph/capsules/capsule123/versions/version123")

        assert response.status_code == 200
        data = response.json()
        assert "version_id" in data
        assert "content" in data

    def test_get_capsule_at_time(self, client: TestClient):
        """Get capsule state at specific time."""
        timestamp = datetime.now(UTC).isoformat()
        response = client.get(
            f"/api/v1/graph/capsules/capsule123/at-time?timestamp={timestamp}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "capsule_id" in data
        assert "found" in data

    def test_get_capsule_at_time_invalid_timestamp(self, client: TestClient):
        """Get capsule at time with invalid timestamp."""
        response = client.get(
            "/api/v1/graph/capsules/capsule123/at-time?timestamp=invalid"
        )

        assert response.status_code == 400

    def test_diff_capsule_versions(self, client: TestClient):
        """Diff two capsule versions."""
        response = client.get(
            "/api/v1/graph/capsules/capsule123/versions/diff?version_a=v1&version_b=v2"
        )

        assert response.status_code == 200
        data = response.json()
        assert "version_a" in data
        assert "version_b" in data
        assert "diff" in data


class TestTrustTimeline:
    """Tests for trust timeline endpoint."""

    def test_get_trust_timeline(self, client: TestClient):
        """Get trust timeline for entity."""
        response = client.get("/api/v1/graph/trust/User/user123/timeline")

        assert response.status_code == 200
        data = response.json()
        assert "entity_id" in data
        assert "entity_type" in data
        assert "timeline" in data
        assert "snapshot_count" in data

    def test_get_trust_timeline_with_dates(self, client: TestClient):
        """Get trust timeline with date range."""
        start = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        end = datetime.now(UTC).isoformat()

        response = client.get(
            f"/api/v1/graph/trust/Capsule/capsule123/timeline?start={start}&end={end}"
        )

        assert response.status_code == 200

    def test_get_trust_timeline_invalid_entity_type(self, client: TestClient):
        """Get trust timeline with invalid entity type."""
        response = client.get("/api/v1/graph/trust/Invalid/id123/timeline")

        assert response.status_code == 400


class TestGraphSnapshots:
    """Tests for graph snapshot endpoints."""

    def test_create_graph_snapshot(self, client: TestClient):
        """Create graph snapshot (requires TRUSTED)."""
        response = client.post("/api/v1/graph/snapshots/graph")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert "snapshot_id" in data
            assert "metrics" in data

    def test_get_latest_graph_snapshot(self, client: TestClient):
        """Get latest graph snapshot."""
        response = client.get("/api/v1/graph/snapshots/graph/latest")

        assert response.status_code == 200
        data = response.json()
        assert "snapshot_id" in data
        assert "found" in data

    def test_get_latest_graph_snapshot_none(
        self, client: TestClient, mock_temporal_repo
    ):
        """Get latest snapshot when none exists."""
        mock_temporal_repo.get_latest_graph_snapshot.return_value = None

        response = client.get("/api/v1/graph/snapshots/graph/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False


# =============================================================================
# Semantic Edge Tests
# =============================================================================


class TestCreateSemanticEdge:
    """Tests for semantic edge creation."""

    def test_create_semantic_edge(self, client: TestClient):
        """Create semantic edge."""
        response = client.post(
            "/api/v1/graph/edges",
            json={
                "source_id": "capsule123",
                "target_id": "capsule456",
                "relationship_type": "SUPPORTS",
                "properties": {"confidence": 0.9},
                "bidirectional": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "source_id" in data
        assert "target_id" in data
        assert "relationship_type" in data

    def test_create_semantic_edge_invalid_type(self, client: TestClient):
        """Create edge with invalid relationship type."""
        response = client.post(
            "/api/v1/graph/edges",
            json={
                "source_id": "capsule123",
                "target_id": "capsule456",
                "relationship_type": "INVALID_TYPE",
            },
        )

        assert response.status_code == 400

    def test_create_semantic_edge_source_not_found(
        self, client: TestClient, mock_capsule_repo
    ):
        """Create edge with non-existent source."""
        mock_capsule_repo.get_by_id.side_effect = [None, MagicMock()]

        response = client.post(
            "/api/v1/graph/edges",
            json={
                "source_id": "nonexistent",
                "target_id": "capsule456",
                "relationship_type": "SUPPORTS",
            },
        )

        assert response.status_code == 404


class TestGetCapsuleEdges:
    """Tests for getting capsule edges."""

    def test_get_capsule_edges(self, client: TestClient):
        """Get edges for a capsule."""
        response = client.get("/api/v1/graph/capsules/capsule123/edges")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_capsule_edges_filtered(self, client: TestClient):
        """Get edges filtered by direction and type."""
        response = client.get(
            "/api/v1/graph/capsules/capsule123/edges?direction=out&relationship_type=SUPPORTS"
        )

        assert response.status_code == 200

    def test_get_capsule_edges_not_found(self, client: TestClient, mock_capsule_repo):
        """Get edges for non-existent capsule."""
        mock_capsule_repo.get_by_id.return_value = None

        response = client.get("/api/v1/graph/capsules/nonexistent/edges")

        assert response.status_code == 404


class TestSemanticNeighbors:
    """Tests for semantic neighbors endpoint."""

    def test_get_semantic_neighbors(self, client: TestClient):
        """Get semantic neighbors of a capsule."""
        response = client.get("/api/v1/graph/capsules/capsule123/neighbors")

        assert response.status_code == 200
        data = response.json()
        assert "capsule_id" in data
        assert "neighbors" in data
        assert "total" in data


class TestContradictions:
    """Tests for contradiction endpoints."""

    def test_get_contradictions(self, client: TestClient):
        """Get contradictions for a capsule."""
        response = client.get("/api/v1/graph/capsules/capsule123/contradictions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestDeleteSemanticEdge:
    """Tests for semantic edge deletion."""

    def test_delete_semantic_edge(self, client: TestClient):
        """Delete semantic edge by creator."""
        response = client.delete("/api/v1/graph/edges/edge123")

        assert response.status_code == 204

    def test_delete_semantic_edge_not_found(
        self, client: TestClient, mock_capsule_repo
    ):
        """Delete non-existent edge."""
        mock_capsule_repo.get_semantic_edge.return_value = None

        response = client.delete("/api/v1/graph/edges/nonexistent")

        assert response.status_code == 404

    def test_delete_semantic_edge_not_owner(
        self, client: TestClient, mock_semantic_edge
    ):
        """Delete edge by non-creator."""
        mock_semantic_edge.created_by = "other_user"

        with patch("forge.api.routes.graph.is_admin", return_value=False):
            response = client.delete("/api/v1/graph/edges/edge123")

            assert response.status_code == 403


# =============================================================================
# Analysis Tests
# =============================================================================


class TestContradictionClusters:
    """Tests for contradiction cluster analysis."""

    def test_get_contradiction_clusters(self, client: TestClient):
        """Get contradiction clusters."""
        response = client.get("/api/v1/graph/analysis/contradiction-clusters")

        assert response.status_code == 200
        data = response.json()
        assert "cluster_count" in data
        assert "clusters" in data

    def test_get_contradiction_clusters_with_min_size(self, client: TestClient):
        """Get clusters with minimum size filter."""
        response = client.get(
            "/api/v1/graph/analysis/contradiction-clusters?min_size=3"
        )

        assert response.status_code == 200


class TestRefreshAnalysis:
    """Tests for analysis refresh endpoint."""

    def test_refresh_graph_analysis(self, client: TestClient):
        """Refresh graph analysis (requires TRUSTED)."""
        response = client.post("/api/v1/graph/analysis/refresh")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert data["refreshed"] is True


# =============================================================================
# Contradiction Resolution Tests
# =============================================================================


class TestContradictionResolution:
    """Tests for contradiction resolution endpoints."""

    def test_get_unresolved_contradictions(self, client: TestClient):
        """Get unresolved contradictions."""
        response = client.get("/api/v1/graph/contradictions/unresolved")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "contradictions" in data

    def test_get_unresolved_contradictions_pagination(self, client: TestClient):
        """Get unresolved contradictions with pagination."""
        response = client.get(
            "/api/v1/graph/contradictions/unresolved?limit=10&offset=5"
        )

        assert response.status_code == 200

    def test_resolve_contradiction(self, client: TestClient):
        """Resolve a contradiction (requires TRUSTED)."""
        response = client.post(
            "/api/v1/graph/contradictions/edge123/resolve",
            json={
                "resolution_type": "keep_both",
                "notes": "Both perspectives are valid",
            },
        )

        assert response.status_code in [200, 400, 403, 404]

    def test_resolve_contradiction_supersede(self, client: TestClient):
        """Resolve contradiction by superseding."""
        response = client.post(
            "/api/v1/graph/contradictions/edge123/resolve",
            json={
                "resolution_type": "supersede",
                "winning_capsule_id": "capsule123",
                "notes": "Newer version is more accurate",
            },
        )

        assert response.status_code in [200, 400, 403, 404]

    def test_get_contradiction_stats(self, client: TestClient):
        """Get contradiction statistics."""
        response = client.get("/api/v1/graph/contradictions/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "resolved" in data
        assert "unresolved" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
