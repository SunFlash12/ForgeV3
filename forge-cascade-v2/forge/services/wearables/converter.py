"""
Wearable Data Converter

Converts wearable device data to HPO phenotypes for diagnosis.
"""

from dataclasses import dataclass
from typing import Any

import structlog

from .models import (
    ActivityData,
    ECGData,
    HeartRateData,
    OxygenData,
    SleepData,
    WearableSession,
)

logger = structlog.get_logger(__name__)


@dataclass
class ConverterConfig:
    """Configuration for wearable data conversion."""
    # Heart rate thresholds
    tachycardia_threshold: int = 100
    bradycardia_threshold: int = 50
    resting_hr_high_threshold: int = 90

    # HRV thresholds
    low_hrv_threshold: float = 20.0  # RMSSD in ms

    # Oxygen thresholds
    hypoxemia_threshold: float = 94.0
    severe_hypoxemia_threshold: float = 90.0

    # Sleep thresholds
    poor_sleep_efficiency: float = 0.75
    low_deep_sleep_percent: float = 10.0
    apnea_spo2_dip_threshold: int = 5

    # Activity thresholds
    sedentary_hours_threshold: int = 10
    low_steps_threshold: int = 2000

    # Minimum data points
    min_hr_readings: int = 10
    min_sleep_sessions: int = 1
    min_oxygen_readings: int = 5


# HPO codes for wearable-derived phenotypes
HPO_MAPPINGS = {
    # Cardiac
    "tachycardia": "HP:0001649",
    "bradycardia": "HP:0001662",
    "palpitations": "HP:0001962",
    "arrhythmia": "HP:0011675",
    "atrial_fibrillation": "HP:0005110",
    "irregular_heart_rhythm": "HP:0011675",

    # Respiratory/Oxygen
    "hypoxemia": "HP:0012418",
    "sleep_apnea": "HP:0010535",
    "desaturation": "HP:0012418",

    # Sleep
    "insomnia": "HP:0100785",
    "sleep_disturbance": "HP:0002360",
    "excessive_daytime_sleepiness": "HP:0002329",
    "decreased_rem_sleep": "HP:0025434",

    # Activity/Movement
    "fatigue": "HP:0012378",
    "exercise_intolerance": "HP:0003546",
    "decreased_activity": "HP:0001324",

    # Autonomic
    "autonomic_dysfunction": "HP:0012332",
    "orthostatic_intolerance": "HP:0012670",
}


