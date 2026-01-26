"""
Diagnosis Session Controller

Manages autonomous diagnosis sessions with interruptable segments,
event streaming, and multi-iteration refinement.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from .engine import DiagnosisEngine, EngineConfig, create_diagnosis_engine
from .models import (
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisState,
    PatientProfile,
)
from .scoring import ScoringConfig

logger = structlog.get_logger(__name__)


class SessionEvent(str, Enum):
    """Events emitted during diagnosis session."""

    SESSION_STARTED = "session_started"
    INTAKE_COMPLETE = "intake_complete"
    HYPOTHESES_GENERATED = "hypotheses_generated"
    SCORING_COMPLETE = "scoring_complete"
    QUESTIONS_READY = "questions_ready"
    ANSWER_RECEIVED = "answer_received"
    REFINEMENT_COMPLETE = "refinement_complete"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_COMPLETE = "session_complete"
    SESSION_EXPIRED = "session_expired"
    ERROR = "error"


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(UTC)


@dataclass
class SessionEventData:
    """Data for a session event."""

    event_type: SessionEvent
    session_id: str
    timestamp: datetime = field(default_factory=_utc_now)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event_type.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class SessionConfig:
    """Configuration for session controller."""

    # Timeouts
    session_timeout: timedelta = field(default_factory=lambda: timedelta(hours=1))
    question_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    idle_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))

    # Iteration limits
    max_iterations: int = 10
    max_questions_total: int = 20

    # Auto-advance behavior
    auto_advance: bool = True
    pause_for_questions: bool = True

    # Confidence thresholds
    early_termination_confidence: float = 0.9
    minimum_confidence_for_completion: float = 0.5


EventCallback = Callable[[SessionEventData], Awaitable[None]]


class SessionController:
    """
    Controller for autonomous diagnosis sessions.

    Features:
    - Autonomous progression through diagnosis states
    - Interruptable question segments
    - Event streaming for real-time updates
    - Pause/resume capability
    - Timeout and expiration handling
    - Multi-iteration refinement
    """

    def __init__(
        self,
        engine: DiagnosisEngine | None = None,
        config: SessionConfig | None = None,
        engine_config: EngineConfig | None = None,
        scoring_config: ScoringConfig | None = None,
        primekg_overlay: Any = None,
        hpo_service: Any = None,
        genetic_service: Any = None,
        neo4j_client: Any = None,
    ) -> None:
        """
        Initialize the session controller.

        Args:
            engine: Optional pre-configured diagnosis engine
            config: Session configuration
            engine_config: Engine configuration (if creating new engine)
            scoring_config: Scoring configuration (if creating new engine)
            primekg_overlay: PrimeKG overlay
            hpo_service: HPO service
            genetic_service: Genetic service
            neo4j_client: Neo4j client
        """
        self.config = config or SessionConfig()

        # Create or use provided engine
        if engine:
            self._engine = engine
        else:
            self._engine = create_diagnosis_engine(
                config=engine_config,
                scoring_config=scoring_config,
                primekg_overlay=primekg_overlay,
                hpo_service=hpo_service,
                genetic_service=genetic_service,
                neo4j_client=neo4j_client,
            )

        # Active sessions
        self._sessions: dict[str, DiagnosisSession] = {}
        self._session_tasks: dict[str, asyncio.Task[Any]] = {}
        self._session_locks: dict[str, asyncio.Lock] = {}

        # Event subscribers
        self._event_callbacks: dict[str, list[EventCallback]] = {}
        self._global_callbacks: list[EventCallback] = []

        # Background task for cleanup
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the session controller."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("session_controller_started")

    async def stop(self) -> None:
        """Stop the session controller."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all active session tasks and await their completion
        tasks_to_cancel = list(self._session_tasks.values())
        for task in tasks_to_cancel:
            task.cancel()

        # Await all cancelled tasks to ensure clean shutdown
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self._session_tasks.clear()
        logger.info("session_controller_stopped", cancelled_tasks=len(tasks_to_cancel))

    async def create_session(
        self,
        patient: PatientProfile | None = None,
        event_callback: EventCallback | None = None,
    ) -> DiagnosisSession:
        """
        Create a new diagnosis session.

        Args:
            patient: Initial patient profile
            event_callback: Optional callback for this session's events

        Returns:
            New diagnosis session
        """
        session = await self._engine.create_session(
            patient=patient,
            auto_advance=False,  # Controller manages advancement
        )

        session.max_iterations = self.config.max_iterations
        session.expires_at = _utc_now() + self.config.session_timeout

        self._sessions[session.id] = session
        self._session_locks[session.id] = asyncio.Lock()

        if event_callback:
            self._event_callbacks[session.id] = [event_callback]

        await self._emit_event(
            SessionEvent.SESSION_STARTED,
            session,
            {
                "patient_id": session.patient.id,
                "expires_at": session.expires_at.isoformat(),
            },
        )

        return session

    async def start_diagnosis(
        self,
        session_id: str,
        phenotypes: list[str] | None = None,
        genetic_variants: list[dict[str, Any]] | None = None,
        medical_history: list[str] | None = None,
        family_history: list[str] | None = None,
        demographics: dict[str, Any] | None = None,
    ) -> DiagnosisSession:
        """
        Start the diagnosis process with initial intake.

        This is the main entry point after creating a session.
        The process runs autonomously until questions need answering.

        Args:
            session_id: Session ID
            phenotypes: Initial phenotypes
            genetic_variants: Initial genetic variants
            medical_history: Medical history items
            family_history: Family history items
            demographics: Patient demographics

        Returns:
            Updated session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._session_locks[session_id]:
            # Process intake
            session = await self._engine.process_intake(
                session,
                phenotypes=phenotypes,
                genetic_variants=genetic_variants,
                medical_history=medical_history,
                family_history=family_history,
                demographics=demographics,
            )

            await self._emit_event(
                SessionEvent.INTAKE_COMPLETE,
                session,
                {
                    "phenotype_count": len(session.patient.phenotypes),
                    "variant_count": len(session.patient.genetic_variants),
                },
            )

            # Start autonomous processing
            if self.config.auto_advance:
                return await self._run_autonomous_loop(session)

            return session

    async def _run_autonomous_loop(
        self,
        session: DiagnosisSession,
    ) -> DiagnosisSession:
        """
        Run the autonomous diagnosis loop.

        Continues until:
        - Confident diagnosis reached
        - Questions need answering (paused)
        - Max iterations reached
        - Session expired
        """
        while session.is_active:
            # Check for expiration
            if session.expires_at and _utc_now() > session.expires_at:
                session.state = DiagnosisState.EXPIRED
                await self._emit_event(SessionEvent.SESSION_EXPIRED, session, {})
                break

            # Check iteration limit
            if session.iterations >= session.max_iterations:
                break

            # Process based on state
            if session.state == DiagnosisState.INTAKE:
                # Generate hypotheses
                session = await self._engine.generate_hypotheses(session)
                await self._emit_event(
                    SessionEvent.HYPOTHESES_GENERATED,
                    session,
                    {
                        "hypothesis_count": len(session.hypotheses),
                    },
                )

            elif session.state == DiagnosisState.ANALYZING:
                # Score hypotheses
                session = await self._engine.score_hypotheses(session)
                await self._emit_event(
                    SessionEvent.SCORING_COMPLETE,
                    session,
                    {
                        "top_hypotheses": [
                            {"disease": h.disease_name, "score": h.combined_score}
                            for h in session.top_hypotheses[:5]
                        ],
                    },
                )

                # Check for early termination
                if (
                    session.top_diagnosis
                    and session.top_diagnosis.combined_score
                    >= self.config.early_termination_confidence
                ):
                    session.state = DiagnosisState.COMPLETE
                    break

            elif session.state == DiagnosisState.QUESTIONING:
                # Generate questions
                session = await self._engine.generate_questions(session)
                await self._emit_event(
                    SessionEvent.QUESTIONS_READY,
                    session,
                    {
                        "questions": [q.to_dict() for q in session.pending_questions],
                    },
                )

                # Pause for questions if configured
                if self.config.pause_for_questions and session.pending_questions:
                    session.state = DiagnosisState.PAUSED
                    await self._emit_event(
                        SessionEvent.SESSION_PAUSED,
                        session,
                        {
                            "reason": "awaiting_answers",
                            "pending_questions": len(session.pending_questions),
                        },
                    )
                    break

            elif session.state == DiagnosisState.REFINING:
                # Re-score with new evidence
                session = await self._engine.score_hypotheses(session)
                await self._emit_event(
                    SessionEvent.REFINEMENT_COMPLETE,
                    session,
                    {
                        "iteration": session.iterations,
                        "top_score": session.top_diagnosis.combined_score
                        if session.top_diagnosis
                        else 0,
                    },
                )

            elif session.state == DiagnosisState.PAUSED:
                # Wait for resume
                break

            elif session.state == DiagnosisState.COMPLETE:
                break

            # Small delay to prevent tight loop
            await asyncio.sleep(0.01)

        # Check if complete
        if session.state == DiagnosisState.COMPLETE or session.is_confident:
            session.state = DiagnosisState.COMPLETE
            await self._emit_event(
                SessionEvent.SESSION_COMPLETE,
                session,
                {
                    "primary_diagnosis": session.top_diagnosis.disease_name
                    if session.top_diagnosis
                    else None,
                    "confidence": session.top_diagnosis.combined_score
                    if session.top_diagnosis
                    else 0,
                    "iterations": session.iterations,
                },
            )

        return session

    async def answer_questions(
        self,
        session_id: str,
        answers: list[dict[str, Any]],
    ) -> DiagnosisSession:
        """
        Submit answers to pending questions.

        Args:
            session_id: Session ID
            answers: List of {question_id, answer, additional_info}

        Returns:
            Updated session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._session_locks[session_id]:
            for answer_data in answers:
                question_id = answer_data.get("question_id")
                answer = answer_data.get("answer")
                additional_info = answer_data.get("additional_info")

                if question_id and answer:
                    session = await self._engine.answer_question(
                        session,
                        question_id=question_id,
                        answer=answer,
                        additional_info=additional_info,
                    )

                    await self._emit_event(
                        SessionEvent.ANSWER_RECEIVED,
                        session,
                        {
                            "question_id": question_id,
                            "answer": answer,
                        },
                    )

            # Resume autonomous processing
            if session.state == DiagnosisState.PAUSED:
                session.state = DiagnosisState.REFINING
                await self._emit_event(SessionEvent.SESSION_RESUMED, session, {})

            if self.config.auto_advance:
                return await self._run_autonomous_loop(session)

            return session

    async def skip_questions(
        self,
        session_id: str,
    ) -> DiagnosisSession:
        """
        Skip pending questions and finalize with current evidence.

        Args:
            session_id: Session ID

        Returns:
            Updated session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._session_locks[session_id]:
            session.pending_questions.clear()
            session.state = DiagnosisState.COMPLETE

            await self._emit_event(
                SessionEvent.SESSION_COMPLETE,
                session,
                {
                    "primary_diagnosis": session.top_diagnosis.disease_name
                    if session.top_diagnosis
                    else None,
                    "confidence": session.top_diagnosis.combined_score
                    if session.top_diagnosis
                    else 0,
                    "questions_skipped": True,
                },
            )

            return session

    async def pause_session(
        self,
        session_id: str,
    ) -> DiagnosisSession:
        """
        Pause a running session.

        Args:
            session_id: Session ID

        Returns:
            Paused session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._session_locks[session_id]:
            if session.is_active:
                session.state = DiagnosisState.PAUSED
                await self._emit_event(
                    SessionEvent.SESSION_PAUSED,
                    session,
                    {
                        "reason": "user_requested",
                    },
                )

            return session

    async def resume_session(
        self,
        session_id: str,
    ) -> DiagnosisSession:
        """
        Resume a paused session.

        Args:
            session_id: Session ID

        Returns:
            Resumed session
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        async with self._session_locks[session_id]:
            if session.state == DiagnosisState.PAUSED:
                # Resume to appropriate state
                if session.pending_questions:
                    session.state = DiagnosisState.QUESTIONING
                else:
                    session.state = DiagnosisState.REFINING

                await self._emit_event(SessionEvent.SESSION_RESUMED, session, {})

                if self.config.auto_advance:
                    return await self._run_autonomous_loop(session)

            return session

    async def get_result(
        self,
        session_id: str,
    ) -> DiagnosisResult:
        """
        Get the final diagnosis result.

        Args:
            session_id: Session ID

        Returns:
            Diagnosis result
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        return await self._engine.finalize_session(session)

    async def stream_events(
        self,
        session_id: str,
    ) -> AsyncIterator[SessionEventData]:
        """
        Stream events for a session.

        Yields events as they occur until session completes.

        Args:
            session_id: Session ID

        Yields:
            Session events
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        queue: asyncio.Queue[SessionEventData] = asyncio.Queue()

        async def queue_callback(event: SessionEventData) -> None:
            await queue.put(event)

        # Subscribe to events
        if session_id not in self._event_callbacks:
            self._event_callbacks[session_id] = []
        self._event_callbacks[session_id].append(queue_callback)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=self.config.idle_timeout.total_seconds(),
                    )
                    yield event

                    # Stop if session complete or expired
                    if event.event_type in {
                        SessionEvent.SESSION_COMPLETE,
                        SessionEvent.SESSION_EXPIRED,
                    }:
                        break

                except TimeoutError:
                    # Session idle timeout
                    break

        finally:
            # Unsubscribe
            if session_id in self._event_callbacks:
                self._event_callbacks[session_id].remove(queue_callback)

    def get_session(self, session_id: str) -> DiagnosisSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        active_only: bool = True,
    ) -> list[DiagnosisSession]:
        """List all sessions."""
        sessions = list(self._sessions.values())
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            # Cancel any running task
            if session_id in self._session_tasks:
                self._session_tasks[session_id].cancel()
                del self._session_tasks[session_id]

            del self._sessions[session_id]
            del self._session_locks[session_id]

            if session_id in self._event_callbacks:
                del self._event_callbacks[session_id]

            self._engine.remove_session(session_id)
            return True

        return False

    def subscribe(
        self,
        callback: EventCallback,
        session_id: str | None = None,
    ) -> None:
        """
        Subscribe to session events.

        Args:
            callback: Event callback function
            session_id: Optional specific session (None for all)
        """
        if session_id:
            if session_id not in self._event_callbacks:
                self._event_callbacks[session_id] = []
            self._event_callbacks[session_id].append(callback)
        else:
            self._global_callbacks.append(callback)

    def unsubscribe(
        self,
        callback: EventCallback,
        session_id: str | None = None,
    ) -> None:
        """
        Unsubscribe from session events.

        Args:
            callback: Event callback to remove
            session_id: Specific session or None for global
        """
        if session_id:
            if session_id in self._event_callbacks:
                self._event_callbacks[session_id].remove(callback)
        else:
            self._global_callbacks.remove(callback)

    async def _emit_event(
        self,
        event_type: SessionEvent,
        session: DiagnosisSession,
        data: dict[str, Any],
    ) -> None:
        """Emit an event to all subscribers."""
        event = SessionEventData(
            event_type=event_type,
            session_id=session.id,
            data=data,
        )

        # Session-specific callbacks
        callbacks = self._event_callbacks.get(session.id, [])
        for callback in callbacks:
            try:
                await callback(event)
            except (RuntimeError, ValueError, TypeError, OSError) as e:
                logger.error("event_callback_failed", error=str(e))

        # Global callbacks
        for callback in self._global_callbacks:
            try:
                await callback(event)
            except (RuntimeError, ValueError, TypeError, OSError) as e:
                logger.error("global_callback_failed", error=str(e))

    async def _cleanup_loop(self) -> None:
        """Background loop to clean up expired and idle sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired_sessions()

            except asyncio.CancelledError:
                break
            except Exception as e:  # Intentional broad catch: prevents background task death
                logger.error("cleanup_loop_error", error=str(e))

    async def _cleanup_expired_sessions(self) -> int:
        """
        Clean up expired and idle sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = _utc_now()
        expired_ids = []
        idle_ids = []

        # Create a snapshot to avoid modification during iteration
        sessions_snapshot = list(self._sessions.items())

        for session_id, session in sessions_snapshot:
            # Check for expired sessions
            if session.expires_at and now > session.expires_at:
                if session.state != DiagnosisState.EXPIRED:
                    session.state = DiagnosisState.EXPIRED
                    await self._emit_event(
                        SessionEvent.SESSION_EXPIRED,
                        session,
                        {},
                    )
                expired_ids.append(session_id)

            # Check for idle sessions (not updated in idle_timeout period)
            elif session.updated_at:
                idle_threshold = now - self.config.idle_timeout
                if session.updated_at < idle_threshold:
                    # Don't expire completed sessions, just queue for cleanup
                    if session.state == DiagnosisState.COMPLETE:
                        idle_ids.append(session_id)
                    else:
                        session.state = DiagnosisState.EXPIRED
                        await self._emit_event(
                            SessionEvent.SESSION_EXPIRED,
                            session,
                            {"reason": "idle_timeout"},
                        )
                        expired_ids.append(session_id)

        # Clean up expired sessions older than 1 hour
        cleanup_count = 0
        cleanup_threshold = now - timedelta(hours=1)

        for session_id in expired_ids:
            expired_session = self._sessions.get(session_id)
            if (
                expired_session
                and expired_session.expires_at
                and expired_session.expires_at < cleanup_threshold
            ):
                await self.delete_session(session_id)
                cleanup_count += 1

        # Clean up completed but idle sessions older than 2 hours
        completed_cleanup_threshold = now - timedelta(hours=2)
        for session_id in idle_ids:
            idle_session = self._sessions.get(session_id)
            if (
                idle_session
                and idle_session.updated_at
                and idle_session.updated_at < completed_cleanup_threshold
            ):
                await self.delete_session(session_id)
                cleanup_count += 1

        if cleanup_count > 0:
            logger.info(
                "sessions_cleaned_up",
                count=cleanup_count,
                remaining=len(self._sessions),
            )

        return cleanup_count

    async def cleanup_all_expired(self) -> int:
        """
        Manually trigger cleanup of all expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        return await self._cleanup_expired_sessions()

    def get_session_stats(self) -> dict[str, Any]:
        """
        Get statistics about current sessions.

        Returns:
            Dictionary with session statistics
        """
        now = _utc_now()
        states: dict[str, int] = {}
        total_age = timedelta()

        for session in self._sessions.values():
            state = session.state.value
            states[state] = states.get(state, 0) + 1
            if session.created_at:
                total_age += now - session.created_at

        return {
            "total_sessions": len(self._sessions),
            "by_state": states,
            "average_age_seconds": (
                total_age.total_seconds() / len(self._sessions) if self._sessions else 0
            ),
        }


# =============================================================================
# Factory Function
# =============================================================================


def create_session_controller(
    config: SessionConfig | None = None,
    engine_config: EngineConfig | None = None,
    scoring_config: ScoringConfig | None = None,
    primekg_overlay: Any = None,
    hpo_service: Any = None,
    genetic_service: Any = None,
    neo4j_client: Any = None,
) -> SessionController:
    """Create a session controller instance."""
    return SessionController(
        config=config,
        engine_config=engine_config,
        scoring_config=scoring_config,
        primekg_overlay=primekg_overlay,
        hpo_service=hpo_service,
        genetic_service=genetic_service,
        neo4j_client=neo4j_client,
    )
