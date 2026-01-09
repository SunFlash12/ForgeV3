# Forge V3 Security Fix Todolist

**Generated:** January 8, 2026  
**Source:** Codebase Audit 2 Report  
**Total Issues:** 272+ findings across 10 phases  
**Purpose:** Comprehensive remediation guide for Claude Code

---

## How to Use This Document

This todolist is organized into four priority tiers. Work through them in order—each tier must be substantially complete before moving to the next. Each task includes the specific file location, line numbers where applicable, and the exact fix required. Check off items as you complete them.

---

## TIER 1: PRODUCTION BLOCKERS (Complete First)

These 9 critical issues must be fixed before any production deployment. Estimated time: 1-2 days.

### 1.1 Replace Vulnerable JWT Library

- [ ] **File:** `forge-cascade-v2/requirements.txt`
- [ ] **Action:** Replace `python-jose[cryptography]>=3.3.0` with `PyJWT>=2.8.0`
- [ ] **File:** `forge-cascade-v2/forge/security/tokens.py`
- [ ] **Action:** Update all imports from `jose` to `jwt`
- [ ] **Action:** Update `jwt.decode()` calls to use PyJWT syntax
- [ ] **Action:** Hardcode allowed algorithms list: `algorithms=["HS256"]` (line 445-460)
- [ ] **Verification:** Run existing auth tests to confirm JWT operations still work

### 1.2 Fix Async/Threading Lock Conflict

- [ ] **File:** `forge-cascade-v2/forge/security/tokens.py` (line 53)
- [ ] **Action:** Replace `threading.Lock()` with `asyncio.Lock()` in TokenBlacklist class
- [ ] **Action:** Update all lock acquisition to use `async with self._lock:`
- [ ] **File:** `forge-cascade-v2/forge/api/routes/system.py` (lines 59-90)
- [ ] **Action:** Replace `threading.Lock()` with `asyncio.Lock()` for maintenance state
- [ ] **Action:** Ensure all reads of maintenance state occur inside the lock
- [ ] **File:** `forge-cascade-v2/forge/database/client.py` (lines 281-286)
- [ ] **Action:** Initialize lock at module level to prevent race condition in `_get_lock()`
- [ ] **Verification:** Test concurrent token operations don't block event loop

### 1.3 Add SSRF Protection to Federation

- [ ] **File:** `forge-cascade-v2/forge/federation/protocol.py` (lines 177-218)
- [ ] **Action:** Create URL validation function that blocks private IP ranges:
  - Block 127.0.0.0/8 (localhost)
  - Block 10.0.0.0/8 (private class A)
  - Block 172.16.0.0/12 (private class B)
  - Block 192.168.0.0/16 (private class C)
  - Block 169.254.0.0/16 (link-local)
  - Block fc00::/7 (IPv6 private)
- [ ] **Action:** Apply validation before every `self._http_client.post()` call
- [ ] **File:** `forge-cascade-v2/forge/federation/protocol.py` (lines 62-64)
- [ ] **Action:** Set `follow_redirects=False` or validate redirect targets
- [ ] **File:** `forge-cascade-v2/forge/services/notifications.py` (lines 63-67)
- [ ] **Action:** Apply same URL validation to webhook URLs
- [ ] **Verification:** Test that internal IP requests are rejected

### 1.4 Fix Non-Atomic Rate Limiting

- [ ] **File:** `forge-cascade-v2/forge/overlays/security_validator.py` (lines 118-147)
- [ ] **Action:** Replace in-memory counter with Redis INCR for atomic operations
- [ ] **Action:** If Redis unavailable, add `asyncio.Lock()` around counter operations
- [ ] **Action:** Ensure check-and-increment is atomic (single operation)
- [ ] **Verification:** Test concurrent requests don't bypass rate limits

### 1.5 Remove Hardcoded Passwords

