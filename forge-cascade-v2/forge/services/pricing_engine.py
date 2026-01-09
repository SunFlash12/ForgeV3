"""
Trust-Based Pricing Engine

Sophisticated pricing algorithm for knowledge capsules based on:
- PageRank and centrality scores
- Trust level and reputation
- Supply/demand dynamics
- Lineage quality and depth
- Historical market data
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PricingTier(str, Enum):
    """Pricing tiers based on capsule characteristics."""
    COMMODITY = "commodity"           # Low uniqueness, high supply
    STANDARD = "standard"             # Normal marketplace item
    PREMIUM = "premium"               # High trust/quality
    EXCLUSIVE = "exclusive"           # Very rare or authoritative
    FOUNDATIONAL = "foundational"     # High PageRank, many derivatives


@dataclass
class PricingFactors:
    """All factors that influence pricing."""
    # Core metrics
    trust_level: int = 50
    pagerank_score: float = 0.0
    betweenness_centrality: float = 0.0
    citation_count: int = 0
    derivative_count: int = 0

    # Engagement metrics
    view_count: int = 0
    search_appearances: int = 0
    click_through_rate: float = 0.0

    # Quality indicators
    content_length: int = 0
    has_sources: bool = False
    source_count: int = 0
    contradiction_count: int = 0

    # Market data
    similar_items_sold: int = 0
    avg_similar_price: Decimal = Decimal("0")
    recent_sales_velocity: float = 0.0

    # Lineage
    lineage_depth: int = 0
    lineage_trust_avg: float = 0.0
    original_source: bool = False

    # Type-specific
    capsule_type: str = "KNOWLEDGE"
    is_decision: bool = False
    is_governance: bool = False

    # Time factors
    age_days: int = 0
    last_updated_days: int = 0


@dataclass
class PricingResult:
    """Complete pricing recommendation."""
    capsule_id: str

    # Price recommendations
    suggested_price: Decimal
    minimum_price: Decimal
    maximum_price: Decimal
    confidence: float  # 0-1 confidence in the suggestion

    # Tier and explanation
    pricing_tier: PricingTier
    tier_reason: str

    # Breakdown
    base_price: Decimal
    multipliers: dict[str, float] = field(default_factory=dict)
    adjustments: dict[str, Decimal] = field(default_factory=dict)

    # Market context
    market_comparison: dict[str, Any] = field(default_factory=dict)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TrustBasedPricingEngine:
    """
    Advanced pricing engine that values capsules based on trust metrics,
    graph centrality, market dynamics, and lineage quality.
    """

    # Base prices by capsule type (in FORGE tokens)
    BASE_PRICES = {
        "OBSERVATION": Decimal("5.00"),
        "KNOWLEDGE": Decimal("10.00"),
        "DECISION": Decimal("25.00"),
        "INSIGHT": Decimal("15.00"),
        "PROTOCOL": Decimal("50.00"),
        "POLICY": Decimal("75.00"),
        "GOVERNANCE": Decimal("100.00"),
    }

    # Trust level multiplier curve (0-100 -> multiplier)
    TRUST_CURVE = [
        (0, 0.25),      # Quarantine
        (20, 0.50),     # Sandbox
        (40, 1.00),     # Standard
        (60, 1.75),     # Trusted
        (80, 2.50),     # Core
        (100, 3.50),    # Maximum
    ]

    # PageRank value thresholds
    PAGERANK_THRESHOLDS = {
        "very_low": 0.0001,
        "low": 0.001,
        "medium": 0.01,
        "high": 0.05,
        "very_high": 0.1,
    }

    def __init__(self, graph_repo=None, marketplace_service=None):
        self.graph_repo = graph_repo
        self.marketplace = marketplace_service

    async def calculate_price(
        self,
        capsule_id: str,
        factors: PricingFactors | None = None,
    ) -> PricingResult:
        """
        Calculate comprehensive pricing for a capsule.

        Args:
            capsule_id: The capsule to price
            factors: Pre-computed factors (or will be fetched)

        Returns:
            Complete pricing recommendation
        """
        # Fetch factors if not provided
        if factors is None:
            factors = await self._fetch_pricing_factors(capsule_id)

        # Determine pricing tier
        tier, tier_reason = self._determine_tier(factors)

        # Get base price for capsule type
        base_price = self.BASE_PRICES.get(
            factors.capsule_type.upper(),
            Decimal("10.00")
        )

        # Calculate multipliers
        multipliers = {}

        # 1. Trust multiplier (most important factor)
        multipliers["trust"] = self._calculate_trust_multiplier(factors.trust_level)

        # 2. PageRank multiplier (network importance)
        multipliers["pagerank"] = self._calculate_pagerank_multiplier(factors.pagerank_score)

        # 3. Citation/influence multiplier
        multipliers["influence"] = self._calculate_influence_multiplier(
            factors.citation_count,
            factors.derivative_count,
        )

        # 4. Quality multiplier
        multipliers["quality"] = self._calculate_quality_multiplier(factors)

        # 5. Demand multiplier
        multipliers["demand"] = self._calculate_demand_multiplier(factors)

        # 6. Rarity/scarcity multiplier
        multipliers["rarity"] = self._calculate_rarity_multiplier(factors)

        # 7. Lineage multiplier
        multipliers["lineage"] = self._calculate_lineage_multiplier(factors)

        # 8. Freshness multiplier (decay over time)
        multipliers["freshness"] = self._calculate_freshness_multiplier(
            factors.age_days,
            factors.last_updated_days,
        )

        # Calculate combined multiplier (weighted geometric mean)
        weights = {
            "trust": 0.30,       # 30% weight
            "pagerank": 0.15,    # 15% weight
            "influence": 0.15,  # 15% weight
            "quality": 0.10,    # 10% weight
            "demand": 0.10,     # 10% weight
            "rarity": 0.10,     # 10% weight
            "lineage": 0.05,    # 5% weight
            "freshness": 0.05,  # 5% weight
        }

        combined_multiplier = self._weighted_geometric_mean(multipliers, weights)

        # Calculate raw suggested price
        raw_price = base_price * Decimal(str(combined_multiplier))

        # Apply adjustments
        adjustments = {}

        # Contradiction penalty
        if factors.contradiction_count > 0:
            penalty = min(Decimal("0.20") * factors.contradiction_count, Decimal("0.50"))
            adjustments["contradiction_penalty"] = -raw_price * penalty

        # Original source bonus
        if factors.original_source:
            adjustments["original_source_bonus"] = raw_price * Decimal("0.25")

        # Decision/governance premium
        if factors.is_decision or factors.is_governance:
            adjustments["governance_premium"] = raw_price * Decimal("0.15")

        # Apply tier-specific adjustments
        tier_adjustment = self._get_tier_adjustment(tier)
        adjustments["tier_adjustment"] = raw_price * Decimal(str(tier_adjustment))

        # Sum adjustments
        total_adjustments = sum(adjustments.values())

        # Final suggested price
        suggested_price = (raw_price + total_adjustments).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # Ensure minimum floor
        minimum_floor = self._get_minimum_floor(factors.trust_level)
        suggested_price = max(suggested_price, minimum_floor)

        # Calculate price range
        min_price = (suggested_price * Decimal("0.60")).quantize(Decimal("0.01"))
        max_price = (suggested_price * Decimal("1.80")).quantize(Decimal("0.01"))

        # Market comparison
        market_comparison = await self._get_market_comparison(factors)

        # Calculate confidence
        confidence = self._calculate_confidence(factors, market_comparison)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            factors, suggested_price, market_comparison
        )

        return PricingResult(
            capsule_id=capsule_id,
            suggested_price=suggested_price,
            minimum_price=min_price,
            maximum_price=max_price,
            confidence=confidence,
            pricing_tier=tier,
            tier_reason=tier_reason,
            base_price=base_price,
            multipliers=multipliers,
            adjustments={k: float(v) for k, v in adjustments.items()},
            market_comparison=market_comparison,
            recommendations=recommendations,
        )

    def _determine_tier(self, factors: PricingFactors) -> tuple[PricingTier, str]:
        """Determine the pricing tier based on capsule characteristics."""
        # Foundational: High PageRank with many derivatives
        if (factors.pagerank_score > self.PAGERANK_THRESHOLDS["high"]
            and factors.derivative_count > 10):
            return PricingTier.FOUNDATIONAL, "High network centrality with significant derivatives"

        # Exclusive: Very high trust + original source
        if factors.trust_level >= 80 and factors.original_source:
            return PricingTier.EXCLUSIVE, "Authoritative original source with maximum trust"

        # Premium: High trust or high PageRank
        if factors.trust_level >= 60 or factors.pagerank_score > self.PAGERANK_THRESHOLDS["medium"]:
            return PricingTier.PREMIUM, "Elevated trust or significant network importance"

        # Commodity: Low trust or high supply
        if factors.trust_level < 30 or factors.similar_items_sold > 50:
            return PricingTier.COMMODITY, "Lower trust level or high market supply"

        return PricingTier.STANDARD, "Standard marketplace item"

    def _calculate_trust_multiplier(self, trust_level: int) -> float:
        """
        Calculate trust multiplier using interpolated curve.

        Trust is the most important factor - higher trust means
        the capsule is more verified and valuable.
        """
        # Clamp trust level
        trust_level = max(0, min(100, trust_level))

        # Find interpolation points
        for i, (threshold, mult) in enumerate(self.TRUST_CURVE):
            if trust_level <= threshold:
                if i == 0:
                    return mult
                # Linear interpolation
                prev_threshold, prev_mult = self.TRUST_CURVE[i - 1]
                ratio = (trust_level - prev_threshold) / (threshold - prev_threshold)
                return prev_mult + ratio * (mult - prev_mult)

        # Above max threshold
        return self.TRUST_CURVE[-1][1]

    def _calculate_pagerank_multiplier(self, pagerank: float) -> float:
        """
        Calculate PageRank multiplier.

        Higher PageRank = more central to the knowledge graph = more valuable.
        """
        if pagerank <= 0:
            return 0.8  # Slight penalty for no PageRank data

        # Logarithmic scale to handle wide range
        # Very low: 0.8x, Low: 1.0x, Medium: 1.5x, High: 2.0x, Very high: 3.0x
        if pagerank < self.PAGERANK_THRESHOLDS["very_low"]:
            return 0.8
        elif pagerank < self.PAGERANK_THRESHOLDS["low"]:
            return 1.0
        elif pagerank < self.PAGERANK_THRESHOLDS["medium"]:
            return 1.2 + 0.3 * math.log10(pagerank / self.PAGERANK_THRESHOLDS["low"])
        elif pagerank < self.PAGERANK_THRESHOLDS["high"]:
            return 1.5 + 0.5 * math.log10(pagerank / self.PAGERANK_THRESHOLDS["medium"])
        else:
            return min(3.0, 2.0 + 0.5 * math.log10(pagerank / self.PAGERANK_THRESHOLDS["high"]))

    def _calculate_influence_multiplier(
        self,
        citations: int,
        derivatives: int,
    ) -> float:
        """
        Calculate influence multiplier based on citations and derivatives.

        Being cited or derived from indicates the capsule has value.
        """
        # Combined influence score
        influence = citations + derivatives * 2  # Derivatives worth 2x citations

        if influence == 0:
            return 0.9  # Slight penalty for no influence

        # Logarithmic curve to prevent extreme values
        # 1 influence: 1.0x, 10: 1.3x, 100: 1.6x, 1000: 2.0x
        return min(2.5, 1.0 + 0.3 * math.log10(influence + 1))

    def _calculate_quality_multiplier(self, factors: PricingFactors) -> float:
        """
        Calculate quality multiplier based on content characteristics.
        """
        multiplier = 1.0

        # Content length bonus (up to 20%)
        if factors.content_length > 500:
            multiplier += min(0.20, factors.content_length / 10000)

        # Source citation bonus (up to 15%)
        if factors.has_sources and factors.source_count > 0:
            multiplier += min(0.15, factors.source_count * 0.03)

        # Contradiction penalty (up to 30%)
        if factors.contradiction_count > 0:
            multiplier -= min(0.30, factors.contradiction_count * 0.10)

        return max(0.5, multiplier)  # Floor at 0.5x

    def _calculate_demand_multiplier(self, factors: PricingFactors) -> float:
        """
        Calculate demand multiplier based on engagement metrics.
        """
        # Base on views and CTR
        if factors.view_count == 0:
            return 0.9

        # View-based component
        view_mult = 1.0 + math.log10(factors.view_count + 1) / 10

        # CTR bonus (if tracked)
        if factors.click_through_rate > 0:
            view_mult += factors.click_through_rate * 0.5

        # Sales velocity component
        if factors.recent_sales_velocity > 0:
            view_mult += min(0.3, factors.recent_sales_velocity * 0.1)

        return min(2.0, view_mult)

    def _calculate_rarity_multiplier(self, factors: PricingFactors) -> float:
        """
        Calculate rarity multiplier based on uniqueness and supply.
        """
        # Original sources are rare
        if factors.original_source:
            return 1.5

        # High betweenness = bridge between communities = rare position
        if factors.betweenness_centrality > 0.1:
            return 1.3

        # Many similar items = lower rarity
        if factors.similar_items_sold > 20:
            return max(0.7, 1.0 - factors.similar_items_sold * 0.01)

        return 1.0

    def _calculate_lineage_multiplier(self, factors: PricingFactors) -> float:
        """
        Calculate lineage multiplier based on provenance quality.
        """
        multiplier = 1.0

        # Lineage depth (derived from high-quality sources)
        if factors.lineage_depth > 0:
            # Being derived from something is valuable if the average trust is high
            if factors.lineage_trust_avg > 60:
                multiplier += min(0.3, factors.lineage_depth * 0.05)
            elif factors.lineage_trust_avg < 40:
                multiplier -= min(0.2, factors.lineage_depth * 0.03)

        return max(0.7, min(1.5, multiplier))

    def _calculate_freshness_multiplier(
        self,
        age_days: int,
        last_updated_days: int,
    ) -> float:
        """
        Calculate freshness multiplier - newer/updated content is more valuable.
        """
        # Use the more favorable of age or last update
        effective_age = min(age_days, last_updated_days) if last_updated_days > 0 else age_days

        if effective_age < 7:
            return 1.2  # Fresh content bonus
        elif effective_age < 30:
            return 1.1
        elif effective_age < 90:
            return 1.0
        elif effective_age < 180:
            return 0.95
        elif effective_age < 365:
            return 0.90
        else:
            return max(0.75, 0.90 - (effective_age - 365) / 3650)  # Slow decay

    def _weighted_geometric_mean(
        self,
        multipliers: dict[str, float],
        weights: dict[str, float],
    ) -> float:
        """Calculate weighted geometric mean of multipliers."""
        total_weight = sum(weights.values())

        log_sum = sum(
            weights.get(k, 0) * math.log(max(0.01, v))
            for k, v in multipliers.items()
        )

        return math.exp(log_sum / total_weight)

    def _get_tier_adjustment(self, tier: PricingTier) -> float:
        """Get price adjustment factor for tier."""
        adjustments = {
            PricingTier.COMMODITY: -0.15,
            PricingTier.STANDARD: 0.0,
            PricingTier.PREMIUM: 0.20,
            PricingTier.EXCLUSIVE: 0.50,
            PricingTier.FOUNDATIONAL: 0.75,
        }
        return adjustments.get(tier, 0.0)

    def _get_minimum_floor(self, trust_level: int) -> Decimal:
        """Get minimum price floor based on trust level."""
        if trust_level < 20:
            return Decimal("1.00")
        elif trust_level < 40:
            return Decimal("3.00")
        elif trust_level < 60:
            return Decimal("5.00")
        else:
            return Decimal("10.00")

    async def _fetch_pricing_factors(self, capsule_id: str) -> PricingFactors:
        """Fetch all pricing factors from repositories."""
        factors = PricingFactors()

        # Would fetch from graph repository and capsule repository
        # This is a stub - in production, would query Neo4j
        if self.graph_repo:
            try:
                # Get PageRank
                rankings = await self.graph_repo.compute_pagerank()
                for r in rankings:
                    if r.node_id == capsule_id:
                        factors.pagerank_score = r.score
                        break
            except Exception as e:
                logger.warning(f"Failed to fetch PageRank: {e}")

        return factors

    async def _get_market_comparison(
        self,
        factors: PricingFactors,
    ) -> dict[str, Any]:
        """Get market comparison data for similar capsules."""
        return {
            "similar_listings": factors.similar_items_sold,
            "avg_price": float(factors.avg_similar_price),
            "price_range": {
                "min": float(factors.avg_similar_price * Decimal("0.5")),
                "max": float(factors.avg_similar_price * Decimal("2.0")),
            } if factors.avg_similar_price > 0 else None,
        }

    def _calculate_confidence(
        self,
        factors: PricingFactors,
        market_comparison: dict[str, Any],
    ) -> float:
        """Calculate confidence score for the price suggestion."""
        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if factors.view_count > 100:
            confidence += 0.1
        if factors.citation_count > 5:
            confidence += 0.1
        if market_comparison.get("similar_listings", 0) > 10:
            confidence += 0.15
        if factors.pagerank_score > 0:
            confidence += 0.1

        # High trust = higher confidence
        if factors.trust_level >= 60:
            confidence += 0.1

        # Contradictions reduce confidence
        if factors.contradiction_count > 0:
            confidence -= 0.1 * factors.contradiction_count

        return max(0.1, min(0.95, confidence))

    def _generate_recommendations(
        self,
        factors: PricingFactors,
        suggested_price: Decimal,
        market_comparison: dict[str, Any],
    ) -> list[str]:
        """Generate pricing recommendations for the seller."""
        recommendations = []

        # Trust-based recommendations
        if factors.trust_level < 40:
            recommendations.append(
                "Consider improving capsule trust level before listing - "
                "higher trust capsules command premium prices"
            )

        # Market positioning
        avg_price = market_comparison.get("avg_price", 0)
        if avg_price > 0:
            if float(suggested_price) > avg_price * 1.5:
                recommendations.append(
                    "Suggested price is above market average - "
                    "ensure capsule quality justifies premium"
                )
            elif float(suggested_price) < avg_price * 0.7:
                recommendations.append(
                    "Suggested price is below market average - "
                    "consider if capsule has unique value not captured"
                )

        # Citation recommendations
        if factors.citation_count == 0:
            recommendations.append(
                "Capsule has no citations - linking to other capsules "
                "can increase perceived value"
            )

        # Freshness recommendations
        if factors.last_updated_days > 180:
            recommendations.append(
                "Capsule hasn't been updated in 6+ months - "
                "updating content can increase freshness multiplier"
            )

        # Lineage recommendations
        if factors.original_source:
            recommendations.append(
                "This is an original source - consider EXCLUSIVE pricing tier"
            )

        return recommendations[:5]  # Max 5 recommendations

    # =========================================================================
    # Lineage Revenue Distribution
    # =========================================================================

    async def calculate_lineage_distribution(
        self,
        capsule_id: str,
        total_lineage_share: Decimal,
    ) -> list[dict[str, Any]]:
        """
        Calculate how lineage revenue should be distributed to contributors.

        Uses depth-weighted distribution where earlier contributors
        receive larger shares.
        """
        distributions = []

        if not self.graph_repo:
            return distributions

        try:
            # Get lineage chain
            # In production, would query: MATCH path = (c:Capsule {id: $id})-[:DERIVED_FROM*1..10]->(ancestor)
            lineage = await self._get_lineage_chain(capsule_id)

            if not lineage:
                return distributions

            # Calculate weights based on depth
            # Depth 1: 40%, Depth 2: 25%, Depth 3: 15%, Depth 4+: remaining split
            depth_weights = {
                1: Decimal("0.40"),
                2: Decimal("0.25"),
                3: Decimal("0.15"),
                4: Decimal("0.10"),
            }
            remaining_weight = Decimal("0.10")  # For depth 5+

            total_weight = Decimal("0")
            for ancestor in lineage:
                depth = ancestor.get("depth", 1)
                weight = depth_weights.get(depth, remaining_weight / max(1, len(lineage) - 4))
                total_weight += weight

                distributions.append({
                    "user_id": ancestor.get("owner_id"),
                    "capsule_id": ancestor.get("capsule_id"),
                    "depth": depth,
                    "weight": float(weight),
                    "amount": total_lineage_share * weight,
                })

            # Normalize to ensure total equals lineage_share
            if total_weight > 0:
                for d in distributions:
                    d["amount"] = (Decimal(str(d["weight"])) / total_weight * total_lineage_share).quantize(Decimal("0.01"))

        except Exception as e:
            logger.warning(f"Failed to calculate lineage distribution: {e}")

        return distributions

    async def _get_lineage_chain(self, capsule_id: str) -> list[dict[str, Any]]:
        """Get the lineage chain for a capsule."""
        # Stub - would query Neo4j
        return []


# Singleton
_pricing_engine: TrustBasedPricingEngine | None = None


async def get_pricing_engine() -> TrustBasedPricingEngine:
    """Get the pricing engine singleton."""
    global _pricing_engine
    if _pricing_engine is None:
        _pricing_engine = TrustBasedPricingEngine()
    return _pricing_engine
