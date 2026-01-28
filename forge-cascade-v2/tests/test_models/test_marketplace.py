"""
Marketplace Model Tests for Forge Cascade V2

Comprehensive tests for marketplace models including:
- All enum validations (ListingStatus, LicenseType, Currency, etc.)
- CapsuleListing model validation
- Purchase and Cart models
- License and PriceSuggestion models
- RevenueDistribution and MarketplaceStats models
- Cart total calculation with currency validation
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from forge.models.marketplace import (
    CapsuleListing,
    Cart,
    CartItem,
    Currency,
    License,
    LicenseType,
    ListingStatus,
    ListingVisibility,
    MarketplaceStats,
    PaymentMethod,
    PaymentStatus,
    PriceSuggestion,
    Purchase,
    RevenueDistribution,
)


# =============================================================================
# Enum Tests
# =============================================================================


class TestListingStatusEnum:
    """Tests for ListingStatus enum."""

    def test_listing_status_values(self):
        """ListingStatus has expected values."""
        assert ListingStatus.DRAFT.value == "draft"
        assert ListingStatus.ACTIVE.value == "active"
        assert ListingStatus.SOLD.value == "sold"
        assert ListingStatus.EXPIRED.value == "expired"
        assert ListingStatus.CANCELLED.value == "cancelled"

    def test_listing_status_is_string_enum(self):
        """ListingStatus is a string enum."""
        assert isinstance(ListingStatus.DRAFT, str)
        assert ListingStatus.DRAFT == "draft"


class TestLicenseTypeEnum:
    """Tests for LicenseType enum."""

    def test_license_type_values(self):
        """LicenseType has expected values."""
        assert LicenseType.PERPETUAL.value == "perpetual"
        assert LicenseType.SUBSCRIPTION.value == "subscription"
        assert LicenseType.USAGE.value == "usage"
        assert LicenseType.DERIVATIVE.value == "derivative"

    def test_license_type_count(self):
        """All license types are present."""
        assert len(LicenseType) == 4


class TestCurrencyEnum:
    """Tests for Currency enum."""

    def test_currency_values(self):
        """Currency has expected values."""
        assert Currency.FORGE.value == "FORGE"
        assert Currency.USD.value == "USD"
        assert Currency.SOL.value == "SOL"
        assert Currency.ETH.value == "ETH"

    def test_currency_is_string_enum(self):
        """Currency is a string enum."""
        assert isinstance(Currency.FORGE, str)
        assert Currency.FORGE == "FORGE"


class TestListingVisibilityEnum:
    """Tests for ListingVisibility enum."""

    def test_visibility_values(self):
        """ListingVisibility has expected values."""
        assert ListingVisibility.PUBLIC.value == "public"
        assert ListingVisibility.UNLISTED.value == "unlisted"
        assert ListingVisibility.PRIVATE.value == "private"


class TestPaymentMethodEnum:
    """Tests for PaymentMethod enum."""

    def test_payment_method_values(self):
        """PaymentMethod has expected values."""
        assert PaymentMethod.PLATFORM.value == "platform"
        assert PaymentMethod.BLOCKCHAIN.value == "blockchain"


class TestPaymentStatusEnum:
    """Tests for PaymentStatus enum."""

    def test_payment_status_values(self):
        """PaymentStatus has expected values."""
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.COMPLETED.value == "completed"
        assert PaymentStatus.FAILED.value == "failed"
        assert PaymentStatus.REFUNDED.value == "refunded"


# =============================================================================
# CapsuleListing Tests
# =============================================================================


class TestCapsuleListing:
    """Tests for CapsuleListing model."""

    def test_valid_listing(self):
        """Valid listing creates model."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("100.00"),
            title="Test Capsule",
        )
        assert listing.capsule_id == "cap-123"
        assert listing.seller_id == "user-456"
        assert listing.price == Decimal("100.00")
        assert listing.title == "Test Capsule"

    def test_default_values(self):
        """Listing has sensible defaults."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("50.00"),
            title="Test",
        )
        assert listing.id is not None  # Auto-generated
        assert listing.currency == Currency.FORGE
        assert listing.license_type == LicenseType.PERPETUAL
        assert listing.status == ListingStatus.DRAFT
        assert listing.featured is False
        assert listing.visibility == ListingVisibility.PUBLIC
        assert listing.tags == []
        assert listing.view_count == 0
        assert listing.purchase_count == 0
        assert listing.revenue_total == Decimal("0")
        assert listing.description is None
        assert listing.license_terms is None
        assert listing.suggested_price is None
        assert listing.subscription_period_days is None
        assert listing.subscription_renewal_price is None
        assert listing.preview_content is None
        assert listing.published_at is None
        assert listing.expires_at is None
        assert listing.updated_at is None

    def test_price_non_negative(self):
        """Price must be >= 0."""
        with pytest.raises(ValidationError):
            CapsuleListing(
                capsule_id="cap-123",
                seller_id="user-456",
                price=Decimal("-10.00"),
                title="Test",
            )

    def test_price_zero_allowed(self):
        """Price of 0 (free) is allowed."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("0"),
            title="Free Capsule",
        )
        assert listing.price == Decimal("0")

    def test_title_max_length(self):
        """Title must be at most 200 characters."""
        with pytest.raises(ValidationError):
            CapsuleListing(
                capsule_id="cap-123",
                seller_id="user-456",
                price=Decimal("10.00"),
                title="a" * 201,
            )

    def test_listing_with_all_fields(self):
        """Listing with all fields populated."""
        now = datetime.now(UTC)
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("99.99"),
            currency=Currency.USD,
            suggested_price=Decimal("89.99"),
            license_type=LicenseType.SUBSCRIPTION,
            license_terms="Monthly subscription",
            subscription_period_days=30,
            subscription_renewal_price=Decimal("49.99"),
            status=ListingStatus.ACTIVE,
            featured=True,
            visibility=ListingVisibility.PUBLIC,
            title="Premium Capsule",
            description="A comprehensive knowledge capsule",
            tags=["ai", "machine-learning", "tutorial"],
            preview_content="This is a preview...",
            view_count=100,
            purchase_count=10,
            revenue_total=Decimal("999.90"),
            published_at=now,
            expires_at=now,
            updated_at=now,
        )
        assert listing.subscription_period_days == 30
        assert listing.featured is True
        assert len(listing.tags) == 3

    def test_listing_all_currencies(self):
        """Listing works with all currencies."""
        for currency in Currency:
            listing = CapsuleListing(
                capsule_id="cap-123",
                seller_id="user-456",
                price=Decimal("100.00"),
                currency=currency,
                title="Test",
            )
            assert listing.currency == currency

    def test_listing_all_statuses(self):
        """Listing works with all statuses."""
        for status in ListingStatus:
            listing = CapsuleListing(
                capsule_id="cap-123",
                seller_id="user-456",
                price=Decimal("100.00"),
                status=status,
                title="Test",
            )
            assert listing.status == status


