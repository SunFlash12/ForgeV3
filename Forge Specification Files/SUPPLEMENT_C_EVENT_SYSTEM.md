# Forge V3 - Supplement: Event System

**Purpose:** Complete event-driven architecture with Kafka for audit trails, cross-service communication, and event sourcing.

**New files to create:**
- `forge/models/events.py`
- `forge/infrastructure/kafka/producer.py`
- `forge/infrastructure/kafka/consumer.py`
- `forge/core/events/service.py`

---

## 1. Event Models

```python
# forge/models/events.py
"""
Event models for the event-driven architecture.

All significant actions in Forge emit events for:
- Audit trail (immutable log of all changes)
- Cross-service communication
- External integrations
- Event sourcing reconstruction
"""
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4
from typing import Any
from pydantic import Field

from forge.models.base import ForgeBaseModel


class EventType(str, Enum):
    """Categories of events in the system."""
    
    # Capsule events
    CAPSULE_CREATED = "capsule.created"
    CAPSULE_UPDATED = "capsule.updated"
    CAPSULE_DELETED = "capsule.deleted"
    CAPSULE_SEARCHED = "capsule.searched"
    
    # User events
    USER_REGISTERED = "user.registered"
    USER_AUTHENTICATED = "user.authenticated"
    USER_LOGOUT = "user.logout"
    USER_TRUST_CHANGED = "user.trust_changed"
    USER_ANONYMIZED = "user.anonymized"
    
    # Governance events
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_ACTIVATED = "proposal.activated"
    PROPOSAL_CLOSED = "proposal.closed"
    PROPOSAL_EXECUTED = "proposal.executed"
    VOTE_CAST = "vote.cast"
    VOTE_UPDATED = "vote.updated"
    
    # Overlay events
    OVERLAY_REGISTERED = "overlay.registered"
    OVERLAY_ACTIVATED = "overlay.activated"
    OVERLAY_INVOKED = "overlay.invoked"
    OVERLAY_QUARANTINED = "overlay.quarantined"
    
    # System events
    IMMUNE_RESPONSE = "system.immune_response"
    CONFIG_CHANGED = "system.config_changed"
    ERROR_OCCURRED = "system.error"


class Event(ForgeBaseModel):
    """
    Base event model.
    
    All events are immutable once created. They form the
    authoritative audit trail of the system.
    """
    
    id: UUID = Field(default_factory=uuid4, description="Unique event ID")
    type: EventType = Field(..., description="Event type/category")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the event occurred (UTC)"
    )
    
    # Actor information
    actor_id: UUID | None = Field(
        default=None,
        description="User ID who triggered the event (null for system events)"
    )
    actor_type: str = Field(
        default="user",
        description="Type of actor: user, system, overlay"
    )
    
    # Resource information
    resource_type: str | None = Field(
        default=None,
        description="Type of resource affected: capsule, user, proposal, etc."
    )
    resource_id: UUID | None = Field(
        default=None,
        description="ID of the affected resource"
    )
    
    # Event data
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific payload data"
    )
    
    # Metadata
    correlation_id: UUID | None = Field(
        default=None,
        description="ID linking related events in a transaction"
    )
    causation_id: UUID | None = Field(
        default=None,
        description="ID of the event that caused this event"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (IP, user agent, etc.)"
    )
    
    # Version for schema evolution
    schema_version: int = Field(
        default=1,
        description="Event schema version for backward compatibility"
    )


# =============================================================================
# SPECIFIC EVENT TYPES
# =============================================================================

class CapsuleCreatedEvent(Event):
    """Event emitted when a capsule is created."""
    type: EventType = EventType.CAPSULE_CREATED
    resource_type: str = "capsule"
    
    @classmethod
    def create(
        cls,
        capsule_id: UUID,
        owner_id: UUID,
        capsule_type: str,
        parent_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> "CapsuleCreatedEvent":
        return cls(
            actor_id=owner_id,
            resource_id=capsule_id,
            correlation_id=correlation_id,
            data={
                "capsule_type": capsule_type,
                "parent_id": str(parent_id) if parent_id else None,
            }
        )


class CapsuleUpdatedEvent(Event):
    """Event emitted when a capsule is updated."""
    type: EventType = EventType.CAPSULE_UPDATED
    resource_type: str = "capsule"
    
    @classmethod
    def create(
        cls,
        capsule_id: UUID,
        actor_id: UUID,
        old_version: str,
        new_version: str,
        fields_changed: list[str],
        correlation_id: UUID | None = None,
    ) -> "CapsuleUpdatedEvent":
        return cls(
            actor_id=actor_id,
            resource_id=capsule_id,
            correlation_id=correlation_id,
            data={
                "old_version": old_version,
                "new_version": new_version,
                "fields_changed": fields_changed,
            }
        )


class UserAuthenticatedEvent(Event):
    """Event emitted on successful authentication."""
    type: EventType = EventType.USER_AUTHENTICATED
    resource_type: str = "user"
    
    @classmethod
    def create(
        cls,
        user_id: UUID,
        ip_address: str,
        user_agent: str | None = None,
    ) -> "UserAuthenticatedEvent":
        return cls(
            actor_id=user_id,
            resource_id=user_id,
            data={
                "ip_address": ip_address,
            },
            metadata={
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        )


class ProposalCreatedEvent(Event):
    """Event emitted when a governance proposal is created."""
    type: EventType = EventType.PROPOSAL_CREATED
    resource_type: str = "proposal"
    
    @classmethod
    def create(
        cls,
        proposal_id: UUID,
        proposer_id: UUID,
        proposal_type: str,
        title: str,
    ) -> "ProposalCreatedEvent":
        return cls(
            actor_id=proposer_id,
            resource_id=proposal_id,
            data={
                "proposal_type": proposal_type,
                "title": title,
            }
        )


class VoteCastEvent(Event):
    """Event emitted when a vote is cast."""
    type: EventType = EventType.VOTE_CAST
    resource_type: str = "vote"
    
    @classmethod
    def create(
        cls,
        vote_id: UUID,
        proposal_id: UUID,
        voter_id: UUID,
        decision: str,
        weight: float,
    ) -> "VoteCastEvent":
        return cls(
            actor_id=voter_id,
            resource_id=vote_id,
            data={
                "proposal_id": str(proposal_id),
                "decision": decision,
                "weight": weight,
            }
        )


class ImmuneResponseEvent(Event):
    """Event emitted when the immune system takes action."""
    type: EventType = EventType.IMMUNE_RESPONSE
    actor_type: str = "system"
    
    @classmethod
    def create(
        cls,
        target_type: str,
        target_id: UUID,
        threat_type: str,
        threat_level: str,
        action_taken: str,
        reason: str,
    ) -> "ImmuneResponseEvent":
        return cls(
            resource_type=target_type,
            resource_id=target_id,
            data={
                "threat_type": threat_type,
                "threat_level": threat_level,
                "action_taken": action_taken,
                "reason": reason,
            }
        )
```

