"""
Cache Invalidation System
=========================

Event-driven cache invalidation for Forge.
Subscribes to capsule change events and invalidates affected cache entries.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from forge.resilience.caching.query_cache import QueryCache, get_query_cache

logger = structlog.get_logger(__name__)


class InvalidationStrategy(Enum):
    """Strategies for cache invalidation."""

    IMMEDIATE = "immediate"      # Invalidate immediately on change
    DEBOUNCED = "debounced"      # Wait for burst of changes to complete
    LAZY = "lazy"                # Mark stale, invalidate on next access


@dataclass
class InvalidationEvent:
    """Represents a cache invalidation event."""

    capsule_id: str
    event_type: str  # created, updated, deleted
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvalidationStats:
    """Statistics for cache invalidation monitoring."""

    events_received: int = 0
    events_processed: int = 0
    entries_invalidated: int = 0
    debounce_merges: int = 0
    errors: int = 0


class CacheInvalidator:
    """
    Event-driven cache invalidation manager.

    Subscribes to capsule change events and coordinates cache invalidation
    across the system. Supports multiple invalidation strategies.
    """

    def __init__(
        self,
        cache: QueryCache | None = None,
        strategy: InvalidationStrategy = InvalidationStrategy.IMMEDIATE,
        debounce_seconds: float = 0.5
    ):
        self._cache = cache
        self._strategy = strategy
        self._debounce_seconds = debounce_seconds
        self._stats = InvalidationStats()

        # Pending invalidations for debouncing
        self._pending: dict[str, InvalidationEvent] = {}
        self._debounce_task: asyncio.Task | None = None

        # Callbacks for custom invalidation logic
        self._callbacks: list[Callable[[InvalidationEvent], None]] = []

        # Track stale entries for lazy invalidation
        self._stale_entries: set[str] = set()

    async def initialize(self, cache: QueryCache | None = None) -> None:
        """Initialize the invalidator with a cache instance."""
        if cache:
            self._cache = cache
        elif self._cache is None:
            self._cache = await get_query_cache()

        logger.info(
            "cache_invalidator_initialized",
            strategy=self._strategy.value
        )

    async def close(self) -> None:
        """Clean up resources."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass

        # Process any remaining pending invalidations
        if self._pending:
            await self._flush_pending()

    def register_callback(
        self,
        callback: Callable[[InvalidationEvent], None]
    ) -> None:
        """Register a callback for invalidation events."""
        self._callbacks.append(callback)

    async def on_capsule_created(
        self,
        capsule_id: str,
        metadata: dict | None = None
    ) -> None:
        """Handle capsule creation event."""
        event = InvalidationEvent(
            capsule_id=capsule_id,
            event_type="created",
            metadata=metadata or {}
        )
        await self._handle_event(event)

    async def on_capsule_updated(
        self,
        capsule_id: str,
        metadata: dict | None = None
    ) -> None:
        """Handle capsule update event."""
        event = InvalidationEvent(
            capsule_id=capsule_id,
            event_type="updated",
            metadata=metadata or {}
        )
        await self._handle_event(event)

    async def on_capsule_deleted(
        self,
        capsule_id: str,
        metadata: dict | None = None
    ) -> None:
        """Handle capsule deletion event."""
        event = InvalidationEvent(
            capsule_id=capsule_id,
            event_type="deleted",
            metadata=metadata or {}
        )
        await self._handle_event(event)

    async def on_lineage_changed(
        self,
        capsule_id: str,
        parent_ids: list[str],
        metadata: dict | None = None
    ) -> None:
        """Handle lineage relationship change."""
        # Invalidate cache for all affected capsules
        all_ids = [capsule_id] + parent_ids

        for cid in all_ids:
            event = InvalidationEvent(
                capsule_id=cid,
                event_type="lineage_changed",
                metadata={**(metadata or {}), "related_ids": all_ids}
            )
            await self._handle_event(event)

    async def check_stale(self, cache_key: str) -> bool:
        """Check if a cache entry is marked as stale (for lazy invalidation)."""
        return cache_key in self._stale_entries

    async def clear_stale(self, cache_key: str) -> None:
        """Clear stale marker after re-fetching."""
        self._stale_entries.discard(cache_key)

    def get_stats(self) -> InvalidationStats:
        """Get invalidation statistics."""
        return self._stats

    async def _handle_event(self, event: InvalidationEvent) -> None:
        """Handle an invalidation event based on strategy."""
        self._stats.events_received += 1

        try:
            if self._strategy == InvalidationStrategy.IMMEDIATE:
                await self._invalidate_immediate(event)

            elif self._strategy == InvalidationStrategy.DEBOUNCED:
                await self._invalidate_debounced(event)

            elif self._strategy == InvalidationStrategy.LAZY:
                await self._invalidate_lazy(event)

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.warning(
                        "invalidation_callback_error",
                        error=str(e)
                    )

            self._stats.events_processed += 1

        except Exception as e:
            logger.error(
                "invalidation_error",
                capsule_id=event.capsule_id,
                error=str(e)
            )
            self._stats.errors += 1

    async def _invalidate_immediate(self, event: InvalidationEvent) -> None:
        """Immediately invalidate cache entries."""
        if self._cache:
            count = await self._cache.invalidate_for_capsule(event.capsule_id)
            self._stats.entries_invalidated += count

            logger.debug(
                "cache_invalidated_immediate",
                capsule_id=event.capsule_id,
                entries=count
            )

    async def _invalidate_debounced(self, event: InvalidationEvent) -> None:
        """Debounce invalidations to handle burst updates."""
        existing = self._pending.get(event.capsule_id)

        if existing:
            # Merge events - keep most recent
            self._stats.debounce_merges += 1
            logger.debug(
                "invalidation_debounce_merge",
                capsule_id=event.capsule_id
            )

        self._pending[event.capsule_id] = event

        # Start or restart debounce timer
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            try:
                await self._debounce_task
            except asyncio.CancelledError:
                pass

        self._debounce_task = asyncio.create_task(
            self._debounce_timer()
        )

    async def _debounce_timer(self) -> None:
        """Wait for debounce period then flush pending invalidations."""
        await asyncio.sleep(self._debounce_seconds)
        await self._flush_pending()

    async def _flush_pending(self) -> None:
        """Flush all pending invalidations."""
        if not self._pending:
            return

        pending = self._pending.copy()
        self._pending.clear()

        if self._cache:
            for capsule_id, _event in pending.items():
                count = await self._cache.invalidate_for_capsule(capsule_id)
                self._stats.entries_invalidated += count

            logger.debug(
                "cache_invalidated_debounced",
                count=len(pending),
                entries=self._stats.entries_invalidated
            )

    async def _invalidate_lazy(self, event: InvalidationEvent) -> None:
        """Mark cache entries as stale for lazy invalidation."""
        # For lazy invalidation, we mark entries stale
        # They'll be re-fetched on next access

        # Build cache keys that would be affected
        from forge.resilience.config import get_resilience_config
        config = get_resilience_config().cache

        # Mark potential cache keys as stale
        stale_patterns = [
            config.capsule_key_pattern.format(capsule_id=event.capsule_id),
            config.lineage_key_pattern.format(
                capsule_id=event.capsule_id,
                depth="*"
            ),
        ]

        for pattern in stale_patterns:
            self._stale_entries.add(pattern)

        logger.debug(
            "cache_marked_stale",
            capsule_id=event.capsule_id,
            patterns=len(stale_patterns)
        )


# Global invalidator instance
_cache_invalidator: CacheInvalidator | None = None


async def get_cache_invalidator() -> CacheInvalidator:
    """Get or create the global cache invalidator instance."""
    global _cache_invalidator
    if _cache_invalidator is None:
        _cache_invalidator = CacheInvalidator()
        await _cache_invalidator.initialize()
    return _cache_invalidator


async def invalidate_on_capsule_change(
    capsule_id: str,
    event_type: str = "updated"
) -> None:
    """Convenience function to trigger cache invalidation."""
    invalidator = await get_cache_invalidator()

    if event_type == "created":
        await invalidator.on_capsule_created(capsule_id)
    elif event_type == "updated":
        await invalidator.on_capsule_updated(capsule_id)
    elif event_type == "deleted":
        await invalidator.on_capsule_deleted(capsule_id)
