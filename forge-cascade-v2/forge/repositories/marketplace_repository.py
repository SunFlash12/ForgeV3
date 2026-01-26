"""
Marketplace Repository

Persistence layer for marketplace entities using Neo4j.
Handles listings, purchases, carts, and licenses.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog

from forge.database.client import Neo4jClient
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
from forge.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ListingRepository(BaseRepository[CapsuleListing, CapsuleListing, CapsuleListing]):
    """Repository for marketplace listings."""

    @property
    def node_label(self) -> str:
        return "MarketplaceListing"

    @property
    def model_class(self) -> type[CapsuleListing]:
        cls: type[CapsuleListing] = CapsuleListing
        return cls

    async def create(self, data: CapsuleListing, **kwargs: Any) -> CapsuleListing:
        """Create a new listing."""
        listing_id = data.id or self._generate_id()
        now = self._now()

        query = """
        CREATE (l:MarketplaceListing {
            id: $id,
            capsule_id: $capsule_id,
            seller_id: $seller_id,
            price: $price,
            currency: $currency,
            license_type: $license_type,
            status: $status,
            title: $title,
            description: $description,
            tags: $tags,
            view_count: $view_count,
            purchase_count: $purchase_count,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN l {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": listing_id,
                "capsule_id": data.capsule_id,
                "seller_id": data.seller_id,
                "price": str(data.price),
                "currency": data.currency.value,
                "license_type": data.license_type.value,
                "status": data.status.value,
                "title": data.title,
                "description": data.description,
                "tags": data.tags,
                "view_count": data.view_count,
                "purchase_count": data.purchase_count,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )

        if result is None:
            raise RuntimeError("Failed to create listing")
        listing = self._to_model(result["entity"])
        if listing is None:
            raise RuntimeError("Failed to deserialize created listing")
        return listing

    async def update(self, entity_id: str, data: CapsuleListing) -> CapsuleListing | None:
        """Update an existing listing."""
        query = """
        MATCH (l:MarketplaceListing {id: $id})
        SET l.price = $price,
            l.status = $status,
            l.title = $title,
            l.description = $description,
            l.tags = $tags,
            l.updated_at = $updated_at
        RETURN l {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": entity_id,
                "price": str(data.price),
                "status": data.status.value,
                "title": data.title,
                "description": data.description,
                "tags": data.tags,
                "updated_at": self._now().isoformat(),
            },
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def find_active(self, skip: int = 0, limit: int = 50) -> list[CapsuleListing]:
        """Find active listings."""
        # SECURITY FIX (Audit 4 - S4): Bound skip/limit to prevent resource exhaustion
        limit = max(1, min(int(limit), 100))
        skip = max(0, int(skip))

        query = """
        MATCH (l:MarketplaceListing)
        WHERE l.status = "active"
        RETURN l {.*} AS entity
        ORDER BY l.created_at DESC
        SKIP $skip
        LIMIT $limit
        """
        results = await self.client.execute(
            query, {"skip": skip, "limit": limit}
        )
        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def find_by_seller(self, seller_id: str, limit: int = 100) -> list[CapsuleListing]:
        """Find all listings by a seller."""
        return await self.find_by_field("seller_id", seller_id, limit)

    async def find_by_capsule(self, capsule_id: str) -> CapsuleListing | None:
        """Find listing for a specific capsule."""
        results = await self.find_by_field("capsule_id", capsule_id, 1)
        return results[0] if results else None

    async def increment_view_count(self, listing_id: str) -> None:
        """Increment view count for a listing."""
        query = """
        MATCH (l:MarketplaceListing {id: $id})
        SET l.view_count = l.view_count + 1
        """
        await self.client.execute(query, {"id": listing_id})

    def _to_model(self, record: dict[str, Any]) -> CapsuleListing | None:
        if not record:
            return None
        try:
            if "currency" in record and isinstance(record["currency"], str):
                record["currency"] = Currency(record["currency"])
            if "license_type" in record and isinstance(record["license_type"], str):
                record["license_type"] = LicenseType(record["license_type"])
            if "status" in record and isinstance(record["status"], str):
                record["status"] = ListingStatus(record["status"])
            if "price" in record and isinstance(record["price"], str):
                record["price"] = Decimal(record["price"])
            return CapsuleListing.model_validate(record)
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error("Failed to convert listing record", error=str(e))
            return None


class PurchaseRepository(BaseRepository[Purchase, Purchase, Purchase]):
    """Repository for purchase records."""

    @property
    def node_label(self) -> str:
        return "MarketplacePurchase"

    @property
    def model_class(self) -> type[Purchase]:
        cls: type[Purchase] = Purchase
        return cls

    async def create(self, data: Purchase, **kwargs: Any) -> Purchase:
        """Create a new purchase record."""
        purchase_id = data.id or self._generate_id()
        now = self._now()

        query = """
        CREATE (p:MarketplacePurchase {
            id: $id,
            listing_id: $listing_id,
            capsule_id: $capsule_id,
            buyer_id: $buyer_id,
            seller_id: $seller_id,
            price: $price,
            currency: $currency,
            license_type: $license_type,
            payment_status: $payment_status,
            seller_revenue: $seller_revenue,
            platform_fee: $platform_fee,
            lineage_revenue: $lineage_revenue,
            treasury_contribution: $treasury_contribution,
            purchased_at: $purchased_at
        })
        RETURN p {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": purchase_id,
                "listing_id": data.listing_id,
                "capsule_id": data.capsule_id,
                "buyer_id": data.buyer_id,
                "seller_id": data.seller_id,
                "price": str(data.price),
                "currency": data.currency.value,
                "license_type": data.license_type.value,
                "payment_status": data.payment_status.value,
                "seller_revenue": str(data.seller_revenue),
                "platform_fee": str(data.platform_fee),
                "lineage_revenue": str(data.lineage_revenue),
                "treasury_contribution": str(data.treasury_contribution),
                "purchased_at": now.isoformat(),
            },
        )

        if result is None:
            raise RuntimeError("Failed to create purchase")
        purchase = self._to_model(result["entity"])
        if purchase is None:
            raise RuntimeError("Failed to deserialize created purchase")
        return purchase

    async def update(self, entity_id: str, data: Purchase) -> Purchase | None:
        """Purchases are mostly immutable - only status can change for refunds."""
        query = """
        MATCH (p:MarketplacePurchase {id: $id})
        SET p.payment_status = $payment_status,
            p.refunded_at = $refunded_at
        RETURN p {.*} AS entity
        """
        result = await self.client.execute_single(
            query,
            {
                "id": entity_id,
                "payment_status": data.payment_status.value,
                "refunded_at": data.refunded_at.isoformat() if data.refunded_at else None,
            },
        )
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def find_by_buyer(self, buyer_id: str, limit: int = 100) -> list[Purchase]:
        """Find all purchases by a buyer."""
        return await self.find_by_field("buyer_id", buyer_id, limit)

    async def find_by_seller(self, seller_id: str, limit: int = 100) -> list[Purchase]:
        """Find all sales by a seller."""
        return await self.find_by_field("seller_id", seller_id, limit)

    async def find_by_capsule(
        self, capsule_id: str, buyer_id: str
    ) -> Purchase | None:
        """Check if buyer has purchased a specific capsule."""
        query = """
        MATCH (p:MarketplacePurchase {capsule_id: $capsule_id, buyer_id: $buyer_id})
        WHERE p.payment_status = "completed"
        RETURN p {.*} AS entity
        LIMIT 1
        """
        result = await self.client.execute_single(
            query, {"capsule_id": capsule_id, "buyer_id": buyer_id}
        )
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    def _to_model(self, record: dict[str, Any]) -> Purchase | None:
        if not record:
            return None
        try:
            if "currency" in record and isinstance(record["currency"], str):
                record["currency"] = Currency(record["currency"])
            if "license_type" in record and isinstance(record["license_type"], str):
                record["license_type"] = LicenseType(record["license_type"])
            if "payment_status" in record and isinstance(record["payment_status"], str):
                record["payment_status"] = PaymentStatus(record["payment_status"])
            for field in [
                "price",
                "seller_revenue",
                "platform_fee",
                "lineage_revenue",
                "treasury_contribution",
            ]:
                if field in record and isinstance(record[field], str):
                    record[field] = Decimal(record[field])
            return Purchase.model_validate(record)
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error("Failed to convert purchase record", error=str(e))
            return None


class CartRepository:
    """Repository for shopping carts."""

    def __init__(self, client: Neo4jClient):
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def get_cart(self, user_id: str) -> Cart:
        """Get or create cart for user."""
        query = """
        MERGE (c:ShoppingCart {user_id: $user_id})
        ON CREATE SET c.id = $new_id, c.updated_at = $now
        RETURN c {.*} AS cart
        """
        result = await self.client.execute_single(
            query,
            {
                "user_id": user_id,
                "new_id": str(uuid4()),
                "now": datetime.now(UTC).isoformat(),
            },
        )

        cart = Cart(
            id=result["cart"].get("id") if result else str(uuid4()),
            user_id=user_id,
            items=[],
        )

        # Load cart items
        items_query = """
        MATCH (c:ShoppingCart {user_id: $user_id})-[:HAS_ITEM]->(i:CartItem)
        RETURN i {.*} AS item
        """
        items_result = await self.client.execute(items_query, {"user_id": user_id})
        for item_record in items_result:
            if item_record.get("item"):
                item_data = item_record["item"]
                cart.items.append(
                    CartItem(
                        id=item_data.get("id"),
                        listing_id=item_data.get("listing_id"),
                        capsule_id=item_data.get("capsule_id"),
                        price=Decimal(item_data.get("price", "0")),
                        currency=Currency(item_data.get("currency", "FORGE")),
                        title=item_data.get("title", ""),
                    )
                )

        return cart

    async def add_item(self, user_id: str, item: CartItem) -> Cart:
        """Add item to cart."""
        # Ensure cart exists
        await self.get_cart(user_id)

        query = """
        MATCH (c:ShoppingCart {user_id: $user_id})
        CREATE (i:CartItem {
            id: $item_id,
            listing_id: $listing_id,
            capsule_id: $capsule_id,
            price: $price,
            currency: $currency,
            title: $title,
            added_at: $added_at
        })
        CREATE (c)-[:HAS_ITEM]->(i)
        SET c.updated_at = $now
        """
        await self.client.execute(
            query,
            {
                "user_id": user_id,
                "item_id": item.id,
                "listing_id": item.listing_id,
                "capsule_id": item.capsule_id,
                "price": str(item.price),
                "currency": item.currency.value,
                "title": item.title,
                "added_at": item.added_at.isoformat(),
                "now": datetime.now(UTC).isoformat(),
            },
        )
        return await self.get_cart(user_id)

    async def remove_item(self, user_id: str, listing_id: str) -> Cart:
        """Remove item from cart."""
        query = """
        MATCH (c:ShoppingCart {user_id: $user_id})-[r:HAS_ITEM]->(i:CartItem {listing_id: $listing_id})
        DELETE r, i
        SET c.updated_at = $now
        """
        await self.client.execute(
            query,
            {
                "user_id": user_id,
                "listing_id": listing_id,
                "now": datetime.now(UTC).isoformat(),
            },
        )
        return await self.get_cart(user_id)

    async def clear_cart(self, user_id: str) -> None:
        """Clear all items from cart."""
        query = """
        MATCH (c:ShoppingCart {user_id: $user_id})-[r:HAS_ITEM]->(i:CartItem)
        DELETE r, i
        SET c.updated_at = $now
        """
        await self.client.execute(
            query, {"user_id": user_id, "now": datetime.now(UTC).isoformat()}
        )


class LicenseRepository(BaseRepository[License, License, License]):
    """Repository for license records."""

    @property
    def node_label(self) -> str:
        return "CapsuleLicense"

    @property
    def model_class(self) -> type[License]:
        cls: type[License] = License
        return cls

    async def create(self, data: License, **kwargs: Any) -> License:
        """Create a new license."""
        license_id = data.id or self._generate_id()
        now = self._now()

        query = """
        CREATE (lic:CapsuleLicense {
            id: $id,
            purchase_id: $purchase_id,
            capsule_id: $capsule_id,
            holder_id: $holder_id,
            grantor_id: $grantor_id,
            license_type: $license_type,
            granted_at: $granted_at,
            expires_at: $expires_at,
            revoked_at: $revoked_at,
            can_view: $can_view,
            can_download: $can_download,
            can_derive: $can_derive,
            can_resell: $can_resell,
            access_count: 0,
            last_accessed_at: $last_accessed_at
        })
        RETURN lic {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": license_id,
                "purchase_id": data.purchase_id,
                "capsule_id": data.capsule_id,
                "holder_id": data.holder_id,
                "grantor_id": data.grantor_id,
                "license_type": data.license_type.value,
                "granted_at": now.isoformat(),
                "expires_at": data.expires_at.isoformat() if data.expires_at else None,
                "revoked_at": None,
                "can_view": data.can_view,
                "can_download": data.can_download,
                "can_derive": data.can_derive,
                "can_resell": data.can_resell,
                "last_accessed_at": None,
            },
        )

        if result is None:
            raise RuntimeError("Failed to create license")
        license_obj = self._to_model(result["entity"])
        if license_obj is None:
            raise RuntimeError("Failed to deserialize created license")
        return license_obj

    async def update(self, entity_id: str, data: License) -> License | None:
        """Update license (for revocation, access tracking)."""
        query = """
        MATCH (lic:CapsuleLicense {id: $id})
        SET lic.revoked_at = $revoked_at,
            lic.access_count = $access_count,
            lic.last_accessed_at = $last_accessed_at
        RETURN lic {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": entity_id,
                "revoked_at": data.revoked_at.isoformat() if data.revoked_at else None,
                "access_count": data.access_count,
                "last_accessed_at": (
                    data.last_accessed_at.isoformat() if data.last_accessed_at else None
                ),
            },
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def find_valid_license(
        self, capsule_id: str, holder_id: str
    ) -> License | None:
        """Find a valid (non-expired, non-revoked) license."""
        query = """
        MATCH (lic:CapsuleLicense {capsule_id: $capsule_id, holder_id: $holder_id})
        WHERE lic.revoked_at IS NULL
          AND (lic.expires_at IS NULL OR datetime(lic.expires_at) > datetime())
        RETURN lic {.*} AS entity
        LIMIT 1
        """
        result = await self.client.execute_single(
            query, {"capsule_id": capsule_id, "holder_id": holder_id}
        )
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def find_by_holder(self, holder_id: str, limit: int = 100) -> list[License]:
        """Find all licenses held by a user."""
        return await self.find_by_field("holder_id", holder_id, limit)

    async def record_access(self, license_id: str) -> None:
        """Record an access event for a license."""
        query = """
        MATCH (lic:CapsuleLicense {id: $id})
        SET lic.access_count = lic.access_count + 1,
            lic.last_accessed_at = $now
        """
        await self.client.execute(
            query, {"id": license_id, "now": datetime.now(UTC).isoformat()}
        )

    async def revoke(self, license_id: str) -> License | None:
        """Revoke a license."""
        query = """
        MATCH (lic:CapsuleLicense {id: $id})
        SET lic.revoked_at = $now
        RETURN lic {.*} AS entity
        """
        result = await self.client.execute_single(
            query, {"id": license_id, "now": datetime.now(UTC).isoformat()}
        )
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    def _to_model(self, record: dict[str, Any]) -> License | None:
        if not record:
            return None
        try:
            if "license_type" in record and isinstance(record["license_type"], str):
                record["license_type"] = LicenseType(record["license_type"])
            return License.model_validate(record)
        except (ValueError, TypeError, KeyError) as e:
            self.logger.error("Failed to convert license record", error=str(e))
            return None


class MarketplaceRepository:
    """
    Unified marketplace repository providing access to all marketplace entities.

    Usage:
        repo = MarketplaceRepository(neo4j_client)
        await repo.initialize()

        # Access sub-repositories
        listing = await repo.listings.create(...)
        purchase = await repo.purchases.create(...)
        cart = await repo.carts.get_cart(user_id)
        license = await repo.licenses.find_valid_license(...)
    """

    def __init__(self, client: Neo4jClient):
        self.client = client
        self.listings = ListingRepository(client)
        self.purchases = PurchaseRepository(client)
        self.carts = CartRepository(client)
        self.licenses = LicenseRepository(client)
        self.logger = structlog.get_logger(__name__)

    async def initialize(self) -> None:
        """Create indexes for marketplace entities."""
        indexes = [
            "CREATE INDEX listing_capsule_idx IF NOT EXISTS FOR (l:MarketplaceListing) ON (l.capsule_id)",
            "CREATE INDEX listing_seller_idx IF NOT EXISTS FOR (l:MarketplaceListing) ON (l.seller_id)",
            "CREATE INDEX listing_status_idx IF NOT EXISTS FOR (l:MarketplaceListing) ON (l.status)",
            "CREATE INDEX purchase_buyer_idx IF NOT EXISTS FOR (p:MarketplacePurchase) ON (p.buyer_id)",
            "CREATE INDEX purchase_seller_idx IF NOT EXISTS FOR (p:MarketplacePurchase) ON (p.seller_id)",
            "CREATE INDEX license_holder_idx IF NOT EXISTS FOR (lic:CapsuleLicense) ON (lic.holder_id)",
            "CREATE INDEX license_capsule_idx IF NOT EXISTS FOR (lic:CapsuleLicense) ON (lic.capsule_id)",
            "CREATE INDEX cart_user_idx IF NOT EXISTS FOR (c:ShoppingCart) ON (c.user_id)",
        ]

        for index_query in indexes:
            try:
                await self.client.execute(index_query)
            except (RuntimeError, OSError, ValueError) as e:
                self.logger.warning("Index creation warning", query=index_query, error=str(e))

        self.logger.info("marketplace_repository_initialized")

    async def get_stats(self) -> MarketplaceStats:
        """Get marketplace statistics."""
        query = """
        MATCH (l:MarketplaceListing)
        WITH count(l) AS total_listings,
             count(CASE WHEN l.status = "active" THEN 1 END) AS active_listings
        OPTIONAL MATCH (p:MarketplacePurchase)
        WHERE p.payment_status = "completed"
        WITH total_listings, active_listings,
             count(p) AS total_sales,
             coalesce(sum(toFloat(p.price)), 0) AS total_revenue
        RETURN total_listings, active_listings, total_sales, total_revenue
        """

        result = await self.client.execute_single(query)

        if result:
            return MarketplaceStats(
                total_listings=result.get("total_listings", 0),
                active_listings=result.get("active_listings", 0),
                total_sales=result.get("total_sales", 0),
                total_revenue=Decimal(str(result.get("total_revenue", 0))),
            )

        return MarketplaceStats()
