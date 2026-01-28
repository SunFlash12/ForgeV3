"""
Comprehensive tests for the Forge Cascade V2 Canary Deployment module.

Tests cover:
- CanaryState and RolloutStrategy enums
- CanaryConfig dataclass
- CanaryMetrics with error rates and latency percentiles
- CanaryDeployment state tracking
- CanaryManager deployment lifecycle
- Traffic routing and outcome recording
- Automatic advancement and rollback
- Approval workflow
- OverlayCanaryManager specialization
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from forge.immune.canary import (
    CanaryConfig,
    CanaryDeployment,
    CanaryManager,
    CanaryMetrics,
    CanaryState,
    OverlayCanaryManager,
    RolloutStrategy,
)

# =============================================================================
# Test Enums
# =============================================================================


class TestCanaryState:
    """Tests for CanaryState enum."""

    def test_all_states_exist(self) -> None:
        """Verify all expected canary states are defined."""
        assert CanaryState.PENDING == "pending"
        assert CanaryState.RUNNING == "running"
        assert CanaryState.PAUSED == "paused"
        assert CanaryState.SUCCEEDED == "succeeded"
        assert CanaryState.FAILED == "failed"
        assert CanaryState.ROLLING_BACK == "rolling_back"

    def test_enum_string_inheritance(self) -> None:
        """Verify enum inherits from str."""
        assert isinstance(CanaryState.RUNNING, str)


class TestRolloutStrategy:
    """Tests for RolloutStrategy enum."""

    def test_all_strategies_exist(self) -> None:
        """Verify all expected rollout strategies are defined."""
        assert RolloutStrategy.LINEAR == "linear"
        assert RolloutStrategy.EXPONENTIAL == "exponential"
        assert RolloutStrategy.MANUAL == "manual"


# =============================================================================
# Test CanaryConfig
# =============================================================================


class TestCanaryConfig:
    """Tests for CanaryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CanaryConfig()

        assert config.initial_percentage == 5.0
        assert config.increment_percentage == 10.0
        assert config.max_percentage == 100.0
        assert config.step_duration_seconds == 300.0
        assert config.min_samples_per_step == 100
        assert config.strategy == RolloutStrategy.LINEAR
        assert config.error_rate_threshold == 0.05
        assert config.latency_p99_threshold_ms == 2000.0
        assert config.anomaly_score_threshold == 0.8
        assert config.auto_rollback is True
        assert config.rollback_on_error is True
        assert config.require_approval_at_percent == 50.0

    def test_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = CanaryConfig(
            initial_percentage=10.0,
            increment_percentage=20.0,
            strategy=RolloutStrategy.EXPONENTIAL,
            error_rate_threshold=0.10,
        )

        assert config.initial_percentage == 10.0
        assert config.increment_percentage == 20.0
        assert config.strategy == RolloutStrategy.EXPONENTIAL
        assert config.error_rate_threshold == 0.10


# =============================================================================
# Test CanaryMetrics
# =============================================================================