- [ ] **File:** `forge-cascade-v2/tests/test_forge_v3_comprehensive.py` (line 28)
- [ ] **Action:** Replace `admin123` with `os.environ.get("TEST_ADMIN_PASSWORD")`
- [ ] **File:** `forge-cascade-v2/tests/manual_test.py` (line 39)
- [ ] **Action:** Replace `admin123` with environment variable
- [ ] **File:** `forge-cascade-v2/tests/test_all_features.py` (lines 18-19)
- [ ] **Action:** Replace `admin123` and `oracle123` with environment variables
- [ ] **File:** `forge-cascade-v2/tests/test_ui_integration.py` (line 15)
- [ ] **Action:** Replace `admin123` with environment variable
- [ ] **File:** `forge-cascade-v2/tests/test_quick.py` (line 10)
- [ ] **Action:** Replace `admin123` with environment variable
- [ ] **File:** `forge-cascade-v2/tests/conftest.py` (lines 25-26)
- [ ] **Action:** Generate random secrets for each test run instead of hardcoded values
- [ ] **All docker-compose files:**
- [ ] **Action:** Remove default passwords from `${REDIS_PASSWORD:-forge_redis_secret}` pattern
- [ ] **Action:** Require explicit password, fail startup if not set
- [ ] **Verification:** Grep codebase for "admin123", "password", ensure none remain

### 1.6 Add Authentication to Federation Peer Registration

- [ ] **File:** `forge-cascade-v2/forge/api/routes/federation.py` (lines 203-281)
- [ ] **Action:** Add `Depends(require_admin)` to peer registration endpoint
- [ ] **Action:** Verify caller has ADMIN or SYSTEM role before allowing registration
- [ ] **Verification:** Test that unauthenticated requests are rejected with 401/403

### 1.7 Implement Federation Key Persistence

- [ ] **File:** `forge-cascade-v2/forge/federation/protocol.py` (lines 77-89)
- [ ] **Action:** Create key storage mechanism (file-based or database)
- [ ] **Action:** On startup, check for existing keys before generating new ones
- [ ] **Action:** If keys exist, load them; if not, generate and persist
- [ ] **Action:** Add key backup/recovery mechanism
- [ ] **Verification:** Restart service and confirm peer identity remains stable

### 1.8 Fix GDS Query Injection

- [ ] **File:** `forge-cascade-v2/forge/repositories/graph_repository.py` (lines 146-163)
- [ ] **Action:** Create whitelist of allowed node labels
- [ ] **Action:** Create whitelist of allowed relationship types
- [ ] **Action:** Validate `request.node_label` against whitelist before use
- [ ] **Action:** Validate `request.relationship_type` against whitelist before use
- [ ] **File:** Same file, lines 367-399, 483-505, 871-892, 1069-1108
- [ ] **Action:** Apply same whitelist validation to all GDS CALL statements
- [ ] **Verification:** Test that invalid labels/types are rejected

### 1.9 Add Nonce to Federation Handshakes

- [ ] **File:** `forge-cascade-v2/forge/federation/protocol.py` (lines 122-151)
- [ ] **Action:** Generate cryptographic nonce (e.g., `secrets.token_hex(32)`) for each handshake
- [ ] **Action:** Include nonce in signed handshake data
- [ ] **Action:** Create nonce tracking store (Redis or in-memory with TTL)
- [ ] **Action:** Reject handshakes with previously-used nonces
- [ ] **Action:** Expire tracked nonces after 5-minute window
- [ ] **Verification:** Test that replayed handshakes are rejected

---

## TIER 2: HIGH PRIORITY (Complete Within 1-2 Weeks)

These issues pose significant security or stability risks. Estimated time: 5-7 days.

### 2.1 Docker Security Hardening

- [ ] **All Dockerfiles:** Pin base images to SHA256 digests
  - [ ] `marketplace/Dockerfile` - pin python and node images
  - [ ] `scripts/backup/Dockerfile` - pin base image
  - [ ] `forge-cascade-v2/frontend/Dockerfile` - pin node image
  - [ ] All other Dockerfiles in project
- [ ] **All Dockerfiles:** Add non-root user configuration
  - [ ] Add `RUN adduser --disabled-password --gecos '' appuser`
  - [ ] Add `USER appuser` before CMD/ENTRYPOINT
