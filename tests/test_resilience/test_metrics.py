"""
Tests for Metrics Collection
============================

Tests for forge/resilience/observability/metrics.py
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.observability.metrics import (
    ForgeMetrics,
    MetricType,
    MetricValue,
    NoOpCounter,
    NoOpGauge,
    NoOpHistogram,
    NoOpMeter,
    get_metrics,
    timed,
)


class TestMetricType:
    """Tests for MetricType enum."""

    def test_capsule_metrics(self):
        """Test capsule-related metric types."""
        assert MetricType.CAPSULE_CREATED.value == "capsule_created_total"
        assert MetricType.CAPSULE_UPDATED.value == "capsule_updated_total"
        assert MetricType.CAPSULE_DELETED.value == "capsule_deleted_total"
        assert MetricType.CAPSULE_SEARCH_LATENCY.value == "capsule_search_latency_seconds"

    def test_cache_metrics(self):
        """Test cache-related metric types."""
        assert MetricType.CACHE_HIT.value == "cache_hit_total"
        assert MetricType.CACHE_MISS.value == "cache_miss_total"
        assert MetricType.CACHE_INVALIDATION.value == "cache_invalidation_total"

    def test_system_metrics(self):
        """Test system-related metric types."""
        assert MetricType.DB_QUERY_LATENCY.value == "db_query_latency_seconds"
        assert MetricType.REQUEST_LATENCY.value == "http_request_latency_seconds"
        assert MetricType.ERROR_COUNT.value == "error_total"


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_metric_value_creation(self):
        """Test creating a metric value."""
        value = MetricValue(
            name="test_metric",
            value=42.5,
            labels={"type": "test"},
        )

        assert value.name == "test_metric"
        assert value.value == 42.5
        assert value.labels == {"type": "test"}
        assert value.timestamp is not None


class TestNoOpClasses:
    """Tests for No-Op metric classes."""

    def test_noop_counter(self):
        """Test NoOpCounter does nothing."""
        counter = NoOpCounter()

        # Should not raise
        counter.add(1)
        counter.add(5, attributes={"key": "value"})

    def test_noop_histogram(self):
        """Test NoOpHistogram does nothing."""
        histogram = NoOpHistogram()

        # Should not raise
        histogram.record(1.5)
        histogram.record(2.5, attributes={"key": "value"})

    def test_noop_gauge(self):
        """Test NoOpGauge does nothing."""
        gauge = NoOpGauge()

        # Should not raise
        gauge.set(100)
        gauge.set(200, attributes={"key": "value"})

    def test_noop_meter(self):
        """Test NoOpMeter creates noop instruments."""
        meter = NoOpMeter()

        counter = meter.create_counter("test_counter")
        histogram = meter.create_histogram("test_histogram")
        up_down_counter = meter.create_up_down_counter("test_up_down")

        assert isinstance(counter, NoOpCounter)
        assert isinstance(histogram, NoOpHistogram)
        assert isinstance(up_down_counter, NoOpCounter)


class TestForgeMetrics:
    """Tests for ForgeMetrics class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.enable_metrics = True
        config.otlp_endpoint = None
        config.service_name = "test-service"
        config.version = "1.0.0"
        config.environment = "test"
        return config

    @pytest.fixture
    def metrics(self, mock_config):
        """Create a ForgeMetrics instance."""
        with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            return ForgeMetrics()

    def test_metrics_creation(self, metrics):
        """Test metrics creation."""
        assert metrics._initialized is False
        assert metrics._meter is None

    def test_initialize_disabled(self, mock_config):
        """Test initialization when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            metrics = ForgeMetrics()
            metrics.initialize()

            assert metrics._initialized is True
            assert isinstance(metrics._meter, NoOpMeter)

    def test_initialize_no_otel(self, mock_config):
        """Test initialization without OpenTelemetry."""
        with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
            mock.return_value.observability = mock_config
            with patch(
                "forge.resilience.observability.metrics.OTEL_METRICS_AVAILABLE", False
            ):
                metrics = ForgeMetrics()
                metrics.initialize()

                assert metrics._initialized is True
                assert isinstance(metrics._meter, NoOpMeter)

    def test_increment(self, metrics):
        """Test incrementing a counter."""
        metrics.initialize()

        metrics.increment("test_counter", value=5)

        assert "test_counter" in metrics._local_counters
        assert metrics._local_counters["test_counter"] == 5

    def test_increment_with_labels(self, metrics):
        """Test incrementing with labels."""
        metrics.initialize()

        metrics.increment("test_counter", value=1, labels={"type": "test"})

        key = "test_counter:{'type': 'test'}"
        assert key in metrics._local_counters

    def test_record_latency(self, metrics):
        """Test recording latency."""
        metrics.initialize()

        metrics.record_latency("test_latency", 0.5)
        metrics.record_latency("test_latency", 1.0)

        assert "test_latency" in metrics._local_histograms
        assert len(metrics._local_histograms["test_latency"]) == 2
        assert metrics._local_histograms["test_latency"] == [0.5, 1.0]

    def test_capsule_created(self, metrics):
        """Test capsule created metric."""
        metrics.initialize()

        metrics.capsule_created("KNOWLEDGE")

        key = "capsules_created:{'type': 'KNOWLEDGE'}"
        assert key in metrics._local_counters

    def test_capsule_updated(self, metrics):
        """Test capsule updated metric."""
        metrics.initialize()

        metrics.capsule_updated("DECISION")

        key = "capsules_updated:{'type': 'DECISION'}"
        assert key in metrics._local_counters

    def test_capsule_deleted(self, metrics):
        """Test capsule deleted metric."""
        metrics.initialize()

        metrics.capsule_deleted("MEMORY")

        key = "capsules_deleted:{'type': 'MEMORY'}"
        assert key in metrics._local_counters

    def test_cache_hit(self, metrics):
        """Test cache hit metric."""
        metrics.initialize()

        metrics.cache_hit("query")

        key = "cache_hits:{'type': 'query'}"
        assert key in metrics._local_counters

    def test_cache_miss(self, metrics):
        """Test cache miss metric."""
        metrics.initialize()

        metrics.cache_miss("lineage")

        key = "cache_misses:{'type': 'lineage'}"
        assert key in metrics._local_counters

    def test_proposal_created(self, metrics):
        """Test proposal created metric."""
        metrics.initialize()

        metrics.proposal_created("STANDARD")

        key = "proposals_created:{'type': 'STANDARD'}"
        assert key in metrics._local_counters

    def test_vote_cast(self, metrics):
        """Test vote cast metric."""
        metrics.initialize()

        metrics.vote_cast("approve")

        key = "votes_cast:{'choice': 'approve'}"
        assert key in metrics._local_counters

    def test_login_attempt(self, metrics):
        """Test login attempt metric."""
        metrics.initialize()

        metrics.login_attempt(success=True)
        metrics.login_attempt(success=False)

        assert "logins:{'success': 'true'}" in metrics._local_counters
        assert "logins:{'success': 'false'}" in metrics._local_counters

    def test_error(self, metrics):
        """Test error metric."""
        metrics.initialize()

        metrics.error("validation_error", "/api/capsules")

        key = "errors:{'type': 'validation_error', 'endpoint': '/api/capsules'}"
        assert key in metrics._local_counters

    def test_request_latency(self, metrics):
        """Test request latency metric."""
        metrics.initialize()

        metrics.request_latency(0.5, "GET", "/api/capsules", 200)

        key = "request_latency:{'method': 'GET', 'endpoint': '/api/capsules', 'status': '200'}"
        assert key in metrics._local_histograms

    def test_db_query_latency(self, metrics):
        """Test database query latency metric."""
        metrics.initialize()

        metrics.db_query_latency(0.1, "read", success=True)

        key = "db_query_latency:{'operation': 'read', 'success': 'true'}"
        assert key in metrics._local_histograms

    def test_search_latency(self, metrics):
        """Test search latency metric."""
        metrics.initialize()

        metrics.search_latency(0.2, result_count=25)

        key = "search_latency:{'result_count': '25'}"
        assert key in metrics._local_histograms

    def test_pipeline_latency(self, metrics):
        """Test pipeline latency metric."""
        metrics.initialize()

        metrics.pipeline_latency(1.5, phase="extraction")

        key = "pipeline_latency:{'phase': 'extraction'}"
        assert key in metrics._local_histograms

    def test_lineage_query_latency(self, metrics):
        """Test lineage query latency metric."""
        metrics.initialize()

        metrics.lineage_query_latency(0.3, depth=5)

        key = "lineage_query_latency:{'depth': '5'}"
        assert key in metrics._local_histograms

    def test_get_local_stats(self, metrics):
        """Test getting local stats."""
        metrics.initialize()

        metrics.increment("test_counter", value=10)
        metrics.record_latency("test_latency", 0.5)
        metrics.record_latency("test_latency", 1.5)

        stats = metrics.get_local_stats()

        assert "counters" in stats
        assert "histograms" in stats
        assert stats["histograms"]["test_latency"]["count"] == 2
        assert stats["histograms"]["test_latency"]["sum"] == 2.0
        assert stats["histograms"]["test_latency"]["avg"] == 1.0
        assert stats["histograms"]["test_latency"]["min"] == 0.5
        assert stats["histograms"]["test_latency"]["max"] == 1.5

    def test_histogram_bounded_growth(self, metrics):
        """Test histogram values are bounded."""
        metrics.initialize()

        # Record many values
        for i in range(2000):
            metrics.record_latency("bounded_test", float(i))

        # Should be bounded to MAX_HISTOGRAM_VALUES_PER_KEY
        assert len(metrics._local_histograms["bounded_test"]) <= metrics.MAX_HISTOGRAM_VALUES_PER_KEY


class TestTimedDecorator:
    """Tests for the timed decorator."""

    def test_timed_sync_function(self):
        """Test timed decorator on sync function."""
        with patch("forge.resilience.observability.metrics._forge_metrics", None):
            with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_metrics = True
                mock_config.observability.otlp_endpoint = None
                mock.return_value = mock_config

                @timed("test_operation")
                def sync_function():
                    return "result"

                result = sync_function()

                assert result == "result"

    @pytest.mark.asyncio
    async def test_timed_async_function(self):
        """Test timed decorator on async function."""
        with patch("forge.resilience.observability.metrics._forge_metrics", None):
            with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_metrics = True
                mock_config.observability.otlp_endpoint = None
                mock.return_value = mock_config

                @timed("test_async_operation")
                async def async_function():
                    await asyncio.sleep(0.01)
                    return "async_result"

                result = await async_function()

                assert result == "async_result"


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_metrics(self):
        """Test getting global metrics instance."""
        with patch("forge.resilience.observability.metrics._forge_metrics", None):
            with patch("forge.resilience.observability.metrics.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.observability.enabled = True
                mock_config.observability.enable_metrics = False
                mock.return_value = mock_config

                metrics = get_metrics()

                assert isinstance(metrics, ForgeMetrics)
                assert metrics._initialized is True
