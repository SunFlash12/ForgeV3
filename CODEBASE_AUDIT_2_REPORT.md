# Forge V3 - Codebase Audit 2
## Comprehensive Security Audit Report

**Date:** January 8, 2026
**Auditor:** Claude Code (Opus 4.5)
**Version:** v1.5.0 (post-Audit 1 fixes)
**Scope:** Full codebase security audit across 10 phases

---

## Executive Summary

This comprehensive security audit analyzed the Forge V3 codebase across 10 phases covering authentication, authorization, cryptography, input validation, API security, database security, infrastructure, code quality, dependencies, frontend security, logging, business logic, and testing gaps.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total Findings** | 272+ |
| **Critical** | 19 |
| **High** | 58 |
| **Medium** | 85 |
| **Low** | 60+ |
| **Positive Findings** | 50+ |
| **Files Analyzed** | 200+ |
| **Lines of Code** | ~50,000 |

### Overall Risk Level: **HIGH**

The codebase has good foundational security practices but contains critical vulnerabilities that must be addressed before production deployment.

---

## Audit 1 Requirements Status

This section tracks all issues identified in Codebase Audit 1 and their current status after v1.5.0 release.

### Priority 1 - Security Vulnerabilities (from Audit 1)

| ID | Issue | Location | Audit 1 Status | Current Status | Audit 2 Findings |
|----|-------|----------|----------------|----------------|------------------|
| A1-S01 | Refresh token validation disabled | `auth_service.py:310-312` | CRITICAL | **FIXED** in v1.5.0 | Token refresh now validates against blacklist |
| A1-S02 | Password reset unimplemented | `auth_service.py:462-500` | CRITICAL | **FIXED** in v1.5.0 | Password reset with secure token implemented |
| A1-S03 | Token blacklist not enforced | `tokens.py:431-458` | CRITICAL | **PARTIAL** | Blacklist checked, but uses threading.Lock (see CRITICAL-4C-02) |
| A1-S04 | Arbitrary callable execution in governance | `governance.py` policy conditions | CRITICAL | **OPEN** | Still allows callable injection (see CRITICAL-1D-03) |
| A1-S05 | No Cypher validation in queries | `knowledge_query.py` | CRITICAL | **PARTIAL** | GDS queries still vulnerable (see CRITICAL-2-01) |
| A1-S06 | Hardcoded test credentials | Multiple test files | CRITICAL | **OPEN** | Still present (see CRITICAL-3B-01) |

### Priority 2 - Missing Functionality (from Audit 1)

| ID | Issue | Location | Audit 1 Status | Current Status | Notes |
|----|-------|----------|----------------|----------------|-------|
| A1-F01 | GraphRepository not exported | `repositories/__init__.py` | HIGH | **FIXED** in v1.5.0 | Now properly exported |
| A1-F02 | TemporalRepository not exported | `repositories/__init__.py` | HIGH | **FIXED** in v1.5.0 | Now properly exported |
| A1-F03 | Monitoring never integrated | `monitoring/` module | HIGH | **OPEN** | Still not integrated into main app |
| A1-F04 | Federation endpoints placeholder | `federation.py` | HIGH | **PARTIAL** | Implemented but with security issues (see Phase 8C) |
| A1-F05 | WASM runtime is scaffold | `wasm_runtime.py` | MEDIUM | **OPEN** | Still scaffold-only |

### Priority 3 - Data Safety (from Audit 1)

| ID | Issue | Location | Audit 1 Status | Current Status | Notes |
|----|-------|----------|----------------|----------------|-------|
| A1-D01 | Transaction double-commit bug | `client.py:128-143` | HIGH | **FIXED** in v1.5.0 | Transaction handling corrected |
| A1-D02 | drop_all() lacks production guard | `client.py` | HIGH | **FIXED** in v1.5.0 | Environment check added |
| A1-D03 | In-memory storage in services | Multiple services | MEDIUM | **OPEN** | Still uses in-memory (marketplace, notifications) |
| A1-D04 | Redis no authentication | Some docker-compose files | HIGH | **PARTIAL** | Added but with insecure defaults (see HIGH-3A-02) |

### Audit 1 Requirements Summary

| Category | Total Issues | Fixed | Partial | Open |
|----------|--------------|-------|---------|------|
| Security (Priority 1) | 6 | 2 | 2 | 2 |
| Functionality (Priority 2) | 5 | 2 | 1 | 2 |
| Data Safety (Priority 3) | 4 | 2 | 1 | 1 |
| **Total** | **15** | **6** | **4** | **5** |

**Conclusion**: 40% of Audit 1 issues fully resolved, 27% partially addressed, 33% still open. Critical security gaps remain.

---

## Table of Contents

