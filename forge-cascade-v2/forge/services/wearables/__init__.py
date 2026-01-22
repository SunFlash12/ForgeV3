"""
Wearable Data Integration Module

Provides wearable device data processing:
- Heart rate and HRV analysis
- Sleep pattern analysis
- Activity and motion data
- Blood oxygen (SpO2) analysis
- ECG rhythm analysis
- Phenotype conversion for diagnosis
"""

from .analyzer import (
    WearableAnalyzer,
    create_wearable_analyzer,
)
from .converter import (
    WearableConverter,
    create_wearable_converter,
)
from .models import (
    ActivityData,
    ECGData,
    HeartRateData,
    OxygenData,
    SleepData,
    WearableDataType,
    WearableReading,
    WearableSession,
)

__all__ = [
    # Models
    "WearableDataType",
    "WearableReading",
    "HeartRateData",
    "SleepData",
    "ActivityData",
    "OxygenData",
    "ECGData",
    "WearableSession",
    # Services
    "WearableConverter",
    "create_wearable_converter",
    "WearableAnalyzer",
    "create_wearable_analyzer",
]
