"""
Base Diagnostic Agent

Abstract base class for all diagnostic agents with common functionality.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class AgentRole(str, Enum):
    """Roles for diagnostic agents."""

    PHENOTYPE_EXPERT = "phenotype_expert"
    GENETIC_EXPERT = "genetic_expert"
    DIFFERENTIAL_EXPERT = "differential_expert"
    HISTORY_EXPERT = "history_expert"
    COORDINATOR = "coordinator"


class MessageType(str, Enum):
    """Types of inter-agent messages."""

    REQUEST = "request"
    RESPONSE = "response"
    ANALYSIS = "analysis"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    QUESTION = "question"
    CONSENSUS = "consensus"
    ERROR = "error"


def _utc_now() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(UTC)


@dataclass
class AgentMessage:
    """
    Message passed between diagnostic agents.

    Enables structured communication for collaborative diagnosis.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    sender: AgentRole = AgentRole.COORDINATOR
    recipient: AgentRole | None = None  # None = broadcast
    message_type: MessageType = MessageType.REQUEST
    content: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)

    # Threading
    in_reply_to: str | None = None
    thread_id: str | None = None

    # Priority
    priority: int = 1  # 1 = highest

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender.value,
            "recipient": self.recipient.value if self.recipient else None,
            "message_type": self.message_type.value,
            "content": self.content,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "in_reply_to": self.in_reply_to,
            "thread_id": self.thread_id,
            "priority": self.priority,
        }


@dataclass
class AgentConfig:
    """Base configuration for diagnostic agents."""

    # Processing limits
    max_hypotheses: int = 20
    confidence_threshold: float = 0.5
    timeout: float = 30.0

    # LLM settings (for agents that use LLMs)
    use_llm: bool = False
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.3

    # Caching
    enable_cache: bool = True
    cache_ttl: int = 3600  # seconds


