"""
Tiered Lineage Storage
======================

Three-tier storage system for lineage data:
- Tier 1 (Hot): Full detail, recent data, high trust
- Tier 2 (Warm): Compressed, older data, standard trust
- Tier 3 (Cold): Archived, historical data, compliance retention
"""

from __future__ import annotations

import json
import gzip
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import asyncio

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)


class StorageTier(Enum):
    """Storage tiers for lineage data."""

    HOT = "hot"       # Tier 1: Full detail, fast access
    WARM = "warm"     # Tier 2: Compressed, moderate access
    COLD = "cold"     # Tier 3: Archived, slow access


@dataclass
class LineageEntry:
    """Represents a lineage relationship entry."""

    entry_id: str
    capsule_id: str
    parent_id: Optional[str]
    relationship_type: str  # DERIVED_FROM, REFERENCES, etc.
    created_at: datetime
    trust_level: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Storage management
    tier: StorageTier = StorageTier.HOT
    compressed: bool = False
    archived_at: Optional[datetime] = None
    last_accessed: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "capsule_id": self.capsule_id,
            "parent_id": self.parent_id,
            "relationship_type": self.relationship_type,
            "created_at": self.created_at.isoformat(),
            "trust_level": self.trust_level,
            "metadata": self.metadata,
            "tier": self.tier.value,
            "compressed": self.compressed,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "last_accessed": self.last_accessed.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LineageEntry':
        """Create from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            capsule_id=data["capsule_id"],
            parent_id=data.get("parent_id"),
            relationship_type=data["relationship_type"],
            created_at=datetime.fromisoformat(data["created_at"]),
            trust_level=data["trust_level"],
            metadata=data.get("metadata", {}),
            tier=StorageTier(data.get("tier", "hot")),
            compressed=data.get("compressed", False),
            archived_at=datetime.fromisoformat(data["archived_at"]) if data.get("archived_at") else None,
            last_accessed=datetime.fromisoformat(data.get("last_accessed", datetime.utcnow().isoformat())),
        )


@dataclass
class TierStats:
    """Statistics for a storage tier."""

    entry_count: int = 0
    total_size_bytes: int = 0
    oldest_entry: Optional[datetime] = None
    newest_entry: Optional[datetime] = None
    avg_trust_level: float = 0.0


class TieredLineageStorage:
    """
    Tiered storage manager for lineage data.

    Manages automatic tier migration based on:
    - Age of lineage data
    - Trust level of associated capsules
    - Access patterns

    Tier Migration Rules:
    - Tier 1 -> Tier 2: Age > tier1_max_age_days OR trust < tier1_min_trust
    - Tier 2 -> Tier 3: Age > tier2_max_age_days OR trust < tier2_min_trust
    """

    def __init__(self):
        self._config = get_resilience_config().lineage
        self._initialized = False

        # In-memory tier storage (production would use actual storage backends)
        self._tier1_storage: Dict[str, LineageEntry] = {}
        self._tier2_storage: Dict[str, bytes] = {}  # Compressed
        self._tier3_storage: Dict[str, str] = {}    # S3 keys

        # Statistics
        self._stats = {
            StorageTier.HOT: TierStats(),
            StorageTier.WARM: TierStats(),
            StorageTier.COLD: TierStats(),
        }

        # Background migration task
        self._migration_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the tiered storage system."""
        if self._initialized:
            return

        if not self._config.enabled:
            logger.info("tiered_lineage_disabled")
            return

        # Start background migration task
        self._migration_task = asyncio.create_task(self._background_migration())

        self._initialized = True
        logger.info(
            "tiered_lineage_initialized",
            tier1_max_age=self._config.tier1_max_age_days,
            tier2_max_age=self._config.tier2_max_age_days
        )

    async def close(self) -> None:
        """Clean up resources."""
        if self._migration_task and not self._migration_task.done():
            self._migration_task.cancel()
            try:
                await self._migration_task
            except asyncio.CancelledError:
                pass

    async def store(self, entry: LineageEntry) -> bool:
        """
        Store a lineage entry in the appropriate tier.

        Args:
            entry: Lineage entry to store

        Returns:
            True if stored successfully
        """
        if not self._config.enabled:
            return True

        # Determine initial tier based on trust level
        tier = self._determine_initial_tier(entry)
        entry.tier = tier

        try:
            if tier == StorageTier.HOT:
                self._tier1_storage[entry.entry_id] = entry
            elif tier == StorageTier.WARM:
                compressed = self._compress_entry(entry)
                self._tier2_storage[entry.entry_id] = compressed
                entry.compressed = True
            else:
                # Tier 3: Archive to cold storage
                s3_key = await self._archive_to_cold(entry)
                self._tier3_storage[entry.entry_id] = s3_key
                entry.archived_at = datetime.utcnow()

            self._update_stats(tier, entry)

            logger.debug(
                "lineage_entry_stored",
                entry_id=entry.entry_id,
                tier=tier.value
            )

            return True

        except Exception as e:
            logger.error(
                "lineage_store_error",
                entry_id=entry.entry_id,
                error=str(e)
            )
            return False

    async def get(self, entry_id: str) -> Optional[LineageEntry]:
        """
        Retrieve a lineage entry from any tier.

        Args:
            entry_id: ID of the entry to retrieve

        Returns:
            LineageEntry or None if not found
        """
        if not self._config.enabled:
            return None

        # Check Tier 1 first (fastest)
        if entry_id in self._tier1_storage:
            entry = self._tier1_storage[entry_id]
            entry.last_accessed = datetime.utcnow()
            return entry

        # Check Tier 2
        if entry_id in self._tier2_storage:
            entry = self._decompress_entry(self._tier2_storage[entry_id])
            entry.last_accessed = datetime.utcnow()
            # Promote to Tier 1 on access (optional hot caching)
            return entry

        # Check Tier 3
        if entry_id in self._tier3_storage:
            entry = await self._retrieve_from_cold(self._tier3_storage[entry_id])
            if entry:
                entry.last_accessed = datetime.utcnow()
            return entry

        return None

    async def get_lineage_chain(
        self,
        capsule_id: str,
        depth: int = 10
    ) -> List[LineageEntry]:
        """
        Get the lineage chain for a capsule.

        Args:
            capsule_id: Root capsule ID
            depth: Maximum depth to traverse

        Returns:
            List of lineage entries in order
        """
        chain = []
        visited = set()
        current_id = capsule_id

        for _ in range(depth):
            if not current_id or current_id in visited:
                break

            visited.add(current_id)

            # Find entry for this capsule
            entry = await self._find_entry_by_capsule(current_id)
            if not entry:
                break

            chain.append(entry)
            current_id = entry.parent_id

        return chain

    async def migrate_to_tier(
        self,
        entry_id: str,
        target_tier: StorageTier
    ) -> bool:
        """
        Migrate an entry to a different tier.

        Args:
            entry_id: ID of entry to migrate
            target_tier: Target storage tier

        Returns:
            True if migration successful
        """
        entry = await self.get(entry_id)
        if not entry:
            return False

        current_tier = entry.tier
        if current_tier == target_tier:
            return True

        try:
            # Remove from current tier
            if current_tier == StorageTier.HOT:
                del self._tier1_storage[entry_id]
            elif current_tier == StorageTier.WARM:
                del self._tier2_storage[entry_id]
            elif current_tier == StorageTier.COLD:
                del self._tier3_storage[entry_id]

            # Store in new tier
            entry.tier = target_tier

            if target_tier == StorageTier.HOT:
                entry.compressed = False
                self._tier1_storage[entry_id] = entry
            elif target_tier == StorageTier.WARM:
                compressed = self._compress_entry(entry)
                self._tier2_storage[entry_id] = compressed
                entry.compressed = True
            else:
                s3_key = await self._archive_to_cold(entry)
                self._tier3_storage[entry_id] = s3_key
                entry.archived_at = datetime.utcnow()

            logger.info(
                "lineage_entry_migrated",
                entry_id=entry_id,
                from_tier=current_tier.value,
                to_tier=target_tier.value
            )

            return True

        except Exception as e:
            logger.error(
                "lineage_migration_error",
                entry_id=entry_id,
                error=str(e)
            )
            return False

    def _determine_initial_tier(self, entry: LineageEntry) -> StorageTier:
        """Determine the initial storage tier for an entry."""
        # High trust -> Hot tier
        if entry.trust_level >= self._config.tier1_min_trust:
            return StorageTier.HOT

        # Standard trust -> Warm tier
        if entry.trust_level >= self._config.tier2_min_trust:
            return StorageTier.WARM

        # Low trust -> Cold tier
        return StorageTier.COLD

    def _compress_entry(self, entry: LineageEntry) -> bytes:
        """Compress an entry for Tier 2 storage."""
        data = json.dumps(entry.to_dict()).encode('utf-8')
        return gzip.compress(data)

    def _decompress_entry(self, data: bytes) -> LineageEntry:
        """Decompress an entry from Tier 2 storage."""
        decompressed = gzip.decompress(data)
        return LineageEntry.from_dict(json.loads(decompressed))

    async def _archive_to_cold(self, entry: LineageEntry) -> str:
        """
        Archive entry to cold storage (S3).

        In production, this would upload to actual S3.
        """
        # Generate S3 key
        s3_key = f"lineage/{entry.created_at.year}/{entry.created_at.month}/{entry.entry_id}.json.gz"

        # Compress data
        compressed = self._compress_entry(entry)

        # In production: upload to S3
        # await s3_client.put_object(
        #     Bucket=self._config.cold_storage_bucket,
        #     Key=s3_key,
        #     Body=compressed
        # )

        logger.debug(
            "lineage_archived",
            entry_id=entry.entry_id,
            s3_key=s3_key
        )

        return s3_key

    async def _retrieve_from_cold(self, s3_key: str) -> Optional[LineageEntry]:
        """
        Retrieve entry from cold storage.

        In production, this would download from S3.
        """
        # In production: download from S3
        # response = await s3_client.get_object(
        #     Bucket=self._config.cold_storage_bucket,
        #     Key=s3_key
        # )
        # data = await response['Body'].read()
        # return self._decompress_entry(data)

        logger.debug(
            "lineage_cold_retrieval",
            s3_key=s3_key
        )

        return None

    async def _find_entry_by_capsule(self, capsule_id: str) -> Optional[LineageEntry]:
        """Find lineage entry by capsule ID."""
        # Check all tiers
        for entry in self._tier1_storage.values():
            if entry.capsule_id == capsule_id:
                return entry

        for data in self._tier2_storage.values():
            entry = self._decompress_entry(data)
            if entry.capsule_id == capsule_id:
                return entry

        return None

    async def _background_migration(self) -> None:
        """Background task to migrate entries between tiers."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run hourly

                if not self._config.enabled:
                    continue

                await self._perform_tier_migration()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("background_migration_error", error=str(e))

    async def _perform_tier_migration(self) -> None:
        """Perform tier migration based on age and trust rules."""
        now = datetime.utcnow()
        tier1_cutoff = now - timedelta(days=self._config.tier1_max_age_days)
        tier2_cutoff = now - timedelta(days=self._config.tier2_max_age_days)

        # Migrate Tier 1 -> Tier 2
        tier1_candidates = [
            entry_id for entry_id, entry in self._tier1_storage.items()
            if entry.created_at < tier1_cutoff or entry.trust_level < self._config.tier1_min_trust
        ]

        for entry_id in tier1_candidates:
            await self.migrate_to_tier(entry_id, StorageTier.WARM)

        # Migrate Tier 2 -> Tier 3
        tier2_candidates = []
        for entry_id, data in self._tier2_storage.items():
            entry = self._decompress_entry(data)
            if entry.created_at < tier2_cutoff or entry.trust_level < self._config.tier2_min_trust:
                tier2_candidates.append(entry_id)

        for entry_id in tier2_candidates:
            await self.migrate_to_tier(entry_id, StorageTier.COLD)

        if tier1_candidates or tier2_candidates:
            logger.info(
                "tier_migration_completed",
                tier1_to_tier2=len(tier1_candidates),
                tier2_to_tier3=len(tier2_candidates)
            )

    def _update_stats(self, tier: StorageTier, entry: LineageEntry) -> None:
        """Update tier statistics."""
        stats = self._stats[tier]
        stats.entry_count += 1

        if stats.oldest_entry is None or entry.created_at < stats.oldest_entry:
            stats.oldest_entry = entry.created_at
        if stats.newest_entry is None or entry.created_at > stats.newest_entry:
            stats.newest_entry = entry.created_at

    def get_tier_stats(self) -> Dict[str, TierStats]:
        """Get statistics for all tiers."""
        return {tier.value: stats for tier, stats in self._stats.items()}


# Global instance
_tiered_storage: Optional[TieredLineageStorage] = None


async def get_tiered_storage() -> TieredLineageStorage:
    """Get or create the global tiered storage instance."""
    global _tiered_storage
    if _tiered_storage is None:
        _tiered_storage = TieredLineageStorage()
        await _tiered_storage.initialize()
    return _tiered_storage
