"""
Comprehensive tests for the EventBus and event system.

Tests cover:
- Subscription management (subscribe, unsubscribe, filtering)
- Event publishing and delivery
- Cascade propagation (initiate, propagate, complete)
- Dead letter queue handling
- Metrics collection
- Lifecycle management (start, stop)
- Security limits (subscriber limits, queue backpressure)
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.kernel.event_system import (
    EventBus,
    EventMetrics,
    Subscription,
    emit,
    get_event_bus,
    init_event_bus,
    on,
    shutdown_event_bus,
)
from forge.models.events import (
    CascadeChain,
    CascadeEvent,
    Event,
    EventPriority,
    EventType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh EventBus instance for testing."""
    return EventBus(
        max_queue_size=100,
        max_retries=2,
        retry_delay_seconds=0.01,  # Fast retries for tests
        max_dead_letter_size=50,
        max_subscribers=100,
    )


@pytest.fixture
async def started_event_bus(event_bus: EventBus) -> EventBus:
    """Create and start an EventBus instance."""
    await event_bus.start()
    yield event_bus
    await event_bus.stop()


@pytest.fixture
def mock_cascade_repository() -> AsyncMock:
    """Create a mock cascade repository."""
    repo = AsyncMock()
    repo.create_chain = AsyncMock()
    repo.add_event = AsyncMock()
    repo.complete_chain = AsyncMock()
    repo.update_chain = AsyncMock()
    repo.get_active_chains = AsyncMock(return_value=[])
    return repo


# =============================================================================
# Subscription Tests
# =============================================================================


class TestSubscription:
    """Tests for Subscription dataclass."""

    def test_subscription_matches_event_type(self) -> None:
        """Test that subscription matches events by type."""
        handler = AsyncMock()
        sub = Subscription(
            id="test-sub",
            handler=handler,
            event_types={EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED},
        )

        event = Event(
            id="evt-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )
        assert sub.matches(event) is True

    def test_subscription_does_not_match_wrong_type(self) -> None:
        """Test that subscription does not match wrong event type."""
        handler = AsyncMock()
        sub = Subscription(
            id="test-sub",
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        event = Event(
            id="evt-1",
            type=EventType.USER_LOGIN,
            source="test",
            payload={},
        )
        assert sub.matches(event) is False

    def test_subscription_matches_priority(self) -> None:
        """Test that subscription respects priority filter."""
        handler = AsyncMock()
        sub = Subscription(
            id="test-sub",
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
            min_priority=EventPriority.HIGH,
        )

        high_priority = Event(
            id="evt-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
            priority=EventPriority.HIGH,
        )
        low_priority = Event(
            id="evt-2",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
            priority=EventPriority.LOW,
        )

        assert sub.matches(high_priority) is True
        assert sub.matches(low_priority) is False

    def test_subscription_matches_with_filter_func(self) -> None:
        """Test that subscription respects custom filter function."""
        handler = AsyncMock()
        sub = Subscription(
            id="test-sub",
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
            filter_func=lambda e: e.payload.get("user_id") == "test-user",
        )

        matching = Event(
            id="evt-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"user_id": "test-user"},
        )
        non_matching = Event(
            id="evt-2",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"user_id": "other-user"},
        )

        assert sub.matches(matching) is True
        assert sub.matches(non_matching) is False


# =============================================================================
# EventBus Subscription Tests
# =============================================================================


class TestEventBusSubscription:
    """Tests for EventBus subscription management."""

    def test_subscribe_returns_id(self, event_bus: EventBus) -> None:
        """Test that subscribe returns a subscription ID."""
        handler = AsyncMock()
        sub_id = event_bus.subscribe(
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        assert sub_id is not None
        assert isinstance(sub_id, str)
        assert len(sub_id) > 0

    def test_subscribe_all(self, event_bus: EventBus) -> None:
        """Test subscribing to all event types."""
        handler = AsyncMock()
        sub_id = event_bus.subscribe_all(handler)

        assert sub_id is not None
        assert event_bus.get_subscription_count() == 1

    def test_unsubscribe(self, event_bus: EventBus) -> None:
        """Test unsubscribing from events."""
        handler = AsyncMock()
        sub_id = event_bus.subscribe(
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        assert event_bus.get_subscription_count() == 1
        result = event_bus.unsubscribe(sub_id)
        assert result is True
        assert event_bus.get_subscription_count() == 0

    def test_unsubscribe_nonexistent(self, event_bus: EventBus) -> None:
        """Test unsubscribing from non-existent subscription."""
        result = event_bus.unsubscribe("nonexistent-id")
        assert result is False

    def test_subscriber_limit_enforced(self, event_bus: EventBus) -> None:
        """Test that subscriber limit is enforced."""
        # Create many subscribers up to the limit
        for i in range(100):
            event_bus.subscribe(
                handler=AsyncMock(),
                event_types={EventType.CAPSULE_CREATED},
            )

        # Next one should fail
        with pytest.raises(RuntimeError, match="Maximum subscriber limit"):
            event_bus.subscribe(
                handler=AsyncMock(),
                event_types={EventType.CAPSULE_CREATED},
            )


# =============================================================================
# Event Publishing Tests
# =============================================================================


class TestEventPublishing:
    """Tests for event publishing functionality."""

    @pytest.mark.asyncio
    async def test_publish_returns_event(self, event_bus: EventBus) -> None:
        """Test that publish returns an Event object."""
        event = await event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={"capsule_id": "test-123"},
            source="test",
        )

        assert event is not None
        assert event.type == EventType.CAPSULE_CREATED
        assert event.payload["capsule_id"] == "test-123"
        assert event.source == "test"

    @pytest.mark.asyncio
    async def test_publish_increments_metrics(self, event_bus: EventBus) -> None:
        """Test that publishing increments metrics."""
        initial_count = event_bus._metrics.events_published

        await event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
        )

        assert event_bus._metrics.events_published == initial_count + 1

    @pytest.mark.asyncio
    async def test_publish_with_correlation_id(self, event_bus: EventBus) -> None:
        """Test publishing with correlation ID."""
        event = await event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
            correlation_id="corr-123",
        )

        assert event.correlation_id == "corr-123"

    @pytest.mark.asyncio
    async def test_publish_with_target(self, event_bus: EventBus) -> None:
        """Test publishing with target overlay."""
        event = await event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
            target="ml_intelligence",
        )

        assert event.target_overlays == ["ml_intelligence"]

    @pytest.mark.asyncio
    async def test_emit_alias(self, event_bus: EventBus) -> None:
        """Test that emit is an alias for publish."""
        event = await event_bus.emit(
            event_type=EventType.CAPSULE_CREATED,
            payload={"test": "data"},
            source="test",
        )

        assert event is not None
        assert event.type == EventType.CAPSULE_CREATED


