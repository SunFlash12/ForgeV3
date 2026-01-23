# Repository Layer Analysis - Forge Cascade V2

**Category:** Data Access Layer (Repositories)
**Status:** Complete
**Analysis Date:** 2026-01-10
**Total Files Analyzed:** 10
**Location:** `forge-cascade-v2/forge/repositories/`

---

## Table of Contents
1. [Overview](#overview)
2. [Base Repository](#base-repository)
3. [Audit Repository](#audit-repository)
4. [Capsule Repository](#capsule-repository)
5. [Cascade Repository](#cascade-repository)
6. [Governance Repository](#governance-repository)
7. [Graph Repository](#graph-repository)
8. [Overlay Repository](#overlay-repository)
9. [Temporal Repository](#temporal-repository)
10. [User Repository](#user-repository)
11. [Cross-Cutting Concerns](#cross-cutting-concerns)
12. [Index Recommendations](#index-recommendations)
13. [Issues Found](#issues-found)
14. [Improvements Identified](#improvements-identified)

---

## Overview

The repository layer provides a clean data access abstraction over Neo4j, implementing the Repository Pattern with domain-specific extensions. All repositories use async operations and follow consistent patterns established by `BaseRepository`.

### Architecture Highlights
- **Database:** Neo4j graph database with Cypher queries
- **Pattern:** Generic Repository with abstract base class
- **Async:** All operations are async/await
- **Security:** Multiple security fixes applied (Audit 3 & 4)
- **Models:** Pydantic models for type safety

### Exported Repositories
```python
__all__ = [
    "BaseRepository",
    "CapsuleRepository",
    "CascadeRepository",
    "get_cascade_repository",
    "UserRepository",
    "OverlayRepository",
    "GovernanceRepository",
    "AuditRepository",
    "GraphRepository",
    "TemporalRepository",
]
```

---

## Base Repository

**File:** `base.py`
**Lines:** 353
**Purpose:** Abstract base class providing common CRUD operations and query patterns

### Pattern Implementation
```python
class BaseRepository(ABC, Generic[T, CreateT, UpdateT]):
    """Generic repository with type parameters for Model, CreateSchema, UpdateSchema"""
```

### Abstract Properties
| Property | Description |
|----------|-------------|
| `node_label` | Neo4j node label for this entity |
| `model_class` | Pydantic model class for deserialization |

### Core CRUD Operations

| Method | Query Type | Description |
|--------|------------|-------------|
| `get_by_id(entity_id)` | READ | Get entity by ID |
| `get_all(skip, limit, order_by, order_dir)` | READ | Paginated list with ordering |
| `count()` | READ | Total entity count |
| `exists(entity_id)` | READ | Check existence |
| `delete(entity_id)` | DELETE | Delete with DETACH |
| `update_field(entity_id, field, value)` | UPDATE | Update single field |
| `find_by_field(field, value, limit)` | READ | Find by field value |
| `create(data, **kwargs)` | CREATE | Abstract - implemented by subclass |
| `update(entity_id, data)` | UPDATE | Abstract - implemented by subclass |

### Security Features

**Cypher Injection Prevention:**
```python
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def validate_identifier(name: str, param_name: str = "identifier") -> str:
    """Validate identifier is safe for Cypher queries"""
    if not VALID_IDENTIFIER_PATTERN.match(name):
        raise ValueError(f"Invalid {param_name}")
    if len(name) > 64:
        raise ValueError(f"{param_name} too long")
    return name
```

**Query Safety:**
- Order direction validated to `ASC`/`DESC` only
- Limit capped at 1000 to prevent memory exhaustion
- Field names validated before interpolation

### Example Cypher Queries

```cypher
-- get_by_id
MATCH (n:{node_label} {id: $id})
RETURN n {.*} AS entity

-- get_all with pagination
MATCH (n:{node_label})
RETURN n {.*} AS entity
ORDER BY n.{order_by} {order_dir}
SKIP $skip
LIMIT $limit

-- delete
MATCH (n:{node_label} {id: $id})
DETACH DELETE n
RETURN count(n) AS deleted
```

### Helper Methods
- `_generate_id()` - UUID generation
- `_now()` - Timezone-aware UTC timestamp
- `_to_model(record)` - Dict to Pydantic model conversion
- `_to_models(records)` - Batch conversion with error filtering

---

## Audit Repository

**File:** `audit_repository.py`
**Lines:** 1111
**Purpose:** Comprehensive audit logging for all system actions, compliance, and anomaly detection

### Data Model
- **Node Label:** `AuditLog`
- **Model:** `AuditEvent`

### Core Operations

| Category | Methods |
|----------|---------|
| **Logging** | `log()`, `log_capsule_action()`, `log_user_action()`, `log_governance_action()`, `log_overlay_action()`, `log_security_event()`, `log_immune_event()`, `log_cascade_action()`, `log_action()` |
| **Queries** | `get_by_id()`, `get_by_correlation_id()`, `get_by_actor()`, `get_by_resource()`, `get_by_event_type()`, `search()` |
| **Analytics** | `get_activity_summary()`, `get_event_counts_by_type()`, `get_actor_activity()`, `get_failed_logins()`, `get_security_events()` |
| **Maintenance** | `purge_old_events()`, `archive_events()`, `count_events()`, `list()` |
| **Bulk Ops** | `log_bulk_operation()`, `log_data_export()`, `log_maintenance_mode()`, `log_self_audit()` |

### Cypher Queries

```cypher
-- Create audit log
CREATE (a:AuditLog {
    id: $id,
    event_type: $event_type,
    actor_id: $actor_id,
    action: $action,
    resource_type: $resource_type,
    resource_id: $resource_id,
    details: $details,
    old_value: $old_value,
    new_value: $new_value,
    ip_address: $ip_address,
    user_agent: $user_agent,
    correlation_id: $correlation_id,
    priority: $priority,
    trust_level_required: $trust_level_required,
    timestamp: datetime($timestamp),
    created_at: datetime($created_at)
})
RETURN a

-- Search with multiple filters
MATCH (a:AuditLog)
WHERE a.action CONTAINS $query_text
  AND a.event_type IN $event_types
  AND a.actor_id IN $actor_ids
  AND a.resource_type IN $resource_types
  AND a.timestamp >= datetime($since)
  AND a.timestamp <= datetime($until)
  AND a.priority >= $priority
RETURN a
ORDER BY a.timestamp DESC
SKIP $offset
LIMIT $limit

-- Failed login detection (security)
MATCH (a:AuditLog {event_type: $event_type})
WHERE a.timestamp >= datetime($since)
WITH a.actor_id as actor_id,
     count(a) as attempt_count,
     collect(a.ip_address) as ip_addresses,
     max(a.timestamp) as last_attempt
WHERE attempt_count >= $threshold
RETURN actor_id, attempt_count, ip_addresses, last_attempt
ORDER BY attempt_count DESC
```

### Security Fixes Applied
1. **Label Injection Prevention (M14):** Archive label validated with regex
2. **Bulk Operation Logging (Audit 3):** Tracks operations affecting multiple resources
3. **Data Export Logging (Audit 3):** GDPR compliance for exports
4. **Self-Audit (Audit 3):** Tracks operations on audit log itself

---

## Capsule Repository

**File:** `capsule_repository.py`
**Lines:** 1680
**Purpose:** Capsule CRUD, symbolic inheritance (lineage), semantic search, and integrity verification

### Data Model
- **Node Label:** `Capsule`
- **Model:** `Capsule`, `CapsuleWithLineage`
- **Relationships:** `DERIVED_FROM`, `SEMANTIC_EDGE`

### Core Operations

| Category | Methods |
|----------|---------|
| **CRUD** | `create()`, `update()`, `get_by_id()`, `get_by_owner()`, `archive()`, `list()`, `get_recent()` |
| **Lineage** | `get_lineage()`, `get_children()`, `get_descendants()`, `get_ancestors()`, `add_parent()` |
| **Search** | `semantic_search()`, `find_similar_by_embedding()` |
| **Semantic Edges** | `create_semantic_edge()`, `get_semantic_neighbors()`, `find_contradictions()`, `find_contradiction_clusters()`, `get_semantic_edges()`, `delete_semantic_edge()`, `update_semantic_edge()` |
| **Integrity** | `verify_integrity()`, `verify_lineage_integrity()`, `get_with_integrity_check()` |
| **Federation** | `get_changes_since()`, `get_edges_since()` |

### Integrity Features

```python
# SHA-256 content hash on create
content_hash = CapsuleIntegrityService.compute_content_hash(data.content)

# Merkle root for lineage verification
merkle_root = CapsuleIntegrityService.compute_merkle_root(
    content_hash, parent_merkle_root
)
```

### Key Cypher Queries

```cypher
-- Create capsule with inheritance
MATCH (parent:Capsule {id: $parent_id})
CREATE (c:Capsule {
    id: $id,
    content: $content,
    content_hash: $content_hash,
    merkle_root: $merkle_root,
    parent_content_hash: $parent_content_hash,
    ...
})
CREATE (c)-[:DERIVED_FROM {
    reason: $evolution_reason,
    timestamp: $now,
    parent_content_hash: $parent_content_hash,
    parent_merkle_root: $parent_merkle_root
}]->(parent)
SET parent.fork_count = parent.fork_count + 1
RETURN c {.*} AS capsule

-- Get full lineage (Isnad chain)
MATCH (c:Capsule {id: $id})
OPTIONAL MATCH path = (c)-[:DERIVED_FROM*0..]->(ancestor:Capsule)
WHERE NOT (ancestor)-[:DERIVED_FROM]->()
WITH c, collect(DISTINCT {
    id: ancestor.id,
    version: ancestor.version,
    title: ancestor.title,
    type: ancestor.type,
    created_at: ancestor.created_at,
    trust_level: ancestor.trust_level,
    depth: length(path)
}) AS lineage
...

-- Vector semantic search
CALL db.index.vector.queryNodes('capsule_embeddings', $limit, $embedding)
YIELD node AS capsule, score
WHERE capsule.trust_level >= $min_trust
RETURN capsule {.*} AS capsule, score
ORDER BY score DESC

-- Find semantic neighbors
MATCH (c:Capsule {id: $id})-[r:SEMANTIC_EDGE]-(neighbor:Capsule)
WHERE r.confidence >= $min_confidence
  AND r.relationship_type IN $type_values
RETURN neighbor.id AS capsule_id,
       neighbor.title AS title,
       r.relationship_type AS relationship_type,
       r.confidence AS confidence
```

### Security Fixes Applied
1. **H26 - Graph Traversal DoS:** `MAX_GRAPH_DEPTH = 20` limits traversal depth
2. **H27 - Authorization Check:** Update verifies `owner_id` matches `caller_id`
3. **M4 - Parameterized Type Filter:** Semantic neighbor type filter uses parameters

### Index Requirements
| Index | Type | Field(s) |
|-------|------|----------|
| `capsule_embeddings` | Vector | `embedding` |
| Unique | Property | `id` |
| Standard | Property | `owner_id`, `type`, `tags`, `created_at` |

---

## Cascade Repository

**File:** `cascade_repository.py`
**Lines:** 520
**Purpose:** Persist cascade chains and events for restart recovery

### Data Model
- **Node Labels:** `CascadeChain`, `CascadeEvent`
- **Models:** `CascadeChain`, `CascadeEvent`
- **Relationship:** `HAS_EVENT` with `order` property

### Core Operations

| Category | Methods |
|----------|---------|
| **Chain CRUD** | `create_chain()`, `update_chain()`, `complete_chain()`, `get_by_id()`, `delete_chain()` |
| **Events** | `add_event()` |
| **Queries** | `get_active_chains()`, `get_completed_chains()` |
| **Maintenance** | `cleanup_old_chains()`, `get_metrics()` |

### Key Cypher Queries

```cypher
-- Create cascade chain
CREATE (c:CascadeChain {
    cascade_id: $cascade_id,
    initiated_by: $initiated_by,
    initiated_at: $initiated_at,
    total_hops: $total_hops,
    overlays_affected: $overlays_affected,
    insights_generated: $insights_generated,
    actions_triggered: $actions_triggered,
    errors_encountered: $errors_encountered,
    status: 'active'
})
RETURN c {.*} AS chain

-- Add event to chain
MATCH (c:CascadeChain {cascade_id: $cascade_id})
CREATE (e:CascadeEvent $event_data)
CREATE (c)-[:HAS_EVENT {order: $order}]->(e)
SET c.total_hops = c.total_hops + 1,
    c.insights_generated = c.insights_generated + 1
RETURN e {.*} AS event

-- Get chain with ordered events
MATCH (c:CascadeChain {cascade_id: $cascade_id})
OPTIONAL MATCH (c)-[r:HAS_EVENT]->(e:CascadeEvent)
WITH c, e, r
ORDER BY r.order ASC
WITH c, collect(e {.*}) AS events
RETURN c {.*} AS chain, events

-- Cleanup old completed chains
MATCH (c:CascadeChain)
WHERE c.status = 'completed'
  AND c.completed_at IS NOT NULL
  AND datetime(c.completed_at) < datetime() - duration({days: $days_old})
OPTIONAL MATCH (c)-[:HAS_EVENT]->(e:CascadeEvent)
WITH c, collect(e) AS events
DETACH DELETE c
FOREACH (e IN events | DELETE e)
RETURN count(c) AS deleted
```

### Singleton Pattern
```python
_cascade_repo: CascadeRepository | None = None

def get_cascade_repository(client: Neo4jClient | None = None) -> CascadeRepository:
    """Get or create singleton instance"""
    global _cascade_repo
    if _cascade_repo is None:
        if client is None:
            raise ValueError("Neo4j client required for first initialization")
        _cascade_repo = CascadeRepository(client)
    return _cascade_repo
```

---

## Governance Repository

**File:** `governance_repository.py`
**Lines:** 1295
**Purpose:** Democratic governance - proposals, votes, Constitutional AI review, Ghost Council

### Data Model
- **Node Labels:** `Proposal`, `Vote`, `VoteDelegation`
- **Models:** `Proposal`, `Vote`, `VoteDelegation`, `GovernanceStats`

### Proposal Lifecycle
```
DRAFT -> VOTING -> PASSED/REJECTED -> EXECUTED
           |
           v
       CANCELLED
```

### Core Operations

| Category | Methods |
|----------|---------|
| **Proposals** | `create()`, `update()`, `start_voting()`, `close_voting()`, `mark_executed()`, `cancel()` |
| **Voting** | `cast_vote()`, `get_vote()`, `get_votes()`, `get_voter_history()`, `record_vote()` |
| **Delegation** | `create_delegation()`, `revoke_delegation()`, `get_delegates()`, `get_user_delegations()` |
| **AI Review** | `save_constitutional_review()`, `save_ghost_council_opinion()` |
| **Queries** | `get_by_status()`, `get_active_proposals()`, `get_by_proposer()`, `get_expiring_soon()` |
| **Stats** | `get_stats()`, `_count_eligible_voters()` |

### Trust-Weighted Voting

```cypher
-- Cast vote with trust weight (atomically updates tallies)
MATCH (p:Proposal {id: $proposal_id})
WHERE p.status = 'voting'
CREATE (v:Vote {
    id: $vote_id,
    proposal_id: $proposal_id,
    voter_id: $voter_id,
    choice: $choice,
    weight: $weight,
    ...
})
CREATE (v)-[:VOTED]->(p)
SET
    p.votes_for = CASE WHEN $choice = 'for' THEN p.votes_for + 1 ELSE p.votes_for END,
    p.votes_against = CASE WHEN $choice = 'against' THEN p.votes_against + 1 ELSE p.votes_against END,
    p.weight_for = CASE WHEN $choice = 'for' THEN p.weight_for + $weight ELSE p.weight_for END,
    p.weight_against = CASE WHEN $choice = 'against' THEN p.weight_against + $weight ELSE p.weight_against END,
    ...
RETURN v {.*} AS vote
```

### Security Fixes Applied

1. **H20 - Trust Weight Verification:**
```python
# Don't trust the trust_weight parameter - fetch from database
verify_query = """
MATCH (u:User {id: $voter_id})
RETURN u.trust_flame AS trust_flame
"""
actual_trust = verify_result.get("trust_flame", 0)
verified_weight = max(0, min(actual_trust, 100)) / 100.0
```

2. **H21 - Timelock Enforcement:**
```cypher
-- Verify timelock before execution
MATCH (p:Proposal {id: $id})
WHERE p.status = 'passed'
  AND (
    p.execution_allowed_after IS NULL
    OR datetime(p.execution_allowed_after) <= datetime($now)
  )
SET p.status = 'executed', ...
```

3. **M5 - Quorum Verification:**
```python
if eligible_voters == 0:
    quorum_met = False
else:
    participation_rate = total_votes / eligible_voters
    quorum_met = participation_rate >= proposal.quorum_percent
```

4. **Double-Vote Prevention (MERGE):**
```cypher
MERGE (v:Vote {proposal_id: $proposal_id, voter_id: $voter_id})
ON CREATE SET v.is_new = true, ...
ON MATCH SET v.is_new = false
```

---

## Graph Repository

**File:** `graph_repository.py`
**Lines:** 1442
**Purpose:** Graph algorithms with layered backend (GDS > Cypher > NetworkX)

### Backend Detection
```python
async def detect_backend(self) -> GraphBackend:
    if self._gds_available is None:
        self._gds_available = await self._check_gds_available()
    return GraphBackend.GDS if self._gds_available else GraphBackend.CYPHER
```

### Core Operations

| Category | Methods |
|----------|---------|
| **PageRank** | `compute_pagerank()`, `_gds_pagerank()`, `_cypher_pagerank()` |
| **Centrality** | `compute_centrality()`, `_degree_centrality()`, `_gds_centrality()` |
| **Communities** | `detect_communities()`, `_gds_communities()`, `_cypher_communities()` |
| **Trust** | `compute_trust_transitivity()`, `get_trust_influences()` |
| **Similarity** | `compute_node_similarity()`, `_gds_node_similarity()`, `_cypher_node_similarity()` |
| **Paths** | `compute_shortest_path()`, `_gds_shortest_path()`, `_cypher_shortest_path()` |
| **Metrics** | `get_graph_metrics()` |

### Security Validation

```python
_SAFE_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')

def validate_neo4j_identifier(value: str, identifier_type: str = "identifier") -> str:
    """Prevents Cypher/GDS injection attacks"""
    if not value or len(value) > 128:
        raise ValueError(...)
    if not _SAFE_IDENTIFIER_PATTERN.match(value):
        raise ValueError(...)
    return value

def validate_relationship_pattern(rel_types: list[str]) -> str:
    """Validates each type before joining with | for Cypher patterns"""
    validated = [validate_neo4j_identifier(rt) for rt in rel_types]
    return "|".join(validated)
```

### Key Cypher Queries

```cypher
-- PageRank approximation (Cypher fallback)
MATCH (n:Capsule)
OPTIONAL MATCH (n)<-[:DERIVED_FROM]-(incoming)
OPTIONAL MATCH (n)-[:DERIVED_FROM]->(outgoing)
WITH n,
     count(DISTINCT incoming) AS in_degree,
     count(DISTINCT outgoing) AS out_degree
WITH n, in_degree, out_degree,
     (in_degree * 1.0 + 1) / (out_degree + 1) AS raw_score
WITH n, raw_score,
     (raw_score * $damping + (1 - $damping)) AS score
ORDER BY score DESC
LIMIT $limit
RETURN n.id AS node_id, score

-- Community detection (connected components)
MATCH (n:Capsule)
WHERE NOT EXISTS { MATCH (n)-[:DERIVED_FROM]->() }
OPTIONAL MATCH path = (n)<-[:DERIVED_FROM*0..10]-(descendant:Capsule)
WITH n AS root, collect(DISTINCT descendant) + [n] AS members
WHERE size(members) >= $min_size
RETURN id(root) AS community_id,
       [m IN members | m.id] AS member_ids

-- Trust transitivity with decay
MATCH path = (source:Capsule {id: $source_id})-[:DERIVED_FROM|SEMANTIC_EDGE*1..5]-(target:Capsule {id: $target_id})
WITH path,
     [n IN nodes(path) | n.trust_level] AS trusts,
     length(path) AS path_length
WITH path, trusts, path_length,
     reduce(trust = 1.0, i IN range(0, size(trusts)-2) |
            trust * (1 - $decay) * (trusts[i+1] / 100.0)
     ) AS cumulative_trust
RETURN [n IN nodes(path) | n.id] AS path_nodes,
       cumulative_trust
ORDER BY cumulative_trust DESC
LIMIT 10
```

### Caching
```python
def __init__(self, ...):
    self._cache: dict[str, tuple[Any, datetime]] = {}

def _get_cached(self, cache_key: str) -> Any | None:
    if cache_key in self._cache:
        value, cached_at = self._cache[cache_key]
        age = (datetime.utcnow() - cached_at).total_seconds()
        if age < self.config.cache_ttl_seconds:
            return value
    return None
```

---

## Overlay Repository

**File:** `overlay_repository.py`
**Lines:** 616
**Purpose:** Overlay lifecycle, state transitions, metrics, and health monitoring

### Data Model
- **Node Label:** `Overlay`
- **Model:** `Overlay`, `OverlayMetrics`, `OverlayExecution`, `OverlayHealthCheck`

### Overlay States
```
REGISTERED -> LOADING -> ACTIVE <-> INACTIVE
                           |
                           v
                      QUARANTINED
                           |
                           v (recover)
                       INACTIVE
```

### Core Operations

| Category | Methods |
|----------|---------|
| **CRUD** | `create()`, `update()`, `get_by_id()`, `get_by_name()` |
| **State** | `set_state()`, `activate()`, `deactivate()`, `quarantine()`, `recover()` |
| **Metrics** | `record_execution()`, `record_health_check()`, `get_metrics()` |
| **Queries** | `get_by_state()`, `get_active()`, `get_quarantined()`, `get_by_capability()`, `get_by_trust_level()`, `get_dependencies()`, `get_dependents()`, `get_unhealthy()` |

### Security Fix - H28: WASM Hash Verification

```python
def _compute_content_hash(self, content: bytes) -> str:
    """Compute SHA-256 hash of overlay content"""
    import hashlib
    return hashlib.sha256(content).hexdigest()

async def create(self, data: OverlayCreate, wasm_content: bytes | None = None, ...):
    # Verify WASM hash if content provided
    if wasm_content:
        computed_hash = self._compute_content_hash(wasm_content)
        if data.source_hash and data.source_hash != computed_hash:
            raise ValueError(f"WASM hash mismatch")
        verified_hash = computed_hash
```

### Key Cypher Queries

```cypher
-- Record execution and update metrics
MATCH (o:Overlay {id: $id})
SET
    o.total_executions = o.total_executions + 1,
    o.successful_executions = CASE WHEN $success THEN o.successful_executions + 1 ELSE o.successful_executions END,
    o.failed_executions = CASE WHEN NOT $success THEN o.failed_executions + 1 ELSE o.failed_executions END,
    o.avg_execution_time_ms = (o.total_execution_time_ms + $exec_time) / (o.total_executions + 1),
    o.consecutive_failures = CASE WHEN $success THEN 0 ELSE o.consecutive_failures + 1 END,
    ...
RETURN o.consecutive_failures AS consecutive_failures

-- Auto-quarantine check
if consecutive_failures >= 5:
    await self.quarantine(overlay_id, "Auto-quarantine: 5 consecutive failures")

-- Find unhealthy overlays
MATCH (o:Overlay)
WHERE o.state = 'ACTIVE'
AND (
    o.consecutive_failures >= $failures_threshold
    OR (o.total_executions > 0 AND toFloat(o.failed_executions) / o.total_executions > $error_threshold)
)
RETURN o {.*} AS entity
```

---

## Temporal Repository

**File:** `temporal_repository.py`
**Lines:** 922
**Purpose:** Capsule versioning and trust snapshots with hybrid snapshot/diff strategy

### Data Model
- **Node Labels:** `CapsuleVersion`, `TrustSnapshot`, `GraphSnapshot`
- **Models:** `CapsuleVersion`, `TrustSnapshot`, `GraphSnapshot`, `VersionHistory`, `TrustTimeline`
- **Relationships:** `HAS_VERSION`, `PREVIOUS_VERSION`

### Versioning Strategy
```python
class VersioningPolicy:
    """Determines when to create full snapshots vs diffs"""

    def should_full_snapshot(self, change_number, trust_level, is_major_version, diff_chain_length):
        # Full snapshot conditions:
        # 1. Every N changes (default: 10)
        # 2. High trust content (default: 90+)
        # 3. Major version changes
        # 4. Diff chain too long (default: 20)
```

### Core Operations

| Category | Methods |
|----------|---------|
| **Versioning** | `create_version()`, `get_version_history()`, `get_capsule_at_time()`, `diff_versions()` |
| **Trust** | `create_trust_snapshot()`, `get_trust_timeline()` |
| **Graph** | `create_graph_snapshot()`, `get_latest_graph_snapshot()`, `get_graph_snapshots()` |
| **Maintenance** | `compact_old_versions()` |

### Key Cypher Queries

```cypher
-- Create version with diff chain tracking
CREATE (v:CapsuleVersion {
    id: $id,
    capsule_id: $capsule_id,
    version_number: $version_number,
    snapshot_type: $snapshot_type,
    content_snapshot: $content_snapshot,
    content_hash: $content_hash,
    diff_from_previous: $diff_json,
    parent_version_id: $parent_version_id,
    diff_chain_length: $diff_chain_length,
    ...
})
WITH v
MATCH (c:Capsule {id: $capsule_id})
CREATE (c)-[:HAS_VERSION]->(v)
WITH v
OPTIONAL MATCH (prev:CapsuleVersion {id: $parent_version_id})
FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
    CREATE (v)-[:PREVIOUS_VERSION]->(prev)
)
RETURN v {.*} AS version

-- Reconstruct content from diff chain
MATCH path = (v:CapsuleVersion {id: $version_id})-[:PREVIOUS_VERSION*0..20]->(snapshot:CapsuleVersion)
WHERE snapshot.snapshot_type = 'full'
WITH path, snapshot, length(path) AS distance
ORDER BY distance
LIMIT 1
RETURN [n IN nodes(path) | n {.*}] AS chain
```

### Trust Snapshot Compression
```python
class TrustSnapshotCompressor:
    """Compresses derived trust changes"""

    def compress(self, snapshot: TrustSnapshot) -> TrustSnapshot:
        # Essential changes preserved in full
        # Derived changes get reconstruction hints
```

---

## User Repository

**File:** `user_repository.py`
**Lines:** 621
**Purpose:** User CRUD, authentication, and trust flame management

### Data Model
- **Node Label:** `User`
- **Models:** `User`, `UserInDB`, `UserPublic`, `UserCreate`, `UserUpdate`

### Security-First Design

**Safe Field Lists:**
```python
USER_SAFE_FIELDS = """
    .id, .username, .email, .display_name, .bio, .avatar_url,
    .role, .trust_flame, .is_active, .is_verified, .auth_provider,
    .last_login, .metadata, .created_at, .updated_at
""".strip()

# Excludes: password_hash, refresh_token, failed_login_attempts, lockout_until
```

### Core Operations

| Category | Methods |
|----------|---------|
| **CRUD** | `create()`, `update()`, `get_by_id()`, `delete()` |
| **Auth** | `get_by_username()`, `get_by_email()`, `get_by_username_or_email()`, `update_password()`, `update_refresh_token()`, `validate_refresh_token()` |
| **Login** | `record_login()`, `record_failed_login()`, `set_lockout()`, `clear_lockout()` |
| **Password Reset** | `store_password_reset_token()`, `validate_password_reset_token()`, `clear_password_reset_token()` |
| **Trust** | `adjust_trust_flame()`, `get_by_trust_level()` |
| **Status** | `deactivate()`, `activate()`, `set_verified()` |
| **Checks** | `username_exists()`, `email_exists()` |

### Security Fixes Applied

1. **Safe Field Projection (Audit 3):**
```python
async def get_by_id(self, entity_id: str) -> User | None:
    query = f"""
    MATCH (u:User {{id: $id}})
    RETURN u {{{USER_SAFE_FIELDS}}} AS user
    """
```

2. **Refresh Token Hashing (Audit 4):**
```python
async def update_refresh_token(self, user_id: str, refresh_token: str | None):
    # Hash the token before storing
    token_hash = hash_refresh_token(refresh_token) if refresh_token else None
    ...

async def validate_refresh_token(self, user_id: str, token: str) -> bool:
    stored_hash = await self.get_refresh_token(user_id)
    return verify_refresh_token_hash(token, stored_hash)
```

3. **Safe Model Conversion:**
```python
def to_safe_user(self, user_in_db: UserInDB) -> User:
    """Strips password_hash and sensitive fields before API exposure"""
```

### Key Cypher Queries

```cypher
-- Trust flame adjustment with bounds
MATCH (u:User {id: $id})
WITH u, u.trust_flame AS old_value
SET u.trust_flame = CASE
    WHEN u.trust_flame + $adjustment < 0 THEN 0
    WHEN u.trust_flame + $adjustment > 100 THEN 100
    ELSE u.trust_flame + $adjustment
END
RETURN old_value, u.trust_flame AS new_value, u.id AS user_id

-- Case-insensitive username lookup
MATCH (u:User)
WHERE toLower(u.username) = toLower($username)
RETURN u {.*} AS user

-- Password reset token validation
MATCH (u:User {id: $id})
WHERE u.password_reset_token = $token_hash
  AND u.password_reset_expires > $now
RETURN u.id AS id
```

---

## Cross-Cutting Concerns

### Error Handling
All repositories use consistent error handling:
- Return `None` for not found
- Raise `RuntimeError` for creation failures
- Log errors with `structlog`

### Logging
```python
self.logger = structlog.get_logger(self.__class__.__name__)

self.logger.info("Created entity", entity_id=id, ...)
self.logger.warning("Operation failed", ...)
self.logger.error("Critical error", error=str(e), ...)
```

### DateTime Handling
```python
def _parse_datetime(self, value: Any) -> datetime:
    if value is None:
        return self._now()
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_native"):  # Neo4j datetime
        return value.to_native()
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return self._now()
```

### Model Conversion
```python
def _to_model(self, record: dict[str, Any]) -> T | None:
    try:
        return self.model_class.model_validate(record)
    except Exception as e:
        self.logger.error("Failed to convert record", error=str(e))
        return None
```

---

## Index Recommendations

### Essential Indexes

```cypher
-- User lookups (case-insensitive)
CREATE INDEX user_username IF NOT EXISTS FOR (u:User) ON (u.username);
CREATE INDEX user_email IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX user_id IF NOT EXISTS FOR (u:User) ON (u.id);

-- Capsule queries
CREATE INDEX capsule_id IF NOT EXISTS FOR (c:Capsule) ON (c.id);
CREATE INDEX capsule_owner IF NOT EXISTS FOR (c:Capsule) ON (c.owner_id);
CREATE INDEX capsule_type IF NOT EXISTS FOR (c:Capsule) ON (c.type);
CREATE INDEX capsule_created IF NOT EXISTS FOR (c:Capsule) ON (c.created_at);

-- Vector index for semantic search
CALL db.index.vector.createNodeIndex(
  'capsule_embeddings',
  'Capsule',
  'embedding',
  1536,
  'cosine'
);

-- Audit log queries
CREATE INDEX audit_actor IF NOT EXISTS FOR (a:AuditLog) ON (a.actor_id);
CREATE INDEX audit_resource IF NOT EXISTS FOR (a:AuditLog) ON (a.resource_type, a.resource_id);
CREATE INDEX audit_timestamp IF NOT EXISTS FOR (a:AuditLog) ON (a.timestamp);
CREATE INDEX audit_correlation IF NOT EXISTS FOR (a:AuditLog) ON (a.correlation_id);

-- Proposal queries
CREATE INDEX proposal_status IF NOT EXISTS FOR (p:Proposal) ON (p.status);
CREATE INDEX proposal_proposer IF NOT EXISTS FOR (p:Proposal) ON (p.proposer_id);

-- Overlay queries
CREATE INDEX overlay_state IF NOT EXISTS FOR (o:Overlay) ON (o.state);
CREATE INDEX overlay_name IF NOT EXISTS FOR (o:Overlay) ON (o.name);

-- Version and snapshot queries
CREATE INDEX version_capsule IF NOT EXISTS FOR (v:CapsuleVersion) ON (v.capsule_id);
CREATE INDEX trust_entity IF NOT EXISTS FOR (t:TrustSnapshot) ON (t.entity_id, t.entity_type);
CREATE INDEX graph_snapshot_time IF NOT EXISTS FOR (g:GraphSnapshot) ON (g.created_at);

-- Cascade queries
CREATE INDEX cascade_status IF NOT EXISTS FOR (c:CascadeChain) ON (c.status);
```

### Full-Text Search Indexes

```cypher
-- Audit log action search
CALL db.index.fulltext.createNodeIndex(
  'audit_action_search',
  ['AuditLog'],
  ['action']
);

-- Capsule content search
CALL db.index.fulltext.createNodeIndex(
  'capsule_content_search',
  ['Capsule'],
  ['title', 'content', 'summary']
);
```

---

## Issues Found

| Severity | File | Issue | Suggested Fix |
|----------|------|-------|---------------|
| Medium | audit_repository.py | CONTAINS search not using full-text index | Add full-text index on `action` field |
| Medium | audit_repository.py | No pagination in `get_by_correlation_id()` | Add `limit` parameter |
| Medium | capsule_repository.py | N+1 query potential in `get_lineage()` | Optimize with single traversal query |
| Medium | capsule_repository.py | Vector index dependency | Add graceful degradation for missing index |
| Medium | cascade_repository.py | No event count limit per chain | Add `max_events` configuration |
| Medium | cascade_repository.py | Global singleton pattern | Consider dependency injection |
| Medium | graph_repository.py | Unbounded cache | Add LRU eviction with max size |
| Medium | graph_repository.py | GDS graph name uses f-string | Validate graph names before use |
| Low | audit_repository.py | JSON serialization for dict fields | Consider native Neo4j map storage |
| Low | capsule_repository.py | Archived capsules never purged | Add cleanup job |
| Low | governance_repository.py | Hardcoded policies | Move to database configuration |
| Low | governance_repository.py | No vote audit trail | Track vote changes |
| Low | governance_repository.py | Expired delegations not auto-removed | Add cleanup job |
| Low | overlay_repository.py | No version history for updates | Track update history |
| Low | overlay_repository.py | WASM content not stored | Consider object storage |
| Low | temporal_repository.py | Simple line-based diff | Use Myers diff algorithm |
| Low | temporal_repository.py | No conflict detection | Add concurrent edit detection |
| Low | user_repository.py | Case-insensitive search inefficient | Store normalized username/email |
| Low | user_repository.py | Trust adjustments not persisted | Integrate with TemporalRepository |

---

## Improvements Identified

| Priority | File | Improvement | Benefit |
|----------|------|-------------|---------|
| 1 | All | Add full-text index for search fields | 10x search performance |
| 1 | capsule_repository.py | Composite index on `(owner_id, is_archived, created_at)` | Query optimization |
| 1 | audit_repository.py | Time-based partitioning for audit logs | Storage efficiency |
| 2 | graph_repository.py | LRU cache eviction | Memory management |
| 2 | temporal_repository.py | Myers diff algorithm | Better diff quality |
| 2 | governance_repository.py | Policy nodes in database | Dynamic configuration |
| 2 | overlay_repository.py | Store WASM in object storage | Proper binary storage |
| 3 | user_repository.py | Integrate trust history with TemporalRepository | Analytics capability |
| 3 | capsule_repository.py | Cursor-based pagination for lineage | Handle deep hierarchies |
| 3 | governance_repository.py | Vote history tracking | Audit compliance |
| 3 | cascade_repository.py | TTL-based automatic cleanup | Storage management |
| 4 | temporal_repository.py | Background compaction job | Maintain query performance |
| 4 | governance_repository.py | Delegation cleanup job | Data hygiene |
| 4 | All | Add repository-level caching layer | Reduce database load |

---

## Possibilities Enabled

### Current Capabilities
1. **Full Audit Trail** - Every action tracked with correlation
2. **Semantic Graph** - Vector search + relationship traversal
3. **Trust Propagation** - Transitive trust calculation
4. **Version Time Travel** - Point-in-time recovery
5. **Democratic Governance** - Trust-weighted voting

### Future Extensions
1. **Real-time Sync** - Federation-ready change tracking (`get_changes_since`)
2. **Graph Analytics** - PageRank, community detection (GDS integration)
3. **Anomaly Detection** - Pattern analysis on audit logs
4. **Content Integrity** - Merkle tree verification for lineage
5. **Smart Overlays** - WASM with health monitoring and auto-quarantine

---

*Analysis completed by Claude Code - 2026-01-10*
