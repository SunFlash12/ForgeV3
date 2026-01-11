"""
Nonce Store for ACP Replay Attack Prevention

Provides persistent storage for used nonces to prevent replay attacks.
Supports Redis as primary backend with in-memory fallback.

SECURITY: Nonces must persist across restarts to prevent replay attacks
where attackers resubmit previously valid signed messages.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class NonceStore:
    """
    Redis-backed nonce storage with in-memory fallback.

    Nonces are stored with TTL to automatically expire old entries.
    The store tracks the highest nonce seen per sender to detect
    replay attempts (nonce reuse or out-of-order submission).
    """

    # Default TTL for nonces (5 minutes)
    DEFAULT_TTL_SECONDS = 300

    # Maximum tracked senders in memory (to prevent memory exhaustion)
    MAX_MEMORY_SENDERS = 100000

    def __init__(
        self,
        redis_client: Any | None = None,
        prefix: str = "forge:acp:nonce:",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        """
        Initialize the nonce store.

        Args:
            redis_client: Redis async client (optional, falls back to memory)
            prefix: Redis key prefix
            ttl_seconds: TTL for nonce entries
        """
        self._redis = redis_client
        self._prefix = prefix
        self._ttl = ttl_seconds

        # In-memory fallback storage
        # Maps sender_address -> highest_nonce_seen
        self._memory_nonces: dict[str, int] = {}
        # Track when each sender's nonce was last updated (for cleanup)
        self._memory_timestamps: dict[str, float] = {}

        self._logger = logger

    def _make_key(self, sender_address: str) -> str:
        """Create Redis key for a sender."""
        return f"{self._prefix}{sender_address.lower()}"

    async def get_highest_nonce(self, sender_address: str) -> int:
        """
        Get the highest nonce seen for a sender.

        Args:
            sender_address: The sender's wallet address

        Returns:
            Highest nonce seen, or 0 if sender is new
        """
        if self._redis:
            try:
                key = self._make_key(sender_address)
                value = await self._redis.get(key)
                if value is not None:
                    return int(value)
                return 0
            except Exception as e:
                self._logger.warning(
                    "redis_get_nonce_error",
                    extra={"sender": sender_address, "error": str(e)},
                )
                # Fall through to memory

        # Memory fallback
        return self._memory_nonces.get(sender_address.lower(), 0)

    async def update_nonce(self, sender_address: str, nonce: int) -> bool:
        """
        Update the highest nonce for a sender.

        Only updates if the new nonce is higher than the current one.

        Args:
            sender_address: The sender's wallet address
            nonce: The new nonce value

        Returns:
            True if updated, False if nonce was not higher
        """
        sender_key = sender_address.lower()
        current = await self.get_highest_nonce(sender_address)

        if nonce <= current:
            return False

        if self._redis:
            try:
                key = self._make_key(sender_address)
                await self._redis.setex(key, self._ttl, str(nonce))
                self._logger.debug(
                    "nonce_updated_redis",
                    extra={"sender": sender_address, "nonce": nonce},
                )
                return True
            except Exception as e:
                self._logger.warning(
                    "redis_set_nonce_error",
                    extra={"sender": sender_address, "error": str(e)},
                )
                # Fall through to memory

        # Memory fallback with size limit
        await self._enforce_memory_limit()
        self._memory_nonces[sender_key] = nonce
        self._memory_timestamps[sender_key] = time.time()

        self._logger.debug(
            "nonce_updated_memory",
            extra={"sender": sender_address, "nonce": nonce},
        )
        return True

    async def verify_and_consume_nonce(
        self, sender_address: str, nonce: int
    ) -> tuple[bool, str]:
        """
        Verify a nonce is valid and consume it atomically.

        This is the primary method for replay protection. A nonce is valid
        if it's greater than the highest seen nonce for this sender.

        Args:
            sender_address: The sender's wallet address
            nonce: The nonce to verify

        Returns:
            Tuple of (is_valid, error_message)
            - (True, "") if valid and consumed
            - (False, reason) if invalid
        """
        current = await self.get_highest_nonce(sender_address)

        if nonce <= current:
            return False, f"Nonce {nonce} is not greater than current {current} (replay attempt)"

        # Update the nonce
        updated = await self.update_nonce(sender_address, nonce)
        if not updated:
            # Race condition - another request beat us
            return False, f"Nonce {nonce} was consumed by concurrent request"

        return True, ""

    async def _enforce_memory_limit(self) -> None:
        """Enforce memory limit by evicting oldest entries."""
        if len(self._memory_nonces) < self.MAX_MEMORY_SENDERS:
            return

        # Evict 10% of oldest entries
        evict_count = self.MAX_MEMORY_SENDERS // 10
        if evict_count < 1:
            evict_count = 1

        # Sort by timestamp and remove oldest
        sorted_senders = sorted(
            self._memory_timestamps.items(),
            key=lambda x: x[1],
        )

        for sender, _ in sorted_senders[:evict_count]:
            self._memory_nonces.pop(sender, None)
            self._memory_timestamps.pop(sender, None)

        self._logger.warning(
            "nonce_cache_eviction",
            extra={
                "evicted_count": evict_count,
                "remaining": len(self._memory_nonces),
            },
        )

    async def cleanup_expired(self) -> dict[str, int]:
        """
        Clean up expired entries from memory cache.

        Redis handles TTL automatically; this is for in-memory cleanup.

        Returns:
            Stats about cleanup
        """
        if self._redis:
            # Redis handles TTL automatically
            return {"checked": 0, "removed": 0, "backend": "redis"}

        now = time.time()
        expired = []

        for sender, timestamp in self._memory_timestamps.items():
            if now - timestamp > self._ttl:
                expired.append(sender)

        for sender in expired:
            self._memory_nonces.pop(sender, None)
            self._memory_timestamps.pop(sender, None)

        return {
            "checked": len(self._memory_timestamps) + len(expired),
            "removed": len(expired),
            "backend": "memory",
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get nonce store statistics."""
        if self._redis:
            try:
                # Count keys with our prefix
                pattern = f"{self._prefix}*"
                cursor = 0
                total_keys = 0

                while True:
                    cursor, batch = await self._redis.scan(
                        cursor, match=pattern, count=100
                    )
                    total_keys += len(batch)
                    if cursor == 0:
                        break

                return {
                    "total_senders": total_keys,
                    "backend": "redis",
                    "memory_fallback_size": len(self._memory_nonces),
                }
            except Exception as e:
                self._logger.error("redis_stats_error", extra={"error": str(e)})

        return {
            "total_senders": len(self._memory_nonces),
            "backend": "memory",
            "max_size": self.MAX_MEMORY_SENDERS,
        }


