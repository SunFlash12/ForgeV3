"""
Forge System API Routes

Provides endpoints for:
- Health checks and readiness probes
- Immune system monitoring (circuit breakers, anomalies, canaries)
- System metrics and status
- Administrative operations
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    AdminUserDep,
    AnomalySystemDep,
    CanaryManagerDep,
    CircuitRegistryDep,
    CoreUserDep,
    CurrentUserDep,
    DbClientDep,
    EventSystemDep,
    HealthCheckerDep,
    OverlayManagerDep,
    PipelineDep,
    TrustedUserDep,
)
from forge.immune.anomaly import AnomalySeverity, AnomalyType
from forge.models.events import EventType

# Resilience integration - metrics and caching
from forge.resilience.integration import (
    record_anomaly_acknowledged,
    record_anomaly_resolved,
    record_cache_cleared,
    record_circuit_breaker_reset,
    record_health_check_access,
    record_maintenance_mode_changed,
)

router = APIRouter(tags=["system"])


# ============================================================================
# Global Maintenance Mode State
# ============================================================================

import threading

_maintenance_state = {
    "enabled": False,
    "enabled_at": None,
    "enabled_by": None,
    "message": "System is under maintenance. Please try again later.",
}
_maintenance_lock = threading.Lock()


def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled."""
    # SECURITY FIX (Audit 3): Acquire lock for consistent read
    with _maintenance_lock:
        return _maintenance_state["enabled"]


def get_maintenance_message() -> str:
    """Get the maintenance mode message."""
    # SECURITY FIX (Audit 3): Acquire lock for consistent read
    with _maintenance_lock:
        return _maintenance_state["message"]


def set_maintenance_mode(enabled: bool, user_id: str | None = None, message: str | None = None) -> None:
    """Set maintenance mode state."""
    with _maintenance_lock:
        _maintenance_state["enabled"] = enabled
        if enabled:
            _maintenance_state["enabled_at"] = datetime.now(UTC)
            _maintenance_state["enabled_by"] = user_id
            if message:
                _maintenance_state["message"] = message
        else:
            _maintenance_state["enabled_at"] = None
            _maintenance_state["enabled_by"] = None
            _maintenance_state["message"] = "System is under maintenance. Please try again later."


# ============================================================================
# Request/Response Models
# ============================================================================


class HealthStatus(BaseModel):
    """Overall health status response."""

    status: str = Field(description="Overall status: healthy, degraded, unhealthy")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    uptime_seconds: float = Field(description="Application uptime in seconds")
    version: str = Field(default="0.1.0")

    components: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual component health status"
    )
    checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Quick health check results"
    )


class CircuitBreakerStatus(BaseModel):
    """Status of a single circuit breaker."""

    name: str
    state: str = Field(description="CLOSED, OPEN, or HALF_OPEN")
    failure_count: int
    success_count: int
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    reset_timeout: float = Field(description="Seconds until OPEN → HALF_OPEN")
    failure_threshold: int
    success_threshold: int


class CircuitBreakerListResponse(BaseModel):
    """List of all circuit breakers."""

    circuit_breakers: list[CircuitBreakerStatus]
    total: int
    open_count: int
    half_open_count: int


class AnomalyResponse(BaseModel):
    """Single anomaly record."""

    id: str
    metric_name: str
    anomaly_type: str
    severity: str
    anomaly_score: float
    value: float
    expected_value: float | None = None
    detected_at: datetime
    acknowledged: bool
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved: bool
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AnomalyListResponse(BaseModel):
    """List of anomalies."""

    anomalies: list[AnomalyResponse]
    total: int
    unresolved_count: int


class AnomalyAcknowledgeRequest(BaseModel):
    """Request to acknowledge an anomaly."""

    notes: str | None = Field(default=None, max_length=500)


class RecordMetricRequest(BaseModel):
    """Request to record a metric value."""

    metric_name: str = Field(min_length=1, max_length=100)
    value: float
    context: dict[str, Any] = Field(default_factory=dict)


class SystemMetricsResponse(BaseModel):
    """Comprehensive system metrics."""

    timestamp: datetime

    # Kernel metrics
    events_emitted_total: int
    events_processed_total: int
    active_overlays: int
    pipeline_executions: int
    average_pipeline_duration_ms: float

    # Immune system metrics
    open_circuit_breakers: int
    active_anomalies: int
    canary_deployments: int

    # Database metrics
    db_connected: bool

    # Resource metrics (if available)
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None


