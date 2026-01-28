"""
Tests for the Nonce Store for ACP Replay Attack Prevention.

This module tests the NonceStore class which provides persistent storage
for used nonces to prevent replay attacks.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.acp.nonce_store import (
    NonceStore,
    close_nonce_store,
    get_nonce_store,
    init_nonce_store,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock()
    client.scan = AsyncMock(return_value=(0, []))
    client.ping = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def nonce_store_memory():
    """Create a NonceStore with in-memory backend."""
    return NonceStore(redis_client=None)


@pytest.fixture
def nonce_store_redis(mock_redis_client):
    """Create a NonceStore with mock Redis backend."""
    return NonceStore(redis_client=mock_redis_client)


@pytest.fixture(autouse=True)
async def reset_global_store():
    """Reset global nonce store before and after each test."""
    import forge.virtuals.acp.nonce_store as nonce_module
    original = nonce_module._nonce_store
    nonce_module._nonce_store = None
    yield
    nonce_module._nonce_store = original


# ==================== NonceStore Initialization Tests ====================


class TestNonceStoreInit:
    """Tests for NonceStore initialization."""

    def test_init_defaults(self, nonce_store_memory):
        """Test NonceStore initialization with defaults."""
        assert nonce_store_memory._redis is None
        assert nonce_store_memory._prefix == "forge:acp:nonce:"
        assert nonce_store_memory._ttl == NonceStore.DEFAULT_TTL_SECONDS

    def test_init_custom_params(self, mock_redis_client):
        """Test NonceStore initialization with custom parameters."""
        store = NonceStore(
            redis_client=mock_redis_client,
            prefix="custom:prefix:",
            ttl_seconds=600,
        )

        assert store._redis is mock_redis_client
        assert store._prefix == "custom:prefix:"
        assert store._ttl == 600

    def test_default_ttl_seconds(self):
        """Test default TTL value."""
        assert NonceStore.DEFAULT_TTL_SECONDS == 300  # 5 minutes

    def test_max_memory_senders(self):
        """Test max memory senders limit."""
        assert NonceStore.MAX_MEMORY_SENDERS == 100000


# ==================== Key Generation Tests ====================


class TestKeyGeneration:
    """Tests for Redis key generation."""

    def test_make_key_lowercase(self, nonce_store_memory):
        """Test that keys are lowercased."""
        key = nonce_store_memory._make_key("0xABCDEF")
        assert key == "forge:acp:nonce:0xabcdef"

    def test_make_key_with_custom_prefix(self, mock_redis_client):
        """Test key generation with custom prefix."""
        store = NonceStore(redis_client=mock_redis_client, prefix="test:")
        key = store._make_key("0x123")
        assert key == "test:0x123"


# ==================== Get Highest Nonce Tests ====================


class TestGetHighestNonce:
    """Tests for getting the highest nonce."""

    @pytest.mark.asyncio
    async def test_get_highest_nonce_new_sender_memory(self, nonce_store_memory):
        """Test getting nonce for new sender returns 0 (memory backend)."""
        result = await nonce_store_memory.get_highest_nonce("0xNewSender")
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_highest_nonce_existing_sender_memory(self, nonce_store_memory):
        """Test getting nonce for existing sender (memory backend)."""
        nonce_store_memory._memory_nonces["0xsender"] = 42
        result = await nonce_store_memory.get_highest_nonce("0xSender")
        assert result == 42

    @pytest.mark.asyncio
    async def test_get_highest_nonce_redis(self, nonce_store_redis, mock_redis_client):
        """Test getting nonce from Redis backend."""
        mock_redis_client.get = AsyncMock(return_value="100")

        result = await nonce_store_redis.get_highest_nonce("0xSender")

        assert result == 100
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_highest_nonce_redis_new_sender(self, nonce_store_redis, mock_redis_client):
        """Test getting nonce for new sender from Redis."""
        mock_redis_client.get = AsyncMock(return_value=None)

        result = await nonce_store_redis.get_highest_nonce("0xNewSender")

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_highest_nonce_redis_error_fallback(
        self, nonce_store_redis, mock_redis_client
    ):
        """Test that Redis errors fall back to memory."""
        mock_redis_client.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        nonce_store_redis._memory_nonces["0xsender"] = 50

        result = await nonce_store_redis.get_highest_nonce("0xSender")

        assert result == 50


# ==================== Update Nonce Tests ====================


class TestUpdateNonce:
    """Tests for updating nonces."""

    @pytest.mark.asyncio
    async def test_update_nonce_success_memory(self, nonce_store_memory):
        """Test successful nonce update (memory backend)."""
        result = await nonce_store_memory.update_nonce("0xSender", 10)

        assert result is True
        assert nonce_store_memory._memory_nonces["0xsender"] == 10
        assert "0xsender" in nonce_store_memory._memory_timestamps

    @pytest.mark.asyncio
    async def test_update_nonce_higher_value(self, nonce_store_memory):
        """Test updating with higher nonce succeeds."""
        await nonce_store_memory.update_nonce("0xSender", 10)
        result = await nonce_store_memory.update_nonce("0xSender", 20)

        assert result is True
        assert nonce_store_memory._memory_nonces["0xsender"] == 20

    @pytest.mark.asyncio
    async def test_update_nonce_lower_value_rejected(self, nonce_store_memory):
        """Test updating with lower nonce fails."""
        await nonce_store_memory.update_nonce("0xSender", 20)
        result = await nonce_store_memory.update_nonce("0xSender", 10)

        assert result is False
        assert nonce_store_memory._memory_nonces["0xsender"] == 20

    @pytest.mark.asyncio
    async def test_update_nonce_same_value_rejected(self, nonce_store_memory):
        """Test updating with same nonce fails (replay protection)."""
        await nonce_store_memory.update_nonce("0xSender", 10)
        result = await nonce_store_memory.update_nonce("0xSender", 10)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_nonce_redis(self, nonce_store_redis, mock_redis_client):
        """Test nonce update with Redis backend."""
        mock_redis_client.get = AsyncMock(return_value=None)

        result = await nonce_store_redis.update_nonce("0xSender", 100)

        assert result is True
        mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonce_redis_error_fallback(
        self, nonce_store_redis, mock_redis_client
    ):
        """Test Redis error falls back to memory for update."""
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await nonce_store_redis.update_nonce("0xSender", 100)

        assert result is True
        assert nonce_store_redis._memory_nonces["0xsender"] == 100


# ==================== Verify and Consume Nonce Tests ====================


class TestVerifyAndConsumeNonce:
    """Tests for verifying and consuming nonces atomically."""

    @pytest.mark.asyncio
    async def test_verify_consume_valid_nonce(self, nonce_store_memory):
        """Test verifying and consuming a valid nonce."""
        is_valid, error = await nonce_store_memory.verify_and_consume_nonce("0xSender", 1)

        assert is_valid is True
        assert error == ""
        assert nonce_store_memory._memory_nonces["0xsender"] == 1

    @pytest.mark.asyncio
    async def test_verify_consume_sequence(self, nonce_store_memory):
        """Test consuming nonces in sequence."""
        result1, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender", 1)
        result2, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender", 2)
        result3, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender", 3)

        assert all([result1, result2, result3])
        assert nonce_store_memory._memory_nonces["0xsender"] == 3

    @pytest.mark.asyncio
    async def test_verify_consume_replay_attack(self, nonce_store_memory):
        """Test detecting replay attack (same nonce reused)."""
        await nonce_store_memory.verify_and_consume_nonce("0xSender", 5)

        is_valid, error = await nonce_store_memory.verify_and_consume_nonce("0xSender", 5)

        assert is_valid is False
        assert "replay attempt" in error.lower()

    @pytest.mark.asyncio
    async def test_verify_consume_out_of_order(self, nonce_store_memory):
        """Test detecting out-of-order nonce (lower than current)."""
        await nonce_store_memory.verify_and_consume_nonce("0xSender", 10)

        is_valid, error = await nonce_store_memory.verify_and_consume_nonce("0xSender", 5)

        assert is_valid is False
        assert "not greater than current" in error.lower()

    @pytest.mark.asyncio
    async def test_verify_consume_allows_gaps(self, nonce_store_memory):
        """Test that nonce gaps are allowed (forward-only)."""
        await nonce_store_memory.verify_and_consume_nonce("0xSender", 1)

        # Skip nonces 2-99
        is_valid, error = await nonce_store_memory.verify_and_consume_nonce("0xSender", 100)

        assert is_valid is True
        assert error == ""
        assert nonce_store_memory._memory_nonces["0xsender"] == 100

    @pytest.mark.asyncio
    async def test_verify_consume_different_senders(self, nonce_store_memory):
        """Test that different senders have independent nonces."""
        await nonce_store_memory.verify_and_consume_nonce("0xSender1", 10)
        await nonce_store_memory.verify_and_consume_nonce("0xSender2", 10)

        # Both should work since they're different senders
        is_valid1, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender1", 11)
        is_valid2, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender2", 11)

        assert is_valid1 is True
        assert is_valid2 is True


# ==================== Memory Limit Tests ====================


class TestMemoryLimit:
    """Tests for memory limit enforcement."""

    @pytest.mark.asyncio
    async def test_enforce_memory_limit_under_threshold(self, nonce_store_memory):
        """Test that cleanup doesn't occur when under limit."""
        # Add some entries
        for i in range(100):
            await nonce_store_memory.update_nonce(f"0xSender{i}", i)

        initial_count = len(nonce_store_memory._memory_nonces)
        await nonce_store_memory._enforce_memory_limit()

        assert len(nonce_store_memory._memory_nonces) == initial_count

    @pytest.mark.asyncio
    async def test_enforce_memory_limit_at_max(self):
        """Test eviction when at max senders."""
        store = NonceStore()
        # Temporarily reduce limit for testing
        original_max = NonceStore.MAX_MEMORY_SENDERS
        NonceStore.MAX_MEMORY_SENDERS = 10

        try:
            # Add entries to reach limit
            for i in range(10):
                store._memory_nonces[f"sender{i}"] = i
                store._memory_timestamps[f"sender{i}"] = time.time() - (10 - i)

            await store._enforce_memory_limit()

            # Should evict 1 entry (10% of 10)
            assert len(store._memory_nonces) == 9
        finally:
            NonceStore.MAX_MEMORY_SENDERS = original_max

    @pytest.mark.asyncio
    async def test_evicts_oldest_entries(self):
        """Test that oldest entries are evicted first."""
        store = NonceStore()
        original_max = NonceStore.MAX_MEMORY_SENDERS
        NonceStore.MAX_MEMORY_SENDERS = 10

        try:
            # Add entries with timestamps
            for i in range(10):
                store._memory_nonces[f"sender{i}"] = i
                store._memory_timestamps[f"sender{i}"] = float(i)  # sender0 is oldest

            await store._enforce_memory_limit()

            # sender0 (oldest) should be evicted
            assert "sender0" not in store._memory_nonces
            assert "sender9" in store._memory_nonces
        finally:
            NonceStore.MAX_MEMORY_SENDERS = original_max


