# FORGE CASCADE RESILIENCE SPECIFICATION V1

**Document Version:** 1.0.0  
**Created:** 2026-01-06  
**Author:** Frowg Systems, Inc.  
**Status:** Draft Specification  
**Classification:** Internal Architecture Document

---

## Document Control

This specification extends the Forge Cascade V3 architecture with solutions for scalability, security, operational resilience, and deployment flexibility. All components defined herein integrate with existing Forge subsystems and maintain backward compatibility with the core specification.

**Prerequisites:** This document assumes familiarity with FORGE_SPECIFICATION_V3_COMPLETE.md, particularly sections on Neo4j Unified Data Store, Seven-Phase Pipeline, Immune System Architecture, and Governance System.

---

## Table of Contents

1. Executive Summary
2. Graph Performance Optimization Layer
3. Lineage Storage Efficiency System
4. Operational Resilience Framework
5. Cold Start Mitigation System
6. Model Migration Architecture
7. Security Hardening Layer
8. Deployment Flexibility (Forge Lite)
9. Integration Points
10. Implementation Priority Matrix

---

## 1. Executive Summary

### 1.1 Purpose

This specification addresses seven critical challenges identified through competitive analysis and architectural review. Each challenge represents a potential failure mode or scaling limitation that could impact Forge's production viability. The solutions presented maintain Forge's core differentiators (Cascade Effect, Symbolic Inheritance, Knowledge Capsules) while ensuring enterprise-grade reliability.

### 1.2 Challenges Addressed

| Challenge | Impact | Solution Domain |
|-----------|--------|-----------------|
| Knowledge graph performance degradation at scale | Query latency exceeds SLA above 100K nodes | Graph Performance Optimization Layer |
| Lineage tracking storage overhead (10-30%) | Storage costs scale non-linearly | Lineage Storage Efficiency System |
| Architectural complexity and maintenance burden | Operational expertise requirements | Operational Resilience Framework |
| Cold start problem for new deployments | Zero initial value proposition | Cold Start Mitigation System |
| Knowledge loss during model updates | Core "ephemeral wisdom" problem | Model Migration Architecture |
| Memory poisoning and security vulnerabilities | $4.63M average breach cost | Security Hardening Layer |
| Complexity overkill for simple use cases | Market adoption friction | Deployment Flexibility (Forge Lite) |

### 1.3 Design Principles

All solutions in this specification adhere to the following principles.

**Incremental Adoption:** Solutions can be enabled progressively without requiring full system reconfiguration. Organizations start with baseline functionality and enable advanced features as needs grow.

**Backward Compatibility:** No solution breaks existing capsule structures, lineage chains, or API contracts. Migrations are non-destructive and reversible.

**Observable by Default:** Every solution includes metrics, logging, and tracing hooks that integrate with existing Prometheus and OpenTelemetry infrastructure.

**Fail-Safe Degradation:** When optimization systems fail, Forge falls back to unoptimized but correct behavior rather than failing entirely.

---

## 2. Graph Performance Optimization Layer

### 2.1 Problem Statement

Neo4j knowledge graphs experience significant performance degradation when edge density exceeds 0.1 (10% of possible node pairs connected) or when multi-hop traversals exceed 4 levels. Production Forge deployments targeting 100K+ capsules require architectural mitigations to maintain sub-200ms query latency.

### 2.2 Domain-Based Graph Partitioning

#### 2.2.1 Partition Schema

Capsules are assigned to logical partitions based on their domain classification. Partitions enable query isolation, allowing traversals to operate within bounded subgraphs rather than scanning the entire knowledge space.

```cypher
// Partition node structure
CREATE (p:Partition {
    id: randomUUID(),
    name: String,                    // Human-readable partition name
    domain_patterns: [String],       // Regex patterns for auto-assignment
    max_capsules: Integer,           // Soft limit triggering subdivision
    created_at: DateTime,
    statistics: {
        capsule_count: Integer,
        edge_density: Float,
        avg_query_latency_ms: Float,
        last_rebalanced: DateTime
    }
})

// Capsule-to-Partition relationship
CREATE (c:Capsule)-[:BELONGS_TO {
    assigned_at: DateTime,
    assignment_method: String,       // 'auto' | 'manual' | 'migration'
    confidence: Float                // For auto-assignment, 0.0-1.0
}]->(p:Partition)
```

#### 2.2.2 Partition Assignment Rules

The system assigns capsules to partitions using a hierarchical decision process.

**Rule 1 - Explicit Domain:** If the capsule's `domain` property matches a partition's `domain_patterns`, assign to that partition with confidence 1.0.

**Rule 2 - Content Classification:** If no explicit match, the ML Intelligence overlay classifies capsule content and assigns to the highest-confidence matching partition.

**Rule 3 - Lineage Inheritance:** If classification confidence is below 0.7, inherit the partition of the parent capsule (for derived capsules) to maintain lineage locality.

**Rule 4 - Default Partition:** Unclassifiable capsules go to a `_general` partition that receives periodic review for reclassification.

```python
class PartitionAssigner:
    """
    Assigns capsules to graph partitions for query isolation.
    
    The assigner prioritizes keeping related capsules together to
    minimize cross-partition traversals during lineage queries.
    """
    
    async def assign_partition(
        self,
        capsule: Capsule,
        ml_overlay: MLIntelligenceOverlay
    ) -> PartitionAssignment:
        # Rule 1: Check explicit domain match
        if capsule.domain:
            partition = await self._find_partition_by_domain(capsule.domain)
            if partition:
                return PartitionAssignment(
                    partition_id=partition.id,
                    method="explicit_domain",
                    confidence=1.0
                )
        
        # Rule 2: ML-based classification
        classification = await ml_overlay.classify_content(capsule.content)
        if classification.confidence >= 0.7:
            partition = await self._find_partition_by_domain(
                classification.primary_class
            )
            if partition:
                return PartitionAssignment(
                    partition_id=partition.id,
                    method="ml_classification",
                    confidence=classification.confidence
                )
        
        # Rule 3: Inherit from parent
        if capsule.parent_id:
            parent_partition = await self._get_capsule_partition(capsule.parent_id)
            if parent_partition:
                return PartitionAssignment(
                    partition_id=parent_partition.id,
                    method="lineage_inheritance",
                    confidence=0.8  # Slight discount for inherited assignment
                )
        
        # Rule 4: Default partition
        default_partition = await self._get_default_partition()
        return PartitionAssignment(
            partition_id=default_partition.id,
            method="default",
            confidence=0.5
        )
```

#### 2.2.3 Cross-Partition Query Handling

When lineage chains span multiple partitions, the query planner executes a federated traversal.

```python
class FederatedLineageQuery:
    """
    Executes lineage queries that may span multiple partitions.
    
    The query planner first identifies which partitions contain
    relevant capsules, then executes parallel subqueries within
    each partition before merging results.
    """
    
    async def get_full_lineage(
        self,
        capsule_id: str,
        max_depth: int = 10
    ) -> LineageTree:
        # Phase 1: Identify partitions in lineage chain
        # This lightweight query traverses only DERIVED_FROM edges
        # to find partition boundaries without loading full capsules
        partition_map = await self._map_lineage_partitions(
            capsule_id, 
            max_depth
        )
        
        # Phase 2: Execute parallel partition-local queries
        partition_results = await asyncio.gather(*[
            self._query_partition_lineage(
                partition_id=pid,
                capsule_ids=capsule_ids,
                depth_range=depth_range
            )
            for pid, (capsule_ids, depth_range) in partition_map.items()
        ])
        
        # Phase 3: Merge results into unified lineage tree
        return self._merge_lineage_results(partition_results)
    
    async def _map_lineage_partitions(
        self,
        capsule_id: str,
        max_depth: int
    ) -> dict[str, tuple[list[str], tuple[int, int]]]:
        """
        Lightweight traversal to identify partition boundaries.
        
        Returns mapping of partition_id -> (capsule_ids, depth_range)
        for efficient parallel querying.
        """
        query = """
        MATCH path = (c:Capsule {id: $capsule_id})
                     -[:DERIVED_FROM*0..$max_depth]->(ancestor:Capsule)
        WITH ancestor, length(path) as depth
        MATCH (ancestor)-[:BELONGS_TO]->(p:Partition)
        RETURN p.id as partition_id, 
               collect(ancestor.id) as capsule_ids,
               min(depth) as min_depth,
               max(depth) as max_depth
        """
        # Execute and return partition map
        ...
```

### 2.3 Query Result Caching

#### 2.3.1 Cache Architecture

Forge implements a two-tier caching system for frequently accessed query patterns.

**Tier 1 - Application Cache (Redis):** Caches complete query results with TTL based on query type and capsule volatility. Lineage queries for stable capsules cache for 1 hour; recent capsules cache for 5 minutes.

**Tier 2 - Neo4j Query Cache:** Leverages Neo4j's internal query plan and result caching for repeated Cypher patterns.

```python
@dataclass
class CacheConfig:
    """Configuration for the query caching system."""
    
    # Tier 1: Redis application cache
    redis_url: str = "redis://localhost:6379"
    default_ttl_seconds: int = 300          # 5 minutes
    lineage_ttl_seconds: int = 3600         # 1 hour for stable lineage
    max_cached_result_bytes: int = 1048576  # 1MB max per result
    
    # Cache key patterns
    lineage_key_pattern: str = "forge:lineage:{capsule_id}:{depth}"
    search_key_pattern: str = "forge:search:{query_hash}"
    partition_key_pattern: str = "forge:partition:{partition_id}:stats"


class QueryCache:
    """
    Two-tier caching for Forge graph queries.
    
    The cache automatically invalidates entries when underlying
    capsules change, using Neo4j's change data capture to detect
    modifications.
    """
    
    def __init__(self, config: CacheConfig):
        self._redis = aioredis.from_url(config.redis_url)
        self._config = config
        self._invalidation_subscriptions: dict[str, set[str]] = {}
    
    async def get_or_compute_lineage(
        self,
        capsule_id: str,
        depth: int,
        compute_func: Callable
    ) -> LineageTree:
        """
        Retrieve lineage from cache or compute and cache result.
        
        Cache entries automatically invalidate when any capsule
        in the lineage chain is modified.
        """
        cache_key = self._config.lineage_key_pattern.format(
            capsule_id=capsule_id,
            depth=depth
        )
        
        # Check cache
        cached = await self._redis.get(cache_key)
        if cached:
            self._record_cache_hit("lineage")
            return LineageTree.deserialize(cached)
        
        # Compute result
        self._record_cache_miss("lineage")
        result = await compute_func()
        
        # Determine TTL based on capsule stability
        ttl = await self._compute_lineage_ttl(result)
        
        # Cache result
        serialized = result.serialize()
        if len(serialized) <= self._config.max_cached_result_bytes:
            await self._redis.setex(cache_key, ttl, serialized)
            
            # Register invalidation triggers for all capsules in lineage
            await self._register_invalidation_triggers(
                cache_key,
                result.all_capsule_ids()
            )
        
        return result
    
    async def _compute_lineage_ttl(self, lineage: LineageTree) -> int:
        """
        Compute appropriate TTL based on lineage stability.
        
        Recently modified capsules get shorter TTLs; stable
        lineage chains get longer caching periods.
        """
        most_recent_modification = max(
            c.updated_at for c in lineage.all_capsules()
        )
        age_hours = (datetime.utcnow() - most_recent_modification).total_seconds() / 3600
        
        if age_hours < 1:
            return 60          # 1 minute for very recent changes
        elif age_hours < 24:
            return 300         # 5 minutes for changes within a day
        elif age_hours < 168:  # 1 week
            return 1800        # 30 minutes
        else:
            return 3600        # 1 hour for stable lineage
    
    async def invalidate_for_capsule(self, capsule_id: str) -> int:
        """
        Invalidate all cache entries affected by a capsule change.
        
        Returns count of invalidated entries.
        """
        triggers = self._invalidation_subscriptions.get(capsule_id, set())
        if not triggers:
            return 0
        
        # Delete all affected cache keys
        pipeline = self._redis.pipeline()
        for cache_key in triggers:
            pipeline.delete(cache_key)
        await pipeline.execute()
        
        # Clean up subscription tracking
        del self._invalidation_subscriptions[capsule_id]
        
        return len(triggers)
```

