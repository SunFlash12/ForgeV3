"""
Governance Overlay for Forge Cascade V2

Manages symbolic governance processes including proposals,
voting, consensus building, and policy enforcement.
Part of the CONSENSUS phase in the 7-phase pipeline.

Responsibilities:
- Proposal evaluation and gating
- Vote collection and validation
- Trust-weighted consensus calculation
- Ghost Council coordination
- Policy rule evaluation

SECURITY FIX (Audit 2): Added asyncio locks to prevent race conditions
in vote processing and proposal management.
"""

import asyncio
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from ..models.base import TrustLevel
from ..models.events import Event, EventType
from ..models.governance import ProposalType, VoteChoice
from ..models.overlay import Capability
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


class GovernanceError(OverlayError):
    """Governance processing error."""
    pass


class InsufficientQuorumError(GovernanceError):
    """Quorum not reached."""
    pass


class PolicyViolationError(GovernanceError):
    """Policy rule violated."""
    pass


class ConsensusFailedError(GovernanceError):
    """Consensus could not be reached."""
    pass


class VotingStatus(str, Enum):
    """Status of voting on a proposal."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    QUORUM_REACHED = "quorum_reached"
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_FAILED = "consensus_failed"
    EXPIRED = "expired"


class ConditionOperator(str, Enum):
    """
    Safe condition operators for policy rules.

    SECURITY: Only these operators are allowed - no arbitrary code execution.
    """
    # Comparison operators
    EQ = "eq"           # ==
    NE = "ne"           # !=
    GT = "gt"           # >
    GE = "ge"           # >=
    LT = "lt"           # <
    LE = "le"           # <=

    # Existence operators
    EXISTS = "exists"           # Field is truthy
    NOT_EXISTS = "not_exists"   # Field is falsy

    # Logical operators (for combining conditions)
    AND = "and"
    OR = "or"


@dataclass
class SafeCondition:
    """
    A safe, declarative condition for policy rules.

    SECURITY: This replaces arbitrary Callable to prevent code injection.
    Conditions are evaluated using only whitelisted operations.

    Examples:
        # Check if proposer_trust >= 50
        SafeCondition("proposer_trust", ConditionOperator.GE, 50)

        # Check if title exists
        SafeCondition("title", ConditionOperator.EXISTS)

        # Combine conditions with AND
        SafeCondition.and_conditions([cond1, cond2])
    """
    field: str
    operator: ConditionOperator
    value: Any | None = None
    sub_conditions: list["SafeCondition"] | None = None

    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Safely evaluate this condition against the context.

        SECURITY: Only allows whitelisted operations on context data.
        """
        # Handle logical operators
        if self.operator == ConditionOperator.AND:
            if not self.sub_conditions:
                return True
            return all(c.evaluate(context) for c in self.sub_conditions)

        if self.operator == ConditionOperator.OR:
            if not self.sub_conditions:
                return False
            return any(c.evaluate(context) for c in self.sub_conditions)

        # Get field value safely - only allow string keys
        if not isinstance(self.field, str):
            return False

        # SECURITY: Prevent path traversal in field names
        if ".." in self.field or "/" in self.field or "\\" in self.field:
            return False

        field_value = context.get(self.field)

        # Existence operators
        if self.operator == ConditionOperator.EXISTS:
            return bool(field_value)

        if self.operator == ConditionOperator.NOT_EXISTS:
            return not bool(field_value)

        # Comparison operators - handle None safely
        if field_value is None:
            return False

        try:
            if self.operator == ConditionOperator.EQ:
                return bool(field_value == self.value)
            elif self.operator == ConditionOperator.NE:
                return bool(field_value != self.value)
            elif self.operator == ConditionOperator.GT:
                return bool(field_value > self.value)
            elif self.operator == ConditionOperator.GE:
                return bool(field_value >= self.value)
            elif self.operator == ConditionOperator.LT:
                return bool(field_value < self.value)
            elif self.operator == ConditionOperator.LE:
                return bool(field_value <= self.value)
        except (TypeError, ValueError):
            # Incompatible types for comparison
            return False

        return False

    @classmethod
    def and_conditions(cls, conditions: list["SafeCondition"]) -> "SafeCondition":
        """Create an AND condition combining multiple conditions."""
        return cls(field="", operator=ConditionOperator.AND, sub_conditions=conditions)

    @classmethod
    def or_conditions(cls, conditions: list["SafeCondition"]) -> "SafeCondition":
        """Create an OR condition combining multiple conditions."""
        return cls(field="", operator=ConditionOperator.OR, sub_conditions=conditions)


