"""
Diagnostic Coordinator

Orchestrates multi-agent collaborative diagnosis.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from .base import (
    AgentMessage,
    AgentRole,
    DiagnosticAgent,
    MessageType,
)
from .differential_agent import DifferentialAgent, create_differential_agent
from .genetic_agent import GeneticAgent, create_genetic_agent
from .phenotype_agent import PhenotypeAgent, create_phenotype_agent

logger = structlog.get_logger(__name__)


@dataclass
class CoordinatorConfig:
    """Configuration for diagnostic coordinator."""
    # Agent enablement
    enable_phenotype_agent: bool = True
    enable_genetic_agent: bool = True
    enable_differential_agent: bool = True

    # Coordination settings
    parallel_analysis: bool = True
    require_consensus: bool = False
    consensus_threshold: float = 0.7

    # Iteration control
    max_iterations: int = 5
    convergence_threshold: float = 0.05

    # Timeouts
    agent_timeout: float = 30.0
    total_timeout: float = 120.0

    # Communication
    broadcast_analyses: bool = True
    enable_agent_questions: bool = True


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(UTC)


@dataclass
class CoordinationSession:
    """A multi-agent diagnosis coordination session."""
    id: str = field(default_factory=lambda: str(uuid4()))
    patient_data: dict[str, Any] = field(default_factory=dict)

    # Agent analyses
    phenotype_analysis: dict[str, Any] | None = None
    genetic_analysis: dict[str, Any] | None = None
    differential_result: dict[str, Any] | None = None

    # Coordination state
    iteration: int = 0
    is_complete: bool = False
    consensus_reached: bool = False

    # Messages
    message_history: list[AgentMessage] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=_utc_now)
    completed_at: datetime | None = None


EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class DiagnosticCoordinator:
    """
    Coordinator for multi-agent diagnostic collaboration.

    Orchestrates:
    - PhenotypeAgent: Phenotype analysis
    - GeneticAgent: Genetic evidence analysis
    - DifferentialAgent: Final diagnosis synthesis

    Workflow:
    1. Dispatch patient data to specialist agents
    2. Collect and broadcast analyses
    3. Coordinate consensus building
    4. Generate final differential diagnosis
    """

    def __init__(
        self,
        config: CoordinatorConfig | None = None,
        phenotype_agent: PhenotypeAgent | None = None,
        genetic_agent: GeneticAgent | None = None,
        differential_agent: DifferentialAgent | None = None,
        primekg_overlay: Any = None,
        hpo_service: Any = None,
        genetic_service: Any = None,
        neo4j_client: Any = None,
    ) -> None:
        """
        Initialize the diagnostic coordinator.

        Args:
            config: Coordinator configuration
            phenotype_agent: Optional pre-configured phenotype agent
            genetic_agent: Optional pre-configured genetic agent
            differential_agent: Optional pre-configured differential agent
            primekg_overlay: PrimeKG overlay
            hpo_service: HPO service
            genetic_service: Genetic service
            neo4j_client: Neo4j client
        """
        self.config = config or CoordinatorConfig()

        # Store dependencies for agent creation
        self._primekg = primekg_overlay
        self._hpo = hpo_service
        self._genetic = genetic_service
        self._neo4j = neo4j_client

        # Initialize agents
        self._agents: dict[AgentRole, DiagnosticAgent] = {}

        if self.config.enable_phenotype_agent:
            self._agents[AgentRole.PHENOTYPE_EXPERT] = phenotype_agent or create_phenotype_agent(
                hpo_service=hpo_service,
                primekg_overlay=primekg_overlay,
                neo4j_client=neo4j_client,
            )

        if self.config.enable_genetic_agent:
            self._agents[AgentRole.GENETIC_EXPERT] = genetic_agent or create_genetic_agent(
                genetic_service=genetic_service,
                primekg_overlay=primekg_overlay,
                neo4j_client=neo4j_client,
            )

        if self.config.enable_differential_agent:
            self._agents[AgentRole.DIFFERENTIAL_EXPERT] = differential_agent or create_differential_agent(
                primekg_overlay=primekg_overlay,
                neo4j_client=neo4j_client,
            )

        # Active sessions
        self._sessions: dict[str, CoordinationSession] = {}

        # Event callbacks
        self._event_callbacks: list[EventCallback] = []

    async def start(self) -> None:
        """Start the coordinator and all agents."""
        for agent in self._agents.values():
            await agent.start()
        logger.info("diagnostic_coordinator_started", agents=len(self._agents))

    async def stop(self) -> None:
        """Stop the coordinator and all agents."""
        for agent in self._agents.values():
            await agent.stop()
        logger.info("diagnostic_coordinator_stopped")

    async def diagnose(
        self,
        patient_data: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run full multi-agent diagnostic analysis.

        Args:
            patient_data: Complete patient data
            session_id: Optional session ID

        Returns:
            Comprehensive diagnosis result
        """
        # Create session
        session = CoordinationSession(
            id=session_id or str(uuid4()),
            patient_data=patient_data,
        )
        self._sessions[session.id] = session

        await self._emit_event("diagnosis_started", {
            "session_id": session.id,
            "agents": list(self._agents.keys()),
        })

        try:
            # Phase 1: Parallel specialist analysis
            await self._run_specialist_analysis(session)

            # Phase 2: Synthesis by differential agent
            await self._run_differential_synthesis(session)

            # Phase 3: Consensus building (if enabled)
            if self.config.require_consensus:
                await self._build_consensus(session)

            session.is_complete = True
            session.completed_at = _utc_now()

            await self._emit_event("diagnosis_complete", {
                "session_id": session.id,
                "result": session.differential_result,
            })

            return self._build_result(session)

        except TimeoutError:
            logger.error("diagnosis_timeout", session_id=session.id)
            return {
                "error": "Diagnosis timeout",
                "partial_results": self._build_result(session),
            }
        except Exception as e:
            logger.error("diagnosis_failed", session_id=session.id, error=str(e))
            return {
                "error": str(e),
                "partial_results": self._build_result(session),
            }

    async def _run_specialist_analysis(
        self,
        session: CoordinationSession,
    ) -> None:
        """Run specialist agent analyses."""
        tasks = []

        # Phenotype analysis
        if AgentRole.PHENOTYPE_EXPERT in self._agents:
            tasks.append(self._run_agent_analysis(
                session,
                AgentRole.PHENOTYPE_EXPERT,
                "phenotype_analysis",
            ))

        # Genetic analysis
        if AgentRole.GENETIC_EXPERT in self._agents:
            tasks.append(self._run_agent_analysis(
                session,
                AgentRole.GENETIC_EXPERT,
                "genetic_analysis",
            ))

        # Run in parallel or sequential
        if self.config.parallel_analysis and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            for task in tasks:
                try:
                    await task
                except Exception as e:
                    logger.warning("agent_analysis_failed", error=str(e))

    async def _run_agent_analysis(
        self,
        session: CoordinationSession,
        role: AgentRole,
        result_key: str,
    ) -> None:
        """Run analysis for a specific agent."""
        agent = self._agents.get(role)
        if not agent:
            return

        await self._emit_event("agent_started", {
            "session_id": session.id,
            "agent": role.value,
        })

        try:
            # Create analysis request
            message = AgentMessage(
                sender=AgentRole.COORDINATOR,
                recipient=role,
                message_type=MessageType.REQUEST,
                content={
                    "request_type": "analyze",
                    "patient_data": session.patient_data,
                },
                context={"session_id": session.id},
            )

            # Send to agent
            response = await asyncio.wait_for(
                agent.receive_message(message),
                timeout=self.config.agent_timeout,
            )

            if response and response.message_type == MessageType.ANALYSIS:
                setattr(session, result_key, response.content)
                session.message_history.append(message)
                session.message_history.append(response)

                await self._emit_event("agent_complete", {
                    "session_id": session.id,
                    "agent": role.value,
                    "result_summary": self._summarize_analysis(response.content),
                })

                # Broadcast to other agents if enabled
                if self.config.broadcast_analyses:
                    await self._broadcast_analysis(session, role, response.content)

        except TimeoutError:
            logger.warning("agent_timeout", agent=role.value)
        except Exception as e:
            logger.error("agent_error", agent=role.value, error=str(e))

    async def _broadcast_analysis(
        self,
        session: CoordinationSession,
        source_role: AgentRole,
        analysis: dict[str, Any],
    ) -> None:
        """Broadcast analysis to other agents."""
        for role, agent in self._agents.items():
            if role != source_role and role != AgentRole.COORDINATOR:
                message = AgentMessage(
                    sender=source_role,
                    recipient=role,
                    message_type=MessageType.ANALYSIS,
                    content=analysis,
                    context={"session_id": session.id},
                )
                # Fire and forget with error handling
                task = asyncio.create_task(agent.receive_message(message))
                task.add_done_callback(
                    lambda t: logger.error("broadcast_task_failed", error=str(t.exception()))
                    if t.exception() else None
                )

    async def _run_differential_synthesis(
        self,
        session: CoordinationSession,
    ) -> None:
        """Run differential diagnosis synthesis."""
        agent = self._agents.get(AgentRole.DIFFERENTIAL_EXPERT)
        if not agent:
            return

        await self._emit_event("synthesis_started", {
            "session_id": session.id,
        })

        # Build context with all analyses
        context = {}
        if session.phenotype_analysis:
            context["phenotype_analysis"] = session.phenotype_analysis
        if session.genetic_analysis:
            context["genetic_analysis"] = session.genetic_analysis

        try:
            message = AgentMessage(
                sender=AgentRole.COORDINATOR,
                recipient=AgentRole.DIFFERENTIAL_EXPERT,
                message_type=MessageType.REQUEST,
                content={
                    "request_type": "analyze",
                    "patient_data": session.patient_data,
                },
                context={
                    "session_id": session.id,
                    **context,
                },
            )

            response = await asyncio.wait_for(
                agent.receive_message(message),
                timeout=self.config.agent_timeout,
            )

            if response and response.message_type == MessageType.ANALYSIS:
                session.differential_result = response.content
                session.message_history.append(message)
                session.message_history.append(response)

                await self._emit_event("synthesis_complete", {
                    "session_id": session.id,
                    "differential_count": len(
                        response.content.get("differential", [])
                    ),
                })

        except TimeoutError:
            logger.warning("differential_timeout")
        except Exception as e:
            logger.error("differential_error", error=str(e))

    async def _build_consensus(
        self,
        session: CoordinationSession,
    ) -> None:
        """Build consensus among agents on top diagnosis."""
        if not session.differential_result:
            return

        differential = session.differential_result.get("differential", [])
        if not differential:
            return

        top_hypothesis = differential[0]

        # Ask each agent to evaluate the top hypothesis
        evaluations = []

        for role, agent in self._agents.items():
            if role == AgentRole.DIFFERENTIAL_EXPERT:
                continue

            message = AgentMessage(
                sender=AgentRole.COORDINATOR,
                recipient=role,
                message_type=MessageType.HYPOTHESIS,
                content={
                    "hypothesis": top_hypothesis,
                    "evidence": self._get_all_evidence(session),
                },
                context={"session_id": session.id},
            )

            try:
                response = await asyncio.wait_for(
                    agent.receive_message(message),
                    timeout=self.config.agent_timeout / 2,
                )
                if response:
                    evaluations.append({
                        "agent": role.value,
                        "evaluation": response.content,
                    })
            except Exception:
                pass

        # Check for consensus
        if evaluations:
            scores = [
                e["evaluation"].get("score", 0.5)
                for e in evaluations
            ]
            avg_score = sum(scores) / len(scores)
            session.consensus_reached = avg_score >= self.config.consensus_threshold

            # Add consensus info to result
            session.differential_result["consensus"] = {
                "reached": session.consensus_reached,
                "average_score": avg_score,
                "agent_evaluations": evaluations,
            }

    def _get_all_evidence(
        self,
        session: CoordinationSession,
    ) -> list[dict[str, Any]]:
        """Get all evidence from patient data."""
        evidence = []

        for phenotype in session.patient_data.get("phenotypes", []):
            if isinstance(phenotype, dict):
                evidence.append({"evidence_type": "phenotype", **phenotype})
            else:
                evidence.append({"evidence_type": "phenotype", "value": phenotype})

        for variant in session.patient_data.get("genetic_variants", []):
            if isinstance(variant, dict):
                evidence.append({"evidence_type": "genetic", **variant})
            else:
                evidence.append({"evidence_type": "genetic", "value": variant})

        for item in session.patient_data.get("medical_history", []):
            if isinstance(item, dict):
                evidence.append({"evidence_type": "history", **item})
            else:
                evidence.append({"evidence_type": "history", "value": item})

        for item in session.patient_data.get("family_history", []):
            if isinstance(item, dict):
                evidence.append({"evidence_type": "family", **item})
            else:
                evidence.append({"evidence_type": "family", "value": item})

        return evidence

    def _build_result(
        self,
        session: CoordinationSession,
    ) -> dict[str, Any]:
        """Build the final result from session."""
        result = {
            "session_id": session.id,
            "is_complete": session.is_complete,
            "iteration": session.iteration,
        }

        # Specialist analyses
        if session.phenotype_analysis:
            result["phenotype_analysis"] = {
                "phenotype_count": session.phenotype_analysis.get("phenotype_count"),
                "systems_affected": session.phenotype_analysis.get("systems_affected"),
                "patterns": session.phenotype_analysis.get("patterns"),
            }

        if session.genetic_analysis:
            result["genetic_analysis"] = {
                "has_genetic_data": session.genetic_analysis.get("has_genetic_data"),
                "pathogenic_count": session.genetic_analysis.get("pathogenic_count"),
                "candidate_genes": session.genetic_analysis.get("candidate_genes", [])[:5],
            }

        # Differential diagnosis
        if session.differential_result:
            result["differential_diagnosis"] = session.differential_result.get("differential", [])
            result["primary_diagnosis"] = session.differential_result.get("primary_diagnosis")
            result["confidence_assessment"] = session.differential_result.get("confidence_assessment")
            result["explanations"] = session.differential_result.get("explanations")

            if session.differential_result.get("consensus"):
                result["consensus"] = session.differential_result["consensus"]

        # Timestamps
        result["created_at"] = session.created_at.isoformat()
        if session.completed_at:
            result["completed_at"] = session.completed_at.isoformat()
            result["duration_seconds"] = (
                session.completed_at - session.created_at
            ).total_seconds()

        return result

    def _summarize_analysis(
        self,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a summary of analysis for events."""
        return {
            "keys": list(analysis.keys()),
            "items_count": sum(
                len(v) if isinstance(v, list | dict) else 1
                for v in analysis.values()
            ),
        }

    async def ask_agent(
        self,
        session_id: str,
        role: AgentRole,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ask a specific agent a question.

        Args:
            session_id: Session ID
            role: Agent role to ask
            question: Question text
            context: Additional context

        Returns:
            Agent's response
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        agent = self._agents.get(role)
        if not agent:
            return {"error": f"Agent {role.value} not available"}

        message = AgentMessage(
            sender=AgentRole.COORDINATOR,
            recipient=role,
            message_type=MessageType.QUESTION,
            content={"question": question},
            context={
                "session_id": session_id,
                **(context or {}),
            },
        )

        try:
            response = await asyncio.wait_for(
                agent.receive_message(message),
                timeout=self.config.agent_timeout,
            )
            return response.content if response else {"answer": "No response"}
        except TimeoutError:
            return {"error": "Agent timeout"}

    async def suggest_discriminating_phenotypes(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get discriminating phenotype suggestions from phenotype agent.

        Args:
            session_id: Session ID

        Returns:
            List of discriminating phenotypes
        """
        session = self._sessions.get(session_id)
        if not session or not session.differential_result:
            return []

        agent = self._agents.get(AgentRole.PHENOTYPE_EXPERT)
        if not agent or not isinstance(agent, PhenotypeAgent):
            return []

        differential = session.differential_result.get("differential", [])
        known_phenotypes = [
            p.get("code") or p.get("hpo_id")
            for p in session.patient_data.get("phenotypes", [])
            if p.get("code") or p.get("hpo_id")
        ]

        return await agent.suggest_discriminating_phenotypes(
            differential,
            known_phenotypes,
        )

    def get_session(self, session_id: str) -> CoordinationSession | None:
        """Get a coordination session."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[CoordinationSession]:
        """List all sessions."""
        return list(self._sessions.values())

    def subscribe(self, callback: EventCallback) -> None:
        """Subscribe to coordinator events."""
        self._event_callbacks.append(callback)

    def unsubscribe(self, callback: EventCallback) -> bool:
        """Unsubscribe from events. Returns True if callback was found and removed."""
        try:
            self._event_callbacks.remove(callback)
            return True
        except ValueError:
            return False

    async def _emit_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Emit an event to all subscribers."""
        for callback in self._event_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error("event_callback_failed", error=str(e))


# =============================================================================
# Factory Function
# =============================================================================

def create_diagnostic_coordinator(
    config: CoordinatorConfig | None = None,
    primekg_overlay: Any = None,
    hpo_service: Any = None,
    genetic_service: Any = None,
    neo4j_client: Any = None,
) -> DiagnosticCoordinator:
    """Create a diagnostic coordinator instance."""
    return DiagnosticCoordinator(
        config=config,
        primekg_overlay=primekg_overlay,
        hpo_service=hpo_service,
        genetic_service=genetic_service,
        neo4j_client=neo4j_client,
    )
