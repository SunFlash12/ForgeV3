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

import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    CoreUserDep,
    CorrelationIdDep,
    EventSystemDep,
    GovernanceRepoDep,
    PaginationDep,
    StandardUserDep,
    TrustedUserDep,
    UserRepoDep,
)
from forge.models.events import EventType
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    ProposalStatus,
    ProposalType,
    Vote,
    VoteChoice,
)

# Resilience integration - caching, validation, metrics
from forge.resilience.integration import (
    cache_proposal,
    check_content_validation,
    get_cached_proposal,
    invalidate_proposal_cache,
    record_cache_hit,
    record_cache_miss,
    record_ghost_council_query,
    record_proposal_created,
    record_proposal_finalized,
    record_vote_cast,
    validate_capsule_content,
)

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
    created_at: str | None  # Can be None if not set
    voting_starts_at: str | None
    voting_ends_at: str | None

    @classmethod
    def from_proposal(cls, proposal: Proposal) -> ProposalResponse:
        # Handle both string and enum types for proposal.type and proposal.status
        proposal_type = proposal.type.value if hasattr(proposal.type, 'value') else str(proposal.type)
        status = proposal.status.value if hasattr(proposal.status, 'value') else str(proposal.status)
        return cls(
            id=proposal.id,
            title=proposal.title,
            description=proposal.description,
            proposal_type=proposal_type,
            status=status,
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
            created_at=proposal.created_at.isoformat() if proposal.created_at else None,
            voting_starts_at=proposal.voting_starts_at.isoformat() if proposal.voting_starts_at else None,
            voting_ends_at=proposal.voting_ends_at.isoformat() if proposal.voting_ends_at else None,
        )


class VoteResponse(BaseModel):
    """Vote response model."""
    id: str
    proposal_id: str
    user_id: str  # Frontend expects user_id, not voter_id
    choice: str
    weight: float
    rationale: str | None
    created_at: str

    @classmethod
    def from_vote(cls, vote: Vote) -> VoteResponse:
        # Handle both string and enum choice
        choice_str = vote.choice.value if hasattr(vote.choice, 'value') else str(vote.choice)
        return cls(
            id=vote.id,
            proposal_id=vote.proposal_id,
            user_id=vote.voter_id,  # Map voter_id to user_id for frontend
            choice=choice_str,
            weight=vote.weight,
            rationale=vote.reason,
            created_at=vote.created_at.isoformat() if vote.created_at else "",
        )


class ProposalListResponse(BaseModel):
    """Paginated list of proposals."""
    items: list[ProposalResponse]
    total: int
    page: int
    per_page: int


class GhostCouncilHistoricalPatterns(BaseModel):
    """Historical patterns for Ghost Council recommendation."""
    similar_proposals: int
    typical_outcome: str
    participation_rate: float


class GhostCouncilResponse(BaseModel):
    """Ghost Council recommendation."""
    proposal_id: str
    recommendation: str  # "APPROVE", "REJECT", "ABSTAIN" - matches VoteChoice
    confidence: float
    reasoning: str  # Frontend expects a single string
    historical_patterns: GhostCouncilHistoricalPatterns


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
    # Resilience: Content validation for title and description
    combined_content = f"{request.title}\n\n{request.description}"
    validation_result = await validate_capsule_content(combined_content)
    check_content_validation(validation_result)

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
    prop_type = request.proposal_type.value if hasattr(request.proposal_type, 'value') else str(request.proposal_type)

    # Resilience: Record metrics
    record_proposal_created(prop_type)

    await event_system.emit(
        event_type=EventType.GOVERNANCE_ACTION,
        payload={
            "action": "proposal_created",
            "proposal_id": proposal_id,
            "proposer_id": user.id,
            "proposal_type": prop_type,
        },
        source="api",
    )

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=proposal_id,
        action="proposal_created",
        details={
            "title": request.title,
            "type": prop_type,
        },
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
) -> dict:
    """
    Get all active (votable) proposals.
    """
    proposals = await governance_repo.get_active_proposals()
    return {"proposals": [ProposalResponse.from_proposal(p) for p in proposals]}


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> ProposalResponse:
    """
    Get a specific proposal.
    """
    # Resilience: Try cache first
    cached = await get_cached_proposal(proposal_id)
    if cached:
        record_cache_hit("proposal")
        return ProposalResponse(**cached)

    record_cache_miss("proposal")

    proposal = await governance_repo.get_proposal(proposal_id)

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    # Resilience: Cache the result
    response = ProposalResponse.from_proposal(proposal)
    await cache_proposal(proposal_id, response.model_dump())

    return response


