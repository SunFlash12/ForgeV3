# FORGE V3 - COMPREHENSIVE FILE-BY-FILE ANALYSIS
## Full Scan 2 - Detailed Per-File Documentation

**Generated:** 2026-01-09
**Scanned By:** Claude Opus 4.5
**Scan Type:** Individual file analysis with full requirement coverage

---

## DOCUMENTATION FORMAT

For each file, the following is documented:
1. **What it is** - File type, purpose, role
2. **What it does** - Functionality provided
3. **How it does it** - Technical implementation details
4. **Why it does it** - Design rationale and architectural decisions
5. **Part in codebase** - Integration points and dependencies
6. **Issues found** - Bugs, security issues, code smells
7. **Errors found** - Runtime errors, exceptions, failures
8. **Needs fixing** - Required fixes with priority
9. **Can be improved** - Enhancement opportunities
10. **New possibilities** - Features/capabilities this could enable

---

# SECTION 1: BACKEND CORE MODULES

## 1.1 API Module (`forge-cascade-v2/forge/api/`)

**Files:** 18 (~7,500 lines) | **Status:** COMPLETE

### File 1: `app.py` (607 lines)
- **What it is:** FastAPI application factory with all middleware, routes, exception handlers
- **What it does:** Creates ForgeApp with 11 API routers, middleware stack, lifespan management, health endpoints
- **How it does it:** Dependency injection via FastAPI Depends(), asyncio initialization, Redis for distributed state
- **Why it does it:** Separation of concerns, graceful degradation, production-ready monitoring
- **Part in codebase:** Entry point for all API operations, security gateway, lifecycle controller
- **Issues found:**
  - **HIGH**: Line 174 - Direct access to `_registry.instances` private attribute
  - **MEDIUM**: Conditional embedding provider setup may fail silently
  - **MEDIUM**: No error recovery if service initialization fails
- **Errors found:** None
- **Needs fixing:** Add error handling for service init failures (HIGH); Fix private attribute access (HIGH)
- **Can be improved:** Circuit breaker for external services, graceful degradation
- **New possibilities:** Plugin architecture for overlays, feature flags, multi-tenant support

### File 2: `middleware.py` (997 lines)
- **What it is:** 10+ middleware implementations for security, performance, observability
- **What it does:** CorrelationId, RequestLogging, Auth, RateLimit (token bucket), SecurityHeaders, CSRF, RequestSize, APILimits, Idempotency, RequestTimeout
- **How it does it:** BaseHTTPMiddleware extension, HMAC for security comparisons, Redis for distributed rate limiting
- **Why it does it:** Defense in depth, early rejection of invalid requests, comprehensive audit trail
- **Part in codebase:** First line of defense for all requests
- **Issues found:**
  - **HIGH**: CSRF token comparison bug - hmac.compare_digest fails if tokens None (line 640)
  - **HIGH**: Redis pipeline result indexing unsafe (line 415)
  - **MEDIUM**: Memory bucket cleanup only on minute window expiration
- **Errors found:** APILimitsMiddleware consumes body stream; CSRF comparison TypeError possible
- **Needs fixing:** Fix CSRF null check (CRITICAL); Validate Redis pipeline results (CRITICAL)
- **Can be improved:** Adaptive rate limiting, request signing support

### File 3: `dependencies.py` (613 lines)
- **What it is:** FastAPI dependency injection for auth, repositories, services, kernel
- **What it does:** Core deps, repository deps, kernel components, immune system, auth (JWT), authorization (trust/role/capability-based)
- **How it does it:** Annotated types with Depends(), lazy evaluation, composition
- **Why it does it:** Type safety, DRY principle, testability, centralized security
- **Part in codebase:** Glue layer connecting HTTP to business logic
- **Issues found:**
  - **HIGH**: TRUSTED_PROXY_RANGES hardcoded (line 447) - not configurable per deployment
  - **HIGH**: IP validation regex incomplete (line 479)
  - **MEDIUM**: get_current_user_optional swallows all exceptions
- **Needs fixing:** Make proxy ranges configurable (HIGH); Fix IP validation (HIGH)
- **Can be improved:** Cache user lookup, add auth failure metrics

### File 4: `routes/__init__.py` (24 lines)
- **What it is:** Module export file for routers
- **No issues found**

### File 5: `routes/auth.py` (872 lines)
- **What it is:** Authentication, registration, login, token management, MFA
- **What it does:** 13 public endpoints + 5 MFA endpoints, JWT with httpOnly cookies, CSRF token
- **How it does it:** Bcrypt hashing, TOTP for MFA, content validation via resilience layer
- **Why it does it:** Defense in depth, session security, password security
- **Issues found:**
  - **HIGH**: Content validation checks concatenated string (line 285) - should validate separately
  - **HIGH**: Password validation happens AFTER pipeline execution (line 289)
  - **MEDIUM**: Duplicate ValueError handler (line 447)
- **Needs fixing:** Move password validation before pipeline (HIGH); Validate fields separately (HIGH)

### File 6: `routes/users.py` (420 lines)
- **What it is:** User listing, admin operations, activity tracking
- **What it does:** 6 endpoints for user management
- **Issues found:**
  - **CRITICAL**: Wrong import paths - imports from `forge.security.dependencies` instead of `forge.api.dependencies` (lines 15-24)
  - **CRITICAL**: Module will fail to load at startup
- **Needs fixing:** Fix all import paths (CRITICAL)

### File 7: `routes/capsules.py` (1031 lines)
- **What it is:** Knowledge capsule CRUD, semantic search, lineage, forking
- **What it does:** Create, list, search, update, delete, lineage queries, semantic edge detection
- **Issues found:**
  - **HIGH**: Background task creates new DB client per task (line 76-140) - should use shared client
  - **MEDIUM**: Search filters not validated/whitelisted (line 393)
- **Needs fixing:** Use shared DB client (CRITICAL); Validate search filters (HIGH)

### File 8: `routes/cascade.py` (414 lines)
- **What it is:** Cascade effect triggers and monitoring
- **What it does:** Trigger, propagate, complete cascades; list/get cascade details
- **Issues found:**
  - **HIGH**: Cascade chains not persisted - lost on restart (line 294)
  - **MEDIUM**: Metrics calculated in-memory only
- **Needs fixing:** Add persistence for cascades (HIGH)

### File 9: `routes/federation.py` (~300 lines)
- **What it is:** Federation peer management and sync
- **Issues found:** Missing error handling for sync operations; no peer relationship persistence

### File 10: `routes/governance.py` (~300 lines)
- **What it is:** Proposal management and voting
- **Issues found:** No time limit enforcement on voting periods; missing quorum validation

### File 11: `routes/graph.py` (~300 lines)
- **What it is:** Knowledge graph queries
- **Issues found:**
  - **HIGH**: Direct Neo4j query execution without parameterization (Cypher injection risk)
  - **MEDIUM**: Hardcoded query limits (1000 nodes)

### File 12-17: Additional Routes (marketplace, notifications, overlays, system, agent_gateway)
- Various endpoints for respective features
- Common issues: In-memory state not persisted, missing input validation

### File 18: `websocket/handlers.py` (250+ lines)
- **What it is:** WebSocket connection management for events, dashboard, chat
- **What it does:** Topic-based pub/sub, room-based messaging, connection tracking
- **Issues found:**
  - **MEDIUM**: No subscription count limit per connection (DoS risk)
  - **MEDIUM**: No rate limiting on WebSocket messages

### API Module Summary Table
| Component | Status | Critical | High | Medium |
|-----------|--------|----------|------|--------|
| app.py | Good | 0 | 2 | 2 |
| middleware.py | Good | 2 | 1 | 2 |
| dependencies.py | Good | 0 | 2 | 1 |
| auth.py | Good | 0 | 2 | 1 |
| users.py | **BROKEN** | 2 | 0 | 0 |
| capsules.py | Good | 1 | 1 | 1 |
| Other routes | Good | 0 | 2 | 5 |

---

