"""
Forge Cascade V2 Kernel

The kernel is the core processing engine of Forge.
It coordinates overlays through the seven-phase pipeline.
"""

from .event_system import (
    EventBus,
    EventSystem,  # Alias for EventBus
    get_event_bus,
    init_event_bus,
    shutdown_event_bus,
    emit,
    on
)

from .overlay_manager import (
    OverlayManager,
    OverlayRegistry,
    OverlayExecutionRequest,
    OverlayNotFoundError,
    OverlayRegistrationError,
    OverlayExecutionError,
    get_overlay_manager,
    init_overlay_manager,
    shutdown_overlay_manager
)

from .pipeline import (
    Pipeline,
    CascadePipeline,  # Alias for Pipeline
    PipelinePhase,
    PipelineStatus,
    PipelineContext,
    PipelineResult,
    PhaseConfig,
    PhaseResult,
    PipelineError,
    PhaseError,
    get_pipeline,
    init_pipeline,
    shutdown_pipeline
)

__all__ = [
    # Event System
    "EventBus",
    "get_event_bus",
    "init_event_bus",
    "shutdown_event_bus",
    "emit",
    "on",
    
    # Overlay Manager
    "OverlayManager",
    "OverlayRegistry",
    "OverlayExecutionRequest",
    "OverlayNotFoundError",
    "OverlayRegistrationError",
    "OverlayExecutionError",
    "get_overlay_manager",
    "init_overlay_manager",
    "shutdown_overlay_manager",
    
    # Pipeline
    "Pipeline",
    "PipelinePhase",
    "PipelineStatus",
    "PipelineContext",
    "PipelineResult",
    "PhaseConfig",
    "PhaseResult",
    "PipelineError",
    "PhaseError",
    "get_pipeline",
    "init_pipeline",
    "shutdown_pipeline",
]
