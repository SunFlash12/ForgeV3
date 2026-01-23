# Forge V3 - API Routes Analysis

## Category: Core API & Routes
## Status: COMPLETE
## Last Updated: 2026-01-10
## Total Lines of Code: ~12,300+
## Framework: FastAPI with Pydantic v2

---

## Files in this Category (17 files)

| # | File | Status | Lines | Summary |
|---|------|--------|-------|---------|
| 1 | `forge-cascade-v2/forge/api/routes/__init__.py` | Complete | 24 | Router exports and module initialization |
| 2 | `forge-cascade-v2/forge/api/routes/agent_gateway.py` | Complete | 654 | AI agent gateway with WebSocket streaming |
| 3 | `forge-cascade-v2/forge/api/routes/auth.py` | Complete | 877 | Authentication, MFA, CSRF protection |
| 4 | `forge-cascade-v2/forge/api/routes/capsules.py` | Complete | 1,438 | Knowledge capsule CRUD and semantic search |
| 5 | `forge-cascade-v2/forge/api/routes/cascade.py` | Complete | 418 | 7-phase Cascade Effect pipeline |
| 6 | `forge-cascade-v2/forge/api/routes/federation.py` | Complete | 1,210 | Federation protocol and peer trust |
| 7 | `forge-cascade-v2/forge/api/routes/governance.py` | Complete | 1,477 | Proposals, voting, Ghost Council AI |
| 8 | `forge-cascade-v2/forge/api/routes/graph.py` | Complete | 1,511 | Graph algorithms and NL queries |
| 9 | `forge-cascade-v2/forge/api/routes/marketplace.py` | Complete | 803 | Knowledge trading with lineage revenue |
| 10 | `forge-cascade-v2/forge/api/routes/notifications.py` | Complete | 490 | Notifications and webhooks |
| 11 | `forge-cascade-v2/forge/api/routes/overlays.py` | Complete | 611 | Overlay/plugin management, canary deployments |
| 12 | `forge-cascade-v2/forge/api/routes/system.py` | Complete | 1,414 | System monitoring, health, maintenance |
| 13 | `forge-cascade-v2/forge/api/routes/users.py` | Complete | 417 | User management and IDOR protection |
| 14 | `forge-cascade-v2/forge/api/app.py` | Complete | 650 | FastAPI application factory |
| 15 | `forge-cascade-v2/forge/api/dependencies.py` | Complete | 609 | Dependency injection system |
| 16 | `forge-cascade-v2/forge/api/middleware.py` | Complete | 1,049 | Security and observability middleware |
| 17 | `forge_virtuals_integration/forge/virtuals/api/routes.py` | Complete | 752 | Web3/Virtuals Protocol integration |

---

## Detailed Analysis

### 1. `__init__.py` (24 lines)

**Purpose**: Module initialization and router exports.

**Functionality**:
- Exports all API routers for registration in main app
- Provides clean import interface

**Key Implementation**:
```python
from .auth import router as auth_router
from .capsules import router as capsules_router
# ... exports all routers
```

**Role in Forge**: Entry point for route registration; maintains clean module boundaries.

**Issues**: None identified.

**Improvements**: Consider adding version prefixes or grouping.

**Possibilities**: Could support dynamic router loading for plugins.

---

### 2. `agent_gateway.py` (654 lines)

**Purpose**: AI agent interaction gateway with session management and capability-based access control.

**Functionality**:
- `POST /agents/sessions` - Create agent session
- `DELETE /agents/sessions/{session_id}` - Terminate session
- `POST /agents/sessions/{session_id}/execute` - Execute agent command
- `GET /agents/sessions/{session_id}/stream` - WebSocket streaming
- `GET /agents/capabilities` - List agent capabilities
- `POST /agents/sessions/{session_id}/fork` - Fork session state

**Key Implementation Details**:
```python
class AgentCapability(str, Enum):
    READ_CAPSULES = "read_capsules"
    WRITE_CAPSULES = "write_capsules"
    EXECUTE_QUERIES = "execute_queries"
    GOVERNANCE_VOTE = "governance_vote"
    # ...
```
- Session-based agent authentication
- Capability permission model
- WebSocket streaming for real-time responses
- Session forking for parallel exploration

**Role in Forge**: Enables AI agents to interact with Forge programmatically; foundation for autonomous knowledge workers.

**Issues**:
- Session cleanup on disconnect not explicitly handled
- No rate limiting per capability

**Improvements**:
- Add session heartbeat mechanism
- Implement capability-level rate limits
- Add session recording for audit

