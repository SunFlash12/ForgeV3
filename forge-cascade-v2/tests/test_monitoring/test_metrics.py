"""
Comprehensive tests for forge.monitoring.metrics module.

Tests cover:
- Metric types (Counter, Gauge, Histogram, Summary)
- Metrics Registry
- Cardinality limits (security feature)
- Prometheus format export
- Decorators and context managers
- FastAPI integration
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.monitoring.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    Summary,
    add_metrics_middleware,
    create_metrics_endpoint,
    get_metrics_registry,
    reset_metrics,
    track_in_progress,
    track_time,
)


# =============================================================================
# Tests for Counter
# =============================================================================


class TestCounter:
    """Tests for Counter metric type."""

    def test_initialization(self) -> None:
        """Verify counter is initialized correctly."""
        counter = Counter(
            name="test_counter",
            description="A test counter",
            labels=["method", "status"],
        )

        assert counter.name == "test_counter"
        assert counter.description == "A test counter"
        assert counter.labels == ["method", "status"]

    def test_increment_without_labels(self) -> None:
        """Verify counter increments without labels."""
        counter = Counter(name="test_counter", description="Test")

        counter.inc()
        counter.inc()
        counter.inc(5.0)

        collected = counter.collect()
        assert len(collected) == 1
        assert collected[0]["value"] == 7.0

    def test_increment_with_labels(self) -> None:
        """Verify counter increments with labels."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["method"],
        )

        counter.inc(method="GET")
        counter.inc(method="GET")
        counter.inc(method="POST")

        collected = counter.collect()
        assert len(collected) == 2

        # Find GET and POST values
        get_value = next(c["value"] for c in collected if c["labels"]["method"] == "GET")
        post_value = next(c["value"] for c in collected if c["labels"]["method"] == "POST")

        assert get_value == 2.0
        assert post_value == 1.0

    def test_increment_with_multiple_labels(self) -> None:
        """Verify counter works with multiple labels."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["method", "status"],
        )

        counter.inc(method="GET", status="200")
        counter.inc(method="GET", status="200")
        counter.inc(method="GET", status="404")
        counter.inc(method="POST", status="200")

        collected = counter.collect()
        assert len(collected) == 3

    def test_collect_format(self) -> None:
        """Verify collect returns correct format."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["method"],
        )
        counter.inc(method="GET")

        collected = counter.collect()

        assert collected[0]["name"] == "test_counter"
        assert collected[0]["type"] == "counter"
        assert "labels" in collected[0]
        assert "value" in collected[0]

    def test_cardinality_limit(self) -> None:
        """Verify cardinality limit is enforced."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["id"],
        )
        counter._max_cardinality = 10  # Set low limit for testing

        # Add 15 unique label combinations
        for i in range(15):
            counter.inc(id=f"id_{i}")

        collected = counter.collect()
        # Should only have 10 unique label combinations
        assert len(collected) == 10

    def test_cardinality_limit_warning(self) -> None:
        """Verify warning is logged when cardinality limit is hit."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["id"],
        )
        counter._max_cardinality = 5

        # Fill up to limit
        for i in range(5):
            counter.inc(id=f"id_{i}")

        assert not counter._cardinality_warned

        # This should trigger warning
        counter.inc(id="id_new")

        assert counter._cardinality_warned

    def test_existing_labels_not_blocked_by_cardinality(self) -> None:
        """Verify existing label combinations can still be incremented."""
        counter = Counter(
            name="test_counter",
            description="Test",
            labels=["id"],
        )
        counter._max_cardinality = 5

        # Fill up to limit
        for i in range(5):
            counter.inc(id=f"id_{i}")

        # Try to add new (should be blocked)
        counter.inc(id="new_id")

        # But existing should still work
        counter.inc(id="id_0", value=10.0)

        collected = counter.collect()
        id_0_value = next(c["value"] for c in collected if c["labels"]["id"] == "id_0")
        assert id_0_value == 11.0  # 1.0 + 10.0


# =============================================================================
# Tests for Gauge
# =============================================================================