@dataclass
class PolicyRule:
    """
    A governance policy rule with safe condition evaluation.

    SECURITY: Uses SafeCondition instead of arbitrary Callable to prevent
    remote code execution through policy injection.
    """
    name: str
    description: str
    condition: SafeCondition  # Safe declarative condition
    required_trust: int = TrustLevel.STANDARD.value
    applies_to: list[ProposalType] = field(default_factory=list)

    def evaluate(self, context: dict[str, Any]) -> tuple[bool, str | None]:
        """Evaluate rule against context using safe condition evaluation."""
        try:
            if self.condition.evaluate(context):
                return True, None
            return False, f"Policy rule '{self.name}' failed"
        except Exception as e:
            logger.warning(
                "policy_rule_evaluation_error",
                rule=self.name,
                error=str(e)
            )
            return False, f"Policy rule '{self.name}' error: {str(e)}"


@dataclass
class ConsensusConfig:
    """Configuration for consensus calculation."""
    # Quorum requirements
    min_votes: int = 3
    quorum_percentage: float = 0.1  # 10% of eligible voters

    # Threshold requirements
    approval_threshold: float = 0.6  # 60% for approval
    rejection_threshold: float = 0.4  # 40% to block

    # Trust weighting
    enable_trust_weighting: bool = True
    trust_weight_power: float = 1.5  # Higher = more weight to trusted

    # Time limits
    voting_period_hours: int = 72
    grace_period_hours: int = 24

    # Special rules
    require_core_approval: bool = False  # Require at least one CORE vote
    allow_abstentions: bool = True


@dataclass
class VoteRecord:
    """Record of a vote with trust context."""
    vote_id: str
    voter_id: str
    vote_type: VoteChoice
    trust_level: int
    weight: float
    timestamp: datetime
    comment: str | None = None


@dataclass
class ConsensusResult:
    """Result of consensus calculation."""
    status: VotingStatus

    # Vote counts
    total_votes: int = 0
    approve_votes: int = 0
    reject_votes: int = 0
    abstain_votes: int = 0

    # Weighted scores
    weighted_approve: float = 0.0
    weighted_reject: float = 0.0
    weighted_abstain: float = 0.0

    # Percentages
    approval_percentage: float = 0.0
    rejection_percentage: float = 0.0

    # Quorum
    quorum_met: bool = False
    quorum_needed: int = 0

    # Thresholds
    approval_threshold_met: bool = False
    rejection_threshold_met: bool = False

    # Core votes
    has_core_approval: bool = False
    has_core_rejection: bool = False

    # Timing
    voting_ends_at: datetime | None = None
    time_remaining_hours: float = 0.0

    # Ghost Council
    ghost_council_recommendation: str | None = None


@dataclass
class GovernanceDecision:
    """Final governance decision."""
    proposal_id: str
    decision: str  # "approved", "rejected", "pending", "expired"
    consensus: ConsensusResult
    policy_results: dict[str, tuple[bool, str | None]]
    effective_at: datetime | None = None
    rationale: str = ""


