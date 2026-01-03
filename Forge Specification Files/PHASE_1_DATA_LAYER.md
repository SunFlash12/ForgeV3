# Forge V3 - Phase 1: Data Layer

**Purpose:** Implement Neo4j client, core data models, and repository pattern for data access.

**Estimated Effort:** 3-4 days
**Dependencies:** Phase 0 (Foundations)
**Outputs:** Working database layer with CRUD operations for all core entities

---

## 1. Overview

This phase establishes the data persistence layer using Neo4j 5.x with native vector indexing. Neo4j serves as the unified store for graph relationships, vector embeddings, and document properties.

**Key Components:**
- Neo4j async client wrapper
- Core entity models (Capsule, User, Overlay, Proposal)
- Repository pattern for data access
- Database schema and indexes
- Connection pooling and transaction management

---

## 2. Neo4j Client

```python
# forge/infrastructure/neo4j/client.py
"""
Async Neo4j client with connection pooling and transaction support.
"""
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession, AsyncTransaction
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from forge.logging import get_logger
from forge.exceptions import ServiceUnavailableError

logger = get_logger(__name__)


class Neo4jClient:
    """
    Async Neo4j client wrapper.
    
    Provides:
    - Connection pooling
    - Automatic retry on transient failures
    - Transaction context managers
    - Health checking
    """
    
    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._max_pool_size = max_connection_pool_size
        self._driver: AsyncDriver | None = None
    
    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        logger.info("connecting_to_neo4j", uri=self._uri)
        
        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            max_connection_pool_size=self._max_pool_size,
        )
        
        # Verify connectivity
        try:
            await self._driver.verify_connectivity()
            logger.info("neo4j_connected")
        except ServiceUnavailable as e:
            logger.error("neo4j_connection_failed", error=str(e))
            raise ServiceUnavailableError(f"Failed to connect to Neo4j: {e}")
    
    async def close(self) -> None:
        """Close the driver connection."""
        if self._driver:
            await self._driver.close()
            logger.info("neo4j_disconnected")
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a session for running queries."""
        if not self._driver:
            raise RuntimeError("Neo4j client not connected")
        
        session = self._driver.session(database=self._database)
        try:
            yield session
        finally:
            await session.close()
    
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncTransaction]:
        """
        Get a transaction for atomic operations.
        
        Usage:
            async with client.transaction() as tx:
                await tx.run("CREATE (n:Node {name: $name})", name="test")
                # Automatically committed on success, rolled back on exception
        """
        async with self.session() as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise
    
    async def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run a query and return results as a list of dicts.
        
        For simple queries that don't need transaction control.
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]
    
    async def run_single(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Run a query expecting a single result."""
        results = await self.run(query, parameters)
        return results[0] if results else None
    
    async def health_check(self) -> bool:
        """Check if Neo4j is healthy."""
        try:
            result = await self.run_single("RETURN 1 as n")
            return result is not None and result.get("n") == 1
        except Exception as e:
            logger.warning("neo4j_health_check_failed", error=str(e))
            return False


# Query builder helpers
class CypherBuilder:
    """
    Helper for building Cypher queries safely.
    
    Ensures parameters are properly escaped and queries are readable.
    """
    
    @staticmethod
    def match_by_id(label: str, id_param: str = "id") -> str:
        """Generate MATCH clause for finding by ID."""
        return f"MATCH (n:{label} {{id: ${id_param}}})"
    
    @staticmethod
    def create_node(label: str, properties: list[str]) -> str:
        """Generate CREATE clause for a node."""
        props = ", ".join(f"{p}: ${p}" for p in properties)
        return f"CREATE (n:{label} {{{props}}})"
    
    @staticmethod
    def set_properties(properties: list[str], prefix: str = "n") -> str:
        """Generate SET clause for updating properties."""
        sets = ", ".join(f"{prefix}.{p} = ${p}" for p in properties)
        return f"SET {sets}"
```

---

## 3. Database Schema

