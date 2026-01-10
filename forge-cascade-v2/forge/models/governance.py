"""
Governance Models

Democratic decision-making with trust-weighted voting,
Constitutional AI ethical review, and Ghost Council.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.models.base import (
    ForgeModel,
    ProposalStatus,
    TimestampMixin,
    generate_id,
)


class ProposalType(str, Enum):
    """Types of governance proposals."""

    POLICY = "policy"               # Policy changes
    SYSTEM = "system"               # System configuration
    OVERLAY = "overlay"             # Overlay management
    CAPSULE = "capsule"             # Capsule governance
    TRUST = "trust"                 # Trust level changes
    CONSTITUTIONAL = "constitutional"  # Constitutional amendments


# SECURITY FIX (Audit 3): Define valid actions for each proposal type
VALID_PROPOSAL_ACTIONS: dict[ProposalType, set[str]] = {
    ProposalType.POLICY: {"update_policy", "create_policy", "remove_policy"},
    ProposalType.SYSTEM: {"update_config", "enable_feature", "disable_feature", "set_limit"},
    ProposalType.OVERLAY: {"enable_overlay", "disable_overlay", "update_overlay_config"},
    ProposalType.CAPSULE: {"archive", "unarchive", "change_trust", "delete", "promote"},
    ProposalType.TRUST: {"adjust_trust", "set_trust_level", "reset_trust"},
    ProposalType.CONSTITUTIONAL: {"amend_constitution", "add_principle", "remove_principle"},
}

# Required fields for each action type
REQUIRED_ACTION_FIELDS: dict[str, list[str]] = {
    "update_policy": ["policy_id", "changes"],
    "create_policy": ["name", "rules"],
    "remove_policy": ["policy_id"],
    "update_config": ["config_key", "new_value"],
    "enable_feature": ["feature_name"],
    "disable_feature": ["feature_name"],
    "set_limit": ["limit_name", "limit_value"],
    "enable_overlay": ["overlay_name"],
    "disable_overlay": ["overlay_name"],
    "update_overlay_config": ["overlay_name", "config"],
    "archive": ["target_id"],
    "unarchive": ["target_id"],
    "change_trust": ["target_id", "new_trust"],
    "delete": ["target_id", "reason"],
    "promote": ["target_id", "new_type"],
    "adjust_trust": ["user_id", "adjustment", "reason"],
    "set_trust_level": ["user_id", "level"],
    "reset_trust": ["user_id"],
    "amend_constitution": ["article_id", "new_text"],
    "add_principle": ["principle_text", "category"],
    "remove_principle": ["principle_id", "justification"],
}


class VoteChoice(str, Enum):
    """
    Vote options - matches frontend VoteChoice type.

    SECURITY FIX (Audit 4 - M17): FOR and AGAINST are aliases that point to
    APPROVE and REJECT respectively. Use the canonical names (APPROVE/REJECT)
    in new code, and use from_string() for safe conversion from input strings.
    """

    APPROVE = "APPROVE"  # Frontend expects uppercase
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"

    # Aliases for backwards compatibility (same values = enum aliases)
    FOR = "APPROVE"
    AGAINST = "REJECT"

    @classmethod
    def from_string(cls, value: str) -> "VoteChoice":
        """
        SECURITY FIX (Audit 4 - M17): Safe conversion from string to VoteChoice.

        Handles both canonical names (APPROVE, REJECT, ABSTAIN) and legacy
        aliases (FOR, AGAINST). Always returns canonical member.

        Args:
            value: String value to convert

        Returns:
            VoteChoice enum member

        Raises:
            ValueError: If value is not a valid vote choice
        """
        if not isinstance(value, str):
            raise ValueError(f"VoteChoice must be string, got {type(value)}")

        # Normalize to uppercase for case-insensitive matching
        normalized = value.strip().upper()

        # Handle legacy aliases explicitly
        alias_map = {
            "FOR": "APPROVE",
            "AGAINST": "REJECT",
            "YES": "APPROVE",  # Common alternative
            "NO": "REJECT",    # Common alternative
        }

        # Map alias to canonical value
        canonical = alias_map.get(normalized, normalized)

        # Validate and return
        try:
            return cls(canonical)
        except ValueError as exc:
            valid_choices = ["APPROVE", "REJECT", "ABSTAIN", "FOR", "AGAINST", "YES", "NO"]
            raise ValueError(
                f"Invalid vote choice '{value}'. Valid choices: {valid_choices}"
            ) from exc


class ProposalBase(ForgeModel):
    """Base proposal fields."""

    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=20, max_length=10000)
    type: ProposalType = Field(default=ProposalType.POLICY)

    # Execution details
    action: dict[str, Any] = Field(
        default_factory=dict,
        description="Action to execute if passed",
    )

    @field_validator("action", mode="before")
    @classmethod
    def parse_action(cls, v: Any) -> dict[str, Any]:
        """Handle action being stored as JSON string in database."""
        import json
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v if v else {}


class ProposalCreate(ProposalBase):
    """Schema for creating a proposal."""

    voting_period_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Duration of voting period",
    )
    quorum_percent: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="Minimum participation required",
    )
    pass_threshold: float = Field(
        default=0.5,
        ge=0.5,
        le=1.0,
        description="Approval ratio needed to pass",
    )

    @model_validator(mode="after")
    def validate_action_for_type(self) -> "ProposalCreate":
        """
        SECURITY FIX (Audit 3): Validate action is appropriate for proposal type.

        Ensures:
        1. Action type is valid for the proposal type
        2. Required fields are present
        3. No unknown fields that could cause execution issues
        """
        if not self.action:
            return self  # Empty action is allowed (informational proposals)

        action_type = self.action.get("type")
        if not action_type:
            return self  # No action type means informational proposal

        # Validate action type is allowed for this proposal type
        valid_actions = VALID_PROPOSAL_ACTIONS.get(self.type, set())
        if action_type not in valid_actions:
            raise ValueError(
                f"Action '{action_type}' is not valid for proposal type '{self.type.value}'. "
                f"Valid actions: {', '.join(sorted(valid_actions))}"
            )

        # Validate required fields are present
        required_fields = REQUIRED_ACTION_FIELDS.get(action_type, [])
        missing_fields = [f for f in required_fields if f not in self.action]
        if missing_fields:
            raise ValueError(
                f"Action '{action_type}' is missing required fields: {', '.join(missing_fields)}"
            )

        # Validate no dangerous fields
        dangerous_fields = {"__import__", "eval", "exec", "compile", "globals", "locals"}
        found_dangerous = dangerous_fields & set(self.action.keys())
        if found_dangerous:
            raise ValueError(f"Action contains forbidden fields: {', '.join(found_dangerous)}")

        return self


class Proposal(ProposalBase, TimestampMixin):
    """Complete proposal schema."""

    id: str
    proposer_id: str
    status: ProposalStatus = Field(default=ProposalStatus.DRAFT)

    # Voting configuration
    voting_period_days: int = 7
    quorum_percent: float = 0.1
    pass_threshold: float = 0.5

    # Voting results
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    weight_for: float = 0.0
    weight_against: float = 0.0
    weight_abstain: float = 0.0

    # Timestamps
    voting_starts_at: datetime | None = None
    voting_ends_at: datetime | None = None
    executed_at: datetime | None = None

    # SECURITY FIX (Audit 3): Timelock - delay between passing and execution
    execution_allowed_after: datetime | None = None  # When proposal can be executed
    timelock_hours: int = 24  # Default 24 hour delay

    # Constitutional AI
    constitutional_review: "ConstitutionalAnalysis | None" = None
    ghost_council_opinion: "GhostCouncilOpinion | None" = None

    @property
    def total_votes(self) -> int:
        """Total number of votes cast."""
        return self.votes_for + self.votes_against + self.votes_abstain

    @property
    def total_weight(self) -> float:
        """Total voting weight."""
        return self.weight_for + self.weight_against + self.weight_abstain

    @property
    def approval_ratio(self) -> float:
        """Calculate approval ratio (excluding abstentions)."""
        decisive_weight = self.weight_for + self.weight_against
        if decisive_weight == 0:
            return 0.0
        return self.weight_for / decisive_weight

    @property
    def is_voting_open(self) -> bool:
        """Check if voting is currently open."""
        if self.status != ProposalStatus.VOTING:
            return False
        now = datetime.now(UTC)
        # Make comparison timezone-safe
        starts = self.voting_starts_at
        ends = self.voting_ends_at
        if starts and starts.tzinfo is None:
            starts = starts.replace(tzinfo=UTC)
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)
        return (
            starts is not None
            and ends is not None
            and starts <= now <= ends
        )

    @property
    def is_execution_allowed(self) -> bool:
        """
        SECURITY FIX (Audit 3): Check if proposal can be executed (timelock passed).

        Returns True if:
        - Status is PASSED
        - execution_allowed_after is set and has passed
        """
        if self.status != ProposalStatus.PASSED:
            return False
        if self.execution_allowed_after is None:
            return False
        now = datetime.now(UTC)
        allowed_after = self.execution_allowed_after
        if allowed_after.tzinfo is None:
            allowed_after = allowed_after.replace(tzinfo=UTC)
        return now >= allowed_after

    @property
    def timelock_remaining_seconds(self) -> int | None:
        """
        SECURITY FIX (Audit 3): Get remaining timelock seconds.

        Returns None if not in PASSED status or timelock already passed.
        """
        if self.status != ProposalStatus.PASSED:
            return None
        if self.execution_allowed_after is None:
            return None
        now = datetime.now(UTC)
        allowed_after = self.execution_allowed_after
        if allowed_after.tzinfo is None:
            allowed_after = allowed_after.replace(tzinfo=UTC)
        remaining = (allowed_after - now).total_seconds()
        return max(0, int(remaining))


class VoteCreate(ForgeModel):
    """Schema for casting a vote."""

    choice: VoteChoice
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional reason for vote",
    )


class Vote(ForgeModel, TimestampMixin):
    """Complete vote schema."""

    id: str
    proposal_id: str
    voter_id: str
    choice: VoteChoice
    weight: float = Field(
        ge=0.0,
        description="Voting weight based on trust flame",
    )
    reason: str | None = None

    # Delegation
    delegated_from: str | None = Field(
        default=None,
        description="ID of user who delegated their vote",
    )


class VoteDelegation(ForgeModel):
    """Vote delegation to another user."""

    id: str = Field(default_factory=generate_id, description="Delegation ID")
    delegator_id: str
    delegate_id: str
    proposal_types: list[ProposalType] | None = Field(
        default=None,
        description="Types to delegate (None = all)",
    )
    is_active: bool = Field(default=True, description="Whether delegation is active")
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════
# CONSTITUTIONAL AI
# ═══════════════════════════════════════════════════════════════


class EthicalConcern(ForgeModel):
    """An ethical concern identified by Constitutional AI."""

    category: str = Field(description="Category of concern")
    severity: str = Field(
        description="low, medium, high, critical",
    )
    description: str
    recommendation: str


class ConstitutionalAnalysis(ForgeModel):
    """Constitutional AI ethical review of a proposal."""

    proposal_id: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    # Scores (0-100)
    ethical_score: int = Field(ge=0, le=100)
    fairness_score: int = Field(ge=0, le=100)
    safety_score: int = Field(ge=0, le=100)
    transparency_score: int = Field(ge=0, le=100)

    # Analysis
    concerns: list[EthicalConcern] = Field(default_factory=list)
    summary: str
    recommendation: str = Field(
        description="approve, review, reject",
    )

    # Confidence
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in analysis",
    )

    @property
    def overall_score(self) -> float:
        """Calculate overall ethical score."""
        return (
            self.ethical_score
            + self.fairness_score
            + self.safety_score
            + self.transparency_score
        ) / 4.0


# ═══════════════════════════════════════════════════════════════
# GHOST COUNCIL
# ═══════════════════════════════════════════════════════════════


class PerspectiveType(str, Enum):
    """The three perspectives each council member must consider."""

    OPTIMISTIC = "optimistic"   # Best-case scenario, benefits, opportunities
    BALANCED = "balanced"       # Objective analysis, trade-offs, facts
    CRITICAL = "critical"       # Risks, concerns, worst-case scenarios


class PerspectiveAnalysis(ForgeModel):
    """A single perspective analysis from a council member."""

    perspective_type: PerspectiveType
    assessment: str = Field(description="Analysis from this perspective")
    key_points: list[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)


class GhostCouncilMember(ForgeModel):
    """A member of the Ghost Council (AI advisory board)."""

    id: str
    name: str
    role: str = Field(description="e.g., Ethics Advisor, Technical Expert")
    domain: str = Field(default="general", description="Area of expertise")
    persona: str = Field(description="AI persona description")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Voting weight in council",
    )
    icon: str = Field(default="user", description="Icon identifier for UI")


class GhostCouncilVote(ForgeModel):
    """A Ghost Council member's vote on a proposal with tri-perspective analysis."""

    member_id: str
    member_name: str
    member_role: str = Field(default="Advisor")

    # The three perspectives (each member analyzes from all three angles)
    perspectives: list[PerspectiveAnalysis] = Field(
        default_factory=list,
        description="Analysis from optimistic, balanced, and critical viewpoints",
    )

    # Final synthesized position after considering all perspectives
    vote: VoteChoice
    reasoning: str = Field(description="Synthesized reasoning considering all perspectives")
    confidence: float = Field(ge=0.0, le=1.0)

    # Key concerns and benefits identified across perspectives
    primary_benefits: list[str] = Field(default_factory=list, max_length=3)
    primary_concerns: list[str] = Field(default_factory=list, max_length=3)


