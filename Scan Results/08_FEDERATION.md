# Forge V3 - FEDERATION Analysis

## Category: FEDERATION
## Status: Complete
## Last Updated: 2026-01-10

---

## Executive Summary

The Federation module enables distributed knowledge sharing across multiple Forge instances. It implements a sophisticated peer-to-peer protocol with cryptographic authentication, trust-based access control, and bidirectional synchronization of capsules and semantic edges. The module has undergone multiple security audits with fixes applied for SSRF, DNS rebinding, replay attacks, and certificate pinning.

---

## Files Analyzed

### 1. `forge-cascade-v2/forge/federation/__init__.py`

**Purpose:** Module entry point and public API exports for the Federation subsystem.

**Key Exports:**
- **Models:** `FederatedPeer`, `FederatedCapsule`, `FederatedEdge`, `SyncState`, `SyncDirection`, `PeerStatus`, `ConflictResolution`, `PeerHandshake`, `SyncPayload`, `FederationStats`
- **Services:** `FederationProtocol`, `SyncService`, `PeerTrustManager`

**Architecture Overview:**
```
FederationProtocol - Cryptographic handshake and secure messaging
SyncService - Orchestrates sync operations between peers
PeerTrustManager - Manages trust scoring and permissions
```

---

### 2. `forge-cascade-v2/forge/federation/models.py`

**Purpose:** Data structures for federated knowledge sharing.

**Key Models:**

| Model | Description |
|-------|-------------|
| `PeerStatus` | Enum: PENDING, ACTIVE, DEGRADED, SUSPENDED, OFFLINE, REVOKED |
| `SyncDirection` | Enum: PUSH, PULL, BIDIRECTIONAL |
| `ConflictResolution` | Enum: HIGHER_TRUST, NEWER_TIMESTAMP, MANUAL_REVIEW, MERGE, LOCAL_WINS, REMOTE_WINS |
| `FederatedPeer` | Remote Forge instance with trust scoring, sync config, and stats |
| `FederatedCapsule` | Tracks capsules from remote peers with local/remote mappings |
| `FederatedEdge` | Tracks semantic edges spanning federated capsules |
| `SyncState` | Tracks sync operation progress with checkpoints for resumable syncs |
| `PeerHandshake` | Cryptographic handshake data with nonce for replay prevention |
| `SyncPayload` | Signed payload with capsules, edges, deletions, and integrity hash |

**Trust Scale Design:**
- Peer trust: 0.0-1.0 floating point scale (granular scoring)
- Capsule TrustLevel: 0-100 integer scale (different system)
- `trust_score_as_int` property converts between scales

**Security Features (Audit 2):**
- Nonce field in `PeerHandshake` for replay prevention
- Nonce field in `SyncPayload` for replay prevention

---

### 3. `forge-cascade-v2/forge/federation/protocol.py`

**Purpose:** Core federation protocol handling peer discovery, handshake, and secure communication.

**Key Components:**

| Class | Purpose |
|-------|---------|
| `SSRFError` | Raised for SSRF attack detection |
| `DNSRebindingError` | Raised for DNS rebinding attack detection |
| `CertificatePinningError` | Raised for TLS certificate mismatch |
| `PinnedConnection` | DNS pinning data with TTL (5 min default) |
| `PinnedCertificate` | TLS cert fingerprint with TOFU/explicit pinning |
| `DNSPinStore` | Thread-safe DNS pin storage (max 10,000 entries) |
| `CertificatePinStore` | Persistent TLS cert pin storage |
| `NonceStore` | Thread-safe nonce tracking for replay prevention |
| `FederationProtocol` | Main protocol implementation |

**Protocol Features:**

1. **Cryptographic Identity:**
   - Ed25519 key pairs for signing
   - Keys persisted to disk with optional encryption
   - Base64-encoded public keys for exchange

2. **Handshake Process:**
   ```
   1. Generate nonce + timestamp
   2. Create signed handshake with instance info
   3. Send to peer's /api/v1/federation/handshake
   4. Verify peer's handshake signature
   5. Pin TLS certificate (TOFU)
   6. Exchange public keys
   ```

3. **Message Signing:**
   - All sync payloads cryptographically signed
   - SHA-256 content hashing for integrity

**Security Fixes Applied:**