## 1.2 Database Module (`forge-cascade-v2/forge/database/`)

**Files:** 3 | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package initializer exposing Neo4jClient, get_db_client, SchemaManager
- **What it does:** Clean import interface for database package
- **How it does it:** Relative imports with `__all__` for explicit API
- **Why it does it:** Encapsulation, allows import from `forge.database` directly
- **Part in codebase:** Entry point for all DB access (API routes, services)
- **Issues found:** Missing docstring for `__all__` (LOW)
- **Errors found:** None
- **Needs fixing:** Add `__version__` for diagnostics (LOW)
- **Can be improved:** Add `close_db_client` export, inline docs
- **New possibilities:** High-level Database facade, DatabaseError hierarchy

### File 2: `schema.py` (608 lines)
- **What it is:** DDL operations for Neo4j schema management
- **What it does:** Creates 14 constraints, 30+ indexes, vector indexes; drops/verifies schema
- **How it does it:** Compiled regex validation, `IF NOT EXISTS` idempotency, `SHOW CONSTRAINTS/INDEXES` for verification
- **Why it does it:** Declarative schema for version control, production drop safety (Audit 2 fix)
- **Part in codebase:** App startup, migrations, tests
- **Issues found:** Generic exception catches (lines 181-184, 377-384) - MEDIUM; Hardcoded expected schema - MEDIUM
- **Errors found:** Silent failures on constraint/index creation
- **Needs fixing:** Atomic operations/rollback (HIGH); Generate expected schema from definitions (MEDIUM)
- **Can be improved:** Migration system, schema diff, dry run mode
- **New possibilities:** Auto-migration, schema versioning, full-text indexes

### File 3: `client.py` (333 lines)
- **What it is:** Async Neo4j driver wrapper with connection pooling
- **What it does:** Session/transaction management, retry logic, health checks, singleton pattern
- **How it does it:** `tenacity` for exponential backoff, double-checked locking (Audit 3 fix), context managers
- **Why it does it:** Async-first design, connection pooling, transient failure handling
- **Part in codebase:** All repository/service DB access
- **Issues found:** `tx.closed()` check logic (line 147) - MEDIUM; Race in singleton fast path - MEDIUM
- **Errors found:** Transaction exception swallowing possible
- **Needs fixing:** Fix transaction closed check (HIGH); Generic exception catching (MEDIUM)
- **Can be improved:** Query logging/timing, batch operations, result pagination
- **New possibilities:** Read/write splitting, circuit breaker, query caching

---

## 1.3 Federation Module (`forge-cascade-v2/forge/federation/`)

**Files:** 5 (~3,800 lines) | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package entry point with comprehensive exports
- **What it does:** Exports all models, FederationProtocol, SyncService, PeerTrustManager
- **How it does it:** Relative imports with `__all__` and docstring examples
- **Why it does it:** Single import point, encapsulation
- **Part in codebase:** Any code needing federation functionality
- **Issues found:** No import error handling (LOW)
- **Needs fixing:** Add `__version__` for protocol versioning (LOW)
- **New possibilities:** `setup()` function for one-line init

### File 2: `models.py`
- **What it is:** Pydantic data models for federation
- **What it does:** Defines FederatedPeer, FederatedCapsule, FederatedEdge, SyncState, PeerHandshake, SyncPayload, 6 enums
- **How it does it:** Pydantic BaseModel with validators, auto-generated IDs
- **Why it does it:** Strong typing prevents data corruption between peers
- **Part in codebase:** Foundation for all federation modules
- **Issues found:**
  - **HIGH**: Optional nonces weaken replay protection (lines 267, 301)
  - **MEDIUM**: Trust scale mismatch (0-100 vs 0.0-1.0)
  - URL not validated at model level
- **Needs fixing:** Make nonce required (HIGH); Normalize trust scale (MEDIUM)
- **New possibilities:** FederatedQuery for cross-instance search

### File 3: `sync.py` (849 lines)
- **What it is:** Sync orchestration service
- **What it does:** Peer registration, pull/push sync, conflict resolution, DB persistence
- **How it does it:** Async lock serialization, state machine, content hash verification (Audit 4 H7)
- **Why it does it:** Single lock prevents race conditions, iteration limit for DoS protection
- **Part in codebase:** Used by API endpoints, scheduled jobs
- **Issues found:**
  - **CRITICAL**: `peer.endpoint` should be `peer.url` (line 689)
  - **CRITICAL**: `peer.metadata` doesn't exist (line 699)
  - **CRITICAL**: Wrong field names in `load_peers_from_db()` (lines 731-743)
  - **HIGH**: Stub implementations for capsule/edge operations
- **Needs fixing:** Fix all attribute name mismatches (CRITICAL); Implement stubs (HIGH)
- **New possibilities:** Incremental sync, streaming WebSocket sync

### File 4: `trust.py` (670 lines)
- **What it is:** Peer trust management service
- **What it does:** Trust scoring (5 tiers), sync permissions, decay, revocation
- **How it does it:** Event sourcing, per-peer locks, bounded deque (Audit 4 M15)
- **Why it does it:** Gradual trust model, automatic penalties, use-it-or-lose-it decay
- **Part in codebase:** Called by SyncService after each sync
- **Issues found:**
  - **HIGH**: `peer.metadata` assignment fails (lines 421-426)
  - **HIGH**: Status changes not persisted to DB (lines 379-392)
  - **MEDIUM**: LRU eviction is actually FIFO (lines 103-106)
- **Needs fixing:** Add metadata to model or remove usage (HIGH); Persist status changes (HIGH)
- **New possibilities:** Web of trust, trust certificates, ML-based scoring

### File 5: `protocol.py` (1,447 lines)
- **What it is:** Secure network protocol with Ed25519 cryptography
- **What it does:** SSRF protection, DNS/TLS pinning, nonce-based replay prevention, key management
- **How it does it:** DNS resolution pinning (Audit 4 H3), TOFU cert pinning (Audit 4 H4), private key encryption (Audit 4 H8)
- **Why it does it:** Ed25519 faster than RSA, pinning prevents MitM/rebinding attacks
- **Part in codebase:** Used by SyncService for all network operations
- **Issues found:**
  - **CRITICAL**: SQL injection in DatabaseReadHostFunction (lines 282-289)
  - **HIGH**: Can't load encrypted keys (lines 868-872)
  - **MEDIUM**: Unix path hardcoded (line 763)
- **Needs fixing:** Use SQL parser for write detection (CRITICAL); Fix key loading (HIGH)
- **New possibilities:** Key rotation, hardware security module integration

---

## 1.4 Immune Module (`forge-cascade-v2/forge/immune/`)

**Files:** 5 (~3,500 lines) | **Status:** COMPLETE

### File 1: `__init__.py` (161 lines)
- **What it is:** Package entry point with factory function
- **What it does:** Exports all components; `create_immune_system()` factory
- **How it does it:** Relative imports, dict return for flexibility
- **Why it does it:** Single point of access, dependency injection for testing
- **Part in codebase:** Application bootstrap, tests
- **Issues found:** Dict return lacks type safety (LOW)
- **Needs fixing:** Create `ImmuneSystem` TypedDict (LOW)
- **New possibilities:** Hot-reload of immune policies

### File 2: `anomaly.py` (1,072 lines)
- **What it is:** ML-based anomaly detection
- **What it does:** Statistical (Z-score/IQR), IsolationForest, Rate, Behavioral detection
- **How it does it:** Pure Python IsolationForest (no sklearn), sliding windows, per-user profiles
- **Why it does it:** Statistical is interpretable, IF handles high-dimensional, composite reduces false positives
- **Part in codebase:** Pipeline metrics, user activity, system health monitoring
- **Issues found:**
  - **HIGH**: Z-score extreme with small std (line 236)
  - **MEDIUM**: IQR quartile imprecise (lines 245-246)
  - **MEDIUM**: Input dict mutation (line 867)