**Possibilities**:
- Multi-agent collaboration sessions
- Agent marketplace integration
- Capability delegation chains

---

### 3. `auth.py` (877 lines)

**Purpose**: Comprehensive authentication system with MFA, CSRF, and secure session management.

**Functionality**:
- `POST /auth/register` - User registration with validation
- `POST /auth/login` - Login with MFA support
- `POST /auth/logout` - Secure logout with token blacklisting
- `POST /auth/refresh` - Token refresh with rotation
- `GET /auth/me` - Current user profile
- `POST /auth/mfa/setup` - Initialize MFA
- `POST /auth/mfa/verify` - Verify MFA code
- `POST /auth/mfa/disable` - Disable MFA
- `POST /auth/mfa/backup-codes` - Generate backup codes
- `POST /auth/password/change` - Password change
- `POST /auth/password/reset-request` - Password reset flow

**Key Implementation Details**:
```python
# Secure cookie configuration
response.set_cookie(
    key="access_token",
    value=tokens["access_token"],
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
)

# CSRF double-submit pattern
csrf_token = secrets.token_urlsafe(32)
response.set_cookie(key="csrf_token", value=csrf_token, ...)
```
- JWT tokens with httpOnly cookies
- CSRF protection via double-submit cookie pattern
- TOTP-based MFA with backup codes
- Token blacklisting on logout
- Password strength validation

**Role in Forge**: Security foundation; protects all authenticated endpoints.

**Issues**:
- Backup codes stored as list (should be hashed individually)
- No account lockout after failed attempts visible in routes

**Improvements**:
- Hash backup codes individually
- Add login attempt tracking in routes
- Support WebAuthn/passkeys
- Add session management (view/revoke sessions)

**Possibilities**:
- SSO/SAML integration
- Hardware security key support
- Biometric authentication

---

### 4. `capsules.py` (1,438 lines)

**Purpose**: Knowledge capsule management - the core data unit of Forge.

**Functionality**:
- `POST /capsules/` - Create capsule with validation
- `GET /capsules/` - List with pagination and filters
- `GET /capsules/{capsule_id}` - Get single capsule
- `PATCH /capsules/{capsule_id}` - Update capsule
- `DELETE /capsules/{capsule_id}` - Soft delete
- `POST /capsules/{capsule_id}/fork` - Fork capsule
- `POST /capsules/{capsule_id}/merge` - Merge capsules
- `GET /capsules/{capsule_id}/lineage` - Get derivation tree
- `GET /capsules/{capsule_id}/versions` - Version history
- `POST /capsules/{capsule_id}/versions/{version_id}/restore` - Restore version
- `GET /capsules/search` - Semantic search
- `POST /capsules/{capsule_id}/validate` - Content validation
- `POST /capsules/batch` - Batch operations

**Key Implementation Details**:
```python
class CapsuleType(str, Enum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    MEMORY = "memory"
    CONTEXT = "context"

# Semantic search integration
results = await capsule_repo.semantic_search(
    query=query,
    user_id=current_user.id,
    limit=limit,
    filters={"type": type_filter} if type_filter else None,
)
```
- Multiple capsule types (knowledge, skill, memory, context)
- Git-like versioning with fork/merge
- Lineage tracking for attribution
- Semantic vector search
- Batch operations for efficiency

**Role in Forge**: Central data model; everything revolves around capsules.

**Issues**:
- Large file (consider splitting by concern)
- Merge conflict resolution not detailed in routes

**Improvements**:
- Split into sub-modules (crud, versioning, search)
- Add capsule templates
- Implement conflict resolution UI hints
- Add capsule validation schemas

**Possibilities**:
- Capsule encryption at rest
- Cross-instance capsule linking
- Real-time collaborative editing

---

### 5. `cascade.py` (418 lines)

**Purpose**: The Cascade Effect - Forge's unique 7-phase knowledge propagation pipeline.

**Functionality**:
- `POST /cascade/trigger` - Trigger cascade propagation
- `GET /cascade/{cascade_id}` - Get cascade status
- `GET /cascade/{cascade_id}/phases` - Get phase details
- `POST /cascade/{cascade_id}/approve` - Manual approval gate
- `POST /cascade/{cascade_id}/reject` - Reject cascade
- `GET /cascade/history` - Cascade history

**Key Implementation Details**:
```python
class CascadePhase(str, Enum):
    INGESTION = "ingestion"
    ANALYSIS = "analysis"
    VALIDATION = "validation"
    CONSENSUS = "consensus"
    EXECUTION = "execution"
    PROPAGATION = "propagation"
    SETTLEMENT = "settlement"
```
- 7-phase pipeline: INGESTION -> ANALYSIS -> VALIDATION -> CONSENSUS -> EXECUTION -> PROPAGATION -> SETTLEMENT
- Manual approval gates
- Phase-level status tracking
- Propagation to connected capsules

