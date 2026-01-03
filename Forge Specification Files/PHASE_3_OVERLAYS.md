# Forge V3 - Phase 3: Overlay Runtime

**Purpose:** Implement WebAssembly-based overlay execution with sandboxing and capability security.

**Estimated Effort:** 4-5 days
**Dependencies:** Phase 0-2
**Outputs:** Working overlay registration, execution, and lifecycle management

---

## 1. Overview

Overlays are self-contained intelligent modules that extend Forge functionality. In V3, overlays compile to WebAssembly (WASM) for true memory isolation, instant termination, and capability-based security.

**Key Capabilities:**
- WASM execution via Wasmtime
- Capability-based permissions (file access, network, capsule read/write)
- Resource limits (memory, CPU time)
- Health monitoring and auto-quarantine

---

## 2. Overlay Models

```python
# forge/models/overlay.py
"""
Overlay domain models.
"""
from datetime import datetime
from uuid import UUID
from pydantic import Field

from forge.models.base import (
    ForgeBaseModel,
    TimestampMixin,
    IdentifiableMixin,
    TrustLevel,
    OverlayState,
)


class OverlayCapability(ForgeBaseModel):
    """Capability granted to an overlay."""
    name: str = Field(description="Capability name (e.g., 'capsule:read')")
    constraints: dict | None = Field(default=None, description="Constraints on the capability")


class OverlayManifest(ForgeBaseModel):
    """
    Overlay manifest defining metadata and requirements.
    
    Submitted with WASM binary during registration.
    """
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(..., max_length=1000)
    author: str = Field(..., max_length=100)
    
    # Capabilities requested
    capabilities: list[OverlayCapability] = Field(default_factory=list)
    
    # Resource limits
    max_memory_mb: int = Field(default=64, ge=1, le=512)
    max_execution_ms: int = Field(default=5000, ge=100, le=30000)
    max_fuel: int = Field(default=1_000_000, description="WASM fuel limit for CPU")
    
    # Entry points
    entry_points: list[str] = Field(
        default_factory=lambda: ["process"],
        description="Exported functions that can be invoked",
    )


class OverlayCreate(ForgeBaseModel):
    """Request to register a new overlay."""
    manifest: OverlayManifest
    wasm_binary: bytes = Field(..., description="Compiled WebAssembly module")
    source_hash: str | None = Field(default=None, description="Hash of source code for verification")


class Overlay(TimestampMixin, IdentifiableMixin, ForgeBaseModel):
    """Complete overlay entity."""
    
    name: str
    version: str
    description: str
    author: str
    state: OverlayState = Field(default=OverlayState.PENDING)
    trust_level: TrustLevel = Field(default=TrustLevel.SANDBOX)
    
    capabilities: list[OverlayCapability] = Field(default_factory=list)
    max_memory_mb: int = 64
    max_execution_ms: int = 5000
    max_fuel: int = 1_000_000
    entry_points: list[str] = Field(default_factory=list)
    
    # Binary storage location (not the binary itself)
    wasm_key: str = Field(description="Object storage key for WASM binary")
    wasm_hash: str = Field(description="SHA-256 hash of WASM binary")
    
    # Health metrics
    invocation_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    avg_execution_ms: float = Field(default=0)
    last_invoked_at: datetime | None = None
    last_error: str | None = None


class OverlayInvocation(ForgeBaseModel):
    """Request to invoke an overlay function."""
    function: str = Field(..., description="Function name to invoke")
    args: dict = Field(default_factory=dict, description="Arguments")
    timeout_ms: int | None = Field(default=None, ge=100, le=30000)


class OverlayResult(ForgeBaseModel):
    """Result of overlay invocation."""
    success: bool
    result: dict | None = None
    error: str | None = None
    execution_time_ms: int
    fuel_consumed: int
```

---

## 3. WASM Runtime

