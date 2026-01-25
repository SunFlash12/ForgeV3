"""
Federation Sync Service

Orchestrates synchronization of capsules and edges between federated Forge instances.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from forge.federation.models import (
    ConflictResolution,
    FederatedCapsule,
    FederatedEdge,
    FederatedPeer,
    FederatedSyncStatus,
    PeerStatus,
    SyncDirection,
    SyncOperationStatus,
    SyncPhase,
    SyncState,
)
from forge.federation.protocol import FederationProtocol
from forge.federation.trust import PeerTrustManager

logger = logging.getLogger(__name__)


class SyncConflict:
    """Represents a sync conflict that needs resolution."""

    def __init__(
        self,
        local_capsule: dict[str, Any] | None,
        remote_capsule: dict[str, Any],
        conflict_type: str,
        reason: str,
    ):
        self.local_capsule = local_capsule
        self.remote_capsule = remote_capsule
        self.conflict_type = conflict_type  # "content", "trust", "deletion"
        self.reason = reason
        self.resolution: str | None = None
        self.resolved_capsule: dict[str, Any] | None = None


class SyncService:
    """
    Manages synchronization between federated peers.

    Responsibilities:
    1. Schedule and execute sync operations
    2. Handle conflicts according to resolution policy
    3. Track sync state and progress
    4. Manage federated capsule/edge records
    """

    def __init__(
        self,
        protocol: FederationProtocol,
        trust_manager: PeerTrustManager,
        capsule_repository: Any,  # CapsuleRepository
        neo4j_driver: Any,  # Neo4j driver
    ):
        self.protocol = protocol
        self.trust_manager = trust_manager
        self.capsule_repo = capsule_repository
        self.driver = neo4j_driver

        # State caches - backed by Neo4j persistence
        self._peers: dict[str, FederatedPeer] = {}
        self._federated_capsules: dict[str, FederatedCapsule] = {}
        self._federated_edges: dict[str, FederatedEdge] = {}
        self._sync_states: dict[str, SyncState] = {}
        self._sync_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the sync service by loading state from Neo4j."""
        if self._initialized:
            return

        await self.load_peers_from_db()
        await self._load_federated_capsules_from_db()
        await self._load_federated_edges_from_db()
        self._initialized = True
        logger.info("Federation sync service initialized")

    async def register_peer(self, peer: FederatedPeer) -> None:
        """Register a new federated peer."""
        self._peers[peer.id] = peer
        # SECURITY FIX (Audit 3): Persist peer to database
        await self.persist_peer(peer)
        logger.info(f"Registered peer: {peer.name} ({peer.id})")

    async def unregister_peer(self, peer_id: str) -> None:
        """Remove a federated peer."""
        if peer_id in self._peers:
            del self._peers[peer_id]
            # SECURITY FIX (Audit 3): Also remove from database
            await self.delete_peer_from_db(peer_id)
            logger.info(f"Unregistered peer: {peer_id}")

    async def get_peer(self, peer_id: str) -> FederatedPeer | None:
        """Get a peer by ID."""
        return self._peers.get(peer_id)

    async def list_peers(self) -> list[FederatedPeer]:
        """List all registered peers."""
        return list(self._peers.values())

    async def get_peer_by_public_key(self, public_key: str) -> FederatedPeer | None:
        """Get a peer by their public key."""
        for peer in self._peers.values():
            if peer.public_key == public_key:
                return peer
        return None

    async def sync_with_peer(
        self,
        peer_id: str,
        direction: SyncDirection | None = None,
        force: bool = False,
    ) -> SyncState:
        """
        Perform sync with a specific peer.

        Args:
            peer_id: The peer to sync with
            direction: Override peer's configured direction
            force: Force sync even if recently synced
        """
        async with self._sync_lock:
            peer = self._peers.get(peer_id)
            if not peer:
                raise ValueError(f"Unknown peer: {peer_id}")

            # Check if sync is needed
            if not force and peer.last_sync_at:
                next_sync = peer.last_sync_at + timedelta(minutes=peer.sync_interval_minutes)
                if datetime.now(UTC) < next_sync:
                    logger.info(f"Skipping sync with {peer.name} - not due yet")
                    return self._create_skipped_state(peer_id)

            # Create sync state
            sync_id = str(uuid.uuid4())
            sync_direction = direction or peer.sync_direction

            state = SyncState(
                id=sync_id,
                peer_id=peer_id,
                direction=sync_direction,
                started_at=datetime.now(UTC),
                status=SyncOperationStatus.RUNNING,
                phase=SyncPhase.INIT,
            )
            self._sync_states[sync_id] = state

            try:
                # Execute sync based on direction
                if sync_direction == SyncDirection.PULL:
                    await self._execute_pull(peer, state)
                elif sync_direction == SyncDirection.PUSH:
                    await self._execute_push(peer, state)
                else:  # BIDIRECTIONAL
                    await self._execute_pull(peer, state)
                    await self._execute_push(peer, state)

                # Update success
                state.status = SyncOperationStatus.COMPLETED
                state.completed_at = datetime.now(UTC)
                peer.last_sync_at = state.completed_at
                peer.successful_syncs += 1
                peer.total_syncs += 1

                # Update trust based on successful sync
                await self.trust_manager.record_successful_sync(peer)

            except Exception as e:
                logger.error(f"Sync failed with {peer.name}: {e}")
                state.status = SyncOperationStatus.FAILED
                state.error_message = str(e)
                state.completed_at = datetime.now(UTC)
                peer.failed_syncs += 1
                peer.total_syncs += 1

                # Reduce trust on failure
                await self.trust_manager.record_failed_sync(peer)

            return state

    # SECURITY FIX (Audit 4 - H6): Maximum iterations to prevent DoS via unbounded sync loop
    MAX_SYNC_ITERATIONS = 100  # Maximum pagination iterations per sync

    async def _execute_pull(self, peer: FederatedPeer, state: SyncState) -> None:
        """Pull changes from a peer."""
        state.phase = SyncPhase.FETCHING
        logger.info(f"Pulling from {peer.name}")

        # Calculate sync window
        state.sync_from = peer.last_sync_at
        state.sync_to = datetime.now(UTC)

        # SECURITY FIX (Audit 4 - H6): Add iteration counter to prevent DoS
        # A malicious peer could claim has_more=True forever to exhaust resources
        iterations = 0

        while iterations < self.MAX_SYNC_ITERATIONS:
            iterations += 1

            payload = await self.protocol.send_sync_request(
                peer=peer,
                since=state.sync_from,
                capsule_types=peer.sync_capsule_types or None,
                limit=100,
            )

            if not payload:
                raise RuntimeError("Failed to fetch changes from peer")

            # SECURITY FIX (Audit 4 - H7): Verify content hash against actual content
            if hasattr(payload, 'content_hash') and payload.content_hash:
                computed_hash = self._compute_content_hash(payload.capsules, payload.edges, payload.deletions)
                if computed_hash != payload.content_hash:
                    logger.error(
                        f"Content hash mismatch from peer {peer.name}: "
                        f"claimed={payload.content_hash[:16]}..., computed={computed_hash[:16]}..."
                    )
                    raise RuntimeError("Content hash verification failed - possible tampering")

            state.capsules_fetched += len(payload.capsules)
            state.edges_fetched += len(payload.edges)

            # Process capsules
            state.phase = SyncPhase.PROCESSING
            await self._process_incoming_capsules(peer, payload.capsules, state)

            # Process edges
            await self._process_incoming_edges(peer, payload.edges, state)

            # Handle deletions
            for deleted_id in payload.deletions:
                await self._handle_remote_deletion(peer, deleted_id)

            if not payload.has_more:
                break
            # Note: cursor pagination not yet implemented in protocol

        # SECURITY FIX (Audit 4 - H6): Log if we hit the iteration limit
        if iterations >= self.MAX_SYNC_ITERATIONS:
            logger.warning(
                f"Sync with peer {peer.name} hit maximum iteration limit ({self.MAX_SYNC_ITERATIONS}). "
                "This may indicate a malicious peer or very large sync backlog."
            )

        state.phase = SyncPhase.FINALIZING
        peer.capsules_received += state.capsules_fetched
        logger.info(
            f"Pull complete: {state.capsules_created} created, "
            f"{state.capsules_updated} updated, {state.capsules_conflicted} conflicts"
        )

    async def _execute_push(self, peer: FederatedPeer, state: SyncState) -> None:
        """Push changes to a peer."""
        state.phase = SyncPhase.PROCESSING  # No "preparing" phase in enum
        logger.info(f"Pushing to {peer.name}")

        # Get local changes since last sync
        capsules = await self._get_local_changes(
            since=peer.last_sync_at,
            min_trust=peer.min_trust_to_sync,
            types=peer.sync_capsule_types or None,
        )

        if not capsules:
            logger.info(f"No changes to push to {peer.name}")
            return

        state.phase = SyncPhase.APPLYING

        # Get edge changes since last sync
        edges = await self._get_edge_changes(
            since=peer.last_sync_at,
            capsule_ids=[c.get("id") for c in capsules if c.get("id")],
        )

        # Create and send payload
        payload = await self.protocol.create_sync_payload(
            sync_id=state.id,
            peer_id=peer.id,
            capsules=capsules,
            edges=edges,
        )

        success = await self.protocol.send_sync_push(peer, payload)
        if not success:
            raise RuntimeError("Failed to push changes to peer")

        peer.capsules_sent += len(capsules)
        logger.info(f"Push complete: {len(capsules)} capsules sent")

    async def _process_incoming_capsules(
        self,
        peer: FederatedPeer,
        capsules: list[dict[str, Any]],
        state: SyncState,
    ) -> None:
        """Process incoming capsules from a peer."""
        for remote_capsule in capsules:
            remote_id = remote_capsule.get("id")
            if not remote_id:
                continue

            # Check trust threshold
            remote_trust = remote_capsule.get("trust_level", 0)
            if remote_trust < peer.min_trust_to_sync:
                state.capsules_skipped += 1
                continue

            # Check if we already have this capsule
            fed_capsule = await self._find_federated_capsule(peer.id, remote_id)

            if fed_capsule and fed_capsule.local_capsule_id:
                # Check for conflicts
                conflict = await self._check_conflict(fed_capsule, remote_capsule)
                if conflict:
                    resolution = await self._resolve_conflict(peer, conflict)
                    if resolution == "skip":
                        state.capsules_conflicted += 1
                        continue
                    elif resolution == "update":
                        await self._update_local_capsule(fed_capsule, remote_capsule)
                        state.capsules_updated += 1
                else:
                    # No conflict, update if changed
                    if fed_capsule.remote_content_hash != remote_capsule.get("content_hash"):
                        await self._update_local_capsule(fed_capsule, remote_capsule)
                        state.capsules_updated += 1
                    else:
                        state.capsules_skipped += 1
            else:
                # New capsule - create local copy
                await self._create_local_capsule(peer, remote_capsule)
                state.capsules_created += 1

    async def _process_incoming_edges(
        self,
        peer: FederatedPeer,
        edges: list[dict[str, Any]],
        state: SyncState,
    ) -> None:
        """Process incoming edges from a peer."""
        for remote_edge in edges:
            remote_id = remote_edge.get("id")
            if not remote_id:
                continue

            # Check if we have both endpoints
            source_id = remote_edge.get("source_id")
            target_id = remote_edge.get("target_id")

            source_local = await self._resolve_to_local_id(peer.id, source_id)
            target_local = await self._resolve_to_local_id(peer.id, target_id)

            if source_local and target_local:
                # Create local edge
                await self._create_local_edge(peer, remote_edge, source_local, target_local)
                state.edges_created += 1
            else:
                state.edges_skipped += 1

    async def _check_conflict(
        self,
        fed_capsule: FederatedCapsule,
        remote_capsule: dict[str, Any],
    ) -> SyncConflict | None:
        """Check if there's a conflict between local and remote versions."""
        # Get local capsule
        local = await self._get_local_capsule(fed_capsule.local_capsule_id)
        if not local:
            return None

        remote_hash = remote_capsule.get("content_hash")
        local_hash = local.get("content_hash")

        # Both changed since last sync?
        if (
            fed_capsule.local_content_hash != local_hash
            and fed_capsule.remote_content_hash != remote_hash
        ):
            return SyncConflict(
                local_capsule=local,
                remote_capsule=remote_capsule,
                conflict_type="content",
                reason="Both local and remote modified since last sync",
            )

        return None

    async def _resolve_conflict(
        self,
        peer: FederatedPeer,
        conflict: SyncConflict,
    ) -> str:
        """Resolve a sync conflict based on policy."""
        resolution = peer.conflict_resolution

        if resolution == ConflictResolution.LOCAL_WINS:
            conflict.resolution = "local_wins"
            return "skip"

        elif resolution == ConflictResolution.REMOTE_WINS:
            conflict.resolution = "remote_wins"
            conflict.resolved_capsule = conflict.remote_capsule
            return "update"

        elif resolution == ConflictResolution.HIGHER_TRUST:
            local_trust = conflict.local_capsule.get("trust_level", 0) if conflict.local_capsule else 0
            remote_trust = conflict.remote_capsule.get("trust_level", 0)

            if remote_trust > local_trust:
                conflict.resolution = "remote_higher_trust"
                conflict.resolved_capsule = conflict.remote_capsule
                return "update"
            else:
                conflict.resolution = "local_higher_trust"
                return "skip"

        elif resolution == ConflictResolution.NEWER_TIMESTAMP:
            local_updated = conflict.local_capsule.get("updated_at") if conflict.local_capsule else None
            remote_updated = conflict.remote_capsule.get("updated_at")

            if remote_updated and (not local_updated or remote_updated > local_updated):
                conflict.resolution = "remote_newer"
                conflict.resolved_capsule = conflict.remote_capsule
                return "update"
            else:
                conflict.resolution = "local_newer"
                return "skip"

        elif resolution == ConflictResolution.MERGE:
            # Attempt merge (simple strategy: combine unique fields)
            merged = await self._merge_capsules(
                conflict.local_capsule,
                conflict.remote_capsule
            )
            conflict.resolution = "merged"
            conflict.resolved_capsule = merged
            return "update"

        else:  # MANUAL_REVIEW
            conflict.resolution = "pending_review"
            # Store for manual review
            await self._flag_for_review(conflict)
            return "skip"

    async def _merge_capsules(
        self,
        local: dict[str, Any] | None,
        remote: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Attempt to merge local and remote capsules.

        SECURITY FIX (Audit 4 - H9): Never accept trust_level from remote peers.
        Trust must always be calculated locally based on our own policies.
        Accepting remote trust values allows attackers to claim high trust.
        """
        if not local:
            # For new capsules, strip the remote trust and use our default
            merged = remote.copy()
            # SECURITY FIX: Don't trust remote trust_level - use UNVERIFIED default
            merged["trust_level"] = 20  # UNVERIFIED - will be recalculated locally
            logger.info(
                "remote_trust_rejected",
                remote_claimed_trust=remote.get("trust_level"),
                assigned_trust=20
            )
            return merged

        merged = local.copy()

        # SECURITY FIX (Audit 4 - H9): Never adopt remote trust levels
        # Trust must be recalculated locally, not accepted from potentially
        # malicious peers. Keeping local trust_level unchanged.
        if remote.get("trust_level", 0) > local.get("trust_level", 0):
            logger.warning(
                "remote_higher_trust_rejected",
                capsule_id=local.get("id"),
                local_trust=local.get("trust_level"),
                remote_claimed_trust=remote.get("trust_level"),
                reason="Trust levels must be calculated locally, not accepted from remote"
            )
            # Keep local trust - do NOT update from remote

        # Combine tags
        local_tags = set(local.get("tags", []))
        remote_tags = set(remote.get("tags", []))
        merged["tags"] = list(local_tags | remote_tags)

        # Take newer content if significantly different
        # (In production, use proper diff/merge)
        if remote.get("updated_at", "") > local.get("updated_at", ""):
            merged["content"] = remote.get("content", merged.get("content"))

        return merged

    async def _flag_for_review(self, conflict: SyncConflict) -> None:
        """Flag a conflict for manual review."""
        # Store in review queue
        logger.info(f"Conflict flagged for review: {conflict.reason}")

    async def _find_federated_capsule(
        self,
        peer_id: str,
        remote_capsule_id: str,
    ) -> FederatedCapsule | None:
        """Find a federated capsule record."""
        key = f"{peer_id}:{remote_capsule_id}"
        return self._federated_capsules.get(key)

    async def _get_local_capsule(self, capsule_id: str | None) -> dict[str, Any] | None:
        """Get a local capsule by ID."""
        if not capsule_id:
            return None

        try:
            async with self.driver.session() as session:
                query = """
                MATCH (c:Capsule {id: $id})
                RETURN c {
                    .id, .title, .content, .type, .trust_level,
                    .owner_id, .created_at, .updated_at, .content_hash, .tags
                } AS capsule
                """
                result = await session.run(query, {"id": capsule_id})
                record = await result.single()
                if record:
                    return record["capsule"]
        except Exception as e:
            logger.error(f"Failed to get local capsule {capsule_id}: {e}")

        return None

    async def _create_local_capsule(
        self,
        peer: FederatedPeer,
        remote_capsule: dict[str, Any],
    ) -> None:
        """Create a local copy of a remote capsule."""
        local_id = str(uuid.uuid4())

        # Create actual capsule in Neo4j
        try:
            async with self.driver.session() as session:
                query = """
                CREATE (c:Capsule {
                    id: $id,
                    title: $title,
                    content: $content,
                    type: $type,
                    trust_level: $trust_level,
                    owner_id: $owner_id,
                    created_at: datetime(),
                    updated_at: datetime(),
                    content_hash: $content_hash,
                    tags: $tags,
                    federated: true,
                    source_peer_id: $peer_id,
                    source_capsule_id: $remote_id
                })
                RETURN c.id AS id
                """
                result = await session.run(query, {
                    "id": local_id,
                    "title": remote_capsule.get("title", ""),
                    "content": remote_capsule.get("content", ""),
                    "type": remote_capsule.get("type", "knowledge"),
                    # SECURITY: Don't trust remote trust level - use UNVERIFIED default
                    "trust_level": 20,  # UNVERIFIED - will be recalculated locally
                    "owner_id": peer.id,  # Attribute to the peer
                    "content_hash": remote_capsule.get("content_hash", ""),
                    "tags": remote_capsule.get("tags", []),
                    "peer_id": peer.id,
                    "remote_id": remote_capsule["id"],
                })
                await result.single()
                logger.debug(f"Created local capsule {local_id} from peer {peer.name}")

        except Exception as e:
            logger.error(f"Failed to create local capsule: {e}")
            return

        # Create federated tracking record
        fed_capsule = FederatedCapsule(
            peer_id=peer.id,
            remote_capsule_id=remote_capsule["id"],
            local_capsule_id=local_id,
            remote_content_hash=remote_capsule.get("content_hash", ""),
            local_content_hash=remote_capsule.get("content_hash", ""),
            sync_status=FederatedSyncStatus.SYNCED,
            remote_title=remote_capsule.get("title"),
            remote_type=remote_capsule.get("type"),
            remote_trust_level=remote_capsule.get("trust_level"),
            remote_owner_id=remote_capsule.get("owner_id"),
            last_synced_at=datetime.now(UTC),
        )

        key = f"{peer.id}:{remote_capsule['id']}"
        self._federated_capsules[key] = fed_capsule

        # Persist to Neo4j
        await self._persist_federated_capsule(fed_capsule)

    async def _update_local_capsule(
        self,
        fed_capsule: FederatedCapsule,
        remote_capsule: dict[str, Any],
    ) -> None:
        """Update local capsule with remote changes."""
        # Update actual capsule in Neo4j
        if fed_capsule.local_capsule_id:
            try:
                async with self.driver.session() as session:
                    query = """
                    MATCH (c:Capsule {id: $id})
                    SET c.title = $title,
                        c.content = $content,
                        c.content_hash = $content_hash,
                        c.tags = $tags,
                        c.updated_at = datetime()
                    RETURN c.id AS id
                    """
                    await session.run(query, {
                        "id": fed_capsule.local_capsule_id,
                        "title": remote_capsule.get("title", ""),
                        "content": remote_capsule.get("content", ""),
                        "content_hash": remote_capsule.get("content_hash", ""),
                        "tags": remote_capsule.get("tags", []),
                        # NOTE: Don't update trust_level - must be calculated locally
                    })
                    logger.debug(f"Updated local capsule {fed_capsule.local_capsule_id}")
            except Exception as e:
                logger.error(f"Failed to update local capsule: {e}")

        # Update tracking record
        fed_capsule.remote_content_hash = remote_capsule.get("content_hash", "")
        fed_capsule.local_content_hash = remote_capsule.get("content_hash", "")
        fed_capsule.last_synced_at = datetime.now(UTC)

    async def _handle_remote_deletion(
        self,
        peer: FederatedPeer,
        remote_id: str,
    ) -> None:
        """Handle a deletion notification from peer."""
        key = f"{peer.id}:{remote_id}"
        if key in self._federated_capsules:
            fed_capsule = self._federated_capsules[key]
            # Mark as rejected (no "deleted_remote" status) - flag for review
            fed_capsule.sync_status = FederatedSyncStatus.REJECTED
            fed_capsule.conflict_reason = "Remote capsule deleted"
            # Don't delete local copy automatically - flag for review

    async def _resolve_to_local_id(
        self,
        peer_id: str,
        remote_id: str,
    ) -> str | None:
        """Resolve a remote ID to a local ID."""
        key = f"{peer_id}:{remote_id}"
        fed_capsule = self._federated_capsules.get(key)
        if fed_capsule:
            return fed_capsule.local_capsule_id
        return None

    async def _create_local_edge(
        self,
        peer: FederatedPeer,
        remote_edge: dict[str, Any],
        source_local: str,
        target_local: str,
    ) -> None:
        """Create a local copy of a remote edge."""
        relationship_type = remote_edge.get("relationship_type", "RELATED_TO")

        fed_edge = FederatedEdge(
            peer_id=peer.id,
            remote_edge_id=remote_edge.get("id", ""),
            source_capsule_id=source_local,
            target_capsule_id=target_local,
            relationship_type=relationship_type,
            source_is_local=True,
            target_is_local=True,
            sync_status=FederatedSyncStatus.SYNCED,
            last_synced_at=datetime.now(UTC),
        )

        self._federated_edges[fed_edge.id] = fed_edge

        # Persist the mapping to Neo4j
        await self._persist_federated_edge(fed_edge)

        # Create actual edge in Neo4j
        try:
            async with self.driver.session() as session:
                # Use MERGE to avoid duplicates
                query = f"""
                MATCH (source:Capsule {{id: $source_id}})
                MATCH (target:Capsule {{id: $target_id}})
                MERGE (source)-[r:{relationship_type}]->(target)
                SET r.federated = true,
                    r.peer_id = $peer_id,
                    r.remote_edge_id = $remote_edge_id,
                    r.created_at = datetime(),
                    r.weight = $weight,
                    r.properties = $properties
                RETURN id(r) AS edge_id
                """
                await session.run(query, {
                    "source_id": source_local,
                    "target_id": target_local,
                    "peer_id": peer.id,
                    "remote_edge_id": remote_edge.get("id", ""),
                    "weight": remote_edge.get("weight", 1.0),
                    "properties": str(remote_edge.get("properties", {})),
                })
                logger.debug(
                    f"Created federated edge {relationship_type} "
                    f"from {source_local} to {target_local}"
                )
        except Exception as e:
            logger.error(f"Failed to create edge in Neo4j: {e}")

    async def _get_edge_changes(
        self,
        since: datetime | None,
        capsule_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Get edge changes for the given capsules since a timestamp."""
        if not capsule_ids:
            return []

        try:
            query = """
            MATCH (source:Capsule)-[r]->(target:Capsule)
            WHERE source.id IN $capsule_ids OR target.id IN $capsule_ids
            """
            params: dict[str, Any] = {"capsule_ids": capsule_ids}

            if since:
                query += " AND (r.created_at > $since OR r.updated_at > $since)"
                params["since"] = since.isoformat()

            # Exclude federated edges (they came from other peers)
            query += " AND (r.federated IS NULL OR r.federated = false)"

            query += """
            RETURN {
                id: id(r),
                source_id: source.id,
                target_id: target.id,
                relationship_type: type(r),
                weight: r.weight,
                properties: r.properties,
                created_at: r.created_at
            } AS edge
            LIMIT 500
            """

            async with self.driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

                edges = [record["edge"] for record in records if record.get("edge")]
                logger.debug(f"Found {len(edges)} edge changes since {since}")
                return edges

        except Exception as e:
            logger.error(f"Failed to get edge changes: {e}")
            return []

    async def _get_local_changes(
        self,
        since: datetime | None,
        min_trust: int,
        types: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Get local capsules that changed since a timestamp."""
        try:
            # Build query to get capsules modified since last sync
            query = """
            MATCH (c:Capsule)
            WHERE c.trust_level >= $min_trust
            """
            params: dict[str, Any] = {"min_trust": min_trust}

            if since:
                query += " AND c.updated_at > $since"
                params["since"] = since.isoformat()

            if types:
                query += " AND c.type IN $types"
                params["types"] = types

            query += """
            RETURN c {
                .id, .title, .content, .type, .trust_level,
                .owner_id, .created_at, .updated_at, .content_hash, .tags
            } AS capsule
            ORDER BY c.updated_at DESC
            LIMIT 500
            """

            async with self.driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()

                capsules = []
                for record in records:
                    capsule_data = record.get("capsule")
                    if capsule_data:
                        # Filter out capsules that originated from this peer (prevent echo)
                        # by checking if they have a federated source
                        capsule_id = capsule_data.get("id")
                        if capsule_id:
                            # Check if this is a federated capsule - skip if from any peer
                            is_federated = any(
                                fc.local_capsule_id == capsule_id
                                for fc in self._federated_capsules.values()
                            )
                            if not is_federated:
                                capsules.append(capsule_data)

                logger.debug(f"Found {len(capsules)} local changes since {since}")
                return capsules

        except Exception as e:
            logger.error(f"Failed to get local changes: {e}")
            return []

    def _create_skipped_state(self, peer_id: str) -> SyncState:
        """Create a sync state for a skipped sync."""
        return SyncState(
            peer_id=peer_id,
            direction=SyncDirection.BIDIRECTIONAL,
            status=SyncOperationStatus.COMPLETED,  # No "skipped" status - use completed
            phase=SyncPhase.FINALIZING,
        )

    async def get_sync_state(self, sync_id: str) -> SyncState | None:
        """Get sync state by ID."""
        return self._sync_states.get(sync_id)

    async def get_sync_history(
        self,
        peer_id: str | None = None,
        limit: int = 50,
    ) -> list[SyncState]:
        """Get sync history, optionally filtered by peer."""
        states = list(self._sync_states.values())
        if peer_id:
            states = [s for s in states if s.peer_id == peer_id]
        states.sort(key=lambda s: s.started_at, reverse=True)
        return states[:limit]

    async def schedule_sync_all(self) -> list[str]:
        """Schedule sync with all active peers."""
        sync_ids = []
        for peer in self._peers.values():
            if peer.status == PeerStatus.ACTIVE:
                try:
                    state = await self.sync_with_peer(peer.id)
                    sync_ids.append(state.id)
                except Exception as e:
                    logger.error(f"Failed to schedule sync with {peer.name}: {e}")
        return sync_ids

    # =========================================================================
    # SECURITY FIX (Audit 3): Federation State Persistence
    # =========================================================================

    async def persist_peer(self, peer: FederatedPeer) -> bool:
        """
        SECURITY FIX (Audit 3): Persist peer to Neo4j database.

        Ensures peer state survives restarts, maintaining:
        - Trust relationships
        - Sync state
        - Public key mappings

        Args:
            peer: The peer to persist

        Returns:
            True if successfully persisted
        """
        import json
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (p:FederatedPeer {id: $id})
                SET p.name = $name,
                    p.endpoint = $endpoint,
                    p.public_key = $public_key,
                    p.status = $status,
                    p.trust_score = $trust_score,
                    p.sync_direction = $sync_direction,
                    p.conflict_resolution = $conflict_resolution,
                    p.last_sync_at = $last_sync_at,
                    p.created_at = $created_at,
                    p.updated_at = $updated_at,
                    p.metadata = $metadata
                RETURN p.id AS id
                """
                result = await session.run(query, {
                    "id": peer.id,
                    "name": peer.name,
                    "endpoint": peer.url,  # FIX: Use 'url' attribute from FederatedPeer model
                    "public_key": peer.public_key,
                    "status": peer.status.value if hasattr(peer.status, 'value') else str(peer.status),
                    "trust_score": peer.trust_score,
                    "sync_direction": peer.sync_direction.value if hasattr(peer.sync_direction, 'value') else str(peer.sync_direction),
                    "conflict_resolution": peer.conflict_resolution.value if hasattr(peer.conflict_resolution, 'value') else str(peer.conflict_resolution),
                    "last_sync_at": peer.last_sync_at.isoformat() if peer.last_sync_at else None,
                    "created_at": peer.created_at.isoformat() if peer.created_at else None,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": json.dumps(peer.metadata) if peer.metadata else None,
                })
                record = await result.single()
                logger.info(f"Persisted peer {peer.name} to database")
                return record is not None
        except Exception as e:
            logger.error(f"Failed to persist peer {peer.id}: {e}")
            return False

    async def load_peers_from_db(self) -> list[FederatedPeer]:
        """
        SECURITY FIX (Audit 3): Load all peers from Neo4j database.

        Called at startup to restore federation state.

        Returns:
            List of loaded peers
        """
        import json
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:FederatedPeer)
                RETURN p {.*} AS peer
                """
                result = await session.run(query)
                records = await result.data()

                loaded_peers = []
                for record in records:
                    peer_data = record["peer"]
                    try:
                        # SECURITY FIX (Audit 6): Bound trust_score to valid range [0.0, 1.0]
                        raw_trust = peer_data.get("trust_score", 0.3)
                        try:
                            bounded_trust = max(0.0, min(1.0, float(raw_trust)))
                        except (ValueError, TypeError):
                            bounded_trust = 0.3  # Default on invalid value

                        peer = FederatedPeer(
                            id=peer_data["id"],
                            name=peer_data["name"],
                            endpoint=peer_data["endpoint"],
                            public_key=peer_data.get("public_key", ""),
                            status=PeerStatus(peer_data.get("status", "pending")),
                            trust_score=bounded_trust,
                            sync_direction=SyncDirection(peer_data.get("sync_direction", "bidirectional")),
                            conflict_resolution=ConflictResolution(peer_data.get("conflict_resolution", "local_wins")),
                            last_sync_at=datetime.fromisoformat(peer_data["last_sync_at"]) if peer_data.get("last_sync_at") else None,
                            created_at=datetime.fromisoformat(peer_data["created_at"]) if peer_data.get("created_at") else None,
                            metadata=json.loads(peer_data["metadata"]) if peer_data.get("metadata") else {},
                        )
                        # Register in memory
                        self._peers[peer.id] = peer
                        loaded_peers.append(peer)
                    except Exception as e:
                        logger.error(f"Failed to parse peer {peer_data.get('id')}: {e}")

                logger.info(f"Loaded {len(loaded_peers)} peers from database")
                return loaded_peers
        except Exception as e:
            logger.error(f"Failed to load peers from database: {e}")
            return []

    async def delete_peer_from_db(self, peer_id: str) -> bool:
        """
        SECURITY FIX (Audit 3): Delete peer from Neo4j database.

        Args:
            peer_id: ID of peer to delete

        Returns:
            True if successfully deleted
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:FederatedPeer {id: $id})
                DELETE p
                RETURN count(*) AS deleted
                """
                result = await session.run(query, {"id": peer_id})
                record = await result.single()
                deleted = record["deleted"] if record else 0
                if deleted > 0:
                    logger.info(f"Deleted peer {peer_id} from database")
                return deleted > 0
        except Exception as e:
            logger.error(f"Failed to delete peer {peer_id}: {e}")
            return False

    def _compute_content_hash(
        self,
        capsules: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        deletions: list[str]
    ) -> str:
        """
        SECURITY FIX (Audit 4 - H7): Compute content hash for verification.

        Computes a SHA-256 hash of the content to verify against claimed hash.
        This prevents accepting tampered content from malicious peers.

        Args:
            capsules: List of capsule dictionaries
            edges: List of edge dictionaries
            deletions: List of deleted capsule IDs

        Returns:
            Hex string of SHA-256 hash
        """
        import hashlib
        import json

        # Build content dictionary in canonical order
        content = {
            "capsules": capsules,
            "edges": edges or [],
            "deletions": deletions or [],
        }

        # Serialize with sorted keys for deterministic output
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    async def persist_trust_score(self, peer_id: str, trust_score: float, reason: str) -> bool:
        """
        SECURITY FIX (Audit 3): Persist trust score update to database.

        Args:
            peer_id: ID of peer
            trust_score: New trust score
            reason: Reason for update

        Returns:
            True if successfully persisted
        """
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (p:FederatedPeer {id: $id})
                SET p.trust_score = $trust_score,
                    p.trust_updated_at = $updated_at,
                    p.trust_update_reason = $reason
                RETURN p.id AS id
                """
                result = await session.run(query, {
                    "id": peer_id,
                    "trust_score": trust_score,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "reason": reason,
                })
                record = await result.single()
                return record is not None
        except Exception as e:
            logger.error(f"Failed to persist trust score for {peer_id}: {e}")
            return False

    # =========================================================================
    # Federated Capsule Persistence
    # =========================================================================

    async def _persist_federated_capsule(self, fed_capsule: FederatedCapsule) -> bool:
        """Persist a federated capsule mapping to Neo4j."""
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (fc:FederatedCapsule {
                    peer_id: $peer_id,
                    remote_capsule_id: $remote_capsule_id
                })
                SET fc.local_capsule_id = $local_capsule_id,
                    fc.remote_content_hash = $remote_content_hash,
                    fc.local_content_hash = $local_content_hash,
                    fc.sync_status = $sync_status,
                    fc.remote_title = $remote_title,
                    fc.remote_type = $remote_type,
                    fc.remote_trust_level = $remote_trust_level,
                    fc.remote_owner_id = $remote_owner_id,
                    fc.last_synced_at = $last_synced_at,
                    fc.conflict_reason = $conflict_reason
                RETURN fc.peer_id AS peer_id
                """
                result = await session.run(query, {
                    "peer_id": fed_capsule.peer_id,
                    "remote_capsule_id": fed_capsule.remote_capsule_id,
                    "local_capsule_id": fed_capsule.local_capsule_id,
                    "remote_content_hash": fed_capsule.remote_content_hash,
                    "local_content_hash": fed_capsule.local_content_hash,
                    "sync_status": fed_capsule.sync_status.value if hasattr(fed_capsule.sync_status, 'value') else str(fed_capsule.sync_status),
                    "remote_title": fed_capsule.remote_title,
                    "remote_type": fed_capsule.remote_type,
                    "remote_trust_level": fed_capsule.remote_trust_level,
                    "remote_owner_id": fed_capsule.remote_owner_id,
                    "last_synced_at": fed_capsule.last_synced_at.isoformat() if fed_capsule.last_synced_at else None,
                    "conflict_reason": fed_capsule.conflict_reason,
                })
                await result.single()
                return True
        except Exception as e:
            logger.error(f"Failed to persist federated capsule mapping: {e}")
            return False

    async def _load_federated_capsules_from_db(self) -> None:
        """Load federated capsule mappings from Neo4j."""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (fc:FederatedCapsule)
                RETURN fc {.*} AS fc
                """
                result = await session.run(query)
                records = await result.data()

                for record in records:
                    fc_data = record.get("fc", {})
                    try:
                        fed_capsule = FederatedCapsule(
                            peer_id=fc_data["peer_id"],
                            remote_capsule_id=fc_data["remote_capsule_id"],
                            local_capsule_id=fc_data.get("local_capsule_id"),
                            remote_content_hash=fc_data.get("remote_content_hash", ""),
                            local_content_hash=fc_data.get("local_content_hash", ""),
                            sync_status=FederatedSyncStatus(fc_data.get("sync_status", "pending")),
                            remote_title=fc_data.get("remote_title"),
                            remote_type=fc_data.get("remote_type"),
                            remote_trust_level=fc_data.get("remote_trust_level"),
                            remote_owner_id=fc_data.get("remote_owner_id"),
                            last_synced_at=datetime.fromisoformat(fc_data["last_synced_at"]) if fc_data.get("last_synced_at") else None,
                            conflict_reason=fc_data.get("conflict_reason"),
                        )
                        key = f"{fed_capsule.peer_id}:{fed_capsule.remote_capsule_id}"
                        self._federated_capsules[key] = fed_capsule
                    except Exception as e:
                        logger.error(f"Failed to parse federated capsule: {e}")

                logger.info(f"Loaded {len(self._federated_capsules)} federated capsule mappings")
        except Exception as e:
            logger.error(f"Failed to load federated capsules: {e}")

    # =========================================================================
    # Federated Edge Persistence
    # =========================================================================

    async def _persist_federated_edge(self, fed_edge: FederatedEdge) -> bool:
        """Persist a federated edge mapping to Neo4j."""
        try:
            async with self.driver.session() as session:
                query = """
                MERGE (fe:FederatedEdge {id: $id})
                SET fe.peer_id = $peer_id,
                    fe.remote_edge_id = $remote_edge_id,
                    fe.source_capsule_id = $source_capsule_id,
                    fe.target_capsule_id = $target_capsule_id,
                    fe.relationship_type = $relationship_type,
                    fe.source_is_local = $source_is_local,
                    fe.target_is_local = $target_is_local,
                    fe.sync_status = $sync_status,
                    fe.last_synced_at = $last_synced_at
                RETURN fe.id AS id
                """
                result = await session.run(query, {
                    "id": fed_edge.id,
                    "peer_id": fed_edge.peer_id,
                    "remote_edge_id": fed_edge.remote_edge_id,
                    "source_capsule_id": fed_edge.source_capsule_id,
                    "target_capsule_id": fed_edge.target_capsule_id,
                    "relationship_type": fed_edge.relationship_type,
                    "source_is_local": fed_edge.source_is_local,
                    "target_is_local": fed_edge.target_is_local,
                    "sync_status": fed_edge.sync_status.value if hasattr(fed_edge.sync_status, 'value') else str(fed_edge.sync_status),
                    "last_synced_at": fed_edge.last_synced_at.isoformat() if fed_edge.last_synced_at else None,
                })
                await result.single()
                return True
        except Exception as e:
            logger.error(f"Failed to persist federated edge mapping: {e}")
            return False

    async def _load_federated_edges_from_db(self) -> None:
        """Load federated edge mappings from Neo4j."""
        try:
            async with self.driver.session() as session:
                query = """
                MATCH (fe:FederatedEdge)
                RETURN fe {.*} AS fe
                """
                result = await session.run(query)
                records = await result.data()

                for record in records:
                    fe_data = record.get("fe", {})
                    try:
                        fed_edge = FederatedEdge(
                            id=fe_data["id"],
                            peer_id=fe_data["peer_id"],
                            remote_edge_id=fe_data.get("remote_edge_id", ""),
                            source_capsule_id=fe_data.get("source_capsule_id", ""),
                            target_capsule_id=fe_data.get("target_capsule_id", ""),
                            relationship_type=fe_data.get("relationship_type", "RELATED_TO"),
                            source_is_local=fe_data.get("source_is_local", True),
                            target_is_local=fe_data.get("target_is_local", True),
                            sync_status=FederatedSyncStatus(fe_data.get("sync_status", "pending")),
                            last_synced_at=datetime.fromisoformat(fe_data["last_synced_at"]) if fe_data.get("last_synced_at") else None,
                        )
                        self._federated_edges[fed_edge.id] = fed_edge
                    except Exception as e:
                        logger.error(f"Failed to parse federated edge: {e}")

                logger.info(f"Loaded {len(self._federated_edges)} federated edge mappings")
        except Exception as e:
            logger.error(f"Failed to load federated edges: {e}")
