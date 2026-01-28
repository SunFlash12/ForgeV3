"""
Semantic Edge Model Tests for Forge Cascade V2

Comprehensive tests for semantic edge models including:
- SemanticRelationType enum and its properties
- ContradictionSeverity, ContradictionStatus, EvidenceType enums
- SemanticEdgeBase, SemanticEdgeCreate, SemanticEdge models
- SemanticEdgeWithNodes model
- Specialized edge types (ContradictionEdge, SupportEdge, SupersedesEdge)
- Semantic graph analysis models
- LLM auto-detection models
- Query models
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.semantic_edges import (
    ContradictionCluster,
    ContradictionEdge,
    ContradictionQuery,
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceType,
    RelationshipClassification,
    SemanticAnalysisRequest,
    SemanticAnalysisResult,
    SemanticDistance,
    SemanticEdge,
    SemanticEdgeBase,
    SemanticEdgeCreate,
    SemanticEdgeQuery,
    SemanticEdgeWithNodes,
    SemanticNeighbor,
    SemanticRelationType,
    SupportEdge,
    SupersedesEdge,
)


# =============================================================================
# SemanticRelationType Enum Tests
# =============================================================================


class TestSemanticRelationType:
    """Tests for SemanticRelationType enum."""

    def test_semantic_relation_type_values(self):
        """SemanticRelationType has expected values."""
        assert SemanticRelationType.RELATED_TO.value == "RELATED_TO"
        assert SemanticRelationType.CONTRADICTS.value == "CONTRADICTS"
        assert SemanticRelationType.SUPPORTS.value == "SUPPORTS"
        assert SemanticRelationType.ELABORATES.value == "ELABORATES"
        assert SemanticRelationType.SUPERSEDES.value == "SUPERSEDES"
        assert SemanticRelationType.REFERENCES.value == "REFERENCES"
        assert SemanticRelationType.IMPLEMENTS.value == "IMPLEMENTS"
        assert SemanticRelationType.EXTENDS.value == "EXTENDS"

    def test_semantic_relation_type_count(self):
        """SemanticRelationType has expected number of values."""
        assert len(SemanticRelationType) == 8

    def test_is_bidirectional_property(self):
        """is_bidirectional property works correctly."""
        # Bidirectional relationships
        assert SemanticRelationType.RELATED_TO.is_bidirectional is True
        assert SemanticRelationType.CONTRADICTS.is_bidirectional is True

        # Directed relationships
        assert SemanticRelationType.SUPPORTS.is_bidirectional is False
        assert SemanticRelationType.ELABORATES.is_bidirectional is False
        assert SemanticRelationType.SUPERSEDES.is_bidirectional is False
        assert SemanticRelationType.REFERENCES.is_bidirectional is False
        assert SemanticRelationType.IMPLEMENTS.is_bidirectional is False
        assert SemanticRelationType.EXTENDS.is_bidirectional is False

    def test_inverse_property_bidirectional(self):
        """Bidirectional relationships return themselves as inverse."""
        assert SemanticRelationType.RELATED_TO.inverse == SemanticRelationType.RELATED_TO
        assert SemanticRelationType.CONTRADICTS.inverse == SemanticRelationType.CONTRADICTS

    def test_inverse_property_directed(self):
        """Directed relationships have no inverse."""
        assert SemanticRelationType.SUPPORTS.inverse is None
        assert SemanticRelationType.ELABORATES.inverse is None
        assert SemanticRelationType.SUPERSEDES.inverse is None
        assert SemanticRelationType.REFERENCES.inverse is None
        assert SemanticRelationType.IMPLEMENTS.inverse is None
        assert SemanticRelationType.EXTENDS.inverse is None


# =============================================================================
# ContradictionSeverity Enum Tests
# =============================================================================


class TestContradictionSeverity:
    """Tests for ContradictionSeverity enum."""

    def test_contradiction_severity_values(self):
        """ContradictionSeverity has expected values."""
        assert ContradictionSeverity.LOW.value == "low"
        assert ContradictionSeverity.MEDIUM.value == "medium"
        assert ContradictionSeverity.HIGH.value == "high"
        assert ContradictionSeverity.CRITICAL.value == "critical"

    def test_contradiction_severity_count(self):
        """ContradictionSeverity has expected number of values."""
        assert len(ContradictionSeverity) == 4


# =============================================================================
# ContradictionStatus Enum Tests
# =============================================================================


class TestContradictionStatus:
    """Tests for ContradictionStatus enum."""

    def test_contradiction_status_values(self):
        """ContradictionStatus has expected values."""
        assert ContradictionStatus.UNRESOLVED.value == "unresolved"
        assert ContradictionStatus.UNDER_REVIEW.value == "under_review"
        assert ContradictionStatus.RESOLVED.value == "resolved"
        assert ContradictionStatus.ACCEPTED.value == "accepted"

    def test_contradiction_status_count(self):
        """ContradictionStatus has expected number of values."""
        assert len(ContradictionStatus) == 4


# =============================================================================
# EvidenceType Enum Tests
# =============================================================================


class TestEvidenceType:
    """Tests for EvidenceType enum."""

    def test_evidence_type_values(self):
        """EvidenceType has expected values."""
        assert EvidenceType.EMPIRICAL.value == "empirical"
        assert EvidenceType.THEORETICAL.value == "theoretical"
        assert EvidenceType.CITATION.value == "citation"
        assert EvidenceType.EXAMPLE.value == "example"
        assert EvidenceType.CONSENSUS.value == "consensus"

    def test_evidence_type_count(self):
        """EvidenceType has expected number of values."""
        assert len(EvidenceType) == 5


# =============================================================================
# SemanticEdgeBase Tests
# =============================================================================


class TestSemanticEdgeBase:
    """Tests for SemanticEdgeBase model."""

    def test_valid_semantic_edge_base(self):
        """Valid SemanticEdgeBase data creates model."""
        edge = SemanticEdgeBase(
            source_id="source123",
            target_id="target456",
            relationship_type=SemanticRelationType.SUPPORTS,
        )

        assert edge.source_id == "source123"
        assert edge.target_id == "target456"
        assert edge.relationship_type == SemanticRelationType.SUPPORTS.value

    def test_semantic_edge_base_defaults(self):
        """SemanticEdgeBase has sensible defaults."""
        edge = SemanticEdgeBase(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.RELATED_TO,
        )

        assert edge.confidence == 1.0
        assert edge.reason is None
        assert edge.auto_detected is False

    def test_semantic_edge_base_with_optional_fields(self):
        """SemanticEdgeBase with optional fields."""
        edge = SemanticEdgeBase(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.ELABORATES,
            confidence=0.85,
            reason="Source provides detailed explanation of target concept",
            auto_detected=True,
        )

        assert edge.confidence == 0.85
        assert edge.reason == "Source provides detailed explanation of target concept"
        assert edge.auto_detected is True

    def test_semantic_edge_base_confidence_bounds(self):
        """confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            SemanticEdgeBase(
                source_id="s1",
                target_id="t1",
                relationship_type=SemanticRelationType.SUPPORTS,
                confidence=1.5,
            )

        with pytest.raises(ValidationError):
            SemanticEdgeBase(
                source_id="s1",
                target_id="t1",
                relationship_type=SemanticRelationType.SUPPORTS,
                confidence=-0.1,
            )

    def test_semantic_edge_base_reason_max_length(self):
        """reason has max length of 1000 characters."""
        long_reason = "a" * 1001
        with pytest.raises(ValidationError):
            SemanticEdgeBase(
                source_id="s1",
                target_id="t1",
                relationship_type=SemanticRelationType.SUPPORTS,
                reason=long_reason,
            )


