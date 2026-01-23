# Forge V3 - Services Analysis

## Category: Business Logic Services
## Status: Analyzed
## Last Updated: 2026-01-10

---

## Files in this Category (16 files)

| # | File | Status | Summary |
|---|------|--------|---------|
| 1 | `forge-cascade-v2/forge/services/__init__.py` | Analyzed | Module exports and public API surface |
| 2 | `forge-cascade-v2/forge/services/agent_gateway.py` | Analyzed | AI agent access gateway with trust-based controls |
| 3 | `forge-cascade-v2/forge/services/embedding.py` | Analyzed | Vector embedding generation for semantic search |
| 4 | `forge-cascade-v2/forge/services/ghost_council.py` | Analyzed | AI advisory board for governance proposals |
| 5 | `forge-cascade-v2/forge/services/init.py` | Analyzed | Service initialization and lifecycle management |
| 6 | `forge-cascade-v2/forge/services/llm.py` | Analyzed | LLM integration for multiple providers |
| 7 | `forge-cascade-v2/forge/services/marketplace.py` | Analyzed | Capsule marketplace with listings, purchases, licensing |
| 8 | `forge-cascade-v2/forge/services/notifications.py` | Analyzed | Multi-channel notification delivery with webhooks |
| 9 | `forge-cascade-v2/forge/services/pricing_engine.py` | Analyzed | Trust-based pricing algorithm for capsules |
| 10 | `forge-cascade-v2/forge/services/query_cache.py` | Analyzed | Redis-backed caching for NL-to-Cypher queries |
| 11 | `forge-cascade-v2/forge/services/query_compiler.py` | Analyzed | Natural language to Cypher query compilation |
| 12 | `forge-cascade-v2/forge/services/scheduler.py` | Analyzed | Background task scheduling with asyncio |
| 13 | `forge-cascade-v2/forge/services/search.py` | Analyzed | Semantic, keyword, and hybrid search |
| 14 | `forge-cascade-v2/forge/services/semantic_edge_detector.py` | Analyzed | Automatic semantic relationship detection |
| 15 | `forge_virtuals_integration/forge/virtuals/revenue/service.py` | Analyzed | Revenue management for Virtuals integration |
| 16 | `forge_virtuals_integration/forge/virtuals/tokenization/service.py` | Analyzed | Entity tokenization lifecycle management |

---

## Detailed Analysis

### 1. `forge-cascade-v2/forge/services/__init__.py`

**Purpose:** Module initialization file that exports the public API surface for all services. Acts as a central import point for embedding, LLM, search, Ghost Council, scheduler, and query cache services.

**Key Exports:**
- `EmbeddingService`, `EmbeddingConfig`, `EmbeddingProvider`, `EmbeddingResult`
- `LLMService`, `LLMConfig`, `LLMProvider`, `LLMMessage`, `LLMResponse`
- `SearchService`, `SearchMode`, `SearchFilters`, `SearchRequest`, `SearchResponse`
- `GhostCouncilService`, `GhostCouncilConfig`, `SeriousIssue`, `IssueSeverity`
- `BackgroundScheduler`, `ScheduledTask`, `SchedulerStats`
- `QueryCache`, `InMemoryQueryCache`, `CachedQueryResult`

**Dependencies:** All internal service modules

**State Management:** N/A - re-exports only

**Issues:** None identified

**Improvements:** None needed - well-organized exports

**Possibilities:** Could add version information or feature flags for service availability

---

### 2. `forge-cascade-v2/forge/services/agent_gateway.py`

**Purpose:** Provides AI agents with programmatic access to the knowledge graph through session management, query execution, rate limiting, and trust-based access control.

**Key Methods:**
```python
async def create_session(agent_name: str, owner_user_id: str, trust_level: AgentTrustLevel, ...) -> tuple[AgentSession, str]
async def authenticate(api_key: str) -> AgentSession | None
async def execute_query(session: AgentSession, query: AgentQuery) -> QueryResult
async def create_capsule(session: AgentSession, request: AgentCapsuleCreation) -> dict[str, Any]
async def stream_query(session: AgentSession, query: AgentQuery) -> AsyncIterator[StreamChunk]
async def get_stats() -> GatewayStats
```

**Dependencies:**
- `forge.models.agent_gateway` - Data models
- `forge.models.capsule` - TrustLevel enum

