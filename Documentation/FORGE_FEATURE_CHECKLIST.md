# Forge V3 - Comprehensive Feature Checklist

**Document Purpose:** Complete catalog of all Forge V3 features, their purposes, system interactions, and associated files.

**Last Updated:** 2026-01-06

---

## Table of Contents
1. [Core Architecture](#1-core-architecture)
2. [Capsules & Knowledge Engine](#2-capsules--knowledge-engine)
3. [Trust System](#3-trust-system)
4. [Ghost Council](#4-ghost-council)
5. [Governance System](#5-governance-system)
6. [Overlay Runtime](#6-overlay-runtime)
7. [Immune System](#7-immune-system)
8. [Security & Authentication](#8-security--authentication)
9. [Event System](#9-event-system)
10. [API Layer](#10-api-layer)
11. [User Interfaces](#11-user-interfaces)
12. [DevOps & Infrastructure](#12-devops--infrastructure)

---

## 1. Core Architecture

### 1.1 Configuration System
**What it is:** Centralized configuration management using Pydantic settings with environment variable support.

**Purpose:** Provides type-safe configuration across the entire application with validation, defaults, and environment-specific overrides.

**System Integration:**
- Loaded at application startup
- Accessed by all modules via `get_settings()` singleton
- Supports development, staging, and production environments

**Associated Files:**
- `forge/config.py` - Settings class and configuration loading
- `.env` - Environment variables (local development)
- `k8s/configmap.yaml` - Kubernetes ConfigMap for deployment

### 1.2 Base Models
**What it is:** Foundational Pydantic models and enums used throughout the application.

**Purpose:** Defines core domain types including TrustLevel enum, ForgeBaseModel with timestamps, and VoteDecision enum.

**System Integration:**
- Extended by all domain models (Capsule, User, Proposal, etc.)
- TrustLevel used in authorization decisions across the system
- VoteDecision used in governance voting

**Associated Files:**
- `forge/models/base.py` - Base model definitions
- `forge/models/__init__.py` - Model exports

### 1.3 Logging System
**What it is:** Structured logging using structlog with JSON output for production.

**Purpose:** Provides consistent, searchable log output with context propagation, correlation IDs, and performance metrics.

**System Integration:**
- Integrated with OpenTelemetry for distributed tracing
- Logs are indexed for ELK/CloudWatch analysis
- Request context automatically attached to all log entries

**Associated Files:**
- `forge/logging.py` - Logger configuration and setup
- `forge/api/middleware.py` - Request logging middleware

### 1.4 Exception Handling
**What it is:** Hierarchical exception system with domain-specific errors.

**Purpose:** Provides consistent error handling with proper HTTP status codes, error messages, and audit trail support.

**Key Exception Types:**
| Exception | HTTP Code | Use Case |
|-----------|-----------|----------|
| `NotFoundError` | 404 | Resource not found |
| `AuthenticationError` | 401 | Invalid credentials |
| `AuthorizationError` | 403 | Insufficient permissions |
| `ValidationError` | 422 | Invalid input data |
| `ConflictError` | 409 | Duplicate resource |
| `ServiceUnavailableError` | 503 | External service down |

**Associated Files:**
- `forge/exceptions.py` - Exception definitions
- `forge/api/middleware.py` - Global exception handler

---

## 2. Capsules & Knowledge Engine

### 2.1 Capsules (Core Knowledge Unit)
**What it is:** Atomic units of knowledge in Forge - the fundamental data structure storing content, embeddings, metadata, and lineage.

**Purpose:** Capsules are the "institutional memory" of Forge. They store knowledge with full provenance tracking, enabling semantic search and trust-based access control.

**Capsule Properties:**
| Property | Description |
|----------|-------------|
| `id` | UUID primary key |
| `content` | The actual knowledge text |
| `type` | Category: KNOWLEDGE, DECISION, POLICY, RITUAL, MEMORY |
| `trust_level` | Access control tier (QUARANTINE → CORE) |
| `embedding` | Vector representation for semantic search |
| `owner_id` | Creator's user ID |
| `parent_id` | Source capsule for lineage (Isnad) |
| `version` | Incremented on updates |
| `metadata` | Flexible JSON for extensions |

**System Integration:**
- Stored in Neo4j as nodes with relationships
- Embeddings stored for vector similarity search
- Lineage tracked via DERIVED_FROM relationships
- Events emitted on create/update/delete

**Associated Files:**
- `forge/models/capsule.py` - Capsule model definitions
- `forge/repositories/capsule_repository.py` - Database operations
- `forge/services/capsule_service.py` - Business logic
- `forge/api/routes/capsules.py` - REST endpoints

### 2.2 Lineage System (Isnad)
**What it is:** Provenance tracking inspired by Islamic hadith scholarship - every capsule knows its intellectual ancestry.

**Purpose:** Enables trust propagation, knowledge attribution, and understanding how ideas evolved over time.

**How It Works:**
1. When a capsule is derived from another, a DERIVED_FROM relationship is created
2. Lineage can be traversed to find original sources
3. Trust can propagate down lineage chains (derived capsules inherit parent's trust)
4. Attestations can be added by trusted users

**System Integration:**
- Neo4j graph relationships for efficient traversal
- Lineage queries support "find all descendants" and "find root"
- Displayed in UI as knowledge provenance

**Associated Files:**
- `forge/repositories/capsule_repository.py` - `get_lineage()`, `get_descendants()`
- `forge/services/capsule_service.py` - Lineage validation
- `forge/api/routes/capsules.py` - `/capsules/{id}/lineage` endpoint

### 2.3 Embedding Service
**What it is:** Service for generating vector embeddings from text content.

**Purpose:** Converts capsule content into vector representations for semantic similarity search.

**Supported Providers:**
| Provider | Model | Dimensions | Use Case |
|----------|-------|------------|----------|
| SentenceTransformers | all-MiniLM-L6-v2 | 384 | Local/cost-effective |
| OpenAI | text-embedding-3-small | 1536 | High quality |
| Mock | N/A | 384 | Testing |

**System Integration:**
- Called automatically when capsules are created/updated
- Embeddings stored in Neo4j for vector index search
- Configurable via settings (provider, model, dimensions)

**Associated Files:**
- `forge/services/embedding.py` - Embedding service implementation
- `forge/services/__init__.py` - Service initialization
- `forge/config.py` - Embedding configuration settings

### 2.4 Search Service
**What it is:** Semantic and hybrid search across capsules using vector similarity.

**Purpose:** Enables users to find relevant knowledge using natural language queries rather than exact keyword matching.

**Search Features:**
- **Semantic Search:** Vector similarity using embeddings
- **Hybrid Search:** Combines semantic with keyword matching
- **Filtered Search:** Restrict by trust level, type, owner
- **Configurable Threshold:** Minimum similarity score

**System Integration:**
- Uses embedding service to vectorize queries
- Queries Neo4j vector index
- Results filtered by user's trust level

**Associated Files:**
- `forge/services/search.py` - Search service implementation
- `forge/repositories/capsule_repository.py` - `search_by_embedding()`
- `forge/api/routes/capsules.py` - `/capsules/search` endpoint

---

## 3. Trust System

### 3.1 Trust Levels
**What it is:** 5-tier hierarchical trust system controlling access to knowledge and capabilities.

**Purpose:** Progressive trust allows the system to protect sensitive knowledge while enabling trusted users to access and contribute more.

**Trust Hierarchy:**
| Level | Weight | Description |
|-------|--------|-------------|
| `QUARANTINE` | 0 | Restricted - under review |
| `SANDBOX` | 1 | New users/overlays - limited access |
| `STANDARD` | 1 | Normal community members |
| `TRUSTED` | 3 | Established contributors |
| `CORE` | 5 | System maintainers/governance |

**Access Rules:**
- Users can only access capsules at or below their trust level
- Users can only invoke overlays at or below their trust level
- Vote weight is determined by trust level
- Certain proposal types require minimum trust level

**System Integration:**
- Stored on User and Capsule models
- Checked in authorization middleware
- Used in governance vote weighting
- Affects overlay execution permissions

**Associated Files:**
- `forge/models/base.py` - TrustLevel enum
- `forge/security/authorization.py` - Trust-based access control
- `forge/api/middleware.py` - Trust level validation

### 3.2 Trust Progression
**What it is:** Mechanisms for users and overlays to advance through trust levels.

**Purpose:** Allows community members to earn higher trust through positive contributions.

**Progression Methods:**
1. **Manual Promotion:** Admin/governance decision
2. **Governance Proposal:** Community vote to promote user
3. **Automatic:** Based on contribution metrics (future)

**Demotion Triggers:**
- Security violations
- Immune system alerts
- Governance decision
- Manual admin action

**Associated Files:**
- `forge/services/trust_service.py` - Trust management
- `forge/overlays/governance.py` - Trust change proposals
- `forge/api/routes/governance.py` - Trust endpoints

---

## 4. Ghost Council

### 4.1 Ghost Council Overview
**What it is:** Panel of 5 AI personas representing different perspectives that deliberate on proposals and serious issues.

**Purpose:** Provides structured, multi-perspective analysis for governance decisions, ensuring diverse viewpoints are considered.

**Council Members:**
| Persona | Role | Focus Area |
|---------|------|------------|
| **Sophia** | Philosopher | Ethics, long-term implications |
| **Marcus** | Guardian | Security, risk assessment |
| **Helena** | Archivist | Historical precedent, governance |
| **Kai** | Innovator | Innovation, technical feasibility |
| **Aria** | Advocate | Community impact, user rights |

### 4.2 Deliberation Process
**What it is:** Structured debate where each Ghost Council member provides their analysis.

**Purpose:** Generates comprehensive analysis covering all angles before governance decisions.

**Process Flow:**
1. Issue/proposal submitted to Ghost Council
2. Each member analyzes independently based on their role
3. Members provide structured opinions with reasoning
4. Final recommendation synthesized from all perspectives
5. Analysis attached to proposal for voter review

**System Integration:**
- Called automatically for new proposals
- Can be invoked for serious issues detected by immune system
- Analysis stored and displayed in governance UI

**Associated Files:**
- `forge/services/ghost_council.py` - Ghost Council service
- `forge/models/ghost_council.py` - Member definitions, deliberation models
- `forge/api/routes/governance.py` - Ghost Council endpoints
- `frontend/src/pages/GhostCouncilPage.tsx` - UI for viewing deliberations

### 4.3 Ghost Council Profiles
**What it is:** Configuration profiles controlling council size for cost optimization.

**Purpose:** Allows balancing between deliberation depth and API costs.

**Profiles:**
| Profile | Members | Use Case |
|---------|---------|----------|
| `quick` | 1 (Sophia) | Fast/cheap, simple decisions |
| `standard` | 3 (Sophia, Marcus, Aria) | Balanced, most decisions |
| `comprehensive` | 5 (all) | Complex/critical decisions |

**Associated Files:**
- `forge/services/ghost_council.py` - Profile configuration
- `forge/config.py` - `GHOST_COUNCIL_PROFILE` setting

### 4.4 Serious Issue Detection
**What it is:** Automatic detection of events that may require Ghost Council attention.

**Purpose:** Proactively identifies security threats, governance violations, or system anomalies.

**Detected Issue Types:**
- Security alerts and threats
- Trust level violations
- Immune system alerts
- Pipeline errors
- Governance anomalies

**System Integration:**
- Subscribes to event system for relevant event types
- Automatically triggers deliberation on serious issues
- Results can trigger automatic responses or escalation

**Associated Files:**
- `forge/services/__init__.py` - Event handler setup
- `forge/services/ghost_council.py` - `detect_serious_issue()`

---

## 5. Governance System

### 5.1 Proposals
**What it is:** Formal requests for system changes that go through community voting.

**Purpose:** Enables democratic decision-making for policy changes, overlay approvals, trust promotions, and system parameters.

**Proposal Types:**
| Type | Required Trust | Description |
|------|----------------|-------------|
| `POLICY` | TRUSTED | New policies or policy changes |
| `OVERLAY` | STANDARD | Overlay approval/revocation |
| `PARAMETER` | TRUSTED | System parameter changes |
| `TRUST` | TRUSTED | User trust level changes |
| `EMERGENCY` | CORE | Urgent security/stability actions |

**Proposal Lifecycle:**
```
DRAFT → ACTIVE → APPROVED/REJECTED → EXECUTED/FAILED
```

**Associated Files:**
- `forge/models/governance.py` - Proposal, Vote models
- `forge/repositories/governance_repository.py` - Database operations
- `forge/overlays/governance.py` - Governance overlay
- `forge/api/routes/governance.py` - REST endpoints

### 5.2 Voting System
**What it is:** Trust-weighted voting with quorum requirements.

**Purpose:** Allows community members to vote on proposals with influence proportional to their trust level.

**Voting Mechanics:**
- **Vote Options:** FOR, AGAINST, ABSTAIN
- **Weight Calculation:** Based on voter's trust level (see Trust Levels table)
- **Quorum:** Minimum participation required (default 30%)
- **Approval Threshold:** Minimum FOR percentage (default 50%)

**System Integration:**
- Votes recorded with weight at time of voting
- Vote tallies updated in real-time
- Automatic closure when voting period ends

**Associated Files:**
- `forge/models/governance.py` - Vote model, VoteDecision enum
- `forge/repositories/governance_repository.py` - Vote operations
- `forge/overlays/governance.py` - `cast_vote()`
- `forge/api/routes/governance.py` - `/proposals/{id}/vote`

### 5.3 Proposal Execution
**What it is:** Automatic execution of approved proposals.

**Purpose:** Implements the changes specified in approved proposals.

**Execution by Type:**
| Type | Execution Action |
|------|-----------------|
| POLICY | Store policy capsule |
| OVERLAY | Activate/deactivate overlay |
| PARAMETER | Update system configuration |
| TRUST | Update user trust level |
| EMERGENCY | Execute emergency action |

**Associated Files:**
- `forge/overlays/governance.py` - `execute_proposal()`
- `forge/services/scheduler.py` - Automatic closure/execution

---

## 6. Overlay Runtime

### 6.1 Overlay System Overview
**What it is:** Plugin/extension system allowing third-party code to extend Forge's capabilities.

**Purpose:** Enables community-contributed functionality while maintaining security through sandboxing.

**Key Concepts:**
- **Overlay:** A WASM module with defined capabilities
- **Manifest:** Describes overlay metadata, capabilities, entry points
- **Capability:** Permission to access specific Forge resources
- **Sandboxing:** Resource limits and isolation

### 6.2 WASM Runtime
**What it is:** WebAssembly execution environment using Wasmtime.

**Purpose:** Provides secure, sandboxed execution of overlay code with resource limits.

**Runtime Features:**
- **Fuel-based Execution:** Limits compute time
- **Memory Limits:** Configurable per trust level
- **Host Functions:** Controlled access to Forge services
- **Timeout Enforcement:** Maximum execution time

**Resource Limits by Trust:**
| Trust Level | Memory (MB) | Fuel | Timeout (ms) |
|-------------|-------------|------|--------------|
| SANDBOX | 32 | 10,000 | 1,000 |
| STANDARD | 64 | 100,000 | 5,000 |
| TRUSTED | 128 | 1,000,000 | 10,000 |
| CORE | 256 | 10,000,000 | 30,000 |

**Associated Files:**
- `forge/overlays/runtime.py` - WASM runtime implementation
- `forge/overlays/host_functions.py` - Host function definitions

### 6.3 Overlay Capabilities
**What it is:** Permission system controlling what overlays can access.

**Purpose:** Fine-grained access control for overlay security.

**Available Capabilities:**
| Capability | Description | Required Trust |
|------------|-------------|----------------|
| `capsule:read` | Read capsules | SANDBOX |
| `capsule:write` | Create capsules | STANDARD |
| `capsule:search` | Semantic search | SANDBOX |
| `user:read` | Read user profiles | STANDARD |
| `governance:read` | View proposals | SANDBOX |
| `governance:vote` | Cast votes | TRUSTED |
| `http:fetch` | External HTTP calls | TRUSTED |
| `system:config` | System configuration | CORE |

**Associated Files:**
- `forge/models/overlay.py` - OverlayCapability model
- `forge/overlays/service.py` - Capability validation
- `forge/overlays/host_functions.py` - Capability enforcement

### 6.4 Overlay Lifecycle
**What it is:** States an overlay transitions through from submission to active use.

**Lifecycle States:**
```
PENDING → ACTIVE ↔ SUSPENDED → DEPRECATED
    ↓                ↓
REJECTED         QUARANTINED
```

| State | Description |
|-------|-------------|
| PENDING | Awaiting approval |
| ACTIVE | Available for invocation |
| SUSPENDED | Temporarily disabled |
| QUARANTINED | Disabled due to issues |
| DEPRECATED | No longer recommended |
| REJECTED | Approval denied |

**Associated Files:**
- `forge/models/overlay.py` - OverlayState enum
- `forge/overlays/service.py` - State transitions
- `forge/overlays/repository.py` - State persistence

### 6.5 Built-in Overlays
**What it is:** System overlays providing core Forge functionality.

**Built-in Overlays:**
| Overlay | Purpose |
|---------|---------|
| `governance` | Proposal creation, voting, execution |
| `search` | Advanced search capabilities |
| `lineage` | Knowledge lineage analysis |
| `compliance` | Regulatory compliance checks |

**Associated Files:**
- `forge/overlays/governance.py` - Governance overlay
- `forge/overlays/search.py` - Search overlay

---

## 7. Immune System

### 7.1 Circuit Breakers
**What it is:** Automatic failure protection that stops calling failing services.

**Purpose:** Prevents cascade failures by isolating unhealthy components.

**States:**
| State | Behavior |
|-------|----------|
| CLOSED | Normal operation, tracking failures |
| OPEN | All calls fail immediately |
| HALF_OPEN | Testing if service recovered |

**Configuration:**
- `failure_threshold`: Failures before opening (default: 3)
- `success_threshold`: Successes to close (default: 2)
- `timeout_seconds`: Time before testing recovery (default: 30)

**Associated Files:**
- `forge/immune/circuit_breaker.py` - Circuit breaker implementation
- `forge/immune/__init__.py` - Immune system initialization
- `forge/config.py` - Circuit breaker settings

### 7.2 Canary Deployments
**What it is:** Gradual traffic shifting for safe overlay updates.

**Purpose:** Enables safe rollout of new overlay versions by testing with small traffic percentage first.

**Canary Process:**
1. Deploy new version alongside old
2. Route small % of traffic to new version
3. Monitor error rate and latency
4. Gradually increase traffic if healthy
5. Auto-rollback if issues detected

**Configuration:**
- `initial_traffic_percent`: Starting traffic % (default: 5%)
- `min_requests`: Minimum requests before evaluation (default: 100)
- `max_error_rate`: Error threshold for rollback (default: 1%)
- `max_latency_ratio`: Latency threshold (default: 2x)

**Associated Files:**
- `forge/immune/canary.py` - Canary deployment logic
- `forge/immune/__init__.py` - Canary initialization

### 7.3 Health Monitoring
**What it is:** Continuous health checks for system components and overlays.

**Purpose:** Detects degraded components before they cause user-facing issues.

**Health Metrics:**
- Component availability
- Response latency
- Error rates
- Resource utilization

**Associated Files:**
- `forge/immune/health.py` - Health check implementation
- `forge/api/routes/system.py` - `/health` endpoint

### 7.4 Anomaly Detection
**What it is:** Statistical analysis to detect unusual patterns.

**Purpose:** Identifies potential security threats or system issues through behavioral analysis.

**Detection Methods:**
- Request rate anomalies
- Error rate spikes
- Latency distribution changes
- Access pattern analysis

**Associated Files:**
- `forge/immune/anomaly.py` - Anomaly detection
- `forge/immune/__init__.py` - Integration with event system

### 7.5 Auto-Quarantine
**What it is:** Automatic isolation of misbehaving overlays or users.

**Purpose:** Protects system stability by automatically responding to threats.

**Quarantine Triggers:**
- Repeated failures (exceeds threshold)
- Security violations
- Resource abuse
- Anomalous behavior

**Quarantine Actions:**
- Overlay: State changed to QUARANTINED
- User: Trust level changed to QUARANTINE
- Alerts generated for admin review

**Associated Files:**
- `forge/immune/__init__.py` - Auto-quarantine logic
- `forge/overlays/service.py` - Overlay quarantine
- `forge/services/trust_service.py` - User quarantine

---

## 8. Security & Authentication

### 8.1 Authentication (JWT)
**What it is:** JSON Web Token based authentication with access and refresh tokens.

**Purpose:** Secure, stateless user authentication with token refresh capability.

**Token Types:**
| Type | Lifetime | Use |
|------|----------|-----|
| Access Token | 60 minutes | API authentication |
| Refresh Token | 7 days | Obtaining new access tokens |

**Token Claims:**
- `sub`: User ID
- `username`: Username
- `role`: User role
- `trust_flame`: Trust level numeric value
- `exp`: Expiration timestamp
- `jti`: Unique token ID (for revocation)

**Associated Files:**
- `forge/security/tokens.py` - Token generation/validation
- `forge/security/auth_service.py` - Authentication service
- `forge/api/routes/auth.py` - Auth endpoints

### 8.2 Password Security
**What it is:** Secure password hashing using Argon2id.

**Purpose:** Protects user passwords with state-of-the-art hashing.

**Password Requirements:**
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit

**Hashing Parameters:**
- Algorithm: Argon2id
- Memory: 65536 KB
- Iterations: 3
- Parallelism: 4

**Associated Files:**
- `forge/security/password.py` - Password hashing
- `forge/security/auth_service.py` - Password validation

### 8.3 Account Protection
**What it is:** Login attempt limiting and account lockout.

**Purpose:** Prevents brute-force password attacks.

**Protection Features:**
- Max 5 failed login attempts
- 15-minute lockout after threshold
- Lockout tracked per account
- Clear on successful login

**Associated Files:**
- `forge/security/auth_service.py` - Login attempt tracking
- `forge/repositories/user_repository.py` - Lockout persistence

### 8.4 Authorization (RBAC + ABAC)
**What it is:** Combined Role-Based and Attribute-Based Access Control.

**Purpose:** Fine-grained access control based on roles, trust levels, and resource ownership.

**Permission Categories:**
| Category | Examples |
|----------|----------|
| CAPSULE | CAPSULE_CREATE, CAPSULE_READ, CAPSULE_UPDATE, CAPSULE_DELETE |
| GOVERNANCE | GOVERNANCE_PROPOSE, GOVERNANCE_VOTE, GOVERNANCE_EXECUTE |
| OVERLAY | OVERLAY_REGISTER, OVERLAY_INVOKE, OVERLAY_MANAGE |
| ADMIN | ADMIN_USER_MANAGE, ADMIN_SYSTEM_CONFIG |

**Associated Files:**
- `forge/security/authorization.py` - Authorization service
- `forge/api/dependencies.py` - Auth dependency injection
- `forge/api/middleware.py` - Authorization middleware

### 8.5 GDPR Compliance
**What it is:** Data protection features for European privacy regulations.

**Purpose:** Ensures compliance with GDPR data subject rights.

**Supported Rights:**
| Right | Implementation |
|-------|----------------|
| Right to Access | Export all user data |
| Right to Erasure | Anonymize user records |
| Right to Portability | JSON/CSV data export |
| Right to Rectification | Update personal data |

**Response Deadline:** 30 days

**Associated Files:**
- `forge/security/gdpr.py` - GDPR service
- `forge/repositories/user_repository.py` - `anonymize()`, `list_by_owner()`
- `forge/api/routes/auth.py` - GDPR endpoints

### 8.6 Audit Logging
**What it is:** Comprehensive logging of security-relevant events.

**Purpose:** Maintains tamper-evident audit trail for compliance and forensics.

**Logged Events:**
- Authentication (login, logout, failed attempts)
- Authorization decisions
- Data access and modifications
- Administrative actions
- Security incidents

**Associated Files:**
- `forge/repositories/audit_repository.py` - Audit log storage
- `forge/security/audit.py` - Audit logging service

---

## 9. Event System

### 9.1 Event Bus
**What it is:** In-memory pub/sub event system for decoupled communication.

**Purpose:** Enables loosely-coupled components to react to system events.

**Event Categories:**
| Category | Events |
|----------|--------|
| Capsule | CAPSULE_CREATED, CAPSULE_UPDATED, CAPSULE_DELETED |
| User | USER_REGISTERED, USER_AUTHENTICATED, TRUST_UPDATED |
| Governance | PROPOSAL_CREATED, VOTE_CAST, PROPOSAL_EXECUTED |
| Security | SECURITY_ALERT, SECURITY_THREAT, ACCESS_DENIED |
| System | SYSTEM_ERROR, PIPELINE_ERROR, IMMUNE_ALERT |

**Associated Files:**
- `forge/kernel/event_system.py` - Event bus implementation
- `forge/models/events.py` - Event type definitions

### 9.2 Event Types
**What it is:** Strongly-typed event definitions with payloads.

**Event Structure:**
```python
class ForgeEvent:
    event_type: EventType
    payload: dict
    source: str
    timestamp: datetime
    correlation_id: str
```

**Associated Files:**
- `forge/models/events.py` - Event models

### 9.3 Kafka Integration (Production)
**What it is:** Apache Kafka for distributed event streaming in production.

**Purpose:** Provides durable, scalable event streaming for multi-instance deployments.

**Features:**
- Topic-per-event-type organization
- Partition key by resource ID
- Consumer groups for scaling
- Event replay capability

**Associated Files:**
- `forge/infrastructure/kafka/producer.py` - Event producer
- `forge/infrastructure/kafka/consumer.py` - Event consumer

---

## 10. API Layer

### 10.1 REST API
**What it is:** FastAPI-based REST API with OpenAPI documentation.

**Purpose:** Provides HTTP interface for all Forge operations.

**API Groups:**
| Group | Base Path | Description |
|-------|-----------|-------------|
| Auth | `/api/v1/auth` | Authentication & registration |
| Capsules | `/api/v1/capsules` | Knowledge management |
| Governance | `/api/v1/governance` | Proposals & voting |
| Overlays | `/api/v1/overlays` | Extension management |
| System | `/api/v1/system` | Health & metrics |

**Associated Files:**
- `forge/api/app.py` - FastAPI application
- `forge/api/routes/` - Route modules
- `forge/api/dependencies.py` - Dependency injection

### 10.2 Authentication Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Create new account |
| `/auth/login` | POST | Authenticate user |
| `/auth/refresh` | POST | Refresh access token |
| `/auth/logout` | POST | Invalidate tokens |
| `/auth/me` | GET | Get current user profile |

**Associated Files:**
- `forge/api/routes/auth.py`

### 10.3 Capsule Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/capsules` | GET | List capsules |
| `/capsules` | POST | Create capsule |
| `/capsules/{id}` | GET | Get capsule by ID |
| `/capsules/{id}` | PUT | Update capsule |
| `/capsules/{id}` | DELETE | Delete capsule |
| `/capsules/search` | POST | Semantic search |
| `/capsules/{id}/lineage` | GET | Get lineage chain |

**Associated Files:**
- `forge/api/routes/capsules.py`

### 10.4 Governance Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/proposals` | GET | List proposals |
| `/proposals` | POST | Create proposal |
| `/proposals/{id}` | GET | Get proposal |
| `/proposals/{id}/vote` | POST | Cast vote |
| `/proposals/{id}/activate` | POST | Activate proposal |
| `/ghost-council/deliberate` | POST | Request deliberation |

**Associated Files:**
- `forge/api/routes/governance.py`

### 10.5 Overlay Routes
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/overlays` | GET | List overlays |
| `/overlays` | POST | Register overlay |
| `/overlays/{id}` | GET | Get overlay |
| `/overlays/{id}/invoke` | POST | Invoke overlay |
| `/overlays/{id}/activate` | POST | Activate overlay |
| `/overlays/{id}/quarantine` | POST | Quarantine overlay |

**Associated Files:**
- `forge/api/routes/overlays.py`

### 10.6 Rate Limiting
**What it is:** Request rate limiting based on trust level.

**Purpose:** Prevents abuse while giving trusted users higher limits.

**Limits by Trust:**
| Trust Level | Requests/Minute |
|-------------|-----------------|
| QUARANTINE | 10 |
| SANDBOX | 30 |
| STANDARD | 100 |
| TRUSTED | 300 |
| CORE | 1000 |

**Associated Files:**
- `forge/api/middleware.py` - Rate limiting middleware

### 10.7 Response Envelope
**What it is:** Consistent API response structure.

**Standard Response:**
```json
{
  "data": {},
  "meta": {
    "request_id": "...",
    "timestamp": "...",
    "version": "1.0.0"
  }
}
```

**Error Response:**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "details": {}
  },
  "meta": {}
}
```

**Associated Files:**
- `forge/api/responses.py` - Response models

---

## 11. User Interfaces

### 11.1 CLI (Command Line Interface)
**What it is:** Terminal interface using Typer and Rich.

**Purpose:** Developer and power-user interface for Forge operations.

**Command Groups:**
| Group | Commands |
|-------|----------|
| `forge auth` | login, logout, register, whoami |
| `forge capsule` | list, get, create, search, lineage |
| `forge governance` | proposals, vote, propose |
| `forge overlay` | list, invoke, register |
| `forge admin` | users, metrics, config |

**Associated Files:**
- `forge/cli/main.py` - CLI entry point
- `forge/cli/commands/` - Command modules

### 11.2 Web Dashboard
**What it is:** React-based web interface with Shadcn/UI components.

**Purpose:** Visual interface for knowledge management and governance.

**Pages:**
| Page | Features |
|------|----------|
| Dashboard | Overview, recent activity, metrics |
| Knowledge | Capsule browser, search, lineage viewer |
| Governance | Proposal list, voting, Ghost Council |
| Overlays | Overlay marketplace, management |
| Settings | Profile, preferences, GDPR |

**Tech Stack:**
- React 19
- Tailwind CSS v4
- Shadcn/UI components
- React Query for data fetching
- React Router for navigation

**Associated Files:**
- `frontend/src/` - React application
- `frontend/src/pages/` - Page components
- `frontend/src/components/` - Reusable components

### 11.3 Mobile App
**What it is:** React Native mobile application (specified, not implemented).

**Purpose:** Mobile access to Forge for on-the-go knowledge capture.

**Planned Features:**
- Push notifications for votes
- Offline capsule drafts
- Voice-to-capsule capture
- QR code sharing

**Associated Files:**
- Specified in `PHASE_7_INTERFACES.md`

---

## 12. DevOps & Infrastructure

### 12.1 Database (Neo4j)
**What it is:** Graph database for storing capsules, users, and relationships.

**Purpose:** Optimized for connected data like lineage, governance, and social relationships.

**Key Indexes:**
- Capsule: id, owner_id, trust_level, embedding (vector)
- User: id, email, trust_level
- Proposal: id, status, type
- Overlay: id, name+version, state

**Associated Files:**
- `forge/database/client.py` - Neo4j client
- `forge/database/schema.py` - Schema initialization

### 12.2 Cache (Redis)
**What it is:** In-memory cache for sessions, rate limiting, and hot data.

**Purpose:** Reduces database load and improves response times.

**Cache Uses:**
- Session tokens
- Rate limit counters
- Ghost Council response cache
- Search result cache

**Associated Files:**
- `forge/infrastructure/redis/client.py` - Redis client

### 12.3 Object Storage (S3)
**What it is:** S3-compatible storage for WASM binaries and large files.

**Purpose:** Stores overlay WASM modules and large attachments.

**Features:**
- Multipart upload for large files
- Presigned URLs for direct access
- Streaming downloads
- Retry with exponential backoff

**Associated Files:**
- `forge/infrastructure/storage/client.py` - Storage client

### 12.4 Docker Configuration
**What it is:** Container configuration for deployment.

**Containers:**
- `api` - FastAPI application
- `neo4j` - Graph database
- `redis` - Cache layer
- `kafka` - Event streaming (production)

**Associated Files:**
- `Dockerfile` - Application container
- `docker-compose.yml` - Development stack

### 12.5 Kubernetes Deployment
**What it is:** Production deployment configuration.

**Resources:**
- Deployment with HPA (3-10 replicas)
- Service for internal networking
- Ingress with TLS
- ConfigMap and Secrets
- ServiceMonitor for metrics

**Associated Files:**
- `k8s/` - Kubernetes manifests

### 12.6 CI/CD Pipeline
**What it is:** GitHub Actions workflow for testing and deployment.

**Pipeline Stages:**
1. **Test** - Linting, type checking, unit tests
2. **Build** - Docker image build and push
3. **Deploy Staging** - Auto-deploy develop branch
4. **Deploy Production** - Auto-deploy main branch

**Associated Files:**
- `.github/workflows/ci.yml` - CI/CD workflow

### 12.7 Monitoring
**What it is:** Observability stack with metrics, logs, and traces.

**Components:**
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards and visualization
- **Jaeger** - Distributed tracing
- **ELK/CloudWatch** - Log aggregation

**Key Metrics:**
- Request rate and latency
- Error rates by endpoint
- Database query performance
- Overlay execution times

**Associated Files:**
- `k8s/monitoring/` - Monitoring configuration

---

## Quick Reference: File Structure

```
forge-cascade-v2/
├── forge/
│   ├── __init__.py
│   ├── config.py                    # Configuration
│   ├── exceptions.py                # Exception definitions
│   ├── logging.py                   # Structured logging
│   │
│   ├── models/                      # Domain models
│   │   ├── base.py                  # TrustLevel, BaseModel
│   │   ├── capsule.py               # Capsule models
│   │   ├── user.py                  # User models
│   │   ├── governance.py            # Proposal, Vote
│   │   ├── overlay.py               # Overlay models
│   │   └── events.py                # Event types
│   │
│   ├── repositories/                # Data access
│   │   ├── capsule_repository.py
│   │   ├── user_repository.py
│   │   ├── governance_repository.py
│   │   ├── overlay_repository.py
│   │   └── audit_repository.py
│   │
│   ├── services/                    # Business logic
│   │   ├── __init__.py              # Service initialization
│   │   ├── embedding.py             # Embedding service
│   │   ├── search.py                # Search service
│   │   ├── llm.py                   # LLM service
│   │   └── ghost_council.py         # Ghost Council
│   │
│   ├── security/                    # Security layer
│   │   ├── auth_service.py          # Authentication
│   │   ├── authorization.py         # Authorization
│   │   ├── tokens.py                # JWT handling
│   │   ├── password.py              # Password hashing
│   │   └── gdpr.py                  # GDPR compliance
│   │
│   ├── overlays/                    # Overlay system
│   │   ├── runtime.py               # WASM runtime
│   │   ├── service.py               # Overlay service
│   │   ├── repository.py            # Overlay storage
│   │   ├── governance.py            # Governance overlay
│   │   └── host_functions.py        # WASM host functions
│   │
│   ├── immune/                      # Immune system
│   │   ├── __init__.py              # Initialization
│   │   ├── circuit_breaker.py
│   │   ├── canary.py
│   │   ├── health.py
│   │   └── anomaly.py
│   │
│   ├── kernel/                      # Core runtime
│   │   ├── event_system.py          # Event bus
│   │   ├── pipeline.py              # 7-phase pipeline
│   │   └── overlay_manager.py       # Overlay lifecycle
│   │
│   ├── database/                    # Database layer
│   │   ├── client.py                # Neo4j client
│   │   └── schema.py                # Schema setup
│   │
│   ├── api/                         # REST API
│   │   ├── app.py                   # FastAPI app
│   │   ├── middleware.py            # Middleware
│   │   ├── dependencies.py          # DI
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── capsules.py
│   │       ├── governance.py
│   │       ├── overlays.py
│   │       └── system.py
│   │
│   └── cli/                         # CLI interface
│       ├── main.py
│       └── commands/
│
├── frontend/                        # Web dashboard
│   └── src/
│       ├── pages/
│       └── components/
│
├── k8s/                             # Kubernetes manifests
├── tests/                           # Test suite
├── scripts/                         # Utility scripts
│   ├── setup_db.py
│   └── seed_data.py
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env
```

---

## Summary

Forge V3 is a comprehensive **Institutional Memory Engine** with:

| Category | Components |
|----------|------------|
| **Knowledge** | Capsules, Lineage (Isnad), Semantic Search |
| **Trust** | 5-tier hierarchy, Progressive access |
| **Governance** | Proposals, Voting, Ghost Council |
| **Extensions** | WASM Overlays, Sandboxing, Capabilities |
| **Security** | JWT Auth, RBAC+ABAC, GDPR, Audit |
| **Resilience** | Circuit Breakers, Canary, Auto-Quarantine |
| **Infrastructure** | Neo4j, Redis, Kafka, Kubernetes |

**Total Estimated Implementation:** 30-40 days across 8 phases
