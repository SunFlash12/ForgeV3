"""
Medical History Models

Data models for medical history representation.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class HistoryType(str, Enum):
    """Types of medical history."""
    CONDITION = "condition"
    DIAGNOSIS = "diagnosis"
    SYMPTOM = "symptom"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    SURGERY = "surgery"
    HOSPITALIZATION = "hospitalization"
    VACCINATION = "vaccination"
    ALLERGY = "allergy"
    FAMILY = "family"
    SOCIAL = "social"
    DEVELOPMENTAL = "developmental"


class FamilyMember(str, Enum):
    """Family member relationships."""
    MOTHER = "mother"
    FATHER = "father"
    SIBLING = "sibling"
    SISTER = "sister"
    BROTHER = "brother"
    MATERNAL_GRANDMOTHER = "maternal_grandmother"
    MATERNAL_GRANDFATHER = "maternal_grandfather"
    PATERNAL_GRANDMOTHER = "paternal_grandmother"
    PATERNAL_GRANDFATHER = "paternal_grandfather"
    AUNT = "aunt"
    UNCLE = "uncle"
    COUSIN = "cousin"
    CHILD = "child"
    OTHER = "other"


@dataclass
class HistoryItem:
    """
    A medical history item.

    Represents conditions, diagnoses, symptoms, or other
    historical medical information.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    history_type: HistoryType = HistoryType.CONDITION
    description: str = ""

    # Coding
    icd10_code: str | None = None
    snomed_code: str | None = None
    hpo_code: str | None = None

    # Timing
    onset_date: date | None = None
    resolution_date: date | None = None
    age_at_onset: int | None = None
    is_current: bool = True

    # Clinical details
    severity: str | None = None  # mild, moderate, severe
    laterality: str | None = None  # left, right, bilateral
    body_site: str | None = None

    # Status
    is_negated: bool = False  # Patient does NOT have this
    is_confirmed: bool = False
    confidence: float = 1.0

    # Source
    source: str | None = None  # EHR, patient_reported, family
    recorded_at: datetime = field(default_factory=_utc_now)

    # Family history specific
    family_member: FamilyMember | None = None
    family_member_detail: str | None = None  # e.g., "maternal aunt"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "history_type": self.history_type.value,
            "description": self.description,
            "icd10_code": self.icd10_code,
            "snomed_code": self.snomed_code,
            "hpo_code": self.hpo_code,
            "onset_date": self.onset_date.isoformat() if self.onset_date else None,
            "age_at_onset": self.age_at_onset,
            "is_current": self.is_current,
            "severity": self.severity,
            "is_negated": self.is_negated,
            "confidence": self.confidence,
            "family_member": self.family_member.value if self.family_member else None,
        }


@dataclass
class MedicationRecord:
    """
    A medication record.

    Tracks current and past medications with dosing.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    medication_name: str = ""
    generic_name: str | None = None

    # Coding
    rxnorm_code: str | None = None
    ndc_code: str | None = None
    atc_code: str | None = None

    # Dosing
    dose: str | None = None
    dose_unit: str | None = None
    frequency: str | None = None
    route: str | None = None  # oral, IV, topical, etc.

    # Timing
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = True

    # Clinical
    indication: str | None = None  # Why prescribed
    prescriber: str | None = None

    # Status
    is_prn: bool = False  # As needed
    adherence: str | None = None  # good, poor, unknown

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "medication_name": self.medication_name,
            "generic_name": self.generic_name,
            "rxnorm_code": self.rxnorm_code,
            "dose": self.dose,
            "frequency": self.frequency,
            "route": self.route,
            "is_current": self.is_current,
            "indication": self.indication,
        }


@dataclass
class ProcedureRecord:
    """
    A procedure or surgery record.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    procedure_name: str = ""
    procedure_type: str = "procedure"  # procedure, surgery, test

    # Coding
    cpt_code: str | None = None
    icd10_pcs_code: str | None = None
    snomed_code: str | None = None

    # Timing
    procedure_date: date | None = None
    age_at_procedure: int | None = None

    # Clinical
    body_site: str | None = None
    laterality: str | None = None
    indication: str | None = None
    outcome: str | None = None
    complications: list[str] = field(default_factory=list)

    # Provider
    facility: str | None = None
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "procedure_name": self.procedure_name,
            "procedure_type": self.procedure_type,
            "cpt_code": self.cpt_code,
            "procedure_date": self.procedure_date.isoformat() if self.procedure_date else None,
            "body_site": self.body_site,
            "outcome": self.outcome,
            "complications": self.complications,
        }


@dataclass
class HistoryTimeline:
    """
    Complete medical history timeline.

    Aggregates all history types into a chronological view.
    """
    patient_id: str = ""

    # Demographics
    birth_date: date | None = None
    sex: str | None = None

    # History components
    conditions: list[HistoryItem] = field(default_factory=list)
    family_history: list[HistoryItem] = field(default_factory=list)
    medications: list[MedicationRecord] = field(default_factory=list)
    procedures: list[ProcedureRecord] = field(default_factory=list)
    allergies: list[HistoryItem] = field(default_factory=list)
    social_history: list[HistoryItem] = field(default_factory=list)

    # Developmental (for pediatric)
    developmental_history: list[HistoryItem] = field(default_factory=list)

    # Computed
    created_at: datetime = field(default_factory=_utc_now)

    @property
    def current_conditions(self) -> list[HistoryItem]:
        """Get current/active conditions."""
        return [c for c in self.conditions if c.is_current and not c.is_negated]

    @property
    def current_medications(self) -> list[MedicationRecord]:
        """Get current medications."""
        return [m for m in self.medications if m.is_current]

    @property
    def condition_codes(self) -> list[str]:
        """Get all ICD-10 codes."""
        return [c.icd10_code for c in self.conditions if c.icd10_code]

    @property
    def phenotype_codes(self) -> list[str]:
        """Get all HPO codes."""
        codes = []
        for c in self.conditions:
            if c.hpo_code:
                codes.append(c.hpo_code)
        return codes

    def get_family_history_for(self, condition: str) -> list[HistoryItem]:
        """Get family history items matching a condition."""
        condition_lower = condition.lower()
        return [
            fh for fh in self.family_history
            if condition_lower in fh.description.lower()
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "sex": self.sex,
            "conditions": [c.to_dict() for c in self.conditions],
            "family_history": [fh.to_dict() for fh in self.family_history],
            "medications": [m.to_dict() for m in self.medications],
            "procedures": [p.to_dict() for p in self.procedures],
            "allergies": [a.to_dict() for a in self.allergies],
            "current_condition_count": len(self.current_conditions),
            "current_medication_count": len(self.current_medications),
        }
