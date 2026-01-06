"""
Forge Cascade V2 - Anomaly Detection System
ML-based anomaly detection for identifying unusual patterns in Forge.

This module provides:
1. IsolationForest-based anomaly detection
2. Statistical anomaly detection (Z-score, IQR)
3. Time-series anomaly detection
4. Behavioral anomaly detection for users

This is part of Forge's Immune System - detecting threats and
unusual patterns before they become problems.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Generic, TypeVar

import structlog

logger = structlog.get_logger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies detected."""
    STATISTICAL = "statistical"       # Z-score / IQR based
    BEHAVIORAL = "behavioral"         # User behavior changes
    TEMPORAL = "temporal"             # Time-series patterns
    ISOLATION = "isolation"           # IsolationForest detection
    THRESHOLD = "threshold"           # Simple threshold breach
    RATE = "rate"                     # Rate-based anomalies
    COMPOSITE = "composite"           # Multiple signals


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"           # Minor deviation
    MEDIUM = "medium"     # Notable anomaly
    HIGH = "high"         # Significant threat
    CRITICAL = "critical" # Immediate action needed


@dataclass
class Anomaly:
    """Represents a detected anomaly."""

    id: str
    type: AnomalyType
    severity: AnomalySeverity

    # What was detected
    metric_name: str
    observed_value: float
    expected_range: tuple[float, float]

    # Scores
    anomaly_score: float  # 0-1, higher = more anomalous
    confidence: float     # 0-1, confidence in detection

    # Context
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: dict[str, Any] = field(default_factory=dict)
    related_anomalies: list[str] = field(default_factory=list)

    # Status
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None

    # Aliases for frontend compatibility
    @property
    def value(self) -> float:
        """Alias for observed_value."""
        return self.observed_value

    @property
    def expected_value(self) -> float | None:
        """Get the midpoint of expected range."""
        if self.expected_range:
            return (self.expected_range[0] + self.expected_range[1]) / 2
        return None

    @property
    def detected_at(self) -> datetime:
        """Alias for timestamp."""
        return self.timestamp

    @property
    def anomaly_type(self) -> AnomalyType:
        """Alias for type."""
        return self.type
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "expected_range": self.expected_range,
            "anomaly_score": self.anomaly_score,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "related_anomalies": self.related_anomalies,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


@dataclass
class AnomalyDetectorConfig:
    """Configuration for anomaly detectors."""
    
    # Statistical detection
    z_score_threshold: float = 3.0     # Standard deviations
    iqr_multiplier: float = 1.5        # IQR fence multiplier
    
    # IsolationForest
    contamination: float = 0.1         # Expected anomaly proportion
    n_estimators: int = 100            # Number of trees
    max_samples: int = 256             # Samples per tree
    
    # Sliding window
    window_size: int = 100             # Data points to keep
    min_samples: int = 20              # Minimum for detection
    
    # Sensitivity
    score_threshold: float = 0.6       # Anomaly score threshold
    confidence_threshold: float = 0.7  # Minimum confidence
    
    # Rate limiting
    cooldown_seconds: float = 60.0     # Min time between same alerts
    max_alerts_per_hour: int = 100     # Rate limit alerts


class AnomalyDetector(ABC):
    """Base class for anomaly detectors."""
    
    def __init__(
        self,
        name: str,
        config: AnomalyDetectorConfig | None = None
    ):
        self.name = name
        self.config = config or AnomalyDetectorConfig()
        self._data_buffer: list[tuple[datetime, float]] = []
        self._last_alert_time: dict[str, datetime] = {}
        self._alerts_this_hour: int = 0
        self._hour_start: datetime = datetime.now(timezone.utc)
    
    @abstractmethod
    async def detect(self, value: float, context: dict[str, Any] | None = None) -> Anomaly | None:
        """Detect if value is anomalous."""
        pass
    
    def add_data_point(self, value: float, timestamp: datetime | None = None) -> None:
        """Add a data point to the buffer."""
        ts = timestamp or datetime.now(timezone.utc)
        self._data_buffer.append((ts, value))
        
        # Trim to window size
        if len(self._data_buffer) > self.config.window_size:
            self._data_buffer = self._data_buffer[-self.config.window_size:]
    
    def get_values(self) -> list[float]:
        """Get buffered values."""
        return [v for _, v in self._data_buffer]
    
    def _can_alert(self, metric_name: str) -> bool:
        """Check if we can raise an alert (rate limiting)."""
        now = datetime.now(timezone.utc)
        
        # Reset hourly counter
        if (now - self._hour_start).total_seconds() > 3600:
            self._alerts_this_hour = 0
            self._hour_start = now
        
        # Check hourly limit
        if self._alerts_this_hour >= self.config.max_alerts_per_hour:
            return False
        
        # Check cooldown
        if metric_name in self._last_alert_time:
            elapsed = (now - self._last_alert_time[metric_name]).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                return False
        
        return True
    
    def _record_alert(self, metric_name: str) -> None:
        """Record that we raised an alert."""
        self._last_alert_time[metric_name] = datetime.now(timezone.utc)
        self._alerts_this_hour += 1
    
    def _generate_id(self) -> str:
        """Generate unique anomaly ID."""
        import uuid
        return f"anomaly_{uuid.uuid4().hex[:12]}"


