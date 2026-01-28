"""
Tests for Ghost Council Service

Tests cover:
- Ghost Council initialization and configuration
- Proposal deliberation
- Issue detection and response
- Consensus calculation
- Caching behavior
- Statistics
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.base import ProposalStatus
from forge.models.events import EventType
from forge.models.governance import (
    GhostCouncilMember,
    GhostCouncilOpinion,
    GhostCouncilVote,
    PerspectiveAnalysis,
    PerspectiveType,
    Proposal,
    ProposalType,
    VoteChoice,
)
from forge.services.ghost_council import (
    DEFAULT_COUNCIL_MEMBERS,
    COUNCIL_TIERS,
    GhostCouncilConfig,
    GhostCouncilService,
    IssueCategory,
    IssueSeverity,
    SeriousIssue,
    get_ghost_council_service,
    init_ghost_council_service,
    shutdown_ghost_council_service,
)


class TestGhostCouncilConfig:
    """Tests for Ghost Council configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GhostCouncilConfig()

        assert config.require_unanimous_for_critical is True
        assert config.min_confidence_threshold == 0.6
        assert config.auto_review_security_issues is True
        assert config.max_deliberation_time == 60.0
        assert config.profile == "comprehensive"
        assert config.cache_enabled is True
        assert config.cache_ttl_days == 30

    def test_custom_config(self):
        """Test custom configuration."""
        config = GhostCouncilConfig(
            profile="quick",
            cache_enabled=False,
            min_confidence_threshold=0.8,
        )

        assert config.profile == "quick"
        assert config.cache_enabled is False
        assert config.min_confidence_threshold == 0.8


class TestGhostCouncilInit:
    """Tests for Ghost Council initialization."""

    def test_init_default(self):
        """Test default initialization."""
        service = GhostCouncilService()

        assert len(service._members) == len(DEFAULT_COUNCIL_MEMBERS)
        assert service._config is not None
        assert isinstance(service._active_issues, dict)
        assert isinstance(service._opinion_cache, dict)

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = GhostCouncilConfig(profile="quick")
        service = GhostCouncilService(config=config)

        assert service._config.profile == "quick"
        # Quick mode should have fewer members
        assert len(service._members) == len(COUNCIL_TIERS["quick"])

    def test_init_with_custom_members(self):
        """Test initialization with custom members."""
        custom_member = GhostCouncilMember(
            id="custom_member",
            name="Custom",
            role="Custom Advisor",
            persona="A custom advisor.",
        )
        service = GhostCouncilService(members=[custom_member])

        assert len(service._members) == 1
        assert service._members[0].name == "Custom"

    def test_profile_member_selection(self):
        """Test member selection based on profile."""
        # Quick profile
        quick_config = GhostCouncilConfig(profile="quick")
        quick_service = GhostCouncilService(config=quick_config)
        assert len(quick_service._members) == 1

        # Standard profile
        standard_config = GhostCouncilConfig(profile="standard")
        standard_service = GhostCouncilService(config=standard_config)
        assert len(standard_service._members) == len(COUNCIL_TIERS["standard"])

        # Comprehensive profile
        comprehensive_config = GhostCouncilConfig(profile="comprehensive")
        comprehensive_service = GhostCouncilService(config=comprehensive_config)
        assert len(comprehensive_service._members) == len(COUNCIL_TIERS["comprehensive"])