- **Errors found:** Division by near-zero std; population vs sample variance
- **Needs fixing:** Add minimum std threshold (HIGH); Use proper interpolation (MEDIUM)
- **New possibilities:** LSTM-based sequence detection, federated learning, anomaly clustering

### File 3: `canary.py` (746 lines)
- **What it is:** Canary deployment manager
- **What it does:** Gradual rollouts (LINEAR/EXPONENTIAL/MANUAL), automatic rollback, health monitoring
- **How it does it:** Weighted random routing, error rate comparison, approval gates
- **Why it does it:** Limit blast radius, reduce MTTR, baseline-aware detection
- **Part in codebase:** Overlay deployment, automation
- **Issues found:**
  - **HIGH**: Potential None access on `step_started_at` (line 591)
  - **MEDIUM**: Thread-unsafe counter (line 624)
  - **MEDIUM**: `total_requests` not incremented (lines 658-673)
- **Needs fixing:** Add None check (HIGH); Use asyncio.Lock (MEDIUM)
- **New possibilities:** Blue-green deployments, A/B/C testing, geographic rollouts

### File 4: `circuit_breaker.py` (671 lines)
- **What it is:** Circuit breaker pattern implementation
- **What it does:** CLOSED/OPEN/HALF_OPEN state machine, sliding window failures, registry
- **How it does it:** Time-based window, rate threshold, decorator pattern
- **Why it does it:** Fail fast, recovery testing, centralized monitoring
- **Part in codebase:** DB calls, ML services, webhooks, overlays
- **Issues found:**
  - **HIGH**: `force_open` permanently mutates config (lines 494-495)
  - **MEDIUM**: Timeout stats outside lock (line 451)
  - **MEDIUM**: Global registry race condition (line 595)
- **Needs fixing:** Store/restore original timeout (HIGH); Move stats inside lock (MEDIUM)
- **New possibilities:** Predictive opening, distributed state, automatic failover

### File 5: `health_checker.py` (777 lines)
- **What it is:** Hierarchical health monitoring
- **What it does:** Composite checks, Neo4j/Overlay/Event/Memory/Disk checks, background monitoring
- **How it does it:** Cache-first with TTL, concurrent child checks, worst-case aggregation
- **Why it does it:** Drill-down visibility, slow-is-problematic latency thresholds
- **Part in codebase:** K8s probes, dashboards, alerting
- **Issues found:**
  - **MEDIUM**: Hardcoded thresholds (lines 407-414)
  - **MEDIUM**: No interface contracts for dependencies
- **Needs fixing:** Move thresholds to config (MEDIUM); Define protocols (MEDIUM)
- **New possibilities:** Predictive health, self-healing triggers, health-based routing

---

## 1.5 Kernel Module (`forge-cascade-v2/forge/kernel/`)

**Files:** 5 (~1,650 lines) | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package initializer for kernel public API
- **What it does:** Exports EventBus, OverlayManager, Pipeline, lifecycle functions
- **How it does it:** Re-exports with `__all__`, backward compatibility aliases
- **Why it does it:** Hide internal structure, preserve API stability
- **Part in codebase:** Any code importing kernel functionality
- **Issues found:** Missing `wasm_runtime` exports (MEDIUM)
- **Needs fixing:** Add wasm exports if public API intended (MEDIUM)
- **New possibilities:** Unified `init_kernel()` / `shutdown_kernel()`

### File 2: `pipeline.py` (866 lines)
- **What it is:** 7-phase processing pipeline orchestrator
- **What it does:** INGESTION→ANALYSIS→VALIDATION→CONSENSUS→EXECUTION→PROPAGATION→SETTLEMENT
- **How it does it:** Phase iteration, parallel/sequential overlay execution, hooks system
- **Why it does it:** Separation of concerns, configurable phases, extensibility
- **Part in codebase:** API endpoints, event handlers, governance
- **Issues found:**
  - **HIGH**: `_emit_pipeline_event` uses wrong Event API (lines 761-782)
  - **MEDIUM**: Deprecated `asyncio.get_event_loop().time()` (multiple lines)
  - **MEDIUM**: Null check missing for overlay.state (line 598)
- **Needs fixing:** Fix Event publishing (HIGH); Update async API (MEDIUM)
- **New possibilities:** Phase branching, rollback, checkpoint/resume

### File 3: `wasm_runtime.py` (762 lines)
- **What it is:** WebAssembly-like security sandbox (Python scaffolding)
- **What it does:** Capability-based access (11 capabilities), fuel metering, host functions
- **How it does it:** Security modes (STRICT/RELAXED/TRUSTED), manifest validation
- **Why it does it:** Memory safety, isolation, resource control, instant termination
- **Part in codebase:** Overlay execution security layer
- **Issues found:**
  - **CRITICAL**: SQL injection in DatabaseReadHostFunction (lines 282-289)
  - **HIGH**: Async task in sync shutdown (lines 700-745)
  - **HIGH**: EventType validation missing try/except (line 323)
- **Needs fixing:** Use SQL parser (CRITICAL); Fix shutdown (HIGH)
- **New possibilities:** Real Wasm integration, hot reloading, GPU capabilities

### File 4: `event_system.py` (776 lines)
- **What it is:** Async pub/sub event bus
- **What it does:** Type-indexed subscriptions, cascade chain management, dead letter queue
- **How it does it:** AsyncQueue, worker pattern, exponential backoff retry
- **Why it does it:** Decoupling, async processing, cascade effect (core Forge feature)
- **Part in codebase:** Pipeline, overlay_manager, all overlays
- **Issues found:**
  - **HIGH**: Event constructor parameter mismatch (lines 219-228)
  - **MEDIUM**: Recursive retry can overflow (lines 576-577)
  - **MEDIUM**: Dead letter queue blocks without timeout (line 580)
- **Needs fixing:** Fix Event constructor (HIGH); Iterative retry (MEDIUM)
- **New possibilities:** Event persistence, distributed bus (Kafka), saga pattern

### File 5: `overlay_manager.py` (830 lines)
- **What it is:** Overlay lifecycle and execution manager
- **What it does:** Registration, activation, discovery (by name/event), circuit breaker, health monitoring
- **How it does it:** Multi-index registry, internal circuit breaker, execution history
- **Why it does it:** Centralized control, fault isolation, efficient discovery
- **Part in codebase:** Pipeline, API, initialization
- **Issues found:**
  - **HIGH**: Event creation mismatch with EventBus.publish (lines 516-522)
  - **HIGH**: `_circuit_lock` not initialized in `__init__` (missing)
  - **MEDIUM**: threading.Lock in async code (lines 626-684)
- **Needs fixing:** Fix Event creation (HIGH); Initialize lock (HIGH); Use asyncio.Lock (MEDIUM)
- **New possibilities:** Overlay marketplace, A/B testing, resource quotas

---

## 1.6 Models Module (`forge-cascade-v2/forge/models/`)

**Files:** 14 (~4,681 lines) | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Central export point for 27 model classes
- **Issues:** Missing exports for 7+ model files (marketplace, agent_gateway, notifications, etc.) - MEDIUM

### File 2: `base.py`
- **What it is:** Foundation - ForgeModel, TimestampMixin, TrustLevel IntEnum, enums, utilities
- **Issues:** Deprecated `datetime.utcnow()` (lines 56-57, 187) - LOW

### File 3: `capsule.py`
- **What it is:** Core Capsule entity - ContentBlock, lineage, search results, stats
- **How it does it:** Embedding validation (384/768/1024/1536/3072 dims), tag normalization
- **Issues:** List max_length doesn't work as expected (line 58-62) - MEDIUM

### File 4: `user.py`
- **What it is:** User entities with Capability/Role enums, Trust Flame scoring
- **Issues:**
  - **HIGH**: Password max_length=100 exceeds bcrypt 72-byte limit (line 146)
  - **MEDIUM**: Refresh token stored unhashed (line 197-199)

### File 5: `governance.py`
- **What it is:** Proposals, voting, Constitutional AI, Ghost Council
- **How it does it:** Action validation, timelock, trust-weighted voting, tri-perspective analysis
- **Issues:** VoteDelegation.id empty string default (line 364) - MEDIUM

