"""
Tests for Marketplace Service

Tests cover:
- Listing creation and management
- Cart operations
- Purchase workflow
- Revenue distribution
- License management
- Price suggestions
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from forge.models.marketplace import (
    Currency,
    LicenseType,
    ListingStatus,
    PaymentStatus,
)
from forge.services.marketplace import MarketplaceService


class TestListingCreation:
    """Tests for listing creation."""

    @pytest.fixture
    def service(self):
        return MarketplaceService()

    @pytest.mark.asyncio
    async def test_create_listing(self, service):
        """Test creating a new listing."""
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("25.00"),
            currency=Currency.FORGE,
            license_type=LicenseType.PERPETUAL,
            title="Test Capsule",
            description="A test capsule listing",
            tags=["test", "example"],
        )

        assert listing.seller_id == "seller-123"
        assert listing.price == Decimal("25.00")
        assert listing.status == ListingStatus.DRAFT
        assert "test" in listing.tags

    @pytest.mark.asyncio
    async def test_listing_starts_as_draft(self, service):
        """New listings should start in draft status."""
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("10.00"),
        )

        assert listing.status == ListingStatus.DRAFT

    @pytest.mark.asyncio
    async def test_publish_listing(self, service):
        """Test publishing a draft listing."""
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("10.00"),
        )

        published = await service.publish_listing(listing.id, "seller-123")

        assert published.status == ListingStatus.ACTIVE
        assert published.published_at is not None

    @pytest.mark.asyncio
    async def test_publish_requires_ownership(self, service):
        """Only owner can publish listing."""
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("10.00"),
        )

        with pytest.raises(ValueError, match="Not authorized"):
            await service.publish_listing(listing.id, "different-seller")


class TestListingRetrieval:
    """Tests for listing retrieval and filtering."""

    @pytest.fixture
    async def service_with_listings(self):
        service = MarketplaceService()

        # Create some listings
        for i in range(5):
            listing = await service.create_listing(
                capsule_id=str(uuid4()),
                seller_id=f"seller-{i % 2}",
                price=Decimal(str(10 + i * 5)),
                tags=["category-a"] if i % 2 == 0 else ["category-b"],
            )
            if i < 3:  # Publish first 3
                await service.publish_listing(listing.id, f"seller-{i % 2}")

        return service

    @pytest.mark.asyncio
    async def test_get_listing_by_id(self, service_with_listings):
        service = service_with_listings
        listings = await service.get_listings(limit=1)
        listing_id = listings[0].id

        result = await service.get_listing(listing_id)

        assert result is not None
        assert result.id == listing_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_listing(self):
        service = MarketplaceService()
        result = await service.get_listing("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_filter_by_status(self, service_with_listings):
        service = service_with_listings
        active = await service.get_listings(status=ListingStatus.ACTIVE)
        drafts = await service.get_listings(status=ListingStatus.DRAFT)

        assert len(active) == 3
        assert len(drafts) == 2

    @pytest.mark.asyncio
    async def test_filter_by_seller(self, service_with_listings):
        service = service_with_listings
        seller_0 = await service.get_listings(seller_id="seller-0")
        seller_1 = await service.get_listings(seller_id="seller-1")

        assert len(seller_0) == 3  # indices 0, 2, 4
        assert len(seller_1) == 2  # indices 1, 3

    @pytest.mark.asyncio
    async def test_pagination(self, service_with_listings):
        service = service_with_listings
        page1 = await service.get_listings(limit=2, offset=0)
        page2 = await service.get_listings(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id


class TestCartOperations:
    """Tests for shopping cart operations."""

    @pytest.fixture
    async def service_with_active_listing(self):
        service = MarketplaceService()
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("25.00"),
        )
        await service.publish_listing(listing.id, "seller-123")
        return service, listing

    @pytest.mark.asyncio
    async def test_get_empty_cart(self):
        service = MarketplaceService()
        cart = await service.get_cart("user-123")

        assert cart.user_id == "user-123"
        assert len(cart.items) == 0

    @pytest.mark.asyncio
    async def test_add_to_cart(self, service_with_active_listing):
        service, listing = service_with_active_listing

        cart = await service.add_to_cart("buyer-123", listing.id)

        assert len(cart.items) == 1
        assert cart.items[0].listing_id == listing.id
        assert cart.items[0].price == Decimal("25.00")

    @pytest.mark.asyncio
    async def test_cannot_add_own_listing(self, service_with_active_listing):
        service, listing = service_with_active_listing

        with pytest.raises(ValueError, match="Cannot purchase your own"):
            await service.add_to_cart("seller-123", listing.id)

    @pytest.mark.asyncio
    async def test_cannot_add_inactive_listing(self):
        service = MarketplaceService()
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("25.00"),
        )
        # Don't publish

        with pytest.raises(ValueError, match="not active"):
            await service.add_to_cart("buyer-123", listing.id)

    @pytest.mark.asyncio
    async def test_remove_from_cart(self, service_with_active_listing):
        service, listing = service_with_active_listing

        await service.add_to_cart("buyer-123", listing.id)
        cart = await service.remove_from_cart("buyer-123", listing.id)

        assert len(cart.items) == 0

    @pytest.mark.asyncio
    async def test_clear_cart(self, service_with_active_listing):
        service, listing = service_with_active_listing

        await service.add_to_cart("buyer-123", listing.id)
        cart = await service.clear_cart("buyer-123")

        assert len(cart.items) == 0


class TestPurchaseWorkflow:
    """Tests for purchase workflow."""

    @pytest.fixture
    async def service_with_active_listing(self):
        service = MarketplaceService()
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("50.00"),
        )
        await service.publish_listing(listing.id, "seller-123")
        return service, listing

    @pytest.mark.asyncio
    async def test_purchase_single(self, service_with_active_listing):
        service, listing = service_with_active_listing

        purchase = await service.purchase_single(
            buyer_id="buyer-123",
            listing_id=listing.id,
        )

        assert purchase.buyer_id == "buyer-123"
        assert purchase.seller_id == "seller-123"
        assert purchase.price == Decimal("50.00")
        assert purchase.payment_status == PaymentStatus.PENDING

    @pytest.mark.asyncio
    async def test_cannot_purchase_twice(self, service_with_active_listing):
        service, listing = service_with_active_listing

        await service.purchase_single("buyer-123", listing.id)

        with pytest.raises(ValueError, match="Already purchased"):
            await service.purchase_single("buyer-123", listing.id)

    @pytest.mark.asyncio
    async def test_checkout_cart(self, service_with_active_listing):
        service, listing = service_with_active_listing

        await service.add_to_cart("buyer-123", listing.id)
        purchases = await service.checkout("buyer-123")

        assert len(purchases) == 1
        assert purchases[0].listing_id == listing.id

    @pytest.mark.asyncio
    async def test_checkout_clears_cart(self, service_with_active_listing):
        service, listing = service_with_active_listing

        await service.add_to_cart("buyer-123", listing.id)
        await service.checkout("buyer-123")

        cart = await service.get_cart("buyer-123")
        assert len(cart.items) == 0

    @pytest.mark.asyncio
    async def test_checkout_empty_cart(self):
        service = MarketplaceService()

        with pytest.raises(ValueError, match="Cart is empty"):
            await service.checkout("buyer-123")


class TestRevenueDistribution:
    """Tests for revenue distribution calculation."""

    def test_distribution_percentages(self):
        service = MarketplaceService()

        assert service.SELLER_SHARE == Decimal("0.70")
        assert service.LINEAGE_SHARE == Decimal("0.15")
        assert service.PLATFORM_SHARE == Decimal("0.10")
        assert service.TREASURY_SHARE == Decimal("0.05")

    def test_distribution_adds_to_100(self):
        service = MarketplaceService()
        total = (
            service.SELLER_SHARE +
            service.LINEAGE_SHARE +
            service.PLATFORM_SHARE +
            service.TREASURY_SHARE
        )
        assert total == Decimal("1.00")

    @pytest.mark.asyncio
    async def test_purchase_includes_distribution(self):
        service = MarketplaceService()
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("100.00"),
        )
        await service.publish_listing(listing.id, "seller-123")

        purchase = await service.purchase_single("buyer-123", listing.id)

        assert purchase.seller_revenue == Decimal("70.00")
        assert purchase.platform_fee == Decimal("10.00")
        assert purchase.lineage_revenue == Decimal("15.00")
        assert purchase.treasury_contribution == Decimal("5.00")


class TestLicenseManagement:
    """Tests for license management."""

    @pytest.fixture
    async def service_with_purchase(self):
        service = MarketplaceService()
        listing = await service.create_listing(
            capsule_id=str(uuid4()),
            seller_id="seller-123",
            price=Decimal("50.00"),
            license_type=LicenseType.PERPETUAL,
        )
        await service.publish_listing(listing.id, "seller-123")
        await service.purchase_single("buyer-123", listing.id)
        return service, listing

    @pytest.mark.asyncio
    async def test_license_created_on_purchase(self, service_with_purchase):
        service, listing = service_with_purchase

        license = await service.check_license("buyer-123", listing.capsule_id)

        assert license is not None
        assert license.holder_id == "buyer-123"
        assert license.license_type == LicenseType.PERPETUAL

    @pytest.mark.asyncio
    async def test_no_license_without_purchase(self):
        service = MarketplaceService()
        license = await service.check_license("user-123", str(uuid4()))
        assert license is None

    @pytest.mark.asyncio
    async def test_record_license_access(self, service_with_purchase):
        service, listing = service_with_purchase

        license = await service.check_license("buyer-123", listing.capsule_id)
        await service.record_access(license.id)

        # Verify access was recorded
        updated_license = service._licenses.get(license.id)
        assert updated_license.access_count == 1


class TestPriceSuggestion:
    """Tests for price suggestion calculation."""

    @pytest.mark.asyncio
    async def test_calculate_suggested_price(self):
        service = MarketplaceService()

        suggestion = await service.calculate_suggested_price(str(uuid4()))

        assert suggestion is not None
        assert suggestion.suggested_price > 0
        assert suggestion.min_price < suggestion.suggested_price
        assert suggestion.max_price > suggestion.suggested_price

    def test_trust_multiplier(self):
        service = MarketplaceService()

        assert service._trust_multiplier(10) == 0.5   # Quarantine
        assert service._trust_multiplier(30) == 1.0   # Sandbox
        assert service._trust_multiplier(50) == 1.5   # Standard
        assert service._trust_multiplier(70) == 2.0   # Trusted
        assert service._trust_multiplier(90) == 3.0   # Core

    def test_demand_multiplier(self):
        service = MarketplaceService()

        # More views/citations = higher multiplier
        mult_low = service._demand_multiplier(0, 0)
        mult_high = service._demand_multiplier(1000, 50)

        assert mult_high > mult_low


class TestMarketplaceStats:
    """Tests for marketplace statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        service = MarketplaceService()
        stats = await service.get_marketplace_stats()

        assert stats.total_listings == 0
        assert stats.active_listings == 0
        assert stats.total_sales == 0
        assert stats.total_revenue == 0

    @pytest.mark.asyncio
    async def test_stats_with_data(self):
        service = MarketplaceService()

        # Create and publish listings
        for i in range(3):
            listing = await service.create_listing(
                capsule_id=str(uuid4()),
                seller_id=f"seller-{i}",
                price=Decimal(str(10 * (i + 1))),
            )
            await service.publish_listing(listing.id, f"seller-{i}")

        # Make a purchase
        listings = await service.get_listings(status=ListingStatus.ACTIVE)
        await service.purchase_single("buyer-1", listings[0].id)

        stats = await service.get_marketplace_stats()

        assert stats.total_listings == 3
        assert stats.active_listings == 3
        assert stats.total_sales == 1
        assert stats.total_revenue > 0
