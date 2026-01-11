"""
Revenue Management Service

This service handles all revenue-related operations for the Forge-Virtuals
integration, including fee collection, revenue distribution, and analytics.

The revenue model encompasses three primary streams:
1. Inference Fees - Per-query charges for knowledge capsule access
2. Service Fees - Overlay-as-a-service percentage fees
3. Governance Rewards - Participation incentives for voting

Revenue flows through a multi-step distribution process that benefits
creators, contributors, and the protocol treasury while implementing
deflationary tokenomics through buyback-and-burn mechanisms.

PERSISTENCE: Pending distributions are persisted via the RevenueRecord's
distribution_complete field. On startup, records with distribution_complete=False
are loaded back into the pending queue. This ensures no revenue is lost on restart.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import uuid4
from collections import defaultdict

from ..config import get_virtuals_config
from ..models import (
    RevenueRecord,
    RevenueType,
    TransactionRecord,
)
from ..chains import get_chain_manager


logger = logging.getLogger(__name__)


class RevenueServiceError(Exception):
    """Base exception for revenue service errors."""
    pass


class RevenueService:
    """
    Service for managing revenue streams within the Forge-Virtuals ecosystem.
    
    This service provides comprehensive revenue management including:
    - Fee collection from various sources (inference, service, trading)
    - Revenue distribution according to configured splits
    - Analytics and reporting on revenue performance
    - Integration with tokenization for revenue-based valuations
    
    The service maintains accurate accounting while enabling real-time
    distribution to stakeholders through the blockchain infrastructure.
    """
    
    def __init__(
        self,
        revenue_repository: Any,  # Forge's RevenueRepository
    ):
        """
        Initialize the revenue service.
        
        Args:
            revenue_repository: Repository for storing revenue records
        """
        self.config = get_virtuals_config()
        self._revenue_repo = revenue_repository
        self._chain_manager = None
        self._pending_distributions: list[RevenueRecord] = []
    
    async def initialize(self) -> None:
        """Initialize the service and chain connections."""
        self._chain_manager = await get_chain_manager()

        # PERSISTENCE: Load pending distributions from database
        await self._load_pending_distributions()

        logger.info(
            f"Revenue Service initialized with {len(self._pending_distributions)} pending distributions"
        )

    async def _load_pending_distributions(self) -> None:
        """
        Load pending (undistributed) revenue records from the database.

        This ensures that any records that were created but not yet distributed
        before a restart are recovered and processed.
        """
        try:
            # Query for records that haven't been distributed yet
            pending_records = await self._revenue_repo.query_pending()
            self._pending_distributions = list(pending_records)
            logger.info(f"Loaded {len(self._pending_distributions)} pending distributions from database")
        except AttributeError:
            # Repository doesn't have query_pending method - fall back to basic query
            try:
                all_records = await self._revenue_repo.query(
                    distribution_complete=False
                )
                self._pending_distributions = list(all_records)
                logger.info(f"Loaded {len(self._pending_distributions)} pending distributions")
            except Exception as e:
                logger.warning(f"Could not load pending distributions: {e}")
                self._pending_distributions = []
        except Exception as e:
            logger.warning(f"Failed to load pending distributions: {e}")
            self._pending_distributions = []
    
    # ==================== Fee Collection ====================
    
    async def record_inference_fee(
        self,
        capsule_id: str,
        user_wallet: str,
        query_text: str,
        tokens_processed: int,
    ) -> RevenueRecord:
        """
        Record an inference fee for a knowledge capsule query.
        
        Inference fees are charged when users or agents query knowledge
        capsules. The fee is calculated based on the configured per-query
        rate and the complexity of the query (tokens processed).
        
        Args:
            capsule_id: ID of the queried capsule
            user_wallet: Wallet of the user making the query
            query_text: The query for logging purposes
            tokens_processed: Number of tokens in query + response
            
        Returns:
            The recorded revenue event
        """
        # Calculate fee based on tokens processed. The base fee covers simple queries,
        # while additional tokens incur proportional charges. This encourages efficient
        # queries while ensuring complex analyses are properly compensated.
        base_fee = self.config.inference_fee_per_query
        token_fee = (tokens_processed / 1000) * 0.0001  # $0.0001 per 1K tokens
        total_fee = base_fee + token_fee
        
        record = RevenueRecord(
            revenue_type=RevenueType.INFERENCE_FEE,
            amount_virtual=total_fee,
            source_entity_id=capsule_id,
            source_entity_type="capsule",
            metadata={
                "user_wallet": user_wallet,
                "tokens_processed": tokens_processed,
                "query_preview": query_text[:100] if query_text else "",
            },
        )
        
        await self._revenue_repo.create(record)
        self._pending_distributions.append(record)
        
        logger.debug(f"Recorded inference fee: {total_fee} VIRTUAL for capsule {capsule_id}")
        return record
    
    async def record_service_fee(
        self,
        overlay_id: str,
        service_type: str,
        base_amount_virtual: float,
        client_wallet: str,
    ) -> RevenueRecord:
        """
        Record a service fee for overlay-as-a-service usage.
        
        Service fees are a percentage of the value provided by overlay
        services. This creates alignment between overlay value and
        revenue generation. Higher-value services generate proportionally
        higher fees, incentivizing quality improvements.
        
        Args:
            overlay_id: ID of the overlay providing service
            service_type: Type of service (analysis, validation, etc.)
            base_amount_virtual: The base transaction amount
            client_wallet: Wallet of the service consumer
            
        Returns:
            The recorded revenue event
        """
        fee_percentage = self.config.overlay_service_fee_percentage
        fee_amount = base_amount_virtual * fee_percentage
        
        record = RevenueRecord(
            revenue_type=RevenueType.SERVICE_FEE,
            amount_virtual=fee_amount,
            source_entity_id=overlay_id,
            source_entity_type="overlay",
            metadata={
                "service_type": service_type,
                "base_amount": base_amount_virtual,
                "fee_percentage": fee_percentage,
                "client_wallet": client_wallet,
            },
        )
        
        await self._revenue_repo.create(record)
        self._pending_distributions.append(record)
        
        logger.debug(f"Recorded service fee: {fee_amount} VIRTUAL for overlay {overlay_id}")
        return record
    
    async def record_governance_reward(
        self,
        participant_wallet: str,
        proposal_id: str,
        participation_type: str,
    ) -> RevenueRecord:
        """
        Record a governance participation reward.
        
        Governance rewards incentivize active participation in the
        democratic governance process. Rewards are distributed from
        the protocol's governance reward pool based on participation
        type and quality. This ensures sustained engagement with
        important protocol decisions.
        
        Args:
            participant_wallet: Wallet receiving the reward
            proposal_id: ID of the proposal participated in
            participation_type: Type (vote, proposal, evaluation)
            
        Returns:
            The recorded revenue event
        """
        # Reward amounts vary by participation type to encourage different
        # forms of engagement. Proposing new ideas earns more than voting,
        # while evaluation tasks fall in between.
        reward_amounts = {
            "vote": 0.01,        # Small reward for voting
            "proposal": 0.5,    # Larger reward for creating proposals
            "evaluation": 0.1,  # Medium reward for evaluation
        }
        
        reward_amount = reward_amounts.get(participation_type, 0.01)
        
        record = RevenueRecord(
            revenue_type=RevenueType.GOVERNANCE_REWARD,
            amount_virtual=reward_amount,
            source_entity_id=proposal_id,
            source_entity_type="proposal",
            beneficiary_addresses=[participant_wallet],
            metadata={
                "participation_type": participation_type,
            },
        )
        
        await self._revenue_repo.create(record)
        
        logger.debug(
            f"Recorded governance reward: {reward_amount} VIRTUAL "
            f"for {participation_type} on {proposal_id}"
        )
        return record
    
    async def record_trading_fee(
        self,
        token_address: str,
        trade_amount_virtual: float,
        trader_wallet: str,
        trade_type: str,
    ) -> RevenueRecord:
        """
        Record the Sentient Tax from token trading.
        
        The Sentient Tax is a 1% fee on all trades of graduated agent
        tokens. This fee funds ongoing development, creator rewards,
        and deflationary buyback-burn mechanisms. It creates sustainable
        revenue tied to token market activity.
        
        Args:
            token_address: Address of the traded token
            trade_amount_virtual: Value of the trade in VIRTUAL
            trader_wallet: Wallet executing the trade
            trade_type: Type of trade (buy, sell)
            
        Returns:
            The recorded revenue event
        """
        sentient_tax_rate = 0.01  # 1% Sentient Tax
        tax_amount = trade_amount_virtual * sentient_tax_rate
        
        record = RevenueRecord(
            revenue_type=RevenueType.TRADING_FEE,
            amount_virtual=tax_amount,
            source_entity_id=token_address,
            source_entity_type="agent_token",
            metadata={
                "trade_amount": trade_amount_virtual,
                "trade_type": trade_type,
                "trader_wallet": trader_wallet,
                "tax_rate": sentient_tax_rate,
            },
        )
        
        await self._revenue_repo.create(record)
        self._pending_distributions.append(record)
        
        logger.debug(f"Recorded trading fee: {tax_amount} VIRTUAL from {trade_type}")
        return record
    
    # ==================== Revenue Distribution ====================
    
    async def process_pending_distributions(
        self,
        batch_size: int = 100,
    ) -> dict[str, float]:
        """
        Process pending revenue distributions in batches.

        This method aggregates pending revenue records and executes
        batch distributions to minimize gas costs. Distributions are
        grouped by beneficiary for efficient processing. The method
        returns a summary of all distributions made.

        SECURITY FIX (Audit 4 - M16): Added integrity check to verify
        distribution amounts match expected totals.

        Args:
            batch_size: Maximum records to process per batch

        Returns:
            Dict mapping beneficiary addresses to total amounts distributed
        """
        if not self._pending_distributions:
            return {}

        # Take a batch of pending distributions
        batch = self._pending_distributions[:batch_size]
        self._pending_distributions = self._pending_distributions[batch_size:]

        # SECURITY FIX (Audit 4 - M16): Calculate expected total for integrity check
        expected_total = sum(record.amount_virtual for record in batch)

        # Aggregate by beneficiary for batch processing
        aggregated: dict[str, float] = defaultdict(float)

        for record in batch:
            for beneficiary in record.beneficiary_addresses:
                aggregated[beneficiary] += record.amount_virtual

        # SECURITY FIX (Audit 4 - M16): Verify distribution integrity
        distribution_total = sum(aggregated.values())
        if abs(distribution_total - expected_total) > 0.001:  # Allow small float precision error
            logger.error(
                "distribution_integrity_mismatch",
                expected_total=expected_total,
                distribution_total=distribution_total,
                difference=distribution_total - expected_total,
                batch_size=len(batch),
            )
            # Return batch to queue and abort this distribution
            self._pending_distributions = batch + self._pending_distributions
            raise RevenueServiceError(
                f"Distribution integrity check failed: expected {expected_total}, "
                f"got {distribution_total} (diff: {distribution_total - expected_total})"
            )

        # Execute batch distribution if enabled
        if self.config.enable_revenue_sharing and aggregated:
            try:
                await self._execute_batch_distribution(aggregated)

                # Mark records as distributed
                for record in batch:
                    record.distribution_complete = True
                    await self._revenue_repo.update(record)

            except Exception as e:
                logger.error(f"Batch distribution failed: {e}")
                # Return records to pending queue for retry
                self._pending_distributions.extend(batch)
                raise RevenueServiceError(f"Distribution failed: {e}")

        logger.info(
            f"Processed {len(batch)} revenue records, "
            f"distributed to {len(aggregated)} beneficiaries, "
            f"total: {distribution_total} VIRTUAL"
        )

        return dict(aggregated)
    
    async def _execute_batch_distribution(
        self,
        distributions: dict[str, float],
    ) -> TransactionRecord:
        """
        Execute a batch of distributions in a single transaction.
        
        This uses a multi-send pattern to distribute VIRTUAL tokens
        to multiple recipients efficiently. The batch approach
        significantly reduces gas costs compared to individual transfers.
        """
        client = self._chain_manager.primary_client
        
        # In production, this would use a multi-send contract or
        # aggregate into a merkle distributor for gas efficiency
        
        return TransactionRecord(
            tx_hash=f"0x{'d' * 64}",
            chain=self.config.primary_chain.value,
            block_number=0,
            timestamp=datetime.now(UTC),
            from_address="treasury",
            to_address="multi_send",
            value=sum(distributions.values()),
            gas_used=0,
            status="pending",
            transaction_type="batch_distribution",
        )
    
    # ==================== Analytics and Reporting ====================
    
    async def get_revenue_summary(
        self,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get a summary of revenue for analysis and reporting.
        
        This method provides comprehensive revenue analytics filtered by
        entity, type, and time period. The summary includes totals by
        revenue type, top performers, and trend data for visualization.
        
        Args:
            entity_id: Optional filter by specific entity
            entity_type: Optional filter by entity type (capsule, overlay, etc.)
            start_date: Optional start of analysis period
            end_date: Optional end of analysis period
            
        Returns:
            Dict containing revenue summary statistics
        """
        # Set defaults for date range
        if end_date is None:
            end_date = datetime.now(UTC)
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        # Query revenue records with filters
        records = await self._revenue_repo.query(
            entity_id=entity_id,
            entity_type=entity_type,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Aggregate by revenue type
        by_type: dict[str, float] = defaultdict(float)
        by_entity: dict[str, float] = defaultdict(float)
        daily_totals: dict[str, float] = defaultdict(float)
        
        for record in records:
            by_type[record.revenue_type.value] += record.amount_virtual
            by_entity[record.source_entity_id] += record.amount_virtual
            day_key = record.timestamp.strftime("%Y-%m-%d")
            daily_totals[day_key] += record.amount_virtual
        
        total_revenue = sum(by_type.values())
        
        # Calculate top performers
        top_entities = sorted(
            by_entity.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_revenue_virtual": total_revenue,
            "by_type": dict(by_type),
            "top_entities": [
                {"entity_id": eid, "revenue": rev}
                for eid, rev in top_entities
            ],
            "daily_totals": dict(daily_totals),
            "record_count": len(records),
            "average_per_record": total_revenue / len(records) if records else 0,
        }
    
    async def get_entity_revenue(
        self,
        entity_id: str,
        entity_type: str,
    ) -> dict[str, Any]:
        """
        Get detailed revenue information for a specific entity.
        
        This provides entity-level revenue analytics including lifetime
        totals, recent activity, and distribution history. This information
        is valuable for assessing entity value and performance.
        
        Args:
            entity_id: ID of the entity
            entity_type: Type of entity
            
        Returns:
            Dict containing entity-specific revenue details
        """
        # Query all records for this entity
        records = await self._revenue_repo.query(
            entity_id=entity_id,
            entity_type=entity_type,
        )
        
        if not records:
            return {
                "entity_id": entity_id,
                "entity_type": entity_type,
                "total_revenue": 0,
                "record_count": 0,
            }
        
        # Calculate statistics
        total_revenue = sum(r.amount_virtual for r in records)
        
        # Group by month for trend analysis
        monthly: dict[str, float] = defaultdict(float)
        for record in records:
            month_key = record.timestamp.strftime("%Y-%m")
            monthly[month_key] += record.amount_virtual
        
        # Find first and last revenue dates
        dates = [r.timestamp for r in records]
        first_revenue = min(dates)
        last_revenue = max(dates)
        
        # Calculate average monthly revenue
        months_active = max(1, len(monthly))
        avg_monthly = total_revenue / months_active
        
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "total_revenue": total_revenue,
            "record_count": len(records),
            "first_revenue": first_revenue.isoformat(),
            "last_revenue": last_revenue.isoformat(),
            "average_monthly_revenue": avg_monthly,
            "monthly_breakdown": dict(monthly),
        }
    
    async def estimate_entity_value(
        self,
        entity_id: str,
        entity_type: str,
        discount_rate: float = 0.1,
        growth_rate: float = 0.05,
    ) -> dict[str, Any]:
        """
        Estimate the value of an entity based on revenue.
        
        This uses a discounted cash flow (DCF) model to estimate the
        present value of future revenue streams. The estimate considers
        historical revenue, growth projections, and risk-adjusted
        discount rates. This is useful for tokenization pricing
        and investment decisions.
        
        Args:
            entity_id: ID of the entity to value
            entity_type: Type of entity
            discount_rate: Annual discount rate (default 10%)
            growth_rate: Expected annual growth rate (default 5%)
            
        Returns:
            Dict containing valuation estimates
        """
        revenue_data = await self.get_entity_revenue(entity_id, entity_type)
        
        avg_monthly = revenue_data.get("average_monthly_revenue", 0)
        annual_revenue = avg_monthly * 12
        
        if annual_revenue <= 0:
            return {
                "entity_id": entity_id,
                "estimated_value": 0,
                "method": "dcf",
                "note": "No revenue history",
            }
        
        # Calculate present value of growing perpetuity. This formula
        # provides a reasonable long-term valuation by discounting future
        # cash flows at the difference between discount and growth rates.
        # PV = CF / (r - g) where CF is cash flow, r is discount rate, g is growth rate
        if discount_rate <= growth_rate:
            # Fallback to simple multiple if growth exceeds discount
            estimated_value = annual_revenue * 10
        else:
            estimated_value = annual_revenue / (discount_rate - growth_rate)
        
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "estimated_value_virtual": estimated_value,
            "annual_revenue": annual_revenue,
            "discount_rate": discount_rate,
            "growth_rate": growth_rate,
            "method": "dcf_perpetuity",
            "confidence": "medium" if revenue_data["record_count"] > 10 else "low",
        }


# Global service instance
_revenue_service: Optional[RevenueService] = None


async def get_revenue_service(
    revenue_repository: Any = None,
) -> RevenueService:
    """Get the global revenue service instance."""
    global _revenue_service
    if _revenue_service is None:
        if revenue_repository is None:
            raise RevenueServiceError(
                "Repository required for first initialization"
            )
        _revenue_service = RevenueService(revenue_repository)
        await _revenue_service.initialize()
    return _revenue_service
