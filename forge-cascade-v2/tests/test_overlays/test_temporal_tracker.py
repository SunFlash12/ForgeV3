"""
Comprehensive tests for the TemporalTrackerOverlay.

Tests cover:
- Overlay initialization and configuration
- Capsule version creation (create, update)
- Trust snapshot creation
- Version history retrieval
- Time-travel queries
- Trust timeline retrieval
- Version diffing
- Graph snapshots
- Version compaction
- Statistics tracking
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from forge.models.events import Event, EventType
from forge.models.overlay import Capability
from forge.models.temporal import (
    ChangeType,
    SnapshotType,
    TrustChangeType,
)
from forge.overlays.base import OverlayContext
from forge.overlays.temporal_tracker import (
    TemporalConfig,
    TemporalError,
    TemporalTrackerOverlay,
    create_temporal_tracker_overlay,
)

# =============================================================================
# Mock Classes
# =============================================================================


class MockVersion:
    """Mock version object."""

    def __init__(
        self,
        version_id: str | None = None,
        capsule_id: str = "test-capsule",
        version_number: int = 1,
        content: str = "test content",
        snapshot_type: SnapshotType = SnapshotType.FULL,
        change_type: ChangeType = ChangeType.CREATE,
        created_by: str = "test-user",
    ):
        self.id = version_id or str(uuid4())
        self.capsule_id = capsule_id
        self.version_number = version_number
        self.content = content
        self.snapshot_type = snapshot_type
        self.change_type = change_type
        self.created_by = created_by
        self.created_at = datetime.now(UTC)
        self.metadata_at_version = {}


class MockTrustSnapshot:
    """Mock trust snapshot object."""

    def __init__(
        self,
        entity_id: str = "test-entity",
        entity_type: str = "User",
        trust_value: int = 60,
        change_type: TrustChangeType = TrustChangeType.MANUAL,
        reason: str | None = None,
    ):
        self.id = str(uuid4())
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.trust_value = trust_value
        self.change_type = change_type
        self.reason = reason
        self.created_at = datetime.now(UTC)


class MockVersionHistory:
    """Mock version history object."""

    def __init__(self, versions: list[MockVersion] | None = None):
        self.versions = versions or []


class MockTrustTimeline:
    """Mock trust timeline object."""

    def __init__(self, snapshots: list[MockTrustSnapshot] | None = None):
        self.snapshots = snapshots or []


class MockVersionComparison:
    """Mock version comparison object."""

    def __init__(self):
        self.diff = MagicMock()
        self.diff.model_dump.return_value = {"changes": []}


class MockGraphSnapshot:
    """Mock graph snapshot object."""

    def __init__(self):
        self.id = str(uuid4())
        self.created_at = datetime.now(UTC)
        self.total_nodes = 100
        self.total_edges = 200


class MockTemporalRepository:
    """Mock temporal repository."""

    def __init__(self):
        self.create_version = AsyncMock(return_value=MockVersion())
        self.create_trust_snapshot = AsyncMock(return_value=MockTrustSnapshot())
        self.get_version_history = AsyncMock(return_value=MockVersionHistory([MockVersion()]))
        self._get_version_by_id = AsyncMock(return_value=MockVersion())
        self._reconstruct_content = AsyncMock(return_value="reconstructed content")
        self.get_capsule_at_time = AsyncMock(return_value=MockVersion())
        self.get_trust_timeline = AsyncMock(return_value=MockTrustTimeline([MockTrustSnapshot()]))
        self.diff_versions = AsyncMock(return_value=MockVersionComparison())
        self.create_graph_snapshot = AsyncMock(return_value=MockGraphSnapshot())
        self.get_latest_graph_snapshot = AsyncMock(return_value=None)
        self.compact_old_versions = AsyncMock(return_value=5)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo() -> MockTemporalRepository:
    """Create a mock temporal repository."""
    return MockTemporalRepository()


@pytest.fixture
def tracker(mock_repo: MockTemporalRepository) -> TemporalTrackerOverlay:
    """Create a TemporalTrackerOverlay with mock repository."""
    return TemporalTrackerOverlay(temporal_repository=mock_repo)


@pytest.fixture
def tracker_no_repo() -> TemporalTrackerOverlay:
    """Create a TemporalTrackerOverlay without repository."""
    return TemporalTrackerOverlay()


@pytest.fixture
async def initialized_tracker(
    tracker: TemporalTrackerOverlay,
) -> TemporalTrackerOverlay:
    """Create and initialize a TemporalTrackerOverlay."""
    await tracker.initialize()
    return tracker


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="temporal_tracker",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestTemporalTrackerInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(self, tracker: TemporalTrackerOverlay) -> None:
        """Test default initialization values."""
        assert tracker.NAME == "temporal_tracker"
        assert tracker.VERSION == "1.0.0"
        assert tracker._config is not None

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TemporalConfig(
            auto_version_on_update=False,
            snapshot_every_n_changes=5,
            track_all_trust_changes=False,
        )
        tracker = TemporalTrackerOverlay(config=config)

        assert tracker._config.auto_version_on_update is False
        assert tracker._config.snapshot_every_n_changes == 5

    @pytest.mark.asyncio
    async def test_initialize(self, tracker: TemporalTrackerOverlay) -> None:
        """Test overlay initialization."""
        result = await tracker.initialize()
        assert result is True

    def test_subscribed_events(self, tracker: TemporalTrackerOverlay) -> None:
        """Test subscribed events."""
        assert EventType.CAPSULE_CREATED in tracker.SUBSCRIBED_EVENTS
        assert EventType.CAPSULE_UPDATED in tracker.SUBSCRIBED_EVENTS
        assert EventType.TRUST_UPDATED in tracker.SUBSCRIBED_EVENTS

    def test_required_capabilities(self, tracker: TemporalTrackerOverlay) -> None:
        """Test required capabilities."""
        assert Capability.DATABASE_READ in tracker.REQUIRED_CAPABILITIES
        assert Capability.DATABASE_WRITE in tracker.REQUIRED_CAPABILITIES

    def test_set_repository(self, tracker_no_repo: TemporalTrackerOverlay) -> None:
        """Test setting repository."""
        mock_repo = MockTemporalRepository()
        tracker_no_repo.set_repository(mock_repo)

        assert tracker_no_repo._temporal_repository is not None


# =============================================================================
# Repository Requirement Tests
# =============================================================================


class TestRepositoryRequirement:
    """Tests for repository requirement."""

    @pytest.mark.asyncio
    async def test_execute_without_repository(
        self,
        tracker_no_repo: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test execution without repository."""
        result = await tracker_no_repo.execute(
            context=overlay_context,
            input_data={"operation": "get_history", "capsule_id": "test"},
        )

        assert result.success is False
        assert "not configured" in result.error

    def test_require_repository_raises(self, tracker_no_repo: TemporalTrackerOverlay) -> None:
        """Test _require_repository raises when not configured."""
        with pytest.raises(TemporalError):
            tracker_no_repo._require_repository()


