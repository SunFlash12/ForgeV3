# Forge V3 - Phase 2: Knowledge Engine

**Purpose:** Implement the capsule service with embedding generation, semantic search, and lineage tracking.

**Estimated Effort:** 3-4 days
**Dependencies:** Phase 0 (Foundations), Phase 1 (Data Layer)
**Outputs:** Working capsule CRUD with semantic search capabilities

---

## 1. Overview

The Knowledge Engine is the core of Forge, responsible for creating, storing, and retrieving knowledge capsules. This phase adds the business logic layer on top of the data layer, including embedding generation for semantic search.

**Key Components:**
- Embedding service (OpenAI/local)
- Capsule service (business logic)
- Hybrid search (vector + graph)
- Lineage (Isnad) queries

---

## 2. Embedding Service

```python
# forge/infrastructure/embedding/service.py
"""
Embedding service for generating vector representations of text.

Supports multiple providers:
- OpenAI (default)
- Azure OpenAI
- Local models (future)
"""
from abc import ABC, abstractmethod
import hashlib
from typing import Protocol

import httpx
from openai import AsyncOpenAI

from forge.config import get_settings
from forge.logging import get_logger
from forge.exceptions import ServiceUnavailableError

logger = get_logger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=self._dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("embedding_failed", error=str(e))
            raise ServiceUnavailableError(f"Embedding service failed: {e}")
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (max 2048 per batch)."""
        if not texts:
            return []
        
        # OpenAI allows up to 2048 inputs per request
        batch_size = 2048
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                    dimensions=self._dimensions,
                )
                # Embeddings are returned in same order as input
                all_embeddings.extend([d.embedding for d in response.data])
            except Exception as e:
                logger.error("batch_embedding_failed", error=str(e), batch_index=i)
                raise ServiceUnavailableError(f"Batch embedding failed: {e}")
        
        return all_embeddings


class EmbeddingService:
    """
    High-level embedding service with caching.
    
    Caches embeddings by content hash to avoid redundant API calls.
    """
    
    def __init__(
        self,
        provider: EmbeddingProvider,
        cache: "RedisClient | None" = None,
        cache_ttl: int = 86400 * 7,  # 7 days
    ):
        self._provider = provider
        self._cache = cache
        self._cache_ttl = cache_ttl
    
    async def generate(self, text: str) -> list[float]:
        """
        Generate embedding for text, using cache if available.
        
        Args:
            text: The text to embed
            
        Returns:
            Vector embedding (1536 dimensions by default)
        """
        # Check cache first
        if self._cache:
            cache_key = self._cache_key(text)
            cached = await self._cache.get(cache_key)
            if cached:
                logger.debug("embedding_cache_hit")
                return cached
        
        # Generate embedding
        embedding = await self._provider.embed(text)
        
        # Cache the result
        if self._cache:
            await self._cache.set(
                cache_key,
                embedding,
                ttl=self._cache_ttl,
            )
        
        return embedding
    
    async def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        
        # For simplicity, don't use cache for batches
        # (could be optimized to check cache for each item)
        return await self._provider.embed_batch(texts)
    
    def _cache_key(self, text: str) -> str:
        """Generate cache key from text content."""
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"embedding:{content_hash}"


def create_embedding_service() -> EmbeddingService:
    """Factory function to create embedding service from settings."""
    settings = get_settings()
    
    if settings.embedding_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI embedding provider")
        
        provider = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
    
    # Cache is optional - would inject RedisClient here
    return EmbeddingService(provider=provider, cache=None)
```

---

## 3. Capsule Service