class TestCanaryMetrics:
    """Tests for CanaryMetrics dataclass."""

    @pytest.fixture
    def metrics(self) -> CanaryMetrics:
        """Create metrics instance for testing."""
        return CanaryMetrics()

    def test_initial_values(self, metrics: CanaryMetrics) -> None:
        """Test initial metric values are zero."""
        assert metrics.total_requests == 0
        assert metrics.canary_requests == 0
        assert metrics.control_requests == 0
        assert metrics.canary_errors == 0
        assert metrics.control_errors == 0
        assert len(metrics.canary_latencies) == 0
        assert len(metrics.control_latencies) == 0

    def test_canary_error_rate_zero_requests(self, metrics: CanaryMetrics) -> None:
        """Test error rate with zero requests."""
        assert metrics.canary_error_rate == 0.0
        assert metrics.control_error_rate == 0.0

    def test_canary_error_rate_calculation(self, metrics: CanaryMetrics) -> None:
        """Test error rate calculation."""
        metrics.canary_requests = 100
        metrics.canary_errors = 5

        assert metrics.canary_error_rate == 0.05

    def test_control_error_rate_calculation(self, metrics: CanaryMetrics) -> None:
        """Test control error rate calculation."""
        metrics.control_requests = 200
        metrics.control_errors = 10

        assert metrics.control_error_rate == 0.05

    def test_error_rate_delta(self, metrics: CanaryMetrics) -> None:
        """Test error rate delta calculation."""
        metrics.canary_requests = 100
        metrics.canary_errors = 10  # 10%
        metrics.control_requests = 100
        metrics.control_errors = 5  # 5%

        assert metrics.error_rate_delta == 0.05  # 10% - 5%

    def test_percentile_empty_list(self, metrics: CanaryMetrics) -> None:
        """Test percentile with empty list."""
        assert metrics.percentile([], 99) == 0.0

    def test_percentile_calculation(self, metrics: CanaryMetrics) -> None:
        """Test percentile calculation."""
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        p50 = metrics.percentile(latencies, 50)
        p99 = metrics.percentile(latencies, 99)

        assert p50 == 300.0  # Median
        assert p99 == 500.0  # Near max

    def test_canary_p99(self, metrics: CanaryMetrics) -> None:
        """Test canary P99 property."""
        metrics.canary_latencies = [100.0, 200.0, 300.0, 400.0, 500.0]
        assert metrics.canary_p99 == 500.0

    def test_control_p99(self, metrics: CanaryMetrics) -> None:
        """Test control P99 property."""
        metrics.control_latencies = [50.0, 100.0, 150.0, 200.0, 250.0]
        assert metrics.control_p99 == 250.0

    def test_record_step(self, metrics: CanaryMetrics) -> None:
        """Test recording step metrics."""
        metrics.canary_requests = 50
        metrics.canary_errors = 2
        metrics.canary_latencies = [100.0, 200.0, 300.0]

        metrics.record_step(1, 10.0)

        assert len(metrics.step_metrics) == 1
        step = metrics.step_metrics[0]
        assert step["step"] == 1
        assert step["percentage"] == 10.0
        assert step["canary_requests"] == 50
        assert "timestamp" in step

    def test_reset_window(self, metrics: CanaryMetrics) -> None:
        """Test resetting window metrics."""
        metrics.canary_requests = 100
        metrics.control_requests = 200
        metrics.canary_errors = 10
        metrics.control_errors = 5
        metrics.canary_latencies = [100.0, 200.0]
        metrics.control_latencies = [50.0, 100.0]

        metrics.reset_window()

        assert metrics.canary_requests == 0
        assert metrics.control_requests == 0
        assert metrics.canary_errors == 0
        assert metrics.control_errors == 0
        assert len(metrics.canary_latencies) == 0
        assert len(metrics.control_latencies) == 0

    def test_to_dict(self, metrics: CanaryMetrics) -> None:
        """Test converting metrics to dictionary."""
        metrics.total_requests = 100
        metrics.canary_requests = 60
        metrics.control_requests = 40

        result = metrics.to_dict()

        assert result["total_requests"] == 100
        assert result["canary_requests"] == 60
        assert result["control_requests"] == 40
        assert "canary_error_rate" in result
        assert "control_error_rate" in result
        assert "error_rate_delta" in result
        assert "canary_p99_ms" in result
        assert "control_p99_ms" in result
        assert "step_metrics" in result


# =============================================================================
# Test CanaryDeployment
# =============================================================================


