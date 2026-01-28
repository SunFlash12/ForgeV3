"""
Comprehensive tests for the WebAssembly Overlay Runtime.

Tests cover:
- Capability enum and FuelBudget
- OverlayManifest creation and serialization
- ExecutionMetrics tracking
- Host functions (logging, database, events)
- Security mode validation
- WasmInstance lifecycle
- WasmOverlayRuntime operations
- Security enforcement
- Cypher query validation
- Global instance management
"""

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

import pytest

from forge.kernel.wasm_runtime import (
    Capability,
    DatabaseReadHostFunction,
    DatabaseWriteHostFunction,
    EventPublishHostFunction,
    ExecutionMetrics,
    ExecutionState,
    FuelBudget,
    HostFunction,
    LogHostFunction,
    OverlayManifest,
    OverlaySecurityMode,
    SecurityError,
    WasmInstance,
    WasmOverlayRuntime,
    _validate_cypher_query,
    get_wasm_runtime,
    init_wasm_runtime,
    shutdown_wasm_runtime,
)


# =============================================================================
# Capability Tests
# =============================================================================


class TestCapability:
    """Tests for Capability enum."""

    def test_capability_values(self) -> None:
        """Test capability enum values."""
        assert Capability.NETWORK_ACCESS.value == "network_access"
        assert Capability.DATABASE_READ.value == "database_read"
        assert Capability.DATABASE_WRITE.value == "database_write"
        assert Capability.EVENT_PUBLISH.value == "event_publish"
        assert Capability.LLM_ACCESS.value == "llm_access"

    def test_capability_membership(self) -> None:
        """Test capability set membership."""
        caps = {Capability.DATABASE_READ, Capability.DATABASE_WRITE}

        assert Capability.DATABASE_READ in caps
        assert Capability.NETWORK_ACCESS not in caps


# =============================================================================
# FuelBudget Tests
# =============================================================================


class TestFuelBudget:
    """Tests for FuelBudget dataclass."""

    def test_default_values(self) -> None:
        """Test default fuel budget values."""
        budget = FuelBudget()

        assert budget.total_fuel == 10_000_000
        assert budget.consumed_fuel == 0
        assert budget.memory_limit_mb == 256
        assert budget.timeout_seconds == 30.0

    def test_remaining_fuel(self) -> None:
        """Test remaining fuel calculation."""
        budget = FuelBudget(total_fuel=1000, consumed_fuel=300)

        assert budget.remaining_fuel == 700

    def test_remaining_fuel_minimum_zero(self) -> None:
        """Test remaining fuel doesn't go negative."""
        budget = FuelBudget(total_fuel=100, consumed_fuel=200)

        assert budget.remaining_fuel == 0

    def test_fuel_percentage(self) -> None:
        """Test fuel percentage calculation."""
        budget = FuelBudget(total_fuel=1000, consumed_fuel=250)

        assert budget.fuel_percentage == 25.0

    def test_fuel_percentage_zero_total(self) -> None:
        """Test fuel percentage with zero total."""
        budget = FuelBudget(total_fuel=0)

        assert budget.fuel_percentage == 0

    def test_consume_fuel_success(self) -> None:
        """Test successful fuel consumption."""
        budget = FuelBudget(total_fuel=1000)

        result = budget.consume(300)

        assert result is True
        assert budget.consumed_fuel == 300

    def test_consume_fuel_insufficient(self) -> None:
        """Test fuel consumption with insufficient fuel."""
        budget = FuelBudget(total_fuel=100)

        result = budget.consume(200)

        assert result is False
        assert budget.consumed_fuel == 0

    def test_is_exhausted(self) -> None:
        """Test fuel exhaustion check."""
        budget = FuelBudget(total_fuel=100, consumed_fuel=100)

        assert budget.is_exhausted() is True

    def test_is_not_exhausted(self) -> None:
        """Test fuel not exhausted."""
        budget = FuelBudget(total_fuel=100, consumed_fuel=50)

        assert budget.is_exhausted() is False