```python
# forge/infrastructure/neo4j/schema.py
"""
Neo4j database schema initialization.

Run this on first deployment or after schema changes.
"""
from forge.infrastructure.neo4j.client import Neo4jClient
from forge.logging import get_logger

logger = get_logger(__name__)

# Schema creation queries
SCHEMA_QUERIES = [
    # =========================================================================
    # CONSTRAINTS (Uniqueness and existence)
    # =========================================================================
    
    # Capsule constraints
    "CREATE CONSTRAINT capsule_id_unique IF NOT EXISTS FOR (c:Capsule) REQUIRE c.id IS UNIQUE",
    
    # User constraints
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
    
    # Overlay constraints
    "CREATE CONSTRAINT overlay_id_unique IF NOT EXISTS FOR (o:Overlay) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT overlay_name_version IF NOT EXISTS FOR (o:Overlay) REQUIRE (o.name, o.version) IS UNIQUE",
    
    # Proposal constraints
    "CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS FOR (p:Proposal) REQUIRE p.id IS UNIQUE",
    
    # Vote constraints
    "CREATE CONSTRAINT vote_id_unique IF NOT EXISTS FOR (v:Vote) REQUIRE v.id IS UNIQUE",
    
    # =========================================================================
    # INDEXES (Performance)
    # =========================================================================
    
    # Capsule indexes
    "CREATE INDEX capsule_type_index IF NOT EXISTS FOR (c:Capsule) ON (c.type)",
    "CREATE INDEX capsule_trust_index IF NOT EXISTS FOR (c:Capsule) ON (c.trust_level)",
    "CREATE INDEX capsule_owner_index IF NOT EXISTS FOR (c:Capsule) ON (c.owner_id)",
    "CREATE INDEX capsule_created_index IF NOT EXISTS FOR (c:Capsule) ON (c.created_at)",
    "CREATE INDEX capsule_type_trust_index IF NOT EXISTS FOR (c:Capsule) ON (c.type, c.trust_level)",
    
    # User indexes
    "CREATE INDEX user_trust_index IF NOT EXISTS FOR (u:User) ON (u.trust_level)",
    
    # Proposal indexes
    "CREATE INDEX proposal_status_index IF NOT EXISTS FOR (p:Proposal) ON (p.status)",
    "CREATE INDEX proposal_type_index IF NOT EXISTS FOR (p:Proposal) ON (p.type)",
    
    # Overlay indexes
    "CREATE INDEX overlay_state_index IF NOT EXISTS FOR (o:Overlay) ON (o.state)",
    
    # =========================================================================
    # VECTOR INDEX (Semantic search)
    # =========================================================================
    
    """
    CREATE VECTOR INDEX capsule_embedding_index IF NOT EXISTS
    FOR (c:Capsule)
    ON c.embedding
    OPTIONS {
        indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine',
            `vector.quantization.enabled`: true
        }
    }
    """,
    
    # =========================================================================
    # FULL-TEXT INDEX (Keyword search)
    # =========================================================================
    
    "CREATE FULLTEXT INDEX capsule_content_fulltext IF NOT EXISTS FOR (c:Capsule) ON EACH [c.content]",
]


async def initialize_schema(client: Neo4jClient) -> None:
    """
    Initialize database schema.
    
    Safe to run multiple times - uses IF NOT EXISTS.
    """
    logger.info("initializing_neo4j_schema")
    
    for query in SCHEMA_QUERIES:
        try:
            await client.run(query)
            logger.debug("schema_query_executed", query=query[:50])
        except Exception as e:
            # Log but continue - some queries may fail if already exists
            logger.warning("schema_query_failed", query=query[:50], error=str(e))
    
    logger.info("neo4j_schema_initialized")


async def verify_schema(client: Neo4jClient) -> dict[str, bool]:
    """Verify that required schema elements exist."""
    checks = {}
    
    # Check vector index
    result = await client.run_single(
        "SHOW INDEXES WHERE name = 'capsule_embedding_index'"
    )
    checks["vector_index"] = result is not None
    
    # Check constraints
    constraints = await client.run("SHOW CONSTRAINTS")
    constraint_names = {c.get("name") for c in constraints}
    checks["capsule_id_constraint"] = "capsule_id_unique" in constraint_names
    checks["user_email_constraint"] = "user_email_unique" in constraint_names
    
    return checks
```

---

## 4. Capsule Model