class StatisticalAnomalyDetector(AnomalyDetector):
    """
    Statistical anomaly detection using Z-score and IQR.
    
    Simple but effective for normally distributed data.
    """
    
    def __init__(self, name: str = "statistical", config: AnomalyDetectorConfig | None = None):
        super().__init__(name, config)
    
    async def detect(self, value: float, context: dict[str, Any] | None = None) -> Anomaly | None:
        """Detect statistical anomalies."""
        self.add_data_point(value)
        
        values = self.get_values()
        if len(values) < self.config.min_samples:
            return None
        
        # Calculate statistics
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 0.001
        
        # Z-score detection
        z_score = abs(value - mean) / std
        z_score_anomaly = z_score > self.config.z_score_threshold
        
        # IQR detection
        sorted_values = sorted(values)
        n = len(sorted_values)
        q1 = sorted_values[n // 4]
        q3 = sorted_values[3 * n // 4]
        iqr = q3 - q1
        lower_fence = q1 - self.config.iqr_multiplier * iqr
        upper_fence = q3 + self.config.iqr_multiplier * iqr
        iqr_anomaly = value < lower_fence or value > upper_fence
        
        # Combine signals
        if not (z_score_anomaly or iqr_anomaly):
            return None
        
        metric_name = context.get("metric_name", "unknown") if context else "unknown"
        if not self._can_alert(metric_name):
            return None
        
        # Calculate anomaly score (0-1)
        z_normalized = min(z_score / (2 * self.config.z_score_threshold), 1.0)
        
        if iqr > 0:
            if value < lower_fence:
                iqr_distance = (lower_fence - value) / iqr
            else:
                iqr_distance = (value - upper_fence) / iqr
            iqr_normalized = min(iqr_distance / self.config.iqr_multiplier, 1.0)
        else:
            iqr_normalized = 0.0
        
        # Combined score
        anomaly_score = max(z_normalized, iqr_normalized)
        confidence = 0.5 + 0.5 * (len(values) / self.config.window_size)
        
        if anomaly_score < self.config.score_threshold:
            return None
        
        # Determine severity
        if anomaly_score > 0.9:
            severity = AnomalySeverity.CRITICAL
        elif anomaly_score > 0.7:
            severity = AnomalySeverity.HIGH
        elif anomaly_score > 0.5:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        
        self._record_alert(metric_name)
        
        return Anomaly(
            id=self._generate_id(),
            type=AnomalyType.STATISTICAL,
            severity=severity,
            metric_name=metric_name,
            observed_value=value,
            expected_range=(lower_fence, upper_fence),
            anomaly_score=anomaly_score,
            confidence=confidence,
            context={
                "z_score": z_score,
                "mean": mean,
                "std": std,
                "iqr": iqr,
                "sample_size": len(values),
                **(context or {}),
            },
        )


class IsolationForestDetector(AnomalyDetector):
    """
    IsolationForest-based anomaly detection.
    
    Works by randomly partitioning data and measuring how
    quickly points become isolated. Anomalies isolate faster.
    
    This is a pure Python implementation suitable for edge deployment.
    """
    
    def __init__(self, name: str = "isolation_forest", config: AnomalyDetectorConfig | None = None):
        super().__init__(name, config)
        self._trees: list[IsolationTree] = []
        self._trained: bool = False
        self._training_lock = asyncio.Lock()
    
    async def detect(self, value: float, context: dict[str, Any] | None = None) -> Anomaly | None:
        """Detect anomalies using IsolationForest."""
        self.add_data_point(value)
        
        values = self.get_values()
        if len(values) < self.config.min_samples:
            return None
        
        # Retrain if needed (async lock to prevent concurrent training)
        async with self._training_lock:
            if not self._trained or len(values) % 50 == 0:
                await self._train(values)
        
        # Get anomaly score
        anomaly_score = self._score_point(value)
        
        if anomaly_score < self.config.score_threshold:
            return None
        
        metric_name = context.get("metric_name", "unknown") if context else "unknown"
        if not self._can_alert(metric_name):
            return None
        
        # Calculate expected range from training data
        sorted_vals = sorted(values)
        p5 = sorted_vals[max(0, int(len(sorted_vals) * 0.05))]
        p95 = sorted_vals[min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))]
        
        # Determine severity based on score
        if anomaly_score > 0.9:
            severity = AnomalySeverity.CRITICAL
        elif anomaly_score > 0.75:
            severity = AnomalySeverity.HIGH
        elif anomaly_score > 0.6:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        
        confidence = min(len(values) / self.config.window_size, 1.0)
        
        self._record_alert(metric_name)
        
        return Anomaly(
            id=self._generate_id(),
            type=AnomalyType.ISOLATION,
            severity=severity,
            metric_name=metric_name,
            observed_value=value,
            expected_range=(p5, p95),
            anomaly_score=anomaly_score,
            confidence=confidence,
            context={
                "n_trees": len(self._trees),
                "sample_size": len(values),
                "contamination": self.config.contamination,
                **(context or {}),
            },
        )
    
    async def _train(self, values: list[float]) -> None:
        """Train IsolationForest on data."""
        self._trees = []
        
        n_samples = min(len(values), self.config.max_samples)
        max_depth = int(math.ceil(math.log2(n_samples))) if n_samples > 1 else 1
        
        for _ in range(self.config.n_estimators):
            # Sample data
            sample = random.sample(values, n_samples)
            
            # Build tree
            tree = IsolationTree(max_depth=max_depth)
            tree.fit(sample)
            self._trees.append(tree)
        
        self._trained = True
        
        logger.debug(
            "isolation_forest_trained",
            n_trees=len(self._trees),
            n_samples=n_samples,
            max_depth=max_depth,
        )
    
    def _score_point(self, value: float) -> float:
        """Calculate anomaly score for a point."""
        if not self._trees:
            return 0.0
        
        # Average path length across all trees
        path_lengths = [tree.path_length(value) for tree in self._trees]
        avg_path_length = sum(path_lengths) / len(path_lengths)
        
        # Normalize using expected path length
        n = len(self.get_values())
        c_n = self._expected_path_length(n)
        
        if c_n == 0:
            return 0.5
        
        # Anomaly score: 2^(-avg_path_length / c(n))
        # Higher score = more anomalous
        score = 2 ** (-avg_path_length / c_n)
        
        return score
    
    @staticmethod
    def _expected_path_length(n: int) -> float:
        """Expected path length for BST with n samples."""
        if n <= 1:
            return 0.0
        if n == 2:
            return 1.0
        
        # H(n-1) approximation: ln(n-1) + 0.5772156649 (Euler-Mascheroni)
        h_n_minus_1 = math.log(n - 1) + 0.5772156649
        return 2 * h_n_minus_1 - (2 * (n - 1) / n)


