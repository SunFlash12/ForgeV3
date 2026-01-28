"""
Overlay Model Tests for Forge Cascade V2

Comprehensive tests for overlay models including:
- Capability enum validation
- OverlayMetrics computed properties
- FuelBudget validation
- OverlayManifest validation
- Overlay model with computed properties
- OverlayExecution with custom validators
- OverlayHealthCheck and OverlayEvent models
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.base import OverlayState, TrustLevel
from forge.models.overlay import (
    CORE_OVERLAY_CAPABILITIES,
    Capability,
    FuelBudget,
    Overlay,
    OverlayBase,
    OverlayEvent,
    OverlayExecution,
    OverlayHealthCheck,
    OverlayManifest,
    OverlayMetrics,
)

# =============================================================================
# Capability Enum Tests
# =============================================================================


class TestCapabilityEnum:
    """Tests for Capability enum."""

    def test_capability_values(self):
        """Capability enum has expected values."""
        assert Capability.NETWORK_ACCESS.value == "NETWORK_ACCESS"
        assert Capability.DATABASE_READ.value == "DATABASE_READ"
        assert Capability.DATABASE_WRITE.value == "DATABASE_WRITE"
        assert Capability.EVENT_PUBLISH.value == "EVENT_PUBLISH"
        assert Capability.EVENT_SUBSCRIBE.value == "EVENT_SUBSCRIBE"
        assert Capability.CAPSULE_CREATE.value == "CAPSULE_CREATE"
        assert Capability.CAPSULE_READ.value == "CAPSULE_READ"
        assert Capability.CAPSULE_WRITE.value == "CAPSULE_WRITE"
        assert Capability.CAPSULE_MODIFY.value == "CAPSULE_MODIFY"
        assert Capability.CAPSULE_DELETE.value == "CAPSULE_DELETE"
        assert Capability.GOVERNANCE_VOTE.value == "GOVERNANCE_VOTE"
        assert Capability.GOVERNANCE_PROPOSE.value == "GOVERNANCE_PROPOSE"
        assert Capability.GOVERNANCE_EXECUTE.value == "GOVERNANCE_EXECUTE"
        assert Capability.USER_READ.value == "USER_READ"
        assert Capability.SYSTEM_CONFIG.value == "SYSTEM_CONFIG"
        assert Capability.LLM_ACCESS.value == "LLM_ACCESS"

    def test_capability_is_string_enum(self):
        """Capability is a string enum."""
        assert isinstance(Capability.NETWORK_ACCESS, str)
        assert Capability.NETWORK_ACCESS == "NETWORK_ACCESS"

    def test_all_capabilities_count(self):
        """All capabilities are present."""
        assert len(Capability) == 16


class TestCoreOverlayCapabilities:
    """Tests for CORE_OVERLAY_CAPABILITIES constant."""

    def test_symbolic_governance_capabilities(self):
        """symbolic_governance has expected capabilities."""
        caps = CORE_OVERLAY_CAPABILITIES["symbolic_governance"]
        assert Capability.DATABASE_READ in caps
        assert Capability.DATABASE_WRITE in caps
        assert Capability.GOVERNANCE_VOTE in caps
        assert Capability.GOVERNANCE_PROPOSE in caps

    def test_security_validator_capabilities(self):
        """security_validator has expected capabilities."""
        caps = CORE_OVERLAY_CAPABILITIES["security_validator"]
        assert Capability.DATABASE_READ in caps
        assert Capability.USER_READ in caps
        assert Capability.DATABASE_WRITE not in caps

    def test_knowledge_query_has_llm_access(self):
        """knowledge_query has LLM_ACCESS capability."""
        caps = CORE_OVERLAY_CAPABILITIES["knowledge_query"]
        assert Capability.DATABASE_READ in caps
        assert Capability.LLM_ACCESS in caps

    def test_primekg_capabilities(self):
        """primekg has expected capabilities."""
        caps = CORE_OVERLAY_CAPABILITIES["primekg"]
        assert Capability.DATABASE_READ in caps
        assert Capability.DATABASE_WRITE in caps
        assert Capability.EVENT_PUBLISH in caps
        assert Capability.LLM_ACCESS in caps


# =============================================================================
# OverlayMetrics Tests
# =============================================================================


class TestOverlayMetrics:
    """Tests for OverlayMetrics model."""

    def test_default_values(self):
        """OverlayMetrics has sensible defaults."""
        metrics = OverlayMetrics()
        assert metrics.total_executions == 0
        assert metrics.successful_executions == 0
        assert metrics.failed_executions == 0
        assert metrics.total_execution_time_ms == 0.0
        assert metrics.avg_execution_time_ms == 0.0
        assert metrics.last_execution is None
        assert metrics.last_error is None
        assert metrics.last_error_time is None
        assert metrics.memory_used_bytes == 0
        assert metrics.cpu_cycles_used == 0
        assert metrics.health_checks_passed == 0
        assert metrics.health_checks_failed == 0
        assert metrics.consecutive_failures == 0

    def test_success_rate_no_executions(self):
        """Success rate is 1.0 when no executions."""
        metrics = OverlayMetrics()
        assert metrics.success_rate == 1.0

    def test_success_rate_all_successful(self):
        """Success rate is 1.0 when all successful."""
        metrics = OverlayMetrics(
            total_executions=100,
            successful_executions=100,
            failed_executions=0,
        )
        assert metrics.success_rate == 1.0

    def test_success_rate_partial(self):
        """Success rate calculates correctly."""
        metrics = OverlayMetrics(
            total_executions=100,
            successful_executions=75,
            failed_executions=25,
        )
        assert metrics.success_rate == 0.75

    def test_error_rate(self):
        """Error rate is 1 - success rate."""
        metrics = OverlayMetrics(
            total_executions=100,
            successful_executions=75,
            failed_executions=25,
        )
        assert metrics.error_rate == 0.25

    def test_error_rate_no_executions(self):
        """Error rate is 0 when no executions."""
        metrics = OverlayMetrics()
        assert metrics.error_rate == 0.0

    def test_metrics_with_last_execution(self):
        """Metrics can have last execution timestamp."""
        now = datetime.now(UTC)
        metrics = OverlayMetrics(
            total_executions=10,
            successful_executions=10,
            last_execution=now,
        )
        assert metrics.last_execution == now

    def test_metrics_with_last_error(self):
        """Metrics can track last error."""
        now = datetime.now(UTC)
        metrics = OverlayMetrics(
            total_executions=10,
            successful_executions=9,
            failed_executions=1,
            last_error="Connection timeout",
            last_error_time=now,
        )
        assert metrics.last_error == "Connection timeout"
        assert metrics.last_error_time == now


# =============================================================================
# FuelBudget Tests
# =============================================================================


class TestFuelBudget:
    """Tests for FuelBudget model."""

    def test_valid_fuel_budget(self):
        """Valid fuel budget creates model."""
        budget = FuelBudget(
            function_name="process_data",
            max_fuel=1_000_000,
            max_memory_bytes=5_242_880,
            timeout_ms=3000,
        )
        assert budget.function_name == "process_data"
        assert budget.max_fuel == 1_000_000
        assert budget.max_memory_bytes == 5_242_880
        assert budget.timeout_ms == 3000

    def test_default_values(self):
        """FuelBudget has sensible defaults."""
        budget = FuelBudget(function_name="test_func")
        assert budget.max_fuel == 5_000_000
        assert budget.max_memory_bytes == 10_485_760  # 10MB
        assert budget.timeout_ms == 5000

    def test_max_fuel_non_negative(self):
        """max_fuel must be >= 0."""
        with pytest.raises(ValidationError):
            FuelBudget(function_name="test", max_fuel=-1)

    def test_max_memory_non_negative(self):
        """max_memory_bytes must be >= 0."""
        with pytest.raises(ValidationError):
            FuelBudget(function_name="test", max_memory_bytes=-1)

    def test_timeout_non_negative(self):
        """timeout_ms must be >= 0."""
        with pytest.raises(ValidationError):
            FuelBudget(function_name="test", timeout_ms=-1)

    def test_zero_values_allowed(self):
        """Zero values are allowed for all resource limits."""
        budget = FuelBudget(
            function_name="minimal",
            max_fuel=0,
            max_memory_bytes=0,
            timeout_ms=0,
        )
        assert budget.max_fuel == 0
        assert budget.max_memory_bytes == 0
        assert budget.timeout_ms == 0


# =============================================================================
# OverlayManifest Tests
# =============================================================================


class TestOverlayManifest:
    """Tests for OverlayManifest model."""

    def test_valid_manifest(self):
        """Valid manifest creates model."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test Overlay",
            version="1.0.0",
            description="A test overlay",
        )
        assert manifest.id == "overlay-123"
        assert manifest.name == "Test Overlay"
        assert manifest.version == "1.0.0"
        assert manifest.description == "A test overlay"

    def test_version_pattern_valid(self):
        """Version must match semantic versioning pattern."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.2.3",
        )
        assert manifest.version == "1.2.3"

        manifest2 = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="0.0.1",
        )
        assert manifest2.version == "0.0.1"

    def test_version_pattern_invalid(self):
        """Invalid version pattern raises error."""
        with pytest.raises(ValidationError, match="String should match pattern"):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="1.0",  # Missing patch version
            )

        with pytest.raises(ValidationError, match="String should match pattern"):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="v1.0.0",  # Leading 'v' not allowed
            )

        with pytest.raises(ValidationError, match="String should match pattern"):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="1.0.0-beta",  # Pre-release not allowed
            )

    def test_name_max_length(self):
        """Name must be at most 100 characters."""
        with pytest.raises(ValidationError):
            OverlayManifest(
                id="overlay-123",
                name="a" * 101,
                version="1.0.0",
            )

    def test_description_max_length(self):
        """Description must be at most 1000 characters."""
        with pytest.raises(ValidationError):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="1.0.0",
                description="a" * 1001,
            )

    def test_trust_required_bounds(self):
        """trust_required must be 0-100."""
        with pytest.raises(ValidationError):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="1.0.0",
                trust_required=-1,
            )

        with pytest.raises(ValidationError):
            OverlayManifest(
                id="overlay-123",
                name="Test",
                version="1.0.0",
                trust_required=101,
            )

    def test_trust_required_default(self):
        """trust_required defaults to 60."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.0.0",
        )
        assert manifest.trust_required == 60

    def test_capabilities_as_set(self):
        """Capabilities are stored as a set."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.0.0",
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )
        assert Capability.DATABASE_READ in manifest.capabilities
        assert Capability.DATABASE_WRITE in manifest.capabilities
        assert len(manifest.capabilities) == 2

    def test_default_collections(self):
        """Default collections are empty."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.0.0",
        )
        assert manifest.capabilities == set()
        assert manifest.dependencies == []
        assert manifest.exports == []
        assert manifest.fuel_budgets == {}

    def test_fuel_budgets_dict(self):
        """fuel_budgets stores FuelBudget objects by function name."""
        budget = FuelBudget(function_name="process")
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.0.0",
            fuel_budgets={"process": budget},
        )
        assert "process" in manifest.fuel_budgets
        assert manifest.fuel_budgets["process"].function_name == "process"

    def test_wasm_optional_fields(self):
        """Wasm-specific fields are optional."""
        manifest = OverlayManifest(
            id="overlay-123",
            name="Test",
            version="1.0.0",
            wasm_path="/path/to/module.wasm",
            source_hash="abc123hash",
        )
        assert manifest.wasm_path == "/path/to/module.wasm"
        assert manifest.source_hash == "abc123hash"