# =============================================================================
# Purchase Tests
# =============================================================================


class TestPurchase:
    """Tests for Purchase model."""

    def test_valid_purchase(self):
        """Valid purchase creates model."""
        purchase = Purchase(
            listing_id="listing-123",
            capsule_id="cap-456",
            buyer_id="user-789",
            seller_id="user-012",
            price=Decimal("100.00"),
            currency=Currency.FORGE,
            license_type=LicenseType.PERPETUAL,
        )
        assert purchase.listing_id == "listing-123"
        assert purchase.buyer_id == "user-789"
        assert purchase.seller_id == "user-012"

    def test_default_values(self):
        """Purchase has sensible defaults."""
        purchase = Purchase(
            listing_id="listing-123",
            capsule_id="cap-456",
            buyer_id="user-789",
            seller_id="user-012",
            price=Decimal("100.00"),
            currency=Currency.FORGE,
            license_type=LicenseType.PERPETUAL,
        )
        assert purchase.id is not None
        assert purchase.license_id is not None
        assert purchase.license_expires_at is None
        assert purchase.payment_method == PaymentMethod.PLATFORM
        assert purchase.transaction_hash is None
        assert purchase.payment_status == PaymentStatus.COMPLETED
        assert purchase.seller_revenue == Decimal("0")
        assert purchase.platform_fee == Decimal("0")
        assert purchase.lineage_revenue == Decimal("0")
        assert purchase.treasury_contribution == Decimal("0")
        assert purchase.refunded_at is None
        assert purchase.notes is None
        assert purchase.purchased_at is not None

    def test_purchase_with_revenue_distribution(self):
        """Purchase with revenue distribution details."""
        purchase = Purchase(
            listing_id="listing-123",
            capsule_id="cap-456",
            buyer_id="user-789",
            seller_id="user-012",
            price=Decimal("100.00"),
            currency=Currency.FORGE,
            license_type=LicenseType.PERPETUAL,
            seller_revenue=Decimal("70.00"),
            platform_fee=Decimal("10.00"),
            lineage_revenue=Decimal("15.00"),
            treasury_contribution=Decimal("5.00"),
        )
        total = (
            purchase.seller_revenue
            + purchase.platform_fee
            + purchase.lineage_revenue
            + purchase.treasury_contribution
        )
        assert total == purchase.price

    def test_purchase_with_blockchain_payment(self):
        """Purchase with blockchain payment method."""
        purchase = Purchase(
            listing_id="listing-123",
            capsule_id="cap-456",
            buyer_id="user-789",
            seller_id="user-012",
            price=Decimal("1.5"),
            currency=Currency.ETH,
            license_type=LicenseType.PERPETUAL,
            payment_method=PaymentMethod.BLOCKCHAIN,
            transaction_hash="0x1234567890abcdef",
        )
        assert purchase.payment_method == PaymentMethod.BLOCKCHAIN
        assert purchase.transaction_hash == "0x1234567890abcdef"