# =============================================================================
# SemanticEdgeCreate Tests
# =============================================================================


class TestSemanticEdgeCreate:
    """Tests for SemanticEdgeCreate model."""

    def test_valid_semantic_edge_create(self):
        """Valid SemanticEdgeCreate data creates model."""
        edge = SemanticEdgeCreate(
            source_id="source123",
            target_id="target456",
            relationship_type=SemanticRelationType.SUPPORTS,
            properties={"evidence_type": "empirical"},
        )

        assert edge.source_id == "source123"
        assert edge.properties["evidence_type"] == "empirical"

    def test_semantic_edge_create_defaults(self):
        """SemanticEdgeCreate has sensible defaults."""
        edge = SemanticEdgeCreate(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.RELATED_TO,
        )

        assert edge.properties == {}

    def test_semantic_edge_create_validator_contradicts(self):
        """Validator adds defaults for CONTRADICTS relationship."""
        edge = SemanticEdgeCreate(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.CONTRADICTS,
            properties={},
        )

        assert edge.properties["severity"] == ContradictionSeverity.MEDIUM.value
        assert edge.properties["resolution_status"] == ContradictionStatus.UNRESOLVED.value

    def test_semantic_edge_create_validator_supports(self):
        """Validator adds defaults for SUPPORTS relationship."""
        edge = SemanticEdgeCreate(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPPORTS,
            properties={},
        )

        assert edge.properties["evidence_type"] == EvidenceType.THEORETICAL.value

    def test_semantic_edge_create_validator_preserves_existing(self):
        """Validator preserves existing values."""
        edge = SemanticEdgeCreate(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.CONTRADICTS,
            properties={
                "severity": ContradictionSeverity.HIGH.value,
                "resolution_status": ContradictionStatus.RESOLVED.value,
            },
        )

        assert edge.properties["severity"] == ContradictionSeverity.HIGH.value
        assert edge.properties["resolution_status"] == ContradictionStatus.RESOLVED.value


