"""
Tests for Trust-Based Pricing Engine

Tests cover:
- PricingTier enum values
- PricingFactors dataclass
- PricingResult dataclass
- TrustBasedPricingEngine calculations
- Trust multiplier curve interpolation
- PageRank multipliers
- Influence, quality, demand, rarity, lineage, freshness multipliers
- Tier determination
- Lineage revenue distribution
- Singleton pattern
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.services.pricing_engine import (
    PricingFactors,
    PricingResult,
    PricingTier,
    TrustBasedPricingEngine,
    get_pricing_engine,
)


class TestPricingTier:
    """Tests for PricingTier enum."""

    def test_tier_values(self):
        """Test all tier enum values exist."""
        assert PricingTier.COMMODITY.value == "commodity"
        assert PricingTier.STANDARD.value == "standard"
        assert PricingTier.PREMIUM.value == "premium"
        assert PricingTier.EXCLUSIVE.value == "exclusive"
        assert PricingTier.FOUNDATIONAL.value == "foundational"

    def test_tier_is_string_enum(self):
        """Test tier is string enum for serialization."""
        assert isinstance(PricingTier.PREMIUM, str)
        assert PricingTier.PREMIUM == "premium"


class TestPricingFactors:
    """Tests for PricingFactors dataclass."""

    def test_default_values(self):
        """Test default pricing factors."""
        factors = PricingFactors()

        assert factors.trust_level == 50
        assert factors.pagerank_score == 0.0
        assert factors.betweenness_centrality == 0.0
        assert factors.citation_count == 0
        assert factors.derivative_count == 0
        assert factors.view_count == 0
        assert factors.search_appearances == 0
        assert factors.click_through_rate == 0.0
        assert factors.content_length == 0
        assert factors.has_sources is False
        assert factors.source_count == 0
        assert factors.contradiction_count == 0
        assert factors.similar_items_sold == 0
        assert factors.avg_similar_price == Decimal("0")
        assert factors.recent_sales_velocity == 0.0
        assert factors.lineage_depth == 0
        assert factors.lineage_trust_avg == 0.0
        assert factors.original_source is False
        assert factors.capsule_type == "KNOWLEDGE"
        assert factors.is_decision is False
        assert factors.is_governance is False
        assert factors.age_days == 0
        assert factors.last_updated_days == 0

    def test_custom_values(self):
        """Test custom pricing factors."""
        factors = PricingFactors(
            trust_level=80,
            pagerank_score=0.05,
            citation_count=25,
            original_source=True,
            capsule_type="DECISION",
        )

        assert factors.trust_level == 80
        assert factors.pagerank_score == 0.05
        assert factors.citation_count == 25
        assert factors.original_source is True
        assert factors.capsule_type == "DECISION"


class TestPricingResult:
    """Tests for PricingResult dataclass."""

    def test_pricing_result_creation(self):
        """Test PricingResult creation."""
        result = PricingResult(
            capsule_id="cap-123",
            suggested_price=Decimal("25.00"),
            minimum_price=Decimal("15.00"),
            maximum_price=Decimal("45.00"),
            confidence=0.85,
            pricing_tier=PricingTier.PREMIUM,
            tier_reason="High trust",
            base_price=Decimal("10.00"),
        )

        assert result.capsule_id == "cap-123"
        assert result.suggested_price == Decimal("25.00")
        assert result.minimum_price == Decimal("15.00")
        assert result.maximum_price == Decimal("45.00")
        assert result.confidence == 0.85
        assert result.pricing_tier == PricingTier.PREMIUM
        assert result.tier_reason == "High trust"
        assert result.base_price == Decimal("10.00")
        assert result.multipliers == {}
        assert result.adjustments == {}
        assert result.market_comparison == {}
        assert result.recommendations == []

    def test_pricing_result_with_multipliers(self):
        """Test PricingResult with multipliers and adjustments."""
        result = PricingResult(
            capsule_id="cap-456",
            suggested_price=Decimal("50.00"),
            minimum_price=Decimal("30.00"),
            maximum_price=Decimal("90.00"),
            confidence=0.90,
            pricing_tier=PricingTier.EXCLUSIVE,
            tier_reason="Original source",
            base_price=Decimal("10.00"),
            multipliers={"trust": 2.5, "pagerank": 1.5},
            adjustments={"original_source_bonus": Decimal("5.00")},
        )

        assert result.multipliers["trust"] == 2.5
        assert result.multipliers["pagerank"] == 1.5
        assert result.adjustments["original_source_bonus"] == Decimal("5.00")


class TestTrustBasedPricingEngine:
    """Tests for TrustBasedPricingEngine."""

    @pytest.fixture
    def engine(self):
        """Create a pricing engine for testing."""
        return TrustBasedPricingEngine()

    @pytest.fixture
    def engine_with_mocks(self):
        """Create a pricing engine with mocked dependencies."""
        graph_repo = AsyncMock()
        marketplace = AsyncMock()
        return TrustBasedPricingEngine(
            graph_repo=graph_repo,
            marketplace_service=marketplace,
        )

    # =========================================================================
    # Trust Multiplier Tests
    # =========================================================================

    def test_trust_multiplier_at_zero(self, engine):
        """Test trust multiplier at trust level 0."""
        mult = engine._calculate_trust_multiplier(0)
        assert mult == 0.25

    def test_trust_multiplier_at_20(self, engine):
        """Test trust multiplier at trust level 20."""
        mult = engine._calculate_trust_multiplier(20)
        assert mult == 0.50

    def test_trust_multiplier_at_40(self, engine):
        """Test trust multiplier at trust level 40."""
        mult = engine._calculate_trust_multiplier(40)
        assert mult == 1.00

    def test_trust_multiplier_at_60(self, engine):
        """Test trust multiplier at trust level 60."""
        mult = engine._calculate_trust_multiplier(60)
        assert mult == 1.75

    def test_trust_multiplier_at_80(self, engine):
        """Test trust multiplier at trust level 80."""
        mult = engine._calculate_trust_multiplier(80)
        assert mult == 2.50

    def test_trust_multiplier_at_100(self, engine):
        """Test trust multiplier at trust level 100."""
        mult = engine._calculate_trust_multiplier(100)
        assert mult == 3.50

    def test_trust_multiplier_interpolation(self, engine):
        """Test trust multiplier interpolation between levels."""
        # Trust 30 should be between 0.50 (at 20) and 1.00 (at 40)
        mult = engine._calculate_trust_multiplier(30)
        assert 0.50 < mult < 1.00
        # Linear interpolation: 0.50 + 0.5 * (1.00 - 0.50) = 0.75
        assert abs(mult - 0.75) < 0.01

    def test_trust_multiplier_clamping_negative(self, engine):
        """Test trust multiplier clamps negative values."""
        mult = engine._calculate_trust_multiplier(-10)
        assert mult == 0.25

    def test_trust_multiplier_clamping_over_100(self, engine):
        """Test trust multiplier clamps values over 100."""
        mult = engine._calculate_trust_multiplier(150)
        assert mult == 3.50

    # =========================================================================
    # PageRank Multiplier Tests
    # =========================================================================

    def test_pagerank_multiplier_zero(self, engine):
        """Test PageRank multiplier at zero."""
        mult = engine._calculate_pagerank_multiplier(0)
        assert mult == 0.8

    def test_pagerank_multiplier_negative(self, engine):
        """Test PageRank multiplier with negative value."""
        mult = engine._calculate_pagerank_multiplier(-0.01)
        assert mult == 0.8

    def test_pagerank_multiplier_very_low(self, engine):
        """Test PageRank multiplier at very low threshold."""
        mult = engine._calculate_pagerank_multiplier(0.00005)
        assert mult == 0.8

    def test_pagerank_multiplier_low(self, engine):
        """Test PageRank multiplier at low threshold."""
        mult = engine._calculate_pagerank_multiplier(0.0005)
        assert mult == 1.0

    def test_pagerank_multiplier_medium(self, engine):
        """Test PageRank multiplier at medium threshold."""
        mult = engine._calculate_pagerank_multiplier(0.005)
        assert 1.2 <= mult < 1.5

    def test_pagerank_multiplier_high(self, engine):
        """Test PageRank multiplier at high threshold."""
        mult = engine._calculate_pagerank_multiplier(0.03)
        assert 1.5 <= mult < 2.0

    def test_pagerank_multiplier_very_high(self, engine):
        """Test PageRank multiplier at very high threshold."""
        mult = engine._calculate_pagerank_multiplier(0.1)
        assert mult >= 2.0
        assert mult <= 3.0

    # =========================================================================
    # Influence Multiplier Tests
    # =========================================================================

    def test_influence_multiplier_no_influence(self, engine):
        """Test influence multiplier with no citations or derivatives."""
        mult = engine._calculate_influence_multiplier(0, 0)
        assert mult == 0.9

    def test_influence_multiplier_citations_only(self, engine):
        """Test influence multiplier with only citations."""
        mult = engine._calculate_influence_multiplier(10, 0)
        # 10 influence = 1.0 + 0.3 * log10(11) ~ 1.3
        assert 1.0 <= mult <= 1.4

    def test_influence_multiplier_derivatives_only(self, engine):
        """Test influence multiplier with only derivatives."""
        mult = engine._calculate_influence_multiplier(0, 5)
        # 10 influence (5 * 2) = 1.0 + 0.3 * log10(11) ~ 1.3
        assert 1.0 <= mult <= 1.4

    def test_influence_multiplier_high_influence(self, engine):
        """Test influence multiplier with high influence."""
        mult = engine._calculate_influence_multiplier(100, 50)
        # 200 influence = 1.0 + 0.3 * log10(201) ~ 1.69
        assert 1.5 <= mult <= 2.0

    def test_influence_multiplier_capped(self, engine):
        """Test influence multiplier is capped at 2.5."""
        mult = engine._calculate_influence_multiplier(10000, 5000)
        assert mult <= 2.5

    # =========================================================================
    # Quality Multiplier Tests
    # =========================================================================

    def test_quality_multiplier_default(self, engine):
        """Test quality multiplier with default factors."""
        factors = PricingFactors()
        mult = engine._calculate_quality_multiplier(factors)
        assert mult == 1.0

    def test_quality_multiplier_long_content(self, engine):
        """Test quality multiplier with long content."""
        factors = PricingFactors(content_length=5000)
        mult = engine._calculate_quality_multiplier(factors)
        assert mult > 1.0
        assert mult <= 1.20

    def test_quality_multiplier_with_sources(self, engine):
        """Test quality multiplier with sources."""
        factors = PricingFactors(has_sources=True, source_count=5)
        mult = engine._calculate_quality_multiplier(factors)
        # 5 sources * 0.03 = 0.15
        assert mult == 1.15

    def test_quality_multiplier_with_contradictions(self, engine):
        """Test quality multiplier penalty for contradictions."""
        factors = PricingFactors(contradiction_count=2)
        mult = engine._calculate_quality_multiplier(factors)
        # 2 * 0.10 = 0.20 penalty
        assert mult == 0.80

    def test_quality_multiplier_floor(self, engine):
        """Test quality multiplier floor at 0.5."""
        factors = PricingFactors(contradiction_count=10)
        mult = engine._calculate_quality_multiplier(factors)
        # Capped at 0.5
        assert mult == 0.5

    # =========================================================================
    # Demand Multiplier Tests
    # =========================================================================

    def test_demand_multiplier_no_views(self, engine):
        """Test demand multiplier with no views."""
        factors = PricingFactors(view_count=0)
        mult = engine._calculate_demand_multiplier(factors)
        assert mult == 0.9

    def test_demand_multiplier_with_views(self, engine):
        """Test demand multiplier with views."""
        factors = PricingFactors(view_count=100)
        mult = engine._calculate_demand_multiplier(factors)
        # 1.0 + log10(101) / 10 ~ 1.2
        assert mult >= 1.0

    def test_demand_multiplier_with_ctr(self, engine):
        """Test demand multiplier with click-through rate."""
        factors = PricingFactors(view_count=100, click_through_rate=0.1)
        mult = engine._calculate_demand_multiplier(factors)
        # Should include CTR bonus
        assert mult > 1.2

    def test_demand_multiplier_with_sales_velocity(self, engine):
        """Test demand multiplier with sales velocity."""
        factors = PricingFactors(view_count=100, recent_sales_velocity=2.0)
        mult = engine._calculate_demand_multiplier(factors)
        assert mult > 1.2

    def test_demand_multiplier_capped(self, engine):
        """Test demand multiplier is capped at 2.0."""
        factors = PricingFactors(
            view_count=1000000,
            click_through_rate=1.0,
            recent_sales_velocity=10.0,
        )
        mult = engine._calculate_demand_multiplier(factors)
        assert mult <= 2.0

    # =========================================================================
    # Rarity Multiplier Tests
    # =========================================================================

    def test_rarity_multiplier_original_source(self, engine):
        """Test rarity multiplier for original source."""
        factors = PricingFactors(original_source=True)
        mult = engine._calculate_rarity_multiplier(factors)
        assert mult == 1.5

    def test_rarity_multiplier_high_betweenness(self, engine):
        """Test rarity multiplier for high betweenness centrality."""
        factors = PricingFactors(betweenness_centrality=0.15)
        mult = engine._calculate_rarity_multiplier(factors)
        assert mult == 1.3

    def test_rarity_multiplier_many_similar_items(self, engine):
        """Test rarity multiplier penalty for many similar items."""
        factors = PricingFactors(similar_items_sold=30)
        mult = engine._calculate_rarity_multiplier(factors)
        # 1.0 - 30 * 0.01 = 0.70
        assert mult == 0.70

    def test_rarity_multiplier_floor(self, engine):
        """Test rarity multiplier floor."""
        factors = PricingFactors(similar_items_sold=100)
        mult = engine._calculate_rarity_multiplier(factors)
        # Floor at 0.70
        assert mult >= 0.70

    def test_rarity_multiplier_default(self, engine):
        """Test rarity multiplier default."""
        factors = PricingFactors()
        mult = engine._calculate_rarity_multiplier(factors)
        assert mult == 1.0

    # =========================================================================
    # Lineage Multiplier Tests
    # =========================================================================

    def test_lineage_multiplier_no_lineage(self, engine):
        """Test lineage multiplier with no lineage."""
        factors = PricingFactors(lineage_depth=0)
        mult = engine._calculate_lineage_multiplier(factors)
        assert mult == 1.0

    def test_lineage_multiplier_high_trust_lineage(self, engine):
        """Test lineage multiplier with high trust lineage."""
        factors = PricingFactors(lineage_depth=3, lineage_trust_avg=75)
        mult = engine._calculate_lineage_multiplier(factors)
        # 3 * 0.05 = 0.15 bonus
        assert mult == 1.15

    def test_lineage_multiplier_low_trust_lineage(self, engine):
        """Test lineage multiplier penalty for low trust lineage."""
        factors = PricingFactors(lineage_depth=3, lineage_trust_avg=30)
        mult = engine._calculate_lineage_multiplier(factors)
        # 3 * 0.03 = 0.09 penalty
        assert mult == 0.91

    def test_lineage_multiplier_bounds(self, engine):
        """Test lineage multiplier is bounded."""
        factors = PricingFactors(lineage_depth=20, lineage_trust_avg=90)
        mult = engine._calculate_lineage_multiplier(factors)
        assert mult <= 1.5

        factors2 = PricingFactors(lineage_depth=20, lineage_trust_avg=10)
        mult2 = engine._calculate_lineage_multiplier(factors2)
        assert mult2 >= 0.7

    # =========================================================================
    # Freshness Multiplier Tests
    # =========================================================================

    def test_freshness_multiplier_brand_new(self, engine):
        """Test freshness multiplier for brand new content."""
        mult = engine._calculate_freshness_multiplier(0, 0)
        assert mult == 1.2

    def test_freshness_multiplier_week_old(self, engine):
        """Test freshness multiplier for week-old content."""
        mult = engine._calculate_freshness_multiplier(5, 0)
        assert mult == 1.2

    def test_freshness_multiplier_month_old(self, engine):
        """Test freshness multiplier for month-old content."""
        mult = engine._calculate_freshness_multiplier(20, 0)
        assert mult == 1.1

    def test_freshness_multiplier_quarter_old(self, engine):
        """Test freshness multiplier for quarter-old content."""
        mult = engine._calculate_freshness_multiplier(60, 0)
        assert mult == 1.0

    def test_freshness_multiplier_half_year_old(self, engine):
        """Test freshness multiplier for half-year-old content."""
        mult = engine._calculate_freshness_multiplier(120, 0)
        assert mult == 0.95

    def test_freshness_multiplier_year_old(self, engine):
        """Test freshness multiplier for year-old content."""
        mult = engine._calculate_freshness_multiplier(300, 0)
        assert mult == 0.90

    def test_freshness_multiplier_very_old(self, engine):
        """Test freshness multiplier for very old content."""
        mult = engine._calculate_freshness_multiplier(730, 0)
        assert mult >= 0.75

    def test_freshness_multiplier_recently_updated(self, engine):
        """Test freshness uses last_updated if more recent."""
        mult = engine._calculate_freshness_multiplier(365, 5)
        assert mult == 1.2  # Uses last_updated (5 days)

    # =========================================================================
    # Tier Determination Tests
    # =========================================================================

    def test_determine_tier_foundational(self, engine):
        """Test foundational tier determination."""
        factors = PricingFactors(
            pagerank_score=0.06,  # > 0.05 (high)
            derivative_count=15,  # > 10
        )
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.FOUNDATIONAL
        assert "centrality" in reason.lower() or "derivative" in reason.lower()

    def test_determine_tier_exclusive(self, engine):
        """Test exclusive tier determination."""
        factors = PricingFactors(
            trust_level=85,  # >= 80
            original_source=True,
        )
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.EXCLUSIVE
        assert "original" in reason.lower() or "trust" in reason.lower()

    def test_determine_tier_premium_high_trust(self, engine):
        """Test premium tier with high trust."""
        factors = PricingFactors(trust_level=65)
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.PREMIUM

    def test_determine_tier_premium_high_pagerank(self, engine):
        """Test premium tier with high PageRank."""
        factors = PricingFactors(pagerank_score=0.015)
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.PREMIUM

    def test_determine_tier_commodity_low_trust(self, engine):
        """Test commodity tier with low trust."""
        factors = PricingFactors(trust_level=25)
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.COMMODITY

    def test_determine_tier_commodity_high_supply(self, engine):
        """Test commodity tier with high supply."""
        factors = PricingFactors(similar_items_sold=60)
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.COMMODITY

    def test_determine_tier_standard(self, engine):
        """Test standard tier default."""
        factors = PricingFactors(trust_level=50)
        tier, reason = engine._determine_tier(factors)
        assert tier == PricingTier.STANDARD

    # =========================================================================
    # Tier Adjustment Tests
    # =========================================================================

    def test_tier_adjustment_commodity(self, engine):
        """Test tier adjustment for commodity."""
        adj = engine._get_tier_adjustment(PricingTier.COMMODITY)
        assert adj == -0.15

    def test_tier_adjustment_standard(self, engine):
        """Test tier adjustment for standard."""
        adj = engine._get_tier_adjustment(PricingTier.STANDARD)
        assert adj == 0.0

    def test_tier_adjustment_premium(self, engine):
        """Test tier adjustment for premium."""
        adj = engine._get_tier_adjustment(PricingTier.PREMIUM)
        assert adj == 0.20

    def test_tier_adjustment_exclusive(self, engine):
        """Test tier adjustment for exclusive."""
        adj = engine._get_tier_adjustment(PricingTier.EXCLUSIVE)
        assert adj == 0.50

    def test_tier_adjustment_foundational(self, engine):
        """Test tier adjustment for foundational."""
        adj = engine._get_tier_adjustment(PricingTier.FOUNDATIONAL)
        assert adj == 0.75

    # =========================================================================
    # Minimum Floor Tests
    # =========================================================================

    def test_minimum_floor_quarantine(self, engine):
        """Test minimum floor for quarantine trust."""
        floor = engine._get_minimum_floor(15)
        assert floor == Decimal("1.00")

    def test_minimum_floor_sandbox(self, engine):
        """Test minimum floor for sandbox trust."""
        floor = engine._get_minimum_floor(30)
        assert floor == Decimal("3.00")

    def test_minimum_floor_standard(self, engine):
        """Test minimum floor for standard trust."""
        floor = engine._get_minimum_floor(50)
        assert floor == Decimal("5.00")

    def test_minimum_floor_trusted(self, engine):
        """Test minimum floor for trusted trust."""
        floor = engine._get_minimum_floor(70)
        assert floor == Decimal("10.00")

    # =========================================================================
    # Weighted Geometric Mean Tests
    # =========================================================================

    def test_weighted_geometric_mean_equal_weights(self, engine):
        """Test weighted geometric mean with equal weights."""
        multipliers = {"a": 2.0, "b": 2.0}
        weights = {"a": 0.5, "b": 0.5}
        result = engine._weighted_geometric_mean(multipliers, weights)
        assert abs(result - 2.0) < 0.01

    def test_weighted_geometric_mean_different_values(self, engine):
        """Test weighted geometric mean with different values."""
        multipliers = {"a": 1.0, "b": 4.0}
        weights = {"a": 0.5, "b": 0.5}
        result = engine._weighted_geometric_mean(multipliers, weights)
        # sqrt(1 * 4) = 2.0
        assert abs(result - 2.0) < 0.01

    def test_weighted_geometric_mean_handles_small_values(self, engine):
        """Test weighted geometric mean clamps very small values."""
        multipliers = {"a": 0.001, "b": 1.0}
        weights = {"a": 0.5, "b": 0.5}
        result = engine._weighted_geometric_mean(multipliers, weights)
        # Should clamp 0.001 to 0.01
        assert result > 0

    # =========================================================================
    # Calculate Price Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_calculate_price_basic(self, engine):
        """Test basic price calculation."""
        factors = PricingFactors(
            trust_level=60,
            capsule_type="KNOWLEDGE",
        )

        result = await engine.calculate_price("cap-123", factors)

        assert isinstance(result, PricingResult)
        assert result.capsule_id == "cap-123"
        assert result.suggested_price > Decimal("0")
        assert result.minimum_price < result.suggested_price
        assert result.maximum_price > result.suggested_price
        assert 0.0 <= result.confidence <= 1.0
        assert result.pricing_tier == PricingTier.PREMIUM  # trust >= 60
        assert result.base_price == Decimal("10.00")  # KNOWLEDGE base price

    @pytest.mark.asyncio
    async def test_calculate_price_decision_type(self, engine):
        """Test price calculation for DECISION type."""
        factors = PricingFactors(
            trust_level=70,
            capsule_type="DECISION",
            is_decision=True,
        )

        result = await engine.calculate_price("cap-456", factors)

        assert result.base_price == Decimal("25.00")  # DECISION base price
        assert "governance_premium" in result.adjustments

    @pytest.mark.asyncio
    async def test_calculate_price_governance_type(self, engine):
        """Test price calculation for GOVERNANCE type."""
        factors = PricingFactors(
            trust_level=80,
            capsule_type="GOVERNANCE",
            is_governance=True,
        )

        result = await engine.calculate_price("cap-789", factors)

        assert result.base_price == Decimal("100.00")  # GOVERNANCE base price
        assert "governance_premium" in result.adjustments

    @pytest.mark.asyncio
    async def test_calculate_price_with_contradictions(self, engine):
        """Test price calculation with contradictions."""
        factors = PricingFactors(
            trust_level=50,
            contradiction_count=2,
        )

        result = await engine.calculate_price("cap-abc", factors)

        assert "contradiction_penalty" in result.adjustments
        assert result.adjustments["contradiction_penalty"] < Decimal("0")

    @pytest.mark.asyncio
    async def test_calculate_price_original_source(self, engine):
        """Test price calculation for original source."""
        factors = PricingFactors(
            trust_level=85,
            original_source=True,
        )

        result = await engine.calculate_price("cap-original", factors)

        assert "original_source_bonus" in result.adjustments
        assert result.adjustments["original_source_bonus"] > Decimal("0")
        assert result.pricing_tier == PricingTier.EXCLUSIVE

    @pytest.mark.asyncio
    async def test_calculate_price_all_multipliers_tracked(self, engine):
        """Test all multipliers are tracked in result."""
        factors = PricingFactors(
            trust_level=70,
            pagerank_score=0.01,
            citation_count=10,
            content_length=1000,
            view_count=100,
            lineage_depth=2,
            lineage_trust_avg=65,
            age_days=30,
        )

        result = await engine.calculate_price("cap-full", factors)

        assert "trust" in result.multipliers
        assert "pagerank" in result.multipliers
        assert "influence" in result.multipliers
        assert "quality" in result.multipliers
        assert "demand" in result.multipliers
        assert "rarity" in result.multipliers
        assert "lineage" in result.multipliers
        assert "freshness" in result.multipliers

    @pytest.mark.asyncio
    async def test_calculate_price_minimum_floor_enforced(self, engine):
        """Test minimum floor is enforced."""
        factors = PricingFactors(
            trust_level=5,  # Very low trust
            contradiction_count=5,  # Many contradictions
            capsule_type="OBSERVATION",
        )

        result = await engine.calculate_price("cap-floor", factors)

        # Should not go below minimum floor of $1.00 for low trust
        assert result.suggested_price >= Decimal("1.00")

    @pytest.mark.asyncio
    async def test_calculate_price_fetches_factors_if_none(self, engine_with_mocks):
        """Test price calculation fetches factors if not provided."""
        engine_with_mocks.graph_repo.compute_pagerank = AsyncMock(return_value=[])

        result = await engine_with_mocks.calculate_price("cap-fetch")

        assert isinstance(result, PricingResult)
        engine_with_mocks.graph_repo.compute_pagerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_price_unknown_capsule_type(self, engine):
        """Test price calculation with unknown capsule type."""
        factors = PricingFactors(
            trust_level=50,
            capsule_type="UNKNOWN_TYPE",
        )

        result = await engine.calculate_price("cap-unknown", factors)

        # Should default to $10.00 base price
        assert result.base_price == Decimal("10.00")

    # =========================================================================
    # Market Comparison Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_market_comparison_with_similar_items(self, engine):
        """Test market comparison with similar items."""
        factors = PricingFactors(
            trust_level=60,
            similar_items_sold=25,
            avg_similar_price=Decimal("15.00"),
        )

        result = await engine.calculate_price("cap-market", factors)

        assert result.market_comparison["similar_listings"] == 25
        assert result.market_comparison["avg_price"] == 15.0
        assert result.market_comparison["price_range"]["min"] == 7.5
        assert result.market_comparison["price_range"]["max"] == 30.0

    @pytest.mark.asyncio
    async def test_market_comparison_no_similar_items(self, engine):
        """Test market comparison with no similar items."""
        factors = PricingFactors(trust_level=60)

        result = await engine.calculate_price("cap-no-market", factors)

        assert result.market_comparison["similar_listings"] == 0
        assert result.market_comparison["price_range"] is None

    # =========================================================================
    # Confidence Calculation Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_confidence_base(self, engine):
        """Test base confidence score."""
        factors = PricingFactors(trust_level=50)

        result = await engine.calculate_price("cap-conf", factors)

        assert result.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_confidence_high_data(self, engine):
        """Test confidence with high data availability."""
        factors = PricingFactors(
            trust_level=70,
            view_count=150,
            citation_count=10,
            similar_items_sold=20,
            pagerank_score=0.01,
        )

        result = await engine.calculate_price("cap-high-conf", factors)

        # Should have higher confidence with more data
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_confidence_reduced_by_contradictions(self, engine):
        """Test confidence reduced by contradictions."""
        factors_clean = PricingFactors(trust_level=60)
        factors_contradicted = PricingFactors(
            trust_level=60,
            contradiction_count=3,
        )

        result_clean = await engine.calculate_price("cap-clean", factors_clean)
        result_contradicted = await engine.calculate_price("cap-contradicted", factors_contradicted)

        assert result_contradicted.confidence < result_clean.confidence

    # =========================================================================
    # Recommendations Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_recommendations_low_trust(self, engine):
        """Test recommendations for low trust capsule."""
        factors = PricingFactors(trust_level=30)

        result = await engine.calculate_price("cap-low-trust", factors)

        # Should suggest improving trust
        trust_recs = [r for r in result.recommendations if "trust" in r.lower()]
        assert len(trust_recs) > 0

    @pytest.mark.asyncio
    async def test_recommendations_no_citations(self, engine):
        """Test recommendations for capsule with no citations."""
        factors = PricingFactors(trust_level=60, citation_count=0)

        result = await engine.calculate_price("cap-no-cite", factors)

        # Should suggest adding citations
        cite_recs = [r for r in result.recommendations if "citation" in r.lower()]
        assert len(cite_recs) > 0

    @pytest.mark.asyncio
    async def test_recommendations_stale_content(self, engine):
        """Test recommendations for stale content."""
        factors = PricingFactors(
            trust_level=60,
            last_updated_days=200,
        )

        result = await engine.calculate_price("cap-stale", factors)

        # Should suggest updating
        update_recs = [r for r in result.recommendations if "updat" in r.lower()]
        assert len(update_recs) > 0

    @pytest.mark.asyncio
    async def test_recommendations_original_source(self, engine):
        """Test recommendations for original source."""
        factors = PricingFactors(
            trust_level=85,
            original_source=True,
        )

        result = await engine.calculate_price("cap-orig-rec", factors)

        # Should suggest exclusive pricing
        orig_recs = [r for r in result.recommendations if "exclusive" in r.lower()]
        assert len(orig_recs) > 0

    @pytest.mark.asyncio
    async def test_recommendations_max_five(self, engine):
        """Test recommendations capped at 5."""
        factors = PricingFactors(
            trust_level=30,
            citation_count=0,
            last_updated_days=200,
            original_source=True,
        )

        result = await engine.calculate_price("cap-many-recs", factors)

        assert len(result.recommendations) <= 5

    # =========================================================================
    # Lineage Distribution Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_lineage_distribution_no_repo(self, engine):
        """Test lineage distribution without graph repo."""
        distributions = await engine.calculate_lineage_distribution(
            "cap-123",
            Decimal("100.00"),
        )

        assert distributions == []

    @pytest.mark.asyncio
    async def test_lineage_distribution_no_lineage(self, engine_with_mocks):
        """Test lineage distribution with no lineage."""
        engine_with_mocks._get_lineage_chain = AsyncMock(return_value=[])

        distributions = await engine_with_mocks.calculate_lineage_distribution(
            "cap-456",
            Decimal("100.00"),
        )

        assert distributions == []

    @pytest.mark.asyncio
    async def test_lineage_distribution_single_ancestor(self, engine_with_mocks):
        """Test lineage distribution with single ancestor."""
        engine_with_mocks._get_lineage_chain = AsyncMock(return_value=[
            {"depth": 1, "owner_id": "user-1", "capsule_id": "cap-ancestor"},
        ])

        distributions = await engine_with_mocks.calculate_lineage_distribution(
            "cap-789",
            Decimal("100.00"),
        )

        assert len(distributions) == 1
        assert distributions[0]["user_id"] == "user-1"
        assert distributions[0]["depth"] == 1
        # Depth 1 gets 40% weight
        assert distributions[0]["amount"] == Decimal("100.00")  # Normalized to full share

    @pytest.mark.asyncio
    async def test_lineage_distribution_multiple_ancestors(self, engine_with_mocks):
        """Test lineage distribution with multiple ancestors."""
        engine_with_mocks._get_lineage_chain = AsyncMock(return_value=[
            {"depth": 1, "owner_id": "user-1", "capsule_id": "cap-a1"},
            {"depth": 2, "owner_id": "user-2", "capsule_id": "cap-a2"},
            {"depth": 3, "owner_id": "user-3", "capsule_id": "cap-a3"},
        ])

        distributions = await engine_with_mocks.calculate_lineage_distribution(
            "cap-multi",
            Decimal("100.00"),
        )

        assert len(distributions) == 3
        # Check weights are applied
        total_amount = sum(d["amount"] for d in distributions)
        assert abs(total_amount - Decimal("100.00")) < Decimal("0.05")

    @pytest.mark.asyncio
    async def test_lineage_distribution_handles_error(self, engine_with_mocks):
        """Test lineage distribution handles errors gracefully."""
        engine_with_mocks._get_lineage_chain = AsyncMock(
            side_effect=ValueError("Database error")
        )

        distributions = await engine_with_mocks.calculate_lineage_distribution(
            "cap-error",
            Decimal("100.00"),
        )

        assert distributions == []

    # =========================================================================
    # Singleton Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_pricing_engine_singleton(self):
        """Test get_pricing_engine returns singleton."""
        # Reset singleton
        import forge.services.pricing_engine as pe_module
        pe_module._pricing_engine = None

        engine1 = await get_pricing_engine()
        engine2 = await get_pricing_engine()

        assert engine1 is engine2

        # Cleanup
        pe_module._pricing_engine = None


class TestPricingEdgeCases:
    """Edge case tests for pricing engine."""

    @pytest.fixture
    def engine(self):
        return TrustBasedPricingEngine()

    @pytest.mark.asyncio
    async def test_price_range_calculations(self, engine):
        """Test price range is correctly calculated."""
        factors = PricingFactors(trust_level=60)

        result = await engine.calculate_price("cap-range", factors)

        # Min should be 60% of suggested
        expected_min = (result.suggested_price * Decimal("0.60")).quantize(Decimal("0.01"))
        assert result.minimum_price == expected_min

        # Max should be 180% of suggested
        expected_max = (result.suggested_price * Decimal("1.80")).quantize(Decimal("0.01"))
        assert result.maximum_price == expected_max

    @pytest.mark.asyncio
    async def test_all_capsule_types_have_base_price(self, engine):
        """Test all known capsule types have defined base prices."""
        types = ["OBSERVATION", "KNOWLEDGE", "DECISION", "INSIGHT",
                 "PROTOCOL", "POLICY", "GOVERNANCE"]

        for capsule_type in types:
            factors = PricingFactors(trust_level=50, capsule_type=capsule_type)
            result = await engine.calculate_price(f"cap-{capsule_type}", factors)

            assert result.base_price > Decimal("0")
            assert result.base_price == engine.BASE_PRICES.get(capsule_type)

    @pytest.mark.asyncio
    async def test_extreme_values_dont_crash(self, engine):
        """Test engine handles extreme values."""
        factors = PricingFactors(
            trust_level=100,
            pagerank_score=1.0,
            citation_count=100000,
            derivative_count=50000,
            view_count=10000000,
            content_length=1000000,
            source_count=1000,
            similar_items_sold=1000,
            avg_similar_price=Decimal("10000.00"),
            lineage_depth=100,
            lineage_trust_avg=100,
            age_days=10000,
        )

        result = await engine.calculate_price("cap-extreme", factors)

        assert isinstance(result, PricingResult)
        assert result.suggested_price > Decimal("0")
        assert not result.suggested_price.is_nan()
        assert not result.suggested_price.is_infinite()
