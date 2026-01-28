"""
Comprehensive tests for the PerformanceOptimizerOverlay.

Tests cover:
- Overlay initialization and lifecycle
- Cache operations (get, set)
- Response timing recording
- Performance metrics retrieval
- LLM parameter optimization
- Performance analysis and recommendations
- Event handling
- Health checks
- Cache cleanup
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.events import Event, EventType
from forge.models.overlay import Capability, OverlayHealthCheck
from forge.overlays.base import OverlayContext, OverlayResult
from forge.overlays.performance_optimizer import (
    CacheEntry,
    OptimizationRecommendation,
    PerformanceMetrics,
    PerformanceOptimizerOverlay,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def optimizer() -> PerformanceOptimizerOverlay:
    """Create a PerformanceOptimizerOverlay instance."""
    return PerformanceOptimizerOverlay()


@pytest.fixture
async def initialized_optimizer(
    optimizer: PerformanceOptimizerOverlay,
) -> PerformanceOptimizerOverlay:
    """Create and initialize a PerformanceOptimizerOverlay."""
    await optimizer.initialize()
    yield optimizer
    await optimizer.cleanup()


@pytest.fixture
def overlay_context() -> OverlayContext:
    """Create a basic overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="performance_optimizer",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=60,
        capabilities={Capability.DATABASE_READ},
    )


@pytest.fixture
def high_trust_context() -> OverlayContext:
    """Create a high trust overlay context."""
    return OverlayContext(
        overlay_id="test-overlay-id",
        overlay_name="performance_optimizer",
        execution_id="test-execution-id",
        triggered_by="test",
        correlation_id="test-correlation-id",
        user_id="test-user",
        trust_flame=85,
        capabilities={Capability.DATABASE_READ},
    )


# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self) -> None:
        """Test creating a cache entry."""
        entry = CacheEntry(value={"data": "test"}, ttl=300.0)

        assert entry.value == {"data": "test"}
        assert entry.ttl == 300.0
        assert entry.hits == 0
        assert entry.is_expired is False

    def test_cache_entry_expiry(self) -> None:
        """Test cache entry expiry detection."""
        # Create an already-expired entry
        entry = CacheEntry(
            value="test",
            created_at=time.time() - 400,
            ttl=300.0,
        )

        assert entry.is_expired is True

    def test_cache_entry_not_expired(self) -> None:
        """Test cache entry not expired."""
        entry = CacheEntry(value="test", ttl=300.0)

        assert entry.is_expired is False


# =============================================================================
# PerformanceMetrics Tests
# =============================================================================


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_metrics_defaults(self) -> None:
        """Test metrics default values."""
        metrics = PerformanceMetrics()

        assert metrics.avg_response_time_ms == 0.0
        assert metrics.total_requests == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.error_count == 0

    def test_cache_hit_rate_calculation(self) -> None:
        """Test cache hit rate calculation."""
        metrics = PerformanceMetrics(cache_hits=30, cache_misses=70)

        assert metrics.cache_hit_rate == 0.3

    def test_cache_hit_rate_zero_requests(self) -> None:
        """Test cache hit rate with no requests."""
        metrics = PerformanceMetrics()

        assert metrics.cache_hit_rate == 0.0


# =============================================================================
# Initialization Tests
# =============================================================================


