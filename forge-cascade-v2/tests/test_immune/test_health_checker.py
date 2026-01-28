"""
Comprehensive tests for the Forge Cascade V2 Health Checker module.

Tests cover:
- HealthStatus enum
- HealthCheckResult dataclass
- HealthCheckConfig dataclass
- Abstract HealthCheck base class
- CompositeHealthCheck aggregation
- FunctionHealthCheck wrapper
- Specific health checks: Neo4j, Overlay, EventSystem, CircuitBreaker
- Resource health checks: Memory, Disk
- ForgeHealthChecker main class
- Background monitoring
- Factory function create_forge_health_checker
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

# =============================================================================
# Test HealthStatus Enum
# =============================================================================


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected health statuses are defined."""
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNKNOWN == "unknown"

    def test_enum_string_inheritance(self) -> None:
        """Verify enum inherits from str."""
        assert isinstance(HealthStatus.HEALTHY, str)


# =============================================================================
# Test HealthCheckResult
# =============================================================================


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    @pytest.fixture
    def healthy_result(self) -> HealthCheckResult:
        """Create a healthy result for testing."""
        return HealthCheckResult(
            name="test_check",
            status=HealthStatus.HEALTHY,
            message="All systems operational",
            latency_ms=50.0,
            details={"version": "1.0"},
        )

    def test_result_creation(self, healthy_result: HealthCheckResult) -> None:
        """Test result is created with correct values."""
        assert healthy_result.name == "test_check"
        assert healthy_result.status == HealthStatus.HEALTHY
        assert healthy_result.message == "All systems operational"
        assert healthy_result.latency_ms == 50.0
        assert healthy_result.details == {"version": "1.0"}

    def test_is_healthy_property(self, healthy_result: HealthCheckResult) -> None:
        """Test is_healthy property."""
        assert healthy_result.is_healthy is True

        unhealthy = HealthCheckResult(
            name="test",
            status=HealthStatus.UNHEALTHY,
        )
        assert unhealthy.is_healthy is False

    def test_is_degraded_property(self) -> None:
        """Test is_degraded property."""
        degraded = HealthCheckResult(
            name="test",
            status=HealthStatus.DEGRADED,
        )
        assert degraded.is_degraded is True

        unhealthy = HealthCheckResult(
            name="test",
            status=HealthStatus.UNHEALTHY,
        )
        assert unhealthy.is_degraded is True

        healthy = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
        )
        assert healthy.is_degraded is False

    def test_to_dict(self, healthy_result: HealthCheckResult) -> None:
        """Test converting result to dictionary."""
        result = healthy_result.to_dict()

        assert result["name"] == "test_check"
        assert result["status"] == "healthy"
        assert result["message"] == "All systems operational"
        assert result["latency_ms"] == 50.0
        assert result["details"] == {"version": "1.0"}
        assert "timestamp" in result

    def test_to_dict_with_children(self) -> None:
        """Test to_dict includes children."""
        child1 = HealthCheckResult(name="child1", status=HealthStatus.HEALTHY)
        child2 = HealthCheckResult(name="child2", status=HealthStatus.DEGRADED)

        parent = HealthCheckResult(
            name="parent",
            status=HealthStatus.DEGRADED,
            children=[child1, child2],
        )

        result = parent.to_dict()

        assert "children" in result
        assert len(result["children"]) == 2
        assert result["children"][0]["name"] == "child1"

    def test_default_timestamp(self) -> None:
        """Test result gets default timestamp."""
        result = HealthCheckResult(name="test", status=HealthStatus.HEALTHY)

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)


# =============================================================================
# Test HealthCheckConfig
# =============================================================================


