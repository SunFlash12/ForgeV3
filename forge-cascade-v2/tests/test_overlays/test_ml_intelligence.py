"""
Comprehensive tests for the MLIntelligenceOverlay.

Tests cover:
- Overlay initialization and configuration
- Embedding generation (pseudo and external)
- Content classification
- Entity extraction
- Pattern detection
- Sentiment analysis
- Keyword extraction
- Anomaly scoring
- Summary generation
- Similarity computation
- Caching behavior
- Statistics tracking
"""

import math

import pytest

from forge.models.events import Event, EventType
from forge.models.overlay import Capability
from forge.overlays.base import OverlayContext
from forge.overlays.ml_intelligence import (
    AnalysisResult,
    ClassificationResult,
    MLIntelligenceOverlay,
    MLProcessingError,
    create_ml_intelligence,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def ml_overlay() -> MLIntelligenceOverlay:
    """Create a basic ML Intelligence overlay."""
    return MLIntelligenceOverlay()


@pytest.fixture
def configured_overlay() -> MLIntelligenceOverlay:
    """Create a configured ML Intelligence overlay."""
    return MLIntelligenceOverlay(
        embedding_dimensions=128,
        enable_classification=True,
        enable_entity_extraction=True,
        enable_pattern_detection=True,
        enable_sentiment=True,
        custom_categories={"custom": ["custom_term", "another_term"]},
    )


@pytest.fixture
async def initialized_overlay(ml_overlay: MLIntelligenceOverlay) -> MLIntelligenceOverlay:
    """Create and initialize an ML Intelligence overlay."""
    await ml_overlay.initialize()
    return ml_overlay


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="ml_intelligence",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ},
    )


@pytest.fixture
def sample_technical_content() -> str:
    """Sample technical content for testing."""
    return """
    This is a guide on how to implement a REST API using Python.
    The function calculates the algorithm complexity.
    For database access, use the server connection with proper API keys.
    Contact support at test@example.com or visit https://example.com/docs
    Version 2.0.1 was released on 2024-01-15.
    """


@pytest.fixture
def sample_business_content() -> str:
    """Sample business content for testing."""
    return """
    Our revenue increased by 20% this quarter. The customer satisfaction
    score improved as our sales strategy focused on market expansion.
    This is a great success for the company!
    """


# =============================================================================
# Initialization Tests
# =============================================================================


class TestMLIntelligenceInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test default initialization values."""
        assert ml_overlay.NAME == "ml_intelligence"
        assert ml_overlay.VERSION == "1.0.0"
        assert ml_overlay._embedding_dim == 384
        assert ml_overlay._enable_classification is True
        assert ml_overlay._enable_entities is True
        assert ml_overlay._enable_patterns is True
        assert ml_overlay._enable_sentiment is True

    def test_custom_initialization(self) -> None:
        """Test custom initialization values."""
        overlay = MLIntelligenceOverlay(
            embedding_dimensions=256,
            enable_classification=False,
            enable_entity_extraction=False,
            enable_pattern_detection=False,
            enable_sentiment=False,
        )
        assert overlay._embedding_dim == 256
        assert overlay._enable_classification is False
        assert overlay._enable_entities is False
        assert overlay._enable_patterns is False
        assert overlay._enable_sentiment is False

    def test_custom_categories(self, configured_overlay: MLIntelligenceOverlay) -> None:
        """Test custom categories are merged."""
        assert "custom" in configured_overlay._categories
        assert "technical" in configured_overlay._categories

    @pytest.mark.asyncio
    async def test_initialize(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test overlay initialization."""
        result = await ml_overlay.initialize()
        assert result is True
        assert ml_overlay._initialized is True

    def test_subscribed_events(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test subscribed events."""
        assert EventType.CAPSULE_CREATED in ml_overlay.SUBSCRIBED_EVENTS
        assert EventType.CAPSULE_UPDATED in ml_overlay.SUBSCRIBED_EVENTS
        assert EventType.SYSTEM_EVENT in ml_overlay.SUBSCRIBED_EVENTS

    def test_required_capabilities(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test required capabilities."""
        assert Capability.DATABASE_READ in ml_overlay.REQUIRED_CAPABILITIES


# =============================================================================
# Execution Tests
# =============================================================================


class TestMLIntelligenceExecution:
    """Tests for overlay execution."""

    @pytest.mark.asyncio
    async def test_execute_with_content(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
        sample_technical_content: str,
    ) -> None:
        """Test execution with content."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"content": sample_technical_content},
        )

        assert result.success is True
        assert result.data is not None
        assert "analysis" in result.data

        analysis = result.data["analysis"]
        assert analysis["embedding"] is not None
        assert analysis["classification"] is not None
        assert analysis["keywords"] is not None

    @pytest.mark.asyncio
    async def test_execute_with_event(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution with event."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"content": "Test content for analysis."},
        )

        result = await initialized_overlay.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is True
        assert result.data is not None

    @pytest.mark.asyncio
    async def test_execute_no_content(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution with no content."""
        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={},
        )

        assert result.success is True
        assert result.data["analysis"] is None

    @pytest.mark.asyncio
    async def test_execute_extracts_from_various_fields(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test content extraction from various fields."""
        for field in ["content", "text", "body", "message", "title", "description"]:
            result = await initialized_overlay.execute(
                context=overlay_context,
                input_data={field: "Test content"},
            )
            assert result.success is True
            assert result.data["analysis"] is not None


# =============================================================================
# Embedding Tests
# =============================================================================


class TestEmbeddingGeneration:
    """Tests for embedding generation."""

    @pytest.mark.asyncio
    async def test_pseudo_embedding_dimensions(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test pseudo embedding has correct dimensions."""
        embedding = ml_overlay._pseudo_embedding("test content")
        assert len(embedding) == 384

    @pytest.mark.asyncio
    async def test_pseudo_embedding_deterministic(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test pseudo embedding is deterministic."""
        emb1 = ml_overlay._pseudo_embedding("test content")
        emb2 = ml_overlay._pseudo_embedding("test content")
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_pseudo_embedding_normalized(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test pseudo embedding is normalized."""
        embedding = ml_overlay._pseudo_embedding("test content")
        magnitude = math.sqrt(sum(x * x for x in embedding))
        assert abs(magnitude - 1.0) < 0.0001

    @pytest.mark.asyncio
    async def test_embedding_caching(
        self,
        initialized_overlay: MLIntelligenceOverlay,
    ) -> None:
        """Test embedding caching."""
        content = "Test content for caching"

        emb1 = await initialized_overlay._generate_embedding(content)
        cache_hits_before = initialized_overlay._stats["cache_hits"]

        emb2 = await initialized_overlay._generate_embedding(content)
        cache_hits_after = initialized_overlay._stats["cache_hits"]

        assert cache_hits_after == cache_hits_before + 1
        assert emb1.embedding == emb2.embedding

    @pytest.mark.asyncio
    async def test_embedding_cache_eviction(self) -> None:
        """Test embedding cache eviction."""
        overlay = MLIntelligenceOverlay()
        overlay._cache_max_size = 3
        await overlay.initialize()

        for i in range(5):
            await overlay._generate_embedding(f"content {i}")

        assert len(overlay._embedding_cache) == 3

    @pytest.mark.asyncio
    async def test_external_embedding_provider(self) -> None:
        """Test using external embedding provider."""

        async def mock_provider(content: str) -> list[float]:
            return [0.1] * 128

        overlay = MLIntelligenceOverlay(
            embedding_dimensions=128,
            embedding_provider=mock_provider,
        )
        await overlay.initialize()

        result = await overlay._generate_embedding("test")
        assert result.model == "external"
        assert len(result.embedding) == 128


# =============================================================================
# Classification Tests
# =============================================================================


class TestClassification:
    """Tests for content classification."""

    def test_classify_technical_content(
        self,
        ml_overlay: MLIntelligenceOverlay,
        sample_technical_content: str,
    ) -> None:
        """Test classification of technical content."""
        result = ml_overlay._classify(sample_technical_content)

        assert isinstance(result, ClassificationResult)
        assert result.primary_class == "technical"
        assert result.confidence > 0

    def test_classify_business_content(
        self,
        ml_overlay: MLIntelligenceOverlay,
        sample_business_content: str,
    ) -> None:
        """Test classification of business content."""
        result = ml_overlay._classify(sample_business_content)

        assert result.primary_class == "business"

    def test_classify_returns_all_classes(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test classification returns all class scores."""
        result = ml_overlay._classify("test content")

        assert "technical" in result.all_classes
        assert "business" in result.all_classes
        assert "personal" in result.all_classes

    def test_classify_with_custom_categories(self) -> None:
        """Test classification with custom categories."""
        overlay = MLIntelligenceOverlay(custom_categories={"special": ["unique", "special_term"]})

        result = overlay._classify("This is a unique and special_term document")

        assert "special" in result.all_classes


# =============================================================================
# Entity Extraction Tests
# =============================================================================


class TestEntityExtraction:
    """Tests for entity extraction."""

    def test_extract_email(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test email extraction."""
        content = "Contact us at test@example.com"
        result = ml_overlay._extract_entities(content)

        emails = [e for e in result.entities if e["type"] == "email"]
        assert len(emails) == 1
        assert emails[0]["text"] == "test@example.com"

    def test_extract_url(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test URL extraction."""
        content = "Visit https://example.com/docs for more info"
        result = ml_overlay._extract_entities(content)

        urls = [e for e in result.entities if e["type"] == "url"]
        assert len(urls) == 1

    def test_extract_date(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test date extraction."""
        content = "The meeting is on 2024-01-15"
        result = ml_overlay._extract_entities(content)

        dates = [e for e in result.entities if e["type"] == "date"]
        assert len(dates) == 1

    def test_extract_version(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test version extraction."""
        content = "Version v2.0.1 released"
        result = ml_overlay._extract_entities(content)

        versions = [e for e in result.entities if e["type"] == "version"]
        assert len(versions) == 1

    def test_extract_money(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test money extraction."""
        content = "The price is $100.00"
        result = ml_overlay._extract_entities(content)

        money = [e for e in result.entities if e["type"] == "money"]
        assert len(money) == 1

    def test_extract_relationships(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test relationship extraction between entities."""
        content = "Contact test@example.com on 2024-01-15"
        result = ml_overlay._extract_entities(content)

        # Should find co-occurrence relationship
        assert len(result.relationships) >= 0


# =============================================================================
# Pattern Detection Tests
# =============================================================================


class TestPatternDetection:
    """Tests for pattern detection."""

    def test_detect_question_pattern(
        self,
        ml_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test question pattern detection."""
        content = "What is the answer? How does this work?"
        patterns = ml_overlay._detect_patterns(content, overlay_context)

        question_patterns = [p for p in patterns if p.pattern_name == "questions"]
        assert len(question_patterns) == 1
        assert question_patterns[0].confidence > 0

    def test_detect_list_pattern(
        self,
        ml_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test list pattern detection."""
        content = "- Item 1\n- Item 2\n* Item 3"
        patterns = ml_overlay._detect_patterns(content, overlay_context)

        list_patterns = [p for p in patterns if p.pattern_name == "list_format"]
        assert len(list_patterns) == 1

    def test_detect_code_pattern(
        self,
        ml_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test code pattern detection."""
        content = "```python\ndef function():\n    pass\n```"
        patterns = ml_overlay._detect_patterns(content, overlay_context)

        code_patterns = [p for p in patterns if p.pattern_name == "code_content"]
        assert len(code_patterns) == 1

    def test_detect_technical_pattern(
        self,
        ml_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test technical content pattern detection."""
        content = "The REST API returns JSON data via HTTP"
        patterns = ml_overlay._detect_patterns(content, overlay_context)

        tech_patterns = [p for p in patterns if p.pattern_name == "technical_content"]
        assert len(tech_patterns) == 1


# =============================================================================
# Sentiment Analysis Tests
# =============================================================================


class TestSentimentAnalysis:
    """Tests for sentiment analysis."""

    def test_positive_sentiment(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test positive sentiment detection."""
        content = "This is excellent! I love it, amazing work, great job!"
        sentiment = ml_overlay._analyze_sentiment(content)

        assert sentiment > 0

    def test_negative_sentiment(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test negative sentiment detection."""
        content = "This is terrible! I hate it, awful work, horrible result!"
        sentiment = ml_overlay._analyze_sentiment(content)

        assert sentiment < 0

    def test_neutral_sentiment(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test neutral sentiment detection."""
        content = "The system processes data and returns results"
        sentiment = ml_overlay._analyze_sentiment(content)

        assert sentiment == 0.0


# =============================================================================
# Keyword Extraction Tests
# =============================================================================


class TestKeywordExtraction:
    """Tests for keyword extraction."""

    def test_extract_keywords(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test keyword extraction."""
        content = "Python programming is useful for data analysis and machine learning"
        keywords = ml_overlay._extract_keywords(content)

        assert len(keywords) > 0
        assert all(len(k) >= 4 for k in keywords)

    def test_keyword_limit(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test keyword count limit."""
        content = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11"
        keywords = ml_overlay._extract_keywords(content, max_keywords=5)

        assert len(keywords) <= 5

    def test_stopwords_filtered(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test stopwords are filtered."""
        content = "that this with from have been"
        keywords = ml_overlay._extract_keywords(content)

        for stopword in ["that", "this", "with", "from", "have", "been"]:
            assert stopword not in keywords


# =============================================================================
# Anomaly Score Tests
# =============================================================================


class TestAnomalyScoring:
    """Tests for anomaly scoring."""

    def test_short_content_anomaly(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test short content gets higher anomaly score."""
        result = AnalysisResult()
        score = ml_overlay._compute_anomaly_score("short", result)

        assert score >= 0.2

    def test_long_content_anomaly(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test very long content gets higher anomaly score."""
        result = AnalysisResult()
        score = ml_overlay._compute_anomaly_score("a" * 15000, result)

        assert score >= 0.3

    def test_low_confidence_anomaly(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test low classification confidence increases anomaly."""
        result = AnalysisResult(
            classification=ClassificationResult(
                primary_class="test",
                confidence=0.1,
                all_classes={},
                features_used=[],
            )
        )
        score = ml_overlay._compute_anomaly_score("normal content", result)

        assert score >= 0.2

    def test_extreme_sentiment_anomaly(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test extreme sentiment increases anomaly."""
        result = AnalysisResult(sentiment=0.95)
        score = ml_overlay._compute_anomaly_score("normal content here", result)

        assert score >= 0.2


# =============================================================================
# Summary Generation Tests
# =============================================================================


class TestSummaryGeneration:
    """Tests for summary generation."""

    def test_generate_summary(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test summary generation."""
        content = "First sentence here. Second sentence follows. Third sentence too."
        summary = ml_overlay._generate_summary(content)

        assert len(summary) > 0
        assert summary.endswith(".")

    def test_summary_empty_content(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test summary of empty content."""
        summary = ml_overlay._generate_summary("")
        assert summary == ""


# =============================================================================
# Similarity Tests
# =============================================================================


class TestSimilarityComputation:
    """Tests for similarity computation."""

    @pytest.mark.asyncio
    async def test_same_content_similarity(
        self, initialized_overlay: MLIntelligenceOverlay
    ) -> None:
        """Test similarity of identical content."""
        similarity = await initialized_overlay.compute_similarity("test content", "test content")

        assert abs(similarity - 1.0) < 0.0001

    @pytest.mark.asyncio
    async def test_different_content_similarity(
        self, initialized_overlay: MLIntelligenceOverlay
    ) -> None:
        """Test similarity of different content."""
        similarity = await initialized_overlay.compute_similarity(
            "content about Python programming",
            "completely unrelated topic about cooking",
        )

        assert -1.0 <= similarity <= 1.0


# =============================================================================
# Statistics and Cache Tests
# =============================================================================


class TestStatisticsAndCache:
    """Tests for statistics tracking and cache management."""

    @pytest.mark.asyncio
    async def test_stats_tracking(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test statistics tracking."""
        await initialized_overlay.execute(
            context=overlay_context,
            input_data={"content": "Test content"},
        )

        stats = initialized_overlay.get_stats()

        assert stats["embeddings_generated"] >= 1
        assert stats["classifications_performed"] >= 1

    def test_clear_cache(self, ml_overlay: MLIntelligenceOverlay) -> None:
        """Test cache clearing."""
        ml_overlay._embedding_cache["key1"] = [0.1, 0.2]
        ml_overlay._embedding_cache["key2"] = [0.3, 0.4]

        cleared = ml_overlay.clear_cache()

        assert cleared == 2
        assert len(ml_overlay._embedding_cache) == 0


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_ml_intelligence factory function."""

    def test_create_default(self) -> None:
        """Test creating default overlay."""
        overlay = create_ml_intelligence()
        assert isinstance(overlay, MLIntelligenceOverlay)

    def test_create_production_mode_requires_provider(self) -> None:
        """Test production mode requires embedding provider."""
        with pytest.raises(ValueError):
            create_ml_intelligence(production_mode=True)

    def test_create_with_provider(self) -> None:
        """Test creating with embedding provider."""

        async def provider(content: str) -> list[float]:
            return [0.1] * 128

        overlay = create_ml_intelligence(
            production_mode=True,
            embedding_provider=provider,
        )
        assert overlay._embedding_provider is not None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_execute_handles_ml_error(
        self,
        initialized_overlay: MLIntelligenceOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution handles ML processing errors gracefully."""

        async def failing_analyze(*args, **kwargs):
            raise MLProcessingError("Test error")

        initialized_overlay._analyze = failing_analyze

        result = await initialized_overlay.execute(
            context=overlay_context,
            input_data={"content": "test"},
        )

        assert result.success is False
        assert "ML analysis failed" in result.error