```python
# forge/models/capsule.py
"""
Capsule domain models.

A Capsule is the atomic unit of knowledge in Forge.
"""
from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import Field, field_validator

from forge.models.base import (
    ForgeBaseModel,
    TimestampMixin,
    IdentifiableMixin,
    CapsuleType,
    TrustLevel,
)


class CapsuleBase(ForgeBaseModel):
    """Base capsule fields shared across create/update/read."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,
        description="The capsule content (1 byte to 1MB)",
    )
    type: CapsuleType = Field(
        ...,
        description="Classification of the capsule",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata",
    )


class CapsuleCreate(CapsuleBase):
    """Schema for creating a new capsule."""
    
    parent_id: UUID | None = Field(
        default=None,
        description="Parent capsule ID for symbolic inheritance",
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "FastAPI is preferred for new Python services due to async support.",
                    "type": "knowledge",
                    "metadata": {"source": "architecture_decision", "tags": ["python", "api"]},
                },
                {
                    "content": "def process_data(items: list) -> dict:\n    return {i: len(i) for i in items}",
                    "type": "code",
                    "parent_id": "123e4567-e89b-12d3-a456-426614174000",
                },
            ],
        },
    }


class CapsuleUpdate(ForgeBaseModel):
    """Schema for updating a capsule (partial update)."""
    
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=1_000_000,
    )
    metadata: dict[str, Any] | None = None


class Capsule(CapsuleBase, TimestampMixin, IdentifiableMixin):
    """
    Complete capsule entity as stored in database.
    
    Includes computed fields and relationships.
    """
    
    version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version",
    )
    owner_id: UUID = Field(
        ...,
        description="ID of the user who created this capsule",
    )
    trust_level: TrustLevel = Field(
        default=TrustLevel.STANDARD,
        description="Trust level (inherited from parent or default)",
    )
    parent_id: UUID | None = Field(
        default=None,
        description="Parent capsule ID if derived",
    )
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding for semantic search (1536 dimensions)",
    )
    is_deleted: bool = Field(
        default=False,
        description="Soft delete flag",
    )
    
    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Ensure version follows semver format."""
        parts = v.split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError("Version must be in format X.Y.Z")
        return v


class CapsuleWithLineage(Capsule):
    """Capsule with resolved lineage information."""
    
    parent: "Capsule | None" = None
    children_count: int = 0
    lineage_depth: int = 0


class LineageEntry(ForgeBaseModel):
    """Entry in a lineage chain."""
    
    capsule: Capsule
    depth: int = Field(description="Distance from the queried capsule")
    relationship_type: str = Field(default="DERIVED_FROM")
    relationship_reason: str | None = None
    relationship_created_at: datetime | None = None


class LineageResult(ForgeBaseModel):
    """Result of a lineage query."""
    
    capsule_id: UUID
    lineage: list[LineageEntry]
    depth: int = Field(description="Total depth of lineage")
    truncated: bool = Field(description="True if max_depth was reached")
```

---

## 5. User Model

```python
# forge/models/user.py
"""
User domain models.
"""
from datetime import datetime
from uuid import UUID
from pydantic import Field, EmailStr

from forge.models.base import (
    ForgeBaseModel,
    TimestampMixin,
    IdentifiableMixin,
    TrustLevel,
)


class UserBase(ForgeBaseModel):
    """Base user fields."""
    
    email: EmailStr = Field(..., description="User email address")
    display_name: str | None = Field(
        default=None,
        max_length=100,
        description="Display name",
    )


class UserCreate(UserBase):
    """Schema for creating a user."""
    
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (will be hashed)",
    )


class UserUpdate(ForgeBaseModel):
    """Schema for updating a user."""
    
    display_name: str | None = Field(default=None, max_length=100)
    # Password updates use a separate endpoint


class User(UserBase, TimestampMixin, IdentifiableMixin):
    """Complete user entity."""
    
    trust_level: TrustLevel = Field(
        default=TrustLevel.STANDARD,
        description="User's trust level",
    )
    roles: list[str] = Field(
        default_factory=lambda: ["user"],
        description="User roles for RBAC",
    )
    is_active: bool = Field(
        default=True,
        description="Whether user can log in",
    )
    mfa_enabled: bool = Field(
        default=False,
        description="Whether MFA is enabled",
    )
    failed_login_attempts: int = Field(
        default=0,
        description="Failed login counter",
    )
    locked_until: datetime | None = Field(
        default=None,
        description="Account lock expiry time",
    )
    last_login_at: datetime | None = Field(
        default=None,
        description="Last successful login",
    )
    
    # These are never returned in API responses
    password_hash: str | None = Field(default=None, exclude=True)


class UserPublic(ForgeBaseModel):
    """Public user information (safe to expose)."""
    
    id: UUID
    email: EmailStr
    display_name: str | None
    trust_level: TrustLevel
    created_at: datetime
```

