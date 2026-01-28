"""
Comprehensive tests for the CapsuleAnalyzerOverlay.

Tests cover:
- Overlay initialization and configuration
- Content analysis (word count, sentences, reading level)
- Insight extraction
- Content classification
- Quality scoring
- Similarity detection
- Trend analysis
- Summarization
- Topic detection
- Sentiment analysis
- Event handling
- Health checks
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.base import CapsuleType
from forge.models.events import Event, EventType
from forge.models.overlay import Capability
from forge.overlays.base import OverlayContext, OverlayResult
from forge.overlays.capsule_analyzer import (
    CapsuleAnalyzerOverlay,
    ContentAnalysis,
    InsightExtraction,
    SimilarityResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analyzer() -> CapsuleAnalyzerOverlay:
    """Create a CapsuleAnalyzerOverlay instance."""
    return CapsuleAnalyzerOverlay()


@pytest.fixture
async def initialized_analyzer(analyzer: CapsuleAnalyzerOverlay) -> CapsuleAnalyzerOverlay:
    """Create and initialize a CapsuleAnalyzerOverlay."""
    await analyzer.initialize()
    return analyzer


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="capsule_analyzer",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ},
    )


@pytest.fixture
def sample_content() -> str:
    """Sample content for testing."""
    return """
    This is a comprehensive guide on software architecture patterns.
    The system uses a microservices approach for better scalability.
    Key components include the API gateway, authentication service, and database layer.
    Performance optimization is crucial for handling high traffic loads.
    """


@pytest.fixture
def code_content() -> str:
    """Sample code content for testing."""
    return """
    def calculate_sum(numbers):
        return sum(numbers)

    class DataProcessor:
        def process(self, data):
            return data

    import os
    ```python
    print("Hello")
    ```
    """


# =============================================================================
# Initialization Tests
# =============================================================================


class TestCapsuleAnalyzerInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test default initialization values."""
        assert analyzer.NAME == "capsule_analyzer"
        assert analyzer.VERSION == "1.0.0"
        assert len(analyzer._analysis_cache) == 0
        assert len(analyzer._topic_index) == 0

    @pytest.mark.asyncio
    async def test_initialize(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test overlay initialization."""
        result = await analyzer.initialize()
        assert result is True
        assert "initialized_at" in analyzer._stats

    @pytest.mark.asyncio
    async def test_cleanup(self, initialized_analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test overlay cleanup."""
        initialized_analyzer._analysis_cache["test"] = ContentAnalysis()
        initialized_analyzer._topic_index["test"] = {"capsule1"}

        await initialized_analyzer.cleanup()

        assert len(initialized_analyzer._analysis_cache) == 0
        assert len(initialized_analyzer._topic_index) == 0

    def test_subscribed_events(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test subscribed events."""
        assert EventType.CAPSULE_CREATED in analyzer.SUBSCRIBED_EVENTS
        assert EventType.CAPSULE_UPDATED in analyzer.SUBSCRIBED_EVENTS


# =============================================================================
# Content Analysis Tests
# =============================================================================


class TestContentAnalysis:
    """Tests for content analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_basic_metrics(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
        sample_content: str,
    ) -> None:
        """Test basic content metrics."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "analyze", "content": sample_content},
        )

        assert result.success is True
        data = result.data
        assert "word_count" in data
        assert "char_count" in data
        assert "sentence_count" in data
        assert data["word_count"] > 0

    @pytest.mark.asyncio
    async def test_analyze_reading_level(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test reading level estimation."""
        # Short sentences - basic level
        basic_content = "Short. Simple. Words."
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "analyze", "content": basic_content},
        )
        assert result.data["reading_level"] == "basic"

        # Longer sentences - advanced level
        advanced_content = (
            "This is a significantly longer sentence that contains many more words "
            "and demonstrates a more complex writing style that requires advanced "
            "reading comprehension skills."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "analyze", "content": advanced_content},
        )
        assert result.data["reading_level"] in ["advanced", "expert"]

    @pytest.mark.asyncio
    async def test_analyze_key_terms(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
        sample_content: str,
    ) -> None:
        """Test key term extraction."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "analyze", "content": sample_content},
        )

        assert "key_terms" in result.data
        assert len(result.data["key_terms"]) > 0

    @pytest.mark.asyncio
    async def test_analyze_no_content(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis with no content."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "analyze", "content": ""},
        )

        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_analyze_caching(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis result caching."""
        capsule_id = "test-capsule-123"

        await initialized_analyzer.execute(
            context=overlay_context,
            input_data={
                "operation": "analyze",
                "content": "Test content",
                "capsule_id": capsule_id,
            },
        )

        assert capsule_id in initialized_analyzer._analysis_cache