class TestGauge:
    """Tests for Gauge metric type."""

    def test_initialization(self) -> None:
        """Verify gauge is initialized correctly."""
        gauge = Gauge(
            name="test_gauge",
            description="A test gauge",
            labels=["component"],
        )

        assert gauge.name == "test_gauge"
        assert gauge.description == "A test gauge"
        assert gauge.labels == ["component"]

    def test_set_value(self) -> None:
        """Verify gauge value can be set."""
        gauge = Gauge(name="test_gauge", description="Test")

        gauge.set(42.0)

        collected = gauge.collect()
        assert collected[0]["value"] == 42.0

    def test_set_value_with_labels(self) -> None:
        """Verify gauge value can be set with labels."""
        gauge = Gauge(
            name="test_gauge",
            description="Test",
            labels=["component"],
        )

        gauge.set(10.0, component="cpu")
        gauge.set(20.0, component="memory")

        collected = gauge.collect()
        cpu_value = next(c["value"] for c in collected if c["labels"]["component"] == "cpu")
        mem_value = next(c["value"] for c in collected if c["labels"]["component"] == "memory")

        assert cpu_value == 10.0
        assert mem_value == 20.0

    def test_increment(self) -> None:
        """Verify gauge can be incremented."""
        gauge = Gauge(name="test_gauge", description="Test")

        gauge.set(10.0)
        gauge.inc(5.0)

        collected = gauge.collect()
        assert collected[0]["value"] == 15.0

    def test_decrement(self) -> None:
        """Verify gauge can be decremented."""
        gauge = Gauge(name="test_gauge", description="Test")

        gauge.set(10.0)
        gauge.dec(3.0)

        collected = gauge.collect()
        assert collected[0]["value"] == 7.0

    def test_increment_from_zero(self) -> None:
        """Verify gauge starts at zero when incremented."""
        gauge = Gauge(name="test_gauge", description="Test")

        gauge.inc(5.0)

        collected = gauge.collect()
        assert collected[0]["value"] == 5.0

    def test_decrement_from_zero(self) -> None:
        """Verify gauge can go negative."""
        gauge = Gauge(name="test_gauge", description="Test")

        gauge.dec(3.0)

        collected = gauge.collect()
        assert collected[0]["value"] == -3.0

    def test_collect_format(self) -> None:
        """Verify collect returns correct format."""
        gauge = Gauge(
            name="test_gauge",
            description="Test",
            labels=["component"],
        )
        gauge.set(100.0, component="cpu")

        collected = gauge.collect()

        assert collected[0]["name"] == "test_gauge"
        assert collected[0]["type"] == "gauge"
        assert "labels" in collected[0]
        assert "value" in collected[0]

    def test_cardinality_limit_set(self) -> None:
        """Verify cardinality limit is enforced for set."""
        gauge = Gauge(
            name="test_gauge",
            description="Test",
            labels=["id"],
        )
        gauge._max_cardinality = 5

        for i in range(10):
            gauge.set(float(i), id=f"id_{i}")

        collected = gauge.collect()
        assert len(collected) == 5

    def test_cardinality_limit_inc_dec(self) -> None:
        """Verify cardinality limit is enforced for inc/dec."""
        gauge = Gauge(
            name="test_gauge",
            description="Test",
            labels=["id"],
        )
        gauge._max_cardinality = 3

        gauge.inc(id="id_0")
        gauge.inc(id="id_1")
        gauge.dec(id="id_2")

        # These should be blocked
        gauge.inc(id="id_3")
        gauge.dec(id="id_4")

        collected = gauge.collect()
        assert len(collected) == 3


# =============================================================================
# Tests for Histogram
# =============================================================================


