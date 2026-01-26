"""
Forge Cascade V2 - Canary Deployment Manager
Gradual rollout system for safe overlay and configuration updates.

Canary deployments allow Forge to:
1. Test new overlays with a subset of traffic
2. Monitor for anomalies during rollout
3. Automatically rollback on failures
4. Gradually increase exposure

This is critical for Forge's self-healing philosophy.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CanaryState(str, Enum):
    """Canary deployment states."""
    PENDING = "pending"           # Not yet started
    RUNNING = "running"           # Active rollout in progress
    PAUSED = "paused"            # Manually paused
    SUCCEEDED = "succeeded"       # Fully rolled out
    FAILED = "failed"            # Rolled back due to failure
    ROLLING_BACK = "rolling_back" # Rollback in progress


class RolloutStrategy(str, Enum):
    """How to advance traffic percentage."""
    LINEAR = "linear"       # Fixed increments (e.g., 10% -> 20% -> 30%)
    EXPONENTIAL = "exponential"  # Doubling (e.g., 1% -> 2% -> 4% -> 8%)
    MANUAL = "manual"       # Human-triggered advances


@dataclass
class CanaryConfig:
    """Configuration for canary deployment."""

    # Traffic control
    initial_percentage: float = 5.0       # Start with 5% traffic
    increment_percentage: float = 10.0    # Increase by 10% each step
    max_percentage: float = 100.0         # Full rollout target

    # Timing
    step_duration_seconds: float = 300.0  # 5 min per step
    min_samples_per_step: int = 100       # Min requests before advancing

    # Strategy
    strategy: RolloutStrategy = RolloutStrategy.LINEAR

    # Thresholds for automatic rollback
    error_rate_threshold: float = 0.05    # 5% errors triggers rollback
    latency_p99_threshold_ms: float = 2000.0  # 2s p99 triggers rollback
    anomaly_score_threshold: float = 0.8  # Anomaly detection threshold

    # Rollback
    auto_rollback: bool = True
    rollback_on_error: bool = True

    # Approval
    require_approval_at_percent: float | None = 50.0  # Pause for approval at 50%


@dataclass
class CanaryMetrics:
    """Metrics tracked during canary deployment."""

    # Request counts
    total_requests: int = 0
    canary_requests: int = 0
    control_requests: int = 0

    # Error tracking
    canary_errors: int = 0
    control_errors: int = 0

    # Latency (ms)
    canary_latencies: list[float] = field(default_factory=list)
    control_latencies: list[float] = field(default_factory=list)

    # Per-step tracking
    step_metrics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def canary_error_rate(self) -> float:
        """Calculate canary error rate."""
        if self.canary_requests == 0:
            return 0.0
        return self.canary_errors / self.canary_requests

    @property
    def control_error_rate(self) -> float:
        """Calculate control error rate."""
        if self.control_requests == 0:
            return 0.0
        return self.control_errors / self.control_requests

    @property
    def error_rate_delta(self) -> float:
        """Difference in error rates (canary - control)."""
        return self.canary_error_rate - self.control_error_rate

    def percentile(self, latencies: list[float], p: float) -> float:
        """Calculate latency percentile."""
        if not latencies:
            return 0.0
        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * p / 100)
        idx = min(idx, len(sorted_latencies) - 1)
        return sorted_latencies[idx]

    @property
    def canary_p99(self) -> float:
        """P99 latency for canary."""
        return self.percentile(self.canary_latencies, 99)

    @property
    def control_p99(self) -> float:
        """P99 latency for control."""
        return self.percentile(self.control_latencies, 99)

    def record_step(self, step_number: int, percentage: float) -> None:
        """Record metrics for completed step."""
        self.step_metrics.append({
            "step": step_number,
            "percentage": percentage,
            "canary_requests": self.canary_requests,
            "canary_errors": self.canary_errors,
            "canary_error_rate": self.canary_error_rate,
            "canary_p99": self.canary_p99,
            "control_error_rate": self.control_error_rate,
            "control_p99": self.control_p99,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def reset_window(self) -> None:
        """Reset metrics for new step window."""
        self.canary_requests = 0
        self.control_requests = 0
        self.canary_errors = 0
        self.control_errors = 0
        self.canary_latencies.clear()
        self.control_latencies.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "canary_requests": self.canary_requests,
            "control_requests": self.control_requests,
            "canary_error_rate": self.canary_error_rate,
            "control_error_rate": self.control_error_rate,
            "error_rate_delta": self.error_rate_delta,
            "canary_p99_ms": self.canary_p99,
            "control_p99_ms": self.control_p99,
            "step_metrics": self.step_metrics,
        }


@dataclass
class CanaryDeployment(Generic[T]):
    """
    A canary deployment instance.

    Tracks the state and progress of rolling out
    a new version (canary) alongside the stable version (control).
    """

    id: str
    name: str
    canary_version: T
    control_version: T
    config: CanaryConfig

    # State tracking
    state: CanaryState = CanaryState.PENDING
    current_percentage: float = 0.0
    current_step: int = 0

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    step_started_at: float | None = None

    # Metrics
    metrics: CanaryMetrics = field(default_factory=CanaryMetrics)

    # Failure info
    failure_reason: str | None = None
    rollback_reason: str | None = None

    # Approval
    awaiting_approval: bool = False
    approved_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "current_percentage": self.current_percentage,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metrics": self.metrics.to_dict(),
            "failure_reason": self.failure_reason,
            "awaiting_approval": self.awaiting_approval,
            "config": {
                "initial_percentage": self.config.initial_percentage,
                "increment_percentage": self.config.increment_percentage,
                "max_percentage": self.config.max_percentage,
                "strategy": self.config.strategy.value,
                "error_rate_threshold": self.config.error_rate_threshold,
            },
        }


class CanaryManager(Generic[T]):
    """
    Manager for canary deployments.

    Handles:
    - Creating and tracking deployments
    - Traffic routing decisions
    - Automatic advancement/rollback
    - Metrics collection

    Usage:
        manager = CanaryManager[OverlayConfig]()

        # Create deployment
        deployment = await manager.create_deployment(
            name="new_ml_overlay",
            canary_version=new_config,
            control_version=old_config,
        )

        # Start rollout
        await manager.start(deployment.id)

        # For each request, get routing
        version = await manager.route(deployment.id)

        # Record outcome
        await manager.record_outcome(deployment.id, is_canary=True, success=True, latency_ms=50)
    """

    def __init__(
        self,
        default_config: CanaryConfig | None = None,
        on_state_change: Callable[[CanaryDeployment[T], CanaryState, CanaryState], Coroutine[Any, Any, None]] | None = None,
    ):
        self.default_config = default_config or CanaryConfig()
        self.on_state_change = on_state_change

        self._deployments: dict[str, CanaryDeployment[T]] = {}
        self._lock = asyncio.Lock()
        self._background_tasks: dict[str, asyncio.Task[None]] = {}
        self._request_counter = 0

    async def create_deployment(
        self,
        name: str,
        canary_version: T,
        control_version: T,
        config: CanaryConfig | None = None,
        deployment_id: str | None = None,
    ) -> CanaryDeployment[T]:
        """Create a new canary deployment."""
        import uuid

        deployment = CanaryDeployment(
            id=deployment_id or str(uuid.uuid4()),
            name=name,
            canary_version=canary_version,
            control_version=control_version,
            config=config or self.default_config,
        )

        async with self._lock:
            self._deployments[deployment.id] = deployment

        logger.info(
            "canary_deployment_created",
            deployment_id=deployment.id,
            name=name,
        )

        return deployment

    async def get_deployment(self, deployment_id: str) -> CanaryDeployment[T] | None:
        """Get deployment by ID."""
        return self._deployments.get(deployment_id)

    async def list_deployments(
        self,
        state: CanaryState | None = None,
    ) -> list[CanaryDeployment[T]]:
        """List all deployments, optionally filtered by state."""
        deployments = list(self._deployments.values())

        if state:
            deployments = [d for d in deployments if d.state == state]

        return deployments

    async def _set_state(
        self,
        deployment: CanaryDeployment[T],
        new_state: CanaryState,
    ) -> None:
        """Update deployment state with notification."""
        old_state = deployment.state
        deployment.state = new_state

        logger.info(
            "canary_state_change",
            deployment_id=deployment.id,
            old_state=old_state.value,
            new_state=new_state.value,
            percentage=deployment.current_percentage,
        )

        if self.on_state_change:
            try:
                await self.on_state_change(deployment, old_state, new_state)
            except (RuntimeError, ValueError, TypeError, OSError) as e:
                logger.error(
                    "canary_state_change_callback_error",
                    error=str(e),
                )

    async def start(self, deployment_id: str) -> bool:
        """Start a canary deployment."""
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return False

        if deployment.state != CanaryState.PENDING:
            logger.warning(
                "canary_already_started",
                deployment_id=deployment_id,
                state=deployment.state.value,
            )
            return False

        # Initialize
        deployment.started_at = datetime.now(UTC)
        deployment.current_percentage = deployment.config.initial_percentage
        deployment.current_step = 1
        deployment.step_started_at = time.monotonic()

        await self._set_state(deployment, CanaryState.RUNNING)

        # Start background monitoring
        self._background_tasks[deployment_id] = asyncio.create_task(
            self._monitor_deployment(deployment)
        )

        return True

    async def pause(self, deployment_id: str) -> bool:
        """Pause a running deployment."""
        deployment = self._deployments.get(deployment_id)
        if not deployment or deployment.state != CanaryState.RUNNING:
            return False

        await self._set_state(deployment, CanaryState.PAUSED)
        return True

    async def resume(self, deployment_id: str) -> bool:
        """Resume a paused deployment."""
        deployment = self._deployments.get(deployment_id)
        if not deployment or deployment.state != CanaryState.PAUSED:
            return False

        deployment.step_started_at = time.monotonic()
        await self._set_state(deployment, CanaryState.RUNNING)
        return True

    async def approve(self, deployment_id: str, approved_by: str) -> bool:
        """Approve a deployment awaiting approval."""
        deployment = self._deployments.get(deployment_id)
        if not deployment or not deployment.awaiting_approval:
            return False

        deployment.awaiting_approval = False
        deployment.approved_by = approved_by

        logger.info(
            "canary_approved",
            deployment_id=deployment_id,
            approved_by=approved_by,
            percentage=deployment.current_percentage,
        )

        # Resume if paused for approval
        if deployment.state == CanaryState.PAUSED:
            await self.resume(deployment_id)

        return True

    async def rollback(
        self,
        deployment_id: str,
        reason: str = "Manual rollback",
    ) -> bool:
        """Manually trigger rollback."""
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return False

        if deployment.state in (CanaryState.SUCCEEDED, CanaryState.FAILED):
            return False

        await self._perform_rollback(deployment, reason)
        return True

    async def _perform_rollback(
        self,
        deployment: CanaryDeployment[T],
        reason: str,
    ) -> None:
        """Execute rollback."""
        deployment.rollback_reason = reason
        await self._set_state(deployment, CanaryState.ROLLING_BACK)

        # Record final metrics
        deployment.metrics.record_step(
            deployment.current_step,
            deployment.current_percentage,
        )

        # Reset to control
        deployment.current_percentage = 0.0
        deployment.completed_at = datetime.now(UTC)

        await self._set_state(deployment, CanaryState.FAILED)

        logger.warning(
            "canary_rolled_back",
            deployment_id=deployment.id,
            reason=reason,
            step=deployment.current_step,
        )

    async def _complete_deployment(
        self,
        deployment: CanaryDeployment[T],
    ) -> None:
        """Complete successful deployment."""
        deployment.current_percentage = 100.0
        deployment.completed_at = datetime.now(UTC)

        # Final metrics
        deployment.metrics.record_step(
            deployment.current_step,
            deployment.current_percentage,
        )

        await self._set_state(deployment, CanaryState.SUCCEEDED)

        logger.info(
            "canary_succeeded",
            deployment_id=deployment.id,
            total_steps=deployment.current_step,
            total_requests=deployment.metrics.total_requests,
        )

    async def _advance_step(
        self,
        deployment: CanaryDeployment[T],
    ) -> None:
        """Advance to next rollout step."""
        # Record current step metrics
        deployment.metrics.record_step(
            deployment.current_step,
            deployment.current_percentage,
        )

        # Calculate next percentage
        config = deployment.config

        if config.strategy == RolloutStrategy.LINEAR:
            next_percentage = deployment.current_percentage + config.increment_percentage
        elif config.strategy == RolloutStrategy.EXPONENTIAL:
            next_percentage = deployment.current_percentage * 2
        else:  # MANUAL
            return  # Wait for manual advance

        next_percentage = min(next_percentage, config.max_percentage)

        # Check for completion
        if next_percentage >= config.max_percentage:
            await self._complete_deployment(deployment)
            return

        # Check for approval requirement
        if (
            config.require_approval_at_percent and
            deployment.current_percentage < config.require_approval_at_percent <= next_percentage and
            not deployment.approved_by
        ):
            deployment.awaiting_approval = True
            await self.pause(deployment.id)
            logger.info(
                "canary_awaiting_approval",
                deployment_id=deployment.id,
                percentage=next_percentage,
            )
            return

        # Advance
        deployment.current_step += 1
        deployment.current_percentage = next_percentage
        deployment.step_started_at = time.monotonic()
        deployment.metrics.reset_window()

        logger.info(
            "canary_step_advanced",
            deployment_id=deployment.id,
            step=deployment.current_step,
            percentage=next_percentage,
        )

    async def _check_health(
        self,
        deployment: CanaryDeployment[T],
    ) -> tuple[bool, str | None]:
        """Check if canary is healthy."""
        config = deployment.config
        metrics = deployment.metrics

        # Need minimum samples
        if metrics.canary_requests < config.min_samples_per_step:
            return True, None

        # Check error rate
        if metrics.canary_error_rate > config.error_rate_threshold:
            return False, f"Error rate {metrics.canary_error_rate:.2%} exceeds threshold {config.error_rate_threshold:.2%}"

        # Check latency
        if metrics.canary_p99 > config.latency_p99_threshold_ms:
            return False, f"P99 latency {metrics.canary_p99:.0f}ms exceeds threshold {config.latency_p99_threshold_ms:.0f}ms"

        # Compare to control (if we have control samples)
        if metrics.control_requests >= 10:
            # Error rate shouldn't be 2x worse than control
            if (
                metrics.control_error_rate > 0 and
                metrics.canary_error_rate > metrics.control_error_rate * 2
            ):
                return False, f"Error rate {metrics.canary_error_rate:.2%} is 2x+ worse than control {metrics.control_error_rate:.2%}"

        return True, None

    async def _monitor_deployment(
        self,
        deployment: CanaryDeployment[T],
    ) -> None:
        """Background monitoring loop for deployment."""
        check_interval = 5.0  # Check every 5 seconds

        while deployment.state == CanaryState.RUNNING:
            try:
                # Check health
                healthy, reason = await self._check_health(deployment)

                if not healthy and deployment.config.auto_rollback:
                    await self._perform_rollback(deployment, reason or "Health check failed")
                    break

                # Check if time to advance
                if deployment.step_started_at:
                    elapsed = time.monotonic() - deployment.step_started_at
                    has_min_samples = deployment.metrics.canary_requests >= deployment.config.min_samples_per_step

                    if elapsed >= deployment.config.step_duration_seconds and has_min_samples:
                        await self._advance_step(deployment)

            except Exception as e:  # Intentional broad catch: background monitor loop must not crash
                logger.error(
                    "canary_monitor_error",
                    deployment_id=deployment.id,
                    error=str(e),
                )

            await asyncio.sleep(check_interval)

    def route(self, deployment_id: str) -> T | None:
        """
        Get version to use for a request.

        Uses weighted random routing based on current percentage.

        Returns:
            canary_version or control_version, or None if deployment not found
        """
        import random

        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return None

        if deployment.state != CanaryState.RUNNING:
            # Return control when not actively running
            return deployment.control_version

        # Note: Counter increments are not locked for performance reasons.
        # In high-concurrency scenarios, counts may have slight inaccuracies
        # but routing decisions remain correct. Use record_outcome() for
        # accurate metrics tracking.
        self._request_counter += 1
        deployment.metrics.total_requests += 1

        # Route based on percentage
        if random.random() * 100 < deployment.current_percentage:
            return deployment.canary_version
        else:
            return deployment.control_version

    def should_use_canary(self, deployment_id: str) -> bool:
        """Simple boolean check for canary routing."""
        import random

        deployment = self._deployments.get(deployment_id)
        if not deployment or deployment.state != CanaryState.RUNNING:
            return False

        return random.random() * 100 < deployment.current_percentage

    async def record_outcome(
        self,
        deployment_id: str,
        is_canary: bool,
        success: bool,
        latency_ms: float,
    ) -> None:
        """
        Record request outcome for metrics.

        Uses lock to ensure thread-safe counter updates in async context.
        """
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return

        async with self._lock:
            metrics = deployment.metrics

            if is_canary:
                metrics.canary_requests += 1
                if not success:
                    metrics.canary_errors += 1
                metrics.canary_latencies.append(latency_ms)

                # Keep latency list bounded
                if len(metrics.canary_latencies) > 10000:
                    metrics.canary_latencies = metrics.canary_latencies[-5000:]
            else:
                metrics.control_requests += 1
                if not success:
                    metrics.control_errors += 1
                metrics.control_latencies.append(latency_ms)

                if len(metrics.control_latencies) > 10000:
                    metrics.control_latencies = metrics.control_latencies[-5000:]

    async def manual_advance(self, deployment_id: str) -> bool:
        """Manually advance to next step (for MANUAL strategy)."""
        deployment = self._deployments.get(deployment_id)
        if not deployment or deployment.state != CanaryState.RUNNING:
            return False

        await self._advance_step(deployment)
        return True

    async def cleanup(self, deployment_id: str) -> bool:
        """Remove completed deployment."""
        deployment = self._deployments.get(deployment_id)
        if not deployment:
            return False

        if deployment.state not in (CanaryState.SUCCEEDED, CanaryState.FAILED):
            return False

        # Cancel any background task
        if deployment_id in self._background_tasks:
            self._background_tasks[deployment_id].cancel()
            del self._background_tasks[deployment_id]

        del self._deployments[deployment_id]
        return True

    def get_active_deployments(self) -> list[str]:
        """Get IDs of active deployments."""
        return [
            d.id for d in self._deployments.values()
            if d.state in (CanaryState.RUNNING, CanaryState.PAUSED)
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all deployments."""
        by_state: dict[str, int] = {}
        for d in self._deployments.values():
            by_state[d.state.value] = by_state.get(d.state.value, 0) + 1

        return {
            "total_deployments": len(self._deployments),
            "by_state": by_state,
            "active_ids": self.get_active_deployments(),
        }


# Convenience functions for overlay canaries
class OverlayCanaryManager(CanaryManager[dict[str, Any]]):
    """Specialized canary manager for overlay configurations."""

    def __init__(self) -> None:
        super().__init__(
            default_config=CanaryConfig(
                initial_percentage=5.0,
                increment_percentage=15.0,
                step_duration_seconds=180.0,  # 3 min per step for overlays
                min_samples_per_step=50,
                error_rate_threshold=0.03,  # 3% for overlays
            )
        )


__all__ = [
    "CanaryState",
    "RolloutStrategy",
    "CanaryConfig",
    "CanaryMetrics",
    "CanaryDeployment",
    "CanaryManager",
    "OverlayCanaryManager",
]
