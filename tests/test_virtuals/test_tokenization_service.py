"""
Tests for Tokenization Service for Forge Entities.

This module tests the service that manages opt-in tokenization of Forge entities
using Virtuals Protocol's tokenization infrastructure.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.config import VirtualsEnvironment
from forge.virtuals.models.base import TokenInfo, TokenizationStatus
from forge.virtuals.models.tokenization import (
    GenesisTier,
    RevenueShare,
    TokenDistribution,
    TokenHolderGovernanceVote,
    TokenHolderProposal,
    TokenizationRequest,
    TokenizedEntity,
    TokenLaunchType,
)
from forge.virtuals.tokenization.service import (
    AlreadyTokenizedError,
    BlockchainConfigurationError,
    InsufficientStakeError,
    TokenizationService,
    TokenizationServiceError,
    get_tokenization_service,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_entity_repo():
    """Create a mock tokenized entity repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_entity_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_contribution_repo():
    """Create a mock contribution repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_entity = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_proposal_repo():
    """Create a mock proposal repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_config():
    """Create a mock Virtuals config."""
    config = MagicMock()
    config.environment = VirtualsEnvironment.LOCAL
    config.enable_tokenization = True
    config.enable_revenue_sharing = True
    config.enable_cross_chain = False
    config.agent_creation_fee = 100.0
    config.primary_chain = MagicMock(value="base")
    config.operator_private_key = None
    config.bonding_curve_address = None
    return config


@pytest.fixture
def mock_chain_manager():
    """Create a mock chain manager."""
    manager = MagicMock()
    manager.primary_client = MagicMock()
    manager.primary_client.chain = MagicMock(value="base")
    manager.initialize = AsyncMock()
    return manager


@pytest.fixture
def tokenization_service(
    mock_entity_repo, mock_contribution_repo, mock_proposal_repo, mock_config
):
    """Create a TokenizationService with mocked dependencies."""
    with patch(
        "forge.virtuals.tokenization.service.get_virtuals_config",
        return_value=mock_config,
    ):
        service = TokenizationService(
            mock_entity_repo,
            mock_contribution_repo,
            mock_proposal_repo,
        )
        return service


@pytest.fixture
def sample_tokenization_request():
    """Create a sample tokenization request."""
    return TokenizationRequest(
        entity_type="capsule",
        entity_id="capsule-123",
        token_name="Knowledge Capsule Token",
        token_symbol="KNCAP",
        token_description="Token for a knowledge capsule",
        initial_stake_virtual=100.0,
        owner_wallet="0x" + "1" * 40,
    )


@pytest.fixture
def sample_tokenized_entity():
    """Create a sample tokenized entity."""
    return TokenizedEntity(
        entity_type="capsule",
        entity_id="capsule-123",
        token_info=TokenInfo(
            token_address="0x" + "a" * 40,
            chain="base",
            symbol="KNCAP",
            name="Knowledge Capsule Token",
        ),
        launch_type=TokenLaunchType.STANDARD,
        distribution=TokenDistribution(),
        revenue_share=RevenueShare(),
        status=TokenizationStatus.BONDING,
        bonding_curve_virtual_accumulated=1000.0,
    )


# ==================== Initialization Tests ====================


class TestTokenizationServiceInit:
    """Tests for TokenizationService initialization."""

    def test_service_creation(
        self, mock_entity_repo, mock_contribution_repo, mock_proposal_repo, mock_config
    ):
        """Test creating a tokenization service."""
        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            service = TokenizationService(
                mock_entity_repo,
                mock_contribution_repo,
                mock_proposal_repo,
            )

            assert service._entity_repo == mock_entity_repo
            assert service._contribution_repo == mock_contribution_repo
            assert service._proposal_repo == mock_proposal_repo

    @pytest.mark.asyncio
    async def test_initialize(self, tokenization_service, mock_chain_manager):
        """Test service initialization."""
        with patch(
            "forge.virtuals.tokenization.service.get_chain_manager",
            AsyncMock(return_value=mock_chain_manager),
        ):
            await tokenization_service.initialize()

            assert tokenization_service._chain_manager == mock_chain_manager