class TestHistogram:
    """Tests for Histogram metric type."""

    def test_initialization(self) -> None:
        """Verify histogram is initialized correctly."""
        histogram = Histogram(
            name="test_histogram",
            description="A test histogram",
            labels=["method"],
            buckets=[0.1, 0.5, 1.0, 5.0],
        )

        assert histogram.name == "test_histogram"
        assert histogram.description == "A test histogram"
        assert histogram.labels == ["method"]
        assert histogram.buckets == [0.1, 0.5, 1.0, 5.0]

    def test_default_buckets(self) -> None:
        """Verify default buckets are set."""
        histogram = Histogram(name="test_histogram", description="Test")

        expected_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        assert histogram.buckets == expected_buckets

    def test_observe_single_value(self) -> None:
        """Verify single observation is recorded."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            buckets=[0.1, 0.5, 1.0],
        )

        histogram.observe(0.25)

        collected = histogram.collect()
        assert len(collected) == 1
        assert collected[0]["count"] == 1
        assert collected[0]["sum"] == 0.25

    def test_observe_multiple_values(self) -> None:
        """Verify multiple observations are recorded."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            buckets=[0.1, 0.5, 1.0],
        )

        histogram.observe(0.05)
        histogram.observe(0.25)
        histogram.observe(0.75)
        histogram.observe(2.0)

        collected = histogram.collect()
        assert collected[0]["count"] == 4
        assert collected[0]["sum"] == 3.05

    def test_bucket_counts(self) -> None:
        """Verify bucket counts are correct."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            buckets=[0.1, 0.5, 1.0],
        )

        histogram.observe(0.05)  # <= 0.1
        histogram.observe(0.25)  # <= 0.5
        histogram.observe(0.75)  # <= 1.0
        histogram.observe(2.0)   # > 1.0 (only in +Inf)

        collected = histogram.collect()
        buckets = collected[0]["buckets"]

        assert buckets[0.1] == 1
        assert buckets[0.5] == 2
        assert buckets[1.0] == 3
        assert buckets[float("inf")] == 4

    def test_observe_with_labels(self) -> None:
        """Verify observations work with labels."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            labels=["method"],
            buckets=[0.1, 0.5, 1.0],
        )

        histogram.observe(0.1, method="GET")
        histogram.observe(0.2, method="GET")
        histogram.observe(0.5, method="POST")

        collected = histogram.collect()
        assert len(collected) == 2

        get_data = next(c for c in collected if c["labels"]["method"] == "GET")
        post_data = next(c for c in collected if c["labels"]["method"] == "POST")

        assert get_data["count"] == 2
        assert post_data["count"] == 1

    def test_collect_format(self) -> None:
        """Verify collect returns correct format."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            labels=["method"],
            buckets=[0.1, 0.5],
        )
        histogram.observe(0.25, method="GET")

        collected = histogram.collect()

        assert collected[0]["name"] == "test_histogram"
        assert collected[0]["type"] == "histogram"
        assert "labels" in collected[0]
        assert "buckets" in collected[0]
        assert "sum" in collected[0]
        assert "count" in collected[0]

    def test_cardinality_limit(self) -> None:
        """Verify cardinality limit is enforced."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            labels=["id"],
            buckets=[0.1, 0.5, 1.0],
        )
        histogram._max_cardinality = 5

        for i in range(10):
            histogram.observe(0.1, id=f"id_{i}")

        collected = histogram.collect()
        assert len(collected) == 5

    def test_bounded_observations(self) -> None:
        """Verify observations are bounded to prevent memory exhaustion."""
        histogram = Histogram(
            name="test_histogram",
            description="Test",
            buckets=[0.1, 0.5, 1.0],
        )
        histogram._max_observations = 100

        # Add more than max observations
        for i in range(200):
            histogram.observe(0.1)

        # Recent observations should be limited
        assert len(histogram._recent_observations.get((), [])) <= 100


# =============================================================================
# Tests for Summary
# =============================================================================


