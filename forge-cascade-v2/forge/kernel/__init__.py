"""
Forge Cascade V2 Kernel

The kernel is the core processing engine of Forge.
It coordinates overlays through the seven-phase pipeline.
"""

from .event_system import (
    EventBus,
    EventSystem,  # Alias for EventBus
    emit,
    get_event_bus,
    init_event_bus,
    on,
    shutdown_event_bus,
)
from .overlay_manager import (
    OverlayExecutionError,
    OverlayExecutionRequest,
    OverlayManager,
    OverlayNotFoundError,
    OverlayRegistrationError,
    OverlayRegistry,
    get_overlay_manager,
    init_overlay_manager,
    shutdown_overlay_manager,
)
from .pipeline import (
    CascadePipeline,  # Alias for Pipeline
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
from .wasm_runtime import (
    Capability as WasmCapability,  # Avoid conflict with overlay Capability
)

# SECURITY FIX (Audit 4 - M): Export WASM runtime for overlay sandboxing
from .wasm_runtime import (
    ExecutionMetrics,
    ExecutionState,
    FuelBudget,
    HostFunction,
    OverlaySecurityMode,
    SecurityError,
    WasmInstance,
    WasmOverlayRuntime,
    get_wasm_runtime,
    init_wasm_runtime,
    shutdown_wasm_runtime,
)
from .wasm_runtime import (
    OverlayManifest as WasmOverlayManifest,  # Avoid conflict
)

__all__ = [
    # Event System
    "EventBus",
    "EventSystem",  # Alias
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
    "CascadePipeline",  # Alias
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
    # WASM Runtime
    "SecurityError",
    "OverlaySecurityMode",
    "WasmCapability",
    "ExecutionState",
    "FuelBudget",
    "WasmOverlayManifest",
    "ExecutionMetrics",
    "HostFunction",
    "WasmInstance",
    "WasmOverlayRuntime",
    "get_wasm_runtime",
    "init_wasm_runtime",
    "shutdown_wasm_runtime",
]
