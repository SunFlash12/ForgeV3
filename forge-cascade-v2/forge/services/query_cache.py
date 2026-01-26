"""
Query Cache Service

Redis-backed caching for NL→Cypher query results.
Reduces LLM API calls and improves response times for repeated queries.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from forge.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class CachedQueryResult:
    """A cached query result."""

    query_hash: str
    original_question: str
    compiled_cypher: str
    parameters: dict[str, Any]
    result_summary: str
    result_count: int
    cached_at: datetime
    ttl_seconds: int
    hit_count: int = 0


class QueryCache:
    """
    Redis-backed cache for NL→Cypher query results.

    Uses hash-based keys for efficient lookup of similar queries.
    """

    def __init__(self, redis_client: Any, prefix: str = "forge:query_cache:"):
        self._redis = redis_client
        self._prefix = prefix
        self._settings = get_settings()
        self._logger = logger.bind(service="query_cache")

        # Local stats (for this instance)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    def _make_key(self, query_hash: str) -> str:
        """Create a Redis key from a query hash."""
        return f"{self._prefix}{query_hash}"

    def _hash_query(self, question: str, user_trust: int) -> str:
        """
        Create a deterministic hash for a query.

        Includes trust level since results may differ by trust.
        """
        normalized = question.lower().strip()
        content = f"{normalized}:trust:{user_trust}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def get(
        self,
        question: str,
        user_trust: int,
    ) -> CachedQueryResult | None:
        """
        Get a cached query result.

        Args:
            question: The natural language question
            user_trust: User's trust level (affects result visibility)

        Returns:
            CachedQueryResult if found and not expired, None otherwise
        """
        query_hash = self._hash_query(question, user_trust)
        key = self._make_key(query_hash)

        try:
            data = await self._redis.get(key)
            if not data:
                self._stats["misses"] += 1
                return None

            result = json.loads(data)

            # Increment hit count
            result["hit_count"] = result.get("hit_count", 0) + 1
            await self._redis.set(
                key,
                json.dumps(result),
                ex=result.get("ttl_seconds", self._settings.query_cache_ttl_seconds),
            )

            self._stats["hits"] += 1
            self._logger.debug(
                "cache_hit",
                query_hash=query_hash,
                hit_count=result["hit_count"],
            )

            return CachedQueryResult(
                query_hash=query_hash,
                original_question=result["original_question"],
                compiled_cypher=result["compiled_cypher"],
                parameters=result.get("parameters", {}),
                result_summary=result.get("result_summary", ""),
                result_count=result.get("result_count", 0),
                cached_at=datetime.fromisoformat(result["cached_at"]),
                ttl_seconds=result.get("ttl_seconds", self._settings.query_cache_ttl_seconds),
                hit_count=result["hit_count"],
            )

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_get_error", error=str(e))
            self._stats["misses"] += 1
            return None

    async def set(
        self,
        question: str,
        user_trust: int,
        compiled_cypher: str,
        parameters: dict[str, Any],
        result_summary: str = "",
        result_count: int = 0,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Cache a query result.

        Args:
            question: The natural language question
            user_trust: User's trust level
            compiled_cypher: The compiled Cypher query
            parameters: Query parameters
            result_summary: Summary of the result (for preview)
            result_count: Number of results returned
            ttl_seconds: Custom TTL (defaults to config)

        Returns:
            True if cached successfully
        """
        query_hash = self._hash_query(question, user_trust)
        key = self._make_key(query_hash)
        ttl = ttl_seconds or self._settings.query_cache_ttl_seconds

        try:
            data = {
                "original_question": question,
                "compiled_cypher": compiled_cypher,
                "parameters": parameters,
                "result_summary": result_summary,
                "result_count": result_count,
                "cached_at": datetime.now(UTC).isoformat(),
                "ttl_seconds": ttl,
                "hit_count": 0,
            }

            await self._redis.set(key, json.dumps(data), ex=ttl)
            self._stats["sets"] += 1

            self._logger.debug(
                "cache_set",
                query_hash=query_hash,
                ttl_seconds=ttl,
            )
            return True

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_set_error", error=str(e))
            return False

    async def invalidate(self, question: str, user_trust: int) -> bool:
        """Invalidate a cached query result."""
        query_hash = self._hash_query(question, user_trust)
        key = self._make_key(query_hash)

        try:
            await self._redis.delete(key)
            self._stats["deletes"] += 1
            return True
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_invalidate_error", error=str(e))
            return False

    async def invalidate_all(self) -> int:
        """Invalidate all cached query results."""
        try:
            pattern = f"{self._prefix}*"
            keys = []

            # Use SCAN for safety with large datasets
            cursor = 0
            while True:
                cursor, batch = await self._redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            if keys:
                await self._redis.delete(*keys)

            self._stats["deletes"] += len(keys)
            self._logger.info("cache_invalidate_all", keys_removed=len(keys))
            return len(keys)

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_invalidate_all_error", error=str(e))
            return 0

    async def cleanup_expired(self) -> dict[str, int | str]:
        """
        Clean up expired entries.

        Note: Redis handles TTL expiration automatically, but this
        can be used for manual cleanup or stats collection.
        """
        # Redis handles TTL automatically, so this is mainly for stats
        try:
            pattern = f"{self._prefix}*"
            cursor = 0
            total_keys = 0

            while True:
                cursor, batch = await self._redis.scan(cursor, match=pattern, count=100)
                total_keys += len(batch)
                if cursor == 0:
                    break

            self._logger.debug("cache_cleanup_check", total_keys=total_keys)
            return {"checked": total_keys, "removed": 0}  # Redis auto-expires

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_cleanup_error", error=str(e))
            return {"checked": 0, "removed": 0, "error": str(e)}

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            pattern = f"{self._prefix}*"
            cursor = 0
            total_keys = 0

            while True:
                cursor, batch = await self._redis.scan(cursor, match=pattern, count=100)
                total_keys += len(batch)
                if cursor == 0:
                    break

            hit_rate = (
                self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                if (self._stats["hits"] + self._stats["misses"]) > 0
                else 0.0
            )

            return {
                "total_cached": total_keys,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "sets": self._stats["sets"],
                "deletes": self._stats["deletes"],
                "hit_rate": round(hit_rate, 4),
            }

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            self._logger.error("cache_stats_error", error=str(e))
            return {"error": str(e)}