**Role in Forge**: Core differentiator; enables trusted knowledge propagation with verification.

**Issues**:
- No rollback mechanism visible
- Phase timeout handling unclear

**Improvements**:
- Add cascade rollback
- Implement phase timeouts
- Add cascade simulation mode
- Support conditional propagation rules

**Possibilities**:
- Cross-federation cascades
- AI-assisted validation
- Cascade analytics dashboard

---

### 6. `federation.py` (1,210 lines)

**Purpose**: Federation protocol for cross-instance communication and trust management.

**Functionality**:
- `POST /federation/peers` - Register peer instance
- `GET /federation/peers` - List peers
- `GET /federation/peers/{peer_id}` - Get peer details
- `DELETE /federation/peers/{peer_id}` - Remove peer
- `POST /federation/peers/{peer_id}/sync` - Trigger sync
- `GET /federation/peers/{peer_id}/sync/status` - Sync status
- `POST /federation/capsules/share` - Share capsule to peer
- `POST /federation/capsules/import` - Import from peer
- `GET /federation/trust/report` - Trust analytics
- `POST /federation/peers/{peer_id}/trust` - Update peer trust
- `POST /federation/handshake` - Initiate federation handshake

**Key Implementation Details**:
```python
# Trust-based rate limiting
TRUST_RATE_MULTIPLIERS = {
    "untrusted": 0.5,
    "basic": 1.0,
    "verified": 2.0,
    "trusted": 5.0,
}

# Content integrity verification
content_hash = hashlib.sha256(content.encode()).hexdigest()
```
- SHA-256 content hashing for integrity
- Trust tiers with rate multipliers
- Cryptographic handshake protocol
- Selective capsule sharing
- Sync conflict resolution

**Role in Forge**: Enables decentralized knowledge network; core to Forge's vision.

**Issues**:
- Complex trust model needs documentation
- Network partition handling unclear

**Improvements**:
- Add federation health dashboard
- Implement conflict resolution strategies
- Add bandwidth throttling per peer
- Support selective field sync

**Possibilities**:
- Blockchain-anchored trust proofs
- Mesh network topology
- Cross-federation governance

---

### 7. `governance.py` (1,477 lines)

**Purpose**: Decentralized governance with proposals, voting, and the Ghost Council AI.

**Functionality**:
- `POST /governance/proposals` - Create proposal
- `GET /governance/proposals` - List proposals
- `GET /governance/proposals/{proposal_id}` - Get proposal
- `POST /governance/proposals/{proposal_id}/vote` - Cast vote
- `GET /governance/proposals/{proposal_id}/votes` - Get votes
- `POST /governance/proposals/{proposal_id}/execute` - Execute passed proposal
- `GET /governance/council/members` - Ghost Council members
- `POST /governance/council/deliberate` - Request AI deliberation
- `GET /governance/delegation` - Get delegations
- `POST /governance/delegation` - Delegate voting power
- `GET /governance/stats` - Governance statistics

**Key Implementation Details**:
```python
class ProposalType(str, Enum):
    PARAMETER_CHANGE = "parameter_change"
    CAPSULE_POLICY = "capsule_policy"
    TRUST_ADJUSTMENT = "trust_adjustment"
    OVERLAY_APPROVAL = "overlay_approval"
    COUNCIL_ELECTION = "council_election"

# Ghost Council AI deliberation
council_opinion = await ghost_council.deliberate(
    proposal=proposal,
    context={"capsules": related_capsules, "history": vote_history}
)
```
- Multiple proposal types
- Trust-weighted voting
- Vote delegation (liquid democracy)
- Ghost Council AI advisors
- Quorum and threshold requirements
- Proposal execution automation

**Role in Forge**: Democratic decision-making; empowers community governance.

**Issues**:
- Ghost Council deliberation latency
- Complex quorum calculations

**Improvements**:
- Add proposal templates
- Implement vote privacy options
- Add governance analytics
- Support quadratic voting

**Possibilities**:
- Cross-federation governance
- AI proposal drafting assistance
- Futarchy-style decision markets

---

### 8. `graph.py` (1,511 lines)

**Purpose**: Knowledge graph algorithms and natural language queries.