```python
# forge/core/overlays/runtime.py
"""
WebAssembly runtime using Wasmtime.

Provides sandboxed execution with:
- Memory isolation
- CPU limits via fuel
- Capability-based host functions
"""
import asyncio
import hashlib
from pathlib import Path
from typing import Any, Callable
from datetime import datetime, timezone
import wasmtime

from forge.models.overlay import Overlay, OverlayResult, OverlayCapability
from forge.exceptions import ServiceUnavailableError, ValidationError
from forge.logging import get_logger

logger = get_logger(__name__)


class WasmHostFunctions:
    """
    Host functions exposed to WASM modules.
    
    These are the capabilities overlays can use.
    Actual implementation depends on granted capabilities.
    """
    
    def __init__(self, overlay: Overlay, services: "OverlayServices"):
        self._overlay = overlay
        self._services = services
        self._capability_names = {c.name for c in overlay.capabilities}
    
    def _check_capability(self, name: str) -> None:
        """Verify overlay has the required capability."""
        if name not in self._capability_names:
            raise PermissionError(f"Overlay lacks capability: {name}")
    
    # Logging (always available)
    def log_info(self, message: str) -> None:
        """Log info message from overlay."""
        logger.info("overlay_log", overlay=self._overlay.name, message=message)
    
    def log_error(self, message: str) -> None:
        """Log error message from overlay."""
        logger.error("overlay_log", overlay=self._overlay.name, message=message)
    
    # Capsule operations (require capabilities)
    async def capsule_read(self, capsule_id: str) -> dict | None:
        """Read a capsule by ID."""
        self._check_capability("capsule:read")
        return await self._services.capsule_service.get_by_id_for_overlay(
            capsule_id, self._overlay.trust_level
        )
    
    async def capsule_search(self, query: str, limit: int = 10) -> list[dict]:
        """Search capsules."""
        self._check_capability("capsule:read")
        return await self._services.capsule_service.search_for_overlay(
            query, self._overlay.trust_level, limit
        )
    
    async def capsule_create(self, content: str, type: str, metadata: dict) -> dict:
        """Create a new capsule."""
        self._check_capability("capsule:write")
        return await self._services.capsule_service.create_from_overlay(
            content, type, metadata, self._overlay
        )


class WasmRuntime:
    """
    WebAssembly runtime manager.
    
    Compiles and caches WASM modules, handles execution with limits.
    """
    
    def __init__(self, services: "OverlayServices"):
        self._services = services
        self._engine = wasmtime.Engine(self._create_config())
        self._module_cache: dict[str, wasmtime.Module] = {}
    
    def _create_config(self) -> wasmtime.Config:
        """Create Wasmtime configuration with safety limits."""
        config = wasmtime.Config()
        config.consume_fuel = True  # Enable fuel metering for CPU limits
        config.epoch_interruption = True  # Enable timeout interruption
        config.cache = True  # Cache compiled modules
        return config
    
    def compile_module(self, wasm_bytes: bytes, module_hash: str) -> wasmtime.Module:
        """
        Compile WASM bytes to a module.
        
        Caches by hash for reuse.
        """
        if module_hash in self._module_cache:
            return self._module_cache[module_hash]
        
        try:
            module = wasmtime.Module(self._engine, wasm_bytes)
            self._module_cache[module_hash] = module
            logger.info("wasm_module_compiled", hash=module_hash)
            return module
        except wasmtime.WasmtimeError as e:
            logger.error("wasm_compilation_failed", error=str(e))
            raise ValidationError(f"Invalid WASM module: {e}")
    
    async def invoke(
        self,
        overlay: Overlay,
        wasm_bytes: bytes,
        function_name: str,
        args: dict,
        timeout_ms: int | None = None,
    ) -> OverlayResult:
        """
        Invoke a function in an overlay's WASM module.
        
        Creates a fresh instance for each invocation (isolation).
        """
        timeout_ms = timeout_ms or overlay.max_execution_ms
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get or compile module
            module = self.compile_module(wasm_bytes, overlay.wasm_hash)
            
            # Create store with limits
            store = wasmtime.Store(self._engine)
            store.set_fuel(overlay.max_fuel)
            
            # Create linker with host functions
            linker = wasmtime.Linker(self._engine)
            host_funcs = WasmHostFunctions(overlay, self._services)
            self._register_host_functions(linker, store, host_funcs)
            
            # Instantiate module
            instance = linker.instantiate(store, module)
            
            # Get the function
            func = instance.exports(store).get(function_name)
            if func is None:
                raise ValidationError(f"Function '{function_name}' not found in module")
            
            # Run with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(self._run_function, store, func, args),
                timeout=timeout_ms / 1000,
            )
            
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            fuel_consumed = overlay.max_fuel - store.get_fuel()
            
            return OverlayResult(
                success=True,
                result=result,
                execution_time_ms=execution_time,
                fuel_consumed=fuel_consumed,
            )
            
        except asyncio.TimeoutError:
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            logger.warning("overlay_timeout", overlay=overlay.name, timeout_ms=timeout_ms)
            return OverlayResult(
                success=False,
                error=f"Execution timed out after {timeout_ms}ms",
                execution_time_ms=execution_time,
                fuel_consumed=overlay.max_fuel,
            )
        except wasmtime.Trap as e:
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            error_msg = str(e)
            
            # Check if it's fuel exhaustion
            if "out of fuel" in error_msg.lower():
                error_msg = "CPU limit exceeded (fuel exhausted)"
            
            logger.warning("overlay_trap", overlay=overlay.name, error=error_msg)
            return OverlayResult(
                success=False,
                error=error_msg,
                execution_time_ms=execution_time,
                fuel_consumed=overlay.max_fuel,
            )
        except Exception as e:
            execution_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            logger.error("overlay_error", overlay=overlay.name, error=str(e))
            return OverlayResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                fuel_consumed=0,
            )
    
    def _run_function(
        self,
        store: wasmtime.Store,
        func: wasmtime.Func,
        args: dict,
    ) -> dict:
        """Run the WASM function (in thread pool)."""
        # Serialize args to JSON bytes for passing to WASM
        import json
        args_json = json.dumps(args).encode()
        
        # Call the function (expects JSON in, JSON out)
        result_ptr = func(store, args_json)
        
        # Read result from WASM memory
        # (Implementation depends on your WASM ABI)
        return {"raw": result_ptr}
    
    def _register_host_functions(
        self,
        linker: wasmtime.Linker,
        store: wasmtime.Store,
        host: WasmHostFunctions,
    ) -> None:
        """Register host functions that WASM can call."""
        # This is simplified - real implementation needs proper ABI
        # For full implementation, use wasm-bindgen or similar
        pass
```