- [ ] **File:** `docker-compose.yml` (line 184)
- [ ] **Action:** Change `ports: - "6379:6379"` to `expose: - "6379"` for Redis
- [ ] **File:** `docker-compose.prod.yml` (line 287)
- [ ] **Action:** Remove Docker socket mount `/var/run/docker.sock`
- [ ] **Action:** Use alternative log collection method (Fluentd, Filebeat)
- [ ] **All docker-compose files:**
- [ ] **Action:** Replace `:latest` tags with specific versions (Jaeger, cloudflared)

### 2.2 WebSocket Security

- [ ] **File:** `forge-cascade-v2/forge/api/websocket/handlers.py` (lines 462-489)
- [ ] **Action:** Remove optional authentication, require auth for all endpoints
- [ ] **File:** Same file (lines 56, 68, 124, 198)
- [ ] **Action:** Add `asyncio.Lock()` to protect counter increments
- [ ] **File:** Same file (lines 123, 154, 226, 251)
- [ ] **Action:** Add `asyncio.Lock()` to protect dictionary modifications
- [ ] **Action:** Add 64KB message size limit to WebSocket handlers
- [ ] **Action:** Add idle timeout (e.g., 5 minutes) with ping/pong
- [ ] **Action:** Add maximum connections per user limit

### 2.3 Fix IDOR Vulnerability

- [ ] **File:** `forge-cascade-v2/forge/api/routes/capsules.py` (lines 519-541)
- [ ] **Action:** Add ownership check: `if current_user.id != owner_id and not is_admin(current_user):`
- [ ] **Action:** Return 403 Forbidden if check fails
- [ ] **Verification:** Test that users cannot access other users' capsule lists

### 2.4 Fix Trust Score Race Condition

- [ ] **File:** `forge-cascade-v2/forge/federation/trust.py` (lines 76-93)
- [ ] **Action:** Add `asyncio.Lock()` to protect trust score updates
- [ ] **Action:** Use atomic read-modify-write pattern

### 2.5 Fix Embedding Cache Race Condition

- [ ] **File:** `forge-cascade-v2/forge/services/embedding.py` (lines 330-350)
- [ ] **Action:** Add `asyncio.Lock()` to protect cache operations
- [ ] **Action:** Consider using `cachetools` with built-in thread safety

### 2.6 Add Execution Timelock to Governance

- [ ] **File:** `forge-cascade-v2/forge/api/routes/governance.py` (lines 1069-1133)
- [ ] **Action:** Add `execution_allowed_after` timestamp field to proposals
- [ ] **Action:** Set timelock period (24-48 hours) after proposal passes
- [ ] **Action:** Check `datetime.now() >= execution_allowed_after` before executing
- [ ] **Action:** Allow emergency bypass only for SYSTEM role with additional approval

### 2.7 Add Missing Audit Logging

- [ ] **File:** `forge-cascade-v2/forge/api/routes/auth.py` (lines 446-454)
- [ ] **Action:** Add audit log entry for token refresh operations
- [ ] **File:** `forge-cascade-v2/forge/security/authorization.py`
- [ ] **Action:** Add audit log entry for all permission denials
- [ ] **Action:** Include user ID, requested permission, and reason for denial

### 2.8 Harden Content Security Policy

- [ ] **File:** `deploy/nginx/sites/forgecascade.org.conf` (line 82)
- [ ] **Action:** Remove `'unsafe-inline'` from script-src
- [ ] **Action:** Remove `'unsafe-eval'` from script-src
- [ ] **Action:** Implement nonce-based CSP for inline scripts
- [ ] **Action:** Update frontend to use nonce attribute on script tags

### 2.9 Add CSRF to Marketplace

- [ ] **File:** `marketplace/src/services/api.ts` (lines 16-38)
- [ ] **Action:** Add axios interceptor to include X-CSRF-Token header
- [ ] **Action:** Fetch CSRF token from cookie or dedicated endpoint
- [ ] **Action:** Include token on all state-changing requests (POST, PUT, DELETE)

### 2.10 Pin GitHub Actions

