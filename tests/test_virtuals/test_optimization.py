"""
Tests for Multi-Chain Query Performance Optimization.

This module tests caching, rate limiting, batching, and parallel execution
for cross-chain queries.
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.virtuals.chains.optimization import (
    CacheEntry,
    ChainQueryOptimizer,
    ParallelExecutor,
    QueryCache,
    RateLimiter,
    RequestBatcher,
    cached,
    get_query_optimizer,
)
from forge.virtuals.config import ChainNetwork


# ==================== CacheEntry Tests ====================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test creating a CacheEntry."""
        entry = CacheEntry(
            value="test_value",
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )

        assert entry.value == "test_value"
        assert entry.hit_count == 0

    def test_cache_entry_hit_count_default(self):
        """Test default hit count is 0."""
        entry = CacheEntry(
            value="data",
            expires_at=datetime.now(UTC),
        )

        assert entry.hit_count == 0


# ==================== QueryCache Tests ====================


class TestQueryCache:
    """Tests for QueryCache."""

    def test_cache_init_defaults(self):
        """Test cache initialization with defaults."""
        cache = QueryCache()

        assert cache._max_size == 1000
        assert cache._default_ttl == 30

    def test_cache_init_custom(self):
        """Test cache initialization with custom values."""
        cache = QueryCache(max_size=500, default_ttl_seconds=60)

        assert cache._max_size == 500
        assert cache._default_ttl == 60

    def test_cache_get_miss(self):
        """Test cache miss."""
        cache = QueryCache()

        result = cache.get("nonexistent_key")

        assert result is None
        assert cache._misses == 1

    def test_cache_set_and_get(self):
        """Test setting and getting a value."""
        cache = QueryCache()

        cache.set("test_key", "test_value")
        result = cache.get("test_key")

        assert result == "test_value"
        assert cache._hits == 1

    def test_cache_expiration(self):
        """Test that expired entries are not returned."""
        cache = QueryCache(default_ttl_seconds=1)

        cache.set("key", "value", ttl_seconds=0)  # Immediately expired

        # Force expiration by modifying expires_at
        cache._cache["key"].expires_at = datetime.now(UTC) - timedelta(seconds=1)

        result = cache.get("key")

        assert result is None
        assert "key" not in cache._cache

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = QueryCache(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key2 and key3 to increase hit count
        cache.get("key2")
        cache.get("key3")

        # Add new entry, should evict key1 (lowest hit count)
        cache.set("key4", "value4")

        assert "key1" not in cache._cache
        assert "key4" in cache._cache

    def test_cache_invalidate(self):
        """Test invalidating a specific key."""
        cache = QueryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_cache_invalidate_prefix(self):
        """Test invalidating by prefix."""
        cache = QueryCache()
        cache.set("user:1", "data1")
        cache.set("user:2", "data2")
        cache.set("other:1", "data3")

        count = cache.invalidate_prefix("user:")

        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("other:1") == "data3"

    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = QueryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.get("key1")  # Increment stats

        cache.clear()

        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = QueryCache(max_size=100)

        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.stats

        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


# ==================== Cached Decorator Tests ====================


class TestCachedDecorator:
    """Tests for the cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_returns_cached_value(self):
        """Test that cached decorator returns cached value."""
        cache = QueryCache()
        call_count = 0

        @cached(cache, key_func=lambda x: f"key:{x}")
        async def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return f"result:{x}"

        # First call - function executes
        result1 = await expensive_function("test")
        assert result1 == "result:test"
        assert call_count == 1

        # Second call - returns cached value
        result2 = await expensive_function("test")
        assert result2 == "result:test"
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_cached_different_keys(self):
        """Test that different keys get different cached values."""
        cache = QueryCache()

        @cached(cache, key_func=lambda x: f"key:{x}")
        async def func(x):
            return f"result:{x}"

        result1 = await func("a")
        result2 = await func("b")

        assert result1 == "result:a"
        assert result2 == "result:b"


# ==================== RateLimiter Tests ====================


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_rate_limiter_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(requests_per_second=5.0, burst_size=10)

        assert limiter._rate == 5.0
        assert limiter._burst == 10

    @pytest.mark.asyncio
    async def test_acquire_allows_burst(self):
        """Test that initial burst is allowed."""
        limiter = RateLimiter(requests_per_second=1.0, burst_size=5)

        # Should allow burst requests without waiting
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_acquire_rate_limits(self):
        """Test that rate limiting kicks in after burst."""
        limiter = RateLimiter(requests_per_second=100.0, burst_size=2)

        start = time.monotonic()

        # Exhaust burst
        await limiter.acquire()
        await limiter.acquire()

        # This should wait
        await limiter.acquire()

        elapsed = time.monotonic() - start

        # Should have waited at least a small amount
        assert elapsed > 0.001

    def test_trigger_backoff(self):
        """Test triggering backoff."""
        limiter = RateLimiter()

        limiter.trigger_backoff(1.0)

        assert limiter._backoff_until > time.monotonic()

    def test_trigger_backoff_doubles(self):
        """Test that backoff doubles on repeated triggers."""
        limiter = RateLimiter()

        limiter.trigger_backoff(1.0)
        first_backoff = limiter._backoff_until

        # Trigger again while still in backoff
        limiter.trigger_backoff(1.0)
        second_backoff = limiter._backoff_until

        # Second backoff should be longer
        assert second_backoff > first_backoff


# ==================== RequestBatcher Tests ====================


class TestRequestBatcher:
    """Tests for RequestBatcher."""

    def test_batcher_init(self):
        """Test batcher initialization."""
        batcher = RequestBatcher(batch_size=50, batch_timeout_ms=100)

        assert batcher._batch_size == 50
        assert batcher._timeout == 0.1

    @pytest.mark.asyncio
    async def test_add_request(self):
        """Test adding a request."""
        batcher = RequestBatcher(batch_size=100)

        # This will add a request and wait for timeout
        async def add_and_flush():
            task = asyncio.create_task(batcher.add_request("eth_call", ["0x123"]))
            await asyncio.sleep(0.01)
            await batcher._flush()
            return await asyncio.wait_for(task, timeout=1.0)

        result = await add_and_flush()
        # Result is None in mock implementation
        assert result is None


# ==================== ParallelExecutor Tests ====================


class TestParallelExecutor:
    """Tests for ParallelExecutor."""

    def test_executor_init(self):
        """Test executor initialization."""
        executor = ParallelExecutor(max_concurrency=5)

        # Semaphores are created lazily
        assert len(executor._semaphores) == 0

    @pytest.mark.asyncio
    async def test_execute_single(self):
        """Test executing a single function."""
        executor = ParallelExecutor()

        async def my_func(x):
            return x * 2

        result = await executor.execute(ChainNetwork.BASE, my_func, 5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_multi(self):
        """Test executing multiple functions in parallel."""
        executor = ParallelExecutor()

        async def my_func(x):
            await asyncio.sleep(0.01)
            return x * 2

        tasks = [
            (ChainNetwork.BASE, my_func, (1,), {}),
            (ChainNetwork.ETHEREUM, my_func, (2,), {}),
            (ChainNetwork.BASE, my_func, (3,), {}),
        ]

        results = await executor.execute_multi(tasks)

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_execute_respects_concurrency(self):
        """Test that executor respects concurrency limit."""
        executor = ParallelExecutor(max_concurrency=2)
        concurrent_count = 0
        max_concurrent = 0

        async def track_concurrency():
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.01)
            concurrent_count -= 1
            return True

        tasks = [
            (ChainNetwork.BASE, track_concurrency, (), {}),
            (ChainNetwork.BASE, track_concurrency, (), {}),
            (ChainNetwork.BASE, track_concurrency, (), {}),
            (ChainNetwork.BASE, track_concurrency, (), {}),
        ]

        await executor.execute_multi(tasks)

        # Max concurrent should be limited to 2
        assert max_concurrent <= 2


# ==================== ChainQueryOptimizer Tests ====================


class TestChainQueryOptimizer:
    """Tests for ChainQueryOptimizer."""

    def test_optimizer_init(self):
        """Test optimizer initialization."""
        optimizer = ChainQueryOptimizer(
            cache_size=500,
            cache_ttl=60,
            requests_per_second=5.0,
            max_concurrency=5,
        )

        assert optimizer.cache._max_size == 500
        assert optimizer._requests_per_second == 5.0

    def test_get_rate_limiter(self):
        """Test getting rate limiter for a chain."""
        optimizer = ChainQueryOptimizer()

        limiter = optimizer.get_rate_limiter(ChainNetwork.BASE)

        assert isinstance(limiter, RateLimiter)

        # Same limiter for same chain
        limiter2 = optimizer.get_rate_limiter(ChainNetwork.BASE)
        assert limiter is limiter2

        # Different limiter for different chain
        limiter3 = optimizer.get_rate_limiter(ChainNetwork.ETHEREUM)
        assert limiter is not limiter3

    @pytest.mark.asyncio
    async def test_query_with_cache(self):
        """Test query with caching."""
        optimizer = ChainQueryOptimizer()
        call_count = 0

        async def my_query():
            nonlocal call_count
            call_count += 1
            return "result"

        # First query - executes function
        result1 = await optimizer.query(
            ChainNetwork.BASE,
            my_query,
            cache_key="test_key",
        )
        assert result1 == "result"
        assert call_count == 1

        # Second query - returns cached value
        result2 = await optimizer.query(
            ChainNetwork.BASE,
            my_query,
            cache_key="test_key",
        )
        assert result2 == "result"
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_query_without_cache(self):
        """Test query without caching."""
        optimizer = ChainQueryOptimizer()
        call_count = 0

        async def my_query():
            nonlocal call_count
            call_count += 1
            return "result"

        await optimizer.query(ChainNetwork.BASE, my_query)
        await optimizer.query(ChainNetwork.BASE, my_query)

        assert call_count == 2  # Called each time

    @pytest.mark.asyncio
    async def test_query_multi(self):
        """Test executing multiple queries."""
        optimizer = ChainQueryOptimizer()

        async def query_a():
            return "a"

        async def query_b():
            return "b"

        queries = [
            {"chain": ChainNetwork.BASE, "func": query_a},
            {"chain": ChainNetwork.ETHEREUM, "func": query_b},
        ]

        results = await optimizer.query_multi(queries)

        assert results == ["a", "b"]

    @pytest.mark.asyncio
    async def test_query_triggers_backoff_on_rate_limit(self):
        """Test that rate limit errors trigger backoff."""
        optimizer = ChainQueryOptimizer()

        async def rate_limited_query():
            raise Exception("Rate limit exceeded")

        with pytest.raises(Exception, match="Rate limit"):
            await optimizer.query(ChainNetwork.BASE, rate_limited_query)

        # Backoff should be triggered
        limiter = optimizer.get_rate_limiter(ChainNetwork.BASE)
        assert limiter._backoff_until > time.monotonic()

    def test_stats(self):
        """Test optimizer statistics."""
        optimizer = ChainQueryOptimizer()

        stats = optimizer.stats

        assert "total_requests" in stats
        assert "cached_requests" in stats
        assert "cache_hit_rate" in stats
        assert "cache_stats" in stats


# ==================== Global Optimizer Tests ====================


class TestGlobalOptimizer:
    """Tests for the global optimizer instance."""

    def test_get_query_optimizer_singleton(self):
        """Test that get_query_optimizer returns a singleton."""
        # Reset global
        import forge.virtuals.chains.optimization as opt_module
        opt_module._optimizer = None

        opt1 = get_query_optimizer()
        opt2 = get_query_optimizer()

        assert opt1 is opt2

        # Cleanup
        opt_module._optimizer = None

    def test_get_query_optimizer_creates_instance(self):
        """Test that get_query_optimizer creates an instance."""
        import forge.virtuals.chains.optimization as opt_module
        opt_module._optimizer = None

        optimizer = get_query_optimizer()

        assert isinstance(optimizer, ChainQueryOptimizer)

        # Cleanup
        opt_module._optimizer = None