# Global nonce store instance
_nonce_store: NonceStore | None = None


async def init_nonce_store(
    redis_url: str | None = None,
    redis_password: str | None = None,
    ttl_seconds: int = NonceStore.DEFAULT_TTL_SECONDS,
) -> NonceStore:
    """
    Initialize the global nonce store.

    Args:
        redis_url: Redis connection URL (optional)
        redis_password: Redis password (optional)
        ttl_seconds: TTL for nonce entries

    Returns:
        Initialized NonceStore instance
    """
    global _nonce_store

    if _nonce_store is not None:
        return _nonce_store

    redis_client = None

    if redis_url:
        try:
            import redis.asyncio as redis

            redis_client = redis.from_url(
                redis_url,
                password=redis_password,
                decode_responses=True,
            )
            # Test connection
            await redis_client.ping()
            logger.info("nonce_store_initialized", extra={"backend": "redis"})

        except Exception as e:
            logger.warning(
                "redis_unavailable_using_memory",
                extra={"error": str(e)},
            )
            redis_client = None

    if redis_client is None:
        logger.info("nonce_store_initialized", extra={"backend": "memory"})

    _nonce_store = NonceStore(
        redis_client=redis_client,
        ttl_seconds=ttl_seconds,
    )

    return _nonce_store


def get_nonce_store() -> NonceStore | None:
    """Get the global nonce store instance."""
    return _nonce_store


async def close_nonce_store() -> None:
    """Close the nonce store and release resources."""
    global _nonce_store

    if _nonce_store is None:
        return

    if _nonce_store._redis:
        try:
            await _nonce_store._redis.close()
        except Exception:
            pass

    _nonce_store = None
    logger.info("nonce_store_closed")
