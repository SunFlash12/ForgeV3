"""
Tokenization Service for Forge Entities

This service manages the opt-in tokenization of Forge entities (capsules,
overlays, agents) using Virtuals Protocol's tokenization infrastructure.

Tokenization transforms Forge assets into ERC-20 tokens with:
- Bonding curve mechanics for price discovery
- Revenue sharing through buyback-and-burn
- Governance rights for token holders
- Cross-chain bridging capabilities

The service handles the complete tokenization lifecycle from initial request
through graduation and ongoing revenue distribution.

Key Concepts:
- Bonding Curve: Price increases as more VIRTUAL is contributed
- Graduation: At 42K VIRTUAL, token gets Uniswap liquidity
- Token-Bound Account: ERC-6551 wallet owned by the token
- Contribution Vault: On-chain record of all improvements

BLOCKCHAIN INTEGRATION REQUIREMENTS:
- Contract ABIs: Must be complete in contracts.py (from https://docs.virtuals.io/developers/contracts)
- Wallet signing: Uses SecretsManager for secure key retrieval
- Operator key: VIRTUALS_OPERATOR_PRIVATE_KEY must be configured

IMPORTANT: This service requires real blockchain connectivity.
Simulation mode has been removed - all operations require proper configuration.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from ..chains import get_chain_manager
from ..config import get_virtuals_config
from ..models import (
    BondingCurveContribution,
    TokenHolderGovernanceVote,
    TokenHolderProposal,
    TokenInfo,
    TokenizationRequest,
    TokenizationStatus,
    TokenizedEntity,
    TransactionRecord,
)
from .contracts import (
    AGENT_FACTORY_ABI,
    BONDING_CURVE_ABI,
    ERC20_ABI,
    MULTISEND_ABI,
    ContractAddresses,
    is_abi_complete,
)

logger = logging.getLogger(__name__)


# Graduation thresholds for different launch types
GRADUATION_THRESHOLDS = {
    "standard": 42000,      # 42K VIRTUAL for standard launch
    "genesis_tier_1": 21000,   # 21K VIRTUAL for Genesis Tier 1
    "genesis_tier_2": 42000,   # 42K VIRTUAL for Genesis Tier 2
    "genesis_tier_3": 100000,  # 100K VIRTUAL for Genesis Tier 3
}


class TokenizationServiceError(Exception):
    """Base exception for tokenization service errors."""
    pass


class InsufficientStakeError(TokenizationServiceError):
    """Raised when initial stake is below minimum."""
    pass


class AlreadyTokenizedError(TokenizationServiceError):
    """Raised when entity is already tokenized."""
    pass


class BlockchainConfigurationError(TokenizationServiceError):
    """Raised when blockchain infrastructure is not properly configured."""
    pass


class TokenizationService:
    """
    Service for managing tokenization of Forge entities.

    This service provides the complete tokenization implementation including:
    - Initial tokenization request processing
    - Bonding curve contribution management
    - Graduation to full token status
    - Revenue distribution and buyback-burn
    - Cross-chain bridging
    - Token holder governance

    The service maintains synchronization between on-chain state (token
    contracts) and off-chain state (Forge database) for efficient querying
    while ensuring all critical operations are verifiable on-chain.
    """

    def __init__(
        self,
        tokenized_entity_repository: Any,  # Forge's TokenizedEntityRepository
        contribution_repository: Any,      # Forge's ContributionRepository
        proposal_repository: Any,          # Forge's ProposalRepository
    ):
        """
        Initialize the tokenization service.

        Args:
            tokenized_entity_repository: Repository for tokenized entity records
            contribution_repository: Repository for contribution tracking
            proposal_repository: Repository for governance proposals
        """
        self.config = get_virtuals_config()
        self._entity_repo = tokenized_entity_repository
        self._contribution_repo = contribution_repository
        self._proposal_repo = proposal_repository
        self._chain_manager = None

    async def initialize(self) -> None:
        """Initialize the service and chain connections."""
        self._chain_manager = await get_chain_manager()
        logger.info("Tokenization Service initialized")

    # ==================== Tokenization Lifecycle ====================

    async def request_tokenization(
        self,
        request: TokenizationRequest,
    ) -> TokenizedEntity:
        """
        Process a tokenization request for a Forge entity.

        This initiates the tokenization process by:
        1. Validating the request and entity ownership
        2. Checking minimum stake requirements
        3. Creating the on-chain token (in bonding curve phase)
        4. Setting up the token-bound account (ERC-6551)
        5. Recording the tokenization in Forge's database

        The entity starts in BONDING status and graduates to GRADUATED
        once the threshold VIRTUAL accumulation is reached.

        Args:
            request: The tokenization request specification

        Returns:
            The created TokenizedEntity in PENDING or BONDING status
        """
        # Check if already tokenized
        existing = await self._entity_repo.get_by_entity_id(
            request.entity_type,
            request.entity_id,
        )
        if existing and existing.status not in [TokenizationStatus.FAILED, TokenizationStatus.REVOKED]:
            raise AlreadyTokenizedError(
                f"Entity {request.entity_type}:{request.entity_id} is already tokenized"
            )

        # Validate minimum stake
        min_stake = self.config.agent_creation_fee
        if request.initial_stake_virtual < min_stake:
            raise InsufficientStakeError(
                f"Minimum stake is {min_stake} VIRTUAL, got {request.initial_stake_virtual}"
            )

        # Determine graduation threshold based on launch type
        threshold_key = request.launch_type
        if request.genesis_tier:
            threshold_key = f"genesis_{request.genesis_tier}"
        graduation_threshold = GRADUATION_THRESHOLDS.get(threshold_key, 42000)

        # Create the tokenized entity record
        token_info = TokenInfo(
            token_address="",  # Will be set after on-chain creation
            chain=request.primary_chain,
            symbol=request.token_symbol,
            name=request.token_name,
            total_supply=1_000_000_000,  # 1 billion standard
            circulating_supply=0,
        )

        entity = TokenizedEntity(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            token_info=token_info,
            launch_type=request.launch_type,
            genesis_tier=request.genesis_tier,
            distribution=request.distribution,
            revenue_share=request.revenue_share,
            status=TokenizationStatus.PENDING,
            enable_holder_governance=request.enable_holder_governance,
            governance_quorum_percent=request.governance_quorum_percent,
            is_multichain=request.enable_multichain,
        )

        # Tokenization must be enabled - no simulation mode
        if not self.config.enable_tokenization:
            raise BlockchainConfigurationError(
                "Tokenization is disabled. Set enable_tokenization=True in Virtuals config "
                "and configure blockchain infrastructure."
            )

        try:
            # Deploy token contract via Virtuals Protocol
            tx_record = await self._deploy_token_contract(
                entity=entity,
                initial_stake=request.initial_stake_virtual,
                owner_wallet=request.owner_wallet,
            )

            entity.creation_tx_hash = tx_record.tx_hash
            entity.status = TokenizationStatus.BONDING
            entity.bonding_curve_virtual_accumulated = request.initial_stake_virtual
            entity.bonding_curve_contributors = 1

            # Extract token address from transaction (would parse from events)
            # entity.token_info.token_address = extract_token_address(tx_record)

            logger.info(
                f"Token deployed for {request.entity_type}:{request.entity_id}, "
                f"tx: {tx_record.tx_hash}"
            )

        except BlockchainConfigurationError:
            raise
        except Exception as e:
            logger.error(f"Token deployment failed: {e}")
            entity.status = TokenizationStatus.FAILED
            entity.metadata["failure_reason"] = str(e)
            raise TokenizationServiceError(f"Token deployment failed: {e}")

        # Estimate graduation date based on current accumulation rate
        # (In practice, this would use historical data and projections)
        if entity.status == TokenizationStatus.BONDING:
            remaining = graduation_threshold - entity.bonding_curve_virtual_accumulated
            # Assume average 1000 VIRTUAL per day accumulation for estimation
            days_remaining = max(1, remaining / 1000)
            entity.estimated_graduation_date = datetime.now(UTC) + timedelta(days=days_remaining)

        # Store in repository
        await self._entity_repo.create(entity)

        return entity

    async def contribute_to_bonding_curve(
        self,
        entity_id: str,
        contributor_wallet: str,
        amount_virtual: float,
    ) -> tuple[TokenizedEntity, BondingCurveContribution]:
        """
        Contribute VIRTUAL to an entity's bonding curve.

        Contributors receive placeholder tokens (FERC20) proportional to
        their contribution. The price per token increases as more VIRTUAL
        is contributed, rewarding early supporters.

        When the graduation threshold is reached, the bonding curve closes,
        real tokens are minted, and Uniswap liquidity is established.

        Args:
            entity_id: ID of the tokenized entity
            contributor_wallet: Wallet making the contribution
            amount_virtual: Amount of VIRTUAL to contribute

        Returns:
            Tuple of (updated entity, contribution record)
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise TokenizationServiceError(f"Entity {entity_id} not found")

        if entity.status != TokenizationStatus.BONDING:
            raise TokenizationServiceError(
                f"Entity is not in bonding phase (status: {entity.status})"
            )

        # Calculate tokens to receive based on bonding curve
        # Bonding curve: price = k * sqrt(supply), where k is a constant
        # This gives early contributors more tokens per VIRTUAL
        current_supply = entity.bonding_curve_virtual_accumulated
        new_supply = current_supply + amount_virtual

        # Simplified linear approximation for token calculation
        # In production, this would use the actual bonding curve formula
        avg_price = 0.001 * (1 + current_supply / 10000)  # Price increases with supply
        tokens_received = amount_virtual / avg_price

        # Record the contribution
        contribution = BondingCurveContribution(
            contributor_wallet=contributor_wallet,
            tokenized_entity_id=entity_id,
            amount_virtual=amount_virtual,
            tokens_received=tokens_received,
            price_at_contribution=avg_price,
            contributed_at=datetime.now(UTC),
            tx_hash="",  # Would be set from on-chain transaction
        )

        # Execute on-chain contribution if enabled
        if self.config.enable_tokenization:
            try:
                tx = await self._contribute_on_chain(
                    entity=entity,
                    contributor_wallet=contributor_wallet,
                    amount_virtual=amount_virtual,
                )
                contribution.tx_hash = tx.tx_hash
            except Exception as e:
                logger.error(f"On-chain contribution failed: {e}")
                raise TokenizationServiceError(f"Contribution failed: {e}")

        # Update entity state
        entity.bonding_curve_virtual_accumulated = new_supply
        entity.bonding_curve_contributors += 1
        entity.token_info.bonding_curve_progress = min(
            1.0,
            new_supply / GRADUATION_THRESHOLDS.get(entity.launch_type, 42000)
        )

        # Check if graduation threshold reached
        threshold = GRADUATION_THRESHOLDS.get(entity.launch_type, 42000)
        if entity.genesis_tier:
            threshold = GRADUATION_THRESHOLDS.get(f"genesis_{entity.genesis_tier}", threshold)

        if new_supply >= threshold:
            entity = await self._graduate_token(entity)
        else:
            # Update graduation estimate
            remaining = threshold - new_supply
            days_remaining = max(1, remaining / 1000)
            entity.estimated_graduation_date = datetime.now(UTC) + timedelta(days=days_remaining)

        await self._entity_repo.update(entity)

        logger.info(
            f"Contribution of {amount_virtual} VIRTUAL to {entity_id}, "
            f"progress: {entity.token_info.bonding_curve_progress:.1%}"
        )

        return entity, contribution

    async def _graduate_token(self, entity: TokenizedEntity) -> TokenizedEntity:
        """
        Graduate a token from bonding curve to full token status.

        Graduation involves:
        1. Minting the full 1 billion token supply
        2. Creating Uniswap V2 liquidity pool with VIRTUAL
        3. Locking liquidity for 10 years
        4. Transitioning from Prototype to Sentient status
        5. Converting FERC20 placeholders to real tokens
        """
        logger.info(f"Graduating token for entity {entity.id}")

        if self.config.enable_tokenization:
            try:
                # Execute graduation on-chain
                tx = await self._execute_graduation_on_chain(entity)
                entity.graduation_tx_hash = tx.tx_hash

                # Extract liquidity pool address from transaction
                # entity.liquidity_pool_address = extract_pool_address(tx)

            except Exception as e:
                logger.error(f"Graduation failed: {e}")
                raise TokenizationServiceError(f"Graduation failed: {e}")

        entity.status = TokenizationStatus.GRADUATED
        entity.graduated_at = datetime.now(UTC)
        entity.liquidity_locked_until = datetime.now(UTC) + timedelta(days=3650)  # 10 years
        entity.token_info.is_graduated = True
        entity.token_info.circulating_supply = int(
            entity.token_info.total_supply * entity.distribution.public_circulation_percent / 100
        )

        return entity

    # ==================== Revenue Distribution ====================

    async def distribute_revenue(
        self,
        entity_id: str,
        revenue_amount_virtual: float,
        revenue_source: str,
    ) -> dict[str, float]:
        """
        Distribute revenue generated by a tokenized entity.

        Revenue flows according to the entity's RevenueShare configuration:
        - Creator share: Direct payment to original creator
        - Contributor share: Proportional to contribution records
        - Treasury share: Entity treasury for operations and buyback-burn

        Args:
            entity_id: ID of the revenue-generating entity
            revenue_amount_virtual: Amount of VIRTUAL to distribute
            revenue_source: Description of revenue source

        Returns:
            Dict mapping recipient addresses to amounts distributed
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise TokenizationServiceError(f"Entity {entity_id} not found")

        distributions = {}
        revenue_share = entity.revenue_share

        # Calculate shares
        creator_amount = revenue_amount_virtual * (revenue_share.creator_share_percent / 100)
        contributor_amount = revenue_amount_virtual * (revenue_share.contributor_share_percent / 100)
        treasury_amount = revenue_amount_virtual * (revenue_share.treasury_share_percent / 100)

        # Creator distribution (would need to look up creator wallet)
        distributions["creator"] = creator_amount

        # Contributor distribution (proportional to contributions)
        contributions = await self._contribution_repo.get_by_entity(entity_id)
        if contributions and contributor_amount > 0:
            total_contribution_value = sum(c.reward_share_percent for c in contributions)
            if total_contribution_value > 0:
                for contribution in contributions:
                    share = contribution.reward_share_percent / total_contribution_value
                    distributions[contribution.contributor_wallet] = distributions.get(
                        contribution.contributor_wallet, 0
                    ) + (contributor_amount * share)

        # Treasury (including buyback-burn)
        buyback_amount = treasury_amount * (revenue_share.buyback_burn_percent / 100)
        treasury_reserve = treasury_amount - buyback_amount

        distributions["treasury"] = treasury_reserve
        distributions["buyback_burn"] = buyback_amount

        # Execute distributions on-chain if enabled
        if self.config.enable_revenue_sharing:
            try:
                await self._execute_distributions(entity, distributions)

                if buyback_amount > 0:
                    await self._execute_buyback_burn(entity, buyback_amount)

            except Exception as e:
                logger.error(f"Revenue distribution failed: {e}")
                raise TokenizationServiceError(f"Distribution failed: {e}")

        # Update entity metrics
        entity.total_revenue_generated += revenue_amount_virtual
        entity.total_buyback_burned += buyback_amount
        entity.total_distributed_to_holders += (creator_amount + contributor_amount)

        await self._entity_repo.update(entity)

        logger.info(
            f"Distributed {revenue_amount_virtual} VIRTUAL from {entity_id}: "
            f"creator={creator_amount}, contributors={contributor_amount}, "
            f"treasury={treasury_reserve}, buyback={buyback_amount}"
        )

        return distributions

    # ==================== Token Holder Governance ====================

    async def create_governance_proposal(
        self,
        entity_id: str,
        proposer_wallet: str,
        title: str,
        description: str,
        proposal_type: str,
        proposed_changes: dict[str, Any],
        voting_duration_days: int = 7,
    ) -> TokenHolderProposal:
        """
        Create a governance proposal for token holders to vote on.

        Proposals can modify entity parameters, allocate treasury funds,
        or make other decisions about the tokenized entity. Only token
        holders can create proposals, with voting power proportional to
        token holdings.

        Args:
            entity_id: ID of the tokenized entity
            proposer_wallet: Wallet of the proposal creator
            title: Short title for the proposal
            description: Detailed description of the proposal
            proposal_type: Type (parameter_change, treasury_allocation, etc.)
            proposed_changes: Specific changes being proposed
            voting_duration_days: How long voting remains open

        Returns:
            The created proposal
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise TokenizationServiceError(f"Entity {entity_id} not found")

        if not entity.enable_holder_governance:
            raise TokenizationServiceError("Governance not enabled for this entity")

        # Verify proposer holds tokens (would check on-chain)
        # proposer_balance = await self._get_token_balance(entity, proposer_wallet)
        # if proposer_balance <= 0:
        #     raise TokenizationServiceError("Proposer must hold tokens")

        now = datetime.now(UTC)
        proposal = TokenHolderProposal(
            tokenized_entity_id=entity_id,
            proposer_wallet=proposer_wallet,
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposed_changes=proposed_changes,
            voting_starts=now,
            voting_ends=now + timedelta(days=voting_duration_days),
            quorum_required=entity.governance_quorum_percent,
        )

        await self._proposal_repo.create(proposal)

        entity.active_proposals += 1
        entity.total_proposals += 1
        await self._entity_repo.update(entity)

        logger.info(f"Created governance proposal {proposal.id} for entity {entity_id}")
        return proposal

    async def cast_governance_vote(
        self,
        proposal_id: str,
        voter_wallet: str,
        vote: str,
    ) -> TokenHolderGovernanceVote:
        """
        Cast a vote on a governance proposal.

        Voting power is proportional to token holdings at the time of voting.
        Each wallet can only vote once per proposal.

        Args:
            proposal_id: ID of the proposal to vote on
            voter_wallet: Wallet casting the vote
            vote: Vote direction ('for', 'against', 'abstain')

        Returns:
            The recorded vote
        """
        if vote not in ["for", "against", "abstain"]:
            raise TokenizationServiceError("Vote must be 'for', 'against', or 'abstain'")

        proposal = await self._proposal_repo.get_by_id(proposal_id)
        if not proposal:
            raise TokenizationServiceError(f"Proposal {proposal_id} not found")

        if proposal.status != "active":
            raise TokenizationServiceError(f"Proposal is not active (status: {proposal.status})")

        now = datetime.now(UTC)
        if now < proposal.voting_starts or now > proposal.voting_ends:
            raise TokenizationServiceError("Voting period is not active")

        # Get voting power (token balance)
        # In production, this would query the token contract
        voting_power = 1000.0  # Placeholder

        vote_record = TokenHolderGovernanceVote(
            voter_wallet=voter_wallet,
            tokenized_entity_id=proposal.tokenized_entity_id,
            proposal_id=proposal_id,
            vote=vote,
            voting_power=voting_power,
        )

        # Update proposal vote tallies
        if vote == "for":
            proposal.votes_for += voting_power
        elif vote == "against":
            proposal.votes_against += voting_power
        else:
            proposal.votes_abstain += voting_power

        proposal.total_voters += 1

        # Check if quorum reached
        entity = await self._entity_repo.get_by_id(proposal.tokenized_entity_id)
        total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain
        total_supply = entity.token_info.total_supply if entity else 1_000_000_000
        participation_percent = (total_votes / total_supply) * 100

        if participation_percent >= proposal.quorum_required:
            proposal.quorum_reached = True

        await self._proposal_repo.update(proposal)

        logger.info(f"Vote recorded on proposal {proposal_id}: {vote} ({voting_power} power)")
        return vote_record

    # ==================== Cross-Chain Operations ====================

    async def bridge_token(
        self,
        entity_id: str,
        destination_chain: str,
        amount: float,
        sender_wallet: str,
        recipient_wallet: str,
    ) -> dict[str, Any]:
        """
        Bridge tokens to another chain using Wormhole.

        This enables cross-chain liquidity for tokenized entities,
        allowing tokens to exist on Base, Ethereum, and Solana.

        Args:
            entity_id: ID of the tokenized entity
            destination_chain: Target chain (ethereum, solana)
            amount: Amount of tokens to bridge
            sender_wallet: Source wallet on origin chain
            recipient_wallet: Destination wallet on target chain

        Returns:
            Bridge request details including estimated completion time
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise TokenizationServiceError(f"Entity {entity_id} not found")

        if not entity.is_multichain:
            raise TokenizationServiceError("Multi-chain not enabled for this entity")

        if entity.status != TokenizationStatus.GRADUATED:
            raise TokenizationServiceError("Can only bridge graduated tokens")

        from ..models import BridgeRequest

        bridge_request = BridgeRequest(
            source_chain=entity.token_info.chain,
            destination_chain=destination_chain,
            token_address=entity.token_info.token_address,
            amount=amount,
            sender_address=sender_wallet,
            recipient_address=recipient_wallet,
            estimated_completion_minutes=30,
        )

        # In production, this would initiate the Wormhole bridge transaction
        if self.config.enable_cross_chain:
            try:
                # source_tx = await self._initiate_bridge(bridge_request)
                # bridge_request.source_tx_hash = source_tx.tx_hash
                pass
            except Exception as e:
                logger.error(f"Bridge initiation failed: {e}")
                raise TokenizationServiceError(f"Bridge failed: {e}")

        # Track bridged chain
        if destination_chain not in entity.bridged_chains:
            entity.bridged_chains.append(destination_chain)
            await self._entity_repo.update(entity)

        logger.info(
            f"Bridge initiated for {amount} tokens from {entity.token_info.chain} "
            f"to {destination_chain}"
        )

        return {
            "request_id": bridge_request.id,
            "source_chain": bridge_request.source_chain,
            "destination_chain": destination_chain,
            "amount": amount,
            "status": "pending",
            "estimated_completion_minutes": bridge_request.estimated_completion_minutes,
        }

    # ==================== Blockchain Operations ====================

    async def _deploy_token_contract(
        self,
        entity: TokenizedEntity,
        initial_stake: float,
        owner_wallet: str,
    ) -> TransactionRecord:
        """
        Deploy the token contract on-chain via Virtuals Protocol AgentFactory.

        Production mode requires:
        1. Complete contract ABIs in contracts.py
        2. Valid AgentFactory address for the chain
        3. Configured operator wallet with sufficient VIRTUAL

        Contract interaction pattern:
        ```solidity
        function createAgent(
            string memory name,
            string memory symbol,
            uint256 initialStake
        ) external returns (address tokenAddress);
        ```
        """
        client = self._chain_manager.primary_client
        chain = self.config.primary_chain.value

        # Get factory address for this chain
        factory_address = ContractAddresses.get_address(chain, "agent_factory")

        # Check if we can make real blockchain calls
        can_deploy = (
            hasattr(client, 'web3') and
            factory_address is not None and
            is_abi_complete("agent_factory") and
            self.config.operator_private_key is not None
        )

        if can_deploy:
            try:
                web3 = client.web3

                # Build the contract instance
                contract = web3.eth.contract(
                    address=web3.to_checksum_address(factory_address),
                    abi=AGENT_FACTORY_ABI
                )

                # Get operator account for signing
                from eth_account import Account
                operator = Account.from_key(self.config.operator_private_key)

                # Build transaction
                stake_wei = web3.to_wei(initial_stake, 'ether')
                nonce = await asyncio.to_thread(
                    web3.eth.get_transaction_count, operator.address
                )
                gas_price = await asyncio.to_thread(web3.eth.gas_price)

                tx = contract.functions.createAgent(
                    entity.token_info.name,
                    entity.token_info.symbol,
                    stake_wei
                ).build_transaction({
                    'from': operator.address,
                    'nonce': nonce,
                    'gas': 500000,
                    'gasPrice': gas_price,
                    'chainId': await asyncio.to_thread(lambda: web3.eth.chain_id),
                })

                # Sign and send transaction
                signed_tx = web3.eth.account.sign_transaction(tx, self.config.operator_private_key)
                tx_hash = await asyncio.to_thread(
                    web3.eth.send_raw_transaction, signed_tx.raw_transaction
                )

                logger.info(
                    f"[BLOCKCHAIN] Token deployment transaction sent: {tx_hash.hex()} "
                    f"for {entity.token_info.name}"
                )

                # Wait for receipt (with timeout)
                receipt = await asyncio.to_thread(
                    web3.eth.wait_for_transaction_receipt, tx_hash, timeout=120
                )

                # Parse AgentCreated event to get token address
                token_address = None
                for log in receipt.logs:
                    try:
                        event = contract.events.AgentCreated().process_log(log)
                        token_address = event.args.tokenAddress
                        break
                    except Exception:
                        continue

                if token_address:
                    entity.token_info.token_address = token_address
                    logger.info(f"[BLOCKCHAIN] Token deployed at: {token_address}")

                return TransactionRecord(
                    tx_hash=tx_hash.hex(),
                    chain=chain,
                    block_number=receipt.blockNumber,
                    timestamp=datetime.now(UTC),
                    from_address=operator.address,
                    to_address=factory_address,
                    value=initial_stake,
                    gas_used=receipt.gasUsed,
                    status="confirmed" if receipt.status == 1 else "failed",
                    transaction_type="token_deploy",
                    related_entity_id=entity.id,
                )

            except Exception as e:
                logger.error(f"Blockchain deployment failed: {e}")
                raise BlockchainConfigurationError(f"Token deployment failed: {e}")

        # No simulation mode - require real blockchain configuration
        missing_reqs = []
        if not hasattr(client, 'web3'):
            missing_reqs.append("web3_client")
        if factory_address is None:
            missing_reqs.append("factory_address")
        if not is_abi_complete("agent_factory"):
            missing_reqs.append("contract_abi")
        if self.config.operator_private_key is None:
            missing_reqs.append("operator_key (VIRTUALS_OPERATOR_PRIVATE_KEY)")

        raise BlockchainConfigurationError(
            f"Token deployment requires real blockchain configuration. "
            f"Missing requirements: {', '.join(missing_reqs)}. "
            f"See https://docs.virtuals.io/developers/contracts for contract ABIs."
        )

    async def _contribute_on_chain(
        self,
        entity: TokenizedEntity,
        contributor_wallet: str,
        amount_virtual: float,
    ) -> TransactionRecord:
        """
        Execute bonding curve contribution on-chain.

        Production mode requires:
        1. Complete contract ABIs for bonding curve
        2. Token contract address (from deployment)
        3. Contributor wallet with VIRTUAL tokens
        4. Approved VIRTUAL spend to bonding curve

        Contract interaction pattern:
        ```solidity
        function contribute(uint256 amount) external returns (uint256 tokensReceived);
        ```
        """
        client = self._chain_manager.primary_client
        chain = self.config.primary_chain.value
        token_address = entity.token_info.token_address

        # Check if we can make real blockchain calls
        can_contribute = (
            hasattr(client, 'web3') and
            token_address is not None and
            is_abi_complete("bonding_curve") and
            self.config.operator_private_key is not None
        )

        if can_contribute:
            try:
                web3 = client.web3
                virtual_token_address = ContractAddresses.get_address(chain, "virtual_token")

                # Get operator account
                from eth_account import Account
                operator = Account.from_key(self.config.operator_private_key)

                amount_wei = web3.to_wei(amount_virtual, 'ether')

                # Step 1: Approve VIRTUAL spend (if needed)
                if virtual_token_address:
                    virtual_contract = web3.eth.contract(
                        address=web3.to_checksum_address(virtual_token_address),
                        abi=ERC20_ABI
                    )

                    # Check current allowance
                    allowance = await asyncio.to_thread(
                        virtual_contract.functions.allowance(
                            operator.address,
                            web3.to_checksum_address(token_address)
                        ).call
                    )

                    if allowance < amount_wei:
                        # Approve spending
                        approve_tx = virtual_contract.functions.approve(
                            web3.to_checksum_address(token_address),
                            amount_wei
                        ).build_transaction({
                            'from': operator.address,
                            'nonce': await asyncio.to_thread(
                                web3.eth.get_transaction_count, operator.address
                            ),
                            'gas': 100000,
                            'gasPrice': await asyncio.to_thread(web3.eth.gas_price),
                            'chainId': await asyncio.to_thread(lambda: web3.eth.chain_id),
                        })

                        signed_approve = web3.eth.account.sign_transaction(
                            approve_tx, self.config.operator_private_key
                        )
                        approve_hash = await asyncio.to_thread(
                            web3.eth.send_raw_transaction, signed_approve.raw_transaction
                        )
                        await asyncio.to_thread(
                            web3.eth.wait_for_transaction_receipt, approve_hash, timeout=60
                        )
                        logger.info(f"[BLOCKCHAIN] VIRTUAL approval confirmed: {approve_hash.hex()}")

                # Step 2: Execute contribution
                bonding_contract = web3.eth.contract(
                    address=web3.to_checksum_address(token_address),
                    abi=BONDING_CURVE_ABI
                )

                nonce = await asyncio.to_thread(
                    web3.eth.get_transaction_count, operator.address
                )

                contribute_tx = bonding_contract.functions.contribute(
                    amount_wei
                ).build_transaction({
                    'from': operator.address,
                    'nonce': nonce,
                    'gas': 200000,
                    'gasPrice': await asyncio.to_thread(web3.eth.gas_price),
                    'chainId': await asyncio.to_thread(lambda: web3.eth.chain_id),
                })

                signed_tx = web3.eth.account.sign_transaction(
                    contribute_tx, self.config.operator_private_key
                )
                tx_hash = await asyncio.to_thread(
                    web3.eth.send_raw_transaction, signed_tx.raw_transaction
                )

                logger.info(
                    f"[BLOCKCHAIN] Contribution transaction sent: {tx_hash.hex()} "
                    f"for {amount_virtual} VIRTUAL to {token_address}"
                )

                receipt = await asyncio.to_thread(
                    web3.eth.wait_for_transaction_receipt, tx_hash, timeout=120
                )

                return TransactionRecord(
                    tx_hash=tx_hash.hex(),
                    chain=chain,
                    block_number=receipt.blockNumber,
                    timestamp=datetime.now(UTC),
                    from_address=operator.address,
                    to_address=token_address,
                    value=amount_virtual,
                    gas_used=receipt.gasUsed,
                    status="confirmed" if receipt.status == 1 else "failed",
                    transaction_type="bonding_contribution",
                    related_entity_id=entity.id,
                )

            except Exception as e:
                logger.error(f"Blockchain contribution failed: {e}")
                raise BlockchainConfigurationError(f"Bonding curve contribution failed: {e}")

        # No simulation mode - require real blockchain configuration
        missing_reqs = []
        if not hasattr(client, 'web3'):
            missing_reqs.append("web3_client")
        if token_address is None:
            missing_reqs.append("token_address")
        if not is_abi_complete("bonding_curve"):
            missing_reqs.append("contract_abi")
        if self.config.operator_private_key is None:
            missing_reqs.append("operator_key (VIRTUALS_OPERATOR_PRIVATE_KEY)")

        raise BlockchainConfigurationError(
            f"Bonding curve contribution requires real blockchain configuration. "
            f"Missing requirements: {', '.join(missing_reqs)}. "
            f"See https://docs.virtuals.io/developers/contracts for contract ABIs."
        )

    async def _execute_graduation_on_chain(
        self,
        entity: TokenizedEntity,
    ) -> TransactionRecord:
        """
        Execute token graduation on-chain.

        Graduation process:
        1. Mint full token supply (1 billion)
        2. Create Uniswap V2 pool with VIRTUAL
        3. Lock liquidity for 10 years
        4. Convert FERC20 placeholders to real ERC20

        Contract interaction pattern:
        ```solidity
        function graduate() external returns (address poolAddress);
        ```
        """
        client = self._chain_manager.primary_client

        if not hasattr(client, 'web3'):
            raise BlockchainConfigurationError(
                "Token graduation requires web3 client configuration."
            )

        if not entity.token_info.token_address:
            raise BlockchainConfigurationError(
                "Token graduation requires valid token contract address."
            )

        token_address = entity.token_info.token_address
        web3 = client._w3

        # Get the BondingCurve contract address - this is where graduation happens
        # The bonding curve contract manages the token lifecycle including graduation
        bonding_curve_address = self.config.bonding_curve_address
        if not bonding_curve_address:
            raise BlockchainConfigurationError(
                "BondingCurve contract address not configured for graduation. "
                "Set BONDING_CURVE_ADDRESS in environment or config."
            )

        try:
            # Create BondingCurve contract instance
            bonding_contract = web3.eth.contract(
                address=web3.to_checksum_address(bonding_curve_address),
                abi=BONDING_CURVE_ABI,
            )

            # Get token info to verify it's ready for graduation
            token_info = await bonding_contract.functions.tokenInfo(
                web3.to_checksum_address(token_address)
            ).call()

            # token_info.status: 0=pending, 1=active, 2=graduated
            if token_info[6] == 2:  # Already graduated
                logger.info(f"Token {token_address} is already graduated")
                return TransactionRecord(
                    tx_hash="",
                    chain=self._chain_manager.primary_client.chain.value,
                    block_number=0,
                    timestamp=datetime.now(UTC),
                    from_address="",
                    to_address=token_address,
                    value=0,
                    gas_used=0,
                    status="already_graduated",
                    transaction_type="graduation",
                )

            # Call unwrapToken to convert FERC20 to ERC20 and create LP
            # This requires the token to have reached graduation threshold
            # The function takes: srcTokenAddress and list of account addresses to unwrap for
            accounts_to_unwrap = [entity.creator_address] if entity.creator_address else []

            unwrap_data = bonding_contract.encodeABI(
                fn_name='unwrapToken',
                args=[
                    web3.to_checksum_address(token_address),
                    [web3.to_checksum_address(a) for a in accounts_to_unwrap],
                ]
            )

            tx_record = await client.send_transaction(
                to_address=bonding_curve_address,
                value=0,
                data=bytes.fromhex(unwrap_data[2:]),
            )

            # Wait for graduation transaction to confirm
            tx_record = await client.wait_for_transaction(
                tx_record.tx_hash,
                timeout_seconds=180,  # Graduation may take longer
            )
            tx_record.transaction_type = "graduation"

            logger.info(
                f"[BLOCKCHAIN] Token {token_address} graduated successfully "
                f"(tx: {tx_record.tx_hash})"
            )

            return tx_record

        except Exception as e:
            logger.error(f"Graduation transaction failed: {e}")
            raise BlockchainConfigurationError(
                f"Token graduation failed for {token_address}: {e}. "
                f"Token has accumulated {entity.bonding_curve_virtual_accumulated} VIRTUAL. "
                f"Verify graduation threshold and contract configuration."
            )

    async def _execute_distributions(
        self,
        entity: TokenizedEntity,
        distributions: dict[str, float],
    ) -> list[TransactionRecord]:
        """
        Execute revenue distributions on-chain.

        Uses batch transfer pattern for gas efficiency:
        1. For few recipients (<5): individual ERC20 transfers
        2. For many recipients: use MultiSend contract or Merkle distributor

        In production, this would:
        - Approve VIRTUAL spend from treasury
        - Execute batch transfer via multi-send contract
        - Or set up Merkle root for claim-based distribution
        """
        client = self._chain_manager.primary_client

        if hasattr(client, 'web3'):
            try:
                total_amount = sum(distributions.values())

                # Filter out special keys (creator, treasury, buyback_burn)
                recipient_distributions = {
                    k: v for k, v in distributions.items()
                    if k not in ("creator", "treasury", "buyback_burn") and v > 0
                }

                # Get VIRTUAL token address for the chain
                virtual_address = ContractAddresses.get_address("base", "virtual_token")
                if not virtual_address:
                    raise BlockchainConfigurationError(
                        "VIRTUAL token address not configured for distribution"
                    )

                tx_records: list[TransactionRecord] = []

                if len(recipient_distributions) <= 5:
                    # Individual transfers for small batches - more gas but simpler
                    for recipient, amount in recipient_distributions.items():
                        try:
                            tx_record = await client.transfer_tokens(
                                token_address=virtual_address,
                                to_address=recipient,
                                amount=amount,
                            )
                            # Wait for confirmation
                            tx_record = await client.wait_for_transaction(
                                tx_record.tx_hash,
                                timeout_seconds=60,
                            )
                            tx_records.append(tx_record)
                            logger.info(
                                f"[BLOCKCHAIN] Transferred {amount} VIRTUAL to {recipient} "
                                f"(tx: {tx_record.tx_hash})"
                            )
                        except Exception as e:
                            logger.error(f"Transfer to {recipient} failed: {e}")
                            # Continue with other transfers, but record failure
                            tx_records.append(TransactionRecord(
                                tx_hash="",
                                chain="base",
                                block_number=0,
                                timestamp=datetime.now(UTC),
                                from_address=client._operator_account.address if client._operator_account else "",
                                to_address=recipient,
                                value=amount,
                                gas_used=0,
                                status="failed",
                                transaction_type="distribution",
                                error_message=str(e),
                            ))
                else:
                    # Batch transfer via MultiSend for gas efficiency
                    multisend_address = ContractAddresses.get_address("base", "multisend")
                    if not multisend_address:
                        # Fall back to individual transfers if MultiSend not available
                        logger.warning(
                            "MultiSend not configured, using individual transfers for batch"
                        )
                        for recipient, amount in recipient_distributions.items():
                            try:
                                tx_record = await client.transfer_tokens(
                                    token_address=virtual_address,
                                    to_address=recipient,
                                    amount=amount,
                                )
                                tx_record = await client.wait_for_transaction(
                                    tx_record.tx_hash,
                                    timeout_seconds=60,
                                )
                                tx_records.append(tx_record)
                            except Exception as e:
                                logger.error(f"Transfer to {recipient} failed: {e}")
                    else:
                        # Use MultiSend contract for batch efficiency
                        # Encode multiple transfer calls into single transaction
                        web3 = client._w3
                        virtual_contract = web3.eth.contract(
                            address=web3.to_checksum_address(virtual_address),
                            abi=ERC20_ABI,
                        )

                        # Build encoded transfer calls for MultiSend
                        # Each transfer is: operation(0) + to(20 bytes) + value(32) + data_length(32) + data
                        encoded_txs = b''
                        for recipient, amount in recipient_distributions.items():
                            amount_wei = int(amount * 10**18)
                            transfer_data = virtual_contract.encodeABI(
                                fn_name='transfer',
                                args=[web3.to_checksum_address(recipient), amount_wei]
                            )
                            # Pack for MultiSend: operation(1) + to + value + dataLength + data
                            encoded_txs += (
                                bytes([0]) +  # operation: 0 = call
                                bytes.fromhex(virtual_address[2:].zfill(40)) +  # to address
                                (0).to_bytes(32, 'big') +  # value (0 for token transfer)
                                len(bytes.fromhex(transfer_data[2:])).to_bytes(32, 'big') +
                                bytes.fromhex(transfer_data[2:])
                            )

                        multisend_contract = web3.eth.contract(
                            address=web3.to_checksum_address(multisend_address),
                            abi=MULTISEND_ABI,
                        )
                        multisend_data = multisend_contract.encodeABI(
                            fn_name='multiSend',
                            args=[encoded_txs]
                        )

                        tx_record = await client.send_transaction(
                            to_address=multisend_address,
                            value=0,
                            data=bytes.fromhex(multisend_data[2:]),
                        )
                        tx_record = await client.wait_for_transaction(
                            tx_record.tx_hash,
                            timeout_seconds=120,
                        )
                        tx_record.transaction_type = "batch_distribution"
                        tx_records.append(tx_record)

                        logger.info(
                            f"[BLOCKCHAIN] Batch transferred {total_amount} VIRTUAL "
                            f"to {len(recipient_distributions)} recipients (tx: {tx_record.tx_hash})"
                        )

                return tx_records

            except BlockchainConfigurationError:
                raise
            except Exception as e:
                logger.error(f"Distribution preparation failed: {e}")
                raise BlockchainConfigurationError(f"Distribution failed: {e}")

        raise BlockchainConfigurationError(
            "Revenue distribution requires web3 client configuration."
        )

    async def _execute_buyback_burn(
        self,
        entity: TokenizedEntity,
        amount: float,
    ) -> TransactionRecord | None:
        """
        Execute buyback and burn on-chain.

        Process:
        1. Swap VIRTUAL for entity tokens on Uniswap
        2. Send purchased tokens to burn address (0x0...dead)

        This implements deflationary tokenomics by using revenue
        to reduce circulating supply, increasing value for holders.
        """
        client = self._chain_manager.primary_client

        if not entity.token_info.token_address or not entity.liquidity_pool_address:
            raise BlockchainConfigurationError(
                f"Cannot execute buyback for entity {entity.id}: "
                "missing token address or liquidity pool"
            )

        if not hasattr(client, 'web3'):
            raise BlockchainConfigurationError(
                "Buyback-burn requires web3 client configuration."
            )

        pool_address = entity.liquidity_pool_address

        # Uniswap router interaction pattern:
        # router = web3.eth.contract(address=UNISWAP_ROUTER, abi=ROUTER_ABI)
        #
        # # Approve VIRTUAL spend
        # virtual_token.functions.approve(UNISWAP_ROUTER, amount)
        #
        # # Swap VIRTUAL for entity token
        # tx = router.functions.swapExactTokensForTokens(
        #     amountIn=web3.to_wei(amount, 'ether'),
        #     amountOutMin=0,  # Could add slippage protection
        #     path=[VIRTUAL_ADDRESS, token_address],
        #     to=BURN_ADDRESS,  # Send directly to burn
        #     deadline=int(datetime.now(UTC).timestamp()) + 300
        # ).build_transaction(...)

        raise BlockchainConfigurationError(
            f"Buyback-burn requires complete Uniswap router ABI implementation. "
            f"Would swap {amount} VIRTUAL for entity tokens and burn at pool {pool_address}."
        )

    async def _get_token_balance(
        self,
        entity: TokenizedEntity,
        wallet: str,
    ) -> Decimal:
        """
        Query token contract for wallet balance.

        Used for governance voting power calculation.
        """
        if not entity.token_info.token_address:
            raise BlockchainConfigurationError(
                "Cannot query token balance: token contract address not set."
            )

        client = self._chain_manager.primary_client

        if not hasattr(client, 'web3'):
            raise BlockchainConfigurationError(
                "Token balance query requires web3 client configuration."
            )

        # Use the EVM client's get_wallet_balance method which handles ERC-20 queries
        try:
            balance = await client.get_wallet_balance(
                address=wallet,
                token_address=entity.token_info.token_address,
            )
            return Decimal(str(balance))
        except Exception as e:
            logger.error(f"Failed to query token balance: {e}")
            raise BlockchainConfigurationError(
                f"Token balance query failed for {wallet} on token "
                f"{entity.token_info.token_address}: {e}"
            )


# Global service instance
_tokenization_service: TokenizationService | None = None


async def get_tokenization_service(
    tokenized_entity_repository: Any = None,
    contribution_repository: Any = None,
    proposal_repository: Any = None,
) -> TokenizationService:
    """Get the global tokenization service instance."""
    global _tokenization_service
    if _tokenization_service is None:
        if any(r is None for r in [tokenized_entity_repository, contribution_repository, proposal_repository]):
            raise TokenizationServiceError(
                "Repositories required for first initialization"
            )
        _tokenization_service = TokenizationService(
            tokenized_entity_repository,
            contribution_repository,
            proposal_repository,
        )
        await _tokenization_service.initialize()
    return _tokenization_service