class GhostCouncilOpinion(ForgeModel):
    """Collective opinion from the Ghost Council with multi-perspective analysis."""

    proposal_id: str
    deliberated_at: datetime = Field(default_factory=datetime.utcnow)

    # Member votes with full perspective analysis
    member_votes: list[GhostCouncilVote] = Field(default_factory=list)

    # Consensus
    consensus_vote: VoteChoice
    consensus_strength: float = Field(
        ge=0.0,
        le=1.0,
        description="How strong the consensus is",
    )

    # Aggregated perspective summaries
    optimistic_summary: str = Field(
        default="",
        description="Aggregated best-case analysis from all members",
    )
    balanced_summary: str = Field(
        default="",
        description="Aggregated objective analysis from all members",
    )
    critical_summary: str = Field(
        default="",
        description="Aggregated risk analysis from all members",
    )

    # Summary
    key_points: list[str] = Field(default_factory=list)
    dissenting_opinions: list[str] = Field(default_factory=list)
    final_recommendation: str

    # Aggregate metrics
    total_benefits_identified: int = Field(default=0)
    total_concerns_identified: int = Field(default=0)


# ═══════════════════════════════════════════════════════════════
# GOVERNANCE STATS
# ═══════════════════════════════════════════════════════════════


class GovernanceStats(ForgeModel):
    """Governance system statistics."""

    total_proposals: int = 0
    active_proposals: int = 0
    passed_proposals: int = 0
    rejected_proposals: int = 0
    total_votes: int = 0
    unique_voters: int = 0
    average_participation: float = 0.0
    average_approval_ratio: float = 0.0
