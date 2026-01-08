"""
Temporal Graph Models

Track how knowledge and trust evolve over time with version history,
snapshots, and reconstruction capabilities.
"""

import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import Field, computed_field

from forge.models.base import ForgeModel, TimestampMixin, TrustLevel, generate_id


class ChangeType(str, Enum):
    """Types of changes that create versions."""

    CREATE = "create"          # Initial creation
    UPDATE = "update"          # Content modification
    FORK = "fork"              # Derived from another capsule
    MERGE = "merge"            # Merged from multiple sources
    RESTORE = "restore"        # Restored from backup/archive
    MIGRATION = "migration"    # System migration


class SnapshotType(str, Enum):
    """Types of version snapshots."""

    FULL = "full"              # Complete content snapshot
    DIFF = "diff"              # Delta from previous version
    REFERENCE = "reference"    # Pointer to another snapshot


class TrustChangeType(str, Enum):
    """Classification of trust changes for storage optimization."""

    ESSENTIAL = "essential"    # Must be preserved in full
    DERIVED = "derived"        # Can be reconstructed from context


class TimeGranularity(str, Enum):
    """Granularity for temporal queries."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# ═══════════════════════════════════════════════════════════════
# CAPSULE VERSIONING
# ═══════════════════════════════════════════════════════════════


class VersionDiff(ForgeModel):
    """Represents the difference between two versions."""

    added_lines: list[str] = Field(default_factory=list)
    removed_lines: list[str] = Field(default_factory=list)
    modified_sections: list[dict[str, Any]] = Field(default_factory=list)
    metadata_changes: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.added_lines or self.removed_lines or self.modified_sections)


class CapsuleVersionBase(ForgeModel):
    """Base fields for capsule versions."""

    capsule_id: str = Field(description="ID of the capsule")
    version_number: str = Field(description="Semantic version (e.g., 1.0.0)")
    change_type: ChangeType
    created_by: str = Field(description="User who created this version")


class CapsuleVersionCreate(CapsuleVersionBase):
    """Schema for creating a version."""

    content: str | None = Field(default=None, description="Content for full snapshot")
    diff: VersionDiff | None = Field(default=None, description="Diff for delta snapshot")
    change_summary: str | None = Field(default=None, max_length=500)


class CapsuleVersion(CapsuleVersionBase, TimestampMixin):
    """Complete capsule version record."""

    id: str = Field(default_factory=generate_id)
    snapshot_type: SnapshotType = Field(default=SnapshotType.FULL)

    # Content storage
    content_snapshot: str | None = Field(
        default=None,
        description="Full content (for FULL snapshots)",
    )
    content_hash: str = Field(description="SHA-256 hash of content")
    diff_from_previous: VersionDiff | None = Field(
        default=None,
        description="Delta (for DIFF snapshots)",
    )

    # Lineage
    parent_version_id: str | None = Field(
        default=None,
        description="Previous version in chain",
    )
    trust_at_version: int = Field(
        ge=0,
        le=100,
        description="Trust level when version was created",
    )

    # Metadata
    change_summary: str | None = None
    tags_at_version: list[str] = Field(default_factory=list)
    metadata_at_version: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()


class CapsuleVersionWithContent(CapsuleVersion):
    """Version with reconstructed content."""

    reconstructed_content: str | None = Field(
        default=None,
        description="Content reconstructed from diffs if needed",
    )


class VersionHistory(ForgeModel):
    """Complete version history for a capsule."""

    capsule_id: str
    current_version: str
    total_versions: int = Field(ge=0)
    versions: list[CapsuleVersion] = Field(default_factory=list)
    first_created: datetime | None = None
    last_modified: datetime | None = None
    total_changes: int = Field(ge=0)
    contributors: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# TRUST SNAPSHOTS
# ═══════════════════════════════════════════════════════════════


class TrustSnapshotBase(ForgeModel):
    """Base fields for trust snapshots."""

    entity_id: str = Field(description="User or Capsule ID")
    entity_type: str = Field(description="'User' or 'Capsule'")
    trust_value: int = Field(ge=0, le=100)


class TrustSnapshotCreate(TrustSnapshotBase):
    """Schema for creating a trust snapshot."""

    reason: str | None = None
    adjusted_by: str | None = None
    evidence: dict[str, Any] | None = None
    source_event_id: str | None = None


class TrustSnapshot(TrustSnapshotBase, TimestampMixin):
    """
    Complete trust snapshot record.

    Implements the essential/derived classification for storage optimization.
    """

    id: str = Field(default_factory=generate_id)
    change_type: TrustChangeType = Field(default=TrustChangeType.ESSENTIAL)

    # Essential change details (preserved in full)
    reason: str | None = Field(default=None, max_length=500)
    adjusted_by: str | None = None
    evidence: dict[str, Any] | None = None

    # Derived change references (minimal storage)
    source_event_id: str | None = Field(
        default=None,
        description="Event that triggered this change",
    )
    reconstruction_hint: str | None = Field(
        default=None,
        description="Hint for LLM reconstruction (e.g., 'cascade_from:lineage_tracker')",
    )

    # Change magnitude
    previous_value: int | None = Field(default=None, ge=0, le=100)
    delta: int | None = None

    @computed_field
    @property
    def is_significant(self) -> bool:
        """Check if this is a significant change (>5 points)."""
        if self.delta is not None:
            return abs(self.delta) > 5
        return True


class TrustTimeline(ForgeModel):
    """Trust evolution over time."""

    entity_id: str
    entity_type: str
    snapshots: list[TrustSnapshot] = Field(default_factory=list)
    start_time: datetime
    end_time: datetime
    granularity: TimeGranularity = TimeGranularity.DAY

    # Aggregated stats
    min_trust: int = Field(ge=0, le=100)
    max_trust: int = Field(ge=0, le=100)
    avg_trust: float = Field(ge=0.0, le=100.0)
    volatility: float = Field(
        ge=0.0,
        description="Standard deviation of trust values",
    )
    total_adjustments: int = Field(ge=0)


# ═══════════════════════════════════════════════════════════════
# TRUST SNAPSHOT COMPRESSION
# ═══════════════════════════════════════════════════════════════


class TrustSnapshotCompressor:
    """
    Compresses trust snapshots by classifying as essential or derived.

    Essential changes (preserved in full):
    - Manual adjustments by admins
    - Role changes
    - Anomaly detections
    - Governance actions
    - Initial assignments

    Derived changes (minimal storage):
    - Cascade effects from overlays
    - Routine decay
    - Automatic adjustments
    """

    ESSENTIAL_REASONS = frozenset({
        "manual_adjustment",
        "admin_adjustment",
        "role_change",
        "anomaly_detected",
        "governance_action",
        "initial_assignment",
        "security_incident",
        "verification_complete",
        "quarantine",
        "restore",
    })

    @classmethod
    def classify(cls, reason: str | None) -> TrustChangeType:
        """Classify a trust change as essential or derived."""
        if reason is None:
            return TrustChangeType.DERIVED
        reason_lower = reason.lower().replace(" ", "_")
        for essential in cls.ESSENTIAL_REASONS:
            if essential in reason_lower:
                return TrustChangeType.ESSENTIAL
        return TrustChangeType.DERIVED

    @classmethod
    def compress(cls, snapshot: TrustSnapshot) -> TrustSnapshot:
        """Compress a snapshot based on its classification."""
        snapshot.change_type = cls.classify(snapshot.reason)

        if snapshot.change_type == TrustChangeType.DERIVED:
            # Keep minimal info for derived changes
            snapshot.evidence = None
            if not snapshot.reconstruction_hint and snapshot.source_event_id:
                snapshot.reconstruction_hint = f"event:{snapshot.source_event_id}"

        return snapshot

    @classmethod
    def estimate_storage(cls, snapshots: list[TrustSnapshot]) -> dict[str, int]:
        """Estimate storage savings from compression."""
        essential_count = sum(1 for s in snapshots if s.change_type == TrustChangeType.ESSENTIAL)
        derived_count = len(snapshots) - essential_count

        # Rough estimates: essential ~500 bytes, derived ~100 bytes
        uncompressed = len(snapshots) * 500
        compressed = (essential_count * 500) + (derived_count * 100)

        return {
            "total_snapshots": len(snapshots),
            "essential_count": essential_count,
            "derived_count": derived_count,
            "uncompressed_bytes": uncompressed,
            "compressed_bytes": compressed,
            "savings_percent": round((1 - compressed / uncompressed) * 100, 1) if uncompressed > 0 else 0,
        }


# ═══════════════════════════════════════════════════════════════
# VERSIONING POLICY
# ═══════════════════════════════════════════════════════════════


class VersioningPolicy(ForgeModel):
    """
    Policy for when to create full snapshots vs diffs.

    Implements hybrid versioning with smart compaction.
    """

    # Full snapshot triggers
    snapshot_every_n_changes: int = Field(
        default=10,
        ge=1,
        description="Create full snapshot every N changes",
    )
    snapshot_for_trust_level: int = Field(
        default=TrustLevel.TRUSTED.value,
        ge=0,
        le=100,
        description="Always snapshot capsules at or above this trust",
    )

    # Compaction settings
    compact_after_days: int = Field(
        default=30,
        ge=1,
        description="Compact old diffs into snapshots after N days",
    )
    keep_snapshots_for_days: int = Field(
        default=365,
        ge=1,
        description="Retain full snapshots for N days",
    )

    # Size limits
    max_diff_chain_length: int = Field(
        default=10,
        ge=1,
        description="Max consecutive diffs before forcing snapshot",
    )
    max_diff_size_bytes: int = Field(
        default=10000,
        ge=100,
        description="Force snapshot if diff exceeds this size",
    )

    def should_full_snapshot(
        self,
        change_number: int,
        trust_level: int,
        is_major_version: bool,
        diff_chain_length: int,
        diff_size: int | None = None,
    ) -> bool:
        """Determine if a full snapshot should be created."""
        return (
            change_number == 1 or                                    # Initial creation
            change_number % self.snapshot_every_n_changes == 0 or    # Periodic
            trust_level >= self.snapshot_for_trust_level or          # High trust
            is_major_version or                                      # Major version bump
            diff_chain_length >= self.max_diff_chain_length or       # Chain too long
            (diff_size is not None and diff_size > self.max_diff_size_bytes)  # Diff too large
        )

    def should_compact(self, version: CapsuleVersion) -> bool:
        """Determine if an old diff should be compacted."""
        if version.snapshot_type != SnapshotType.DIFF:
            return False
        age = datetime.utcnow() - version.created_at
        return age > timedelta(days=self.compact_after_days)


# ═══════════════════════════════════════════════════════════════
# GRAPH SNAPSHOTS
# ═══════════════════════════════════════════════════════════════


class GraphSnapshot(ForgeModel, TimestampMixin):
    """
    Point-in-time snapshot of graph metrics.

    Used for tracking overall graph evolution.
    """

    id: str = Field(default_factory=generate_id)

    # Size metrics
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_type: dict[str, int] = Field(default_factory=dict)

    # Structure metrics
    density: float = Field(ge=0.0, le=1.0)
    avg_degree: float = Field(ge=0.0)
    connected_components: int = Field(ge=0)

    # Trust metrics
    avg_trust: float = Field(ge=0.0, le=100.0)
    trust_distribution: dict[str, int] = Field(default_factory=dict)

    # Community metrics
    community_count: int = Field(ge=0)
    modularity: float | None = None

    # Top entities
    top_capsules_by_pagerank: list[str] = Field(
        default_factory=list,
        description="Top 10 capsule IDs by PageRank",
    )
    top_users_by_influence: list[str] = Field(
        default_factory=list,
        description="Top 10 user IDs by influence",
    )

    # Anomalies
    active_anomalies: int = Field(ge=0)
    anomaly_types: dict[str, int] = Field(default_factory=dict)


class GraphEvolution(ForgeModel):
    """Track how the graph changes over time."""

    snapshots: list[GraphSnapshot] = Field(default_factory=list)
    start_time: datetime
    end_time: datetime
    granularity: TimeGranularity = TimeGranularity.DAY

    # Trends
    node_growth_rate: float = Field(description="Nodes added per period")
    edge_growth_rate: float = Field(description="Edges added per period")
    trust_trend: float = Field(description="Change in avg trust per period")


# ═══════════════════════════════════════════════════════════════
# TEMPORAL QUERIES
# ═══════════════════════════════════════════════════════════════


class TemporalQuery(ForgeModel):
    """Base query for temporal data."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    granularity: TimeGranularity = TimeGranularity.DAY


