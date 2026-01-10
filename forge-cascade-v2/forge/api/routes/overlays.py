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

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from forge.api.dependencies import (
    ActiveUserDep,
    AdminUserDep,
    AuditRepoDep,
    CanaryManagerDep,
    CoreUserDep,
    CorrelationIdDep,
    OverlayManagerDep,
    TrustedUserDep,
)
from forge.models.overlay import OverlayPhase, OverlayState

# Resilience integration - metrics and caching
from forge.resilience.integration import (
    invalidate_overlay_cache,
    record_canary_advanced,
    record_canary_rolled_back,
    record_canary_started,
    record_overlay_activated,
    record_overlay_config_updated,
    record_overlay_deactivated,
    record_overlays_reloaded,
)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class OverlayResponse(BaseModel):
    """Overlay information response - matches frontend Overlay type."""
    id: str
    name: str
    version: str
    description: str
    phase: int  # Frontend expects number, not string
    priority: int
    enabled: bool  # Frontend expects enabled, maps from state == ACTIVE
    critical: bool  # Frontend expects critical, not is_critical
    config: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_overlay(cls, overlay: Any) -> OverlayResponse:
        """Create response from BaseOverlay instance."""
        # Map phase enum to integer (1-7 for pipeline phases)
        phase_map = {
            "intake": 1, "validation": 2, "analysis": 3, "governance": 4,
            "integration": 5, "distribution": 6, "feedback": 7
        }
        # Safely get phase - some overlays may not have this attribute
        phase_int = 1  # Default to intake phase
        if hasattr(overlay, 'phase') and overlay.phase is not None:
            phase_value = overlay.phase.value if hasattr(overlay.phase, 'value') else str(overlay.phase)
            phase_int = phase_map.get(phase_value.lower(), 1)

        # Get last execution time (BaseOverlay uses last_execution, not last_active)
        last_exec = getattr(overlay, 'last_execution', None) or getattr(overlay, 'last_active', None)
        last_time = last_exec.isoformat() if last_exec else ""

        return cls(
            id=overlay.id,  # BaseOverlay uses .id
            name=getattr(overlay, 'NAME', getattr(overlay, 'name', 'unknown')),  # Class constant NAME
            version=getattr(overlay, 'VERSION', getattr(overlay, 'version', '1.0.0')),  # Class constant VERSION
            description=getattr(overlay, 'DESCRIPTION', getattr(overlay, 'description', '')),  # Class constant
            phase=phase_int,
            priority=getattr(overlay, 'priority', 100),  # Default priority
            enabled=overlay.state == OverlayState.ACTIVE,
            critical=getattr(overlay, 'is_critical', False),  # Default to non-critical
            config=getattr(overlay, 'config', {}),  # Default empty config
            created_at=last_time,
            updated_at=last_time,
        )


class UpdateOverlayConfigRequest(BaseModel):
    """Request to update overlay configuration."""
    config: dict[str, Any]


class OverlayMetricsResponse(BaseModel):
    """Overlay metrics response - matches frontend OverlayMetrics type."""
    overlay_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_ms: float  # Frontend expects average_duration_ms
    error_rate: float
    last_executed: str | None  # Frontend expects last_executed


class CanaryStatusResponse(BaseModel):
    """Canary deployment status response - matches frontend CanaryDeployment type."""
    overlay_id: str
    current_stage: int
    total_stages: int
    traffic_percentage: float
    started_at: str
    current_stage_started_at: str
    last_advanced_at: str | None
    success_count: int
    failure_count: int
    rollback_on_failure: bool
    is_complete: bool
    can_advance: bool


# =============================================================================
# Overlay Management Endpoints
# =============================================================================

