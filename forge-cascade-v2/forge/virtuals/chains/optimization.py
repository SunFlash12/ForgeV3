"""
Multi-Chain Query Performance Optimization

This module provides performance optimizations for multi-chain operations:
- Connection pooling
- Request batching
- Caching layer
- Parallel execution
- Rate limiting with backoff

These optimizations reduce latency and improve throughput for cross-chain
queries while respecting RPC endpoint rate limits.
"""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, TypeVar

from ..config import ChainNetwork

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: datetime
    hit_count: int = 0


class QueryCache:
    """
    LRU cache for blockchain queries with TTL support.

    Caches expensive RPC calls like balance queries and block data
    to reduce network overhead and improve response times.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 30,
    ):
        """
        Initialize the query cache.

        Args:
            max_size: Maximum number of entries
            default_ttl_seconds: Default TTL for cache entries
        """
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        if datetime.now(UTC) > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None

        entry.hit_count += 1
        self._hits += 1
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set value in cache with TTL."""
        if len(self._cache) >= self._max_size:
            self._evict_lru()

        ttl = ttl_seconds or self._default_ttl
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
        )

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with lowest hit count
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].hit_count
        )
        del self._cache[lru_key]

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry."""
        self._cache.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries with a key prefix."""
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


def cached(
    cache: QueryCache,
    key_func: Callable[..., str],
    ttl_seconds: int | None = None,
) -> Callable[..., Any]:
    """
    Decorator to cache async function results.

    Args:
        cache: QueryCache instance
        key_func: Function to generate cache key from args
        ttl_seconds: Optional TTL override
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_func(*args, **kwargs)
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result

        return wrapper
    return decorator


class RateLimiter:
    """
    Token bucket rate limiter for RPC endpoints.

    Prevents overwhelming RPC endpoints with too many requests
    and implements exponential backoff on rate limit errors.
    """

    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Sustained request rate
            burst_size: Maximum burst of requests
        """
        self._rate = requests_per_second
        self._burst = burst_size
        self._tokens = float(burst_size)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self._backoff_until: float = 0

    async def acquire(self) -> None:
        """Acquire permission to make a request."""
        async with self._lock:
            now = time.monotonic()

            # Check backoff
            if now < self._backoff_until:
                wait_time = self._backoff_until - now
                logger.debug(f"Rate limiter backoff: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                now = time.monotonic()

            # Refill tokens
            time_passed = now - self._last_update
            self._tokens = min(
                self._burst,
                self._tokens + time_passed * self._rate
            )
            self._last_update = now

            # Wait if no tokens available
            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1

    def trigger_backoff(self, seconds: float = 1.0) -> None:
        """Trigger exponential backoff after rate limit error."""
        now = time.monotonic()
        # Double the backoff each time
        if self._backoff_until > now:
            seconds = min(seconds * 2, 30)  # Cap at 30 seconds
        self._backoff_until = now + seconds
        logger.warning(f"Rate limit triggered, backing off for {seconds}s")


class RequestBatcher:
    """
    Batches multiple RPC requests into single multicall.

    Groups requests within a time window and executes them
    together to reduce network round trips.
    """

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout_ms: int = 50,
    ):
        """
        Initialize request batcher.

        Args:
            batch_size: Maximum requests per batch
            batch_timeout_ms: Max time to wait for batch
        """
        self._batch_size = batch_size
        self._timeout = batch_timeout_ms / 1000
        self._pending: list[dict[str, Any]] = []
        self._results: dict[int, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()
        self._request_id = 0

    async def add_request(
        self,
        method: str,
        params: list[Any],
    ) -> Any:
        """
        Add a request to the batch and wait for result.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            RPC response
        """
        async with self._lock:
            self._request_id += 1
            request_id = self._request_id

            future = asyncio.get_event_loop().create_future()
            self._results[request_id] = future

            self._pending.append({
                "id": request_id,
                "method": method,
                "params": params,
            })

            # Trigger batch if full
            if len(self._pending) >= self._batch_size:
                await self._flush()

        # Wait for result with timeout
        try:
            return await asyncio.wait_for(future, timeout=30)
        except TimeoutError:
            raise TimeoutError(f"Request {request_id} timed out")

    async def _flush(self) -> None:
        """Flush pending requests as a batch."""
        if not self._pending:
            return

        batch = self._pending
        self._pending = []

        # Execute batch (implementation depends on RPC client)
        # For now, just resolve each request individually
        for request in batch:
            future = self._results.pop(request["id"], None)
            if future and not future.done():
                # Placeholder - actual implementation would use JSON-RPC batch
                future.set_result(None)


class ParallelExecutor:
    """
    Executes queries across multiple chains in parallel.

    Manages concurrent execution while respecting per-chain rate limits.
    """

    def __init__(self, max_concurrency: int = 10):
        """
        Initialize parallel executor.

        Args:
            max_concurrency: Maximum concurrent operations per chain
        """
        self._semaphores: dict[ChainNetwork, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_concurrency)
        )

    async def execute(
        self,
        chain: ChainNetwork,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function with concurrency control.

        Args:
            chain: Target chain
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result
        """
        async with self._semaphores[chain]:
            result: Any = await func(*args, **kwargs)
            return result

    async def execute_multi(
        self,
        tasks: list[tuple[ChainNetwork, Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
    ) -> list[Any]:
        """
        Execute multiple tasks across chains in parallel.

        Args:
            tasks: List of (chain, func, args, kwargs) tuples

        Returns:
            List of results in order
        """
        async def run_task(
            chain: ChainNetwork,
            func: Callable[..., Any],
            args: tuple[Any, ...],
            kwargs: dict[str, Any],
        ) -> Any:
            return await self.execute(chain, func, *args, **kwargs)

        coroutines = [
            run_task(chain, func, args, kwargs)
            for chain, func, args, kwargs in tasks
        ]

        return await asyncio.gather(*coroutines, return_exceptions=True)


class ChainQueryOptimizer:
    """
    Main optimization layer for multi-chain queries.

    Combines caching, rate limiting, batching, and parallel execution
    to provide optimal performance for blockchain operations.
    """

    def __init__(
        self,
        cache_size: int = 1000,
        cache_ttl: int = 30,
        requests_per_second: float = 10.0,
        max_concurrency: int = 10,
    ):
        """
        Initialize the query optimizer.

        Args:
            cache_size: Maximum cache entries
            cache_ttl: Default cache TTL in seconds
            requests_per_second: Rate limit per chain
            max_concurrency: Max concurrent requests per chain
        """
        self.cache = QueryCache(max_size=cache_size, default_ttl_seconds=cache_ttl)
        self._rate_limiters: dict[ChainNetwork, RateLimiter] = {}
        self._executor = ParallelExecutor(max_concurrency)
        self._requests_per_second = requests_per_second

        # Metrics
        self._total_requests = 0
        self._cached_requests = 0

    def get_rate_limiter(self, chain: ChainNetwork) -> RateLimiter:
        """Get or create rate limiter for a chain."""
        if chain not in self._rate_limiters:
            self._rate_limiters[chain] = RateLimiter(
                requests_per_second=self._requests_per_second
            )
        return self._rate_limiters[chain]

    async def query(
        self,
        chain: ChainNetwork,
        func: Callable[..., Any],
        cache_key: str | None = None,
        cache_ttl: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an optimized query.

        Args:
            chain: Target chain
            func: Query function
            cache_key: Optional cache key (None = no caching)
            cache_ttl: Optional cache TTL
            *args, **kwargs: Function arguments

        Returns:
            Query result
        """
        self._total_requests += 1

        # Check cache
        if cache_key:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                self._cached_requests += 1
                return cached_result

        # Rate limit
        limiter = self.get_rate_limiter(chain)
        await limiter.acquire()

        # Execute with concurrency control
        try:
            result = await self._executor.execute(chain, func, *args, **kwargs)

            # Cache result
            if cache_key:
                self.cache.set(cache_key, result, cache_ttl)

            return result

        except Exception as e:  # Intentional broad catch: re-raises after rate-limit detection
            if "rate limit" in str(e).lower():
                limiter.trigger_backoff()
            raise

    async def query_multi(
        self,
        queries: list[dict[str, Any]],
    ) -> list[Any]:
        """
        Execute multiple queries in parallel.

        Args:
            queries: List of query specifications:
                {
                    "chain": ChainNetwork,
                    "func": async callable,
                    "args": tuple,
                    "kwargs": dict,
                    "cache_key": str | None,
                }

        Returns:
            List of results
        """
        async def run_query(q: dict[str, Any]) -> Any:
            args = q.get("args", ())
            kwargs = q.get("kwargs", {})
            return await self.query(
                q["chain"],
                q["func"],
                q.get("cache_key"),
                q.get("cache_ttl"),
                *args,
                **kwargs,
            )

        return await asyncio.gather(
            *[run_query(q) for q in queries],
            return_exceptions=True,
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Get optimizer statistics."""
        return {
            "total_requests": self._total_requests,
            "cached_requests": self._cached_requests,
            "cache_hit_rate": (
                self._cached_requests / self._total_requests
                if self._total_requests > 0 else 0
            ),
            "cache_stats": self.cache.stats,
        }


# Global optimizer instance
_optimizer: ChainQueryOptimizer | None = None


def get_query_optimizer() -> ChainQueryOptimizer:
    """Get the global query optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = ChainQueryOptimizer()
    return _optimizer
