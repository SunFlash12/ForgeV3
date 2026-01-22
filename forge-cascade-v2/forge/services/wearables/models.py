"""
Wearable Data Models

Data models for wearable device readings.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(UTC)


class WearableDataType(str, Enum):
    """Types of wearable data."""
    HEART_RATE = "heart_rate"
    HRV = "hrv"  # Heart rate variability
    SLEEP = "sleep"
    ACTIVITY = "activity"
    STEPS = "steps"
    OXYGEN = "oxygen"  # SpO2
    ECG = "ecg"
    BLOOD_PRESSURE = "blood_pressure"
    TEMPERATURE = "temperature"
    GLUCOSE = "glucose"
    RESPIRATORY_RATE = "respiratory_rate"


class SleepStage(str, Enum):
    """Sleep stages."""
    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"
    UNKNOWN = "unknown"


class ActivityType(str, Enum):
    """Activity types."""
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    VIGOROUS = "vigorous"
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    SLEEP = "sleep"
    OTHER = "other"


@dataclass
class WearableReading:
    """
    Base class for wearable readings.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    data_type: WearableDataType = WearableDataType.HEART_RATE
    timestamp: datetime = field(default_factory=_utc_now)
    value: float = 0.0
    unit: str = ""

    # Quality indicators
    confidence: float = 1.0  # Device confidence in reading
    is_valid: bool = True

    # Device info
    device_type: str | None = None  # Apple Watch, Fitbit, etc.
    device_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "data_type": self.data_type.value,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "confidence": self.confidence,
        }


@dataclass
class HeartRateData:
    """
    Heart rate and HRV data.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=_utc_now)

    # Heart rate
    bpm: int = 0
    resting_hr: int | None = None

    # HRV metrics
    hrv_rmssd: float | None = None  # Root mean square of successive differences
    hrv_sdnn: float | None = None   # Standard deviation of NN intervals
    hrv_pnn50: float | None = None  # Percentage of successive differences > 50ms

    # Context
    activity_level: str | None = None  # resting, active, exercise
    is_resting: bool = False

    # Abnormality flags
    is_irregular: bool = False
    is_tachycardia: bool = False  # HR > 100
    is_bradycardia: bool = False  # HR < 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "bpm": self.bpm,
            "resting_hr": self.resting_hr,
            "hrv_rmssd": self.hrv_rmssd,
            "is_irregular": self.is_irregular,
            "is_tachycardia": self.is_tachycardia,
            "is_bradycardia": self.is_bradycardia,
        }


@dataclass
class SleepData:
    """
    Sleep tracking data.
    """
    id: str = field(default_factory=lambda: str(uuid4()))

    # Timing
    sleep_start: datetime | None = None
    sleep_end: datetime | None = None
    total_duration_minutes: int = 0

    # Stages
    awake_minutes: int = 0
    light_minutes: int = 0
    deep_minutes: int = 0
    rem_minutes: int = 0

    # Quality metrics
    sleep_efficiency: float = 0.0  # Time asleep / time in bed
    wake_count: int = 0  # Number of wake episodes
    sleep_latency_minutes: int = 0  # Time to fall asleep

    # Heart rate during sleep
    avg_hr_sleeping: int | None = None
    min_hr_sleeping: int | None = None

    # Oxygen during sleep
    avg_spo2: float | None = None
    min_spo2: float | None = None
    spo2_dips_count: int = 0  # Oxygen desaturation events

    # Abnormality flags
    has_sleep_disturbance: bool = False
    possible_apnea: bool = False

    @property
    def deep_sleep_percentage(self) -> float:
        if self.total_duration_minutes == 0:
            return 0.0
        return self.deep_minutes / self.total_duration_minutes * 100

    @property
    def rem_percentage(self) -> float:
        if self.total_duration_minutes == 0:
            return 0.0
        return self.rem_minutes / self.total_duration_minutes * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "sleep_start": self.sleep_start.isoformat() if self.sleep_start else None,
            "sleep_end": self.sleep_end.isoformat() if self.sleep_end else None,
            "total_duration_minutes": self.total_duration_minutes,
            "deep_minutes": self.deep_minutes,
            "rem_minutes": self.rem_minutes,
            "sleep_efficiency": self.sleep_efficiency,
            "wake_count": self.wake_count,
            "possible_apnea": self.possible_apnea,
            "spo2_dips_count": self.spo2_dips_count,
        }


@dataclass
class ActivityData:
    """
    Activity and motion data.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    date: datetime = field(default_factory=_utc_now)

    # Steps
    steps: int = 0
    distance_meters: float = 0.0
    floors_climbed: int = 0

    # Active time
    sedentary_minutes: int = 0
    light_active_minutes: int = 0
    moderate_active_minutes: int = 0
    vigorous_active_minutes: int = 0

    # Energy
    calories_burned: int = 0
    active_calories: int = 0

    # Exercise
    exercise_count: int = 0
    exercise_types: list[str] = field(default_factory=list)
    exercise_minutes: int = 0

    # Movement metrics
    avg_daily_steps_30d: int | None = None  # 30-day average

    # Abnormality flags
    is_unusually_inactive: bool = False
    is_unusually_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "steps": self.steps,
            "distance_meters": self.distance_meters,
            "active_minutes": self.light_active_minutes + self.moderate_active_minutes + self.vigorous_active_minutes,
            "calories_burned": self.calories_burned,
            "exercise_minutes": self.exercise_minutes,
        }


