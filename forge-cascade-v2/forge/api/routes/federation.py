"""
Federation API Routes

REST API for managing federated peers and sync operations.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field

from forge.federation.models import (
    FederatedPeer,
    FederatedCapsule,
    SyncState,
    SyncDirection,
    PeerStatus,
    ConflictResolution,
    PeerHandshake,
    FederationStats,
    SyncOperationStatus,
    SyncPhase,
    SyncPayload,
)
from forge.federation.protocol import FederationProtocol
from forge.federation.sync import SyncService
from forge.federation.trust import PeerTrustManager
from forge.repositories.capsule_repository import CapsuleRepository
from forge.database.client import get_db_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/federation", tags=["Federation"])


# ============================================================================
# Request/Response Models
# ============================================================================

class PeerRegistrationRequest(BaseModel):
    """Request to register a new peer."""
    name: str = Field(description="Human-readable peer name")
    url: str = Field(description="Base URL of the peer's API")
    description: str | None = None
    admin_contact: str | None = None
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    sync_interval_minutes: int = Field(default=60, ge=5)
    conflict_resolution: ConflictResolution = ConflictResolution.HIGHER_TRUST
    sync_capsule_types: list[str] = Field(default_factory=list)
    min_trust_to_sync: int = Field(default=50, ge=0, le=100)


class PeerUpdateRequest(BaseModel):
    """Request to update peer settings."""
    name: str | None = None
    description: str | None = None
    admin_contact: str | None = None
    sync_direction: SyncDirection | None = None
    sync_interval_minutes: int | None = None
    conflict_resolution: ConflictResolution | None = None
    sync_capsule_types: list[str] | None = None
    min_trust_to_sync: int | None = None
    status: PeerStatus | None = None


class TrustAdjustmentRequest(BaseModel):
    """Request to manually adjust peer trust."""
    delta: float = Field(ge=-1.0, le=1.0)
    reason: str


class SyncTriggerRequest(BaseModel):
    """Request to trigger a sync."""
    direction: SyncDirection | None = None
    force: bool = False


class PeerResponse(BaseModel):
    """Response containing peer information."""
    id: str
    name: str
    url: str
    public_key: str
    trust_score: float
    trust_tier: str
    status: PeerStatus
    sync_direction: SyncDirection
    sync_interval_minutes: int
    conflict_resolution: ConflictResolution
    sync_capsule_types: list[str]
    min_trust_to_sync: int
    description: str | None
    admin_contact: str | None
    registered_at: datetime
    last_sync_at: datetime | None
    last_seen_at: datetime | None
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    capsules_received: int
    capsules_sent: int


class SyncStateResponse(BaseModel):
    """Response containing sync state."""
    id: str
    peer_id: str
    peer_name: str
    direction: SyncDirection
    started_at: datetime
    completed_at: datetime | None
    status: SyncOperationStatus
    phase: SyncPhase
    capsules_fetched: int
    capsules_created: int
    capsules_updated: int
    capsules_skipped: int
    capsules_conflicted: int
    edges_fetched: int
    edges_created: int
    edges_skipped: int
    error_message: str | None


class FederationStatsResponse(BaseModel):
    """Response containing federation statistics."""
    total_peers: int
    active_peers: int
    pending_peers: int
    total_federated_capsules: int
    synced_capsules: int
    pending_capsules: int
    conflicted_capsules: int
    total_federated_edges: int
    last_sync_at: datetime | None
    syncs_today: int
    syncs_failed_today: int
    network_health: dict[str, Any]


# ============================================================================
# Dependency Injection (would be configured in app.py)
# ============================================================================

# Global instances (in production, use proper DI)
_protocol: FederationProtocol | None = None
_sync_service: SyncService | None = None
_trust_manager: PeerTrustManager | None = None


async def get_protocol() -> FederationProtocol:
    global _protocol
    if not _protocol:
        _protocol = FederationProtocol(
            instance_id=str(uuid.uuid4()),
            instance_name="Forge Instance"
        )
        await _protocol.initialize()
    return _protocol


async def get_trust_manager() -> PeerTrustManager:
    global _trust_manager
    if not _trust_manager:
        _trust_manager = PeerTrustManager()
    return _trust_manager


async def get_sync_service() -> SyncService:
    global _sync_service
    if not _sync_service:
        protocol = await get_protocol()
        trust_manager = await get_trust_manager()
        capsule_repo = await get_capsule_repository()
        _sync_service = SyncService(
            protocol=protocol,
            trust_manager=trust_manager,
            capsule_repository=capsule_repo,
            neo4j_driver=None,  # TODO: Inject if needed for raw queries
        )
    return _sync_service


_capsule_repository: CapsuleRepository | None = None


async def get_capsule_repository() -> CapsuleRepository:
    """Get capsule repository for federation operations."""
    global _capsule_repository
    if not _capsule_repository:
        db_client = await get_db_client()
        _capsule_repository = CapsuleRepository(db_client)
    return _capsule_repository


# ============================================================================
# Peer Management Routes
# ============================================================================

@router.post("/peers", response_model=PeerResponse)
async def register_peer(
    request: PeerRegistrationRequest,
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """
    Register a new federated peer.

    This initiates a handshake with the remote peer to exchange public keys
    and establish trust.
    """
    # Attempt handshake with peer
    handshake_result = await protocol.initiate_handshake(request.url)

    if not handshake_result:
        raise HTTPException(
            status_code=400,
            detail="Failed to establish handshake with peer"
        )

    our_handshake, their_handshake = handshake_result

    # Create peer record (id generated automatically via default_factory)
    peer = FederatedPeer(
        name=request.name,
        url=request.url,
        public_key=their_handshake.public_key,
        our_public_key=our_handshake.public_key,
        trust_score=0.3,  # Initial trust
        status=PeerStatus.PENDING,
        sync_direction=request.sync_direction,
        sync_interval_minutes=request.sync_interval_minutes,
        conflict_resolution=request.conflict_resolution,
        sync_capsule_types=request.sync_capsule_types,
        min_trust_to_sync=request.min_trust_to_sync,
        description=request.description,
        admin_contact=request.admin_contact,
    )

    # Initialize trust
    await trust_manager.initialize_peer_trust(peer)

    # Register with sync service
    await sync_service.register_peer(peer)

    # Set to active after successful handshake
    peer.status = PeerStatus.ACTIVE
    peer.last_seen_at = datetime.now(timezone.utc)

    trust_tier = await trust_manager.get_trust_tier(peer)

    logger.info(f"Registered new peer: {peer.name} ({peer.id})")

    return PeerResponse(
        id=peer.id,
        name=peer.name,
        url=peer.url,
        public_key=peer.public_key,
        trust_score=peer.trust_score,
        trust_tier=trust_tier,
        status=peer.status,
        sync_direction=peer.sync_direction,
        sync_interval_minutes=peer.sync_interval_minutes,
        conflict_resolution=peer.conflict_resolution,
        sync_capsule_types=peer.sync_capsule_types,
        min_trust_to_sync=peer.min_trust_to_sync,
        description=peer.description,
        admin_contact=peer.admin_contact,
        registered_at=peer.registered_at,
        last_sync_at=peer.last_sync_at,
        last_seen_at=peer.last_seen_at,
        total_syncs=peer.total_syncs,
        successful_syncs=peer.successful_syncs,
        failed_syncs=peer.failed_syncs,
        capsules_received=peer.capsules_received,
        capsules_sent=peer.capsules_sent,
    )


@router.get("/peers", response_model=list[PeerResponse])
async def list_peers(
    status: PeerStatus | None = None,
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """List all registered peers, optionally filtered by status."""
    peers = await sync_service.list_peers()

    if status:
        peers = [p for p in peers if p.status == status]

    responses = []
    for peer in peers:
        trust_tier = await trust_manager.get_trust_tier(peer)
        responses.append(PeerResponse(
            id=peer.id,
            name=peer.name,
            url=peer.url,
            public_key=peer.public_key,
            trust_score=peer.trust_score,
            trust_tier=trust_tier,
            status=peer.status,
            sync_direction=peer.sync_direction,
            sync_interval_minutes=peer.sync_interval_minutes,
            conflict_resolution=peer.conflict_resolution,
            sync_capsule_types=peer.sync_capsule_types,
            min_trust_to_sync=peer.min_trust_to_sync,
            description=peer.description,
            admin_contact=peer.admin_contact,
            registered_at=peer.registered_at,
            last_sync_at=peer.last_sync_at,
            last_seen_at=peer.last_seen_at,
            total_syncs=peer.total_syncs,
            successful_syncs=peer.successful_syncs,
            failed_syncs=peer.failed_syncs,
            capsules_received=peer.capsules_received,
            capsules_sent=peer.capsules_sent,
        ))

    return responses


@router.get("/peers/{peer_id}", response_model=PeerResponse)
async def get_peer(
    peer_id: str,
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Get details for a specific peer."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    trust_tier = await trust_manager.get_trust_tier(peer)

    return PeerResponse(
        id=peer.id,
        name=peer.name,
        url=peer.url,
        public_key=peer.public_key,
        trust_score=peer.trust_score,
        trust_tier=trust_tier,
        status=peer.status,
        sync_direction=peer.sync_direction,
        sync_interval_minutes=peer.sync_interval_minutes,
        conflict_resolution=peer.conflict_resolution,
        sync_capsule_types=peer.sync_capsule_types,
        min_trust_to_sync=peer.min_trust_to_sync,
        description=peer.description,
        admin_contact=peer.admin_contact,
        registered_at=peer.registered_at,
        last_sync_at=peer.last_sync_at,
        last_seen_at=peer.last_seen_at,
        total_syncs=peer.total_syncs,
        successful_syncs=peer.successful_syncs,
        failed_syncs=peer.failed_syncs,
        capsules_received=peer.capsules_received,
        capsules_sent=peer.capsules_sent,
    )


@router.patch("/peers/{peer_id}", response_model=PeerResponse)
async def update_peer(
    peer_id: str,
    request: PeerUpdateRequest,
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Update peer settings."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    # Update fields
    if request.name is not None:
        peer.name = request.name
    if request.description is not None:
        peer.description = request.description
    if request.admin_contact is not None:
        peer.admin_contact = request.admin_contact
    if request.sync_direction is not None:
        peer.sync_direction = request.sync_direction
    if request.sync_interval_minutes is not None:
        peer.sync_interval_minutes = request.sync_interval_minutes
    if request.conflict_resolution is not None:
        peer.conflict_resolution = request.conflict_resolution
    if request.sync_capsule_types is not None:
        peer.sync_capsule_types = request.sync_capsule_types
    if request.min_trust_to_sync is not None:
        peer.min_trust_to_sync = request.min_trust_to_sync
    if request.status is not None:
        peer.status = request.status

    trust_tier = await trust_manager.get_trust_tier(peer)

    return PeerResponse(
        id=peer.id,
        name=peer.name,
        url=peer.url,
        public_key=peer.public_key,
        trust_score=peer.trust_score,
        trust_tier=trust_tier,
        status=peer.status,
        sync_direction=peer.sync_direction,
        sync_interval_minutes=peer.sync_interval_minutes,
        conflict_resolution=peer.conflict_resolution,
        sync_capsule_types=peer.sync_capsule_types,
        min_trust_to_sync=peer.min_trust_to_sync,
        description=peer.description,
        admin_contact=peer.admin_contact,
        registered_at=peer.registered_at,
        last_sync_at=peer.last_sync_at,
        last_seen_at=peer.last_seen_at,
        total_syncs=peer.total_syncs,
        successful_syncs=peer.successful_syncs,
        failed_syncs=peer.failed_syncs,
        capsules_received=peer.capsules_received,
        capsules_sent=peer.capsules_sent,
    )


@router.delete("/peers/{peer_id}")
async def remove_peer(
    peer_id: str,
    sync_service: SyncService = Depends(get_sync_service),
):
    """Remove a federated peer."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    await sync_service.unregister_peer(peer_id)
    logger.info(f"Removed peer: {peer.name} ({peer_id})")

    return {"message": f"Peer {peer.name} removed successfully"}