class WearableConverter:
    """
    Converts wearable data to phenotypes.

    Analyzes patterns in wearable data and maps them to
    HPO phenotype codes for integration with diagnosis.
    """

    def __init__(
        self,
        config: ConverterConfig | None = None,
    ):
        """
        Initialize the converter.

        Args:
            config: Converter configuration
        """
        self.config = config or ConverterConfig()

    def convert_session(
        self,
        session: WearableSession,
    ) -> list[dict[str, Any]]:
        """
        Convert a wearable session to phenotypes.

        Args:
            session: Wearable data session

        Returns:
            List of phenotype dictionaries with HPO codes
        """
        phenotypes = []

        # Convert heart rate data
        if session.heart_rate_data:
            hr_phenotypes = self._convert_heart_rate(session.heart_rate_data)
            phenotypes.extend(hr_phenotypes)

        # Convert sleep data
        if session.sleep_data:
            sleep_phenotypes = self._convert_sleep(session.sleep_data)
            phenotypes.extend(sleep_phenotypes)

        # Convert oxygen data
        if session.oxygen_data:
            oxygen_phenotypes = self._convert_oxygen(session.oxygen_data)
            phenotypes.extend(oxygen_phenotypes)

        # Convert ECG data
        if session.ecg_data:
            ecg_phenotypes = self._convert_ecg(session.ecg_data)
            phenotypes.extend(ecg_phenotypes)

        # Convert activity data
        if session.activity_data:
            activity_phenotypes = self._convert_activity(session.activity_data)
            phenotypes.extend(activity_phenotypes)

        # Cross-data analysis
        cross_phenotypes = self._analyze_cross_data(session)
        phenotypes.extend(cross_phenotypes)

        # Update session
        session.phenotypes = phenotypes

        logger.info(
            "wearable_converted",
            session_id=session.id,
            phenotype_count=len(phenotypes),
        )

        return phenotypes

    def _convert_heart_rate(
        self,
        data: list[HeartRateData],
    ) -> list[dict[str, Any]]:
        """Convert heart rate data to phenotypes."""
        phenotypes = []

        if len(data) < self.config.min_hr_readings:
            return phenotypes

        # Calculate statistics
        hr_values = [d.bpm for d in data if d.bpm > 0]
        if not hr_values:
            return phenotypes

        avg_hr = sum(hr_values) / len(hr_values)
        max_hr = max(hr_values)
        min_hr = min(hr_values)

        # Get resting HR
        resting_values = [d.resting_hr for d in data if d.resting_hr]
        sum(resting_values) / len(resting_values) if resting_values else None

        # Check for tachycardia
        tachy_count = sum(1 for hr in hr_values if hr > self.config.tachycardia_threshold)
        if tachy_count > len(hr_values) * 0.1:  # >10% of readings
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["tachycardia"],
                "name": "Tachycardia",
                "source": "wearable_heart_rate",
                "confidence": min(0.9, tachy_count / len(hr_values)),
                "evidence": {
                    "avg_hr": avg_hr,
                    "max_hr": max_hr,
                    "tachy_percentage": tachy_count / len(hr_values) * 100,
                },
            })

        # Check for bradycardia
        brady_count = sum(1 for hr in hr_values if hr < self.config.bradycardia_threshold)
        if brady_count > len(hr_values) * 0.1:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["bradycardia"],
                "name": "Bradycardia",
                "source": "wearable_heart_rate",
                "confidence": min(0.9, brady_count / len(hr_values)),
                "evidence": {
                    "avg_hr": avg_hr,
                    "min_hr": min_hr,
                    "brady_percentage": brady_count / len(hr_values) * 100,
                },
            })

        # Check for irregular rhythm
        irregular_count = sum(1 for d in data if d.is_irregular)
        if irregular_count > 0:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["irregular_heart_rhythm"],
                "name": "Irregular heart rhythm",
                "source": "wearable_heart_rate",
                "confidence": min(0.8, irregular_count / len(data) + 0.3),
                "evidence": {
                    "irregular_episodes": irregular_count,
                },
            })

        # Check HRV for autonomic dysfunction
        hrv_values = [d.hrv_rmssd for d in data if d.hrv_rmssd is not None]
        if hrv_values:
            avg_hrv = sum(hrv_values) / len(hrv_values)
            if avg_hrv < self.config.low_hrv_threshold:
                phenotypes.append({
                    "hpo_id": HPO_MAPPINGS["autonomic_dysfunction"],
                    "name": "Autonomic dysfunction",
                    "source": "wearable_hrv",
                    "confidence": 0.6,
                    "evidence": {
                        "avg_hrv_rmssd": avg_hrv,
                        "threshold": self.config.low_hrv_threshold,
                    },
                })

        return phenotypes

    def _convert_sleep(
        self,
        data: list[SleepData],
    ) -> list[dict[str, Any]]:
        """Convert sleep data to phenotypes."""
        phenotypes = []

        if len(data) < self.config.min_sleep_sessions or len(data) == 0:
            return phenotypes

        # Calculate averages (len(data) > 0 guaranteed by check above)
        avg_efficiency = sum(d.sleep_efficiency for d in data) / len(data)
        avg_deep_pct = sum(d.deep_sleep_percentage for d in data) / len(data)
        sum(d.total_duration_minutes for d in data) / len(data)
        total_wake_count = sum(d.wake_count for d in data)
        total_apnea_possible = sum(1 for d in data if d.possible_apnea)

        # Poor sleep efficiency
        if avg_efficiency < self.config.poor_sleep_efficiency:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["sleep_disturbance"],
                "name": "Sleep disturbance",
                "source": "wearable_sleep",
                "confidence": 0.7,
                "evidence": {
                    "avg_sleep_efficiency": avg_efficiency,
                    "threshold": self.config.poor_sleep_efficiency,
                    "sessions_analyzed": len(data),
                },
            })

        # Low deep sleep
        if avg_deep_pct < self.config.low_deep_sleep_percent:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["decreased_rem_sleep"],
                "name": "Decreased deep/REM sleep",
                "source": "wearable_sleep",
                "confidence": 0.6,
                "evidence": {
                    "avg_deep_sleep_percent": avg_deep_pct,
                    "threshold": self.config.low_deep_sleep_percent,
                },
            })

        # Frequent waking (insomnia pattern)
        avg_wakes = total_wake_count / len(data)
        if avg_wakes > 5:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["insomnia"],
                "name": "Insomnia",
                "source": "wearable_sleep",
                "confidence": min(0.8, avg_wakes / 10),
                "evidence": {
                    "avg_wake_episodes": avg_wakes,
                },
            })

        # Sleep apnea indicators
        if total_apnea_possible > 0:
            # Check SpO2 dips during sleep
            spo2_dips = sum(d.spo2_dips_count for d in data)
            if spo2_dips >= self.config.apnea_spo2_dip_threshold:
                phenotypes.append({
                    "hpo_id": HPO_MAPPINGS["sleep_apnea"],
                    "name": "Sleep apnea",
                    "source": "wearable_sleep",
                    "confidence": min(0.8, spo2_dips / 20 + 0.4),
                    "evidence": {
                        "spo2_dip_events": spo2_dips,
                        "sessions_with_apnea_indicator": total_apnea_possible,
                    },
                })

        return phenotypes

    def _convert_oxygen(
        self,
        data: list[OxygenData],
    ) -> list[dict[str, Any]]:
        """Convert oxygen data to phenotypes."""
        phenotypes = []

        if len(data) < self.config.min_oxygen_readings:
            return phenotypes

        spo2_values = [d.spo2_percent for d in data if d.spo2_percent > 0]
        if not spo2_values:
            return phenotypes

        avg_spo2 = sum(spo2_values) / len(spo2_values)
        min_spo2 = min(spo2_values)

        # Count low readings
        low_count = sum(1 for v in spo2_values if v < self.config.hypoxemia_threshold)
        critical_count = sum(1 for v in spo2_values if v < self.config.severe_hypoxemia_threshold)

        # Hypoxemia
        if low_count > len(spo2_values) * 0.05 or min_spo2 < self.config.severe_hypoxemia_threshold:
            confidence = 0.5
            if critical_count > 0:
                confidence = 0.8
            elif low_count > len(spo2_values) * 0.2:
                confidence = 0.7

            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["hypoxemia"],
                "name": "Hypoxemia",
                "source": "wearable_oxygen",
                "confidence": confidence,
                "evidence": {
                    "avg_spo2": avg_spo2,
                    "min_spo2": min_spo2,
                    "low_reading_count": low_count,
                    "critical_reading_count": critical_count,
                },
            })

        return phenotypes

    def _convert_ecg(
        self,
        data: list[ECGData],
    ) -> list[dict[str, Any]]:
        """Convert ECG data to phenotypes."""
        phenotypes = []

        if not data:
            return phenotypes

        # Check for AFib
        afib_count = sum(1 for d in data if d.is_atrial_fibrillation)
        if afib_count > 0:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["atrial_fibrillation"],
                "name": "Atrial fibrillation",
                "source": "wearable_ecg",
                "confidence": min(0.9, 0.5 + afib_count / len(data) * 0.5),
                "evidence": {
                    "afib_episodes": afib_count,
                    "total_recordings": len(data),
                },
            })

        # Check for irregular rhythms
        irregular_count = sum(1 for d in data if d.is_irregular)
        if irregular_count > 0 and afib_count == 0:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["arrhythmia"],
                "name": "Cardiac arrhythmia",
                "source": "wearable_ecg",
                "confidence": min(0.8, 0.4 + irregular_count / len(data) * 0.4),
                "evidence": {
                    "irregular_episodes": irregular_count,
                    "total_recordings": len(data),
                },
            })

        return phenotypes

    def _convert_activity(
        self,
        data: list[ActivityData],
    ) -> list[dict[str, Any]]:
        """Convert activity data to phenotypes."""
        phenotypes = []

        if not data:
            return phenotypes

        # Calculate averages
        avg_steps = sum(d.steps for d in data) / len(data)
        avg_sedentary = sum(d.sedentary_minutes for d in data) / len(data)

        # Low activity / fatigue indicator
        if avg_steps < self.config.low_steps_threshold:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["decreased_activity"],
                "name": "Decreased activity",
                "source": "wearable_activity",
                "confidence": 0.5,
                "evidence": {
                    "avg_daily_steps": avg_steps,
                    "threshold": self.config.low_steps_threshold,
                    "days_analyzed": len(data),
                },
            })

        # Excessive sedentary time
        if avg_sedentary > self.config.sedentary_hours_threshold * 60:
            phenotypes.append({
                "hpo_id": HPO_MAPPINGS["fatigue"],
                "name": "Fatigue",
                "source": "wearable_activity",
                "confidence": 0.4,
                "evidence": {
                    "avg_sedentary_hours": avg_sedentary / 60,
                    "threshold_hours": self.config.sedentary_hours_threshold,
                },
            })

        return phenotypes

    def _analyze_cross_data(
        self,
        session: WearableSession,
    ) -> list[dict[str, Any]]:
        """Analyze patterns across multiple data types."""
        phenotypes = []

        # Exercise intolerance: low activity + high resting HR
        if session.heart_rate_data and session.activity_data:
            resting_hrs = [d.resting_hr for d in session.heart_rate_data if d.resting_hr]
            avg_steps = sum(d.steps for d in session.activity_data) / len(session.activity_data) if session.activity_data else 0

            if resting_hrs and avg_steps < self.config.low_steps_threshold:
                avg_resting = sum(resting_hrs) / len(resting_hrs)
                if avg_resting > self.config.resting_hr_high_threshold:
                    phenotypes.append({
                        "hpo_id": HPO_MAPPINGS["exercise_intolerance"],
                        "name": "Exercise intolerance",
                        "source": "wearable_combined",
                        "confidence": 0.6,
                        "evidence": {
                            "avg_resting_hr": avg_resting,
                            "avg_daily_steps": avg_steps,
                            "analysis": "High resting HR with low activity",
                        },
                    })

        # Nocturnal hypoxemia pattern
        if session.sleep_data and session.oxygen_data:
            sleep_oxygen_issues = sum(
                1 for s in session.sleep_data
                if s.min_spo2 and s.min_spo2 < self.config.hypoxemia_threshold
            )
            if sleep_oxygen_issues > 0:
                phenotypes.append({
                    "hpo_id": HPO_MAPPINGS["desaturation"],
                    "name": "Nocturnal oxygen desaturation",
                    "source": "wearable_combined",
                    "confidence": 0.7,
                    "evidence": {
                        "nights_with_desaturation": sleep_oxygen_issues,
                        "total_nights": len(session.sleep_data),
                    },
                })

        return phenotypes


# =============================================================================
# Factory Function
# =============================================================================

def create_wearable_converter(
    config: ConverterConfig | None = None,
) -> WearableConverter:
    """Create a wearable converter instance."""
    return WearableConverter(config=config)