- [ ] **File:** `.github/workflows/ci.yml` (line 262)
- [ ] **Action:** Replace `aquasecurity/trivy-action@master` with specific SHA
- [ ] **File:** `forge-cascade-v2/.github/workflows/ci-cd.yml` (line 282)
- [ ] **Action:** Replace `@master` with specific SHA
- [ ] **All workflow files:**
- [ ] **Action:** Pin all actions to full SHA (e.g., `actions/checkout@a1b2c3d4...`)

### 2.11 Fix Token Refresh Vulnerability

- [ ] **File:** `forge-cascade-v2/forge/api/routes/auth.py` (lines 420-460)
- [ ] **Action:** Extract JTI from old access token before refresh
- [ ] **Action:** Add old access token JTI to blacklist
- [ ] **Action:** Issue new access token with new JTI
- [ ] **Verification:** Confirm old tokens stop working after refresh

### 2.12 Fix Session Fixation

- [ ] **File:** `forge-cascade-v2/forge/api/routes/auth.py` (lines 350-380)
- [ ] **Action:** Generate new session ID on successful login
- [ ] **Action:** Invalidate previous session if one existed
- [ ] **Action:** Issue new tokens with fresh identifiers

### 2.13 Fix User Enumeration

- [ ] **File:** `forge-cascade-v2/forge/api/routes/auth.py` (lines 280-330)
- [ ] **Action:** Replace specific error messages with generic "Account already exists"
- [ ] **File:** `forge-cascade-v2/forge/security/auth_service.py` (lines 175-200)
- [ ] **Action:** Always perform password hash comparison even for non-existent users
- [ ] **Action:** Use constant-time comparison for timing attack prevention

### 2.14 Fix Error Message Disclosure

- [ ] **File:** `forge-cascade-v2/forge/api/routes/system.py` (lines 288, 394)
- [ ] **Action:** Replace `"error": str(e)` with generic "Service unavailable"
- [ ] **Action:** Log full error details internally
- [ ] **File:** `forge-cascade-v2/forge/security/dependencies.py` (lines 95-100)
- [ ] **Action:** Return generic "Invalid token" instead of detailed error
- [ ] **Files:** `auth.py`, `marketplace.py`, `agent_gateway.py`
- [ ] **Action:** Find and fix all `detail=str(e)` patterns

### 2.15 Fix Authorization Issues

- [ ] **File:** `forge-cascade-v2/forge/security/authorization.py` (lines 269-272)
- [ ] **Action:** Define explicit permissions for SYSTEM role instead of `"all": True`
- [ ] **File:** Same file (lines 115-124)
- [ ] **Action:** Fix boundary condition: use `>=` instead of `>` for CORE threshold
- [ ] **File:** Same file (lines 519-523)
- [ ] **Action:** Check capability denials BEFORE role permissions
- [ ] **Action:** Normalize roles to consistent case (uppercase or lowercase)

---

## TIER 3: MEDIUM PRIORITY (Complete Within 2-4 Weeks)

These issues should be addressed for production hardening. Estimated time: 2-3 weeks.

### 3.1 Create Security Unit Tests

- [ ] Create `tests/security/test_tokens.py`
  - [ ] Test JWT generation with correct claims
  - [ ] Test JWT validation rejects invalid tokens
  - [ ] Test algorithm confusion attacks are blocked
  - [ ] Test token expiry is enforced
  - [ ] Test blacklist prevents reuse
- [ ] Create `tests/security/test_password.py`
  - [ ] Test password hashing produces different hashes
  - [ ] Test password verification works correctly
  - [ ] Test timing-safe comparison is used
- [ ] Create `tests/security/test_authorization.py`
  - [ ] Test trust level boundaries
  - [ ] Test role-based permissions
  - [ ] Test capability overrides
  - [ ] Test IDOR prevention
- [ ] Create `tests/security/test_crypto.py`
  - [ ] Test AES-256-GCM encryption/decryption
  - [ ] Test Ed25519 signature generation/verification
  - [ ] Test key derivation functions
- [ ] Create `tests/middleware/test_csrf.py`
  - [ ] Test CSRF token generation
  - [ ] Test CSRF validation
  - [ ] Test CSRF bypass attempts fail
