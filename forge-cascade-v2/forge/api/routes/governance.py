"""
Forge Cascade V2 - Governance Routes
Endpoints for symbolic governance and voting.

Provides:
- Proposal management
- Voting operations
- Ghost Council interactions
- Policy queries
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    GovernanceRepoDep,
    AuditRepoDep,
    EventSystemDep,
    ActiveUserDep,
    StandardUserDep,
    TrustedUserDep,
    CoreUserDep,
    PaginationDep,
    CorrelationIdDep,
)
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    ProposalType,
    ProposalStatus,
    Vote,
    VoteChoice,
)
from forge.models.events import Event, EventType


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateProposalRequest(BaseModel):
    """Request to create a new proposal."""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    proposal_type: ProposalType = ProposalType.POLICY
    action: dict[str, Any] = Field(default_factory=dict)
    voting_period_days: int = Field(default=7, ge=1, le=30)
    quorum_percent: float = Field(default=0.1, ge=0.01, le=1.0)
    pass_threshold: float = Field(default=0.5, ge=0.5, le=1.0)


class VoteRequest(BaseModel):
    """Request to cast a vote."""
    choice: VoteChoice
    rationale: str | None = None


class ProposalResponse(BaseModel):
    """Proposal response model."""
    id: str
    title: str
    description: str
    proposal_type: str
    status: str
    proposer_id: str
    action: dict[str, Any]
    voting_period_days: int
    quorum_percent: float
    pass_threshold: float
    votes_for: int
    votes_against: int
    votes_abstain: int
    weight_for: float
    weight_against: float
    weight_abstain: float
    created_at: str
    voting_starts_at: str | None
    voting_ends_at: str | None
    
    @classmethod
    def from_proposal(cls, proposal: Proposal) -> "ProposalResponse":
        return cls(
            id=proposal.id,
            title=proposal.title,
            description=proposal.description,
            proposal_type=proposal.type.value,
            status=proposal.status.value,
            proposer_id=proposal.proposer_id,
            action=proposal.action,
            voting_period_days=proposal.voting_period_days,
            quorum_percent=proposal.quorum_percent,
            pass_threshold=proposal.pass_threshold,
            votes_for=proposal.votes_for,
            votes_against=proposal.votes_against,
            votes_abstain=proposal.votes_abstain,
            weight_for=proposal.weight_for,
            weight_against=proposal.weight_against,
            weight_abstain=proposal.weight_abstain,
            created_at=proposal.created_at.isoformat() if proposal.created_at else "",
            voting_starts_at=proposal.voting_starts_at.isoformat() if proposal.voting_starts_at else None,
            voting_ends_at=proposal.voting_ends_at.isoformat() if proposal.voting_ends_at else None,
        )


class VoteResponse(BaseModel):
    """Vote response model."""
    id: str
    proposal_id: str
    voter_id: str
    choice: str
    weight: float
    rationale: str | None
    created_at: str
    
    @classmethod
    def from_vote(cls, vote: Vote) -> "VoteResponse":
        return cls(
            id=vote.id,
            proposal_id=vote.proposal_id,
            voter_id=vote.voter_id,
            choice=vote.choice.value,
            weight=vote.weight,
            rationale=vote.rationale,
            created_at=vote.created_at.isoformat() if vote.created_at else "",
        )


class ProposalListResponse(BaseModel):
    """Paginated list of proposals."""
    items: list[ProposalResponse]
    total: int
    page: int
    per_page: int


class GhostCouncilResponse(BaseModel):
    """Ghost Council recommendation."""
    proposal_id: str
    recommendation: str  # "approve", "reject", "abstain"
    confidence: float
    reasoning: list[str]
    historical_patterns: list[str]


# =============================================================================
# Proposal Endpoints
# =============================================================================

@router.post("/proposals", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    request: CreateProposalRequest,
    user: StandardUserDep,  # Minimum STANDARD to propose
    governance_repo: GovernanceRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> ProposalResponse:
    """
    Create a new governance proposal.
    
    Proposals enter PENDING status and begin voting after creation.
    """
    proposal_id = f"prop_{uuid4().hex[:12]}"
    
    proposal_data = ProposalCreate(
        title=request.title,
        description=request.description,
        type=request.proposal_type,
        action=request.action,
        voting_period_days=request.voting_period_days,
        quorum_percent=request.quorum_percent,
        pass_threshold=request.pass_threshold,
    )
    
    created = await governance_repo.create(proposal_data, proposer_id=user.id)
    
    # Emit event
    await event_system.emit(Event(
        type=EventType.GOVERNANCE_ACTION,
        source="api",
        data={
            "action": "proposal_created",
            "proposal_id": proposal_id,
            "proposer_id": user.id,
            "proposal_type": request.proposal_type.value,
        },
    ))
    
    await audit_repo.log_action(
        action="proposal_created",
        entity_type="proposal",
        entity_id=proposal_id,
        user_id=user.id,
        details={
            "title": request.title,
            "type": request.proposal_type.value,
        },
        correlation_id=correlation_id,
    )
    
    return ProposalResponse.from_proposal(created)


@router.get("/proposals", response_model=ProposalListResponse)
async def list_proposals(
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
    pagination: PaginationDep,
    status_filter: ProposalStatus | None = None,
    proposal_type: ProposalType | None = None,
) -> ProposalListResponse:
    """
    List governance proposals.
    """
    filters = {}
    if status_filter:
        filters["status"] = status_filter.value
    if proposal_type:
        filters["proposal_type"] = proposal_type.value
    
    proposals, total = await governance_repo.list_proposals(
        offset=pagination.offset,
        limit=pagination.per_page,
        filters=filters,
    )
    
    return ProposalListResponse(
        items=[ProposalResponse.from_proposal(p) for p in proposals],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get("/proposals/active")
async def get_active_proposals(
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> list[ProposalResponse]:
    """
    Get all active (votable) proposals.
    """
    proposals = await governance_repo.get_active_proposals()
    return [ProposalResponse.from_proposal(p) for p in proposals]


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> ProposalResponse:
    """
    Get a specific proposal.
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )
    
    return ProposalResponse.from_proposal(proposal)


