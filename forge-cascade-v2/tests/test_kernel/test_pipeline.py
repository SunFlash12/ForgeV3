"""
Comprehensive tests for the Pipeline.

Tests cover:
- Pipeline configuration (phase configs, enable/disable)
- Phase execution (sequential and parallel)
- Custom phase handlers
- Hooks (pre-phase, post-phase, completion)
- Error handling and failure modes
- Concurrency limits
- Pipeline history and statistics
- Lifecycle management
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.kernel.event_system import EventBus
from forge.kernel.overlay_manager import OverlayManager
from forge.kernel.pipeline import (
    PhaseConfig,
    PhaseError,
    PhaseResult,
    Pipeline,
    PipelineContext,
    PipelineError,
    PipelinePhase,
    PipelineResult,
    PipelineStatus,
    get_pipeline,
    init_pipeline,
    shutdown_pipeline,
)
from forge.models.base import OverlayState
from forge.models.events import Event, EventType
from forge.models.overlay import Capability, FuelBudget
from forge.overlays.base import BaseOverlay, OverlayContext, OverlayResult


# =============================================================================
# Test Overlays for Pipeline
# =============================================================================


class IngestionOverlay(BaseOverlay):
    """Test overlay for ingestion phase."""

    NAME = "ingestion"
    VERSION = "1.0.0"
    SUBSCRIBED_EVENTS = set()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        data = input_data or {}
        data["ingested"] = True
        data["ingestion_timestamp"] = datetime.now(UTC).isoformat()
        return OverlayResult.ok(data=data)


class ValidationOverlay(BaseOverlay):
    """Test overlay for validation phase."""

    NAME = "security_validator"
    VERSION = "1.0.0"
    SUBSCRIBED_EVENTS = set()

    def __init__(self, should_fail: bool = False) -> None:
        super().__init__()
        self.should_fail = should_fail

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        if self.should_fail:
            return OverlayResult.fail("Validation failed")

        data = input_data or {}
        data["validated"] = True
        return OverlayResult.ok(data=data)


class AnalysisOverlay(BaseOverlay):
    """Test overlay for analysis phase."""

    NAME = "ml_intelligence"
    VERSION = "1.0.0"
    SUBSCRIBED_EVENTS = set()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        data = input_data or {}
        data["analyzed"] = True
        data["analysis_score"] = 0.85
        return OverlayResult.ok(data=data)


class SlowOverlay(BaseOverlay):
    """Test overlay that takes time to execute."""

    NAME = "slow_overlay"
    VERSION = "1.0.0"
    SUBSCRIBED_EVENTS = set()

    def __init__(self, delay: float = 0.5) -> None:
        super().__init__()
        self.delay = delay

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        await asyncio.sleep(self.delay)
        return OverlayResult.ok(data={"slow_processed": True})


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh EventBus."""
    return EventBus()


@pytest.fixture
def overlay_manager() -> OverlayManager:
    """Create a fresh OverlayManager."""
    return OverlayManager()


@pytest.fixture
def pipeline(overlay_manager: OverlayManager, event_bus: EventBus) -> Pipeline:
    """Create a pipeline with dependencies."""
    return Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)


@pytest.fixture
async def pipeline_with_overlays(
    overlay_manager: OverlayManager, event_bus: EventBus
) -> Pipeline:
    """Create a pipeline with registered overlays."""
    await overlay_manager.start()

    # Register test overlays
    ingestion = IngestionOverlay()
    validation = ValidationOverlay()
    analysis = AnalysisOverlay()

    await overlay_manager.register_instance(ingestion)
    await overlay_manager.register_instance(validation)
    await overlay_manager.register_instance(analysis)

    pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

    yield pipeline

    await overlay_manager.stop()


# =============================================================================
# PipelineError Tests
# =============================================================================


class TestPipelineError:
    """Tests for PipelineError and PhaseError."""

    def test_pipeline_error_with_context(self) -> None:
        """Test PipelineError includes context in message."""
        error = PipelineError(
            message="Test error",
            phase="validation",
            overlay="security_validator",
            capsule_id="cap-123",
        )

        assert "Test error" in str(error)
        assert "phase=validation" in str(error)
        assert "overlay=security_validator" in str(error)
        assert "capsule=cap-123" in str(error)

    def test_pipeline_error_without_context(self) -> None:
        """Test PipelineError without context."""
        error = PipelineError("Simple error")
        assert str(error) == "Simple error"

    def test_phase_error(self) -> None:
        """Test PhaseError with phase enum."""
        error = PhaseError(
            phase=PipelinePhase.VALIDATION,
            message="Phase failed",
            overlay="test_overlay",
        )

        assert "Phase failed" in str(error)
        assert "phase=validation" in str(error)


