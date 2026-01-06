"""
Base Repository

Abstract base class for all repositories with common CRUD operations
and Neo4j query patterns.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import re
from typing import Any, Generic, TypeVar
from uuid import uuid4

import structlog
from pydantic import BaseModel

from forge.database.client import Neo4jClient

logger = structlog.get_logger(__name__)

# Regex for valid Cypher identifiers (property names, etc.)
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def validate_identifier(name: str, param_name: str = "identifier") -> str:
    """
    Validate that a string is a safe Cypher identifier.

    Prevents Cypher injection through field/property names.

    Args:
        name: The identifier to validate
        param_name: Name of the parameter (for error messages)

    Returns:
        The validated identifier

    Raises:
        ValueError: If the identifier is invalid
    """
    if not name:
        raise ValueError(f"{param_name} cannot be empty")
    if not VALID_IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"Invalid {param_name}: must be alphanumeric with underscores, starting with letter or underscore")
    if len(name) > 64:
        raise ValueError(f"{param_name} too long (max 64 characters)")
    return name

# Type variables for generic repository
T = TypeVar("T", bound=BaseModel)  # Model type
CreateT = TypeVar("CreateT", bound=BaseModel)  # Create schema type
UpdateT = TypeVar("UpdateT", bound=BaseModel)  # Update schema type


class BaseRepository(ABC, Generic[T, CreateT, UpdateT]):
    """
    Abstract base repository with common CRUD operations.
    
    Provides a foundation for entity-specific repositories with
    Neo4j Cypher query patterns.
    """

    def __init__(self, client: Neo4jClient):
        """
        Initialize repository with database client.
        
        Args:
            client: Neo4j client instance
        """
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def node_label(self) -> str:
        """The Neo4j node label for this entity."""
        pass

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """The Pydantic model class for this entity."""
        pass

    def _generate_id(self) -> str:
        """Generate a new unique ID."""
        return str(uuid4())

    def _now(self) -> datetime:
        """Get current UTC timestamp."""
        return datetime.utcnow()

    def _to_model(self, record: dict[str, Any]) -> T | None:
        """
        Convert a Neo4j record to a Pydantic model.
        
        Args:
            record: Dict from Neo4j query result
            
        Returns:
            Pydantic model instance or None
        """
        if not record:
            return None
        try:
            return self.model_class.model_validate(record)
        except Exception as e:
            self.logger.error(
                "Failed to convert record to model",
                error=str(e),
                record_keys=list(record.keys()),
            )
            return None

    def _to_models(self, records: list[dict[str, Any]]) -> list[T]:
        """
        Convert multiple Neo4j records to Pydantic models.
        
        Args:
            records: List of dicts from Neo4j query
            
        Returns:
            List of Pydantic model instances
        """
        return [m for m in (self._to_model(r) for r in records) if m is not None]

    async def get_by_id(self, entity_id: str) -> T | None:
        """
        Get an entity by its ID.
        
        Args:
            entity_id: The entity's unique ID
            
        Returns:
            Entity model or None if not found
        """
        query = f"""
        MATCH (n:{self.node_label} {{id: $id}})
        RETURN n {{.*}} AS entity
        """
        
        result = await self.client.execute_single(query, {"id": entity_id})
        
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "created_at",
        order_dir: str = "DESC",
    ) -> list[T]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return (capped at 1000)
            order_by: Field to order by (validated for safety)
            order_dir: Order direction (ASC or DESC)

        Returns:
            List of entity models
        """
        # Validate order_by to prevent Cypher injection
        order_by = validate_identifier(order_by, "order_by")

        # Validate order direction
        order_dir = order_dir.upper()
        if order_dir not in ("ASC", "DESC"):
            order_dir = "DESC"

        # Cap limit to prevent memory exhaustion
        limit = min(max(1, limit), 1000)
        skip = max(0, skip)

        query = f"""
        MATCH (n:{self.node_label})
        RETURN n {{.*}} AS entity
        ORDER BY n.{order_by} {order_dir}
        SKIP $skip
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"skip": skip, "limit": limit},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def count(self) -> int:
        """
        Count total entities.
        
        Returns:
            Total count
        """
        query = f"MATCH (n:{self.node_label}) RETURN count(n) AS count"
        result = await self.client.execute_single(query)
        return result.get("count", 0) if result else 0

    async def exists(self, entity_id: str) -> bool:
        """
        Check if an entity exists.
        
        Args:
            entity_id: The entity's ID
            
        Returns:
            True if exists
        """
        query = f"""
        MATCH (n:{self.node_label} {{id: $id}})
        RETURN count(n) > 0 AS exists
        """
        
        result = await self.client.execute_single(query, {"id": entity_id})
        return result.get("exists", False) if result else False

    async def delete(self, entity_id: str) -> bool:
        """
        Delete an entity by ID.
        
        Args:
            entity_id: The entity's ID
            
        Returns:
            True if deleted
        """
        query = f"""
        MATCH (n:{self.node_label} {{id: $id}})
        DETACH DELETE n
        RETURN count(n) AS deleted
        """
        
        result = await self.client.execute_single(query, {"id": entity_id})
        deleted = result.get("deleted", 0) if result else 0
        
        if deleted > 0:
            self.logger.info(
                "Deleted entity",
                entity_type=self.node_label,
                entity_id=entity_id,
            )
        
        return deleted > 0

    async def update_field(
        self,
        entity_id: str,
        field: str,
        value: Any,
    ) -> T | None:
        """
        Update a single field on an entity.

        Args:
            entity_id: The entity's ID
            field: Field name to update (validated for safety)
            value: New value

        Returns:
            Updated entity or None
        """
        # Validate field name to prevent Cypher injection
        field = validate_identifier(field, "field")

        query = f"""
        MATCH (n:{self.node_label} {{id: $id}})
        SET n.{field} = $value, n.updated_at = $now
        RETURN n {{.*}} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": entity_id,
                "value": value,
                "now": self._now().isoformat(),
            },
        )

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    async def find_by_field(
        self,
        field: str,
        value: Any,
        limit: int = 100,
    ) -> list[T]:
        """
        Find entities by a field value.

        Args:
            field: Field name to search (validated for safety)
            value: Value to match
            limit: Maximum results (capped at 1000)

        Returns:
            List of matching entities
        """
        # Validate field name to prevent Cypher injection
        field = validate_identifier(field, "field")

        # Cap limit
        limit = min(max(1, limit), 1000)

        query = f"""
        MATCH (n:{self.node_label} {{{field}: $value}})
        RETURN n {{.*}} AS entity
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"value": value, "limit": limit},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    @abstractmethod
    async def create(self, data: CreateT, **kwargs: Any) -> T:
        """
        Create a new entity.
        
        Args:
            data: Creation schema
            **kwargs: Additional arguments
            
        Returns:
            Created entity
        """
        pass

    @abstractmethod
    async def update(self, entity_id: str, data: UpdateT) -> T | None:
        """
        Update an existing entity.
        
        Args:
            entity_id: Entity ID
            data: Update schema
            
        Returns:
            Updated entity or None
        """
        pass
