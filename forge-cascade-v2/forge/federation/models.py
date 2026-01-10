"""
Federation Data Models

Defines the data structures for federated knowledge sharing between Forge instances.
"""

from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import Field, HttpUrl

from forge.models.base import ForgeModel, generate_id


class PeerStatus(str, Enum):
    """Status of a federated peer."""
    PENDING = "pending"          # Awaiting trust establishment
    ACTIVE = "active"            # Fully connected and syncing
    DEGRADED = "degraded"        # Connectivity issues
    SUSPENDED = "suspended"      # Manually suspended
    OFFLINE = "offline"          # Unreachable
    REVOKED = "revoked"          # Trust revoked


class SyncDirection(str, Enum):
    """Direction of sync operations."""
    PUSH = "push"                # Send to peer
    PULL = "pull"                # Receive from peer
    BIDIRECTIONAL = "bidirectional"


class ConflictResolution(str, Enum):
    """How to resolve sync conflicts."""
    HIGHER_TRUST = "higher_trust"      # Higher trust capsule wins
    NEWER_TIMESTAMP = "newer_timestamp"  # More recent wins
    MANUAL_REVIEW = "manual_review"      # Flag for human review
    MERGE = "merge"                      # Attempt to merge
    LOCAL_WINS = "local_wins"            # Always prefer local
    REMOTE_WINS = "remote_wins"          # Always prefer remote