# =============================================================================
# OverlayManifest Tests
# =============================================================================


class TestOverlayManifest:
    """Tests for OverlayManifest dataclass."""

    def test_default_manifest(self) -> None:
        """Test default manifest values."""
        manifest = OverlayManifest(
            id="test-overlay",
            name="Test Overlay",
            version="1.0.0",
        )

        assert manifest.description == ""
        assert manifest.capabilities == set()
        assert manifest.dependencies == []
        assert manifest.trust_required == 60
        assert manifest.security_mode == OverlaySecurityMode.WASM_STRICT
        assert manifest.is_internal_trusted is False

    def test_manifest_with_capabilities(self) -> None:
        """Test manifest with capabilities."""
        manifest = OverlayManifest(
            id="test-overlay",
            name="Test Overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ, Capability.EVENT_PUBLISH},
        )

        assert Capability.DATABASE_READ in manifest.capabilities
        assert Capability.EVENT_PUBLISH in manifest.capabilities

    def test_manifest_to_dict(self) -> None:
        """Test manifest serialization to dict."""
        manifest = OverlayManifest(
            id="test-overlay",
            name="Test Overlay",
            version="1.0.0",
            description="A test overlay",
            capabilities={Capability.DATABASE_READ},
        )

        data = manifest.to_dict()

        assert data["id"] == "test-overlay"
        assert data["name"] == "Test Overlay"
        assert data["version"] == "1.0.0"
        assert "database_read" in data["capabilities"]

    def test_manifest_fuel_budgets(self) -> None:
        """Test manifest fuel budgets."""
        manifest = OverlayManifest(
            id="test",
            name="Test",
            version="1.0.0",
        )

        assert "initialize" in manifest.fuel_budgets
        assert "run" in manifest.fuel_budgets
        assert "health_check" in manifest.fuel_budgets


# =============================================================================
# ExecutionMetrics Tests
# =============================================================================


class TestExecutionMetrics:
    """Tests for ExecutionMetrics dataclass."""

    def test_default_metrics(self) -> None:
        """Test default metric values."""
        metrics = ExecutionMetrics()

        assert metrics.invocations == 0
        assert metrics.total_fuel_consumed == 0
        assert metrics.errors == 0
        assert metrics.last_invocation is None

    def test_record_invocation_success(self) -> None:
        """Test recording successful invocation."""
        metrics = ExecutionMetrics()

        metrics.record_invocation(
            function="run",
            fuel_consumed=1000,
            execution_time_ms=50.0,
            success=True,
        )

        assert metrics.invocations == 1
        assert metrics.total_fuel_consumed == 1000
        assert metrics.total_execution_time_ms == 50.0
        assert metrics.errors == 0
        assert metrics.last_invocation is not None

    def test_record_invocation_failure(self) -> None:
        """Test recording failed invocation."""
        metrics = ExecutionMetrics()

        metrics.record_invocation(
            function="run",
            fuel_consumed=500,
            execution_time_ms=20.0,
            success=False,
        )

        assert metrics.invocations == 1
        assert metrics.errors == 1

    def test_function_metrics_tracking(self) -> None:
        """Test per-function metrics tracking."""
        metrics = ExecutionMetrics()

        metrics.record_invocation("run", 100, 10.0, True)
        metrics.record_invocation("run", 150, 15.0, True)
        metrics.record_invocation("health_check", 50, 5.0, True)

        assert metrics.function_metrics["run"]["invocations"] == 2
        assert metrics.function_metrics["run"]["total_fuel"] == 250
        assert metrics.function_metrics["health_check"]["invocations"] == 1

    def test_metrics_to_dict(self) -> None:
        """Test metrics serialization."""
        metrics = ExecutionMetrics()
        metrics.record_invocation("run", 100, 10.0, True)

        data = metrics.to_dict()

        assert data["invocations"] == 1
        assert data["total_fuel_consumed"] == 100
        assert "avg_fuel_per_invocation" in data
        assert "error_rate" in data


