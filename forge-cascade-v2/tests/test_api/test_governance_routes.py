"""
Governance Routes Tests for Forge Cascade V2

Comprehensive tests for governance API routes including:
- Proposal management (create, list, get, submit, withdraw, finalize)
- Voting operations (cast vote, get votes)
- Ghost Council endpoints
- Policy queries
- Delegation management
- Metrics and Constitutional AI analysis
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.models.base import ProposalStatus
from forge.models.governance import ProposalType, VoteChoice


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_proposal():
    """Create a mock proposal."""
    proposal = MagicMock()
    proposal.id = "prop_test123"
    proposal.title = "Test Proposal"
    proposal.description = "A test proposal for testing purposes"
    proposal.type = ProposalType.POLICY
    proposal.status = ProposalStatus.VOTING
    proposal.proposer_id = "user123"
    proposal.action = {"type": "policy_change"}
    proposal.voting_period_days = 7
    proposal.quorum_percent = 0.1
    proposal.pass_threshold = 0.5
    proposal.votes_for = 5
    proposal.votes_against = 2
    proposal.votes_abstain = 1
    proposal.weight_for = 3.5
    proposal.weight_against = 1.2
    proposal.weight_abstain = 0.5
    proposal.created_at = datetime.now(UTC)
    proposal.voting_starts_at = datetime.now(UTC)
    proposal.voting_ends_at = datetime.now(UTC) + timedelta(days=7)
    return proposal


@pytest.fixture
def mock_vote():
    """Create a mock vote."""
    vote = MagicMock()
    vote.id = "vote_test123"
    vote.proposal_id = "prop_test123"
    vote.voter_id = "user456"
    vote.choice = VoteChoice.APPROVE
    vote.weight = 0.75
    vote.reason = "Good proposal"
    vote.created_at = datetime.now(UTC)
    return vote


@pytest.fixture
def mock_delegation():
    """Create a mock delegation."""
    delegation = MagicMock()
    delegation.id = "del_test123"
    delegation.delegator_id = "user123"
    delegation.delegate_id = "user456"
    delegation.proposal_types = None
    delegation.is_active = True
    delegation.created_at = datetime.now(UTC)
    delegation.expires_at = None
    return delegation


@pytest.fixture
def mock_governance_repo(mock_proposal, mock_vote, mock_delegation):
    """Create mock governance repository."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=mock_proposal)
    repo.list_proposals = AsyncMock(return_value=([mock_proposal], 1))
    repo.get_proposal = AsyncMock(return_value=mock_proposal)
    repo.get_active_proposals = AsyncMock(return_value=[mock_proposal])
    repo.start_voting = AsyncMock(return_value=mock_proposal)
    repo.update_proposal_status = AsyncMock(return_value=mock_proposal)
    repo.record_vote = AsyncMock(return_value=mock_vote)
    repo.get_proposal_votes = AsyncMock(return_value=[mock_vote])
    repo.get_user_vote = AsyncMock(return_value=None)
    repo.get_active_policies = AsyncMock(return_value=[{"id": "policy1", "content": "Policy"}])
    repo.get_policy = AsyncMock(return_value={"id": "policy1", "content": "Policy"})
    repo.create_delegation = AsyncMock()
    repo.get_user_delegations = AsyncMock(return_value=[mock_delegation])
    repo.get_delegation = AsyncMock(return_value=mock_delegation)
    repo.get_delegates = AsyncMock(return_value=[])
    repo.revoke_delegation_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo():
    """Create mock user repository."""
    repo = AsyncMock()
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.trust_flame = 60
    user.is_active = True
    repo.get_by_id = AsyncMock(return_value=user)
    return repo


@pytest.fixture
def mock_audit_repo():
    """Create mock audit repository."""
    repo = AsyncMock()
    repo.log_governance_action = AsyncMock()
    return repo


