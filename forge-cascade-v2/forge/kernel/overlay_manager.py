"""
Overlay Manager for Forge Cascade V2

Manages overlay lifecycle, registration, discovery, and event routing.
Acts as the central coordinator for all overlay instances.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from ..models.base import OverlayState
from ..models.events import Event, EventType
from ..models.overlay import Capability, FuelBudget, OverlayHealthCheck
from ..overlays.base import BaseOverlay, OverlayContext, OverlayError, OverlayResult
from .event_system import EventBus, get_event_bus

logger = structlog.get_logger()


class OverlayNotFoundError(OverlayError):
    """Overlay not found in registry."""
    pass


class OverlayRegistrationError(OverlayError):
    """Error registering overlay."""
    pass


class OverlayExecutionError(OverlayError):
    """Error executing overlay."""
    pass


@dataclass
class OverlayExecutionRequest:
    """Request to execute an overlay."""
    overlay_name: str
    input_data: dict[str, Any] | None = None
    event: Event | None = None
    user_id: str | None = None
    trust_flame: int = 60
    capabilities: set[Capability] = field(default_factory=set)
    fuel_budget: FuelBudget | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OverlayRegistry:
    """Registry of overlay instances."""
    instances: dict[str, BaseOverlay] = field(default_factory=dict)  # id -> instance
    by_name: dict[str, list[str]] = field(default_factory=dict)  # name -> [ids]
    by_event: dict[EventType, set[str]] = field(default_factory=dict)  # event -> {ids}
    classes: dict[str, type[BaseOverlay]] = field(default_factory=dict)  # name -> class


class OverlayManager:
    """
    Manages overlay lifecycle and execution.

    Responsibilities:
    - Overlay registration and discovery
    - Lifecycle management (init, cleanup)
    - Event routing to appropriate overlays
    - Execution coordination
    - Health monitoring
    """

    def __init__(self, event_bus: EventBus | None = None):
        """
        Initialize the overlay manager.

        Args:
            event_bus: EventBus instance (uses global if not provided)
        """
        self._registry = OverlayRegistry()
        self._event_bus = event_bus
        self._running = False
        self._lock = asyncio.Lock()
        self._logger = logger.bind(component="overlay_manager")

        # Execution tracking
        self._pending_executions: dict[str, asyncio.Task[Any]] = {}
        # SECURITY FIX (Audit 7 - Session 2): Use deque for automatic memory bounding
        self._max_history = 1000
        self._execution_history: deque[dict[str, Any]] = deque(maxlen=self._max_history)

        # Circuit breaker per overlay
        self._failure_counts: dict[str, int] = {}
        self._circuit_open: dict[str, datetime] = {}
        self._circuit_threshold = 5
        self._circuit_timeout = 30  # seconds

    async def start(self) -> None:
        """Start the overlay manager."""
        if self._running:
            return

        self._event_bus = self._event_bus or get_event_bus()
        self._running = True

        # Subscribe to all events to route to overlays
        self._event_bus.subscribe_all(self._handle_event)

        self._logger.info("overlay_manager_started")

    async def stop(self) -> None:
        """Stop the overlay manager."""
        if not self._running:
            return

        self._running = False

        # Cancel pending executions
        for task in self._pending_executions.values():
            task.cancel()

        if self._pending_executions:
            await asyncio.gather(
                *self._pending_executions.values(),
                return_exceptions=True
            )

        # Cleanup all overlays
        async with self._lock:
            for overlay in self._registry.instances.values():
                try:
                    await overlay.cleanup()
                except (OverlayError, RuntimeError, OSError) as e:
                    self._logger.error(
                        "overlay_cleanup_error",
                        overlay_name=overlay.NAME,
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        self._logger.info("overlay_manager_stopped")

    # =========================================================================
    # Registration
    # =========================================================================

    def register_class(
        self,
        overlay_class: type[BaseOverlay],
        name: str | None = None
    ) -> None:
        """
        Register an overlay class for later instantiation.

        Args:
            overlay_class: The overlay class to register
            name: Optional name override
        """
        class_name = name or overlay_class.NAME
        self._registry.classes[class_name] = overlay_class
        self._logger.info("overlay_class_registered", name=class_name)

    async def create_instance(
        self,
        name: str,
        auto_init: bool = True,
        **kwargs: Any
    ) -> BaseOverlay:
        """
        Create and register a new overlay instance.

        Args:
            name: Name of registered overlay class
            auto_init: Whether to initialize immediately
            **kwargs: Arguments to pass to constructor

        Returns:
            The created overlay instance
        """
        if name not in self._registry.classes:
            raise OverlayNotFoundError(f"Overlay class '{name}' not registered")

        overlay_class = self._registry.classes[name]
        overlay = overlay_class(**kwargs) if kwargs else overlay_class()

        await self.register_instance(overlay, auto_init=auto_init)
        return overlay

    async def register_instance(
        self,
        overlay: BaseOverlay,
        auto_init: bool = True
    ) -> str:
        """
        Register an overlay instance.

        Args:
            overlay: The overlay instance to register
            auto_init: Whether to initialize immediately

        Returns:
            The overlay ID
        """
        async with self._lock:
            # Store instance
            self._registry.instances[overlay.id] = overlay

            # Index by name
            if overlay.NAME not in self._registry.by_name:
                self._registry.by_name[overlay.NAME] = []
            self._registry.by_name[overlay.NAME].append(overlay.id)

            # Index by subscribed events
            for event_type in overlay.SUBSCRIBED_EVENTS:
                if event_type not in self._registry.by_event:
                    self._registry.by_event[event_type] = set()
                self._registry.by_event[event_type].add(overlay.id)

        self._logger.info(
            "overlay_instance_registered",
            overlay_id=overlay.id,
            name=overlay.NAME,
            events=len(overlay.SUBSCRIBED_EVENTS)
        )

        # Initialize if requested
        if auto_init:
            success = await overlay.initialize()
            if not success:
                await self.unregister(overlay.id)
                raise OverlayRegistrationError(
                    f"Failed to initialize overlay '{overlay.NAME}'"
                )

        return overlay.id

    async def activate(self, overlay_id: str) -> bool:
        """
        Activate an overlay (set state to ACTIVE).

        Args:
            overlay_id: ID of overlay to activate

        Returns:
            True if overlay was found and activated
        """
        overlay = self.get_by_id(overlay_id)
        if not overlay:
            return False

        if overlay.state == OverlayState.ACTIVE:
            return True  # Already active

        # If not initialized, initialize it
        if not overlay._initialized:
            success = await overlay.initialize()
            if not success:
                self._logger.error(
                    "overlay_activation_failed",
                    overlay_id=overlay_id,
                    reason="initialization_failed"
                )
                return False
        else:
            # Just set state to active
            overlay.state = OverlayState.ACTIVE

        # Reset circuit breaker
        self.reset_circuit(overlay_id)

        self._logger.info("overlay_activated", overlay_id=overlay_id, name=overlay.NAME)
        return True

    async def deactivate(self, overlay_id: str) -> bool:
        """
        Deactivate an overlay (set state to INACTIVE).

        Args:
            overlay_id: ID of overlay to deactivate

        Returns:
            True if overlay was found and deactivated
        """
        overlay = self.get_by_id(overlay_id)
        if not overlay:
            return False

        if overlay.state != OverlayState.ACTIVE:
            return True  # Already not active

        overlay.state = OverlayState.INACTIVE

        self._logger.info("overlay_deactivated", overlay_id=overlay_id, name=overlay.NAME)
        return True

    async def unregister(self, overlay_id: str) -> bool:
        """
        Unregister an overlay.

        Args:
            overlay_id: ID of overlay to unregister

        Returns:
            True if overlay was found and unregistered
        """
        async with self._lock:
            if overlay_id not in self._registry.instances:
                return False

            overlay = self._registry.instances[overlay_id]

            # Cleanup
            try:
                await overlay.cleanup()
            except (OverlayError, RuntimeError, OSError) as e:
                self._logger.error(
                    "overlay_cleanup_error",
                    overlay_id=overlay_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Remove from indices
            del self._registry.instances[overlay_id]

            if overlay.NAME in self._registry.by_name:
                self._registry.by_name[overlay.NAME].remove(overlay_id)
                if not self._registry.by_name[overlay.NAME]:
                    del self._registry.by_name[overlay.NAME]

            for event_type in overlay.SUBSCRIBED_EVENTS:
                if event_type in self._registry.by_event:
                    self._registry.by_event[event_type].discard(overlay_id)

            # Clear circuit breaker state
            self._failure_counts.pop(overlay_id, None)
            self._circuit_open.pop(overlay_id, None)

        self._logger.info("overlay_unregistered", overlay_id=overlay_id)
        return True

    # =========================================================================
    # Discovery
    # =========================================================================

    def get_by_id(self, overlay_id: str) -> BaseOverlay | None:
        """Get overlay by ID."""
        return self._registry.instances.get(overlay_id)

    def get_by_name(self, name: str) -> list[BaseOverlay]:
        """Get all overlays with a given name."""
        ids = self._registry.by_name.get(name, [])
        return [self._registry.instances[id_] for id_ in ids]

    def get_by_event(self, event_type: EventType) -> list[BaseOverlay]:
        """Get overlays that subscribe to an event type."""
        ids = self._registry.by_event.get(event_type, set())
        return [self._registry.instances[id_] for id_ in ids]

    def list_all(self) -> list[BaseOverlay]:
        """List all registered overlays."""
        return list(self._registry.instances.values())

    def get_overlay_count(self) -> int:
        """Get total number of registered overlay instances."""
        return len(self._registry.instances)

    def list_active(self) -> list[BaseOverlay]:
        """List all active overlays."""
        return [
            o for o in self._registry.instances.values()
            if o.state == OverlayState.ACTIVE
        ]

    def get_overlays_for_phase(self, phase: int) -> list[BaseOverlay]:
        """List overlays for a specific pipeline phase."""
        return [
            o for o in self._registry.instances.values()
            if getattr(o, 'phase', None) == phase or
               (hasattr(o, 'phase') and hasattr(o.phase, 'value') and
                self._phase_to_int(o.phase) == phase)
        ]

    def _phase_to_int(self, phase: Any) -> int:
        """Convert phase enum to integer."""
        phase_map = {
            "intake": 1, "validation": 2, "analysis": 3, "governance": 4,
            "integration": 5, "distribution": 6, "feedback": 7
        }
        if hasattr(phase, 'value'):
            return phase_map.get(phase.value.lower(), 0)
        return phase_map.get(str(phase).lower(), 0)

    def get_registry_info(self) -> dict[str, Any]:
        """Get registry summary information."""
        return {
            "total_instances": len(self._registry.instances),
            "total_classes": len(self._registry.classes),
            "by_name": {
                name: len(ids)
                for name, ids in self._registry.by_name.items()
            },
            "by_event": {
                et.value: len(ids)
                for et, ids in self._registry.by_event.items()
            },
            "active": len(self.list_active()),
            "circuit_open": len(self._circuit_open)
        }

    # =========================================================================
    # Execution
    # =========================================================================

    async def execute(
        self,
        request: OverlayExecutionRequest
    ) -> OverlayResult:
        """
        Execute an overlay by name.

        Args:
            request: Execution request details

        Returns:
            OverlayResult from execution
        """
        # Get overlay instances
        overlays = self.get_by_name(request.overlay_name)
        if not overlays:
            return OverlayResult.fail(
                f"No overlay found with name: {request.overlay_name}"
            )

        # Use first active overlay
        overlay = None
        for o in overlays:
            if o.state == OverlayState.ACTIVE:
                if not self._is_circuit_open(o.id):
                    overlay = o
                    break

        if not overlay:
            return OverlayResult.fail(
                f"No active overlay available: {request.overlay_name}"
            )

        return await self.execute_overlay(overlay.id, request)

    async def execute_overlay(
        self,
        overlay_id: str,
        request: OverlayExecutionRequest
    ) -> OverlayResult:
        """
        Execute a specific overlay instance.

        Args:
            overlay_id: ID of overlay to execute
            request: Execution request details

        Returns:
            OverlayResult from execution
        """
        overlay = self.get_by_id(overlay_id)
        if not overlay:
            return OverlayResult.fail(f"Overlay not found: {overlay_id}")

        # Check circuit breaker
        if self._is_circuit_open(overlay_id):
            return OverlayResult.fail(
                f"Overlay circuit breaker open: {overlay.NAME}"
            )

        # Build context
        context = OverlayContext(
            overlay_id=overlay_id,
            overlay_name=overlay.NAME,
            execution_id=str(uuid4()),
            triggered_by=request.event.id if request.event else "manual",
            correlation_id=request.correlation_id or str(uuid4()),
            user_id=request.user_id,
            trust_flame=request.trust_flame,
            capabilities=request.capabilities or overlay.REQUIRED_CAPABILITIES,
            fuel_budget=request.fuel_budget or overlay.DEFAULT_FUEL_BUDGET,
            metadata=request.metadata
        )

        # Execute
        datetime.now(UTC)
        try:
            result = await overlay.run(context, request.event, request.input_data)

            # Record success
            self._record_execution(
                overlay_id=overlay_id,
                execution_id=context.execution_id,
                success=result.success,
                duration_ms=result.duration_ms,
                error=result.error
            )

            if result.success:
                self._failure_counts[overlay_id] = 0
            else:
                self._record_failure(overlay_id)

            # Emit any events from result
            if result.events_to_emit and self._event_bus:
                for event_data in result.events_to_emit:
                    await self._event_bus.publish(
                        event_type=EventType(event_data["event_type"]),
                        payload=event_data.get("payload", {}),
                        source=event_data.get("source", f"overlay:{overlay.NAME}"),
                        correlation_id=context.correlation_id,
                    )

            return result

        except (OverlayError, RuntimeError, ValueError, TypeError, KeyError, OSError) as e:
            self._record_failure(overlay_id)
            self._logger.error(
                "overlay_execution_failed",
                overlay_id=overlay_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return OverlayResult.fail(f"Execution error: {str(e)}")

    async def execute_for_event(
        self,
        event: Event,
        user_id: str | None = None,
        trust_flame: int = 60,
        capabilities: set[Capability] | None = None
    ) -> dict[str, OverlayResult]:
        """
        Execute all overlays that subscribe to an event.

        Args:
            event: The triggering event
            user_id: Optional user context
            trust_flame: Trust level for execution
            capabilities: Capabilities to grant

        Returns:
            Dict mapping overlay_id to result
        """
        overlays = self.get_by_event(event.type)
        if not overlays:
            return {}

        results = {}
        for overlay in overlays:
            if overlay.state != OverlayState.ACTIVE:
                continue
            if self._is_circuit_open(overlay.id):
                continue

            request = OverlayExecutionRequest(
                overlay_name=overlay.NAME,
                event=event,
                user_id=user_id,
                trust_flame=trust_flame,
                capabilities=capabilities or overlay.REQUIRED_CAPABILITIES,
                correlation_id=event.correlation_id
            )

            result = await self.execute_overlay(overlay.id, request)
            results[overlay.id] = result

        return results

    # =========================================================================
    # Event Handling
    # =========================================================================

    async def _handle_event(self, event: Event) -> None:
        """Handle events from the event bus."""
        if not self._running:
            return

        overlays = self.get_by_event(event.type)
        if not overlays:
            return

        self._logger.debug(
            "routing_event_to_overlays",
            event_type=event.type.value,
            overlay_count=len(overlays)
        )

        # Execute overlays concurrently
        tasks = []
        for overlay in overlays:
            if overlay.state != OverlayState.ACTIVE:
                continue
            if self._is_circuit_open(overlay.id):
                continue

            request = OverlayExecutionRequest(
                overlay_name=overlay.NAME,
                event=event,
                correlation_id=event.correlation_id
            )

            task = asyncio.create_task(
                self.execute_overlay(overlay.id, request)
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # =========================================================================
    # Circuit Breaker
    # SECURITY FIX (Audit 4 - H12): Use lock for atomic circuit breaker operations
    # =========================================================================

    def __init_circuit_lock(self) -> None:
        """Initialize circuit breaker lock if not already done."""
        if not hasattr(self, '_circuit_lock'):
            import threading
            self._circuit_lock = threading.Lock()

    def _is_circuit_open(self, overlay_id: str) -> bool:
        """
        Check if circuit breaker is open for an overlay.

        SECURITY FIX (Audit 4 - H12): Now uses atomic operations with locking
        to prevent race conditions in check-then-delete pattern.
        """
        self.__init_circuit_lock()

        with self._circuit_lock:
            if overlay_id not in self._circuit_open:
                return False

            open_time = self._circuit_open[overlay_id]
            if (datetime.now(UTC) - open_time).seconds >= self._circuit_timeout:
                # Half-open: allow one attempt - atomic delete under lock
                del self._circuit_open[overlay_id]
                return False

            return True

    def _record_failure(self, overlay_id: str) -> None:
        """
        Record an overlay execution failure.

        SECURITY FIX (Audit 4 - H12): Now uses atomic operations with locking.
        """
        self.__init_circuit_lock()

        with self._circuit_lock:
            self._failure_counts[overlay_id] = \
                self._failure_counts.get(overlay_id, 0) + 1

            if self._failure_counts[overlay_id] >= self._circuit_threshold:
                self._circuit_open[overlay_id] = datetime.now(UTC)
                self._logger.warning(
                    "overlay_circuit_opened",
                    overlay_id=overlay_id,
                    failures=self._failure_counts[overlay_id]
                )

    def reset_circuit(self, overlay_id: str) -> None:
        """
        Manually reset a circuit breaker.

        SECURITY FIX (Audit 4 - H12): Now uses atomic operations with locking.
        """
        self.__init_circuit_lock()

        with self._circuit_lock:
            self._failure_counts.pop(overlay_id, None)
            self._circuit_open.pop(overlay_id, None)
        self._logger.info("overlay_circuit_reset", overlay_id=overlay_id)

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    async def health_check_all(self) -> dict[str, OverlayHealthCheck]:
        """
        Perform health checks on all overlays.

        Returns:
            Dict mapping overlay_id to health check result
        """
        results = {}
        for overlay_id, overlay in self._registry.instances.items():
            try:
                results[overlay_id] = await overlay.health_check()
            except (OverlayError, RuntimeError, ValueError, OSError) as e:
                results[overlay_id] = OverlayHealthCheck(
                    overlay_id=overlay_id,
                    level="L1",
                    healthy=False,
                    message=str(e),
                    details={
                        "overlay_name": overlay.NAME,
                        "state": overlay.state.value if overlay.state else "unknown",
                        "execution_count": overlay.execution_count,
                        "error_count": overlay.error_count,
                        "error_rate": 1.0,
                    },
                    timestamp=datetime.now(UTC),
                )

        return results

    async def get_unhealthy_overlays(self) -> list[OverlayHealthCheck]:
        """Get list of unhealthy overlays."""
        all_health = await self.health_check_all()
        return [h for h in all_health.values() if not h.healthy]

    # =========================================================================
    # History & Metrics
    # =========================================================================

    def _record_execution(
        self,
        overlay_id: str,
        execution_id: str,
        success: bool,
        duration_ms: float,
        error: str | None = None
    ) -> None:
        """Record execution in history (deque auto-trims at maxlen)."""
        self._execution_history.append({
            "overlay_id": overlay_id,
            "execution_id": execution_id,
            "success": success,
            "duration_ms": duration_ms,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat()
        })

    def get_execution_stats(
        self,
        overlay_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get execution statistics.

        Args:
            overlay_id: Optional filter by overlay

        Returns:
            Statistics dict
        """
        history: list[dict[str, Any]] = list(self._execution_history)
        if overlay_id:
            history = [e for e in history if e["overlay_id"] == overlay_id]

        if not history:
            return {
                "total": 0,
                "success": 0,
                "failure": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0
            }

        success_count = sum(1 for e in history if e["success"])
        durations = [e["duration_ms"] for e in history]

        return {
            "total": len(history),
            "success": success_count,
            "failure": len(history) - success_count,
            "success_rate": success_count / len(history),
            "avg_duration_ms": sum(durations) / len(durations),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations)
        }

    def get_recent_executions(
        self,
        limit: int = 10,
        overlay_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent executions."""
        history: list[dict[str, Any]] = list(self._execution_history)
        if overlay_id:
            history = [e for e in history if e["overlay_id"] == overlay_id]

        return history[-limit:][::-1]  # Most recent first


# =========================================================================
# Global Instance
# =========================================================================

_overlay_manager: OverlayManager | None = None


def get_overlay_manager() -> OverlayManager:
    """Get the global overlay manager instance."""
    global _overlay_manager
    if _overlay_manager is None:
        _overlay_manager = OverlayManager()
    return _overlay_manager


async def init_overlay_manager(
    event_bus: EventBus | None = None
) -> OverlayManager:
    """Initialize and start the global overlay manager."""
    global _overlay_manager
    _overlay_manager = OverlayManager(event_bus)
    await _overlay_manager.start()
    return _overlay_manager


async def shutdown_overlay_manager() -> None:
    """Shutdown the global overlay manager."""
    global _overlay_manager
    if _overlay_manager:
        await _overlay_manager.stop()
        _overlay_manager = None
