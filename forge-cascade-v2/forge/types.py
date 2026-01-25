"""
Central Type Definitions for Forge Cascade

This module provides type aliases, TypedDicts, and Protocols for type-safe development.
Use these types throughout the codebase to ensure consistency and enable strict type checking.

SECURITY FIX (Audit 6 - Session 5): Centralized types for full mypy strict compliance.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
    Protocol,
    TypedDict,
    TypeVar,
    runtime_checkable,
)

from pydantic import Field

if TYPE_CHECKING:
    from forge.models.capsule import Capsule


# =============================================================================
# JSON Types
# =============================================================================

# Recursive JSON value type
JsonPrimitive = str | int | float | bool | None
JsonValue = JsonPrimitive | dict[str, "JsonValue"] | list["JsonValue"]
JsonDict = dict[str, JsonValue]
JsonList = list[JsonValue]


# =============================================================================
# Trust & Governance Types
# =============================================================================

# Trust score: 0-100 scale representing user/capsule trustworthiness
TrustScore = Annotated[int, Field(ge=0, le=100)]

# Trust level categories
TrustLevel = Literal["untrusted", "low", "medium", "high", "verified"]

# Governance vote options
VoteChoice = Literal["approve", "reject", "abstain"]

# Proposal status
ProposalStatus = Literal["draft", "active", "passed", "rejected", "executed", "expired"]

# Ghost Council recommendation
CouncilRecommendation = Literal["approve", "reject", "abstain"]

# Risk assessment levels
RiskLevel = Literal["low", "medium", "high", "critical"]


# =============================================================================
# Marketplace Types
# =============================================================================

# Supported currencies
Currency = Literal["FORGE", "USD", "ETH", "USDC"]

# Price as positive decimal
PositiveDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]

# Listing status
ListingStatus = Literal["draft", "active", "sold", "delisted", "expired"]


class SellerStats(TypedDict):
    """Statistics for a seller in the marketplace."""
    seller_id: str
    total_revenue: float
    total_sales: int
    avg_rating: float


class CapsuleSaleStats(TypedDict):
    """Sales statistics for a capsule."""
    capsule_id: str
    total_sales: int
    total_revenue: float
    last_sale_at: str | None


class MarketplaceAnalytics(TypedDict):
    """Analytics data for the marketplace."""
    total_listings: int
    active_listings: int
    total_sales: int
    total_volume: float
    top_sellers: list[SellerStats]
    top_capsules: list[CapsuleSaleStats]


# =============================================================================
# LLM & AI Types
# =============================================================================

class LLMResponse(TypedDict):
    """Response from an LLM provider."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    latency_ms: float


class GhostCouncilOpinion(TypedDict):
    """Opinion from a Ghost Council member."""
    member_id: str
    member_name: str
    recommendation: CouncilRecommendation
    confidence: float
    reasoning: str
    concerns: list[str]


class GhostCouncilResult(TypedDict):
    """Result of a Ghost Council deliberation."""
    recommendation: CouncilRecommendation
    confidence: float
    reasoning: list[str]
    concerns: list[str]
    suggested_amendments: list[str]
    risk_assessment: RiskLevel
    affected_components: list[str]
    individual_opinions: list[GhostCouncilOpinion]
    model: str
    tokens_used: int


class EmbeddingResult(TypedDict):
    """Result of an embedding operation."""
    embedding: list[float]
    model: str
    dimensions: int
    latency_ms: float


# =============================================================================
# Health Check Types
# =============================================================================

# Health status
HealthStatus = Literal["healthy", "degraded", "unhealthy", "unknown"]


class HealthCheckResult(TypedDict):
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    latency_ms: float
    timestamp: str


# Callback signature for async health checks
HealthCheckCallback = Callable[[], Coroutine[object, object, tuple[bool, str]]]


# =============================================================================
# Event & Callback Types
# =============================================================================

# Event handler signature
EventHandler = Callable[[str, JsonDict], Coroutine[object, object, None]]

# Cascade event types
CascadeEventType = Literal[
    "capsule_created",
    "capsule_updated",
    "capsule_deleted",
    "proposal_created",
    "proposal_voted",
    "proposal_executed",
    "trust_changed",
    "overlay_triggered",
]


class CascadeEvent(TypedDict):
    """A cascade event in the event system."""
    event_id: str
    event_type: CascadeEventType
    timestamp: str
    source_id: str
    payload: JsonDict


# =============================================================================
# Repository & Database Types
# =============================================================================

# Generic type variable for repository models
EntityT = TypeVar("EntityT")
CreateSchemaT = TypeVar("CreateSchemaT")
UpdateSchemaT = TypeVar("UpdateSchemaT")

# Neo4j record type (more specific than Any)
Neo4jRecord = Mapping[str, str | int | float | bool | list[str] | None]


# =============================================================================
# Protocol Definitions
# =============================================================================


@runtime_checkable
class CapsuleRepositoryProtocol(Protocol):
    """Protocol for capsule repository implementations."""

    async def get_by_id(self, capsule_id: str) -> Capsule | None:
        """Get a capsule by ID."""
        ...

    async def search_semantic(
        self,
        query: str,
        capsule_types: list[str] | None = None,
        limit: int = 10,
        min_trust_level: float = 0.0,
    ) -> Sequence[Capsule]:
        """Semantic search for capsules."""
        ...


@runtime_checkable
class EventBusProtocol(Protocol):
    """Protocol for event bus implementations."""

    async def publish(self, event_type: str, payload: JsonDict) -> None:
        """Publish an event."""
        ...

    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        ...


@runtime_checkable
class HealthCheckProtocol(Protocol):
    """Protocol for health check implementations."""

    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        ...

    @property
    def name(self) -> str:
        """Name of the health check."""
        ...


# =============================================================================
# Utility Types
# =============================================================================

# Pagination parameters
class PaginationParams(TypedDict, total=False):
    """Standard pagination parameters."""
    limit: int
    offset: int
    cursor: str | None


# Sort direction
SortDirection = Literal["asc", "desc"]

# Time range for queries
class TimeRange(TypedDict):
    """Time range for filtering queries."""
    start: datetime
    end: datetime


# =============================================================================
# API Response Types
# =============================================================================

class APIError(TypedDict):
    """Standard API error response."""
    error: str
    code: str
    details: JsonDict | None


class PaginatedResponse(TypedDict):
    """Standard paginated API response."""
    items: list[JsonDict]
    total: int
    limit: int
    offset: int
    has_more: bool