# In-memory fallback cache for when Redis is unavailable
class InMemoryQueryCache:
    """
    In-memory fallback cache.

    Used when Redis is not configured or unavailable.
    """

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, dict[str, Any]] = {}
        self._max_size = max_size
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
        self._logger = logger.bind(service="query_cache_memory")

    def _hash_query(self, question: str, user_trust: int) -> str:
        normalized = question.lower().strip()
        content = f"{normalized}:trust:{user_trust}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def get(self, question: str, user_trust: int) -> CachedQueryResult | None:
        query_hash = self._hash_query(question, user_trust)

        if query_hash not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[query_hash]

        # Check expiration
        cached_at = datetime.fromisoformat(entry["cached_at"])
        ttl = entry.get("ttl_seconds", 3600)
        if (datetime.now(UTC) - cached_at).total_seconds() > ttl:
            del self._cache[query_hash]
            self._stats["misses"] += 1
            return None

        entry["hit_count"] = entry.get("hit_count", 0) + 1
        self._stats["hits"] += 1

        return CachedQueryResult(
            query_hash=query_hash,
            original_question=entry["original_question"],
            compiled_cypher=entry["compiled_cypher"],
            parameters=entry.get("parameters", {}),
            result_summary=entry.get("result_summary", ""),
            result_count=entry.get("result_count", 0),
            cached_at=cached_at,
            ttl_seconds=ttl,
            hit_count=entry["hit_count"],
        )

    async def set(
        self,
        question: str,
        user_trust: int,
        compiled_cypher: str,
        parameters: dict[str, Any],
        result_summary: str = "",
        result_count: int = 0,
        ttl_seconds: int | None = None,
    ) -> bool:
        query_hash = self._hash_query(question, user_trust)

        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k]["cached_at"],
            )
            del self._cache[oldest_key]

        self._cache[query_hash] = {
            "original_question": question,
            "compiled_cypher": compiled_cypher,
            "parameters": parameters,
            "result_summary": result_summary,
            "result_count": result_count,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": ttl_seconds or 3600,
            "hit_count": 0,
        }
        self._stats["sets"] += 1
        return True

    async def invalidate(self, question: str, user_trust: int) -> bool:
        query_hash = self._hash_query(question, user_trust)
        if query_hash in self._cache:
            del self._cache[query_hash]
            self._stats["deletes"] += 1
            return True
        return False

    async def invalidate_all(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._stats["deletes"] += count
        return count

    async def cleanup_expired(self) -> dict[str, int]:
        now = datetime.now(UTC)
        expired = []

        for key, entry in self._cache.items():
            cached_at = datetime.fromisoformat(entry["cached_at"])
            ttl = entry.get("ttl_seconds", 3600)
            if (now - cached_at).total_seconds() > ttl:
                expired.append(key)

        for key in expired:
            del self._cache[key]

        return {"checked": len(self._cache) + len(expired), "removed": len(expired)}

    async def get_stats(self) -> dict[str, Any]:
        hit_rate = (
            self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
            if (self._stats["hits"] + self._stats["misses"]) > 0
            else 0.0
        )
        return {
            "total_cached": len(self._cache),
            "max_size": self._max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "hit_rate": round(hit_rate, 4),
            "backend": "memory",
        }


# Global cache instance
_query_cache: QueryCache | InMemoryQueryCache | None = None


async def init_query_cache() -> QueryCache | InMemoryQueryCache:
    """Initialize the query cache with Redis or fallback to memory."""
    global _query_cache

    if _query_cache is not None:
        return _query_cache

    settings = get_settings()

    if not settings.query_cache_enabled:
        logger.info("query_cache_disabled")
        _query_cache = InMemoryQueryCache(max_size=0)  # Disabled
        return _query_cache

    if settings.redis_url:
        try:
            import redis.asyncio as redis

            client = redis.from_url(  # type: ignore[no-untyped-call]
                settings.redis_url,
                password=settings.redis_password,
                decode_responses=True,
            )
            # Test connection
            await client.ping()

            _query_cache = QueryCache(client)
            logger.info("query_cache_initialized", backend="redis")

        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning(
                "redis_unavailable_using_memory",
                error=str(e),
            )
            _query_cache = InMemoryQueryCache(max_size=settings.query_cache_max_size)
    else:
        logger.info("query_cache_initialized", backend="memory")
        _query_cache = InMemoryQueryCache(max_size=settings.query_cache_max_size)

    return _query_cache


def get_query_cache() -> QueryCache | InMemoryQueryCache | None:
    """Get the query cache instance."""
    return _query_cache


async def close_query_cache() -> None:
    """Close the query cache connection."""
    global _query_cache

    if _query_cache is None:
        return

    if isinstance(_query_cache, QueryCache) and _query_cache._redis:
        try:
            await _query_cache._redis.close()
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            # SECURITY FIX (Audit 5): Log Redis close errors instead of silently ignoring
            logger.warning("query_cache_redis_close_error", error=str(e))

    _query_cache = None
    logger.info("query_cache_closed")