class FederatedSyncStatus(str, Enum):
    """Status of a federated item sync."""
    PENDING = "pending"
    SYNCED = "synced"
    CONFLICT = "conflict"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class SyncOperationStatus(str, Enum):
    """Status of a sync operation."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncPhase(str, Enum):
    """Current phase of a sync operation."""
    INIT = "init"
    FETCHING = "fetching"
    PROCESSING = "processing"
    APPLYING = "applying"
    FINALIZING = "finalizing"


class FederatedPeer(ForgeModel):
    """
    A remote Forge instance that we can sync with.

    Trust is established through:
    1. Initial handshake with public key exchange
    2. Ghost Council review for untrusted peers
    3. Successful sync history increases trust
    """

    id: str = Field(default_factory=generate_id, description="Unique peer identifier")
    name: str = Field(description="Human-readable peer name")
    url: str = Field(description="Base URL of the peer's API (validated at API layer)")

    # Cryptographic identity
    public_key: str = Field(description="Peer's Ed25519 public key (base64)")
    our_public_key: str | None = Field(
        default=None,
        description="Our public key as registered with this peer"
    )

    # Trust & Status
    # Note: Peer trust uses 0.0-1.0 scale for granular trust scoring.
    # This differs from capsule TrustLevel (0-100) used in min_trust_to_sync.
    # Use trust_score_as_int property for 0-100 scale conversion.
    trust_score: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Peer trust: 0.0=untrusted, 1.0=fully trusted (0.0-1.0 scale)"
    )
    status: PeerStatus = Field(default=PeerStatus.PENDING)

    @property
    def trust_score_as_int(self) -> int:
        """Convert trust_score (0.0-1.0) to integer scale (0-100) for TrustLevel compatibility."""
        return int(self.trust_score * 100)

    # Sync configuration
    sync_direction: SyncDirection = Field(default=SyncDirection.BIDIRECTIONAL)
    sync_interval_minutes: int = Field(default=60, ge=5)
    conflict_resolution: ConflictResolution = Field(
        default=ConflictResolution.HIGHER_TRUST
    )

    # Filtering
    sync_capsule_types: list[str] = Field(
        default_factory=list,
        description="Empty = all types, otherwise filter to these"
    )
    min_trust_to_sync: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum capsule trust level to sync"
    )

    # Metadata
    description: str | None = None
    admin_contact: str | None = None

    # Timestamps
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_sync_at: datetime | None = None
    last_seen_at: datetime | None = None

    # Stats
    total_syncs: int = Field(default=0)
    successful_syncs: int = Field(default=0)
    failed_syncs: int = Field(default=0)
    capsules_received: int = Field(default=0)
    capsules_sent: int = Field(default=0)


class FederatedCapsule(ForgeModel):
    """
    Tracks a capsule that exists on a remote peer.
    Links remote capsule to local copy (if synced).
    """

    id: str = Field(default_factory=generate_id, description="Local tracking ID")
    peer_id: str = Field(description="Which peer this came from")

    # Remote identity
    remote_capsule_id: str = Field(description="ID on the remote peer")
    remote_content_hash: str = Field(description="Hash of content on remote")

    # Local copy (if synced)
    local_capsule_id: str | None = Field(
        default=None,
        description="ID of local copy if we've synced it"
    )
    local_content_hash: str | None = None

    # Sync state
    sync_status: FederatedSyncStatus = Field(
        default=FederatedSyncStatus.PENDING,
        description="Current sync status"
    )
    conflict_reason: str | None = None

    # Remote metadata (cached)
    remote_title: str | None = None
    remote_type: str | None = None
    remote_trust_level: int | None = None
    remote_owner_id: str | None = None
    remote_created_at: datetime | None = None
    remote_updated_at: datetime | None = None

    # Timestamps
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_synced_at: datetime | None = None

    # Review
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None


class FederatedEdge(ForgeModel):
    """
    Tracks a semantic edge that spans federated capsules.
    """

    id: str = Field(default_factory=generate_id)
    peer_id: str

    # The edge
    remote_edge_id: str
    source_capsule_id: str  # Could be local or federated
    target_capsule_id: str  # Could be local or federated
    relationship_type: str

    # Whether endpoints are local or remote
    source_is_local: bool = False
    target_is_local: bool = False

    # Local copy
    local_edge_id: str | None = None
    sync_status: FederatedSyncStatus = Field(default=FederatedSyncStatus.PENDING)

    # Timestamps
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_synced_at: datetime | None = None


class SyncState(ForgeModel):
    """
    Tracks the state of a sync operation with a peer.
    """

    id: str = Field(default_factory=generate_id)
    peer_id: str

    # Operation
    direction: SyncDirection
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # Progress
    status: SyncOperationStatus = Field(default=SyncOperationStatus.RUNNING)
    phase: SyncPhase = Field(default=SyncPhase.INIT)

    # Sync window
    sync_from: datetime | None = None  # Changes since this time
    sync_to: datetime | None = None    # Up to this time

    # Counts
    capsules_fetched: int = 0
    capsules_created: int = 0
    capsules_updated: int = 0
    capsules_skipped: int = 0
    capsules_conflicted: int = 0

    edges_fetched: int = 0
    edges_created: int = 0
    edges_skipped: int = 0

    # Errors
    error_message: str | None = None
    error_details: dict[str, Any] | None = None

    # Checkpoints (for resumable syncs)
    last_processed_id: str | None = None
    checkpoint_data: dict[str, Any] | None = None


class PeerHandshake(ForgeModel):
    """
    Data exchanged during peer handshake.
    """

    instance_id: str
    instance_name: str
    api_version: str
    public_key: str

    # Capabilities
    supports_push: bool = True
    supports_pull: bool = True
    supports_streaming: bool = False

    # Offered sync config
    suggested_interval_minutes: int = 60
    max_capsules_per_sync: int = 1000

    # Signature over the handshake data
    signature: str
    timestamp: datetime

    # SECURITY FIX (Audit 2): Nonce for replay attack prevention
    # Optional for backward compatibility with older peers
    nonce: str | None = Field(
        default=None,
        description="Cryptographic nonce to prevent replay attacks (32 hex chars)"
    )


class SyncPayload(ForgeModel):
    """
    Payload for sync operations.
    """

    peer_id: str
    sync_id: str
    timestamp: datetime

    # Changes
    capsules: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    deletions: list[str] = Field(default_factory=list)

    # Pagination
    has_more: bool = False
    next_cursor: str | None = None

    # Integrity
    content_hash: str
    signature: str

    # SECURITY FIX (Audit 2): Nonce for replay attack prevention
    # Optional for backward compatibility with older peers
    nonce: str | None = Field(
        default=None,
        description="Cryptographic nonce to prevent replay attacks (32 hex chars)"
    )


class FederationStats(ForgeModel):
    """
    Overall federation statistics.
    """

    total_peers: int = 0
    active_peers: int = 0
    pending_peers: int = 0

    total_federated_capsules: int = 0
    synced_capsules: int = 0
    pending_capsules: int = 0
    conflicted_capsules: int = 0

    total_federated_edges: int = 0

    last_sync_at: datetime | None = None
    syncs_today: int = 0
    syncs_failed_today: int = 0

    bytes_received_today: int = 0
    bytes_sent_today: int = 0
