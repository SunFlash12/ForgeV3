"""
Tests for federation models.
"""

import pytest
from datetime import datetime, UTC, timedelta
from pydantic import ValidationError

from forge.federation.models import (
    PeerStatus,
    SyncDirection,
    ConflictResolution,
    FederatedSyncStatus,
    SyncOperationStatus,
    SyncPhase,
    FederatedPeer,
    FederatedCapsule,
    FederatedEdge,
    SyncState,
    PeerHandshake,
    SyncPayload,
    FederationStats,
)


class TestPeerStatusEnum:
    """Tests for PeerStatus enum."""

    def test_all_values(self):
        """Test all PeerStatus values exist."""
        assert PeerStatus.PENDING == "pending"
        assert PeerStatus.ACTIVE == "active"
        assert PeerStatus.DEGRADED == "degraded"
        assert PeerStatus.SUSPENDED == "suspended"
        assert PeerStatus.OFFLINE == "offline"
        assert PeerStatus.REVOKED == "revoked"

    def test_from_string(self):
        """Test creating PeerStatus from string."""
        assert PeerStatus("pending") == PeerStatus.PENDING
        assert PeerStatus("active") == PeerStatus.ACTIVE

    def test_invalid_value(self):
        """Test invalid PeerStatus value."""
        with pytest.raises(ValueError):
            PeerStatus("invalid")


class TestSyncDirectionEnum:
    """Tests for SyncDirection enum."""

    def test_all_values(self):
        """Test all SyncDirection values exist."""
        assert SyncDirection.PUSH == "push"
        assert SyncDirection.PULL == "pull"
        assert SyncDirection.BIDIRECTIONAL == "bidirectional"

    def test_from_string(self):
        """Test creating SyncDirection from string."""
        assert SyncDirection("push") == SyncDirection.PUSH
        assert SyncDirection("bidirectional") == SyncDirection.BIDIRECTIONAL


class TestConflictResolutionEnum:
    """Tests for ConflictResolution enum."""

    def test_all_values(self):
        """Test all ConflictResolution values exist."""
        assert ConflictResolution.HIGHER_TRUST == "higher_trust"
        assert ConflictResolution.NEWER_TIMESTAMP == "newer_timestamp"
        assert ConflictResolution.MANUAL_REVIEW == "manual_review"
        assert ConflictResolution.MERGE == "merge"
        assert ConflictResolution.LOCAL_WINS == "local_wins"
        assert ConflictResolution.REMOTE_WINS == "remote_wins"


class TestFederatedSyncStatusEnum:
    """Tests for FederatedSyncStatus enum."""

    def test_all_values(self):
        """Test all FederatedSyncStatus values exist."""
        assert FederatedSyncStatus.PENDING == "pending"
        assert FederatedSyncStatus.SYNCED == "synced"
        assert FederatedSyncStatus.CONFLICT == "conflict"
        assert FederatedSyncStatus.REJECTED == "rejected"
        assert FederatedSyncStatus.SKIPPED == "skipped"


class TestSyncOperationStatusEnum:
    """Tests for SyncOperationStatus enum."""

    def test_all_values(self):
        """Test all SyncOperationStatus values exist."""
        assert SyncOperationStatus.RUNNING == "running"
        assert SyncOperationStatus.COMPLETED == "completed"
        assert SyncOperationStatus.FAILED == "failed"
        assert SyncOperationStatus.CANCELLED == "cancelled"


class TestSyncPhaseEnum:
    """Tests for SyncPhase enum."""

    def test_all_values(self):
        """Test all SyncPhase values exist."""
        assert SyncPhase.INIT == "init"
        assert SyncPhase.FETCHING == "fetching"
        assert SyncPhase.PROCESSING == "processing"
        assert SyncPhase.APPLYING == "applying"
        assert SyncPhase.FINALIZING == "finalizing"