- [ ] Create `tests/middleware/test_rate_limiting.py`
  - [ ] Test rate limits are enforced
  - [ ] Test concurrent requests don't bypass
- [ ] Create `tests/federation/test_trust.py`
  - [ ] Test trust score updates
  - [ ] Test trust boundaries enforced
  - [ ] Test trust decay
- [ ] Create `tests/federation/test_protocol.py`
  - [ ] Test handshake signature verification
  - [ ] Test nonce replay prevention
  - [ ] Test SSRF protection

### 3.2 Add Bounded Memory Limits

- [ ] **File:** `forge-cascade-v2/forge/overlays/security_validator.py` (line 300)
- [ ] **Action:** Replace `defaultdict(list)` with bounded structure
- [ ] **Action:** Implement maximum entries per user (e.g., 1000)
- [ ] **Action:** Use `collections.deque` with maxlen for bounded storage
- [ ] **File:** `forge-cascade-v2/forge/overlays/lineage_tracker.py` (lines 186, 190)
- [ ] **Action:** Implement LRU eviction for `_nodes` dictionary
- [ ] **Action:** Use `cachetools.LRUCache` or similar
- [ ] **File:** `forge-cascade-v2/forge/security/tokens.py` (lines 53-90)
- [ ] **Action:** Add maximum size to in-memory token blacklist
- [ ] **Action:** Evict oldest entries when limit reached

### 3.3 Implement HTTP Client Reuse

- [ ] **File:** `forge-cascade-v2/forge/services/llm.py` (lines 227, 300, 369)
- [ ] **Action:** Create persistent `httpx.AsyncClient` at service initialization
- [ ] **Action:** Reuse client across requests
- [ ] **Action:** Implement proper cleanup on service shutdown
- [ ] **Action:** Add connection pooling configuration

### 3.4 Complete Quorum Verification

- [ ] **File:** `forge-cascade-v2/forge/repositories/governance_repository.py` (lines 255-265)
- [ ] **Action:** Implement complete quorum calculation
- [ ] **Action:** Remove TODO comment
- [ ] **Action:** Add tests for quorum edge cases

### 3.5 Implement MFA

- [ ] Create `forge-cascade-v2/forge/security/mfa.py`
- [ ] **Action:** Implement TOTP generation using pyotp
- [ ] **Action:** Implement TOTP verification
- [ ] **Action:** Add MFA setup endpoint
- [ ] **Action:** Add MFA verification to login flow
- [ ] **Action:** Add backup codes generation
- [ ] **Action:** Add audit logging for MFA events

### 3.6 Add Trust Revocation to Federation

- [ ] **File:** `forge-cascade-v2/forge/federation/trust.py`
- [ ] **Action:** Add `revoke_peer(peer_id)` method
- [ ] **Action:** Set trust to 0 and mark as revoked
- [ ] **Action:** Prevent revoked peers from reconnecting
- [ ] **Action:** Add revocation audit log

### 3.7 Add Trust Expiration to Federation

- [ ] **File:** `forge-cascade-v2/forge/federation/trust.py`
- [ ] **Action:** Add `last_verified` timestamp to peer trust
- [ ] **Action:** Implement trust decay over time
- [ ] **Action:** Require periodic re-verification (e.g., weekly)

### 3.8 Fix Input Validation Issues

- [ ] **File:** `forge-cascade-v2/forge/services/query_compiler.py` (lines 600-608)
- [ ] **Action:** Add regex complexity validation
- [ ] **Action:** Use RE2 library or implement complexity limits
- [ ] **Action:** Set maximum regex length
- [ ] **File:** `forge-cascade-v2/forge/models/governance.py` (lines 57-67)
- [ ] **Action:** Define ActionType enum with allowed actions
- [ ] **Action:** Validate action field against enum
- [ ] **Action:** Reject unknown action types

### 3.9 Fix Governance Action Validation

- [ ] **File:** `forge-cascade-v2/forge/models/governance.py` (lines 52-56)
- [ ] **Action:** Create Pydantic model for allowed governance actions
- [ ] **Action:** Validate all action dicts against schema
- [ ] **File:** `forge-cascade-v2/forge/api/routes/governance.py`
- [ ] **Action:** Add execution failure handling
- [ ] **Action:** Implement retry logic for failed executions
- [ ] **Action:** Add failure notifications