# =============================================================================
# Capsule Created Tests
# =============================================================================


class TestCapsuleCreated:
    """Tests for capsule created handling."""

    @pytest.mark.asyncio
    async def test_handle_capsule_created(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test handling capsule created event."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "new-capsule",
                "content": "Initial content",
                "trust_level": 60,
            },
        )

        result = await initialized_tracker.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is True
        assert "version_id" in result.data
        mock_repo.create_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_capsule_created_increments_stats(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test stats are incremented on capsule creation."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "test-capsule", "content": "content"},
        )

        await initialized_tracker.execute(context=overlay_context, event=event)

        assert initialized_tracker._stats["versions_created"] >= 1

    @pytest.mark.asyncio
    async def test_capsule_created_emits_event(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test event emission on capsule creation."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "test-capsule", "content": "content"},
        )

        result = await initialized_tracker.execute(context=overlay_context, event=event)

        assert len(result.events_to_emit) >= 1


# =============================================================================
# Capsule Updated Tests
# =============================================================================


class TestCapsuleUpdated:
    """Tests for capsule updated handling."""

    @pytest.mark.asyncio
    async def test_handle_capsule_updated(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test handling capsule updated event."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_UPDATED,
            source="test",
            payload={
                "capsule_id": "existing-capsule",
                "content": "Updated content",
            },
        )

        result = await initialized_tracker.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is True
        mock_repo.create_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_capsule_updated_major_change(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test handling major capsule update (fork)."""
        event = Event(
            id="test-event",
            type=EventType.CAPSULE_UPDATED,
            source="test",
            payload={
                "capsule_id": "capsule",
                "content": "Forked content",
                "is_major": True,
            },
        )

        await initialized_tracker.execute(context=overlay_context, event=event)

        # Check that FORK change type was used
        call_args = mock_repo.create_version.call_args
        assert call_args.kwargs["change_type"] == ChangeType.FORK


# =============================================================================
# Trust Adjusted Tests
# =============================================================================


class TestTrustAdjusted:
    """Tests for trust adjustment handling."""

    @pytest.mark.asyncio
    async def test_handle_trust_adjusted(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test handling trust updated event."""
        event = Event(
            id="test-event",
            type=EventType.TRUST_UPDATED,
            source="test",
            payload={
                "entity_id": "user-123",
                "entity_type": "User",
                "new_trust": 80,
                "reason": "Contribution reward",
            },
        )

        result = await initialized_tracker.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is True
        mock_repo.create_trust_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_trust_adjusted_missing_data(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test trust adjustment with missing data."""
        event = Event(
            id="test-event",
            type=EventType.TRUST_UPDATED,
            source="test",
            payload={},  # Missing required fields
        )

        result = await initialized_tracker.execute(context=overlay_context, event=event)

        assert "error" in result.data


# =============================================================================
# Version History Tests
# =============================================================================


class TestVersionHistory:
    """Tests for version history retrieval."""

    @pytest.mark.asyncio
    async def test_get_version_history(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting version history."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_history",
                "capsule_id": "test-capsule",
            },
        )

        assert result.success is True
        assert "versions" in result.data
        mock_repo.get_version_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_version_history_missing_id(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting version history without capsule_id."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={"operation": "get_history"},
        )

        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_get_version_history_with_limit(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting version history with limit."""
        await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_history",
                "capsule_id": "test",
                "limit": 10,
            },
        )

        call_args = mock_repo.get_version_history.call_args
        assert call_args.kwargs["limit"] == 10