class TestFederatedPeer:
    """Tests for FederatedPeer model."""

    def test_create_minimal(self):
        """Test creating peer with minimal fields."""
        peer = FederatedPeer(
            name="Test Peer",
            url="https://peer.example.com",
            public_key="base64encodedkey==",
        )
        assert peer.name == "Test Peer"
        assert peer.url == "https://peer.example.com"
        assert peer.public_key == "base64encodedkey=="
        assert peer.id is not None  # Auto-generated
        assert peer.status == PeerStatus.PENDING
        assert peer.trust_score == 0.3  # Default initial trust

    def test_create_full(self):
        """Test creating peer with all fields."""
        now = datetime.now(UTC)
        peer = FederatedPeer(
            id="peer-123",
            name="Full Peer",
            url="https://full.example.com",
            public_key="pubkey123==",
            our_public_key="ourkey123==",
            trust_score=0.75,
            status=PeerStatus.ACTIVE,
            sync_direction=SyncDirection.BIDIRECTIONAL,
            sync_interval_minutes=30,
            conflict_resolution=ConflictResolution.HIGHER_TRUST,
            sync_capsule_types=["knowledge", "code"],
            min_trust_to_sync=60,
            description="A full peer",
            admin_contact="admin@example.com",
            registered_at=now,
            last_sync_at=now,
            last_seen_at=now,
            total_syncs=100,
            successful_syncs=95,
            failed_syncs=5,
            capsules_received=500,
            capsules_sent=300,
        )
        assert peer.id == "peer-123"
        assert peer.trust_score == 0.75
        assert peer.status == PeerStatus.ACTIVE
        assert peer.sync_interval_minutes == 30
        assert peer.min_trust_to_sync == 60

    def test_trust_score_bounds(self):
        """Test trust_score validation bounds."""
        # Valid bounds
        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            trust_score=0.0,
        )
        assert peer.trust_score == 0.0

        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            trust_score=1.0,
        )
        assert peer.trust_score == 1.0

        # Out of bounds
        with pytest.raises(ValidationError):
            FederatedPeer(
                name="Test",
                url="https://test.com",
                public_key="key==",
                trust_score=-0.1,
            )

        with pytest.raises(ValidationError):
            FederatedPeer(
                name="Test",
                url="https://test.com",
                public_key="key==",
                trust_score=1.1,
            )

    def test_trust_score_as_int_property(self):
        """Test trust_score_as_int conversion."""
        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            trust_score=0.75,
        )
        assert peer.trust_score_as_int == 75

        peer.trust_score = 0.0
        assert peer.trust_score_as_int == 0

        peer.trust_score = 1.0
        assert peer.trust_score_as_int == 100

    def test_sync_interval_minimum(self):
        """Test sync_interval_minutes minimum validation."""
        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            sync_interval_minutes=5,  # Minimum
        )
        assert peer.sync_interval_minutes == 5

        with pytest.raises(ValidationError):
            FederatedPeer(
                name="Test",
                url="https://test.com",
                public_key="key==",
                sync_interval_minutes=4,  # Below minimum
            )

    def test_min_trust_to_sync_bounds(self):
        """Test min_trust_to_sync validation."""
        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            min_trust_to_sync=0,
        )
        assert peer.min_trust_to_sync == 0

        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
            min_trust_to_sync=100,
        )
        assert peer.min_trust_to_sync == 100

        with pytest.raises(ValidationError):
            FederatedPeer(
                name="Test",
                url="https://test.com",
                public_key="key==",
                min_trust_to_sync=-1,
            )

        with pytest.raises(ValidationError):
            FederatedPeer(
                name="Test",
                url="https://test.com",
                public_key="key==",
                min_trust_to_sync=101,
            )

    def test_serialization(self):
        """Test peer serialization."""
        peer = FederatedPeer(
            name="Test",
            url="https://test.com",
            public_key="key==",
        )
        data = peer.model_dump()
        assert data["name"] == "Test"
        assert data["url"] == "https://test.com"
        assert "id" in data


