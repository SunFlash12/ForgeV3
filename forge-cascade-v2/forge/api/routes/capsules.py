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
from pydantic import BaseModel, Field

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
)
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    CapsuleType,
    ContentBlock,
)
from forge.models.events import Event, EventType


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateCapsuleRequest(BaseModel):
    """Request to create a new capsule."""
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(..., min_length=1)
    type: CapsuleType = CapsuleType.KNOWLEDGE
    parent_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateCapsuleRequest(BaseModel):
    """Request to update a capsule."""
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


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
            type=capsule.type.value,
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
    pages: int


class LineageResponse(BaseModel):
    """Capsule lineage (Isnad) response."""
    capsule: CapsuleResponse
    ancestors: list[CapsuleResponse]
    descendants: list[CapsuleResponse]
    depth: int
    trust_gradient: list[float]


class SearchRequest(BaseModel):
    """Semantic search request."""
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


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
        action="create_capsule",
        data=capsule_data.model_dump(),
        user_id=user.id,
        trust_score=float(user.trust_flame),
    )
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Capsule creation failed pipeline validation",
        )
    
    # Create in database
    capsule = await capsule_repo.create(capsule_data)
    
    # Emit event
    await event_system.emit(Event(
        type=EventType.CAPSULE_CREATED,
        source="api",
        data={
            "capsule_id": capsule.id,
            "creator_id": user.id,
            "title": capsule.title,
            "type": capsule.type.value,
            "parent_id": capsule.parent_id,
        },
    ))
    
    # Audit log
    await audit_repo.log_action(
        action="capsule_created",
        entity_type="capsule",
        entity_id=capsule.id,
        user_id=user.id,
        details={"title": capsule.title, "type": capsule.type.value},
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
        pages=(total + pagination.per_page - 1) // pagination.per_page,
    )


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
    capsule = await capsule_repo.get_by_id(capsule_id)
    
    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )
    
    # Emit access event (for tracking)
    await event_system.emit(Event(
        type=EventType.CAPSULE_ACCESSED,
        source="api",
        data={"capsule_id": capsule_id, "user_id": user.id},
    ))
    
    return CapsuleResponse.from_capsule(capsule)


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
    
    Only the creator or users with TRUSTED+ can update.
    Updates are versioned.
    """
    capsule = await capsule_repo.get_by_id(capsule_id)
    
    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )
    
    # Check permissions
    if capsule.owner_id != user.id and user.trust_flame < 80:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner or TRUSTED users can update capsules",
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
        action="update_capsule",
        data={"capsule_id": capsule_id, "updates": updates},
        user_id=user.id,
        trust_score=float(user.trust_flame),
    )
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Update failed pipeline validation",
        )
    
    # Update in database
    updated = await capsule_repo.update(capsule_id, CapsuleUpdate(**updates))
    
    # Emit event
    await event_system.emit(Event(
        type=EventType.CAPSULE_UPDATED,
        source="api",
        data={
            "capsule_id": capsule_id,
            "user_id": user.id,
            "fields": list(updates.keys()),
        },
    ))
    
    # Audit log
    await audit_repo.log_action(
        action="capsule_updated",
        entity_type="capsule",
        entity_id=capsule_id,
        user_id=user.id,
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
    
    Requires TRUSTED trust level. Soft-delete preserves lineage.
    """
    capsule = await capsule_repo.get_by_id(capsule_id)
    
    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )
    
    # Delete
    await capsule_repo.delete(capsule_id)
    
    # Emit event
    await event_system.emit(Event(
        type=EventType.CAPSULE_DELETED,
        source="api",
        data={"capsule_id": capsule_id, "user_id": user.id},
    ))
    
    # Audit log
    await audit_repo.log_action(
        action="capsule_deleted",
        entity_type="capsule",
        entity_id=capsule_id,
        user_id=user.id,
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
    
    return LineageResponse(
        capsule=CapsuleResponse.from_capsule(capsule),
        ancestors=[CapsuleResponse.from_capsule(c) for c in ancestors],
        descendants=[CapsuleResponse.from_capsule(c) for c in descendants],
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
    await event_system.emit(Event(
        type=EventType.CAPSULE_LINKED,
        source="api",
        data={
            "capsule_id": capsule_id,
            "parent_id": parent_id,
            "user_id": user.id,
        },
    ))
    
    await audit_repo.log_action(
        action="capsule_linked",
        entity_type="capsule",
        entity_id=capsule_id,
        user_id=user.id,
        details={"parent_id": parent_id},
        correlation_id=correlation_id,
    )
    
    return CapsuleResponse.from_capsule(updated)


# =============================================================================
# Search Endpoints
# =============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_capsules(
    request: SearchRequest,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
) -> SearchResponse:
    """
    Semantic search across capsules.
    """
    results, scores = await capsule_repo.semantic_search(
        query=request.query,
        limit=request.limit,
        filters=request.filters,
    )
    
    return SearchResponse(
        query=request.query,
        results=[CapsuleResponse.from_capsule(c) for c in results],
        scores=scores,
        total=len(results),
    )


@router.get("/search/recent")
async def get_recent_capsules(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[CapsuleResponse]:
    """
    Get most recently created capsules.
    """
    capsules = await capsule_repo.get_recent(limit=limit)
    return [CapsuleResponse.from_capsule(c) for c in capsules]


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
        pages=(total + pagination.per_page - 1) // pagination.per_page,
    )


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
    await event_system.emit(Event(
        type=EventType.CAPSULE_CREATED,
        source="api",
        data={
            "capsule_id": forked.id,
            "creator_id": user.id,
            "parent_id": capsule_id,
            "fork": True,
            "evolution_reason": request.evolution_reason,
        },
    ))
    
    # Audit log
    await audit_repo.log_action(
        action="capsule_forked",
        entity_type="capsule",
        entity_id=forked.id,
        user_id=user.id,
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
    
    # Check ownership
    if capsule.owner_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to archive this capsule",
        )
    
    # Archive the capsule
    update_data = CapsuleUpdate(is_archived=True)
    archived = await capsule_repo.update(capsule_id, update_data)
    
    # Audit log
    await audit_repo.log_action(
        action="capsule_archived",
        entity_type="capsule",
        entity_id=capsule_id,
        user_id=user.id,
        details={"archived": True},
        correlation_id=correlation_id,
    )
    
    return CapsuleResponse.from_capsule(archived)