### 2.4 Materialized Lineage Views

#### 2.4.1 Concept

For capsules with deep lineage chains (>5 generations) that are frequently queried, Forge pre-computes and stores "materialized views" of the complete ancestry. These views update asynchronously when any capsule in the chain changes.

```cypher
// Materialized lineage view node
CREATE (mlv:MaterializedLineageView {
    id: randomUUID(),
    root_capsule_id: String,         // The capsule this view represents
    lineage_depth: Integer,          // How many generations are materialized
    capsule_ids: [String],           // Ordered list of ancestor IDs
    trust_chain: [Integer],          // Trust levels at each generation
    total_generations: Integer,
    created_at: DateTime,
    last_refreshed: DateTime,
    refresh_status: String,          // 'current' | 'stale' | 'refreshing'
    staleness_trigger_ids: [String]  // Capsule IDs that would invalidate this view
})

// Index for efficient lookup
CREATE INDEX materialized_lineage_root 
FOR (mlv:MaterializedLineageView) 
ON (mlv.root_capsule_id)
```

#### 2.4.2 Refresh Strategy

Materialized views refresh through an event-driven background process.

```python
class MaterializedLineageManager:
    """
    Manages pre-computed lineage views for frequently accessed capsules.
    
    Views are created on-demand when a capsule's lineage is queried
    more than MATERIALIZATION_THRESHOLD times within OBSERVATION_WINDOW.
    Once created, views refresh asynchronously when underlying data changes.
    """
    
    MATERIALIZATION_THRESHOLD = 10   # Queries before materializing
    OBSERVATION_WINDOW_HOURS = 24    # Window for counting queries
    MAX_MATERIALIZED_DEPTH = 20      # Don't materialize beyond this
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        event_bus: EventBus,
        cache: QueryCache
    ):
        self._neo4j = neo4j_client
        self._event_bus = event_bus
        self._cache = cache
        self._query_counts: dict[str, list[datetime]] = defaultdict(list)
        
        # Subscribe to capsule change events
        self._event_bus.subscribe(
            event_types={EventType.CAPSULE_UPDATED, EventType.CAPSULE_CREATED},
            handler=self._handle_capsule_change
        )
    
    async def get_lineage_with_materialization(
        self,
        capsule_id: str,
        max_depth: int = 10
    ) -> LineageTree:
        """
        Retrieve lineage, using materialized view if available.
        
        Also tracks query frequency to identify candidates for
        future materialization.
        """
        # Record this query for materialization analysis
        self._record_query(capsule_id)
        
        # Check for existing materialized view
        view = await self._get_materialized_view(capsule_id)
        if view and view.refresh_status == 'current':
            return self._view_to_lineage_tree(view)
        
        # Fall back to live query
        lineage = await self._query_live_lineage(capsule_id, max_depth)
        
        # Check if we should materialize this lineage
        if self._should_materialize(capsule_id, lineage):
            await self._create_materialized_view(capsule_id, lineage)
        
        return lineage
    
    def _should_materialize(
        self,
        capsule_id: str,
        lineage: LineageTree
    ) -> bool:
        """
        Determine if a lineage should be materialized.
        
        Criteria:
        1. Query count exceeds threshold within observation window
        2. Lineage depth is >= 5 (shallow lineage doesn't benefit)
        3. Lineage depth doesn't exceed maximum
        4. View doesn't already exist
        """
        # Count recent queries
        recent_queries = [
            ts for ts in self._query_counts[capsule_id]
            if ts > datetime.utcnow() - timedelta(hours=self.OBSERVATION_WINDOW_HOURS)
        ]
        
        if len(recent_queries) < self.MATERIALIZATION_THRESHOLD:
            return False
        
        if lineage.depth < 5:
            return False
        
        if lineage.depth > self.MAX_MATERIALIZED_DEPTH:
            return False
        
        return True
    
    async def _handle_capsule_change(self, event: Event) -> None:
        """
        Handle capsule changes by marking affected views as stale.
        
        Stale views are refreshed by the background refresh worker.
        """
        capsule_id = event.payload.get("capsule_id")
        
        # Find all views that include this capsule in their lineage
        query = """
        MATCH (mlv:MaterializedLineageView)
        WHERE $capsule_id IN mlv.staleness_trigger_ids
        SET mlv.refresh_status = 'stale'
        RETURN mlv.id as view_id
        """
        
        result = await self._neo4j.execute_query(
            query,
            {"capsule_id": capsule_id}
        )
        
        stale_count = len(result)
        if stale_count > 0:
            logger.info(
                f"Marked {stale_count} materialized views as stale",
                trigger_capsule=capsule_id
            )
            
            # Emit event for background refresh worker
            await self._event_bus.publish(Event(
                event_type=EventType.LINEAGE_VIEW_STALE,
                payload={"view_ids": [r["view_id"] for r in result]}
            ))
```

### 2.5 Performance Monitoring

The Graph Performance Optimization Layer exposes the following metrics for monitoring and alerting.

```python
class GraphPerformanceMetrics:
    """
    Prometheus metrics for graph performance monitoring.
    
    These metrics enable alerting on performance degradation
    and capacity planning for graph scaling.
    """
    
    # Query latency histogram by operation type
    query_latency = Histogram(
        'forge_graph_query_latency_seconds',
        'Graph query latency in seconds',
        ['operation', 'partition', 'cache_status'],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    
    # Partition statistics
    partition_capsule_count = Gauge(
        'forge_partition_capsule_count',
        'Number of capsules in each partition',
        ['partition_id', 'partition_name']
    )
    
    partition_edge_density = Gauge(
        'forge_partition_edge_density',
        'Edge density (edges / possible edges) per partition',
        ['partition_id']
    )
    
    # Cache effectiveness
    cache_hit_rate = Gauge(
        'forge_cache_hit_rate',
        'Cache hit rate by query type',
        ['query_type']
    )
    
    cache_invalidations = Counter(
        'forge_cache_invalidations_total',
        'Total cache invalidations',
        ['reason']
    )
    
    # Materialized view statistics
    materialized_views_total = Gauge(
        'forge_materialized_views_total',
        'Total number of materialized lineage views'
    )
    
    materialized_view_staleness = Gauge(
        'forge_materialized_views_stale',
        'Number of stale materialized views pending refresh'
    )
    
    # Cross-partition query tracking
    cross_partition_queries = Counter(
        'forge_cross_partition_queries_total',
        'Queries spanning multiple partitions'
    )
```

---

## 3. Lineage Storage Efficiency System

### 3.1 Problem Statement

Full lineage tracking requires storing timestamps, derivation reasons, content diffs, and confidence scores on every DERIVED_FROM relationship. At scale, this adds 10-30% storage overhead. Organizations with millions of capsules need strategies to manage this cost without sacrificing audit trail integrity.

### 3.2 Tiered Lineage Detail

#### 3.2.1 Lineage Tiers

Forge implements three tiers of lineage detail, with automatic tier assignment based on capsule age and trust level.

**Tier 1 - Full Detail:** Complete lineage information including full content diffs, derivation reasoning, and all metadata. Applied to capsules created within the last 30 days or with trust level >= TRUSTED (80).

**Tier 2 - Compressed Detail:** Parent reference, timestamp, and change summary (not full diff). Derivation reason compressed to category tag. Applied to capsules 30-180 days old with trust level >= STANDARD (60).

**Tier 3 - Archival Reference:** Parent reference and timestamp only. Full details retrievable on-demand from cold storage. Applied to capsules older than 180 days or with trust level < STANDARD.

```python
@dataclass
class LineageTierConfig:
    """Configuration for lineage storage tiers."""
    
    # Tier boundaries
    tier1_max_age_days: int = 30
    tier2_max_age_days: int = 180
    
    tier1_min_trust: TrustLevel = TrustLevel.TRUSTED
    tier2_min_trust: TrustLevel = TrustLevel.STANDARD
    
    # Storage locations
    hot_storage: str = "neo4j"           # Tier 1
    warm_storage: str = "neo4j"          # Tier 2 (same DB, compressed)
    cold_storage: str = "s3"             # Tier 3 archive


class LineageTierManager:
    """
    Manages tiered storage of lineage information.
    
    Automatically migrates lineage data between tiers based on
    age and trust level, while ensuring full lineage remains
    reconstructable on demand.
    """
    
    def __init__(
        self,
        config: LineageTierConfig,
        neo4j_client: Neo4jClient,
        cold_storage_client: S3Client
    ):
        self._config = config
        self._neo4j = neo4j_client
        self._cold_storage = cold_storage_client
    
    def determine_tier(self, capsule: Capsule) -> int:
        """
        Determine appropriate lineage tier for a capsule.
        
        Higher tiers (1) retain more detail; lower tiers (3) compress.
        """
        age_days = (datetime.utcnow() - capsule.created_at).days
        
        # Tier 1: Recent or high-trust capsules
        if age_days <= self._config.tier1_max_age_days:
            return 1
        if capsule.trust_level >= self._config.tier1_min_trust:
            return 1
        
        # Tier 2: Moderate age and trust
        if age_days <= self._config.tier2_max_age_days:
            if capsule.trust_level >= self._config.tier2_min_trust:
                return 2
        
        # Tier 3: Old or low-trust capsules
        return 3
    
    async def store_lineage(
        self,
        child_capsule: Capsule,
        parent_capsule: Capsule,
        derivation: DerivationInfo
    ) -> None:
        """
        Store lineage information at appropriate tier.
        
        New lineage always starts at Tier 1; the background
        migration worker demotes to lower tiers over time.
        """
        tier = self.determine_tier(child_capsule)
        
        if tier == 1:
            await self._store_tier1_lineage(
                child_capsule, parent_capsule, derivation
            )
        elif tier == 2:
            await self._store_tier2_lineage(
                child_capsule, parent_capsule, derivation
            )
        else:
            await self._store_tier3_lineage(
                child_capsule, parent_capsule, derivation
            )
    
    async def _store_tier1_lineage(
        self,
        child: Capsule,
        parent: Capsule,
        derivation: DerivationInfo
    ) -> None:
        """
        Store full-detail lineage in Neo4j.
        
        Includes complete content diff, full derivation reasoning,
        and all metadata fields.
        """
        query = """
        MATCH (child:Capsule {id: $child_id})
        MATCH (parent:Capsule {id: $parent_id})
        CREATE (child)-[:DERIVED_FROM {
            timestamp: datetime($timestamp),
            reason: $reason,
            reason_category: $reason_category,
            changes: $changes,
            change_summary: $change_summary,
            confidence: $confidence,
            derivation_method: $derivation_method,
            context_snapshot: $context_snapshot,
            lineage_tier: 1
        }]->(parent)
        """
        
        await self._neo4j.execute_query(query, {
            "child_id": child.id,
            "parent_id": parent.id,
            "timestamp": derivation.timestamp.isoformat(),
            "reason": derivation.reason,
            "reason_category": self._categorize_reason(derivation.reason),
            "changes": derivation.diff.to_json(),
            "change_summary": derivation.diff.summarize(),
            "confidence": derivation.confidence,
            "derivation_method": derivation.method,
            "context_snapshot": derivation.context[:1000]  # Truncate context
        })
    
    async def _store_tier2_lineage(
        self,
        child: Capsule,
        parent: Capsule,
        derivation: DerivationInfo
    ) -> None:
        """
        Store compressed lineage in Neo4j.
        
        Omits full diff; stores only change summary and category.
        Full details archived to cold storage with reference pointer.
        """
        # Archive full details to cold storage
        archive_key = f"lineage/{child.id}/{parent.id}/{derivation.timestamp.isoformat()}"
        await self._cold_storage.put_json(
            key=archive_key,
            data=derivation.to_dict()
        )
        
        # Store compressed reference in Neo4j
        query = """
        MATCH (child:Capsule {id: $child_id})
        MATCH (parent:Capsule {id: $parent_id})
        CREATE (child)-[:DERIVED_FROM {
            timestamp: datetime($timestamp),
            reason_category: $reason_category,
            change_summary: $change_summary,
            confidence: $confidence,
            archive_key: $archive_key,
            lineage_tier: 2
        }]->(parent)
        """
        
        await self._neo4j.execute_query(query, {
            "child_id": child.id,
            "parent_id": parent.id,
            "timestamp": derivation.timestamp.isoformat(),
            "reason_category": self._categorize_reason(derivation.reason),
            "change_summary": derivation.diff.summarize(),
            "confidence": derivation.confidence,
            "archive_key": archive_key
        })
    
    async def retrieve_full_lineage_details(
        self,
        child_id: str,
        parent_id: str
    ) -> DerivationInfo:
        """
        Retrieve full lineage details, fetching from archive if needed.
        
        This method transparently handles tier differences, always
        returning complete derivation information regardless of
        storage tier.
        """
        # First check Neo4j for tier info
        query = """
        MATCH (child:Capsule {id: $child_id})
              -[r:DERIVED_FROM]->(parent:Capsule {id: $parent_id})
        RETURN r.lineage_tier as tier,
               r.archive_key as archive_key,
               properties(r) as props
        """
        
        result = await self._neo4j.execute_query(query, {
            "child_id": child_id,
            "parent_id": parent_id
        })
        
        if not result:
            raise LineageNotFoundError(child_id, parent_id)
        
        tier = result[0]["tier"]
        props = result[0]["props"]
        
        if tier == 1:
            # Full details available in Neo4j
            return DerivationInfo.from_neo4j_properties(props)
        
        elif tier in (2, 3):
            # Fetch from cold storage
            archive_key = result[0]["archive_key"]
            archived_data = await self._cold_storage.get_json(archive_key)
            return DerivationInfo.from_dict(archived_data)
```

