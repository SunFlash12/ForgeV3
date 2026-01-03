# FORGE CASCADE - Upgraded Architecture Specification

**Version:** 2.0  
**Date:** 2026-01-01  
**Status:** Architecture Upgrade - Incorporating Feasibility Study Recommendations  
**Purpose:** Production-ready specification addressing latency, security, and scalability concerns

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Upgrades Overview](#architecture-upgrades-overview)
3. [Problem Statement & Core Vision](#problem-statement--core-vision)
4. [Core Concepts & Terminology](#core-concepts--terminology)
5. [Upgraded Architecture](#upgraded-architecture)
6. [Data Layer: Neo4j Unified Store](#data-layer-neo4j-unified-store)
7. [Overlay Runtime: WebAssembly Sandbox](#overlay-runtime-webassembly-sandbox)
8. [Optimized Seven-Phase Pipeline](#optimized-seven-phase-pipeline)
9. [Immune System Architecture](#immune-system-architecture)
10. [User-Facing Features](#user-facing-features)
11. [API Specification](#api-specification)
12. [Technology Stack](#technology-stack)
13. [Development & Operational Goals](#development--operational-goals)
14. [Deployment Architecture](#deployment-architecture)
15. [Migration Path from V1](#migration-path-from-v1)
16. [Success Metrics](#success-metrics)

---

## Executive Summary

**Forge Cascade** is a cognitive architecture platform designed to solve **ephemeral wisdom in AI systems**—the loss of learned knowledge when AI systems are upgraded, retrained, or restarted.

### What's New in V2

This specification incorporates critical architectural upgrades identified in the comprehensive feasibility study:

| Component | V1 (Original) | V2 (Upgraded) | Benefit |
|-----------|---------------|---------------|---------|
| **Database** | PostgreSQL + separate Vector DB | Neo4j with native Vector Index | Single source of truth for lineage + semantics |
| **Overlay Runtime** | Python + RLIMIT_AS sandboxing | WebAssembly (Wasm) isolation | True memory safety, instant termination |
| **Pipeline** | Sequential 7-phase (2-5s latency) | Parallelized phases (~800ms-1.5s) | 3x latency improvement |
| **Immune System** | Basic health checks | Canary deployments + hierarchical validation | Prevents autoimmune failures |

### Strategic Positioning

Based on feasibility analysis, Forge is positioned as:

- **NOT** a consumer chatbot competitor
- **IS** an "Institutional Memory Engine" for enterprise
- **Target markets:** Regulated sectors (legal, biotech, finance) where lineage and governance matter more than speed

### Core Innovation

The **Capsule + Symbolic Inheritance** architecture remains the primary differentiator—providing traceable "Isnad" (knowledge lineage) that enables:

- Audit trails for AI decisions
- Compliance with EU AI Act explainability requirements
- Knowledge preservation across model generations

---

## Architecture Upgrades Overview

### Upgrade 1: Neo4j Unified Data Store

**Problem Solved:** The original architecture required synchronizing three separate data layers (vector, graph, relational), creating consistency nightmares and "hallucinated references."

**Solution:** Neo4j 5.x with native vector indexing provides:

```
┌─────────────────────────────────────────────────────────────┐
│                    NEO4J UNIFIED STORE                       │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   GRAPH     │  │   VECTOR    │  │    PROPERTIES       │  │
│  │  Lineage    │  │  Semantic   │  │   Trust, Version,   │  │
│  │  Ancestry   │  │  Search     │  │   Owner, Metadata   │  │
│  │  Cascades   │  │  Similarity │  │   Timestamps        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                              │
│           ALL IN ONE ACID-COMPLIANT DATABASE                 │
└─────────────────────────────────────────────────────────────┘
```

### Upgrade 2: WebAssembly Overlay Runtime

**Problem Solved:** Python's RLIMIT_AS sandboxing is insecure—C-extensions and introspection can escape. The Immune System cannot cleanly terminate misbehaving Overlays.

**Solution:** Compile Overlays to WebAssembly for true isolation:

```
┌─────────────────────────────────────────────────────────────┐
│                   OVERLAY EXECUTION                          │
│                                                              │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │   Python Overlay     │ →  │   Nuitka/Pyodide         │   │
│  │   Source Code        │    │   Compilation            │   │
│  └──────────────────────┘    └──────────────────────────┘   │
│                                       │                      │
│                                       ▼                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              WASMTIME / WASMER RUNTIME               │   │
│  │                                                      │   │
│  │  • Memory-safe sandbox (no escape possible)          │   │
│  │  • Instant termination (clean process kill)          │   │
│  │  • Resource metering (CPU cycles, memory)            │   │
│  │  • Capability-based security (explicit permissions)  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Upgrade 3: Parallelized Pipeline

**Problem Solved:** Sequential 7-phase execution creates 2-5 second latency, unacceptable even for async workflows.

**Solution:** Parallelize independent phases:

```
ORIGINAL (Sequential):
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
  300ms    800ms     100ms     20ms     2000ms    10ms      400ms
                                                          = 3.6s total

UPGRADED (Parallelized):
┌─────────────────────────────────────────────────────────────┐
│ PARALLEL GROUP 1 (max 300ms)                                │
│   Phase 1: Context      ─┐                                  │
│   Phase 2: Analysis     ─┼─► asyncio.gather()               │
│   Phase 3: Security     ─┘                                  │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ SEQUENTIAL (necessary dependency)                           │
│   Phase 4: Optimization (uses Phase 1-3 results)    20ms    │
│   Phase 5: Intelligence (main LLM call)            1000ms   │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ FIRE-AND-FORGET (async, don't await)                        │
│   Phase 6: Metrics      ─┐                                  │
│   Phase 7: Storage      ─┴─► asyncio.create_task()          │
└─────────────────────────────────────────────────────────────┘

NEW TOTAL: ~1.3s (vs 3.6s = 2.8x improvement)
```

---

## Problem Statement & Core Vision

### The Problem: Ephemeral Wisdom

Traditional AI systems suffer from **knowledge amnesia**:

- **Nuanced Wisdom is Lost:** Experiential knowledge disappears on upgrade
- **Mistakes Repeat:** New versions re-learn the same errors
- **No Generational Learning:** Each generation starts from scratch
- **Knowledge Trapped in State:** Wisdom exists only within current parameters

This is analogous to humanity without books—every generation starting from zero.

### The Solution: Forge Cascade

Forge provides cognitive architecture through:

1. **Persistent Memory:** Knowledge survives across system generations via Capsules
2. **Evolutionary Intelligence:** Each generation builds upon predecessors
3. **Symbolic Inheritance:** Explicit lineage linking new knowledge to ancestors
4. **The Cascade Effect:** Breakthroughs propagate across the ecosystem
5. **Self-Governance:** Democratic processes and ethical guardrails
6. **Self-Healing Architecture:** Immune system detects, quarantines, repairs

### The Philosophical Foundation

Forge creates **AI systems that learn like cultures, not individuals**. Just as human civilization progresses through accumulated cultural knowledge, Forge enables AI to build an ever-growing repository of wisdom that transcends any single instance.

---

## Core Concepts & Terminology

### Capsule

**Definition:** The atomic unit of knowledge in Forge.

**Properties:**

```typescript
interface Capsule {
  id: UUID;                    // Unique identifier
  content: string;             // The actual knowledge/data
  type: CapsuleType;           // knowledge | code | decision | insight | config
  version: SemVer;             // Semantic versioning (1.0.0, 2.1.0)
  parent_id: UUID | null;      // Symbolic inheritance link
  owner_id: UUID;              // Creator/owner
  trust_level: TrustLevel;     // CORE | TRUSTED | STANDARD | SANDBOX | QUARANTINE
  embedding: float[1536];      // Vector embedding for semantic search
  metadata: JSON;              // Extensible properties
  created_at: DateTime;
  updated_at: DateTime;
}
```

**Lifecycle:**

```
CREATE → ACTIVE → VERSION (creates child) → ARCHIVE → MIGRATE
```

### Overlay

**Definition:** Self-contained intelligent module providing specialized functionality.

**V2 Change:** Overlays are now compiled to WebAssembly for execution.

**Properties:**

```typescript
interface Overlay {
  id: UUID;
  name: string;
  version: SemVer;
  wasm_binary: Uint8Array;     // Compiled WebAssembly module
  source_hash: SHA256;         // Hash of source for verification
  trust_level: TrustLevel;
  dependencies: UUID[];
  capabilities: Capability[];  // Explicit permissions required
  state: OverlayState;
  metrics: OverlayMetrics;
}

enum Capability {
  NETWORK_ACCESS,              // Can make HTTP requests
  DATABASE_READ,               // Can read from Neo4j
  DATABASE_WRITE,              // Can write to Neo4j
  EVENT_PUBLISH,               // Can publish to event system
  EVENT_SUBSCRIBE,             // Can subscribe to events
  CAPSULE_CREATE,              // Can create capsules
  CAPSULE_MODIFY,              // Can modify capsules
  GOVERNANCE_VOTE,             // Can participate in governance
}
```

**Core Overlays:**

| Overlay | Purpose | Capabilities |
|---------|---------|--------------|
| `symbolic_governance` | Democratic decision-making | DATABASE_*, EVENT_*, GOVERNANCE_* |
| `security_validator` | Trust validation, threat detection | DATABASE_READ, EVENT_* |
| `ml_intelligence` | Pattern recognition, anomaly detection | DATABASE_READ, EVENT_PUBLISH |
| `performance_optimizer` | Resource allocation, caching | DATABASE_READ, EVENT_* |
| `capsule_analyzer` | Content analysis, insights | DATABASE_*, CAPSULE_* |
| `lineage_tracker` | Ancestry visualization, Isnad | DATABASE_READ |

### Symbolic Inheritance

**Definition:** Knowledge passes down through generations with explicit lineage tracking.

**Neo4j Implementation:**

```cypher
// Create capsule with parent relationship
CREATE (child:Capsule {
  id: $child_id,
  content: $content,
  trust_level: $trust,
  version: '1.0.0'
})
WITH child
MATCH (parent:Capsule {id: $parent_id})
CREATE (child)-[:DERIVED_FROM {
  reason: $evolution_reason,
  timestamp: datetime(),
  changes: $diff
}]->(parent)

// Trace full lineage
MATCH path = (c:Capsule {id: $capsule_id})-[:DERIVED_FROM*]->(ancestor)
RETURN path
```

### Trust Hierarchy

**Levels:**

| Level | Value | Description | Capabilities |
|-------|-------|-------------|--------------|
| `CORE` | 100 | System-critical | Full access, immune to quarantine |
| `TRUSTED` | 80 | Verified, reliable | Most operations, governance voting |
| `STANDARD` | 60 | Default level | Basic operations |
| `SANDBOX` | 40 | Experimental | Limited, monitored |
| `QUARANTINE` | 0 | Blocked | No execution |

**Dynamic Adjustment:**

- **Increase:** Successful operations, positive votes, time in service
- **Decrease:** Failures, security incidents, negative votes
- **Auto-quarantine:** 3+ consecutive health check failures

### The Cascade Effect

**Definition:** Knowledge propagation where breakthroughs diffuse across the ecosystem.

**Mechanism:**

```
1. Overlay X detects insight
2. Publishes event via SecureEventSystem
3. OverlayManager routes to relevant overlays
4. Each overlay integrates insight
5. System-wide intelligence increases
```

**Example:**

```
SecurityValidator: Detects new SQL injection pattern
    ↓ (security_threat event)
MLIntelligence: Updates anomaly model
    ↓ (model_updated event)
PerformanceOptimizer: Increases validation resources
    ↓ (optimization_applied event)
GovernanceSystem: Creates proposal for input rules
    ↓ (governance_action event)
AuditLog: Records cascade chain
```

---

## Upgraded Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE LAYER                          │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  FastAPI Application (ASGI)                                    │ │
│  │  - OpenAPI/Swagger documentation                               │ │
│  │  - WebSocket support for real-time updates                     │ │
│  │  - Static files (dashboard SPA)                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FORGE KERNEL                                 │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    OverlayManager                              │ │
│  │                                                                │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │ │
│  │  │  Wasm Runtime    │  │  Lifecycle       │  │  Dependency  │ │ │
│  │  │  (Wasmtime)      │  │  State Machine   │  │  Resolution  │ │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────┘ │ │
│  │                                                                │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │ │
│  │  │  Capability      │  │  Health Monitor  │  │  Event       │ │ │
│  │  │  Enforcement     │  │  + Canary Deploy │  │  Router      │ │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Security Layer                              │ │
│  │  - TrustHierarchy (reputation)                                 │ │
│  │  - CapabilityEnforcer (permissions)                            │ │
│  │  - ConstitutionalAI (ethical drift detection)                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Immune System                               │ │
│  │  - Anomaly Detection (IsolationForest)                         │ │
│  │  - Canary Validator (staged rollouts)                          │ │
│  │  - Auto-Quarantine (circuit breaker)                           │ │
│  │  - State Rollback (capsule version revert)                     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │              Overlay Modules (WebAssembly)                     │ │
│  │                                                                │ │
│  │  [symbolic_governance.wasm]  [ml_intelligence.wasm]            │ │
│  │  [security_validator.wasm]   [performance_optimizer.wasm]      │ │
│  │  [capsule_analyzer.wasm]     [lineage_tracker.wasm]            │ │
│  └────────────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       NEO4J DATA LAYER                               │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Graph Storage (Lineage, Relationships, Cascades)              │ │
│  │  Vector Index (Semantic Search, Similarity)                    │ │
│  │  Property Storage (Trust, Metadata, Timestamps)                │ │
│  │                                                                │ │
│  │  Drivers: neo4j-python-driver (async)                          │ │
│  │  Deployment: Neo4j Aura (cloud) or self-hosted cluster         │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Layer: Neo4j Unified Store

### Why Neo4j?

The feasibility study identified sync issues between vector, graph, and relational layers. Neo4j 5.x solves this with native vector indexing.

**Single Database Benefits:**

- **ACID transactions** across all data types
- **No sync issues** between layers
- **Native graph** for lineage queries
- **Vector search** for semantic retrieval
- **Cypher query language** for complex patterns

### Schema Design

#### Node Types

```cypher
// Capsule Node
CREATE CONSTRAINT capsule_id IF NOT EXISTS
FOR (c:Capsule) REQUIRE c.id IS UNIQUE;

CREATE (c:Capsule {
  id: randomUUID(),
  content: "Knowledge content here",
  type: "knowledge",
  version: "1.0.0",
  trust_level: 60,
  owner_id: $owner_uuid,
  created_at: datetime(),
  updated_at: datetime(),
  metadata: $json_metadata
})

// Create vector index for semantic search
CREATE VECTOR INDEX capsule_embeddings IF NOT EXISTS
FOR (c:Capsule) ON c.embedding
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
}

// User Node
CREATE CONSTRAINT user_id IF NOT EXISTS
FOR (u:User) REQUIRE u.id IS UNIQUE;

CREATE (u:User {
  id: randomUUID(),
  username: "unique_username",
  email: "user@example.com",
  password_hash: $hash,
  role: "user",
  trust_flame: 60,
  is_active: true,
  created_at: datetime()
})

// Overlay Node (state tracking)
CREATE CONSTRAINT overlay_id IF NOT EXISTS
FOR (o:Overlay) REQUIRE o.id IS UNIQUE;

CREATE (o:Overlay {
  id: randomUUID(),
  name: "ml_intelligence",
  version: "1.2.0",
  state: "ACTIVE",
  trust_level: 80,
  wasm_hash: $sha256_hash,
  capabilities: ["DATABASE_READ", "EVENT_PUBLISH"],
  activated_at: datetime(),
  metrics: $json_metrics
})

// Governance Proposal
CREATE (p:Proposal {
  id: randomUUID(),
  title: "Increase ML model training frequency",
  description: $full_description,
  proposer_id: $user_id,
  status: "voting",
  votes_for: 0,
  votes_against: 0,
  weight_for: 0.0,
  weight_against: 0.0,
  created_at: datetime(),
  closes_at: datetime() + duration('P7D')
})

// Audit Log
CREATE (a:AuditLog {
  id: randomUUID(),
  operation: "CREATE",
  entity_type: "Capsule",
  entity_id: $capsule_id,
  user_id: $actor_id,
  changes: $json_diff,
  correlation_id: $correlation_uuid,
  timestamp: datetime()
})
```

#### Relationship Types

```cypher
// Symbolic Inheritance
(child:Capsule)-[:DERIVED_FROM {
  reason: "Performance optimization",
  timestamp: datetime(),
  changes: $json_diff
}]->(parent:Capsule)

// Ownership
(u:User)-[:OWNS]->(c:Capsule)
(u:User)-[:CREATED]->(p:Proposal)

// Voting
(u:User)-[:VOTED {
  vote: "for",
  weight: 80.0,
  timestamp: datetime()
}]->(p:Proposal)

// Cascade Events
(source:Overlay)-[:TRIGGERED {
  event_type: "security_threat",
  payload: $json_payload,
  timestamp: datetime()
}]->(target:Overlay)

// Trust History
(entity)-[:TRUST_CHANGED {
  old_level: 60,
  new_level: 80,
  reason: "Consistent successful operations",
  timestamp: datetime()
}]->(entity)
```

### Common Queries

#### Semantic Search with Vector Index

```cypher
// Find similar capsules
CALL db.index.vector.queryNodes(
  'capsule_embeddings',
  10,
  $query_embedding
) YIELD node AS capsule, score
WHERE capsule.trust_level >= 40
RETURN capsule.id, capsule.content, capsule.type, score
ORDER BY score DESC
```

#### Full Lineage Trace (The "Isnad")

```cypher
// Get complete ancestry of a capsule
MATCH path = (c:Capsule {id: $capsule_id})-[:DERIVED_FROM*0..]->(ancestor:Capsule)
WHERE NOT (ancestor)-[:DERIVED_FROM]->()
RETURN path,
       [node in nodes(path) | {
         id: node.id,
         version: node.version,
         created_at: node.created_at
       }] AS lineage
```

#### Cascade Event Propagation

```cypher
// Find all overlays affected by a cascade
MATCH path = (source:Overlay {name: $source_name})
             -[:TRIGGERED*1..5]->(affected:Overlay)
WHERE affected.state = 'ACTIVE'
RETURN DISTINCT affected.name, length(path) AS hop_distance
ORDER BY hop_distance
```

#### Trust-Weighted Governance Query

```cypher
// Get proposal with weighted vote counts
MATCH (p:Proposal {id: $proposal_id})
OPTIONAL MATCH (voter:User)-[v:VOTED]->(p)
WITH p,
     sum(CASE WHEN v.vote = 'for' THEN v.weight ELSE 0 END) AS weight_for,
     sum(CASE WHEN v.vote = 'against' THEN v.weight ELSE 0 END) AS weight_against,
     count(CASE WHEN v.vote = 'for' THEN 1 END) AS votes_for,
     count(CASE WHEN v.vote = 'against' THEN 1 END) AS votes_against
RETURN p {
  .*,
  votes_for: votes_for,
  votes_against: votes_against,
  weight_for: weight_for,
  weight_against: weight_against,
  approval_ratio: CASE WHEN weight_for + weight_against > 0 
                       THEN weight_for / (weight_for + weight_against)
                       ELSE 0 END
}
```

### Python Driver Integration

```python
from neo4j import AsyncGraphDatabase
from contextlib import asynccontextmanager

class Neo4jClient:
    """Async Neo4j client for Forge."""
    
    def __init__(self, uri: str, user: str, password: str):
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        await self._driver.close()
    
    @asynccontextmanager
    async def session(self):
        async with self._driver.session() as session:
            yield session
    
    async def create_capsule(
        self,
        content: str,
        capsule_type: str,
        owner_id: str,
        parent_id: str | None = None,
        embedding: list[float] | None = None
    ) -> dict:
        """Create a new capsule with optional symbolic inheritance."""
        
        query = """
        CREATE (c:Capsule {
            id: randomUUID(),
            content: $content,
            type: $type,
            version: '1.0.0',
            trust_level: 60,
            owner_id: $owner_id,
            embedding: $embedding,
            created_at: datetime(),
            updated_at: datetime()
        })
        WITH c
        OPTIONAL MATCH (parent:Capsule {id: $parent_id})
        FOREACH (_ IN CASE WHEN parent IS NOT NULL THEN [1] ELSE [] END |
            CREATE (c)-[:DERIVED_FROM {
                timestamp: datetime()
            }]->(parent)
        )
        MATCH (owner:User {id: $owner_id})
        CREATE (owner)-[:OWNS]->(c)
        RETURN c {.id, .content, .type, .version, .trust_level, .created_at}
        """
        
        async with self.session() as session:
            result = await session.run(
                query,
                content=content,
                type=capsule_type,
                owner_id=owner_id,
                parent_id=parent_id,
                embedding=embedding
            )
            record = await result.single()
            return dict(record["c"])
    
    async def semantic_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_trust: int = 40
    ) -> list[dict]:
        """Search capsules by semantic similarity."""
        
        query = """
        CALL db.index.vector.queryNodes('capsule_embeddings', $limit, $embedding)
        YIELD node, score
        WHERE node.trust_level >= $min_trust
        RETURN node {.id, .content, .type, .trust_level}, score
        ORDER BY score DESC
        """
        
        async with self.session() as session:
            result = await session.run(
                query,
                embedding=query_embedding,
                limit=limit,
                min_trust=min_trust
            )
            return [{"capsule": dict(r["node"]), "score": r["score"]} 
                    async for r in result]
    
    async def get_lineage(self, capsule_id: str) -> list[dict]:
        """Get full ancestry chain of a capsule."""
        
        query = """
        MATCH path = (c:Capsule {id: $id})-[:DERIVED_FROM*0..]->(ancestor)
        WHERE NOT (ancestor)-[:DERIVED_FROM]->()
        UNWIND nodes(path) AS node
        RETURN DISTINCT node {.id, .version, .content, .created_at}
        ORDER BY node.created_at ASC
        """
        
        async with self.session() as session:
            result = await session.run(query, id=capsule_id)
            return [dict(r["node"]) async for r in result]
```

---

## Overlay Runtime: WebAssembly Sandbox

### Why WebAssembly?

The feasibility study identified critical security issues with Python sandboxing:

| Issue | Python + RLIMIT_AS | WebAssembly |
|-------|-------------------|-------------|
| Memory escape | C-extensions can bypass | Impossible by design |
| Introspection | Can inspect/modify runtime | No access to host |
| Clean termination | Process may hang | Instant, clean kill |
| Resource metering | Approximate limits | Precise fuel metering |
| Capability control | Honor system | Explicit imports only |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OVERLAY COMPILATION PIPELINE                  │
│                                                                  │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────────┐ │
│  │  Python    │    │  Nuitka    │    │  .wasm binary          │ │
│  │  Source    │ →  │  Compiler  │ →  │  + manifest.json       │ │
│  │  (.py)     │    │            │    │  + capabilities.json   │ │
│  └────────────┘    └────────────┘    └────────────────────────┘ │
│                                                                  │
│  Alternative: Use Pyodide for simpler compilation                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    WASMTIME RUNTIME HOST                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Instance Manager                                        │   │
│  │  - Creates isolated Wasm instances per overlay           │   │
│  │  - Manages fuel (CPU cycle limits)                       │   │
│  │  - Handles memory allocation                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Host Functions (imported by Wasm)                       │   │
│  │  - db_read(query) → JSON                                 │   │
│  │  - db_write(query, params) → Result                      │   │
│  │  - event_publish(type, payload) → void                   │   │
│  │  - event_subscribe(type, callback) → void                │   │
│  │  - log(level, message) → void                            │   │
│  │  - get_config(key) → value                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Capability Enforcer                                     │   │
│  │  - Validates requested capabilities against manifest     │   │
│  │  - Blocks unauthorized host function calls               │   │
│  │  - Logs capability violations                            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import wasmtime
from pathlib import Path
from typing import Callable, Any
from dataclasses import dataclass
from enum import Enum, auto

class Capability(Enum):
    NETWORK_ACCESS = auto()
    DATABASE_READ = auto()
    DATABASE_WRITE = auto()
    EVENT_PUBLISH = auto()
    EVENT_SUBSCRIBE = auto()
    CAPSULE_CREATE = auto()
    CAPSULE_MODIFY = auto()
    GOVERNANCE_VOTE = auto()

@dataclass
class OverlayManifest:
    """Manifest for a compiled overlay."""
    id: str
    name: str
    version: str
    wasm_path: Path
    capabilities: set[Capability]
    dependencies: list[str]
    trust_level: int

class WasmOverlayRuntime:
    """WebAssembly runtime for secure overlay execution."""
    
    def __init__(self, db_client, event_system):
        self.db = db_client
        self.events = event_system
        self.engine = wasmtime.Engine()
        self.instances: dict[str, wasmtime.Instance] = {}
        self.manifests: dict[str, OverlayManifest] = {}
    
    def _create_linker(self, manifest: OverlayManifest) -> wasmtime.Linker:
        """Create linker with host functions based on capabilities."""
        
        linker = wasmtime.Linker(self.engine)
        
        # Always available: logging
        @wasmtime.Func.wrap(self.store, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []))
        def log(level: int, msg_ptr: int):
            # Implementation reads string from Wasm memory
            pass
        linker.define("host", "log", log)
        
        # Capability-gated functions
        if Capability.DATABASE_READ in manifest.capabilities:
            @wasmtime.Func.wrap(self.store, wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()]))
            def db_read(query_ptr: int) -> int:
                # Execute read query, return result pointer
                pass
            linker.define("host", "db_read", db_read)
        
        if Capability.DATABASE_WRITE in manifest.capabilities:
            @wasmtime.Func.wrap(self.store, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], [wasmtime.ValType.i32()]))
            def db_write(query_ptr: int, params_ptr: int) -> int:
                # Execute write query, return result
                pass
            linker.define("host", "db_write", db_write)
        
        if Capability.EVENT_PUBLISH in manifest.capabilities:
            @wasmtime.Func.wrap(self.store, wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []))
            def event_publish(type_ptr: int, payload_ptr: int):
                # Publish event to event system
                pass
            linker.define("host", "event_publish", event_publish)
        
        return linker
    
    async def load_overlay(self, manifest: OverlayManifest) -> str:
        """Load and instantiate a WebAssembly overlay."""
        
        # Read Wasm binary
        wasm_bytes = manifest.wasm_path.read_bytes()
        
        # Create store with fuel metering
        store = wasmtime.Store(self.engine)
        store.set_fuel(10_000_000)  # 10M instructions max
        
        # Compile module
        module = wasmtime.Module(self.engine, wasm_bytes)
        
        # Create linker with capability-gated host functions
        linker = self._create_linker(manifest)
        
        # Instantiate
        instance = linker.instantiate(store, module)
        
        # Store references
        self.instances[manifest.id] = instance
        self.manifests[manifest.id] = manifest
        
        # Call initialize export
        init_func = instance.exports(store).get("initialize")
        if init_func:
            init_func(store)
        
        return manifest.id
    
    async def execute(
        self, 
        overlay_id: str, 
        function: str, 
        payload: dict
    ) -> dict:
        """Execute a function on an overlay with resource limits."""
        
        instance = self.instances.get(overlay_id)
        if not instance:
            raise ValueError(f"Overlay {overlay_id} not loaded")
        
        store = wasmtime.Store(self.engine)
        store.set_fuel(5_000_000)  # 5M instructions per call
        
        # Get export function
        func = instance.exports(store).get(function)
        if not func:
            raise ValueError(f"Function {function} not exported")
        
        # Serialize payload to Wasm memory
        # ... (memory management code)
        
        # Call function
        result_ptr = func(store, payload_ptr)
        
        # Deserialize result from Wasm memory
        # ... (memory management code)
        
        return result
    
    async def terminate(self, overlay_id: str) -> None:
        """Immediately terminate an overlay instance."""
        
        if overlay_id in self.instances:
            # Wasm instances are garbage collected when dereferenced
            # No need for explicit cleanup - just remove references
            del self.instances[overlay_id]
            del self.manifests[overlay_id]
            # Instance is now terminated, memory freed
```

### Overlay Development

**Overlay Source Structure:**

```
overlays/
├── ml_intelligence/
│   ├── manifest.json         # Capabilities, dependencies, metadata
│   ├── src/
│   │   ├── __init__.py
│   │   ├── overlay.py        # Main overlay class
│   │   ├── models.py         # ML models
│   │   └── utils.py
│   ├── tests/
│   │   └── test_overlay.py
│   └── build/
│       ├── ml_intelligence.wasm  # Compiled binary
│       └── ml_intelligence.wat   # WebAssembly text (debug)
```

**manifest.json:**

```json
{
  "id": "ml_intelligence",
  "name": "ML Intelligence Overlay",
  "version": "1.2.0",
  "description": "Pattern recognition and anomaly detection",
  "capabilities": [
    "DATABASE_READ",
    "EVENT_PUBLISH",
    "EVENT_SUBSCRIBE"
  ],
  "dependencies": [],
  "trust_required": 60,
  "exports": [
    "initialize",
    "analyze",
    "detect_anomaly",
    "health_check"
  ],
  "fuel_budget": {
    "initialize": 10000000,
    "analyze": 5000000,
    "detect_anomaly": 2000000,
    "health_check": 100000
  }
}
```

**Overlay Source (Python → Wasm):**

```python
# overlays/ml_intelligence/src/overlay.py
"""ML Intelligence Overlay - Compiled to WebAssembly."""

from host import db_read, event_publish, log  # Host function imports

# State (persisted in Wasm linear memory between calls)
_model_trained = False
_anomaly_threshold = 0.85

def initialize() -> int:
    """Initialize the overlay. Called once on load."""
    global _model_trained
    
    log(0, "ML Intelligence initializing...")
    
    # Load any persisted state from database
    config = db_read("MATCH (c:Config {overlay: 'ml_intelligence'}) RETURN c")
    if config:
        _anomaly_threshold = config.get("threshold", 0.85)
    
    _model_trained = True
    log(0, "ML Intelligence initialized successfully")
    return 0  # Success

def analyze(payload_json: str) -> str:
    """Analyze data for patterns. Returns JSON result."""
    import json
    
    payload = json.loads(payload_json)
    data = payload.get("data", [])
    
    # Pattern analysis logic
    patterns = []
    for item in data:
        # ... analysis code ...
        pass
    
    result = {
        "patterns": patterns,
        "confidence": 0.92,
        "recommendations": []
    }
    
    # Publish insight event
    event_publish("pattern_detected", json.dumps(result))
    
    return json.dumps(result)

def detect_anomaly(metrics_json: str) -> str:
    """Detect anomalies in system metrics."""
    import json
    
    metrics = json.loads(metrics_json)
    
    # Anomaly detection using IsolationForest-style logic
    anomaly_score = _calculate_anomaly_score(metrics)
    is_anomaly = anomaly_score > _anomaly_threshold
    
    if is_anomaly:
        event_publish("anomaly_detected", json.dumps({
            "score": anomaly_score,
            "metrics": metrics,
            "severity": "high" if anomaly_score > 0.95 else "medium"
        }))
    
    return json.dumps({
        "is_anomaly": is_anomaly,
        "score": anomaly_score
    })

def health_check() -> int:
    """Return 0 if healthy, non-zero if failing."""
    if not _model_trained:
        return 1
    return 0

def _calculate_anomaly_score(metrics: dict) -> float:
    """Internal anomaly scoring logic."""
    # Simplified isolation forest-style calculation
    # In production, this would be a proper ML model
    score = 0.0
    
    if metrics.get("cpu_usage", 0) > 90:
        score += 0.3
    if metrics.get("memory_usage", 0) > 85:
        score += 0.3
    if metrics.get("error_rate", 0) > 0.05:
        score += 0.4
    
    return min(score, 1.0)
```

---

## Optimized Seven-Phase Pipeline

### Overview

The original pipeline executed all 7 phases sequentially (2-5s latency). The optimized version parallelizes independent phases.

### Phase Dependencies

```
Phase 1 (Context)     ─┐
Phase 2 (Analysis)    ─┼─► Independent, can parallelize
Phase 3 (Security)    ─┘
         │
         ▼
Phase 4 (Optimization) ← Needs Phase 1-3 results
         │
         ▼
Phase 5 (Intelligence) ← Main LLM call, bottleneck
         │
         ▼
Phase 6 (Metrics)     ─┐
Phase 7 (Storage)     ─┴─► Independent, fire-and-forget
```

### Implementation

```python
import asyncio
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime
import uuid

@dataclass
class PipelineContext:
    """Context passed through the pipeline."""
    correlation_id: str
    user_id: str
    request_data: dict
    
    # Populated by phases
    retrieved_context: Optional[dict] = None
    ml_analysis: Optional[dict] = None
    security_result: Optional[dict] = None
    optimization_hints: Optional[dict] = None
    intelligence_output: Optional[dict] = None
    
    # Timing
    started_at: datetime = None
    phase_timings: dict = None
    
    def __post_init__(self):
        self.started_at = datetime.utcnow()
        self.phase_timings = {}

class OptimizedPipeline:
    """Seven-Phase Coordination Pipeline with parallelization."""
    
    def __init__(
        self,
        db: "Neo4jClient",
        llm: "LLMClient",
        overlays: "OverlayManager",
        metrics_sink: "MetricsSink"
    ):
        self.db = db
        self.llm = llm
        self.overlays = overlays
        self.metrics = metrics_sink
    
    async def execute(self, user_id: str, request: dict) -> dict:
        """Execute the full pipeline with optimizations."""
        
        ctx = PipelineContext(
            correlation_id=str(uuid.uuid4()),
            user_id=user_id,
            request_data=request
        )
        
        # ═══════════════════════════════════════════════════════════
        # PARALLEL GROUP 1: Context, Analysis, Security
        # These phases have no interdependencies
        # ═══════════════════════════════════════════════════════════
        
        parallel_start = datetime.utcnow()
        
        context_result, analysis_result, security_result = await asyncio.gather(
            self._phase_1_context(ctx),
            self._phase_2_analysis(ctx),
            self._phase_3_security(ctx),
            return_exceptions=True
        )
        
        ctx.phase_timings["parallel_group_1"] = (
            datetime.utcnow() - parallel_start
        ).total_seconds()
        
        # Handle any errors from parallel execution
        if isinstance(context_result, Exception):
            raise context_result
        if isinstance(security_result, Exception):
            raise security_result
        # Analysis failures are non-fatal
        if isinstance(analysis_result, Exception):
            analysis_result = {"error": str(analysis_result), "fallback": True}
        
        ctx.retrieved_context = context_result
        ctx.ml_analysis = analysis_result
        ctx.security_result = security_result
        
        # Security check - abort if failed
        if not security_result.get("approved", False):
            return {
                "error": "Security check failed",
                "reason": security_result.get("reason"),
                "correlation_id": ctx.correlation_id
            }
        
        # ═══════════════════════════════════════════════════════════
        # SEQUENTIAL: Optimization needs all parallel results
        # ═══════════════════════════════════════════════════════════
        
        opt_start = datetime.utcnow()
        ctx.optimization_hints = await self._phase_4_optimization(ctx)
        ctx.phase_timings["phase_4_optimization"] = (
            datetime.utcnow() - opt_start
        ).total_seconds()
        
        # ═══════════════════════════════════════════════════════════
        # SEQUENTIAL: Intelligence (LLM) - main bottleneck
        # ═══════════════════════════════════════════════════════════
        
        intel_start = datetime.utcnow()
        ctx.intelligence_output = await self._phase_5_intelligence(ctx)
        ctx.phase_timings["phase_5_intelligence"] = (
            datetime.utcnow() - intel_start
        ).total_seconds()
        
        # ═══════════════════════════════════════════════════════════
        # FIRE-AND-FORGET: Metrics and Storage
        # Don't await - let them complete in background
        # ═══════════════════════════════════════════════════════════
        
        asyncio.create_task(self._phase_6_metrics(ctx))
        asyncio.create_task(self._phase_7_storage(ctx))
        
        # Calculate total time
        total_time = (datetime.utcnow() - ctx.started_at).total_seconds()
        
        return {
            "result": ctx.intelligence_output,
            "correlation_id": ctx.correlation_id,
            "timing": {
                "total_seconds": total_time,
                "phases": ctx.phase_timings
            }
        }
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE IMPLEMENTATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def _phase_1_context(self, ctx: PipelineContext) -> dict:
        """Phase 1: Context Creation & Validation.
        
        - Gather relevant capsules via semantic search
        - Load user profile and preferences
        - Validate input data
        """
        
        # Generate embedding for semantic search
        query_text = ctx.request_data.get("query", "")
        embedding = await self.llm.embed(query_text)
        
        # Parallel sub-operations
        capsules, user_profile = await asyncio.gather(
            self.db.semantic_search(embedding, limit=5),
            self.db.get_user_profile(ctx.user_id)
        )
        
        return {
            "relevant_capsules": capsules,
            "user_profile": user_profile,
            "query_embedding": embedding
        }
    
    async def _phase_2_analysis(self, ctx: PipelineContext) -> dict:
        """Phase 2: Comprehensive ML Analysis.
        
        - Pattern recognition on request
        - Anomaly detection
        - Predictive insights
        """
        
        # Call ML Intelligence overlay
        result = await self.overlays.execute(
            "ml_intelligence",
            "analyze",
            {"data": ctx.request_data}
        )
        
        return result
    
    async def _phase_3_security(self, ctx: PipelineContext) -> dict:
        """Phase 3: Security Assessment.
        
        - Validate user trust level
        - Check operation permissions
        - Threat detection
        """
        
        # Get user trust level
        user = await self.db.get_user(ctx.user_id)
        trust_level = user.get("trust_flame", 60)
        
        # Check if operation is allowed
        required_trust = ctx.request_data.get("required_trust", 40)
        
        # Call security validator overlay
        threat_check = await self.overlays.execute(
            "security_validator",
            "validate",
            {
                "user_id": ctx.user_id,
                "operation": ctx.request_data.get("operation"),
                "payload": ctx.request_data
            }
        )
        
        approved = (
            trust_level >= required_trust and 
            not threat_check.get("threat_detected", False)
        )
        
        return {
            "approved": approved,
            "trust_level": trust_level,
            "required_trust": required_trust,
            "threat_check": threat_check,
            "reason": None if approved else "Insufficient trust or threat detected"
        }
    
    async def _phase_4_optimization(self, ctx: PipelineContext) -> dict:
        """Phase 4: Performance Optimization.
        
        - Determine caching strategy
        - Select optimal model/parameters
        - Resource allocation hints
        """
        
        # Check cache for similar queries
        cache_key = f"query:{hash(ctx.request_data.get('query', ''))}"
        cached = await self._check_cache(cache_key)
        
        if cached:
            return {"use_cache": True, "cached_result": cached}
        
        # Determine optimal LLM parameters based on complexity
        complexity = ctx.ml_analysis.get("complexity_score", 0.5)
        
        return {
            "use_cache": False,
            "llm_params": {
                "temperature": 0.7 if complexity > 0.7 else 0.3,
                "max_tokens": 2000 if complexity > 0.5 else 1000
            },
            "priority": "high" if ctx.security_result.get("trust_level", 0) >= 80 else "normal"
        }
    
    async def _phase_5_intelligence(self, ctx: PipelineContext) -> dict:
        """Phase 5: Intelligence Generation.
        
        - Main LLM inference call
        - Generate response using context
        - This is the primary bottleneck
        """
        
        # Check if we can use cached result
        if ctx.optimization_hints.get("use_cache"):
            return ctx.optimization_hints["cached_result"]
        
        # Build prompt with context
        prompt = self._build_prompt(ctx)
        
        # Call LLM
        response = await self.llm.generate(
            prompt=prompt,
            **ctx.optimization_hints.get("llm_params", {})
        )
        
        return {
            "response": response,
            "model_used": self.llm.model_name,
            "tokens_used": response.get("usage", {})
        }
    
    async def _phase_6_metrics(self, ctx: PipelineContext) -> None:
        """Phase 6: Metrics Updating (fire-and-forget).
        
        - Record performance metrics
        - Update usage statistics
        - Feed ML training data
        """
        
        try:
            await self.metrics.record({
                "correlation_id": ctx.correlation_id,
                "user_id": ctx.user_id,
                "total_time": (datetime.utcnow() - ctx.started_at).total_seconds(),
                "phase_timings": ctx.phase_timings,
                "ml_analysis": ctx.ml_analysis,
                "security_result": ctx.security_result
            })
        except Exception as e:
            # Log but don't fail - metrics are non-critical
            print(f"Metrics recording failed: {e}")
    
    async def _phase_7_storage(self, ctx: PipelineContext) -> None:
        """Phase 7: Results Storage (fire-and-forget).
        
        - Persist interaction to audit log
        - Create capsule if warranted
        - Update lineage relationships
        """
        
        try:
            # Create audit log entry
            await self.db.create_audit_log(
                operation="PIPELINE_EXECUTE",
                entity_type="Interaction",
                entity_id=ctx.correlation_id,
                user_id=ctx.user_id,
                changes={
                    "request": ctx.request_data,
                    "response_summary": ctx.intelligence_output.get("response", "")[:500]
                },
                correlation_id=ctx.correlation_id
            )
            
            # Optionally create capsule from interaction
            if ctx.request_data.get("save_as_capsule"):
                await self.db.create_capsule(
                    content=ctx.intelligence_output.get("response", ""),
                    capsule_type="insight",
                    owner_id=ctx.user_id
                )
                
        except Exception as e:
            # Log but don't fail
            print(f"Storage failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _check_cache(self, key: str) -> Optional[dict]:
        """Check response cache."""
        # Implementation depends on caching layer (Redis, in-memory, etc.)
        return None
    
    def _build_prompt(self, ctx: PipelineContext) -> str:
        """Build LLM prompt with context."""
        
        capsule_context = "\n".join([
            f"- {c['capsule']['content'][:200]}"
            for c in ctx.retrieved_context.get("relevant_capsules", [])
        ])
        
        return f"""Context from knowledge base:
{capsule_context}

User query: {ctx.request_data.get('query', '')}

Provide a helpful, accurate response based on the context above."""
```

### Latency Comparison

| Scenario | V1 Sequential | V2 Parallelized | Improvement |
|----------|---------------|-----------------|-------------|
| Simple query | 2.3s | 0.8s | 2.9x |
| Complex analysis | 4.2s | 1.5s | 2.8x |
| Cache hit | 2.0s | 0.3s | 6.7x |
| Security failure | 1.5s | 0.4s | 3.8x |

---

## Immune System Architecture

### Overview

The feasibility study identified "autoimmune" risks where legitimate changes get incorrectly quarantined. V2 implements hierarchical health checks and canary deployments.

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      IMMUNE SYSTEM                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Anomaly Detector (ML-based)                             │   │
│  │  - IsolationForest for outlier detection                 │   │
│  │  - Baseline learning from historical metrics             │   │
│  │  - Adaptive thresholds per overlay                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Canary Validator                                        │   │
│  │  - New overlay versions tested on 5% traffic first       │   │
│  │  - Success criteria: error rate < 1%, latency < 2x       │   │
│  │  - Auto-rollback if canary fails                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Circuit Breaker                                         │   │
│  │  - Per-overlay failure tracking                          │   │
│  │  - States: CLOSED → OPEN → HALF_OPEN                     │   │
│  │  - Exponential backoff for retries                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  State Rollback Manager                                  │   │
│  │  - Capsule version snapshots                             │   │
│  │  - Transaction log replay                                │   │
│  │  - Point-in-time recovery                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Hierarchical Health Checker                             │   │
│  │  - L1: Overlay self-check (health_check())               │   │
│  │  - L2: Dependency validation                             │   │
│  │  - L3: System-wide consistency check                     │   │
│  │  - L4: External probe validation                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
import asyncio

class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, rejecting calls
    HALF_OPEN = auto()   # Testing if recovered

@dataclass
class CircuitBreaker:
    """Per-overlay circuit breaker."""
    
    overlay_id: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure: Optional[datetime] = None
    
    # Configuration
    failure_threshold: int = 3
    success_threshold: int = 2
    timeout: timedelta = timedelta(seconds=30)
    
    def record_success(self):
        """Record successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        self.success_count = 0
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def can_execute(self) -> bool:
        """Check if operation should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure and datetime.utcnow() - self.last_failure > self.timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN: allow single test request
        return True

@dataclass  
class CanaryDeployment:
    """Canary deployment for overlay updates."""
    
    overlay_id: str
    old_version: str
    new_version: str
    traffic_percentage: float = 0.05  # 5% initial traffic
    
    # Metrics
    old_requests: int = 0
    new_requests: int = 0
    old_errors: int = 0
    new_errors: int = 0
    old_latency_sum: float = 0.0
    new_latency_sum: float = 0.0
    
    # Criteria
    max_error_rate: float = 0.01      # 1% error rate max
    max_latency_ratio: float = 2.0    # New can be max 2x slower
    min_requests: int = 100           # Minimum requests before decision
    
    started_at: datetime = field(default_factory=datetime.utcnow)
    
    def should_route_to_new(self) -> bool:
        """Determine if request should go to new version."""
        import random
        return random.random() < self.traffic_percentage
    
    def record_result(self, is_new: bool, success: bool, latency: float):
        """Record result from either version."""
        if is_new:
            self.new_requests += 1
            if not success:
                self.new_errors += 1
            self.new_latency_sum += latency
        else:
            self.old_requests += 1
            if not success:
                self.old_errors += 1
            self.old_latency_sum += latency
    
    def evaluate(self) -> tuple[str, str]:
        """Evaluate canary status. Returns (action, reason)."""
        
        if self.new_requests < self.min_requests:
            return ("continue", f"Need more data: {self.new_requests}/{self.min_requests}")
        
        # Calculate metrics
        new_error_rate = self.new_errors / self.new_requests if self.new_requests > 0 else 0
        old_error_rate = self.old_errors / self.old_requests if self.old_requests > 0 else 0
        
        new_avg_latency = self.new_latency_sum / self.new_requests if self.new_requests > 0 else 0
        old_avg_latency = self.old_latency_sum / self.old_requests if self.old_requests > 0 else 1
        
        latency_ratio = new_avg_latency / old_avg_latency if old_avg_latency > 0 else 1
        
        # Check error rate
        if new_error_rate > self.max_error_rate:
            return ("rollback", f"Error rate too high: {new_error_rate:.2%} > {self.max_error_rate:.2%}")
        
        # Check latency
        if latency_ratio > self.max_latency_ratio:
            return ("rollback", f"Latency too high: {latency_ratio:.1f}x > {self.max_latency_ratio:.1f}x")
        
        # Success - can promote
        if new_error_rate <= old_error_rate * 1.1:  # Allow 10% variance
            return ("promote", f"Canary successful: error={new_error_rate:.2%}, latency={latency_ratio:.1f}x")
        
        return ("continue", "Metrics acceptable, gathering more data")

class ImmuneSystem:
    """Self-healing immune system for Forge."""
    
    def __init__(self, overlay_manager: "OverlayManager", db: "Neo4jClient"):
        self.overlays = overlay_manager
        self.db = db
        
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.canaries: dict[str, CanaryDeployment] = {}
        self.quarantined: set[str] = set()
        
        # Anomaly detection
        self._baseline_metrics: dict[str, list[dict]] = {}
    
    async def health_check_all(self) -> dict:
        """Run hierarchical health checks on all overlays."""
        
        results = {}
        
        for overlay_id in self.overlays.active_overlays:
            results[overlay_id] = await self._hierarchical_health_check(overlay_id)
        
        return results
    
    async def _hierarchical_health_check(self, overlay_id: str) -> dict:
        """Four-level hierarchical health check."""
        
        result = {
            "overlay_id": overlay_id,
            "levels": {},
            "healthy": True,
            "action": None
        }
        
        # L1: Overlay self-check
        try:
            l1_result = await self.overlays.execute(overlay_id, "health_check", {})
            l1_healthy = l1_result.get("status") == 0
            result["levels"]["L1_self_check"] = {"healthy": l1_healthy}
        except Exception as e:
            result["levels"]["L1_self_check"] = {"healthy": False, "error": str(e)}
            l1_healthy = False
        
        if not l1_healthy:
            result["healthy"] = False
            result["action"] = "quarantine_pending"
            return result
        
        # L2: Dependency validation
        dependencies = await self.overlays.get_dependencies(overlay_id)
        l2_healthy = all(
            dep_id not in self.quarantined 
            for dep_id in dependencies
        )
        result["levels"]["L2_dependencies"] = {
            "healthy": l2_healthy,
            "dependencies": dependencies
        }
        
        if not l2_healthy:
            result["healthy"] = False
            result["action"] = "dependency_failure"
            return result
        
        # L3: System consistency
        circuit = self.circuit_breakers.get(overlay_id)
        l3_healthy = circuit is None or circuit.state != CircuitState.OPEN
        result["levels"]["L3_circuit_breaker"] = {
            "healthy": l3_healthy,
            "state": circuit.state.name if circuit else "NO_CIRCUIT"
        }
        
        if not l3_healthy:
            result["healthy"] = False
            result["action"] = "circuit_open"
            return result
        
        # L4: External probe (optional)
        # Could call external monitoring service here
        result["levels"]["L4_external_probe"] = {"healthy": True, "skipped": True}
        
        return result
    
    async def quarantine_overlay(self, overlay_id: str, reason: str) -> None:
        """Quarantine a misbehaving overlay."""
        
        if overlay_id in self.quarantined:
            return
        
        # Terminate the Wasm instance immediately
        await self.overlays.terminate(overlay_id)
        
        self.quarantined.add(overlay_id)
        
        # Record in database
        await self.db.update_overlay_state(
            overlay_id,
            state="QUARANTINED",
            reason=reason
        )
        
        # Publish event for cascade notification
        await self.overlays.events.publish(
            sender="immune_system",
            event_type="overlay_quarantined",
            payload={"overlay_id": overlay_id, "reason": reason}
        )
    
    async def attempt_recovery(self, overlay_id: str) -> bool:
        """Attempt to recover a quarantined overlay."""
        
        if overlay_id not in self.quarantined:
            return False
        
        # Reset circuit breaker
        if overlay_id in self.circuit_breakers:
            self.circuit_breakers[overlay_id] = CircuitBreaker(overlay_id)
        
        # Try to reload
        try:
            await self.overlays.reload(overlay_id)
            
            # Run health check
            health = await self._hierarchical_health_check(overlay_id)
            
            if health["healthy"]:
                self.quarantined.discard(overlay_id)
                await self.db.update_overlay_state(overlay_id, state="ACTIVE")
                return True
            else:
                # Still unhealthy, re-quarantine
                await self.quarantine_overlay(overlay_id, "Recovery failed health check")
                return False
                
        except Exception as e:
            await self.quarantine_overlay(overlay_id, f"Recovery exception: {e}")
            return False
    
    async def start_canary(
        self,
        overlay_id: str,
        new_version_path: str
    ) -> CanaryDeployment:
        """Start a canary deployment for an overlay update."""
        
        current = await self.overlays.get_manifest(overlay_id)
        
        canary = CanaryDeployment(
            overlay_id=overlay_id,
            old_version=current.version,
            new_version=new_version_path
        )
        
        self.canaries[overlay_id] = canary
        
        # Load new version alongside old
        await self.overlays.load_canary(overlay_id, new_version_path)
        
        return canary
    
    async def evaluate_canaries(self) -> list[dict]:
        """Evaluate all active canary deployments."""
        
        results = []
        
        for overlay_id, canary in list(self.canaries.items()):
            action, reason = canary.evaluate()
            
            results.append({
                "overlay_id": overlay_id,
                "action": action,
                "reason": reason
            })
            
            if action == "promote":
                await self.overlays.promote_canary(overlay_id)
                del self.canaries[overlay_id]
            elif action == "rollback":
                await self.overlays.rollback_canary(overlay_id)
                del self.canaries[overlay_id]
        
        return results
```

---

## User-Facing Features

### Authentication & User Management

- User registration (email/password)
- OAuth login (Google, GitHub, Discord)
- Web3 wallet authentication
- Session management
- Two-factor authentication
- Trust flame scoring and reputation

### Capsule Management

- CRUD operations with versioning
- Symbolic inheritance (parent-child relationships)
- Lineage visualization (ancestry tree)
- Semantic search (vector similarity)
- Licensing (public, private, for-sale)
- Tags, categories, sharing

### Symbolic Governance

- Proposal lifecycle: DRAFT → ACTIVE → VOTING → CLOSED
- Trust-weighted voting
- Constitutional AI ethical review
- Ghost Council (AI advisory board)
- Delegation (vote proxy)

### Dashboard & Analytics

- System health status
- Overlay management
- Performance metrics
- Security status
- Governance activity
- Capsule analytics
- ML intelligence insights

### Ghost Chat (AI Interaction)

- Conversational interface
- Capsule knowledge base integration
- Natural language search
- Command execution
- Code generation

---

## API Specification

### Base URL

```
Production: https://api.forge-cascade.io/v2
Staging:    https://api-staging.forge-cascade.io/v2
```

### Authentication

```
Authorization: Bearer <jwt_token>
```

### Core Endpoints

#### Capsules

```
GET    /capsules                    # List (paginated, filterable)
POST   /capsules                    # Create
GET    /capsules/{id}               # Get details
PUT    /capsules/{id}               # Update (creates version)
DELETE /capsules/{id}               # Archive
GET    /capsules/{id}/lineage       # Get ancestry tree
POST   /capsules/{id}/fork          # Create child capsule
GET    /capsules/search?q=...       # Semantic search
```

#### Governance

```
GET    /governance/proposals                  # List proposals
POST   /governance/proposals                  # Create proposal
GET    /governance/proposals/{id}             # Get details
POST   /governance/proposals/{id}/vote        # Cast vote
GET    /governance/proposals/{id}/analysis    # Constitutional AI analysis
```

#### Overlays

```
GET    /overlays                    # List all
POST   /overlays/{id}/enable        # Enable
POST   /overlays/{id}/disable       # Disable
GET    /overlays/{id}/health        # Health check
GET    /overlays/{id}/metrics       # Performance metrics
POST   /overlays/{id}/canary        # Start canary deployment
```

#### System

```
GET    /system/health               # Overall health
GET    /system/metrics              # System metrics
GET    /system/audit-log            # Audit trail
POST   /system/maintenance          # Toggle maintenance mode
```

### WebSocket Endpoints

```
WS /ws/events                       # Real-time event stream
WS /ws/chat                         # Ghost Chat interface
WS /ws/dashboard                    # Dashboard updates
```

---

## Technology Stack

### Core Technologies

| Layer | V1 | V2 | Rationale |
|-------|----|----|-----------|
| **Web Framework** | Quart | FastAPI | Better OpenAPI, native async, Pydantic |
| **Database** | PostgreSQL + Vector DB | Neo4j 5.x | Unified graph + vector + properties |
| **ORM** | SQLAlchemy | neo4j-python-driver | Native async, Cypher queries |
| **Overlay Runtime** | Python + RLIMIT_AS | WebAssembly (Wasmtime) | True isolation, instant termination |
| **ML** | scikit-learn | scikit-learn + ONNX | Same + portable models |

### Full Stack

```yaml
Backend:
  - Python 3.11+
  - FastAPI (ASGI)
  - Pydantic v2 (validation)
  - neo4j-python-driver (async)
  - wasmtime-py (Wasm runtime)
  - uvicorn (ASGI server)

Database:
  - Neo4j 5.x (primary)
  - Redis (caching, sessions)

ML/AI:
  - scikit-learn (anomaly detection)
  - sentence-transformers (embeddings)
  - ONNX (model portability)

Frontend:
  - React 18 (SPA dashboard)
  - TailwindCSS
  - Recharts (visualizations)
  - WebSocket client

DevOps:
  - Docker + Docker Compose
  - Kubernetes (production)
  - ArgoCD (GitOps)
  - GitHub Actions (CI)

Monitoring:
  - Prometheus (metrics)
  - Grafana (dashboards)
  - Jaeger (tracing)
  - Sentry (errors)
```

### Development Environment

```yaml
IDE: VSCode or PyCharm
Python: 3.11+ with venv
Neo4j: Docker (neo4j:5-community) or Aura Free
Wasm Toolchain: Nuitka or Pyodide
Testing: pytest + pytest-asyncio
Linting: ruff + black
Type Checking: mypy
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER                                │
│                      (CloudFlare / Nginx)                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   API Pod 1     │  │   API Pod 2     │  │   API Pod N     │
│   (FastAPI)     │  │   (FastAPI)     │  │   (FastAPI)     │
│                 │  │                 │  │                 │
│ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │
│ │Wasm Runtime │ │  │ │Wasm Runtime │ │  │ │Wasm Runtime │ │
│ │(Overlays)   │ │  │ │(Overlays)   │ │  │ │(Overlays)   │ │
│ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐   ┌─────────────┐   ┌─────────────────┐
│   NEO4J CLUSTER │   │    REDIS    │   │    LLM API      │
│                 │   │   (Cache)   │   │  (Claude/GPT)   │
│ ┌─────┐ ┌─────┐ │   │             │   │                 │
│ │Core │ │Read │ │   │             │   │                 │
│ │Node │ │Repl │ │   │             │   │                 │
│ └─────┘ └─────┘ │   │             │   │                 │
└─────────────────┘   └─────────────┘   └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       MONITORING STACK                               │
│                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ Prometheus │  │  Grafana   │  │   Jaeger   │  │   Sentry   │    │
│  │ (Metrics)  │  │ (Dashboards│  │ (Tracing)  │  │ (Errors)   │    │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Migration Path from V1

### Phase 1: Database Migration (Weeks 1-4)

1. Deploy Neo4j alongside existing PostgreSQL
2. Create migration scripts for:
   - Users → User nodes
   - Capsules → Capsule nodes + DERIVED_FROM relationships
   - Overlays → Overlay nodes
   - Audit logs → AuditLog nodes
3. Generate embeddings for all existing capsules
4. Validate data integrity
5. Switch reads to Neo4j
6. Switch writes to Neo4j
7. Deprecate PostgreSQL

### Phase 2: API Migration (Weeks 5-8)

1. Deploy FastAPI alongside Quart
2. Implement all endpoints in FastAPI
3. Add OpenAPI documentation
4. Gradual traffic migration (10% → 50% → 100%)
5. Deprecate Quart

### Phase 3: Overlay Runtime Migration (Weeks 9-12)

1. Set up Wasm compilation pipeline
2. Compile existing overlays to Wasm
3. Deploy Wasmtime runtime
4. Test each overlay in sandbox
5. Canary deployment for each overlay
6. Remove Python sandbox fallback

### Phase 4: Pipeline Optimization (Weeks 13-14)

1. Implement parallelized pipeline
2. A/B test against sequential pipeline
3. Validate latency improvements
4. Full rollout

---

## Success Metrics

### Technical Metrics

| Metric | V1 Baseline | V2 Target |
|--------|-------------|-----------|
| API latency (P95) | 3.5s | 1.2s |
| Uptime | 99.5% | 99.9% |
| Error rate | 0.5% | 0.1% |
| Auto-recovery rate | 60% | 95% |
| Security incidents | 2/month | 0/month |

### Business Metrics

| Metric | V1 Baseline | V2 Target (12mo) |
|--------|-------------|------------------|
| Enterprise customers | 0 | 50 |
| Average contract value | N/A | $50k |
| Capsule lineage depth | 2.3 | 5.0 |
| Governance participation | 15% | 50% |

### Innovation Metrics

| Metric | Target |
|--------|--------|
| Cascade events/day | 100+ |
| Auto-quarantine success | >95% |
| Canary promotion rate | >90% |
| Lineage trace accuracy | 100% |

---

## Conclusion

This V2 specification addresses the critical issues identified in the feasibility study:

1. **Neo4j unified store** eliminates sync issues between data layers
2. **WebAssembly runtime** provides true security isolation for overlays
3. **Parallelized pipeline** reduces latency from 3.5s to ~1.2s
4. **Enhanced immune system** prevents autoimmune failures with canary deployments

The architecture positions Forge Cascade as enterprise-grade **"Institutional Memory Engine"** infrastructure, not a consumer chatbot competitor.

**Key differentiators preserved:**
- Capsule-based knowledge persistence
- Symbolic inheritance with full lineage tracking
- Self-governance through democratic processes
- Self-healing with intelligent recovery

---

**Document Status:** Living Document  
**Next Review:** Q2 2026  
**Maintainer:** Forge Architecture Team  

---

END OF SPECIFICATION V2
