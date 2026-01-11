"""
Graph Partition Manager
=======================

Manages domain-based partitioning of the Forge knowledge graph.
Ensures optimal query performance through intelligent capsule placement.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)


class PartitionStrategy(Enum):
    """Strategies for partitioning capsules."""

    DOMAIN = "domain"           # Partition by domain/topic
    USER = "user"               # Partition by owner
    TIME = "time"               # Partition by creation time
    HASH = "hash"               # Consistent hash partitioning
    HYBRID = "hybrid"           # Combination of strategies


class PartitionState(Enum):
    """State of a partition."""

    ACTIVE = "active"
    REBALANCING = "rebalancing"
    READONLY = "readonly"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass
class PartitionStats:
    """Statistics for a partition."""

    capsule_count: int = 0
    edge_count: int = 0
    total_size_bytes: int = 0
    avg_query_latency_ms: float = 0.0
    queries_per_second: float = 0.0
    last_write_at: datetime | None = None
    last_query_at: datetime | None = None


@dataclass
class Partition:
    """Represents a graph partition."""

    partition_id: str
    name: str
    strategy: PartitionStrategy
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: PartitionState = PartitionState.ACTIVE
    stats: PartitionStats = field(default_factory=PartitionStats)

    # Partition boundaries
    domain_tags: set[str] = field(default_factory=set)
    user_ids: set[str] = field(default_factory=set)
    hash_range: tuple[int, int] = (0, 100)

    # Configuration
    max_capsules: int = 50000
    max_edges: int = 500000

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_full(self) -> bool:
        """Check if partition has reached capacity."""
        return self.stats.capsule_count >= self.max_capsules

    @property
    def utilization(self) -> float:
        """Get partition utilization percentage."""
        return (self.stats.capsule_count / self.max_capsules) * 100 if self.max_capsules > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "partition_id": self.partition_id,
            "name": self.name,
            "strategy": self.strategy.value,
            "created_at": self.created_at.isoformat(),
            "state": self.state.value,
            "stats": {
                "capsule_count": self.stats.capsule_count,
                "edge_count": self.stats.edge_count,
                "total_size_bytes": self.stats.total_size_bytes,
                "avg_query_latency_ms": self.stats.avg_query_latency_ms,
                "utilization": self.utilization,
            },
            "domain_tags": list(self.domain_tags),
            "hash_range": self.hash_range,
        }


@dataclass
class RebalanceJob:
    """Represents a partition rebalancing job."""

    job_id: str
    source_partition: str
    target_partition: str
    capsules_to_move: list[str] = field(default_factory=list)
    moved_count: int = 0
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PartitionManager:
    """
    Manages graph partitioning for Forge.

    Features:
    - Domain-based partition assignment
    - Automatic rebalancing when partitions become uneven
    - Cross-partition query routing
    - Partition lifecycle management
    """

    def __init__(self):
        self._config = get_resilience_config().partitioning
        self._partitions: dict[str, Partition] = {}
        self._capsule_partition_map: dict[str, str] = {}
        self._rebalance_jobs: dict[str, RebalanceJob] = {}
        self._initialized = False
        self._rebalance_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize the partition manager."""
        if self._initialized:
            return

        if not self._config.enabled:
            logger.info("partitioning_disabled")
            return

        # Create default partition
        default = Partition(
            partition_id="default",
            name="Default Partition",
            strategy=PartitionStrategy.HASH,
            hash_range=(0, 100),
        )
        self._partitions["default"] = default

        # Start background rebalancing task
        if self._config.auto_rebalance:
            self._rebalance_task = asyncio.create_task(self._background_rebalance())

        self._initialized = True
        logger.info("partition_manager_initialized")

    async def close(self) -> None:
        """Clean up resources."""
        if self._rebalance_task and not self._rebalance_task.done():
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass

    def create_partition(
        self,
        name: str,
        strategy: PartitionStrategy = PartitionStrategy.DOMAIN,
        domain_tags: set[str] | None = None,
        max_capsules: int | None = None
    ) -> Partition:
        """
        Create a new partition.

        Args:
            name: Partition name
            strategy: Partitioning strategy
            domain_tags: Domain tags for domain-based partitioning
            max_capsules: Maximum capsules (uses config default if not specified)

        Returns:
            Created partition

        SECURITY FIX (Audit 4 - H16): Uses SHA-256 with longer prefix instead
        of MD5 with 8 chars to reduce collision probability.
        """
        # SECURITY FIX: Use SHA-256 with 16 chars (64 bits) instead of MD5 with 8 chars (32 bits)
        # MD5 with 8 hex chars has ~50% collision probability at ~65k partitions (birthday paradox)
        # SHA-256 with 16 hex chars has ~50% collision probability at ~4 billion partitions
        partition_id = f"p_{hashlib.sha256(name.encode()).hexdigest()[:16]}"

        partition = Partition(
            partition_id=partition_id,
            name=name,
            strategy=strategy,
            domain_tags=domain_tags or set(),
            max_capsules=max_capsules or self._config.max_capsules_per_partition,
        )

        self._partitions[partition_id] = partition

        logger.info(
            "partition_created",
            partition_id=partition_id,
            name=name,
            strategy=strategy.value
        )

        return partition

    def get_partition(self, partition_id: str) -> Partition | None:
        """Get partition by ID."""
        return self._partitions.get(partition_id)

    def list_partitions(self) -> list[Partition]:
        """List all partitions."""
        return list(self._partitions.values())

    def assign_capsule(
        self,
        capsule_id: str,
        domain_tags: set[str] | None = None,
        owner_id: str | None = None
    ) -> str:
        """
        Assign a capsule to a partition.

        Args:
            capsule_id: Capsule ID
            domain_tags: Tags associated with the capsule
            owner_id: Owner of the capsule

        Returns:
            Assigned partition ID
        """
        if not self._config.enabled:
            return "default"

        # Find best partition
        partition_id = self._find_best_partition(capsule_id, domain_tags, owner_id)

        # Record assignment
        self._capsule_partition_map[capsule_id] = partition_id

        # Update partition stats
        if partition_id in self._partitions:
            self._partitions[partition_id].stats.capsule_count += 1

        logger.debug(
            "capsule_assigned",
            capsule_id=capsule_id,
            partition_id=partition_id
        )

        return partition_id

    def get_capsule_partition(self, capsule_id: str) -> str | None:
        """Get the partition ID for a capsule."""
        return self._capsule_partition_map.get(capsule_id)

    def _find_best_partition(
        self,
        capsule_id: str,
        domain_tags: set[str] | None,
        owner_id: str | None
    ) -> str:
        """Find the best partition for a capsule."""
        candidates = []

        for partition in self._partitions.values():
            if partition.state != PartitionState.ACTIVE:
                continue
            if partition.is_full:
                continue

            score = self._calculate_partition_score(
                partition,
                capsule_id,
                domain_tags,
                owner_id
            )
            candidates.append((partition.partition_id, score))

        if not candidates:
            # All partitions full - create new one
            new_partition = self.create_partition(
                name=f"Auto-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
                strategy=PartitionStrategy.HASH
            )
            return new_partition.partition_id

        # Return partition with highest score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _calculate_partition_score(
        self,
        partition: Partition,
        capsule_id: str,
        domain_tags: set[str] | None,
        owner_id: str | None
    ) -> float:
        """Calculate affinity score for a partition."""
        score = 0.0

        # Domain tag overlap
        if domain_tags and partition.domain_tags:
            overlap = len(domain_tags & partition.domain_tags)
            score += overlap * 10

        # Owner match (for user-based partitioning)
        if owner_id and owner_id in partition.user_ids:
            score += 20

        # Hash-based score
        if partition.strategy == PartitionStrategy.HASH:
            hash_val = int(hashlib.md5(capsule_id.encode()).hexdigest(), 16) % 100
            if partition.hash_range[0] <= hash_val < partition.hash_range[1]:
                score += 15

        # Prefer less utilized partitions
        utilization_bonus = (100 - partition.utilization) / 10
        score += utilization_bonus

        return score

    async def trigger_rebalance(self) -> RebalanceJob | None:
        """
        Trigger partition rebalancing if needed.

        Returns:
            RebalanceJob if rebalancing started, None otherwise
        """
        if not self._config.enabled or not self._config.auto_rebalance:
            return None

        # Calculate imbalance
        utilizations = [p.utilization for p in self._partitions.values()]
        if not utilizations:
            return None

        max_util = max(utilizations)
        min_util = min(utilizations)
        imbalance = (max_util - min_util) / 100

        if imbalance < self._config.rebalance_threshold:
            return None

        # Find source (most utilized) and target (least utilized) partitions
        partitions = sorted(
            self._partitions.values(),
            key=lambda p: p.utilization,
            reverse=True
        )

        source = partitions[0]
        target = partitions[-1]

        # Create rebalance job
        job = RebalanceJob(
            job_id=f"rebal_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            source_partition=source.partition_id,
            target_partition=target.partition_id,
        )

        self._rebalance_jobs[job.job_id] = job

        # SECURITY FIX (Audit 3): Track background task and handle exceptions
        async def _safe_rebalance(j: RebalanceJob) -> None:
            try:
                await self._execute_rebalance(j)
            except Exception as e:
                j.status = "failed"
                logger.error(
                    "rebalance_execution_error",
                    job_id=j.job_id,
                    error=str(e)
                )

        # Start rebalancing with exception handling
        task = asyncio.create_task(_safe_rebalance(job))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        logger.info(
            "rebalance_triggered",
            job_id=job.job_id,
            source=source.partition_id,
            target=target.partition_id,
            imbalance=imbalance
        )

        return job

    async def _execute_rebalance(self, job: RebalanceJob) -> None:
        """Execute a rebalancing job."""
        job.status = "running"
        job.started_at = datetime.now(UTC)

        source = self._partitions.get(job.source_partition)
        target = self._partitions.get(job.target_partition)

        if not source or not target:
            job.status = "failed"
            return

        # Set partition states
        source.state = PartitionState.REBALANCING
        target.state = PartitionState.REBALANCING

        try:
            # Find capsules to move (move 10% of source to balance)
            capsules_to_move = int(source.stats.capsule_count * 0.1)

            # Get capsules from source (would query database in production)
            moved = 0
            for capsule_id, partition_id in list(self._capsule_partition_map.items()):
                if partition_id == source.partition_id and moved < capsules_to_move:
                    # Move capsule
                    self._capsule_partition_map[capsule_id] = target.partition_id
                    source.stats.capsule_count -= 1
                    target.stats.capsule_count += 1
                    moved += 1
                    job.moved_count += 1

            job.status = "completed"
            job.completed_at = datetime.now(UTC)

            logger.info(
                "rebalance_completed",
                job_id=job.job_id,
                moved=job.moved_count
            )

        except Exception as e:
            job.status = "failed"
            logger.error(
                "rebalance_failed",
                job_id=job.job_id,
                error=str(e)
            )

        finally:
            source.state = PartitionState.ACTIVE
            target.state = PartitionState.ACTIVE

    async def _background_rebalance(self) -> None:
        """Background task for periodic rebalancing checks."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check hourly

                if self._config.enabled and self._config.auto_rebalance:
                    await self.trigger_rebalance()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("background_rebalance_error", error=str(e))

    def get_partition_stats(self) -> dict[str, Any]:
        """Get statistics for all partitions."""
        return {
            p.partition_id: p.to_dict()
            for p in self._partitions.values()
        }

    def get_rebalance_status(self) -> list[dict[str, Any]]:
        """Get status of rebalancing jobs."""
        return [
            {
                "job_id": job.job_id,
                "source": job.source_partition,
                "target": job.target_partition,
                "moved": job.moved_count,
                "status": job.status,
            }
            for job in self._rebalance_jobs.values()
        ]


# Global instance
_partition_manager: PartitionManager | None = None


async def get_partition_manager() -> PartitionManager:
    """Get or create the global partition manager instance."""
    global _partition_manager
    if _partition_manager is None:
        _partition_manager = PartitionManager()
        await _partition_manager.initialize()
    return _partition_manager
