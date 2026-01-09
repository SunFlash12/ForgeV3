# Codebase Audit 2 - Implementation Plan

## Overview
This document contains all 150+ fixes identified in Codebase Audit 2, organized by priority.

---

## PHASE 1: CRITICAL FIXES (Immediate - Block Production)

### CRITICAL-01: Replace python-jose with PyJWT
**File:** `forge-cascade-v2/requirements.txt`, `requirements.txt`
**Issue:** python-jose abandoned since 2022, CVE-2022-29217
**Fix:**
```python
# Remove:
python-jose[cryptography]>=3.3.0

# Add:
PyJWT>=2.8.0
cryptography>=41.0.0
```
**Code Changes:** Update all imports from `jose` to `jwt`, update token creation/verification calls

---

### CRITICAL-02: Add SSRF Protection to Federation
**File:** `forge-cascade-v2/forge/federation/protocol.py`
**Issue:** No URL validation before HTTP requests to peer URLs
**Fix:**
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('10.0.0.0/8'),       # Private
    ipaddress.ip_network('172.16.0.0/12'),    # Private
    ipaddress.ip_network('192.168.0.0/16'),   # Private
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local
    ipaddress.ip_network('::1/128'),          # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),         # IPv6 private
]

def validate_peer_url(url: str) -> bool:
    """Validate peer URL is not internal/private."""
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http'):
        return False

    # Resolve hostname
    try:
        import socket
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)

        for blocked in BLOCKED_IP_RANGES:
            if ip_obj in blocked:
                return False
    except socket.gaierror:
        return False

    return True
```
**Also:** Set `follow_redirects=False` or add redirect validation

---

### CRITICAL-03: Replace threading.Lock with asyncio.Lock in TokenBlacklist
**File:** `forge-cascade-v2/forge/security/tokens.py:53`
**Issue:** threading.Lock blocks async event loop
**Fix:**
```python
class TokenBlacklist:
    _blacklist: set[str] = set()
    _expiry_times: dict[str, datetime] = {}
    _lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def add(cls, jti: str, expires_at: datetime) -> None:
        async with cls._get_lock():
            cls._blacklist.add(jti)
            cls._expiry_times[jti] = expires_at

    @classmethod
    async def is_blacklisted(cls, jti: str) -> bool:
        async with cls._get_lock():
            return jti in cls._blacklist
```

---

### CRITICAL-04: Fix Rate Limiting Race Condition
**File:** `forge-cascade-v2/forge/overlays/security_validator.py:118-147`
**Issue:** Non-atomic counter increments allow rate limit bypass
**Fix Option A (Redis):**
```python
async def check_rate_limit(self, user_id: str) -> tuple[bool, str | None]:
    key = f"rate_limit:{user_id}:{int(time.time() // 60)}"
    count = await self.redis.incr(key)
    if count == 1:
        await self.redis.expire(key, 60)

    if count > self.requests_per_minute:
        return False, f"Rate limit exceeded: {self.requests_per_minute}/min"
    return True, None
```
**Fix Option B (asyncio.Lock):**
```python
_rate_limit_lock = asyncio.Lock()

async def check_rate_limit(self, user_id: str) -> tuple[bool, str | None]:
    async with self._rate_limit_lock:
        now = datetime.utcnow()
        if now - self.minute_reset > timedelta(minutes=1):
            self.minute_counts.clear()
            self.minute_reset = now

        if self.minute_counts[user_id] >= self.requests_per_minute:
            return False, f"Rate limit exceeded"

        self.minute_counts[user_id] += 1
        return True, None