# ==================== Cleanup Expired Tests ====================


class TestCleanupExpired:
    """Tests for cleaning up expired entries."""

    @pytest.mark.asyncio
    async def test_cleanup_redis_noop(self, nonce_store_redis):
        """Test that cleanup is a no-op for Redis (TTL handled automatically)."""
        result = await nonce_store_redis.cleanup_expired()

        assert result["backend"] == "redis"
        assert result["checked"] == 0
        assert result["removed"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_memory_removes_expired(self):
        """Test cleanup removes expired entries from memory."""
        store = NonceStore(ttl_seconds=1)  # 1 second TTL

        # Add entry with old timestamp
        store._memory_nonces["old_sender"] = 100
        store._memory_timestamps["old_sender"] = time.time() - 10  # 10 seconds ago

        # Add recent entry
        store._memory_nonces["new_sender"] = 200
        store._memory_timestamps["new_sender"] = time.time()

        result = await store.cleanup_expired()

        assert result["backend"] == "memory"
        assert result["removed"] == 1
        assert "old_sender" not in store._memory_nonces
        assert "new_sender" in store._memory_nonces

    @pytest.mark.asyncio
    async def test_cleanup_memory_no_expired(self, nonce_store_memory):
        """Test cleanup when no entries are expired."""
        nonce_store_memory._memory_nonces["sender"] = 100
        nonce_store_memory._memory_timestamps["sender"] = time.time()

        result = await nonce_store_memory.cleanup_expired()

        assert result["removed"] == 0
        assert "sender" in nonce_store_memory._memory_nonces


# ==================== Get Stats Tests ====================


class TestGetStats:
    """Tests for getting nonce store statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_memory(self, nonce_store_memory):
        """Test getting stats from memory backend."""
        nonce_store_memory._memory_nonces["sender1"] = 10
        nonce_store_memory._memory_nonces["sender2"] = 20

        stats = await nonce_store_memory.get_stats()

        assert stats["total_senders"] == 2
        assert stats["backend"] == "memory"
        assert stats["max_size"] == NonceStore.MAX_MEMORY_SENDERS

    @pytest.mark.asyncio
    async def test_get_stats_redis(self, nonce_store_redis, mock_redis_client):
        """Test getting stats from Redis backend."""
        mock_redis_client.scan = AsyncMock(return_value=(0, ["key1", "key2", "key3"]))

        stats = await nonce_store_redis.get_stats()

        assert stats["total_senders"] == 3
        assert stats["backend"] == "redis"

    @pytest.mark.asyncio
    async def test_get_stats_redis_error_fallback(
        self, nonce_store_redis, mock_redis_client
    ):
        """Test stats fallback to memory on Redis error."""
        mock_redis_client.scan = AsyncMock(side_effect=ConnectionError("Redis down"))
        nonce_store_redis._memory_nonces["sender"] = 10

        stats = await nonce_store_redis.get_stats()

        assert stats["backend"] == "memory"
        assert stats["total_senders"] == 1


# ==================== Global Store Management Tests ====================


class TestGlobalStoreManagement:
    """Tests for global nonce store management functions."""

    @pytest.mark.asyncio
    async def test_init_nonce_store_memory(self):
        """Test initializing global store with memory backend."""
        store = await init_nonce_store()

        assert store is not None
        assert store._redis is None
        assert get_nonce_store() is store

    @pytest.mark.asyncio
    async def test_init_nonce_store_idempotent(self):
        """Test that init_nonce_store is idempotent."""
        store1 = await init_nonce_store()
        store2 = await init_nonce_store()

        assert store1 is store2

    @pytest.mark.asyncio
    async def test_init_nonce_store_custom_ttl(self):
        """Test initializing with custom TTL."""
        store = await init_nonce_store(ttl_seconds=600)

        assert store._ttl == 600

    @pytest.mark.asyncio
    async def test_get_nonce_store_before_init(self):
        """Test getting store before initialization returns None."""
        result = get_nonce_store()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_nonce_store(self):
        """Test closing the global nonce store."""
        await init_nonce_store()
        assert get_nonce_store() is not None

        await close_nonce_store()

        assert get_nonce_store() is None

    @pytest.mark.asyncio
    async def test_close_nonce_store_when_not_init(self):
        """Test closing store when not initialized doesn't error."""
        await close_nonce_store()  # Should not raise

    @pytest.mark.asyncio
    async def test_init_with_redis_url(self):
        """Test initializing with Redis URL."""
        with patch("forge.virtuals.acp.nonce_store.redis.asyncio") as mock_redis_module:
            mock_client = MagicMock()
            mock_client.ping = AsyncMock()
            mock_redis_module.from_url = MagicMock(return_value=mock_client)

            store = await init_nonce_store(
                redis_url="redis://localhost:6379",
                redis_password="secret",
            )

            assert store._redis is mock_client
            mock_redis_module.from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_redis_connection_failure_fallback(self):
        """Test Redis connection failure falls back to memory."""
        with patch("forge.virtuals.acp.nonce_store.redis.asyncio") as mock_redis_module:
            mock_client = MagicMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("Cannot connect"))
            mock_redis_module.from_url = MagicMock(return_value=mock_client)

            store = await init_nonce_store(redis_url="redis://localhost:6379")

            assert store._redis is None