**Functionality**:
- `GET /graph/nodes` - List graph nodes
- `GET /graph/nodes/{node_id}` - Get node details
- `GET /graph/edges` - List edges
- `POST /graph/edges` - Create edge
- `DELETE /graph/edges/{edge_id}` - Delete edge
- `GET /graph/query` - Execute graph query
- `POST /graph/query/natural` - Natural language query
- `GET /graph/paths/{source_id}/{target_id}` - Find paths
- `GET /graph/clusters` - Get clusters
- `GET /graph/centrality` - Centrality metrics
- `GET /graph/recommendations/{node_id}` - Get recommendations
- `POST /graph/embeddings/compute` - Compute embeddings
- `GET /graph/visualization` - Get visualization data

**Key Implementation Details**:
```python
# Natural language to graph query
async def natural_language_query(
    query: str,
    current_user: ActiveUserDep,
    graph_service: GraphServiceDep,
) -> GraphQueryResponse:
    # LLM translates NL to graph query
    parsed = await graph_service.parse_natural_query(query)
    results = await graph_service.execute_query(parsed)
    return results

# Graph algorithms
- PageRank centrality
- Community detection
- Shortest path
- Semantic similarity
```
- Natural language query interface
- Multiple graph algorithms
- Embedding-based similarity
- Cluster detection
- Visualization data export

**Role in Forge**: Makes knowledge connections discoverable; enables insight generation.

**Issues**:
- Large algorithm library (performance concerns)
- Query complexity limits unclear

**Improvements**:
- Add query caching
- Implement query complexity scoring
- Add incremental embedding updates
- Support custom algorithms

**Possibilities**:
- Real-time graph streaming
- Predictive link suggestion
- Knowledge gap detection

---

### 9. `marketplace.py` (803 lines)

**Purpose**: Knowledge trading marketplace with lineage-based revenue sharing.

**Functionality**:
- `GET /marketplace/listings` - Browse listings
- `POST /marketplace/listings` - Create listing
- `GET /marketplace/listings/{listing_id}` - Get listing
- `PATCH /marketplace/listings/{listing_id}` - Update listing
- `DELETE /marketplace/listings/{listing_id}` - Remove listing
- `POST /marketplace/listings/{listing_id}/purchase` - Purchase
- `GET /marketplace/purchases` - User's purchases
- `GET /marketplace/sales` - User's sales
- `GET /marketplace/analytics` - Market analytics
- `GET /marketplace/revenue/{capsule_id}` - Lineage revenue

**Key Implementation Details**:
```python
# Lineage-based revenue sharing
async def calculate_lineage_revenue(capsule_id: str) -> LineageRevenue:
    lineage = await capsule_repo.get_lineage(capsule_id)
    shares = distribute_revenue(lineage, sale_amount)
    # Original creators get perpetual royalties
    return shares

# Trust-based pricing
price_multiplier = get_trust_multiplier(seller.trust_flame)
```
- Capsule listings with metadata
- Lineage-tracked revenue sharing
- Trust-based pricing modifiers
- Purchase history
- Market analytics

**Role in Forge**: Economic layer; incentivizes quality knowledge creation.

**Issues**:
- Payment integration placeholder
- Dispute resolution unclear

**Improvements**:
- Add escrow system
- Implement dispute resolution
- Add bundle/subscription options
- Support auctions

**Possibilities**:
- Token-based payments
- Knowledge derivatives
- Prediction markets for quality

---

### 10. `notifications.py` (490 lines)

**Purpose**: User notifications and webhook management.

**Functionality**:
- `GET /notifications/` - List notifications
- `GET /notifications/{notification_id}` - Get notification
- `PATCH /notifications/{notification_id}/read` - Mark as read
- `PATCH /notifications/read-all` - Mark all read
- `DELETE /notifications/{notification_id}` - Delete notification
- `GET /notifications/preferences` - Get preferences
- `PATCH /notifications/preferences` - Update preferences
- `POST /notifications/webhooks` - Register webhook
- `GET /notifications/webhooks` - List webhooks
- `DELETE /notifications/webhooks/{webhook_id}` - Remove webhook
- `POST /notifications/webhooks/{webhook_id}/test` - Test webhook

**Key Implementation Details**:
```python
class NotificationType(str, Enum):
    CAPSULE_UPDATE = "capsule_update"
    GOVERNANCE_VOTE = "governance_vote"
    FEDERATION_SYNC = "federation_sync"
    MARKETPLACE_SALE = "marketplace_sale"
    SYSTEM_ALERT = "system_alert"

# Webhook delivery with retry
async def deliver_webhook(webhook: Webhook, payload: dict):
    for attempt in range(MAX_RETRIES):
        try:
            await http_client.post(webhook.url, json=payload)
            break
        except Exception:
            await asyncio.sleep(backoff(attempt))
```
- Multiple notification types
- User preference management
- Webhook registration
- Webhook testing
- Delivery retry logic