@router.get("/")
async def list_overlays(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> dict:
    """
    List all registered overlays.
    """
    overlays = overlay_manager.list_all()
    return {"overlays": [OverlayResponse.from_overlay(o) for o in overlays]}


@router.get("/active")
async def list_active_overlays(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> dict:
    """
    List only active overlays.
    """
    overlays = overlay_manager.list_active()
    return {"overlays": [OverlayResponse.from_overlay(o) for o in overlays]}


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
    overlay = overlay_manager.get_by_id(overlay_id)

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
    overlay = overlay_manager.get_by_id(overlay_id)

    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    if overlay.state == OverlayState.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overlay already active",
        )

    await overlay_manager.activate(overlay_id)

    # Resilience: Record activation metric and invalidate cache
    record_overlay_activated(overlay_id)
    await invalidate_overlay_cache()

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
    overlay = overlay_manager.get_by_id(overlay_id)

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

    # Resilience: Record deactivation metric and invalidate cache
    record_overlay_deactivated(overlay_id)
    await invalidate_overlay_cache()

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
    overlay = overlay_manager.get_by_id(overlay_id)

    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    # Merge config
    new_config = {**overlay.config, **request.config}
    overlay.config = new_config

    # Resilience: Record config update metric and invalidate cache
    record_overlay_config_updated(overlay_id)
    await invalidate_overlay_cache()

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
    overlay = overlay_manager.get_by_id(overlay_id)

    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    stats = overlay.get_stats() if hasattr(overlay, 'get_stats') else {}

    total = stats.get('total_executions', 0)
    successful = stats.get('successful_executions', 0)
    failed = total - successful

    # Get last execution time (BaseOverlay uses last_execution, not last_active)
    last_exec = getattr(overlay, 'last_execution', None) or getattr(overlay, 'last_active', None)

    return OverlayMetricsResponse(
        overlay_id=overlay_id,
        total_executions=total,
        successful_executions=successful,
        failed_executions=failed,
        average_duration_ms=stats.get('avg_execution_time_ms', 0),  # Map to frontend field name
        error_rate=failed / total if total > 0 else 0,
        last_executed=last_exec.isoformat() if last_exec else None,  # Map to frontend field name
    )


@router.get("/metrics/summary")
async def get_all_overlay_metrics(
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> dict:
    """
    Get summary metrics for all overlays.
    """
    overlays = overlay_manager.list_all()

    summary = {
        "total_overlays": len(overlays),
        "active_overlays": sum(1 for o in overlays if o.state == OverlayState.ACTIVE),
        "by_phase": {},
        "by_state": {},
    }

    for overlay in overlays:
        # Safely get phase - some overlays may not have this attribute
        if hasattr(overlay, 'phase') and overlay.phase is not None:
            phase = overlay.phase.value if hasattr(overlay.phase, 'value') else str(overlay.phase)
        else:
            phase = "unknown"
        state = overlay.state.value if hasattr(overlay.state, 'value') else str(overlay.state)

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

def _canary_to_response(overlay_id: str, deployment: Any) -> CanaryStatusResponse:
    """Convert canary deployment to response format matching frontend."""

    now_iso = datetime.now(UTC).isoformat()

    return CanaryStatusResponse(
        overlay_id=overlay_id,
        current_stage=getattr(deployment, 'current_stage', 0),
        total_stages=len(getattr(deployment, 'stages', [5, 10, 25, 50, 100])),
        traffic_percentage=getattr(deployment, 'current_percentage', 0),
        started_at=deployment.started_at.isoformat() if hasattr(deployment, 'started_at') and deployment.started_at else now_iso,
        current_stage_started_at=deployment.current_stage_started_at.isoformat() if hasattr(deployment, 'current_stage_started_at') and deployment.current_stage_started_at else now_iso,
        last_advanced_at=deployment.last_advanced_at.isoformat() if hasattr(deployment, 'last_advanced_at') and deployment.last_advanced_at else None,
        success_count=getattr(deployment.metrics, 'success_count', 0) if hasattr(deployment, 'metrics') else 0,
        failure_count=getattr(deployment.metrics, 'failure_count', 0) if hasattr(deployment, 'metrics') else 0,
        rollback_on_failure=getattr(deployment, 'rollback_on_failure', True),
        is_complete=deployment.is_complete() if hasattr(deployment, 'is_complete') else False,
        can_advance=deployment.can_advance() if hasattr(deployment, 'can_advance') else False,
    )


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

    overlay = overlay_manager.get_by_id(overlay_id)

    if not overlay:
        raise HTTPException(status_code=404, detail="Overlay not found")

    # Check if there's an active canary
    deployment = canary_manager.get_deployment(overlay_id)

    if not deployment:
        # Return empty canary status when no deployment exists
        now_iso = datetime.now(UTC).isoformat()
        return CanaryStatusResponse(
            overlay_id=overlay_id,
            current_stage=0,
            total_stages=5,
            traffic_percentage=0,
            started_at=now_iso,
            current_stage_started_at=now_iso,
            last_advanced_at=None,
            success_count=0,
            failure_count=0,
            rollback_on_failure=True,
            is_complete=False,
            can_advance=False,
        )

    return _canary_to_response(overlay_id, deployment)


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
    overlay = overlay_manager.get_by_id(overlay_id)

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

    # Resilience: Record canary start metric
    record_canary_started(overlay_id)

    await audit_repo.log_action(
        action="canary_started",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        correlation_id=correlation_id,
    )

    return _canary_to_response(overlay_id, deployment)


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

    # Re-fetch deployment after advancing
    deployment = canary_manager.get_deployment(overlay_id)

    # Resilience: Record canary advance metric
    record_canary_advanced(overlay_id, getattr(deployment, 'current_stage', 0))

    await audit_repo.log_action(
        action="canary_advanced",
        entity_type="overlay",
        entity_id=overlay_id,
        user_id=user.id,
        details={"new_percentage": getattr(deployment, 'current_percentage', 0)},
        correlation_id=correlation_id,
    )

    return _canary_to_response(overlay_id, deployment)


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

    # Resilience: Record canary rollback metric
    record_canary_rolled_back(overlay_id)

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

    overlay_count = len(overlay_manager.list_all())

    # Resilience: Record reload metric and invalidate cache
    record_overlays_reloaded(overlay_count)
    await invalidate_overlay_cache()

    await audit_repo.log_action(
        action="overlays_reloaded",
        entity_type="system",
        entity_id="overlay_manager",
        user_id=user.id,
        correlation_id=correlation_id,
    )

    return {
        "status": "reloaded",
        "overlay_count": overlay_count,
    }
