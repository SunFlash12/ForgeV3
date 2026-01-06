"""
Pipeline for Forge Cascade V2

Seven-phase coordination pipeline for processing capsules and events.
The pipeline orchestrates overlay execution in a defined sequence.

Phases:
1. INGESTION - Data validation and normalization
2. ANALYSIS - ML processing, classification, embedding
3. VALIDATION - Security checks, trust verification
4. CONSENSUS - Governance approval (if required)
5. EXECUTION - Core processing and state changes
6. PROPAGATION - Cascade effect handling, event emission
7. SETTLEMENT - Finalization, audit logging
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4
import asyncio
import structlog

from ..models.events import Event, EventType
from ..models.overlay import Capability, FuelBudget, OverlayState
from ..models.base import TrustLevel
from ..overlays.base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
    OverlayError
)
from .event_system import EventBus, get_event_bus
from .overlay_manager import OverlayManager, get_overlay_manager

logger = structlog.get_logger()


class PipelinePhase(str, Enum):
    """The seven phases of the Forge pipeline."""
    INGESTION = "ingestion"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    CONSENSUS = "consensus"
    EXECUTION = "execution"
    PROPAGATION = "propagation"
    SETTLEMENT = "settlement"


class PipelineStatus(str, Enum):
    """Status of a pipeline execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class PipelineError(OverlayError):
    """Pipeline execution error."""
    pass


class PhaseError(PipelineError):
    """Error in a specific phase."""
    def __init__(self, phase: PipelinePhase, message: str):
        self.phase = phase
        super().__init__(f"[{phase.value}] {message}")


@dataclass
class PhaseConfig:
    """Configuration for a pipeline phase."""
    name: PipelinePhase
    enabled: bool = True
    timeout_ms: int = 5000
    required: bool = True  # If False, failures don't stop pipeline
    parallel: bool = False  # Execute overlays in parallel
    max_retries: int = 0
    retry_delay_ms: int = 100