# ==================== Request Tokenization Tests ====================


class TestRequestTokenization:
    """Tests for request_tokenization method."""

    @pytest.mark.asyncio
    async def test_request_tokenization_success(
        self,
        tokenization_service,
        sample_tokenization_request,
        mock_entity_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test successful tokenization request."""
        mock_entity_repo.get_by_entity_id = AsyncMock(return_value=None)
        tokenization_service._chain_manager = mock_chain_manager

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            result = await tokenization_service.request_tokenization(
                sample_tokenization_request
            )

            assert result is not None
            assert result.entity_type == "capsule"
            assert result.status == TokenizationStatus.BONDING
            mock_entity_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_tokenization_already_tokenized(
        self,
        tokenization_service,
        sample_tokenization_request,
        mock_entity_repo,
        sample_tokenized_entity,
    ):
        """Test error when entity is already tokenized."""
        mock_entity_repo.get_by_entity_id = AsyncMock(return_value=sample_tokenized_entity)

        with pytest.raises(AlreadyTokenizedError, match="already tokenized"):
            await tokenization_service.request_tokenization(sample_tokenization_request)

    @pytest.mark.asyncio
    async def test_request_tokenization_insufficient_stake(
        self, tokenization_service, mock_entity_repo
    ):
        """Test error when stake is below minimum."""
        mock_entity_repo.get_by_entity_id = AsyncMock(return_value=None)

        request = TokenizationRequest(
            entity_type="capsule",
            entity_id="capsule-123",
            token_name="Test Token",
            token_symbol="TEST",
            token_description="Test",
            initial_stake_virtual=50.0,  # Below minimum
            owner_wallet="0x" + "1" * 40,
        )

        with pytest.raises(InsufficientStakeError, match="Minimum stake"):
            await tokenization_service.request_tokenization(request)

    @pytest.mark.asyncio
    async def test_request_tokenization_disabled(
        self,
        tokenization_service,
        sample_tokenization_request,
        mock_entity_repo,
        mock_config,
    ):
        """Test error when tokenization is disabled."""
        mock_entity_repo.get_by_entity_id = AsyncMock(return_value=None)
        mock_config.enable_tokenization = False

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            tokenization_service.config = mock_config

            with pytest.raises(BlockchainConfigurationError, match="disabled"):
                await tokenization_service.request_tokenization(
                    sample_tokenization_request
                )

    @pytest.mark.asyncio
    async def test_request_tokenization_genesis_tier(
        self,
        tokenization_service,
        mock_entity_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test tokenization request with Genesis tier."""
        mock_entity_repo.get_by_entity_id = AsyncMock(return_value=None)
        tokenization_service._chain_manager = mock_chain_manager

        request = TokenizationRequest(
            entity_type="agent",
            entity_id="agent-456",
            token_name="Agent Token",
            token_symbol="AGNT",
            token_description="Agent governance token",
            launch_type=TokenLaunchType.GENESIS,
            genesis_tier=GenesisTier.TIER_1,
            initial_stake_virtual=200.0,
            owner_wallet="0x" + "1" * 40,
        )

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            result = await tokenization_service.request_tokenization(request)

            assert result.launch_type == TokenLaunchType.GENESIS
            assert result.genesis_tier == GenesisTier.TIER_1


# ==================== Contribute to Bonding Curve Tests ====================


class TestContributeToBondingCurve:
    """Tests for contribute_to_bonding_curve method."""

    @pytest.mark.asyncio
    async def test_contribute_success(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test successful bonding curve contribution."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)
        tokenization_service._chain_manager = mock_chain_manager

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            entity, contribution = await tokenization_service.contribute_to_bonding_curve(
                entity_id="entity-123",
                contributor_wallet="0x" + "2" * 40,
                amount_virtual=500.0,
            )

            assert entity.bonding_curve_virtual_accumulated == 1500.0
            assert contribution.amount_virtual == 500.0

    @pytest.mark.asyncio
    async def test_contribute_entity_not_found(
        self, tokenization_service, mock_entity_repo
    ):
        """Test error when entity not found."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TokenizationServiceError, match="not found"):
            await tokenization_service.contribute_to_bonding_curve(
                entity_id="nonexistent",
                contributor_wallet="0x" + "1" * 40,
                amount_virtual=100.0,
            )

    @pytest.mark.asyncio
    async def test_contribute_not_in_bonding_phase(
        self, tokenization_service, sample_tokenized_entity, mock_entity_repo
    ):
        """Test error when entity is not in bonding phase."""
        sample_tokenized_entity.status = TokenizationStatus.GRADUATED
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        with pytest.raises(TokenizationServiceError, match="not in bonding phase"):
            await tokenization_service.contribute_to_bonding_curve(
                entity_id="entity-123",
                contributor_wallet="0x" + "1" * 40,
                amount_virtual=100.0,
            )

    @pytest.mark.asyncio
    async def test_contribute_triggers_graduation(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test that contribution triggers graduation when threshold reached."""
        # Set accumulated close to threshold
        sample_tokenized_entity.bonding_curve_virtual_accumulated = 41500.0
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)
        tokenization_service._chain_manager = mock_chain_manager

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            entity, contribution = await tokenization_service.contribute_to_bonding_curve(
                entity_id="entity-123",
                contributor_wallet="0x" + "2" * 40,
                amount_virtual=1000.0,  # Pushes over 42K threshold
            )

            assert entity.status == TokenizationStatus.GRADUATED


# ==================== Distribute Revenue Tests ====================


class TestDistributeRevenue:
    """Tests for distribute_revenue method."""

    @pytest.mark.asyncio
    async def test_distribute_revenue_success(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_contribution_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test successful revenue distribution."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)
        mock_contribution_repo.get_by_entity = AsyncMock(return_value=[])
        tokenization_service._chain_manager = mock_chain_manager

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            distributions = await tokenization_service.distribute_revenue(
                entity_id="entity-123",
                revenue_amount_virtual=100.0,
                revenue_source="inference_fees",
            )

            assert "creator" in distributions
            assert "treasury" in distributions
            assert "buyback_burn" in distributions

    @pytest.mark.asyncio
    async def test_distribute_revenue_entity_not_found(
        self, tokenization_service, mock_entity_repo
    ):
        """Test error when entity not found."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TokenizationServiceError, match="not found"):
            await tokenization_service.distribute_revenue(
                entity_id="nonexistent",
                revenue_amount_virtual=100.0,
                revenue_source="test",
            )

    @pytest.mark.asyncio
    async def test_distribute_revenue_with_contributors(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_contribution_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test revenue distribution with contributors."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        # Mock contributors
        contributors = [
            MagicMock(contributor_wallet="0x" + "1" * 40, reward_share_percent=30.0),
            MagicMock(contributor_wallet="0x" + "2" * 40, reward_share_percent=70.0),
        ]
        mock_contribution_repo.get_by_entity = AsyncMock(return_value=contributors)
        tokenization_service._chain_manager = mock_chain_manager

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            distributions = await tokenization_service.distribute_revenue(
                entity_id="entity-123",
                revenue_amount_virtual=100.0,
                revenue_source="test",
            )

            # Should include contributor wallets
            assert "0x" + "1" * 40 in distributions or "0x" + "2" * 40 in distributions


# ==================== Create Governance Proposal Tests ====================


class TestCreateGovernanceProposal:
    """Tests for create_governance_proposal method."""

    @pytest.mark.asyncio
    async def test_create_proposal_success(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_proposal_repo,
    ):
        """Test successful proposal creation."""
        sample_tokenized_entity.enable_holder_governance = True
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        proposal = await tokenization_service.create_governance_proposal(
            entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Increase Revenue Share",
            description="Proposal to increase creator revenue share",
            proposal_type="parameter_change",
            proposed_changes={"creator_share_percent": 35.0},
        )

        assert proposal is not None
        assert proposal.title == "Increase Revenue Share"
        mock_proposal_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_entity_not_found(
        self, tokenization_service, mock_entity_repo
    ):
        """Test error when entity not found."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TokenizationServiceError, match="not found"):
            await tokenization_service.create_governance_proposal(
                entity_id="nonexistent",
                proposer_wallet="0x" + "1" * 40,
                title="Test",
                description="Test",
                proposal_type="test",
                proposed_changes={},
            )

    @pytest.mark.asyncio
    async def test_create_proposal_governance_disabled(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
    ):
        """Test error when governance is disabled."""
        sample_tokenized_entity.enable_holder_governance = False
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        with pytest.raises(TokenizationServiceError, match="not enabled"):
            await tokenization_service.create_governance_proposal(
                entity_id="entity-123",
                proposer_wallet="0x" + "1" * 40,
                title="Test",
                description="Test",
                proposal_type="test",
                proposed_changes={},
            )


# ==================== Cast Governance Vote Tests ====================


class TestCastGovernanceVote:
    """Tests for cast_governance_vote method."""

    @pytest.mark.asyncio
    async def test_cast_vote_for(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_proposal_repo,
    ):
        """Test casting a 'for' vote."""
        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Test Proposal",
            description="Test",
            proposal_type="parameter_change",
            proposed_changes={},
            voting_starts=now - timedelta(days=1),
            voting_ends=now + timedelta(days=6),
            quorum_required=10.0,
        )
        mock_proposal_repo.get_by_id = AsyncMock(return_value=proposal)
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        vote = await tokenization_service.cast_governance_vote(
            proposal_id="proposal-123",
            voter_wallet="0x" + "2" * 40,
            vote="for",
        )

        assert vote.vote == "for"
        assert proposal.votes_for > 0

    @pytest.mark.asyncio
    async def test_cast_vote_against(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_proposal_repo,
    ):
        """Test casting an 'against' vote."""
        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id="entity-123",
            proposer_wallet="0x" + "1" * 40,
            title="Test Proposal",
            description="Test",
            proposal_type="parameter_change",
            proposed_changes={},
            voting_starts=now - timedelta(days=1),
            voting_ends=now + timedelta(days=6),
            quorum_required=10.0,
        )
        mock_proposal_repo.get_by_id = AsyncMock(return_value=proposal)
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        vote = await tokenization_service.cast_governance_vote(
            proposal_id="proposal-123",
            voter_wallet="0x" + "2" * 40,
            vote="against",
        )

        assert vote.vote == "against"

    @pytest.mark.asyncio
    async def test_cast_vote_invalid_vote_type(
        self, tokenization_service, mock_proposal_repo
    ):
        """Test error for invalid vote type."""
        with pytest.raises(TokenizationServiceError, match="must be"):
            await tokenization_service.cast_governance_vote(
                proposal_id="proposal-123",
                voter_wallet="0x" + "1" * 40,
                vote="invalid",
            )

    @pytest.mark.asyncio
    async def test_cast_vote_proposal_not_found(
        self, tokenization_service, mock_proposal_repo
    ):
        """Test error when proposal not found."""
        mock_proposal_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TokenizationServiceError, match="not found"):
            await tokenization_service.cast_governance_vote(
                proposal_id="nonexistent",
                voter_wallet="0x" + "1" * 40,
                vote="for",
            )

    @pytest.mark.asyncio
    async def test_cast_vote_proposal_not_active(
        self, tokenization_service, mock_proposal_repo
    ):
        """Test error when proposal is not active."""
        proposal = MagicMock()
        proposal.status = "executed"
        mock_proposal_repo.get_by_id = AsyncMock(return_value=proposal)

        with pytest.raises(TokenizationServiceError, match="not active"):
            await tokenization_service.cast_governance_vote(
                proposal_id="proposal-123",
                voter_wallet="0x" + "1" * 40,
                vote="for",
            )


