"""
Background Scheduler Service

Handles periodic background tasks like:
- Automatic graph snapshots
- Version compaction
- Cache cleanup
- Health monitoring

Uses asyncio for lightweight scheduling without external dependencies.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

import structlog

from forge.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class ScheduledTask:
    """A scheduled background task."""

    name: str
    func: Callable[[], Coroutine[Any, Any, Any]]
    interval_seconds: float
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class SchedulerStats:
    """Statistics for the scheduler."""

    started_at: Optional[datetime] = None
    tasks_registered: int = 0
    total_runs: int = 0
    total_errors: int = 0
    is_running: bool = False


class BackgroundScheduler:
    """
    Lightweight asyncio-based background scheduler.

    Runs periodic tasks without blocking the main event loop.
    """

    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
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
        self._stats.started_at = datetime.now(timezone.utc)
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
        for name, task in self._running_tasks.items():
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
            try:
                # Execute the task
                await task.func()
                task.last_run = datetime.now(timezone.utc)
                task.run_count += 1
                self._stats.total_runs += 1

                self._logger.debug(
                    "task_executed",
                    name=task.name,
                    run_count=task.run_count,
                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                task.error_count += 1
                task.last_error = str(e)
                self._stats.total_errors += 1

                self._logger.error(
                    "task_error",
                    name=task.name,
                    error=str(e),
                    error_count=task.error_count,
                )

            # Wait for the next interval
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=task.interval_seconds,
                )
                # If we get here, shutdown was requested
                break
            except asyncio.TimeoutError:
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
            task.last_run = datetime.now(timezone.utc)
            task.run_count += 1
            self._stats.total_runs += 1
            return True
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            self._stats.total_errors += 1
            self._logger.error("manual_task_error", name=name, error=str(e))
            return False


# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


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


def _create_graph_snapshot_task() -> Callable[[], Coroutine[Any, Any, Any]]:
    """Create the graph snapshot task function."""

    async def task():
        """Create a periodic graph snapshot."""
        from forge.database.client import Neo4jClient
        from forge.repositories.graph_repository import GraphRepository
        from forge.repositories.temporal_repository import TemporalRepository

        logger.info("scheduled_graph_snapshot_starting")

        client = Neo4jClient()
        await client.connect()

        try:
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
                    "nodes_by_type": metrics.node_distribution,
                    "edges_by_type": metrics.edge_distribution,
                },
                created_by="scheduler",
            )

            logger.info(
                "scheduled_graph_snapshot_complete",
                snapshot_id=snapshot.id,
                total_nodes=metrics.total_nodes,
            )

        finally:
            await client.close()

    return task


def _create_version_compaction_task() -> Callable[[], Coroutine[Any, Any, Any]]:
    """Create the version compaction task function."""

    async def task():
        """Compact old version diffs into full snapshots."""
        from forge.database.client import Neo4jClient
        from forge.repositories.temporal_repository import TemporalRepository

        logger.info("scheduled_version_compaction_starting")

        client = Neo4jClient()
        await client.connect()

        try:
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

        finally:
            await client.close()

    return task


def _create_cache_cleanup_task() -> Callable[[], Coroutine[Any, Any, Any]]:
    """Create the cache cleanup task function."""

    async def task():
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
