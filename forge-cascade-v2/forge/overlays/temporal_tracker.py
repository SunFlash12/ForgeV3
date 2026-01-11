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
    SnapshotType,
    TrustSnapshotCompressor,
    VersioningPolicy,
)
from ..repositories.temporal_repository import TemporalRepository
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


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
        config: TemporalConfig | None = None
    ):
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
            snapshot_every_n=self._config.snapshot_every_n_changes,
            always_snapshot_trusted=self._config.always_snapshot_trusted
        )
        self._trust_compressor = TrustSnapshotCompressor()

        # Version counters (in-memory, per capsule)
        self._version_counts: dict[str, int] = {}

        # Last graph snapshot time
        self._last_graph_snapshot: datetime | None = None

        # Statistics
        self._stats = {
            "versions_created": 0,
            "trust_snapshots_created": 0,
            "graph_snapshots_created": 0,
            "compactions_performed": 0,
            "diffs_computed": 0,
            "full_snapshots": 0
        }

        self._logger = logger.bind(overlay=self.NAME)

    def set_repository(self, repository: TemporalRepository) -> None:
        """Set the temporal repository (for dependency injection)."""
        self._temporal_repository = repository

    async def initialize(self) -> bool:
        """Initialize the temporal tracker."""
        self._logger.info(
            "temporal_tracker_initialized",
            auto_version=self._config.auto_version_on_update,
            snapshot_interval=self._config.snapshot_every_n_changes
        )
        return await super().initialize()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute temporal tracking operations.

        Handles:
        - CAPSULE_CREATED: Create initial version
        - CAPSULE_UPDATED: Create new version with diff/snapshot
        - TRUST_ADJUSTED: Record trust snapshot
        - SYSTEM_EVENT: May trigger graph snapshot
        """
        if not self._temporal_repository:
            return OverlayResult.fail("Temporal repository not configured")

        data = input_data or {}
        if event:
            data.update(event.payload or {})
            data["event_type"] = event.event_type

        try:
            result_data = {}
            events_to_emit = []

            # Route based on event type
            if event:
                if event.event_type == EventType.CAPSULE_CREATED:
                    result_data = await self._handle_capsule_created(data, context)
                    events_to_emit.append(
                        self.create_event_emission(
                            EventType.SYSTEM_EVENT,
                            {"type": "version_created", "capsule_id": data.get("capsule_id")}
                        )
                    )
                elif event.event_type == EventType.CAPSULE_UPDATED:
                    result_data = await self._handle_capsule_updated(data, context)
                    events_to_emit.append(
                        self.create_event_emission(
                            EventType.SYSTEM_EVENT,
                            {"type": "version_created", "capsule_id": data.get("capsule_id")}
                        )
                    )
                elif event.event_type == EventType.TRUST_UPDATED:
                    result_data = await self._handle_trust_adjusted(data, context)
                elif event.event_type == EventType.SYSTEM_EVENT:
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
                    "trust_snapshots": self._stats["trust_snapshots_created"]
                }
            )

        except Exception as e:
            self._logger.error(
                "temporal_tracking_error",
                error=str(e),
                event_type=event.event_type.value if event else "direct"
            )
            return OverlayResult.fail(f"Temporal tracking error: {str(e)}")

    async def _handle_capsule_created(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle new capsule creation - create initial version."""
        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        content = data.get("content", "")
        trust_level = data.get("trust_level", TrustLevel.STANDARD.value)

        # Create initial version (always full snapshot)
        version = await self._temporal_repository.create_version(
            capsule_id=capsule_id,
            content=content,
            change_type="create",
            created_by=context.user_id,
            snapshot_type=SnapshotType.FULL,
            metadata={
                "trust_level": trust_level,
                "initial": True
            }
        )

        self._version_counts[capsule_id] = 1
        self._stats["versions_created"] += 1
        self._stats["full_snapshots"] += 1

        return {
            "version_id": version.version_id,
            "capsule_id": capsule_id,
            "version_number": version.version_number,
            "snapshot_type": version.snapshot_type.value,
            "created_at": version.created_at.isoformat()
        }

    async def _handle_capsule_updated(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle capsule update - create new version."""
        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        content = data.get("content", "")
        old_content = data.get("old_content", "")
        trust_level = data.get("trust_level", TrustLevel.STANDARD.value)

        # Increment version count
        count = self._version_counts.get(capsule_id, 0) + 1
        self._version_counts[capsule_id] = count

        # Determine snapshot type
        is_trusted = trust_level >= TrustLevel.TRUSTED.value
        snapshot_type = self._versioning_policy.get_snapshot_type(
            change_number=count,
            is_trusted=is_trusted,
            is_major=data.get("is_major", False)
        )

        # Create version
        version = await self._temporal_repository.create_version(
            capsule_id=capsule_id,
            content=content,
            change_type="update",
            created_by=context.user_id,
            snapshot_type=snapshot_type,
            previous_content=old_content if snapshot_type == SnapshotType.DIFF else None,
            metadata={
                "trust_level": trust_level,
                "change_number": count
            }
        )

        self._stats["versions_created"] += 1
        if snapshot_type == SnapshotType.FULL:
            self._stats["full_snapshots"] += 1
        else:
            self._stats["diffs_computed"] += 1

        return {
            "version_id": version.version_id,
            "capsule_id": capsule_id,
            "version_number": version.version_number,
            "snapshot_type": version.snapshot_type.value,
            "change_number": count,
            "created_at": version.created_at.isoformat()
        }

    async def _handle_trust_adjusted(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle trust adjustment - create trust snapshot."""
        entity_id = data.get("entity_id") or data.get("user_id") or data.get("capsule_id")
        entity_type = data.get("entity_type", "User")
        new_trust = data.get("new_trust") or data.get("trust_value")
        old_trust = data.get("old_trust")
        reason = data.get("reason")

        if not entity_id or new_trust is None:
            return {"error": "Missing entity_id or new_trust"}

        # Determine if this is an essential change
        change_type = self._trust_compressor.classify_change(
            reason=reason,
            trust_delta=abs(new_trust - (old_trust or new_trust)),
            context=data
        )

        # Create snapshot (compressed if derived)
        snapshot = await self._temporal_repository.create_trust_snapshot(
            entity_id=entity_id,
            entity_type=entity_type,
            trust_value=new_trust,
            reason=reason,
            adjusted_by=context.user_id,
            change_type=change_type,
            compress=self._config.compress_derived_snapshots
        )

        self._stats["trust_snapshots_created"] += 1

        return {
            "snapshot_id": snapshot.snapshot_id,
            "entity_id": entity_id,
            "trust_value": new_trust,
            "change_type": change_type.value,
            "timestamp": snapshot.timestamp.isoformat()
        }

    async def _handle_system_event(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle system events that might trigger graph snapshots."""
        event_subtype = data.get("type", data.get("subtype"))

        if event_subtype == "graph_snapshot_requested":
            return await self._create_graph_snapshot(data, context)

        return {"handled": False, "event_subtype": event_subtype}

    async def _get_version_history(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Get version history for a capsule."""
        capsule_id = data.get("capsule_id")
        if not capsule_id:
            return {"error": "Missing capsule_id"}

        limit = data.get("limit", 50)
        versions = await self._temporal_repository.get_version_history(
            capsule_id=capsule_id,
            limit=limit
        )

        return {
            "capsule_id": capsule_id,
            "version_count": len(versions),
            "versions": [
                {
                    "version_id": v.version_id,
                    "version_number": v.version_number,
                    "snapshot_type": v.snapshot_type.value,
                    "change_type": v.change_type,
                    "created_by": v.created_by,
                    "created_at": v.created_at.isoformat()
                }
                for v in versions
            ]
        }

    async def _get_specific_version(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Get a specific version with full content."""
        version_id = data.get("version_id")
        if not version_id:
            return {"error": "Missing version_id"}

        version = await self._temporal_repository.get_version(version_id)
        if not version:
            return {"error": "Version not found", "version_id": version_id}

        # Reconstruct content if needed
        content = await self._temporal_repository.reconstruct_content(version)

        return {
            "version_id": version.version_id,
            "capsule_id": version.capsule_id,
            "version_number": version.version_number,
            "content": content,
            "snapshot_type": version.snapshot_type.value,
            "change_type": version.change_type,
            "created_by": version.created_by,
            "created_at": version.created_at.isoformat(),
            "metadata": version.metadata
        }

    async def _get_capsule_at_time(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Get capsule state at a specific point in time."""
        capsule_id = data.get("capsule_id")
        timestamp_str = data.get("timestamp")

        if not capsule_id or not timestamp_str:
            return {"error": "Missing capsule_id or timestamp"}

        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        version = await self._temporal_repository.get_capsule_at_time(
            capsule_id=capsule_id,
            timestamp=timestamp
        )

        if not version:
            return {
                "capsule_id": capsule_id,
                "timestamp": timestamp.isoformat(),
                "found": False
            }

        content = await self._temporal_repository.reconstruct_content(version)

        return {
            "capsule_id": capsule_id,
            "timestamp": timestamp.isoformat(),
            "found": True,
            "version_id": version.version_id,
            "version_number": version.version_number,
            "content": content,
            "created_at": version.created_at.isoformat()
        }

    async def _get_trust_timeline(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Get trust evolution timeline for an entity."""
        entity_id = data.get("entity_id")
        entity_type = data.get("entity_type", "User")
        start_str = data.get("start")
        end_str = data.get("end")

        if not entity_id:
            return {"error": "Missing entity_id"}

        start = datetime.fromisoformat(start_str) if start_str else datetime.now(UTC) - timedelta(days=30)
        end = datetime.fromisoformat(end_str) if end_str else datetime.now(UTC)

        snapshots = await self._temporal_repository.get_trust_timeline(
            entity_id=entity_id,
            entity_type=entity_type,
            start=start,
            end=end
        )

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "snapshot_count": len(snapshots),
            "timeline": [
                {
                    "trust_value": s.trust_value,
                    "timestamp": s.timestamp.isoformat(),
                    "change_type": s.change_type.value,
                    "reason": s.reason
                }
                for s in snapshots
            ],
            "trust_min": min(s.trust_value for s in snapshots) if snapshots else None,
            "trust_max": max(s.trust_value for s in snapshots) if snapshots else None,
            "trust_current": snapshots[-1].trust_value if snapshots else None
        }

    async def _diff_versions(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Compute diff between two versions."""
        version_a = data.get("version_a")
        version_b = data.get("version_b")

        if not version_a or not version_b:
            return {"error": "Missing version_a or version_b"}

        diff = await self._temporal_repository.diff_versions(version_a, version_b)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "diff": diff
        }

    async def _create_graph_snapshot(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Create a graph snapshot."""
        snapshot = await self._temporal_repository.create_graph_snapshot()
        self._last_graph_snapshot = datetime.now(UTC)
        self._stats["graph_snapshots_created"] += 1

        return {
            "snapshot_id": snapshot.snapshot_id,
            "created_at": snapshot.created_at.isoformat(),
            "metrics": snapshot.metrics
        }

    async def _compact_versions(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Compact old versions to save storage."""
        capsule_id = data.get("capsule_id")
        older_than_days = data.get("older_than_days", self._config.compact_after_days)
        keep_min = data.get("keep_min", self._config.keep_min_versions)

        if capsule_id:
            result = await self._temporal_repository.compact_versions(
                capsule_id=capsule_id,
                older_than=datetime.now(UTC) - timedelta(days=older_than_days),
                keep_min=keep_min
            )
            self._stats["compactions_performed"] += 1
            return result
        else:
            # System-wide compaction
            return {"error": "capsule_id required for compaction"}

    async def _maybe_graph_snapshot(self, context: OverlayContext) -> None:
        """Create graph snapshot if due."""
        if not self._config.enable_graph_snapshots:
            return

        interval = timedelta(hours=self._config.graph_snapshot_interval_hours)

        if self._last_graph_snapshot is None:
            # Check if there's a recent one in the database
            recent = await self._temporal_repository.get_latest_graph_snapshot()
            if recent:
                self._last_graph_snapshot = recent.created_at

        if self._last_graph_snapshot is None or datetime.now(UTC) - self._last_graph_snapshot > interval:
            await self._create_graph_snapshot({}, context)

    def get_stats(self) -> dict:
        """Get temporal tracking statistics."""
        return {
            **self._stats,
            "tracked_capsules": len(self._version_counts),
            "last_graph_snapshot": self._last_graph_snapshot.isoformat() if self._last_graph_snapshot else None
        }


# Convenience function
def create_temporal_tracker_overlay(
    temporal_repository: TemporalRepository | None = None,
    **kwargs
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
