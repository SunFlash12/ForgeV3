"""
Diagnosis API Routes

REST endpoints for the differential diagnosis hypothesis engine.
"""

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    get_current_active_user,
)
from forge.services.diagnosis.validation import (
    validate_genetic_input,
    validate_phenotype_input,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


def _handle_internal_error(e: Exception, context: str) -> HTTPException:  # noqa: ARG001
    """Log internal error and return sanitized HTTPException."""
    logger.error(
        "diagnosis_api_error",
        context=context,
        error_type=type(e).__name__,
        error=str(e),
        exc_info=True,
    )
    return HTTPException(
        status_code=500,
        detail=f"Internal error during {context}. Please try again or contact support.",
    )


# =============================================================================
# Request/Response Models
# =============================================================================


class PhenotypeInput(BaseModel):
    """A phenotype input."""

    code: str | None = Field(None, description="HPO code (e.g., HP:0001250)")
    value: str | None = Field(None, description="Text description")
    negated: bool = Field(False, description="Whether phenotype is absent")
    severity: str | None = Field(None, description="Severity: mild, moderate, severe")


class GeneticVariantInput(BaseModel):
    """A genetic variant input."""

    notation: str | None = Field(None, description="Variant notation (e.g., NM_000546.6:c.215C>G)")
    gene_symbol: str | None = Field(None, description="Gene symbol (e.g., BRCA1)")
    pathogenicity: str | None = Field(None, description="Pathogenicity classification")
    zygosity: str | None = Field(None, description="Zygosity: heterozygous, homozygous")


class PatientDemographics(BaseModel):
    """Patient demographics."""

    age: int | None = Field(None, description="Current age in years")
    age_of_onset: int | None = Field(None, description="Age at symptom onset")
    sex: str | None = Field(None, description="Sex: male, female, other")
    ethnicity: str | None = Field(None, description="Ethnicity")


class CreateSessionRequest(BaseModel):
    """Request to create a diagnosis session."""

    patient_id: str | None = Field(None, description="Optional patient ID")
    auto_advance: bool = Field(True, description="Auto-advance through diagnosis states")


class StartDiagnosisRequest(BaseModel):
    """Request to start diagnosis with initial data."""

    phenotypes: list[str | PhenotypeInput] = Field(
        default=[], description="Phenotypes (HPO codes or descriptions)"
    )
    genetic_variants: list[GeneticVariantInput] = Field(default=[], description="Genetic variants")
    medical_history: list[str] = Field(default=[], description="Medical history items")
    family_history: list[str] = Field(default=[], description="Family history items")
    demographics: PatientDemographics | None = Field(None, description="Patient demographics")


class AnswerQuestionRequest(BaseModel):
    """Request to answer follow-up questions."""

    answers: list[dict[str, Any]] = Field(
        ..., description="List of {question_id, answer, additional_info}"
    )


class SessionResponse(BaseModel):
    """Session state response."""

    session_id: str
    state: str
    is_complete: bool
    is_confident: bool
    iteration: int
    hypotheses_count: int
    top_hypotheses: list[dict[str, Any]]
    pending_questions: list[dict[str, Any]]
    answered_questions_count: int


class DiagnosisResultResponse(BaseModel):
    """Final diagnosis result response."""

    session_id: str
    primary_diagnosis: dict[str, Any] | None
    confidence: float
    differential: list[dict[str, Any]]
    key_findings: list[str]
    recommended_tests: list[str]
    iterations: int
    questions_asked: int


class MultiAgentDiagnosisRequest(BaseModel):
    """Request for multi-agent diagnosis."""

    phenotypes: list[str | PhenotypeInput] = Field(default=[], description="Phenotypes")
    genetic_variants: list[GeneticVariantInput] = Field(default=[], description="Genetic variants")
    medical_history: list[str] = Field(default=[], description="Medical history")
    family_history: list[str] = Field(default=[], description="Family history")
    demographics: PatientDemographics | None = None
    wearable_data: list[dict[str, Any]] = Field(default=[], description="Wearable device data")


# =============================================================================
# Dependency Injection (Thread-Safe Singleton)
# =============================================================================

import threading


class _DiagnosisServices:
    """Thread-safe singleton for diagnosis services."""

    _instance: "_DiagnosisServices | None" = None
    _lock: threading.Lock = threading.Lock()
    _session_controller: Any
    _diagnostic_coordinator: Any
    _initialized: bool

    def __new__(cls) -> "_DiagnosisServices":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._session_controller = None
                    cls._instance._diagnostic_coordinator = None
                    cls._instance._initialized = False
        return cls._instance

    def initialize(self, session_controller: Any, diagnostic_coordinator: Any) -> None:
        """Thread-safe initialization."""
        with self._lock:
            self._session_controller = session_controller
            self._diagnostic_coordinator = diagnostic_coordinator
            self._initialized = True

    @property
    def session_controller(self) -> Any:
        return self._session_controller

    @property
    def diagnostic_coordinator(self) -> Any:
        return self._diagnostic_coordinator

    @property
    def is_initialized(self) -> bool:
        return self._initialized


_services = _DiagnosisServices()


def get_session_controller() -> Any:
    """Get the session controller."""
    if not _services.is_initialized or _services.session_controller is None:
        raise HTTPException(status_code=503, detail="Diagnosis service not initialized")
    return _services.session_controller


def get_diagnostic_coordinator() -> Any:
    """Get the diagnostic coordinator."""
    if not _services.is_initialized or _services.diagnostic_coordinator is None:
        raise HTTPException(status_code=503, detail="Multi-agent diagnosis not initialized")
    return _services.diagnostic_coordinator


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="Create a new diagnosis session",
    description="Create a new autonomous diagnosis session.",
)
async def create_session(
    request: CreateSessionRequest,  # noqa: ARG001
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Create a new diagnosis session."""
    try:
        session = await controller.create_session(
            patient=None,  # Will be populated during start
        )

        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )

    except (RuntimeError, ValueError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "session creation")


@router.post(
    "/sessions/{session_id}/start",
    response_model=SessionResponse,
    summary="Start diagnosis with initial data",
    description="Start the diagnosis process with initial patient data.",
)
async def start_diagnosis(
    session_id: str,
    request: StartDiagnosisRequest,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Start diagnosis with initial intake data."""
    try:
        # Convert and validate phenotype inputs
        raw_phenotypes: list[str | dict[str, Any]] = []
        for p in request.phenotypes:
            if isinstance(p, str):
                raw_phenotypes.append(p)
            else:
                raw_phenotypes.append({"code": p.code, "value": p.value})

        # Validate phenotypes - separates HPO codes from text descriptions
        hpo_codes, text_descriptions = validate_phenotype_input(raw_phenotypes)
        phenotypes = hpo_codes + text_descriptions

        # Convert and validate genetic inputs
        raw_variants = [
            {
                "notation": v.notation,
                "gene_symbol": v.gene_symbol,
                "pathogenicity": v.pathogenicity,
                "zygosity": v.zygosity,
            }
            for v in request.genetic_variants
        ]
        genetic_variants = validate_genetic_input(raw_variants)

        demographics = None
        if request.demographics:
            demographics = {
                "age": request.demographics.age,
                "age_of_onset": request.demographics.age_of_onset,
                "sex": request.demographics.sex,
                "ethnicity": request.demographics.ethnicity,
            }

        session = await controller.start_diagnosis(
            session_id=session_id,
            phenotypes=phenotypes,
            genetic_variants=genetic_variants,
            medical_history=request.medical_history,
            family_history=request.family_history,
            demographics=demographics,
        )

        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )

    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")
    except (RuntimeError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "starting diagnosis")


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get session status",
    description="Get the current status of a diagnosis session.",
)
async def get_session(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Get session status."""
    session = controller.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        session_id=session.id,
        state=session.state.value,
        is_complete=session.is_complete,
        is_confident=session.is_confident,
        iteration=session.iterations,
        hypotheses_count=len(session.hypotheses),
        top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
        pending_questions=[q.to_dict() for q in session.pending_questions],
        answered_questions_count=len(session.answered_questions),
    )


@router.post(
    "/sessions/{session_id}/answer",
    response_model=SessionResponse,
    summary="Answer follow-up questions",
    description="Submit answers to pending follow-up questions.",
)
async def answer_questions(
    session_id: str,
    request: AnswerQuestionRequest,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Answer follow-up questions."""
    try:
        session = await controller.answer_questions(
            session_id=session_id,
            answers=request.answers,
        )

        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )

    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")
    except (RuntimeError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "answering questions")