---

## 2. Kafka Producer

```python
# forge/infrastructure/kafka/producer.py
"""
Kafka producer for publishing events.

Events are published to topic-per-event-type for easy consumption
by specific subscribers.
"""
import json
from typing import Any
from uuid import UUID

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from forge.config import get_settings
from forge.models.events import Event, EventType
from forge.logging import get_logger

logger = get_logger(__name__)


class EventJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for event serialization."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        if hasattr(obj, "isoformat"):  # datetime
            return obj.isoformat()
        if hasattr(obj, "value"):  # Enum
            return obj.value
        return super().default(obj)


class KafkaEventProducer:
    """
    Async Kafka producer for events.
    
    Events are:
    - Serialized to JSON
    - Published to topic named after event type (e.g., "forge.capsule.created")
    - Keyed by resource_id for partition locality
    """
    
    TOPIC_PREFIX = "forge"
    
    def __init__(self, bootstrap_servers: str | None = None):
        settings = get_settings()
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._producer: AIOKafkaProducer | None = None
    
    async def start(self) -> None:
        """Start the producer."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, cls=EventJSONEncoder).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            # Ensure messages are durably stored
            acks="all",
            # Retry transient failures
            retries=3,
            # Compress large batches
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info("kafka_producer_started")
    
    async def stop(self) -> None:
        """Stop the producer and flush pending messages."""
        if self._producer:
            await self._producer.stop()
            logger.info("kafka_producer_stopped")
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to Kafka.
        
        The event is published to a topic derived from its type.
        The key is the resource_id for partition consistency.
        """
        if not self._producer:
            raise RuntimeError("Producer not started")
        
        topic = self._get_topic(event.type)
        key = str(event.resource_id) if event.resource_id else None
        value = event.model_dump()
        
        try:
            # Send and wait for acknowledgment
            await self._producer.send_and_wait(
                topic=topic,
                key=key,
                value=value,
            )
            
            logger.debug(
                "event_published",
                event_type=event.type.value,
                event_id=str(event.id),
                topic=topic,
            )
            
        except KafkaError as e:
            logger.error(
                "event_publish_failed",
                event_type=event.type.value,
                event_id=str(event.id),
                error=str(e),
            )
            raise
    
    async def publish_batch(self, events: list[Event]) -> None:
        """
        Publish multiple events efficiently.
        
        Uses batching for better throughput.
        """
        if not self._producer:
            raise RuntimeError("Producer not started")
        
        # Send all without waiting
        futures = []
        for event in events:
            topic = self._get_topic(event.type)
            key = str(event.resource_id) if event.resource_id else None
            value = event.model_dump()
            
            future = await self._producer.send(
                topic=topic,
                key=key,
                value=value,
            )
            futures.append((event, future))
        
        # Wait for all to complete
        for event, future in futures:
            try:
                await future
            except KafkaError as e:
                logger.error(
                    "event_batch_publish_failed",
                    event_id=str(event.id),
                    error=str(e),
                )
        
        logger.debug("event_batch_published", count=len(events))
    
    def _get_topic(self, event_type: EventType) -> str:
        """Get topic name for an event type."""
        # e.g., EventType.CAPSULE_CREATED -> "forge.capsule.created"
        return f"{self.TOPIC_PREFIX}.{event_type.value}"


# Singleton instance
_producer: KafkaEventProducer | None = None


async def get_event_producer() -> KafkaEventProducer:
    """Get or create the singleton producer."""
    global _producer
    if _producer is None:
        _producer = KafkaEventProducer()
        await _producer.start()
    return _producer


async def shutdown_event_producer() -> None:
    """Shutdown the producer on application exit."""
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
```

