"""
Tests for federation sync service.
"""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from forge.federation.sync import (
    SyncConflict,
    SyncService,
)
from forge.federation.models import (
    FederatedPeer,
    FederatedCapsule,
    FederatedEdge,
    SyncState,
    PeerStatus,
    SyncDirection,
    SyncOperationStatus,
    SyncPhase,
    ConflictResolution,
    FederatedSyncStatus,
    SyncPayload,
)


class TestSyncConflict:
    """Tests for SyncConflict class."""

    def test_create_conflict(self):
        """Test creating sync conflict."""
        local = {"id": "local-1", "content": "local content"}
        remote = {"id": "remote-1", "content": "remote content"}

        conflict = SyncConflict(
            local_capsule=local,
            remote_capsule=remote,
            conflict_type="content",
            reason="Both modified",
        )

        assert conflict.local_capsule == local
        assert conflict.remote_capsule == remote
        assert conflict.conflict_type == "content"
        assert conflict.reason == "Both modified"
        assert conflict.resolution is None
        assert conflict.resolved_capsule is None

    def test_conflict_without_local(self):
        """Test conflict without local capsule."""
        remote = {"id": "remote-1", "content": "remote content"}

        conflict = SyncConflict(
            local_capsule=None,
            remote_capsule=remote,
            conflict_type="trust",
            reason="Trust mismatch",
        )

        assert conflict.local_capsule is None