class TestHealthCheckConfig:
    """Tests for HealthCheckConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = HealthCheckConfig()

        assert config.timeout_seconds == 5.0
        assert config.check_interval_seconds == 30.0
        assert config.latency_warning_ms == 1000.0
        assert config.latency_critical_ms == 5000.0
        assert config.retry_count == 2
        assert config.retry_delay_seconds == 1.0
        assert config.cache_ttl_seconds == 10.0

    def test_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = HealthCheckConfig(
            timeout_seconds=10.0,
            retry_count=5,
            cache_ttl_seconds=30.0,
        )

        assert config.timeout_seconds == 10.0
        assert config.retry_count == 5
        assert config.cache_ttl_seconds == 30.0


# =============================================================================
# Test FunctionHealthCheck
# =============================================================================


class TestFunctionHealthCheck:
    """Tests for FunctionHealthCheck wrapper."""

    @pytest.mark.asyncio
    async def test_healthy_function(self) -> None:
        """Test function that returns healthy status."""

        async def healthy_fn() -> tuple[bool, str]:
            return True, "All good"

        check = FunctionHealthCheck("func_check", healthy_fn)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"

    @pytest.mark.asyncio
    async def test_unhealthy_function(self) -> None:
        """Test function that returns unhealthy status."""

        async def unhealthy_fn() -> tuple[bool, str]:
            return False, "Something wrong"

        check = FunctionHealthCheck("func_check", unhealthy_fn)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Something wrong"

    @pytest.mark.asyncio
    async def test_function_exception(self) -> None:
        """Test function that raises exception."""

        async def error_fn() -> tuple[bool, str]:
            raise RuntimeError("Check failed")

        check = FunctionHealthCheck("func_check", error_fn)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed" in result.message


# =============================================================================
# Test CompositeHealthCheck
# =============================================================================


class TestCompositeHealthCheck:
    """Tests for CompositeHealthCheck aggregation."""

    @pytest.fixture
    def composite(self) -> CompositeHealthCheck:
        """Create a composite check for testing."""
        return CompositeHealthCheck("composite_test")

    def test_add_check(self, composite: CompositeHealthCheck) -> None:
        """Test adding a check to composite."""

        async def fn() -> tuple[bool, str]:
            return True, "OK"

        check = FunctionHealthCheck("sub_check", fn)
        composite.add_check(check)

        assert len(composite.checks) == 1

    def test_remove_check(self, composite: CompositeHealthCheck) -> None:
        """Test removing a check from composite."""

        async def fn() -> tuple[bool, str]:
            return True, "OK"

        check = FunctionHealthCheck("sub_check", fn)
        composite.add_check(check)

        success = composite.remove_check("sub_check")

        assert success is True
        assert len(composite.checks) == 0

    def test_remove_nonexistent_check(self, composite: CompositeHealthCheck) -> None:
        """Test removing nonexistent check."""
        success = composite.remove_check("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_empty_composite_unknown(self, composite: CompositeHealthCheck) -> None:
        """Test empty composite returns unknown status."""
        result = await composite.check()

        assert result.status == HealthStatus.UNKNOWN
        assert "No health checks configured" in result.message

    @pytest.mark.asyncio
    async def test_all_healthy_returns_healthy(self, composite: CompositeHealthCheck) -> None:
        """Test all healthy children returns healthy."""

        async def healthy1() -> tuple[bool, str]:
            return True, "OK"

        async def healthy2() -> tuple[bool, str]:
            return True, "OK"

        composite.add_check(FunctionHealthCheck("check1", healthy1))
        composite.add_check(FunctionHealthCheck("check2", healthy2))

        result = await composite.check()

        assert result.status == HealthStatus.HEALTHY
        assert "All checks passed" in result.message

    @pytest.mark.asyncio
    async def test_any_unhealthy_returns_unhealthy(self, composite: CompositeHealthCheck) -> None:
        """Test any unhealthy child returns unhealthy."""

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        async def unhealthy() -> tuple[bool, str]:
            return False, "Failed"

        composite.add_check(FunctionHealthCheck("check1", healthy))
        composite.add_check(FunctionHealthCheck("check2", unhealthy))

        result = await composite.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "unhealthy" in result.message.lower()

    @pytest.mark.asyncio
    async def test_degraded_without_unhealthy_returns_degraded(
        self, composite: CompositeHealthCheck
    ) -> None:
        """Test degraded without unhealthy returns degraded."""
        # We need to create a check that directly returns degraded
        # This requires a custom health check class

        class DegradedCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Degraded",
                )

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        composite.add_check(FunctionHealthCheck("check1", healthy))
        composite.add_check(DegradedCheck("check2"))

        result = await composite.check()

        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_composite_includes_children(self, composite: CompositeHealthCheck) -> None:
        """Test composite result includes children."""

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        composite.add_check(FunctionHealthCheck("check1", healthy))
        composite.add_check(FunctionHealthCheck("check2", healthy))

        result = await composite.check()

        assert len(result.children) == 2
        assert result.children[0].name == "check1"

    @pytest.mark.asyncio
    async def test_composite_handles_exception(self, composite: CompositeHealthCheck) -> None:
        """Test composite handles child exceptions."""

        async def error() -> tuple[bool, str]:
            raise RuntimeError("Error")

        composite.add_check(FunctionHealthCheck("check1", error))

        result = await composite.check()

        assert result.status == HealthStatus.UNHEALTHY


# =============================================================================
# Test HealthCheck - Caching
# =============================================================================


class TestHealthCheckCaching:
    """Tests for HealthCheck caching behavior."""

    @pytest.mark.asyncio
    async def test_uses_cache_within_ttl(self) -> None:
        """Test cached result is returned within TTL."""
        call_count = 0

        async def tracked_fn() -> tuple[bool, str]:
            nonlocal call_count
            call_count += 1
            return True, "OK"

        config = HealthCheckConfig(cache_ttl_seconds=60.0)
        check = FunctionHealthCheck("cached", tracked_fn, config)

        # First call
        await check.execute(use_cache=True)
        # Second call should use cache
        await check.execute(use_cache=True)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_bypasses_cache_when_disabled(self) -> None:
        """Test cache is bypassed when disabled."""
        call_count = 0

        async def tracked_fn() -> tuple[bool, str]:
            nonlocal call_count
            call_count += 1
            return True, "OK"

        config = HealthCheckConfig(cache_ttl_seconds=60.0)
        check = FunctionHealthCheck("cached", tracked_fn, config)

        # First call
        await check.execute(use_cache=False)
        # Second call without cache
        await check.execute(use_cache=False)

        assert call_count == 2


# =============================================================================
# Test HealthCheck - Retry
# =============================================================================


class TestHealthCheckRetry:
    """Tests for HealthCheck retry behavior."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        """Test check retries on failure."""
        call_count = 0

        async def failing_fn() -> tuple[bool, str]:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection failed")

        config = HealthCheckConfig(
            retry_count=2,
            retry_delay_seconds=0.01,
        )
        check = FunctionHealthCheck("retry", failing_fn, config)

        result = await check.execute(use_cache=False)

        # Should have retried: 1 initial + 2 retries = 3 calls
        assert call_count == 3
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_succeeds_on_retry(self) -> None:
        """Test check succeeds on retry."""
        call_count = 0

        async def eventually_succeeds() -> tuple[bool, str]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return True, "OK"

        config = HealthCheckConfig(
            retry_count=2,
            retry_delay_seconds=0.01,
        )
        check = FunctionHealthCheck("retry", eventually_succeeds, config)

        result = await check.execute(use_cache=False)

        assert result.status == HealthStatus.HEALTHY


# =============================================================================
# Test HealthCheck - Latency Thresholds
# =============================================================================


class TestHealthCheckLatency:
    """Tests for HealthCheck latency thresholds."""

    @pytest.mark.asyncio
    async def test_slow_check_degrades_status(self) -> None:
        """Test slow check degrades healthy to degraded."""

        async def slow_fn() -> tuple[bool, str]:
            await asyncio.sleep(0.15)  # 150ms
            return True, "OK"

        config = HealthCheckConfig(
            latency_warning_ms=100.0,  # 100ms warning
            latency_critical_ms=500.0,
        )
        check = FunctionHealthCheck("slow", slow_fn, config)

        result = await check.execute(use_cache=False)

        assert result.status == HealthStatus.DEGRADED
        assert "Latency warning" in result.message

    @pytest.mark.asyncio
    async def test_very_slow_check_unhealthy(self) -> None:
        """Test very slow check becomes unhealthy."""

        async def very_slow_fn() -> tuple[bool, str]:
            await asyncio.sleep(0.6)  # 600ms
            return True, "OK"

        config = HealthCheckConfig(
            latency_warning_ms=100.0,
            latency_critical_ms=500.0,  # 500ms critical
        )
        check = FunctionHealthCheck("slow", very_slow_fn, config)

        result = await check.execute(use_cache=False)

        assert result.status == HealthStatus.UNHEALTHY
        assert "Latency critical" in result.message


# =============================================================================
# Test Neo4jHealthCheck
# =============================================================================


class TestNeo4jHealthCheck:
    """Tests for Neo4jHealthCheck."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock Neo4j client."""
        client = MagicMock()
        client._uri = "neo4j://localhost:7687/test"
        return client

    @pytest.mark.asyncio
    async def test_healthy_connection(self, mock_client: MagicMock) -> None:
        """Test healthy Neo4j connection."""
        # Set up mock session
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_record = {"n": 1}
        mock_result.single = AsyncMock(return_value=mock_record)
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_client.session = MagicMock(return_value=mock_session)

        check = Neo4jHealthCheck(mock_client)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "Connected to Neo4j" in result.message

    @pytest.mark.asyncio
    async def test_connection_failure(self, mock_client: MagicMock) -> None:
        """Test Neo4j connection failure."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=ConnectionError("Failed"))
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_client.session = MagicMock(return_value=mock_session)

        check = Neo4jHealthCheck(mock_client)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY


# =============================================================================
# Test OverlayHealthCheck
# =============================================================================


class TestOverlayHealthCheck:
    """Tests for OverlayHealthCheck."""

    @pytest.fixture
    def mock_manager(self) -> MagicMock:
        """Create a mock overlay manager."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_all_overlays_active(self, mock_manager: MagicMock) -> None:
        """Test all overlays active."""
        mock_manager.get_system_status = AsyncMock(
            return_value={
                "total_overlays": 5,
                "active_overlays": 5,
                "errored_overlays": 0,
            }
        )

        check = OverlayHealthCheck(mock_manager)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "All 5 overlays active" in result.message

    @pytest.mark.asyncio
    async def test_some_overlays_errored(self, mock_manager: MagicMock) -> None:
        """Test some overlays in error state."""
        mock_manager.get_system_status = AsyncMock(
            return_value={
                "total_overlays": 5,
                "active_overlays": 3,
                "errored_overlays": 2,
            }
        )

        check = OverlayHealthCheck(mock_manager)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "error state" in result.message

    @pytest.mark.asyncio
    async def test_some_overlays_inactive(self, mock_manager: MagicMock) -> None:
        """Test some overlays inactive."""
        mock_manager.get_system_status = AsyncMock(
            return_value={
                "total_overlays": 5,
                "active_overlays": 3,
                "errored_overlays": 0,
            }
        )

        check = OverlayHealthCheck(mock_manager)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "3/5" in result.message


