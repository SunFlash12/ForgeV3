"""
Marketplace Repository Tests for Forge Cascade V2

Comprehensive tests for MarketplaceRepository including:
- ListingRepository CRUD operations
- PurchaseRepository operations
- CartRepository operations
- LicenseRepository operations
- MarketplaceRepository unified interface
- Statistics and initialization
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from forge.models.marketplace import (
    CapsuleListing,
    Cart,
    CartItem,
    Currency,
    License,
    LicenseType,
    ListingStatus,
    MarketplaceStats,
    PaymentStatus,
    Purchase,
)
from forge.repositories.marketplace_repository import (
    CartRepository,
    LicenseRepository,
    ListingRepository,
    MarketplaceRepository,
    PurchaseRepository,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def listing_repository(mock_db_client):
    """Create listing repository with mock client."""
    return ListingRepository(mock_db_client)


@pytest.fixture
def purchase_repository(mock_db_client):
    """Create purchase repository with mock client."""
    return PurchaseRepository(mock_db_client)


@pytest.fixture
def cart_repository(mock_db_client):
    """Create cart repository with mock client."""
    return CartRepository(mock_db_client)


@pytest.fixture
def license_repository(mock_db_client):
    """Create license repository with mock client."""
    return LicenseRepository(mock_db_client)


@pytest.fixture
def marketplace_repository(mock_db_client):
    """Create unified marketplace repository with mock client."""
    return MarketplaceRepository(mock_db_client)


@pytest.fixture
def sample_listing_data():
    """Sample listing data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "listing123",
        "capsule_id": "cap123",
        "seller_id": "user123",
        "price": "99.99",
        "currency": "FORGE",
        "license_type": "standard",
        "status": "active",
        "title": "Test Listing",
        "description": "A test marketplace listing",
        "tags": ["test", "example"],
        "view_count": 100,
        "purchase_count": 5,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@pytest.fixture
def sample_purchase_data():
    """Sample purchase data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "purchase123",
        "listing_id": "listing123",
        "capsule_id": "cap123",
        "buyer_id": "buyer456",
        "seller_id": "user123",
        "price": "99.99",
        "currency": "FORGE",
        "license_type": "standard",
        "payment_status": "completed",
        "seller_revenue": "89.99",
        "platform_fee": "5.00",
        "lineage_revenue": "3.00",
        "treasury_contribution": "2.00",
        "purchased_at": now.isoformat(),
    }


@pytest.fixture
def sample_license_data():
    """Sample license data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "license123",
        "purchase_id": "purchase123",
        "capsule_id": "cap123",
        "holder_id": "buyer456",
        "grantor_id": "user123",
        "license_type": "standard",
        "granted_at": now.isoformat(),
        "expires_at": None,
        "revoked_at": None,
        "can_view": True,
        "can_download": True,
        "can_derive": False,
        "can_resell": False,
        "access_count": 0,
        "last_accessed_at": None,
    }