@router.post(
    "/sessions/{session_id}/skip",
    response_model=SessionResponse,
    summary="Skip pending questions",
    description="Skip pending questions and finalize with current evidence.",
)
async def skip_questions(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Skip questions and finalize."""
    try:
        session = await controller.skip_questions(session_id)

        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )

    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")
    except (RuntimeError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "skipping questions")


@router.post(
    "/sessions/{session_id}/pause",
    response_model=SessionResponse,
    summary="Pause session",
)
async def pause_session(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Pause a running session."""
    try:
        session = await controller.pause_session(session_id)
        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )
    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")


@router.post(
    "/sessions/{session_id}/resume",
    response_model=SessionResponse,
    summary="Resume session",
)
async def resume_session(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> SessionResponse:
    """Resume a paused session."""
    try:
        session = await controller.resume_session(session_id)
        return SessionResponse(
            session_id=session.id,
            state=session.state.value,
            is_complete=session.is_complete,
            is_confident=session.is_confident,
            iteration=session.iterations,
            hypotheses_count=len(session.hypotheses),
            top_hypotheses=[h.to_dict() for h in session.top_hypotheses[:5]],
            pending_questions=[q.to_dict() for q in session.pending_questions],
            answered_questions_count=len(session.answered_questions),
        )
    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")


@router.get(
    "/sessions/{session_id}/result",
    response_model=DiagnosisResultResponse,
    summary="Get final diagnosis result",
    description="Get the final diagnosis result for a completed session.",
)
async def get_result(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> DiagnosisResultResponse:
    """Get final diagnosis result."""
    try:
        result = await controller.get_result(session_id)

        return DiagnosisResultResponse(
            session_id=result.session_id,
            primary_diagnosis=result.primary_diagnosis.to_dict()
            if result.primary_diagnosis
            else None,
            confidence=result.confidence,
            differential=[h.to_dict() for h in result.differential],
            key_findings=result.key_findings,
            recommended_tests=result.recommended_tests,
            iterations=result.iterations,
            questions_asked=result.questions_asked,
        )

    except ValueError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail="Resource not found")
    except (RuntimeError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "getting result")


@router.get(
    "/sessions/{session_id}/stream",
    summary="Stream session events",
    description="Stream real-time events for a diagnosis session using SSE.",
)
async def stream_events(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> StreamingResponse:
    """Stream session events via Server-Sent Events."""
    from collections.abc import AsyncGenerator

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in controller.stream_events(session_id):
                yield f"data: {json.dumps(event.to_dict())}\n\n"
        except ValueError as e:
            # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details
            logger.error("Stream event error for session %s: %s", session_id, e)
            yield f"data: {json.dumps({'error': 'Stream processing failed'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete(
    "/sessions/{session_id}",
    summary="Delete session",
)
async def delete_session(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    controller: Any = Depends(get_session_controller),  # noqa: B008
) -> dict[str, str]:
    """Delete a diagnosis session."""
    deleted = await controller.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


# =============================================================================
# Multi-Agent Diagnosis Endpoints
# =============================================================================


@router.post(
    "/multi-agent/diagnose",
    summary="Run multi-agent diagnosis",
    description="Run a full multi-agent collaborative diagnosis.",
)
async def multi_agent_diagnose(
    request: MultiAgentDiagnosisRequest,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    coordinator: Any = Depends(get_diagnostic_coordinator),  # noqa: B008
) -> Any:
    """Run multi-agent diagnosis."""
    try:
        # Convert and validate phenotype inputs
        raw_phenotypes: list[str | dict[str, Any]] = []
        for p in request.phenotypes:
            if isinstance(p, str):
                raw_phenotypes.append(p)
            else:
                raw_phenotypes.append({"code": p.code, "value": p.value})

        hpo_codes, text_descriptions = validate_phenotype_input(raw_phenotypes)

        # Build phenotypes list with validated codes and text
        phenotypes: list[dict[str, Any]] = []
        for code in hpo_codes:
            phenotypes.append({"code": code, "value": code})
        for desc in text_descriptions:
            phenotypes.append({"value": desc})

        # Handle negated phenotypes separately
        for p in request.phenotypes:
            if not isinstance(p, str) and p.negated and p.code:
                # Re-add negated phenotypes with validation
                if p.code.upper().startswith("HP:") and len(p.code) == 10:
                    negated_phenotype: dict[str, Any] = {
                        "code": p.code.upper(),
                        "value": p.value,
                        "negated": True,
                    }
                    phenotypes.append(negated_phenotype)

        # Convert and validate genetic inputs
        raw_variants = [
            {
                "notation": v.notation,
                "gene_symbol": v.gene_symbol,
                "pathogenicity": v.pathogenicity,
            }
            for v in request.genetic_variants
        ]
        genetic_variants = validate_genetic_input(raw_variants)

        patient_data: dict[str, Any] = {
            "phenotypes": phenotypes,
            "genetic_variants": genetic_variants,
            "medical_history": [{"value": h} for h in request.medical_history],
            "family_history": [{"value": h} for h in request.family_history],
            "wearable_data": request.wearable_data,
        }

        if request.demographics:
            patient_data["age"] = request.demographics.age
            patient_data["age_of_onset"] = request.demographics.age_of_onset
            patient_data["sex"] = request.demographics.sex

        result = await coordinator.diagnose(patient_data)
        return result

    except (RuntimeError, ValueError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "multi-agent diagnosis")


@router.get(
    "/multi-agent/sessions/{session_id}/discriminating-phenotypes",
    summary="Get discriminating phenotypes",
    description="Get phenotypes that would best discriminate between top diagnoses.",
)
async def get_discriminating_phenotypes(
    session_id: str,
    user: Any = Depends(get_current_active_user),  # noqa: ARG001, B008
    coordinator: Any = Depends(get_diagnostic_coordinator),  # noqa: B008
) -> dict[str, Any]:
    """Get discriminating phenotype suggestions."""
    try:
        suggestions = await coordinator.suggest_discriminating_phenotypes(session_id)
        return {"suggestions": suggestions}
    except (RuntimeError, ValueError, TypeError, OSError) as e:
        raise _handle_internal_error(e, "getting discriminating phenotypes")


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get(
    "/health",
    summary="Health check",
)
async def health_check() -> dict[str, str | bool]:
    """Check diagnosis service health."""
    return {
        "status": "healthy",
        "service": "diagnosis",
        "timestamp": datetime.now(UTC).isoformat(),
        "session_controller_available": _services.session_controller is not None,
        "coordinator_available": _services.diagnostic_coordinator is not None,
    }


# =============================================================================
# Service Initialization
# =============================================================================


def initialize_diagnosis_services(
    session_controller: Any,
    diagnostic_coordinator: Any,
) -> None:
    """Initialize diagnosis services (called from app.py). Thread-safe."""
    _services.initialize(session_controller, diagnostic_coordinator)