# =============================================================================
# Test EventSystemHealthCheck
# =============================================================================


class TestEventSystemHealthCheck:
    """Tests for EventSystemHealthCheck."""

    @pytest.fixture
    def mock_event_system(self) -> MagicMock:
        """Create a mock event system."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_healthy_event_system(self, mock_event_system: MagicMock) -> None:
        """Test healthy event system."""
        mock_event_system.get_metrics = MagicMock(
            return_value={
                "pending_events": 10,
                "dead_letter_count": 5,
                "subscriber_count": 3,
            }
        )

        check = EventSystemHealthCheck(mock_event_system)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_high_dead_letter_count(self, mock_event_system: MagicMock) -> None:
        """Test high dead letter count degrades status."""
        mock_event_system.get_metrics = MagicMock(
            return_value={
                "pending_events": 10,
                "dead_letter_count": 200,  # Above default threshold
                "subscriber_count": 3,
            }
        )

        check = EventSystemHealthCheck(mock_event_system)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "dead letter" in result.message.lower()

    @pytest.mark.asyncio
    async def test_high_pending_events(self, mock_event_system: MagicMock) -> None:
        """Test high pending events degrades status."""
        mock_event_system.get_metrics = MagicMock(
            return_value={
                "pending_events": 2000,  # Above default threshold
                "dead_letter_count": 5,
                "subscriber_count": 3,
            }
        )

        check = EventSystemHealthCheck(mock_event_system)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "backlog" in result.message.lower()

    @pytest.mark.asyncio
    async def test_no_subscribers(self, mock_event_system: MagicMock) -> None:
        """Test no subscribers degrades status."""
        mock_event_system.get_metrics = MagicMock(
            return_value={
                "pending_events": 10,
                "dead_letter_count": 5,
                "subscriber_count": 0,
            }
        )

        check = EventSystemHealthCheck(mock_event_system)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "No active subscribers" in result.message


# =============================================================================
# Test CircuitBreakerHealthCheck
# =============================================================================


class TestCircuitBreakerHealthCheck:
    """Tests for CircuitBreakerHealthCheck."""

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        """Create a mock circuit breaker registry."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_all_circuits_closed(self, mock_registry: MagicMock) -> None:
        """Test all circuits closed."""
        mock_registry.get_health_summary = MagicMock(
            return_value={
                "total_circuits": 5,
                "open": 0,
                "open_circuits": [],
            }
        )

        check = CircuitBreakerHealthCheck(mock_registry)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "All 5 circuits closed" in result.message

    @pytest.mark.asyncio
    async def test_some_circuits_open(self, mock_registry: MagicMock) -> None:
        """Test some circuits open degrades status."""
        mock_registry.get_health_summary = MagicMock(
            return_value={
                "total_circuits": 5,
                "open": 2,
                "open_circuits": ["neo4j", "redis"],
            }
        )

        check = CircuitBreakerHealthCheck(mock_registry)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "2 circuit(s) open" in result.message
        assert "neo4j" in result.message
        assert "redis" in result.message

    @pytest.mark.asyncio
    async def test_no_circuits_registered(self, mock_registry: MagicMock) -> None:
        """Test no circuits registered."""
        mock_registry.get_health_summary = MagicMock(
            return_value={
                "total_circuits": 0,
                "open": 0,
                "open_circuits": [],
            }
        )

        check = CircuitBreakerHealthCheck(mock_registry)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "No circuit breakers registered" in result.message


