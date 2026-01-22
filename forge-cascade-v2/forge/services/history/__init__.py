"""
Medical History Processing Module

Provides extraction and analysis of medical history:
- Clinical history parsing
- Family history extraction
- Medication history analysis
- Procedure/surgical history
- ICD-10/SNOMED coding
"""

from .analyzer import (
    HistoryAnalyzer,
    create_history_analyzer,
)
from .extractor import (
    HistoryExtractor,
    create_history_extractor,
)
from .models import (
    FamilyMember,
    HistoryItem,
    HistoryTimeline,
    HistoryType,
    MedicationRecord,
    ProcedureRecord,
)

__all__ = [
    # Models
    "HistoryItem",
    "HistoryType",
    "FamilyMember",
    "MedicationRecord",
    "ProcedureRecord",
    "HistoryTimeline",
    # Services
    "HistoryExtractor",
    "create_history_extractor",
    "HistoryAnalyzer",
    "create_history_analyzer",
]