@router.post("/proposals/{proposal_id}/submit", response_model=ProposalResponse)
async def submit_proposal_for_voting(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> ProposalResponse:
    """
    Submit a draft proposal to start the voting period.

    Only the proposer can submit their proposal. This transitions the
    proposal from DRAFT to VOTING status and sets the voting period.
    """
    proposal = await governance_repo.get_proposal(proposal_id)

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal.proposer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the proposer can submit this proposal",
        )

    # Check current status
    status_str = proposal.status.value if hasattr(proposal.status, 'value') else str(proposal.status)
    if status_str.upper() != 'DRAFT':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal is already in {status_str} status, cannot submit",
        )

    # Start voting
    updated = await governance_repo.start_voting(proposal_id)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start voting period",
        )

    # Resilience: Invalidate cache
    await invalidate_proposal_cache(proposal_id)

    # Emit event
    await event_system.emit(
        event_type=EventType.GOVERNANCE_ACTION,
        payload={
            "action": "proposal_submitted",
            "proposal_id": proposal_id,
            "proposer_id": user.id,
            "voting_ends_at": updated.voting_ends_at.isoformat() if updated.voting_ends_at else None,
        },
        source="api",
    )

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=proposal_id,
        action="proposal_submitted",
        details={"new_status": "voting"},
    )

    return ProposalResponse.from_proposal(updated)


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

    # Resilience: Invalidate cache
    await invalidate_proposal_cache(proposal_id)

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=proposal_id,
        action="proposal_withdrawn",
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
    user_repo: UserRepoDep,
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

    # Handle both string and enum status
    status_str = proposal.status.value if hasattr(proposal.status, 'value') else str(proposal.status)
    if status_str.upper() not in ('ACTIVE', 'VOTING'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal is not open for voting",
        )

    # Check if voting period has ended (timezone-safe)
    if proposal.voting_ends_at:
        ends_at = proposal.voting_ends_at
        # Handle naive datetime from database
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > ends_at:
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

    # SECURITY FIX: Fetch fresh user trust score to prevent race condition
    # The user object from dependency injection may be stale
    fresh_user = await user_repo.get_by_id(user.id)
    if not fresh_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Clamp trust to valid range and calculate weight
    trust_flame = max(0, min(100, fresh_user.trust_flame))

    # Use linear weighting to prevent governance capture by high-trust users
    # Old formula: (trust/100)^1.5 gave 6.3x weight advantage
    # New formula: linear with minimum floor
    weight = max(0.1, trust_flame / 100)  # Linear weight, minimum 0.1

    vote = Vote(
        id=f"vote_{uuid4().hex[:12]}",
        proposal_id=proposal_id,
        voter_id=user.id,
        choice=request.choice,
        weight=weight,
        reason=request.rationale,
        created_at=datetime.now(UTC),
    )

    created = await governance_repo.record_vote(vote)

    # Handle both string and enum choice for event/audit
    choice_for_log = request.choice.value if hasattr(request.choice, 'value') else str(request.choice)

    # Resilience: Invalidate proposal cache and record metrics
    await invalidate_proposal_cache(proposal_id)
    record_vote_cast(choice_for_log)

    # Emit event
    await event_system.emit(
        event_type=EventType.VOTE_CAST,
        payload={
            "proposal_id": proposal_id,
            "voter_id": user.id,
            "choice": choice_for_log,
            "weight": weight,
        },
        source="api",
    )

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=proposal_id,
        action="vote_cast",
        details={
            "vote_id": vote.id,
            "choice": choice_for_log,
        },
    )

    return VoteResponse.from_vote(created)


