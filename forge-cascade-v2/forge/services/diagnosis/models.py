"""
Diagnosis Engine Models

Data models for differential diagnosis generation and session management.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(UTC)


class DiagnosisState(str, Enum):
    """State of a diagnosis session."""
    INTAKE = "intake"           # Gathering initial information
    ANALYZING = "analyzing"     # Processing initial data
    QUESTIONING = "questioning" # Asking follow-up questions
    REFINING = "refining"       # Refining hypotheses
    COMPLETE = "complete"       # Diagnosis complete
    PAUSED = "paused"           # Session paused by user
    EXPIRED = "expired"         # Session timed out


class EvidenceType(str, Enum):
    """Type of clinical evidence."""
    PHENOTYPE = "phenotype"     # HPO phenotype
    GENETIC = "genetic"         # Genetic variant
    LABORATORY = "laboratory"   # Lab test result
    IMAGING = "imaging"         # Imaging finding
    HISTORY = "history"         # Medical history
    FAMILY = "family"           # Family history
    MEDICATION = "medication"   # Current medications
    PROCEDURE = "procedure"     # Surgical/procedural history
    WEARABLE = "wearable"       # Wearable device data
    OTHER = "other"


class EvidencePolarity(str, Enum):
    """Whether evidence supports or refutes a hypothesis."""
    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass
class EvidenceItem:
    """
    A piece of clinical evidence.

    Could be a phenotype, genetic variant, lab result, etc.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    evidence_type: EvidenceType = EvidenceType.OTHER
    value: str = ""                  # The evidence value/description
    code: str | None = None          # Standardized code (HPO, LOINC, etc.)
    source: str | None = None        # Where this evidence came from

    # Clinical context
    negated: bool = False            # Evidence is absent/negative
    severity: str | None = None
    onset: str | None = None         # Age of onset
    progression: str | None = None

    # Confidence
    confidence: float = 1.0          # How certain we are about this evidence
    confirmed: bool = False          # Explicitly confirmed by user

    # Timestamps
    observed_at: datetime | None = None
    recorded_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "evidence_type": self.evidence_type.value,
            "value": self.value,
            "code": self.code,
            "negated": self.negated,
            "severity": self.severity,
            "confidence": self.confidence,
            "confirmed": self.confirmed,
        }


@dataclass
class DiagnosisHypothesis:
    """
    A candidate diagnosis hypothesis.

    Contains the disease, supporting/refuting evidence, and scores.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    disease_id: str = ""              # MONDO or OMIM ID
    disease_name: str = ""
    description: str | None = None

    # Scores
    prior_probability: float = 0.001   # Base prevalence
    posterior_probability: float = 0.0  # After evidence
    phenotype_score: float = 0.0       # From phenotype matching
    genetic_score: float = 0.0         # From genetic evidence
    history_score: float = 0.0         # From medical history
    combined_score: float = 0.0        # Final weighted score

    # Evidence
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    refuting_evidence: list[EvidenceItem] = field(default_factory=list)
    neutral_evidence: list[EvidenceItem] = field(default_factory=list)

    # Phenotype details
    matched_phenotypes: list[str] = field(default_factory=list)
    expected_phenotypes: list[str] = field(default_factory=list)
    missing_phenotypes: list[str] = field(default_factory=list)

    # Genetic details
    associated_genes: list[str] = field(default_factory=list)
    found_variants: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    rank: int = 0
    confidence_interval: tuple[float, float] | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    @property
    def evidence_strength(self) -> str:
        """Categorize evidence strength."""
        if self.combined_score >= 0.8:
            return "strong"
        elif self.combined_score >= 0.5:
            return "moderate"
        elif self.combined_score >= 0.2:
            return "weak"
        else:
            return "minimal"

    @property
    def support_count(self) -> int:
        """Number of supporting evidence items."""
        return len(self.supporting_evidence)

    @property
    def refute_count(self) -> int:
        """Number of refuting evidence items."""
        return len(self.refuting_evidence)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "disease_id": self.disease_id,
            "disease_name": self.disease_name,
            "description": self.description,
            "combined_score": self.combined_score,
            "phenotype_score": self.phenotype_score,
            "genetic_score": self.genetic_score,
            "history_score": self.history_score,
            "posterior_probability": self.posterior_probability,
            "matched_phenotypes": self.matched_phenotypes,
            "missing_phenotypes": self.missing_phenotypes,
            "associated_genes": self.associated_genes,
            "evidence_strength": self.evidence_strength,
            "rank": self.rank,
            "supporting_evidence_count": self.support_count,
            "refuting_evidence_count": self.refute_count,
        }


@dataclass
class FollowUpQuestion:
    """
    A follow-up question to refine the diagnosis.

    Generated to discriminate between top hypotheses.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    question_text: str = ""
    question_type: str = "binary"    # binary, multiple_choice, free_text, numeric

    # What this question is about
    target_phenotype: str | None = None  # HPO ID if asking about phenotype
    target_evidence: str | None = None   # Evidence type

    # Answer options for multiple choice
    options: list[dict[str, Any]] = field(default_factory=list)

    # Expected impact
    hypotheses_affected: list[str] = field(default_factory=list)  # Hypothesis IDs
    information_gain: float = 0.0        # Expected info gain if answered
    priority: int = 1                    # 1 = highest priority

    # Answer (when filled)
    answer: str | None = None
    answered_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "target_phenotype": self.target_phenotype,
            "options": self.options,
            "information_gain": self.information_gain,
            "priority": self.priority,
            "answer": self.answer,
        }


