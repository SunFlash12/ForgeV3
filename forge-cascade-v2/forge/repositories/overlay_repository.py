"""
Overlay Repository

Manages overlay lifecycle, state transitions, metrics, and capability tracking.
Supports the WebAssembly isolation model with health monitoring.
"""

from typing import Any

import structlog
from pydantic import BaseModel

from forge.database.client import Neo4jClient
from forge.models.base import OverlayState, TrustLevel
from forge.models.overlay import (
    Capability,
    Overlay,
    OverlayExecution,
    OverlayHealthCheck,
    OverlayManifest,
    OverlayMetrics,
)
from forge.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class OverlayCreate(OverlayManifest):
    """Schema for registering an overlay."""
    pass


class OverlayUpdate(BaseModel):
    """Schema for updating an overlay."""

    name: str | None = None
    description: str | None = None
    version: str | None = None
    capabilities: set[Capability] | None = None
    trust_level: TrustLevel | None = None


class OverlayRepository(BaseRepository[Overlay, OverlayCreate, OverlayUpdate]):
    """
    Repository for overlay management.

    Handles overlay lifecycle:
    - Registration (REGISTERED)
    - Loading/Validation (LOADING)
    - Activation (ACTIVE)
    - Deactivation (INACTIVE)
    - Quarantine (QUARANTINED)
    """

    def __init__(self, client: Neo4jClient):
        super().__init__(client)

    @property
    def node_label(self) -> str:
        return "Overlay"

    @property
    def model_class(self) -> type[Overlay]:
        cls: type[Overlay] = Overlay
        return cls

    def _compute_content_hash(self, content: bytes) -> str:
        """
        SECURITY FIX (Audit 4 - H28): Compute SHA-256 hash of overlay content.

        Args:
            content: Raw overlay content (WASM bytecode or Python source)

        Returns:
            Hex string of SHA-256 hash
        """
        import hashlib
        return hashlib.sha256(content).hexdigest()

    async def create(  # type: ignore[override]
        self,
        data: OverlayCreate,
        wasm_content: bytes | None = None,
        **kwargs: Any,
    ) -> Overlay:
        """
        Register a new overlay.

        SECURITY FIX (Audit 4 - H28): Now verifies wasm_hash against actual
        WASM content before storing. This prevents hash manipulation attacks.

        Args:
            data: Overlay manifest/configuration
            wasm_content: Optional WASM bytecode for hash verification

        Returns:
            Registered overlay

        Raises:
            ValueError: If provided hash doesn't match computed hash
        """
        now = self._now().isoformat()
        overlay_id = data.id or self._generate_id()

        # SECURITY FIX (Audit 4 - H28): Verify WASM hash if content provided
        verified_hash = data.source_hash
        if wasm_content:
            computed_hash = self._compute_content_hash(wasm_content)
            if data.source_hash and data.source_hash != computed_hash:
                self.logger.error(
                    "wasm_hash_mismatch",
                    overlay_id=overlay_id,
                    claimed_hash=data.source_hash[:16] + "...",
                    computed_hash=computed_hash[:16] + "...",
                )
                raise ValueError(
                    f"WASM hash mismatch: claimed {data.source_hash[:16]}... "
                    f"but computed {computed_hash[:16]}..."
                )
            verified_hash = computed_hash
            self.logger.info(
                "wasm_hash_verified",
                overlay_id=overlay_id,
                hash=computed_hash[:16] + "..."
            )

        # Convert capabilities to list of strings for Neo4j
        capabilities_list = [c.value for c in data.capabilities]

        query = """
        CREATE (o:Overlay {
            id: $id,
            name: $name,
            description: $description,
            version: $version,
            state: $state,
            trust_level: $trust_level,
            capabilities: $capabilities,
            dependencies: $dependencies,
            wasm_hash: $wasm_hash,
            wasm_hash_verified: $hash_verified,
            created_at: $created_at,
            updated_at: $updated_at,

            // Metrics (embedded)
            total_executions: 0,
            successful_executions: 0,
            failed_executions: 0,
            total_execution_time_ms: 0.0,
            avg_execution_time_ms: 0.0,
            memory_used_bytes: 0,
            cpu_cycles_used: 0,
            health_checks_passed: 0,
            health_checks_failed: 0,
            consecutive_failures: 0
        })
        RETURN o {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": overlay_id,
                "name": data.name,
                "description": data.description,
                "version": data.version,
                "state": OverlayState.REGISTERED.value,
                "trust_level": TrustLevel.STANDARD.value,
                "capabilities": capabilities_list,
                "dependencies": data.dependencies,
                "wasm_hash": verified_hash,
                "hash_verified": wasm_content is not None,  # Track if hash was verified
                "created_at": now,
                "updated_at": now,
            },
        )

        self.logger.info(
            "Registered overlay",
            overlay_id=overlay_id,
            name=data.name,
            version=data.version,
        )

        if result is None:
            raise RuntimeError("Failed to create overlay")
        overlay = self._to_model(result["entity"])
        if overlay is None:
            raise RuntimeError("Failed to deserialize created overlay")
        return overlay

    async def update(
        self,
        entity_id: str,
        data: OverlayUpdate,
    ) -> Overlay | None:
        """
        Update overlay configuration.

        Args:
            entity_id: Overlay ID
            data: Update fields

        Returns:
            Updated overlay or None
        """
        # Build dynamic SET clause
        set_parts = ["o.updated_at = $now"]
        params: dict[str, Any] = {
            "id": entity_id,
            "now": self._now().isoformat(),
        }

        if data.name is not None:
            set_parts.append("o.name = $name")
            params["name"] = data.name

        if data.description is not None:
            set_parts.append("o.description = $description")
            params["description"] = data.description

        if data.version is not None:
            set_parts.append("o.version = $version")
            params["version"] = data.version

        if data.capabilities is not None:
            set_parts.append("o.capabilities = $capabilities")
            params["capabilities"] = [c.value for c in data.capabilities]

        if data.trust_level is not None:
            set_parts.append("o.trust_level = $trust_level")
            params["trust_level"] = data.trust_level.value

        query = f"""
        MATCH (o:Overlay {{id: $id}})
        SET {', '.join(set_parts)}
        RETURN o {{.*}} AS entity
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None

    # ═══════════════════════════════════════════════════════════════
    # STATE TRANSITIONS
    # ═══════════════════════════════════════════════════════════════

    async def set_state(
        self,
        overlay_id: str,
        new_state: OverlayState,
        reason: str | None = None,
    ) -> Overlay | None:
        """
        Transition overlay to a new state.

        Args:
            overlay_id: Overlay ID
            new_state: Target state
            reason: Optional reason for transition

        Returns:
            Updated overlay
        """
        now = self._now().isoformat()

        # Build state-specific updates
        extra_sets = []
        if new_state == OverlayState.ACTIVE:
            extra_sets.append("o.activated_at = $now")
        elif new_state in (OverlayState.INACTIVE, OverlayState.QUARANTINED):
            extra_sets.append("o.deactivated_at = $now")

        set_clause = "o.state = $state, o.updated_at = $now"
        if extra_sets:
            set_clause += ", " + ", ".join(extra_sets)

        query = f"""
        MATCH (o:Overlay {{id: $id}})
        SET {set_clause}
        RETURN o {{.*}} AS entity
        """

        result = await self.client.execute_single(
            query,
            {"id": overlay_id, "state": new_state.value, "now": now},
        )

        if result and result.get("entity"):
            self.logger.info(
                "Overlay state changed",
                overlay_id=overlay_id,
                new_state=new_state.value,
                reason=reason,
            )
            return self._to_model(result["entity"])
        return None

    async def activate(self, overlay_id: str) -> Overlay | None:
        """Activate an overlay."""
        return await self.set_state(overlay_id, OverlayState.ACTIVE)

    async def deactivate(self, overlay_id: str, reason: str | None = None) -> Overlay | None:
        """Deactivate an overlay."""
        return await self.set_state(overlay_id, OverlayState.INACTIVE, reason)

    async def quarantine(self, overlay_id: str, reason: str) -> Overlay | None:
        """Quarantine a misbehaving overlay."""
        self.logger.warning(
            "Quarantining overlay",
            overlay_id=overlay_id,
            reason=reason,
        )
        return await self.set_state(overlay_id, OverlayState.QUARANTINED, reason)

    async def recover(self, overlay_id: str) -> Overlay | None:
        """Recover a quarantined overlay to inactive state."""
        # Reset consecutive failures
        await self.client.execute_single(
            """
            MATCH (o:Overlay {id: $id})
            SET o.consecutive_failures = 0
            """,
            {"id": overlay_id},
        )
        return await self.set_state(overlay_id, OverlayState.INACTIVE, "Recovered from quarantine")

    # ═══════════════════════════════════════════════════════════════
    # METRICS & EXECUTION TRACKING
    # ═══════════════════════════════════════════════════════════════

    async def record_execution(
        self,
        overlay_id: str,
        execution: OverlayExecution,
    ) -> bool:
        """
        Record an overlay execution and update metrics.

        Args:
            overlay_id: Overlay ID
            execution: Execution details

        Returns:
            True if recorded
        """
        query = """
        MATCH (o:Overlay {id: $id})
        SET
            o.total_executions = o.total_executions + 1,
            o.successful_executions = CASE WHEN $success THEN o.successful_executions + 1 ELSE o.successful_executions END,
            o.failed_executions = CASE WHEN NOT $success THEN o.failed_executions + 1 ELSE o.failed_executions END,
            o.total_execution_time_ms = o.total_execution_time_ms + $exec_time,
            o.avg_execution_time_ms = (o.total_execution_time_ms + $exec_time) / (o.total_executions + 1),
            o.last_execution = $timestamp,
            o.last_error = CASE WHEN NOT $success THEN $error ELSE o.last_error END,
            o.last_error_time = CASE WHEN NOT $success THEN $timestamp ELSE o.last_error_time END,
            o.consecutive_failures = CASE WHEN $success THEN 0 ELSE o.consecutive_failures + 1 END,
            o.memory_used_bytes = CASE WHEN $memory > o.memory_used_bytes THEN $memory ELSE o.memory_used_bytes END,
            o.cpu_cycles_used = o.cpu_cycles_used + $fuel,
            o.updated_at = $timestamp
        RETURN o.consecutive_failures AS consecutive_failures
        """

        result = await self.client.execute_single(
            query,
            {
                "id": overlay_id,
                "success": execution.success,
                "exec_time": execution.execution_time_ms,
                "timestamp": execution.timestamp.isoformat(),
                "error": execution.error,
                "memory": execution.memory_used_bytes,
                "fuel": execution.fuel_used,
            },
        )

        # Check for auto-quarantine threshold
        if result:
            consecutive_failures = result.get("consecutive_failures", 0)
            if consecutive_failures >= 5:
                await self.quarantine(
                    overlay_id,
                    f"Auto-quarantine: {consecutive_failures} consecutive failures",
                )

        return result is not None

    async def record_health_check(
        self,
        overlay_id: str,
        health_check: OverlayHealthCheck,
    ) -> bool:
        """
        Record a health check result.

        Args:
            overlay_id: Overlay ID
            health_check: Health check result

        Returns:
            True if recorded
        """
        query = """
        MATCH (o:Overlay {id: $id})
        SET
            o.health_checks_passed = CASE WHEN $healthy THEN o.health_checks_passed + 1 ELSE o.health_checks_passed END,
            o.health_checks_failed = CASE WHEN NOT $healthy THEN o.health_checks_failed + 1 ELSE o.health_checks_failed END,
            o.updated_at = $timestamp
        RETURN o {.*} AS entity
        """

        result = await self.client.execute_single(
            query,
            {
                "id": overlay_id,
                "healthy": health_check.healthy,
                "timestamp": health_check.timestamp.isoformat(),
            },
        )

        return result is not None

    async def get_metrics(self, overlay_id: str) -> OverlayMetrics | None:
        """
        Get current metrics for an overlay.

        Args:
            overlay_id: Overlay ID

        Returns:
            Metrics object
        """
        query = """
        MATCH (o:Overlay {id: $id})
        RETURN {
            total_executions: o.total_executions,
            successful_executions: o.successful_executions,
            failed_executions: o.failed_executions,
            total_execution_time_ms: o.total_execution_time_ms,
            avg_execution_time_ms: o.avg_execution_time_ms,
            last_execution: o.last_execution,
            last_error: o.last_error,
            last_error_time: o.last_error_time,
            memory_used_bytes: o.memory_used_bytes,
            cpu_cycles_used: o.cpu_cycles_used,
            health_checks_passed: o.health_checks_passed,
            health_checks_failed: o.health_checks_failed,
            consecutive_failures: o.consecutive_failures
        } AS metrics
        """

        result = await self.client.execute_single(query, {"id": overlay_id})

        if result and result.get("metrics"):
            return OverlayMetrics.model_validate(result["metrics"])
        return None

    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════

    async def get_by_state(
        self,
        state: OverlayState,
        limit: int = 100,
    ) -> list[Overlay]:
        """Get overlays by state."""
        return await self.find_by_field("state", state.value, limit)

    async def get_active(self) -> list[Overlay]:
        """Get all active overlays."""
        return await self.get_by_state(OverlayState.ACTIVE)

    async def get_quarantined(self) -> list[Overlay]:
        """Get all quarantined overlays."""
        return await self.get_by_state(OverlayState.QUARANTINED)

    async def get_by_capability(
        self,
        capability: Capability,
        active_only: bool = True,
    ) -> list[Overlay]:
        """
        Get overlays that have a specific capability.

        Args:
            capability: Required capability
            active_only: Only return active overlays

        Returns:
            List of overlays
        """
        state_filter = "AND o.state = 'ACTIVE'" if active_only else ""

        query = f"""
        MATCH (o:Overlay)
        WHERE $capability IN o.capabilities {state_filter}
        RETURN o {{.*}} AS entity
        """

        results = await self.client.execute(
            query,
            {"capability": capability.value},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_by_trust_level(
        self,
        min_trust: TrustLevel,
    ) -> list[Overlay]:
        """Get overlays at or above a trust level."""
        query = """
        MATCH (o:Overlay)
        WHERE o.trust_level >= $trust
        RETURN o {.*} AS entity
        ORDER BY o.trust_level DESC
        """

        results = await self.client.execute(
            query,
            {"trust": min_trust.value},
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_dependencies(self, overlay_id: str) -> list[Overlay]:
        """
        Get overlays that this overlay depends on.

        Args:
            overlay_id: Overlay ID

        Returns:
            List of dependency overlays
        """
        query = """
        MATCH (o:Overlay {id: $id})
        WITH o.dependencies AS dep_ids
        UNWIND dep_ids AS dep_id
        MATCH (dep:Overlay {id: dep_id})
        RETURN dep {.*} AS entity
        """

        results = await self.client.execute(query, {"id": overlay_id})
        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_dependents(self, overlay_id: str) -> list[Overlay]:
        """
        Get overlays that depend on this overlay.

        Args:
            overlay_id: Overlay ID

        Returns:
            List of dependent overlays
        """
        query = """
        MATCH (o:Overlay)
        WHERE $id IN o.dependencies
        RETURN o {.*} AS entity
        """

        results = await self.client.execute(query, {"id": overlay_id})
        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_unhealthy(
        self,
        error_rate_threshold: float = 0.1,
        consecutive_failures_threshold: int = 3,
    ) -> list[Overlay]:
        """
        Get overlays that are unhealthy based on metrics.

        Args:
            error_rate_threshold: Max acceptable error rate
            consecutive_failures_threshold: Max consecutive failures

        Returns:
            List of unhealthy overlays
        """
        query = """
        MATCH (o:Overlay)
        WHERE o.state = 'ACTIVE'
        AND (
            o.consecutive_failures >= $failures_threshold
            OR (o.total_executions > 0 AND toFloat(o.failed_executions) / o.total_executions > $error_threshold)
        )
        RETURN o {.*} AS entity
        """

        results = await self.client.execute(
            query,
            {
                "failures_threshold": consecutive_failures_threshold,
                "error_threshold": error_rate_threshold,
            },
        )

        return self._to_models([r["entity"] for r in results if r.get("entity")])

    async def get_by_name(self, name: str) -> Overlay | None:
        """Get overlay by name."""
        query = """
        MATCH (o:Overlay {name: $name})
        RETURN o {.*} AS entity
        """
        result = await self.client.execute_single(query, {"name": name})
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None