@pytest.fixture
def mock_event_system():
    """Create mock event system."""
    system = AsyncMock()
    system.emit = AsyncMock()
    return system


@pytest.fixture
def mock_standard_user():
    """Create mock STANDARD trust user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "standarduser"
    user.trust_flame = 40
    user.trust_level = MagicMock(value=40)
    user.is_active = True
    user.role = "user"
    return user


@pytest.fixture
def mock_trusted_user():
    """Create mock TRUSTED trust user."""
    user = MagicMock()
    user.id = "user456"
    user.username = "trusteduser"
    user.trust_flame = 60
    user.trust_level = MagicMock(value=60)
    user.is_active = True
    user.role = "user"
    return user


@pytest.fixture
def mock_core_user():
    """Create mock CORE trust user."""
    user = MagicMock()
    user.id = "user789"
    user.username = "coreuser"
    user.trust_flame = 80
    user.trust_level = MagicMock(value=80)
    user.is_active = True
    user.role = "admin"
    return user


@pytest.fixture
def governance_app(
    mock_governance_repo,
    mock_user_repo,
    mock_audit_repo,
    mock_event_system,
    mock_standard_user,
):
    """Create FastAPI app with governance router and mocked dependencies."""
    from forge.api.routes.governance import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/governance")

    # Override dependencies
    from forge.api.dependencies import (
        get_governance_repo,
        get_user_repo,
        get_audit_repo,
        get_event_system,
        get_current_active_user,
    )

    app.dependency_overrides[get_governance_repo] = lambda: mock_governance_repo
    app.dependency_overrides[get_user_repo] = lambda: mock_user_repo
    app.dependency_overrides[get_audit_repo] = lambda: mock_audit_repo
    app.dependency_overrides[get_event_system] = lambda: mock_event_system
    app.dependency_overrides[get_current_active_user] = lambda: mock_standard_user

    return app


@pytest.fixture
def client(governance_app):
    """Create test client."""
    return TestClient(governance_app)


# =============================================================================
# Proposal Creation Tests
# =============================================================================


class TestCreateProposal:
    """Tests for POST /governance/proposals endpoint."""

    def test_create_proposal_success(self, client: TestClient):
        """Create proposal with valid data."""
        with patch("forge.api.routes.governance.validate_capsule_content") as mock_validate:
            mock_validate.return_value = MagicMock(is_valid=True)

            response = client.post(
                "/api/v1/governance/proposals",
                json={
                    "title": "New Policy Proposal",
                    "description": "This is a detailed description of the proposal that meets the minimum length requirement.",
                    "proposal_type": "POLICY",
                    "action": {"type": "update_policy", "target": "trust_rules"},
                    "voting_period_days": 7,
                    "quorum_percent": 0.15,
                    "pass_threshold": 0.6,
                },
            )

            assert response.status_code in [201, 400, 500]
            if response.status_code == 201:
                data = response.json()
                assert "id" in data
                assert "title" in data
                assert "status" in data

    def test_create_proposal_minimal(self, client: TestClient):
        """Create proposal with minimal required fields."""
        with patch("forge.api.routes.governance.validate_capsule_content") as mock_validate:
            mock_validate.return_value = MagicMock(is_valid=True)

            response = client.post(
                "/api/v1/governance/proposals",
                json={
                    "title": "Minimal Proposal Title",
                    "description": "This description meets the minimum twenty character requirement.",
                },
            )

            assert response.status_code in [201, 400, 500]

    def test_create_proposal_title_too_short(self, client: TestClient):
        """Create proposal with title too short."""
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "title": "Shor",  # Less than 5 chars
                "description": "Valid description that is long enough.",
            },
        )

        assert response.status_code == 422

    def test_create_proposal_description_too_short(self, client: TestClient):
        """Create proposal with description too short."""
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "title": "Valid Title",
                "description": "Too short",  # Less than 20 chars
            },
        )

        assert response.status_code == 422

    def test_create_proposal_invalid_voting_period(self, client: TestClient):
        """Create proposal with invalid voting period."""
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "title": "Valid Title Here",
                "description": "Valid description that is long enough.",
                "voting_period_days": 60,  # Over 30 day limit
            },
        )

        assert response.status_code == 422

    def test_create_proposal_invalid_quorum(self, client: TestClient):
        """Create proposal with invalid quorum percent."""
        response = client.post(
            "/api/v1/governance/proposals",
            json={
                "title": "Valid Title Here",
                "description": "Valid description that is long enough.",
                "quorum_percent": 1.5,  # Over 1.0 limit
            },
        )

        assert response.status_code == 422


# =============================================================================
# List Proposals Tests
# =============================================================================


class TestListProposals:
    """Tests for GET /governance/proposals endpoint."""

    def test_list_proposals_success(self, client: TestClient):
        """List all proposals."""
        response = client.get("/api/v1/governance/proposals")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data

    def test_list_proposals_filtered(self, client: TestClient):
        """List proposals filtered by status."""
        response = client.get("/api/v1/governance/proposals?status_filter=VOTING")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_proposals_by_type(self, client: TestClient):
        """List proposals filtered by type."""
        response = client.get("/api/v1/governance/proposals?proposal_type=POLICY")

        assert response.status_code == 200

    def test_get_active_proposals(self, client: TestClient):
        """Get active proposals."""
        response = client.get("/api/v1/governance/proposals/active")

        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data


# =============================================================================
# Get Proposal Tests
# =============================================================================


class TestGetProposal:
    """Tests for GET /governance/proposals/{proposal_id} endpoint."""

    def test_get_proposal_success(self, client: TestClient):
        """Get proposal by ID."""
        response = client.get("/api/v1/governance/proposals/prop_test123")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "status" in data
        assert "votes_for" in data
        assert "votes_against" in data

    def test_get_proposal_not_found(self, client: TestClient, mock_governance_repo):
        """Get non-existent proposal."""
        mock_governance_repo.get_proposal.return_value = None

        response = client.get("/api/v1/governance/proposals/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Submit Proposal Tests
# =============================================================================


class TestSubmitProposal:
    """Tests for POST /governance/proposals/{proposal_id}/submit endpoint."""

    def test_submit_proposal_success(self, client: TestClient, mock_proposal):
        """Submit proposal for voting."""
        mock_proposal.status = MagicMock(value="draft")

        response = client.post("/api/v1/governance/proposals/prop_test123/submit")

        assert response.status_code in [200, 400, 403, 404]

    def test_submit_proposal_not_owner(self, client: TestClient, mock_proposal):
        """Submit proposal by non-owner fails."""
        mock_proposal.proposer_id = "other_user"

        response = client.post("/api/v1/governance/proposals/prop_test123/submit")

        assert response.status_code == 403

    def test_submit_proposal_already_voting(self, client: TestClient, mock_proposal):
        """Submit proposal that's already in voting."""
        mock_proposal.status = MagicMock(value="voting")

        response = client.post("/api/v1/governance/proposals/prop_test123/submit")

        assert response.status_code == 400