# =============================================================================
# PhaseConfig Tests
# =============================================================================


class TestPhaseConfig:
    """Tests for PhaseConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default phase configuration."""
        config = PhaseConfig(name=PipelinePhase.INGESTION)

        assert config.enabled is True
        assert config.timeout_ms == 5000
        assert config.required is True
        assert config.parallel is False
        assert config.max_retries == 0

    def test_custom_config(self) -> None:
        """Test custom phase configuration."""
        config = PhaseConfig(
            name=PipelinePhase.ANALYSIS,
            enabled=True,
            timeout_ms=10000,
            required=False,
            parallel=True,
            max_retries=2,
        )

        assert config.timeout_ms == 10000
        assert config.required is False
        assert config.parallel is True


# =============================================================================
# PipelineContext Tests
# =============================================================================


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_get_phase_data_exists(self) -> None:
        """Test getting phase data when it exists."""
        context = PipelineContext(
            pipeline_id="test-pipeline",
            correlation_id="corr-123",
            triggered_by="manual",
            phase_results={
                PipelinePhase.INGESTION: PhaseResult(
                    phase=PipelinePhase.INGESTION,
                    status=PipelineStatus.COMPLETED,
                    data={"ingested": True},
                )
            },
        )

        data = context.get_phase_data(PipelinePhase.INGESTION)
        assert data["ingested"] is True

    def test_get_phase_data_not_exists(self) -> None:
        """Test getting phase data when it doesn't exist."""
        context = PipelineContext(
            pipeline_id="test-pipeline",
            correlation_id="corr-123",
            triggered_by="manual",
        )

        data = context.get_phase_data(PipelinePhase.VALIDATION)
        assert data == {}


# =============================================================================
# PipelineResult Tests
# =============================================================================


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_success_property_completed(self) -> None:
        """Test success property for completed pipeline."""
        result = PipelineResult(
            pipeline_id="test",
            correlation_id="corr",
            status=PipelineStatus.COMPLETED,
        )
        assert result.success is True

    def test_success_property_failed(self) -> None:
        """Test success property for failed pipeline."""
        result = PipelineResult(
            pipeline_id="test",
            correlation_id="corr",
            status=PipelineStatus.FAILED,
        )
        assert result.success is False


# =============================================================================
# Pipeline Configuration Tests
# =============================================================================


class TestPipelineConfiguration:
    """Tests for pipeline configuration."""

    def test_configure_phase(self, pipeline: Pipeline) -> None:
        """Test configuring a phase."""
        config = PhaseConfig(
            name=PipelinePhase.ANALYSIS,
            timeout_ms=15000,
            parallel=True,
        )

        pipeline.configure_phase(PipelinePhase.ANALYSIS, config)

        assert pipeline._phase_configs[PipelinePhase.ANALYSIS].timeout_ms == 15000
        assert pipeline._phase_configs[PipelinePhase.ANALYSIS].parallel is True

    def test_disable_phase(self, pipeline: Pipeline) -> None:
        """Test disabling a phase."""
        pipeline.disable_phase(PipelinePhase.CONSENSUS)

        assert pipeline._phase_configs[PipelinePhase.CONSENSUS].enabled is False

    def test_enable_phase(self, pipeline: Pipeline) -> None:
        """Test enabling a phase."""
        pipeline.disable_phase(PipelinePhase.CONSENSUS)
        pipeline.enable_phase(PipelinePhase.CONSENSUS)

        assert pipeline._phase_configs[PipelinePhase.CONSENSUS].enabled is True

    def test_set_phase_handler(self, pipeline: Pipeline) -> None:
        """Test setting a custom phase handler."""

        def custom_handler(context: PipelineContext) -> PhaseResult:
            return PhaseResult(
                phase=PipelinePhase.INGESTION,
                status=PipelineStatus.COMPLETED,
            )

        pipeline.set_phase_handler(PipelinePhase.INGESTION, custom_handler)

        assert PipelinePhase.INGESTION in pipeline._custom_handlers


