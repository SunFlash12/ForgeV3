"""
Pydantic Validation Schemas for Forge API

This module provides validated types and utility functions for runtime
type checking at API boundaries. All API inputs should use these types
to ensure data integrity and prevent injection attacks.

SECURITY FIX (Audit 6 - Session 5): Runtime validation for critical paths.

Usage:
    from forge.api.schemas.validation import (
        PositiveDecimal,
        TrustScore,
        MetadataDict,
        BoundedString,
    )

    class MyRequest(BaseModel):
        price: PositiveDecimal
        trust_level: TrustScore
        metadata: MetadataDict
        description: BoundedString
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

# =============================================================================
# Validated Type Aliases
# =============================================================================

# Positive integer (greater than 0)
PositiveInt = Annotated[int, Field(gt=0)]

# Non-negative integer (0 or greater)
NonNegativeInt = Annotated[int, Field(ge=0)]

# Positive decimal (greater than 0)
PositiveDecimal = Annotated[Decimal, Field(gt=Decimal("0"))]

# Non-negative decimal (0 or greater)
NonNegativeDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]

# Trust score: 0-100 scale
TrustScore = Annotated[int, Field(ge=0, le=100)]

# Trust level float: 0.0-1.0 scale
TrustLevel = Annotated[float, Field(ge=0.0, le=1.0)]

# Bounded string with sensible defaults (1-10000 chars)
BoundedString = Annotated[str, StringConstraints(min_length=1, max_length=10000)]

# Short string (1-255 chars) for names, titles
ShortString = Annotated[str, StringConstraints(min_length=1, max_length=255)]

# Medium string (1-2000 chars) for descriptions
MediumString = Annotated[str, StringConstraints(min_length=1, max_length=2000)]

# UUID string (exact format)
UUIDString = Annotated[
    str,
    StringConstraints(
        min_length=36,
        max_length=36,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    ),
]

# Ethereum address
EthereumAddress = Annotated[
    str,
    StringConstraints(
        min_length=42,
        max_length=42,
        pattern=r"^0x[0-9a-fA-F]{40}$",
    ),
]

# Email address (basic validation)
Email = Annotated[
    str,
    StringConstraints(
        min_length=5,
        max_length=255,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    ),
]


# =============================================================================
# JSON Depth Validation
# =============================================================================

MAX_JSON_DEPTH = 10
MAX_ARRAY_LENGTH = 100
MAX_OBJECT_KEYS = 50


def validate_json_depth(
    value: object,
    max_depth: int = MAX_JSON_DEPTH,
    current_depth: int = 0,
) -> bool:
    """
    Validate that a JSON-like structure doesn't exceed maximum depth.

    This prevents deeply nested JSON attacks that could cause stack overflow
    or excessive memory usage during processing.

    Args:
        value: The value to check
        max_depth: Maximum allowed nesting depth
        current_depth: Current recursion depth

    Returns:
        True if valid, raises ValueError if too deep

    Raises:
        ValueError: If the structure exceeds maximum depth
    """
    if current_depth > max_depth:
        raise ValueError(f"JSON structure exceeds maximum depth of {max_depth}")

    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_KEYS:
            raise ValueError(f"Object exceeds maximum keys ({MAX_OBJECT_KEYS})")
        for v in value.values():
            validate_json_depth(v, max_depth, current_depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ARRAY_LENGTH:
            raise ValueError(f"Array exceeds maximum length ({MAX_ARRAY_LENGTH})")
        for item in value:
            validate_json_depth(item, max_depth, current_depth + 1)

    return True


def _check_json_depth(v: dict[str, object]) -> dict[str, object]:
    """Validator function for JSON depth checking."""
    validate_json_depth(v)
    return v


# Metadata dict with depth validation
MetadataDict = Annotated[dict[str, object], AfterValidator(_check_json_depth)]


# =============================================================================
# Validated Base Models
# =============================================================================


class StrictModel(BaseModel):
    """
    Base model with strict validation settings.

    Use this as a base class for API request/response models that need
    strict type enforcement.
    """

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_default=True,
        str_strip_whitespace=True,
    )


class FlexibleModel(BaseModel):
    """
    Base model with flexible validation settings.

    Use this for internal data structures where strict validation
    would be too restrictive.
    """

    model_config = ConfigDict(
        extra="ignore",
        validate_default=True,
        str_strip_whitespace=True,
    )


# =============================================================================
# Common Validated Schemas
# =============================================================================


class PaginationRequest(StrictModel):
    """Standard pagination parameters for API requests."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PaginationResponse(BaseModel):
    """Standard pagination metadata for API responses."""

    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool


class MarketplacePriceInput(StrictModel):
    """Validated price input for marketplace operations."""

    price: PositiveDecimal
    currency: str = Field(pattern=r"^(FORGE|USD|ETH|USDC)$")


class TrustUpdateInput(StrictModel):
    """Validated input for trust level updates."""

    trust_flame: TrustScore
    reason: BoundedString = Field(min_length=10, max_length=500)


class SearchRequest(StrictModel):
    """Validated search request."""

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    filters: MetadataDict | None = None


class IdList(StrictModel):
    """Validated list of IDs for batch operations."""

    ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def validate_ids_not_empty(cls, v: list[str]) -> list[str]:
        """Ensure no empty strings in ID list."""
        for item in v:
            if not item or not item.strip():
                raise ValueError("ID list contains empty values")
        return [item.strip() for item in v]


# =============================================================================
# API Error Response
# =============================================================================


class APIErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = None
    message: str
    code: str | None = None


class APIErrorResponse(BaseModel):
    """Standard API error response format."""

    error: str
    code: str
    details: list[APIErrorDetail] | None = None
    path: str | None = None


# =============================================================================
# Type Variables for Generic Validation
# =============================================================================

T = TypeVar("T")


def validate_list_max_length(
    items: list[T],
    max_length: int = MAX_ARRAY_LENGTH,
) -> list[T]:
    """
    Validate that a list doesn't exceed maximum length.

    Args:
        items: The list to validate
        max_length: Maximum allowed length

    Returns:
        The validated list

    Raises:
        ValueError: If list exceeds maximum length
    """
    if len(items) > max_length:
        raise ValueError(f"List exceeds maximum length of {max_length}")
    return items


def validate_dict_max_keys(
    data: dict[str, T],
    max_keys: int = MAX_OBJECT_KEYS,
) -> dict[str, T]:
    """
    Validate that a dict doesn't exceed maximum keys.

    Args:
        data: The dict to validate
        max_keys: Maximum allowed keys

    Returns:
        The validated dict

    Raises:
        ValueError: If dict exceeds maximum keys
    """
    if len(data) > max_keys:
        raise ValueError(f"Dict exceeds maximum keys of {max_keys}")
    return data
