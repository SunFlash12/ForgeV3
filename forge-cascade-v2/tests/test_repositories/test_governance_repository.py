"""
Governance Repository Tests for Forge Cascade V2

Comprehensive tests for GovernanceRepository including:
- Proposal CRUD operations
- Voting lifecycle
- Constitutional AI review
- Ghost Council opinions
- Vote delegation
- Trust-weighted voting
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from forge.models.base import ProposalStatus
from forge.models.governance import (
    ConstitutionalAnalysis,
    GhostCouncilOpinion,
    GovernanceStats,
    Proposal,
    ProposalCreate,
    ProposalType,
    Vote,
    VoteChoice,
    VoteCreate,
    VoteDelegation,
)
from forge.repositories.governance_repository import (
    GovernanceRepository,
    ProposalUpdate,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def governance_repository(mock_db_client):
    """Create governance repository with mock client."""
    return GovernanceRepository(mock_db_client)


@pytest.fixture
def sample_proposal_data():
    """Sample proposal data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "prop123",
        "title": "Test Proposal",
        "description": "A test proposal description",
        "type": "policy",
        "action": "{}",
        "proposer_id": "user123",
        "status": "draft",
        "voting_period_days": 7,
        "quorum_percent": 0.1,
        "pass_threshold": 0.5,
        "votes_for": 0,
        "votes_against": 0,
        "votes_abstain": 0,
        "weight_for": 0.0,
        "weight_against": 0.0,
        "weight_abstain": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@pytest.fixture
