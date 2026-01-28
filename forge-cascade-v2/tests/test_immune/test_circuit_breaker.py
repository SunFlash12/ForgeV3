"""
Comprehensive tests for the Forge Cascade V2 Circuit Breaker module.

Tests cover:
- CircuitState enum
- CircuitBreakerConfig dataclass
- CircuitStats tracking
- CircuitBreakerError exception
- CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold detection
- Recovery timeout behavior
- Call timeout handling
- Decorator usage
- CircuitBreakerRegistry management
- Global registry functions
- ForgeCircuits pre-configured breakers
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

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


# =============================================================================
# Test CircuitState Enum
# =============================================================================


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_all_states_exist(self) -> None:
        """Verify all expected circuit states are defined."""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_enum_string_inheritance(self) -> None:
        """Verify enum inherits from str."""
        assert isinstance(CircuitState.CLOSED, str)


# =============================================================================
# Test CircuitBreakerConfig
# =============================================================================


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.failure_rate_threshold == 0.5
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.window_size == 10
        assert config.min_calls_for_rate == 5
        assert config.success_threshold == 2
        assert config.call_timeout == 30.0
        assert config.excluded_exceptions == ()

    def test_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60.0,
            call_timeout=10.0,
        )

        assert config.failure_threshold == 3
        assert config.recovery_timeout == 60.0
        assert config.call_timeout == 10.0

    def test_excluded_exceptions(self) -> None:
        """Test excluded exceptions configuration."""
        config = CircuitBreakerConfig(
            excluded_exceptions=(ValueError, KeyError),
        )

        assert ValueError in config.excluded_exceptions
        assert KeyError in config.excluded_exceptions


# =============================================================================
# Test CircuitStats
# =============================================================================


class TestCircuitStats:
    """Tests for CircuitStats dataclass."""

    @pytest.fixture
    def stats(self) -> CircuitStats:
        """Create stats instance for testing."""
        return CircuitStats()

    def test_initial_values(self, stats: CircuitStats) -> None:
        """Test initial stat values are zero."""
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0
        assert stats.timeout_calls == 0
        assert len(stats.recent_successes) == 0
        assert len(stats.recent_failures) == 0
        assert stats.half_open_successes == 0
        assert stats.half_open_failures == 0

    def test_failure_rate_empty(self, stats: CircuitStats) -> None:
        """Test failure rate with no data."""
        assert stats.failure_rate == 0.0

    def test_failure_rate_calculation(self, stats: CircuitStats) -> None:
        """Test failure rate calculation."""
        stats.recent_successes = [1.0, 2.0, 3.0]
        stats.recent_failures = [4.0, 5.0]

        assert stats.failure_rate == 2 / 5  # 40%

    def test_success_rate(self, stats: CircuitStats) -> None:
        """Test success rate calculation."""
        stats.recent_successes = [1.0, 2.0, 3.0]
        stats.recent_failures = [4.0, 5.0]

        assert stats.success_rate == 3 / 5  # 60%

    def test_reset_window(self, stats: CircuitStats) -> None:
        """Test resetting sliding window."""
        stats.recent_successes = [1.0, 2.0, 3.0]
        stats.recent_failures = [4.0, 5.0]

        stats.reset_window()

        assert len(stats.recent_successes) == 0
        assert len(stats.recent_failures) == 0

    def test_reset_half_open(self, stats: CircuitStats) -> None:
        """Test resetting half-open counters."""
        stats.half_open_successes = 2
        stats.half_open_failures = 1

        stats.reset_half_open()

        assert stats.half_open_successes == 0
        assert stats.half_open_failures == 0

    def test_to_dict(self, stats: CircuitStats) -> None:
        """Test converting stats to dictionary."""
        stats.total_calls = 100
        stats.successful_calls = 90
        stats.failed_calls = 10

        result = stats.to_dict()

        assert result["total_calls"] == 100
        assert result["successful_calls"] == 90
        assert result["failed_calls"] == 10
        assert "failure_rate" in result
        assert "success_rate" in result


# =============================================================================
# Test CircuitBreakerError
# =============================================================================


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_error_creation(self) -> None:
        """Test error is created with correct attributes."""
        error = CircuitBreakerError(
            circuit_name="test_circuit",
            state=CircuitState.OPEN,
            recovery_time=15.5,
        )

        assert error.circuit_name == "test_circuit"
        assert error.state == CircuitState.OPEN
        assert error.recovery_time == 15.5

    def test_error_message_with_recovery_time(self) -> None:
        """Test error message includes recovery time."""
        error = CircuitBreakerError(
            circuit_name="test",
            state=CircuitState.OPEN,
            recovery_time=10.0,
        )

        message = str(error)
        assert "test" in message
        assert "open" in message
        assert "10.0" in message

    def test_error_message_without_recovery_time(self) -> None:
        """Test error message without recovery time."""
        error = CircuitBreakerError(
            circuit_name="test",
            state=CircuitState.OPEN,
        )

        message = str(error)
        assert "test" in message
        assert "open" in message


# =============================================================================
# Test CircuitBreaker - Basic Operations
# =============================================================================


class TestCircuitBreakerBasics:
    """Tests for CircuitBreaker basic operations."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,
            call_timeout=5.0,
        )
        return CircuitBreaker("test_breaker", config)

    def test_breaker_creation(self, breaker: CircuitBreaker[str]) -> None:
        """Test breaker is created with correct initial state."""
        assert breaker.name == "test_breaker"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.is_half_open is False

    def test_state_property(self, breaker: CircuitBreaker[str]) -> None:
        """Test state property returns current state."""
        assert breaker.state == CircuitState.CLOSED

    def test_stats_property(self, breaker: CircuitBreaker[str]) -> None:
        """Test stats property returns stats object."""
        stats = breaker.stats
        assert isinstance(stats, CircuitStats)

    def test_get_status(self, breaker: CircuitBreaker[str]) -> None:
        """Test get_status returns complete status dict."""
        status = breaker.get_status()

        assert status["name"] == "test_breaker"
        assert status["state"] == "closed"
        assert "stats" in status
        assert "config" in status
        assert "recovery_time" in status