class TestFederatedCapsule:
    """Tests for FederatedCapsule model."""

    def test_create_minimal(self):
        """Test creating federated capsule with minimal fields."""
        fc = FederatedCapsule(
            peer_id="peer-123",
            remote_capsule_id="remote-cap-456",
            remote_content_hash="abc123hash",
        )
        assert fc.peer_id == "peer-123"
        assert fc.remote_capsule_id == "remote-cap-456"
        assert fc.remote_content_hash == "abc123hash"
        assert fc.sync_status == FederatedSyncStatus.PENDING
        assert fc.local_capsule_id is None

    def test_create_synced(self):
        """Test creating synced federated capsule."""
        fc = FederatedCapsule(
            peer_id="peer-123",
            remote_capsule_id="remote-cap-456",
            remote_content_hash="abc123hash",
            local_capsule_id="local-cap-789",
            local_content_hash="abc123hash",
            sync_status=FederatedSyncStatus.SYNCED,
            remote_title="Test Capsule",
            remote_type="knowledge",
            remote_trust_level=75,
            remote_owner_id="user-123",
        )
        assert fc.local_capsule_id == "local-cap-789"
        assert fc.sync_status == FederatedSyncStatus.SYNCED
        assert fc.remote_title == "Test Capsule"

    def test_conflict_state(self):
        """Test federated capsule in conflict state."""
        fc = FederatedCapsule(
            peer_id="peer-123",
            remote_capsule_id="remote-cap-456",
            remote_content_hash="abc123hash",
            sync_status=FederatedSyncStatus.CONFLICT,
            conflict_reason="Content hash mismatch",
        )
        assert fc.sync_status == FederatedSyncStatus.CONFLICT
        assert fc.conflict_reason == "Content hash mismatch"


class TestFederatedEdge:
    """Tests for FederatedEdge model."""

    def test_create_minimal(self):
        """Test creating federated edge with minimal fields."""
        edge = FederatedEdge(
            peer_id="peer-123",
            remote_edge_id="edge-456",
            source_capsule_id="cap-1",
            target_capsule_id="cap-2",
            relationship_type="RELATED_TO",
        )
        assert edge.peer_id == "peer-123"
        assert edge.relationship_type == "RELATED_TO"
        assert edge.source_is_local is False
        assert edge.target_is_local is False

    def test_create_local_edge(self):
        """Test creating edge with local capsules."""
        edge = FederatedEdge(
            peer_id="peer-123",
            remote_edge_id="edge-456",
            source_capsule_id="local-cap-1",
            target_capsule_id="local-cap-2",
            relationship_type="DERIVED_FROM",
            source_is_local=True,
            target_is_local=True,
            local_edge_id="local-edge-789",
            sync_status=FederatedSyncStatus.SYNCED,
        )
        assert edge.source_is_local is True
        assert edge.target_is_local is True
        assert edge.local_edge_id == "local-edge-789"


class TestSyncState:
    """Tests for SyncState model."""

    def test_create_new_sync(self):
        """Test creating new sync state."""
        state = SyncState(
            peer_id="peer-123",
            direction=SyncDirection.PULL,
        )
        assert state.peer_id == "peer-123"
        assert state.direction == SyncDirection.PULL
        assert state.status == SyncOperationStatus.RUNNING
        assert state.phase == SyncPhase.INIT
        assert state.capsules_fetched == 0

    def test_sync_progress(self):
        """Test sync state with progress."""
        state = SyncState(
            peer_id="peer-123",
            direction=SyncDirection.BIDIRECTIONAL,
            status=SyncOperationStatus.RUNNING,
            phase=SyncPhase.PROCESSING,
            capsules_fetched=50,
            capsules_created=30,
            capsules_updated=15,
            capsules_skipped=3,
            capsules_conflicted=2,
            edges_fetched=20,
            edges_created=18,
            edges_skipped=2,
        )
        assert state.capsules_fetched == 50
        assert state.capsules_created == 30
        assert state.capsules_conflicted == 2

    def test_sync_completed(self):
        """Test completed sync state."""
        now = datetime.now(UTC)
        state = SyncState(
            peer_id="peer-123",
            direction=SyncDirection.PUSH,
            started_at=now - timedelta(minutes=5),
            completed_at=now,
            status=SyncOperationStatus.COMPLETED,
            phase=SyncPhase.FINALIZING,
        )
        assert state.status == SyncOperationStatus.COMPLETED
        assert state.completed_at is not None

    def test_sync_failed(self):
        """Test failed sync state."""
        state = SyncState(
            peer_id="peer-123",
            direction=SyncDirection.PULL,
            status=SyncOperationStatus.FAILED,
            error_message="Connection timeout",
            error_details={"timeout_seconds": 30},
        )
        assert state.status == SyncOperationStatus.FAILED
        assert state.error_message == "Connection timeout"
        assert state.error_details["timeout_seconds"] == 30


