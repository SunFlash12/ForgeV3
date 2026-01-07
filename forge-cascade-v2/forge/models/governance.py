"""
Governance Models

Democratic decision-making with trust-weighted voting,
Constitutional AI ethical review, and Ghost Council.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from forge.models.base import (
    ForgeModel,
    TimestampMixin,
    ProposalStatus,
)


class ProposalType(str, Enum):
    """Types of governance proposals."""

    POLICY = "policy"               # Policy changes
    SYSTEM = "system"               # System configuration
    OVERLAY = "overlay"             # Overlay management
    CAPSULE = "capsule"             # Capsule governance
    TRUST = "trust"                 # Trust level changes
    CONSTITUTIONAL = "constitutional"  # Constitutional amendments


class VoteChoice(str, Enum):
    """Vote options - matches frontend VoteChoice type."""

    APPROVE = "APPROVE"  # Frontend expects uppercase
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"

    # Aliases for backwards compatibility
    FOR = "APPROVE"
    AGAINST = "REJECT"


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
        from datetime import timezone
        if self.status != ProposalStatus.VOTING:
            return False
        now = datetime.now(timezone.utc)
        # Make comparison timezone-safe
        starts = self.voting_starts_at
        ends = self.voting_ends_at
        if starts and starts.tzinfo is None:
            starts = starts.replace(tzinfo=timezone.utc)
        if ends and ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        return (
            starts is not None
            and ends is not None
            and starts <= now <= ends
        )


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

    id: str = Field(default="", description="Delegation ID")
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


class GhostCouncilMember(ForgeModel):
    """A member of the Ghost Council (AI advisory board)."""

    id: str
    name: str
    role: str = Field(description="e.g., Ethics Advisor, Technical Expert")
    persona: str = Field(description="AI persona description")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Voting weight in council",
    )


class GhostCouncilVote(ForgeModel):
    """A Ghost Council member's vote on a proposal."""

    member_id: str
    member_name: str
    vote: VoteChoice
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class GhostCouncilOpinion(ForgeModel):
    """Collective opinion from the Ghost Council."""

    proposal_id: str
    deliberated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Member votes
    member_votes: list[GhostCouncilVote] = Field(default_factory=list)
    
    # Consensus
    consensus_vote: VoteChoice
    consensus_strength: float = Field(
        ge=0.0,
        le=1.0,
        description="How strong the consensus is",
    )
    
    # Summary
    key_points: list[str] = Field(default_factory=list)
    dissenting_opinions: list[str] = Field(default_factory=list)
    final_recommendation: str


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