class IsolationTree:
    """Single tree in IsolationForest."""
    
    def __init__(self, max_depth: int = 8):
        self.max_depth = max_depth
        self.root: IsolationNode | None = None
    
    def fit(self, data: list[float]) -> None:
        """Build tree from data."""
        self.root = self._build_tree(data, 0)
    
    def _build_tree(self, data: list[float], depth: int) -> IsolationNode:
        """Recursively build tree."""
        n = len(data)
        
        # Base case: max depth or single point
        if depth >= self.max_depth or n <= 1:
            return IsolationNode(size=n)
        
        # Random split point
        min_val, max_val = min(data), max(data)
        
        if min_val == max_val:
            return IsolationNode(size=n)
        
        split_value = random.uniform(min_val, max_val)
        
        # Partition
        left_data = [x for x in data if x < split_value]
        right_data = [x for x in data if x >= split_value]
        
        # Handle edge cases
        if not left_data or not right_data:
            return IsolationNode(size=n)
        
        return IsolationNode(
            split_value=split_value,
            left=self._build_tree(left_data, depth + 1),
            right=self._build_tree(right_data, depth + 1),
        )
    
    def path_length(self, value: float) -> float:
        """Calculate path length for a value."""
        return self._path_length(self.root, value, 0)
    
    def _path_length(self, node: IsolationNode | None, value: float, depth: int) -> float:
        """Recursively calculate path length."""
        if node is None:
            return depth
        
        if node.is_leaf:
            # Adjust for external nodes (BST average path)
            if node.size > 1:
                return depth + self._c(node.size)
            return depth
        
        if value < node.split_value:
            return self._path_length(node.left, value, depth + 1)
        return self._path_length(node.right, value, depth + 1)
    
    @staticmethod
    def _c(n: int) -> float:
        """Expected path adjustment for external nodes."""
        if n <= 1:
            return 0.0
        if n == 2:
            return 1.0
        h = math.log(n - 1) + 0.5772156649
        return 2 * h - (2 * (n - 1) / n)


