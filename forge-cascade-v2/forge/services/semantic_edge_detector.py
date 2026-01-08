"""
Semantic Edge Detector Service

Automatically detects and creates semantic relationships between capsules
using embedding similarity and LLM-based classification.

This service:
1. Finds semantically similar capsules via embedding vectors
2. Uses LLM reasoning to classify relationship types
3. Creates edges with confidence scores
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog

from forge.models.capsule import Capsule
from forge.models.semantic_edges import SemanticRelationType, SemanticEdge
from forge.repositories.capsule_repository import CapsuleRepository
from forge.services.embedding import EmbeddingService, get_embedding_service
from forge.services.llm import get_llm_service

logger = structlog.get_logger(__name__)


@dataclass
class RelationshipClassification:
    """Result of LLM relationship classification."""
    relationship_type: SemanticRelationType | None
    confidence: float
    reasoning: str
    bidirectional: bool = False


@dataclass
class DetectionConfig:
    """Configuration for semantic edge detection."""
    # Similarity threshold for candidate selection
    similarity_threshold: float = 0.7
    # Confidence threshold for edge creation
    confidence_threshold: float = 0.7
    # Maximum candidates to analyze per capsule
    max_candidates: int = 20
    # Enable auto-detection (can be disabled for testing)
    enabled: bool = True
    # Relationship types to detect
    enabled_types: set[SemanticRelationType] = field(default_factory=lambda: {
        SemanticRelationType.SUPPORTS,
        SemanticRelationType.CONTRADICTS,
        SemanticRelationType.ELABORATES,
        SemanticRelationType.REFERENCES,
        SemanticRelationType.RELATED_TO,
    })


@dataclass
class DetectionResult:
    """Result of semantic edge detection for a capsule."""
    capsule_id: str
    candidates_analyzed: int
    edges_created: int
    edges: list[SemanticEdge]
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


class SemanticEdgeDetector:
    """
    Service for automatic detection of semantic relationships between capsules.

    Uses a two-phase approach:
    1. Vector similarity to find candidates
    2. LLM classification to determine relationship type and confidence
    """

    # LLM prompt for relationship classification
    CLASSIFICATION_PROMPT = """Analyze the relationship between two knowledge capsules and classify their semantic connection.

## Source Capsule
Title: {source_title}
Type: {source_type}
Content:
{source_content}

## Target Capsule
Title: {target_title}
Type: {target_type}
Content:
{target_content}

## Task
Determine if there is a meaningful semantic relationship between these capsules.