---

## 3. Kafka Consumer

```python
# forge/infrastructure/kafka/consumer.py
"""
Kafka consumer for processing events.

Consumers subscribe to topics and process events with handlers.
Supports consumer groups for horizontal scaling.
"""
import asyncio
import json
from typing import Callable, Awaitable, Any
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from forge.config import get_settings
from forge.models.events import Event, EventType
from forge.logging import get_logger

logger = get_logger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


class KafkaEventConsumer:
    """
    Async Kafka consumer for processing events.
    
    Supports:
    - Multiple topic subscriptions
    - Handler registration per event type
    - Consumer group for distributed processing
    - Automatic offset commits after processing
    """
    
    TOPIC_PREFIX = "forge"
    
    def __init__(
        self,
        group_id: str,
        bootstrap_servers: str | None = None,
    ):
        settings = get_settings()
        self._bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._running = False
    
    def register_handler(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """
        Register a handler for an event type.
        
        Multiple handlers can be registered for the same event type.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("handler_registered", event_type=event_type.value)
    
    async def start(self, event_types: list[EventType]) -> None:
        """
        Start consuming events of the specified types.
        
        Subscribes to topics for each event type.
        """
        topics = [f"{self.TOPIC_PREFIX}.{et.value}" for et in event_types]
        
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode()),
            # Start from earliest unprocessed message
            auto_offset_reset="earliest",
            # Commit offsets after processing
            enable_auto_commit=False,
        )
        
        await self._consumer.start()
        self._running = True
        logger.info(
            "kafka_consumer_started",
            group_id=self._group_id,
            topics=topics,
        )
    
    async def stop(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("kafka_consumer_stopped")
    
    async def run(self) -> None:
        """
        Main consumption loop.
        
        Processes messages and calls registered handlers.
        Commits offsets after successful processing.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started")
        
        try:
            async for message in self._consumer:
                if not self._running:
                    break
                
                try:
                    # Parse event from message
                    event_data = message.value
                    event_type = EventType(event_data["type"])
                    
                    # Reconstruct Event object
                    event = Event(**event_data)
                    
                    # Call all registered handlers
                    handlers = self._handlers.get(event_type, [])
                    for handler in handlers:
                        try:
                            await handler(event)
                        except Exception as e:
                            logger.error(
                                "event_handler_error",
                                event_type=event_type.value,
                                event_id=str(event.id),
                                handler=handler.__name__,
                                error=str(e),
                            )
                    
                    # Commit offset after successful processing
                    await self._consumer.commit()
                    
                    logger.debug(
                        "event_processed",
                        event_type=event_type.value,
                        event_id=str(event.id),
                    )
                    
                except Exception as e:
                    logger.error(
                        "event_processing_error",
                        error=str(e),
                        message=str(message.value)[:200],
                    )
                    
        except asyncio.CancelledError:
            logger.info("consumer_loop_cancelled")
        except KafkaError as e:
            logger.error("kafka_consumer_error", error=str(e))
            raise


# Example usage of the consumer
async def run_event_processor():
    """Example of setting up and running an event processor."""
    
    # Create consumer for audit logging
    consumer = KafkaEventConsumer(group_id="audit-logger")
    
    # Register handlers
    async def log_capsule_created(event: Event):
        logger.info(
            "audit_capsule_created",
            capsule_id=str(event.resource_id),
            owner_id=str(event.actor_id),
        )
    
    async def log_user_authenticated(event: Event):
        logger.info(
            "audit_user_authenticated",
            user_id=str(event.actor_id),
            ip=event.metadata.get("ip_address"),
        )
    
    consumer.register_handler(EventType.CAPSULE_CREATED, log_capsule_created)
    consumer.register_handler(EventType.USER_AUTHENTICATED, log_user_authenticated)
    
    # Start consuming
    await consumer.start([
        EventType.CAPSULE_CREATED,
        EventType.USER_AUTHENTICATED,
    ])
    
    # Run until stopped
    await consumer.run()
```