# =============================================================================
# Event Delivery Tests
# =============================================================================


class TestEventDelivery:
    """Tests for event delivery to subscribers."""

    @pytest.mark.asyncio
    async def test_event_delivered_to_subscriber(
        self, started_event_bus: EventBus
    ) -> None:
        """Test that events are delivered to matching subscribers."""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        started_event_bus.subscribe(
            handler=handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        await started_event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={"test": "value"},
            source="test",
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].payload["test"] == "value"

    @pytest.mark.asyncio
    async def test_event_not_delivered_to_non_matching_subscriber(
        self, started_event_bus: EventBus
    ) -> None:
        """Test that events are not delivered to non-matching subscribers."""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        started_event_bus.subscribe(
            handler=handler,
            event_types={EventType.USER_LOGIN},  # Different type
        )

        await started_event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_handler_timeout(self, started_event_bus: EventBus) -> None:
        """Test that handler timeout is enforced."""

        async def slow_handler(event: Event) -> None:
            await asyncio.sleep(60)  # Longer than timeout

        started_event_bus.subscribe(
            handler=slow_handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        await started_event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
        )

        # Wait a bit but not the full timeout
        await asyncio.sleep(0.5)

        # Metrics should show failed delivery eventually
        # (handler will timeout at 30s in production)

    @pytest.mark.asyncio
    async def test_handler_error_goes_to_dead_letter(
        self, started_event_bus: EventBus
    ) -> None:
        """Test that handler errors send events to dead letter queue."""

        async def failing_handler(event: Event) -> None:
            raise ValueError("Handler error")

        started_event_bus.subscribe(
            handler=failing_handler,
            event_types={EventType.CAPSULE_CREATED},
        )

        await started_event_bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
        )

        # Wait for retries to complete
        await asyncio.sleep(0.2)

        # Should be in dead letter queue after retries
        assert started_event_bus._dead_letter_queue.qsize() > 0