class EventLogResponse(BaseModel):
    """Recent event log entry."""

    event_type: str
    timestamp: datetime
    data: dict[str, Any]
    correlation_id: str | None = None


class EventListResponse(BaseModel):
    """List of recent events."""

    events: list[EventLogResponse]
    total: int


class CanaryDeploymentResponse(BaseModel):
    """Canary deployment status."""

    overlay_id: str
    current_stage: int
    total_stages: int
    traffic_percentage: float
    started_at: datetime
    current_stage_started_at: datetime
    last_advanced_at: datetime | None = None
    success_count: int
    failure_count: int
    rollback_on_failure: bool
    is_complete: bool
    can_advance: bool


class CanaryListResponse(BaseModel):
    """List of active canary deployments."""

    deployments: list[CanaryDeploymentResponse]
    total: int


# ============================================================================
# Health Check Endpoints
# ============================================================================


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Comprehensive health check",
    description="Returns detailed health status of all system components"
)
async def get_health(
    db_client: DbClientDep,
    event_system: EventSystemDep,
    overlay_manager: OverlayManagerDep,
    circuit_registry: CircuitRegistryDep,
    health_checker: HealthCheckerDep,
    anomaly_system: AnomalySystemDep,
) -> HealthStatus:
    """Get comprehensive system health status."""

    # Resilience: Record health check access metric
    record_health_check_access()

    # Calculate uptime from event system start
    uptime = (
        datetime.now(UTC) - event_system._start_time
    ).total_seconds() if hasattr(event_system, "_start_time") else 0.0

    # Component status
    components = {}
    checks = {}

    # Database health
    try:
        db_healthy = await db_client.verify_connection()
        components["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "neo4j"
        }
        checks["database"] = db_healthy
    except Exception as e:
        # SECURITY FIX (Audit 3): Don't expose internal error details
        import structlog
        structlog.get_logger(__name__).error("database_health_check_failed", error=str(e))
        components["database"] = {"status": "unhealthy", "error": "Database connection failed"}
        checks["database"] = False

    # Event system health
    event_healthy = event_system._running if hasattr(event_system, "_running") else True
    components["event_system"] = {
        "status": "healthy" if event_healthy else "degraded",
        "queue_size": event_system._queue.qsize() if hasattr(event_system, "_queue") else 0
    }
    checks["event_system"] = event_healthy

    # Overlay manager health
    overlay_count = len(overlay_manager._overlays) if hasattr(overlay_manager, "_overlays") else 0
    active_count = len([o for o in overlay_manager._overlays.values() if o.enabled]) if hasattr(overlay_manager, "_overlays") else 0
    components["overlay_manager"] = {
        "status": "healthy",
        "total_overlays": overlay_count,
        "active_overlays": active_count
    }
    checks["overlay_manager"] = True

    # Circuit breakers health
    open_breakers = sum(
        1 for cb in circuit_registry._breakers.values()
        if cb.state.name == "OPEN"
    ) if hasattr(circuit_registry, "_breakers") else 0

    components["circuit_breakers"] = {
        "status": "degraded" if open_breakers > 0 else "healthy",
        "total": len(circuit_registry._breakers) if hasattr(circuit_registry, "_breakers") else 0,
        "open": open_breakers
    }
    checks["circuit_breakers"] = open_breakers == 0

    # Anomaly system health
    unresolved = len(anomaly_system.get_unresolved_anomalies())
    critical_anomalies = len([
        a for a in anomaly_system.get_unresolved_anomalies()
        if a.severity == AnomalySeverity.CRITICAL
    ])

    anomaly_status = "healthy"
    if critical_anomalies > 0:
        anomaly_status = "unhealthy"
    elif unresolved > 5:
        anomaly_status = "degraded"

    components["anomaly_detection"] = {
        "status": anomaly_status,
        "unresolved": unresolved,
        "critical": critical_anomalies
    }
    checks["anomaly_detection"] = critical_anomalies == 0

    # Determine overall status
    all_healthy = all(checks.values())
    any_unhealthy = any(
        c.get("status") == "unhealthy"
        for c in components.values()
    )

    if any_unhealthy:
        overall_status = "unhealthy"
    elif not all_healthy:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthStatus(
        status=overall_status,
        uptime_seconds=uptime,
        components=components,
        checks=checks
    )


