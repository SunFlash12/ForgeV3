"""
Temporal Tracker Overlay for Forge Cascade V2

Tracks how knowledge and trust evolve over time:
- Capsule version history (content changes)
- Trust snapshots (trust evolution)
- Graph snapshots (periodic state captures)
- Diff computation and time-travel queries

Uses a hybrid versioning strategy:
- Diffs for routine changes
- Full snapshots for major changes and periodic captures
- Smart compaction for storage optimization
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from ..models.base import TrustLevel
from ..models.events import Event, EventType
from ..models.overlay import Capability
from ..models.temporal import (
    ChangeType,
    SnapshotType,
    TrustSnapshotCompressor,
    TrustSnapshotCreate,
    VersioningPolicy,
)
from ..repositories.temporal_repository import TemporalRepository
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class TemporalError(OverlayError):
    """Temporal tracking error."""

    pass


class VersionNotFoundError(TemporalError):
    """Version not found."""

    pass


@dataclass
class TemporalConfig:
    """Configuration for temporal tracking."""

    # Versioning
    auto_version_on_update: bool = True
    snapshot_every_n_changes: int = 10
    always_snapshot_trusted: bool = True  # Full snapshot for trust_level >= TRUSTED

    # Trust snapshots
    track_all_trust_changes: bool = True
    compress_derived_snapshots: bool = True

    # Graph snapshots
    enable_graph_snapshots: bool = True
    graph_snapshot_interval_hours: int = 24

    # Compaction
    enable_compaction: bool = True
    compact_after_days: int = 30
    keep_min_versions: int = 5

    # Retention
    trust_snapshot_retention_days: int = 365
    version_retention_days: int = 180


@dataclass
class VersionChangeStats:
    """Statistics about a version change."""

    version_id: str
    change_type: str
    lines_added: int = 0
    lines_removed: int = 0
    properties_changed: list[str] = field(default_factory=list)
    is_major_change: bool = False


class TemporalTrackerOverlay(BaseOverlay):
    """
    Temporal tracking overlay for version history and trust evolution.

    Automatically creates versions when capsules change and tracks
    trust modifications across the system.
    """

    NAME = "temporal_tracker"
    VERSION = "1.0.0"
    DESCRIPTION = "Tracks capsule versions and trust evolution over time"

    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.TRUST_UPDATED,
        EventType.SYSTEM_EVENT,
    }

    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
    }

    def __init__(
        self,
        temporal_repository: TemporalRepository | None = None,
        config: TemporalConfig | None = None,
    ) -> None:
        """
        Initialize the temporal tracker.

        Args:
            temporal_repository: Repository for temporal data
            config: Tracker configuration
        """
        super().__init__()

        self._temporal_repository = temporal_repository
        self._config = config or TemporalConfig()
        self._versioning_policy = VersioningPolicy(
            snapshot_every_n_changes=self._config.snapshot_every_n_changes,
        )
        self._trust_compressor = TrustSnapshotCompressor()

        # Version counters (in-memory, per capsule)
        self._version_counts: dict[str, int] = {}

        # Last graph snapshot time
        self._last_graph_snapshot: datetime | None = None

        # Statistics
        self._stats: dict[str, int] = {
            "versions_created": 0,
            "trust_snapshots_created": 0,
            "graph_snapshots_created": 0,
            "compactions_performed": 0,
            "diffs_computed": 0,
            "full_snapshots": 0,
        }

        self._logger = logger.bind(overlay=self.NAME)

    def _require_repository(self) -> TemporalRepository:
        """Return the temporal repository or raise if not configured."""
        if self._temporal_repository is None:
            raise TemporalError("Temporal repository not configured")
        return self._temporal_repository

    def set_repository(self, repository: TemporalRepository) -> None:
        """Set the temporal repository (for dependency injection)."""
        self._temporal_repository = repository

    async def initialize(self) -> bool:
        """Initialize the temporal tracker."""
        self._logger.info(
            "temporal_tracker_initialized",
            auto_version=self._config.auto_version_on_update,
            snapshot_interval=self._config.snapshot_every_n_changes,
        )
        return await super().initialize()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """
        Execute temporal tracking operations.

        Handles:
        - CAPSULE_CREATED: Create initial version
        - CAPSULE_UPDATED: Create new version with diff/snapshot
        - TRUST_UPDATED: Record trust snapshot
        - SYSTEM_EVENT: May trigger graph snapshot
        """
        if self._temporal_repository is None:
            return OverlayResult.fail("Temporal repository not configured")

        data: dict[str, Any] = input_data or {}
        if event:
            data.update(event.payload or {})
            data["event_type"] = event.type

        try:
            result_data: dict[str, Any] = {}
            events_to_emit: list[dict[str, Any]] = []

            # Route based on event type
            if event:
                if event.type == EventType.CAPSULE_CREATED:
                    result_data = await self._handle_capsule_created(data, context)
                    events_to_emit.append(
                        self.create_event_emission(
                            EventType.SYSTEM_EVENT,
                            {"type": "version_created", "capsule_id": data.get("capsule_id")},
                        )
                    )
                elif event.type == EventType.CAPSULE_UPDATED:
                    result_data = await self._handle_capsule_updated(data, context)
                    events_to_emit.append(
                        self.create_event_emission(
                            EventType.SYSTEM_EVENT,
                            {"type": "version_created", "capsule_id": data.get("capsule_id")},
                        )
                    )
                elif event.type == EventType.TRUST_UPDATED:
                    result_data = await self._handle_trust_adjusted(data, context)
                elif event.type == EventType.SYSTEM_EVENT:
                    result_data = await self._handle_system_event(data, context)
            else:
                # Direct invocation - determine operation
                operation = data.get("operation", "get_history")
                if operation == "get_history":
                    result_data = await self._get_version_history(data, context)
                elif operation == "get_version":
                    result_data = await self._get_specific_version(data, context)
                elif operation == "get_at_time":
                    result_data = await self._get_capsule_at_time(data, context)
                elif operation == "get_trust_timeline":
                    result_data = await self._get_trust_timeline(data, context)
                elif operation == "diff_versions":
                    result_data = await self._diff_versions(data, context)
                elif operation == "create_graph_snapshot":
                    result_data = await self._create_graph_snapshot(data, context)
                elif operation == "compact":
                    result_data = await self._compact_versions(data, context)
                else:
                    return OverlayResult.fail(f"Unknown operation: {operation}")

            # Check if graph snapshot is due
            if self._config.enable_graph_snapshots:
                await self._maybe_graph_snapshot(context)

            return OverlayResult.ok(
                data=result_data,
                events_to_emit=events_to_emit,
                metrics={
                    "versions_created": self._stats["versions_created"],
                    "trust_snapshots": self._stats["trust_snapshots_created"],
                },
            )

        except (
            TemporalError,
            VersionNotFoundError,
            OverlayError,
            ValueError,
            TypeError,
            KeyError,
            RuntimeError,
        ) as e:
            self._logger.error(
                "temporal_tracking_error",
                error=str(e),
                error_type=type(e).__name__,
                event_type=event.type.value if event else "direct",
            )
            return OverlayResult.fail(f"Temporal tracking error: {str(e)}")

    async def _handle_capsule_created(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Handle new capsule creation - create initial version."""
        repo = self._require_repository()

        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        content: str = data.get("content", "")
        trust_level: int = data.get("trust_level", TrustLevel.STANDARD.value)

        # Create initial version (always full snapshot)
        version = await repo.create_version(
            capsule_id=capsule_id,
            content=content,
            change_type=ChangeType.CREATE,
            created_by=context.user_id or "system",
            trust_level=trust_level,
            metadata={"trust_level": trust_level, "initial": True},
        )

        self._version_counts[capsule_id] = 1
        self._stats["versions_created"] += 1
        self._stats["full_snapshots"] += 1

        return {
            "version_id": version.id,
            "capsule_id": capsule_id,
            "version_number": version.version_number,
            "snapshot_type": version.snapshot_type.value,
            "created_at": version.created_at.isoformat(),
        }

    async def _handle_capsule_updated(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Handle capsule update - create new version."""
        repo = self._require_repository()

        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        content: str = data.get("content", "")
        trust_level: int = data.get("trust_level", TrustLevel.STANDARD.value)

        # Increment version count
        count = self._version_counts.get(capsule_id, 0) + 1
        self._version_counts[capsule_id] = count

        # Determine if this is a major change (fork or merge)
        is_major: bool = data.get("is_major", False)
        change_type = ChangeType.UPDATE
        if is_major:
            change_type = ChangeType.FORK

        # Create version - the repository decides snapshot type via policy
        version = await repo.create_version(
            capsule_id=capsule_id,
            content=content,
            change_type=change_type,
            created_by=context.user_id or "system",
            trust_level=trust_level,
            metadata={"trust_level": trust_level, "change_number": count},
        )

        self._stats["versions_created"] += 1
        if version.snapshot_type == SnapshotType.FULL:
            self._stats["full_snapshots"] += 1
        else:
            self._stats["diffs_computed"] += 1

        return {
            "version_id": version.id,
            "capsule_id": capsule_id,
            "version_number": version.version_number,
            "snapshot_type": version.snapshot_type.value,
            "change_number": count,
            "created_at": version.created_at.isoformat(),
        }

    async def _handle_trust_adjusted(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Handle trust adjustment - create trust snapshot."""
        repo = self._require_repository()

        entity_id: str | None = (
            data.get("entity_id") or data.get("user_id") or data.get("capsule_id")
        )
        entity_type: str = data.get("entity_type", "User")
        new_trust: int | None = data.get("new_trust") or data.get("trust_value")
        reason: str | None = data.get("reason")

        if not entity_id or new_trust is None:
            return {"error": "Missing entity_id or new_trust"}

        # Create snapshot via TrustSnapshotCreate
        snapshot_create = TrustSnapshotCreate(
            entity_id=entity_id,
            entity_type=entity_type,
            trust_value=new_trust,
            reason=reason,
            adjusted_by=context.user_id,
            source_event_id=data.get("source_event_id"),
        )

        snapshot = await repo.create_trust_snapshot(data=snapshot_create)

        self._stats["trust_snapshots_created"] += 1

        return {
            "snapshot_id": snapshot.id,
            "entity_id": entity_id,
            "trust_value": new_trust,
            "change_type": snapshot.change_type.value,
            "timestamp": snapshot.created_at.isoformat(),
        }

    async def _handle_system_event(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Handle system events that might trigger graph snapshots."""
        event_subtype: str | None = data.get("type", data.get("subtype"))

        if event_subtype == "graph_snapshot_requested":
            return await self._create_graph_snapshot(data, context)

        return {"handled": False, "event_subtype": event_subtype}

    async def _get_version_history(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Get version history for a capsule."""
        repo = self._require_repository()

        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        limit: int = data.get("limit", 50)
        history = await repo.get_version_history(capsule_id=capsule_id, limit=limit)

        return {
            "capsule_id": capsule_id,
            "version_count": len(history.versions),
            "versions": [
                {
                    "version_id": v.id,
                    "version_number": v.version_number,
                    "snapshot_type": v.snapshot_type.value,
                    "change_type": v.change_type.value,
                    "created_by": v.created_by,
                    "created_at": v.created_at.isoformat(),
                }
                for v in history.versions
            ],
        }

    async def _get_specific_version(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Get a specific version with full content."""
        repo = self._require_repository()

        version_id = data.get("version_id")
        if not version_id:
            return {"error": "Missing version_id"}

        version = await repo._get_version_by_id(version_id)
        if not version:
            return {"error": "Version not found", "version_id": version_id}

        # Reconstruct content if needed
        content = await repo._reconstruct_content(version)

        return {
            "version_id": version.id,
            "capsule_id": version.capsule_id,
            "version_number": version.version_number,
            "content": content,
            "snapshot_type": version.snapshot_type.value,
            "change_type": version.change_type.value,
            "created_by": version.created_by,
            "created_at": version.created_at.isoformat(),
            "metadata": version.metadata_at_version,
        }

    async def _get_capsule_at_time(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Get capsule state at a specific point in time."""
        repo = self._require_repository()

        capsule_id = data.get("capsule_id")
        timestamp_str: str | None = data.get("timestamp")

        if not capsule_id or not timestamp_str:
            return {"error": "Missing capsule_id or timestamp"}

        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        version = await repo.get_capsule_at_time(capsule_id=capsule_id, timestamp=timestamp)

        if not version:
            return {"capsule_id": capsule_id, "timestamp": timestamp.isoformat(), "found": False}

        content = await repo._reconstruct_content(version)

        return {
            "capsule_id": capsule_id,
            "timestamp": timestamp.isoformat(),
            "found": True,
            "version_id": version.id,
            "version_number": version.version_number,
            "content": content,
            "created_at": version.created_at.isoformat(),
        }

    async def _get_trust_timeline(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Get trust evolution timeline for an entity."""
        repo = self._require_repository()

        entity_id = data.get("entity_id")
        entity_type: str = data.get("entity_type", "User")
        start_str: str | None = data.get("start")
        end_str: str | None = data.get("end")

        if not entity_id:
            return {"error": "Missing entity_id"}

        start = (
            datetime.fromisoformat(start_str)
            if start_str
            else datetime.now(UTC) - timedelta(days=30)
        )
        end = datetime.fromisoformat(end_str) if end_str else datetime.now(UTC)

        timeline = await repo.get_trust_timeline(
            entity_id=entity_id, entity_type=entity_type, start=start, end=end
        )

        snapshots = timeline.snapshots

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "snapshot_count": len(snapshots),
            "timeline": [
                {
                    "trust_value": s.trust_value,
                    "timestamp": s.created_at.isoformat(),
                    "change_type": s.change_type.value,
                    "reason": s.reason,
                }
                for s in snapshots
            ],
            "trust_min": min(s.trust_value for s in snapshots) if snapshots else None,
            "trust_max": max(s.trust_value for s in snapshots) if snapshots else None,
            "trust_current": snapshots[-1].trust_value if snapshots else None,
        }

    async def _diff_versions(self, data: dict[str, Any], context: OverlayContext) -> dict[str, Any]:
        """Compute diff between two versions."""
        repo = self._require_repository()

        version_a = data.get("version_a")
        version_b = data.get("version_b")

        if not version_a or not version_b:
            return {"error": "Missing version_a or version_b"}

        comparison = await repo.diff_versions(version_a, version_b)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "diff": comparison.diff.model_dump(),
        }

    async def _create_graph_snapshot(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Create a graph snapshot."""
        repo = self._require_repository()

        metrics: dict[str, Any] = data.get("metrics", {})
        snapshot = await repo.create_graph_snapshot(metrics=metrics)
        self._last_graph_snapshot = datetime.now(UTC)
        self._stats["graph_snapshots_created"] += 1

        return {
            "snapshot_id": snapshot.id,
            "created_at": snapshot.created_at.isoformat(),
            "metrics": {
                "total_nodes": snapshot.total_nodes,
                "total_edges": snapshot.total_edges,
            },
        }

    async def _compact_versions(
        self, data: dict[str, Any], context: OverlayContext
    ) -> dict[str, Any]:
        """Compact old versions to save storage."""
        repo = self._require_repository()

        capsule_id: str | None = data.get("capsule_id")

        if capsule_id:
            compacted = await repo.compact_old_versions(
                capsule_id=capsule_id,
            )
            self._stats["compactions_performed"] += 1
            return {
                "capsule_id": capsule_id,
                "compacted_count": compacted,
            }
        else:
            # System-wide compaction
            return {"error": "capsule_id required for compaction"}

    async def _maybe_graph_snapshot(self, context: OverlayContext) -> None:
        """Create graph snapshot if due."""
        if not self._config.enable_graph_snapshots:
            return

        repo = self._require_repository()
        interval = timedelta(hours=self._config.graph_snapshot_interval_hours)

        if self._last_graph_snapshot is None:
            # Check if there's a recent one in the database
            recent = await repo.get_latest_graph_snapshot()
            if recent:
                self._last_graph_snapshot = recent.created_at

        if (
            self._last_graph_snapshot is None
            or datetime.now(UTC) - self._last_graph_snapshot > interval
        ):
            await self._create_graph_snapshot({}, context)

    def get_stats(self) -> dict[str, Any]:
        """Get temporal tracking statistics."""
        return {
            **self._stats,
            "tracked_capsules": len(self._version_counts),
            "last_graph_snapshot": self._last_graph_snapshot.isoformat()
            if self._last_graph_snapshot
            else None,
        }


# Convenience function
def create_temporal_tracker_overlay(
    temporal_repository: TemporalRepository | None = None, **kwargs: Any
) -> TemporalTrackerOverlay:
    """
    Create a temporal tracker overlay.

    Args:
        temporal_repository: Repository for temporal data
        **kwargs: Additional configuration

    Returns:
        Configured TemporalTrackerOverlay
    """
    config = TemporalConfig(**kwargs)
    return TemporalTrackerOverlay(temporal_repository=temporal_repository, config=config)
