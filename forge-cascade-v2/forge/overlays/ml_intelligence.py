"""
ML Intelligence Overlay for Forge Cascade V2

Pattern recognition, classification, and embedding generation.
Part of the ANALYSIS phase in the 7-phase pipeline.

Responsibilities:
- Generate semantic embeddings for capsules
- Classify content by type and category
- Detect patterns and anomalies
- Extract entities and relationships
- Compute similarity scores
"""

import hashlib
import math
import re
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

import structlog

from ..models.events import Event, EventType
from ..models.overlay import Capability
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


class MLProcessingError(OverlayError):
    """ML processing error."""
    pass


class EmbeddingError(MLProcessingError):
    """Embedding generation error."""
    pass


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    embedding: list[float]
    model: str
    dimensions: int
    input_tokens: int
    generation_time_ms: float


@dataclass
class ClassificationResult:
    """Result of content classification."""
    primary_class: str
    confidence: float
    all_classes: dict[str, float]
    features_used: list[str]


@dataclass
class EntityExtractionResult:
    """Result of entity extraction."""
    entities: list[dict[str, Any]]  # [{"text": ..., "type": ..., "start": ..., "end": ...}]
    relationships: list[dict[str, Any]]  # [{"from": ..., "to": ..., "type": ...}]


@dataclass
class PatternMatch:
    """A detected pattern."""
    pattern_name: str
    confidence: float
    evidence: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    embedding: EmbeddingResult | None = None
    classification: ClassificationResult | None = None
    entities: EntityExtractionResult | None = None
    patterns: list[PatternMatch] = field(default_factory=list)
    anomaly_score: float = 0.0
    summary: str | None = None
    keywords: list[str] = field(default_factory=list)
    sentiment: float | None = None  # -1.0 to 1.0
    processing_time_ms: float = 0.0