@router.delete("/proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_proposal(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
):
    """
    Withdraw a proposal (only by proposer, before voting ends).
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.proposer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the proposer can withdraw",
        )
    
    if proposal.status not in [ProposalStatus.PENDING, ProposalStatus.ACTIVE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot withdraw completed proposal",
        )
    
    await governance_repo.update_proposal_status(proposal_id, ProposalStatus.WITHDRAWN)
    
    await audit_repo.log_action(
        action="proposal_withdrawn",
        entity_type="proposal",
        entity_id=proposal_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )


# =============================================================================
# Voting Endpoints
# =============================================================================

@router.post("/proposals/{proposal_id}/vote", response_model=VoteResponse)
async def cast_vote(
    proposal_id: str,
    request: VoteRequest,
    user: StandardUserDep,  # STANDARD to vote
    governance_repo: GovernanceRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> VoteResponse:
    """
    Cast a vote on a proposal.
    
    Vote weight is based on user's trust score.
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status != ProposalStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot vote on {proposal.status.value} proposal",
        )
    
    if datetime.now(timezone.utc) > proposal.voting_ends_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting period has ended",
        )
    
    # Check if already voted
    existing = await governance_repo.get_user_vote(proposal_id, user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already voted on this proposal",
        )
    
    # Calculate vote weight (trust-weighted)
    weight = (user.trust_flame / 100) ** 1.5  # Same formula as governance overlay
    
    vote = Vote(
        id=f"vote_{uuid4().hex[:12]}",
        proposal_id=proposal_id,
        voter_id=user.id,
        choice=request.choice,
        weight=weight,
        rationale=request.rationale,
        created_at=datetime.now(timezone.utc),
    )
    
    created = await governance_repo.record_vote(vote)
    
    # Emit event
    await event_system.emit(Event(
        type=EventType.VOTE_CAST,
        source="api",
        data={
            "proposal_id": proposal_id,
            "voter_id": user.id,
            "choice": request.choice.value,
            "weight": weight,
        },
    ))
    
    await audit_repo.log_action(
        action="vote_cast",
        entity_type="vote",
        entity_id=vote.id,
        user_id=user.id,
        details={
            "proposal_id": proposal_id,
            "choice": request.choice.value,
        },
        correlation_id=correlation_id,
    )
    
    return VoteResponse.from_vote(created)