@dataclass
class PhaseResult:
    """Result of a phase execution."""
    phase: PipelinePhase
    status: PipelineStatus
    data: dict[str, Any] = field(default_factory=dict)
    overlays_executed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineContext:
    """Context for a pipeline execution."""
    # Identity
    pipeline_id: str
    correlation_id: str
    
    # Trigger
    triggered_by: str  # Event ID, "manual", or capsule ID
    trigger_event: Optional[Event] = None
    
    # User context
    user_id: Optional[str] = None
    trust_flame: int = 60
    
    # Resource context
    capsule_id: Optional[str] = None
    proposal_id: Optional[str] = None
    
    # Execution state
    data: dict[str, Any] = field(default_factory=dict)
    phase_results: dict[PipelinePhase, PhaseResult] = field(default_factory=dict)
    
    # Capabilities and limits
    capabilities: set[Capability] = field(default_factory=set)
    fuel_budget: Optional[FuelBudget] = None
    
    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    current_phase: Optional[PipelinePhase] = None
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_phase_data(self, phase: PipelinePhase) -> dict:
        """Get data from a completed phase."""
        if phase in self.phase_results:
            return self.phase_results[phase].data
        return {}


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution."""
    pipeline_id: str
    correlation_id: str
    status: PipelineStatus
    phases: dict[PipelinePhase, PhaseResult] = field(default_factory=dict)
    final_data: dict[str, Any] = field(default_factory=dict)
    events_emitted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def success(self) -> bool:
        return self.status == PipelineStatus.COMPLETED


# Phase handler type
PhaseHandler = Callable[[PipelineContext], PhaseResult]


class Pipeline:
    """
    The Forge seven-phase pipeline.
    
    Coordinates overlay execution across phases to process
    capsules, events, and governance actions.
    """
    
    # Default phase order
    PHASE_ORDER = [
        PipelinePhase.INGESTION,
        PipelinePhase.ANALYSIS,
        PipelinePhase.VALIDATION,
        PipelinePhase.CONSENSUS,
        PipelinePhase.EXECUTION,
        PipelinePhase.PROPAGATION,
        PipelinePhase.SETTLEMENT,
    ]
    
    # Default phase configurations
    DEFAULT_PHASE_CONFIGS = {
        PipelinePhase.INGESTION: PhaseConfig(
            name=PipelinePhase.INGESTION,
            timeout_ms=3000,
            required=True
        ),
        PipelinePhase.ANALYSIS: PhaseConfig(
            name=PipelinePhase.ANALYSIS,
            timeout_ms=10000,  # ML can be slow
            required=True,
            parallel=True
        ),
        PipelinePhase.VALIDATION: PhaseConfig(
            name=PipelinePhase.VALIDATION,
            timeout_ms=5000,
            required=True
        ),
        PipelinePhase.CONSENSUS: PhaseConfig(
            name=PipelinePhase.CONSENSUS,
            timeout_ms=5000,
            required=False,  # Not all actions need consensus
            enabled=True
        ),
        PipelinePhase.EXECUTION: PhaseConfig(
            name=PipelinePhase.EXECUTION,
            timeout_ms=10000,
            required=True,
            max_retries=1
        ),
        PipelinePhase.PROPAGATION: PhaseConfig(
            name=PipelinePhase.PROPAGATION,
            timeout_ms=5000,
            required=True,
            parallel=True
        ),
        PipelinePhase.SETTLEMENT: PhaseConfig(
            name=PipelinePhase.SETTLEMENT,
            timeout_ms=3000,
            required=True
        ),
    }
    
    # Phase to overlay name mapping
    PHASE_OVERLAYS = {
        PipelinePhase.INGESTION: ["ingestion", "normalization"],
        PipelinePhase.ANALYSIS: ["ml_intelligence", "embedding", "classification"],
        PipelinePhase.VALIDATION: ["security_validator", "trust_verifier"],
        PipelinePhase.CONSENSUS: ["governance", "voting"],
        PipelinePhase.EXECUTION: ["capsule_processor", "state_mutator"],
        PipelinePhase.PROPAGATION: ["cascade", "notification"],
        PipelinePhase.SETTLEMENT: ["audit", "lineage_tracker"],
    }
    
    def __init__(
        self,
        overlay_manager: Optional[OverlayManager] = None,
        event_bus: Optional[EventBus] = None,
        phase_configs: Optional[dict[PipelinePhase, PhaseConfig]] = None
    ):
        """
        Initialize the pipeline.
        
        Args:
            overlay_manager: OverlayManager instance
            event_bus: EventBus instance
            phase_configs: Custom phase configurations
        """
        self._overlay_manager = overlay_manager
        self._event_bus = event_bus
        self._phase_configs = phase_configs or self.DEFAULT_PHASE_CONFIGS.copy()
        
        self._logger = logger.bind(component="pipeline")
        
        # Custom phase handlers (override default behavior)
        self._custom_handlers: dict[PipelinePhase, PhaseHandler] = {}
        
        # Pipeline instances tracking
        self._active_pipelines: dict[str, PipelineContext] = {}
        self._pipeline_history: list[PipelineResult] = []
        self._max_history = 100
        
        # Hooks for extensibility
        self._pre_phase_hooks: list[Callable] = []
        self._post_phase_hooks: list[Callable] = []
        self._pipeline_complete_hooks: list[Callable] = []
    
    def _get_overlay_manager(self) -> OverlayManager:
        """Get the overlay manager instance."""
        if self._overlay_manager is None:
            self._overlay_manager = get_overlay_manager()
        return self._overlay_manager
    
    def _get_event_bus(self) -> EventBus:
        """Get the event bus instance."""
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def configure_phase(
        self,
        phase: PipelinePhase,
        config: PhaseConfig
    ) -> None:
        """Configure a phase."""
        self._phase_configs[phase] = config
    
    def disable_phase(self, phase: PipelinePhase) -> None:
        """Disable a phase."""
        if phase in self._phase_configs:
            self._phase_configs[phase].enabled = False
    
    def enable_phase(self, phase: PipelinePhase) -> None:
        """Enable a phase."""
        if phase in self._phase_configs:
            self._phase_configs[phase].enabled = True
    
    def set_phase_handler(
        self,
        phase: PipelinePhase,
        handler: PhaseHandler
    ) -> None:
        """Set a custom handler for a phase."""
        self._custom_handlers[phase] = handler
    
    # =========================================================================
    # Hooks
    # =========================================================================
    
    def add_pre_phase_hook(
        self,
        hook: Callable[[PipelineContext, PipelinePhase], None]
    ) -> None:
        """Add a hook called before each phase."""
        self._pre_phase_hooks.append(hook)
    
    def add_post_phase_hook(
        self,
        hook: Callable[[PipelineContext, PhaseResult], None]
    ) -> None:
        """Add a hook called after each phase."""
        self._post_phase_hooks.append(hook)
    
    def add_completion_hook(
        self,
        hook: Callable[[PipelineResult], None]
    ) -> None:
        """Add a hook called when pipeline completes."""
        self._pipeline_complete_hooks.append(hook)
    
    # =========================================================================
    # Execution
    # =========================================================================
    
    async def execute(
        self,
        input_data: dict[str, Any],
        triggered_by: str = "manual",
        event: Optional[Event] = None,
        user_id: Optional[str] = None,
        trust_flame: int = 60,
        capsule_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        capabilities: Optional[set[Capability]] = None,
        fuel_budget: Optional[FuelBudget] = None,
        metadata: Optional[dict[str, Any]] = None,
        skip_phases: Optional[set[PipelinePhase]] = None
    ) -> PipelineResult:
        """
        Execute the pipeline.
        
        Args:
            input_data: Initial data to process
            triggered_by: What triggered the pipeline
            event: Triggering event (if any)
            user_id: User context
            trust_flame: Trust level
            capsule_id: Capsule being processed
            proposal_id: Governance proposal (if any)
            capabilities: Capabilities to grant
            fuel_budget: Resource limits
            metadata: Additional context
            skip_phases: Phases to skip
            
        Returns:
            PipelineResult with execution details
        """
        pipeline_id = str(uuid4())
        correlation_id = event.correlation_id if event else str(uuid4())
        
        # Create context
        context = PipelineContext(
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
            triggered_by=triggered_by,
            trigger_event=event,
            user_id=user_id,
            trust_flame=trust_flame,
            capsule_id=capsule_id,
            proposal_id=proposal_id,
            data=input_data.copy(),
            capabilities=capabilities or set(),
            fuel_budget=fuel_budget,
            metadata=metadata or {}
        )
        
        self._active_pipelines[pipeline_id] = context
        
        self._logger.info(
            "pipeline_started",
            pipeline_id=pipeline_id,
            triggered_by=triggered_by,
            phases=len(self.PHASE_ORDER)
        )
        
        # Execute phases
        errors = []
        events_emitted = []
        start_time = asyncio.get_event_loop().time()
        
        try:
            for phase in self.PHASE_ORDER:
                config = self._phase_configs.get(phase)
                
                # Skip disabled phases
                if not config or not config.enabled:
                    continue
                
                # Skip explicitly skipped phases
                if skip_phases and phase in skip_phases:
                    continue
                
                context.current_phase = phase
                
                # Pre-phase hooks
                for hook in self._pre_phase_hooks:
                    try:
                        await self._run_hook(hook, context, phase)
                    except Exception as e:
                        self._logger.warning(
                            "pre_phase_hook_error",
                            phase=phase.value,
                            error=str(e)
                        )
                
                # Execute phase
                phase_result = await self._execute_phase(context, phase, config)
                context.phase_results[phase] = phase_result
                
                # Merge phase data into context
                if phase_result.data:
                    context.data.update(phase_result.data)
                
                # Post-phase hooks
                for hook in self._post_phase_hooks:
                    try:
                        await self._run_hook(hook, context, phase_result)
                    except Exception as e:
                        self._logger.warning(
                            "post_phase_hook_error",
                            phase=phase.value,
                            error=str(e)
                        )
                
                # Handle phase failure
                if phase_result.status == PipelineStatus.FAILED:
                    errors.extend(phase_result.errors)
                    
                    if config.required:
                        self._logger.error(
                            "pipeline_phase_failed",
                            pipeline_id=pipeline_id,
                            phase=phase.value,
                            errors=phase_result.errors
                        )
                        break
                    else:
                        self._logger.warning(
                            "pipeline_optional_phase_failed",
                            pipeline_id=pipeline_id,
                            phase=phase.value
                        )
        
        except asyncio.CancelledError:
            errors.append("Pipeline cancelled")
            self._logger.warning("pipeline_cancelled", pipeline_id=pipeline_id)
        
        except Exception as e:
            errors.append(f"Pipeline error: {str(e)}")
            self._logger.error(
                "pipeline_error",
                pipeline_id=pipeline_id,
                error=str(e),
                exc_info=True
            )
        
        finally:
            del self._active_pipelines[pipeline_id]
        
        # Determine final status
        failed_required = any(
            r.status == PipelineStatus.FAILED and 
            self._phase_configs[p].required
            for p, r in context.phase_results.items()
        )
        
        status = PipelineStatus.FAILED if failed_required or errors else PipelineStatus.COMPLETED
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        # Build result
        result = PipelineResult(
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
            status=status,
            phases=context.phase_results,
            final_data=context.data,
            events_emitted=events_emitted,
            errors=errors,
            duration_ms=duration_ms,
            started_at=context.started_at,
            completed_at=datetime.utcnow()
        )
        
        # Completion hooks
        for hook in self._pipeline_complete_hooks:
            try:
                await self._run_hook(hook, result)
            except Exception as e:
                self._logger.warning(
                    "completion_hook_error",
                    error=str(e)
                )
        
        # Record history
        self._pipeline_history.append(result)
        if len(self._pipeline_history) > self._max_history:
            self._pipeline_history = self._pipeline_history[-self._max_history:]
        
        self._logger.info(
            "pipeline_completed",
            pipeline_id=pipeline_id,
            status=status.value,
            duration_ms=round(duration_ms, 2),
            phases_completed=len(context.phase_results)
        )
        
        # Emit completion event
        await self._emit_pipeline_event(result)
        
        return result
    
    async def _execute_phase(
        self,
        context: PipelineContext,
        phase: PipelinePhase,
        config: PhaseConfig
    ) -> PhaseResult:
        """Execute a single phase."""
        start_time = asyncio.get_event_loop().time()
        started_at = datetime.utcnow()
        
        self._logger.debug(
            "phase_started",
            pipeline_id=context.pipeline_id,
            phase=phase.value
        )
        
        # Check for custom handler
        if phase in self._custom_handlers:
            try:
                result = await asyncio.wait_for(
                    self._run_handler(
                        self._custom_handlers[phase],
                        context
                    ),
                    timeout=config.timeout_ms / 1000
                )
                result.started_at = started_at
                result.completed_at = datetime.utcnow()
                result.duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                return result
                
            except asyncio.TimeoutError:
                return PhaseResult(
                    phase=phase,
                    status=PipelineStatus.FAILED,
                    errors=[f"Phase timeout after {config.timeout_ms}ms"],
                    duration_ms=config.timeout_ms,
                    started_at=started_at,
                    completed_at=datetime.utcnow()
                )
        
        # Default: execute registered overlays for this phase
        overlay_names = self.PHASE_OVERLAYS.get(phase, [])
        if not overlay_names:
            # No overlays for this phase, pass through
            return PhaseResult(
                phase=phase,
                status=PipelineStatus.COMPLETED,
                data=context.data.copy(),
                duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        manager = self._get_overlay_manager()
        
        # Get available overlays
        overlays = []
        for name in overlay_names:
            found = manager.get_by_name(name)
            overlays.extend([
                o for o in found 
                if o.state == OverlayState.ACTIVE
            ])
        
        if not overlays:
            # No active overlays, pass through
            return PhaseResult(
                phase=phase,
                status=PipelineStatus.COMPLETED,
                data=context.data.copy(),
                duration_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
                started_at=started_at,
                completed_at=datetime.utcnow()
            )
        
        # Execute overlays
        results: list[OverlayResult] = []
        executed: list[str] = []
        errors: list[str] = []
        merged_data = context.data.copy()
        
        try:
            if config.parallel:
                # Execute in parallel
                tasks = []
                for overlay in overlays:
                    overlay_ctx = OverlayContext(
                        overlay_id=overlay.id,
                        overlay_name=overlay.NAME,
                        execution_id=str(uuid4()),
                        triggered_by=f"pipeline:{context.pipeline_id}",
                        correlation_id=context.correlation_id,
                        user_id=context.user_id,
                        trust_flame=context.trust_flame,
                        capsule_id=context.capsule_id,
                        proposal_id=context.proposal_id,
                        capabilities=context.capabilities | overlay.REQUIRED_CAPABILITIES,
                        fuel_budget=context.fuel_budget,
                        metadata={
                            "phase": phase.value,
                            **context.metadata
                        }
                    )
                    
                    task = asyncio.create_task(
                        overlay.run(overlay_ctx, context.trigger_event, context.data)
                    )
                    tasks.append((overlay.NAME, task))
                
                # Wait with timeout
                done, pending = await asyncio.wait(
                    [t for _, t in tasks],
                    timeout=config.timeout_ms / 1000
                )
                
                # Cancel pending
                for task in pending:
                    task.cancel()
                
                # Collect results
                for name, task in tasks:
                    if task in done:
                        try:
                            result = task.result()
                            results.append(result)
                            executed.append(name)
                            if result.success and result.data:
                                merged_data.update(result.data)
                            elif not result.success:
                                errors.append(f"{name}: {result.error}")
                        except Exception as e:
                            errors.append(f"{name}: {str(e)}")
            else:
                # Execute sequentially
                for overlay in overlays:
                    overlay_ctx = OverlayContext(
                        overlay_id=overlay.id,
                        overlay_name=overlay.NAME,
                        execution_id=str(uuid4()),
                        triggered_by=f"pipeline:{context.pipeline_id}",
                        correlation_id=context.correlation_id,
                        user_id=context.user_id,
                        trust_flame=context.trust_flame,
                        capsule_id=context.capsule_id,
                        proposal_id=context.proposal_id,
                        capabilities=context.capabilities | overlay.REQUIRED_CAPABILITIES,
                        fuel_budget=context.fuel_budget,
                        metadata={
                            "phase": phase.value,
                            **context.metadata
                        }
                    )
                    
                    try:
                        result = await asyncio.wait_for(
                            overlay.run(overlay_ctx, context.trigger_event, merged_data),
                            timeout=config.timeout_ms / 1000
                        )
                        results.append(result)
                        executed.append(overlay.NAME)
                        
                        if result.success and result.data:
                            merged_data.update(result.data)
                        elif not result.success:
                            errors.append(f"{overlay.NAME}: {result.error}")
                            if config.required:
                                break
                    
                    except asyncio.TimeoutError:
                        errors.append(f"{overlay.NAME}: timeout")
                        if config.required:
                            break
                    
                    except Exception as e:
                        errors.append(f"{overlay.NAME}: {str(e)}")
                        if config.required:
                            break
        
        except Exception as e:
            errors.append(f"Phase execution error: {str(e)}")
        
        # Determine status
        all_success = all(r.success for r in results) if results else True
        status = PipelineStatus.COMPLETED if all_success and not errors else PipelineStatus.FAILED
        
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        
        self._logger.debug(
            "phase_completed",
            pipeline_id=context.pipeline_id,
            phase=phase.value,
            status=status.value,
            overlays=len(executed),
            duration_ms=round(duration_ms, 2)
        )
        
        return PhaseResult(
            phase=phase,
            status=status,
            data=merged_data,
            overlays_executed=executed,
            errors=errors,
            duration_ms=duration_ms,
            started_at=started_at,
            completed_at=datetime.utcnow()
        )
    
    async def _run_handler(
        self,
        handler: PhaseHandler,
        context: PipelineContext
    ) -> PhaseResult:
        """Run a custom phase handler."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(context)
        return handler(context)
    
    async def _run_hook(self, hook: Callable, *args) -> None:
        """Run a hook function."""
        if asyncio.iscoroutinefunction(hook):
            await hook(*args)
        else:
            hook(*args)
    
    async def _emit_pipeline_event(self, result: PipelineResult) -> None:
        """Emit a pipeline completion event."""
        event_bus = self._get_event_bus()
        
        event_type = (
            EventType.CASCADE_COMPLETE 
            if result.success 
            else EventType.SYSTEM_EVENT
        )
        
        await event_bus.publish(
            event_type=event_type,
            payload={
                "pipeline_id": result.pipeline_id,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "phases_completed": len(result.phases),
                "success": result.success
            },
            source="pipeline",
            correlation_id=result.correlation_id,
        )
    
    # =========================================================================
    # Control
    # =========================================================================
    
    async def cancel(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline."""
        if pipeline_id not in self._active_pipelines:
            return False
        
        # Context will be cleaned up when execute() catches CancelledError
        self._logger.info("pipeline_cancel_requested", pipeline_id=pipeline_id)
        return True
    
    def get_active_pipelines(self) -> list[PipelineContext]:
        """Get all active pipeline contexts."""
        return list(self._active_pipelines.values())
    
    def get_pipeline_history(
        self,
        limit: int = 10
    ) -> list[PipelineResult]:
        """Get recent pipeline results."""
        return self._pipeline_history[-limit:][::-1]
    
    def get_pipeline_stats(self) -> dict:
        """Get pipeline execution statistics."""
        if not self._pipeline_history:
            return {
                "total": 0,
                "success": 0,
                "failure": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0
            }
        
        success_count = sum(1 for r in self._pipeline_history if r.success)
        durations = [r.duration_ms for r in self._pipeline_history]
        
        return {
            "total": len(self._pipeline_history),
            "success": success_count,
            "failure": len(self._pipeline_history) - success_count,
            "success_rate": success_count / len(self._pipeline_history),
            "avg_duration_ms": sum(durations) / len(durations),
            "active": len(self._active_pipelines)
        }


# =========================================================================
# Global Instance
# =========================================================================

_pipeline: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    """Get the global pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline()
    return _pipeline


def init_pipeline(
    overlay_manager: Optional[OverlayManager] = None,
    event_bus: Optional[EventBus] = None,
    phase_configs: Optional[dict[PipelinePhase, PhaseConfig]] = None
) -> Pipeline:
    """Initialize the global pipeline."""
    global _pipeline
    _pipeline = Pipeline(overlay_manager, event_bus, phase_configs)
    return _pipeline


def shutdown_pipeline() -> None:
    """Shutdown the global pipeline."""
    global _pipeline
    _pipeline = None


# Alias for backward compatibility
CascadePipeline = Pipeline