**Role in Forge**: User engagement; keeps users informed of relevant events.

**Issues**:
- No webhook signature verification visible
- Notification batching not implemented

**Improvements**:
- Add webhook HMAC signatures
- Implement notification digest/batching
- Add push notification support
- Support notification templates

**Possibilities**:
- AI-prioritized notifications
- Cross-platform delivery
- Notification analytics

---

### 11. `overlays.py` (611 lines)

**Purpose**: Overlay/plugin system with canary deployment support.

**Functionality**:
- `GET /overlays/` - List overlays
- `POST /overlays/` - Register overlay
- `GET /overlays/{overlay_id}` - Get overlay
- `PATCH /overlays/{overlay_id}` - Update overlay
- `DELETE /overlays/{overlay_id}` - Remove overlay
- `POST /overlays/{overlay_id}/activate` - Activate overlay
- `POST /overlays/{overlay_id}/deactivate` - Deactivate overlay
- `POST /overlays/{overlay_id}/canary/start` - Start canary deployment
- `GET /overlays/{overlay_id}/canary/status` - Canary status
- `POST /overlays/{overlay_id}/canary/promote` - Promote canary
- `POST /overlays/{overlay_id}/canary/rollback` - Rollback canary

**Key Implementation Details**:
```python
# Canary deployment
@router.post("/{overlay_id}/canary/start")
async def start_canary_deployment(
    overlay_id: str,
    config: CanaryConfig,
    admin: AdminUserDep,
    canary_manager: CanaryManagerDep,
):
    deployment = await canary_manager.start(
        deployment_id=overlay_id,
        target=overlay.config,
        percentage=config.initial_percentage,
    )
    record_canary_started(overlay_id)
    return deployment
```
- Overlay lifecycle management
- Canary deployments with traffic splitting
- Gradual rollout control
- Automatic rollback on errors

**Role in Forge**: Extensibility; enables safe third-party integrations.

**Issues**:
- Overlay sandboxing not visible in routes
- Dependency management unclear

**Improvements**:
- Add overlay sandboxing
- Implement dependency resolution
- Add overlay marketplace integration
- Support overlay versioning

**Possibilities**:
- Overlay composition
- Cross-overlay communication
- Overlay revenue sharing

---

### 12. `system.py` (1,414 lines)

**Purpose**: System monitoring, health checks, and administrative operations.

**Functionality**:
- `GET /system/health` - Health check
- `GET /system/health/detailed` - Detailed health
- `GET /system/metrics` - System metrics
- `GET /system/circuit-breakers` - Circuit breaker status
- `POST /system/circuit-breakers/{name}/reset` - Reset breaker
- `GET /system/anomalies` - Detected anomalies
- `POST /system/anomalies/{anomaly_id}/acknowledge` - Acknowledge
- `GET /system/maintenance` - Maintenance status
- `POST /system/maintenance/enable` - Enable maintenance
- `POST /system/maintenance/disable` - Disable maintenance
- `GET /system/cache/stats` - Cache statistics
- `POST /system/cache/clear` - Clear cache
- `GET /system/audit/logs` - Audit logs
- `GET /system/config` - System configuration

**Key Implementation Details**:
```python
# Thread-safe maintenance mode
_maintenance_lock = threading.Lock()
_maintenance_state = {"enabled": False, "message": "", "started_at": None}

def is_maintenance_mode() -> bool:
    with _maintenance_lock:
        return _maintenance_state["enabled"]

# SECURITY FIX (Audit 3): Don't expose internal error details
except Exception as e:
    structlog.get_logger(__name__).error("database_health_check_failed", error=str(e))
    components["database"] = {"status": "unhealthy", "error": "Database connection failed"}
```
- Thread-safe maintenance mode
- Circuit breaker monitoring
- Anomaly detection and acknowledgment
- Cache management
- Audit log access
- Health check aggregation

**Role in Forge**: Operations/DevOps interface; critical for monitoring and maintenance.

**Issues**:
- Some metrics may expose sensitive info
- Anomaly acknowledgment doesn't prevent re-alerting

**Improvements**:
- Add metrics filtering for public endpoints
- Implement anomaly suppression windows
- Add scheduled maintenance windows
- Support custom health checks

**Possibilities**:
- Predictive maintenance
- Auto-scaling triggers
- SLA monitoring

---