# =============================================================================
# OverlayBase Tests
# =============================================================================


class TestOverlayBase:
    """Tests for OverlayBase model."""

    def test_valid_overlay_base(self):
        """Valid overlay base creates model."""
        base = OverlayBase(
            name="Test Overlay",
            description="A test overlay description",
        )
        assert base.name == "Test Overlay"
        assert base.description == "A test overlay description"

    def test_name_max_length(self):
        """Name must be at most 100 characters."""
        with pytest.raises(ValidationError):
            OverlayBase(name="a" * 101)

    def test_description_default(self):
        """Description defaults to empty string."""
        base = OverlayBase(name="Test")
        assert base.description == ""

    def test_description_max_length(self):
        """Description must be at most 1000 characters."""
        with pytest.raises(ValidationError):
            OverlayBase(name="Test", description="a" * 1001)


# =============================================================================
# Overlay Tests
# =============================================================================


class TestOverlay:
    """Tests for Overlay model."""

    def test_valid_overlay(self):
        """Valid overlay creates model."""
        overlay = Overlay(
            id="overlay-123",
            name="Test Overlay",
            description="A test overlay",
        )
        assert overlay.id == "overlay-123"
        assert overlay.name == "Test Overlay"
        assert overlay.version == "1.0.0"  # Default

    def test_default_values(self):
        """Overlay has sensible defaults."""
        overlay = Overlay(id="overlay-123", name="Test")
        assert overlay.version == "1.0.0"
        assert overlay.state == OverlayState.REGISTERED
        assert overlay.trust_level == TrustLevel.STANDARD
        assert overlay.capabilities == set()
        assert overlay.dependencies == []
        assert isinstance(overlay.metrics, OverlayMetrics)
        assert overlay.activated_at is None
        assert overlay.deactivated_at is None
        assert overlay.wasm_hash is None

    def test_is_active_property_when_active(self):
        """is_active returns True when state is ACTIVE."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.ACTIVE,
        )
        assert overlay.is_active is True

    def test_is_active_property_when_not_active(self):
        """is_active returns False when state is not ACTIVE."""
        for state in [
            OverlayState.REGISTERED,
            OverlayState.STOPPED,
            OverlayState.QUARANTINED,
            OverlayState.ERROR,
        ]:
            overlay = Overlay(
                id="overlay-123",
                name="Test",
                state=state,
            )
            assert overlay.is_active is False

    def test_is_healthy_property_healthy(self):
        """is_healthy returns True when active with good metrics."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.ACTIVE,
            metrics=OverlayMetrics(
                total_executions=100,
                successful_executions=95,
                failed_executions=5,
                consecutive_failures=0,
            ),
        )
        assert overlay.is_healthy is True

    def test_is_healthy_property_not_active(self):
        """is_healthy returns False when not active."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.STOPPED,
        )
        assert overlay.is_healthy is False

    def test_is_healthy_property_too_many_consecutive_failures(self):
        """is_healthy returns False with too many consecutive failures."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.ACTIVE,
            metrics=OverlayMetrics(consecutive_failures=3),
        )
        assert overlay.is_healthy is False

    def test_is_healthy_property_high_error_rate(self):
        """is_healthy returns False with high error rate (>= 10%)."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.ACTIVE,
            metrics=OverlayMetrics(
                total_executions=100,
                successful_executions=89,  # 11% error rate
                failed_executions=11,
                consecutive_failures=0,
            ),
        )
        assert overlay.is_healthy is False

    def test_overlay_with_timestamps(self):
        """Overlay can have activation/deactivation timestamps."""
        now = datetime.now(UTC)
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            activated_at=now,
        )
        assert overlay.activated_at == now

    def test_overlay_capabilities(self):
        """Overlay can have capabilities."""
        overlay = Overlay(
            id="overlay-123",
            name="Test",
            capabilities={Capability.DATABASE_READ, Capability.EVENT_PUBLISH},
        )
        assert Capability.DATABASE_READ in overlay.capabilities
        assert len(overlay.capabilities) == 2


# =============================================================================
# OverlayExecution Tests
# =============================================================================


class TestOverlayExecution:
    """Tests for OverlayExecution model."""

    def test_valid_execution(self):
        """Valid execution creates model."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="process_data",
            input_payload={"key": "value"},
            success=True,
            execution_time_ms=150.5,
        )
        assert execution.overlay_id == "overlay-123"
        assert execution.function_name == "process_data"
        assert execution.success is True
        assert execution.execution_time_ms == 150.5

    def test_execution_with_output(self):
        """Execution can have output result."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="process_data",
            input_payload={"input": "data"},
            output_result={"result": "processed"},
            success=True,
            execution_time_ms=100.0,
        )
        assert execution.output_result == {"result": "processed"}

    def test_execution_with_error(self):
        """Execution can have error details."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="process_data",
            input_payload={"input": "data"},
            success=False,
            error="Connection timeout",
            execution_time_ms=5000.0,
        )
        assert execution.success is False
        assert execution.error == "Connection timeout"

    def test_default_values(self):
        """Execution has sensible defaults."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="test",
            input_payload={},
            success=True,
            execution_time_ms=50.0,
        )
        assert execution.output_result is None
        assert execution.error is None
        assert execution.fuel_used == 0
        assert execution.memory_used_bytes == 0
        assert execution.correlation_id is None
        assert execution.timestamp is not None

    def test_input_payload_security_validation(self):
        """Input payload validates against forbidden keys."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            OverlayExecution(
                overlay_id="overlay-123",
                function_name="test",
                input_payload={"__proto__": "malicious"},
                success=True,
                execution_time_ms=50.0,
            )

    def test_input_payload_security_nested(self):
        """Input payload validates nested dicts for forbidden keys."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            OverlayExecution(
                overlay_id="overlay-123",
                function_name="test",
                input_payload={"nested": {"__class__": "evil"}},
                success=True,
                execution_time_ms=50.0,
            )

    def test_valid_payload_passes(self):
        """Valid payloads pass security validation."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="test",
            input_payload={
                "data": {"name": "test", "values": [1, 2, 3]},
                "config": {"enabled": True},
            },
            success=True,
            execution_time_ms=50.0,
        )
        assert "data" in execution.input_payload