# =============================================================================
# Host Function Tests
# =============================================================================


class TestLogHostFunction:
    """Tests for LogHostFunction."""

    @pytest.mark.asyncio
    async def test_log_debug(self) -> None:
        """Test debug logging."""
        log_func = LogHostFunction("test-overlay")

        # Should not raise
        await log_func(0, "Debug message")

    @pytest.mark.asyncio
    async def test_log_info(self) -> None:
        """Test info logging."""
        log_func = LogHostFunction("test-overlay")

        await log_func(1, "Info message")

    @pytest.mark.asyncio
    async def test_log_warning(self) -> None:
        """Test warning logging."""
        log_func = LogHostFunction("test-overlay")

        await log_func(2, "Warning message")

    @pytest.mark.asyncio
    async def test_log_error(self) -> None:
        """Test error logging."""
        log_func = LogHostFunction("test-overlay")

        await log_func(3, "Error message")

    @pytest.mark.asyncio
    async def test_log_unknown_level(self) -> None:
        """Test logging with unknown level defaults to info."""
        log_func = LogHostFunction("test-overlay")

        await log_func(99, "Unknown level message")


class TestDatabaseReadHostFunction:
    """Tests for DatabaseReadHostFunction."""

    @pytest.mark.asyncio
    async def test_execute_read_query(self) -> None:
        """Test executing a read query."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=[{"id": "1", "name": "test"}])

        db_func = DatabaseReadHostFunction(mock_db)

        result = await db_func("MATCH (n) RETURN n", {"limit": 10})

        assert result == [{"id": "1", "name": "test"}]
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_write_query(self) -> None:
        """Test rejecting write queries."""
        mock_db = AsyncMock()
        db_func = DatabaseReadHostFunction(mock_db)

        with pytest.raises(PermissionError, match="Write operations not allowed"):
            await db_func("CREATE (n:Node {name: 'test'})")

    @pytest.mark.asyncio
    async def test_reject_merge_query(self) -> None:
        """Test rejecting MERGE queries."""
        mock_db = AsyncMock()
        db_func = DatabaseReadHostFunction(mock_db)

        with pytest.raises(PermissionError):
            await db_func("MERGE (n:Node {id: 1})")

    @pytest.mark.asyncio
    async def test_reject_delete_query(self) -> None:
        """Test rejecting DELETE queries."""
        mock_db = AsyncMock()
        db_func = DatabaseReadHostFunction(mock_db)

        with pytest.raises(PermissionError):
            await db_func("MATCH (n) DELETE n")


class TestDatabaseWriteHostFunction:
    """Tests for DatabaseWriteHostFunction."""

    @pytest.mark.asyncio
    async def test_execute_write_query(self) -> None:
        """Test executing a write query."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=[])

        db_func = DatabaseWriteHostFunction(mock_db)

        result = await db_func("CREATE (n:Node {name: 'test'})")

        mock_db.execute.assert_called_once()


class TestEventPublishHostFunction:
    """Tests for EventPublishHostFunction."""

    @pytest.mark.asyncio
    async def test_publish_event(self) -> None:
        """Test publishing an event."""
        mock_bus = AsyncMock()
        mock_bus.publish = AsyncMock()

        event_func = EventPublishHostFunction(mock_bus, "test-overlay")

        await event_func("CAPSULE_CREATED", {"capsule_id": "123"})

        mock_bus.publish.assert_called_once()


# =============================================================================
# Cypher Query Validation Tests
# =============================================================================


