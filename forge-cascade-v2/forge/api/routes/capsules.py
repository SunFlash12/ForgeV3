"""
Forge Cascade V2 - Capsule Routes
Endpoints for knowledge capsule management.

Provides:
- Capsule CRUD operations
- Content versioning
- Lineage (Isnad) queries
- Semantic search
- Pipeline processing
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field, field_validator

from forge.api.dependencies import (
    CapsuleRepoDep,
    AuditRepoDep,
    PipelineDep,
    EventSystemDep,
    ActiveUserDep,
    SandboxUserDep,
    StandardUserDep,
    TrustedUserDep,
    PaginationDep,
    CorrelationIdDep,
    EmbeddingServiceDep,
)
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    CapsuleType,
    ContentBlock,
)
from forge.models.events import Event, EventType

# Resilience integration - caching, validation, metrics
from forge.resilience.integration import (
    get_cached_capsule,
    cache_capsule,
    invalidate_capsule_cache,
    get_cached_search,
    cache_search_results,
    get_cached_lineage,
    cache_lineage,
    validate_capsule_content,
    check_content_validation,
    record_capsule_created,
    record_capsule_updated,
    record_capsule_deleted,
    record_search,
    record_lineage_query,
    record_cache_hit,
    record_cache_miss,
)
import hashlib
import time


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCapsuleRequest(BaseModel):
    """Request to create a new capsule."""
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(..., min_length=1, max_length=1_000_000)  # 1MB max
    type: CapsuleType = CapsuleType.KNOWLEDGE
    parent_id: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)  # Max 50 tags
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tag list."""
        if len(v) > 50:
            raise ValueError("Maximum 50 tags allowed")
        for tag in v:
            if len(tag) > 100:
                raise ValueError(f"Tag '{tag[:20]}...' too long (max 100 chars)")
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate metadata size."""
        if len(v) > 20:
            raise ValueError("Maximum 20 metadata keys allowed")
        import json
        total_size = len(json.dumps(v))
        if total_size > 65536:  # 64KB
            raise ValueError("Metadata too large (max 64KB)")
        return v


class UpdateCapsuleRequest(BaseModel):
    """Request to update a capsule."""
    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=1_000_000)  # 1MB max
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tag list."""
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Maximum 50 tags allowed")
        for tag in v:
            if len(tag) > 100:
                raise ValueError(f"Tag '{tag[:20]}...' too long (max 100 chars)")
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate metadata size."""
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("Maximum 20 metadata keys allowed")
        import json
        total_size = len(json.dumps(v))
        if total_size > 65536:  # 64KB
            raise ValueError("Metadata too large (max 64KB)")
        return v


class CapsuleResponse(BaseModel):
    """Capsule response model."""
    id: str
    title: str | None
    content: str
    type: str
    owner_id: str
    trust_level: str
    version: str
    parent_id: str | None
    tags: list[str]
    metadata: dict[str, Any]
    view_count: int
    fork_count: int
    is_archived: bool
    created_at: str
    updated_at: str
    
    @classmethod
    def from_capsule(cls, capsule: Capsule) -> "CapsuleResponse":
        return cls(
            id=capsule.id,
            title=capsule.title,
            content=capsule.content,
            type=capsule.type.value if hasattr(capsule.type, 'value') else str(capsule.type),
            owner_id=capsule.owner_id,
            trust_level=capsule.trust_level.value if hasattr(capsule.trust_level, 'value') else str(capsule.trust_level),
            version=capsule.version,
            parent_id=capsule.parent_id,
            tags=capsule.tags,
            metadata=capsule.metadata,
            view_count=capsule.view_count,
            fork_count=capsule.fork_count,
            is_archived=capsule.is_archived,
            created_at=capsule.created_at.isoformat() if capsule.created_at else "",
            updated_at=capsule.updated_at.isoformat() if capsule.updated_at else "",
        )


class CapsuleListResponse(BaseModel):
    """Paginated list of capsules."""
    items: list[CapsuleResponse]
    total: int
    page: int
    per_page: int
    total_pages: int  # Frontend expects total_pages, not pages


class LineageResponse(BaseModel):
    """Capsule lineage (Isnad) response."""
    capsule: CapsuleResponse
    ancestors: list[CapsuleResponse]
    descendants: list[CapsuleResponse]
    depth: int
    trust_gradient: list[float]


class SearchRequest(BaseModel):
    """Semantic search request."""
    query: str = Field(..., min_length=1, max_length=2000)  # Prevent DoS via huge queries
    limit: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize search query to prevent injection and control character issues."""
        import re
        # Remove control characters (except standard whitespace)
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)
        # Normalize whitespace (collapse multiple spaces, strip)
        v = ' '.join(v.split())
        if not v:
            raise ValueError("Search query cannot be empty after sanitization")
        return v


