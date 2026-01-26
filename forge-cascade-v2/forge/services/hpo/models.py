"""
HPO Data Models

Models for Human Phenotype Ontology terms, annotations, and matches.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PhenotypeSeverity(str, Enum):
    """Severity of a phenotype presentation."""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    PROFOUND = "profound"
    UNKNOWN = "unknown"


class PhenotypeOccurrence(str, Enum):
    """Frequency of phenotype occurrence in a disease."""
    ALWAYS = "always"              # 100%
    VERY_FREQUENT = "very_frequent"  # 80-99%
    FREQUENT = "frequent"          # 30-79%
    OCCASIONAL = "occasional"      # 5-29%
    RARE = "rare"                  # 1-4%
    EXCLUDED = "excluded"          # 0%
    UNKNOWN = "unknown"


@dataclass
class HPOTerm:
    """
    Human Phenotype Ontology term.

    HPO provides a standardized vocabulary for phenotypic abnormalities.
    Each term has an ID (e.g., HP:0001250) and a name (e.g., "Seizure").
    """
    hpo_id: str                     # e.g., "HP:0001250"
    name: str                       # e.g., "Seizure"
    definition: str | None = None   # Full definition text
    synonyms: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)  # Parent HPO IDs
    children: list[str] = field(default_factory=list)  # Child HPO IDs
    is_obsolete: bool = False
    replaced_by: str | None = None  # If obsolete, new term

    # Additional metadata
    category: str | None = None     # Top-level category
    xrefs: list[str] = field(default_factory=list)  # Cross-references (UMLS, SNOMED)
    created_at: datetime | None = None

    @property
    def is_root(self) -> bool:
        """Check if this is a root term (no parents)."""
        return len(self.parents) == 0

    @property
    def depth(self) -> int:
        """Return 0 for root, counting from parents would require graph traversal."""
        if self.is_root:
            return 0
        return -1  # Unknown without traversal

    def __hash__(self) -> int:
        return hash(self.hpo_id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HPOTerm):
            return self.hpo_id == other.hpo_id
        return False


@dataclass
class HPOAnnotation:
    """
    HPO-Disease annotation.

    Links an HPO term to a disease with frequency information.
    """
    hpo_id: str
    disease_id: str               # MONDO, OMIM, or ORPHA ID
    disease_name: str
    occurrence: PhenotypeOccurrence = PhenotypeOccurrence.UNKNOWN
    onset: str | None = None      # Age of onset (HPO term)
    modifier: str | None = None   # Severity modifier
    source: str | None = None     # Evidence source (PMID, expert)
    evidence_code: str | None = None  # PCS, IEA, TAS

    @property
    def frequency_percent(self) -> float:
        """Convert occurrence to approximate percentage."""
        mapping = {
            PhenotypeOccurrence.ALWAYS: 100.0,
            PhenotypeOccurrence.VERY_FREQUENT: 90.0,
            PhenotypeOccurrence.FREQUENT: 55.0,
            PhenotypeOccurrence.OCCASIONAL: 17.0,
            PhenotypeOccurrence.RARE: 2.5,
            PhenotypeOccurrence.EXCLUDED: 0.0,
            PhenotypeOccurrence.UNKNOWN: 50.0,  # Assume 50% if unknown
        }
        return mapping.get(self.occurrence, 50.0)


@dataclass
class PhenotypeMatch:
    """
    Result of matching a phenotype to an HPO term.

    Used in phenotype extraction and normalization.
    """
    hpo_id: str
    hpo_name: str
    match_type: str               # "exact", "synonym", "semantic", "parent"
    confidence: float             # 0.0 to 1.0
    original_text: str            # The text that was matched
    character_offset: tuple[int, int] | None = None  # Start, end position

    # Additional context
    negated: bool = False         # True if phenotype is absent
    severity: PhenotypeSeverity = PhenotypeSeverity.UNKNOWN
    laterality: str | None = None  # "left", "right", "bilateral"
    temporal: str | None = None    # "onset", "progression", etc.

    def __lt__(self, other: "PhenotypeMatch") -> bool:
        """Enable sorting by confidence."""
        return self.confidence > other.confidence


@dataclass
class ExtractedPhenotype:
    """
    A phenotype extracted from clinical text.

    Contains the matched HPO term, context, and extraction metadata.
    """
    hpo_id: str
    hpo_name: str
    original_text: str
    context: str | None = None     # Surrounding text for context

    # Match quality
    confidence: float = 0.0
    match_type: str = "unknown"

    # Clinical modifiers
    negated: bool = False
    severity: PhenotypeSeverity = PhenotypeSeverity.UNKNOWN
    onset: str | None = None
    laterality: str | None = None
    progression: str | None = None

    # Extraction metadata
    source_section: str | None = None  # "chief_complaint", "history", etc.
    character_span: tuple[int, int] | None = None
    extracted_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "hpo_id": self.hpo_id,
            "hpo_name": self.hpo_name,
            "original_text": self.original_text,
            "context": self.context,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "negated": self.negated,
            "severity": self.severity.value,
            "onset": self.onset,
            "laterality": self.laterality,
            "progression": self.progression,
            "source_section": self.source_section,
        }


@dataclass
class HPOHierarchy:
    """
    Cached HPO hierarchy for efficient traversal.

    Stores parent-child relationships and precomputed paths.
    """
    terms: dict[str, HPOTerm] = field(default_factory=dict)
    parent_map: dict[str, set[str]] = field(default_factory=dict)
    child_map: dict[str, set[str]] = field(default_factory=dict)
    ancestor_cache: dict[str, set[str]] = field(default_factory=dict)
    descendant_cache: dict[str, set[str]] = field(default_factory=dict)

    def get_ancestors(self, hpo_id: str, include_self: bool = False) -> set[str]:
        """Get all ancestors of an HPO term."""
        if hpo_id in self.ancestor_cache:
            result = self.ancestor_cache[hpo_id].copy()
        else:
            result = set()
            to_process = [hpo_id]
            while to_process:
                current = to_process.pop()
                parents = self.parent_map.get(current, set())
                for parent in parents:
                    if parent not in result:
                        result.add(parent)
                        to_process.append(parent)
            self.ancestor_cache[hpo_id] = result.copy()

        if include_self:
            result.add(hpo_id)
        return result

    def get_descendants(self, hpo_id: str, include_self: bool = False) -> set[str]:
        """Get all descendants of an HPO term."""
        if hpo_id in self.descendant_cache:
            result = self.descendant_cache[hpo_id].copy()
        else:
            result = set()
            to_process = [hpo_id]
            while to_process:
                current = to_process.pop()
                children = self.child_map.get(current, set())
                for child in children:
                    if child not in result:
                        result.add(child)
                        to_process.append(child)
            self.descendant_cache[hpo_id] = result.copy()

        if include_self:
            result.add(hpo_id)
        return result

    def get_lca(self, term1: str, term2: str) -> str | None:
        """
        Find the Lowest Common Ancestor of two HPO terms.

        Returns the most specific term that is an ancestor of both.
        """
        ancestors1 = self.get_ancestors(term1, include_self=True)
        ancestors2 = self.get_ancestors(term2, include_self=True)

        common = ancestors1 & ancestors2
        if not common:
            return None

        # Find the LCA (the one with the most ancestors itself)
        lca = None
        max_depth = -1
        for ancestor in common:
            depth = len(self.get_ancestors(ancestor))
            if depth > max_depth:
                max_depth = depth
                lca = ancestor

        return lca

    def semantic_similarity(self, term1: str, term2: str) -> float:
        """
        Calculate semantic similarity between two HPO terms.

        Uses Resnik-like information content based on LCA.
        """
        if term1 == term2:
            return 1.0

        lca = self.get_lca(term1, term2)
        if not lca:
            return 0.0

        # IC = -log(descendants / total_terms)
        # Similarity = IC(LCA) / max(IC(term1), IC(term2))
        total = len(self.terms)
        if total == 0:
            return 0.0

        lca_desc = len(self.get_descendants(lca, include_self=True))
        term1_desc = len(self.get_descendants(term1, include_self=True))
        term2_desc = len(self.get_descendants(term2, include_self=True))

        # Avoid log(0)
        if lca_desc == 0 or term1_desc == 0 or term2_desc == 0:
            return 0.0

        import math
        ic_lca = -math.log(lca_desc / total)
        ic_term1 = -math.log(term1_desc / total)
        ic_term2 = -math.log(term2_desc / total)

        max_ic = max(ic_term1, ic_term2)
        if max_ic == 0:
            return 0.0

        return min(ic_lca / max_ic, 1.0)