@dataclass
class IsolationNode:
    """Node in IsolationTree."""
    
    size: int = 1
    split_value: float | None = None
    left: IsolationNode | None = None
    right: IsolationNode | None = None
    
    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


class RateAnomalyDetector(AnomalyDetector):
    """
    Detect anomalies in event rates.
    
    Useful for detecting sudden spikes or drops in activity.
    """
    
    def __init__(
        self,
        name: str = "rate",
        config: AnomalyDetectorConfig | None = None,
        bucket_seconds: float = 60.0,
    ):
        super().__init__(name, config)
        self.bucket_seconds = bucket_seconds
        self._buckets: dict[int, int] = defaultdict(int)
    
    async def detect(self, value: float = 1.0, context: dict[str, Any] | None = None) -> Anomaly | None:
        """Detect rate anomalies. value is the event weight (usually 1)."""
        now = datetime.now(timezone.utc)
        bucket = int(now.timestamp() / self.bucket_seconds)
        
        # Increment bucket
        self._buckets[bucket] += int(value)
        
        # Clean old buckets (keep last window_size)
        min_bucket = bucket - self.config.window_size
        self._buckets = {k: v for k, v in self._buckets.items() if k >= min_bucket}
        
        # Get recent rates
        rates = [self._buckets.get(bucket - i, 0) for i in range(self.config.window_size)]
        
        if len([r for r in rates if r > 0]) < self.config.min_samples:
            return None
        
        current_rate = rates[0]
        
        # Calculate statistics
        mean = sum(rates) / len(rates)
        variance = sum((x - mean) ** 2 for x in rates) / len(rates)
        std = math.sqrt(variance) if variance > 0 else 0.001
        
        # Z-score for rate
        if std > 0:
            z_score = abs(current_rate - mean) / std
        else:
            z_score = 0.0
        
        if z_score < self.config.z_score_threshold:
            return None
        
        metric_name = context.get("metric_name", "rate") if context else "rate"
        if not self._can_alert(metric_name):
            return None
        
        # Anomaly score
        anomaly_score = min(z_score / (2 * self.config.z_score_threshold), 1.0)
        
        # Direction matters for severity
        is_spike = current_rate > mean
        
        if is_spike and current_rate > mean + 4 * std:
            severity = AnomalySeverity.CRITICAL
        elif is_spike and current_rate > mean + 3 * std:
            severity = AnomalySeverity.HIGH
        elif current_rate < mean - 3 * std:  # Sudden drop
            severity = AnomalySeverity.HIGH
        elif z_score > 3:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        
        self._record_alert(metric_name)
        
        return Anomaly(
            id=self._generate_id(),
            type=AnomalyType.RATE,
            severity=severity,
            metric_name=metric_name,
            observed_value=current_rate,
            expected_range=(mean - 2 * std, mean + 2 * std),
            anomaly_score=anomaly_score,
            confidence=0.8,
            context={
                "z_score": z_score,
                "mean_rate": mean,
                "std": std,
                "direction": "spike" if is_spike else "drop",
                "bucket_seconds": self.bucket_seconds,
                **(context or {}),
            },
        )


