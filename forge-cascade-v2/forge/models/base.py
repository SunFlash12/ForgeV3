"""
Base Models and Common Types

Foundation classes for all Forge models including enums,
mixins, and base model configuration.
"""

from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def convert_neo4j_datetime(value: Any) -> datetime:
    """
    Convert Neo4j DateTime to Python datetime.

    SECURITY FIX (Audit 4 - L5): Uses datetime.now(timezone.utc) instead of
    deprecated datetime.utcnow() for proper timezone-aware handling.
    """

    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        # Ensure timezone-aware
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    # Handle Neo4j DateTime object
    if hasattr(value, 'to_native'):
        return value.to_native()
    # Handle string format
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value


class ForgeModel(BaseModel):
    """Base model for all Forge entities with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )


class TimestampMixin(BaseModel):
    """Mixin providing created_at and updated_at fields."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime(cls, v: Any) -> datetime:
        """Convert Neo4j DateTime to Python datetime."""
        return convert_neo4j_datetime(v)


class TrustLevel(IntEnum):
    """
    Trust hierarchy levels for entities in the Forge system.

    Higher values indicate more trust and more capabilities.
    """

    QUARANTINE = 0    # Blocked - no execution allowed
    SANDBOX = 40      # Experimental - limited, heavily monitored
    STANDARD = 60     # Default level - basic operations
    TRUSTED = 80      # Verified, reliable - most operations
    CORE = 100        # System-critical - full access, immune to quarantine

    @classmethod
    def from_value(cls, value: int) -> "TrustLevel":
        """Get the appropriate trust level for a numeric value."""
        for level in sorted(cls, key=lambda x: x.value, reverse=True):
            if value >= level.value:
                return level
        return cls.QUARANTINE

    @property
    def can_execute(self) -> bool:
        """Check if this trust level allows execution."""
        return self.value > TrustLevel.QUARANTINE.value

    @property
    def can_vote(self) -> bool:
        """Check if this trust level allows governance voting."""
        return self.value >= TrustLevel.TRUSTED.value


class CapsuleType(str, Enum):
    """Types of knowledge capsules - matches frontend CapsuleType."""

    # Frontend-compatible types
    INSIGHT = "INSIGHT"        # AI-generated insights
    DECISION = "DECISION"      # Recorded decisions with rationale
    LESSON = "LESSON"          # Learned lessons
    WARNING = "WARNING"        # Warnings and cautions
    PRINCIPLE = "PRINCIPLE"    # Guiding principles
    MEMORY = "MEMORY"          # Institutional memory

    # Additional backend types
    KNOWLEDGE = "KNOWLEDGE"    # General knowledge/information
    CODE = "CODE"              # Code snippets, functions
    CONFIG = "CONFIG"          # Configuration data
    TEMPLATE = "TEMPLATE"      # Reusable templates
    DOCUMENT = "DOCUMENT"      # Full documents


class OverlayState(str, Enum):
    """Lifecycle states for overlays."""

    REGISTERED = "registered"  # Known but not loaded
    LOADING = "loading"        # Currently being loaded
    ACTIVE = "active"          # Running and healthy
    DEGRADED = "degraded"      # Running but with issues
    STOPPING = "stopping"      # Graceful shutdown in progress
    STOPPED = "stopped"        # Stopped but can be restarted
    INACTIVE = "inactive"      # Not active, available for activation
    QUARANTINED = "quarantined"  # Blocked due to failures
    ERROR = "error"            # Fatal error state


class OverlayPhase(str, Enum):
    """Pipeline phases that overlays can participate in."""

    VALIDATION = "validation"      # Input validation
    SECURITY = "security"          # Security checks
    ENRICHMENT = "enrichment"      # Data enrichment
    PROCESSING = "processing"      # Core processing
    GOVERNANCE = "governance"      # Governance checks
    FINALIZATION = "finalization"  # Final processing
    NOTIFICATION = "notification"  # Notifications


class ProposalStatus(str, Enum):
    """Status of governance proposals."""

    DRAFT = "draft"            # Not yet submitted
    ACTIVE = "active"          # Open for discussion
    VOTING = "voting"          # Voting period active
    PASSED = "passed"          # Approved
    REJECTED = "rejected"      # Rejected
    EXECUTED = "executed"      # Implemented
    CANCELLED = "cancelled"    # Withdrawn


class AuditOperation(str, Enum):
    """Types of auditable operations."""

    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    VOTE = "VOTE"
    QUARANTINE = "QUARANTINE"
    RECOVER = "RECOVER"


# ═══════════════════════════════════════════════════════════════
# COMMON RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck(ForgeModel):
    """Health check response."""

    status: HealthStatus
    service: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(ForgeModel):
    """Generic paginated response wrapper."""

    items: list[Any]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class ErrorResponse(ForgeModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None
    correlation_id: str | None = None


class SuccessResponse(ForgeModel):
    """Standard success response."""

    success: bool = True
    message: str = "Operation completed successfully"
    data: dict[str, Any] | None = None


# ═══════════════════════════════════════════════════════════════
# ID GENERATION
# ═══════════════════════════════════════════════════════════════


def generate_id() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


def generate_uuid() -> UUID:
    """Generate a new UUID."""
    return uuid4()
