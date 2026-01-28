"""
Tests for Query Cache Implementation
====================================

Tests for forge/resilience/caching/query_cache.py
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.caching.query_cache import (
    CacheEntry,
    CacheStats,
    QueryCache,
    get_query_cache,
    invalidate_cache_for_capsule,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a cache entry."""
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=300)

        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            created_at=now,
            expires_at=expires,
            query_type="general",
        )

        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert entry.created_at == now
        assert entry.expires_at == expires
        assert entry.query_type == "general"

    def test_is_expired_false(self):
        """Test is_expired returns false for valid entry."""
        entry = CacheEntry(
            key="test_key",
            value="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            query_type="general",
        )

        assert entry.is_expired is False

    def test_is_expired_true(self):
        """Test is_expired returns true for expired entry."""
        entry = CacheEntry(
            key="test_key",
            value="test",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            query_type="general",
        )

        assert entry.is_expired is True

    def test_ttl_remaining_positive(self):
        """Test ttl_remaining for valid entry."""
        entry = CacheEntry(
            key="test_key",
            value="test",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(seconds=100),
            query_type="general",
        )

        # Should be close to 100 seconds (allow small drift)
        assert 95 <= entry.ttl_remaining <= 100

    def test_ttl_remaining_zero_when_expired(self):
        """Test ttl_remaining is 0 for expired entry."""
        entry = CacheEntry(
            key="test_key",
            value="test",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            query_type="general",
        )

        assert entry.ttl_remaining == 0


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_stats_defaults(self):
        """Test default values."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.invalidations == 0
        assert stats.errors == 0

    def test_hit_rate_zero_total(self):
        """Test hit rate with no requests."""
        stats = CacheStats()

        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)

        assert stats.hit_rate == 0.75

    def test_hit_rate_all_hits(self):
        """Test hit rate with all hits."""
        stats = CacheStats(hits=100, misses=0)

        assert stats.hit_rate == 1.0


class TestQueryCache:
    """Tests for QueryCache class."""

    @pytest.fixture
    def cache_config(self):
        """Create a mock cache config."""
        config = MagicMock()
        config.enabled = True
        config.redis_url = None
        config.default_ttl_seconds = 300
        config.lineage_ttl_seconds = 3600
        config.search_ttl_seconds = 600
        config.max_cached_result_bytes = 1048576
        config.lineage_key_pattern = "forge:lineage:{capsule_id}:{depth}"
        config.search_key_pattern = "forge:search:{query_hash}"
        config.capsule_key_pattern = "forge:capsule:{capsule_id}"
        return config

    @pytest.fixture
    def cache(self, cache_config):
        """Create a QueryCache with mocked config."""
        with patch("forge.resilience.caching.query_cache.get_resilience_config") as mock:
            mock.return_value.cache = cache_config
            return QueryCache(config=cache_config)

    @pytest.mark.asyncio
    async def test_initialize_disabled(self, cache_config):
        """Test initialization when disabled."""
        cache_config.enabled = False

        with patch("forge.resilience.caching.query_cache.get_resilience_config") as mock:
            mock.return_value.cache = cache_config
            cache = QueryCache(config=cache_config)
            await cache.initialize()

            assert not cache._use_redis

    @pytest.mark.asyncio
    async def test_initialize_memory_fallback(self, cache):
        """Test initialization falls back to memory cache."""
        await cache.initialize()

        assert not cache._use_redis

    @pytest.mark.asyncio
    async def test_get_miss(self, cache):
        """Test cache miss."""
        await cache.initialize()

        result = await cache.get("nonexistent_key")

        assert result is None
        assert cache._stats.misses == 1

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """Test setting and getting a value."""
        await cache.initialize()

        success = await cache.set("test_key", {"data": "value"})
        assert success is True

        result = await cache.get("test_key")
        assert result == {"data": "value"}
        assert cache._stats.hits == 1

    @pytest.mark.asyncio
    async def test_set_disabled(self, cache_config):
        """Test set returns false when disabled."""
        cache_config.enabled = False

        with patch("forge.resilience.caching.query_cache.get_resilience_config") as mock:
            mock.return_value.cache = cache_config
            cache = QueryCache(config=cache_config)

            result = await cache.set("key", "value")

            assert result is False

    @pytest.mark.asyncio
    async def test_set_value_too_large(self, cache):
        """Test set rejects values that are too large."""
        await cache.initialize()

        # Create a value larger than max_cached_result_bytes
        large_value = {"data": "x" * 2000000}

        result = await cache.set("large_key", large_value)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test deleting a cache entry."""
        await cache.initialize()

        await cache.set("delete_key", "value")
        result = await cache.delete("delete_key")

        assert result is True
        assert await cache.get("delete_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """Test deleting nonexistent key."""
        await cache.initialize()

        result = await cache.delete("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_compute_cached(self, cache):
        """Test get_or_compute returns cached value."""
        await cache.initialize()

        await cache.set("compute_key", "cached_value")
        compute_func = MagicMock(return_value="computed_value")

        result = await cache.get_or_compute("compute_key", compute_func)

        assert result == "cached_value"
        compute_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_compute_miss(self, cache):
        """Test get_or_compute computes on miss."""
        await cache.initialize()

        compute_func = MagicMock(return_value="computed_value")

        result = await cache.get_or_compute("new_key", compute_func)

        assert result == "computed_value"
        compute_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_compute_async_func(self, cache):
        """Test get_or_compute with async compute function."""
        await cache.initialize()

        async def async_compute():
            return "async_value"

        result = await cache.get_or_compute("async_key", async_compute)

        assert result == "async_value"

    @pytest.mark.asyncio
    async def test_get_or_compute_lineage(self, cache):
        """Test get_or_compute_lineage method."""
        await cache.initialize()

        def compute_lineage():
            return {"capsules": [{"id": "cap_1"}]}

        result = await cache.get_or_compute_lineage("cap_123", 5, compute_lineage)

        assert result == {"capsules": [{"id": "cap_1"}]}

    @pytest.mark.asyncio
    async def test_get_or_compute_search(self, cache):
        """Test get_or_compute_search method."""
        await cache.initialize()

        def compute_search():
            return [{"id": "cap_1"}]

        result = await cache.get_or_compute_search(
            "test query",
            {"filter": "value"},
            compute_search,
        )

        assert result == [{"id": "cap_1"}]

    @pytest.mark.asyncio
    async def test_invalidate_for_capsule(self, cache):
        """Test invalidating cache for a capsule."""
        await cache.initialize()

        # Set up invalidation tracking
        await cache.set(
            "key1",
            "value1",
            related_capsule_ids=["cap_123"],
        )

        count = await cache.invalidate_for_capsule("cap_123")

        assert count == 1
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_clear_all(self, cache):
        """Test clearing all cache entries."""
        await cache.initialize()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        count = await cache.clear_all()

        assert count == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    def test_get_stats(self, cache):
        """Test getting cache stats."""
        stats = cache.get_stats()

        assert isinstance(stats, CacheStats)

    def test_sanitize_cache_key_valid(self, cache):
        """Test sanitizing valid cache key component."""
        result = cache._sanitize_cache_key_component("valid-key_123")

        assert result == "valid-key_123"

    def test_sanitize_cache_key_invalid(self, cache):
        """Test sanitizing invalid cache key component."""
        result = cache._sanitize_cache_key_component("invalid:key/with\\special<chars>")

        assert result.startswith("sanitized_")
        assert len(result) == len("sanitized_") + 32

    def test_sanitize_cache_key_too_long(self, cache):
        """Test sanitizing too-long cache key component."""
        long_key = "a" * 200

        result = cache._sanitize_cache_key_component(long_key)

        assert result.startswith("sanitized_")

    def test_hash_query(self, cache):
        """Test query hashing."""
        hash1 = cache._hash_query("query", {"filter": "value"})
        hash2 = cache._hash_query("query", {"filter": "value"})
        hash3 = cache._hash_query("query", {"filter": "different"})

        assert hash1 == hash2  # Same input = same hash
        assert hash1 != hash3  # Different input = different hash
        assert len(hash1) == 16  # 16-char hash

    @pytest.mark.asyncio
    async def test_compute_lineage_ttl_empty(self, cache):
        """Test lineage TTL calculation with empty result."""
        await cache.initialize()

        ttl = await cache._compute_lineage_ttl([])

        assert ttl == cache._config.lineage_ttl_seconds

    @pytest.mark.asyncio
    async def test_compute_lineage_ttl_recent(self, cache):
        """Test lineage TTL for recently modified capsules."""
        await cache.initialize()

        recent_capsule = MagicMock()
        recent_capsule.updated_at = datetime.now(UTC) - timedelta(minutes=30)

        result = MagicMock()
        result.all_capsules = MagicMock(return_value=[recent_capsule])

        ttl = await cache._compute_lineage_ttl(result)

        assert ttl == 60  # 1 minute for very recent changes

    @pytest.mark.asyncio
    async def test_expired_entry_removed_on_get(self, cache):
        """Test that expired entries are removed on access."""
        await cache.initialize()

        # Manually add an expired entry
        cache._memory_cache["expired_key"] = CacheEntry(
            key="expired_key",
            value="old_value",
            created_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            query_type="general",
        )

        result = await cache.get("expired_key")

        assert result is None
        assert "expired_key" not in cache._memory_cache


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_query_cache(self):
        """Test getting global query cache."""
        with patch("forge.resilience.caching.query_cache._query_cache", None):
            with patch("forge.resilience.caching.query_cache.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.cache.enabled = True
                mock_config.cache.redis_url = None
                mock.return_value = mock_config

                cache = await get_query_cache()

                assert isinstance(cache, QueryCache)

    @pytest.mark.asyncio
    async def test_invalidate_cache_for_capsule(self):
        """Test convenience function for cache invalidation."""
        with patch("forge.resilience.caching.query_cache.get_query_cache") as mock_get:
            mock_cache = AsyncMock()
            mock_cache.invalidate_for_capsule = AsyncMock(return_value=5)
            mock_get.return_value = mock_cache

            count = await invalidate_cache_for_capsule("cap_123")

            assert count == 5
            mock_cache.invalidate_for_capsule.assert_called_once_with("cap_123")
