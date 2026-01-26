"""
Phenotype Normalizer Service

Normalizes and maps phenotypes to standardized HPO terms:
- Synonym resolution
- Semantic similarity matching
- Embedding-based matching
- Multi-level abstraction (specific to general)
"""

from dataclasses import dataclass
from typing import Any

import structlog

from .models import (
    ExtractedPhenotype,
    PhenotypeMatch,
)
from .ontology import HPOOntologyService

logger = structlog.get_logger(__name__)


@dataclass
class NormalizationConfig:
    """Configuration for phenotype normalization."""

    min_similarity: float = 0.7
    max_candidates: int = 5
    prefer_specific: bool = True  # Prefer more specific terms
    use_embeddings: bool = False
    embedding_weight: float = 0.5  # Weight for embedding vs exact match


class PhenotypeNormalizer:
    """
    Service for normalizing phenotypes to standard HPO terms.

    Features:
    - Multi-strategy matching (exact, synonym, semantic, embedding)
    - Candidate ranking
    - Specificity preference
    - Abstraction level selection
    """

    def __init__(
        self,
        ontology: HPOOntologyService,
        config: NormalizationConfig | None = None,
        embedding_service: Any = None,
    ):
        """
        Initialize the normalizer.

        Args:
            ontology: HPO ontology service
            config: Normalization configuration
            embedding_service: Optional embedding service for semantic matching
        """
        self.ontology = ontology
        self.config = config or NormalizationConfig()
        self.embedding_service = embedding_service

        # Cache for embedding lookups
        self._embedding_cache: dict[str, list[float]] = {}

    async def normalize(
        self,
        text: str,
        context: str | None = None,
    ) -> list[PhenotypeMatch]:
        """
        Normalize a phenotype description to HPO terms.

        Args:
            text: Phenotype text to normalize
            context: Optional context text

        Returns:
            List of candidate matches, sorted by confidence
        """
        if not text:
            return []

        text_lower = text.lower().strip()

        # Strategy 1: Exact match
        exact_match = self.ontology.get_term_by_name(text_lower)
        if exact_match:
            return [
                PhenotypeMatch(
                    hpo_id=exact_match.hpo_id,
                    hpo_name=exact_match.name,
                    match_type="exact",
                    confidence=1.0,
                    original_text=text,
                )
            ]

        # Strategy 2: Search with synonyms
        search_results = self.ontology.search_terms(
            text,
            limit=self.config.max_candidates * 2,
        )

        candidates = []
        for term in search_results:
            # Calculate match confidence
            confidence = self._calculate_text_similarity(text_lower, term.name.lower())

            # Check synonyms
            for syn in term.synonyms:
                syn_conf = self._calculate_text_similarity(text_lower, syn.lower())
                if syn_conf > confidence:
                    confidence = syn_conf

            if confidence >= self.config.min_similarity:
                candidates.append(
                    PhenotypeMatch(
                        hpo_id=term.hpo_id,
                        hpo_name=term.name,
                        match_type="search",
                        confidence=confidence,
                        original_text=text,
                    )
                )

        # Strategy 3: Embedding-based matching (if enabled)
        if self.config.use_embeddings and self.embedding_service:
            embedding_candidates = await self._match_by_embedding(text)
            candidates = self._merge_candidates(candidates, embedding_candidates)

        # Sort by confidence
        candidates.sort(key=lambda x: x.confidence, reverse=True)

        # Apply specificity preference
        if self.config.prefer_specific:
            candidates = self._prefer_specific_terms(candidates)

        return candidates[: self.config.max_candidates]

    async def normalize_extraction(
        self,
        extraction: ExtractedPhenotype,
    ) -> ExtractedPhenotype:
        """
        Normalize an extracted phenotype.

        Updates the HPO ID and name if a better match is found.
        """
        # Already has a high-confidence match
        if extraction.confidence >= 0.95:
            return extraction

        # Try to find better match
        matches = await self.normalize(
            extraction.original_text,
            context=extraction.context,
        )

        if matches and matches[0].confidence > extraction.confidence:
            best = matches[0]
            extraction.hpo_id = best.hpo_id
            extraction.hpo_name = best.hpo_name
            extraction.confidence = best.confidence
            extraction.match_type = f"normalized_{best.match_type}"

        return extraction

    async def normalize_batch(
        self,
        extractions: list[ExtractedPhenotype],
    ) -> list[ExtractedPhenotype]:
        """Normalize a batch of extracted phenotypes."""
        return [await self.normalize_extraction(ext) for ext in extractions]

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using multiple methods.

        Uses a combination of:
        - Jaccard similarity on tokens
        - Levenshtein ratio
        - Substring matching
        """
        if text1 == text2:
            return 1.0

        # Tokenize
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())

        # Jaccard similarity
        if tokens1 or tokens2:
            jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        else:
            jaccard = 0.0

        # Substring matching
        substring = 0.0
        if text1 in text2:
            substring = len(text1) / len(text2)
        elif text2 in text1:
            substring = len(text2) / len(text1)

        # Levenshtein ratio (simplified)
        lev_ratio = self._levenshtein_ratio(text1, text2)

        # Weighted combination
        return jaccard * 0.3 + substring * 0.3 + lev_ratio * 0.4

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio."""
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)

        # Simple Levenshtein distance
        if len1 > len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        current_row: list[int] = list(range(len1 + 1))
        for i in range(1, len2 + 1):
            previous_row: list[int] = current_row
            current_row = [i] + [0] * len1
            for j in range(1, len1 + 1):
                add, delete, change = (
                    previous_row[j] + 1,
                    current_row[j - 1] + 1,
                    previous_row[j - 1],
                )
                if s1[j - 1] != s2[i - 1]:
                    change += 1
                current_row[j] = min(add, delete, change)

        distance: int = current_row[len1]
        return 1.0 - (distance / max_len)

    async def _match_by_embedding(self, text: str) -> list[PhenotypeMatch]:
        """Match phenotype using embedding similarity."""
        if not self.embedding_service:
            return []

        try:
            # Get embedding for input text
            await self.embedding_service.embed_text(text)

            # Search similar HPO terms
            results = await self.embedding_service.semantic_search(
                query=text,
                node_type="effect/phenotype",  # PrimeKG phenotype type
                limit=self.config.max_candidates,
                min_score=self.config.min_similarity,
            )

            candidates = []
            for result in results:
                # Map PrimeKG phenotype to HPO
                hpo_id = result.get("node_id", "")
                if hpo_id.startswith("HP:"):
                    term = self.ontology.get_term(hpo_id)
                    if term:
                        candidates.append(
                            PhenotypeMatch(
                                hpo_id=hpo_id,
                                hpo_name=term.name,
                                match_type="embedding",
                                confidence=result.get("score", 0.0),
                                original_text=text,
                            )
                        )

            return candidates

        except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
            logger.warning("embedding_match_failed", error=str(e))
            return []

    def _merge_candidates(
        self,
        text_candidates: list[PhenotypeMatch],
        embedding_candidates: list[PhenotypeMatch],
    ) -> list[PhenotypeMatch]:
        """Merge text-based and embedding-based candidates."""
        merged: dict[str, PhenotypeMatch] = {}

        # Add text candidates
        for cand in text_candidates:
            merged[cand.hpo_id] = cand

        # Merge embedding candidates
        for cand in embedding_candidates:
            if cand.hpo_id in merged:
                # Combine scores
                existing = merged[cand.hpo_id]
                combined_conf = (
                    existing.confidence * (1 - self.config.embedding_weight)
                    + cand.confidence * self.config.embedding_weight
                )
                existing.confidence = combined_conf
                existing.match_type = "combined"
            else:
                # Scale down embedding-only matches
                cand.confidence *= self.config.embedding_weight
                merged[cand.hpo_id] = cand

        return list(merged.values())

    def _prefer_specific_terms(
        self,
        candidates: list[PhenotypeMatch],
    ) -> list[PhenotypeMatch]:
        """
        Prefer more specific (deeper in hierarchy) terms.

        If two candidates are similar in confidence, prefer the more specific one.
        """
        if len(candidates) <= 1:
            return candidates

        # Calculate specificity (depth in hierarchy)
        specificity = {}
        for cand in candidates:
            # More ancestors = more specific
            ancestors = self.ontology.get_ancestors(cand.hpo_id)
            specificity[cand.hpo_id] = len(ancestors)

        # Adjust confidence based on specificity
        max_spec = max(specificity.values()) if specificity else 1

        for cand in candidates:
            spec = specificity.get(cand.hpo_id, 0)
            # Small boost for more specific terms
            spec_bonus = (spec / max_spec) * 0.05
            cand.confidence = min(1.0, cand.confidence + spec_bonus)

        # Re-sort
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates

    def get_parent_terms(
        self,
        hpo_id: str,
        max_level: int = 3,
    ) -> list[tuple[str, str, int]]:
        """
        Get parent terms up to a certain level.

        Returns list of (hpo_id, name, level) tuples.
        """
        result = []
        current = {hpo_id}
        level = 0

        while current and level < max_level:
            level += 1
            next_level = set()

            for term_id in current:
                term = self.ontology.get_term(term_id)
                if term:
                    for parent_id in term.parents:
                        parent = self.ontology.get_term(parent_id)
                        if parent:
                            result.append((parent_id, parent.name, level))
                            next_level.add(parent_id)

            current = next_level

        return result

    def abstract_to_level(
        self,
        hpo_id: str,
        target_level: int = 2,
    ) -> str | None:
        """
        Abstract an HPO term to a higher level in the hierarchy.

        Useful for grouping specific phenotypes into categories.
        """
        parents = self.get_parent_terms(hpo_id, max_level=target_level + 1)

        # Find term at target level
        for parent_id, _, level in parents:
            if level == target_level:
                return parent_id

        # Return the highest available
        if parents:
            return parents[-1][0]

        return None

    def group_by_category(
        self,
        hpo_ids: list[str],
    ) -> dict[str, list[str]]:
        """
        Group HPO terms by their top-level category.

        Categories are like:
        - Abnormality of the nervous system
        - Abnormality of the cardiovascular system
        """
        groups: dict[str, list[str]] = {}

        for hpo_id in hpo_ids:
            category = self.ontology.get_category(hpo_id)
            if category:
                if category not in groups:
                    groups[category] = []
                groups[category].append(hpo_id)
            else:
                if "Uncategorized" not in groups:
                    groups["Uncategorized"] = []
                groups["Uncategorized"].append(hpo_id)

        return groups


# =============================================================================
# Factory Function
# =============================================================================


def create_phenotype_normalizer(
    ontology: HPOOntologyService,
    config: NormalizationConfig | None = None,
    embedding_service: Any = None,
) -> PhenotypeNormalizer:
    """
    Create a phenotype normalizer instance.

    Args:
        ontology: HPO ontology service
        config: Normalization configuration
        embedding_service: Optional embedding service

    Returns:
        Configured PhenotypeNormalizer
    """
    return PhenotypeNormalizer(
        ontology=ontology,
        config=config,
        embedding_service=embedding_service,
    )