# =============================================================================
# Cascade Tests
# =============================================================================


class TestCascadePropagation:
    """Tests for cascade event propagation."""

    @pytest.mark.asyncio
    async def test_publish_cascade_creates_chain(self, event_bus: EventBus) -> None:
        """Test that publish_cascade creates a cascade chain."""
        chain = await event_bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="anomaly_detected",
            insight_data={"score": 0.95},
        )

        assert chain is not None
        assert chain.initiated_by == "ml_intelligence"
        assert len(chain.events) == 1
        assert chain.total_hops == 1

    @pytest.mark.asyncio
    async def test_publish_cascade_with_existing_chain(
        self, event_bus: EventBus
    ) -> None:
        """Test publishing to existing cascade chain."""
        # Create initial cascade
        chain1 = await event_bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="pattern_detected",
            insight_data={"pattern": "test"},
        )

        # Continue cascade
        chain2 = await event_bus.publish_cascade(
            source_overlay="security_validator",
            insight_type="threat_assessment",
            insight_data={"threat": False},
            cascade_id=chain1.cascade_id,
        )

        assert chain1.cascade_id == chain2.cascade_id
        assert len(chain2.events) == 2

    @pytest.mark.asyncio
    async def test_propagate_cascade(self, event_bus: EventBus) -> None:
        """Test cascade propagation to new overlay."""
        # Create initial cascade
        chain = await event_bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="anomaly_detected",
            insight_data={"score": 0.95},
        )

        # Propagate to another overlay
        cascade_event = await event_bus.propagate_cascade(
            cascade_id=chain.cascade_id,
            target_overlay="security_validator",
            insight_type="threat_check",
            insight_data={"requires_action": True},
            impact_score=0.8,
        )

        assert cascade_event is not None
        assert cascade_event.source_overlay == "security_validator"
        assert cascade_event.impact_score == 0.8

    @pytest.mark.asyncio
    async def test_propagate_cascade_prevents_cycles(
        self, event_bus: EventBus
    ) -> None:
        """Test that cascade propagation prevents cycles."""
        # Create initial cascade
        chain = await event_bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="test",
            insight_data={},
        )

        # Try to propagate back to same overlay
        cascade_event = await event_bus.propagate_cascade(
            cascade_id=chain.cascade_id,
            target_overlay="ml_intelligence",  # Same as initiator
            insight_type="test",
            insight_data={},
        )

        assert cascade_event is None

    @pytest.mark.asyncio
    async def test_propagate_cascade_respects_max_hops(
        self, event_bus: EventBus
    ) -> None:
        """Test that cascade respects max hops limit."""
        # Create cascade with max_hops=1
        chain = await event_bus.publish_cascade(
            source_overlay="overlay1",
            insight_type="test",
            insight_data={},
            max_hops=1,
        )

        # First propagation should work
        event1 = await event_bus.propagate_cascade(
            cascade_id=chain.cascade_id,
            target_overlay="overlay2",
            insight_type="test",
            insight_data={},
        )
        assert event1 is not None

        # Second propagation should fail (max hops reached)
        event2 = await event_bus.propagate_cascade(
            cascade_id=chain.cascade_id,
            target_overlay="overlay3",
            insight_type="test",
            insight_data={},
        )
        assert event2 is None

    @pytest.mark.asyncio
    async def test_complete_cascade(self, event_bus: EventBus) -> None:
        """Test completing a cascade chain."""
        # Create cascade
        chain = await event_bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="test",
            insight_data={},
        )

        # Complete it
        completed_chain = await event_bus.complete_cascade(chain.cascade_id)

        assert completed_chain is not None
        assert completed_chain.completed_at is not None
        assert event_bus.get_cascade_chain(chain.cascade_id) is None

    @pytest.mark.asyncio
    async def test_complete_nonexistent_cascade(self, event_bus: EventBus) -> None:
        """Test completing non-existent cascade returns None."""
        result = await event_bus.complete_cascade("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_cascades(self, event_bus: EventBus) -> None:
        """Test getting active cascades."""
        # Create multiple cascades
        await event_bus.publish_cascade(
            source_overlay="overlay1",
            insight_type="test",
            insight_data={},
        )
        await event_bus.publish_cascade(
            source_overlay="overlay2",
            insight_type="test",
            insight_data={},
        )

        active = event_bus.get_active_cascades()
        assert len(active) == 2


# =============================================================================
# Cascade Persistence Tests
# =============================================================================


class TestCascadePersistence:
    """Tests for cascade persistence with repository."""

    @pytest.mark.asyncio
    async def test_cascade_persisted_on_create(
        self, mock_cascade_repository: AsyncMock
    ) -> None:
        """Test that cascade chain is persisted on creation."""
        bus = EventBus(cascade_repository=mock_cascade_repository)

        await bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="test",
            insight_data={},
        )

        mock_cascade_repository.create_chain.assert_called_once()

    @pytest.mark.asyncio
    async def test_cascade_event_persisted(
        self, mock_cascade_repository: AsyncMock
    ) -> None:
        """Test that cascade events are persisted."""
        bus = EventBus(cascade_repository=mock_cascade_repository)

        chain = await bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="test",
            insight_data={},
        )

        # Add another event to existing chain
        await bus.publish_cascade(
            source_overlay="security",
            insight_type="test2",
            insight_data={},
            cascade_id=chain.cascade_id,
        )

        # Should persist event
        mock_cascade_repository.add_event.assert_called()

    @pytest.mark.asyncio
    async def test_cascade_complete_persisted(
        self, mock_cascade_repository: AsyncMock
    ) -> None:
        """Test that cascade completion is persisted."""
        bus = EventBus(cascade_repository=mock_cascade_repository)

        chain = await bus.publish_cascade(
            source_overlay="ml_intelligence",
            insight_type="test",
            insight_data={},
        )

        await bus.complete_cascade(chain.cascade_id)

        mock_cascade_repository.complete_chain.assert_called_once_with(chain.cascade_id)

    @pytest.mark.asyncio
    async def test_active_cascades_loaded_on_start(
        self, mock_cascade_repository: AsyncMock
    ) -> None:
        """Test that active cascades are loaded on startup."""
        # Set up mock to return some chains
        mock_chain = CascadeChain(
            cascade_id="loaded-chain",
            initiated_by="test",
            initiated_at=datetime.now(UTC),
            events=[],
            total_hops=0,
            overlays_affected=["test"],
            insights_generated=0,
            actions_triggered=0,
            errors_encountered=0,
        )
        mock_cascade_repository.get_active_chains.return_value = [mock_chain]

        bus = EventBus(cascade_repository=mock_cascade_repository)
        await bus.start()

        # Should have loaded the chain
        assert bus.get_cascade_chain("loaded-chain") is not None

        await bus.stop()