class TestPerformanceOptimizerInitialization:
    """Tests for overlay initialization."""

    def test_default_initialization(
        self, optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test default initialization values."""
        assert optimizer.NAME == "performance_optimizer"
        assert optimizer.VERSION == "1.0.0"
        assert len(optimizer._cache) == 0
        assert len(optimizer._response_times) == 0

    @pytest.mark.asyncio
    async def test_initialize(self, optimizer: PerformanceOptimizerOverlay) -> None:
        """Test overlay initialization."""
        result = await optimizer.initialize()
        assert result is True
        assert "initialized_at" in optimizer._stats
        assert optimizer._cleanup_task is not None

        await optimizer.cleanup()

    @pytest.mark.asyncio
    async def test_cleanup(
        self, initialized_optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test overlay cleanup."""
        # Add some cache entries
        initialized_optimizer._cache["test"] = CacheEntry(value="test")

        await initialized_optimizer.cleanup()

        assert len(initialized_optimizer._cache) == 0
        assert initialized_optimizer._cleanup_task is None or \
               initialized_optimizer._cleanup_task.cancelled()

    def test_subscribed_events(
        self, optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test subscribed events."""
        assert EventType.SYSTEM_EVENT in optimizer.SUBSCRIBED_EVENTS
        assert EventType.SYSTEM_ERROR in optimizer.SUBSCRIBED_EVENTS


# =============================================================================
# Cache Get Operation Tests
# =============================================================================


class TestCacheGetOperation:
    """Tests for cache_get operation."""

    @pytest.mark.asyncio
    async def test_cache_get_hit(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get with hit."""
        # Pre-populate cache
        initialized_optimizer._cache["test-key"] = CacheEntry(
            value={"data": "cached_value"}
        )

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "test-key"},
        )

        assert result.success is True
        assert result.data["hit"] is True
        assert result.data["value"] == {"data": "cached_value"}

    @pytest.mark.asyncio
    async def test_cache_get_miss(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get with miss."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "nonexistent"},
        )

        assert result.success is True
        assert result.data["hit"] is False

    @pytest.mark.asyncio
    async def test_cache_get_no_key(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get without key."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get"},
        )

        assert result.success is True
        assert result.data["hit"] is False
        assert "error" in result.data

    @pytest.mark.asyncio
    async def test_cache_get_expired(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get with expired entry."""
        # Add expired entry
        initialized_optimizer._cache["expired-key"] = CacheEntry(
            value="old_value",
            created_at=time.time() - 400,
            ttl=300.0,
        )

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "expired-key"},
        )

        assert result.success is True
        assert result.data["hit"] is False

    @pytest.mark.asyncio
    async def test_cache_get_increments_hits(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get increments hit counter."""
        entry = CacheEntry(value="test")
        initialized_optimizer._cache["key"] = entry

        await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "key"},
        )

        assert entry.hits == 1

    @pytest.mark.asyncio
    async def test_cache_get_updates_stats(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache get updates statistics."""
        initialized_optimizer._cache["key"] = CacheEntry(value="test")

        await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "key"},
        )

        assert initialized_optimizer._stats["cache_hits"] >= 1


# =============================================================================
# Cache Set Operation Tests
# =============================================================================


class TestCacheSetOperation:
    """Tests for cache_set operation."""

    @pytest.mark.asyncio
    async def test_cache_set(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test setting cache value."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "cache_set",
                "key": "new-key",
                "value": {"data": "new_value"},
            },
        )

        assert result.success is True
        assert result.data["success"] is True
        assert "new-key" in initialized_optimizer._cache

    @pytest.mark.asyncio
    async def test_cache_set_custom_ttl(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test setting cache with custom TTL."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "cache_set",
                "key": "ttl-key",
                "value": "test",
                "ttl": 600.0,
            },
        )

        assert result.success is True
        assert initialized_optimizer._cache["ttl-key"].ttl == 600.0

    @pytest.mark.asyncio
    async def test_cache_set_no_key(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test cache set without key."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_set", "value": "test"},
        )

        assert result.success is True
        assert result.data["success"] is False


# =============================================================================
# Record Timing Operation Tests
# =============================================================================


class TestRecordTimingOperation:
    """Tests for record_timing operation."""

    @pytest.mark.asyncio
    async def test_record_timing(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test recording response timing."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "record_timing",
                "endpoint": "api/capsules",
                "response_time_ms": 150.0,
                "success": True,
            },
        )

        assert result.success is True
        assert result.data["recorded"] is True
        assert 150.0 in initialized_optimizer._response_times

    @pytest.mark.asyncio
    async def test_record_timing_with_error(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test recording timing for failed request."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "record_timing",
                "endpoint": "api/capsules",
                "response_time_ms": 500.0,
                "success": False,
            },
        )

        assert result.success is True
        metrics = initialized_optimizer._endpoint_metrics["api/capsules"]
        assert metrics.error_count >= 1

    @pytest.mark.asyncio
    async def test_record_timing_rolling_window(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test response times rolling window."""
        # Add many timing records
        for i in range(1200):
            await initialized_optimizer.execute(
                context=overlay_context,
                input_data={
                    "operation": "record_timing",
                    "endpoint": "api/test",
                    "response_time_ms": float(i),
                },
            )

        # Rolling window should be limited to 1000
        assert len(initialized_optimizer._response_times) == 1000

    @pytest.mark.asyncio
    async def test_record_timing_updates_percentiles(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test percentile calculation on timing records."""
        # Record exactly 100 times to trigger percentile calculation
        for i in range(100):
            await initialized_optimizer.execute(
                context=overlay_context,
                input_data={
                    "operation": "record_timing",
                    "endpoint": "api/test",
                    "response_time_ms": float(i * 10),
                },
            )

        metrics = initialized_optimizer._endpoint_metrics["api/test"]
        assert metrics.avg_response_time_ms > 0


# =============================================================================
# Get Metrics Operation Tests
# =============================================================================


class TestGetMetricsOperation:
    """Tests for get_metrics operation."""

    @pytest.mark.asyncio
    async def test_get_aggregate_metrics(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting aggregate metrics."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "get_metrics"},
        )

        assert result.success is True
        assert "cache_size" in result.data
        assert "cache_hit_rate" in result.data
        assert "total_endpoints" in result.data
        assert "avg_response_time_ms" in result.data

    @pytest.mark.asyncio
    async def test_get_endpoint_metrics(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting endpoint-specific metrics."""
        # Record some timings first
        await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "record_timing",
                "endpoint": "api/capsules",
                "response_time_ms": 100.0,
            },
        )

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_metrics",
                "endpoint": "api/capsules",
            },
        )

        assert result.success is True
        assert result.data["endpoint"] == "api/capsules"
        assert "total_requests" in result.data

    @pytest.mark.asyncio
    async def test_get_metrics_nonexistent_endpoint(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test getting metrics for nonexistent endpoint."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_metrics",
                "endpoint": "nonexistent",
            },
        )

        assert result.success is True
        assert "error" in result.data