# ==================== Concurrency Tests ====================


class TestNonceConcurrency:
    """Tests for concurrent nonce operations."""

    @pytest.mark.asyncio
    async def test_concurrent_verify_consume(self, nonce_store_memory):
        """Test concurrent verify_and_consume with same nonce."""
        results = []

        async def verify_consume():
            is_valid, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender", 1)
            results.append(is_valid)

        # Run multiple concurrent attempts
        await asyncio.gather(
            verify_consume(),
            verify_consume(),
            verify_consume(),
        )

        # Only one should succeed
        assert results.count(True) == 1
        assert results.count(False) == 2

    @pytest.mark.asyncio
    async def test_concurrent_different_senders(self, nonce_store_memory):
        """Test concurrent operations on different senders."""
        async def update_sender(sender: str, nonce: int):
            return await nonce_store_memory.verify_and_consume_nonce(sender, nonce)

        results = await asyncio.gather(
            update_sender("0xSender1", 1),
            update_sender("0xSender2", 1),
            update_sender("0xSender3", 1),
        )

        # All should succeed (different senders)
        assert all(r[0] for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_increasing_nonces(self, nonce_store_memory):
        """Test concurrent operations with increasing nonces."""
        async def update(nonce: int):
            await asyncio.sleep(nonce * 0.001)  # Small delay based on nonce
            return await nonce_store_memory.verify_and_consume_nonce("0xSender", nonce)

        results = await asyncio.gather(
            update(1),
            update(2),
            update(3),
        )

        # All should succeed since nonces are increasing
        assert all(r[0] for r in results)


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_nonce_zero(self, nonce_store_memory):
        """Test handling of nonce value 0."""
        # New sender starts at 0, so nonce 0 should fail
        is_valid, error = await nonce_store_memory.verify_and_consume_nonce("0xSender", 0)

        assert is_valid is False
        assert "not greater than current" in error.lower()

    @pytest.mark.asyncio
    async def test_nonce_one_first_valid(self, nonce_store_memory):
        """Test that nonce 1 is valid for a new sender."""
        is_valid, _ = await nonce_store_memory.verify_and_consume_nonce("0xSender", 1)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_large_nonce_value(self, nonce_store_memory):
        """Test handling of very large nonce values."""
        large_nonce = 2**64

        result = await nonce_store_memory.update_nonce("0xSender", large_nonce)

        assert result is True
        assert nonce_store_memory._memory_nonces["0xsender"] == large_nonce

    @pytest.mark.asyncio
    async def test_negative_nonce_rejected(self, nonce_store_memory):
        """Test that negative nonces are handled correctly."""
        # First set a positive nonce
        await nonce_store_memory.update_nonce("0xSender", 5)

        # Negative nonce should fail (not greater than current)
        result = await nonce_store_memory.update_nonce("0xSender", -1)

        assert result is False

    @pytest.mark.asyncio
    async def test_address_case_insensitivity(self, nonce_store_memory):
        """Test that addresses are treated case-insensitively."""
        await nonce_store_memory.update_nonce("0xABCDEF", 10)

        # Same address with different case
        nonce = await nonce_store_memory.get_highest_nonce("0xabcdef")

        assert nonce == 10

    @pytest.mark.asyncio
    async def test_empty_address(self, nonce_store_memory):
        """Test handling of empty address."""
        result = await nonce_store_memory.update_nonce("", 1)

        assert result is True
        assert nonce_store_memory._memory_nonces[""] == 1