# =============================================================================
# Insight Extraction Tests
# =============================================================================


class TestInsightExtraction:
    """Tests for insight extraction."""

    @pytest.mark.asyncio
    async def test_extract_action_items(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test action item extraction."""
        content = (
            "We should implement the feature. "
            "You must complete the task. "
            "We need to review the code."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "extract_insights", "content": content},
        )

        assert result.success is True
        assert len(result.data["action_items"]) >= 1

    @pytest.mark.asyncio
    async def test_extract_questions(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test question extraction."""
        content = "What is the solution? How do we proceed? Why did this happen?"
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "extract_insights", "content": content},
        )

        assert result.success is True
        assert len(result.data["questions_raised"]) >= 1

    @pytest.mark.asyncio
    async def test_extract_facts(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test fact extraction."""
        content = (
            "The system is running on 4 servers. "
            "The database contains 1000 records."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "extract_insights", "content": content},
        )

        assert result.success is True
        assert len(result.data["key_facts"]) >= 1


# =============================================================================
# Content Classification Tests
# =============================================================================


class TestContentClassification:
    """Tests for content classification."""

    @pytest.mark.asyncio
    async def test_classify_code(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
        code_content: str,
    ) -> None:
        """Test code content classification."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "classify", "content": code_content},
        )

        assert result.success is True
        assert result.data["suggested_type"] == CapsuleType.CODE.value

    @pytest.mark.asyncio
    async def test_classify_knowledge(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test knowledge content classification."""
        content = (
            "This is a guide on how to implement the tutorial. "
            "An overview and explanation follows."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "classify", "content": content},
        )

        assert result.success is True
        assert result.data["suggested_type"] == CapsuleType.KNOWLEDGE.value

    @pytest.mark.asyncio
    async def test_classify_decision(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test decision content classification."""
        content = "We decided to use Python. The decision was approved by the team."
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "classify", "content": content},
        )

        assert result.success is True
        assert result.data["suggested_type"] == CapsuleType.DECISION.value

    @pytest.mark.asyncio
    async def test_classify_insight(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test insight content classification."""
        content = (
            "We learned that caching improves performance. "
            "This observation was discovered during testing."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "classify", "content": content},
        )

        assert result.success is True
        assert result.data["suggested_type"] == CapsuleType.INSIGHT.value

    @pytest.mark.asyncio
    async def test_classify_with_confidence(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test classification confidence."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "classify", "content": "Test content"},
        )

        assert "confidence" in result.data
        assert 0 <= result.data["confidence"] <= 1


# =============================================================================
# Quality Scoring Tests
# =============================================================================


class TestQualityScoring:
    """Tests for quality scoring."""

    @pytest.mark.asyncio
    async def test_score_quality_dimensions(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
        sample_content: str,
    ) -> None:
        """Test quality scoring dimensions."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "score_quality", "content": sample_content},
        )

        assert result.success is True
        dimensions = result.data["dimensions"]
        assert "completeness" in dimensions
        assert "clarity" in dimensions
        assert "structure" in dimensions
        assert "depth" in dimensions
        assert "relevance" in dimensions

    @pytest.mark.asyncio
    async def test_score_quality_level(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test quality level assignment."""
        # High quality content
        high_quality = """
        # Introduction

        This is a comprehensive guide about Forge capsule knowledge management.

        ## Key Points

        - The system handles data efficiently
        - Analysis provides useful insights
        - Performance is optimized for scale

        The architecture ensures reliability and consistency across all operations.
        """
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "score_quality", "content": high_quality},
        )

        assert result.data["quality_level"] in ["excellent", "good", "fair"]

    @pytest.mark.asyncio
    async def test_score_improvement_suggestions(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test improvement suggestions."""
        # Low quality content
        low_quality = "Short content."
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "score_quality", "content": low_quality},
        )

        assert "improvement_suggestions" in result.data


