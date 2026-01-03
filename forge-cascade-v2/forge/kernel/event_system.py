"""
Event System for Forge Cascade V2

Async pub/sub event system for cascade effect propagation,
overlay coordination, and real-time updates.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional, Set
from uuid import uuid4
import structlog

from ..models.events import Event, EventType, EventPriority, CascadeEvent, CascadeChain
from ..models.base import TrustLevel

logger = structlog.get_logger()


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


@dataclass
class Subscription:
    """Represents an event subscription."""
    id: str
    handler: EventHandler
    event_types: Set[EventType]
    min_priority: EventPriority = EventPriority.LOW
    filter_func: Optional[Callable[[Event], bool]] = None
    
    def matches(self, event: Event) -> bool:
        """Check if this subscription matches an event."""
        # Check event type
        if event.event_type not in self.event_types:
            return False
        
        # Check priority
        if event.priority.value < self.min_priority.value:
            return False
        
        # Apply custom filter if present
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True


@dataclass
class EventMetrics:
    """Metrics for event system monitoring."""
    events_published: int = 0
    events_delivered: int = 0
    events_failed: int = 0
    cascade_chains: int = 0
    avg_delivery_time_ms: float = 0.0
    delivery_times: list = field(default_factory=list)
    
    def record_delivery(self, duration_ms: float):
        """Record a delivery time."""
        self.delivery_times.append(duration_ms)
        # Keep only last 1000 samples
        if len(self.delivery_times) > 1000:
            self.delivery_times = self.delivery_times[-1000:]
        self.avg_delivery_time_ms = sum(self.delivery_times) / len(self.delivery_times)


class EventBus:
    """
    Async event bus for pub/sub messaging.
    
    Features:
    - Multiple event types
    - Priority-based filtering
    - Cascade propagation
    - Dead letter queue for failed events
    - Metrics collection
    """
    
    def __init__(
        self,
        max_queue_size: int = 10000,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0
    ):
        self._subscriptions: dict[str, Subscription] = {}
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._dead_letter_queue: asyncio.Queue[tuple[Event, Exception]] = asyncio.Queue()
        self._cascade_chains: dict[str, CascadeChain] = {}
        self._metrics = EventMetrics()
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        # Event type index for faster lookups
        self._type_index: dict[EventType, Set[str]] = defaultdict(set)
    
    # =========================================================================
    # Subscription Management
    # =========================================================================
    
    def subscribe(
        self,
        handler: EventHandler,
        event_types: Set[EventType],
        min_priority: EventPriority = EventPriority.LOW,
        filter_func: Optional[Callable[[Event], bool]] = None
    ) -> str:
        """
        Subscribe to events.
        
        Args:
            handler: Async function to handle events
            event_types: Set of event types to subscribe to
            min_priority: Minimum priority to receive
            filter_func: Optional additional filter
            
        Returns:
            Subscription ID for unsubscribing
        """
        sub_id = str(uuid4())
        
        subscription = Subscription(
            id=sub_id,
            handler=handler,
            event_types=event_types,
            min_priority=min_priority,
            filter_func=filter_func
        )
        
        self._subscriptions[sub_id] = subscription
        
        # Update type index
        for event_type in event_types:
            self._type_index[event_type].add(sub_id)
        
        logger.info(
            "event_subscription_created",
            subscription_id=sub_id,
            event_types=[et.value for et in event_types]
        )
        
        return sub_id
    
    def subscribe_all(
        self,
        handler: EventHandler,
        min_priority: EventPriority = EventPriority.NORMAL
    ) -> str:
        """Subscribe to all event types."""
        return self.subscribe(
            handler=handler,
            event_types=set(EventType),
            min_priority=min_priority
        )
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if unsubscribed, False if not found
        """
        if subscription_id not in self._subscriptions:
            return False
        
        subscription = self._subscriptions.pop(subscription_id)
        
        # Remove from type index
        for event_type in subscription.event_types:
            self._type_index[event_type].discard(subscription_id)
        
        logger.info("event_subscription_removed", subscription_id=subscription_id)
        return True
    
    # =========================================================================
    # Event Publishing
    # =========================================================================
    
    async def publish(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        source: str,
        priority: EventPriority = EventPriority.NORMAL,
        target: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None
    ) -> Event:
        """
        Publish an event.
        
        Args:
            event_type: Type of event
            payload: Event data
            source: Source identifier (e.g., "overlay:ml_intelligence")
            priority: Event priority
            target: Optional specific target
            correlation_id: For linking related events
            metadata: Additional metadata
            
        Returns:
            Created Event
        """
        event = Event(
            id=str(uuid4()),
            event_type=event_type,
            payload=payload,
            source=source,
            priority=priority,
            target=target,
            correlation_id=correlation_id or str(uuid4()),
            metadata=metadata or {},
            timestamp=datetime.utcnow()
        )
        
        await self._event_queue.put(event)
        self._metrics.events_published += 1
        
        logger.debug(
            "event_published",
            event_id=event.id,
            event_type=event_type.value,
            source=source,
            priority=priority.value
        )
        
        return event
    
    async def publish_cascade(
        self,
        initial_event_type: EventType,
        payload: dict[str, Any],
        source: str,
        chain_id: Optional[str] = None
    ) -> CascadeChain:
        """
        Publish an event that initiates a cascade chain.
        
        Cascade chains allow tracking of events that trigger other events.
        
        Args:
            initial_event_type: Type of triggering event
            payload: Event data
            source: Source identifier
            chain_id: Optional existing chain ID to continue
            
        Returns:
            CascadeChain tracking the propagation
        """
        chain_id = chain_id or str(uuid4())
        
        # Create or get existing chain
        if chain_id not in self._cascade_chains:
            self._cascade_chains[chain_id] = CascadeChain(
                id=chain_id,
                root_event_id="",  # Will be set below
                events=[],
                started_at=datetime.utcnow()
            )
            self._metrics.cascade_chains += 1
        
        chain = self._cascade_chains[chain_id]
        
        # Create cascade event
        cascade_event = CascadeEvent(
            id=str(uuid4()),
            event_type=initial_event_type,
            payload=payload,
            source=source,
            chain_id=chain_id,
            depth=len(chain.events),
            parent_event_id=chain.events[-1].id if chain.events else None,
            timestamp=datetime.utcnow()
        )
        
        # Update chain
        if not chain.root_event_id:
            chain.root_event_id = cascade_event.id
        chain.events.append(cascade_event)
        
        # Publish as regular event
        await self.publish(
            event_type=initial_event_type,
            payload={**payload, "_cascade_chain_id": chain_id, "_cascade_depth": cascade_event.depth},
            source=source,
            priority=EventPriority.HIGH,
            correlation_id=chain_id
        )
        
        return chain
    
    async def complete_cascade(self, chain_id: str) -> Optional[CascadeChain]:
        """
        Mark a cascade chain as complete.
        
        Args:
            chain_id: ID of the cascade chain
            
        Returns:
            Completed CascadeChain or None if not found
        """
        if chain_id not in self._cascade_chains:
            return None
        
        chain = self._cascade_chains.pop(chain_id)
        chain.completed_at = datetime.utcnow()
        chain.total_events = len(chain.events)
        
        logger.info(
            "cascade_completed",
            chain_id=chain_id,
            total_events=chain.total_events,
            duration_ms=(chain.completed_at - chain.started_at).total_seconds() * 1000
        )
        
        return chain
    
    # =========================================================================
    # Event Processing
    # =========================================================================
    
    async def _process_event(self, event: Event) -> None:
        """Process a single event by dispatching to matching subscribers."""
        start_time = asyncio.get_event_loop().time()
        
        # Find matching subscriptions using type index
        potential_subs = self._type_index.get(event.event_type, set())
        
        tasks = []
        for sub_id in potential_subs:
            subscription = self._subscriptions.get(sub_id)
            if subscription and subscription.matches(event):
                tasks.append(self._deliver_event(subscription, event))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self._metrics.events_failed += 1
                    logger.error("event_delivery_failed", event_id=event.id, error=str(result))
                else:
                    self._metrics.events_delivered += 1
        
        # Record metrics
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        self._metrics.record_delivery(duration_ms)
    
    async def _deliver_event(
        self,
        subscription: Subscription,
        event: Event,
        attempt: int = 1
    ) -> None:
        """Deliver event to a single subscriber with retry logic."""
        try:
            await asyncio.wait_for(
                subscription.handler(event),
                timeout=30.0  # 30 second timeout per handler
            )
        except asyncio.TimeoutError:
            logger.warning(
                "event_handler_timeout",
                subscription_id=subscription.id,
                event_id=event.id
            )
            raise
        except Exception as e:
            if attempt < self._max_retries:
                logger.warning(
                    "event_delivery_retry",
                    subscription_id=subscription.id,
                    event_id=event.id,
                    attempt=attempt,
                    error=str(e)
                )
                await asyncio.sleep(self._retry_delay * attempt)
                await self._deliver_event(subscription, event, attempt + 1)
            else:
                # Send to dead letter queue
                await self._dead_letter_queue.put((event, e))
                raise
    
    async def _worker(self) -> None:
        """Background worker that processes events from the queue."""
        logger.info("event_worker_started")
        
        while self._running:
            try:
                # Wait for event with timeout to allow checking _running
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                await self._process_event(event)
                self._event_queue.task_done()
                
            except Exception as e:
                logger.error("event_worker_error", error=str(e))
        
        logger.info("event_worker_stopped")
    
    # =========================================================================
    # Lifecycle Management
    # =========================================================================
    
    async def start(self) -> None:
        """Start the event bus worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("event_bus_started")
    
    async def stop(self, timeout: float = 10.0) -> None:
        """
        Stop the event bus gracefully.
        
        Args:
            timeout: Maximum time to wait for pending events
        """
        if not self._running:
            return
        
        self._running = False
        
        # Wait for queue to drain
        try:
            await asyncio.wait_for(
                self._event_queue.join(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("event_bus_stop_timeout", pending_events=self._event_queue.qsize())
        
        # Cancel worker
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("event_bus_stopped")
    
    # =========================================================================
    # Dead Letter Queue
    # =========================================================================
    
    async def get_dead_letters(
        self,
        limit: int = 100
    ) -> list[tuple[Event, str]]:
        """
        Get events from the dead letter queue.
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of (event, error_message) tuples
        """
        dead_letters = []
        
        while len(dead_letters) < limit and not self._dead_letter_queue.empty():
            event, error = await self._dead_letter_queue.get()
            dead_letters.append((event, str(error)))
        
        return dead_letters
    
    async def retry_dead_letter(self, event: Event) -> None:
        """Retry a dead letter event by re-publishing it."""
        await self._event_queue.put(event)
    
    # =========================================================================
    # Metrics & Monitoring
    # =========================================================================
    
    def get_metrics(self) -> dict[str, Any]:
        """Get event system metrics."""
        return {
            "events_published": self._metrics.events_published,
            "events_delivered": self._metrics.events_delivered,
            "events_failed": self._metrics.events_failed,
            "cascade_chains": self._metrics.cascade_chains,
            "avg_delivery_time_ms": round(self._metrics.avg_delivery_time_ms, 2),
            "queue_size": self._event_queue.qsize(),
            "dead_letter_size": self._dead_letter_queue.qsize(),
            "active_subscriptions": len(self._subscriptions),
            "active_cascades": len(self._cascade_chains)
        }
    
    def get_subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return len(self._subscriptions)
    
    def get_queue_size(self) -> int:
        """Get current event queue size."""
        return self._event_queue.qsize()


# =============================================================================
# Global Event Bus Instance
# =============================================================================

_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def init_event_bus() -> EventBus:
    """Initialize and start the global event bus."""
    bus = get_event_bus()
    await bus.start()
    return bus


async def shutdown_event_bus() -> None:
    """Shutdown the global event bus."""
    global _event_bus
    if _event_bus is not None:
        await _event_bus.stop()
        _event_bus = None


# =============================================================================
# Convenience Functions
# =============================================================================

async def emit(
    event_type: EventType,
    payload: dict[str, Any],
    source: str = "system",
    priority: EventPriority = EventPriority.NORMAL
) -> Event:
    """
    Convenience function to emit an event.
    
    Usage:
        await emit(EventType.CAPSULE_CREATED, {"capsule_id": "123"}, "api")
    """
    bus = get_event_bus()
    return await bus.publish(event_type, payload, source, priority)


def on(
    event_types: Set[EventType],
    min_priority: EventPriority = EventPriority.LOW
) -> Callable[[EventHandler], EventHandler]:
    """
    Decorator to subscribe a function to events.
    
    Usage:
        @on({EventType.CAPSULE_CREATED})
        async def handle_capsule_created(event: Event):
            print(f"Capsule created: {event.payload}")
    """
    def decorator(handler: EventHandler) -> EventHandler:
        bus = get_event_bus()
        bus.subscribe(handler, event_types, min_priority)
        return handler
    return decorator


# Alias for backward compatibility
EventSystem = EventBus