class TestSyncService:
    """Tests for SyncService class."""

    @pytest.fixture
    def mock_protocol(self):
        """Create mock protocol."""
        protocol = AsyncMock()
        protocol.send_sync_request = AsyncMock()
        protocol.send_sync_push = AsyncMock(return_value=True)
        protocol.create_sync_payload = AsyncMock()
        return protocol

    @pytest.fixture
    def mock_trust_manager(self):
        """Create mock trust manager."""
        manager = AsyncMock()
        manager.record_successful_sync = AsyncMock(return_value=0.6)
        manager.record_failed_sync = AsyncMock(return_value=0.4)
        return manager

    @pytest.fixture
    def mock_capsule_repo(self):
        """Create mock capsule repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_driver(self):
        """Create mock Neo4j driver."""
        driver = MagicMock()
        session = AsyncMock()
        driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
        driver.session.return_value.__aexit__ = AsyncMock(return_value=None)
        return driver

    @pytest.fixture
    def sync_service(self, mock_protocol, mock_trust_manager, mock_capsule_repo, mock_driver):
        """Create sync service instance."""
        return SyncService(
            protocol=mock_protocol,
            trust_manager=mock_trust_manager,
            capsule_repository=mock_capsule_repo,
            neo4j_driver=mock_driver,
        )

    @pytest.fixture
    def sample_peer(self):
        """Create sample peer."""
        return FederatedPeer(
            id="peer-123",
            name="Test Peer",
            url="https://peer.example.com",
            public_key="pubkey==",
            trust_score=0.5,
            status=PeerStatus.ACTIVE,
            sync_direction=SyncDirection.BIDIRECTIONAL,
        )

    @pytest.mark.asyncio
    async def test_initialize(self, sync_service, mock_driver):
        """Test service initialization."""
        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        await sync_service.initialize()

        assert sync_service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, sync_service, mock_driver):
        """Test initialization is idempotent."""
        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        await sync_service.initialize()
        sync_service._initialized = True

        # Second call should skip
        await sync_service.initialize()

    @pytest.mark.asyncio
    async def test_register_peer(self, sync_service, mock_driver, sample_peer):
        """Test registering a peer."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"id": sample_peer.id}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        await sync_service.register_peer(sample_peer)

        assert sample_peer.id in sync_service._peers

    @pytest.mark.asyncio
    async def test_unregister_peer(self, sync_service, mock_driver, sample_peer):
        """Test unregistering a peer."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"deleted": 1}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        sync_service._peers[sample_peer.id] = sample_peer

        await sync_service.unregister_peer(sample_peer.id)

        assert sample_peer.id not in sync_service._peers

    @pytest.mark.asyncio
    async def test_get_peer(self, sync_service, sample_peer):
        """Test getting a peer."""
        sync_service._peers[sample_peer.id] = sample_peer

        peer = await sync_service.get_peer(sample_peer.id)

        assert peer == sample_peer

    @pytest.mark.asyncio
    async def test_get_peer_not_found(self, sync_service):
        """Test getting non-existent peer."""
        peer = await sync_service.get_peer("unknown")
        assert peer is None

    @pytest.mark.asyncio
    async def test_list_peers(self, sync_service, sample_peer):
        """Test listing peers."""
        peer2 = FederatedPeer(
            id="peer-456",
            name="Peer 2",
            url="https://peer2.com",
            public_key="key2",
        )
        sync_service._peers[sample_peer.id] = sample_peer
        sync_service._peers[peer2.id] = peer2

        peers = await sync_service.list_peers()

        assert len(peers) == 2

    @pytest.mark.asyncio
    async def test_get_peer_by_public_key(self, sync_service, sample_peer):
        """Test getting peer by public key."""
        sync_service._peers[sample_peer.id] = sample_peer

        peer = await sync_service.get_peer_by_public_key(sample_peer.public_key)

        assert peer == sample_peer

    @pytest.mark.asyncio
    async def test_get_peer_by_public_key_not_found(self, sync_service):
        """Test getting peer by unknown public key."""
        peer = await sync_service.get_peer_by_public_key("unknown")
        assert peer is None

    @pytest.mark.asyncio
    async def test_sync_with_peer_unknown(self, sync_service):
        """Test sync with unknown peer."""
        with pytest.raises(ValueError, match="Unknown peer"):
            await sync_service.sync_with_peer("unknown-peer")

    @pytest.mark.asyncio
    async def test_sync_with_peer_skipped(self, sync_service, sample_peer):
        """Test sync skipped when not due."""
        sample_peer.last_sync_at = datetime.now(UTC)
        sync_service._peers[sample_peer.id] = sample_peer

        state = await sync_service.sync_with_peer(sample_peer.id, force=False)

        assert state.status == SyncOperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_with_peer_pull(self, sync_service, mock_protocol, sample_peer):
        """Test pull sync."""
        sample_peer.sync_direction = SyncDirection.PULL
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock sync response
        payload = MagicMock()
        payload.capsules = []
        payload.edges = []
        payload.deletions = []
        payload.has_more = False
        payload.content_hash = "hash123"
        mock_protocol.send_sync_request.return_value = payload

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        assert state.status == SyncOperationStatus.COMPLETED
        mock_protocol.send_sync_request.assert_called()

    @pytest.mark.asyncio
    async def test_sync_with_peer_push(self, sync_service, mock_protocol, mock_driver, sample_peer):
        """Test push sync."""
        sample_peer.sync_direction = SyncDirection.PUSH
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock database query
        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        mock_protocol.create_sync_payload.return_value = MagicMock()

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        assert state.status == SyncOperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_with_peer_bidirectional(self, sync_service, mock_protocol, mock_driver, sample_peer):
        """Test bidirectional sync."""
        sample_peer.sync_direction = SyncDirection.BIDIRECTIONAL
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock sync response
        payload = MagicMock()
        payload.capsules = []
        payload.edges = []
        payload.deletions = []
        payload.has_more = False
        payload.content_hash = "hash123"
        mock_protocol.send_sync_request.return_value = payload

        # Mock database query
        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        mock_protocol.create_sync_payload.return_value = MagicMock()

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        assert state.status == SyncOperationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_sync_with_peer_failure(self, sync_service, mock_protocol, sample_peer):
        """Test sync failure handling."""
        sample_peer.sync_direction = SyncDirection.PULL
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock sync failure
        mock_protocol.send_sync_request.return_value = None

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        assert state.status == SyncOperationStatus.FAILED
        assert state.error_message is not None

    @pytest.mark.asyncio
    async def test_process_incoming_capsules(self, sync_service, mock_driver, sample_peer):
        """Test processing incoming capsules."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"id": "local-1"}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        capsules = [
            {
                "id": "remote-1",
                "title": "Test",
                "content": "Content",
                "trust_level": 60,
                "content_hash": "hash1",
            }
        ]

        state = SyncState(
            peer_id=sample_peer.id,
            direction=SyncDirection.PULL,
        )

        await sync_service._process_incoming_capsules(sample_peer, capsules, state)

        assert state.capsules_created == 1

    @pytest.mark.asyncio
    async def test_process_incoming_capsules_trust_filter(self, sync_service, sample_peer):
        """Test capsules filtered by trust level."""
        sample_peer.min_trust_to_sync = 50

        capsules = [
            {
                "id": "remote-1",
                "title": "Low Trust",
                "trust_level": 30,  # Below threshold
            }
        ]

        state = SyncState(
            peer_id=sample_peer.id,
            direction=SyncDirection.PULL,
        )

        await sync_service._process_incoming_capsules(sample_peer, capsules, state)

        assert state.capsules_skipped == 1
        assert state.capsules_created == 0

    @pytest.mark.asyncio
    async def test_process_incoming_edges(self, sync_service, mock_driver, sample_peer):
        """Test processing incoming edges."""
        # Setup federated capsule mappings
        sync_service._federated_capsules = {
            f"{sample_peer.id}:remote-1": FederatedCapsule(
                peer_id=sample_peer.id,
                remote_capsule_id="remote-1",
                local_capsule_id="local-1",
                remote_content_hash="hash1",
            ),
            f"{sample_peer.id}:remote-2": FederatedCapsule(
                peer_id=sample_peer.id,
                remote_capsule_id="remote-2",
                local_capsule_id="local-2",
                remote_content_hash="hash2",
            ),
        }

        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"edge_id": 123}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        edges = [
            {
                "id": "edge-1",
                "source_id": "remote-1",
                "target_id": "remote-2",
                "relationship_type": "RELATED_TO",
            }
        ]

        state = SyncState(
            peer_id=sample_peer.id,
            direction=SyncDirection.PULL,
        )

        await sync_service._process_incoming_edges(sample_peer, edges, state)

        assert state.edges_created == 1

    @pytest.mark.asyncio
    async def test_process_incoming_edges_invalid_relationship(self, sync_service, mock_driver, sample_peer):
        """Test invalid relationship type is sanitized."""
        sync_service._federated_capsules = {
            f"{sample_peer.id}:remote-1": FederatedCapsule(
                peer_id=sample_peer.id,
                remote_capsule_id="remote-1",
                local_capsule_id="local-1",
                remote_content_hash="hash1",
            ),
            f"{sample_peer.id}:remote-2": FederatedCapsule(
                peer_id=sample_peer.id,
                remote_capsule_id="remote-2",
                local_capsule_id="local-2",
                remote_content_hash="hash2",
            ),
        }

        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"edge_id": 123}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        edges = [
            {
                "id": "edge-1",
                "source_id": "remote-1",
                "target_id": "remote-2",
                "relationship_type": "MALICIOUS_TYPE; DROP DATABASE",  # Invalid
            }
        ]

        state = SyncState(
            peer_id=sample_peer.id,
            direction=SyncDirection.PULL,
        )

        await sync_service._process_incoming_edges(sample_peer, edges, state)

        # Should have sanitized to RELATED_TO
        assert state.edges_created == 1

    @pytest.mark.asyncio
    async def test_check_conflict_no_conflict(self, sync_service, mock_driver, sample_peer):
        """Test no conflict when hashes match."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"capsule": {"id": "local-1", "content_hash": "hash1"}}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        fed_capsule = FederatedCapsule(
            peer_id=sample_peer.id,
            remote_capsule_id="remote-1",
            local_capsule_id="local-1",
            remote_content_hash="hash1",
            local_content_hash="hash1",
        )

        remote_capsule = {
            "id": "remote-1",
            "content_hash": "hash1",
        }

        conflict = await sync_service._check_conflict(fed_capsule, remote_capsule)

        assert conflict is None

    @pytest.mark.asyncio
    async def test_check_conflict_detected(self, sync_service, mock_driver, sample_peer):
        """Test conflict detected when both changed."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"capsule": {"id": "local-1", "content_hash": "local_changed"}}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        fed_capsule = FederatedCapsule(
            peer_id=sample_peer.id,
            remote_capsule_id="remote-1",
            local_capsule_id="local-1",
            remote_content_hash="original",
            local_content_hash="original",
        )

        remote_capsule = {
            "id": "remote-1",
            "content_hash": "remote_changed",
        }

        conflict = await sync_service._check_conflict(fed_capsule, remote_capsule)

        assert conflict is not None
        assert conflict.conflict_type == "content"

    @pytest.mark.asyncio
    async def test_resolve_conflict_local_wins(self, sync_service, sample_peer):
        """Test local_wins conflict resolution."""
        sample_peer.conflict_resolution = ConflictResolution.LOCAL_WINS

        conflict = SyncConflict(
            local_capsule={"id": "local-1"},
            remote_capsule={"id": "remote-1"},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "skip"
        assert conflict.resolution == "local_wins"

    @pytest.mark.asyncio
    async def test_resolve_conflict_remote_wins(self, sync_service, sample_peer):
        """Test remote_wins conflict resolution."""
        sample_peer.conflict_resolution = ConflictResolution.REMOTE_WINS

        conflict = SyncConflict(
            local_capsule={"id": "local-1"},
            remote_capsule={"id": "remote-1"},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "update"
        assert conflict.resolution == "remote_wins"

    @pytest.mark.asyncio
    async def test_resolve_conflict_higher_trust_remote(self, sync_service, sample_peer):
        """Test higher_trust resolution (remote wins)."""
        sample_peer.conflict_resolution = ConflictResolution.HIGHER_TRUST

        conflict = SyncConflict(
            local_capsule={"id": "local-1", "trust_level": 50},
            remote_capsule={"id": "remote-1", "trust_level": 80},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "update"
        assert conflict.resolution == "remote_higher_trust"

    @pytest.mark.asyncio
    async def test_resolve_conflict_higher_trust_local(self, sync_service, sample_peer):
        """Test higher_trust resolution (local wins)."""
        sample_peer.conflict_resolution = ConflictResolution.HIGHER_TRUST

        conflict = SyncConflict(
            local_capsule={"id": "local-1", "trust_level": 80},
            remote_capsule={"id": "remote-1", "trust_level": 50},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "skip"
        assert conflict.resolution == "local_higher_trust"

    @pytest.mark.asyncio
    async def test_resolve_conflict_newer_timestamp_remote(self, sync_service, sample_peer):
        """Test newer_timestamp resolution (remote wins)."""
        sample_peer.conflict_resolution = ConflictResolution.NEWER_TIMESTAMP

        conflict = SyncConflict(
            local_capsule={"id": "local-1", "updated_at": "2024-01-01T00:00:00"},
            remote_capsule={"id": "remote-1", "updated_at": "2024-01-02T00:00:00"},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "update"
        assert conflict.resolution == "remote_newer"

    @pytest.mark.asyncio
    async def test_resolve_conflict_merge(self, sync_service, sample_peer):
        """Test merge conflict resolution."""
        sample_peer.conflict_resolution = ConflictResolution.MERGE

        conflict = SyncConflict(
            local_capsule={"id": "local-1", "tags": ["a", "b"], "trust_level": 50},
            remote_capsule={"id": "remote-1", "tags": ["b", "c"], "trust_level": 60},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "update"
        assert conflict.resolution == "merged"
        # Merged tags should include all
        assert set(conflict.resolved_capsule["tags"]) == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_resolve_conflict_manual_review(self, sync_service, sample_peer):
        """Test manual_review conflict resolution."""
        sample_peer.conflict_resolution = ConflictResolution.MANUAL_REVIEW

        conflict = SyncConflict(
            local_capsule={"id": "local-1"},
            remote_capsule={"id": "remote-1"},
            conflict_type="content",
            reason="Both modified",
        )

        result = await sync_service._resolve_conflict(sample_peer, conflict)

        assert result == "skip"
        assert conflict.resolution == "pending_review"

    @pytest.mark.asyncio
    async def test_merge_capsules_rejects_remote_trust(self, sync_service):
        """Test merge never accepts remote trust level."""
        local = {"id": "local-1", "trust_level": 50, "tags": ["a"]}
        remote = {"id": "remote-1", "trust_level": 90, "tags": ["b"]}  # Higher trust

        merged = await sync_service._merge_capsules(local, remote)

        # Should keep local trust, not adopt remote
        assert merged["trust_level"] == 50

    @pytest.mark.asyncio
    async def test_merge_capsules_new_capsule(self, sync_service):
        """Test merge for new capsule sets UNVERIFIED trust."""
        remote = {"id": "remote-1", "trust_level": 90, "tags": ["a"]}

        merged = await sync_service._merge_capsules(None, remote)

        # Should use UNVERIFIED default (20)
        assert merged["trust_level"] == 20

    @pytest.mark.asyncio
    async def test_get_sync_state(self, sync_service):
        """Test getting sync state."""
        state = SyncState(
            id="sync-123",
            peer_id="peer-1",
            direction=SyncDirection.PULL,
        )
        sync_service._sync_states["sync-123"] = state

        result = await sync_service.get_sync_state("sync-123")

        assert result == state

    @pytest.mark.asyncio
    async def test_get_sync_state_not_found(self, sync_service):
        """Test getting non-existent sync state."""
        result = await sync_service.get_sync_state("unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_sync_history(self, sync_service):
        """Test getting sync history."""
        for i in range(5):
            state = SyncState(
                id=f"sync-{i}",
                peer_id="peer-1",
                direction=SyncDirection.PULL,
                started_at=datetime.now(UTC) - timedelta(hours=i),
            )
            sync_service._sync_states[f"sync-{i}"] = state

        history = await sync_service.get_sync_history()

        assert len(history) == 5
        # Should be sorted by started_at descending
        assert history[0].id == "sync-0"

    @pytest.mark.asyncio
    async def test_get_sync_history_filtered(self, sync_service):
        """Test getting filtered sync history."""
        sync_service._sync_states["sync-1"] = SyncState(
            id="sync-1",
            peer_id="peer-1",
            direction=SyncDirection.PULL,
        )
        sync_service._sync_states["sync-2"] = SyncState(
            id="sync-2",
            peer_id="peer-2",
            direction=SyncDirection.PULL,
        )

        history = await sync_service.get_sync_history(peer_id="peer-1")

        assert len(history) == 1
        assert history[0].peer_id == "peer-1"

    @pytest.mark.asyncio
    async def test_get_sync_history_limit(self, sync_service):
        """Test sync history limit."""
        for i in range(10):
            state = SyncState(
                id=f"sync-{i}",
                peer_id="peer-1",
                direction=SyncDirection.PULL,
            )
            sync_service._sync_states[f"sync-{i}"] = state

        history = await sync_service.get_sync_history(limit=3)

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_schedule_sync_all(self, sync_service, mock_protocol, mock_driver, sample_peer):
        """Test scheduling sync with all peers."""
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock sync response
        payload = MagicMock()
        payload.capsules = []
        payload.edges = []
        payload.deletions = []
        payload.has_more = False
        payload.content_hash = "hash"
        mock_protocol.send_sync_request.return_value = payload

        # Mock database
        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        mock_protocol.create_sync_payload.return_value = MagicMock()

        sync_ids = await sync_service.schedule_sync_all()

        assert len(sync_ids) == 1

    @pytest.mark.asyncio
    async def test_schedule_sync_all_skips_inactive(self, sync_service):
        """Test sync_all skips inactive peers."""
        peer = FederatedPeer(
            id="peer-1",
            name="Inactive",
            url="https://peer.com",
            public_key="key",
            status=PeerStatus.OFFLINE,
        )
        sync_service._peers[peer.id] = peer

        sync_ids = await sync_service.schedule_sync_all()

        assert len(sync_ids) == 0

    @pytest.mark.asyncio
    async def test_persist_peer(self, sync_service, mock_driver, sample_peer):
        """Test persisting peer to database."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"id": sample_peer.id}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await sync_service.persist_peer(sample_peer)

        assert success is True

    @pytest.mark.asyncio
    async def test_persist_trust_score(self, sync_service, mock_driver):
        """Test persisting trust score."""
        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = {"id": "peer-1"}
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await sync_service.persist_trust_score("peer-1", 0.75, "Manual adjustment")

        assert success is True

    def test_compute_content_hash(self, sync_service):
        """Test content hash computation."""
        capsules = [{"id": "1", "content": "test"}]
        edges = [{"id": "e1", "type": "RELATED_TO"}]
        deletions = ["d1"]

        hash1 = sync_service._compute_content_hash(capsules, edges, deletions)
        hash2 = sync_service._compute_content_hash(capsules, edges, deletions)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_compute_content_hash_different(self, sync_service):
        """Test content hash differs for different content."""
        hash1 = sync_service._compute_content_hash([{"id": "1"}], [], [])
        hash2 = sync_service._compute_content_hash([{"id": "2"}], [], [])

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_max_sync_iterations(self, sync_service, mock_protocol, sample_peer):
        """Test max sync iterations prevents DoS."""
        sample_peer.sync_direction = SyncDirection.PULL
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock payload that always says has_more=True
        payload = MagicMock()
        payload.capsules = []
        payload.edges = []
        payload.deletions = []
        payload.has_more = True  # Always more
        payload.content_hash = "hash"
        mock_protocol.send_sync_request.return_value = payload

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        # Should complete after hitting max iterations
        assert state.status == SyncOperationStatus.COMPLETED
        # Check iteration count via call count
        assert mock_protocol.send_sync_request.call_count <= SyncService.MAX_SYNC_ITERATIONS

    @pytest.mark.asyncio
    async def test_sync_states_bounded(self, sync_service, mock_protocol, mock_driver, sample_peer):
        """Test sync states are bounded to prevent memory exhaustion."""
        original_max = sync_service.MAX_SYNC_STATES
        sync_service.MAX_SYNC_STATES = 5

        sync_service._peers[sample_peer.id] = sample_peer

        # Mock successful sync
        payload = MagicMock()
        payload.capsules = []
        payload.edges = []
        payload.deletions = []
        payload.has_more = False
        payload.content_hash = "hash"
        mock_protocol.send_sync_request.return_value = payload

        session = AsyncMock()
        result = AsyncMock()
        result.data.return_value = []
        session.run.return_value = result
        mock_driver.session.return_value.__aenter__.return_value = session
        mock_protocol.create_sync_payload.return_value = MagicMock()

        # Run many syncs
        for _ in range(10):
            await sync_service.sync_with_peer(sample_peer.id, force=True)

        # Should be bounded
        assert len(sync_service._sync_states) <= 5

        sync_service.MAX_SYNC_STATES = original_max

    @pytest.mark.asyncio
    async def test_content_hash_verification(self, sync_service, mock_protocol, sample_peer):
        """Test content hash verification detects tampering."""
        sample_peer.sync_direction = SyncDirection.PULL
        sync_service._peers[sample_peer.id] = sample_peer

        # Mock payload with mismatched hash
        payload = MagicMock()
        payload.capsules = [{"id": "1", "content": "test"}]
        payload.edges = []
        payload.deletions = []
        payload.has_more = False
        payload.content_hash = "wrong_hash"  # Doesn't match content
        mock_protocol.send_sync_request.return_value = payload

        state = await sync_service.sync_with_peer(sample_peer.id, force=True)

        # Should fail due to hash mismatch
        assert state.status == SyncOperationStatus.FAILED
        assert "hash" in state.error_message.lower()