**State Management:**
- In-memory session storage with bounded caches (SECURITY FIX: LRU eviction to prevent DoS)
- API key hash mapping for authentication
- Rate limit tracking per session
- Query result caching (OrderedDict for LRU)

**Issues:**
- In-memory storage would lose state on restart (noted as "would be Redis in production")

**Improvements:**
- Implement Redis-backed session storage for production
- Add session persistence across restarts

**Possibilities:**
- WebSocket support for real-time agent queries
- Multi-tenant agent isolation

**Security Notes:**
- SECURITY FIX (Audit 4 - H10): Bounded cache sizes to prevent memory exhaustion DoS
- Comprehensive Cypher validation to prevent injection via Unicode homoglyphs, DETACH DELETE, CALL procedures

---

### 3. `forge-cascade-v2/forge/services/embedding.py`

**Purpose:** Generates vector embeddings for semantic search across capsules. Supports multiple providers (OpenAI, Sentence Transformers, Mock) with caching for cost optimization.

**Key Methods:**
```python
async def embed(text: str) -> EmbeddingResult
async def embed_batch(texts: list[str], show_progress: bool = False) -> list[EmbeddingResult]
async def cache_stats() -> dict[str, Any]
async def clear_cache() -> None
```

**Dependencies:**
- `httpx` - For OpenAI API calls
- `sentence_transformers` - Optional local embeddings
- `structlog` - Logging

**State Management:**
- Thread-safe in-memory cache with async locks (SECURITY FIX: Audit 3)
- Configurable cache size (default 50,000 entries for cost optimization)
- Provider instances with lazy HTTP client initialization

**Issues:**
- Large cache sizes may consume significant memory

**Improvements:**
- Add persistent cache (Redis/disk) for cross-restart caching
- Implement cache warming strategies

**Possibilities:**
- Support for more embedding providers (Cohere, Voyage)
- Adaptive dimension selection based on use case

**Security Notes:**
- SECURITY FIX (Audit 4 - H24): API keys loaded from env, redacted in logs/repr
- SECURITY FIX (Audit 4 - H25): MAX_BATCH_SIZE = 10,000 to prevent cost abuse

---

### 4. `forge-cascade-v2/forge/services/ghost_council.py`

**Purpose:** AI advisory board that provides tri-perspective analysis (Optimistic, Balanced, Critical) on governance proposals and responds to serious system issues. Features 10 council members with different expertise domains.

**Key Methods:**
```python
async def deliberate_proposal(proposal: Proposal, context: dict | None, constitutional_review: dict | None, skip_cache: bool = False) -> GhostCouncilOpinion
async def respond_to_issue(issue: SeriousIssue) -> GhostCouncilOpinion
def detect_serious_issue(event_type: EventType, payload: dict, source: str) -> SeriousIssue | None
def add_issue_handler(handler: Callable[[SeriousIssue], None]) -> None
def get_stats() -> dict[str, Any]
```

**Dependencies:**
- `forge.models.governance` - Proposal, Vote models
- `forge.models.events` - EventType enum
- `forge.services.llm` - LLM service for AI deliberation

**State Management:**
- Opinion cache with TTL (configurable, default 30 days)
- Active issues tracking
- Statistics counters (proposals reviewed, unanimous decisions, cache hits)
- Profile-based member selection (quick/standard/comprehensive)

**Issues:**
- Cache key could collide if proposals have same title/description/type

**Improvements:**
- Include proposal ID in cache key for uniqueness
- Add cache versioning for prompt changes

**Possibilities:**
- Historical trend analysis of council decisions
- A/B testing different council configurations

**Security Notes:**
- SECURITY FIX (Audit 4): Profile included in cache key to prevent cross-config collisions
- SECURITY FIX (Audit 4): Prompt sanitization for all user-provided content

---

### 5. `forge-cascade-v2/forge/services/init.py`

**Purpose:** Initializes all services based on application configuration during FastAPI startup. Handles embedding, LLM, search, and Ghost Council service lifecycle.

**Key Methods:**
```python
def init_all_services(db_client=None, capsule_repo=None, event_bus=None) -> None
def shutdown_all_services() -> None
```

**Dependencies:**
- `forge.config` - Settings
- All service modules for initialization

**State Management:**
- Coordinates global service singletons
- Sets up event handlers for Ghost Council issue detection