### File 6: `overlay.py`
- **What it is:** 16 capability types, OverlayManifest, FuelBudget, state tracking
- **Why:** Least privilege, resource limits, health metrics

### File 7: `events.py`
- **What it is:** 60+ EventTypes, priorities, CascadeEvent with hop tracking, AuditEvent

### File 8: `semantic_edges.py`
- **What it is:** Bidirectional semantic relationships (RELATED_TO, CONTRADICTS, SUPPORTS, etc.)
- **Issues:** SUPPORTS inverse is incorrectly SUPPORTS (line 49) - MEDIUM

### File 9: `temporal.py`
- **What it is:** Version control - CapsuleVersion, TrustSnapshot, GraphSnapshot, hybrid versioning
- **Issues:** compress() mutates input (lines 278-288) - MEDIUM

### File 10: `query.py`
- **What it is:** Natural language to Cypher - QueryIntent, CompiledQuery, schema models
- **Issues:** Timeout allows 5 minutes (line 424) - MEDIUM

### File 11: `graph_analysis.py`
- **What it is:** Graph algorithm results - NodeRanking, Community, trust transitivity

### File 12: `notifications.py`
- **What it is:** Webhooks, in-app notifications, delivery tracking
- **Issues:** Webhook secret stored unhashed (line 87) - MEDIUM

### File 13: `marketplace.py`
- **What it is:** Knowledge marketplace - listings, purchases, licenses, revenue distribution (70/15/10/5)
- **Issues:** Cart total ignores currency (lines 165-168) - MEDIUM

### File 14: `agent_gateway.py`
- **What it is:** AI agent integration - sessions, queries, access control, streaming
- **Issues:** Excessive timeout (line 123) - MEDIUM

---

## 1.7 Monitoring Module (`forge-cascade-v2/forge/monitoring/`)

**Files:** 3 | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package entry point exporting monitoring APIs
- **What it does:** Re-exports MetricsRegistry, Counter, Gauge, Histogram, Summary, configure_logging, get_logger
- **How it does it:** Relative imports with `__all__` facade pattern
- **Why it does it:** Clean API hiding internal structure
- **Part in codebase:** Used by `forge/api/app.py` for bootstrap
- **Issues found:** Incomplete `__all__` list (LOW)
- **Errors found:** None
- **Needs fixing:** Add all exported symbols to `__all__` (LOW)
- **Can be improved:** Version info, lazy imports
- **New possibilities:** Unified `initialize_monitoring()` function

### File 2: `metrics.py` (644 lines)
- **What it is:** Prometheus-compatible metrics collection system
- **What it does:** Counter, Gauge, Histogram, Summary metrics; MetricsRegistry; FastAPI middleware; `/metrics` endpoint
- **How it does it:** Dataclasses for metric types, label-keyed dicts, Prometheus text format export
- **Why it does it:** Lightweight async-first custom implementation vs official library
- **Part in codebase:** HTTP metrics, DB queries, pipeline, overlays, LLM, governance
- **Issues found:**
  - **CRITICAL**: Histogram/Summary store ALL observations - unbounded memory (lines 110-117, 156-163)
  - **HIGH**: `reset_metrics()` breaks global metric references (line 615-618)
  - Thread safety missing for `_values` mutations
- **Errors found:** Memory exhaustion possible; state corruption on reset
- **Needs fixing:** Bounded observation storage (CRITICAL); Thread safety (HIGH)
- **Can be improved:** Time-window sampling, metric TTL, OpenTelemetry bridge
- **New possibilities:** Distributed metrics, push gateway, alert rules

### File 3: `logging.py` (372 lines)
- **What it is:** Structured logging with structlog
- **What it does:** JSON/Console output, sensitive data sanitization, request context middleware
- **How it does it:** Processor pipeline, `contextvars` for async context, recursive sanitization
- **Why it does it:** Machine-parseable logs, credential leak prevention
- **Part in codebase:** 50+ files use `structlog.get_logger()`
- **Issues found:**
  - **HIGH**: Formatter mutations via `pop()` (lines 282-297, 304-314)
  - **HIGH**: Missing sensitive keys (private_key, access_token, etc.)
- **Errors found:** Formatter data loss; potential import error for `rich`
- **Needs fixing:** Copy dict before processing (HIGH); Expand sensitive keys (HIGH)
- **Can be improved:** Configurable sensitive keys, async file handler, log sampling
- **New possibilities:** Direct push to Loki/ES, audit trail, PII detection

---

## 1.8 Overlays Module (`forge-cascade-v2/forge/overlays/`)

**Files:** 11 (~5,500 lines) | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package entry point exporting 11 overlays and 60+ symbols

### File 2: `base.py`
- **What it is:** BaseOverlay ABC, OverlayContext, OverlayResult, capability-based security
- **Issues:** Error rate calculation bug (line 330-331) - MEDIUM

### File 3: `ml_intelligence.py` (ANALYSIS phase)
- **What it is:** Embedding generation, classification, entity extraction, sentiment, anomaly scoring
- **How it does it:** Hash-based pseudo-embedding (dev), cache with FIFO eviction
- **Issues:** Inconsistent OverlayResult construction (lines 229-234) - MEDIUM

### File 4: `capsule_analyzer.py`
- **What it is:** Quality scoring, insight extraction, similarity detection
- **Issues:**
  - Unbounded caches - memory leak risk (lines 90-93) - MEDIUM
  - health_check return type mismatch (lines 610-617) - MEDIUM

### File 5: `performance_optimizer.py`
- **What it is:** Query caching, response time tracking, LLM parameter optimization
- **Issues:**
  - **HIGH**: Unbounded cache (line 94)
  - Percentile calculation fails on small samples (lines 227-228) - MEDIUM

### File 6: `graph_algorithms.py`
- **What it is:** PageRank, centrality, community detection, trust transitivity
- **How it does it:** GDS → Cypher → NetworkX fallback

### File 7: `temporal_tracker.py` (SETTLEMENT phase)
- **What it is:** Version history, trust evolution, time-travel queries
- **How it does it:** Hybrid snapshot/diff, policy-driven, smart compaction

### File 8: `knowledge_query.py`
- **What it is:** Natural language → Cypher, trust-aware, Cypher validation
- **Issues:** Cache size limits needed (line 201) - MEDIUM

### File 9: `governance.py` (CONSENSUS phase)
- **What it is:** Proposals, trust-weighted voting, SafeCondition policy validation
- **How it does it:** Vote weight clamped 0-100, quorum calculation, timelock
- **Issues:** In-memory proposals lost on restart (line 356) - MEDIUM

### File 10: `lineage_tracker.py` (SETTLEMENT phase)
- **What it is:** Isnad chains, semantic edges, contradiction detection
- **How it does it:** Bounded memory (100k nodes), LRU eviction, iterative BFS
- **Security:** Audit 2,3,4 fixes applied - bounded memory, iterative algorithms

### File 11: `security_validator.py` (VALIDATION phase)
- **What it is:** Content policy, trust verification, rate limiting, threat detection
- **How it does it:** safe_search for ReDoS prevention, async locks, OrderedDict LRU
- **Security:** Multiple audit fixes - SQL/XSS detection, bounded caches

---

## 1.9 Repositories Module (`forge-cascade-v2/forge/repositories/`)

**Files:** 9 (~7,721 lines) | **Status:** COMPLETE

### File 1: `__init__.py`
- **What it is:** Package entry point exporting 8 repository classes

### File 2: `base.py` (354 lines)
- **What it is:** Generic Repository pattern with CRUD, pagination (max 1000), identifier validation
- **How it does it:** Regex validation `^[a-zA-Z_][a-zA-Z0-9_]*$`, timezone-aware timestamps

### File 3: `temporal_repository.py` (908 lines)
- **What it is:** Capsule versioning, trust snapshots, graph snapshots, time-travel queries
- **Issues:**
  - **CRITICAL**: Diff algorithm is fundamentally broken (lines 390-402)
  - Diff loses position info, corrupts content on reconstruction