class TestCanaryDeployment:
    """Tests for CanaryDeployment dataclass."""

    @pytest.fixture
    def deployment(self) -> CanaryDeployment[str]:
        """Create a deployment for testing."""
        config = CanaryConfig()
        return CanaryDeployment(
            id="deploy-123",
            name="test_deployment",
            canary_version="v2.0",
            control_version="v1.0",
            config=config,
        )

    def test_deployment_creation(self, deployment: CanaryDeployment[str]) -> None:
        """Test deployment is created with correct values."""
        assert deployment.id == "deploy-123"
        assert deployment.name == "test_deployment"
        assert deployment.canary_version == "v2.0"
        assert deployment.control_version == "v1.0"
        assert deployment.state == CanaryState.PENDING
        assert deployment.current_percentage == 0.0
        assert deployment.current_step == 0
        assert deployment.awaiting_approval is False

    def test_deployment_has_metrics(self, deployment: CanaryDeployment[str]) -> None:
        """Test deployment includes metrics object."""
        assert isinstance(deployment.metrics, CanaryMetrics)

    def test_to_dict(self, deployment: CanaryDeployment[str]) -> None:
        """Test converting deployment to dictionary."""
        result = deployment.to_dict()

        assert result["id"] == "deploy-123"
        assert result["name"] == "test_deployment"
        assert result["state"] == "pending"
        assert result["current_percentage"] == 0.0
        assert result["current_step"] == 0
        assert "created_at" in result
        assert "metrics" in result
        assert "config" in result


# =============================================================================
# Test CanaryManager - Creation and Basic Operations
# =============================================================================