# =============================================================================
# SemanticEdge Tests
# =============================================================================


class TestSemanticEdge:
    """Tests for SemanticEdge model."""

    def test_valid_semantic_edge(self):
        """Valid SemanticEdge data creates model."""
        edge = SemanticEdge(
            source_id="source123",
            target_id="target456",
            relationship_type=SemanticRelationType.SUPPORTS,
            created_by="user789",
        )

        assert edge.source_id == "source123"
        assert edge.created_by == "user789"
        assert edge.id is not None  # auto-generated

    def test_semantic_edge_defaults(self):
        """SemanticEdge has sensible defaults."""
        edge = SemanticEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.RELATED_TO,
            created_by="user1",
        )

        assert edge.properties == {}
        assert edge.created_at is not None
        assert edge.updated_at is not None

    def test_semantic_edge_bidirectional_computed_true(self):
        """Bidirectional is computed for bidirectional relationships."""
        edge = SemanticEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.RELATED_TO,
            created_by="user1",
        )

        assert edge.bidirectional is True

        edge2 = SemanticEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.CONTRADICTS,
            created_by="user1",
        )

        assert edge2.bidirectional is True

    def test_semantic_edge_bidirectional_computed_false(self):
        """Bidirectional is computed for directed relationships."""
        edge = SemanticEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPPORTS,
            created_by="user1",
        )

        assert edge.bidirectional is False


# =============================================================================
# SemanticEdgeWithNodes Tests
# =============================================================================


class TestSemanticEdgeWithNodes:
    """Tests for SemanticEdgeWithNodes model."""

    def test_valid_semantic_edge_with_nodes(self):
        """Valid SemanticEdgeWithNodes data creates model."""
        edge = SemanticEdgeWithNodes(
            source_id="source123",
            target_id="target456",
            relationship_type=SemanticRelationType.ELABORATES,
            created_by="user789",
            source_title="Source Capsule",
            source_type="INSIGHT",
            target_title="Target Capsule",
            target_type="KNOWLEDGE",
        )

        assert edge.source_title == "Source Capsule"
        assert edge.source_type == "INSIGHT"
        assert edge.target_title == "Target Capsule"
        assert edge.target_type == "KNOWLEDGE"

    def test_semantic_edge_with_nodes_defaults(self):
        """SemanticEdgeWithNodes has sensible defaults."""
        edge = SemanticEdgeWithNodes(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.REFERENCES,
            created_by="user1",
        )

        assert edge.source_title is None
        assert edge.source_type is None
        assert edge.target_title is None
        assert edge.target_type is None


# =============================================================================
# ContradictionEdge Tests
# =============================================================================


class TestContradictionEdge:
    """Tests for ContradictionEdge model."""

    def test_contradiction_edge_properties(self):
        """ContradictionEdge exposes properties correctly."""
        edge = ContradictionEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.CONTRADICTS,
            created_by="user1",
            properties={
                "severity": ContradictionSeverity.HIGH.value,
                "resolution_status": ContradictionStatus.UNDER_REVIEW.value,
                "resolution_notes": "Being reviewed by team",
            },
        )

        assert edge.severity == ContradictionSeverity.HIGH
        assert edge.resolution_status == ContradictionStatus.UNDER_REVIEW
        assert edge.resolution_notes == "Being reviewed by team"

    def test_contradiction_edge_default_properties(self):
        """ContradictionEdge returns defaults when properties missing."""
        edge = ContradictionEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.CONTRADICTS,
            created_by="user1",
            properties={},
        )

        assert edge.severity == ContradictionSeverity.MEDIUM
        assert edge.resolution_status == ContradictionStatus.UNRESOLVED
        assert edge.resolution_notes is None


