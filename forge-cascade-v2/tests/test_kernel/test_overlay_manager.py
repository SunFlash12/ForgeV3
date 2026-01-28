"""
Comprehensive tests for the OverlayManager.

Tests cover:
- Overlay registration (class and instance)
- Overlay activation and deactivation
- Overlay discovery (by ID, name, event type)
- Overlay execution and coordination
- Circuit breaker functionality
- Health monitoring
- Execution history and metrics
- Lifecycle management (start, stop)
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.kernel.event_system import EventBus
from forge.kernel.overlay_manager import (
    OverlayExecutionRequest,
    OverlayManager,
    OverlayNotFoundError,
    OverlayRegistrationError,
    get_overlay_manager,
    init_overlay_manager,
    shutdown_overlay_manager,
)
from forge.models.base import OverlayState
from forge.models.events import Event, EventType
from forge.models.overlay import Capability, FuelBudget
from forge.overlays.base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
    PassthroughOverlay,
)


# =============================================================================
# Test Overlays
# =============================================================================


class MockOverlay(BaseOverlay):
    """Mock overlay for testing."""

    NAME = "mock_overlay"
    VERSION = "1.0.0"
    DESCRIPTION = "Mock overlay for testing"
    SUBSCRIBED_EVENTS = {EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED}
    REQUIRED_CAPABILITIES = {Capability.DATABASE_READ}

    def __init__(self) -> None:
        super().__init__()
        self.execute_count = 0
        self.should_fail = False
        self.fail_message = "Test failure"

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """Execute mock logic."""
        self.execute_count += 1

        if self.should_fail:
            return OverlayResult.fail(self.fail_message)

        return OverlayResult.ok(
            data={
                "processed": True,
                "execute_count": self.execute_count,
                "input_data": input_data,
            }
        )


class FailingOverlay(BaseOverlay):
    """Overlay that always fails."""

    NAME = "failing_overlay"
    VERSION = "1.0.0"
    DESCRIPTION = "Always fails"
    SUBSCRIBED_EVENTS = {EventType.SYSTEM_EVENT}

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """Always fails."""
        raise RuntimeError("Intentional failure")


class SlowOverlay(BaseOverlay):
    """Overlay that takes time to execute."""

    NAME = "slow_overlay"
    VERSION = "1.0.0"
    DESCRIPTION = "Slow execution"
    SUBSCRIBED_EVENTS = {EventType.SYSTEM_EVENT}

    def __init__(self, delay: float = 0.1) -> None:
        super().__init__()
        self.delay = delay

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """Execute with delay."""
        await asyncio.sleep(self.delay)
        return OverlayResult.ok(data={"delayed": True})


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def overlay_manager() -> OverlayManager:
    """Create a fresh OverlayManager instance."""
    return OverlayManager()


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def overlay_manager_with_bus(event_bus: EventBus) -> OverlayManager:
    """Create OverlayManager with an EventBus."""
    return OverlayManager(event_bus=event_bus)


@pytest.fixture
async def started_manager(overlay_manager: OverlayManager) -> OverlayManager:
    """Create and start an OverlayManager."""
    await overlay_manager.start()
    yield overlay_manager
    await overlay_manager.stop()


@pytest.fixture
def mock_overlay() -> MockOverlay:
    """Create a mock overlay instance."""
    return MockOverlay()


# =============================================================================
# Registration Tests
# =============================================================================


class TestOverlayRegistration:
    """Tests for overlay registration."""

    def test_register_class(self, overlay_manager: OverlayManager) -> None:
        """Test registering an overlay class."""
        overlay_manager.register_class(MockOverlay)

        assert "mock_overlay" in overlay_manager._registry.classes

    def test_register_class_with_custom_name(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test registering an overlay class with custom name."""
        overlay_manager.register_class(MockOverlay, name="custom_name")

        assert "custom_name" in overlay_manager._registry.classes
        assert "mock_overlay" not in overlay_manager._registry.classes

    @pytest.mark.asyncio
    async def test_create_instance(self, overlay_manager: OverlayManager) -> None:
        """Test creating an overlay instance from registered class."""
        overlay_manager.register_class(MockOverlay)

        overlay = await overlay_manager.create_instance("mock_overlay")

        assert overlay is not None
        assert overlay.NAME == "mock_overlay"
        assert overlay._initialized is True

    @pytest.mark.asyncio
    async def test_create_instance_not_found(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test creating instance for unregistered class."""
        with pytest.raises(OverlayNotFoundError):
            await overlay_manager.create_instance("nonexistent")

    @pytest.mark.asyncio
    async def test_register_instance(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test registering an overlay instance."""
        overlay_id = await overlay_manager.register_instance(mock_overlay)

        assert overlay_id == mock_overlay.id
        assert overlay_manager.get_by_id(overlay_id) is mock_overlay

    @pytest.mark.asyncio
    async def test_register_instance_indexes_by_name(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that instance is indexed by name."""
        await overlay_manager.register_instance(mock_overlay)

        overlays = overlay_manager.get_by_name("mock_overlay")
        assert len(overlays) == 1
        assert overlays[0] is mock_overlay

    @pytest.mark.asyncio
    async def test_register_instance_indexes_by_event(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that instance is indexed by subscribed events."""
        await overlay_manager.register_instance(mock_overlay)

        overlays = overlay_manager.get_by_event(EventType.CAPSULE_CREATED)
        assert len(overlays) == 1
        assert overlays[0] is mock_overlay

    @pytest.mark.asyncio
    async def test_register_instance_auto_init(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that instance is auto-initialized."""
        await overlay_manager.register_instance(mock_overlay, auto_init=True)

        assert mock_overlay._initialized is True
        assert mock_overlay.state == OverlayState.ACTIVE

    @pytest.mark.asyncio
    async def test_register_instance_no_auto_init(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test instance registration without auto-init."""
        await overlay_manager.register_instance(mock_overlay, auto_init=False)

        assert mock_overlay._initialized is False
        assert mock_overlay.state == OverlayState.REGISTERED


# =============================================================================
# Activation/Deactivation Tests
# =============================================================================


class TestOverlayActivation:
    """Tests for overlay activation and deactivation."""

    @pytest.mark.asyncio
    async def test_activate_overlay(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test activating an overlay."""
        await overlay_manager.register_instance(mock_overlay, auto_init=False)

        result = await overlay_manager.activate(mock_overlay.id)

        assert result is True
        assert mock_overlay.state == OverlayState.ACTIVE

    @pytest.mark.asyncio
    async def test_activate_already_active(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test activating already active overlay."""
        await overlay_manager.register_instance(mock_overlay)

        result = await overlay_manager.activate(mock_overlay.id)

        assert result is True  # Should succeed but not change state

    @pytest.mark.asyncio
    async def test_activate_nonexistent(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test activating non-existent overlay."""
        result = await overlay_manager.activate("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_overlay(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test deactivating an overlay."""
        await overlay_manager.register_instance(mock_overlay)

        result = await overlay_manager.deactivate(mock_overlay.id)

        assert result is True
        assert mock_overlay.state == OverlayState.INACTIVE

    @pytest.mark.asyncio
    async def test_deactivate_already_inactive(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test deactivating already inactive overlay."""
        await overlay_manager.register_instance(mock_overlay, auto_init=False)

        result = await overlay_manager.deactivate(mock_overlay.id)

        assert result is True  # Should succeed

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test deactivating non-existent overlay."""
        result = await overlay_manager.deactivate("nonexistent")
        assert result is False


# =============================================================================
# Unregistration Tests
# =============================================================================


class TestOverlayUnregistration:
    """Tests for overlay unregistration."""

    @pytest.mark.asyncio
    async def test_unregister(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test unregistering an overlay."""
        await overlay_manager.register_instance(mock_overlay)

        result = await overlay_manager.unregister(mock_overlay.id)

        assert result is True
        assert overlay_manager.get_by_id(mock_overlay.id) is None

    @pytest.mark.asyncio
    async def test_unregister_removes_from_indices(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that unregister removes from all indices."""
        await overlay_manager.register_instance(mock_overlay)

        await overlay_manager.unregister(mock_overlay.id)

        assert len(overlay_manager.get_by_name("mock_overlay")) == 0
        assert len(overlay_manager.get_by_event(EventType.CAPSULE_CREATED)) == 0

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test unregistering non-existent overlay."""
        result = await overlay_manager.unregister("nonexistent")
        assert result is False


# =============================================================================
# Discovery Tests
# =============================================================================


class TestOverlayDiscovery:
    """Tests for overlay discovery."""

    @pytest.mark.asyncio
    async def test_get_by_id(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting overlay by ID."""
        await overlay_manager.register_instance(mock_overlay)

        result = overlay_manager.get_by_id(mock_overlay.id)

        assert result is mock_overlay

    def test_get_by_id_nonexistent(self, overlay_manager: OverlayManager) -> None:
        """Test getting non-existent overlay by ID."""
        result = overlay_manager.get_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting overlays by name."""
        await overlay_manager.register_instance(mock_overlay)

        result = overlay_manager.get_by_name("mock_overlay")

        assert len(result) == 1
        assert result[0] is mock_overlay

    @pytest.mark.asyncio
    async def test_get_by_name_multiple(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test getting multiple overlays by name."""
        overlay1 = MockOverlay()
        overlay2 = MockOverlay()

        await overlay_manager.register_instance(overlay1)
        await overlay_manager.register_instance(overlay2)

        result = overlay_manager.get_by_name("mock_overlay")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_event(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting overlays by event type."""
        await overlay_manager.register_instance(mock_overlay)

        result = overlay_manager.get_by_event(EventType.CAPSULE_CREATED)

        assert len(result) == 1
        assert result[0] is mock_overlay

    @pytest.mark.asyncio
    async def test_list_all(self, overlay_manager: OverlayManager) -> None:
        """Test listing all overlays."""
        overlay1 = MockOverlay()
        overlay2 = PassthroughOverlay()

        await overlay_manager.register_instance(overlay1)
        await overlay_manager.register_instance(overlay2)

        result = overlay_manager.list_all()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_active(self, overlay_manager: OverlayManager) -> None:
        """Test listing active overlays."""
        overlay1 = MockOverlay()
        overlay2 = MockOverlay()

        await overlay_manager.register_instance(overlay1, auto_init=True)
        await overlay_manager.register_instance(overlay2, auto_init=False)

        result = overlay_manager.list_active()

        assert len(result) == 1
        assert result[0] is overlay1

    def test_get_overlay_count(self, overlay_manager: OverlayManager) -> None:
        """Test getting overlay count."""
        assert overlay_manager.get_overlay_count() == 0

    @pytest.mark.asyncio
    async def test_get_registry_info(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting registry info."""
        await overlay_manager.register_instance(mock_overlay)

        info = overlay_manager.get_registry_info()

        assert info["total_instances"] == 1
        assert info["active"] == 1


# =============================================================================
# Execution Tests
# =============================================================================


class TestOverlayExecution:
    """Tests for overlay execution."""

    @pytest.mark.asyncio
    async def test_execute_by_name(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test executing overlay by name."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            input_data={"test": "data"},
            capabilities={Capability.DATABASE_READ},
        )
        result = await overlay_manager.execute(request)

        assert result.success is True
        assert result.data["processed"] is True

    @pytest.mark.asyncio
    async def test_execute_not_found(self, overlay_manager: OverlayManager) -> None:
        """Test executing non-existent overlay."""
        request = OverlayExecutionRequest(overlay_name="nonexistent")
        result = await overlay_manager.execute(request)

        assert result.success is False
        assert "No overlay found" in result.error

    @pytest.mark.asyncio
    async def test_execute_overlay_by_id(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test executing specific overlay by ID."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            capabilities={Capability.DATABASE_READ},
        )
        result = await overlay_manager.execute_overlay(mock_overlay.id, request)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_records_history(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that execution is recorded in history."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            capabilities={Capability.DATABASE_READ},
        )
        await overlay_manager.execute(request)

        history = overlay_manager.get_recent_executions(limit=1)
        assert len(history) == 1
        assert history[0]["success"] is True

    @pytest.mark.asyncio
    async def test_execute_for_event(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test executing overlays for an event."""
        await overlay_manager.register_instance(mock_overlay)

        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "123"},
        )

        results = await overlay_manager.execute_for_event(
            event=event,
            capabilities={Capability.DATABASE_READ},
        )

        assert len(results) == 1
        assert list(results.values())[0].success is True


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test that circuit opens after threshold failures."""
        overlay = FailingOverlay()
        await overlay_manager.register_instance(overlay)

        request = OverlayExecutionRequest(overlay_name="failing_overlay")

        # Execute until circuit opens (threshold is 5)
        for _ in range(5):
            await overlay_manager.execute(request)

        # Circuit should be open now
        assert overlay_manager._is_circuit_open(overlay.id) is True

    @pytest.mark.asyncio
    async def test_circuit_blocks_execution(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test that open circuit blocks execution."""
        overlay = FailingOverlay()
        await overlay_manager.register_instance(overlay)

        # Manually open circuit
        overlay_manager._circuit_open[overlay.id] = datetime.now(UTC)

        request = OverlayExecutionRequest(overlay_name="failing_overlay")
        result = await overlay_manager.execute(request)

        assert result.success is False
        assert "circuit breaker open" in result.error.lower()

    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test that circuit resets after timeout."""
        overlay = MockOverlay()
        await overlay_manager.register_instance(overlay)

        # Open circuit with old timestamp
        old_time = datetime.now(UTC) - timedelta(seconds=60)
        overlay_manager._circuit_open[overlay.id] = old_time

        # Check should reset circuit
        is_open = overlay_manager._is_circuit_open(overlay.id)

        assert is_open is False
        assert overlay.id not in overlay_manager._circuit_open

    @pytest.mark.asyncio
    async def test_reset_circuit_manually(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test manually resetting circuit."""
        await overlay_manager.register_instance(mock_overlay)

        overlay_manager._circuit_open[mock_overlay.id] = datetime.now(UTC)
        overlay_manager._failure_counts[mock_overlay.id] = 10

        overlay_manager.reset_circuit(mock_overlay.id)

        assert mock_overlay.id not in overlay_manager._circuit_open
        assert mock_overlay.id not in overlay_manager._failure_counts


# =============================================================================
# Health Monitoring Tests
# =============================================================================


class TestHealthMonitoring:
    """Tests for health monitoring functionality."""

    @pytest.mark.asyncio
    async def test_health_check_all(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test health check for all overlays."""
        await overlay_manager.register_instance(mock_overlay)

        results = await overlay_manager.health_check_all()

        assert mock_overlay.id in results
        assert results[mock_overlay.id].healthy is True

    @pytest.mark.asyncio
    async def test_get_unhealthy_overlays(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test getting unhealthy overlays."""
        overlay1 = MockOverlay()
        overlay2 = MockOverlay()

        await overlay_manager.register_instance(overlay1)
        await overlay_manager.register_instance(overlay2, auto_init=False)

        unhealthy = await overlay_manager.get_unhealthy_overlays()

        # overlay2 should be unhealthy (not initialized)
        assert len(unhealthy) == 1


# =============================================================================
# History and Metrics Tests
# =============================================================================


class TestHistoryAndMetrics:
    """Tests for execution history and metrics."""

    @pytest.mark.asyncio
    async def test_get_execution_stats(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting execution statistics."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            capabilities={Capability.DATABASE_READ},
        )
        await overlay_manager.execute(request)
        await overlay_manager.execute(request)

        stats = overlay_manager.get_execution_stats()

        assert stats["total"] == 2
        assert stats["success"] == 2
        assert stats["failure"] == 0

    @pytest.mark.asyncio
    async def test_get_execution_stats_by_overlay(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting execution statistics for specific overlay."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            capabilities={Capability.DATABASE_READ},
        )
        await overlay_manager.execute(request)

        stats = overlay_manager.get_execution_stats(overlay_id=mock_overlay.id)

        assert stats["total"] == 1

    def test_get_execution_stats_empty(self, overlay_manager: OverlayManager) -> None:
        """Test getting stats with no executions."""
        stats = overlay_manager.get_execution_stats()

        assert stats["total"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_recent_executions(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test getting recent executions."""
        await overlay_manager.register_instance(mock_overlay)

        request = OverlayExecutionRequest(
            overlay_name="mock_overlay",
            capabilities={Capability.DATABASE_READ},
        )
        for _ in range(5):
            await overlay_manager.execute(request)

        recent = overlay_manager.get_recent_executions(limit=3)

        assert len(recent) == 3

    def test_execution_history_bounded(self, overlay_manager: OverlayManager) -> None:
        """Test that execution history is bounded."""
        # Fill history beyond limit
        for i in range(1100):
            overlay_manager._record_execution(
                overlay_id=f"overlay-{i}",
                execution_id=f"exec-{i}",
                success=True,
                duration_ms=100.0,
            )

        # Should be bounded to max_history (1000)
        assert len(overlay_manager._execution_history) == 1000


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestOverlayManagerLifecycle:
    """Tests for OverlayManager lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self, overlay_manager: OverlayManager) -> None:
        """Test starting the overlay manager."""
        await overlay_manager.start()

        assert overlay_manager._running is True
        assert overlay_manager._event_bus is not None

        await overlay_manager.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, overlay_manager: OverlayManager) -> None:
        """Test that start is idempotent."""
        await overlay_manager.start()
        await overlay_manager.start()

        assert overlay_manager._running is True

        await overlay_manager.stop()

    @pytest.mark.asyncio
    async def test_stop(self, overlay_manager: OverlayManager) -> None:
        """Test stopping the overlay manager."""
        await overlay_manager.start()
        await overlay_manager.stop()

        assert overlay_manager._running is False

    @pytest.mark.asyncio
    async def test_stop_cleanup_overlays(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that stop cleans up overlays."""
        await overlay_manager.start()
        await overlay_manager.register_instance(mock_overlay)

        await overlay_manager.stop()

        # Overlay should have been cleaned up
        assert mock_overlay._initialized is False


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestEventHandling:
    """Tests for event handling functionality."""

    @pytest.mark.asyncio
    async def test_handle_event_routes_to_overlays(
        self, started_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that events are routed to overlays."""
        await started_manager.register_instance(mock_overlay)

        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )

        await started_manager._handle_event(event)

        assert mock_overlay.execute_count == 1

    @pytest.mark.asyncio
    async def test_handle_event_skips_inactive_overlays(
        self, started_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that events skip inactive overlays."""
        await started_manager.register_instance(mock_overlay, auto_init=False)

        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )

        await started_manager._handle_event(event)

        assert mock_overlay.execute_count == 0

    @pytest.mark.asyncio
    async def test_handle_event_when_not_running(
        self, overlay_manager: OverlayManager, mock_overlay: MockOverlay
    ) -> None:
        """Test that events are ignored when not running."""
        await overlay_manager.register_instance(mock_overlay)

        event = Event(
            id="test-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )

        await overlay_manager._handle_event(event)

        assert mock_overlay.execute_count == 0


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalOverlayManager:
    """Tests for global overlay manager instance."""

    def test_get_overlay_manager(self) -> None:
        """Test getting global overlay manager."""
        import forge.kernel.overlay_manager as om

        om._overlay_manager = None

        manager = get_overlay_manager()
        assert manager is not None

        manager2 = get_overlay_manager()
        assert manager is manager2

        om._overlay_manager = None

    @pytest.mark.asyncio
    async def test_init_overlay_manager(self) -> None:
        """Test initializing global overlay manager."""
        import forge.kernel.overlay_manager as om

        om._overlay_manager = None

        manager = await init_overlay_manager()
        assert manager._running is True

        await shutdown_overlay_manager()
        assert om._overlay_manager is None

    @pytest.mark.asyncio
    async def test_shutdown_overlay_manager(self) -> None:
        """Test shutting down global overlay manager."""
        import forge.kernel.overlay_manager as om

        await init_overlay_manager()
        await shutdown_overlay_manager()

        assert om._overlay_manager is None


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_execute_with_event_emission(
        self, overlay_manager_with_bus: OverlayManager
    ) -> None:
        """Test that events from results are emitted."""

        class EmittingOverlay(BaseOverlay):
            NAME = "emitting_overlay"
            VERSION = "1.0.0"
            SUBSCRIBED_EVENTS = {EventType.SYSTEM_EVENT}

            async def execute(
                self,
                context: OverlayContext,
                event: Event | None = None,
                input_data: dict[str, Any] | None = None,
            ) -> OverlayResult:
                return OverlayResult.ok(
                    events_to_emit=[
                        {
                            "event_type": EventType.CAPSULE_CREATED.value,
                            "payload": {"test": True},
                        }
                    ]
                )

        overlay = EmittingOverlay()
        await overlay_manager_with_bus.register_instance(overlay)
        await overlay_manager_with_bus.start()

        request = OverlayExecutionRequest(overlay_name="emitting_overlay")
        result = await overlay_manager_with_bus.execute(request)

        assert result.success is True

        await overlay_manager_with_bus.stop()

    @pytest.mark.asyncio
    async def test_phase_to_int_conversion(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test phase to int conversion."""
        from enum import Enum

        class TestPhase(str, Enum):
            VALIDATION = "validation"

        result = overlay_manager._phase_to_int(TestPhase.VALIDATION)
        assert result == 2  # validation maps to 2

    @pytest.mark.asyncio
    async def test_get_overlays_for_phase(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test getting overlays for a pipeline phase."""
        # Currently no overlays have phase attribute in tests
        result = overlay_manager.get_overlays_for_phase(1)
        assert result == []
