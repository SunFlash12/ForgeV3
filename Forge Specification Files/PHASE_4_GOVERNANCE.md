# Forge V3 - Phase 4: Governance System

**Purpose:** Implement democratic governance with proposals, trust-weighted voting, and self-healing immune system.

**Estimated Effort:** 4-5 days
**Dependencies:** Phase 0-3
**Outputs:** Working proposal system, voting mechanism, and automated health monitoring

---

## 1. Overview

The governance system enables democratic decision-making within Forge. Key features include trust-weighted voting (higher trust = more vote weight), AI advisory analysis, and an immune system that automatically responds to threats.

---

## 2. Governance Models

```python
# forge/models/governance.py
"""
Governance domain models for proposals and voting.
"""
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import Field, field_validator

from forge.models.base import (
    ForgeBaseModel,
    TimestampMixin,
    IdentifiableMixin,
    TrustLevel,
    ProposalStatus,
    ProposalType,
    VoteDecision,
)


class ProposalPayload(ForgeBaseModel):
    """Base class for proposal payloads."""
    pass


class ConfigChangePayload(ProposalPayload):
    """Payload for configuration change proposals."""
    config_key: str
    old_value: str | None
    new_value: str


class TrustAdjustmentPayload(ProposalPayload):
    """Payload for trust level adjustment proposals."""
    target_type: str = Field(description="'user' or 'overlay'")
    target_id: UUID
    current_trust: TrustLevel
    proposed_trust: TrustLevel
    reason: str


class OverlayRegistrationPayload(ProposalPayload):
    """Payload for overlay registration proposals."""
    overlay_id: UUID
    overlay_name: str
    capabilities: list[str]
    risk_assessment: str | None = None


class ProposalCreate(ForgeBaseModel):
    """Request to create a proposal."""
    
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10000)
    type: ProposalType
    payload: dict = Field(default_factory=dict)
    voting_duration_hours: int = Field(default=72, ge=1, le=168)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Increase rate limit for TRUSTED users",
                    "description": "Proposal to increase API rate limits from 1000 to 2000 req/min for TRUSTED users.",
                    "type": "configuration",
                    "payload": {
                        "config_key": "rate_limit.trusted",
                        "old_value": "1000",
                        "new_value": "2000",
                    },
                    "voting_duration_hours": 48,
                },
            ],
        },
    }


class Proposal(TimestampMixin, IdentifiableMixin, ForgeBaseModel):
    """Complete proposal entity."""
    
    title: str
    description: str
    type: ProposalType
    status: ProposalStatus = Field(default=ProposalStatus.DRAFT)
    payload: dict = Field(default_factory=dict)
    
    proposer_id: UUID
    voting_starts_at: datetime | None = None
    voting_ends_at: datetime | None = None
    
    # Voting thresholds
    quorum_percentage: float = Field(default=0.3, description="% of eligible voters required")
    approval_threshold: float = Field(default=0.5, description="% of votes needed to pass")
    
    # Results (computed)
    votes_for: float = Field(default=0, description="Weighted votes in favor")
    votes_against: float = Field(default=0, description="Weighted votes against")
    votes_abstain: float = Field(default=0, description="Weighted abstentions")
    total_eligible_weight: float = Field(default=0, description="Total weight of eligible voters")
    
    # AI analysis (advisory only)
    ai_analysis: dict | None = Field(default=None, description="Constitutional AI analysis")
    
    # Execution
    executed_at: datetime | None = None
    execution_result: str | None = None


class VoteCreate(ForgeBaseModel):
    """Request to cast a vote."""
    
    decision: VoteDecision
    reasoning: str | None = Field(default=None, max_length=2000)


class Vote(TimestampMixin, IdentifiableMixin, ForgeBaseModel):
    """A vote on a proposal."""
    
    proposal_id: UUID
    voter_id: UUID
    decision: VoteDecision
    weight: float = Field(description="Vote weight based on trust level")
    reasoning: str | None = None


class GovernanceMetrics(ForgeBaseModel):
    """Governance participation metrics."""
    
    total_proposals: int
    active_proposals: int
    total_votes_cast: int
    average_participation: float
    proposals_by_status: dict[str, int]
```