# =============================================================================
# SupportEdge Tests
# =============================================================================


class TestSupportEdge:
    """Tests for SupportEdge model."""

    def test_support_edge_properties(self):
        """SupportEdge exposes properties correctly."""
        edge = SupportEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPPORTS,
            created_by="user1",
            confidence=0.9,
            properties={
                "evidence_type": EvidenceType.EMPIRICAL.value,
                "evidence_reference": "https://example.com/paper",
                "strength": 0.95,
            },
        )

        assert edge.evidence_type == EvidenceType.EMPIRICAL
        assert edge.evidence_reference == "https://example.com/paper"
        assert edge.strength == 0.95

    def test_support_edge_default_properties(self):
        """SupportEdge returns defaults when properties missing."""
        edge = SupportEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPPORTS,
            created_by="user1",
            confidence=0.8,
            properties={},
        )

        assert edge.evidence_type == EvidenceType.THEORETICAL
        assert edge.evidence_reference is None
        assert edge.strength == 0.8  # Falls back to confidence


# =============================================================================
# SupersedesEdge Tests
# =============================================================================


class TestSupersedesEdge:
    """Tests for SupersedesEdge model."""

    def test_supersedes_edge_properties(self):
        """SupersedesEdge exposes properties correctly."""
        deprecated_time = datetime.now(UTC).isoformat()
        edge = SupersedesEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPERSEDES,
            created_by="user1",
            properties={
                "deprecated_at": deprecated_time,
                "deprecation_reason": "Outdated information",
                "migration_notes": "Use the new version",
            },
        )

        assert edge.deprecated_at is not None
        assert edge.deprecation_reason == "Outdated information"
        assert edge.migration_notes == "Use the new version"

    def test_supersedes_edge_default_properties(self):
        """SupersedesEdge returns defaults when properties missing."""
        edge = SupersedesEdge(
            source_id="s1",
            target_id="t1",
            relationship_type=SemanticRelationType.SUPERSEDES,
            created_by="user1",
            properties={},
        )

        assert edge.deprecated_at is None
        assert edge.deprecation_reason is None
        assert edge.migration_notes is None


# =============================================================================
# SemanticNeighbor Tests
# =============================================================================


