"""
Tests for Tokenization Models for Forge Entities.

This module tests the models for the opt-in tokenization of Forge entities
including Knowledge Capsules, Overlays, and Governance Proposals.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from forge.virtuals.models.tokenization import (
    BondingCurveContribution,
    ContributionRecord,
    GenesisTier,
    RevenueShare,
    TokenDistribution,
    TokenHolderGovernanceVote,
    TokenHolderProposal,
    TokenizableEntityType,
    TokenizationRequest,
    TokenizedEntity,
    TokenLaunchType,
)
from forge.virtuals.models.base import TokenInfo, TokenizationStatus


# ==================== TokenizableEntityType Tests ====================


class TestTokenizableEntityType:
    """Tests for TokenizableEntityType enum."""

    def test_all_entity_types(self):
        """Test all tokenizable entity types."""
        assert TokenizableEntityType.CAPSULE == "capsule"
        assert TokenizableEntityType.OVERLAY == "overlay"
        assert TokenizableEntityType.AGENT == "agent"
        assert TokenizableEntityType.CAPSULE_COLLECTION == "capsule_collection"
        assert TokenizableEntityType.GOVERNANCE_PROPOSAL == "governance_proposal"

    def test_entity_type_count(self):
        """Test number of entity types."""
        assert len(TokenizableEntityType) == 5


# ==================== TokenLaunchType Tests ====================


class TestTokenLaunchType:
    """Tests for TokenLaunchType enum."""

    def test_all_launch_types(self):
        """Test all launch types."""
        assert TokenLaunchType.STANDARD == "standard"
        assert TokenLaunchType.GENESIS == "genesis"


# ==================== GenesisTier Tests ====================


class TestGenesisTier:
    """Tests for GenesisTier enum."""

    def test_all_genesis_tiers(self):
        """Test all genesis tiers."""
        assert GenesisTier.TIER_1 == "tier_1"
        assert GenesisTier.TIER_2 == "tier_2"
        assert GenesisTier.TIER_3 == "tier_3"


# ==================== TokenDistribution Tests ====================


class TestTokenDistribution:
    """Tests for TokenDistribution model."""

    def test_distribution_defaults(self):
        """Test default distribution values."""
        dist = TokenDistribution()

        assert dist.public_circulation_percent == 60.0
        assert dist.ecosystem_treasury_percent == 35.0
        assert dist.liquidity_pool_percent == 5.0
        assert dist.creator_allocation_percent == 0.0

    def test_distribution_custom(self):
        """Test custom distribution."""
        dist = TokenDistribution(
            public_circulation_percent=50.0,
            ecosystem_treasury_percent=40.0,
            liquidity_pool_percent=5.0,
            creator_allocation_percent=5.0,
        )

        assert dist.public_circulation_percent == 50.0
        assert dist.creator_allocation_percent == 5.0

    def test_distribution_total_validation(self):
        """Test that total cannot exceed 100%."""
        with pytest.raises(ValidationError):
            TokenDistribution(
                public_circulation_percent=60.0,
                ecosystem_treasury_percent=35.0,
                liquidity_pool_percent=5.0,
                creator_allocation_percent=10.0,  # Total = 110%
            )


# ==================== RevenueShare Tests ====================


class TestRevenueShare:
    """Tests for RevenueShare model."""

    def test_revenue_share_defaults(self):
        """Test default revenue share values."""
        share = RevenueShare()

        assert share.creator_share_percent == 30.0
        assert share.contributor_share_percent == 20.0
        assert share.treasury_share_percent == 50.0
        assert share.buyback_burn_percent == 50.0

    def test_revenue_share_custom(self):
        """Test custom revenue share."""
        share = RevenueShare(
            creator_share_percent=40.0,
            contributor_share_percent=30.0,
            treasury_share_percent=30.0,
            buyback_burn_percent=75.0,
        )

        assert share.creator_share_percent == 40.0
        assert share.buyback_burn_percent == 75.0


# ==================== TokenizationRequest Tests ====================


class TestTokenizationRequest:
    """Tests for TokenizationRequest model."""

    def test_request_creation(self):
        """Test creating a tokenization request."""
        request = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-123",
            token_name="Knowledge Capsule Token",
            token_symbol="KNCAP",
            token_description="Token representing a knowledge capsule",
            initial_stake_virtual=100.0,
            owner_wallet="0x" + "1" * 40,
        )

        assert request.entity_type == "capsule"
        assert request.token_symbol == "KNCAP"
        assert request.launch_type == TokenLaunchType.STANDARD

    def test_request_genesis_launch(self):
        """Test request with genesis launch."""
        request = TokenizationRequest(
            entity_type="agent",
            entity_id="agent-456",
            token_name="Agent Token",
            token_symbol="AGNT",
            token_description="Agent governance token",
            launch_type=TokenLaunchType.GENESIS,
            genesis_tier=GenesisTier.TIER_2,
            initial_stake_virtual=500.0,
            owner_wallet="0x" + "1" * 40,
        )

        assert request.launch_type == TokenLaunchType.GENESIS
        assert request.genesis_tier == GenesisTier.TIER_2

    def test_request_symbol_uppercase(self):
        """Test symbol is uppercased."""
        request = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-123",
            token_name="Test Token",
            token_symbol="test",
            token_description="Test description",
            initial_stake_virtual=100.0,
            owner_wallet="0x" + "1" * 40,
        )

        assert request.token_symbol == "TEST"

    def test_request_symbol_alphanumeric(self):
        """Test symbol must be alphanumeric."""
        with pytest.raises(ValidationError):
            TokenizationRequest(
                entity_type="capsule",
                entity_id="capsule-123",
                token_name="Test Token",
                token_symbol="TEST-1",  # Invalid: contains dash
                token_description="Test",
                initial_stake_virtual=100.0,
                owner_wallet="0x" + "1" * 40,
            )

    def test_request_minimum_stake(self):
        """Test minimum stake validation."""
        with pytest.raises(ValidationError):
            TokenizationRequest(
                entity_type="capsule",
                entity_id="capsule-123",
                token_name="Test Token",
                token_symbol="TEST",
                token_description="Test",
                initial_stake_virtual=50.0,  # Below 100 minimum
                owner_wallet="0x" + "1" * 40,
            )

    def test_request_with_multichain(self):
        """Test request with multichain enabled."""
        request = TokenizationRequest(
            entity_type="overlay",
            entity_id="overlay-789",
            token_name="Overlay Token",
            token_symbol="OVLY",
            token_description="Multi-chain overlay token",
            initial_stake_virtual=1000.0,
            owner_wallet="0x" + "1" * 40,
            enable_multichain=True,
        )

        assert request.enable_multichain is True


# ==================== TokenizedEntity Tests ====================


class TestTokenizedEntity:
    """Tests for TokenizedEntity model."""

    def test_entity_creation(self):
        """Test creating a tokenized entity."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="capsule",
            entity_id="capsule-123",
            token_info=token_info,
            launch_type=TokenLaunchType.STANDARD,
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
        )

        assert entity.entity_type == "capsule"
        assert entity.status == TokenizationStatus.PENDING

    def test_entity_is_graduated_false(self):
        """Test is_graduated for non-graduated entity."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="agent",
            entity_id="agent-123",
            token_info=token_info,
            launch_type=TokenLaunchType.STANDARD,
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
            status=TokenizationStatus.BONDING,
        )

        assert entity.is_graduated() is False

    def test_entity_is_graduated_true(self):
        """Test is_graduated for graduated entity."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="agent",
            entity_id="agent-123",
            token_info=token_info,
            launch_type=TokenLaunchType.STANDARD,
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
            status=TokenizationStatus.GRADUATED,
        )

        assert entity.is_graduated() is True

    def test_graduation_progress_standard(self):
        """Test graduation progress for standard launch."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="capsule",
            entity_id="capsule-123",
            token_info=token_info,
            launch_type="standard",
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
            bonding_curve_virtual_accumulated=21000.0,
        )

        progress = entity.graduation_progress()
        assert progress == 0.5  # 21000 / 42000

    def test_graduation_progress_tier_1(self):
        """Test graduation progress for Genesis Tier 1."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="agent",
            entity_id="agent-123",
            token_info=token_info,
            launch_type="genesis",
            genesis_tier=GenesisTier.TIER_1,
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
            bonding_curve_virtual_accumulated=21000.0,
        )

        progress = entity.graduation_progress()
        assert progress == 1.0  # Reached threshold

    def test_graduation_progress_tier_3(self):
        """Test graduation progress for Genesis Tier 3."""
        token_info = TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="TEST",
            name="Test Token",
        )

        entity = TokenizedEntity(
            entity_type="overlay",
            entity_id="overlay-123",
            token_info=token_info,
            launch_type="genesis",
            genesis_tier=GenesisTier.TIER_3,
            distribution=TokenDistribution(),
            revenue_share=RevenueShare(),
            bonding_curve_virtual_accumulated=50000.0,
        )

        progress = entity.graduation_progress()
        assert progress == 0.5  # 50000 / 100000