### 13. `users.py` (417 lines)

**Purpose**: User management with IDOR protection.

**Functionality**:
- `GET /users/` - List users (admin only)
- `GET /users/{user_id}` - Get user profile
- `PATCH /users/{user_id}` - Admin update user
- `GET /users/{user_id}/capsules` - User's capsules
- `GET /users/{user_id}/activity` - User activity timeline
- `GET /users/{user_id}/governance` - Governance participation
- `PUT /users/{user_id}/trust` - Update trust level

**Key Implementation Details**:
```python
# SECURITY FIX (Audit 2): Add IDOR protection
if current_user.id != user_id and not is_admin(current_user):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Can only view your own capsules",
    )

# Consistent role checking
from forge.security.authorization import is_admin
```
- IDOR protection on all user endpoints
- Admin-only user listing
- Trust level management
- Activity timeline from audit logs
- Governance participation summary

**Role in Forge**: User data access; ensures proper authorization.

**Issues**:
- Pagination max page limit (10000) could be lower
- No user search functionality

**Improvements**:
- Add user search by username/email (admin)
- Implement user export
- Add user merge functionality
- Support user impersonation (admin)

**Possibilities**:
- User analytics dashboard
- Reputation badges
- Social features

---

### 14. `app.py` (650 lines)

**Purpose**: FastAPI application factory and configuration.

**Functionality**:
- Application factory pattern
- Router registration
- Middleware configuration
- Exception handlers
- CORS setup
- OpenAPI customization
- Startup/shutdown events

**Key Implementation Details**:
```python
def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="Forge API",
        version=settings.VERSION,
        docs_url="/api/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/api/redoc" if settings.DOCS_ENABLED else None,
    )

    # Register middleware in order
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    # ...

    # Register routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(capsules_router, prefix="/api/v1")
    # ...
```
- Clean application factory
- Environment-based configuration
- Ordered middleware registration
- Versioned API prefix
- Conditional docs exposure

**Role in Forge**: Application bootstrap; orchestrates all components.

**Issues**:
- Many routers in single registration block
- No API versioning strategy beyond prefix

**Improvements**:
- Group routers by domain
- Add proper API versioning
- Implement feature flags
- Add request ID logging

**Possibilities**:
- Multiple API versions
- GraphQL endpoint
- gRPC support

---

### 15. `dependencies.py` (609 lines)

**Purpose**: Dependency injection system for FastAPI.

**Functionality**:
- Repository dependencies (UserRepoDep, CapsuleRepoDep, etc.)
- Service dependencies (GraphServiceDep, etc.)
- User authentication dependencies (ActiveUserDep, AdminUserDep, etc.)
- Request context (CorrelationIdDep)
- Database session management

**Key Implementation Details**:
```python
# Typed dependency aliases
ActiveUserDep = Annotated[User, Depends(get_active_user)]
AdminUserDep = Annotated[User, Depends(get_admin_user)]
TrustedUserDep = Annotated[User, Depends(get_trusted_user)]
CoreUserDep = Annotated[User, Depends(get_core_user)]

# Repository factory
async def get_user_repo(session: SessionDep) -> UserRepository:
    return UserRepository(session)

UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
```
- Clean dependency injection
- Multiple user authorization levels
- Repository pattern implementation
- Session lifecycle management
- Typed annotations for IDE support

**Role in Forge**: Clean architecture enabler; separates concerns.

**Issues**:
- Large single file
- Some circular import potential

**Improvements**:
- Split by domain (auth deps, repo deps, service deps)
- Add dependency caching
- Implement dependency health checks

**Possibilities**:
- Hot-swappable implementations
- Testing mock injection
- Dependency metrics

---

### 16. `middleware.py` (1,049 lines)

**Purpose**: Security and observability middleware stack.

**Functionality**:
- `CorrelationIdMiddleware` - Request tracing
- `RequestLoggingMiddleware` - Structured logging
- `RateLimitMiddleware` - Trust-based rate limiting
- `CSRFMiddleware` - CSRF protection
- `SecurityHeadersMiddleware` - Security headers
- `MaintenanceModeMiddleware` - Maintenance mode
- `CompressionMiddleware` - Response compression
- `CacheControlMiddleware` - Cache headers
- `IdempotencyMiddleware` - Idempotent requests
- `RequestValidationMiddleware` - Input validation
- `ErrorHandlingMiddleware` - Exception formatting