class TestSemanticNeighbor:
    """Tests for SemanticNeighbor model."""

    def test_valid_semantic_neighbor(self):
        """Valid SemanticNeighbor data creates model."""
        neighbor = SemanticNeighbor(
            capsule_id="capsule123",
            title="Related Capsule",
            capsule_type="INSIGHT",
            trust_level=80,
            relationship_type=SemanticRelationType.SUPPORTS,
            direction="outgoing",
            confidence=0.85,
            edge_id="edge456",
        )

        assert neighbor.capsule_id == "capsule123"
        assert neighbor.direction == "outgoing"
        assert neighbor.confidence == 0.85

    def test_semantic_neighbor_defaults(self):
        """SemanticNeighbor has sensible defaults."""
        neighbor = SemanticNeighbor(
            capsule_id="c1",
            relationship_type=SemanticRelationType.RELATED_TO,
            direction="both",
            confidence=0.5,
            edge_id="e1",
        )

        assert neighbor.title is None
        assert neighbor.capsule_type is None
        assert neighbor.trust_level is None

    def test_semantic_neighbor_confidence_bounds(self):
        """confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            SemanticNeighbor(
                capsule_id="c1",
                relationship_type=SemanticRelationType.RELATED_TO,
                direction="incoming",
                confidence=1.5,
                edge_id="e1",
            )


# =============================================================================
# SemanticDistance Tests
# =============================================================================


class TestSemanticDistance:
    """Tests for SemanticDistance model."""

    def test_valid_semantic_distance(self):
        """Valid SemanticDistance data creates model."""
        distance = SemanticDistance(
            source_id="source123",
            target_id="target456",
            distance=2.5,
            path=["source123", "mid789", "target456"],
            relationship_types=[SemanticRelationType.SUPPORTS, SemanticRelationType.ELABORATES],
            avg_confidence=0.85,
        )

        assert distance.source_id == "source123"
        assert distance.distance == 2.5
        assert len(distance.path) == 3

    def test_semantic_distance_defaults(self):
        """SemanticDistance has sensible defaults."""
        distance = SemanticDistance(
            source_id="s1",
            target_id="t1",
            distance=1.0,
            avg_confidence=0.9,
        )

        assert distance.path == []
        assert distance.relationship_types == []

    def test_semantic_distance_bounds(self):
        """distance and avg_confidence have proper bounds."""
        with pytest.raises(ValidationError):
            SemanticDistance(
                source_id="s1",
                target_id="t1",
                distance=-0.5,
                avg_confidence=0.9,
            )

        with pytest.raises(ValidationError):
            SemanticDistance(
                source_id="s1",
                target_id="t1",
                distance=1.0,
                avg_confidence=1.5,
            )


# =============================================================================
# ContradictionCluster Tests
# =============================================================================


class TestContradictionCluster:
    """Tests for ContradictionCluster model."""

    def test_valid_contradiction_cluster(self):
        """Valid ContradictionCluster data creates model."""
        cluster = ContradictionCluster(
            capsule_ids=["c1", "c2", "c3"],
            overall_severity=ContradictionSeverity.HIGH,
            resolution_status=ContradictionStatus.UNDER_REVIEW,
        )

        assert len(cluster.capsule_ids) == 3
        assert cluster.overall_severity == ContradictionSeverity.HIGH
        assert cluster.size == 3

    def test_contradiction_cluster_defaults(self):
        """ContradictionCluster has sensible defaults."""
        cluster = ContradictionCluster()

        assert cluster.cluster_id is not None  # auto-generated
        assert cluster.capsule_ids == []
        assert cluster.edges == []
        assert cluster.overall_severity == ContradictionSeverity.MEDIUM
        assert cluster.resolution_status == ContradictionStatus.UNRESOLVED
        assert cluster.detected_at is not None
        assert cluster.size == 0

    def test_contradiction_cluster_size_property(self):
        """size property returns correct count."""
        cluster = ContradictionCluster(capsule_ids=["c1", "c2", "c3", "c4", "c5"])
        assert cluster.size == 5


# =============================================================================
# RelationshipClassification Tests
# =============================================================================


class TestRelationshipClassification:
    """Tests for RelationshipClassification model."""

    def test_valid_relationship_classification(self):
        """Valid RelationshipClassification data creates model."""
        classification = RelationshipClassification(
            source_id="source123",
            target_id="target456",
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.92,
            reasoning="Strong semantic similarity and supporting evidence found.",
            evidence_snippets=["Evidence snippet 1", "Evidence snippet 2"],
            should_create=True,
        )

        assert classification.relationship_type == SemanticRelationType.SUPPORTS.value
        assert classification.confidence == 0.92
        assert classification.should_create is True

    def test_relationship_classification_defaults(self):
        """RelationshipClassification has sensible defaults."""
        classification = RelationshipClassification(
            source_id="s1",
            target_id="t1",
            confidence=0.6,
            reasoning="Low confidence classification",
        )

        assert classification.relationship_type is None
        assert classification.evidence_snippets == []
        assert classification.should_create is False

    def test_relationship_classification_confidence_bounds(self):
        """confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            RelationshipClassification(
                source_id="s1",
                target_id="t1",
                confidence=1.5,
                reasoning="Test",
            )


# =============================================================================
# SemanticAnalysisRequest Tests
# =============================================================================


class TestSemanticAnalysisRequest:
    """Tests for SemanticAnalysisRequest model."""

    def test_valid_semantic_analysis_request(self):
        """Valid SemanticAnalysisRequest data creates model."""
        request = SemanticAnalysisRequest(
            capsule_id="capsule123",
            content="This is the capsule content to analyze.",
            max_candidates=30,
            min_confidence=0.8,
        )

        assert request.capsule_id == "capsule123"
        assert request.max_candidates == 30
        assert request.min_confidence == 0.8

    def test_semantic_analysis_request_defaults(self):
        """SemanticAnalysisRequest has sensible defaults."""
        request = SemanticAnalysisRequest(
            capsule_id="c1",
            content="Content",
        )

        assert request.embedding is None
        assert request.max_candidates == 20
        assert request.min_confidence == 0.7
        assert request.relationship_types is None

    def test_semantic_analysis_request_with_embedding(self):
        """SemanticAnalysisRequest with embedding."""
        embedding = [0.1] * 1536
        request = SemanticAnalysisRequest(
            capsule_id="c1",
            content="Content",
            embedding=embedding,
        )

        assert request.embedding is not None
        assert len(request.embedding) == 1536

    def test_semantic_analysis_request_bounds(self):
        """SemanticAnalysisRequest fields have proper bounds."""
        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(
                capsule_id="c1",
                content="Content",
                max_candidates=0,
            )

        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(
                capsule_id="c1",
                content="Content",
                max_candidates=101,
            )

        with pytest.raises(ValidationError):
            SemanticAnalysisRequest(
                capsule_id="c1",
                content="Content",
                min_confidence=-0.1,
            )