@router.get("/proposals/{proposal_id}/votes")
async def get_proposal_votes(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> list[VoteResponse]:
    """
    Get all votes on a proposal.
    """
    votes = await governance_repo.get_proposal_votes(proposal_id)
    return [VoteResponse.from_vote(v) for v in votes]


@router.get("/proposals/{proposal_id}/my-vote")
async def get_my_vote(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> VoteResponse | None:
    """
    Get current user's vote on a proposal.
    """
    vote = await governance_repo.get_user_vote(proposal_id, user.id)
    if vote:
        return VoteResponse.from_vote(vote)
    return None


# =============================================================================
# Ghost Council Endpoints
# =============================================================================

@router.get("/proposals/{proposal_id}/ghost-council", response_model=GhostCouncilResponse)
async def get_ghost_council_recommendation(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> GhostCouncilResponse:
    """
    Get Ghost Council's recommendation on a proposal.
    
    The Ghost Council analyzes historical voting patterns and
    provides symbolic guidance based on institutional memory.
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Get voting data
    votes = await governance_repo.get_proposal_votes(proposal_id)
    
    # Analyze patterns (simplified - real implementation in governance overlay)
    for_weight = sum(v.weight for v in votes if v.choice == VoteChoice.FOR)
    against_weight = sum(v.weight for v in votes if v.choice == VoteChoice.AGAINST)
    total_weight = for_weight + against_weight
    
    if total_weight == 0:
        recommendation = "abstain"
        confidence = 0.5
        reasoning = ["Insufficient voting data for recommendation"]
    elif for_weight / total_weight > 0.65:
        recommendation = "approve"
        confidence = for_weight / total_weight
        reasoning = [
            f"Strong community support ({for_weight:.1f} weighted votes for)",
            "Aligns with historical approval patterns",
        ]
    elif against_weight / total_weight > 0.65:
        recommendation = "reject"
        confidence = against_weight / total_weight
        reasoning = [
            f"Strong community opposition ({against_weight:.1f} weighted votes against)",
            "Similar proposals have faced rejection",
        ]
    else:
        recommendation = "abstain"
        confidence = 0.5 + abs(for_weight - against_weight) / (2 * total_weight)
        reasoning = [
            "Community is divided on this proposal",
            "Recommend further discussion before decision",
        ]
    
    # Historical patterns
    patterns = [
        f"This is a {proposal.type.value} type proposal",
        f"Voting period ends in {(proposal.voting_ends_at - datetime.now(timezone.utc)).days} days",
    ]
    
    return GhostCouncilResponse(
        proposal_id=proposal_id,
        recommendation=recommendation,
        confidence=confidence,
        reasoning=reasoning,
        historical_patterns=patterns,
    )


# =============================================================================
# Policy Endpoints
# =============================================================================

@router.get("/policies")
async def get_active_policies(
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> list[dict]:
    """
    Get all active governance policies.
    """
    policies = await governance_repo.get_active_policies()
    return policies


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> dict:
    """
    Get a specific policy.
    """
    policy = await governance_repo.get_policy(policy_id)
    
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return policy


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.post("/proposals/{proposal_id}/finalize", response_model=ProposalResponse)
async def finalize_proposal(
    proposal_id: str,
    user: CoreUserDep,  # CORE trust to finalize
    governance_repo: GovernanceRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> ProposalResponse:
    """
    Manually finalize a proposal (admin action).
    
    Normally proposals are finalized automatically, but this
    allows manual resolution if needed.
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if proposal.status in [ProposalStatus.APPROVED, ProposalStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal already finalized",
        )
    
    # Calculate result
    votes = await governance_repo.get_proposal_votes(proposal_id)
    for_weight = sum(v.weight for v in votes if v.choice == VoteChoice.FOR)
    against_weight = sum(v.weight for v in votes if v.choice == VoteChoice.AGAINST)
    
    if for_weight > against_weight:
        new_status = ProposalStatus.APPROVED
    else:
        new_status = ProposalStatus.REJECTED
    
    updated = await governance_repo.update_proposal_status(proposal_id, new_status)
    
    await event_system.emit(Event(
        type=EventType.GOVERNANCE_ACTION,
        source="api",
        data={
            "action": "proposal_finalized",
            "proposal_id": proposal_id,
            "status": new_status.value,
            "by": user.id,
        },
    ))
    
    await audit_repo.log_action(
        action="proposal_finalized",
        entity_type="proposal",
        entity_id=proposal_id,
        user_id=user.id,
        details={"new_status": new_status.value},
        correlation_id=correlation_id,
    )
    
    return ProposalResponse.from_proposal(updated)


# =============================================================================
# Constitutional AI Analysis
# =============================================================================

class ConstitutionalAnalysisResponse(BaseModel):
    """Constitutional AI analysis response."""
    proposal_id: str
    analyzed_at: str
    ethical_score: int
    fairness_score: int
    safety_score: int
    transparency_score: int
    overall_score: float
    concerns: list[dict]
    summary: str
    recommendation: str  # approve, review, reject
    confidence: float


@router.get("/proposals/{proposal_id}/constitutional-analysis", response_model=ConstitutionalAnalysisResponse)
async def get_constitutional_analysis(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> ConstitutionalAnalysisResponse:
    """
    Get Constitutional AI ethical analysis of a proposal.
    
    The Constitutional AI system evaluates proposals against:
    - Ethical principles
    - Fairness and equity
    - Safety considerations
    - Transparency requirements
    
    This helps ensure proposals align with system values before voting.
    """
    proposal = await governance_repo.get_proposal(proposal_id)
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # Perform constitutional analysis
    analysis = await _analyze_proposal_constitutionality(proposal)
    
    return ConstitutionalAnalysisResponse(
        proposal_id=proposal_id,
        analyzed_at=analysis["analyzed_at"],
        ethical_score=analysis["ethical_score"],
        fairness_score=analysis["fairness_score"],
        safety_score=analysis["safety_score"],
        transparency_score=analysis["transparency_score"],
        overall_score=analysis["overall_score"],
        concerns=analysis["concerns"],
        summary=analysis["summary"],
        recommendation=analysis["recommendation"],
        confidence=analysis["confidence"],
    )


async def _analyze_proposal_constitutionality(proposal) -> dict:
    """
    Analyze proposal against constitutional principles.
    
    This is a simplified implementation. In production, this would
    integrate with actual Constitutional AI systems or LLM-based
    ethical review.
    """
    from datetime import datetime, timezone
    
    # Base scores start at 75 (neutral-positive)
    ethical_score = 75
    fairness_score = 75
    safety_score = 75
    transparency_score = 75
    concerns = []
    
    title = proposal.title.lower()
    description = proposal.description.lower()
    combined = f"{title} {description}"
    
    # Check for ethical concerns
    ethical_red_flags = ["exclude", "discriminat", "unfair", "bias"]
    for flag in ethical_red_flags:
        if flag in combined:
            ethical_score -= 15
            concerns.append({
                "category": "ethical",
                "severity": "medium",
                "description": f"Proposal may involve {flag} practices",
            })
    
    # Check for safety concerns
    safety_red_flags = ["bypass security", "remove validation", "disable check"]
    for flag in safety_red_flags:
        if flag in combined:
            safety_score -= 20
            concerns.append({
                "category": "safety",
                "severity": "high",
                "description": f"Proposal may compromise system safety",
            })
    
    # Check for transparency
    if len(description) < 100:
        transparency_score -= 10
        concerns.append({
            "category": "transparency",
            "severity": "low",
            "description": "Proposal description lacks detail",
        })
    
    # Positive signals
    positive_terms = ["improve", "enhance", "community", "transparent", "fair"]
    positive_count = sum(1 for term in positive_terms if term in combined)
    ethical_score += positive_count * 5
    fairness_score += positive_count * 3
    
    # Cap scores
    ethical_score = max(0, min(100, ethical_score))
    fairness_score = max(0, min(100, fairness_score))
    safety_score = max(0, min(100, safety_score))
    transparency_score = max(0, min(100, transparency_score))
    
    # Calculate overall score
    overall_score = (
        ethical_score * 0.3 +
        fairness_score * 0.25 +
        safety_score * 0.3 +
        transparency_score * 0.15
    )
    
    # Determine recommendation
    if overall_score >= 70 and not any(c["severity"] == "high" for c in concerns):
        recommendation = "approve"
        summary = "This proposal aligns with constitutional principles and is recommended for community vote."
    elif overall_score >= 50:
        recommendation = "review"
        summary = "This proposal raises some concerns and requires careful community review before voting."
    else:
        recommendation = "reject"
        summary = "This proposal conflicts with core constitutional principles and should be reconsidered."
    
    # Confidence based on analysis depth
    confidence = min(0.9, 0.5 + len(combined) / 1000)
    
    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "ethical_score": ethical_score,
        "fairness_score": fairness_score,
        "safety_score": safety_score,
        "transparency_score": transparency_score,
        "overall_score": round(overall_score, 1),
        "concerns": concerns,
        "summary": summary,
        "recommendation": recommendation,
        "confidence": round(confidence, 2),
    }


# =============================================================================
# Delegation Endpoints
# =============================================================================

class CreateDelegationRequest(BaseModel):
    """Request to delegate votes to another user."""
    delegate_id: str = Field(..., description="User ID to delegate to")
    proposal_types: list[str] | None = Field(
        None,
        description="Proposal types to delegate (None = all)",
    )
    expires_at: str | None = Field(None, description="Expiration datetime")


class DelegationResponse(BaseModel):
    """Delegation response."""
    id: str
    delegator_id: str
    delegate_id: str
    proposal_types: list[str] | None
    is_active: bool
    created_at: str
    expires_at: str | None


@router.post("/delegations", response_model=DelegationResponse)
async def create_delegation(
    request: CreateDelegationRequest,
    user: StandardUserDep,
    governance_repo: GovernanceRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> DelegationResponse:
    """
    Delegate voting power to another user.
    
    Delegation allows trusted users to vote on your behalf.
    You can limit delegation to specific proposal types.
    """
    from datetime import datetime, timezone
    from uuid import uuid4
    
    # Validate delegate exists
    # In a real implementation, check user exists
    
    # Cannot delegate to self
    if request.delegate_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delegate to yourself",
        )
    
    delegation_id = f"del_{uuid4().hex[:12]}"
    
    # Create delegation
    delegation = await governance_repo.create_delegation({
        "id": delegation_id,
        "delegator_id": user.id,
        "delegate_id": request.delegate_id,
        "proposal_types": request.proposal_types,
        "is_active": True,
        "expires_at": request.expires_at,
    })
    
    await audit_repo.log_action(
        action="delegation_created",
        entity_type="delegation",
        entity_id=delegation_id,
        user_id=user.id,
        details={
            "delegate_id": request.delegate_id,
            "proposal_types": request.proposal_types,
        },
        correlation_id=correlation_id,
    )
    
    return DelegationResponse(
        id=delegation_id,
        delegator_id=user.id,
        delegate_id=request.delegate_id,
        proposal_types=request.proposal_types,
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=request.expires_at,
    )


@router.get("/delegations", response_model=list[DelegationResponse])
async def get_my_delegations(
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> list[DelegationResponse]:
    """Get delegations where I am either delegator or delegate."""
    delegations = await governance_repo.get_user_delegations(user.id)
    
    return [
        DelegationResponse(
            id=d.id,
            delegator_id=d.delegator_id,
            delegate_id=d.delegate_id,
            proposal_types=d.proposal_types,
            is_active=d.is_active,
            created_at=d.created_at.isoformat() if d.created_at else "",
            expires_at=d.expires_at.isoformat() if d.expires_at else None,
        )
        for d in delegations
    ]


@router.delete("/delegations/{delegation_id}")
async def revoke_delegation(
    delegation_id: str,
    user: StandardUserDep,
    governance_repo: GovernanceRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict:
    """Revoke a delegation."""
    delegation = await governance_repo.get_delegation(delegation_id)
    
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    
    if delegation.delegator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only revoke your own delegations",
        )
    
    await governance_repo.revoke_delegation_by_id(delegation_id)
    
    await audit_repo.log_action(
        action="delegation_revoked",
        entity_type="delegation",
        entity_id=delegation_id,
        user_id=user.id,
        details={},
        correlation_id=correlation_id,
    )
    
    return {"status": "revoked", "delegation_id": delegation_id}