@pytest.fixture
def sample_cart_item_data():
    """Sample cart item data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "item123",
        "listing_id": "listing123",
        "capsule_id": "cap123",
        "price": "99.99",
        "currency": "FORGE",
        "title": "Test Item",
        "added_at": now.isoformat(),
    }


# =============================================================================
# ListingRepository Tests
# =============================================================================


class TestListingRepository:
    """Tests for ListingRepository."""

    @pytest.mark.asyncio
    async def test_create_listing_success(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Successfully create a listing."""
        mock_db_client.execute_single.return_value = {"entity": sample_listing_data}

        listing = CapsuleListing(
            id="listing123",
            capsule_id="cap123",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            status=ListingStatus.ACTIVE,
            title="Test Listing",
            description="A test listing",
            tags=["test"],
        )

        result = await listing_repository.create(listing)

        assert result is not None
        assert result.title == "Test Listing"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_listing_failure_raises_error(
        self, listing_repository, mock_db_client
    ):
        """Listing creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        listing = CapsuleListing(
            capsule_id="cap123",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            status=ListingStatus.ACTIVE,
            title="Test",
        )

        with pytest.raises(RuntimeError, match="Failed to create listing"):
            await listing_repository.create(listing)

    @pytest.mark.asyncio
    async def test_update_listing_success(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Successfully update a listing."""
        sample_listing_data["title"] = "Updated Title"
        mock_db_client.execute_single.return_value = {"entity": sample_listing_data}

        listing = CapsuleListing(
            id="listing123",
            capsule_id="cap123",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            status=ListingStatus.ACTIVE,
            title="Updated Title",
        )

        result = await listing_repository.update("listing123", listing)

        assert result is not None
        assert result.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_listing_not_found(
        self, listing_repository, mock_db_client
    ):
        """Update returns None when listing not found."""
        mock_db_client.execute_single.return_value = None

        listing = CapsuleListing(
            capsule_id="cap123",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            status=ListingStatus.ACTIVE,
            title="Test",
        )

        result = await listing_repository.update("nonexistent", listing)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_active_listings(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Find active listings."""
        mock_db_client.execute.return_value = [{"entity": sample_listing_data}]

        result = await listing_repository.find_active()

        assert len(result) == 1
        assert result[0].status == ListingStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_find_active_listings_limit_capped(
        self, listing_repository, mock_db_client
    ):
        """Find active listings respects limit cap."""
        mock_db_client.execute.return_value = []

        await listing_repository.find_active(limit=500)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100  # Capped at 100

    @pytest.mark.asyncio
    async def test_find_by_seller(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Find listings by seller."""
        mock_db_client.execute.return_value = [{"entity": sample_listing_data}]

        result = await listing_repository.find_by_seller("user123")

        assert len(result) == 1
        assert result[0].seller_id == "user123"

    @pytest.mark.asyncio
    async def test_find_by_capsule(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Find listing for specific capsule."""
        mock_db_client.execute.return_value = [{"entity": sample_listing_data}]

        result = await listing_repository.find_by_capsule("cap123")

        assert result is not None
        assert result.capsule_id == "cap123"

    @pytest.mark.asyncio
    async def test_find_by_capsule_not_found(
        self, listing_repository, mock_db_client
    ):
        """Find by capsule returns None when not found."""
        mock_db_client.execute.return_value = []

        result = await listing_repository.find_by_capsule("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_increment_view_count(
        self, listing_repository, mock_db_client
    ):
        """Increment listing view count."""
        await listing_repository.increment_view_count("listing123")

        mock_db_client.execute.assert_called_once()
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "view_count + 1" in query

    def test_to_model_conversion(self, listing_repository, sample_listing_data):
        """Test model conversion handles string to enum conversion."""
        result = listing_repository._to_model(sample_listing_data)

        assert result is not None
        assert result.currency == Currency.FORGE
        assert result.license_type == LicenseType.STANDARD
        assert result.status == ListingStatus.ACTIVE
        assert isinstance(result.price, Decimal)

    def test_to_model_conversion_invalid_data(self, listing_repository):
        """Test model conversion handles invalid data."""
        result = listing_repository._to_model({"invalid": "data"})

        assert result is None

    def test_to_model_conversion_empty_record(self, listing_repository):
        """Test model conversion handles empty record."""
        result = listing_repository._to_model({})

        assert result is None


# =============================================================================
# PurchaseRepository Tests
# =============================================================================


class TestPurchaseRepository:
    """Tests for PurchaseRepository."""

    @pytest.mark.asyncio
    async def test_create_purchase_success(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Successfully create a purchase."""
        mock_db_client.execute_single.return_value = {"entity": sample_purchase_data}

        purchase = Purchase(
            listing_id="listing123",
            capsule_id="cap123",
            buyer_id="buyer456",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            payment_status=PaymentStatus.COMPLETED,
            seller_revenue=Decimal("89.99"),
            platform_fee=Decimal("5.00"),
            lineage_revenue=Decimal("3.00"),
            treasury_contribution=Decimal("2.00"),
        )

        result = await purchase_repository.create(purchase)

        assert result is not None
        assert result.buyer_id == "buyer456"

    @pytest.mark.asyncio
    async def test_create_purchase_failure_raises_error(
        self, purchase_repository, mock_db_client
    ):
        """Purchase creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        purchase = Purchase(
            listing_id="listing123",
            capsule_id="cap123",
            buyer_id="buyer456",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            payment_status=PaymentStatus.COMPLETED,
            seller_revenue=Decimal("89.99"),
            platform_fee=Decimal("5.00"),
            lineage_revenue=Decimal("3.00"),
            treasury_contribution=Decimal("2.00"),
        )

        with pytest.raises(RuntimeError, match="Failed to create purchase"):
            await purchase_repository.create(purchase)

    @pytest.mark.asyncio
    async def test_update_purchase_refund(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Update purchase for refund."""
        sample_purchase_data["payment_status"] = "refunded"
        sample_purchase_data["refunded_at"] = datetime.now(UTC).isoformat()
        mock_db_client.execute_single.return_value = {"entity": sample_purchase_data}

        purchase = Purchase(
            id="purchase123",
            listing_id="listing123",
            capsule_id="cap123",
            buyer_id="buyer456",
            seller_id="user123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            payment_status=PaymentStatus.REFUNDED,
            seller_revenue=Decimal("89.99"),
            platform_fee=Decimal("5.00"),
            lineage_revenue=Decimal("3.00"),
            treasury_contribution=Decimal("2.00"),
            refunded_at=datetime.now(UTC),
        )

        result = await purchase_repository.update("purchase123", purchase)

        assert result is not None

    @pytest.mark.asyncio
    async def test_find_by_buyer(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Find purchases by buyer."""
        mock_db_client.execute.return_value = [{"entity": sample_purchase_data}]

        result = await purchase_repository.find_by_buyer("buyer456")

        assert len(result) == 1
        assert result[0].buyer_id == "buyer456"

    @pytest.mark.asyncio
    async def test_find_by_seller(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Find sales by seller."""
        mock_db_client.execute.return_value = [{"entity": sample_purchase_data}]

        result = await purchase_repository.find_by_seller("user123")

        assert len(result) == 1
        assert result[0].seller_id == "user123"

    @pytest.mark.asyncio
    async def test_find_by_capsule_with_buyer(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Check if buyer has purchased specific capsule."""
        mock_db_client.execute_single.return_value = {"entity": sample_purchase_data}

        result = await purchase_repository.find_by_capsule("cap123", "buyer456")

        assert result is not None
        assert result.capsule_id == "cap123"
        assert result.buyer_id == "buyer456"

    @pytest.mark.asyncio
    async def test_find_by_capsule_no_purchase(
        self, purchase_repository, mock_db_client
    ):
        """Find by capsule returns None when not purchased."""
        mock_db_client.execute_single.return_value = None

        result = await purchase_repository.find_by_capsule("cap123", "other_user")

        assert result is None

    def test_to_model_conversion(self, purchase_repository, sample_purchase_data):
        """Test model conversion handles decimal and enum conversion."""
        result = purchase_repository._to_model(sample_purchase_data)

        assert result is not None
        assert result.currency == Currency.FORGE
        assert result.license_type == LicenseType.STANDARD
        assert result.payment_status == PaymentStatus.COMPLETED
        assert isinstance(result.price, Decimal)
        assert isinstance(result.seller_revenue, Decimal)


# =============================================================================
# CartRepository Tests
# =============================================================================


class TestCartRepository:
    """Tests for CartRepository."""

    @pytest.mark.asyncio
    async def test_get_cart_creates_if_not_exists(
        self, cart_repository, mock_db_client
    ):
        """Get cart creates new cart if not exists."""
        mock_db_client.execute_single.return_value = {
            "cart": {"id": "cart123", "user_id": "user123"}
        }
        mock_db_client.execute.return_value = []

        result = await cart_repository.get_cart("user123")

        assert result is not None
        assert result.user_id == "user123"
        assert isinstance(result.items, list)

    @pytest.mark.asyncio
    async def test_get_cart_loads_items(
        self, cart_repository, mock_db_client, sample_cart_item_data
    ):
        """Get cart loads existing items."""
        mock_db_client.execute_single.return_value = {
            "cart": {"id": "cart123", "user_id": "user123"}
        }
        mock_db_client.execute.return_value = [{"item": sample_cart_item_data}]

        result = await cart_repository.get_cart("user123")

        assert len(result.items) == 1
        assert result.items[0].listing_id == "listing123"

    @pytest.mark.asyncio
    async def test_add_item_to_cart(
        self, cart_repository, mock_db_client, sample_cart_item_data
    ):
        """Add item to cart."""
        # First call for get_cart (MERGE), second for loading items after add
        mock_db_client.execute_single.side_effect = [
            {"cart": {"id": "cart123", "user_id": "user123"}},  # Initial get
            {"cart": {"id": "cart123", "user_id": "user123"}},  # After add get
        ]
        mock_db_client.execute.side_effect = [
            [],  # Initial items
            None,  # Add item
            [{"item": sample_cart_item_data}],  # Items after add
        ]

        item = CartItem(
            id="item123",
            listing_id="listing123",
            capsule_id="cap123",
            price=Decimal("99.99"),
            currency=Currency.FORGE,
            title="Test Item",
        )

        result = await cart_repository.add_item("user123", item)

        assert result is not None

    @pytest.mark.asyncio
    async def test_remove_item_from_cart(
        self, cart_repository, mock_db_client
    ):
        """Remove item from cart."""
        mock_db_client.execute_single.return_value = {
            "cart": {"id": "cart123", "user_id": "user123"}
        }
        mock_db_client.execute.return_value = []

        result = await cart_repository.remove_item("user123", "listing123")

        assert result is not None
        # Verify delete query was called
        delete_calls = [
            c for c in mock_db_client.execute.call_args_list
            if "DELETE" in str(c)
        ]
        assert len(delete_calls) > 0

    @pytest.mark.asyncio
    async def test_clear_cart(self, cart_repository, mock_db_client):
        """Clear all items from cart."""
        await cart_repository.clear_cart("user123")

        mock_db_client.execute.assert_called()
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "DELETE" in query


# =============================================================================
# LicenseRepository Tests
# =============================================================================


class TestLicenseRepository:
    """Tests for LicenseRepository."""

    @pytest.mark.asyncio
    async def test_create_license_success(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """Successfully create a license."""
        mock_db_client.execute_single.return_value = {"entity": sample_license_data}

        license_obj = License(
            purchase_id="purchase123",
            capsule_id="cap123",
            holder_id="buyer456",
            grantor_id="user123",
            license_type=LicenseType.STANDARD,
            can_view=True,
            can_download=True,
            can_derive=False,
            can_resell=False,
        )

        result = await license_repository.create(license_obj)

        assert result is not None
        assert result.holder_id == "buyer456"

    @pytest.mark.asyncio
    async def test_create_license_failure_raises_error(
        self, license_repository, mock_db_client
    ):
        """License creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        license_obj = License(
            purchase_id="purchase123",
            capsule_id="cap123",
            holder_id="buyer456",
            grantor_id="user123",
            license_type=LicenseType.STANDARD,
        )

        with pytest.raises(RuntimeError, match="Failed to create license"):
            await license_repository.create(license_obj)

    @pytest.mark.asyncio
    async def test_update_license_access_tracking(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """Update license for access tracking."""
        sample_license_data["access_count"] = 5
        sample_license_data["last_accessed_at"] = datetime.now(UTC).isoformat()
        mock_db_client.execute_single.return_value = {"entity": sample_license_data}

        license_obj = License(
            id="license123",
            purchase_id="purchase123",
            capsule_id="cap123",
            holder_id="buyer456",
            grantor_id="user123",
            license_type=LicenseType.STANDARD,
            access_count=5,
            last_accessed_at=datetime.now(UTC),
        )

        result = await license_repository.update("license123", license_obj)

        assert result is not None
        assert result.access_count == 5

    @pytest.mark.asyncio
    async def test_find_valid_license(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """Find valid (non-expired, non-revoked) license."""
        mock_db_client.execute_single.return_value = {"entity": sample_license_data}

        result = await license_repository.find_valid_license("cap123", "buyer456")

        assert result is not None
        assert result.revoked_at is None

    @pytest.mark.asyncio
    async def test_find_valid_license_not_found(
        self, license_repository, mock_db_client
    ):
        """Find valid license returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await license_repository.find_valid_license("cap123", "other_user")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_holder(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """Find all licenses held by user."""
        mock_db_client.execute.return_value = [{"entity": sample_license_data}]

        result = await license_repository.find_by_holder("buyer456")

        assert len(result) == 1
        assert result[0].holder_id == "buyer456"

    @pytest.mark.asyncio
    async def test_record_access(self, license_repository, mock_db_client):
        """Record license access event."""
        await license_repository.record_access("license123")

        mock_db_client.execute.assert_called_once()
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "access_count + 1" in query

    @pytest.mark.asyncio
    async def test_revoke_license(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """Revoke a license."""
        sample_license_data["revoked_at"] = datetime.now(UTC).isoformat()
        mock_db_client.execute_single.return_value = {"entity": sample_license_data}

        result = await license_repository.revoke("license123")

        assert result is not None
        assert result.revoked_at is not None

    @pytest.mark.asyncio
    async def test_revoke_license_not_found(
        self, license_repository, mock_db_client
    ):
        """Revoke returns None when license not found."""
        mock_db_client.execute_single.return_value = None

        result = await license_repository.revoke("nonexistent")

        assert result is None

    def test_to_model_conversion(self, license_repository, sample_license_data):
        """Test model conversion handles enum conversion."""
        result = license_repository._to_model(sample_license_data)

        assert result is not None
        assert result.license_type == LicenseType.STANDARD


# =============================================================================
# MarketplaceRepository Tests
# =============================================================================


class TestMarketplaceRepository:
    """Tests for unified MarketplaceRepository."""

    @pytest.mark.asyncio
    async def test_initialize_creates_indexes(
        self, marketplace_repository, mock_db_client
    ):
        """Initialize creates necessary indexes."""
        mock_db_client.execute.return_value = None

        await marketplace_repository.initialize()

        # Should create multiple indexes
        assert mock_db_client.execute.call_count >= 8

    @pytest.mark.asyncio
    async def test_initialize_handles_index_errors(
        self, marketplace_repository, mock_db_client
    ):
        """Initialize handles index creation errors gracefully."""
        mock_db_client.execute.side_effect = RuntimeError("Index error")

        # Should not raise
        await marketplace_repository.initialize()

    @pytest.mark.asyncio
    async def test_get_stats_success(
        self, marketplace_repository, mock_db_client
    ):
        """Get marketplace statistics."""
        mock_db_client.execute_single.return_value = {
            "total_listings": 100,
            "active_listings": 75,
            "total_sales": 500,
            "total_revenue": 50000.00,
        }

        result = await marketplace_repository.get_stats()

        assert isinstance(result, MarketplaceStats)
        assert result.total_listings == 100
        assert result.active_listings == 75
        assert result.total_sales == 500
        assert result.total_revenue == Decimal("50000.00")

    @pytest.mark.asyncio
    async def test_get_stats_empty(
        self, marketplace_repository, mock_db_client
    ):
        """Get stats returns defaults when no data."""
        mock_db_client.execute_single.return_value = None

        result = await marketplace_repository.get_stats()

        assert isinstance(result, MarketplaceStats)
        assert result.total_listings == 0

    def test_sub_repository_access(self, marketplace_repository):
        """Verify sub-repository access."""
        assert isinstance(marketplace_repository.listings, ListingRepository)
        assert isinstance(marketplace_repository.purchases, PurchaseRepository)
        assert isinstance(marketplace_repository.carts, CartRepository)
        assert isinstance(marketplace_repository.licenses, LicenseRepository)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_listing_with_zero_price(
        self, listing_repository, mock_db_client, sample_listing_data
    ):
        """Listing with zero price (free)."""
        sample_listing_data["price"] = "0.00"
        mock_db_client.execute_single.return_value = {"entity": sample_listing_data}

        listing = CapsuleListing(
            capsule_id="cap123",
            seller_id="user123",
            price=Decimal("0.00"),
            currency=Currency.FORGE,
            license_type=LicenseType.STANDARD,
            status=ListingStatus.ACTIVE,
            title="Free Item",
        )

        result = await listing_repository.create(listing)

        assert result is not None
        assert result.price == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_license_with_expiry(
        self, license_repository, mock_db_client, sample_license_data
    ):
        """License with expiration date."""
        future_date = datetime.now(UTC) + timedelta(days=30)
        sample_license_data["expires_at"] = future_date.isoformat()
        mock_db_client.execute_single.return_value = {"entity": sample_license_data}

        license_obj = License(
            purchase_id="purchase123",
            capsule_id="cap123",
            holder_id="buyer456",
            grantor_id="user123",
            license_type=LicenseType.STANDARD,
            expires_at=future_date,
        )

        result = await license_repository.create(license_obj)

        assert result is not None

    @pytest.mark.asyncio
    async def test_purchase_with_all_revenue_fields(
        self, purchase_repository, mock_db_client, sample_purchase_data
    ):
        """Purchase with complete revenue breakdown."""
        result = purchase_repository._to_model(sample_purchase_data)

        assert result is not None
        assert result.seller_revenue == Decimal("89.99")
        assert result.platform_fee == Decimal("5.00")
        assert result.lineage_revenue == Decimal("3.00")
        assert result.treasury_contribution == Decimal("2.00")

        # Verify total adds up (approximately)
        total = (
            result.seller_revenue
            + result.platform_fee
            + result.lineage_revenue
            + result.treasury_contribution
        )
        assert total == result.price

    @pytest.mark.asyncio
    async def test_cart_item_price_conversion(
        self, cart_repository, mock_db_client
    ):
        """Cart item handles string to Decimal conversion."""
        mock_db_client.execute_single.return_value = {
            "cart": {"id": "cart123", "user_id": "user123"}
        }
        mock_db_client.execute.return_value = [
            {
                "item": {
                    "id": "item1",
                    "listing_id": "listing1",
                    "capsule_id": "cap1",
                    "price": "123.45",
                    "currency": "FORGE",
                    "title": "Test",
                }
            }
        ]

        result = await cart_repository.get_cart("user123")

        assert len(result.items) == 1
        assert isinstance(result.items[0].price, Decimal)
        assert result.items[0].price == Decimal("123.45")


# =============================================================================
# Currency and License Type Tests
# =============================================================================


class TestEnumerations:
    """Tests for currency and license type handling."""

    def test_currency_values(self):
        """Test currency enumeration values."""
        assert Currency.FORGE.value == "FORGE"
        # Add other currencies if defined

    def test_license_type_values(self):
        """Test license type enumeration values."""
        assert LicenseType.STANDARD.value == "standard"
        # Add other license types if defined

    def test_listing_status_values(self):
        """Test listing status enumeration values."""
        assert ListingStatus.ACTIVE.value == "active"
        # Add other statuses if defined

    def test_payment_status_values(self):
        """Test payment status enumeration values."""
        assert PaymentStatus.COMPLETED.value == "completed"
        assert PaymentStatus.REFUNDED.value == "refunded"
        # Add other statuses if defined


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