# =============================================================================
# SemanticAnalysisResult Tests
# =============================================================================


class TestSemanticAnalysisResult:
    """Tests for SemanticAnalysisResult model."""

    def test_valid_semantic_analysis_result(self):
        """Valid SemanticAnalysisResult data creates model."""
        result = SemanticAnalysisResult(
            capsule_id="capsule123",
            candidates_analyzed=25,
            analysis_time_ms=150.5,
            model_used="gpt-4",
        )

        assert result.capsule_id == "capsule123"
        assert result.candidates_analyzed == 25
        assert result.model_used == "gpt-4"

    def test_semantic_analysis_result_defaults(self):
        """SemanticAnalysisResult has sensible defaults."""
        result = SemanticAnalysisResult(
            capsule_id="c1",
            candidates_analyzed=10,
            analysis_time_ms=50.0,
        )

        assert result.classifications == []
        assert result.edges_created == []
        assert result.model_used is None


# =============================================================================
# SemanticEdgeQuery Tests
# =============================================================================


class TestSemanticEdgeQuery:
    """Tests for SemanticEdgeQuery model."""

    def test_valid_semantic_edge_query(self):
        """Valid SemanticEdgeQuery data creates model."""
        query = SemanticEdgeQuery(
            capsule_id="capsule123",
            relationship_types=[SemanticRelationType.SUPPORTS, SemanticRelationType.CONTRADICTS],
            direction="out",
            min_confidence=0.7,
        )

        assert query.capsule_id == "capsule123"
        assert query.direction == "out"
        assert query.min_confidence == 0.7

    def test_semantic_edge_query_defaults(self):
        """SemanticEdgeQuery has sensible defaults."""
        query = SemanticEdgeQuery()

        assert query.capsule_id is None
        assert query.relationship_types is None
        assert query.direction == "both"
        assert query.min_confidence == 0.0
        assert query.include_auto_detected is True
        assert query.created_by is None
        assert query.created_after is None
        assert query.created_before is None
        assert query.limit == 100
        assert query.offset == 0

    def test_semantic_edge_query_direction_pattern(self):
        """direction must match pattern (in|out|both)."""
        # Valid directions
        SemanticEdgeQuery(direction="in")
        SemanticEdgeQuery(direction="out")
        SemanticEdgeQuery(direction="both")

        # Invalid direction
        with pytest.raises(ValidationError):
            SemanticEdgeQuery(direction="invalid")

    def test_semantic_edge_query_limit_bounds(self):
        """limit must be between 1 and 100."""
        with pytest.raises(ValidationError):
            SemanticEdgeQuery(limit=0)

        with pytest.raises(ValidationError):
            SemanticEdgeQuery(limit=101)


# =============================================================================
# ContradictionQuery Tests
# =============================================================================


class TestContradictionQuery:
    """Tests for ContradictionQuery model."""

    def test_valid_contradiction_query(self):
        """Valid ContradictionQuery data creates model."""
        query = ContradictionQuery(
            capsule_id="capsule123",
            tags=["machine-learning", "nlp"],
            min_severity=ContradictionSeverity.HIGH,
            resolution_status=ContradictionStatus.UNRESOLVED,
        )

        assert query.capsule_id == "capsule123"
        assert query.min_severity == ContradictionSeverity.HIGH
        assert "machine-learning" in query.tags

    def test_contradiction_query_defaults(self):
        """ContradictionQuery has sensible defaults."""
        query = ContradictionQuery()

        assert query.capsule_id is None
        assert query.tags is None
        assert query.min_severity == ContradictionSeverity.LOW
        assert query.resolution_status is None
        assert query.include_resolved is False
        assert query.limit == 50

    def test_contradiction_query_limit_bounds(self):
        """limit must be between 1 and 500."""
        with pytest.raises(ValidationError):
            ContradictionQuery(limit=0)

        with pytest.raises(ValidationError):
            ContradictionQuery(limit=501)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