@dataclass
class OxygenData:
    """
    Blood oxygen (SpO2) data.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=_utc_now)

    # Reading
    spo2_percent: float = 0.0

    # Context
    is_sleeping: bool = False
    altitude_meters: float | None = None

    # Abnormality flags
    is_low: bool = False  # < 95%
    is_critical: bool = False  # < 90%

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "spo2_percent": self.spo2_percent,
            "is_low": self.is_low,
            "is_critical": self.is_critical,
        }


@dataclass
class ECGData:
    """
    ECG recording data.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=_utc_now)

    # Recording
    duration_seconds: float = 0.0
    sample_rate_hz: int = 0
    samples: list[float] = field(default_factory=list)

    # Analysis results
    avg_heart_rate: int = 0
    classification: str = "unknown"  # sinus_rhythm, afib, inconclusive

    # Rhythm flags
    is_sinus_rhythm: bool = False
    is_atrial_fibrillation: bool = False
    is_irregular: bool = False
    has_artifact: bool = False

    # Intervals (if available)
    pr_interval_ms: float | None = None
    qrs_duration_ms: float | None = None
    qt_interval_ms: float | None = None
    qtc_interval_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "avg_heart_rate": self.avg_heart_rate,
            "classification": self.classification,
            "is_atrial_fibrillation": self.is_atrial_fibrillation,
            "is_irregular": self.is_irregular,
        }


@dataclass
class WearableSession:
    """
    A session of wearable data for analysis.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    patient_id: str = ""

    # Time range
    start_time: datetime = field(default_factory=_utc_now)
    end_time: datetime | None = None

    # Data collections
    heart_rate_data: list[HeartRateData] = field(default_factory=list)
    sleep_data: list[SleepData] = field(default_factory=list)
    activity_data: list[ActivityData] = field(default_factory=list)
    oxygen_data: list[OxygenData] = field(default_factory=list)
    ecg_data: list[ECGData] = field(default_factory=list)

    # Device info
    devices: list[str] = field(default_factory=list)

    # Analysis results (populated after analysis)
    abnormalities: list[dict[str, Any]] = field(default_factory=list)
    phenotypes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> timedelta | None:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def has_heart_data(self) -> bool:
        return len(self.heart_rate_data) > 0

    @property
    def has_sleep_data(self) -> bool:
        return len(self.sleep_data) > 0

    @property
    def has_ecg_data(self) -> bool:
        return len(self.ecg_data) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "data_summary": {
                "heart_rate_readings": len(self.heart_rate_data),
                "sleep_sessions": len(self.sleep_data),
                "activity_days": len(self.activity_data),
                "oxygen_readings": len(self.oxygen_data),
                "ecg_recordings": len(self.ecg_data),
            },
            "devices": self.devices,
            "abnormalities_count": len(self.abnormalities),
            "phenotypes_count": len(self.phenotypes),
        }