Possible relationship types:
- SUPPORTS: Source provides evidence or agreement for target's claims
- CONTRADICTS: Source conflicts with or opposes target's content
- ELABORATES: Source provides additional detail, examples, or explanation of target
- REFERENCES: Source explicitly cites or mentions target
- RELATED_TO: Generic semantic association (use only if others don't fit)
- NONE: No meaningful relationship exists

## Response Format
Respond with a JSON object:
{{
    "relationship_type": "SUPPORTS" | "CONTRADICTS" | "ELABORATES" | "REFERENCES" | "RELATED_TO" | "NONE",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this relationship exists",
    "bidirectional": true/false (whether the relationship goes both ways equally)
}}

Only return the JSON object, no other text."""

    def __init__(
        self,
        capsule_repo: CapsuleRepository,
        embedding_service: EmbeddingService | None = None,
        config: DetectionConfig | None = None,
    ):
        self.capsule_repo = capsule_repo
        self.embedding_service = embedding_service or get_embedding_service()
        self.config = config or DetectionConfig()
        self._llm = None

    @property
    def llm(self):
        """Lazy load LLM service."""
        if self._llm is None:
            self._llm = get_llm_service()
        return self._llm

    async def analyze_capsule(
        self,
        capsule: Capsule,
        created_by: str,
    ) -> DetectionResult:
        """
        Analyze a capsule and detect semantic relationships to existing capsules.

        Args:
            capsule: The capsule to analyze
            created_by: User ID to attribute edge creation

        Returns:
            DetectionResult with detected edges
        """
        import time
        start = time.time()

        result = DetectionResult(
            capsule_id=capsule.id,
            candidates_analyzed=0,
            edges_created=0,
            edges=[],
        )

        if not self.config.enabled:
            return result

        try:
            # Phase 1: Find similar capsules via embedding
            candidates = await self._find_similar_capsules(capsule)
            result.candidates_analyzed = len(candidates)

            if not candidates:
                logger.debug("no_candidates_found", capsule_id=capsule.id)
                return result

            # Phase 2: Classify relationships using LLM
            for candidate, similarity in candidates:
                try:
                    classification = await self._classify_relationship(capsule, candidate)

                    if (
                        classification.relationship_type
                        and classification.relationship_type in self.config.enabled_types
                        and classification.confidence >= self.config.confidence_threshold
                    ):
                        # Create the edge
                        edge = await self._create_edge(
                            source=capsule,
                            target=candidate,
                            classification=classification,
                            similarity=similarity,
                            created_by=created_by,
                        )
                        if edge:
                            result.edges.append(edge)
                            result.edges_created += 1

                except Exception as e:
                    logger.warning(
                        "classification_failed",
                        capsule_id=capsule.id,
                        target_id=candidate.id,
                        error=str(e),
                    )
                    result.errors.append(f"Failed to classify {candidate.id}: {str(e)}")

        except Exception as e:
            logger.error("detection_failed", capsule_id=capsule.id, error=str(e))
            result.errors.append(str(e))

        result.duration_ms = (time.time() - start) * 1000
        logger.info(
            "edge_detection_complete",
            capsule_id=capsule.id,
            candidates=result.candidates_analyzed,
            created=result.edges_created,
            duration_ms=result.duration_ms,
        )

        return result

    async def _find_similar_capsules(
        self,
        capsule: Capsule,
    ) -> list[tuple[Capsule, float]]:
        """Find capsules similar to the given one via embedding."""
        if not capsule.embedding:
            # Generate embedding if not present
            content = f"{capsule.title}\n{capsule.content}"
            capsule.embedding = await self.embedding_service.embed(content)

        # Search for similar capsules
        similar = await self.capsule_repo.find_similar_by_embedding(
            embedding=capsule.embedding,
            limit=self.config.max_candidates + 1,  # +1 to account for self
            min_similarity=self.config.similarity_threshold,
        )

        # Filter out the source capsule and sort by similarity
        results = [
            (c, score)
            for c, score in similar
            if c.id != capsule.id
        ]

        return results[:self.config.max_candidates]

    async def _classify_relationship(
        self,
        source: Capsule,
        target: Capsule,
    ) -> RelationshipClassification:
        """Use LLM to classify the relationship between two capsules."""
        prompt = self.CLASSIFICATION_PROMPT.format(
            source_title=source.title,
            source_type=source.type.value if hasattr(source.type, 'value') else str(source.type),
            source_content=source.content[:2000],  # Truncate for token limits
            target_title=target.title,
            target_type=target.type.value if hasattr(target.type, 'value') else str(target.type),
            target_content=target.content[:2000],
        )

        response = await self.llm.complete(
            prompt=prompt,
            max_tokens=500,
            temperature=0.1,  # Low temperature for consistent classification
        )

        # Parse JSON response
        import json
        try:
            # Extract JSON from response (handle potential markdown wrapping)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())

            rel_type_str = data.get("relationship_type", "NONE")
            if rel_type_str == "NONE" or rel_type_str is None:
                return RelationshipClassification(
                    relationship_type=None,
                    confidence=0.0,
                    reasoning=data.get("reasoning", "No relationship detected"),
                )

            return RelationshipClassification(
                relationship_type=SemanticRelationType(rel_type_str),
                confidence=float(data.get("confidence", 0.0)),
                reasoning=data.get("reasoning", ""),
                bidirectional=bool(data.get("bidirectional", False)),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("classification_parse_error", error=str(e), response=response.text[:200])
            return RelationshipClassification(
                relationship_type=None,
                confidence=0.0,
                reasoning=f"Parse error: {str(e)}",
            )

    async def _create_edge(
        self,
        source: Capsule,
        target: Capsule,
        classification: RelationshipClassification,
        similarity: float,
        created_by: str,
    ) -> SemanticEdge | None:
        """Create a semantic edge in the database."""
        if not classification.relationship_type:
            return None

        from forge.models.semantic_edges import SemanticEdgeCreate

        properties = {
            "similarity": similarity,
            "reasoning": classification.reasoning,
            "detected_at": datetime.utcnow().isoformat(),
        }

        try:
            edge_data = SemanticEdgeCreate(
                source_id=source.id,
                target_id=target.id,
                relationship_type=classification.relationship_type,
                confidence=classification.confidence,
                reason=classification.reasoning,
                auto_detected=True,
                properties=properties,
            )
            edge = await self.capsule_repo.create_semantic_edge(
                data=edge_data,
                created_by=created_by,
            )
            return edge

        except Exception as e:
            logger.error(
                "edge_creation_failed",
                source_id=source.id,
                target_id=target.id,
                error=str(e),
            )
            return None

    async def batch_analyze(
        self,
        capsule_ids: list[str],
        created_by: str,
    ) -> list[DetectionResult]:
        """
        Analyze multiple capsules for semantic relationships.

        Useful for backfilling relationships on existing capsules.
        """
        results = []
        for capsule_id in capsule_ids:
            capsule = await self.capsule_repo.get_by_id(capsule_id)
            if capsule:
                result = await self.analyze_capsule(capsule, created_by)
                results.append(result)
            else:
                results.append(DetectionResult(
                    capsule_id=capsule_id,
                    candidates_analyzed=0,
                    edges_created=0,
                    edges=[],
                    errors=[f"Capsule {capsule_id} not found"],
                ))
        return results


# Global detector instance (lazily initialized)
_detector: SemanticEdgeDetector | None = None


def get_semantic_edge_detector(
    capsule_repo: CapsuleRepository,
) -> SemanticEdgeDetector:
    """Get or create the semantic edge detector service."""
    global _detector
    if _detector is None:
        _detector = SemanticEdgeDetector(capsule_repo)
    return _detector


def create_semantic_edge_detector(
    capsule_repo: CapsuleRepository,
    config: DetectionConfig | None = None,
) -> SemanticEdgeDetector:
    """Create a new semantic edge detector with custom config."""
    return SemanticEdgeDetector(capsule_repo, config=config)