---

## 4. Event Service

```python
# forge/core/events/service.py
"""
Event service for centralized event publishing.

All services use this to emit events, ensuring consistency
and making it easy to add cross-cutting concerns.
"""
from uuid import UUID
from typing import Any

from forge.infrastructure.kafka.producer import get_event_producer, KafkaEventProducer
from forge.models.events import (
    Event,
    EventType,
    CapsuleCreatedEvent,
    CapsuleUpdatedEvent,
    UserAuthenticatedEvent,
    ProposalCreatedEvent,
    VoteCastEvent,
    ImmuneResponseEvent,
)
from forge.logging import get_logger

logger = get_logger(__name__)


class EventService:
    """
    Centralized event publishing service.
    
    Provides typed methods for common events and handles
    the producer lifecycle.
    """
    
    def __init__(self, producer: KafkaEventProducer | None = None):
        self._producer = producer
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the event service."""
        if not self._initialized:
            self._producer = await get_event_producer()
            self._initialized = True
    
    async def publish(self, event: Event) -> None:
        """Publish any event."""
        if not self._producer:
            await self.initialize()
        await self._producer.publish(event)
    
    # =========================================================================
    # CAPSULE EVENTS
    # =========================================================================
    
    async def capsule_created(
        self,
        capsule_id: UUID,
        owner_id: UUID,
        capsule_type: str,
        parent_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        """Emit capsule created event."""
        event = CapsuleCreatedEvent.create(
            capsule_id=capsule_id,
            owner_id=owner_id,
            capsule_type=capsule_type,
            parent_id=parent_id,
            correlation_id=correlation_id,
        )
        await self.publish(event)
    
    async def capsule_updated(
        self,
        capsule_id: UUID,
        actor_id: UUID,
        old_version: str,
        new_version: str,
        fields_changed: list[str],
        correlation_id: UUID | None = None,
    ) -> None:
        """Emit capsule updated event."""
        event = CapsuleUpdatedEvent.create(
            capsule_id=capsule_id,
            actor_id=actor_id,
            old_version=old_version,
            new_version=new_version,
            fields_changed=fields_changed,
            correlation_id=correlation_id,
        )
        await self.publish(event)
    
    async def capsule_deleted(
        self,
        capsule_id: UUID,
        actor_id: UUID,
    ) -> None:
        """Emit capsule deleted event."""
        event = Event(
            type=EventType.CAPSULE_DELETED,
            actor_id=actor_id,
            resource_type="capsule",
            resource_id=capsule_id,
        )
        await self.publish(event)
    
    # =========================================================================
    # USER EVENTS
    # =========================================================================
    
    async def user_authenticated(
        self,
        user_id: UUID,
        ip_address: str,
        user_agent: str | None = None,
    ) -> None:
        """Emit user authenticated event."""
        event = UserAuthenticatedEvent.create(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.publish(event)
    
    async def user_trust_changed(
        self,
        user_id: UUID,
        actor_id: UUID,
        old_trust: str,
        new_trust: str,
        reason: str,
    ) -> None:
        """Emit user trust level changed event."""
        event = Event(
            type=EventType.USER_TRUST_CHANGED,
            actor_id=actor_id,
            resource_type="user",
            resource_id=user_id,
            data={
                "old_trust": old_trust,
                "new_trust": new_trust,
                "reason": reason,
            }
        )
        await self.publish(event)
    
    # =========================================================================
    # GOVERNANCE EVENTS
    # =========================================================================
    
    async def proposal_created(
        self,
        proposal_id: UUID,
        proposer_id: UUID,
        proposal_type: str,
        title: str,
    ) -> None:
        """Emit proposal created event."""
        event = ProposalCreatedEvent.create(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            proposal_type=proposal_type,
            title=title,
        )
        await self.publish(event)
    
    async def vote_cast(
        self,
        vote_id: UUID,
        proposal_id: UUID,
        voter_id: UUID,
        decision: str,
        weight: float,
    ) -> None:
        """Emit vote cast event."""
        event = VoteCastEvent.create(
            vote_id=vote_id,
            proposal_id=proposal_id,
            voter_id=voter_id,
            decision=decision,
            weight=weight,
        )
        await self.publish(event)
    
    # =========================================================================
    # SYSTEM EVENTS
    # =========================================================================
    
    async def immune_response(
        self,
        target_type: str,
        target_id: UUID,
        threat_type: str,
        threat_level: str,
        action_taken: str,
        reason: str,
    ) -> None:
        """Emit immune system response event."""
        event = ImmuneResponseEvent.create(
            target_type=target_type,
            target_id=target_id,
            threat_type=threat_type,
            threat_level=threat_level,
            action_taken=action_taken,
            reason=reason,
        )
        await self.publish(event)


# Singleton instance
_event_service: EventService | None = None


def get_event_service() -> EventService:
    """Get the singleton event service."""
    global _event_service
    if _event_service is None:
        _event_service = EventService()
    return _event_service
```

---

## 5. Integration with Services

Add event publishing to existing services. Here's an example for CapsuleService:

```python
# Update to forge/core/capsules/service.py

from forge.core.events.service import get_event_service

class CapsuleService:
    def __init__(
        self,
        repository: CapsuleRepository,
        embedding_service: EmbeddingService,
        event_service: EventService | None = None,  # Add this
    ):
        self._repo = repository
        self._embedding = embedding_service
        self._events = event_service or get_event_service()  # Add this
    
    async def create(
        self,
        data: CapsuleCreate,
        owner: User,
    ) -> Capsule:
        # ... existing creation logic ...
        
        capsule = await self._repo.create(...)
        
        # Emit event after successful creation
        await self._events.capsule_created(
            capsule_id=capsule.id,
            owner_id=owner.id,
            capsule_type=capsule.type.value,
            parent_id=data.parent_id,
        )
        
        return capsule
```
