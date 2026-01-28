"""
Governance Model Tests for Forge Cascade V2

Comprehensive tests for governance models including:
- Proposal creation and validation
- Vote choice enums and aliases
- VoteDelegation validation
- Constitutional AI models
- Ghost Council models
- Action validation for proposal types
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from forge.models.base import ProposalStatus
from forge.models.governance import (
    REQUIRED_ACTION_FIELDS,
    VALID_PROPOSAL_ACTIONS,
    ConstitutionalAnalysis,
    EthicalConcern,
    GhostCouncilMember,
    GhostCouncilOpinion,
    GhostCouncilVote,
    GovernanceStats,
    PerspectiveAnalysis,
    PerspectiveType,
    Proposal,
    ProposalBase,
    ProposalCreate,
    ProposalType,
    Vote,
    VoteChoice,
    VoteCreate,
    VoteDelegation,
)

# =============================================================================
# ProposalType Enum Tests
# =============================================================================


class TestProposalType:
    """Tests for ProposalType enum."""

    def test_proposal_type_values(self):
        """ProposalType has expected values."""
        assert ProposalType.POLICY.value == "policy"
        assert ProposalType.SYSTEM.value == "system"
        assert ProposalType.OVERLAY.value == "overlay"
        assert ProposalType.CAPSULE.value == "capsule"
        assert ProposalType.TRUST.value == "trust"
        assert ProposalType.CONSTITUTIONAL.value == "constitutional"

    def test_proposal_type_count(self):
        """ProposalType has exactly 6 members."""
        assert len(ProposalType) == 6


# =============================================================================
# VoteChoice Enum Tests
# =============================================================================


class TestVoteChoice:
    """Tests for VoteChoice enum."""

    def test_vote_choice_canonical_values(self):
        """VoteChoice has canonical values."""
        assert VoteChoice.APPROVE.value == "APPROVE"
        assert VoteChoice.REJECT.value == "REJECT"
        assert VoteChoice.ABSTAIN.value == "ABSTAIN"

    def test_vote_choice_aliases(self):
        """VoteChoice has FOR/AGAINST aliases."""
        # Aliases have the same value as their canonical counterparts
        assert VoteChoice.FOR.value == "APPROVE"
        assert VoteChoice.AGAINST.value == "REJECT"

    def test_from_string_canonical(self):
        """from_string works with canonical values."""
        assert VoteChoice.from_string("APPROVE") == VoteChoice.APPROVE
        assert VoteChoice.from_string("REJECT") == VoteChoice.REJECT
        assert VoteChoice.from_string("ABSTAIN") == VoteChoice.ABSTAIN

    def test_from_string_case_insensitive(self):
        """from_string is case insensitive."""
        assert VoteChoice.from_string("approve") == VoteChoice.APPROVE
        assert VoteChoice.from_string("Reject") == VoteChoice.REJECT
        assert VoteChoice.from_string("ABSTAIN") == VoteChoice.ABSTAIN

    def test_from_string_aliases(self):
        """from_string handles legacy aliases."""
        assert VoteChoice.from_string("FOR") == VoteChoice.APPROVE
        assert VoteChoice.from_string("AGAINST") == VoteChoice.REJECT
        assert VoteChoice.from_string("for") == VoteChoice.APPROVE
        assert VoteChoice.from_string("against") == VoteChoice.REJECT

    def test_from_string_common_alternatives(self):
        """from_string handles YES/NO alternatives."""
        assert VoteChoice.from_string("YES") == VoteChoice.APPROVE
        assert VoteChoice.from_string("NO") == VoteChoice.REJECT
        assert VoteChoice.from_string("yes") == VoteChoice.APPROVE
        assert VoteChoice.from_string("no") == VoteChoice.REJECT

    def test_from_string_strips_whitespace(self):
        """from_string strips whitespace."""
        assert VoteChoice.from_string("  APPROVE  ") == VoteChoice.APPROVE
        assert VoteChoice.from_string("\tREJECT\n") == VoteChoice.REJECT

    def test_from_string_invalid_value(self):
        """from_string raises ValueError for invalid values."""
        with pytest.raises(ValueError, match="Invalid vote choice"):
            VoteChoice.from_string("INVALID")
        with pytest.raises(ValueError, match="Invalid vote choice"):
            VoteChoice.from_string("MAYBE")

    def test_from_string_non_string_raises(self):
        """from_string raises ValueError for non-string input."""
        with pytest.raises(ValueError, match="must be string"):
            VoteChoice.from_string(123)  # type: ignore
        with pytest.raises(ValueError, match="must be string"):
            VoteChoice.from_string(None)  # type: ignore


# =============================================================================
# PerspectiveType Enum Tests
# =============================================================================


class TestPerspectiveType:
    """Tests for PerspectiveType enum."""

    def test_perspective_type_values(self):
        """PerspectiveType has expected values."""
        assert PerspectiveType.OPTIMISTIC.value == "optimistic"
        assert PerspectiveType.BALANCED.value == "balanced"
        assert PerspectiveType.CRITICAL.value == "critical"

    def test_perspective_type_count(self):
        """PerspectiveType has exactly 3 members."""
        assert len(PerspectiveType) == 3


# =============================================================================
# ProposalBase Tests
# =============================================================================


class TestProposalBase:
    """Tests for ProposalBase model."""

    def test_valid_proposal_base(self):
        """Valid proposal base data creates model."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            type=ProposalType.POLICY,
            action={"type": "update_policy", "policy_id": "p1", "changes": {}},
        )
        assert proposal.title == "Test Proposal Title"
        assert proposal.type == ProposalType.POLICY

    def test_title_min_length(self):
        """Title must be at least 5 characters."""
        with pytest.raises(ValidationError, match="String should have at least 5"):
            ProposalBase(
                title="Test",  # 4 chars
                description="This is a test proposal with enough description length.",
            )

    def test_title_max_length(self):
        """Title must be at most 200 characters."""
        with pytest.raises(ValidationError):
            ProposalBase(
                title="T" * 201,
                description="This is a test proposal with enough description length.",
            )

    def test_description_min_length(self):
        """Description must be at least 20 characters."""
        with pytest.raises(ValidationError, match="String should have at least 20"):
            ProposalBase(
                title="Test Proposal",
                description="Too short",  # Less than 20 chars
            )

    def test_description_max_length(self):
        """Description must be at most 10000 characters."""
        with pytest.raises(ValidationError):
            ProposalBase(
                title="Test Proposal",
                description="D" * 10001,
            )

    def test_default_type(self):
        """Default proposal type is POLICY."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
        )
        assert proposal.type == ProposalType.POLICY

    def test_action_default(self):
        """Action defaults to empty dict."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
        )
        assert proposal.action == {}

    def test_action_from_json_string(self):
        """Action can be parsed from JSON string."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action='{"type": "update_policy", "policy_id": "p1"}',
        )
        assert proposal.action == {"type": "update_policy", "policy_id": "p1"}

    def test_action_invalid_json_string(self):
        """Invalid JSON string becomes empty dict."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action="not valid json",
        )
        assert proposal.action == {}

    def test_action_from_dict(self):
        """Action can be passed as dict."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action={"key": "value"},
        )
        assert proposal.action == {"key": "value"}

    def test_action_non_dict_non_string(self):
        """Non-dict, non-string action becomes empty dict."""
        proposal = ProposalBase(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action=12345,  # type: ignore
        )
        assert proposal.action == {}


# =============================================================================
# ProposalCreate Tests
# =============================================================================


class TestProposalCreate:
    """Tests for ProposalCreate model."""

    def test_valid_proposal_create(self):
        """Valid proposal create data."""
        proposal = ProposalCreate(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            voting_period_days=7,
            quorum_percent=0.1,
            pass_threshold=0.5,
        )
        assert proposal.voting_period_days == 7
        assert proposal.quorum_percent == 0.1
        assert proposal.pass_threshold == 0.5

    def test_voting_period_days_bounds(self):
        """Voting period must be 1-30 days."""
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                voting_period_days=0,
            )
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                voting_period_days=31,
            )

    def test_quorum_percent_bounds(self):
        """Quorum percent must be 0.01-1.0."""
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                quorum_percent=0.001,
            )
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                quorum_percent=1.5,
            )

    def test_pass_threshold_bounds(self):
        """Pass threshold must be 0.5-1.0."""
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                pass_threshold=0.4,
            )
        with pytest.raises(ValidationError):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                pass_threshold=1.5,
            )

    def test_empty_action_allowed(self):
        """Empty action is allowed (informational proposals)."""
        proposal = ProposalCreate(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action={},
        )
        assert proposal.action == {}

    def test_action_without_type_allowed(self):
        """Action without type is allowed (informational)."""
        proposal = ProposalCreate(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            action={"note": "just informational"},
        )
        assert proposal.action == {"note": "just informational"}

    def test_valid_action_for_policy_type(self):
        """Valid action for POLICY type passes validation."""
        proposal = ProposalCreate(
            title="Test Proposal Title",
            description="This is a test proposal with enough description length.",
            type=ProposalType.POLICY,
            action={"type": "update_policy", "policy_id": "p1", "changes": {}},
        )
        assert proposal.action["type"] == "update_policy"

    def test_invalid_action_for_proposal_type(self):
        """Invalid action type for proposal type raises error."""
        with pytest.raises(ValidationError, match="not valid for proposal type"):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                type=ProposalType.POLICY,
                action={"type": "archive"},  # CAPSULE action, not POLICY
            )

    def test_missing_required_action_fields(self):
        """Missing required fields in action raises error."""
        with pytest.raises(ValidationError, match="missing required fields"):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                type=ProposalType.POLICY,
                action={"type": "update_policy"},  # Missing policy_id and changes
            )

    def test_dangerous_fields_rejected(self):
        """Dangerous fields in action are rejected."""
        with pytest.raises(ValidationError, match="forbidden fields"):
            ProposalCreate(
                title="Test Proposal Title",
                description="This is a test proposal with enough description length.",
                type=ProposalType.POLICY,
                action={
                    "type": "update_policy",
                    "policy_id": "p1",
                    "changes": {},
                    "__import__": "os",
                },
            )

    def test_all_action_types_have_required_fields(self):
        """Every valid action type has required fields defined."""
        for proposal_type, actions in VALID_PROPOSAL_ACTIONS.items():
            for action in actions:
                assert action in REQUIRED_ACTION_FIELDS, (
                    f"Action '{action}' missing from REQUIRED_ACTION_FIELDS"
                )


# =============================================================================
# Proposal Tests
# =============================================================================


class TestProposal:
    """Tests for Proposal model."""

    def create_proposal(self, **kwargs):
        """Helper to create a proposal with defaults."""
        defaults = {
            "id": "prop-123",
            "proposer_id": "user-456",
            "title": "Test Proposal Title",
            "description": "This is a test proposal with enough description length.",
            "status": ProposalStatus.DRAFT,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        defaults.update(kwargs)
        return Proposal(**defaults)

    def test_valid_proposal(self):
        """Valid proposal creates model."""
        proposal = self.create_proposal()
        assert proposal.id == "prop-123"
        assert proposal.proposer_id == "user-456"
        assert proposal.status == ProposalStatus.DRAFT

    def test_proposal_defaults(self):
        """Proposal has sensible defaults."""
        proposal = self.create_proposal()
        assert proposal.voting_period_days == 7
        assert proposal.quorum_percent == 0.1
        assert proposal.pass_threshold == 0.5
        assert proposal.votes_for == 0
        assert proposal.votes_against == 0
        assert proposal.votes_abstain == 0
        assert proposal.weight_for == 0.0
        assert proposal.weight_against == 0.0
        assert proposal.weight_abstain == 0.0
        assert proposal.timelock_hours == 24

    def test_total_votes_property(self):
        """total_votes calculates correctly."""
        proposal = self.create_proposal(
            votes_for=10,
            votes_against=5,
            votes_abstain=3,
        )
        assert proposal.total_votes == 18

    def test_total_weight_property(self):
        """total_weight calculates correctly."""
        proposal = self.create_proposal(
            weight_for=100.0,
            weight_against=50.0,
            weight_abstain=25.0,
        )
        assert proposal.total_weight == 175.0

    def test_approval_ratio_property(self):
        """approval_ratio calculates correctly."""
        proposal = self.create_proposal(
            weight_for=75.0,
            weight_against=25.0,
            weight_abstain=10.0,
        )
        # Excludes abstentions: 75 / (75 + 25) = 0.75
        assert proposal.approval_ratio == 0.75

    def test_approval_ratio_zero_votes(self):
        """approval_ratio returns 0.0 when no decisive votes."""
        proposal = self.create_proposal(
            weight_for=0.0,
            weight_against=0.0,
            weight_abstain=10.0,
        )
        assert proposal.approval_ratio == 0.0

    def test_is_voting_open_draft(self):
        """is_voting_open returns False for DRAFT status."""
        proposal = self.create_proposal(status=ProposalStatus.DRAFT)
        assert proposal.is_voting_open is False

    def test_is_voting_open_voting_in_range(self):
        """is_voting_open returns True when in voting period."""
        now = datetime.now(UTC)
        proposal = self.create_proposal(
            status=ProposalStatus.VOTING,
            voting_starts_at=now - timedelta(hours=1),
            voting_ends_at=now + timedelta(hours=1),
        )
        assert proposal.is_voting_open is True

    def test_is_voting_open_voting_ended(self):
        """is_voting_open returns False when voting ended."""
        now = datetime.now(UTC)
        proposal = self.create_proposal(
            status=ProposalStatus.VOTING,
            voting_starts_at=now - timedelta(hours=2),
            voting_ends_at=now - timedelta(hours=1),
        )
        assert proposal.is_voting_open is False

    def test_is_execution_allowed_not_passed(self):
        """is_execution_allowed returns False if not PASSED."""
        proposal = self.create_proposal(status=ProposalStatus.DRAFT)
        assert proposal.is_execution_allowed is False

    def test_is_execution_allowed_no_timelock(self):
        """is_execution_allowed returns False if no execution_allowed_after."""
        proposal = self.create_proposal(
            status=ProposalStatus.PASSED,
            execution_allowed_after=None,
        )
        assert proposal.is_execution_allowed is False

    def test_is_execution_allowed_timelock_passed(self):
        """is_execution_allowed returns True when timelock passed."""
        now = datetime.now(UTC)
        proposal = self.create_proposal(
            status=ProposalStatus.PASSED,
            execution_allowed_after=now - timedelta(hours=1),
        )
        assert proposal.is_execution_allowed is True

    def test_is_execution_allowed_timelock_not_passed(self):
        """is_execution_allowed returns False when timelock not passed."""
        now = datetime.now(UTC)
        proposal = self.create_proposal(
            status=ProposalStatus.PASSED,
            execution_allowed_after=now + timedelta(hours=1),
        )
        assert proposal.is_execution_allowed is False

    def test_timelock_remaining_seconds(self):
        """timelock_remaining_seconds calculates correctly."""
        now = datetime.now(UTC)
        proposal = self.create_proposal(
            status=ProposalStatus.PASSED,
            execution_allowed_after=now + timedelta(hours=1),
        )
        # Should be approximately 3600 seconds
        remaining = proposal.timelock_remaining_seconds
        assert remaining is not None
        assert 3500 < remaining <= 3600

    def test_timelock_remaining_none_when_not_passed(self):
        """timelock_remaining_seconds returns None if not PASSED."""
        proposal = self.create_proposal(status=ProposalStatus.DRAFT)
        assert proposal.timelock_remaining_seconds is None


# =============================================================================
# VoteCreate Tests
# =============================================================================


class TestVoteCreate:
    """Tests for VoteCreate model."""

    def test_valid_vote_create(self):
        """Valid vote create data."""
        vote = VoteCreate(
            choice=VoteChoice.APPROVE,
            reason="Good proposal",
        )
        assert vote.choice == VoteChoice.APPROVE
        assert vote.reason == "Good proposal"

    def test_vote_create_reason_optional(self):
        """Reason is optional."""
        vote = VoteCreate(choice=VoteChoice.REJECT)
        assert vote.reason is None

    def test_vote_create_reason_max_length(self):
        """Reason has max length of 1000."""
        with pytest.raises(ValidationError):
            VoteCreate(
                choice=VoteChoice.APPROVE,
                reason="R" * 1001,
            )


# =============================================================================
# Vote Tests
# =============================================================================


class TestVote:
    """Tests for Vote model."""

    def test_valid_vote(self):
        """Valid vote creates model."""
        vote = Vote(
            id="vote-123",
            proposal_id="prop-456",
            voter_id="user-789",
            choice=VoteChoice.APPROVE,
            weight=1.5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert vote.id == "vote-123"
        assert vote.weight == 1.5

    def test_vote_weight_bounds(self):
        """Weight must be >= 0."""
        with pytest.raises(ValidationError):
            Vote(
                id="vote-123",
                proposal_id="prop-456",
                voter_id="user-789",
                choice=VoteChoice.APPROVE,
                weight=-1.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_vote_delegated_from(self):
        """Vote can have delegated_from."""
        vote = Vote(
            id="vote-123",
            proposal_id="prop-456",
            voter_id="user-789",
            choice=VoteChoice.APPROVE,
            weight=1.5,
            delegated_from="other-user",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert vote.delegated_from == "other-user"


# =============================================================================
# VoteDelegation Tests
# =============================================================================


class TestVoteDelegation:
    """Tests for VoteDelegation model."""

    def test_valid_delegation(self):
        """Valid delegation creates model."""
        delegation = VoteDelegation(
            delegator_id="user-123",
            delegate_id="user-456",
        )
        assert delegation.delegator_id == "user-123"
        assert delegation.delegate_id == "user-456"
        assert delegation.is_active is True
        assert delegation.proposal_types is None

    def test_delegation_with_proposal_types(self):
        """Delegation can specify proposal types."""
        delegation = VoteDelegation(
            delegator_id="user-123",
            delegate_id="user-456",
            proposal_types=[ProposalType.POLICY, ProposalType.SYSTEM],
        )
        assert delegation.proposal_types == [ProposalType.POLICY, ProposalType.SYSTEM]

    def test_delegation_auto_generates_id(self):
        """Delegation auto-generates ID."""
        delegation = VoteDelegation(
            delegator_id="user-123",
            delegate_id="user-456",
        )
        assert delegation.id is not None
        assert len(delegation.id) > 0

    def test_delegation_with_expiry(self):
        """Delegation can have expiry."""
        expires = datetime.now(UTC) + timedelta(days=30)
        delegation = VoteDelegation(
            delegator_id="user-123",
            delegate_id="user-456",
            expires_at=expires,
        )
        assert delegation.expires_at == expires


# =============================================================================
# EthicalConcern Tests
# =============================================================================


class TestEthicalConcern:
    """Tests for EthicalConcern model."""

    def test_valid_ethical_concern(self):
        """Valid ethical concern creates model."""
        concern = EthicalConcern(
            category="privacy",
            severity="high",
            description="May expose user data",
            recommendation="Add data anonymization",
        )
        assert concern.category == "privacy"
        assert concern.severity == "high"


# =============================================================================
# ConstitutionalAnalysis Tests
# =============================================================================


class TestConstitutionalAnalysis:
    """Tests for ConstitutionalAnalysis model."""

    def test_valid_constitutional_analysis(self):
        """Valid analysis creates model."""
        analysis = ConstitutionalAnalysis(
            proposal_id="prop-123",
            ethical_score=80,
            fairness_score=75,
            safety_score=90,
            transparency_score=85,
            concerns=[],
            summary="The proposal is ethically sound.",
            recommendation="approve",
            confidence=0.9,
        )
        assert analysis.ethical_score == 80
        assert analysis.recommendation == "approve"

    def test_score_bounds(self):
        """Scores must be 0-100."""
        with pytest.raises(ValidationError):
            ConstitutionalAnalysis(
                proposal_id="prop-123",
                ethical_score=150,  # Invalid
                fairness_score=75,
                safety_score=90,
                transparency_score=85,
                summary="Summary",
                recommendation="approve",
                confidence=0.9,
            )
        with pytest.raises(ValidationError):
            ConstitutionalAnalysis(
                proposal_id="prop-123",
                ethical_score=-10,  # Invalid
                fairness_score=75,
                safety_score=90,
                transparency_score=85,
                summary="Summary",
                recommendation="approve",
                confidence=0.9,
            )

    def test_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            ConstitutionalAnalysis(
                proposal_id="prop-123",
                ethical_score=80,
                fairness_score=75,
                safety_score=90,
                transparency_score=85,
                summary="Summary",
                recommendation="approve",
                confidence=1.5,  # Invalid
            )

    def test_overall_score_property(self):
        """overall_score calculates average."""
        analysis = ConstitutionalAnalysis(
            proposal_id="prop-123",
            ethical_score=80,
            fairness_score=60,
            safety_score=100,
            transparency_score=80,
            summary="Summary",
            recommendation="approve",
            confidence=0.9,
        )
        # (80 + 60 + 100 + 80) / 4 = 80.0
        assert analysis.overall_score == 80.0


# =============================================================================
# PerspectiveAnalysis Tests
# =============================================================================


class TestPerspectiveAnalysis:
    """Tests for PerspectiveAnalysis model."""

    def test_valid_perspective_analysis(self):
        """Valid perspective analysis creates model."""
        analysis = PerspectiveAnalysis(
            perspective_type=PerspectiveType.OPTIMISTIC,
            assessment="This could lead to great improvements.",
            key_points=["Better UX", "Increased engagement"],
            confidence=0.8,
        )
        assert analysis.perspective_type == PerspectiveType.OPTIMISTIC
        assert len(analysis.key_points) == 2

    def test_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            PerspectiveAnalysis(
                perspective_type=PerspectiveType.CRITICAL,
                assessment="Assessment",
                confidence=1.5,
            )

    def test_default_confidence(self):
        """Default confidence is 0.7."""
        analysis = PerspectiveAnalysis(
            perspective_type=PerspectiveType.BALANCED,
            assessment="Assessment",
        )
        assert analysis.confidence == 0.7


# =============================================================================
# GhostCouncilMember Tests
# =============================================================================


class TestGhostCouncilMember:
    """Tests for GhostCouncilMember model."""

    def test_valid_ghost_council_member(self):
        """Valid member creates model."""
        member = GhostCouncilMember(
            id="member-123",
            name="Ethics Advisor",
            role="Ethics Expert",
            domain="ethics",
            persona="A careful and thoughtful advisor focused on ethical implications.",
            weight=1.5,
        )
        assert member.name == "Ethics Advisor"
        assert member.weight == 1.5

    def test_weight_bounds(self):
        """Weight must be >= 0."""
        with pytest.raises(ValidationError):
            GhostCouncilMember(
                id="member-123",
                name="Test",
                role="Role",
                persona="Persona",
                weight=-1.0,
            )

    def test_defaults(self):
        """Member has sensible defaults."""
        member = GhostCouncilMember(
            id="member-123",
            name="Test",
            role="Role",
            persona="Persona",
        )
        assert member.domain == "general"
        assert member.weight == 1.0
        assert member.icon == "user"


# =============================================================================
# GhostCouncilVote Tests
# =============================================================================


class TestGhostCouncilVote:
    """Tests for GhostCouncilVote model."""

    def test_valid_ghost_council_vote(self):
        """Valid vote creates model."""
        vote = GhostCouncilVote(
            member_id="member-123",
            member_name="Ethics Advisor",
            vote=VoteChoice.APPROVE,
            reasoning="The proposal aligns with our ethical principles.",
            confidence=0.85,
        )
        assert vote.vote == VoteChoice.APPROVE
        assert vote.confidence == 0.85

    def test_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            GhostCouncilVote(
                member_id="member-123",
                member_name="Test",
                vote=VoteChoice.REJECT,
                reasoning="Reasoning",
                confidence=1.5,
            )

    def test_defaults(self):
        """Vote has sensible defaults."""
        vote = GhostCouncilVote(
            member_id="member-123",
            member_name="Test",
            vote=VoteChoice.ABSTAIN,
            reasoning="Reasoning",
            confidence=0.5,
        )
        assert vote.member_role == "Advisor"
        assert vote.perspectives == []
        assert vote.primary_benefits == []
        assert vote.primary_concerns == []


# =============================================================================
# GhostCouncilOpinion Tests
# =============================================================================


class TestGhostCouncilOpinion:
    """Tests for GhostCouncilOpinion model."""

    def test_valid_ghost_council_opinion(self):
        """Valid opinion creates model."""
        opinion = GhostCouncilOpinion(
            proposal_id="prop-123",
            consensus_vote=VoteChoice.APPROVE,
            consensus_strength=0.8,
            final_recommendation="Proceed with implementation.",
        )
        assert opinion.consensus_vote == VoteChoice.APPROVE
        assert opinion.consensus_strength == 0.8

    def test_consensus_strength_bounds(self):
        """Consensus strength must be 0.0-1.0."""
        with pytest.raises(ValidationError):
            GhostCouncilOpinion(
                proposal_id="prop-123",
                consensus_vote=VoteChoice.REJECT,
                consensus_strength=1.5,
                final_recommendation="Recommendation",
            )

    def test_defaults(self):
        """Opinion has sensible defaults."""
        opinion = GhostCouncilOpinion(
            proposal_id="prop-123",
            consensus_vote=VoteChoice.ABSTAIN,
            consensus_strength=0.5,
            final_recommendation="Recommendation",
        )
        assert opinion.member_votes == []
        assert opinion.key_points == []
        assert opinion.dissenting_opinions == []
        assert opinion.optimistic_summary == ""
        assert opinion.balanced_summary == ""
        assert opinion.critical_summary == ""
        assert opinion.total_benefits_identified == 0
        assert opinion.total_concerns_identified == 0


# =============================================================================
# GovernanceStats Tests
# =============================================================================


class TestGovernanceStats:
    """Tests for GovernanceStats model."""

    def test_valid_governance_stats(self):
        """Valid stats creates model."""
        stats = GovernanceStats(
            total_proposals=100,
            active_proposals=10,
            passed_proposals=60,
            rejected_proposals=25,
            total_votes=1500,
            unique_voters=200,
            average_participation=0.75,
            average_approval_ratio=0.65,
        )
        assert stats.total_proposals == 100
        assert stats.average_participation == 0.75

    def test_defaults(self):
        """Stats has zero defaults."""
        stats = GovernanceStats()
        assert stats.total_proposals == 0
        assert stats.active_proposals == 0
        assert stats.passed_proposals == 0
        assert stats.rejected_proposals == 0
        assert stats.total_votes == 0
        assert stats.unique_voters == 0
        assert stats.average_participation == 0.0
        assert stats.average_approval_ratio == 0.0


# =============================================================================
# VALID_PROPOSAL_ACTIONS Completeness Tests
# =============================================================================


class TestValidProposalActions:
    """Tests for VALID_PROPOSAL_ACTIONS constant."""

    def test_all_proposal_types_have_actions(self):
        """Every ProposalType has defined actions."""
        for proposal_type in ProposalType:
            assert proposal_type in VALID_PROPOSAL_ACTIONS, (
                f"ProposalType.{proposal_type.name} missing from VALID_PROPOSAL_ACTIONS"
            )

    def test_actions_are_non_empty(self):
        """Each proposal type has at least one action."""
        for proposal_type, actions in VALID_PROPOSAL_ACTIONS.items():
            assert len(actions) > 0, f"ProposalType.{proposal_type.name} has no actions defined"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
