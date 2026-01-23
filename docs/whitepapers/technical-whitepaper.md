# Forge V3 Technical Whitepaper

**Version 1.0**
**Institutional Memory & Knowledge Governance Engine**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Core Technologies](#3-core-technologies)
4. [Knowledge Capsule System](#4-knowledge-capsule-system)
5. [Overlay Pipeline Architecture](#5-overlay-pipeline-architecture)
6. [Ghost Council: AI Governance](#6-ghost-council-ai-governance)
7. [Trust Flame System](#7-trust-flame-system)
8. [Federation Protocol](#8-federation-protocol)
9. [Security Architecture](#9-security-architecture)
10. [API Reference](#10-api-reference)
11. [Blockchain Integration](#11-blockchain-integration)
12. [Deployment](#12-deployment)

---

## 1. Executive Summary

Forge is an institutional memory and knowledge governance engine designed for the age of AI-generated content. It provides a comprehensive platform for capturing, verifying, governing, and monetizing knowledge through a sophisticated graph-based architecture.

### Core Innovation

Forge introduces seven breakthrough technologies:

1. **Ghost Council** - An AI advisory board of 9+ specialized members that analyzes proposals through tri-perspective analysis (optimistic, balanced, critical) before synthesis
2. **Trust Flame System** - Dynamic reputation scoring (0-100) that affects all system interactions including visibility, voting weight, and access permissions
3. **Isnad Lineage Tracking** - Inspired by Islamic scholarly tradition, tracks knowledge provenance through derivation chains and semantic relationships
4. **7-Phase Overlay Pipeline** - Modular, composable processing units with resource constraints (fuel budgets) for predictable execution
5. **Cascade Effect** - Event-driven knowledge propagation that ripples through the graph when capsules are created or modified
6. **Immune System** - Self-healing infrastructure with circuit breakers, canary deployments, and anomaly detection
7. **Federation Protocol** - Secure peer-to-peer knowledge sharing with Ed25519 cryptographic trust

### Technical Highlights

- **Async-First Architecture**: Pure async/await Python with FastAPI for high concurrency
- **Graph Database**: Neo4j for complex relationship traversal and knowledge representation
- **Production Security**: 4 audit cycles implementing enterprise-grade protections
- **Multi-Chain Ready**: Solana and EVM blockchain integration via Virtuals Protocol

---

## 2. System Architecture Overview

### 2.1 Layered Architecture

Forge implements a 5-layer architecture designed for modularity, testability, and scalability:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│         React 18/19 Frontend + WebSocket Handlers               │
├─────────────────────────────────────────────────────────────────┤
│                      API LAYER                                  │
│    FastAPI Routes + Middleware Stack (12 layers)                │
├─────────────────────────────────────────────────────────────────┤
│                  APPLICATION LAYER                              │
│    Services (Ghost Council, Marketplace, Search, LLM, etc.)     │
├─────────────────────────────────────────────────────────────────┤
│                    DOMAIN LAYER                                 │
│    Models + Repository Pattern + Event System                   │
├─────────────────────────────────────────────────────────────────┤
│                 INFRASTRUCTURE LAYER                            │
│      Neo4j + Redis + External Integrations                      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Architecture

```
                           ┌──────────────────┐
                           │   React Frontend │
                           │  (Marketplace +  │
                           │   Dashboard)     │
                           └────────┬─────────┘
                                    │ HTTP/WebSocket
                           ┌────────▼─────────┐
                           │    API Gateway   │
                           │   (Middleware)   │
                           └────────┬─────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Cascade     │         │   Compliance    │         │    Virtuals     │
│     API       │         │      API        │         │      API        │
│   (Port 8001) │         │   (Port 8002)   │         │   (Port 8003)   │
└───────┬───────┘         └────────┬────────┘         └────────┬────────┘
        │                          │                           │
        └──────────────────────────┼───────────────────────────┘
                                   │
                           ┌───────▼───────┐
                           │  Event Bus    │
                           │  (Pub/Sub)    │
                           └───────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
            ┌─────────────┐ ┌───────────┐ ┌─────────────┐
            │   Overlay   │ │  Overlay  │ │   Overlay   │
            │   Manager   │ │  Manager  │ │   Manager   │
            └──────┬──────┘ └─────┬─────┘ └──────┬──────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  │
                          ┌───────▼───────┐
                          │    Neo4j      │
                          │  (Graph DB)   │
                          └───────────────┘
```

### 2.3 Data Flow

**Request Processing Pipeline:**

```
Client Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MIDDLEWARE STACK                            │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐   │
│  │Security  │→│Correlation │→│Rate Limit  │→│Authentication│   │
│  │Headers   │ │ID          │ │            │ │              │   │
│  └──────────┘ └────────────┘ └────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OVERLAY PIPELINE                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │1.Ingest  │→│2.Analysis│→│3.Validate│→│4.Consensus│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │5.Execute │→│6.Propagate│→│7.Settle │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────┐
│  Neo4j Graph    │
│  (Persistence)  │
└─────────────────┘
     │
     ▼
Response to Client
```

---

## 3. Core Technologies

### 3.1 Neo4j Knowledge Graph

Forge uses Neo4j as its primary data store, chosen for its native graph capabilities essential for knowledge representation.

**Why Graph Database:**
- **Relationship-First**: Knowledge is inherently relational; capsules derive from, support, or contradict others
- **Traversal Performance**: O(1) relationship traversal regardless of dataset size
- **Schema Flexibility**: Evolving knowledge structures without migrations
- **Native Graph Algorithms**: Built-in PageRank, community detection, centrality measures

**Schema Overview:**

```
Node Types:
├── User (id, username, email, trust_score, role, capabilities)
├── Capsule (id, content, type, version, embedding[1536], hash)
├── CapsuleVersion (id, content, version, created_at, parent_version)
├── Proposal (id, title, description, status, votes_for, votes_against)
├── Vote (id, choice, weight, timestamp)
├── Overlay (id, name, status, config, metrics)
├── Event (id, type, priority, payload, timestamp)
├── AuditLog (id, action, actor_id, resource_id, timestamp)
└── FederatedPeer (id, url, public_key, trust_score, status)

Relationships:
├── (User)-[:CREATES]->(Capsule)
├── (Capsule)-[:DERIVES_FROM]->(Capsule)       # Lineage
├── (Capsule)-[:SUPPORTS]->(Capsule)           # Semantic
├── (Capsule)-[:CONTRADICTS]->(Capsule)        # Semantic
├── (Capsule)-[:ELABORATES]->(Capsule)         # Semantic
├── (Capsule)-[:HAS_VERSION]->(CapsuleVersion)
├── (User)-[:CASTS]->(Vote)-[:ON]->(Proposal)
├── (Overlay)-[:SUBSCRIBES_TO]->(Event)
└── (FederatedPeer)-[:SYNCS_WITH]->(FederatedPeer)
```

**Indexes and Constraints:**

```cypher
-- Unique constraints
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE;
CREATE CONSTRAINT capsule_id IF NOT EXISTS FOR (c:Capsule) REQUIRE c.id IS UNIQUE;

-- Vector index for semantic search
CREATE VECTOR INDEX capsule_embedding IF NOT EXISTS
FOR (c:Capsule) ON (c.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}};

-- Full-text search
CREATE FULLTEXT INDEX capsule_content IF NOT EXISTS FOR (c:Capsule) ON EACH [c.content, c.title];
```

### 3.2 FastAPI Async Architecture

The backend is built on FastAPI with pure async/await patterns throughout:

**Key Characteristics:**
- **Async Database**: All Neo4j operations use async drivers
- **Non-Blocking I/O**: File operations, HTTP calls, and message queues are async
- **Connection Pooling**: Max 50 connections with 3600s lifetime
- **Dependency Injection**: FastAPI's `Depends()` for clean IoC

**Application Factory Pattern:**

```python
class ForgeApp:
    """Singleton container for all core components."""

    db_client: DatabaseClient
    event_system: EventSystem
    overlay_manager: OverlayManager
    immune_system: ImmuneSystem
    services: Dict[str, Any]
    resilience_layer: ResilienceLayer

    async def initialize(self):
        """Ordered initialization sequence with error recovery."""
        self.db_client = await DatabaseClient.create()
        self.event_system = EventSystem(cascade_repository=...)
        self.overlay_manager = OverlayManager(event_bus=self.event_system.bus)
        # ... register core overlays
        self.immune_system = ImmuneSystem()
        self.resilience_layer = ResilienceLayer()
```

### 3.3 React Frontend Stack

**Technology Stack:**
- **Framework**: React 18 (Dashboard) / React 19 (Marketplace)
- **Build Tool**: Vite for fast development and optimized builds
- **State Management**: Zustand for auth + TanStack React Query for server state
- **Styling**: Tailwind CSS v4 with PostCSS
- **HTTP Client**: Axios with custom interceptors

**State Management Pattern:**

```typescript
// Auth store (Zustand - client state)
const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  login: async (credentials) => { ... },
  logout: async () => { ... },
}));

// Server state (React Query)
const { data: proposals } = useQuery({
  queryKey: ['proposals'],
  queryFn: () => api.getProposals(),
  staleTime: 60000,
  retry: 1,
});
```

---

## 4. Knowledge Capsule System

### 4.1 Capsule Data Model

Capsules are the atomic units of knowledge in Forge:

```python
@dataclass
class Capsule:
    id: str                    # UUID
    content: str               # Max 100KB
    title: str                 # Human-readable title
    type: CapsuleType          # KNOWLEDGE, PROMPT, CODE, DATASET, RITUAL
    version: str               # Semantic versioning (1.0.0)
    creator_id: str            # User who created

    # Integrity
    content_hash: str          # SHA-256 of content
    signature: str | None      # Ed25519 signature (Phase 2+)

    # Semantic
    embedding: list[float]     # 1536-dimensional vector
    tags: list[str]            # User-defined tags

    # Lineage
    parent_ids: list[str]      # Direct derivation sources
    derived_at: datetime       # When derived

    # Metadata
    created_at: datetime
    updated_at: datetime
    trust_score: float         # Aggregated trust from lineage
    view_count: int
    citation_count: int

class CapsuleType(Enum):
    KNOWLEDGE = "knowledge"    # General information
    PROMPT = "prompt"          # AI prompt templates
    CODE = "code"              # Source code
    DATASET = "dataset"        # Structured data
    RITUAL = "ritual"          # Procedural knowledge
```

### 4.2 Versioning Strategy

Forge implements a **hybrid versioning** approach:

```
┌─────────────────────────────────────────────────────────────┐
│                     VERSIONING STRATEGY                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Routine Changes         Major Changes                     │
│   ──────────────         ──────────────                     │
│   ┌─────┐                ┌─────────────┐                   │
│   │Diff │  ←───────────  │Full Snapshot│                   │
│   │Only │                │             │                   │
│   └─────┘                └─────────────┘                   │
│                                                             │
│   When:                  When:                              │
│   • Minor edits          • Trust level upgrade              │
│   • Typo fixes           • Every N changes                  │
│   • Small additions      • Major content overhaul           │
│                          • Explicit user request            │
│                                                             │
│   Compaction: After 30 days, diffs are merged into          │
│   consolidated snapshots for storage efficiency             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Version Chain Example:**

```
v1.0.0 (Snapshot)
    │
    ├── v1.0.1 (Diff: +3 lines)
    ├── v1.0.2 (Diff: -1 line, +2 lines)
    └── v1.1.0 (Snapshot - major change)
            │
            ├── v1.1.1 (Diff: +5 lines)
            └── v1.1.2 (Diff: +1 line)
```

### 4.3 Isnad Lineage Tracking

Inspired by the Islamic scholarly tradition of *Isnad* (chain of transmission), Forge tracks knowledge provenance:

**Semantic Edge Types:**

| Edge Type | Description | Example |
|-----------|-------------|---------|
| `DERIVES_FROM` | Direct derivation | A quote includes source |
| `SUPPORTS` | Evidence backing | Research validates claim |
| `CONTRADICTS` | Opposing information | Counter-argument |
| `ELABORATES` | Expands upon | Detailed explanation |
| `REFERENCES` | Loose citation | Mentions related work |
| `RELATED_TO` | Topical similarity | Same domain |

**Lineage Node Structure:**

```python
@dataclass
class LineageNode:
    capsule_id: str
    parent_ids: list[str]
    child_ids: list[str]
    semantic_edges: list[SemanticEdgeInfo]
    depth: int                 # Distance from root
    influence_score: float     # PageRank-based
    descendant_count: int      # Number of derivatives
    trust_gradient: float      # Trust decay from origin
```

**Anomaly Detection:**
- Circular references (A → B → A)
- Broken chains (missing parent)
- Trust gradient violations (child more trusted than parent)
- Orphaned nodes (no connections)

### 4.4 Integrity Verification

**Multi-Phase Security Model:**

```
Phase 1 (Current):     SHA-256 Content Hashing
                       ─────────────────────────
                       • Hash computed on creation
                       • Verified on retrieval
                       • Detects tampering

Phase 2 (Implemented): Ed25519 Digital Signatures
                       ─────────────────────────
                       • Creator signs capsule
                       • Public key verification
                       • Non-repudiation

Phase 3 (Planned):     Merkle Tree Lineage
                       ─────────────────────────
                       • Full lineage hash tree
                       • Efficient subset verification
                       • Tamper-evident history
```

**Hash Computation:**

```python
def compute_capsule_hash(capsule: Capsule) -> str:
    """Compute SHA-256 hash of capsule content."""
    content = f"{capsule.id}:{capsule.content}:{capsule.version}"
    return hashlib.sha256(content.encode()).hexdigest()

def verify_capsule_integrity(capsule: Capsule) -> bool:
    """Verify capsule has not been tampered with."""
    computed = compute_capsule_hash(capsule)
    return hmac.compare_digest(computed, capsule.content_hash)
```

---

## 5. Overlay Pipeline Architecture

### 5.1 The 7-Phase Pipeline

Overlays are modular processing units that handle specialized aspects of the knowledge lifecycle:

```
┌─────────────────────────────────────────────────────────────────┐
│                    7-PHASE OVERLAY PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: INGESTION                                             │
│  ───────────────────                                            │
│  • Input normalization                                          │
│  • Format validation                                            │
│  • Content extraction                                           │
│                                                                 │
│  Phase 2: ANALYSIS         ┌─────────────────────────┐          │
│  ─────────────────         │  ML Intelligence        │          │
│  • Entity extraction  ────▶│  Overlay                │          │
│  • Classification          │  • Embeddings           │          │
│  • Embedding generation    │  • Classification       │          │
│                            │  • Pattern detection    │          │
│                            └─────────────────────────┘          │
│                                                                 │
│  Phase 3: VALIDATION       ┌─────────────────────────┐          │
│  ───────────────────       │  Security Validator     │          │
│  • Content policies   ────▶│  Overlay                │          │
│  • Trust verification      │  • XSS detection        │          │
│  • Rate limit checks       │  • SQL injection check  │          │
│                            │  • Trust level verify   │          │
│                            └─────────────────────────┘          │
│                                                                 │
│  Phase 4: CONSENSUS        ┌─────────────────────────┐          │
│  ──────────────────        │  Governance Overlay     │          │
│  • Voting required?   ────▶│  • Policy evaluation    │          │
│  • Quorum checks           │  • Vote tallying        │          │
│  • Policy enforcement      │  • Trust-weighted calc  │          │
│                            └─────────────────────────┘          │
│                                                                 │
│  Phase 5: EXECUTION                                             │
│  ──────────────────                                             │
│  • Core operation                                               │
│  • Database writes                                              │
│  • Resource allocation                                          │
│                                                                 │
│  Phase 6: PROPAGATION                                           │
│  ────────────────────                                           │
│  • Cascade event emission                                       │
│  • Downstream notifications                                     │
│  • Cache invalidation                                           │
│                                                                 │
│  Phase 7: SETTLEMENT       ┌─────────────────────────┐          │
│  ────────────────────      │  Lineage Tracker        │          │
│  • Lineage recording  ────▶│  Overlay                │          │
│  • Trust updates           │  • Derivation tracking  │          │
│  • Audit logging           │  • Isnad computation    │          │
│                            └─────────────────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Overlay Base Architecture

```python
@dataclass
class OverlayContext:
    """Context passed to each overlay execution."""
    overlay_id: str
    execution_id: str
    user_id: str | None
    trust_flame: int = 60            # User's trust score
    capabilities: set[Capability]    # What this overlay can do
    fuel_budget: FuelBudget         # Resource constraints

@dataclass
class FuelBudget:
    """Resource constraints for overlay execution."""
    max_fuel: int = 1_000_000       # Function call limit
    max_memory_bytes: int = 10_485_760  # 10 MB
    timeout_ms: int = 5_000         # 5 seconds

@dataclass
class OverlayResult:
    """Result from overlay execution."""
    success: bool
    data: dict[str, Any] | None
    error: str | None
    events_to_emit: list[dict]      # Cascade events
    metrics: dict[str, Any]
    duration_ms: float

class BaseOverlay(ABC):
    """Abstract base for all overlays."""

    name: str
    version: str
    phase: PipelinePhase

    @abstractmethod
    async def execute(
        self,
        context: OverlayContext,
        event: Event,
        input_data: dict
    ) -> OverlayResult:
        """Main processing logic."""
        pass

    async def initialize(self) -> bool:
        """Called on startup."""
        return True

    async def cleanup(self) -> None:
        """Called on shutdown."""
        pass

    async def health_check(self) -> OverlayHealthCheck:
        """Report overlay health status."""
        return OverlayHealthCheck(
            status="healthy",
            execution_count=self._execution_count,
            error_rate=self._error_count / max(self._execution_count, 1),
            last_error=self._last_error
        )
```

### 5.3 Core Overlays

#### Security Validator Overlay

**Purpose**: Content validation and threat detection

**Rules Framework:**
```python
class ContentPolicyRule:
    """Pattern-based content validation."""
    pattern: str              # Regex pattern
    action: RuleAction        # BLOCK, WARN, LOG
    message: str              # User feedback

class TrustRule:
    """Trust level requirements."""
    min_trust: int            # Minimum trust score
    operation: str            # Operation being attempted

class RateLimitRule:
    """Rate limiting per operation."""
    max_requests: int
    window_seconds: int
    scope: str                # per_user, per_ip, global
```

**Threat Detection:**
- XSS pattern matching (with ReDoS protection)
- SQL injection detection
- Large payload detection (>10MB)
- Regex timeout protection (500ms limit)

#### ML Intelligence Overlay

**Purpose**: Semantic analysis and classification

**Capabilities:**
- **Embeddings**: 1536-dimensional vectors (OpenAI text-embedding-3-small)
- **Classification**: Content type and category with confidence scores
- **Entity Extraction**: Named entities and relationships
- **Sentiment Analysis**: -1.0 to 1.0 scoring
- **Keyword Extraction**: Domain-relevant terms

**Caching:**
- Embedding cache: 50,000 entries max
- TTL: Configurable per operation
- LRU eviction on capacity

#### Governance Overlay

**Purpose**: Democratic consensus and policy enforcement

**Voting Mechanics:**
```python
def calculate_weighted_vote(user: User, choice: VoteChoice) -> float:
    """Trust-weighted voting calculation."""
    base_weight = 1.0
    trust_multiplier = user.trust_score / 100.0  # 0-1 scale
    return base_weight * trust_multiplier

def check_quorum(proposal: Proposal, votes: list[Vote]) -> bool:
    """Check if quorum has been reached."""
    eligible_voters = get_eligible_voters(proposal)
    participation = len(votes) / len(eligible_voters)
    return participation >= proposal.quorum_threshold  # Default 50%

def determine_outcome(proposal: Proposal, votes: list[Vote]) -> ProposalOutcome:
    """Determine proposal outcome."""
    weighted_for = sum(v.weight for v in votes if v.choice == FOR)
    weighted_against = sum(v.weight for v in votes if v.choice == AGAINST)
    total = weighted_for + weighted_against

    if total == 0:
        return ProposalOutcome.NO_VOTES

    approval_rate = weighted_for / total
    if approval_rate >= proposal.pass_threshold:  # Default 66%
        return ProposalOutcome.PASSED
    return ProposalOutcome.REJECTED
```

**Declarative Policy Rules:**
```python
# Safe condition operators (no code execution)
OPERATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "exists": lambda a, _: a is not None,
    "not_exists": lambda a, _: a is None,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}

# Example policy rule
policy = {
    "condition": {
        "and": [
            {"field": "proposer_trust", "op": "ge", "value": 50},
            {"field": "content_type", "op": "eq", "value": "CRITICAL"}
        ]
    },
    "action": "require_ghost_council_review"
}
```

#### Lineage Tracker Overlay

**Purpose**: Track capsule ancestry and provenance

**Isnad Analysis:**
```python
async def compute_lineage(capsule_id: str) -> LineageTree:
    """Compute full lineage tree for a capsule."""
    ancestors = await trace_ancestors(capsule_id, max_depth=50)
    descendants = await trace_descendants(capsule_id, max_depth=50)
    semantic_edges = await get_semantic_relationships(capsule_id)

    return LineageTree(
        root=capsule_id,
        ancestors=ancestors,
        descendants=descendants,
        semantic_edges=semantic_edges,
        influence_score=compute_pagerank_score(capsule_id),
        trust_gradient=compute_trust_decay(ancestors)
    )
```

**Metrics:**
- Lineage depth distribution
- Most influential capsules (by descendant count)
- Orphaned nodes
- Trust decay across generations

#### Temporal Tracker Overlay

**Purpose**: Versioning and time-travel queries

**Capabilities:**
```python
async def get_version_at(capsule_id: str, timestamp: datetime) -> CapsuleVersion:
    """Retrieve capsule state at a specific point in time."""
    versions = await get_versions_before(capsule_id, timestamp)
    if not versions:
        raise VersionNotFound(f"No version exists before {timestamp}")

    # Apply diffs if needed
    base = find_nearest_snapshot(versions)
    return apply_diffs(base, versions)

async def diff_versions(v1_id: str, v2_id: str) -> VersionDiff:
    """Compute diff between two versions."""
    v1 = await get_version(v1_id)
    v2 = await get_version(v2_id)
    return compute_diff(v1.content, v2.content)

async def create_graph_snapshot() -> GraphSnapshot:
    """Create a full graph state snapshot."""
    return GraphSnapshot(
        timestamp=datetime.utcnow(),
        node_count=await count_nodes(),
        edge_count=await count_edges(),
        trust_distribution=await compute_trust_distribution(),
        top_capsules=await get_top_by_pagerank(100)
    )
```

#### Graph Algorithms Overlay

**Purpose**: Analytical algorithms on knowledge graph

**Algorithms:**

| Algorithm | Purpose | Implementation |
|-----------|---------|----------------|
| **PageRank** | Importance ranking | Neo4j GDS / Pure Cypher |
| **Betweenness Centrality** | Bridge identification | Neo4j GDS |
| **Community Detection** | Cluster identification | Louvain / Label Propagation |
| **Trust Transitivity** | Multi-hop trust | Custom (max 5 hops, 0.9 decay) |

**Configuration:**
```python
class PageRankConfig:
    damping_factor: float = 0.85
    max_iterations: int = 20
    tolerance: float = 1e-6

class TrustTransitivityConfig:
    max_hops: int = 5
    decay_per_hop: float = 0.9
    min_trust_threshold: float = 0.1
```

#### Knowledge Query Overlay

**Purpose**: Natural language querying

**Pipeline:**
```
Natural Language Query
         │
         ▼
┌─────────────────────┐
│  Intent Extraction  │ ← LLM identifies query type
│  (LLM)              │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Schema Mapping     │ ← Maps entities to Neo4j labels
│                     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Cypher Generation  │ ← Builds parameterized query
│  (LLM)              │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Query Validation   │ ← Rejects write/delete operations
│                     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Execution          │ ← Runs against Neo4j
│                     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Answer Synthesis   │ ← LLM creates human response
│  (LLM)              │
└─────────────────────┘
```

**Security:**
- CypherValidator rejects `CREATE`, `DELETE`, `SET`, `MERGE`
- Parameterized queries prevent injection
- Trust-level filtering on results

### 5.4 Fuel Budget System

Resource constraints prevent runaway overlays:

```python
class FuelBudgetEnforcer:
    """Enforces resource limits on overlay execution."""

    def __init__(self, budget: FuelBudget):
        self.budget = budget
        self.fuel_consumed = 0
        self.start_time = time.monotonic()

    def consume_fuel(self, amount: int = 1):
        """Consume fuel for an operation."""
        self.fuel_consumed += amount
        if self.fuel_consumed > self.budget.max_fuel:
            raise FuelExhausted("Overlay exceeded fuel budget")

    def check_timeout(self):
        """Check if timeout has been exceeded."""
        elapsed_ms = (time.monotonic() - self.start_time) * 1000
        if elapsed_ms > self.budget.timeout_ms:
            raise TimeoutExceeded("Overlay exceeded time budget")

    def check_memory(self):
        """Check memory usage."""
        import tracemalloc
        current, _ = tracemalloc.get_traced_memory()
        if current > self.budget.max_memory_bytes:
            raise MemoryExceeded("Overlay exceeded memory budget")
```

---

## 6. Ghost Council: AI Governance

### 6.1 Overview

The Ghost Council is an AI-powered advisory board that provides multi-perspective analysis on proposals and system issues. It represents a novel approach to synthetic governance.

### 6.2 Council Composition

**9+ Specialized Members:**

| Member | Domain | Icon | Weight | Focus Areas |
|--------|--------|------|--------|-------------|
| **Sophia** (Ethics) | Ethics Guardian | Scale | 2.0x | Moral philosophy, fairness, societal impact |
| **Marcus** (Security) | Security Sentinel | Shield | 2.0x | Threat analysis, resilience, compliance |
| **Aria** (Governance) | Governance Guide | GitBranch | 2.0x | Policy, voting systems, precedent |
| **Zen** (Technical) | System Steward | CPU | 1.0x | Performance, reliability, scalability |
| **Nova** (Innovation) | Innovation Scout | Lightbulb | 1.0x | Progress, experimentation, emerging patterns |
| **Atlas** (Data) | Data Specialist | Database | 1.0x | Privacy, analytics, data implications |
| **Harmony** (Community) | Community Advocate | Users | 1.0x | User experience, adoption, accessibility |
| **Phoenix** (Economics) | Economics Analyst | TrendingUp | 1.0x | Cost-benefit, incentives, ROI |
| **Prudence** (Risk) | Risk Manager | AlertTriangle | 1.0x | Failure modes, worst-cases, mitigation |

### 6.3 Tri-Perspective Analysis

Each council member analyzes from three distinct viewpoints:

```
┌─────────────────────────────────────────────────────────────────┐
│                   TRI-PERSPECTIVE ANALYSIS                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                        PROPOSAL                                 │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                   │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│   │OPTIMISTIC│     │ BALANCED │     │ CRITICAL │               │
│   └────┬─────┘     └────┬─────┘     └────┬─────┘               │
│        │                │                │                      │
│    Benefits         Facts &          Risks &                    │
│    Opportunities    Trade-offs       Concerns                   │
│    Best outcomes    Alternatives     Worst cases                │
│    Positive         Realistic        Potential                  │
│    precedents       expectations     failures                   │
│        │                │                │                      │
│        └────────────────┼────────────────┘                      │
│                         │                                       │
│                         ▼                                       │
│              ┌────────────────────┐                             │
│              │    SYNTHESIS       │                             │
│              │  Weighted average  │                             │
│              │  of perspectives   │                             │
│              └────────────────────┘                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.4 Decision Synthesis Algorithm

```python
async def synthesize_council_decision(
    proposal: Proposal,
    profile: str = "comprehensive"  # quick, standard, comprehensive
) -> GhostCouncilDecision:
    """
    Synthesize Ghost Council decision from all member opinions.
    """
    # Select members based on profile
    if profile == "quick":
        members = [get_member("ethics")]  # 1 member
    elif profile == "standard":
        members = [get_member("ethics"), get_member("security"),
                   get_member("governance")]  # 3 members
    else:  # comprehensive
        members = get_all_members()  # 9+ members

    opinions = []
    for member in members:
        # Each member provides tri-perspective analysis
        optimistic = await member.analyze(proposal, Perspective.OPTIMISTIC)
        balanced = await member.analyze(proposal, Perspective.BALANCED)
        critical = await member.analyze(proposal, Perspective.CRITICAL)

        # Member synthesizes their position
        position = member.synthesize([optimistic, balanced, critical])
        opinions.append(MemberOpinion(
            member=member,
            perspectives=[optimistic, balanced, critical],
            position=position,
            confidence=position.confidence,
            weight=member.weight
        ))

    # Aggregate all opinions
    weighted_scores = []
    for opinion in opinions:
        score = opinion.position.approval_score * opinion.weight
        weighted_scores.append(score)

    final_score = sum(weighted_scores) / sum(m.weight for m in members)

    return GhostCouncilDecision(
        recommendation=Recommendation.APPROVE if final_score > 0.5 else Recommendation.REJECT,
        confidence=compute_confidence(opinions),
        reasoning=synthesize_reasoning(opinions),
        member_opinions=opinions,
        historical_patterns=await find_similar_decisions(proposal)
    )
```

### 6.5 Caching and Optimization

**Cost Profiles:**

| Profile | Members | LLM Calls | Use Case |
|---------|---------|-----------|----------|
| Quick | 1 | 3 | Low-stakes decisions |
| Standard | 3 | 9 | Normal proposals |
| Comprehensive | 9+ | 27+ | High-impact decisions |

**Caching:**
- Opinion cache: 30-day TTL
- Cache key: `{proposal_hash}:{member_id}:{perspective}`
- Cache hits tracked in stats

---

## 7. Trust Flame System

### 7.1 Overview

Trust Flame is a dynamic reputation system that quantifies user trustworthiness on a 0-100 scale. Unlike static role-based access, trust evolves based on behavior.

### 7.2 Trust Levels

```
┌─────────────────────────────────────────────────────────────────┐
│                      TRUST LEVELS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  100 ┌─────────────────────────────────────────────────────┐   │
│      │                     CORE                             │   │
│      │  • Full system access                                │   │
│      │  • Immune to rate limits                             │   │
│      │  • Can modify trust of others                        │   │
│   80 ├─────────────────────────────────────────────────────┤   │
│      │                    TRUSTED                           │   │
│      │  • Governance participation                          │   │
│      │  • 2x rate limit multiplier                          │   │
│      │  • Priority federation sync                          │   │
│   60 ├─────────────────────────────────────────────────────┤   │
│      │                   STANDARD                           │   │
│      │  • Default new user level                            │   │
│      │  • Normal rate limits                                │   │
│      │  • Full read/write access                            │   │
│   40 ├─────────────────────────────────────────────────────┤   │
│      │                    SANDBOX                           │   │
│      │  • Experimental users                                │   │
│      │  • 0.5x rate limit                                   │   │
│      │  • Heavy monitoring                                  │   │
│   0  ├─────────────────────────────────────────────────────┤   │
│      │                  QUARANTINE                          │   │
│      │  • Blocked from most operations                      │   │
│      │  • 0.1x rate limit                                   │   │
│      │  • Under review                                      │   │
│      └─────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Trust Score Mechanics

**Score Components:**

```python
def calculate_trust_score(user: User) -> float:
    """
    Calculate user's trust score based on multiple factors.
    """
    components = {
        # Contribution quality (40% weight)
        "capsule_quality": capsule_quality_score(user) * 0.40,

        # Community standing (30% weight)
        "community": community_standing_score(user) * 0.30,

        # Verification status (20% weight)
        "verification": verification_score(user) * 0.20,

        # Account age (10% weight)
        "longevity": longevity_score(user) * 0.10,
    }

    base_score = sum(components.values())

    # Apply penalties
    base_score -= policy_violation_penalty(user)
    base_score -= inactivity_decay(user)

    # Clamp to 0-100
    return max(0, min(100, base_score))
```

**Trust Adjustments:**

| Event | Adjustment |
|-------|------------|
| Capsule highly cited | +2 to +5 |
| Proposal approved | +3 |
| Governance participation | +1 |
| Policy violation | -5 to -20 |
| Inactivity (per week) | -1 |
| Verified identity | +10 (one-time) |
| Ghost Council endorsement | +5 |

### 7.4 Trust-Based Permissions

**Capability Matrix:**

| Capability | QUARANTINE | SANDBOX | STANDARD | TRUSTED | CORE |
|------------|------------|---------|----------|---------|------|
| Read capsules | Limited | Yes | Yes | Yes | Yes |
| Create capsules | No | Limited | Yes | Yes | Yes |
| Vote on proposals | No | No | Limited | Yes | Yes |
| Create proposals | No | No | No | Yes | Yes |
| Moderate content | No | No | No | Limited | Yes |
| Manage users | No | No | No | No | Yes |
| System config | No | No | No | No | Yes |

**Rate Limit Multipliers:**

```python
RATE_LIMIT_MULTIPLIERS = {
    TrustLevel.QUARANTINE: 0.1,   # 10% of normal
    TrustLevel.SANDBOX: 0.5,      # 50% of normal
    TrustLevel.STANDARD: 1.0,     # 100% (baseline)
    TrustLevel.TRUSTED: 2.0,      # 200% of normal
    TrustLevel.CORE: 10.0,        # Effectively unlimited
}
```

### 7.5 Trust Decay and Recovery

**Inactivity Decay:**
- Trust decays -1 per week of inactivity
- Minimum decay floor: 30 (SANDBOX level)
- Reactivation via contribution immediately stops decay

**Recovery Path:**

```
QUARANTINE → SANDBOX → STANDARD → TRUSTED → CORE
     │           │          │          │         │
     └───────────┴──────────┴──────────┴─────────┘
           Requires positive contributions
           and time without violations

Typical timeline:
• QUARANTINE → SANDBOX: 1-2 weeks good behavior
• SANDBOX → STANDARD: 2-4 weeks consistent contribution
• STANDARD → TRUSTED: 1-3 months high-quality work
• TRUSTED → CORE: By invitation/exceptional contribution
```

---

## 8. Federation Protocol

### 8.1 Overview

Federation enables secure peer-to-peer knowledge sharing between Forge instances. Each instance maintains sovereignty while participating in a trust network.

### 8.2 Peer Discovery and Handshake

**Handshake Protocol:**

```
┌─────────────┐                              ┌─────────────┐
│   Peer A    │                              │   Peer B    │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       │  1. Discovery Request                      │
       │  ──────────────────────────────────────▶  │
       │     URL + Public Key                       │
       │                                            │
       │  2. Handshake Challenge                    │
       │  ◀──────────────────────────────────────  │
       │     Nonce + Timestamp + B's Public Key     │
       │                                            │
       │  3. Signed Response                        │
       │  ──────────────────────────────────────▶  │
       │     A signs: nonce + timestamp + A's key   │
       │                                            │
       │  4. Verification + Trust Init              │
       │  ◀──────────────────────────────────────  │
       │     Trust score = 0.3 (INITIAL)            │
       │                                            │
       │  5. Connection Established                 │
       │  ◀─────────────────────────────────────▶  │
       │                                            │
```

**PeerHandshake Structure:**

```python
@dataclass
class PeerHandshake:
    instance_id: str
    instance_name: str
    api_version: str = "1.0"
    public_key: str              # Base64 Ed25519
    timestamp: str               # ISO8601
    nonce: str                   # 32-char hex (128 bits)
    signature: str               # Base64 Ed25519 signature
    supports_push: bool = True
    supports_pull: bool = True
    max_capsules_per_sync: int = 1000
    suggested_interval_minutes: int = 60
```

### 8.3 Trust Management

**Trust Tiers:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEDERATION TRUST TIERS                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Score    │ Tier       │ Permissions                            │
│  ─────────┼────────────┼──────────────────────────────────────  │
│  0.8-1.0  │ CORE       │ Auto-accept, 5x rate, bidirectional   │
│  0.6-0.8  │ TRUSTED    │ Priority sync, 2x rate, bidirectional │
│  0.4-0.6  │ STANDARD   │ Normal sync, 1x rate, bidirectional   │
│  0.2-0.4  │ LIMITED    │ Pull-only, 0.5x rate, review required │
│  0.0-0.2  │ QUARANTINE │ No sync allowed                       │
│                                                                 │
│  Trust Adjustments:                                             │
│  • Sync success:      +0.02                                     │
│  • Sync failure:      -0.05                                     │
│  • Conflict resolved: -0.01                                     │
│  • Inactivity/week:   -0.01 (min: INITIAL_TRUST)                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Trust Recommendations:**

```python
async def generate_trust_recommendation(peer_id: str) -> TrustRecommendation:
    """Generate recommendation based on peer behavior."""
    history = await get_peer_history(peer_id)

    consecutive_failures = count_consecutive_failures(history)
    consecutive_successes = count_consecutive_successes(history)

    if consecutive_failures >= 3:
        return TrustRecommendation(
            action="DECREASE",
            reason=f"{consecutive_failures} consecutive sync failures",
            suggested_adjustment=-0.1
        )

    if consecutive_successes >= 10:
        return TrustRecommendation(
            action="INCREASE",
            reason=f"{consecutive_successes} consecutive successful syncs",
            suggested_adjustment=+0.05
        )

    return TrustRecommendation(action="MAINTAIN", reason="Normal operation")
```

### 8.4 Sync Mechanisms

**Sync Phases:**

```
Phase 1: INIT
    • Validate peer trust level
    • Check sync permissions
    • Acquire sync lock

Phase 2: FETCHING
    • Request changes since last sync
    • Receive capsule batch (max 1000)
    • Verify signatures

Phase 3: PROCESSING
    • Validate each capsule
    • Check for conflicts
    • Compute lineage impacts

Phase 4: APPLYING
    • Write to local database
    • Update trust scores
    • Emit cascade events

Phase 5: FINALIZING
    • Update sync metadata
    • Release lock
    • Record metrics
```

**Conflict Resolution:**

```python
class ConflictStrategy(Enum):
    KEEP_LATEST = "keep_latest"      # Timestamp-based
    KEEP_REMOTE = "keep_remote"      # Always accept external
    KEEP_LOCAL = "keep_local"        # Always keep local
    CUSTOM = "custom"                # User-defined

async def resolve_conflict(
    local: Capsule,
    remote: Capsule,
    strategy: ConflictStrategy
) -> Capsule:
    if strategy == ConflictStrategy.KEEP_LATEST:
        return local if local.updated_at > remote.updated_at else remote
    elif strategy == ConflictStrategy.KEEP_REMOTE:
        return remote
    elif strategy == ConflictStrategy.KEEP_LOCAL:
        return local
    else:
        return await custom_resolution(local, remote)
```

### 8.5 Security Measures

**SSRF Protection:**

```python
BLOCKED_IP_RANGES = [
    "10.0.0.0/8",        # Private
    "172.16.0.0/12",     # Private
    "192.168.0.0/16",    # Private
    "127.0.0.0/8",       # Loopback
    "169.254.0.0/16",    # Link-local
    "0.0.0.0/8",         # Invalid
]

BLOCKED_HOSTNAMES = [
    "localhost",
    "127.0.0.1",
    "metadata.google.internal",
    "169.254.169.254",   # AWS metadata
]

def validate_federation_url(url: str) -> bool:
    """Prevent SSRF attacks."""
    parsed = urlparse(url)

    # Block non-HTTPS in production
    if PRODUCTION and parsed.scheme != "https":
        return False

    # Resolve hostname
    try:
        ip = socket.gethostbyname(parsed.hostname)
    except socket.gaierror:
        return False

    # Check against blocked ranges
    ip_obj = ipaddress.ip_address(ip)
    for range_str in BLOCKED_IP_RANGES:
        if ip_obj in ipaddress.ip_network(range_str):
            return False

    return True
```

**DNS Pinning:**

```python
class DNSPinStore:
    """Stores resolved IPs at validation time to prevent DNS rebinding."""

    def __init__(self, ttl_seconds: int = 300, max_pins: int = 10_000):
        self.pins: dict[str, DNSPin] = {}
        self.ttl = ttl_seconds
        self.max_pins = max_pins

    def pin(self, hostname: str, addresses: list[str]) -> None:
        """Store resolved addresses for hostname."""
        if len(self.pins) >= self.max_pins:
            self._evict_oldest()

        self.pins[hostname] = DNSPin(
            hostname=hostname,
            addresses=addresses,
            created_at=datetime.utcnow()
        )

    def verify(self, hostname: str, address: str) -> bool:
        """Verify address matches pinned resolution."""
        pin = self.pins.get(hostname)
        if not pin:
            return False
        if pin.is_expired(self.ttl):
            del self.pins[hostname]
            return False
        return address in pin.addresses
```

**TLS Certificate Pinning:**

```python
class CertificatePinStore:
    """SHA-256 fingerprint pinning with TOFU model."""

    def pin_certificate(self, hostname: str, cert_der: bytes) -> None:
        """Pin certificate fingerprint."""
        fingerprint = hashlib.sha256(cert_der).hexdigest()
        self.pins[hostname] = CertificatePin(
            hostname=hostname,
            fingerprint=fingerprint,
            pinned_at=datetime.utcnow()
        )

    def verify_certificate(self, hostname: str, cert_der: bytes) -> bool:
        """Verify certificate matches pinned fingerprint."""
        pin = self.pins.get(hostname)
        if not pin:
            # TOFU: Trust on first use
            self.pin_certificate(hostname, cert_der)
            return True

        fingerprint = hashlib.sha256(cert_der).hexdigest()
        return hmac.compare_digest(fingerprint, pin.fingerprint)
```

**Nonce-Based Replay Prevention:**

```python
class NonceStore:
    """Prevents replay attacks with nonce tracking."""

    TTL_SECONDS = 3600  # 1 hour
    MAX_NONCES = 100_000

    def __init__(self):
        self.nonces: dict[str, datetime] = {}
        self.lock = asyncio.Lock()

    async def check_and_add(self, nonce: str) -> bool:
        """
        Check if nonce is valid (not seen before).
        Returns True if valid, False if replay detected.
        """
        async with self.lock:
            self._cleanup_expired()

            if nonce in self.nonces:
                return False  # Replay detected

            if len(self.nonces) >= self.MAX_NONCES:
                self._evict_oldest()

            self.nonces[nonce] = datetime.utcnow()
            return True
```

---

## 9. Security Architecture

### 9.1 Authentication

**JWT Token System:**

```python
# Configuration
JWT_ALGORITHM = "HS256"  # Hardcoded to prevent algorithm confusion
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

@dataclass
class TokenPayload:
    sub: str                    # User ID
    exp: datetime               # Expiration
    jti: str                    # JWT ID for revocation
    scopes: list[str]           # Permissions
    trust_level: int            # User's trust score

def create_access_token(user: User) -> str:
    payload = TokenPayload(
        sub=user.id,
        exp=datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        jti=str(uuid4()),
        scopes=user.capabilities,
        trust_level=user.trust_score
    )
    return jwt.encode(payload.dict(), JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
```

**Token Blacklist:**

```python
class TokenBlacklist:
    """Redis-backed token blacklist with in-memory fallback."""

    MAX_SIZE = 100_000  # Memory limit

    async def revoke(self, jti: str, exp: datetime) -> None:
        """Add token to blacklist."""
        ttl = (exp - datetime.utcnow()).total_seconds()
        if self.redis:
            await self.redis.setex(f"blacklist:{jti}", int(ttl), "1")
        else:
            self._memory_store[jti] = exp
            self._enforce_size_limit()

    async def is_revoked(self, jti: str) -> bool:
        """Check if token is revoked."""
        if self.redis:
            return await self.redis.exists(f"blacklist:{jti}")
        return jti in self._memory_store
```

**Password Security:**

```python
# Bcrypt configuration
BCRYPT_ROUNDS = 12  # 4-31, higher = slower but more secure

def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    # Bcrypt truncates at 72 bytes
    if len(password.encode()) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS))

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())

def validate_password_strength(password: str) -> bool:
    """Ensure password meets complexity requirements."""
    return (
        len(password) >= 8 and
        any(c.isupper() for c in password) and
        any(c.islower() for c in password) and
        any(c.isdigit() for c in password)
    )
```

**Multi-Factor Authentication:**

```python
class MFAService:
    """TOTP-based MFA with backup codes."""

    def setup_totp(self, user: User) -> MFASetup:
        """Generate TOTP secret and backup codes."""
        secret = pyotp.random_base32()
        backup_codes = [secrets.token_hex(4) for _ in range(10)]

        return MFASetup(
            secret=secret,
            provisioning_uri=pyotp.TOTP(secret).provisioning_uri(
                user.email,
                issuer_name="Forge"
            ),
            backup_codes=backup_codes
        )

    def verify_totp(self, user: User, code: str) -> bool:
        """Verify TOTP code."""
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(code, valid_window=1)  # 30-second window
```

### 9.2 Authorization

**Role-Based Access Control:**

```python
class UserRole(Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SYSTEM = "system"

ROLE_CAPABILITIES = {
    UserRole.USER: {
        Capability.READ_CAPSULES,
        Capability.CREATE_CAPSULES,
        Capability.VOTE,
    },
    UserRole.MODERATOR: {
        # All user capabilities plus:
        Capability.MODERATE_CONTENT,
        Capability.VIEW_REPORTS,
    },
    UserRole.ADMIN: {
        # All moderator capabilities plus:
        Capability.MANAGE_USERS,
        Capability.VIEW_AUDIT_LOGS,
        Capability.CONFIGURE_OVERLAYS,
    },
    UserRole.SYSTEM: {
        # All capabilities
        *Capability,
    },
}
```

**Capability-Based Fine-Grained Access:**

```python
class Capability(Enum):
    # Capsule operations
    READ_CAPSULES = "capsules:read"
    CREATE_CAPSULES = "capsules:create"
    UPDATE_CAPSULES = "capsules:update"
    DELETE_CAPSULES = "capsules:delete"

    # Governance
    VOTE = "governance:vote"
    CREATE_PROPOSALS = "governance:create_proposals"
    FINALIZE_PROPOSALS = "governance:finalize"

    # Moderation
    MODERATE_CONTENT = "moderation:content"
    VIEW_REPORTS = "moderation:reports"

    # Administration
    MANAGE_USERS = "admin:users"
    CONFIGURE_OVERLAYS = "admin:overlays"
    VIEW_AUDIT_LOGS = "admin:audit"
    MANAGE_FEDERATION = "admin:federation"
```

### 9.3 Middleware Stack

**12-Layer Security Middleware:**

```python
# Order matters - executed top to bottom on request, bottom to top on response

MIDDLEWARE_STACK = [
    # 1. Security Headers (HSTS, CSP, X-Frame-Options)
    SecurityHeadersMiddleware(
        hsts_max_age=31536000,  # 1 year in production
        content_security_policy="default-src 'self'",
    ),

    # 2. Request Timeout
    RequestTimeoutMiddleware(
        default_timeout=30,
        extended_timeout=120,  # For long operations
    ),

    # 3. Correlation ID (request tracing)
    CorrelationIdMiddleware(),

    # 4. Request Logging
    RequestLoggingMiddleware(
        sanitize_headers=["authorization", "cookie"],
    ),

    # 5. Observability (metrics, tracing)
    ObservabilityMiddleware(),

    # 6. Prometheus Metrics
    PrometheusMiddleware(),

    # 7. Request Size Limit
    RequestSizeLimitMiddleware(max_size=10 * 1024 * 1024),  # 10 MB

    # 8. API Limits
    APILimitsMiddleware(
        max_json_depth=20,
        max_query_params=50,
        max_array_length=1000,
    ),

    # 9. CSRF Protection (production only)
    CSRFProtectionMiddleware(
        exempt_paths=["/api/v1/auth/login"],
    ),

    # 10. Idempotency
    IdempotencyMiddleware(
        cache_ttl=86400,  # 24 hours
        max_entries=10000,
    ),

    # 11. Authentication
    AuthenticationMiddleware(
        exclude_paths=["/health", "/ready", "/api/v1/auth/login"],
    ),

    # 12. Rate Limiting
    RateLimitMiddleware(
        auth_limit="10/minute",
        general_limit="100/minute",
    ),
]
```

### 9.4 Audit Fixes Implemented

**4 Security Audit Cycles:**

| Audit | Focus | Key Fixes |
|-------|-------|-----------|
| **Audit 1** | Core Architecture | Async-first design, proper error handling |
| **Audit 2** | Input & Protocol | Request size limits, validation sanitization, SSRF protection |
| **Audit 3** | Session & Token | Bounded blacklist, TTL enforcement, session limits |
| **Audit 4** | Advanced Protection | DNS pinning, cert pinning, nonce replay prevention |

**Notable Security Features:**

- **IP-based Rate Limiting**: 20 failed attempts per 5 min → 15 min lockout
- **Account Lockout**: 3 failures → account lockout
- **Prompt Sanitization**: Prevents LLM prompt injection
- **Safe Regex**: 500ms timeout for ReDoS prevention
- **Avatar URL Validation**: Blocks javascript: and data: URIs
- **Bcrypt Truncation Warning**: Errors on passwords > 72 bytes

---

## 10. API Reference

### 10.1 Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create new account |
| POST | `/api/v1/auth/login` | Authenticate user |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| POST | `/api/v1/auth/logout` | Revoke tokens |
| POST | `/api/v1/auth/mfa/setup` | Enable 2FA |
| POST | `/api/v1/auth/mfa/verify` | Verify 2FA code |

**Example: Login**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "usr_abc123",
    "email": "user@example.com",
    "trust_score": 65,
    "trust_level": "STANDARD"
  }
}
```

### 10.2 Capsule Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/capsules` | List capsules |
| POST | `/api/v1/capsules` | Create capsule |
| GET | `/api/v1/capsules/{id}` | Get capsule |
| PUT | `/api/v1/capsules/{id}` | Update capsule |
| DELETE | `/api/v1/capsules/{id}` | Delete capsule |
| GET | `/api/v1/capsules/{id}/lineage` | Get lineage tree |
| GET | `/api/v1/capsules/{id}/versions` | Get version history |
| POST | `/api/v1/capsules/search` | Semantic search |

**Example: Create Capsule**
```http
POST /api/v1/capsules
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "API Rate Limiting Best Practices",
  "content": "Rate limiting is essential for...",
  "type": "KNOWLEDGE",
  "tags": ["api", "security", "performance"],
  "parent_ids": ["cap_xyz789"]
}
```

### 10.3 Governance Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/governance/proposals` | List proposals |
| POST | `/api/v1/governance/proposals` | Create proposal |
| GET | `/api/v1/governance/proposals/{id}` | Get proposal |
| POST | `/api/v1/governance/proposals/{id}/vote` | Cast vote |
| GET | `/api/v1/governance/proposals/{id}/ghost-council` | Get AI analysis |

**Example: Cast Vote**
```http
POST /api/v1/governance/proposals/prop_123/vote
Authorization: Bearer {token}
Content-Type: application/json

{
  "choice": "FOR",
  "reasoning": "This proposal improves system security."
}
```

### 10.4 Federation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/federation/peers` | List peers |
| POST | `/api/v1/federation/peers` | Register peer |
| GET | `/api/v1/federation/peers/{id}` | Get peer details |
| POST | `/api/v1/federation/peers/{id}/sync` | Trigger sync |
| PUT | `/api/v1/federation/peers/{id}/trust` | Update trust |

### 10.5 System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/ready` | Readiness probe |
| GET | `/metrics` | Prometheus metrics |
| GET | `/api/v1/system/status` | Component status |
| GET | `/api/v1/system/overlays` | Overlay status |

### 10.6 WebSocket Events

**Connection:**
```javascript
const ws = new WebSocket('wss://forge.example.com/ws/events');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['capsules', 'proposals', 'system']
  }));
};
```

**Event Types:**

| Event | Description |
|-------|-------------|
| `capsule.created` | New capsule created |
| `capsule.updated` | Capsule modified |
| `proposal.created` | New proposal |
| `proposal.voted` | Vote cast |
| `proposal.finalized` | Proposal concluded |
| `system.health` | Health status change |
| `overlay.status` | Overlay status change |

---

## 11. Blockchain Integration

### 11.1 Virtuals Protocol Overview

Forge integrates with Virtuals Protocol for blockchain capabilities:

```
┌─────────────────────────────────────────────────────────────────┐
│                   VIRTUALS PROTOCOL INTEGRATION                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │    Agent     │    │ Tokenization │    │     ACP      │      │
│  │  Management  │    │   Service    │    │  Protocol    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                    ┌────────▼────────┐                          │
│                    │   Forge Core    │                          │
│                    │   Integration   │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│              ┌──────────────┼──────────────┐                    │
│              │              │              │                    │
│              ▼              ▼              ▼                    │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│        │  Solana  │   │   EVM    │   │  Revenue │              │
│        │  Chain   │   │  Chains  │   │ Tracking │              │
│        └──────────┘   └──────────┘   └──────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Agent Management

```python
@dataclass
class AgentSession:
    """AI agent session for knowledge graph access."""
    id: str
    agent_id: str
    api_key: str
    trust_level: AgentTrustLevel
    capabilities: set[AgentCapability]
    rate_limits: RateLimits
    created_at: datetime
    expires_at: datetime

class AgentTrustLevel(Enum):
    BASIC = "basic"          # Read-only access
    STANDARD = "standard"    # Read + limited write
    ADVANCED = "advanced"    # Full access, governance participation
    CORE = "core"            # System-level access
```

### 11.3 Tokenization

**Token Types:**
- **ERC-20 Governance Tokens**: Voting rights in Forge governance
- **Capsule NFTs**: Unique tokens representing capsule ownership
- **Agent Service Tokens**: Payment for AI agent services

**Bonding Curve Pricing:**
```python
def calculate_token_price(supply: int, amount: int) -> float:
    """Calculate price using bonding curve."""
    INITIAL_PRICE = 0.001  # Starting price
    CURVE_FACTOR = 0.0001  # Price increase per token

    # Integral of linear curve
    start_price = INITIAL_PRICE + CURVE_FACTOR * supply
    end_price = INITIAL_PRICE + CURVE_FACTOR * (supply + amount)

    return (start_price + end_price) * amount / 2
```

### 11.4 Multi-Chain Support

**Supported Chains:**
- **Solana**: Native SPL tokens, fast transactions
- **Ethereum**: ERC-20, ERC-721, smart contracts
- **Base**: Low-cost EVM transactions
- **Arbitrum**: L2 scaling

**Transaction Model:**
```python
@dataclass
class BlockchainTransaction:
    id: str
    chain: str                  # solana, ethereum, base, arbitrum
    type: TransactionType       # MINT, TRANSFER, BURN, CONTRACT_CALL
    from_address: str
    to_address: str
    amount: Decimal
    token_address: str | None
    signature: str
    status: TransactionStatus
    block_number: int | None
    timestamp: datetime
```

---

## 12. Deployment

### 12.1 Docker Compose Configurations

**Development (docker-compose.yml):**
```yaml
services:
  cascade-api:
    build: ./forge-cascade-v2
    ports:
      - "8001:8001"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - LLM_PROVIDER=mock
    depends_on:
      - neo4j
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  compliance-api:
    build: ./forge-compliance
    ports:
      - "8002:8002"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
    depends_on:
      - neo4j

  virtuals-api:
    build: ./forge-virtuals
    ports:
      - "8003:8003"
    environment:
      - SOLANA_RPC_URL=${SOLANA_RPC_URL}
      - ETH_RPC_URL=${ETH_RPC_URL}

  frontend:
    build: ./marketplace
    ports:
      - "80:80"
    depends_on:
      - cascade-api

  neo4j:
    image: neo4j:5.15.0
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    # No external port - internal only

  jaeger:
    image: jaegertracing/all-in-one:1.53
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP

volumes:
  neo4j_data:
```

**Production with Cloudflare (docker-compose.cloudflare.yml):**
```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:2024.12.2
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - cascade-api
      - frontend

  cascade-api:
    # No external ports - accessed via tunnel
    environment:
      - APP_ENV=production
      - LLM_PROVIDER=anthropic
      - LLM_MODEL=claude-sonnet-4-20250514
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

  jaeger:
    ports:
      - "127.0.0.1:16686:16686"  # Localhost only
```

### 12.2 Environment Variables

**Required:**
```bash
# Security (REQUIRED)
JWT_SECRET_KEY=          # Min 32 chars, high entropy
REDIS_PASSWORD=          # No default for security
NEO4J_PASSWORD=          # Database password

# Database
NEO4J_URI=bolt://neo4j:7687
REDIS_URL=redis://:password@redis:6379

# Application
APP_ENV=production       # development, staging, production
```

**Optional:**
```bash
# LLM Configuration
LLM_PROVIDER=anthropic   # mock, anthropic, openai
LLM_MODEL=claude-sonnet-4-20250514
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.4

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Security Tuning
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_BCRYPT_ROUNDS=12
MAX_CONCURRENT_SESSIONS_PER_USER=5

# Resilience
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
QUERY_CACHE_TTL_SECONDS=3600
QUERY_CACHE_MAX_SIZE=10000

# Observability
PROMETHEUS_ENABLED=true
OTLP_ENDPOINT=http://jaeger:4317
SENTRY_DSN=               # Optional error tracking
```

### 12.3 Health Checks

**Endpoints:**
- `/health` - Lightweight readiness (immediate response)
- `/ready` - Full component verification
- `/metrics` - Prometheus metrics

**Kubernetes Probes:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8001
  initialDelaySeconds: 5
  periodSeconds: 5
```

### 12.4 Graceful Shutdown

**Shutdown Sequence:**
1. Stop accepting new requests
2. Drain active requests (30s timeout)
3. Shutdown scheduler (stop background tasks)
4. Flush query cache
5. Cleanup overlays
6. Drain event system
7. Close database connections

```python
async def shutdown():
    """Graceful shutdown sequence."""
    logger.info("Initiating graceful shutdown...")

    # 1. Scheduler
    if app.scheduler:
        app.scheduler.shutdown(wait=True)

    # 2. Query cache
    if app.query_cache:
        await app.query_cache.flush()

    # 3. Overlays
    if app.overlay_manager:
        await app.overlay_manager.cleanup_all()

    # 4. Event system
    if app.event_system:
        await app.event_system.drain(timeout=30)

    # 5. Database
    if app.db_client:
        await app.db_client.close()

    logger.info("Shutdown complete")
```

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Capsule** | Atomic unit of knowledge in Forge |
| **Cascade** | Event-driven propagation of changes through the graph |
| **Ghost Council** | AI advisory board for governance decisions |
| **Isnad** | Chain of knowledge transmission (from Islamic scholarship) |
| **Overlay** | Modular processing unit in the pipeline |
| **Trust Flame** | Dynamic reputation score (0-100) |
| **Federation** | P2P connection between Forge instances |
| **Fuel Budget** | Resource constraints for overlay execution |

---

## Appendix B: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | January 2025 | Initial technical whitepaper |

---

*This document is maintained by the Forge development team. For the latest version, visit the official documentation.*