# =============================================================================
# Similarity Detection Tests
# =============================================================================


class TestSimilarityDetection:
    """Tests for similarity detection."""

    @pytest.mark.asyncio
    async def test_find_similar_no_matches(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test finding similar when no cache exists."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "find_similar", "content": "Test content"},
        )

        assert result.success is True
        assert "similar_capsules" in result.data

    @pytest.mark.asyncio
    async def test_find_similar_with_cache(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test finding similar with cached analyses."""
        # First, analyze some capsules
        await initialized_analyzer.execute(
            context=overlay_context,
            input_data={
                "operation": "analyze",
                "content": "Technology software system database",
                "capsule_id": "capsule-1",
            },
        )
        await initialized_analyzer.execute(
            context=overlay_context,
            input_data={
                "operation": "analyze",
                "content": "Technology software programming code",
                "capsule_id": "capsule-2",
            },
        )

        # Now find similar
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={
                "operation": "find_similar",
                "content": "Technology software development",
                "capsule_id": "capsule-3",
            },
        )

        assert result.success is True


# =============================================================================
# Trend Analysis Tests
# =============================================================================


class TestTrendAnalysis:
    """Tests for trend analysis."""

    @pytest.mark.asyncio
    async def test_get_trends_empty(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting trends with no data."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "get_trends"},
        )

        assert result.success is True
        assert "trending_terms" in result.data
        assert "trending_topics" in result.data

    @pytest.mark.asyncio
    async def test_get_trends_with_data(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting trends with analyzed data."""
        # Analyze some content
        for i in range(5):
            await initialized_analyzer.execute(
                context=overlay_context,
                input_data={
                    "operation": "analyze",
                    "content": f"Technology software system test content {i}",
                    "capsule_id": f"capsule-{i}",
                },
            )

        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "get_trends", "top_n": 5},
        )

        assert result.success is True
        assert result.data["total_capsules_analyzed"] >= 5


# =============================================================================
# Summarization Tests
# =============================================================================


class TestSummarization:
    """Tests for content summarization."""

    @pytest.mark.asyncio
    async def test_summarize_content(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
        sample_content: str,
    ) -> None:
        """Test content summarization."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "summarize", "content": sample_content},
        )

        assert result.success is True
        assert "summary" in result.data
        assert len(result.data["summary"]) > 0

    @pytest.mark.asyncio
    async def test_summarize_max_sentences(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test summarization with max sentences limit."""
        content = (
            "First sentence. Second sentence. Third sentence. "
            "Fourth sentence. Fifth sentence."
        )
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={
                "operation": "summarize",
                "content": content,
                "max_sentences": 2,
            },
        )

        assert result.success is True
        assert result.data["sentence_count"] <= 2


# =============================================================================
# Topic Detection Tests
# =============================================================================