---

## 4. Overlay Service

```python
# forge/core/overlays/service.py
"""
Overlay business logic service.
"""
import hashlib
from uuid import UUID

from forge.core.overlays.runtime import WasmRuntime
from forge.core.overlays.repository import OverlayRepository
from forge.infrastructure.storage.client import ObjectStorageClient
from forge.models.overlay import (
    Overlay,
    OverlayCreate,
    OverlayManifest,
    OverlayInvocation,
    OverlayResult,
    OverlayState,
)
from forge.models.user import User
from forge.models.base import TrustLevel
from forge.exceptions import NotFoundError, AuthorizationError, ValidationError
from forge.logging import get_logger

logger = get_logger(__name__)


class OverlayService:
    """Service for overlay management and invocation."""
    
    # Capabilities that require elevated trust
    PRIVILEGED_CAPABILITIES = {
        "capsule:write",
        "capsule:delete",
        "governance:vote",
        "system:config",
    }
    
    def __init__(
        self,
        repository: OverlayRepository,
        runtime: WasmRuntime,
        storage: ObjectStorageClient,
    ):
        self._repo = repository
        self._runtime = runtime
        self._storage = storage
    
    async def register(
        self,
        data: OverlayCreate,
        submitter: User,
    ) -> Overlay:
        """
        Register a new overlay.
        
        Overlay starts in PENDING state and requires governance
        approval before activation.
        """
        manifest = data.manifest
        
        # Validate WASM binary
        wasm_hash = hashlib.sha256(data.wasm_binary).hexdigest()
        
        # Try to compile (validates the binary)
        self._runtime.compile_module(data.wasm_binary, wasm_hash)
        
        # Check for privileged capabilities
        has_privileged = any(
            cap.name in self.PRIVILEGED_CAPABILITIES
            for cap in manifest.capabilities
        )
        
        # Determine initial trust level
        if has_privileged:
            trust_level = TrustLevel.SANDBOX  # Requires approval for higher
        else:
            trust_level = TrustLevel.SANDBOX
        
        # Store WASM binary
        wasm_key = f"overlays/{manifest.name}/{manifest.version}/{wasm_hash}.wasm"
        await self._storage.put(wasm_key, data.wasm_binary)
        
        # Create overlay record
        overlay = await self._repo.create(
            manifest=manifest,
            wasm_key=wasm_key,
            wasm_hash=wasm_hash,
            submitter_id=submitter.id,
            trust_level=trust_level,
        )
        
        logger.info(
            "overlay_registered",
            overlay_id=str(overlay.id),
            name=manifest.name,
            version=manifest.version,
        )
        
        return overlay
    
    async def get(self, overlay_id: UUID) -> Overlay | None:
        """Get overlay by ID."""
        return await self._repo.get_by_id(overlay_id)
    
    async def invoke(
        self,
        overlay_id: UUID,
        invocation: OverlayInvocation,
        user: User,
    ) -> OverlayResult:
        """
        Invoke an overlay function.
        
        Checks:
        - Overlay exists and is active
        - User has sufficient trust level
        - Function is a valid entry point
        """
        overlay = await self._repo.get_by_id(overlay_id)
        
        if not overlay:
            raise NotFoundError("Overlay", str(overlay_id))
        
        # Check state
        if overlay.state != OverlayState.ACTIVE:
            raise ValidationError(
                f"Overlay is not active (state: {overlay.state.value})"
            )
        
        # Check trust level
        if not user.trust_level.can_access(overlay.trust_level):
            raise AuthorizationError("Insufficient trust level to invoke overlay")
        
        # Check entry point
        if invocation.function not in overlay.entry_points:
            raise ValidationError(
                f"'{invocation.function}' is not a valid entry point. "
                f"Available: {overlay.entry_points}"
            )
        
        # Load WASM binary
        wasm_bytes = await self._storage.get(overlay.wasm_key)
        if not wasm_bytes:
            raise ServiceUnavailableError("Overlay binary not found")
        
        # Invoke
        result = await self._runtime.invoke(
            overlay=overlay,
            wasm_bytes=wasm_bytes,
            function_name=invocation.function,
            args=invocation.args,
            timeout_ms=invocation.timeout_ms,
        )
        
        # Update metrics
        await self._repo.record_invocation(
            overlay_id=overlay_id,
            success=result.success,
            execution_time_ms=result.execution_time_ms,
            error=result.error,
        )
        
        # Check for auto-quarantine
        if not result.success:
            await self._check_health(overlay_id)
        
        return result
    
    async def _check_health(self, overlay_id: UUID) -> None:
        """Check overlay health and quarantine if unhealthy."""
        overlay = await self._repo.get_by_id(overlay_id)
        if not overlay:
            return
        
        # Quarantine if failure rate is too high
        if overlay.invocation_count >= 10:
            failure_rate = overlay.failure_count / overlay.invocation_count
            if failure_rate > 0.5:  # >50% failure rate
                await self._repo.update_state(overlay_id, OverlayState.QUARANTINED)
                logger.warning(
                    "overlay_quarantined",
                    overlay_id=str(overlay_id),
                    failure_rate=failure_rate,
                )
    
    async def activate(self, overlay_id: UUID, user: User) -> Overlay:
        """Activate a pending overlay (requires admin or governance approval)."""
        if "admin" not in user.roles:
            raise AuthorizationError("Only admins can activate overlays")
        
        overlay = await self._repo.get_by_id(overlay_id)
        if not overlay:
            raise NotFoundError("Overlay", str(overlay_id))
        
        if overlay.state != OverlayState.PENDING:
            raise ValidationError(f"Cannot activate overlay in state: {overlay.state.value}")
        
        return await self._repo.update_state(overlay_id, OverlayState.ACTIVE)
    
    async def suspend(self, overlay_id: UUID, user: User, reason: str) -> Overlay:
        """Suspend an active overlay."""
        if "admin" not in user.roles and "operator" not in user.roles:
            raise AuthorizationError("Insufficient privileges to suspend overlay")
        
        overlay = await self._repo.get_by_id(overlay_id)
        if not overlay:
            raise NotFoundError("Overlay", str(overlay_id))
        
        logger.info("overlay_suspended", overlay_id=str(overlay_id), reason=reason)
        return await self._repo.update_state(overlay_id, OverlayState.SUSPENDED)
```