### 3.3 Delta-Based Diff Storage

#### 3.3.1 JSON Patch Format

Instead of storing complete before/after content snapshots, Forge stores diffs in RFC 6902 JSON Patch format, reducing storage for small changes by 80-95%.

```python
class LineageDiff:
    """
    Represents changes between parent and child capsule content.
    
    Uses JSON Patch format for efficient storage of incremental
    changes, with fallback to full snapshot for large changes.
    """
    
    # If patch is larger than this percentage of full content, store snapshot
    PATCH_EFFICIENCY_THRESHOLD = 0.5
    
    @classmethod
    def compute(cls, parent_content: str, child_content: str) -> 'LineageDiff':
        """
        Compute the most efficient diff representation.
        
        For small changes, JSON Patch is dramatically smaller.
        For large rewrites, a full snapshot may be more efficient.
        """
        # Parse content as JSON if possible, otherwise treat as text
        try:
            parent_json = json.loads(parent_content)
            child_json = json.loads(child_content)
            patch = jsonpatch.make_patch(parent_json, child_json)
            patch_str = patch.to_string()
        except json.JSONDecodeError:
            # Text content: use unified diff
            diff_lines = list(difflib.unified_diff(
                parent_content.splitlines(),
                child_content.splitlines(),
                lineterm=''
            ))
            patch_str = '\n'.join(diff_lines)
        
        # Check efficiency
        patch_size = len(patch_str.encode('utf-8'))
        full_size = len(child_content.encode('utf-8'))
        
        if patch_size < full_size * cls.PATCH_EFFICIENCY_THRESHOLD:
            return cls(
                diff_type='patch',
                data=patch_str,
                original_size=len(parent_content),
                new_size=len(child_content)
            )
        else:
            return cls(
                diff_type='snapshot',
                data=child_content,
                original_size=len(parent_content),
                new_size=len(child_content)
            )
    
    def apply(self, parent_content: str) -> str:
        """
        Apply this diff to parent content to reconstruct child content.
        """
        if self.diff_type == 'snapshot':
            return self.data
        
        try:
            parent_json = json.loads(parent_content)
            patch = jsonpatch.JsonPatch.from_string(self.data)
            result = patch.apply(parent_json)
            return json.dumps(result)
        except json.JSONDecodeError:
            # Text diff: apply unified diff
            return self._apply_unified_diff(parent_content, self.data)
    
    def summarize(self) -> str:
        """
        Generate a human-readable summary of changes.
        
        Used for Tier 2 storage where full diff is archived.
        """
        if self.diff_type == 'snapshot':
            size_change = self.new_size - self.original_size
            return f"Complete rewrite ({size_change:+d} bytes)"
        
        # Count operations in patch
        if self.data.startswith('['):
            # JSON Patch
            ops = json.loads(self.data)
            op_counts = Counter(op['op'] for op in ops)
            parts = []
            if op_counts.get('add'):
                parts.append(f"{op_counts['add']} additions")
            if op_counts.get('remove'):
                parts.append(f"{op_counts['remove']} removals")
            if op_counts.get('replace'):
                parts.append(f"{op_counts['replace']} modifications")
            return ', '.join(parts) if parts else "No changes"
        else:
            # Unified diff
            additions = self.data.count('\n+') - self.data.count('\n+++')
            deletions = self.data.count('\n-') - self.data.count('\n---')
            return f"+{additions}/-{deletions} lines"
```

### 3.4 Lineage Compression Background Worker

A background worker periodically migrates lineage data to appropriate tiers as capsules age.

```python
class LineageTierMigrationWorker:
    """
    Background worker that migrates lineage data between storage tiers.
    
    Runs periodically to identify lineage relationships that should
    be demoted to lower tiers based on age and trust level changes.
    """
    
    def __init__(
        self,
        tier_manager: LineageTierManager,
        config: LineageTierConfig
    ):
        self._tier_manager = tier_manager
        self._config = config
        self._running = False
    
    async def run_migration_cycle(self) -> MigrationReport:
        """
        Execute one migration cycle.
        
        Identifies candidates for tier demotion and migrates them
        while preserving data integrity.
        """
        report = MigrationReport()
        
        # Find Tier 1 candidates for demotion to Tier 2
        tier1_candidates = await self._find_tier1_demotion_candidates()
        for candidate in tier1_candidates:
            try:
                await self._demote_to_tier2(candidate)
                report.tier1_to_tier2 += 1
            except Exception as e:
                report.errors.append(f"Tier1->2 failed for {candidate.id}: {e}")
        
        # Find Tier 2 candidates for demotion to Tier 3
        tier2_candidates = await self._find_tier2_demotion_candidates()
        for candidate in tier2_candidates:
            try:
                await self._demote_to_tier3(candidate)
                report.tier2_to_tier3 += 1
            except Exception as e:
                report.errors.append(f"Tier2->3 failed for {candidate.id}: {e}")
        
        # Calculate storage savings
        report.bytes_saved = await self._calculate_savings()
        
        return report
    
    async def _find_tier1_demotion_candidates(self) -> list[LineageRelationship]:
        """
        Find Tier 1 lineage relationships eligible for demotion.
        
        Criteria:
        - Currently Tier 1
        - Capsule age > tier1_max_age_days
        - Capsule trust_level < tier1_min_trust
        """
        query = """
        MATCH (child:Capsule)-[r:DERIVED_FROM {lineage_tier: 1}]->(parent:Capsule)
        WHERE child.created_at < datetime() - duration({days: $max_age})
          AND child.trust_level < $min_trust
        RETURN child.id as child_id, 
               parent.id as parent_id,
               r as relationship
        LIMIT 1000
        """
        
        result = await self._tier_manager._neo4j.execute_query(query, {
            "max_age": self._config.tier1_max_age_days,
            "min_trust": self._config.tier1_min_trust.value
        })
        
        return [LineageRelationship.from_result(r) for r in result]
```

---

## 4. Operational Resilience Framework

### 4.1 Problem Statement

Forge's seven-phase pipeline, multiple overlays, governance systems, and immune systems create significant operational complexity. Organizations deploying Forge need comprehensive observability, documented recovery procedures, and automated incident response.

### 4.2 Observability Stack Integration

#### 4.2.1 OpenTelemetry Instrumentation

Every Forge component exports traces, metrics, and logs through OpenTelemetry.

```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter


class ForgeObservability:
    """
    Centralized observability configuration for Forge.
    
    Provides tracing, metrics, and structured logging that correlate
    across the entire request lifecycle.
    """
    
    def __init__(self, config: ObservabilityConfig):
        self._config = config
        self._tracer = None
        self._meter = None
        
    def initialize(self) -> None:
        """Initialize OpenTelemetry exporters and providers."""
        # Tracing
        trace_provider = TracerProvider(
            resource=Resource.create({
                "service.name": "forge-cascade",
                "service.version": self._config.version,
                "deployment.environment": self._config.environment
            })
        )
        trace_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(
                endpoint=self._config.otlp_endpoint
            ))
        )
        trace.set_tracer_provider(trace_provider)
        self._tracer = trace.get_tracer("forge.cascade")
        
        # Metrics
        metric_provider = MeterProvider(
            resource=Resource.create({
                "service.name": "forge-cascade"
            }),
            metric_readers=[
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=self._config.otlp_endpoint),
                    export_interval_millis=10000
                )
            ]
        )
        metrics.set_meter_provider(metric_provider)
        self._meter = metrics.get_meter("forge.cascade")
    
    def create_pipeline_span(
        self,
        request_id: str,
        phase: PipelinePhase
    ) -> trace.Span:
        """
        Create a span for pipeline phase execution.
        
        Links to parent request span and includes phase-specific
        attributes for debugging.
        """
        return self._tracer.start_span(
            name=f"pipeline.{phase.value}",
            attributes={
                "forge.request_id": request_id,
                "forge.pipeline.phase": phase.value,
                "forge.pipeline.phase_number": phase.order
            }
        )


class PipelineInstrumentation:
    """
    Automatic instrumentation for the seven-phase pipeline.
    
    Wraps each phase execution with tracing and metrics collection.
    """
    
    def __init__(self, observability: ForgeObservability):
        self._obs = observability
        
        # Phase latency histogram
        self._phase_duration = observability._meter.create_histogram(
            name="forge.pipeline.phase.duration",
            description="Duration of each pipeline phase",
            unit="ms"
        )
        
        # Phase success/failure counter
        self._phase_outcomes = observability._meter.create_counter(
            name="forge.pipeline.phase.outcomes",
            description="Outcome counts by phase"
        )
    
    async def execute_phase_with_instrumentation(
        self,
        phase: PipelinePhase,
        context: PipelineContext,
        execute_func: Callable
    ) -> PhaseResult:
        """
        Execute a pipeline phase with full instrumentation.
        
        Creates a trace span, records timing metrics, and captures
        any errors for debugging.
        """
        with self._obs.create_pipeline_span(context.request_id, phase) as span:
            start_time = time.perf_counter()
            
            try:
                result = await execute_func()
                
                # Record success
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._phase_duration.record(
                    duration_ms,
                    {"phase": phase.value, "status": "success"}
                )
                self._phase_outcomes.add(
                    1,
                    {"phase": phase.value, "outcome": "success"}
                )
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                span.set_attribute("forge.phase.duration_ms", duration_ms)
                
                return result
                
            except Exception as e:
                # Record failure
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._phase_duration.record(
                    duration_ms,
                    {"phase": phase.value, "status": "error"}
                )
                self._phase_outcomes.add(
                    1,
                    {"phase": phase.value, "outcome": "error"}
                )
                
                span.set_status(trace.Status(
                    trace.StatusCode.ERROR,
                    description=str(e)
                ))
                span.record_exception(e)
                
                raise
```

