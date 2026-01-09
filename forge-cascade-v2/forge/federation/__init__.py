"""
Forge Federation Module

Enables distributed knowledge sharing across multiple Forge instances.
Peers can discover each other, establish trust, and sync capsules/edges.

Architecture:
    FederationProtocol - Handles cryptographic handshake and secure messaging
    SyncService - Orchestrates sync operations between peers
    PeerTrustManager - Manages trust scoring and permissions

Usage:
    from forge.federation import FederationProtocol, SyncService, PeerTrustManager

    # Initialize protocol
    protocol = FederationProtocol(instance_id, instance_name)
    await protocol.initialize()

    # Create trust manager
    trust_manager = PeerTrustManager()

    # Create sync service
    sync_service = SyncService(protocol, trust_manager, capsule_repo, neo4j_driver)

    # Register a peer
    handshake = await protocol.initiate_handshake(peer_url)
    peer = FederatedPeer(...)
    await sync_service.register_peer(peer)

    # Sync with peer
    state = await sync_service.sync_with_peer(peer_id)
"""

from forge.federation.models import (
    FederatedPeer,
    FederatedCapsule,
    FederatedEdge,
    SyncState,
    SyncDirection,
    PeerStatus,
    ConflictResolution,
    PeerHandshake,
    SyncPayload,
    FederationStats,
)
from forge.federation.protocol import FederationProtocol
from forge.federation.sync import SyncService
from forge.federation.trust import PeerTrustManager

__all__ = [
    # Models
    "FederatedPeer",
    "FederatedCapsule",
    "FederatedEdge",
    "SyncState",
    "SyncDirection",
    "PeerStatus",
    "ConflictResolution",
    "PeerHandshake",
    "SyncPayload",
    "FederationStats",
    # Services
    "FederationProtocol",
    "SyncService",
    "PeerTrustManager",
]
