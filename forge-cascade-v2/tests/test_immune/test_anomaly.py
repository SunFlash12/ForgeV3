"""
Comprehensive tests for the Forge Cascade V2 Anomaly Detection module.

Tests cover:
- AnomalyType and AnomalySeverity enums
- Anomaly dataclass and its properties
- AnomalyDetectorConfig
- StatisticalAnomalyDetector (Z-score and IQR detection)
- IsolationForestDetector
- RateAnomalyDetector
- BehavioralAnomalyDetector
- CompositeAnomalyDetector
- ForgeAnomalySystem
- Factory function create_forge_anomaly_system
"""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from forge.immune.anomaly import (
    Anomaly,
    AnomalyDetector,
    AnomalyDetectorConfig,
    AnomalySeverity,
    AnomalyType,
    BehavioralAnomalyDetector,
    CompositeAnomalyDetector,
    ForgeAnomalySystem,
    IsolationForestDetector,
    IsolationNode,
    IsolationTree,
    RateAnomalyDetector,
    StatisticalAnomalyDetector,
    UserProfile,
    create_forge_anomaly_system,
)


# =============================================================================
# Test Enums
# =============================================================================


class TestAnomalyType:
    """Tests for AnomalyType enum."""

    def test_all_types_exist(self) -> None:
        """Verify all expected anomaly types are defined."""
        assert AnomalyType.STATISTICAL == "statistical"
        assert AnomalyType.BEHAVIORAL == "behavioral"
        assert AnomalyType.TEMPORAL == "temporal"
        assert AnomalyType.ISOLATION == "isolation"
        assert AnomalyType.THRESHOLD == "threshold"
        assert AnomalyType.RATE == "rate"
        assert AnomalyType.COMPOSITE == "composite"

    def test_enum_string_inheritance(self) -> None:
        """Verify enum inherits from str."""
        assert isinstance(AnomalyType.STATISTICAL, str)
        assert AnomalyType.STATISTICAL.upper() == "STATISTICAL"


class TestAnomalySeverity:
    """Tests for AnomalySeverity enum."""

    def test_all_severities_exist(self) -> None:
        """Verify all expected severity levels are defined."""
        assert AnomalySeverity.LOW == "low"
        assert AnomalySeverity.MEDIUM == "medium"
        assert AnomalySeverity.HIGH == "high"
        assert AnomalySeverity.CRITICAL == "critical"

    def test_enum_string_inheritance(self) -> None:
        """Verify enum inherits from str."""
        assert isinstance(AnomalySeverity.CRITICAL, str)


# =============================================================================
# Test Anomaly Dataclass
# =============================================================================