```

---

### CRITICAL-05: Remove Hardcoded Default Passwords
**Files:**
- `forge-cascade-v2/test_forge_v3_comprehensive.py:28`
- `forge-cascade-v2/manual_test.py:39`
- `forge-cascade-v2/test_all_features.py:18-19`
- `forge-cascade-v2/test_ui_integration.py:15`
- `forge-cascade-v2/test_quick.py:10`
- `docker-compose.yml:191,195`
- `docker-compose.prod.yml`
- All other docker-compose files

**Fix for test files:**
```python
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("SEED_ADMIN_PASSWORD environment variable required")
```

**Fix for docker-compose:**
```yaml
# Remove default values
command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD required}
```

---

### CRITICAL-06: Add Authentication to Federation Peer Registration
**File:** `forge-cascade-v2/forge/api/routes/federation.py:203-281`
**Issue:** Any user can register federation peers
**Fix:**
```python
@router.post("/peers", response_model=PeerResponse)
async def register_peer(
    request: PeerRegistrationRequest,
    admin: AdminUserDep,  # ADD THIS - require admin role
    protocol: FederationProtocol = Depends(get_protocol),
    audit_repo: AuditRepoDep,
):
    # Audit log the registration
    await audit_repo.log_action(
        action="federation_peer_registered",
        entity_type="federation_peer",
        entity_id=request.url,
        user_id=admin.id,
        details={"peer_name": request.name, "peer_url": request.url},
    )
    # ... rest of implementation
```

---

### CRITICAL-07: Implement Federation Key Persistence
**File:** `forge-cascade-v2/forge/federation/protocol.py:77-89`
**Issue:** Keys regenerated on every restart, breaking peer trust
**Fix:**
```python
import os
from cryptography.hazmat.primitives import serialization

async def _load_or_generate_keys(self) -> None:
    """Load existing keys from secure storage or generate new ones."""
    key_path = os.environ.get("FEDERATION_KEY_PATH", "/app/keys/federation.key")

    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(), password=None
            )
        logger.info("Loaded existing federation keypair")
    else:
        # Generate new keys only on first run
        self._private_key = ed25519.Ed25519PrivateKey.generate()

        # Save to secure storage
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        os.chmod(key_path, 0o600)  # Restrict permissions
        logger.info("Generated new federation keypair")
```

---

### CRITICAL-08: Fix GDS Query Injection
**File:** `forge-cascade-v2/forge/repositories/graph_repository.py`
**Locations:** Lines 146-163, 367-399, 483-505, 871-892, 1069-1108
**Issue:** Node labels and relationship types passed directly to GDS CALL

**Fix - Add whitelist validation:**
```python
ALLOWED_NODE_LABELS = {"Capsule", "User", "Proposal", "Vote"}
ALLOWED_RELATIONSHIPS = {"DERIVED_FROM", "RELATED_TO", "OWNS", "VOTED", "SUPPORTS", "CONTRADICTS"}

def validate_gds_input(node_label: str = None, relationship_type: str = None) -> None:
    if node_label and node_label not in ALLOWED_NODE_LABELS:
        raise ValueError(f"Invalid node label: {node_label}")
    if relationship_type and relationship_type not in ALLOWED_RELATIONSHIPS:
        raise ValueError(f"Invalid relationship type: {relationship_type}")

async def compute_pagerank(self, request: PageRankRequest) -> list[NodeRanking]:
    validate_gds_input(request.node_label, request.relationship_type)
    # ... rest of implementation with validated inputs
```

---

### CRITICAL-09: Add Nonce-Based Replay Prevention
**File:** `forge-cascade-v2/forge/federation/protocol.py`
**Issue:** No nonce in handshakes allows replay attacks within 5-minute window

**Fix:**
```python
import secrets
from functools import lru_cache

# Nonce cache with TTL
_used_nonces: dict[str, datetime] = {}
_nonce_lock = asyncio.Lock()

async def create_handshake(self) -> PeerHandshake:
    timestamp = datetime.now(timezone.utc)
    nonce = secrets.token_hex(32)  # 256-bit random nonce

    handshake_data = {
        "instance_id": self.instance_id,
        "nonce": nonce,  # ADD NONCE
        "timestamp": timestamp.isoformat(),
        # ... rest of fields
    }
    # Sign including nonce
    ...

async def verify_handshake(self, handshake: PeerHandshake) -> bool:
    # Check nonce hasn't been used
    async with _nonce_lock:
        if handshake.nonce in _used_nonces:
            logger.warning("Replay attack detected: nonce reused")
            return False

        # Clean old nonces (older than 5 minutes)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        _used_nonces = {k: v for k, v in _used_nonces.items() if v > cutoff}

        # Store new nonce
        _used_nonces[handshake.nonce] = datetime.now(timezone.utc)

    # Continue with signature verification
    ...