# ==================== Bridge Token Tests ====================


class TestBridgeToken:
    """Tests for bridge_token method."""

    @pytest.mark.asyncio
    async def test_bridge_token_success(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
        mock_config,
    ):
        """Test successful token bridge."""
        sample_tokenized_entity.status = TokenizationStatus.GRADUATED
        sample_tokenized_entity.is_multichain = True
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            result = await tokenization_service.bridge_token(
                entity_id="entity-123",
                destination_chain="ethereum",
                amount=1000.0,
                sender_wallet="0x" + "1" * 40,
                recipient_wallet="0x" + "2" * 40,
            )

            assert result["status"] == "pending"
            assert result["destination_chain"] == "ethereum"

    @pytest.mark.asyncio
    async def test_bridge_token_entity_not_found(
        self, tokenization_service, mock_entity_repo
    ):
        """Test error when entity not found."""
        mock_entity_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(TokenizationServiceError, match="not found"):
            await tokenization_service.bridge_token(
                entity_id="nonexistent",
                destination_chain="ethereum",
                amount=1000.0,
                sender_wallet="0x" + "1" * 40,
                recipient_wallet="0x" + "2" * 40,
            )

    @pytest.mark.asyncio
    async def test_bridge_token_multichain_disabled(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
    ):
        """Test error when multichain is disabled."""
        sample_tokenized_entity.is_multichain = False
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        with pytest.raises(TokenizationServiceError, match="not enabled"):
            await tokenization_service.bridge_token(
                entity_id="entity-123",
                destination_chain="ethereum",
                amount=1000.0,
                sender_wallet="0x" + "1" * 40,
                recipient_wallet="0x" + "2" * 40,
            )

    @pytest.mark.asyncio
    async def test_bridge_token_not_graduated(
        self,
        tokenization_service,
        sample_tokenized_entity,
        mock_entity_repo,
    ):
        """Test error when token is not graduated."""
        sample_tokenized_entity.is_multichain = True
        sample_tokenized_entity.status = TokenizationStatus.BONDING
        mock_entity_repo.get_by_id = AsyncMock(return_value=sample_tokenized_entity)

        with pytest.raises(TokenizationServiceError, match="graduated"):
            await tokenization_service.bridge_token(
                entity_id="entity-123",
                destination_chain="ethereum",
                amount=1000.0,
                sender_wallet="0x" + "1" * 40,
                recipient_wallet="0x" + "2" * 40,
            )