**Key Implementation Details**:
```python
# Trust-based rate limiting
class RateLimitMiddleware(BaseHTTPMiddleware):
    AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register", ...}

    async def dispatch(self, request, call_next):
        trust_level = get_user_trust(request)
        multiplier = TRUST_MULTIPLIERS.get(trust_level, 1.0)
        limit = base_limit * multiplier
        # ...

# CSRF with timing-safe comparison
if not hmac.compare_digest(csrf_cookie, csrf_header):
    return JSONResponse(status_code=403, content={"error": "CSRF token invalid"})

# Security headers
response.headers["Content-Security-Policy"] = "default-src 'none'; ..."
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"

# SECURITY FIX (Audit 4 - M): Add cache size limit
MAX_CACHE_SIZE = 10000  # Max cached idempotency entries
```
- 10+ middleware classes
- Trust-based rate limiting
- CSRF with timing-safe comparison
- Comprehensive security headers
- Idempotency support
- Request logging with correlation IDs

**Role in Forge**: Security foundation; applies cross-cutting concerns uniformly.

**Issues**:
- Large file with many responsibilities
- Middleware order is critical (documented?)

**Improvements**:
- Split into separate files
- Document middleware order requirements
- Add middleware bypass for internal calls
- Implement circuit breaker for middleware

**Possibilities**:
- Pluggable middleware system
- A/B testing middleware
- Request replay

---

### 17. `routes.py` (Virtuals Integration) (752 lines)

**Purpose**: Web3/Virtuals Protocol integration for tokenized knowledge.

**Functionality**:
- `POST /virtuals/agents/register` - Register agent on chain
- `GET /virtuals/agents/{agent_id}` - Get agent status
- `POST /virtuals/capsules/{capsule_id}/tokenize` - Tokenize capsule
- `GET /virtuals/capsules/{capsule_id}/token` - Get token info
- `POST /virtuals/marketplace/list` - List on-chain marketplace
- `POST /virtuals/marketplace/purchase` - On-chain purchase
- `GET /virtuals/wallet/balance` - Get wallet balance
- `POST /virtuals/wallet/connect` - Connect wallet
- `GET /virtuals/transactions` - Transaction history

**Key Implementation Details**:
```python
# Capsule tokenization
@router.post("/capsules/{capsule_id}/tokenize")
async def tokenize_capsule(
    capsule_id: str,
    config: TokenizationConfig,
    current_user: ActiveUserDep,
    virtuals_service: VirtualsServiceDep,
):
    # Creates on-chain representation
    token = await virtuals_service.tokenize(
        capsule_id=capsule_id,
        owner=current_user.wallet_address,
        royalty_bps=config.royalty_bps,
    )
    return token
```
- Agent on-chain registration
- Capsule NFT tokenization
- On-chain marketplace integration
- Wallet connection flow
- Transaction tracking

**Role in Forge**: Web3 bridge; enables tokenized knowledge economy.

**Issues**:
- Gas estimation not visible
- Network selection unclear

**Improvements**:
- Add multi-chain support
- Implement gas estimation
- Add batch tokenization
- Support lazy minting

**Possibilities**:
- DAO governance integration
- Cross-chain bridges
- DeFi integrations

---

## Security Audit Summary

The codebase shows evidence of multiple security audit rounds with fixes applied:

### Audit 2 Fixes
- IDOR protection on user endpoints
- Authorization checks on capsule access

### Audit 3 Fixes
- Error message sanitization (no internal details exposed)
- Structured logging of errors

### Audit 4 Fixes (Most Recent)
- Cache size limits to prevent memory exhaustion
- Rate limit improvements
- Service-level security enhancements

---

## Issues Found

| Severity | File | Issue | Suggested Fix |
|----------|------|-------|---------------|
| Medium | `auth.py` | Backup codes stored as list, not individually hashed | Hash each backup code separately |
| Medium | `middleware.py` | Single large file with many responsibilities | Split into domain-specific middleware files |
| Medium | `capsules.py` | Large file (1,438 lines) | Split by concern (CRUD, versioning, search) |
| Low | `agent_gateway.py` | No explicit session cleanup on disconnect | Add WebSocket disconnect handler |
| Low | `users.py` | Max page limit of 10,000 is high | Reduce to 1,000 or implement cursor pagination |
| Low | `notifications.py` | No webhook signature verification | Add HMAC signature verification |
| Low | `app.py` | No API versioning strategy | Implement proper version management |
| Info | `dependencies.py` | Potential circular imports | Split by domain |
| Info | `system.py` | Some metrics may expose sensitive info | Add filtering for public endpoints |

---

## Improvements Identified