**Issues:**
- Provider fallback to "mock" if not recognized (logged as warning)

**Improvements:**
- Add health checks during initialization
- Implement graceful degradation if services fail to initialize

**Possibilities:**
- Hot-reload configuration without restart
- Service dependency injection framework

**Security Notes:**
- SECURITY FIX (Audit 4 - M): Warns when falling back to mock providers
- Background task exception handling with proper logging

---

### 6. `forge-cascade-v2/forge/services/llm.py`

**Purpose:** Language model integration supporting multiple providers (Anthropic Claude, OpenAI GPT-4, Ollama local models, Mock) for Ghost Council, Constitutional AI, and content analysis.

**Key Methods:**
```python
async def complete(messages: list[LLMMessage], max_tokens: int | None, temperature: float | None) -> LLMResponse
async def ghost_council_review(proposal_title: str, proposal_description: str, ...) -> dict[str, Any]
async def constitutional_review(content: str, content_type: str, action: str, ...) -> dict[str, Any]
async def analyze_capsule(content: str, capsule_type: str, existing_tags: list[str] | None) -> dict[str, Any]
```

**Dependencies:**
- `httpx` - HTTP client for API calls
- `structlog` - Logging

**State Management:**
- Lazy HTTP client initialization per provider
- Retry logic with exponential backoff
- Global singleton instance

**Issues:**
- No token usage tracking aggregation across calls

**Improvements:**
- Add cost tracking and budget limits
- Implement response streaming for long completions

**Possibilities:**
- Support for function calling/tool use
- Provider failover chains

**Security Notes:**
- SECURITY FIX (Audit 3): HTTP client reuse instead of creating per request
- SECURITY FIX (Audit 4): Prompt sanitization with XML delimiters for user content

---

### 7. `forge-cascade-v2/forge/services/marketplace.py`

**Purpose:** Handles capsule marketplace operations including listings, purchases, carts, licensing, and revenue distribution. Implements trust-based pricing with 70/15/10/5 split (seller/lineage/platform/treasury).

**Key Methods:**
```python
async def create_listing(capsule_id: str, seller_id: str, price: Decimal, ...) -> CapsuleListing
async def publish_listing(listing_id: str, seller_id: str) -> CapsuleListing
async def add_to_cart(user_id: str, listing_id: str) -> Cart
async def checkout(user_id: str, payment_method: PaymentMethod) -> list[Purchase]
async def check_license(user_id: str, capsule_id: str) -> License | None
async def get_marketplace_stats() -> MarketplaceStats
```

**Dependencies:**
- `forge.models.marketplace` - Marketplace data models
- `neo4j_client` - Database persistence

**State Management:**
- In-memory caches for listings, purchases, carts, licenses
- Neo4j persistence for all data
- Load from database on startup

**Issues:**
- View counts not persisted to database (only incremented in memory)

**Improvements:**
- Batch persistence for frequently updated metrics
- Add pagination to listing queries

**Possibilities:**
- Auction/bidding mechanism
- Subscription marketplace for recurring access

**Security Notes:**
- SECURITY FIX (Audit 4): Listing updates now persisted to database
- Authorization checks on all write operations

---

### 8. `forge-cascade-v2/forge/services/notifications.py`

**Purpose:** Multi-channel notification delivery supporting in-app notifications, webhook delivery with SSRF protection, retry logic, and user preferences management.

**Key Methods:**
```python
async def notify(user_id: str, event_type: NotificationEvent, title: str, message: str, ...) -> Notification
async def broadcast(event_type: NotificationEvent, title: str, message: str, ...) -> int
async def create_webhook(user_id: str, url: str, secret: str, ...) -> WebhookSubscription
async def get_notifications(user_id: str, unread_only: bool = False, ...) -> list[Notification]
async def mark_as_read(notification_id: str, user_id: str) -> bool
```

**Dependencies:**
- `httpx` - HTTP client for webhooks
- `bcrypt` - Secret hashing
- `socket`, `ipaddress` - SSRF validation

**State Management:**
- Background worker tasks for webhook delivery and retries
- Async queues for webhook processing
- User preference storage

**Issues:**
- Loaded webhooks from DB have hashed secret, can't sign new payloads

**Improvements:**
- Implement proper secret rotation mechanism
- Add webhook health monitoring

**Possibilities:**
- Email and Slack integration
- Push notifications for mobile

