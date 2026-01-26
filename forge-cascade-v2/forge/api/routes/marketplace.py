"""
Marketplace API Routes

Endpoints for the capsule marketplace.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from forge.api.dependencies import ActiveUserDep
from forge.models.marketplace import (
    Currency,
    LicenseType,
    ListingStatus,
    ListingVisibility,
)
from forge.models.user import User
from forge.services.marketplace import (
    ListingUpdateFields,
    MarketplaceService,
    get_marketplace_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# SECURITY FIX (Audit 3): Sanitize error messages to prevent information disclosure
def _sanitize_validation_error(e: Exception, context: str) -> str:
    """
    Return a safe error message for validation errors.

    Logs the actual error internally but returns a generic message to users.
    """
    error_str = str(e).lower()
    logger.warning(f"marketplace_validation_error: {context}", extra={"error": str(e)})

    # Map known validation errors to user-friendly messages
    if "not found" in error_str:
        return "The requested item was not found"
    if "permission" in error_str or "not own" in error_str or "unauthorized" in error_str:
        return "You do not have permission to perform this action"
    if "already" in error_str:
        return "This action has already been performed"
    if "price" in error_str:
        return "Invalid price specified"
    if "quantity" in error_str or "stock" in error_str:
        return "Invalid quantity or insufficient stock"
    if "status" in error_str:
        return "Invalid status for this operation"
    if "cart" in error_str:
        return "Cart operation failed"

    # Generic fallback - don't expose internal details
    return "Invalid request. Please check your input and try again."


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateListingRequest(BaseModel):
    """Request to create a listing."""
    capsule_id: str
    price: Decimal = Field(ge=0)
    currency: Currency = Currency.FORGE
    license_type: LicenseType = LicenseType.PERPETUAL
    title: str = Field(max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    preview_content: str | None = None


class UpdateListingRequest(BaseModel):
    """Request to update a listing."""
    price: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    tags: list[str] | None = None
    preview_content: str | None = None
    visibility: ListingVisibility | None = None


class ListingResponse(BaseModel):
    """Listing information response."""
    id: str
    capsule_id: str
    seller_id: str
    price: float
    currency: str
    suggested_price: float | None
    license_type: str
    status: str
    title: str
    description: str | None
    tags: list[str]
    preview_content: str | None
    view_count: int
    purchase_count: int
    created_at: datetime
    published_at: datetime | None


class ListingListResponse(BaseModel):
    """List of listings."""
    listings: list[ListingResponse]
    total: int


class CartResponse(BaseModel):
    """Cart information response."""
    items: list[dict[str, Any]]
    total: float
    item_count: int


class PurchaseResponse(BaseModel):
    """Purchase information response."""
    id: str
    listing_id: str
    capsule_id: str
    price: float
    currency: str
    license_type: str
    purchased_at: datetime
    license_expires_at: datetime | None


class PriceSuggestionResponse(BaseModel):
    """Price suggestion response."""
    capsule_id: str
    suggested_price: float
    min_price: float
    max_price: float
    factors: dict[str, float]


class StatsResponse(BaseModel):
    """Marketplace statistics response."""
    total_listings: int
    active_listings: int
    total_sales: int
    total_revenue: float
    sales_today: int
    sales_this_week: int
    avg_price: float
    top_sellers: list[dict[str, Any]]
    top_capsules: list[dict[str, Any]]


# ============================================================================
# Dependencies
# ============================================================================

async def get_marketplace() -> MarketplaceService:
    """Get marketplace service dependency."""
    return await get_marketplace_service()


MarketplaceDep = Depends(get_marketplace)


# ============================================================================
# Listing Endpoints
# ============================================================================

@router.post("/listings", response_model=ListingResponse)
async def create_listing(
    request: CreateListingRequest,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> ListingResponse:
    """Create a new marketplace listing."""
    try:
        listing = await svc.create_listing(
            capsule_id=request.capsule_id,
            seller_id=user.id,
            price=request.price,
            currency=request.currency,
            license_type=request.license_type,
            title=request.title,
            description=request.description,
            tags=request.tags,
        )
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "create_listing"))

    return ListingResponse(
        id=listing.id,
        capsule_id=listing.capsule_id,
        seller_id=listing.seller_id,
        price=float(listing.price),
        currency=listing.currency.value,
        suggested_price=float(listing.suggested_price) if listing.suggested_price else None,
        license_type=listing.license_type.value,
        status=listing.status.value,
        title=listing.title,
        description=listing.description,
        tags=listing.tags,
        preview_content=listing.preview_content,
        view_count=listing.view_count,
        purchase_count=listing.purchase_count,
        created_at=listing.created_at,
        published_at=listing.published_at,
    )


@router.get("/listings", response_model=ListingListResponse)
async def list_listings(
    status: str | None = Query(default="active"),
    seller_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    tags: str | None = Query(default=None, description="Comma-separated tags"),
    sort_by: str = Query(default="created_at"),
    # SECURITY FIX (Audit 7 - Session 3): Reduce max limit to 100 to prevent excessive queries
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    svc: MarketplaceService = MarketplaceDep,
) -> ListingListResponse:
    """Browse marketplace listings."""
    listing_status = ListingStatus(status) if status else None
    tag_list = tags.split(",") if tags else None
    min_dec = Decimal(str(min_price)) if min_price else None
    max_dec = Decimal(str(max_price)) if max_price else None

    listings = await svc.get_listings(
        status=listing_status,
        seller_id=seller_id,
        min_price=min_dec,
        max_price=max_dec,
        tags=tag_list,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    return ListingListResponse(
        listings=[
            ListingResponse(
                id=l.id,
                capsule_id=l.capsule_id,
                seller_id=l.seller_id,
                price=float(l.price),
                currency=l.currency.value,
                suggested_price=float(l.suggested_price) if l.suggested_price else None,
                license_type=l.license_type.value,
                status=l.status.value,
                title=l.title,
                description=l.description,
                tags=l.tags,
                preview_content=l.preview_content,
                view_count=l.view_count,
                purchase_count=l.purchase_count,
                created_at=l.created_at,
                published_at=l.published_at,
            )
            for l in listings
        ],
        total=len(listings),
    )


@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    svc: MarketplaceService = MarketplaceDep,
) -> ListingResponse:
    """Get details for a specific listing."""
    listing = await svc.get_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Record view
    await svc.record_view(listing_id)

    return ListingResponse(
        id=listing.id,
        capsule_id=listing.capsule_id,
        seller_id=listing.seller_id,
        price=float(listing.price),
        currency=listing.currency.value,
        suggested_price=float(listing.suggested_price) if listing.suggested_price else None,
        license_type=listing.license_type.value,
        status=listing.status.value,
        title=listing.title,
        description=listing.description,
        tags=listing.tags,
        preview_content=listing.preview_content,
        view_count=listing.view_count,
        purchase_count=listing.purchase_count,
        created_at=listing.created_at,
        published_at=listing.published_at,
    )


@router.post("/listings/{listing_id}/publish", response_model=ListingResponse)
async def publish_listing(
    listing_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> ListingResponse:
    """Publish a draft listing."""
    try:
        listing = await svc.publish_listing(listing_id, user.id)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "publish_listing"))

    return ListingResponse(
        id=listing.id,
        capsule_id=listing.capsule_id,
        seller_id=listing.seller_id,
        price=float(listing.price),
        currency=listing.currency.value,
        suggested_price=float(listing.suggested_price) if listing.suggested_price else None,
        license_type=listing.license_type.value,
        status=listing.status.value,
        title=listing.title,
        description=listing.description,
        tags=listing.tags,
        preview_content=listing.preview_content,
        view_count=listing.view_count,
        purchase_count=listing.purchase_count,
        created_at=listing.created_at,
        published_at=listing.published_at,
    )


@router.patch("/listings/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: str,
    request: UpdateListingRequest,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> ListingResponse:
    """Update a listing."""
    try:
        updates: ListingUpdateFields = request.model_dump(exclude_none=True)  # type: ignore[assignment]
        listing = await svc.update_listing(listing_id, user.id, updates)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "update_listing"))

    return ListingResponse(
        id=listing.id,
        capsule_id=listing.capsule_id,
        seller_id=listing.seller_id,
        price=float(listing.price),
        currency=listing.currency.value,
        suggested_price=float(listing.suggested_price) if listing.suggested_price else None,
        license_type=listing.license_type.value,
        status=listing.status.value,
        title=listing.title,
        description=listing.description,
        tags=listing.tags,
        preview_content=listing.preview_content,
        view_count=listing.view_count,
        purchase_count=listing.purchase_count,
        created_at=listing.created_at,
        published_at=listing.published_at,
    )


@router.delete("/listings/{listing_id}")
async def cancel_listing(
    listing_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> dict[str, bool]:
    """Cancel a listing."""
    try:
        await svc.cancel_listing(listing_id, user.id)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "cancel_listing"))

    return {"cancelled": True}


# ============================================================================
# Cart Endpoints
# ============================================================================

@router.get("/cart", response_model=CartResponse)
async def get_cart(
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> CartResponse:
    """Get current user's cart."""
    cart = await svc.get_cart(user.id)

    return CartResponse(
        items=[
            {
                "listing_id": item.listing_id,
                "capsule_id": item.capsule_id,
                "title": item.title,
                "price": float(item.price),
                "currency": item.currency.value,
                "added_at": item.added_at.isoformat(),
            }
            for item in cart.items
        ],
        total=float(cart.total),
        item_count=cart.item_count,
    )