class VersionHistoryQuery(TemporalQuery):
    """Query for capsule version history."""

    capsule_id: str
    include_content: bool = Field(
        default=False,
        description="Include full content in response",
    )
    change_types: list[ChangeType] | None = None
    created_by: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class TrustTimelineQuery(TemporalQuery):
    """Query for trust evolution."""

    entity_id: str
    entity_type: str = Field(pattern="^(User|Capsule)$")
    include_derived: bool = Field(
        default=True,
        description="Include derived (compressed) snapshots",
    )
    min_delta: int | None = Field(
        default=None,
        ge=1,
        description="Only include changes with at least this delta",
    )


class CapsuleAtTimeQuery(ForgeModel):
    """Query to get capsule state at a specific time."""

    capsule_id: str
    timestamp: datetime
    include_trust: bool = Field(default=True)
    include_relationships: bool = Field(default=False)


class GraphSnapshotQuery(TemporalQuery):
    """Query for graph snapshots."""

    include_top_entities: bool = Field(default=True)
    include_anomalies: bool = Field(default=True)
    limit: int = Field(default=30, ge=1, le=365)


# ═══════════════════════════════════════════════════════════════
# VERSION COMPARISON
# ═══════════════════════════════════════════════════════════════


class VersionComparison(ForgeModel):
    """Comparison between two versions."""

    capsule_id: str
    version_a_id: str
    version_b_id: str
    version_a_number: str
    version_b_number: str
    diff: VersionDiff
    time_between: timedelta | None = None
    changes_between: int = Field(ge=0, description="Number of intermediate versions")
    trust_change: int = Field(description="Change in trust level")
    contributors: list[str] = Field(default_factory=list)