### 4.3 Runbook System

#### 4.3.1 Automated Runbook Structure

Forge includes machine-readable runbooks that integrate with incident management systems.

```python
@dataclass
class Runbook:
    """
    Structured runbook for operational procedures.
    
    Runbooks are both human-readable documentation and machine-executable
    procedure definitions that can be triggered automatically.
    """
    
    id: str
    title: str
    description: str
    trigger_conditions: list[TriggerCondition]
    severity: Severity
    steps: list[RunbookStep]
    escalation_path: list[EscalationLevel]
    estimated_resolution_time: timedelta
    
    def evaluate_triggers(self, alert: Alert) -> bool:
        """Check if this runbook applies to the given alert."""
        return any(
            condition.matches(alert) 
            for condition in self.trigger_conditions
        )


@dataclass
class RunbookStep:
    """
    Individual step in a runbook procedure.
    
    Steps can be manual (require human action) or automated
    (execute programmatically).
    """
    
    order: int
    title: str
    description: str
    step_type: Literal["manual", "automated", "decision"]
    
    # For automated steps
    automation_script: Optional[str] = None
    automation_params: dict = field(default_factory=dict)
    
    # For decision steps
    decision_options: list[DecisionOption] = field(default_factory=list)
    
    # Verification
    verification_query: Optional[str] = None
    expected_result: Optional[Any] = None


# Example runbook definition
CIRCUIT_BREAKER_TRIP_RUNBOOK = Runbook(
    id="RB-001",
    title="Circuit Breaker Trip Recovery",
    description="""
    Procedure for recovering when an overlay's circuit breaker trips,
    indicating repeated failures that have triggered isolation.
    """,
    trigger_conditions=[
        TriggerCondition(
            metric="forge_circuit_breaker_state",
            operator="==",
            value="open"
        )
    ],
    severity=Severity.HIGH,
    steps=[
        RunbookStep(
            order=1,
            title="Identify Affected Overlay",
            description="Determine which overlay triggered the circuit breaker",
            step_type="automated",
            automation_script="scripts/runbooks/identify_tripped_breaker.py",
            verification_query="SELECT overlay_name FROM circuit_breakers WHERE state = 'open'"
        ),
        RunbookStep(
            order=2,
            title="Check Dependency Health",
            description="Verify that upstream dependencies (Neo4j, Redis) are healthy",
            step_type="automated",
            automation_script="scripts/runbooks/check_dependencies.py",
            verification_query="GET /api/v1/system/health"
        ),
        RunbookStep(
            order=3,
            title="Review Recent Errors",
            description="Examine error logs for the affected overlay",
            step_type="automated",
            automation_script="scripts/runbooks/fetch_overlay_errors.py",
            automation_params={"time_range": "15m", "limit": 100}
        ),
        RunbookStep(
            order=4,
            title="Determine Recovery Action",
            description="Based on error patterns, choose recovery approach",
            step_type="decision",
            decision_options=[
                DecisionOption(
                    label="Dependency Issue",
                    description="Upstream service failure; wait for recovery",
                    next_step=5
                ),
                DecisionOption(
                    label="Overlay Bug",
                    description="Overlay code issue; disable and investigate",
                    next_step=6
                ),
                DecisionOption(
                    label="Transient Error",
                    description="Temporary issue resolved; force reset",
                    next_step=7
                )
            ]
        ),
        RunbookStep(
            order=5,
            title="Wait for Dependency Recovery",
            description="Monitor upstream service; breaker will auto-reset when healthy",
            step_type="manual",
            verification_query="GET /api/v1/overlays/{overlay_id}/health"
        ),
        RunbookStep(
            order=6,
            title="Disable Overlay for Investigation",
            description="Disable the overlay to prevent further cascading failures",
            step_type="automated",
            automation_script="scripts/runbooks/disable_overlay.py"
        ),
        RunbookStep(
            order=7,
            title="Force Circuit Breaker Reset",
            description="Manually reset the circuit breaker to half-open state",
            step_type="automated",
            automation_script="scripts/runbooks/reset_circuit_breaker.py",
            verification_query="SELECT state FROM circuit_breakers WHERE overlay_id = $overlay_id"
        )
    ],
    escalation_path=[
        EscalationLevel(
            level=1,
            notify=["on-call-engineer"],
            after_minutes=0
        ),
        EscalationLevel(
            level=2,
            notify=["engineering-lead"],
            after_minutes=15
        ),
        EscalationLevel(
            level=3,
            notify=["vp-engineering"],
            after_minutes=60
        )
    ],
    estimated_resolution_time=timedelta(minutes=30)
)
```

### 4.4 Failure Mode Catalog

Forge documents all known failure modes with detection signatures and recovery procedures.

```yaml
# failure_modes.yaml
failure_modes:
  - id: FM-001
    name: Neo4j Connection Pool Exhaustion
    description: |
      All connections in the Neo4j pool are in use, causing new
      queries to timeout waiting for available connections.
    detection:
      metrics:
        - name: neo4j_pool_available_connections
          condition: "== 0"
          duration: "30s"
      logs:
        - pattern: "ConnectionPoolTimeout"
    impact:
      - All capsule operations blocked
      - Pipeline phases 1, 2, 7 fail
      - Health checks report degraded
    root_causes:
      - Long-running queries holding connections
      - Connection leak in application code
      - Neo4j server overloaded
    recovery:
      runbook: RB-002
      immediate_actions:
        - Increase pool size temporarily
        - Kill long-running queries
      long_term_fixes:
        - Add query timeouts
        - Implement connection leak detection
        - Scale Neo4j cluster

  - id: FM-002
    name: Cascade Storm
    description: |
      A single event triggers an exponentially growing cascade
      of secondary events, overwhelming the event system.
    detection:
      metrics:
        - name: forge_events_published_rate
          condition: "> 1000/s"
          duration: "10s"
        - name: forge_event_queue_depth
          condition: "> 5000"
    impact:
      - Event delivery delays
      - Memory pressure from queue growth
      - Secondary service overload
    root_causes:
      - Circular cascade dependency
      - Missing cascade depth limit
      - Overlay publishing to own subscribed events
    recovery:
      runbook: RB-003
      immediate_actions:
        - Enable cascade circuit breaker
        - Purge event queue
        - Disable triggering overlay
      long_term_fixes:
        - Implement cascade depth limits
        - Add circular dependency detection
        - Review overlay event contracts

  - id: FM-003
    name: Trust Level Cascade Collapse
    description: |
      A compromised or buggy capsule causes trust degradation
      that propagates through lineage, affecting healthy capsules.
    detection:
      metrics:
        - name: forge_capsules_quarantined_rate
          condition: "> 10/min"
          duration: "5m"
      logs:
        - pattern: "TrustDegradation.*propagated"
    impact:
      - Valid capsules incorrectly quarantined
      - Knowledge access disrupted
      - Governance proposals blocked
    root_causes:
      - Aggressive trust propagation rules
      - Single compromised root capsule
      - Trust calculation bug
    recovery:
      runbook: RB-004
      immediate_actions:
        - Pause trust propagation
        - Identify patient zero capsule
        - Snapshot current trust state
      long_term_fixes:
        - Implement trust propagation damping
        - Add trust restoration procedures
        - Limit single-capsule trust impact radius
```

---

## 5. Cold Start Mitigation System

### 5.1 Problem Statement

New Forge deployments have no capsules, no learned patterns, and no institutional memory. Users receive no value until knowledge accumulates. This "cold start" problem delays time-to-value and hinders adoption.

### 5.2 Knowledge Starter Packs

#### 5.2.1 Starter Pack Schema

Curated collections of foundational capsules that new deployments can import.

```cypher
// Starter pack metadata
CREATE (sp:StarterPack {
    id: randomUUID(),
    name: String,                    // "Security Best Practices"
    description: String,
    domain: String,                  // Primary domain classification
    version: String,                 // Semantic version
    capsule_count: Integer,
    total_size_bytes: Integer,
    created_by: String,              // Organization that created pack
    license: String,                 // Usage license
    compatibility_version: String,   // Minimum Forge version required
    created_at: DateTime,
    updated_at: DateTime,
    download_count: Integer,
    rating: Float                    // Community rating 0-5
})

// Capsules included in starter pack
CREATE (sp:StarterPack)-[:INCLUDES {
    import_order: Integer,           // Order for import dependencies
    optional: Boolean                // Whether capsule can be skipped
}]->(c:Capsule)

// Dependencies between starter packs
CREATE (sp1:StarterPack)-[:DEPENDS_ON {
    min_version: String
}]->(sp2:StarterPack)
```

#### 5.2.2 Starter Pack Import System

```python
class StarterPackManager:
    """
    Manages import and export of knowledge starter packs.
    
    Starter packs allow organizations to bootstrap new Forge
    deployments with curated foundational knowledge.
    """
    
    REGISTRY_URL = "https://registry.forgeecosystem.io/packs"
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        capsule_repository: CapsuleRepository
    ):
        self._neo4j = neo4j_client
        self._capsule_repo = capsule_repository
    
    async def list_available_packs(
        self,
        domain: Optional[str] = None,
        min_rating: float = 0.0
    ) -> list[StarterPackInfo]:
        """
        List starter packs available from the registry.
        
        Can filter by domain and minimum community rating.
        """
        params = {"min_rating": min_rating}
        if domain:
            params["domain"] = domain
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.REGISTRY_URL}/list",
                params=params
            ) as response:
                data = await response.json()
                return [StarterPackInfo(**pack) for pack in data["packs"]]
    
    async def import_pack(
        self,
        pack_id: str,
        options: ImportOptions = None
    ) -> ImportReport:
        """
        Import a starter pack into this Forge instance.
        
        Handles dependency resolution, capsule creation, and
        lineage establishment. Existing capsules with matching
        IDs are skipped unless force_update is specified.
        """
        options = options or ImportOptions()
        report = ImportReport(pack_id=pack_id)
        
        # Download pack manifest
        manifest = await self._download_manifest(pack_id)
        report.pack_name = manifest.name
        report.total_capsules = manifest.capsule_count
        
        # Check and import dependencies first
        for dep in manifest.dependencies:
            if not await self._is_pack_installed(dep.pack_id):
                logger.info(f"Installing dependency: {dep.pack_id}")
                dep_report = await self.import_pack(
                    dep.pack_id,
                    options.for_dependency()
                )
                report.dependency_reports.append(dep_report)
        
        # Download and import capsules
        capsules = await self._download_pack_capsules(pack_id)
        
        for capsule_data in capsules:
            try:
                # Check if capsule already exists
                existing = await self._capsule_repo.get_by_id(capsule_data["id"])
                
                if existing and not options.force_update:
                    report.skipped += 1
                    continue
                
                # Create capsule with starter pack provenance
                capsule = Capsule(
                    **capsule_data,
                    metadata={
                        **capsule_data.get("metadata", {}),
                        "source": "starter_pack",
                        "source_pack_id": pack_id,
                        "imported_at": datetime.utcnow().isoformat()
                    }
                )
                
                await self._capsule_repo.create(capsule)
                report.imported += 1
                
            except Exception as e:
                report.errors.append(f"Failed to import {capsule_data['id']}: {e}")
        
        # Re-establish lineage relationships
        await self._restore_lineage(pack_id, manifest.lineage_map)
        
        # Mark pack as installed
        await self._mark_pack_installed(pack_id, manifest.version)
        
        return report
    
    async def export_pack(
        self,
        name: str,
        description: str,
        capsule_ids: list[str],
        include_lineage: bool = True
    ) -> ExportedPack:
        """
        Export selected capsules as a reusable starter pack.
        
        Automatically includes lineage ancestors up to the
        specified depth to maintain knowledge coherence.
        """
        export = ExportedPack(
            name=name,
            description=description,
            version="1.0.0",
            created_at=datetime.utcnow()
        )
        
        # Collect capsules and their lineage
        all_capsule_ids = set(capsule_ids)
        
        if include_lineage:
            for cid in capsule_ids:
                ancestors = await self._capsule_repo.get_ancestors(cid, max_depth=10)
                all_capsule_ids.update(a.id for a in ancestors)
        
        # Export capsule data
        for cid in all_capsule_ids:
            capsule = await self._capsule_repo.get_by_id(cid)
            export.capsules.append(capsule.to_export_dict())
        
        # Export lineage map
        export.lineage_map = await self._build_lineage_map(all_capsule_ids)
        
        return export


@dataclass
class ImportOptions:
    """Options for starter pack import."""
    
    force_update: bool = False       # Overwrite existing capsules
    skip_dependencies: bool = False  # Don't auto-import dependencies
    trust_level_override: Optional[TrustLevel] = None  # Override imported trust
    target_partition: Optional[str] = None  # Import to specific partition
    
    def for_dependency(self) -> 'ImportOptions':
        """Create options suitable for dependency imports."""
        return ImportOptions(
            force_update=False,
            skip_dependencies=False,
            trust_level_override=self.trust_level_override,
            target_partition=self.target_partition
        )
```