def sample_vote_data():
    """Sample vote data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "vote123",
        "proposal_id": "prop123",
        "voter_id": "user456",
        "choice": "for",
        "weight": 0.75,
        "reason": "I support this proposal",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


# =============================================================================
# Proposal Creation Tests
# =============================================================================


class TestGovernanceRepositoryProposalCreate:
    """Tests for proposal creation."""

    @pytest.mark.asyncio
    async def test_create_proposal_success(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Successful proposal creation."""
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        proposal_create = ProposalCreate(
            title="Test Proposal",
            description="A test proposal description",
            type=ProposalType.POLICY,
            voting_period_days=7,
        )

        result = await governance_repository.create(
            data=proposal_create,
            proposer_id="user123",
        )

        assert result.title == "Test Proposal"
        assert result.proposer_id == "user123"
        assert result.status == ProposalStatus.DRAFT
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_with_action(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Proposal creation with action dict."""
        sample_proposal_data["action"] = '{"key": "value"}'
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        proposal_create = ProposalCreate(
            title="Action Proposal",
            description="Proposal with action",
            type=ProposalType.POLICY,
            action={"key": "value"},
        )

        await governance_repository.create(
            data=proposal_create,
            proposer_id="user123",
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["action"] == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_create_proposal_failure_raises_error(
        self, governance_repository, mock_db_client
    ):
        """Proposal creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        proposal_create = ProposalCreate(
            title="Test Proposal",
            description="Description",
            type=ProposalType.POLICY,
        )

        with pytest.raises(RuntimeError, match="Failed to create proposal"):
            await governance_repository.create(
                data=proposal_create,
                proposer_id="user123",
            )


# =============================================================================
# Proposal Update Tests
# =============================================================================


class TestGovernanceRepositoryProposalUpdate:
    """Tests for proposal update operations."""

    @pytest.mark.asyncio
    async def test_update_proposal_title(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Update proposal title (only in draft status)."""
        sample_proposal_data["title"] = "Updated Title"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        update = ProposalUpdate(title="Updated Title")
        result = await governance_repository.update("prop123", update)

        assert result is not None
        assert result.title == "Updated Title"
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "status = 'draft'" in query

    @pytest.mark.asyncio
    async def test_update_proposal_description(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Update proposal description."""
        sample_proposal_data["description"] = "New description"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        update = ProposalUpdate(description="New description")
        result = await governance_repository.update("prop123", update)

        assert result.description == "New description"

    @pytest.mark.asyncio
    async def test_update_proposal_action(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Update proposal action."""
        sample_proposal_data["action"] = '{"new": "action"}'
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        update = ProposalUpdate(action={"new": "action"})
        await governance_repository.update("prop123", update)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["action"] == '{"new": "action"}'

    @pytest.mark.asyncio
    async def test_update_proposal_not_draft_returns_none(
        self, governance_repository, mock_db_client
    ):
        """Update returns None for non-draft proposal."""
        mock_db_client.execute_single.return_value = None

        update = ProposalUpdate(title="New Title")
        result = await governance_repository.update("prop123", update)

        assert result is None


# =============================================================================
# Voting Lifecycle Tests
# =============================================================================


class TestGovernanceRepositoryVotingLifecycle:
    """Tests for voting lifecycle operations."""

    @pytest.mark.asyncio
    async def test_start_voting_success(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Successfully start voting period."""
        # First call returns proposal, second updates it
        sample_proposal_data["status"] = "voting"
        mock_db_client.execute_single.side_effect = [
            {"entity": sample_proposal_data},  # get_by_id
            {"entity": sample_proposal_data},  # start_voting update
        ]

        result = await governance_repository.start_voting("prop123")

        assert result is not None
        assert result.status == ProposalStatus.VOTING

    @pytest.mark.asyncio
    async def test_start_voting_proposal_not_found(
        self, governance_repository, mock_db_client
    ):
        """Start voting returns None for nonexistent proposal."""
        mock_db_client.execute_single.return_value = None

        result = await governance_repository.start_voting("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_close_voting_passed(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Close voting with proposal passing."""
        sample_proposal_data["status"] = "voting"
        sample_proposal_data["votes_for"] = 10
        sample_proposal_data["votes_against"] = 2
        sample_proposal_data["votes_abstain"] = 1
        sample_proposal_data["quorum_percent"] = 0.1
        sample_proposal_data["pass_threshold"] = 0.5

        passed_proposal = {**sample_proposal_data, "status": "passed"}

        mock_db_client.execute_single.side_effect = [
            {"entity": sample_proposal_data},  # get_by_id
            {"eligible_count": 100},  # _count_eligible_voters
            {"entity": passed_proposal},  # close_voting update
        ]

        result = await governance_repository.close_voting("prop123")

        assert result is not None
        assert result.status == ProposalStatus.PASSED

    @pytest.mark.asyncio
    async def test_close_voting_rejected(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Close voting with proposal rejected."""
        sample_proposal_data["status"] = "voting"
        sample_proposal_data["votes_for"] = 2
        sample_proposal_data["votes_against"] = 10
        sample_proposal_data["votes_abstain"] = 1
        sample_proposal_data["quorum_percent"] = 0.1
        sample_proposal_data["pass_threshold"] = 0.5

        rejected_proposal = {**sample_proposal_data, "status": "rejected"}

        mock_db_client.execute_single.side_effect = [
            {"entity": sample_proposal_data},  # get_by_id
            {"eligible_count": 100},  # _count_eligible_voters
            {"entity": rejected_proposal},  # close_voting update
        ]

        result = await governance_repository.close_voting("prop123")

        assert result is not None
        assert result.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_close_voting_quorum_not_met(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Close voting fails quorum check."""
        sample_proposal_data["status"] = "voting"
        sample_proposal_data["votes_for"] = 5
        sample_proposal_data["votes_against"] = 2
        sample_proposal_data["votes_abstain"] = 0
        sample_proposal_data["quorum_percent"] = 0.5  # 50% quorum

        rejected_proposal = {**sample_proposal_data, "status": "rejected"}

        mock_db_client.execute_single.side_effect = [
            {"entity": sample_proposal_data},
            {"eligible_count": 100},  # Only 7% voted
            {"entity": rejected_proposal},
        ]

        result = await governance_repository.close_voting("prop123")

        assert result is not None
        assert result.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_close_voting_no_eligible_voters(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Close voting with no eligible voters."""
        sample_proposal_data["status"] = "voting"
        sample_proposal_data["votes_for"] = 5
        sample_proposal_data["votes_against"] = 0

        rejected_proposal = {**sample_proposal_data, "status": "rejected"}

        mock_db_client.execute_single.side_effect = [
            {"entity": sample_proposal_data},
            {"eligible_count": 0},  # No eligible voters
            {"entity": rejected_proposal},
        ]

        result = await governance_repository.close_voting("prop123")

        assert result is not None
        assert result.status == ProposalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_close_voting_not_in_voting_status(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Close voting returns None for non-voting proposal."""
        sample_proposal_data["status"] = "draft"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        result = await governance_repository.close_voting("prop123")

        assert result is None

    @pytest.mark.asyncio
    async def test_mark_executed_success(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Successfully mark proposal as executed."""
        sample_proposal_data["status"] = "executed"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        result = await governance_repository.mark_executed("prop123")

        assert result is not None
        assert result.status == ProposalStatus.EXECUTED

    @pytest.mark.asyncio
    async def test_mark_executed_blocked_by_timelock(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Execution blocked by timelock."""
        # First call returns None (timelock not expired)
        # Second call checks status
        mock_db_client.execute_single.side_effect = [
            None,  # Execution blocked
            {"status": "passed", "timelock": datetime.now(UTC).isoformat()},
        ]

        result = await governance_repository.mark_executed("prop123")

        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_proposal_success(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Successfully cancel proposal."""
        sample_proposal_data["status"] = "cancelled"
        sample_proposal_data["cancellation_reason"] = "Changed plans"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        result = await governance_repository.cancel("prop123", "Changed plans")

        assert result is not None
        assert result.status == ProposalStatus.CANCELLED


# =============================================================================
# Voting Tests
# =============================================================================


class TestGovernanceRepositoryVoting:
    """Tests for voting operations."""

    @pytest.mark.asyncio
    async def test_cast_vote_success(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Successfully cast vote."""
        mock_db_client.execute_single.side_effect = [
            None,  # get_vote returns None (no existing vote)
            {"trust_flame": 75},  # verify voter trust
            {"vote": sample_vote_data},  # cast_vote result
        ]

        vote_data = VoteCreate(
            choice=VoteChoice.FOR,
            reason="I support this",
        )

        result = await governance_repository.cast_vote(
            proposal_id="prop123",
            voter_id="user456",
            vote_data=vote_data,
            trust_weight=0.75,
        )

        assert result is not None
        assert result.choice == VoteChoice.FOR

    @pytest.mark.asyncio
    async def test_cast_vote_already_voted(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Cast vote returns None if already voted."""
        mock_db_client.execute_single.return_value = {"vote": sample_vote_data}

        vote_data = VoteCreate(choice=VoteChoice.FOR)

        result = await governance_repository.cast_vote(
            proposal_id="prop123",
            voter_id="user456",
            vote_data=vote_data,
            trust_weight=0.75,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_cast_vote_verifies_trust_weight(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Cast vote verifies actual trust level from database."""
        mock_db_client.execute_single.side_effect = [
            None,  # No existing vote
            {"trust_flame": 50},  # Actual trust is 50, not 90
            {"vote": sample_vote_data},
        ]

        vote_data = VoteCreate(choice=VoteChoice.FOR)

        await governance_repository.cast_vote(
            proposal_id="prop123",
            voter_id="user456",
            vote_data=vote_data,
            trust_weight=0.90,  # Claimed weight
        )

        # Verify the weight used is the verified one (0.50), not claimed (0.90)
        call_args = mock_db_client.execute_single.call_args_list[-1]
        params = call_args[0][1]
        assert params["weight"] == 0.50

    @pytest.mark.asyncio
    async def test_cast_vote_voter_not_found(
        self, governance_repository, mock_db_client
    ):
        """Cast vote returns None if voter not found."""
        mock_db_client.execute_single.side_effect = [
            None,  # No existing vote
            None,  # Voter not found
        ]

        vote_data = VoteCreate(choice=VoteChoice.FOR)

        result = await governance_repository.cast_vote(
            proposal_id="prop123",
            voter_id="nonexistent",
            vote_data=vote_data,
            trust_weight=0.75,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_vote(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Get user's vote on proposal."""
        mock_db_client.execute_single.return_value = {"vote": sample_vote_data}

        result = await governance_repository.get_vote("prop123", "user456")

        assert result is not None
        assert result.voter_id == "user456"

    @pytest.mark.asyncio
    async def test_get_votes_for_proposal(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Get all votes for a proposal."""
        mock_db_client.execute.return_value = [{"vote": sample_vote_data}]

        result = await governance_repository.get_votes("prop123")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_votes_limit_capped(
        self, governance_repository, mock_db_client
    ):
        """Get votes respects limit cap."""
        mock_db_client.execute.return_value = []

        await governance_repository.get_votes("prop123", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 500  # Capped at 500

    @pytest.mark.asyncio
    async def test_get_voter_history(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Get user's voting history."""
        mock_db_client.execute.return_value = [{"vote": sample_vote_data}]

        result = await governance_repository.get_voter_history("user456")

        assert len(result) == 1
        assert result[0].voter_id == "user456"


# =============================================================================
# Vote Delegation Tests
# =============================================================================


class TestGovernanceRepositoryDelegation:
    """Tests for vote delegation operations."""

    @pytest.mark.asyncio
    async def test_create_delegation_success(
        self, governance_repository, mock_db_client
    ):
        """Successfully create vote delegation."""
        delegation_data = {
            "delegator_id": "user123",
            "delegate_id": "user456",
            "proposal_types": ["policy"],
            "expires_at": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute_single.return_value = {"delegation": delegation_data}

        delegation = VoteDelegation(
            delegator_id="user123",
            delegate_id="user456",
            proposal_types=[ProposalType.POLICY],
        )

        result = await governance_repository.create_delegation(delegation)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_delegation_success(
        self, governance_repository, mock_db_client
    ):
        """Successfully revoke delegation."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        result = await governance_repository.revoke_delegation("user123", "user456")

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_delegation_not_found(
        self, governance_repository, mock_db_client
    ):
        """Revoke delegation returns False when not found."""
        mock_db_client.execute_single.return_value = {"deleted": 0}

        result = await governance_repository.revoke_delegation("user123", "nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_delegates(
        self, governance_repository, mock_db_client
    ):
        """Get all delegations from a user."""
        delegation_data = {
            "delegator_id": "user123",
            "delegate_id": "user456",
            "proposal_types": None,
            "expires_at": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute.return_value = [{"delegation": delegation_data}]

        result = await governance_repository.get_delegates("user123")

        assert len(result) == 1
        assert result[0].delegate_id == "user456"


# =============================================================================
# Constitutional AI & Ghost Council Tests
# =============================================================================


class TestGovernanceRepositoryConstitutional:
    """Tests for Constitutional AI and Ghost Council operations."""

    @pytest.mark.asyncio
    async def test_save_constitutional_review(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Save Constitutional AI review."""
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        analysis = ConstitutionalAnalysis(
            recommendation="approve",
            overall_score=0.85,
            principle_scores={"fairness": 0.9, "safety": 0.8},
            concerns=[],
            rationale="This proposal aligns with principles.",
        )

        result = await governance_repository.save_constitutional_review(
            "prop123", analysis
        )

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert "review_json" in params

    @pytest.mark.asyncio
    async def test_save_ghost_council_opinion(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Save Ghost Council opinion."""
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        opinion = GhostCouncilOpinion(
            consensus_vote=VoteChoice.FOR,
            consensus_strength=0.75,
            individual_opinions=[],
            synthesis="The council supports this proposal.",
            key_concerns=[],
        )

        result = await governance_repository.save_ghost_council_opinion(
            "prop123", opinion
        )

        assert result is True


# =============================================================================
# Query Tests
# =============================================================================


class TestGovernanceRepositoryQueries:
    """Tests for query operations."""

    @pytest.mark.asyncio
    async def test_get_by_status(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Get proposals by status."""
        mock_db_client.execute.return_value = [{"entity": sample_proposal_data}]

        result = await governance_repository.get_by_status(ProposalStatus.DRAFT)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_active_proposals(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Get active proposals (voting status)."""
        sample_proposal_data["status"] = "voting"
        mock_db_client.execute.return_value = [{"entity": sample_proposal_data}]

        result = await governance_repository.get_active_proposals()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_by_proposer(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Get proposals by proposer."""
        mock_db_client.execute.return_value = [{"entity": sample_proposal_data}]

        result = await governance_repository.get_by_proposer("user123")

        assert len(result) == 1
        assert result[0].proposer_id == "user123"

    @pytest.mark.asyncio
    async def test_get_by_proposer_limit_capped(
        self, governance_repository, mock_db_client
    ):
        """Get by proposer respects limit cap."""
        mock_db_client.execute.return_value = []

        await governance_repository.get_by_proposer("user123", limit=500)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100  # Capped at 100

    @pytest.mark.asyncio
    async def test_get_expiring_soon(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Get proposals expiring soon."""
        sample_proposal_data["status"] = "voting"
        mock_db_client.execute.return_value = [{"entity": sample_proposal_data}]

        result = await governance_repository.get_expiring_soon(hours=24)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_proposals_with_filters(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """List proposals with filters and pagination."""
        mock_db_client.execute_single.return_value = {"total": 1}
        mock_db_client.execute.return_value = [{"entity": sample_proposal_data}]

        proposals, total = await governance_repository.list_proposals(
            offset=0,
            limit=10,
            filters={"status": "draft", "proposal_type": "policy"},
        )

        assert len(proposals) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_proposals_limit_capped(
        self, governance_repository, mock_db_client
    ):
        """List proposals respects limit cap."""
        mock_db_client.execute_single.return_value = {"total": 0}
        mock_db_client.execute.return_value = []

        await governance_repository.list_proposals(offset=0, limit=500)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100  # Capped at 100


# =============================================================================
# Statistics Tests
# =============================================================================


class TestGovernanceRepositoryStats:
    """Tests for statistics operations."""

    @pytest.mark.asyncio
    async def test_get_stats(self, governance_repository, mock_db_client):
        """Get governance statistics."""
        mock_db_client.execute_single.return_value = {
            "stats": {
                "total_proposals": 100,
                "active_proposals": 5,
                "passed_proposals": 50,
                "rejected_proposals": 30,
                "total_votes": 500,
                "unique_voters": 75,
            }
        }

        result = await governance_repository.get_stats()

        assert isinstance(result, GovernanceStats)
        assert result.total_proposals == 100
        assert result.active_proposals == 5

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, governance_repository, mock_db_client):
        """Get stats returns default when no data."""
        mock_db_client.execute_single.return_value = None

        result = await governance_repository.get_stats()

        assert isinstance(result, GovernanceStats)
        assert result.total_proposals == 0


# =============================================================================
# API Route Method Tests
# =============================================================================


class TestGovernanceRepositoryAPIMethods:
    """Tests for API route methods."""

    @pytest.mark.asyncio
    async def test_get_proposal_alias(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """get_proposal is alias for get_by_id."""
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        result = await governance_repository.get_proposal("prop123")

        assert result is not None
        assert result.id == "prop123"

    @pytest.mark.asyncio
    async def test_update_proposal_status(
        self, governance_repository, mock_db_client, sample_proposal_data
    ):
        """Update proposal status directly."""
        sample_proposal_data["status"] = "voting"
        mock_db_client.execute_single.return_value = {"entity": sample_proposal_data}

        result = await governance_repository.update_proposal_status(
            "prop123", ProposalStatus.VOTING
        )

        assert result is not None
        assert result.status == ProposalStatus.VOTING

    @pytest.mark.asyncio
    async def test_record_vote_atomic(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Record vote atomically prevents double voting."""
        mock_db_client.execute_single.return_value = {
            "vote": sample_vote_data,
            "is_new": True,
        }

        vote = Vote(
            id="vote123",
            proposal_id="prop123",
            voter_id="user456",
            choice=VoteChoice.FOR,
            weight=0.75,
        )

        result = await governance_repository.record_vote(vote)

        assert result is not None
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "MERGE" in query  # Uses MERGE for atomic operation

    @pytest.mark.asyncio
    async def test_record_vote_duplicate_blocked(
        self, governance_repository, mock_db_client, sample_vote_data
    ):
        """Record vote handles duplicate attempts."""
        mock_db_client.execute_single.return_value = {
            "vote": sample_vote_data,
            "is_new": False,  # Indicates duplicate
        }

        vote = Vote(
            id="vote123",
            proposal_id="prop123",
            voter_id="user456",
            choice=VoteChoice.FOR,
            weight=0.75,
        )

        result = await governance_repository.record_vote(vote)

        # Still returns the vote object but logs warning
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_active_policies(self, governance_repository, mock_db_client):
        """Get active policies returns default policies."""
        result = await governance_repository.get_active_policies()

        assert isinstance(result, list)
        assert len(result) > 0
        assert all("id" in p and "name" in p for p in result)

    @pytest.mark.asyncio
    async def test_get_policy(self, governance_repository, mock_db_client):
        """Get specific policy by ID."""
        result = await governance_repository.get_policy("policy_quorum")

        assert result is not None
        assert result["id"] == "policy_quorum"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, governance_repository, mock_db_client):
        """Get policy returns None for unknown ID."""
        result = await governance_repository.get_policy("unknown_policy")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_delegation_from_dict(
        self, governance_repository, mock_db_client
    ):
        """Create delegation from dict."""
        delegation_data = {
            "id": "del123",
            "delegator_id": "user123",
            "delegate_id": "user456",
            "proposal_types": ["policy"],
            "is_active": True,
        }
        mock_db_client.execute_single.return_value = {"delegation": delegation_data}

        result = await governance_repository.create_delegation_from_dict(delegation_data)

        assert result["id"] == "del123"


# =============================================================================
# Additional Delegation Method Tests
# =============================================================================


class TestGovernanceRepositoryAdditionalDelegation:
    """Tests for additional delegation methods."""

    @pytest.mark.asyncio
    async def test_get_delegation(self, governance_repository, mock_db_client):
        """Get delegation by ID."""
        delegation_data = {
            "id": "del123",
            "delegator_id": "user123",
            "delegate_id": "user456",
            "proposal_types": None,
            "expires_at": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute_single.return_value = {"delegation": delegation_data}

        result = await governance_repository.get_delegation("del123")

        assert result is not None
        assert result.delegator_id == "user123"

    @pytest.mark.asyncio
    async def test_get_user_delegations(self, governance_repository, mock_db_client):
        """Get all delegations for a user."""
        delegation_data = {
            "delegator_id": "user123",
            "delegate_id": "user456",
            "proposal_types": None,
            "expires_at": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute.return_value = [{"delegation": delegation_data}]

        result = await governance_repository.get_user_delegations("user123")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_revoke_delegation_by_id(self, governance_repository, mock_db_client):
        """Revoke delegation by ID."""
        mock_db_client.execute_single.return_value = {"updated": 1}

        result = await governance_repository.revoke_delegation_by_id("del123")

        assert result is True


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestGovernanceRepositoryHelpers:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    async def test_count_eligible_voters(
        self, governance_repository, mock_db_client
    ):
        """Count eligible voters with minimum trust level."""
        mock_db_client.execute_single.return_value = {"eligible_count": 50}

        result = await governance_repository._count_eligible_voters(min_trust_level=30)

        assert result == 50
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["min_trust"] == 30

    @pytest.mark.asyncio
    async def test_count_eligible_voters_none_result(
        self, governance_repository, mock_db_client
    ):
        """Count eligible voters returns 0 on None result."""
        mock_db_client.execute_single.return_value = None

        result = await governance_repository._count_eligible_voters()

        assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