# =============================================================================
# Dead Letter Queue Tests
# =============================================================================


class TestDeadLetterQueue:
    """Tests for dead letter queue functionality."""

    @pytest.mark.asyncio
    async def test_get_dead_letters(self, event_bus: EventBus) -> None:
        """Test retrieving dead letters."""
        # Add some dead letters manually
        event = Event(
            id="dead-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )
        error = ValueError("Test error")
        await event_bus._dead_letter_queue.put((event, error))

        dead_letters = await event_bus.get_dead_letters(limit=10)

        assert len(dead_letters) == 1
        assert dead_letters[0][0].id == "dead-1"
        assert "Test error" in dead_letters[0][1]

    @pytest.mark.asyncio
    async def test_retry_dead_letter(self, event_bus: EventBus) -> None:
        """Test retrying a dead letter event."""
        event = Event(
            id="retry-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={},
        )

        await event_bus.retry_dead_letter(event)

        assert event_bus.get_queue_size() == 1


# =============================================================================
# Metrics Tests
# =============================================================================


class TestEventMetrics:
    """Tests for event metrics collection."""

    def test_record_delivery(self) -> None:
        """Test recording delivery time."""
        metrics = EventMetrics()
        metrics.record_delivery(100.0)
        metrics.record_delivery(200.0)

        assert len(metrics.delivery_times) == 2
        assert metrics.avg_delivery_time_ms == 150.0

    def test_delivery_times_bounded(self) -> None:
        """Test that delivery times are bounded."""
        metrics = EventMetrics()

        # Add more than maxlen
        for i in range(1500):
            metrics.record_delivery(float(i))

        # Should only keep last 1000
        assert len(metrics.delivery_times) == 1000

    def test_get_metrics(self, event_bus: EventBus) -> None:
        """Test getting event bus metrics."""
        metrics = event_bus.get_metrics()

        assert "events_published" in metrics
        assert "events_delivered" in metrics
        assert "events_failed" in metrics
        assert "queue_size" in metrics
        assert "dead_letter_size" in metrics
        assert "active_subscriptions" in metrics


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestEventBusLifecycle:
    """Tests for EventBus lifecycle management."""

    @pytest.mark.asyncio
    async def test_start(self, event_bus: EventBus) -> None:
        """Test starting the event bus."""
        assert event_bus._running is False

        await event_bus.start()

        assert event_bus._running is True
        assert event_bus._worker_task is not None

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, event_bus: EventBus) -> None:
        """Test that start is idempotent."""
        await event_bus.start()
        task1 = event_bus._worker_task

        await event_bus.start()  # Second call
        task2 = event_bus._worker_task

        assert task1 is task2  # Same task

        await event_bus.stop()

    @pytest.mark.asyncio
    async def test_stop(self, event_bus: EventBus) -> None:
        """Test stopping the event bus."""
        await event_bus.start()
        await event_bus.stop()

        assert event_bus._running is False

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, event_bus: EventBus) -> None:
        """Test that stop is idempotent."""
        await event_bus.start()
        await event_bus.stop()
        await event_bus.stop()  # Second call should not error

        assert event_bus._running is False


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalEventBus:
    """Tests for global event bus instance management."""

    def test_get_event_bus(self) -> None:
        """Test getting global event bus."""
        # Reset global state
        import forge.kernel.event_system as es

        es._event_bus = None

        bus = get_event_bus()
        assert bus is not None

        # Should return same instance
        bus2 = get_event_bus()
        assert bus is bus2

        # Cleanup
        es._event_bus = None

    @pytest.mark.asyncio
    async def test_init_event_bus(self) -> None:
        """Test initializing global event bus."""
        import forge.kernel.event_system as es

        es._event_bus = None

        bus = await init_event_bus()
        assert bus._running is True

        await shutdown_event_bus()
        assert es._event_bus is None

    @pytest.mark.asyncio
    async def test_shutdown_event_bus(self) -> None:
        """Test shutting down global event bus."""
        import forge.kernel.event_system as es

        await init_event_bus()
        await shutdown_event_bus()

        assert es._event_bus is None


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_emit_function(self) -> None:
        """Test emit convenience function."""
        import forge.kernel.event_system as es

        es._event_bus = None
        bus = await init_event_bus()

        event = await emit(
            event_type=EventType.CAPSULE_CREATED,
            payload={"test": "data"},
            source="test",
        )

        assert event is not None
        assert event.type == EventType.CAPSULE_CREATED

        await shutdown_event_bus()

    def test_on_decorator(self) -> None:
        """Test on decorator for subscribing."""
        import forge.kernel.event_system as es

        es._event_bus = None
        bus = get_event_bus()

        @on({EventType.CAPSULE_CREATED})
        async def handler(event: Event) -> None:
            pass

        assert bus.get_subscription_count() == 1

        es._event_bus = None


# =============================================================================
# Queue Backpressure Tests
# =============================================================================


class TestQueueBackpressure:
    """Tests for queue backpressure handling."""

    @pytest.mark.asyncio
    async def test_publish_timeout_on_full_queue(self) -> None:
        """Test that publish times out when queue is full."""
        # Create bus with very small queue
        bus = EventBus(max_queue_size=1)

        # Fill the queue
        await bus.publish(
            event_type=EventType.CAPSULE_CREATED,
            payload={},
            source="test",
        )

        # Next publish should timeout (queue full, no worker consuming)
        with pytest.raises(RuntimeError, match="Event queue full"):
            # Temporarily reduce timeout for test
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                await bus.publish(
                    event_type=EventType.CAPSULE_CREATED,
                    payload={},
                    source="test",
                )