### 5.3 Progressive Profiling

#### 5.3.1 User Behavior Learning

The ML Intelligence overlay learns user patterns from early interactions to accelerate personalization.

```python
class ProgressiveProfiler:
    """
    Builds user profiles progressively from interaction patterns.
    
    Rather than requiring explicit configuration, the profiler
    learns preferences, expertise areas, and common queries
    from natural usage patterns.
    """
    
    # Minimum interactions before profile stabilizes
    PROFILE_STABILIZATION_THRESHOLD = 50
    
    def __init__(
        self,
        ml_overlay: MLIntelligenceOverlay,
        user_repository: UserRepository
    ):
        self._ml = ml_overlay
        self._user_repo = user_repository
        self._interaction_buffer: dict[str, list[Interaction]] = defaultdict(list)
    
    async def record_interaction(
        self,
        user_id: str,
        interaction: Interaction
    ) -> ProfileUpdate:
        """
        Record a user interaction and update profile progressively.
        
        Early interactions have high learning weight; as the profile
        stabilizes, new interactions have diminishing impact.
        """
        # Buffer interaction
        self._interaction_buffer[user_id].append(interaction)
        
        # Get current profile
        profile = await self._user_repo.get_profile(user_id)
        interaction_count = profile.interaction_count + 1
        
        # Calculate learning rate (decreases as profile matures)
        learning_rate = self._calculate_learning_rate(interaction_count)
        
        # Extract signals from interaction
        signals = await self._extract_profile_signals(interaction)
        
        # Update profile with weighted signals
        updates = ProfileUpdate()
        
        # Update domain interests
        for domain, score in signals.domain_interests.items():
            current = profile.domain_interests.get(domain, 0.5)
            new_score = current + learning_rate * (score - current)
            updates.domain_interests[domain] = new_score
        
        # Update expertise indicators
        for area, indicators in signals.expertise_indicators.items():
            current_level = profile.expertise_levels.get(area, "novice")
            inferred_level = self._infer_expertise_level(indicators)
            if self._should_upgrade_expertise(current_level, inferred_level, learning_rate):
                updates.expertise_levels[area] = inferred_level
        
        # Update query patterns
        updates.query_patterns = self._update_query_patterns(
            profile.query_patterns,
            signals.query_pattern,
            learning_rate
        )
        
        # Persist updates
        await self._user_repo.update_profile(user_id, updates)
        
        return updates
    
    def _calculate_learning_rate(self, interaction_count: int) -> float:
        """
        Calculate learning rate based on profile maturity.
        
        Follows a decay curve: high initial learning (0.3) that
        decreases toward minimum (0.01) as interactions accumulate.
        """
        initial_rate = 0.3
        minimum_rate = 0.01
        decay_factor = 0.05
        
        rate = initial_rate * math.exp(-decay_factor * interaction_count)
        return max(rate, minimum_rate)
    
    async def _extract_profile_signals(
        self,
        interaction: Interaction
    ) -> ProfileSignals:
        """
        Extract learning signals from a single interaction.
        
        Uses ML classification to identify domain interests,
        query complexity to infer expertise, and patterns in
        query structure.
        """
        signals = ProfileSignals()
        
        # Classify query domain
        classification = await self._ml.classify_content(interaction.query)
        signals.domain_interests = classification.all_classes
        
        # Analyze query sophistication
        sophistication = await self._ml.analyze_query_sophistication(
            interaction.query
        )
        signals.expertise_indicators = {
            classification.primary_class: {
                "terminology_level": sophistication.terminology_score,
                "concept_complexity": sophistication.concept_depth,
                "assumed_knowledge": sophistication.assumed_prerequisites
            }
        }
        
        # Extract query pattern
        signals.query_pattern = QueryPattern(
            structure=self._classify_query_structure(interaction.query),
            typical_length=len(interaction.query.split()),
            uses_technical_terms=sophistication.terminology_score > 0.7
        )
        
        return signals
```

### 5.4 Knowledge Marketplace

#### 5.4.1 Marketplace Architecture

Organizations can share or sell curated capsule collections through a decentralized marketplace.

```python
class KnowledgeMarketplace:
    """
    Decentralized marketplace for trading knowledge assets.
    
    Integrates with Virtuals Protocol tokenization for
    pricing, licensing, and revenue distribution.
    """
    
    def __init__(
        self,
        starter_pack_manager: StarterPackManager,
        tokenization_service: TokenizationService,
        revenue_service: RevenueService
    ):
        self._packs = starter_pack_manager
        self._tokenization = tokenization_service
        self._revenue = revenue_service
    
    async def list_pack(
        self,
        pack: ExportedPack,
        listing: MarketplaceListing
    ) -> ListingResult:
        """
        List a starter pack on the marketplace.
        
        Can be free (open source), one-time purchase, or
        subscription-based licensing.
        """
        # Validate pack quality
        quality_score = await self._assess_pack_quality(pack)
        if quality_score < 0.6:
            raise PackQualityError(
                f"Pack quality score {quality_score} below minimum 0.6"
            )
        
        # Create marketplace entry
        entry = MarketplaceEntry(
            pack_id=pack.id,
            seller_id=listing.seller_id,
            name=pack.name,
            description=pack.description,
            capsule_count=len(pack.capsules),
            domains=self._extract_domains(pack),
            quality_score=quality_score,
            pricing=listing.pricing,
            license_type=listing.license_type,
            created_at=datetime.utcnow()
        )
        
        # If tokenized pricing, create token
        if listing.pricing.type == "tokenized":
            token_info = await self._tokenization.tokenize_entity(
                entity_type="capsule_collection",
                entity_id=pack.id,
                metadata={
                    "name": pack.name,
                    "capsule_count": len(pack.capsules)
                }
            )
            entry.token_address = token_info.contract_address
        
        # Register with marketplace registry
        await self._register_listing(entry)
        
        return ListingResult(
            listing_id=entry.id,
            pack_id=pack.id,
            marketplace_url=f"https://marketplace.forge.io/packs/{entry.id}"
        )
    
    async def purchase_pack(
        self,
        listing_id: str,
        buyer_id: str,
        payment: Payment
    ) -> PurchaseResult:
        """
        Purchase a starter pack from the marketplace.
        
        Handles payment processing, license generation, and
        automatic import into buyer's Forge instance.
        """
        listing = await self._get_listing(listing_id)
        
        # Process payment
        if listing.pricing.type == "free":
            payment_result = PaymentResult(status="free")
        elif listing.pricing.type == "one_time":
            payment_result = await self._process_fiat_payment(
                payment,
                listing.pricing.amount
            )
        elif listing.pricing.type == "tokenized":
            payment_result = await self._process_token_payment(
                payment,
                listing.token_address,
                listing.pricing.token_amount
            )
        
        if payment_result.status != "success" and payment_result.status != "free":
            raise PaymentFailedError(payment_result.error)
        
        # Generate license
        license = License(
            pack_id=listing.pack_id,
            licensee_id=buyer_id,
            license_type=listing.license_type,
            granted_at=datetime.utcnow(),
            expires_at=self._calculate_expiry(listing.license_type)
        )
        
        # Distribute revenue to creator
        if payment_result.amount:
            await self._revenue.distribute_pack_revenue(
                seller_id=listing.seller_id,
                amount=payment_result.amount,
                pack_id=listing.pack_id
            )
        
        # Import pack for buyer
        import_report = await self._packs.import_pack(
            listing.pack_id,
            ImportOptions(trust_level_override=TrustLevel.STANDARD)
        )
        
        return PurchaseResult(
            license=license,
            import_report=import_report
        )
```

---

## 6. Model Migration Architecture

### 6.1 Problem Statement

When embedding models or extraction models change, existing vector representations become incompatible. This is the core "ephemeral wisdom" problem. Forge's architecture must ensure knowledge survives model transitions.

### 6.2 Embedding Version Management

#### 6.2.1 Multi-Version Embedding Storage

Capsules can store embeddings from multiple model versions simultaneously during migration periods.

```cypher
// Extended capsule schema with versioned embeddings
CREATE (c:Capsule {
    id: String,
    content: String,
    // ... other properties ...
    
    // Versioned embeddings stored as separate properties
    embedding_v1: [Float],           // Legacy model
    embedding_v2: [Float],           // Current model
    embedding_v3: [Float],           // New model (during migration)
    
    // Embedding metadata
    embedding_metadata: {
        current_version: String,      // Which version is authoritative
        versions: {
            v1: {
                model: "text-embedding-ada-002",
                generated_at: DateTime,
                dimensions: 1536
            },
            v2: {
                model: "text-embedding-3-small",
                generated_at: DateTime,
                dimensions: 1536
            },
            v3: {
                model: "text-embedding-3-large",
                generated_at: DateTime,
                dimensions: 3072
            }
        },
        migration_status: String     // 'stable' | 'migrating' | 'legacy_only'
    }
})

// Separate vector indexes for each embedding version
CREATE VECTOR INDEX capsule_embeddings_v2
FOR (c:Capsule)
ON c.embedding_v2
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
}

CREATE VECTOR INDEX capsule_embeddings_v3
FOR (c:Capsule)
ON c.embedding_v3
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 3072,
        `vector.similarity_function`: 'cosine'
    }
}
```

#### 6.2.2 Background Re-Embedding Service