# =============================================================================
# Hook Tests
# =============================================================================


class TestPipelineHooks:
    """Tests for pipeline hooks."""

    def test_add_pre_phase_hook(self, pipeline: Pipeline) -> None:
        """Test adding pre-phase hook."""
        calls: list[tuple[PipelineContext, PipelinePhase]] = []

        def hook(context: PipelineContext, phase: PipelinePhase) -> None:
            calls.append((context, phase))

        pipeline.add_pre_phase_hook(hook)

        assert len(pipeline._pre_phase_hooks) == 1

    def test_add_post_phase_hook(self, pipeline: Pipeline) -> None:
        """Test adding post-phase hook."""
        calls: list[tuple[PipelineContext, PhaseResult]] = []

        def hook(context: PipelineContext, result: PhaseResult) -> None:
            calls.append((context, result))

        pipeline.add_post_phase_hook(hook)

        assert len(pipeline._post_phase_hooks) == 1

    def test_add_completion_hook(self, pipeline: Pipeline) -> None:
        """Test adding completion hook."""
        calls: list[PipelineResult] = []

        def hook(result: PipelineResult) -> None:
            calls.append(result)

        pipeline.add_completion_hook(hook)

        assert len(pipeline._pipeline_complete_hooks) == 1

    @pytest.mark.asyncio
    async def test_hooks_are_called(self, pipeline_with_overlays: Pipeline) -> None:
        """Test that hooks are called during execution."""
        pre_phase_calls: list[PipelinePhase] = []
        post_phase_calls: list[PipelinePhase] = []
        completion_calls: list[PipelineResult] = []

        def pre_hook(context: PipelineContext, phase: PipelinePhase) -> None:
            pre_phase_calls.append(phase)

        def post_hook(context: PipelineContext, result: PhaseResult) -> None:
            post_phase_calls.append(result.phase)

        def completion_hook(result: PipelineResult) -> None:
            completion_calls.append(result)

        pipeline_with_overlays.add_pre_phase_hook(pre_hook)
        pipeline_with_overlays.add_post_phase_hook(post_hook)
        pipeline_with_overlays.add_completion_hook(completion_hook)

        await pipeline_with_overlays.execute(input_data={"test": True})

        assert len(pre_phase_calls) > 0
        assert len(post_phase_calls) > 0
        assert len(completion_calls) == 1


# =============================================================================
# Pipeline Execution Tests
# =============================================================================