@router.get("/proposals/{proposal_id}/votes")
async def get_proposal_votes(
    proposal_id: str,
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> dict:
    """
    Get all votes on a proposal.
    """
    votes = await governance_repo.get_proposal_votes(proposal_id)
    return {"votes": [VoteResponse.from_vote(v) for v in votes]}


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
    use_ai: bool = Query(default=True, description="Use AI deliberation (False for quick heuristic)"),
) -> GhostCouncilResponse:
    """
    Get Ghost Council's recommendation on a proposal.

    The Ghost Council is an AI advisory board that analyzes proposals
    and provides transparent recommendations. When use_ai=True, the
    council members deliberate using LLM-based analysis. When use_ai=False,
    uses quick heuristics based on voting patterns.
    """
    start_time = time.perf_counter()

    proposal = await governance_repo.get_proposal(proposal_id)

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Get voting data for context
    votes = await governance_repo.get_proposal_votes(proposal_id)

    # Calculate vote statistics for context
    for_weight = sum(v.weight for v in votes if v.choice == VoteChoice.APPROVE)
    against_weight = sum(v.weight for v in votes if v.choice == VoteChoice.REJECT)
    total_weight = for_weight + against_weight
    total_votes = len(votes)

    if use_ai:
        # Use full Ghost Council AI deliberation
        from forge.services.ghost_council import get_ghost_council_service

        ghost_council = get_ghost_council_service()

        # Get Constitutional AI review first for context
        constitutional_review = await _analyze_proposal_constitutionality(proposal)

        # Have Ghost Council deliberate
        opinion = await ghost_council.deliberate_proposal(
            proposal=proposal,
            context={
                "votes_for": proposal.votes_for,
                "votes_against": proposal.votes_against,
                "weighted_for": for_weight,
                "weighted_against": against_weight,
                "total_voters": total_votes,
                "voting_period_remaining": (
                    (proposal.voting_ends_at - datetime.now(UTC)).total_seconds() / 3600
                    if proposal.voting_ends_at else None
                ),
            },
            constitutional_review=constitutional_review,
        )

        # Convert to API response format
        # Handle both enum and string consensus_vote values
        consensus_vote = opinion.consensus_vote
        if hasattr(consensus_vote, 'value'):
            recommendation = consensus_vote.value
        else:
            recommendation = str(consensus_vote)
        confidence = opinion.consensus_strength
        reasoning = opinion.final_recommendation

        # Determine typical outcome from consensus
        vote_str = recommendation.upper()
        if vote_str == "APPROVE":
            typical_outcome = "approved"
        elif vote_str == "REJECT":
            typical_outcome = "rejected"
        else:
            typical_outcome = "contested"

    else:
        # Quick heuristic fallback (original implementation)
        if total_weight == 0:
            recommendation = "ABSTAIN"
            confidence = 0.5
            reasoning = "Insufficient voting data for recommendation"
            typical_outcome = "pending"
        elif for_weight / total_weight > 0.65:
            recommendation = "APPROVE"
            confidence = for_weight / total_weight
            reasoning = f"Strong community support ({for_weight:.1f} weighted votes for). Aligns with historical approval patterns."
            typical_outcome = "approved"
        elif against_weight / total_weight > 0.65:
            recommendation = "REJECT"
            confidence = against_weight / total_weight
            reasoning = f"Strong community opposition ({against_weight:.1f} weighted votes against). Similar proposals have faced rejection."
            typical_outcome = "rejected"
        else:
            recommendation = "ABSTAIN"
            confidence = 0.5 + abs(for_weight - against_weight) / (2 * total_weight) if total_weight > 0 else 0.5
            reasoning = "Community is divided on this proposal. Recommend further discussion before decision."
            typical_outcome = "contested"

    # Calculate participation rate
    participation_rate = min(1.0, total_votes / 10) if total_votes > 0 else 0.0

    # Historical patterns matching frontend format
    historical_patterns = GhostCouncilHistoricalPatterns(
        similar_proposals=5,
        typical_outcome=typical_outcome,
        participation_rate=participation_rate,
    )

    # Resilience: Record metrics
    latency = time.perf_counter() - start_time
    record_ghost_council_query(latency, use_ai)

    return GhostCouncilResponse(
        proposal_id=proposal_id,
        recommendation=recommendation,
        confidence=confidence,
        reasoning=reasoning,
        historical_patterns=historical_patterns,
    )