### File 4: `graph_repository.py` (1,443 lines)
- **What it is:** PageRank, centrality, community detection, trust transitivity, pathfinding
- **How it does it:** Multi-backend (GDS → Cypher fallback), caching with TTL
- **Issues:** Cypher PageRank approximation is not true PageRank (lines 284-319)

### File 5: `overlay_repository.py` (617 lines)
- **What it is:** WASM overlay lifecycle, state machine, SHA-256 hash verification
- **How it does it:** Auto-quarantine after 5 failures, embedded metrics

### File 6: `user_repository.py` (611 lines)
- **What it is:** User CRUD, auth support, trust flame management
- **How it does it:** Safe field lists prevent hash leakage, constant-time comparison (Audit 4 M1)

### File 7: `governance_repository.py` (1,299 lines)
- **What it is:** Proposals, votes, delegations, Constitutional AI, Ghost Council
- **How it does it:** Trust verification from DB (H20), timelock enforcement (H21)
- **Issues:** Vote choice values inconsistent ('APPROVE' vs 'for') - HIGH

### File 8: `capsule_repository.py` (1,364 lines)
- **What it is:** Core CRUD, lineage (Isnad), semantic search, semantic edges
- **How it does it:** Vector index queries, owner verification (H27), MAX_GRAPH_DEPTH=20
- **Issues:** Cypher injection in get_semantic_edges (line 1199) - HIGH

### File 9: `audit_repository.py` (1,118 lines)
- **What it is:** Comprehensive audit logging, compliance (GDPR), self-audit
- **How it does it:** Correlation IDs, archive pattern, JSON serialization

---

## 1.10 Resilience Module (`forge-cascade-v2/forge/resilience/`)

**Files:** 27 (~9,500 lines) | **Status:** COMPLETE

### Summary
Enterprise-grade reliability, scalability, and operational resilience across 9 subdirectories: caching, observability, security, lineage, migration, partitioning, cold_start, and profiles.

### Critical Issues Found
- **HIGH**: `integration.py` Lines 437-441, 633 - Wildcard cache deletion using `cache.delete("proposals:list:*")` doesn't work with Redis - needs `scan_iter` pattern matching
- **HIGH**: `tenant_isolation.py` Line 330 - Tenant filter not applied when query has no WHERE clause (data leakage risk)

### Key Files
- `config.py`: 11 configuration dataclasses, profile-based defaults, environment variable loading
- `integration.py`: FastAPI middleware, 40+ caching/metrics helpers, pattern-based path templating
- `caching/query_cache.py`: Two-tier Redis cache with JSON serialization (security fix), TTL-based expiration
- `observability/tracing.py`: OpenTelemetry integration with graceful degradation
- `security/content_validator.py`: Multi-stage validation pipeline with ReDoS timeout protection
- `security/tenant_isolation.py`: Multi-tenant isolation with quota enforcement
- `lineage/tiered_storage.py`: Three-tier storage (Hot/Warm/Cold) with gzip compression
- `partitioning/partition_manager.py`: Domain-based partitioning with SHA-256 IDs

### Security Audit Fixes Applied
- Content validation with ReDoS timeout protection (Audit 4)
- Parameterized tenant queries (Audit 4 - H14)
- Filter key validation for migrations (Audit 4 - H17)
- Content validation for starter packs (Audit 4 - H30)

---

## 1.11 Security Module (`forge-cascade-v2/forge/security/`)

**Files:** 9 (~4,500 lines) | **Status:** COMPLETE

### Summary
Comprehensive security infrastructure: authorization, MFA, JWT tokens, password hashing, prompt sanitization, and ReDoS protection.

### Critical Issues Found
- **CRITICAL**: `mfa.py` Line 459 - Missing `timedelta` import causes NameError at runtime
- **HIGH**: `safe_regex.py` Line 305 - Wrong argument order in `safe_sub()`
- **HIGH**: `tokens.py` Lines 993-995 - `TokenService.create_refresh_token` missing username parameter
- **HIGH**: `mfa.py` Line 577-579 - `verify_backup_code()` doesn't load from DB first

### Key Files
- `authorization.py` (757 lines): Trust-based RBAC with 5-level hierarchy, capability-based access control
- `tokens.py` (1,031 lines): JWT management with key rotation, token blacklist (Redis + memory fallback)
- `password.py` (345 lines): Bcrypt hashing, Unicode normalization (Audit 4 L10), strength validation
- `auth_service.py` (1,031 lines): IP rate limiting (Audit 4 M2), account lockout, token rotation
- `mfa.py` (693 lines): TOTP-based MFA (RFC 6238), backup codes, rate limiting
- `safe_regex.py` (313 lines): ReDoS protection with timeout, pattern validation
- `prompt_sanitization.py` (277 lines): LLM prompt injection prevention with 24 patterns
- `dependencies.py` (486 lines): FastAPI security dependencies, IP extraction with proxy trust

### Security Audit Fixes Applied
- Algorithm confusion prevention for JWT (CVE-2022-29217 fix)
- IP spoofing prevention (Audit 4 M7)
- Missing claims rejection (Audit 4 H1)

---

## 1.12 Services Module (`forge-cascade-v2/forge/services/`)

**Files:** 14 (~9,500 lines) | **Status:** COMPLETE

### Summary
Core business services: LLM integration, Ghost Council AI advisory, search, embeddings, marketplace, notifications, and query compilation.

### Critical Issues Found
- **CRITICAL**: `query_compiler.py` Line 605 - SQL injection via string interpolation in trust filter
- **CRITICAL**: `semantic_edge_detector.py` Lines 284-288, 294 - API mismatch with LLMService (wrong method signature/attribute)
- **CRITICAL**: `notifications.py` Lines 274, 284-285, 309 - Undefined `self._logger` causes AttributeError
- **HIGH**: `notifications.py` Lines 848-858 - Secret field mismatch between save/load
- **HIGH**: `scheduler.py` Lines 318-319, 359-360, 365-366 - Database connection leak per task execution
- **HIGH**: `llm.py` Lines 878-881 - HTTP client not closed on shutdown
- **HIGH**: `marketplace.py` Lines 184, 240-252 - Updates and cart not persisted
- **HIGH**: `pricing_engine.py` Lines 505-522, 680-683 - Stub implementations not completed

### Key Files
- `llm.py` (894 lines): Multi-provider LLM abstraction (Anthropic, OpenAI, Ollama, Mock), retry logic
- `ghost_council.py` (1,444 lines): 10-member AI advisory board with tri-perspective analysis
- `search.py` (644 lines): Semantic, keyword, and hybrid search modes
- `embedding.py` (690 lines): Vector embedding with caching, batch limits (Audit 4 H25)
- `query_compiler.py` (854 lines): Natural language to Cypher translation with validation
- `marketplace.py` (784 lines): Knowledge capsule e-commerce (70/15/10/5 revenue split)
- `notifications.py` (905 lines): Multi-channel notifications with SSRF protection, HMAC signatures
- `agent_gateway.py` (1,012 lines): AI agent integration with bounded memory (Audit 4 H10)

### Security Audit Fixes Applied
- HTTP client reuse (Audit 3)
- Prompt sanitization for injection prevention (Audit 4)
- SSRF protection for webhooks (Audit 3)
- Bcrypt for webhook secrets (Audit 4 H18)
- Admin-only broadcast (Audit 4 M19)
- Batch size limiting (Audit 4 H25)

---

# SECTION 2: ADDITIONAL MODULES

## 2.1 Compliance Module (`forge/compliance/`)

**Files:** 30+ (~8,500 lines) | **Status:** COMPLETE

### Overview
Enterprise-grade compliance framework implementing 400+ technical controls across 25+ regulatory frameworks (GDPR, CCPA/CPRA, HIPAA, PCI-DSS, EU AI Act, SOC 2, ISO 27001).