# =============================================================================
# Cart and CartItem Tests
# =============================================================================


class TestCartItem:
    """Tests for CartItem model."""

    def test_valid_cart_item(self):
        """Valid cart item creates model."""
        item = CartItem(
            listing_id="listing-123",
            capsule_id="cap-456",
            price=Decimal("50.00"),
            currency=Currency.FORGE,
            title="Test Capsule",
        )
        assert item.listing_id == "listing-123"
        assert item.price == Decimal("50.00")
        assert item.title == "Test Capsule"

    def test_cart_item_auto_id(self):
        """Cart item auto-generates ID."""
        item = CartItem(
            listing_id="listing-123",
            capsule_id="cap-456",
            price=Decimal("50.00"),
            currency=Currency.FORGE,
            title="Test",
        )
        assert item.id is not None

    def test_cart_item_timestamp(self):
        """Cart item has added_at timestamp."""
        item = CartItem(
            listing_id="listing-123",
            capsule_id="cap-456",
            price=Decimal("50.00"),
            currency=Currency.FORGE,
            title="Test",
        )
        assert item.added_at is not None


class TestCart:
    """Tests for Cart model."""

    def test_valid_cart(self):
        """Valid cart creates model."""
        cart = Cart(user_id="user-123")
        assert cart.user_id == "user-123"
        assert cart.items == []

    def test_cart_default_values(self):
        """Cart has sensible defaults."""
        cart = Cart(user_id="user-123")
        assert cart.id is not None
        assert cart.items == []
        assert cart.updated_at is not None

    def test_cart_total_empty(self):
        """Empty cart has total of 0."""
        cart = Cart(user_id="user-123")
        assert cart.total == Decimal(0)

    def test_cart_total_single_item(self):
        """Cart with single item calculates total."""
        cart = Cart(
            user_id="user-123",
            items=[
                CartItem(
                    listing_id="l-1",
                    capsule_id="c-1",
                    price=Decimal("50.00"),
                    currency=Currency.FORGE,
                    title="Item 1",
                )
            ],
        )
        assert cart.total == Decimal("50.00")

    def test_cart_total_multiple_items_same_currency(self):
        """Cart with multiple items in same currency calculates total."""
        cart = Cart(
            user_id="user-123",
            items=[
                CartItem(
                    listing_id="l-1",
                    capsule_id="c-1",
                    price=Decimal("50.00"),
                    currency=Currency.FORGE,
                    title="Item 1",
                ),
                CartItem(
                    listing_id="l-2",
                    capsule_id="c-2",
                    price=Decimal("30.00"),
                    currency=Currency.FORGE,
                    title="Item 2",
                ),
                CartItem(
                    listing_id="l-3",
                    capsule_id="c-3",
                    price=Decimal("20.00"),
                    currency=Currency.FORGE,
                    title="Item 3",
                ),
            ],
        )
        assert cart.total == Decimal("100.00")

    def test_cart_total_mixed_currencies_raises_error(self):
        """Cart with mixed currencies raises ValueError."""
        cart = Cart(
            user_id="user-123",
            items=[
                CartItem(
                    listing_id="l-1",
                    capsule_id="c-1",
                    price=Decimal("50.00"),
                    currency=Currency.FORGE,
                    title="Item 1",
                ),
                CartItem(
                    listing_id="l-2",
                    capsule_id="c-2",
                    price=Decimal("30.00"),
                    currency=Currency.USD,
                    title="Item 2",
                ),
            ],
        )
        with pytest.raises(ValueError, match="mixed currencies"):
            _ = cart.total

    def test_cart_totals_by_currency(self):
        """Cart calculates totals by currency."""
        cart = Cart(
            user_id="user-123",
            items=[
                CartItem(
                    listing_id="l-1",
                    capsule_id="c-1",
                    price=Decimal("50.00"),
                    currency=Currency.FORGE,
                    title="Item 1",
                ),
                CartItem(
                    listing_id="l-2",
                    capsule_id="c-2",
                    price=Decimal("30.00"),
                    currency=Currency.USD,
                    title="Item 2",
                ),
                CartItem(
                    listing_id="l-3",
                    capsule_id="c-3",
                    price=Decimal("20.00"),
                    currency=Currency.FORGE,
                    title="Item 3",
                ),
            ],
        )
        totals = cart.totals_by_currency
        assert totals[Currency.FORGE] == Decimal("70.00")
        assert totals[Currency.USD] == Decimal("30.00")

    def test_cart_totals_by_currency_empty(self):
        """Empty cart has empty totals by currency."""
        cart = Cart(user_id="user-123")
        assert cart.totals_by_currency == {}

    def test_cart_item_count(self):
        """Cart counts items correctly."""
        cart = Cart(user_id="user-123")
        assert cart.item_count == 0

        cart_with_items = Cart(
            user_id="user-123",
            items=[
                CartItem(
                    listing_id="l-1",
                    capsule_id="c-1",
                    price=Decimal("50.00"),
                    currency=Currency.FORGE,
                    title="Item 1",
                ),
                CartItem(
                    listing_id="l-2",
                    capsule_id="c-2",
                    price=Decimal("30.00"),
                    currency=Currency.FORGE,
                    title="Item 2",
                ),
            ],
        )
        assert cart_with_items.item_count == 2


