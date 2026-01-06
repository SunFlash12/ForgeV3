"""
Forge Cascade V2 - Ghost Council Service

The Ghost Council is an AI advisory board that provides recommendations
on governance proposals and responds to serious system issues.

Features:
- Multiple AI personas with different expertise areas
- Deliberation on proposals with voting and reasoning
- Automatic detection and response to serious issues
- Integration with Constitutional AI for ethical review
- Event-driven alerts for critical situations
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Callable
from uuid import uuid4

import structlog

from forge.models.governance import (
    GhostCouncilMember,
    GhostCouncilVote,
    GhostCouncilOpinion,
    VoteChoice,
    Proposal,
)
from forge.models.events import EventType

logger = structlog.get_logger(__name__)


class IssueSeverity(str, Enum):
    """Severity levels for system issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    """Categories of serious issues."""
    SECURITY = "security"
    GOVERNANCE = "governance"
    TRUST = "trust"
    SYSTEM = "system"
    ETHICAL = "ethical"
    DATA_INTEGRITY = "data_integrity"


@dataclass
class SeriousIssue:
    """A serious issue requiring Ghost Council attention."""
    id: str
    category: IssueCategory
    severity: IssueSeverity
    title: str
    description: str
    affected_entities: list[str]
    detected_at: datetime
    source: str  # What component detected this
    context: dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution: Optional[str] = None
    ghost_council_opinion: Optional[GhostCouncilOpinion] = None


@dataclass
class GhostCouncilConfig:
    """Configuration for Ghost Council."""
    # Deliberation settings
    require_unanimous_for_critical: bool = True
    min_confidence_threshold: float = 0.6

    # Auto-trigger thresholds
    auto_review_security_issues: bool = True
    auto_review_trust_drops: bool = True
    auto_review_governance_conflicts: bool = True

    # Response timeouts (seconds)
    max_deliberation_time: float = 60.0

    # Severity thresholds
    critical_security_events: int = 3  # Trigger after N security events
    trust_drop_threshold: float = 20.0  # Trigger if trust drops by this much


# Default Ghost Council Members - Each with a unique perspective
DEFAULT_COUNCIL_MEMBERS = [
    GhostCouncilMember(
        id="gc_ethics",
        name="Sophia (Ethics Guardian)",
        role="Ethics Advisor",
        persona="""You are Sophia, the Ethics Guardian of the Ghost Council.
Your focus is on ethical implications, fairness, and ensuring decisions align
with moral principles. You consider the impact on all stakeholders and advocate
for transparency and justice. You're cautious about changes that could harm
vulnerable participants or create unfair advantages.""",
        weight=1.2,
    ),
    GhostCouncilMember(
        id="gc_security",
        name="Marcus (Security Sentinel)",
        role="Security Expert",
        persona="""You are Marcus, the Security Sentinel of the Ghost Council.
Your focus is on system security, threat assessment, and risk mitigation.
You evaluate proposals and issues for security vulnerabilities, potential
exploits, and overall system stability. You're skeptical of changes that
reduce security controls or expand attack surfaces.""",
        weight=1.3,
    ),
    GhostCouncilMember(
        id="gc_governance",
        name="Helena (Governance Keeper)",
        role="Governance Expert",
        persona="""You are Helena, the Governance Keeper of the Ghost Council.
Your focus is on democratic principles, procedural fairness, and institutional
memory. You ensure decisions respect established governance processes and
precedents. You advocate for inclusive decision-making and guard against
concentration of power.""",
        weight=1.1,
    ),
    GhostCouncilMember(
        id="gc_technical",
        name="Kai (Technical Architect)",
        role="Technical Expert",
        persona="""You are Kai, the Technical Architect of the Ghost Council.
Your focus is on technical feasibility, system architecture, and implementation
risks. You evaluate whether proposals are technically sound and won't introduce
technical debt or system instability. You advocate for clean, maintainable
solutions.""",
        weight=1.0,
    ),
    GhostCouncilMember(
        id="gc_community",
        name="Aria (Community Voice)",
        role="Community Advocate",
        persona="""You are Aria, the Community Voice of the Ghost Council.
Your focus is on community impact, user experience, and social dynamics.
You consider how decisions affect the community, advocate for user needs,
and ensure the system serves its participants well. You're sensitive to
changes that could fragment or alienate community members.""",
        weight=1.0,
    ),
]