class BehavioralAnomalyDetector(AnomalyDetector):
    """
    Detect anomalies in user behavior patterns.
    
    Tracks per-user metrics and detects deviations from
    their normal behavior.
    """
    
    def __init__(self, name: str = "behavioral", config: AnomalyDetectorConfig | None = None):
        super().__init__(name, config)
        self._user_profiles: dict[str, UserProfile] = {}
    
    async def detect(
        self,
        value: float,
        context: dict[str, Any] | None = None
    ) -> Anomaly | None:
        """Detect behavioral anomalies for a user."""
        if not context or "user_id" not in context:
            return None
        
        user_id = context["user_id"]
        metric_name = context.get("metric_name", "behavior")
        
        # Get or create profile
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)
        
        profile = self._user_profiles[user_id]
        profile.add_observation(metric_name, value)
        
        # Check for anomaly
        stats = profile.get_stats(metric_name)
        if stats["count"] < self.config.min_samples:
            return None
        
        mean, std = stats["mean"], stats["std"]
        if std == 0:
            std = 0.001
        
        z_score = abs(value - mean) / std
        
        if z_score < self.config.z_score_threshold:
            return None
        
        full_metric = f"{user_id}:{metric_name}"
        if not self._can_alert(full_metric):
            return None
        
        anomaly_score = min(z_score / (2 * self.config.z_score_threshold), 1.0)
        
        if anomaly_score > 0.85:
            severity = AnomalySeverity.HIGH
        elif anomaly_score > 0.6:
            severity = AnomalySeverity.MEDIUM
        else:
            severity = AnomalySeverity.LOW
        
        self._record_alert(full_metric)
        
        return Anomaly(
            id=self._generate_id(),
            type=AnomalyType.BEHAVIORAL,
            severity=severity,
            metric_name=metric_name,
            observed_value=value,
            expected_range=(mean - 2 * std, mean + 2 * std),
            anomaly_score=anomaly_score,
            confidence=min(stats["count"] / 50, 1.0),
            context={
                "user_id": user_id,
                "z_score": z_score,
                "user_mean": mean,
                "user_std": std,
                "observation_count": stats["count"],
                **(context or {}),
            },
        )


@dataclass
class UserProfile:
    """Behavioral profile for a user."""
    
    user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Metric observations: metric_name -> list of (timestamp, value)
    _observations: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)
    _max_observations: int = 500
    
    def add_observation(self, metric: str, value: float) -> None:
        """Add an observation for a metric."""
        if metric not in self._observations:
            self._observations[metric] = []
        
        self._observations[metric].append((datetime.now(timezone.utc), value))
        
        # Trim
        if len(self._observations[metric]) > self._max_observations:
            self._observations[metric] = self._observations[metric][-self._max_observations:]
    
    def get_stats(self, metric: str) -> dict[str, float]:
        """Get statistics for a metric."""
        if metric not in self._observations:
            return {"count": 0, "mean": 0.0, "std": 0.0}
        
        values = [v for _, v in self._observations[metric]]
        n = len(values)
        
        if n == 0:
            return {"count": 0, "mean": 0.0, "std": 0.0}
        
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std = math.sqrt(variance)
        
        return {"count": n, "mean": mean, "std": std}


class CompositeAnomalyDetector(AnomalyDetector):
    """
    Combines multiple detectors for robust anomaly detection.
    
    Aggregates signals from different detection methods.
    """
    
    def __init__(
        self,
        name: str = "composite",
        config: AnomalyDetectorConfig | None = None,
        detectors: list[AnomalyDetector] | None = None,
    ):
        super().__init__(name, config)
        self.detectors = detectors or []
        self._min_agreement: int = 2  # Minimum detectors that must agree
    
    def add_detector(self, detector: AnomalyDetector) -> None:
        """Add a detector to the composite."""
        self.detectors.append(detector)
    
    async def detect(self, value: float, context: dict[str, Any] | None = None) -> Anomaly | None:
        """Detect using all sub-detectors."""
        if len(self.detectors) < self._min_agreement:
            return None
        
        # Run all detectors
        anomalies: list[Anomaly] = []
        for detector in self.detectors:
            result = await detector.detect(value, context)
            if result:
                anomalies.append(result)
        
        if len(anomalies) < self._min_agreement:
            return None
        
        metric_name = context.get("metric_name", "composite") if context else "composite"
        if not self._can_alert(metric_name):
            return None
        
        # Aggregate scores
        avg_score = sum(a.anomaly_score for a in anomalies) / len(anomalies)
        max_score = max(a.anomaly_score for a in anomalies)
        avg_confidence = sum(a.confidence for a in anomalies) / len(anomalies)
        
        # Use max severity
        severities = [a.severity for a in anomalies]
        severity_order = [AnomalySeverity.LOW, AnomalySeverity.MEDIUM, 
                         AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]
        max_severity = max(severities, key=lambda s: severity_order.index(s))
        
        # Combine expected ranges
        all_lowers = [a.expected_range[0] for a in anomalies]
        all_uppers = [a.expected_range[1] for a in anomalies]
        combined_range = (sum(all_lowers) / len(all_lowers), sum(all_uppers) / len(all_uppers))
        
        self._record_alert(metric_name)
        
        return Anomaly(
            id=self._generate_id(),
            type=AnomalyType.COMPOSITE,
            severity=max_severity,
            metric_name=metric_name,
            observed_value=value,
            expected_range=combined_range,
            anomaly_score=max_score,  # Use max for composite
            confidence=avg_confidence * (len(anomalies) / len(self.detectors)),
            context={
                "n_detectors": len(self.detectors),
                "n_triggered": len(anomalies),
                "triggered_types": [a.type.value for a in anomalies],
                "individual_scores": {a.type.value: a.anomaly_score for a in anomalies},
                **(context or {}),
            },
            related_anomalies=[a.id for a in anomalies],
        )


