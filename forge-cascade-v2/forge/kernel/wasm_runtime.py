"""
Forge Cascade V2 - WebAssembly Overlay Runtime

Provides secure execution environment for overlays using WebAssembly.
This module implements the V2 specification's security requirements:
- Memory-safe sandbox isolation
- Capability-based security
- Fuel metering for resource control
- Instant termination

Current Status: SCAFFOLDING
The full Wasm compilation pipeline requires external tooling (Nuitka/Pyodide).
This module provides the runtime interface that will be used once overlays
are compiled to WebAssembly.

For now, overlays run in Python with this interface providing:
- Capability enforcement
- Resource monitoring
- Execution lifecycle management
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar
import hashlib
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class SecurityError(Exception):
    """
    Raised when a security constraint is violated.

    SECURITY FIX (Audit 4): Explicit exception for security violations.
    """
    pass


class Capability(str, Enum):
    """
    Overlay capabilities - explicit permissions required for operations.
    
    Overlays must declare required capabilities in their manifest.
    Only declared capabilities are available at runtime.
    """
    NETWORK_ACCESS = "network_access"          # HTTP requests
    DATABASE_READ = "database_read"            # Neo4j read queries
    DATABASE_WRITE = "database_write"          # Neo4j write queries
    EVENT_PUBLISH = "event_publish"            # Publish to event bus
    EVENT_SUBSCRIBE = "event_subscribe"        # Subscribe to events
    CAPSULE_CREATE = "capsule_create"          # Create capsules
    CAPSULE_MODIFY = "capsule_modify"          # Modify capsules
    GOVERNANCE_VOTE = "governance_vote"        # Participate in governance
    LLM_ACCESS = "llm_access"                  # Use LLM service
    FILE_READ = "file_read"                    # Read local files
    FILE_WRITE = "file_write"                  # Write local files


class ExecutionState(str, Enum):
    """State of an overlay execution instance."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"
    FAILED = "failed"


@dataclass
class FuelBudget:
    """
    Resource budget for overlay execution.
    
    Fuel metering prevents runaway computations.
    Each operation consumes fuel; execution halts when fuel is exhausted.
    """
    total_fuel: int = 10_000_000       # Total fuel allocated
    consumed_fuel: int = 0              # Fuel consumed so far
    memory_limit_mb: int = 256          # Memory limit in MB
    timeout_seconds: float = 30.0       # Maximum execution time
    
    @property
    def remaining_fuel(self) -> int:
        return max(0, self.total_fuel - self.consumed_fuel)
    
    @property
    def fuel_percentage(self) -> float:
        return (self.consumed_fuel / self.total_fuel) * 100 if self.total_fuel > 0 else 0
    
    def consume(self, amount: int) -> bool:
        """Consume fuel. Returns False if insufficient fuel."""
        if self.remaining_fuel < amount:
            return False
        self.consumed_fuel += amount
        return True
    
    def is_exhausted(self) -> bool:
        return self.remaining_fuel <= 0


class OverlaySecurityMode(str, Enum):
    """
    Security mode for overlay execution.

    SECURITY FIX (Audit 4): Explicit security mode to prevent sandbox escape.
    """
    WASM_STRICT = "wasm_strict"        # Full WASM isolation (default, safest)
    WASM_RELAXED = "wasm_relaxed"      # WASM with some relaxed constraints
    PYTHON_TRUSTED = "python_trusted"  # Python mode - ONLY for internal trusted overlays
    # Note: There is NO "python_untrusted" mode - untrusted code MUST use WASM


