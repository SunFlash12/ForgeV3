# Forge V3 - Models Analysis

## Category: Data Models
## Status: COMPLETE
## Last Updated: 2026-01-10

---

## Files in this Category (19 files)

| # | File | Status | Summary |
|---|------|--------|---------|
| 1 | `forge-cascade-v2/forge/models/__init__.py` | Complete | Central export module for all model classes |
| 2 | `forge-cascade-v2/forge/models/agent_gateway.py` | Complete | AI agent gateway with sessions, queries, capabilities |
| 3 | `forge-cascade-v2/forge/models/base.py` | Complete | Foundation: ForgeModel, enums, mixins, responses |
| 4 | `forge-cascade-v2/forge/models/capsule.py` | Complete | Capsule models with versioning, lineage, integrity |
| 5 | `forge-cascade-v2/forge/models/events.py` | Complete | Event system for pub/sub and cascade propagation |
| 6 | `forge-cascade-v2/forge/models/governance.py` | Complete | Governance: proposals, votes, Constitutional AI |
| 7 | `forge-cascade-v2/forge/models/graph_analysis.py` | Complete | Graph algorithms: PageRank, centrality, communities |
| 8 | `forge-cascade-v2/forge/models/marketplace.py` | Complete | Marketplace: listings, purchases, revenue |
| 9 | `forge-cascade-v2/forge/models/notifications.py` | Complete | Webhooks and notification preferences |
| 10 | `forge-cascade-v2/forge/models/overlay.py` | Complete | Overlay lifecycle, capabilities, metrics |
| 11 | `forge-cascade-v2/forge/models/query.py` | Complete | NL to Cypher query compilation |
| 12 | `forge-cascade-v2/forge/models/semantic_edges.py` | Complete | Semantic relationships between capsules |
| 13 | `forge-cascade-v2/forge/models/temporal.py` | Complete | Versioning, snapshots, trust evolution |
| 14 | `forge-cascade-v2/forge/models/user.py` | Complete | User auth, roles, Trust Flame, signing keys |
| 15 | `forge_virtuals_integration/forge/virtuals/models/__init__.py` | Complete | Virtuals Protocol model exports |
| 16 | `forge_virtuals_integration/forge/virtuals/models/acp.py` | Complete | Agent Commerce Protocol |
| 17 | `forge_virtuals_integration/forge/virtuals/models/agent.py` | Complete | GAME framework agent models |
| 18 | `forge_virtuals_integration/forge/virtuals/models/base.py` | Complete | Virtuals base: wallet, token, transaction |
| 19 | `forge_virtuals_integration/forge/virtuals/models/tokenization.py` | Complete | Entity tokenization on Virtuals Protocol |

---

## Overview