class DiagnosticAgent(ABC):
    """
    Abstract base class for diagnostic agents.

    Each agent specializes in a specific aspect of diagnosis:
    - Analyzing specific evidence types
    - Generating hypotheses from their domain
    - Answering questions from other agents
    - Contributing to consensus decisions
    """

    def __init__(
        self,
        role: AgentRole,
        config: AgentConfig | None = None,
    ):
        """
        Initialize the diagnostic agent.

        Args:
            role: Agent's role
            config: Agent configuration
        """
        self.role = role
        self.config = config or AgentConfig()
        self.agent_id = str(uuid4())

        # Message history
        self._message_history: list[AgentMessage] = []
        self._pending_responses: dict[str, AgentMessage] = {}

        # State
        self._is_active = False
        self._current_session: str | None = None

        logger.info(
            "agent_initialized",
            agent_id=self.agent_id,
            role=role.value,
        )

    @property
    def is_active(self) -> bool:
        """Check if agent is active."""
        return self._is_active

    async def start(self) -> None:
        """Start the agent."""
        self._is_active = True
        logger.info("agent_started", agent_id=self.agent_id)

    async def stop(self) -> None:
        """Stop the agent."""
        self._is_active = False
        logger.info("agent_stopped", agent_id=self.agent_id)

    async def receive_message(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """
        Receive and process a message.

        Args:
            message: Incoming message

        Returns:
            Response message or None
        """
        self._message_history.append(message)

        logger.debug(
            "message_received",
            agent_id=self.agent_id,
            message_type=message.message_type.value,
            sender=message.sender.value,
        )

        # Route based on message type
        try:
            if message.message_type == MessageType.REQUEST:
                return await self._handle_request(message)
            elif message.message_type == MessageType.ANALYSIS:
                return await self._handle_analysis(message)
            elif message.message_type == MessageType.EVIDENCE:
                return await self._handle_evidence(message)
            elif message.message_type == MessageType.QUESTION:
                return await self._handle_question(message)
            elif message.message_type == MessageType.HYPOTHESIS:
                return await self._handle_hypothesis(message)
            else:
                return await self._handle_other(message)

        except (RuntimeError, ValueError, TypeError, ConnectionError, OSError) as e:
            logger.error(
                "message_handling_failed",
                agent_id=self.agent_id,
                error=str(e),
            )
            return self._create_error_response(message, str(e))

    @abstractmethod
    async def analyze(
        self,
        patient_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform domain-specific analysis.

        Args:
            patient_data: Patient information
            context: Additional context

        Returns:
            Analysis results
        """
        pass

    @abstractmethod
    async def generate_hypotheses(
        self,
        evidence: list[dict[str, Any]],
        existing_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate hypotheses from evidence.

        Args:
            evidence: Evidence items
            existing_hypotheses: Current hypotheses to refine

        Returns:
            List of hypothesis dictionaries
        """
        pass

    @abstractmethod
    async def evaluate_hypothesis(
        self,
        hypothesis: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Evaluate a hypothesis against evidence.

        Args:
            hypothesis: Hypothesis to evaluate
            evidence: Evidence items

        Returns:
            Evaluation result with score and reasoning
        """
        pass

    async def _handle_request(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle a request message."""
        request_type = message.content.get("request_type")

        if request_type == "analyze":
            result = await self.analyze(
                message.content.get("patient_data", {}),
                message.context,
            )
            return self._create_response(message, result, MessageType.ANALYSIS)

        elif request_type == "hypothesize":
            hypotheses = await self.generate_hypotheses(
                message.content.get("evidence", []),
                message.content.get("existing_hypotheses"),
            )
            return self._create_response(
                message,
                {"hypotheses": hypotheses},
                MessageType.HYPOTHESIS,
            )

        elif request_type == "evaluate":
            evaluation = await self.evaluate_hypothesis(
                message.content.get("hypothesis", {}),
                message.content.get("evidence", []),
            )
            return self._create_response(message, evaluation, MessageType.RESPONSE)

        return None

    async def _handle_analysis(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle an analysis message from another agent."""
        # Subclasses can override to incorporate other agents' analyses
        return None

    async def _handle_evidence(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle new evidence."""
        # Subclasses can override to process new evidence
        return None

    async def _handle_question(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle a question from another agent."""
        # Default: return unknown
        return self._create_response(
            message,
            {"answer": "unknown", "confidence": 0.0},
            MessageType.RESPONSE,
        )

    async def _handle_hypothesis(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle a hypothesis from another agent."""
        # Evaluate the hypothesis from our perspective
        hypothesis = message.content.get("hypothesis", {})
        evidence = message.content.get("evidence", [])

        evaluation = await self.evaluate_hypothesis(hypothesis, evidence)
        return self._create_response(message, evaluation, MessageType.RESPONSE)

    async def _handle_other(
        self,
        message: AgentMessage,
    ) -> AgentMessage | None:
        """Handle other message types."""
        return None

    def _create_response(
        self,
        original: AgentMessage,
        content: dict[str, Any],
        message_type: MessageType = MessageType.RESPONSE,
    ) -> AgentMessage:
        """Create a response message."""
        return AgentMessage(
            sender=self.role,
            recipient=original.sender,
            message_type=message_type,
            content=content,
            context=original.context,
            in_reply_to=original.id,
            thread_id=original.thread_id or original.id,
        )

    def _create_error_response(
        self,
        original: AgentMessage,
        error: str,
    ) -> AgentMessage:
        """Create an error response message."""
        return AgentMessage(
            sender=self.role,
            recipient=original.sender,
            message_type=MessageType.ERROR,
            content={"error": error},
            in_reply_to=original.id,
            thread_id=original.thread_id or original.id,
        )

    def get_message_history(
        self,
        limit: int | None = None,
    ) -> list[AgentMessage]:
        """Get message history."""
        if limit:
            return self._message_history[-limit:]
        return self._message_history.copy()

    def clear_history(self) -> None:
        """Clear message history."""
        self._message_history.clear()
        self._pending_responses.clear()
