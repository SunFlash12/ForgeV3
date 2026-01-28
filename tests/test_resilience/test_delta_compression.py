"""
Tests for Delta-Based Lineage Compression
=========================================

Tests for forge/resilience/lineage/delta_compression.py
"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from forge.resilience.lineage.delta_compression import (
    DeltaCompressor,
    DiffEntry,
    DiffOperation,
    LineageDiff,
    LineageSnapshot,
    get_delta_compressor,
)


class TestDiffOperation:
    """Tests for DiffOperation enum."""

    def test_operation_values(self):
        """Test all operation values."""
        assert DiffOperation.ADD.value == "add"
        assert DiffOperation.REMOVE.value == "remove"
        assert DiffOperation.MODIFY.value == "modify"
        assert DiffOperation.MOVE.value == "move"


class TestDiffEntry:
    """Tests for DiffEntry dataclass."""

    def test_entry_creation_add(self):
        """Test creating an add entry."""
        entry = DiffEntry(
            operation=DiffOperation.ADD,
            path="root.new_field",
            new_value="new_value",
        )

        assert entry.operation == DiffOperation.ADD
        assert entry.path == "root.new_field"
        assert entry.old_value is None
        assert entry.new_value == "new_value"
        assert entry.metadata == {}

    def test_entry_creation_modify(self):
        """Test creating a modify entry."""
        entry = DiffEntry(
            operation=DiffOperation.MODIFY,
            path="root.field",
            old_value="old",
            new_value="new",
            metadata={"reason": "update"},
        )

        assert entry.operation == DiffOperation.MODIFY
        assert entry.old_value == "old"
        assert entry.new_value == "new"
        assert entry.metadata == {"reason": "update"}

    def test_entry_creation_remove(self):
        """Test creating a remove entry."""
        entry = DiffEntry(
            operation=DiffOperation.REMOVE,
            path="root.removed_field",
            old_value="deleted_value",
        )

        assert entry.operation == DiffOperation.REMOVE
        assert entry.old_value == "deleted_value"
        assert entry.new_value is None


class TestLineageDiff:
    """Tests for LineageDiff dataclass."""

    def test_diff_creation(self):
        """Test creating a lineage diff."""
        entries = [
            DiffEntry(operation=DiffOperation.ADD, path="field1", new_value="value1"),
            DiffEntry(operation=DiffOperation.MODIFY, path="field2", old_value="a", new_value="b"),
        ]

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash="abc123",
            target_hash="def456",
            entries=entries,
            compression_ratio=0.5,
        )

        assert diff.diff_id == "diff_123"
        assert diff.base_hash == "abc123"
        assert diff.target_hash == "def456"
        assert len(diff.entries) == 2
        assert diff.compression_ratio == 0.5

    def test_diff_to_dict(self):
        """Test converting diff to dictionary."""
        entries = [
            DiffEntry(operation=DiffOperation.ADD, path="field", new_value="value"),
        ]

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash="abc",
            target_hash="def",
            entries=entries,
        )

        result = diff.to_dict()

        assert result["diff_id"] == "diff_123"
        assert result["base_hash"] == "abc"
        assert result["target_hash"] == "def"
        assert len(result["entries"]) == 1
        assert result["entries"][0]["operation"] == "add"
        assert result["entries"][0]["path"] == "field"

    def test_diff_from_dict(self):
        """Test creating diff from dictionary."""
        data = {
            "diff_id": "diff_456",
            "base_hash": "aaa",
            "target_hash": "bbb",
            "created_at": datetime.now(UTC).isoformat(),
            "entries": [
                {
                    "operation": "modify",
                    "path": "root.value",
                    "old_value": 1,
                    "new_value": 2,
                    "metadata": {"reason": "test"},
                }
            ],
            "compression_ratio": 0.75,
        }

        diff = LineageDiff.from_dict(data)

        assert diff.diff_id == "diff_456"
        assert len(diff.entries) == 1
        assert diff.entries[0].operation == DiffOperation.MODIFY
        assert diff.entries[0].old_value == 1
        assert diff.entries[0].new_value == 2
        assert diff.compression_ratio == 0.75


class TestLineageSnapshot:
    """Tests for LineageSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a snapshot."""
        data = {"capsule_id": "cap_123", "parent": "cap_parent"}

        snapshot = LineageSnapshot(
            snapshot_id="snap_123",
            capsule_id="cap_123",
            version=1,
            created_at=datetime.now(UTC),
            data=data,
        )

        assert snapshot.snapshot_id == "snap_123"
        assert snapshot.capsule_id == "cap_123"
        assert snapshot.version == 1
        assert snapshot.data == data
        assert len(snapshot.hash) == 16  # SHA-256 truncated to 16 chars

    def test_snapshot_hash_consistency(self):
        """Test that same data produces same hash."""
        data = {"key": "value", "number": 42}

        snap1 = LineageSnapshot(
            snapshot_id="s1",
            capsule_id="cap",
            version=1,
            created_at=datetime.now(UTC),
            data=data,
        )

        snap2 = LineageSnapshot(
            snapshot_id="s2",
            capsule_id="cap",
            version=2,
            created_at=datetime.now(UTC),
            data=data,
        )

        # Same data = same hash
        assert snap1.hash == snap2.hash

    def test_snapshot_hash_difference(self):
        """Test that different data produces different hash."""
        snap1 = LineageSnapshot(
            snapshot_id="s1",
            capsule_id="cap",
            version=1,
            created_at=datetime.now(UTC),
            data={"key": "value1"},
        )

        snap2 = LineageSnapshot(
            snapshot_id="s2",
            capsule_id="cap",
            version=1,
            created_at=datetime.now(UTC),
            data={"key": "value2"},
        )

        assert snap1.hash != snap2.hash


class TestDeltaCompressor:
    """Tests for DeltaCompressor class."""

    @pytest.fixture
    def compressor(self):
        """Create a DeltaCompressor instance."""
        return DeltaCompressor(max_delta_chain=5)

    def test_compressor_creation(self):
        """Test compressor creation with defaults."""
        compressor = DeltaCompressor()

        assert compressor._max_delta_chain == 10
        assert compressor._snapshots == {}
        assert compressor._deltas == {}

    def test_create_snapshot(self, compressor):
        """Test creating a snapshot."""
        data = {"capsule": "cap_123", "parents": ["cap_parent"]}

        snapshot = compressor.create_snapshot("cap_123", data, version=1)

        assert snapshot.capsule_id == "cap_123"
        assert snapshot.version == 1
        assert snapshot.data == data
        assert snapshot.snapshot_id in compressor._snapshots
        assert compressor._stats["snapshots_created"] == 1

    def test_compute_diff_add(self, compressor):
        """Test computing diff with additions."""
        old_snapshot = compressor.create_snapshot("cap_1", {"key1": "value1"}, version=1)
        new_snapshot = compressor.create_snapshot(
            "cap_1",
            {"key1": "value1", "key2": "value2"},
            version=2,
        )

        diff = compressor.compute_diff(old_snapshot, new_snapshot)

        assert diff.base_hash == old_snapshot.hash
        assert diff.target_hash == new_snapshot.hash
        assert len(diff.entries) == 1
        assert diff.entries[0].operation == DiffOperation.ADD
        assert diff.entries[0].path == "key2"
        assert diff.entries[0].new_value == "value2"

    def test_compute_diff_remove(self, compressor):
        """Test computing diff with removals."""
        old_snapshot = compressor.create_snapshot(
            "cap_1",
            {"key1": "value1", "key2": "value2"},
            version=1,
        )
        new_snapshot = compressor.create_snapshot("cap_1", {"key1": "value1"}, version=2)

        diff = compressor.compute_diff(old_snapshot, new_snapshot)

        assert len(diff.entries) == 1
        assert diff.entries[0].operation == DiffOperation.REMOVE
        assert diff.entries[0].path == "key2"
        assert diff.entries[0].old_value == "value2"

    def test_compute_diff_modify(self, compressor):
        """Test computing diff with modifications."""
        old_snapshot = compressor.create_snapshot("cap_1", {"key": "old_value"}, version=1)
        new_snapshot = compressor.create_snapshot("cap_1", {"key": "new_value"}, version=2)

        diff = compressor.compute_diff(old_snapshot, new_snapshot)

        assert len(diff.entries) == 1
        assert diff.entries[0].operation == DiffOperation.MODIFY
        assert diff.entries[0].path == "key"
        assert diff.entries[0].old_value == "old_value"
        assert diff.entries[0].new_value == "new_value"

    def test_compute_diff_nested(self, compressor):
        """Test computing diff with nested structures."""
        old_data = {
            "level1": {
                "level2": {"value": 1},
            }
        }
        new_data = {
            "level1": {
                "level2": {"value": 2},
            }
        }

        old_snapshot = compressor.create_snapshot("cap_1", old_data, version=1)
        new_snapshot = compressor.create_snapshot("cap_1", new_data, version=2)

        diff = compressor.compute_diff(old_snapshot, new_snapshot)

        assert len(diff.entries) == 1
        assert diff.entries[0].path == "level1.level2.value"
        assert diff.entries[0].old_value == 1
        assert diff.entries[0].new_value == 2

    def test_compute_diff_lists(self, compressor):
        """Test computing diff with list changes."""
        old_data = {"items": [1, 2, 3]}
        new_data = {"items": [1, 2, 3, 4]}

        old_snapshot = compressor.create_snapshot("cap_1", old_data, version=1)
        new_snapshot = compressor.create_snapshot("cap_1", new_data, version=2)

        diff = compressor.compute_diff(old_snapshot, new_snapshot)

        assert len(diff.entries) == 1
        assert diff.entries[0].operation == DiffOperation.ADD
        assert diff.entries[0].path == "items[3]"
        assert diff.entries[0].new_value == 4

    def test_apply_diff_add(self, compressor):
        """Test applying add diff."""
        base_snapshot = compressor.create_snapshot("cap_1", {"key1": "value1"}, version=1)
        target_data = {"key1": "value1", "key2": "value2"}

        # Create target snapshot to get its hash
        target_snapshot = LineageSnapshot(
            snapshot_id="target",
            capsule_id="cap_1",
            version=2,
            created_at=datetime.now(UTC),
            data=target_data,
        )

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash=base_snapshot.hash,
            target_hash=target_snapshot.hash,
            entries=[
                DiffEntry(
                    operation=DiffOperation.ADD,
                    path="key2",
                    new_value="value2",
                )
            ],
        )

        result = compressor.apply_diff(base_snapshot, diff)

        assert result.data == target_data

    def test_apply_diff_remove(self, compressor):
        """Test applying remove diff."""
        base_data = {"key1": "value1", "key2": "value2"}
        target_data = {"key1": "value1"}

        base_snapshot = compressor.create_snapshot("cap_1", base_data, version=1)
        target_snapshot = LineageSnapshot(
            snapshot_id="target",
            capsule_id="cap_1",
            version=2,
            created_at=datetime.now(UTC),
            data=target_data,
        )

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash=base_snapshot.hash,
            target_hash=target_snapshot.hash,
            entries=[
                DiffEntry(
                    operation=DiffOperation.REMOVE,
                    path="key2",
                    old_value="value2",
                )
            ],
        )

        result = compressor.apply_diff(base_snapshot, diff)

        assert result.data == target_data

    def test_apply_diff_modify(self, compressor):
        """Test applying modify diff."""
        base_snapshot = compressor.create_snapshot("cap_1", {"key": "old"}, version=1)
        target_data = {"key": "new"}

        target_snapshot = LineageSnapshot(
            snapshot_id="target",
            capsule_id="cap_1",
            version=2,
            created_at=datetime.now(UTC),
            data=target_data,
        )

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash=base_snapshot.hash,
            target_hash=target_snapshot.hash,
            entries=[
                DiffEntry(
                    operation=DiffOperation.MODIFY,
                    path="key",
                    old_value="old",
                    new_value="new",
                )
            ],
        )

        result = compressor.apply_diff(base_snapshot, diff)

        assert result.data == target_data

    def test_apply_diff_hash_mismatch(self, compressor):
        """Test that applying diff with wrong base hash raises error."""
        base_snapshot = compressor.create_snapshot("cap_1", {"key": "value"}, version=1)

        diff = LineageDiff(
            diff_id="diff_123",
            base_hash="wrong_hash",
            target_hash="target_hash",
            entries=[],
        )

        with pytest.raises(ValueError, match="Base hash mismatch"):
            compressor.apply_diff(base_snapshot, diff)

    def test_store_delta(self, compressor):
        """Test storing a delta."""
        diff = LineageDiff(
            diff_id="diff_123",
            base_hash="abc",
            target_hash="def",
            entries=[],
        )

        compressor.store_delta("cap_1", diff)

        assert "cap_1" in compressor._deltas
        assert len(compressor._deltas["cap_1"]) == 1
        assert compressor._deltas["cap_1"][0] == diff

    def test_store_delta_chain_limit(self, compressor):
        """Test that delta chain tracks consolidation needed."""
        for i in range(5):
            diff = LineageDiff(
                diff_id=f"diff_{i}",
                base_hash=f"base_{i}",
                target_hash=f"target_{i}",
                entries=[],
            )
            compressor.store_delta("cap_1", diff)

        assert len(compressor._deltas["cap_1"]) == 5

    def test_get_deltas(self, compressor):
        """Test getting deltas for a capsule."""
        diff1 = LineageDiff(
            diff_id="diff_1",
            base_hash="a",
            target_hash="b",
            entries=[],
        )
        diff2 = LineageDiff(
            diff_id="diff_2",
            base_hash="b",
            target_hash="c",
            entries=[],
        )

        compressor.store_delta("cap_1", diff1)
        compressor.store_delta("cap_1", diff2)

        deltas = compressor.get_deltas("cap_1")

        assert len(deltas) == 2
        assert deltas[0].diff_id == "diff_1"
        assert deltas[1].diff_id == "diff_2"

    def test_get_deltas_empty(self, compressor):
        """Test getting deltas for nonexistent capsule."""
        deltas = compressor.get_deltas("nonexistent")

        assert deltas == []

    def test_compress_snapshot(self, compressor):
        """Test compressing a snapshot."""
        data = {"key": "value", "nested": {"data": [1, 2, 3]}}
        snapshot = compressor.create_snapshot("cap_1", data, version=1)

        compressed = compressor.compress_snapshot(snapshot)

        assert isinstance(compressed, bytes)
        # Compressed should be smaller or similar for small data
        assert len(compressed) > 0

    def test_decompress_snapshot(self, compressor):
        """Test decompressing a snapshot."""
        data = {"key": "value", "nested": {"data": [1, 2, 3]}}
        snapshot = compressor.create_snapshot("cap_1", data, version=1)

        compressed = compressor.compress_snapshot(snapshot)
        decompressed = compressor.decompress_snapshot(compressed, "new_snap", "cap_1")

        assert decompressed.data == data
        assert decompressed.snapshot_id == "new_snap"
        assert decompressed.capsule_id == "cap_1"

    def test_get_stats(self, compressor):
        """Test getting compression stats."""
        compressor.create_snapshot("cap_1", {"key": "value"}, version=1)
        compressor.create_snapshot("cap_1", {"key": "value2"}, version=2)

        stats = compressor.get_stats()

        assert stats["snapshots_created"] == 2
        assert "deltas_created" in stats
        assert "bytes_saved" in stats

    def test_parse_path_simple(self, compressor):
        """Test parsing simple path."""
        path = "root.child.value"

        parts = compressor._parse_path(path)

        assert parts == ["root", "child", "value"]

    def test_parse_path_with_array(self, compressor):
        """Test parsing path with array indices."""
        path = "root.items[0].value"

        parts = compressor._parse_path(path)

        assert parts == ["root", "items", 0, "value"]

    def test_parse_path_empty(self, compressor):
        """Test parsing empty path."""
        parts = compressor._parse_path("")

        assert parts == []


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_delta_compressor(self):
        """Test getting global delta compressor."""
        with patch("forge.resilience.lineage.delta_compression._delta_compressor", None):
            compressor = get_delta_compressor()

            assert isinstance(compressor, DeltaCompressor)
