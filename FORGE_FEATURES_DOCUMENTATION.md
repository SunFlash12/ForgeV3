# Forge V3: Complete Feature Documentation

## Institutional Memory Engine - Comprehensive Technical Reference

---

# Table of Contents

1. [System Overview](#1-system-overview)
2. [The Seven-Phase Pipeline](#2-the-seven-phase-pipeline)
3. [Capsule System: Knowledge Management](#3-capsule-system-knowledge-management)
4. [Event System: The Cascade Effect](#4-event-system-the-cascade-effect)
5. [Overlay System: Modular Processing](#5-overlay-system-modular-processing)
6. [Governance: Ghost Council & Democratic Voting](#6-governance-ghost-council--democratic-voting)
7. [Security: Authentication & Authorization](#7-security-authentication--authorization)
8. [Immune System: Self-Healing & Resilience](#8-immune-system-self-healing--resilience)
9. [Compliance Framework](#9-compliance-framework)
10. [Trust Hierarchy](#10-trust-hierarchy)
11. [Data Flow: End-to-End Processing](#11-data-flow-end-to-end-processing)

---

# 1. System Overview

Forge V3 is an **Institutional Memory Engine** designed to capture, evolve, and govern organizational knowledge through a sophisticated system of interconnected components. At its core, Forge treats knowledge as living entities called **Capsules** that flow through a **Seven-Phase Pipeline**, are processed by specialized **Overlays**, and are governed democratically through the **Ghost Council**.

## Core Design Principles

- **Knowledge as First-Class Citizens**: Every piece of information is a versioned, traceable Capsule with lineage
- **Cascade Effect**: Insights propagate through the system, triggering related processing automatically
- **Democratic Governance**: AI-assisted decision-making with human oversight via the Ghost Council
- **Self-Healing**: The Immune System automatically detects and recovers from failures
- **Compliance by Design**: Regulatory requirements are enforced through configuration, not code changes
- **Trust-Based Access**: A graduated trust hierarchy controls what users and overlays can do

## Technology Stack

- **Backend**: Python 3.12, FastAPI, async/await throughout
- **Database**: Neo4j 5.x (graph database for relationships and lineage)
- **Cache**: Redis (distributed caching and rate limiting)
- **Frontend**: React 19, TypeScript, Tailwind CSS v4, Vite
- **ML**: Sentence-Transformers for embeddings, scikit-learn for anomaly detection
- **Infrastructure**: Docker, Nginx, Prometheus monitoring

---

# 2. The Seven-Phase Pipeline

Every operation in Forge flows through a structured seven-phase pipeline. This ensures consistent processing, security validation, governance approval, and proper audit trails.

## Phase Overview

```
INGESTION → ANALYSIS → VALIDATION → CONSENSUS → EXECUTION → PROPAGATION → SETTLEMENT
```

### Phase 1: INGESTION
**Purpose**: Receive and normalize incoming data

- Validates request format and required fields
- Normalizes data structures (tags lowercased, whitespace trimmed)
- Assigns correlation IDs for request tracking
- Applies input size limits (max 1MB content)

**Timeout**: 3 seconds | **Required**: Yes | **Parallel**: No

### Phase 2: ANALYSIS
**Purpose**: Extract meaning through ML processing

- **Embedding Generation**: Creates 1536-dimensional vector representations for semantic search
- **Content Classification**: Categorizes into technical, business, personal, educational, creative, or governance
- **Entity Extraction**: Identifies emails, URLs, dates, monetary values, phone numbers
- **Pattern Detection**: Finds questions, code blocks, lists, technical content
- **Sentiment Analysis**: Scores content from -1.0 (negative) to +1.0 (positive)
- **Quality Scoring**: Evaluates completeness, clarity, structure, depth

**Overlays**: MLIntelligenceOverlay, CapsuleAnalyzerOverlay
**Timeout**: 10 seconds | **Required**: Yes | **Parallel**: Yes (overlays run concurrently)

### Phase 3: VALIDATION
**Purpose**: Security checks and trust verification

- **Content Policy**: Blocks secrets, credentials, prohibited patterns
- **Trust Verification**: Confirms user has sufficient trust level for the operation
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
- Optional Ghost Council deliberation for AI advisory

**Overlays**: GovernanceOverlay
**Timeout**: 5 seconds | **Required**: No (skippable for routine operations)

### Phase 5: EXECUTION
**Purpose**: Core processing and state changes

- Performs the actual requested operation (create, update, delete)
- Writes to Neo4j database
- Updates relationships and indices
- Manages transactions with rollback on failure

**Overlays**: PerformanceOptimizerOverlay (caching)
**Timeout**: 10 seconds | **Required**: Yes | **Max Retries**: 1

### Phase 6: PROPAGATION
**Purpose**: Cascade effect and event emission

- Emits events to notify other system components
- Triggers cascade chains for insight propagation
- Routes events to subscribed overlays
- Manages hop limits to prevent infinite loops (max 5 hops)

**Timeout**: 5 seconds | **Required**: Yes | **Parallel**: Yes

### Phase 7: SETTLEMENT
**Purpose**: Finalization and audit logging

- Records immutable audit entries with cryptographic hashing
- Tracks lineage relationships (Isnad chains)
- Updates metrics and statistics
- Closes the pipeline execution record

**Overlays**: LineageTrackerOverlay
**Timeout**: 3 seconds | **Required**: Yes

## Pipeline Context

Every pipeline execution carries a `PipelineContext` containing:

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

# 3. Capsule System: Knowledge Management

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
  - content: str (1-100,000 characters)
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

Isnad (Arabic: إسناد, "chain of transmission") tracks how knowledge evolves through derivation:

### Symbolic Inheritance
When a Capsule is created from another (forked), it maintains a `parent_id` link forming a **DERIVED_FROM** relationship. This creates acyclic directed graphs representing knowledge evolution.

### Lineage Traversal
```
Original Insight
    └── Fork: Applied to Project A
        └── Fork: Adapted for Mobile
            └── Fork: iOS-specific version
```

### Lineage Features
- **Ancestor Retrieval**: Get all capsules in the derivation chain (max depth: 10)
- **Descendant Discovery**: Find all capsules derived from a given capsule
- **Trust Gradient**: Track how trust levels evolve through the chain
- **Cycle Prevention**: System validates no circular references exist
- **Influence Scoring**: Measures impact based on descendants and trust weighting

### Fork Operation
```python
POST /capsules/{capsule_id}/fork
{
  "title": "Optional new title",
  "content": "Optional modified content",
  "evolution_reason": "Why this fork was created"  # Required
}
```

The fork inherits tags, summary, and metadata while establishing the parent-child relationship.

## Semantic Search

Capsules are searchable through vector similarity:

1. **Query Embedding**: User's search query is embedded into a 1536-dimensional vector
2. **Neo4j Vector Index**: Query `capsule_embeddings` index for similar vectors
3. **Trust Filtering**: Results filtered by minimum trust level
4. **Score Ranking**: Results ordered by cosine similarity (0.0-1.0)

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
CREATE (POST /capsules)
  → Validation Phase (security, trust)
  → Analysis Phase (embedding, classification)
  → Execution Phase (Neo4j write)
  → Settlement Phase (lineage, audit)
  → CAPSULE_CREATED event emitted

UPDATE (PATCH /capsules/{id})
  → Owner verification (or admin)
  → Content re-validation
  → Re-embedding if content changed
  → Cache invalidation
  → CAPSULE_UPDATED event emitted

ARCHIVE (POST /capsules/{id}/archive)
  → Soft delete (is_archived = true)
  → Preserves lineage references
  → Queryable via admin tools

DELETE (DELETE /capsules/{id})
  → Requires TRUSTED trust level
  → Cache invalidation
  → CAPSULE_DELETED event emitted
```

---

# 4. Event System: The Cascade Effect

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

### System Events
- `SYSTEM_EVENT`: General system notifications
- `SYSTEM_ERROR`: Error conditions
- `OVERLAY_REGISTERED`: New overlay activated

## Event Structure

```python
Event:
  - id: UUID
  - type: EventType
  - priority: EventPriority (LOW, NORMAL, HIGH, CRITICAL)
  - payload: dict[str, Any]
  - source: str (e.g., "overlay:ml_intelligence", "api:capsules")
  - correlation_id: UUID (links related events)
  - target_overlays: Optional[list[str]] (broadcast vs. targeted)
  - metadata: dict[str, Any]
  - timestamp: datetime
```

## The Cascade Effect

The Cascade Effect is Forge's mechanism for propagating insights across overlays automatically:

### How Cascades Work

1. **Initiation**: An overlay discovers an insight and publishes `CASCADE_INITIATED`
2. **Chain Creation**: System creates a `CascadeChain` with unique `cascade_id`
3. **First Hop**: Event routed to subscribed overlays (hop_count = 0)
4. **Processing**: Receiving overlay processes and may emit new insights
5. **Propagation**: New insights continue the chain (hop_count increments)
6. **Cycle Prevention**: Visited overlays tracked; cannot receive same cascade twice
7. **Hop Limiting**: Maximum 5 hops prevents infinite loops
8. **Completion**: Chain completes when no more propagation possible

### Cascade Chain Structure

```python
CascadeChain:
  - cascade_id: UUID
  - initiated_by: str (source overlay)
  - events: list[CascadeEvent]
  - total_hops: int
  - overlays_affected: list[str] (prevents cycles)
  - insights_generated: int
  - actions_triggered: int
  - errors_encountered: int

CascadeEvent:
  - id: UUID
  - source_overlay: str
  - insight_type: str
  - insight_data: dict
  - hop_count: int
  - max_hops: int (default: 5)
  - visited_overlays: list[str]
  - impact_score: float (0-1)
```

### Example Cascade Flow

```
1. User creates a DECISION capsule about API authentication
2. MLIntelligenceOverlay analyzes → detects "security" classification
3. Cascade initiated: "security_relevant_content"
4. SecurityValidatorOverlay receives (hop 1)
   → Validates no credentials exposed
   → Emits "security_validated" insight
5. GovernanceOverlay receives (hop 2)
   → Checks if policy proposal needed
   → No action required
6. CapsuleAnalyzerOverlay receives (hop 3)
   → Extracts key decisions and rationale
   → Links to related capsules
7. Cascade completes: 3 hops, 4 overlays affected, 2 insights generated
```

## Event Delivery

### Subscription Model
```python
subscription = event_bus.subscribe(
    event_types={EventType.CAPSULE_CREATED, EventType.CAPSULE_UPDATED},
    handler=my_async_handler,
    min_priority=EventPriority.NORMAL,
    filter_func=lambda e: e.payload.get("type") == "INSIGHT"
)
```

### Delivery Guarantees
- **Concurrent Delivery**: All matching handlers run in parallel
- **Retry Logic**: 3 attempts with exponential backoff (1s base delay)
- **Dead Letter Queue**: Failed events preserved for investigation
- **Timeout**: 30 seconds per handler
- **Metrics**: Published, delivered, failed counts tracked

### Event Queue
- Async queue with 10,000 item capacity
- Background worker processes continuously
- Type indexing for O(1) subscription lookup

---

# 5. Overlay System: Modular Processing

Overlays are self-contained processing modules that extend Forge's capabilities without modifying the core kernel. They subscribe to events, process data within resource constraints, and emit new events to trigger cascades.

## Overlay Architecture

### Base Overlay Contract

Every overlay implements:

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

### Overlay Context

Each execution receives a context with:

```python
OverlayContext:
  - overlay_id: str
  - overlay_name: str
  - execution_id: UUID (unique per execution)
  - triggered_by: str (event ID or "manual")
  - correlation_id: str
  - user_id: Optional[str]
  - trust_flame: int (0-100)
  - capsule_id: Optional[str]
  - proposal_id: Optional[str]
  - capabilities: Set[Capability]
  - fuel_budget: FuelBudget
  - metadata: dict
```

### Resource Constraints (Fuel Budget)

```python
FuelBudget:
  - total_fuel: 1,000,000 (computational units)
  - max_memory_bytes: 10 MB
  - timeout_ms: 5000 (5 seconds)
```

Overlays consume fuel as they operate. Execution halts if fuel exhausted.

## The Six Overlay Types

### 1. Security Validator Overlay
**Phase**: VALIDATION | **Purpose**: Threat detection and trust enforcement

**Features**:
- **Content Policy Validation**: Blocks secrets, credentials, prohibited patterns
- **Trust Level Verification**: Ensures user has permission for operation
- **Rate Limiting**: Enforces request limits per user (minute/hour windows)
- **Input Sanitization**: Detects SQL injection, XSS, malicious payloads
- **Threat Tracking**: Auto-blocks after 10+ threats in 1 hour

**Validation Rules**:
| Rule | What It Checks |
|------|----------------|
| ContentPolicyRule | Blocked patterns, exposed secrets |
| TrustRule | User trust vs. required trust |
| RateLimitRule | Request frequency limits |
| InputSanitizationRule | SQL injection, XSS, script tags |

**Output**: `ValidationResult` with threats, warnings, and rule outcomes

### 2. ML Intelligence Overlay
**Phase**: ANALYSIS | **Purpose**: Semantic understanding and classification

**Features**:
- **Embedding Generation**: 384-1536 dimensional vectors for semantic search
- **Content Classification**: technical, business, personal, educational, creative, governance
- **Entity Extraction**: Emails, URLs, dates, money, phone numbers, versions
- **Pattern Detection**: Questions, lists, code blocks, references
- **Sentiment Analysis**: -1.0 to +1.0 scale
- **Anomaly Scoring**: Flags unusual content (very short/long, extreme sentiment)
- **Keyword Extraction**: TF-based extraction filtering stopwords

**Output**: `AnalysisResult` with embeddings, classifications, entities, patterns, sentiment

### 3. Governance Overlay
**Phase**: CONSENSUS | **Purpose**: Democratic decision-making

**Features**:
- **Proposal Evaluation**: Validates against policies before voting
- **Vote Collection**: Trust-weighted votes (APPROVE, REJECT, ABSTAIN)
- **Consensus Calculation**: Configurable thresholds and quorum
- **Early Consensus**: Supermajority (80%+) can end voting early
- **Policy Enforcement**: Custom rules (trust thresholds, content requirements)
- **Ghost Council Integration**: AI advisory recommendations

**Configuration**:
```python
ConsensusConfig:
  - min_votes: 3
  - quorum_percentage: 10%
  - approval_threshold: 60%
  - rejection_threshold: 40%
  - voting_period_hours: 72
  - enable_trust_weighting: True
  - trust_weight_power: 1.5
```

### 4. Lineage Tracker Overlay
**Phase**: SETTLEMENT | **Purpose**: Isnad chain management

**Features**:
- **Ancestor/Descendant Tracking**: Maintains derivation relationships
- **Isnad Chain Computation**: Full transmission history with trust gradient
- **Circular Reference Detection**: Prevents cycles in lineage graph
- **Influence Scoring**: Measures capsule impact (trust-weighted, decay-based)
- **Anomaly Detection**: Flags excessive depth, rapid derivations, broken chains

**Anomaly Types**:
- Circular references
- Broken chains (missing parents)
- Trust spikes (sudden trust changes)
- Rapid derivation (>100/day from single capsule)

### 5. Capsule Analyzer Overlay
**Phase**: ANALYSIS | **Purpose**: Content insights and quality assessment

**Features**:
- **Content Analysis**: Word count, reading level (basic→expert)
- **Quality Scoring**: Completeness, clarity, structure, depth, relevance
- **Insight Extraction**: Main ideas, key facts, action items, questions
- **Type Suggestion**: Recommends optimal capsule type based on content
- **Similarity Detection**: Finds related capsules via topic overlap
- **Trend Analysis**: Tracks trending terms across capsules
- **Summarization**: Extractive summary (top sentences by importance)

### 6. Performance Optimizer Overlay
**Phase**: EXECUTION | **Purpose**: Caching and performance monitoring

**Features**:
- **Query Caching**: TTL-based cache with hit/miss tracking
- **Performance Monitoring**: Response times (avg, p95, p99), error rates
- **Optimization Recommendations**: Based on metrics analysis
- **LLM Parameter Selection**: Optimized temperature, max_tokens, top_p
- **Resource Hints**: Priority levels for request handling

**Recommendations Generated**:
- Low cache hit rate (<30%) → Increase TTL
- High response times (>1s avg) → Investigate slow endpoints
- High error rates (>5%) → Improve reliability

## Overlay Manager

The `OverlayManager` coordinates all overlay operations:

### Registration
```python
manager.register_class(MyOverlay)        # Register class
instance_id = await manager.create_instance("my_overlay")  # Instantiate
```

### Execution
```python
result = await manager.execute(OverlayExecutionRequest(
    overlay_name="security_validator",
    input_data={"content": "..."},
    event=capsule_created_event,
    user_id="user_123",
    trust_flame=75
))
```

### Event Routing
When events are published, the manager automatically routes to all subscribed overlays in parallel.

### Circuit Breaker Protection
Overlays that fail repeatedly are automatically disabled:
- 5 consecutive failures → Circuit opens
- 30 second recovery timeout
- Test calls allowed in half-open state
- 2 successes to close circuit

### Health Monitoring
```python
health = await manager.health_check_all()
unhealthy = await manager.get_unhealthy_overlays()
```

---

# 6. Governance: Ghost Council & Democratic Voting

Forge implements a sophisticated governance system combining AI-powered advisory with human democratic voting.

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

### Proposal Lifecycle

```
DRAFT → VOTING → PASSED/REJECTED → EXECUTED
```

1. **Draft**: Proposer creates and can edit/cancel
2. **Voting**: Submitted for community vote (1-30 day period)
3. **Outcome**: Determined by approval ratio vs. threshold
4. **Execution**: Passed proposals trigger their action

### Creating a Proposal

```python
POST /proposals
{
  "title": "Enable ML classification for all capsules",
  "description": "This proposal enables automatic ML-based classification...",
  "type": "SYSTEM",
  "voting_period_days": 7,
  "quorum_percent": 10,
  "pass_threshold": 50,
  "action": {"setting": "ml_classification", "value": true}
}
```

### Trust-Weighted Voting

Votes carry weight based on the voter's trust level:

```python
vote_weight = max(0.1, trust_flame / 100)

# Examples:
# trust_flame = 100 (CORE)    → weight = 1.0
# trust_flame = 80 (TRUSTED)  → weight = 0.8
# trust_flame = 60 (STANDARD) → weight = 0.6
# trust_flame = 40 (SANDBOX)  → weight = 0.4
# trust_flame = 0 (QUARANTINE)→ weight = 0.1 (floor)
```

### Consensus Calculation

```python
approval_ratio = weighted_for / (weighted_for + weighted_against)

# Pass conditions:
1. approval_ratio >= pass_threshold (e.g., 50%)
2. total_votes >= quorum (e.g., 10% of eligible voters)
3. voting_period has ended (or supermajority reached)
```

### Vote Delegation

Users can delegate their voting power:

```python
POST /delegations
{
  "delegate_to": "user_456",
  "proposal_types": ["POLICY", "SYSTEM"],
  "expires_at": "2025-01-01T00:00:00Z"
}
```

Delegation features:
- Circular delegation prevention (max depth: 10)
- Revocable at any time
- Type-specific delegation
- Expiration support

## Ghost Council: AI Advisory

The Ghost Council is a system of five AI personas that deliberate on governance proposals, providing transparent advisory recommendations.

### Council Members

| Member | Role | Weight | Focus |
|--------|------|--------|-------|
| **Sophia** | Ethics Guardian | 1.2x | Ethical implications, fairness, stakeholder impact |
| **Marcus** | Security Sentinel | 1.3x | Security vulnerabilities, threat assessment, risk mitigation |
| **Helena** | Governance Keeper | 1.1x | Democratic principles, procedural fairness, power concentration |
| **Kai** | Technical Architect | 1.0x | Technical feasibility, system architecture, implementation risks |
| **Aria** | Community Voice | 1.0x | Community impact, user experience, social dynamics |

### Deliberation Process

1. **Proposal Analysis**: Each member receives proposal with context (voting data, Constitutional AI review)
2. **Independent Analysis**: Members analyze using LLM with their persona
3. **Voting**: Each member votes APPROVE, REJECT, or ABSTAIN with reasoning
4. **Weight Calculation**: Individual votes weighted by `member.weight × confidence_score`
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

### Cost Optimization

Three deliberation profiles:
- **Quick**: 1 member (lowest cost)
- **Standard**: 3 members
- **Comprehensive**: 5 members (highest accuracy)

Caching: Identical proposals within 30 days reuse cached opinions.

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

## Serious Issues System

The Ghost Council also responds to system emergencies:

### Issue Categories
- SECURITY: Threat detection, attacks
- GOVERNANCE: Vetoes, emergency actions, constitution violations
- TRUST: Significant trust drops (>20 points)
- SYSTEM: Multiple errors, critical failures
- ETHICAL: Values conflicts
- DATA_INTEGRITY: Data corruption

### Severity Levels
- LOW, MEDIUM, HIGH, CRITICAL

For CRITICAL issues, the Ghost Council can block rejection unless unanimous.

---

# 7. Security: Authentication & Authorization

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

**Refresh Tokens** (7-day expiry): Used to obtain new access tokens without re-authentication.

### Token Security Features
- HS256 cryptographic signatures
- JTI-based blacklisting for revocation
- Trust flame validation (must be present and in range)
- Automatic cleanup of expired blacklist entries

### Login Flow

1. User submits credentials (username/email + password)
2. System checks account lockout status (5 failed attempts = 30-minute lockout)
3. Password verified with bcrypt (constant-time comparison)
4. Token pair generated (access + refresh)
5. Session established with httpOnly cookies
6. Audit log entry created

### Password Requirements

```
- Minimum 12 characters (PCI-DSS 4.0.1)
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character
- No common weak patterns
- 90-day expiration
- Cannot reuse last 4 passwords
```

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

Capabilities granted by trust level:

```python
STANDARD:
  - CAPSULE_READ, CAPSULE_WRITE
  - EVENT_SUBSCRIBE
  - DATABASE_READ

TRUSTED:
  - All STANDARD capabilities plus:
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

## Middleware Stack

Request processing passes through multiple security layers:

1. **Correlation ID**: Assigns tracking ID for distributed tracing
2. **Request Logging**: Logs method, path, duration (redacts sensitive params)
3. **Authentication**: Extracts and validates JWT
4. **Rate Limiting**: Enforces per-user limits (trust-weighted multiplier)
5. **Security Headers**: Adds CSP, X-Frame-Options, HSTS
6. **CSRF Protection**: Double-submit cookie pattern

### Rate Limiting

```python
Default Limits:
  - 60 requests/minute
  - 1000 requests/hour
  - 10 burst allowance

Auth Endpoints (Stricter):
  - 10 requests/minute
  - 50 requests/hour
  - No burst allowance
```

Trust-based multipliers:
- QUARANTINE: 0.1x (6 req/min)
- SANDBOX: 0.5x (30 req/min)
- STANDARD: 1.0x (60 req/min)
- TRUSTED: 2.0x (120 req/min)
- CORE: 10.0x + immune to limits

### Security Headers

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'none'
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

---

# 8. Immune System: Self-Healing & Resilience

Forge's immune system provides automatic failure detection, prevention, and recovery.

## Circuit Breakers

Circuit breakers prevent cascading failures by stopping requests to failing services.

### States

```
CLOSED (Normal) → OPEN (Tripped) → HALF_OPEN (Testing)
      ↑                                    │
      └────────────── Success ─────────────┘
```

### Configuration

```python
CircuitBreakerConfig:
  - failure_threshold: 5       # Failures to open circuit
  - recovery_timeout: 30s      # Time before half-open
  - call_timeout: 10s          # Max time per call
  - failure_rate_threshold: 0.5  # 50% failure rate opens circuit
  - half_open_max_calls: 3     # Test calls in half-open
  - success_threshold: 2       # Successes to close circuit
```

### Pre-configured Services

| Service | Failures | Recovery | Timeout |
|---------|----------|----------|---------|
| Neo4j | 3 | 30s | 10s |
| External ML | 5 | 60s | 30s |
| Overlays | 5 | 15s | 5s |
| Webhooks | 10 | 120s | - |

## Anomaly Detection

Multiple detection methods identify unusual patterns:

### Detection Types

| Type | Method | What It Detects |
|------|--------|-----------------|
| Statistical | Z-score, IQR | Values outside normal distribution |
| Behavioral | Per-user baselines | Deviations from user's own patterns |
| Temporal | Time-series | Sudden spikes or drops |
| Isolation | IsolationForest ML | Multi-dimensional outliers |
| Rate | Time-bucketed | Frequency anomalies |
| Composite | Multiple detectors | High-confidence anomalies |

### Severity Classification

```python
- CRITICAL: score > 0.9 (immediate action required)
- HIGH: score > 0.7 (investigate soon)
- MEDIUM: score > 0.5 (monitor closely)
- LOW: score > 0 (note for patterns)
```

### Pre-configured Detectors

- `pipeline_latency_ms`: Composite (Statistical + IsolationForest)
- `error_rate`: Rate-based (sensitive z-score: 2.5)
- `capsule_creation_rate`: Rate-based
- `trust_score_change`: Statistical
- `memory_usage_mb`: Statistical
- `user_activity`: Behavioral

## Health Monitoring

Hierarchical health checks provide system-wide visibility:

### Health Status

```python
HEALTHY    → Fully operational
DEGRADED   → Operational but impaired
UNHEALTHY  → Not operational
UNKNOWN    → Cannot determine
```

### Health Check Hierarchy

```
System Health (Composite)
├── Database Layer
│   └── Neo4j Health Check
├── Kernel Layer
│   ├── Overlay Health Check
│   └── Event System Health Check
└── Infrastructure Layer
    ├── Memory Usage Check (warning: 80%, critical: 95%)
    ├── Disk Usage Check (warning: 85%, critical: 95%)
    └── Circuit Breaker Health Check
```

### Background Monitoring

Continuous health checks run every 30 seconds with callbacks on status changes.

## Canary Deployments

Safe gradual rollouts for new overlay versions:

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

### Approval Gates

At 50% traffic, rollouts can pause for human approval before proceeding.

## Self-Healing Scenarios

### Database Connection Failure
1. Circuit breaker detects 3 consecutive failures
2. Circuit opens → blocks database calls
3. Health check fails → system marked DEGRADED
4. After 30 seconds: Circuit half-open → test calls
5. If tests succeed → Circuit closes → HEALTHY

### Overlay Canary Failure
1. Canary at 15% traffic
2. Latency increases: p99 goes 100ms → 2500ms
3. Health check fails (>2000ms threshold)
4. Auto-rollback → returns to stable version
5. Full traffic on old version

---

# 9. Compliance Framework

Forge includes a comprehensive compliance framework supporting 25+ regulatory frameworks with 400+ controls.

## Supported Frameworks

### Privacy Regulations
- **GDPR**: EU General Data Protection Regulation
- **CCPA/CPRA**: California Consumer Privacy Act
- **LGPD**: Brazil's General Data Protection Law
- **PIPL**: China Personal Information Protection Law
- **PDPA**: Singapore/Thailand Personal Data Protection
- Plus: APPI, POPIA, DPDP, LAW25, PIPEDA, VCDPA, CTDPA, UCPA

### Security Standards
- **SOC 2**: Trust Services Criteria (CC6, CC7, CC8, CC9)
- **ISO 27001**: Information Security Management
- **NIST CSF/800-53**: Security controls framework
- **CIS Controls**: Center for Internet Security
- **FedRAMP**: Federal cloud security
- **CSA CCM**: Cloud Controls Matrix

### Industry-Specific
- **HIPAA**: Healthcare (PHI protection)
- **PCI-DSS 4.0.1**: Payment cards
- **COPPA**: Children's data (June 2025 updates)
- **FERPA**: Educational records
- **GLBA**: Financial data
- **SOX/FINRA**: Financial reporting

### AI Governance
- **EU AI Act**: Risk-based AI regulation
- **Colorado AI Act**: State AI requirements
- **NYC Local Law 144**: Automated employment decisions
- **NIST AI RMF**: AI risk management framework
- **ISO 42001**: AI management system

### Accessibility
- **WCAG 2.2**: Web Content Accessibility Guidelines
- **EAA**: European Accessibility Act
- **EN 301 549**: EU accessibility standard
- **ADA Digital/Section 508**: US accessibility

## Privacy Compliance Services

### Data Subject Access Requests (DSAR)

Handles all data subject rights requests:

| Request Type | GDPR Article | Processing |
|--------------|--------------|------------|
| Access | 15 | Export all personal data |
| Rectification | 16 | Correct inaccurate data |
| Erasure | 17 | "Right to be forgotten" |
| Restriction | 18 | Limit processing |
| Portability | 20 | Machine-readable export |
| Objection | 21 | Opt-out of processing |
| Automated Decisions | 22 | Human review of AI decisions |

**Deadline Enforcement**:
- GDPR: 30 days
- CCPA: 45 days
- LGPD: 15 days (strictest)

### Consent Management

Granular consent tracking for:
- Essential operations
- Analytics
- Marketing
- Profiling
- Third-party sharing
- AI processing/training
- Research
- Health/Financial data
- Children's data

**Features**:
- IAB TCF 2.2 string encoding
- Global Privacy Control (GPC) support
- CCPA Do Not Sell/Share compliance
- Demonstrable consent proof export

## Security Compliance

### Access Control Service

**RBAC (Role-Based)**:
- Default roles: User, Data Steward, Compliance Officer, AI Reviewer, Administrator
- Resource types: Capsule, User, Overlay, Proposal, Audit Log, etc.
- Data classifications: Public, Internal, Confidential, Restricted, Sensitive, PHI, PCI

**ABAC (Attribute-Based)**:
- Subject attributes (department, clearance)
- Resource attributes (classification, data type)
- Environment attributes (time, IP, device trust)

### Session Security

```python
Session Controls:
  - Duration: 8 hours (4 hours for privileged)
  - Idle timeout: 15 minutes (PCI-DSS)
  - Concurrent sessions: 3 maximum
  - MFA: Required for privileged users
```

## AI Governance

### EU AI Act Risk Classification

| Risk Level | Examples | Requirements |
|------------|----------|--------------|
| Unacceptable | Social scoring, manipulation | Prohibited |
| High-Risk | Employment decisions, credit scoring | Conformity assessment, registration |
| GPAI Systemic | Large general-purpose AI | Special obligations |
| Limited | Chatbots, emotion recognition | Transparency |
| Minimal | Recommendations, search | None |

### AI System Registration

For high-risk systems:
- System name, version, provider
- Risk classification
- Intended purpose
- Model type and oversight measures
- Training data description
- EU database registration

### AI Decision Logging

Every AI decision logs:
- System ID and model version
- Decision outcome and confidence
- Reasoning chain and key factors
- Legal/significant effect flags
- Plain-language explanation
- Human review capability

### Bias Detection

Metrics tracked:
- Demographic parity
- Equalized odds
- Equal opportunity
- Predictive parity
- Calibration across protected groups

## Data Residency

### Regional Data Pods

| Region | Locations |
|--------|-----------|
| North America | us-east-1, us-west-2, ca-central-1 |
| Europe | eu-west-1, eu-central-1, eu-north-1 |
| Asia-Pacific | ap-southeast-1, ap-northeast-1, ap-south-1 |
| China | cn-north-1, cn-northwest-1 (isolated) |
| Other | sa-east-1, me-south-1, af-south-1 |

### Transfer Mechanisms

| Mechanism | Use Case |
|-----------|----------|
| Adequacy Decisions | Pre-approved countries |
| SCCs | Standard Contractual Clauses |
| BCRs | Binding Corporate Rules |
| CAC Assessment | China-specific |
| Derogations | Specific exceptions |
| Prohibited | Russia transfers |

### Localization Requirements

- **China (PIPL)**: Mandatory localization; CAC assessment for transfers
- **Russia (FZ-152)**: Mandatory localization; transfers PROHIBITED
- **Vietnam/Indonesia**: Mandatory localization

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

## Compliance Enforcement Points

1. **Request/Response**: Access control before sensitive operations
2. **Data Access**: Audit logging for all sensitive reads
3. **Consent**: Processing blocked without valid consent
4. **Cross-Border**: Data residency routing enforced
5. **Breach**: Automated deadline calculation and notification
6. **AI Decisions**: Logging mandatory, explainability required

---

# 10. Trust Hierarchy

Trust is Forge's mechanism for graduated access control. It affects what users can do, how their votes count, and what resources they can access.

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

## Trust Flame Score

The `trust_flame` is a numeric score (0-100) that:
- Determines trust level (e.g., 75 → TRUSTED)
- Weights governance votes
- Sets rate limit multipliers
- Controls capability access

### Score to Level Conversion

```python
def get_trust_level(trust_flame: int) -> TrustLevel:
    if trust_flame >= 100: return TrustLevel.CORE
    if trust_flame >= 80: return TrustLevel.TRUSTED
    if trust_flame >= 60: return TrustLevel.STANDARD
    if trust_flame >= 40: return TrustLevel.SANDBOX
    return TrustLevel.QUARANTINE
```

## Trust Adjustment

Administrators can adjust trust with full audit trail:

```python
POST /users/{user_id}/trust
{
  "new_trust_flame": 80,
  "reason": "Promoted to trusted contributor after 6 months"
}
```

All changes logged with:
- Actor (who made the change)
- Previous and new values
- Reason
- Timestamp

---

# 11. Data Flow: End-to-End Processing

This section traces how data flows through Forge from initial request to final response.

## Capsule Creation Flow

```
1. CLIENT REQUEST
   POST /api/v1/capsules
   Authorization: Bearer <access_token>
   {
     "title": "Authentication Best Practices",
     "content": "...",
     "type": "KNOWLEDGE",
     "tags": ["security", "auth"]
   }
         │
         ▼
2. MIDDLEWARE STACK
   ├─ Correlation ID assigned
   ├─ Request logged
   ├─ JWT validated → user_id, trust_flame extracted
   ├─ Rate limit checked (trust-weighted)
   └─ Security headers added
         │
         ▼
3. ROUTE HANDLER
   ├─ Dependency injection: AuthContext, require_trust(SANDBOX)
   └─ Request validated against CreateCapsuleRequest schema
         │
         ▼
4. PIPELINE EXECUTION
   │
   ├─ PHASE 1: INGESTION (3s timeout)
   │   ├─ Normalize content (trim, sanitize)
   │   ├─ Validate field sizes
   │   └─ Assign pipeline_id, correlation_id
   │
   ├─ PHASE 2: ANALYSIS (10s timeout, parallel)
   │   ├─ MLIntelligenceOverlay
   │   │   ├─ Generate embedding (1536-dim vector)
   │   │   ├─ Classify content → "technical"
   │   │   ├─ Extract entities (URLs, references)
   │   │   └─ Detect patterns (code blocks)
   │   │
   │   └─ CapsuleAnalyzerOverlay
   │       ├─ Calculate quality score
   │       ├─ Extract key insights
   │       └─ Suggest reading level
   │
   ├─ PHASE 3: VALIDATION (5s timeout)
   │   └─ SecurityValidatorOverlay
   │       ├─ Content policy check (no secrets)
   │       ├─ Trust verification (user >= SANDBOX)
   │       ├─ Rate limit check
   │       └─ Input sanitization (no XSS)
   │
   ├─ PHASE 4: CONSENSUS (skipped for routine creates)
   │
   ├─ PHASE 5: EXECUTION (10s timeout)
   │   ├─ Generate capsule_id: "cap_a1b2c3d4e5f6"
   │   ├─ Neo4j: CREATE (c:Capsule {...})
   │   └─ Store embedding in vector index
   │
   ├─ PHASE 6: PROPAGATION (5s timeout, parallel)
   │   ├─ Emit CAPSULE_CREATED event
   │   │   ├─ capsule_id, creator_id, type, title
   │   │   └─ Classification results
   │   │
   │   └─ Cascade initiated if ML detected insights
   │       └─ Other overlays may process
   │
   └─ PHASE 7: SETTLEMENT (3s timeout)
       └─ LineageTrackerOverlay
           ├─ Record in audit log (SHA-256 chained)
           ├─ If parent_id: Create DERIVED_FROM relationship
           └─ Update metrics
         │
         ▼
5. RESPONSE
   HTTP 201 Created
   {
     "id": "cap_a1b2c3d4e5f6",
     "title": "Authentication Best Practices",
     "content": "...",
     "type": "KNOWLEDGE",
     "version": "1.0.0",
     "owner_id": "user_123",
     "trust_level": "STANDARD",
     "tags": ["security", "auth"],
     "created_at": "2025-01-07T10:30:00Z",
     "view_count": 0,
     "fork_count": 0
   }
```

## Governance Proposal Flow

```
1. CREATE PROPOSAL
   POST /proposals
   └─ Validated, stored in DRAFT state
         │
         ▼
2. SUBMIT FOR VOTING
   POST /proposals/{id}/submit
   ├─ Transitions: DRAFT → VOTING
   ├─ Sets voting_starts_at, voting_ends_at
   └─ Emit GOVERNANCE_ACTION event
         │
         ▼
3. CONSTITUTIONAL AI REVIEW (automatic)
   ├─ Ethical score calculation
   ├─ Fairness assessment
   ├─ Safety analysis
   └─ Recommendation: approve/review/reject
         │
         ▼
4. GHOST COUNCIL DELIBERATION (optional)
   ├─ Sophia (Ethics): Analyzes fairness
   ├─ Marcus (Security): Checks risks
   ├─ Helena (Governance): Reviews procedure
   ├─ Kai (Technical): Evaluates feasibility
   ├─ Aria (Community): Considers impact
   │
   └─ Weighted consensus recommendation
         │
         ▼
5. COMMUNITY VOTING
   POST /proposals/{id}/vote
   {
     "choice": "APPROVE",
     "reason": "Good for security"
   }
   ├─ Vote weight = trust_flame / 100
   ├─ Recorded atomically (no double-voting)
   └─ Emit VOTE_CAST event
         │
         ▼
6. CONSENSUS CALCULATION
   ├─ Count weighted votes
   ├─ approval_ratio = for / (for + against)
   ├─ Check quorum met
   └─ Compare vs. pass_threshold
         │
         ▼
7. FINALIZATION
   POST /proposals/{id}/finalize
   ├─ PASSED: approval_ratio >= threshold
   └─ REJECTED: approval_ratio < threshold
         │
         ▼
8. EXECUTION (if PASSED)
   ├─ Execute action payload
   ├─ Mark as EXECUTED
   └─ Emit completion event
```

## Search Flow

```
1. CLIENT REQUEST
   POST /capsules/search
   {"query": "How do we handle authentication?", "limit": 10}
         │
         ▼
2. CACHE CHECK
   ├─ Hash query parameters
   └─ Return cached results if found (TTL: 10 min)
         │
         ▼
3. EMBEDDING GENERATION
   ├─ EmbeddingService.embed(query)
   └─ Returns 1536-dimensional vector
         │
         ▼
4. VECTOR SEARCH
   Neo4j query:
   CALL db.index.vector.queryNodes(
     'capsule_embeddings',
     10,  // limit
     $embedding
   )
   YIELD node AS capsule, score
   WHERE capsule.trust_level >= 'standard'
   RETURN capsule, score
   ORDER BY score DESC
         │
         ▼
5. RESULT ASSEMBLY
   ├─ Convert to CapsuleResponse objects
   ├─ Include similarity scores
   └─ Cache results
         │
         ▼
6. RESPONSE
   {
     "results": [...],
     "scores": [0.95, 0.87, 0.82, ...],
     "total": 10
   }
```

## Event Cascade Flow

```
1. TRIGGER EVENT
   CAPSULE_CREATED with classification: "security_relevant"
         │
         ▼
2. EVENT BUS ROUTING
   ├─ Check type index for subscribed overlays
   └─ Route to: SecurityValidator, Governance, Analyzer
         │
         ▼
3. CASCADE INITIATION
   publish_cascade(
     insight_type="security_relevant_content",
     insight_data={capsule_id, classification},
     initiated_by="ml_intelligence"
   )
         │
         ▼
4. CHAIN CREATED
   CascadeChain {
     cascade_id: "casc_xyz",
     initiated_by: "ml_intelligence",
     overlays_affected: ["ml_intelligence"],
     total_hops: 0
   }
         │
         ▼
5. HOP 1: SecurityValidator
   ├─ Receives CASCADE_INITIATED
   ├─ Validates no credentials exposed
   ├─ Emits "security_validated" insight
   └─ propagate_cascade() → hop_count = 1
         │
         ▼
6. HOP 2: GovernanceOverlay
   ├─ Receives CASCADE_PROPAGATED
   ├─ Checks if policy review needed
   └─ No new insight (chain continues but no emit)
         │
         ▼
7. HOP 3: CapsuleAnalyzer
   ├─ Receives CASCADE_PROPAGATED
   ├─ Extracts security-related insights
   ├─ Links to related capsules
   └─ No further propagation needed
         │
         ▼
8. CASCADE COMPLETE
   complete_cascade(cascade_id)
   ├─ Moves chain to completed
   ├─ Emits CASCADE_COMPLETE
   └─ Logs: 3 hops, 4 overlays, 2 insights
```

---

# Summary

Forge V3 is a sophisticated system for institutional knowledge management that combines:

1. **Capsules**: Versioned, traceable knowledge units with semantic search
2. **Seven-Phase Pipeline**: Structured processing ensuring security and governance
3. **Event System**: Asynchronous communication enabling the cascade effect
4. **Overlays**: Modular, capability-controlled processing extensions
5. **Ghost Council**: AI-assisted democratic governance
6. **Security**: Multi-layer authentication and authorization
7. **Immune System**: Self-healing through circuit breakers and anomaly detection
8. **Compliance**: 400+ controls across 25+ regulatory frameworks
9. **Trust Hierarchy**: Graduated access based on user reputation

Together, these components create a self-governing, resilient, and compliant platform for preserving and evolving organizational knowledge.