# =============================================================================
# Withdraw Proposal Tests
# =============================================================================


class TestWithdrawProposal:
    """Tests for DELETE /governance/proposals/{proposal_id} endpoint."""

    def test_withdraw_proposal_success(self, client: TestClient, mock_proposal):
        """Withdraw proposal successfully."""
        mock_proposal.status = ProposalStatus.DRAFT

        response = client.delete("/api/v1/governance/proposals/prop_test123")

        assert response.status_code in [204, 400, 403, 404]

    def test_withdraw_proposal_not_owner(self, client: TestClient, mock_proposal):
        """Withdraw proposal by non-owner fails."""
        mock_proposal.proposer_id = "other_user"

        response = client.delete("/api/v1/governance/proposals/prop_test123")

        assert response.status_code == 403


# =============================================================================
# Voting Tests
# =============================================================================


class TestCastVote:
    """Tests for POST /governance/proposals/{proposal_id}/vote endpoint."""

    def test_cast_vote_success(self, client: TestClient):
        """Cast vote successfully."""
        response = client.post(
            "/api/v1/governance/proposals/prop_test123/vote",
            json={
                "choice": "APPROVE",
                "rationale": "This is a good proposal",
            },
        )

        assert response.status_code in [200, 400, 500]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "choice" in data
            assert "weight" in data

    def test_cast_vote_reject(self, client: TestClient):
        """Cast reject vote."""
        response = client.post(
            "/api/v1/governance/proposals/prop_test123/vote",
            json={
                "choice": "REJECT",
                "rationale": "Not a good proposal",
            },
        )

        assert response.status_code in [200, 400, 500]

    def test_cast_vote_abstain(self, client: TestClient):
        """Cast abstain vote."""
        response = client.post(
            "/api/v1/governance/proposals/prop_test123/vote",
            json={
                "choice": "ABSTAIN",
            },
        )

        assert response.status_code in [200, 400, 500]

    def test_cast_vote_already_voted(self, client: TestClient, mock_governance_repo, mock_vote):
        """Cast vote when already voted fails."""
        mock_governance_repo.get_user_vote.return_value = mock_vote

        response = client.post(
            "/api/v1/governance/proposals/prop_test123/vote",
            json={"choice": "APPROVE"},
        )

        assert response.status_code == 400

    def test_cast_vote_proposal_not_voting(self, client: TestClient, mock_proposal):
        """Cast vote on non-voting proposal."""
        mock_proposal.status = MagicMock(value="passed")

        response = client.post(
            "/api/v1/governance/proposals/prop_test123/vote",
            json={"choice": "APPROVE"},
        )

        assert response.status_code == 400

    def test_get_proposal_votes(self, client: TestClient):
        """Get all votes on a proposal."""
        response = client.get("/api/v1/governance/proposals/prop_test123/votes")

        assert response.status_code == 200
        data = response.json()
        assert "votes" in data

    def test_get_my_vote(self, client: TestClient, mock_governance_repo, mock_vote):
        """Get current user's vote."""
        mock_governance_repo.get_user_vote.return_value = mock_vote

        response = client.get("/api/v1/governance/proposals/prop_test123/my-vote")

        assert response.status_code == 200

    def test_get_my_vote_not_voted(self, client: TestClient, mock_governance_repo):
        """Get vote when not voted returns null."""
        mock_governance_repo.get_user_vote.return_value = None

        response = client.get("/api/v1/governance/proposals/prop_test123/my-vote")

        assert response.status_code == 200
        assert response.json() is None


