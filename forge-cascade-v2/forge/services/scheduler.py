"""
Background Scheduler Service

Handles periodic background tasks like:
- Automatic graph snapshots
- Version compaction
- Cache cleanup
- Health monitoring

Uses asyncio for lightweight scheduling without external dependencies.
Includes circuit breaker protection for database-dependent tasks.
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from forge.config import get_settings
from forge.immune.circuit_breaker import CircuitBreakerError, ForgeCircuits

logger = structlog.get_logger(__name__)

# Maximum consecutive failures before auto-disabling a task
MAX_CONSECUTIVE_FAILURES = 10


@dataclass
class ScheduledTask:
    """A scheduled background task."""

    name: str
    func: Callable[[], Coroutine[Any, Any, Any]]
    interval_seconds: float
    enabled: bool = True
    last_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    consecutive_failures: int = 0  # Track consecutive failures for auto-disable
    last_error: str | None = None
    auto_disabled: bool = False  # Track if task was auto-disabled due to failures


@dataclass
class SchedulerStats:
    """Statistics for the scheduler."""

    started_at: datetime | None = None
    tasks_registered: int = 0
    total_runs: int = 0
    total_errors: int = 0
    is_running: bool = False


class BackgroundScheduler:
    """
    Lightweight asyncio-based background scheduler.

    Runs periodic tasks without blocking the main event loop.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._stats = SchedulerStats()
        self._shutdown_event = asyncio.Event()
        self._logger = logger.bind(service="scheduler")

    def register(
        self,
        name: str,
        func: Callable[[], Coroutine[Any, Any, Any]],
        interval_seconds: float,
        enabled: bool = True,
    ) -> None:
        """
        Register a scheduled task.

        Args:
            name: Unique task name
            func: Async function to execute
            interval_seconds: Interval between executions
            enabled: Whether the task is enabled
        """
        if name in self._tasks:
            self._logger.warning("task_already_registered", name=name)
            return

        self._tasks[name] = ScheduledTask(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )
        self._stats.tasks_registered += 1
        self._logger.info(
            "task_registered",
            name=name,
            interval_seconds=interval_seconds,
            enabled=enabled,
        )

    def enable_task(self, name: str) -> bool:
        """Enable a task by name."""
        if name in self._tasks:
            self._tasks[name].enabled = True
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task by name."""
        if name in self._tasks:
            self._tasks[name].enabled = False
            return True
        return False

    async def start(self) -> None:
        """Start the scheduler and all enabled tasks."""
        if self._stats.is_running:
            self._logger.warning("scheduler_already_running")
            return

        self._stats.is_running = True
        self._stats.started_at = datetime.now(UTC)
        self._shutdown_event.clear()

        self._logger.info(
            "scheduler_starting",
            tasks=len(self._tasks),
            enabled=[n for n, t in self._tasks.items() if t.enabled],
        )

        # Start task loops for enabled tasks
        for name, task in self._tasks.items():
            if task.enabled:
                self._running_tasks[name] = asyncio.create_task(
                    self._task_loop(task),
                    name=f"scheduler_{name}",
                )

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._stats.is_running:
            return

        self._logger.info("scheduler_stopping")
        self._shutdown_event.set()

        # Cancel all running task loops
        for _name, task in self._running_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._running_tasks.clear()
        self._stats.is_running = False
        self._logger.info("scheduler_stopped")

    async def _task_loop(self, task: ScheduledTask) -> None:
        """
        Run a task in a loop with the specified interval.

        Handles errors gracefully and continues running.
        Auto-disables task after MAX_CONSECUTIVE_FAILURES to prevent error spam.
        """
        self._logger.info(
            "task_loop_starting",
            name=task.name,
            interval=task.interval_seconds,
        )

        # Initial delay to stagger task starts
        initial_delay = hash(task.name) % 10
        await asyncio.sleep(initial_delay)

        while not self._shutdown_event.is_set():
            # Check if task was auto-disabled
            if task.auto_disabled:
                self._logger.warning(
                    "task_auto_disabled_skipping",
                    name=task.name,
                    consecutive_failures=task.consecutive_failures,
                )
                break

            try:
                # Execute the task
                await task.func()
                task.last_run = datetime.now(UTC)
                task.run_count += 1
                self._stats.total_runs += 1
                task.consecutive_failures = 0  # Reset on success

                self._logger.debug(
                    "task_executed",
                    name=task.name,
                    run_count=task.run_count,
                )

            except asyncio.CancelledError:
                raise
            except CircuitBreakerError as e:
                # Circuit breaker is protecting us - log but don't count as new failure
                self._logger.warning(
                    "task_circuit_breaker_open",
                    name=task.name,
                    circuit=str(e),
                )
            except Exception as e:  # Intentional broad catch: prevents background task death
                task.error_count += 1
                task.consecutive_failures += 1
                task.last_error = str(e)
                self._stats.total_errors += 1

                self._logger.error(
                    "task_error",
                    name=task.name,
                    error=str(e),
                    error_count=task.error_count,
                    consecutive_failures=task.consecutive_failures,
                )

                # Auto-disable after too many consecutive failures
                if task.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    task.auto_disabled = True
                    task.enabled = False
                    self._logger.critical(
                        "task_auto_disabled",
                        name=task.name,
                        consecutive_failures=task.consecutive_failures,
                        last_error=task.last_error,
                        message="Task auto-disabled after repeated failures. Check service connectivity.",
                    )
                    break

            # Wait for the next interval
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=task.interval_seconds,
                )
                # If we get here, shutdown was requested
                break
            except TimeoutError:
                # Normal timeout, continue loop
                pass

    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "is_running": self._stats.is_running,
            "started_at": self._stats.started_at.isoformat() if self._stats.started_at else None,
            "tasks_registered": self._stats.tasks_registered,
            "total_runs": self._stats.total_runs,
            "total_errors": self._stats.total_errors,
            "tasks": {
                name: {
                    "enabled": task.enabled,
                    "interval_seconds": task.interval_seconds,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "run_count": task.run_count,
                    "error_count": task.error_count,
                    "consecutive_failures": task.consecutive_failures,
                    "auto_disabled": task.auto_disabled,
                    "last_error": task.last_error,
                }
                for name, task in self._tasks.items()
            },
        }

    async def run_task_now(self, name: str) -> bool:
        """Manually trigger a task to run immediately."""
        if name not in self._tasks:
            return False

        task = self._tasks[name]
        try:
            await task.func()
            task.last_run = datetime.now(UTC)
            task.run_count += 1
            self._stats.total_runs += 1
            task.consecutive_failures = 0  # Reset on success
            return True
        except Exception as e:  # Intentional broad catch: prevents background task death
            task.error_count += 1
            task.consecutive_failures += 1
            task.last_error = str(e)
            self._stats.total_errors += 1
            self._logger.error("manual_task_error", name=name, error=str(e))
            return False

    def reset_task(self, name: str) -> bool:
        """
        Reset a task's failure counters and re-enable if auto-disabled.

        Use this to recover a task after fixing connectivity issues.
        """
        if name not in self._tasks:
            return False

        task = self._tasks[name]
        task.consecutive_failures = 0
        task.auto_disabled = False
        task.enabled = True
        task.last_error = None

        self._logger.info(
            "task_reset",
            name=name,
            message="Task reset and re-enabled",
        )

        # Restart the task loop if scheduler is running
        if self._stats.is_running and name not in self._running_tasks:
            self._running_tasks[name] = asyncio.create_task(
                self._task_loop(task),
                name=f"scheduler_{name}",
            )

        return True

    def get_auto_disabled_tasks(self) -> list[str]:
        """Get list of tasks that were auto-disabled due to failures."""
        return [
            name for name, task in self._tasks.items()
            if task.auto_disabled
        ]


# Global scheduler instance
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


async def setup_scheduler() -> BackgroundScheduler:
    """
    Set up the scheduler with default tasks.

    Registers graph snapshot, version compaction, and cache cleanup tasks.
    """
    settings = get_settings()
    scheduler = get_scheduler()

    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        return scheduler

    # Register graph snapshot task
    if settings.graph_snapshot_enabled:
        scheduler.register(
            name="graph_snapshot",
            func=_create_graph_snapshot_task(),
            interval_seconds=settings.graph_snapshot_interval_minutes * 60,
            enabled=True,
        )

    # Register version compaction task
    if settings.version_compaction_enabled:
        scheduler.register(
            name="version_compaction",
            func=_create_version_compaction_task(),
            interval_seconds=settings.version_compaction_interval_hours * 3600,
            enabled=True,
        )

    # Register cache cleanup task
    scheduler.register(
        name="query_cache_cleanup",
        func=_create_cache_cleanup_task(),
        interval_seconds=settings.query_cache_cleanup_interval_minutes * 60,
        enabled=True,
    )

    return scheduler


def _create_graph_snapshot_task() -> Callable[[], Coroutine[Any, Any, None]]:
    """Create the graph snapshot task function with circuit breaker protection."""

    async def task() -> None:
        """Create a periodic graph snapshot."""
        from forge.database.client import Neo4jClient
        from forge.repositories.graph_repository import GraphRepository
        from forge.repositories.temporal_repository import TemporalRepository

        logger.info("scheduled_graph_snapshot_starting")

        # Get circuit breaker for Neo4j operations
        neo4j_circuit = await ForgeCircuits.neo4j()

        # Inner function for circuit breaker to wrap
        async def do_snapshot() -> Any:
            client = None
            try:
                client = Neo4jClient()
                await client.connect()
                graph_repo = GraphRepository(client)
                temporal_repo = TemporalRepository(client)

                # Get current metrics
                metrics = await graph_repo.get_graph_metrics()

                # Create snapshot
                snapshot = await temporal_repo.create_graph_snapshot(
                    metrics={
                        "total_nodes": metrics.total_nodes,
                        "total_edges": metrics.total_edges,
                        "density": metrics.density,
                        "avg_degree": getattr(metrics, 'avg_degree', 0.0),
                        "connected_components": metrics.connected_components,
                        "nodes_by_type": metrics.nodes_by_type,
                        "edges_by_type": metrics.edges_by_type,
                    },
                    created_by="scheduler",
                )

                logger.info(
                    "scheduled_graph_snapshot_complete",
                    snapshot_id=snapshot.id,
                    total_nodes=metrics.total_nodes,
                )
                return snapshot

            finally:
                if client:
                    await client.close()

        # Execute through circuit breaker
        await neo4j_circuit.call(do_snapshot)

    return task


def _create_version_compaction_task() -> Callable[[], Coroutine[Any, Any, None]]:
    """Create the version compaction task function with circuit breaker protection."""

    async def task() -> None:
        """Compact old version diffs into full snapshots."""
        from forge.database.client import Neo4jClient
        from forge.repositories.temporal_repository import TemporalRepository

        logger.info("scheduled_version_compaction_starting")

        # Get circuit breaker for Neo4j operations
        neo4j_circuit = await ForgeCircuits.neo4j()

        async def do_compaction() -> int:
            client = None
            try:
                client = Neo4jClient()
                await client.connect()
                temporal_repo = TemporalRepository(client)

                # Get capsules with old versions to compact
                query = """
                MATCH (c:Capsule)-[:HAS_VERSION]->(v:CapsuleVersion)
                WHERE v.snapshot_type = 'diff'
                  AND v.created_at < datetime() - duration('P30D')
                RETURN DISTINCT c.id AS capsule_id
                LIMIT 100
                """
                results = await client.execute(query, {})

                total_compacted = 0
                for r in results:
                    capsule_id = r.get("capsule_id")
                    if capsule_id:
                        compacted = await temporal_repo.compact_old_versions(capsule_id)
                        total_compacted += compacted

                logger.info(
                    "scheduled_version_compaction_complete",
                    capsules_processed=len(results),
                    versions_compacted=total_compacted,
                )
                return total_compacted

            finally:
                if client:
                    await client.close()

        # Execute through circuit breaker
        await neo4j_circuit.call(do_compaction)

    return task


def _create_cache_cleanup_task() -> Callable[[], Coroutine[Any, Any, None]]:
    """Create the cache cleanup task function."""

    async def task() -> None:
        """Clean up expired query cache entries."""
        from forge.services.query_cache import get_query_cache

        logger.debug("scheduled_cache_cleanup_starting")

        cache = get_query_cache()
        if cache:
            stats = await cache.cleanup_expired()
            logger.debug(
                "scheduled_cache_cleanup_complete",
                entries_removed=stats.get("removed", 0),
            )

    return task
