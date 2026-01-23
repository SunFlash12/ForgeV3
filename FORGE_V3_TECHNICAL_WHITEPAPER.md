# FORGE V3 Technical Whitepaper

**The Institutional Memory Engine: Architecture, Implementation, and Technical Specifications**

**Version 1.0 | January 2026**

---

## Abstract

Forge V3 is a sophisticated cognitive architecture platform designed to solve the critical problem of **ephemeral wisdom** in AI systems. Unlike traditional AI systems that lose context and learned knowledge upon retraining or system upgrades, Forge establishes persistent, traceable, and governable institutional memory through a novel combination of graph-based knowledge storage, symbolic lineage tracking (Isnad), democratic AI governance (Ghost Council), and self-healing infrastructure.

This technical whitepaper provides a comprehensive analysis of Forge V3's architecture, covering its 7-phase processing pipeline, overlay system, security mechanisms, compliance framework, federation protocol, and blockchain integration capabilities. The platform consists of approximately 50,000+ lines of production-grade code across 93+ Python backend modules and a modern React 19 frontend, implementing 400+ compliance controls across 25+ regulatory jurisdictions.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Core Architecture](#2-core-architecture)
3. [The Capsule System](#3-the-capsule-system)
4. [Seven-Phase Pipeline](#4-seven-phase-pipeline)
5. [Overlay System](#5-overlay-system)
6. [Ghost Council Governance](#6-ghost-council-governance)
7. [Trust and Security Architecture](#7-trust-and-security-architecture)
8. [Database Layer](#8-database-layer)
9. [Immune System and Resilience](#9-immune-system-and-resilience)
10. [Federation Protocol](#10-federation-protocol)
11. [API Architecture](#11-api-architecture)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Compliance Framework](#13-compliance-framework)
14. [Virtuals Protocol Integration](#14-virtuals-protocol-integration)
15. [Deployment Architecture](#15-deployment-architecture)
16. [Performance Characteristics](#16-performance-characteristics)
17. [Conclusion](#17-conclusion)

---

## 1. Introduction

### 1.1 The Problem: Ephemeral Wisdom

Traditional AI systems suffer from a fundamental limitation: knowledge is transient. When large language models are retrained, when systems are upgraded, or when AI agents are replaced, accumulated wisdom is lost. This creates several critical challenges for enterprise adoption:

- **No Audit Trail**: AI decisions cannot be traced or explained over time
- **Lost Institutional Knowledge**: Organizational learning disappears with system changes
- **Compliance Risk**: Regulatory requirements (EU AI Act, GDPR, HIPAA) mandate explainability and traceability
- **Governance Gap**: No democratic oversight mechanisms for AI decision-making

### 1.2 The Solution: Institutional Memory Engine

Forge V3 addresses these challenges through a paradigm shift: treating knowledge as **persistent, versioned, and governable assets** rather than ephemeral context. The core innovation is the **Capsule** - an atomic unit of knowledge with:

- Complete version history
- Traceable lineage (Isnad)
- Trust-weighted access control
- Semantic embeddings for retrieval
- Cryptographic integrity verification

### 1.3 Design Principles

Forge V3 is built on five foundational principles:

1. **Persistence**: Knowledge survives model upgrades and system restarts
2. **Traceability**: Every piece of knowledge has complete provenance
3. **Governance**: Democratic processes with AI advisory oversight
4. **Security**: Defense-in-depth with trust-based access control
5. **Extensibility**: Modular overlay system for custom processing

---

## 2. Core Architecture

### 2.1 System Overview

Forge V3 employs a microservices architecture with three primary API services:

| Service | Port | Responsibility |
|---------|------|----------------|
| **Cascade API** | 8001 | Core engine: capsules, governance, overlays, system |
| **Compliance API** | 8002 | GDPR, DSAR, consent, breach notification, AI governance |
| **Virtuals API** | 8003 | Blockchain integration: tokenization, ACP, revenue |

### 2.2 Technology Stack

**Backend Layer:**
- **Language**: Python 3.12 with async/await throughout
- **Framework**: FastAPI with Uvicorn ASGI server
- **Database**: Neo4j 5.x (unified graph + vector + properties)
- **Cache**: Redis 7.x for sessions, rate limiting, and query caching
- **Validation**: Pydantic v2 for type-safe data models
- **Authentication**: PyJWT with bcrypt password hashing

**Frontend Layer:**
- **Framework**: React 19 with TypeScript 5.9
- **State Management**: Zustand 5.0 + TanStack React Query 5.90
- **Styling**: Tailwind CSS v4 with custom theming
- **Build**: Vite 7.3.1 for optimized production builds

**Infrastructure Layer:**
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Docker Compose (development), Kubernetes-ready
- **Observability**: Prometheus, Grafana, Jaeger distributed tracing
- **CI/CD**: GitHub Actions with security scanning

### 2.3 Directory Structure

```
forge-cascade-v2/
├── forge/                      # Backend Python package
│   ├── api/                   # FastAPI application layer
│   │   ├── app.py            # Application factory & lifespan
│   │   ├── middleware.py     # Auth, CORS, rate limiting
│   │   ├── routes/           # 12 route modules
│   │   └── websocket/        # Real-time event handlers
│   ├── database/             # Neo4j integration
│   ├── kernel/               # Core processing engine
│   │   ├── pipeline.py       # 7-phase pipeline
│   │   ├── event_system.py   # Pub/sub event bus
│   │   └── overlay_manager.py# Overlay lifecycle
│   ├── models/               # 14 Pydantic model modules
│   ├── repositories/         # 9 data access layer modules
│   ├── services/             # 14 business logic modules
│   ├── overlays/             # 10 processing overlays
│   ├── security/             # 12 security modules
│   ├── immune/               # Self-healing infrastructure
│   ├── federation/           # Multi-instance coordination
│   ├── resilience/           # Fault tolerance patterns
│   └── monitoring/           # Observability
├── frontend/                  # React 19 dashboard
├── docker/                    # Container configurations
└── scripts/                   # Setup and utility scripts
```

---

## 3. The Capsule System

### 3.1 Capsule Architecture

The **Capsule** is the atomic unit of knowledge in Forge. Each capsule is a self-contained, versioned container with rich metadata:

```python
class Capsule:
    id: UUID                    # Unique identifier
    type: CapsuleType           # INSIGHT, DECISION, LESSON, etc.
    title: str                  # Human-readable title
    content: str                # Knowledge content (1 byte - 1 MB)
    owner_id: UUID              # Creator reference
    trust_level: TrustLevel     # 5-tier access control
    version: str                # Semantic versioning
    parent_id: Optional[UUID]   # Lineage link (Isnad)
    tags: List[str]             # Categorization (max 50)
    metadata: Dict[str, Any]    # Extensible metadata
    embedding: List[float]      # 1536-dim semantic vector
    content_hash: str           # SHA-256 integrity hash
    signature: Optional[str]    # Ed25519 digital signature
    created_at: datetime
    updated_at: datetime
```

### 3.2 Capsule Types

Forge supports 11 distinct capsule types for semantic classification:

| Type | Description | Use Case |
|------|-------------|----------|
| `INSIGHT` | Discovered patterns or understanding | Analysis results |
| `DECISION` | Choices made with reasoning | Governance records |
| `LESSON` | Learned experiences | Post-mortems |
| `WARNING` | Risk or threat information | Security alerts |
| `PRINCIPLE` | Guiding rules or standards | Policy documentation |
| `MEMORY` | Historical context | Institutional knowledge |
| `KNOWLEDGE` | General information | Documentation |
| `CODE` | Executable or reference code | Technical artifacts |
| `CONFIG` | Configuration data | System settings |
| `TEMPLATE` | Reusable patterns | Boilerplate content |
| `DOCUMENT` | Structured documents | Reports, specifications |

### 3.3 Isnad: Symbolic Lineage

Inspired by Islamic hadith scholarship, **Isnad** provides complete chain of custody for knowledge. Every capsule can reference its parent, creating an immutable ancestry tree:

```
Root Capsule (Original Insight)
    └── DERIVED_FROM → Version 1.1 (Refinement)
        └── DERIVED_FROM → Child Capsule A (Application)
        └── DERIVED_FROM → Child Capsule B (Extension)
            └── DERIVED_FROM → Grandchild Capsule (Further Development)
```

**Key Properties:**
- **Symbolic Inheritance**: Derived capsules inherit trust context
- **Traversal**: Query all ancestors or descendants
- **Trust Propagation**: Trust scores flow through lineage
- **Influence Scoring**: Impact measured by descendant count

### 3.4 Content Integrity

Capsules implement cryptographic integrity verification:

1. **Content Hashing**: SHA-256 hash of content for tamper detection
2. **Digital Signatures**: Ed25519 signatures for authenticity (Phase 2)
3. **Merkle Trees**: Lineage chain integrity verification (Phase 3)

```python
def verify_integrity(capsule: Capsule) -> bool:
    computed_hash = hashlib.sha256(capsule.content.encode()).hexdigest()
    return computed_hash == capsule.content_hash
```

---

## 4. Seven-Phase Pipeline

### 4.1 Pipeline Architecture

Every operation in Forge flows through a structured 7-phase pipeline, optimized for parallel execution where possible:

```
INPUT → INGESTION → ANALYSIS → VALIDATION → CONSENSUS → EXECUTION → PROPAGATION → SETTLEMENT → OUTPUT
        ─────────────────────   ─────────────────────   ──────────────────────────
              PARALLEL (~300ms)      SEQUENTIAL (~1000ms)       ASYNC (~150ms)
```

**Total Latency: ~1.2 seconds** (optimized from 3.5s baseline)

### 4.2 Phase Details

#### Phase 1: INGESTION (Parallel)
- Input validation and normalization
- Schema verification
- Initial sanitization

#### Phase 2: ANALYSIS (Parallel)
- ML processing and pattern detection
- Embedding generation (1536-dimensional vectors)
- Content classification

#### Phase 3: VALIDATION (Parallel)
- Security checks and threat detection
- Trust level verification
- Capability authorization

#### Phase 4: CONSENSUS (Sequential)
- Governance approval workflows
- Quorum calculations
- Policy rule evaluation

#### Phase 5: EXECUTION (Sequential)
- LLM processing (bottleneck phase)
- Ghost Council deliberation
- Core operation execution

#### Phase 6: PROPAGATION (Async)
- Cascade effect triggering
- Event emission to subscribers
- Webhook notifications

#### Phase 7: SETTLEMENT (Async)
- Audit logging with correlation IDs
- State finalization
- Analytics recording

### 4.3 Pipeline Configuration

Each phase is independently configurable:

```python
@dataclass
class PhaseConfig:
    enabled: bool = True          # Can disable individual phases
    timeout_ms: int = 5000        # Phase timeout
    required: bool = False        # Failure handling
    parallel: bool = True         # Execution mode
    retry_count: int = 3          # Retry attempts
```

---

## 5. Overlay System

### 5.1 Overlay Architecture

**Overlays** are modular processing units that extend Forge's capabilities. Each overlay is a self-contained component with defined capabilities, resource limits, and lifecycle management.

```python
class BaseOverlay(ABC):
    id: str
    name: str
    trust_level: int              # Required trust to activate
    capabilities: Set[Capability] # Required permissions
    fuel_budget: int              # Resource limits

    @abstractmethod
    async def process(
        self,
        context: ExecutionContext,
        input_data: Dict[str, Any]
    ) -> OverlayResult:
        pass
```

### 5.2 Built-in Overlays

Forge ships with 7 pre-configured overlays:

| Overlay | Phase | Trust | Responsibility |
|---------|-------|-------|----------------|
| **SecurityValidator** | VALIDATION | 90 | Input validation, threat detection |
| **MLIntelligence** | ANALYSIS | 85 | Pattern recognition, embeddings |
| **GovernanceOverlay** | CONSENSUS | 85 | Proposal evaluation, policy enforcement |
| **LineageTracker** | VALIDATION | 85 | Isnad tracking and verification |
| **GraphAlgorithms** | PROCESSING | 80 | PageRank, centrality, communities |
| **KnowledgeQuery** | PROCESSING | 80 | Natural language retrieval |
| **TemporalTracker** | PROCESSING | 80 | Version history, temporal analysis |

### 5.3 Capability System

Overlays request specific capabilities to access resources:

```python
class Capability(Enum):
    NETWORK_ACCESS = "network_access"
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"
    EVENT_PUBLISH = "event_publish"
    EVENT_SUBSCRIBE = "event_subscribe"
    CAPSULE_CREATE = "capsule_create"
    CAPSULE_MODIFY = "capsule_modify"
    CAPSULE_DELETE = "capsule_delete"
    GOVERNANCE_VOTE = "governance_vote"
    GOVERNANCE_PROPOSE = "governance_propose"
    USER_READ = "user_read"
    SYSTEM_CONFIG = "system_config"
    LLM_ACCESS = "llm_access"
```

### 5.4 Fuel Budget System

WebAssembly isolation provides resource metering:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_fuel` | 5,000,000 | CPU cycles |
| `max_memory_bytes` | 10 MB | Memory limit |
| `timeout_ms` | 5,000 | Execution timeout |

**Operation Costs:**
- Simple operation: 100 cycles
- Database read: 10,000 cycles
- Network request: 50,000 cycles
- LLM call: 500,000+ cycles

---

## 6. Ghost Council Governance

### 6.1 Architecture Overview

The **Ghost Council** is an AI-powered governance mechanism providing ethical oversight and decision recommendations. It implements Constitutional AI principles for transparent, explainable governance.

### 6.2 Council Members

| Member | Role | Weight | Focus |
|--------|------|--------|-------|
| **Sophia** | Ethics Guardian | 1.2x | Fairness, harm prevention |
| **Marcus** | Security Sentinel | 1.3x | Threats, vulnerabilities |
| **Helena** | Governance Keeper | 1.1x | Democracy, procedure |
| **Kai** | Technical Architect | 1.0x | Feasibility, architecture |
| **Aria** | Community Voice | 1.0x | User experience, dynamics |

### 6.3 Deliberation Process

```
1. Proposal Submission
    ↓
2. Constitutional AI Review
    ├── Ethical Assessment
    ├── Fairness Analysis
    ├── Safety Evaluation
    └── Transparency Check
    ↓
3. Independent Member Analysis (LLM)
    ↓
4. Weighted Voting
    ├── vote_power = member.weight × confidence_score
    ↓
5. Consensus Calculation
    ↓
6. Recommendation with Dissenting Opinions
```

### 6.4 Constitutional Principles

The Ghost Council evaluates proposals against 8 core principles:

1. **Knowledge Preservation**: Changes should enhance knowledge transmission
2. **Transparency**: All decisions must be traceable and explainable
3. **Fairness**: No unfair disadvantage without strong justification
4. **Safety**: No security vulnerabilities or reduced resilience
5. **Democratic Governance**: Humans retain ultimate decision authority
6. **Trust Hierarchy**: Trust levels reflect actual reliability
7. **Lineage Integrity**: Isnad chains must remain intact
8. **Ethical AI**: AI provides analysis, not binding judgments

### 6.5 Cost Profiles

| Profile | Members | LLM Calls | Use Case |
|---------|---------|-----------|----------|
| `quick` | Sophia only | 1 | Low-stakes decisions |
| `standard` | Sophia, Marcus, Helena | 3 | Normal governance |
| `comprehensive` | All 5 members | 5 | Critical decisions |

---

## 7. Trust and Security Architecture

### 7.1 Trust Hierarchy

Forge implements a 5-tier trust model with progressive access:

| Level | Score | Capabilities | Rate Limit |
|-------|-------|--------------|------------|
| **QUARANTINE** | 0-40 | Read public only | 0.1x (6/min) |
| **SANDBOX** | 40-60 | Create capsules (limited) | 0.5x (30/min) |
| **STANDARD** | 60-80 | Full basic ops, voting | 1.0x (60/min) |
| **TRUSTED** | 80-100 | Create proposals, priority | 2.0x (120/min) |
| **CORE** | 100 | Full access, no limits | Unlimited |

### 7.2 Authentication System

**Token Management:**
- **Access Token**: JWT with 30-60 minute expiry
- **Refresh Token**: HttpOnly cookie with 7-30 day expiry
- **Token Blacklist**: Redis-backed distributed revocation

**Security Features:**
- CSRF protection via double-submit cookie pattern
- Account lockout: 5 failed attempts → 15-minute lockout
- IP-based rate limiting for credential stuffing prevention
- MFA support (TOTP + backup codes)

### 7.3 Password Security

Implemented according to PCI-DSS 4.0.1 and NIST 800-63B:

```python
class PasswordPolicy:
    min_length: int = 12
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    bcrypt_rounds: int = 12
```

**Additional Protections:**
- 200+ common password blacklist
- Banned substrings: "admin", "password", "root", "test"
- Context-aware validation (no username/email in password)
- Unicode NFKC normalization before hashing

### 7.4 Security Audit Trail

Four major security audits have been completed with all critical findings addressed:

| Audit | Focus | Key Fixes |
|-------|-------|-----------|
| Audit 2 | Token & Validation | PyJWT migration, async locks, algorithm hardening |
| Audit 3 | Passwords & Permissions | Password blacklist, explicit permissions, session management |
| Audit 4 | Multi-layered | IP rate limiting, MFA lockout, memory bounds, DNS pinning |

---

## 8. Database Layer

### 8.1 Neo4j Integration

Forge uses Neo4j 5.x as a unified data store combining:
- **Graph Database**: Relationships and traversals
- **Vector Index**: Semantic similarity search (1536 dimensions)
- **Property Store**: Document-style data

### 8.2 Schema Design

**Node Types:**
```cypher
(:Capsule {id, content, type, owner_id, trust_level, embedding, ...})
(:User {id, username, email, trust_flame, role, ...})
(:Overlay {id, name, state, trust_level, ...})
(:Proposal {id, title, status, votes_for, votes_against, ...})
(:Vote {id, choice, weight, rationale, ...})
(:AuditLog {id, action, entity_type, timestamp, correlation_id, ...})
(:Event {id, type, source, priority, payload, ...})
(:CascadeChain {id, status, created_at, ...})
```

**Relationship Types:**
```cypher
(Capsule)-[:PARENT_OF]->(Capsule)       // Isnad lineage
(Capsule)-[:LINKED_TO]->(Capsule)       // Semantic connections
(Capsule)-[:CREATED_BY]->(User)         // Ownership
(Capsule)-[:PROCESSED_BY]->(Overlay)    // Processing history
(User)-[:VOTED_ON]->(Proposal)          // Governance
(SemanticEdge)-[:CONNECTS]->(Capsule)   // Auto-detected relationships
```

### 8.3 Indexing Strategy

| Index Type | Count | Purpose |
|------------|-------|---------|
| Unique Constraints | 13 | Entity uniqueness |
| Range Indexes | 18 | Query optimization |
| Vector Index | 1 | Semantic similarity |

### 8.4 Repository Pattern

All data access flows through repository classes implementing:

```python
class BaseRepository(ABC):
    async def create(self, entity: T) -> T
    async def get_by_id(self, id: UUID) -> Optional[T]
    async def update(self, entity: T) -> T
    async def delete(self, id: UUID) -> bool
    async def list(self, pagination: Pagination) -> List[T]
```

**Security Features:**
- Cypher injection prevention via identifier validation
- Pattern: `^[a-zA-Z_][a-zA-Z0-9_]*$`
- Maximum identifier length: 128 characters

---

## 9. Immune System and Resilience

### 9.1 Self-Healing Architecture

Forge implements a biological-inspired **Immune System** for automatic failure detection and recovery:

```
DETECTION → ISOLATION → DIAGNOSIS → RECOVERY → LEARNING
```

### 9.2 Circuit Breaker Pattern

State machine for failure isolation:

```
CLOSED (normal)
    ↓ (5 failures OR 50% error rate)
OPEN (blocking requests)
    ↓ (30 seconds elapsed)
HALF_OPEN (testing)
    ↓ (2 successes)      ↓ (any failure)
CLOSED                   OPEN
```

**Configuration:**
```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    failure_rate_threshold: float = 0.5
    recovery_timeout: int = 30
    half_open_max_calls: int = 3
    success_threshold: int = 2
    window_size: int = 10
```

### 9.3 Anomaly Detection

Multi-method detection system:

| Method | Algorithm | Use Case |
|--------|-----------|----------|
| Statistical | Z-score + IQR | Numeric outliers |
| IsolationForest | Random partition trees | Multi-dimensional |
| Rate-based | Bucket Z-score | Event spikes |
| Behavioral | Per-user profiling | User anomalies |
| Composite | 2+ detectors agree | High confidence |

**Severity Mapping:**
| Score | Severity | Response |
|-------|----------|----------|
| > 0.9 | CRITICAL | Immediate alert |
| > 0.7 | HIGH | Escalation |
| > 0.5 | MEDIUM | Monitoring |
| else | LOW | Logging |

### 9.4 Canary Deployments

Gradual rollout with automatic rollback:

```
Old 100% → Old 95% / New 5%
         → Old 50% / New 50% (if metrics pass)
         → Old 0% / New 100% (if metrics pass)
         → Rollback to Old 100% (if failure)
```

**Thresholds:**
- Initial traffic: 5%
- Minimum requests: 100
- Max error rate: 1%
- Max latency ratio: 2.0x

### 9.5 Health Checks

4-tier hierarchical health monitoring:

| Level | Name | Check |
|-------|------|-------|
| L1 | Connectivity | Can connect to service |
| L2 | Schema | Database schema ready |
| L3 | Operations | Can read/write |
| L4 | Performance | Within SLA latency |

---

## 10. Federation Protocol

### 10.1 Overview

Federation enables knowledge sharing between Forge instances with cryptographic security and trust-based access control.

### 10.2 Trust Scoring Model

Dynamic trust calculation for federated peers:

| Event | Trust Delta |
|-------|-------------|
| Successful sync | +0.02 |
| Failed sync | -0.05 |
| Unresolved conflict | -0.01 |
| Manual accept | +0.03 |
| Manual reject | -0.08 |
| Inactivity (per week) | -0.01 |

**Trust Tiers:**
| Tier | Score | Permissions |
|------|-------|-------------|
| QUARANTINE | 0.0-0.2 | No sync |
| LIMITED | 0.2-0.4 | Pull only, manual review |
| STANDARD | 0.4-0.6 | Bidirectional |
| TRUSTED | 0.6-0.8 | Priority sync, 2x rate |
| CORE | 0.8-1.0 | Auto-accept, 5x rate |

### 10.3 Security Hardening

| Protection | Implementation |
|------------|----------------|
| SSRF Prevention | Private IP blocking, URL validation |
| DNS Pinning | 5-minute TTL for resolved IPs |
| TLS Pinning | SHA-256 certificate fingerprints |
| Replay Prevention | Unique nonces per request |
| Redirect Blocking | Disabled redirect following |

### 10.4 Sync Protocol

```
PHASE 1: INIT
    ↓ Establish connection, verify trust
PHASE 2: FETCHING
    ↓ Retrieve delta changes
PHASE 3: PROCESSING
    ↓ Validate incoming data
PHASE 4: APPLYING
    ↓ Merge with conflict resolution
PHASE 5: FINALIZING
    ↓ Commit changes, update trust
```

**Conflict Resolution Strategies:**
- `HIGHER_TRUST`: Prefer higher-trust source
- `NEWER_TIMESTAMP`: Prefer most recent
- `MANUAL_REVIEW`: Queue for human review
- `MERGE`: Attempt automatic merge
- `LOCAL_WINS`: Prefer local version
- `REMOTE_WINS`: Prefer remote version

---

## 11. API Architecture

### 11.1 Endpoint Summary

Forge exposes 25+ REST endpoints across 12 route modules:

| Route Module | Endpoints | Authentication |
|--------------|-----------|----------------|
| `/auth` | 8 | Public/Authenticated |
| `/capsules` | 12 | Authenticated |
| `/governance` | 6 | Authenticated + Trust |
| `/overlays` | 9 | Admin |
| `/graph` | 10 | Authenticated |
| `/federation` | 7 | Admin |
| `/marketplace` | 10 | Authenticated |
| `/agent-gateway` | 6 | API Key |
| `/notifications` | 5 | Authenticated |
| `/system` | 8 | Admin |
| `/cascade` | 5 | Authenticated |
| `/users` | 5 | Admin |

### 11.2 WebSocket Endpoints

Real-time communication via WebSocket:

| Endpoint | Purpose | Events |
|----------|---------|--------|
| `/ws/events` | Event stream | CAPSULE_*, PROPOSAL_*, OVERLAY_*, SYSTEM_* |
| `/ws/chat` | Discussion rooms | Message, mention, typing |
| `/ws/dashboard` | Live metrics | Health, anomalies, performance |

### 11.3 Middleware Stack

Request processing order (outermost first):

1. **SecurityHeadersMiddleware**: HSTS, CSP, X-Frame-Options
2. **RequestTimeoutMiddleware**: 30s standard, 120s extended
3. **CorrelationIdMiddleware**: Request tracing
4. **RequestLoggingMiddleware**: Structured logging
5. **ObservabilityMiddleware**: Metrics collection
6. **RequestSizeLimitMiddleware**: 10MB max
7. **APILimitsMiddleware**: JSON depth, query params
8. **CSRFProtectionMiddleware**: Double-submit cookie
9. **AuthenticationMiddleware**: JWT validation
10. **RateLimitMiddleware**: Redis-backed throttling

### 11.4 Response Patterns

Standardized response models:

```python
# Success Response
{
    "success": true,
    "message": "Operation completed",
    "data": {...}
}

# Error Response
{
    "error": "ErrorType",
    "message": "Human-readable description",
    "details": {...},
    "correlation_id": "uuid"
}

# Paginated Response
{
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_more": true
}
```

---

## 12. Frontend Architecture

### 12.1 Technology Stack

- **Framework**: React 19.2.0 with TypeScript 5.9
- **State**: Zustand 5.0.10 (auth) + TanStack Query 5.90 (server state)
- **Styling**: Tailwind CSS 4.1.18 with custom theme
- **Routing**: React Router 7.12.0
- **Visualization**: Recharts 3.6.0, React Force Graph 2D

### 12.2 Page Structure

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Metrics, activity, health |
| Capsules | `/capsules` | Knowledge management |
| Governance | `/governance` | Proposals and voting |
| Ghost Council | `/ghost-council` | AI advisor interface |
| Graph Explorer | `/graph` | Knowledge visualization |
| Overlays | `/overlays` | Module management |
| Federation | `/federation` | Peer management |
| System | `/system` | Infrastructure monitoring |
| Settings | `/settings` | User preferences |

### 12.3 Security Implementation

**CSRF Protection:**
- X-CSRF-Token header on state-changing requests
- Token stored in memory (not localStorage)
- 403 error detection with automatic refresh

**Authentication:**
- HttpOnly cookie-based tokens
- Automatic token refresh on 401
- Session validation on app load

---

## 13. Compliance Framework

### 13.1 Regulatory Coverage

Forge implements 400+ technical controls across 25+ jurisdictions:

**Privacy Regulations:**
| Regulation | Jurisdiction | DSAR Deadline |
|------------|--------------|---------------|
| GDPR | EU/EEA | 30 days |
| CCPA/CPRA | California | 45 days |
| LGPD | Brazil | 15 days |
| PIPL | China | Localization required |
| PDPA | Singapore/Thailand | Consent-based |

**Security Standards:**
| Standard | Focus | Controls |
|----------|-------|----------|
| SOC 2 Type II | Trust services | CC6.1-CC9.2 |
| ISO 27001:2022 | Information security | A.5-A.8 |
| NIST 800-53 | Federal security | AC, AU, CA, IA, SC |
| PCI-DSS 4.0.1 | Payment cards | 12 requirements |

**AI Governance:**
| Regulation | Jurisdiction | Max Penalty |
|------------|--------------|-------------|
| EU AI Act | EU | 7% global revenue |
| Colorado AI Act | Colorado | Disclosure requirements |
| NYC Local Law 144 | NYC | Automated hiring |

### 13.2 DSAR Processing

Data Subject Access Request workflow:

```
Submission → Identity Verification → Data Collection → Review → Delivery
    ↓              ↓                      ↓             ↓          ↓
 Logging     Multi-method           Automated       Redaction   Export
             verification           gathering                   formats
```

**Export Formats:**
- JSON (structured, metadata-inclusive)
- CSV (tabular)
- JSON-LD (machine-readable)
- PDF (human-readable, accessible)

### 13.3 Breach Notification

72-hour GDPR breach notification workflow:

```
Detection → Assessment → Notification → Documentation → Remediation
              ↓
         Severity scoring:
         - Individuals affected
         - Sensitivity of data
         - Malicious intent
         - Containment status
```

### 13.4 AI Risk Classification (EU AI Act)

| Risk Level | Examples | Requirements |
|------------|----------|--------------|
| Prohibited | Social scoring, manipulation | Banned |
| High-Risk | Employment, credit, biometric | Conformity assessment |
| Limited | Chatbots, emotion recognition | Transparency obligations |
| Minimal | Recommendations, translation | None |

---

## 14. Virtuals Protocol Integration

### 14.1 Overview

Virtuals Protocol integration transforms Forge into a decentralized AI economy:

- **Overlays** → Autonomous revenue-generating agents
- **Capsules** → Monetized knowledge assets
- **Governance** → Token-weighted democratic control
- **Contributors** → Perpetual revenue earners

### 14.2 GAME SDK Integration

Agent functions exposed to the GAME SDK:

| Function | Purpose | Parameters |
|----------|---------|------------|
| `search_capsules` | Query knowledge | query, types, limit, trust |
| `get_capsule` | Retrieve content | capsule_id |
| `create_capsule` | Create knowledge | title, content, type, tags |
| `run_overlay` | Execute analysis | overlay_id, input, params |
| `cast_vote` | Governance | proposal_id, vote, reasoning |

### 14.3 Tokenization Model

**Bonding Curve:**
```
avg_price = 0.001 × (1 + current_supply / 10,000)
```
- Early contributors receive more tokens per VIRTUAL
- Creates incentive for early participation

**Graduation Thresholds:**
| Tier | Threshold | Use Case |
|------|-----------|----------|
| Genesis T1 | 21,000 VIRTUAL | Fast track |
| Standard | 42,000 VIRTUAL | Default |
| Genesis T3 | 100,000 VIRTUAL | Premium |

### 14.4 Revenue Distribution

```
Revenue Event (100%)
    ├── 30% → Creator wallet
    ├── 20% → Contributors (proportional shares)
    └── 50% → Treasury
              ├── 50% → Operations
              └── 50% → Buyback & Burn
```

### 14.5 Multi-Chain Support

| Chain | Type | Primary Use |
|-------|------|-------------|
| Base | EVM (L2) | Primary operations |
| Ethereum | EVM | Bridge operations |
| Solana | SPL | Alternative trading |

---

## 15. Deployment Architecture

### 15.1 Container Services

| Service | Image | Port | Resources |
|---------|-------|------|-----------|
| cascade-api | python:3.12 | 8001 | 2 CPU, 2GB RAM |
| compliance-api | python:3.12 | 8002 | 0.5 CPU, 512MB RAM |
| virtuals-api | python:3.12 | 8003 | 0.5 CPU, 512MB RAM |
| frontend | nginx:alpine | 80 | 0.25 CPU, 256MB RAM |
| redis | redis:7-alpine | 6379 | 0.5 CPU, 256MB RAM |

### 15.2 Production Architecture

```
                    ┌─────────────┐
                    │     CDN     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │Load Balancer│
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
    │  API Pod  │   │  API Pod  │   │  API Pod  │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
    │  Neo4j    │   │   Redis   │   │  Jaeger   │
    │  Cluster  │   │  Cluster  │   │  Tracing  │
    └───────────┘   └───────────┘   └───────────┘
```

### 15.3 Health Checks

All services implement health probes:

| Service | Endpoint | Interval | Retries |
|---------|----------|----------|---------|
| APIs | `/health` | 30s | 3 |
| Redis | `redis-cli ping` | 10s | 5 |
| Neo4j | HTTP 7474 | 30s | 5 |

---

## 16. Performance Characteristics

### 16.1 Latency Targets

| Metric | Target | Achieved |
|--------|--------|----------|
| P50 Latency | < 500ms | ~300ms |
| P99 Latency | < 2000ms | ~1200ms |
| Pipeline Total | < 1500ms | ~1200ms |

### 16.2 Throughput

| Configuration | Requests/Second |
|---------------|-----------------|
| Single Instance | 1,000+ |
| 3-Node Cluster | 3,000+ |
| Enterprise Scale | 5,000+ |

### 16.3 Optimization Strategies

1. **Parallel Phase Execution**: Phases 1-3 run concurrently
2. **Embedding Cache**: 50,000 entry cache (70-85% hit rate)
3. **Ghost Council Caching**: 30-day TTL for opinions
4. **Query Caching**: Redis-backed query result caching
5. **Connection Pooling**: Neo4j pool size of 50

---

## 17. Conclusion

Forge V3 represents a fundamental advancement in enterprise AI architecture. By treating knowledge as persistent, governable assets rather than ephemeral context, Forge solves the core challenge of institutional memory in AI systems.

**Key Technical Achievements:**

1. **Isnad System**: Complete knowledge lineage with cryptographic integrity
2. **7-Phase Pipeline**: Optimized processing with ~1.2s end-to-end latency
3. **Ghost Council**: Democratic AI governance with Constitutional AI principles
4. **Immune System**: Self-healing infrastructure with circuit breakers and anomaly detection
5. **Federation Protocol**: Secure multi-instance knowledge sharing
6. **Compliance Framework**: 400+ controls across 25+ jurisdictions
7. **Blockchain Integration**: Tokenization and revenue generation via Virtuals Protocol

**Production Readiness:**
- 50,000+ lines of code
- 93+ backend modules
- 4 completed security audits
- Comprehensive test coverage
- Docker/Kubernetes deployment ready

Forge V3 is positioned to become the standard for enterprise institutional memory, enabling organizations to preserve, govern, and monetize their collective AI-powered intelligence.

---

**Document Version**: 1.0
**Last Updated**: January 2026
**Classification**: Technical Documentation

---

*For implementation details, API documentation, and deployment guides, refer to the accompanying technical specifications in the Forge V3 repository.*