### Critical Issues Found
- **CRITICAL**: `server.py` - CORS policy allows any origin (`allow_origins=["*"]`) for sensitive compliance APIs
- **CRITICAL**: `core/engine.py` - In-memory storage loses all data on restart (DSARs, breaches, consents, audit logs)
- **CRITICAL**: `api/routes.py` - No authentication/authorization on any endpoint
- **CRITICAL**: `encryption/service.py` - InMemoryKeyStore not suitable for production (keys lost on restart)
- **HIGH**: `core/engine.py` - No concurrency control/locking for shared state
- **HIGH**: `privacy/dsar_processor.py` - Data source operations are synchronous (blocks event loop)
- **HIGH**: `security/access_control.py` - No enforcement mechanism for defined policies

### File Documentation

#### Root Files
- `__init__.py` (150 lines): Public API facade with comprehensive exports
- `server.py`: FastAPI microservice on port 8002 with health check
- `verify_imports.py`: CI/CD import validation script

#### Core Module (`core/`)
| File | Lines | Purpose | Critical Issues |
|------|-------|---------|-----------------|
| `enums.py` | 830 | Jurisdiction, Framework, Classification enums | Hardcoded deadline values |
| `config.py` | 250 | Pydantic BaseSettings with env var loading | HSM disabled by default |
| `models.py` | 730 | ComplianceStatus, DSAR, Consent, Breach, AISystem models | Audit event stores plaintext errors |
| `registry.py` | 600 | 400+ compliance control definitions | Static controls, no dynamic registration |
| `engine.py` | 1153 | Central orchestration with audit chain | In-memory state, no persistence |

#### API Module (`api/`)
| File | Lines | Purpose | Critical Issues |
|------|-------|---------|-----------------|
| `routes.py` | 150+ | DSAR, consent, breach endpoints | No auth/authz on any endpoint |
| `extended_routes.py` | 150+ | Industry-specific endpoints | Business logic in routes |

#### Service Modules

**Encryption (`encryption/service.py`)**
- AES-256-GCM encryption with key rotation
- Key lifecycle management
- **CRITICAL**: InMemoryKeyStore loses keys on restart

**Privacy Services**
- `consent_service.py`: GDPR/CCPA/TCF consent management
  - **HIGH**: No TCF string validation
  - **MEDIUM**: GPC signal handling incomplete
- `dsar_processor.py`: Automated DSAR lifecycle
  - **CRITICAL**: Sync data source operations block event loop
  - **HIGH**: No state machine for status transitions

**Security Services**
- `access_control.py`: RBAC/ABAC implementation
  - **CRITICAL**: Policies defined but not enforced
- `breach_notification.py`: Incident response management
  - **CRITICAL**: No deadline enforcement/alerting
- `vendor_management.py`: Third-party risk management
  - **HIGH**: No certification verification

**Data Residency (`residency/service.py`)**
- Transfer Impact Assessments (Schrems II)
- Cross-border transfer management
- **CRITICAL**: No integration with actual data movement

**AI Governance (`ai_governance/service.py`)**
- EU AI Act compliance
- Bias detection and fairness metrics
- **CRITICAL**: No actual bias detection implementation

**Industry Services (`industry/services.py`)**
- HIPAA authorization and PHI access logging
- PCI-DSS controls
- COPPA parental consent
- **CRITICAL**: Authorization validation weak (no signature verification)

**Accessibility (`accessibility/service.py`)**
- WCAG 2.2 compliance tracking
- VPAT generation
- **CRITICAL**: No actual accessibility testing integration

**Reporting (`reporting/service.py`)**
- SOC 2, gap analysis, audit readiness reports
- **HIGH**: Report generation logic not implemented

### Regulatory Framework Coverage
| Framework | Coverage | Implementation Status |
|-----------|----------|----------------------|
| GDPR | Articles 5-21, 25-34 | 80% |
| CCPA/CPRA | §1798.100-199 | 75% |
| HIPAA | 164.302-318, 400-414 | 60% |
| PCI-DSS 4.0 | Req 1-12 | 50% |
| EU AI Act | Title III-IV | 40% |
| SOC 2 | CC1-CC9 | 70% |
| ISO 27001 | A.5-A.18 | 65% |

### Immediate Action Required
1. Implement persistent storage layer (PostgreSQL recommended)
2. Add authentication middleware to all API endpoints
3. Implement access control enforcement
4. Force HSM backend for production encryption
5. Add database transactions for consistency

---

## 2.2 Virtuals Integration (`forge_virtuals_integration/`)

**Files:** 23 (~9,500 lines) | **Status:** COMPLETE

### Summary
Integration between Forge's institutional memory and Virtuals Protocol's autonomous AI agent infrastructure. Covers tokenization, GAME framework agents, Agent Commerce Protocol (ACP), and multi-chain support.

### Critical Issues Found
- **CRITICAL**: `models/tokenization.py` Lines 21-27 - Fake enum classes that don't actually use Enum
- **CRITICAL**: `game/sdk_client.py` Line 353 - Infinite recursion possible on auth failure
- **HIGH**: `revenue/service.py` Line 68 - In-memory pending distributions lost on restart
- **HIGH**: `acp/service.py` Line 99 - In-memory nonce tracking lost on restart (enables replay attacks)
- **HIGH**: `tokenization/service.py` Line 553 - Voting power hardcoded to 1000.0 placeholder
- **HIGH**: `api/routes.py` Lines 83-91 - Development mode returns placeholder wallet (could leak to production)

### Key Files
- `config.py`: VirtualsConfig with environment variable loading, contract addresses, RPC endpoints
- `models/agent.py`: ForgeAgent, AgentPersonality, WorkerDefinition for GAME framework
- `chains/evm_client.py`: EVM blockchain interactions (Base/Ethereum) with web3.py
- `chains/solana_client.py`: Solana blockchain interactions with Ed25519 signatures
- `game/sdk_client.py`: GAME framework API client with agent loop execution
- `game/forge_functions.py`: 7 pre-built functions for agents (search, create capsule, vote)
- `tokenization/service.py`: Entity tokenization lifecycle with bonding curve math
- `acp/service.py`: Agent Commerce Protocol with 4-phase transactions and escrow
- `revenue/service.py`: Revenue tracking, distribution, DCF valuation

### Security Audit Fixes Applied
- Wallet creation returns private key for secure storage (Audit fix)
- Unlimited token approvals require explicit `allow_unlimited=True` (Audit fix)
- ACP memo signing with real cryptographic signatures (ECDSA/Ed25519)
- Nonce-based replay attack prevention
- Distribution integrity verification

---

## 2.3 Marketplace Frontend (`marketplace/`)

**Files:** 20 (React/TypeScript/Vite) | **Status:** COMPLETE

### Summary
React 19 frontend for "Forge Shop" knowledge capsule marketplace. Built with Vite, TanStack Query, Tailwind CSS.

### Critical Issues Found
- **CRITICAL**: `CapsuleDetail.tsx` Lines 5-6 - Page never fetches capsule data, always shows placeholder
- **HIGH**: `CapsuleDetail.tsx` Lines 53-93 - All content hardcoded, buttons non-functional
- **HIGH**: `Profile.tsx` Lines 1-46 - Entire page static, no auth integration
- **HIGH**: `App.tsx` Lines 17-18 - No protected routes (Profile accessible when logged out)

### Medium Issues
- `Browse.tsx` Lines 152-158: Trust level filters non-functional
- `CartContext.tsx` Lines 67-71: Type mismatches with Capsule interface
- `Login.tsx` Lines 84-85: OAuth callback route `/auth/callback` doesn't exist in App.tsx
- `App.tsx` Lines 12-20: No 404 catch-all route
- `nginx.conf` Line 21: CSP uses unsafe-inline (weakens XSS protection)
- `Dockerfile` Line 24: Missing package-lock.json (non-reproducible builds)