```

---

## PHASE 2: HIGH PRIORITY FIXES (1-2 Weeks)

### HIGH-01: Pin Docker Base Images
**Files:** All Dockerfiles
**Fix:** Pin to specific versions with SHA256 digests
```dockerfile
# Instead of:
FROM python:3.11-slim
FROM node:20-alpine
FROM nginx:alpine

# Use:
FROM python:3.11.11-slim@sha256:abc123...
FROM node:20.18.1-alpine@sha256:def456...
FROM nginx:1.27.3-alpine@sha256:ghi789...
```

---

### HIGH-02: Add Non-Root Users to Dockerfiles
**Files:**
- `marketplace/Dockerfile`
- `scripts/backup/Dockerfile`
- `forge-cascade-v2/frontend/Dockerfile`

**Fix for marketplace/Dockerfile:**
```dockerfile
FROM nginx:alpine

# Create non-root user
RUN addgroup -g 101 -S nginx && \
    adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx nginx

# ... copy files ...

# Use non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
```

---

### HIGH-03: Remove Redis Port Exposure
**File:** `docker-compose.yml:183-195`
**Fix:**
```yaml
redis:
  image: redis:7-alpine
  container_name: forge-redis
  # REMOVE THIS:
  # ports:
  #   - "6379:6379"

  # Keep internal exposure only:
  expose:
    - "6379"
```

---

### HIGH-04: Remove Docker Socket Mount
**File:** `forge-cascade-v2/docker/docker-compose.prod.yml:287`
**Issue:** Docker socket grants root-equivalent access
**Fix:** Use alternative log collection (Loki file-based driver, etc.)
```yaml
# REMOVE:
# volumes:
#   - /var/run/docker.sock:/var/run/docker.sock
```

---

### HIGH-05: Add Locks to WebSocket Connection Dictionaries
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py`
**Fix:**
```python
class ConnectionManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._event_connections: dict[str, WebSocketConnection] = {}
        # ...

    async def connect_events(self, connection_id: str, connection: WebSocketConnection):
        async with self._lock:
            self._event_connections[connection_id] = connection
            self._total_connections += 1

    async def disconnect_events(self, connection_id: str):
        async with self._lock:
            if connection_id in self._event_connections:
                del self._event_connections[connection_id]
```

---

### HIGH-06: Add Locks to Trust Score Updates
**File:** `forge-cascade-v2/forge/federation/trust.py`
**Fix:**
```python
class PeerTrustManager:
    def __init__(self):
        self._trust_lock = asyncio.Lock()

    async def record_successful_sync(self, peer: FederatedPeer) -> float:
        async with self._trust_lock:
            old_trust = peer.trust_score
            new_trust = min(1.0, old_trust + self.SYNC_SUCCESS_BONUS)
            peer.trust_score = new_trust
            self._peer_trust_cache[peer.id] = new_trust
            return new_trust
```

---

### HIGH-07: Fix IDOR on By-Owner Endpoint
**File:** `forge-cascade-v2/forge/api/routes/capsules.py:519-541`
**Fix:**
```python
@router.get("/search/by-owner/{owner_id}")
async def get_capsules_by_owner(
    owner_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    pagination: PaginationDep,
) -> CapsuleListResponse:
    # SECURITY FIX: Only allow users to view their own capsules
    # or admins to view any user's capsules
    if user.id != owner_id and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other users' capsules",
        )
    # ... rest of implementation
```

---

### HIGH-08: Add Governance Execution Timelock
**File:** `forge-cascade-v2/forge/api/routes/governance.py`
**Fix:**
```python
EXECUTION_TIMELOCK_HOURS = 24  # Configurable

@router.post("/{proposal_id}/finalize")
async def finalize_proposal(
    proposal_id: str,
    user: CoreUserDep,
    governance_repo: GovernanceRepoDep,
):
    proposal = await governance_repo.get_by_id(proposal_id)

    # Check timelock period has passed
    if proposal.status == ProposalStatus.PASSED:
        timelock_end = proposal.voting_ends_at + timedelta(hours=EXECUTION_TIMELOCK_HOURS)
        if datetime.now(timezone.utc) < timelock_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Execution timelock active until {timelock_end.isoformat()}",
            )
    # ... rest of implementation
```