---

## 6. Capsule Repository

```python
# forge/core/capsules/repository.py
"""
Capsule repository for database operations.

Implements the repository pattern for clean separation
between business logic and data access.
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import Any

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    CapsuleWithLineage,
    LineageEntry,
    LineageResult,
)
from forge.models.base import TrustLevel, CapsuleType
from forge.exceptions import NotFoundError
from forge.logging import get_logger

logger = get_logger(__name__)


class CapsuleRepository:
    """
    Repository for Capsule data access.
    
    All database operations for capsules go through this class.
    """
    
    def __init__(self, neo4j: Neo4jClient):
        self._neo4j = neo4j
    
    async def create(
        self,
        data: CapsuleCreate,
        owner_id: UUID,
        embedding: list[float] | None = None,
        trust_level: TrustLevel = TrustLevel.STANDARD,
    ) -> Capsule:
        """
        Create a new capsule.
        
        If parent_id is provided, creates DERIVED_FROM relationship.
        """
        capsule_id = UUID(bytes=__import__('uuid').uuid4().bytes)
        now = datetime.now(timezone.utc)
        
        async with self._neo4j.transaction() as tx:
            # Create the capsule node
            result = await tx.run("""
                CREATE (c:Capsule {
                    id: $id,
                    content: $content,
                    type: $type,
                    version: '1.0.0',
                    owner_id: $owner_id,
                    trust_level: $trust_level,
                    metadata: $metadata,
                    embedding: $embedding,
                    is_deleted: false,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at)
                })
                RETURN c
            """, {
                "id": str(capsule_id),
                "content": data.content,
                "type": data.type.value,
                "owner_id": str(owner_id),
                "trust_level": trust_level.value,
                "metadata": data.metadata,
                "embedding": embedding,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            
            record = await result.single()
            capsule_data = dict(record["c"])
            
            # Create parent relationship if specified
            if data.parent_id:
                await tx.run("""
                    MATCH (child:Capsule {id: $child_id})
                    MATCH (parent:Capsule {id: $parent_id})
                    CREATE (child)-[:DERIVED_FROM {
                        created_at: datetime(),
                        reason: 'user_created'
                    }]->(parent)
                """, {
                    "child_id": str(capsule_id),
                    "parent_id": str(data.parent_id),
                })
                capsule_data["parent_id"] = str(data.parent_id)
        
        logger.info("capsule_created", capsule_id=str(capsule_id), type=data.type.value)
        
        return self._map_to_capsule(capsule_data)
    
    async def get_by_id(self, capsule_id: UUID) -> Capsule | None:
        """Get a capsule by ID."""
        result = await self._neo4j.run_single("""
            MATCH (c:Capsule {id: $id})
            WHERE c.is_deleted = false
            OPTIONAL MATCH (c)-[:DERIVED_FROM]->(parent:Capsule)
            RETURN c, parent.id as parent_id
        """, {"id": str(capsule_id)})
        
        if not result:
            return None
        
        data = dict(result["c"])
        data["parent_id"] = result.get("parent_id")
        return self._map_to_capsule(data)
    
    async def get_by_id_or_raise(self, capsule_id: UUID) -> Capsule:
        """Get a capsule by ID or raise NotFoundError."""
        capsule = await self.get_by_id(capsule_id)
        if not capsule:
            raise NotFoundError("Capsule", str(capsule_id))
        return capsule
    
    async def update(
        self,
        capsule_id: UUID,
        data: CapsuleUpdate,
        new_embedding: list[float] | None = None,
    ) -> Capsule:
        """
        Update a capsule.
        
        Content updates increment the version.
        """
        # Build SET clause dynamically based on provided fields
        set_parts = ["c.updated_at = datetime()"]
        params: dict[str, Any] = {"id": str(capsule_id)}
        
        if data.content is not None:
            set_parts.append("c.content = $content")
            params["content"] = data.content
            # Increment version on content change
            set_parts.append("""
                c.version = 
                    toString(toInteger(split(c.version, '.')[0])) + '.' +
                    toString(toInteger(split(c.version, '.')[1]) + 1) + '.0'
            """)
        
        if data.metadata is not None:
            set_parts.append("c.metadata = $metadata")
            params["metadata"] = data.metadata
        
        if new_embedding is not None:
            set_parts.append("c.embedding = $embedding")
            params["embedding"] = new_embedding
        
        query = f"""
            MATCH (c:Capsule {{id: $id}})
            WHERE c.is_deleted = false
            SET {', '.join(set_parts)}
            RETURN c
        """
        
        result = await self._neo4j.run_single(query, params)
        
        if not result:
            raise NotFoundError("Capsule", str(capsule_id))
        
        logger.info("capsule_updated", capsule_id=str(capsule_id))
        return self._map_to_capsule(dict(result["c"]))
    
    async def soft_delete(self, capsule_id: UUID) -> bool:
        """Soft delete a capsule."""
        result = await self._neo4j.run_single("""
            MATCH (c:Capsule {id: $id})
            WHERE c.is_deleted = false
            SET c.is_deleted = true, c.updated_at = datetime()
            RETURN c.id as id
        """, {"id": str(capsule_id)})
        
        if result:
            logger.info("capsule_deleted", capsule_id=str(capsule_id))
            return True
        return False
    
    async def list(
        self,
        page: int = 1,
        per_page: int = 20,
        type_filter: CapsuleType | None = None,
        trust_level_filter: TrustLevel | None = None,
        owner_id: UUID | None = None,
        parent_id: UUID | None = None,
    ) -> tuple[list[Capsule], int]:
        """
        List capsules with pagination and filtering.
        
        Returns (capsules, total_count).
        """
        # Build WHERE clause
        where_parts = ["c.is_deleted = false"]
        params: dict[str, Any] = {
            "skip": (page - 1) * per_page,
            "limit": per_page,
        }
        
        if type_filter:
            where_parts.append("c.type = $type")
            params["type"] = type_filter.value
        
        if trust_level_filter:
            where_parts.append("c.trust_level = $trust_level")
            params["trust_level"] = trust_level_filter.value
        
        if owner_id:
            where_parts.append("c.owner_id = $owner_id")
            params["owner_id"] = str(owner_id)
        
        if parent_id:
            where_parts.append("EXISTS((c)-[:DERIVED_FROM]->(:Capsule {id: $parent_id}))")
            params["parent_id"] = str(parent_id)
        
        where_clause = " AND ".join(where_parts)
        
        # Get total count
        count_result = await self._neo4j.run_single(f"""
            MATCH (c:Capsule)
            WHERE {where_clause}
            RETURN count(c) as total
        """, params)
        total = count_result["total"] if count_result else 0
        
        # Get paginated results
        results = await self._neo4j.run(f"""
            MATCH (c:Capsule)
            WHERE {where_clause}
            OPTIONAL MATCH (c)-[:DERIVED_FROM]->(parent:Capsule)
            RETURN c, parent.id as parent_id
            ORDER BY c.created_at DESC
            SKIP $skip
            LIMIT $limit
        """, params)
        
        capsules = []
        for record in results:
            data = dict(record["c"])
            data["parent_id"] = record.get("parent_id")
            capsules.append(self._map_to_capsule(data))
        
        return capsules, total
    
    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_score: float = 0.7,
        type_filter: CapsuleType | None = None,
    ) -> list[tuple[Capsule, float]]:
        """
        Semantic search using vector similarity.
        
        Returns list of (capsule, similarity_score) tuples.
        """
        # Build optional type filter
        type_clause = ""
        params: dict[str, Any] = {
            "embedding": embedding,
            "limit": limit,
        }
        
        if type_filter:
            type_clause = "AND node.type = $type"
            params["type"] = type_filter.value
        
        results = await self._neo4j.run(f"""
            CALL db.index.vector.queryNodes(
                'capsule_embedding_index',
                $limit,
                $embedding
            )
            YIELD node, score
            WHERE node.is_deleted = false 
                AND score >= {min_score}
                {type_clause}
            OPTIONAL MATCH (node)-[:DERIVED_FROM]->(parent:Capsule)
            RETURN node, score, parent.id as parent_id
            ORDER BY score DESC
        """, params)
        
        capsules_with_scores = []
        for record in results:
            data = dict(record["node"])
            data["parent_id"] = record.get("parent_id")
            capsule = self._map_to_capsule(data)
            capsules_with_scores.append((capsule, record["score"]))
        
        return capsules_with_scores
    
    async def get_lineage(
        self,
        capsule_id: UUID,
        max_depth: int = 10,
    ) -> LineageResult:
        """
        Get the ancestry chain (Isnad) for a capsule.
        
        Traverses DERIVED_FROM relationships backwards.
        """
        results = await self._neo4j.run("""
            MATCH (start:Capsule {id: $id})
            MATCH path = (start)-[:DERIVED_FROM*1..]->(ancestor:Capsule)
            WITH ancestor, length(path) as depth, 
                 relationships(path)[-1] as rel
            WHERE ancestor.is_deleted = false
            RETURN ancestor, depth, 
                   rel.reason as reason,
                   rel.created_at as rel_created_at
            ORDER BY depth
            LIMIT $max_depth
        """, {"id": str(capsule_id), "max_depth": max_depth})
        
        lineage = []
        for record in results:
            ancestor_data = dict(record["ancestor"])
            entry = LineageEntry(
                capsule=self._map_to_capsule(ancestor_data),
                depth=record["depth"],
                relationship_reason=record.get("reason"),
                relationship_created_at=record.get("rel_created_at"),
            )
            lineage.append(entry)
        
        return LineageResult(
            capsule_id=capsule_id,
            lineage=lineage,
            depth=len(lineage),
            truncated=len(lineage) >= max_depth,
        )
    
    async def get_children_count(self, capsule_id: UUID) -> int:
        """Count capsules that derive from this one."""
        result = await self._neo4j.run_single("""
            MATCH (parent:Capsule {id: $id})<-[:DERIVED_FROM]-(child:Capsule)
            WHERE child.is_deleted = false
            RETURN count(child) as count
        """, {"id": str(capsule_id)})
        return result["count"] if result else 0
    
    def _map_to_capsule(self, data: dict[str, Any]) -> Capsule:
        """Map Neo4j record to Capsule model."""
        # Handle Neo4j DateTime conversion
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        
        return Capsule(
            id=UUID(data["id"]),
            content=data["content"],
            type=CapsuleType(data["type"]),
            version=data.get("version", "1.0.0"),
            owner_id=UUID(data["owner_id"]),
            trust_level=TrustLevel(data["trust_level"]),
            parent_id=UUID(data["parent_id"]) if data.get("parent_id") else None,
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            is_deleted=data.get("is_deleted", False),
            created_at=created_at,
            updated_at=updated_at,
        )
```