# =============================================================================
# Ghost Council Serious Issues
# =============================================================================

class SeriousIssueResponse(BaseModel):
    """Response for a serious issue."""
    id: str
    category: str
    severity: str
    title: str
    description: str
    affected_entities: list[str]
    detected_at: str
    source: str
    resolved: bool
    resolution: str | None
    has_ghost_council_opinion: bool


class GhostCouncilMemberResponse(BaseModel):
    """Ghost Council member info."""
    id: str
    name: str
    role: str
    weight: float


@router.get("/ghost-council/members", response_model=list[GhostCouncilMemberResponse])
async def get_ghost_council_members(
    user: ActiveUserDep,
) -> list[GhostCouncilMemberResponse]:
    """
    Get the list of Ghost Council members.

    The Ghost Council consists of AI advisors with different expertise areas
    who deliberate on proposals and serious issues.
    """
    from forge.services.ghost_council import get_ghost_council_service

    ghost_council = get_ghost_council_service()

    return [
        GhostCouncilMemberResponse(
            id=member.id,
            name=member.name,
            role=member.role,
            weight=member.weight,
        )
        for member in ghost_council.members
    ]


@router.get("/ghost-council/issues", response_model=list[SeriousIssueResponse])
async def get_active_issues(
    user: TrustedUserDep,  # TRUSTED to view issues
) -> list[SeriousIssueResponse]:
    """
    Get all active (unresolved) serious issues.

    Serious issues are automatically detected by the system and
    require Ghost Council attention.
    """
    from forge.services.ghost_council import get_ghost_council_service

    ghost_council = get_ghost_council_service()
    issues = ghost_council.get_active_issues()

    return [
        SeriousIssueResponse(
            id=issue.id,
            category=issue.category.value,
            severity=issue.severity.value,
            title=issue.title,
            description=issue.description,
            affected_entities=issue.affected_entities,
            detected_at=issue.detected_at.isoformat(),
            source=issue.source,
            resolved=issue.resolved,
            resolution=issue.resolution,
            has_ghost_council_opinion=issue.ghost_council_opinion is not None,
        )
        for issue in issues
    ]


class ReportIssueRequest(BaseModel):
    """Request to manually report a serious issue."""
    category: str = Field(..., description="Issue category: security, governance, trust, system, ethical, data_integrity")
    severity: str = Field(..., description="Issue severity: low, medium, high, critical")
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20)
    affected_entities: list[str] = Field(default_factory=list)


@router.post("/ghost-council/issues", response_model=SeriousIssueResponse)
async def report_serious_issue(
    request: ReportIssueRequest,
    user: TrustedUserDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> SeriousIssueResponse:
    """
    Manually report a serious issue for Ghost Council review.

    This triggers Ghost Council deliberation on the reported issue.
    """
    # Resilience: Content validation for title and description
    combined_content = f"{request.title}\n\n{request.description}"
    validation_result = await validate_capsule_content(combined_content)
    check_content_validation(validation_result)

    from uuid import uuid4

    from forge.services.ghost_council import (
        IssueCategory,
        IssueSeverity,
        SeriousIssue,
        get_ghost_council_service,
    )

    ghost_council = get_ghost_council_service()

    # Validate category and severity
    # SECURITY: Don't expose valid enum values in error messages
    try:
        category = IssueCategory(request.category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category",
        )

    try:
        severity = IssueSeverity(request.severity)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid severity",
        )

    # Create the issue
    issue = SeriousIssue(
        id=str(uuid4()),
        category=category,
        severity=severity,
        title=request.title,
        description=request.description,
        affected_entities=request.affected_entities,
        detected_at=datetime.now(UTC),
        source=f"user_report:{user.id}",
        context={"reported_by": user.id, "reported_by_username": user.username},
    )

    # Have Ghost Council respond
    await ghost_council.respond_to_issue(issue)

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=f"issue_{issue.id}",
        action="serious_issue_reported",
        details={
            "category": category.value,
            "severity": severity.value,
            "title": request.title,
        },
    )

    return SeriousIssueResponse(
        id=issue.id,
        category=issue.category.value,
        severity=issue.severity.value,
        title=issue.title,
        description=issue.description,
        affected_entities=issue.affected_entities,
        detected_at=issue.detected_at.isoformat(),
        source=issue.source,
        resolved=issue.resolved,
        resolution=issue.resolution,
        has_ghost_council_opinion=issue.ghost_council_opinion is not None,
    )


