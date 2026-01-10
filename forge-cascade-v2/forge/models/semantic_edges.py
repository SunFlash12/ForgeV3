"""
Semantic Edge Models

Bidirectional semantic relationships between capsules that encode
meaning beyond simple parent-child derivation.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from forge.models.base import ForgeModel, TimestampMixin, generate_id


class SemanticRelationType(str, Enum):
    """
    Types of semantic relationships between capsules.

    These extend beyond the basic DERIVED_FROM lineage to capture
    richer knowledge connections.
    """

    # Bidirectional relationships
    RELATED_TO = "RELATED_TO"          # Generic semantic association
    CONTRADICTS = "CONTRADICTS"        # Conflicting information

    # Directed relationships (source -> target)
    SUPPORTS = "SUPPORTS"              # Source supports target's claims
    ELABORATES = "ELABORATES"          # Source provides detail on target
    SUPERSEDES = "SUPERSEDES"          # Source replaces target
    REFERENCES = "REFERENCES"          # Source cites target
    IMPLEMENTS = "IMPLEMENTS"          # Source implements target's concept
    EXTENDS = "EXTENDS"                # Source extends target's idea

    @property
    def is_bidirectional(self) -> bool:
        """Check if this relationship type is bidirectional."""
        return self in {
            SemanticRelationType.RELATED_TO,
            SemanticRelationType.CONTRADICTS,
        }

    @property
    def inverse(self) -> "SemanticRelationType | None":
        """
        Get the inverse relationship type, if applicable.

        Bidirectional relationships (RELATED_TO, CONTRADICTS) are their own inverse.
        Directed relationships have no natural inverse - they are asymmetric.
        """
        if self.is_bidirectional:
            return self  # Symmetric relationships
        # Directed relationships have no inverse
        # (e.g., if A supports B, B doesn't necessarily support A)
        return None


class ContradictionSeverity(str, Enum):
    """Severity levels for contradictions."""

    LOW = "low"            # Minor discrepancy
    MEDIUM = "medium"      # Significant disagreement
    HIGH = "high"          # Direct contradiction
    CRITICAL = "critical"  # Fundamental conflict


class ContradictionStatus(str, Enum):
    """Resolution status for contradictions."""

    UNRESOLVED = "unresolved"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"  # Contradiction acknowledged, both valid


class EvidenceType(str, Enum):
    """Types of evidence for SUPPORTS relationships."""

    EMPIRICAL = "empirical"        # Data-backed
    THEORETICAL = "theoretical"    # Logical/theoretical
    CITATION = "citation"          # Referenced source
    EXAMPLE = "example"            # Concrete example
    CONSENSUS = "consensus"        # Community agreement


# ═══════════════════════════════════════════════════════════════
# SEMANTIC EDGE MODELS
# ═══════════════════════════════════════════════════════════════


class SemanticEdgeBase(ForgeModel):
    """Base properties for semantic edges."""

    source_id: str = Field(description="Source capsule ID")
    target_id: str = Field(description="Target capsule ID")
    relationship_type: SemanticRelationType

    # Common properties
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this relationship (0-1)",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Explanation for this relationship",
    )
    auto_detected: bool = Field(
        default=False,
        description="Whether this was auto-detected by LLM",
    )


class SemanticEdgeCreate(SemanticEdgeBase):
    """Schema for creating a semantic edge."""

    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific properties",
    )

    @field_validator("properties")
    @classmethod
    def validate_properties(cls, v: dict, info) -> dict:
        """Validate properties based on relationship type."""
        rel_type = info.data.get("relationship_type")
        if rel_type == SemanticRelationType.CONTRADICTS:
            if "severity" not in v:
                v["severity"] = ContradictionSeverity.MEDIUM.value
            if "resolution_status" not in v:
                v["resolution_status"] = ContradictionStatus.UNRESOLVED.value
        elif rel_type == SemanticRelationType.SUPPORTS:
            if "evidence_type" not in v:
                v["evidence_type"] = EvidenceType.THEORETICAL.value
        return v


class SemanticEdge(SemanticEdgeBase, TimestampMixin):
    """Complete semantic edge with metadata."""

    id: str = Field(default_factory=generate_id)
    created_by: str = Field(description="User who created this edge")

    # Type-specific properties
    properties: dict[str, Any] = Field(default_factory=dict)

    # Computed
    bidirectional: bool = Field(default=False)

    def __init__(self, **data):
        super().__init__(**data)
        self.bidirectional = self.relationship_type.is_bidirectional


class SemanticEdgeWithNodes(SemanticEdge):
    """Semantic edge with source and target capsule info."""

    source_title: str | None = None
    source_type: str | None = None
    target_title: str | None = None
    target_type: str | None = None


# ═══════════════════════════════════════════════════════════════
# SPECIALIZED EDGE TYPES
# ═══════════════════════════════════════════════════════════════


class ContradictionEdge(SemanticEdge):
    """A CONTRADICTS relationship with resolution tracking."""

    @property
    def severity(self) -> ContradictionSeverity:
        return ContradictionSeverity(
            self.properties.get("severity", ContradictionSeverity.MEDIUM.value)
        )

    @property
    def resolution_status(self) -> ContradictionStatus:
        return ContradictionStatus(
            self.properties.get("resolution_status", ContradictionStatus.UNRESOLVED.value)
        )

    @property
    def resolution_notes(self) -> str | None:
        return self.properties.get("resolution_notes")


class SupportEdge(SemanticEdge):
    """A SUPPORTS relationship with evidence tracking."""

    @property
    def evidence_type(self) -> EvidenceType:
        return EvidenceType(
            self.properties.get("evidence_type", EvidenceType.THEORETICAL.value)
        )

    @property
    def evidence_reference(self) -> str | None:
        return self.properties.get("evidence_reference")

    @property
    def strength(self) -> float:
        """How strongly does source support target."""
        return self.properties.get("strength", self.confidence)


class SupersedesEdge(SemanticEdge):
    """A SUPERSEDES relationship for content replacement."""

    @property
    def deprecated_at(self) -> datetime | None:
        ts = self.properties.get("deprecated_at")
        if ts and isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    @property
    def deprecation_reason(self) -> str | None:
        return self.properties.get("deprecation_reason")

    @property
    def migration_notes(self) -> str | None:
        return self.properties.get("migration_notes")


# ═══════════════════════════════════════════════════════════════
# SEMANTIC GRAPH ANALYSIS
# ═══════════════════════════════════════════════════════════════


class SemanticNeighbor(ForgeModel):
    """A semantically connected neighbor capsule."""

    capsule_id: str
    title: str | None = None
    capsule_type: str | None = None
    trust_level: int | None = None
    relationship_type: SemanticRelationType
    direction: str = Field(description="'incoming' or 'outgoing' or 'both'")
    confidence: float = Field(ge=0.0, le=1.0)
    edge_id: str


class SemanticDistance(ForgeModel):
    """Semantic distance between two capsules."""

    source_id: str
    target_id: str
    distance: float = Field(
        ge=0.0,
        description="Semantic distance (lower = more related)",
    )
    path: list[str] = Field(
        default_factory=list,
        description="Path of capsule IDs connecting source to target",
    )
    relationship_types: list[SemanticRelationType] = Field(
        default_factory=list,
        description="Types of relationships along the path",
    )
    avg_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Average confidence along the path",
    )


class ContradictionCluster(ForgeModel):
    """A cluster of contradicting capsules."""

    cluster_id: str = Field(default_factory=generate_id)
    capsule_ids: list[str] = Field(default_factory=list)
    edges: list[SemanticEdge] = Field(default_factory=list)
    overall_severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    resolution_status: ContradictionStatus = ContradictionStatus.UNRESOLVED
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def size(self) -> int:
        return len(self.capsule_ids)


# ═══════════════════════════════════════════════════════════════
# LLM AUTO-DETECTION
# ═══════════════════════════════════════════════════════════════


class RelationshipClassification(ForgeModel):
    """LLM classification of relationship between two capsules."""

    source_id: str
    target_id: str
    relationship_type: SemanticRelationType | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="LLM's explanation")
    evidence_snippets: list[str] = Field(
        default_factory=list,
        description="Text snippets supporting the classification",
    )
    should_create: bool = Field(
        default=False,
        description="Whether confidence is high enough to create edge",
    )


class SemanticAnalysisRequest(ForgeModel):
    """Request to analyze semantic relationships for a capsule."""

    capsule_id: str
    content: str
    embedding: list[float] | None = None
    max_candidates: int = Field(default=20, ge=1, le=100)
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    relationship_types: list[SemanticRelationType] | None = Field(
        default=None,
        description="Specific types to look for (None = all)",
    )


class SemanticAnalysisResult(ForgeModel):
    """Result of semantic relationship analysis."""

    capsule_id: str
    classifications: list[RelationshipClassification] = Field(default_factory=list)
    edges_created: list[SemanticEdge] = Field(default_factory=list)
    candidates_analyzed: int = Field(ge=0)
    analysis_time_ms: float = Field(ge=0.0)
    model_used: str | None = None


# ═══════════════════════════════════════════════════════════════
# QUERY MODELS
# ═══════════════════════════════════════════════════════════════


class SemanticEdgeQuery(ForgeModel):
    """Query parameters for semantic edges."""

    capsule_id: str | None = Field(default=None, description="Filter by capsule")
    relationship_types: list[SemanticRelationType] | None = None
    direction: str = Field(
        default="both",
        pattern="^(in|out|both)$",
        description="Edge direction relative to capsule_id",
    )
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    include_auto_detected: bool = Field(default=True)
    created_by: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ContradictionQuery(ForgeModel):
    """Query for finding contradictions."""

    capsule_id: str | None = Field(
        default=None,
        description="Find contradictions involving this capsule",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Find contradictions in capsules with these tags",
    )
    min_severity: ContradictionSeverity = Field(default=ContradictionSeverity.LOW)
    resolution_status: ContradictionStatus | None = None
    include_resolved: bool = Field(default=False)
    limit: int = Field(default=50, ge=1, le=500)