# =============================================================================
# OverlayHealthCheck Tests
# =============================================================================


class TestOverlayHealthCheck:
    """Tests for OverlayHealthCheck model."""

    def test_valid_health_check(self):
        """Valid health check creates model."""
        check = OverlayHealthCheck(
            overlay_id="overlay-123",
            level="L1",
            healthy=True,
            message="All checks passed",
        )
        assert check.overlay_id == "overlay-123"
        assert check.level == "L1"
        assert check.healthy is True
        assert check.message == "All checks passed"

    def test_health_check_with_details(self):
        """Health check can have details dict."""
        check = OverlayHealthCheck(
            overlay_id="overlay-123",
            level="L2",
            healthy=False,
            message="Memory threshold exceeded",
            details={"memory_used": 90, "threshold": 80},
        )
        assert check.details["memory_used"] == 90
        assert check.details["threshold"] == 80

    def test_default_values(self):
        """Health check has sensible defaults."""
        check = OverlayHealthCheck(
            overlay_id="overlay-123",
            level="L1",
            healthy=True,
        )
        assert check.message is None
        assert check.details == {}
        assert check.timestamp is not None


# =============================================================================
# OverlayEvent Tests
# =============================================================================


class TestOverlayEvent:
    """Tests for OverlayEvent model."""

    def test_valid_event(self):
        """Valid event creates model."""
        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="capsule.created",
            payload={"capsule_id": "cap-456"},
        )
        assert event.source_overlay == "overlay-123"
        assert event.event_type == "capsule.created"
        assert event.payload["capsule_id"] == "cap-456"

    def test_event_with_targets(self):
        """Event can specify target overlays."""
        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="cascade.triggered",
            payload={"insight": "data"},
            target_overlays=["overlay-456", "overlay-789"],
        )
        assert event.target_overlays == ["overlay-456", "overlay-789"]

    def test_broadcast_event(self):
        """Event with no targets is a broadcast."""
        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="system.notification",
            payload={"message": "Hello"},
        )
        assert event.target_overlays is None

    def test_default_values(self):
        """Event has sensible defaults."""
        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="test",
            payload={},
        )
        assert event.correlation_id is None
        assert event.target_overlays is None
        assert event.timestamp is not None

    def test_payload_security_validation(self):
        """Payload validates against forbidden keys."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            OverlayEvent(
                source_overlay="overlay-123",
                event_type="test",
                payload={"__prototype__": "malicious"},
            )

    def test_payload_security_nested(self):
        """Payload validates nested dicts for forbidden keys."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            OverlayEvent(
                source_overlay="overlay-123",
                event_type="test",
                payload={"data": {"constructor": "evil"}},
            )

    def test_valid_payload_passes(self):
        """Valid payloads pass security validation."""
        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="test",
            payload={
                "data": {"name": "test", "values": [1, 2, 3]},
                "metadata": {"timestamp": "2024-01-01T00:00:00Z"},
            },
        )
        assert "data" in event.payload


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestOverlayEdgeCases:
    """Edge case tests for overlay models."""

    def test_overlay_state_transitions(self):
        """Overlay can transition through states."""
        overlay = Overlay(id="overlay-123", name="Test")
        assert overlay.state == OverlayState.REGISTERED

        # Simulate state transitions by creating new instances
        # (in real use, this would be done through service layer)
        overlay_active = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.ACTIVE,
        )
        assert overlay_active.is_active

        overlay_quarantined = Overlay(
            id="overlay-123",
            name="Test",
            state=OverlayState.QUARANTINED,
        )
        assert not overlay_quarantined.is_active
        assert not overlay_quarantined.is_healthy

    def test_metrics_edge_cases(self):
        """Test metrics with edge case values."""
        # All zeros
        metrics = OverlayMetrics()
        assert metrics.success_rate == 1.0
        assert metrics.error_rate == 0.0

        # All failures
        metrics_fail = OverlayMetrics(
            total_executions=100,
            successful_executions=0,
            failed_executions=100,
        )
        assert metrics_fail.success_rate == 0.0
        assert metrics_fail.error_rate == 1.0

    def test_overlay_with_all_trust_levels(self):
        """Overlay works with all trust levels."""
        for trust_level in TrustLevel:
            overlay = Overlay(
                id="overlay-123",
                name="Test",
                trust_level=trust_level,
            )
            assert overlay.trust_level == trust_level

    def test_manifest_with_all_capabilities(self):
        """Manifest can have all capabilities."""
        all_caps = set(Capability)
        manifest = OverlayManifest(
            id="overlay-123",
            name="Super Overlay",
            version="1.0.0",
            capabilities=all_caps,
        )
        assert len(manifest.capabilities) == 16

    def test_empty_payload_validation(self):
        """Empty payloads pass validation."""
        execution = OverlayExecution(
            overlay_id="overlay-123",
            function_name="test",
            input_payload={},
            success=True,
            execution_time_ms=50.0,
        )
        assert execution.input_payload == {}

        event = OverlayEvent(
            source_overlay="overlay-123",
            event_type="test",
            payload={},
        )
        assert event.payload == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