class TestSummary:
    """Tests for Summary metric type."""

    def test_initialization(self) -> None:
        """Verify summary is initialized correctly."""
        summary = Summary(
            name="test_summary",
            description="A test summary",
            labels=["method"],
            quantiles=[0.5, 0.9, 0.99],
        )

        assert summary.name == "test_summary"
        assert summary.description == "A test summary"
        assert summary.labels == ["method"]
        assert summary.quantiles == [0.5, 0.9, 0.99]

    def test_default_quantiles(self) -> None:
        """Verify default quantiles are set."""
        summary = Summary(name="test_summary", description="Test")

        assert summary.quantiles == [0.5, 0.9, 0.99]

    def test_observe_single_value(self) -> None:
        """Verify single observation is recorded."""
        summary = Summary(name="test_summary", description="Test")

        summary.observe(0.25)

        collected = summary.collect()
        assert len(collected) == 1
        assert collected[0]["count"] == 1
        assert collected[0]["sum"] == 0.25

    def test_observe_multiple_values(self) -> None:
        """Verify multiple observations are recorded."""
        summary = Summary(name="test_summary", description="Test")

        summary.observe(0.1)
        summary.observe(0.2)
        summary.observe(0.3)
        summary.observe(0.4)

        collected = summary.collect()
        assert collected[0]["count"] == 4
        assert collected[0]["sum"] == 1.0

    def test_quantile_calculation(self) -> None:
        """Verify quantiles are calculated correctly."""
        summary = Summary(
            name="test_summary",
            description="Test",
            quantiles=[0.5, 0.9],
        )

        # Add values 1-10
        for i in range(1, 11):
            summary.observe(float(i))

        collected = summary.collect()
        quantiles = collected[0]["quantiles"]

        # 50th percentile should be around 5
        assert quantiles[0.5] in [5, 6]
        # 90th percentile should be around 9
        assert quantiles[0.9] in [9, 10]

    def test_observe_with_labels(self) -> None:
        """Verify observations work with labels."""
        summary = Summary(
            name="test_summary",
            description="Test",
            labels=["method"],
        )

        summary.observe(0.1, method="GET")
        summary.observe(0.2, method="GET")
        summary.observe(0.5, method="POST")

        collected = summary.collect()
        assert len(collected) == 2

    def test_collect_format(self) -> None:
        """Verify collect returns correct format."""
        summary = Summary(
            name="test_summary",
            description="Test",
            labels=["method"],
        )
        summary.observe(0.25, method="GET")

        collected = summary.collect()

        assert collected[0]["name"] == "test_summary"
        assert collected[0]["type"] == "summary"
        assert "labels" in collected[0]
        assert "quantiles" in collected[0]
        assert "sum" in collected[0]
        assert "count" in collected[0]

    def test_cardinality_limit(self) -> None:
        """Verify cardinality limit is enforced."""
        summary = Summary(
            name="test_summary",
            description="Test",
            labels=["id"],
        )
        summary._max_cardinality = 5

        for i in range(10):
            summary.observe(0.1, id=f"id_{i}")

        collected = summary.collect()
        assert len(collected) == 5

    def test_bounded_observations(self) -> None:
        """Verify observations are bounded to prevent memory exhaustion."""
        summary = Summary(name="test_summary", description="Test")
        summary._max_observations = 100

        for i in range(200):
            summary.observe(0.1)

        # Observations should be limited
        assert len(summary._observations.get((), [])) <= 100


# =============================================================================
# Tests for MetricsRegistry
# =============================================================================


