"""
Agent Commerce Protocol (ACP) Package

This package implements the Virtuals Protocol Agent Commerce Protocol
for enabling secure, verifiable commerce between AI agents.

ACP provides a four-phase transaction framework:
1. Request - Service discovery and job initiation
2. Negotiation - Terms agreement with cryptographic signatures
3. Transaction - Escrow payment and work execution
4. Evaluation - Deliverable verification and fund release

Example Usage:
    from forge.virtuals.acp import get_acp_service, ACPJobCreate
    
    async def example():
        service = await get_acp_service(job_repo, offering_repo)
        
        # Register a service offering
        offering = await service.register_offering(
            agent_id="agent_123",
            agent_wallet="0x...",
            offering=my_offering,
        )
        
        # Create a job from an offering
        job = await service.create_job(
            create_request=ACPJobCreate(
                job_offering_id=offering.id,
                buyer_agent_id="buyer_agent",
                requirements="Analyze Q3 financial data",
                max_fee_virtual=100.0,
            ),
            buyer_wallet="0x...",
        )
"""

from .service import (
    ACPService,
    ACPServiceError,
    InvalidPhaseTransitionError,
    EscrowError,
    get_acp_service,
)
from .nonce_store import (
    NonceStore,
    init_nonce_store,
    get_nonce_store,
    close_nonce_store,
)

__all__ = [
    # Service
    "ACPService",
    "ACPServiceError",
    "InvalidPhaseTransitionError",
    "EscrowError",
    "get_acp_service",
    # Nonce Store (for replay attack prevention)
    "NonceStore",
    "init_nonce_store",
    "get_nonce_store",
    "close_nonce_store",
]