class ForgeAnomalySystem:
    """
    Complete anomaly detection system for Forge.
    
    Manages multiple detectors for different metrics and
    provides a unified interface for anomaly detection.
    """
    
    def __init__(self, config: AnomalyDetectorConfig | None = None):
        self.config = config or AnomalyDetectorConfig()
        self._detectors: dict[str, AnomalyDetector] = {}
        self._anomaly_history: list[Anomaly] = []
        self._max_history: int = 1000
        self._callbacks: list[Callable[[Anomaly], Coroutine[Any, Any, None]]] = []
        self._running: bool = False
    
    def register_detector(self, metric_name: str, detector: AnomalyDetector) -> None:
        """Register a detector for a metric."""
        self._detectors[metric_name] = detector
        logger.info("anomaly_detector_registered", metric=metric_name, detector=detector.name)
    
    def register_callback(
        self,
        callback: Callable[[Anomaly], Coroutine[Any, Any, None]]
    ) -> None:
        """Register callback for anomaly notifications."""
        self._callbacks.append(callback)
    
    async def record_metric(
        self,
        metric_name: str,
        value: float,
        context: dict[str, Any] | None = None
    ) -> Anomaly | None:
        """Record a metric value and check for anomalies."""
        detector = self._detectors.get(metric_name)
        
        if not detector:
            # Use default statistical detector
            detector = StatisticalAnomalyDetector(f"auto_{metric_name}", self.config)
            self._detectors[metric_name] = detector
        
        # Add metric name to context
        ctx = context or {}
        ctx["metric_name"] = metric_name
        
        # Detect
        anomaly = await detector.detect(value, ctx)
        
        if anomaly:
            await self._handle_anomaly(anomaly)
        
        return anomaly
    
    async def _handle_anomaly(self, anomaly: Anomaly) -> None:
        """Handle detected anomaly."""
        # Store
        self._anomaly_history.append(anomaly)
        if len(self._anomaly_history) > self._max_history:
            self._anomaly_history = self._anomaly_history[-self._max_history:]
        
        logger.warning(
            "anomaly_detected",
            id=anomaly.id,
            type=anomaly.type.value,
            severity=anomaly.severity.value,
            metric=anomaly.metric_name,
            score=anomaly.anomaly_score,
        )
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                await callback(anomaly)
            except Exception as e:
                logger.error("anomaly_callback_failed", error=str(e))
    
    def get_recent_anomalies(
        self,
        since: datetime | None = None,
        severity: AnomalySeverity | None = None,
        type_filter: AnomalyType | None = None,
    ) -> list[Anomaly]:
        """Get recent anomalies with optional filters."""
        result = self._anomaly_history.copy()
        
        if since:
            result = [a for a in result if a.timestamp >= since]
        
        if severity:
            severity_order = [AnomalySeverity.LOW, AnomalySeverity.MEDIUM,
                            AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]
            min_idx = severity_order.index(severity)
            result = [a for a in result if severity_order.index(a.severity) >= min_idx]
        
        if type_filter:
            result = [a for a in result if a.type == type_filter]
        
        return result
    
    def get_unresolved_anomalies(self) -> list[Anomaly]:
        """Get anomalies that haven't been resolved."""
        return [a for a in self._anomaly_history if not a.resolved]

    def get_anomaly(self, anomaly_id: str) -> Anomaly | None:
        """Get a specific anomaly by ID."""
        for anomaly in self._anomaly_history:
            if anomaly.id == anomaly_id:
                return anomaly
        return None

    def acknowledge(self, anomaly_id: str, acknowledged_by: str | None = None) -> bool:
        """Acknowledge an anomaly."""
        from datetime import datetime, timezone
        for anomaly in self._anomaly_history:
            if anomaly.id == anomaly_id:
                anomaly.acknowledged = True
                anomaly.acknowledged_at = datetime.now(timezone.utc)
                anomaly.acknowledged_by = acknowledged_by
                return True
        return False

    def resolve(self, anomaly_id: str, resolved_by: str | None = None, notes: str | None = None) -> bool:
        """Mark an anomaly as resolved."""
        from datetime import datetime, timezone
        for anomaly in self._anomaly_history:
            if anomaly.id == anomaly_id:
                anomaly.resolved = True
                anomaly.resolved_at = datetime.now(timezone.utc)
                anomaly.resolved_by = resolved_by
                anomaly.resolution_notes = notes
                return True
        return False
    
    def get_summary(self) -> dict[str, Any]:
        """Get anomaly system summary."""
        now = datetime.now(timezone.utc)
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        recent_hour = [a for a in self._anomaly_history if a.timestamp >= last_hour]
        recent_day = [a for a in self._anomaly_history if a.timestamp >= last_day]
        
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        for a in recent_day:
            by_severity[a.severity.value] += 1
            by_type[a.type.value] += 1
        
        return {
            "total_anomalies": len(self._anomaly_history),
            "last_hour": len(recent_hour),
            "last_day": len(recent_day),
            "unresolved": len(self.get_unresolved_anomalies()),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "registered_detectors": list(self._detectors.keys()),
        }