class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_initialization(self) -> None:
        """Verify registry is initialized correctly."""
        registry = MetricsRegistry(prefix="test")

        assert registry.prefix == "test"
        assert len(registry._metrics) == 0

    def test_default_prefix(self) -> None:
        """Verify default prefix is 'forge'."""
        registry = MetricsRegistry()

        assert registry.prefix == "forge"

    def test_create_counter(self) -> None:
        """Verify counter creation."""
        registry = MetricsRegistry(prefix="test")

        counter = registry.counter(
            "requests_total",
            "Total requests",
            ["method"],
        )

        assert counter.name == "test_requests_total"
        assert isinstance(counter, Counter)

    def test_create_gauge(self) -> None:
        """Verify gauge creation."""
        registry = MetricsRegistry(prefix="test")

        gauge = registry.gauge(
            "active_connections",
            "Active connections",
        )

        assert gauge.name == "test_active_connections"
        assert isinstance(gauge, Gauge)

    def test_create_histogram(self) -> None:
        """Verify histogram creation."""
        registry = MetricsRegistry(prefix="test")

        histogram = registry.histogram(
            "request_duration",
            "Request duration",
            ["method"],
            buckets=[0.1, 0.5, 1.0],
        )

        assert histogram.name == "test_request_duration"
        assert isinstance(histogram, Histogram)
        assert histogram.buckets == [0.1, 0.5, 1.0]

    def test_create_summary(self) -> None:
        """Verify summary creation."""
        registry = MetricsRegistry(prefix="test")

        summary = registry.summary(
            "response_size",
            "Response size",
            quantiles=[0.5, 0.99],
        )

        assert summary.name == "test_response_size"
        assert isinstance(summary, Summary)
        assert summary.quantiles == [0.5, 0.99]

    def test_get_existing_metric(self) -> None:
        """Verify getting existing metric returns same instance."""
        registry = MetricsRegistry(prefix="test")

        counter1 = registry.counter("requests", "Total requests")
        counter2 = registry.counter("requests", "Total requests")

        assert counter1 is counter2

    def test_collect_all(self) -> None:
        """Verify collect_all gathers all metrics."""
        registry = MetricsRegistry(prefix="test")

        counter = registry.counter("requests", "Total requests")
        gauge = registry.gauge("active", "Active")

        counter.inc()
        gauge.set(5.0)

        collected = registry.collect_all()

        assert len(collected) == 2

    def test_to_prometheus_format_counter(self) -> None:
        """Verify Prometheus format for counter."""
        registry = MetricsRegistry(prefix="test")

        counter = registry.counter("requests_total", "Total requests", ["method"])
        counter.inc(method="GET")

        output = registry.to_prometheus_format()

        assert "# HELP test_requests_total Total requests" in output
        assert "# TYPE test_requests_total counter" in output
        assert 'test_requests_total{method="GET"} 1.0' in output

    def test_to_prometheus_format_gauge(self) -> None:
        """Verify Prometheus format for gauge."""
        registry = MetricsRegistry(prefix="test")

        gauge = registry.gauge("active_connections", "Active connections")
        gauge.set(42.0)

        output = registry.to_prometheus_format()

        assert "# HELP test_active_connections Active connections" in output
        assert "# TYPE test_active_connections gauge" in output
        assert "test_active_connections 42.0" in output

    def test_to_prometheus_format_histogram(self) -> None:
        """Verify Prometheus format for histogram."""
        registry = MetricsRegistry(prefix="test")

        histogram = registry.histogram(
            "request_duration",
            "Request duration",
            buckets=[0.1, 0.5],
        )
        histogram.observe(0.25)

        output = registry.to_prometheus_format()

        assert "# HELP test_request_duration Request duration" in output
        assert "# TYPE test_request_duration histogram" in output
        assert "test_request_duration_bucket" in output
        assert "test_request_duration_sum" in output
        assert "test_request_duration_count" in output

    def test_to_prometheus_format_summary(self) -> None:
        """Verify Prometheus format for summary."""
        registry = MetricsRegistry(prefix="test")

        summary = registry.summary(
            "response_size",
            "Response size",
            quantiles=[0.5, 0.9],
        )
        summary.observe(100.0)

        output = registry.to_prometheus_format()

        assert "# HELP test_response_size Response size" in output
        assert "# TYPE test_response_size summary" in output
        assert "test_response_size_sum" in output
        assert "test_response_size_count" in output

    def test_to_prometheus_format_includes_process_start_time(self) -> None:
        """Verify process start time is included."""
        registry = MetricsRegistry(prefix="test")

        output = registry.to_prometheus_format()

        assert "test_process_start_time_seconds" in output

    def test_format_labels_empty(self) -> None:
        """Verify empty labels format correctly."""
        registry = MetricsRegistry()

        result = registry._format_labels({})

        assert result == ""

    def test_format_labels_single(self) -> None:
        """Verify single label formats correctly."""
        registry = MetricsRegistry()

        result = registry._format_labels({"method": "GET"})

        assert result == '{method="GET"}'

    def test_format_labels_multiple(self) -> None:
        """Verify multiple labels format correctly."""
        registry = MetricsRegistry()

        result = registry._format_labels({"method": "GET", "status": "200"})

        assert 'method="GET"' in result
        assert 'status="200"' in result


# =============================================================================
# Tests for track_time decorator
# =============================================================================


class TestTrackTime:
    """Tests for track_time decorator."""

    def test_tracks_sync_function_time(self) -> None:
        """Verify sync function timing is tracked."""
        histogram = Histogram(
            name="test_duration",
            description="Test duration",
            labels=["operation"],
            buckets=[0.01, 0.1, 1.0],
        )

        @track_time(histogram, operation="test")
        def slow_function() -> str:
            time.sleep(0.02)
            return "done"

        result = slow_function()

        assert result == "done"
        collected = histogram.collect()
        assert collected[0]["count"] == 1
        assert collected[0]["sum"] >= 0.02

    @pytest.mark.asyncio
    async def test_tracks_async_function_time(self) -> None:
        """Verify async function timing is tracked."""
        histogram = Histogram(
            name="test_duration",
            description="Test duration",
            labels=["operation"],
            buckets=[0.01, 0.1, 1.0],
        )

        @track_time(histogram, operation="test")
        async def slow_async_function() -> str:
            await asyncio.sleep(0.02)
            return "done"

        result = await slow_async_function()

        assert result == "done"
        collected = histogram.collect()
        assert collected[0]["count"] == 1
        assert collected[0]["sum"] >= 0.02

    def test_tracks_time_on_exception(self) -> None:
        """Verify timing is tracked even when exception occurs."""
        histogram = Histogram(
            name="test_duration",
            description="Test duration",
            buckets=[0.01, 0.1, 1.0],
        )

        @track_time(histogram)
        def failing_function() -> None:
            time.sleep(0.02)
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        collected = histogram.collect()
        assert collected[0]["count"] == 1


