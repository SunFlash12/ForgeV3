"""
Federation API Routes

REST API for managing federated peers and sync operations.

SECURITY FIX (Audit 2):
- Added authentication to peer management routes
- Require admin role for peer registration/modification/deletion
- Added rate limiting to public federation endpoints

SECURITY FIX (Audit 3):
- Replaced Python hash() with SHA-256 for content integrity
"""

import hashlib
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any


def _compute_content_hash(content: str | None) -> str | None:
    """
    SECURITY FIX (Audit 3): Compute SHA-256 hash for content integrity.

    Uses cryptographic hash instead of Python's hash() which:
    - Is not consistent across Python sessions
    - Is not cryptographically secure
    - Could lead to hash collisions

    Args:
        content: The content string to hash

    Returns:
        Hexadecimal SHA-256 hash or None if content is None
    """
    if content is None:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from forge.api.dependencies import get_current_active_user
from forge.database.client import get_db_client
from forge.federation.models import (
    ConflictResolution,
    FederatedPeer,
    PeerHandshake,
    PeerStatus,
    SyncDirection,
    SyncOperationStatus,
    SyncPayload,
    SyncPhase,
)
from forge.federation.protocol import FederationProtocol
from forge.federation.sync import SyncService
from forge.federation.trust import PeerTrustManager
from forge.models.user import User
from forge.repositories.capsule_repository import CapsuleRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/federation", tags=["Federation"])


# ============================================================================
# SECURITY FIX (Audit 2): Rate Limiting for Federation Endpoints
# ============================================================================