# =============================================================================
# License Tests
# =============================================================================


class TestLicense:
    """Tests for License model."""

    def test_valid_license(self):
        """Valid license creates model."""
        license_obj = License(
            purchase_id="purchase-123",
            capsule_id="cap-456",
            holder_id="user-789",
            grantor_id="user-012",
            license_type=LicenseType.PERPETUAL,
        )
        assert license_obj.purchase_id == "purchase-123"
        assert license_obj.holder_id == "user-789"
        assert license_obj.license_type == LicenseType.PERPETUAL

    def test_default_values(self):
        """License has sensible defaults."""
        license_obj = License(
            purchase_id="purchase-123",
            capsule_id="cap-456",
            holder_id="user-789",
            grantor_id="user-012",
            license_type=LicenseType.PERPETUAL,
        )
        assert license_obj.id is not None
        assert license_obj.granted_at is not None
        assert license_obj.expires_at is None
        assert license_obj.revoked_at is None
        assert license_obj.can_view is True
        assert license_obj.can_download is True
        assert license_obj.can_derive is False
        assert license_obj.can_resell is False
        assert license_obj.access_count == 0
        assert license_obj.last_accessed_at is None

    def test_license_with_expiration(self):
        """License can have expiration date."""
        expiry = datetime.now(UTC)
        license_obj = License(
            purchase_id="purchase-123",
            capsule_id="cap-456",
            holder_id="user-789",
            grantor_id="user-012",
            license_type=LicenseType.SUBSCRIPTION,
            expires_at=expiry,
        )
        assert license_obj.expires_at == expiry

    def test_license_with_derivative_permissions(self):
        """License can grant derivative permissions."""
        license_obj = License(
            purchase_id="purchase-123",
            capsule_id="cap-456",
            holder_id="user-789",
            grantor_id="user-012",
            license_type=LicenseType.DERIVATIVE,
            can_derive=True,
            can_resell=True,
        )
        assert license_obj.can_derive is True
        assert license_obj.can_resell is True

    def test_license_all_types(self):
        """License works with all license types."""
        for license_type in LicenseType:
            license_obj = License(
                purchase_id="purchase-123",
                capsule_id="cap-456",
                holder_id="user-789",
                grantor_id="user-012",
                license_type=license_type,
            )
            assert license_obj.license_type == license_type


# =============================================================================
# PriceSuggestion Tests
# =============================================================================


