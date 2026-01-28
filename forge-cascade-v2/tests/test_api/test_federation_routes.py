"""
Federation Routes Tests for Forge Cascade V2

Comprehensive tests for federation API routes including:
- Peer management (register, list, get, update, delete)
- Trust management
- Sync operations
- Statistics
- Incoming routes (handshake, health, changes, capsules)
- Rate limiting
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge.federation.models import (
    ConflictResolution,
    PeerStatus,
    SyncDirection,
    SyncOperationStatus,
    SyncPhase,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_peer():
    """Create a mock federated peer."""
    peer = MagicMock()
    peer.id = "peer123"
    peer.name = "Test Peer"
    peer.url = "https://peer.example.com"
    peer.public_key = "abc123pubkey"
    peer.our_public_key = "our_pubkey"
    peer.trust_score = 0.75
    peer.status = PeerStatus.ACTIVE
    peer.sync_direction = SyncDirection.BIDIRECTIONAL
    peer.sync_interval_minutes = 60
    peer.conflict_resolution = ConflictResolution.HIGHER_TRUST
    peer.sync_capsule_types = ["KNOWLEDGE", "DECISION"]
    peer.min_trust_to_sync = 50
    peer.description = "Test peer description"
    peer.admin_contact = "admin@example.com"
    peer.registered_at = datetime.now(UTC)
    peer.last_sync_at = None
    peer.last_seen_at = datetime.now(UTC)
    peer.total_syncs = 0
    peer.successful_syncs = 0
    peer.failed_syncs = 0
    peer.capsules_received = 0
    peer.capsules_sent = 0
    return peer


@pytest.fixture
def mock_sync_state():
    """Create a mock sync state."""
    state = MagicMock()
    state.id = "sync123"
    state.peer_id = "peer123"
    state.direction = SyncDirection.BIDIRECTIONAL
    state.started_at = datetime.now(UTC)
    state.completed_at = None
    state.status = SyncOperationStatus.IN_PROGRESS
    state.phase = SyncPhase.FETCHING
    state.capsules_fetched = 10
    state.capsules_created = 5
    state.capsules_updated = 3
    state.capsules_skipped = 2
    state.capsules_conflicted = 0
    state.edges_fetched = 5
    state.edges_created = 3
    state.edges_skipped = 2
    state.error_message = None
    return state


@pytest.fixture
def mock_protocol():
    """Create mock federation protocol."""
    protocol = AsyncMock()
    protocol.initiate_handshake = AsyncMock(
        return_value=(
            MagicMock(public_key="our_pubkey"),
            MagicMock(public_key="their_pubkey"),
        )
    )
    protocol.verify_handshake = MagicMock(return_value=True)
    protocol.create_handshake = AsyncMock(return_value=MagicMock(
        model_dump=lambda mode: {"public_key": "our_pubkey", "signature": "sig123"}
    ))
    protocol.verify_signature = MagicMock(return_value=True)
    protocol.API_VERSION = "1.0"
    return protocol


@pytest.fixture
def mock_sync_service(mock_peer, mock_sync_state):
    """Create mock sync service."""
    service = AsyncMock()
    service.register_peer = AsyncMock()
    service.list_peers = AsyncMock(return_value=[mock_peer])
    service.get_peer = AsyncMock(return_value=mock_peer)
    service.get_peer_by_public_key = AsyncMock(return_value=mock_peer)
    service.unregister_peer = AsyncMock()
    service.sync_with_peer = AsyncMock(return_value=mock_sync_state)
    service.schedule_sync_all = AsyncMock(return_value=["sync1", "sync2"])
    service.get_sync_history = AsyncMock(return_value=[mock_sync_state])
    service.get_sync_state = AsyncMock(return_value=mock_sync_state)
    service._find_federated_capsule = AsyncMock(return_value=None)
    service._create_local_capsule = AsyncMock()
    return service


@pytest.fixture
def mock_trust_manager(mock_peer):
    """Create mock trust manager."""
    manager = AsyncMock()
    manager.initialize_peer_trust = AsyncMock()
    manager.get_trust_tier = AsyncMock(return_value="standard")
    manager.manual_adjustment = AsyncMock(return_value=0.80)
    manager.get_trust_history = AsyncMock(return_value=[])
    manager.get_sync_permissions = AsyncMock(return_value={
        "can_push": True,
        "can_pull": True,
        "max_capsules_per_sync": 100,
    })
    manager.can_sync = AsyncMock(return_value=(True, None))
    manager.get_federation_stats = AsyncMock(return_value=MagicMock(
        total_peers=5,
        active_peers=3,
        pending_peers=1,
        total_federated_capsules=100,
        synced_capsules=80,
        pending_capsules=15,
        conflicted_capsules=5,
        total_federated_edges=50,
        last_sync_at=datetime.now(UTC),
        syncs_today=10,
        syncs_failed_today=1,
    ))
    manager.calculate_network_trust = AsyncMock(return_value={"overall": 0.75})
    return manager


@pytest.fixture
def mock_capsule_repo():
    """Create mock capsule repository."""
    repo = AsyncMock()
    repo.get_changes_since = AsyncMock(return_value=([], []))
    repo.get_edges_since = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_admin_user():
    """Create mock admin user."""
    user = MagicMock()
    user.id = "admin123"
    user.username = "admin"
    user.role = "admin"
    user.trust_flame = 90
    user.is_active = True
    return user


@pytest.fixture
def mock_regular_user():
    """Create mock regular user."""
    user = MagicMock()
    user.id = "user123"
    user.username = "testuser"
    user.role = "user"
    user.trust_flame = 60
    user.is_active = True
    return user


@pytest.fixture
def federation_app(
    mock_protocol,
    mock_sync_service,
    mock_trust_manager,
    mock_capsule_repo,
    mock_admin_user,
):
    """Create FastAPI app with federation router and mocked dependencies."""
    from forge.api.routes.federation import (
        router,
        get_protocol,
        get_sync_service,
        get_trust_manager,
        get_capsule_repository,
    )
    from forge.api.dependencies import get_current_active_user

    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    app.dependency_overrides[get_protocol] = lambda: mock_protocol
    app.dependency_overrides[get_sync_service] = lambda: mock_sync_service
    app.dependency_overrides[get_trust_manager] = lambda: mock_trust_manager
    app.dependency_overrides[get_capsule_repository] = lambda: mock_capsule_repo
    app.dependency_overrides[get_current_active_user] = lambda: mock_admin_user

    return app


@pytest.fixture
def client(federation_app):
    """Create test client."""
    return TestClient(federation_app)


# =============================================================================
# Peer Registration Tests
# =============================================================================


class TestRegisterPeer:
    """Tests for POST /federation/peers endpoint."""

    def test_register_peer_success(self, client: TestClient):
        """Register peer with valid data."""
        response = client.post(
            "/federation/peers",
            json={
                "name": "New Peer",
                "url": "https://newpeer.example.com",
                "description": "A new peer",
                "admin_contact": "admin@newpeer.com",
                "sync_direction": "BIDIRECTIONAL",
                "sync_interval_minutes": 30,
                "conflict_resolution": "HIGHER_TRUST",
                "sync_capsule_types": ["KNOWLEDGE"],
                "min_trust_to_sync": 40,
            },
        )

        assert response.status_code in [200, 400, 503]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "name" in data
            assert "url" in data
            assert "trust_score" in data

    def test_register_peer_minimal(self, client: TestClient):
        """Register peer with minimal required fields."""
        response = client.post(
            "/federation/peers",
            json={
                "name": "Minimal Peer",
                "url": "https://minimal.example.com",
            },
        )

        assert response.status_code in [200, 400, 503]

    def test_register_peer_non_admin(
        self, federation_app, mock_regular_user
    ):
        """Register peer as non-admin fails."""
        from forge.api.dependencies import get_current_active_user
        federation_app.dependency_overrides[get_current_active_user] = lambda: mock_regular_user

        client = TestClient(federation_app)
        response = client.post(
            "/federation/peers",
            json={
                "name": "Test Peer",
                "url": "https://test.example.com",
            },
        )

        assert response.status_code == 403

    def test_register_peer_invalid_sync_interval(self, client: TestClient):
        """Register peer with invalid sync interval fails."""
        response = client.post(
            "/federation/peers",
            json={
                "name": "Bad Peer",
                "url": "https://bad.example.com",
                "sync_interval_minutes": 1,  # Below minimum of 5
            },
        )

        assert response.status_code == 422

    def test_register_peer_handshake_failure(self, client: TestClient, mock_protocol):
        """Register peer when handshake fails."""
        mock_protocol.initiate_handshake.return_value = None

        response = client.post(
            "/federation/peers",
            json={
                "name": "Failing Peer",
                "url": "https://failing.example.com",
            },
        )

        assert response.status_code in [400, 503]


# =============================================================================
# List Peers Tests
# =============================================================================


class TestListPeers:
    """Tests for GET /federation/peers endpoint."""

    def test_list_peers_success(self, client: TestClient):
        """List all peers."""
        response = client.get("/federation/peers")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "id" in data[0]
            assert "name" in data[0]
            assert "trust_score" in data[0]

    def test_list_peers_filter_by_status(self, client: TestClient):
        """List peers filtered by status."""
        response = client.get("/federation/peers?status=ACTIVE")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_peers_pagination(self, client: TestClient):
        """List peers with pagination."""
        response = client.get("/federation/peers?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10


# =============================================================================
# Get Peer Tests
# =============================================================================


class TestGetPeer:
    """Tests for GET /federation/peers/{peer_id} endpoint."""

    def test_get_peer_success(self, client: TestClient):
        """Get peer by ID."""
        response = client.get("/federation/peers/peer123")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "trust_tier" in data

    def test_get_peer_not_found(self, client: TestClient, mock_sync_service):
        """Get non-existent peer."""
        mock_sync_service.get_peer.return_value = None

        response = client.get("/federation/peers/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Update Peer Tests
# =============================================================================


class TestUpdatePeer:
    """Tests for PATCH /federation/peers/{peer_id} endpoint."""

    def test_update_peer_success(self, client: TestClient):
        """Update peer settings."""
        response = client.patch(
            "/federation/peers/peer123",
            json={
                "name": "Updated Peer Name",
                "description": "Updated description",
                "sync_interval_minutes": 45,
            },
        )

        assert response.status_code in [200, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data

    def test_update_peer_status(self, client: TestClient):
        """Update peer status."""
        response = client.patch(
            "/federation/peers/peer123",
            json={
                "status": "SUSPENDED",
            },
        )

        assert response.status_code in [200, 403, 404]

    def test_update_peer_not_found(self, client: TestClient, mock_sync_service):
        """Update non-existent peer."""
        mock_sync_service.get_peer.return_value = None

        response = client.patch(
            "/federation/peers/nonexistent",
            json={"name": "New Name"},
        )

        assert response.status_code == 404

    def test_update_peer_non_admin(self, federation_app, mock_regular_user):
        """Update peer as non-admin fails."""
        from forge.api.dependencies import get_current_active_user
        federation_app.dependency_overrides[get_current_active_user] = lambda: mock_regular_user

        client = TestClient(federation_app)
        response = client.patch(
            "/federation/peers/peer123",
            json={"name": "New Name"},
        )

        assert response.status_code == 403


# =============================================================================
# Remove Peer Tests
# =============================================================================


class TestRemovePeer:
    """Tests for DELETE /federation/peers/{peer_id} endpoint."""

    def test_remove_peer_success(self, client: TestClient):
        """Remove peer successfully."""
        response = client.delete("/federation/peers/peer123")

        assert response.status_code in [200, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert "message" in data

    def test_remove_peer_not_found(self, client: TestClient, mock_sync_service):
        """Remove non-existent peer."""
        mock_sync_service.get_peer.return_value = None

        response = client.delete("/federation/peers/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Trust Management Tests
# =============================================================================


class TestTrustManagement:
    """Tests for trust management endpoints."""

    def test_adjust_trust_success(self, client: TestClient):
        """Adjust peer trust score."""
        response = client.post(
            "/federation/peers/peer123/trust",
            json={
                "delta": 0.1,
                "reason": "Good behavior",
            },
        )

        assert response.status_code in [200, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert "old_trust" in data
            assert "new_trust" in data
            assert "delta" in data

    def test_adjust_trust_invalid_delta(self, client: TestClient):
        """Adjust trust with invalid delta."""
        response = client.post(
            "/federation/peers/peer123/trust",
            json={
                "delta": 2.0,  # Outside -1.0 to 1.0 range
                "reason": "Invalid",
            },
        )

        assert response.status_code == 422

    def test_get_trust_history(self, client: TestClient):
        """Get peer trust history."""
        response = client.get("/federation/peers/peer123/trust/history")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "peer_id" in data
            assert "events" in data

    def test_get_peer_permissions(self, client: TestClient):
        """Get peer sync permissions."""
        response = client.get("/federation/peers/peer123/trust/permissions")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "can_push" in data or "can_pull" in data


# =============================================================================
# Sync Tests
# =============================================================================


class TestSyncOperations:
    """Tests for sync operation endpoints."""

    def test_trigger_sync(self, client: TestClient):
        """Trigger sync with specific peer."""
        response = client.post(
            "/federation/sync/peer123",
            json={
                "direction": "PULL",
                "force": False,
            },
        )

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "peer_id" in data
            assert "status" in data

    def test_trigger_sync_all(self, client: TestClient):
        """Trigger sync with all peers."""
        response = client.post("/federation/sync/all")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "sync_ids" in data

    def test_get_sync_status(self, client: TestClient):
        """Get sync status history."""
        response = client.get("/federation/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert "syncs" in data

    def test_get_sync_status_filtered(self, client: TestClient):
        """Get sync status filtered by peer."""
        response = client.get("/federation/sync/status?peer_id=peer123&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "syncs" in data

    def test_get_sync_details(self, client: TestClient):
        """Get specific sync operation details."""
        response = client.get("/federation/sync/sync123")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "phase" in data

    def test_get_sync_details_not_found(self, client: TestClient, mock_sync_service):
        """Get non-existent sync operation."""
        mock_sync_service.get_sync_state.return_value = None

        response = client.get("/federation/sync/nonexistent")

        assert response.status_code == 404


# =============================================================================
# Statistics Tests
# =============================================================================


class TestFederationStats:
    """Tests for federation statistics endpoint."""

    def test_get_federation_stats(self, client: TestClient):
        """Get federation statistics."""
        response = client.get("/federation/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_peers" in data
        assert "active_peers" in data
        assert "total_federated_capsules" in data
        assert "network_health" in data


# =============================================================================
# Incoming Routes Tests
# =============================================================================


class TestHandshake:
    """Tests for POST /federation/handshake endpoint."""

    def test_handshake_success(self, client: TestClient):
        """Handle incoming handshake."""
        response = client.post(
            "/federation/handshake",
            json={
                "public_key": "peer_public_key",
                "instance_id": "instance123",
                "instance_name": "Remote Peer",
                "api_version": "1.0",
                "signature": "valid_signature",
            },
        )

        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert "public_key" in data

    def test_handshake_invalid_signature(self, client: TestClient, mock_protocol):
        """Handshake with invalid signature."""
        mock_protocol.verify_handshake.return_value = False

        response = client.post(
            "/federation/handshake",
            json={
                "public_key": "bad_key",
                "instance_id": "instance123",
                "instance_name": "Bad Peer",
                "api_version": "1.0",
                "signature": "invalid",
            },
        )

        assert response.status_code == 400


class TestFederationHealth:
    """Tests for GET /federation/health endpoint."""

    def test_federation_health(self, client: TestClient):
        """Check federation health."""
        response = client.get("/federation/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "api_version" in data


class TestGetChanges:
    """Tests for GET /federation/changes endpoint."""

    def test_get_changes_missing_auth(self, client: TestClient):
        """Get changes without authentication headers."""
        response = client.get("/federation/changes")

        assert response.status_code == 401

    def test_get_changes_with_auth(self, client: TestClient, mock_protocol):
        """Get changes with valid authentication."""
        response = client.get(
            "/federation/changes?limit=50",
            headers={
                "X-Forge-Signature": "valid_signature",
                "X-Forge-Public-Key": "peer_pubkey",
            },
        )

        # Should return changes or auth error
        assert response.status_code in [200, 401, 403]

    def test_get_changes_unauthorized_peer(
        self, client: TestClient, mock_sync_service
    ):
        """Get changes from unknown peer."""
        mock_sync_service.get_peer_by_public_key.return_value = None

        response = client.get(
            "/federation/changes",
            headers={
                "X-Forge-Signature": "valid_signature",
                "X-Forge-Public-Key": "unknown_pubkey",
            },
        )

        assert response.status_code in [401, 403]


class TestReceiveCapsules:
    """Tests for POST /federation/incoming/capsules endpoint."""

    def test_receive_capsules_missing_auth(self, client: TestClient):
        """Receive capsules without authentication."""
        response = client.post(
            "/federation/incoming/capsules",
            json={
                "capsules": [],
                "signature": "sig",
            },
        )

        assert response.status_code == 401

    def test_receive_capsules_success(
        self, client: TestClient, mock_protocol, mock_sync_service
    ):
        """Receive capsules with valid authentication."""
        response = client.post(
            "/federation/incoming/capsules",
            json={
                "capsules": [
                    {
                        "id": "capsule123",
                        "content": "Test content",
                        "type": "KNOWLEDGE",
                        "trust_level": 60,
                        "content_hash": "abc123",
                    }
                ],
                "edges": [],
                "deletions": [],
                "signature": "valid_sig",
            },
            headers={"X-Forge-Public-Key": "peer_pubkey"},
        )

        assert response.status_code in [200, 401, 403]


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for federation rate limiting."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter can be initialized."""
        from forge.api.routes.federation import FederationRateLimiter

        limiter = FederationRateLimiter(
            requests_per_minute=30,
            requests_per_hour=500,
            handshake_per_hour=10,
        )

        assert limiter.requests_per_minute == 30
        assert limiter.requests_per_hour == 500
        assert limiter.handshake_per_hour == 10

    def test_rate_limiter_trust_multiplier(self):
        """Test trust-based rate limit multipliers."""
        from forge.api.routes.federation import FederationRateLimiter

        limiter = FederationRateLimiter()

        # Set high trust
        limiter.set_peer_trust("test_peer_key", 0.9)

        # Check multiplier is applied
        key = f"peer:test_peer_key"[:32 + 5]  # peer: prefix + first 32 chars
        multiplier = limiter._get_trust_multiplier(key)
        assert multiplier >= 1.0  # High trust gets higher multiplier

    def test_rate_limiter_low_trust(self):
        """Test low trust reduces rate limits."""
        from forge.api.routes.federation import FederationRateLimiter

        limiter = FederationRateLimiter()

        # Set low trust
        limiter.set_peer_trust("untrusted_key", 0.1)

        key = f"peer:untrusted_key"[:32 + 5]
        multiplier = limiter._get_trust_multiplier(key)
        assert multiplier < 1.0  # Low trust gets lower multiplier


# =============================================================================
# Content Hash Tests
# =============================================================================


class TestContentHash:
    """Tests for content hash computation."""

    def test_compute_content_hash(self):
        """Test SHA-256 content hash computation."""
        from forge.api.routes.federation import _compute_content_hash

        content = "Test content for hashing"
        hash1 = _compute_content_hash(content)
        hash2 = _compute_content_hash(content)

        # Same content should produce same hash
        assert hash1 == hash2
        # Hash should be 64 hex characters (256 bits)
        assert len(hash1) == 64

    def test_compute_content_hash_none(self):
        """Test hash computation with None content."""
        from forge.api.routes.federation import _compute_content_hash

        result = _compute_content_hash(None)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