# ============================================================================
# Trust Management Routes
# ============================================================================

@router.post("/peers/{peer_id}/trust")
async def adjust_peer_trust(
    peer_id: str,
    request: TrustAdjustmentRequest,
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Manually adjust a peer's trust score."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    old_trust = peer.trust_score
    new_trust = await trust_manager.manual_adjustment(
        peer=peer,
        delta=request.delta,
        reason=request.reason,
        adjusted_by="api_user",  # TODO: Get from auth
    )

    return {
        "peer_id": peer_id,
        "old_trust": old_trust,
        "new_trust": new_trust,
        "delta": request.delta,
        "reason": request.reason,
    }


@router.get("/peers/{peer_id}/trust/history")
async def get_peer_trust_history(
    peer_id: str,
    limit: int = Query(default=50, le=200),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Get trust adjustment history for a peer."""
    history = await trust_manager.get_trust_history(peer_id, limit)

    return {
        "peer_id": peer_id,
        "events": [
            {
                "event_type": e.event_type,
                "delta": e.delta,
                "reason": e.reason,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in history
        ]
    }


@router.get("/peers/{peer_id}/trust/permissions")
async def get_peer_permissions(
    peer_id: str,
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Get sync permissions for a peer based on their trust tier."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    permissions = await trust_manager.get_sync_permissions(peer)
    return permissions


# ============================================================================
# Sync Routes
# ============================================================================

@router.post("/sync/{peer_id}", response_model=SyncStateResponse)
async def trigger_sync(
    peer_id: str,
    request: SyncTriggerRequest,
    sync_service: SyncService = Depends(get_sync_service),
):
    """Trigger a sync with a specific peer."""
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    state = await sync_service.sync_with_peer(
        peer_id=peer_id,
        direction=request.direction,
        force=request.force,
    )

    return SyncStateResponse(
        id=state.id,
        peer_id=state.peer_id,
        peer_name=peer.name,
        direction=state.direction,
        started_at=state.started_at,
        completed_at=state.completed_at,
        status=state.status,
        phase=state.phase,
        capsules_fetched=state.capsules_fetched,
        capsules_created=state.capsules_created,
        capsules_updated=state.capsules_updated,
        capsules_skipped=state.capsules_skipped,
        capsules_conflicted=state.capsules_conflicted,
        edges_fetched=state.edges_fetched,
        edges_created=state.edges_created,
        edges_skipped=state.edges_skipped,
        error_message=state.error_message,
    )


@router.post("/sync/all")
async def trigger_sync_all(
    sync_service: SyncService = Depends(get_sync_service),
):
    """Trigger sync with all active peers."""
    sync_ids = await sync_service.schedule_sync_all()
    return {
        "message": f"Triggered sync with {len(sync_ids)} peers",
        "sync_ids": sync_ids,
    }


@router.get("/sync/status")
async def get_sync_status(
    peer_id: str | None = None,
    limit: int = Query(default=20, le=100),
    sync_service: SyncService = Depends(get_sync_service),
):
    """Get recent sync history."""
    history = await sync_service.get_sync_history(peer_id, limit)

    return {
        "syncs": [
            {
                "id": s.id,
                "peer_id": s.peer_id,
                "direction": s.direction.value if isinstance(s.direction, SyncDirection) else s.direction,
                "status": s.status.value if isinstance(s.status, SyncOperationStatus) else s.status,
                "phase": s.phase.value if isinstance(s.phase, SyncPhase) else s.phase,
                "started_at": s.started_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "capsules_synced": s.capsules_created + s.capsules_updated,
                "error": s.error_message,
            }
            for s in history
        ]
    }


@router.get("/sync/{sync_id}", response_model=SyncStateResponse)
async def get_sync_details(
    sync_id: str,
    sync_service: SyncService = Depends(get_sync_service),
):
    """Get details for a specific sync operation."""
    state = await sync_service.get_sync_state(sync_id)
    if not state:
        raise HTTPException(status_code=404, detail="Sync not found")

    peer = await sync_service.get_peer(state.peer_id)
    peer_name = peer.name if peer else "Unknown"

    return SyncStateResponse(
        id=state.id,
        peer_id=state.peer_id,
        peer_name=peer_name,
        direction=state.direction,
        started_at=state.started_at,
        completed_at=state.completed_at,
        status=state.status,
        phase=state.phase,
        capsules_fetched=state.capsules_fetched,
        capsules_created=state.capsules_created,
        capsules_updated=state.capsules_updated,
        capsules_skipped=state.capsules_skipped,
        capsules_conflicted=state.capsules_conflicted,
        edges_fetched=state.edges_fetched,
        edges_created=state.edges_created,
        edges_skipped=state.edges_skipped,
        error_message=state.error_message,
    )


# ============================================================================
# Statistics Routes
# ============================================================================

@router.get("/stats", response_model=FederationStatsResponse)
async def get_federation_stats(
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
):
    """Get overall federation statistics."""
    peers = await sync_service.list_peers()
    stats = await trust_manager.get_federation_stats(peers)
    network_health = await trust_manager.calculate_network_trust(peers)

    return FederationStatsResponse(
        total_peers=stats.total_peers,
        active_peers=stats.active_peers,
        pending_peers=stats.pending_peers,
        total_federated_capsules=stats.total_federated_capsules,
        synced_capsules=stats.synced_capsules,
        pending_capsules=stats.pending_capsules,
        conflicted_capsules=stats.conflicted_capsules,
        total_federated_edges=stats.total_federated_edges,
        last_sync_at=stats.last_sync_at,
        syncs_today=stats.syncs_today,
        syncs_failed_today=stats.syncs_failed_today,
        network_health=network_health,
    )


# ============================================================================
# Incoming Routes (for other peers to call)
# ============================================================================

@router.post("/handshake")
async def handle_handshake(
    handshake: PeerHandshake,
    protocol: FederationProtocol = Depends(get_protocol),
):
    """
    Handle incoming handshake from a peer.
    Returns our handshake response.
    """
    # Verify their handshake
    if not protocol.verify_handshake(handshake):
        raise HTTPException(status_code=400, detail="Invalid handshake signature")

    # Create our response
    our_handshake = await protocol.create_handshake()

    return our_handshake.model_dump(mode='json')


@router.get("/health")
async def federation_health():
    """Health check endpoint for peers."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_version": FederationProtocol.API_VERSION,
    }


@router.get("/changes")
async def get_changes(
    since: datetime | None = None,
    types: str | None = None,
    limit: int = Query(default=100, le=1000),
    x_forge_signature: str = Header(None),
    x_forge_public_key: str = Header(None),
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    capsule_repo: CapsuleRepository = Depends(get_capsule_repository),
):
    """
    Get changes for a peer to pull.
    Requires signed request with valid peer public key.
    """
    if not x_forge_signature or not x_forge_public_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Forge-Signature or X-Forge-Public-Key header"
        )

    # Verify the request signature
    import json
    params = {"limit": limit}
    if since:
        params["since"] = since.isoformat()
    if types:
        params["types"] = types

    request_data = json.dumps(params, sort_keys=True).encode('utf-8')
    if not protocol.verify_signature(request_data, x_forge_signature, x_forge_public_key):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    # Verify peer is known and allowed to pull
    peer = await sync_service.get_peer_by_public_key(x_forge_public_key)
    if not peer:
        raise HTTPException(status_code=403, detail="Unknown peer")

    trust_manager = await get_trust_manager()
    can_sync, reason = await trust_manager.can_sync(peer)
    if not can_sync:
        raise HTTPException(status_code=403, detail=reason)

    permissions = await trust_manager.get_sync_permissions(peer)
    if not permissions.get("can_pull"):
        raise HTTPException(status_code=403, detail="Peer not authorized to pull")

    # Apply max_capsules_per_sync from permissions
    max_capsules = permissions.get("max_capsules_per_sync", 100)
    actual_limit = min(limit, max_capsules)

    # Parse types if provided
    type_list = types.split(",") if types else None

    # Query capsule changes since timestamp
    capsules, deleted_ids = await capsule_repo.get_changes_since(
        since=since,
        types=type_list,
        min_trust=peer.min_trust_to_sync,
        limit=actual_limit + 1,  # +1 to check if there's more
    )

    # Get edge changes
    edges = await capsule_repo.get_edges_since(since=since, limit=actual_limit)

    # Check if there are more results
    has_more = len(capsules) > actual_limit
    if has_more:
        capsules = capsules[:actual_limit]

    # Convert capsules to dict format for federation
    capsule_dicts = [
        {
            "id": c.id,
            "content": c.content,
            "type": c.type.value if hasattr(c.type, 'value') else c.type,
            "title": c.title,
            "summary": c.summary,
            "tags": c.tags,
            "trust_level": c.trust_level,
            "owner_id": c.owner_id,
            "parent_id": c.parent_id,
            "version": c.version,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "content_hash": hash(c.content) if c.content else None,  # Simple hash for now
        }
        for c in capsules
    ]

    logger.info(
        f"Federation get_changes: returning {len(capsule_dicts)} capsules, "
        f"{len(edges)} edges, {len(deleted_ids)} deletions for peer {peer.name}"
    )

    return {
        "capsules": capsule_dicts,
        "edges": edges,
        "deletions": deleted_ids,
        "has_more": has_more,
        "next_cursor": capsules[-1].updated_at.isoformat() if has_more and capsules else None,
    }


