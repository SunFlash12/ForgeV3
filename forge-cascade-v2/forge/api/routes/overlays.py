"""
Forge Cascade V2 - Overlay Routes
Endpoints for overlay management and monitoring.

Provides:
- Overlay listing and status
- Overlay activation/deactivation
- Overlay configuration
- Overlay metrics
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    OverlayRepoDep,
    OverlayManagerDep,
    CanaryManagerDep,
    AuditRepoDep,
    ActiveUserDep,
    TrustedUserDep,
    CoreUserDep,
    AdminUserDep,
    CorrelationIdDep,
)
from forge.models.overlay import OverlayState, OverlayPhase


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class OverlayResponse(BaseModel):
    """Overlay information response."""
    id: str
    name: str
    version: str
    description: str | None
    state: str
    phase: str
    priority: int
    is_critical: bool
    config: dict[str, Any]
    stats: dict[str, Any]
    last_active: str | None
    
    @classmethod
    def from_overlay(cls, overlay: Any) -> "OverlayResponse":
        """Create response from overlay instance."""
        return cls(
            id=overlay.overlay_id,
            name=overlay.name,
            version=overlay.version,
            description=getattr(overlay, 'description', None),
            state=overlay.state.value,
            phase=overlay.phase.value,
            priority=overlay.priority,
            is_critical=overlay.is_critical,
            config=overlay.config,
            stats=overlay.get_stats() if hasattr(overlay, 'get_stats') else {},
            last_active=overlay.last_active.isoformat() if overlay.last_active else None,
        )


class UpdateOverlayConfigRequest(BaseModel):
    """Request to update overlay configuration."""
    config: dict[str, Any]


class OverlayMetricsResponse(BaseModel):
    """Overlay metrics response."""
    overlay_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    avg_execution_time_ms: float
    error_rate: float
    last_execution: str | None


class CanaryStatusResponse(BaseModel):
    """Canary deployment status response."""
    overlay_id: str
    is_canary: bool
    percentage: float
    samples: int
    error_rate: float
    state: str | None


# =============================================================================
# Overlay Management Endpoints
# =============================================================================

@router.get("/", response_model=list[OverlayResponse])
async def list_overlays(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> list[OverlayResponse]:
    """
    List all registered overlays.
    """
    overlays = overlay_manager.get_all_overlays()
    return [OverlayResponse.from_overlay(o) for o in overlays]


@router.get("/active", response_model=list[OverlayResponse])
async def list_active_overlays(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> list[OverlayResponse]:
    """
    List only active overlays.
    """
    overlays = overlay_manager.get_active_overlays()
    return [OverlayResponse.from_overlay(o) for o in overlays]


@router.get("/by-phase/{phase}", response_model=list[OverlayResponse])
async def list_overlays_by_phase(
    phase: OverlayPhase,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> list[OverlayResponse]:
    """
    List overlays by their pipeline phase.
    """
    overlays = overlay_manager.get_overlays_for_phase(phase)
    return [OverlayResponse.from_overlay(o) for o in overlays]


@router.get("/{overlay_id}", response_model=OverlayResponse)
async def get_overlay(
    overlay_id: str,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> OverlayResponse:
    """
    Get a specific overlay's information.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Overlay not found",
        )
    
    return OverlayResponse.from_overlay(overlay)