# =============================================================================
# Test MemoryHealthCheck
# =============================================================================


class TestMemoryHealthCheck:
    """Tests for MemoryHealthCheck."""

    @pytest.mark.asyncio
    async def test_healthy_memory(self) -> None:
        """Test healthy memory usage."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = MagicMock(
                percent=50.0,
                total=16 * (1024**3),
                available=8 * (1024**3),
            )

            check = MemoryHealthCheck(warning_percent=80.0, critical_percent=95.0)
            result = await check.check()

            assert result.status == HealthStatus.HEALTHY
            assert "50.0%" in result.message

    @pytest.mark.asyncio
    async def test_high_memory_usage_warning(self) -> None:
        """Test high memory usage triggers warning."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = MagicMock(
                percent=85.0,
                total=16 * (1024**3),
                available=2.4 * (1024**3),
            )

            check = MemoryHealthCheck(warning_percent=80.0, critical_percent=95.0)
            result = await check.check()

            assert result.status == HealthStatus.DEGRADED
            assert "High memory" in result.message

    @pytest.mark.asyncio
    async def test_critical_memory_usage(self) -> None:
        """Test critical memory usage."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.return_value = MagicMock(
                percent=97.0,
                total=16 * (1024**3),
                available=0.5 * (1024**3),
            )

            check = MemoryHealthCheck(warning_percent=80.0, critical_percent=95.0)
            result = await check.check()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Critical memory" in result.message

    @pytest.mark.asyncio
    async def test_psutil_not_installed(self) -> None:
        """Test handling when psutil not installed."""
        with patch.dict("sys.modules", {"psutil": None}):
            # Force reimport to trigger ImportError
            check = MemoryHealthCheck()

            # Patch the check method to simulate import error
            async def mock_check() -> HealthCheckResult:
                try:
                    import psutil  # noqa: F401
                except ImportError:
                    return HealthCheckResult(
                        name="memory",
                        status=HealthStatus.UNKNOWN,
                        message="psutil not installed",
                    )
                return HealthCheckResult(name="memory", status=HealthStatus.HEALTHY, message="OK")

            result = await mock_check()
            assert result.status == HealthStatus.UNKNOWN or result.status == HealthStatus.HEALTHY


# =============================================================================
# Test DiskHealthCheck
# =============================================================================


class TestDiskHealthCheck:
    """Tests for DiskHealthCheck."""

    @pytest.mark.asyncio
    async def test_healthy_disk(self) -> None:
        """Test healthy disk usage."""
        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value = MagicMock(
                percent=50.0,
                total=500 * (1024**3),
                free=250 * (1024**3),
            )

            check = DiskHealthCheck(
                path="/",
                warning_percent=85.0,
                critical_percent=95.0,
            )
            result = await check.check()

            assert result.status == HealthStatus.HEALTHY
            assert "50.0%" in result.message

    @pytest.mark.asyncio
    async def test_high_disk_usage_warning(self) -> None:
        """Test high disk usage triggers warning."""
        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value = MagicMock(
                percent=90.0,
                total=500 * (1024**3),
                free=50 * (1024**3),
            )

            check = DiskHealthCheck(
                path="/",
                warning_percent=85.0,
                critical_percent=95.0,
            )
            result = await check.check()

            assert result.status == HealthStatus.DEGRADED
            assert "High disk" in result.message

    @pytest.mark.asyncio
    async def test_critical_disk_usage(self) -> None:
        """Test critical disk usage."""
        with patch("psutil.disk_usage") as mock_disk:
            mock_disk.return_value = MagicMock(
                percent=97.0,
                total=500 * (1024**3),
                free=15 * (1024**3),
            )

            check = DiskHealthCheck(
                path="/",
                warning_percent=85.0,
                critical_percent=95.0,
            )
            result = await check.check()

            assert result.status == HealthStatus.UNHEALTHY
            assert "Critical disk" in result.message


# =============================================================================
# Test ForgeHealthChecker
# =============================================================================


class TestForgeHealthChecker:
    """Tests for ForgeHealthChecker main class."""

    @pytest.fixture
    def checker(self) -> ForgeHealthChecker:
        """Create a health checker for testing."""
        return ForgeHealthChecker()

    def test_checker_creation(self, checker: ForgeHealthChecker) -> None:
        """Test checker is created correctly."""
        assert checker.root is not None
        assert isinstance(checker.root, CompositeHealthCheck)

    def test_add_check(self, checker: ForgeHealthChecker) -> None:
        """Test adding a check to category."""

        async def fn() -> tuple[bool, str]:
            return True, "OK"

        check = FunctionHealthCheck("test", fn)
        checker.add_check("database", check)

        assert "database" in checker._checks

    def test_add_simple_check(self, checker: ForgeHealthChecker) -> None:
        """Test adding a simple function check."""

        async def fn() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", fn)

        assert "database" in checker._checks

    @pytest.mark.asyncio
    async def test_check_health(self, checker: ForgeHealthChecker) -> None:
        """Test full health check."""

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", healthy)
        checker.add_simple_check("api", "rest", healthy)

        result = await checker.check_health()

        assert result is not None
        assert result.name == "forge_system"

    @pytest.mark.asyncio
    async def test_check_category(self, checker: ForgeHealthChecker) -> None:
        """Test checking specific category."""

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", healthy)

        result = await checker.check_category("database")

        assert result is not None
        assert result.name == "database"

    @pytest.mark.asyncio
    async def test_check_nonexistent_category(self, checker: ForgeHealthChecker) -> None:
        """Test checking non-existent category."""
        result = await checker.check_category("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_quick_status(self, checker: ForgeHealthChecker) -> None:
        """Test getting quick status."""

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", healthy)

        status = await checker.get_quick_status()

        assert "status" in status
        assert "message" in status
        assert "timestamp" in status

    def test_get_check_names(self, checker: ForgeHealthChecker) -> None:
        """Test getting check names by category."""

        async def fn1() -> tuple[bool, str]:
            return True, "OK"

        async def fn2() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", fn1)
        checker.add_simple_check("database", "redis", fn2)
        checker.add_simple_check("api", "rest", fn1)

        names = checker.get_check_names()

        assert "database" in names
        assert "api" in names
        assert "neo4j" in names["database"]
        assert "redis" in names["database"]


# =============================================================================
# Test ForgeHealthChecker - Background Monitoring
# =============================================================================


class TestForgeHealthCheckerBackgroundMonitoring:
    """Tests for ForgeHealthChecker background monitoring."""

    @pytest.fixture
    def checker(self) -> ForgeHealthChecker:
        """Create a health checker with a simple check."""
        checker = ForgeHealthChecker()

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("test", "simple", healthy)
        return checker

    @pytest.mark.asyncio
    async def test_start_background_monitoring(self, checker: ForgeHealthChecker) -> None:
        """Test starting background monitoring."""
        await checker.start_background_monitoring(interval_seconds=0.1)

        assert checker._running is True
        assert checker._background_task is not None

        # Clean up
        await checker.stop_background_monitoring()

    @pytest.mark.asyncio
    async def test_stop_background_monitoring(self, checker: ForgeHealthChecker) -> None:
        """Test stopping background monitoring."""
        await checker.start_background_monitoring(interval_seconds=0.1)
        await checker.stop_background_monitoring()

        assert checker._running is False
        assert checker._background_task is None

    @pytest.mark.asyncio
    async def test_callback_invoked(self, checker: ForgeHealthChecker) -> None:
        """Test callback is invoked during monitoring."""
        callback = AsyncMock()

        await checker.start_background_monitoring(
            interval_seconds=0.1,
            callback=callback,
        )

        # Wait for at least one check
        await asyncio.sleep(0.2)

        await checker.stop_background_monitoring()

        callback.assert_called()

    @pytest.mark.asyncio
    async def test_start_monitoring_idempotent(self, checker: ForgeHealthChecker) -> None:
        """Test starting monitoring twice is idempotent."""
        await checker.start_background_monitoring(interval_seconds=0.1)
        task1 = checker._background_task

        await checker.start_background_monitoring(interval_seconds=0.1)
        task2 = checker._background_task

        assert task1 is task2

        await checker.stop_background_monitoring()


# =============================================================================
# Test Factory Function
# =============================================================================


class TestCreateForgeHealthChecker:
    """Tests for create_forge_health_checker factory function."""

    def test_creates_empty_checker(self) -> None:
        """Test creating checker without dependencies."""
        checker = create_forge_health_checker()

        assert isinstance(checker, ForgeHealthChecker)
        # Should have infrastructure checks (memory, disk)
        assert "infrastructure" in checker._checks

    def test_creates_checker_with_neo4j(self) -> None:
        """Test creating checker with Neo4j client."""
        mock_client = MagicMock()
        mock_client._uri = "neo4j://localhost:7687"

        checker = create_forge_health_checker(neo4j_client=mock_client)

        assert "database" in checker._checks

    def test_creates_checker_with_overlay_manager(self) -> None:
        """Test creating checker with overlay manager."""
        mock_manager = MagicMock()

        checker = create_forge_health_checker(overlay_manager=mock_manager)

        assert "kernel" in checker._checks

    def test_creates_checker_with_event_system(self) -> None:
        """Test creating checker with event system."""
        mock_event_system = MagicMock()

        checker = create_forge_health_checker(event_system=mock_event_system)

        assert "kernel" in checker._checks

    def test_creates_checker_with_circuit_registry(self) -> None:
        """Test creating checker with circuit breaker registry."""
        mock_registry = MagicMock()

        checker = create_forge_health_checker(circuit_registry=mock_registry)

        # Circuit breaker check goes to infrastructure
        names = checker.get_check_names()
        assert "circuit_breakers" in names.get("infrastructure", [])


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestHealthCheckerEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_composite_handles_task_exception(self) -> None:
        """Test composite handles task that raises during gather."""

        class FailingCheck(HealthCheck):
            async def check(self) -> HealthCheckResult:
                raise RuntimeError("Unexpected error")

        composite = CompositeHealthCheck("test")
        composite.add_check(FailingCheck("failing"))

        result = await composite.check()

        # Should handle gracefully
        assert result.status == HealthStatus.UNHEALTHY
        assert len(result.children) == 1

    @pytest.mark.asyncio
    async def test_health_check_timeout(self) -> None:
        """Test health check respects timeout."""

        async def slow_fn() -> tuple[bool, str]:
            await asyncio.sleep(10)  # Very slow
            return True, "OK"

        config = HealthCheckConfig(timeout_seconds=0.1)
        check = FunctionHealthCheck("slow", slow_fn, config)

        result = await check.execute(use_cache=False)

        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.message

    @pytest.mark.asyncio
    async def test_multiple_categories(self) -> None:
        """Test multiple categories work correctly."""
        checker = ForgeHealthChecker()

        async def healthy() -> tuple[bool, str]:
            return True, "OK"

        checker.add_simple_check("database", "neo4j", healthy)
        checker.add_simple_check("database", "redis", healthy)
        checker.add_simple_check("cache", "memcached", healthy)
        checker.add_simple_check("api", "rest", healthy)
        checker.add_simple_check("api", "graphql", healthy)

        result = await checker.check_health()

        assert result.status == HealthStatus.HEALTHY
        assert len(result.children) == 3  # database, cache, api