class TestCypherQueryValidation:
    """Tests for Cypher query validation."""

    def test_valid_query(self) -> None:
        """Test valid query passes validation."""
        _validate_cypher_query("MATCH (n) RETURN n")

    def test_reject_multiple_statements(self) -> None:
        """Test rejecting multiple statements."""
        with pytest.raises(ValueError, match="Multiple statements"):
            _validate_cypher_query("MATCH (n) RETURN n; DROP DATABASE")

    def test_reject_call_statement(self) -> None:
        """Test rejecting non-APOC CALL statements."""
        with pytest.raises(ValueError, match="CALL statements"):
            _validate_cypher_query("CALL db.labels()")

    def test_allow_apoc_call(self) -> None:
        """Test allowing APOC CALL statements."""
        _validate_cypher_query("CALL apoc.help('text')")

    def test_reject_load_csv(self) -> None:
        """Test rejecting LOAD CSV."""
        with pytest.raises(ValueError, match="LOAD CSV"):
            _validate_cypher_query("LOAD CSV FROM 'file.csv' AS row")

    def test_reject_periodic_commit(self) -> None:
        """Test rejecting PERIODIC COMMIT."""
        with pytest.raises(ValueError, match="PERIODIC COMMIT"):
            _validate_cypher_query("USING PERIODIC COMMIT 1000")

    def test_reject_query_hints(self) -> None:
        """Test rejecting query hints."""
        with pytest.raises(ValueError, match="Query hints"):
            _validate_cypher_query("MATCH (n) USING INDEX n:Label(id)")


# =============================================================================
# WasmInstance Tests
# =============================================================================


class TestWasmInstance:
    """Tests for WasmInstance dataclass."""

    def test_default_instance(self) -> None:
        """Test default instance values."""
        manifest = OverlayManifest(id="test", name="Test", version="1.0.0")
        instance = WasmInstance(id="inst-1", manifest=manifest)

        assert instance.state == ExecutionState.INITIALIZING
        assert instance._terminated is False

    def test_is_active_ready(self) -> None:
        """Test is_active when ready."""
        manifest = OverlayManifest(id="test", name="Test", version="1.0.0")
        instance = WasmInstance(
            id="inst-1",
            manifest=manifest,
            state=ExecutionState.READY,
        )

        assert instance.is_active() is True

    def test_is_active_running(self) -> None:
        """Test is_active when running."""
        manifest = OverlayManifest(id="test", name="Test", version="1.0.0")
        instance = WasmInstance(
            id="inst-1",
            manifest=manifest,
            state=ExecutionState.RUNNING,
        )

        assert instance.is_active() is True

    def test_is_not_active_terminated(self) -> None:
        """Test is_active when terminated."""
        manifest = OverlayManifest(id="test", name="Test", version="1.0.0")
        instance = WasmInstance(
            id="inst-1",
            manifest=manifest,
            state=ExecutionState.READY,
            _terminated=True,
        )

        assert instance.is_active() is False

    def test_is_not_active_fuel_exhausted(self) -> None:
        """Test is_active when fuel exhausted."""
        manifest = OverlayManifest(id="test", name="Test", version="1.0.0")
        instance = WasmInstance(
            id="inst-1",
            manifest=manifest,
            state=ExecutionState.READY,
            fuel_budget=FuelBudget(total_fuel=100, consumed_fuel=100),
        )

        assert instance.is_active() is False

    def test_has_capability(self) -> None:
        """Test capability checking."""
        manifest = OverlayManifest(
            id="test",
            name="Test",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
        )
        instance = WasmInstance(id="inst-1", manifest=manifest)

        assert instance.has_capability(Capability.DATABASE_READ) is True
        assert instance.has_capability(Capability.DATABASE_WRITE) is False


# =============================================================================
# WasmOverlayRuntime Tests
# =============================================================================


