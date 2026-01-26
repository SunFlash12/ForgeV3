"""
Forge Cascade V2 - Cascade Effect Routes
Endpoints for triggering and monitoring cascade propagation.

The Cascade Effect is the core innovation where:
1. An overlay detects an insight
2. Publishes event via EventSystem
3. OverlayManager routes to relevant overlays
4. Each overlay integrates the insight
5. System-wide intelligence increases

Provides:
- Cascade triggering
- Cascade chain monitoring
- Cascade metrics

NOTE: Cascade chains are now persisted to Neo4j via CascadeRepository.
The EventSystem integrates with CascadeRepository to:
1. Create chains in Neo4j when cascades start
2. Add events to chains as cascades propagate
3. Complete chains in Neo4j when cascades finish
4. Load active chains from Neo4j on startup
See: forge/repositories/cascade_repository.py
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    CorrelationIdDep,
    EventSystemDep,
    PipelineDep,
    TrustedUserDep,
)
from forge.models.events import CascadeChain, CascadeEvent

# Resilience integration - metrics and caching
from forge.resilience.integration import (
    invalidate_cascade_cache,
    record_cascade_completed,
    record_cascade_propagated,
    record_cascade_triggered,
    record_pipeline_executed,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class TriggerCascadeRequest(BaseModel):
    """Request to trigger a cascade."""
    source_overlay: str = Field(description="The overlay initiating the cascade")
    insight_type: str = Field(description="Type of insight being cascaded")
    insight_data: dict[str, Any] = Field(description="The insight payload")
    max_hops: int = Field(default=5, ge=1, le=10, description="Maximum cascade depth")


class CascadeEventResponse(BaseModel):
    """Response for a cascade event."""
    id: str
    source_overlay: str
    insight_type: str
    insight_data: dict[str, Any]
    hop_count: int
    max_hops: int
    visited_overlays: list[str]
    impact_score: float
    timestamp: str
    correlation_id: str | None


class CascadeChainResponse(BaseModel):
    """Response for a cascade chain."""
    cascade_id: str
    initiated_by: str
    initiated_at: str
    events: list[CascadeEventResponse]
    completed_at: str | None
    total_hops: int
    overlays_affected: list[str]
    insights_generated: int
    actions_triggered: int
    errors_encountered: int
    status: str  # "active" or "completed"


class CascadeMetricsResponse(BaseModel):
    """Response for cascade system metrics."""
    total_cascades: int
    active_cascades: int
    completed_cascades: int
    total_events: int
    avg_hops_per_cascade: float
    avg_overlays_affected: float


class PropagateRequest(BaseModel):
    """Request to propagate an existing cascade."""
    cascade_id: str = Field(description="ID of the cascade to propagate")
    target_overlay: str = Field(description="The overlay receiving the propagation")
    insight_type: str = Field(description="Type of insight being propagated")
    insight_data: dict[str, Any] = Field(description="The insight payload")
    impact_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Calculated impact")


# =============================================================================
# Helper Functions
# =============================================================================

def _event_to_response(event: CascadeEvent) -> CascadeEventResponse:
    """Convert CascadeEvent model to response."""
    return CascadeEventResponse(
        id=event.id,
        source_overlay=event.source_overlay,
        insight_type=event.insight_type,
        insight_data=event.insight_data,
        hop_count=event.hop_count,
        max_hops=event.max_hops,
        visited_overlays=event.visited_overlays,
        impact_score=event.impact_score,
        timestamp=event.timestamp.isoformat() if event.timestamp else "",
        correlation_id=event.correlation_id,
    )


def _chain_to_response(chain: CascadeChain, is_active: bool = True) -> CascadeChainResponse:
    """Convert CascadeChain model to response."""
    return CascadeChainResponse(
        cascade_id=chain.cascade_id,
        initiated_by=chain.initiated_by,
        initiated_at=chain.initiated_at.isoformat() if chain.initiated_at else "",
        events=[_event_to_response(e) for e in chain.events],
        completed_at=chain.completed_at.isoformat() if chain.completed_at else None,
        total_hops=chain.total_hops,
        overlays_affected=chain.overlays_affected,
        insights_generated=chain.insights_generated,
        actions_triggered=chain.actions_triggered,
        errors_encountered=chain.errors_encountered,
        status="active" if is_active else "completed",
    )


# =============================================================================
# Cascade Management Endpoints
# =============================================================================

@router.post("/trigger", response_model=CascadeChainResponse)
async def trigger_cascade(
    request: TriggerCascadeRequest,
    user: TrustedUserDep,  # TRUSTED to trigger cascades
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CascadeChainResponse:
    """
    Trigger a new cascade chain.

    This initiates the Cascade Effect where an insight propagates
    across the overlay ecosystem. The insight will be routed to
    all overlays that subscribe to CASCADE_INITIATED events.
    """
    chain = await event_system.publish_cascade(
        source_overlay=request.source_overlay,
        insight_type=request.insight_type,
        insight_data=request.insight_data,
        max_hops=request.max_hops,
    )

    # Resilience: Record cascade trigger metric and invalidate cache
    record_cascade_triggered(request.source_overlay, request.insight_type)
    await invalidate_cascade_cache()

    await audit_repo.log_action(
        action="cascade_triggered",
        entity_type="cascade",
        entity_id=chain.cascade_id,
        user_id=user.id,
        details={
            "source_overlay": request.source_overlay,
            "insight_type": request.insight_type,
            "max_hops": request.max_hops,
        },
        correlation_id=correlation_id,
    )

    return _chain_to_response(chain)


@router.post("/propagate", response_model=CascadeEventResponse)
async def propagate_cascade(
    request: PropagateRequest,
    user: TrustedUserDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CascadeEventResponse:
    """
    Propagate an existing cascade to a new overlay.

    This continues the cascade chain by routing the insight to
    a new target overlay. The system prevents cycles and enforces
    the maximum hop limit.
    """
    event = await event_system.propagate_cascade(
        cascade_id=request.cascade_id,
        target_overlay=request.target_overlay,
        insight_type=request.insight_type,
        insight_data=request.insight_data,
        impact_score=request.impact_score,
    )

    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not propagate cascade - either max hops reached, cycle detected, or cascade not found",
        )

    # Resilience: Record cascade propagation metric and invalidate cache
    record_cascade_propagated(request.cascade_id, request.target_overlay, event.hop_count)
    await invalidate_cascade_cache()

    await audit_repo.log_action(
        action="cascade_propagated",
        entity_type="cascade",
        entity_id=request.cascade_id,
        user_id=user.id,
        details={
            "target_overlay": request.target_overlay,
            "insight_type": request.insight_type,
            "hop_count": event.hop_count,
        },
        correlation_id=correlation_id,
    )

    return _event_to_response(event)


@router.post("/{cascade_id}/complete", response_model=CascadeChainResponse)
async def complete_cascade(
    cascade_id: str,
    user: TrustedUserDep,
    event_system: EventSystemDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CascadeChainResponse:
    """
    Mark a cascade chain as complete.

    This finalizes the cascade and emits a CASCADE_COMPLETE event.
    """
    chain = await event_system.complete_cascade(cascade_id)

    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cascade chain not found",
        )

    # Resilience: Record cascade completion metric and invalidate cache
    record_cascade_completed(cascade_id, chain.total_hops, len(chain.overlays_affected))
    await invalidate_cascade_cache()

    await audit_repo.log_action(
        action="cascade_completed",
        entity_type="cascade",
        entity_id=cascade_id,
        user_id=user.id,
        details={
            "total_hops": chain.total_hops,
            "overlays_affected": len(chain.overlays_affected),
        },
        correlation_id=correlation_id,
    )

    return _chain_to_response(chain, is_active=False)


# =============================================================================
# Cascade Query Endpoints
# =============================================================================

@router.get("/", response_model=list[CascadeChainResponse])
async def list_active_cascades(
    user: ActiveUserDep,
    event_system: EventSystemDep,
) -> list[CascadeChainResponse]:
    """
    List all active (incomplete) cascade chains.
    """
    chains = event_system.get_active_cascades()
    return [_chain_to_response(c) for c in chains]


@router.get("/{cascade_id}", response_model=CascadeChainResponse)
async def get_cascade(
    cascade_id: str,
    user: ActiveUserDep,
    event_system: EventSystemDep,
) -> CascadeChainResponse:
    """
    Get details of a specific cascade chain.
    """
    chain = event_system.get_cascade_chain(cascade_id)

    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cascade chain not found",
        )

    return _chain_to_response(chain)


@router.get("/metrics/summary", response_model=CascadeMetricsResponse)
async def get_cascade_metrics(
    user: ActiveUserDep,
    event_system: EventSystemDep,
) -> CascadeMetricsResponse:
    """
    Get summary metrics for the cascade system.
    """
    metrics = event_system.get_metrics()
    active_chains = event_system.get_active_cascades()

    # Calculate aggregated metrics
    total_hops = sum(c.total_hops for c in active_chains)
    total_affected = sum(len(c.overlays_affected) for c in active_chains)
    num_active = len(active_chains)

    return CascadeMetricsResponse(
        total_cascades=metrics.get("cascade_chains", 0),
        active_cascades=num_active,
        completed_cascades=metrics.get("cascade_chains", 0) - num_active,
        total_events=metrics.get("events_published", 0),
        avg_hops_per_cascade=total_hops / num_active if num_active > 0 else 0.0,
        avg_overlays_affected=total_affected / num_active if num_active > 0 else 0.0,
    )


# =============================================================================
# Pipeline Integration
# =============================================================================

@router.post("/execute-pipeline")
async def execute_cascade_pipeline(
    request: TriggerCascadeRequest,
    user: TrustedUserDep,
    pipeline: PipelineDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict[str, Any]:
    """
    Execute the full 7-phase pipeline with cascade propagation.

    This triggers the complete cascade pipeline including:
    1. INGESTION - Data validation
    2. ANALYSIS - ML processing
    3. VALIDATION - Security checks
    4. CONSENSUS - Governance approval
    5. EXECUTION - Core processing
    6. PROPAGATION - Cascade effect handling
    7. SETTLEMENT - Audit logging
    """
    result = await pipeline.execute(
        input_data={
            "insight_type": request.insight_type,
            "insight_data": request.insight_data,
            "source_overlay": request.source_overlay,
        },
        triggered_by=f"user:{user.id}",
        user_id=user.id,
        trust_flame=user.trust_flame,
        metadata={
            "cascade_trigger": True,
            "max_hops": request.max_hops,
        }
    )

    # Resilience: Record pipeline execution metric
    record_pipeline_executed(result.pipeline_id, result.status.value, result.duration_ms)

    await audit_repo.log_action(
        action="cascade_pipeline_executed",
        entity_type="pipeline",
        entity_id=result.pipeline_id,
        user_id=user.id,
        details={
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "phases_completed": len(result.phases),
        },
        correlation_id=correlation_id,
    )

    return {
        "pipeline_id": result.pipeline_id,
        "status": result.status.value,
        "success": result.success,
        "duration_ms": result.duration_ms,
        "phases": {
            phase.value: {
                "status": r.status.value,
                "duration_ms": r.duration_ms,
                "overlays_executed": r.overlays_executed,
            }
            for phase, r in result.phases.items()
        },
        "errors": result.errors,
    }