---

## 3. Governance Service

```python
# forge/core/governance/service.py
"""
Governance business logic service.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from forge.core.governance.repository import GovernanceRepository
from forge.core.users.repository import UserRepository
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    Vote,
    VoteCreate,
    ProposalStatus,
    ProposalType,
)
from forge.models.user import User
from forge.models.base import TrustLevel, VoteDecision
from forge.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
    ConflictError,
)
from forge.logging import get_logger

logger = get_logger(__name__)


# Vote weights by trust level
TRUST_VOTE_WEIGHTS = {
    TrustLevel.CORE: 5.0,
    TrustLevel.TRUSTED: 3.0,
    TrustLevel.STANDARD: 1.0,
    TrustLevel.SANDBOX: 0.5,
    TrustLevel.QUARANTINE: 0.0,
}

# Minimum trust levels to create each proposal type
PROPOSAL_TRUST_REQUIREMENTS = {
    ProposalType.CONFIGURATION: TrustLevel.TRUSTED,
    ProposalType.POLICY: TrustLevel.TRUSTED,
    ProposalType.TRUST_ADJUSTMENT: TrustLevel.TRUSTED,
    ProposalType.OVERLAY_REGISTRATION: TrustLevel.STANDARD,
    ProposalType.OVERLAY_UPDATE: TrustLevel.STANDARD,
    ProposalType.EMERGENCY: TrustLevel.CORE,
}


class GovernanceService:
    """Service for governance operations."""
    
    def __init__(
        self,
        repository: GovernanceRepository,
        user_repository: UserRepository,
        ai_analyzer: "ConstitutionalAIAnalyzer | None" = None,
    ):
        self._repo = repository
        self._users = user_repository
        self._ai = ai_analyzer
    
    async def create_proposal(
        self,
        data: ProposalCreate,
        proposer: User,
    ) -> Proposal:
        """
        Create a new governance proposal.
        
        Starts in DRAFT status. Must be activated to open voting.
        """
        # Check trust level requirement
        required_trust = PROPOSAL_TRUST_REQUIREMENTS.get(
            data.type, TrustLevel.STANDARD
        )
        if not proposer.trust_level.can_access(required_trust):
            raise AuthorizationError(
                f"Creating {data.type.value} proposals requires {required_trust.value} trust level"
            )
        
        # Calculate voting end time
        voting_ends = datetime.now(timezone.utc) + timedelta(hours=data.voting_duration_hours)
        
        proposal = await self._repo.create_proposal(
            data=data,
            proposer_id=proposer.id,
            voting_ends_at=voting_ends,
        )
        
        logger.info(
            "proposal_created",
            proposal_id=str(proposal.id),
            type=data.type.value,
            proposer=proposer.email,
        )
        
        return proposal
    
    async def activate_proposal(
        self,
        proposal_id: UUID,
        user: User,
    ) -> Proposal:
        """
        Activate a draft proposal, opening it for voting.
        
        Triggers AI analysis if available.
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            raise NotFoundError("Proposal", str(proposal_id))
        
        # Only proposer or admin can activate
        if proposal.proposer_id != user.id and "admin" not in user.roles:
            raise AuthorizationError("Only the proposer can activate this proposal")
        
        if proposal.status != ProposalStatus.DRAFT:
            raise ValidationError(f"Cannot activate proposal in status: {proposal.status.value}")
        
        # Get AI analysis (advisory only)
        ai_analysis = None
        if self._ai:
            ai_analysis = await self._ai.analyze_proposal(proposal)
        
        # Calculate total eligible weight
        eligible_weight = await self._calculate_eligible_weight()
        
        # Activate
        proposal = await self._repo.activate_proposal(
            proposal_id=proposal_id,
            ai_analysis=ai_analysis,
            total_eligible_weight=eligible_weight,
        )
        
        logger.info("proposal_activated", proposal_id=str(proposal_id))
        return proposal
    
    async def cast_vote(
        self,
        proposal_id: UUID,
        data: VoteCreate,
        voter: User,
    ) -> Vote:
        """
        Cast or update a vote on a proposal.
        
        Vote weight determined by voter's trust level.
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            raise NotFoundError("Proposal", str(proposal_id))
        
        # Check voting is open
        if proposal.status != ProposalStatus.ACTIVE:
            raise ValidationError("Voting is not open for this proposal")
        
        now = datetime.now(timezone.utc)
        if proposal.voting_ends_at and now > proposal.voting_ends_at:
            raise ValidationError("Voting has ended for this proposal")
        
        # Check voter eligibility
        if voter.trust_level == TrustLevel.QUARANTINE:
            raise AuthorizationError("Quarantined users cannot vote")
        
        # Calculate vote weight
        weight = TRUST_VOTE_WEIGHTS[voter.trust_level]
        
        # Check for existing vote
        existing = await self._repo.get_vote(proposal_id, voter.id)
        
        if existing:
            # Update existing vote
            vote = await self._repo.update_vote(
                vote_id=existing.id,
                decision=data.decision,
                reasoning=data.reasoning,
            )
            logger.info("vote_updated", proposal_id=str(proposal_id), voter=voter.email)
        else:
            # Create new vote
            vote = await self._repo.create_vote(
                proposal_id=proposal_id,
                voter_id=voter.id,
                decision=data.decision,
                weight=weight,
                reasoning=data.reasoning,
            )
            logger.info("vote_cast", proposal_id=str(proposal_id), voter=voter.email)
        
        # Update proposal vote counts
        await self._update_vote_counts(proposal_id)
        
        return vote
    
    async def close_voting(self, proposal_id: UUID) -> Proposal:
        """
        Close voting and determine outcome.
        
        Called by scheduler when voting_ends_at is reached.
        """
        proposal = await self._repo.get_proposal(proposal_id)
        if not proposal:
            raise NotFoundError("Proposal", str(proposal_id))
        
        if proposal.status != ProposalStatus.ACTIVE:
            return proposal  # Already closed
        
        # Check quorum
        total_voted = proposal.votes_for + proposal.votes_against + proposal.votes_abstain
        participation = total_voted / proposal.total_eligible_weight if proposal.total_eligible_weight > 0 else 0
        
        quorum_met = participation >= proposal.quorum_percentage
        
        # Check approval
        votes_cast = proposal.votes_for + proposal.votes_against
        approval_rate = proposal.votes_for / votes_cast if votes_cast > 0 else 0
        
        passed = quorum_met and approval_rate >= proposal.approval_threshold
        
        new_status = ProposalStatus.APPROVED if passed else ProposalStatus.REJECTED
        
        proposal = await self._repo.close_proposal(proposal_id, new_status)
        
        logger.info(
            "proposal_closed",
            proposal_id=str(proposal_id),
            status=new_status.value,
            quorum_met=quorum_met,
            approval_rate=approval_rate,
        )
        
        # Execute if approved
        if passed:
            await self._execute_proposal(proposal)
        
        return proposal
    
    async def _execute_proposal(self, proposal: Proposal) -> None:
        """Execute an approved proposal."""
        try:
            # Execution depends on proposal type
            if proposal.type == ProposalType.CONFIGURATION:
                await self._execute_config_change(proposal)
            elif proposal.type == ProposalType.TRUST_ADJUSTMENT:
                await self._execute_trust_adjustment(proposal)
            elif proposal.type == ProposalType.OVERLAY_REGISTRATION:
                await self._execute_overlay_registration(proposal)
            # ... other types
            
            await self._repo.mark_executed(proposal.id, "success")
            logger.info("proposal_executed", proposal_id=str(proposal.id))
            
        except Exception as e:
            await self._repo.mark_executed(proposal.id, f"failed: {e}")
            logger.error("proposal_execution_failed", proposal_id=str(proposal.id), error=str(e))
    
    async def _execute_trust_adjustment(self, proposal: Proposal) -> None:
        """Execute a trust level adjustment."""
        payload = proposal.payload
        target_id = UUID(payload["target_id"])
        new_trust = TrustLevel(payload["proposed_trust"])
        
        if payload["target_type"] == "user":
            await self._users.update_trust_level(target_id, new_trust)
        # ... handle overlay trust adjustments
    
    async def _update_vote_counts(self, proposal_id: UUID) -> None:
        """Recalculate vote counts for a proposal."""
        await self._repo.recalculate_votes(proposal_id)
    
    async def _calculate_eligible_weight(self) -> float:
        """Calculate total vote weight of all eligible voters."""
        # Sum weights of all non-quarantined users
        users = await self._users.list_active()
        return sum(TRUST_VOTE_WEIGHTS[u.trust_level] for u in users)
    
    async def get_proposal(self, proposal_id: UUID) -> Proposal | None:
        """Get a proposal by ID."""
        return await self._repo.get_proposal(proposal_id)
    
    async def list_proposals(
        self,
        status: ProposalStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Proposal], int]:
        """List proposals with filtering."""
        return await self._repo.list_proposals(status, page, per_page)
```