class TestWasmOverlayRuntime:
    """Tests for WasmOverlayRuntime."""

    @pytest.fixture
    def runtime(self) -> WasmOverlayRuntime:
        """Create a fresh runtime."""
        return WasmOverlayRuntime()

    @pytest.fixture
    def trusted_manifest(self) -> OverlayManifest:
        """Create a trusted Python manifest."""
        return OverlayManifest(
            id="trusted-overlay",
            name="Trusted Overlay",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
            capabilities={Capability.DATABASE_READ},
        )

    @pytest.fixture
    def mock_python_overlay(self) -> MagicMock:
        """Create a mock Python overlay."""
        overlay = MagicMock()
        overlay.run = AsyncMock(return_value={"success": True})
        return overlay

    # -------------------------------------------------------------------------
    # Loading Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_load_overlay_trusted(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test loading a trusted Python overlay."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        assert instance_id is not None
        assert instance_id in runtime._instances

    @pytest.mark.asyncio
    async def test_load_overlay_untrusted_fails(
        self,
        runtime: WasmOverlayRuntime,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test loading untrusted Python overlay fails."""
        manifest = OverlayManifest(
            id="untrusted",
            name="Untrusted",
            version="1.0.0",
            security_mode=OverlaySecurityMode.WASM_STRICT,  # Wrong mode
            is_internal_trusted=False,
        )

        with pytest.raises(SecurityError, match="PYTHON_TRUSTED"):
            await runtime.load_overlay(manifest, mock_python_overlay)

    @pytest.mark.asyncio
    async def test_load_overlay_not_internal_trusted_fails(
        self,
        runtime: WasmOverlayRuntime,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test loading non-internal-trusted overlay fails."""
        manifest = OverlayManifest(
            id="external",
            name="External",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=False,  # Not trusted
        )

        with pytest.raises(SecurityError, match="is_internal_trusted"):
            await runtime.load_overlay(manifest, mock_python_overlay)

    @pytest.mark.asyncio
    async def test_load_overlay_creates_host_functions(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test that loading creates host functions."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        instance = runtime.get_instance(instance_id)
        assert "log" in instance.host_functions  # Always available

    @pytest.mark.asyncio
    async def test_load_overlay_with_db_capability(
        self,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test loading overlay with database capability."""
        mock_db = AsyncMock()
        runtime = WasmOverlayRuntime(db_client=mock_db)

        manifest = OverlayManifest(
            id="db-overlay",
            name="DB Overlay",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
            capabilities={Capability.DATABASE_READ},
        )

        instance_id = await runtime.load_overlay(manifest, mock_python_overlay)

        instance = runtime.get_instance(instance_id)
        assert "db_read" in instance.host_functions

    @pytest.mark.asyncio
    async def test_load_overlay_with_event_capability(
        self,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test loading overlay with event capability."""
        mock_bus = AsyncMock()
        runtime = WasmOverlayRuntime(event_bus=mock_bus)

        manifest = OverlayManifest(
            id="event-overlay",
            name="Event Overlay",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
            capabilities={Capability.EVENT_PUBLISH},
        )

        instance_id = await runtime.load_overlay(manifest, mock_python_overlay)

        instance = runtime.get_instance(instance_id)
        assert "event_publish" in instance.host_functions

    @pytest.mark.asyncio
    async def test_load_overlay_verifies_wasm_hash(self) -> None:
        """Test that WASM hash is verified when provided."""
        runtime = WasmOverlayRuntime()

        # Create a temporary WASM-like file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wasm") as f:
            f.write(b"fake wasm content")
            wasm_path = Path(f.name)

        correct_hash = hashlib.sha256(b"fake wasm content").hexdigest()

        manifest = OverlayManifest(
            id="wasm-overlay",
            name="WASM Overlay",
            version="1.0.0",
            wasm_path=wasm_path,
            source_hash=correct_hash,
        )

        # Should succeed with correct hash
        instance_id = await runtime.load_overlay(manifest, None)
        assert instance_id is not None

        # Cleanup
        wasm_path.unlink()

    @pytest.mark.asyncio
    async def test_load_overlay_fails_on_hash_mismatch(self) -> None:
        """Test that hash mismatch fails loading."""
        runtime = WasmOverlayRuntime()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wasm") as f:
            f.write(b"fake wasm content")
            wasm_path = Path(f.name)

        manifest = OverlayManifest(
            id="wasm-overlay",
            name="WASM Overlay",
            version="1.0.0",
            wasm_path=wasm_path,
            source_hash="wrong_hash",
        )

        with pytest.raises(SecurityError, match="integrity check failed"):
            await runtime.load_overlay(manifest, None)

        wasm_path.unlink()

    # -------------------------------------------------------------------------
    # Execution Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_execute_function(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
    ) -> None:
        """Test executing a function on an overlay."""
        mock_overlay = MagicMock()
        mock_overlay.run = AsyncMock(return_value={"result": "success"})

        instance_id = await runtime.load_overlay(trusted_manifest, mock_overlay)

        result = await runtime.execute(instance_id, "run", {"input": "test"})

        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_instance(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test executing on non-existent instance."""
        with pytest.raises(ValueError, match="not found"):
            await runtime.execute("nonexistent", "run", {})

    @pytest.mark.asyncio
    async def test_execute_inactive_instance(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test executing on inactive instance."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        # Terminate the instance
        await runtime.terminate(instance_id)

        # Try to execute
        with pytest.raises(ValueError):
            await runtime.execute(instance_id, "run", {})

    @pytest.mark.asyncio
    async def test_execute_unexported_function(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test executing unexported function fails."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        with pytest.raises(ValueError, match="not exported"):
            await runtime.execute(instance_id, "nonexistent_function", {})

    @pytest.mark.asyncio
    async def test_execute_insufficient_fuel(
        self,
        runtime: WasmOverlayRuntime,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test executing with insufficient fuel."""
        manifest = OverlayManifest(
            id="low-fuel",
            name="Low Fuel",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
            fuel_budgets={"run": 1_000_000_000},  # Very high fuel requirement
        )

        instance_id = await runtime.load_overlay(manifest, mock_python_overlay)

        # Consume most fuel
        instance = runtime.get_instance(instance_id)
        instance.fuel_budget.consume(instance.fuel_budget.total_fuel - 1)

        with pytest.raises(RuntimeError, match="Insufficient fuel"):
            await runtime.execute(instance_id, "run", {})

    @pytest.mark.asyncio
    async def test_execute_records_metrics(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
    ) -> None:
        """Test that execution records metrics."""
        mock_overlay = MagicMock()
        mock_overlay.run = AsyncMock(return_value={"success": True})

        instance_id = await runtime.load_overlay(trusted_manifest, mock_overlay)

        await runtime.execute(instance_id, "run", {})

        metrics = runtime.get_metrics(instance_id)
        assert metrics["invocations"] == 1

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test execution timeout."""

        async def slow_run(payload: dict) -> dict:
            await asyncio.sleep(60)
            return {"success": True}

        mock_overlay = MagicMock()
        mock_overlay.run = slow_run

        manifest = OverlayManifest(
            id="slow",
            name="Slow",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
            fuel_budgets={"run": 1_000_000},
        )

        instance_id = await runtime.load_overlay(manifest, mock_overlay)

        # Set very short timeout
        runtime._instances[instance_id].fuel_budget.timeout_seconds = 0.01

        with pytest.raises(RuntimeError, match="timeout"):
            await runtime.execute(instance_id, "run", {})

    @pytest.mark.asyncio
    async def test_execute_security_mode_enforcement(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test security mode is enforced at execution time."""
        # Create manifest with wrong security mode but somehow has Python overlay
        manifest = OverlayManifest(
            id="wrong-mode",
            name="Wrong Mode",
            version="1.0.0",
            security_mode=OverlaySecurityMode.PYTHON_TRUSTED,
            is_internal_trusted=True,
        )

        mock_overlay = MagicMock()
        mock_overlay.run = AsyncMock(return_value={})

        instance_id = await runtime.load_overlay(manifest, mock_overlay)

        # Manually change security mode after loading (simulating bypass attempt)
        runtime._instances[instance_id].manifest.security_mode = (
            OverlaySecurityMode.WASM_STRICT
        )

        with pytest.raises(SecurityError):
            await runtime.execute(instance_id, "run", {})

    # -------------------------------------------------------------------------
    # Termination Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_terminate_instance(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test terminating an instance."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        result = await runtime.terminate(instance_id)

        assert result is True
        assert instance_id not in runtime._instances

    @pytest.mark.asyncio
    async def test_terminate_nonexistent(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test terminating non-existent instance."""
        result = await runtime.terminate("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_terminate_clears_references(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test that termination clears references."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        instance = runtime.get_instance(instance_id)
        assert instance._python_overlay is not None

        await runtime.terminate(instance_id)

        # Instance should be removed entirely
        assert runtime.get_instance(instance_id) is None

    # -------------------------------------------------------------------------
    # Query Tests
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_instance(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test getting instance by ID."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        instance = runtime.get_instance(instance_id)

        assert instance is not None
        assert instance.id == instance_id

    def test_get_instance_nonexistent(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test getting non-existent instance."""
        instance = runtime.get_instance("nonexistent")
        assert instance is None

    @pytest.mark.asyncio
    async def test_get_active_instances(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test getting active instances."""
        await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        active = runtime.get_active_instances()

        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_get_metrics(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test getting instance metrics."""
        instance_id = await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        metrics = runtime.get_metrics(instance_id)

        assert metrics is not None
        assert "invocations" in metrics

    def test_get_metrics_nonexistent(
        self,
        runtime: WasmOverlayRuntime,
    ) -> None:
        """Test getting metrics for non-existent instance."""
        metrics = runtime.get_metrics("nonexistent")
        assert metrics is None

    @pytest.mark.asyncio
    async def test_get_summary(
        self,
        runtime: WasmOverlayRuntime,
        trusted_manifest: OverlayManifest,
        mock_python_overlay: MagicMock,
    ) -> None:
        """Test getting runtime summary."""
        await runtime.load_overlay(trusted_manifest, mock_python_overlay)

        summary = runtime.get_summary()

        assert summary["total_instances"] == 1
        assert summary["active_instances"] == 1
        assert "instances_by_state" in summary


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalWasmRuntime:
    """Tests for global WASM runtime instance."""

    def test_get_wasm_runtime(self) -> None:
        """Test getting global runtime."""
        import forge.kernel.wasm_runtime as wr

        wr._wasm_runtime = None

        runtime = get_wasm_runtime()
        assert runtime is not None

        runtime2 = get_wasm_runtime()
        assert runtime is runtime2

        wr._wasm_runtime = None

    def test_init_wasm_runtime(self) -> None:
        """Test initializing global runtime."""
        import forge.kernel.wasm_runtime as wr

        wr._wasm_runtime = None

        mock_db = MagicMock()
        mock_bus = MagicMock()

        runtime = init_wasm_runtime(db_client=mock_db, event_bus=mock_bus)

        assert runtime._db is mock_db
        assert runtime._events is mock_bus

        wr._wasm_runtime = None

    def test_shutdown_wasm_runtime(self) -> None:
        """Test shutting down global runtime."""
        import forge.kernel.wasm_runtime as wr

        init_wasm_runtime()
        shutdown_wasm_runtime()

        assert wr._wasm_runtime is None


# =============================================================================
# Security Mode Tests
# =============================================================================


class TestOverlaySecurityMode:
    """Tests for security mode enum."""

    def test_security_mode_values(self) -> None:
        """Test security mode values."""
        assert OverlaySecurityMode.WASM_STRICT.value == "wasm_strict"
        assert OverlaySecurityMode.WASM_RELAXED.value == "wasm_relaxed"
        assert OverlaySecurityMode.PYTHON_TRUSTED.value == "python_trusted"


# =============================================================================
# Execution State Tests
# =============================================================================


class TestExecutionState:
    """Tests for ExecutionState enum."""

    def test_execution_state_values(self) -> None:
        """Test execution state values."""
        assert ExecutionState.INITIALIZING.value == "initializing"
        assert ExecutionState.READY.value == "ready"
        assert ExecutionState.RUNNING.value == "running"
        assert ExecutionState.PAUSED.value == "paused"
        assert ExecutionState.TERMINATED.value == "terminated"
        assert ExecutionState.FAILED.value == "failed"