### Key Files
- `src/App.tsx`: React Router v7 routing (6 routes under Layout)
- `src/pages/Browse.tsx` (371 lines): Capsule catalog with filters, grid/list views
- `src/contexts/AuthContext.tsx`: Authentication state with TanStack Query integration
- `src/contexts/CartContext.tsx`: Shopping cart with localStorage persistence, XSS sanitization
- `src/hooks/useCapsules.ts`: TanStack Query hooks for data fetching
- `src/services/api.ts`: Axios client with CSRF, auth interceptor

### Architecture
```
marketplace/
├── src/components/ (Layout, common)
├── src/pages/ (Home, Browse, CapsuleDetail, Cart, Profile, Login)
├── src/contexts/ (Auth, Cart)
├── src/hooks/ (useCapsules)
├── src/services/ (api client)
└── Configuration (Vite, Tailwind, TypeScript)
```

---

## 2.4 Main Frontend (`forge-cascade-v2/frontend/`)

**Files:** 25 (React 19/TypeScript/Vite) | **Status:** COMPLETE

### Overview
Modern React 19 SPA with trust-based governance UI, TanStack Query for server state, Zustand for client state, Tailwind CSS styling. Implements dashboard, capsule management, governance voting, Ghost Council AI advisory, and system monitoring.

### Critical Issues Found
- **CRITICAL**: `pages/CapsuleDetail.tsx` - Never fetches data, always shows placeholder
- **HIGH**: ~50% of page implementations are incomplete stubs
- **HIGH**: No edit functionality for capsules (Edit button non-functional)
- **HIGH**: Missing proposal creation UI in GovernancePage
- **MEDIUM**: CSRF error detection relies on string matching (brittle)
- **MEDIUM**: Frontend trust filtering only - backend must enforce

### Configuration Files

| File | Purpose | Issues |
|------|---------|--------|
| `package.json` | Dependencies (React 19, Router 7, Query 5) | axios slightly outdated |
| `vite.config.ts` | Vite bundler config | No proxy config for dev |
| `tsconfig.json` | TypeScript strict mode enabled | None |
| `tailwind.config.js` | Custom theme (forge, ghost, trust palettes) | None |

### Core Application

**Entry Point (`src/main.tsx`)**
- QueryClient with 1-min stale time, 1 retry
- ErrorBoundary → ThemeProvider → QueryClient → BrowserRouter → App
- **Issue**: Global error handler only logs to console (no error tracking)

**Router (`src/App.tsx`)**
```
/login                     → LoginPage
/                          → Layout (protected)
  /                        → DashboardPage
  /capsules                → CapsulesPage
  /capsules/:id/versions   → VersionHistoryPage
  /governance              → GovernancePage
  /ghost-council           → GhostCouncilPage
  /overlays                → OverlaysPage (TRUSTED+)
  /federation              → FederationPage (TRUSTED+)
  /graph                   → GraphExplorerPage
  /system                  → SystemPage (TRUSTED+)
  /settings                → SettingsPage
```

### API Client (`src/api/client.ts` - 554 lines)

**Security Implementation**
- httpOnly cookies for JWT tokens (XSS-immune)
- CSRF token management (in-memory, not localStorage)
- Auto token refresh with 401 handling
- Rate-limited retry prevention

**Issues**
- **MEDIUM**: CSRF error detection via string matching ("CSRF" in error message)
- **LOW**: 401 retry flag could cause double-fetch on network errors

### State Management

**Auth Store (`src/stores/authStore.ts` - 143 lines)**
- Zustand with localStorage persistence (isAuthenticated only)
- User/TrustInfo fetching on demand
- **Issue**: Auto-login after registration (should require verification)

**Theme Context (`src/contexts/ThemeContext.tsx`)**
- Light/Dark/System modes
- Respects prefers-color-scheme
- localStorage persistence

### Component Library (`src/components/common/index.tsx` - 664 lines)

| Component | Features |
|-----------|----------|
| ErrorBoundary | Catches render errors, dev-mode details |
| Card | 3 variants (default, hover, accent) |
| Button | 6 variants, 3 sizes, loading state |
| TrustBadge | 5 trust levels with colors |
| Modal | Focus trap, backdrop click, configurable size |
| Input/Select/Textarea | Labels, errors, help text |
| Skeleton | Shimmer animation loading states |

### Page Implementations

| Page | Lines | Status | Critical Issues |
|------|-------|--------|-----------------|
| LoginPage | 346 | ✅ Complete | None |
| DashboardPage | 388 | ✅ Complete | Mock chart data |
| CapsulesPage | 882 | ⚠️ 80% | Edit non-functional |
| GovernancePage | 150+ | ❌ Partial | No create/vote UI |
| GhostCouncilPage | 80+ | ❌ Partial | Stub implementation |
| OverlaysPage | 80+ | ❌ Partial | Stub implementation |
| ContradictionsPage | 80+ | ❌ Partial | Stub implementation |
| FederationPage | 80+ | ❌ Partial | Stub implementation |
| GraphExplorerPage | 80+ | ❌ Partial | Stub implementation |
| SystemPage | 100+ | ❌ Partial | Stub implementation |
| SettingsPage | 100+ | ❌ Partial | Stub implementation |

### Layout Components

**Header (`src/components/layout/Header.tsx` - 113 lines)**
- Search bar (navigates to /capsules?search=)
- System health indicator (30s refresh)
- Notification bell with anomaly count
- **Issue**: Notification click does nothing

**Sidebar (`src/components/layout/Sidebar.tsx` - 185 lines)**
- Collapsible navigation
- Trust-level based menu filtering
- User avatar and trust badge

### Types (`src/types/index.ts` - 316 lines)
- Comprehensive type coverage
- TrustLevel, UserRole, CapsuleType, ProposalStatus enums
- User, Capsule, Proposal, Vote, SystemHealth interfaces
- PaginatedResponse<T> generic

### Estimated Completion: 40-50%

### Immediate Action Required
1. Complete all stub page implementations
2. Implement capsule edit functionality
3. Add proposal creation and voting UI
4. Integrate error tracking (Sentry recommended)
5. Add form validation framework (React Hook Form + Zod)
6. Add unit/E2E tests (Vitest, Playwright)

---

# SECTION 3: CONFIGURATION & DEVOPS

## 3.1 Docker & Infrastructure

**Files:** 31 configuration files | **Status:** COMPLETE

### Summary
Comprehensive Docker and DevOps infrastructure: development, production, Cloudflare tunnel deployments; CI/CD pipelines; nginx reverse proxy with SSL.

### Critical Issues Found
- **CRITICAL**: `docker-compose.prod.yml` Lines 312-313 - Unused/mismatched volume declarations
- **CRITICAL**: `nginx.prod.conf` Lines 134-136 - HTTP redirect to HTTP instead of HTTPS (logic error)
- **CRITICAL**: `.github/workflows/ci.yml` Lines 25, 28, etc. - Uses non-existent GitHub Action versions (@v6)
- **CRITICAL**: `.github/workflows/pr-check.yml` Lines 17, 24, 37 - Uses non-existent Action versions (@v6)
- **CRITICAL**: `.github/workflows/release.yml` Lines 27, 48, 59 - Uses non-existent Action versions (@v6)

### High Priority Issues
- `docker-compose.yml` Line 137: Frontend exposed on 0.0.0.0:80 (should be localhost)
- `docker-compose.cloudflare.yml` Lines 192-193: Jaeger exposed externally (bypasses tunnel security)
- `forge-cascade-v2/docker/docker-compose.prod.yml` Lines 27-28: Neo4j exposed externally
- `forge-cascade-v2/docker/docker-compose.prod.yml` Line 75: Redis password may be empty
- `forge-cascade-v2/docker/docker-compose.prod.yml` Line 287: Docker socket mounted (security risk)
- `Dockerfile.backend` Line 107: `--forwarded-allow-ips "*"` is insecure
- `ci.yml` Lines 43, 60-61, 112, 142: Test failures ignored with `|| true`