class GovernanceOverlay(BaseOverlay):
    """
    Governance overlay for symbolic decision-making.

    Manages the consensus phase of the pipeline, evaluating
    proposals against policies and calculating trust-weighted votes.
    """

    NAME = "governance"
    VERSION = "1.0.0"
    DESCRIPTION = "Symbolic governance, voting, and consensus"

    SUBSCRIBED_EVENTS = {
        EventType.PROPOSAL_CREATED,
        EventType.VOTE_CAST,
        EventType.GOVERNANCE_ACTION,
        EventType.TRUST_UPDATED,
    }

    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_PUBLISH
    }

    def __init__(
        self,
        consensus_config: ConsensusConfig | None = None,
        policy_rules: list[PolicyRule] | None = None,
        enable_ghost_council: bool = True,
        eligible_voters_provider: Callable[[], int] | None = None
    ):
        """
        Initialize the governance overlay.

        Args:
            consensus_config: Consensus calculation configuration
            policy_rules: Policy rules to enforce
            enable_ghost_council: Enable Ghost Council recommendations
            eligible_voters_provider: Function to get eligible voter count
        """
        super().__init__()

        self._config = consensus_config or ConsensusConfig()
        self._policies: list[PolicyRule] = policy_rules or []
        self._enable_ghost_council = enable_ghost_council
        self._eligible_voters_provider = eligible_voters_provider

        # Active votes cache
        self._active_proposals: dict[str, list[VoteRecord]] = {}

        # SECURITY FIX (Audit 2): Add locks to prevent race conditions
        self._proposals_lock = asyncio.Lock()  # Global lock for proposals dict
        self._proposal_locks: dict[str, asyncio.Lock] = {}  # Per-proposal locks

        # Statistics
        self._stats = {
            "proposals_evaluated": 0,
            "votes_processed": 0,
            "consensus_reached": 0,
            "policies_enforced": 0
        }
        self._stats_lock = asyncio.Lock()  # Lock for stats updates

        # Add default policies
        self._add_default_policies()

        self._logger = logger.bind(overlay=self.NAME)

    async def _get_proposal_lock(self, proposal_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific proposal."""
        async with self._proposals_lock:
            if proposal_id not in self._proposal_locks:
                self._proposal_locks[proposal_id] = asyncio.Lock()
            return self._proposal_locks[proposal_id]

    async def _update_stats(self, key: str, delta: int = 1) -> None:
        """Thread-safe stats update."""
        async with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + delta

    def _add_default_policies(self) -> None:
        """Add default governance policies using safe conditions."""
        # Trust threshold policy: proposer_trust >= STANDARD
        self._policies.append(PolicyRule(
            name="trust_threshold",
            description="Proposer must have sufficient trust",
            condition=SafeCondition(
                field="proposer_trust",
                operator=ConditionOperator.GE,
                value=TrustLevel.STANDARD.value
            ),
            required_trust=0,
            applies_to=[ProposalType.POLICY, ProposalType.SYSTEM]
        ))

        # Content policy: title AND description must exist
        self._policies.append(PolicyRule(
            name="proposal_content",
            description="Proposal must have title and description",
            condition=SafeCondition.and_conditions([
                SafeCondition("title", ConditionOperator.EXISTS),
                SafeCondition("description", ConditionOperator.EXISTS),
            ]),
            required_trust=0,
            applies_to=[]  # All types
        ))

        # Resource limits policy: estimated_resources <= 1000
        self._policies.append(PolicyRule(
            name="resource_limits",
            description="Proposal must not exceed resource limits",
            condition=SafeCondition(
                field="estimated_resources",
                operator=ConditionOperator.LE,
                value=1000
            ),
            required_trust=TrustLevel.TRUSTED.value,
            applies_to=[ProposalType.SYSTEM]
        ))

    async def initialize(self) -> bool:
        """Initialize the governance overlay."""
        self._logger.info(
            "governance_initialized",
            policies=len(self._policies),
            config={
                "approval_threshold": self._config.approval_threshold,
                "quorum_percentage": self._config.quorum_percentage,
                "voting_period_hours": self._config.voting_period_hours
            }
        )
        return True

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute governance processing.

        Args:
            context: Execution context
            event: Triggering event
            input_data: Data to process

        Returns:
            Governance result
        """
        import time
        start_time = time.time()

        data = input_data or {}
        if event:
            data.update(event.payload or {})
            data["event_type"] = event.type

        # Determine action based on event type
        if event:
            if event.type == EventType.PROPOSAL_CREATED:
                result = await self._handle_proposal_created(data, context)
            elif event.type == EventType.VOTE_CAST:
                result = await self._handle_vote_cast(data, context)
            elif event.type == EventType.GOVERNANCE_ACTION:
                result = await self._handle_governance_action(data, context)
            else:
                result = await self._evaluate_consensus(data, context)
        else:
            # Direct call - evaluate consensus
            result = await self._evaluate_consensus(data, context)

        duration_ms = (time.time() - start_time) * 1000

        self._logger.info(
            "governance_execution_complete",
            action=event.type.value if event else "evaluate",
            duration_ms=round(duration_ms, 2)
        )

        return result

    async def _handle_proposal_created(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> OverlayResult:
        """Handle new proposal creation."""
        proposal_id: str = str(data.get("proposal_id", ""))

        # Evaluate policies
        policy_results = self._evaluate_policies(data)
        all_passed = all(passed for passed, _ in policy_results.values())

        # SECURITY FIX (Audit 2): Use thread-safe stats update
        await self._update_stats("proposals_evaluated")
        await self._update_stats("policies_enforced", len(policy_results))

        if not all_passed:
            failed_policies = [
                name for name, (passed, _) in policy_results.items()
                if not passed
            ]
            return OverlayResult(
                success=False,
                error=f"Policy violations: {', '.join(failed_policies)}",
                data={
                    "proposal_id": proposal_id,
                    "policy_results": {
                        name: {"passed": passed, "error": error}
                        for name, (passed, error) in policy_results.items()
                    }
                },
                events_to_emit=[{
                    "event_type": EventType.GOVERNANCE_ACTION,
                    "payload": {
                        "action": "proposal_rejected",
                        "proposal_id": proposal_id,
                        "reason": "policy_violation"
                    }
                }]
            )

        # SECURITY FIX (Audit 2): Use lock for initializing proposal voting
        proposal_lock = await self._get_proposal_lock(proposal_id)
        async with proposal_lock:
            self._active_proposals[proposal_id] = []

        # Calculate voting end time
        voting_ends_at = datetime.now(UTC) + timedelta(
            hours=self._config.voting_period_hours
        )

        return OverlayResult(
            success=True,
            data={
                "proposal_id": proposal_id,
                "status": "voting_started",
                "policy_results": {
                    name: {"passed": passed, "error": error}
                    for name, (passed, error) in policy_results.items()
                },
                "voting_ends_at": voting_ends_at.isoformat(),
                "quorum_needed": self._calculate_quorum()
            },
            events_to_emit=[{
                "event_type": EventType.GOVERNANCE_ACTION,
                "payload": {
                    "action": "voting_started",
                    "proposal_id": proposal_id,
                    "voting_ends_at": voting_ends_at.isoformat()
                }
            }]
        )

    async def _handle_vote_cast(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> OverlayResult:
        """Handle vote being cast."""
        raw_proposal_id = data.get("proposal_id")
        voter_id: str = str(data.get("voter_id") or context.user_id or "anonymous")
        vote_type = VoteChoice(data.get("vote_type", "approve"))
        comment: str | None = data.get("comment")

        if not raw_proposal_id:
            return OverlayResult(
                success=False,
                error="Missing proposal_id"
            )
        proposal_id: str = str(raw_proposal_id)

        # Calculate vote weight based on trust
        trust_level = context.trust_flame
        weight = self._calculate_vote_weight(trust_level)

        # Record vote
        vote_record = VoteRecord(
            vote_id=f"vote_{voter_id}_{proposal_id}",
            voter_id=voter_id,
            vote_type=vote_type,
            trust_level=trust_level,
            weight=weight,
            timestamp=datetime.now(UTC),
            comment=comment
        )

        # SECURITY FIX (Audit 2): Use per-proposal lock to prevent race conditions
        proposal_lock = await self._get_proposal_lock(proposal_id)
        async with proposal_lock:
            # Store vote
            if proposal_id not in self._active_proposals:
                self._active_proposals[proposal_id] = []

            # Remove previous vote from same voter (atomic with lock)
            self._active_proposals[proposal_id] = [
                v for v in self._active_proposals[proposal_id]
                if v.voter_id != voter_id
            ]
            self._active_proposals[proposal_id].append(vote_record)

            # Get a copy of votes for consensus calculation
            votes_copy = list(self._active_proposals[proposal_id])

        # Update stats outside lock
        await self._update_stats("votes_processed")

        # Calculate current consensus with the copy
        consensus = self._calculate_consensus(
            votes_copy,
            data.get("created_at")
        )

        # Check if decision can be made
        decision = None
        if consensus.status in {
            VotingStatus.CONSENSUS_REACHED,
            VotingStatus.CONSENSUS_FAILED,
            VotingStatus.EXPIRED
        }:
            decision, consensus_reached = self._make_decision(proposal_id, consensus, {})
            # SECURITY FIX (Audit 2): Thread-safe stats update
            if consensus_reached:
                await self._update_stats("consensus_reached")

        return OverlayResult(
            success=True,
            data={
                "proposal_id": proposal_id,
                "vote_recorded": {
                    "voter_id": voter_id,
                    "vote_type": vote_type.value,
                    "weight": weight,
                    "trust_level": trust_level
                },
                "consensus": self._consensus_to_dict(consensus),
                "decision": decision.__dict__ if decision else None
            },
            events_to_emit=[{
                "event_type": EventType.VOTE_CAST,
                "payload": {
                    "proposal_id": proposal_id,
                    "voter_id": voter_id,
                    "vote_type": vote_type.value,
                    "consensus_status": consensus.status.value
                }
            }]
        )

    async def _handle_governance_action(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> OverlayResult:
        """Handle governance actions."""
        action = data.get("action")
        proposal_id: str = str(data.get("proposal_id", ""))

        if action == "check_consensus":
            return await self._evaluate_consensus(data, context)

        elif action == "close_voting":
            # SECURITY FIX (Audit 2): Use lock for closing voting
            proposal_lock = await self._get_proposal_lock(proposal_id)
            decision = None
            consensus_reached = False
            async with proposal_lock:
                if proposal_id in self._active_proposals:
                    votes = list(self._active_proposals[proposal_id])
                    consensus = self._calculate_consensus(votes, data.get("created_at"))
                    decision, consensus_reached = self._make_decision(proposal_id, consensus, {})

                    # Clean up
                    del self._active_proposals[proposal_id]

            if decision:
                # SECURITY FIX (Audit 2): Thread-safe stats update outside lock
                if consensus_reached:
                    await self._update_stats("consensus_reached")

                return OverlayResult(
                    success=True,
                    data={
                        "action": "voting_closed",
                        "proposal_id": proposal_id,
                        "decision": decision.__dict__
                    }
                )

        elif action == "execute_proposal":
            # SECURITY FIX (Audit 3): Enforce timelock before execution
            from datetime import datetime as dt

            execution_allowed_after = data.get("execution_allowed_after")
            if execution_allowed_after:
                # Parse the datetime if it's a string
                if isinstance(execution_allowed_after, str):
                    try:
                        execution_allowed_after = dt.fromisoformat(execution_allowed_after.replace('Z', '+00:00'))
                    except ValueError:
                        return OverlayResult(
                            success=False,
                            error="Invalid execution_allowed_after format"
                        )

                now = dt.now(UTC)
                if execution_allowed_after.tzinfo is None:
                    execution_allowed_after = execution_allowed_after.replace(tzinfo=UTC)

                if now < execution_allowed_after:
                    remaining_seconds = int((execution_allowed_after - now).total_seconds())
                    self._logger.warning(
                        "proposal_execution_blocked_timelock",
                        proposal_id=proposal_id,
                        remaining_seconds=remaining_seconds
                    )
                    return OverlayResult(
                        success=False,
                        error=f"Proposal execution blocked: timelock has {remaining_seconds} seconds remaining",
                        data={
                            "timelock_remaining_seconds": remaining_seconds,
                            "execution_allowed_after": execution_allowed_after.isoformat()
                        }
                    )

            # Timelock passed or not set - proceed with execution
            self._logger.info(
                "proposal_execution_allowed",
                proposal_id=proposal_id
            )
            await self._update_stats("proposals_executed")

            return OverlayResult(
                success=True,
                data={
                    "action": "proposal_executed",
                    "proposal_id": proposal_id
                }
            )

        return OverlayResult(
            success=False,
            error=f"Unknown action: {action}"
        )

    async def _evaluate_consensus(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> OverlayResult:
        """Evaluate current consensus state."""
        raw_proposal_id = data.get("proposal_id")

        if not raw_proposal_id:
            # SECURITY FIX (Audit 2): Use lock for reading all proposals
            async with self._proposals_lock:
                active_summary: dict[str, dict[str, Any]] = {}
                for pid, votes in self._active_proposals.items():
                    consensus = self._calculate_consensus(list(votes), None)
                    active_summary[pid] = self._consensus_to_dict(consensus)
                num_active = len(self._active_proposals)

            return OverlayResult(
                success=True,
                data={
                    "active_proposals": num_active,
                    "summary": active_summary
                }
            )

        proposal_id: str = str(raw_proposal_id)

        # SECURITY FIX (Audit 2): Use per-proposal lock for reading votes
        proposal_lock = await self._get_proposal_lock(proposal_id)
        async with proposal_lock:
            votes = list(self._active_proposals.get(proposal_id, []))
        consensus = self._calculate_consensus(votes, data.get("created_at"))

        # Get Ghost Council recommendation if enabled
        if self._enable_ghost_council:
            consensus.ghost_council_recommendation = self._get_ghost_council_recommendation(
                data, consensus
            )

        return OverlayResult(
            success=True,
            data={
                "proposal_id": proposal_id,
                "consensus": self._consensus_to_dict(consensus),
                "votes": [
                    {
                        "voter_id": v.voter_id,
                        "vote_type": v.vote_type.value,
                        "weight": v.weight,
                        "timestamp": v.timestamp.isoformat()
                    }
                    for v in votes
                ]
            }
        )

    def _evaluate_policies(self, data: dict[str, Any]) -> dict[str, tuple[bool, str | None]]:
        """Evaluate all applicable policies."""
        results = {}
        proposal_type = data.get("proposal_type")

        for policy in self._policies:
            # Check if policy applies to this proposal type
            if policy.applies_to and proposal_type:
                if ProposalType(proposal_type) not in policy.applies_to:
                    continue

            passed, error = policy.evaluate(data)
            results[policy.name] = (passed, error)

        return results

    def _calculate_vote_weight(self, trust_level: int) -> float:
        """
        Calculate vote weight based on trust level.

        SECURITY FIX (Audit 4 - H11): Clamp trust values to 0-100 range
        to prevent trust_level > 100 from producing weights > 1.0,
        which would give unfair vote amplification.
        """
        if not self._config.enable_trust_weighting:
            return 1.0

        # SECURITY FIX: Clamp trust to valid range to prevent amplification
        clamped_trust = max(0, min(trust_level, 100))

        # Normalize trust to 0-1 range
        normalized = clamped_trust / 100.0

        # Apply power function for weighting
        weight = math.pow(normalized, self._config.trust_weight_power)

        # Ensure minimum weight and maximum weight
        # Maximum weight is 1.0 to prevent any amplification beyond equal voting
        return max(0.1, min(weight, 1.0))

    def _calculate_quorum(self) -> int:
        """Calculate required quorum."""
        if self._eligible_voters_provider:
            eligible = self._eligible_voters_provider()
            return max(
                self._config.min_votes,
                int(eligible * self._config.quorum_percentage)
            )
        return self._config.min_votes

    def _calculate_consensus(
        self,
        votes: list[VoteRecord],
        proposal_created_at: str | None
    ) -> ConsensusResult:
        """Calculate consensus from votes."""
        result = ConsensusResult(status=VotingStatus.IN_PROGRESS)

        if not votes:
            result.status = VotingStatus.NOT_STARTED
            result.quorum_needed = self._calculate_quorum()
            return result

        # Count votes
        result.total_votes = len(votes)
        result.approve_votes = sum(1 for v in votes if v.vote_type == VoteChoice.APPROVE)
        result.reject_votes = sum(1 for v in votes if v.vote_type == VoteChoice.REJECT)
        result.abstain_votes = sum(1 for v in votes if v.vote_type == VoteChoice.ABSTAIN)

        # Calculate weighted scores
        result.weighted_approve = sum(
            v.weight for v in votes if v.vote_type == VoteChoice.APPROVE
        )
        result.weighted_reject = sum(
            v.weight for v in votes if v.vote_type == VoteChoice.REJECT
        )
        result.weighted_abstain = sum(
            v.weight for v in votes if v.vote_type == VoteChoice.ABSTAIN
        )

        total_weight = result.weighted_approve + result.weighted_reject
        if self._config.allow_abstentions:
            total_weight += result.weighted_abstain

        # Calculate percentages
        if total_weight > 0:
            result.approval_percentage = result.weighted_approve / total_weight
            result.rejection_percentage = result.weighted_reject / total_weight

        # Check quorum
        result.quorum_needed = self._calculate_quorum()
        result.quorum_met = result.total_votes >= result.quorum_needed

        # Check thresholds
        result.approval_threshold_met = result.approval_percentage >= self._config.approval_threshold
        result.rejection_threshold_met = result.rejection_percentage >= self._config.rejection_threshold

        # Check core votes
        core_votes = [v for v in votes if v.trust_level >= TrustLevel.CORE.value]
        result.has_core_approval = any(v.vote_type == VoteChoice.APPROVE for v in core_votes)
        result.has_core_rejection = any(v.vote_type == VoteChoice.REJECT for v in core_votes)

        # Calculate voting end time
        if proposal_created_at:
            try:
                created = datetime.fromisoformat(proposal_created_at.replace('Z', '+00:00'))
                result.voting_ends_at = created + timedelta(hours=self._config.voting_period_hours)
                remaining = result.voting_ends_at - datetime.now(UTC)
                result.time_remaining_hours = max(0, remaining.total_seconds() / 3600)
            except (ValueError, TypeError):
                pass

        # Determine final status
        if result.voting_ends_at and datetime.now(UTC) > result.voting_ends_at:
            if result.quorum_met:
                if result.approval_threshold_met:
                    result.status = VotingStatus.CONSENSUS_REACHED
                else:
                    result.status = VotingStatus.CONSENSUS_FAILED
            else:
                result.status = VotingStatus.EXPIRED
        elif result.quorum_met:
            result.status = VotingStatus.QUORUM_REACHED

            # Check if early consensus possible
            if result.approval_percentage >= 0.8:  # Supermajority
                result.status = VotingStatus.CONSENSUS_REACHED
            elif result.rejection_percentage >= 0.8:
                result.status = VotingStatus.CONSENSUS_FAILED

        # Special: Core rejection blocks
        if self._config.require_core_approval and result.has_core_rejection:
            result.status = VotingStatus.CONSENSUS_FAILED

        # NOTE: Stats update moved to _make_decision to avoid double-counting
        return result

    def _make_decision(
        self,
        proposal_id: str,
        consensus: ConsensusResult,
        policy_results: dict[str, tuple[bool, str | None]]
    ) -> tuple[GovernanceDecision, bool]:
        """
        Make final governance decision.

        Returns:
            Tuple of (decision, consensus_reached) where consensus_reached indicates
            if stats should be updated (caller should call _update_stats).
        """
        consensus_reached = False
        if consensus.status == VotingStatus.CONSENSUS_REACHED:
            decision_str = "approved"
            rationale = f"Consensus reached with {consensus.approval_percentage:.1%} approval"
            consensus_reached = True
        elif consensus.status == VotingStatus.CONSENSUS_FAILED:
            decision_str = "rejected"
            rationale = f"Consensus failed - {consensus.rejection_percentage:.1%} rejection"
        elif consensus.status == VotingStatus.EXPIRED:
            decision_str = "expired"
            rationale = "Voting period expired without quorum"
        else:
            decision_str = "pending"
            rationale = f"Voting in progress - {consensus.total_votes} votes cast"

        decision = GovernanceDecision(
            proposal_id=proposal_id,
            decision=decision_str,
            consensus=consensus,
            policy_results=policy_results,
            effective_at=datetime.now(UTC) if decision_str == "approved" else None,
            rationale=rationale
        )
        return decision, consensus_reached

    def _get_ghost_council_recommendation(
        self,
        data: dict[str, Any],
        consensus: ConsensusResult
    ) -> str:
        """
        Get Ghost Council recommendation.

        The Ghost Council represents the collective wisdom of
        historical decisions. This is a simplified implementation.
        """
        # Simple heuristic based on proposal type and consensus
        data.get("proposal_type", "general")

        if consensus.total_votes < 3:
            return "AWAIT_MORE_VOTES: Insufficient data for recommendation"

        if consensus.has_core_rejection:
            return "CAUTION: Core member has expressed concerns"

        if consensus.approval_percentage > 0.7:
            return "FAVORABLE: Strong community support detected"
        elif consensus.rejection_percentage > 0.5:
            return "UNFAVORABLE: Significant opposition exists"
        else:
            return "NEUTRAL: Community divided - consider amendments"

    def _consensus_to_dict(self, consensus: ConsensusResult) -> dict[str, Any]:
        """Convert consensus result to dictionary."""
        return {
            "status": consensus.status.value,
            "total_votes": consensus.total_votes,
            "approve_votes": consensus.approve_votes,
            "reject_votes": consensus.reject_votes,
            "abstain_votes": consensus.abstain_votes,
            "weighted_approve": round(consensus.weighted_approve, 3),
            "weighted_reject": round(consensus.weighted_reject, 3),
            "approval_percentage": round(consensus.approval_percentage, 3),
            "rejection_percentage": round(consensus.rejection_percentage, 3),
            "quorum_met": consensus.quorum_met,
            "quorum_needed": consensus.quorum_needed,
            "approval_threshold_met": consensus.approval_threshold_met,
            "has_core_approval": consensus.has_core_approval,
            "has_core_rejection": consensus.has_core_rejection,
            "voting_ends_at": consensus.voting_ends_at.isoformat() if consensus.voting_ends_at else None,
            "time_remaining_hours": round(consensus.time_remaining_hours, 1),
            "ghost_council_recommendation": consensus.ghost_council_recommendation
        }

    def add_policy(self, policy: PolicyRule) -> None:
        """
        Add a governance policy.

        SECURITY: Validates that the policy uses SafeCondition, not arbitrary callables.
        """
        # SECURITY: Ensure condition is a SafeCondition, not an arbitrary callable
        if not isinstance(policy.condition, SafeCondition):
            raise PolicyViolationError(
                f"Policy '{policy.name}' must use SafeCondition, not arbitrary callables. "
                "This is a security requirement to prevent code injection."
            )

        # Validate SafeCondition structure
        self._validate_safe_condition(policy.condition)

        self._policies.append(policy)
        self._logger.info(
            "policy_added",
            policy_name=policy.name,
            description=policy.description
        )

    def _validate_safe_condition(self, condition: SafeCondition, depth: int = 0) -> None:
        """
        Recursively validate a SafeCondition structure.

        SECURITY: Prevents malformed conditions and limits recursion depth.
        """
        # Limit recursion depth to prevent stack overflow attacks
        MAX_DEPTH = 10
        if depth > MAX_DEPTH:
            raise PolicyViolationError(
                f"SafeCondition nesting depth exceeds maximum of {MAX_DEPTH}"
            )

        # Validate operator is from our enum (not an arbitrary value)
        if not isinstance(condition.operator, ConditionOperator):
            raise PolicyViolationError(
                f"Invalid condition operator: {condition.operator}"
            )

        # For logical operators, validate sub-conditions
        if condition.operator in (ConditionOperator.AND, ConditionOperator.OR):
            if condition.sub_conditions:
                for sub in condition.sub_conditions:
                    if not isinstance(sub, SafeCondition):
                        raise PolicyViolationError(
                            "Sub-conditions must be SafeCondition instances"
                        )
                    self._validate_safe_condition(sub, depth + 1)
        else:
            # For comparison operators, validate field name
            if not isinstance(condition.field, str) or not condition.field:
                raise PolicyViolationError(
                    "Condition field must be a non-empty string"
                )

            # SECURITY: Block potentially dangerous field patterns
            dangerous_patterns = ["..", "__", "\\", "/", "\x00"]
            for pattern in dangerous_patterns:
                if pattern in condition.field:
                    raise PolicyViolationError(
                        f"Condition field contains forbidden pattern: {pattern}"
                    )

    def remove_policy(self, policy_name: str) -> bool:
        """Remove a policy by name."""
        for i, policy in enumerate(self._policies):
            if policy.name == policy_name:
                self._policies.pop(i)
                return True
        return False

    def get_policies(self) -> list[dict[str, Any]]:
        """Get all policies."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "required_trust": p.required_trust,
                "applies_to": [t.value for t in p.applies_to]
            }
            for p in self._policies
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get governance statistics."""
        return {
            **self._stats,
            "active_proposals": len(self._active_proposals),
            "policies_count": len(self._policies)
        }


# Convenience function
def create_governance_overlay(
    strict_mode: bool = False,
    **kwargs: Any
) -> GovernanceOverlay:
    """
    Create a governance overlay.

    Args:
        strict_mode: If True, uses stricter consensus requirements
        **kwargs: Additional configuration

    Returns:
        Configured GovernanceOverlay
    """
    if strict_mode:
        config = ConsensusConfig(
            min_votes=5,
            quorum_percentage=0.2,
            approval_threshold=0.7,
            require_core_approval=True
        )
        kwargs["consensus_config"] = config

    return GovernanceOverlay(**kwargs)