### 3.10 Fix Password Strength Validation

- [ ] **File:** `forge-cascade-v2/forge/security/password.py` (lines 80-120)
- [ ] **Action:** Add check against common password list (local file)
- [ ] **Action:** Consider haveibeenpwned API integration (optional)
- [ ] **Action:** Add check against user's previous passwords

### 3.11 Add API Limits

- [ ] **Action:** Add JSON depth limit (e.g., max 20 levels)
- [ ] **Action:** Add query parameter count limit (e.g., max 50)
- [ ] **Action:** Add request body size limit
- [ ] **Action:** Add IP-based rate limiting in addition to user-based

### 3.12 Fix Database Security

- [ ] **File:** `forge-cascade-v2/forge/repositories/user_repository.py` (lines 166, 372-376)
- [ ] **Action:** Replace `u {.*}` with explicit field list excluding password_hash
- [ ] **Action:** Add transaction timeout configuration to Neo4j client

### 3.13 Fix Frontend Security

- [ ] **File:** `forge-cascade-v2/frontend/index.html` (lines 11-13)
- [ ] **Action:** Add Subresource Integrity hashes to external fonts
- [ ] **Action:** Or self-host Google Fonts
- [ ] **File:** `marketplace/src/pages/Login.tsx` (lines 57-61)
- [ ] **Action:** Implement server-side OAuth redirect_uri validation
- [ ] **Action:** Disable source maps in production builds

### 3.14 Fix Logging Issues

- [ ] **File:** `forge-cascade-v2/forge/security/auth_service.py` (lines 139, 531, 541)
- [ ] **Action:** Hash or mask email addresses in audit logs
- [ ] **File:** Same file (line 182)
- [ ] **Action:** Don't log attempted username/email on failed login
- [ ] **File:** `forge-cascade-v2/forge/services/search.py` (line 204)
- [ ] **Action:** Truncate search queries in error logs

### 3.15 Track Background Tasks

- [ ] **File:** `forge-cascade-v2/forge/resilience/partition_manager.py` (line 163)
- [ ] **Action:** Store task reference from `asyncio.create_task()`
- [ ] **Action:** Add exception handler to log errors
- [ ] **File:** `forge-cascade-v2/forge/kernel/wasm_runtime.py` (line 645)
- [ ] **Action:** Store task reference, add exception handler
- [ ] **File:** `forge-cascade-v2/forge/services/init.py` (line 174)
- [ ] **Action:** Store task reference, add exception handler

---

## TIER 4: LONG-TERM IMPROVEMENTS (Ongoing)

These are enhancements for comprehensive security posture. Estimated time: ongoing.

### 4.1 Dependency Management

- [ ] **Action:** Pin all Python dependencies to exact versions using pip-compile
- [ ] **Action:** Generate locked requirements with `--generate-hashes`
- [ ] **Action:** Pin all Docker base images to SHA256 digests
- [ ] **Action:** Align dependency versions across packages (frontend vs marketplace)
- [ ] **Action:** Set up automated dependency vulnerability scanning
- [ ] **Action:** Consider migrating from passlib to bcrypt directly (passlib abandoned)

### 4.2 Federation State Persistence

- [ ] **Action:** Implement persistent storage for federation state
- [ ] **Action:** Persist peer trust scores to database
- [ ] **Action:** Persist nonce tracking across restarts
- [ ] **Action:** Add federation state backup mechanism

### 4.3 Federation Rate Limiting

- [ ] **Action:** Add federation-specific rate limits per peer
- [ ] **Action:** Limit handshake attempts per IP
- [ ] **Action:** Limit sync requests per time period

### 4.4 Content Integrity

- [ ] **File:** `forge-cascade-v2/forge/api/routes/federation.py` (line 776)
- [ ] **Action:** Replace Python `hash()` with SHA-256 for content hashing
- [ ] **Action:** Use cryptographic hashes for all integrity checks

### 4.5 Cryptography Improvements