@dataclass
class PatientProfile:
    """
    Patient information for diagnosis.

    Contains demographics, history, and collected evidence.
    """
    id: str = field(default_factory=lambda: str(uuid4()))

    # Demographics
    age: int | None = None
    age_of_onset: int | None = None
    sex: str | None = None           # "male", "female", "other"
    ethnicity: str | None = None

    # Clinical data
    phenotypes: list[EvidenceItem] = field(default_factory=list)
    genetic_variants: list[EvidenceItem] = field(default_factory=list)
    laboratory_results: list[EvidenceItem] = field(default_factory=list)
    imaging_findings: list[EvidenceItem] = field(default_factory=list)

    # History
    medical_history: list[EvidenceItem] = field(default_factory=list)
    family_history: list[EvidenceItem] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)

    # Wearable data
    wearable_data: list[EvidenceItem] = field(default_factory=list)

    # Known diagnoses (to exclude or prioritize)
    existing_diagnoses: list[str] = field(default_factory=list)

    @property
    def all_evidence(self) -> list[EvidenceItem]:
        """Get all evidence items."""
        return (
            self.phenotypes +
            self.genetic_variants +
            self.laboratory_results +
            self.imaging_findings +
            self.medical_history +
            self.family_history +
            self.wearable_data
        )

    @property
    def phenotype_codes(self) -> list[str]:
        """Get all HPO codes."""
        return [
            e.code for e in self.phenotypes
            if e.code and not e.negated
        ]

    @property
    def negated_phenotype_codes(self) -> list[str]:
        """Get all negated HPO codes."""
        return [
            e.code for e in self.phenotypes
            if e.code and e.negated
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "age": self.age,
            "age_of_onset": self.age_of_onset,
            "sex": self.sex,
            "phenotype_count": len(self.phenotypes),
            "genetic_variant_count": len(self.genetic_variants),
            "existing_diagnoses": self.existing_diagnoses,
            "medications": self.medications,
        }


@dataclass
class DiagnosisSession:
    """
    An autonomous diagnosis session.

    Tracks state, hypotheses, questions, and user interactions.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    state: DiagnosisState = DiagnosisState.INTAKE
    patient: PatientProfile = field(default_factory=PatientProfile)

    # Hypotheses
    hypotheses: list[DiagnosisHypothesis] = field(default_factory=list)
    top_hypotheses: list[DiagnosisHypothesis] = field(default_factory=list)

    # Questions
    pending_questions: list[FollowUpQuestion] = field(default_factory=list)
    answered_questions: list[FollowUpQuestion] = field(default_factory=list)

    # Session history
    iterations: int = 0
    max_iterations: int = 10
    events: list[dict[str, Any]] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    expires_at: datetime | None = None

    # Configuration
    auto_advance: bool = True        # Automatically advance state
    confidence_threshold: float = 0.7  # Threshold to consider diagnosis confident
    max_questions: int = 20          # Max follow-up questions

    @property
    def is_complete(self) -> bool:
        """Check if diagnosis is complete."""
        return self.state == DiagnosisState.COMPLETE

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.state not in {
            DiagnosisState.COMPLETE,
            DiagnosisState.EXPIRED,
        }

    @property
    def top_diagnosis(self) -> DiagnosisHypothesis | None:
        """Get the top diagnosis hypothesis."""
        if self.top_hypotheses:
            return self.top_hypotheses[0]
        return None

    @property
    def is_confident(self) -> bool:
        """Check if we're confident in the top diagnosis."""
        if not self.top_diagnosis:
            return False
        return self.top_diagnosis.combined_score >= self.confidence_threshold

    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Add an event to session history."""
        self.events.append({
            "type": event_type,
            "data": data,
            "timestamp": _utc_now().isoformat(),
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "state": self.state.value,
            "iterations": self.iterations,
            "hypotheses_count": len(self.hypotheses),
            "top_hypotheses": [h.to_dict() for h in self.top_hypotheses[:5]],
            "pending_questions": [q.to_dict() for q in self.pending_questions[:3]],
            "answered_questions_count": len(self.answered_questions),
            "is_confident": self.is_confident,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DiagnosisResult:
    """
    Final diagnosis result.

    Produced when a session completes.
    """
    session_id: str
    patient_id: str | None = None

    # Primary diagnosis
    primary_diagnosis: DiagnosisHypothesis | None = None
    confidence: float = 0.0

    # Differential
    differential: list[DiagnosisHypothesis] = field(default_factory=list)

    # Summary
    supporting_evidence_summary: str | None = None
    key_findings: list[str] = field(default_factory=list)
    recommended_tests: list[str] = field(default_factory=list)

    # Metadata
    iterations: int = 0
    questions_asked: int = 0
    evidence_count: int = 0

    # Timestamps
    completed_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "patient_id": self.patient_id,
            "primary_diagnosis": self.primary_diagnosis.to_dict() if self.primary_diagnosis else None,
            "confidence": self.confidence,
            "differential": [h.to_dict() for h in self.differential[:10]],
            "key_findings": self.key_findings,
            "recommended_tests": self.recommended_tests,
            "iterations": self.iterations,
            "questions_asked": self.questions_asked,
            "evidence_count": self.evidence_count,
            "completed_at": self.completed_at.isoformat(),
        }
