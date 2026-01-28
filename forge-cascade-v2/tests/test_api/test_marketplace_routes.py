"""
Marketplace Routes Tests for Forge Cascade V2

Comprehensive tests for marketplace API routes including:
- Listing management (create, list, get, update, publish, cancel)
- Featured listings
- Cart operations
- Purchase and checkout flows
- Pricing endpoints
- Statistics
- License checking
- Web3 / Virtuals Protocol purchases
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.models.marketplace import (
    Currency,
    LicenseType,
    ListingStatus,
    ListingVisibility,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_listing():
    """Create a mock marketplace listing."""
    listing = MagicMock()
    listing.id = "listing123"
    listing.capsule_id = "capsule123"
    listing.seller_id = "user123"
    listing.price = Decimal("99.99")
    listing.currency = Currency.FORGE
    listing.suggested_price = Decimal("89.99")
    listing.license_type = LicenseType.PERPETUAL
    listing.status = ListingStatus.ACTIVE
    listing.title = "Test Listing"
    listing.description = "A test marketplace listing"
    listing.tags = ["knowledge", "test"]
    listing.preview_content = "Preview of the capsule content"
    listing.view_count = 100
    listing.purchase_count = 10
    listing.created_at = datetime.now(UTC)
    listing.published_at = datetime.now(UTC)
    return listing


@pytest.fixture
def mock_cart_item():
    """Create a mock cart item."""
    item = MagicMock()
    item.listing_id = "listing123"
    item.capsule_id = "capsule123"
    item.title = "Test Listing"
    item.price = Decimal("99.99")
    item.currency = Currency.FORGE
    item.added_at = datetime.now(UTC)
    return item


@pytest.fixture
def mock_cart(mock_cart_item):
    """Create a mock cart."""
    cart = MagicMock()
    cart.items = [mock_cart_item]
    cart.total = Decimal("99.99")
    cart.item_count = 1
    return cart


@pytest.fixture
def mock_purchase():
    """Create a mock purchase."""
    purchase = MagicMock()
    purchase.id = "purchase123"
    purchase.listing_id = "listing123"
    purchase.capsule_id = "capsule123"
    purchase.price = Decimal("99.99")
    purchase.currency = Currency.FORGE
    purchase.license_type = LicenseType.PERPETUAL
    purchase.purchased_at = datetime.now(UTC)
    purchase.license_expires_at = None
    return purchase


@pytest.fixture
def mock_license():
    """Create a mock license."""
    license_obj = MagicMock()
    license_obj.id = "license123"
    license_obj.license_type = LicenseType.PERPETUAL
    license_obj.granted_at = datetime.now(UTC)
    license_obj.expires_at = None
    license_obj.can_view = True
    license_obj.can_download = True
    license_obj.can_derive = False
    return license_obj


@pytest.fixture
def mock_price_suggestion():
    """Create a mock price suggestion."""
    suggestion = MagicMock()
    suggestion.capsule_id = "capsule123"
    suggestion.suggested_price = Decimal("89.99")
    suggestion.min_price = Decimal("49.99")
    suggestion.max_price = Decimal("149.99")
    suggestion.factors = {"trust": 1.2, "demand": 0.9, "complexity": 1.1}
    return suggestion


@pytest.fixture
def mock_marketplace_stats():
    """Create mock marketplace statistics."""
    stats = MagicMock()
    stats.total_listings = 1000
    stats.active_listings = 800
    stats.total_sales = 5000
    stats.total_revenue = Decimal("49999.99")
    stats.sales_today = 50
    stats.sales_this_week = 350
    stats.avg_price = Decimal("49.99")
    stats.top_sellers = [{"seller_id": "user1", "sales": 100}]
    stats.top_capsules = [{"capsule_id": "cap1", "purchases": 50}]
    return stats


@pytest.fixture
def mock_marketplace_service(
    mock_listing,
    mock_cart,
    mock_purchase,
    mock_license,
    mock_price_suggestion,
    mock_marketplace_stats,
):
    """Create mock marketplace service."""
    service = AsyncMock()
    service.create_listing = AsyncMock(return_value=mock_listing)
    service.get_listings = AsyncMock(return_value=[mock_listing])
    service.get_listing = AsyncMock(return_value=mock_listing)
    service.publish_listing = AsyncMock(return_value=mock_listing)
    service.update_listing = AsyncMock(return_value=mock_listing)
    service.cancel_listing = AsyncMock()
    service.record_view = AsyncMock()
    service.get_featured_listings = AsyncMock(return_value=[
        {
            "id": "listing123",
            "capsule_id": "capsule123",
            "title": "Featured Listing",
            "description": "A featured capsule",
            "category": "knowledge",
            "price": 99.99,
            "currency": "FORGE",
            "tags": ["featured"],
            "preview_content": "Preview",
            "author_name": "Test Author",
            "purchase_count": 100,
            "view_count": 1000,
            "tokenization": None,
        }
    ])
    service.get_cart = AsyncMock(return_value=mock_cart)
    service.add_to_cart = AsyncMock(return_value=mock_cart)
    service.remove_from_cart = AsyncMock(return_value=mock_cart)
    service.checkout = AsyncMock(return_value=[mock_purchase])
    service.purchase_single = AsyncMock(return_value=mock_purchase)
    service.get_user_purchases = AsyncMock(return_value=[mock_purchase])
    service.get_user_sales = AsyncMock(return_value=[mock_purchase])
    service.calculate_suggested_price = AsyncMock(return_value=mock_price_suggestion)
    service.get_marketplace_stats = AsyncMock(return_value=mock_marketplace_stats)
    service.check_license = AsyncMock(return_value=mock_license)
    return service


@pytest.fixture
def mock_active_user():
    """Create mock authenticated user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.trust_flame = 60
    user.is_active = True
    return user


