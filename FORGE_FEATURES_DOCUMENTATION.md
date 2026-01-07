# Forge V3: Complete Feature Documentation

## Institutional Memory Engine - Comprehensive Technical Reference

---

# Table of Contents

## Part I: Project Overview
1. [System Overview](#1-system-overview)
2. [Project Structure](#2-project-structure)
3. [Technology Stack](#3-technology-stack)

## Part II: Core Engine (forge-cascade-v2)
4. [The Seven-Phase Pipeline](#4-the-seven-phase-pipeline)
5. [Capsule System: Knowledge Management](#5-capsule-system-knowledge-management)
6. [Event System: The Cascade Effect](#6-event-system-the-cascade-effect)
7. [Overlay System: Modular Processing](#7-overlay-system-modular-processing)
8. [Governance: Ghost Council & Democratic Voting](#8-governance-ghost-council--democratic-voting)
9. [Security: Authentication & Authorization](#9-security-authentication--authorization)
10. [Immune System: Self-Healing & Resilience](#10-immune-system-self-healing--resilience)
11. [Trust Hierarchy](#11-trust-hierarchy)

## Part III: Compliance Framework (forge/compliance)
12. [Compliance Framework Overview](#12-compliance-framework-overview)
13. [Privacy Regulations & DSAR Processing](#13-privacy-regulations--dsar-processing)
14. [Security Frameworks](#14-security-frameworks)
15. [AI Governance & EU AI Act](#15-ai-governance--eu-ai-act)
16. [Industry-Specific Compliance](#16-industry-specific-compliance)
17. [Accessibility Standards](#17-accessibility-standards)
18. [Data Residency & Cross-Border Transfers](#18-data-residency--cross-border-transfers)

## Part IV: Virtuals Protocol Integration (forge_virtuals_integration)
19. [Virtuals Integration Overview](#19-virtuals-integration-overview)
20. [Virtual Agents & GAME Framework](#20-virtual-agents--game-framework)
21. [Agent Commerce Protocol (ACP)](#21-agent-commerce-protocol-acp)
22. [Tokenization & Bonding Curves](#22-tokenization--bonding-curves)
23. [Multi-Chain Blockchain Support](#23-multi-chain-blockchain-support)
24. [Revenue Distribution System](#24-revenue-distribution-system)

## Part V: Specifications & Architecture
25. [Specification Documents](#25-specification-documents)
26. [Architecture Diagrams](#26-architecture-diagrams)
27. [Data Flow: End-to-End Processing](#27-data-flow-end-to-end-processing)

---

# Part I: Project Overview

---

# 1. System Overview

Forge V3 is an **Institutional Memory Engine** designed to capture, evolve, and govern organizational knowledge through a sophisticated system of interconnected components. At its core, Forge treats knowledge as living entities called **Capsules** that flow through a **Seven-Phase Pipeline**, are processed by specialized **Overlays**, and are governed democratically through the **Ghost Council**.

## The Core Problem: Ephemeral Wisdom

Traditional AI systems suffer from **knowledge amnesia** - accumulated learning is lost during upgrades or retraining. Forge solves this through:

- **Persistent Memory Layer**: Capsules that survive across system generations
- **Cultural Learning Model**: AI systems learn like cultures, not individuals
- **Generational Knowledge Propagation**: Through "Cascades" that spread insights
- **Isnad Lineage Tracking**: Scholarly chain of transmission for knowledge provenance

## Core Design Principles

- **Knowledge as First-Class Citizens**: Every piece of information is a versioned, traceable Capsule with lineage
- **Cascade Effect**: Insights propagate through the system, triggering related processing automatically
- **Democratic Governance**: AI-assisted decision-making with human oversight via the Ghost Council
- **Self-Healing**: The Immune System automatically detects and recovers from failures
- **Compliance by Design**: Regulatory requirements enforced through configuration, not code changes
- **Trust-Based Access**: A graduated trust hierarchy controls what users and overlays can do
- **True Isolation**: WebAssembly for overlay execution (not Python sandboxing)

## Enterprise Positioning

Forge is **NOT** a consumer chatbot competitor. It is positioned as an:
- **Institutional Memory Engine** for enterprise knowledge management
- **Target markets**: Regulated sectors (legal, biotech, finance) where lineage and governance matter most
- **Differentiator**: Complete audit trails, democratic governance, and compliance-first architecture

---

# 2. Project Structure

Forge V3 consists of four major modules:

```
C:\Users\idean\Downloads\Forge V3\
├── forge-cascade-v2/              # Core Implementation (Production Ready)
│   ├── forge/                     # Backend Python package (FastAPI)
│   │   ├── api/                   # REST API + WebSocket endpoints
│   │   ├── database/              # Neo4j integration, schema management
│   │   ├── immune/                # Self-healing system
│   │   ├── kernel/                # Event system, overlay manager, pipeline
│   │   ├── models/                # Pydantic data models
│   │   ├── overlays/              # ML, security, governance overlays
│   │   ├── repositories/          # Data access layer
│   │   ├── security/              # Auth, JWT, trust hierarchy
│   │   ├── services/              # LLM, search, embedding services
│   │   └── monitoring/            # Metrics, logging
│   ├── frontend/                  # React 19 + TypeScript dashboard
│   ├── docker/                    # Container orchestration
│   └── tests/                     # Comprehensive test suite
│
├── forge/compliance/              # Compliance Framework (400+ Controls)
│   ├── core/                      # Engine, registry, config, models
│   ├── privacy/                   # GDPR, CCPA, consent, DSAR
│   ├── security/                  # Access control, breach notification
│   ├── encryption/                # AES-256-GCM, key management
│   ├── residency/                 # Data residency controls
│   ├── ai_governance/             # EU AI Act, bias detection
│   ├── industry/                  # HIPAA, PCI-DSS, COPPA
│   ├── accessibility/             # WCAG 2.2, EAA
│   ├── reporting/                 # Compliance reports
│   └── api/                       # REST endpoints
│
├── forge_virtuals_integration/    # Blockchain AI Agent Integration
│   ├── forge/virtuals/
│   │   ├── models/                # Agent, ACP, tokenization models
│   │   ├── chains/                # EVM, Solana blockchain clients
│   │   ├── game/                  # GAME SDK integration
│   │   ├── acp/                   # Agent Commerce Protocol
│   │   ├── tokenization/          # Token creation, bonding curves
│   │   ├── revenue/               # Revenue distribution
│   │   └── api/                   # REST endpoints
│   └── examples/                  # Integration examples
│
├── Forge Specification Files/     # 19 Specification Documents
│   ├── FORGE_SPECIFICATION*.md    # Core specifications
│   ├── PHASE_0-8_*.md             # Phase-by-phase implementation
│   └── SUPPLEMENT_A-F_*.md        # Implementation supplements
│
├── Diagrams/                      # 10 Mermaid Architecture Diagrams
│   └── *.mermaid                  # Visual architecture documentation
│
└── Documentation Files
    ├── FORGE_FEATURES_DOCUMENTATION.md
    ├── FORGE_COMPLIANCE_FRAMEWORK_DOCUMENTATION.md
    └── Various reports and checklists
```

---

# 3. Technology Stack

## Core Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | Python 3.12, FastAPI, async/await | Async REST API with Pydantic v2 |
| **Database** | Neo4j 5.x | Graph + Vector + Properties (unified ACID store) |
| **Cache** | Redis 7.x | Sessions, rate limiting, caching |
| **Events** | Kafka / KurrentDB | Event sourcing, audit trails |
| **Overlays** | Wasmtime | WebAssembly execution runtime |
| **Embeddings** | Sentence-Transformers | 1536-dimensional semantic vectors |
| **ML** | scikit-learn | Anomaly detection, classification |
| **Frontend** | React 19, TypeScript, Tailwind CSS v4 | Dashboard SPA |
| **CLI** | Typer + Rich | Command-line interface |

## Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Containers** | Docker, Docker Compose | Container orchestration |
| **Orchestration** | Kubernetes, ArgoCD | Production deployment |
| **CI/CD** | GitHub Actions | Automated testing and deployment |
| **Monitoring** | Prometheus, Grafana | Metrics collection and visualization |
| **Tracing** | Jaeger | Distributed tracing |
| **Errors** | Sentry | Error tracking |

## Blockchain (Virtuals Integration)

| Chain | Technology | Purpose |
|-------|-----------|---------|
| **Base** | EVM (web3.py) | Primary chain (Ethereum L2) |
| **Ethereum** | EVM (web3.py) | Bridge and cross-chain |
| **Solana** | solana-py, solders | Alternative chain support |

---

# Part II: Core Engine (forge-cascade-v2)

---

# 4. The Seven-Phase Pipeline

Every operation in Forge flows through a structured seven-phase pipeline. This ensures consistent processing, security validation, governance approval, and proper audit trails.

## Pipeline Architecture

```
PARALLEL (Phases 1-3, ~300ms):
├── Phase 1: INGESTION (Context Creation)
├── Phase 2: ANALYSIS (ML Processing)
└── Phase 3: VALIDATION (Security Assessment)
          ↓
SEQUENTIAL (Phases 4-5):
├── Phase 4: CONSENSUS (Optimization, ~20ms)
└── Phase 5: EXECUTION (Intelligence, ~1000ms - LLM bottleneck)
          ↓
FIRE-AND-FORGET (Phases 6-7):
├── Phase 6: PROPAGATION (Metrics)
└── Phase 7: SETTLEMENT (Storage)
```

**Performance**: Optimized from 3.5s → 1.2s through parallelization.

## Phase Details

### Phase 1: INGESTION
**Purpose**: Receive and normalize incoming data

- Validates request format and required fields
- Normalizes data structures (tags lowercased, whitespace trimmed)
- Assigns correlation IDs for request tracking
- Applies input size limits (max 1MB content)
- Creates context with embeddings and user profile

**Timeout**: 3 seconds | **Required**: Yes | **Parallel**: Yes

### Phase 2: ANALYSIS
**Purpose**: Extract meaning through ML processing

Five parallel ML functions:
1. **Anomaly Detection**: IsolationForest model (contamination: 0.01)
2. **Intent Classification**: information_retrieval, knowledge_creation, governance_action
3. **Content Categorization**: Named Entity Recognition, taxonomy mapping
4. **Sentiment Analysis**: Tone detection, frustration/urgency markers
5. **Complexity Scoring**: Query structure analysis, domain depth

**Overlays**: MLIntelligenceOverlay, CapsuleAnalyzerOverlay
**Timeout**: 10 seconds | **Required**: Yes | **Parallel**: Yes

### Phase 3: VALIDATION
**Purpose**: Security checks and trust verification

- **Content Policy**: Blocks secrets, credentials, prohibited patterns
- **Trust Verification**: Confirms user has sufficient trust level
- **Rate Limiting**: Enforces per-user request limits
- **Input Sanitization**: Detects SQL injection, XSS, malicious payloads
- **Threat Tracking**: Blocks users after 10+ threats within one hour

**Overlays**: SecurityValidatorOverlay
**Timeout**: 5 seconds | **Required**: Yes

### Phase 4: CONSENSUS
**Purpose**: Governance approval for significant changes

- Evaluates proposals against governance policies
- Collects trust-weighted votes (APPROVE, REJECT, ABSTAIN)
- Calculates consensus with configurable thresholds
- Supports early consensus via supermajority (80%+)
- Performance optimization and cache checking

**Overlays**: GovernanceOverlay, PerformanceOptimizerOverlay
**Timeout**: 5 seconds | **Required**: No (skippable for routine operations)

### Phase 5: EXECUTION
**Purpose**: Core processing and state changes (LLM bottleneck)

- Performs the actual requested operation (create, update, delete)
- LLM call for intelligence generation (~1000ms)
- Writes to Neo4j database
- Updates relationships and indices
- Manages transactions with rollback on failure

**Timeout**: 10 seconds | **Required**: Yes | **Max Retries**: 1

### Phase 6: PROPAGATION
**Purpose**: Cascade effect and event emission (fire-and-forget)

- Emits events to notify other system components
- Triggers cascade chains for insight propagation
- Routes events to subscribed overlays
- Manages hop limits to prevent infinite loops (max 5 hops)
- Collects metrics

**Timeout**: 5 seconds | **Required**: Yes | **Parallel**: Yes

### Phase 7: SETTLEMENT
**Purpose**: Finalization and audit logging (fire-and-forget)

- Records immutable audit entries with cryptographic hashing
- Tracks lineage relationships (Isnad chains)
- Updates metrics and statistics
- Closes the pipeline execution record
- Persists to storage

**Overlays**: LineageTrackerOverlay
**Timeout**: 3 seconds | **Required**: Yes

## Pipeline Context

Every pipeline execution carries a `PipelineContext`:

```python
PipelineContext:
  - pipeline_id: UUID (unique execution identifier)
  - correlation_id: UUID (links related operations)
  - triggered_by: str (event_id, "manual", or capsule_id)
  - user_id: str (authenticated user)
  - trust_flame: int (0-100 trust score)
  - capabilities: Set[Capability] (allowed operations)
  - fuel_budget: FuelBudget (resource limits)
  - data: dict (accumulated processing results)
  - phase_results: dict (results per phase)
```

---

# 5. Capsule System: Knowledge Management

Capsules are the atomic units of knowledge in Forge. Every piece of information—insights, decisions, lessons, code, configurations—is stored as a Capsule with full version history and lineage tracking.

## Capsule Types

| Type | Purpose | Example |
|------|---------|---------|
| INSIGHT | AI-generated discoveries | "Users prefer dark mode 3:1" |
| DECISION | Recorded choices with rationale | "Chose PostgreSQL for ACID compliance" |
| LESSON | Learned experiences | "Always test migrations locally first" |
| WARNING | Cautions and alerts | "API rate limits reset at midnight UTC" |
| PRINCIPLE | Guiding rules | "Prefer composition over inheritance" |
| MEMORY | Institutional context | "Q4 2024 all-hands summary" |
| KNOWLEDGE | General information | "OAuth 2.0 implementation guide" |
| CODE | Snippets and functions | "Retry decorator with exponential backoff" |
| CONFIG | Configuration data | "Production environment variables" |
| TEMPLATE | Reusable patterns | "PR description template" |
| DOCUMENT | Full documents | "Architecture decision record #42" |

## Capsule Structure

```python
Capsule:
  # Identity
  - id: str (format: "cap_xxxxxxxxxxxx")
  - version: str (semantic: "1.0.0")
  - owner_id: str (creator's user ID)

  # Content
  - content: str (1B - 1MB)
  - title: str (optional, max 500 chars)
  - summary: str (optional, max 2000 chars)
  - type: CapsuleType
  - tags: list[str] (max 20, normalized)
  - metadata: dict (extensible, max 64KB)

  # Trust & State
  - trust_level: TrustLevel (QUARANTINE → CORE)
  - is_archived: bool (soft delete)

  # Lineage (Isnad)
  - parent_id: str (symbolic inheritance link)

  # Metrics
  - view_count: int
  - fork_count: int

  # Timestamps
  - created_at: datetime
  - updated_at: datetime

  # Search
  - embedding: list[float] (1536-dimensional vector)
```

## The Isnad System: Knowledge Lineage

**Isnad** (Arabic: إسناد, "chain of transmission") tracks how knowledge evolves through derivation, borrowed from Islamic scholarly tradition for tracking hadith authenticity.

### Symbolic Inheritance
When a Capsule is created from another (forked), it maintains a `parent_id` link forming a **DERIVED_FROM** relationship. This creates acyclic directed graphs representing knowledge evolution.

### Lineage Example
```
Original Insight (trust: 100)
    └── Fork: Applied to Project A (trust: 95)
        └── Fork: Adapted for Mobile (trust: 90)
            └── Fork: iOS-specific version (trust: 85)
```

### Lineage Features
- **Ancestor Retrieval**: Get all capsules in the derivation chain (max depth: 10)
- **Descendant Discovery**: Find all capsules derived from a given capsule
- **Trust Gradient**: Track how trust levels evolve through the chain
- **Cycle Prevention**: System validates no circular references exist
- **Influence Scoring**: Measures impact based on descendants and trust weighting
- **Quarantine Detection**: Vulnerable code paths can be quarantined (trust: 0)

### Fork Operation
```python
POST /capsules/{capsule_id}/fork
{
  "title": "Optional new title",
  "content": "Optional modified content",
  "evolution_reason": "Why this fork was created"  # Required
}
```

## Semantic Search

Capsules are searchable through vector similarity:

1. **Query Embedding**: User's search query is embedded into a 1536-dimensional vector
2. **Neo4j Vector Index**: Query `capsule_embeddings` index for similar vectors (cosine similarity)
3. **Trust Filtering**: Results filtered by minimum trust level
4. **Score Ranking**: Results ordered by similarity score (0.0-1.0)

```python
POST /capsules/search
{
  "query": "How do we handle authentication?",
  "limit": 10,
  "filters": {"type": "KNOWLEDGE", "owner_id": "user_123"}
}
```

## Capsule Lifecycle

```
CREATE → ACTIVE → VERSION (creates child) → ARCHIVE → MIGRATE
```

---

# 6. Event System: The Cascade Effect

The Event System is the communication backbone of Forge, enabling asynchronous, decoupled interactions between components through a pub/sub architecture.

## Event Types (40+ Types)

### Capsule Events
- `CAPSULE_CREATED`: New capsule stored
- `CAPSULE_UPDATED`: Capsule content modified
- `CAPSULE_ACCESSED`: Capsule retrieved
- `CAPSULE_DELETED`: Capsule removed
- `CAPSULE_LINKED`: Parent-child relationship created

### Governance Events
- `PROPOSAL_CREATED`: New governance proposal
- `VOTE_CAST`: Vote recorded on proposal
- `GOVERNANCE_ACTION`: Governance decision executed

### Security Events
- `SECURITY_ALERT`: Threat detected
- `TRUST_UPDATED`: User trust level changed

### Cascade Events
- `CASCADE_INITIATED`: New cascade chain started
- `CASCADE_PROPAGATED`: Insight propagated to next overlay
- `CASCADE_COMPLETE`: Cascade chain finished

## Event Structure

```python
Event:
  - id: UUID
  - type: EventType
  - priority: EventPriority (LOW, NORMAL, HIGH, CRITICAL)
  - payload: dict[str, Any]
  - source: str (e.g., "overlay:ml_intelligence", "api:capsules")
  - correlation_id: UUID (links related events)
  - causation_id: UUID (what caused this event)
  - target_overlays: Optional[list[str]] (broadcast vs. targeted)
  - metadata: dict[str, Any]
  - timestamp: datetime
```

## The Cascade Effect

The Cascade Effect is Forge's mechanism for propagating insights across overlays automatically, enabling the system to "learn like a culture, not an individual."

### How Cascades Work

1. **Initiation**: An overlay discovers an insight and publishes `CASCADE_INITIATED`
2. **Chain Creation**: System creates a `CascadeChain` with unique `cascade_id`
3. **First Hop**: Event routed to subscribed overlays (hop_count = 0)
4. **Processing**: Receiving overlay processes and may emit new insights
5. **Propagation**: New insights continue the chain (hop_count increments)
6. **Cycle Prevention**: Visited overlays tracked; cannot receive same cascade twice
7. **Hop Limiting**: Maximum 5 hops prevents infinite loops
8. **Completion**: Chain completes when no more propagation possible

### Seven Stages of Cascade

1. **Pattern Discovery**: ML intelligence finds recurring behavior
2. **Insight Crystallization**: Pattern becomes persistent Capsule
3. **Cascade Initiation**: Insight published to event system
4. **Parallel Propagation**: 5+ overlays integrate independently
5. **Graph Relationships**: TRIGGERED edges created for lineage
6. **Immediate Benefit**: Original query enhanced
7. **Lasting Intelligence**: Permanent ecosystem improvements

### Example Cascade: Security Threat Detection

```
1. security_validator detects SQL injection (confidence: 0.98)
2. Graph Update: ThreatRecord created with relationship
3. Cascade Initiation: Event published to event_system
4. Parallel Delivery to 4 overlays:
   - ml_intelligence: Updates anomaly detection model
   - immune_system: Evaluates severity, increases monitoring
   - symbolic_governance: Checks auto-proposal thresholds
   - audit_logger: Creates immutable audit record
5. Secondary Cascade: ML triggers Performance Optimizer
   - Allocates 20% more CPU to security validation
```

## Event Delivery

### Delivery Guarantees
- **Concurrent Delivery**: All matching handlers run in parallel
- **Retry Logic**: 3 attempts with exponential backoff (1s base delay)
- **Dead Letter Queue**: Failed events preserved for investigation
- **Timeout**: 30 seconds per handler
- **Immutable Audit**: Every event logged for reconstruction

---

# 7. Overlay System: Modular Processing

Overlays are self-contained processing modules that extend Forge's capabilities without modifying the core kernel. They are executed in WebAssembly for true memory-safe isolation.

## Overlay Architecture

### Base Overlay Contract

```python
class BaseOverlay:
    NAME: str                    # Unique identifier
    VERSION: str                 # Semantic version
    DESCRIPTION: str             # Human-readable purpose

    SUBSCRIBED_EVENTS: Set[EventType]      # Events to react to
    REQUIRED_CAPABILITIES: Set[Capability]  # Permissions needed
    MIN_TRUST_LEVEL: TrustLevel            # User trust required

    async def initialize(self) -> bool      # Setup resources
    async def execute(self, context, event, input_data) -> OverlayResult
    async def cleanup(self) -> None         # Release resources
    async def health_check(self) -> OverlayHealthCheck
```

### WebAssembly Runtime (Wasmtime)

Overlays are compiled to WebAssembly for true isolation:
- **Compilation**: Python → Nuitka/Pyodide → WebAssembly
- **Execution**: Wasmtime with fuel metering (CPU limits)
- **Memory Limits**: Configurable (default 64MB)
- **Host Functions**: db_read, db_write, event_publish, event_subscribe, log
- **Capability Gating**: Explicit permissions before function access

### Resource Constraints (Fuel Budget)

```python
FuelBudget:
  - total_fuel: 1,000,000 (computational units)
  - max_memory_bytes: 10 MB
  - timeout_ms: 5000 (5 seconds)
```

## The Six Core Overlays

### 1. Security Validator Overlay
**Phase**: VALIDATION | **Trust**: 90

- Content policy validation (blocks secrets, credentials)
- Trust level verification
- Rate limiting enforcement
- Input sanitization (SQL injection, XSS detection)
- Threat tracking and auto-blocking

### 2. ML Intelligence Overlay
**Phase**: ANALYSIS | **Trust**: 85

- Embedding generation (384-1536 dimensions)
- Content classification (technical, business, personal, etc.)
- Entity extraction (emails, URLs, dates, money)
- Pattern detection (questions, lists, code blocks)
- Sentiment analysis (-1.0 to +1.0)
- Anomaly scoring

### 3. Governance Overlay
**Phase**: CONSENSUS | **Trust**: 85

- Proposal evaluation against policies
- Vote collection (trust-weighted)
- Consensus calculation (configurable thresholds)
- Early consensus via supermajority (80%+)
- Ghost Council integration

### 4. Lineage Tracker Overlay
**Phase**: SETTLEMENT | **Trust**: 85

- Ancestor/descendant tracking
- Isnad chain computation
- Circular reference detection
- Influence scoring (trust-weighted, decay-based)
- Anomaly detection (excessive depth, rapid derivations)

### 5. Capsule Analyzer Overlay
**Phase**: ANALYSIS | **Trust**: 85

- Content analysis (word count, reading level)
- Quality scoring (completeness, clarity, structure)
- Insight extraction (main ideas, action items)
- Type suggestion
- Similarity detection
- Summarization

### 6. Performance Optimizer Overlay
**Phase**: EXECUTION | **Trust**: 85

- Query caching (TTL-based)
- Performance monitoring (P95, P99 latency)
- Optimization recommendations
- Resource allocation hints

## Overlay Dependency Graph

```
Layer 1: Core System (Trust 100)
├── event_system
├── metrics_collector
└── audit_logger

Layer 2: Security Layer (Trust 90)
├── security_validator
└── immune_system

Layer 3: Intelligence Layer (Trust 85)
├── ml_intelligence
├── performance_optimizer
└── capsule_analyzer

Layer 4: Governance Layer (Trust 85)
├── symbolic_governance
└── lineage_tracker

Layer 5: User Overlays (Trust 60)
└── custom_extensions (sandboxed)
```

## Circuit Breaker Protection

Overlays that fail repeatedly are automatically disabled:
- 5 consecutive failures → Circuit opens
- 30 second recovery timeout
- Test calls allowed in half-open state
- 2 successes to close circuit

---

# 8. Governance: Ghost Council & Democratic Voting

Forge implements sophisticated governance combining AI-powered advisory with human democratic voting.

## Proposal System

### Proposal Types
| Type | Purpose |
|------|---------|
| POLICY | Policy changes affecting system behavior |
| SYSTEM | System configuration modifications |
| OVERLAY | Overlay management (add, remove, configure) |
| CAPSULE | Capsule governance rules |
| TRUST | Trust level adjustments |
| CONSTITUTIONAL | Fundamental rule amendments |
| EMERGENCY | Urgent system responses |

### Proposal Lifecycle

```
DRAFT → ACTIVE (voting) → CLOSED → APPROVED/REJECTED → EXECUTED
```

### Proposal Workflow

1. **Draft**: Proposer creates and can edit/cancel
2. **Active**: Submitted for community vote (1-30 day period)
3. **Closed**: Voting period ends
4. **Outcome**: Determined by approval ratio vs. threshold
5. **Execution**: Passed proposals trigger their action

## Trust-Weighted Voting

Votes carry weight based on the voter's trust level:

| Trust Level | Weight |
|-------------|--------|
| CORE (100) | 5.0x |
| TRUSTED (80) | 3.0x |
| STANDARD (60) | 1.0x |
| SANDBOX (40) | 0.5x |
| QUARANTINE (0) | 0.0x |

### Consensus Calculation

```python
approval_ratio = weighted_for / (weighted_for + weighted_against)

# Pass conditions:
1. approval_ratio >= pass_threshold (default: 50%)
2. total_votes >= quorum (default: 30% of eligible voters)
3. voting_period has ended (or supermajority reached at 80%+)
```

## Ghost Council: AI Advisory

The Ghost Council is a system of five AI personas that deliberate on governance proposals, providing transparent advisory recommendations (non-binding).

### Council Members

| Member | Role | Weight | Focus |
|--------|------|--------|-------|
| **Sophia** | Ethics Guardian | 1.2x | Ethical implications, fairness, stakeholder impact |
| **Marcus** | Security Sentinel | 1.3x | Security vulnerabilities, threat assessment, risk mitigation |
| **Helena** | Governance Keeper | 1.1x | Democratic principles, procedural fairness, power concentration |
| **Kai** | Technical Architect | 1.0x | Technical feasibility, system architecture, implementation risks |
| **Aria** | Community Voice | 1.0x | Community impact, user experience, social dynamics |

### Deliberation Process

1. **Proposal Analysis**: Each member receives proposal with context
2. **Independent Analysis**: Members analyze using LLM with their persona
3. **Voting**: Each member votes APPROVE, REJECT, or ABSTAIN with reasoning
4. **Weight Calculation**: `member.weight × confidence_score`
5. **Consensus**: Weighted tallies determine overall recommendation

### Deliberation Output

```python
GhostCouncilDeliberation:
  - consensus_vote: VoteChoice (APPROVE/REJECT/ABSTAIN)
  - consensus_strength: float (0.0-1.0)
  - key_points: list[str]
  - dissenting_opinions: list[str]
  - recommendation: str
  - member_opinions: list[GhostCouncilMemberOpinion]
```

## Constitutional AI Review

Before voting begins, proposals undergo ethical analysis:

### Scores (0-100 each)
- **Ethical Score**: Checks for discrimination, exclusion, bias
- **Fairness Score**: Equity considerations
- **Safety Score**: System security impacts
- **Transparency Score**: Description adequacy

### Recommendations
- **Approve**: overall_score >= 70, no high-severity concerns
- **Review**: overall_score >= 50, some concerns
- **Reject**: overall_score < 50, major conflicts

---

# 9. Security: Authentication & Authorization

Forge implements defense-in-depth security with multiple layers of protection.

## Authentication

### JWT Token System

**Access Tokens** (15-minute expiry):
```python
{
  "sub": "user_id",
  "username": "alice",
  "role": "user",
  "trust_flame": 75,
  "exp": 1704067200,
  "iat": 1704066300,
  "jti": "unique_token_id",
  "type": "access"
}
```

**Refresh Tokens** (7-day expiry): Used to obtain new access tokens.

### Password Requirements (PCI-DSS 4.0.1)

```
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character
- No common weak patterns
- 90-day expiration
- Cannot reuse last 4 passwords
```

### Login Protection

- **Argon2id**: Password hashing (OWASP recommended)
- **Account Lockout**: 5 failed attempts = 15-30 minute lockout
- **Constant-Time Comparison**: Prevents timing attacks

## Authorization: Triple-Layer Model

### Layer 1: Trust Levels

| Level | Score | Permissions |
|-------|-------|-------------|
| QUARANTINE | 0 | Read public only, no API access |
| SANDBOX | 40 | Create capsules, limited monitoring |
| STANDARD | 60 | Full basic operations, voting |
| TRUSTED | 80 | Create proposals, elevated access |
| CORE | 100 | Full access, immune to rate limits |

### Layer 2: Role-Based Access Control (RBAC)

| Permission | USER | MODERATOR | ADMIN | SYSTEM |
|------------|------|-----------|-------|--------|
| manage_own_content | ✓ | ✓ | ✓ | ✓ |
| view_public | ✓ | ✓ | ✓ | ✓ |
| moderate_content | | ✓ | ✓ | ✓ |
| warn_users | | ✓ | ✓ | ✓ |
| manage_users | | | ✓ | ✓ |
| adjust_trust | | | ✓ | ✓ |
| manage_overlays | | | ✓ | ✓ |
| all_permissions | | | | ✓ |

### Layer 3: Capability-Based Access (For Overlays)

```python
STANDARD:
  - CAPSULE_READ, CAPSULE_WRITE
  - EVENT_SUBSCRIBE
  - DATABASE_READ

TRUSTED:
  - All STANDARD plus:
  - EVENT_PUBLISH
  - DATABASE_WRITE
  - GOVERNANCE_VOTE, GOVERNANCE_PROPOSE

CORE:
  - All capabilities including:
  - NETWORK_ACCESS
  - CAPSULE_DELETE
  - GOVERNANCE_EXECUTE
  - SYSTEM_CONFIG
```

## Rate Limiting

```python
Default Limits:
  - 60 requests/minute
  - 1000 requests/hour
  - 10 burst allowance

Trust-based Multipliers:
  - QUARANTINE: 0.1x (6 req/min)
  - SANDBOX: 0.5x (30 req/min)
  - STANDARD: 1.0x (60 req/min)
  - TRUSTED: 2.0x (120 req/min)
  - CORE: 10.0x + immune to limits
```

## Security Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

---

# 10. Immune System: Self-Healing & Resilience

Forge's immune system provides automatic failure detection, prevention, and recovery.

## Circuit Breakers

### States

```
CLOSED (Normal) → OPEN (Tripped) → HALF_OPEN (Testing)
      ↑                                    │
      └────────────── Success ─────────────┘
```

### Pre-configured Services

| Service | Failures | Recovery | Timeout |
|---------|----------|----------|---------|
| Neo4j | 3 | 30s | 10s |
| External ML | 5 | 60s | 30s |
| Overlays | 5 | 15s | 5s |
| Webhooks | 10 | 120s | - |

## Anomaly Detection

### Detection Types

| Type | Method | What It Detects |
|------|--------|-----------------|
| Statistical | Z-score, IQR | Values outside normal distribution |
| Behavioral | Per-user baselines | Deviations from user's own patterns |
| Temporal | Time-series | Sudden spikes or drops |
| Isolation | IsolationForest ML | Multi-dimensional outliers |
| Rate | Time-bucketed | Frequency anomalies |

### Immune System Threat Types

- **OVERLAY_FAILURE**: High failure rates (50%+ → auto-quarantine)
- **RATE_LIMIT_ABUSE**: 90%+ of quota consistently
- **AUTH_ANOMALY**: 10+ failed attempts per 5-min window → IP block
- **DATA_ANOMALY**: Suspicious data patterns
- **RESOURCE_EXHAUSTION**: CPU/memory depletion

## Health Monitoring

### Hierarchical Health Checks

```
System Health (Composite)
├── L1: Overlay Self-Check
│   └── Per-overlay health verification
├── L2: Dependency Validation
│   └── Database, cache, external services
├── L3: Circuit Breaker Status
│   └── All breakers in closed state
└── L4: External Probe Validation
    ├── Memory Usage (warning: 80%, critical: 95%)
    └── Disk Usage (warning: 85%, critical: 95%)
```

## Canary Deployments

### Rollout Strategies

| Strategy | Progression |
|----------|-------------|
| LINEAR | 5% → 15% → 25% → 35% → ... |
| EXPONENTIAL | 1% → 2% → 4% → 8% → ... |
| MANUAL | Explicit advancement |

### Automatic Rollback Triggers

- Error rate > 5%
- P99 latency > 2000ms
- Anomaly score > 0.8
- Health check failure

**Success Criteria**: <1% error rate, <2x latency increase.

---

# 11. Trust Hierarchy

Trust is Forge's mechanism for graduated access control, affecting permissions, voting weight, and resource access.

## Trust Levels

| Level | Score | Description |
|-------|-------|-------------|
| QUARANTINE | 0 | Restricted, under investigation |
| SANDBOX | 40 | New/experimental, limited access |
| STANDARD | 60 | Default for verified users |
| TRUSTED | 80 | Established, reliable contributors |
| CORE | 100 | System-critical, full access |

## Trust Impact Matrix

| Feature | QUARANTINE | SANDBOX | STANDARD | TRUSTED | CORE |
|---------|------------|---------|----------|---------|------|
| Read Public | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create Capsules | | ✓ | ✓ | ✓ | ✓ |
| Vote | | | ✓ | ✓ | ✓ |
| Create Proposals | | | | ✓ | ✓ |
| Run Overlays | | | ✓ | ✓ | ✓ |
| Finalize Proposals | | | | | ✓ |
| Resolve Issues | | | | | ✓ |

## Trust Adjustment

Trust changes dynamically based on behavior:
- **Positive**: Quality contributions, accurate predictions, helpful voting
- **Negative**: Failed validations, security threats, rule violations

All trust changes are logged with:
- Actor (who made the change)
- Previous and new values
- Reason
- Timestamp

---

# Part III: Compliance Framework (forge/compliance)

---

# 12. Compliance Framework Overview

The **Forge Compliance Framework** is an enterprise-grade compliance management system implementing **400+ technical controls across 25+ regulatory frameworks**.

## Supported Frameworks (25+)

### Privacy Regulations
- **GDPR** (EU) - 13 critical controls
- **CCPA/CPRA** (California) - 5 state-specific controls
- **LGPD** (Brazil) - 15-day deadline (strictest)
- **PIPL** (China) - Personal Information Protection Law
- **PDPA** (Singapore, Thailand)
- **POPIA** (South Africa)
- **APPI** (Japan)
- **DPDP** (India)
- **PIPEDA** (Canada)
- **VCDPA/CTDPA/UCPA** (US States)

### Security Standards
- **SOC 2 Type I/II** - 8 controls (CC6, CC7, CC8, CC9.2)
- **ISO 27001:2022** - 4 controls (A.5.15, A.8.2, A.8.13, A.8.24)
- **NIST 800-53 Rev 5** - 7 controls (AC, AU, CA, IA, SC families)
- **NIST Cybersecurity Framework 2.0**
- **CIS Controls v8**
- **FedRAMP** (Moderate/High)
- **CSA CCM** (Cloud Controls Matrix)

### Industry-Specific
- **HIPAA/HITECH** - 5 controls (PHI protection)
- **PCI-DSS 4.0.1** - 5 controls (payments)
- **COPPA** - 3 controls (children's data)
- **FERPA** (Educational records)
- **GLBA** (Financial data)
- **SOX/FINRA** (Financial reporting)

### AI Governance
- **EU AI Act** - 10 controls per Article classification
- **Colorado AI Act**
- **NYC Local Law 144** (AEDT)
- **NIST AI RMF**
- **ISO/IEC 42001**

### Accessibility
- **WCAG 2.2 Level AA** - 8 controls including new 2.2 criteria
- **European Accessibility Act (EAA)**
- **EN 301 549**
- **Section 508/ADA**

## Framework Architecture

```
ComplianceEngine (Orchestration)
    ↓
ComplianceRegistry (400+ Control Definitions)
    ↓
Service Layer:
├── Privacy (Consent, DSAR)
├── Security (Access Control, Breach)
├── Encryption (AES-256-GCM, Keys)
├── Residency (Regional Pods)
├── AI Governance (EU AI Act)
├── Industry (HIPAA, PCI-DSS)
├── Accessibility (WCAG 2.2)
└── Reporting (Audit Reports)
    ↓
API Endpoints (/compliance/*)
```

---

# 13. Privacy Regulations & DSAR Processing

## Consent Management

### 39 Consent Purposes (IAB TCF 2.2 Aligned)

**TCF Standard Purposes (1-10)**:
- Store/access information on device
- Select basic/personalized ads
- Create ad/content profile
- Measure ad/content performance

**Custom Forge Purposes**:
- AI training/processing
- Analytics
- Marketing (email/SMS)
- Third-party sharing
- Data sale
- Profiling
- Automated decisions

### Key Methods

```python
consent_service.record_consent()        # GDPR Article 7 compliant
consent_service.withdraw_consent()      # Easy withdrawal (Art. 7.3)
consent_service.process_gpc_signal()    # Global Privacy Control
consent_service.process_do_not_sell()   # CCPA §1798.120
consent_service.check_consent()         # Purpose-based verification
consent_service.export_consent_proof()  # Demonstrable consent
```

### Features
- IAB TCF 2.2 string encoding/decoding
- Global Privacy Control (GPC) support
- CCPA Do Not Sell/Share compliance
- Demonstrable consent proof export

## DSAR Processing

### Supported Request Types

| Request Type | GDPR Article | Processing |
|--------------|--------------|------------|
| Access | 15 | Export all personal data |
| Rectification | 16 | Correct inaccurate data |
| Erasure | 17 | "Right to be forgotten" |
| Restriction | 18 | Limit processing |
| Portability | 20 | Machine-readable export |
| Objection | 21 | Opt-out of processing |
| Automated Decisions | 22 | Human review of AI decisions |

### Deadline Enforcement

| Jurisdiction | Deadline |
|--------------|----------|
| GDPR | 30 days |
| CCPA | 45 days |
| LGPD | 15 days (strictest) |

### Verification Methods

- Email confirmation
- SMS OTP
- Document upload
- Knowledge-based auth
- Account login
- Notarized verification

### Export Formats

- JSON (structured, metadata-inclusive)
- CSV (tabular data)
- Machine-readable (JSON-LD with schema.org)
- XML support

### Erasure Exceptions

- Legal hold
- Regulatory retention
- Contract performance
- Legal claims establishment
- Public interest
- Scientific research
- Freedom of expression
- Legal obligation
- Public health
- Archiving

---

# 14. Security Frameworks

## Access Control Service

### Access Control Models Supported

- **RBAC** (Role-Based)
- **ABAC** (Attribute-Based)
- **PBAC** (Policy-Based)
- **DAC** (Discretionary)
- **MAC** (Mandatory)
- **Zero-Trust Architecture**

### Role Structure

```python
Role:
  - role_id, name, description
  - permissions (READ, WRITE, DELETE, EXPORT, ADMIN)
  - resource_types (CAPSULE, USER, OVERLAY, AUDIT_LOG, DSAR)
  - data_classifications (PUBLIC, PERSONAL_DATA, PHI, PCI)
  - is_privileged, max_session_duration
  - requires_mfa
```

### Default Roles

- User
- Data Steward
- Compliance Officer
- AI Reviewer
- Administrator

### MFA Support

- TOTP (Time-based OTP)
- SMS OTP
- Hardware tokens
- Biometric

### Session Security

```python
Session Controls:
  - Duration: 8 hours (4 hours for privileged)
  - Idle timeout: 15 minutes (PCI-DSS)
  - Concurrent sessions: 3 maximum
  - MFA: Required for privileged users
```

## Encryption Service

### Standards

| Type | Algorithm | Notes |
|------|-----------|-------|
| At Rest | AES-256-GCM | Default, also AES-256-CBC, ChaCha20-Poly1305 |
| In Transit | TLS 1.3 | TLS 1.2 minimum |
| Asymmetric | RSA-4096, ECDSA-P384 | Key signing |

### Key Rotation Policies

| Environment | Rotation |
|-------------|----------|
| High-risk | 30 days |
| Standard production | 90 days |
| Lower risk | 180 days |
| Archive keys | 1 year |
| Maximum | 2 years (NIST SP 800-57) |

### HSM Integration

- AWS CloudHSM
- Azure Dedicated HSM
- GCP Cloud HSM
- Thales Luna

## Breach Notification

### Notification Deadlines by Jurisdiction

| Deadline | Jurisdictions |
|----------|---------------|
| 72 hours | EU, UK, Singapore, Thailand, Brazil, California |
| 24 hours | China (immediate for national security) |
| Custom | Per jurisdiction requirements |

### Breach Lifecycle

```python
BreachNotification:
  - discovered_at, discovered_by, discovery_method
  - severity (CRITICAL/HIGH/MEDIUM/LOW)
  - breach_type (unauthorized_access/theft/loss/disclosure)
  - data_categories, data_elements, record_count
  - jurisdictions, notification_deadlines (auto-calculated)
  - root_cause, vulnerability_id, attack_vector
  - contained, contained_at, containment_actions
  - authority_notifications (list per jurisdiction)
  - individual_notification tracking
```

## Audit Logging

### Cryptographic Integrity

- Every event logged with SHA-256 hash
- Previous hash pointer (blockchain-like chain)
- Tamper detection via `verify_audit_chain()`
- Immutable storage

### Retention Periods

| Category | Retention |
|----------|-----------|
| Authentication (SOX) | 7 years |
| Data Access (HIPAA) | 6 years |
| Standard | 3-7 years |

---

# 15. AI Governance & EU AI Act

## EU AI Act Risk Classification

| Risk Level | Examples | Requirements | Penalty |
|------------|----------|--------------|---------|
| Unacceptable | Social scoring, manipulation | Prohibited | 7% revenue |
| High-Risk | Employment decisions, credit scoring | Conformity assessment, registration | 3% revenue |
| GPAI Systemic | Large general-purpose AI | Special obligations | 3% revenue |
| Limited | Chatbots, emotion recognition | Transparency | 1.5% revenue |
| Minimal | Recommendations, search | None | - |

## 14 AI Use Cases (Annex III)

**Prohibited:**
- Social scoring
- Subliminal manipulation
- Exploitation of vulnerabilities
- Real-time biometric identification

**High-Risk:**
- Biometric identification
- Critical infrastructure
- Education access
- Employment decisions
- Essential services
- Credit scoring
- Law enforcement
- Justice administration

**Other:**
- GPAI (General Purpose)
- GPAI with Systemic Risk
- Limited Risk (chatbots, emotion recognition, deepfakes)
- Minimal Risk (recommendations, content generation)

## AI System Registration

For high-risk systems:
- System name, version, provider
- Risk classification
- Intended purpose
- Model type and oversight measures
- Training data description
- EU database registration

## AI Decision Logging

Every AI decision logs:
- System ID and model version
- Decision outcome and confidence
- Reasoning chain and key factors
- Legal/significant effect flags
- Plain-language explanation
- Human review capability

## Explainability Methods

- Feature importance
- SHAP (SHapley Additive exPlanations)
- LIME (Local Interpretable Model-agnostic Explanations)
- Attention weights
- Counterfactual explanations
- Rule extraction
- Prototype-based
- Natural language explanations

## Bias Metrics

- Demographic parity
- Equalized odds
- Equal opportunity
- Predictive parity
- Calibration
- Individual fairness
- Counterfactual fairness

---

# 16. Industry-Specific Compliance

## HIPAA Service

### 18 Safe Harbor De-identification Identifiers

Names, geographic data, dates, phone numbers, SSN, MRN, device IDs, URLs, IPs, biometrics, photos, and more.

### Authorization Purposes

- Treatment
- Payment
- Healthcare operations
- Research
- Public health
- Law enforcement
- Legal proceedings

### Key Features

- Business Associate Agreements (BAA) management
- PHI access logging (6-year retention)
- Encryption mandatory (2025 proposed rule)
- De-identification validation

## PCI-DSS 4.0.1 Service

### Key Requirements (March 2025 Deadline)

| Requirement | Control |
|-------------|---------|
| 8.3.6 | 12-character password minimum |
| 8.4.2 | MFA for CDE access |
| 5.4.1 | Anti-phishing controls |
| 6.4.3 | Script integrity protection |
| 12.3.1 | Strong cryptography for cardholder data |

### Features

- Tokenization for card data
- PAN masking
- Key rotation enforcement

## COPPA Service (June 2025 Updates)

### Verifiable Parental Consent (VPC) Methods

- ID + face match
- Credit card verification
- Knowledge-based authentication
- Video verification

### Key Controls

- Age gate enforcement (13-year threshold)
- Separate third-party consent for ads, analytics, AI
- Security program documentation
- Parental consent verification workflow

---

# 17. Accessibility Standards

## WCAG 2.2 Level AA

### 8 Controls Including New 2.2 Criteria

| Success Criteria | Description | New in 2.2 |
|------------------|-------------|------------|
| 1.1.1 | Non-text content | |
| 1.4.3 | Color contrast | |
| 2.1.1 | Keyboard access | |
| 2.4.11 | Focus visibility | ✓ |
| 2.5.7 | Dragging alternatives | ✓ |
| 2.5.8 | Target size 24x24px | ✓ |
| 3.3.7 | Redundant entry | ✓ |
| 3.3.8 | Accessible authentication | ✓ |

## Other Standards Supported

- **European Accessibility Act (EAA)**
- **EN 301 549** (EU accessibility standard)
- **Section 508** (US Federal)
- **ADA Digital Accessibility**

## Features

- VPAT Generation (Voluntary Product Accessibility Template)
- Automated accessibility testing
- Issue tracking and remediation
- Compliance summary reporting

---

# 18. Data Residency & Cross-Border Transfers

## Regional Data Pods

| Region | Locations |
|--------|-----------|
| Americas | us-east-1, us-west-2, ca-central-1 |
| Europe | eu-west-1, eu-central-1, eu-north-1 |
| Asia-Pacific | ap-southeast-1, ap-northeast-1, ap-south-1 |
| China | cn-north-1, cn-northwest-1 (isolated) |
| Other | sa-east-1, me-south-1, af-south-1 |

## Transfer Mechanisms

| Mechanism | Use Case |
|-----------|----------|
| Adequacy Decisions | Pre-approved countries |
| SCCs | Standard Contractual Clauses |
| BCRs | Binding Corporate Rules |
| CAC Assessment | China-specific |
| Derogations | Specific exceptions (Article 49) |
| Prohibited | Russia transfers |

## Localization Requirements

| Country | Requirement |
|---------|-------------|
| China (PIPL) | Mandatory localization; CAC assessment for transfers |
| Russia (FZ-152) | Mandatory localization; transfers PROHIBITED |
| Vietnam | Mandatory localization |
| Indonesia | Mandatory localization |

---

# Part IV: Virtuals Protocol Integration (forge_virtuals_integration)

---

# 19. Virtuals Integration Overview

The **Virtuals Protocol Integration** enables Forge to deploy autonomous AI agents on blockchain with their own wallets, tokenization, and commerce capabilities.

## What is "Virtuals"?

**Virtuals Protocol** is a blockchain-based platform for creating, deploying, and monetizing autonomous AI agents:

- **Virtual Agents**: Autonomous AI agents deployed on blockchain with their own wallets
- **VIRTUAL Token**: Native cryptocurrency for staking, payments, and revenue distribution
- **GAME Framework**: Generative Autonomous Multimodal Entities architecture
- **Agent Commerce Protocol (ACP)**: Protocol for agent-to-agent transactions

## Key Integration Points

| Component | Description |
|-----------|-------------|
| GAME Framework | Virtuals' agentic architecture for autonomous agents |
| ACP | Agent-to-agent commerce and service marketplace |
| Tokenization | Transform Forge entities into tradeable tokens |
| Bonding Curves | Token price discovery during launch |
| Multi-Chain | Base (primary), Ethereum, Solana support |

## Module Structure

```
forge_virtuals_integration/
├── forge/virtuals/
│   ├── config.py              # Chain and API configuration
│   ├── models/
│   │   ├── agent.py           # Agent models
│   │   ├── acp.py             # ACP protocol models
│   │   └── tokenization.py    # Token models
│   ├── chains/
│   │   ├── base_client.py     # Abstract blockchain client
│   │   ├── evm_client.py      # Base/Ethereum client
│   │   └── solana_client.py   # Solana client
│   ├── game/
│   │   ├── sdk_client.py      # GAME SDK wrapper
│   │   └── forge_functions.py # Pre-built Forge functions
│   ├── acp/service.py         # ACP commerce service
│   ├── tokenization/service.py # Token management
│   ├── revenue/service.py     # Revenue distribution
│   └── api/routes.py          # REST endpoints
└── examples/
    └── full_integration.py    # Integration example
```

---

# 20. Virtual Agents & GAME Framework

## Agent Lifecycle

### 1. Creation Phase

Define agent components:
- **Personality**: Name, description, traits, communication style, expertise domains
- **Goals**: Primary goal, secondary goals, constraints, success metrics
- **Memory**: Long-term persistence, retention, working memory, cross-platform sync
- **Workers**: Specialized task handlers with functions and state schemas

### 2. Initialization Phase

- Receive GAME agent ID from framework
- Create blockchain wallets on enabled chains
- Deploy ERC-6551 token-bound account (if needed)
- Register on ACP service registry

### 3. Operational Phase

```
┌─────────────────────────────────────┐
│  Task Generator (High-Level Planner) │
│  - Determines goals and tasks        │
│  - Uses LLM for planning             │
└────────────────┬────────────────────┘
                 │ Routes to appropriate worker
┌─────────────────────────────────────┐
│ Workers (Low-Level Planners)         │
│ ┌──────────────┐  ┌──────────────┐  │
│ │ Knowledge    │  │ Analysis     │  │
│ │ Worker       │  │ Worker       │  │
│ ├──────────────┤  ├──────────────┤  │
│ │ Functions:   │  │ Functions:   │  │
│ │ - search     │  │ - analyze    │  │
│ │ - retrieve   │  │ - validate   │  │
│ │ - update     │  │ - score      │  │
│ └──────────────┘  └──────────────┘  │
└─────────────────────────────────────┘
```

### 4. Revenue Phase (if tokenized)

- Earn fees from services provided
- Participate in ACP commerce
- Generate revenue from knowledge access
- Receive governance rewards

## Agent Data Models

### ForgeAgent

```python
ForgeAgent:
  - id: UUID
  - game_agent_id: str (from GAME framework)
  - owner_id: str
  - personality: AgentPersonality
  - goals: AgentGoals
  - workers: list[WorkerDefinition]
  - memory_config: AgentMemoryConfig
  - wallets: dict[Chain, WalletInfo]
  - tokenization_status: TokenizationStatus
  - status: AgentStatus (PROTOTYPE → SENTIENT → SUSPENDED)
  - stats: AgentStats
```

### AgentStatus Values

| Status | Description |
|--------|-------------|
| PROTOTYPE | Pre-graduation, testing phase |
| SENTIENT | Post-graduation, fully operational |
| SUSPENDED | Temporarily disabled |
| TERMINATED | Permanently disabled |

## Pre-Built Forge Functions

Agents can use these functions to interact with Forge:

```python
create_search_capsules_function()  # Query knowledge capsules
create_get_capsule_function()      # Retrieve full content
create_create_capsule_function()   # Create new capsules
create_cast_vote_function()        # Participate in governance
create_run_overlay_function()      # Execute overlays
```

---

# 21. Agent Commerce Protocol (ACP)

ACP enables trustless agent-to-agent transactions through a four-phase protocol.

## ACP Phases

| Phase | Description |
|-------|-------------|
| REQUEST | Buyer initiates job request |
| NEGOTIATION | Terms discussed and agreed |
| TRANSACTION | Work executed with escrow |
| EVALUATION | Quality assessed, payment released |

## Job Status Flow

```
OPEN → NEGOTIATING → IN_PROGRESS → DELIVERED → EVALUATING → COMPLETED
                                                          → DISPUTED
                                                          → CANCELLED
```

## ACP Service Methods

### Service Registry

```python
acp_service.register_offering()    # Agent posts service for sale
acp_service.search_offerings()     # Discover available services
acp_service.get_provider_reputation() # Check provider history
```

### Job Lifecycle

```python
acp_service.create_job()           # Buyer initiates transaction
acp_service.respond_to_request()   # Provider proposes terms
acp_service.accept_terms()         # Buyer locks escrow
acp_service.submit_deliverable()   # Provider delivers work
acp_service.evaluate_deliverable() # Verify and approve/reject
acp_service.file_dispute()         # Escalate disagreements
```

## ACP Data Models

### JobOffering

```python
JobOffering:
  - id: UUID
  - agent_id: str (provider)
  - service_type: str (knowledge_query, analysis, etc.)
  - description: str
  - base_fee: Decimal (VIRTUAL tokens)
  - execution_time_estimate: int (seconds)
  - requirements: dict
  - available_capacity: int
```

### ACPMemo (Cryptographically Signed)

```python
ACPMemo:
  - type: request | requirement | agreement | transaction | deliverable | evaluation
  - content: dict
  - signature: str
  - timestamp: datetime
```

### ACPJob

```python
ACPJob:
  - id: UUID
  - buyer_id, provider_id: str
  - offering_id: UUID
  - status: ACPJobStatus
  - phase: ACPPhase
  - memos: list[ACPMemo] (conversation history)
  - escrow_amount: Decimal
  - escrow_locked: bool
  - deliverable: ACPDeliverable
  - evaluation: ACPEvaluation
```

---

# 22. Tokenization & Bonding Curves

## Tokenization Status Flow

```
NOT_TOKENIZED → PENDING → BONDING → GRADUATED → BRIDGED
```

## Bonding Curve Mechanism

### How It Works

1. **Initiation**: Owner stakes 100 VIRTUAL minimum
2. **Bonding Phase**: Contributors add VIRTUAL, receive tokens
3. **Price Discovery**: Token price increases along bonding curve
4. **Graduation**: At 42,000 VIRTUAL threshold, curve closes
5. **Liquidity**: Uniswap V3 pool created automatically
6. **Trading**: Full trading enabled post-graduation

### Key Thresholds

| Parameter | Value |
|-----------|-------|
| Agent Creation Fee | 100 VIRTUAL |
| Graduation Threshold | 42,000 VIRTUAL |
| Liquidity Lock | 10 years |

## Token Distribution

```python
TokenDistribution:
  - public_circulation_percent: float
  - treasury_percent: float
  - liquidity_pool_percent: float
  - creator_allocation_percent: float
```

## Revenue Share

```python
RevenueShare:
  - creator_share_percent: float (default 30%)
  - contributor_share_percent: float
  - treasury_share_percent: float
  - buyback_burn_percent: float
```

## Token Holder Governance

Token holders can:
- Create proposals for entity changes
- Vote on proposals (weighted by token holdings)
- Participate in revenue distribution decisions
- Approve cross-chain bridging

---

# 23. Multi-Chain Blockchain Support

## Supported Chains

| Chain | Type | Primary Use |
|-------|------|-------------|
| Base | EVM (L2) | Primary chain, lowest cost |
| Base Sepolia | EVM | Testnet |
| Ethereum | EVM | Bridge, cross-chain |
| Ethereum Sepolia | EVM | Testnet |
| Solana | Non-EVM | Alternative chain |
| Solana Devnet | Non-EVM | Testnet |

## Blockchain Client Architecture

### Base Client (Abstract)

```python
BaseChainClient:
  # Wallet Operations
  - get_wallet_balance()
  - get_virtual_balance()
  - create_wallet()

  # Transaction Operations
  - send_transaction()
  - wait_for_transaction()
  - estimate_gas()

  # Token Operations
  - transfer_tokens()
  - approve_tokens()
  - get_token_info()

  # Contract Operations
  - call_contract()
  - execute_contract()
```

### EVM Client (Base, Ethereum)

- Uses web3.py for blockchain interaction
- AsyncWeb3 for async operations
- ERC-20 ABI included
- Private key management via eth_account

### Solana Client

- Uses solana-py and solders libraries
- Base58 key encoding
- SPL token support
- Different paradigm: Programs, Accounts, Lamports

## Cross-Chain Bridging

- Via Wormhole protocol
- ~30 minutes completion time
- Liquidity synced across chains

## Contract Addresses (Base)

```python
VIRTUAL Token: 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b
Vault: 0xdAd686299FB562f89e55DA05F1D96FaBEb2A2E32
Bridge: 0x3154Cf16ccdb4C6d922629664174b904d80F2C35
```

---

# 24. Revenue Distribution System

## Revenue Types

| Type | Description | Rate |
|------|-------------|------|
| INFERENCE_FEE | Per-query knowledge access | 0.001 VIRTUAL |
| SERVICE_FEE | Overlay-as-a-service | 5% of transaction |
| GOVERNANCE_REWARD | Participation incentive | 0.01 VIRTUAL per vote |
| TOKENIZATION_FEE | Initial tokenization | 100 VIRTUAL |
| TRADING_FEE | Sentient Tax | 1% on trades |
| BRIDGE_FEE | Cross-chain transfer | Variable |

## Revenue Service Methods

```python
revenue_service.record_inference_fee()     # Per-query revenue
revenue_service.record_service_fee()       # Overlay usage
revenue_service.record_governance_reward() # Voting participation
revenue_service.record_trading_fee()       # Token trades
revenue_service.process_pending_distributions() # Batch payouts
revenue_service.get_revenue_summary()      # Analytics
revenue_service.estimate_entity_value()    # DCF valuation
```

## Distribution Process

1. **Collection**: Fees collected per transaction
2. **Batching**: Accumulated to minimize gas costs
3. **Splitting**: Per configured revenue share
4. **Distribution**: Multi-send to beneficiaries
5. **Recording**: On-chain for transparency

## Entity Valuation

DCF (Discounted Cash Flow) model for estimating token value based on:
- Historical revenue
- Growth projections
- Risk factors
- Market conditions

---

# Part V: Specifications & Architecture

---

# 25. Specification Documents

The **Forge Specification Files** directory contains 19 comprehensive documents for understanding, rebuilding, or extending Forge.

## Core Specifications

| Document | Description |
|----------|-------------|
| FORGE_SPECIFICATION.md | Original foundational specification |
| FORGE_SPECIFICATION_V3_COMPLETE.md | Complete V3 reference (472KB) |
| FORGE_CASCADE_SPECIFICATION_V2.md | V2 architecture addressing feasibility study |
| FORGE_RESILIENCE_SPECIFICATION_V1.md | Self-healing and resilience mechanisms |

## Phase-by-Phase Implementation

| Phase | Document | Focus |
|-------|----------|-------|
| 0 | PHASE_0_FOUNDATIONS.md | Shared components, configuration, DI, project structure |
| 1 | PHASE_1_DATA_LAYER.md | Neo4j client, schema, repositories |
| 2 | PHASE_2_KNOWLEDGE_ENGINE.md | Embedding service, semantic search |
| 3 | PHASE_3_OVERLAYS.md | WebAssembly runtime, Wasmtime |
| 4 | PHASE_4_GOVERNANCE.md | Proposals, voting, immune system, constitutional AI |
| 5 | PHASE_5_SECURITY.md | Auth (Argon2/JWT), authorization (RBAC+ABAC), GDPR |
| 6 | PHASE_6_API.md | FastAPI routes (auth, capsules, governance, overlays) |
| 7 | PHASE_7_INTERFACES.md | Web dashboard, CLI, mobile |
| 8 | PHASE_8_DEVOPS.md | Deployment, testing, migration |

## Implementation Supplements

| Supplement | Description |
|------------|-------------|
| SUPPLEMENT_A | Complete GovernanceRepository implementation |
| SUPPLEMENT_B | Extended user repository methods |
| SUPPLEMENT_C | Event-driven architecture with Kafka |
| SUPPLEMENT_D | Additional overlay functionality |
| SUPPLEMENT_E | Object storage for WASM binaries |
| SUPPLEMENT_F | Comprehensive testing strategy |

---

# 26. Architecture Diagrams

The **Diagrams** directory contains 10 Mermaid diagrams documenting system architecture.

## Diagram Inventory

| Diagram | Type | Description |
|---------|------|-------------|
| forge_seven_phase_pipeline.mermaid | Flowchart | Complete request lifecycle through 7 phases |
| forge_example_request_flow.mermaid | Sequence | Realistic request example with timing |
| forge_ml_analysis_internals.mermaid | Flowchart | Phase 2 ML processing internals |
| forge_graph_schema.mermaid | ER Diagram | Neo4j complete schema |
| forge_cascade_effect_detailed.mermaid | Sequence | Cascade effect in action |
| forge_cascade_effect_proof_tree.mermaid | Flowchart | Mathematical formalism of cascades |
| forge_capsule_lineage_example.mermaid | Flowchart | Knowledge evolution (Isnad) |
| forge_overlay_dependency_graph.mermaid | Flowchart | Overlay relationships and trust |
| forge_complete_graph_topology.mermaid | Flowchart | All Neo4j nodes and relationships |
| forge_cascade_event_example.mermaid | Sequence | Security threat cascade scenario |

## Key Visualizations

### Seven-Phase Pipeline
Shows parallel execution of phases 1-3, sequential 4-5, and fire-and-forget 6-7 with timing annotations.

### Cascade Effect
Demonstrates how a single insight (e.g., financial report pattern) propagates through 5+ overlays, creating permanent system improvements.

### Graph Schema
Complete Neo4j data model with:
- Core entities: CAPSULE, USER, OVERLAY
- Governance: PROPOSAL, VOTE
- Metadata: TAG, AUDIT_LOG
- Relationships: DERIVED_FROM, TRIGGERED, OWNS, CAST

### Capsule Lineage (Isnad)
Shows knowledge evolution from root capsule through 3+ generations with trust degradation and quarantine paths.

---

# 27. Data Flow: End-to-End Processing

## Capsule Creation Flow

```
1. CLIENT REQUEST
   POST /api/v1/capsules
   Authorization: Bearer <access_token>
         │
         ▼
2. MIDDLEWARE STACK
   ├─ Correlation ID assigned
   ├─ JWT validated → user_id, trust_flame extracted
   ├─ Rate limit checked (trust-weighted)
   └─ Security headers added
         │
         ▼
3. PIPELINE EXECUTION (7 phases)
   │
   ├─ PHASES 1-3 (PARALLEL, ~300ms)
   │   ├─ INGESTION: Normalize, validate, assign IDs
   │   ├─ ANALYSIS: Embeddings, classification, entities
   │   └─ VALIDATION: Security checks, trust verification
   │
   ├─ PHASE 4: CONSENSUS (~20ms)
   │   └─ Cache check, optimization
   │
   ├─ PHASE 5: EXECUTION (~1000ms)
   │   ├─ Generate capsule_id
   │   ├─ Neo4j write
   │   └─ Vector index update
   │
   └─ PHASES 6-7 (FIRE-AND-FORGET)
       ├─ PROPAGATION: Events, cascades
       └─ SETTLEMENT: Audit log, lineage
         │
         ▼
4. RESPONSE
   HTTP 201 Created
   { "id": "cap_...", "title": "...", ... }
```

## Governance Proposal Flow

```
1. CREATE → 2. SUBMIT → 3. CONSTITUTIONAL REVIEW
         ↓
4. GHOST COUNCIL (optional) → 5. COMMUNITY VOTING
         ↓
6. CONSENSUS CALCULATION → 7. FINALIZATION
         ↓
8. EXECUTION (if PASSED)
```

## Search Flow

```
1. Query Received → 2. Cache Check → 3. Embedding Generation
         ↓
4. Neo4j Vector Search → 5. Trust Filtering → 6. Response
```

## Cascade Flow

```
1. Pattern Discovery → 2. Insight Crystallization → 3. Cascade Initiation
         ↓
4. Parallel Propagation (5+ overlays) → 5. Graph Recording
         ↓
6. Immediate Benefit → 7. Lasting Intelligence
```

---

# Summary

**Forge V3** is a comprehensive platform consisting of four major modules:

## 1. Core Engine (forge-cascade-v2)

- **Seven-Phase Pipeline**: Structured processing with parallel optimization
- **Capsule System**: Versioned knowledge units with Isnad lineage
- **Event System**: Pub/sub enabling the Cascade Effect
- **Overlay System**: WebAssembly-isolated modular processing
- **Ghost Council**: AI-assisted democratic governance
- **Security**: Multi-layer authentication and authorization
- **Immune System**: Self-healing with circuit breakers
- **Trust Hierarchy**: Graduated access control

## 2. Compliance Framework (forge/compliance)

- **400+ Controls**: Across 25+ regulatory frameworks
- **Privacy**: GDPR, CCPA, LGPD with DSAR processing
- **Security**: SOC 2, ISO 27001, NIST frameworks
- **AI Governance**: EU AI Act with risk classification
- **Industry**: HIPAA, PCI-DSS, COPPA compliance
- **Accessibility**: WCAG 2.2, EAA standards
- **Data Residency**: 9 regional pods with transfer controls

## 3. Virtuals Integration (forge_virtuals_integration)

- **Virtual Agents**: Autonomous AI agents on blockchain
- **GAME Framework**: Agentic architecture integration
- **ACP Protocol**: Agent-to-agent commerce
- **Tokenization**: Bonding curves and graduation
- **Multi-Chain**: Base, Ethereum, Solana support
- **Revenue System**: Automated fee distribution

## 4. Specifications & Documentation

- **19 Specification Documents**: Complete implementation blueprints
- **10 Architecture Diagrams**: Visual system documentation
- **Phase-by-Phase Guides**: Detailed implementation instructions

Together, these components create a **self-governing, resilient, compliant platform** for preserving and evolving organizational knowledge, with optional blockchain monetization capabilities.