---

## 4. Immune System

```python
# forge/core/governance/immune.py
"""
Immune system for automatic threat response.

Monitors system health and automatically responds to:
- Failing overlays (quarantine)
- Suspicious activity patterns
- Resource exhaustion
- Security anomalies
"""
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from forge.models.base import TrustLevel, OverlayState
from forge.logging import get_logger

logger = get_logger(__name__)


class ThreatLevel(str, Enum):
    """Severity of detected threat."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of threats detected."""
    OVERLAY_FAILURE = "overlay_failure"
    RATE_LIMIT_ABUSE = "rate_limit_abuse"
    AUTH_ANOMALY = "auth_anomaly"
    DATA_ANOMALY = "data_anomaly"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class ImmuneResponse:
    """Response action taken by the immune system."""
    
    def __init__(
        self,
        threat_type: ThreatType,
        threat_level: ThreatLevel,
        target_type: str,
        target_id: UUID,
        action: str,
        reason: str,
    ):
        self.threat_type = threat_type
        self.threat_level = threat_level
        self.target_type = target_type
        self.target_id = target_id
        self.action = action
        self.reason = reason
        self.timestamp = datetime.now(timezone.utc)


class ImmuneSystem:
    """
    Automated threat detection and response.
    
    Runs continuously, monitoring for issues and
    taking automated action when thresholds are exceeded.
    """
    
    # Thresholds for automatic responses
    OVERLAY_FAILURE_RATE_THRESHOLD = 0.5  # 50% failure rate
    OVERLAY_MIN_INVOCATIONS = 10  # Minimum invocations before judging
    
    AUTH_FAILURE_THRESHOLD = 10  # Failed logins per window
    AUTH_WINDOW_MINUTES = 5
    
    RATE_LIMIT_ABUSE_THRESHOLD = 0.9  # 90% of limit used consistently
    
    def __init__(
        self,
        overlay_service: "OverlayService",
        user_service: "UserService",
        redis: "RedisClient",
    ):
        self._overlays = overlay_service
        self._users = user_service
        self._redis = redis
        self._responses: list[ImmuneResponse] = []
    
    async def check_overlay_health(self, overlay_id: UUID) -> ImmuneResponse | None:
        """
        Check overlay health and quarantine if unhealthy.
        
        Called after each invocation failure.
        """
        overlay = await self._overlays.get(overlay_id)
        if not overlay or overlay.state == OverlayState.QUARANTINED:
            return None
        
        # Need minimum invocations to judge
        if overlay.invocation_count < self.OVERLAY_MIN_INVOCATIONS:
            return None
        
        failure_rate = overlay.failure_count / overlay.invocation_count
        
        if failure_rate > self.OVERLAY_FAILURE_RATE_THRESHOLD:
            # Quarantine the overlay
            await self._overlays._repo.update_state(overlay_id, OverlayState.QUARANTINED)
            
            response = ImmuneResponse(
                threat_type=ThreatType.OVERLAY_FAILURE,
                threat_level=ThreatLevel.HIGH,
                target_type="overlay",
                target_id=overlay_id,
                action="quarantine",
                reason=f"Failure rate {failure_rate:.1%} exceeds threshold {self.OVERLAY_FAILURE_RATE_THRESHOLD:.0%}",
            )
            
            self._responses.append(response)
            logger.warning(
                "immune_response",
                action="overlay_quarantined",
                overlay_id=str(overlay_id),
                failure_rate=failure_rate,
            )
            
            return response
        
        return None
    
    async def check_auth_anomaly(
        self,
        user_id: UUID | None,
        ip_address: str,
        success: bool,
    ) -> ImmuneResponse | None:
        """
        Check for authentication anomalies.
        
        Called after each authentication attempt.
        """
        if success:
            return None
        
        # Track failures by IP
        key = f"auth_failures:{ip_address}"
        failures = await self._redis.increment(key, ttl=self.AUTH_WINDOW_MINUTES * 60)
        
        if failures >= self.AUTH_FAILURE_THRESHOLD:
            # Block the IP temporarily
            block_key = f"blocked_ip:{ip_address}"
            await self._redis.set(block_key, "1", ttl=3600)  # 1 hour block
            
            response = ImmuneResponse(
                threat_type=ThreatType.AUTH_ANOMALY,
                threat_level=ThreatLevel.MEDIUM,
                target_type="ip",
                target_id=UUID(int=hash(ip_address) % (2**128)),  # Fake UUID from IP
                action="block_ip",
                reason=f"{failures} failed auth attempts in {self.AUTH_WINDOW_MINUTES} minutes",
            )
            
            self._responses.append(response)
            logger.warning("immune_response", action="ip_blocked", ip=ip_address)
            
            return response
        
        return None
    
    async def check_user_behavior(self, user_id: UUID) -> ImmuneResponse | None:
        """
        Check user behavior for anomalies.
        
        Could detect:
        - Unusual access patterns
        - Mass data downloads
        - Suspicious API usage
        """
        # Implementation would analyze user activity logs
        # For now, return None (no anomaly detected)
        return None
    
    async def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if an IP is currently blocked."""
        result = await self._redis.get(f"blocked_ip:{ip_address}")
        return result is not None
    
    async def get_recent_responses(
        self,
        limit: int = 100,
    ) -> list[ImmuneResponse]:
        """Get recent immune system responses."""
        return self._responses[-limit:]
    
    async def manual_quarantine(
        self,
        target_type: str,
        target_id: UUID,
        reason: str,
        admin: "User",
    ) -> ImmuneResponse:
        """Manually trigger a quarantine action."""
        if target_type == "overlay":
            await self._overlays._repo.update_state(target_id, OverlayState.QUARANTINED)
        elif target_type == "user":
            await self._users._repo.update_trust_level(target_id, TrustLevel.QUARANTINE)
        
        response = ImmuneResponse(
            threat_type=ThreatType.DATA_ANOMALY,  # Generic for manual
            threat_level=ThreatLevel.HIGH,
            target_type=target_type,
            target_id=target_id,
            action="manual_quarantine",
            reason=f"Manual action by {admin.email}: {reason}",
        )
        
        self._responses.append(response)
        logger.warning(
            "manual_quarantine",
            target_type=target_type,
            target_id=str(target_id),
            admin=admin.email,
            reason=reason,
        )
        
        return response
```

