"""
Differential Diagnosis Hypothesis Engine

Provides autonomous differential diagnosis generation:
- Bayesian hypothesis scoring
- Multi-factor evidence integration (phenotype, genetic, history)
- Iterative refinement through follow-up questions
- Confidence-based ranking
- Autonomous session management with pause/resume
- Event streaming for real-time updates
"""

from .models import (
    DiagnosisHypothesis,
    DiagnosisSession,
    DiagnosisState,
    DiagnosisResult,
    PatientProfile,
    EvidenceItem,
    EvidenceType,
    EvidencePolarity,
    FollowUpQuestion,
)
from .scoring import (
    BayesianScorer,
    ScoringConfig,
    create_bayesian_scorer,
)
from .engine import (
    DiagnosisEngine,
    EngineConfig,
    create_diagnosis_engine,
)
from .session import (
    SessionController,
    SessionConfig,
    SessionEvent,
    SessionEventData,
    create_session_controller,
)
from .validation import (
    is_valid_hpo_code,
    is_valid_gene_symbol,
    is_valid_disease_id,
    sanitize_hpo_codes,
    sanitize_gene_symbols,
    validate_phenotype_input,
    validate_genetic_input,
    InputValidator,
)

__all__ = [
    # Models
    "DiagnosisHypothesis",
    "DiagnosisSession",
    "DiagnosisState",
    "DiagnosisResult",
    "PatientProfile",
    "EvidenceItem",
    "EvidenceType",
    "EvidencePolarity",
    "FollowUpQuestion",
    # Scoring
    "BayesianScorer",
    "ScoringConfig",
    "create_bayesian_scorer",
    # Engine
    "DiagnosisEngine",
    "EngineConfig",
    "create_diagnosis_engine",
    # Session
    "SessionController",
    "SessionConfig",
    "SessionEvent",
    "SessionEventData",
    "create_session_controller",
    # Validation
    "is_valid_hpo_code",
    "is_valid_gene_symbol",
    "is_valid_disease_id",
    "sanitize_hpo_codes",
    "sanitize_gene_symbols",
    "validate_phenotype_input",
    "validate_genetic_input",
    "InputValidator",
]