# =============================================================================
# Get Specific Version Tests
# =============================================================================


class TestGetSpecificVersion:
    """Tests for retrieving specific versions."""

    @pytest.mark.asyncio
    async def test_get_version(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting a specific version."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_version",
                "version_id": "version-123",
            },
        )

        assert result.success is True
        assert "content" in result.data

    @pytest.mark.asyncio
    async def test_get_version_not_found(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting non-existent version."""
        mock_repo._get_version_by_id.return_value = None

        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_version",
                "version_id": "nonexistent",
            },
        )

        assert "error" in result.data


# =============================================================================
# Time-Travel Query Tests
# =============================================================================


class TestTimeTravelQueries:
    """Tests for time-travel queries."""

    @pytest.mark.asyncio
    async def test_get_capsule_at_time(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting capsule state at a specific time."""
        timestamp = datetime.now(UTC).isoformat()

        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_at_time",
                "capsule_id": "test-capsule",
                "timestamp": timestamp,
            },
        )

        assert result.success is True
        assert result.data["found"] is True

    @pytest.mark.asyncio
    async def test_get_capsule_at_time_not_found(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting capsule at time when not found."""
        mock_repo.get_capsule_at_time.return_value = None

        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_at_time",
                "capsule_id": "test",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        assert result.data["found"] is False


# =============================================================================
# Trust Timeline Tests
# =============================================================================


class TestTrustTimeline:
    """Tests for trust timeline retrieval."""

    @pytest.mark.asyncio
    async def test_get_trust_timeline(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting trust timeline."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_trust_timeline",
                "entity_id": "user-123",
                "entity_type": "User",
            },
        )

        assert result.success is True
        assert "timeline" in result.data
        assert "snapshot_count" in result.data

    @pytest.mark.asyncio
    async def test_get_trust_timeline_with_dates(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test getting trust timeline with date range."""
        start = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        end = datetime.now(UTC).isoformat()

        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "get_trust_timeline",
                "entity_id": "user-123",
                "start": start,
                "end": end,
            },
        )

        assert result.success is True


# =============================================================================
# Version Diff Tests
# =============================================================================