| Audit | Fix | Description |
|-------|-----|-------------|
| Audit 2 | SSRF Protection | Private IP blocking, redirect disabled |
| Audit 4 - H3 | DNS Pinning | Prevents DNS rebinding attacks |
| Audit 4 - H4 | TLS Cert Pinning | SHA-256 fingerprint with TOFU |
| Audit 4 - H5 | Nonce Enforcement | Mandatory nonces (no backward compat) |
| Audit 4 - H8 | Key Encryption | Private keys encrypted at rest |
| Audit 4 - H29 | Sync Request Nonce | Nonces in sync requests |
| Audit 4 - M6 | File Permissions | Cross-platform restrictive permissions |

**URL Validation (`validate_url_for_ssrf`):**
- Requires HTTPS in production
- Blocks dangerous hostnames (localhost, metadata endpoints)
- Validates resolved IP addresses (no private/loopback/link-local)
- DNS pinning with rebinding detection
- Returns `ValidatedURL` with pinned IPs

---

### 4. `forge-cascade-v2/forge/federation/sync.py`

**Purpose:** Orchestrates capsule and edge synchronization between federated peers.

**Key Components:**

| Class | Purpose |
|-------|---------|
| `SyncConflict` | Represents a conflict requiring resolution |
| `SyncService` | Main synchronization service |

**Sync Service Features:**

1. **Peer Management:**
   - Register/unregister peers with database persistence
   - Lookup by ID or public key
   - List all registered peers

2. **Sync Operations:**
   - Pull: Fetch changes from peer (with pagination limit)
   - Push: Send local changes to peer
   - Bidirectional: Both pull and push

3. **Sync Phases:**
   ```
   INIT -> FETCHING -> PROCESSING -> APPLYING -> FINALIZING
   ```

4. **Conflict Resolution Strategies:**
   - `LOCAL_WINS`: Always keep local version
   - `REMOTE_WINS`: Always accept remote version
   - `HIGHER_TRUST`: Higher trust level wins
   - `NEWER_TIMESTAMP`: More recent modification wins
   - `MERGE`: Combine unique fields (tags union, newer content)
   - `MANUAL_REVIEW`: Flag for human review

**Security Fixes Applied:**

| Audit | Fix | Description |
|-------|-----|-------------|
| Audit 3 | Peer Persistence | Store peers in Neo4j database |
| Audit 4 - H6 | Iteration Limit | MAX_SYNC_ITERATIONS = 100 to prevent DoS |
| Audit 4 - H7 | Content Hash Verify | Verify content_hash against actual content |
| Audit 4 - H9 | Trust Rejection | Never accept remote trust_level values |

**Critical Security Design:**
```python
# Remote trust levels are NEVER accepted
# Capsules from federation always get trust_level = 20 (UNVERIFIED)
# Trust must be calculated locally
```

**Database Operations:**
- Creates capsules with `federated: true` marker
- Tracks source_peer_id and source_capsule_id
- Uses MERGE for edges to prevent duplicates
- Filters out federated capsules from push (prevents echo)

---

### 5. `forge-cascade-v2/forge/federation/trust.py`

**Purpose:** Manages trust relationships between federated Forge instances.

**Trust Model:**

| Trust Range | Tier | Permissions |
|-------------|------|-------------|
| 0.0-0.2 | QUARANTINE | No sync allowed |
| 0.2-0.4 | LIMITED | Pull only, manual review required |
| 0.4-0.6 | STANDARD | Bidirectional sync |
| 0.6-0.8 | TRUSTED | Priority sync, 2x rate limit |
| 0.8-1.0 | CORE | Full trust, auto-accept, 5x rate limit |

**Trust Adjustment Values:**

| Event | Delta |
|-------|-------|
| Successful sync | +0.02 |
| Failed sync | -0.05 |
| Conflict penalty | -0.01 |
| Manual accept | +0.03 |
| Manual reject | -0.08 |
| Inactivity decay | -0.01/week |

**Key Features:**

1. **TrustEvent Tracking:** Records all trust-affecting events with timestamps
2. **Per-Peer Locking:** Fine-grained asyncio locks prevent race conditions
3. **Bounded Collections:** Prevents memory exhaustion (max 5000 history events)
4. **Inactivity Decay:** Trust decays if peer inactive for >1 week
5. **Trust Expiration:** Peers need re-verification after 7 days

**Security Fixes Applied:**

| Audit | Fix | Description |
|-------|-----|-------------|
| Audit 2 | Asyncio Locks | Prevents race conditions in trust updates |
| Audit 3 | Trust Revocation | Implements revoke_peer() with metadata |
| Audit 3 | Trust Expiration | check_trust_expiration() with decay |
| Audit 4 - M15 | Bounded Collections | deque with maxlen, cache limits |

