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

import hashlib
import time
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    CapsuleRepoDep,
    CorrelationIdDep,
    EmbeddingServiceDep,
    EventSystemDep,
    PaginationDep,
    PipelineDep,
    SandboxUserDep,
    StandardUserDep,
    TrustedUserDep,
)
from forge.models.base import CapsuleType
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    IntegrityReport,
    IntegrityStatus,
    LineageIntegrityReport,
)
from forge.models.events import EventType
from forge.models.user import KeyStorageStrategy

# Resilience integration - caching, validation, metrics
from forge.resilience.integration import (
    cache_capsule,
    cache_lineage,
    cache_search_results,
    check_content_validation,
    get_cached_capsule,
    get_cached_lineage,
    get_cached_search,
    invalidate_capsule_cache,
    record_cache_hit,
    record_cache_miss,
    record_capsule_created,
    record_capsule_deleted,
    record_capsule_updated,
    record_lineage_query,
    record_search,
    validate_capsule_content,
)
from forge.security.capsule_integrity import CapsuleIntegrityService
from forge.security.key_management import (
    KeyManagementService,
    KeyNotFoundError,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


# =============================================================================
# Background Tasks
# =============================================================================


async def run_semantic_edge_detection(capsule_id: str, user_id: str) -> None:
    """
    Background task to analyze a capsule for semantic relationships.

    This runs asynchronously after capsule creation to detect
    SUPPORTS, CONTRADICTS, ELABORATES relationships with existing capsules.
    """
    try:
        from forge.config import get_settings
        from forge.database.client import Neo4jClient
        from forge.repositories.capsule_repository import CapsuleRepository
        from forge.services.semantic_edge_detector import (
            DetectionConfig,
            SemanticEdgeDetector,
        )

        settings = get_settings()

        # Only run in production or if explicitly enabled
        if settings.app_env == "development" and not getattr(
            settings, "enable_dev_semantic_detection", False
        ):
            logger.debug(
                "semantic_detection_skipped", reason="development mode", capsule_id=capsule_id
            )
            return

        # LIMITATION (Audit 7 - Session 3): This background task creates its own Neo4jClient
        # instead of using the application's connection pool. This is a known limitation because
        # FastAPI BackgroundTasks run outside the request lifecycle, so the request-scoped DB
        # dependency is unavailable. Consider migrating to a task queue (Celery/ARQ) with
        # shared connection pooling for production workloads.
        db_client = Neo4jClient()
        await db_client.connect()

        try:
            capsule_repo = CapsuleRepository(db_client)

            # Get the capsule
            capsule = await capsule_repo.get_by_id(capsule_id)
            if not capsule:
                logger.warning("semantic_detection_capsule_not_found", capsule_id=capsule_id)
                return

            # Configure detector with conservative settings
            config = DetectionConfig(
                similarity_threshold=0.75,  # Higher threshold for auto-detection
                confidence_threshold=0.8,  # Require high confidence
                max_candidates=10,  # Limit candidates for performance
                enabled=True,
            )

            detector = SemanticEdgeDetector(capsule_repo, config=config)
            result = await detector.analyze_capsule(capsule, created_by=user_id)

            logger.info(
                "semantic_detection_complete",
                capsule_id=capsule_id,
                candidates_analyzed=result.candidates_analyzed,
                edges_created=result.edges_created,
                duration_ms=result.duration_ms,
            )

        finally:
            await db_client.close()

    except (RuntimeError, ValueError, TypeError, OSError) as e:
        logger.error(
            "semantic_detection_failed",
            capsule_id=capsule_id,
            error=str(e),
        )


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
    def from_capsule(cls, capsule: Capsule) -> CapsuleResponse:
        return cls(
            id=capsule.id,
            title=capsule.title,
            content=capsule.content,
            type=capsule.type.value if hasattr(capsule.type, "value") else str(capsule.type),
            owner_id=capsule.owner_id,
            trust_level=str(capsule.trust_level.value)
            if hasattr(capsule.trust_level, "value")
            else str(capsule.trust_level),
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

    # SECURITY FIX: Whitelist allowed filter keys to prevent injection
    ALLOWED_FILTER_KEYS: ClassVar[set[str]] = {
        "owner_id",
        "type",
        "tag",
        "min_trust",
        "max_trust",
        "created_after",
        "created_before",
    }

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate and whitelist filter keys."""
        if not v:
            return v
        invalid_keys = set(v.keys()) - cls.ALLOWED_FILTER_KEYS
        if invalid_keys:
            raise ValueError(
                f"Invalid filter keys: {invalid_keys}. Allowed: {cls.ALLOWED_FILTER_KEYS}"
            )
        return v

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize search query to prevent injection and control character issues."""
        import re

        # Remove control characters (except standard whitespace)
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        # Normalize whitespace (collapse multiple spaces, strip)
        v = " ".join(v.split())
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
    background_tasks: BackgroundTasks,
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
    f"cap_{uuid4().hex[:12]}"

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
        error_detail = (
            result.errors[0] if result.errors else "Capsule creation failed pipeline validation"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
        )

    # Create in database
    capsule = await capsule_repo.create(capsule_data, owner_id=user.id)

    # Get type value safely (could be enum or string)
    type_value = capsule.type.value if hasattr(capsule.type, "value") else str(capsule.type)

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

    # Schedule semantic edge detection in background
    # This will auto-detect SUPPORTS, CONTRADICTS, ELABORATES relationships
    background_tasks.add_task(run_semantic_edge_detection, capsule.id, user.id)

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

    capsules, total = await capsule_repo.list_capsules(
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

    cache_key_data = json.dumps(
        {
            "query": request.query,
            "limit": request.limit,
            "filters": request.filters,
        },
        sort_keys=True,
    )
    query_hash = hashlib.sha256(cache_key_data.encode()).hexdigest()[:16]

    # Try cache first
    cached = await get_cached_search(query_hash)
    if cached:
        record_cache_hit("search")
        latency = time.perf_counter() - start_time
        record_search(latency, len(cached))
        cached_results: list[dict[str, Any]] = (
            cached.get("results", []) if isinstance(cached, dict) else []  # type: ignore[attr-defined,unused-ignore]
        )
        cached_scores: list[float] = cached.get("scores", []) if isinstance(cached, dict) else []  # type: ignore[attr-defined,unused-ignore]
        cached_total: int = cached.get("total", 0) if isinstance(cached, dict) else 0  # type: ignore[attr-defined,unused-ignore]
        return SearchResponse(
            query=request.query,
            results=[CapsuleResponse(**c) for c in cached_results],
            scores=cached_scores,
            total=cached_total,
        )

    record_cache_miss("search")

    # Convert text query to embedding vector
    embedding_result = await embedding_service.embed(request.query)

    # Extract validated filters (whitelist enforced by SearchRequest validator)
    owner_id = request.filters.get("owner_id") if request.filters else None
    capsule_type = request.filters.get("type") if request.filters else None
    min_trust_raw = request.filters.get("min_trust") if request.filters else None
    min_trust: int = int(min_trust_raw) if min_trust_raw is not None else 40

    # Search with embedding
    search_results = await capsule_repo.semantic_search(
        query_embedding=embedding_result.embedding,
        limit=request.limit,
        owner_id=owner_id,
        capsule_type=capsule_type,
        min_trust=min_trust,
    )

    # Extract capsules and scores from results
    capsules = [r.capsule for r in search_results]
    scores = [r.score for r in search_results]

    # Build response
    response_data = [CapsuleResponse.from_capsule(c) for c in capsules]

    # Resilience: Cache results and record metrics
    # Note: cache_search_results type annotation expects list, but actually stores any value
    # We pass the dict as-is since the cache implementation handles it correctly
    from typing import cast

    search_cache_data = cast(
        list[Any],
        {
            "results": [r.model_dump() for r in response_data],
            "scores": scores,
            "total": len(capsules),
        },
    )
    await cache_search_results(
        query_hash,
        search_cache_data,
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
) -> dict[str, list[CapsuleResponse]]:
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

    Regular users can only view their own capsules.
    Admins can view any user's capsules.
    """
    from forge.security.authorization import is_admin

    # SECURITY FIX (Audit 2): Add IDOR protection
    if user.id != owner_id and not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own capsules",
        )

    capsules, total = await capsule_repo.list_capsules(
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

    # Build update data for CapsuleUpdate
    update_title: str | None = request.title
    update_content: str | None = request.content
    update_tags: list[str] | None = request.tags
    update_metadata: dict[str, Any] | None = None
    if request.metadata is not None:
        update_metadata = {**capsule.metadata, **request.metadata}

    # Check if there are any updates
    has_updates = any(
        [
            update_title is not None,
            update_content is not None,
            update_tags is not None,
            update_metadata is not None,
        ]
    )

    if not has_updates:
        return CapsuleResponse.from_capsule(capsule)

    # Create update data dict for pipeline
    updates_dict: dict[str, Any] = {}
    if update_title is not None:
        updates_dict["title"] = update_title
    if update_content is not None:
        updates_dict["content"] = update_content
    if update_tags is not None:
        updates_dict["tags"] = update_tags
    if update_metadata is not None:
        updates_dict["metadata"] = update_metadata

    # Process through pipeline
    result = await pipeline.execute(
        input_data={"capsule_id": capsule_id, "updates": updates_dict},
        triggered_by="update_capsule",
        user_id=user.id,
        trust_flame=int(user.trust_flame),
    )

    if not result.success:
        error_detail = result.errors[0] if result.errors else "Update failed pipeline validation"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
        )

    # Update in database
    capsule_update = CapsuleUpdate(
        title=update_title,
        content=update_content,
        tags=update_tags,
        metadata=update_metadata,
    )
    updated = await capsule_repo.update(capsule_id, capsule_update)

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found or update failed",
        )

    # Get type value safely
    type_value = updated.type.value if hasattr(updated.type, "value") else str(updated.type)

    # Resilience: Invalidate cache and record metrics
    await invalidate_capsule_cache(capsule_id)
    record_capsule_updated(type_value)

    # Emit event
    await event_system.emit(
        event_type=EventType.CAPSULE_UPDATED,
        payload={
            "capsule_id": capsule_id,
            "user_id": user.id,
            "fields": list(updates_dict.keys()),
        },
        source="api",
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="update",
        details={"fields": list(updates_dict.keys())},
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
) -> None:
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
    type_value = capsule.type.value if hasattr(capsule.type, "value") else str(capsule.type)

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

    # Calculate trust gradient from capsule and ancestors (which are full Capsule objects)
    # Descendants are LineageNode objects with trust_level available
    all_trust_levels: list[tuple[datetime, float]] = []

    # Add main capsule
    capsule_trust = (
        float(capsule.trust_level.value)
        if hasattr(capsule.trust_level, "value")
        else float(capsule.trust_level)
    )
    all_trust_levels.append((capsule.created_at or datetime.min, capsule_trust))

    # Add ancestors (Capsule objects)
    for a in ancestors:
        trust_val = (
            float(a.trust_level.value) if hasattr(a.trust_level, "value") else float(a.trust_level)
        )
        all_trust_levels.append((a.created_at or datetime.min, trust_val))

    # Add descendants (LineageNode objects)
    for d in descendants:
        trust_val = (
            float(d.trust_level.value) if hasattr(d.trust_level, "value") else float(d.trust_level)
        )
        all_trust_levels.append((d.created_at or datetime.min, trust_val))

    # Sort by created_at and extract trust values
    all_trust_levels.sort(key=lambda x: x[0])
    trust_gradient = [t[1] for t in all_trust_levels]

    # Build response
    capsule_response = CapsuleResponse.from_capsule(capsule)
    ancestor_responses = [CapsuleResponse.from_capsule(c) for c in ancestors]

    # Convert LineageNode to CapsuleResponse for descendants
    # LineageNode doesn't have all fields, so we create minimal responses
    descendant_responses: list[CapsuleResponse] = []
    for d in descendants:
        descendant_responses.append(
            CapsuleResponse(
                id=d.id,
                title=d.title,
                content="",  # Not available in LineageNode
                type=d.type.value if hasattr(d.type, "value") else str(d.type),
                owner_id="",  # Not available in LineageNode
                trust_level=str(d.trust_level.value)
                if hasattr(d.trust_level, "value")
                else str(d.trust_level),
                version=d.version,
                parent_id=None,  # Not available in LineageNode
                tags=[],  # Not available in LineageNode
                metadata={},  # Not available in LineageNode
                view_count=0,  # Not available in LineageNode
                fork_count=0,  # Not available in LineageNode
                is_archived=False,  # Not available in LineageNode
                created_at=d.created_at.isoformat() if d.created_at else "",
                updated_at=d.created_at.isoformat()
                if d.created_at
                else "",  # Use created_at as fallback
            )
        )

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

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link capsule",
        )

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


@router.post(
    "/{capsule_id}/fork", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED
)
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

    # Archive the capsule using the dedicated archive method
    archived = await capsule_repo.archive(capsule_id)

    if archived is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive capsule",
        )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="archive",
        details={"archived": True},
        correlation_id=correlation_id,
    )

    return CapsuleResponse.from_capsule(archived)


# =============================================================================
# Integrity Verification Endpoints
# =============================================================================


@router.get("/{capsule_id}/integrity", response_model=IntegrityReport)
async def verify_capsule_integrity(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    update_status: bool = Query(
        default=True,
        description="Whether to update integrity_status in database",
    ),
) -> IntegrityReport:
    """
    Verify the integrity of a capsule's content.

    Performs:
    - Content hash verification (SHA-256)
    - Signature verification (if signed)
    - Merkle root verification (if has lineage)

    Returns comprehensive integrity report.
    """
    result = await capsule_repo.verify_integrity(
        capsule_id=capsule_id,
        update_status=update_status,
    )

    if not result.get("found", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Determine overall status
    if result.get("valid", False):
        overall_status = IntegrityStatus.VALID
    else:
        overall_status = IntegrityStatus.CORRUPTED

    return IntegrityReport(
        capsule_id=capsule_id,
        content_hash_valid=result.get("valid", False),
        content_hash_expected=result.get("content_hash_expected"),
        content_hash_computed=result.get("content_hash_computed"),
        signature_valid=None,  # Phase 2
        merkle_chain_valid=None,  # Checked in lineage endpoint
        overall_status=overall_status,
        checked_at=datetime.fromisoformat(result.get("verified_at", datetime.now(UTC).isoformat())),
        details={
            "has_signature": result.get("has_signature", False),
            "has_merkle_root": result.get("has_merkle_root", False),
            "errors": result.get("errors", []),
            "status_updated": result.get("status_updated", False),
        },
    )


@router.get("/{capsule_id}/lineage/integrity", response_model=LineageIntegrityReport)
async def verify_lineage_integrity(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
) -> LineageIntegrityReport:
    """
    Verify the integrity of the entire lineage chain for a capsule.

    Traces from root ancestor to the specified capsule and verifies:
    - Content hash of each capsule in chain
    - Merkle root chain integrity (each child correctly chains to parent)

    Returns detailed report showing which capsules passed/failed.
    """
    result = await capsule_repo.verify_lineage_integrity(capsule_id=capsule_id)

    if not result.get("found", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    return LineageIntegrityReport(
        capsule_id=capsule_id,
        chain_length=result.get("chain_length", 0),
        all_hashes_valid=result.get("all_hashes_valid", False),
        merkle_chain_valid=result.get("merkle_chain_valid", False),
        broken_at=result.get("broken_at"),
        verified_capsules=result.get("verified_capsules", []),
        failed_capsules=result.get("failed_capsules", []),
        checked_at=datetime.fromisoformat(result.get("verified_at", datetime.now(UTC).isoformat())),
    )


# =============================================================================
# Capsule Signing Endpoints
# =============================================================================


class SignCapsuleRequest(BaseModel):
    """Request to sign a capsule with user's private key."""

    password: str | None = Field(
        default=None,
        description="Password for SERVER_CUSTODY or PASSWORD_DERIVED strategies",
    )
    private_key_b64: str | None = Field(
        default=None,
        description="Base64 private key for CLIENT_ONLY strategy",
    )


class SignatureResponse(BaseModel):
    """Response after signing a capsule."""

    capsule_id: str
    signature: str
    content_hash: str
    signed_at: str
    signed_by: str
    algorithm: str = "Ed25519"


class SignatureVerifyResponse(BaseModel):
    """Response from signature verification."""

    capsule_id: str
    signature_valid: bool
    content_hash_valid: bool
    signer_id: str | None
    signer_public_key: str | None
    verified_at: str
    details: dict[str, Any]


@router.post("/{capsule_id}/sign", response_model=SignatureResponse)
async def sign_capsule(
    capsule_id: str,
    request: SignCapsuleRequest,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> SignatureResponse:
    """
    Sign a capsule with the current user's Ed25519 private key.

    The signature proves the user vouches for this capsule's content.
    Only the capsule owner can sign their capsules.

    Key retrieval depends on user's key_storage_strategy:
    - SERVER_CUSTODY: Provide password to decrypt stored key
    - CLIENT_ONLY: Provide private_key_b64 directly
    - PASSWORD_DERIVED: Provide password to derive key
    """
    # Get capsule
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Only owner can sign
    if capsule.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the capsule owner can sign it",
        )

    # Get user's signing key configuration
    # Note: In production, this would come from user_repo.get_by_id(user.id)
    # For now, we check the user object's attributes
    key_strategy = getattr(user, "key_storage_strategy", KeyStorageStrategy.NONE)

    if key_strategy == KeyStorageStrategy.NONE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no signing keys configured. Set up keys first.",
        )

    # Get private key based on strategy
    try:
        if key_strategy == KeyStorageStrategy.SERVER_CUSTODY:
            if not request.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password required for SERVER_CUSTODY key strategy",
                )
            encrypted_key = getattr(user, "encrypted_private_key", None)
            if not encrypted_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No encrypted key found for user",
                )
            private_key = KeyManagementService.decrypt_private_key(encrypted_key, request.password)

        elif key_strategy == KeyStorageStrategy.CLIENT_ONLY:
            if not request.private_key_b64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Private key required for CLIENT_ONLY strategy",
                )
            import base64

            private_key = base64.b64decode(request.private_key_b64)

        elif key_strategy == KeyStorageStrategy.PASSWORD_DERIVED:
            if not request.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password required for PASSWORD_DERIVED strategy",
                )
            salt_b64 = getattr(user, "signing_key_salt", None)
            if not salt_b64:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No key salt found for user",
                )
            private_key = KeyManagementService.get_private_key_password_derived(
                request.password, salt_b64
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown key storage strategy: {key_strategy}",
            )

    except KeyNotFoundError as e:
        logger.warning(f"Key not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Required key not found",
        ) from e
    except (ValueError, TypeError, OSError, RuntimeError) as e:
        logger.warning("capsule_sign_failed", error=str(e), capsule_id=capsule_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve private key. Check password or key configuration.",
        ) from e

    # Compute content hash and sign
    content_hash = CapsuleIntegrityService.compute_content_hash(capsule.content)
    signature = CapsuleIntegrityService.sign_capsule(content_hash, private_key)
    signed_at = datetime.now(UTC)

    # Update capsule with signature
    update_query = """
    MATCH (c:Capsule {id: $id})
    SET c.signature = $signature,
        c.signed_at = $signed_at,
        c.signed_by = $signed_by,
        c.signature_algorithm = 'Ed25519'
    RETURN c {.*} AS capsule
    """
    await capsule_repo.client.execute_single(
        update_query,
        {
            "id": capsule_id,
            "signature": signature,
            "signed_at": signed_at.isoformat(),
            "signed_by": user.id,
        },
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=capsule_id,
        action="sign",
        details={"algorithm": "Ed25519"},
        correlation_id=correlation_id,
    )

    logger.info(
        "capsule_signed",
        capsule_id=capsule_id,
        user_id=user.id,
        content_hash=content_hash[:16] + "...",
    )

    return SignatureResponse(
        capsule_id=capsule_id,
        signature=signature,
        content_hash=content_hash,
        signed_at=signed_at.isoformat(),
        signed_by=user.id,
        algorithm="Ed25519",
    )