This document provides comprehensive analysis of all model files in the Forge V3 codebase. The models are organized into two main packages:
- **forge-cascade-v2/forge/models/** - Core Forge Cascade models (14 files)
- **forge_virtuals_integration/forge/virtuals/models/** - Virtuals Protocol integration models (5 files)

**Total Models: 192 | Total Enums: 51**

---

## Detailed Analysis

### 1. forge-cascade-v2/forge/models/__init__.py

**Purpose:** Central export module that re-exports all model classes from submodules for convenient imports.

**Models Exported:**
- Base: `ForgeModel`, `TimestampMixin`, `TrustLevel`, `CapsuleType`, `OverlayState`, `ProposalStatus`
- Capsule: `Capsule`, `CapsuleCreate`, `CapsuleUpdate`, `CapsuleInDB`, `CapsuleWithLineage`, `LineageNode`
- User: `User`, `UserCreate`, `UserUpdate`, `UserInDB`, `UserPublic`, `Token`, `TokenPayload`
- Overlay: `Overlay`, `OverlayManifest`, `OverlayMetrics`, `Capability`
- Governance: `Proposal`, `ProposalCreate`, `Vote`, `VoteCreate`, `ConstitutionalAnalysis`
- Events: `Event`, `EventType`, `CascadeEvent`

**Validation Rules:** None directly - delegates to submodules.

**Relationships:** Acts as facade for all model submodules.

**Issues:**
- Some models from submodules not exported (e.g., `GatewayStats`, `SemanticEdge`, `GraphMetrics`)

**Improvements:**
- Consider exporting more models that may be needed externally
- Add version information for API compatibility

**Possibilities:**
- Enable lazy loading for performance
- Add model registry for dynamic discovery

---

### 2. forge-cascade-v2/forge/models/agent_gateway.py

**Purpose:** Data structures for AI agent interactions with the knowledge graph, implementing an Agent Knowledge Gateway.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `AgentCapability` (Enum) | Permissions: READ_CAPSULES, QUERY_GRAPH, SEMANTIC_SEARCH, CREATE_CAPSULES, UPDATE_CAPSULES, EXECUTE_CASCADE, ACCESS_LINEAGE, VIEW_GOVERNANCE |
| `AgentTrustLevel` (Enum) | Trust tiers: UNTRUSTED, BASIC, VERIFIED, TRUSTED, SYSTEM |
| `QueryType` (Enum) | Query types: NATURAL_LANGUAGE, SEMANTIC_SEARCH, GRAPH_TRAVERSE, DIRECT_CYPHER, AGGREGATION |
| `ResponseFormat` (Enum) | Output formats: JSON, MARKDOWN, PLAIN, STREAMING |
| `AgentSession` | Active agent session with rate limiting, usage tracking, permissions |
| `AgentQuery` | Query specification with context, filters, and response preferences |
| `QueryResult` | Result including generated Cypher, answer, sources, and metrics |
| `AccessType` (Enum) | Access types: READ, WRITE, DERIVE |
| `CapsuleAccess` | Record of agent access to a capsule with trust verification |
| `AgentCapsuleCreation` | Request for agent to create a capsule with provenance |
| `GatewayStats` | Statistics for the agent gateway |
| `StreamChunk` | A chunk of streaming response data |

**Validation Rules:**
- `max_results`: 1-100 range (Field ge=1, le=100)
- `timeout_seconds`: 1-300 range
- `impact_score`: 0.0-1.0 range
- `requests_per_minute`: default 60
- `max_tokens_per_request`: default 4096

**Relationships:**
- `AgentSession` references `AgentTrustLevel` and `AgentCapability`
- `AgentQuery` references `QueryType` and `ResponseFormat`
- `CapsuleAccess` links to `AgentTrustLevel`

**Issues:**
- No validation that `api_key_hash` is actually a valid hash format
- `allowed_capsule_types` accepts any strings - could be stricter
- Missing rate limit enforcement logic

**Improvements:**
- Add regex validation for `api_key_hash` format
- Validate `allowed_capsule_types` against `CapsuleType` enum
- Add session expiration validation logic
- Consider adding request signing for security

**Possibilities:**
- Enable multi-tenant agent deployments
- Add agent analytics and learning from query patterns
- Support for agent-to-agent communication protocols

---

### 3. forge-cascade-v2/forge/models/base.py

**Purpose:** Foundation classes including base model configuration, enums, mixins, and common response models.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `ForgeModel` | Base Pydantic model with common config (str_strip_whitespace, validate_assignment, etc.) |
| `TimestampMixin` | Mixin providing `created_at` and `updated_at` with Neo4j datetime conversion |
| `TrustLevel` (IntEnum) | Trust hierarchy: QUARANTINE=0, SANDBOX=40, STANDARD=60, TRUSTED=80, CORE=100 |
| `CapsuleType` (Enum) | Types: INSIGHT, DECISION, LESSON, WARNING, PRINCIPLE, MEMORY, KNOWLEDGE, CODE, CONFIG, TEMPLATE, DOCUMENT |
| `OverlayState` (Enum) | Lifecycle states: REGISTERED, LOADING, ACTIVE, DEGRADED, STOPPING, STOPPED, INACTIVE, QUARANTINED, ERROR |
| `OverlayPhase` (Enum) | Pipeline phases: VALIDATION, SECURITY, ENRICHMENT, PROCESSING, GOVERNANCE, FINALIZATION, NOTIFICATION |
| `ProposalStatus` (Enum) | Status: DRAFT, ACTIVE, VOTING, PASSED, REJECTED, EXECUTED, CANCELLED |
| `AuditOperation` (Enum) | Audit types: CREATE, READ, UPDATE, DELETE, EXECUTE, VOTE, QUARANTINE, RECOVER |
| `HealthStatus` (Enum) | Health values: HEALTHY, DEGRADED, UNHEALTHY |
| `HealthCheck` | Health check response with status, service, version, timestamp, details |
| `PaginatedResponse` | Generic pagination wrapper with items, total, page, page_size, has_more |
| `ErrorResponse` | Standard error with error code, message, details, correlation_id |
| `SuccessResponse` | Standard success with message and optional data |

**Utility Functions:**
- `convert_neo4j_datetime()`: Converts Neo4j DateTime to Python datetime (timezone-aware)
- `generate_id()`: Generates UUID string
- `generate_uuid()`: Generates UUID object

**Validation Rules:**
- `TrustLevel.from_value()`: Maps numeric value to appropriate trust level
- `TrustLevel.can_execute`: True if value > QUARANTINE
- `TrustLevel.can_vote`: True if value >= TRUSTED (80)
- `PaginatedResponse.total_pages`: Computed from total and page_size

**Relationships:** Base classes inherited by most other models.

**Issues:**
- **SECURITY FIX noted but inconsistency**: `TimestampMixin` still uses `datetime.utcnow` in default_factory while `convert_neo4j_datetime` uses `datetime.now(UTC)`
- `HealthCheck.timestamp` uses deprecated `datetime.utcnow`
- `PaginatedResponse.items` typed as `list[Any]` - loses type safety

**Improvements:**
- Fix all `datetime.utcnow` to `lambda: datetime.now(UTC)` for consistency
- Add generic type parameter to `PaginatedResponse[T]`
- Add `__str__` and `__repr__` methods to enums for better debugging
- Add validation that trust levels are within bounds

**Possibilities:**
- Add model versioning for API evolution
- Implement model serialization hooks for different backends
- Add audit trail mixin for change tracking

---

### 4. forge-cascade-v2/forge/models/capsule.py

**Purpose:** The atomic unit of knowledge in Forge with versioning, symbolic inheritance (lineage), semantic search, and integrity verification.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `IntegrityStatus` (Enum) | Status: UNVERIFIED, VALID, CORRUPTED, PENDING |
| `ContentBlock` | A block of content with type (text, code, markdown) and optional language |
| `CapsuleBase` | Base fields: content, type, title, summary, tags, metadata |
| `CapsuleCreate` | Creation schema with parent_id and evolution_reason |
| `CapsuleUpdate` | Update schema with optional fields |
| `Capsule` | Complete schema: id, version, owner_id, trust_level, parent_id, is_archived, view_count, fork_count |
| `CapsuleInDB` | Database schema with embedding, content_hash, integrity fields, signature fields, Merkle tree fields |
| `LineageNode` | Node in lineage tree with id, version, title, type, created_at, trust_level, depth |
| `DerivedFromRelation` | Metadata about DERIVED_FROM relationship |
| `CapsuleWithLineage` | Capsule with full lineage and children lists |
| `CapsuleSearchResult` | Search result with capsule, score (0-1), and highlights |
| `CapsuleFork` | Request to fork with parent_id, content, evolution_reason, inherit_metadata |
| `CapsuleStats` | Statistics: total_count, by_type, by_trust_level, average_lineage_depth, etc. |
| `IntegrityReport` | Verification report with hash validity, signature validity, merkle chain validity |
| `LineageIntegrityReport` | Integrity report for entire lineage chain |

**Validation Rules:**
- `content`: min_length=1, max_length=100000
- `title`: max_length=500
- `summary`: max_length=2000
- `tags`: max 20 items, normalized to lowercase
- `content_hash`: Must match SHA-256 pattern (64 hex chars)
- `merkle_root`: Must match SHA-256 pattern
- `parent_content_hash`: Must match SHA-256 pattern
- `embedding`: Valid dimensions {384, 768, 1024, 1536, 3072}, values in range [-10, 10]
- `score` (search result): 0.0-1.0 range

**Relationships:**
- `CapsuleCreate` extends `CapsuleBase`
- `Capsule` extends `CapsuleBase` + `TimestampMixin`
- `CapsuleInDB` extends `Capsule`
- `CapsuleWithLineage` extends `Capsule`
- References `CapsuleType`, `TrustLevel`, `IntegrityStatus`

**Issues:**
- `ContentBlock` model defined but not used in `CapsuleBase`
- No validation that `owner_id` is a valid user ID
- No validation that `parent_id` refers to existing capsule
- Signature fields exist but signing logic not in model
- `embedding` validation allows multiple dimension sizes but doesn't track which model created it

**Improvements:**
- Implement content block support in capsule content structure
- Add foreign key validation for owner_id and parent_id
- Add `compute_content_hash()` method to model
- Add `verify_signature()` method to model
- Track embedding model version/type
- Add content compression for large capsules

**Possibilities:**
- Full cryptographic signing with Ed25519
- Merkle tree lineage verification
- Content-addressable storage
- Differential content updates
- Multi-modal content (images, audio)

---

### 5. forge-cascade-v2/forge/models/events.py

**Purpose:** Event system for pub/sub messaging and cascade propagation across overlays.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `EventType` (Enum) | 50+ event types across categories: SYSTEM, CAPSULE, USER, OVERLAY, ML, SECURITY, IMMUNE, GOVERNANCE, PIPELINE, CASCADE |
| `EventPriority` (Enum) | Priorities: LOW, NORMAL, HIGH, CRITICAL |
| `Event` | Base event: id, type, source, payload, timestamp, correlation_id, priority, target_overlays, metadata |
| `EventSubscription` | Subscription: subscriber_id, event_types, event_patterns (wildcards), priority_filter, callback |
| `CascadeEvent` | Cascade propagation: source_overlay, insight_type, insight_data, hop_count, max_hops, visited_overlays, impact_score |
| `CascadeChain` | Complete cascade record: events list, completion status, outcomes |
| `EventHandlerResult` | Handler result: event_id, handler_id, success, output, error, processing_time_ms, triggered_events |
| `EventMetrics` | System metrics: totals, by_type, by_source, avg_processing_time, queue_size |
| `AuditEvent` | Audit log entry with actor, action, resource, old/new values, IP, user_agent |

**Validation Rules:**
- `hop_count`: ge=0
- `max_hops`: ge=1, default=5
- `impact_score`: 0.0-1.0 range
- `CascadeEvent.can_propagate`: hop_count < max_hops

**Relationships:**
- `Event` references `EventType` and `EventPriority`
- `EventSubscription` references `EventType` and `EventPriority`
- `CascadeEvent` uses `ForgeModel` base
- `CascadeChain` contains list of `CascadeEvent`
- `AuditEvent` references `EventType` and `EventPriority`

**Issues:**
- `Event.timestamp` uses deprecated `datetime.utcnow`
- `EventSubscription.callback` is string - could be more type-safe
- No validation that `source` is a valid overlay/component
- `event_patterns` wildcards mentioned but pattern matching logic not defined

**Improvements:**
- Replace all `datetime.utcnow` with timezone-aware datetimes
- Define callback signature interface
- Add event schema validation for payload
- Implement pattern matching for event_patterns
- Add event replay capability
- Add dead letter queue for failed events

**Possibilities:**
- Event sourcing for full system replay
- Cross-instance event federation
- Event-driven workflows
- Machine learning on event streams
- Real-time event dashboards

---

### 6. forge-cascade-v2/forge/models/governance.py

**Purpose:** Democratic decision-making with trust-weighted voting, Constitutional AI ethical review, and Ghost Council.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `ProposalType` (Enum) | Types: POLICY, SYSTEM, OVERLAY, CAPSULE, TRUST, CONSTITUTIONAL |
| `VoteChoice` (Enum) | Choices: APPROVE, REJECT, ABSTAIN (with FOR/AGAINST aliases) |
| `ProposalBase` | Base: title, description, type, action dict |
| `ProposalCreate` | Creation schema with voting_period_days, quorum_percent, pass_threshold |
| `Proposal` | Complete proposal with voting results, timestamps, timelock, constitutional review |
| `VoteCreate` | Vote creation with choice and optional reason |
| `Vote` | Complete vote with weight and delegation info |
| `VoteDelegation` | Delegation to another user with type filters and expiration |
| `EthicalConcern` | Constitutional AI concern with category, severity, description, recommendation |
| `ConstitutionalAnalysis` | Ethical review with scores (0-100), concerns list, recommendation |
| `PerspectiveType` (Enum) | Ghost Council perspectives: OPTIMISTIC, BALANCED, CRITICAL |
| `PerspectiveAnalysis` | Single perspective analysis |
| `GhostCouncilMember` | Council member definition with persona, weight, icon |
| `GhostCouncilVote` | Member vote with tri-perspective analysis |
| `GhostCouncilOpinion` | Collective council opinion with consensus and summaries |
| `GovernanceStats` | System statistics |

**Constants:**
- `VALID_PROPOSAL_ACTIONS`: Maps ProposalType to valid action types
- `REQUIRED_ACTION_FIELDS`: Maps action types to required fields

**Validation Rules:**
- `title`: min_length=5, max_length=200
- `description`: min_length=20, max_length=10000
- `voting_period_days`: 1-30
- `quorum_percent`: 0.01-1.0
- `pass_threshold`: 0.5-1.0
- `VoteChoice.from_string()`: Safe conversion with alias handling
- `ProposalCreate.validate_action_for_type()`: Validates action type matches proposal type
- Dangerous fields blocked: `__import__`, `eval`, `exec`, `compile`, `globals`, `locals`

**Relationships:**
- `Proposal` extends `ProposalBase` + `TimestampMixin`
- `Proposal` contains `ConstitutionalAnalysis` and `GhostCouncilOpinion`
- `Vote` extends `ForgeModel` + `TimestampMixin`
- `GhostCouncilOpinion` contains `GhostCouncilVote` list

**Issues:**
- `VoteDelegation.created_at` uses deprecated `datetime.utcnow`
- No validation that `proposer_id` exists
- No validation that `delegate_id` is different from `delegator_id`
- Circular delegation not prevented in model

**Improvements:**
- Add self-delegation prevention
- Add circular delegation detection
- Validate proposer exists and has sufficient trust
- Add proposal version history
- Add vote changing/updating mechanism

**Possibilities:**
- Quadratic voting support
- Multi-stage voting processes
- Cross-proposal dependencies
- Automated proposal execution
- Governance analytics dashboard

---

### 7. forge-cascade-v2/forge/models/graph_analysis.py

**Purpose:** Data structures for graph algorithm results including PageRank, centrality, community detection, and trust analysis.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `GraphBackend` (Enum) | Backends: GDS, CYPHER, NETWORKX |
| `AlgorithmType` (Enum) | Algorithms: PAGERANK, BETWEENNESS_CENTRALITY, CLOSENESS_CENTRALITY, DEGREE_CENTRALITY, EIGENVECTOR_CENTRALITY, COMMUNITY_LOUVAIN, COMMUNITY_LABEL_PROPAGATION, TRUST_TRANSITIVITY, SHORTEST_PATH |
| `NodeRanking` | Ranked node with score and rank |
| `NodeRankingResult` | Complete ranking result with algorithm, backend, rankings list, metadata |
| `CommunityMember` | Node within a community with centrality |
| `Community` | Detected community with members, density, modularity contribution, characterization |
| `CommunityDetectionResult` | Complete community detection result |
| `TrustPath` | Path through graph for trust computation with hop-by-hop trust values |
| `TrustTransitivityResult` | Trust propagation result between two nodes |
| `TrustInfluence` | Node's influence on trust propagation |
| `GraphMetrics` | Comprehensive graph statistics: size, structure, connectivity, trust metrics |
| `PageRankRequest` | Parameters for PageRank computation |
| `CentralityRequest` | Parameters for centrality computation |
| `CommunityDetectionRequest` | Parameters for community detection |
| `TrustTransitivityRequest` | Parameters for trust transitivity |
| `NodeSimilarityRequest` | Parameters for node similarity using GDS |
| `SimilarNode` | Similar node with score and shared neighbors |
| `NodeSimilarityResult` | Similarity computation result |
| `ShortestPathRequest` | Parameters for shortest path |
| `PathNode` | Node in a path |
| `ShortestPathResult` | Shortest path computation result |
| `GraphAlgorithmConfig` | Configuration for the graph algorithm provider |

**Validation Rules:**
- `damping_factor`: 0.0-1.0 (PageRank)
- `max_iterations`: 1-100
- `tolerance`: > 0.0
- `limit`: 1-1000 (various requests)
- `modularity`: -1.0 to 1.0
- `density`: 0.0-1.0
- `coverage`: 0.0-1.0
- `decay_rate`: 0.0-1.0 (trust transitivity)
- `max_hops`: 1-10 (trust transitivity)
- `similarity_cutoff`: 0.0-1.0

**Relationships:**
- Request models map to Result models
- All use `ForgeModel` base
- Results reference `AlgorithmType` and `GraphBackend`

**Issues:**
- `computed_at` fields use deprecated `datetime.utcnow`
- No validation that node_label/relationship_type exist in schema
- No caching key generation for algorithm results

**Improvements:**
- Add schema validation for node labels and relationship types
- Generate cache keys from request parameters
- Add progress reporting for long-running algorithms
- Add algorithm benchmarking data

**Possibilities:**
- Real-time graph streaming updates
- Incremental algorithm computation
- Algorithm recommendation engine
- Visual graph exploration
- Federated graph analysis across instances

---

### 8. forge-cascade-v2/forge/models/marketplace.py

**Purpose:** Data structures for the knowledge capsule marketplace.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `ListingStatus` (Enum) | Status: DRAFT, ACTIVE, SOLD, EXPIRED, CANCELLED |
| `LicenseType` (Enum) | Types: PERPETUAL, SUBSCRIPTION, USAGE, DERIVATIVE |
| `Currency` (Enum) | Currencies: FORGE, USD, SOL, ETH |
| `ListingVisibility` (Enum) | Visibility: PUBLIC, UNLISTED, PRIVATE |
| `PaymentMethod` (Enum) | Methods: PLATFORM, BLOCKCHAIN |
| `PaymentStatus` (Enum) | Status: PENDING, COMPLETED, FAILED, REFUNDED |
| `CapsuleListing` | Listing: capsule_id, seller_id, price, license, visibility, metadata, stats |
| `Purchase` | Purchase record with transaction details, revenue distribution |
| `Cart` | Shopping cart with items, currency validation |
| `CartItem` | Item in cart with listing reference and price |
| `License` | License granting access with permissions and usage tracking |
| `PriceSuggestion` | System-generated price with multipliers and context |
| `RevenueDistribution` | Revenue distribution: 70% seller, 15% lineage, 10% platform, 5% treasury |
| `MarketplaceStats` | Overall marketplace statistics |

**Validation Rules:**
- `price`: ge=0 (Decimal)
- `Cart.total`: Validates all items have same currency, raises ValueError if mixed
- `Cart.totals_by_currency`: Groups by currency for mixed cart handling
- License permissions: can_view, can_download, can_derive, can_resell

**Relationships:**
- `CapsuleListing` references capsule_id and seller_id
- `Purchase` links listing, capsule, buyer, seller
- `Cart` contains `CartItem` list
- `License` references purchase and capsule
- `RevenueDistribution` links to purchase

**Issues:**
- Using `Decimal` for prices but not all calculations may preserve precision
- No validation that capsule_id exists
- No validation that seller owns the capsule
- Currency conversion not handled

**Improvements:**
- Add capsule ownership validation
- Implement currency conversion
- Add escrow mechanism for purchases
- Add refund logic validation
- Add subscription renewal logic
- Consider using Decimal consistently

**Possibilities:**
- Bundle sales (multiple capsules)
- Auctions and bidding
- Dynamic pricing based on demand
- NFT-based licenses
- Cross-marketplace federation

---

### 9. forge-cascade-v2/forge/models/notifications.py

**Purpose:** Data structures for the webhook and notification system.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `NotificationEvent` (Enum) | Events: PROPOSAL_*, ISSUE_*, COUNCIL_*, CAPSULE_*, PEER_*, SYNC_*, ANOMALY_*, SYSTEM_*, USER_* |
| `NotificationPriority` (Enum) | Priorities: LOW, NORMAL, HIGH, CRITICAL |
| `DeliveryChannel` (Enum) | Channels: IN_APP, WEBHOOK, EMAIL, SLACK |
| `DigestFrequency` (Enum) | Frequencies: HOURLY, DAILY, WEEKLY |
| `WebhookSubscription` | Subscription: url, secret, events filter, state, stats |
| `Notification` | In-app notification with content, related entity, state |
| `WebhookDelivery` | Delivery attempt record with request/response details |
| `NotificationPreferences` | User preferences: channel preferences, mute settings, quiet hours, digest |
| `WebhookPayload` | Standard webhook payload format with signature |

**Validation Rules:**
- `quiet_hours_start`: 0-23 (hour)
- `quiet_hours_end`: 0-23 (hour)
- `message`: max_length=2000
- `title`: max_length=200
- `WebhookPayload.to_dict_for_signing()`: Provides consistent format for HMAC signing

**Relationships:**
- `WebhookSubscription` filters by `NotificationEvent` and `NotificationPriority`
- `Notification` references `NotificationEvent` and `NotificationPriority`
- `WebhookDelivery` references subscription and notification
- `NotificationPreferences` maps events to `DeliveryChannel` lists

**Issues:**
- `url` not validated as HTTPS (webhook security concern)
- `secret` not validated for minimum length/complexity
- No validation that quiet hours start < end
- `consecutive_failures` not used for automatic disabling

**Improvements:**
- Validate webhook URLs are HTTPS
- Enforce minimum secret length (e.g., 32 bytes)
- Handle quiet hours crossing midnight
- Auto-disable webhooks after N consecutive failures
- Add webhook URL verification challenge

**Possibilities:**
- Push notifications (mobile/browser)
- SMS notifications
- Integration with Slack/Discord bots
- Notification analytics
- AI-generated notification summaries

---

### 10. forge-cascade-v2/forge/models/overlay.py

**Purpose:** Overlay models for intelligent modules providing specialized functionality with WebAssembly isolation.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `Capability` (Enum) | 16 capabilities: NETWORK_ACCESS, DATABASE_READ/WRITE, EVENT_PUBLISH/SUBSCRIBE, CAPSULE_*, GOVERNANCE_*, USER_READ, SYSTEM_CONFIG, LLM_ACCESS |
| `CORE_OVERLAY_CAPABILITIES` | Pre-defined capability sets for core overlays |
| `OverlayMetrics` | Runtime metrics: executions, timing, resource usage, health |
| `FuelBudget` | Resource limits: max_fuel, max_memory_bytes, timeout_ms |
| `OverlayManifest` | Manifest: id, name, version, capabilities, dependencies, exports, fuel budgets, wasm path |
| `OverlayBase` | Base: name, description |
| `Overlay` | Complete overlay: state, trust_level, capabilities, dependencies, metrics, activation timestamps, wasm_hash |
| `OverlayExecution` | Execution record: input/output, success, timing, resource usage |
| `OverlayHealthCheck` | Health check result: level (L1-L4), healthy, message, details |
| `OverlayEvent` | Event published by/to overlay |

**Constants:**
- `CORE_OVERLAY_CAPABILITIES`: Maps overlay names to capability sets for 9 core overlays

**Validation Rules:**
- `version`: Pattern `^\d+\.\d+\.\d+$` (semantic version)
- `trust_required`: 0-100
- `max_fuel`: default 5,000,000
- `max_memory_bytes`: default 10MB
- `timeout_ms`: default 5000
- `OverlayMetrics.success_rate`: Computed from execution counts
- `Overlay.is_healthy`: Active + < 3 consecutive failures + < 10% error rate

**Relationships:**
- `Overlay` extends `OverlayBase` + `TimestampMixin`
- `Overlay` references `OverlayState`, `TrustLevel`, `Capability`
- `OverlayManifest` contains `FuelBudget` dict
- `Overlay` contains `OverlayMetrics`

**Issues:**
- `OverlayExecution.timestamp` uses deprecated `datetime.utcnow`
- No validation that wasm_path exists or is valid
- `source_hash` format not validated
- Capability conflicts not detected

**Improvements:**
- Validate wasm_path existence
- Validate source_hash format (SHA-256)
- Add capability conflict detection
- Add overlay version comparison
- Add dependency resolution validation

**Possibilities:**
- Hot-reload overlays without restart
- Overlay marketplace
- Overlay sandboxing with WebAssembly
- Cross-instance overlay sharing
- Overlay performance profiling

---

### 11. forge-cascade-v2/forge/models/query.py

**Purpose:** Knowledge query models for natural language to Cypher query compilation.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `QueryOperator` (Enum) | Operators: =, <>, >, <, >=, <=, CONTAINS, STARTS WITH, ENDS WITH, =~, IN, NOT IN, IS NULL, IS NOT NULL |
| `AggregationType` (Enum) | Aggregations: COUNT, SUM, AVG, MIN, MAX, COLLECT, COUNT_DISTINCT |
| `SortDirection` (Enum) | Directions: ASC, DESC |
| `QueryComplexity` (Enum) | Complexity: SIMPLE, MODERATE, COMPLEX, EXPENSIVE |
| `EntityRef` | Node reference: alias, label, properties, is_optional |
| `RelationshipRef` | Relationship reference: type, direction, hops, properties |
| `PathPattern` | Path pattern: source, relationship, target |
| `Constraint` | WHERE clause constraint: field, operator, value |
| `Aggregation` | RETURN aggregation: function, field, alias |
| `OrderBy` | Ordering: field, direction |
| `QueryIntent` | Parsed intent: entities, paths, constraints, return fields, aggregations, ordering |
| `CompiledQuery` | Compiled Cypher: query string, parameters, explanation, metadata |
| `QueryValidation` | Validation result: is_valid, errors, warnings, estimated_cost |
| `QueryResultRow` | Single result row |
| `QueryResult` | Complete result: rows, answer, confidence, timing |
| `QueryError` | Error with suggestion |
| `SchemaProperty` | Schema property: name, type, description, example, indexed |
| `SchemaNodeLabel` | Node label schema: label, description, properties |
| `SchemaRelationship` | Relationship schema: type, labels, properties, bidirectional |
| `GraphSchema` | Complete schema with helper methods |
| `NaturalLanguageQueryRequest` | NL query request with options |
| `DirectCypherRequest` | Direct Cypher request |
| `QueryHistoryEntry` | Query history with feedback |
| `QuerySuggestion` | Suggested query |

**Validation Rules:**
- `question`: min_length=3, max_length=1000
- `cypher`: min_length=5, max_length=5000
- `timeout_ms`: 1000-120000 (SECURITY FIX: reduced from 5min to 2min)
- `limit`: 1-1000
- `trust_filter`: 0-100
- `feedback_score`: 1-5

**Relationships:**
- `QueryIntent` contains `EntityRef`, `PathPattern`, `Constraint`, `Aggregation`, `OrderBy`
- `QueryResult` contains `CompiledQuery` and `QueryResultRow` list
- `GraphSchema` contains `SchemaNodeLabel` and `SchemaRelationship` lists

**Issues:**
- `get_default_schema()` hardcodes schema - should be configurable
- No Cypher injection protection in model (should be in service)
- `RelationshipRef.direction` uses string pattern instead of enum
- `QueryHistoryEntry` feedback not typed strongly

**Improvements:**
- Add Cypher syntax validation in model
- Use enum for relationship direction
- Add query template system
- Add query caching hints
- Validate queries against schema in model

**Possibilities:**
- Query auto-completion
- Query recommendation based on history
- Visual query builder integration
- Query performance optimization suggestions
- Federated queries across instances

---

### 12. forge-cascade-v2/forge/models/semantic_edges.py

**Purpose:** Bidirectional semantic relationships between capsules beyond simple parent-child derivation.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `SemanticRelationType` (Enum) | Types: RELATED_TO, CONTRADICTS (bidirectional), SUPPORTS, ELABORATES, SUPERSEDES, REFERENCES, IMPLEMENTS, EXTENDS (directed) |
| `ContradictionSeverity` (Enum) | Severities: LOW, MEDIUM, HIGH, CRITICAL |
| `ContradictionStatus` (Enum) | Status: UNRESOLVED, UNDER_REVIEW, RESOLVED, ACCEPTED |
| `EvidenceType` (Enum) | Types: EMPIRICAL, THEORETICAL, CITATION, EXAMPLE, CONSENSUS |
| `SemanticEdgeBase` | Base: source_id, target_id, relationship_type, confidence, reason, auto_detected |
| `SemanticEdgeCreate` | Creation schema with properties validation |
| `SemanticEdge` | Complete edge with created_by and computed bidirectional flag |
| `SemanticEdgeWithNodes` | Edge with source/target node info |
| `ContradictionEdge` | Specialized edge with severity and resolution properties |
| `SupportEdge` | Specialized edge with evidence type and strength |
| `SupersedesEdge` | Specialized edge with deprecation info |
| `SemanticNeighbor` | Connected neighbor capsule |
| `SemanticDistance` | Distance between capsules with path |
| `ContradictionCluster` | Cluster of contradicting capsules |
| `RelationshipClassification` | LLM classification result |
| `SemanticAnalysisRequest` | Request for semantic analysis |
| `SemanticAnalysisResult` | Analysis result with classifications and edges |
| `SemanticEdgeQuery` | Query parameters for edges |
| `ContradictionQuery` | Query for contradictions |

**Validation Rules:**
- `confidence`: 0.0-1.0
- `reason`: max_length=1000
- `SemanticEdgeCreate.validate_properties()`: Adds defaults based on relationship type
- `SemanticRelationType.is_bidirectional`: RELATED_TO and CONTRADICTS
- `SemanticRelationType.inverse`: Returns self for bidirectional, None for directed

**Relationships:**
- `SemanticEdge` extends `SemanticEdgeBase` + `TimestampMixin`
- `ContradictionEdge`, `SupportEdge`, `SupersedesEdge` extend `SemanticEdge`
- `SemanticAnalysisResult` contains `RelationshipClassification` and `SemanticEdge` lists
- `ContradictionCluster` contains `SemanticEdge` list

**Issues:**
- `ContradictionCluster.detected_at` uses deprecated `datetime.utcnow`
- No validation that source_id != target_id (self-loops)
- Specialized edge classes use property getters that could fail on missing keys
- `SemanticEdge.__init__` modifies `bidirectional` which could cause issues

**Improvements:**
- Add self-loop prevention
- Use model_validator for bidirectional computation
- Add safer property access with defaults
- Add edge conflict detection (e.g., SUPPORTS and CONTRADICTS same pair)
- Add edge merging for duplicate detection

**Possibilities:**
- Semantic graph visualization
- Contradiction resolution workflows
- Evidence chain analysis
- Semantic similarity scoring
- Knowledge gap detection

---

### 13. forge-cascade-v2/forge/models/temporal.py

**Purpose:** Track knowledge and trust evolution over time with version history, snapshots, and reconstruction.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `ChangeType` (Enum) | Types: CREATE, UPDATE, FORK, MERGE, RESTORE, MIGRATION |
| `SnapshotType` (Enum) | Types: FULL, DIFF, REFERENCE |
| `TrustChangeType` (Enum) | Types: ESSENTIAL, DERIVED |
| `TimeGranularity` (Enum) | Granularities: HOUR, DAY, WEEK, MONTH |
| `VersionDiff` | Difference between versions: added/removed lines, modified sections |
| `CapsuleVersionBase` | Base: capsule_id, version_number, change_type, created_by |
| `CapsuleVersionCreate` | Creation schema with content or diff |
| `CapsuleVersion` | Complete version with snapshot, hash, lineage |
| `CapsuleVersionWithContent` | Version with reconstructed content |
| `VersionHistory` | Complete history with versions list and metadata |
| `TrustSnapshotBase` | Base: entity_id, entity_type, trust_value |
| `TrustSnapshotCreate` | Creation schema with reason and evidence |
| `TrustSnapshot` | Complete snapshot with change classification and reconstruction hints |
| `TrustTimeline` | Trust evolution with aggregated stats |
| `TrustSnapshotCompressor` | Utility class for classifying and compressing snapshots |
| `VersioningPolicy` | Policy for full snapshots vs diffs |
| `GraphSnapshot` | Point-in-time graph metrics |
| `GraphEvolution` | Graph changes over time with trends |
| `TemporalQuery` | Base temporal query |
| `VersionHistoryQuery` | Query for capsule versions |
| `TrustTimelineQuery` | Query for trust evolution |
| `CapsuleAtTimeQuery` | Query for capsule state at time |
| `GraphSnapshotQuery` | Query for graph snapshots |
| `VersionComparison` | Comparison between versions |

**Key Features:**
- `TrustSnapshotCompressor.ESSENTIAL_REASONS`: Preserves full details for important changes
- `TrustSnapshotCompressor.classify()`: Classifies changes as essential or derived
- `TrustSnapshotCompressor.estimate_storage()`: Estimates compression savings
- `VersioningPolicy.should_full_snapshot()`: Determines when to create full snapshot
- `CapsuleVersion.compute_hash()`: SHA-256 content hashing

**Validation Rules:**
- `trust_value`: 0-100
- `snapshot_every_n_changes`: ge=1
- `compact_after_days`: ge=1
- `keep_snapshots_for_days`: ge=1
- `max_diff_chain_length`: ge=1
- `max_diff_size_bytes`: ge=100
- `TrustSnapshot.is_significant`: abs(delta) > 5

**Relationships:**
- `CapsuleVersion` extends `CapsuleVersionBase` + `TimestampMixin`
- `TrustSnapshot` extends `TrustSnapshotBase` + `TimestampMixin`
- `VersionHistory` contains `CapsuleVersion` list
- `TrustTimeline` contains `TrustSnapshot` list
- `GraphEvolution` contains `GraphSnapshot` list

**Issues:**
- `VersioningPolicy.should_compact()` uses deprecated `datetime.utcnow`
- No validation that version_number follows semantic versioning
- `VersionDiff` doesn't validate that modifications are consistent

**Improvements:**
- Add semantic version validation
- Add diff application/reconstruction logic in model
- Add version branching support
- Add conflict detection for concurrent modifications
- Add archival policy for old versions

**Possibilities:**
- Time-travel queries (capsule at any point in time)
- Trend analysis and prediction
- Anomaly detection in trust changes
- Version rollback mechanisms
- Compliance audit trails

---

### 14. forge-cascade-v2/forge/models/user.py

**Purpose:** User entities with authentication, trust scoring (Trust Flame), and role-based access control.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `Capability` (Enum) | User capabilities for access control (13 capabilities) |
| `UserRole` (Enum) | Roles: USER, MODERATOR, ADMIN, SYSTEM |
| `AuthProvider` (Enum) | Providers: LOCAL, GOOGLE, GITHUB, DISCORD, WEB3 |
| `KeyStorageStrategy` (Enum) | Ed25519 key storage: SERVER_CUSTODY, CLIENT_ONLY, PASSWORD_DERIVED, NONE |
| `UserBase` | Base: username, email, display_name, bio, avatar_url |
| `UserCreate` | Creation with password (8-72 chars, bcrypt limit) |
| `UserUpdate` | Update schema for profile fields |
| `UserPasswordChange` | Password change with current/new |
| `User` | Complete user: role, trust_flame, is_active, is_verified, auth_provider, metadata |
| `UserInDB` | Database schema with password_hash, refresh_token (hashed), lockout, signing keys |
| `UserPublic` | Public profile without sensitive data |
| `LoginRequest` | Login with username_or_email and password |
| `Token` | JWT token response: access_token, refresh_token, token_type, expires_in |
| `TokenPayload` | JWT claims: sub, username, role, trust_flame, exp, iat, jti, type |
| `RefreshTokenRequest` | Refresh token request |
| `TrustFlameAdjustment` | Trust adjustment record |
| `TrustFlameReason` (Enum) | Adjustment reasons: SUCCESSFUL_OPERATION, FAILED_OPERATION, etc. |
| `UserStats` | User statistics with history |

**Validation Rules:**
- `username`: 3-50 chars, pattern `^[a-zA-Z0-9_-]+$`
- `password`: 8-72 chars (SECURITY FIX: bcrypt truncation limit)
- Password strength: must contain uppercase, lowercase, digit
- `avatar_url`: Must be http or https (SECURITY FIX: prevents XSS via javascript: URIs)
- `trust_flame`: 0-100
- `User.trust_level`: Computed from trust_flame using TrustLevel.from_value()

**Relationships:**
- `User` extends `UserBase` + `TimestampMixin`
- `UserInDB` extends `User`
- `User` references `UserRole`, `AuthProvider`, `TrustLevel`
- `UserStats` contains `TrustFlameAdjustment` list

**Issues:**
- `TrustFlameAdjustment.timestamp` uses deprecated `datetime.utcnow`
- `Capability` enum in user.py duplicates/conflicts with `Capability` in overlay.py
- No email validation beyond Pydantic's EmailStr
- No username uniqueness validation in model (database concern)

**Improvements:**
- Rename one of the `Capability` enums to avoid confusion
- Add email verification token model
- Add password reset token model
- Add 2FA/MFA support models
- Add session management models

**Possibilities:**
- OAuth2 flow integration
- Passwordless authentication
- Biometric authentication
- SSO federation
- Hierarchical permissions

---

## Virtuals Protocol Integration Models

### 15. forge_virtuals_integration/forge/virtuals/models/__init__.py

**Purpose:** Central export module for Virtuals Protocol integration models.

**Models Exported:**
- Base: `TokenizationStatus`, `AgentStatus`, `ACPPhase`, `ACPJobStatus`, `RevenueType`, `VirtualsBaseModel`, `WalletInfo`, `TokenInfo`, `TransactionRecord`, `RevenueRecord`, `BridgeRequest`
- Agent: `AgentPersonality`, `WorkerDefinition`, `AgentGoals`, `AgentMemoryConfig`, `ForgeAgentCreate`, `ForgeAgent`, `AgentUpdate`, `AgentStats`, `AgentListResponse`
- ACP: `JobOffering`, `ACPMemo`, `ACPJob`, `ACPJobCreate`, `ACPNegotiationTerms`, `ACPDeliverable`, `ACPEvaluation`, `ACPDispute`, `ACPRegistryEntry`, `ACPStats`
- Tokenization: `TokenizableEntityType`, `TokenLaunchType`, `GenesisTier`, `TokenDistribution`, `RevenueShare`, `TokenizationRequest`, `TokenizedEntity`, `ContributionRecord`, `TokenHolderGovernanceVote`, `TokenHolderProposal`, `BondingCurveContribution`

---

### 16. forge_virtuals_integration/forge/virtuals/models/acp.py

**Purpose:** Agent Commerce Protocol (ACP) models for secure, verifiable commerce between AI agents.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `JobOffering` | Service offering: provider, service type, pricing, constraints, availability |
| `ACPMemo` | Cryptographically signed memo with content_hash and nonce |
| `ACPJob` | Complete job: participants, phases, memos, escrow, deliverables, dispute handling |
| `ACPJobCreate` | Job creation schema |
| `ACPNegotiationTerms` | Proposed terms during negotiation |
| `ACPDeliverable` | Deliverable submission |
| `ACPEvaluation` | Evaluation result with requirements tracking |
| `ACPDispute` | Dispute with evidence |
| `ACPRegistryEntry` | Agent registry entry with reputation |
| `ACPStats` | ACP activity statistics |

**Validation Rules:**
- `base_fee_virtual`: ge=0
- `max_execution_time_seconds`: default 300
- `min_buyer_trust_score`: 0.0-1.0
- `ACPMemo.nonce`: For replay attack prevention (SECURITY FIX)
- `ACPJob.advance_to_phase()`: Validates sequential phase progression
- `ACPJob.is_timed_out()`: Checks phase-specific timeouts

**Relationships:**
- `ACPJob` extends `VirtualsBaseModel`
- `ACPJob` contains multiple `ACPMemo` instances
- `ACPRegistryEntry` contains `JobOffering` list

**Issues:**
- `created_at`/`updated_at` use deprecated `datetime.utcnow`
- No signature verification logic in model
- `content_hash` format not validated
- Escrow amount calculations not validated

**Improvements:**
- Add signature verification method
- Validate content_hash format (SHA-256)
- Add escrow amount validation
- Add dispute resolution logic
- Add payment verification

**Possibilities:**
- Multi-agent job workflows
- Reputation-based pricing
- Automated dispute resolution
- Cross-chain settlements
- Job templates and automation

---

### 17. forge_virtuals_integration/forge/virtuals/models/agent.py

**Purpose:** AI agent models for the Virtuals Protocol GAME framework integration.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `AgentPersonality` | Personality: traits, communication style, expertise, guidelines |
| `WorkerDefinition` | GAME worker: functions, state schema, concurrency |
| `AgentGoals` | Goals: primary, secondary, constraints, success metrics |
| `AgentMemoryConfig` | Memory config: long-term, retention, working memory, sync |
| `ForgeAgentCreate` | Creation schema: identity, Forge integration, workers, tokenization |
| `ForgeAgent` | Complete agent: GAME integration, blockchain state, tokenization, metrics |
| `AgentUpdate` | Update schema for mutable fields |
| `AgentStats` | Aggregated statistics |
| `AgentListResponse` | Paginated list response |

**Key Features:**
- `AgentPersonality.to_game_prompt()`: Generates GAME framework prompt
- `ForgeAgent.is_operational()`: Checks operational status
- `ForgeAgent.is_tokenized()`: Checks tokenization status
- `ForgeAgent.get_wallet()`: Gets wallet by chain

**Validation Rules:**
- `name`: 3-64 chars
- `token_symbol`: max 10 chars, uppercase alphanumeric
- `initial_virtual_stake`: ge=100.0
- `trust_score`: 0.0-1.0

**Relationships:**
- `ForgeAgentCreate` contains `AgentPersonality`, `AgentGoals`, `AgentMemoryConfig`, `WorkerDefinition` list
- `ForgeAgent` extends `VirtualsBaseModel`
- `ForgeAgent` contains `WalletInfo` dict and `TokenInfo`

**Issues:**
- `api_access_token` stored in model - security concern
- No validation of `forge_overlay_id` existence
- `last_active_at` tracking logic not defined

**Improvements:**
- Remove or secure `api_access_token`
- Add overlay existence validation
- Add worker capability validation
- Add agent health monitoring

**Possibilities:**
- Multi-chain agent deployment
- Agent collaboration networks
- Autonomous agent governance
- Agent skill marketplace
- Agent personality evolution

---

### 18. forge_virtuals_integration/forge/virtuals/models/base.py

**Purpose:** Fundamental data structures for the Virtuals Protocol integration layer.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `TokenizationStatus` (Enum) | Status: NOT_TOKENIZED, PENDING, BONDING, GRADUATED, BRIDGED, FAILED, REVOKED |
| `AgentStatus` (Enum) | Status: PROTOTYPE, SENTIENT, SUSPENDED, TERMINATED |
| `ACPPhase` (Enum) | Phases: REQUEST, NEGOTIATION, TRANSACTION, EVALUATION |
| `ACPJobStatus` (Enum) | Status: OPEN, NEGOTIATING, IN_PROGRESS, DELIVERED, EVALUATING, COMPLETED, DISPUTED, CANCELLED, EXPIRED |
| `RevenueType` (Enum) | Types: INFERENCE_FEE, SERVICE_FEE, GOVERNANCE_REWARD, TOKENIZATION_FEE, TRADING_FEE, BRIDGE_FEE |
| `VirtualsBaseModel` | Base model with id, timestamps, metadata |
| `WalletInfo` | Wallet: address, chain, type, token-bound info, balance |
| `TokenInfo` | Token: address, symbol, supply, liquidity, graduation progress |
| `TransactionRecord` | Transaction: hash, block, addresses, value, gas, status |
| `RevenueRecord` | Revenue: type, amount, source, beneficiaries, distribution |
| `BridgeRequest` | Cross-chain bridge request |

**Validation Rules:**
- `WalletInfo.address`: EVM addresses 42 chars, Solana 32-44 chars
- `bonding_curve_progress`: 0.0-1.0
- `total_supply`: default 1 billion

**Relationships:**
- All other Virtuals models extend or reference these base types
- `WalletInfo` may be token-bound (ERC-6551)
- `TransactionRecord` links to Forge entities

**Issues:**
- `created_at`/`updated_at` use deprecated `datetime.utcnow`
- `WalletInfo.balance_virtual` is float - should use Decimal for precision
- No checksum validation for EVM addresses

**Improvements:**
- Add EVM address checksum validation
- Use Decimal for financial values
- Add multi-sig wallet support
- Add transaction confirmation tracking

**Possibilities:**
- Cross-chain identity
- Wallet abstraction
- Gas sponsorship
- Account recovery

---

### 19. forge_virtuals_integration/forge/virtuals/models/tokenization.py

**Purpose:** Opt-in tokenization of Forge entities (Capsules, Overlays, Agents) on Virtuals Protocol.

**Models Defined:**

| Model | Description |
|-------|-------------|
| `TokenizableEntityType` (Enum) | Types: CAPSULE, OVERLAY, AGENT, CAPSULE_COLLECTION, GOVERNANCE_PROPOSAL |
| `TokenLaunchType` (Enum) | Types: STANDARD (42K), GENESIS (presale) |
| `GenesisTier` (Enum) | Tiers: TIER_1 (21K), TIER_2 (42K), TIER_3 (100K) |
| `TokenDistribution` | Distribution: 60% public, 35% treasury, 5% LP, optional creator |
| `RevenueShare` | Revenue: 30% creator, 20% contributors, 50% treasury, buyback settings |
| `TokenizationRequest` | Request: entity, token config, launch type, distribution, revenue, governance |
| `TokenizedEntity` | Tokenized entity: token info, bonding state, graduation, holders, revenue, governance |
| `ContributionRecord` | Contribution to entity with validation and rewards |
| `TokenHolderGovernanceVote` | Token holder vote |
| `TokenHolderProposal` | Holder governance proposal |
| `BondingCurveContribution` | Bonding curve contribution record |

**Validation Rules:**
- `TokenDistribution`: Total allocations <= 100%
- `token_symbol`: Uppercase alphanumeric
- `initial_stake_virtual`: ge=100.0
- `governance_quorum_percent`: 1.0-100.0
- `validation_score`: 0.0-1.0
- `reward_share_percent`: 0.0-100.0

**Key Features:**
- `TokenizedEntity.is_graduated()`: Status check
- `TokenizedEntity.graduation_progress()`: Progress calculation with tier-specific thresholds

**Relationships:**
- `TokenizedEntity` extends `VirtualsBaseModel`
- `TokenizedEntity` contains `TokenInfo`, `TokenDistribution`, `RevenueShare`
- `TokenHolderProposal` references `TokenizedEntity`
- `ContributionRecord` links to entity and NFT

**Issues:**
- Uses string for `entity_type` instead of `TokenizableEntityType` enum
- `genesis_tier` comparison uses `GenesisTier.TIER_1` without proper enum import
- No validation that entity exists
- Revenue distribution sums not validated

**Improvements:**
- Use proper enum types throughout
- Validate revenue distribution percentages sum correctly
- Add entity existence validation
- Add contribution validation workflow
- Add vesting schedule support

**Possibilities:**
- Fractional ownership
- Revenue streaming
- Governance delegation
- Token buyback automation
- Cross-entity token swaps

---

## Issues Found

| Severity | File | Issue | Suggested Fix |
|----------|------|-------|---------------|
| Medium | base.py | `TimestampMixin` uses `datetime.utcnow` | Replace with `lambda: datetime.now(UTC)` |
| Medium | events.py | `Event.timestamp` uses deprecated `datetime.utcnow` | Use timezone-aware datetime |
| Medium | governance.py | `VoteDelegation.created_at` uses deprecated datetime | Use timezone-aware datetime |
| Medium | temporal.py | `VersioningPolicy.should_compact()` uses deprecated datetime | Use timezone-aware datetime |
| Medium | user.py | `TrustFlameAdjustment.timestamp` uses deprecated datetime | Use timezone-aware datetime |
| Medium | acp.py | `created_at`/`updated_at` use deprecated datetime | Use timezone-aware datetime |
| Low | user.py, overlay.py | Duplicate `Capability` enum | Rename to `UserCapability` and `OverlayCapability` |
| Medium | marketplace.py | Mixed Decimal/float for financial values | Use Decimal consistently |
| High | virtuals/base.py | `balance_virtual` is float, not Decimal | Use Decimal for financial precision |
| Medium | capsule.py | `ContentBlock` defined but not used | Implement or remove |
| Low | capsule.py | No foreign key validation for owner_id | Add validation in service layer |
| Medium | notifications.py | Webhook URL not validated as HTTPS | Add URL scheme validation |
| Low | semantic_edges.py | No self-loop prevention | Add source_id != target_id validation |
| Medium | agent.py | `api_access_token` stored in model | Move to secure storage |

---

## Improvements Identified

| Priority | File | Improvement | Benefit |
|----------|------|-------------|---------|
| High | All files | Replace datetime.utcnow with timezone-aware | Consistency and deprecation compliance |
| High | marketplace.py, virtuals/* | Use Decimal for all financial values | Financial precision |
| High | capsule.py | Add signature verification methods | Enable cryptographic integrity |
| Medium | base.py | Make PaginatedResponse generic | Type safety |
| Medium | governance.py | Add circular delegation prevention | Prevent infinite loops |
| Medium | overlay.py | Validate wasm_path and source_hash | Security validation |
| Medium | query.py | Add Cypher syntax validation | Prevent invalid queries |
| Medium | notifications.py | Auto-disable after N consecutive failures | Reliability |
| Low | All files | Add __str__ and __repr__ to enums | Better debugging |
| Low | user.py, overlay.py | Rename duplicate Capability enums | Clarity |

---

## Data Model Relationships

```
                                    ForgeModel (base.py)
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
         TimestampMixin              [Enums]                    [Response Models]
              |                    TrustLevel                   HealthCheck
              |                    CapsuleType                  PaginatedResponse
              |                    OverlayState                 ErrorResponse
              |                    ProposalStatus               SuccessResponse
              |
    +---------+---------+------------------+------------------+
    |         |         |                  |                  |
  User     Capsule   Overlay           Proposal             Event
    |         |         |                  |                  |
    |    CapsuleInDB  OverlayManifest     Vote          CascadeEvent
    |         |         |                  |
 UserInDB    |    OverlayMetrics    ConstitutionalAnalysis
    |         |                            |
UserPublic   +-> SemanticEdge       GhostCouncilOpinion
              |
              +-> CapsuleWithLineage
              |
              +-> LineageNode


                              VirtualsBaseModel (virtuals/base.py)
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
         ForgeAgent                   ACPJob                   TokenizedEntity
              |                           |                           |
    +----+----+----+             +--------+--------+          +-------+-------+
    |    |    |    |             |        |        |          |       |       |
WalletInfo TokenInfo  AgentPersonality   ACPMemo   JobOffering  TokenInfo  RevenueShare
```

---

## Validation Rules Summary

| Category | Rule | Files |
|----------|------|-------|
| String Length | username: 3-50 chars | user.py |
| String Length | password: 8-72 chars (bcrypt limit) | user.py |
| String Length | content: 1-100000 chars | capsule.py |
| String Length | title: max 500 chars | capsule.py |
| Numeric Range | trust_flame: 0-100 | user.py, capsule.py |
| Numeric Range | confidence: 0.0-1.0 | semantic_edges.py, query.py |
| Numeric Range | damping_factor: 0.0-1.0 | graph_analysis.py |
| Pattern | SHA-256 hash: 64 hex chars | capsule.py |
| Pattern | semantic version: ^\d+\.\d+\.\d+$ | overlay.py |
| Pattern | username: ^[a-zA-Z0-9_-]+$ | user.py |
| URL Scheme | avatar_url: http/https only | user.py |
| Enum Validation | VoteChoice.from_string() | governance.py |
| Action Validation | ProposalCreate.validate_action_for_type() | governance.py |
| Embedding | Valid dimensions: {384, 768, 1024, 1536, 3072} | capsule.py |
| Currency | Cart.total validates same currency | marketplace.py |
| Distribution | Total allocations <= 100% | tokenization.py |

---

## Model Count Summary

| File | Model Count | Enum Count |
|------|-------------|------------|
| base.py (cascade) | 6 | 8 |
| agent_gateway.py | 9 | 4 |
| capsule.py | 14 | 1 |
| events.py | 8 | 2 |
| governance.py | 15 | 3 |
| graph_analysis.py | 19 | 2 |
| marketplace.py | 10 | 6 |
| notifications.py | 6 | 4 |
| overlay.py | 9 | 1 |
| query.py | 21 | 4 |
| semantic_edges.py | 17 | 4 |
| temporal.py | 18 | 4 |
| user.py | 15 | 5 |
| base.py (virtuals) | 6 | 5 |
| acp.py | 10 | 0 |
| agent.py | 9 | 0 |
| tokenization.py | 10 | 3 |
| **Total** | **192** | **51** |

---

*Analysis completed: 2026-01-10*
*Total Files Analyzed: 19*
*Total Models Documented: 192*
*Total Enums Documented: 51*