class TestVersionDiff:
    """Tests for version diffing."""

    @pytest.mark.asyncio
    async def test_diff_versions(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test diffing two versions."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "diff_versions",
                "version_a": "version-1",
                "version_b": "version-2",
            },
        )

        assert result.success is True
        assert "diff" in result.data

    @pytest.mark.asyncio
    async def test_diff_versions_missing_ids(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test diffing with missing version IDs."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "diff_versions",
                "version_a": "version-1",
            },
        )

        assert "error" in result.data


# =============================================================================
# Graph Snapshot Tests
# =============================================================================


class TestGraphSnapshots:
    """Tests for graph snapshots."""

    @pytest.mark.asyncio
    async def test_create_graph_snapshot(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test creating a graph snapshot."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "create_graph_snapshot",
                "metrics": {"custom_metric": 42},
            },
        )

        assert result.success is True
        assert "snapshot_id" in result.data

    @pytest.mark.asyncio
    async def test_auto_graph_snapshot(
        self,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test automatic graph snapshot creation."""
        config = TemporalConfig(
            enable_graph_snapshots=True,
            graph_snapshot_interval_hours=0,  # Force snapshot
        )
        tracker = TemporalTrackerOverlay(
            temporal_repository=mock_repo,
            config=config,
        )
        await tracker.initialize()

        # Execute any operation to trigger maybe_graph_snapshot
        event = Event(
            id="test",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "test", "content": "content"},
        )
        await tracker.execute(context=overlay_context, event=event)

        # Graph snapshot should have been created
        assert mock_repo.create_graph_snapshot.called


# =============================================================================
# Compaction Tests
# =============================================================================


class TestCompaction:
    """Tests for version compaction."""

    @pytest.mark.asyncio
    async def test_compact_versions(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test compacting old versions."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={
                "operation": "compact",
                "capsule_id": "test-capsule",
            },
        )

        assert result.success is True
        assert "compacted_count" in result.data

    @pytest.mark.asyncio
    async def test_compact_without_capsule_id(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test compaction requires capsule_id."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={"operation": "compact"},
        )

        assert "error" in result.data


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    def test_get_stats(self, tracker: TemporalTrackerOverlay) -> None:
        """Test getting statistics."""
        stats = tracker.get_stats()

        assert "versions_created" in stats
        assert "trust_snapshots_created" in stats
        assert "tracked_capsules" in stats

    @pytest.mark.asyncio
    async def test_stats_updated_on_operations(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test statistics are updated during operations."""
        event = Event(
            id="test",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "test", "content": "content"},
        )

        await initialized_tracker.execute(context=overlay_context, event=event)

        stats = initialized_tracker.get_stats()
        assert stats["versions_created"] >= 1


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for create_temporal_tracker_overlay factory function."""

    def test_create_default(self) -> None:
        """Test creating default overlay."""
        overlay = create_temporal_tracker_overlay()
        assert isinstance(overlay, TemporalTrackerOverlay)

    def test_create_with_config(self) -> None:
        """Test creating with configuration."""
        overlay = create_temporal_tracker_overlay(
            snapshot_every_n_changes=5,
            enable_graph_snapshots=False,
        )

        assert overlay._config.snapshot_every_n_changes == 5
        assert overlay._config.enable_graph_snapshots is False

    def test_create_with_repository(self) -> None:
        """Test creating with repository."""
        mock_repo = MockTemporalRepository()
        overlay = create_temporal_tracker_overlay(
            temporal_repository=mock_repo,
        )

        assert overlay._temporal_repository is not None


# =============================================================================
# Unknown Operation Tests
# =============================================================================


class TestUnknownOperation:
    """Tests for unknown operation handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test handling unknown operation."""
        result = await initialized_tracker.execute(
            context=overlay_context,
            input_data={"operation": "unknown_op"},
        )

        assert result.success is False
        assert "Unknown operation" in result.error


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_repository_error_handling(
        self,
        initialized_tracker: TemporalTrackerOverlay,
        overlay_context: OverlayContext,
        mock_repo: MockTemporalRepository,
    ) -> None:
        """Test handling repository errors."""
        mock_repo.create_version.side_effect = RuntimeError("Database error")

        event = Event(
            id="test",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "test", "content": "content"},
        )

        result = await initialized_tracker.execute(
            context=overlay_context,
            event=event,
        )

        assert result.success is False
        assert "error" in result.error.lower()