- [ ] **Action:** Implement key rotation mechanism for JWT secrets
- [ ] **Action:** Implement key rotation for encryption keys
- [ ] **Action:** Consider RS256 (asymmetric) for JWT in production
- [ ] **Action:** Add HSM integration for key storage (enterprise)

### 4.6 Additional Headers

- [ ] **Action:** Add Permissions-Policy header
- [ ] **Action:** Review and harden all security headers

### 4.7 Audit System Improvements

- [ ] **Action:** Add bulk operation audit logging
- [ ] **Action:** Add data export audit logging
- [ ] **Action:** Add self-audit for audit log operations
- [ ] **Action:** Add maintenance mode logging to audit repository

### 4.8 Session Management

- [ ] **Action:** Add configurable concurrent session limit per user
- [ ] **Action:** Cap access token expiry at 15-30 minutes
- [ ] **Action:** Implement token rotation for refresh tokens

### 4.9 Monitoring Integration

- [ ] **File:** `forge-cascade-v2/forge/monitoring/` (entire module)
- [ ] **Action:** Call `configure_logging()` at application startup
- [ ] **Action:** Create `/metrics` endpoint
- [ ] **Action:** Connect Prometheus to metrics endpoint
- [ ] **Action:** Set up alerting for security events

### 4.10 Complete Open Audit 1 Items

- [ ] **A1-S04:** Fix arbitrary callable execution in `governance.py`
- [ ] **A1-F03:** Integrate monitoring module
- [ ] **A1-F05:** Implement real WASM runtime (not scaffold)
- [ ] **A1-D03:** Add persistent storage to marketplace and notifications services

---

## Verification Checklist

After completing each tier, run these verification steps:

### After Tier 1
- [ ] Run full test suite: `pytest`
- [ ] Verify no hardcoded passwords: `grep -r "admin123" --include="*.py"`
- [ ] Verify JWT library replaced: `grep -r "python-jose" requirements.txt`
- [ ] Test federation SSRF blocked: attempt to register internal IP as peer
- [ ] Test rate limiting: send concurrent requests, verify limits enforced

### After Tier 2
- [ ] Run security-focused tests
- [ ] Test IDOR: attempt to access other user's capsules
- [ ] Test CSRF: verify state-changing requests require token
- [ ] Test WebSocket auth: verify unauthenticated connections rejected
- [ ] Docker security scan: `docker scan <image>`

### After Tier 3
- [ ] Security test coverage > 50%
- [ ] Test MFA flow end-to-end
- [ ] Test federation trust revocation
- [ ] Memory profiling: verify no unbounded growth
- [ ] Load test: verify system handles concurrent load

### After Tier 4
- [ ] Full security audit (external)
- [ ] Penetration testing
- [ ] Compliance verification
- [ ] Documentation review

---

## Progress Tracking

| Tier | Total Tasks | Completed | Percentage |
|------|-------------|-----------|------------|
| Tier 1 (Blockers) | 47 | 0 | 0% |
| Tier 2 (High) | 72 | 0 | 0% |
| Tier 3 (Medium) | 89 | 0 | 0% |
| Tier 4 (Long-term) | 41 | 0 | 0% |
| **Total** | **249** | **0** | **0%** |

---

## Notes for Claude Code

When working through this list, follow these principles:

1. **Always create a branch** before making changes. Name it `security-fix/[issue-id]`.

2. **Run tests after each fix** to ensure nothing breaks. The command is typically `pytest` for Python and `npm test` for JavaScript.

3. **One commit per logical fix.** Don't bundle unrelated fixes in the same commit.

4. **Document your changes** in the commit message, referencing the audit finding (e.g., "Fix CRITICAL-1A-01: Hardcode JWT algorithm list").

5. **When fixing race conditions,** prefer `asyncio.Lock()` over `threading.Lock()` since the codebase is async.

6. **When adding validation,** prefer allowlists over blocklists. Define what IS allowed, not what isn't.

7. **When handling errors,** log the full error internally but return generic messages to users.

8. **When in doubt,** err on the side of security over convenience.

---

*Generated from Codebase Audit 2 Report dated January 8, 2026*
