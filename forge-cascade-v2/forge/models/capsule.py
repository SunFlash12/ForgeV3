"""
Capsule Models

The Capsule is the atomic unit of knowledge in Forge.
Capsules support versioning, symbolic inheritance (lineage),
and semantic search via embeddings.

Integrity Features:
- Content hash verification (SHA-256)
- Digital signatures (Ed25519) - Phase 2
- Merkle tree lineage verification - Phase 3
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from forge.models.base import (
    CapsuleType,
    ForgeModel,
    TimestampMixin,
    TrustLevel,
)


class IntegrityStatus(str, Enum):
    """Status of capsule content integrity verification."""

    UNVERIFIED = "unverified"  # Never verified
    VALID = "valid"  # Hash matches content
    CORRUPTED = "corrupted"  # Hash mismatch detected
    PENDING = "pending"  # Verification in progress


class ContentBlock(ForgeModel):
    """
    A block of content within a capsule.

    ContentBlocks allow for structured content with different types.
    """

    content: str = Field(description="The content text")
    content_type: str = Field(default="text", description="Type of content (text, code, markdown, etc.)")
    language: str | None = Field(default=None, description="Programming language for code blocks")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CapsuleBase(ForgeModel):
    """Base fields shared across capsule schemas."""

    content: str = Field(
        min_length=1,
        max_length=100000,
        description="The actual knowledge content",
    )
    type: CapsuleType = Field(
        default=CapsuleType.KNOWLEDGE,
        description="Type of capsule",
    )
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Optional title",
    )
    summary: str | None = Field(
        default=None,
        max_length=2000,
        description="Brief summary of content",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Tags for categorization",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible properties",
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Normalize and validate tags."""
        return [tag.lower().strip() for tag in v if tag.strip()][:20]


# SHA-256 hash pattern: 64 lowercase hex characters
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class CapsuleCreate(CapsuleBase):
    """Schema for creating a new capsule."""

    parent_id: str | None = Field(
        default=None,
        description="Parent capsule ID for symbolic inheritance",
    )
    evolution_reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason for deriving from parent",
    )


class CapsuleUpdate(ForgeModel):
    """Schema for updating an existing capsule."""

    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=100000,
    )
    title: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class Capsule(CapsuleBase, TimestampMixin):
    """Complete capsule schema for API responses."""

    id: str = Field(description="Unique identifier")
    version: str = Field(default="1.0.0", description="Semantic version")
    owner_id: str = Field(description="Owner user ID")
    trust_level: TrustLevel = Field(
        default=TrustLevel.STANDARD,
        description="Trust level for this capsule",
    )
    parent_id: str | None = Field(
        default=None,
        description="Parent capsule ID",
    )
    is_archived: bool = Field(default=False, description="Archive status")
    view_count: int = Field(default=0, ge=0, description="View counter")
    fork_count: int = Field(default=0, ge=0, description="Fork counter")


class CapsuleInDB(Capsule):
    """Capsule with database-specific fields."""

    # SECURITY FIX (Audit 4 - L4): Validate embedding dimensions and value ranges
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding for semantic search (1536 dims for OpenAI)",
    )

    # ═══════════════════════════════════════════════════════════════
    # INTEGRITY FIELDS (Phase 1: Content Hash)
    # ═══════════════════════════════════════════════════════════════
    content_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of content for integrity verification",
    )
    integrity_status: IntegrityStatus = Field(
        default=IntegrityStatus.UNVERIFIED,
        description="Current integrity verification status",
    )
    integrity_verified_at: datetime | None = Field(
        default=None,
        description="Timestamp of last integrity verification",
    )

    # ═══════════════════════════════════════════════════════════════
    # SIGNATURE FIELDS (Phase 2: Digital Signatures) - Placeholder
    # ═══════════════════════════════════════════════════════════════
    signature: str | None = Field(
        default=None,
        description="Ed25519 signature of content_hash (base64)",
    )
    signature_algorithm: str = Field(
        default="Ed25519",
        description="Signature algorithm used",
    )
    signed_at: datetime | None = Field(
        default=None,
        description="Timestamp when capsule was signed",
    )
    signed_by: str | None = Field(
        default=None,
        description="User ID who signed the capsule",
    )

    # ═══════════════════════════════════════════════════════════════
    # MERKLE TREE FIELDS (Phase 3: Lineage Verification) - Placeholder
    # ═══════════════════════════════════════════════════════════════
    parent_content_hash: str | None = Field(
        default=None,
        description="Content hash of parent at fork time (immutable snapshot)",
    )
    merkle_root: str | None = Field(
        default=None,
        description="Hash chain root: hash(content_hash + parent_merkle_root)",
    )

    @field_validator("content_hash", mode="after")
    @classmethod
    def validate_content_hash(cls, v: str | None) -> str | None:
        """Validate content_hash is a valid SHA-256 hash (64 hex chars)."""
        if v is None:
            return v
        if not SHA256_PATTERN.match(v):
            raise ValueError("content_hash must be a valid SHA-256 hash (64 hex chars)")
        return v

    @field_validator("merkle_root", mode="after")
    @classmethod
    def validate_merkle_root(cls, v: str | None) -> str | None:
        """Validate merkle_root is a valid SHA-256 hash."""
        if v is None:
            return v
        if not SHA256_PATTERN.match(v):
            raise ValueError("merkle_root must be a valid SHA-256 hash (64 hex chars)")
        return v

    @field_validator("parent_content_hash", mode="after")
    @classmethod
    def validate_parent_content_hash(cls, v: str | None) -> str | None:
        """Validate parent_content_hash is a valid SHA-256 hash."""
        if v is None:
            return v
        if not SHA256_PATTERN.match(v):
            raise ValueError("parent_content_hash must be a valid SHA-256 hash (64 hex chars)")
        return v

    @field_validator("embedding", mode="after")
    @classmethod
    def validate_embedding(cls, v: list[float] | None) -> list[float] | None:
        """Validate embedding dimensions and value ranges."""
        if v is None:
            return v
        # OpenAI embeddings are 1536 dimensions, allow some flexibility
        valid_dimensions = {384, 768, 1024, 1536, 3072}
        if len(v) not in valid_dimensions:
            raise ValueError(
                f"Embedding must have valid dimensions ({valid_dimensions}), "
                f"got {len(v)}"
            )
        # Check value ranges (embeddings should be normalized, typically -1 to 1)
        for i, val in enumerate(v):
            if not isinstance(val, int | float):
                raise ValueError(f"Embedding value at index {i} must be numeric")
            if val < -10.0 or val > 10.0:
                raise ValueError(
                    f"Embedding value at index {i} is out of valid range [-10, 10]: {val}"
                )
        return v