# ==================== ContributionRecord Tests ====================


class TestContributionRecord:
    """Tests for ContributionRecord model."""

    def test_contribution_creation(self):
        """Test creating a contribution record."""
        contribution = ContributionRecord(
            tokenized_entity_id="entity-123",
            contributor_wallet="0x" + "1" * 40,
            contribution_type="data",
            contribution_description="Added new knowledge data",
            contribution_hash="abc123hash",
        )

        assert contribution.contribution_type == "data"
        assert contribution.is_approved is False
        assert contribution.reward_share_percent == 0.0

    def test_contribution_approved(self):
        """Test approved contribution."""
        contribution = ContributionRecord(
            tokenized_entity_id="entity-123",
            contributor_wallet="0x" + "1" * 40,
            contribution_type="code",
            contribution_description="Improved model",
            contribution_hash="def456hash",
            validated_by="evaluator-agent",
            validation_score=0.9,
            is_approved=True,
            reward_share_percent=5.0,
            approved_at=datetime.now(UTC),
        )

        assert contribution.is_approved is True
        assert contribution.reward_share_percent == 5.0
        assert contribution.validation_score == 0.9

    def test_contribution_with_nft(self):
        """Test contribution with NFT representation."""
        contribution = ContributionRecord(
            tokenized_entity_id="entity-123",
            contributor_wallet="0x" + "1" * 40,
            contribution_type="curation",
            contribution_description="Curated content",
            contribution_hash="ghi789hash",
            contribution_nft_id="nft-123",
            contribution_nft_tx_hash="0x" + "f" * 64,
        )

        assert contribution.contribution_nft_id == "nft-123"