class SearchResponse(BaseModel):
    """Search results."""
    query: str
    results: list[CapsuleResponse]
    scores: list[float]
    total: int


# =============================================================================
# CRUD Endpoints
# =============================================================================

@router.post("/", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def create_capsule(
    request: CreateCapsuleRequest,
    user: SandboxUserDep,  # Minimum SANDBOX trust to create
    capsule_repo: CapsuleRepoDep,
    pipeline: PipelineDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CapsuleResponse:
    """
    Create a new knowledge capsule.

    The capsule will be processed through the 7-phase cascade pipeline
    for validation, analysis, and governance checks.
    """
    # Resilience: Content validation for security threats
    validation_result = await validate_capsule_content(request.content)
    check_content_validation(validation_result)

    # Build capsule create model
    capsule_id = f"cap_{uuid4().hex[:12]}"

    capsule_data = CapsuleCreate(
        content=request.content,
        type=request.type,
        title=request.title,
        parent_id=request.parent_id,
        tags=request.tags,
        metadata=request.metadata,
    )

    # Process through pipeline
    result = await pipeline.execute(
        input_data=capsule_data.model_dump(),
        triggered_by="create_capsule",
        user_id=user.id,
        trust_flame=int(user.trust_flame),
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Capsule creation failed pipeline validation",
        )

    # Create in database
    capsule = await capsule_repo.create(capsule_data, owner_id=user.id)

    # Get type value safely (could be enum or string)
    type_value = capsule.type.value if hasattr(capsule.type, 'value') else str(capsule.type)

    # Resilience: Record metrics
    record_capsule_created(type_value)

    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_CREATED,
        payload={
            "capsule_id": capsule.id,
            "creator_id": user.id,
            "title": capsule.title,
            "type": type_value,
            "parent_id": capsule.parent_id,
        },
        source="api",
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule.id,
        action="create",
        details={"title": capsule.title, "type": type_value},
        correlation_id=correlation_id,
    )

    return CapsuleResponse.from_capsule(capsule)


@router.get("/", response_model=CapsuleListResponse)
async def list_capsules(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    pagination: PaginationDep,
    capsule_type: CapsuleType | None = None,
    owner_id: str | None = None,
    tag: str | None = None,
) -> CapsuleListResponse:
    """
    List capsules with optional filtering.
    """
    filters = {}
    if capsule_type:
        filters["type"] = capsule_type.value
    if owner_id:
        filters["owner_id"] = owner_id
    if tag:
        filters["tag"] = tag
    
    capsules, total = await capsule_repo.list(
        offset=pagination.offset,
        limit=pagination.per_page,
        filters=filters,
    )
    
    return CapsuleListResponse(
        items=[CapsuleResponse.from_capsule(c) for c in capsules],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=(total + pagination.per_page - 1) // pagination.per_page,
    )


# =============================================================================
# Search Endpoints (must be before /{capsule_id} routes)
# =============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_capsules(
    request: SearchRequest,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    embedding_service: EmbeddingServiceDep,
) -> SearchResponse:
    """
    Semantic search across capsules.
    """
    start_time = time.perf_counter()

    # Resilience: Create cache key from query hash
    import json
    cache_key_data = json.dumps({
        "query": request.query,
        "limit": request.limit,
        "filters": request.filters,
    }, sort_keys=True)
    query_hash = hashlib.sha256(cache_key_data.encode()).hexdigest()[:16]

    # Try cache first
    cached = await get_cached_search(query_hash)
    if cached:
        record_cache_hit("search")
        latency = time.perf_counter() - start_time
        record_search(latency, len(cached))
        return SearchResponse(
            query=request.query,
            results=[CapsuleResponse(**c) for c in cached.get("results", [])],
            scores=cached.get("scores", []),
            total=cached.get("total", 0),
        )

    record_cache_miss("search")

    # Convert text query to embedding vector
    embedding_result = await embedding_service.embed(request.query)

    # Extract filters
    owner_id = request.filters.get("owner_id") if request.filters else None
    capsule_type = request.filters.get("type") if request.filters else None

    # Search with embedding
    search_results = await capsule_repo.semantic_search(
        query_embedding=embedding_result.embedding,
        limit=request.limit,
        owner_id=owner_id,
    )

    # Extract capsules and scores from results
    capsules = [r.capsule for r in search_results]
    scores = [r.score for r in search_results]

    # Build response
    response_data = [CapsuleResponse.from_capsule(c) for c in capsules]

    # Resilience: Cache results and record metrics
    await cache_search_results(
        query_hash,
        {
            "results": [r.model_dump() for r in response_data],
            "scores": scores,
            "total": len(capsules),
        },
        ttl=600,  # 10 minute cache for search results
    )

    latency = time.perf_counter() - start_time
    record_search(latency, len(capsules))

    return SearchResponse(
        query=request.query,
        results=response_data,
        scores=scores,
        total=len(capsules),
    )


