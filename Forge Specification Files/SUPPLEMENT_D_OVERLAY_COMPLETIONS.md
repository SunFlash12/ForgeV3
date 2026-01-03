# Forge V3 - Phase 3 Supplement: Overlay Completions

**Purpose:** Complete the overlay system with the missing OverlayServices class and full repository implementation.

**Files to update/create:**
- `forge/core/overlays/services.py` (new)
- `forge/core/overlays/repository.py` (additions)

---

## 1. OverlayServices Dataclass

This provides the bundled dependencies that host functions need access to.

```python
# forge/core/overlays/services.py
"""
OverlayServices - Dependency bundle for overlay execution.

Host functions in WASM modules need access to Forge services.
This dataclass bundles them together for clean injection.
"""
from dataclasses import dataclass
from typing import Protocol

from forge.core.capsules.service import CapsuleService
from forge.core.users.repository import UserRepository
from forge.models.overlay import Overlay
from forge.models.base import TrustLevel
from forge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OverlayServices:
    """
    Bundle of services available to overlay host functions.
    
    These services are accessed by WASM host functions when overlays
    request capabilities like reading capsules or searching knowledge.
    
    The actual access is mediated by the overlay's granted capabilities.
    """
    
    capsule_service: "CapsuleServiceForOverlay"
    user_repository: UserRepository
    
    @classmethod
    def create(
        cls,
        capsule_service: CapsuleService,
        user_repository: UserRepository,
    ) -> "OverlayServices":
        """
        Create OverlayServices with wrapped services.
        
        Services are wrapped to add overlay-specific constraints.
        """
        return cls(
            capsule_service=CapsuleServiceForOverlay(capsule_service),
            user_repository=user_repository,
        )


class CapsuleServiceForOverlay:
    """
    Capsule service wrapper for overlay access.
    
    Provides restricted methods that overlays can call through host functions.
    All methods respect the overlay's trust level.
    """
    
    def __init__(self, service: CapsuleService):
        self._service = service
    
    async def get_by_id_for_overlay(
        self,
        capsule_id: str,
        overlay_trust_level: TrustLevel,
    ) -> dict | None:
        """
        Get a capsule by ID, respecting overlay's trust level.
        
        Returns dict representation suitable for WASM serialization.
        """
        from uuid import UUID
        
        try:
            # Create a fake user with the overlay's trust level
            # This ensures trust level checking works correctly
            capsule = await self._service._repo.get_by_id(UUID(capsule_id))
            
            if not capsule:
                return None
            
            # Check trust level access
            if not overlay_trust_level.can_access(capsule.trust_level):
                logger.warning(
                    "overlay_capsule_access_denied",
                    capsule_id=capsule_id,
                    capsule_trust=capsule.trust_level.value,
                    overlay_trust=overlay_trust_level.value,
                )
                return None
            
            # Return serializable dict (no embedding to save bandwidth)
            return {
                "id": str(capsule.id),
                "content": capsule.content,
                "type": capsule.type.value,
                "trust_level": capsule.trust_level.value,
                "version": capsule.version,
                "metadata": capsule.metadata,
                "created_at": capsule.created_at.isoformat(),
            }
            
        except Exception as e:
            logger.error("overlay_get_capsule_error", error=str(e))
            return None
    
    async def search_for_overlay(
        self,
        query: str,
        overlay_trust_level: TrustLevel,
        limit: int = 10,
    ) -> list[dict]:
        """
        Search capsules for an overlay.
        
        Results are filtered to the overlay's trust level.
        """
        # Generate query embedding
        query_embedding = await self._service._embedding.generate(query)
        
        # Search with trust level filter
        results = await self._service._repo.search_by_embedding(
            embedding=query_embedding,
            limit=limit * 2,  # Get extra to account for filtering
            min_score=0.6,
        )
        
        # Filter by trust level and convert to dicts
        filtered = []
        for capsule, score in results:
            if overlay_trust_level.can_access(capsule.trust_level):
                filtered.append({
                    "capsule": {
                        "id": str(capsule.id),
                        "content": capsule.content[:500],  # Truncate for overlay
                        "type": capsule.type.value,
                        "trust_level": capsule.trust_level.value,
                    },
                    "score": score,
                })
            
            if len(filtered) >= limit:
                break
        
        return filtered
    
    async def create_from_overlay(
        self,
        content: str,
        capsule_type: str,
        metadata: dict,
        overlay: Overlay,
    ) -> dict:
        """
        Create a capsule from an overlay.
        
        The capsule inherits the overlay's trust level.
        """
        from forge.models.capsule import CapsuleCreate, CapsuleType
        from uuid import uuid4
        
        # Capsule created by overlay gets overlay's trust level
        data = CapsuleCreate(
            content=content,
            type=CapsuleType(capsule_type),
            metadata={
                **metadata,
                "created_by_overlay": str(overlay.id),
                "overlay_name": overlay.name,
            },
        )
        
        # Generate embedding
        embedding = await self._service._embedding.generate(content)
        
        # Create with overlay as owner (using a system user for this)
        # In practice you'd have a dedicated system user for overlay-created content
        capsule = await self._service._repo.create(
            data=data,
            owner_id=uuid4(),  # Would be overlay's system user ID
            embedding=embedding,
            trust_level=overlay.trust_level,
        )
        
        logger.info(
            "capsule_created_by_overlay",
            capsule_id=str(capsule.id),
            overlay_id=str(overlay.id),
        )
        
        return {
            "id": str(capsule.id),
            "type": capsule.type.value,
            "created_at": capsule.created_at.isoformat(),
        }
```