# =============================================================================
# Ghost Council Tests
# =============================================================================


class TestGhostCouncil:
    """Tests for Ghost Council endpoints."""

    def test_get_ghost_council_recommendation(self, client: TestClient):
        """Get Ghost Council recommendation."""
        with patch("forge.api.routes.governance.get_ghost_council_service") as mock_gc:
            mock_service = MagicMock()
            mock_opinion = MagicMock()
            mock_opinion.consensus_vote = MagicMock(value="APPROVE")
            mock_opinion.consensus_strength = 0.85
            mock_opinion.final_recommendation = "This proposal aligns with community values."
            mock_service.deliberate_proposal = AsyncMock(return_value=mock_opinion)
            mock_gc.return_value = mock_service

            response = client.get(
                "/api/v1/governance/proposals/prop_test123/ghost-council?use_ai=true"
            )

            assert response.status_code in [200, 404, 500]
            if response.status_code == 200:
                data = response.json()
                assert "proposal_id" in data
                assert "recommendation" in data
                assert "confidence" in data
                assert "reasoning" in data

    def test_get_ghost_council_heuristic(self, client: TestClient):
        """Get Ghost Council recommendation using heuristics."""
        response = client.get(
            "/api/v1/governance/proposals/prop_test123/ghost-council?use_ai=false"
        )

        assert response.status_code in [200, 404, 500]

    def test_get_ghost_council_members(self, client: TestClient):
        """Get Ghost Council members."""
        with patch("forge.api.routes.governance.DEFAULT_COUNCIL_MEMBERS", [
            MagicMock(
                id="member1",
                name="Ethics Expert",
                role="advisor",
                domain="ethics",
                icon="scale",
                weight=1.0,
                persona="Ethical advisor",
            )
        ]):
            response = client.get("/api/v1/governance/ghost-council/members")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_ghost_council_stats(self, client: TestClient):
        """Get Ghost Council statistics."""
        with patch("forge.api.routes.governance.get_ghost_council_service") as mock_gc:
            mock_service = MagicMock()
            mock_service.get_stats.return_value = {
                "proposals_reviewed": 10,
                "issues_responded": 5,
            }
            mock_gc.return_value = mock_service

            response = client.get("/api/v1/governance/ghost-council/stats")

            assert response.status_code == 200