class TestPriceSuggestion:
    """Tests for PriceSuggestion model."""

    def test_valid_price_suggestion(self):
        """Valid price suggestion creates model."""
        suggestion = PriceSuggestion(
            capsule_id="cap-123",
            suggested_price=Decimal("100.00"),
            min_price=Decimal("50.00"),
            max_price=Decimal("200.00"),
        )
        assert suggestion.capsule_id == "cap-123"
        assert suggestion.suggested_price == Decimal("100.00")
        assert suggestion.min_price == Decimal("50.00")
        assert suggestion.max_price == Decimal("200.00")

    def test_default_values(self):
        """Price suggestion has sensible defaults."""
        suggestion = PriceSuggestion(
            capsule_id="cap-123",
            suggested_price=Decimal("100.00"),
            min_price=Decimal("50.00"),
            max_price=Decimal("200.00"),
        )
        assert suggestion.id is not None
        assert suggestion.currency == Currency.FORGE
        assert suggestion.factors == {}
        assert suggestion.trust_multiplier == 1.0
        assert suggestion.demand_multiplier == 1.0
        assert suggestion.rarity_multiplier == 1.0
        assert suggestion.pagerank_score == 0.0
        assert suggestion.citation_count == 0
        assert suggestion.view_count == 0
        assert suggestion.calculated_at is not None

    def test_price_suggestion_with_factors(self):
        """Price suggestion with pricing factors."""
        suggestion = PriceSuggestion(
            capsule_id="cap-123",
            suggested_price=Decimal("150.00"),
            min_price=Decimal("100.00"),
            max_price=Decimal("300.00"),
            factors={
                "quality_score": 0.9,
                "demand_factor": 1.2,
                "rarity_factor": 1.5,
            },
            trust_multiplier=1.1,
            demand_multiplier=1.2,
            rarity_multiplier=1.5,
        )
        assert suggestion.factors["quality_score"] == 0.9
        assert suggestion.trust_multiplier == 1.1

    def test_price_suggestion_with_context(self):
        """Price suggestion with context metrics."""
        suggestion = PriceSuggestion(
            capsule_id="cap-123",
            suggested_price=Decimal("100.00"),
            min_price=Decimal("50.00"),
            max_price=Decimal("200.00"),
            pagerank_score=0.85,
            citation_count=50,
            view_count=1000,
        )
        assert suggestion.pagerank_score == 0.85
        assert suggestion.citation_count == 50
        assert suggestion.view_count == 1000


# =============================================================================
# RevenueDistribution Tests
# =============================================================================


class TestRevenueDistribution:
    """Tests for RevenueDistribution model."""

    def test_valid_revenue_distribution(self):
        """Valid revenue distribution creates model."""
        distribution = RevenueDistribution(
            purchase_id="purchase-123",
            total_amount=Decimal("100.00"),
            currency=Currency.FORGE,
            seller_share=Decimal("70.00"),
            lineage_share=Decimal("15.00"),
            platform_share=Decimal("10.00"),
            treasury_share=Decimal("5.00"),
        )
        assert distribution.total_amount == Decimal("100.00")
        assert distribution.seller_share == Decimal("70.00")
        assert distribution.lineage_share == Decimal("15.00")
        assert distribution.platform_share == Decimal("10.00")
        assert distribution.treasury_share == Decimal("5.00")

    def test_revenue_distribution_adds_up(self):
        """Revenue distribution shares add up to total."""
        distribution = RevenueDistribution(
            purchase_id="purchase-123",
            total_amount=Decimal("100.00"),
            currency=Currency.FORGE,
            seller_share=Decimal("70.00"),
            lineage_share=Decimal("15.00"),
            platform_share=Decimal("10.00"),
            treasury_share=Decimal("5.00"),
        )
        total = (
            distribution.seller_share
            + distribution.lineage_share
            + distribution.platform_share
            + distribution.treasury_share
        )
        assert total == distribution.total_amount

    def test_default_values(self):
        """Revenue distribution has sensible defaults."""
        distribution = RevenueDistribution(
            purchase_id="purchase-123",
            total_amount=Decimal("100.00"),
            currency=Currency.FORGE,
            seller_share=Decimal("70.00"),
            lineage_share=Decimal("15.00"),
            platform_share=Decimal("10.00"),
            treasury_share=Decimal("5.00"),
        )
        assert distribution.id is not None
        assert distribution.lineage_recipients == []
        assert distribution.distributed_at is not None

    def test_revenue_distribution_with_lineage_recipients(self):
        """Revenue distribution with lineage recipient breakdown."""
        distribution = RevenueDistribution(
            purchase_id="purchase-123",
            total_amount=Decimal("100.00"),
            currency=Currency.FORGE,
            seller_share=Decimal("70.00"),
            lineage_share=Decimal("15.00"),
            platform_share=Decimal("10.00"),
            treasury_share=Decimal("5.00"),
            lineage_recipients=[
                {"user_id": "user-1", "amount": Decimal("10.00"), "contribution_weight": 0.67},
                {"user_id": "user-2", "amount": Decimal("5.00"), "contribution_weight": 0.33},
            ],
        )
        assert len(distribution.lineage_recipients) == 2
        assert distribution.lineage_recipients[0]["user_id"] == "user-1"