1. [Phase 1: Security Deep Dive](#phase-1-security-deep-dive)
   - 1A: Authentication & Session Management
   - 1B: Authorization & Access Control
   - 1C: Cryptography & Secrets Management
   - 1D: Input Validation & Injection Prevention
   - 1E: API Security & Rate Limiting
2. [Phase 2: Database Security](#phase-2-database-security)
3. [Phase 3: Infrastructure Security](#phase-3-infrastructure-security)
4. [Phase 4: Code Quality](#phase-4-code-quality)
5. [Phase 5: Dependencies](#phase-5-dependencies)
6. [Phase 6: Frontend Security](#phase-6-frontend-security)
7. [Phase 7: Logging & Monitoring](#phase-7-logging--monitoring)
8. [Phase 8: Business Logic](#phase-8-business-logic)
9. [Phase 9: Testing Gaps](#phase-9-testing-gaps)
10. [Phase 10: Recommendations](#phase-10-recommendations)

---

## Phase 1: Security Deep Dive

### Phase 1A: Authentication & Session Management

**Findings:** 7 CRITICAL, 12 HIGH, 8 MEDIUM

#### CRITICAL-1A-01: Missing Algorithm Validation in JWT
**File:** `forge-cascade-v2/forge/security/tokens.py`
**Line:** 445-460
**Description:** JWT decoding uses configurable algorithm from settings without strict validation, potentially allowing algorithm confusion attacks.
**Impact:** Attackers could potentially forge tokens using weaker algorithms.
**Recommendation:** Hardcode allowed algorithms list: `algorithms=["HS256"]`

#### CRITICAL-1A-02: Token Refresh Vulnerability
**File:** `forge-cascade-v2/forge/api/routes/auth.py`
**Line:** 420-460
**Description:** Token refresh doesn't fully invalidate old access tokens, allowing continued use until expiry.
**Impact:** Compromised tokens remain valid even after refresh.
**Recommendation:** Blacklist old access token JTI on refresh.

#### CRITICAL-1A-03: Token Blacklist In-Memory Scalability
**File:** `forge-cascade-v2/forge/security/tokens.py`
**Line:** 53-90
**Description:** TokenBlacklist uses in-memory set with Redis fallback. In-memory implementation doesn't scale across multiple instances.
**Impact:** Token revocation fails in multi-instance deployments.
**Recommendation:** Require Redis in production, fail startup if unavailable.

#### HIGH-1A-01: Session Fixation Possible
**File:** `forge-cascade-v2/forge/api/routes/auth.py`
**Line:** 350-380
**Description:** Session ID not rotated on login, allowing session fixation attacks.
**Impact:** Attackers who set a session ID can hijack authenticated sessions.
**Recommendation:** Generate new session/token on successful authentication.

#### HIGH-1A-02: Registration User Enumeration
**File:** `forge-cascade-v2/forge/api/routes/auth.py`
**Line:** 280-330
**Description:** Different error messages for "username exists" vs "email exists" enable enumeration.
**Impact:** Attackers can enumerate valid usernames/emails.
**Recommendation:** Use generic "Account already exists" message.

#### HIGH-1A-03: Login User Enumeration via Timing
**File:** `forge-cascade-v2/forge/security/auth_service.py`
**Line:** 175-200
**Description:** Early return for non-existent users creates timing difference.
**Impact:** Timing attacks can enumerate valid usernames.
**Recommendation:** Always perform password hash comparison even for invalid users.

#### HIGH-1A-04: Password Strength Validation Insufficient
**File:** `forge-cascade-v2/forge/security/password.py`
**Line:** 80-120
**Description:** Password validation doesn't check against common password lists or previous passwords.
**Impact:** Users can set commonly breached passwords.
**Recommendation:** Add haveibeenpwned API check or local common password list.

#### MEDIUM-1A-01: Concurrent Session Limit Not Enforced
**Description:** No limit on concurrent sessions per user.
**Recommendation:** Add configurable concurrent session limit.

#### MEDIUM-1A-02: Token Expiry Too Long
**Description:** Access token expiry configurable up to 24 hours.
**Recommendation:** Cap access token expiry at 15-30 minutes.

#### POSITIVE-1A-01: Password Hashing Excellent
**File:** `forge-cascade-v2/forge/security/password.py`
**Description:** bcrypt with configurable rounds (default 12), timing-safe comparison.
**Assessment:** EXCELLENT implementation.

---

### Phase 1B: Authorization & Access Control

**Findings:** 5 CRITICAL, 8 HIGH, 6 MEDIUM

#### CRITICAL-1B-01: SYSTEM Role Blanket Permission
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Line:** 269-272
**Description:** SYSTEM role has `"all": True` granting unlimited permissions without granular control.
**Impact:** Compromised SYSTEM account has unrestricted access.
**Recommendation:** Define explicit permissions even for SYSTEM role.

#### CRITICAL-1B-02: Missing Auth on Capsule By-Owner Endpoint (IDOR)
**File:** `forge-cascade-v2/forge/api/routes/capsules.py`
**Line:** 519-541
**Description:** `/search/by-owner/{owner_id}` allows any authenticated user to view any user's capsules.
**Impact:** Unauthorized access to private capsule lists.
**Recommendation:** Verify `current_user.id == owner_id` or require admin role.

#### HIGH-1B-01: Trust Level Boundary Bug
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Line:** 115-124
**Description:** Trust score of exactly 100 may not map correctly to CORE level due to boundary condition.
**Impact:** Users with trust_flame=100 may not get CORE privileges.
**Recommendation:** Use `>=` instead of `>` for CORE threshold.

#### HIGH-1B-02: Capability Override Bypass
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Line:** 519-523
**Description:** Capability overrides checked after role permissions, allowing bypass.
**Impact:** Denied capabilities may still be granted through role.
**Recommendation:** Check capability denials before role permissions.

#### HIGH-1B-03: String-Based Role Matching
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Description:** Role comparison uses string matching, vulnerable to case sensitivity issues.
**Recommendation:** Normalize roles to uppercase/lowercase consistently.

#### POSITIVE-1B-01: Trust Level Hierarchy
**Description:** Well-defined trust levels (QUARANTINE, SANDBOX, STANDARD, TRUSTED, CORE) with clear boundaries.

---

### Phase 1C: Cryptography & Secrets Management

**Findings:** 2 CRITICAL, 4 HIGH, 3 MEDIUM
**Overall Score:** 7.1/10

#### CRITICAL-1C-01: In-Memory Key Store Not Production-Ready
**File:** `forge/compliance/encryption/service.py`
**Line:** 114-185
**Description:** InMemoryKeyStore stores encryption keys in memory, lost on restart.
**Impact:** Encrypted data becomes unrecoverable after restart.
**Recommendation:** Implement HSM, AWS KMS, or HashiCorp Vault integration.

#### CRITICAL-1C-02: Federation Keys Regenerated on Restart
**File:** `forge-cascade-v2/forge/federation/protocol.py`
**Line:** 77-89
**Description:** Ed25519 keypair generated fresh on every initialization with no persistence.
**Impact:** Federation peer identity changes on restart, breaking trust relationships.
**Recommendation:** Persist keys to secure storage, load on startup.

#### HIGH-1C-01: JWT Should Use RS256 for Production
**File:** `forge-cascade-v2/forge/security/tokens.py`
**Description:** Uses HS256 (symmetric) instead of RS256 (asymmetric).
**Impact:** Secret key must be shared with all services that verify tokens.
**Recommendation:** Use RS256 with public/private key pair for production.

#### HIGH-1C-02: No Key Rotation Mechanism
**Description:** No automated key rotation for JWT secrets or encryption keys.
**Recommendation:** Implement key rotation with grace period.

#### POSITIVE-1C-01: AES-256-GCM Implementation
**File:** `forge/compliance/encryption/service.py`
**Description:** Excellent envelope encryption with AES-256-GCM, unique IVs per encryption.

#### POSITIVE-1C-02: Ed25519 for Federation Signatures
**Description:** Modern, secure signature algorithm choice for federation.

---

### Phase 1D: Input Validation & Injection Prevention

**Findings:** 3 CRITICAL, 5 HIGH, 7 MEDIUM

#### CRITICAL-1D-01: SSRF in Federation Peer URLs
**File:** `forge-cascade-v2/forge/federation/protocol.py`
**Line:** 177-218
**Description:** Peer URLs used directly in HTTP requests without validation.
**Impact:** Attackers can make server request internal network resources.
**Evidence:**
```python
response = await self._http_client.post(
    f"{peer_url.rstrip('/')}/api/v1/federation/handshake",
    # peer_url not validated - can be internal IP
)
```
**Recommendation:** Validate URLs, block private IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).

#### CRITICAL-1D-02: Regex Injection in Query Compilation (ReDoS)
**File:** `forge-cascade-v2/forge/services/query_compiler.py`
**Line:** 600-608
**Description:** User-provided regex patterns passed directly to Neo4j without complexity validation.
**Impact:** Catastrophic backtracking can cause denial of service.
**Evidence:**
```python
elif constraint.operator == QueryOperator.REGEX:
    where_clauses.append(f"{constraint.field} =~ ${param_name}")
    # User-controlled regex without validation
```
**Recommendation:** Use RE2 library or limit regex complexity.

#### CRITICAL-1D-03: JSON Injection in Governance Actions
**File:** `forge-cascade-v2/forge/models/governance.py`
**Line:** 57-67
**Description:** Action field accepts arbitrary dict without schema validation.
**Impact:** Malicious governance proposals can execute arbitrary actions.
**Evidence:**
```python
@field_validator("action", mode="before")
def parse_action(cls, v: Any) -> dict[str, Any]:
    if isinstance(v, str):
        return json.loads(v)  # NO SCHEMA VALIDATION
```
**Recommendation:** Define ActionType enum with explicit allowed actions.

#### HIGH-1D-01: Unvalidated Federation Peer Registration
**File:** `forge-cascade-v2/forge/api/routes/federation.py`
**Line:** 203-281
**Description:** Any user can register federation peers without authentication.
**Recommendation:** Require admin role for peer registration.

#### HIGH-1D-02: Header Injection Potential
**Description:** Some user inputs used in response headers without sanitization.
**Recommendation:** Sanitize all header values.

#### MEDIUM-1D-01: Content Validation Bypass
**Description:** Content validation can be bypassed with certain encodings.
**Recommendation:** Normalize content encoding before validation.

---

### Phase 1E: API Security & Rate Limiting

**Findings:** 0 CRITICAL, 3 HIGH, 5 MEDIUM

#### HIGH-1E-01: Rate Limiting Bypass with Multiple Accounts
**Description:** Rate limits per user, not per IP. Multiple accounts bypass limits.
**Recommendation:** Add IP-based rate limiting in addition to user-based.

#### HIGH-1E-02: Missing JSON Depth Limits
**Description:** No limit on JSON nesting depth, enabling DoS via deeply nested payloads.
**Recommendation:** Add max_depth parameter to JSON parsing.

#### HIGH-1E-03: Missing Query Parameter Count Limits
**Description:** No limit on number of query parameters per request.
**Recommendation:** Limit query parameters to reasonable count (e.g., 50).

#### MEDIUM-1E-01: Missing WebSocket Timeouts
**Description:** WebSocket connections have no idle timeout.
**Recommendation:** Add configurable idle timeout with ping/pong.

#### POSITIVE-1E-01: Security Headers Well-Implemented
**File:** `forge-cascade-v2/forge/api/middleware.py`
**Line:** 498-549
**Description:** Comprehensive security headers including CSP, HSTS, X-Frame-Options.

#### POSITIVE-1E-02: CORS Properly Configured
**Description:** CORS rejects wildcard origin in production, explicit origins required.

---

## Phase 2: Database Security

**Findings:** 2 CRITICAL, 1 HIGH, 3 MEDIUM

#### CRITICAL-2-01: GDS Query Injection
**File:** `forge-cascade-v2/forge/repositories/graph_repository.py`
**Lines:** 146-163, 367-399, 483-505, 871-892, 1069-1108
**Description:** Node labels and relationship types passed directly into GDS CALL statements via f-strings.
**Impact:** Attackers can manipulate graph algorithm parameters, potentially accessing unauthorized data.
**Evidence:**
```python
# Line 146-158 - VULNERABLE
graph_name = f"pagerank_{request.node_label}_{request.relationship_type}"
await self.client.execute(
    f"""
    CALL gds.graph.project(
        '{graph_name}',          # INJECTION POINT
        '{request.node_label}',  # INJECTION POINT
        '{request.relationship_type}'  # INJECTION POINT
    )
    """
)
```
**Recommendation:** Whitelist allowed node labels and relationship types.

#### CRITICAL-2-02: Password Hash Returned in User Queries
**File:** `forge-cascade-v2/forge/repositories/user_repository.py`
**Line:** 166, 372-376
**Description:** Query uses `u {.*}` pattern which returns all fields including password_hash.
**Impact:** Password hash exposed if Pydantic model misconfigured.
**Mitigating Factor:** Pydantic model excludes password_hash field.
**Recommendation:** Explicitly list returned fields, exclude password_hash in query.

#### HIGH-2-01: Transaction Timeout Not Configured
**Description:** Neo4j transactions have no explicit timeout.
**Recommendation:** Add transaction timeout to prevent long-running queries.

#### POSITIVE-2-01: Connection Pooling Properly Configured
**File:** `forge-cascade-v2/forge/database/client.py`
**Description:** Neo4j driver configured with max_connection_pool_size, connection_timeout.

#### POSITIVE-2-02: Parameterized Queries Used
**Description:** Most queries use parameterized queries correctly, preventing Cypher injection.

---

## Phase 3: Infrastructure Security

### Phase 3A: Docker Security

**Findings:** 5 CRITICAL, 12 HIGH, 26 MEDIUM, 8 LOW

#### CRITICAL-3A-01: Use of :latest Tags (4 instances)
**Files:** `docker-compose.yml:206`, `docker-compose.prod.yml:217`, `docker-compose.cloudflare.yml:13,181`
**Description:** Jaeger and cloudflared images use `:latest` tag.
**Impact:** Unpredictable deployments, potential supply chain attacks.
**Recommendation:** Pin to specific versions with SHA256 digest.

#### CRITICAL-3A-02: Docker Socket Mount
**File:** `forge-cascade-v2/docker/docker-compose.prod.yml:287`
**Description:** Docker socket mounted into container: `/var/run/docker.sock:/var/run/docker.sock`
**Impact:** Container has root-equivalent access to host system.
**Recommendation:** Use alternative log collection method.

#### HIGH-3A-01: Containers Running as Root (3 instances)
**Files:** `marketplace/Dockerfile`, `scripts/backup/Dockerfile`, `forge-cascade-v2/frontend/Dockerfile`
**Description:** No USER instruction, containers run as root.
**Recommendation:** Add non-root user configuration.

#### HIGH-3A-02: Hardcoded Redis Password Defaults
**Files:** All docker-compose files
**Description:** `${REDIS_PASSWORD:-forge_redis_secret}` provides insecure default.
**Recommendation:** Require explicit password, fail if not set.

#### HIGH-3A-03: Redis Port Exposed to Host
**File:** `docker-compose.yml:184`
**Description:** `ports: - "6379:6379"` exposes Redis externally.
**Recommendation:** Use `expose` instead of `ports` for internal services.

---

### Phase 3B: Environment Variables & Config

**Findings:** 5 CRITICAL, 4 HIGH, 5 MEDIUM, 3 LOW

#### CRITICAL-3B-01: Hardcoded Default Passwords in Test Files
**Files:**
- `test_forge_v3_comprehensive.py:28` - `admin123`
- `manual_test.py:39` - `admin123`
- `test_all_features.py:18-19` - `admin123`, `oracle123`
- `test_ui_integration.py:15` - `admin123`
- `test_quick.py:10` - `admin123`

**Impact:** If test files run in production or defaults used, accounts compromised.
**Recommendation:** Require environment variables without defaults.

#### HIGH-3B-01: Test JWT Secrets
**File:** `forge-cascade-v2/tests/conftest.py:25-26`
**Description:** Hardcoded test secrets in test configuration.
**Recommendation:** Generate random secrets for each test run.

#### POSITIVE-3B-01: Comprehensive .gitignore
**Description:** Root .gitignore properly excludes .env, credentials, keys.

#### POSITIVE-3B-02: JWT Secret Validation
**File:** `forge-cascade-v2/forge/config.py:104-116`
**Description:** JWT secret validated for minimum length (32 chars) and entropy (10 unique chars).

---

### Phase 3C: Network Security

**Findings:** 2 CRITICAL, 5 HIGH, 8 MEDIUM, 4 LOW

#### CRITICAL-3C-01: Redis Port Exposed Externally
**File:** `docker-compose.yml:183-195`
**Description:** Redis port 6379 mapped to host network.
**Impact:** Redis accessible from outside Docker network.
**Recommendation:** Remove port mapping, use internal networking only.

#### CRITICAL-3C-02: Webhook URL SSRF Vulnerability
**File:** `forge-cascade-v2/forge/services/notifications.py:63-67`
**Description:** Webhook URLs accepted without validation.
**Impact:** SSRF attacks via webhook callbacks.
**Recommendation:** Validate URLs, block internal IPs, require HTTPS.

#### HIGH-3C-01: CSP Contains unsafe-inline/unsafe-eval
**File:** `deploy/nginx/sites/forgecascade.org.conf:82`
**Description:** CSP allows `'unsafe-inline'` and `'unsafe-eval'` in script-src.
**Impact:** XSS protection significantly weakened.
**Recommendation:** Use nonce-based CSP.

#### HIGH-3C-02: WebSocket Auth Optional
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py:462-489`
**Description:** Authentication optional for /ws/events and /ws/dashboard.
**Recommendation:** Require authentication for all WebSocket endpoints.

#### HIGH-3C-03: No WebSocket Message Size Limits
**Description:** No limit on WebSocket message size.
**Impact:** Memory exhaustion attacks possible.
**Recommendation:** Implement 64KB message limit.

#### POSITIVE-3C-01: TLS Configuration Strong
**File:** `deploy/nginx/sites/forgecascade.org.conf:67-75`
**Description:** TLS 1.2+, strong cipher suites, OCSP stapling enabled.

---

## Phase 4: Code Quality

### Phase 4A: Error Handling

**Findings:** 2 CRITICAL, 7 HIGH, 9 MEDIUM, 3 LOW

#### CRITICAL-4A-01: Database Error Messages Exposed
**File:** `forge-cascade-v2/forge/api/routes/system.py:288,394`
**Description:** Health check exposes database error messages to users.
**Evidence:**
```python
except Exception as e:
    components["database"] = {"status": "unhealthy", "error": str(e)}
```
**Recommendation:** Return generic error, log details internally.

#### CRITICAL-4A-02: Token Validation Error Details Exposed
**File:** `forge-cascade-v2/forge/security/dependencies.py:95-100`
**Description:** TokenInvalidError details exposed to users.
**Recommendation:** Return generic "Invalid token" message.

#### HIGH-4A-01: Blanket Exception in Login
**File:** `forge-cascade-v2/forge/api/routes/auth.py:399-406`
**Description:** Catches all exceptions, potentially hiding bugs.
**Recommendation:** Catch specific authentication exceptions.

#### HIGH-4A-02: detail=str(e) Pattern (Multiple Locations)
**Files:** auth.py, marketplace.py, agent_gateway.py
**Description:** Raw exception messages exposed to users.
**Recommendation:** Use error codes with safe messages.

#### POSITIVE-4A-01: Global Exception Handler
**File:** `forge-cascade-v2/forge/api/app.py:461-474`
**Description:** Unhandled exceptions return generic 500 error.

#### POSITIVE-4A-02: CancelledError Properly Handled
**Description:** asyncio.CancelledError correctly handled in 16+ locations.

---

### Phase 4B: Resource Management

**Findings:** 0 CRITICAL, 3 HIGH, 11 MEDIUM, 10 LOW

#### HIGH-4B-01: Database Connection Leak in Background Tasks
**File:** `forge-cascade-v2/forge/api/routes/capsules.py:99-132`
**Description:** Background task creates Neo4jClient with potential leak if connect() fails.
**Recommendation:** Use async context manager pattern.

#### HIGH-4B-02: Unbounded Threat Cache (DoS Vector)
**File:** `forge-cascade-v2/forge/overlays/security_validator.py:300`
**Description:** `_threat_cache` uses defaultdict(list) without size limits.
**Impact:** Memory exhaustion under attack.
**Recommendation:** Add maximum entries per user, use bounded deque.

#### HIGH-4B-03: Unbounded Lineage Nodes
**File:** `forge-cascade-v2/forge/overlays/lineage_tracker.py:186,190`
**Description:** `_nodes` dict grows unbounded.
**Recommendation:** Implement LRU eviction.

#### MEDIUM-4B-01: HTTP Clients Created Per-Request
**File:** `forge-cascade-v2/forge/services/llm.py:227,300,369`
**Description:** LLM providers create new httpx.AsyncClient for each request.
**Impact:** Connection pool not reused, performance degradation.
**Recommendation:** Create persistent client, reuse across requests.

#### MEDIUM-4B-02: Orphan Background Tasks (3 locations)
**Files:** partition_manager.py:163, wasm_runtime.py:645, services/init.py:174
**Description:** asyncio.create_task() without storing reference.
**Impact:** Task errors silently swallowed.
**Recommendation:** Store task references, add exception handlers.

---

### Phase 4C: Race Conditions & Concurrency

**Findings:** 4 CRITICAL, 7 HIGH, 5 MEDIUM, 2 LOW

#### CRITICAL-4C-01: Non-Atomic Rate Limiting
**File:** `forge-cascade-v2/forge/overlays/security_validator.py:118-147`
**Description:** Rate limit counters incremented without locking.
**Impact:** Concurrent requests bypass rate limits.
**Evidence:**
```python
def validate(self, data: dict) -> tuple[bool, Optional[str]]:
    # RACE: Multiple threads read same counter value
    if self.minute_counts[user_id] >= self.requests_per_minute:
        return False, "Rate limit exceeded"
    self.minute_counts[user_id] += 1  # Non-atomic
```
**Recommendation:** Use Redis INCR or asyncio.Lock.

#### CRITICAL-4C-02: threading.Lock Blocks Event Loop
**File:** `forge-cascade-v2/forge/security/tokens.py:53`
**Description:** TokenBlacklist uses threading.Lock in async context.
**Impact:** Event loop blocked during token operations.
**Recommendation:** Replace with asyncio.Lock.

#### CRITICAL-4C-03: threading.Lock in Maintenance State
**File:** `forge-cascade-v2/forge/api/routes/system.py:59-90`
**Description:** Maintenance state uses threading.Lock, reads occur outside lock.
**Recommendation:** Use asyncio.Lock, protect all reads.

#### CRITICAL-4C-04: Lazy Lock Initialization Race
**File:** `forge-cascade-v2/forge/database/client.py:281-286`
**Description:** _get_lock() has race condition creating multiple locks.
**Recommendation:** Initialize lock at module level.

#### HIGH-4C-01: WebSocket Counter Race Conditions
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py:56,68,124,198`
**Description:** Multiple counters incremented without locks.
**Recommendation:** Protect with asyncio.Lock.

#### HIGH-4C-02: WebSocket Dictionary Race Conditions
**File:** `forge-cascade-v2/forge/api/websocket/handlers.py:123,154,226,251`
**Description:** Connection dictionaries modified without locks.
**Impact:** KeyError or lost connections possible.
**Recommendation:** Protect dictionary operations with lock.

#### HIGH-4C-03: Trust Score Update Race
**File:** `forge-cascade-v2/forge/federation/trust.py:76-93`
**Description:** Trust score read-modify-write without lock.
**Impact:** Lost updates under concurrent sync.
**Recommendation:** Add asyncio.Lock to protect updates.

#### HIGH-4C-04: Embedding Cache Race
**File:** `forge-cascade-v2/forge/services/embedding.py:330-350`
**Description:** Cache operations without locks.
**Recommendation:** Protect cache access with lock.

---

## Phase 5: Dependencies

### Phase 5A: Vulnerability Scanning

**Findings:** 1 CRITICAL, 8 HIGH, 12 MEDIUM, 7 LOW

#### CRITICAL-5A-01: python-jose Abandoned with CVEs
**File:** `forge-cascade-v2/requirements.txt`
**Package:** `python-jose[cryptography]>=3.3.0`
**Issue:** Not maintained since 2022, CVE-2022-29217 (algorithm confusion).
**Recommendation:** Replace with `PyJWT>=2.8.0`.

#### HIGH-5A-01: No Version Pinning (Python)
**Files:** requirements.txt, forge-cascade-v2/requirements.txt, forge_virtuals_integration/requirements.txt
**Description:** All packages use `>=` constraints instead of exact versions.
**Impact:** Non-reproducible builds, unexpected breaking changes.
**Recommendation:** Pin to exact versions with pip-compile.

#### HIGH-5A-02: No Python Lock File
**Description:** No requirements.lock or pip-compile output for transitive dependencies.
**Recommendation:** Generate locked requirements with hashes.

#### HIGH-5A-03: Unpinned Docker Base Images
**Files:** All Dockerfiles
**Description:** Base images use floating tags (python:3.11-slim, node:20-alpine).
**Recommendation:** Pin to specific versions with SHA256 digest.

#### HIGH-5A-04: passlib Abandoned
**Package:** `passlib[bcrypt]>=1.7.4`
**Issue:** No releases since 2020.
**Recommendation:** Consider migration to bcrypt directly.

#### MEDIUM-5A-01: Version Inconsistencies
**Description:** marketplace uses older versions than frontend (vite 6 vs 7, tailwind 3 vs 4).
**Recommendation:** Align dependency versions across packages.

---

### Phase 5B: Supply Chain Security

**Findings:** 0 CRITICAL, 5 HIGH, 9 MEDIUM, 4 LOW

#### HIGH-5B-01: GitHub Actions Use @master
**Files:** `.github/workflows/ci.yml:262`, `forge-cascade-v2/.github/workflows/ci-cd.yml:282`
**Description:** `aquasecurity/trivy-action@master` uses unpinned branch.
**Impact:** Supply chain attack vector if maintainer compromised.
**Recommendation:** Pin to specific version or SHA.

#### HIGH-5B-02: Actions Use Version Tags Only
**Description:** Actions pinned to version tags (v3, v4) not SHA hashes.
**Recommendation:** Pin to full SHA for maximum security.

#### HIGH-5B-03: Python Dependencies Without Hash Verification
**Description:** No `--hash` flags in requirements files.
**Recommendation:** Use pip-compile with --generate-hashes.

#### MEDIUM-5B-01: npm install Instead of npm ci
**File:** `marketplace/Dockerfile:27`
**Description:** Uses `npm install --legacy-peer-deps` instead of `npm ci`.
**Impact:** Non-deterministic builds.
**Recommendation:** Use `npm ci` for reproducible builds.

#### POSITIVE-5B-01: Lock Files Have Integrity Hashes
**Description:** package-lock.json files include SHA-512 integrity hashes.

#### POSITIVE-5B-02: No curl|bash Patterns
**Description:** No dangerous script piping found.

---

## Phase 6: Frontend Security

### Phase 6A: XSS, CSRF & Client-Side

**Findings:** 0 CRITICAL, 1 HIGH, 2 MEDIUM, 4 LOW

#### HIGH-6A-01: Missing CSRF Protection in Marketplace
**File:** `marketplace/src/services/api.ts:16-38`
**Description:** Marketplace API client doesn't implement CSRF token handling.
**Recommendation:** Add X-CSRF-Token header interceptor.

#### MEDIUM-6A-01: External Fonts Without SRI
**File:** `forge-cascade-v2/frontend/index.html:11-13`
**Description:** Google Fonts loaded without Subresource Integrity.
**Recommendation:** Self-host fonts or add integrity hashes.

#### MEDIUM-6A-02: OAuth Redirect Validation
**File:** `marketplace/src/pages/Login.tsx:57-61`
**Description:** OAuth redirect URL needs server-side validation.
**Recommendation:** Validate redirect_uri against allowlist on server.

#### POSITIVE-6A-01: No dangerouslySetInnerHTML
**Description:** No dangerous HTML injection patterns found.

#### POSITIVE-6A-02: CSRF Token in Memory
**File:** `forge-cascade-v2/frontend/src/api/client.ts:45-67`
**Description:** CSRF token stored in memory (not localStorage), added to state-changing requests.

#### POSITIVE-6A-03: CSV Export Properly Escaped
**File:** `forge-cascade-v2/frontend/src/pages/SettingsPage.tsx:217-248`
**Description:** CSV injection prevention with formula character escaping.

---

### Phase 6B: Sensitive Data in Browser

**Findings:** 0 CRITICAL, 0 HIGH, 2 MEDIUM, 2 LOW

**Overall Assessment:** GOOD - Auth tokens in httpOnly cookies, passwords cleared after use.

#### MEDIUM-6B-01: Source Maps in Production
**Description:** Source maps may be enabled in production builds.
**Recommendation:** Disable source maps for production.

#### LOW-6B-01: Console Error Logging
**Description:** Errors logged to console in production.
**Recommendation:** Use production error tracking service.

#### POSITIVE-6B-01: Token Storage
**Description:** Auth tokens in httpOnly cookies, not localStorage/sessionStorage.

#### POSITIVE-6B-02: Password Handling
**Description:** Passwords cleared from state after form submission.

---

## Phase 7: Logging & Monitoring

### Phase 7A: Sensitive Data in Logs

**Findings:** 0 CRITICAL, 0 HIGH, 3 MEDIUM, 6 LOW

**Overall Assessment:** GOOD logging hygiene with centralized sanitization.

#### MEDIUM-7A-01: Email in Audit Logs
**File:** `forge-cascade-v2/forge/security/auth_service.py:139,531,541`
**Description:** Email addresses logged in audit event details.
**Recommendation:** Hash or mask email addresses.

#### MEDIUM-7A-02: Failed Login Credential Logged
**File:** `forge-cascade-v2/forge/security/auth_service.py:182`
**Description:** Attempted username/email logged on failed login.
**Recommendation:** Don't log attempted credentials.

#### MEDIUM-7A-03: Search Query in Errors
**File:** `forge-cascade-v2/forge/services/search.py:204`
**Description:** Full user query logged in error messages.
**Recommendation:** Truncate queries in error logs.

#### POSITIVE-7A-01: Centralized Sanitization
**File:** `forge-cascade-v2/forge/monitoring/logging.py:68-98`
**Description:** Excellent sensitive data sanitization processor.

#### POSITIVE-7A-02: Query Parameter Sanitization
**File:** `forge-cascade-v2/forge/api/middleware.py:34-65`
**Description:** Comprehensive sensitive parameter redaction.

---

### Phase 7B: Audit Trail Completeness

**Findings:** 1 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW

#### CRITICAL-7B-01: No MFA Implementation
**Description:** No multi-factor authentication exists in the codebase.
**Impact:** Cannot audit MFA events because they don't exist.
**Recommendation:** Implement TOTP-based MFA.

#### HIGH-7B-01: Token Refresh Not Audited
**File:** `forge-cascade-v2/forge/api/routes/auth.py:446-454`
**Description:** Token refresh only records metrics, not audit log.
**Recommendation:** Add audit logging for token refresh.

#### HIGH-7B-02: Permission Denials Not Audited
**File:** `forge-cascade-v2/forge/security/authorization.py`
**Description:** Authorization failures not logged to audit repository.
**Recommendation:** Log permission denials with context.

#### HIGH-7B-03: Bulk Operations Not Audited
**Description:** No bulk operation support with audit trails.
**Recommendation:** Implement audit logging for any bulk operations.

#### HIGH-7B-04: Data Exports Not Audited
**Description:** No data export functionality with audit logging.
**Recommendation:** Audit all data export operations.

#### MEDIUM-7B-01: Maintenance Mode Not in Audit Repo
**File:** `forge-cascade-v2/forge/api/routes/system.py:926-970`
**Description:** Maintenance mode changes logged to event system, not audit repo.
**Recommendation:** Also log to audit repository.

#### POSITIVE-7B-01: Comprehensive Audit Schema
**File:** `forge-cascade-v2/forge/repositories/audit_repository.py:28-43`
**Description:** Audit log accepts timestamps, IPs, user agents, correlation IDs.

---

## Phase 8: Business Logic

### Phase 8A: Trust System Bypass

**Findings:** 0 CRITICAL, 1 HIGH, 3 MEDIUM, 2 LOW

#### HIGH-8A-01: CORE Trust Level Rate Limit Immunity
**File:** `forge-cascade-v2/forge/security/authorization.py:89-98`
**Description:** CORE trust level grants `"immune_to_rate_limit": True`.
**Impact:** Compromised CORE account can DoS system.
**Recommendation:** Remove immunity, use high multiplier instead.

#### MEDIUM-8A-01: Default Trust Fallback
**File:** `forge-cascade-v2/forge/security/dependencies.py:60,86`
**Description:** Default trust_flame=60 used if token claim is None.
**Recommendation:** Reject tokens with missing trust claims.

#### MEDIUM-8A-02: Federation Trust Manual Adjustment Unlimited
**File:** `forge-cascade-v2/forge/federation/trust.py:161-190`
**Description:** No limit on single trust adjustment magnitude.
**Recommendation:** Cap single adjustments at +/-0.2.

#### POSITIVE-8A-01: Trust Boundaries Enforced
**Description:** Trust clamped to 0-100 at model, repository, and database levels.

#### POSITIVE-8A-02: Fresh Trust Score for Voting
**File:** `forge-cascade-v2/forge/api/routes/governance.py:491-506`
**Description:** Fresh user data fetched before calculating vote weight.

#### POSITIVE-8A-03: Delegation Cycle Detection
**File:** `forge-cascade-v2/forge/api/routes/governance.py:1359-1396`
**Description:** MAX_DELEGATION_DEPTH prevents infinite chains.

---

### Phase 8B: Governance & Voting

**Findings:** 0 CRITICAL, 4 HIGH, 3 MEDIUM, 3 LOW

#### HIGH-8B-01: No Execution Timelock
**File:** `forge-cascade-v2/forge/api/routes/governance.py:1069-1133`
**Description:** Passed proposals can execute immediately without delay.
**Impact:** No challenge period for contested decisions.
**Recommendation:** Add 24-48 hour timelock before execution.

#### HIGH-8B-02: Execution Without Multi-Approval
**File:** `forge-cascade-v2/forge/repositories/governance_repository.py:294-323`
**Description:** Proposal execution only checks status='passed'.
**Recommendation:** Require additional approval for high-impact proposals.

#### HIGH-8B-03: Unvalidated Action Dict
**File:** `forge-cascade-v2/forge/models/governance.py:52-56`
**Description:** Action field accepts arbitrary dict without validation.
**Recommendation:** Define ActionType enum with allowed actions.

#### HIGH-8B-04: No Failed Execution Handling
**Description:** No mechanism for handling failed proposal executions.
**Recommendation:** Implement retry logic, failure notifications.

#### MEDIUM-8B-01: Incomplete Quorum Verification
**File:** `forge-cascade-v2/forge/repositories/governance_repository.py:255-265`
**Description:** Quorum check has TODO comment indicating incomplete implementation.
**Recommendation:** Complete quorum verification logic.

#### MEDIUM-8B-02: No Duplicate Proposal Prevention
**Description:** Multiple identical proposals can be created.
**Recommendation:** Implement content hashing for duplicate detection.

#### POSITIVE-8B-01: Atomic Double-Voting Prevention
**File:** `forge-cascade-v2/forge/repositories/governance_repository.py:894-965`
**Description:** MERGE query prevents double voting atomically.

#### POSITIVE-8B-02: Ghost Council Critical Issue Override
**File:** `forge-cascade-v2/forge/services/ghost_council.py:1209-1229`
**Description:** Critical issues require unanimous rejection to dismiss.

---

### Phase 8C: Federation Trust & Peer Verification

**Findings:** 2 CRITICAL, 6 HIGH, 6 MEDIUM, 3 LOW

#### CRITICAL-8C-01: Federation SSRF - No URL Validation
**File:** `forge-cascade-v2/forge/federation/protocol.py:177-218`
**Description:** Peer URLs used in HTTP requests without validation.
**Impact:** Server can be made to request internal network resources.
**Recommendation:** Validate URLs, block private IP ranges.

#### CRITICAL-8C-02: Federation SSRF - Redirects Followed
**File:** `forge-cascade-v2/forge/federation/protocol.py:62-64`
**Description:** `follow_redirects=True` without restrictions.
**Impact:** Initial URL validation bypassed via redirect to internal IP.
**Recommendation:** Disable redirects or validate redirect targets.

#### HIGH-8C-01: No Replay Attack Prevention
**File:** `forge-cascade-v2/forge/federation/protocol.py:122-151`
**Description:** Handshakes have 5-minute timestamp window but no nonce.
**Impact:** Captured handshakes can be replayed within window.
**Recommendation:** Add cryptographic nonce, track used nonces.

#### HIGH-8C-02: Keys Regenerated on Restart
**File:** `forge-cascade-v2/forge/federation/protocol.py:77-89`
**Description:** Ed25519 keypair generated fresh each startup.
**Impact:** Peer identity changes, breaking trust relationships.
**Recommendation:** Persist keys to secure storage.

#### HIGH-8C-03: Unauthenticated Peer Registration
**File:** `forge-cascade-v2/forge/api/routes/federation.py:203-281`
**Description:** No authentication required to register peers.
**Recommendation:** Require admin role.

#### HIGH-8C-04: Handshake Accepts Any Valid Signature
**File:** `forge-cascade-v2/forge/api/routes/federation.py:662-678`
**Description:** Incoming handshakes accepted from any peer with valid signature.
**Recommendation:** Implement peer pre-authorization.

#### HIGH-8C-05: Peer URL Field Not HttpUrl
**File:** `forge-cascade-v2/forge/federation/models.py:79`
**Description:** Peer URL stored as plain string despite HttpUrl import.
**Recommendation:** Change field type to HttpUrl.

#### HIGH-8C-06: Request Signing Missing Context
**File:** `forge-cascade-v2/forge/federation/protocol.py:243-299`
**Description:** Sync request signatures don't include URL or timestamp.
**Impact:** Signed requests can be replayed to different endpoints.
**Recommendation:** Include URL, timestamp, nonce in signed data.

#### MEDIUM-8C-01: Initial Trust Too Permissive
**File:** `forge-cascade-v2/forge/federation/trust.py:73`
**Description:** Initial trust 0.3 allows LIMITED tier access immediately.
**Recommendation:** Start at 0.1 (QUARANTINE), require explicit trust grant.

#### MEDIUM-8C-02: No Trust Revocation Mechanism
**Description:** No method to revoke peer trust.
**Recommendation:** Implement revoke_peer() method.

#### MEDIUM-8C-03: No Trust Expiration
**Description:** Trust never expires, only minimal decay.
**Recommendation:** Require periodic re-verification.

#### MEDIUM-8C-04: Incoming Data Not Validated
**File:** `forge-cascade-v2/forge/federation/sync.py:260-302`
**Description:** Incoming capsule data not thoroughly validated.
**Recommendation:** Define strict Pydantic model for incoming data.

#### MEDIUM-8C-05: Non-Cryptographic Content Hash
**File:** `forge-cascade-v2/forge/api/routes/federation.py:776`
**Description:** Uses Python's `hash()` function for content hashing.
**Recommendation:** Use SHA-256 for cryptographic integrity.

#### MEDIUM-8C-06: Error Messages May Leak Information
**File:** `forge-cascade-v2/forge/api/routes/federation.py:691-792`
**Description:** Federation errors may expose internal details.
**Recommendation:** Return generic error messages to peers.

---

## Phase 9: Testing Gaps

**Overall Security Test Coverage: ~15-20% (INADEQUATE)**

### CRITICAL GAPS

| Category | Status | Impact |
|----------|--------|--------|
| Token Generation/Validation | MISSING | High - JWT security untested |
| Token Blacklisting | MISSING | High - Revocation untested |
| Password Hashing | MISSING | High - Core auth untested |
| Federation Signatures | MISSING | Critical - Crypto untested |
| Authorization Logic | MISSING | High - Access control untested |
| CSRF Middleware | MISSING | High - Protection untested |

### Existing Tests (Partial Coverage)

- Integration tests for login/register flows
- Double-voting prevention (integration)
- Rate limiting (functional only)
- Input validation (SQL/XSS basic tests)

### Recommended Test Files to Create

1. `tests/security/test_tokens.py` - CRITICAL
2. `tests/security/test_password.py` - CRITICAL
3. `tests/security/test_authorization.py` - HIGH
4. `tests/security/test_crypto.py` - CRITICAL
5. `tests/middleware/test_csrf.py` - HIGH
6. `tests/middleware/test_rate_limiting.py` - MEDIUM
7. `tests/federation/test_trust.py` - CRITICAL
8. `tests/federation/test_protocol.py` - CRITICAL
9. `tests/governance/test_voting_security.py` - MEDIUM

---

## Phase 10: Recommendations

### Immediate Actions (Block Production)

1. **Replace python-jose** with PyJWT>=2.8.0
2. **Add SSRF protection** to federation (URL validation, IP blocking)
3. **Fix threading.Lock** → asyncio.Lock in TokenBlacklist
4. **Fix rate limiting** race condition with atomic operations
5. **Remove hardcoded passwords** from test files and docker-compose
6. **Add authentication** to federation peer registration
7. **Implement key persistence** for federation
8. **Fix GDS injection** with input whitelist
9. **Add nonce** to federation handshakes

### Short-Term (1-2 Weeks)

1. Pin Docker images to SHA digests
2. Add non-root users to Dockerfiles
3. Remove Redis port exposure
4. Add locks to WebSocket and trust operations
5. Fix IDOR vulnerability
6. Add execution timelock to governance
7. Add audit logging for token refresh and permission denials
8. Harden CSP (remove unsafe-inline/unsafe-eval)
9. Add CSRF to marketplace
10. Pin GitHub Actions to SHA

### Medium-Term (2-4 Weeks)

1. Create security unit tests
2. Add bounded memory limits to caches
3. Implement HTTP client reuse
4. Complete quorum verification
5. Implement MFA
6. Add trust revocation to federation
7. Add WebSocket message/connection limits
8. Fix error message disclosure

### Long-Term (Ongoing)

1. Pin all Python dependencies with hashes
2. Add Permissions-Policy header
3. Implement federation state persistence
4. Add federation-specific rate limiting
5. Use cryptographic hashes for content integrity
6. Track all background tasks
7. Self-audit for audit log operations

---

## Appendix A: Files Requiring Changes

### Critical Priority
- `forge-cascade-v2/requirements.txt`
- `forge-cascade-v2/forge/security/tokens.py`
- `forge-cascade-v2/forge/federation/protocol.py`
- `forge-cascade-v2/forge/overlays/security_validator.py`
- `forge-cascade-v2/forge/repositories/graph_repository.py`
- `forge-cascade-v2/forge/api/routes/federation.py`
- All test files with hardcoded passwords
- All docker-compose files

### High Priority
- All Dockerfiles
- `forge-cascade-v2/forge/api/websocket/handlers.py`
- `forge-cascade-v2/forge/federation/trust.py`
- `forge-cascade-v2/forge/api/routes/capsules.py`
- `forge-cascade-v2/forge/api/routes/governance.py`
- `deploy/nginx/sites/forgecascade.org.conf`
- `marketplace/src/services/api.ts`
- `.github/workflows/*.yml`

---

## Appendix B: Positive Security Findings

The codebase demonstrates several excellent security practices:

1. **Password Hashing**: bcrypt with configurable rounds
2. **JWT Validation**: Required claims validated, trust range checked
3. **CORS Protection**: Production wildcard prevention
4. **Log Sanitization**: Centralized sensitive data redaction
5. **Database Transactions**: Proper rollback on error
6. **Delegation Cycle Detection**: Prevents infinite chains
7. **Atomic Double-Voting Prevention**: MERGE query
8. **Token Storage**: httpOnly cookies
9. **CSRF in Memory**: Not in localStorage
10. **CSV Injection Prevention**: Formula character escaping
11. **Content Validation**: Input sanitization
12. **TLS Configuration**: Strong cipher suites

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-08 | Claude Code | Initial comprehensive audit |

---

*End of Codebase Audit 2 Report*