class MLIntelligenceOverlay(BaseOverlay):
    """
    ML Intelligence overlay for content analysis.

    Provides pattern recognition, classification, embedding
    generation, and entity extraction capabilities.

    Note: This implementation uses lightweight local algorithms.
    For production, integrate with external ML services
    (OpenAI, Cohere, local transformers, etc.)
    """

    NAME = "ml_intelligence"
    VERSION = "1.0.0"
    DESCRIPTION = "Pattern recognition, classification, and embedding generation"

    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.SYSTEM_EVENT,
    }

    REQUIRED_CAPABILITIES = {Capability.DATABASE_READ}

    # Default classification categories
    DEFAULT_CATEGORIES = {
        "technical": ["code", "api", "function", "algorithm", "database", "server"],
        "business": ["revenue", "profit", "customer", "market", "strategy", "sales"],
        "personal": ["family", "friend", "birthday", "vacation", "health", "hobby"],
        "educational": ["learn", "study", "course", "lecture", "research", "paper"],
        "creative": ["story", "poem", "art", "music", "design", "creative"],
        "governance": ["proposal", "vote", "policy", "rule", "consensus", "council"],
    }

    # Entity patterns
    ENTITY_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "url": r'https?://[^\s<>"{}|\\^`\[\]]+',
        "date": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
        "time": r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b',
        "money": r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP)\b',
        "phone": r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b',
        "version": r'\bv?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?\b',
    }

    def __init__(
        self,
        embedding_dimensions: int = 384,
        enable_classification: bool = True,
        enable_entity_extraction: bool = True,
        enable_pattern_detection: bool = True,
        enable_sentiment: bool = True,
        custom_categories: dict[str, list[str]] | None = None,
        embedding_provider: Callable[[str], Coroutine[Any, Any, list[float]]] | None = None
    ) -> None:
        """
        Initialize the ML Intelligence overlay.

        Args:
            embedding_dimensions: Dimensions for embeddings
            enable_classification: Enable content classification
            enable_entity_extraction: Enable entity extraction
            enable_pattern_detection: Enable pattern detection
            enable_sentiment: Enable sentiment analysis
            custom_categories: Custom classification categories
            embedding_provider: Optional external embedding function
        """
        super().__init__()

        self._embedding_dim = embedding_dimensions
        self._enable_classification = enable_classification
        self._enable_entities = enable_entity_extraction
        self._enable_patterns = enable_pattern_detection
        self._enable_sentiment = enable_sentiment

        # Merge categories
        self._categories = {**self.DEFAULT_CATEGORIES}
        if custom_categories:
            self._categories.update(custom_categories)

        # External provider
        self._embedding_provider: Callable[[str], Coroutine[Any, Any, list[float]]] | None = embedding_provider

        # Cache for embeddings
        self._embedding_cache: dict[str, list[float]] = {}
        self._cache_max_size = 1000

        # Statistics
        self._stats = {
            "embeddings_generated": 0,
            "classifications_performed": 0,
            "entities_extracted": 0,
            "cache_hits": 0
        }

        self._logger = logger.bind(overlay=self.NAME)

    async def initialize(self) -> bool:
        """Initialize the ML intelligence overlay."""
        self._logger.info(
            "ml_intelligence_initialized",
            embedding_dim=self._embedding_dim,
            categories=list(self._categories.keys())
        )
        return True

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute ML analysis.

        Args:
            context: Execution context
            event: Triggering event
            input_data: Data to analyze

        Returns:
            Analysis result
        """
        import time
        start_time = time.time()

        data = input_data or {}
        if event:
            data.update(event.payload or {})

        # Extract content to analyze
        content = self._extract_content(data)
        if not content:
            # SECURITY FIX (Audit 4 - M): Fix OverlayResult construction - remove invalid params
            return OverlayResult.ok(
                data={"analysis": None, "reason": "No content to analyze"}
            )

        # Run analysis
        try:
            result = await self._analyze(content, context)
            result.processing_time_ms = (time.time() - start_time) * 1000

            self._logger.info(
                "ml_analysis_complete",
                has_embedding=result.embedding is not None,
                classification=result.classification.primary_class if result.classification else None,
                entities_found=len(result.entities.entities) if result.entities else 0,
                patterns_found=len(result.patterns),
                duration_ms=round(result.processing_time_ms, 2)
            )

            # SECURITY FIX (Audit 4 - M): Fix OverlayResult construction - use class methods
            return OverlayResult.ok(
                data={
                    "analysis": {
                        "embedding": result.embedding.embedding if result.embedding else None,
                        "embedding_model": result.embedding.model if result.embedding else None,
                        "classification": {
                            "primary": result.classification.primary_class,
                            "confidence": result.classification.confidence,
                            "all": result.classification.all_classes
                        } if result.classification else None,
                        "entities": result.entities.entities if result.entities else [],
                        "relationships": result.entities.relationships if result.entities else [],
                        "patterns": [
                            {"name": p.pattern_name, "confidence": p.confidence}
                            for p in result.patterns
                        ],
                        "anomaly_score": result.anomaly_score,
                        "keywords": result.keywords,
                        "sentiment": result.sentiment,
                        "summary": result.summary,
                        "processing_time_ms": round(result.processing_time_ms, 2)
                    }
                },
                metrics={
                    "content_length": len(content),
                    "entities_found": len(result.entities.entities) if result.entities else 0,
                    "patterns_found": len(result.patterns),
                    "embedding_dimensions": self._embedding_dim
                }
            )

        except (MLProcessingError, EmbeddingError, ValueError, TypeError, KeyError, RuntimeError) as e:
            self._logger.error(
                "ml_analysis_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return OverlayResult.fail(error=f"ML analysis failed: {str(e)}")

    def _extract_content(self, data: dict[str, Any]) -> str:
        """Extract text content from data."""
        # Try common content fields
        for field_name in ["content", "text", "body", "message", "title", "description"]:
            if field_name in data and data[field_name]:
                val = data[field_name]
                if isinstance(val, str):
                    return val
                elif isinstance(val, dict):
                    return str(val)

        # Fallback to full data
        return str(data) if data else ""

    async def _analyze(
        self,
        content: str,
        context: OverlayContext
    ) -> AnalysisResult:
        """Perform full analysis on content."""
        result = AnalysisResult()

        # Generate embedding
        result.embedding = await self._generate_embedding(content)
        self._stats["embeddings_generated"] += 1

        # Classification
        if self._enable_classification:
            result.classification = self._classify(content)
            self._stats["classifications_performed"] += 1

        # Entity extraction
        if self._enable_entities:
            result.entities = self._extract_entities(content)
            self._stats["entities_extracted"] += len(result.entities.entities)

        # Pattern detection
        if self._enable_patterns:
            result.patterns = self._detect_patterns(content, context)

        # Sentiment
        if self._enable_sentiment:
            result.sentiment = self._analyze_sentiment(content)

        # Keywords
        result.keywords = self._extract_keywords(content)

        # Anomaly score
        result.anomaly_score = self._compute_anomaly_score(content, result)

        # Summary
        result.summary = self._generate_summary(content)

        return result

    async def _generate_embedding(self, content: str) -> EmbeddingResult:
        """
        Generate embedding for content.

        Uses the Forge embedding service for real semantic embeddings.
        Falls back to external provider if configured.
        """
        import time
        start_time = time.time()

        # Check cache
        cache_key = hashlib.md5(content.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            self._stats["cache_hits"] += 1
            return EmbeddingResult(
                embedding=self._embedding_cache[cache_key],
                model="cache",
                dimensions=self._embedding_dim,
                input_tokens=len(content.split()),
                generation_time_ms=0.0
            )

        embedding = None
        model_name = "unknown"

        # Try custom external provider first if configured
        if self._embedding_provider:
            try:
                embedding = await self._embedding_provider(content)
                model_name = "external"
            except (EmbeddingError, ConnectionError, TimeoutError, ValueError, RuntimeError, OSError) as e:
                self._logger.warning(
                    "external_embedding_provider_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Use Forge embedding service as default
        if embedding is None:
            try:
                from forge.services.embedding import (
                    EmbeddingConfigurationError,
                    get_embedding_service,
                )

                embedding_service = get_embedding_service()
                result = await embedding_service.embed(content)
                embedding = result.embedding
                model_name = result.model
                self._embedding_dim = result.dimensions

            except EmbeddingConfigurationError as e:
                self._logger.warning(
                    "embedding_service_not_configured",
                    error=str(e),
                    action="falling_back_to_pseudo_embedding"
                )
                # Fall back to pseudo-embedding only if no embedding service configured
                embedding = self._pseudo_embedding(content)
                model_name = "pseudo-hash-fallback"

            except (EmbeddingError, RuntimeError, ValueError, ConnectionError, OSError) as e:
                self._logger.error(
                    "embedding_service_error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                # Fall back to pseudo-embedding on error
                embedding = self._pseudo_embedding(content)
                model_name = "pseudo-hash-fallback"

        # Cache result
        if len(self._embedding_cache) >= self._cache_max_size:
            # Remove oldest (simple FIFO)
            oldest_key = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest_key]
        self._embedding_cache[cache_key] = embedding

        duration_ms = (time.time() - start_time) * 1000

        return EmbeddingResult(
            embedding=embedding,
            model=model_name,
            dimensions=len(embedding),
            input_tokens=len(content.split()),
            generation_time_ms=duration_ms
        )

    def _pseudo_embedding(self, content: str) -> list[float]:
        """
        Generate a deterministic pseudo-embedding.

        WARNING: This is NOT a real semantic embedding. It provides consistent
        but meaningless vectors for fallback scenarios when embedding service
        is unavailable. The Forge embedding service should be configured for
        real semantic search functionality.

        This fallback exists only to prevent errors during development or when
        embedding infrastructure is temporarily unavailable.
        """
        # Normalize content
        normalized = content.lower().strip()

        # Generate hash-based values
        embedding = []
        for i in range(self._embedding_dim):
            # Create different hash for each dimension
            h = hashlib.sha256(f"{normalized}:{i}".encode()).digest()
            # Convert to float in [-1, 1]
            value = (int.from_bytes(h[:4], 'big') / (2**32 - 1)) * 2 - 1
            embedding.append(value)

        # Normalize to unit length
        magnitude = math.sqrt(sum(x*x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    def _classify(self, content: str) -> ClassificationResult:
        """Classify content into categories."""
        content_lower = content.lower()
        words = set(re.findall(r'\b\w+\b', content_lower))

        scores = {}
        features_used = []

        for category, keywords in self._categories.items():
            score = 0
            for keyword in keywords:
                if keyword in words:
                    score += 1
                    features_used.append(f"{category}:{keyword}")
            scores[category] = score / max(len(keywords), 1)

        # Normalize scores
        total = sum(scores.values()) or 1
        normalized = {k: v / total for k, v in scores.items()}

        # Find primary class
        primary = max(normalized.items(), key=lambda x: x[1])

        return ClassificationResult(
            primary_class=primary[0],
            confidence=primary[1],
            all_classes=normalized,
            features_used=features_used[:10]  # Limit features returned
        )

    def _extract_entities(self, content: str) -> EntityExtractionResult:
        """Extract named entities from content."""
        entities = []

        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            for match in re.finditer(pattern, content):
                entities.append({
                    "text": match.group(),
                    "type": entity_type,
                    "start": match.start(),
                    "end": match.end()
                })

        # Simple relationship detection (entities in same sentence)
        relationships = []
        sentences = re.split(r'[.!?]', content)

        for sentence in sentences:
            sentence_entities = [
                e for e in entities
                if e["text"] in sentence
            ]
            # Create relationships between entities in same sentence
            for i, e1 in enumerate(sentence_entities):
                for e2 in sentence_entities[i+1:]:
                    relationships.append({
                        "from": e1["text"],
                        "to": e2["text"],
                        "type": "co_occurrence",
                        "context": sentence[:100]
                    })

        return EntityExtractionResult(
            entities=entities,
            relationships=relationships[:20]  # Limit relationships
        )

    def _detect_patterns(
        self,
        content: str,
        context: OverlayContext
    ) -> list[PatternMatch]:
        """Detect patterns in content."""
        patterns = []

        # Question pattern
        if "?" in content:
            question_count = content.count("?")
            patterns.append(PatternMatch(
                pattern_name="questions",
                confidence=min(question_count / 5, 1.0),
                evidence=[f"Found {question_count} question(s)"]
            ))

        # List pattern
        list_indicators = re.findall(r'^\s*[-*•]\s', content, re.MULTILINE)
        if list_indicators:
            patterns.append(PatternMatch(
                pattern_name="list_format",
                confidence=min(len(list_indicators) / 10, 1.0),
                evidence=[f"Found {len(list_indicators)} list items"]
            ))

        # Code pattern
        code_indicators = re.findall(r'```|def |function |class |import |const |let |var ', content)
        if code_indicators:
            patterns.append(PatternMatch(
                pattern_name="code_content",
                confidence=min(len(code_indicators) / 5, 1.0),
                evidence=code_indicators[:5]
            ))

        # Technical pattern
        tech_terms = re.findall(r'\b(?:API|HTTP|JSON|SQL|HTML|CSS|JWT|REST|GraphQL)\b', content, re.IGNORECASE)
        if tech_terms:
            patterns.append(PatternMatch(
                pattern_name="technical_content",
                confidence=min(len(tech_terms) / 5, 1.0),
                evidence=list(set(tech_terms))[:5]
            ))

        # Reference pattern (links to other content)
        references = re.findall(r'(?:see|refer to|mentioned in|linked from)\s+["\']?[\w\s]+["\']?', content, re.IGNORECASE)
        if references:
            patterns.append(PatternMatch(
                pattern_name="references",
                confidence=min(len(references) / 3, 1.0),
                evidence=references[:3]
            ))

        return patterns

    def _analyze_sentiment(self, content: str) -> float:
        """
        Simple sentiment analysis.

        Returns value from -1.0 (negative) to 1.0 (positive).
        """
        positive_words = {
            "good", "great", "excellent", "amazing", "wonderful", "fantastic",
            "love", "happy", "joy", "success", "perfect", "best", "better",
            "thank", "thanks", "appreciate", "helpful", "useful", "awesome"
        }
        negative_words = {
            "bad", "terrible", "awful", "horrible", "hate", "sad", "angry",
            "fail", "failure", "worst", "worse", "problem", "issue", "error",
            "bug", "broken", "wrong", "difficult", "hard", "frustrating"
        }

        words = set(re.findall(r'\b\w+\b', content.lower()))

        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)
        total = positive_count + negative_count

        if total == 0:
            return 0.0

        return (positive_count - negative_count) / total

    def _extract_keywords(self, content: str, max_keywords: int = 10) -> list[str]:
        """Extract key terms from content."""
        # Simple TF approach
        words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())

        # Filter stopwords
        stopwords = {
            "that", "this", "with", "from", "have", "been", "were", "they",
            "their", "what", "when", "where", "which", "while", "about",
            "would", "could", "should", "there", "these", "those", "being"
        }
        words = [w for w in words if w not in stopwords]

        # Count frequencies
        freq: defaultdict[str, int] = defaultdict(int)
        for word in words:
            freq[word] += 1

        # Sort by frequency
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        return [word for word, _ in sorted_words[:max_keywords]]

    def _compute_anomaly_score(
        self,
        content: str,
        result: AnalysisResult
    ) -> float:
        """
        Compute anomaly score for content.

        Higher scores indicate more unusual content.
        """
        score = 0.0

        # Length anomaly
        length = len(content)
        if length < 10:
            score += 0.2
        elif length > 10000:
            score += 0.3

        # Classification confidence anomaly
        if result.classification and result.classification.confidence < 0.2:
            score += 0.2

        # Entity density anomaly
        if result.entities:
            entity_density = len(result.entities.entities) / max(len(content.split()), 1)
            if entity_density > 0.5:  # More than half words are entities
                score += 0.3

        # Extreme sentiment
        if result.sentiment:
            if abs(result.sentiment) > 0.8:
                score += 0.2

        return min(score, 1.0)

    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """Generate a brief summary of content."""
        # Simple extractive summary - first sentence(s)
        sentences = re.split(r'[.!?]', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return content[:max_length]

        summary = sentences[0]
        for sentence in sentences[1:]:
            if len(summary) + len(sentence) + 2 <= max_length:
                summary += ". " + sentence
            else:
                break

        if not summary.endswith((".", "!", "?")):
            summary += "."

        return summary

    def get_stats(self) -> dict[str, Any]:
        """Get processing statistics."""
        return {
            **self._stats,
            "cache_size": len(self._embedding_cache),
            "categories": list(self._categories.keys())
        }

    def clear_cache(self) -> int:
        """Clear embedding cache. Returns number of entries cleared."""
        count = len(self._embedding_cache)
        self._embedding_cache.clear()
        return count

    async def compute_similarity(
        self,
        content1: str,
        content2: str
    ) -> float:
        """
        Compute cosine similarity between two pieces of content.

        Returns value from -1.0 to 1.0.
        """
        emb1 = await self._generate_embedding(content1)
        emb2 = await self._generate_embedding(content2)

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(emb1.embedding, emb2.embedding, strict=False))
        mag1 = math.sqrt(sum(x*x for x in emb1.embedding))
        mag2 = math.sqrt(sum(x*x for x in emb2.embedding))

        if mag1 * mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)


# Convenience function
def create_ml_intelligence(
    production_mode: bool = False,
    **kwargs: Any,
) -> MLIntelligenceOverlay:
    """
    Create an ML Intelligence overlay.

    Args:
        production_mode: If True, expects external embedding provider
        **kwargs: Additional configuration

    Returns:
        Configured MLIntelligenceOverlay
    """
    if production_mode and "embedding_provider" not in kwargs:
        raise ValueError("Production mode requires embedding_provider")

    return MLIntelligenceOverlay(**kwargs)