class TestCanaryManagerBasics:
    """Tests for CanaryManager basic operations."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(
            initial_percentage=10.0,
            step_duration_seconds=1.0,  # Fast for testing
            min_samples_per_step=5,
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_create_deployment(self, manager: CanaryManager[str]) -> None:
        """Test creating a deployment."""
        deployment = await manager.create_deployment(
            name="test_deploy",
            canary_version="v2.0",
            control_version="v1.0",
        )

        assert deployment is not None
        assert deployment.name == "test_deploy"
        assert deployment.canary_version == "v2.0"
        assert deployment.control_version == "v1.0"
        assert deployment.state == CanaryState.PENDING

    @pytest.mark.asyncio
    async def test_create_deployment_with_custom_id(self, manager: CanaryManager[str]) -> None:
        """Test creating deployment with custom ID."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
            deployment_id="custom-id-123",
        )

        assert deployment.id == "custom-id-123"

    @pytest.mark.asyncio
    async def test_get_deployment(self, manager: CanaryManager[str]) -> None:
        """Test getting deployment by ID."""
        created = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        retrieved = await manager.get_deployment(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_deployment(self, manager: CanaryManager[str]) -> None:
        """Test getting non-existent deployment returns None."""
        result = await manager.get_deployment("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_deployments(self, manager: CanaryManager[str]) -> None:
        """Test listing all deployments."""
        await manager.create_deployment(
            name="deploy1",
            canary_version="v1",
            control_version="v0",
        )
        await manager.create_deployment(
            name="deploy2",
            canary_version="v2",
            control_version="v1",
        )

        all_deployments = await manager.list_deployments()
        assert len(all_deployments) == 2

    @pytest.mark.asyncio
    async def test_list_deployments_filtered_by_state(self, manager: CanaryManager[str]) -> None:
        """Test listing deployments filtered by state."""
        deploy1 = await manager.create_deployment(
            name="deploy1",
            canary_version="v1",
            control_version="v0",
        )
        await manager.create_deployment(
            name="deploy2",
            canary_version="v2",
            control_version="v1",
        )

        # Start one deployment
        await manager.start(deploy1.id)

        pending = await manager.list_deployments(state=CanaryState.PENDING)
        running = await manager.list_deployments(state=CanaryState.RUNNING)

        assert len(pending) == 1
        assert len(running) == 1


# =============================================================================
# Test CanaryManager - State Transitions
# =============================================================================


class TestCanaryManagerStateTransitions:
    """Tests for CanaryManager state transitions."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(
            initial_percentage=10.0,
            step_duration_seconds=0.1,
            min_samples_per_step=2,
            require_approval_at_percent=None,  # Disable approval for tests
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_start_deployment(self, manager: CanaryManager[str]) -> None:
        """Test starting a deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        success = await manager.start(deployment.id)

        assert success is True
        assert deployment.state == CanaryState.RUNNING
        assert deployment.started_at is not None
        assert deployment.current_percentage == 10.0
        assert deployment.current_step == 1

    @pytest.mark.asyncio
    async def test_start_nonexistent_deployment(self, manager: CanaryManager[str]) -> None:
        """Test starting non-existent deployment fails."""
        success = await manager.start("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_start_already_started_deployment(self, manager: CanaryManager[str]) -> None:
        """Test starting already started deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        await manager.start(deployment.id)
        success = await manager.start(deployment.id)

        assert success is False

    @pytest.mark.asyncio
    async def test_pause_deployment(self, manager: CanaryManager[str]) -> None:
        """Test pausing a running deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        success = await manager.pause(deployment.id)

        assert success is True
        assert deployment.state == CanaryState.PAUSED

    @pytest.mark.asyncio
    async def test_pause_non_running_deployment(self, manager: CanaryManager[str]) -> None:
        """Test pausing non-running deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        success = await manager.pause(deployment.id)
        assert success is False

    @pytest.mark.asyncio
    async def test_resume_deployment(self, manager: CanaryManager[str]) -> None:
        """Test resuming a paused deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)
        await manager.pause(deployment.id)

        success = await manager.resume(deployment.id)

        assert success is True
        assert deployment.state == CanaryState.RUNNING

    @pytest.mark.asyncio
    async def test_resume_non_paused_deployment(self, manager: CanaryManager[str]) -> None:
        """Test resuming non-paused deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        success = await manager.resume(deployment.id)
        assert success is False

    @pytest.mark.asyncio
    async def test_state_change_callback(self, manager: CanaryManager[str]) -> None:
        """Test state change callback is invoked."""
        callback = AsyncMock()
        manager.on_state_change = callback

        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        callback.assert_called()
        call_args = callback.call_args
        assert call_args[0][1] == CanaryState.PENDING
        assert call_args[0][2] == CanaryState.RUNNING


# =============================================================================
# Test CanaryManager - Rollback
# =============================================================================


class TestCanaryManagerRollback:
    """Tests for CanaryManager rollback functionality."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(
            initial_percentage=10.0,
            step_duration_seconds=0.1,
            min_samples_per_step=2,
            error_rate_threshold=0.05,
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_manual_rollback(self, manager: CanaryManager[str]) -> None:
        """Test manual rollback of deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        success = await manager.rollback(deployment.id, reason="Test rollback")

        assert success is True
        assert deployment.state == CanaryState.FAILED
        assert deployment.rollback_reason == "Test rollback"
        assert deployment.current_percentage == 0.0

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_deployment(self, manager: CanaryManager[str]) -> None:
        """Test rollback of non-existent deployment fails."""
        success = await manager.rollback("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_rollback_completed_deployment(self, manager: CanaryManager[str]) -> None:
        """Test rollback of completed deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        # Force to succeeded state
        deployment.state = CanaryState.SUCCEEDED

        success = await manager.rollback(deployment.id)
        assert success is False


# =============================================================================
# Test CanaryManager - Traffic Routing
# =============================================================================


class TestCanaryManagerRouting:
    """Tests for CanaryManager traffic routing."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(initial_percentage=50.0)
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_route_returns_version(self, manager: CanaryManager[str]) -> None:
        """Test routing returns a version."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        version = manager.route(deployment.id)

        assert version in ["v2.0", "v1.0"]

    @pytest.mark.asyncio
    async def test_route_nonexistent_deployment(self, manager: CanaryManager[str]) -> None:
        """Test routing non-existent deployment returns None."""
        version = manager.route("nonexistent")
        assert version is None

    @pytest.mark.asyncio
    async def test_route_non_running_returns_control(self, manager: CanaryManager[str]) -> None:
        """Test routing non-running deployment returns control."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        # Don't start - still PENDING

        version = manager.route(deployment.id)
        assert version == "v1.0"

    @pytest.mark.asyncio
    async def test_route_increments_counter(self, manager: CanaryManager[str]) -> None:
        """Test routing increments request counter."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        initial_count = deployment.metrics.total_requests

        manager.route(deployment.id)
        manager.route(deployment.id)
        manager.route(deployment.id)

        assert deployment.metrics.total_requests == initial_count + 3

    @pytest.mark.asyncio
    async def test_should_use_canary(self, manager: CanaryManager[str]) -> None:
        """Test should_use_canary returns boolean."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        result = manager.should_use_canary(deployment.id)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_should_use_canary_non_running(self, manager: CanaryManager[str]) -> None:
        """Test should_use_canary returns False for non-running."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        result = manager.should_use_canary(deployment.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_routing_distribution(self, manager: CanaryManager[str]) -> None:
        """Test routing roughly follows percentage distribution."""
        # Use 50% canary for easier testing
        deployment = await manager.create_deployment(
            name="test",
            canary_version="canary",
            control_version="control",
        )
        await manager.start(deployment.id)

        canary_count = 0
        control_count = 0

        for _ in range(1000):
            version = manager.route(deployment.id)
            if version == "canary":
                canary_count += 1
            else:
                control_count += 1

        # Should be roughly 50/50, allow 10% deviation
        ratio = canary_count / (canary_count + control_count)
        assert 0.40 <= ratio <= 0.60


# =============================================================================
# Test CanaryManager - Outcome Recording
# =============================================================================


class TestCanaryManagerOutcomes:
    """Tests for CanaryManager outcome recording."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(initial_percentage=50.0)
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_record_canary_success(self, manager: CanaryManager[str]) -> None:
        """Test recording canary success."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        await manager.record_outcome(
            deployment.id,
            is_canary=True,
            success=True,
            latency_ms=100.0,
        )

        assert deployment.metrics.canary_requests == 1
        assert deployment.metrics.canary_errors == 0
        assert 100.0 in deployment.metrics.canary_latencies

    @pytest.mark.asyncio
    async def test_record_canary_failure(self, manager: CanaryManager[str]) -> None:
        """Test recording canary failure."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        await manager.record_outcome(
            deployment.id,
            is_canary=True,
            success=False,
            latency_ms=500.0,
        )

        assert deployment.metrics.canary_requests == 1
        assert deployment.metrics.canary_errors == 1

    @pytest.mark.asyncio
    async def test_record_control_success(self, manager: CanaryManager[str]) -> None:
        """Test recording control success."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        await manager.record_outcome(
            deployment.id,
            is_canary=False,
            success=True,
            latency_ms=50.0,
        )

        assert deployment.metrics.control_requests == 1
        assert deployment.metrics.control_errors == 0
        assert 50.0 in deployment.metrics.control_latencies

    @pytest.mark.asyncio
    async def test_record_outcome_trims_latencies(self, manager: CanaryManager[str]) -> None:
        """Test latency lists are trimmed."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        # Record many outcomes
        for i in range(15000):
            await manager.record_outcome(
                deployment.id,
                is_canary=True,
                success=True,
                latency_ms=float(i),
            )

        # Should be trimmed to 5000
        assert len(deployment.metrics.canary_latencies) <= 5000


# =============================================================================
# Test CanaryManager - Health Checks
# =============================================================================


class TestCanaryManagerHealthChecks:
    """Tests for CanaryManager health check logic."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(
            initial_percentage=10.0,
            error_rate_threshold=0.05,
            latency_p99_threshold_ms=1000.0,
            min_samples_per_step=10,
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_health_check_passes_with_good_metrics(self, manager: CanaryManager[str]) -> None:
        """Test health check passes with good metrics."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        # Set up good metrics
        deployment.metrics.canary_requests = 100
        deployment.metrics.canary_errors = 2  # 2% error rate
        deployment.metrics.canary_latencies = [100.0] * 100

        healthy, reason = await manager._check_health(deployment)

        assert healthy is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_health_check_fails_high_error_rate(self, manager: CanaryManager[str]) -> None:
        """Test health check fails with high error rate."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        # Set up bad metrics - 10% error rate
        deployment.metrics.canary_requests = 100
        deployment.metrics.canary_errors = 10

        healthy, reason = await manager._check_health(deployment)

        assert healthy is False
        assert "Error rate" in reason

    @pytest.mark.asyncio
    async def test_health_check_fails_high_latency(self, manager: CanaryManager[str]) -> None:
        """Test health check fails with high latency."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        # Set up high latency
        deployment.metrics.canary_requests = 100
        deployment.metrics.canary_errors = 0
        deployment.metrics.canary_latencies = [2000.0] * 100  # All 2000ms

        healthy, reason = await manager._check_health(deployment)

        assert healthy is False
        assert "P99 latency" in reason

    @pytest.mark.asyncio
    async def test_health_check_skipped_insufficient_samples(
        self, manager: CanaryManager[str]
    ) -> None:
        """Test health check skipped with insufficient samples."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        # Few samples
        deployment.metrics.canary_requests = 5

        healthy, reason = await manager._check_health(deployment)

        assert healthy is True  # Passes due to insufficient data