### Key Files
- `docker-compose.yml`: 8 services for development with health checks and resource limits
- `docker-compose.prod.yml`: Production with nginx SSL termination and certbot
- `docker-compose.cloudflare.yml`: Cloudflare Tunnel alternative deployment
- `forge-cascade-v2/docker/docker-compose.prod.yml`: Full stack with Prometheus, Grafana, Loki
- `deploy/docker-compose.prod.yml`: Pre-built GHCR images for deployment
- `.github/workflows/ci.yml`: Main CI/CD with linting, tests, Docker builds, security scanning
- `deploy/nginx/sites/forgecascade.org.conf`: Production nginx with rate limiting, WebSocket proxy

### Recommendations
1. **Immediate**: Fix GitHub Actions versions (@v6 → @v4)
2. **Immediate**: Fix nginx HTTPS redirect logic
3. **High**: Bind internal services to localhost, not 0.0.0.0
4. **High**: Pin Docker image tags (no floating :latest)
5. **Medium**: Remove Docker socket mount from monitoring stack

---

## 3.2 Scripts & Tests

**Files:** 20+ scripts and test files | **Status:** COMPLETE

### Summary
Test suite (pytest), database scripts, backup/restore utilities, deployment automation, and CI/CD helper scripts.

### CRITICAL SECURITY FINDING
- **CRITICAL**: `.seed_credentials` file contains **plaintext passwords** - MUST rotate immediately:
  ```
  SEED_ADMIN_PASSWORD=dyxIiN95JaM8hu3Fdl!mog*G
  SEED_ORACLE_PASSWORD=Z^65k92u#JD8kJ7plWaadRgA
  ...
  ```

### High Priority Issues
- `test_endpoints.py` Lines 59, 75, 87, 99: Tests accept HTTP 500 status codes, masking errors
- `seed_data.py` Line 446: Deletes all data before reseeding without confirmation
- `neo4j_backup.py` Lines 127-139: No batching - memory issues with large databases
- `neo4j_restore.py` Line 97-106: `clear_database` has no confirmation check
- `deploy.sh` Line 101: Unsafe env file sourcing (`source "$ENV_FILE"`)

### Key Files

**Test Files:**
- `conftest.py` (401 lines): Pytest fixtures with production environment detection
- `test_embedding.py`: Unit tests for EmbeddingService
- `test_llm.py`: Unit tests for LLMService and Ghost Council
- `test_search.py`: Unit tests for SearchService
- `test_endpoints.py`: API integration tests
- `manual_test.py`: End-to-end feature verification script

**Database Scripts:**
- `setup_db.py`: Neo4j schema initialization (constraints, indexes, vector indexes)
- `seed_data.py`: Development data seeding with secure password generation
- `health_check.py`: System health monitoring (Neo4j, API, Redis)

**Backup Scripts:**
- `neo4j_backup.py`: Database export to compressed JSON with incremental support
- `neo4j_restore.py`: Database restoration with ID mapping
- `backup.sh`: Backup wrapper with S3 upload and webhook notifications
- `entrypoint.sh`: Docker backup service entrypoint with cron scheduling

**Deployment Scripts:**
- `deploy.sh`: Production deployment automation with SSL setup
- `init-ssl.sh`: Let's Encrypt certificate initialization
- `start_servers.sh`: Development server startup

### Test Coverage Assessment
| Module | Coverage | Gaps |
|--------|----------|------|
| Embedding | Good | OpenAI provider, error handling |
| LLM | Good | Streaming, rate limits, timeouts |
| Search | Good | Pagination, fuzzy search |
| API | Medium | Accepts 500 errors as valid |
| Integration | Good | Not in CI pipeline |

---

# APPENDIX: SUMMARY TABLES

## Critical Issues by File

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `.seed_credentials` | - | Plaintext passwords in repository | **CRITICAL** |
| `mfa.py` | 459 | Missing `timedelta` import causes NameError | **CRITICAL** |
| `query_compiler.py` | 605 | SQL injection via string interpolation | **CRITICAL** |
| `semantic_edge_detector.py` | 284-294 | API mismatch with LLMService | **CRITICAL** |
| `notifications.py` | 274, 284, 309 | Undefined `self._logger` | **CRITICAL** |
| `CapsuleDetail.tsx` | 5-6 | Never fetches data, always placeholder | **CRITICAL** |
| `nginx.prod.conf` | 134-136 | HTTP→HTTP redirect (should be HTTPS) | **CRITICAL** |
| `ci.yml` | 25, 28, etc. | Uses non-existent @v6 GitHub Actions | **CRITICAL** |
| `sync.py` | 689 | `peer.endpoint` should be `peer.url` | **CRITICAL** |
| `temporal_repository.py` | 390-402 | Diff algorithm fundamentally broken | **CRITICAL** |
| `wasm_runtime.py` | 282-289 | SQL injection in DatabaseReadHostFunction | **CRITICAL** |
| `metrics.py` | 110-117 | Unbounded memory (Histogram stores ALL obs) | **CRITICAL** |
| `routes/users.py` | 15-24 | Wrong import paths - module won't load | **CRITICAL** |
| `middleware.py` | 640 | CSRF comparison fails if tokens None | **CRITICAL** |
| `compliance/server.py` | - | CORS allows any origin for sensitive APIs | **CRITICAL** |
| `compliance/engine.py` | - | In-memory storage loses all data on restart | **CRITICAL** |
| `compliance/api/routes.py` | - | No authentication on any endpoint | **CRITICAL** |
| `compliance/encryption/service.py` | - | InMemoryKeyStore loses keys on restart | **CRITICAL** |
| `compliance/access_control.py` | - | Policies defined but not enforced | **CRITICAL** |

## High Priority Issues Summary

| Category | Count | Key Examples |
|----------|-------|--------------|
| Security | 15 | Missing auth, SQL injection, hardcoded secrets |
| Data Integrity | 8 | Lost data on restart, broken algorithms |
| Memory Leaks | 6 | Unbounded caches, no eviction |
| API Mismatches | 5 | Wrong field names, missing parameters |
| CI/CD | 5 | Wrong action versions, ignored test failures |

## Module Completion Status

| Module | Files | Status | Critical Issues |
|--------|-------|--------|-----------------|
| Database | 3 | COMPLETE | 1 |
| Federation | 5 | COMPLETE | 3 |
| Immune | 5 | COMPLETE | 2 |
| Kernel | 5 | COMPLETE | 3 |
| Models | 14 | COMPLETE | 1 |
| Monitoring | 3 | COMPLETE | 1 |
| Overlays | 11 | COMPLETE | 1 |
| Repositories | 9 | COMPLETE | 2 |
| Resilience | 27 | COMPLETE | 2 |
| Security | 9 | COMPLETE | 4 |
| Services | 14 | COMPLETE | 4 |
| Compliance | 30 | COMPLETE | 8 |
| Virtuals | 23 | COMPLETE | 3 |
| Marketplace | 20 | COMPLETE | 1 |
| Frontend | 25 | COMPLETE | 2 |
| API | 18 | COMPLETE | 5 |
| DevOps | 31 | COMPLETE | 5 |
| Scripts/Tests | 20+ | COMPLETE | 1 |

## Recommended Fix Priority

### Immediate (Before Production)
1. Rotate all `.seed_credentials` passwords
2. Fix GitHub Actions @v6 → @v4
3. Fix nginx HTTPS redirect logic
4. Fix SQL injection in `query_compiler.py` and `wasm_runtime.py`
5. Fix `mfa.py` missing import
6. Fix `notifications.py` undefined logger

### Short-term (Within 1 Week)
1. Implement missing data fetching in `CapsuleDetail.tsx`
2. Fix API mismatches in `semantic_edge_detector.py`
3. Add memory bounds to caches and histograms
4. Fix peer attribute name mismatches in federation
5. Pin all Docker image tags

### Medium-term (Within 1 Month)
1. Add protected routes in marketplace frontend
2. Implement actual checkout flow
3. Complete stub implementations in `pricing_engine.py`
4. Add batching to `neo4j_backup.py`
5. Improve test coverage (remove 500 acceptance)