**Security Notes:**
- SECURITY FIX (Audit 3): Comprehensive SSRF validation (private IPs, cloud metadata endpoints)
- SECURITY FIX (Audit 4 - H18): Webhook secrets hashed with bcrypt before storage
- SECURITY FIX (Audit 4 - M19): Broadcast requires admin permissions

---

### 9. `forge-cascade-v2/forge/services/pricing_engine.py`

**Purpose:** Sophisticated trust-based pricing algorithm for knowledge capsules considering PageRank, centrality, trust level, demand, rarity, lineage quality, and freshness.

**Key Methods:**
```python
async def calculate_price(capsule_id: str, factors: PricingFactors | None) -> PricingResult
async def calculate_lineage_distribution(capsule_id: str, total_lineage_share: Decimal) -> list[dict[str, Any]]
```

**Dependencies:**
- `forge.repositories.graph_repository` - For PageRank data
- `math` - Mathematical calculations

**State Management:**
- Stateless calculations (all data fetched per request)
- Configurable base prices by capsule type
- Trust curve and PageRank threshold constants

**Issues:**
- `_get_lineage_chain` is a stub returning empty list

**Improvements:**
- Implement actual lineage chain retrieval
- Add historical price tracking for trend analysis

**Possibilities:**
- Machine learning price prediction
- Dynamic pricing based on real-time demand

**Security Notes:**
- All calculations are deterministic and server-side

---

### 10. `forge-cascade-v2/forge/services/query_cache.py`

**Purpose:** Redis-backed caching for NL-to-Cypher query results to reduce LLM API calls and improve response times.

**Key Methods:**
```python
async def get(question: str, user_trust: int) -> CachedQueryResult | None
async def set(question: str, user_trust: int, compiled_cypher: str, parameters: dict, ...) -> bool
async def invalidate(question: str, user_trust: int) -> bool
async def invalidate_all() -> int
async def get_stats() -> dict[str, Any]
```

**Dependencies:**
- `redis.asyncio` - Redis client
- `forge.config` - Settings

**State Management:**
- Redis-backed cache with automatic TTL expiration
- In-memory fallback (`InMemoryQueryCache`) when Redis unavailable
- Hit count tracking per cached query

**Issues:**
- In-memory cache uses simple oldest-first eviction

**Improvements:**
- Implement LRU eviction for in-memory fallback
- Add cache warming for common queries

**Possibilities:**
- Query result clustering for similar questions
- Semantic cache keys using embeddings

---

### 11. `forge-cascade-v2/forge/services/query_compiler.py`

**Purpose:** Translates natural language questions into validated Cypher queries using LLM intent extraction. Includes comprehensive security validation to prevent injection attacks.

**Key Methods:**
```python
async def compile(question: str, user_trust: int = 60) -> CompiledQuery
async def query(question: str, user_trust: int, synthesize_answer: bool, max_results: int) -> QueryResult
```

**Classes:**
- `CypherValidator` - Security validation for generated queries
- `QueryCompiler` - NL to Cypher compilation
- `KnowledgeQueryService` - High-level query execution

**Dependencies:**
- `forge.services.llm` - LLM for intent extraction
- `forge.database.client` - Neo4j execution
- `forge.models.query` - Query data models

**State Management:**
- Stateless compilation (uses LLM service)
- Schema context for query generation

**Issues:**
- Fallback intent extraction is keyword-based and simplistic

**Improvements:**
- Add query plan caching for repeated patterns
- Implement query complexity limits

**Possibilities:**
- Multi-turn conversational queries
- Query explanation generation

**Security Notes:**
- SECURITY FIX (Audit 4): Prompt sanitization for user questions
- Comprehensive Cypher validation including forbidden keywords, injection patterns, write operation blocking

---

### 12. `forge-cascade-v2/forge/services/scheduler.py`

**Purpose:** Lightweight asyncio-based background scheduler for periodic tasks (graph snapshots, version compaction, cache cleanup) without external dependencies.

**Key Methods:**
```python
def register(name: str, func: Callable, interval_seconds: float, enabled: bool = True) -> None
async def start() -> None
async def stop() -> None
async def run_task_now(name: str) -> bool
def get_stats() -> dict[str, Any]
```

**Dependencies:**
- `forge.config` - Settings
- `forge.database.client` - For scheduled tasks
- `forge.repositories` - Graph and temporal repositories