---

## 7. User Repository

```python
# forge/core/users/repository.py
"""
User repository for database operations.
"""
from uuid import UUID
from datetime import datetime, timezone

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.models.user import User, UserCreate, UserUpdate
from forge.models.base import TrustLevel
from forge.exceptions import NotFoundError, ConflictError
from forge.logging import get_logger

logger = get_logger(__name__)


class UserRepository:
    """Repository for User data access."""
    
    def __init__(self, neo4j: Neo4jClient):
        self._neo4j = neo4j
    
    async def create(
        self,
        data: UserCreate,
        password_hash: str,
    ) -> User:
        """Create a new user."""
        user_id = UUID(bytes=__import__('uuid').uuid4().bytes)
        now = datetime.now(timezone.utc)
        
        # Check if email already exists
        existing = await self.get_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email {data.email} already exists")
        
        result = await self._neo4j.run_single("""
            CREATE (u:User {
                id: $id,
                email: $email,
                display_name: $display_name,
                password_hash: $password_hash,
                trust_level: $trust_level,
                roles: $roles,
                is_active: true,
                mfa_enabled: false,
                failed_login_attempts: 0,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at)
            })
            RETURN u
        """, {
            "id": str(user_id),
            "email": data.email.lower(),
            "display_name": data.display_name,
            "password_hash": password_hash,
            "trust_level": TrustLevel.STANDARD.value,
            "roles": ["user"],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        
        logger.info("user_created", user_id=str(user_id), email=data.email)
        return self._map_to_user(dict(result["u"]))
    
    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            RETURN u
        """, {"id": str(user_id)})
        
        if not result:
            return None
        return self._map_to_user(dict(result["u"]))
    
    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self._neo4j.run_single("""
            MATCH (u:User {email: $email})
            RETURN u
        """, {"email": email.lower()})
        
        if not result:
            return None
        return self._map_to_user(dict(result["u"]))
    
    async def update_password_hash(self, user_id: UUID, new_hash: str) -> None:
        """Update user's password hash."""
        await self._neo4j.run("""
            MATCH (u:User {id: $id})
            SET u.password_hash = $hash, u.updated_at = datetime()
        """, {"id": str(user_id), "hash": new_hash})
    
    async def update_failed_attempts(
        self,
        user_id: UUID,
        count: int,
        locked_until: datetime | None,
    ) -> None:
        """Update failed login attempt counter."""
        await self._neo4j.run("""
            MATCH (u:User {id: $id})
            SET u.failed_login_attempts = $count,
                u.locked_until = $locked_until,
                u.updated_at = datetime()
        """, {
            "id": str(user_id),
            "count": count,
            "locked_until": locked_until.isoformat() if locked_until else None,
        })
    
    async def clear_failed_attempts(self, user_id: UUID) -> None:
        """Clear failed attempts on successful login."""
        await self._neo4j.run("""
            MATCH (u:User {id: $id})
            SET u.failed_login_attempts = 0,
                u.locked_until = null,
                u.last_login_at = datetime(),
                u.updated_at = datetime()
        """, {"id": str(user_id)})
    
    async def update_trust_level(
        self,
        user_id: UUID,
        trust_level: TrustLevel,
    ) -> User:
        """Update user's trust level."""
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            SET u.trust_level = $trust_level, u.updated_at = datetime()
            RETURN u
        """, {"id": str(user_id), "trust_level": trust_level.value})
        
        if not result:
            raise NotFoundError("User", str(user_id))
        
        logger.info("user_trust_updated", user_id=str(user_id), trust_level=trust_level.value)
        return self._map_to_user(dict(result["u"]))
    
    def _map_to_user(self, data: dict) -> User:
        """Map Neo4j record to User model."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        last_login = data.get("last_login_at")
        locked_until = data.get("locked_until")
        
        # Convert Neo4j DateTime
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        if hasattr(last_login, "to_native"):
            last_login = last_login.to_native()
        if hasattr(locked_until, "to_native"):
            locked_until = locked_until.to_native()
        
        return User(
            id=UUID(data["id"]),
            email=data["email"],
            display_name=data.get("display_name"),
            password_hash=data.get("password_hash"),
            trust_level=TrustLevel(data["trust_level"]),
            roles=data.get("roles", ["user"]),
            is_active=data.get("is_active", True),
            mfa_enabled=data.get("mfa_enabled", False),
            failed_login_attempts=data.get("failed_login_attempts", 0),
            locked_until=locked_until,
            last_login_at=last_login,
            created_at=created_at,
            updated_at=updated_at,
        )
```