**Governance Integration:**
- `manual_adjustment()`: Allows Ghost Council to adjust trust
- `recommend_trust_adjustment()`: Suggests adjustments for review
- `revoke_peer()`: Complete trust revocation with audit trail

---

## Protocol Flow Diagram

```
Instance A                              Instance B
    |                                       |
    |-- 1. Create handshake (sign) -------->|
    |<-- 2. Return handshake (sign) --------|
    |   [Verify signature, pin cert]        |
    |                                       |
    |-- 3. Register peer --------------->   |
    |   [Store in DB, init trust]           |
    |                                       |
    |-- 4. Sync request (pull) ------------>|
    |   [Signed with nonce]                 |
    |<-- 5. SyncPayload (signed) -----------|
    |   [Verify sig, hash, nonce]           |
    |   [Apply changes, resolve conflicts]  |
    |                                       |
    |-- 6. SyncPayload (push) ------------->|
    |   [Signed with nonce]                 |
    |   [Update trust scores]               |
```

---

## Sync Mechanism Details

### Pull Sync Flow:
1. Calculate sync window (since last_sync_at)
2. Send signed request with nonce to peer
3. Receive paginated SyncPayload
4. Verify content hash matches actual content
5. Process capsules:
   - Check trust threshold
   - Detect conflicts (both modified since last sync)
   - Apply conflict resolution strategy
   - Create/update local copies
6. Process edges:
   - Resolve remote IDs to local IDs
   - Create federated edges in Neo4j
