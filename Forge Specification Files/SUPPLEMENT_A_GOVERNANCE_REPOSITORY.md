# Forge V3 - Phase 4 Supplement: Governance Repository

**Purpose:** Complete implementation of GovernanceRepository that was referenced but not implemented in Phase 4.

**Add this to:** `forge/core/governance/repository.py`

---

```python
# forge/core/governance/repository.py
"""
Governance repository for proposals, votes, and governance state.

Handles all database operations for the governance system.
"""
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Any

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    Vote,
    ProposalStatus,
    ProposalType,
)
from forge.models.base import VoteDecision
from forge.exceptions import NotFoundError
from forge.logging import get_logger

logger = get_logger(__name__)


class GovernanceRepository:
    """
    Repository for governance data access.
    
    Manages proposals, votes, and governance configuration.
    """
    
    def __init__(self, neo4j: Neo4jClient):
        self._neo4j = neo4j
    
    # =========================================================================
    # PROPOSAL OPERATIONS
    # =========================================================================
    
    async def create_proposal(
        self,
        data: ProposalCreate,
        proposer_id: UUID,
        voting_ends_at: datetime,
    ) -> Proposal:
        """
        Create a new governance proposal.
        
        Starts in DRAFT status until explicitly activated.
        """
        proposal_id = uuid4()
        now = datetime.now(timezone.utc)
        
        result = await self._neo4j.run_single("""
            CREATE (p:Proposal {
                id: $id,
                title: $title,
                description: $description,
                type: $type,
                status: $status,
                payload: $payload,
                proposer_id: $proposer_id,
                voting_ends_at: datetime($voting_ends_at),
                quorum_percentage: $quorum_percentage,
                approval_threshold: $approval_threshold,
                votes_for: 0,
                votes_against: 0,
                votes_abstain: 0,
                total_eligible_weight: 0,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at)
            })
            RETURN p
        """, {
            "id": str(proposal_id),
            "title": data.title,
            "description": data.description,
            "type": data.type.value,
            "status": ProposalStatus.DRAFT.value,
            "payload": data.payload,
            "proposer_id": str(proposer_id),
            "voting_ends_at": voting_ends_at.isoformat(),
            "quorum_percentage": 0.3,  # 30% quorum default
            "approval_threshold": 0.5,  # 50% approval default
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        
        logger.info("proposal_created", proposal_id=str(proposal_id))
        return self._map_to_proposal(dict(result["p"]))
    
    async def get_proposal(self, proposal_id: UUID) -> Proposal | None:
        """Get a proposal by ID."""
        result = await self._neo4j.run_single("""
            MATCH (p:Proposal {id: $id})
            RETURN p
        """, {"id": str(proposal_id)})
        
        if not result:
            return None
        return self._map_to_proposal(dict(result["p"]))
    
    async def list_proposals(
        self,
        status: ProposalStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Proposal], int]:
        """
        List proposals with optional status filter.
        
        Returns (proposals, total_count).
        """
        where_clause = "true"
        params: dict[str, Any] = {
            "skip": (page - 1) * per_page,
            "limit": per_page,
        }
        
        if status:
            where_clause = "p.status = $status"
            params["status"] = status.value
        
        # Get total count
        count_result = await self._neo4j.run_single(f"""
            MATCH (p:Proposal)
            WHERE {where_clause}
            RETURN count(p) as total
        """, params)
        total = count_result["total"] if count_result else 0
        
        # Get paginated results
        results = await self._neo4j.run(f"""
            MATCH (p:Proposal)
            WHERE {where_clause}
            RETURN p
            ORDER BY p.created_at DESC
            SKIP $skip
            LIMIT $limit
        """, params)
        
        proposals = [self._map_to_proposal(dict(r["p"])) for r in results]
        return proposals, total
    
    async def activate_proposal(
        self,
        proposal_id: UUID,
        ai_analysis: dict | None,
        total_eligible_weight: float,
    ) -> Proposal:
        """
        Activate a draft proposal, opening it for voting.
        
        Sets status to ACTIVE and records voting start time.
        """
        now = datetime.now(timezone.utc)
        
        result = await self._neo4j.run_single("""
            MATCH (p:Proposal {id: $id})
            SET p.status = $status,
                p.voting_starts_at = datetime($voting_starts_at),
                p.ai_analysis = $ai_analysis,
                p.total_eligible_weight = $total_eligible_weight,
                p.updated_at = datetime()
            RETURN p
        """, {
            "id": str(proposal_id),
            "status": ProposalStatus.ACTIVE.value,
            "voting_starts_at": now.isoformat(),
            "ai_analysis": ai_analysis,
            "total_eligible_weight": total_eligible_weight,
        })
        
        if not result:
            raise NotFoundError("Proposal", str(proposal_id))
        
        logger.info("proposal_activated", proposal_id=str(proposal_id))
        return self._map_to_proposal(dict(result["p"]))
    
    async def close_proposal(
        self,
        proposal_id: UUID,
        final_status: ProposalStatus,
    ) -> Proposal:
        """
        Close voting on a proposal with final status.
        
        final_status should be APPROVED or REJECTED.
        """
        result = await self._neo4j.run_single("""
            MATCH (p:Proposal {id: $id})
            SET p.status = $status,
                p.updated_at = datetime()
            RETURN p
        """, {
            "id": str(proposal_id),
            "status": final_status.value,
        })
        
        if not result:
            raise NotFoundError("Proposal", str(proposal_id))
        
        logger.info("proposal_closed", proposal_id=str(proposal_id), status=final_status.value)
        return self._map_to_proposal(dict(result["p"]))
    
    async def mark_executed(
        self,
        proposal_id: UUID,
        result: str,
    ) -> Proposal:
        """Mark a proposal as executed with result."""
        now = datetime.now(timezone.utc)
        
        db_result = await self._neo4j.run_single("""
            MATCH (p:Proposal {id: $id})
            SET p.status = $status,
                p.executed_at = datetime($executed_at),
                p.execution_result = $result,
                p.updated_at = datetime()
            RETURN p
        """, {
            "id": str(proposal_id),
            "status": ProposalStatus.EXECUTED.value if "success" in result.lower() else ProposalStatus.FAILED.value,
            "executed_at": now.isoformat(),
            "result": result,
        })
        
        if not db_result:
            raise NotFoundError("Proposal", str(proposal_id))
        
        return self._map_to_proposal(dict(db_result["p"]))
    
    async def get_active_proposals_past_deadline(self) -> list[Proposal]:
        """
        Get all active proposals that have passed their voting deadline.
        
        Used by scheduler to close voting automatically.
        """
        now = datetime.now(timezone.utc)
        
        results = await self._neo4j.run("""
            MATCH (p:Proposal {status: 'active'})
            WHERE p.voting_ends_at <= datetime($now)
            RETURN p
        """, {"now": now.isoformat()})
        
        return [self._map_to_proposal(dict(r["p"])) for r in results]
    
    # =========================================================================
    # VOTE OPERATIONS
    # =========================================================================
    
    async def create_vote(
        self,
        proposal_id: UUID,
        voter_id: UUID,
        decision: VoteDecision,
        weight: float,
        reasoning: str | None = None,
    ) -> Vote:
        """Create a new vote on a proposal."""
        vote_id = uuid4()
        now = datetime.now(timezone.utc)
        
        async with self._neo4j.transaction() as tx:
            # Create vote node
            result = await tx.run("""
                CREATE (v:Vote {
                    id: $id,
                    proposal_id: $proposal_id,
                    voter_id: $voter_id,
                    decision: $decision,
                    weight: $weight,
                    reasoning: $reasoning,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                RETURN v
            """, {
                "id": str(vote_id),
                "proposal_id": str(proposal_id),
                "voter_id": str(voter_id),
                "decision": decision.value,
                "weight": weight,
                "reasoning": reasoning,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            
            vote_record = await result.single()
            
            # Create relationships
            await tx.run("""
                MATCH (v:Vote {id: $vote_id})
                MATCH (p:Proposal {id: $proposal_id})
                MATCH (u:User {id: $voter_id})
                CREATE (v)-[:CAST_ON]->(p)
                CREATE (v)-[:CAST_BY]->(u)
            """, {
                "vote_id": str(vote_id),
                "proposal_id": str(proposal_id),
                "voter_id": str(voter_id),
            })
        
        logger.info("vote_created", vote_id=str(vote_id), proposal_id=str(proposal_id))
        return self._map_to_vote(dict(vote_record["v"]))
    
    async def get_vote(
        self,
        proposal_id: UUID,
        voter_id: UUID,
    ) -> Vote | None:
        """Get a user's vote on a specific proposal."""
        result = await self._neo4j.run_single("""
            MATCH (v:Vote {proposal_id: $proposal_id, voter_id: $voter_id})
            RETURN v
        """, {
            "proposal_id": str(proposal_id),
            "voter_id": str(voter_id),
        })
        
        if not result:
            return None
        return self._map_to_vote(dict(result["v"]))
    
    async def update_vote(
        self,
        vote_id: UUID,
        decision: VoteDecision,
        reasoning: str | None = None,
    ) -> Vote:
        """Update an existing vote."""
        result = await self._neo4j.run_single("""
            MATCH (v:Vote {id: $id})
            SET v.decision = $decision,
                v.reasoning = $reasoning,
                v.updated_at = datetime()
            RETURN v
        """, {
            "id": str(vote_id),
            "decision": decision.value,
            "reasoning": reasoning,
        })
        
        if not result:
            raise NotFoundError("Vote", str(vote_id))
        
        logger.info("vote_updated", vote_id=str(vote_id))
        return self._map_to_vote(dict(result["v"]))
    
    async def get_votes_for_proposal(self, proposal_id: UUID) -> list[Vote]:
        """Get all votes cast on a proposal."""
        results = await self._neo4j.run("""
            MATCH (v:Vote {proposal_id: $proposal_id})
            RETURN v
            ORDER BY v.created_at
        """, {"proposal_id": str(proposal_id)})
        
        return [self._map_to_vote(dict(r["v"])) for r in results]
    
    async def recalculate_votes(self, proposal_id: UUID) -> None:
        """
        Recalculate vote tallies for a proposal.
        
        Aggregates all votes by decision and updates proposal totals.
        This is called after each vote to keep tallies current.
        """
        # Aggregate votes by decision
        results = await self._neo4j.run("""
            MATCH (v:Vote {proposal_id: $proposal_id})
            RETURN v.decision as decision, sum(v.weight) as total_weight
        """, {"proposal_id": str(proposal_id)})
        
        # Initialize tallies
        votes_for = 0.0
        votes_against = 0.0
        votes_abstain = 0.0
        
        # Sum up by decision type
        for record in results:
            decision = record["decision"]
            weight = record["total_weight"] or 0.0
            
            if decision == VoteDecision.FOR.value:
                votes_for = weight
            elif decision == VoteDecision.AGAINST.value:
                votes_against = weight
            elif decision == VoteDecision.ABSTAIN.value:
                votes_abstain = weight
        
        # Update proposal with new tallies
        await self._neo4j.run("""
            MATCH (p:Proposal {id: $id})
            SET p.votes_for = $votes_for,
                p.votes_against = $votes_against,
                p.votes_abstain = $votes_abstain,
                p.updated_at = datetime()
        """, {
            "id": str(proposal_id),
            "votes_for": votes_for,
            "votes_against": votes_against,
            "votes_abstain": votes_abstain,
        })
        
        logger.debug(
            "votes_recalculated",
            proposal_id=str(proposal_id),
            votes_for=votes_for,
            votes_against=votes_against,
            votes_abstain=votes_abstain,
        )
    
    async def get_voter_participation(self, user_id: UUID) -> dict:
        """Get voting statistics for a user."""
        result = await self._neo4j.run_single("""
            MATCH (v:Vote {voter_id: $user_id})
            RETURN count(v) as total_votes,
                   sum(CASE WHEN v.decision = 'for' THEN 1 ELSE 0 END) as votes_for,
                   sum(CASE WHEN v.decision = 'against' THEN 1 ELSE 0 END) as votes_against,
                   sum(CASE WHEN v.decision = 'abstain' THEN 1 ELSE 0 END) as votes_abstain
        """, {"user_id": str(user_id)})
        
        if not result:
            return {"total_votes": 0, "votes_for": 0, "votes_against": 0, "votes_abstain": 0}
        
        return {
            "total_votes": result["total_votes"],
            "votes_for": result["votes_for"],
            "votes_against": result["votes_against"],
            "votes_abstain": result["votes_abstain"],
        }
    
    # =========================================================================
    # GOVERNANCE METRICS
    # =========================================================================
    
    async def get_governance_metrics(self) -> dict:
        """Get overall governance system metrics."""
        result = await self._neo4j.run_single("""
            MATCH (p:Proposal)
            WITH count(p) as total,
                 sum(CASE WHEN p.status = 'active' THEN 1 ELSE 0 END) as active,
                 sum(CASE WHEN p.status = 'approved' THEN 1 ELSE 0 END) as approved,
                 sum(CASE WHEN p.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                 sum(CASE WHEN p.status = 'executed' THEN 1 ELSE 0 END) as executed
            MATCH (v:Vote)
            WITH total, active, approved, rejected, executed, count(v) as total_votes
            RETURN total, active, approved, rejected, executed, total_votes
        """)
        
        if not result:
            return {
                "total_proposals": 0,
                "active_proposals": 0,
                "approved_proposals": 0,
                "rejected_proposals": 0,
                "executed_proposals": 0,
                "total_votes_cast": 0,
            }
        
        return {
            "total_proposals": result["total"],
            "active_proposals": result["active"],
            "approved_proposals": result["approved"],
            "rejected_proposals": result["rejected"],
            "executed_proposals": result["executed"],
            "total_votes_cast": result["total_votes"],
        }
    
    # =========================================================================
    # MAPPING HELPERS
    # =========================================================================
    
    def _map_to_proposal(self, data: dict) -> Proposal:
        """Map Neo4j record to Proposal model."""
        # Handle Neo4j DateTime conversion
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        voting_starts_at = data.get("voting_starts_at")
        voting_ends_at = data.get("voting_ends_at")
        executed_at = data.get("executed_at")
        
        for dt_field in [created_at, updated_at, voting_starts_at, voting_ends_at, executed_at]:
            if dt_field and hasattr(dt_field, "to_native"):
                dt_field = dt_field.to_native()
        
        return Proposal(
            id=UUID(data["id"]),
            title=data["title"],
            description=data["description"],
            type=ProposalType(data["type"]),
            status=ProposalStatus(data["status"]),
            payload=data.get("payload", {}),
            proposer_id=UUID(data["proposer_id"]),
            voting_starts_at=voting_starts_at if hasattr(voting_starts_at, "isoformat") else None,
            voting_ends_at=voting_ends_at if hasattr(voting_ends_at, "isoformat") else None,
            quorum_percentage=data.get("quorum_percentage", 0.3),
            approval_threshold=data.get("approval_threshold", 0.5),
            votes_for=data.get("votes_for", 0),
            votes_against=data.get("votes_against", 0),
            votes_abstain=data.get("votes_abstain", 0),
            total_eligible_weight=data.get("total_eligible_weight", 0),
            ai_analysis=data.get("ai_analysis"),
            executed_at=executed_at if hasattr(executed_at, "isoformat") else None,
            execution_result=data.get("execution_result"),
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def _map_to_vote(self, data: dict) -> Vote:
        """Map Neo4j record to Vote model."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        
        return Vote(
            id=UUID(data["id"]),
            proposal_id=UUID(data["proposal_id"]),
            voter_id=UUID(data["voter_id"]),
            decision=VoteDecision(data["decision"]),
            weight=data["weight"],
            reasoning=data.get("reasoning"),
            created_at=created_at,
            updated_at=updated_at,
        )
```