@router.get("/{capsule_id}/signature/verify", response_model=SignatureVerifyResponse)
async def verify_capsule_signature(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
) -> SignatureVerifyResponse:
    """
    Verify a capsule's Ed25519 signature.

    Checks that:
    1. The signature is valid for the content hash
    2. The content hash matches the current content
    3. The signer's public key is retrieved from their user record

    Returns detailed verification results.
    """
    # Get capsule with signature info
    query = """
    MATCH (c:Capsule {id: $id})
    RETURN c.content AS content,
           c.content_hash AS content_hash,
           c.signature AS signature,
           c.signed_by AS signed_by,
           c.signed_at AS signed_at
    """
    result = await capsule_repo.client.execute_single(query, {"id": capsule_id})

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    signature = result.get("signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Capsule is not signed",
        )

    content = result["content"]
    stored_hash = result.get("content_hash")
    signed_by = result.get("signed_by")

    # Compute and verify content hash
    computed_hash = CapsuleIntegrityService.compute_content_hash(content)
    content_hash_valid = stored_hash and CapsuleIntegrityService.verify_content_hash(
        content, stored_hash
    )

    # Get signer's public key
    signer_public_key = None
    signature_valid = False

    if signed_by:
        signer_query = """
        MATCH (u:User {id: $id})
        RETURN u.signing_public_key AS public_key
        """
        signer_result = await capsule_repo.client.execute_single(signer_query, {"id": signed_by})
        if signer_result:
            signer_public_key = signer_result.get("public_key")

            if signer_public_key:
                # Verify signature
                hash_to_verify = stored_hash or computed_hash
                signature_valid = CapsuleIntegrityService.verify_signature(
                    hash_to_verify, signature, signer_public_key
                )

    verified_at = datetime.now(UTC)

    return SignatureVerifyResponse(
        capsule_id=capsule_id,
        signature_valid=signature_valid,
        content_hash_valid=content_hash_valid or False,
        signer_id=signed_by,
        signer_public_key=signer_public_key,
        verified_at=verified_at.isoformat(),
        details={
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
            "has_signer_key": signer_public_key is not None,
            "signed_at": result.get("signed_at"),
        },
    )
