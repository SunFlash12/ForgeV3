"""
Base Overlay for Forge Cascade V2

Abstract base class for all overlay implementations.
Overlays are modular processing units that can be dynamically
loaded, configured, and executed within the Forge kernel.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import structlog

from ..models.base import TrustLevel
from ..models.events import Event, EventType
from ..models.overlay import (
    Capability,
    FuelBudget,
    Overlay,
    OverlayExecution,
    OverlayHealthCheck,
    OverlayManifest,
    OverlayState,
)

logger = structlog.get_logger()


@dataclass
class OverlayContext:
    """
    Context provided to overlays during execution.

    Contains everything an overlay needs to do its work without
    direct access to system internals.
    """
    # Identity
    overlay_id: str
    overlay_name: str

    # Execution context
    execution_id: str
    triggered_by: str  # Event ID or "manual"
    correlation_id: str

    # User context (if applicable)
    user_id: str | None = None
    trust_flame: int = 60

    # Resource context
    capsule_id: str | None = None
    proposal_id: str | None = None

    # Capabilities granted
    capabilities: set[Capability] = field(default_factory=set)

    # Resource limits
    fuel_budget: FuelBudget | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)

    def has_capability(self, cap: Capability) -> bool:
        """Check if context has a capability."""
        return cap in self.capabilities

    def require_capability(self, cap: Capability) -> None:
        """Raise error if capability is missing."""
        if not self.has_capability(cap):
            raise CapabilityError(f"Missing required capability: {cap.value}")


@dataclass
class OverlayResult:
    """Result returned from overlay execution."""
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    events_to_emit: list[dict] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @classmethod
    def ok(cls, data: dict[str, Any] | None = None, **kwargs) -> "OverlayResult":
        """Create a successful result."""
        return cls(success=True, data=data, **kwargs)

    @classmethod
    def fail(cls, error: str, **kwargs) -> "OverlayResult":
        """Create a failed result."""
        return cls(success=False, error=error, **kwargs)


class OverlayError(Exception):
    """Base exception for overlay errors."""
    pass


class CapabilityError(OverlayError):
    """Missing required capability."""
    pass


class ResourceLimitError(OverlayError):
    """Resource limit exceeded."""
    pass


class OverlayTimeoutError(OverlayError):
    """Overlay execution timed out."""
    pass


class BaseOverlay(ABC):
    """
    Abstract base class for Forge overlays.

    Overlays are self-contained processing modules that:
    - Subscribe to specific events
    - Process data within resource constraints
    - Emit events to trigger cascades
    - Report health status

    Lifecycle:
    1. initialize() - Called once when overlay is loaded
    2. execute() - Called for each triggering event
    3. cleanup() - Called when overlay is unloaded
    """

    # Override these in subclasses
    NAME: str = "base_overlay"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Base overlay implementation"

    # Events this overlay listens to
    SUBSCRIBED_EVENTS: set[EventType] = set()

    # Required capabilities
    REQUIRED_CAPABILITIES: set[Capability] = set()

    # Default fuel budget
    DEFAULT_FUEL_BUDGET = FuelBudget(
        function_name="overlay_execution",
        max_fuel=1_000_000,
        max_memory_bytes=10 * 1024 * 1024,  # 10 MB
        timeout_ms=5000  # 5 seconds
    )

    # Minimum trust level to use this overlay
    MIN_TRUST_LEVEL: TrustLevel = TrustLevel.STANDARD

    def __init__(self):
        self.id = str(uuid4())
        self.state = OverlayState.REGISTERED
        self.execution_count = 0
        self.error_count = 0
        self.last_execution: datetime | None = None
        self.last_error: str | None = None
        self._initialized = False
        self._logger = logger.bind(overlay_name=self.NAME, overlay_id=self.id)
        self.config: dict[str, Any] = {}  # Runtime configuration

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    async def initialize(self) -> bool:
        """
        Initialize the overlay.

        Override this to perform setup tasks like:
        - Loading models
        - Establishing connections
        - Pre-computing data

        Returns:
            True if initialization successful
        """
        self._initialized = True
        self.state = OverlayState.ACTIVE
        self._logger.info("overlay_initialized")
        return True

    async def cleanup(self) -> None:
        """
        Clean up overlay resources.

        Override this to:
        - Close connections
        - Release resources
        - Persist state if needed
        """
        self.state = OverlayState.INACTIVE
        self._initialized = False
        self._logger.info("overlay_cleanup")

    @abstractmethod
    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute the overlay's main logic.

        Args:
            context: Execution context with capabilities and limits
            event: Triggering event (if event-driven)
            input_data: Direct input (if manually invoked)

        Returns:
            OverlayResult with success/failure and data
        """
        pass

    # =========================================================================
    # Execution Wrapper
    # =========================================================================

    async def run(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Run the overlay with resource tracking and error handling.

        This wraps execute() with:
        - Timeout enforcement
        - Error handling
        - Metrics collection
        - State management
        """
        if not self._initialized:
            return OverlayResult.fail("Overlay not initialized")

        if self.state != OverlayState.ACTIVE:
            return OverlayResult.fail(f"Overlay in {self.state.value} state")

        # Check capabilities
        missing = self.REQUIRED_CAPABILITIES - context.capabilities
        if missing:
            return OverlayResult.fail(
                f"Missing capabilities: {[c.value for c in missing]}"
            )

        # Get timeout
        timeout_ms = self.DEFAULT_FUEL_BUDGET.timeout_ms
        if context.fuel_budget:
            timeout_ms = context.fuel_budget.timeout_ms

        start_time = asyncio.get_running_loop().time()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.execute(context, event, input_data),
                timeout=timeout_ms / 1000.0
            )

            # Record metrics
            duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000
            result.duration_ms = duration_ms

            self.execution_count += 1
            self.last_execution = datetime.utcnow()

            self._logger.info(
                "overlay_execution_complete",
                execution_id=context.execution_id,
                success=result.success,
                duration_ms=round(duration_ms, 2)
            )

            return result

        except TimeoutError:
            self.error_count += 1
            self.last_error = f"Timeout after {timeout_ms}ms"
            self._logger.error(
                "overlay_timeout",
                execution_id=context.execution_id,
                timeout_ms=timeout_ms
            )
            return OverlayResult.fail(self.last_error)

        except CapabilityError as e:
            self.error_count += 1
            self.last_error = str(e)
            self._logger.error(
                "overlay_capability_error",
                execution_id=context.execution_id,
                error=str(e)
            )
            return OverlayResult.fail(str(e))

        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            self._logger.error(
                "overlay_error",
                execution_id=context.execution_id,
                error=str(e),
                exc_info=True
            )
            return OverlayResult.fail(f"Overlay error: {str(e)}")

    # =========================================================================
    # Health & Status
    # =========================================================================

    async def health_check(self) -> OverlayHealthCheck:
        """
        Perform a health check.

        Override this to add custom health checks.

        Returns:
            OverlayHealthCheck with status information
        """
        healthy = self._initialized and self.state == OverlayState.ACTIVE

        # Calculate error rate
        total = self.execution_count + self.error_count
        error_rate = self.error_count / total if total > 0 else 0.0

        return OverlayHealthCheck(
            overlay_id=self.id,
            overlay_name=self.NAME,
            healthy=healthy,
            state=self.state,
            execution_count=self.execution_count,
            error_count=self.error_count,
            error_rate=error_rate,
            last_execution=self.last_execution,
            last_error=self.last_error,
            checked_at=datetime.utcnow()
        )

    def get_manifest(self) -> OverlayManifest:
        """Get the overlay manifest describing capabilities and requirements."""
        return OverlayManifest(
            name=self.NAME,
            version=self.VERSION,
            description=self.DESCRIPTION,
            subscribed_events=[et.value for et in self.SUBSCRIBED_EVENTS],
            required_capabilities=[c.value for c in self.REQUIRED_CAPABILITIES],
            fuel_budget=self.DEFAULT_FUEL_BUDGET,
            min_trust_level=self.MIN_TRUST_LEVEL.value
        )

    def to_model(self) -> Overlay:
        """Convert to Overlay model."""
        return Overlay(
            id=self.id,
            name=self.NAME,
            version=self.VERSION,
            description=self.DESCRIPTION,
            state=self.state,
            manifest=self.get_manifest()
        )

    # =========================================================================
    # Event Helpers
    # =========================================================================

    def should_handle(self, event: Event) -> bool:
        """Check if this overlay should handle an event."""
        return event.event_type in self.SUBSCRIBED_EVENTS

    def create_event_emission(
        self,
        event_type: EventType,
        payload: dict[str, Any]
    ) -> dict:
        """
        Create an event emission for the result.

        Events created here will be emitted after execution completes.
        """
        return {
            "event_type": event_type.value,
            "payload": payload,
            "source": f"overlay:{self.NAME}"
        }

    # =========================================================================
    # Context Helpers
    # =========================================================================

    def create_context(
        self,
        triggered_by: str = "manual",
        user_id: str | None = None,
        trust_flame: int = 60,
        capabilities: set[Capability] | None = None,
        fuel_budget: FuelBudget | None = None,
        **metadata
    ) -> OverlayContext:
        """
        Create an execution context.

        Useful for manual invocation.
        """
        return OverlayContext(
            overlay_id=self.id,
            overlay_name=self.NAME,
            execution_id=str(uuid4()),
            triggered_by=triggered_by,
            correlation_id=str(uuid4()),
            user_id=user_id,
            trust_flame=trust_flame,
            capabilities=capabilities or self.REQUIRED_CAPABILITIES,
            fuel_budget=fuel_budget or self.DEFAULT_FUEL_BUDGET,
            metadata=metadata
        )


class PassthroughOverlay(BaseOverlay):
    """
    Simple passthrough overlay for testing.

    Just returns the input data unchanged.
    """

    NAME = "passthrough"
    VERSION = "1.0.0"
    DESCRIPTION = "Passes input through unchanged"
    SUBSCRIBED_EVENTS = {EventType.SYSTEM_EVENT}

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """Simply return input as output."""
        data = input_data or {}
        if event:
            data["event_type"] = event.event_type.value
            data["event_payload"] = event.payload

        return OverlayResult.ok(data=data)


class CompositeOverlay(BaseOverlay):
    """
    Overlay that composes multiple overlays in sequence.

    Executes each child overlay and passes results forward.
    """

    NAME = "composite"
    VERSION = "1.0.0"
    DESCRIPTION = "Composes multiple overlays"

    def __init__(self, overlays: list[BaseOverlay]):
        super().__init__()
        self.overlays = overlays

        # Aggregate subscribed events
        self.SUBSCRIBED_EVENTS = set()
        for overlay in overlays:
            self.SUBSCRIBED_EVENTS.update(overlay.SUBSCRIBED_EVENTS)

    async def initialize(self) -> bool:
        """Initialize all child overlays."""
        for overlay in self.overlays:
            if not await overlay.initialize():
                return False
        return await super().initialize()

    async def cleanup(self) -> None:
        """Cleanup all child overlays."""
        for overlay in self.overlays:
            await overlay.cleanup()
        await super().cleanup()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """Execute all child overlays in sequence."""
        current_data = input_data or {}
        all_events = []
        all_metrics = {}
        total_duration = 0.0

        for overlay in self.overlays:
            result = await overlay.run(context, event, current_data)

            if not result.success:
                return OverlayResult.fail(
                    f"Child overlay '{overlay.NAME}' failed: {result.error}",
                    events_to_emit=all_events,
                    metrics=all_metrics,
                    duration_ms=total_duration + result.duration_ms
                )

            # Chain data forward
            if result.data:
                current_data.update(result.data)

            # Collect events and metrics
            all_events.extend(result.events_to_emit)
            all_metrics[overlay.NAME] = result.metrics
            total_duration += result.duration_ms

        return OverlayResult.ok(
            data=current_data,
            events_to_emit=all_events,
            metrics=all_metrics,
            duration_ms=total_duration
        )