@router.post("/{overlay_id}/activate", response_model=OverlayResponse)
async def activate_overlay(
    overlay_id: str,
    user: TrustedUserDep,  # TRUSTED to activate
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> OverlayResponse:
    """
    Activate an overlay.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    if overlay.state == OverlayState.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overlay already active",
        )
    
    await overlay_manager.activate(overlay_id)
    
    await audit_repo.log_action(
        action="overlay_activated",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return OverlayResponse.from_overlay(overlay)


@router.post("/{overlay_id}/deactivate", response_model=OverlayResponse)
async def deactivate_overlay(
    overlay_id: str,
    user: TrustedUserDep,
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> OverlayResponse:
    """
    Deactivate an overlay.
    
    Critical overlays cannot be deactivated.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    if overlay.is_critical:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate critical overlay",
        )
    
    if overlay.state != OverlayState.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overlay not active",
        )
    
    await overlay_manager.deactivate(overlay_id)
    
    await audit_repo.log_action(
        action="overlay_deactivated",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return OverlayResponse.from_overlay(overlay)


@router.patch("/{overlay_id}/config", response_model=OverlayResponse)
async def update_overlay_config(
    overlay_id: str,
    request: UpdateOverlayConfigRequest,
    user: CoreUserDep,  # CORE to change config
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> OverlayResponse:
    """
    Update overlay configuration.
    
    Changes take effect immediately.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    # Merge config
    new_config = {**overlay.config, **request.config}
    overlay.config = new_config
    
    await audit_repo.log_action(
        action="overlay_config_updated",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        details={"config_keys": list(request.config.keys())},
        correlation_id=correlation_id,
    )
    
    return OverlayResponse.from_overlay(overlay)


# =============================================================================
# Overlay Metrics Endpoints
# =============================================================================

@router.get("/{overlay_id}/metrics", response_model=OverlayMetricsResponse)
async def get_overlay_metrics(
    overlay_id: str,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> OverlayMetricsResponse:
    """
    Get overlay execution metrics.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    stats = overlay.get_stats() if hasattr(overlay, 'get_stats') else {}
    
    total = stats.get('total_executions', 0)
    successful = stats.get('successful_executions', 0)
    failed = total - successful
    
    return OverlayMetricsResponse(
        overlay_id=overlay_id,
        total_executions=total,
        successful_executions=successful,
        failed_executions=failed,
        avg_execution_time_ms=stats.get('avg_execution_time_ms', 0),
        error_rate=failed / total if total > 0 else 0,
        last_execution=overlay.last_active.isoformat() if overlay.last_active else None,
    )


@router.get("/metrics/summary")
async def get_all_overlay_metrics(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> dict:
    """
    Get summary metrics for all overlays.
    """
    overlays = overlay_manager.get_all_overlays()
    
    summary = {
        "total_overlays": len(overlays),
        "active_overlays": sum(1 for o in overlays if o.state == OverlayState.ACTIVE),
        "by_phase": {},
        "by_state": {},
    }
    
    for overlay in overlays:
        phase = overlay.phase.value
        state = overlay.state.value
        
        if phase not in summary["by_phase"]:
            summary["by_phase"][phase] = 0
        summary["by_phase"][phase] += 1
        
        if state not in summary["by_state"]:
            summary["by_state"][state] = 0
        summary["by_state"][state] += 1
    
    return summary


# =============================================================================
# Canary Deployment Endpoints
# =============================================================================

@router.get("/{overlay_id}/canary", response_model=CanaryStatusResponse)
async def get_canary_status(
    overlay_id: str,
    user: ActiveUserDep,
    canary_manager: CanaryManagerDep,
    overlay_manager: OverlayManagerDep,
) -> CanaryStatusResponse:
    """
    Get canary deployment status for an overlay.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    # Check if there's an active canary
    deployment = canary_manager.get_deployment(overlay_id)
    
    if not deployment:
        return CanaryStatusResponse(
            overlay_id=overlay_id,
            is_canary=False,
            percentage=0,
            samples=0,
            error_rate=0,
            state=None,
        )
    
    metrics = deployment.metrics
    
    return CanaryStatusResponse(
        overlay_id=overlay_id,
        is_canary=True,
        percentage=deployment.current_percentage,
        samples=metrics.total_samples,
        error_rate=metrics.error_rate,
        state=deployment.state.value,
    )


@router.post("/{overlay_id}/canary/start")
async def start_canary_deployment(
    overlay_id: str,
    user: CoreUserDep,
    canary_manager: CanaryManagerDep,
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CanaryStatusResponse:
    """
    Start a canary deployment for an overlay update.
    """
    overlay = overlay_manager.get_overlay(overlay_id)
    
    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")
    
    # Check if already in canary
    existing = canary_manager.get_deployment(overlay_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Canary deployment already in progress",
        )
    
    # Start canary
    deployment = await canary_manager.start(
        deployment_id=overlay_id,
        target=overlay.config,
    )
    
    await audit_repo.log_action(
        action="canary_started",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return CanaryStatusResponse(
        overlay_id=overlay_id,
        is_canary=True,
        percentage=deployment.current_percentage,
        samples=0,
        error_rate=0,
        state=deployment.state.value,
    )


@router.post("/{overlay_id}/canary/advance")
async def advance_canary_deployment(
    overlay_id: str,
    user: CoreUserDep,
    canary_manager: CanaryManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> CanaryStatusResponse:
    """
    Manually advance a canary deployment to the next stage.
    """
    deployment = canary_manager.get_deployment(overlay_id)
    
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active canary deployment",
        )
    
    await canary_manager.advance(overlay_id)
    
    await audit_repo.log_action(
        action="canary_advanced",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        details={"new_percentage": deployment.current_percentage},
        correlation_id=correlation_id,
    )
    
    return CanaryStatusResponse(
        overlay_id=overlay_id,
        is_canary=True,
        percentage=deployment.current_percentage,
        samples=deployment.metrics.total_samples,
        error_rate=deployment.metrics.error_rate,
        state=deployment.state.value,
    )


@router.post("/{overlay_id}/canary/rollback")
async def rollback_canary_deployment(
    overlay_id: str,
    user: CoreUserDep,
    canary_manager: CanaryManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict:
    """
    Rollback a canary deployment.
    """
    deployment = canary_manager.get_deployment(overlay_id)
    
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active canary deployment",
        )
    
    await canary_manager.rollback(overlay_id)
    
    await audit_repo.log_action(
        action="canary_rolled_back",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return {"status": "rolled_back", "overlay_id": overlay_id}


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.post("/reload-all")
async def reload_all_overlays(
    user: AdminUserDep,
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict:
    """
    Reload all overlays (admin action).
    
    This restarts all overlays, useful after configuration changes.
    """
    await overlay_manager.stop()
    await overlay_manager.start()
    
    await audit_repo.log_action(
        action="overlays_reloaded",
        entity_type="system",
        entity_id="overlay_manager",
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return {
        "status": "reloaded",
        "overlay_count": len(overlay_manager.get_all_overlays()),
    }
