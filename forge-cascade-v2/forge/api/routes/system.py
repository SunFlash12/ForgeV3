"""
Forge System API Routes

Provides endpoints for:
- Health checks and readiness probes
- Immune system monitoring (circuit breakers, anomalies, canaries)
- System metrics and status
- Administrative operations
"""

import asyncio
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
        enabled = _maintenance_state["enabled"]
        return bool(enabled)


def get_maintenance_message() -> str:
    """Get the maintenance mode message."""
    # SECURITY FIX (Audit 3): Acquire lock for consistent read
    with _maintenance_lock:
        message = _maintenance_state["message"]
        return str(message) if message else "System is under maintenance. Please try again later."


def set_maintenance_mode(enabled: bool, user_id: str | None = None, message: str | None = None) -> None:
    """Set maintenance mode state."""
    with _maintenance_lock:
        _maintenance_state["enabled"] = enabled
        if enabled:
            _maintenance_state["enabled_at"] = datetime.now(UTC)  # type: ignore[assignment]
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
    start_time = getattr(event_system, "_start_time", None)
    uptime = (datetime.now(UTC) - start_time).total_seconds() if start_time else 0.0

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
    except (OSError, ConnectionError, TimeoutError, RuntimeError) as e:
        # SECURITY FIX (Audit 3): Don't expose internal error details
        import structlog
        structlog.get_logger(__name__).error("database_health_check_failed", error=str(e))
        components["database"] = {"status": "unhealthy", "error": "Database connection failed"}
        checks["database"] = False

    # Event system health
    event_healthy: bool = getattr(event_system, "_running", True)
    event_queue = getattr(event_system, "_queue", None)
    queue_size = event_queue.qsize() if event_queue else 0
    components["event_system"] = {
        "status": "healthy" if event_healthy else "degraded",
        "queue_size": str(queue_size)
    }
    checks["event_system"] = event_healthy

    # Overlay manager health
    overlays_dict = getattr(overlay_manager, "_overlays", {})
    overlay_count = len(overlays_dict)
    active_count = len([o for o in overlays_dict.values() if o.enabled])
    components["overlay_manager"] = {
        "status": "healthy",
        "total_overlays": str(overlay_count),
        "active_overlays": str(active_count)
    }
    checks["overlay_manager"] = True

    # Circuit breakers health
    breakers_dict = getattr(circuit_registry, "_breakers", {})
    open_breakers = sum(
        1 for cb in breakers_dict.values()
        if cb.state.name == "OPEN"
    )

    total_breakers = len(breakers_dict)
    components["circuit_breakers"] = {
        "status": "degraded" if open_breakers > 0 else "healthy",
        "total": str(total_breakers),
        "open": str(open_breakers)
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
        "unresolved": str(unresolved),
        "critical": str(critical_anomalies)
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
    except (OSError, ConnectionError, TimeoutError, RuntimeError) as e:
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

    breakers_dict = getattr(circuit_registry, "_breakers", {})
    for name, cb in breakers_dict.items():
        state_name = cb.state.name
        if state_name == "OPEN":
            open_count += 1
        elif state_name == "HALF_OPEN":
            half_open_count += 1

        # Access circuit breaker stats and config for status
        stats = cb.stats
        config = cb.config
        breakers.append(CircuitBreakerStatus(
            name=name,
            state=state_name,
            failure_count=stats.failed_calls,
            success_count=stats.successful_calls,
            last_failure_time=datetime.fromtimestamp(stats.last_failure_time, tz=UTC) if stats.last_failure_time else None,
            last_success_time=datetime.fromtimestamp(stats.last_success_time, tz=UTC) if stats.last_success_time else None,
            reset_timeout=config.recovery_timeout,
            failure_threshold=config.failure_threshold,
            success_threshold=config.success_threshold
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

    breakers_dict = getattr(circuit_registry, "_breakers", {})
    if name not in breakers_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found"
        )

    cb = breakers_dict[name]
    await cb.reset()

    # Resilience: Record circuit breaker reset metric
    record_circuit_breaker_reset(name)

    # Emit event
    await event_system.emit(
        EventType.IMMUNE_EVENT,
        {
            "event_name": "CIRCUIT_BREAKER_RESET",
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

    if anomaly is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly '{anomaly_id}' not found after acknowledgment"
        )

    # Resilience: Record anomaly acknowledgment metric
    record_anomaly_acknowledged(anomaly_id, anomaly.severity.name)

    await event_system.emit(
        EventType.ANOMALY_DETECTED,
        {
            "event_name": "ANOMALY_ACKNOWLEDGED",
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

    if anomaly is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly '{anomaly_id}' not found after resolution"
        )

    # Resilience: Record anomaly resolution metric
    record_anomaly_resolved(anomaly_id, anomaly.severity.name)

    await event_system.emit(
        EventType.ANOMALY_DETECTED,
        {
            "event_name": "ANOMALY_RESOLVED",
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

    anomaly = await anomaly_system.record_metric(
        metric_name=request.metric_name,
        value=request.value,
        context=request.context
    )

    response: dict[str, Any] = {"recorded": True, "metric_name": request.metric_name}

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

    deployments_dict = getattr(canary_manager, "_deployments", {})
    for overlay_id, deployment in deployments_dict.items():
        # Map CanaryDeployment attributes to response model
        started = deployment.started_at or deployment.created_at
        step_started = datetime.fromtimestamp(deployment.step_started_at, tz=UTC) if deployment.step_started_at else started

        # Calculate total stages based on config (linear strategy increments)
        config = deployment.config
        total_stages = int((config.max_percentage - config.initial_percentage) / config.increment_percentage) + 1

        # Check if complete and can advance
        is_complete = deployment.state.name in ("SUCCEEDED", "FAILED")
        can_advance = deployment.state.name == "RUNNING" and deployment.current_percentage < config.max_percentage

        deployments.append(CanaryDeploymentResponse(
            overlay_id=overlay_id,
            current_stage=deployment.current_step,
            total_stages=total_stages,
            traffic_percentage=deployment.current_percentage,
            started_at=started,
            current_stage_started_at=step_started,
            last_advanced_at=step_started if deployment.current_step > 0 else None,
            success_count=deployment.metrics.canary_requests - deployment.metrics.canary_errors,
            failure_count=deployment.metrics.canary_errors,
            rollback_on_failure=config.auto_rollback,
            is_complete=is_complete,
            can_advance=can_advance
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
    overlays_dict_metrics = getattr(overlay_manager, "_overlays", {})
    active_overlays = len([
        o for o in overlays_dict_metrics.values()
        if o.enabled
    ])

    # Pipeline metrics
    pipeline_executions = getattr(pipeline, "_execution_count", 0)
    total_duration = getattr(pipeline, "_total_duration_ms", 0)
    avg_duration = (
        total_duration / pipeline_executions
        if pipeline_executions > 0 else 0.0
    )

    # Circuit breaker metrics
    breakers_dict_metrics = getattr(circuit_registry, "_breakers", {})
    open_breakers = sum(
        1 for cb in breakers_dict_metrics.values()
        if cb.state.name == "OPEN"
    )

    # Anomaly metrics
    active_anomalies = len(anomaly_system.get_unresolved_anomalies())

    # Canary metrics
    deployments_dict_metrics = getattr(canary_manager, "_deployments", {})
    canary_count = len(deployments_dict_metrics)

    # Database check
    try:
        db_connected = await db_client.verify_connection()
    except (OSError, ConnectionError, TimeoutError, RuntimeError):
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
        EventType.SYSTEM_EVENT,
        {
            "event_name": "MAINTENANCE_MODE_ENABLED",
            "enabled_by": str(user.id),
            "message": custom_message or get_maintenance_message()
        }
    )

    with _maintenance_lock:
        enabled_at_val = _maintenance_state["enabled_at"]
    return MaintenanceModeResponse(
        enabled=True,
        enabled_at=enabled_at_val if isinstance(enabled_at_val, datetime) else None,
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
        EventType.SYSTEM_EVENT,
        {
            "event_name": "MAINTENANCE_MODE_DISABLED",
            "disabled_by": str(user.id)
        }
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
    with _maintenance_lock:
        enabled_val = bool(_maintenance_state["enabled"])
        enabled_at_val = _maintenance_state["enabled_at"]
        enabled_by_val = _maintenance_state["enabled_by"]
    return MaintenanceModeResponse(
        enabled=enabled_val,
        enabled_at=enabled_at_val if isinstance(enabled_at_val, datetime) else None,
        enabled_by=str(enabled_by_val) if enabled_by_val else None,
        message=get_maintenance_message() if enabled_val else "System is operational"
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
            blacklist_lock = getattr(TokenBlacklist, "_lock", None)
            if blacklist_lock:
                with blacklist_lock:
                    blacklist = getattr(TokenBlacklist, "_blacklist", None)
                    expiry_times = getattr(TokenBlacklist, "_expiry_times", None)
                    count = len(blacklist) if blacklist else 0
                    if blacklist:
                        blacklist.clear()
                    if expiry_times:
                        expiry_times.clear()
                    cleared.append(f"token_blacklist ({count} entries)")
            else:
                cleared.append("token_blacklist (no lock)")
        except (RuntimeError, AttributeError, OSError) as e:
            errors.append(f"token_blacklist: {str(e)}")

    # Clear query cache (from resilience integration)
    if clear_all or "query_cache" in (requested_caches or []):
        try:
            import forge.resilience.integration as resilience_module
            clear_query_cache_fn = getattr(resilience_module, "clear_query_cache", None)
            if clear_query_cache_fn:
                count = clear_query_cache_fn()
                cleared.append(f"query_cache ({count} entries)")
        except ImportError:
            # Function not available
            pass
        except (RuntimeError, AttributeError, OSError) as e:
            errors.append(f"query_cache: {str(e)}")

    # Clear health status cache
    if clear_all or "health_cache" in (requested_caches or []):
        try:
            # Clear the cached health status
            import forge.resilience.integration as resilience_module
            health_cache = getattr(resilience_module, "_health_cache", None)
            if health_cache and hasattr(health_cache, "clear"):
                health_cache.clear()
                cleared.append("health_cache")
        except ImportError:
            pass
        except (RuntimeError, AttributeError, OSError) as e:
            errors.append(f"health_cache: {str(e)}")

    # Clear metrics cache
    if clear_all or "metrics_cache" in (requested_caches or []):
        try:
            import forge.resilience.integration as resilience_module
            metrics_cache = getattr(resilience_module, "_metrics_cache", None)
            if metrics_cache and hasattr(metrics_cache, "clear"):
                metrics_cache.clear()
                cleared.append("metrics_cache")
        except ImportError:
            pass
        except (RuntimeError, AttributeError, OSError) as e:
            errors.append(f"metrics_cache: {str(e)}")

    # Clear embedding service cache if available
    if clear_all or "embedding_cache" in (requested_caches or []):
        try:
            from forge.services.embedding import get_embedding_service
            svc = get_embedding_service()
            cache = getattr(svc, "_cache", None)
            if cache is not None:
                count = len(cache) if hasattr(cache, "__len__") else 0
                clear_method = getattr(cache, "clear", None)
                if clear_method:
                    await clear_method() if asyncio.iscoroutinefunction(clear_method) else clear_method()
                cleared.append(f"embedding_cache ({count} entries)")
        except (RuntimeError, AttributeError, ImportError, OSError) as e:
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
    start_time_status = getattr(event_system, "_start_time", None)
    uptime = (datetime.now(UTC) - start_time_status).total_seconds() if start_time_status else 0.0

    services = {}

    # Database status
    try:
        db_ok = await db_client.verify_connection()
        services["database"] = "operational" if db_ok else "down"
    except (OSError, ConnectionError, TimeoutError, RuntimeError):
        services["database"] = "down"

    # Event system status
    event_running: bool = getattr(event_system, "_running", True)
    services["event_system"] = "operational" if event_running else "degraded"

    # Circuit breakers status
    breakers_dict_status = getattr(circuit_registry, "_breakers", {})
    open_breakers = sum(
        1 for cb in breakers_dict_status.values()
        if cb.state.name == "OPEN"
    )
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
    entries, total = await audit_repo.list_events(
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


# ============================================================================
# Dashboard Metrics Endpoints
# ============================================================================


class ActivityDataPoint(BaseModel):
    """Single activity data point for timeline charts."""
    time: str = Field(description="Time label (e.g., '08:00')")
    capsules: int = Field(description="Capsule count in this period")
    votes: int = Field(description="Vote count in this period")
    events: int = Field(description="Event count in this period")


class ActivityTimelineResponse(BaseModel):
    """Activity timeline data for dashboard charts."""
    data: list[ActivityDataPoint]
    total_capsules: int
    total_votes: int
    total_events: int
    period_hours: int


@router.get(
    "/metrics/activity-timeline",
    response_model=ActivityTimelineResponse,
    summary="Get activity timeline",
    description="Returns time-series activity data for dashboard charts"
)
async def get_activity_timeline(
    _user: CurrentUserDep,
    db_client: DbClientDep,
    event_system: EventSystemDep,
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
) -> ActivityTimelineResponse:
    """
    Get activity timeline data for dashboard charts.

    Returns capsule, vote, and event counts bucketed by 4-hour periods.
    """
    # Calculate time buckets (every 4 hours for 24h period)
    now = datetime.now(UTC)
    bucket_size = max(1, hours // 6)  # 6 data points

    data_points = []
    total_capsules = 0
    total_votes = 0
    total_events = 0

    # Get event history for event counts
    event_history = getattr(event_system, "_event_history", [])

    for i in range(6):
        # Calculate time range for this bucket
        bucket_end = now - timedelta(hours=i * bucket_size)
        bucket_start = bucket_end - timedelta(hours=bucket_size)
        time_label = bucket_end.strftime("%H:00")

        # Query capsules created in this period
        capsule_query = """
        MATCH (c:Capsule)
        WHERE c.created_at >= $start AND c.created_at < $end
        RETURN count(c) as count
        """
        capsule_result = await db_client.execute_single(capsule_query, {
            "start": bucket_start.isoformat(),
            "end": bucket_end.isoformat()
        })
        capsule_count = capsule_result.get("count", 0) if capsule_result else 0

        # Query votes cast in this period
        vote_query = """
        MATCH (v:Vote)
        WHERE v.created_at >= $start AND v.created_at < $end
        RETURN count(v) as count
        """
        vote_result = await db_client.execute_single(vote_query, {
            "start": bucket_start.isoformat(),
            "end": bucket_end.isoformat()
        })
        vote_count = vote_result.get("count", 0) if vote_result else 0

        # Count events from history
        event_count = len([
            e for e in event_history
            if bucket_start <= e.get("timestamp", now) < bucket_end
        ])

        data_points.append(ActivityDataPoint(
            time=time_label,
            capsules=capsule_count,
            votes=vote_count,
            events=event_count
        ))

        total_capsules += capsule_count
        total_votes += vote_count
        total_events += event_count

    # Reverse to show chronological order (oldest first)
    data_points.reverse()

    return ActivityTimelineResponse(
        data=data_points,
        total_capsules=total_capsules,
        total_votes=total_votes,
        total_events=total_events,
        period_hours=hours
    )


class TrustDistributionEntry(BaseModel):
    """Trust level distribution entry."""
    name: str = Field(description="Trust level name")
    value: int = Field(description="Number of users at this level")
    color: str = Field(description="Suggested color for charting")


class TrustDistributionResponse(BaseModel):
    """Trust distribution data for dashboard charts."""
    distribution: list[TrustDistributionEntry]
    total_users: int


@router.get(
    "/metrics/trust-distribution",
    response_model=TrustDistributionResponse,
    summary="Get trust distribution",
    description="Returns user distribution by trust level for dashboard charts"
)
async def get_trust_distribution(
    _user: CurrentUserDep,
    db_client: DbClientDep,
) -> TrustDistributionResponse:
    """
    Get trust distribution data for dashboard charts.

    Returns count of users at each trust level.
    """
    # Trust level colors (consistent with frontend)
    trust_colors = {
        "Core": "#8b5cf6",      # Purple
        "Trusted": "#22c55e",   # Green
        "Standard": "#3b82f6",  # Blue
        "Sandbox": "#f59e0b",   # Amber
        "Untrusted": "#ef4444", # Red
    }

    # Trust level boundaries (based on TrustLevel enum values)
    # Core: 80-100, Trusted: 60-79, Standard: 40-59, Sandbox: 20-39, Untrusted: 0-19
    trust_ranges = [
        ("Core", 80, 101),
        ("Trusted", 60, 80),
        ("Standard", 40, 60),
        ("Sandbox", 20, 40),
        ("Untrusted", 0, 20),
    ]

    distribution = []
    total = 0

    for name, min_val, max_val in trust_ranges:
        query = """
        MATCH (u:User)
        WHERE u.trust_flame >= $min AND u.trust_flame < $max
        RETURN count(u) as count
        """
        result = await db_client.execute_single(query, {"min": min_val, "max": max_val})
        count = result.get("count", 0) if result else 0

        distribution.append(TrustDistributionEntry(
            name=name,
            value=count,
            color=trust_colors.get(name, "#94a3b8")
        ))
        total += count

    return TrustDistributionResponse(
        distribution=distribution,
        total_users=total
    )


class PipelinePhaseMetric(BaseModel):
    """Pipeline phase performance metric."""
    phase: str = Field(description="Pipeline phase name")
    duration: float = Field(description="Average duration in milliseconds")
    execution_count: int = Field(description="Number of executions")


class PipelinePerformanceResponse(BaseModel):
    """Pipeline performance data for dashboard charts."""
    phases: list[PipelinePhaseMetric]
    total_executions: int
    average_total_duration_ms: float


@router.get(
    "/metrics/pipeline-performance",
    response_model=PipelinePerformanceResponse,
    summary="Get pipeline performance",
    description="Returns pipeline phase performance data for dashboard charts"
)
async def get_pipeline_performance(
    _user: CurrentUserDep,
    pipeline: PipelineDep,
) -> PipelinePerformanceResponse:
    """
    Get pipeline phase performance data for dashboard charts.

    Returns average duration for each pipeline phase.
    """
    # Standard pipeline phases with default metrics
    default_phases = [
        "Validation",
        "Security",
        "Intelligence",
        "Governance",
        "Lineage",
        "Consensus",
        "Commit"
    ]

    phases = []
    total_executions = getattr(pipeline, "_execution_count", 0)
    total_duration = getattr(pipeline, "_total_duration_ms", 0)

    # Try to get per-phase metrics from pipeline
    phase_metrics = getattr(pipeline, "_phase_metrics", {})

    for phase_name in default_phases:
        if phase_name in phase_metrics:
            # Real metrics available
            metrics = phase_metrics[phase_name]
            phases.append(PipelinePhaseMetric(
                phase=phase_name,
                duration=metrics.get("avg_duration_ms", 0),
                execution_count=metrics.get("count", 0)
            ))
        else:
            # Estimate based on typical distribution
            # Each phase typically takes ~14% of total time
            estimated_duration = (total_duration / total_executions / 7) if total_executions > 0 else 0
            phases.append(PipelinePhaseMetric(
                phase=phase_name,
                duration=estimated_duration,
                execution_count=total_executions
            ))

    avg_total = total_duration / total_executions if total_executions > 0 else 0

    return PipelinePerformanceResponse(
        phases=phases,
        total_executions=total_executions,
        average_total_duration_ms=avg_total
    )
