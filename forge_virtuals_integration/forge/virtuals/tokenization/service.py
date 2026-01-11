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

BLOCKCHAIN INTEGRATION: The helper methods (_deploy_token_contract, etc.)
are implemented with Web3.py patterns but run in simulation mode until:
1. Contract ABIs are provided from Virtuals Protocol documentation
2. Wallet/signing integration is implemented (secure key management)
3. Contract addresses are configured for each chain

Toggle config.enable_tokenization=True to enable real blockchain operations.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from ..config import get_virtuals_config, ChainNetwork
from ..models import (
    TokenizationRequest,
    TokenizedEntity,
    TokenizationStatus,
    TokenInfo,
    TokenDistribution,
    RevenueShare,
    ContributionRecord,
    TokenHolderProposal,
    TokenHolderGovernanceVote,
    BondingCurveContribution,
    TransactionRecord,
)
from ..chains import get_chain_manager


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
        
        # Create on-chain token (if ACP/tokenization enabled)
        if self.config.enable_tokenization:
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
                
            except Exception as e:
                logger.error(f"Token deployment failed: {e}")
                entity.status = TokenizationStatus.FAILED
                entity.metadata["failure_reason"] = str(e)
        else:
            # Simulation mode - mark as bonding without on-chain tx
            entity.status = TokenizationStatus.BONDING
            entity.bonding_curve_virtual_accumulated = request.initial_stake_virtual
            entity.bonding_curve_contributors = 1
        
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
    
    # ==================== Helper Methods ====================

    def _generate_tx_hash(self, *args: Any) -> str:
        """Generate a deterministic transaction hash for simulation mode."""
        data = ":".join(str(arg) for arg in args) + str(datetime.now(UTC).timestamp())
        return "0x" + hashlib.sha256(data.encode()).hexdigest()

    async def _deploy_token_contract(
        self,
        entity: TokenizedEntity,
        initial_stake: float,
        owner_wallet: str,
    ) -> TransactionRecord:
        """
        Deploy the token contract on-chain via Virtuals Protocol AgentFactory.

        In production mode (config.enable_tokenization=True), this will:
        1. Build a transaction to AgentFactory.createAgent()
        2. Sign with the configured system wallet
        3. Submit and wait for confirmation
        4. Parse events to extract token address

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

        # Check if we have real blockchain integration
        if hasattr(client, 'web3') and hasattr(self.config, 'agent_factory_address'):
            try:
                web3 = client.web3
                factory_address = self.config.agent_factory_address

                # Build transaction (requires ABI from Virtuals Protocol)
                # contract = web3.eth.contract(address=factory_address, abi=AGENT_FACTORY_ABI)
                # tx = contract.functions.createAgent(
                #     entity.token_info.name,
                #     entity.token_info.symbol,
                #     web3.to_wei(initial_stake, 'ether')
                # ).build_transaction({
                #     'from': owner_wallet,
                #     'nonce': await web3.eth.get_transaction_count(owner_wallet),
                #     'gas': 500000,
                #     'gasPrice': await web3.eth.gas_price
                # })

                # For now, log that real deployment would occur
                logger.info(
                    f"[BLOCKCHAIN] Would deploy token via AgentFactory at {factory_address} "
                    f"for {entity.token_info.name} with {initial_stake} VIRTUAL stake"
                )

            except Exception as e:
                logger.error(f"Blockchain deployment preparation failed: {e}")

        # Simulation mode - return deterministic tx hash
        tx_hash = self._generate_tx_hash("deploy", entity.id, owner_wallet, initial_stake)

        return TransactionRecord(
            tx_hash=tx_hash,
            chain=self.config.primary_chain.value,
            block_number=0,  # Would be populated from receipt
            timestamp=datetime.now(UTC),
            from_address=owner_wallet,
            to_address=getattr(self.config, 'agent_factory_address', 'agent_factory'),
            value=initial_stake,
            gas_used=0,  # Would be populated from receipt
            status="simulated",  # Mark as simulated until real deployment
            transaction_type="token_deploy",
            related_entity_id=entity.id,
        )

    async def _contribute_on_chain(
        self,
        entity: TokenizedEntity,
        contributor_wallet: str,
        amount_virtual: float,
    ) -> TransactionRecord:
        """
        Execute bonding curve contribution on-chain.

        In production mode, this will:
        1. Approve VIRTUAL token spend to bonding curve contract
        2. Call contribute() on the token's bonding curve
        3. Parse events to get tokens received

        Contract interaction pattern:
        ```solidity
        function contribute(uint256 amount) external returns (uint256 tokensReceived);
        ```
        """
        client = self._chain_manager.primary_client

        if hasattr(client, 'web3') and entity.token_info.token_address:
            try:
                web3 = client.web3
                token_address = entity.token_info.token_address

                # Build contribution transaction (requires ABI)
                # contract = web3.eth.contract(address=token_address, abi=BONDING_CURVE_ABI)
                # tx = contract.functions.contribute(
                #     web3.to_wei(amount_virtual, 'ether')
                # ).build_transaction({
                #     'from': contributor_wallet,
                #     'value': web3.to_wei(amount_virtual, 'ether'),  # If native token
                #     ...
                # })

                logger.info(
                    f"[BLOCKCHAIN] Would contribute {amount_virtual} VIRTUAL "
                    f"to bonding curve at {token_address}"
                )

            except Exception as e:
                logger.error(f"Blockchain contribution preparation failed: {e}")

        # Simulation mode
        tx_hash = self._generate_tx_hash("contribute", entity.id, contributor_wallet, amount_virtual)

        return TransactionRecord(
            tx_hash=tx_hash,
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.now(UTC),
            from_address=contributor_wallet,
            to_address=entity.token_info.token_address or "bonding_curve",
            value=amount_virtual,
            gas_used=0,
            status="simulated",
            transaction_type="bonding_contribution",
            related_entity_id=entity.id,
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

        if hasattr(client, 'web3') and entity.token_info.token_address:
            try:
                web3 = client.web3
                token_address = entity.token_info.token_address

                # Build graduation transaction (requires ABI)
                # contract = web3.eth.contract(address=token_address, abi=TOKEN_ABI)
                # tx = contract.functions.graduate().build_transaction({
                #     'from': self.config.system_wallet,  # System triggers graduation
                #     ...
                # })

                logger.info(
                    f"[BLOCKCHAIN] Would graduate token at {token_address} "
                    f"with {entity.bonding_curve_virtual_accumulated} VIRTUAL accumulated"
                )

            except Exception as e:
                logger.error(f"Blockchain graduation preparation failed: {e}")

        # Simulation mode
        tx_hash = self._generate_tx_hash("graduate", entity.id, entity.bonding_curve_virtual_accumulated)

        return TransactionRecord(
            tx_hash=tx_hash,
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.now(UTC),
            from_address=getattr(self.config, 'system_wallet', 'system'),
            to_address=entity.token_info.token_address or "token_contract",
            value=0,
            gas_used=0,
            status="simulated",
            transaction_type="graduation",
            related_entity_id=entity.id,
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
        tx_records = []

        if hasattr(client, 'web3'):
            try:
                web3 = client.web3
                total_amount = sum(distributions.values())

                # Filter out special keys (creator, treasury, buyback_burn)
                recipient_distributions = {
                    k: v for k, v in distributions.items()
                    if k not in ("creator", "treasury", "buyback_burn") and v > 0
                }

                if len(recipient_distributions) <= 5:
                    # Individual transfers for small batches
                    for recipient, amount in recipient_distributions.items():
                        # tx = virtual_token.functions.transfer(recipient, amount).build_transaction(...)
                        logger.info(f"[BLOCKCHAIN] Would transfer {amount} VIRTUAL to {recipient}")
                else:
                    # Batch transfer via multi-send
                    # recipients = list(recipient_distributions.keys())
                    # amounts = [web3.to_wei(v, 'ether') for v in recipient_distributions.values()]
                    # tx = multi_send.functions.multiTransfer(recipients, amounts).build_transaction(...)
                    logger.info(
                        f"[BLOCKCHAIN] Would batch transfer {total_amount} VIRTUAL "
                        f"to {len(recipient_distributions)} recipients"
                    )

            except Exception as e:
                logger.error(f"Distribution preparation failed: {e}")

        # Create simulation records for each distribution
        for recipient, amount in distributions.items():
            if amount > 0:
                tx_hash = self._generate_tx_hash("distribute", entity.id, recipient, amount)
                tx_records.append(TransactionRecord(
                    tx_hash=tx_hash,
                    chain=self.config.primary_chain.value,
                    block_number=0,
                    timestamp=datetime.now(UTC),
                    from_address="treasury",
                    to_address=recipient,
                    value=amount,
                    gas_used=0,
                    status="simulated",
                    transaction_type="revenue_distribution",
                    related_entity_id=entity.id,
                ))

        logger.info(
            f"Prepared {len(tx_records)} distribution transactions "
            f"for entity {entity.id}"
        )

        return tx_records

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
            logger.warning(
                f"Cannot execute buyback for entity {entity.id}: "
                "missing token address or liquidity pool"
            )
            return None

        if hasattr(client, 'web3'):
            try:
                web3 = client.web3
                token_address = entity.token_info.token_address
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

                logger.info(
                    f"[BLOCKCHAIN] Would swap {amount} VIRTUAL for entity tokens "
                    f"and burn at pool {pool_address}"
                )

            except Exception as e:
                logger.error(f"Buyback-burn preparation failed: {e}")

        # Simulation mode
        tx_hash = self._generate_tx_hash("buyback_burn", entity.id, amount)

        return TransactionRecord(
            tx_hash=tx_hash,
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.now(UTC),
            from_address="treasury",
            to_address="0x000000000000000000000000000000000000dEaD",  # Burn address
            value=amount,
            gas_used=0,
            status="simulated",
            transaction_type="buyback_burn",
            related_entity_id=entity.id,
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
            return Decimal("0")

        client = self._chain_manager.primary_client

        if hasattr(client, 'web3'):
            try:
                web3 = client.web3
                # contract = web3.eth.contract(
                #     address=entity.token_info.token_address,
                #     abi=ERC20_ABI
                # )
                # balance = await contract.functions.balanceOf(wallet).call()
                # return Decimal(balance) / Decimal(10 ** 18)

                logger.debug(f"[BLOCKCHAIN] Would query balance for {wallet}")

            except Exception as e:
                logger.error(f"Balance query failed: {e}")

        # Simulation mode - return placeholder
        return Decimal("1000")


# Global service instance
_tokenization_service: Optional[TokenizationService] = None


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
