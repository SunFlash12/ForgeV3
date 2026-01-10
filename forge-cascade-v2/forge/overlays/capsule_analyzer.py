"""
Capsule Analyzer Overlay

Provides content analysis capabilities for capsules:
- Content classification
- Insight extraction
- Quality scoring
- Semantic similarity analysis
- Trend detection across capsules

Mentioned in spec as core overlay for extracting insights
from capsule content.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from forge.models.base import CapsuleType
from forge.models.events import Event, EventType
from forge.overlays.base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
)

logger = structlog.get_logger(__name__)


@dataclass
class ContentAnalysis:
    """Results of content analysis."""
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    avg_sentence_length: float = 0.0
    reading_level: str = "standard"
    key_terms: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    quality_score: float = 0.5


@dataclass
class InsightExtraction:
    """Extracted insights from content."""
    main_ideas: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    questions_raised: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass
class SimilarityResult:
    """Similarity comparison result."""
    capsule_id: str
    similarity_score: float
    common_terms: list[str] = field(default_factory=list)
    relationship: str = "related"  # related, duplicate, evolution


class CapsuleAnalyzerOverlay(BaseOverlay):
    """
    Capsule content analysis overlay.

    Provides:
    - Content classification and categorization
    - Quality scoring
    - Insight extraction
    - Similarity detection
    - Trend analysis
    """

    NAME = "capsule_analyzer"
    VERSION = "1.0.0"
    DESCRIPTION = "Analyzes capsule content for insights and quality"

    SUBSCRIBED_EVENTS = {EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED}

    # SECURITY FIX (Audit 4 - M): Add cache size limits to prevent memory exhaustion
    MAX_ANALYSIS_CACHE_SIZE = 10000  # Maximum cached analyses
    MAX_TOPIC_INDEX_SIZE = 5000  # Maximum topics tracked

    def __init__(self):
        super().__init__()
        self._analysis_cache: dict[str, ContentAnalysis] = {}
        self._topic_index: dict[str, set[str]] = {}  # topic -> capsule_ids
        self._term_frequency: Counter = Counter()
        self._stats: dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize analyzer resources."""
        self._logger.info("Initializing capsule analyzer")
        self._stats["initialized_at"] = datetime.now(UTC).isoformat()
        return await super().initialize()

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._analysis_cache.clear()
        self._topic_index.clear()
        self._term_frequency.clear()
        self._logger.info("Capsule analyzer shutdown complete")
        await super().cleanup()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """
        Process capsule analysis requests.

        Operations:
        - analyze: Full content analysis
        - extract_insights: Extract key insights
        - classify: Classify content type
        - score_quality: Score content quality
        - find_similar: Find similar capsules
        - get_trends: Get trending topics
        """
        data = input_data or {}
        operation = data.get("operation", "analyze")

        try:
            if operation == "analyze":
                result = await self._analyze_content(data)
            elif operation == "extract_insights":
                result = await self._extract_insights(data)
            elif operation == "classify":
                result = await self._classify_content(data)
            elif operation == "score_quality":
                result = await self._score_quality(data)
            elif operation == "find_similar":
                result = await self._find_similar(data)
            elif operation == "get_trends":
                result = await self._get_trends(data)
            elif operation == "summarize":
                result = await self._summarize_content(data)
            else:
                return OverlayResult.fail(f"Unknown operation: {operation}")

            self._stats["operations_processed"] = self._stats.get("operations_processed", 0) + 1

            return OverlayResult.ok(result)

        except Exception as e:
            self._logger.error("Capsule analyzer error", error=str(e))
            return OverlayResult.fail(str(e))

    async def _analyze_content(self, data: dict) -> dict:
        """Perform comprehensive content analysis."""
        content = data.get("content", "")
        capsule_id = data.get("capsule_id")

        if not content:
            return {"error": "No content provided"}

        # Basic text metrics
        words = content.split()
        word_count = len(words)
        char_count = len(content)

        # Sentence analysis
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        # Reading level estimation (simplified)
        if avg_sentence_length < 10:
            reading_level = "basic"
        elif avg_sentence_length < 20:
            reading_level = "standard"
        elif avg_sentence_length < 30:
            reading_level = "advanced"
        else:
            reading_level = "expert"

        # Extract key terms (simple frequency-based)
        word_freq = Counter(
            word.lower() for word in words
            if len(word) > 4 and word.isalpha()
        )
        key_terms = [term for term, _ in word_freq.most_common(10)]

        # Topic detection (simplified keyword matching)
        topics = self._detect_topics(content)

        # Sentiment (very basic)
        sentiment = self._analyze_sentiment(content)

        # Quality score
        quality_score = self._calculate_quality_score(
            word_count, sentence_count, len(key_terms)
        )

        # Update global term frequency
        self._term_frequency.update(word_freq)

        # Update topic index
        if capsule_id:
            for topic in topics:
                if topic not in self._topic_index:
                    # SECURITY FIX (Audit 4 - M): Limit topic index size
                    if len(self._topic_index) >= self.MAX_TOPIC_INDEX_SIZE:
                        # Remove topic with fewest capsules (least useful)
                        min_topic = min(self._topic_index, key=lambda t: len(self._topic_index[t]))
                        del self._topic_index[min_topic]
                    self._topic_index[topic] = set()
                self._topic_index[topic].add(capsule_id)

        analysis = {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "reading_level": reading_level,
            "key_terms": key_terms,
            "topics": topics,
            "sentiment": sentiment,
            "quality_score": round(quality_score, 2),
        }

        # Cache analysis with size limit
        if capsule_id:
            # SECURITY FIX (Audit 4 - M): Evict oldest entries if cache is full
            if len(self._analysis_cache) >= self.MAX_ANALYSIS_CACHE_SIZE:
                # Remove oldest entry (FIFO - first key added)
                oldest_key = next(iter(self._analysis_cache))
                del self._analysis_cache[oldest_key]
            self._analysis_cache[capsule_id] = ContentAnalysis(**analysis)

        return analysis

    async def _extract_insights(self, data: dict) -> dict:
        """Extract key insights from content."""
        content = data.get("content", "")

        if not content:
            return {"error": "No content provided"}

        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Extract different types of insights
        main_ideas: list[str] = []
        key_facts: list[str] = []
        action_items: list[str] = []
        questions: list[str] = []
        references: list[str] = []

        for sentence in sentences:
            lower = sentence.lower()

            # Action items (contains actionable verbs)
            if any(verb in lower for verb in ["should", "must", "need to", "will", "implement"]):
                action_items.append(sentence)

            # Questions
            elif sentence.endswith("?") or "?" in sentence:
                questions.append(sentence)

            # Facts (contains numbers or definitive statements)
            elif re.search(r'\d+', sentence) or any(word in lower for word in ["is", "are", "was", "were"]):
                key_facts.append(sentence)

            # References (mentions external sources)
            elif any(word in lower for word in ["according to", "study", "research", "source"]):
                references.append(sentence)

            # Main ideas (first sentences of paragraphs or key statements)
            elif len(sentence.split()) > 5:
                main_ideas.append(sentence)

        return {
            "main_ideas": main_ideas[:5],
            "key_facts": key_facts[:5],
            "action_items": action_items[:5],
            "questions_raised": questions[:3],
            "references": references[:3],
        }

    async def _classify_content(self, data: dict) -> dict:
        """Classify content into capsule type."""
        content = data.get("content", "")
        current_type = data.get("current_type")

        if not content:
            return {"error": "No content provided"}

        lower = content.lower()

        # Score for each type
        scores = {
            CapsuleType.KNOWLEDGE.value: 0,
            CapsuleType.CODE.value: 0,
            CapsuleType.DECISION.value: 0,
            CapsuleType.INSIGHT.value: 0,
            CapsuleType.CONFIG.value: 0,
            CapsuleType.NOTE.value: 0,
        }

        # Code detection
        if any(pattern in content for pattern in ["def ", "class ", "import ", "function", "=>", "{}", "return "]):
            scores[CapsuleType.CODE.value] += 3
        if re.search(r'```[\w]*\n', content):
            scores[CapsuleType.CODE.value] += 2

        # Decision detection
        if any(word in lower for word in ["decided", "decision", "chose", "approved", "rejected"]):
            scores[CapsuleType.DECISION.value] += 2

        # Insight detection
        if any(word in lower for word in ["insight", "learned", "discovered", "realized", "observation"]):
            scores[CapsuleType.INSIGHT.value] += 2

        # Config detection
        if any(pattern in content for pattern in ["=", ":", "true", "false"]) and "{" in content:
            scores[CapsuleType.CONFIG.value] += 2

        # Knowledge detection
        if any(word in lower for word in ["how to", "guide", "tutorial", "explanation", "overview"]):
            scores[CapsuleType.KNOWLEDGE.value] += 2

        # Note is default low-content type
        if len(content.split()) < 50:
            scores[CapsuleType.NOTE.value] += 1

        # Get best classification
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type] / (sum(scores.values()) or 1)

        return {
            "suggested_type": best_type,
            "confidence": round(confidence, 2),
            "all_scores": scores,
            "current_type": current_type,
            "should_reclassify": current_type != best_type and confidence > 0.6,
        }

    async def _score_quality(self, data: dict) -> dict:
        """Score content quality on multiple dimensions."""
        content = data.get("content", "")

        if not content:
            return {"error": "No content provided"}

        words = content.split()
        word_count = len(words)

        # Dimension scores (0-1)
        scores = {
            "completeness": 0.0,
            "clarity": 0.0,
            "structure": 0.0,
            "depth": 0.0,
            "relevance": 0.0,
        }

        # Completeness: based on length
        if word_count >= 100:
            scores["completeness"] = min(word_count / 500, 1.0)
        else:
            scores["completeness"] = word_count / 100

        # Clarity: based on sentence structure
        sentences = re.split(r'[.!?]+', content)
        avg_sentence_words = word_count / len(sentences) if sentences else 0
        if 10 <= avg_sentence_words <= 25:
            scores["clarity"] = 0.9
        elif avg_sentence_words < 10:
            scores["clarity"] = 0.6
        else:
            scores["clarity"] = max(0.3, 1.0 - (avg_sentence_words - 25) * 0.02)

        # Structure: check for headers, lists, paragraphs
        has_headers = bool(re.search(r'^#+\s|^###', content, re.MULTILINE))
        has_lists = bool(re.search(r'^\s*[-*•]\s|^\d+\.\s', content, re.MULTILINE))
        has_paragraphs = "\n\n" in content

        structure_features = sum([has_headers, has_lists, has_paragraphs])
        scores["structure"] = structure_features / 3

        # Depth: unique terms and concepts
        unique_words = len({word.lower() for word in words if len(word) > 3})
        depth_ratio = unique_words / word_count if word_count > 0 else 0
        scores["depth"] = min(depth_ratio * 3, 1.0)

        # Relevance: presence of key terms (simplified)
        relevant_terms = ["forge", "capsule", "knowledge", "system", "data", "analysis"]
        relevance_count = sum(1 for term in relevant_terms if term in content.lower())
        scores["relevance"] = min(relevance_count / 3, 1.0)

        # Overall quality score (weighted average)
        weights = {
            "completeness": 0.2,
            "clarity": 0.25,
            "structure": 0.15,
            "depth": 0.25,
            "relevance": 0.15,
        }

        overall = sum(scores[dim] * weights[dim] for dim in scores)

        return {
            "overall_score": round(overall, 2),
            "dimensions": {k: round(v, 2) for k, v in scores.items()},
            "quality_level": self._quality_level(overall),
            "improvement_suggestions": self._get_improvement_suggestions(scores),
        }

    async def _find_similar(self, data: dict) -> dict:
        """Find similar capsules based on content."""
        content = data.get("content", "")
        capsule_id = data.get("capsule_id")
        limit = data.get("limit", 5)

        if not content:
            return {"error": "No content provided"}

        # Get terms from content
        words = content.lower().split()
        content_terms = {word for word in words if len(word) > 4 and word.isalpha()}

        # Find capsules with similar topics
        similar: list[dict] = []

        for topic in self._detect_topics(content):
            if topic in self._topic_index:
                for other_id in self._topic_index[topic]:
                    if other_id != capsule_id:
                        # Get cached analysis if available
                        other_analysis = self._analysis_cache.get(other_id)
                        if other_analysis:
                            common = set(other_analysis.key_terms) & content_terms
                            if common:
                                similar.append({
                                    "capsule_id": other_id,
                                    "similarity_score": len(common) / max(len(content_terms), 1),
                                    "common_terms": list(common)[:5],
                                    "relationship": "related",
                                })

        # Sort by similarity and limit
        similar.sort(key=lambda x: x["similarity_score"], reverse=True)

        return {
            "similar_capsules": similar[:limit],
            "search_terms": list(content_terms)[:10],
            "topics_searched": self._detect_topics(content),
        }

    async def _get_trends(self, data: dict) -> dict:
        """Get trending topics and terms."""
        top_n = data.get("top_n", 10)

        # Most frequent terms
        trending_terms = self._term_frequency.most_common(top_n)

        # Most active topics
        trending_topics = sorted(
            self._topic_index.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:top_n]

        return {
            "trending_terms": [{"term": term, "count": count} for term, count in trending_terms],
            "trending_topics": [
                {"topic": topic, "capsule_count": len(capsule_ids)}
                for topic, capsule_ids in trending_topics
            ],
            "total_capsules_analyzed": len(self._analysis_cache),
            "total_unique_terms": len(self._term_frequency),
        }

    async def _summarize_content(self, data: dict) -> dict:
        """Generate a summary of content."""
        content = data.get("content", "")
        max_sentences = data.get("max_sentences", 3)

        if not content:
            return {"error": "No content provided"}

        # Split into sentences
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 3]

        if not sentences:
            return {"summary": content[:200], "method": "truncation"}

        # Score sentences by importance (simple heuristic)
        scored = []
        for i, sentence in enumerate(sentences):
            score = 0
            # First sentences are often important
            if i < 2:
                score += 2
            # Longer sentences often contain more info
            score += len(sentence.split()) / 20
            # Sentences with key terms
            if any(term in sentence.lower() for term in ["key", "main", "important", "essential"]):
                score += 1
            scored.append((score, sentence))

        # Get top sentences
        scored.sort(reverse=True)
        summary_sentences = [s for _, s in scored[:max_sentences]]

        return {
            "summary": ". ".join(summary_sentences) + ".",
            "sentence_count": len(summary_sentences),
            "compression_ratio": round(len(summary_sentences) / len(sentences), 2) if sentences else 1.0,
            "method": "extractive",
        }

    def _detect_topics(self, content: str) -> list[str]:
        """Detect topics from content."""
        lower = content.lower()

        topic_keywords = {
            "technology": ["software", "code", "programming", "system", "api", "database"],
            "security": ["security", "auth", "permission", "trust", "vulnerability"],
            "governance": ["governance", "vote", "proposal", "decision", "policy"],
            "machine_learning": ["ml", "model", "training", "prediction", "analysis"],
            "architecture": ["architecture", "design", "pattern", "structure", "component"],
            "performance": ["performance", "optimization", "cache", "latency", "speed"],
            "data": ["data", "storage", "database", "query", "record"],
        }

        detected = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in lower for keyword in keywords):
                detected.append(topic)

        return detected if detected else ["general"]

    def _analyze_sentiment(self, content: str) -> str:
        """Simple sentiment analysis."""
        lower = content.lower()

        positive_words = ["good", "great", "excellent", "success", "improve", "best", "positive"]
        negative_words = ["bad", "fail", "error", "problem", "issue", "wrong", "negative"]

        positive_count = sum(1 for word in positive_words if word in lower)
        negative_count = sum(1 for word in negative_words if word in lower)

        if positive_count > negative_count + 1:
            return "positive"
        elif negative_count > positive_count + 1:
            return "negative"
        return "neutral"

    def _calculate_quality_score(
        self,
        word_count: int,
        sentence_count: int,
        key_term_count: int,
    ) -> float:
        """Calculate overall quality score."""
        # Normalize metrics
        length_score = min(word_count / 200, 1.0)
        structure_score = min(sentence_count / 10, 1.0) if sentence_count > 0 else 0
        depth_score = min(key_term_count / 5, 1.0)

        return (length_score * 0.3 + structure_score * 0.3 + depth_score * 0.4)

    def _quality_level(self, score: float) -> str:
        """Convert numeric score to quality level."""
        if score >= 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        elif score >= 0.4:
            return "fair"
        elif score >= 0.2:
            return "needs_improvement"
        return "poor"

    def _get_improvement_suggestions(self, scores: dict[str, float]) -> list[str]:
        """Get suggestions for improving content quality."""
        suggestions = []

        if scores["completeness"] < 0.5:
            suggestions.append("Add more detail and context to improve completeness")
        if scores["clarity"] < 0.5:
            suggestions.append("Use shorter, clearer sentences")
        if scores["structure"] < 0.5:
            suggestions.append("Add headers, lists, or paragraph breaks for better structure")
        if scores["depth"] < 0.5:
            suggestions.append("Include more specific terms and concepts")
        if scores["relevance"] < 0.5:
            suggestions.append("Ensure content is relevant to the topic")

        return suggestions

    async def handle_event(self, event: Event) -> None:
        """Handle capsule events for auto-analysis."""
        if event.type in {EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED}:
            capsule_id = event.data.get("capsule_id")
            content = event.data.get("content")

            if capsule_id and content:
                # Auto-analyze new/updated capsules
                await self._analyze_content({
                    "capsule_id": capsule_id,
                    "content": content,
                })

                self._logger.debug(
                    "Auto-analyzed capsule",
                    capsule_id=capsule_id,
                )

    async def health_check(self) -> bool:
        """Check overlay health."""
        try:
            # Test analysis functionality
            result = await self._analyze_content({"content": "Test content for health check."})
            return "word_count" in result
        except Exception:
            return False