class TestTopicDetection:
    """Tests for topic detection."""

    def test_detect_technology_topic(
        self, analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test technology topic detection."""
        content = "The software system uses a database and API for programming"
        topics = analyzer._detect_topics(content)

        assert "technology" in topics

    def test_detect_security_topic(
        self, analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test security topic detection."""
        content = "Security authentication and permission trust vulnerability"
        topics = analyzer._detect_topics(content)

        assert "security" in topics

    def test_detect_multiple_topics(
        self, analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test detecting multiple topics."""
        content = "The software system security authentication database"
        topics = analyzer._detect_topics(content)

        assert len(topics) >= 2

    def test_detect_general_topic(
        self, analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test fallback to general topic."""
        content = "Some unrelated random words here"
        topics = analyzer._detect_topics(content)

        assert "general" in topics


# =============================================================================
# Sentiment Analysis Tests
# =============================================================================


class TestAnalyzerSentiment:
    """Tests for sentiment analysis."""

    def test_positive_sentiment(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test positive sentiment detection."""
        content = "This is great and excellent, a success!"
        sentiment = analyzer._analyze_sentiment(content)

        assert sentiment == "positive"

    def test_negative_sentiment(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test negative sentiment detection."""
        content = "This is bad and terrible, a complete failure"
        sentiment = analyzer._analyze_sentiment(content)

        assert sentiment == "negative"

    def test_neutral_sentiment(self, analyzer: CapsuleAnalyzerOverlay) -> None:
        """Test neutral sentiment detection."""
        content = "The system processes data"
        sentiment = analyzer._analyze_sentiment(content)

        assert sentiment == "neutral"


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestEventHandling:
    """Tests for event handling."""

    @pytest.mark.asyncio
    async def test_handle_capsule_created_event(
        self, initialized_analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test handling capsule created event."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "capsule-123",
                "content": "Test content for analysis",
            },
        )

        await initialized_analyzer.handle_event(event)

        # Should have cached the analysis
        assert "capsule-123" in initialized_analyzer._analysis_cache

    @pytest.mark.asyncio
    async def test_handle_capsule_updated_event(
        self, initialized_analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test handling capsule updated event."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_UPDATED,
            source="test",
            payload={
                "capsule_id": "capsule-456",
                "content": "Updated content for analysis",
            },
        )

        await initialized_analyzer.handle_event(event)

        assert "capsule-456" in initialized_analyzer._analysis_cache


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health checks."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, initialized_analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test health check when healthy."""
        health = await initialized_analyzer.health_check()

        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_includes_overlay_id(
        self, initialized_analyzer: CapsuleAnalyzerOverlay
    ) -> None:
        """Test health check includes overlay ID."""
        health = await initialized_analyzer.health_check()

        assert health.overlay_id == initialized_analyzer.id


# =============================================================================
# Cache Limit Tests
# =============================================================================


class TestCacheLimits:
    """Tests for cache size limits."""

    @pytest.mark.asyncio
    async def test_analysis_cache_limit(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis cache size limit."""
        # Set a small limit for testing
        initialized_analyzer.MAX_ANALYSIS_CACHE_SIZE = 3

        for i in range(5):
            await initialized_analyzer.execute(
                context=overlay_context,
                input_data={
                    "operation": "analyze",
                    "content": f"Test content {i}",
                    "capsule_id": f"capsule-{i}",
                },
            )

        # Cache should be limited
        assert len(initialized_analyzer._analysis_cache) <= 3

    @pytest.mark.asyncio
    async def test_topic_index_limit(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test topic index size limit."""
        initialized_analyzer.MAX_TOPIC_INDEX_SIZE = 3

        # Add various content to populate topics
        for i in range(10):
            await initialized_analyzer.execute(
                context=overlay_context,
                input_data={
                    "operation": "analyze",
                    "content": f"Topic{i} software system",
                    "capsule_id": f"capsule-{i}",
                },
            )

        # Topic index should be limited
        assert len(initialized_analyzer._topic_index) <= 5


# =============================================================================
# Unknown Operation Tests
# =============================================================================


class TestUnknownOperation:
    """Tests for unknown operation handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(
        self,
        initialized_analyzer: CapsuleAnalyzerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test handling unknown operation."""
        result = await initialized_analyzer.execute(
            context=overlay_context,
            input_data={"operation": "unknown_op"},
        )

        assert result.success is False
        assert "Unknown operation" in result.error