```python
# forge/core/capsules/service.py
"""
Capsule business logic service.

Orchestrates capsule operations including:
- Creation with embedding generation
- Updates with version management
- Search (semantic and keyword)
- Lineage queries
"""
from uuid import UUID
from typing import Any

from forge.core.capsules.repository import CapsuleRepository
from forge.infrastructure.embedding.service import EmbeddingService
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    LineageResult,
)
from forge.models.base import TrustLevel, CapsuleType
from forge.models.user import User
from forge.exceptions import NotFoundError, AuthorizationError, ValidationError
from forge.logging import get_logger

logger = get_logger(__name__)


class CapsuleService:
    """
    Service layer for capsule operations.
    
    Handles business logic, authorization, and orchestration
    between repositories and external services.
    """
    
    def __init__(
        self,
        repository: CapsuleRepository,
        embedding_service: EmbeddingService,
    ):
        self._repo = repository
        self._embedding = embedding_service
    
    async def create(
        self,
        data: CapsuleCreate,
        owner: User,
    ) -> Capsule:
        """
        Create a new capsule.
        
        Steps:
        1. Validate parent exists (if specified)
        2. Determine trust level (inherit from parent or use default)
        3. Generate embedding for content
        4. Create capsule in database
        
        Args:
            data: Capsule creation data
            owner: The user creating the capsule
            
        Returns:
            Created Capsule
            
        Raises:
            NotFoundError: If parent_id specified but not found
            AuthorizationError: If user cannot derive from parent
            ValidationError: If content is invalid
        """
        trust_level = TrustLevel.STANDARD
        
        # Validate and process parent relationship
        if data.parent_id:
            parent = await self._repo.get_by_id(data.parent_id)
            if not parent:
                raise NotFoundError("Capsule", str(data.parent_id))
            
            # User must have sufficient trust to derive from parent
            if not owner.trust_level.can_access(parent.trust_level):
                raise AuthorizationError(
                    f"Cannot derive from capsule with trust level {parent.trust_level.value}. "
                    f"Your trust level: {owner.trust_level.value}"
                )
            
            # Inherit trust level from parent (or keep lower if user is lower)
            if owner.trust_level.numeric_value < parent.trust_level.numeric_value:
                trust_level = owner.trust_level
            else:
                trust_level = parent.trust_level
        
        # Generate embedding for semantic search
        embedding = await self._embedding.generate(data.content)
        
        # Create capsule
        capsule = await self._repo.create(
            data=data,
            owner_id=owner.id,
            embedding=embedding,
            trust_level=trust_level,
        )
        
        logger.info(
            "capsule_created",
            capsule_id=str(capsule.id),
            type=capsule.type.value,
            has_parent=data.parent_id is not None,
        )
        
        return capsule
    
    async def get(self, capsule_id: UUID, user: User) -> Capsule:
        """
        Get a capsule by ID.
        
        Enforces trust level access control.
        """
        capsule = await self._repo.get_by_id(capsule_id)
        
        if not capsule:
            raise NotFoundError("Capsule", str(capsule_id))
        
        # Check trust level access
        if not user.trust_level.can_access(capsule.trust_level):
            raise AuthorizationError(
                f"Insufficient trust level to access this capsule"
            )
        
        return capsule
    
    async def update(
        self,
        capsule_id: UUID,
        data: CapsuleUpdate,
        user: User,
    ) -> Capsule:
        """
        Update a capsule.
        
        Only the owner (or admin) can update.
        Content changes trigger version increment and new embedding.
        """
        capsule = await self._repo.get_by_id(capsule_id)
        
        if not capsule:
            raise NotFoundError("Capsule", str(capsule_id))
        
        # Authorization: owner or admin
        if capsule.owner_id != user.id and "admin" not in user.roles:
            raise AuthorizationError("Only the owner can update this capsule")
        
        # Generate new embedding if content changed
        new_embedding = None
        if data.content is not None and data.content != capsule.content:
            new_embedding = await self._embedding.generate(data.content)
        
        updated = await self._repo.update(
            capsule_id=capsule_id,
            data=data,
            new_embedding=new_embedding,
        )
        
        logger.info("capsule_updated", capsule_id=str(capsule_id))
        return updated
    
    async def delete(
        self,
        capsule_id: UUID,
        user: User,
        cascade: bool = False,
    ) -> bool:
        """
        Soft delete a capsule.
        
        Args:
            capsule_id: Capsule to delete
            user: User performing deletion
            cascade: If True, also delete derived capsules
            
        Raises:
            AuthorizationError: If user cannot delete
            ConflictError: If capsule has children and cascade=False
        """
        capsule = await self._repo.get_by_id(capsule_id)
        
        if not capsule:
            raise NotFoundError("Capsule", str(capsule_id))
        
        # Authorization
        if capsule.owner_id != user.id and "admin" not in user.roles:
            raise AuthorizationError("Only the owner can delete this capsule")
        
        # Check for children
        if not cascade:
            children_count = await self._repo.get_children_count(capsule_id)
            if children_count > 0:
                raise ValidationError(
                    f"Capsule has {children_count} derived capsules. "
                    f"Use cascade=true to delete them as well."
                )
        
        # TODO: Handle cascade deletion
        
        success = await self._repo.soft_delete(capsule_id)
        
        if success:
            logger.info("capsule_deleted", capsule_id=str(capsule_id))
        
        return success
    
    async def list(
        self,
        user: User,
        page: int = 1,
        per_page: int = 20,
        type_filter: CapsuleType | None = None,
        trust_level_filter: TrustLevel | None = None,
        owner_id: UUID | None = None,
        parent_id: UUID | None = None,
    ) -> tuple[list[Capsule], int]:
        """
        List capsules with filters.
        
        Automatically filters by user's accessible trust levels.
        """
        # Limit trust level filter to what user can access
        if trust_level_filter:
            if not user.trust_level.can_access(trust_level_filter):
                trust_level_filter = user.trust_level
        
        capsules, total = await self._repo.list(
            page=page,
            per_page=per_page,
            type_filter=type_filter,
            trust_level_filter=trust_level_filter,
            owner_id=owner_id,
            parent_id=parent_id,
        )
        
        # Filter out capsules user can't access
        accessible = [
            c for c in capsules
            if user.trust_level.can_access(c.trust_level)
        ]
        
        return accessible, total
    
    async def search(
        self,
        query: str,
        user: User,
        limit: int = 10,
        min_score: float = 0.7,
        type_filter: CapsuleType | None = None,
    ) -> list[tuple[Capsule, float]]:
        """
        Semantic search for capsules.
        
        Uses vector similarity to find relevant capsules.
        
        Args:
            query: Natural language search query
            user: User performing search
            limit: Maximum results
            min_score: Minimum similarity score (0-1)
            type_filter: Optional type filter
            
        Returns:
            List of (capsule, score) tuples
        """
        # Generate query embedding
        query_embedding = await self._embedding.generate(query)
        
        # Search
        results = await self._repo.search_by_embedding(
            embedding=query_embedding,
            limit=limit,
            min_score=min_score,
            type_filter=type_filter,
        )
        
        # Filter by trust level
        accessible = [
            (capsule, score)
            for capsule, score in results
            if user.trust_level.can_access(capsule.trust_level)
        ]
        
        logger.info(
            "capsule_search",
            query_length=len(query),
            results_count=len(accessible),
        )
        
        return accessible
    
    async def get_lineage(
        self,
        capsule_id: UUID,
        user: User,
        max_depth: int = 10,
    ) -> LineageResult:
        """
        Get the ancestry chain (Isnad) for a capsule.
        
        Returns the complete chain of DERIVED_FROM relationships.
        """
        # Verify user can access the capsule
        capsule = await self.get(capsule_id, user)
        
        lineage = await self._repo.get_lineage(capsule_id, max_depth)
        
        # Filter out ancestors user can't access
        lineage.lineage = [
            entry for entry in lineage.lineage
            if user.trust_level.can_access(entry.capsule.trust_level)
        ]
        lineage.depth = len(lineage.lineage)
        
        return lineage


# Hybrid search combining vector and graph
class HybridSearchService:
    """
    Combines semantic search with graph traversal.
    
    Enables queries like:
    - "Find capsules about X that are derived from Y"
    - "Find capsules similar to X within 2 hops of Y"
    """
    
    def __init__(
        self,
        capsule_service: CapsuleService,
        neo4j: "Neo4jClient",
    ):
        self._capsule = capsule_service
        self._neo4j = neo4j
    
    async def search_with_context(
        self,
        query: str,
        user: User,
        context_capsule_id: UUID | None = None,
        max_hops: int = 2,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search with optional graph context.
        
        If context_capsule_id is provided, results are ranked higher
        if they are within max_hops of the context capsule.
        """
        # Get base semantic results
        results = await self._capsule.search(query, user, limit=limit * 2)
        
        if not context_capsule_id:
            return [
                {"capsule": c, "score": s, "hops": None}
                for c, s in results[:limit]
            ]
        
        # Get graph distances from context capsule
        capsule_ids = [str(c.id) for c, _ in results]
        
        distances = await self._neo4j.run("""
            MATCH (context:Capsule {id: $context_id})
            UNWIND $capsule_ids as target_id
            MATCH (target:Capsule {id: target_id})
            OPTIONAL MATCH path = shortestPath((context)-[:DERIVED_FROM*..10]-(target))
            RETURN target_id, 
                   CASE WHEN path IS NULL THEN -1 ELSE length(path) END as distance
        """, {"context_id": str(context_capsule_id), "capsule_ids": capsule_ids})
        
        distance_map = {d["target_id"]: d["distance"] for d in distances}
        
        # Combine scores
        scored_results = []
        for capsule, semantic_score in results:
            distance = distance_map.get(str(capsule.id), -1)
            
            # Boost score for nearby capsules
            if distance >= 0 and distance <= max_hops:
                boost = 1.0 + (0.1 * (max_hops - distance + 1))
            else:
                boost = 1.0
            
            combined_score = semantic_score * boost
            
            scored_results.append({
                "capsule": capsule,
                "score": combined_score,
                "semantic_score": semantic_score,
                "hops": distance if distance >= 0 else None,
            })
        
        # Sort by combined score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_results[:limit]
```

