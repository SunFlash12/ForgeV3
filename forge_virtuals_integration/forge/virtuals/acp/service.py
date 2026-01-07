"""
Agent Commerce Protocol (ACP) Service

This service implements the four-phase Agent Commerce Protocol for enabling
secure, verifiable commerce between AI agents. ACP allows Forge agents to
offer services, negotiate terms, execute transactions, and evaluate deliverables
all with on-chain settlement and escrow.

The ACP Service handles the complete lifecycle of agent-to-agent transactions,
from service discovery through final settlement. It integrates with Forge's
trust system to ensure only reputable agents can participate in commerce.

ACP Phases:
1. Request - Buyer discovers services and initiates job
2. Negotiation - Parties agree on terms with cryptographic signatures
3. Transaction - Payment escrowed, work performed
4. Evaluation - Deliverables verified, funds released
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from ..config import get_virtuals_config
from ..models import (
    ACPJob,
    ACPJobCreate,
    ACPJobStatus,
    ACPPhase,
    ACPMemo,
    ACPNegotiationTerms,
    ACPDeliverable,
    ACPEvaluation,
    ACPDispute,
    JobOffering,
    ACPRegistryEntry,
)
from ..chains import get_chain_manager


logger = logging.getLogger(__name__)


class ACPServiceError(Exception):
    """Base exception for ACP service errors."""
    pass


class InvalidPhaseTransitionError(ACPServiceError):
    """Raised when attempting an invalid phase transition."""
    pass


class EscrowError(ACPServiceError):
    """Raised when escrow operations fail."""
    pass


class ACPService:
    """
    Service for managing Agent Commerce Protocol transactions.
    
    This service provides the complete ACP implementation including:
    - Service registry for discovering agent offerings
    - Job creation and lifecycle management
    - Cryptographic memo signing and verification
    - Escrow management with on-chain settlement
    - Dispute resolution
    
    The service maintains both on-chain state (through smart contracts)
    and off-chain state (in the Forge database) for efficient querying
    while ensuring all critical operations are verifiable on-chain.
    """
    
    def __init__(
        self,
        job_repository: Any,  # Would be Forge's ACPJobRepository
        offering_repository: Any,  # Would be Forge's OfferingRepository
    ):
        """
        Initialize the ACP service.
        
        Args:
            job_repository: Repository for storing and retrieving ACP jobs
            offering_repository: Repository for service offerings
        """
        self.config = get_virtuals_config()
        self._job_repo = job_repository
        self._offering_repo = offering_repository
        self._chain_manager = None
    
    async def initialize(self) -> None:
        """Initialize the service and chain connections."""
        self._chain_manager = await get_chain_manager()
        logger.info("ACP Service initialized")
    
    # ==================== Service Registry ====================
    
    async def register_offering(
        self,
        agent_id: str,
        agent_wallet: str,
        offering: JobOffering,
    ) -> JobOffering:
        """
        Register a new service offering in the ACP registry.
        
        This makes the agent's service discoverable by other agents and users.
        The offering is stored both on-chain (for verifiability) and in the
        local database (for efficient querying).
        
        Args:
            agent_id: ID of the agent offering the service
            agent_wallet: Wallet address of the offering agent
            offering: The service offering to register
            
        Returns:
            The registered offering with registry ID assigned
        """
        offering.provider_agent_id = agent_id
        offering.provider_wallet = agent_wallet
        
        # Store in local repository for fast queries
        await self._offering_repo.create(offering)
        
        # Register on-chain for verifiability (if ACP contracts are available)
        if self.config.enable_acp:
            try:
                client = self._chain_manager.primary_client
                # This would call the ACP registry contract
                # tx = await client.execute_contract(
                #     contract_address=acp_registry_address,
                #     function_name="registerOffering",
                #     args=[...],
                #     abi=acp_registry_abi,
                # )
                # offering.registry_id = extract_from_tx(tx)
                # offering.registration_tx_hash = tx.tx_hash
                pass
            except Exception as e:
                logger.warning(f"On-chain registration failed: {e}")
        
        logger.info(f"Registered offering {offering.id} for agent {agent_id}")
        return offering
    
    async def search_offerings(
        self,
        service_type: Optional[str] = None,
        query: Optional[str] = None,
        max_fee: Optional[float] = None,
        min_provider_reputation: float = 0.0,
        limit: int = 20,
    ) -> list[JobOffering]:
        """
        Search the service registry for matching offerings.
        
        This enables service discovery, allowing agents to find providers
        that can fulfill their needs. The search considers service type,
        natural language queries, pricing, and provider reputation.
        
        Args:
            service_type: Filter by service type (knowledge_query, analysis, etc.)
            query: Natural language description of needed service
            max_fee: Maximum acceptable base fee in VIRTUAL
            min_provider_reputation: Minimum required provider reputation (0-1)
            limit: Maximum results to return
            
        Returns:
            List of matching offerings sorted by relevance/reputation
        """
        # Query local repository with filters
        offerings = await self._offering_repo.search(
            service_type=service_type,
            query=query,
            max_fee=max_fee,
            min_provider_reputation=min_provider_reputation,
            limit=limit,
        )
        
        return offerings
    
    async def get_registry_entry(self, agent_id: str) -> Optional[ACPRegistryEntry]:
        """
        Get an agent's complete registry entry with all offerings and stats.
        
        This provides a comprehensive view of an agent's ACP presence,
        including all services offered, reputation, and historical metrics.
        """
        offerings = await self._offering_repo.get_by_agent(agent_id)
        
        if not offerings:
            return None
        
        # Calculate aggregate stats
        total_jobs = await self._job_repo.count_by_provider(agent_id)
        total_revenue = await self._job_repo.sum_revenue_by_provider(agent_id)
        avg_rating = await self._job_repo.average_rating_by_provider(agent_id)
        
        return ACPRegistryEntry(
            id=str(uuid4()),
            agent_id=agent_id,
            wallet_address=offerings[0].provider_wallet,
            offerings=offerings,
            total_jobs_completed=total_jobs,
            total_revenue_earned=total_revenue,
            average_rating=avg_rating or 0.0,
            reputation_score=self._calculate_reputation(total_jobs, avg_rating),
        )
    
    # ==================== Job Lifecycle ====================
    
    async def create_job(
        self,
        create_request: ACPJobCreate,
        buyer_wallet: str,
    ) -> ACPJob:
        """
        Create a new ACP job from a service offering.
        
        This initiates the Request phase of the ACP protocol. The buyer
        specifies their requirements and maximum acceptable fee. The job
        is then available for the provider to accept and begin negotiation.
        
        Args:
            create_request: Job creation specification
            buyer_wallet: Wallet address of the buyer
            
        Returns:
            The created job in REQUEST phase
        """
        # Get the offering details
        offering = await self._offering_repo.get_by_id(create_request.job_offering_id)
        if not offering:
            raise ACPServiceError(f"Offering {create_request.job_offering_id} not found")
        
        # Validate buyer's fee limit against offering's base fee
        if create_request.max_fee_virtual < offering.base_fee_virtual:
            raise ACPServiceError(
                f"Max fee ({create_request.max_fee_virtual}) below offering minimum ({offering.base_fee_virtual})"
            )
        
        # Create the job
        job = ACPJob(
            job_offering_id=create_request.job_offering_id,
            buyer_agent_id=create_request.buyer_agent_id,
            buyer_wallet=buyer_wallet,
            provider_agent_id=offering.provider_agent_id,
            provider_wallet=offering.provider_wallet,
            current_phase=ACPPhase.REQUEST,
            status=ACPJobStatus.OPEN,
            requirements=create_request.requirements,
        )
        
        # Create and sign the request memo
        request_memo = await self._create_memo(
            job_id=job.id,
            memo_type="request",
            content={
                "requirements": create_request.requirements,
                "max_fee_virtual": create_request.max_fee_virtual,
                "preferred_deadline": create_request.preferred_deadline.isoformat() if create_request.preferred_deadline else None,
                "additional_context": create_request.additional_context,
            },
            sender_address=buyer_wallet,
        )
        job.request_memo = request_memo
        
        # Store the job
        await self._job_repo.create(job)
        
        logger.info(f"Created ACP job {job.id} for offering {offering.id}")
        return job
    
    async def respond_to_request(
        self,
        job_id: str,
        terms: ACPNegotiationTerms,
        provider_wallet: str,
    ) -> ACPJob:
        """
        Provider responds to a job request with proposed terms.
        
        This transitions the job from REQUEST to NEGOTIATION phase. The
        provider specifies the fee, deadline, and deliverable details.
        The terms are cryptographically signed to create a binding offer.
        
        Args:
            job_id: ID of the job to respond to
            terms: Proposed terms from the provider
            provider_wallet: Wallet address of provider (for verification)
            
        Returns:
            Updated job in NEGOTIATION phase
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ACPServiceError(f"Job {job_id} not found")
        
        if job.current_phase != ACPPhase.REQUEST:
            raise InvalidPhaseTransitionError(
                f"Cannot respond to job in {job.current_phase} phase"
            )
        
        if job.provider_wallet != provider_wallet:
            raise ACPServiceError("Only the designated provider can respond")
        
        # Create requirement memo with proposed terms
        requirement_memo = await self._create_memo(
            job_id=job.id,
            memo_type="requirement",
            content={
                "proposed_fee_virtual": terms.proposed_fee_virtual,
                "proposed_deadline": terms.proposed_deadline.isoformat(),
                "deliverable_format": terms.deliverable_format,
                "deliverable_description": terms.deliverable_description,
                "special_conditions": terms.special_conditions,
            },
            sender_address=provider_wallet,
        )
        
        job.requirement_memo = requirement_memo
        job.negotiated_terms = requirement_memo.content
        job.advance_to_phase(ACPPhase.NEGOTIATION)
        job.status = ACPJobStatus.NEGOTIATING
        
        await self._job_repo.update(job)
        
        logger.info(f"Provider responded to job {job_id}, moved to NEGOTIATION")
        return job
    
    async def accept_terms(
        self,
        job_id: str,
        buyer_wallet: str,
    ) -> ACPJob:
        """
        Buyer accepts the proposed terms and initiates escrow.
        
        This transitions the job from NEGOTIATION to TRANSACTION phase.
        The agreed fee is locked in escrow, and the provider is authorized
        to begin work. This is a critical on-chain operation.
        
        Args:
            job_id: ID of the job
            buyer_wallet: Buyer's wallet (for escrow payment)
            
        Returns:
            Updated job in TRANSACTION phase with escrow active
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ACPServiceError(f"Job {job_id} not found")
        
        if job.current_phase != ACPPhase.NEGOTIATION:
            raise InvalidPhaseTransitionError(
                f"Cannot accept terms in {job.current_phase} phase"
            )
        
        if job.buyer_wallet != buyer_wallet:
            raise ACPServiceError("Only the buyer can accept terms")
        
        agreed_fee = job.negotiated_terms.get("proposed_fee_virtual", 0)
        
        # Create agreement memo
        agreement_memo = await self._create_memo(
            job_id=job.id,
            memo_type="agreement",
            content={
                "agreed_fee_virtual": agreed_fee,
                "agreed_terms": job.negotiated_terms,
                "buyer_acceptance": True,
            },
            sender_address=buyer_wallet,
        )
        
        # Lock funds in escrow (on-chain)
        if self.config.enable_acp:
            try:
                escrow_tx = await self._lock_escrow(
                    job_id=job.id,
                    payer_wallet=buyer_wallet,
                    amount_virtual=agreed_fee,
                )
                job.escrow_tx_hash = escrow_tx.tx_hash
            except Exception as e:
                raise EscrowError(f"Failed to lock escrow: {e}")
        
        job.agreement_memo = agreement_memo
        job.agreed_fee_virtual = agreed_fee
        job.agreed_deadline = datetime.fromisoformat(
            job.negotiated_terms.get("proposed_deadline", datetime.utcnow().isoformat())
        )
        job.escrow_amount_virtual = agreed_fee
        job.advance_to_phase(ACPPhase.TRANSACTION)
        job.status = ACPJobStatus.IN_PROGRESS
        job.execution_timeout = job.agreed_deadline
        
        await self._job_repo.update(job)
        
        logger.info(f"Terms accepted for job {job_id}, escrow locked: {agreed_fee} VIRTUAL")
        return job
    
    async def submit_deliverable(
        self,
        job_id: str,
        deliverable: ACPDeliverable,
        provider_wallet: str,
    ) -> ACPJob:
        """
        Provider submits deliverables for the completed work.
        
        This creates the deliverable memo and moves the job toward
        evaluation. The deliverable can be content, a URL reference,
        or a file hash depending on the service type.
        
        Args:
            job_id: ID of the job
            deliverable: The deliverable submission
            provider_wallet: Provider's wallet (for verification)
            
        Returns:
            Updated job awaiting evaluation
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ACPServiceError(f"Job {job_id} not found")
        
        if job.current_phase != ACPPhase.TRANSACTION:
            raise InvalidPhaseTransitionError(
                f"Cannot submit deliverable in {job.current_phase} phase"
            )
        
        if job.provider_wallet != provider_wallet:
            raise ACPServiceError("Only the provider can submit deliverables")
        
        # Create deliverable memo
        deliverable_memo = await self._create_memo(
            job_id=job.id,
            memo_type="deliverable",
            content={
                "content_type": deliverable.content_type,
                "content": deliverable.content,
                "notes": deliverable.notes,
            },
            sender_address=provider_wallet,
        )
        
        job.deliverable_memo = deliverable_memo
        job.deliverable_content = deliverable.content
        job.delivered_at = datetime.utcnow()
        job.status = ACPJobStatus.DELIVERED
        job.advance_to_phase(ACPPhase.EVALUATION)
        job.evaluation_timeout = datetime.utcnow() + timedelta(
            hours=self.config.acp_evaluation_timeout_hours
        )
        
        await self._job_repo.update(job)
        
        logger.info(f"Deliverable submitted for job {job_id}")
        return job
    
    async def evaluate_deliverable(
        self,
        job_id: str,
        evaluation: ACPEvaluation,
        evaluator_wallet: str,
    ) -> ACPJob:
        """
        Evaluate the deliverable and settle the transaction.
        
        This is the final phase of the ACP protocol. The evaluator
        (buyer or designated evaluator agent) reviews the deliverable
        and approves or rejects it. Approval triggers escrow release
        to the provider; rejection may initiate dispute resolution.
        
        Args:
            job_id: ID of the job
            evaluation: The evaluation result
            evaluator_wallet: Wallet of the evaluator
            
        Returns:
            Completed job with evaluation recorded
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ACPServiceError(f"Job {job_id} not found")
        
        if job.current_phase != ACPPhase.EVALUATION:
            raise InvalidPhaseTransitionError(
                f"Cannot evaluate in {job.current_phase} phase"
            )
        
        # Verify evaluator authorization (buyer or designated evaluator)
        if evaluator_wallet not in [job.buyer_wallet, job.evaluator_agent_id]:
            raise ACPServiceError("Unauthorized evaluator")
        
        # Create evaluation memo
        evaluation_memo = await self._create_memo(
            job_id=job.id,
            memo_type="evaluation",
            content={
                "result": evaluation.result,
                "score": evaluation.score,
                "feedback": evaluation.feedback,
                "met_requirements": evaluation.met_requirements,
                "unmet_requirements": evaluation.unmet_requirements,
            },
            sender_address=evaluator_wallet,
        )
        
        job.evaluation_memo = evaluation_memo
        job.evaluation_result = evaluation.result
        job.evaluation_score = evaluation.score
        job.evaluation_feedback = evaluation.feedback
        job.evaluated_at = datetime.utcnow()
        job.status = ACPJobStatus.EVALUATING
        
        # Handle evaluation result
        if evaluation.result == "approved":
            # Release escrow to provider
            if self.config.enable_acp and job.escrow_tx_hash:
                try:
                    settlement_tx = await self._release_escrow(
                        job_id=job.id,
                        recipient_wallet=job.provider_wallet,
                        amount_virtual=job.escrow_amount_virtual,
                    )
                    job.settlement_tx_hash = settlement_tx.tx_hash
                except Exception as e:
                    logger.error(f"Escrow release failed: {e}")
                    raise EscrowError(f"Failed to release escrow: {e}")
            
            job.escrow_released = True
            job.status = ACPJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            logger.info(f"Job {job_id} completed successfully, escrow released")
            
        elif evaluation.result == "rejected":
            # Initiate refund (partial or full based on work done)
            job.status = ACPJobStatus.DISPUTED
            job.is_disputed = True
            job.dispute_reason = f"Deliverable rejected: {evaluation.feedback}"
            
            logger.warning(f"Job {job_id} deliverable rejected, dispute initiated")
        
        await self._job_repo.update(job)
        return job
    
    async def file_dispute(
        self,
        job_id: str,
        dispute: ACPDispute,
        filer_wallet: str,
    ) -> ACPJob:
        """
        File a dispute for a job.
        
        Disputes can be filed by either party when there's disagreement
        about terms, deliverables, or evaluation. The dispute triggers
        a resolution process that may involve arbitration.
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ACPServiceError(f"Job {job_id} not found")
        
        if filer_wallet not in [job.buyer_wallet, job.provider_wallet]:
            raise ACPServiceError("Only buyer or provider can file disputes")
        
        job.is_disputed = True
        job.dispute_reason = dispute.reason
        job.status = ACPJobStatus.DISPUTED
        
        await self._job_repo.update(job)
        
        logger.warning(f"Dispute filed for job {job_id}: {dispute.reason}")
        return job
    
    # ==================== Helper Methods ====================
    
    async def _create_memo(
        self,
        job_id: str,
        memo_type: str,
        content: dict[str, Any],
        sender_address: str,
    ) -> ACPMemo:
        """
        Create a cryptographically signed ACP memo.
        
        Memos form the immutable record of the ACP transaction,
        with each party signing their contributions.
        """
        content_json = json.dumps(content, sort_keys=True)
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()
        
        # In production, this would use actual cryptographic signing
        # with the sender's private key
        signature = f"sig_{content_hash[:16]}_{sender_address[-8:]}"
        
        return ACPMemo(
            memo_type=memo_type,
            job_id=job_id,
            content=content,
            content_hash=content_hash,
            sender_address=sender_address,
            sender_signature=signature,
        )
    
    async def _lock_escrow(
        self,
        job_id: str,
        payer_wallet: str,
        amount_virtual: float,
    ):
        """Lock funds in escrow for a job."""
        client = self._chain_manager.primary_client
        
        # This would interact with the ACP escrow contract
        # For now, return a mock transaction
        from ..models import TransactionRecord
        return TransactionRecord(
            tx_hash=f"0x{'0' * 64}",
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.utcnow(),
            from_address=payer_wallet,
            to_address="escrow_contract",
            value=amount_virtual,
            gas_used=0,
            status="pending",
            transaction_type="escrow_lock",
            related_entity_id=job_id,
        )
    
    async def _release_escrow(
        self,
        job_id: str,
        recipient_wallet: str,
        amount_virtual: float,
    ):
        """Release escrowed funds to the provider."""
        client = self._chain_manager.primary_client
        
        # This would interact with the ACP escrow contract
        from ..models import TransactionRecord
        return TransactionRecord(
            tx_hash=f"0x{'1' * 64}",
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.utcnow(),
            from_address="escrow_contract",
            to_address=recipient_wallet,
            value=amount_virtual,
            gas_used=0,
            status="pending",
            transaction_type="escrow_release",
            related_entity_id=job_id,
        )
    
    def _calculate_reputation(
        self,
        total_jobs: int,
        avg_rating: Optional[float],
    ) -> float:
        """
        Calculate reputation score from job history.
        
        The reputation algorithm considers:
        - Number of completed jobs (experience)
        - Average rating (quality)
        - Dispute rate (reliability)
        """
        if total_jobs == 0:
            return 0.5  # Default neutral reputation
        
        rating = avg_rating or 3.0  # Default average if no ratings
        
        # Normalize rating from 0-5 scale to 0-1
        normalized_rating = rating / 5.0
        
        # Experience factor (logarithmic scale)
        import math
        experience_factor = min(1.0, math.log(total_jobs + 1) / math.log(100))
        
        # Combined reputation
        reputation = (normalized_rating * 0.7) + (experience_factor * 0.3)
        
        return round(reputation, 3)


# Global service instance
_acp_service: Optional[ACPService] = None


async def get_acp_service(
    job_repository: Any = None,
    offering_repository: Any = None,
) -> ACPService:
    """
    Get the global ACP service instance.
    
    Initializes the service if not already done.
    """
    global _acp_service
    if _acp_service is None:
        if job_repository is None or offering_repository is None:
            raise ACPServiceError(
                "Repositories required for first initialization"
            )
        _acp_service = ACPService(job_repository, offering_repository)
        await _acp_service.initialize()
    return _acp_service