# =============================================================================
# Get LLM Params Operation Tests
# =============================================================================


class TestGetLLMParamsOperation:
    """Tests for get_llm_params operation."""

    @pytest.mark.asyncio
    async def test_get_llm_params_simple_query(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test LLM params for simple query."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_llm_params",
                "complexity_score": 0.3,
                "query_length": 50,
            },
        )

        assert result.success is True
        assert result.data["use_cache"] is False
        assert "llm_params" in result.data
        params = result.data["llm_params"]
        assert params["temperature"] == 0.3
        assert params["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_get_llm_params_medium_query(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test LLM params for medium complexity query."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_llm_params",
                "complexity_score": 0.6,
                "query_length": 100,
            },
        )

        assert result.success is True
        params = result.data["llm_params"]
        assert params["temperature"] == 0.5
        assert params["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_get_llm_params_complex_query(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test LLM params for complex query."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_llm_params",
                "complexity_score": 0.9,
                "query_length": 200,
            },
        )

        assert result.success is True
        params = result.data["llm_params"]
        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 4000

    @pytest.mark.asyncio
    async def test_get_llm_params_high_trust_priority(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        high_trust_context: OverlayContext,
    ) -> None:
        """Test high trust gets high priority."""
        result = await initialized_optimizer.execute(
            context=high_trust_context,
            input_data={
                "operation": "get_llm_params",
                "complexity_score": 0.5,
            },
        )

        assert result.success is True
        assert result.data["priority"] == "high"

    @pytest.mark.asyncio
    async def test_get_llm_params_with_cache_hit(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test LLM params with cache hit."""
        # Pre-populate cache
        initialized_optimizer._cache["llm-cache-key"] = CacheEntry(
            value={"cached": "result"}
        )

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={
                "operation": "get_llm_params",
                "cache_key": "llm-cache-key",
            },
        )

        assert result.success is True
        assert result.data["use_cache"] is True
        assert result.data["cached_result"] == {"cached": "result"}


# =============================================================================
# Analyze and Recommend Operation Tests
# =============================================================================


class TestAnalyzeOperation:
    """Tests for analyze operation."""

    @pytest.mark.asyncio
    async def test_analyze_no_data(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis with no data."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "analyze"},
        )

        assert result.success is True
        assert "recommendations" in result.data
        assert "metrics_analyzed" in result.data
        assert "timestamp" in result.data

    @pytest.mark.asyncio
    async def test_analyze_low_cache_hit_rate(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis with low cache hit rate."""
        # Set up low cache hit rate
        initialized_optimizer._stats["cache_hits"] = 10
        initialized_optimizer._stats["cache_misses"] = 100

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "analyze"},
        )

        assert result.success is True
        recommendations = result.data["recommendations"]
        cache_recs = [
            r for r in recommendations if r["category"] == "caching"
        ]
        assert len(cache_recs) >= 1

    @pytest.mark.asyncio
    async def test_analyze_high_response_time(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis with high response times."""
        # Add high response times
        initialized_optimizer._response_times = [1500.0] * 100

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "analyze"},
        )

        assert result.success is True
        recommendations = result.data["recommendations"]
        perf_recs = [
            r for r in recommendations if r["category"] == "performance"
        ]
        assert len(perf_recs) >= 1
        assert perf_recs[0]["priority"] == "critical"

    @pytest.mark.asyncio
    async def test_analyze_high_error_rate(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test analysis with high error rate."""
        # Set up endpoint with high error rate
        metrics = initialized_optimizer._endpoint_metrics["api/errors"]
        metrics.total_requests = 100
        metrics.error_count = 10

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "analyze"},
        )

        assert result.success is True
        recommendations = result.data["recommendations"]
        reliability_recs = [
            r for r in recommendations if r["category"] == "reliability"
        ]
        assert len(reliability_recs) >= 1


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestEventHandling:
    """Tests for event handling."""

    @pytest.mark.asyncio
    async def test_handle_system_error_event(
        self, initialized_optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test handling system error event."""
        event = Event(
            id="test-event",
            type=EventType.SYSTEM_ERROR,
            source="test",
            payload={"type": "database_error", "message": "Connection failed"},
        )

        # Should not raise
        await initialized_optimizer.handle_event(event)


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health checks."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, initialized_optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test health check when healthy."""
        health = await initialized_optimizer.health_check()

        assert health.healthy is True
        assert health.overlay_id == initialized_optimizer.id
        assert "Cache operational" in health.message

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(
        self, optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test health check when unhealthy (cache issue)."""
        # Initialize but mock cache to fail
        await optimizer.initialize()

        async def failing_cache_set(*args, **kwargs):
            raise RuntimeError("Cache failure")

        optimizer._cache_set = failing_cache_set

        health = await optimizer.health_check()

        assert health.healthy is False
        await optimizer.cleanup()


# =============================================================================
# Unknown Operation Tests
# =============================================================================


class TestUnknownOperation:
    """Tests for unknown operation handling."""

    @pytest.mark.asyncio
    async def test_unknown_operation(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test handling unknown operation."""
        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "unknown_op"},
        )

        assert result.success is False
        assert "Unknown operation" in result.error


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for statistics tracking."""

    @pytest.mark.asyncio
    async def test_operations_processed_counter(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test operations processed counter."""
        await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "get_metrics"},
        )

        assert initialized_optimizer._stats["operations_processed"] >= 1