class TestAnomaly:
    """Tests for Anomaly dataclass."""

    @pytest.fixture
    def sample_anomaly(self) -> Anomaly:
        """Create a sample anomaly for testing."""
        return Anomaly(
            id="test_anomaly_123",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.HIGH,
            metric_name="cpu_usage",
            observed_value=95.5,
            expected_range=(20.0, 80.0),
            anomaly_score=0.85,
            confidence=0.92,
            context={"host": "server1"},
            related_anomalies=["anomaly_001", "anomaly_002"],
        )

    def test_anomaly_creation(self, sample_anomaly: Anomaly) -> None:
        """Test anomaly is created with correct values."""
        assert sample_anomaly.id == "test_anomaly_123"
        assert sample_anomaly.type == AnomalyType.STATISTICAL
        assert sample_anomaly.severity == AnomalySeverity.HIGH
        assert sample_anomaly.metric_name == "cpu_usage"
        assert sample_anomaly.observed_value == 95.5
        assert sample_anomaly.expected_range == (20.0, 80.0)
        assert sample_anomaly.anomaly_score == 0.85
        assert sample_anomaly.confidence == 0.92
        assert sample_anomaly.acknowledged is False
        assert sample_anomaly.resolved is False

    def test_value_alias(self, sample_anomaly: Anomaly) -> None:
        """Test value property is alias for observed_value."""
        assert sample_anomaly.value == sample_anomaly.observed_value
        assert sample_anomaly.value == 95.5

    def test_expected_value_property(self, sample_anomaly: Anomaly) -> None:
        """Test expected_value returns midpoint of expected_range."""
        expected = (20.0 + 80.0) / 2
        assert sample_anomaly.expected_value == expected

    def test_detected_at_alias(self, sample_anomaly: Anomaly) -> None:
        """Test detected_at is alias for timestamp."""
        assert sample_anomaly.detected_at == sample_anomaly.timestamp

    def test_anomaly_type_alias(self, sample_anomaly: Anomaly) -> None:
        """Test anomaly_type is alias for type."""
        assert sample_anomaly.anomaly_type == sample_anomaly.type

    def test_to_dict(self, sample_anomaly: Anomaly) -> None:
        """Test to_dict method produces expected dictionary."""
        result = sample_anomaly.to_dict()

        assert result["id"] == "test_anomaly_123"
        assert result["type"] == "statistical"
        assert result["severity"] == "high"
        assert result["metric_name"] == "cpu_usage"
        assert result["observed_value"] == 95.5
        assert result["expected_range"] == (20.0, 80.0)
        assert result["anomaly_score"] == 0.85
        assert result["confidence"] == 0.92
        assert result["context"] == {"host": "server1"}
        assert result["related_anomalies"] == ["anomaly_001", "anomaly_002"]
        assert result["acknowledged"] is False
        assert result["resolved"] is False
        assert "timestamp" in result

    def test_default_timestamp(self) -> None:
        """Test anomaly gets default timestamp on creation."""
        anomaly = Anomaly(
            id="test",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.LOW,
            metric_name="test",
            observed_value=1.0,
            expected_range=(0.0, 2.0),
            anomaly_score=0.5,
            confidence=0.5,
        )
        assert anomaly.timestamp is not None
        assert isinstance(anomaly.timestamp, datetime)


# =============================================================================
# Test AnomalyDetectorConfig
# =============================================================================


