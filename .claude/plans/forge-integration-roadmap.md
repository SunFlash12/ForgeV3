# Forge Integration Roadmap

## Overview

Comprehensive plan to integrate all Forge subsystems into a cohesive knowledge marketplace with AI agent capabilities.

---

## Phase 1: Quick Wins

### 1.1 Knowledge Graph Explorer UI

**Purpose:** Interactive visualization of the knowledge graph with PageRank, communities, and semantic edges.

**New Files:**
- `forge-cascade-v2/frontend/src/pages/GraphExplorerPage.tsx`
- `forge-cascade-v2/frontend/src/components/graph/ForceGraph.tsx`
- `forge-cascade-v2/frontend/src/components/graph/NodeDetails.tsx`
- `forge-cascade-v2/frontend/src/components/graph/GraphControls.tsx`

**API Endpoints:**
```python
GET /api/v1/graph/explore
  - Returns nodes (capsules) and edges with positions
  - Supports filtering by type, trust_level, community

GET /api/v1/graph/node/{id}/neighbors
  - Returns immediate neighbors with relationship types

GET /api/v1/graph/communities
  - Returns detected communities with member counts

GET /api/v1/graph/paths/{source_id}/{target_id}
  - Returns shortest paths between nodes
```

**Features:**
- Force-directed graph layout (D3.js or react-force-graph)
- Node sizing by PageRank score
- Node coloring by community/trust level
- Edge styling by relationship type (SUPPORTS=green, CONTRADICTS=red)
- Click node → show details panel
- Search/filter controls
- Zoom/pan navigation
- Community highlighting

**Dependencies:** `react-force-graph-2d` or `@visx/network`

---

### 1.2 Webhook/Notification System

**Purpose:** Real-time alerts for governance events, Ghost Council issues, and system anomalies.

**New Files:**
- `forge-cascade-v2/forge/services/notifications.py`
- `forge-cascade-v2/forge/models/notifications.py`
- `forge-cascade-v2/forge/api/routes/webhooks.py`
- `forge-cascade-v2/frontend/src/components/NotificationBell.tsx`

**Database Schema:**
```python
class WebhookSubscription(ForgeModel):
    id: str
    user_id: str
    url: str
    secret: str  # For HMAC signing
    events: list[str]  # ["proposal.created", "issue.critical", ...]
    active: bool
    created_at: datetime

class Notification(ForgeModel):
    id: str
    user_id: str
    type: str  # "proposal", "issue", "anomaly", "vote"
    title: str
    message: str
    data: dict
    read: bool
    created_at: datetime
```

**Event Types:**
```python
class NotificationEvent(str, Enum):
    # Proposals
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_PASSED = "proposal.passed"
    PROPOSAL_REJECTED = "proposal.rejected"
    PROPOSAL_NEEDS_VOTE = "proposal.needs_vote"

    # Ghost Council
    ISSUE_DETECTED = "issue.detected"
    ISSUE_CRITICAL = "issue.critical"
    COUNCIL_RECOMMENDATION = "council.recommendation"

    # Capsules
    CAPSULE_CONTRADICTION = "capsule.contradiction"
    CAPSULE_TRUST_CHANGE = "capsule.trust_change"

    # System
    ANOMALY_DETECTED = "anomaly.detected"
    SYSTEM_DEGRADED = "system.degraded"
```

**API Endpoints:**
```python
POST /api/v1/webhooks
  - Register new webhook subscription

GET /api/v1/webhooks
  - List user's webhook subscriptions

DELETE /api/v1/webhooks/{id}
  - Remove webhook subscription

GET /api/v1/notifications
  - Get user's in-app notifications

POST /api/v1/notifications/{id}/read
  - Mark notification as read

POST /api/v1/notifications/read-all
  - Mark all notifications as read
```

**Webhook Payload:**
```json
{
  "event": "issue.critical",
  "timestamp": "2024-01-08T12:00:00Z",
  "data": {
    "issue_id": "...",
    "title": "Security threat detected",
    "severity": "critical",
    "category": "security"
  },
  "signature": "sha256=..."
}
```

---

### 1.3 Marketplace Backend Integration

**Purpose:** Connect the existing marketplace frontend to the Cascade API.

**New Files:**
- `forge-cascade-v2/forge/api/routes/marketplace.py`
- `forge-cascade-v2/forge/services/marketplace.py`
- `forge-cascade-v2/forge/models/marketplace.py`

**Models:**
```python
class CapsuleListing(ForgeModel):
    id: str
    capsule_id: str
    seller_id: str
    price: Decimal
    currency: str  # "FORGE", "USD", "SOL"
    license_type: str  # "perpetual", "subscription", "usage"
    status: str  # "active", "sold", "expired"
    created_at: datetime
    expires_at: datetime | None

class Purchase(ForgeModel):
    id: str
    listing_id: str
    buyer_id: str
    price: Decimal
    currency: str
    license_granted: str
    purchased_at: datetime
    transaction_hash: str | None  # For blockchain purchases

class Cart(ForgeModel):
    user_id: str
    items: list[CartItem]
    updated_at: datetime

class CartItem(ForgeModel):
    listing_id: str
    added_at: datetime
```

