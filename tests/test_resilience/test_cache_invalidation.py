"""
Tests for Cache Invalidation System
===================================

Tests for forge/resilience/caching/cache_invalidation.py
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.caching.cache_invalidation import (
    CacheInvalidator,
    InvalidationEvent,
    InvalidationStats,
    InvalidationStrategy,
    get_cache_invalidator,
    invalidate_on_capsule_change,
)


class TestInvalidationEvent:
    """Tests for InvalidationEvent dataclass."""

    def test_event_creation_with_defaults(self):
        """Test creating an event with default values."""
        event = InvalidationEvent(capsule_id="cap_123", event_type="created")

        assert event.capsule_id == "cap_123"
        assert event.event_type == "created"
        assert isinstance(event.timestamp, datetime)
        assert event.metadata == {}

    def test_event_creation_with_metadata(self):
        """Test creating an event with custom metadata."""
        metadata = {"user_id": "user_123", "reason": "test"}
        event = InvalidationEvent(
            capsule_id="cap_456",
            event_type="updated",
            metadata=metadata,
        )

        assert event.metadata == metadata


class TestInvalidationStats:
    """Tests for InvalidationStats dataclass."""

    def test_stats_default_values(self):
        """Test default values for stats."""
        stats = InvalidationStats()

        assert stats.events_received == 0
        assert stats.events_processed == 0
        assert stats.entries_invalidated == 0
        assert stats.debounce_merges == 0
        assert stats.errors == 0

    def test_stats_custom_values(self):
        """Test creating stats with custom values."""
        stats = InvalidationStats(
            events_received=10,
            events_processed=9,
            entries_invalidated=5,
            errors=1,
        )

        assert stats.events_received == 10
        assert stats.events_processed == 9
        assert stats.entries_invalidated == 5
        assert stats.errors == 1


class TestCacheInvalidator:
    """Tests for CacheInvalidator class."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        cache = AsyncMock()
        cache.invalidate_for_capsule = AsyncMock(return_value=3)
        return cache

    @pytest.fixture
    def invalidator(self, mock_cache):
        """Create an invalidator with mock cache."""
        return CacheInvalidator(
            cache=mock_cache,
            strategy=InvalidationStrategy.IMMEDIATE,
        )

    def test_invalidator_creation_defaults(self):
        """Test invalidator creation with defaults."""
        invalidator = CacheInvalidator()

        assert invalidator._cache is None
        assert invalidator._strategy == InvalidationStrategy.IMMEDIATE
        assert invalidator._debounce_seconds == 0.5
        assert isinstance(invalidator._stats, InvalidationStats)

    def test_invalidator_creation_with_params(self, mock_cache):
        """Test invalidator creation with custom params."""
        invalidator = CacheInvalidator(
            cache=mock_cache,
            strategy=InvalidationStrategy.DEBOUNCED,
            debounce_seconds=1.0,
        )

        assert invalidator._cache == mock_cache
        assert invalidator._strategy == InvalidationStrategy.DEBOUNCED
        assert invalidator._debounce_seconds == 1.0

    @pytest.mark.asyncio
    async def test_initialize_with_cache(self, mock_cache):
        """Test initialization with provided cache."""
        invalidator = CacheInvalidator()
        await invalidator.initialize(cache=mock_cache)

        assert invalidator._cache == mock_cache

    @pytest.mark.asyncio
    async def test_close_cancels_debounce_task(self, invalidator):
        """Test that close cancels any pending debounce task."""
        # Create a debounce task
        invalidator._debounce_task = asyncio.create_task(asyncio.sleep(10))

        await invalidator.close()

        assert invalidator._debounce_task.done() or invalidator._debounce_task.cancelled()

    def test_register_callback(self, invalidator):
        """Test registering a callback."""
        callback = MagicMock()

        invalidator.register_callback(callback)

        assert callback in invalidator._callbacks

    @pytest.mark.asyncio
    async def test_on_capsule_created(self, invalidator, mock_cache):
        """Test handling capsule creation event."""
        await invalidator.on_capsule_created("cap_123", {"key": "value"})

        assert invalidator._stats.events_received == 1
        mock_cache.invalidate_for_capsule.assert_called_once_with("cap_123")

    @pytest.mark.asyncio
    async def test_on_capsule_updated(self, invalidator, mock_cache):
        """Test handling capsule update event."""
        await invalidator.on_capsule_updated("cap_456")

        assert invalidator._stats.events_received == 1
        mock_cache.invalidate_for_capsule.assert_called_once_with("cap_456")

    @pytest.mark.asyncio
    async def test_on_capsule_deleted(self, invalidator, mock_cache):
        """Test handling capsule deletion event."""
        await invalidator.on_capsule_deleted("cap_789")

        assert invalidator._stats.events_received == 1
        mock_cache.invalidate_for_capsule.assert_called_once_with("cap_789")

    @pytest.mark.asyncio
    async def test_on_lineage_changed(self, invalidator, mock_cache):
        """Test handling lineage change event."""
        await invalidator.on_lineage_changed(
            "cap_123",
            parent_ids=["cap_parent1", "cap_parent2"],
        )

        # Should invalidate for all related capsules
        assert invalidator._stats.events_received == 3  # capsule + 2 parents
        assert mock_cache.invalidate_for_capsule.call_count == 3

    @pytest.mark.asyncio
    async def test_check_stale(self, invalidator):
        """Test checking if entry is stale."""
        invalidator._stale_entries.add("key1")

        assert await invalidator.check_stale("key1") is True
        assert await invalidator.check_stale("key2") is False

    @pytest.mark.asyncio
    async def test_clear_stale(self, invalidator):
        """Test clearing stale marker."""
        invalidator._stale_entries.add("key1")

        await invalidator.clear_stale("key1")

        assert "key1" not in invalidator._stale_entries

    def test_get_stats(self, invalidator):
        """Test getting stats."""
        stats = invalidator.get_stats()

        assert isinstance(stats, InvalidationStats)

    @pytest.mark.asyncio
    async def test_immediate_strategy(self, invalidator, mock_cache):
        """Test immediate invalidation strategy."""
        invalidator._strategy = InvalidationStrategy.IMMEDIATE

        await invalidator.on_capsule_updated("cap_123")

        mock_cache.invalidate_for_capsule.assert_called_once()
        assert invalidator._stats.entries_invalidated == 3

    @pytest.mark.asyncio
    async def test_debounced_strategy(self, mock_cache):
        """Test debounced invalidation strategy."""
        invalidator = CacheInvalidator(
            cache=mock_cache,
            strategy=InvalidationStrategy.DEBOUNCED,
            debounce_seconds=0.1,
        )

        # Trigger multiple events quickly
        await invalidator.on_capsule_updated("cap_123")
        await invalidator.on_capsule_updated("cap_123")  # Same capsule

        assert invalidator._stats.debounce_merges == 1

        # Wait for debounce
        await asyncio.sleep(0.2)

        # Should have called once due to debouncing
        mock_cache.invalidate_for_capsule.assert_called()

    @pytest.mark.asyncio
    async def test_lazy_strategy(self, mock_cache):
        """Test lazy invalidation strategy."""
        invalidator = CacheInvalidator(
            cache=mock_cache,
            strategy=InvalidationStrategy.LAZY,
        )

        with patch("forge.resilience.caching.cache_invalidation.get_resilience_config") as mock_config:
            mock_config.return_value.cache.capsule_key_pattern = "forge:capsule:{capsule_id}"
            mock_config.return_value.cache.lineage_key_pattern = "forge:lineage:{capsule_id}:{depth}"

            await invalidator.on_capsule_updated("cap_123")

        # Should mark as stale, not invalidate immediately
        mock_cache.invalidate_for_capsule.assert_not_called()
        assert len(invalidator._stale_entries) > 0

    @pytest.mark.asyncio
    async def test_callback_invoked(self, invalidator):
        """Test that registered callbacks are invoked."""
        callback_sync = MagicMock()
        callback_async = AsyncMock()

        invalidator.register_callback(callback_sync)
        invalidator.register_callback(callback_async)

        await invalidator.on_capsule_created("cap_123")

        callback_sync.assert_called_once()
        callback_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, invalidator):
        """Test that callback errors don't stop processing."""
        failing_callback = MagicMock(side_effect=ValueError("Test error"))

        invalidator.register_callback(failing_callback)

        # Should not raise
        await invalidator.on_capsule_created("cap_123")

        # Stats should still update
        assert invalidator._stats.events_processed == 1


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_cache_invalidator(self):
        """Test getting global cache invalidator."""
        with patch("forge.resilience.caching.cache_invalidation._cache_invalidator", None):
            with patch("forge.resilience.caching.cache_invalidation.get_query_cache") as mock_get_cache:
                mock_get_cache.return_value = AsyncMock()

                invalidator = await get_cache_invalidator()

                assert isinstance(invalidator, CacheInvalidator)

    @pytest.mark.asyncio
    async def test_invalidate_on_capsule_change_created(self):
        """Test convenience function for created event."""
        with patch("forge.resilience.caching.cache_invalidation.get_cache_invalidator") as mock_get:
            mock_invalidator = AsyncMock()
            mock_get.return_value = mock_invalidator

            await invalidate_on_capsule_change("cap_123", "created")

            mock_invalidator.on_capsule_created.assert_called_once_with("cap_123")

    @pytest.mark.asyncio
    async def test_invalidate_on_capsule_change_updated(self):
        """Test convenience function for updated event."""
        with patch("forge.resilience.caching.cache_invalidation.get_cache_invalidator") as mock_get:
            mock_invalidator = AsyncMock()
            mock_get.return_value = mock_invalidator

            await invalidate_on_capsule_change("cap_123", "updated")

            mock_invalidator.on_capsule_updated.assert_called_once_with("cap_123")

    @pytest.mark.asyncio
    async def test_invalidate_on_capsule_change_deleted(self):
        """Test convenience function for deleted event."""
        with patch("forge.resilience.caching.cache_invalidation.get_cache_invalidator") as mock_get:
            mock_invalidator = AsyncMock()
            mock_get.return_value = mock_invalidator

            await invalidate_on_capsule_change("cap_123", "deleted")

            mock_invalidator.on_capsule_deleted.assert_called_once_with("cap_123")


class TestInvalidationStrategy:
    """Tests for InvalidationStrategy enum."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        assert InvalidationStrategy.IMMEDIATE.value == "immediate"
        assert InvalidationStrategy.DEBOUNCED.value == "debounced"
        assert InvalidationStrategy.LAZY.value == "lazy"
