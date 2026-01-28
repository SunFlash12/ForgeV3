"""
Tests for federation trust manager.
"""

from datetime import UTC, datetime, timedelta

import pytest

from forge.federation.models import (
    FederatedPeer,
    PeerStatus,
)
from forge.federation.trust import (
    PeerTrustManager,
    TrustEvent,
)


class TestTrustEvent:
    """Tests for TrustEvent class."""

    def test_create_event(self):
        """Test creating trust event."""
        event = TrustEvent(
            peer_id="peer-123",
            event_type="sync_success",
            delta=0.02,
            reason="Successful sync",
        )
        assert event.peer_id == "peer-123"
        assert event.event_type == "sync_success"
        assert event.delta == 0.02
        assert event.reason == "Successful sync"
        assert event.timestamp is not None

    def test_create_event_with_timestamp(self):
        """Test creating event with explicit timestamp."""
        ts = datetime.now(UTC) - timedelta(hours=1)
        event = TrustEvent(
            peer_id="peer-123",
            event_type="sync_failure",
            delta=-0.05,
            reason="Connection timeout",
            timestamp=ts,
        )
        assert event.timestamp == ts


class TestPeerTrustManager:
    """Tests for PeerTrustManager class."""

    @pytest.fixture
    def trust_manager(self):
        """Create trust manager instance."""
        return PeerTrustManager()

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
        )

    @pytest.mark.asyncio
    async def test_initialize_peer_trust(self, trust_manager, sample_peer):
        """Test initializing trust for new peer."""
        sample_peer.trust_score = 0  # Reset to trigger initialization

        await trust_manager.initialize_peer_trust(sample_peer)

        assert sample_peer.trust_score == PeerTrustManager.INITIAL_TRUST
        assert sample_peer.id in trust_manager._peer_trust_cache

    @pytest.mark.asyncio
    async def test_initialize_peer_trust_preserves_existing(self, trust_manager, sample_peer):
        """Test initialization preserves existing trust."""
        sample_peer.trust_score = 0.7

        await trust_manager.initialize_peer_trust(sample_peer)

        assert sample_peer.trust_score == 0.7

    @pytest.mark.asyncio
    async def test_record_successful_sync(self, trust_manager, sample_peer):
        """Test recording successful sync increases trust."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.record_successful_sync(sample_peer)

        expected = min(1.0, initial_trust + PeerTrustManager.SYNC_SUCCESS_BONUS)
        assert new_trust == expected
        assert sample_peer.trust_score == expected

    @pytest.mark.asyncio
    async def test_record_successful_sync_capped_at_1(self, trust_manager, sample_peer):
        """Test trust is capped at 1.0."""
        sample_peer.trust_score = 0.99

        new_trust = await trust_manager.record_successful_sync(sample_peer)

        assert new_trust == 1.0

    @pytest.mark.asyncio
    async def test_record_failed_sync(self, trust_manager, sample_peer):
        """Test recording failed sync decreases trust."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.record_failed_sync(sample_peer)

        expected = max(0.0, initial_trust - PeerTrustManager.SYNC_FAILURE_PENALTY)
        assert new_trust == expected
        assert sample_peer.trust_score == expected

    @pytest.mark.asyncio
    async def test_record_failed_sync_floored_at_0(self, trust_manager, sample_peer):
        """Test trust is floored at 0.0."""
        sample_peer.trust_score = 0.02

        new_trust = await trust_manager.record_failed_sync(sample_peer)

        assert new_trust == 0.0

    @pytest.mark.asyncio
    async def test_failed_sync_suspends_peer(self, trust_manager, sample_peer):
        """Test peer is suspended when trust drops below threshold."""
        sample_peer.trust_score = 0.15  # Just above quarantine

        await trust_manager.record_failed_sync(sample_peer)

        assert sample_peer.status == PeerStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_record_conflict_unresolved(self, trust_manager, sample_peer):
        """Test recording unresolved conflict."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.record_conflict(sample_peer, "content", resolved=False)

        expected = max(0.0, initial_trust - PeerTrustManager.CONFLICT_PENALTY)
        assert new_trust == expected

    @pytest.mark.asyncio
    async def test_record_conflict_resolved(self, trust_manager, sample_peer):
        """Test recording resolved conflict (no penalty)."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.record_conflict(sample_peer, "content", resolved=True)

        assert new_trust == initial_trust

    @pytest.mark.asyncio
    async def test_manual_adjustment_increase(self, trust_manager, sample_peer):
        """Test manual trust increase."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.manual_adjustment(
            sample_peer,
            delta=0.1,
            reason="Good behavior",
            adjusted_by="admin",
        )

        assert new_trust == initial_trust + 0.1

    @pytest.mark.asyncio
    async def test_manual_adjustment_decrease(self, trust_manager, sample_peer):
        """Test manual trust decrease."""
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.manual_adjustment(
            sample_peer,
            delta=-0.1,
            reason="Policy violation",
            adjusted_by="admin",
        )

        assert new_trust == initial_trust - 0.1

    @pytest.mark.asyncio
    async def test_manual_adjustment_capped(self, trust_manager, sample_peer):
        """Test manual adjustment is capped at bounds."""
        sample_peer.trust_score = 0.95

        new_trust = await trust_manager.manual_adjustment(
            sample_peer,
            delta=0.2,
            reason="Exceptional peer",
            adjusted_by="admin",
        )

        assert new_trust == 1.0

    @pytest.mark.asyncio
    async def test_apply_inactivity_decay(self, trust_manager, sample_peer):
        """Test inactivity decay."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(weeks=2)
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.apply_inactivity_decay(sample_peer)

        # Should decay by 2 weeks worth
        expected_decay = PeerTrustManager.INACTIVITY_DECAY_RATE * 2
        expected = max(PeerTrustManager.INITIAL_TRUST, initial_trust - expected_decay)
        assert abs(new_trust - expected) < 0.001

    @pytest.mark.asyncio
    async def test_apply_inactivity_decay_no_last_seen(self, trust_manager, sample_peer):
        """Test no decay when last_seen_at is not set."""
        sample_peer.last_seen_at = None
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.apply_inactivity_decay(sample_peer)

        assert new_trust == initial_trust

    @pytest.mark.asyncio
    async def test_apply_inactivity_decay_recent(self, trust_manager, sample_peer):
        """Test no decay for recently seen peer."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(days=3)
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.apply_inactivity_decay(sample_peer)

        assert new_trust == initial_trust

    @pytest.mark.asyncio
    async def test_get_trust_tier_quarantine(self, trust_manager, sample_peer):
        """Test QUARANTINE tier."""
        sample_peer.trust_score = 0.1
        tier = await trust_manager.get_trust_tier(sample_peer)
        assert tier == "QUARANTINE"

    @pytest.mark.asyncio
    async def test_get_trust_tier_limited(self, trust_manager, sample_peer):
        """Test LIMITED tier."""
        sample_peer.trust_score = 0.3
        tier = await trust_manager.get_trust_tier(sample_peer)
        assert tier == "LIMITED"

    @pytest.mark.asyncio
    async def test_get_trust_tier_standard(self, trust_manager, sample_peer):
        """Test STANDARD tier."""
        sample_peer.trust_score = 0.5
        tier = await trust_manager.get_trust_tier(sample_peer)
        assert tier == "STANDARD"

    @pytest.mark.asyncio
    async def test_get_trust_tier_trusted(self, trust_manager, sample_peer):
        """Test TRUSTED tier."""
        sample_peer.trust_score = 0.7
        tier = await trust_manager.get_trust_tier(sample_peer)
        assert tier == "TRUSTED"

    @pytest.mark.asyncio
    async def test_get_trust_tier_core(self, trust_manager, sample_peer):
        """Test CORE tier."""
        sample_peer.trust_score = 0.9
        tier = await trust_manager.get_trust_tier(sample_peer)
        assert tier == "CORE"

    @pytest.mark.asyncio
    async def test_can_sync_quarantine(self, trust_manager, sample_peer):
        """Test sync not allowed for quarantined peer."""
        sample_peer.trust_score = 0.1

        can_sync, reason = await trust_manager.can_sync(sample_peer)

        assert can_sync is False
        assert "quarantined" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_sync_suspended(self, trust_manager, sample_peer):
        """Test sync not allowed for suspended peer."""
        sample_peer.status = PeerStatus.SUSPENDED

        can_sync, reason = await trust_manager.can_sync(sample_peer)

        assert can_sync is False
        assert "suspended" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_sync_revoked(self, trust_manager, sample_peer):
        """Test sync not allowed for revoked peer."""
        sample_peer.status = PeerStatus.REVOKED

        can_sync, reason = await trust_manager.can_sync(sample_peer)

        assert can_sync is False
        assert "revoked" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_sync_offline(self, trust_manager, sample_peer):
        """Test sync not allowed for offline peer."""
        sample_peer.status = PeerStatus.OFFLINE

        can_sync, reason = await trust_manager.can_sync(sample_peer)

        assert can_sync is False
        assert "offline" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_sync_active(self, trust_manager, sample_peer):
        """Test sync allowed for active peer with good trust."""
        sample_peer.trust_score = 0.5
        sample_peer.status = PeerStatus.ACTIVE

        can_sync, reason = await trust_manager.can_sync(sample_peer)

        assert can_sync is True
        assert "allowed" in reason.lower()

    @pytest.mark.asyncio
    async def test_get_sync_permissions_quarantine(self, trust_manager, sample_peer):
        """Test permissions for quarantined peer."""
        sample_peer.trust_score = 0.1

        perms = await trust_manager.get_sync_permissions(sample_peer)

        assert perms["tier"] == "QUARANTINE"
        assert perms["can_push"] is False
        assert perms["can_pull"] is False

    @pytest.mark.asyncio
    async def test_get_sync_permissions_limited(self, trust_manager, sample_peer):
        """Test permissions for limited peer."""
        sample_peer.trust_score = 0.3

        perms = await trust_manager.get_sync_permissions(sample_peer)

        assert perms["tier"] == "LIMITED"
        assert perms["can_push"] is False
        assert perms["can_pull"] is True
        assert perms["requires_review"] is True
        assert perms["max_capsules_per_sync"] == 50

    @pytest.mark.asyncio
    async def test_get_sync_permissions_standard(self, trust_manager, sample_peer):
        """Test permissions for standard peer."""
        sample_peer.trust_score = 0.5

        perms = await trust_manager.get_sync_permissions(sample_peer)

        assert perms["tier"] == "STANDARD"
        assert perms["can_push"] is True
        assert perms["can_pull"] is True
        assert perms["requires_review"] is False
        assert perms["max_capsules_per_sync"] == 200

    @pytest.mark.asyncio
    async def test_get_sync_permissions_trusted(self, trust_manager, sample_peer):
        """Test permissions for trusted peer."""
        sample_peer.trust_score = 0.7

        perms = await trust_manager.get_sync_permissions(sample_peer)

        assert perms["tier"] == "TRUSTED"
        assert perms["can_push"] is True
        assert perms["can_pull"] is True
        assert perms["rate_limit_multiplier"] == 2.0
        assert perms["max_capsules_per_sync"] == 500

    @pytest.mark.asyncio
    async def test_get_sync_permissions_core(self, trust_manager, sample_peer):
        """Test permissions for core peer."""
        sample_peer.trust_score = 0.9

        perms = await trust_manager.get_sync_permissions(sample_peer)

        assert perms["tier"] == "CORE"
        assert perms["can_push"] is True
        assert perms["can_pull"] is True
        assert perms["auto_accept"] is True
        assert perms["rate_limit_multiplier"] == 5.0
        assert perms["max_capsules_per_sync"] == 1000

    @pytest.mark.asyncio
    async def test_revoke_peer(self, trust_manager, sample_peer):
        """Test revoking peer trust."""
        await trust_manager.revoke_peer(
            sample_peer,
            reason="Malicious behavior",
            revoked_by="admin",
        )

        assert sample_peer.trust_score == 0.0
        assert sample_peer.status == PeerStatus.REVOKED
        assert "REVOKED" in sample_peer.description

    @pytest.mark.asyncio
    async def test_check_trust_expiration_never_verified(self, trust_manager, sample_peer):
        """Test trust expiration for never verified peer."""
        sample_peer.last_seen_at = None

        is_expired, reason = await trust_manager.check_trust_expiration(sample_peer)

        assert is_expired is True
        assert "never been verified" in reason

    @pytest.mark.asyncio
    async def test_check_trust_expiration_expired(self, trust_manager, sample_peer):
        """Test trust expiration for old verification."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(days=10)

        is_expired, reason = await trust_manager.check_trust_expiration(
            sample_peer, max_trust_age_days=7
        )

        assert is_expired is True
        assert "expired" in reason.lower()

    @pytest.mark.asyncio
    async def test_check_trust_expiration_valid(self, trust_manager, sample_peer):
        """Test trust expiration for recent verification."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(days=3)

        is_expired, reason = await trust_manager.check_trust_expiration(
            sample_peer, max_trust_age_days=7
        )

        assert is_expired is False
        assert "valid" in reason.lower()

    @pytest.mark.asyncio
    async def test_apply_trust_decay_if_expired(self, trust_manager, sample_peer):
        """Test trust decay for expired trust."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(days=10)
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.apply_trust_decay_if_expired(
            sample_peer, max_trust_age_days=7
        )

        assert new_trust < initial_trust
        assert new_trust == max(0.0, initial_trust - 0.1)

    @pytest.mark.asyncio
    async def test_apply_trust_decay_not_expired(self, trust_manager, sample_peer):
        """Test no decay for valid trust."""
        sample_peer.last_seen_at = datetime.now(UTC) - timedelta(days=3)
        initial_trust = sample_peer.trust_score

        new_trust = await trust_manager.apply_trust_decay_if_expired(
            sample_peer, max_trust_age_days=7
        )

        assert new_trust == initial_trust

    @pytest.mark.asyncio
    async def test_get_trust_history(self, trust_manager, sample_peer):
        """Test getting trust history."""
        # Generate some events
        await trust_manager.record_successful_sync(sample_peer)
        await trust_manager.record_successful_sync(sample_peer)
        await trust_manager.record_failed_sync(sample_peer)

        history = await trust_manager.get_trust_history(sample_peer.id)

        assert len(history) == 3
        assert history[-1].event_type == "sync_failure"

    @pytest.mark.asyncio
    async def test_get_trust_history_limit(self, trust_manager, sample_peer):
        """Test trust history limit."""
        for _ in range(20):
            await trust_manager.record_successful_sync(sample_peer)

        history = await trust_manager.get_trust_history(sample_peer.id, limit=5)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_calculate_network_trust_empty(self, trust_manager):
        """Test network trust for empty peer list."""
        metrics = await trust_manager.calculate_network_trust([])

        assert metrics["average_trust"] == 0.0
        assert metrics["healthy_peers"] == 0

    @pytest.mark.asyncio
    async def test_calculate_network_trust(self, trust_manager):
        """Test network trust calculation."""
        peers = [
            FederatedPeer(name="P1", url="https://p1.com", public_key="k1", trust_score=0.3),
            FederatedPeer(name="P2", url="https://p2.com", public_key="k2", trust_score=0.5),
            FederatedPeer(name="P3", url="https://p3.com", public_key="k3", trust_score=0.7),
            FederatedPeer(name="P4", url="https://p4.com", public_key="k4", trust_score=0.9),
        ]

        metrics = await trust_manager.calculate_network_trust(peers)

        assert metrics["average_trust"] == 0.6
        assert metrics["min_trust"] == 0.3
        assert metrics["max_trust"] == 0.9
        assert metrics["healthy_peers"] == 3  # STANDARD, TRUSTED, CORE
        assert metrics["at_risk_peers"] == 1  # LIMITED

    @pytest.mark.asyncio
    async def test_get_federation_stats(self, trust_manager):
        """Test getting federation stats."""
        peers = [
            FederatedPeer(
                name="P1", url="https://p1.com", public_key="k1", status=PeerStatus.ACTIVE
            ),
            FederatedPeer(
                name="P2", url="https://p2.com", public_key="k2", status=PeerStatus.ACTIVE
            ),
            FederatedPeer(
                name="P3", url="https://p3.com", public_key="k3", status=PeerStatus.PENDING
            ),
        ]

        stats = await trust_manager.get_federation_stats(peers)

        assert stats.total_peers == 3
        assert stats.active_peers == 2
        assert stats.pending_peers == 1

    @pytest.mark.asyncio
    async def test_recommend_trust_adjustment_failures(self, trust_manager, sample_peer):
        """Test recommendation for peer with many failures."""
        # Record multiple failures
        for _ in range(5):
            await trust_manager.record_failed_sync(sample_peer)

        recommendation = await trust_manager.recommend_trust_adjustment(sample_peer)

        assert recommendation is not None
        assert recommendation["recommendation"] == "decrease"
        assert recommendation["suggested_delta"] < 0

    @pytest.mark.asyncio
    async def test_recommend_trust_adjustment_successes(self, trust_manager, sample_peer):
        """Test recommendation for peer with many successes."""
        sample_peer.trust_score = 0.5  # STANDARD tier

        # Record many successes
        for _ in range(15):
            await trust_manager.record_successful_sync(sample_peer)

        recommendation = await trust_manager.recommend_trust_adjustment(sample_peer)

        assert recommendation is not None
        assert recommendation["recommendation"] == "increase"
        assert recommendation["suggested_delta"] > 0

    @pytest.mark.asyncio
    async def test_recommend_trust_adjustment_none(self, trust_manager, sample_peer):
        """Test no recommendation for normal activity."""
        # Mixed activity
        await trust_manager.record_successful_sync(sample_peer)
        await trust_manager.record_successful_sync(sample_peer)
        await trust_manager.record_failed_sync(sample_peer)

        recommendation = await trust_manager.recommend_trust_adjustment(sample_peer)

        assert recommendation is None

    @pytest.mark.asyncio
    async def test_concurrent_trust_updates(self, trust_manager, sample_peer):
        """Test concurrent trust updates are safe."""
        import asyncio

        initial_trust = sample_peer.trust_score

        # Run many concurrent updates
        tasks = []
        for _ in range(50):
            tasks.append(trust_manager.record_successful_sync(sample_peer))
            tasks.append(trust_manager.record_failed_sync(sample_peer))

        await asyncio.gather(*tasks)

        # Should not have any race conditions (trust should be valid)
        assert 0.0 <= sample_peer.trust_score <= 1.0

    @pytest.mark.asyncio
    async def test_peer_locks_eviction(self, trust_manager):
        """Test peer locks are evicted when limit reached."""
        trust_manager.MAX_PEER_LOCKS = 5

        # Create many peer locks
        for i in range(10):
            await trust_manager._get_peer_lock(f"peer-{i}")

        assert len(trust_manager._peer_locks) <= 5

    @pytest.mark.asyncio
    async def test_trust_cache_eviction(self, trust_manager, sample_peer):
        """Test trust cache is evicted when limit reached."""
        trust_manager.MAX_PEER_CACHE = 5

        # Initialize many peers
        for i in range(10):
            peer = FederatedPeer(
                id=f"peer-{i}",
                name=f"Peer {i}",
                url=f"https://peer{i}.com",
                public_key=f"key{i}",
            )
            await trust_manager.initialize_peer_trust(peer)

        assert len(trust_manager._peer_trust_cache) <= 5

    @pytest.mark.asyncio
    async def test_trust_history_bounded(self, trust_manager, sample_peer):
        """Test trust history is bounded."""
        original_max = trust_manager.MAX_HISTORY_EVENTS
        trust_manager._trust_history = trust_manager._trust_history.__class__(maxlen=10)

        # Generate many events
        for _ in range(20):
            await trust_manager.record_successful_sync(sample_peer)

        # Should be bounded
        assert len(trust_manager._trust_history) <= 10