---

## 2. Complete Overlay Repository

Add these missing methods to the OverlayRepository:

```python
# Additional methods for forge/core/overlays/repository.py

from typing import Any
from datetime import datetime, timezone

class OverlayRepository:
    # ... existing methods from Phase 3 ...
    
    async def get_by_name_version(
        self,
        name: str,
        version: str,
    ) -> Overlay | None:
        """Get overlay by name and version combination."""
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {name: $name, version: $version})
            RETURN o
        """, {"name": name, "version": version})
        
        if not result:
            return None
        return self._map_to_overlay(dict(result["o"]))
    
    async def list_by_submitter(
        self,
        submitter_id: UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Overlay], int]:
        """
        List overlays submitted by a specific user.
        
        Returns (overlays, total_count).
        """
        params = {
            "submitter_id": str(submitter_id),
            "skip": (page - 1) * per_page,
            "limit": per_page,
        }
        
        # Get count
        count_result = await self._neo4j.run_single("""
            MATCH (o:Overlay {submitter_id: $submitter_id})
            RETURN count(o) as total
        """, params)
        total = count_result["total"] if count_result else 0
        
        # Get paginated results
        results = await self._neo4j.run("""
            MATCH (o:Overlay {submitter_id: $submitter_id})
            RETURN o
            ORDER BY o.created_at DESC
            SKIP $skip
            LIMIT $limit
        """, params)
        
        return [self._map_to_overlay(dict(r["o"])) for r in results], total
    
    async def list_by_state(
        self,
        state: OverlayState,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Overlay], int]:
        """List overlays filtered by state."""
        params = {
            "state": state.value,
            "skip": (page - 1) * per_page,
            "limit": per_page,
        }
        
        count_result = await self._neo4j.run_single("""
            MATCH (o:Overlay {state: $state})
            RETURN count(o) as total
        """, params)
        total = count_result["total"] if count_result else 0
        
        results = await self._neo4j.run("""
            MATCH (o:Overlay {state: $state})
            RETURN o
            ORDER BY o.name, o.version
            SKIP $skip
            LIMIT $limit
        """, params)
        
        return [self._map_to_overlay(dict(r["o"])) for r in results], total
    
    async def update_trust_level(
        self,
        overlay_id: UUID,
        trust_level: TrustLevel,
    ) -> Overlay:
        """Update an overlay's trust level."""
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {id: $id})
            SET o.trust_level = $trust_level,
                o.updated_at = datetime()
            RETURN o
        """, {
            "id": str(overlay_id),
            "trust_level": trust_level.value,
        })
        
        if not result:
            raise NotFoundError("Overlay", str(overlay_id))
        
        logger.info(
            "overlay_trust_updated",
            overlay_id=str(overlay_id),
            trust_level=trust_level.value,
        )
        return self._map_to_overlay(dict(result["o"]))
    
    async def get_health_metrics(
        self,
        overlay_id: UUID,
    ) -> dict:
        """
        Get detailed health metrics for an overlay.
        
        Returns statistics useful for monitoring and quarantine decisions.
        """
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {id: $id})
            RETURN o.invocation_count as total_invocations,
                   o.failure_count as total_failures,
                   o.avg_execution_ms as avg_execution_ms,
                   o.last_invoked_at as last_invoked_at,
                   o.last_error as last_error,
                   o.state as state,
                   CASE WHEN o.invocation_count > 0 
                        THEN toFloat(o.failure_count) / o.invocation_count 
                        ELSE 0 END as failure_rate
        """, {"id": str(overlay_id)})
        
        if not result:
            raise NotFoundError("Overlay", str(overlay_id))
        
        return {
            "total_invocations": result["total_invocations"],
            "total_failures": result["total_failures"],
            "avg_execution_ms": result["avg_execution_ms"],
            "last_invoked_at": result["last_invoked_at"],
            "last_error": result["last_error"],
            "state": result["state"],
            "failure_rate": result["failure_rate"],
        }
    
    async def get_all_quarantined(self) -> list[Overlay]:
        """Get all quarantined overlays for review."""
        results = await self._neo4j.run("""
            MATCH (o:Overlay {state: 'quarantined'})
            RETURN o
            ORDER BY o.updated_at DESC
        """)
        
        return [self._map_to_overlay(dict(r["o"])) for r in results]
    
    async def reset_metrics(self, overlay_id: UUID) -> None:
        """
        Reset invocation metrics for an overlay.
        
        Useful when releasing from quarantine to give it a fresh start.
        """
        await self._neo4j.run("""
            MATCH (o:Overlay {id: $id})
            SET o.invocation_count = 0,
                o.failure_count = 0,
                o.avg_execution_ms = 0,
                o.last_error = null,
                o.updated_at = datetime()
        """, {"id": str(overlay_id)})
        
        logger.info("overlay_metrics_reset", overlay_id=str(overlay_id))
    
    async def delete(self, overlay_id: UUID) -> bool:
        """
        Delete an overlay and its relationships.
        
        Should only be used for overlays that haven't been widely used.
        """
        result = await self._neo4j.run_single("""
            MATCH (o:Overlay {id: $id})
            DETACH DELETE o
            RETURN true as deleted
        """, {"id": str(overlay_id)})
        
        if result and result.get("deleted"):
            logger.info("overlay_deleted", overlay_id=str(overlay_id))
            return True
        return False
    
    async def search_by_name(
        self,
        name_pattern: str,
        limit: int = 20,
    ) -> list[Overlay]:
        """Search overlays by name pattern."""
        results = await self._neo4j.run("""
            MATCH (o:Overlay)
            WHERE o.name CONTAINS $pattern
            RETURN o
            ORDER BY o.name
            LIMIT $limit
        """, {"pattern": name_pattern.lower(), "limit": limit})
        
        return [self._map_to_overlay(dict(r["o"])) for r in results]
    
    async def get_by_capability(
        self,
        capability: str,
    ) -> list[Overlay]:
        """
        Find all active overlays that have a specific capability.
        
        Useful for auditing which overlays can do what.
        """
        results = await self._neo4j.run("""
            MATCH (o:Overlay {state: 'active'})
            WHERE any(cap IN o.capabilities WHERE cap.name = $capability)
            RETURN o
            ORDER BY o.name
        """, {"capability": capability})
        
        return [self._map_to_overlay(dict(r["o"])) for r in results]
```