---

## 8. Testing the Data Layer

```python
# tests/unit/test_capsule_repository.py
"""
Unit tests for CapsuleRepository.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from forge.core.capsules.repository import CapsuleRepository
from forge.models.capsule import CapsuleCreate, CapsuleType
from forge.models.base import TrustLevel


@pytest.fixture
def mock_neo4j():
    """Create mock Neo4j client."""
    client = AsyncMock()
    return client


@pytest.fixture
def repository(mock_neo4j):
    """Create repository with mocked client."""
    return CapsuleRepository(mock_neo4j)


class TestCapsuleRepositoryCreate:
    """Tests for capsule creation."""
    
    async def test_create_capsule_basic(self, repository, mock_neo4j):
        """Test creating a basic capsule."""
        # Arrange
        mock_neo4j.transaction.return_value.__aenter__.return_value.run.return_value.single.return_value = {
            "c": {
                "id": "test-id",
                "content": "test content",
                "type": "knowledge",
                "version": "1.0.0",
                "owner_id": "owner-id",
                "trust_level": "standard",
                "metadata": {},
                "is_deleted": False,
                "created_at": "2026-01-02T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        }
        
        data = CapsuleCreate(
            content="test content",
            type=CapsuleType.KNOWLEDGE,
        )
        owner_id = uuid4()
        
        # Act
        result = await repository.create(data, owner_id)
        
        # Assert
        assert result.content == "test content"
        assert result.type == CapsuleType.KNOWLEDGE
        assert result.version == "1.0.0"
    
    async def test_create_capsule_with_parent(self, repository, mock_neo4j):
        """Test creating capsule with parent relationship."""
        parent_id = uuid4()
        
        mock_neo4j.transaction.return_value.__aenter__.return_value.run.return_value.single.return_value = {
            "c": {
                "id": "child-id",
                "content": "derived content",
                "type": "knowledge",
                "version": "1.0.0",
                "owner_id": "owner-id",
                "trust_level": "standard",
                "metadata": {},
                "is_deleted": False,
                "created_at": "2026-01-02T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        }
        
        data = CapsuleCreate(
            content="derived content",
            type=CapsuleType.KNOWLEDGE,
            parent_id=parent_id,
        )
        
        # Act
        result = await repository.create(data, uuid4())
        
        # Assert
        # Verify parent relationship query was called
        tx = mock_neo4j.transaction.return_value.__aenter__.return_value
        assert tx.run.call_count >= 2  # Create + relationship


class TestCapsuleRepositorySearch:
    """Tests for semantic search."""
    
    async def test_search_by_embedding(self, repository, mock_neo4j):
        """Test vector search returns scored results."""
        mock_neo4j.run.return_value = [
            {
                "node": {
                    "id": "result-1",
                    "content": "matching content",
                    "type": "knowledge",
                    "version": "1.0.0",
                    "owner_id": "owner-id",
                    "trust_level": "standard",
                    "metadata": {},
                    "is_deleted": False,
                    "created_at": "2026-01-02T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                },
                "score": 0.95,
                "parent_id": None,
            }
        ]
        
        embedding = [0.1] * 1536
        
        # Act
        results = await repository.search_by_embedding(embedding, limit=10)
        
        # Assert
        assert len(results) == 1
        capsule, score = results[0]
        assert score == 0.95
        assert capsule.content == "matching content"
```