@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes/container orchestration"
)
async def liveness_probe() -> dict[str, str]:
    """Simple liveness check - always returns OK if the process is running."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Readiness check verifying critical dependencies"
)
async def readiness_probe(
    db_client: DbClientDep,
) -> dict[str, Any]:
    """Readiness check - verifies critical dependencies are available."""

    ready = True
    details = {}

    # Check database
    try:
        db_ready = await db_client.verify_connection()
        details["database"] = "ready" if db_ready else "not_ready"
        if not db_ready:
            ready = False
    except Exception as e:
        # SECURITY FIX (Audit 3): Don't expose internal error details
        import structlog
        structlog.get_logger(__name__).error("readiness_check_failed", error=str(e))
        details["database"] = "error: connection failed"
        ready = False

    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "details": details}
        )

    return {"status": "ready", "details": details}


# ============================================================================
# Circuit Breaker Endpoints
# ============================================================================


@router.get(
    "/circuit-breakers",
    response_model=CircuitBreakerListResponse,
    summary="List all circuit breakers",
    description="Returns status of all registered circuit breakers"
)
async def list_circuit_breakers(
    _user: CurrentUserDep,
    circuit_registry: CircuitRegistryDep,
) -> CircuitBreakerListResponse:
    """List all circuit breakers and their current states."""

    breakers = []
    open_count = 0
    half_open_count = 0

    for name, cb in circuit_registry._breakers.items():
        state_name = cb.state.name
        if state_name == "OPEN":
            open_count += 1
        elif state_name == "HALF_OPEN":
            half_open_count += 1

        breakers.append(CircuitBreakerStatus(
            name=name,
            state=state_name,
            failure_count=cb._failure_count,
            success_count=cb._success_count,
            last_failure_time=cb._last_failure_time,
            last_success_time=cb._last_success_time,
            reset_timeout=cb._reset_timeout,
            failure_threshold=cb._failure_threshold,
            success_threshold=cb._success_threshold
        ))

    return CircuitBreakerListResponse(
        circuit_breakers=breakers,
        total=len(breakers),
        open_count=open_count,
        half_open_count=half_open_count
    )


@router.post(
    "/circuit-breakers/{name}/reset",
    summary="Reset a circuit breaker",
    description="Manually reset a circuit breaker to closed state"
)
async def reset_circuit_breaker(
    name: str,
    user: TrustedUserDep,
    circuit_registry: CircuitRegistryDep,
    event_system: EventSystemDep,
) -> dict[str, str]:
    """Manually reset a circuit breaker."""

    if name not in circuit_registry._breakers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found"
        )

    cb = circuit_registry._breakers[name]
    cb.reset()

    # Resilience: Record circuit breaker reset metric
    record_circuit_breaker_reset(name)

    # Emit event
    await event_system.emit(
        "CIRCUIT_BREAKER_RESET",
        {
            "circuit_name": name,
            "reset_by": str(user.id),
            "previous_state": cb.state.name
        }
    )

    return {"status": "reset", "circuit_breaker": name}


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================


@router.get(
    "/anomalies",
    response_model=AnomalyListResponse,
    summary="List anomalies",
    description="Returns detected anomalies with filtering options"
)
async def list_anomalies(
    _user: CurrentUserDep,
    anomaly_system: AnomalySystemDep,
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    anomaly_type: str | None = Query(default=None, description="Filter by type"),
    unresolved_only: bool = Query(default=False, description="Only show unresolved"),
) -> AnomalyListResponse:
    """List detected anomalies with optional filtering."""

    # Parse severity filter
    severity_filter = None
    if severity:
        try:
            severity_filter = AnomalySeverity[severity.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid severity: {severity}"
            )

    # Parse anomaly type filter
    type_filter = None
    if anomaly_type:
        try:
            type_filter = AnomalyType[anomaly_type.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid anomaly type: {anomaly_type}"
            )

    # Get anomalies
    since = datetime.now(UTC) - timedelta(hours=hours)

    if unresolved_only:
        anomalies = anomaly_system.get_unresolved_anomalies()
        # Apply time filter
        anomalies = [a for a in anomalies if a.detected_at >= since]
    else:
        anomalies = anomaly_system.get_recent_anomalies(
            since=since,
            severity=severity_filter,
            type_filter=type_filter
        )

    # Apply additional filters
    if severity_filter and not unresolved_only:
        anomalies = [a for a in anomalies if a.severity == severity_filter]
    if type_filter:
        anomalies = [a for a in anomalies if a.anomaly_type == type_filter]

    # Convert to response format
    response_anomalies = [
        AnomalyResponse(
            id=a.id,
            metric_name=a.metric_name,
            anomaly_type=a.anomaly_type.name,
            severity=a.severity.name,
            anomaly_score=a.anomaly_score,
            value=a.value,
            expected_value=a.expected_value,
            detected_at=a.detected_at,
            acknowledged=a.acknowledged,
            acknowledged_at=a.acknowledged_at,
            acknowledged_by=a.acknowledged_by,
            resolved=a.resolved,
            resolved_at=a.resolved_at,
            resolved_by=a.resolved_by,
            context=a.context
        )
        for a in anomalies
    ]

    unresolved = len([a for a in anomalies if not a.resolved])

    return AnomalyListResponse(
        anomalies=response_anomalies,
        total=len(response_anomalies),
        unresolved_count=unresolved
    )


@router.post(
    "/anomalies/{anomaly_id}/acknowledge",
    response_model=AnomalyResponse,
    summary="Acknowledge an anomaly",
    description="Mark an anomaly as acknowledged"
)
async def acknowledge_anomaly(
    anomaly_id: str,
    request: AnomalyAcknowledgeRequest,
    user: TrustedUserDep,
    anomaly_system: AnomalySystemDep,
    event_system: EventSystemDep,
) -> AnomalyResponse:
    """Acknowledge an anomaly."""

    success = anomaly_system.acknowledge(anomaly_id, str(user.id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly '{anomaly_id}' not found"
        )

    # Get the updated anomaly to return
    anomaly = anomaly_system.get_anomaly(anomaly_id)

    # Resilience: Record anomaly acknowledgment metric
    record_anomaly_acknowledged(anomaly_id, anomaly.severity.name)

    await event_system.emit(
        "ANOMALY_ACKNOWLEDGED",
        {
            "anomaly_id": anomaly_id,
            "acknowledged_by": str(user.id),
            "notes": request.notes
        }
    )
    return AnomalyResponse(
        id=anomaly.id,
        metric_name=anomaly.metric_name,
        anomaly_type=anomaly.anomaly_type.name,
        severity=anomaly.severity.name,
        anomaly_score=anomaly.anomaly_score,
        value=anomaly.value,
        expected_value=anomaly.expected_value,
        detected_at=anomaly.detected_at,
        acknowledged=anomaly.acknowledged,
        acknowledged_at=anomaly.acknowledged_at,
        acknowledged_by=anomaly.acknowledged_by,
        resolved=anomaly.resolved,
        resolved_at=anomaly.resolved_at,
        resolved_by=anomaly.resolved_by,
        context=anomaly.context
    )


@router.post(
    "/anomalies/{anomaly_id}/resolve",
    response_model=AnomalyResponse,
    summary="Resolve an anomaly",
    description="Mark an anomaly as resolved"
)
async def resolve_anomaly(
    anomaly_id: str,
    user: TrustedUserDep,
    anomaly_system: AnomalySystemDep,
    event_system: EventSystemDep,
) -> AnomalyResponse:
    """Resolve an anomaly."""

    success = anomaly_system.resolve(anomaly_id, str(user.id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly '{anomaly_id}' not found"
        )

    # Get the updated anomaly to return
    anomaly = anomaly_system.get_anomaly(anomaly_id)

    # Resilience: Record anomaly resolution metric
    record_anomaly_resolved(anomaly_id, anomaly.severity.name)

    await event_system.emit(
        "ANOMALY_RESOLVED",
        {
            "anomaly_id": anomaly_id,
            "resolved_by": str(user.id)
        }
    )
    return AnomalyResponse(
        id=anomaly.id,
        metric_name=anomaly.metric_name,
        anomaly_type=anomaly.anomaly_type.name,
        severity=anomaly.severity.name,
        anomaly_score=anomaly.anomaly_score,
        value=anomaly.value,
        expected_value=anomaly.expected_value,
        detected_at=anomaly.detected_at,
        acknowledged=anomaly.acknowledged,
        acknowledged_at=anomaly.acknowledged_at,
        acknowledged_by=anomaly.acknowledged_by,
        resolved=anomaly.resolved,
        resolved_at=anomaly.resolved_at,
        resolved_by=anomaly.resolved_by,
        context=anomaly.context
    )


@router.post(
    "/metrics/record",
    summary="Record a metric value",
    description="Record a metric value for anomaly detection"
)
async def record_metric(
    request: RecordMetricRequest,
    _user: CurrentUserDep,
    anomaly_system: AnomalySystemDep,
) -> dict[str, Any]:
    """Record a metric value for anomaly detection."""

    anomaly = anomaly_system.record_metric(
        metric_name=request.metric_name,
        value=request.value,
        context=request.context
    )

    response = {"recorded": True, "metric_name": request.metric_name}

    if anomaly:
        response["anomaly_detected"] = True
        response["anomaly"] = AnomalyResponse(
            id=anomaly.id,
            metric_name=anomaly.metric_name,
            anomaly_type=anomaly.anomaly_type.name,
            severity=anomaly.severity.name,
            anomaly_score=anomaly.anomaly_score,
            value=anomaly.value,
            expected_value=anomaly.expected_value,
            detected_at=anomaly.detected_at,
            acknowledged=anomaly.acknowledged,
            resolved=anomaly.resolved,
            context=anomaly.context
        ).model_dump()

    return response


# ============================================================================
# Canary Deployment Endpoints
# ============================================================================


@router.get(
    "/canaries",
    response_model=CanaryListResponse,
    summary="List active canary deployments",
    description="Returns all active canary deployments"
)
async def list_canary_deployments(
    _user: CurrentUserDep,
    canary_manager: CanaryManagerDep,
) -> CanaryListResponse:
    """List all active canary deployments."""

    deployments = []

    for overlay_id, deployment in canary_manager._deployments.items():
        deployments.append(CanaryDeploymentResponse(
            overlay_id=overlay_id,
            current_stage=deployment.current_stage,
            total_stages=len(deployment.stages),
            traffic_percentage=deployment.get_traffic_percentage(),
            started_at=deployment.started_at,
            current_stage_started_at=deployment.current_stage_started_at,
            last_advanced_at=deployment.last_advanced_at,
            success_count=deployment.success_count,
            failure_count=deployment.failure_count,
            rollback_on_failure=deployment.rollback_on_failure,
            is_complete=deployment.is_complete(),
            can_advance=deployment.can_advance()
        ))

    return CanaryListResponse(
        deployments=deployments,
        total=len(deployments)
    )


# ============================================================================
# System Metrics Endpoints
# ============================================================================


@router.get(
    "/metrics",
    response_model=SystemMetricsResponse,
    summary="Get system metrics",
    description="Returns comprehensive system metrics"
)
async def get_system_metrics(
    _user: CurrentUserDep,
    db_client: DbClientDep,
    event_system: EventSystemDep,
    overlay_manager: OverlayManagerDep,
    pipeline: PipelineDep,
    circuit_registry: CircuitRegistryDep,
    anomaly_system: AnomalySystemDep,
    canary_manager: CanaryManagerDep,
) -> SystemMetricsResponse:
    """Get comprehensive system metrics."""

    # Event system metrics
    events_emitted = getattr(event_system, "_events_emitted", 0)
    events_processed = getattr(event_system, "_events_processed", 0)

    # Overlay metrics
    active_overlays = len([
        o for o in overlay_manager._overlays.values()
        if o.enabled
    ]) if hasattr(overlay_manager, "_overlays") else 0

    # Pipeline metrics
    pipeline_executions = getattr(pipeline, "_execution_count", 0)
    total_duration = getattr(pipeline, "_total_duration_ms", 0)
    avg_duration = (
        total_duration / pipeline_executions
        if pipeline_executions > 0 else 0.0
    )

    # Circuit breaker metrics
    open_breakers = sum(
        1 for cb in circuit_registry._breakers.values()
        if cb.state.name == "OPEN"
    ) if hasattr(circuit_registry, "_breakers") else 0

    # Anomaly metrics
    active_anomalies = len(anomaly_system.get_unresolved_anomalies())

    # Canary metrics
    canary_count = len(canary_manager._deployments) if hasattr(canary_manager, "_deployments") else 0

    # Database check
    try:
        db_connected = await db_client.verify_connection()
    except Exception:
        db_connected = False

    # Try to get memory usage
    memory_mb = None
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
    except ImportError:
        pass

    return SystemMetricsResponse(
        timestamp=datetime.now(UTC),
        events_emitted_total=events_emitted,
        events_processed_total=events_processed,
        active_overlays=active_overlays,
        pipeline_executions=pipeline_executions,
        average_pipeline_duration_ms=avg_duration,
        open_circuit_breakers=open_breakers,
        active_anomalies=active_anomalies,
        canary_deployments=canary_count,
        db_connected=db_connected,
        memory_usage_mb=memory_mb
    )


# ============================================================================
# Event Log Endpoints
# ============================================================================


@router.get(
    "/events/recent",
    response_model=EventListResponse,
    summary="Get recent events",
    description="Returns recently emitted events"
)
async def get_recent_events(
    _user: TrustedUserDep,
    event_system: EventSystemDep,
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None, description="Filter by event type"),
) -> EventListResponse:
    """Get recently emitted events."""

    # Get event history from event system
    history = getattr(event_system, "_event_history", [])

    # Filter by type if specified
    if event_type:
        history = [e for e in history if e.get("event_type") == event_type]

    # Limit results
    history = history[-limit:]

    events = [
        EventLogResponse(
            event_type=e.get("event_type", "UNKNOWN"),
            timestamp=e.get("timestamp", datetime.now(UTC)),
            data=e.get("data", {}),
            correlation_id=e.get("correlation_id")
        )
        for e in history
    ]

    return EventListResponse(
        events=events,
        total=len(events)
    )


# ============================================================================
# Administrative Endpoints
# ============================================================================


class MaintenanceModeRequest(BaseModel):
    """Request to enable/disable maintenance mode."""
    message: str | None = Field(
        default=None,
        max_length=500,
        description="Custom maintenance message to display"
    )


class MaintenanceModeResponse(BaseModel):
    """Maintenance mode status response."""
    enabled: bool
    enabled_at: datetime | None = None
    enabled_by: str | None = None
    message: str


@router.post(
    "/maintenance/enable",
    response_model=MaintenanceModeResponse,
    summary="Enable maintenance mode",
    description="Put the system into maintenance mode (ADMIN only)"
)
async def enable_maintenance_mode(
    user: AdminUserDep,
    event_system: EventSystemDep,
    request: MaintenanceModeRequest | None = None,
) -> MaintenanceModeResponse:
    """
    Enable maintenance mode.

    When enabled:
    - Non-admin API requests will receive 503 Service Unavailable
    - Health endpoints remain accessible
    - Admin users can still access all endpoints
    """
    custom_message = request.message if request else None

    # Set the maintenance mode state
    set_maintenance_mode(
        enabled=True,
        user_id=str(user.id),
        message=custom_message
    )

    # Resilience: Record maintenance mode change metric
    record_maintenance_mode_changed(enabled=True)

    await event_system.emit(
        "MAINTENANCE_MODE_ENABLED",
        {
            "enabled_by": str(user.id),
            "message": custom_message or get_maintenance_message()
        }
    )

    return MaintenanceModeResponse(
        enabled=True,
        enabled_at=_maintenance_state["enabled_at"],
        enabled_by=str(user.id),
        message=get_maintenance_message()
    )


@router.post(
    "/maintenance/disable",
    response_model=MaintenanceModeResponse,
    summary="Disable maintenance mode",
    description="Take the system out of maintenance mode (ADMIN only)"
)
async def disable_maintenance_mode(
    user: AdminUserDep,
    event_system: EventSystemDep,
) -> MaintenanceModeResponse:
    """Disable maintenance mode and restore normal operations."""

    # Set the maintenance mode state
    set_maintenance_mode(enabled=False, user_id=str(user.id))

    # Resilience: Record maintenance mode change metric
    record_maintenance_mode_changed(enabled=False)

    await event_system.emit(
        "MAINTENANCE_MODE_DISABLED",
        {"disabled_by": str(user.id)}
    )

    return MaintenanceModeResponse(
        enabled=False,
        enabled_at=None,
        enabled_by=None,
        message="System is operational"
    )


@router.get(
    "/maintenance/status",
    response_model=MaintenanceModeResponse,
    summary="Get maintenance mode status",
    description="Check if maintenance mode is enabled"
)
async def get_maintenance_status() -> MaintenanceModeResponse:
    """Get current maintenance mode status."""
    return MaintenanceModeResponse(
        enabled=_maintenance_state["enabled"],
        enabled_at=_maintenance_state["enabled_at"],
        enabled_by=_maintenance_state["enabled_by"],
        message=get_maintenance_message() if _maintenance_state["enabled"] else "System is operational"
    )


class CacheClearRequest(BaseModel):
    """Request to clear specific caches."""
    caches: list[str] | None = Field(
        default=None,
        description="Specific caches to clear. If empty/null, clears all caches."
    )


class CacheClearResponse(BaseModel):
    """Cache clear operation response."""
    status: str
    caches_cleared: list[str]
    errors: list[str] = Field(default_factory=list)


@router.post(
    "/cache/clear",
    response_model=CacheClearResponse,
    summary="Clear system caches",
    description="Clear various system caches (CORE+ only)"
)
async def clear_caches(
    user: CoreUserDep,
    event_system: EventSystemDep,
    request: CacheClearRequest | None = None,
) -> CacheClearResponse:
    """
    Clear system caches.

    Available caches:
    - token_blacklist: In-memory token blacklist (Redis is separate)
    - query_cache: Query result caches
    - health_cache: Cached health check results
    - metrics_cache: Cached system metrics
    - embedding_cache: Cached embeddings (if using local cache)

    If no specific caches are specified, all caches are cleared.
    """
    cleared = []
    errors = []

    # Determine which caches to clear
    requested_caches = request.caches if request and request.caches else None
    clear_all = requested_caches is None

    # Clear token blacklist in-memory cache
    if clear_all or "token_blacklist" in (requested_caches or []):
        try:
            from forge.security.tokens import TokenBlacklist
            with TokenBlacklist._lock:
                count = len(TokenBlacklist._blacklist)
                TokenBlacklist._blacklist.clear()
                TokenBlacklist._expiry_times.clear()
                cleared.append(f"token_blacklist ({count} entries)")
        except Exception as e:
            errors.append(f"token_blacklist: {str(e)}")

    # Clear query cache (from resilience integration)
    if clear_all or "query_cache" in (requested_caches or []):
        try:
            from forge.resilience.integration import clear_query_cache
            count = clear_query_cache()
            cleared.append(f"query_cache ({count} entries)")
        except ImportError:
            # Function not available
            pass
        except Exception as e:
            errors.append(f"query_cache: {str(e)}")

    # Clear health status cache
    if clear_all or "health_cache" in (requested_caches or []):
        try:
            # Clear the cached health status
            from forge.resilience.integration import _health_cache
            if hasattr(_health_cache, "clear"):
                _health_cache.clear()
                cleared.append("health_cache")
        except ImportError:
            pass
        except Exception as e:
            errors.append(f"health_cache: {str(e)}")

    # Clear metrics cache
    if clear_all or "metrics_cache" in (requested_caches or []):
        try:
            from forge.resilience.integration import _metrics_cache
            if hasattr(_metrics_cache, "clear"):
                _metrics_cache.clear()
                cleared.append("metrics_cache")
        except ImportError:
            pass
        except Exception as e:
            errors.append(f"metrics_cache: {str(e)}")

    # Clear embedding service cache if available
    if clear_all or "embedding_cache" in (requested_caches or []):
        try:
            from forge.services.embedding import get_embedding_service
            svc = get_embedding_service()
            if hasattr(svc, "_cache") and svc._cache is not None:
                count = len(svc._cache)
                svc._cache.clear()
                cleared.append(f"embedding_cache ({count} entries)")
        except Exception as e:
            errors.append(f"embedding_cache: {str(e)}")

    # Resilience: Record cache clear metric
    record_cache_cleared(cleared)

    await event_system.emit(
        EventType.SYSTEM_EVENT,
        {
            "event_name": "caches_cleared",
            "cleared_by": str(user.id),
            "caches": cleared,
            "errors": errors
        }
    )

    return CacheClearResponse(
        status="completed" if not errors else "partial",
        caches_cleared=cleared,
        errors=errors
    )


@router.get(
    "/info",
    summary="Get system information",
    description="Returns basic system information"
)
async def get_system_info() -> dict[str, Any]:
    """Get basic system information."""

    import sys

    return {
        "name": "Forge Knowledge Cascade",
        "version": "0.1.0",
        "python_version": sys.version,
        "api_version": "v1",
        "timestamp": datetime.now(UTC).isoformat()
    }


# ============================================================================
# System Status Endpoint (simplified status view)
# ============================================================================


class SystemStatusResponse(BaseModel):
    """Simplified system status response."""

    status: str = Field(description="Overall status: operational, degraded, down")
    version: str = Field(default="0.1.0")
    uptime_seconds: float
    timestamp: datetime
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Status of each service: operational, degraded, down"
    )


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Get system status",
    description="Returns simplified system status for monitoring"
)
async def get_system_status(
    db_client: DbClientDep,
    event_system: EventSystemDep,
    circuit_registry: CircuitRegistryDep,
) -> SystemStatusResponse:
    """Get simplified system status."""

    # Calculate uptime
    uptime = (
        datetime.now(UTC) - event_system._start_time
    ).total_seconds() if hasattr(event_system, "_start_time") else 0.0

    services = {}

    # Database status
    try:
        db_ok = await db_client.verify_connection()
        services["database"] = "operational" if db_ok else "down"
    except Exception:
        services["database"] = "down"

    # Event system status
    event_running = event_system._running if hasattr(event_system, "_running") else True
    services["event_system"] = "operational" if event_running else "degraded"

    # Circuit breakers status
    open_breakers = sum(
        1 for cb in circuit_registry._breakers.values()
        if cb.state.name == "OPEN"
    ) if hasattr(circuit_registry, "_breakers") else 0
    services["circuit_breakers"] = "degraded" if open_breakers > 0 else "operational"

    # API is operational if we got here
    services["api"] = "operational"

    # Determine overall status
    if services["database"] == "down":
        overall = "down"
    elif any(s == "degraded" for s in services.values()):
        overall = "degraded"
    else:
        overall = "operational"

    return SystemStatusResponse(
        status=overall,
        uptime_seconds=uptime,
        timestamp=datetime.now(UTC),
        services=services,
    )


# ============================================================================
# Audit Log Endpoints
# ============================================================================

class AuditLogEntry(BaseModel):
    """Audit log entry response."""
    id: str
    action: str  # Maps from AuditEvent.operation
    entity_type: str
    entity_id: str
    user_id: str | None  # Maps from AuditEvent.actor_id
    details: dict[str, Any]  # Maps from AuditEvent.changes
    correlation_id: str | None
    timestamp: datetime


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""
    items: list[AuditLogEntry]
    total: int
    page: int
    per_page: int


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Get audit log",
    description="Retrieve audit log entries with optional filtering (ADMIN only)"
)
async def get_audit_log(
    user: AdminUserDep,
    db: DbClientDep,
    action: str | None = Query(None, description="Filter by action type"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditLogResponse:
    """
    Get audit log entries.

    Returns paginated audit trail of all system operations.
    """
    from forge.repositories.audit_repository import AuditRepository

    audit_repo = AuditRepository(db)

    # Build filters
    filters = {}
    if action:
        filters["action"] = action
    if entity_type:
        filters["entity_type"] = entity_type
    if user_id:
        filters["user_id"] = user_id

    # Query audit logs
    entries, total = await audit_repo.list(
        offset=offset,
        limit=limit,
        filters=filters,
    )

    return AuditLogResponse(
        items=[
            AuditLogEntry(
                id=e.id,
                action=e.action,
                entity_type=e.resource_type,
                entity_id=e.resource_id or "",
                user_id=e.actor_id,
                details=e.details or {},
                correlation_id=e.correlation_id,
                timestamp=e.timestamp,
            )
            for e in entries
        ],
        total=total,
        page=offset // limit + 1,
        per_page=limit,
    )


@router.get(
    "/audit-log/{correlation_id}",
    summary="Get audit trail by correlation ID",
    description="Get all audit entries for a specific operation"
)
async def get_audit_trail(
    correlation_id: str,
    user: AdminUserDep,
    db: DbClientDep,
) -> list[AuditLogEntry]:
    """
    Get all audit entries for a correlation ID.

    Useful for tracing a complete operation across services.
    """
    from forge.repositories.audit_repository import AuditRepository

    audit_repo = AuditRepository(db)
    entries = await audit_repo.get_by_correlation_id(correlation_id)

    return [
        AuditLogEntry(
            id=e.id,
            action=e.action,
            entity_type=e.resource_type,
            entity_id=e.resource_id or "",
            user_id=e.actor_id,
            details=e.details or {},
            correlation_id=e.correlation_id,
            timestamp=e.timestamp,
        )
        for e in entries
    ]


# ============================================================================
# Alias Endpoints for convenience
# ============================================================================


@router.get(
    "/audit",
    response_model=AuditLogResponse,
    summary="Get audit log (alias)",
    description="Alias for /audit-log endpoint"
)
async def get_audit_alias(
    user: AdminUserDep,
    db: DbClientDep,
    action: str | None = Query(None, description="Filter by action type"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditLogResponse:
    """Alias for /audit-log - Get audit log entries."""
    return await get_audit_log(
        user=user,
        db=db,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="Get recent events (alias)",
    description="Alias for /events/recent endpoint"
)
async def get_events_alias(
    _user: TrustedUserDep,
    event_system: EventSystemDep,
    limit: int = Query(default=50, ge=1, le=500),
    event_type: str | None = Query(default=None, description="Filter by event type"),
) -> EventListResponse:
    """Alias for /events/recent - Get recently emitted events."""
    return await get_recent_events(
        _user=_user,
        event_system=event_system,
        limit=limit,
        event_type=event_type,
    )