**State Management:**
- Task registry with run counts and error tracking
- Shutdown event for graceful termination
- Per-task asyncio.Task management

**Issues:**
- Tasks staggered by name hash (may not evenly distribute)

**Improvements:**
- Add task dependencies for ordered execution
- Implement cron-style scheduling

**Possibilities:**
- Web UI for task management
- Task result persistence

**Security Notes:**
- SECURITY FIX: Client creation inside try block to prevent connection leaks

---

### 13. `forge-cascade-v2/forge/services/search.py`

**Purpose:** Unified search service integrating semantic (vector), keyword, hybrid, and exact search modes with result ranking, filtering, and boost mechanisms.

**Key Methods:**
```python
async def search(request: SearchRequest) -> SearchResponse
```

**Internal Methods:**
- `_semantic_search()` - Vector similarity search
- `_keyword_search()` - Full-text regex search
- `_hybrid_search()` - Combined semantic + keyword
- `_exact_search()` - Exact content match

**Dependencies:**
- `forge.services.embedding` - Embedding generation
- `forge.repositories.capsule_repository` - Data access
- Neo4j vector index for similarity search

**State Management:**
- Stateless (uses embedding service and database)
- Result score normalization

**Issues:**
- Repository path only supports single type/owner filter

**Improvements:**
- Add faceted search results
- Implement search suggestions

**Possibilities:**
- Personalized search ranking
- Search analytics and trending

**Security Notes:**
- SECURITY FIX (Audit 4 - M20): Regex metacharacter escaping to prevent ReDoS
- SECURITY FIX (Audit 4): Falls back to direct search when multiple filters specified
- Query truncation in error logs to prevent data leakage

---

### 14. `forge-cascade-v2/forge/services/semantic_edge_detector.py`

**Purpose:** Automatically detects and creates semantic relationships between capsules using a two-phase approach: vector similarity for candidate selection, then LLM classification for relationship type determination.

**Key Methods:**
```python
async def analyze_capsule(capsule: Capsule, created_by: str) -> DetectionResult
async def batch_analyze(capsule_ids: list[str], created_by: str) -> list[DetectionResult]
```

**Dependencies:**
- `forge.services.embedding` - Vector embeddings
- `forge.services.llm` - Relationship classification
- `forge.repositories.capsule_repository` - Data access
- `forge.models.semantic_edges` - Relationship types

**State Management:**
- Lazy LLM service initialization
- Detection configuration (thresholds, max candidates, enabled types)

**Issues:**
- No rate limiting on batch analysis

**Improvements:**
- Add confidence calibration based on feedback
- Implement incremental analysis for updated capsules

**Possibilities:**
- Knowledge graph visualization of detected relationships
- Relationship strength evolution tracking

**Security Notes:**
- SECURITY FIX (Audit 4): Prompt sanitization with XML delimiters
- Low temperature (0.1) for consistent classification

---

### 15. `forge_virtuals_integration/forge/virtuals/revenue/service.py`

**Purpose:** Revenue management for the Forge-Virtuals ecosystem handling inference fees, service fees, governance rewards, trading fees (Sentient Tax), distribution processing, and DCF valuation.

**Key Methods:**
```python
async def record_inference_fee(capsule_id: str, user_wallet: str, query_text: str, tokens_processed: int) -> RevenueRecord
async def record_service_fee(overlay_id: str, service_type: str, base_amount_virtual: float, client_wallet: str) -> RevenueRecord
async def record_governance_reward(participant_wallet: str, proposal_id: str, participation_type: str) -> RevenueRecord
async def record_trading_fee(token_address: str, trade_amount_virtual: float, trader_wallet: str, trade_type: str) -> RevenueRecord
async def process_pending_distributions(batch_size: int = 100) -> dict[str, float]
async def get_revenue_summary(entity_id: str | None, ...) -> dict[str, Any]
async def estimate_entity_value(entity_id: str, entity_type: str, discount_rate: float, growth_rate: float) -> dict[str, Any]
```

**Dependencies:**
- `..config` - Virtuals configuration
- `..models` - RevenueRecord, TransactionRecord
- `..chains` - Chain manager for blockchain ops

**State Management:**
- Pending distributions queue (persisted on startup)
- Repository-backed record storage
- Aggregation for batch processing

**Issues:**
- DCF valuation uses simplified perpetuity formula

