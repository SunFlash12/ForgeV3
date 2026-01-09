"""
Integration Tests for Graph Extensions

Tests for:
- Graph algorithms (PageRank, centrality, community detection)
- Knowledge query compilation
- Temporal operations (versions, trust timeline)
- Semantic edge operations
- Lineage tracking with semantic edges
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from forge.models.base import TrustLevel, CapsuleType
from forge.models.graph_analysis import NodeRanking, CommunityResult, GraphMetrics, TrustTransitivityResult
from forge.models.semantic_edges import SemanticRelationType, SemanticEdge, SemanticEdgeCreate
from forge.models.temporal import CapsuleVersion, TrustSnapshot, GraphSnapshot


# =============================================================================
# Graph Repository Tests
# =============================================================================

class TestGraphRepository:
    """Tests for GraphRepository."""

    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        client = MagicMock()
        client.execute = AsyncMock()
        client.execute_single = AsyncMock()
        return client

    @pytest.fixture
    def graph_repo(self, mock_db_client):
        """Create GraphRepository with mock client."""
        from forge.repositories.graph_repository import GraphRepository
        return GraphRepository(mock_db_client)

    @pytest.mark.asyncio
    async def test_compute_pagerank_returns_rankings(self, graph_repo, mock_db_client):
        """Test PageRank computation returns properly ranked nodes."""
        # Setup mock response
        mock_db_client.execute.return_value = [
            {"node_id": "cap1", "node_type": "Capsule", "score": 0.95},
            {"node_id": "cap2", "node_type": "Capsule", "score": 0.72},
            {"node_id": "cap3", "node_type": "Capsule", "score": 0.45},
        ]

        result = await graph_repo.compute_pagerank(
            node_label="Capsule",
            relationship_type="DERIVED_FROM",
            limit=10,
        )

        assert len(result) == 3
        assert result[0].score > result[1].score > result[2].score
        assert result[0].rank == 1
        assert result[2].rank == 3

    @pytest.mark.asyncio
    async def test_compute_centrality_degree(self, graph_repo, mock_db_client):
        """Test degree centrality computation."""
        mock_db_client.execute.return_value = [
            {"node_id": "hub1", "node_type": "Capsule", "score": 15.0},
            {"node_id": "leaf1", "node_type": "Capsule", "score": 2.0},
        ]

        result = await graph_repo.compute_centrality(
            centrality_type="degree",
            node_label="Capsule",
        )

        assert len(result) == 2
        assert result[0].node_id == "hub1"
        assert result[0].score == 15.0

    @pytest.mark.asyncio
    async def test_detect_communities(self, graph_repo, mock_db_client):
        """Test community detection returns clusters."""
        mock_db_client.execute.return_value = [
            {"community_id": 0, "size": 5, "node_ids": ["c1", "c2", "c3", "c4", "c5"]},
            {"community_id": 1, "size": 3, "node_ids": ["c6", "c7", "c8"]},
        ]

        result = await graph_repo.detect_communities(
            algorithm="louvain",
            min_community_size=2,
        )

        assert len(result) == 2
        assert result[0].size == 5
        assert len(result[0].node_ids) == 5

    @pytest.mark.asyncio
    async def test_trust_transitivity_calculation(self, graph_repo, mock_db_client):
        """Test trust transitivity through graph paths."""
        mock_db_client.execute_single.return_value = {
            "trust_score": 0.729,  # 0.9^3 for 3 hops
            "path_count": 2,
            "best_path": ["cap1", "cap2", "cap3", "cap4"],
            "best_path_length": 3,
        }

        result = await graph_repo.compute_trust_transitivity(
            source_id="cap1",
            target_id="cap4",
            max_hops=5,
            decay_factor=0.9,
        )

        assert result.trust_score == pytest.approx(0.729, rel=0.01)
        assert result.path_count == 2
        assert len(result.best_path) == 4

    @pytest.mark.asyncio
    async def test_graph_metrics(self, graph_repo, mock_db_client):
        """Test overall graph metrics retrieval."""
        mock_db_client.execute_single.return_value = {
            "total_nodes": 100,
            "total_edges": 250,
            "density": 0.05,
            "avg_clustering": 0.3,
            "connected_components": 2,
            "node_distribution": {"Capsule": 80, "User": 20},
            "edge_distribution": {"DERIVED_FROM": 150, "SEMANTIC_EDGE": 100},
        }

        result = await graph_repo.get_graph_metrics()

        assert result.total_nodes == 100
        assert result.total_edges == 250
        assert result.connected_components == 2


# =============================================================================
# Temporal Repository Tests
# =============================================================================

class TestTemporalRepository:
    """Tests for TemporalRepository."""

    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        client = MagicMock()
        client.execute = AsyncMock()
        client.execute_single = AsyncMock()
        return client

    @pytest.fixture
    def temporal_repo(self, mock_db_client):
        """Create TemporalRepository with mock client."""
        from forge.repositories.temporal_repository import TemporalRepository
        return TemporalRepository(mock_db_client)

    @pytest.mark.asyncio
    async def test_create_version(self, temporal_repo, mock_db_client):
        """Test capsule version creation."""
        mock_db_client.execute_single.return_value = {
            "version_id": "v1",
            "capsule_id": "cap1",
            "version_number": "1.0.0",
            "snapshot_type": "full",
            "change_type": "create",
            "content_hash": "abc123",
            "created_at": datetime.utcnow().isoformat(),
        }

        result = await temporal_repo.create_version(
            capsule_id="cap1",
            content="Test content",
            change_type="create",
            created_by="user1",
        )

        assert result.capsule_id == "cap1"
        assert result.change_type == "create"

    @pytest.mark.asyncio
    async def test_get_version_history(self, temporal_repo, mock_db_client):
        """Test retrieving version history."""
        mock_db_client.execute.return_value = [
            {"version_id": "v3", "version_number": "1.2.0", "created_at": datetime.utcnow().isoformat()},
            {"version_id": "v2", "version_number": "1.1.0", "created_at": (datetime.utcnow() - timedelta(days=1)).isoformat()},
            {"version_id": "v1", "version_number": "1.0.0", "created_at": (datetime.utcnow() - timedelta(days=2)).isoformat()},
        ]

        result = await temporal_repo.get_version_history(capsule_id="cap1", limit=10)

        assert len(result) == 3
        # Should be in reverse chronological order
        assert result[0].version_number == "1.2.0"

    @pytest.mark.asyncio
    async def test_get_capsule_at_time(self, temporal_repo, mock_db_client):
        """Test time-travel query for capsule."""
        target_time = datetime.utcnow() - timedelta(days=5)
        mock_db_client.execute_single.return_value = {
            "version_id": "v2",
            "capsule_id": "cap1",
            "content": "Content at that time",
            "created_at": (target_time - timedelta(hours=1)).isoformat(),
        }

        result = await temporal_repo.get_capsule_at_time(
            capsule_id="cap1",
            timestamp=target_time,
        )

        assert result is not None
        assert result.version_id == "v2"

    @pytest.mark.asyncio
    async def test_get_trust_timeline(self, temporal_repo, mock_db_client):
        """Test trust evolution timeline."""
        mock_db_client.execute.return_value = [
            {"trust_value": 60, "timestamp": datetime.utcnow().isoformat(), "change_type": "derived"},
            {"trust_value": 65, "timestamp": (datetime.utcnow() - timedelta(days=7)).isoformat(), "change_type": "essential"},
            {"trust_value": 50, "timestamp": (datetime.utcnow() - timedelta(days=14)).isoformat(), "change_type": "essential"},
        ]

        result = await temporal_repo.get_trust_timeline(
            entity_id="user1",
            entity_type="User",
            start=datetime.utcnow() - timedelta(days=30),
            end=datetime.utcnow(),
        )

        assert len(result) == 3
        # Trust increased from 50 to 65 to 60


# =============================================================================
# Semantic Edge Tests
# =============================================================================

class TestSemanticEdges:
    """Tests for semantic edge operations."""

    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        client = MagicMock()
        client.execute = AsyncMock()
        client.execute_single = AsyncMock()
        return client

    @pytest.fixture
    def capsule_repo(self, mock_db_client):
        """Create CapsuleRepository with mock client."""
        from forge.repositories.capsule_repository import CapsuleRepository
        return CapsuleRepository(mock_db_client)

    @pytest.mark.asyncio
    async def test_create_semantic_edge_supports(self, capsule_repo, mock_db_client):
        """Test creating SUPPORTS relationship."""
        now = datetime.utcnow()
        mock_db_client.execute_single.return_value = {
            "edge": {
                "id": "edge1",
                "source_id": "cap1",
                "target_id": "cap2",
                "relationship_type": "SUPPORTS",
                "confidence": 0.9,
                "auto_detected": False,
                "bidirectional": False,
                "created_by": "user1",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "properties": "{}",
            }
        }

        edge_data = SemanticEdgeCreate(
            source_id="cap1",
            target_id="cap2",
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.9,
        )

        result = await capsule_repo.create_semantic_edge(
            data=edge_data,
            created_by="user1",
        )

        assert result.relationship_type == SemanticRelationType.SUPPORTS
        assert result.source_id == "cap1"
        assert result.target_id == "cap2"

    @pytest.mark.asyncio
    async def test_create_semantic_edge_contradicts_bidirectional(self, capsule_repo, mock_db_client):
        """Test creating CONTRADICTS relationship (bidirectional)."""
        now = datetime.utcnow()
        mock_db_client.execute_single.return_value = {
            "edge": {
                "id": "edge2",
                "source_id": "cap1",
                "target_id": "cap2",
                "relationship_type": "CONTRADICTS",
                "confidence": 0.85,
                "auto_detected": True,
                "bidirectional": True,  # CONTRADICTS is inherently bidirectional
                "created_by": "system",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "properties": '{"severity": "high"}',
            }
        }

        edge_data = SemanticEdgeCreate(
            source_id="cap1",
            target_id="cap2",
            relationship_type=SemanticRelationType.CONTRADICTS,
            confidence=0.85,
            auto_detected=True,
        )

        result = await capsule_repo.create_semantic_edge(
            data=edge_data,
            created_by="system",
        )

        assert result.relationship_type == SemanticRelationType.CONTRADICTS
        assert result.bidirectional is True

    @pytest.mark.asyncio
    async def test_get_semantic_neighbors(self, capsule_repo, mock_db_client):
        """Test getting semantic neighbors of a capsule."""
        mock_db_client.execute.return_value = [
            {
                "capsule_id": "cap2",
                "title": "Related Capsule",
                "relationship_type": "SUPPORTS",
                "confidence": 0.9,
                "direction": "outgoing",
                "edge_id": "edge1",
            },
            {
                "capsule_id": "cap3",
                "title": "Another Capsule",
                "relationship_type": "ELABORATES",
                "confidence": 0.7,
                "direction": "outgoing",
                "edge_id": "edge2",
            },
        ]

        result = await capsule_repo.get_semantic_neighbors(
            capsule_id="cap1",
            direction="out",
        )

        assert len(result) == 2
        assert result[0].relationship_type == SemanticRelationType.SUPPORTS

    @pytest.mark.asyncio
    async def test_find_contradictions(self, capsule_repo, mock_db_client):
        """Test finding contradiction relationships."""
        now = datetime.utcnow()
        mock_db_client.execute.return_value = [
            {
                "capsule1": {"id": "cap1", "title": "Statement A", "type": "KNOWLEDGE"},
                "capsule2": {"id": "cap2", "title": "Statement B", "type": "KNOWLEDGE"},
                "edge": {
                    "id": "edge1",
                    "source_id": "cap1",
                    "target_id": "cap2",
                    "relationship_type": "CONTRADICTS",
                    "confidence": 0.9,
                    "bidirectional": True,
                    "created_by": "system",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "properties": "{}",
                }
            }
        ]

        result = await capsule_repo.find_contradictions(capsule_id="cap1")

        assert len(result) == 1
        capsule1, capsule2, edge = result[0]
        assert edge.relationship_type == SemanticRelationType.CONTRADICTS


# =============================================================================
# Semantic Edge Detector Tests
# =============================================================================

class TestSemanticEdgeDetector:
    """Tests for SemanticEdgeDetector service."""

    @pytest.fixture
    def mock_capsule_repo(self):
        """Create mock capsule repository."""
        repo = MagicMock()
        repo.find_similar_by_embedding = AsyncMock()
        repo.create_semantic_edge = AsyncMock()
        return repo

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = MagicMock()
        service.embed = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def detector(self, mock_capsule_repo, mock_embedding_service):
        """Create SemanticEdgeDetector with mocks."""
        from forge.services.semantic_edge_detector import (
            SemanticEdgeDetector,
            DetectionConfig,
        )

        config = DetectionConfig(
            similarity_threshold=0.7,
            confidence_threshold=0.7,
            max_candidates=5,
            enabled=True,
        )

        return SemanticEdgeDetector(
            capsule_repo=mock_capsule_repo,
            embedding_service=mock_embedding_service,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_analyze_capsule_finds_similar(self, detector, mock_capsule_repo):
        """Test that analyzer finds similar capsules."""
        from forge.models.capsule import Capsule

        source_capsule = MagicMock()
        source_capsule.id = "cap1"
        source_capsule.title = "Test Capsule"
        source_capsule.content = "Test content about security"
        source_capsule.type = MagicMock(value="KNOWLEDGE")
        source_capsule.embedding = [0.1] * 1536

        similar_capsule = MagicMock()
        similar_capsule.id = "cap2"
        similar_capsule.title = "Similar Capsule"
        similar_capsule.content = "Related security content"
        similar_capsule.type = MagicMock(value="KNOWLEDGE")

        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (similar_capsule, 0.85)
        ]

        # Mock LLM response to skip actual LLM call
        with patch.object(detector, '_classify_relationship') as mock_classify:
            from forge.services.semantic_edge_detector import RelationshipClassification

            mock_classify.return_value = RelationshipClassification(
                relationship_type=None,  # No relationship detected
                confidence=0.3,
                reasoning="Not related enough",
            )

            result = await detector.analyze_capsule(source_capsule, created_by="user1")

            assert result.candidates_analyzed == 1
            assert result.capsule_id == "cap1"


# =============================================================================
# Lineage Tracker with Semantic Edges Tests
# =============================================================================

class TestLineageTrackerSemanticEdges:
    """Tests for lineage tracker with semantic edge support."""

    @pytest.fixture
    def lineage_tracker(self):
        """Create LineageTrackerOverlay."""
        from forge.overlays.lineage_tracker import LineageTrackerOverlay
        return LineageTrackerOverlay(
            enable_anomaly_detection=True,
            enable_metrics=True,
        )

    @pytest.fixture
    def overlay_context(self):
        """Create overlay context."""
        from forge.overlays.base import OverlayContext
        return OverlayContext(
            user_id="user1",
            trust_flame=70,
            correlation_id="test-corr-id",
        )

    @pytest.mark.asyncio
    async def test_handle_semantic_edge_created(self, lineage_tracker, overlay_context):
        """Test handling semantic edge creation event."""
        from forge.models.events import Event, EventType

        # First create the source and target nodes
        await lineage_tracker._handle_capsule_created(
            {"capsule_id": "cap1", "type": "KNOWLEDGE", "title": "Source"},
            overlay_context,
        )
        await lineage_tracker._handle_capsule_created(
            {"capsule_id": "cap2", "type": "KNOWLEDGE", "title": "Target"},
            overlay_context,
        )

        # Now create semantic edge
        result = await lineage_tracker._handle_semantic_edge_created(
            {
                "source_id": "cap1",
                "target_id": "cap2",
                "relationship_type": "SUPPORTS",
                "confidence": 0.9,
                "bidirectional": False,
            },
            overlay_context,
        )

        assert result["edge_tracked"] is True
        assert result["relationship_type"] == "SUPPORTS"

        # Verify node was updated
        node = lineage_tracker.get_node("cap1")
        assert "cap2" in node.supports

    @pytest.mark.asyncio
    async def test_contradiction_detection(self, lineage_tracker, overlay_context):
        """Test contradiction anomaly detection."""
        # Create two capsules
        await lineage_tracker._handle_capsule_created(
            {"capsule_id": "cap1", "type": "KNOWLEDGE"},
            overlay_context,
        )
        await lineage_tracker._handle_capsule_created(
            {"capsule_id": "cap2", "type": "KNOWLEDGE"},
            overlay_context,
        )

        # Create contradiction edge
        await lineage_tracker._handle_semantic_edge_created(
            {
                "source_id": "cap1",
                "target_id": "cap2",
                "relationship_type": "CONTRADICTS",
                "confidence": 0.95,
                "bidirectional": True,
            },
            overlay_context,
        )

        # Check anomaly detection
        anomalies = lineage_tracker._detect_anomalies("cap1")

        assert any(a.anomaly_type == "contradiction_detected" for a in anomalies)

    def test_compute_semantic_distance(self, lineage_tracker, overlay_context):
        """Test semantic distance computation."""
        # Manually add nodes with semantic edges
        from forge.overlays.lineage_tracker import LineageNode, SemanticEdgeInfo

        lineage_tracker._nodes["cap1"] = LineageNode(
            capsule_id="cap1",
            capsule_type="KNOWLEDGE",
            semantic_edges=[
                SemanticEdgeInfo(target_id="cap2", relationship_type="SUPPORTS"),
            ],
        )
        lineage_tracker._nodes["cap2"] = LineageNode(
            capsule_id="cap2",
            capsule_type="KNOWLEDGE",
            semantic_edges=[
                SemanticEdgeInfo(target_id="cap3", relationship_type="ELABORATES"),
            ],
        )
        lineage_tracker._nodes["cap3"] = LineageNode(
            capsule_id="cap3",
            capsule_type="KNOWLEDGE",
        )

        result = lineage_tracker.compute_semantic_distance("cap1", "cap3")

        assert result["found"] is True
        assert result["distance"] == 2
        assert result["path"] == ["cap1", "cap2", "cap3"]
        assert result["relationship_types"] == ["SUPPORTS", "ELABORATES"]

    def test_find_contradiction_clusters(self, lineage_tracker):
        """Test finding contradiction clusters."""
        from forge.overlays.lineage_tracker import LineageNode

        # Create a contradiction cluster: cap1 <-> cap2 <-> cap3
        lineage_tracker._nodes["cap1"] = LineageNode(
            capsule_id="cap1",
            capsule_type="KNOWLEDGE",
            contradicts=["cap2"],
        )
        lineage_tracker._nodes["cap2"] = LineageNode(
            capsule_id="cap2",
            capsule_type="KNOWLEDGE",
            contradicts=["cap1", "cap3"],
        )
        lineage_tracker._nodes["cap3"] = LineageNode(
            capsule_id="cap3",
            capsule_type="KNOWLEDGE",
            contradicts=["cap2"],
        )

        clusters = lineage_tracker.find_contradiction_clusters(min_size=2)

        assert len(clusters) == 1
        assert clusters[0]["size"] == 3
        assert set(clusters[0]["capsule_ids"]) == {"cap1", "cap2", "cap3"}


# =============================================================================
# Knowledge Query Tests
# =============================================================================

class TestKnowledgeQueryOverlay:
    """Tests for knowledge query overlay."""

    @pytest.fixture
    def mock_graph_repo(self):
        """Create mock graph repository."""
        repo = MagicMock()
        repo.execute_cypher = AsyncMock()
        return repo

    @pytest.fixture
    def knowledge_overlay(self):
        """Create KnowledgeQueryOverlay."""
        from forge.overlays.knowledge_query import KnowledgeQueryOverlay
        return KnowledgeQueryOverlay()

    @pytest.mark.asyncio
    async def test_query_intent_parsing(self, knowledge_overlay):
        """Test that query intent is properly parsed."""
        from forge.overlays.knowledge_query import QueryContext

        context = QueryContext(
            question="What are the most influential capsules?",
            user_trust_level=60,
            limit=10,
        )

        # The overlay should identify this as a ranking query
        intent = await knowledge_overlay._parse_intent(context.question)

        # Should detect that this is asking about influence/importance
        assert intent is not None


# =============================================================================
# API Route Integration Tests
# =============================================================================

class TestGraphAPIRoutes:
    """Integration tests for graph API routes."""

    @pytest.mark.asyncio
    async def test_pagerank_endpoint_structure(self):
        """Test PageRank endpoint returns correct structure."""
        # This would be a full integration test with TestClient
        # For now, verify the response model structure
        from forge.api.routes.graph import NodeRankingResponse

        response = NodeRankingResponse(
            node_id="cap1",
            node_type="Capsule",
            score=0.95,
            rank=1,
        )

        assert response.node_id == "cap1"
        assert response.rank == 1

    @pytest.mark.asyncio
    async def test_knowledge_query_response_structure(self):
        """Test knowledge query response structure."""
        from forge.api.routes.graph import KnowledgeQueryResponse

        response = KnowledgeQueryResponse(
            question="Test question",
            answer="Test answer",
            result_count=5,
            execution_time_ms=100.5,
            complexity="medium",
        )

        assert response.result_count == 5
        assert response.complexity == "medium"

    @pytest.mark.asyncio
    async def test_semantic_edge_response_structure(self):
        """Test semantic edge response structure."""
        from forge.api.routes.graph import SemanticEdgeResponse

        response = SemanticEdgeResponse(
            id="edge1",
            source_id="cap1",
            target_id="cap2",
            relationship_type="SUPPORTS",
            properties={"confidence": 0.9},
            created_by="user1",
            created_at="2024-01-01T00:00:00",
            bidirectional=False,
        )

        assert response.relationship_type == "SUPPORTS"
        assert response.properties["confidence"] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