class FederationRateLimiter:
    """
    Rate limiter for federation endpoints.

    Applies stricter limits to prevent abuse from external peers.
    Uses in-memory storage (for distributed deployments, use Redis).

    SECURITY FIX (Audit 3): Added trust-based rate limits per peer.
    """

    # Trust-based rate limit multipliers
    TRUST_RATE_MULTIPLIERS = {
        "core": 3.0,  # 0.8-1.0 trust: 3x normal limits
        "trusted": 2.0,  # 0.6-0.8 trust: 2x normal limits
        "standard": 1.0,  # 0.4-0.6 trust: normal limits
        "limited": 0.5,  # 0.2-0.4 trust: 50% limits
        "quarantine": 0.1,  # 0.0-0.2 trust: 10% limits (nearly blocked)
    }

    def __init__(
        self,
        requests_per_minute: int = 30,
        requests_per_hour: int = 500,
        handshake_per_hour: int = 10,  # Stricter for handshakes
        sync_per_hour: int = 60,  # SECURITY FIX (Audit 3): Sync-specific limit
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.handshake_per_hour = handshake_per_hour
        self.sync_per_hour = sync_per_hour
        self._minute_counts: dict[str, tuple[float, int]] = {}
        self._hour_counts: dict[str, tuple[float, int]] = {}
        self._handshake_counts: dict[str, tuple[float, int]] = {}
        self._sync_counts: dict[str, tuple[float, int]] = {}  # SECURITY FIX (Audit 3)
        self._peer_trust_levels: dict[str, float] = {}  # SECURITY FIX (Audit 3)

    def _get_client_key(self, request: Request, public_key: str | None = None) -> str:
        """Get rate limit key from peer public key or IP."""
        if public_key:
            return f"peer:{public_key[:32]}"
        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        if request.client:
            return f"ip:{request.client.host}"
        return "ip:unknown"

    def set_peer_trust(self, public_key: str, trust_score: float) -> None:
        """
        SECURITY FIX (Audit 3): Set peer trust level for rate limit adjustment.

        Args:
            public_key: Peer's public key
            trust_score: Trust score (0.0-1.0)
        """
        key = f"peer:{public_key[:32]}"
        self._peer_trust_levels[key] = trust_score
        logger.debug(f"Set trust level for {key}: {trust_score}")

    def _get_trust_multiplier(self, key: str) -> float:
        """
        SECURITY FIX (Audit 3): Get rate limit multiplier based on trust.

        Higher trust = higher limits (up to 3x for core peers).
        """
        trust_score = self._peer_trust_levels.get(key, 0.3)  # Default to low trust

        if trust_score >= 0.8:
            return self.TRUST_RATE_MULTIPLIERS["core"]
        elif trust_score >= 0.6:
            return self.TRUST_RATE_MULTIPLIERS["trusted"]
        elif trust_score >= 0.4:
            return self.TRUST_RATE_MULTIPLIERS["standard"]
        elif trust_score >= 0.2:
            return self.TRUST_RATE_MULTIPLIERS["limited"]
        else:
            return self.TRUST_RATE_MULTIPLIERS["quarantine"]

    def check_rate_limit(
        self,
        request: Request,
        public_key: str | None = None,
        is_handshake: bool = False,
        is_sync: bool = False,  # SECURITY FIX (Audit 3): Sync-specific limit
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limits.

        SECURITY FIX (Audit 3): Now applies trust-based rate multipliers.

        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        key = self._get_client_key(request, public_key)

        # SECURITY FIX (Audit 3): Get trust-based rate multiplier
        trust_multiplier = self._get_trust_multiplier(key)
        adjusted_minute_limit = int(self.requests_per_minute * trust_multiplier)
        adjusted_hour_limit = int(self.requests_per_hour * trust_multiplier)
        adjusted_sync_limit = int(self.sync_per_hour * trust_multiplier)

        # Check minute limit
        if key in self._minute_counts:
            window_start, count = self._minute_counts[key]
            if now - window_start < 60:
                if count >= adjusted_minute_limit:
                    logger.warning(
                        f"Federation minute rate limit exceeded for {key} (trust: {trust_multiplier}x)"
                    )
                    return False, int(60 - (now - window_start))
            else:
                self._minute_counts[key] = (now, 0)

        # Check hour limit
        if key in self._hour_counts:
            window_start, count = self._hour_counts[key]
            if now - window_start < 3600:
                if count >= adjusted_hour_limit:
                    logger.warning(
                        f"Federation hour rate limit exceeded for {key} (trust: {trust_multiplier}x)"
                    )
                    return False, int(3600 - (now - window_start))
            else:
                self._hour_counts[key] = (now, 0)

        # SECURITY FIX (Audit 3): Check sync-specific limit
        if is_sync:
            if key in self._sync_counts:
                window_start, count = self._sync_counts[key]
                if now - window_start < 3600:
                    if count >= adjusted_sync_limit:
                        logger.warning(f"Federation sync rate limit exceeded for {key}")
                        return False, int(3600 - (now - window_start))
                else:
                    self._sync_counts[key] = (now, 0)

        # Special stricter limit for handshakes
        if is_handshake:
            if key in self._handshake_counts:
                window_start, count = self._handshake_counts[key]
                if now - window_start < 3600:
                    if count >= self.handshake_per_hour:
                        logger.warning(f"Federation handshake rate limit exceeded for {key}")
                        return False, int(3600 - (now - window_start))
                else:
                    self._handshake_counts[key] = (now, 0)

        # Increment counters
        if key not in self._minute_counts:
            self._minute_counts[key] = (now, 0)
        if key not in self._hour_counts:
            self._hour_counts[key] = (now, 0)
        if is_handshake and key not in self._handshake_counts:
            self._handshake_counts[key] = (now, 0)
        # SECURITY FIX (Audit 3): Track sync counts
        if is_sync and key not in self._sync_counts:
            self._sync_counts[key] = (now, 0)

        _, minute_count = self._minute_counts[key]
        self._minute_counts[key] = (self._minute_counts[key][0], minute_count + 1)

        _, hour_count = self._hour_counts[key]
        self._hour_counts[key] = (self._hour_counts[key][0], hour_count + 1)

        if is_handshake:
            _, handshake_count = self._handshake_counts[key]
            self._handshake_counts[key] = (self._handshake_counts[key][0], handshake_count + 1)

        # SECURITY FIX (Audit 3): Increment sync counter
        if is_sync:
            _, sync_count = self._sync_counts[key]
            self._sync_counts[key] = (self._sync_counts[key][0], sync_count + 1)

        return True, 0


# Global rate limiter instance
_federation_rate_limiter = FederationRateLimiter()


async def check_federation_rate_limit(
    request: Request,
    x_forge_public_key: str | None = Header(default=None),
) -> None:
    """Dependency to check federation rate limits."""
    is_handshake = request.url.path.endswith("/handshake")
    allowed, retry_after = _federation_rate_limiter.check_rate_limit(
        request, x_forge_public_key, is_handshake
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Federation rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


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
            instance_id=str(uuid.uuid4()), instance_name="Forge Instance"
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

# Type alias for admin user dependency
AdminUserDep = Annotated[User, Depends(get_current_active_user)]


def require_admin_role(user: User) -> None:
    """Verify user has admin role. Raises HTTPException if not."""
    if user.role not in ("admin", "system"):
        raise HTTPException(
            status_code=403, detail="Admin privileges required for federation management"
        )


@router.post("/peers", response_model=PeerResponse)
async def register_peer(
    request: PeerRegistrationRequest,
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> PeerResponse:
    """
    Register a new federated peer.

    This initiates a handshake with the remote peer to exchange public keys
    and establish trust.

    Requires admin authentication.
    """
    # SECURITY FIX: Require admin role for peer registration
    require_admin_role(current_user)
    # Attempt handshake with peer
    handshake_result = await protocol.initiate_handshake(request.url)

    if not handshake_result:
        raise HTTPException(status_code=400, detail="Failed to establish handshake with peer")

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
    peer.last_seen_at = datetime.now(UTC)

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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    status: PeerStatus | None = None,
    # SECURITY FIX (Audit 7 - Session 3): Added pagination to prevent unbounded queries
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> list[PeerResponse]:
    """List all registered peers, optionally filtered by status."""
    peers = await sync_service.list_peers()

    if status:
        peers = [p for p in peers if p.status == status]

    # SECURITY FIX (Audit 7 - Session 3): Apply pagination bounds
    peers = peers[offset : offset + limit]

    responses = []
    for peer in peers:
        trust_tier = await trust_manager.get_trust_tier(peer)
        responses.append(
            PeerResponse(
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
        )

    return responses


@router.get("/peers/{peer_id}", response_model=PeerResponse)
async def get_peer(
    peer_id: str,
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> PeerResponse:
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> PeerResponse:
    """Update peer settings. Requires admin authentication."""
    # SECURITY FIX: Require admin role for peer modification
    require_admin_role(current_user)
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
) -> dict[str, str]:
    """Remove a federated peer. Requires admin authentication."""
    # SECURITY FIX: Require admin role for peer removal
    require_admin_role(current_user)
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> dict[str, Any]:
    """Manually adjust a peer's trust score. Requires admin authentication."""
    # SECURITY FIX: Require admin role for trust adjustment
    require_admin_role(current_user)
    peer = await sync_service.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    old_trust = peer.trust_score
    new_trust = await trust_manager.manual_adjustment(
        peer=peer,
        delta=request.delta,
        reason=request.reason,
        adjusted_by=current_user.username,  # Use authenticated user
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    limit: int = Query(
        default=50, ge=1, le=200
    ),  # SECURITY FIX (Audit 7 - Session 3): Added lower bound
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> dict[str, Any]:
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
        ],
    }


@router.get("/peers/{peer_id}/trust/permissions")
async def get_peer_permissions(
    peer_id: str,
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> dict[str, Any]:
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
) -> SyncStateResponse:
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
) -> dict[str, Any]:
    """Trigger sync with all active peers."""
    sync_ids = await sync_service.schedule_sync_all()
    return {
        "message": f"Triggered sync with {len(sync_ids)} peers",
        "sync_ids": sync_ids,
    }


@router.get("/sync/status")
async def get_sync_status(
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    peer_id: str | None = None,
    limit: int = Query(
        default=20, ge=1, le=100
    ),  # SECURITY FIX (Audit 7 - Session 3): Added lower bound
    sync_service: SyncService = Depends(get_sync_service),
) -> dict[str, Any]:
    """Get recent sync history."""
    history = await sync_service.get_sync_history(peer_id, limit)

    return {
        "syncs": [
            {
                "id": s.id,
                "peer_id": s.peer_id,
                "direction": s.direction.value
                if isinstance(s.direction, SyncDirection)
                else s.direction,
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
) -> SyncStateResponse:
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
    current_user: AdminUserDep,  # SECURITY FIX: Require authentication
    sync_service: SyncService = Depends(get_sync_service),
    trust_manager: PeerTrustManager = Depends(get_trust_manager),
) -> FederationStatsResponse:
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


@router.post("/handshake", dependencies=[Depends(check_federation_rate_limit)])
async def handle_handshake(
    handshake: PeerHandshake,
    protocol: FederationProtocol = Depends(get_protocol),
) -> dict[str, Any]:
    """
    Handle incoming handshake from a peer.
    Returns our handshake response.
    """
    # Verify their handshake
    if not protocol.verify_handshake(handshake):
        raise HTTPException(status_code=400, detail="Invalid handshake signature")

    # Create our response
    our_handshake = await protocol.create_handshake()

    return our_handshake.model_dump(mode="json")


@router.get("/health", dependencies=[Depends(check_federation_rate_limit)])
async def federation_health() -> dict[str, Any]:
    """Health check endpoint for peers."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "api_version": FederationProtocol.API_VERSION,
    }


@router.get("/changes", dependencies=[Depends(check_federation_rate_limit)])
async def get_changes(
    since: datetime | None = None,
    types: str | None = None,
    limit: int = Query(default=100, ge=1, le=100),  # SECURITY FIX (Audit 5): Reduced from 1000
    x_forge_signature: str = Header(None),
    x_forge_public_key: str = Header(None),
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    capsule_repo: CapsuleRepository = Depends(get_capsule_repository),
) -> dict[str, Any]:
    """
    Get changes for a peer to pull.
    Requires signed request with valid peer public key.
    """
    if not x_forge_signature or not x_forge_public_key:
        raise HTTPException(
            status_code=401, detail="Missing X-Forge-Signature or X-Forge-Public-Key header"
        )

    # Verify the request signature
    import json

    params: dict[str, int | str] = {"limit": limit}
    if since:
        params["since"] = since.isoformat()
    if types:
        params["types"] = types

    request_data = json.dumps(params, sort_keys=True).encode("utf-8")
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
            "type": c.type.value if hasattr(c.type, "value") else c.type,
            "title": c.title,
            "summary": c.summary,
            "tags": c.tags,
            "trust_level": c.trust_level,
            "owner_id": c.owner_id,
            "parent_id": c.parent_id,
            "version": c.version,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "content_hash": _compute_content_hash(c.content),  # SECURITY FIX (Audit 3): SHA-256
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


@router.post("/incoming/capsules", dependencies=[Depends(check_federation_rate_limit)])
async def receive_capsules(
    payload: SyncPayload,
    x_forge_public_key: str = Header(None),
    protocol: FederationProtocol = Depends(get_protocol),
    sync_service: SyncService = Depends(get_sync_service),
    capsule_repo: CapsuleRepository = Depends(get_capsule_repository),
) -> dict[str, int]:
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
        payload_json.encode("utf-8"), payload.signature, x_forge_public_key
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

    from forge.models.base import CapsuleType
    from forge.models.capsule import CapsuleCreate

    for remote_capsule in payload.capsules:
        try:
            remote_id = remote_capsule.get("id")
            if not remote_id:
                rejected += 1
                continue

            # Check trust threshold
            remote_trust = remote_capsule.get("trust_level", 0)
            if remote_trust < peer.min_trust_to_sync:
                logger.debug(
                    f"Skipping capsule {remote_id}: trust {remote_trust} < {peer.min_trust_to_sync}"
                )
                rejected += 1
                continue

            # Check if capsule already exists locally (by checking federated records)
            fed_capsule = await sync_service._find_federated_capsule(peer.id, remote_id)

            if fed_capsule and fed_capsule.local_capsule_id:
                # Capsule exists - check for conflict
                local = await capsule_repo.get_by_id(fed_capsule.local_capsule_id)
                if local:
                    remote_hash = remote_capsule.get("content_hash")
                    # SECURITY FIX (Audit 3): Use SHA-256 for consistent hashing
                    local_hash = _compute_content_hash(local.content)

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
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.error(f"Failed to create capsule from {remote_id}: {e}")
                    rejected += 1

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error(f"Error processing incoming capsule: {e}")
            rejected += 1

    # Update peer stats
    peer.capsules_received += accepted
    peer.last_seen_at = datetime.now(UTC)

    logger.info(
        f"Federation receive_capsules from {peer.name}: "
        f"{accepted} accepted, {rejected} rejected, {conflicts} conflicts"
    )

    return {
        "accepted": accepted,
        "rejected": rejected,
        "conflicts": conflicts,
    }