**API Endpoints:**
```python
# Listings
GET /api/v1/marketplace/listings
  - Browse available capsule listings
  - Filter by type, price_range, trust_level

POST /api/v1/marketplace/listings
  - Create new listing for owned capsule

GET /api/v1/marketplace/listings/{id}
  - Get listing details

DELETE /api/v1/marketplace/listings/{id}
  - Remove listing (seller only)

# Cart
GET /api/v1/marketplace/cart
  - Get user's cart

POST /api/v1/marketplace/cart/items
  - Add item to cart

DELETE /api/v1/marketplace/cart/items/{listing_id}
  - Remove item from cart

# Purchases
POST /api/v1/marketplace/checkout
  - Process cart purchase

GET /api/v1/marketplace/purchases
  - Get user's purchase history

GET /api/v1/marketplace/sales
  - Get user's sales history
```

**Integration Points:**
- Capsule ownership verification via `/capsules/{id}`
- Trust level affects listing visibility (low trust = warning)
- Ghost Council can review high-value transactions
- Blockchain transaction verification via Virtuals integration

---

## Phase 2: Strategic

### 2.1 Agent Knowledge Gateway

**Purpose:** Enable Virtuals AI agents to query and contribute to the knowledge graph.

**New Files:**
- `forge-cascade-v2/forge/api/routes/agent_gateway.py`
- `forge-cascade-v2/forge/services/agent_auth.py`
- `forge-cascade-v2/forge/models/agent.py`
- `forge-cascade-v2/forge/websockets/agent_stream.py`

**Agent Authentication:**
```python
class AgentCredential(ForgeModel):
    agent_id: str
    api_key: str  # Hashed
    owner_id: str
    permissions: list[str]  # ["read", "write", "query"]
    rate_limit: int  # Requests per minute
    created_at: datetime
    last_used: datetime | None
```

**API Endpoints:**
```python
# Agent Management
POST /api/v1/agents
  - Register new agent, get API key

GET /api/v1/agents
  - List user's registered agents

DELETE /api/v1/agents/{id}
  - Revoke agent credentials

# Knowledge Operations
GET /api/v1/agent/knowledge/search
  - Semantic search across capsules
  - Parameters: query, limit, min_trust, types[]

POST /api/v1/agent/knowledge/query
  - Natural language query (NL→Cypher)
  - Returns structured results

GET /api/v1/agent/knowledge/capsule/{id}
  - Get capsule content for agent consumption

POST /api/v1/agent/knowledge/capsule
  - Agent creates new capsule (sandbox trust)

POST /api/v1/agent/knowledge/capsule/{id}/feedback
  - Agent provides feedback on capsule usefulness

# WebSocket
WS /api/v1/agent/stream
  - Real-time knowledge updates
  - Subscribe to topics/capsule types
```

**Rate Limiting & Quotas:**
```python
class AgentQuota:
    queries_per_minute: int = 60
    capsules_per_day: int = 100
    bytes_per_request: int = 1_000_000
```

**Integration with Virtuals ACP:**
```python
# Bridge ACP messages to knowledge operations
class ACPKnowledgeBridge:
    async def handle_acp_message(self, message: ACPMessage):
        if message.type == "knowledge.query":
            return await self.query_knowledge(message.payload)
        elif message.type == "knowledge.contribute":
            return await self.create_capsule(message.payload)
```

---

### 2.2 Trust-Based Pricing Model

**Purpose:** Capsule value derived from trust metrics.

**New Files:**
- `forge-cascade-v2/forge/services/pricing.py`
- `forge-cascade-v2/forge/models/pricing.py`

**Pricing Formula:**
```python
class CapsulePricingEngine:
    """
    Price = BasePrice × TrustMultiplier × DemandMultiplier × RarityMultiplier

    TrustMultiplier = 1 + (trust_level / 100) × 2
        - QUARANTINE: 0.5x
        - SANDBOX: 1.0x
        - STANDARD: 1.5x
        - TRUSTED: 2.0x
        - CORE: 3.0x

    DemandMultiplier = 1 + log(views + citations) / 10

    RarityMultiplier = Based on community uniqueness
    """

    def calculate_suggested_price(
        self,
        capsule: Capsule,
        pagerank_score: float,
        citation_count: int,
        view_count: int,
    ) -> PriceSuggestion:
        trust_mult = self._trust_multiplier(capsule.trust_level)
        demand_mult = self._demand_multiplier(view_count, citation_count)
        rarity_mult = self._rarity_multiplier(capsule, pagerank_score)

        base_price = Decimal("10.00")  # Configurable

        suggested = base_price * trust_mult * demand_mult * rarity_mult

        return PriceSuggestion(
            suggested_price=suggested,
            min_price=suggested * Decimal("0.5"),
            max_price=suggested * Decimal("2.0"),
            factors={
                "trust": trust_mult,
                "demand": demand_mult,
                "rarity": rarity_mult,
            }
        )
```