---

## 3. Update Overlay Service to Use OverlayServices

```python
# Updates for forge/core/overlays/service.py

from forge.core.overlays.services import OverlayServices

class OverlayService:
    def __init__(
        self,
        repository: OverlayRepository,
        runtime: WasmRuntime,
        storage: ObjectStorageClient,
        overlay_services: OverlayServices | None = None,  # Add this
    ):
        self._repo = repository
        self._runtime = runtime
        self._storage = storage
        self._services = overlay_services  # Add this
    
    async def invoke(
        self,
        overlay_id: UUID,
        invocation: OverlayInvocation,
        user: User,
    ) -> OverlayResult:
        # ... existing validation code ...
        
        # Make sure services are available for host functions
        if not self._services:
            raise RuntimeError("OverlayServices not configured")
        
        # Update runtime to pass services
        result = await self._runtime.invoke(
            overlay=overlay,
            wasm_bytes=wasm_bytes,
            function_name=invocation.function,
            args=invocation.args,
            timeout_ms=invocation.timeout_ms,
            services=self._services,  # Add this parameter
        )
        
        # ... rest of method ...
```

---

## 4. Database Schema for Overlays

Add these to the schema initialization:

```python
# Add to forge/infrastructure/neo4j/schema.py SCHEMA_QUERIES

OVERLAY_SCHEMA_QUERIES = [
    # Overlay constraints
    "CREATE CONSTRAINT overlay_id_unique IF NOT EXISTS FOR (o:Overlay) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT overlay_name_version IF NOT EXISTS FOR (o:Overlay) REQUIRE (o.name, o.version) IS UNIQUE",
    
    # Overlay indexes
    "CREATE INDEX overlay_state_index IF NOT EXISTS FOR (o:Overlay) ON (o.state)",
    "CREATE INDEX overlay_trust_index IF NOT EXISTS FOR (o:Overlay) ON (o.trust_level)",
    "CREATE INDEX overlay_submitter_index IF NOT EXISTS FOR (o:Overlay) ON (o.submitter_id)",
    "CREATE INDEX overlay_name_index IF NOT EXISTS FOR (o:Overlay) ON (o.name)",
]
```