```python
class EmbeddingMigrationService:
    """
    Manages migration between embedding model versions.
    
    Runs as a background service that progressively re-embeds
    capsules using new models while maintaining query availability
    through the old model.
    """
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        embedding_provider: EmbeddingProvider,
        config: MigrationConfig
    ):
        self._neo4j = neo4j_client
        self._embedding = embedding_provider
        self._config = config
        self._migration_state: Optional[MigrationState] = None
    
    async def start_migration(
        self,
        from_version: str,
        to_version: str,
        to_model: str
    ) -> MigrationState:
        """
        Initiate a migration from one embedding version to another.
        
        Migration runs in background, processing capsules in batches
        while queries continue using the old version.
        """
        # Verify new model is available
        await self._embedding.verify_model(to_model)
        
        # Count capsules needing migration
        count = await self._count_capsules_needing_migration(from_version, to_version)
        
        # Create migration state
        self._migration_state = MigrationState(
            id=str(uuid4()),
            from_version=from_version,
            to_version=to_version,
            to_model=to_model,
            total_capsules=count,
            migrated_capsules=0,
            started_at=datetime.utcnow(),
            status="running"
        )
        
        # Persist migration state
        await self._save_migration_state()
        
        # Start background worker
        asyncio.create_task(self._run_migration())
        
        return self._migration_state
    
    async def _run_migration(self) -> None:
        """
        Execute migration in background.
        
        Processes capsules in batches, respecting rate limits and
        updating progress. Supports pause/resume.
        """
        batch_size = self._config.batch_size
        delay_between_batches = self._config.delay_seconds
        
        while self._migration_state.status == "running":
            # Get next batch of capsules
            capsules = await self._get_unmigrated_capsules(batch_size)
            
            if not capsules:
                # Migration complete
                self._migration_state.status = "completed"
                self._migration_state.completed_at = datetime.utcnow()
                await self._save_migration_state()
                await self._finalize_migration()
                return
            
            # Generate embeddings for batch
            contents = [c.content for c in capsules]
            embeddings = await self._embedding.embed_batch(
                contents,
                model=self._migration_state.to_model
            )
            
            # Update capsules with new embeddings
            await self._update_capsule_embeddings(
                capsules,
                embeddings,
                self._migration_state.to_version
            )
            
            # Update progress
            self._migration_state.migrated_capsules += len(capsules)
            await self._save_migration_state()
            
            # Rate limiting
            await asyncio.sleep(delay_between_batches)
    
    async def _finalize_migration(self) -> None:
        """
        Finalize migration by switching authoritative version.
        
        Updates all capsules to use new version as authoritative,
        and optionally cleans up old embeddings after grace period.
        """
        # Update authoritative version for all capsules
        query = """
        MATCH (c:Capsule)
        WHERE c.embedding_metadata.current_version = $old_version
        SET c.embedding_metadata.current_version = $new_version,
            c.embedding_metadata.migration_status = 'stable'
        """
        
        await self._neo4j.execute_query(query, {
            "old_version": self._migration_state.from_version,
            "new_version": self._migration_state.to_version
        })
        
        logger.info(
            f"Migration finalized: {self._migration_state.from_version} -> "
            f"{self._migration_state.to_version}"
        )
        
        # Schedule cleanup of old embeddings
        if self._config.cleanup_old_embeddings:
            await self._schedule_embedding_cleanup(
                self._migration_state.from_version,
                delay_days=self._config.cleanup_grace_period_days
            )
    
    async def get_query_embedding_version(self) -> str:
        """
        Determine which embedding version to use for queries.
        
        During migration, continues using old version until
        migration is 100% complete and finalized.
        """
        if self._migration_state and self._migration_state.status == "running":
            # Migration in progress: use old version for consistency
            return self._migration_state.from_version
        
        # No migration or migration complete: use current authoritative
        result = await self._neo4j.execute_query("""
            MATCH (c:Capsule)
            RETURN c.embedding_metadata.current_version as version
            LIMIT 1
        """)
        
        return result[0]["version"] if result else "v1"
```

### 6.3 Extraction Model Versioning

#### 6.3.1 Versioned Insight Tracking

When ML models that extract insights change, new extractions create new capsule versions with explicit version linkage.

```python
class ExtractionVersionManager:
    """
    Manages versioning of ML extraction outputs.
    
    When extraction models change (entity recognition, classification,
    pattern detection), new extractions create versioned capsules
    that link to their predecessors.
    """
    
    def __init__(
        self,
        capsule_repository: CapsuleRepository,
        ml_overlay: MLIntelligenceOverlay
    ):
        self._capsule_repo = capsule_repository
        self._ml = ml_overlay
        self._current_extraction_version: str = "1.0.0"
    
    async def record_extraction(
        self,
        source_content: str,
        extracted_insights: list[ExtractedInsight],
        extraction_config: ExtractionConfig
    ) -> list[Capsule]:
        """
        Record insights extracted by ML models.
        
        Each insight becomes a capsule with extraction version
        metadata. If re-extracting from same source with new
        model, creates versioned successors to previous extractions.
        """
        capsules = []
        
        for insight in extracted_insights:
            # Check for existing extraction from same source
            existing = await self._find_existing_extraction(
                source_hash=self._hash_content(source_content),
                insight_type=insight.type
            )
            
            if existing:
                # Create versioned successor
                capsule = await self._create_versioned_successor(
                    predecessor=existing,
                    new_insight=insight,
                    extraction_config=extraction_config
                )
            else:
                # Create new capsule
                capsule = Capsule(
                    id=str(uuid4()),
                    type=CapsuleType.INSIGHT,
                    content=insight.content,
                    domain=insight.domain,
                    trust_level=TrustLevel.STANDARD,
                    metadata={
                        "extraction_version": self._current_extraction_version,
                        "extraction_model": extraction_config.model_name,
                        "extraction_config": extraction_config.to_dict(),
                        "source_hash": self._hash_content(source_content),
                        "insight_type": insight.type,
                        "confidence": insight.confidence
                    }
                )
            
            await self._capsule_repo.create(capsule)
            capsules.append(capsule)
        
        return capsules
    
    async def _create_versioned_successor(
        self,
        predecessor: Capsule,
        new_insight: ExtractedInsight,
        extraction_config: ExtractionConfig
    ) -> Capsule:
        """
        Create a new capsule version that supersedes a previous extraction.
        
        The predecessor is not deleted; instead, it's marked as
        superseded and linked to its successor for lineage tracking.
        """
        # Create successor capsule
        successor = Capsule(
            id=str(uuid4()),
            type=CapsuleType.INSIGHT,
            content=new_insight.content,
            domain=new_insight.domain,
            parent_id=predecessor.id,
            trust_level=TrustLevel.STANDARD,
            metadata={
                "extraction_version": self._current_extraction_version,
                "extraction_model": extraction_config.model_name,
                "source_hash": predecessor.metadata.get("source_hash"),
                "insight_type": new_insight.type,
                "confidence": new_insight.confidence,
                "supersedes": predecessor.id,
                "supersedes_reason": "model_upgrade",
                "predecessor_extraction_version": predecessor.metadata.get(
                    "extraction_version"
                )
            }
        )
        
        # Mark predecessor as superseded
        await self._capsule_repo.update(
            predecessor.id,
            {
                "lifecycle_state": CapsuleLifecycle.SUPERSEDED,
                "superseded_by": successor.id,
                "superseded_at": datetime.utcnow().isoformat()
            }
        )
        
        return successor
    
    async def get_current_insight(
        self,
        source_hash: str,
        insight_type: str
    ) -> Optional[Capsule]:
        """
        Get the current (non-superseded) insight for a source.
        
        Traverses the supersession chain to find the latest
        extraction, regardless of how many model versions have
        been applied.
        """
        query = """
        MATCH (c:Capsule)
        WHERE c.metadata.source_hash = $source_hash
          AND c.metadata.insight_type = $insight_type
          AND c.lifecycle_state <> 'SUPERSEDED'
        RETURN c
        """
        
        result = await self._capsule_repo._neo4j.execute_query(query, {
            "source_hash": source_hash,
            "insight_type": insight_type
        })
        
        return Capsule.from_neo4j(result[0]["c"]) if result else None
```

---

## 7. Security Hardening Layer

### 7.1 Problem Statement

Persistent AI memory introduces novel attack surfaces including memory poisoning, cross-context data leakage, and the amplified impact of security breaches. Forge must implement defense-in-depth security that protects knowledge integrity without sacrificing functionality.

### 7.2 Enhanced Trust Boundary Enforcement

#### 7.2.1 Tenant Isolation

Multi-tenant deployments enforce strict isolation between organizational boundaries.

```python
class TenantIsolationEnforcer:
    """
    Enforces strict isolation between tenants in multi-tenant deployments.
    
    All database queries are automatically scoped to the current
    tenant, and cross-tenant data access is prevented at the
    infrastructure level.
    """
    
    def __init__(self, neo4j_client: Neo4jClient):
        self._neo4j = neo4j_client
    
    def create_tenant_scoped_session(
        self,
        tenant_id: str,
        user_id: str
    ) -> TenantScopedSession:
        """
        Create a database session that enforces tenant isolation.
        
        All queries executed through this session automatically
        include tenant filtering, preventing accidental or
        malicious cross-tenant access.
        """
        return TenantScopedSession(
            neo4j_client=self._neo4j,
            tenant_id=tenant_id,
            user_id=user_id,
            query_interceptor=self._create_tenant_interceptor(tenant_id)
        )
    
    def _create_tenant_interceptor(
        self,
        tenant_id: str
    ) -> QueryInterceptor:
        """
        Create a query interceptor that adds tenant filtering.
        
        This interceptor modifies Cypher queries to include
        tenant_id constraints, providing defense-in-depth
        beyond application-level filtering.
        """
        return QueryInterceptor(
            pre_execute=lambda query, params: self._add_tenant_filter(
                query, params, tenant_id
            ),
            post_execute=lambda results: self._verify_tenant_results(
                results, tenant_id
            )
        )
    
    def _add_tenant_filter(
        self,
        query: str,
        params: dict,
        tenant_id: str
    ) -> tuple[str, dict]:
        """
        Modify query to include tenant filtering.
        
        Injects tenant_id constraint into MATCH clauses and
        adds parameter for tenant filtering.
        """
        # Add tenant parameter
        params = {**params, "_tenant_id": tenant_id}
        
        # Inject tenant filter into query
        # This is a simplified example; production would use
        # proper Cypher parsing
        if "MATCH" in query.upper():
            # Add WHERE clause if not present
            if "WHERE" not in query.upper():
                query = query.replace(
                    "RETURN",
                    "WHERE n.tenant_id = $_tenant_id RETURN"
                )
            else:
                # Add to existing WHERE clause
                query = query.replace(
                    "WHERE",
                    "WHERE n.tenant_id = $_tenant_id AND"
                )
        
        return query, params


class TenantScopedSession:
    """
    Database session with automatic tenant isolation.
    
    Provides the same interface as the standard Neo4j client
    but with tenant filtering applied to all operations.
    """
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        tenant_id: str,
        user_id: str,
        query_interceptor: QueryInterceptor
    ):
        self._neo4j = neo4j_client
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._interceptor = query_interceptor
    
    async def execute_query(
        self,
        query: str,
        params: dict = None
    ) -> list[dict]:
        """
        Execute query with tenant isolation.
        """
        params = params or {}
        
        # Apply tenant filtering
        filtered_query, filtered_params = self._interceptor.pre_execute(
            query, params
        )
        
        # Execute
        results = await self._neo4j.execute_query(filtered_query, filtered_params)
        
        # Verify results
        self._interceptor.post_execute(results)
        
        return results
```

### 7.3 Content Validation Pipeline

#### 7.3.1 Injection Detection

The security_validator overlay scans content for prompt injection patterns and malicious payloads.

