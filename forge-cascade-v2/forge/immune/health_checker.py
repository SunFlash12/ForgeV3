"""
Forge Cascade V2 - Hierarchical Health Checker
Multi-level health monitoring system for Forge components.

Health Hierarchy:
- System (top-level aggregate)
  - Database Layer
  - Kernel Layer
  - API Layer
  - External Services

Each component reports: HEALTHY, DEGRADED, UNHEALTHY, or UNKNOWN
"""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from forge.database.client import Neo4jClient


# =============================================================================
# Protocol Definitions for External Dependencies
# =============================================================================


@runtime_checkable
class OverlayManagerProtocol(Protocol):
    """Protocol for overlay manager health checks."""

    async def get_system_status(self) -> dict[str, int | str]: ...


@runtime_checkable
class EventSystemProtocol(Protocol):
    """Protocol for event system health checks."""

    def get_metrics(self) -> dict[str, int]: ...


@runtime_checkable
class CircuitBreakerRegistryProtocol(Protocol):
    """Protocol for circuit breaker registry health checks."""

    def get_health_summary(self) -> dict[str, int | float | list[str]]: ...

logger = structlog.get_logger(__name__)

# Configurable health check thresholds (via environment variables)
HEALTH_DEAD_LETTER_THRESHOLD = int(os.getenv("HEALTH_DEAD_LETTER_THRESHOLD", "100"))
HEALTH_PENDING_EVENTS_THRESHOLD = int(os.getenv("HEALTH_PENDING_EVENTS_THRESHOLD", "1000"))


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"       # Fully operational
    DEGRADED = "degraded"     # Operational but impaired
    UNHEALTHY = "unhealthy"   # Not operational
    UNKNOWN = "unknown"       # Cannot determine status


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, object] = field(default_factory=dict)
    children: list[HealthCheckResult] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        """Check if status is degraded or worse."""
        return self.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for API responses."""
        result: dict[str, object] = {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms

        if self.details:
            result["details"] = self.details

        if self.children:
            result["children"] = [c.to_dict() for c in self.children]

        return result


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""

    # Timing
    timeout_seconds: float = 5.0
    check_interval_seconds: float = 30.0

    # Thresholds
    latency_warning_ms: float = 1000.0   # Degraded if slower
    latency_critical_ms: float = 5000.0   # Unhealthy if slower

    # Retry
    retry_count: int = 2
    retry_delay_seconds: float = 1.0

    # Caching
    cache_ttl_seconds: float = 10.0


class HealthCheck(ABC):
    """Abstract base class for health checks."""

    def __init__(
        self,
        name: str,
        config: HealthCheckConfig | None = None,
    ):
        self.name = name
        self.config = config or HealthCheckConfig()
        self._last_result: HealthCheckResult | None = None
        self._last_check_time: float = 0

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        pass

    async def execute(self, use_cache: bool = True) -> HealthCheckResult:
        """Execute health check with caching and timing."""
        # Check cache
        if use_cache and self._last_result:
            elapsed = time.monotonic() - self._last_check_time
            if elapsed < self.config.cache_ttl_seconds:
                return self._last_result

        # Perform check with retry
        start_time = time.monotonic()
        result: HealthCheckResult | None = None
        last_error: Exception | None = None

        for attempt in range(self.config.retry_count + 1):
            try:
                result = await asyncio.wait_for(
                    self.check(),
                    timeout=self.config.timeout_seconds,
                )
                break
            except TimeoutError:
                last_error = TimeoutError(f"Health check timed out after {self.config.timeout_seconds}s")
            except Exception as e:
                last_error = e

            if attempt < self.config.retry_count:
                await asyncio.sleep(self.config.retry_delay_seconds)

        # Calculate latency
        latency_ms = (time.monotonic() - start_time) * 1000

        # Build result
        if result is None:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(last_error) if last_error else "Check failed",
                latency_ms=latency_ms,
            )
        else:
            result.latency_ms = latency_ms

            # Apply latency thresholds
            if result.status == HealthStatus.HEALTHY:
                if latency_ms > self.config.latency_critical_ms:
                    result.status = HealthStatus.UNHEALTHY
                    result.message = f"Latency critical: {latency_ms:.0f}ms"
                elif latency_ms > self.config.latency_warning_ms:
                    result.status = HealthStatus.DEGRADED
                    result.message = f"Latency warning: {latency_ms:.0f}ms"

        # Update cache
        self._last_result = result
        self._last_check_time = time.monotonic()

        return result


class CompositeHealthCheck(HealthCheck):
    """
    Health check that aggregates multiple child checks.

    Aggregation rules:
    - All children HEALTHY → HEALTHY
    - Any child UNHEALTHY → UNHEALTHY
    - Any child DEGRADED (no UNHEALTHY) → DEGRADED
    - All children UNKNOWN → UNKNOWN
    """

    def __init__(
        self,
        name: str,
        checks: list[HealthCheck] | None = None,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__(name, config)
        self.checks: list[HealthCheck] = checks or []

    def add_check(self, check: HealthCheck) -> None:
        """Add a child health check."""
        self.checks.append(check)

    def remove_check(self, name: str) -> bool:
        """Remove a child health check by name."""
        for i, check in enumerate(self.checks):
            if check.name == name:
                self.checks.pop(i)
                return True
        return False

    async def check(self) -> HealthCheckResult:
        """Perform all child checks and aggregate."""
        if not self.checks:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="No health checks configured",
            )

        # Run all checks concurrently
        child_results = await asyncio.gather(
            *[c.execute() for c in self.checks],
            return_exceptions=True,
        )

        # Process results
        children: list[HealthCheckResult] = []
        statuses: list[HealthStatus] = []

        for result in child_results:
            if isinstance(result, BaseException):
                children.append(HealthCheckResult(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                ))
                statuses.append(HealthStatus.UNHEALTHY)
            elif isinstance(result, HealthCheckResult):
                children.append(result)
                statuses.append(result.status)

        # Aggregate status
        if all(s == HealthStatus.HEALTHY for s in statuses):
            aggregate_status = HealthStatus.HEALTHY
            message = "All checks passed"
        elif HealthStatus.UNHEALTHY in statuses:
            aggregate_status = HealthStatus.UNHEALTHY
            unhealthy_count = statuses.count(HealthStatus.UNHEALTHY)
            message = f"{unhealthy_count} check(s) unhealthy"
        elif HealthStatus.DEGRADED in statuses:
            aggregate_status = HealthStatus.DEGRADED
            degraded_count = statuses.count(HealthStatus.DEGRADED)
            message = f"{degraded_count} check(s) degraded"
        else:
            aggregate_status = HealthStatus.UNKNOWN
            message = "Unable to determine status"

        return HealthCheckResult(
            name=self.name,
            status=aggregate_status,
            message=message,
            children=children,
            details={
                "total_checks": len(children),
                "healthy": statuses.count(HealthStatus.HEALTHY),
                "degraded": statuses.count(HealthStatus.DEGRADED),
                "unhealthy": statuses.count(HealthStatus.UNHEALTHY),
                "unknown": statuses.count(HealthStatus.UNKNOWN),
            },
        )


class FunctionHealthCheck(HealthCheck):
    """Health check based on an async function."""

    def __init__(
        self,
        name: str,
        check_fn: Callable[[], Coroutine[object, object, tuple[bool, str]]],
        config: HealthCheckConfig | None = None,
    ):
        super().__init__(name, config)
        self.check_fn = check_fn

    async def check(self) -> HealthCheckResult:
        """Execute the check function."""
        try:
            healthy, message = await self.check_fn()
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                message=message,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


class Neo4jHealthCheck(HealthCheck):
    """Health check for Neo4j database connection."""

    def __init__(
        self,
        client: Neo4jClient,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("neo4j", config)
        self.client = client

    async def check(self) -> HealthCheckResult:
        """Check Neo4j connectivity."""
        try:
            # Simple query to verify connection
            async with self.client.session() as session:
                result = await session.run("RETURN 1 as n")
                record = await result.single()

                if record and record["n"] == 1:
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.HEALTHY,
                        message="Connected to Neo4j",
                        details={
                            "uri": self.client.uri[:30] + "...",
                        },
                    )

                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Unexpected response from Neo4j",
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Neo4j connection failed: {e}",
            )


class OverlayHealthCheck(HealthCheck):
    """Health check for overlay system."""

    def __init__(
        self,
        overlay_manager: OverlayManagerProtocol,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("overlays", config)
        self.overlay_manager = overlay_manager

    async def check(self) -> HealthCheckResult:
        """Check overlay system health."""
        try:
            status = await self.overlay_manager.get_system_status()

            total = status.get("total_overlays", 0)
            active = status.get("active_overlays", 0)
            errored = status.get("errored_overlays", 0)

            if errored > 0:
                health_status = HealthStatus.DEGRADED
                message = f"{errored} overlay(s) in error state"
            elif active == total:
                health_status = HealthStatus.HEALTHY
                message = f"All {total} overlays active"
            else:
                health_status = HealthStatus.DEGRADED
                message = f"{active}/{total} overlays active"

            return HealthCheckResult(
                name=self.name,
                status=health_status,
                message=message,
                details=status,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Overlay check failed: {e}",
            )


class EventSystemHealthCheck(HealthCheck):
    """Health check for event system."""

    def __init__(
        self,
        event_system: EventSystemProtocol,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("events", config)
        self.event_system = event_system

    async def check(self) -> HealthCheckResult:
        """Check event system health."""
        try:
            # Get event system metrics
            metrics = self.event_system.get_metrics()

            pending = metrics.get("pending_events", 0)
            dead_letter = metrics.get("dead_letter_count", 0)
            subscribers = metrics.get("subscriber_count", 0)

            # Determine health (using configurable thresholds)
            if dead_letter > HEALTH_DEAD_LETTER_THRESHOLD:
                health_status = HealthStatus.DEGRADED
                message = f"High dead letter count: {dead_letter} (threshold: {HEALTH_DEAD_LETTER_THRESHOLD})"
            elif pending > HEALTH_PENDING_EVENTS_THRESHOLD:
                health_status = HealthStatus.DEGRADED
                message = f"Event backlog building: {pending} (threshold: {HEALTH_PENDING_EVENTS_THRESHOLD})"
            elif subscribers == 0:
                health_status = HealthStatus.DEGRADED
                message = "No active subscribers"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"{subscribers} subscribers, {pending} pending"

            return HealthCheckResult(
                name=self.name,
                status=health_status,
                message=message,
                details=metrics,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Event system check failed: {e}",
            )


class CircuitBreakerHealthCheck(HealthCheck):
    """Health check for circuit breakers."""

    def __init__(
        self,
        registry: CircuitBreakerRegistryProtocol,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("circuit_breakers", config)
        self.registry = registry

    async def check(self) -> HealthCheckResult:
        """Check circuit breaker health."""
        try:
            summary = self.registry.get_health_summary()

            open_circuits = summary.get("open", 0)
            total = summary.get("total_circuits", 0)
            summary.get("health_score", 1.0)

            if open_circuits > 0:
                health_status = HealthStatus.DEGRADED
                open_names = summary.get("open_circuits", [])
                message = f"{open_circuits} circuit(s) open: {', '.join(open_names)}"
            elif total == 0:
                health_status = HealthStatus.HEALTHY
                message = "No circuit breakers registered"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"All {total} circuits closed"

            return HealthCheckResult(
                name=self.name,
                status=health_status,
                message=message,
                details=summary,
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Circuit breaker check failed: {e}",
            )


class MemoryHealthCheck(HealthCheck):
    """Health check for memory usage."""

    def __init__(
        self,
        warning_percent: float = 80.0,
        critical_percent: float = 95.0,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("memory", config)
        self.warning_percent = warning_percent
        self.critical_percent = critical_percent

    async def check(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            used_percent = memory.percent

            if used_percent >= self.critical_percent:
                health_status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {used_percent:.1f}%"
            elif used_percent >= self.warning_percent:
                health_status = HealthStatus.DEGRADED
                message = f"High memory usage: {used_percent:.1f}%"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"Memory usage: {used_percent:.1f}%"

            return HealthCheckResult(
                name=self.name,
                status=health_status,
                message=message,
                details={
                    "total_gb": memory.total / (1024 ** 3),
                    "available_gb": memory.available / (1024 ** 3),
                    "used_percent": used_percent,
                },
            )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="psutil not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {e}",
            )


class DiskHealthCheck(HealthCheck):
    """Health check for disk usage."""

    def __init__(
        self,
        path: str = "/",
        warning_percent: float = 85.0,
        critical_percent: float = 95.0,
        config: HealthCheckConfig | None = None,
    ):
        super().__init__("disk", config)
        self.path = path
        self.warning_percent = warning_percent
        self.critical_percent = critical_percent

    async def check(self) -> HealthCheckResult:
        """Check disk usage."""
        try:
            import psutil

            disk = psutil.disk_usage(self.path)
            used_percent = disk.percent

            if used_percent >= self.critical_percent:
                health_status = HealthStatus.UNHEALTHY
                message = f"Critical disk usage: {used_percent:.1f}%"
            elif used_percent >= self.warning_percent:
                health_status = HealthStatus.DEGRADED
                message = f"High disk usage: {used_percent:.1f}%"
            else:
                health_status = HealthStatus.HEALTHY
                message = f"Disk usage: {used_percent:.1f}%"

            return HealthCheckResult(
                name=self.name,
                status=health_status,
                message=message,
                details={
                    "path": self.path,
                    "total_gb": disk.total / (1024 ** 3),
                    "free_gb": disk.free / (1024 ** 3),
                    "used_percent": used_percent,
                },
            )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="psutil not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {e}",
            )


class ForgeHealthChecker:
    """
    Main health checker for Forge system.

    Provides hierarchical health monitoring:
    - System Health (aggregate)
      - Database Health
      - Kernel Health (events + overlays)
      - Infrastructure Health (memory, disk, circuits)
    """

    def __init__(self) -> None:
        self.root = CompositeHealthCheck("forge_system")
        self._checks: dict[str, HealthCheck] = {}
        self._background_task: asyncio.Task[None] | None = None
        self._running = False

    def add_check(
        self,
        category: str,
        check: HealthCheck,
    ) -> None:
        """Add a health check to a category."""
        # Get or create category composite
        if category not in self._checks:
            self._checks[category] = CompositeHealthCheck(category)
            self.root.add_check(self._checks[category])

        # Add check to category
        category_check = self._checks[category]
        if isinstance(category_check, CompositeHealthCheck):
            category_check.add_check(check)

    def add_simple_check(
        self,
        category: str,
        name: str,
        check_fn: Callable[[], Coroutine[object, object, tuple[bool, str]]],
    ) -> None:
        """Add a simple function-based health check."""
        self.add_check(category, FunctionHealthCheck(name, check_fn))

    async def check_health(self) -> HealthCheckResult:
        """Perform full system health check."""
        return await self.root.execute(use_cache=False)

    async def check_category(self, category: str) -> HealthCheckResult | None:
        """Check health of a specific category."""
        check = self._checks.get(category)
        if check:
            return await check.execute()
        return None

    async def get_quick_status(self) -> dict[str, object]:
        """Get quick status (uses cache)."""
        result = await self.root.execute(use_cache=True)
        return {
            "status": result.status.value,
            "message": result.message,
            "timestamp": result.timestamp.isoformat(),
        }

    async def start_background_monitoring(
        self,
        interval_seconds: float = 30.0,
        callback: Callable[[HealthCheckResult], Coroutine[object, object, None]] | None = None,
    ) -> None:
        """Start background health monitoring."""
        if self._running:
            return

        self._running = True

        async def monitor_loop() -> None:
            while self._running:
                try:
                    result = await self.check_health()

                    if result.status != HealthStatus.HEALTHY:
                        logger.warning(
                            "health_check_issue",
                            status=result.status.value,
                            message=result.message,
                        )

                    if callback:
                        await callback(result)

                except Exception as e:
                    logger.error("health_monitor_error", error=str(e))

                await asyncio.sleep(interval_seconds)

        self._background_task = asyncio.create_task(monitor_loop())
        logger.info(
            "health_monitoring_started",
            interval_seconds=interval_seconds,
        )

    async def stop_background_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._running = False

        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

        logger.info("health_monitoring_stopped")

    def get_check_names(self) -> dict[str, list[str]]:
        """Get all registered check names by category."""
        result: dict[str, list[str]] = {}

        for category, check in self._checks.items():
            if isinstance(check, CompositeHealthCheck):
                result[category] = [c.name for c in check.checks]
            else:
                result[category] = [check.name]

        return result


# Factory function for creating standard Forge health checker
def create_forge_health_checker(
    neo4j_client: Neo4jClient | None = None,
    overlay_manager: OverlayManagerProtocol | None = None,
    event_system: EventSystemProtocol | None = None,
    circuit_registry: CircuitBreakerRegistryProtocol | None = None,
) -> ForgeHealthChecker:
    """
    Create a pre-configured Forge health checker.

    Args:
        neo4j_client: Optional Neo4j client
        overlay_manager: Optional overlay manager
        event_system: Optional event system
        circuit_registry: Optional circuit breaker registry

    Returns:
        Configured ForgeHealthChecker
    """
    checker = ForgeHealthChecker()

    # Database checks
    if neo4j_client:
        checker.add_check("database", Neo4jHealthCheck(neo4j_client))

    # Kernel checks
    if overlay_manager:
        checker.add_check("kernel", OverlayHealthCheck(overlay_manager))

    if event_system:
        checker.add_check("kernel", EventSystemHealthCheck(event_system))

    # Infrastructure checks
    checker.add_check("infrastructure", MemoryHealthCheck())
    checker.add_check("infrastructure", DiskHealthCheck())

    if circuit_registry:
        checker.add_check("infrastructure", CircuitBreakerHealthCheck(circuit_registry))

    return checker


__all__ = [
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
]
