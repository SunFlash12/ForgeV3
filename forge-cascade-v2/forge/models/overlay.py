"""
Overlay Models

Overlays are intelligent modules providing specialized functionality.
Designed for WebAssembly isolation with capability-based security.
"""

from datetime import datetime
from enum import Enum, auto
from typing import Any

from pydantic import Field

from forge.models.base import (
    ForgeModel,
    TimestampMixin,
    TrustLevel,
    OverlayState,
    OverlayPhase,
)


class Capability(str, Enum):
    """
    Capabilities that overlays can request.
    
    Each capability grants specific permissions to the overlay.
    Follows principle of least privilege.
    """

    NETWORK_ACCESS = "NETWORK_ACCESS"       # Can make HTTP requests
    DATABASE_READ = "DATABASE_READ"         # Can read from Neo4j
    DATABASE_WRITE = "DATABASE_WRITE"       # Can write to Neo4j
    EVENT_PUBLISH = "EVENT_PUBLISH"         # Can publish events
    EVENT_SUBSCRIBE = "EVENT_SUBSCRIBE"     # Can subscribe to events
    CAPSULE_CREATE = "CAPSULE_CREATE"       # Can create capsules
    CAPSULE_READ = "CAPSULE_READ"           # Can read capsules
    CAPSULE_WRITE = "CAPSULE_WRITE"         # Can write/update capsules
    CAPSULE_MODIFY = "CAPSULE_MODIFY"       # Can modify capsules
    CAPSULE_DELETE = "CAPSULE_DELETE"       # Can delete capsules
    GOVERNANCE_VOTE = "GOVERNANCE_VOTE"     # Can vote on proposals
    GOVERNANCE_PROPOSE = "GOVERNANCE_PROPOSE"  # Can create proposals
    GOVERNANCE_EXECUTE = "GOVERNANCE_EXECUTE"  # Can execute passed proposals
    USER_READ = "USER_READ"                 # Can read user data
    SYSTEM_CONFIG = "SYSTEM_CONFIG"         # Can modify system config


# Core overlay capability sets
CORE_OVERLAY_CAPABILITIES = {
    "symbolic_governance": {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
        Capability.GOVERNANCE_VOTE,
        Capability.GOVERNANCE_PROPOSE,
    },
    "security_validator": {
        Capability.DATABASE_READ,
        Capability.EVENT_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
        Capability.USER_READ,
    },
    "ml_intelligence": {
        Capability.DATABASE_READ,
        Capability.EVENT_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
    },
    "performance_optimizer": {
        Capability.DATABASE_READ,
        Capability.EVENT_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
    },
    "capsule_analyzer": {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.CAPSULE_CREATE,
        Capability.CAPSULE_MODIFY,
    },
    "lineage_tracker": {
        Capability.DATABASE_READ,
    },
}


class OverlayMetrics(ForgeModel):
    """Runtime metrics for an overlay."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    last_execution: datetime | None = None
    last_error: str | None = None
    last_error_time: datetime | None = None
    
    # Resource usage
    memory_used_bytes: int = 0
    cpu_cycles_used: int = 0
    
    # Health
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_executions == 0:
            return 1.0
        return self.successful_executions / self.total_executions

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        return 1.0 - self.success_rate


class FuelBudget(ForgeModel):
    """Resource limits for overlay functions."""

    function_name: str
    max_fuel: int = Field(
        default=5_000_000,
        ge=0,
        description="Max CPU cycles/instructions",
    )
    max_memory_bytes: int = Field(
        default=10_485_760,  # 10MB
        ge=0,
        description="Max memory allocation",
    )
    timeout_ms: int = Field(
        default=5000,
        ge=0,
        description="Execution timeout",
    )


class OverlayManifest(ForgeModel):
    """Manifest describing an overlay's configuration and requirements."""

    id: str
    name: str = Field(max_length=100)
    version: str = Field(
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version",
    )
    description: str = Field(default="", max_length=1000)
    
    # Security
    capabilities: set[Capability] = Field(
        default_factory=set,
        description="Required capabilities",
    )
    trust_required: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Minimum trust level to use",
    )
    
    # Dependencies
    dependencies: list[str] = Field(
        default_factory=list,
        description="Required overlay IDs",
    )
    
    # Exports (functions provided)
    exports: list[str] = Field(
        default_factory=list,
        description="Exported function names",
    )
    
    # Resource limits per function
    fuel_budgets: dict[str, FuelBudget] = Field(
        default_factory=dict,
        description="Fuel budget per function",
    )
    
    # Wasm-specific
    wasm_path: str | None = Field(
        default=None,
        description="Path to compiled Wasm binary",
    )
    source_hash: str | None = Field(
        default=None,
        description="SHA256 of source code",
    )


class OverlayBase(ForgeModel):
    """Base overlay fields."""

    name: str = Field(max_length=100)
    description: str = Field(default="", max_length=1000)


class Overlay(OverlayBase, TimestampMixin):
    """Complete overlay schema."""

    id: str
    version: str = Field(default="1.0.0")
    state: OverlayState = Field(default=OverlayState.REGISTERED)
    trust_level: TrustLevel = Field(default=TrustLevel.STANDARD)
    capabilities: set[Capability] = Field(default_factory=set)
    dependencies: list[str] = Field(default_factory=list)
    metrics: OverlayMetrics = Field(default_factory=OverlayMetrics)
    
    # Activation
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    
    # Wasm
    wasm_hash: str | None = None
    
    @property
    def is_active(self) -> bool:
        """Check if overlay is currently active."""
        return self.state == OverlayState.ACTIVE

    @property
    def is_healthy(self) -> bool:
        """Check if overlay is healthy based on metrics."""
        return (
            self.is_active
            and self.metrics.consecutive_failures < 3
            and self.metrics.error_rate < 0.1
        )


class OverlayExecution(ForgeModel):
    """Record of an overlay function execution."""

    overlay_id: str
    function_name: str
    input_payload: dict[str, Any]
    output_result: dict[str, Any] | None = None
    success: bool
    error: str | None = None
    execution_time_ms: float
    fuel_used: int = 0
    memory_used_bytes: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None


class OverlayHealthCheck(ForgeModel):
    """Result of an overlay health check."""

    overlay_id: str
    level: str = Field(description="L1-L4 health check level")
    healthy: bool
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OverlayEvent(ForgeModel):
    """Event published by or to an overlay."""

    source_overlay: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None
    target_overlays: list[str] | None = Field(
        default=None,
        description="Specific targets, or None for broadcast",
    )