class LineageNode(ForgeModel):
    """A node in the lineage tree."""

    id: str
    version: str
    title: str | None = None
    type: CapsuleType
    created_at: datetime
    trust_level: TrustLevel
    depth: int = Field(
        ge=0,
        description="Distance from the queried capsule (0 = self)",
    )


class DerivedFromRelation(ForgeModel):
    """Metadata about a DERIVED_FROM relationship."""

    parent_id: str
    child_id: str
    reason: str | None = None
    timestamp: datetime
    changes: dict[str, Any] | None = None


class CapsuleWithLineage(Capsule):
    """Capsule with full lineage information."""

    lineage: list[LineageNode] = Field(
        default_factory=list,
        description="Ancestry chain (oldest first)",
    )
    children: list[LineageNode] = Field(
        default_factory=list,
        description="Direct child capsules",
    )
    lineage_depth: int = Field(
        default=0,
        ge=0,
        description="Total depth of ancestry",
    )


class CapsuleSearchResult(ForgeModel):
    """Result from semantic search."""

    capsule: Capsule
    score: float = Field(ge=0.0, le=1.0, description="Similarity score")
    highlights: list[str] = Field(
        default_factory=list,
        description="Matching text snippets",
    )


class CapsuleFork(ForgeModel):
    """Request to fork (derive from) a capsule."""

    parent_id: str = Field(description="Capsule to fork from")
    content: str | None = Field(
        default=None,
        description="New content (if different from parent)",
    )
    evolution_reason: str = Field(
        min_length=1,
        max_length=1000,
        description="Reason for forking",
    )
    inherit_metadata: bool = Field(
        default=True,
        description="Copy parent metadata",
    )


class CapsuleStats(ForgeModel):
    """Statistics about capsules."""

    total_count: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_trust_level: dict[str, int] = Field(default_factory=dict)
    average_lineage_depth: float = 0.0
    total_views: int = 0
    total_forks: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRITY VERIFICATION MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class IntegrityReport(ForgeModel):
    """Comprehensive integrity verification report for a capsule."""

    capsule_id: str = Field(description="Capsule ID that was verified")
    content_hash_valid: bool = Field(
        description="Whether content hash matches computed hash"
    )
    content_hash_expected: str | None = Field(
        default=None,
        description="Expected SHA-256 hash (stored)",
    )
    content_hash_computed: str | None = Field(
        default=None,
        description="Computed SHA-256 hash (from content)",
    )
    signature_valid: bool | None = Field(
        default=None,
        description="Whether signature is valid (None if not signed)",
    )
    merkle_chain_valid: bool | None = Field(
        default=None,
        description="Whether Merkle chain is valid (None if no lineage)",
    )
    overall_status: IntegrityStatus = Field(
        description="Overall integrity status",
    )
    checked_at: datetime = Field(
        description="Timestamp when verification was performed",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional verification details",
    )


class LineageIntegrityReport(ForgeModel):
    """Integrity report for an entire capsule lineage chain."""

    capsule_id: str = Field(description="Leaf capsule ID")
    chain_length: int = Field(
        ge=0,
        description="Number of capsules in the lineage chain",
    )
    all_hashes_valid: bool = Field(
        description="Whether all content hashes in chain are valid",
    )
    merkle_chain_valid: bool = Field(
        description="Whether Merkle tree chain is unbroken",
    )
    broken_at: str | None = Field(
        default=None,
        description="Capsule ID where chain integrity breaks (if any)",
    )
    verified_capsules: list[str] = Field(
        default_factory=list,
        description="List of capsule IDs that passed verification",
    )
    failed_capsules: list[str] = Field(
        default_factory=list,
        description="List of capsule IDs that failed verification",
    )
    checked_at: datetime = Field(
        description="Timestamp when verification was performed",
    )