**Revenue Sharing:**
```python
class RevenueDistribution:
    """
    When capsule is sold:
    - 70% to seller
    - 15% to lineage contributors (DERIVED_FROM chain)
    - 10% to platform
    - 5% to community treasury
    """

    def calculate_distribution(
        self,
        sale_amount: Decimal,
        capsule: Capsule,
        lineage: list[Capsule],
    ) -> dict[str, Decimal]:
        seller_share = sale_amount * Decimal("0.70")
        lineage_share = sale_amount * Decimal("0.15")
        platform_share = sale_amount * Decimal("0.10")
        treasury_share = sale_amount * Decimal("0.05")

        # Distribute lineage share by contribution weight
        lineage_distribution = self._distribute_lineage(
            lineage_share, lineage
        )

        return {
            "seller": seller_share,
            "platform": platform_share,
            "treasury": treasury_share,
            **lineage_distribution,
        }
```

---

### 2.3 Federated Knowledge

**Purpose:** Connect multiple Forge instances for distributed knowledge sharing.

**New Files:**
- `forge-cascade-v2/forge/federation/protocol.py`
- `forge-cascade-v2/forge/federation/sync.py`
- `forge-cascade-v2/forge/federation/trust.py`
- `forge-cascade-v2/forge/api/routes/federation.py`

**Federation Model:**
```python
class FederatedPeer(ForgeModel):
    id: str
    name: str
    url: str
    public_key: str  # For signing
    trust_score: float  # 0.0 - 1.0
    last_sync: datetime
    status: str  # "active", "degraded", "offline"

class FederatedCapsule(ForgeModel):
    local_id: str
    remote_id: str
    peer_id: str
    sync_status: str  # "synced", "pending", "conflict"
    last_synced: datetime
```

**Protocol:**
```python
class FederationProtocol:
    """
    1. Peer Discovery
       - Manual registration or DNS-based discovery
       - Exchange public keys

    2. Trust Establishment
       - Initial trust = 0.3
       - Trust increases with successful syncs
       - Ghost Council can review peer trust

    3. Sync Mechanisms
       - Push: Broadcast high-trust capsules
       - Pull: Request specific capsules/queries
       - Diff: Incremental sync since last timestamp

    4. Conflict Resolution
       - Higher trust wins
       - Or flag for manual review
    """

    async def sync_with_peer(self, peer: FederatedPeer):
        # Get changes since last sync
        changes = await self._get_peer_changes(peer)

        for change in changes:
            if change.type == "capsule":
                await self._merge_capsule(change, peer)
            elif change.type == "edge":
                await self._merge_edge(change, peer)
```

**API Endpoints:**
```python
# Peer Management
POST /api/v1/federation/peers
  - Register new peer

GET /api/v1/federation/peers
  - List known peers

DELETE /api/v1/federation/peers/{id}
  - Remove peer

# Sync
POST /api/v1/federation/sync/{peer_id}
  - Trigger sync with peer

GET /api/v1/federation/sync/status
  - Get sync status across all peers

# Incoming (for other peers)
POST /api/v1/federation/incoming/capsules
  - Receive capsules from peer

GET /api/v1/federation/incoming/changes
  - Peer requests changes since timestamp
```

---

## Implementation Order

```
Week 1-2: Phase 1
├── 1.1 Graph Explorer UI
├── 1.2 Webhook/Notification System
└── 1.3 Marketplace Backend Integration

Week 3-4: Phase 2
├── 2.1 Agent Knowledge Gateway
├── 2.2 Trust-Based Pricing
└── 2.3 Federation (foundation)

Week 5+: Polish & Integration
├── End-to-end testing
├── Documentation
├── Performance optimization
└── Security audit
```

---

## Technical Dependencies

**Frontend:**
- `react-force-graph-2d` - Graph visualization
- `@tanstack/react-query` - Already present
- `socket.io-client` - WebSocket for notifications

**Backend:**
- `aioredis` - Already present (caching)
- `websockets` or `socket.io` - Real-time
- `cryptography` - Webhook signing, federation keys
- `httpx` - Async HTTP for federation

---

## Success Metrics

| Feature | Metric | Target |
|---------|--------|--------|
| Graph Explorer | User engagement | >5 min avg session |
| Notifications | Delivery rate | >99% |
| Marketplace | Transactions/day | >10 |
| Agent Gateway | API calls/day | >1000 |
| Federation | Peer uptime | >95% |
