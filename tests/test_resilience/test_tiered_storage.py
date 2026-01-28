"""
Tests for Tiered Lineage Storage
================================

Tests for forge/resilience/lineage/tiered_storage.py
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.lineage.tiered_storage import (
    LineageEntry,
    StorageTier,
    TierStats,
    TieredLineageStorage,
    get_tiered_storage,
)


class TestStorageTier:
    """Tests for StorageTier enum."""

    def test_tier_values(self):
        """Test all tier values."""
        assert StorageTier.HOT.value == "hot"
        assert StorageTier.WARM.value == "warm"
        assert StorageTier.COLD.value == "cold"


class TestLineageEntry:
    """Tests for LineageEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a lineage entry."""
        entry = LineageEntry(
            entry_id="entry_123",
            capsule_id="cap_456",
            parent_id="cap_parent",
            relationship_type="DERIVED_FROM",
            created_at=datetime.now(UTC),
            trust_level=80,
        )

        assert entry.entry_id == "entry_123"
        assert entry.capsule_id == "cap_456"
        assert entry.parent_id == "cap_parent"
        assert entry.relationship_type == "DERIVED_FROM"
        assert entry.trust_level == 80
        assert entry.tier == StorageTier.HOT
        assert entry.compressed is False
        assert entry.archived_at is None

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        now = datetime.now(UTC)
        entry = LineageEntry(
            entry_id="entry_123",
            capsule_id="cap_456",
            parent_id=None,
            relationship_type="ROOT",
            created_at=now,
            trust_level=90,
            metadata={"source": "test"},
        )

        result = entry.to_dict()

        assert result["entry_id"] == "entry_123"
        assert result["capsule_id"] == "cap_456"
        assert result["parent_id"] is None
        assert result["relationship_type"] == "ROOT"
        assert result["trust_level"] == 90
        assert result["tier"] == "hot"
        assert result["compressed"] is False
        assert result["metadata"] == {"source": "test"}

    def test_entry_from_dict(self):
        """Test creating entry from dictionary."""
        now = datetime.now(UTC)
        data = {
            "entry_id": "entry_789",
            "capsule_id": "cap_abc",
            "parent_id": "cap_parent",
            "relationship_type": "REFERENCES",
            "created_at": now.isoformat(),
            "trust_level": 70,
            "metadata": {},
            "tier": "warm",
            "compressed": True,
            "archived_at": None,
            "last_accessed": now.isoformat(),
        }

        entry = LineageEntry.from_dict(data)

        assert entry.entry_id == "entry_789"
        assert entry.capsule_id == "cap_abc"
        assert entry.tier == StorageTier.WARM
        assert entry.compressed is True


class TestTierStats:
    """Tests for TierStats dataclass."""

    def test_stats_defaults(self):
        """Test default stats values."""
        stats = TierStats()

        assert stats.entry_count == 0
        assert stats.total_size_bytes == 0
        assert stats.oldest_entry is None
        assert stats.newest_entry is None
        assert stats.avg_trust_level == 0.0


class TestTieredLineageStorage:
    """Tests for TieredLineageStorage class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.tier1_max_age_days = 30
        config.tier2_max_age_days = 180
        config.tier1_min_trust = 80
        config.tier2_min_trust = 60
        return config

    @pytest.fixture
    def storage(self, mock_config):
        """Create a TieredLineageStorage instance."""
        with patch("forge.resilience.lineage.tiered_storage.get_resilience_config") as mock:
            mock.return_value.lineage = mock_config
            return TieredLineageStorage()

    @pytest.mark.asyncio
    async def test_initialize(self, storage):
        """Test storage initialization."""
        await storage.initialize()

        assert storage._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, mock_config):
        """Test initialization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.lineage.tiered_storage.get_resilience_config") as mock:
            mock.return_value.lineage = mock_config
            storage = TieredLineageStorage()
            await storage.initialize()

            assert storage._initialized is False

    @pytest.mark.asyncio
    async def test_close(self, storage):
        """Test closing storage."""
        await storage.initialize()
        await storage.close()

        # Migration task should be cancelled
        assert storage._migration_task is None or storage._migration_task.done()

    @pytest.mark.asyncio
    async def test_store_high_trust(self, storage):
        """Test storing high-trust entry goes to hot tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="entry_hot",
            capsule_id="cap_1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=90,
        )

        result = await storage.store(entry)

        assert result is True
        assert entry.tier == StorageTier.HOT
        assert "entry_hot" in storage._tier1_storage

    @pytest.mark.asyncio
    async def test_store_medium_trust(self, storage):
        """Test storing medium-trust entry goes to warm tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="entry_warm",
            capsule_id="cap_2",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=70,
        )

        result = await storage.store(entry)

        assert result is True
        assert entry.tier == StorageTier.WARM
        assert "entry_warm" in storage._tier2_storage
        assert entry.compressed is True

    @pytest.mark.asyncio
    async def test_store_low_trust(self, storage):
        """Test storing low-trust entry goes to cold tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="entry_cold",
            capsule_id="cap_3",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=50,
        )

        result = await storage.store(entry)

        assert result is True
        assert entry.tier == StorageTier.COLD
        assert "entry_cold" in storage._tier3_storage
        assert entry.archived_at is not None

    @pytest.mark.asyncio
    async def test_store_disabled(self, mock_config):
        """Test store returns True when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.lineage.tiered_storage.get_resilience_config") as mock:
            mock.return_value.lineage = mock_config
            storage = TieredLineageStorage()

            entry = LineageEntry(
                entry_id="entry_1",
                capsule_id="cap_1",
                parent_id=None,
                relationship_type="ROOT",
                created_at=datetime.now(UTC),
                trust_level=90,
            )

            result = await storage.store(entry)

            assert result is True

    @pytest.mark.asyncio
    async def test_get_from_hot(self, storage):
        """Test getting entry from hot tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="entry_get",
            capsule_id="cap_1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=90,
        )
        await storage.store(entry)

        result = await storage.get("entry_get")

        assert result is not None
        assert result.entry_id == "entry_get"

    @pytest.mark.asyncio
    async def test_get_from_warm(self, storage):
        """Test getting entry from warm tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="entry_warm_get",
            capsule_id="cap_2",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=70,
        )
        await storage.store(entry)

        result = await storage.get("entry_warm_get")

        assert result is not None
        assert result.entry_id == "entry_warm_get"

    @pytest.mark.asyncio
    async def test_get_not_found(self, storage):
        """Test getting nonexistent entry."""
        await storage.initialize()

        result = await storage.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_disabled(self, mock_config):
        """Test get returns None when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.lineage.tiered_storage.get_resilience_config") as mock:
            mock.return_value.lineage = mock_config
            storage = TieredLineageStorage()

            result = await storage.get("any_id")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_lineage_chain(self, storage):
        """Test getting lineage chain."""
        await storage.initialize()

        # Create a chain: cap_1 -> cap_2 -> cap_3
        entries = [
            LineageEntry(
                entry_id="e1",
                capsule_id="cap_1",
                parent_id="cap_2",
                relationship_type="DERIVED_FROM",
                created_at=datetime.now(UTC),
                trust_level=90,
            ),
            LineageEntry(
                entry_id="e2",
                capsule_id="cap_2",
                parent_id="cap_3",
                relationship_type="DERIVED_FROM",
                created_at=datetime.now(UTC),
                trust_level=90,
            ),
            LineageEntry(
                entry_id="e3",
                capsule_id="cap_3",
                parent_id=None,
                relationship_type="ROOT",
                created_at=datetime.now(UTC),
                trust_level=90,
            ),
        ]

        for entry in entries:
            await storage.store(entry)

        chain = await storage.get_lineage_chain("cap_1", depth=5)

        assert len(chain) == 3
        assert chain[0].capsule_id == "cap_1"
        assert chain[1].capsule_id == "cap_2"
        assert chain[2].capsule_id == "cap_3"

    @pytest.mark.asyncio
    async def test_get_lineage_chain_cycle_detection(self, storage):
        """Test lineage chain handles cycles."""
        await storage.initialize()

        # Create a cycle: cap_1 -> cap_2 -> cap_1
        entries = [
            LineageEntry(
                entry_id="e1",
                capsule_id="cap_1",
                parent_id="cap_2",
                relationship_type="DERIVED_FROM",
                created_at=datetime.now(UTC),
                trust_level=90,
            ),
            LineageEntry(
                entry_id="e2",
                capsule_id="cap_2",
                parent_id="cap_1",
                relationship_type="DERIVED_FROM",
                created_at=datetime.now(UTC),
                trust_level=90,
            ),
        ]

        for entry in entries:
            await storage.store(entry)

        chain = await storage.get_lineage_chain("cap_1", depth=10)

        # Should stop when cycle detected
        assert len(chain) == 2

    @pytest.mark.asyncio
    async def test_migrate_to_tier_hot_to_warm(self, storage):
        """Test migrating entry from hot to warm tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="migrate_entry",
            capsule_id="cap_1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=90,
        )
        await storage.store(entry)
        assert "migrate_entry" in storage._tier1_storage

        result = await storage.migrate_to_tier("migrate_entry", StorageTier.WARM)

        assert result is True
        assert "migrate_entry" not in storage._tier1_storage
        assert "migrate_entry" in storage._tier2_storage

    @pytest.mark.asyncio
    async def test_migrate_to_tier_warm_to_cold(self, storage):
        """Test migrating entry from warm to cold tier."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="migrate_entry_2",
            capsule_id="cap_2",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=70,
        )
        await storage.store(entry)
        assert "migrate_entry_2" in storage._tier2_storage

        result = await storage.migrate_to_tier("migrate_entry_2", StorageTier.COLD)

        assert result is True
        assert "migrate_entry_2" not in storage._tier2_storage
        assert "migrate_entry_2" in storage._tier3_storage

    @pytest.mark.asyncio
    async def test_migrate_to_tier_same_tier(self, storage):
        """Test migrating to same tier returns True."""
        await storage.initialize()

        entry = LineageEntry(
            entry_id="same_tier_entry",
            capsule_id="cap_1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=90,
        )
        await storage.store(entry)

        result = await storage.migrate_to_tier("same_tier_entry", StorageTier.HOT)

        assert result is True

    @pytest.mark.asyncio
    async def test_migrate_to_tier_not_found(self, storage):
        """Test migrating nonexistent entry."""
        await storage.initialize()

        result = await storage.migrate_to_tier("nonexistent", StorageTier.WARM)

        assert result is False

    def test_determine_initial_tier_high_trust(self, storage):
        """Test tier determination for high trust."""
        entry = LineageEntry(
            entry_id="e1",
            capsule_id="c1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=90,
        )

        tier = storage._determine_initial_tier(entry)

        assert tier == StorageTier.HOT

    def test_determine_initial_tier_medium_trust(self, storage):
        """Test tier determination for medium trust."""
        entry = LineageEntry(
            entry_id="e1",
            capsule_id="c1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=70,
        )

        tier = storage._determine_initial_tier(entry)

        assert tier == StorageTier.WARM

    def test_determine_initial_tier_low_trust(self, storage):
        """Test tier determination for low trust."""
        entry = LineageEntry(
            entry_id="e1",
            capsule_id="c1",
            parent_id=None,
            relationship_type="ROOT",
            created_at=datetime.now(UTC),
            trust_level=50,
        )

        tier = storage._determine_initial_tier(entry)

        assert tier == StorageTier.COLD

    def test_compress_decompress_entry(self, storage):
        """Test entry compression and decompression."""
        entry = LineageEntry(
            entry_id="compress_test",
            capsule_id="cap_1",
            parent_id="cap_parent",
            relationship_type="DERIVED_FROM",
            created_at=datetime.now(UTC),
            trust_level=75,
            metadata={"key": "value"},
        )

        compressed = storage._compress_entry(entry)
        decompressed = storage._decompress_entry(compressed)

        assert decompressed.entry_id == entry.entry_id
        assert decompressed.capsule_id == entry.capsule_id
        assert decompressed.parent_id == entry.parent_id
        assert decompressed.trust_level == entry.trust_level

    def test_get_tier_stats(self, storage):
        """Test getting tier statistics."""
        stats = storage.get_tier_stats()

        assert "hot" in stats
        assert "warm" in stats
        assert "cold" in stats
        assert isinstance(stats["hot"], TierStats)


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_tiered_storage(self):
        """Test getting global tiered storage."""
        with patch("forge.resilience.lineage.tiered_storage._tiered_storage", None):
            with patch("forge.resilience.lineage.tiered_storage.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.lineage.enabled = True
                mock_config.lineage.tier1_max_age_days = 30
                mock_config.lineage.tier2_max_age_days = 180
                mock_config.lineage.tier1_min_trust = 80
                mock_config.lineage.tier2_min_trust = 60
                mock.return_value = mock_config

                storage = await get_tiered_storage()

                assert isinstance(storage, TieredLineageStorage)
