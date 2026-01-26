"""
Wearable Data Analyzer

Analyzes wearable data for health insights and abnormality detection.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from .converter import WearableConverter, create_wearable_converter
from .models import (
    ActivityData,
    HeartRateData,
    SleepData,
    WearableSession,
)

logger = structlog.get_logger(__name__)


@dataclass
class AnalyzerConfig:
    """Configuration for wearable analysis."""

    # Trend detection
    trend_window_days: int = 7
    significant_change_percent: float = 15.0

    # Baseline calculation
    baseline_window_days: int = 30

    # Alert thresholds
    alert_on_critical: bool = True
    alert_on_trend: bool = True


class WearableAnalyzer:
    """
    Analyzes wearable data for health patterns.

    Provides:
    - Summary statistics
    - Trend analysis
    - Abnormality detection
    - Baseline comparison
    - Health score calculation
    """

    def __init__(
        self,
        config: AnalyzerConfig | None = None,
        converter: WearableConverter | None = None,
    ):
        """
        Initialize the analyzer.

        Args:
            config: Analyzer configuration
            converter: Wearable data converter
        """
        self.config = config or AnalyzerConfig()
        self._converter = converter or create_wearable_converter()

    def analyze_session(
        self,
        session: WearableSession,
    ) -> dict[str, Any]:
        """
        Analyze a wearable data session.

        Args:
            session: Wearable data session

        Returns:
            Analysis results
        """
        abnormalities: list[dict[str, Any]] = []
        heart_analysis: dict[str, Any] | None = None
        sleep_analysis: dict[str, Any] | None = None
        activity_analysis: dict[str, Any] | None = None
        oxygen_analysis: dict[str, Any] | None = None

        # Analyze heart rate data
        if session.heart_rate_data:
            heart_analysis = self._analyze_heart_rate(session.heart_rate_data)
            abnormalities.extend(heart_analysis.get("abnormalities", []))

        # Analyze sleep data
        if session.sleep_data:
            sleep_analysis = self._analyze_sleep(session.sleep_data)
            abnormalities.extend(sleep_analysis.get("abnormalities", []))

        # Analyze activity data
        if session.activity_data:
            activity_analysis = self._analyze_activity(session.activity_data)
            abnormalities.extend(activity_analysis.get("abnormalities", []))

        # Analyze oxygen data
        if session.oxygen_data:
            oxygen_analysis = self._analyze_oxygen(session)
            abnormalities.extend(oxygen_analysis.get("abnormalities", []))

        # Convert to phenotypes
        phenotypes = self._converter.convert_session(session)

        results: dict[str, Any] = {
            "session_id": session.id,
            "analysis_timestamp": datetime.now(UTC).isoformat(),
            "data_summary": self._generate_data_summary(session),
            "heart_analysis": heart_analysis,
            "sleep_analysis": sleep_analysis,
            "activity_analysis": activity_analysis,
            "oxygen_analysis": oxygen_analysis,
            "abnormalities": abnormalities,
            "health_indicators": {},
            "phenotypes": phenotypes,
        }

        # Calculate health indicators
        results["health_indicators"] = self._calculate_health_indicators(results)

        # Update session
        session.abnormalities = abnormalities
        session.phenotypes = phenotypes

        logger.info(
            "wearable_analysis_complete",
            session_id=session.id,
            abnormalities=len(abnormalities),
            phenotypes=len(phenotypes),
        )

        return results

    def _generate_data_summary(
        self,
        session: WearableSession,
    ) -> dict[str, Any]:
        """Generate summary of available data."""
        return {
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "duration_hours": session.duration.total_seconds() / 3600 if session.duration else None,
            "heart_rate_readings": len(session.heart_rate_data),
            "sleep_sessions": len(session.sleep_data),
            "activity_days": len(session.activity_data),
            "oxygen_readings": len(session.oxygen_data),
            "ecg_recordings": len(session.ecg_data),
            "devices": session.devices,
        }

    def _analyze_heart_rate(
        self,
        data: list[HeartRateData],
    ) -> dict[str, Any]:
        """Analyze heart rate data."""
        if not data:
            return {"message": "No heart rate data"}

        hr_values = [d.bpm for d in data if d.bpm > 0]
        resting_values = [d.resting_hr for d in data if d.resting_hr]
        hrv_values = [d.hrv_rmssd for d in data if d.hrv_rmssd is not None]

        statistics: dict[str, Any] = {}
        abnormalities: list[dict[str, Any]] = []
        trends: dict[str, Any] = {}

        # Heart rate statistics
        if hr_values:
            statistics["heart_rate"] = {
                "mean": sum(hr_values) / len(hr_values),
                "min": min(hr_values),
                "max": max(hr_values),
                "range": max(hr_values) - min(hr_values),
            }

        # Resting heart rate
        if resting_values:
            avg_resting = sum(resting_values) / len(resting_values)
            statistics["resting_hr"] = {
                "mean": avg_resting,
                "min": min(resting_values),
                "max": max(resting_values),
            }

            # Check for elevated resting HR
            if avg_resting > 85:
                abnormalities.append(
                    {
                        "type": "elevated_resting_hr",
                        "severity": "moderate" if avg_resting > 100 else "mild",
                        "value": avg_resting,
                        "message": f"Elevated average resting heart rate: {avg_resting:.0f} bpm",
                    }
                )

        # HRV analysis
        if hrv_values:
            avg_hrv = sum(hrv_values) / len(hrv_values)
            statistics["hrv"] = {
                "mean_rmssd": avg_hrv,
                "min_rmssd": min(hrv_values),
                "max_rmssd": max(hrv_values),
            }

            if avg_hrv < 20:
                abnormalities.append(
                    {
                        "type": "low_hrv",
                        "severity": "moderate",
                        "value": avg_hrv,
                        "message": f"Low heart rate variability: {avg_hrv:.1f} ms (may indicate stress or autonomic dysfunction)",
                    }
                )

        # Check for arrhythmia indicators
        irregular_count = sum(1 for d in data if d.is_irregular)
        if irregular_count > 0:
            abnormalities.append(
                {
                    "type": "irregular_rhythm",
                    "severity": "moderate" if irregular_count > 5 else "mild",
                    "count": irregular_count,
                    "message": f"Detected {irregular_count} episodes of irregular heart rhythm",
                }
            )

        # Trend analysis
        if len(hr_values) >= 14:  # At least 2 weeks of data
            trends = self._calculate_hr_trends(data)

        return {
            "reading_count": len(data),
            "statistics": statistics,
            "abnormalities": abnormalities,
            "trends": trends,
        }

    def _analyze_sleep(
        self,
        data: list[SleepData],
    ) -> dict[str, Any]:
        """Analyze sleep data."""
        if not data:
            return {"message": "No sleep data"}

        statistics: dict[str, Any] = {}
        abnormalities: list[dict[str, Any]] = []
        patterns: dict[str, Any] = {}

        # Duration statistics
        durations = [d.total_duration_minutes for d in data]
        statistics["duration"] = {
            "mean_hours": sum(durations) / len(durations) / 60,
            "min_hours": min(durations) / 60,
            "max_hours": max(durations) / 60,
        }

        # Efficiency
        efficiencies = [d.sleep_efficiency for d in data]
        avg_efficiency = sum(efficiencies) / len(efficiencies)
        statistics["efficiency"] = {
            "mean": avg_efficiency,
            "min": min(efficiencies),
        }

        if avg_efficiency < 0.75:
            abnormalities.append(
                {
                    "type": "poor_sleep_efficiency",
                    "severity": "moderate",
                    "value": avg_efficiency,
                    "message": f"Low average sleep efficiency: {avg_efficiency:.0%}",
                }
            )

        # Deep sleep
        deep_pcts = [d.deep_sleep_percentage for d in data]
        avg_deep = sum(deep_pcts) / len(deep_pcts)
        statistics["deep_sleep"] = {
            "mean_percent": avg_deep,
        }

        if avg_deep < 10:
            abnormalities.append(
                {
                    "type": "low_deep_sleep",
                    "severity": "mild",
                    "value": avg_deep,
                    "message": f"Low deep sleep: {avg_deep:.1f}% (recommended: 15-20%)",
                }
            )

        # Sleep apnea indicators
        apnea_nights = sum(1 for d in data if d.possible_apnea or d.spo2_dips_count > 5)
        if apnea_nights > 0:
            abnormalities.append(
                {
                    "type": "sleep_apnea_indicator",
                    "severity": "moderate" if apnea_nights > len(data) * 0.3 else "mild",
                    "nights_affected": apnea_nights,
                    "message": f"Possible sleep apnea indicators on {apnea_nights} nights",
                }
            )

        # Wake patterns
        avg_wakes = sum(d.wake_count for d in data) / len(data)
        patterns["avg_wake_episodes"] = avg_wakes

        return {
            "session_count": len(data),
            "statistics": statistics,
            "abnormalities": abnormalities,
            "patterns": patterns,
        }

    def _analyze_activity(
        self,
        data: list[ActivityData],
    ) -> dict[str, Any]:
        """Analyze activity data."""
        if not data:
            return {"message": "No activity data"}

        statistics: dict[str, Any] = {}
        abnormalities: list[dict[str, Any]] = []
        trends: dict[str, Any] = {}

        # Steps
        steps = [d.steps for d in data]
        avg_steps = sum(steps) / len(steps)
        statistics["steps"] = {
            "mean": avg_steps,
            "min": min(steps),
            "max": max(steps),
            "total": sum(steps),
        }

        if avg_steps < 5000:
            severity = "moderate" if avg_steps < 2500 else "mild"
            abnormalities.append(
                {
                    "type": "low_activity",
                    "severity": severity,
                    "value": avg_steps,
                    "message": f"Low average daily steps: {avg_steps:.0f} (recommended: 7,000-10,000)",
                }
            )

        # Active minutes
        active_mins = [
            d.light_active_minutes + d.moderate_active_minutes + d.vigorous_active_minutes
            for d in data
        ]
        avg_active = sum(active_mins) / len(active_mins)
        statistics["active_minutes"] = {
            "mean": avg_active,
            "min": min(active_mins),
            "max": max(active_mins),
        }

        if avg_active < 30:
            abnormalities.append(
                {
                    "type": "insufficient_active_time",
                    "severity": "moderate",
                    "value": avg_active,
                    "message": f"Low daily active time: {avg_active:.0f} minutes (recommended: 30+ minutes)",
                }
            )

        # Sedentary time
        sedentary = [d.sedentary_minutes for d in data]
        avg_sedentary = sum(sedentary) / len(sedentary)
        statistics["sedentary_hours"] = avg_sedentary / 60

        if avg_sedentary > 600:  # 10 hours
            abnormalities.append(
                {
                    "type": "excessive_sedentary",
                    "severity": "mild",
                    "value": avg_sedentary / 60,
                    "message": f"High sedentary time: {avg_sedentary / 60:.1f} hours/day",
                }
            )

        return {
            "day_count": len(data),
            "statistics": statistics,
            "abnormalities": abnormalities,
            "trends": trends,
        }

    def _analyze_oxygen(
        self,
        session: WearableSession,
    ) -> dict[str, Any]:
        """Analyze oxygen data."""
        data = session.oxygen_data
        if not data:
            return {"message": "No oxygen data"}

        statistics: dict[str, Any] = {}
        abnormalities: list[dict[str, Any]] = []

        spo2_values = [d.spo2_percent for d in data if d.spo2_percent > 0]
        if not spo2_values:
            return {
                "reading_count": len(data),
                "statistics": statistics,
                "abnormalities": abnormalities,
            }

        avg_spo2 = sum(spo2_values) / len(spo2_values)
        min_spo2 = min(spo2_values)

        statistics["spo2"] = {
            "mean": avg_spo2,
            "min": min_spo2,
            "max": max(spo2_values),
        }

        # Low oxygen
        low_count = sum(1 for v in spo2_values if v < 94)
        if low_count > 0 or min_spo2 < 92:
            severity = "severe" if min_spo2 < 90 else "moderate" if min_spo2 < 92 else "mild"
            abnormalities.append(
                {
                    "type": "hypoxemia",
                    "severity": severity,
                    "min_value": min_spo2,
                    "low_reading_count": low_count,
                    "message": f"Low oxygen saturation detected: minimum {min_spo2:.0f}%",
                }
            )

        # Check sleep oxygen separately
        sleep_oxygen = [d for d in data if d.is_sleeping]
        if sleep_oxygen:
            sleep_spo2 = [d.spo2_percent for d in sleep_oxygen if d.spo2_percent > 0]
            if sleep_spo2:
                min_sleep_spo2 = min(sleep_spo2)
                if min_sleep_spo2 < 94:
                    abnormalities.append(
                        {
                            "type": "nocturnal_hypoxemia",
                            "severity": "moderate",
                            "min_value": min_sleep_spo2,
                            "message": f"Nocturnal oxygen desaturation: minimum {min_sleep_spo2:.0f}%",
                        }
                    )

        return {
            "reading_count": len(data),
            "statistics": statistics,
            "abnormalities": abnormalities,
        }

    def _calculate_hr_trends(
        self,
        data: list[HeartRateData],
    ) -> dict[str, Any]:
        """Calculate heart rate trends over time."""
        if len(data) < 14:
            return {}

        # Sort by timestamp
        sorted_data = sorted(data, key=lambda d: d.timestamp)

        # Split into first and last week
        mid_point = len(sorted_data) // 2
        first_half = sorted_data[:mid_point]
        second_half = sorted_data[mid_point:]

        first_avg = sum(d.bpm for d in first_half) / len(first_half) if first_half else 0
        second_avg = sum(d.bpm for d in second_half) / len(second_half) if second_half else 0

        # Avoid division by zero
        if first_avg == 0:
            change_percent = 0.0
        else:
            change_percent = (second_avg - first_avg) / first_avg * 100

        trend = "stable"
        if change_percent > self.config.significant_change_percent:
            trend = "increasing"
        elif change_percent < -self.config.significant_change_percent:
            trend = "decreasing"

        return {
            "trend": trend,
            "change_percent": change_percent,
            "first_period_avg": first_avg,
            "second_period_avg": second_avg,
        }

    def _calculate_health_indicators(
        self,
        analysis_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate overall health indicators."""
        indicators = {
            "overall_score": 100,
            "cardiovascular_score": 100,
            "sleep_score": 100,
            "activity_score": 100,
        }

        # Deduct for abnormalities
        abnormalities = analysis_results.get("abnormalities", [])
        for abnormality in abnormalities:
            severity = abnormality.get("severity", "mild")
            deduction = {"mild": 5, "moderate": 10, "severe": 20}.get(severity, 5)

            # Apply to relevant category
            abnorm_type = abnormality.get("type", "")
            if any(kw in abnorm_type for kw in ["hr", "heart", "rhythm", "hrv"]):
                indicators["cardiovascular_score"] -= deduction
            elif any(kw in abnorm_type for kw in ["sleep", "apnea"]):
                indicators["sleep_score"] -= deduction
            elif any(kw in abnorm_type for kw in ["activity", "steps", "sedentary"]):
                indicators["activity_score"] -= deduction

            indicators["overall_score"] -= deduction // 2

        # Ensure non-negative
        for key in indicators:
            indicators[key] = max(0, indicators[key])

        return indicators


# =============================================================================
# Factory Function
# =============================================================================


def create_wearable_analyzer(
    config: AnalyzerConfig | None = None,
    converter: WearableConverter | None = None,
) -> WearableAnalyzer:
    """Create a wearable analyzer instance."""
    return WearableAnalyzer(
        config=config,
        converter=converter,
    )