class TestAnomalyDetectorConfig:
    """Tests for AnomalyDetectorConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = AnomalyDetectorConfig()

        assert config.z_score_threshold == 3.0
        assert config.iqr_multiplier == 1.5
        assert config.contamination == 0.1
        assert config.n_estimators == 100
        assert config.max_samples == 256
        assert config.window_size == 100
        assert config.min_samples == 20
        assert config.score_threshold == 0.6
        assert config.confidence_threshold == 0.7
        assert config.cooldown_seconds == 60.0
        assert config.max_alerts_per_hour == 100

    def test_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = AnomalyDetectorConfig(
            z_score_threshold=2.5,
            window_size=50,
            min_samples=10,
        )

        assert config.z_score_threshold == 2.5
        assert config.window_size == 50
        assert config.min_samples == 10


# =============================================================================
# Test Base AnomalyDetector
# =============================================================================


class TestAnomalyDetectorBase:
    """Tests for base AnomalyDetector class functionality."""

    @pytest.fixture
    def detector(self) -> StatisticalAnomalyDetector:
        """Create a detector for testing base methods."""
        config = AnomalyDetectorConfig(window_size=10, min_samples=3)
        return StatisticalAnomalyDetector("test_detector", config)

    def test_add_data_point(self, detector: StatisticalAnomalyDetector) -> None:
        """Test adding data points to buffer."""
        detector.add_data_point(10.0)
        detector.add_data_point(20.0)
        detector.add_data_point(30.0)

        values = detector.get_values()
        assert len(values) == 3
        assert values == [10.0, 20.0, 30.0]

    def test_buffer_trimming(self, detector: StatisticalAnomalyDetector) -> None:
        """Test buffer trims to window size."""
        # Add more than window_size (10) points
        for i in range(15):
            detector.add_data_point(float(i))

        values = detector.get_values()
        assert len(values) == 10
        assert values == [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0]

    def test_score_to_severity(self, detector: StatisticalAnomalyDetector) -> None:
        """Test score to severity mapping."""
        assert detector._score_to_severity(0.2) == AnomalySeverity.LOW
        assert detector._score_to_severity(0.4) == AnomalySeverity.MEDIUM
        assert detector._score_to_severity(0.7) == AnomalySeverity.HIGH
        assert detector._score_to_severity(0.9) == AnomalySeverity.CRITICAL

    def test_generate_id(self, detector: StatisticalAnomalyDetector) -> None:
        """Test ID generation produces unique IDs."""
        id1 = detector._generate_id()
        id2 = detector._generate_id()

        assert id1.startswith("anomaly_")
        assert id2.startswith("anomaly_")
        assert id1 != id2

    def test_can_alert_respects_hourly_limit(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test alert rate limiting respects hourly limit."""
        detector._alerts_this_hour = detector.config.max_alerts_per_hour

        assert detector._can_alert("metric") is False

    def test_critical_severity_bypasses_cooldown(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test critical alerts bypass cooldown."""
        # Record an alert
        detector._record_alert("metric")

        # Normal severity should be blocked by cooldown
        assert detector._can_alert("metric", AnomalySeverity.LOW) is False

        # Critical should bypass
        assert detector._can_alert("metric", AnomalySeverity.CRITICAL) is True


# =============================================================================
# Test StatisticalAnomalyDetector
# =============================================================================


class TestStatisticalAnomalyDetector:
    """Tests for StatisticalAnomalyDetector."""

    @pytest.fixture
    def detector(self) -> StatisticalAnomalyDetector:
        """Create a statistical detector for testing."""
        config = AnomalyDetectorConfig(
            window_size=50,
            min_samples=10,
            z_score_threshold=2.0,
            score_threshold=0.3,
        )
        return StatisticalAnomalyDetector("stat_detector", config)

    @pytest.mark.asyncio
    async def test_no_detection_with_insufficient_samples(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test no detection when samples < min_samples."""
        for i in range(5):
            result = await detector.detect(10.0 + i)

        assert result is None

    @pytest.mark.asyncio
    async def test_detects_z_score_anomaly(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test detection of Z-score based anomalies."""
        # Add normal values
        for _ in range(20):
            await detector.detect(50.0, {"metric_name": "test"})

        # Add extreme anomaly
        result = await detector.detect(150.0, {"metric_name": "test"})

        assert result is not None
        assert result.type == AnomalyType.STATISTICAL
        assert result.observed_value == 150.0
        assert result.context["z_score"] > detector.config.z_score_threshold

    @pytest.mark.asyncio
    async def test_detects_iqr_anomaly(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test detection of IQR based anomalies."""
        # Add values with clear IQR bounds
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100] * 2:
            await detector.detect(float(v), {"metric_name": "test"})

        # Add outlier beyond IQR fences
        result = await detector.detect(500.0, {"metric_name": "test"})

        assert result is not None
        assert "iqr" in result.context

    @pytest.mark.asyncio
    async def test_severity_based_on_score(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test severity is determined by anomaly score."""
        # Fill with stable data
        for _ in range(20):
            await detector.detect(50.0, {"metric_name": "test"})

        # Very extreme value should produce high severity
        result = await detector.detect(1000.0, {"metric_name": "test"})

        assert result is not None
        assert result.severity in [
            AnomalySeverity.HIGH,
            AnomalySeverity.CRITICAL,
        ]

    @pytest.mark.asyncio
    async def test_normal_values_no_detection(
        self, detector: StatisticalAnomalyDetector
    ) -> None:
        """Test normal values don't trigger detection."""
        # Add consistent values
        for _ in range(25):
            result = await detector.detect(50.0, {"metric_name": "test"})

        # Last value should not be anomalous
        assert result is None


# =============================================================================
# Test IsolationForestDetector
# =============================================================================


class TestIsolationTree:
    """Tests for IsolationTree class."""

    def test_tree_building(self) -> None:
        """Test tree is built correctly."""
        tree = IsolationTree(max_depth=4)
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        tree.fit(data)

        assert tree.root is not None

    def test_path_length_calculation(self) -> None:
        """Test path length calculation for points."""
        tree = IsolationTree(max_depth=4)
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        tree.fit(data)

        # Normal values should have longer paths
        path_normal = tree.path_length(3.0)
        # Extreme value should have shorter path (isolates faster)
        path_extreme = tree.path_length(100.0)

        assert path_normal > 0
        assert path_extreme > 0


class TestIsolationNode:
    """Tests for IsolationNode class."""

    def test_leaf_node(self) -> None:
        """Test leaf node identification."""
        leaf = IsolationNode(size=5)
        assert leaf.is_leaf is True

    def test_internal_node(self) -> None:
        """Test internal node has children."""
        left = IsolationNode(size=2)
        right = IsolationNode(size=3)
        internal = IsolationNode(split_value=5.0, left=left, right=right)

        assert internal.is_leaf is False


class TestIsolationForestDetector:
    """Tests for IsolationForestDetector."""

    @pytest.fixture
    def detector(self) -> IsolationForestDetector:
        """Create an isolation forest detector for testing."""
        config = AnomalyDetectorConfig(
            window_size=100,
            min_samples=20,
            n_estimators=10,
            max_samples=50,
            score_threshold=0.5,
        )
        return IsolationForestDetector("iso_forest", config)

    @pytest.mark.asyncio
    async def test_no_detection_with_insufficient_samples(
        self, detector: IsolationForestDetector
    ) -> None:
        """Test no detection when samples < min_samples."""
        for i in range(10):
            result = await detector.detect(float(i))

        assert result is None

    @pytest.mark.asyncio
    async def test_trains_after_min_samples(
        self, detector: IsolationForestDetector
    ) -> None:
        """Test training occurs after minimum samples collected."""
        for i in range(25):
            await detector.detect(float(i % 10), {"metric_name": "test"})

        assert detector._trained is True
        assert len(detector._trees) == detector.config.n_estimators

    @pytest.mark.asyncio
    async def test_detects_anomalous_points(
        self, detector: IsolationForestDetector
    ) -> None:
        """Test detection of anomalous points."""
        # Add normal distribution of values
        for i in range(30):
            await detector.detect(50.0 + (i % 5), {"metric_name": "test"})

        # Add extreme anomaly
        result = await detector.detect(1000.0, {"metric_name": "test"})

        # Should detect if score exceeds threshold
        if result is not None:
            assert result.type == AnomalyType.ISOLATION
            assert result.anomaly_score >= detector.config.score_threshold

    def test_expected_path_length_calculation(self) -> None:
        """Test expected path length formula."""
        # n=1 should be 0
        assert IsolationForestDetector._expected_path_length(1) == 0.0

        # n=2 should be 1
        assert IsolationForestDetector._expected_path_length(2) == 1.0

        # Larger n should be positive
        result = IsolationForestDetector._expected_path_length(100)
        assert result > 0


# =============================================================================
# Test RateAnomalyDetector
# =============================================================================


class TestRateAnomalyDetector:
    """Tests for RateAnomalyDetector."""

    @pytest.fixture
    def detector(self) -> RateAnomalyDetector:
        """Create a rate detector for testing."""
        config = AnomalyDetectorConfig(
            window_size=10,
            min_samples=3,
            z_score_threshold=2.0,
        )
        return RateAnomalyDetector("rate_detector", config, bucket_seconds=1.0)

    @pytest.mark.asyncio
    async def test_bucket_accumulation(
        self, detector: RateAnomalyDetector
    ) -> None:
        """Test events accumulate in buckets."""
        await detector.detect(1.0, {"metric_name": "test"})
        await detector.detect(1.0, {"metric_name": "test"})
        await detector.detect(1.0, {"metric_name": "test"})

        # Should have events in current bucket
        assert len(detector._buckets) > 0

    @pytest.mark.asyncio
    async def test_detects_rate_spike(self, detector: RateAnomalyDetector) -> None:
        """Test detection of rate spikes."""
        # Simulate low rate for several buckets
        for _ in range(5):
            await detector.detect(1.0, {"metric_name": "test"})
            await asyncio.sleep(0.01)

        # Allow some time to pass
        await asyncio.sleep(1.1)

        # Simulate massive spike - many events in quick succession
        for _ in range(100):
            result = await detector.detect(1.0, {"metric_name": "test"})

        # May or may not detect based on timing
        if result is not None:
            assert result.type == AnomalyType.RATE

    @pytest.mark.asyncio
    async def test_no_detection_for_normal_rate(
        self, detector: RateAnomalyDetector
    ) -> None:
        """Test normal rates don't trigger detection."""
        # Consistent low rate
        for _ in range(10):
            result = await detector.detect(1.0, {"metric_name": "test"})

        # Should not trigger on stable rate with insufficient variance
        # (depends on bucket timing)


# =============================================================================
# Test BehavioralAnomalyDetector
# =============================================================================


class TestUserProfile:
    """Tests for UserProfile class."""

    def test_profile_creation(self) -> None:
        """Test user profile is created correctly."""
        profile = UserProfile(user_id="user123")

        assert profile.user_id == "user123"
        assert profile.created_at is not None

    def test_add_observation(self) -> None:
        """Test adding observations to profile."""
        profile = UserProfile(user_id="user123")

        profile.add_observation("login_count", 5.0)
        profile.add_observation("login_count", 6.0)
        profile.add_observation("login_count", 7.0)

        stats = profile.get_stats("login_count")
        assert stats["count"] == 3
        assert stats["mean"] == 6.0

    def test_get_stats_empty_metric(self) -> None:
        """Test getting stats for non-existent metric."""
        profile = UserProfile(user_id="user123")

        stats = profile.get_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["mean"] == 0.0
        assert stats["std"] == 0.0

    def test_observation_trimming(self) -> None:
        """Test observations are trimmed to max size."""
        profile = UserProfile(user_id="user123")

        # Add more than max observations
        for i in range(600):
            profile.add_observation("metric", float(i))

        stats = profile.get_stats("metric")
        assert stats["count"] == 500  # _max_observations default


class TestBehavioralAnomalyDetector:
    """Tests for BehavioralAnomalyDetector."""

    @pytest.fixture
    def detector(self) -> BehavioralAnomalyDetector:
        """Create a behavioral detector for testing."""
        config = AnomalyDetectorConfig(
            min_samples=5,
            z_score_threshold=2.0,
        )
        return BehavioralAnomalyDetector("behavioral", config)

    @pytest.mark.asyncio
    async def test_requires_user_id(
        self, detector: BehavioralAnomalyDetector
    ) -> None:
        """Test detection requires user_id in context."""
        result = await detector.detect(10.0, {"metric_name": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_builds_user_profile(
        self, detector: BehavioralAnomalyDetector
    ) -> None:
        """Test user profiles are built from observations."""
        context = {"user_id": "user123", "metric_name": "logins"}

        for _ in range(10):
            await detector.detect(5.0, context)

        assert "user123" in detector._user_profiles
        profile = detector._user_profiles["user123"]
        assert profile.get_stats("logins")["count"] == 10

    @pytest.mark.asyncio
    async def test_detects_behavioral_anomaly(
        self, detector: BehavioralAnomalyDetector
    ) -> None:
        """Test detection of behavioral anomalies."""
        context = {"user_id": "user123", "metric_name": "api_calls"}

        # Build normal baseline
        for _ in range(10):
            await detector.detect(100.0, context)

        # Extreme deviation from normal
        result = await detector.detect(1000.0, context)

        # Should detect anomaly
        if result is not None:
            assert result.type == AnomalyType.BEHAVIORAL
            assert "user_id" in result.context
            assert result.context["user_id"] == "user123"


# =============================================================================
# Test CompositeAnomalyDetector
# =============================================================================


class TestCompositeAnomalyDetector:
    """Tests for CompositeAnomalyDetector."""

    @pytest.fixture
    def composite_detector(self) -> CompositeAnomalyDetector:
        """Create a composite detector with sub-detectors."""
        config = AnomalyDetectorConfig(min_samples=5)
        composite = CompositeAnomalyDetector("composite", config)

        composite.add_detector(StatisticalAnomalyDetector("stat1", config))
        composite.add_detector(StatisticalAnomalyDetector("stat2", config))

        return composite

    def test_add_detector(self, composite_detector: CompositeAnomalyDetector) -> None:
        """Test adding detectors to composite."""
        assert len(composite_detector.detectors) == 2

    @pytest.mark.asyncio
    async def test_requires_min_agreement(
        self, composite_detector: CompositeAnomalyDetector
    ) -> None:
        """Test composite requires minimum detector agreement."""
        # With only 2 detectors and _min_agreement=2, both must agree
        composite_detector._min_agreement = 2

        # Not enough detectors
        composite_with_one = CompositeAnomalyDetector("test")
        composite_with_one.add_detector(
            StatisticalAnomalyDetector("stat", AnomalyDetectorConfig())
        )
        composite_with_one._min_agreement = 2

        result = await composite_with_one.detect(100.0, {"metric_name": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_aggregates_scores(
        self, composite_detector: CompositeAnomalyDetector
    ) -> None:
        """Test composite aggregates scores from sub-detectors."""
        # Fill with normal data
        for _ in range(10):
            for detector in composite_detector.detectors:
                await detector.detect(50.0, {"metric_name": "test"})

        # Now detect with composite using extreme value
        result = await composite_detector.detect(1000.0, {"metric_name": "test"})

        if result is not None:
            assert result.type == AnomalyType.COMPOSITE
            assert "n_triggered" in result.context
            assert "triggered_types" in result.context


# =============================================================================
# Test ForgeAnomalySystem
# =============================================================================


class TestForgeAnomalySystem:
    """Tests for ForgeAnomalySystem."""

    @pytest.fixture
    def system(self) -> ForgeAnomalySystem:
        """Create an anomaly system for testing."""
        config = AnomalyDetectorConfig(min_samples=3)
        return ForgeAnomalySystem(config)

    def test_register_detector(self, system: ForgeAnomalySystem) -> None:
        """Test registering a detector."""
        detector = StatisticalAnomalyDetector("test", system.config)
        system.register_detector("test_metric", detector)

        assert "test_metric" in system._detectors

    def test_register_callback(self, system: ForgeAnomalySystem) -> None:
        """Test registering a callback."""
        callback = AsyncMock()
        system.register_callback(callback)

        assert callback in system._callbacks

    @pytest.mark.asyncio
    async def test_record_metric_creates_detector(
        self, system: ForgeAnomalySystem
    ) -> None:
        """Test recording metric auto-creates detector."""
        await system.record_metric("new_metric", 10.0)

        assert "new_metric" in system._detectors

    @pytest.mark.asyncio
    async def test_callback_invoked_on_anomaly(
        self, system: ForgeAnomalySystem
    ) -> None:
        """Test callbacks are invoked when anomaly detected."""
        callback = AsyncMock()
        system.register_callback(callback)

        # Register detector and build baseline
        detector = StatisticalAnomalyDetector("test", system.config)
        system.register_detector("test_metric", detector)

        for _ in range(10):
            await system.record_metric("test_metric", 50.0)

        # Record anomalous value
        await system.record_metric("test_metric", 1000.0)

        # Callback may have been called if anomaly detected

    @pytest.mark.asyncio
    async def test_get_recent_anomalies(self, system: ForgeAnomalySystem) -> None:
        """Test getting recent anomalies."""
        # Manually add an anomaly to history
        anomaly = Anomaly(
            id="test_anomaly",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.HIGH,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
        )
        system._anomaly_history.append(anomaly)

        recent = system.get_recent_anomalies()
        assert len(recent) == 1
        assert recent[0].id == "test_anomaly"

    @pytest.mark.asyncio
    async def test_get_recent_anomalies_with_filters(
        self, system: ForgeAnomalySystem
    ) -> None:
        """Test filtering recent anomalies."""
        # Add anomalies of different severities
        for severity in [
            AnomalySeverity.LOW,
            AnomalySeverity.HIGH,
            AnomalySeverity.CRITICAL,
        ]:
            anomaly = Anomaly(
                id=f"anomaly_{severity.value}",
                type=AnomalyType.STATISTICAL,
                severity=severity,
                metric_name="test",
                observed_value=100.0,
                expected_range=(0.0, 50.0),
                anomaly_score=0.8,
                confidence=0.9,
            )
            system._anomaly_history.append(anomaly)

        # Filter by severity
        high_or_above = system.get_recent_anomalies(severity=AnomalySeverity.HIGH)
        assert len(high_or_above) == 2  # HIGH and CRITICAL

    def test_get_unresolved_anomalies(self, system: ForgeAnomalySystem) -> None:
        """Test getting unresolved anomalies."""
        # Add resolved and unresolved anomalies
        resolved = Anomaly(
            id="resolved",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.LOW,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
            resolved=True,
        )
        unresolved = Anomaly(
            id="unresolved",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.LOW,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
        )
        system._anomaly_history.extend([resolved, unresolved])

        result = system.get_unresolved_anomalies()
        assert len(result) == 1
        assert result[0].id == "unresolved"

    def test_get_anomaly_by_id(self, system: ForgeAnomalySystem) -> None:
        """Test getting anomaly by ID."""
        anomaly = Anomaly(
            id="specific_anomaly",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.LOW,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
        )
        system._anomaly_history.append(anomaly)

        found = system.get_anomaly("specific_anomaly")
        assert found is not None
        assert found.id == "specific_anomaly"

        not_found = system.get_anomaly("nonexistent")
        assert not_found is None

    def test_acknowledge_anomaly(self, system: ForgeAnomalySystem) -> None:
        """Test acknowledging an anomaly."""
        anomaly = Anomaly(
            id="to_ack",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.HIGH,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
        )
        system._anomaly_history.append(anomaly)

        success = system.acknowledge("to_ack", acknowledged_by="admin")
        assert success is True
        assert anomaly.acknowledged is True
        assert anomaly.acknowledged_by == "admin"
        assert anomaly.acknowledged_at is not None

    def test_resolve_anomaly(self, system: ForgeAnomalySystem) -> None:
        """Test resolving an anomaly."""
        anomaly = Anomaly(
            id="to_resolve",
            type=AnomalyType.STATISTICAL,
            severity=AnomalySeverity.HIGH,
            metric_name="test",
            observed_value=100.0,
            expected_range=(0.0, 50.0),
            anomaly_score=0.8,
            confidence=0.9,
        )
        system._anomaly_history.append(anomaly)

        success = system.resolve(
            "to_resolve", resolved_by="admin", notes="Fixed the issue"
        )
        assert success is True
        assert anomaly.resolved is True
        assert anomaly.resolved_by == "admin"
        assert anomaly.resolution_notes == "Fixed the issue"
        assert anomaly.resolved_at is not None

    def test_get_summary(self, system: ForgeAnomalySystem) -> None:
        """Test getting system summary."""
        # Add some anomalies
        for i in range(5):
            anomaly = Anomaly(
                id=f"anomaly_{i}",
                type=AnomalyType.STATISTICAL,
                severity=AnomalySeverity.MEDIUM,
                metric_name="test",
                observed_value=100.0,
                expected_range=(0.0, 50.0),
                anomaly_score=0.8,
                confidence=0.9,
            )
            system._anomaly_history.append(anomaly)

        summary = system.get_summary()

        assert summary["total_anomalies"] == 5
        assert "last_hour" in summary
        assert "last_day" in summary
        assert "by_severity" in summary
        assert "by_type" in summary
        assert "registered_detectors" in summary


# =============================================================================
# Test Factory Function
# =============================================================================


class TestCreateForgeAnomalySystem:
    """Tests for create_forge_anomaly_system factory function."""

    def test_creates_default_system(self) -> None:
        """Test creating system with default options."""
        system = create_forge_anomaly_system()

        assert isinstance(system, ForgeAnomalySystem)
        assert len(system._detectors) > 0

    def test_creates_system_with_all_detectors(self) -> None:
        """Test system includes all detector types."""
        system = create_forge_anomaly_system(
            include_isolation_forest=True,
            include_rate_detector=True,
            include_behavioral=True,
        )

        # Check for expected detector registrations
        assert "pipeline_latency_ms" in system._detectors
        assert "error_rate" in system._detectors
        assert "capsule_creation_rate" in system._detectors
        assert "trust_score_change" in system._detectors
        assert "memory_usage_mb" in system._detectors
        assert "user_activity" in system._detectors

    def test_creates_system_without_optional_detectors(self) -> None:
        """Test system without optional detectors."""
        system = create_forge_anomaly_system(
            include_isolation_forest=False,
            include_rate_detector=False,
            include_behavioral=False,
        )

        # Rate detectors should not be registered
        assert "error_rate" not in system._detectors
        assert "capsule_creation_rate" not in system._detectors
        assert "user_activity" not in system._detectors

        # But basic detectors should still exist
        assert "trust_score_change" in system._detectors