---

## Database Schema Additions

Add these constraints and indexes for governance:

```python
# Add to forge/infrastructure/neo4j/schema.py SCHEMA_QUERIES list:

GOVERNANCE_SCHEMA_QUERIES = [
    # Proposal constraints
    "CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS FOR (p:Proposal) REQUIRE p.id IS UNIQUE",
    
    # Vote constraints
    "CREATE CONSTRAINT vote_id_unique IF NOT EXISTS FOR (v:Vote) REQUIRE v.id IS UNIQUE",
    
    # Prevent duplicate votes (one vote per user per proposal)
    "CREATE CONSTRAINT vote_unique_per_user IF NOT EXISTS FOR (v:Vote) REQUIRE (v.proposal_id, v.voter_id) IS UNIQUE",
    
    # Proposal indexes
    "CREATE INDEX proposal_status_index IF NOT EXISTS FOR (p:Proposal) ON (p.status)",
    "CREATE INDEX proposal_type_index IF NOT EXISTS FOR (p:Proposal) ON (p.type)",
    "CREATE INDEX proposal_proposer_index IF NOT EXISTS FOR (p:Proposal) ON (p.proposer_id)",
    "CREATE INDEX proposal_voting_ends_index IF NOT EXISTS FOR (p:Proposal) ON (p.voting_ends_at)",
    
    # Vote indexes
    "CREATE INDEX vote_proposal_index IF NOT EXISTS FOR (v:Vote) ON (v.proposal_id)",
    "CREATE INDEX vote_voter_index IF NOT EXISTS FOR (v:Vote) ON (v.voter_id)",
]
```
