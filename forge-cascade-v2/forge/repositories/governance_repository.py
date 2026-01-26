"""
Governance Repository

Manages democratic governance: proposals, votes, constitutional AI review,
and Ghost Council opinions. Supports trust-weighted voting.
"""

from datetime import datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel

from forge.database.client import Neo4jClient
from forge.models.base import ProposalStatus
from forge.models.governance import (
    ConstitutionalAnalysis,
    GhostCouncilOpinion,
    GovernanceStats,
    Proposal,
    ProposalCreate,
    ProposalType,
    Vote,
    VoteCreate,
    VoteDelegation,
)
from forge.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ProposalUpdate(BaseModel):
    """Schema for updating a proposal."""

    title: str | None = None
    description: str | None = None
    action: dict[str, Any] | None = None


class GovernanceRepository(BaseRepository[Proposal, ProposalCreate, ProposalUpdate]):
    """
    Repository for governance operations.

    Handles:
    - Proposal lifecycle (DRAFT → VOTING → PASSED/REJECTED → EXECUTED)
    - Trust-weighted voting
    - Constitutional AI review
    - Ghost Council deliberation
    - Vote delegation
    """

    def __init__(self, client: Neo4jClient):
        super().__init__(client)

    @property
    def node_label(self) -> str:
        return "Proposal"

    @property
    def model_class(self) -> type[Proposal]:
        cls: type[Proposal] = Proposal
        return cls

    # ═══════════════════════════════════════════════════════════════
    # PROPOSAL MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    async def create(  # type: ignore[override]
        self,
        data: ProposalCreate,
        proposer_id: str,
        **kwargs: object,
    ) -> Proposal:
        """
        Create a new proposal.

        Args:
            data: Proposal creation data
            proposer_id: ID of the user creating the proposal

        Returns:
            Created proposal
        """
        now = self._now()
        proposal_id = self._generate_id()

        # Serialize action dict to JSON string for Neo4j
        import json
        action_json = json.dumps(data.action) if data.action else "{}"

        query = """
        CREATE (p:Proposal {
            id: $id,
            title: $title,
            description: $description,
            type: $type,
            action: $action,
            proposer_id: $proposer_id,
            status: $status,
            voting_period_days: $voting_period_days,
            quorum_percent: $quorum_percent,
            pass_threshold: $pass_threshold,
            votes_for: 0,
            votes_against: 0,
            votes_abstain: 0,
            weight_for: 0.0,
            weight_against: 0.0,
            weight_abstain: 0.0,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": proposal_id,
                "title": data.title,
                "description": data.description,
                "type": data.type.value if hasattr(data.type, "value") else str(data.type),
                "action": action_json,
                "proposer_id": proposer_id,
                "status": ProposalStatus.DRAFT.value,
                "voting_period_days": data.voting_period_days,
                "quorum_percent": data.quorum_percent,
                "pass_threshold": data.pass_threshold,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )

        self.logger.info(
            "Created proposal",
            proposal_id=proposal_id,
            title=data.title,
            type=data.type.value if hasattr(data.type, "value") else str(data.type),
            proposer_id=proposer_id,
        )

        if result is None:
            raise RuntimeError("Failed to create proposal")
        proposal = self._to_model(result["entity"])
        if proposal is None:
            raise RuntimeError("Failed to deserialize created proposal")
        return proposal

    async def update(
        self,
        entity_id: str,
        data: ProposalUpdate,
    ) -> Proposal | None:
        """
        Update a proposal (only allowed in DRAFT status).

        Args:
            entity_id: Proposal ID
            data: Update fields

        Returns:
            Updated proposal or None
        """
        import json

        set_parts = ["p.updated_at = $now"]
        params: dict[str, Any] = {
            "id": entity_id,
            "now": self._now().isoformat(),
        }

        if data.title is not None:
            set_parts.append("p.title = $title")
            params["title"] = data.title

        if data.description is not None:
            set_parts.append("p.description = $description")
            params["description"] = data.description

        if data.action is not None:
            set_parts.append("p.action = $action")
            params["action"] = json.dumps(data.action)

        query = f"""
        MATCH (p:Proposal {{id: $id}})
        WHERE p.status = 'draft'
        SET {', '.join(set_parts)}
        RETURN p {{.*}} AS entity
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def start_voting(self, proposal_id: str) -> Proposal | None:
        """
        Start the voting period for a proposal.

        Args:
            proposal_id: Proposal ID

        Returns:
            Updated proposal
        """
        now = self._now()

        query = """
        MATCH (p:Proposal {id: $id})
        WHERE p.status = 'draft'
        SET
            p.status = 'voting',
            p.voting_starts_at = $starts_at,
            p.voting_ends_at = $ends_at,
            p.updated_at = $now
        RETURN p {.*} AS entity
        """

        # Get voting period days first
        proposal = await self.get_by_id(proposal_id)
        if not proposal:
            return None

        ends_at = now + timedelta(days=proposal.voting_period_days)

        result = await self.client.execute_single(
            query,
            {
                "id": proposal_id,
                "starts_at": now.isoformat(),
                "ends_at": ends_at.isoformat(),
                "now": now.isoformat(),
            },
        )

        if result and result.get("entity"):
            self.logger.info(
                "Voting started",
                proposal_id=proposal_id,
                ends_at=ends_at.isoformat(),
            )
            return self._to_model(result["entity"])
        return None

    async def close_voting(self, proposal_id: str) -> Proposal | None:
        """
        Close voting and determine outcome.

        Args:
            proposal_id: Proposal ID

        Returns:
            Updated proposal with final status
        """
        proposal = await self.get_by_id(proposal_id)
        if not proposal or proposal.status != ProposalStatus.VOTING:
            return None

        # SECURITY FIX (Audit 3): Complete quorum verification
        # Get total eligible voters and check quorum
        eligible_voters = await self._count_eligible_voters()
        total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain

        # SECURITY FIX (Audit 4 - M5): Check quorum properly
        # Cannot meet quorum if there are no eligible voters
        if eligible_voters == 0:
            self.logger.warning(
                "quorum_check_no_voters",
                proposal_id=proposal_id,
                eligible_voters=0,
            )
            quorum_met = False
        else:
            participation_rate = total_votes / eligible_voters
            quorum_met = participation_rate >= proposal.quorum_percent

        # Determine if passed (must meet both quorum AND approval threshold)
        passed = (
            quorum_met and
            proposal.approval_ratio >= proposal.pass_threshold
        )

        # Log quorum status
        self.logger.info(
            "quorum_check",
            proposal_id=proposal_id,
            eligible_voters=eligible_voters,
            total_votes=total_votes,
            quorum_percent=proposal.quorum_percent,
            quorum_met=quorum_met,
            approval_ratio=proposal.approval_ratio,
            pass_threshold=proposal.pass_threshold,
        )

        new_status = ProposalStatus.PASSED if passed else ProposalStatus.REJECTED

        # SECURITY FIX (Audit 3): Calculate timelock for passed proposals
        from datetime import timedelta
        now = self._now()
        execution_allowed_after = None
        if passed:
            timelock_hours = getattr(proposal, 'timelock_hours', 24)
            execution_allowed_after = now + timedelta(hours=timelock_hours)
            self.logger.info(
                "timelock_set",
                proposal_id=proposal_id,
                timelock_hours=timelock_hours,
                execution_allowed_after=execution_allowed_after.isoformat(),
            )

        query = """
        MATCH (p:Proposal {id: $id})
        SET
            p.status = $status,
            p.updated_at = $now,
            p.execution_allowed_after = $execution_allowed_after
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": proposal_id,
                "status": new_status.value,
                "now": now.isoformat(),
                "execution_allowed_after": execution_allowed_after.isoformat() if execution_allowed_after else None,
            },
        )

        if result and result.get("entity"):
            self.logger.info(
                "Voting closed",
                proposal_id=proposal_id,
                result="passed" if passed else "rejected",
                approval_ratio=proposal.approval_ratio,
            )
            return self._to_model(result["entity"])
        return None

    async def _count_eligible_voters(self, min_trust_level: int = 30) -> int:
        """
        Count users eligible to vote on proposals.

        SECURITY FIX (Audit 3): Implement proper quorum calculation
        by counting active users with sufficient trust level.

        Args:
            min_trust_level: Minimum trust flame required to vote (default: 30 = STANDARD)

        Returns:
            Number of eligible voters
        """
        query = """
        MATCH (u:User)
        WHERE u.is_active = true
          AND u.trust_flame >= $min_trust
        RETURN count(u) AS eligible_count
        """

        result = await self.client.execute_single(
            query,
            {"min_trust": min_trust_level},
        )

        return result.get("eligible_count", 0) if result else 0

    async def mark_executed(self, proposal_id: str) -> Proposal | None:
        """
        Mark a passed proposal as executed.

        SECURITY FIX (Audit 4 - H21): Now verifies that the timelock has
        expired before allowing execution. This prevents premature execution
        of proposals that should have a mandatory waiting period.

        Args:
            proposal_id: Proposal ID

        Returns:
            Updated proposal, or None if timelock not yet expired
        """
        now = self._now()
        now_iso = now.isoformat()

        # SECURITY FIX: Add timelock verification to prevent early execution
        # The proposal can only be executed if:
        # 1. Status is 'passed'
        # 2. Either no execution_allowed_after is set, OR it has already passed
        query = """
        MATCH (p:Proposal {id: $id})
        WHERE p.status = 'passed'
          AND (
            p.execution_allowed_after IS NULL
            OR datetime(p.execution_allowed_after) <= datetime($now)
          )
        SET
            p.status = 'executed',
            p.executed_at = $now,
            p.updated_at = $now
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {"id": proposal_id, "now": now_iso},
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])

        # If no result, check if it's due to timelock or other reason
        check_query = """
        MATCH (p:Proposal {id: $id})
        RETURN p.status AS status, p.execution_allowed_after AS timelock
        """
        check_result = await self.client.execute_single(check_query, {"id": proposal_id})

        if check_result:
            status = check_result.get("status")
            timelock = check_result.get("timelock")
            if status == "passed" and timelock:
                # Log that timelock blocked execution
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "proposal_execution_blocked_by_timelock",
                    proposal_id=proposal_id,
                    timelock=timelock,
                    current_time=now_iso
                )

        return None

    async def cancel(self, proposal_id: str, reason: str) -> Proposal | None:
        """
        Cancel a proposal.

        Args:
            proposal_id: Proposal ID
            reason: Cancellation reason

        Returns:
            Updated proposal
        """
        query = """
        MATCH (p:Proposal {id: $id})
        WHERE p.status IN ['draft', 'voting']
        SET
            p.status = 'cancelled',
            p.cancellation_reason = $reason,
            p.updated_at = $now
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": proposal_id,
                "reason": reason,
                "now": self._now().isoformat(),
            },
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    # ═══════════════════════════════════════════════════════════════
    # VOTING
    # ═══════════════════════════════════════════════════════════════

    async def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote_data: VoteCreate,
        trust_weight: float,
    ) -> Vote | None:
        """
        Cast a vote on a proposal.

        SECURITY FIX (Audit 4 - H20): Now verifies voter's actual trust level
        instead of accepting trust_weight parameter blindly.

        Args:
            proposal_id: Proposal ID
            voter_id: Voter's user ID
            vote_data: Vote choice and optional reason
            trust_weight: Voter's trust-based weight (will be verified)

        Returns:
            Created vote or None if already voted
        """
        now = self._now().isoformat()
        vote_id = self._generate_id()

        # Check if already voted
        existing = await self.get_vote(proposal_id, voter_id)
        if existing:
            self.logger.warning(
                "User already voted",
                proposal_id=proposal_id,
                voter_id=voter_id,
            )
            return None

        # SECURITY FIX (Audit 4 - H20): Verify voter's actual trust level
        # Don't trust the trust_weight parameter - fetch from database
        verify_query = """
        MATCH (u:User {id: $voter_id})
        RETURN u.trust_flame AS trust_flame
        """
        verify_result = await self.client.execute_single(verify_query, {"voter_id": voter_id})

        if not verify_result:
            self.logger.warning(
                "Voter not found",
                voter_id=voter_id,
            )
            return None

        # Calculate verified weight from actual trust level
        actual_trust = verify_result.get("trust_flame", 0) or 0

        # Clamp trust to valid range and calculate weight
        clamped_trust = max(0, min(actual_trust, 100))
        verified_weight = clamped_trust / 100.0  # Normalize to 0-1

        # Log if there's a mismatch between claimed and actual weight
        if abs(trust_weight - verified_weight) > 0.01:
            self.logger.warning(
                "trust_weight_mismatch_corrected",
                proposal_id=proposal_id,
                voter_id=voter_id,
                claimed_weight=trust_weight,
                verified_weight=verified_weight,
                actual_trust=actual_trust
            )

        # Create vote and update proposal tallies atomically
        # Use verified_weight instead of untrusted trust_weight parameter
        query = """
        MATCH (p:Proposal {id: $proposal_id})
        WHERE p.status = 'voting'
        CREATE (v:Vote {
            id: $vote_id,
            proposal_id: $proposal_id,
            voter_id: $voter_id,
            choice: $choice,
            weight: $weight,
            reason: $reason,
            created_at: $now,
            updated_at: $now
        })
        CREATE (v)-[:VOTED]->(p)
        SET
            p.votes_for = CASE WHEN $choice = 'for' THEN p.votes_for + 1 ELSE p.votes_for END,
            p.votes_against = CASE WHEN $choice = 'against' THEN p.votes_against + 1 ELSE p.votes_against END,
            p.votes_abstain = CASE WHEN $choice = 'abstain' THEN p.votes_abstain + 1 ELSE p.votes_abstain END,
            p.weight_for = CASE WHEN $choice = 'for' THEN p.weight_for + $weight ELSE p.weight_for END,
            p.weight_against = CASE WHEN $choice = 'against' THEN p.weight_against + $weight ELSE p.weight_against END,
            p.weight_abstain = CASE WHEN $choice = 'abstain' THEN p.weight_abstain + $weight ELSE p.weight_abstain END,
            p.updated_at = $now
        RETURN v {.*} AS vote
        """

        # Handle both string and enum choice
        choice_val = vote_data.choice.value if hasattr(vote_data.choice, 'value') else str(vote_data.choice)

        result = await self.client.execute_single(
            query,
            {
                "proposal_id": proposal_id,
                "vote_id": vote_id,
                "voter_id": voter_id,
                "choice": choice_val,
                "weight": verified_weight,  # SECURITY FIX: Use verified weight
                "reason": vote_data.reason,
                "now": now,
            },
        )

        if result and result.get("vote"):
            self.logger.info(
                "Vote cast",
                proposal_id=proposal_id,
                voter_id=voter_id,
                choice=choice_val,
                weight=verified_weight,  # SECURITY FIX: Log verified weight
            )
            return Vote.model_validate(result["vote"])
        return None

    async def get_vote(self, proposal_id: str, voter_id: str) -> Vote | None:
        """Get a user's vote on a proposal."""
        query = """
        MATCH (v:Vote {proposal_id: $proposal_id, voter_id: $voter_id})
        RETURN v {.*} AS vote
        """

        result = await self.client.execute_single(
            query,
            {"proposal_id": proposal_id, "voter_id": voter_id},
        )

        if result and result.get("vote"):
            return Vote.model_validate(result["vote"])
        return None

    async def get_votes(
        self,
        proposal_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Vote]:
        """Get all votes for a proposal."""
        query = """
        MATCH (v:Vote)-[:VOTED]->(p:Proposal {id: $proposal_id})
        RETURN v {.*} AS vote
        ORDER BY v.created_at DESC
        SKIP $skip
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"proposal_id": proposal_id, "skip": skip, "limit": limit},
        )

        return [
            Vote.model_validate(r["vote"])
            for r in results
            if r.get("vote")
        ]

    async def get_voter_history(
        self,
        voter_id: str,
        limit: int = 50,
    ) -> list[Vote]:
        """Get a user's voting history."""
        query = """
        MATCH (v:Vote {voter_id: $voter_id})
        RETURN v {.*} AS vote
        ORDER BY v.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"voter_id": voter_id, "limit": limit},
        )

        return [
            Vote.model_validate(r["vote"])
            for r in results
            if r.get("vote")
        ]

    # ═══════════════════════════════════════════════════════════════
    # VOTE DELEGATION
    # ═══════════════════════════════════════════════════════════════

    async def create_delegation(
        self,
        delegation: VoteDelegation,
    ) -> bool:
        """
        Create a vote delegation.

        Args:
            delegation: Delegation configuration

        Returns:
            True if created
        """

        query = """
        MERGE (d:VoteDelegation {
            delegator_id: $delegator_id,
            delegate_id: $delegate_id
        })
        SET
            d.proposal_types = $proposal_types,
            d.expires_at = $expires_at,
            d.created_at = $created_at
        RETURN d {.*} AS delegation
        """

        result = await self.client.execute_single(
            query,
            {
                "delegator_id": delegation.delegator_id,
                "delegate_id": delegation.delegate_id,
                "proposal_types": (
                    [t.value for t in delegation.proposal_types]
                    if delegation.proposal_types
                    else None
                ),
                "expires_at": (
                    delegation.expires_at.isoformat()
                    if delegation.expires_at
                    else None
                ),
                "created_at": delegation.created_at.isoformat(),
            },
        )

        return result is not None

    async def revoke_delegation(
        self,
        delegator_id: str,
        delegate_id: str,
    ) -> bool:
        """Revoke a vote delegation."""
        query = """
        MATCH (d:VoteDelegation {
            delegator_id: $delegator_id,
            delegate_id: $delegate_id
        })
        DELETE d
        RETURN count(*) AS deleted
        """

        result = await self.client.execute_single(
            query,
            {"delegator_id": delegator_id, "delegate_id": delegate_id},
        )

        deleted: int = result.get("deleted", 0) if result else 0
        return deleted > 0

    async def get_delegates(self, delegator_id: str) -> list[VoteDelegation]:
        """Get all delegations from a user."""
        query = """
        MATCH (d:VoteDelegation {delegator_id: $delegator_id})
        WHERE d.expires_at IS NULL OR d.expires_at > $now
        RETURN d {.*} AS delegation
        """

        results = await self.client.execute(
            query,
            {"delegator_id": delegator_id, "now": self._now().isoformat()},
        )

        delegations = []
        for r in results:
            if r.get("delegation"):
                d = r["delegation"]
                delegations.append(VoteDelegation(
                    delegator_id=d["delegator_id"],
                    delegate_id=d["delegate_id"],
                    proposal_types=(
                        [ProposalType(t) for t in d["proposal_types"]]
                        if d.get("proposal_types")
                        else None
                    ),
                    expires_at=(
                        datetime.fromisoformat(d["expires_at"])
                        if d.get("expires_at")
                        else None
                    ),
                ))
        return delegations

    # ═══════════════════════════════════════════════════════════════
    # CONSTITUTIONAL AI & GHOST COUNCIL
    # ═══════════════════════════════════════════════════════════════

    async def save_constitutional_review(
        self,
        proposal_id: str,
        analysis: ConstitutionalAnalysis,
    ) -> bool:
        """
        Save Constitutional AI review for a proposal.

        Args:
            proposal_id: Proposal ID
            analysis: Constitutional analysis

        Returns:
            True if saved
        """

        query = """
        MATCH (p:Proposal {id: $proposal_id})
        SET
            p.constitutional_review = $review_json,
            p.updated_at = $now
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "proposal_id": proposal_id,
                "review_json": analysis.model_dump_json(),
                "now": self._now().isoformat(),
            },
        )

        if result:
            self.logger.info(
                "Constitutional review saved",
                proposal_id=proposal_id,
                recommendation=analysis.recommendation,
                overall_score=analysis.overall_score,
            )

        return result is not None

    async def save_ghost_council_opinion(
        self,
        proposal_id: str,
        opinion: GhostCouncilOpinion,
    ) -> bool:
        """
        Save Ghost Council opinion for a proposal.

        Args:
            proposal_id: Proposal ID
            opinion: Ghost Council collective opinion

        Returns:
            True if saved
        """
        query = """
        MATCH (p:Proposal {id: $proposal_id})
        SET
            p.ghost_council_opinion = $opinion_json,
            p.updated_at = $now
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "proposal_id": proposal_id,
                "opinion_json": opinion.model_dump_json(),
                "now": self._now().isoformat(),
            },
        )

        if result:
            self.logger.info(
                "Ghost Council opinion saved",
                proposal_id=proposal_id,
                consensus_vote=opinion.consensus_vote.value,
                consensus_strength=opinion.consensus_strength,
            )

        return result is not None

    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════

    async def get_by_status(
        self,
        status: ProposalStatus,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Proposal]:
        """Get proposals by status."""
        return await self.find_by_field("status", status.value, limit)

    async def get_active_proposals(self) -> list[Proposal]:
        """Get all proposals currently accepting votes."""
        now = self._now().isoformat()

        query = """
        MATCH (p:Proposal)
        WHERE p.status = 'voting'
        AND p.voting_ends_at > $now
        RETURN p {.*} AS entity
        ORDER BY p.voting_ends_at ASC
        """

        results = await self.client.execute(query, {"now": now})
        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_by_proposer(
        self,
        proposer_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Proposal]:
        """Get proposals by a specific user."""
        query = """
        MATCH (p:Proposal {proposer_id: $proposer_id})
        RETURN p {.*} AS entity
        ORDER BY p.created_at DESC
        SKIP $skip
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"proposer_id": proposer_id, "skip": skip, "limit": limit},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_by_type(
        self,
        proposal_type: ProposalType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Proposal]:
        """Get proposals by type."""
        return await self.find_by_field("type", proposal_type.value, limit)

    async def get_expiring_soon(
        self,
        hours: int = 24,
    ) -> list[Proposal]:
        """Get proposals expiring within the specified hours."""
        now = self._now()
        deadline = (now + timedelta(hours=hours)).isoformat()

        query = """
        MATCH (p:Proposal)
        WHERE p.status = 'voting'
        AND p.voting_ends_at <= $deadline
        AND p.voting_ends_at > $now
        RETURN p {.*} AS entity
        ORDER BY p.voting_ends_at ASC
        """

        results = await self.client.execute(
            query,
            {"now": now.isoformat(), "deadline": deadline},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════
    # API ROUTE METHODS
    # ═══════════════════════════════════════════════════════════════

    async def list_proposals(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[Proposal], int]:
        """
        List proposals with pagination and filtering.

        Args:
            offset: Number of records to skip
            limit: Maximum records to return
            filters: Optional filter dict (status, proposal_type)

        Returns:
            Tuple of (proposals list, total count)
        """
        where_clauses = []
        params: dict[str, Any] = {"offset": offset, "limit": limit}

        if filters:
            if "status" in filters:
                where_clauses.append("p.status = $status")
                params["status"] = filters["status"]
            if "proposal_type" in filters:
                where_clauses.append("p.type = $proposal_type")
                params["proposal_type"] = filters["proposal_type"]

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"""
        MATCH (p:Proposal)
        WHERE {where_clause}
        RETURN count(p) AS total
        """
        count_result = await self.client.execute_single(count_query, params)
        total = count_result.get("total", 0) if count_result else 0

        # Get paginated results
        query = f"""
        MATCH (p:Proposal)
        WHERE {where_clause}
        RETURN p {{.*}} AS entity
        ORDER BY p.created_at DESC
        SKIP $offset
        LIMIT $limit
        """

        results = await self.client.execute(query, params)
        proposals = self._to_models([r["entity"] for r in results if r.get("entity")])

        return proposals, total

    async def get_proposal(self, proposal_id: str) -> Proposal | None:
        """Get a proposal by ID (alias for get_by_id)."""
        return await self.get_by_id(proposal_id)

    async def update_proposal_status(
        self,
        proposal_id: str,
        status: ProposalStatus,
    ) -> Proposal | None:
        """
        Update a proposal's status.

        Args:
            proposal_id: Proposal ID
            status: New status

        Returns:
            Updated proposal or None
        """
        query = """
        MATCH (p:Proposal {id: $id})
        SET p.status = $status, p.updated_at = $now
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": proposal_id,
                "status": status.value,
                "now": self._now().isoformat(),
            },
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def record_vote(self, vote: Vote) -> Vote:
        """
        Record a vote atomically to prevent double voting.

        Uses MERGE to ensure only one vote per user per proposal exists,
        preventing race conditions in concurrent voting scenarios.

        Args:
            vote: Vote object to record

        Returns:
            Recorded vote
        """
        now = self._now().isoformat()

        # SECURITY FIX: Use MERGE to atomically prevent double voting
        # This handles race conditions where two concurrent vote requests
        # might both pass the existing vote check
        query = """
        MATCH (p:Proposal {id: $proposal_id})
        WHERE p.status IN ['active', 'voting']
        MERGE (v:Vote {proposal_id: $proposal_id, voter_id: $voter_id})
        ON CREATE SET
            v.id = $vote_id,
            v.choice = $choice,
            v.weight = $weight,
            v.reason = $reason,
            v.created_at = $now,
            v.updated_at = $now,
            v.is_new = true
        ON MATCH SET
            v.is_new = false
        WITH v, p, v.is_new AS is_new
        WHERE is_new = true
        MERGE (v)-[:VOTED]->(p)
        SET
            p.votes_for = CASE WHEN $choice = 'APPROVE' THEN p.votes_for + 1 ELSE p.votes_for END,
            p.votes_against = CASE WHEN $choice = 'REJECT' THEN p.votes_against + 1 ELSE p.votes_against END,
            p.votes_abstain = CASE WHEN $choice = 'ABSTAIN' THEN p.votes_abstain + 1 ELSE p.votes_abstain END,
            p.weight_for = CASE WHEN $choice = 'APPROVE' THEN p.weight_for + $weight ELSE p.weight_for END,
            p.weight_against = CASE WHEN $choice = 'REJECT' THEN p.weight_against + $weight ELSE p.weight_against END,
            p.weight_abstain = CASE WHEN $choice = 'ABSTAIN' THEN p.weight_abstain + $weight ELSE p.weight_abstain END,
            p.updated_at = $now,
            v.is_new = null
        RETURN v {.*} AS vote, is_new
        """

        # Handle both string and enum choice
        choice_str = vote.choice.value if hasattr(vote.choice, 'value') else str(vote.choice)

        result = await self.client.execute_single(
            query,
            {
                "proposal_id": vote.proposal_id,
                "vote_id": vote.id,
                "voter_id": vote.voter_id,
                "choice": choice_str,
                "weight": vote.weight,
                "reason": vote.reason,
                "now": now,
            },
        )

        # If is_new is False, vote already existed (concurrent request)
        if result and result.get("is_new") is False:
            self.logger.warning(
                "Duplicate vote attempt blocked",
                proposal_id=vote.proposal_id,
                voter_id=vote.voter_id,
            )

        return vote

    async def get_user_vote(self, proposal_id: str, user_id: str) -> Vote | None:
        """Get a user's vote on a proposal (alias for get_vote)."""
        return await self.get_vote(proposal_id, user_id)

    async def get_proposal_votes(self, proposal_id: str) -> list[Vote]:
        """Get all votes on a proposal (alias for get_votes)."""
        return await self.get_votes(proposal_id)

    async def get_active_policies(self) -> list[dict[str, Any]]:
        """
        Get all active governance policies.

        Returns:
            List of policy dicts
        """
        # In a real implementation, this would query actual policy nodes
        # For now, return system default policies
        return [
            {
                "id": "policy_quorum",
                "name": "Quorum Requirement",
                "description": "Minimum participation required for valid vote",
                "value": 0.1,
                "is_active": True,
            },
            {
                "id": "policy_threshold",
                "name": "Pass Threshold",
                "description": "Minimum approval ratio to pass proposals",
                "value": 0.5,
                "is_active": True,
            },
            {
                "id": "policy_voting_period",
                "name": "Default Voting Period",
                "description": "Default duration for proposal voting",
                "value": 7,
                "unit": "days",
                "is_active": True,
            },
        ]

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """
        Get a specific policy.

        Args:
            policy_id: Policy ID

        Returns:
            Policy dict or None
        """
        policies = await self.get_active_policies()
        for policy in policies:
            if policy["id"] == policy_id:
                return policy
        return None

    async def create_delegation_from_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a vote delegation from a dict.

        Args:
            data: Delegation data dict

        Returns:
            Created delegation as dict
        """

        query = """
        CREATE (d:VoteDelegation {
            id: $id,
            delegator_id: $delegator_id,
            delegate_id: $delegate_id,
            proposal_types: $proposal_types,
            is_active: $is_active,
            expires_at: $expires_at,
            created_at: $created_at
        })
        RETURN d {.*} AS delegation
        """

        result = await self.client.execute_single(
            query,
            {
                "id": data["id"],
                "delegator_id": data["delegator_id"],
                "delegate_id": data["delegate_id"],
                "proposal_types": data.get("proposal_types"),
                "is_active": data.get("is_active", True),
                "expires_at": data.get("expires_at"),
                "created_at": self._now().isoformat(),
            },
        )

        if result and result.get("delegation"):
            delegation: dict[str, Any] = result["delegation"]
            return delegation
        return data

    async def get_stats(self) -> GovernanceStats:
        """Get governance system statistics."""
        query = """
        MATCH (p:Proposal)
        WITH
            count(p) AS total,
            count(CASE WHEN p.status = 'voting' THEN 1 END) AS active,
            count(CASE WHEN p.status IN ['passed', 'executed'] THEN 1 END) AS passed,
            count(CASE WHEN p.status = 'rejected' THEN 1 END) AS rejected
        OPTIONAL MATCH (v:Vote)
        WITH total, active, passed, rejected,
            count(v) AS total_votes,
            count(DISTINCT v.voter_id) AS unique_voters
        RETURN {
            total_proposals: total,
            active_proposals: active,
            passed_proposals: passed,
            rejected_proposals: rejected,
            total_votes: total_votes,
            unique_voters: unique_voters
        } AS stats
        """

        result = await self.client.execute_single(query)

        if result and result.get("stats"):
            return GovernanceStats.model_validate(result["stats"])
        return GovernanceStats()

    # ═══════════════════════════════════════════════════════════════
    # ADDITIONAL DELEGATION METHODS
    # ═══════════════════════════════════════════════════════════════

    async def get_delegation(self, delegation_id: str) -> VoteDelegation | None:
        """Get a specific delegation by ID."""
        query = """
        MATCH (d:VoteDelegation {id: $delegation_id})
        RETURN d {.*} AS delegation
        """

        result = await self.client.execute_single(
            query,
            {"delegation_id": delegation_id},
        )

        if result and result.get("delegation"):
            return VoteDelegation.model_validate(result["delegation"])
        return None

    async def get_user_delegations(self, user_id: str) -> list[VoteDelegation]:
        """Get all delegations where user is either delegator or delegate."""
        query = """
        MATCH (d:VoteDelegation)
        WHERE d.delegator_id = $user_id OR d.delegate_id = $user_id
        RETURN d {.*} AS delegation
        ORDER BY d.created_at DESC
        """

        results = await self.client.execute(
            query,
            {"user_id": user_id},
        )

        delegations = []
        for r in results:
            if r.get("delegation"):
                try:
                    delegations.append(VoteDelegation.model_validate(r["delegation"]))
                except Exception:
                    pass

        return delegations

    async def revoke_delegation_by_id(self, delegation_id: str) -> bool:
        """Revoke a delegation by its ID."""
        query = """
        MATCH (d:VoteDelegation {id: $delegation_id})
        SET d.is_active = false
        RETURN count(*) AS updated
        """

        result = await self.client.execute_single(
            query,
            {"delegation_id": delegation_id},
        )

        updated: int = result.get("updated", 0) if result else 0
        return updated > 0