| Priority | File | Improvement | Benefit |
|----------|------|-------------|---------|
| High | `middleware.py` | Document middleware order requirements | Prevent misconfiguration |
| High | `auth.py` | Add WebAuthn/passkeys support | Modern authentication |
| High | `federation.py` | Add federation health dashboard | Operational visibility |
| Medium | `governance.py` | Add proposal templates | User experience |
| Medium | `capsules.py` | Add capsule validation schemas | Data quality |
| Medium | `graph.py` | Implement query caching | Performance |
| Medium | `marketplace.py` | Add escrow system | Transaction safety |
| Medium | `overlays.py` | Add overlay sandboxing | Security |
| Low | `notifications.py` | Implement notification batching | Reduce noise |
| Low | `system.py` | Add scheduled maintenance windows | Operations |
| Low | `agent_gateway.py` | Add session recording | Audit trail |

---

## Cross-Category Dependencies

| This File | Depends On | Category |
|-----------|------------|----------|
| `routes/*.py` | `models/*.py` | Models |
| `routes/*.py` | `repositories/*.py` | Repositories |
| `routes/*.py` | `services/*.py` | Services |
| `dependencies.py` | `security/*.py` | Security |
| `middleware.py` | `services/rate_limit.py` | Services |
| `auth.py` | `security/jwt.py`, `security/mfa.py` | Security |
| `federation.py` | `federation/protocol.py` | Federation |
| `governance.py` | `services/ghost_council.py` | Services |
| `cascade.py` | `services/cascade.py` | Services |
| `graph.py` | `services/graph.py` | Services |
| `virtuals/routes.py` | `virtuals/service.py` | Virtuals |

---

## Architecture Notes

The API layer follows a clean, modular architecture:

```
                    +-----------------+
                    |   FastAPI App   |
                    |    (app.py)     |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v--------+  +--v--+  +-------v-------+
     |   Middleware    |  | DI  |  |    Routes     |
     | (10+ classes)   |  |     |  | (13 modules)  |
     +--------+--------+  +--+--+  +-------+-------+
              |              |              |
              +--------------+--------------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v--------+  +--v--+  +-------v-------+
     |   Repositories  |  |     |  |   Services    |
     |                 |  |     |  |               |
     +--------+--------+  +-----+  +-------+-------+
              |                            |
              +------------+---------------+
                           |
                    +------v------+
                    |   Models    |
                    +-------------+
```

**Key Patterns**:
1. **Dependency Injection**: All dependencies injected via FastAPI's DI system
2. **Repository Pattern**: Data access abstracted through repositories
3. **Service Layer**: Business logic in services, routes are thin
4. **Middleware Stack**: Cross-cutting concerns handled uniformly
5. **Type Safety**: Pydantic models for all request/response validation

---

## Security Considerations

### Strengths
1. **Authentication**: JWT with httpOnly cookies, CSRF protection, MFA support
2. **Authorization**: Role-based with trust levels, IDOR protection
3. **Input Validation**: Pydantic models with constraints
4. **Rate Limiting**: Trust-based with Redis backend
5. **Security Headers**: Comprehensive CSP, X-Frame-Options, etc.
6. **Audit Logging**: All sensitive actions logged
7. **Error Handling**: Internal details not exposed

### Areas for Attention
1. Backup codes should be individually hashed
2. Webhook signatures needed for webhook endpoints
3. API versioning strategy for deprecation
4. Metrics endpoint filtering for sensitive data
5. Session management UI for users

---

## Recommendations

### High Priority
1. **Split Large Files**: `middleware.py`, `capsules.py`, `governance.py`, `graph.py`
2. **Document Middleware Order**: Critical for security correctness
3. **Add Webhook Signatures**: HMAC for webhook delivery
4. **Implement API Versioning**: Prepare for breaking changes

### Medium Priority
1. Add WebAuthn support to auth
2. Create federation health dashboard
3. Implement query caching for graph
4. Add overlay sandboxing

### Low Priority
1. Add notification batching
2. Implement scheduled maintenance windows
3. Add session recording for agents
4. Create user analytics dashboard

---

## Conclusion

The Forge V3 API layer is a sophisticated, well-architected system with:

**Strengths**:
- Clean separation of concerns
- Comprehensive security measures
- Evidence of multiple security audits
- Innovative features (Ghost Council, Cascade Effect, Federation)
- Type-safe implementation

**Areas for Growth**:
- File organization (some very large files)
- Documentation (especially middleware order)
- API versioning strategy
- Some security edge cases (webhook signatures, backup codes)

**Total API Surface**: ~100+ endpoints across 13 route modules, providing a comprehensive platform for decentralized knowledge management, governance, and trading.
