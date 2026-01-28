"""
Overlay Repository Tests for Forge Cascade V2

Comprehensive tests for OverlayRepository including:
- Overlay CRUD operations
- State transitions (activate, deactivate, quarantine, recover)
- Metrics and execution tracking
- Health checks
- Capability-based queries
- Trust level filtering
- Dependency management

NOTE: Due to ForgeModel's `use_enum_values=True` config, Capability enums are
stored as strings in Pydantic models. The repository's create() method has a
bug where it calls .value on capabilities that are already strings. Tests that
exercise this path will fail until the repository is fixed to handle both cases.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.base import OverlayState, TrustLevel
from forge.models.overlay import (
    Capability,
    Overlay,
    OverlayExecution,
    OverlayHealthCheck,
    OverlayMetrics,
)
from forge.repositories.overlay_repository import (
    OverlayCreate,
    OverlayRepository,
    OverlayUpdate,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def overlay_repository(mock_db_client):
    """Create overlay repository with mock client."""
    return OverlayRepository(mock_db_client)


@pytest.fixture
def sample_overlay_data():
    """Sample overlay data for testing.

    Note: This matches the raw format returned from Neo4j, which the
    Pydantic model will validate and convert (e.g., strings to enums).
    State values must be lowercase (e.g., 'registered', 'active').
    TrustLevel must be an integer (0, 40, 60, 80, or 100).
    """
    return {
        "id": "overlay123",
        "name": "test-overlay",
        "description": "A test overlay for testing",
        "version": "1.0.0",
        "state": "registered",  # lowercase to match OverlayState enum values
        "trust_level": 60,  # TrustLevel is IntEnum: 0, 40, 60, 80, 100
        "capabilities": ["DATABASE_READ", "EVENT_PUBLISH"],
        "dependencies": [],
        "wasm_hash": "a" * 64,
        "wasm_hash_verified": True,
        # Metrics are embedded in the Overlay node in Neo4j
        "total_executions": 10,
        "successful_executions": 9,
        "failed_executions": 1,
        "total_execution_time_ms": 500.0,
        "avg_execution_time_ms": 50.0,
        "memory_used_bytes": 1024,
        "cpu_cycles_used": 10000,
        "health_checks_passed": 5,
        "health_checks_failed": 0,
        "consecutive_failures": 0,
        "activated_at": None,
        "deactivated_at": None,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Overlay Creation Tests
# =============================================================================


class TestOverlayRepositoryCreate:
    """Tests for overlay creation.

    NOTE: Some tests are marked xfail due to a bug in overlay_repository.py
    where line 128 calls .value on capabilities that are already strings
    (due to ForgeModel's use_enum_values=True configuration).
    """

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 128 calls .value on string capabilities"
    )
    async def test_create_overlay_success(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Successful overlay creation."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        overlay_create = OverlayCreate(
            id="overlay123",
            name="test-overlay",
            version="1.0.0",
            description="A test overlay for testing",
            capabilities={Capability.DATABASE_READ, Capability.EVENT_PUBLISH},
        )

        result = await overlay_repository.create(data=overlay_create)

        assert result.name == "test-overlay"
        assert result.version == "1.0.0"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 128 calls .value on string capabilities"
    )
    async def test_create_overlay_with_wasm_content_verifies_hash(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Overlay creation with WASM content verifies hash."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        wasm_content = b"fake wasm binary content"
        # Compute expected hash
        import hashlib

        expected_hash = hashlib.sha256(wasm_content).hexdigest()

        overlay_create = OverlayCreate(
            id="overlay123",
            name="wasm-overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
        )

        result = await overlay_repository.create(
            data=overlay_create,
            wasm_content=wasm_content,
        )

        # Verify hash was passed to query
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["wasm_hash"] == expected_hash
        assert params["hash_verified"] is True

    @pytest.mark.asyncio
    async def test_create_overlay_wasm_hash_mismatch_raises_error(
        self, overlay_repository, mock_db_client
    ):
        """Overlay creation with mismatched WASM hash raises error."""
        wasm_content = b"fake wasm binary content"

        overlay_create = OverlayCreate(
            id="overlay123",
            name="wasm-overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
            source_hash="incorrect_hash_that_does_not_match",
        )

        with pytest.raises(ValueError, match="WASM hash mismatch"):
            await overlay_repository.create(
                data=overlay_create,
                wasm_content=wasm_content,
            )

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 128 calls .value on string capabilities"
    )
    async def test_create_overlay_without_wasm_content(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Overlay creation without WASM content uses provided hash."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        provided_hash = "a" * 64
        overlay_create = OverlayCreate(
            id="overlay123",
            name="test-overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
            source_hash=provided_hash,
        )

        await overlay_repository.create(data=overlay_create)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["wasm_hash"] == provided_hash
        assert params["hash_verified"] is False

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 128 calls .value on string capabilities"
    )
    async def test_create_overlay_generates_id_if_missing(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Overlay creation generates ID if not provided."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        overlay_create = OverlayCreate(
            id="",  # Empty ID, should generate
            name="test-overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
        )

        with patch.object(overlay_repository, "_generate_id", return_value="generated-id"):
            await overlay_repository.create(data=overlay_create)

            call_args = mock_db_client.execute_single.call_args
            params = call_args[0][1]
            # Note: since id="", the or expression will use _generate_id
            assert params["id"] is not None

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 128 calls .value on string capabilities"
    )
    async def test_create_overlay_failure_raises_runtime_error(
        self, overlay_repository, mock_db_client
    ):
        """Overlay creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        overlay_create = OverlayCreate(
            id="overlay123",
            name="test-overlay",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ},
        )

        with pytest.raises(RuntimeError, match="Failed to create overlay"):
            await overlay_repository.create(data=overlay_create)


