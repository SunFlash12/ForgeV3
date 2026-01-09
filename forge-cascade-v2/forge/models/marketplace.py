"""
Marketplace Models

Data structures for the knowledge capsule marketplace.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import Field
from forge.models.base import ForgeModel, generate_id


class ListingStatus(str, Enum):
    """Status of a marketplace listing."""
    DRAFT = "draft"
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class LicenseType(str, Enum):
    """Types of licenses for capsule access."""
    PERPETUAL = "perpetual"       # One-time purchase, forever access
    SUBSCRIPTION = "subscription"  # Recurring payment
    USAGE = "usage"               # Pay per use
    DERIVATIVE = "derivative"     # Can create derived works


class Currency(str, Enum):
    """Supported currencies."""
    FORGE = "FORGE"   # Platform token
    USD = "USD"
    SOL = "SOL"       # Solana
    ETH = "ETH"       # Ethereum


class ListingVisibility(str, Enum):
    """Visibility options for listings."""
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


class PaymentMethod(str, Enum):
    """Supported payment methods."""
    PLATFORM = "platform"
    BLOCKCHAIN = "blockchain"


class PaymentStatus(str, Enum):
    """Status of a payment transaction."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class CapsuleListing(ForgeModel):
    """
    A capsule listed for sale in the marketplace.
    """

    id: str = Field(default_factory=generate_id)
    capsule_id: str = Field(description="ID of the capsule being sold")
    seller_id: str = Field(description="User ID of the seller")

    # Pricing
    price: Decimal = Field(ge=0, description="Listing price")
    currency: Currency = Field(default=Currency.FORGE)
    suggested_price: Decimal | None = Field(
        default=None,
        description="System-suggested price based on trust metrics"
    )

    # License
    license_type: LicenseType = Field(default=LicenseType.PERPETUAL)
    license_terms: str | None = Field(
        default=None,
        description="Custom license terms"
    )

    # Subscription details (if applicable)
    subscription_period_days: int | None = None
    subscription_renewal_price: Decimal | None = None

    # Status
    status: ListingStatus = Field(default=ListingStatus.DRAFT)

    # Visibility
    featured: bool = Field(default=False)
    visibility: ListingVisibility = Field(default=ListingVisibility.PUBLIC)

    # Metadata
    title: str = Field(max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    preview_content: str | None = Field(
        default=None,
        description="Public preview of capsule content"
    )

    # Stats
    view_count: int = Field(default=0)
    purchase_count: int = Field(default=0)
    revenue_total: Decimal = Field(default=Decimal("0"))

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


class Purchase(ForgeModel):
    """
    Record of a marketplace purchase.
    """

    id: str = Field(default_factory=generate_id)
    listing_id: str
    capsule_id: str
    buyer_id: str
    seller_id: str

    # Transaction
    price: Decimal
    currency: Currency
    license_type: LicenseType

    # License details
    license_id: str = Field(default_factory=generate_id)
    license_expires_at: datetime | None = None

    # Payment
    payment_method: PaymentMethod = Field(default=PaymentMethod.PLATFORM)
    transaction_hash: str | None = None
    payment_status: PaymentStatus = Field(default=PaymentStatus.COMPLETED)

    # Revenue distribution
    seller_revenue: Decimal = Field(default=Decimal("0"))
    platform_fee: Decimal = Field(default=Decimal("0"))
    lineage_revenue: Decimal = Field(default=Decimal("0"))
    treasury_contribution: Decimal = Field(default=Decimal("0"))

    # Metadata
    purchased_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    refunded_at: datetime | None = None
    notes: str | None = None


class Cart(ForgeModel):
    """
    User's shopping cart.
    """

    id: str = Field(default_factory=generate_id)
    user_id: str
    items: list["CartItem"] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total(self) -> Decimal:
        """Calculate cart total."""
        return sum(item.price for item in self.items)

    @property
    def item_count(self) -> int:
        """Count of items in cart."""
        return len(self.items)


class CartItem(ForgeModel):
    """
    An item in a shopping cart.
    """

    id: str = Field(default_factory=generate_id)
    listing_id: str
    capsule_id: str
    price: Decimal
    currency: Currency
    title: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class License(ForgeModel):
    """
    A license granting access to a capsule.
    """

    id: str = Field(default_factory=generate_id)
    purchase_id: str
    capsule_id: str
    holder_id: str
    grantor_id: str

    license_type: LicenseType
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    # Permissions
    can_view: bool = Field(default=True)
    can_download: bool = Field(default=True)
    can_derive: bool = Field(default=False)
    can_resell: bool = Field(default=False)

    # Usage tracking
    access_count: int = Field(default=0)
    last_accessed_at: datetime | None = None


class PriceSuggestion(ForgeModel):
    """
    System-generated price suggestion for a capsule.
    """

    id: str = Field(default_factory=generate_id)
    capsule_id: str
    suggested_price: Decimal
    min_price: Decimal
    max_price: Decimal
    currency: Currency = Field(default=Currency.FORGE)

    # Factors
    factors: dict[str, float] = Field(default_factory=dict)
    trust_multiplier: float = Field(default=1.0)
    demand_multiplier: float = Field(default=1.0)
    rarity_multiplier: float = Field(default=1.0)

    # Context
    pagerank_score: float = Field(default=0.0)
    citation_count: int = Field(default=0)
    view_count: int = Field(default=0)

    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevenueDistribution(ForgeModel):
    """
    How revenue from a sale is distributed.
    """

    id: str = Field(default_factory=generate_id)
    purchase_id: str
    total_amount: Decimal
    currency: Currency

    # Distribution
    seller_share: Decimal = Field(description="70% to seller")
    lineage_share: Decimal = Field(description="15% to lineage contributors")
    platform_share: Decimal = Field(description="10% to platform")
    treasury_share: Decimal = Field(description="5% to community treasury")

    # Lineage breakdown
    lineage_recipients: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{user_id, amount, contribution_weight}]"
    )

    distributed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketplaceStats(ForgeModel):
    """
    Overall marketplace statistics.
    """

    total_listings: int = 0
    active_listings: int = 0
    total_sales: int = 0
    total_revenue: Decimal = Decimal("0")

    # By period
    sales_today: int = 0
    sales_this_week: int = 0
    sales_this_month: int = 0
    revenue_today: Decimal = Decimal("0")
    revenue_this_week: Decimal = Decimal("0")
    revenue_this_month: Decimal = Decimal("0")

    # Top items
    top_sellers: list[dict[str, Any]] = Field(default_factory=list)
    top_capsules: list[dict[str, Any]] = Field(default_factory=list)
    trending_tags: list[str] = Field(default_factory=list)

    # Averages
    avg_price: Decimal = Decimal("0")
    avg_capsules_per_seller: float = 0.0

    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
