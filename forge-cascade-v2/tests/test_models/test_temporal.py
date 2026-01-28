"""
Temporal Graph Model Tests for Forge Cascade V2

Comprehensive tests for temporal graph models including:
- Version history and diff models
- Trust snapshot models
- Snapshot compression
- Versioning policy
- Graph evolution models
- Temporal query models
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from forge.models.base import TrustLevel
from forge.models.temporal import (
    CapsuleAtTimeQuery,
    CapsuleVersion,
    CapsuleVersionBase,
    CapsuleVersionCreate,
    CapsuleVersionWithContent,
    ChangeType,
    GraphEvolution,
    GraphSnapshot,
    GraphSnapshotQuery,
    SnapshotType,
    TemporalQuery,
    TimeGranularity,
    TrustChangeType,
    TrustSnapshot,
    TrustSnapshotBase,
    TrustSnapshotCompressor,
    TrustSnapshotCreate,
    TrustTimeline,
    TrustTimelineQuery,
    VersionComparison,
    VersionDiff,
    VersionHistory,
    VersionHistoryQuery,
    VersioningPolicy,
)


# =============================================================================
# ChangeType Enum Tests
# =============================================================================


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_change_type_values(self):
        """ChangeType has expected values."""
        assert ChangeType.CREATE.value == "create"
        assert ChangeType.UPDATE.value == "update"
        assert ChangeType.FORK.value == "fork"
        assert ChangeType.MERGE.value == "merge"
        assert ChangeType.RESTORE.value == "restore"
        assert ChangeType.MIGRATION.value == "migration"

    def test_change_type_count(self):
        """ChangeType has exactly 6 members."""
        assert len(ChangeType) == 6


# =============================================================================
# SnapshotType Enum Tests
# =============================================================================


class TestSnapshotType:
    """Tests for SnapshotType enum."""

    def test_snapshot_type_values(self):
        """SnapshotType has expected values."""
        assert SnapshotType.FULL.value == "full"
        assert SnapshotType.DIFF.value == "diff"
        assert SnapshotType.REFERENCE.value == "reference"

    def test_snapshot_type_count(self):
        """SnapshotType has exactly 3 members."""
        assert len(SnapshotType) == 3


# =============================================================================
# TrustChangeType Enum Tests
# =============================================================================


class TestTrustChangeType:
    """Tests for TrustChangeType enum."""

    def test_trust_change_type_values(self):
        """TrustChangeType has expected values."""
        assert TrustChangeType.ESSENTIAL.value == "essential"
        assert TrustChangeType.DERIVED.value == "derived"

    def test_trust_change_type_count(self):
        """TrustChangeType has exactly 2 members."""
        assert len(TrustChangeType) == 2


# =============================================================================
# TimeGranularity Enum Tests
# =============================================================================


class TestTimeGranularity:
    """Tests for TimeGranularity enum."""

    def test_time_granularity_values(self):
        """TimeGranularity has expected values."""
        assert TimeGranularity.HOUR.value == "hour"
        assert TimeGranularity.DAY.value == "day"
        assert TimeGranularity.WEEK.value == "week"
        assert TimeGranularity.MONTH.value == "month"

    def test_time_granularity_count(self):
        """TimeGranularity has exactly 4 members."""
        assert len(TimeGranularity) == 4


# =============================================================================
# VersionDiff Tests
# =============================================================================


class TestVersionDiff:
    """Tests for VersionDiff model."""

    def test_valid_version_diff(self):
        """Valid version diff creates model."""
        diff = VersionDiff(
            added_lines=["+ new line 1", "+ new line 2"],
            removed_lines=["- old line"],
            modified_sections=[{"section": "intro", "changes": "updated"}],
            metadata_changes={"title": "New Title"},
            summary="Updated intro and title",
        )
        assert len(diff.added_lines) == 2
        assert len(diff.removed_lines) == 1
        assert diff.summary == "Updated intro and title"

    def test_version_diff_defaults(self):
        """VersionDiff has sensible defaults."""
        diff = VersionDiff()
        assert diff.added_lines == []
        assert diff.removed_lines == []
        assert diff.modified_sections == []
        assert diff.metadata_changes == {}
        assert diff.summary is None

    def test_is_empty_property_true(self):
        """is_empty returns True for empty diff."""
        diff = VersionDiff()
        assert diff.is_empty is True

    def test_is_empty_property_false_added(self):
        """is_empty returns False when lines added."""
        diff = VersionDiff(added_lines=["new line"])
        assert diff.is_empty is False

    def test_is_empty_property_false_removed(self):
        """is_empty returns False when lines removed."""
        diff = VersionDiff(removed_lines=["old line"])
        assert diff.is_empty is False

    def test_is_empty_property_false_modified(self):
        """is_empty returns False when sections modified."""
        diff = VersionDiff(modified_sections=[{"section": "test"}])
        assert diff.is_empty is False


# =============================================================================
# CapsuleVersionBase Tests
# =============================================================================


class TestCapsuleVersionBase:
    """Tests for CapsuleVersionBase model."""

    def test_valid_capsule_version_base(self):
        """Valid capsule version base creates model."""
        version = CapsuleVersionBase(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
        )
        assert version.capsule_id == "cap-123"
        assert version.version_number == "1.0.0"
        assert version.change_type == ChangeType.CREATE


# =============================================================================
# CapsuleVersionCreate Tests
# =============================================================================


class TestCapsuleVersionCreate:
    """Tests for CapsuleVersionCreate model."""

    def test_valid_capsule_version_create(self):
        """Valid capsule version create creates model."""
        version = CapsuleVersionCreate(
            capsule_id="cap-123",
            version_number="1.1.0",
            change_type=ChangeType.UPDATE,
            created_by="user-456",
            content="Updated content",
            change_summary="Fixed typos",
        )
        assert version.content == "Updated content"
        assert version.change_summary == "Fixed typos"

    def test_capsule_version_create_defaults(self):
        """CapsuleVersionCreate has sensible defaults."""
        version = CapsuleVersionCreate(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
        )
        assert version.content is None
        assert version.diff is None
        assert version.change_summary is None

    def test_capsule_version_create_with_diff(self):
        """CapsuleVersionCreate can include diff."""
        diff = VersionDiff(added_lines=["new line"])
        version = CapsuleVersionCreate(
            capsule_id="cap-123",
            version_number="1.1.0",
            change_type=ChangeType.UPDATE,
            created_by="user-456",
            diff=diff,
        )
        assert version.diff is not None
        assert len(version.diff.added_lines) == 1

    def test_change_summary_max_length(self):
        """Change summary has max length of 500."""
        with pytest.raises(ValidationError):
            CapsuleVersionCreate(
                capsule_id="cap-123",
                version_number="1.0.0",
                change_type=ChangeType.CREATE,
                created_by="user-456",
                change_summary="S" * 501,
            )


# =============================================================================
# CapsuleVersion Tests
# =============================================================================


class TestCapsuleVersion:
    """Tests for CapsuleVersion model."""

    def test_valid_capsule_version(self):
        """Valid capsule version creates model."""
        version = CapsuleVersion(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
            content_hash="abc123hash",
            trust_at_version=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert version.capsule_id == "cap-123"
        assert version.trust_at_version == 60

    def test_capsule_version_defaults(self):
        """CapsuleVersion has sensible defaults."""
        version = CapsuleVersion(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert version.id is not None
        assert version.snapshot_type == SnapshotType.FULL
        assert version.content_snapshot is None
        assert version.diff_from_previous is None
        assert version.parent_version_id is None
        assert version.change_summary is None
        assert version.tags_at_version == []
        assert version.metadata_at_version == {}

    def test_trust_at_version_bounds(self):
        """Trust at version must be 0-100."""
        with pytest.raises(ValidationError):
            CapsuleVersion(
                capsule_id="cap-123",
                version_number="1.0.0",
                change_type=ChangeType.CREATE,
                created_by="user-456",
                content_hash="abc123",
                trust_at_version=-1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        with pytest.raises(ValidationError):
            CapsuleVersion(
                capsule_id="cap-123",
                version_number="1.0.0",
                change_type=ChangeType.CREATE,
                created_by="user-456",
                content_hash="abc123",
                trust_at_version=101,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_compute_hash(self):
        """compute_hash generates SHA-256 hash."""
        content = "Test content"
        hash1 = CapsuleVersion.compute_hash(content)
        hash2 = CapsuleVersion.compute_hash(content)

        # Same content produces same hash
        assert hash1 == hash2
        # Hash is 64 chars (SHA-256 hex)
        assert len(hash1) == 64

        # Different content produces different hash
        hash3 = CapsuleVersion.compute_hash("Different content")
        assert hash1 != hash3


# =============================================================================
# CapsuleVersionWithContent Tests
# =============================================================================


class TestCapsuleVersionWithContent:
    """Tests for CapsuleVersionWithContent model."""

    def test_valid_capsule_version_with_content(self):
        """Valid capsule version with content creates model."""
        version = CapsuleVersionWithContent(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            reconstructed_content="Full content here",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert version.reconstructed_content == "Full content here"

    def test_reconstructed_content_default(self):
        """Reconstructed content defaults to None."""
        version = CapsuleVersionWithContent(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert version.reconstructed_content is None


# =============================================================================
# VersionHistory Tests
# =============================================================================


class TestVersionHistory:
    """Tests for VersionHistory model."""

    def test_valid_version_history(self):
        """Valid version history creates model."""
        history = VersionHistory(
            capsule_id="cap-123",
            current_version="2.1.0",
            total_versions=10,
            total_changes=15,
            contributors=["user-1", "user-2"],
        )
        assert history.capsule_id == "cap-123"
        assert history.total_versions == 10

    def test_version_history_defaults(self):
        """VersionHistory has sensible defaults."""
        history = VersionHistory(
            capsule_id="cap-123",
            current_version="1.0.0",
            total_versions=1,
            total_changes=0,
        )
        assert history.versions == []
        assert history.first_created is None
        assert history.last_modified is None
        assert history.contributors == []

    def test_total_versions_bounds(self):
        """Total versions must be >= 0."""
        with pytest.raises(ValidationError):
            VersionHistory(
                capsule_id="cap-123",
                current_version="1.0.0",
                total_versions=-1,
                total_changes=0,
            )

    def test_total_changes_bounds(self):
        """Total changes must be >= 0."""
        with pytest.raises(ValidationError):
            VersionHistory(
                capsule_id="cap-123",
                current_version="1.0.0",
                total_versions=1,
                total_changes=-1,
            )


# =============================================================================
# TrustSnapshotBase Tests
# =============================================================================


class TestTrustSnapshotBase:
    """Tests for TrustSnapshotBase model."""

    def test_valid_trust_snapshot_base(self):
        """Valid trust snapshot base creates model."""
        snapshot = TrustSnapshotBase(
            entity_id="user-123",
            entity_type="User",
            trust_value=75,
        )
        assert snapshot.entity_id == "user-123"
        assert snapshot.trust_value == 75

    def test_trust_value_bounds(self):
        """Trust value must be 0-100."""
        TrustSnapshotBase(entity_id="u1", entity_type="User", trust_value=0)
        TrustSnapshotBase(entity_id="u1", entity_type="User", trust_value=100)

        with pytest.raises(ValidationError):
            TrustSnapshotBase(entity_id="u1", entity_type="User", trust_value=-1)
        with pytest.raises(ValidationError):
            TrustSnapshotBase(entity_id="u1", entity_type="User", trust_value=101)


# =============================================================================
# TrustSnapshotCreate Tests
# =============================================================================


class TestTrustSnapshotCreate:
    """Tests for TrustSnapshotCreate model."""

    def test_valid_trust_snapshot_create(self):
        """Valid trust snapshot create creates model."""
        snapshot = TrustSnapshotCreate(
            entity_id="user-123",
            entity_type="User",
            trust_value=80,
            reason="Verified identity",
            adjusted_by="admin-1",
        )
        assert snapshot.reason == "Verified identity"
        assert snapshot.adjusted_by == "admin-1"

    def test_trust_snapshot_create_defaults(self):
        """TrustSnapshotCreate has sensible defaults."""
        snapshot = TrustSnapshotCreate(
            entity_id="user-123",
            entity_type="User",
            trust_value=60,
        )
        assert snapshot.reason is None
        assert snapshot.adjusted_by is None
        assert snapshot.evidence is None
        assert snapshot.source_event_id is None


# =============================================================================
# TrustSnapshot Tests
# =============================================================================


class TestTrustSnapshot:
    """Tests for TrustSnapshot model."""

    def test_valid_trust_snapshot(self):
        """Valid trust snapshot creates model."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=75,
            reason="Good behavior",
            previous_value=70,
            delta=5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.trust_value == 75
        assert snapshot.delta == 5

    def test_trust_snapshot_defaults(self):
        """TrustSnapshot has sensible defaults."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.id is not None
        assert snapshot.change_type == TrustChangeType.ESSENTIAL
        assert snapshot.reason is None
        assert snapshot.adjusted_by is None
        assert snapshot.evidence is None
        assert snapshot.source_event_id is None
        assert snapshot.reconstruction_hint is None
        assert snapshot.previous_value is None
        assert snapshot.delta is None

    def test_reason_max_length(self):
        """Reason has max length of 500."""
        with pytest.raises(ValidationError):
            TrustSnapshot(
                entity_id="user-123",
                entity_type="User",
                trust_value=60,
                reason="R" * 501,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_previous_value_bounds(self):
        """Previous value must be 0-100."""
        with pytest.raises(ValidationError):
            TrustSnapshot(
                entity_id="user-123",
                entity_type="User",
                trust_value=60,
                previous_value=-1,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        with pytest.raises(ValidationError):
            TrustSnapshot(
                entity_id="user-123",
                entity_type="User",
                trust_value=60,
                previous_value=101,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_is_significant_property_large_delta(self):
        """is_significant returns True for delta > 5."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=70,
            delta=10,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.is_significant is True

    def test_is_significant_property_small_delta(self):
        """is_significant returns False for delta <= 5."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=65,
            delta=5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.is_significant is False

    def test_is_significant_property_no_delta(self):
        """is_significant returns True when no delta."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.is_significant is True

    def test_is_significant_negative_delta(self):
        """is_significant handles negative delta."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=50,
            delta=-10,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.is_significant is True  # abs(-10) > 5


# =============================================================================
# TrustTimeline Tests
# =============================================================================


class TestTrustTimeline:
    """Tests for TrustTimeline model."""

    def test_valid_trust_timeline(self):
        """Valid trust timeline creates model."""
        timeline = TrustTimeline(
            entity_id="user-123",
            entity_type="User",
            start_time=datetime.now(UTC) - timedelta(days=30),
            end_time=datetime.now(UTC),
            min_trust=40,
            max_trust=80,
            avg_trust=60.5,
            volatility=5.2,
            total_adjustments=10,
        )
        assert timeline.entity_id == "user-123"
        assert timeline.avg_trust == 60.5

    def test_trust_timeline_defaults(self):
        """TrustTimeline has sensible defaults."""
        timeline = TrustTimeline(
            entity_id="user-123",
            entity_type="User",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            min_trust=60,
            max_trust=60,
            avg_trust=60.0,
            volatility=0.0,
            total_adjustments=0,
        )
        assert timeline.snapshots == []
        assert timeline.granularity == TimeGranularity.DAY

    def test_trust_bounds(self):
        """Trust values must be 0-100."""
        with pytest.raises(ValidationError):
            TrustTimeline(
                entity_id="u1",
                entity_type="User",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                min_trust=-1,
                max_trust=100,
                avg_trust=50.0,
                volatility=0.0,
                total_adjustments=0,
            )
        with pytest.raises(ValidationError):
            TrustTimeline(
                entity_id="u1",
                entity_type="User",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                min_trust=0,
                max_trust=101,
                avg_trust=50.0,
                volatility=0.0,
                total_adjustments=0,
            )
        with pytest.raises(ValidationError):
            TrustTimeline(
                entity_id="u1",
                entity_type="User",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                min_trust=0,
                max_trust=100,
                avg_trust=101.0,
                volatility=0.0,
                total_adjustments=0,
            )

    def test_volatility_bounds(self):
        """Volatility must be >= 0."""
        with pytest.raises(ValidationError):
            TrustTimeline(
                entity_id="u1",
                entity_type="User",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                min_trust=0,
                max_trust=100,
                avg_trust=50.0,
                volatility=-1.0,
                total_adjustments=0,
            )

    def test_total_adjustments_bounds(self):
        """Total adjustments must be >= 0."""
        with pytest.raises(ValidationError):
            TrustTimeline(
                entity_id="u1",
                entity_type="User",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                min_trust=0,
                max_trust=100,
                avg_trust=50.0,
                volatility=0.0,
                total_adjustments=-1,
            )


# =============================================================================
# TrustSnapshotCompressor Tests
# =============================================================================


class TestTrustSnapshotCompressor:
    """Tests for TrustSnapshotCompressor class."""

    def test_classify_essential_reasons(self):
        """Essential reasons are classified correctly."""
        assert TrustSnapshotCompressor.classify("manual_adjustment") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("admin_adjustment") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("role_change") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("anomaly_detected") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("governance_action") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("initial_assignment") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("security_incident") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("verification_complete") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("quarantine") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("restore") == TrustChangeType.ESSENTIAL

    def test_classify_derived_reasons(self):
        """Non-essential reasons are classified as derived."""
        assert TrustSnapshotCompressor.classify("cascade_update") == TrustChangeType.DERIVED
        assert TrustSnapshotCompressor.classify("routine_decay") == TrustChangeType.DERIVED
        assert TrustSnapshotCompressor.classify("automatic_adjustment") == TrustChangeType.DERIVED
        assert TrustSnapshotCompressor.classify("overlay_effect") == TrustChangeType.DERIVED

    def test_classify_none_reason(self):
        """None reason is classified as derived."""
        assert TrustSnapshotCompressor.classify(None) == TrustChangeType.DERIVED

    def test_classify_case_insensitive(self):
        """Classification is case insensitive."""
        assert TrustSnapshotCompressor.classify("Manual_Adjustment") == TrustChangeType.ESSENTIAL
        assert TrustSnapshotCompressor.classify("ADMIN ADJUSTMENT") == TrustChangeType.ESSENTIAL

    def test_classify_partial_match(self):
        """Classification matches partial reason strings."""
        assert TrustSnapshotCompressor.classify("user manual_adjustment applied") == TrustChangeType.ESSENTIAL

    def test_compress_essential_snapshot(self):
        """Essential snapshots retain all data."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=80,
            reason="manual_adjustment",
            evidence={"note": "Admin approved"},
            source_event_id="event-1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        compressed = TrustSnapshotCompressor.compress(snapshot)

        assert compressed.change_type == TrustChangeType.ESSENTIAL
        assert compressed.evidence == {"note": "Admin approved"}

    def test_compress_derived_snapshot(self):
        """Derived snapshots have evidence removed."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=65,
            reason="cascade_update",
            evidence={"source": "overlay"},
            source_event_id="event-2",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        compressed = TrustSnapshotCompressor.compress(snapshot)

        assert compressed.change_type == TrustChangeType.DERIVED
        assert compressed.evidence is None
        assert compressed.reconstruction_hint == "event:event-2"

    def test_compress_does_not_mutate_original(self):
        """Compress returns a new object, doesn't mutate original."""
        snapshot = TrustSnapshot(
            entity_id="user-123",
            entity_type="User",
            trust_value=65,
            reason="cascade_update",
            evidence={"source": "overlay"},
            source_event_id="event-2",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        original_evidence = snapshot.evidence

        compressed = TrustSnapshotCompressor.compress(snapshot)

        assert snapshot.evidence == original_evidence  # Original unchanged
        assert compressed is not snapshot  # Different object

    def test_estimate_storage(self):
        """estimate_storage calculates savings correctly."""
        snapshots = [
            TrustSnapshot(
                entity_id="u1",
                entity_type="User",
                trust_value=60,
                change_type=TrustChangeType.ESSENTIAL,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            TrustSnapshot(
                entity_id="u1",
                entity_type="User",
                trust_value=62,
                change_type=TrustChangeType.DERIVED,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            TrustSnapshot(
                entity_id="u1",
                entity_type="User",
                trust_value=64,
                change_type=TrustChangeType.DERIVED,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        estimate = TrustSnapshotCompressor.estimate_storage(snapshots)

        assert estimate["total_snapshots"] == 3
        assert estimate["essential_count"] == 1
        assert estimate["derived_count"] == 2
        assert estimate["uncompressed_bytes"] == 1500  # 3 * 500
        assert estimate["compressed_bytes"] == 700  # 1*500 + 2*100
        assert estimate["savings_percent"] > 50

    def test_estimate_storage_empty(self):
        """estimate_storage handles empty list."""
        estimate = TrustSnapshotCompressor.estimate_storage([])

        assert estimate["total_snapshots"] == 0
        assert estimate["savings_percent"] == 0.0


# =============================================================================
# VersioningPolicy Tests
# =============================================================================


class TestVersioningPolicy:
    """Tests for VersioningPolicy model."""

    def test_valid_versioning_policy(self):
        """Valid versioning policy creates model."""
        policy = VersioningPolicy(
            snapshot_every_n_changes=5,
            snapshot_for_trust_level=70,
            compact_after_days=60,
            keep_snapshots_for_days=730,
            max_diff_chain_length=15,
            max_diff_size_bytes=20000,
        )
        assert policy.snapshot_every_n_changes == 5
        assert policy.compact_after_days == 60

    def test_versioning_policy_defaults(self):
        """VersioningPolicy has sensible defaults."""
        policy = VersioningPolicy()
        assert policy.snapshot_every_n_changes == 10
        assert policy.snapshot_for_trust_level == TrustLevel.TRUSTED.value  # 80
        assert policy.compact_after_days == 30
        assert policy.keep_snapshots_for_days == 365
        assert policy.max_diff_chain_length == 10
        assert policy.max_diff_size_bytes == 10000

    def test_snapshot_every_n_changes_bounds(self):
        """snapshot_every_n_changes must be >= 1."""
        with pytest.raises(ValidationError):
            VersioningPolicy(snapshot_every_n_changes=0)

    def test_should_full_snapshot_initial_creation(self):
        """should_full_snapshot returns True for initial creation."""
        policy = VersioningPolicy()
        assert policy.should_full_snapshot(
            change_number=1,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=0,
        ) is True

    def test_should_full_snapshot_periodic(self):
        """should_full_snapshot returns True at periodic intervals."""
        policy = VersioningPolicy(snapshot_every_n_changes=5)
        assert policy.should_full_snapshot(
            change_number=5,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=4,
        ) is True
        assert policy.should_full_snapshot(
            change_number=10,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=9,
        ) is True

    def test_should_full_snapshot_high_trust(self):
        """should_full_snapshot returns True for high trust capsules."""
        policy = VersioningPolicy(snapshot_for_trust_level=80)
        assert policy.should_full_snapshot(
            change_number=3,
            trust_level=85,
            is_major_version=False,
            diff_chain_length=2,
        ) is True

    def test_should_full_snapshot_major_version(self):
        """should_full_snapshot returns True for major versions."""
        policy = VersioningPolicy()
        assert policy.should_full_snapshot(
            change_number=3,
            trust_level=60,
            is_major_version=True,
            diff_chain_length=2,
        ) is True

    def test_should_full_snapshot_chain_too_long(self):
        """should_full_snapshot returns True when diff chain too long."""
        policy = VersioningPolicy(max_diff_chain_length=5)
        assert policy.should_full_snapshot(
            change_number=7,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=5,
        ) is True

    def test_should_full_snapshot_diff_too_large(self):
        """should_full_snapshot returns True when diff too large."""
        policy = VersioningPolicy(max_diff_size_bytes=5000)
        assert policy.should_full_snapshot(
            change_number=3,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=2,
            diff_size=6000,
        ) is True

    def test_should_full_snapshot_false(self):
        """should_full_snapshot returns False when no triggers hit."""
        policy = VersioningPolicy(
            snapshot_every_n_changes=10,
            snapshot_for_trust_level=80,
            max_diff_chain_length=10,
        )
        assert policy.should_full_snapshot(
            change_number=3,
            trust_level=60,
            is_major_version=False,
            diff_chain_length=2,
            diff_size=1000,
        ) is False

    def test_should_compact_diff_old_enough(self):
        """should_compact returns True for old diffs."""
        policy = VersioningPolicy(compact_after_days=30)
        old_version = CapsuleVersion(
            capsule_id="cap-123",
            version_number="1.1.0",
            change_type=ChangeType.UPDATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            snapshot_type=SnapshotType.DIFF,
            created_at=datetime.now(UTC) - timedelta(days=31),
            updated_at=datetime.now(UTC) - timedelta(days=31),
        )
        assert policy.should_compact(old_version) is True

    def test_should_compact_diff_not_old_enough(self):
        """should_compact returns False for recent diffs."""
        policy = VersioningPolicy(compact_after_days=30)
        recent_version = CapsuleVersion(
            capsule_id="cap-123",
            version_number="1.1.0",
            change_type=ChangeType.UPDATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            snapshot_type=SnapshotType.DIFF,
            created_at=datetime.now(UTC) - timedelta(days=10),
            updated_at=datetime.now(UTC) - timedelta(days=10),
        )
        assert policy.should_compact(recent_version) is False

    def test_should_compact_full_snapshot(self):
        """should_compact returns False for full snapshots."""
        policy = VersioningPolicy(compact_after_days=30)
        full_version = CapsuleVersion(
            capsule_id="cap-123",
            version_number="1.0.0",
            change_type=ChangeType.CREATE,
            created_by="user-456",
            content_hash="abc123",
            trust_at_version=60,
            snapshot_type=SnapshotType.FULL,
            created_at=datetime.now(UTC) - timedelta(days=60),
            updated_at=datetime.now(UTC) - timedelta(days=60),
        )
        assert policy.should_compact(full_version) is False


# =============================================================================
# GraphSnapshot Tests
# =============================================================================


class TestGraphSnapshot:
    """Tests for GraphSnapshot model."""

    def test_valid_graph_snapshot(self):
        """Valid graph snapshot creates model."""
        snapshot = GraphSnapshot(
            total_nodes=1000,
            total_edges=5000,
            nodes_by_type={"Capsule": 800, "User": 200},
            edges_by_type={"DERIVED_FROM": 2000, "OWNS": 800},
            density=0.01,
            avg_degree=5.0,
            connected_components=3,
            avg_trust=65.5,
            community_count=10,
            active_anomalies=2,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.total_nodes == 1000
        assert snapshot.avg_trust == 65.5

    def test_graph_snapshot_defaults(self):
        """GraphSnapshot has sensible defaults."""
        snapshot = GraphSnapshot(
            total_nodes=0,
            total_edges=0,
            density=0.0,
            avg_degree=0.0,
            connected_components=0,
            avg_trust=0.0,
            community_count=0,
            active_anomalies=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert snapshot.id is not None
        assert snapshot.nodes_by_type == {}
        assert snapshot.edges_by_type == {}
        assert snapshot.trust_distribution == {}
        assert snapshot.modularity is None
        assert snapshot.top_capsules_by_pagerank == []
        assert snapshot.top_users_by_influence == []
        assert snapshot.anomaly_types == {}

    def test_graph_snapshot_bounds(self):
        """Graph snapshot values have proper bounds."""
        with pytest.raises(ValidationError):
            GraphSnapshot(
                total_nodes=-1,
                total_edges=0,
                density=0.0,
                avg_degree=0.0,
                connected_components=0,
                avg_trust=0.0,
                community_count=0,
                active_anomalies=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        with pytest.raises(ValidationError):
            GraphSnapshot(
                total_nodes=0,
                total_edges=0,
                density=1.5,  # Must be 0-1
                avg_degree=0.0,
                connected_components=0,
                avg_trust=0.0,
                community_count=0,
                active_anomalies=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        with pytest.raises(ValidationError):
            GraphSnapshot(
                total_nodes=0,
                total_edges=0,
                density=0.0,
                avg_degree=0.0,
                connected_components=0,
                avg_trust=101.0,  # Must be 0-100
                community_count=0,
                active_anomalies=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )


# =============================================================================
# GraphEvolution Tests
# =============================================================================


class TestGraphEvolution:
    """Tests for GraphEvolution model."""

    def test_valid_graph_evolution(self):
        """Valid graph evolution creates model."""
        evolution = GraphEvolution(
            start_time=datetime.now(UTC) - timedelta(days=30),
            end_time=datetime.now(UTC),
            node_growth_rate=10.5,
            edge_growth_rate=25.3,
            trust_trend=0.5,
        )
        assert evolution.node_growth_rate == 10.5
        assert evolution.trust_trend == 0.5

    def test_graph_evolution_defaults(self):
        """GraphEvolution has sensible defaults."""
        evolution = GraphEvolution(
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            node_growth_rate=0.0,
            edge_growth_rate=0.0,
            trust_trend=0.0,
        )
        assert evolution.snapshots == []
        assert evolution.granularity == TimeGranularity.DAY


# =============================================================================
# TemporalQuery Tests
# =============================================================================


class TestTemporalQuery:
    """Tests for TemporalQuery model."""

    def test_valid_temporal_query(self):
        """Valid temporal query creates model."""
        query = TemporalQuery(
            start_time=datetime.now(UTC) - timedelta(days=7),
            end_time=datetime.now(UTC),
            granularity=TimeGranularity.HOUR,
        )
        assert query.granularity == TimeGranularity.HOUR

    def test_temporal_query_defaults(self):
        """TemporalQuery has sensible defaults."""
        query = TemporalQuery()
        assert query.start_time is None
        assert query.end_time is None
        assert query.granularity == TimeGranularity.DAY


# =============================================================================
# VersionHistoryQuery Tests
# =============================================================================


class TestVersionHistoryQuery:
    """Tests for VersionHistoryQuery model."""

    def test_valid_version_history_query(self):
        """Valid version history query creates model."""
        query = VersionHistoryQuery(
            capsule_id="cap-123",
            include_content=True,
            change_types=[ChangeType.UPDATE, ChangeType.FORK],
            limit=20,
        )
        assert query.capsule_id == "cap-123"
        assert query.include_content is True

    def test_version_history_query_defaults(self):
        """VersionHistoryQuery has sensible defaults."""
        query = VersionHistoryQuery(capsule_id="cap-123")
        assert query.include_content is False
        assert query.change_types is None
        assert query.created_by is None
        assert query.limit == 50

    def test_version_history_query_limit_bounds(self):
        """Limit must be 1-500."""
        VersionHistoryQuery(capsule_id="cap-123", limit=1)
        VersionHistoryQuery(capsule_id="cap-123", limit=500)

        with pytest.raises(ValidationError):
            VersionHistoryQuery(capsule_id="cap-123", limit=0)
        with pytest.raises(ValidationError):
            VersionHistoryQuery(capsule_id="cap-123", limit=501)


# =============================================================================
# TrustTimelineQuery Tests
# =============================================================================


class TestTrustTimelineQuery:
    """Tests for TrustTimelineQuery model."""

    def test_valid_trust_timeline_query(self):
        """Valid trust timeline query creates model."""
        query = TrustTimelineQuery(
            entity_id="user-123",
            entity_type="User",
            include_derived=False,
            min_delta=10,
        )
        assert query.entity_id == "user-123"
        assert query.include_derived is False

    def test_trust_timeline_query_defaults(self):
        """TrustTimelineQuery has sensible defaults."""
        query = TrustTimelineQuery(
            entity_id="cap-123",
            entity_type="Capsule",
        )
        assert query.include_derived is True
        assert query.min_delta is None

    def test_entity_type_pattern(self):
        """Entity type must be User or Capsule."""
        TrustTimelineQuery(entity_id="u1", entity_type="User")
        TrustTimelineQuery(entity_id="c1", entity_type="Capsule")

        with pytest.raises(ValidationError, match="String should match pattern"):
            TrustTimelineQuery(entity_id="x1", entity_type="Unknown")

    def test_min_delta_bounds(self):
        """min_delta must be >= 1."""
        TrustTimelineQuery(entity_id="u1", entity_type="User", min_delta=1)

        with pytest.raises(ValidationError):
            TrustTimelineQuery(entity_id="u1", entity_type="User", min_delta=0)


# =============================================================================
# CapsuleAtTimeQuery Tests (from temporal module)
# =============================================================================


class TestCapsuleAtTimeQueryTemporal:
    """Tests for CapsuleAtTimeQuery model in temporal module."""

    def test_valid_capsule_at_time_query(self):
        """Valid query creates model."""
        query = CapsuleAtTimeQuery(
            capsule_id="cap-123",
            timestamp=datetime.now(UTC) - timedelta(days=7),
            include_trust=True,
            include_relationships=True,
        )
        assert query.capsule_id == "cap-123"
        assert query.include_relationships is True

    def test_capsule_at_time_query_defaults(self):
        """CapsuleAtTimeQuery has sensible defaults."""
        query = CapsuleAtTimeQuery(
            capsule_id="cap-123",
            timestamp=datetime.now(UTC),
        )
        assert query.include_trust is True
        assert query.include_relationships is False


# =============================================================================
# GraphSnapshotQuery Tests (from temporal module)
# =============================================================================


class TestGraphSnapshotQueryTemporal:
    """Tests for GraphSnapshotQuery model in temporal module."""

    def test_valid_graph_snapshot_query(self):
        """Valid query creates model."""
        query = GraphSnapshotQuery(
            start_time=datetime.now(UTC) - timedelta(days=30),
            end_time=datetime.now(UTC),
            include_top_entities=False,
            include_anomalies=False,
            limit=100,
        )
        assert query.include_top_entities is False
        assert query.limit == 100

    def test_graph_snapshot_query_defaults(self):
        """GraphSnapshotQuery has sensible defaults."""
        query = GraphSnapshotQuery()
        assert query.include_top_entities is True
        assert query.include_anomalies is True
        assert query.limit == 30

    def test_graph_snapshot_query_limit_bounds(self):
        """Limit must be 1-365."""
        GraphSnapshotQuery(limit=1)
        GraphSnapshotQuery(limit=365)

        with pytest.raises(ValidationError):
            GraphSnapshotQuery(limit=0)
        with pytest.raises(ValidationError):
            GraphSnapshotQuery(limit=366)


# =============================================================================
# VersionComparison Tests
# =============================================================================


class TestVersionComparison:
    """Tests for VersionComparison model."""

    def test_valid_version_comparison(self):
        """Valid version comparison creates model."""
        comparison = VersionComparison(
            capsule_id="cap-123",
            version_a_id="v1",
            version_b_id="v5",
            version_a_number="1.0.0",
            version_b_number="1.4.0",
            diff=VersionDiff(added_lines=["new content"]),
            time_between=timedelta(days=30),
            changes_between=4,
            trust_change=10,
            contributors=["user-1", "user-2"],
        )
        assert comparison.changes_between == 4
        assert comparison.trust_change == 10

    def test_version_comparison_defaults(self):
        """VersionComparison has sensible defaults."""
        comparison = VersionComparison(
            capsule_id="cap-123",
            version_a_id="v1",
            version_b_id="v2",
            version_a_number="1.0.0",
            version_b_number="1.1.0",
            diff=VersionDiff(),
            changes_between=1,
            trust_change=0,
        )
        assert comparison.time_between is None
        assert comparison.contributors == []

    def test_changes_between_bounds(self):
        """changes_between must be >= 0."""
        with pytest.raises(ValidationError):
            VersionComparison(
                capsule_id="cap-123",
                version_a_id="v1",
                version_b_id="v2",
                version_a_number="1.0.0",
                version_b_number="1.1.0",
                diff=VersionDiff(),
                changes_between=-1,
                trust_change=0,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