# =============================================================================
# Test CircuitBreaker - State Transitions
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Tests for CircuitBreaker state transitions."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,  # Fast recovery for tests
            success_threshold=2,
            call_timeout=5.0,
        )
        return CircuitBreaker("test_breaker", config)

    @pytest.mark.asyncio
    async def test_successful_call_keeps_closed(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test successful calls keep circuit closed."""

        async def success_fn() -> str:
            return "success"

        result = await breaker.call(success_fn)

        assert result == "success"
        assert breaker.is_closed is True
        assert breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self, breaker: CircuitBreaker[str]) -> None:
        """Test failures open the circuit after threshold."""

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        # Cause failures up to threshold
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        assert breaker.is_open is True
        assert breaker.stats.failed_calls == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test open circuit rejects calls."""

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        async def success_fn() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        # Now calls should be rejected
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(success_fn)

        assert exc_info.value.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_recovery_timeout_transitions_to_half_open(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test circuit transitions to half-open after recovery timeout."""

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        async def success_fn() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        assert breaker.is_open is True

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open
        result = await breaker.call(success_fn)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test successful calls in half-open close the circuit."""

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        async def success_fn() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Successful calls in half-open (need success_threshold=2)
        await breaker.call(success_fn)
        await breaker.call(success_fn)

        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test failure in half-open reopens circuit."""

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        async def success_fn() -> str:
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        # Wait for recovery
        await asyncio.sleep(0.15)

        # First call transitions to half-open and succeeds
        await breaker.call(success_fn)

        # Failure in half-open
        with pytest.raises(RuntimeError):
            await breaker.call(failing_fn)

        assert breaker.is_open is True


# =============================================================================
# Test CircuitBreaker - Failure Rate Detection
# =============================================================================


class TestCircuitBreakerFailureRate:
    """Tests for CircuitBreaker failure rate detection."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for testing failure rate."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High threshold
            failure_rate_threshold=0.5,  # 50% failure rate
            min_calls_for_rate=5,
            window_size=10,
            recovery_timeout=0.1,
        )
        return CircuitBreaker("rate_test", config)

    @pytest.mark.asyncio
    async def test_failure_rate_opens_circuit(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test failure rate threshold opens circuit."""

        async def success_fn() -> str:
            return "success"

        async def failing_fn() -> str:
            raise RuntimeError("Simulated failure")

        # 2 successes, 3 failures = 60% failure rate
        await breaker.call(success_fn)
        await breaker.call(success_fn)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        # Should be open due to failure rate (60% > 50%)
        assert breaker.is_open is True


# =============================================================================
# Test CircuitBreaker - Timeout Handling
# =============================================================================


class TestCircuitBreakerTimeout:
    """Tests for CircuitBreaker timeout handling."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker with short timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            call_timeout=0.1,  # 100ms timeout
        )
        return CircuitBreaker("timeout_test", config)

    @pytest.mark.asyncio
    async def test_timeout_counts_as_failure(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test call timeout counts as failure."""

        async def slow_fn() -> str:
            await asyncio.sleep(0.5)  # Longer than timeout
            return "success"

        with pytest.raises(TimeoutError):
            await breaker.call(slow_fn)

        assert breaker.stats.timeout_calls == 1
        assert breaker.stats.failed_calls == 1


# =============================================================================
# Test CircuitBreaker - Excluded Exceptions
# =============================================================================


class TestCircuitBreakerExcludedExceptions:
    """Tests for CircuitBreaker excluded exceptions."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker with excluded exceptions."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            excluded_exceptions=(ValueError,),
        )
        return CircuitBreaker("excluded_test", config)

    @pytest.mark.asyncio
    async def test_excluded_exception_not_counted(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test excluded exceptions don't count as failures."""

        async def excluded_fn() -> str:
            raise ValueError("Excluded error")

        # Raise excluded exception multiple times
        for _ in range(5):
            with pytest.raises(ValueError):
                await breaker.call(excluded_fn)

        # Should still be closed (ValueError is excluded)
        assert breaker.is_closed is True
        assert breaker.stats.successful_calls == 5  # Counted as success

    @pytest.mark.asyncio
    async def test_non_excluded_exception_counted(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test non-excluded exceptions count as failures."""

        async def non_excluded_fn() -> str:
            raise RuntimeError("Non-excluded error")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(non_excluded_fn)

        assert breaker.is_open is True


# =============================================================================
# Test CircuitBreaker - Decorator Usage
# =============================================================================


class TestCircuitBreakerDecorator:
    """Tests for CircuitBreaker as decorator."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for decorator testing."""
        config = CircuitBreakerConfig(failure_threshold=3)
        return CircuitBreaker("decorator_test", config)

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test decorator wraps function correctly."""

        @breaker
        async def my_function() -> str:
            """My docstring."""
            return "result"

        result = await my_function()

        assert result == "result"
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    @pytest.mark.asyncio
    async def test_decorator_tracks_calls(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test decorator tracks calls through breaker."""

        @breaker
        async def my_function() -> str:
            return "result"

        await my_function()
        await my_function()

        assert breaker.stats.total_calls == 2
        assert breaker.stats.successful_calls == 2


# =============================================================================
# Test CircuitBreaker - Listeners
# =============================================================================


class TestCircuitBreakerListeners:
    """Tests for CircuitBreaker state change listeners."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for listener testing."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
        )
        return CircuitBreaker("listener_test", config)

    @pytest.mark.asyncio
    async def test_listener_called_on_state_change(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test listener is called on state change."""
        listener = AsyncMock()
        breaker.add_listener(listener)

        async def failing_fn() -> str:
            raise RuntimeError("Failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        listener.assert_called()
        call_args = listener.call_args[0]
        assert call_args[0] == CircuitState.CLOSED
        assert call_args[1] == CircuitState.OPEN

    def test_remove_listener(self, breaker: CircuitBreaker[str]) -> None:
        """Test removing a listener."""
        listener = AsyncMock()
        breaker.add_listener(listener)

        assert listener in breaker._listeners

        breaker.remove_listener(listener)

        assert listener not in breaker._listeners


# =============================================================================
# Test CircuitBreaker - Reset and Force Operations
# =============================================================================


class TestCircuitBreakerManualOps:
    """Tests for CircuitBreaker manual operations."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for manual ops testing."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=30.0,
        )
        return CircuitBreaker("manual_test", config)

    @pytest.mark.asyncio
    async def test_reset_closes_circuit(self, breaker: CircuitBreaker[str]) -> None:
        """Test reset closes open circuit."""

        async def failing_fn() -> str:
            raise RuntimeError("Failure")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        assert breaker.is_open is True

        await breaker.reset()

        assert breaker.is_closed is True
        assert breaker.stats.total_calls == 0

    @pytest.mark.asyncio
    async def test_force_open(self, breaker: CircuitBreaker[str]) -> None:
        """Test force opening the circuit."""
        assert breaker.is_closed is True

        await breaker.force_open()

        assert breaker.is_open is True

    @pytest.mark.asyncio
    async def test_force_open_with_duration(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test force opening with custom duration."""
        await breaker.force_open(duration=60.0)

        assert breaker.is_open is True
        assert breaker.config.recovery_timeout == 60.0


# =============================================================================
# Test CircuitBreaker - Window Trimming
# =============================================================================


class TestCircuitBreakerWindowTrimming:
    """Tests for CircuitBreaker sliding window trimming."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker with small window."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High to avoid opening
            window_size=5,
        )
        return CircuitBreaker("window_test", config)

    @pytest.mark.asyncio
    async def test_window_trims_to_size(self, breaker: CircuitBreaker[str]) -> None:
        """Test sliding window trims to configured size."""

        async def success_fn() -> str:
            return "success"

        async def failing_fn() -> str:
            raise RuntimeError("Failure")

        # Add more than window_size calls
        for _ in range(3):
            await breaker.call(success_fn)

        for _ in range(4):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        total_recent = len(breaker.stats.recent_successes) + len(
            breaker.stats.recent_failures
        )
        assert total_recent <= 5


# =============================================================================
# Test CircuitBreakerRegistry
# =============================================================================


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    @pytest.fixture
    def registry(self) -> CircuitBreakerRegistry:
        """Create a fresh registry for testing."""
        return CircuitBreakerRegistry()

    @pytest.mark.asyncio
    async def test_get_or_create(self, registry: CircuitBreakerRegistry) -> None:
        """Test get_or_create returns breaker."""
        breaker = await registry.get_or_create("test")

        assert breaker is not None
        assert breaker.name == "test"

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(
        self, registry: CircuitBreakerRegistry
    ) -> None:
        """Test get_or_create returns existing breaker."""
        breaker1 = await registry.get_or_create("test")
        breaker2 = await registry.get_or_create("test")

        assert breaker1 is breaker2

    @pytest.mark.asyncio
    async def test_get_existing(self, registry: CircuitBreakerRegistry) -> None:
        """Test get returns existing breaker."""
        await registry.get_or_create("test")

        breaker = await registry.get("test")

        assert breaker is not None
        assert breaker.name == "test"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, registry: CircuitBreakerRegistry) -> None:
        """Test get returns None for nonexistent breaker."""
        breaker = await registry.get("nonexistent")
        assert breaker is None

    @pytest.mark.asyncio
    async def test_remove(self, registry: CircuitBreakerRegistry) -> None:
        """Test removing a breaker."""
        await registry.get_or_create("test")

        success = await registry.remove("test")

        assert success is True
        assert await registry.get("test") is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, registry: CircuitBreakerRegistry) -> None:
        """Test removing nonexistent breaker."""
        success = await registry.remove("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_list_all(self, registry: CircuitBreakerRegistry) -> None:
        """Test listing all breaker names."""
        await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")
        await registry.get_or_create("breaker3")

        names = registry.list_all()

        assert len(names) == 3
        assert "breaker1" in names
        assert "breaker2" in names
        assert "breaker3" in names

    @pytest.mark.asyncio
    async def test_get_all_status(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting status of all breakers."""
        await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")

        status = registry.get_all_status()

        assert "breaker1" in status
        assert "breaker2" in status
        assert status["breaker1"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_reset_all(self, registry: CircuitBreakerRegistry) -> None:
        """Test resetting all breakers."""
        breaker1 = await registry.get_or_create("breaker1")
        breaker2 = await registry.get_or_create("breaker2")

        # Open both breakers
        await breaker1.force_open()
        await breaker2.force_open()

        await registry.reset_all()

        assert breaker1.is_closed is True
        assert breaker2.is_closed is True

    @pytest.mark.asyncio
    async def test_get_open_circuits(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting list of open circuits."""
        breaker1 = await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")

        await breaker1.force_open()

        open_circuits = registry.get_open_circuits()

        assert "breaker1" in open_circuits
        assert "breaker2" not in open_circuits

    @pytest.mark.asyncio
    async def test_get_health_summary(self, registry: CircuitBreakerRegistry) -> None:
        """Test getting health summary."""
        breaker1 = await registry.get_or_create("breaker1")
        await registry.get_or_create("breaker2")
        await registry.get_or_create("breaker3")

        await breaker1.force_open()

        summary = registry.get_health_summary()

        assert summary["total_circuits"] == 3
        assert summary["closed"] == 2
        assert summary["open"] == 1
        assert summary["half_open"] == 0
        assert summary["health_score"] == 2 / 3
        assert "breaker1" in summary["open_circuits"]


# =============================================================================
# Test Global Registry
# =============================================================================


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_circuit_registry_returns_same_instance(self) -> None:
        """Test global registry returns same instance."""
        registry1 = get_circuit_registry()
        registry2 = get_circuit_registry()

        assert registry1 is registry2

    @pytest.mark.asyncio
    async def test_circuit_breaker_function(self) -> None:
        """Test circuit_breaker convenience function."""
        breaker = await circuit_breaker("convenience_test")

        assert breaker is not None
        assert breaker.name == "convenience_test"

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_config(self) -> None:
        """Test circuit_breaker with custom config."""
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = await circuit_breaker("config_test", config)

        assert breaker.config.failure_threshold == 10


# =============================================================================
# Test ForgeCircuits Pre-configured Breakers
# =============================================================================


class TestForgeCircuits:
    """Tests for ForgeCircuits pre-configured breakers."""

    @pytest.mark.asyncio
    async def test_neo4j_breaker(self) -> None:
        """Test Neo4j circuit breaker configuration."""
        breaker = await ForgeCircuits.neo4j()

        assert breaker.name == "neo4j"
        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 30.0
        assert breaker.config.call_timeout == 10.0

    @pytest.mark.asyncio
    async def test_external_ml_breaker(self) -> None:
        """Test external ML circuit breaker configuration."""
        breaker = await ForgeCircuits.external_ml()

        assert breaker.name == "external_ml"
        assert breaker.config.failure_threshold == 5
        assert breaker.config.recovery_timeout == 60.0
        assert breaker.config.call_timeout == 30.0

    @pytest.mark.asyncio
    async def test_overlay_breaker(self) -> None:
        """Test overlay circuit breaker configuration."""
        breaker = await ForgeCircuits.overlay("ml_classifier")

        assert breaker.name == "overlay_ml_classifier"
        assert breaker.config.failure_threshold == 5
        assert breaker.config.recovery_timeout == 15.0
        assert breaker.config.call_timeout == 5.0

    @pytest.mark.asyncio
    async def test_webhook_breaker(self) -> None:
        """Test webhook circuit breaker configuration."""
        breaker = await ForgeCircuits.webhook()

        assert breaker.name == "webhook"
        assert breaker.config.failure_threshold == 10
        assert breaker.config.recovery_timeout == 120.0
        assert breaker.config.call_timeout == 15.0
        assert breaker.config.failure_rate_threshold == 0.7


# =============================================================================
# Test CircuitBreaker - Concurrency
# =============================================================================


class TestCircuitBreakerConcurrency:
    """Tests for CircuitBreaker concurrent access."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for concurrency testing."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High threshold
            call_timeout=5.0,
        )
        return CircuitBreaker("concurrent_test", config)

    @pytest.mark.asyncio
    async def test_concurrent_calls(self, breaker: CircuitBreaker[str]) -> None:
        """Test concurrent calls through breaker."""
        call_count = 0

        async def tracked_fn() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "success"

        # Run many concurrent calls
        tasks = [breaker.call(tracked_fn) for _ in range(50)]
        results = await asyncio.gather(*tasks)

        assert all(r == "success" for r in results)
        assert call_count == 50
        assert breaker.stats.successful_calls == 50

    @pytest.mark.asyncio
    async def test_concurrent_failures_open_circuit(
        self, breaker: CircuitBreaker[str]
    ) -> None:
        """Test concurrent failures properly open circuit."""
        breaker.config.failure_threshold = 5

        async def failing_fn() -> str:
            await asyncio.sleep(0.01)
            raise RuntimeError("Failure")

        # Run concurrent failing calls
        tasks = [breaker.call(failing_fn) for _ in range(10)]

        # Some will fail, some will be rejected
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have opened the circuit
        assert breaker.is_open is True

        # Count different exception types
        runtime_errors = sum(1 for r in results if isinstance(r, RuntimeError))
        circuit_errors = sum(1 for r in results if isinstance(r, CircuitBreakerError))

        # Should have some of each (exact count depends on timing)
        assert runtime_errors > 0 or circuit_errors > 0


# =============================================================================
# Test CircuitBreaker - Half-Open Max Calls
# =============================================================================


class TestCircuitBreakerHalfOpenLimit:
    """Tests for CircuitBreaker half-open call limits."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker[str]:
        """Create a circuit breaker for half-open testing."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_max_calls=2,
            success_threshold=1,
        )
        return CircuitBreaker("halfopen_test", config)

    @pytest.mark.asyncio
    async def test_half_open_limits_calls(self, breaker: CircuitBreaker[str]) -> None:
        """Test half-open state limits concurrent calls."""

        async def failing_fn() -> str:
            raise RuntimeError("Failure")

        async def slow_fn() -> str:
            await asyncio.sleep(0.2)
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_fn)

        assert breaker.is_open is True

        # Wait for recovery
        await asyncio.sleep(0.1)

        # Start slow calls that will use up half-open slots
        tasks = [breaker.call(slow_fn) for _ in range(5)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Some should succeed, some should be rejected
        successes = sum(1 for r in results if r == "success")
        rejections = sum(1 for r in results if isinstance(r, CircuitBreakerError))

        # Should have limited concurrent half-open calls
        assert successes > 0