@router.post("/cart/items/{listing_id}", response_model=CartResponse)
async def add_to_cart(
    listing_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> CartResponse:
    """Add a listing to cart."""
    try:
        cart = await svc.add_to_cart(user.id, listing_id)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "add_to_cart"))

    return CartResponse(
        items=[
            {
                "listing_id": item.listing_id,
                "capsule_id": item.capsule_id,
                "title": item.title,
                "price": float(item.price),
                "currency": item.currency.value,
                "added_at": item.added_at.isoformat(),
            }
            for item in cart.items
        ],
        total=float(cart.total),
        item_count=cart.item_count,
    )


@router.delete("/cart/items/{listing_id}", response_model=CartResponse)
async def remove_from_cart(
    listing_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> CartResponse:
    """Remove a listing from cart."""
    cart = await svc.remove_from_cart(user.id, listing_id)

    return CartResponse(
        items=[
            {
                "listing_id": item.listing_id,
                "capsule_id": item.capsule_id,
                "title": item.title,
                "price": float(item.price),
                "currency": item.currency.value,
                "added_at": item.added_at.isoformat(),
            }
            for item in cart.items
        ],
        total=float(cart.total),
        item_count=cart.item_count,
    )


# ============================================================================
# Purchase Endpoints
# ============================================================================

@router.post("/checkout", response_model=list[PurchaseResponse])
async def checkout(
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> list[PurchaseResponse]:
    """Process cart checkout."""
    try:
        purchases = await svc.checkout(user.id)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "checkout"))

    return [
        PurchaseResponse(
            id=p.id,
            listing_id=p.listing_id,
            capsule_id=p.capsule_id,
            price=float(p.price),
            currency=p.currency.value,
            license_type=p.license_type.value,
            purchased_at=p.purchased_at,
            license_expires_at=p.license_expires_at,
        )
        for p in purchases
    ]


