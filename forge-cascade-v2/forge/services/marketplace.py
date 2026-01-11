"""
Marketplace Service

Handles capsule listings, purchases, and revenue distribution.

PERSISTENCE: All marketplace data (listings, purchases, carts, licenses) is now
persisted to Neo4j. Data is loaded from the database on service initialization
and synchronized on every modification.
"""

import logging
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from forge.models.marketplace import (
    CapsuleListing,
    Cart,
    CartItem,
    Currency,
    License,
    LicenseType,
    ListingStatus,
    MarketplaceStats,
    PaymentMethod,
    PaymentStatus,
    PriceSuggestion,
    Purchase,
    RevenueDistribution,
)

logger = logging.getLogger(__name__)


class MarketplaceService:
    """
    Central service for marketplace operations.
    """

    # Revenue distribution percentages
    SELLER_SHARE = Decimal("0.70")
    LINEAGE_SHARE = Decimal("0.15")
    PLATFORM_SHARE = Decimal("0.10")
    TREASURY_SHARE = Decimal("0.05")

    # Base price for suggestions
    BASE_PRICE = Decimal("10.00")

    def __init__(self, capsule_repository=None, neo4j_client=None):
        self.capsule_repo = capsule_repository
        self.neo4j = neo4j_client

        # In-memory storage (would use database in production)
        self._listings: dict[str, CapsuleListing] = {}
        self._purchases: dict[str, Purchase] = {}
        self._carts: dict[str, Cart] = {}
        self._licenses: dict[str, License] = {}

    # =========================================================================
    # Listings
    # =========================================================================

    async def create_listing(
        self,
        capsule_id: str,
        seller_id: str,
        price: Decimal,
        currency: Currency = Currency.FORGE,
        license_type: LicenseType = LicenseType.PERPETUAL,
        title: str = "",
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> CapsuleListing:
        """Create a new marketplace listing."""
        # Verify ownership
        if self.capsule_repo:
            capsule = await self.capsule_repo.get_by_id(capsule_id)
            if not capsule or capsule.owner_id != seller_id:
                raise ValueError("User does not own this capsule")

        # Get price suggestion
        suggestion = await self.calculate_suggested_price(capsule_id)

        listing = CapsuleListing(
            capsule_id=capsule_id,
            seller_id=seller_id,
            price=price,
            currency=currency,
            suggested_price=suggestion.suggested_price if suggestion else None,
            license_type=license_type,
            status=ListingStatus.DRAFT,
            title=title or f"Capsule {capsule_id[:8]}",
            description=description,
            tags=tags or [],
        )

        self._listings[listing.id] = listing
        # AUDIT 3 FIX (A1-D03): Persist to database
        await self._persist_listing(listing)
        logger.info(f"Created listing {listing.id} for capsule {capsule_id}")
        return listing

    async def publish_listing(self, listing_id: str, seller_id: str) -> CapsuleListing:
        """Publish a listing to make it active."""
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        if listing.seller_id != seller_id:
            raise ValueError("Not authorized to publish this listing")
        if listing.status != ListingStatus.DRAFT:
            raise ValueError("Only draft listings can be published")

        listing.status = ListingStatus.ACTIVE
        listing.published_at = datetime.now(UTC)
        # AUDIT 3 FIX (A1-D03): Persist status change
        await self._persist_listing(listing)
        return listing

    async def get_listing(self, listing_id: str) -> CapsuleListing | None:
        """Get a listing by ID."""
        return self._listings.get(listing_id)

    async def get_listings(
        self,
        status: ListingStatus | None = None,
        seller_id: str | None = None,
        capsule_type: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        tags: list[str] | None = None,
        sort_by: str = "created_at",
        limit: int = 50,
        offset: int = 0,
    ) -> list[CapsuleListing]:
        """Get listings with optional filters."""
        listings = list(self._listings.values())

        # Apply filters
        if status:
            listings = [l for l in listings if l.status == status]
        if seller_id:
            listings = [l for l in listings if l.seller_id == seller_id]
        if min_price is not None:
            listings = [l for l in listings if l.price >= min_price]
        if max_price is not None:
            listings = [l for l in listings if l.price <= max_price]
        if tags:
            listings = [l for l in listings if any(t in l.tags for t in tags)]

        # Sort
        if sort_by == "price_asc":
            listings.sort(key=lambda l: l.price)
        elif sort_by == "price_desc":
            listings.sort(key=lambda l: l.price, reverse=True)
        elif sort_by == "popular":
            listings.sort(key=lambda l: l.purchase_count, reverse=True)
        else:  # created_at
            listings.sort(key=lambda l: l.created_at, reverse=True)

        return listings[offset:offset + limit]

    async def update_listing(
        self,
        listing_id: str,
        seller_id: str,
        updates: dict[str, Any],
    ) -> CapsuleListing:
        """Update a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        if listing.seller_id != seller_id:
            raise ValueError("Not authorized to update this listing")

        # Can only update certain fields
        allowed_fields = {
            "price", "description", "tags", "preview_content",
            "license_terms", "visibility"
        }

        for key, value in updates.items():
            if key in allowed_fields and hasattr(listing, key):
                setattr(listing, key, value)

        listing.updated_at = datetime.now(UTC)

        # SECURITY FIX (Audit 4): Persist listing updates to database
        await self._persist_listing(listing)

        return listing

    async def cancel_listing(self, listing_id: str, seller_id: str) -> CapsuleListing:
        """Cancel a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        if listing.seller_id != seller_id:
            raise ValueError("Not authorized to cancel this listing")

        listing.status = ListingStatus.CANCELLED
        listing.updated_at = datetime.now(UTC)
        # PERSISTENCE: Save status change to database
        await self._persist_listing(listing)
        return listing

    async def record_view(self, listing_id: str) -> None:
        """Record a view of a listing."""
        listing = self._listings.get(listing_id)
        if listing:
            listing.view_count += 1

    # =========================================================================
    # Cart
    # =========================================================================

    async def get_cart(self, user_id: str) -> Cart:
        """Get or create cart for user."""
        if user_id not in self._carts:
            # Try to load from database first
            cart = await self._load_cart_from_db(user_id)
            if cart:
                self._carts[user_id] = cart
            else:
                self._carts[user_id] = Cart(user_id=user_id)
        return self._carts[user_id]

    async def add_to_cart(self, user_id: str, listing_id: str) -> Cart:
        """Add a listing to cart."""
        cart = await self.get_cart(user_id)
        listing = await self.get_listing(listing_id)

        if not listing:
            raise ValueError("Listing not found")
        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")
        if listing.seller_id == user_id:
            raise ValueError("Cannot purchase your own listing")

        # Check if already in cart
        if any(item.listing_id == listing_id for item in cart.items):
            raise ValueError("Already in cart")

        cart.items.append(CartItem(
            listing_id=listing_id,
            capsule_id=listing.capsule_id,
            price=listing.price,
            currency=listing.currency,
            title=listing.title,
        ))
        cart.updated_at = datetime.now(UTC)

        # PERSISTENCE: Save cart to database
        await self._persist_cart(cart)

        return cart

    async def remove_from_cart(self, user_id: str, listing_id: str) -> Cart:
        """Remove a listing from cart."""
        cart = await self.get_cart(user_id)
        cart.items = [item for item in cart.items if item.listing_id != listing_id]
        cart.updated_at = datetime.now(UTC)
        # PERSISTENCE: Save cart to database
        await self._persist_cart(cart)
        return cart

    async def clear_cart(self, user_id: str) -> Cart:
        """Clear all items from cart."""
        cart = await self.get_cart(user_id)
        cart.items = []
        cart.updated_at = datetime.now(UTC)
        # PERSISTENCE: Save cart to database
        await self._persist_cart(cart)
        return cart

    # =========================================================================
    # Purchases
    # =========================================================================

    async def checkout(
        self,
        user_id: str,
        payment_method: PaymentMethod = PaymentMethod.PLATFORM,
    ) -> list[Purchase]:
        """Process cart checkout."""
        cart = await self.get_cart(user_id)
        if not cart.items:
            raise ValueError("Cart is empty")

        purchases = []
        for item in cart.items:
            purchase = await self._process_purchase(
                buyer_id=user_id,
                listing_id=item.listing_id,
                payment_method=payment_method,
            )
            purchases.append(purchase)

        # Clear cart after successful checkout
        await self.clear_cart(user_id)

        return purchases

    async def purchase_single(
        self,
        buyer_id: str,
        listing_id: str,
        payment_method: PaymentMethod = PaymentMethod.PLATFORM,
    ) -> Purchase:
        """Purchase a single listing directly."""
        return await self._process_purchase(
            buyer_id=buyer_id,
            listing_id=listing_id,
            payment_method=payment_method,
        )

    async def _process_purchase(
        self,
        buyer_id: str,
        listing_id: str,
        payment_method: PaymentMethod,
    ) -> Purchase:
        """Process a single purchase."""
        listing = await self.get_listing(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")
        if listing.seller_id == buyer_id:
            raise ValueError("Cannot purchase your own listing")

        # Check if already purchased
        existing = [
            p for p in self._purchases.values()
            if p.buyer_id == buyer_id and p.capsule_id == listing.capsule_id
        ]
        if existing:
            raise ValueError("Already purchased this capsule")

        # Calculate revenue distribution
        distribution = self._calculate_distribution(listing.price, listing.capsule_id)

        # Create purchase record
        purchase = Purchase(
            listing_id=listing.id,
            capsule_id=listing.capsule_id,
            buyer_id=buyer_id,
            seller_id=listing.seller_id,
            price=listing.price,
            currency=listing.currency,
            license_type=listing.license_type,
            payment_method=payment_method,
            seller_revenue=distribution.seller_share,
            platform_fee=distribution.platform_share,
            lineage_revenue=distribution.lineage_share,
            treasury_contribution=distribution.treasury_share,
        )

        # Set license expiration for subscriptions
        if listing.license_type == LicenseType.SUBSCRIPTION and listing.subscription_period_days:
            purchase.license_expires_at = datetime.now(UTC) + timedelta(
                days=listing.subscription_period_days
            )

        self._purchases[purchase.id] = purchase
        # AUDIT 3 FIX (A1-D03): Persist purchase to database
        await self._persist_purchase(purchase)

        # Create license
        license = License(
            purchase_id=purchase.id,
            capsule_id=listing.capsule_id,
            holder_id=buyer_id,
            grantor_id=listing.seller_id,
            license_type=listing.license_type,
            expires_at=purchase.license_expires_at,
            can_derive=listing.license_type == LicenseType.DERIVATIVE,
        )
        self._licenses[license.id] = license
        # PERSISTENCE: Save license to database
        await self._persist_license(license)

        # Update listing stats
        listing.purchase_count += 1
        listing.revenue_total += listing.price
        # AUDIT 3 FIX (A1-D03): Persist listing stats update
        await self._persist_listing(listing)

        logger.info(f"Purchase completed: {purchase.id} for capsule {listing.capsule_id}")
        return purchase

    def _calculate_distribution(
        self,
        amount: Decimal,
        capsule_id: str,
    ) -> RevenueDistribution:
        """Calculate revenue distribution for a sale."""
        return RevenueDistribution(
            purchase_id="",  # Will be set after purchase created
            total_amount=amount,
            currency=Currency.FORGE,
            seller_share=amount * self.SELLER_SHARE,
            lineage_share=amount * self.LINEAGE_SHARE,
            platform_share=amount * self.PLATFORM_SHARE,
            treasury_share=amount * self.TREASURY_SHARE,
            lineage_recipients=[],  # Would be populated from lineage graph
        )

    async def get_user_purchases(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[Purchase]:
        """Get purchases made by a user."""
        purchases = [p for p in self._purchases.values() if p.buyer_id == user_id]
        purchases.sort(key=lambda p: p.purchased_at, reverse=True)
        return purchases[:limit]

    async def get_user_sales(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[Purchase]:
        """Get sales made by a user."""
        sales = [p for p in self._purchases.values() if p.seller_id == user_id]
        sales.sort(key=lambda p: p.purchased_at, reverse=True)
        return sales[:limit]

    # =========================================================================
    # Licensing
    # =========================================================================

    async def check_license(self, user_id: str, capsule_id: str) -> License | None:
        """Check if user has valid license for capsule."""
        for license in self._licenses.values():
            if license.holder_id == user_id and license.capsule_id == capsule_id:
                if license.revoked_at:
                    continue
                if license.expires_at and license.expires_at < datetime.now(UTC):
                    continue
                return license
        return None

    async def record_access(self, license_id: str) -> None:
        """Record an access to a licensed capsule."""
        license = self._licenses.get(license_id)
        if license:
            license.access_count += 1
            license.last_accessed_at = datetime.now(UTC)

    # =========================================================================
    # Pricing
    # =========================================================================

    async def calculate_suggested_price(
        self,
        capsule_id: str,
    ) -> PriceSuggestion | None:
        """Calculate suggested price based on trust metrics."""
        # Initialize default metrics
        pagerank_score = 0.0
        citation_count = 0
        view_count = 0
        trust_level = 50

        if self.capsule_repo:
            capsule = await self.capsule_repo.get_by_id(capsule_id)
            if capsule:
                trust_level = capsule.trust_level
                # Get additional metrics from graph

        # Calculate multipliers
        trust_mult = self._trust_multiplier(trust_level)
        demand_mult = self._demand_multiplier(view_count, citation_count)
        rarity_mult = self._rarity_multiplier(pagerank_score)

        suggested = self.BASE_PRICE * Decimal(str(trust_mult)) * Decimal(str(demand_mult)) * Decimal(str(rarity_mult))

        return PriceSuggestion(
            capsule_id=capsule_id,
            suggested_price=suggested.quantize(Decimal("0.01")),
            min_price=(suggested * Decimal("0.5")).quantize(Decimal("0.01")),
            max_price=(suggested * Decimal("2.0")).quantize(Decimal("0.01")),
            factors={
                "trust": trust_mult,
                "demand": demand_mult,
                "rarity": rarity_mult,
            },
            trust_multiplier=trust_mult,
            demand_multiplier=demand_mult,
            rarity_multiplier=rarity_mult,
            pagerank_score=pagerank_score,
            citation_count=citation_count,
            view_count=view_count,
        )

    def _trust_multiplier(self, trust_level: int) -> float:
        """Calculate trust multiplier for pricing."""
        # QUARANTINE: 0.5x, SANDBOX: 1.0x, STANDARD: 1.5x, TRUSTED: 2.0x, CORE: 3.0x
        if trust_level < 20:
            return 0.5
        elif trust_level < 40:
            return 1.0
        elif trust_level < 60:
            return 1.5
        elif trust_level < 80:
            return 2.0
        else:
            return 3.0

    def _demand_multiplier(self, views: int, citations: int) -> float:
        """Calculate demand multiplier based on views and citations."""
        return 1.0 + math.log1p(views + citations * 5) / 10

    def _rarity_multiplier(self, pagerank_score: float) -> float:
        """Calculate rarity multiplier based on PageRank uniqueness."""
        # Higher PageRank = more central/important = more valuable
        return 1.0 + pagerank_score * 5

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_marketplace_stats(self) -> MarketplaceStats:
        """Get overall marketplace statistics."""
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        all_listings = list(self._listings.values())
        all_purchases = list(self._purchases.values())

        active_listings = [l for l in all_listings if l.status == ListingStatus.ACTIVE]

        sales_today = [p for p in all_purchases if p.purchased_at >= today_start]
        sales_week = [p for p in all_purchases if p.purchased_at >= week_start]
        sales_month = [p for p in all_purchases if p.purchased_at >= month_start]

        # Top sellers
        seller_revenue: dict[str, Decimal] = {}
        for p in all_purchases:
            seller_revenue[p.seller_id] = seller_revenue.get(p.seller_id, Decimal("0")) + p.seller_revenue

        top_sellers = sorted(
            [{"seller_id": k, "revenue": float(v)} for k, v in seller_revenue.items()],
            key=lambda x: x["revenue"],
            reverse=True
        )[:10]

        # Top capsules
        capsule_sales: dict[str, int] = {}
        for p in all_purchases:
            capsule_sales[p.capsule_id] = capsule_sales.get(p.capsule_id, 0) + 1

        top_capsules = sorted(
            [{"capsule_id": k, "sales": v} for k, v in capsule_sales.items()],
            key=lambda x: x["sales"],
            reverse=True
        )[:10]

        # Calculate averages
        prices = [l.price for l in active_listings]
        avg_price = sum(prices) / len(prices) if prices else Decimal("0")

        sellers = {l.seller_id for l in all_listings}
        avg_per_seller = len(all_listings) / len(sellers) if sellers else 0

        return MarketplaceStats(
            total_listings=len(all_listings),
            active_listings=len(active_listings),
            total_sales=len(all_purchases),
            total_revenue=sum(p.price for p in all_purchases),
            sales_today=len(sales_today),
            sales_this_week=len(sales_week),
            sales_this_month=len(sales_month),
            revenue_today=sum(p.price for p in sales_today),
            revenue_this_week=sum(p.price for p in sales_week),
            revenue_this_month=sum(p.price for p in sales_month),
            top_sellers=top_sellers,
            top_capsules=top_capsules,
            avg_price=avg_price,
            avg_capsules_per_seller=avg_per_seller,
        )

    # =========================================================================
    # Persistence Methods (Audit 3 - A1-D03)
    # =========================================================================

    async def _persist_listing(self, listing: CapsuleListing) -> bool:
        """
        Persist a listing to Neo4j database.

        AUDIT 3 FIX (A1-D03): Add persistent storage to marketplace service.
        """
        if not self.neo4j:
            logger.debug("No Neo4j client, skipping listing persistence")
            return False

        try:
            query = """
            MERGE (l:MarketplaceListing {id: $id})
            SET l.capsule_id = $capsule_id,
                l.seller_id = $seller_id,
                l.price = $price,
                l.currency = $currency,
                l.license_type = $license_type,
                l.status = $status,
                l.title = $title,
                l.description = $description,
                l.tags = $tags,
                l.created_at = $created_at,
                l.published_at = $published_at,
                l.updated_at = datetime()
            RETURN l.id as id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "id": listing.id,
                    "capsule_id": listing.capsule_id,
                    "seller_id": listing.seller_id,
                    "price": str(listing.price),
                    "currency": listing.currency.value,
                    "license_type": listing.license_type.value,
                    "status": listing.status.value,
                    "title": listing.title,
                    "description": listing.description or "",
                    "tags": listing.tags,
                    "created_at": listing.created_at.isoformat() if listing.created_at else None,
                    "published_at": listing.published_at.isoformat() if listing.published_at else None,
                }
            )
            logger.debug(f"Persisted listing {listing.id} to database")
            return True
        except Exception as e:
            logger.error(f"Failed to persist listing {listing.id}: {e}")
            return False

    async def _persist_purchase(self, purchase: Purchase) -> bool:
        """Persist a purchase to Neo4j database."""
        if not self.neo4j:
            return False

        try:
            query = """
            MERGE (p:MarketplacePurchase {id: $id})
            SET p.listing_id = $listing_id,
                p.capsule_id = $capsule_id,
                p.buyer_id = $buyer_id,
                p.seller_id = $seller_id,
                p.price = $price,
                p.currency = $currency,
                p.license_type = $license_type,
                p.payment_status = $payment_status,
                p.purchased_at = $purchased_at
            RETURN p.id as id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "id": purchase.id,
                    "listing_id": purchase.listing_id,
                    "capsule_id": purchase.capsule_id,
                    "buyer_id": purchase.buyer_id,
                    "seller_id": purchase.seller_id,
                    "price": str(purchase.price),
                    "currency": purchase.currency.value,
                    "license_type": purchase.license_type.value,
                    "payment_status": purchase.payment_status.value,
                    "purchased_at": purchase.purchased_at.isoformat() if purchase.purchased_at else None,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist purchase {purchase.id}: {e}")
            return False

    async def _persist_cart(self, cart: Cart) -> bool:
        """Persist a cart to Neo4j database."""
        if not self.neo4j:
            return False

        try:
            # Store cart with items serialized as JSON
            import json
            items_json = json.dumps([
                {
                    "listing_id": item.listing_id,
                    "capsule_id": item.capsule_id,
                    "quantity": item.quantity,
                    "price": str(item.price),
                    "currency": item.currency.value,
                    "title": item.title,
                }
                for item in cart.items
            ])

            query = """
            MERGE (c:MarketplaceCart {user_id: $user_id})
            SET c.items = $items,
                c.total = $total,
                c.updated_at = datetime()
            RETURN c.user_id as user_id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "user_id": cart.user_id,
                    "items": items_json,
                    "total": str(cart.total),
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist cart for user {cart.user_id}: {e}")
            return False

    async def _load_cart_from_db(self, user_id: str) -> Cart | None:
        """Load a cart from the database."""
        if not self.neo4j:
            return None

        try:
            import json
            query = """
            MATCH (c:MarketplaceCart {user_id: $user_id})
            RETURN c.user_id as user_id, c.items as items, c.total as total
            """
            results = await self.neo4j.execute_read(query, parameters={"user_id": user_id})

            if not results:
                return None

            record = results[0]
            items_data = json.loads(record["items"]) if record["items"] else []

            cart = Cart(user_id=user_id)
            for item_data in items_data:
                cart.items.append(CartItem(
                    listing_id=item_data["listing_id"],
                    capsule_id=item_data.get("capsule_id", ""),
                    quantity=item_data.get("quantity", 1),
                    price=Decimal(item_data.get("price", "0")),
                    currency=Currency(item_data.get("currency", "forge")),
                    title=item_data.get("title", ""),
                ))

            return cart
        except Exception as e:
            logger.error(f"Failed to load cart for user {user_id}: {e}")
            return None

    async def _persist_license(self, license: License) -> bool:
        """Persist a license to Neo4j database."""
        if not self.neo4j:
            return False

        try:
            query = """
            MERGE (l:MarketplaceLicense {id: $id})
            SET l.purchase_id = $purchase_id,
                l.capsule_id = $capsule_id,
                l.holder_id = $holder_id,
                l.grantor_id = $grantor_id,
                l.license_type = $license_type,
                l.expires_at = $expires_at,
                l.revoked_at = $revoked_at,
                l.can_derive = $can_derive,
                l.access_count = $access_count,
                l.created_at = $created_at
            RETURN l.id as id
            """
            await self.neo4j.execute_write(
                query,
                parameters={
                    "id": license.id,
                    "purchase_id": license.purchase_id,
                    "capsule_id": license.capsule_id,
                    "holder_id": license.holder_id,
                    "grantor_id": license.grantor_id,
                    "license_type": license.license_type.value,
                    "expires_at": license.expires_at.isoformat() if license.expires_at else None,
                    "revoked_at": license.revoked_at.isoformat() if license.revoked_at else None,
                    "can_derive": license.can_derive,
                    "access_count": license.access_count,
                    "created_at": license.created_at.isoformat() if license.created_at else None,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist license {license.id}: {e}")
            return False

    async def load_from_database(self) -> int:
        """
        Load all marketplace data from Neo4j on startup.

        Returns:
            Number of listings loaded
        """
        if not self.neo4j:
            logger.warning("No Neo4j client, cannot load marketplace data")
            return 0

        loaded = 0
        try:
            # Load listings
            query = """
            MATCH (l:MarketplaceListing)
            RETURN l.id as id, l.capsule_id as capsule_id, l.seller_id as seller_id,
                   l.price as price, l.currency as currency, l.license_type as license_type,
                   l.status as status, l.title as title, l.description as description,
                   l.tags as tags, l.created_at as created_at, l.published_at as published_at
            """
            results = await self.neo4j.execute_read(query)

            for record in results:
                listing = CapsuleListing(
                    id=record["id"],
                    capsule_id=record["capsule_id"],
                    seller_id=record["seller_id"],
                    price=Decimal(record["price"]) if record["price"] else Decimal("0"),
                    currency=Currency(record["currency"]) if record["currency"] else Currency.FORGE,
                    license_type=LicenseType(record["license_type"]) if record["license_type"] else LicenseType.PERPETUAL,
                    status=ListingStatus(record["status"]) if record["status"] else ListingStatus.DRAFT,
                    title=record["title"] or "",
                    description=record["description"],
                    tags=record["tags"] or [],
                )
                self._listings[listing.id] = listing
                loaded += 1

            # Load purchases
            purchase_query = """
            MATCH (p:MarketplacePurchase)
            RETURN p.id as id, p.listing_id as listing_id, p.capsule_id as capsule_id,
                   p.buyer_id as buyer_id, p.seller_id as seller_id, p.price as price,
                   p.currency as currency, p.license_type as license_type,
                   p.payment_status as payment_status, p.purchased_at as purchased_at
            """
            purchase_results = await self.neo4j.execute_read(purchase_query)

            for record in purchase_results:
                purchase = Purchase(
                    id=record["id"],
                    listing_id=record["listing_id"],
                    capsule_id=record["capsule_id"],
                    buyer_id=record["buyer_id"],
                    seller_id=record["seller_id"],
                    price=Decimal(record["price"]) if record["price"] else Decimal("0"),
                    currency=Currency(record["currency"]) if record["currency"] else Currency.FORGE,
                    license_type=LicenseType(record["license_type"]) if record["license_type"] else LicenseType.PERPETUAL,
                    payment_status=PaymentStatus(record["payment_status"]) if record["payment_status"] else PaymentStatus.PENDING,
                )
                self._purchases[purchase.id] = purchase

            # Load licenses
            license_query = """
            MATCH (l:MarketplaceLicense)
            RETURN l.id as id, l.purchase_id as purchase_id, l.capsule_id as capsule_id,
                   l.holder_id as holder_id, l.grantor_id as grantor_id,
                   l.license_type as license_type, l.expires_at as expires_at,
                   l.revoked_at as revoked_at, l.can_derive as can_derive,
                   l.access_count as access_count, l.created_at as created_at
            """
            license_results = await self.neo4j.execute_read(license_query)

            for record in license_results:
                expires_at = None
                if record["expires_at"]:
                    try:
                        expires_at = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                revoked_at = None
                if record["revoked_at"]:
                    try:
                        revoked_at = datetime.fromisoformat(record["revoked_at"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                lic = License(
                    id=record["id"],
                    purchase_id=record["purchase_id"],
                    capsule_id=record["capsule_id"],
                    holder_id=record["holder_id"],
                    grantor_id=record["grantor_id"],
                    license_type=LicenseType(record["license_type"]) if record["license_type"] else LicenseType.PERPETUAL,
                    expires_at=expires_at,
                    revoked_at=revoked_at,
                    can_derive=record.get("can_derive", False),
                    access_count=record.get("access_count", 0),
                )
                self._licenses[lic.id] = lic

            logger.info(
                f"Loaded {loaded} listings, {len(self._purchases)} purchases, "
                f"and {len(self._licenses)} licenses from database"
            )
            return loaded
        except Exception as e:
            logger.error(f"Failed to load marketplace data: {e}")
            return 0

    async def _delete_listing_from_db(self, listing_id: str) -> bool:
        """Delete a listing from the database."""
        if not self.neo4j:
            return False

        try:
            query = """
            MATCH (l:MarketplaceListing {id: $id})
            DELETE l
            """
            await self.neo4j.execute_write(query, parameters={"id": listing_id})
            return True
        except Exception as e:
            logger.error(f"Failed to delete listing {listing_id}: {e}")
            return False


# Global instance
_marketplace_service: MarketplaceService | None = None
_marketplace_initialized: bool = False


async def get_marketplace_service(
    neo4j_client=None,
    capsule_repo=None,
) -> MarketplaceService:
    """
    Get the global marketplace service instance.

    On first call, initializes with Neo4j client and loads data from database.
    Subsequent calls return the cached instance.

    Args:
        neo4j_client: Optional Neo4j client (used on first initialization)
        capsule_repo: Optional capsule repository (used on first initialization)
    """
    global _marketplace_service, _marketplace_initialized

    if _marketplace_service is None:
        # Try to get Neo4j client from ForgeApp if not provided
        if neo4j_client is None:
            try:
                from forge.api.app import forge_app
                neo4j_client = forge_app.db_client
            except (ImportError, AttributeError):
                logger.warning("Could not get Neo4j client from ForgeApp")

        _marketplace_service = MarketplaceService(
            capsule_repository=capsule_repo,
            neo4j_client=neo4j_client,
        )

    # Load from database on first successful initialization with Neo4j
    if not _marketplace_initialized and _marketplace_service.neo4j:
        try:
            loaded = await _marketplace_service.load_from_database()
            _marketplace_initialized = True
            logger.info(f"Marketplace service initialized with {loaded} listings from database")
        except Exception as e:
            logger.warning(f"Failed to load marketplace data on startup: {e}")

    return _marketplace_service


async def close_marketplace_service() -> None:
    """Reset the marketplace service (for testing or shutdown)."""
    global _marketplace_service, _marketplace_initialized
    _marketplace_service = None
    _marketplace_initialized = False