class TestProposalDeliberation:
    """Tests for proposal deliberation."""

    @pytest.fixture
    def service(self):
        config = GhostCouncilConfig(cache_enabled=False)
        return GhostCouncilService(config=config)

    @pytest.fixture
    def mock_proposal(self):
        return Proposal(
            id="proposal-123",
            proposer_id="user-1",
            title="Test Proposal",
            description="This is a test proposal with enough characters.",
            type=ProposalType.POLICY,
            status=ProposalStatus.VOTING,
            votes_for=5,
            votes_against=2,
            votes_abstain=1,
            weight_for=50.0,
            weight_against=20.0,
            weight_abstain=10.0,
        )

    @pytest.mark.asyncio
    async def test_deliberate_proposal(self, service, mock_proposal):
        """Test proposal deliberation returns opinion."""
        # Mock LLM service
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {
                    "assessment": "Good potential benefits.",
                    "key_points": ["benefit 1", "benefit 2"],
                    "confidence": 0.8,
                },
                "balanced": {
                    "assessment": "Trade-offs exist.",
                    "key_points": ["trade-off 1"],
                    "confidence": 0.85,
                },
                "critical": {
                    "assessment": "Some risks to consider.",
                    "key_points": ["risk 1"],
                    "confidence": 0.75,
                },
            },
            "synthesis": {
                "vote": "APPROVE",
                "reasoning": "Benefits outweigh risks.",
                "confidence": 0.8,
                "primary_benefits": ["benefit 1"],
                "primary_concerns": ["risk 1"],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            opinion = await service.deliberate_proposal(mock_proposal)

        assert isinstance(opinion, GhostCouncilOpinion)
        assert opinion.proposal_id == "proposal-123"
        assert opinion.consensus_vote in [VoteChoice.APPROVE, VoteChoice.REJECT, VoteChoice.ABSTAIN]
        assert len(opinion.member_votes) > 0

    @pytest.mark.asyncio
    async def test_deliberate_proposal_with_context(self, service, mock_proposal):
        """Test proposal deliberation with additional context."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {"assessment": "Good", "key_points": [], "confidence": 0.7},
                "balanced": {"assessment": "Neutral", "key_points": [], "confidence": 0.7},
                "critical": {"assessment": "Risky", "key_points": [], "confidence": 0.7},
            },
            "synthesis": {
                "vote": "APPROVE",
                "reasoning": "Approved.",
                "confidence": 0.7,
                "primary_benefits": [],
                "primary_concerns": [],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            context = {"related_proposals": ["prop-001"], "previous_votes": 10}
            opinion = await service.deliberate_proposal(mock_proposal, context=context)

        assert opinion is not None

    @pytest.mark.asyncio
    async def test_deliberate_proposal_llm_error(self, service, mock_proposal):
        """Test deliberation handles LLM errors gracefully."""
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM error"))

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            opinion = await service.deliberate_proposal(mock_proposal)

        # Should still return an opinion with abstain votes
        assert opinion is not None
        for vote in opinion.member_votes:
            assert vote.vote == VoteChoice.ABSTAIN


class TestCaching:
    """Tests for opinion caching."""

    @pytest.fixture
    def mock_proposal(self):
        return Proposal(
            id="cached-proposal",
            proposer_id="user-1",
            title="Cached Proposal",
            description="This proposal will be cached for testing purposes.",
            type=ProposalType.POLICY,
            status=ProposalStatus.VOTING,
        )

    def test_hash_proposal(self):
        """Test proposal hashing for cache key."""
        config = GhostCouncilConfig(profile="standard")
        service = GhostCouncilService(config=config)

        proposal = Proposal(
            id="test-1",
            proposer_id="user-1",
            title="Test Title",
            description="Test description for the proposal hash.",
            type=ProposalType.POLICY,
        )

        hash1 = service._hash_proposal(proposal)
        hash2 = service._hash_proposal(proposal)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_hash_proposal_different_profiles(self):
        """Test that different profiles produce different cache keys."""
        proposal = Proposal(
            id="test-1",
            proposer_id="user-1",
            title="Same Title",
            description="Same description but different profiles.",
            type=ProposalType.POLICY,
        )

        service1 = GhostCouncilService(config=GhostCouncilConfig(profile="quick"))
        service2 = GhostCouncilService(config=GhostCouncilConfig(profile="standard"))

        hash1 = service1._hash_proposal(proposal)
        hash2 = service2._hash_proposal(proposal)

        assert hash1 != hash2

    def test_cache_validity(self):
        """Test cache validity checking."""
        config = GhostCouncilConfig(cache_ttl_days=30)
        service = GhostCouncilService(config=config)

        # Recent cache should be valid
        recent = datetime.now(UTC) - timedelta(days=10)
        assert service._is_cache_valid(recent) is True

        # Expired cache should be invalid
        expired = datetime.now(UTC) - timedelta(days=40)
        assert service._is_cache_valid(expired) is False

    def test_cache_validity_disabled(self):
        """Test cache validity when caching is disabled."""
        config = GhostCouncilConfig(cache_enabled=False)
        service = GhostCouncilService(config=config)

        recent = datetime.now(UTC)
        assert service._is_cache_valid(recent) is False

    @pytest.mark.asyncio
    async def test_cached_opinion_returned(self, mock_proposal):
        """Test that cached opinions are returned."""
        config = GhostCouncilConfig(cache_enabled=True, cache_ttl_days=30)
        service = GhostCouncilService(config=config)

        # Pre-cache an opinion
        cached_opinion = GhostCouncilOpinion(
            proposal_id=mock_proposal.id,
            deliberated_at=datetime.now(UTC),
            member_votes=[],
            consensus_vote=VoteChoice.APPROVE,
            consensus_strength=0.9,
            key_points=["cached"],
            dissenting_opinions=[],
            final_recommendation="Cached recommendation",
        )
        cache_key = service._hash_proposal(mock_proposal)
        service._opinion_cache[cache_key] = (cached_opinion, datetime.now(UTC))

        # Get cached opinion
        result = service._get_cached_opinion(mock_proposal)

        assert result is not None
        assert result.final_recommendation == "Cached recommendation"
        assert service._stats["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_skip_cache_option(self, mock_proposal):
        """Test skip_cache forces fresh deliberation."""
        config = GhostCouncilConfig(cache_enabled=True)
        service = GhostCouncilService(config=config)

        # Pre-cache an opinion
        cached_opinion = GhostCouncilOpinion(
            proposal_id=mock_proposal.id,
            deliberated_at=datetime.now(UTC),
            member_votes=[],
            consensus_vote=VoteChoice.APPROVE,
            consensus_strength=0.9,
            key_points=["cached"],
            dissenting_opinions=[],
            final_recommendation="Cached",
        )
        cache_key = service._hash_proposal(mock_proposal)
        service._opinion_cache[cache_key] = (cached_opinion, datetime.now(UTC))

        # Mock LLM for fresh deliberation
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {"assessment": "Fresh", "key_points": [], "confidence": 0.7},
                "balanced": {"assessment": "Fresh", "key_points": [], "confidence": 0.7},
                "critical": {"assessment": "Fresh", "key_points": [], "confidence": 0.7},
            },
            "synthesis": {
                "vote": "REJECT",
                "reasoning": "Fresh deliberation.",
                "confidence": 0.7,
                "primary_benefits": [],
                "primary_concerns": [],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            result = await service.deliberate_proposal(mock_proposal, skip_cache=True)

        # Should have fresh result, not cached
        assert result.consensus_vote != cached_opinion.consensus_vote or result.final_recommendation != "Cached"

    def test_cache_size_limit(self):
        """Test cache size limits."""
        config = GhostCouncilConfig(cache_enabled=True)
        service = GhostCouncilService(config=config)

        # Fill cache beyond limit
        for i in range(1100):
            proposal = Proposal(
                id=f"prop-{i}",
                proposer_id="user-1",
                title=f"Proposal {i}",
                description=f"Description for proposal {i} with enough characters.",
                type=ProposalType.POLICY,
            )
            opinion = GhostCouncilOpinion(
                proposal_id=proposal.id,
                deliberated_at=datetime.now(UTC),
                member_votes=[],
                consensus_vote=VoteChoice.APPROVE,
                consensus_strength=0.5,
                key_points=[],
                dissenting_opinions=[],
                final_recommendation="Test",
            )
            service._cache_opinion(proposal, opinion)

        # Should have trimmed to max size
        assert len(service._opinion_cache) <= 1000


class TestConsensusCalculation:
    """Tests for consensus calculation."""

    @pytest.fixture
    def service(self):
        return GhostCouncilService()

    def test_calculate_consensus_unanimous_approve(self, service):
        """Test consensus with unanimous approval."""
        votes = [
            GhostCouncilVote(
                member_id="gc_ethics",
                member_name="Sophia",
                member_role="Ethics Guardian",
                perspectives=[],
                vote=VoteChoice.APPROVE,
                reasoning="Approved.",
                confidence=0.9,
                primary_benefits=["benefit"],
                primary_concerns=[],
            ),
            GhostCouncilVote(
                member_id="gc_security",
                member_name="Marcus",
                member_role="Security Sentinel",
                perspectives=[],
                vote=VoteChoice.APPROVE,
                reasoning="Secure.",
                confidence=0.85,
                primary_benefits=["secure"],
                primary_concerns=[],
            ),
        ]

        result = service._calculate_consensus(votes)

        assert result["vote"] == VoteChoice.APPROVE
        assert result["strength"] > 0.8

    def test_calculate_consensus_unanimous_reject(self, service):
        """Test consensus with unanimous rejection."""
        votes = [
            GhostCouncilVote(
                member_id="gc_ethics",
                member_name="Sophia",
                member_role="Ethics Guardian",
                perspectives=[],
                vote=VoteChoice.REJECT,
                reasoning="Rejected.",
                confidence=0.9,
                primary_benefits=[],
                primary_concerns=["concern"],
            ),
        ]

        result = service._calculate_consensus(votes)

        assert result["vote"] == VoteChoice.REJECT

    def test_calculate_consensus_split_decision(self, service):
        """Test consensus with split decision."""
        votes = [
            GhostCouncilVote(
                member_id="gc_ethics",
                member_name="Sophia",
                member_role="Ethics Guardian",
                perspectives=[],
                vote=VoteChoice.APPROVE,
                reasoning="Approved.",
                confidence=0.9,
                primary_benefits=[],
                primary_concerns=[],
            ),
            GhostCouncilVote(
                member_id="gc_security",
                member_name="Marcus",
                member_role="Security Sentinel",
                perspectives=[],
                vote=VoteChoice.REJECT,
                reasoning="Rejected.",
                confidence=0.9,
                primary_benefits=[],
                primary_concerns=[],
            ),
        ]

        result = service._calculate_consensus(votes)

        # Result depends on weights
        assert result["vote"] in [VoteChoice.APPROVE, VoteChoice.REJECT, VoteChoice.ABSTAIN]

    def test_calculate_consensus_no_votes(self, service):
        """Test consensus with no votes."""
        result = service._calculate_consensus([])

        assert result["vote"] == VoteChoice.ABSTAIN
        assert result["strength"] == 0.0

    def test_calculate_consensus_weighted_votes(self, service):
        """Test consensus respects member weights."""
        # Create a service with known member weights
        high_weight_member = GhostCouncilMember(
            id="high_weight",
            name="High",
            role="Advisor",
            persona="High weight advisor",
            weight=2.0,
        )
        low_weight_member = GhostCouncilMember(
            id="low_weight",
            name="Low",
            role="Advisor",
            persona="Low weight advisor",
            weight=0.5,
        )
        service_weighted = GhostCouncilService(members=[high_weight_member, low_weight_member])

        votes = [
            GhostCouncilVote(
                member_id="high_weight",
                member_name="High",
                member_role="Advisor",
                perspectives=[],
                vote=VoteChoice.APPROVE,
                reasoning="High weight approves.",
                confidence=1.0,
                primary_benefits=[],
                primary_concerns=[],
            ),
            GhostCouncilVote(
                member_id="low_weight",
                member_name="Low",
                member_role="Advisor",
                perspectives=[],
                vote=VoteChoice.REJECT,
                reasoning="Low weight rejects.",
                confidence=1.0,
                primary_benefits=[],
                primary_concerns=[],
            ),
        ]

        result = service_weighted._calculate_consensus(votes)

        # High weight should win
        assert result["vote"] == VoteChoice.APPROVE


class TestIssueDetection:
    """Tests for serious issue detection."""

    @pytest.fixture
    def service(self):
        return GhostCouncilService()

    def test_detect_security_threat_critical(self, service):
        """Test detecting critical security threat."""
        payload = {
            "threat_level": "critical",
            "threat_type": "Data breach",
            "description": "Unauthorized access detected",
            "affected_entities": ["user-1", "user-2"],
        }

        issue = service.detect_serious_issue(EventType.SECURITY_THREAT, payload, "security_monitor")

        assert issue is not None
        assert issue.category == IssueCategory.SECURITY
        assert issue.severity == IssueSeverity.CRITICAL
        assert "Data breach" in issue.title

    def test_detect_security_threat_high(self, service):
        """Test detecting high severity security threat."""
        payload = {
            "threat_level": "high",
            "threat_type": "Brute force attack",
        }

        issue = service.detect_serious_issue(EventType.SECURITY_ALERT, payload, "security")

        assert issue is not None
        assert issue.severity == IssueSeverity.HIGH

    def test_detect_security_threat_low_ignored(self, service):
        """Test that low severity threats are ignored."""
        payload = {"threat_level": "low"}

        issue = service.detect_serious_issue(EventType.SECURITY_ALERT, payload, "security")

        assert issue is None

    def test_detect_trust_drop(self, service):
        """Test detecting significant trust drop."""
        payload = {
            "user_id": "user-123",
            "old_trust": 80,
            "new_trust": 50,
        }

        issue = service.detect_serious_issue(EventType.TRUST_UPDATED, payload, "trust_system")

        assert issue is not None
        assert issue.category == IssueCategory.TRUST
        assert issue.severity == IssueSeverity.HIGH

    def test_detect_trust_drop_below_threshold(self, service):
        """Test trust drop below threshold is ignored."""
        payload = {
            "user_id": "user-123",
            "old_trust": 80,
            "new_trust": 75,  # Only 5 point drop
        }

        issue = service.detect_serious_issue(EventType.TRUST_UPDATED, payload, "trust_system")

        assert issue is None

    def test_detect_governance_conflict(self, service):
        """Test detecting governance conflicts."""
        payload = {
            "action": "proposal_vetoed",
            "proposal_id": "prop-123",
            "description": "Emergency veto applied",
        }

        issue = service.detect_serious_issue(EventType.GOVERNANCE_ACTION, payload, "governance")

        assert issue is not None
        assert issue.category == IssueCategory.GOVERNANCE
        assert issue.severity == IssueSeverity.HIGH

    def test_detect_system_error(self, service):
        """Test detecting system errors."""
        payload = {
            "error_count": 5,
            "error_type": "Database connection",
            "message": "Multiple connection failures",
            "affected_components": ["api", "worker"],
        }

        issue = service.detect_serious_issue(EventType.SYSTEM_ERROR, payload, "system_monitor")

        assert issue is not None
        assert issue.category == IssueCategory.SYSTEM
        assert issue.severity == IssueSeverity.HIGH

    def test_detect_immune_alert(self, service):
        """Test detecting immune system alerts."""
        payload = {
            "alert_type": "quarantine",
            "description": "Capsule quarantined",
            "affected_entities": ["capsule-123"],
        }

        issue = service.detect_serious_issue(EventType.IMMUNE_ALERT, payload, "immune_system")

        assert issue is not None
        assert issue.category == IssueCategory.SYSTEM
        assert "Immune System Alert" in issue.title


class TestIssueResponse:
    """Tests for responding to serious issues."""

    @pytest.fixture
    def service(self):
        config = GhostCouncilConfig(cache_enabled=False)
        return GhostCouncilService(config=config)

    @pytest.fixture
    def mock_issue(self):
        return SeriousIssue(
            id="issue-123",
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            title="Security Breach Detected",
            description="Unauthorized access to sensitive data.",
            affected_entities=["user-1", "capsule-123"],
            detected_at=datetime.now(UTC),
            source="security_monitor",
        )

    @pytest.mark.asyncio
    async def test_respond_to_issue(self, service, mock_issue):
        """Test responding to a serious issue."""
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {"assessment": "Can be resolved.", "key_points": [], "confidence": 0.7},
                "balanced": {"assessment": "Serious but manageable.", "key_points": [], "confidence": 0.8},
                "critical": {"assessment": "Act quickly.", "key_points": [], "confidence": 0.9},
            },
            "synthesis": {
                "vote": "APPROVE",
                "reasoning": "Immediate action required.",
                "confidence": 0.85,
                "primary_benefits": ["security restored"],
                "primary_concerns": ["data exposure"],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            opinion = await service.respond_to_issue(mock_issue)

        assert opinion is not None
        assert opinion.proposal_id == f"issue_{mock_issue.id}"
        assert mock_issue.ghost_council_opinion is not None
        assert mock_issue.id in service._active_issues

    @pytest.mark.asyncio
    async def test_respond_to_issue_notifies_handlers(self, service, mock_issue):
        """Test that issue response notifies handlers."""
        handler_called = False
        received_issue = None

        def mock_handler(issue):
            nonlocal handler_called, received_issue
            handler_called = True
            received_issue = issue

        service.add_issue_handler(mock_handler)

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {"assessment": "Good", "key_points": [], "confidence": 0.7},
                "balanced": {"assessment": "OK", "key_points": [], "confidence": 0.7},
                "critical": {"assessment": "Risk", "key_points": [], "confidence": 0.7},
            },
            "synthesis": {
                "vote": "APPROVE",
                "reasoning": "Action.",
                "confidence": 0.7,
                "primary_benefits": [],
                "primary_concerns": [],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        with patch("forge.services.ghost_council.get_llm_service", return_value=mock_llm):
            await service.respond_to_issue(mock_issue)

        assert handler_called is True
        assert received_issue.id == mock_issue.id

    @pytest.mark.asyncio
    async def test_critical_issue_consensus_override(self, service):
        """Test that critical issues require unanimous rejection."""
        critical_issue = SeriousIssue(
            id="critical-issue",
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.CRITICAL,
            title="Critical Security Issue",
            description="Critical security breach detected.",
            affected_entities=[],
            detected_at=datetime.now(UTC),
            source="security",
        )

        # Create votes with split decision (not unanimous REJECT)
        votes = [
            GhostCouncilVote(
                member_id="gc_ethics",
                member_name="Sophia",
                member_role="Ethics Guardian",
                perspectives=[],
                vote=VoteChoice.REJECT,
                reasoning="Reject.",
                confidence=0.9,
                primary_benefits=[],
                primary_concerns=[],
            ),
            GhostCouncilVote(
                member_id="gc_security",
                member_name="Marcus",
                member_role="Security Sentinel",
                perspectives=[],
                vote=VoteChoice.APPROVE,  # Not unanimous
                reasoning="Approve.",
                confidence=0.8,
                primary_benefits=[],
                primary_concerns=[],
            ),
        ]

        result = service._calculate_issue_consensus(votes, critical_issue)

        # Should override to APPROVE (take action) for critical issues
        assert result["vote"] == VoteChoice.APPROVE
        assert "CRITICAL ISSUE" in result["recommendation"]


class TestIssueManagement:
    """Tests for issue management."""

    @pytest.fixture
    def service(self):
        return GhostCouncilService()

    def test_get_active_issues(self, service):
        """Test getting active issues."""
        issue1 = SeriousIssue(
            id="issue-1",
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            title="Issue 1",
            description="First issue",
            affected_entities=[],
            detected_at=datetime.now(UTC),
            source="test",
            resolved=False,
        )
        issue2 = SeriousIssue(
            id="issue-2",
            category=IssueCategory.TRUST,
            severity=IssueSeverity.MEDIUM,
            title="Issue 2",
            description="Second issue",
            affected_entities=[],
            detected_at=datetime.now(UTC),
            source="test",
            resolved=True,
        )

        service._active_issues["issue-1"] = issue1
        service._active_issues["issue-2"] = issue2

        active = service.get_active_issues()

        assert len(active) == 1
        assert active[0].id == "issue-1"

    def test_resolve_issue(self, service):
        """Test resolving an issue."""
        issue = SeriousIssue(
            id="issue-to-resolve",
            category=IssueCategory.SYSTEM,
            severity=IssueSeverity.HIGH,
            title="Resolvable Issue",
            description="Can be resolved",
            affected_entities=[],
            detected_at=datetime.now(UTC),
            source="test",
        )
        service._active_issues[issue.id] = issue

        result = service.resolve_issue(issue.id, "Fixed by admin")

        assert result is True
        assert issue.resolved is True
        assert issue.resolution == "Fixed by admin"

    def test_resolve_issue_not_found(self, service):
        """Test resolving non-existent issue."""
        result = service.resolve_issue("nonexistent", "Resolution")
        assert result is False


class TestStatistics:
    """Tests for statistics."""

    @pytest.fixture
    def service(self):
        return GhostCouncilService()

    def test_get_stats(self, service):
        """Test getting statistics."""
        # Add some data
        service._stats["proposals_reviewed"] = 10
        service._stats["issues_responded"] = 5

        issue = SeriousIssue(
            id="active-issue",
            category=IssueCategory.SECURITY,
            severity=IssueSeverity.HIGH,
            title="Active",
            description="Active issue",
            affected_entities=[],
            detected_at=datetime.now(UTC),
            source="test",
        )
        service._active_issues[issue.id] = issue

        stats = service.get_stats()

        assert stats["proposals_reviewed"] == 10
        assert stats["issues_responded"] == 5
        assert stats["active_issues"] == 1
        assert stats["total_issues_tracked"] == 1
        assert stats["council_members"] == len(service._members)


class TestMemberVoting:
    """Tests for member voting."""

    @pytest.fixture
    def service(self):
        config = GhostCouncilConfig(cache_enabled=False)
        return GhostCouncilService(config=config)

    @pytest.fixture
    def mock_proposal(self):
        return Proposal(
            id="vote-proposal",
            proposer_id="user-1",
            title="Vote Proposal",
            description="A proposal to test member voting functionality.",
            type=ProposalType.POLICY,
        )

    @pytest.mark.asyncio
    async def test_get_member_vote_valid_response(self, service, mock_proposal):
        """Test getting a valid member vote."""
        member = service._members[0]

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "perspectives": {
                "optimistic": {
                    "assessment": "Great opportunity.",
                    "key_points": ["opportunity 1", "opportunity 2"],
                    "confidence": 0.85,
                },
                "balanced": {
                    "assessment": "Fair trade-offs.",
                    "key_points": ["trade-off 1"],
                    "confidence": 0.8,
                },
                "critical": {
                    "assessment": "Minor risks.",
                    "key_points": ["risk 1"],
                    "confidence": 0.7,
                },
            },
            "synthesis": {
                "vote": "APPROVE",
                "reasoning": "Benefits outweigh concerns.",
                "confidence": 0.8,
                "primary_benefits": ["benefit 1", "benefit 2"],
                "primary_concerns": ["concern 1"],
            },
        })
        mock_llm.complete = AsyncMock(return_value=mock_response)

        vote = await service._get_member_vote(
            member=member,
            proposal=mock_proposal,
            context=None,
            constitutional_review=None,
            llm=mock_llm,
        )

        assert vote.member_id == member.id
        assert vote.vote == VoteChoice.APPROVE
        assert len(vote.perspectives) == 3
        assert vote.confidence == 0.8

    @pytest.mark.asyncio
    async def test_get_member_vote_llm_failure(self, service, mock_proposal):
        """Test member vote handling LLM failure."""
        member = service._members[0]

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        vote = await service._get_member_vote(
            member=member,
            proposal=mock_proposal,
            context=None,
            constitutional_review=None,
            llm=mock_llm,
        )

        assert vote.vote == VoteChoice.ABSTAIN
        assert vote.confidence == 0.0
        assert "Unable to complete analysis" in vote.reasoning


class TestGlobalFunctions:
    """Tests for global service functions."""

    def test_get_ghost_council_service_singleton(self):
        """Test getting singleton instance."""
        # Clear existing instance
        shutdown_ghost_council_service()

        service1 = get_ghost_council_service()
        service2 = get_ghost_council_service()

        assert service1 is service2

        # Clean up
        shutdown_ghost_council_service()

    def test_init_ghost_council_service(self):
        """Test initializing service with config."""
        shutdown_ghost_council_service()

        config = GhostCouncilConfig(profile="quick")
        service = init_ghost_council_service(config=config)

        assert service._config.profile == "quick"
        assert get_ghost_council_service() is service

        # Clean up
        shutdown_ghost_council_service()

    def test_shutdown_ghost_council_service(self):
        """Test shutting down service."""
        # Ensure service exists
        get_ghost_council_service()

        shutdown_ghost_council_service()

        # Should create new instance
        import forge.services.ghost_council as module
        assert module._ghost_council_service is None


class TestProperties:
    """Tests for service properties."""

    def test_members_property(self):
        """Test members property."""
        service = GhostCouncilService()
        members = service.members

        assert isinstance(members, list)
        assert len(members) > 0
        assert all(isinstance(m, GhostCouncilMember) for m in members)

    def test_config_property(self):
        """Test config property."""
        config = GhostCouncilConfig(profile="standard")
        service = GhostCouncilService(config=config)

        assert service.config is config
        assert service.config.profile == "standard"


class TestDefaultCouncilMembers:
    """Tests for default council members."""

    def test_default_members_exist(self):
        """Test that default council members are defined."""
        assert len(DEFAULT_COUNCIL_MEMBERS) > 0

    def test_default_members_have_required_fields(self):
        """Test that all default members have required fields."""
        for member in DEFAULT_COUNCIL_MEMBERS:
            assert member.id is not None
            assert member.name is not None
            assert member.role is not None
            assert member.persona is not None
            assert member.weight > 0

    def test_council_tiers_defined(self):
        """Test that council tiers are properly defined."""
        assert "quick" in COUNCIL_TIERS
        assert "standard" in COUNCIL_TIERS
        assert "comprehensive" in COUNCIL_TIERS

        # Quick should have fewer members than comprehensive
        assert len(COUNCIL_TIERS["quick"]) < len(COUNCIL_TIERS["comprehensive"])