---

### HIGH-09: Add Token Refresh Audit Logging
**File:** `forge-cascade-v2/forge/api/routes/auth.py:446-454`
**Fix:**
```python
# After successful token refresh:
await audit_repo.log_user_action(
    actor_id=user.id,
    target_user_id=user.id,
    action="token_refreshed",
    ip_address=client_info.ip_address,
    user_agent=client_info.user_agent,
)
```

---

### HIGH-10: Add Permission Denial Audit Logging
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Fix:** Add audit logging to all authorization decorators
```python
def require_trust_level(min_level: TrustLevel):
    async def dependency(
        user: ActiveUserDep,
        audit_repo: AuditRepoDep,
        request: Request,
    ) -> User:
        authorizer = TrustAuthorizer(min_level)
        if not authorizer.authorize(user):
            # LOG PERMISSION DENIAL
            await audit_repo.log_action(
                action="permission_denied",
                entity_type="trust_check",
                entity_id=str(request.url.path),
                user_id=user.id,
                details={
                    "required_level": min_level.name,
                    "user_level": get_trust_level_from_score(user.trust_flame).name,
                },
            )
            raise HTTPException(...)
        return user
    return dependency
```

---

### HIGH-11: Harden Content Security Policy
**File:** `deploy/nginx/sites/forgecascade.org.conf:82`
**Fix:** Remove unsafe-inline and unsafe-eval
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'nonce-$request_id'; style-src 'self' 'nonce-$request_id'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://forgecascade.org wss://forgecascade.org;" always;
```
**Note:** This requires updating frontend to use nonce-based inline scripts/styles

---

### HIGH-12: Add CSRF Protection to Marketplace
**File:** `marketplace/src/services/api.ts`
**Fix:**
```typescript
let csrfToken: string | null = null;

export const setCSRFToken = (token: string) => {
  csrfToken = token;
};