class ResolveIssueRequest(BaseModel):
    """Request to resolve a serious issue."""
    resolution: str = Field(..., min_length=10, description="How the issue was resolved")


@router.post("/ghost-council/issues/{issue_id}/resolve")
async def resolve_serious_issue(
    issue_id: str,
    request: ResolveIssueRequest,
    user: CoreUserDep,  # CORE to resolve issues
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict:
    """
    Mark a serious issue as resolved.

    Only CORE trust users can resolve serious issues.
    """
    from forge.services.ghost_council import get_ghost_council_service

    ghost_council = get_ghost_council_service()

    if not ghost_council.resolve_issue(issue_id, request.resolution):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found",
        )

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=f"issue_{issue_id}",
        action="serious_issue_resolved",
        details={"resolution": request.resolution},
    )

    return {"status": "resolved", "issue_id": issue_id}


@router.get("/ghost-council/stats")
async def get_ghost_council_stats(
    user: ActiveUserDep,
) -> dict:
    """
    Get Ghost Council statistics.

    Returns metrics about proposals reviewed, issues responded to, etc.
    """
    from forge.services.ghost_council import get_ghost_council_service

    ghost_council = get_ghost_council_service()
    return ghost_council.get_stats()


# =============================================================================
# Governance Metrics Endpoint
# =============================================================================


class GovernanceMetricsResponse(BaseModel):
    """Governance system metrics."""
    timestamp: str
    total_proposals: int
    active_proposals: int
    passed_proposals: int
    rejected_proposals: int
    total_votes: int
    unique_voters: int
    average_participation: float
    average_pass_rate: float
    proposals_by_type: dict[str, int]
    proposals_by_status: dict[str, int]