---

## 5. Constitutional AI Analyzer

```python
# forge/core/governance/constitutional_ai.py
"""
Constitutional AI analysis for governance proposals.

Provides advisory (non-binding) analysis based on:
- Forge constitution (defined principles)
- Historical precedent
- Risk assessment
"""
from forge.models.governance import Proposal
from forge.logging import get_logger

logger = get_logger(__name__)


class ConstitutionalAIAnalyzer:
    """
    AI-powered proposal analysis.
    
    Uses LLM to evaluate proposals against constitutional principles.
    Output is advisory only - humans make final decisions.
    """
    
    # Core constitutional principles
    CONSTITUTION = """
    FORGE CONSTITUTIONAL PRINCIPLES:
    
    1. KNOWLEDGE PRESERVATION: Changes should enhance, not diminish, 
       the system's ability to preserve and transmit knowledge.
    
    2. TRUST INTEGRITY: Trust levels should reflect actual reliability.
       Adjustments should be evidence-based and proportional.
    
    3. TRANSPARENCY: All governance decisions should be traceable
       and explainable. No hidden or automated binding decisions.
    
    4. GRADUAL CHANGE: Prefer incremental changes over dramatic ones.
       Reversibility is valued.
    
    5. HUMAN OVERSIGHT: Humans retain ultimate decision authority.
       AI provides analysis, not binding judgments.
    
    6. SECURITY: Changes should not introduce security vulnerabilities
       or reduce system resilience.
    
    7. FAIRNESS: Changes should not unfairly disadvantage specific
       users or use cases without strong justification.
    """
    
    def __init__(self, llm_client: "LLMClient"):
        self._llm = llm_client
    
    async def analyze_proposal(self, proposal: Proposal) -> dict:
        """
        Analyze a proposal against constitutional principles.
        
        Returns advisory analysis (non-binding).
        """
        prompt = f"""
        Analyze this governance proposal against the Forge constitution.
        
        {self.CONSTITUTION}
        
        PROPOSAL:
        Title: {proposal.title}
        Type: {proposal.type.value}
        Description: {proposal.description}
        Payload: {proposal.payload}
        
        Provide analysis in the following format:
        1. Constitutional alignment (which principles are affected)
        2. Potential risks
        3. Potential benefits
        4. Recommendation (support/oppose/neutral) with reasoning
        5. Suggested modifications (if any)
        
        Remember: This is advisory only. Final decision rests with voters.
        """
        
        try:
            response = await self._llm.complete(prompt, max_tokens=1000)
            
            analysis = {
                "raw_analysis": response,
                "recommendation": self._extract_recommendation(response),
                "risks": self._extract_risks(response),
                "benefits": self._extract_benefits(response),
                "is_advisory": True,  # Always emphasize this is non-binding
            }
            
            logger.info(
                "proposal_analyzed",
                proposal_id=str(proposal.id),
                recommendation=analysis["recommendation"],
            )
            
            return analysis
            
        except Exception as e:
            logger.error("ai_analysis_failed", error=str(e))
            return {
                "raw_analysis": None,
                "recommendation": "neutral",
                "error": str(e),
                "is_advisory": True,
            }
    
    def _extract_recommendation(self, analysis: str) -> str:
        """Extract recommendation from analysis text."""
        lower = analysis.lower()
        if "recommend support" in lower or "recommendation: support" in lower:
            return "support"
        elif "recommend oppose" in lower or "recommendation: oppose" in lower:
            return "oppose"
        return "neutral"
    
    def _extract_risks(self, analysis: str) -> list[str]:
        """Extract identified risks."""
        # Simple extraction - production would use structured output
        return []
    
    def _extract_benefits(self, analysis: str) -> list[str]:
        """Extract identified benefits."""
        return []
```

---

## 6. Next Steps

After completing Phase 4, proceed to **Phase 5: Security & Compliance** to implement:

- Authentication (password, MFA, API keys)
- Authorization (RBAC + ABAC)
- Encryption (at rest and in transit)
- Compliance logging and GDPR support