# =============================================================================
# MarketplaceStats Tests
# =============================================================================


class TestMarketplaceStats:
    """Tests for MarketplaceStats model."""

    def test_default_values(self):
        """MarketplaceStats has sensible defaults."""
        stats = MarketplaceStats()
        assert stats.total_listings == 0
        assert stats.active_listings == 0
        assert stats.total_sales == 0
        assert stats.total_revenue == Decimal("0")
        assert stats.sales_today == 0
        assert stats.sales_this_week == 0
        assert stats.sales_this_month == 0
        assert stats.revenue_today == Decimal("0")
        assert stats.revenue_this_week == Decimal("0")
        assert stats.revenue_this_month == Decimal("0")
        assert stats.top_sellers == []
        assert stats.top_capsules == []
        assert stats.trending_tags == []
        assert stats.avg_price == Decimal("0")
        assert stats.avg_capsules_per_seller == 0.0
        assert stats.calculated_at is not None

    def test_stats_with_data(self):
        """MarketplaceStats with populated data."""
        stats = MarketplaceStats(
            total_listings=1000,
            active_listings=500,
            total_sales=250,
            total_revenue=Decimal("25000.00"),
            sales_today=10,
            sales_this_week=50,
            sales_this_month=150,
            revenue_today=Decimal("1000.00"),
            revenue_this_week=Decimal("5000.00"),
            revenue_this_month=Decimal("15000.00"),
            top_sellers=[
                {"user_id": "user-1", "sales": 50, "revenue": Decimal("5000.00")},
                {"user_id": "user-2", "sales": 30, "revenue": Decimal("3000.00")},
            ],
            top_capsules=[
                {"capsule_id": "cap-1", "sales": 100, "rating": 4.9},
            ],
            trending_tags=["ai", "machine-learning", "tutorial"],
            avg_price=Decimal("100.00"),
            avg_capsules_per_seller=2.5,
        )
        assert stats.total_listings == 1000
        assert stats.active_listings == 500
        assert len(stats.top_sellers) == 2
        assert len(stats.trending_tags) == 3


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestMarketplaceEdgeCases:
    """Edge case tests for marketplace models."""

    def test_decimal_precision(self):
        """Decimal values maintain precision."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("99.999"),
            title="Precise Price",
        )
        assert listing.price == Decimal("99.999")

    def test_large_decimal_values(self):
        """Large decimal values are handled."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("9999999.99"),
            title="Expensive",
        )
        assert listing.price == Decimal("9999999.99")

    def test_cart_with_many_items(self):
        """Cart handles many items."""
        items = [
            CartItem(
                listing_id=f"l-{i}",
                capsule_id=f"c-{i}",
                price=Decimal("10.00"),
                currency=Currency.FORGE,
                title=f"Item {i}",
            )
            for i in range(100)
        ]
        cart = Cart(user_id="user-123", items=items)
        assert cart.item_count == 100
        assert cart.total == Decimal("1000.00")

    def test_empty_strings_in_optional_fields(self):
        """Empty strings in optional fields."""
        listing = CapsuleListing(
            capsule_id="cap-123",
            seller_id="user-456",
            price=Decimal("50.00"),
            title="Test",
            description="",
            license_terms="",
            preview_content="",
        )
        # Pydantic strips whitespace, empty string stays as empty string
        assert listing.description == ""

    def test_id_generation_uniqueness(self):
        """Auto-generated IDs are unique."""
        listings = [
            CapsuleListing(
                capsule_id="cap-123",
                seller_id="user-456",
                price=Decimal("50.00"),
                title="Test",
            )
            for _ in range(10)
        ]
        ids = [l.id for l in listings]
        assert len(ids) == len(set(ids))  # All unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
