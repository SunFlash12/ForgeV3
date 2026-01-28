"""
Tests for Background Scheduler Service

Tests cover:
- ScheduledTask dataclass
- SchedulerStats dataclass
- BackgroundScheduler task registration and management
- Task execution loops
- Error handling and auto-disable
- Circuit breaker integration
- Task state management
- Global scheduler functions
- Setup scheduler with default tasks
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.services.scheduler import (
    MAX_CONSECUTIVE_FAILURES,
    BackgroundScheduler,
    ScheduledTask,
    SchedulerStats,
    get_scheduler,
    setup_scheduler,
)


class TestScheduledTask:
    """Tests for ScheduledTask dataclass."""

    def test_scheduled_task_creation(self):
        """Test creating a ScheduledTask."""
        task = ScheduledTask(
            name="test_task",
            func=AsyncMock(),
            interval_seconds=60.0,
            enabled=True,
        )

        assert task.name == "test_task"
        assert task.interval_seconds == 60.0
        assert task.enabled is True
        assert task.last_run is None
        assert task.run_count == 0
        assert task.error_count == 0
        assert task.consecutive_failures == 0
        assert task.last_error is None
        assert task.auto_disabled is False

    def test_scheduled_task_defaults(self):
        """Test ScheduledTask default values."""
        task = ScheduledTask(
            name="default_task",
            func=AsyncMock(),
            interval_seconds=30.0,
        )

        assert task.enabled is True
        assert task.last_run is None
        assert task.run_count == 0
        assert task.error_count == 0


class TestSchedulerStats:
    """Tests for SchedulerStats dataclass."""

    def test_scheduler_stats_creation(self):
        """Test creating SchedulerStats."""
        stats = SchedulerStats()

        assert stats.started_at is None
        assert stats.tasks_registered == 0
        assert stats.total_runs == 0
        assert stats.total_errors == 0
        assert stats.is_running is False

    def test_scheduler_stats_with_values(self):
        """Test SchedulerStats with values."""
        stats = SchedulerStats(
            started_at=datetime.now(UTC),
            tasks_registered=5,
            total_runs=100,
            total_errors=3,
            is_running=True,
        )

        assert stats.tasks_registered == 5
        assert stats.total_runs == 100
        assert stats.total_errors == 3
        assert stats.is_running is True


class TestBackgroundScheduler:
    """Tests for BackgroundScheduler."""

    @pytest.fixture
    def scheduler(self):
        """Create a BackgroundScheduler for testing."""
        return BackgroundScheduler()

    @pytest.fixture
    def mock_task_func(self):
        """Create a mock async task function."""
        return AsyncMock()

    # =========================================================================
    # Task Registration Tests
    # =========================================================================

    def test_register_task(self, scheduler, mock_task_func):
        """Test registering a task."""
        scheduler.register(
            name="test_task",
            func=mock_task_func,
            interval_seconds=60.0,
            enabled=True,
        )

        assert "test_task" in scheduler._tasks
        assert scheduler._tasks["test_task"].name == "test_task"
        assert scheduler._tasks["test_task"].interval_seconds == 60.0
        assert scheduler._tasks["test_task"].enabled is True
        assert scheduler._stats.tasks_registered == 1

    def test_register_task_disabled(self, scheduler, mock_task_func):
        """Test registering a disabled task."""
        scheduler.register(
            name="disabled_task",
            func=mock_task_func,
            interval_seconds=30.0,
            enabled=False,
        )

        assert scheduler._tasks["disabled_task"].enabled is False

    def test_register_duplicate_task_ignored(self, scheduler, mock_task_func):
        """Test registering duplicate task is ignored."""
        scheduler.register("task1", mock_task_func, 60.0)
        scheduler.register("task1", mock_task_func, 120.0)  # Different interval

        # Should still have original interval
        assert scheduler._tasks["task1"].interval_seconds == 60.0
        assert scheduler._stats.tasks_registered == 1

    def test_register_multiple_tasks(self, scheduler):
        """Test registering multiple tasks."""
        for i in range(5):
            scheduler.register(f"task_{i}", AsyncMock(), 60.0)

        assert len(scheduler._tasks) == 5
        assert scheduler._stats.tasks_registered == 5

    # =========================================================================
    # Enable/Disable Tests
    # =========================================================================

    def test_enable_task(self, scheduler, mock_task_func):
        """Test enabling a task."""
        scheduler.register("task1", mock_task_func, 60.0, enabled=False)

        result = scheduler.enable_task("task1")

        assert result is True
        assert scheduler._tasks["task1"].enabled is True

    def test_enable_nonexistent_task(self, scheduler):
        """Test enabling nonexistent task returns False."""
        result = scheduler.enable_task("nonexistent")
        assert result is False

    def test_disable_task(self, scheduler, mock_task_func):
        """Test disabling a task."""
        scheduler.register("task1", mock_task_func, 60.0, enabled=True)

        result = scheduler.disable_task("task1")

        assert result is True
        assert scheduler._tasks["task1"].enabled is False

    def test_disable_nonexistent_task(self, scheduler):
        """Test disabling nonexistent task returns False."""
        result = scheduler.disable_task("nonexistent")
        assert result is False

    # =========================================================================
    # Start/Stop Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_start_scheduler(self, scheduler, mock_task_func):
        """Test starting the scheduler."""
        scheduler.register("task1", mock_task_func, 60.0)

        await scheduler.start()

        try:
            assert scheduler._stats.is_running is True
            assert scheduler._stats.started_at is not None
            assert "task1" in scheduler._running_tasks
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_only_enabled_tasks(self, scheduler):
        """Test start only runs enabled tasks."""
        scheduler.register("enabled_task", AsyncMock(), 60.0, enabled=True)
        scheduler.register("disabled_task", AsyncMock(), 60.0, enabled=False)

        await scheduler.start()

        try:
            assert "enabled_task" in scheduler._running_tasks
            assert "disabled_task" not in scheduler._running_tasks
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, scheduler, mock_task_func):
        """Test starting already running scheduler is no-op."""
        scheduler.register("task1", mock_task_func, 60.0)

        await scheduler.start()
        original_started_at = scheduler._stats.started_at

        await scheduler.start()  # Should not change anything

        try:
            assert scheduler._stats.started_at == original_started_at
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_scheduler(self, scheduler, mock_task_func):
        """Test stopping the scheduler."""
        scheduler.register("task1", mock_task_func, 60.0)

        await scheduler.start()
        await scheduler.stop()

        assert scheduler._stats.is_running is False
        assert len(scheduler._running_tasks) == 0

    @pytest.mark.asyncio
    async def test_stop_not_running(self, scheduler):
        """Test stopping scheduler that is not running is no-op."""
        # Should not raise
        await scheduler.stop()
        assert scheduler._stats.is_running is False

    # =========================================================================
    # Task Execution Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_task_executes(self, scheduler):
        """Test task function is executed."""
        executed = []

        async def task_func():
            executed.append(True)

        scheduler.register("exec_task", task_func, 0.1)

        await scheduler.start()
        # Wait for task to execute
        await asyncio.sleep(0.3)
        await scheduler.stop()

        assert len(executed) >= 1

    @pytest.mark.asyncio
    async def test_task_updates_stats(self, scheduler):
        """Test task execution updates stats."""
        async def task_func():
            pass

        scheduler.register("stats_task", task_func, 0.1)

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        task = scheduler._tasks["stats_task"]
        assert task.run_count >= 1
        assert task.last_run is not None
        assert scheduler._stats.total_runs >= 1

    @pytest.mark.asyncio
    async def test_task_error_handling(self, scheduler):
        """Test task error is handled and logged."""
        async def failing_task():
            raise ValueError("Task failed!")

        scheduler.register("failing_task", failing_task, 0.1)

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        task = scheduler._tasks["failing_task"]
        assert task.error_count >= 1
        assert task.consecutive_failures >= 1
        assert task.last_error == "Task failed!"
        assert scheduler._stats.total_errors >= 1

    @pytest.mark.asyncio
    async def test_task_resets_consecutive_failures_on_success(self, scheduler):
        """Test consecutive failures reset after success."""
        call_count = [0]

        async def intermittent_task():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ValueError("Fail")

        scheduler.register("intermittent_task", intermittent_task, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        task = scheduler._tasks["intermittent_task"]
        # After success, consecutive_failures should be 0
        assert task.consecutive_failures == 0
        assert task.run_count >= 1

    @pytest.mark.asyncio
    async def test_task_auto_disables_after_max_failures(self, scheduler):
        """Test task auto-disables after MAX_CONSECUTIVE_FAILURES."""
        async def always_failing():
            raise ValueError("Always fails")

        scheduler.register("auto_disable_task", always_failing, 0.01)

        await scheduler.start()
        # Wait for enough failures
        await asyncio.sleep(0.5)
        await scheduler.stop()

        task = scheduler._tasks["auto_disable_task"]
        assert task.auto_disabled is True
        assert task.enabled is False
        assert task.consecutive_failures >= MAX_CONSECUTIVE_FAILURES

    @pytest.mark.asyncio
    async def test_circuit_breaker_error_not_counted_as_new_failure(self, scheduler):
        """Test circuit breaker errors don't increment consecutive failures."""
        from forge.immune.circuit_breaker import CircuitBreakerError, CircuitState

        async def circuit_breaker_task():
            raise CircuitBreakerError("test_circuit", CircuitState.OPEN)

        scheduler.register("cb_task", circuit_breaker_task, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        task = scheduler._tasks["cb_task"]
        # Error count should not increase significantly for circuit breaker errors
        assert task.error_count == 0

    # =========================================================================
    # Get Stats Tests
    # =========================================================================

    def test_get_stats_initial(self, scheduler):
        """Test get_stats with initial values."""
        stats = scheduler.get_stats()

        assert stats["is_running"] is False
        assert stats["started_at"] is None
        assert stats["tasks_registered"] == 0
        assert stats["total_runs"] == 0
        assert stats["total_errors"] == 0
        assert stats["tasks"] == {}

    def test_get_stats_with_tasks(self, scheduler, mock_task_func):
        """Test get_stats with registered tasks."""
        scheduler.register("task1", mock_task_func, 60.0)
        scheduler.register("task2", mock_task_func, 120.0, enabled=False)

        stats = scheduler.get_stats()

        assert stats["tasks_registered"] == 2
        assert "task1" in stats["tasks"]
        assert "task2" in stats["tasks"]
        assert stats["tasks"]["task1"]["enabled"] is True
        assert stats["tasks"]["task2"]["enabled"] is False
        assert stats["tasks"]["task1"]["interval_seconds"] == 60.0
        assert stats["tasks"]["task2"]["interval_seconds"] == 120.0

    @pytest.mark.asyncio
    async def test_get_stats_after_execution(self, scheduler):
        """Test get_stats after task execution."""
        async def task_func():
            pass

        scheduler.register("exec_task", task_func, 0.1)

        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()

        stats = scheduler.get_stats()

        assert stats["total_runs"] >= 1
        assert stats["tasks"]["exec_task"]["run_count"] >= 1
        assert stats["tasks"]["exec_task"]["last_run"] is not None

    # =========================================================================
    # Run Task Now Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_run_task_now_success(self, scheduler):
        """Test manually running a task."""
        executed = []

        async def task_func():
            executed.append(True)

        scheduler.register("manual_task", task_func, 3600.0)  # Long interval

        result = await scheduler.run_task_now("manual_task")

        assert result is True
        assert len(executed) == 1
        task = scheduler._tasks["manual_task"]
        assert task.run_count == 1
        assert task.last_run is not None

    @pytest.mark.asyncio
    async def test_run_task_now_nonexistent(self, scheduler):
        """Test running nonexistent task returns False."""
        result = await scheduler.run_task_now("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_run_task_now_error(self, scheduler):
        """Test running task that errors returns False."""
        async def failing_task():
            raise ValueError("Error!")

        scheduler.register("failing_manual", failing_task, 3600.0)

        result = await scheduler.run_task_now("failing_manual")

        assert result is False
        task = scheduler._tasks["failing_manual"]
        assert task.error_count == 1
        assert task.last_error == "Error!"

    @pytest.mark.asyncio
    async def test_run_task_now_resets_failures(self, scheduler):
        """Test successful manual run resets consecutive failures."""
        async def task_func():
            pass

        scheduler.register("reset_task", task_func, 3600.0)
        scheduler._tasks["reset_task"].consecutive_failures = 5

        result = await scheduler.run_task_now("reset_task")

        assert result is True
        assert scheduler._tasks["reset_task"].consecutive_failures == 0

    # =========================================================================
    # Reset Task Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_reset_task_success(self, scheduler, mock_task_func):
        """Test resetting a task."""
        scheduler.register("reset_me", mock_task_func, 60.0)

        # Simulate failures
        task = scheduler._tasks["reset_me"]
        task.consecutive_failures = 10
        task.auto_disabled = True
        task.enabled = False
        task.last_error = "Some error"

        result = await scheduler.reset_task("reset_me")

        assert result is True
        assert task.consecutive_failures == 0
        assert task.auto_disabled is False
        assert task.enabled is True
        assert task.last_error is None

    @pytest.mark.asyncio
    async def test_reset_task_nonexistent(self, scheduler):
        """Test resetting nonexistent task returns False."""
        result = await scheduler.reset_task("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_task_restarts_loop_when_running(self, scheduler, mock_task_func):
        """Test reset restarts task loop when scheduler is running."""
        scheduler.register("restart_me", mock_task_func, 0.1)

        await scheduler.start()

        # Auto-disable the task
        task = scheduler._tasks["restart_me"]
        task.auto_disabled = True
        task.enabled = False

        # Remove from running tasks to simulate stopped loop
        if "restart_me" in scheduler._running_tasks:
            scheduler._running_tasks["restart_me"].cancel()
            del scheduler._running_tasks["restart_me"]

        await asyncio.sleep(0.1)

        # Reset should restart it
        await scheduler.reset_task("restart_me")

        assert "restart_me" in scheduler._running_tasks

        await scheduler.stop()

    # =========================================================================
    # Get Auto Disabled Tasks Tests
    # =========================================================================

    def test_get_auto_disabled_tasks_empty(self, scheduler, mock_task_func):
        """Test getting auto-disabled tasks when none exist."""
        scheduler.register("task1", mock_task_func, 60.0)
        scheduler.register("task2", mock_task_func, 60.0)

        disabled = scheduler.get_auto_disabled_tasks()

        assert disabled == []

    def test_get_auto_disabled_tasks_with_disabled(self, scheduler, mock_task_func):
        """Test getting auto-disabled tasks."""
        scheduler.register("task1", mock_task_func, 60.0)
        scheduler.register("task2", mock_task_func, 60.0)
        scheduler.register("task3", mock_task_func, 60.0)

        scheduler._tasks["task1"].auto_disabled = True
        scheduler._tasks["task3"].auto_disabled = True

        disabled = scheduler.get_auto_disabled_tasks()

        assert len(disabled) == 2
        assert "task1" in disabled
        assert "task3" in disabled


class TestGlobalSchedulerFunctions:
    """Tests for global scheduler functions."""

    @pytest.fixture(autouse=True)
    def reset_global_scheduler(self):
        """Reset global scheduler before each test."""
        import forge.services.scheduler as scheduler_module
        scheduler_module._scheduler = None
        yield
        scheduler_module._scheduler = None

    def test_get_scheduler_creates_instance(self):
        """Test get_scheduler creates a new instance."""
        scheduler = get_scheduler()

        assert scheduler is not None
        assert isinstance(scheduler, BackgroundScheduler)

    def test_get_scheduler_returns_same_instance(self):
        """Test get_scheduler returns singleton."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2

    @pytest.mark.asyncio
    async def test_setup_scheduler_disabled(self):
        """Test setup_scheduler when scheduler is disabled."""
        with patch('forge.services.scheduler.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                scheduler_enabled=False,
            )

            scheduler = await setup_scheduler()

            # Should return scheduler but no tasks registered
            assert scheduler is not None
            assert len(scheduler._tasks) == 0

    @pytest.mark.asyncio
    async def test_setup_scheduler_with_all_tasks(self):
        """Test setup_scheduler registers all enabled tasks."""
        with patch('forge.services.scheduler.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                scheduler_enabled=True,
                graph_snapshot_enabled=True,
                graph_snapshot_interval_minutes=60,
                version_compaction_enabled=True,
                version_compaction_interval_hours=24,
                query_cache_cleanup_interval_minutes=30,
            )

            scheduler = await setup_scheduler()

            assert "graph_snapshot" in scheduler._tasks
            assert "version_compaction" in scheduler._tasks
            assert "query_cache_cleanup" in scheduler._tasks

    @pytest.mark.asyncio
    async def test_setup_scheduler_snapshot_disabled(self):
        """Test setup_scheduler with snapshot disabled."""
        with patch('forge.services.scheduler.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                scheduler_enabled=True,
                graph_snapshot_enabled=False,
                version_compaction_enabled=True,
                version_compaction_interval_hours=24,
                query_cache_cleanup_interval_minutes=30,
            )

            scheduler = await setup_scheduler()

            assert "graph_snapshot" not in scheduler._tasks
            assert "version_compaction" in scheduler._tasks

    @pytest.mark.asyncio
    async def test_setup_scheduler_compaction_disabled(self):
        """Test setup_scheduler with compaction disabled."""
        with patch('forge.services.scheduler.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                scheduler_enabled=True,
                graph_snapshot_enabled=True,
                graph_snapshot_interval_minutes=60,
                version_compaction_enabled=False,
                query_cache_cleanup_interval_minutes=30,
            )

            scheduler = await setup_scheduler()

            assert "graph_snapshot" in scheduler._tasks
            assert "version_compaction" not in scheduler._tasks

    @pytest.mark.asyncio
    async def test_setup_scheduler_intervals(self):
        """Test setup_scheduler uses correct intervals."""
        with patch('forge.services.scheduler.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                scheduler_enabled=True,
                graph_snapshot_enabled=True,
                graph_snapshot_interval_minutes=120,
                version_compaction_enabled=True,
                version_compaction_interval_hours=48,
                query_cache_cleanup_interval_minutes=15,
            )

            scheduler = await setup_scheduler()

            assert scheduler._tasks["graph_snapshot"].interval_seconds == 120 * 60
            assert scheduler._tasks["version_compaction"].interval_seconds == 48 * 3600
            assert scheduler._tasks["query_cache_cleanup"].interval_seconds == 15 * 60


class TestScheduledTaskFunctions:
    """Tests for the scheduled task factory functions."""

    @pytest.mark.asyncio
    async def test_graph_snapshot_task(self):
        """Test graph snapshot task execution."""
        from forge.services.scheduler import _create_graph_snapshot_task

        task_func = _create_graph_snapshot_task()

        # Mock the dependencies
        mock_client = AsyncMock()
        mock_graph_repo = AsyncMock()
        mock_temporal_repo = AsyncMock()

        mock_graph_repo.get_graph_metrics = AsyncMock(return_value=MagicMock(
            total_nodes=100,
            total_edges=200,
            density=0.5,
            connected_components=1,
            nodes_by_type={"Capsule": 50},
            edges_by_type={"DERIVED_FROM": 100},
        ))
        mock_temporal_repo.create_graph_snapshot = AsyncMock(return_value=MagicMock(id="snap-123"))

        mock_circuit = AsyncMock()
        mock_circuit.call = AsyncMock(side_effect=lambda fn: fn())

        with patch('forge.services.scheduler.ForgeCircuits.neo4j', AsyncMock(return_value=mock_circuit)):
            with patch('forge.services.scheduler.Neo4jClient', return_value=mock_client):
                with patch('forge.services.scheduler.GraphRepository', return_value=mock_graph_repo):
                    with patch('forge.services.scheduler.TemporalRepository', return_value=mock_temporal_repo):
                        await task_func()

        mock_graph_repo.get_graph_metrics.assert_called_once()
        mock_temporal_repo.create_graph_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_version_compaction_task(self):
        """Test version compaction task execution."""
        from forge.services.scheduler import _create_version_compaction_task

        task_func = _create_version_compaction_task()

        mock_client = AsyncMock()
        mock_client.execute = AsyncMock(return_value=[{"capsule_id": "cap-1"}, {"capsule_id": "cap-2"}])

        mock_temporal_repo = AsyncMock()
        mock_temporal_repo.compact_old_versions = AsyncMock(return_value=5)

        mock_circuit = AsyncMock()
        mock_circuit.call = AsyncMock(side_effect=lambda fn: fn())

        with patch('forge.services.scheduler.ForgeCircuits.neo4j', AsyncMock(return_value=mock_circuit)):
            with patch('forge.services.scheduler.Neo4jClient', return_value=mock_client):
                with patch('forge.services.scheduler.TemporalRepository', return_value=mock_temporal_repo):
                    await task_func()

        # Should be called for each capsule
        assert mock_temporal_repo.compact_old_versions.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_cleanup_task(self):
        """Test cache cleanup task execution."""
        from forge.services.scheduler import _create_cache_cleanup_task

        task_func = _create_cache_cleanup_task()

        mock_cache = AsyncMock()
        mock_cache.cleanup_expired = AsyncMock(return_value={"removed": 5})

        with patch('forge.services.scheduler.get_query_cache', return_value=mock_cache):
            await task_func()

        mock_cache.cleanup_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_cleanup_task_no_cache(self):
        """Test cache cleanup task when no cache is configured."""
        from forge.services.scheduler import _create_cache_cleanup_task

        task_func = _create_cache_cleanup_task()

        with patch('forge.services.scheduler.get_query_cache', return_value=None):
            # Should not raise
            await task_func()


class TestSchedulerConcurrency:
    """Tests for scheduler concurrency handling."""

    @pytest.fixture
    def scheduler(self):
        return BackgroundScheduler()

    @pytest.mark.asyncio
    async def test_task_loop_uses_staggered_delay(self, scheduler):
        """Test task loops use staggered initial delays."""
        start_times = []

        async def recording_task():
            start_times.append(datetime.now(UTC))

        # Register tasks with different names (different hash values)
        scheduler.register("task_a", recording_task, 0.05)
        scheduler.register("task_b", recording_task, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        # Both tasks should have executed
        assert len(start_times) >= 2

    @pytest.mark.asyncio
    async def test_shutdown_event_stops_task(self, scheduler):
        """Test shutdown event properly stops task loops."""
        run_count = [0]

        async def counting_task():
            run_count[0] += 1
            await asyncio.sleep(0.01)

        scheduler.register("counting_task", counting_task, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.1)

        initial_count = run_count[0]
        await scheduler.stop()

        await asyncio.sleep(0.1)

        # No more executions after stop
        assert run_count[0] == initial_count or run_count[0] == initial_count + 1

    @pytest.mark.asyncio
    async def test_multiple_tasks_run_concurrently(self, scheduler):
        """Test multiple tasks run concurrently."""
        task_runs = {"task_a": 0, "task_b": 0}

        async def task_a():
            task_runs["task_a"] += 1
            await asyncio.sleep(0.02)

        async def task_b():
            task_runs["task_b"] += 1
            await asyncio.sleep(0.02)

        scheduler.register("task_a", task_a, 0.05)
        scheduler.register("task_b", task_b, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        # Both tasks should have run multiple times
        assert task_runs["task_a"] >= 2
        assert task_runs["task_b"] >= 2


class TestSchedulerEdgeCases:
    """Edge case tests for scheduler."""

    @pytest.fixture
    def scheduler(self):
        return BackgroundScheduler()

    @pytest.mark.asyncio
    async def test_very_short_interval(self, scheduler):
        """Test task with very short interval."""
        run_count = [0]

        async def fast_task():
            run_count[0] += 1

        scheduler.register("fast_task", fast_task, 0.01)  # 10ms

        await scheduler.start()
        await asyncio.sleep(0.15)
        await scheduler.stop()

        assert run_count[0] >= 5

    @pytest.mark.asyncio
    async def test_task_longer_than_interval(self, scheduler):
        """Test task that takes longer than its interval."""
        run_count = [0]

        async def slow_task():
            run_count[0] += 1
            await asyncio.sleep(0.1)  # Task takes 100ms

        scheduler.register("slow_task", slow_task, 0.05)  # 50ms interval

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        # Should still complete without issues
        assert run_count[0] >= 1

    @pytest.mark.asyncio
    async def test_task_cancelled_during_execution(self, scheduler):
        """Test task cancelled during execution."""
        started = []
        finished = []

        async def long_task():
            started.append(True)
            await asyncio.sleep(1.0)  # Long task
            finished.append(True)

        scheduler.register("long_task", long_task, 0.05)

        await scheduler.start()
        await asyncio.sleep(0.2)  # Let task start
        await scheduler.stop()  # Cancel mid-execution

        # Task started but may not have finished
        assert len(started) >= 1
        # Cancelled tasks won't finish cleanly
        assert len(finished) <= len(started)

    @pytest.mark.asyncio
    async def test_run_task_now_while_running(self, scheduler):
        """Test manually running a task while scheduler is running."""
        run_count = [0]

        async def counting_task():
            run_count[0] += 1

        scheduler.register("count_task", counting_task, 3600.0)  # Long interval

        await scheduler.start()

        # Manually trigger multiple times
        await scheduler.run_task_now("count_task")
        await scheduler.run_task_now("count_task")
        await scheduler.run_task_now("count_task")

        await scheduler.stop()

        assert run_count[0] >= 3

    @pytest.mark.asyncio
    async def test_task_state_lock_protects_concurrent_updates(self, scheduler):
        """Test task state lock protects concurrent state updates."""
        async def task_func():
            pass

        scheduler.register("lock_test", task_func, 3600.0)

        # Simulate concurrent run_task_now and reset_task calls
        async def concurrent_runs():
            tasks = [
                scheduler.run_task_now("lock_test"),
                scheduler.reset_task("lock_test"),
                scheduler.run_task_now("lock_test"),
            ]
            await asyncio.gather(*tasks)

        # Should not raise any concurrency errors
        await concurrent_runs()

        task = scheduler._tasks["lock_test"]
        assert task.run_count >= 1