class GhostCouncilService:
    """
    Service for Ghost Council operations.

    The Ghost Council provides AI-powered advisory opinions on:
    - Governance proposals
    - Serious system issues
    - Policy conflicts
    - Trust hierarchy changes

    Usage:
        service = GhostCouncilService()

        # Review a proposal
        opinion = await service.deliberate_proposal(proposal)

        # Respond to a serious issue
        response = await service.respond_to_issue(issue)
    """

    def __init__(
        self,
        config: Optional[GhostCouncilConfig] = None,
        members: Optional[list[GhostCouncilMember]] = None,
    ):
        self._config = config or GhostCouncilConfig()
        self._members = members or DEFAULT_COUNCIL_MEMBERS
        self._active_issues: dict[str, SeriousIssue] = {}
        self._issue_handlers: list[Callable[[SeriousIssue], None]] = []

        # Statistics
        self._stats = {
            "proposals_reviewed": 0,
            "issues_responded": 0,
            "unanimous_decisions": 0,
            "split_decisions": 0,
        }

        logger.info(
            "ghost_council_initialized",
            members=len(self._members),
            member_names=[m.name for m in self._members],
        )

    @property
    def members(self) -> list[GhostCouncilMember]:
        """Get Ghost Council members."""
        return self._members

    @property
    def config(self) -> GhostCouncilConfig:
        """Get configuration."""
        return self._config

    def add_issue_handler(self, handler: Callable[[SeriousIssue], None]) -> None:
        """Add a handler for serious issues."""
        self._issue_handlers.append(handler)

    async def deliberate_proposal(
        self,
        proposal: Proposal,
        context: Optional[dict[str, Any]] = None,
        constitutional_review: Optional[dict[str, Any]] = None,
    ) -> GhostCouncilOpinion:
        """
        Have the Ghost Council deliberate on a proposal.

        Args:
            proposal: The governance proposal to review
            context: Additional context (voting data, history, etc.)
            constitutional_review: Optional Constitutional AI review

        Returns:
            Collective Ghost Council opinion
        """
        logger.info(
            "ghost_council_deliberating",
            proposal_id=proposal.id,
            proposal_title=proposal.title,
        )

        # Get LLM service
        from forge.services.llm import get_llm_service, LLMMessage
        llm = get_llm_service()

        member_votes: list[GhostCouncilVote] = []

        # Each council member deliberates
        for member in self._members:
            vote = await self._get_member_vote(
                member=member,
                proposal=proposal,
                context=context,
                constitutional_review=constitutional_review,
                llm=llm,
            )
            member_votes.append(vote)

        # Calculate consensus
        consensus = self._calculate_consensus(member_votes)

        # Build final opinion
        opinion = GhostCouncilOpinion(
            proposal_id=proposal.id,
            deliberated_at=datetime.now(timezone.utc),
            member_votes=member_votes,
            consensus_vote=consensus["vote"],
            consensus_strength=consensus["strength"],
            key_points=consensus["key_points"],
            dissenting_opinions=consensus["dissenting"],
            final_recommendation=consensus["recommendation"],
        )

        self._stats["proposals_reviewed"] += 1
        if consensus["strength"] >= 0.9:
            self._stats["unanimous_decisions"] += 1
        else:
            self._stats["split_decisions"] += 1

        logger.info(
            "ghost_council_deliberation_complete",
            proposal_id=proposal.id,
            consensus_vote=consensus["vote"].value,
            consensus_strength=consensus["strength"],
            votes={
                "approve": sum(1 for v in member_votes if v.vote == VoteChoice.APPROVE),
                "reject": sum(1 for v in member_votes if v.vote == VoteChoice.REJECT),
                "abstain": sum(1 for v in member_votes if v.vote == VoteChoice.ABSTAIN),
            },
        )

        return opinion

    async def _get_member_vote(
        self,
        member: GhostCouncilMember,
        proposal: Proposal,
        context: Optional[dict[str, Any]],
        constitutional_review: Optional[dict[str, Any]],
        llm,
    ) -> GhostCouncilVote:
        """Get a single member's vote on a proposal."""
        from forge.services.llm import LLMMessage

        # Build the system prompt with member persona
        system_prompt = f"""{member.persona}

As a member of the Ghost Council, you are reviewing a governance proposal.
Your vote will be weighted at {member.weight}x in the final tally.

Analyze the proposal and provide:
1. Your vote: APPROVE, REJECT, or ABSTAIN
2. Your reasoning (2-3 sentences)
3. Your confidence level (0.0-1.0)

Respond in JSON format:
{{
    "vote": "APPROVE" | "REJECT" | "ABSTAIN",
    "reasoning": "Your reasoning here",
    "confidence": 0.85
}}"""

        # Build user prompt with proposal details
        user_prompt = f"""**Proposal: {proposal.title}**

Type: {proposal.type.value if hasattr(proposal.type, 'value') else proposal.type}
Status: {proposal.status.value if hasattr(proposal.status, 'value') else proposal.status}

Description:
{proposal.description}

Current Votes:
- For: {proposal.votes_for} ({proposal.weight_for:.2f} weighted)
- Against: {proposal.votes_against} ({proposal.weight_against:.2f} weighted)
- Abstain: {proposal.votes_abstain}
"""

        if context:
            user_prompt += f"\nAdditional Context:\n{json.dumps(context, indent=2)}"

        if constitutional_review:
            user_prompt += f"""

Constitutional AI Review:
- Overall Score: {constitutional_review.get('overall_score', 'N/A')}
- Recommendation: {constitutional_review.get('recommendation', 'N/A')}
- Concerns: {constitutional_review.get('concerns', [])}
"""

        user_prompt += "\n\nProvide your Ghost Council vote as JSON:"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        try:
            response = await llm.complete(messages, temperature=0.3)

            # Parse response
            content = response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            result = json.loads(content)

            vote_str = result.get("vote", "ABSTAIN").upper()
            if vote_str == "APPROVE":
                vote = VoteChoice.APPROVE
            elif vote_str == "REJECT":
                vote = VoteChoice.REJECT
            else:
                vote = VoteChoice.ABSTAIN

            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                vote=vote,
                reasoning=result.get("reasoning", "No reasoning provided"),
                confidence=min(1.0, max(0.0, float(result.get("confidence", 0.5)))),
            )

        except Exception as e:
            logger.warning(
                "ghost_council_member_vote_failed",
                member=member.name,
                error=str(e),
            )
            # Default to abstain on error
            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                vote=VoteChoice.ABSTAIN,
                reasoning=f"Unable to complete analysis: {str(e)}",
                confidence=0.0,
            )

    def _calculate_consensus(
        self,
        votes: list[GhostCouncilVote],
    ) -> dict[str, Any]:
        """Calculate consensus from member votes."""
        if not votes:
            return {
                "vote": VoteChoice.ABSTAIN,
                "strength": 0.0,
                "key_points": [],
                "dissenting": [],
                "recommendation": "Unable to reach consensus - no votes",
            }

        # Calculate weighted votes
        weighted_approve = 0.0
        weighted_reject = 0.0
        weighted_abstain = 0.0

        member_weights = {m.id: m.weight for m in self._members}

        for vote in votes:
            weight = member_weights.get(vote.member_id, 1.0) * vote.confidence
            if vote.vote == VoteChoice.APPROVE:
                weighted_approve += weight
            elif vote.vote == VoteChoice.REJECT:
                weighted_reject += weight
            else:
                weighted_abstain += weight

        total_weight = weighted_approve + weighted_reject + weighted_abstain

        # Determine consensus vote
        if weighted_approve > weighted_reject and weighted_approve > weighted_abstain:
            consensus_vote = VoteChoice.APPROVE
            strength = weighted_approve / total_weight if total_weight > 0 else 0
        elif weighted_reject > weighted_approve and weighted_reject > weighted_abstain:
            consensus_vote = VoteChoice.REJECT
            strength = weighted_reject / total_weight if total_weight > 0 else 0
        else:
            consensus_vote = VoteChoice.ABSTAIN
            strength = 0.5  # Split or uncertain

        # Collect key points from approvers/majority
        key_points = []
        dissenting = []

        for vote in votes:
            if vote.vote == consensus_vote:
                if len(key_points) < 3:
                    key_points.append(f"{vote.member_name}: {vote.reasoning}")
            else:
                if len(dissenting) < 2:
                    dissenting.append(f"{vote.member_name}: {vote.reasoning}")

        # Build recommendation
        if consensus_vote == VoteChoice.APPROVE:
            if strength >= 0.8:
                recommendation = "STRONGLY APPROVE: The Ghost Council recommends approval with high confidence."
            else:
                recommendation = "APPROVE WITH CAUTION: The Ghost Council leans toward approval but recommends careful implementation."
        elif consensus_vote == VoteChoice.REJECT:
            if strength >= 0.8:
                recommendation = "STRONGLY REJECT: The Ghost Council recommends rejection due to significant concerns."
            else:
                recommendation = "LEAN REJECT: The Ghost Council has concerns and suggests revising the proposal."
        else:
            recommendation = "NO CONSENSUS: The Ghost Council is divided. Further community discussion recommended."

        return {
            "vote": consensus_vote,
            "strength": round(strength, 3),
            "key_points": key_points,
            "dissenting": dissenting,
            "recommendation": recommendation,
        }

    async def respond_to_issue(
        self,
        issue: SeriousIssue,
    ) -> GhostCouncilOpinion:
        """
        Have the Ghost Council respond to a serious issue.

        Args:
            issue: The serious issue requiring attention

        Returns:
            Ghost Council opinion with recommended actions
        """
        logger.warning(
            "ghost_council_responding_to_issue",
            issue_id=issue.id,
            category=issue.category.value,
            severity=issue.severity.value,
            title=issue.title,
        )

        # Store active issue
        self._active_issues[issue.id] = issue

        # Get LLM service
        from forge.services.llm import get_llm_service, LLMMessage
        llm = get_llm_service()

        member_votes: list[GhostCouncilVote] = []

        # Each council member provides input
        for member in self._members:
            vote = await self._get_member_issue_response(
                member=member,
                issue=issue,
                llm=llm,
            )
            member_votes.append(vote)

        # Calculate consensus
        consensus = self._calculate_issue_consensus(member_votes, issue)

        # Build opinion
        opinion = GhostCouncilOpinion(
            proposal_id=f"issue_{issue.id}",  # Use issue ID as proposal ID
            deliberated_at=datetime.now(timezone.utc),
            member_votes=member_votes,
            consensus_vote=consensus["vote"],
            consensus_strength=consensus["strength"],
            key_points=consensus["key_points"],
            dissenting_opinions=consensus["dissenting"],
            final_recommendation=consensus["recommendation"],
        )

        # Update issue with opinion
        issue.ghost_council_opinion = opinion

        self._stats["issues_responded"] += 1

        # Notify handlers
        for handler in self._issue_handlers:
            try:
                handler(issue)
            except Exception as e:
                logger.error("issue_handler_failed", error=str(e))

        logger.info(
            "ghost_council_issue_response_complete",
            issue_id=issue.id,
            recommendation=consensus["recommendation"][:100],
        )

        return opinion

    async def _get_member_issue_response(
        self,
        member: GhostCouncilMember,
        issue: SeriousIssue,
        llm,
    ) -> GhostCouncilVote:
        """Get a member's response to a serious issue."""
        from forge.services.llm import LLMMessage

        system_prompt = f"""{member.persona}

A SERIOUS ISSUE has been detected in the system that requires Ghost Council attention.
Severity: {issue.severity.value.upper()}
Category: {issue.category.value}

As a Ghost Council member, analyze this issue and recommend:
1. Whether to APPROVE (take immediate action), REJECT (dismiss as non-critical), or ABSTAIN
2. Your reasoning and recommended actions
3. Your confidence in the assessment

Respond in JSON:
{{
    "vote": "APPROVE" | "REJECT" | "ABSTAIN",
    "reasoning": "Your analysis and recommended actions",
    "confidence": 0.85
}}"""

        user_prompt = f"""**SERIOUS ISSUE ALERT**

Title: {issue.title}
Category: {issue.category.value}
Severity: {issue.severity.value}
Source: {issue.source}
Detected: {issue.detected_at.isoformat()}

Description:
{issue.description}

Affected Entities: {', '.join(issue.affected_entities) if issue.affected_entities else 'None specified'}

Context:
{json.dumps(issue.context, indent=2) if issue.context else 'No additional context'}

Provide your Ghost Council assessment as JSON:"""

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        try:
            response = await llm.complete(messages, temperature=0.2)

            content = response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            result = json.loads(content)

            vote_str = result.get("vote", "APPROVE").upper()  # Default to action for issues
            if vote_str == "APPROVE":
                vote = VoteChoice.APPROVE
            elif vote_str == "REJECT":
                vote = VoteChoice.REJECT
            else:
                vote = VoteChoice.ABSTAIN

            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                vote=vote,
                reasoning=result.get("reasoning", "Immediate attention recommended"),
                confidence=min(1.0, max(0.0, float(result.get("confidence", 0.8)))),
            )

        except Exception as e:
            logger.warning(
                "ghost_council_issue_response_failed",
                member=member.name,
                error=str(e),
            )
            # For issues, default to APPROVE (take action) on error
            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                vote=VoteChoice.APPROVE,
                reasoning=f"Unable to complete analysis, recommending precautionary action: {str(e)}",
                confidence=0.5,
            )

    def _calculate_issue_consensus(
        self,
        votes: list[GhostCouncilVote],
        issue: SeriousIssue,
    ) -> dict[str, Any]:
        """Calculate consensus for issue response."""
        base_consensus = self._calculate_consensus(votes)

        # For critical issues, require stronger consensus for dismissal
        if issue.severity == IssueSeverity.CRITICAL:
            if base_consensus["vote"] == VoteChoice.REJECT:
                # Check if unanimous
                if not all(v.vote == VoteChoice.REJECT for v in votes):
                    base_consensus["vote"] = VoteChoice.APPROVE
                    base_consensus["recommendation"] = (
                        "CRITICAL ISSUE - ACTION REQUIRED: Despite some disagreement, "
                        "critical severity mandates immediate response. "
                        + base_consensus["recommendation"]
                    )

        return base_consensus

    def detect_serious_issue(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        source: str,
    ) -> Optional[SeriousIssue]:
        """
        Detect if an event constitutes a serious issue.

        Args:
            event_type: The type of event
            payload: Event payload
            source: Source of the event

        Returns:
            SeriousIssue if detected, None otherwise
        """
        issue = None

        # Security violations
        if event_type in (EventType.SECURITY_ALERT, EventType.SECURITY_THREAT):
            threat_level = payload.get("threat_level", "medium")
            if threat_level in ("high", "critical"):
                issue = SeriousIssue(
                    id=str(uuid4()),
                    category=IssueCategory.SECURITY,
                    severity=IssueSeverity.CRITICAL if threat_level == "critical" else IssueSeverity.HIGH,
                    title=f"Security Threat Detected: {payload.get('threat_type', 'Unknown')}",
                    description=payload.get("description", "A security threat has been detected"),
                    affected_entities=payload.get("affected_entities", []),
                    detected_at=datetime.now(timezone.utc),
                    source=source,
                    context=payload,
                )

        # Trust violations
        elif event_type == EventType.TRUST_UPDATED:
            old_trust = payload.get("old_trust", 100)
            new_trust = payload.get("new_trust", 100)
            trust_drop = old_trust - new_trust

            if trust_drop >= self._config.trust_drop_threshold:
                issue = SeriousIssue(
                    id=str(uuid4()),
                    category=IssueCategory.TRUST,
                    severity=IssueSeverity.HIGH if trust_drop >= 30 else IssueSeverity.MEDIUM,
                    title=f"Significant Trust Drop: {payload.get('user_id', 'Unknown')}",
                    description=f"User trust dropped by {trust_drop} points (from {old_trust} to {new_trust})",
                    affected_entities=[payload.get("user_id", "unknown")],
                    detected_at=datetime.now(timezone.utc),
                    source=source,
                    context=payload,
                )

        # Governance conflicts
        elif event_type == EventType.GOVERNANCE_ACTION:
            action = payload.get("action", "")
            if action in ("proposal_vetoed", "emergency_action", "constitution_violation"):
                issue = SeriousIssue(
                    id=str(uuid4()),
                    category=IssueCategory.GOVERNANCE,
                    severity=IssueSeverity.HIGH,
                    title=f"Governance Alert: {action.replace('_', ' ').title()}",
                    description=payload.get("description", f"Governance action: {action}"),
                    affected_entities=[payload.get("proposal_id", "unknown")],
                    detected_at=datetime.now(timezone.utc),
                    source=source,
                    context=payload,
                )

        # System errors
        elif event_type in (EventType.SYSTEM_ERROR, EventType.PIPELINE_ERROR):
            error_count = payload.get("error_count", 1)
            if error_count >= 3 or payload.get("severity") == "critical":
                issue = SeriousIssue(
                    id=str(uuid4()),
                    category=IssueCategory.SYSTEM,
                    severity=IssueSeverity.HIGH,
                    title=f"System Error: {payload.get('error_type', 'Multiple errors')}",
                    description=payload.get("message", "Multiple system errors detected"),
                    affected_entities=payload.get("affected_components", []),
                    detected_at=datetime.now(timezone.utc),
                    source=source,
                    context=payload,
                )

        # Immune system alerts
        elif event_type == EventType.IMMUNE_ALERT:
            alert_type = payload.get("alert_type", "")
            if alert_type in ("quarantine", "circuit_breaker", "anomaly_critical"):
                issue = SeriousIssue(
                    id=str(uuid4()),
                    category=IssueCategory.SYSTEM,
                    severity=IssueSeverity.HIGH,
                    title=f"Immune System Alert: {alert_type.replace('_', ' ').title()}",
                    description=payload.get("description", f"Immune system triggered: {alert_type}"),
                    affected_entities=payload.get("affected_entities", []),
                    detected_at=datetime.now(timezone.utc),
                    source=source,
                    context=payload,
                )

        if issue:
            logger.warning(
                "serious_issue_detected",
                issue_id=issue.id,
                category=issue.category.value,
                severity=issue.severity.value,
                title=issue.title,
            )

        return issue

    def get_active_issues(self) -> list[SeriousIssue]:
        """Get all active (unresolved) issues."""
        return [
            issue for issue in self._active_issues.values()
            if not issue.resolved
        ]

    def resolve_issue(
        self,
        issue_id: str,
        resolution: str,
    ) -> bool:
        """Mark an issue as resolved."""
        if issue_id in self._active_issues:
            self._active_issues[issue_id].resolved = True
            self._active_issues[issue_id].resolution = resolution
            logger.info(
                "issue_resolved",
                issue_id=issue_id,
                resolution=resolution,
            )
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get Ghost Council statistics."""
        return {
            **self._stats,
            "active_issues": len(self.get_active_issues()),
            "total_issues_tracked": len(self._active_issues),
            "council_members": len(self._members),
        }


# =============================================================================
# Global Instance
# =============================================================================

_ghost_council_service: Optional[GhostCouncilService] = None


def get_ghost_council_service() -> GhostCouncilService:
    """Get the global Ghost Council service instance."""
    global _ghost_council_service
    if _ghost_council_service is None:
        _ghost_council_service = GhostCouncilService()
    return _ghost_council_service


def init_ghost_council_service(
    config: Optional[GhostCouncilConfig] = None,
    members: Optional[list[GhostCouncilMember]] = None,
) -> GhostCouncilService:
    """Initialize the global Ghost Council service."""
    global _ghost_council_service
    _ghost_council_service = GhostCouncilService(config=config, members=members)
    return _ghost_council_service


def shutdown_ghost_council_service() -> None:
    """Shutdown the Ghost Council service."""
    global _ghost_council_service
    _ghost_council_service = None


__all__ = [
    "GhostCouncilService",
    "GhostCouncilConfig",
    "SeriousIssue",
    "IssueSeverity",
    "IssueCategory",
    "get_ghost_council_service",
    "init_ghost_council_service",
    "shutdown_ghost_council_service",
    "DEFAULT_COUNCIL_MEMBERS",
]