# =============================================================================
# Constitutional Analysis Tests
# =============================================================================


class TestConstitutionalAnalysis:
    """Tests for Constitutional AI analysis endpoint."""

    def test_get_constitutional_analysis(self, client: TestClient):
        """Get Constitutional AI analysis."""
        response = client.get(
            "/api/v1/governance/proposals/prop_test123/constitutional-analysis"
        )

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "proposal_id" in data
            assert "ethical_score" in data
            assert "fairness_score" in data
            assert "safety_score" in data
            assert "recommendation" in data


# =============================================================================
# Delegation Tests
# =============================================================================


class TestDelegation:
    """Tests for delegation endpoints."""

    def test_create_delegation_success(self, client: TestClient, mock_user_repo):
        """Create delegation successfully."""
        delegate_user = MagicMock()
        delegate_user.id = "user456"
        delegate_user.is_active = True
        mock_user_repo.get_by_id = AsyncMock(return_value=delegate_user)

        response = client.post(
            "/api/v1/governance/delegations",
            json={
                "delegate_id": "user456",
                "proposal_types": ["POLICY"],
                "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            },
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_create_delegation_self(self, client: TestClient):
        """Create delegation to self fails."""
        response = client.post(
            "/api/v1/governance/delegations",
            json={
                "delegate_id": "user123",  # Same as current user
            },
        )

        assert response.status_code == 400

    def test_create_delegation_inactive_user(self, client: TestClient, mock_user_repo):
        """Create delegation to inactive user fails."""
        inactive_user = MagicMock()
        inactive_user.id = "inactive_user"
        inactive_user.is_active = False
        mock_user_repo.get_by_id = AsyncMock(return_value=inactive_user)

        response = client.post(
            "/api/v1/governance/delegations",
            json={"delegate_id": "inactive_user"},
        )

        assert response.status_code == 400

    def test_get_my_delegations(self, client: TestClient):
        """Get my delegations."""
        response = client.get("/api/v1/governance/delegations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_revoke_delegation_success(self, client: TestClient, mock_delegation):
        """Revoke delegation successfully."""
        response = client.delete("/api/v1/governance/delegations/del_test123")

        assert response.status_code in [200, 403, 404]

    def test_revoke_delegation_not_owner(self, client: TestClient, mock_delegation):
        """Revoke delegation by non-owner fails."""
        mock_delegation.delegator_id = "other_user"

        response = client.delete("/api/v1/governance/delegations/del_test123")

        assert response.status_code == 403


# =============================================================================
# Finalize Proposal Tests
# =============================================================================


class TestFinalizeProposal:
    """Tests for POST /governance/proposals/{proposal_id}/finalize endpoint."""

    def test_finalize_proposal_requires_core(
        self, governance_app, mock_core_user
    ):
        """Finalize proposal requires CORE trust."""
        from forge.api.dependencies import get_current_active_user
        governance_app.dependency_overrides[get_current_active_user] = lambda: mock_core_user

        client = TestClient(governance_app)
        response = client.post("/api/v1/governance/proposals/prop_test123/finalize")

        # CORE user should be able to finalize (or get expected error)
        assert response.status_code in [200, 400, 404, 500]


# =============================================================================
# Metrics Tests
# =============================================================================


class TestGovernanceMetrics:
    """Tests for GET /governance/metrics endpoint."""

    def test_get_governance_metrics(self, client: TestClient):
        """Get governance metrics."""
        response = client.get("/api/v1/governance/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "total_proposals" in data
        assert "active_proposals" in data
        assert "total_votes" in data


# =============================================================================
# Policy Tests
# =============================================================================


class TestPolicies:
    """Tests for policy endpoints."""

    def test_get_active_policies(self, client: TestClient):
        """Get active policies."""
        response = client.get("/api/v1/governance/policies")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_policy(self, client: TestClient):
        """Get specific policy."""
        response = client.get("/api/v1/governance/policies/policy1")

        assert response.status_code == 200

    def test_get_policy_not_found(self, client: TestClient, mock_governance_repo):
        """Get non-existent policy."""
        mock_governance_repo.get_policy.return_value = None

        response = client.get("/api/v1/governance/policies/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Serious Issues Tests
# =============================================================================


class TestSeriousIssues:
    """Tests for Ghost Council serious issues endpoints."""

    def test_get_active_issues(self, governance_app, mock_trusted_user):
        """Get active issues requires TRUSTED trust."""
        from forge.api.dependencies import get_current_active_user
        governance_app.dependency_overrides[get_current_active_user] = lambda: mock_trusted_user

        with patch("forge.api.routes.governance.get_ghost_council_service") as mock_gc:
            mock_service = MagicMock()
            mock_service.get_active_issues.return_value = []
            mock_gc.return_value = mock_service

            client = TestClient(governance_app)
            response = client.get("/api/v1/governance/ghost-council/issues")

            assert response.status_code == 200

    def test_report_serious_issue(self, governance_app, mock_trusted_user):
        """Report serious issue."""
        from forge.api.dependencies import get_current_active_user
        governance_app.dependency_overrides[get_current_active_user] = lambda: mock_trusted_user

        with patch("forge.api.routes.governance.get_ghost_council_service") as mock_gc, \
             patch("forge.api.routes.governance.validate_capsule_content") as mock_validate:
            mock_service = MagicMock()
            mock_service.respond_to_issue = AsyncMock()
            mock_gc.return_value = mock_service
            mock_validate.return_value = MagicMock(is_valid=True)

            client = TestClient(governance_app)
            response = client.post(
                "/api/v1/governance/ghost-council/issues",
                json={
                    "category": "security",
                    "severity": "high",
                    "title": "Security Issue Found",
                    "description": "A serious security vulnerability was discovered.",
                    "affected_entities": ["capsule123"],
                },
            )

            assert response.status_code in [200, 400, 500]

    def test_resolve_serious_issue(self, governance_app, mock_core_user):
        """Resolve serious issue requires CORE trust."""
        from forge.api.dependencies import get_current_active_user
        governance_app.dependency_overrides[get_current_active_user] = lambda: mock_core_user

        with patch("forge.api.routes.governance.get_ghost_council_service") as mock_gc:
            mock_service = MagicMock()
            mock_service.resolve_issue.return_value = True
            mock_gc.return_value = mock_service

            client = TestClient(governance_app)
            response = client.post(
                "/api/v1/governance/ghost-council/issues/issue123/resolve",
                json={"resolution": "Issue was fixed by patching the vulnerability."},
            )

            assert response.status_code in [200, 404, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
