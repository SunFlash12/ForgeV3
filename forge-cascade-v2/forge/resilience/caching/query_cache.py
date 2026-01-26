"""
Query Cache Implementation
==========================

Two-tier caching system for Forge graph queries.

Tier 1: Redis application cache with TTL based on query type
Tier 2: Neo4j's internal query cache for repeated Cypher patterns
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Generic, TypeVar

import structlog

from forge.resilience.config import CacheConfig, get_resilience_config

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

T = TypeVar("T")

# Try to import redis, but allow graceful degradation
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry(Generic[T]):
    """Represents a cached query result."""

    key: str
    value: T
    created_at: datetime
    expires_at: datetime
    query_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return datetime.now(UTC) > self.expires_at

    @property
    def ttl_remaining(self) -> int:
        """Get remaining TTL in seconds."""
        remaining = (self.expires_at - datetime.now(UTC)).total_seconds()
        return max(0, int(remaining))


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QueryCache:
    """
    Two-tier caching for Forge graph queries.

    The cache automatically invalidates entries when underlying
    capsules change, using event subscriptions to detect modifications.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or get_resilience_config().cache
        self._redis: Any = None
        self._use_redis = False
        self._stats = CacheStats()

        # Fallback in-memory cache
        self._memory_cache: dict[str, CacheEntry[Any]] = {}

        # Track which cache keys depend on which capsule IDs
        self._invalidation_subscriptions: dict[str, set[str]] = defaultdict(set)

    async def initialize(self) -> None:
        """Initialize the cache connection."""
        if not self._config.enabled:
            logger.info("query_cache_disabled")
            return

        if REDIS_AVAILABLE and self._config.redis_url:
            try:
                self._redis = aioredis.from_url(  # type: ignore[no-untyped-call]
                    self._config.redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # We handle encoding ourselves
                )
                # Test connection
                await self._redis.ping()
                self._use_redis = True
                logger.info(
                    "query_cache_redis_connected", redis_url=self._config.redis_url[:20] + "..."
                )
            except (ConnectionError, TimeoutError, OSError, ValueError) as e:
                logger.warning("query_cache_redis_failed", error=str(e), fallback="memory")
                self._use_redis = False
        else:
            logger.info("query_cache_using_memory")

    async def close(self) -> None:
        """Close the cache connection."""
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Any | None:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self._config.enabled:
            return None

        try:
            if self._use_redis:
                data = await self._redis.get(key)
                if data:
                    self._stats.hits += 1
                    # SECURITY FIX (Audit 4): Replace pickle with JSON to prevent RCE
                    return json.loads(data.decode("utf-8"))
                self._stats.misses += 1
                return None
            else:
                entry = self._memory_cache.get(key)
                if entry and not entry.is_expired:
                    self._stats.hits += 1
                    return entry.value
                elif entry:
                    # Remove expired entry
                    del self._memory_cache[key]
                self._stats.misses += 1
                return None

        except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            self._stats.errors += 1
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        query_type: str = "general",
        related_capsule_ids: list[str] | None = None,
    ) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            query_type: Type of query for metrics
            related_capsule_ids: Capsule IDs that should trigger invalidation

        Returns:
            True if successfully cached
        """
        if not self._config.enabled:
            return False

        ttl = ttl or self._config.default_ttl_seconds

        try:
            # Check size limit
            # SECURITY FIX (Audit 4): Replace pickle with JSON to prevent RCE
            serialized = json.dumps(value, default=str).encode("utf-8")
            if len(serialized) > self._config.max_cached_result_bytes:
                logger.warning(
                    "cache_value_too_large",
                    key=key,
                    size=len(serialized),
                    max_size=self._config.max_cached_result_bytes,
                )
                return False

            if self._use_redis:
                await self._redis.setex(key, ttl, serialized)
            else:
                self._memory_cache[key] = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
                    query_type=query_type,
                )

            # Register invalidation triggers
            if related_capsule_ids:
                await self._register_invalidation_triggers(key, related_capsule_ids)

            return True

        except (ConnectionError, TimeoutError, OSError, ValueError, TypeError) as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            self._stats.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        if not self._config.enabled:
            return False

        try:
            if self._use_redis:
                result: int = await self._redis.delete(key)
                return result > 0
            else:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    return True
                return False
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], Any],
        ttl: int | None = None,
        query_type: str = "general",
        related_capsule_ids: list[str] | None = None,
    ) -> Any:
        """
        Get value from cache or compute and cache it.

        Args:
            key: Cache key
            compute_func: Async function to compute value if not cached
            ttl: TTL in seconds
            query_type: Query type for metrics
            related_capsule_ids: Capsule IDs for invalidation

        Returns:
            Cached or computed value
        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value
        if callable(compute_func):
            import asyncio

            if asyncio.iscoroutinefunction(compute_func):
                value = await compute_func()
            else:
                value = compute_func()
        else:
            value = compute_func

        # Cache result
        await self.set(
            key, value, ttl=ttl, query_type=query_type, related_capsule_ids=related_capsule_ids
        )

        return value

    def _sanitize_cache_key_component(self, component: str) -> str:
        """
        SECURITY FIX (Audit 4 - H15): Sanitize cache key components.

        Validates and sanitizes components to prevent cache key injection attacks
        where malicious IDs could overwrite or access other cache entries.

        Args:
            component: The cache key component to sanitize

        Returns:
            Sanitized component safe for use in cache keys

        Raises:
            ValueError: If component contains disallowed characters
        """
        import re

        # Convert to string if needed
        component_str = str(component)

        # Validate format - only allow alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", component_str):
            # Log the issue and sanitize
            import hashlib

            # Hash the invalid component to create a safe key
            safe_key = hashlib.sha256(component_str.encode()).hexdigest()[:32]
            logger.warning(
                "cache_key_sanitized",
                original_length=len(component_str),
                reason="Invalid characters or length",
            )
            return f"sanitized_{safe_key}"

        return component_str

    async def get_or_compute_lineage(
        self, capsule_id: str, depth: int, compute_func: Callable[[], Any]
    ) -> Any:
        """
        Get or compute lineage query result with appropriate TTL.

        Lineage queries get longer TTLs for stable lineage chains.

        SECURITY FIX (Audit 4 - H15): Now sanitizes capsule_id to prevent
        cache key injection attacks.
        """
        # SECURITY FIX: Sanitize cache key components
        safe_capsule_id = self._sanitize_cache_key_component(capsule_id)
        safe_depth = max(1, min(int(depth), 100))  # Clamp depth to reasonable range

        key = self._config.lineage_key_pattern.format(capsule_id=safe_capsule_id, depth=safe_depth)

        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value
        import asyncio

        if asyncio.iscoroutinefunction(compute_func):
            result = await compute_func()
        else:
            result = compute_func()

        # Compute TTL based on lineage stability
        ttl = await self._compute_lineage_ttl(result)

        # Get all capsule IDs in lineage for invalidation
        capsule_ids = self._extract_capsule_ids(result)

        await self.set(key, result, ttl=ttl, query_type="lineage", related_capsule_ids=capsule_ids)

        return result

    async def get_or_compute_search(
        self, query: str, filters: dict[str, Any], compute_func: Callable[[], Any]
    ) -> Any:
        """
        Get or compute search query result.

        Search results have moderate TTL as they may change more frequently.
        """
        query_hash = self._hash_query(query, filters)
        key = self._config.search_key_pattern.format(query_hash=query_hash)

        return await self.get_or_compute(
            key, compute_func, ttl=self._config.search_ttl_seconds, query_type="search"
        )

    async def invalidate_for_capsule(self, capsule_id: str) -> int:
        """
        Invalidate all cache entries affected by a capsule change.

        Args:
            capsule_id: ID of the changed capsule

        Returns:
            Number of invalidated entries
        """
        triggers = self._invalidation_subscriptions.get(capsule_id, set())
        if not triggers:
            return 0

        count = 0
        for cache_key in list(triggers):
            if await self.delete(cache_key):
                count += 1

        # Clean up subscription tracking
        if capsule_id in self._invalidation_subscriptions:
            del self._invalidation_subscriptions[capsule_id]

        self._stats.invalidations += count

        logger.debug("cache_invalidated", capsule_id=capsule_id, count=count)

        return count

    async def clear_all(self) -> int:
        """Clear all cache entries."""
        count = 0

        if self._use_redis:
            # Use pattern matching to delete only Forge keys
            async for key in self._redis.scan_iter("forge:*"):
                await self._redis.delete(key)
                count += 1
        else:
            count = len(self._memory_cache)
            self._memory_cache.clear()

        self._invalidation_subscriptions.clear()

        return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    async def _register_invalidation_triggers(self, cache_key: str, capsule_ids: list[str]) -> None:
        """Register cache key for invalidation when capsules change."""
        for capsule_id in capsule_ids:
            self._invalidation_subscriptions[capsule_id].add(cache_key)

    async def _compute_lineage_ttl(self, lineage_result: Any) -> int:
        """
        Compute TTL based on lineage stability.

        Recently modified capsules get shorter TTLs; stable lineage
        chains get longer caching periods.
        """
        # Try to extract modification timestamps
        try:
            if hasattr(lineage_result, "all_capsules"):
                capsules = lineage_result.all_capsules()
            elif isinstance(lineage_result, list):
                capsules = lineage_result
            elif isinstance(lineage_result, dict) and "capsules" in lineage_result:
                capsules = lineage_result["capsules"]
            else:
                return self._config.default_ttl_seconds

            if not capsules:
                return self._config.lineage_ttl_seconds

            # Find most recent modification
            most_recent = datetime.min
            for capsule in capsules:
                if hasattr(capsule, "updated_at") and capsule.updated_at:
                    if capsule.updated_at > most_recent:
                        most_recent = capsule.updated_at
                elif isinstance(capsule, dict) and "updated_at" in capsule:
                    ts = capsule["updated_at"]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts > most_recent:
                        most_recent = ts

            if most_recent == datetime.min:
                return self._config.lineage_ttl_seconds

            age_hours = (datetime.now(UTC) - most_recent).total_seconds() / 3600

            if age_hours < 1:
                return 60  # 1 minute for very recent changes
            elif age_hours < 24:
                return 300  # 5 minutes for changes within a day
            elif age_hours < 168:  # 1 week
                return 1800  # 30 minutes
            else:
                return 3600  # 1 hour for stable lineage

        except (ValueError, TypeError, KeyError, AttributeError, OSError):
            return self._config.default_ttl_seconds

    def _extract_capsule_ids(self, result: Any) -> list[str]:
        """Extract capsule IDs from a result for invalidation tracking."""
        ids = []

        try:
            if hasattr(result, "all_capsule_ids"):
                ids = result.all_capsule_ids()
            elif hasattr(result, "all_capsules"):
                ids = [c.id for c in result.all_capsules() if hasattr(c, "id")]
            elif isinstance(result, list):
                for item in result:
                    if hasattr(item, "id"):
                        ids.append(item.id)
                    elif isinstance(item, dict) and "id" in item:
                        ids.append(item["id"])
            elif isinstance(result, dict):
                if "id" in result:
                    ids.append(result["id"])
                if "capsules" in result:
                    ids.extend(self._extract_capsule_ids(result["capsules"]))
        except (ValueError, TypeError, KeyError, AttributeError):
            pass

        return ids

    def _hash_query(self, query: str, filters: dict[str, Any]) -> str:
        """Create a hash for a search query."""
        content = json.dumps({"query": query, "filters": filters}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Global cache instance
_query_cache: QueryCache | None = None


async def get_query_cache() -> QueryCache:
    """Get or create the global query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
        await _query_cache.initialize()
    return _query_cache


async def invalidate_cache_for_capsule(capsule_id: str) -> int:
    """Convenience function to invalidate cache for a capsule change."""
    cache = await get_query_cache()
    return await cache.invalidate_for_capsule(capsule_id)