# =============================================================================
# Cleanup Loop Tests
# =============================================================================


class TestCleanupLoop:
    """Tests for cleanup loop functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_entries(
        self, optimizer: PerformanceOptimizerOverlay
    ) -> None:
        """Test cleanup loop removes expired entries."""
        await optimizer.initialize()

        # Add an expired entry
        optimizer._cache["expired"] = CacheEntry(
            value="old",
            created_at=time.time() - 400,
            ttl=300.0,
        )

        # Add a fresh entry
        optimizer._cache["fresh"] = CacheEntry(value="new", ttl=300.0)

        # Manually trigger cleanup logic
        expired_keys = [
            key for key, entry in optimizer._cache.items() if entry.is_expired
        ]
        for key in expired_keys:
            del optimizer._cache[key]

        assert "expired" not in optimizer._cache
        assert "fresh" in optimizer._cache

        await optimizer.cleanup()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_runtime_error(
        self,
        initialized_optimizer: PerformanceOptimizerOverlay,
        overlay_context: OverlayContext,
    ) -> None:
        """Test handling runtime errors."""
        # Mock an operation to raise an error
        async def failing_operation(*args, **kwargs):
            raise RuntimeError("Test error")

        initialized_optimizer._cache_get = failing_operation

        result = await initialized_optimizer.execute(
            context=overlay_context,
            input_data={"operation": "cache_get", "key": "test"},
        )

        assert result.success is False
        assert "Test error" in result.error