@router.get("/metrics", response_model=GovernanceMetricsResponse)
async def get_governance_metrics(
    user: ActiveUserDep,
    governance_repo: GovernanceRepoDep,
) -> GovernanceMetricsResponse:
    """
    Get governance system metrics.

    Returns statistics about proposals, voting participation,
    and governance health.
    """
    # Get all proposals for metrics
    proposals, total = await governance_repo.list_proposals(
        offset=0,
        limit=1000,  # Get all for metrics
        filters={},
    )

    # Count by status
    status_counts = {}
    type_counts = {}
    total_votes = 0
    unique_voters = set()
    passed = 0
    rejected = 0
    active = 0

    for p in proposals:
        # Count by status
        status_str = p.status.value if hasattr(p.status, 'value') else str(p.status)
        status_counts[status_str] = status_counts.get(status_str, 0) + 1

        # Count by type
        type_str = p.type.value if hasattr(p.type, 'value') else str(p.type)
        type_counts[type_str] = type_counts.get(type_str, 0) + 1

        # Track pass/reject/active
        if status_str.upper() == 'PASSED':
            passed += 1
        elif status_str.upper() == 'REJECTED':
            rejected += 1
        elif status_str.upper() in ('ACTIVE', 'VOTING', 'PENDING'):
            active += 1

        # Aggregate vote counts
        total_votes += p.votes_for + p.votes_against + p.votes_abstain

        # Get votes for unique voter tracking
        votes = await governance_repo.get_proposal_votes(p.id)
        for v in votes:
            unique_voters.add(v.voter_id)

    # Calculate averages
    decided = passed + rejected
    avg_pass_rate = passed / decided if decided > 0 else 0.0
    avg_participation = len(unique_voters) / max(1, total) if total > 0 else 0.0

    return GovernanceMetricsResponse(
        timestamp=datetime.now(UTC).isoformat(),
        total_proposals=total,
        active_proposals=active,
        passed_proposals=passed,
        rejected_proposals=rejected,
        total_votes=total_votes,
        unique_voters=len(unique_voters),
        average_participation=round(avg_participation, 3),
        average_pass_rate=round(avg_pass_rate, 3),
        proposals_by_type=type_counts,
        proposals_by_status=status_counts,
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

    if proposal.status in [ProposalStatus.PASSED, ProposalStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal already finalized",
        )

    # Calculate result
    votes = await governance_repo.get_proposal_votes(proposal_id)
    for_weight = sum(v.weight for v in votes if v.choice == VoteChoice.APPROVE)
    against_weight = sum(v.weight for v in votes if v.choice == VoteChoice.REJECT)

    if for_weight > against_weight:
        new_status = ProposalStatus.PASSED
    else:
        new_status = ProposalStatus.REJECTED

    updated = await governance_repo.update_proposal_status(proposal_id, new_status)

    # Handle both string and enum status
    status_val = new_status.value if hasattr(new_status, 'value') else str(new_status)

    # Resilience: Invalidate cache and record metrics
    await invalidate_proposal_cache(proposal_id)
    record_proposal_finalized(status_val)

    await event_system.emit(
        event_type=EventType.GOVERNANCE_ACTION,
        payload={
            "action": "proposal_finalized",
            "proposal_id": proposal_id,
            "status": status_val,
            "by": user.id,
        },
        source="api",
    )

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=proposal_id,
        action="proposal_finalized",
        details={"new_status": status_val},
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
    from datetime import datetime

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
                "description": "Proposal may compromise system safety",
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
        "analyzed_at": datetime.now(UTC).isoformat(),
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
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> DelegationResponse:
    """
    Delegate voting power to another user.

    Delegation allows trusted users to vote on your behalf.
    You can limit delegation to specific proposal types.
    """
    from datetime import datetime
    from uuid import uuid4

    # Cannot delegate to self
    if request.delegate_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delegate to yourself",
        )

    # SECURITY FIX: Validate delegate user exists
    delegate = await user_repo.get_by_id(request.delegate_id)
    if not delegate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delegate user not found",
        )

    # Check delegate is active
    if not delegate.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delegate to inactive user",
        )

    # SECURITY FIX: Check for delegation cycles
    # A cycle would be: A -> B -> C -> A (or any loop back to the delegator)
    MAX_DELEGATION_DEPTH = 10  # Configurable max depth to prevent infinite recursion

    async def would_create_cycle(target_id: str, visited: set[str], depth: int = 0) -> tuple[bool, str]:
        """
        Check if delegating to target_id would create a cycle.

        Returns:
            (is_problematic, reason) - True with reason if cycle found or chain too deep
        """
        if target_id in visited:
            return True, "circular_chain"  # Found actual cycle
        if depth > MAX_DELEGATION_DEPTH:
            return True, "chain_too_deep"  # Chain too deep (not a cycle, but rejected)
        visited.add(target_id)

        # Get target's active delegations (who does target delegate to?)
        target_delegations = await governance_repo.get_delegates(target_id)
        for delegation in target_delegations:
            if delegation.is_active:
                is_bad, reason = await would_create_cycle(delegation.delegate_id, visited.copy(), depth + 1)
                if is_bad:
                    return True, reason
        return False, ""

    is_problematic, reason = await would_create_cycle(request.delegate_id, {user.id})
    if is_problematic:
        if reason == "circular_chain":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create delegation: would create a circular delegation chain",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create delegation: chain would exceed maximum depth of {MAX_DELEGATION_DEPTH}",
            )

    delegation_id = f"del_{uuid4().hex[:12]}"

    # Create delegation
    await governance_repo.create_delegation({
        "id": delegation_id,
        "delegator_id": user.id,
        "delegate_id": request.delegate_id,
        "proposal_types": request.proposal_types,
        "is_active": True,
        "expires_at": request.expires_at,
    })

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=delegation_id,  # Using delegation_id as a stand-in
        action="delegation_created",
        details={
            "delegate_id": request.delegate_id,
            "proposal_types": request.proposal_types,
        },
    )

    return DelegationResponse(
        id=delegation_id,
        delegator_id=user.id,
        delegate_id=request.delegate_id,
        proposal_types=request.proposal_types,
        is_active=True,
        created_at=datetime.now(UTC).isoformat(),
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

    await audit_repo.log_governance_action(
        actor_id=user.id,
        proposal_id=delegation_id,  # Using delegation_id as a stand-in
        action="delegation_revoked",
    )

    return {"status": "revoked", "delegation_id": delegation_id}