# =============================================================================
# Tests for track_in_progress context manager
# =============================================================================


class TestTrackInProgress:
    """Tests for track_in_progress context manager."""

    @pytest.mark.asyncio
    async def test_increments_on_entry(self) -> None:
        """Verify gauge is incremented on entry."""
        gauge = Gauge(
            name="test_in_progress",
            description="Test in progress",
            labels=["operation"],
        )

        async with track_in_progress(gauge, operation="test"):
            collected = gauge.collect()
            assert collected[0]["value"] == 1.0

    @pytest.mark.asyncio
    async def test_decrements_on_exit(self) -> None:
        """Verify gauge is decremented on exit."""
        gauge = Gauge(
            name="test_in_progress",
            description="Test in progress",
            labels=["operation"],
        )

        async with track_in_progress(gauge, operation="test"):
            pass

        collected = gauge.collect()
        assert collected[0]["value"] == 0.0

    @pytest.mark.asyncio
    async def test_decrements_on_exception(self) -> None:
        """Verify gauge is decremented even on exception."""
        gauge = Gauge(
            name="test_in_progress",
            description="Test in progress",
            labels=["operation"],
        )

        with pytest.raises(ValueError):
            async with track_in_progress(gauge, operation="test"):
                raise ValueError("Test error")

        collected = gauge.collect()
        assert collected[0]["value"] == 0.0

    @pytest.mark.asyncio
    async def test_tracks_multiple_concurrent_operations(self) -> None:
        """Verify multiple concurrent operations are tracked."""
        gauge = Gauge(
            name="test_in_progress",
            description="Test in progress",
            labels=["operation"],
        )

        async def operation() -> None:
            async with track_in_progress(gauge, operation="test"):
                await asyncio.sleep(0.05)

        # Start multiple concurrent operations
        tasks = [asyncio.create_task(operation()) for _ in range(3)]

        await asyncio.sleep(0.01)  # Let them start
        collected = gauge.collect()
        assert collected[0]["value"] == 3.0

        await asyncio.gather(*tasks)
        collected = gauge.collect()
        assert collected[0]["value"] == 0.0


# =============================================================================
# Tests for Global Functions
# =============================================================================


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_get_metrics_registry(self) -> None:
        """Verify get_metrics_registry returns global registry."""
        registry = get_metrics_registry()

        assert isinstance(registry, MetricsRegistry)

    def test_reset_metrics(self) -> None:
        """Verify reset_metrics creates new registry."""
        registry1 = get_metrics_registry()
        counter = registry1.counter("test", "Test counter")
        counter.inc()

        reset_metrics()

        registry2 = get_metrics_registry()
        # New registry should have no metrics
        assert len(registry2._metrics) == 0


# =============================================================================
# Tests for FastAPI Integration
# =============================================================================


class TestFastAPIIntegration:
    """Tests for FastAPI integration functions."""

    def test_add_metrics_middleware(self) -> None:
        """Verify metrics middleware can be added."""
        app_mock = MagicMock()

        add_metrics_middleware(app_mock)

        app_mock.add_middleware.assert_called_once()

    def test_create_metrics_endpoint(self) -> None:
        """Verify metrics endpoint can be created."""
        app_mock = MagicMock()

        create_metrics_endpoint(app_mock)

        # Verify decorator was called (get decorator)
        app_mock.get.assert_called_once_with("/metrics", include_in_schema=False)


# =============================================================================
# Tests for Pre-defined Metrics
# =============================================================================