---

## 5. Overlay Repository

```python
# forge/core/overlays/repository.py
"""
Overlay repository for database operations.
"""
from uuid import UUID, uuid4
from datetime import datetime, timezone

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.models.overlay import Overlay, OverlayManifest, OverlayState
from forge.models.base import TrustLevel
from forge.logging import get_logger

logger = get_logger(__name__)


class OverlayRepository:
    """Repository for Overlay data access."""
    
    def __init__(self, neo4j: Neo4jClient):
        self._neo4j = neo4j
    
    async def create(
        self,
        manifest: OverlayManifest,
        wasm_key: str,
        wasm_hash: str,
        submitter_id: UUID,
        trust_level: TrustLevel,
    ) -> Overlay:
        """Create a new overlay."""
        overlay_id = uuid4()
        now = datetime.now(timezone.utc)
        
        result = await self._neo4j.run_single("""
            CREATE (o:Overlay {
                id: $id,
                name: $name,
                version: $version,
                description: $description,
                author: $author,
                state: $state,
                trust_level: $trust_level,
                capabilities: $capabilities,
                max_memory_mb: $max_memory_mb,
                max_execution_ms: $max_execution_ms,
                max_fuel: $max_fuel,
                entry_points: $entry_points,
                wasm_key: $wasm_key,
                wasm_hash: $wasm_hash,
                submitter_id: $submitter_id,
                invocation_count: 0,
                failure_count: 0,
                avg_execution_ms: 0,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at)
            })
            RETURN o
        """, {
            "id": str(overlay_id),
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "state": OverlayState.PENDING.value,
            "trust_level": trust_level.value,
            "capabilities": [c.model_dump() for c in manifest.capabilities],
            "max_memory_mb": manifest.max_memory_mb,
            "max_execution_ms": manifest.max_execution_ms,
            "max_fuel": manifest.max_fuel,
            "entry_points": manifest.entry_points,
            "wasm_key": wasm_key,
            "wasm_hash": wasm_hash,
            "submitter_id": str(submitter_id),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })
        
        return self._map_to_overlay(dict(result["o"]))
    
    async def get_by_id(self, overlay_id: UUID) -> Overlay | None:
        """Get overlay by ID."""
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {id: $id})
            RETURN o
        """, {"id": str(overlay_id)})
        
        if not result:
            return None
        return self._map_to_overlay(dict(result["o"]))
    
    async def update_state(self, overlay_id: UUID, state: OverlayState) -> Overlay:
        """Update overlay state."""
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {id: $id})
            SET o.state = $state, o.updated_at = datetime()
            RETURN o
        """, {"id": str(overlay_id), "state": state.value})
        
        return self._map_to_overlay(dict(result["o"]))
    
    async def record_invocation(
        self,
        overlay_id: UUID,
        success: bool,
        execution_time_ms: int,
        error: str | None,
    ) -> None:
        """Record invocation metrics."""
        await self._neo4j.run("""
            MATCH (o:Overlay {id: $id})
            SET o.invocation_count = o.invocation_count + 1,
                o.failure_count = o.failure_count + CASE WHEN $success THEN 0 ELSE 1 END,
                o.avg_execution_ms = (o.avg_execution_ms * o.invocation_count + $exec_time) / (o.invocation_count + 1),
                o.last_invoked_at = datetime(),
                o.last_error = CASE WHEN $success THEN o.last_error ELSE $error END,
                o.updated_at = datetime()
        """, {
            "id": str(overlay_id),
            "success": success,
            "exec_time": execution_time_ms,
            "error": error,
        })
    
    async def list_active(self) -> list[Overlay]:
        """List all active overlays."""
        results = await self._neo4j.run("""
            MATCH (o:Overlay {state: 'active'})
            RETURN o
            ORDER BY o.name
        """)
        return [self._map_to_overlay(dict(r["o"])) for r in results]
    
    def _map_to_overlay(self, data: dict) -> Overlay:
        """Map Neo4j record to Overlay model."""
        from forge.models.overlay import OverlayCapability
        
        capabilities = [
            OverlayCapability(**c) if isinstance(c, dict) else c
            for c in data.get("capabilities", [])
        ]
        
        return Overlay(
            id=UUID(data["id"]),
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            state=OverlayState(data["state"]),
            trust_level=TrustLevel(data["trust_level"]),
            capabilities=capabilities,
            max_memory_mb=data["max_memory_mb"],
            max_execution_ms=data["max_execution_ms"],
            max_fuel=data["max_fuel"],
            entry_points=data["entry_points"],
            wasm_key=data["wasm_key"],
            wasm_hash=data["wasm_hash"],
            invocation_count=data.get("invocation_count", 0),
            failure_count=data.get("failure_count", 0),
            avg_execution_ms=data.get("avg_execution_ms", 0),
        )
```