@dataclass
class OverlayManifest:
    """
    Manifest describing an overlay's requirements and metadata.

    In full Wasm implementation, this would be loaded from manifest.json
    and the wasm_path would point to compiled .wasm binary.
    """
    id: str
    name: str
    version: str
    description: str = ""
    capabilities: set[Capability] = field(default_factory=set)
    dependencies: list[str] = field(default_factory=list)
    trust_required: int = 60

    # SECURITY FIX (Audit 4): Explicit security mode to prevent sandbox escape
    security_mode: OverlaySecurityMode = OverlaySecurityMode.WASM_STRICT
    # For Python mode, require explicit attestation that overlay is trusted
    is_internal_trusted: bool = False

    # Wasm-specific (for future implementation)
    wasm_path: Optional[Path] = None
    source_hash: Optional[str] = None
    
    # Fuel budgets per function
    fuel_budgets: dict[str, int] = field(default_factory=lambda: {
        "initialize": 10_000_000,
        "run": 5_000_000,
        "health_check": 100_000,
        "shutdown": 500_000,
    })
    
    # Exported functions
    exports: list[str] = field(default_factory=lambda: [
        "initialize",
        "run",
        "health_check",
        "shutdown",
    ])
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "dependencies": self.dependencies,
            "trust_required": self.trust_required,
            "exports": self.exports,
            "fuel_budgets": self.fuel_budgets,
        }


@dataclass
class ExecutionMetrics:
    """Metrics collected during overlay execution."""
    invocations: int = 0
    total_fuel_consumed: int = 0
    total_execution_time_ms: float = 0.0
    errors: int = 0
    last_invocation: Optional[datetime] = None
    
    # Per-function metrics
    function_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    def record_invocation(
        self,
        function: str,
        fuel_consumed: int,
        execution_time_ms: float,
        success: bool,
    ) -> None:
        """Record metrics for an invocation."""
        self.invocations += 1
        self.total_fuel_consumed += fuel_consumed
        self.total_execution_time_ms += execution_time_ms
        self.last_invocation = datetime.now(timezone.utc)
        
        if not success:
            self.errors += 1
        
        if function not in self.function_metrics:
            self.function_metrics[function] = {
                "invocations": 0,
                "total_fuel": 0,
                "total_time_ms": 0.0,
                "errors": 0,
            }
        
        self.function_metrics[function]["invocations"] += 1
        self.function_metrics[function]["total_fuel"] += fuel_consumed
        self.function_metrics[function]["total_time_ms"] += execution_time_ms
        if not success:
            self.function_metrics[function]["errors"] += 1
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "invocations": self.invocations,
            "total_fuel_consumed": self.total_fuel_consumed,
            "total_execution_time_ms": self.total_execution_time_ms,
            "errors": self.errors,
            "error_rate": self.errors / self.invocations if self.invocations > 0 else 0,
            "avg_fuel_per_invocation": self.total_fuel_consumed / self.invocations if self.invocations > 0 else 0,
            "avg_time_per_invocation_ms": self.total_execution_time_ms / self.invocations if self.invocations > 0 else 0,
            "last_invocation": self.last_invocation.isoformat() if self.last_invocation else None,
            "function_metrics": self.function_metrics,
        }


class HostFunction(ABC):
    """
    Abstract base for host functions exposed to Wasm overlays.
    
    Host functions are the bridge between Wasm sandbox and host system.
    They are capability-gated - only available if overlay has the capability.
    """
    
    name: str
    required_capability: Optional[Capability] = None
    
    @abstractmethod
    async def __call__(self, *args, **kwargs) -> Any:
        """Execute the host function."""
        pass


class LogHostFunction(HostFunction):
    """Logging host function - always available."""
    
    name = "log"
    required_capability = None
    
    def __init__(self, overlay_id: str):
        self.overlay_id = overlay_id
        self._logger = structlog.get_logger(f"overlay.{overlay_id}")
    
    async def __call__(self, level: int, message: str) -> None:
        """Log a message from the overlay."""
        log_levels = {
            0: self._logger.debug,
            1: self._logger.info,
            2: self._logger.warning,
            3: self._logger.error,
        }
        log_func = log_levels.get(level, self._logger.info)
        log_func(message, overlay_id=self.overlay_id)