class TestPredefinedMetrics:
    """Tests for pre-defined metrics."""

    def test_http_metrics_exist(self) -> None:
        """Verify HTTP metrics are defined."""
        from forge.monitoring.metrics import (
            http_request_duration_seconds,
            http_requests_in_progress,
            http_requests_total,
        )

        assert http_requests_total is not None
        assert http_request_duration_seconds is not None
        assert http_requests_in_progress is not None

    def test_database_metrics_exist(self) -> None:
        """Verify database metrics are defined."""
        from forge.monitoring.metrics import (
            db_connections_active,
            db_errors_total,
            db_query_duration_seconds,
        )

        assert db_query_duration_seconds is not None
        assert db_connections_active is not None
        assert db_errors_total is not None

    def test_pipeline_metrics_exist(self) -> None:
        """Verify pipeline metrics are defined."""
        from forge.monitoring.metrics import (
            pipeline_duration_seconds,
            pipeline_executions_total,
        )

        assert pipeline_executions_total is not None
        assert pipeline_duration_seconds is not None

    def test_overlay_metrics_exist(self) -> None:
        """Verify overlay metrics are defined."""
        from forge.monitoring.metrics import (
            overlay_errors_total,
            overlay_fuel_consumed,
            overlay_invocations_total,
        )

        assert overlay_invocations_total is not None
        assert overlay_fuel_consumed is not None
        assert overlay_errors_total is not None

    def test_service_metrics_exist(self) -> None:
        """Verify service metrics are defined."""
        from forge.monitoring.metrics import (
            embedding_requests_total,
            llm_requests_total,
            llm_tokens_total,
            search_duration_seconds,
            search_requests_total,
        )

        assert llm_requests_total is not None
        assert llm_tokens_total is not None
        assert embedding_requests_total is not None
        assert search_requests_total is not None
        assert search_duration_seconds is not None

    def test_capsule_metrics_exist(self) -> None:
        """Verify capsule metrics are defined."""
        from forge.monitoring.metrics import capsules_active, capsules_created_total

        assert capsules_created_total is not None
        assert capsules_active is not None

    def test_governance_metrics_exist(self) -> None:
        """Verify governance metrics are defined."""
        from forge.monitoring.metrics import proposals_created_total, votes_cast_total

        assert proposals_created_total is not None
        assert votes_cast_total is not None

    def test_immune_system_metrics_exist(self) -> None:
        """Verify immune system metrics are defined."""
        from forge.monitoring.metrics import (
            canary_traffic_percent,
            circuit_breaker_state,
            health_check_status,
        )

        assert circuit_breaker_state is not None
        assert health_check_status is not None
        assert canary_traffic_percent is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestMetricsIntegration:
    """Integration tests for the metrics module."""

    def test_full_metrics_pipeline(self) -> None:
        """Test complete metrics collection and export pipeline."""
        registry = MetricsRegistry(prefix="integration")

        # Create various metrics
        counter = registry.counter("requests", "Total requests", ["method"])
        gauge = registry.gauge("active", "Active connections")
        histogram = registry.histogram("duration", "Duration", buckets=[0.1, 0.5, 1.0])
        summary = registry.summary("size", "Response size")

        # Record some data
        counter.inc(method="GET")
        counter.inc(method="GET")
        counter.inc(method="POST")
        gauge.set(10.0)
        histogram.observe(0.25)
        histogram.observe(0.75)
        summary.observe(100.0)
        summary.observe(200.0)

        # Collect all
        collected = registry.collect_all()
        assert len(collected) >= 4

        # Export to Prometheus format
        output = registry.to_prometheus_format()
        assert "integration_requests" in output
        assert "integration_active" in output
        assert "integration_duration" in output
        assert "integration_size" in output

    def test_metrics_with_high_cardinality_protection(self) -> None:
        """Test metrics properly handle high cardinality."""
        registry = MetricsRegistry(prefix="test")

        counter = registry.counter("requests", "Total requests", ["user_id"])
        # Manually set low cardinality limit for testing
        counter._max_cardinality = 10

        # Try to add many unique label combinations
        for i in range(100):
            counter.inc(user_id=f"user_{i}")

        collected = counter.collect()
        # Should be limited to max cardinality
        assert len(collected) <= 10

    def test_concurrent_metric_updates(self) -> None:
        """Test metrics handle concurrent updates correctly."""
        registry = MetricsRegistry(prefix="test")
        counter = registry.counter("requests", "Total requests")

        # Simulate concurrent increments
        import threading

        def increment() -> None:
            for _ in range(100):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        collected = counter.collect()
        assert collected[0]["value"] == 1000.0