# =============================================================================
# Test CanaryManager - Approval Workflow
# =============================================================================


class TestCanaryManagerApproval:
    """Tests for CanaryManager approval workflow."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager with approval enabled."""
        config = CanaryConfig(
            initial_percentage=10.0,
            increment_percentage=20.0,
            require_approval_at_percent=50.0,
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_approve_awaiting_deployment(self, manager: CanaryManager[str]) -> None:
        """Test approving a deployment awaiting approval."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        deployment.awaiting_approval = True

        success = await manager.approve(deployment.id, approved_by="admin")

        assert success is True
        assert deployment.awaiting_approval is False
        assert deployment.approved_by == "admin"

    @pytest.mark.asyncio
    async def test_approve_non_awaiting_deployment(self, manager: CanaryManager[str]) -> None:
        """Test approving non-awaiting deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )

        success = await manager.approve(deployment.id, approved_by="admin")
        assert success is False


# =============================================================================
# Test CanaryManager - Advancement
# =============================================================================


class TestCanaryManagerAdvancement:
    """Tests for CanaryManager step advancement."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        config = CanaryConfig(
            initial_percentage=10.0,
            increment_percentage=20.0,
            max_percentage=100.0,
            strategy=RolloutStrategy.LINEAR,
            require_approval_at_percent=None,
        )
        return CanaryManager(default_config=config)

    @pytest.mark.asyncio
    async def test_linear_advancement(self, manager: CanaryManager[str]) -> None:
        """Test linear rollout strategy advancement."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        initial = deployment.current_percentage
        await manager._advance_step(deployment)

        expected = initial + 20.0
        assert deployment.current_percentage == expected

    @pytest.mark.asyncio
    async def test_exponential_advancement(self) -> None:
        """Test exponential rollout strategy advancement."""
        config = CanaryConfig(
            initial_percentage=5.0,
            strategy=RolloutStrategy.EXPONENTIAL,
            require_approval_at_percent=None,
        )
        manager: CanaryManager[str] = CanaryManager(default_config=config)

        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        await manager._advance_step(deployment)

        # Should double: 5% -> 10%
        assert deployment.current_percentage == 10.0

    @pytest.mark.asyncio
    async def test_manual_advance(self) -> None:
        """Test manual advancement."""
        config = CanaryConfig(
            initial_percentage=10.0,
            increment_percentage=20.0,
            strategy=RolloutStrategy.MANUAL,
            require_approval_at_percent=None,
        )
        manager: CanaryManager[str] = CanaryManager(default_config=config)

        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        success = await manager.manual_advance(deployment.id)

        # Manual strategy should NOT auto-advance
        assert success is True

    @pytest.mark.asyncio
    async def test_advancement_caps_at_max(self, manager: CanaryManager[str]) -> None:
        """Test advancement caps at max percentage."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        # Set near max
        deployment.current_percentage = 95.0

        await manager._advance_step(deployment)

        # Should complete at 100%
        assert deployment.state == CanaryState.SUCCEEDED
        assert deployment.current_percentage == 100.0


# =============================================================================
# Test CanaryManager - Cleanup
# =============================================================================


class TestCanaryManagerCleanup:
    """Tests for CanaryManager cleanup operations."""

    @pytest.fixture
    def manager(self) -> CanaryManager[str]:
        """Create a canary manager for testing."""
        return CanaryManager()

    @pytest.mark.asyncio
    async def test_cleanup_completed_deployment(self, manager: CanaryManager[str]) -> None:
        """Test cleaning up completed deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        deployment.state = CanaryState.SUCCEEDED

        success = await manager.cleanup(deployment.id)

        assert success is True
        assert await manager.get_deployment(deployment.id) is None

    @pytest.mark.asyncio
    async def test_cleanup_failed_deployment(self, manager: CanaryManager[str]) -> None:
        """Test cleaning up failed deployment."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        deployment.state = CanaryState.FAILED

        success = await manager.cleanup(deployment.id)
        assert success is True

    @pytest.mark.asyncio
    async def test_cleanup_active_deployment_fails(self, manager: CanaryManager[str]) -> None:
        """Test cleaning up active deployment fails."""
        deployment = await manager.create_deployment(
            name="test",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deployment.id)

        success = await manager.cleanup(deployment.id)
        assert success is False

    @pytest.mark.asyncio
    async def test_get_active_deployments(self, manager: CanaryManager[str]) -> None:
        """Test getting active deployment IDs."""
        deploy1 = await manager.create_deployment(
            name="test1",
            canary_version="v2.0",
            control_version="v1.0",
        )
        deploy2 = await manager.create_deployment(
            name="test2",
            canary_version="v2.0",
            control_version="v1.0",
        )

        await manager.start(deploy1.id)

        active = manager.get_active_deployments()

        assert deploy1.id in active
        assert deploy2.id not in active

    @pytest.mark.asyncio
    async def test_get_summary(self, manager: CanaryManager[str]) -> None:
        """Test getting manager summary."""
        await manager.create_deployment(
            name="test1",
            canary_version="v2.0",
            control_version="v1.0",
        )
        deploy2 = await manager.create_deployment(
            name="test2",
            canary_version="v2.0",
            control_version="v1.0",
        )
        await manager.start(deploy2.id)

        summary = manager.get_summary()

        assert summary["total_deployments"] == 2
        assert "by_state" in summary
        assert "active_ids" in summary
        assert len(summary["active_ids"]) == 1


# =============================================================================
# Test OverlayCanaryManager
# =============================================================================


class TestOverlayCanaryManager:
    """Tests for OverlayCanaryManager specialization."""

    def test_default_config(self) -> None:
        """Test overlay manager has specialized default config."""
        manager = OverlayCanaryManager()

        config = manager.default_config

        assert config.initial_percentage == 5.0
        assert config.increment_percentage == 15.0
        assert config.step_duration_seconds == 180.0
        assert config.min_samples_per_step == 50
        assert config.error_rate_threshold == 0.03

    @pytest.mark.asyncio
    async def test_create_overlay_deployment(self) -> None:
        """Test creating overlay deployment."""
        manager = OverlayCanaryManager()

        deployment = await manager.create_deployment(
            name="ml_overlay",
            canary_version={"model": "v2"},
            control_version={"model": "v1"},
        )

        assert deployment.canary_version == {"model": "v2"}
        assert deployment.control_version == {"model": "v1"}