---

## 6. Object Storage Client

```python
# forge/infrastructure/storage/client.py
"""
Object storage client for binary files (WASM, attachments).

Supports S3-compatible storage (AWS S3, MinIO, etc.)
"""
import aioboto3
from botocore.config import Config

from forge.config import get_settings
from forge.logging import get_logger

logger = get_logger(__name__)


class ObjectStorageClient:
    """Async object storage client."""
    
    def __init__(
        self,
        endpoint_url: str | None = None,
        bucket: str = "forge-data",
        region: str = "us-east-1",
    ):
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._region = region
        self._session = aioboto3.Session()
    
    async def put(self, key: str, data: bytes) -> None:
        """Upload data to storage."""
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
        ) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
            )
        logger.debug("object_uploaded", key=key, size=len(data))
    
    async def get(self, key: str) -> bytes | None:
        """Download data from storage."""
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
            ) as s3:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
                data = await response["Body"].read()
                return data
        except Exception as e:
            logger.warning("object_not_found", key=key, error=str(e))
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete object from storage."""
        try:
            async with self._session.client(
                "s3",
                endpoint_url=self._endpoint_url,
                region_name=self._region,
            ) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=key)
                return True
        except Exception:
            return False
```

---

## 7. Next Steps

After completing Phase 3, proceed to **Phase 4: Governance** to implement:

- Proposal creation and lifecycle
- Trust-weighted voting
- Constitutional AI advisory
- Immune system (auto-healing)