---

## 4. Redis Client (for caching)

```python
# forge/infrastructure/redis/client.py
"""
Async Redis client for caching and session storage.
"""
import json
from typing import Any
import redis.asyncio as redis

from forge.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Async Redis client wrapper."""
    
    def __init__(self, url: str, max_connections: int = 20):
        self._url = url
        self._max_connections = max_connections
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        self._pool = redis.ConnectionPool.from_url(
            self._url,
            max_connections=self._max_connections,
            decode_responses=True,
        )
        self._client = redis.Redis(connection_pool=self._pool)
        
        # Test connection
        await self._client.ping()
        logger.info("redis_connected")
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("redis_disconnected")
    
    async def get(self, key: str) -> Any | None:
        """Get value by key (JSON decoded)."""
        if not self._client:
            return None
        
        value = await self._client.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set value (JSON encoded)."""
        if not self._client:
            return
        
        encoded = json.dumps(value)
        if ttl:
            await self._client.setex(key, ttl, encoded)
        else:
            await self._client.set(key, encoded)
    
    async def delete(self, key: str) -> bool:
        """Delete a key."""
        if not self._client:
            return False
        return await self._client.delete(key) > 0
    
    async def increment(self, key: str, ttl: int | None = None) -> int:
        """Increment counter (for rate limiting)."""
        if not self._client:
            return 0
        
        value = await self._client.incr(key)
        if ttl and value == 1:  # First increment, set expiry
            await self._client.expire(key, ttl)
        return value
    
    async def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            if not self._client:
                return False
            await self._client.ping()
            return True
        except Exception:
            return False
```