```python
class ContentValidator:
    """
    Validates capsule content for security threats.
    
    Detects prompt injection attempts, malicious payloads,
    and content that could corrupt system behavior.
    """
    
    # Injection patterns (simplified; production uses ML classifier)
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+.*(instructions|rules|constraints)",
        r"you\s+are\s+now\s+(?:a\s+)?(?:different|new|another)",
        r"system\s*:\s*",
        r"<\s*/?(?:system|admin|root)",
        r"\\x[0-9a-fA-F]{2}",  # Hex escape sequences
        r"base64\s*:\s*[A-Za-z0-9+/=]+",  # Base64 payloads
    ]
    
    def __init__(
        self,
        ml_overlay: MLIntelligenceOverlay,
        config: ValidationConfig
    ):
        self._ml = ml_overlay
        self._config = config
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS]
    
    async def validate_content(
        self,
        content: str,
        context: ValidationContext
    ) -> ValidationResult:
        """
        Comprehensive content validation.
        
        Combines pattern matching with ML-based anomaly detection
        to identify potentially malicious content.
        """
        result = ValidationResult(
            content_hash=self._hash_content(content),
            validated_at=datetime.utcnow()
        )
        
        # Pattern-based detection
        pattern_threats = self._detect_pattern_threats(content)
        if pattern_threats:
            result.threats.extend(pattern_threats)
        
        # ML-based anomaly detection
        anomaly_score = await self._ml.compute_anomaly_score(
            content,
            context.domain
        )
        if anomaly_score > self._config.anomaly_threshold:
            result.threats.append(Threat(
                type="anomaly",
                severity="medium",
                confidence=anomaly_score,
                description="Content anomaly detected by ML classifier"
            ))
        
        # Check for system reference attempts
        system_refs = self._detect_system_references(content)
        if system_refs:
            result.threats.append(Threat(
                type="system_reference",
                severity="high",
                confidence=0.9,
                description=f"Suspicious system references: {system_refs}"
            ))
        
        # Compute overall verdict
        result.verdict = self._compute_verdict(result.threats)
        result.should_quarantine = result.verdict == "reject"
        
        return result
    
    def _detect_pattern_threats(self, content: str) -> list[Threat]:
        """
        Detect threats using pattern matching.
        """
        threats = []
        
        for pattern in self._patterns:
            matches = pattern.findall(content)
            if matches:
                threats.append(Threat(
                    type="pattern_match",
                    severity="high",
                    confidence=0.95,
                    description=f"Injection pattern detected: {pattern.pattern}",
                    evidence=matches[:3]  # First 3 matches
                ))
        
        return threats
    
    def _detect_system_references(self, content: str) -> list[str]:
        """
        Detect attempts to reference or manipulate system internals.
        """
        system_terms = [
            "system prompt",
            "root capsule",
            "trust_level",
            "admin override",
            "governance bypass",
            "circuit breaker",
            "quarantine escape"
        ]
        
        found = []
        content_lower = content.lower()
        
        for term in system_terms:
            if term in content_lower:
                found.append(term)
        
        return found
```

### 7.4 Consent and Privacy Management

#### 7.4.1 GDPR-Compliant Memory Controls

Users control what Forge remembers about them.

```python
class PrivacyManager:
    """
    Manages user privacy preferences and GDPR compliance.
    
    Provides granular control over what information Forge
    stores about users, with full audit trail and data
    export/deletion capabilities.
    """
    
    def __init__(
        self,
        capsule_repository: CapsuleRepository,
        user_repository: UserRepository,
        audit_logger: AuditLogger
    ):
        self._capsule_repo = capsule_repository
        self._user_repo = user_repository
        self._audit = audit_logger
    
    async def update_privacy_preferences(
        self,
        user_id: str,
        preferences: PrivacyPreferences
    ) -> None:
        """
        Update user's privacy preferences.
        
        Changes take effect immediately for new data; existing
        data is processed according to retention policies.
        """
        # Log the preference change
        await self._audit.log(AuditEvent(
            event_type="privacy_preferences_updated",
            user_id=user_id,
            old_value=await self._user_repo.get_privacy_preferences(user_id),
            new_value=preferences,
            timestamp=datetime.utcnow()
        ))
        
        # Persist preferences
        await self._user_repo.update_privacy_preferences(user_id, preferences)
        
        # If user disabled persistent memory, schedule deletion
        if not preferences.allow_persistent_memory:
            await self._schedule_memory_deletion(user_id)
    
    async def process_data_subject_access_request(
        self,
        user_id: str
    ) -> DSARResponse:
        """
        Process a GDPR Data Subject Access Request.
        
        Compiles all data stored about the user into a
        portable format for export.
        """
        response = DSARResponse(
            user_id=user_id,
            request_date=datetime.utcnow()
        )
        
        # Gather user profile data
        profile = await self._user_repo.get_full_profile(user_id)
        response.profile_data = profile.to_export_dict()
        
        # Gather all user-owned capsules
        capsules = await self._capsule_repo.get_by_owner(user_id)
        response.capsules = [c.to_export_dict() for c in capsules]
        
        # Gather interaction history
        interactions = await self._user_repo.get_interaction_history(user_id)
        response.interactions = [i.to_export_dict() for i in interactions]
        
        # Gather derived insights
        insights = await self._capsule_repo.get_derived_insights(user_id)
        response.derived_insights = [i.to_export_dict() for i in insights]
        
        # Log DSAR processing
        await self._audit.log(AuditEvent(
            event_type="dsar_processed",
            user_id=user_id,
            details={
                "capsule_count": len(response.capsules),
                "interaction_count": len(response.interactions)
            }
        ))
        
        return response
    
    async def process_deletion_request(
        self,
        user_id: str,
        verification: DeletionVerification
    ) -> DeletionReport:
        """
        Process a GDPR Right to Erasure request.
        
        Deletes all user data while preserving system integrity.
        Some data may be anonymized rather than deleted if
        required for system operation.
        """
        report = DeletionReport(user_id=user_id)
        
        # Verify request (prevent accidental deletion)
        if not await self._verify_deletion_request(user_id, verification):
            raise VerificationFailedError("Deletion verification failed")
        
        # Delete user-owned capsules
        owned_capsules = await self._capsule_repo.get_by_owner(user_id)
        for capsule in owned_capsules:
            # Check if capsule has derivatives owned by others
            derivatives = await self._capsule_repo.get_derivatives(capsule.id)
            other_owner_derivatives = [
                d for d in derivatives if d.owner_id != user_id
            ]
            
            if other_owner_derivatives:
                # Anonymize rather than delete (preserve lineage integrity)
                await self._anonymize_capsule(capsule)
                report.anonymized.append(capsule.id)
            else:
                # Safe to delete
                await self._capsule_repo.delete(capsule.id)
                report.deleted.append(capsule.id)
        
        # Delete user profile (anonymize public contributions)
        await self._anonymize_user_profile(user_id)
        report.profile_deleted = True
        
        # Delete interaction history
        await self._user_repo.delete_interaction_history(user_id)
        report.interactions_deleted = True
        
        # Log deletion
        await self._audit.log(AuditEvent(
            event_type="deletion_request_processed",
            user_id="[DELETED]",  # Don't log actual user_id post-deletion
            details={
                "capsules_deleted": len(report.deleted),
                "capsules_anonymized": len(report.anonymized)
            }
        ))
        
        return report
```

---

## 8. Deployment Flexibility (Forge Lite)

### 8.1 Problem Statement

Forge's full architecture is sophisticated but may be overkill for simpler use cases. Organizations with basic persistent memory needs shouldn't be forced to operate complex governance and immune systems. A "Forge Lite" configuration provides an on-ramp that scales up as needs grow.

### 8.2 Deployment Profiles

#### 8.2.1 Profile Definitions

```python
class DeploymentProfile(Enum):
    """
    Predefined deployment configurations for different use cases.
    """
    
    LITE = "lite"           # Basic persistence, minimal overhead
    STANDARD = "standard"   # Full features, single-tenant
    ENTERPRISE = "enterprise"  # Multi-tenant, compliance, governance


@dataclass
class ProfileConfiguration:
    """
    Configuration for a deployment profile.
    
    Defines which components are enabled and their settings
    for each profile level.
    """
    
    profile: DeploymentProfile
    
    # Core components (always enabled)
    neo4j_enabled: bool = True
    capsule_repository_enabled: bool = True
    
    # Pipeline configuration
    pipeline_phases: list[PipelinePhase] = field(default_factory=list)
    pipeline_parallelization: bool = False
    
    # Overlay configuration
    enabled_overlays: list[str] = field(default_factory=list)
    
    # Governance
    governance_enabled: bool = False
    ghost_council_enabled: bool = False
    trust_weighted_voting: bool = False
    
    # Immune system
    circuit_breakers_enabled: bool = False
    canary_deployments_enabled: bool = False
    anomaly_detection_enabled: bool = False
    
    # Lineage
    full_lineage_tracking: bool = False
    tiered_lineage: bool = False
    
    # Security
    content_validation_enabled: bool = False
    tenant_isolation_enabled: bool = False
    
    # Observability
    prometheus_metrics: bool = True
    opentelemetry_tracing: bool = False
    detailed_audit_logging: bool = False


# Profile definitions
PROFILE_CONFIGURATIONS = {
    DeploymentProfile.LITE: ProfileConfiguration(
        profile=DeploymentProfile.LITE,
        pipeline_phases=[
            PipelinePhase.INGESTION,
            PipelinePhase.STORAGE
        ],
        pipeline_parallelization=False,
        enabled_overlays=[],  # No overlays in Lite
        governance_enabled=False,
        ghost_council_enabled=False,
        circuit_breakers_enabled=False,
        full_lineage_tracking=False,  # Basic parent reference only
        content_validation_enabled=False,  # Basic validation only
        prometheus_metrics=True,
        opentelemetry_tracing=False
    ),
    
    DeploymentProfile.STANDARD: ProfileConfiguration(
        profile=DeploymentProfile.STANDARD,
        pipeline_phases=list(PipelinePhase),  # All 7 phases
        pipeline_parallelization=True,
        enabled_overlays=[
            "ml_intelligence",
            "security_validator",
            "lineage_tracker"
        ],
        governance_enabled=True,
        ghost_council_enabled=False,  # Optional add-on
        circuit_breakers_enabled=True,
        canary_deployments_enabled=False,
        anomaly_detection_enabled=True,
        full_lineage_tracking=True,
        tiered_lineage=True,
        content_validation_enabled=True,
        prometheus_metrics=True,
        opentelemetry_tracing=True,
        detailed_audit_logging=True
    ),
    
    DeploymentProfile.ENTERPRISE: ProfileConfiguration(
        profile=DeploymentProfile.ENTERPRISE,
        pipeline_phases=list(PipelinePhase),
        pipeline_parallelization=True,
        enabled_overlays=[
            "ml_intelligence",
            "security_validator",
            "governance",
            "lineage_tracker"
        ],
        governance_enabled=True,
        ghost_council_enabled=True,
        trust_weighted_voting=True,
        circuit_breakers_enabled=True,
        canary_deployments_enabled=True,
        anomaly_detection_enabled=True,
        full_lineage_tracking=True,
        tiered_lineage=True,
        content_validation_enabled=True,
        tenant_isolation_enabled=True,
        prometheus_metrics=True,
        opentelemetry_tracing=True,
        detailed_audit_logging=True
    )
}
```

#### 8.2.2 Profile-Aware Application Factory