**Improvements:**
- Add multi-period DCF with terminal value
- Implement revenue forecasting

**Possibilities:**
- Real-time revenue dashboards
- Revenue-based credit scoring

**Security Notes:**
- SECURITY FIX (Audit 4 - M16): Distribution integrity verification (expected vs actual totals)

---

### 16. `forge_virtuals_integration/forge/virtuals/tokenization/service.py`

**Purpose:** Complete tokenization lifecycle management for Forge entities including bonding curve mechanics, graduation to Uniswap liquidity, revenue distribution, governance voting, and cross-chain bridging via Wormhole.

**Key Methods:**
```python
async def request_tokenization(request: TokenizationRequest) -> TokenizedEntity
async def contribute_to_bonding_curve(entity_id: str, contributor_wallet: str, amount_virtual: float) -> tuple[TokenizedEntity, BondingCurveContribution]
async def distribute_revenue(entity_id: str, revenue_amount_virtual: float, revenue_source: str) -> dict[str, float]
async def create_governance_proposal(entity_id: str, proposer_wallet: str, title: str, description: str, ...) -> TokenHolderProposal
async def cast_governance_vote(proposal_id: str, voter_wallet: str, vote: str) -> TokenHolderGovernanceVote
async def bridge_token(entity_id: str, destination_chain: str, amount: float, ...) -> dict[str, Any]
```

**Dependencies:**
- `..config` - Virtuals config with graduation thresholds
- `..models` - Tokenization models
- `..chains` - Blockchain integration

**State Management:**
- Repository-backed entity, contribution, and proposal storage
- Chain manager for blockchain operations
- Simulation mode with deterministic tx hashes

**Issues:**
- Voting power hardcoded to 1000 in simulation mode
- Web3 integration requires contract ABIs

**Improvements:**
- Implement actual token balance queries
- Add proposal execution after voting ends

**Possibilities:**
- Multi-sig treasury management
- Automated market making strategies

**Security Notes:**
- Graduation threshold validation
- Vote validation (for/against/abstain only)
- Entity ownership verification before tokenization

---

## Cross-Service Architecture Summary

### Service Categories

1. **AI/ML Services:** EmbeddingService, LLMService, GhostCouncilService, SemanticEdgeDetector
2. **Search/Query Services:** SearchService, QueryCompiler, QueryCache
3. **Infrastructure Services:** BackgroundScheduler, NotificationService
4. **Business Logic Services:** MarketplaceService, PricingEngine, AgentGatewayService
5. **Blockchain Services:** RevenueService, TokenizationService

### Common Patterns

- **Global Singletons:** Most services use `get_*_service()` pattern for singleton access
- **Lazy Initialization:** HTTP clients and expensive resources initialized on first use
- **Async/Await:** All services are fully async-compatible
- **Structured Logging:** Consistent use of `structlog` across services
- **Security Hardening:** Multiple audit fixes applied (Audit 3 and Audit 4)

### Security Audit Fixes Applied

| Audit | Fix ID | Description |
|-------|--------|-------------|
| Audit 3 | Various | HTTP client reuse, SSRF protection, thread-safe caching |
| Audit 4 | H10 | Bounded cache sizes to prevent DoS |
| Audit 4 | H18 | Bcrypt hashing for webhook secrets |
| Audit 4 | H24 | API key redaction in logs |
| Audit 4 | H25 | Batch size limits for embedding requests |
| Audit 4 | M16 | Distribution integrity verification |
| Audit 4 | M19 | Admin permissions for broadcast |
| Audit 4 | M20 | Regex escape for search queries |
| Audit 4 | Various | Prompt sanitization with XML delimiters |

### Dependency Graph

```
init.py
  ├── embedding.py (EmbeddingService)
  ├── llm.py (LLMService)
  ├── search.py (SearchService) ──► embedding.py
  └── ghost_council.py (GhostCouncilService) ──► llm.py

query_compiler.py ──► llm.py

semantic_edge_detector.py
  ├── embedding.py
  └── llm.py

marketplace.py ──► pricing_engine.py

agent_gateway.py
  ├── query_compiler.py
  └── capsule_repository

notifications.py (standalone)

scheduler.py
  ├── query_cache.py
  └── temporal_repository

revenue/service.py ──► chains (blockchain)

tokenization/service.py ──► chains (blockchain)
```
