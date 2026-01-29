"""
Tests for Query Cache Service

Tests cover:
- CachedQueryResult dataclass
- QueryCache (Redis-backed)
- InMemoryQueryCache (fallback)
- Hash-based key generation
- Cache get/set/invalidate operations
- TTL handling
- Cache statistics
- Global cache initialization
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.services.query_cache import (
    CachedQueryResult,
    InMemoryQueryCache,
    QueryCache,
    close_query_cache,
    get_query_cache,
    init_query_cache,
)


# Module-level fixture to reset global cache before any test in this module
@pytest.fixture(autouse=True, scope="function")
def reset_query_cache_singleton():
    """Reset global query cache singleton before and after each test."""
    import forge.services.query_cache as cache_module

    original = cache_module._query_cache
    cache_module._query_cache = None
    yield
    # Cleanup: close cache if open and reset
    if cache_module._query_cache is not None:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                if loop.is_running():
                    loop.create_task(close_query_cache())
                else:
                    loop.run_until_complete(close_query_cache())
        except Exception:
            pass
    cache_module._query_cache = None


class TestCachedQueryResult:
    """Tests for CachedQueryResult dataclass."""

    def test_cached_query_result_creation(self):
        """Test creating a CachedQueryResult."""
        result = CachedQueryResult(
            query_hash="abc123",
            original_question="What is AI?",
            compiled_cypher="MATCH (c:Capsule) RETURN c",
            parameters={"limit": 10},
            result_summary="Found 5 capsules",
            result_count=5,
            cached_at=datetime.now(UTC),
            ttl_seconds=3600,
            hit_count=0,
        )

        assert result.query_hash == "abc123"
        assert result.original_question == "What is AI?"
        assert result.compiled_cypher == "MATCH (c:Capsule) RETURN c"
        assert result.parameters == {"limit": 10}
        assert result.result_summary == "Found 5 capsules"
        assert result.result_count == 5
        assert result.ttl_seconds == 3600
        assert result.hit_count == 0

    def test_cached_query_result_with_hits(self):
        """Test CachedQueryResult with hit count."""
        result = CachedQueryResult(
            query_hash="def456",
            original_question="How many users?",
            compiled_cypher="MATCH (u:User) RETURN count(u)",
            parameters={},
            result_summary="100 users",
            result_count=1,
            cached_at=datetime.now(UTC),
            ttl_seconds=1800,
            hit_count=25,
        )

        assert result.hit_count == 25


class TestQueryCache:
    """Tests for Redis-backed QueryCache."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest.fixture
    def cache(self, mock_redis):
        """Create a QueryCache with mock Redis."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_ttl_seconds=3600,
            )
            return QueryCache(mock_redis)

    # =========================================================================
    # Key Generation Tests
    # =========================================================================

    def test_make_key(self, cache):
        """Test key generation."""
        key = cache._make_key("abc123")
        assert key == "forge:query_cache:abc123"

    def test_make_key_custom_prefix(self, mock_redis):
        """Test key generation with custom prefix."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(query_cache_ttl_seconds=3600)
            cache = QueryCache(mock_redis, prefix="custom:")

        key = cache._make_key("xyz789")
        assert key == "custom:xyz789"

    def test_hash_query_deterministic(self, cache):
        """Test query hashing is deterministic."""
        hash1 = cache._hash_query("What is AI?", 60)
        hash2 = cache._hash_query("What is AI?", 60)
        assert hash1 == hash2

    def test_hash_query_normalizes_case(self, cache):
        """Test query hashing normalizes case."""
        hash1 = cache._hash_query("What is AI?", 60)
        hash2 = cache._hash_query("WHAT IS AI?", 60)
        assert hash1 == hash2

    def test_hash_query_normalizes_whitespace(self, cache):
        """Test query hashing normalizes whitespace."""
        hash1 = cache._hash_query("What is AI?", 60)
        hash2 = cache._hash_query("  What is AI?  ", 60)
        assert hash1 == hash2

    def test_hash_query_different_trust_different_hash(self, cache):
        """Test different trust levels produce different hashes."""
        hash1 = cache._hash_query("What is AI?", 60)
        hash2 = cache._hash_query("What is AI?", 80)
        assert hash1 != hash2

    def test_hash_query_length(self, cache):
        """Test query hash is 32 characters."""
        hash_val = cache._hash_query("Test question", 50)
        assert len(hash_val) == 32

    def test_hash_query_manual_verification(self, cache):
        """Test query hash matches expected SHA256."""
        question = "test question"
        trust = 50
        normalized = question.lower().strip()
        content = f"{normalized}:trust:{trust}"
        expected = hashlib.sha256(content.encode()).hexdigest()[:32]

        actual = cache._hash_query(question, trust)
        assert actual == expected

    # =========================================================================
    # Cache Get Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get.return_value = None

        result = await cache.get("What is AI?", 60)

        assert result is None
        assert cache._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache, mock_redis):
        """Test cache hit returns CachedQueryResult."""
        cached_data = {
            "original_question": "What is AI?",
            "compiled_cypher": "MATCH (c:Capsule) RETURN c",
            "parameters": {},
            "result_summary": "Results",
            "result_count": 10,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": 3600,
            "hit_count": 5,
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache.get("What is AI?", 60)

        assert result is not None
        assert isinstance(result, CachedQueryResult)
        assert result.original_question == "What is AI?"
        assert result.compiled_cypher == "MATCH (c:Capsule) RETURN c"
        assert result.result_count == 10
        assert result.hit_count == 6  # Incremented
        assert cache._stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_increments_hit_count(self, cache, mock_redis):
        """Test get increments hit count in Redis."""
        cached_data = {
            "original_question": "Test",
            "compiled_cypher": "MATCH (c) RETURN c",
            "parameters": {},
            "result_summary": "",
            "result_count": 0,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": 3600,
            "hit_count": 10,
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        await cache.get("Test", 50)

        # Verify Redis set was called to update hit count
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        saved_data = json.loads(call_args[0][1])
        assert saved_data["hit_count"] == 11

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self, cache, mock_redis):
        """Test get handles connection errors gracefully."""
        mock_redis.get.side_effect = ConnectionError("Redis unavailable")

        result = await cache.get("Test", 50)

        assert result is None
        assert cache._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_handles_timeout_error(self, cache, mock_redis):
        """Test get handles timeout errors gracefully."""
        mock_redis.get.side_effect = TimeoutError("Redis timeout")

        result = await cache.get("Test", 50)

        assert result is None
        assert cache._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_handles_invalid_json(self, cache, mock_redis):
        """Test get handles invalid JSON gracefully."""
        mock_redis.get.return_value = "not valid json"

        result = await cache.get("Test", 50)

        assert result is None
        assert cache._stats["misses"] == 1

    # =========================================================================
    # Cache Set Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_set_success(self, cache, mock_redis):
        """Test successful cache set."""
        result = await cache.set(
            question="What is AI?",
            user_trust=60,
            compiled_cypher="MATCH (c:Capsule) RETURN c",
            parameters={"limit": 10},
            result_summary="Found results",
            result_count=5,
        )

        assert result is True
        assert cache._stats["sets"] == 1
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache, mock_redis):
        """Test cache set with custom TTL."""
        await cache.set(
            question="Test",
            user_trust=50,
            compiled_cypher="MATCH (c) RETURN c",
            parameters={},
            ttl_seconds=7200,
        )

        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") == 7200

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl(self, cache, mock_redis):
        """Test cache set uses default TTL from settings."""
        await cache.set(
            question="Test",
            user_trust=50,
            compiled_cypher="MATCH (c) RETURN c",
            parameters={},
        )

        call_args = mock_redis.set.call_args
        # Default TTL from mock settings is 3600
        assert call_args.kwargs.get("ex") == 3600

    @pytest.mark.asyncio
    async def test_set_stores_all_fields(self, cache, mock_redis):
        """Test set stores all required fields."""
        await cache.set(
            question="What is AI?",
            user_trust=60,
            compiled_cypher="MATCH (c:Capsule) RETURN c",
            parameters={"p0": "value"},
            result_summary="Summary here",
            result_count=42,
            ttl_seconds=1800,
        )

        call_args = mock_redis.set.call_args
        stored_data = json.loads(call_args[0][1])

        assert stored_data["original_question"] == "What is AI?"
        assert stored_data["compiled_cypher"] == "MATCH (c:Capsule) RETURN c"
        assert stored_data["parameters"] == {"p0": "value"}
        assert stored_data["result_summary"] == "Summary here"
        assert stored_data["result_count"] == 42
        assert stored_data["ttl_seconds"] == 1800
        assert stored_data["hit_count"] == 0
        assert "cached_at" in stored_data

    @pytest.mark.asyncio
    async def test_set_handles_connection_error(self, cache, mock_redis):
        """Test set handles connection errors gracefully."""
        mock_redis.set.side_effect = ConnectionError("Redis unavailable")

        result = await cache.set(
            question="Test",
            user_trust=50,
            compiled_cypher="MATCH (c) RETURN c",
            parameters={},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_set_handles_timeout_error(self, cache, mock_redis):
        """Test set handles timeout errors gracefully."""
        mock_redis.set.side_effect = TimeoutError("Redis timeout")

        result = await cache.set(
            question="Test",
            user_trust=50,
            compiled_cypher="MATCH (c) RETURN c",
            parameters={},
        )

        assert result is False

    # =========================================================================
    # Cache Invalidate Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalidate_success(self, cache, mock_redis):
        """Test successful cache invalidation."""
        result = await cache.invalidate("What is AI?", 60)

        assert result is True
        assert cache._stats["deletes"] == 1
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_correct_key(self, cache, mock_redis):
        """Test invalidate uses correct key."""
        await cache.invalidate("What is AI?", 60)

        expected_hash = cache._hash_query("What is AI?", 60)
        expected_key = f"forge:query_cache:{expected_hash}"
        mock_redis.delete.assert_called_with(expected_key)

    @pytest.mark.asyncio
    async def test_invalidate_handles_error(self, cache, mock_redis):
        """Test invalidate handles errors gracefully."""
        mock_redis.delete.side_effect = ConnectionError("Redis unavailable")

        result = await cache.invalidate("Test", 50)

        assert result is False

    # =========================================================================
    # Cache Invalidate All Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalidate_all_empty(self, cache, mock_redis):
        """Test invalidate_all with no keys."""
        mock_redis.scan.return_value = (0, [])

        count = await cache.invalidate_all()

        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_all_with_keys(self, cache, mock_redis):
        """Test invalidate_all with multiple keys."""
        mock_redis.scan.return_value = (
            0,
            [
                "forge:query_cache:key1",
                "forge:query_cache:key2",
                "forge:query_cache:key3",
            ],
        )

        count = await cache.invalidate_all()

        assert count == 3
        assert cache._stats["deletes"] == 3
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_all_uses_scan(self, cache, mock_redis):
        """Test invalidate_all uses SCAN for safety."""
        mock_redis.scan.return_value = (0, [])

        await cache.invalidate_all()

        mock_redis.scan.assert_called()
        call_args = mock_redis.scan.call_args
        assert call_args.kwargs.get("match") == "forge:query_cache:*"

    @pytest.mark.asyncio
    async def test_invalidate_all_handles_error(self, cache, mock_redis):
        """Test invalidate_all handles errors gracefully."""
        mock_redis.scan.side_effect = ConnectionError("Redis unavailable")

        count = await cache.invalidate_all()

        assert count == 0

    # =========================================================================
    # Cache Cleanup Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache, mock_redis):
        """Test cleanup_expired returns stats."""
        mock_redis.scan.return_value = (0, ["key1", "key2"])

        result = await cache.cleanup_expired()

        # Redis handles TTL automatically, so removed is 0
        assert result["checked"] == 2
        assert result["removed"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_handles_error(self, cache, mock_redis):
        """Test cleanup_expired handles errors gracefully."""
        mock_redis.scan.side_effect = ConnectionError("Redis unavailable")

        result = await cache.cleanup_expired()

        assert result["checked"] == 0
        assert result["removed"] == 0
        assert "error" in result

    # =========================================================================
    # Cache Stats Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_stats_initial(self, cache, mock_redis):
        """Test get_stats with initial values."""
        mock_redis.scan.return_value = (0, [])

        stats = await cache.get_stats()

        assert stats["total_cached"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["sets"] == 0
        assert stats["deletes"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_after_operations(self, cache, mock_redis):
        """Test get_stats after operations."""
        # Simulate some operations
        mock_redis.get.return_value = None
        await cache.get("q1", 50)  # Miss
        await cache.get("q2", 50)  # Miss

        cached_data = {
            "original_question": "q3",
            "compiled_cypher": "MATCH (c) RETURN c",
            "parameters": {},
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": 3600,
            "hit_count": 0,
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        await cache.get("q3", 50)  # Hit

        await cache.set("q4", 50, "MATCH (c) RETURN c", {})  # Set

        mock_redis.scan.return_value = (0, ["key1", "key2", "key3"])
        stats = await cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["sets"] == 1
        # Hit rate: 1 / (1 + 2) = 0.3333
        assert abs(stats["hit_rate"] - 0.3333) < 0.01

    @pytest.mark.asyncio
    async def test_get_stats_handles_error(self, cache, mock_redis):
        """Test get_stats handles errors gracefully."""
        mock_redis.scan.side_effect = ConnectionError("Redis unavailable")

        stats = await cache.get_stats()

        assert "error" in stats


class TestInMemoryQueryCache:
    """Tests for in-memory query cache fallback."""

    @pytest.fixture
    def cache(self):
        """Create an InMemoryQueryCache."""
        return InMemoryQueryCache(max_size=10)

    # =========================================================================
    # Hash Query Tests
    # =========================================================================

    def test_hash_query_deterministic(self, cache):
        """Test query hashing is deterministic."""
        hash1 = cache._hash_query("What is AI?", 60)
        hash2 = cache._hash_query("What is AI?", 60)
        assert hash1 == hash2

    def test_hash_query_normalizes(self, cache):
        """Test query hashing normalizes input."""
        hash1 = cache._hash_query("what is ai?", 60)
        hash2 = cache._hash_query("  WHAT IS AI?  ", 60)
        assert hash1 == hash2

    # =========================================================================
    # Cache Get Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = await cache.get("Unknown question", 50)

        assert result is None
        assert cache._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache):
        """Test cache hit returns result."""
        await cache.set(
            question="What is AI?",
            user_trust=60,
            compiled_cypher="MATCH (c:Capsule) RETURN c",
            parameters={"limit": 10},
            result_summary="Found results",
            result_count=5,
        )

        result = await cache.get("What is AI?", 60)

        assert result is not None
        assert result.original_question == "What is AI?"
        assert result.compiled_cypher == "MATCH (c:Capsule) RETURN c"
        assert result.hit_count == 1
        assert cache._stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_increments_hit_count(self, cache):
        """Test get increments hit count."""
        await cache.set("Test", 50, "MATCH (c) RETURN c", {})

        await cache.get("Test", 50)
        await cache.get("Test", 50)
        await cache.get("Test", 50)

        result = await cache.get("Test", 50)
        assert result.hit_count == 4

    @pytest.mark.asyncio
    async def test_get_expired_entry(self, cache):
        """Test expired entries are removed."""
        await cache.set("Test", 50, "MATCH (c) RETURN c", {}, ttl_seconds=1)

        # Manually expire the entry
        query_hash = cache._hash_query("Test", 50)
        cache._cache[query_hash]["cached_at"] = (
            datetime.now(UTC) - timedelta(seconds=10)
        ).isoformat()

        result = await cache.get("Test", 50)

        assert result is None
        assert query_hash not in cache._cache
        assert cache._stats["misses"] == 1

    # =========================================================================
    # Cache Set Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_set_success(self, cache):
        """Test successful cache set."""
        result = await cache.set(
            question="What is AI?",
            user_trust=60,
            compiled_cypher="MATCH (c:Capsule) RETURN c",
            parameters={"limit": 10},
        )

        assert result is True
        assert cache._stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, cache):
        """Test cache set with custom TTL."""
        await cache.set("Test", 50, "MATCH (c) RETURN c", {}, ttl_seconds=7200)

        query_hash = cache._hash_query("Test", 50)
        assert cache._cache[query_hash]["ttl_seconds"] == 7200

    @pytest.mark.asyncio
    async def test_set_default_ttl(self, cache):
        """Test cache set uses default TTL."""
        await cache.set("Test", 50, "MATCH (c) RETURN c", {})

        query_hash = cache._hash_query("Test", 50)
        assert cache._cache[query_hash]["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_set_evicts_oldest_at_capacity(self, cache):
        """Test LRU eviction when at capacity."""
        # Fill cache
        for i in range(10):
            await cache.set(f"Question {i}", 50, "MATCH (c) RETURN c", {})

        assert len(cache._cache) == 10

        # Add one more
        await cache.set("Question 10", 50, "MATCH (c) RETURN c", {})

        # Should still be at max size
        assert len(cache._cache) == 10

        # First question should be evicted
        result = await cache.get("Question 0", 50)
        assert result is None

    # =========================================================================
    # Cache Invalidate Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalidate_existing(self, cache):
        """Test invalidating existing entry."""
        await cache.set("Test", 50, "MATCH (c) RETURN c", {})

        result = await cache.invalidate("Test", 50)

        assert result is True
        assert cache._stats["deletes"] == 1

        get_result = await cache.get("Test", 50)
        assert get_result is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent(self, cache):
        """Test invalidating nonexistent entry."""
        result = await cache.invalidate("Unknown", 50)

        assert result is False
        assert cache._stats["deletes"] == 0

    # =========================================================================
    # Cache Invalidate All Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache):
        """Test invalidate_all clears all entries."""
        await cache.set("Q1", 50, "MATCH (c) RETURN c", {})
        await cache.set("Q2", 50, "MATCH (c) RETURN c", {})
        await cache.set("Q3", 50, "MATCH (c) RETURN c", {})

        count = await cache.invalidate_all()

        assert count == 3
        assert len(cache._cache) == 0
        assert cache._stats["deletes"] == 3

    # =========================================================================
    # Cache Cleanup Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_entries(self, cache):
        """Test cleanup_expired removes expired entries."""
        await cache.set("Q1", 50, "MATCH (c) RETURN c", {}, ttl_seconds=1)
        await cache.set("Q2", 50, "MATCH (c) RETURN c", {}, ttl_seconds=3600)

        # Manually expire Q1
        hash1 = cache._hash_query("Q1", 50)
        cache._cache[hash1]["cached_at"] = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()

        result = await cache.cleanup_expired()

        assert result["removed"] == 1
        assert len(cache._cache) == 1

    # =========================================================================
    # Cache Stats Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        """Test get_stats returns correct values."""
        await cache.set("Q1", 50, "MATCH (c) RETURN c", {})
        await cache.get("Q1", 50)  # Hit
        await cache.get("Q2", 50)  # Miss

        stats = await cache.get_stats()

        assert stats["total_cached"] == 1
        assert stats["max_size"] == 10
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1
        assert stats["deletes"] == 0
        assert stats["hit_rate"] == 0.5
        assert stats["backend"] == "memory"


class TestGlobalCacheFunctions:
    """Tests for global cache initialization functions."""

    # Note: Module-level reset_query_cache_singleton fixture handles singleton reset

    @pytest.mark.asyncio
    async def test_init_query_cache_disabled(self):
        """Test init when cache is disabled."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=False,
            )

            cache = await init_query_cache()

            assert isinstance(cache, InMemoryQueryCache)
            assert cache._max_size == 0

    @pytest.mark.asyncio
    async def test_init_query_cache_no_redis(self):
        """Test init without Redis URL."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url=None,
                query_cache_max_size=5000,
            )

            cache = await init_query_cache()

            assert isinstance(cache, InMemoryQueryCache)
            assert cache._max_size == 5000

    @pytest.mark.asyncio
    async def test_init_query_cache_redis_success(self):
        """Test init with successful Redis connection."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)

        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url="redis://localhost:6379",
                redis_password=None,
                query_cache_max_size=5000,
                query_cache_ttl_seconds=3600,
            )

            with patch("redis.asyncio.from_url", return_value=mock_client):
                cache = await init_query_cache()

            assert isinstance(cache, QueryCache)

    @pytest.mark.asyncio
    async def test_init_query_cache_redis_failure(self):
        """Test init falls back to memory when Redis fails."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url="redis://localhost:6379",
                redis_password=None,
                query_cache_max_size=5000,
            )

            with patch("redis.asyncio.from_url", side_effect=ConnectionError("Cannot connect")):
                cache = await init_query_cache()

            assert isinstance(cache, InMemoryQueryCache)

    @pytest.mark.asyncio
    async def test_init_query_cache_returns_existing(self):
        """Test init returns existing cache if already initialized."""

        # First initialization
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url=None,
                query_cache_max_size=1000,
            )

            cache1 = await init_query_cache()

        # Second call should return same instance
        cache2 = await init_query_cache()

        assert cache1 is cache2

    def test_get_query_cache_none(self):
        """Test get_query_cache returns None before init."""
        cache = get_query_cache()
        assert cache is None

    @pytest.mark.asyncio
    async def test_get_query_cache_after_init(self):
        """Test get_query_cache returns cache after init."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url=None,
                query_cache_max_size=1000,
            )

            await init_query_cache()

        cache = get_query_cache()
        assert cache is not None
        assert isinstance(cache, InMemoryQueryCache)

    @pytest.mark.asyncio
    async def test_close_query_cache_none(self):
        """Test close_query_cache when no cache exists."""
        # Should not raise
        await close_query_cache()

    @pytest.mark.asyncio
    async def test_close_query_cache_memory(self):
        """Test close_query_cache with in-memory cache."""
        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url=None,
                query_cache_max_size=1000,
            )

            await init_query_cache()

        await close_query_cache()

        cache = get_query_cache()
        assert cache is None

    @pytest.mark.asyncio
    async def test_close_query_cache_redis(self):
        """Test close_query_cache with Redis cache."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()

        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url="redis://localhost:6379",
                redis_password=None,
                query_cache_max_size=5000,
                query_cache_ttl_seconds=3600,
            )

            with patch("redis.asyncio.from_url", return_value=mock_client):
                await init_query_cache()

        await close_query_cache()

        mock_client.close.assert_called_once()
        cache = get_query_cache()
        assert cache is None

    @pytest.mark.asyncio
    async def test_close_query_cache_handles_error(self):
        """Test close_query_cache handles errors gracefully."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.close = AsyncMock(side_effect=ConnectionError("Error closing"))

        with patch("forge.services.query_cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                query_cache_enabled=True,
                redis_url="redis://localhost:6379",
                redis_password=None,
                query_cache_max_size=5000,
                query_cache_ttl_seconds=3600,
            )

            with patch("redis.asyncio.from_url", return_value=mock_client):
                await init_query_cache()

        # Should not raise
        await close_query_cache()
        cache = get_query_cache()
        assert cache is None