---

## 9. Integration Test Setup

```python
# tests/integration/conftest.py
"""
Integration test fixtures using testcontainers.
"""
import pytest
import asyncio
from testcontainers.neo4j import Neo4jContainer

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.infrastructure.neo4j.schema import initialize_schema


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def neo4j_container():
    """Start Neo4j container for integration tests."""
    with Neo4jContainer("neo4j:5.15-enterprise") as container:
        container.with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        yield container


@pytest.fixture
async def neo4j_client(neo4j_container):
    """Create Neo4j client connected to test container."""
    client = Neo4jClient(
        uri=neo4j_container.get_connection_url(),
        user="neo4j",
        password="test",
        database="neo4j",
    )
    await client.connect()
    await initialize_schema(client)
    yield client
    await client.close()


@pytest.fixture
async def capsule_repository(neo4j_client):
    """Create CapsuleRepository with test client."""
    from forge.core.capsules.repository import CapsuleRepository
    return CapsuleRepository(neo4j_client)
```

---

## 10. Next Steps

After completing Phase 1:

1. Run tests to verify data layer works correctly
2. Proceed to **Phase 2: Knowledge Engine** to add:
   - Embedding generation service
   - Capsule business logic service
   - Semantic search with HybridRAG

The data layer provides the foundation for all subsequent phases.