```python
class ForgeApplicationFactory:
    """
    Creates Forge application instances configured for specific profiles.
    
    The factory reads the deployment profile and initializes only
    the components required for that profile, reducing resource
    usage and complexity for simpler deployments.
    """
    
    def __init__(self, profile: DeploymentProfile):
        self._profile = profile
        self._config = PROFILE_CONFIGURATIONS[profile]
    
    async def create_application(self) -> ForgeApplication:
        """
        Create a Forge application instance for the configured profile.
        """
        app = ForgeApplication(profile=self._profile)
        
        # Initialize database (always required)
        app.neo4j_client = await self._create_neo4j_client()
        app.capsule_repository = CapsuleRepository(app.neo4j_client)
        
        # Initialize pipeline with profile-appropriate phases
        app.pipeline = self._create_pipeline()
        
        # Initialize overlays
        if self._config.enabled_overlays:
            app.overlay_manager = await self._create_overlay_manager()
        
        # Initialize governance if enabled
        if self._config.governance_enabled:
            app.governance = await self._create_governance_system()
        
        # Initialize immune system components
        if self._config.circuit_breakers_enabled:
            app.circuit_breaker_manager = CircuitBreakerManager()
        
        if self._config.anomaly_detection_enabled:
            app.anomaly_detector = AnomalyDetector()
        
        # Initialize security components
        if self._config.content_validation_enabled:
            app.content_validator = ContentValidator(
                ml_overlay=app.overlay_manager.get("ml_intelligence") if app.overlay_manager else None,
                config=ValidationConfig()
            )
        
        if self._config.tenant_isolation_enabled:
            app.tenant_enforcer = TenantIsolationEnforcer(app.neo4j_client)
        
        # Initialize observability
        app.observability = ForgeObservability(
            config=ObservabilityConfig(
                enable_tracing=self._config.opentelemetry_tracing,
                enable_metrics=self._config.prometheus_metrics
            )
        )
        
        logger.info(
            f"Forge application created with profile: {self._profile.value}",
            components_enabled=self._list_enabled_components()
        )
        
        return app
    
    def _create_pipeline(self) -> Pipeline:
        """
        Create pipeline with profile-appropriate phases.
        """
        phase_configs = []
        
        for phase in self._config.pipeline_phases:
            phase_configs.append(PhaseConfig(
                name=phase,
                enabled=True,
                parallel=self._config.pipeline_parallelization
            ))
        
        return Pipeline(phase_configs=phase_configs)
    
    def _list_enabled_components(self) -> list[str]:
        """
        List components enabled for this profile.
        """
        components = ["neo4j", "capsule_repository", "pipeline"]
        
        if self._config.enabled_overlays:
            components.extend(self._config.enabled_overlays)
        
        if self._config.governance_enabled:
            components.append("governance")
        
        if self._config.ghost_council_enabled:
            components.append("ghost_council")
        
        if self._config.circuit_breakers_enabled:
            components.append("circuit_breakers")
        
        if self._config.anomaly_detection_enabled:
            components.append("anomaly_detection")
        
        if self._config.content_validation_enabled:
            components.append("content_validation")
        
        if self._config.tenant_isolation_enabled:
            components.append("tenant_isolation")
        
        return components
```

### 8.3 Profile Migration

Organizations can upgrade from Lite to Standard to Enterprise as needs grow.

```python
class ProfileMigrationManager:
    """
    Manages migration between deployment profiles.
    
    Handles enabling additional components, creating required
    database structures, and validating migration prerequisites.
    """
    
    VALID_MIGRATIONS = {
        DeploymentProfile.LITE: [DeploymentProfile.STANDARD],
        DeploymentProfile.STANDARD: [DeploymentProfile.ENTERPRISE],
        DeploymentProfile.ENTERPRISE: []  # No upgrade from Enterprise
    }
    
    async def migrate_profile(
        self,
        current_profile: DeploymentProfile,
        target_profile: DeploymentProfile,
        app: ForgeApplication
    ) -> MigrationReport:
        """
        Migrate Forge instance to a new deployment profile.
        
        This is a non-destructive operation that enables additional
        features without disrupting existing functionality.
        """
        # Validate migration path
        if target_profile not in self.VALID_MIGRATIONS[current_profile]:
            raise InvalidMigrationError(
                f"Cannot migrate from {current_profile} to {target_profile}"
            )
        
        report = MigrationReport(
            from_profile=current_profile,
            to_profile=target_profile,
            started_at=datetime.utcnow()
        )
        
        target_config = PROFILE_CONFIGURATIONS[target_profile]
        current_config = PROFILE_CONFIGURATIONS[current_profile]
        
        # Enable new pipeline phases
        new_phases = set(target_config.pipeline_phases) - set(current_config.pipeline_phases)
        for phase in new_phases:
            await self._enable_pipeline_phase(app, phase)
            report.phases_enabled.append(phase)
        
        # Initialize new overlays
        new_overlays = set(target_config.enabled_overlays) - set(current_config.enabled_overlays)
        for overlay_name in new_overlays:
            await self._initialize_overlay(app, overlay_name)
            report.overlays_enabled.append(overlay_name)
        
        # Enable governance if transitioning to it
        if target_config.governance_enabled and not current_config.governance_enabled:
            await self._enable_governance(app)
            report.governance_enabled = True
        
        # Enable immune system components
        if target_config.circuit_breakers_enabled and not current_config.circuit_breakers_enabled:
            await self._enable_circuit_breakers(app)
            report.circuit_breakers_enabled = True
        
        # Backfill lineage if enabling full tracking
        if target_config.full_lineage_tracking and not current_config.full_lineage_tracking:
            await self._backfill_lineage(app)
            report.lineage_backfilled = True
        
        # Update stored profile
        await self._update_profile_marker(app, target_profile)
        
        report.completed_at = datetime.utcnow()
        report.success = True
        
        return report
```

---

## 9. Integration Points

### 9.1 Cross-Component Dependencies

The following diagram illustrates how resilience components integrate with core Forge systems.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FORGE RESILIENCE LAYER                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ Graph Perf Opt  │    │ Lineage Storage │    │ Model Migration │     │
│  │  - Partitioning │    │  - Tiered Store │    │  - Version Mgmt │     │
│  │  - Caching      │    │  - Delta Diffs  │    │  - Re-embedding │     │
│  │  - Mat. Views   │    │  - Background   │    │  - Extraction   │     │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘     │
│           │                      │                      │               │
│           └──────────────────────┼──────────────────────┘               │
│                                  │                                      │
│                                  ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      NEO4J UNIFIED DATA STORE                     │ │
│  │                                                                   │ │
│  │   Capsules ◄──► Lineage ◄──► Partitions ◄──► Embeddings         │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                  ▲                                      │
│           ┌──────────────────────┼──────────────────────┐               │
│           │                      │                      │               │
│  ┌────────┴────────┐    ┌────────┴────────┐    ┌────────┴────────┐     │
│  │ Cold Start      │    │ Security        │    │ Ops Resilience  │     │
│  │  - Starter Pack │    │  - Validation   │    │  - Observability│     │
│  │  - Profiling    │    │  - Isolation    │    │  - Runbooks     │     │
│  │  - Marketplace  │    │  - Privacy      │    │  - Failure Cat. │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FORGE CORE COMPONENTS                           │
│                                                                         │
│   Seven-Phase Pipeline ◄──► Overlay Manager ◄──► Governance System     │
│            │                      │                      │              │
│            ▼                      ▼                      ▼              │
│      Event System ◄────────► Immune System ◄────────► API Layer        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Configuration Schema

All resilience components are configured through a unified configuration schema.

```python
@dataclass
class ForgeResilienceConfig:
    """
    Unified configuration for all resilience components.
    """
    
    # Deployment profile
    profile: DeploymentProfile = DeploymentProfile.STANDARD
    
    # Graph performance
    graph_performance: GraphPerformanceConfig = field(
        default_factory=GraphPerformanceConfig
    )
    
    # Lineage storage
    lineage_storage: LineageTierConfig = field(
        default_factory=LineageTierConfig
    )
    
    # Model migration
    model_migration: MigrationConfig = field(
        default_factory=MigrationConfig
    )
    
    # Cold start
    cold_start: ColdStartConfig = field(
        default_factory=ColdStartConfig
    )
    
    # Security
    security: SecurityHardeningConfig = field(
        default_factory=SecurityHardeningConfig
    )
    
    # Observability
    observability: ObservabilityConfig = field(
        default_factory=ObservabilityConfig
    )
    
    @classmethod
    def from_environment(cls) -> 'ForgeResilienceConfig':
        """Load configuration from environment variables."""
        return cls(
            profile=DeploymentProfile(
                os.getenv("FORGE_PROFILE", "standard")
            ),
            graph_performance=GraphPerformanceConfig.from_environment(),
            lineage_storage=LineageTierConfig.from_environment(),
            # ... etc
        )
```

---

## 10. Implementation Priority Matrix

### 10.1 Priority Ranking

Components are ranked by impact (how much they improve reliability/scalability) and effort (implementation complexity).

| Component | Impact | Effort | Priority | Dependencies |
|-----------|--------|--------|----------|--------------|
| Query Caching | High | Low | P0 | Redis |
| Observability Integration | High | Low | P0 | OTel SDK |
| Content Validation | High | Medium | P0 | ML Overlay |
| Tiered Lineage Storage | High | Medium | P1 | S3 Client |
| Graph Partitioning | High | High | P1 | Schema Migration |
| Embedding Migration | High | Medium | P1 | Embedding Provider |
| Tenant Isolation | Medium | Medium | P1 | Multi-tenant Deploy |
| Starter Packs | Medium | Low | P2 | None |
| Progressive Profiling | Medium | Medium | P2 | ML Overlay |
| Materialized Views | Medium | High | P2 | Partitioning |
| Runbook System | Medium | Medium | P2 | Observability |
| Knowledge Marketplace | Low | High | P3 | Tokenization |
| Forge Lite Profile | Low | Low | P3 | None |

### 10.2 Implementation Phases

**Phase 1 (Weeks 1-2): Foundation**
- Query caching with Redis
- OpenTelemetry integration
- Content validation pipeline
- Basic Prometheus metrics

**Phase 2 (Weeks 3-4): Storage Optimization**
- Tiered lineage storage
- Delta-based diff storage
- Background tier migration worker
- Embedding version management

**Phase 3 (Weeks 5-6): Scale Preparation**
- Graph partitioning schema
- Partition assignment logic
- Cross-partition query handling
- Background re-embedding service

**Phase 4 (Weeks 7-8): Enterprise Features**
- Tenant isolation enforcement
- Privacy management (GDPR)
- Runbook system
- Failure mode catalog

**Phase 5 (Weeks 9-10): Ecosystem**
- Starter pack import/export
- Progressive profiling
- Knowledge marketplace foundation
- Deployment profile system

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| Cascade Storm | Runaway event propagation that overwhelms the system |
| Cold Start | State of new deployment with no accumulated knowledge |
| Lineage Tier | Storage classification for lineage detail level |
| Materialized View | Pre-computed query result stored for fast retrieval |
| Memory Poisoning | Attack injecting malicious data into AI memory |
| Partition | Logical subdivision of the knowledge graph |
| Progressive Profiling | Gradual learning of user preferences from behavior |
| Starter Pack | Curated capsule collection for bootstrapping |
| Tenant | Isolated organizational unit in multi-tenant deployment |

---

## Appendix B: Related Specifications

- FORGE_SPECIFICATION_V3_COMPLETE.md - Core architecture
- FORGE_VIRTUALS_INTEGRATION.md - Tokenization and marketplace
- FORGE_COMPLIANCE_FRAMEWORK.md - Regulatory compliance

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-06 | Frowg Systems | Initial specification |

---

**End of Specification**
