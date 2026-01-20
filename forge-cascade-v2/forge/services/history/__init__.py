"""
Medical History Processing Module

Provides extraction and analysis of medical history:
- Clinical history parsing
- Family history extraction
- Medication history analysis
- Procedure/surgical history
- ICD-10/SNOMED coding
"""

from .models import (
    HistoryItem,
    HistoryType,
    FamilyMember,
    MedicationRecord,
    ProcedureRecord,
    HistoryTimeline,
)
from .extractor import (
    HistoryExtractor,
    create_history_extractor,
)
from .analyzer import (
    HistoryAnalyzer,
    create_history_analyzer,
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