def create_forge_anomaly_system(
    include_isolation_forest: bool = True,
    include_rate_detector: bool = True,
    include_behavioral: bool = True,
) -> ForgeAnomalySystem:
    """
    Create pre-configured anomaly system for Forge.
    
    Sets up appropriate detectors for common Forge metrics.
    """
    config = AnomalyDetectorConfig(
        z_score_threshold=3.0,
        contamination=0.05,  # 5% anomaly rate
        window_size=100,
        min_samples=20,
        score_threshold=0.6,
    )
    
    system = ForgeAnomalySystem(config)
    
    # Register default detectors
    
    # Pipeline latency
    latency_detector = CompositeAnomalyDetector("pipeline_latency", config)
    latency_detector.add_detector(StatisticalAnomalyDetector("stat_latency", config))
    if include_isolation_forest:
        latency_detector.add_detector(IsolationForestDetector("iso_latency", config))
    system.register_detector("pipeline_latency_ms", latency_detector)
    
    # Error rates
    if include_rate_detector:
        error_rate_config = AnomalyDetectorConfig(
            z_score_threshold=2.5,  # More sensitive for errors
            window_size=60,
            cooldown_seconds=30.0,
        )
        system.register_detector(
            "error_rate",
            RateAnomalyDetector("error_rate", error_rate_config, bucket_seconds=60.0)
        )
    
    # Capsule creation rate
    if include_rate_detector:
        system.register_detector(
            "capsule_creation_rate",
            RateAnomalyDetector("capsule_rate", config, bucket_seconds=60.0)
        )
    
    # Trust score changes
    system.register_detector(
        "trust_score_change",
        StatisticalAnomalyDetector("trust_change", config)
    )
    
    # Memory usage
    system.register_detector(
        "memory_usage_mb",
        StatisticalAnomalyDetector("memory", config)
    )
    
    # User behavior (if enabled)
    if include_behavioral:
        behavioral_config = AnomalyDetectorConfig(
            z_score_threshold=2.5,
            min_samples=10,  # Need less history per user
            window_size=50,
        )
        system.register_detector(
            "user_activity",
            BehavioralAnomalyDetector("user_behavior", behavioral_config)
        )
    
    return system


__all__ = [
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "AnomalyDetectorConfig",
    "AnomalyDetector",
    "StatisticalAnomalyDetector",
    "IsolationForestDetector",
    "RateAnomalyDetector",
    "BehavioralAnomalyDetector",
    "CompositeAnomalyDetector",
    "ForgeAnomalySystem",
    "create_forge_anomaly_system",
]