@router.get("/search/recent")
async def get_recent_capsules(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    Get most recently created capsules.
    """
    capsules = await capsule_repo.get_recent(limit=limit)
    return {"capsules": [CapsuleResponse.from_capsule(c) for c in capsules]}


@router.get("/search/by-owner/{owner_id}")
async def get_capsules_by_owner(
    owner_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    pagination: PaginationDep,
) -> CapsuleListResponse:
    """
    Get capsules by a specific owner.
    """
    capsules, total = await capsule_repo.list(
        offset=pagination.offset,
        limit=pagination.per_page,
        filters={"owner_id": owner_id},
    )

    return CapsuleListResponse(
        items=[CapsuleResponse.from_capsule(c) for c in capsules],
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        total_pages=(total + pagination.per_page - 1) // pagination.per_page,
    )


# =============================================================================
# Capsule by ID Endpoints
# =============================================================================

@router.get("/{capsule_id}", response_model=CapsuleResponse)
async def get_capsule(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    event_system: EventSystemDep,
) -> CapsuleResponse:
    """
    Get a specific capsule by ID.
    """
    # Resilience: Try cache first
    cached = await get_cached_capsule(capsule_id)
    if cached:
        record_cache_hit("capsule")
        # Still emit access event for tracking
        await event_system.emit(
            event_type=EventType.CAPSULE_ACCESSED,
            payload={"capsule_id": capsule_id, "user_id": user.id, "cached": True},
            source="api",
        )
        return CapsuleResponse(**cached)

    record_cache_miss("capsule")

    capsule = await capsule_repo.get_by_id(capsule_id)

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Resilience: Cache the result
    response = CapsuleResponse.from_capsule(capsule)
    await cache_capsule(capsule_id, response.model_dump())

    # Emit access event (for tracking)
    await event_system.emit(
        event_type=EventType.CAPSULE_ACCESSED,
        payload={"capsule_id": capsule_id, "user_id": user.id},
        source="api",
    )

    return response


@router.patch("/{capsule_id}", response_model=CapsuleResponse)
async def update_capsule(
    capsule_id: str,
    request: UpdateCapsuleRequest,
    user: StandardUserDep,  # Minimum STANDARD trust to update
    capsule_repo: CapsuleRepoDep,
    pipeline: PipelineDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CapsuleResponse:
    """
    Update a capsule.

    Only the owner can update their capsules.
    Admins can update any capsule.
    """
    from forge.security.authorization import is_admin

    # Resilience: Content validation if content is being updated
    if request.content is not None:
        validation_result = await validate_capsule_content(request.content)
        check_content_validation(validation_result)

    capsule = await capsule_repo.get_by_id(capsule_id)

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # SECURITY FIX: Only owner OR admin can update
    is_owner = capsule.owner_id == user.id
    user_is_admin = is_admin(user)

    if not is_owner and not user_is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the capsule owner can update this capsule",
        )

    # Build update
    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.content is not None:
        updates["content"] = request.content
    if request.tags is not None:
        updates["tags"] = request.tags
    if request.metadata is not None:
        updates["metadata"] = {**capsule.metadata, **request.metadata}

    if not updates:
        return CapsuleResponse.from_capsule(capsule)

    # Process through pipeline
    result = await pipeline.execute(
        input_data={"capsule_id": capsule_id, "updates": updates},
        triggered_by="update_capsule",
        user_id=user.id,
        trust_flame=int(user.trust_flame),
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Update failed pipeline validation",
        )

    # Update in database
    updated = await capsule_repo.update(capsule_id, CapsuleUpdate(**updates))

    # Get type value safely
    type_value = updated.type.value if hasattr(updated.type, 'value') else str(updated.type)

    # Resilience: Invalidate cache and record metrics
    await invalidate_capsule_cache(capsule_id)
    record_capsule_updated(type_value)

    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_UPDATED,
        payload={
            "capsule_id": capsule_id,
            "user_id": user.id,
            "fields": list(updates.keys()),
        },
        source="api",
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="update",
        details={"fields": list(updates.keys())},
        correlation_id=correlation_id,
    )

    return CapsuleResponse.from_capsule(updated)


@router.delete("/{capsule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capsule(
    capsule_id: str,
    user: TrustedUserDep,  # Minimum TRUSTED to delete
    capsule_repo: CapsuleRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
):
    """
    Delete a capsule.

    Only the owner can delete their capsules.
    Admins can delete any capsule.
    Requires TRUSTED trust level.
    """
    from forge.security.authorization import is_admin

    capsule = await capsule_repo.get_by_id(capsule_id)

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Get type value for metrics before deletion
    type_value = capsule.type.value if hasattr(capsule.type, 'value') else str(capsule.type)

    # SECURITY FIX: Only owner OR admin can delete
    is_owner = capsule.owner_id == user.id
    user_is_admin = is_admin(user)

    if not is_owner and not user_is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the capsule owner can delete this capsule",
        )

    # Delete
    await capsule_repo.delete(capsule_id)

    # Resilience: Invalidate cache and record metrics
    await invalidate_capsule_cache(capsule_id)
    record_capsule_deleted(type_value)

    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_DELETED,
        payload={"capsule_id": capsule_id, "user_id": user.id},
        source="api",
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="delete",
        correlation_id=correlation_id,
    )


# =============================================================================
# Lineage Endpoints
# =============================================================================

@router.get("/{capsule_id}/lineage", response_model=LineageResponse)
async def get_lineage(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    depth: int = Query(default=5, ge=1, le=20),
) -> LineageResponse:
    """
    Get capsule lineage (Isnad chain).

    Returns ancestors and descendants up to specified depth.
    """
    start_time = time.perf_counter()

    # Resilience: Try cache first
    cached = await get_cached_lineage(capsule_id, depth)
    if cached:
        record_cache_hit("lineage")
        latency = time.perf_counter() - start_time
        record_lineage_query(latency, depth)
        return LineageResponse(
            capsule=CapsuleResponse(**cached["capsule"]),
            ancestors=[CapsuleResponse(**a) for a in cached.get("ancestors", [])],
            descendants=[CapsuleResponse(**d) for d in cached.get("descendants", [])],
            depth=cached.get("depth", 0),
            trust_gradient=cached.get("trust_gradient", []),
        )

    record_cache_miss("lineage")

    capsule = await capsule_repo.get_by_id(capsule_id)

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Get lineage
    ancestors = await capsule_repo.get_ancestors(capsule_id, max_depth=depth)
    descendants = await capsule_repo.get_descendants(capsule_id, max_depth=depth)

    # Calculate trust gradient (using trust_level enum value)
    all_in_chain = [capsule] + ancestors + descendants
    trust_gradient = [float(c.trust_level.value) if hasattr(c.trust_level, 'value') else float(c.trust_level) for c in sorted(all_in_chain, key=lambda x: x.created_at or datetime.min)]

    # Build response
    capsule_response = CapsuleResponse.from_capsule(capsule)
    ancestor_responses = [CapsuleResponse.from_capsule(c) for c in ancestors]
    descendant_responses = [CapsuleResponse.from_capsule(c) for c in descendants]

    # Resilience: Cache lineage and record metrics
    await cache_lineage(
        capsule_id,
        depth,
        {
            "capsule": capsule_response.model_dump(),
            "ancestors": [a.model_dump() for a in ancestor_responses],
            "descendants": [d.model_dump() for d in descendant_responses],
            "depth": len(ancestors),
            "trust_gradient": trust_gradient,
        },
        ttl=1800,  # 30 minute cache for lineage (more stable)
    )

    latency = time.perf_counter() - start_time
    record_lineage_query(latency, depth)

    return LineageResponse(
        capsule=capsule_response,
        ancestors=ancestor_responses,
        descendants=descendant_responses,
        depth=len(ancestors),
        trust_gradient=trust_gradient,
    )


@router.post("/{capsule_id}/link/{parent_id}", response_model=CapsuleResponse)
async def link_capsule(
    capsule_id: str,
    parent_id: str,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CapsuleResponse:
    """
    Link a capsule to a parent (create Isnad relationship).
    """
    # Verify both exist
    capsule = await capsule_repo.get_by_id(capsule_id)
    parent = await capsule_repo.get_by_id(parent_id)
    
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")
    
    # Check for cycles
    ancestors = await capsule_repo.get_ancestors(parent_id, max_depth=50)
    if any(a.id == capsule_id for a in ancestors):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create circular reference",
        )
    
    # Create link
    updated = await capsule_repo.add_parent(capsule_id, parent_id)
    
    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_LINKED,
        payload={
            "capsule_id": capsule_id,
            "parent_id": parent_id,
            "user_id": user.id,
        },
        source="api",
    )
    
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="linked",
        details={"parent_id": parent_id},
        correlation_id=correlation_id,
    )
    
    return CapsuleResponse.from_capsule(updated)


# =============================================================================
# Fork Endpoint - Create child capsule (Symbolic Inheritance)
# =============================================================================

class ForkCapsuleRequest(BaseModel):
    """Request to fork (derive from) a capsule."""
    title: str | None = None
    content: str | None = None
    evolution_reason: str = Field(..., min_length=1, description="Why this fork was created")


@router.post("/{capsule_id}/fork", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def fork_capsule(
    capsule_id: str,
    request: ForkCapsuleRequest,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CapsuleResponse:
    """
    Fork a capsule to create a derived child capsule.
    
    This implements symbolic inheritance - the new capsule maintains
    an explicit lineage link to its parent.
    """
    # Get parent capsule
    parent = await capsule_repo.get_by_id(capsule_id)
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent capsule not found",
        )
    
    # Create forked capsule
    fork_data = CapsuleCreate(
        title=request.title or f"Fork of: {parent.title}",
        content=request.content or parent.content,
        type=parent.type,
        summary=parent.summary,
        tags=parent.tags.copy() if parent.tags else [],
        metadata={
            **(parent.metadata or {}),
            "forked_from": capsule_id,
            "fork_reason": request.evolution_reason,
        },
        parent_id=capsule_id,
        evolution_reason=request.evolution_reason,
    )
    
    forked = await capsule_repo.create(fork_data, owner_id=user.id)
    
    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_CREATED,
        payload={
            "capsule_id": forked.id,
            "creator_id": user.id,
            "parent_id": capsule_id,
            "fork": True,
            "evolution_reason": request.evolution_reason,
        },
        source="api",
    )
    
    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=forked.id,
        action="fork",
        details={
            "parent_id": capsule_id,
            "evolution_reason": request.evolution_reason,
        },
        correlation_id=correlation_id,
    )
    
    return CapsuleResponse.from_capsule(forked)


@router.post("/{capsule_id}/archive", response_model=CapsuleResponse)
async def archive_capsule(
    capsule_id: str,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CapsuleResponse:
    """
    Archive a capsule (soft delete).
    
    Archived capsules are not deleted but marked as inactive.
    They can still be referenced by child capsules for lineage.
    """
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )
    
    # Check ownership - use consistent is_admin() check
    from forge.security.authorization import is_admin
    if capsule.owner_id != user.id and not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to archive this capsule",
        )
    
    # Archive the capsule
    update_data = CapsuleUpdate(is_archived=True)
    archived = await capsule_repo.update(capsule_id, update_data)
    
    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="archive",
        details={"archived": True},
        correlation_id=correlation_id,
    )
    
    return CapsuleResponse.from_capsule(archived)