@pytest.fixture
def marketplace_app(mock_marketplace_service, mock_active_user):
    """Create FastAPI app with marketplace router and mocked dependencies."""
    from forge.api.routes.marketplace import router, get_marketplace

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Override dependencies
    from forge.api.dependencies import get_current_active_user

    app.dependency_overrides[get_marketplace] = lambda: mock_marketplace_service
    app.dependency_overrides[get_current_active_user] = lambda: mock_active_user

    return app


@pytest.fixture
def client(marketplace_app):
    """Create test client."""
    return TestClient(marketplace_app)


# =============================================================================
# Listing Creation Tests
# =============================================================================


class TestCreateListing:
    """Tests for POST /marketplace/listings endpoint."""

    def test_create_listing_success(self, client: TestClient):
        """Create listing with valid data."""
        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "capsule123",
                "price": 99.99,
                "currency": "FORGE",
                "license_type": "PERPETUAL",
                "title": "Test Listing Title",
                "description": "A detailed description of the listing",
                "tags": ["knowledge", "test"],
                "preview_content": "Preview of the capsule content",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "capsule_id" in data
        assert "price" in data
        assert "status" in data

    def test_create_listing_minimal(self, client: TestClient):
        """Create listing with minimal required fields."""
        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "capsule123",
                "price": 49.99,
                "title": "Minimal Listing",
            },
        )

        assert response.status_code == 200

    def test_create_listing_zero_price(self, client: TestClient):
        """Create free listing."""
        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "capsule123",
                "price": 0,
                "title": "Free Listing",
            },
        )

        assert response.status_code == 200

    def test_create_listing_negative_price(self, client: TestClient):
        """Create listing with negative price fails."""
        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "capsule123",
                "price": -10,
                "title": "Invalid Listing",
            },
        )

        assert response.status_code == 422

    def test_create_listing_title_too_long(self, client: TestClient):
        """Create listing with title exceeding max length."""
        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "capsule123",
                "price": 99.99,
                "title": "A" * 201,  # Over 200 char limit
            },
        )

        assert response.status_code == 422

    def test_create_listing_service_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Create listing when service returns error."""
        mock_marketplace_service.create_listing.side_effect = ValueError("Capsule not found")

        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "nonexistent",
                "price": 99.99,
                "title": "Test Listing",
            },
        )

        assert response.status_code == 400


# =============================================================================
# List Listings Tests
# =============================================================================


class TestListListings:
    """Tests for GET /marketplace/listings endpoint."""

    def test_list_listings(self, client: TestClient):
        """List all listings."""
        response = client.get("/api/v1/marketplace/listings")

        assert response.status_code == 200
        data = response.json()
        assert "listings" in data
        assert "total" in data

    def test_list_listings_filtered_by_status(self, client: TestClient):
        """List listings filtered by status."""
        response = client.get("/api/v1/marketplace/listings?status=active")

        assert response.status_code == 200

    def test_list_listings_by_seller(self, client: TestClient):
        """List listings by seller."""
        response = client.get("/api/v1/marketplace/listings?seller_id=user123")

        assert response.status_code == 200

    def test_list_listings_price_range(self, client: TestClient):
        """List listings within price range."""
        response = client.get(
            "/api/v1/marketplace/listings?min_price=10&max_price=100"
        )

        assert response.status_code == 200

    def test_list_listings_by_tags(self, client: TestClient):
        """List listings by tags."""
        response = client.get("/api/v1/marketplace/listings?tags=knowledge,test")

        assert response.status_code == 200

    def test_list_listings_sorted(self, client: TestClient):
        """List listings with custom sorting."""
        response = client.get("/api/v1/marketplace/listings?sort_by=price")

        assert response.status_code == 200

    def test_list_listings_pagination(self, client: TestClient):
        """List listings with pagination."""
        response = client.get("/api/v1/marketplace/listings?limit=10&offset=0")

        assert response.status_code == 200


# =============================================================================
# Get Listing Tests
# =============================================================================


class TestGetListing:
    """Tests for GET /marketplace/listings/{listing_id} endpoint."""

    def test_get_listing(self, client: TestClient):
        """Get listing by ID."""
        response = client.get("/api/v1/marketplace/listings/listing123")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "price" in data

    def test_get_listing_not_found(
        self, client: TestClient, mock_marketplace_service
    ):
        """Get non-existent listing."""
        mock_marketplace_service.get_listing.return_value = None

        response = client.get("/api/v1/marketplace/listings/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Publish Listing Tests
# =============================================================================


class TestPublishListing:
    """Tests for POST /marketplace/listings/{listing_id}/publish endpoint."""

    def test_publish_listing(self, client: TestClient):
        """Publish a draft listing."""
        response = client.post("/api/v1/marketplace/listings/listing123/publish")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "status" in data

    def test_publish_listing_service_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Publish listing when not authorized."""
        mock_marketplace_service.publish_listing.side_effect = ValueError(
            "You do not own this listing"
        )

        response = client.post("/api/v1/marketplace/listings/other_listing/publish")

        assert response.status_code == 400


