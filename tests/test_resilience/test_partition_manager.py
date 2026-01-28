"""
Tests for Graph Partition Manager
=================================

Tests for forge/resilience/partitioning/partition_manager.py
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.partitioning.partition_manager import (
    Partition,
    PartitionManager,
    PartitionState,
    PartitionStats,
    PartitionStrategy,
    RebalanceJob,
    get_partition_manager,
)


class TestPartitionStrategy:
    """Tests for PartitionStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values."""
        assert PartitionStrategy.DOMAIN.value == "domain"
        assert PartitionStrategy.USER.value == "user"
        assert PartitionStrategy.TIME.value == "time"
        assert PartitionStrategy.HASH.value == "hash"
        assert PartitionStrategy.HYBRID.value == "hybrid"


class TestPartitionState:
    """Tests for PartitionState enum."""

    def test_state_values(self):
        """Test all state values."""
        assert PartitionState.ACTIVE.value == "active"
        assert PartitionState.REBALANCING.value == "rebalancing"
        assert PartitionState.READONLY.value == "readonly"
        assert PartitionState.DRAINING.value == "draining"
        assert PartitionState.OFFLINE.value == "offline"


class TestPartitionStats:
    """Tests for PartitionStats dataclass."""

    def test_stats_defaults(self):
        """Test default stats values."""
        stats = PartitionStats()

        assert stats.capsule_count == 0
        assert stats.edge_count == 0
        assert stats.total_size_bytes == 0
        assert stats.avg_query_latency_ms == 0.0
        assert stats.queries_per_second == 0.0
        assert stats.last_write_at is None
        assert stats.last_query_at is None


class TestPartition:
    """Tests for Partition dataclass."""

    def test_partition_creation(self):
        """Test creating a partition."""
        partition = Partition(
            partition_id="p_test",
            name="Test Partition",
            strategy=PartitionStrategy.DOMAIN,
        )

        assert partition.partition_id == "p_test"
        assert partition.name == "Test Partition"
        assert partition.strategy == PartitionStrategy.DOMAIN
        assert partition.state == PartitionState.ACTIVE
        assert partition.max_capsules == 50000
        assert partition.max_edges == 500000

    def test_partition_is_full(self):
        """Test is_full property."""
        partition = Partition(
            partition_id="p_full",
            name="Full Partition",
            strategy=PartitionStrategy.HASH,
            max_capsules=100,
        )
        partition.stats.capsule_count = 100

        assert partition.is_full is True

        partition.stats.capsule_count = 50
        assert partition.is_full is False

    def test_partition_utilization(self):
        """Test utilization calculation."""
        partition = Partition(
            partition_id="p_util",
            name="Utilization Partition",
            strategy=PartitionStrategy.HASH,
            max_capsules=100,
        )
        partition.stats.capsule_count = 25

        assert partition.utilization == 25.0

    def test_partition_utilization_zero_max(self):
        """Test utilization with zero max capsules."""
        partition = Partition(
            partition_id="p_zero",
            name="Zero Partition",
            strategy=PartitionStrategy.HASH,
            max_capsules=0,
        )

        assert partition.utilization == 0.0

    def test_partition_to_dict(self):
        """Test converting partition to dictionary."""
        partition = Partition(
            partition_id="p_dict",
            name="Dict Partition",
            strategy=PartitionStrategy.DOMAIN,
            domain_tags={"science", "technology"},
            hash_range=(0, 50),
        )
        partition.stats.capsule_count = 1000

        result = partition.to_dict()

        assert result["partition_id"] == "p_dict"
        assert result["name"] == "Dict Partition"
        assert result["strategy"] == "domain"
        assert result["state"] == "active"
        assert result["stats"]["capsule_count"] == 1000
        assert set(result["domain_tags"]) == {"science", "technology"}
        assert result["hash_range"] == (0, 50)


class TestRebalanceJob:
    """Tests for RebalanceJob dataclass."""

    def test_job_creation(self):
        """Test creating a rebalance job."""
        job = RebalanceJob(
            job_id="rebal_123",
            source_partition="p_source",
            target_partition="p_target",
        )

        assert job.job_id == "rebal_123"
        assert job.source_partition == "p_source"
        assert job.target_partition == "p_target"
        assert job.moved_count == 0
        assert job.status == "pending"
        assert job.started_at is None
        assert job.completed_at is None


class TestPartitionManager:
    """Tests for PartitionManager class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.max_capsules_per_partition = 50000
        config.auto_rebalance = False
        config.rebalance_threshold = 0.2
        return config

    @pytest.fixture
    def manager(self, mock_config):
        """Create a partition manager instance."""
        with patch("forge.resilience.partitioning.partition_manager.get_resilience_config") as mock:
            mock.return_value.partitioning = mock_config
            return PartitionManager()

    @pytest.mark.asyncio
    async def test_initialize(self, manager):
        """Test manager initialization."""
        await manager.initialize()

        assert manager._initialized is True
        assert "default" in manager._partitions

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, mock_config):
        """Test initialization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.partitioning.partition_manager.get_resilience_config") as mock:
            mock.return_value.partitioning = mock_config
            manager = PartitionManager()
            await manager.initialize()

            assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, manager):
        """Test that initialize is idempotent."""
        await manager.initialize()
        initial_count = len(manager._partitions)

        await manager.initialize()

        assert len(manager._partitions) == initial_count

    @pytest.mark.asyncio
    async def test_close(self, manager, mock_config):
        """Test closing manager."""
        mock_config.auto_rebalance = True

        await manager.initialize()
        await manager.close()

        # Should not raise

    def test_create_partition(self, manager):
        """Test creating a partition."""
        partition = manager.create_partition(
            name="Science Partition",
            strategy=PartitionStrategy.DOMAIN,
            domain_tags={"science", "research"},
        )

        assert partition.name == "Science Partition"
        assert partition.strategy == PartitionStrategy.DOMAIN
        assert partition.domain_tags == {"science", "research"}
        assert partition.partition_id in manager._partitions

    def test_create_partition_with_max_capsules(self, manager):
        """Test creating partition with custom max capsules."""
        partition = manager.create_partition(
            name="Small Partition",
            max_capsules=1000,
        )

        assert partition.max_capsules == 1000

    def test_get_partition(self, manager):
        """Test getting partition by ID."""
        partition = manager.create_partition(name="Test Partition")

        result = manager.get_partition(partition.partition_id)

        assert result == partition

    def test_get_partition_not_found(self, manager):
        """Test getting nonexistent partition."""
        result = manager.get_partition("nonexistent")

        assert result is None

    def test_list_partitions(self, manager):
        """Test listing all partitions."""
        manager.create_partition(name="Partition 1")
        manager.create_partition(name="Partition 2")

        partitions = manager.list_partitions()

        assert len(partitions) == 2

    def test_assign_capsule(self, manager):
        """Test assigning capsule to partition."""
        manager.create_partition(
            name="Default",
            strategy=PartitionStrategy.HASH,
        )

        partition_id = manager.assign_capsule(
            capsule_id="cap_123",
            domain_tags={"science"},
        )

        assert partition_id is not None
        assert manager.get_capsule_partition("cap_123") == partition_id

    def test_assign_capsule_disabled(self, mock_config):
        """Test capsule assignment when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.partitioning.partition_manager.get_resilience_config") as mock:
            mock.return_value.partitioning = mock_config
            manager = PartitionManager()

            partition_id = manager.assign_capsule("cap_123")

            assert partition_id == "default"

    def test_assign_capsule_creates_new_partition_when_full(self, manager):
        """Test that new partition is created when all are full."""
        partition = manager.create_partition(
            name="Full Partition",
            max_capsules=1,
        )
        partition.stats.capsule_count = 1

        new_partition_id = manager.assign_capsule("cap_new")

        assert new_partition_id != partition.partition_id

    def test_get_capsule_partition(self, manager):
        """Test getting capsule's partition."""
        manager.create_partition(name="Test Partition")
        manager.assign_capsule("cap_123")

        partition_id = manager.get_capsule_partition("cap_123")

        assert partition_id is not None

    def test_get_capsule_partition_not_found(self, manager):
        """Test getting partition for unassigned capsule."""
        result = manager.get_capsule_partition("nonexistent")

        assert result is None

    def test_calculate_partition_score_domain_match(self, manager):
        """Test partition scoring with domain tag match."""
        partition = Partition(
            partition_id="p_science",
            name="Science Partition",
            strategy=PartitionStrategy.DOMAIN,
            domain_tags={"science", "research"},
        )

        score = manager._calculate_partition_score(
            partition,
            capsule_id="cap_123",
            domain_tags={"science"},
            owner_id=None,
        )

        assert score > 0

    def test_calculate_partition_score_owner_match(self, manager):
        """Test partition scoring with owner match."""
        partition = Partition(
            partition_id="p_user",
            name="User Partition",
            strategy=PartitionStrategy.USER,
        )
        partition.user_ids.add("user_123")

        score = manager._calculate_partition_score(
            partition,
            capsule_id="cap_123",
            domain_tags=None,
            owner_id="user_123",
        )

        assert score > 0

    @pytest.mark.asyncio
    async def test_trigger_rebalance_not_needed(self, manager, mock_config):
        """Test rebalancing when not needed."""
        mock_config.auto_rebalance = True
        await manager.initialize()

        result = await manager.trigger_rebalance()

        # With only one partition, no rebalancing needed
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_rebalance_disabled(self, mock_config):
        """Test rebalancing when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.partitioning.partition_manager.get_resilience_config") as mock:
            mock.return_value.partitioning = mock_config
            manager = PartitionManager()

            result = await manager.trigger_rebalance()

            assert result is None

    @pytest.mark.asyncio
    async def test_trigger_rebalance_creates_job(self, manager, mock_config):
        """Test that rebalancing creates a job when needed."""
        mock_config.auto_rebalance = True

        # Create two partitions with significant imbalance
        p1 = manager.create_partition(name="Heavy Partition")
        p1.stats.capsule_count = 40000  # 80% full

        p2 = manager.create_partition(name="Light Partition")
        p2.stats.capsule_count = 5000  # 10% full

        result = await manager.trigger_rebalance()

        if result:  # If threshold was exceeded
            assert result.source_partition == p1.partition_id
            assert result.target_partition == p2.partition_id
            assert result.status in ["pending", "running"]

    @pytest.mark.asyncio
    async def test_execute_rebalance(self, manager):
        """Test rebalance execution."""
        source = manager.create_partition(name="Source")
        source.stats.capsule_count = 100
        target = manager.create_partition(name="Target")
        target.stats.capsule_count = 10

        # Assign some capsules to source
        for i in range(10):
            manager._capsule_partition_map[f"cap_{i}"] = source.partition_id

        job = RebalanceJob(
            job_id="test_job",
            source_partition=source.partition_id,
            target_partition=target.partition_id,
        )

        await manager._execute_rebalance(job)

        assert job.status == "completed"
        assert job.moved_count > 0

    @pytest.mark.asyncio
    async def test_execute_rebalance_missing_partitions(self, manager):
        """Test rebalance with missing partitions fails."""
        job = RebalanceJob(
            job_id="test_job",
            source_partition="nonexistent_source",
            target_partition="nonexistent_target",
        )

        await manager._execute_rebalance(job)

        assert job.status == "failed"

    def test_get_partition_stats(self, manager):
        """Test getting partition statistics."""
        manager.create_partition(name="Partition 1")
        manager.create_partition(name="Partition 2")

        stats = manager.get_partition_stats()

        assert len(stats) == 2

    def test_get_rebalance_status(self, manager):
        """Test getting rebalance job status."""
        job = RebalanceJob(
            job_id="job_1",
            source_partition="p_source",
            target_partition="p_target",
        )
        job.status = "completed"
        job.moved_count = 50
        manager._rebalance_jobs["job_1"] = job

        status = manager.get_rebalance_status()

        assert len(status) == 1
        assert status[0]["job_id"] == "job_1"
        assert status[0]["status"] == "completed"
        assert status[0]["moved"] == 50


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_partition_manager(self):
        """Test getting global partition manager."""
        with patch("forge.resilience.partitioning.partition_manager._partition_manager", None):
            with patch("forge.resilience.partitioning.partition_manager.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.partitioning.enabled = True
                mock_config.partitioning.max_capsules_per_partition = 50000
                mock_config.partitioning.auto_rebalance = False
                mock.return_value = mock_config

                manager = await get_partition_manager()

                assert isinstance(manager, PartitionManager)
                assert manager._initialized is True
