"""
Delta-Based Lineage Compression
===============================

Efficient storage of lineage changes using delta encoding.
Reduces storage requirements by storing only differences between versions.
"""

from __future__ import annotations

import hashlib
import json
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class DiffOperation(Enum):
    """Types of diff operations."""

    ADD = "add"           # New field/value added
    REMOVE = "remove"     # Field/value removed
    MODIFY = "modify"     # Value changed
    MOVE = "move"         # Position changed (for arrays)


@dataclass
class DiffEntry:
    """Represents a single difference in a delta."""

    operation: DiffOperation
    path: str                      # JSONPath to the changed element
    old_value: Any | None = None
    new_value: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageDiff:
    """Represents the difference between two lineage snapshots."""

    diff_id: str
    base_hash: str                 # Hash of the base snapshot
    target_hash: str               # Hash of the resulting snapshot
    created_at: datetime = field(default_factory=datetime.utcnow)
    entries: list[DiffEntry] = field(default_factory=list)
    compression_ratio: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "diff_id": self.diff_id,
            "base_hash": self.base_hash,
            "target_hash": self.target_hash,
            "created_at": self.created_at.isoformat(),
            "entries": [
                {
                    "operation": e.operation.value,
                    "path": e.path,
                    "old_value": e.old_value,
                    "new_value": e.new_value,
                    "metadata": e.metadata,
                }
                for e in self.entries
            ],
            "compression_ratio": self.compression_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LineageDiff:
        """Create from dictionary."""
        entries = [
            DiffEntry(
                operation=DiffOperation(e["operation"]),
                path=e["path"],
                old_value=e.get("old_value"),
                new_value=e.get("new_value"),
                metadata=e.get("metadata", {}),
            )
            for e in data.get("entries", [])
        ]

        return cls(
            diff_id=data["diff_id"],
            base_hash=data["base_hash"],
            target_hash=data["target_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            entries=entries,
            compression_ratio=data.get("compression_ratio", 1.0),
        )


@dataclass
class LineageSnapshot:
    """A complete snapshot of lineage state."""

    snapshot_id: str
    capsule_id: str
    version: int
    created_at: datetime
    data: dict[str, Any]
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute hash of snapshot data."""
        content = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class DeltaCompressor:
    """
    Delta-based compression for lineage data.

    Stores lineage history as a base snapshot plus a chain of deltas,
    reducing storage requirements for frequently changing lineage graphs.
    """

    def __init__(self, max_delta_chain: int = 10):
        self._max_delta_chain = max_delta_chain
        self._snapshots: dict[str, LineageSnapshot] = {}
        self._deltas: dict[str, list[LineageDiff]] = {}  # capsule_id -> deltas
        self._stats = {
            "snapshots_created": 0,
            "deltas_created": 0,
            "bytes_saved": 0,
        }

    def create_snapshot(
        self,
        capsule_id: str,
        data: dict[str, Any],
        version: int = 1
    ) -> LineageSnapshot:
        """
        Create a new lineage snapshot.

        Args:
            capsule_id: ID of the root capsule
            data: Lineage data to snapshot
            version: Version number

        Returns:
            Created snapshot
        """
        snapshot = LineageSnapshot(
            snapshot_id=f"{capsule_id}_v{version}_{datetime.utcnow().timestamp()}",
            capsule_id=capsule_id,
            version=version,
            created_at=datetime.utcnow(),
            data=data,
        )

        self._snapshots[snapshot.snapshot_id] = snapshot
        self._stats["snapshots_created"] += 1

        logger.debug(
            "lineage_snapshot_created",
            snapshot_id=snapshot.snapshot_id,
            hash=snapshot.hash
        )

        return snapshot

    def compute_diff(
        self,
        old_snapshot: LineageSnapshot,
        new_snapshot: LineageSnapshot
    ) -> LineageDiff:
        """
        Compute the difference between two snapshots.

        Args:
            old_snapshot: Base snapshot
            new_snapshot: Target snapshot

        Returns:
            LineageDiff containing the changes
        """
        entries = self._diff_dicts("", old_snapshot.data, new_snapshot.data)

        # Calculate compression ratio
        len(json.dumps(old_snapshot.data))
        new_size = len(json.dumps(new_snapshot.data))
        diff_size = len(json.dumps([e.new_value for e in entries]))
        compression_ratio = diff_size / new_size if new_size > 0 else 1.0

        diff = LineageDiff(
            diff_id=f"diff_{old_snapshot.hash}_{new_snapshot.hash}",
            base_hash=old_snapshot.hash,
            target_hash=new_snapshot.hash,
            entries=entries,
            compression_ratio=compression_ratio,
        )

        self._stats["deltas_created"] += 1
        self._stats["bytes_saved"] += max(0, new_size - diff_size)

        logger.debug(
            "lineage_diff_computed",
            diff_id=diff.diff_id,
            entries=len(entries),
            compression_ratio=compression_ratio
        )

        return diff

    def _diff_dicts(
        self,
        path: str,
        old: dict[str, Any],
        new: dict[str, Any]
    ) -> list[DiffEntry]:
        """Recursively compute differences between dictionaries."""
        entries = []

        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            key_path = f"{path}.{key}" if path else key

            if key not in old:
                # Added
                entries.append(DiffEntry(
                    operation=DiffOperation.ADD,
                    path=key_path,
                    new_value=new[key],
                ))
            elif key not in new:
                # Removed
                entries.append(DiffEntry(
                    operation=DiffOperation.REMOVE,
                    path=key_path,
                    old_value=old[key],
                ))
            elif old[key] != new[key]:
                # Modified
                if isinstance(old[key], dict) and isinstance(new[key], dict):
                    # Recurse for nested dicts
                    entries.extend(self._diff_dicts(key_path, old[key], new[key]))
                elif isinstance(old[key], list) and isinstance(new[key], list):
                    # Handle list diffs
                    entries.extend(self._diff_lists(key_path, old[key], new[key]))
                else:
                    entries.append(DiffEntry(
                        operation=DiffOperation.MODIFY,
                        path=key_path,
                        old_value=old[key],
                        new_value=new[key],
                    ))

        return entries

    def _diff_lists(
        self,
        path: str,
        old: list[Any],
        new: list[Any]
    ) -> list[DiffEntry]:
        """Compute differences between lists."""
        entries = []

        # Simple approach: track additions/removals by index
        max_len = max(len(old), len(new))

        for i in range(max_len):
            item_path = f"{path}[{i}]"

            if i >= len(old):
                # Added
                entries.append(DiffEntry(
                    operation=DiffOperation.ADD,
                    path=item_path,
                    new_value=new[i],
                ))
            elif i >= len(new):
                # Removed
                entries.append(DiffEntry(
                    operation=DiffOperation.REMOVE,
                    path=item_path,
                    old_value=old[i],
                ))
            elif old[i] != new[i]:
                # Modified
                if isinstance(old[i], dict) and isinstance(new[i], dict):
                    entries.extend(self._diff_dicts(item_path, old[i], new[i]))
                else:
                    entries.append(DiffEntry(
                        operation=DiffOperation.MODIFY,
                        path=item_path,
                        old_value=old[i],
                        new_value=new[i],
                    ))

        return entries

    def apply_diff(
        self,
        base_snapshot: LineageSnapshot,
        diff: LineageDiff
    ) -> LineageSnapshot:
        """
        Apply a diff to a base snapshot to reconstruct target state.

        Args:
            base_snapshot: Base snapshot to apply diff to
            diff: Diff to apply

        Returns:
            Reconstructed snapshot
        """
        # Verify base hash matches
        if base_snapshot.hash != diff.base_hash:
            raise ValueError(
                f"Base hash mismatch: {base_snapshot.hash} != {diff.base_hash}"
            )

        # Deep copy base data
        result_data = json.loads(json.dumps(base_snapshot.data))

        # Apply each diff entry
        for entry in diff.entries:
            self._apply_entry(result_data, entry)

        # Create new snapshot
        result = LineageSnapshot(
            snapshot_id=f"reconstructed_{diff.target_hash}",
            capsule_id=base_snapshot.capsule_id,
            version=base_snapshot.version + 1,
            created_at=datetime.utcnow(),
            data=result_data,
        )

        # Verify result hash
        if result.hash != diff.target_hash:
            logger.warning(
                "diff_application_hash_mismatch",
                expected=diff.target_hash,
                actual=result.hash
            )

        return result

    def _apply_entry(self, data: dict[str, Any], entry: DiffEntry) -> None:
        """Apply a single diff entry to data."""
        path_parts = self._parse_path(entry.path)

        if not path_parts:
            return

        # Navigate to parent
        current = data
        for part in path_parts[:-1]:
            if isinstance(part, int):
                current = current[part]
            else:
                current = current[part]

        # Apply operation
        final_key = path_parts[-1]

        if entry.operation == DiffOperation.ADD:
            if isinstance(final_key, int):
                current.insert(final_key, entry.new_value)
            else:
                current[final_key] = entry.new_value

        elif entry.operation == DiffOperation.REMOVE:
            if isinstance(final_key, int):
                del current[final_key]
            else:
                del current[final_key]

        elif entry.operation == DiffOperation.MODIFY:
            current[final_key] = entry.new_value

    def _parse_path(self, path: str) -> list[Any]:
        """Parse a JSONPath-like string into components."""
        if not path:
            return []

        parts = []
        current = ""

        i = 0
        while i < len(path):
            if path[i] == '.':
                if current:
                    parts.append(current)
                    current = ""
            elif path[i] == '[':
                if current:
                    parts.append(current)
                    current = ""
                # Find closing bracket
                j = path.index(']', i)
                index = int(path[i+1:j])
                parts.append(index)
                i = j
            else:
                current += path[i]
            i += 1

        if current:
            parts.append(current)

        return parts

    def store_delta(self, capsule_id: str, diff: LineageDiff) -> None:
        """
        Store a delta for a capsule's lineage.

        Args:
            capsule_id: Capsule ID
            diff: Delta to store
        """
        if capsule_id not in self._deltas:
            self._deltas[capsule_id] = []

        self._deltas[capsule_id].append(diff)

        # Check if we need to consolidate (create new snapshot)
        if len(self._deltas[capsule_id]) >= self._max_delta_chain:
            logger.info(
                "delta_chain_consolidation_needed",
                capsule_id=capsule_id,
                delta_count=len(self._deltas[capsule_id])
            )
            # In production, would trigger snapshot consolidation

    def get_deltas(self, capsule_id: str) -> list[LineageDiff]:
        """Get all deltas for a capsule."""
        return self._deltas.get(capsule_id, [])

    def compress_snapshot(self, snapshot: LineageSnapshot) -> bytes:
        """
        Compress a snapshot for storage.

        Args:
            snapshot: Snapshot to compress

        Returns:
            Compressed bytes
        """
        data = json.dumps(snapshot.data, sort_keys=True).encode('utf-8')
        return zlib.compress(data, level=9)

    def decompress_snapshot(
        self,
        compressed: bytes,
        snapshot_id: str,
        capsule_id: str
    ) -> LineageSnapshot:
        """
        Decompress a stored snapshot.

        Args:
            compressed: Compressed data
            snapshot_id: ID for the snapshot
            capsule_id: Capsule ID

        Returns:
            Decompressed snapshot
        """
        data = json.loads(zlib.decompress(compressed))
        return LineageSnapshot(
            snapshot_id=snapshot_id,
            capsule_id=capsule_id,
            version=1,
            created_at=datetime.utcnow(),
            data=data,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get compression statistics."""
        return dict(self._stats)


# Global compressor instance
_delta_compressor: DeltaCompressor | None = None


def get_delta_compressor() -> DeltaCompressor:
    """Get or create the global delta compressor instance."""
    global _delta_compressor
    if _delta_compressor is None:
        _delta_compressor = DeltaCompressor()
    return _delta_compressor