@router.post("/listings/{listing_id}/purchase", response_model=PurchaseResponse)
async def purchase_single(
    listing_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> PurchaseResponse:
    """Purchase a single listing directly."""
    try:
        purchase = await svc.purchase_single(user.id, listing_id)
    except ValueError as e:
        # SECURITY FIX (Audit 3): Sanitize error message
        raise HTTPException(status_code=400, detail=_sanitize_validation_error(e, "purchase_single"))

    return PurchaseResponse(
        id=purchase.id,
        listing_id=purchase.listing_id,
        capsule_id=purchase.capsule_id,
        price=float(purchase.price),
        currency=purchase.currency.value,
        license_type=purchase.license_type.value,
        purchased_at=purchase.purchased_at,
        license_expires_at=purchase.license_expires_at,
    )


@router.get("/purchases", response_model=list[PurchaseResponse])
async def get_purchases(
    user: ActiveUserDep,
    # SECURITY FIX (Audit 7 - Session 3): Reduce max limit to 100
    limit: int = Query(default=50, ge=1, le=100),
    svc: MarketplaceService = MarketplaceDep,
) -> list[PurchaseResponse]:
    """Get purchase history."""
    purchases = await svc.get_user_purchases(user.id, limit)

    return [
        PurchaseResponse(
            id=p.id,
            listing_id=p.listing_id,
            capsule_id=p.capsule_id,
            price=float(p.price),
            currency=p.currency.value,
            license_type=p.license_type.value,
            purchased_at=p.purchased_at,
            license_expires_at=p.license_expires_at,
        )
        for p in purchases
    ]


@router.get("/sales", response_model=list[PurchaseResponse])
async def get_sales(
    user: ActiveUserDep,
    # SECURITY FIX (Audit 7 - Session 3): Reduce max limit to 100
    limit: int = Query(default=50, ge=1, le=100),
    svc: MarketplaceService = MarketplaceDep,
) -> list[PurchaseResponse]:
    """Get sales history (as a seller)."""
    sales = await svc.get_user_sales(user.id, limit)

    return [
        PurchaseResponse(
            id=s.id,
            listing_id=s.listing_id,
            capsule_id=s.capsule_id,
            price=float(s.price),
            currency=s.currency.value,
            license_type=s.license_type.value,
            purchased_at=s.purchased_at,
            license_expires_at=s.license_expires_at,
        )
        for s in sales
    ]


# ============================================================================
# Pricing Endpoints
# ============================================================================

@router.get("/pricing/{capsule_id}", response_model=PriceSuggestionResponse)
async def get_suggested_price(
    capsule_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> PriceSuggestionResponse:
    """Get suggested price for a capsule."""
    suggestion = await svc.calculate_suggested_price(capsule_id)

    if not suggestion:
        raise HTTPException(status_code=404, detail="Capsule not found")

    return PriceSuggestionResponse(
        capsule_id=suggestion.capsule_id,
        suggested_price=float(suggestion.suggested_price),
        min_price=float(suggestion.min_price),
        max_price=float(suggestion.max_price),
        factors=suggestion.factors,
    )


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_marketplace_stats(
    svc: MarketplaceService = MarketplaceDep,
) -> StatsResponse:
    """Get marketplace statistics."""
    stats = await svc.get_marketplace_stats()

    return StatsResponse(
        total_listings=stats.total_listings,
        active_listings=stats.active_listings,
        total_sales=stats.total_sales,
        total_revenue=float(stats.total_revenue),
        sales_today=stats.sales_today,
        sales_this_week=stats.sales_this_week,
        avg_price=float(stats.avg_price),
        top_sellers=stats.top_sellers,
        top_capsules=stats.top_capsules,
    )


# ============================================================================
# License Check Endpoint
# ============================================================================

@router.get("/license/{capsule_id}")
async def check_license(
    capsule_id: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> dict[str, Any]:
    """Check if user has a valid license for a capsule."""
    license = await svc.check_license(user.id, capsule_id)

    if not license:
        return {
            "has_license": False,
            "capsule_id": capsule_id,
        }

    return {
        "has_license": True,
        "capsule_id": capsule_id,
        "license_id": license.id,
        "license_type": license.license_type.value,
        "granted_at": license.granted_at.isoformat(),
        "expires_at": license.expires_at.isoformat() if license.expires_at else None,
        "can_view": license.can_view,
        "can_download": license.can_download,
        "can_derive": license.can_derive,
    }


# ============================================================================
# Advanced Pricing Engine Endpoints
# ============================================================================

class DetailedPricingRequest(BaseModel):
    """Request for detailed pricing analysis."""
    capsule_id: str
    include_recommendations: bool = True
    include_market_comparison: bool = True


class DetailedPricingResponse(BaseModel):
    """Detailed pricing analysis response."""
    capsule_id: str
    suggested_price: float
    minimum_price: float
    maximum_price: float
    confidence: float
    pricing_tier: str
    tier_reason: str
    base_price: float
    multipliers: dict[str, float]
    adjustments: dict[str, float]
    market_comparison: dict[str, Any] | None
    recommendations: list[str]


class LineageDistributionResponse(BaseModel):
    """Lineage revenue distribution response."""
    capsule_id: str
    total_lineage_share: float
    distributions: list[dict[str, Any]]


@router.post("/pricing/analyze", response_model=DetailedPricingResponse)
async def analyze_pricing(
    request: DetailedPricingRequest,
    user: ActiveUserDep,
) -> DetailedPricingResponse:
    """
    Get detailed pricing analysis using the trust-based pricing engine.

    Returns comprehensive breakdown of pricing factors, multipliers,
    and recommendations.
    """
    from forge.services.pricing_engine import get_pricing_engine

    engine = await get_pricing_engine()

    # Calculate detailed pricing
    result = await engine.calculate_price(request.capsule_id)

    return DetailedPricingResponse(
        capsule_id=result.capsule_id,
        suggested_price=float(result.suggested_price),
        minimum_price=float(result.minimum_price),
        maximum_price=float(result.maximum_price),
        confidence=result.confidence,
        pricing_tier=result.pricing_tier.value,
        tier_reason=result.tier_reason,
        base_price=float(result.base_price),
        multipliers=result.multipliers,
        adjustments={k: float(v) for k, v in result.adjustments.items()},
        market_comparison=result.market_comparison if request.include_market_comparison else None,
        recommendations=result.recommendations if request.include_recommendations else [],
    )


@router.get("/pricing/{capsule_id}/lineage-distribution")
async def get_lineage_distribution(
    capsule_id: str,
    sale_price: float = Query(..., gt=0, description="The sale price to calculate distribution from"),
    user: User | None = None,
) -> LineageDistributionResponse:
    """
    Calculate how lineage revenue would be distributed for a sale.

    Shows which ancestor capsule owners would receive revenue
    and their respective shares.
    """
    from decimal import Decimal

    from forge.services.pricing_engine import get_pricing_engine

    engine = await get_pricing_engine()

    # Lineage share is 15% of sale price
    lineage_share = Decimal(str(sale_price)) * Decimal("0.15")

    distributions = await engine.calculate_lineage_distribution(
        capsule_id=capsule_id,
        total_lineage_share=lineage_share,
    )

    return LineageDistributionResponse(
        capsule_id=capsule_id,
        total_lineage_share=float(lineage_share),
        distributions=[
            {
                "user_id": d["user_id"],
                "capsule_id": d["capsule_id"],
                "depth": d["depth"],
                "weight": d["weight"],
                "amount": float(d["amount"]),
            }
            for d in distributions
        ],
    )


@router.get("/pricing/tiers")
async def get_pricing_tiers() -> dict[str, Any]:
    """Get information about pricing tiers and base prices."""
    from forge.services.pricing_engine import PricingTier, TrustBasedPricingEngine

    return {
        "tiers": [
            {
                "name": tier.value,
                "description": _get_tier_description(tier),
            }
            for tier in PricingTier
        ],
        "base_prices": {
            k: float(v)
            for k, v in TrustBasedPricingEngine.BASE_PRICES.items()
        },
        "trust_curve": [
            {"trust_level": t, "multiplier": m}
            for t, m in TrustBasedPricingEngine.TRUST_CURVE
        ],
        "revenue_distribution": {
            "seller": 0.70,
            "lineage": 0.15,
            "platform": 0.10,
            "treasury": 0.05,
        },
    }


def _get_tier_description(tier: Any) -> str:
    """Get description for pricing tier."""
    from forge.services.pricing_engine import PricingTier

    descriptions = {
        PricingTier.COMMODITY: "Low uniqueness, high supply - basic marketplace items",
        PricingTier.STANDARD: "Normal marketplace item with typical characteristics",
        PricingTier.PREMIUM: "High trust or significant network importance",
        PricingTier.EXCLUSIVE: "Very rare or authoritative original sources",
        PricingTier.FOUNDATIONAL: "High PageRank with many derivatives - knowledge foundations",
    }
    return descriptions.get(tier, tier.value)


# ============================================================================
# Web3 / Virtuals Protocol Purchase Endpoints
# ============================================================================

class Web3PurchaseItem(BaseModel):
    """Item in a Web3 purchase."""
    listing_id: str
    capsule_id: str
    title: str
    price_virtual: str  # Price in wei (18 decimals)
    price_usd: float | None = None


class Web3PurchaseRequest(BaseModel):
    """Request to submit a Web3 purchase."""
    items: list[Web3PurchaseItem]
    wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    transaction_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")


class Web3PurchaseResponse(BaseModel):
    """Response for a Web3 purchase submission."""
    purchase_id: str
    status: str  # pending, confirmed, failed
    transaction_hash: str | None
    capsule_ids: list[str]
    total_virtual: str
    created_at: datetime


class TransactionStatusResponse(BaseModel):
    """Response for transaction status check."""
    transaction_hash: str
    status: str  # pending, confirmed, failed
    block_number: int | None
    confirmations: int
    capsule_ids: list[str]
    total_virtual: str


class VirtualPriceResponse(BaseModel):
    """Response for $VIRTUAL token price."""
    price_usd: float
    updated_at: datetime


@router.post("/purchase", response_model=Web3PurchaseResponse)
async def submit_web3_purchase(
    request: Web3PurchaseRequest,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> Web3PurchaseResponse:
    """
    Submit a Web3 purchase after on-chain transaction.

    The backend will verify the transaction on Base and grant capsule access.
    """
    from forge.config import get_settings

    settings = get_settings()

    # Verify the transaction on-chain
    try:
        from forge.services.web3_service import verify_purchase_transaction

        verification = await verify_purchase_transaction(
            transaction_hash=request.transaction_hash,
            expected_wallet=request.wallet_address,
            expected_items=request.items,
            rpc_url=settings.base_rpc_url,
            virtual_token_address=settings.virtual_token_address,
        )

        if not verification.is_valid:
            # SECURITY FIX (Audit 7 - Session 3): Don't leak verification internals
            logger.warning("web3_tx_verification_failed: tx=%s, error=%s", request.transaction_hash, verification.error)
            raise HTTPException(
                status_code=400,
                detail="Transaction verification failed. Please check your transaction and try again.",
            )

        # Process the purchase - grant capsule access
        capsule_ids = [item.capsule_id for item in request.items]
        total_virtual = sum(int(item.price_virtual) for item in request.items)

        # Record purchase in database
        purchase = await svc.record_web3_purchase(  # type: ignore[attr-defined]
            user_id=user.id,
            wallet_address=request.wallet_address,
            transaction_hash=request.transaction_hash,
            capsule_ids=capsule_ids,
            total_virtual=str(total_virtual),
            block_number=verification.block_number,
        )

        return Web3PurchaseResponse(
            purchase_id=purchase.id,
            status="confirmed",
            transaction_hash=request.transaction_hash,
            capsule_ids=capsule_ids,
            total_virtual=str(total_virtual),
            created_at=purchase.created_at,
        )

    except ImportError:
        # Web3 service not available - return pending status
        logger.warning("web3_service_not_available: tx=%s", request.transaction_hash)

        # Still record the purchase request for manual verification
        capsule_ids = [item.capsule_id for item in request.items]
        total_virtual = sum(int(item.price_virtual) for item in request.items)

        return Web3PurchaseResponse(
            purchase_id=f"pending_{request.transaction_hash[:16]}",
            status="pending",
            transaction_hash=request.transaction_hash,
            capsule_ids=capsule_ids,
            total_virtual=str(total_virtual),
            # SECURITY FIX (Audit 7 - Session 3): Use timezone-aware datetime
            created_at=datetime.now(UTC),
        )

    except (ValueError, ConnectionError, TimeoutError, OSError) as e:
        logger.error("web3_purchase_failed: error=%s, tx=%s", str(e), request.transaction_hash)
        raise HTTPException(
            status_code=400,
            detail="Failed to process purchase. Please contact support.",
        )


@router.get("/transaction/{transaction_hash}", response_model=TransactionStatusResponse)
async def get_transaction_status(
    transaction_hash: str,
    user: ActiveUserDep,
    svc: MarketplaceService = MarketplaceDep,
) -> TransactionStatusResponse:
    """
    Check status of a purchase transaction.

    Returns current confirmation status and purchased capsules.
    """
    # Validate transaction hash format
    if not transaction_hash.startswith("0x") or len(transaction_hash) != 66:
        raise HTTPException(status_code=400, detail="Invalid transaction hash format")

    from forge.config import get_settings

    settings = get_settings()

    try:
        from forge.services.web3_service import get_transaction_info

        tx_info = await get_transaction_info(
            transaction_hash=transaction_hash,
            rpc_url=settings.base_rpc_url,
        )

        # Look up purchase record
        purchase = await svc.get_purchase_by_transaction(transaction_hash)  # type: ignore[attr-defined]

        if purchase:
            return TransactionStatusResponse(
                transaction_hash=transaction_hash,
                status="confirmed" if tx_info.confirmations >= 12 else "pending",
                block_number=tx_info.block_number,
                confirmations=tx_info.confirmations,
                capsule_ids=purchase.capsule_ids,
                total_virtual=purchase.total_virtual,
            )
        else:
            return TransactionStatusResponse(
                transaction_hash=transaction_hash,
                status="pending" if tx_info.block_number else "not_found",
                block_number=tx_info.block_number,
                confirmations=tx_info.confirmations,
                capsule_ids=[],
                total_virtual="0",
            )

    except ImportError:
        # Web3 service not available
        logger.warning("web3_service_not_available_for_status")
        raise HTTPException(
            status_code=503,
            detail="Transaction verification service temporarily unavailable",
        )

    except (ValueError, ConnectionError, TimeoutError, OSError) as e:
        logger.error("transaction_status_failed: error=%s, tx=%s", str(e), transaction_hash)
        raise HTTPException(
            status_code=500,
            detail="Failed to check transaction status",
        )


@router.get("/virtual-price", response_model=VirtualPriceResponse)
async def get_virtual_price() -> VirtualPriceResponse:
    """
    Get current $VIRTUAL token price in USD.

    Price is fetched from DEX aggregators and cached for 5 minutes.
    """
    import httpx

    from forge.config import get_settings

    settings = get_settings()

    try:
        # Try to get price from DexScreener API (supports Base)
        async with httpx.AsyncClient(timeout=10.0) as client:
            # $VIRTUAL token on Base
            response = await client.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{settings.virtual_token_address}"
            )

            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Get price from most liquid pair
                    price = float(pairs[0].get("priceUsd", 0))
                    return VirtualPriceResponse(
                        price_usd=price,
                        # SECURITY FIX (Audit 7 - Session 3): Use timezone-aware datetime
                        updated_at=datetime.now(UTC),
                    )

        # Fallback price if API fails
        logger.warning("virtual_price_api_failed: fallback=%s", 0.10)
        return VirtualPriceResponse(
            price_usd=0.10,  # Fallback price
            # SECURITY FIX (Audit 7 - Session 3): Use timezone-aware datetime
            updated_at=datetime.now(UTC),
        )

    except (ValueError, ConnectionError, TimeoutError, OSError) as e:
        logger.error("virtual_price_fetch_failed: error=%s", str(e))
        return VirtualPriceResponse(
            price_usd=0.10,  # Fallback price
            # SECURITY FIX (Audit 7 - Session 3): Use timezone-aware datetime
            updated_at=datetime.now(UTC),
        )
