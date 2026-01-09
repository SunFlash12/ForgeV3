"""
Marketplace Service

Handles capsule listings, purchases, and revenue distribution.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any
import math

from forge.models.marketplace import (
    CapsuleListing,
    ListingStatus,
    LicenseType,
    Currency,
    Purchase,
    Cart,
    CartItem,
    License,
    PriceSuggestion,
    RevenueDistribution,
    MarketplaceStats,
    PaymentMethod,
    PaymentStatus,
)
from forge.models.base import generate_id, TrustLevel

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
        listing.published_at = datetime.now(timezone.utc)
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

        listing.updated_at = datetime.now(timezone.utc)
        return listing

    async def cancel_listing(self, listing_id: str, seller_id: str) -> CapsuleListing:
        """Cancel a listing."""
        listing = self._listings.get(listing_id)
        if not listing:
            raise ValueError("Listing not found")
        if listing.seller_id != seller_id:
            raise ValueError("Not authorized to cancel this listing")

        listing.status = ListingStatus.CANCELLED
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
        cart.updated_at = datetime.now(timezone.utc)

        return cart

    async def remove_from_cart(self, user_id: str, listing_id: str) -> Cart:
        """Remove a listing from cart."""
        cart = await self.get_cart(user_id)
        cart.items = [item for item in cart.items if item.listing_id != listing_id]
        cart.updated_at = datetime.now(timezone.utc)
        return cart

    async def clear_cart(self, user_id: str) -> Cart:
        """Clear all items from cart."""
        cart = await self.get_cart(user_id)
        cart.items = []
        cart.updated_at = datetime.now(timezone.utc)
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
            purchase.license_expires_at = datetime.now(timezone.utc) + timedelta(
                days=listing.subscription_period_days
            )

        self._purchases[purchase.id] = purchase

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

        # Update listing stats
        listing.purchase_count += 1
        listing.revenue_total += listing.price

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
                if license.expires_at and license.expires_at < datetime.now(timezone.utc):
                    continue
                return license
        return None

    async def record_access(self, license_id: str) -> None:
        """Record an access to a licensed capsule."""
        license = self._licenses.get(license_id)
        if license:
            license.access_count += 1
            license.last_accessed_at = datetime.now(timezone.utc)

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
        now = datetime.now(timezone.utc)
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

        sellers = set(l.seller_id for l in all_listings)
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


# Global instance
_marketplace_service: MarketplaceService | None = None


async def get_marketplace_service() -> MarketplaceService:
    """Get the global marketplace service instance."""
    global _marketplace_service
    if _marketplace_service is None:
        _marketplace_service = MarketplaceService()
    return _marketplace_service