# ==================== Global Service Tests ====================


class TestGetTokenizationService:
    """Tests for get_tokenization_service function."""

    @pytest.mark.asyncio
    async def test_get_service_first_call(
        self,
        mock_entity_repo,
        mock_contribution_repo,
        mock_proposal_repo,
        mock_chain_manager,
        mock_config,
    ):
        """Test getting service on first call."""
        import forge.virtuals.tokenization.service as service_module

        service_module._tokenization_service = None

        with patch(
            "forge.virtuals.tokenization.service.get_virtuals_config",
            return_value=mock_config,
        ):
            with patch(
                "forge.virtuals.tokenization.service.get_chain_manager",
                AsyncMock(return_value=mock_chain_manager),
            ):
                service = await get_tokenization_service(
                    mock_entity_repo,
                    mock_contribution_repo,
                    mock_proposal_repo,
                )

                assert service is not None
                assert isinstance(service, TokenizationService)

        # Cleanup
        service_module._tokenization_service = None

    @pytest.mark.asyncio
    async def test_get_service_without_repos_on_first_call(self):
        """Test error when repos not provided on first call."""
        import forge.virtuals.tokenization.service as service_module

        service_module._tokenization_service = None

        with pytest.raises(TokenizationServiceError, match="Repositories required"):
            await get_tokenization_service()

        # Cleanup
        service_module._tokenization_service = None


# ==================== Exception Tests ====================


class TestExceptions:
    """Tests for custom exceptions."""

    def test_tokenization_service_error(self):
        """Test TokenizationServiceError."""
        error = TokenizationServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_insufficient_stake_error(self):
        """Test InsufficientStakeError."""
        error = InsufficientStakeError("Stake too low")
        assert isinstance(error, TokenizationServiceError)

    def test_already_tokenized_error(self):
        """Test AlreadyTokenizedError."""
        error = AlreadyTokenizedError("Already exists")
        assert isinstance(error, TokenizationServiceError)

    def test_blockchain_configuration_error(self):
        """Test BlockchainConfigurationError."""
        error = BlockchainConfigurationError("Config missing")
        assert isinstance(error, TokenizationServiceError)
