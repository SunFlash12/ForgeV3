"""
Revenue Management Package

This package handles all revenue-related operations for the Forge-Virtuals
integration, providing comprehensive fee collection, distribution, and
analytics capabilities.

Revenue Streams:
- Inference Fees: Per-query charges for knowledge capsule access
- Service Fees: Overlay-as-a-service percentage fees
- Governance Rewards: Participation incentives
- Trading Fees: Sentient Tax from token trades

Example Usage:
    from forge.virtuals.revenue import get_revenue_service
    
    async def track_capsule_usage():
        service = await get_revenue_service(revenue_repo)
        
        # Record fee when capsule is queried
        record = await service.record_inference_fee(
            capsule_id="capsule_123",
            user_wallet="0x...",
            query_text="What is our Q3 strategy?",
            tokens_processed=1500,
        )
        
        # Get revenue analytics
        summary = await service.get_revenue_summary(
            entity_id="capsule_123",
            entity_type="capsule",
        )
"""

from .service import (
    RevenueService,
    RevenueServiceError,
    get_revenue_service,
)

__all__ = [
    "RevenueService",
    "RevenueServiceError",
    "get_revenue_service",
]