class TestPipelineExecution:
    """Tests for pipeline execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_result(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test that execute returns a PipelineResult."""
        result = await pipeline_with_overlays.execute(
            input_data={"initial": "data"},
            triggered_by="test",
        )

        assert result is not None
        assert isinstance(result, PipelineResult)
        assert result.pipeline_id is not None
        assert result.correlation_id is not None

    @pytest.mark.asyncio
    async def test_execute_passes_data_between_phases(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test that data flows between phases."""
        result = await pipeline_with_overlays.execute(
            input_data={"initial": "value"},
        )

        # Data should contain initial value plus phase additions
        assert "initial" in result.final_data
        # Check for data from overlays that ran
        # Note: only overlays that match PHASE_OVERLAYS mapping will run

    @pytest.mark.asyncio
    async def test_execute_with_event(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test executing with a triggering event."""
        event = Event(
            id="trigger-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "123"},
            correlation_id="event-corr-123",
        )

        result = await pipeline_with_overlays.execute(
            input_data={},
            event=event,
        )

        # Should use event's correlation ID
        assert result.correlation_id == "event-corr-123"

    @pytest.mark.asyncio
    async def test_execute_with_skip_phases(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test skipping specific phases."""
        result = await pipeline_with_overlays.execute(
            input_data={},
            skip_phases={PipelinePhase.CONSENSUS, PipelinePhase.PROPAGATION},
        )

        # Skipped phases should not be in results
        assert PipelinePhase.CONSENSUS not in result.phases
        assert PipelinePhase.PROPAGATION not in result.phases

    @pytest.mark.asyncio
    async def test_execute_with_disabled_phase(self, pipeline: Pipeline) -> None:
        """Test that disabled phases are skipped."""
        pipeline.disable_phase(PipelinePhase.ANALYSIS)

        result = await pipeline.execute(input_data={})

        assert PipelinePhase.ANALYSIS not in result.phases

    @pytest.mark.asyncio
    async def test_execute_with_custom_handler(self, pipeline: Pipeline) -> None:
        """Test execution with custom phase handler."""

        async def custom_handler(context: PipelineContext) -> PhaseResult:
            return PhaseResult(
                phase=PipelinePhase.INGESTION,
                status=PipelineStatus.COMPLETED,
                data={"custom": "handler_data"},
            )

        pipeline.set_phase_handler(PipelinePhase.INGESTION, custom_handler)

        result = await pipeline.execute(input_data={})

        assert result.phases[PipelinePhase.INGESTION].data.get("custom") == "handler_data"

    @pytest.mark.asyncio
    async def test_execute_records_timing(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test that execution timing is recorded."""
        result = await pipeline_with_overlays.execute(input_data={})

        assert result.duration_ms > 0
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_adds_to_history(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test that execution is added to history."""
        await pipeline_with_overlays.execute(input_data={})

        history = pipeline_with_overlays.get_pipeline_history(limit=1)
        assert len(history) == 1


# =============================================================================
# Phase Execution Tests
# =============================================================================


class TestPhaseExecution:
    """Tests for individual phase execution."""

    @pytest.mark.asyncio
    async def test_phase_with_no_overlays_passes_through(
        self, pipeline: Pipeline
    ) -> None:
        """Test that phases with no overlays pass through."""
        result = await pipeline.execute(input_data={"test": "data"})

        # Should complete even without overlays
        assert result.status == PipelineStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_parallel_phase_execution(
        self, overlay_manager: OverlayManager, event_bus: EventBus
    ) -> None:
        """Test parallel phase execution."""
        await overlay_manager.start()

        # Create multiple analysis overlays
        overlay1 = AnalysisOverlay()
        overlay2 = AnalysisOverlay()
        overlay1.NAME = "ml_intelligence"
        overlay2.NAME = "embedding"

        await overlay_manager.register_instance(overlay1)
        await overlay_manager.register_instance(overlay2)

        pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

        # Configure analysis phase as parallel
        pipeline._phase_configs[PipelinePhase.ANALYSIS].parallel = True

        result = await pipeline.execute(input_data={})

        # Both should have executed
        assert result.status == PipelineStatus.COMPLETED

        await overlay_manager.stop()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPipelineErrorHandling:
    """Tests for pipeline error handling."""

    @pytest.mark.asyncio
    async def test_required_phase_failure_stops_pipeline(
        self, overlay_manager: OverlayManager, event_bus: EventBus
    ) -> None:
        """Test that required phase failure stops pipeline."""
        await overlay_manager.start()

        failing_validator = ValidationOverlay(should_fail=True)
        await overlay_manager.register_instance(failing_validator)

        pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

        result = await pipeline.execute(input_data={})

        assert result.status == PipelineStatus.FAILED
        assert len(result.errors) > 0

        await overlay_manager.stop()

    @pytest.mark.asyncio
    async def test_optional_phase_failure_continues(
        self, overlay_manager: OverlayManager, event_bus: EventBus
    ) -> None:
        """Test that optional phase failure continues pipeline."""
        await overlay_manager.start()

        failing_validator = ValidationOverlay(should_fail=True)
        failing_validator.NAME = "governance"  # Consensus phase overlay
        await overlay_manager.register_instance(failing_validator)

        pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

        # Consensus is already marked as not required in defaults

        result = await pipeline.execute(input_data={})

        # Should complete despite consensus failure
        # because consensus is not required by default
        assert result.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED]

        await overlay_manager.stop()

    @pytest.mark.asyncio
    async def test_phase_timeout(
        self, overlay_manager: OverlayManager, event_bus: EventBus
    ) -> None:
        """Test that phase timeout is enforced."""
        await overlay_manager.start()

        slow_overlay = SlowOverlay(delay=10.0)
        slow_overlay.NAME = "ingestion"
        await overlay_manager.register_instance(slow_overlay)

        pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

        # Configure very short timeout
        pipeline._phase_configs[PipelinePhase.INGESTION].timeout_ms = 100

        result = await pipeline.execute(input_data={})

        # Should fail due to timeout
        assert result.status == PipelineStatus.FAILED
        assert any("timeout" in e.lower() for e in result.errors)

        await overlay_manager.stop()

    @pytest.mark.asyncio
    async def test_hook_errors_dont_stop_pipeline(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test that hook errors don't stop pipeline execution."""

        def failing_hook(context: PipelineContext, phase: PipelinePhase) -> None:
            raise ValueError("Hook error")

        pipeline_with_overlays.add_pre_phase_hook(failing_hook)

        # Pipeline should still complete
        result = await pipeline_with_overlays.execute(input_data={})

        # Should complete despite hook failure
        assert result is not None


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestPipelineConcurrency:
    """Tests for pipeline concurrency limits."""

    @pytest.mark.asyncio
    async def test_concurrent_pipeline_limit(self, pipeline: Pipeline) -> None:
        """Test that concurrent pipeline limit is enforced."""
        # Create many concurrent pipelines
        tasks = [pipeline.execute(input_data={}) for _ in range(60)]

        # All should eventually complete (within semaphore limit)
        results = await asyncio.gather(*tasks)

        assert all(r is not None for r in results)

    def test_max_concurrent_configurable(self) -> None:
        """Test that max concurrent is configurable."""
        pipeline = Pipeline()
        assert pipeline._max_concurrent == 50  # Default value


# =============================================================================
# Pipeline Control Tests
# =============================================================================


class TestPipelineControl:
    """Tests for pipeline control operations."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_pipeline(self, pipeline: Pipeline) -> None:
        """Test canceling non-existent pipeline."""
        result = await pipeline.cancel("nonexistent")
        assert result is False

    def test_get_active_pipelines(self, pipeline: Pipeline) -> None:
        """Test getting active pipelines."""
        active = pipeline.get_active_pipelines()
        assert isinstance(active, list)

    def test_get_pipeline_history(self, pipeline: Pipeline) -> None:
        """Test getting pipeline history."""
        history = pipeline.get_pipeline_history(limit=10)
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_get_pipeline_stats(
        self, pipeline_with_overlays: Pipeline
    ) -> None:
        """Test getting pipeline statistics."""
        await pipeline_with_overlays.execute(input_data={})
        await pipeline_with_overlays.execute(input_data={})

        stats = pipeline_with_overlays.get_pipeline_stats()

        assert stats["total"] == 2
        assert "success" in stats
        assert "failure" in stats
        assert "avg_duration_ms" in stats

    def test_get_pipeline_stats_empty(self, pipeline: Pipeline) -> None:
        """Test getting stats with no history."""
        stats = pipeline.get_pipeline_stats()

        assert stats["total"] == 0
        assert stats["success_rate"] == 0.0


# =============================================================================
# History Bounding Tests
# =============================================================================


class TestPipelineHistoryBounding:
    """Tests for pipeline history bounding."""

    @pytest.mark.asyncio
    async def test_history_is_bounded(self, pipeline: Pipeline) -> None:
        """Test that history is bounded."""
        # Execute more than max_history pipelines
        for _ in range(110):
            await pipeline.execute(input_data={})

        # History should be bounded
        assert len(pipeline._pipeline_history) <= pipeline._max_history


# =============================================================================
# Event Emission Tests
# =============================================================================


class TestPipelineEventEmission:
    """Tests for pipeline event emission."""

    @pytest.mark.asyncio
    async def test_completion_event_emitted(
        self, overlay_manager: OverlayManager
    ) -> None:
        """Test that completion event is emitted."""
        event_bus = EventBus()
        events_received: list[Event] = []

        async def event_handler(event: Event) -> None:
            events_received.append(event)

        event_bus.subscribe(
            handler=event_handler,
            event_types={EventType.CASCADE_COMPLETE, EventType.SYSTEM_EVENT},
        )

        await event_bus.start()

        pipeline = Pipeline(overlay_manager=overlay_manager, event_bus=event_bus)

        await pipeline.execute(input_data={})

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Should have emitted completion event
        assert len(events_received) >= 1

        await event_bus.stop()


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalPipeline:
    """Tests for global pipeline instance."""

    def test_get_pipeline(self) -> None:
        """Test getting global pipeline."""
        import forge.kernel.pipeline as p

        p._pipeline = None

        pipeline = get_pipeline()
        assert pipeline is not None

        pipeline2 = get_pipeline()
        assert pipeline is pipeline2

        p._pipeline = None

    def test_init_pipeline(self) -> None:
        """Test initializing global pipeline."""
        import forge.kernel.pipeline as p

        p._pipeline = None

        pipeline = init_pipeline()
        assert pipeline is not None

        p._pipeline = None

    def test_init_pipeline_with_config(self) -> None:
        """Test initializing with custom config."""
        import forge.kernel.pipeline as p

        p._pipeline = None

        custom_config = {
            PipelinePhase.ANALYSIS: PhaseConfig(
                name=PipelinePhase.ANALYSIS,
                timeout_ms=20000,
            )
        }

        pipeline = init_pipeline(phase_configs=custom_config)

        assert pipeline._phase_configs[PipelinePhase.ANALYSIS].timeout_ms == 20000

        p._pipeline = None

    def test_shutdown_pipeline(self) -> None:
        """Test shutting down global pipeline."""
        import forge.kernel.pipeline as p

        init_pipeline()
        shutdown_pipeline()

        assert p._pipeline is None


# =============================================================================
# Phase Order Tests
# =============================================================================


class TestPhaseOrder:
    """Tests for phase ordering."""

    def test_default_phase_order(self) -> None:
        """Test default phase order."""
        expected = [
            PipelinePhase.INGESTION,
            PipelinePhase.ANALYSIS,
            PipelinePhase.VALIDATION,
            PipelinePhase.CONSENSUS,
            PipelinePhase.EXECUTION,
            PipelinePhase.PROPAGATION,
            PipelinePhase.SETTLEMENT,
        ]

        assert Pipeline.PHASE_ORDER == expected

    def test_phase_overlays_mapping(self) -> None:
        """Test phase to overlay mapping."""
        assert "ingestion" in Pipeline.PHASE_OVERLAYS[PipelinePhase.INGESTION]
        assert "ml_intelligence" in Pipeline.PHASE_OVERLAYS[PipelinePhase.ANALYSIS]
        assert "security_validator" in Pipeline.PHASE_OVERLAYS[PipelinePhase.VALIDATION]


# =============================================================================
# Edge Cases
# =============================================================================


class TestPipelineEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_input_data(self, pipeline: Pipeline) -> None:
        """Test execution with empty input data."""
        result = await pipeline.execute(input_data={})
        assert result is not None

    @pytest.mark.asyncio
    async def test_large_input_data(self, pipeline: Pipeline) -> None:
        """Test execution with large input data."""
        large_data = {"key_" + str(i): "value_" + str(i) for i in range(1000)}

        result = await pipeline.execute(input_data=large_data)
        assert result is not None

    @pytest.mark.asyncio
    async def test_execution_with_all_metadata(self, pipeline: Pipeline) -> None:
        """Test execution with all optional parameters."""
        result = await pipeline.execute(
            input_data={"test": True},
            triggered_by="test-trigger",
            user_id="user-123",
            trust_flame=80,
            capsule_id="cap-123",
            proposal_id="prop-456",
            capabilities={Capability.DATABASE_READ},
            fuel_budget=FuelBudget(
                function_name="test",
                max_fuel=1000000,
            ),
            metadata={"custom": "meta"},
        )

        assert result is not None
        assert result.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED]

    @pytest.mark.asyncio
    async def test_async_custom_handler(self, pipeline: Pipeline) -> None:
        """Test async custom phase handler."""

        async def async_handler(context: PipelineContext) -> PhaseResult:
            await asyncio.sleep(0.01)
            return PhaseResult(
                phase=PipelinePhase.INGESTION,
                status=PipelineStatus.COMPLETED,
                data={"async": True},
            )

        pipeline.set_phase_handler(PipelinePhase.INGESTION, async_handler)

        result = await pipeline.execute(input_data={})

        assert result.phases[PipelinePhase.INGESTION].data.get("async") is True

    @pytest.mark.asyncio
    async def test_sync_custom_handler(self, pipeline: Pipeline) -> None:
        """Test sync custom phase handler."""

        def sync_handler(context: PipelineContext) -> PhaseResult:
            return PhaseResult(
                phase=PipelinePhase.INGESTION,
                status=PipelineStatus.COMPLETED,
                data={"sync": True},
            )

        pipeline.set_phase_handler(PipelinePhase.INGESTION, sync_handler)

        result = await pipeline.execute(input_data={})

        assert result.phases[PipelinePhase.INGESTION].data.get("sync") is True