// Add interceptor
this.client.interceptors.request.use((config) => {
  const statefulMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
  if (statefulMethods.includes(config.method?.toUpperCase() || '')) {
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});
```

---

### HIGH-13: Pin GitHub Actions to SHA
**Files:** `.github/workflows/ci.yml`, `forge-cascade-v2/.github/workflows/ci-cd.yml`
**Fix:**
```yaml
# Instead of:
- uses: aquasecurity/trivy-action@master
- uses: actions/checkout@v6

# Use:
- uses: aquasecurity/trivy-action@0.28.0  # Or full SHA
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

---

### HIGH-14: Add Webhook URL Validation
**File:** `forge-cascade-v2/forge/services/notifications.py`
**Fix:**
```python
async def create_webhook(
    self,
    user_id: str,
    url: str,
    events: list[str],
) -> WebhookSubscription:
    # VALIDATE URL
    if not self._validate_webhook_url(url):
        raise ValueError("Invalid webhook URL: must be HTTPS and not internal")

    # ... rest of implementation

def _validate_webhook_url(self, url: str) -> bool:
    """Validate webhook URL is safe (not internal/private)."""
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)

    # Must be HTTPS
    if parsed.scheme != 'https':
        return False

    # Resolve and check IP
    try:
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)

        # Block private ranges
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return False
    except:
        return False

    return True
```

---

### HIGH-15: Fix ReDoS in Query Compiler
**File:** `forge-cascade-v2/forge/services/query_compiler.py`
**Fix:** Add regex complexity limits or use re2
```python
import re2  # Google's RE2 library (no backtracking)

def compile_regex_constraint(self, pattern: str) -> str:
    # Validate regex complexity
    if len(pattern) > 100:
        raise ValueError("Regex pattern too long")

    # Use RE2 which doesn't allow catastrophic backtracking
    try:
        re2.compile(pattern)
    except re2.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    return pattern
```

---

## PHASE 3: MEDIUM PRIORITY FIXES (2-4 Weeks)

### MEDIUM-01: Create Security Unit Tests
**New Files:**
- `forge-cascade-v2/tests/security/test_tokens.py`
- `forge-cascade-v2/tests/security/test_password.py`
- `forge-cascade-v2/tests/security/test_authorization.py`
- `forge-cascade-v2/tests/middleware/test_csrf.py`
- `forge-cascade-v2/tests/middleware/test_rate_limiting.py`
- `forge-cascade-v2/tests/federation/test_trust.py`
- `forge-cascade-v2/tests/federation/test_protocol.py`

---

### MEDIUM-02: Add Bounded Memory Limits to Caches
**Files:**
- `forge-cascade-v2/forge/overlays/security_validator.py` (_threat_cache)
- `forge-cascade-v2/forge/overlays/lineage_tracker.py` (_nodes, _recent_derivations)
- `forge-cascade-v2/forge/services/embedding.py` (EmbeddingCache)

**Fix Example:**
```python
from collections import OrderedDict

class BoundedCache:
    def __init__(self, max_size: int = 10000):
        self._cache = OrderedDict()
        self._max_size = max_size

    def set(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)  # Remove oldest
        self._cache[key] = value
```

---

### MEDIUM-03: Reuse HTTP Clients in LLM Providers
**File:** `forge-cascade-v2/forge/services/llm.py`
**Fix:**
```python
class AnthropicProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        self._config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
```

---

### MEDIUM-04: Complete Quorum Verification
**File:** `forge-cascade-v2/forge/repositories/governance_repository.py:255-265`
**Fix:**
```python
async def close_voting(self, proposal_id: str) -> Proposal:
    proposal = await self.get_by_id(proposal_id)

    # Get total eligible voters (users with STANDARD+ trust)
    total_eligible = await self._count_eligible_voters()
    total_votes = proposal.votes_for + proposal.votes_against + proposal.votes_abstain

    # Check quorum
    participation_rate = total_votes / total_eligible if total_eligible > 0 else 0
    quorum_met = participation_rate >= proposal.quorum_percent

    # Determine outcome
    if not quorum_met:
        new_status = ProposalStatus.FAILED_QUORUM
    elif proposal.approval_ratio >= proposal.pass_threshold:
        new_status = ProposalStatus.PASSED
    else:
        new_status = ProposalStatus.REJECTED

    # ... update proposal status
```

---

### MEDIUM-05: Implement MFA
**New Files:**
- `forge-cascade-v2/forge/security/mfa.py`
- `forge-cascade-v2/forge/api/routes/mfa.py`

**Implementation Outline:**
```python
import pyotp

class MFAService:
    async def generate_secret(self, user_id: str) -> str:
        secret = pyotp.random_base32()
        # Store encrypted in database
        return secret

    async def verify_totp(self, user_id: str, code: str) -> bool:
        secret = await self._get_user_secret(user_id)
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    async def generate_backup_codes(self, user_id: str) -> list[str]:
        codes = [secrets.token_hex(4) for _ in range(10)]
        # Store hashed codes
        return codes
```

---

### MEDIUM-06: Add Trust Revocation to Federation
**File:** `forge-cascade-v2/forge/federation/trust.py`
**Fix:**
```python
async def revoke_peer(
    self,
    peer: FederatedPeer,
    reason: str,
    revoked_by: str,
) -> None:
    """Revoke a peer's trust and disable federation."""
    async with self._trust_lock:
        peer.trust_score = 0.0
        peer.status = PeerStatus.REVOKED
        peer.revoked_at = datetime.now(timezone.utc)
        peer.revocation_reason = reason

        self._peer_trust_cache[peer.id] = 0.0

        self._record_event(
            peer=peer,
            event_type="revoked",
            old_trust=peer.trust_score,
            new_trust=0.0,
            reason=reason,
            triggered_by=revoked_by,
        )
```

---

### MEDIUM-07: Add WebSocket Message Size Limits
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py`
**Fix:**
```python
MAX_MESSAGE_SIZE = 64 * 1024  # 64KB

async def receive_message(websocket: WebSocket) -> dict:
    """Receive and validate WebSocket message with size limit."""
    raw = await websocket.receive_text()

    if len(raw) > MAX_MESSAGE_SIZE:
        await websocket.close(code=1009)  # Message too big
        raise ValueError("Message exceeds size limit")

    return json.loads(raw)
```

---

### MEDIUM-08: Fix Error Message Disclosure
**Files:** Multiple API route files
**Pattern:** Replace `detail=str(e)` with generic messages
```python
# Before:
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))