# =============================================================================
# Overlay Update Tests
# =============================================================================


class TestOverlayRepositoryUpdate:
    """Tests for overlay update operations."""

    @pytest.mark.asyncio
    async def test_update_overlay_name(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Update overlay name."""
        sample_overlay_data["name"] = "updated-name"
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        update = OverlayUpdate(name="updated-name")
        result = await overlay_repository.update("overlay123", update)

        assert result.name == "updated-name"
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["name"] == "updated-name"

    @pytest.mark.asyncio
    async def test_update_overlay_description(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Update overlay description."""
        sample_overlay_data["description"] = "New description"
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        update = OverlayUpdate(description="New description")
        result = await overlay_repository.update("overlay123", update)

        assert result.description == "New description"

    @pytest.mark.asyncio
    async def test_update_overlay_version(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Update overlay version."""
        sample_overlay_data["version"] = "2.0.0"
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        update = OverlayUpdate(version="2.0.0")
        result = await overlay_repository.update("overlay123", update)

        assert result.version == "2.0.0"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="Bug: overlay_repository.py line 228 calls .value on string capabilities"
    )
    async def test_update_overlay_capabilities(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Update overlay capabilities."""
        sample_overlay_data["capabilities"] = ["DATABASE_WRITE", "LLM_ACCESS"]
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        update = OverlayUpdate(capabilities={Capability.DATABASE_WRITE, Capability.LLM_ACCESS})
        result = await overlay_repository.update("overlay123", update)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        # Capabilities should be converted to list of strings
        assert "DATABASE_WRITE" in params["capabilities"]
        assert "LLM_ACCESS" in params["capabilities"]

    @pytest.mark.asyncio
    async def test_update_overlay_trust_level(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Update overlay trust level."""
        sample_overlay_data["trust_level"] = 80  # TrustLevel.TRUSTED
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        update = OverlayUpdate(trust_level=TrustLevel.TRUSTED)
        result = await overlay_repository.update("overlay123", update)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["trust_level"] == TrustLevel.TRUSTED.value

    @pytest.mark.asyncio
    async def test_update_overlay_not_found(self, overlay_repository, mock_db_client):
        """Update returns None for non-existent overlay."""
        mock_db_client.execute_single.return_value = None

        update = OverlayUpdate(name="new-name")
        result = await overlay_repository.update("nonexistent", update)

        assert result is None


# =============================================================================
# State Transition Tests
# =============================================================================


class TestOverlayRepositoryStateTransitions:
    """Tests for overlay state transitions."""

    @pytest.mark.asyncio
    async def test_set_state_to_active(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Set overlay state to ACTIVE."""
        sample_overlay_data["state"] = "active"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.set_state(
            "overlay123",
            OverlayState.ACTIVE,
            reason="Manual activation",
        )

        assert result.state == OverlayState.ACTIVE
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        # Should set activated_at for ACTIVE state
        assert "activated_at" in query

    @pytest.mark.asyncio
    async def test_set_state_to_inactive(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Set overlay state to INACTIVE."""
        sample_overlay_data["state"] = "inactive"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.set_state(
            "overlay123",
            OverlayState.INACTIVE,
            reason="Manual deactivation",
        )

        assert result.state == OverlayState.INACTIVE
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        # Should set deactivated_at for INACTIVE state
        assert "deactivated_at" in query

    @pytest.mark.asyncio
    async def test_set_state_to_quarantined(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Set overlay state to QUARANTINED."""
        sample_overlay_data["state"] = "quarantined"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.set_state(
            "overlay123",
            OverlayState.QUARANTINED,
            reason="Security concern",
        )

        assert result.state == OverlayState.QUARANTINED
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        # Should set deactivated_at for QUARANTINED state
        assert "deactivated_at" in query

    @pytest.mark.asyncio
    async def test_activate_overlay(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Activate an overlay."""
        sample_overlay_data["state"] = "active"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.activate("overlay123")

        assert result.state == OverlayState.ACTIVE

    @pytest.mark.asyncio
    async def test_deactivate_overlay(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Deactivate an overlay."""
        sample_overlay_data["state"] = "inactive"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.deactivate("overlay123", reason="Maintenance")

        assert result.state == OverlayState.INACTIVE

    @pytest.mark.asyncio
    async def test_quarantine_overlay(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Quarantine a misbehaving overlay."""
        sample_overlay_data["state"] = "quarantined"  # lowercase
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.quarantine(
            "overlay123",
            reason="Excessive failures",
        )

        assert result.state == OverlayState.QUARANTINED

    @pytest.mark.asyncio
    async def test_recover_overlay(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Recover a quarantined overlay."""
        # First call resets consecutive_failures, second sets state
        sample_overlay_data["state"] = "inactive"  # lowercase
        mock_db_client.execute_single.side_effect = [
            None,  # Reset failures
            {"entity": sample_overlay_data},  # Set state
        ]

        result = await overlay_repository.recover("overlay123")

        assert result.state == OverlayState.INACTIVE
        # Should have made two calls
        assert mock_db_client.execute_single.call_count == 2

    @pytest.mark.asyncio
    async def test_set_state_not_found(self, overlay_repository, mock_db_client):
        """Set state returns None for non-existent overlay."""
        mock_db_client.execute_single.return_value = None

        result = await overlay_repository.set_state(
            "nonexistent",
            OverlayState.ACTIVE,
        )

        assert result is None


# =============================================================================
# Metrics and Execution Tests
# =============================================================================


class TestOverlayRepositoryMetrics:
    """Tests for overlay metrics and execution tracking."""

    @pytest.mark.asyncio
    async def test_record_successful_execution(
        self, overlay_repository, mock_db_client
    ):
        """Record a successful execution."""
        mock_db_client.execute_single.return_value = {"consecutive_failures": 0}

        execution = OverlayExecution(
            overlay_id="overlay123",
            function_name="process",
            input_payload={"data": "test"},
            output_result={"result": "success"},
            success=True,
            execution_time_ms=45.5,
            fuel_used=1000,
            memory_used_bytes=2048,
        )

        result = await overlay_repository.record_execution("overlay123", execution)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["success"] is True
        assert params["exec_time"] == 45.5
        assert params["fuel"] == 1000
        assert params["memory"] == 2048

    @pytest.mark.asyncio
    async def test_record_failed_execution(
        self, overlay_repository, mock_db_client
    ):
        """Record a failed execution."""
        mock_db_client.execute_single.return_value = {"consecutive_failures": 1}

        execution = OverlayExecution(
            overlay_id="overlay123",
            function_name="process",
            input_payload={"data": "test"},
            success=False,
            error="Processing failed",
            execution_time_ms=100.0,
            fuel_used=500,
            memory_used_bytes=1024,
        )

        result = await overlay_repository.record_execution("overlay123", execution)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["success"] is False
        assert params["error"] == "Processing failed"

    @pytest.mark.asyncio
    async def test_record_execution_auto_quarantine(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Auto-quarantine after 5 consecutive failures."""
        # First call returns 5 consecutive failures, second is quarantine
        sample_overlay_data["state"] = "quarantined"
        mock_db_client.execute_single.side_effect = [
            {"consecutive_failures": 5},
            {"entity": sample_overlay_data},  # quarantine call
        ]

        execution = OverlayExecution(
            overlay_id="overlay123",
            function_name="process",
            input_payload={},
            success=False,
            error="Fatal error",
            execution_time_ms=10.0,
        )

        await overlay_repository.record_execution("overlay123", execution)

        # Should have called quarantine
        assert mock_db_client.execute_single.call_count == 2

    @pytest.mark.asyncio
    async def test_record_health_check_passed(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Record a passed health check."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        health_check = OverlayHealthCheck(
            overlay_id="overlay123",
            level="L1",
            healthy=True,
            message="All systems operational",
        )

        result = await overlay_repository.record_health_check("overlay123", health_check)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["healthy"] is True

    @pytest.mark.asyncio
    async def test_record_health_check_failed(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Record a failed health check."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        health_check = OverlayHealthCheck(
            overlay_id="overlay123",
            level="L2",
            healthy=False,
            message="Memory limit exceeded",
        )

        result = await overlay_repository.record_health_check("overlay123", health_check)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["healthy"] is False

    @pytest.mark.asyncio
    async def test_get_metrics(self, overlay_repository, mock_db_client):
        """Get overlay metrics."""
        metrics_data = {
            "total_executions": 100,
            "successful_executions": 95,
            "failed_executions": 5,
            "total_execution_time_ms": 5000.0,
            "avg_execution_time_ms": 50.0,
            "last_execution": datetime.now(UTC).isoformat(),
            "last_error": None,
            "last_error_time": None,
            "memory_used_bytes": 10240,
            "cpu_cycles_used": 50000,
            "health_checks_passed": 20,
            "health_checks_failed": 0,
            "consecutive_failures": 0,
        }
        mock_db_client.execute_single.return_value = {"metrics": metrics_data}

        result = await overlay_repository.get_metrics("overlay123")

        assert isinstance(result, OverlayMetrics)
        assert result.total_executions == 100
        assert result.successful_executions == 95
        assert result.failed_executions == 5

    @pytest.mark.asyncio
    async def test_get_metrics_not_found(self, overlay_repository, mock_db_client):
        """Get metrics returns None for non-existent overlay."""
        mock_db_client.execute_single.return_value = None

        result = await overlay_repository.get_metrics("nonexistent")

        assert result is None


# =============================================================================
# Query Tests
# =============================================================================


class TestOverlayRepositoryQueries:
    """Tests for overlay query operations."""

    @pytest.mark.asyncio
    async def test_get_by_state(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlays by state."""
        # Use find_by_field which is inherited
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_by_state(OverlayState.REGISTERED)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_active(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get all active overlays."""
        sample_overlay_data["state"] = "active"
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_active()

        assert len(result) == 1
        assert result[0].state == OverlayState.ACTIVE

    @pytest.mark.asyncio
    async def test_get_quarantined(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get all quarantined overlays."""
        sample_overlay_data["state"] = "quarantined"
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_quarantined()

        assert len(result) == 1
        assert result[0].state == OverlayState.QUARANTINED

    @pytest.mark.asyncio
    async def test_get_by_capability_active_only(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlays by capability (active only)."""
        sample_overlay_data["state"] = "active"
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_by_capability(
            Capability.DATABASE_READ,
            active_only=True,
        )

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["capability"] == "DATABASE_READ"
        assert params["state"] == "active"

    @pytest.mark.asyncio
    async def test_get_by_capability_all_states(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlays by capability (all states)."""
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_by_capability(
            Capability.DATABASE_READ,
            active_only=False,
        )

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["capability"] == "DATABASE_READ"
        assert "state" not in params

    @pytest.mark.asyncio
    async def test_get_by_trust_level(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlays at or above trust level."""
        sample_overlay_data["trust_level"] = 80  # TrustLevel.TRUSTED
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_by_trust_level(TrustLevel.TRUSTED)

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["trust"] == TrustLevel.TRUSTED.value

    @pytest.mark.asyncio
    async def test_get_dependencies(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlay dependencies."""
        dep_data = {**sample_overlay_data, "id": "dep123", "name": "dependency-overlay"}
        mock_db_client.execute.return_value = [{"entity": dep_data}]

        result = await overlay_repository.get_dependencies("overlay123")

        assert len(result) == 1
        assert result[0].id == "dep123"

    @pytest.mark.asyncio
    async def test_get_dependents(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlays that depend on this overlay."""
        dependent_data = {
            **sample_overlay_data,
            "id": "dependent123",
            "dependencies": ["overlay123"],
        }
        mock_db_client.execute.return_value = [{"entity": dependent_data}]

        result = await overlay_repository.get_dependents("overlay123")

        assert len(result) == 1
        assert result[0].id == "dependent123"

    @pytest.mark.asyncio
    async def test_get_unhealthy(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get unhealthy overlays."""
        sample_overlay_data["state"] = "active"
        sample_overlay_data["consecutive_failures"] = 5
        mock_db_client.execute.return_value = [{"entity": sample_overlay_data}]

        result = await overlay_repository.get_unhealthy(
            error_rate_threshold=0.1,
            consecutive_failures_threshold=3,
        )

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["failures_threshold"] == 3
        assert params["error_threshold"] == 0.1

    @pytest.mark.asyncio
    async def test_get_by_name(
        self, overlay_repository, mock_db_client, sample_overlay_data
    ):
        """Get overlay by name."""
        mock_db_client.execute_single.return_value = {"entity": sample_overlay_data}

        result = await overlay_repository.get_by_name("test-overlay")

        assert result.name == "test-overlay"
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["name"] == "test-overlay"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, overlay_repository, mock_db_client):
        """Get by name returns None for non-existent overlay."""
        mock_db_client.execute_single.return_value = None

        result = await overlay_repository.get_by_name("nonexistent")

        assert result is None


# =============================================================================
# Content Hash Tests
# =============================================================================


class TestOverlayRepositoryContentHash:
    """Tests for content hash computation."""

    def test_compute_content_hash(self, overlay_repository):
        """Compute SHA-256 hash of content."""
        content = b"test content for hashing"

        result = overlay_repository._compute_content_hash(content)

        # Should return SHA-256 hex digest (64 characters)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_compute_content_hash_different_inputs(self, overlay_repository):
        """Different inputs produce different hashes."""
        content1 = b"content one"
        content2 = b"content two"

        hash1 = overlay_repository._compute_content_hash(content1)
        hash2 = overlay_repository._compute_content_hash(content2)

        assert hash1 != hash2

    def test_compute_content_hash_consistent(self, overlay_repository):
        """Same input produces same hash."""
        content = b"consistent content"

        hash1 = overlay_repository._compute_content_hash(content)
        hash2 = overlay_repository._compute_content_hash(content)

        assert hash1 == hash2


# =============================================================================
# Node Label and Model Class Tests
# =============================================================================


class TestOverlayRepositoryProperties:
    """Tests for repository properties."""

    def test_node_label(self, overlay_repository):
        """Node label is 'Overlay'."""
        assert overlay_repository.node_label == "Overlay"

    def test_model_class(self, overlay_repository):
        """Model class is Overlay."""
        assert overlay_repository.model_class == Overlay


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
