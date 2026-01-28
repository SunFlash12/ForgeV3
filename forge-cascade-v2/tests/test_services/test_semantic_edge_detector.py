"""
Tests for Semantic Edge Detector Service

Tests automatic detection and creation of semantic relationships between capsules
using embedding similarity and LLM-based classification.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.semantic_edges import SemanticEdge, SemanticRelationType
from forge.services.semantic_edge_detector import (
    DetectionConfig,
    DetectionResult,
    RelationshipClassification,
    SemanticEdgeDetector,
    create_semantic_edge_detector,
    get_semantic_edge_detector,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_capsule():
    """Create a mock capsule for testing."""
    capsule = MagicMock()
    capsule.id = "capsule-123"
    capsule.title = "Test Capsule"
    capsule.content = "This is test content for semantic analysis."
    capsule.type = MagicMock()
    capsule.type.value = "knowledge"
    capsule.embedding = None
    return capsule


@pytest.fixture
def mock_target_capsule():
    """Create a mock target capsule for testing."""
    capsule = MagicMock()
    capsule.id = "capsule-456"
    capsule.title = "Target Capsule"
    capsule.content = "This is related content that might have a relationship."
    capsule.type = MagicMock()
    capsule.type.value = "knowledge"
    return capsule


@pytest.fixture
def mock_capsule_repo():
    """Create a mock capsule repository."""
    repo = AsyncMock()
    repo.find_similar_by_embedding = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create_semantic_edge = AsyncMock()
    return repo


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    embedding_result = MagicMock()
    embedding_result.embedding = [0.1] * 384  # Mock embedding vector
    service.embed = AsyncMock(return_value=embedding_result)
    return service


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    service = AsyncMock()
    response = MagicMock()
    response.content = json.dumps({
        "relationship_type": "SUPPORTS",
        "confidence": 0.85,
        "reasoning": "Source provides evidence for target claims",
        "bidirectional": False,
    })
    service.complete = AsyncMock(return_value=response)
    return service


@pytest.fixture
def detection_config():
    """Create a test detection config."""
    return DetectionConfig(
        similarity_threshold=0.7,
        confidence_threshold=0.7,
        max_candidates=10,
        enabled=True,
        enabled_types={
            SemanticRelationType.SUPPORTS,
            SemanticRelationType.CONTRADICTS,
            SemanticRelationType.ELABORATES,
            SemanticRelationType.REFERENCES,
            SemanticRelationType.RELATED_TO,
        },
    )


@pytest.fixture
def semantic_edge_detector(mock_capsule_repo, mock_embedding_service, detection_config):
    """Create a semantic edge detector for testing."""
    detector = SemanticEdgeDetector(
        capsule_repo=mock_capsule_repo,
        embedding_service=mock_embedding_service,
        config=detection_config,
    )
    return detector


# =============================================================================
# Test DetectionConfig
# =============================================================================


class TestDetectionConfig:
    """Tests for DetectionConfig dataclass."""

    def test_default_config(self):
        """Test default config values."""
        config = DetectionConfig()

        assert config.similarity_threshold == 0.7
        assert config.confidence_threshold == 0.7
        assert config.max_candidates == 20
        assert config.enabled is True
        assert SemanticRelationType.SUPPORTS in config.enabled_types
        assert SemanticRelationType.CONTRADICTS in config.enabled_types

    def test_custom_config(self):
        """Test custom config values."""
        config = DetectionConfig(
            similarity_threshold=0.8,
            confidence_threshold=0.9,
            max_candidates=5,
            enabled=False,
            enabled_types={SemanticRelationType.SUPPORTS},
        )

        assert config.similarity_threshold == 0.8
        assert config.confidence_threshold == 0.9
        assert config.max_candidates == 5
        assert config.enabled is False
        assert len(config.enabled_types) == 1


# =============================================================================
# Test RelationshipClassification
# =============================================================================


class TestRelationshipClassification:
    """Tests for RelationshipClassification dataclass."""

    def test_classification_with_relationship(self):
        """Test classification with a detected relationship."""
        classification = RelationshipClassification(
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.85,
            reasoning="Source supports target",
            bidirectional=False,
        )

        assert classification.relationship_type == SemanticRelationType.SUPPORTS
        assert classification.confidence == 0.85
        assert classification.reasoning == "Source supports target"
        assert classification.bidirectional is False

    def test_classification_no_relationship(self):
        """Test classification with no relationship."""
        classification = RelationshipClassification(
            relationship_type=None,
            confidence=0.0,
            reasoning="No relationship detected",
        )

        assert classification.relationship_type is None
        assert classification.confidence == 0.0


# =============================================================================
# Test DetectionResult
# =============================================================================


class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_empty_result(self):
        """Test empty detection result."""
        result = DetectionResult(
            capsule_id="test-123",
            candidates_analyzed=0,
            edges_created=0,
            edges=[],
        )

        assert result.capsule_id == "test-123"
        assert result.candidates_analyzed == 0
        assert result.edges_created == 0
        assert len(result.edges) == 0
        assert len(result.errors) == 0

    def test_result_with_edges_and_errors(self):
        """Test detection result with edges and errors."""
        mock_edge = MagicMock(spec=SemanticEdge)

        result = DetectionResult(
            capsule_id="test-456",
            candidates_analyzed=5,
            edges_created=2,
            edges=[mock_edge, mock_edge],
            errors=["Failed to process capsule-789"],
            duration_ms=150.5,
        )

        assert result.candidates_analyzed == 5
        assert result.edges_created == 2
        assert len(result.edges) == 2
        assert len(result.errors) == 1
        assert result.duration_ms == 150.5


# =============================================================================
# Test SemanticEdgeDetector Initialization
# =============================================================================


class TestSemanticEdgeDetectorInit:
    """Tests for SemanticEdgeDetector initialization."""

    def test_init_with_defaults(self, mock_capsule_repo):
        """Test initialization with default values."""
        with patch("forge.services.semantic_edge_detector.get_embedding_service") as mock_get_embed:
            mock_get_embed.return_value = MagicMock()
            detector = SemanticEdgeDetector(capsule_repo=mock_capsule_repo)

            assert detector.capsule_repo is mock_capsule_repo
            assert detector.config is not None
            assert detector.config.enabled is True

    def test_init_with_custom_config(self, mock_capsule_repo, mock_embedding_service, detection_config):
        """Test initialization with custom config."""
        detector = SemanticEdgeDetector(
            capsule_repo=mock_capsule_repo,
            embedding_service=mock_embedding_service,
            config=detection_config,
        )

        assert detector.embedding_service is mock_embedding_service
        assert detector.config.max_candidates == 10

    def test_lazy_llm_loading(self, semantic_edge_detector):
        """Test lazy loading of LLM service."""
        assert semantic_edge_detector._llm is None

        with patch("forge.services.semantic_edge_detector.get_llm_service") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            # Access the property to trigger lazy loading
            llm = semantic_edge_detector.llm

            assert llm is mock_llm
            mock_get_llm.assert_called_once()


# =============================================================================
# Test analyze_capsule
# =============================================================================


class TestAnalyzeCapsule:
    """Tests for analyze_capsule method."""

    @pytest.mark.asyncio
    async def test_analyze_disabled(self, semantic_edge_detector, mock_capsule):
        """Test analysis returns empty result when disabled."""
        semantic_edge_detector.config.enabled = False

        result = await semantic_edge_detector.analyze_capsule(
            capsule=mock_capsule,
            created_by="user-123",
        )

        assert result.capsule_id == mock_capsule.id
        assert result.candidates_analyzed == 0
        assert result.edges_created == 0

    @pytest.mark.asyncio
    async def test_analyze_no_candidates(
        self, semantic_edge_detector, mock_capsule, mock_capsule_repo
    ):
        """Test analysis with no similar capsules found."""
        mock_capsule_repo.find_similar_by_embedding.return_value = []

        result = await semantic_edge_detector.analyze_capsule(
            capsule=mock_capsule,
            created_by="user-123",
        )

        assert result.candidates_analyzed == 0
        assert result.edges_created == 0

    @pytest.mark.asyncio
    async def test_analyze_with_candidates(
        self,
        semantic_edge_detector,
        mock_capsule,
        mock_target_capsule,
        mock_capsule_repo,
        mock_llm_service,
    ):
        """Test analysis with candidates found."""
        # Setup mock to return similar capsules
        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_target_capsule, 0.85),
        ]

        # Setup mock edge creation
        mock_edge = MagicMock(spec=SemanticEdge)
        mock_edge.id = "edge-123"
        mock_capsule_repo.create_semantic_edge.return_value = mock_edge

        # Inject mock LLM
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            result = await semantic_edge_detector.analyze_capsule(
                capsule=mock_capsule,
                created_by="user-123",
            )

        assert result.candidates_analyzed == 1
        assert result.edges_created == 1
        assert len(result.edges) == 1

    @pytest.mark.asyncio
    async def test_analyze_generates_embedding_if_missing(
        self, semantic_edge_detector, mock_capsule, mock_embedding_service, mock_capsule_repo
    ):
        """Test that embedding is generated if capsule has no embedding."""
        mock_capsule.embedding = None
        mock_capsule_repo.find_similar_by_embedding.return_value = []

        await semantic_edge_detector.analyze_capsule(
            capsule=mock_capsule,
            created_by="user-123",
        )

        # Should have called embed to generate embedding
        mock_embedding_service.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_uses_existing_embedding(
        self, semantic_edge_detector, mock_capsule, mock_embedding_service, mock_capsule_repo
    ):
        """Test that existing embedding is used if present."""
        mock_capsule.embedding = [0.5] * 384
        mock_capsule_repo.find_similar_by_embedding.return_value = []

        await semantic_edge_detector.analyze_capsule(
            capsule=mock_capsule,
            created_by="user-123",
        )

        # Should NOT have called embed since embedding exists
        mock_embedding_service.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_analyze_filters_self(
        self, semantic_edge_detector, mock_capsule, mock_capsule_repo
    ):
        """Test that the source capsule is filtered from candidates."""
        # Return the same capsule as a candidate (simulating self-match)
        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_capsule, 1.0),  # Self-match with perfect similarity
        ]

        result = await semantic_edge_detector.analyze_capsule(
            capsule=mock_capsule,
            created_by="user-123",
        )

        # Self should be filtered out
        assert result.candidates_analyzed == 0

    @pytest.mark.asyncio
    async def test_analyze_handles_classification_error(
        self,
        semantic_edge_detector,
        mock_capsule,
        mock_target_capsule,
        mock_capsule_repo,
        mock_llm_service,
    ):
        """Test that classification errors are handled gracefully."""
        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_target_capsule, 0.85),
        ]

        # Make LLM raise an error
        mock_llm_service.complete.side_effect = RuntimeError("LLM error")
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            result = await semantic_edge_detector.analyze_capsule(
                capsule=mock_capsule,
                created_by="user-123",
            )

        assert result.candidates_analyzed == 1
        assert result.edges_created == 0
        assert len(result.errors) == 1


# =============================================================================
# Test _find_similar_capsules
# =============================================================================


class TestFindSimilarCapsules:
    """Tests for _find_similar_capsules method."""

    @pytest.mark.asyncio
    async def test_find_similar_with_embedding(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_capsule_repo
    ):
        """Test finding similar capsules with existing embedding."""
        mock_capsule.embedding = [0.5] * 384
        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_target_capsule, 0.9),
        ]

        results = await semantic_edge_detector._find_similar_capsules(mock_capsule)

        assert len(results) == 1
        assert results[0][0] == mock_target_capsule
        assert results[0][1] == 0.9

        mock_capsule_repo.find_similar_by_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_similar_limits_results(
        self, semantic_edge_detector, mock_capsule, mock_capsule_repo
    ):
        """Test that results are limited to max_candidates."""
        semantic_edge_detector.config.max_candidates = 2

        # Create many mock capsules
        mock_capsules = []
        for i in range(5):
            c = MagicMock()
            c.id = f"capsule-{i}"
            mock_capsules.append((c, 0.9 - i * 0.01))

        mock_capsule_repo.find_similar_by_embedding.return_value = mock_capsules
        mock_capsule.embedding = [0.5] * 384

        results = await semantic_edge_detector._find_similar_capsules(mock_capsule)

        # Should be limited to max_candidates
        assert len(results) <= 2


# =============================================================================
# Test _classify_relationship
# =============================================================================


class TestClassifyRelationship:
    """Tests for _classify_relationship method."""

    @pytest.mark.asyncio
    async def test_classify_supports_relationship(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_llm_service
    ):
        """Test classification of SUPPORTS relationship."""
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            classification = await semantic_edge_detector._classify_relationship(
                source=mock_capsule,
                target=mock_target_capsule,
            )

        assert classification.relationship_type == SemanticRelationType.SUPPORTS
        assert classification.confidence == 0.85
        assert classification.bidirectional is False

    @pytest.mark.asyncio
    async def test_classify_no_relationship(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_llm_service
    ):
        """Test classification when no relationship exists."""
        # Configure LLM to return NONE
        response = MagicMock()
        response.content = json.dumps({
            "relationship_type": "NONE",
            "confidence": 0.1,
            "reasoning": "No meaningful relationship",
            "bidirectional": False,
        })
        mock_llm_service.complete.return_value = response
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            classification = await semantic_edge_detector._classify_relationship(
                source=mock_capsule,
                target=mock_target_capsule,
            )

        assert classification.relationship_type is None
        assert classification.confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_handles_markdown_wrapped_json(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_llm_service
    ):
        """Test classification handles markdown-wrapped JSON response."""
        # Configure LLM to return JSON wrapped in markdown
        response = MagicMock()
        response.content = """```json
{
    "relationship_type": "ELABORATES",
    "confidence": 0.75,
    "reasoning": "Source elaborates on target",
    "bidirectional": false
}
```"""
        mock_llm_service.complete.return_value = response
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            classification = await semantic_edge_detector._classify_relationship(
                source=mock_capsule,
                target=mock_target_capsule,
            )

        assert classification.relationship_type == SemanticRelationType.ELABORATES
        assert classification.confidence == 0.75

    @pytest.mark.asyncio
    async def test_classify_handles_invalid_json(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_llm_service
    ):
        """Test classification handles invalid JSON gracefully."""
        response = MagicMock()
        response.content = "Invalid JSON response"
        mock_llm_service.complete.return_value = response
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            classification = await semantic_edge_detector._classify_relationship(
                source=mock_capsule,
                target=mock_target_capsule,
            )

        assert classification.relationship_type is None
        assert classification.confidence == 0.0
        assert "Parse error" in classification.reasoning


# =============================================================================
# Test _create_edge
# =============================================================================


class TestCreateEdge:
    """Tests for _create_edge method."""

    @pytest.mark.asyncio
    async def test_create_edge_success(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_capsule_repo
    ):
        """Test successful edge creation."""
        classification = RelationshipClassification(
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.85,
            reasoning="Source supports target",
            bidirectional=False,
        )

        mock_edge = MagicMock(spec=SemanticEdge)
        mock_edge.id = "edge-123"
        mock_capsule_repo.create_semantic_edge.return_value = mock_edge

        edge = await semantic_edge_detector._create_edge(
            source=mock_capsule,
            target=mock_target_capsule,
            classification=classification,
            similarity=0.85,
            created_by="user-123",
        )

        assert edge is mock_edge
        mock_capsule_repo.create_semantic_edge.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_edge_no_relationship_type(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_capsule_repo
    ):
        """Test edge creation returns None when no relationship type."""
        classification = RelationshipClassification(
            relationship_type=None,
            confidence=0.0,
            reasoning="No relationship",
        )

        edge = await semantic_edge_detector._create_edge(
            source=mock_capsule,
            target=mock_target_capsule,
            classification=classification,
            similarity=0.5,
            created_by="user-123",
        )

        assert edge is None
        mock_capsule_repo.create_semantic_edge.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_edge_handles_error(
        self, semantic_edge_detector, mock_capsule, mock_target_capsule, mock_capsule_repo
    ):
        """Test edge creation handles errors gracefully."""
        classification = RelationshipClassification(
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.85,
            reasoning="Source supports target",
        )

        mock_capsule_repo.create_semantic_edge.side_effect = RuntimeError("DB error")

        edge = await semantic_edge_detector._create_edge(
            source=mock_capsule,
            target=mock_target_capsule,
            classification=classification,
            similarity=0.85,
            created_by="user-123",
        )

        assert edge is None


# =============================================================================
# Test batch_analyze
# =============================================================================


class TestBatchAnalyze:
    """Tests for batch_analyze method."""

    @pytest.mark.asyncio
    async def test_batch_analyze_multiple_capsules(
        self, semantic_edge_detector, mock_capsule, mock_capsule_repo
    ):
        """Test batch analysis of multiple capsules."""
        # Setup mock to return the capsule for each ID
        mock_capsule_repo.get_by_id.return_value = mock_capsule
        mock_capsule_repo.find_similar_by_embedding.return_value = []

        results = await semantic_edge_detector.batch_analyze(
            capsule_ids=["capsule-1", "capsule-2", "capsule-3"],
            created_by="user-123",
        )

        assert len(results) == 3
        assert all(isinstance(r, DetectionResult) for r in results)

    @pytest.mark.asyncio
    async def test_batch_analyze_handles_missing_capsules(
        self, semantic_edge_detector, mock_capsule_repo
    ):
        """Test batch analysis handles missing capsules."""
        mock_capsule_repo.get_by_id.return_value = None

        results = await semantic_edge_detector.batch_analyze(
            capsule_ids=["missing-1", "missing-2"],
            created_by="user-123",
        )

        assert len(results) == 2
        for result in results:
            assert len(result.errors) == 1
            assert "not found" in result.errors[0]


# =============================================================================
# Test Factory Functions
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_semantic_edge_detector(self, mock_capsule_repo, detection_config):
        """Test create_semantic_edge_detector factory."""
        with patch("forge.services.semantic_edge_detector.get_embedding_service") as mock_get_embed:
            mock_get_embed.return_value = MagicMock()

            detector = create_semantic_edge_detector(
                capsule_repo=mock_capsule_repo,
                config=detection_config,
            )

            assert isinstance(detector, SemanticEdgeDetector)
            assert detector.config.max_candidates == 10

    def test_get_semantic_edge_detector_creates_singleton(self, mock_capsule_repo):
        """Test get_semantic_edge_detector creates singleton."""
        import forge.services.semantic_edge_detector as detector_module

        # Reset global detector
        detector_module._detector = None

        with patch("forge.services.semantic_edge_detector.get_embedding_service") as mock_get_embed:
            mock_get_embed.return_value = MagicMock()

            detector1 = get_semantic_edge_detector(mock_capsule_repo)
            detector2 = get_semantic_edge_detector(mock_capsule_repo)

            assert detector1 is detector2

            # Cleanup
            detector_module._detector = None


# =============================================================================
# Test Confidence Threshold Filtering
# =============================================================================


class TestConfidenceThreshold:
    """Tests for confidence threshold filtering."""

    @pytest.mark.asyncio
    async def test_low_confidence_not_created(
        self,
        semantic_edge_detector,
        mock_capsule,
        mock_target_capsule,
        mock_capsule_repo,
        mock_llm_service,
    ):
        """Test that edges with low confidence are not created."""
        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_target_capsule, 0.85),
        ]

        # Configure LLM to return low confidence
        response = MagicMock()
        response.content = json.dumps({
            "relationship_type": "SUPPORTS",
            "confidence": 0.5,  # Below threshold
            "reasoning": "Weak relationship",
            "bidirectional": False,
        })
        mock_llm_service.complete.return_value = response
        semantic_edge_detector._llm = mock_llm_service

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            result = await semantic_edge_detector.analyze_capsule(
                capsule=mock_capsule,
                created_by="user-123",
            )

        assert result.candidates_analyzed == 1
        assert result.edges_created == 0
        mock_capsule_repo.create_semantic_edge.assert_not_called()


# =============================================================================
# Test Relationship Type Filtering
# =============================================================================


class TestRelationshipTypeFiltering:
    """Tests for relationship type filtering."""

    @pytest.mark.asyncio
    async def test_disabled_type_not_created(
        self,
        mock_capsule,
        mock_target_capsule,
        mock_capsule_repo,
        mock_embedding_service,
        mock_llm_service,
    ):
        """Test that disabled relationship types are not created."""
        # Configure to only allow SUPPORTS
        config = DetectionConfig(
            enabled_types={SemanticRelationType.SUPPORTS},
        )

        detector = SemanticEdgeDetector(
            capsule_repo=mock_capsule_repo,
            embedding_service=mock_embedding_service,
            config=config,
        )
        detector._llm = mock_llm_service

        mock_capsule_repo.find_similar_by_embedding.return_value = [
            (mock_target_capsule, 0.85),
        ]

        # Configure LLM to return CONTRADICTS (disabled)
        response = MagicMock()
        response.content = json.dumps({
            "relationship_type": "CONTRADICTS",
            "confidence": 0.9,
            "reasoning": "Source contradicts target",
            "bidirectional": True,
        })
        mock_llm_service.complete.return_value = response

        with patch("forge.services.semantic_edge_detector.sanitize_for_prompt", side_effect=lambda x, **kwargs: x):
            result = await detector.analyze_capsule(
                capsule=mock_capsule,
                created_by="user-123",
            )

        assert result.candidates_analyzed == 1
        assert result.edges_created == 0