# ==================== TokenHolderGovernanceVote Tests ====================


class TestTokenHolderGovernanceVote:
    """Tests for TokenHolderGovernanceVote model."""

    def test_vote_for(self):
        """Test vote for a proposal."""
        vote = TokenHolderGovernanceVote(
            voter_wallet="0x" + "1" * 40,
            tokenized_entity_id="entity-123",
            proposal_id="proposal-456",
            vote="for",
            voting_power=1000.0,
        )

        assert vote.vote == "for"
        assert vote.voting_power == 1000.0

    def test_vote_against(self):
        """Test vote against a proposal."""
        vote = TokenHolderGovernanceVote(
            voter_wallet="0x" + "2" * 40,
            tokenized_entity_id="entity-123",
            proposal_id="proposal-456",
            vote="against",
            voting_power=500.0,
        )

        assert vote.vote == "against"

    def test_vote_abstain(self):
        """Test abstain vote."""
        vote = TokenHolderGovernanceVote(
            voter_wallet="0x" + "3" * 40,
            tokenized_entity_id="entity-123",
            proposal_id="proposal-456",
            vote="abstain",
            voting_power=250.0,
        )

        assert vote.vote == "abstain"

    def test_vote_with_tx_hash(self):
        """Test vote with transaction hash."""
        vote = TokenHolderGovernanceVote(
            voter_wallet="0x" + "1" * 40,
            tokenized_entity_id="entity-123",
            proposal_id="proposal-456",
            vote="for",
            voting_power=1000.0,
            tx_hash="0x" + "a" * 64,
        )

        assert vote.tx_hash is not None


# ==================== TokenHolderProposal Tests ====================


class TestTokenHolderProposal:
    """Tests for TokenHolderProposal model."""

    def test_proposal_creation(self):
        """Test creating a governance proposal."""
        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Increase Revenue Share",
            description="Proposal to increase creator revenue share from 30% to 35%",
            proposal_type="parameter_change",
            proposed_changes={"creator_share_percent": 35.0},
            voting_starts=now,
            voting_ends=now + timedelta(days=7),
            quorum_required=10.0,
        )

        assert proposal.title == "Increase Revenue Share"
        assert proposal.status == "active"
        assert proposal.votes_for == 0.0

    def test_proposal_with_votes(self):
        """Test proposal with votes."""
        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Treasury Allocation",
            description="Allocate 10K VIRTUAL from treasury",
            proposal_type="treasury_allocation",
            proposed_changes={"amount": 10000, "recipient": "development"},
            voting_starts=now - timedelta(days=3),
            voting_ends=now + timedelta(days=4),
            quorum_required=10.0,
            votes_for=50000.0,
            votes_against=10000.0,
            votes_abstain=5000.0,
            total_voters=150,
            quorum_reached=True,
        )

        assert proposal.votes_for == 50000.0
        assert proposal.quorum_reached is True
        assert proposal.total_voters == 150

    def test_proposal_executed(self):
        """Test executed proposal."""
        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Executed Proposal",
            description="A proposal that has been executed",
            proposal_type="parameter_change",
            proposed_changes={"fee_rate": 0.02},
            voting_starts=now - timedelta(days=10),
            voting_ends=now - timedelta(days=3),
            quorum_required=10.0,
            status="executed",
            execution_tx_hash="0x" + "e" * 64,
            executed_at=now - timedelta(days=1),
        )

        assert proposal.status == "executed"
        assert proposal.execution_tx_hash is not None


# ==================== BondingCurveContribution Tests ====================


class TestBondingCurveContribution:
    """Tests for BondingCurveContribution model."""

    def test_contribution_creation(self):
        """Test creating a bonding curve contribution."""
        contribution = BondingCurveContribution(
            contributor_wallet="0x" + "1" * 40,
            tokenized_entity_id="entity-123",
            amount_virtual=1000.0,
            tokens_received=100000.0,
            price_at_contribution=0.01,
            tx_hash="0x" + "b" * 64,
        )

        assert contribution.amount_virtual == 1000.0
        assert contribution.tokens_received == 100000.0
        assert contribution.price_at_contribution == 0.01

    def test_contribution_timestamp(self):
        """Test contribution has timestamp."""
        contribution = BondingCurveContribution(
            contributor_wallet="0x" + "2" * 40,
            tokenized_entity_id="entity-456",
            amount_virtual=500.0,
            tokens_received=40000.0,
            price_at_contribution=0.0125,
            tx_hash="0x" + "c" * 64,
        )

        assert contribution.contributed_at is not None
