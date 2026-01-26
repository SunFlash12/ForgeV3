"""
Federation Trust Manager

Manages trust relationships between federated Forge instances.
Trust is earned through successful interactions and can be adjusted by governance.

SECURITY FIX (Audit 2): Added asyncio locks to prevent race conditions
in trust score updates.
SECURITY FIX (Audit 4 - M15): Added bounded collections to prevent memory exhaustion
from unbounded trust history growth.
"""

import asyncio
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any

from forge.federation.models import (
    FederatedPeer,
    FederationStats,
    PeerStatus,
)

logger = logging.getLogger(__name__)


class TrustEvent:
    """Records a trust-affecting event."""

    def __init__(
        self,
        peer_id: str,
        event_type: str,
        delta: float,
        reason: str,
        timestamp: datetime | None = None,
    ):
        self.peer_id = peer_id
        self.event_type = event_type
        self.delta = delta
        self.reason = reason
        self.timestamp = timestamp or datetime.now(UTC)


class PeerTrustManager:
    """
    Manages trust scoring for federated peers.

    Trust Model:
    - Initial trust: 0.3 (cautious)
    - Successful syncs increase trust
    - Failed syncs decrease trust
    - Ghost Council can manually adjust
    - Trust decay over inactivity

    Trust Thresholds:
    - 0.0-0.2: QUARANTINE - No sync allowed
    - 0.2-0.4: LIMITED - Pull only, manual review required
    - 0.4-0.6: STANDARD - Normal bidirectional sync
    - 0.6-0.8: TRUSTED - Priority sync, higher rate limits
    - 0.8-1.0: CORE - Full trust, auto-accept changes
    """

    # Trust adjustment amounts
    SYNC_SUCCESS_BONUS = 0.02
    SYNC_FAILURE_PENALTY = 0.05
    CONFLICT_PENALTY = 0.01
    MANUAL_REVIEW_ACCEPT = 0.03
    MANUAL_REVIEW_REJECT = 0.08
    INACTIVITY_DECAY_RATE = 0.01  # per week

    # Trust thresholds
    QUARANTINE_THRESHOLD = 0.2
    LIMITED_THRESHOLD = 0.4
    TRUSTED_THRESHOLD = 0.6
    CORE_THRESHOLD = 0.8

    # Initial trust for new peers
    INITIAL_TRUST = 0.3

    # SECURITY FIX (Audit 4 - M15): Memory limits to prevent unbounded growth
    MAX_HISTORY_EVENTS = 5000
    MAX_PEER_LOCKS = 10000
    MAX_PEER_CACHE = 10000

    def __init__(self) -> None:
        # SECURITY FIX (Audit 4 - M15): Use deque with maxlen for bounded history
        self._trust_history: deque[TrustEvent] = deque(maxlen=self.MAX_HISTORY_EVENTS)
        self._peer_trust_cache: dict[str, float] = {}
        # SECURITY FIX (Audit 2): Lock to prevent race conditions in trust updates
        self._trust_lock = asyncio.Lock()
        self._peer_locks: dict[
            str, asyncio.Lock
        ] = {}  # Per-peer locks for fine-grained concurrency

    async def _get_peer_lock(self, peer_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific peer."""
        # SECURITY FIX (Audit 2): Use global lock to protect peer_locks dict creation
        async with self._trust_lock:
            if peer_id not in self._peer_locks:
                # SECURITY FIX (Audit 4 - M15): Enforce limit on peer locks
                if len(self._peer_locks) >= self.MAX_PEER_LOCKS:
                    # Evict oldest locks using FIFO (insertion order).
                    # Note: True LRU would require tracking access times, but FIFO
                    # is acceptable for locks since active peers create new locks anyway.
                    evict_count = self.MAX_PEER_LOCKS // 10
                    keys_to_evict = list(self._peer_locks.keys())[:evict_count]
                    for key in keys_to_evict:
                        del self._peer_locks[key]
                    logger.warning(
                        "peer_locks_eviction: evicted_count=%s, remaining=%s",
                        evict_count,
                        len(self._peer_locks),
                    )
                self._peer_locks[peer_id] = asyncio.Lock()
            return self._peer_locks[peer_id]

    def _update_trust_cache(self, peer_id: str, trust_score: float) -> None:
        """
        Update trust cache with limit enforcement.

        SECURITY FIX (Audit 4 - M15): Enforce limit on peer trust cache.
        """
        if peer_id not in self._peer_trust_cache:
            if len(self._peer_trust_cache) >= self.MAX_PEER_CACHE:
                # Evict oldest entries (first 10%)
                evict_count = self.MAX_PEER_CACHE // 10
                keys_to_evict = list(self._peer_trust_cache.keys())[:evict_count]
                for key in keys_to_evict:
                    del self._peer_trust_cache[key]
                logger.warning(
                    "peer_cache_eviction: evicted_count=%s, remaining=%s",
                    evict_count,
                    len(self._peer_trust_cache),
                )
        self._peer_trust_cache[peer_id] = trust_score

    async def initialize_peer_trust(self, peer: FederatedPeer) -> None:
        """Set initial trust for a new peer."""
        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            # Only set initial trust if peer hasn't been initialized yet (not in cache)
            if peer.id not in self._peer_trust_cache:
                if peer.trust_score == 0:
                    peer.trust_score = self.INITIAL_TRUST

            # SECURITY FIX (Audit 4 - M15): Use bounded cache update
            self._update_trust_cache(peer.id, peer.trust_score)
            self._record_event(
                peer.id,
                "initialized",
                0,
                f"Peer registered with initial trust {peer.trust_score:.2f}",
            )
            logger.info(f"Initialized trust for {peer.name}: {peer.trust_score:.2f}")

    async def record_successful_sync(self, peer: FederatedPeer) -> float:
        """Record a successful sync and increase trust."""
        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            old_trust = peer.trust_score
            new_trust = min(1.0, old_trust + self.SYNC_SUCCESS_BONUS)

            peer.trust_score = new_trust
            self._update_trust_cache(peer.id, new_trust)

            self._record_event(
                peer.id,
                "sync_success",
                self.SYNC_SUCCESS_BONUS,
                f"Successful sync increased trust from {old_trust:.2f} to {new_trust:.2f}",
            )

            logger.debug(f"Trust increased for {peer.name}: {old_trust:.2f} -> {new_trust:.2f}")
            return new_trust

    async def record_failed_sync(self, peer: FederatedPeer) -> float:
        """Record a failed sync and decrease trust."""
        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            old_trust = peer.trust_score
            new_trust = max(0.0, old_trust - self.SYNC_FAILURE_PENALTY)

            peer.trust_score = new_trust
            self._update_trust_cache(peer.id, new_trust)

            self._record_event(
                peer.id,
                "sync_failure",
                -self.SYNC_FAILURE_PENALTY,
                f"Failed sync decreased trust from {old_trust:.2f} to {new_trust:.2f}",
            )

            logger.warning(f"Trust decreased for {peer.name}: {old_trust:.2f} -> {new_trust:.2f}")

            # Check if we need to change status
            if new_trust < self.QUARANTINE_THRESHOLD:
                peer.status = PeerStatus.SUSPENDED
                logger.warning(f"Peer {peer.name} suspended due to low trust")

            return new_trust

    async def record_conflict(
        self,
        peer: FederatedPeer,
        conflict_type: str,
        resolved: bool,
    ) -> float:
        """Record a sync conflict."""
        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            penalty = self.CONFLICT_PENALTY if not resolved else 0

            old_trust = peer.trust_score
            new_trust = max(0.0, old_trust - penalty)

            peer.trust_score = new_trust
            self._update_trust_cache(peer.id, new_trust)

            self._record_event(
                peer.id, "conflict", -penalty, f"Conflict ({conflict_type}), resolved={resolved}"
            )

            return new_trust

    async def manual_adjustment(
        self,
        peer: FederatedPeer,
        delta: float,
        reason: str,
        adjusted_by: str,
    ) -> float:
        """Manual trust adjustment by governance."""
        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            old_trust = peer.trust_score
            new_trust = max(0.0, min(1.0, old_trust + delta))

            peer.trust_score = new_trust
            self._update_trust_cache(peer.id, new_trust)

            self._record_event(
                peer.id, "manual_adjustment", delta, f"Manual adjustment by {adjusted_by}: {reason}"
            )

            logger.info(
                f"Manual trust adjustment for {peer.name} by {adjusted_by}: "
                f"{old_trust:.2f} -> {new_trust:.2f} ({reason})"
            )

            # Update status based on new trust
            await self._update_peer_status(peer)

            return new_trust

    async def apply_inactivity_decay(self, peer: FederatedPeer) -> float:
        """Apply trust decay for inactive peers."""
        if not peer.last_seen_at:
            return peer.trust_score

        # Calculate weeks since last seen
        now = datetime.now(UTC)
        inactive_duration = now - peer.last_seen_at
        inactive_weeks = inactive_duration.days / 7

        if inactive_weeks < 1:
            return peer.trust_score

        # SECURITY FIX (Audit 2): Use per-peer lock to prevent race conditions
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            # Apply decay
            decay = self.INACTIVITY_DECAY_RATE * inactive_weeks
            old_trust = peer.trust_score
            new_trust = max(self.INITIAL_TRUST, old_trust - decay)  # Don't decay below initial

            if new_trust != old_trust:
                peer.trust_score = new_trust
                self._update_trust_cache(peer.id, new_trust)

                self._record_event(
                    peer.id, "inactivity_decay", -decay, f"Inactive for {inactive_weeks:.1f} weeks"
                )

                logger.info(f"Trust decay for {peer.name}: {old_trust:.2f} -> {new_trust:.2f}")

            return new_trust

    async def get_trust_tier(self, peer: FederatedPeer) -> str:
        """Get the trust tier for a peer."""
        trust = peer.trust_score

        if trust >= self.CORE_THRESHOLD:
            return "CORE"
        elif trust >= self.TRUSTED_THRESHOLD:
            return "TRUSTED"
        elif trust >= self.LIMITED_THRESHOLD:
            return "STANDARD"
        elif trust >= self.QUARANTINE_THRESHOLD:
            return "LIMITED"
        else:
            return "QUARANTINE"

    async def can_sync(self, peer: FederatedPeer) -> tuple[bool, str]:
        """Check if sync is allowed with a peer."""
        tier = await self.get_trust_tier(peer)

        if tier == "QUARANTINE":
            return False, "Peer is quarantined due to low trust"

        if peer.status == PeerStatus.SUSPENDED:
            return False, "Peer is suspended"

        if peer.status == PeerStatus.REVOKED:
            return False, "Peer trust has been revoked"

        if peer.status == PeerStatus.OFFLINE:
            return False, "Peer is offline"

        return True, f"Sync allowed (tier: {tier})"

    async def get_sync_permissions(self, peer: FederatedPeer) -> dict[str, Any]:
        """Get sync permissions based on trust tier."""
        tier = await self.get_trust_tier(peer)

        permissions = {
            "tier": tier,
            "can_push": False,
            "can_pull": False,
            "auto_accept": False,
            "requires_review": True,
            "rate_limit_multiplier": 1.0,
            "max_capsules_per_sync": 100,
        }

        if tier == "QUARANTINE":
            # No sync allowed
            pass

        elif tier == "LIMITED":
            permissions["can_pull"] = True
            permissions["requires_review"] = True
            permissions["max_capsules_per_sync"] = 50

        elif tier == "STANDARD":
            permissions["can_push"] = True
            permissions["can_pull"] = True
            permissions["requires_review"] = False
            permissions["max_capsules_per_sync"] = 200

        elif tier == "TRUSTED":
            permissions["can_push"] = True
            permissions["can_pull"] = True
            permissions["requires_review"] = False
            permissions["rate_limit_multiplier"] = 2.0
            permissions["max_capsules_per_sync"] = 500

        elif tier == "CORE":
            permissions["can_push"] = True
            permissions["can_pull"] = True
            permissions["auto_accept"] = True
            permissions["requires_review"] = False
            permissions["rate_limit_multiplier"] = 5.0
            permissions["max_capsules_per_sync"] = 1000

        return permissions

    async def _update_peer_status(self, peer: FederatedPeer) -> None:
        """Update peer status based on trust score."""
        tier = await self.get_trust_tier(peer)

        if tier == "QUARANTINE":
            if peer.status not in (PeerStatus.SUSPENDED, PeerStatus.REVOKED):
                peer.status = PeerStatus.SUSPENDED
                logger.warning(f"Peer {peer.name} auto-suspended due to low trust")

        elif peer.status == PeerStatus.SUSPENDED:
            # Check if we can restore
            if tier in ("STANDARD", "TRUSTED", "CORE"):
                peer.status = PeerStatus.ACTIVE
                logger.info(f"Peer {peer.name} restored to active status")
            elif tier == "LIMITED":
                peer.status = PeerStatus.DEGRADED

    async def revoke_peer(
        self,
        peer: FederatedPeer,
        reason: str,
        revoked_by: str,
    ) -> None:
        """
        Revoke trust for a peer.

        SECURITY FIX (Audit 3): Implement trust revocation per 3.6.

        Args:
            peer: Peer to revoke
            reason: Reason for revocation
            revoked_by: ID of the user/system revoking trust
        """
        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            old_trust = peer.trust_score

            # Set trust to 0 and mark as revoked
            peer.trust_score = 0.0
            peer.status = PeerStatus.REVOKED
            self._update_trust_cache(peer.id, 0.0)

            # Store revocation metadata in description field
            revoked_at = datetime.now(UTC).isoformat()
            peer.description = f"REVOKED at {revoked_at} by {revoked_by}: {reason}"

            self._record_event(
                peer.id, "trust_revoked", -old_trust, f"Trust revoked by {revoked_by}: {reason}"
            )

            logger.warning(f"Trust revoked for {peer.name} by {revoked_by}: {reason}")

    async def check_trust_expiration(
        self,
        peer: FederatedPeer,
        max_trust_age_days: int = 7,
    ) -> tuple[bool, str]:
        """
        Check if peer trust has expired and needs re-verification.

        SECURITY FIX (Audit 3): Implement trust expiration per 3.7.

        Args:
            peer: Peer to check
            max_trust_age_days: Days before trust requires re-verification

        Returns:
            (is_expired, reason)
        """
        # Check if peer has verification timestamp
        last_verified = getattr(peer, "last_verified_at", None)
        if not last_verified:
            # Use last_seen_at as fallback
            last_verified = peer.last_seen_at

        if not last_verified:
            return True, "Peer has never been verified"

        # Calculate time since last verification
        now = datetime.now(UTC)
        if isinstance(last_verified, str):
            last_verified = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))

        age = now - last_verified
        if age.days >= max_trust_age_days:
            return True, f"Trust expired ({age.days} days since verification)"

        return False, f"Trust valid ({age.days} days old)"

    async def apply_trust_decay_if_expired(
        self,
        peer: FederatedPeer,
        max_trust_age_days: int = 7,
    ) -> float:
        """
        Apply trust decay for peers with expired trust.

        SECURITY FIX (Audit 3): Automatic trust decay for unverified peers.

        Args:
            peer: Peer to check
            max_trust_age_days: Days before trust decay applies

        Returns:
            New trust score
        """
        is_expired, reason = await self.check_trust_expiration(peer, max_trust_age_days)

        if not is_expired:
            return peer.trust_score

        peer_lock = await self._get_peer_lock(peer.id)
        async with peer_lock:
            old_trust = peer.trust_score

            # Apply significant decay for expired trust
            decay = 0.1  # 10% decay for expired trust
            new_trust = max(0.0, old_trust - decay)

            peer.trust_score = new_trust
            self._update_trust_cache(peer.id, new_trust)

            self._record_event(peer.id, "trust_expired_decay", -decay, reason)

            logger.warning(
                f"Trust expired for {peer.name}: {old_trust:.2f} -> {new_trust:.2f} ({reason})"
            )

            # Update status based on new trust
            await self._update_peer_status(peer)

            return new_trust

    def _record_event(
        self,
        peer_id: str,
        event_type: str,
        delta: float,
        reason: str,
    ) -> None:
        """Record a trust event."""
        event = TrustEvent(
            peer_id=peer_id,
            event_type=event_type,
            delta=delta,
            reason=reason,
        )
        # SECURITY FIX (Audit 4 - M15): deque with maxlen auto-evicts oldest events
        self._trust_history.append(event)

    async def get_trust_history(
        self,
        peer_id: str | None = None,
        limit: int = 100,
    ) -> list[TrustEvent]:
        """Get trust event history."""
        events_list: list[TrustEvent] = list(self._trust_history)
        if peer_id:
            events_list = [e for e in events_list if e.peer_id == peer_id]
        return events_list[-limit:]

    async def calculate_network_trust(
        self,
        peers: list[FederatedPeer],
    ) -> dict[str, Any]:
        """Calculate aggregate network trust metrics."""
        if not peers:
            return {
                "average_trust": 0.0,
                "min_trust": 0.0,
                "max_trust": 0.0,
                "tier_distribution": {},
                "healthy_peers": 0,
                "at_risk_peers": 0,
            }

        trust_scores = [p.trust_score for p in peers]
        tiers: dict[str, int] = {}
        healthy = 0
        at_risk = 0

        for peer in peers:
            tier = await self.get_trust_tier(peer)
            tiers[tier] = tiers.get(tier, 0) + 1

            if tier in ("STANDARD", "TRUSTED", "CORE"):
                healthy += 1
            elif tier in ("LIMITED", "QUARANTINE"):
                at_risk += 1

        return {
            "average_trust": sum(trust_scores) / len(trust_scores),
            "min_trust": min(trust_scores),
            "max_trust": max(trust_scores),
            "tier_distribution": tiers,
            "healthy_peers": healthy,
            "at_risk_peers": at_risk,
        }

    async def get_federation_stats(
        self,
        peers: list[FederatedPeer],
    ) -> FederationStats:
        """Get overall federation statistics."""
        active = sum(1 for p in peers if p.status == PeerStatus.ACTIVE)
        pending = sum(1 for p in peers if p.status == PeerStatus.PENDING)

        # Count federated capsules (would query from sync service)
        total_federated = 0
        synced = 0
        pending_capsules = 0
        conflicted = 0

        return FederationStats(
            total_peers=len(peers),
            active_peers=active,
            pending_peers=pending,
            total_federated_capsules=total_federated,
            synced_capsules=synced,
            pending_capsules=pending_capsules,
            conflicted_capsules=conflicted,
        )

    async def recommend_trust_adjustment(
        self,
        peer: FederatedPeer,
    ) -> dict[str, Any] | None:
        """
        Analyze peer and recommend trust adjustment if needed.
        Returns recommendation for Ghost Council review.
        """
        # Get recent history
        history = await self.get_trust_history(peer.id, limit=20)

        recent_failures = sum(
            1
            for e in history
            if e.event_type == "sync_failure" and (datetime.now(UTC) - e.timestamp).days < 7
        )

        recent_successes = sum(
            1
            for e in history
            if e.event_type == "sync_success" and (datetime.now(UTC) - e.timestamp).days < 7
        )

        # Check for concerning patterns
        if recent_failures >= 3 and recent_successes == 0:
            return {
                "peer_id": peer.id,
                "peer_name": peer.name,
                "current_trust": peer.trust_score,
                "recommendation": "decrease",
                "suggested_delta": -0.1,
                "reason": f"Multiple consecutive failures ({recent_failures} in last 7 days)",
                "evidence": {
                    "recent_failures": recent_failures,
                    "recent_successes": recent_successes,
                },
            }

        # Check for exceptional performance
        if recent_successes >= 10 and recent_failures == 0:
            current_tier = await self.get_trust_tier(peer)
            if current_tier not in ("TRUSTED", "CORE"):
                return {
                    "peer_id": peer.id,
                    "peer_name": peer.name,
                    "current_trust": peer.trust_score,
                    "recommendation": "increase",
                    "suggested_delta": 0.1,
                    "reason": f"Consistent reliability ({recent_successes} successes in last 7 days)",
                    "evidence": {
                        "recent_failures": recent_failures,
                        "recent_successes": recent_successes,
                    },
                }

        return None