def _validate_cypher_query(query: str) -> None:
    """
    SECURITY FIX: Validate Cypher query to prevent injection attacks.

    Raises:
        ValueError: If query appears to contain injection patterns
    """
    # Check for multiple statements (query chaining)
    if ';' in query:
        raise ValueError("Multiple statements not allowed in query")

    # Check for CALL clauses that could execute procedures
    query_lower = query.lower()
    if 'call ' in query_lower and 'apoc' not in query_lower:
        # Allow APOC procedures but block other CALL usage for safety
        raise ValueError("CALL statements restricted")

    # Check for LOAD CSV or other data import
    if 'load csv' in query_lower:
        raise ValueError("LOAD CSV not allowed")

    # Check for periodic commit (batch operations)
    if 'periodic commit' in query_lower:
        raise ValueError("PERIODIC COMMIT not allowed")

    # Check for USING clause which could affect query planning
    if 'using index' in query_lower or 'using scan' in query_lower:
        raise ValueError("Query hints not allowed from overlays")


class DatabaseReadHostFunction(HostFunction):
    """Database read host function."""

    name = "db_read"
    required_capability = Capability.DATABASE_READ

    def __init__(self, db_client: Any):
        self.db = db_client

    async def __call__(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """Execute a read query."""
        # SECURITY FIX: Validate query for injection patterns
        _validate_cypher_query(query)

        # Validate query is read-only
        query_lower = query.lower().strip()
        if any(kw in query_lower for kw in ["create", "merge", "set", "delete", "remove"]):
            raise PermissionError("Write operations not allowed with DATABASE_READ capability")

        return await self.db.execute(query, params or {})


class DatabaseWriteHostFunction(HostFunction):
    """Database write host function."""

    name = "db_write"
    required_capability = Capability.DATABASE_WRITE

    def __init__(self, db_client: Any):
        self.db = db_client

    async def __call__(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """Execute a write query."""
        # SECURITY FIX: Validate query for injection patterns
        _validate_cypher_query(query)
        return await self.db.execute(query, params or {})


class EventPublishHostFunction(HostFunction):
    """Event publishing host function."""
    
    name = "event_publish"
    required_capability = Capability.EVENT_PUBLISH
    
    def __init__(self, event_bus: Any, overlay_id: str):
        self.event_bus = event_bus
        self.overlay_id = overlay_id
    
    async def __call__(self, event_type: str, payload: dict) -> None:
        """Publish an event."""
        from ..models.events import Event, EventType
        from uuid import uuid4
        
        event = Event(
            id=str(uuid4()),
            event_type=EventType(event_type) if event_type in EventType.__members__ else EventType.SYSTEM_EVENT,
            source=f"overlay:{self.overlay_id}",
            payload=payload,
        )
        
        await self.event_bus.publish(event)


@dataclass
class WasmInstance:
    """
    A WebAssembly overlay instance.
    
    In full implementation, this would wrap wasmtime.Instance.
    Currently wraps Python overlay with Wasm-like interface.
    """
    id: str
    manifest: OverlayManifest
    state: ExecutionState = ExecutionState.INITIALIZING
    fuel_budget: FuelBudget = field(default_factory=FuelBudget)
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Host functions available to this instance
    host_functions: dict[str, HostFunction] = field(default_factory=dict)
    
    # Internal state
    _python_overlay: Optional[Any] = None  # Wrapped Python overlay for now
    _terminated: bool = False
    
    def is_active(self) -> bool:
        """Check if instance is active."""
        return (
            self.state in (ExecutionState.READY, ExecutionState.RUNNING) and
            not self._terminated and
            not self.fuel_budget.is_exhausted()
        )
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if instance has a capability."""
        return capability in self.manifest.capabilities


class WasmOverlayRuntime:
    """
    WebAssembly runtime for secure overlay execution.
    
    This is the main entry point for overlay lifecycle management.
    
    Full Wasm Flow (future):
    1. Load overlay manifest
    2. Compile .wasm binary
    3. Create Wasmtime engine and store
    4. Link host functions based on capabilities
    5. Instantiate module
    6. Execute exports
    
    Current Flow (Python scaffolding):
    1. Load overlay manifest
    2. Import Python overlay class
    3. Create instance with capability enforcement
    4. Execute methods with fuel tracking
    """
    
    def __init__(
        self,
        db_client: Any = None,
        event_bus: Any = None,
    ):
        self._db = db_client
        self._events = event_bus
        self._instances: dict[str, WasmInstance] = {}
        self._manifests: dict[str, OverlayManifest] = {}
        
        # Wasm engine (for future use)
        self._engine = None  # wasmtime.Engine()
        
        logger.info("wasm_runtime_initialized", mode="python_scaffolding")
    
    def _create_host_functions(
        self,
        instance: WasmInstance,
    ) -> dict[str, HostFunction]:
        """Create host functions based on overlay capabilities."""
        host_funcs: dict[str, HostFunction] = {}
        
        # Always available: logging
        host_funcs["log"] = LogHostFunction(instance.id)
        
        # Capability-gated functions
        if instance.has_capability(Capability.DATABASE_READ):
            host_funcs["db_read"] = DatabaseReadHostFunction(self._db)
        
        if instance.has_capability(Capability.DATABASE_WRITE):
            host_funcs["db_write"] = DatabaseWriteHostFunction(self._db)
        
        if instance.has_capability(Capability.EVENT_PUBLISH):
            host_funcs["event_publish"] = EventPublishHostFunction(
                self._events, instance.id
            )
        
        return host_funcs
    
    async def load_overlay(
        self,
        manifest: OverlayManifest,
        python_overlay: Optional[Any] = None,
    ) -> str:
        """
        Load and instantiate an overlay.

        Args:
            manifest: Overlay manifest
            python_overlay: Python overlay instance (current mode)

        Returns:
            Instance ID

        Raises:
            SecurityError: If Python overlay is provided without proper trust settings
        """
        # SECURITY FIX (Audit 4): Validate security settings at load time
        if python_overlay is not None:
            if manifest.security_mode != OverlaySecurityMode.PYTHON_TRUSTED:
                raise SecurityError(
                    f"Cannot load Python overlay '{manifest.name}' with security_mode "
                    f"'{manifest.security_mode.value}'. "
                    f"Python overlays MUST have security_mode=PYTHON_TRUSTED."
                )
            if not manifest.is_internal_trusted:
                raise SecurityError(
                    f"Cannot load Python overlay '{manifest.name}' without "
                    f"is_internal_trusted=True. Python overlays are only allowed "
                    f"for internal trusted code."
                )
            logger.warning(
                "loading_python_overlay",
                overlay_name=manifest.name,
                warning="Loading Python overlay - bypasses WASM isolation. "
                        "Only use for internal trusted overlays.",
            )

        instance_id = f"{manifest.id}-{int(time.time() * 1000)}"

        # Create instance
        instance = WasmInstance(
            id=instance_id,
            manifest=manifest,
            fuel_budget=FuelBudget(
                total_fuel=manifest.fuel_budgets.get("run", 5_000_000),
            ),
        )

        # Create host functions based on capabilities
        instance.host_functions = self._create_host_functions(instance)

        # Store Python overlay reference (current mode)
        instance._python_overlay = python_overlay
        
        # Store instance
        self._instances[instance_id] = instance
        self._manifests[manifest.id] = manifest
        
        # Mark as ready
        instance.state = ExecutionState.READY
        
        logger.info(
            "overlay_loaded",
            instance_id=instance_id,
            overlay_name=manifest.name,
            capabilities=[c.value for c in manifest.capabilities],
        )
        
        return instance_id
    
    async def execute(
        self,
        instance_id: str,
        function: str,
        payload: dict,
    ) -> dict[str, Any]:
        """
        Execute a function on an overlay instance.
        
        Args:
            instance_id: Instance ID
            function: Function name to call
            payload: Input payload
            
        Returns:
            Function result
        """
        instance = self._instances.get(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        
        if not instance.is_active():
            raise RuntimeError(f"Instance {instance_id} is not active")
        
        if function not in instance.manifest.exports:
            raise ValueError(f"Function {function} not exported")
        
        # Get fuel budget for this function
        function_fuel = instance.manifest.fuel_budgets.get(function, 1_000_000)
        
        # Check fuel
        if instance.fuel_budget.remaining_fuel < function_fuel:
            raise RuntimeError("Insufficient fuel for execution")
        
        instance.state = ExecutionState.RUNNING
        start_time = time.monotonic()
        
        try:
            # SECURITY FIX (Audit 4): Enforce security mode to prevent sandbox escape
            # Python mode ONLY allowed for explicitly trusted internal overlays
            if instance._python_overlay:
                # Check if Python execution is allowed
                if instance.manifest.security_mode != OverlaySecurityMode.PYTHON_TRUSTED:
                    logger.error(
                        "python_execution_blocked_wrong_mode",
                        instance_id=instance_id,
                        overlay_name=instance.manifest.name,
                        security_mode=instance.manifest.security_mode.value,
                        required_mode=OverlaySecurityMode.PYTHON_TRUSTED.value,
                    )
                    raise SecurityError(
                        f"Overlay '{instance.manifest.name}' has Python overlay but security_mode "
                        f"is '{instance.manifest.security_mode.value}'. "
                        f"Python execution requires PYTHON_TRUSTED mode."
                    )

                if not instance.manifest.is_internal_trusted:
                    logger.error(
                        "python_execution_blocked_not_trusted",
                        instance_id=instance_id,
                        overlay_name=instance.manifest.name,
                    )
                    raise SecurityError(
                        f"Overlay '{instance.manifest.name}' is not marked as internally trusted. "
                        f"Python execution is only allowed for internal trusted overlays. "
                        f"Untrusted overlays MUST be compiled to WebAssembly."
                    )

                logger.warning(
                    "python_mode_execution",
                    instance_id=instance_id,
                    overlay_name=instance.manifest.name,
                    warning="Running in Python mode - no WASM isolation. Only for trusted internal overlays.",
                )

                # Execute Python method (only for trusted internal overlays)
                method = getattr(instance._python_overlay, function, None)
                if method:
                    if asyncio.iscoroutinefunction(method):
                        result = await asyncio.wait_for(
                            method(payload),
                            timeout=instance.fuel_budget.timeout_seconds,
                        )
                    else:
                        result = method(payload)
                else:
                    result = {"error": f"Method {function} not found"}
            else:
                # Wasm mode (future)
                # result = instance.exports[function](store, payload_ptr)
                result = {"error": "Wasm execution not implemented"}
            
            # Calculate execution time and fuel
            execution_time_ms = (time.monotonic() - start_time) * 1000
            fuel_consumed = int(execution_time_ms * 1000)  # Rough approximation
            
            # Consume fuel
            instance.fuel_budget.consume(fuel_consumed)
            
            # Record metrics
            instance.metrics.record_invocation(
                function=function,
                fuel_consumed=fuel_consumed,
                execution_time_ms=execution_time_ms,
                success=True,
            )
            
            instance.state = ExecutionState.READY
            
            return result if isinstance(result, dict) else {"result": result}
            
        except asyncio.TimeoutError:
            instance.metrics.record_invocation(
                function=function,
                fuel_consumed=function_fuel,
                execution_time_ms=instance.fuel_budget.timeout_seconds * 1000,
                success=False,
            )
            instance.state = ExecutionState.FAILED
            raise RuntimeError(f"Execution timeout after {instance.fuel_budget.timeout_seconds}s")
            
        except Exception as e:
            execution_time_ms = (time.monotonic() - start_time) * 1000
            instance.metrics.record_invocation(
                function=function,
                fuel_consumed=int(execution_time_ms * 1000),
                execution_time_ms=execution_time_ms,
                success=False,
            )
            instance.state = ExecutionState.FAILED
            raise
    
    async def terminate(self, instance_id: str) -> bool:
        """
        Immediately terminate an overlay instance.
        
        In Wasm mode, this drops the instance reference which
        immediately frees all memory. No cleanup needed.
        
        Args:
            instance_id: Instance to terminate
            
        Returns:
            True if terminated
        """
        instance = self._instances.get(instance_id)
        if not instance:
            return False
        
        instance._terminated = True
        instance.state = ExecutionState.TERMINATED
        
        # Clear references
        instance._python_overlay = None
        instance.host_functions.clear()
        
        # Remove from active instances
        del self._instances[instance_id]
        
        logger.info(
            "overlay_terminated",
            instance_id=instance_id,
            overlay_name=instance.manifest.name,
        )
        
        return True
    
    def get_instance(self, instance_id: str) -> Optional[WasmInstance]:
        """Get an instance by ID."""
        return self._instances.get(instance_id)
    
    def get_active_instances(self) -> list[WasmInstance]:
        """Get all active instances."""
        return [i for i in self._instances.values() if i.is_active()]
    
    def get_metrics(self, instance_id: str) -> Optional[dict[str, Any]]:
        """Get metrics for an instance."""
        instance = self._instances.get(instance_id)
        if instance:
            return instance.metrics.to_dict()
        return None
    
    def get_summary(self) -> dict[str, Any]:
        """Get runtime summary."""
        active = [i for i in self._instances.values() if i.is_active()]
        
        return {
            "total_instances": len(self._instances),
            "active_instances": len(active),
            "instances_by_state": {
                state.value: sum(1 for i in self._instances.values() if i.state == state)
                for state in ExecutionState
            },
            "total_fuel_consumed": sum(
                i.metrics.total_fuel_consumed for i in self._instances.values()
            ),
            "total_invocations": sum(
                i.metrics.invocations for i in self._instances.values()
            ),
        }


# =============================================================================
# Global Instance
# =============================================================================

_wasm_runtime: Optional[WasmOverlayRuntime] = None


def get_wasm_runtime() -> WasmOverlayRuntime:
    """Get the global Wasm runtime instance."""
    global _wasm_runtime
    if _wasm_runtime is None:
        _wasm_runtime = WasmOverlayRuntime()
    return _wasm_runtime


def init_wasm_runtime(
    db_client: Any = None,
    event_bus: Any = None,
) -> WasmOverlayRuntime:
    """Initialize the global Wasm runtime."""
    global _wasm_runtime
    _wasm_runtime = WasmOverlayRuntime(db_client, event_bus)
    return _wasm_runtime


def shutdown_wasm_runtime() -> None:
    """Shutdown the global Wasm runtime."""
    global _wasm_runtime
    if _wasm_runtime:
        # SECURITY FIX (Audit 3): Track background tasks and handle exceptions
        async def _safe_terminate(instance_id: str) -> None:
            try:
                await _wasm_runtime.terminate(instance_id)
            except Exception as e:
                import structlog
                structlog.get_logger().error(
                    "wasm_terminate_error",
                    instance_id=instance_id,
                    error=str(e)
                )

        # Terminate all instances with exception handling
        for instance_id in list(_wasm_runtime._instances.keys()):
            task = asyncio.create_task(_safe_terminate(instance_id))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    _wasm_runtime = None


__all__ = [
    "SecurityError",
    "OverlaySecurityMode",
    "Capability",
    "ExecutionState",
    "FuelBudget",
    "OverlayManifest",
    "ExecutionMetrics",
    "HostFunction",
    "WasmInstance",
    "WasmOverlayRuntime",
    "get_wasm_runtime",
    "init_wasm_runtime",
    "shutdown_wasm_runtime",
]
