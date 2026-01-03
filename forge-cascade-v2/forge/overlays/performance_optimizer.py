"""
Performance Optimizer Overlay

Monitors system performance and provides optimization recommendations.
Implements caching strategies, resource allocation hints, and
performance analysis.

Mentioned in spec as core overlay for:
- Determining caching strategy
- Selecting optimal model/parameters
- Resource allocation hints
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from forge.overlays.base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
)
from forge.models.events import Event, EventType


logger = structlog.get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL tracking."""
    value: Any
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    ttl: float = 300.0  # 5 minutes default
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    error_count: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""
    category: str  # caching, scaling, configuration
    priority: str  # low, medium, high, critical
    title: str
    description: str
    expected_improvement: str
    action: dict[str, Any] = field(default_factory=dict)


class PerformanceOptimizerOverlay(BaseOverlay):
    """
    Performance optimization overlay.
    
    Provides:
    - Query result caching
    - Performance monitoring
    - Optimization recommendations
    - Resource allocation hints
    """
    
    NAME = "performance_optimizer"
    VERSION = "1.0.0"
    DESCRIPTION = "Monitors performance and provides optimization hints"
    
    SUBSCRIBED_EVENTS = {EventType.SYSTEM_EVENT, EventType.SYSTEM_ERROR}
    
    def __init__(self):
        super().__init__()
        self._cache: dict[str, CacheEntry] = {}
        self._response_times: list[float] = []
        self._endpoint_metrics: dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self._optimization_history: list[OptimizationRecommendation] = []
        self._cleanup_task: asyncio.Task | None = None
        self._stats: dict[str, Any] = {}
    
    async def initialize(self) -> bool:
        """Initialize performance monitoring."""
        self._logger.info("Initializing performance optimizer")
        
        # Start cache cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self._stats["initialized_at"] = datetime.now(timezone.utc).isoformat()
        
        return await super().initialize()
    
    async def cleanup(self) -> None:
        """Shutdown and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._cache.clear()
        self._logger.info("Performance optimizer shutdown complete")
        await super().cleanup()
    
    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """
        Process performance optimization requests.
        
        Operations:
        - cache_get: Get cached value
        - cache_set: Set cache value
        - get_metrics: Get performance metrics
        - analyze: Analyze and recommend optimizations
        - get_llm_params: Get optimized LLM parameters
        """
        data = input_data or {}
        operation = data.get("operation", "analyze")
        
        try:
            if operation == "cache_get":
                result = await self._cache_get(data)
            elif operation == "cache_set":
                result = await self._cache_set(data)
            elif operation == "record_timing":
                result = await self._record_timing(data)
            elif operation == "get_metrics":
                result = await self._get_metrics(data)
            elif operation == "get_llm_params":
                result = await self._get_optimized_llm_params(data, context)
            elif operation == "analyze":
                result = await self._analyze_and_recommend(data)
            else:
                return OverlayResult.fail(f"Unknown operation: {operation}")
            
            self._stats["operations_processed"] = self._stats.get("operations_processed", 0) + 1
            
            return OverlayResult.ok(result)
            
        except Exception as e:
            self._logger.error("Performance optimizer error", error=str(e))
            return OverlayResult.fail(str(e))
    
    async def _cache_get(self, data: dict) -> dict:
        """Get value from cache."""
        key = data.get("key")
        if not key:
            return {"hit": False, "error": "No key provided"}
        
        entry = self._cache.get(key)
        if entry is None or entry.is_expired:
            self._stats["cache_misses"] = self._stats.get("cache_misses", 0) + 1
            return {"hit": False}
        
        entry.hits += 1
        self._stats["cache_hits"] = self._stats.get("cache_hits", 0) + 1
        
        return {
            "hit": True,
            "value": entry.value,
            "age_seconds": time.time() - entry.created_at,
            "hits": entry.hits,
        }
    
    async def _cache_set(self, data: dict) -> dict:
        """Set value in cache."""
        key = data.get("key")
        value = data.get("value")
        ttl = data.get("ttl", 300.0)
        
        if not key:
            return {"success": False, "error": "No key provided"}
        
        self._cache[key] = CacheEntry(
            value=value,
            ttl=ttl,
        )
        
        return {"success": True, "key": key, "ttl": ttl}
    
    async def _record_timing(self, data: dict) -> dict:
        """Record response timing for analysis."""
        endpoint = data.get("endpoint", "unknown")
        response_time_ms = data.get("response_time_ms", 0)
        success = data.get("success", True)
        
        # Update metrics
        metrics = self._endpoint_metrics[endpoint]
        metrics.total_requests += 1
        
        if not success:
            metrics.error_count += 1
        
        # Keep rolling window of response times
        self._response_times.append(response_time_ms)
        if len(self._response_times) > 1000:
            self._response_times = self._response_times[-1000:]
        
        # Recalculate averages periodically
        if metrics.total_requests % 100 == 0:
            sorted_times = sorted(self._response_times)
            metrics.avg_response_time_ms = sum(sorted_times) / len(sorted_times)
            metrics.p95_response_time_ms = sorted_times[int(len(sorted_times) * 0.95)]
            metrics.p99_response_time_ms = sorted_times[int(len(sorted_times) * 0.99)]
        
        return {"recorded": True, "endpoint": endpoint}
    
    async def _get_metrics(self, data: dict) -> dict:
        """Get current performance metrics."""
        endpoint = data.get("endpoint")
        
        if endpoint:
            metrics = self._endpoint_metrics.get(endpoint)
            if metrics:
                return {
                    "endpoint": endpoint,
                    "avg_response_time_ms": metrics.avg_response_time_ms,
                    "p95_response_time_ms": metrics.p95_response_time_ms,
                    "p99_response_time_ms": metrics.p99_response_time_ms,
                    "total_requests": metrics.total_requests,
                    "error_rate": metrics.error_count / metrics.total_requests if metrics.total_requests > 0 else 0,
                }
            return {"endpoint": endpoint, "error": "No metrics for endpoint"}
        
        # Return aggregate metrics
        cache_hits = self._stats.get("cache_hits", 0)
        cache_misses = self._stats.get("cache_misses", 0)
        
        return {
            "cache_size": len(self._cache),
            "cache_hit_rate": cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0,
            "total_endpoints": len(self._endpoint_metrics),
            "avg_response_time_ms": sum(self._response_times) / len(self._response_times) if self._response_times else 0,
            "operations_processed": self._stats.get("operations_processed", 0),
        }
    
    async def _get_optimized_llm_params(self, data: dict, context: OverlayContext) -> dict:
        """
        Get optimized LLM parameters based on context.
        
        Used by Phase 4 of the pipeline to determine optimal
        model parameters for the current request.
        """
        complexity_score = data.get("complexity_score", 0.5)
        query_length = data.get("query_length", 100)
        trust_level = context.trust_flame
        
        # Check cache first
        cache_key = data.get("cache_key")
        if cache_key:
            cached = await self._cache_get({"key": cache_key})
            if cached.get("hit"):
                return {
                    "use_cache": True,
                    "cached_result": cached["value"],
                }
        
        # Determine optimal parameters based on complexity
        if complexity_score > 0.8:
            # Complex query - use more tokens, higher temperature
            llm_params = {
                "temperature": 0.7,
                "max_tokens": 4000,
                "top_p": 0.95,
            }
        elif complexity_score > 0.5:
            # Medium complexity
            llm_params = {
                "temperature": 0.5,
                "max_tokens": 2000,
                "top_p": 0.9,
            }
        else:
            # Simple query - fast response
            llm_params = {
                "temperature": 0.3,
                "max_tokens": 1000,
                "top_p": 0.85,
            }
        
        # Adjust for trust level
        priority = "high" if trust_level >= 80 else "normal"
        
        return {
            "use_cache": False,
            "llm_params": llm_params,
            "priority": priority,
            "estimated_tokens": query_length * 3,  # Rough estimate
        }
    
    async def _analyze_and_recommend(self, data: dict) -> dict:
        """Analyze system performance and generate recommendations."""
        recommendations: list[dict] = []
        
        # Check cache hit rate
        cache_hits = self._stats.get("cache_hits", 0)
        cache_misses = self._stats.get("cache_misses", 0)
        total_cache_ops = cache_hits + cache_misses
        
        if total_cache_ops > 100:
            hit_rate = cache_hits / total_cache_ops
            if hit_rate < 0.3:
                recommendations.append({
                    "category": "caching",
                    "priority": "high",
                    "title": "Low cache hit rate",
                    "description": f"Cache hit rate is {hit_rate:.1%}, consider increasing TTL or cache size",
                    "expected_improvement": "20-40% latency reduction",
                })
        
        # Check response times
        if self._response_times and len(self._response_times) > 50:
            avg_time = sum(self._response_times) / len(self._response_times)
            if avg_time > 1000:  # > 1 second
                recommendations.append({
                    "category": "performance",
                    "priority": "critical",
                    "title": "High average response time",
                    "description": f"Average response time is {avg_time:.0f}ms",
                    "expected_improvement": "Investigate slow endpoints",
                })
        
        # Check error rates
        for endpoint, metrics in self._endpoint_metrics.items():
            if metrics.total_requests > 50:
                error_rate = metrics.error_count / metrics.total_requests
                if error_rate > 0.05:  # > 5% errors
                    recommendations.append({
                        "category": "reliability",
                        "priority": "high",
                        "title": f"High error rate for {endpoint}",
                        "description": f"Error rate is {error_rate:.1%}",
                        "expected_improvement": "Improve reliability",
                    })
        
        return {
            "recommendations": recommendations,
            "metrics_analyzed": {
                "cache_operations": total_cache_ops,
                "response_samples": len(self._response_times),
                "endpoints_monitored": len(self._endpoint_metrics),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    async def handle_event(self, event: Event) -> None:
        """Handle subscribed events."""
        if event.type == EventType.SYSTEM_ALERT:
            # Log performance-related alerts
            self._logger.warning(
                "System alert received",
                alert_type=event.data.get("type"),
                details=event.data,
            )
    
    async def health_check(self) -> bool:
        """Check overlay health."""
        try:
            # Verify cache is accessible
            await self._cache_set({"key": "_health_check", "value": "ok", "ttl": 60})
            result = await self._cache_get({"key": "_health_check"})
            
            return result.get("hit", False)
        except Exception:
            return False
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                expired_keys = [
                    key for key, entry in self._cache.items()
                    if entry.is_expired
                ]
                
                for key in expired_keys:
                    del self._cache[key]
                
                if expired_keys:
                    self._logger.debug(
                        "Cleaned expired cache entries",
                        count=len(expired_keys),
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Cache cleanup error", error=str(e))