# After:
except ValueError as e:
    logger.warning("validation_error", error=str(e), path=request.url.path)
    raise HTTPException(status_code=400, detail="Invalid request data")
```

---

### MEDIUM-09: Add Connection Limits to WebSocket
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py`
**Fix:**
```python
MAX_CONNECTIONS_PER_USER = 5
MAX_TOTAL_CONNECTIONS = 10000

async def connect_events(self, connection_id: str, connection: WebSocketConnection):
    async with self._lock:
        # Check global limit
        if self._total_connections >= MAX_TOTAL_CONNECTIONS:
            raise WebSocketException(code=1013, reason="Server at capacity")

        # Check per-user limit
        user_id = connection.user_id
        if user_id:
            user_conn_count = len(self._user_connections.get(user_id, set()))
            if user_conn_count >= MAX_CONNECTIONS_PER_USER:
                raise WebSocketException(code=1013, reason="Too many connections")

        # ... proceed with connection
```

---

### MEDIUM-10: Implement Proposal Action Validation
**File:** `forge-cascade-v2/forge/models/governance.py`
**Fix:**
```python
from enum import Enum

class ActionType(str, Enum):
    UPDATE_POLICY = "update_policy"
    ADJUST_TRUST = "adjust_trust"
    MODIFY_CONFIG = "modify_config"
    GRANT_ROLE = "grant_role"

class ProposalAction(BaseModel):
    action_type: ActionType
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v, info):
        action_type = info.data.get("action_type")
        # Validate parameters based on action type
        if action_type == ActionType.ADJUST_TRUST:
            if "delta" not in v or not isinstance(v["delta"], int):
                raise ValueError("ADJUST_TRUST requires integer 'delta'")
            if abs(v["delta"]) > 20:
                raise ValueError("Trust adjustment limited to +/-20")
        return v
```

---

## PHASE 4: LOW PRIORITY FIXES (Ongoing)

### LOW-01: Pin All Python Dependencies
```bash
# Generate locked requirements
pip-compile requirements.in -o requirements.txt --generate-hashes
```

### LOW-02: Add Permissions-Policy Header to Nginx
```nginx
add_header Permissions-Policy "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()" always;
```

### LOW-03: Remove Deprecated Docker Compose Version Field
Remove `version: '3.8'` from all docker-compose files (obsolete in modern Docker)

### LOW-04: Add maxLength to Frontend Form Inputs
```tsx
<input
  type="text"
  value={username}
  onChange={(e) => setUsername(e.target.value)}
  maxLength={255}  // ADD THIS
  ...
/>
```

### LOW-05: Implement Federation State Persistence
Move from in-memory to database storage for federation state

### LOW-06: Add Federation-Specific Rate Limiting
Separate rate limits for sync operations vs normal API calls

### LOW-07: Use Cryptographic Hash for Content Integrity
```python
import hashlib
content_hash = hashlib.sha256(content.encode()).hexdigest()
```

### LOW-08: Track All Background Tasks
Store task references and cancel on shutdown

### LOW-09: Add Self-Audit for Audit Log Purge
Log when audit records are deleted/archived

### LOW-10: Environment-Based Stack Trace Verbosity
Only include full traces in development mode

---

## Implementation Tracking

Use the todo list to track progress through these fixes. Start with CRITICAL items before moving to HIGH, then MEDIUM, then LOW.

Estimated effort:
- CRITICAL (9 items): 3-5 days
- HIGH (15 items): 1-2 weeks
- MEDIUM (10 items): 2-3 weeks
- LOW (10 items): Ongoing

Total: ~6-8 weeks for full remediation
