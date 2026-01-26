"""
Forge Cascade V2 - Immune System
Self-healing infrastructure for Forge's digital society.

The Immune System provides:
1. Circuit Breaker - Prevents cascade failures
2. Health Checker - Hierarchical health monitoring
3. Canary Deployments - Safe gradual rollouts
4. Anomaly Detection - ML-based pattern detection

Together, these components ensure Forge remains resilient
and can heal itself from failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forge.database.client import Neo4jClient
    from forge.immune.health_checker import (
        EventSystemProtocol,
        OverlayManagerProtocol,
    )

from forge.immune.anomaly import (
    Anomaly,
    AnomalyDetector,
    AnomalyDetectorConfig,
    AnomalySeverity,
    AnomalyType,
    BehavioralAnomalyDetector,
    CompositeAnomalyDetector,
    ForgeAnomalySystem,
    IsolationForestDetector,
    RateAnomalyDetector,
    StatisticalAnomalyDetector,
    create_forge_anomaly_system,
)
from forge.immune.canary import (
    CanaryConfig,
    CanaryDeployment,
    CanaryManager,
    CanaryMetrics,
    CanaryState,
    OverlayCanaryManager,
    RolloutStrategy,
)
from forge.immune.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    CircuitStats,
    ForgeCircuits,
    circuit_breaker,
    get_circuit_registry,
)
from forge.immune.health_checker import (
    CircuitBreakerHealthCheck,
    CompositeHealthCheck,
    DiskHealthCheck,
    EventSystemHealthCheck,
    ForgeHealthChecker,
    FunctionHealthCheck,
    HealthCheck,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    MemoryHealthCheck,
    Neo4jHealthCheck,
    OverlayHealthCheck,
    create_forge_health_checker,
)

# Convenience factory functions

def create_immune_system(
    db_client: Neo4jClient | None = None,
    overlay_manager: OverlayManagerProtocol | None = None,
    event_system: EventSystemProtocol | None = None,
) -> dict[str, object]:
    """
    Create complete Forge immune system.

    Returns dict with all immune components ready to use.
    """
    circuit_registry = get_circuit_registry()

    health_checker = create_forge_health_checker(
        neo4j_client=db_client,
        overlay_manager=overlay_manager,
        event_system=event_system,
        circuit_registry=circuit_registry,
    )

    anomaly_system = create_forge_anomaly_system(
        include_isolation_forest=True,
        include_rate_detector=True,
        include_behavioral=True,
    )

    canary_manager = OverlayCanaryManager()

    return {
        "circuit_registry": circuit_registry,
        "health_checker": health_checker,
        "anomaly_system": anomaly_system,
        "canary_manager": canary_manager,
    }


__all__ = [
    # Circuit Breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitStats",
    "CircuitBreakerError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "get_circuit_registry",
    "circuit_breaker",
    "ForgeCircuits",

    # Health Checker
    "HealthStatus",
    "HealthCheckResult",
    "HealthCheckConfig",
    "HealthCheck",
    "CompositeHealthCheck",
    "FunctionHealthCheck",
    "Neo4jHealthCheck",
    "OverlayHealthCheck",
    "EventSystemHealthCheck",
    "CircuitBreakerHealthCheck",
    "MemoryHealthCheck",
    "DiskHealthCheck",
    "ForgeHealthChecker",
    "create_forge_health_checker",

    # Canary
    "CanaryState",
    "RolloutStrategy",
    "CanaryConfig",
    "CanaryMetrics",
    "CanaryDeployment",
    "CanaryManager",
    "OverlayCanaryManager",

    # Anomaly Detection
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "AnomalyDetectorConfig",
    "AnomalyDetector",
    "StatisticalAnomalyDetector",
    "IsolationForestDetector",
    "RateAnomalyDetector",
    "BehavioralAnomalyDetector",
    "CompositeAnomalyDetector",
    "ForgeAnomalySystem",
    "create_forge_anomaly_system",

    # Factory
    "create_immune_system",
]