class TestPeerHandshake:
    """Tests for PeerHandshake model."""

    def test_create_handshake(self):
        """Test creating peer handshake."""
        now = datetime.now(UTC)
        handshake = PeerHandshake(
            instance_id="instance-123",
            instance_name="Test Forge",
            api_version="1.0",
            public_key="pubkey==",
            signature="signature==",
            timestamp=now,
        )
        assert handshake.instance_id == "instance-123"
        assert handshake.api_version == "1.0"
        assert handshake.supports_push is True
        assert handshake.supports_pull is True
        assert handshake.supports_streaming is False
        assert handshake.nonce is None  # Optional for backward compatibility

    def test_handshake_with_nonce(self):
        """Test handshake with nonce for replay prevention."""
        now = datetime.now(UTC)
        handshake = PeerHandshake(
            instance_id="instance-123",
            instance_name="Secure Forge",
            api_version="1.0",
            public_key="pubkey==",
            signature="signature==",
            timestamp=now,
            nonce="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        )
        assert handshake.nonce == "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"

    def test_handshake_full_config(self):
        """Test handshake with full configuration."""
        now = datetime.now(UTC)
        handshake = PeerHandshake(
            instance_id="instance-123",
            instance_name="Custom Forge",
            api_version="1.0",
            public_key="pubkey==",
            supports_push=True,
            supports_pull=True,
            supports_streaming=True,
            suggested_interval_minutes=30,
            max_capsules_per_sync=500,
            signature="signature==",
            timestamp=now,
        )
        assert handshake.supports_streaming is True
        assert handshake.suggested_interval_minutes == 30
        assert handshake.max_capsules_per_sync == 500


class TestSyncPayload:
    """Tests for SyncPayload model."""

    def test_create_empty_payload(self):
        """Test creating empty sync payload."""
        now = datetime.now(UTC)
        payload = SyncPayload(
            peer_id="peer-123",
            sync_id="sync-456",
            timestamp=now,
            content_hash="emptyhash",
            signature="sig==",
        )
        assert payload.peer_id == "peer-123"
        assert payload.capsules == []
        assert payload.edges == []
        assert payload.deletions == []
        assert payload.has_more is False

    def test_create_full_payload(self):
        """Test creating payload with content."""
        now = datetime.now(UTC)
        capsules = [
            {"id": "cap-1", "title": "Test", "content": "Content"},
            {"id": "cap-2", "title": "Test 2", "content": "Content 2"},
        ]
        edges = [
            {"id": "edge-1", "source_id": "cap-1", "target_id": "cap-2"},
        ]
        deletions = ["old-cap-1", "old-cap-2"]

        payload = SyncPayload(
            peer_id="peer-123",
            sync_id="sync-456",
            timestamp=now,
            capsules=capsules,
            edges=edges,
            deletions=deletions,
            has_more=True,
            next_cursor="cursor123",
            content_hash="fullhash",
            signature="sig==",
            nonce="nonce123456789012345678901234",
        )
        assert len(payload.capsules) == 2
        assert len(payload.edges) == 1
        assert len(payload.deletions) == 2
        assert payload.has_more is True
        assert payload.next_cursor == "cursor123"
        assert payload.nonce is not None


class TestFederationStats:
    """Tests for FederationStats model."""

    def test_create_empty_stats(self):
        """Test creating empty federation stats."""
        stats = FederationStats()
        assert stats.total_peers == 0
        assert stats.active_peers == 0
        assert stats.pending_peers == 0
        assert stats.total_federated_capsules == 0

    def test_create_populated_stats(self):
        """Test creating populated federation stats."""
        now = datetime.now(UTC)
        stats = FederationStats(
            total_peers=10,
            active_peers=7,
            pending_peers=3,
            total_federated_capsules=1000,
            synced_capsules=950,
            pending_capsules=30,
            conflicted_capsules=20,
            total_federated_edges=500,
            last_sync_at=now,
            syncs_today=25,
            syncs_failed_today=2,
            bytes_received_today=1024000,
            bytes_sent_today=512000,
        )
        assert stats.total_peers == 10
        assert stats.active_peers == 7
        assert stats.synced_capsules == 950
        assert stats.bytes_received_today == 1024000