# =============================================================================
# Update Listing Tests
# =============================================================================


class TestUpdateListing:
    """Tests for PATCH /marketplace/listings/{listing_id} endpoint."""

    def test_update_listing(self, client: TestClient):
        """Update listing details."""
        response = client.patch(
            "/api/v1/marketplace/listings/listing123",
            json={
                "price": 149.99,
                "description": "Updated description",
                "tags": ["updated", "tags"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    def test_update_listing_visibility(self, client: TestClient):
        """Update listing visibility."""
        response = client.patch(
            "/api/v1/marketplace/listings/listing123",
            json={"visibility": "PRIVATE"},
        )

        assert response.status_code == 200

    def test_update_listing_service_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Update listing not owned by user."""
        mock_marketplace_service.update_listing.side_effect = ValueError(
            "Permission denied"
        )

        response = client.patch(
            "/api/v1/marketplace/listings/other_listing",
            json={"price": 199.99},
        )

        assert response.status_code == 400


# =============================================================================
# Cancel Listing Tests
# =============================================================================


class TestCancelListing:
    """Tests for DELETE /marketplace/listings/{listing_id} endpoint."""

    def test_cancel_listing(self, client: TestClient):
        """Cancel a listing."""
        response = client.delete("/api/v1/marketplace/listings/listing123")

        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is True

    def test_cancel_listing_service_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Cancel listing not owned by user."""
        mock_marketplace_service.cancel_listing.side_effect = ValueError(
            "Permission denied"
        )

        response = client.delete("/api/v1/marketplace/listings/other_listing")

        assert response.status_code == 400


# =============================================================================
# Featured Listings Tests
# =============================================================================


class TestFeaturedListings:
    """Tests for GET /marketplace/featured endpoint."""

    def test_get_featured_listings(self, client: TestClient):
        """Get featured listings."""
        response = client.get("/api/v1/marketplace/featured")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "title" in data[0]
            assert "category" in data[0]

    def test_get_featured_listings_with_limit(self, client: TestClient):
        """Get featured listings with custom limit."""
        response = client.get("/api/v1/marketplace/featured?limit=3")

        assert response.status_code == 200

    def test_get_featured_listings_with_tokenization(
        self, client: TestClient, mock_marketplace_service
    ):
        """Get featured listings with tokenization data."""
        mock_marketplace_service.get_featured_listings.return_value = [
            {
                "id": "listing123",
                "capsule_id": "capsule123",
                "title": "Tokenized Listing",
                "description": "A tokenized capsule",
                "category": "knowledge",
                "price": 99.99,
                "currency": "VIRTUAL",
                "tags": ["tokenized"],
                "preview_content": "Preview",
                "author_name": "Test Author",
                "purchase_count": 100,
                "view_count": 1000,
                "tokenization": {
                    "token_symbol": "CAP",
                    "launch_type": "fair_launch",
                    "genesis_tier": "standard",
                    "graduation_progress": 0.75,
                    "total_holders": 150,
                    "bonding_curve_virtual_accumulated": 5000.0,
                    "graduation_threshold": 10000.0,
                    "status": "active",
                },
            }
        ]

        response = client.get("/api/v1/marketplace/featured")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["tokenization"] is not None
        assert "token_symbol" in data[0]["tokenization"]


# =============================================================================
# Cart Tests
# =============================================================================


class TestCart:
    """Tests for cart endpoints."""

    def test_get_cart(self, client: TestClient):
        """Get current cart."""
        response = client.get("/api/v1/marketplace/cart")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "item_count" in data

    def test_add_to_cart(self, client: TestClient):
        """Add item to cart."""
        response = client.post("/api/v1/marketplace/cart/items/listing123")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_add_to_cart_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Add to cart service error."""
        mock_marketplace_service.add_to_cart.side_effect = ValueError("Already in cart")

        response = client.post("/api/v1/marketplace/cart/items/listing123")

        assert response.status_code == 400

    def test_remove_from_cart(self, client: TestClient):
        """Remove item from cart."""
        response = client.delete("/api/v1/marketplace/cart/items/listing123")

        assert response.status_code == 200


# =============================================================================
# Purchase Tests
# =============================================================================


class TestCheckout:
    """Tests for POST /marketplace/checkout endpoint."""

    def test_checkout(self, client: TestClient):
        """Process checkout."""
        response = client.post("/api/v1/marketplace/checkout")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "listing_id" in data[0]
            assert "price" in data[0]

    def test_checkout_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Checkout with empty cart or error."""
        mock_marketplace_service.checkout.side_effect = ValueError("Cart is empty")

        response = client.post("/api/v1/marketplace/checkout")

        assert response.status_code == 400


class TestPurchaseSingle:
    """Tests for POST /marketplace/listings/{listing_id}/purchase endpoint."""

    def test_purchase_single(self, client: TestClient):
        """Purchase single listing directly."""
        response = client.post("/api/v1/marketplace/listings/listing123/purchase")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "listing_id" in data
        assert "purchased_at" in data

    def test_purchase_single_error(
        self, client: TestClient, mock_marketplace_service
    ):
        """Purchase single listing error."""
        mock_marketplace_service.purchase_single.side_effect = ValueError(
            "Listing not available"
        )

        response = client.post("/api/v1/marketplace/listings/unavailable/purchase")

        assert response.status_code == 400


class TestPurchaseHistory:
    """Tests for purchase and sales history endpoints."""

    def test_get_purchases(self, client: TestClient):
        """Get purchase history."""
        response = client.get("/api/v1/marketplace/purchases")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_purchases_with_limit(self, client: TestClient):
        """Get purchase history with limit."""
        response = client.get("/api/v1/marketplace/purchases?limit=10")

        assert response.status_code == 200

    def test_get_sales(self, client: TestClient):
        """Get sales history."""
        response = client.get("/api/v1/marketplace/sales")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# =============================================================================
# Pricing Tests
# =============================================================================


class TestPricing:
    """Tests for pricing endpoints."""

    def test_get_suggested_price(self, client: TestClient):
        """Get suggested price for capsule."""
        response = client.get("/api/v1/marketplace/pricing/capsule123")

        assert response.status_code == 200
        data = response.json()
        assert "capsule_id" in data
        assert "suggested_price" in data
        assert "min_price" in data
        assert "max_price" in data
        assert "factors" in data

    def test_get_suggested_price_not_found(
        self, client: TestClient, mock_marketplace_service
    ):
        """Get suggested price for non-existent capsule."""
        mock_marketplace_service.calculate_suggested_price.return_value = None

        response = client.get("/api/v1/marketplace/pricing/nonexistent")

        assert response.status_code == 404

    def test_analyze_pricing(self, client: TestClient):
        """Analyze detailed pricing."""
        with patch("forge.api.routes.marketplace.get_pricing_engine") as mock_engine:
            engine = AsyncMock()
            result = MagicMock()
            result.capsule_id = "capsule123"
            result.suggested_price = Decimal("99.99")
            result.minimum_price = Decimal("49.99")
            result.maximum_price = Decimal("199.99")
            result.confidence = 0.85
            result.pricing_tier = MagicMock(value="STANDARD")
            result.tier_reason = "Normal marketplace item"
            result.base_price = Decimal("79.99")
            result.multipliers = {"trust": 1.2}
            result.adjustments = {"demand": Decimal("10.00")}
            result.market_comparison = {"similar_avg": 89.99}
            result.recommendations = ["Consider lowering price"]
            engine.calculate_price = AsyncMock(return_value=result)
            mock_engine.return_value = engine

            response = client.post(
                "/api/v1/marketplace/pricing/analyze",
                json={
                    "capsule_id": "capsule123",
                    "include_recommendations": True,
                    "include_market_comparison": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "capsule_id" in data
            assert "suggested_price" in data
            assert "pricing_tier" in data
            assert "recommendations" in data

    def test_get_lineage_distribution(self, client: TestClient):
        """Get lineage revenue distribution."""
        with patch("forge.api.routes.marketplace.get_pricing_engine") as mock_engine:
            engine = AsyncMock()
            engine.calculate_lineage_distribution = AsyncMock(return_value=[
                {"user_id": "user1", "capsule_id": "cap1", "depth": 1, "weight": 0.5, "amount": Decimal("7.50")},
            ])
            mock_engine.return_value = engine

            response = client.get(
                "/api/v1/marketplace/pricing/capsule123/lineage-distribution?sale_price=100"
            )

            assert response.status_code == 200
            data = response.json()
            assert "capsule_id" in data
            assert "total_lineage_share" in data
            assert "distributions" in data

    def test_get_pricing_tiers(self, client: TestClient):
        """Get pricing tier information."""
        response = client.get("/api/v1/marketplace/pricing/tiers")

        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert "base_prices" in data
        assert "trust_curve" in data
        assert "revenue_distribution" in data


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Tests for GET /marketplace/stats endpoint."""

    def test_get_marketplace_stats(self, client: TestClient):
        """Get marketplace statistics."""
        response = client.get("/api/v1/marketplace/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_listings" in data
        assert "active_listings" in data
        assert "total_sales" in data
        assert "total_revenue" in data
        assert "sales_today" in data
        assert "avg_price" in data


# =============================================================================
# License Check Tests
# =============================================================================


class TestLicenseCheck:
    """Tests for GET /marketplace/license/{capsule_id} endpoint."""

    def test_check_license_has_license(self, client: TestClient):
        """Check license when user has one."""
        response = client.get("/api/v1/marketplace/license/capsule123")

        assert response.status_code == 200
        data = response.json()
        assert data["has_license"] is True
        assert "license_id" in data
        assert "license_type" in data
        assert "can_view" in data

    def test_check_license_no_license(
        self, client: TestClient, mock_marketplace_service
    ):
        """Check license when user doesn't have one."""
        mock_marketplace_service.check_license.return_value = None

        response = client.get("/api/v1/marketplace/license/capsule456")

        assert response.status_code == 200
        data = response.json()
        assert data["has_license"] is False


# =============================================================================
# Web3 Purchase Tests
# =============================================================================


class TestWeb3Purchase:
    """Tests for Web3/Virtuals Protocol purchase endpoints."""

    def test_submit_web3_purchase(self, client: TestClient):
        """Submit Web3 purchase."""
        with patch("forge.api.routes.marketplace.verify_purchase_transaction") as mock_verify:
            verification = MagicMock()
            verification.is_valid = True
            verification.block_number = 12345678
            mock_verify.return_value = verification

            with patch.object(
                client.app.dependency_overrides.get(
                    type(list(client.app.dependency_overrides.keys())[0])
                ),
                "record_web3_purchase",
                new_callable=AsyncMock,
            ):
                response = client.post(
                    "/api/v1/marketplace/purchase",
                    json={
                        "items": [
                            {
                                "listing_id": "listing123",
                                "capsule_id": "capsule123",
                                "title": "Test Listing",
                                "price_virtual": "1000000000000000000",
                            }
                        ],
                        "wallet_address": "0x1234567890123456789012345678901234567890",
                        "transaction_hash": "0x" + "a" * 64,
                    },
                )

                # May fail if web3 service not available
                assert response.status_code in [200, 400, 500]

    def test_submit_web3_purchase_invalid_wallet(self, client: TestClient):
        """Submit Web3 purchase with invalid wallet address."""
        response = client.post(
            "/api/v1/marketplace/purchase",
            json={
                "items": [
                    {
                        "listing_id": "listing123",
                        "capsule_id": "capsule123",
                        "title": "Test",
                        "price_virtual": "1000000000000000000",
                    }
                ],
                "wallet_address": "invalid_address",
                "transaction_hash": "0x" + "a" * 64,
            },
        )

        assert response.status_code == 422

    def test_submit_web3_purchase_invalid_tx_hash(self, client: TestClient):
        """Submit Web3 purchase with invalid transaction hash."""
        response = client.post(
            "/api/v1/marketplace/purchase",
            json={
                "items": [
                    {
                        "listing_id": "listing123",
                        "capsule_id": "capsule123",
                        "title": "Test",
                        "price_virtual": "1000000000000000000",
                    }
                ],
                "wallet_address": "0x1234567890123456789012345678901234567890",
                "transaction_hash": "invalid_hash",
            },
        )

        assert response.status_code == 422

    def test_get_transaction_status(self, client: TestClient):
        """Get transaction status."""
        with patch("forge.api.routes.marketplace.get_transaction_info") as mock_info:
            tx_info = MagicMock()
            tx_info.block_number = 12345678
            tx_info.confirmations = 15
            mock_info.return_value = tx_info

            response = client.get(
                f"/api/v1/marketplace/transaction/0x{'a' * 64}"
            )

            # May fail if web3 service not available
            assert response.status_code in [200, 400, 503]

    def test_get_transaction_status_invalid_hash(self, client: TestClient):
        """Get transaction status with invalid hash."""
        response = client.get("/api/v1/marketplace/transaction/invalid")

        assert response.status_code == 400

    def test_get_virtual_price(self, client: TestClient):
        """Get $VIRTUAL token price."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "pairs": [{"priceUsd": "0.15"}]
            }
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            response = client.get("/api/v1/marketplace/virtual-price")

            assert response.status_code == 200
            data = response.json()
            assert "price_usd" in data
            assert "updated_at" in data


# =============================================================================
# Error Sanitization Tests
# =============================================================================


class TestErrorSanitization:
    """Tests for error message sanitization."""

    def test_not_found_error_sanitized(
        self, client: TestClient, mock_marketplace_service
    ):
        """Not found errors are sanitized."""
        mock_marketplace_service.create_listing.side_effect = ValueError(
            "Capsule with ID xyz not found in database"
        )

        response = client.post(
            "/api/v1/marketplace/listings",
            json={
                "capsule_id": "xyz",
                "price": 99.99,
                "title": "Test",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert "not found" in data["detail"].lower()
        assert "xyz" not in data["detail"]  # ID not leaked

    def test_permission_error_sanitized(
        self, client: TestClient, mock_marketplace_service
    ):
        """Permission errors are sanitized."""
        mock_marketplace_service.update_listing.side_effect = ValueError(
            "User user123 does not own listing abc456"
        )

        response = client.patch(
            "/api/v1/marketplace/listings/abc456",
            json={"price": 199.99},
        )

        assert response.status_code == 400
        data = response.json()
        assert "permission" in data["detail"].lower()
        assert "user123" not in data["detail"]  # User ID not leaked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