7. Handle deletions (flag for review, don't auto-delete)
8. Update peer stats and trust

### Push Sync Flow:
1. Query local capsules modified since last sync
2. Filter by min_trust and capsule types
3. Exclude federated capsules (prevent echo)
4. Get related edge changes
5. Create signed SyncPayload with content hash
6. Send to peer

---

## Trust Establishment Flow

```
1. New peer registration -> trust = 0.3 (INITIAL_TRUST)
2. Each successful sync -> trust += 0.02
3. Each failed sync -> trust -= 0.05
4. Inactivity (>1 week) -> trust -= 0.01/week
5. Trust expiration (>7 days) -> 10% decay
6. Manual adjustment by Ghost Council
7. Revocation sets trust = 0.0, status = REVOKED
```

---

## Issues Found

| Severity | File | Issue | Suggested Fix |
|----------|------|-------|---------------|
| LOW | sync.py:913 | Uses `peer.metadata` which may not exist on FederatedPeer model | Add `metadata: dict[str, Any] = Field(default_factory=dict)` to FederatedPeer |
| LOW | sync.py:944-955 | `load_peers_from_db()` uses `endpoint` but model has `url` field | Ensure database schema matches model field names |
| LOW | protocol.py:761 | Default key path differs between Docker and local dev | Consider consolidating path logic into config |
| MEDIUM | sync.py:691-692 | Dynamic Cypher query construction with relationship_type | Validate relationship_type against whitelist to prevent injection |
| LOW | trust.py:105-108 | FIFO eviction for peer_locks is not true LRU | Consider using OrderedDict for LRU semantics if needed |
| INFO | models.py:94-99 | Trust score scale mismatch (0-1 vs 0-100) could cause confusion | Document prominently or unify scales |
| LOW | sync.py:552 | Peer metadata access in history lookup | Ensure deque indexing handles edge cases |

---

## Improvements Identified

| Priority | File | Improvement | Benefit |
|----------|------|-------------|---------|
| MEDIUM | protocol.py | Add connection pooling for federation HTTP client | Reduce connection overhead for frequent syncs |
| MEDIUM | sync.py | Implement cursor-based pagination for large syncs | Handle peers with large capsule counts |
| HIGH | sync.py | Add sync rate limiting per peer | Prevent resource exhaustion from aggressive peers |
| MEDIUM | trust.py | Add trust score persistence to database | Trust survives restarts without relying on sync |
| LOW | protocol.py | Add cert rotation announcement protocol | Allow planned certificate changes without pinning failures |
| MEDIUM | sync.py | Implement vector clock for conflict detection | More accurate conflict detection than timestamp |
| HIGH | trust.py | Add distributed trust consensus | Peers can share trust observations about other peers |
| LOW | models.py | Add sync batch tracking | Track individual batches for partial retry |
| MEDIUM | protocol.py | Add mutual TLS support | Stronger authentication than TOFU |
| LOW | sync.py | Add sync priority queue | Prioritize syncs with high-trust or stale peers |

---

## Possibilities - Advanced Federation Features

### 1. Multi-Hop Federation
Allow capsules to traverse through intermediate peers:
- Peer A syncs with Peer B
- Peer B syncs with Peer C
- Peer A indirectly receives capsules from Peer C
- Requires transitive trust calculation

### 2. Selective Sync Subscriptions
Peers subscribe to specific topics/tags:
- Subscribe to capsules with specific tags
- Subscribe to capsules matching semantic queries
- Reduces unnecessary sync traffic

### 3. Real-time Sync with WebSockets
Replace polling with push notifications:
- Immediate propagation of new capsules
- Bidirectional event streaming
- Reduced latency for time-sensitive content

### 4. Byzantine Fault Tolerance
Handle malicious peers in the network:
- Require N-of-M peer confirmation for high-trust capsules
- Detect and isolate peers spreading inconsistent data
- Merkle tree verification across peer network

### 5. Federated Search
Query across federated peers:
- Broadcast semantic queries to trusted peers
- Aggregate and rank results
- Privacy-preserving query protocols

### 6. Peer Reputation Network
Distributed reputation system:
- Peers vouch for other peers
- Web of trust model
- Sybil attack resistance

### 7. Differential Sync
Optimize bandwidth with deltas:
- Send only changed fields instead of full capsules
- CRDT-based merging for conflict-free updates
- Compressed binary protocol

### 8. Federated Ghost Council
Cross-instance governance:
- Propose governance actions to peer councils
- Vote on federation-wide policies
- Shared blocklists for malicious content

---

## Security Architecture Summary

### Defense in Depth Layers:

1. **Transport Security:**
   - HTTPS required in production
   - TLS certificate pinning (TOFU/explicit)
   - DNS pinning against rebinding

2. **Authentication:**
   - Ed25519 cryptographic signatures
   - All messages signed
   - Public key exchange during handshake

3. **Replay Prevention:**
   - Nonces required on all messages
   - Timestamp freshness checks (5 min window)
   - Nonce store with TTL expiration

4. **Access Control:**
   - Trust-based permissions
   - Tiered sync capabilities
   - Quarantine for untrusted peers

5. **Data Integrity:**
   - SHA-256 content hashes
   - Hash verification before processing
   - Signed payloads

6. **Trust Isolation:**
   - Remote trust_level never accepted
   - Local trust calculation only
   - Federated capsules start at UNVERIFIED

### Attack Mitigations:

| Attack Vector | Mitigation |
|---------------|------------|
| SSRF | URL validation, private IP blocking |
| DNS Rebinding | DNS pinning with TTL |
| Man-in-the-Middle | TLS cert pinning |
| Replay Attack | Mandatory nonces, timestamp checking |
| Trust Escalation | Local-only trust calculation |
| DoS via Pagination | MAX_SYNC_ITERATIONS limit |
| Memory Exhaustion | Bounded collections, cache eviction |
| Key Theft | Encrypted private keys, restrictive permissions |

---

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `FEDERATION_KEY_PATH` | `/app/data/federation_keys` | Key storage path |
| `FEDERATION_KEY_PASSPHRASE` | (none) | Passphrase for key encryption |
| Handshake Timeout | 30 seconds | Timeout for handshake operations |
| Request Timeout | 60 seconds | Timeout for sync requests |
| DNS Pin TTL | 300 seconds | DNS pinning expiration |
| Nonce TTL | 3600 seconds | Nonce expiration |
| Max Nonces | 100,000 | Maximum stored nonces |
| Max DNS Pins | 10,000 | Maximum DNS pins |
| Max Sync Iterations | 100 | Pagination limit per sync |
| Sync Interval Min | 5 minutes | Minimum sync interval |
| Max History Events | 5,000 | Trust history limit |

---

## Conclusion

The Federation module implements a robust peer-to-peer protocol for distributed knowledge sharing. Key strengths include:

1. **Strong Security Posture:** Multiple audit rounds have hardened against SSRF, DNS rebinding, replay attacks, and MitM attacks
2. **Flexible Trust Model:** Granular trust tiers with automatic adjustment based on behavior
3. **Conflict Resolution:** Multiple strategies for handling sync conflicts
4. **Persistence:** Peers and trust state survive restarts via Neo4j storage
5. **Memory Safety:** Bounded collections prevent resource exhaustion

Areas for enhancement:
1. Rate limiting for aggressive peers
2. Cursor-based pagination for large syncs
3. Real-time sync via WebSockets
4. Distributed trust consensus