@router.post("/incoming/capsules")
async def receive_capsules(
    payload: SyncPayload,
    x_forge_public_key: str = Header(None),
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    capsule_repo: CapsuleRepository = Depends(get_capsule_repository),
):
    """
    Receive capsules pushed from a peer.
    Verifies signature before processing.
    """
    if not x_forge_public_key:
        raise HTTPException(status_code=401, detail="Missing X-Forge-Public-Key header")

    # Verify signature over payload
    payload_copy = payload.model_copy()
    payload_copy.signature = ""
    payload_json = payload_copy.model_dump_json()

    if not protocol.verify_signature(
        payload_json.encode('utf-8'),
        payload.signature,
        x_forge_public_key
    ):
        raise HTTPException(status_code=401, detail="Invalid payload signature")

    # Find the peer by public key
    peer = await sync_service.get_peer_by_public_key(x_forge_public_key)
    if not peer:
        raise HTTPException(status_code=403, detail="Unknown peer")

    # Check if peer is allowed to push
    trust_manager = await get_trust_manager()
    can_sync, reason = await trust_manager.can_sync(peer)
    if not can_sync:
        raise HTTPException(status_code=403, detail=reason)

    permissions = await trust_manager.get_sync_permissions(peer)
    if not permissions.get("can_push"):
        raise HTTPException(status_code=403, detail="Peer not authorized to push")

    # Process incoming capsules
    accepted = 0
    rejected = 0
    conflicts = 0

    from forge.models.capsule import CapsuleCreate
    from forge.models.base import CapsuleType

    for remote_capsule in payload.capsules:
        try:
            remote_id = remote_capsule.get("id")
            if not remote_id:
                rejected += 1
                continue

            # Check trust threshold
            remote_trust = remote_capsule.get("trust_level", 0)
            if remote_trust < peer.min_trust_to_sync:
                logger.debug(f"Skipping capsule {remote_id}: trust {remote_trust} < {peer.min_trust_to_sync}")
                rejected += 1
                continue

            # Check if capsule already exists locally (by checking federated records)
            fed_capsule = await sync_service._find_federated_capsule(peer.id, remote_id)

            if fed_capsule and fed_capsule.local_capsule_id:
                # Capsule exists - check for conflict
                local = await capsule_repo.get_by_id(fed_capsule.local_capsule_id)
                if local:
                    remote_hash = remote_capsule.get("content_hash")
                    local_hash = hash(local.content) if local.content else None

                    if remote_hash != local_hash:
                        # Conflict - resolve based on policy
                        if peer.conflict_resolution == ConflictResolution.REMOTE_WINS:
                            # Update local capsule
                            from forge.models.capsule import CapsuleUpdate
                            update_data = CapsuleUpdate(
                                content=remote_capsule.get("content"),
                                title=remote_capsule.get("title"),
                                summary=remote_capsule.get("summary"),
                                tags=remote_capsule.get("tags"),
                            )
                            await capsule_repo.update(fed_capsule.local_capsule_id, update_data)
                            accepted += 1
                        elif peer.conflict_resolution == ConflictResolution.HIGHER_TRUST:
                            if remote_trust > (local.trust_level or 0):
                                from forge.models.capsule import CapsuleUpdate
                                update_data = CapsuleUpdate(
                                    content=remote_capsule.get("content"),
                                    title=remote_capsule.get("title"),
                                )
                                await capsule_repo.update(fed_capsule.local_capsule_id, update_data)
                                accepted += 1
                            else:
                                conflicts += 1
                        else:
                            # LOCAL_WINS or MANUAL_REVIEW - record conflict
                            conflicts += 1
                    else:
                        # No change
                        accepted += 1
                else:
                    rejected += 1
            else:
                # New capsule - create local copy
                try:
                    capsule_type = remote_capsule.get("type", "KNOWLEDGE")
                    if isinstance(capsule_type, str):
                        try:
                            capsule_type = CapsuleType(capsule_type)
                        except ValueError:
                            capsule_type = CapsuleType.KNOWLEDGE

                    create_data = CapsuleCreate(
                        content=remote_capsule.get("content", ""),
                        type=capsule_type,
                        title=remote_capsule.get("title"),
                        summary=remote_capsule.get("summary"),
                        tags=remote_capsule.get("tags", []),
                        parent_id=None,  # Don't preserve remote parent relationships
                    )

                    # Create with a federation system user
                    new_capsule = await capsule_repo.create(
                        data=create_data,
                        owner_id=f"federation:{peer.id}",
                    )

                    # Track the federation mapping
                    await sync_service._create_local_capsule(peer, remote_capsule)

                    accepted += 1
                    logger.info(f"Created federated capsule {new_capsule.id} from peer {peer.name}")
                except Exception as e:
                    logger.error(f"Failed to create capsule from {remote_id}: {e}")
                    rejected += 1

        except Exception as e:
            logger.error(f"Error processing incoming capsule: {e}")
            rejected += 1

    # Update peer stats
    peer.capsules_received += accepted
    peer.last_seen_at = datetime.now(timezone.utc)

    logger.info(
        f"Federation receive_capsules from {peer.name}: "
        f"{accepted} accepted, {rejected} rejected, {conflicts} conflicts"
    )

    return {
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": conflicts,
    }