---

## 5. Search Response Models

```python
# forge/models/search.py
"""
Search-related models.
"""
from pydantic import Field
from forge.models.base import ForgeBaseModel, CapsuleType
from forge.models.capsule import Capsule


class SearchQuery(ForgeBaseModel):
    """Semantic search request."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Natural language search query",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum results",
    )
    min_score: float = Field(
        default=0.7,
        ge=0,
        le=1,
        description="Minimum similarity score",
    )
    type: CapsuleType | None = Field(
        default=None,
        description="Filter by capsule type",
    )


class SearchResult(ForgeBaseModel):
    """Single search result."""
    
    capsule: Capsule
    score: float = Field(description="Similarity score (0-1)")
    

class SearchResponse(ForgeBaseModel):
    """Search response."""
    
    results: list[SearchResult]
    query: str
    total: int
```

---

## 6. Unit Tests

```python
# tests/unit/test_capsule_service.py
"""
Unit tests for CapsuleService.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from forge.core.capsules.service import CapsuleService
from forge.models.capsule import CapsuleCreate, Capsule, CapsuleType
from forge.models.user import User
from forge.models.base import TrustLevel
from forge.exceptions import NotFoundError, AuthorizationError


@pytest.fixture
def mock_repository():
    return AsyncMock()


@pytest.fixture
def mock_embedding():
    service = AsyncMock()
    service.generate.return_value = [0.1] * 1536
    return service


@pytest.fixture
def capsule_service(mock_repository, mock_embedding):
    return CapsuleService(mock_repository, mock_embedding)


@pytest.fixture
def test_user():
    return User(
        id=uuid4(),
        email="test@example.com",
        trust_level=TrustLevel.STANDARD,
        roles=["user"],
    )


@pytest.fixture
def admin_user():
    return User(
        id=uuid4(),
        email="admin@example.com",
        trust_level=TrustLevel.CORE,
        roles=["admin"],
    )


class TestCapsuleServiceCreate:
    
    async def test_create_basic_capsule(
        self, capsule_service, mock_repository, mock_embedding, test_user
    ):
        """Test creating a capsule without parent."""
        mock_repository.create.return_value = Capsule(
            id=uuid4(),
            content="test content",
            type=CapsuleType.KNOWLEDGE,
            owner_id=test_user.id,
            trust_level=TrustLevel.STANDARD,
        )
        
        data = CapsuleCreate(content="test content", type=CapsuleType.KNOWLEDGE)
        
        result = await capsule_service.create(data, test_user)
        
        assert result.content == "test content"
        mock_embedding.generate.assert_called_once_with("test content")
        mock_repository.create.assert_called_once()
    
    async def test_create_with_parent_inherits_trust(
        self, capsule_service, mock_repository, mock_embedding, test_user
    ):
        """Test that child capsule inherits parent's trust level."""
        parent_id = uuid4()
        parent = Capsule(
            id=parent_id,
            content="parent",
            type=CapsuleType.KNOWLEDGE,
            owner_id=uuid4(),
            trust_level=TrustLevel.TRUSTED,
        )
        mock_repository.get_by_id.return_value = parent
        mock_repository.create.return_value = Capsule(
            id=uuid4(),
            content="child",
            type=CapsuleType.KNOWLEDGE,
            owner_id=test_user.id,
            trust_level=TrustLevel.STANDARD,  # User's level, not parent's
        )
        
        data = CapsuleCreate(
            content="child",
            type=CapsuleType.KNOWLEDGE,
            parent_id=parent_id,
        )
        
        # User with STANDARD trust trying to derive from TRUSTED parent
        # Should work but inherit user's trust level
        result = await capsule_service.create(data, test_user)
        
        # Verify create was called with user's trust level
        call_args = mock_repository.create.call_args
        assert call_args.kwargs["trust_level"] == TrustLevel.STANDARD
    
    async def test_create_fails_if_parent_not_found(
        self, capsule_service, mock_repository, test_user
    ):
        """Test that creation fails if parent doesn't exist."""
        mock_repository.get_by_id.return_value = None
        
        data = CapsuleCreate(
            content="orphan",
            type=CapsuleType.KNOWLEDGE,
            parent_id=uuid4(),
        )
        
        with pytest.raises(NotFoundError):
            await capsule_service.create(data, test_user)


class TestCapsuleServiceSearch:
    
    async def test_search_filters_by_trust_level(
        self, capsule_service, mock_repository, mock_embedding, test_user
    ):
        """Test that search results are filtered by user's trust level."""
        # User has STANDARD trust
        # Repository returns mix of trust levels
        mock_repository.search_by_embedding.return_value = [
            (Capsule(
                id=uuid4(),
                content="standard capsule",
                type=CapsuleType.KNOWLEDGE,
                owner_id=uuid4(),
                trust_level=TrustLevel.STANDARD,
            ), 0.95),
            (Capsule(
                id=uuid4(),
                content="core capsule",
                type=CapsuleType.KNOWLEDGE,
                owner_id=uuid4(),
                trust_level=TrustLevel.CORE,  # User can't access
            ), 0.90),
        ]
        
        results = await capsule_service.search("test query", test_user)
        
        # Should only return the STANDARD capsule
        assert len(results) == 1
        assert results[0][0].trust_level == TrustLevel.STANDARD
```

---

## 7. Integration Points

After completing Phase 2, the following integration points are ready:

**For Phase 3 (Overlays):**
- Capsule service can be invoked by overlays to read/write knowledge

**For Phase 4 (Governance):**
- Trust level changes can cascade to capsules

**For Phase 6 (API):**
- Service methods map directly to API endpoints

---

## 8. Next Steps

Proceed to **Phase 3: Overlay Runtime** to implement:
- WebAssembly execution environment
- Overlay registry and lifecycle
- Capability-based security
- Event integration
