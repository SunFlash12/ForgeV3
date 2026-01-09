# Forge V3 - Audit 4 Master Security Todolist

**Generated:** 2026-01-09
**Previous Audits:** Audit 1, 2, 3 Complete
**Scope:** Comprehensive codebase analysis - 12 parallel agents

---

## Executive Summary

This audit identified **200+ security findings** across the entire Forge V3 codebase through 12 specialized agents analyzing different modules. Findings are organized by severity with specific file paths, line numbers, and remediation recommendations.

---

## CRITICAL SEVERITY (Immediate Action Required)

### C1. Pickle Deserialization RCE
- **File:** `forge-cascade-v2/forge/resilience/caching/query_cache.py`
- **Lines:** 150, 197
- **Issue:** Unsafe pickle deserialization allows arbitrary code execution if cache is compromised
- **Fix:** Replace pickle with JSON serialization
```python
# Replace:
return pickle.loads(data)
# With:
return json.loads(data)
```

### C2. WASM Sandbox Escape via Python Fallback
- **File:** `forge-cascade-v2/forge/kernel/wasm_runtime.py`
- **Lines:** 487-502
- **Issue:** Python fallback mode bypasses declared WASM isolation, allows arbitrary code execution
- **Fix:** Implement actual WASM isolation or remove fallback capability

### C3. Prompt Injection - LLM Services (7 locations)
- **Files:**
  - `forge-cascade-v2/forge/services/llm.py` (Lines 571-614, 656-765)
  - `forge-cascade-v2/forge/services/ghost_council.py` (Lines 513-609, 691-717)
  - `forge-cascade-v2/forge/services/query_compiler.py` (Lines 346-365)
  - `forge-cascade-v2/forge/services/semantic_edge_detector.py` (Lines 246-299)
- **Issue:** User content directly interpolated into LLM prompts without sanitization
- **Fix:** Implement prompt escaping, structured output schemas, output validation

### C4. Direct Cypher Execution Vulnerability
- **File:** `forge-cascade-v2/forge/services/agent_gateway.py`
- **Lines:** 512-557
- **Issue:** Keyword blocklist easily bypassable (Unicode homoglyphs, DETACH DELETE, CALL procedures)
- **Fix:** Use Cypher AST parser instead of string matching

### C5. MFA In-Memory Storage
- **File:** `forge-cascade-v2/forge/security/mfa.py`
- **Lines:** 92-97
- **Issue:** MFA secrets, backup codes stored in-memory dictionaries - lost on restart
- **Fix:** Implement database-backed encrypted storage

### C6. Authentication Placeholder Returns Null Address
- **File:** `forge_virtuals_integration/forge/virtuals/api/routes.py`
- **Lines:** 59-69
- **Issue:** All API endpoints use hardcoded null address `0x0000...` for authentication
- **Fix:** Integrate with Forge's actual authentication system

### C7. Wallet Private Keys Lost on Creation
- **Files:**
  - `forge_virtuals_integration/forge/virtuals/chains/evm_client.py` (Lines 246-272)
  - `forge_virtuals_integration/forge/virtuals/chains/solana_client.py` (Lines 178-197)
- **Issue:** Newly created wallet private keys are NOT returned or stored - immediate funds loss risk
- **Fix:** Return private key securely or integrate with key management system

### C8. Fake Signatures in ACP Memos
- **File:** `forge_virtuals_integration/forge/virtuals/acp/service.py`
- **Lines:** 585-612
- **Issue:** "Signature" is string concatenation, not cryptographic - anyone can forge memos
- **Fix:** Implement proper cryptographic signing (Ed25519 or ECDSA)

### C9. In-Memory Audit Logs Without Persistence
- **File:** `forge/compliance/core/engine.py`
- **Lines:** 74, 150-151
- **Issue:** Audit events stored only in memory, lost on restart
- **Fix:** Persist to tamper-proof external storage immediately

### C10. Password Hash Exposure via RETURN u {.*}
- **File:** `forge-cascade-v2/forge/repositories/user_repository.py`
- **Lines:** 97-99, 199-203, 214-217
- **Issue:** Authentication methods return ALL fields including password_hash
- **Fix:** Use explicit safe field lists: `RETURN u {.id, .username, .email, .role} AS user`

### C11. In-Memory Key Store for Compliance
- **File:** `forge/compliance/encryption/service.py`
- **Lines:** 114-186
- **Issue:** Encryption keys stored in memory without HSM protection
- **Fix:** Integrate with HSM-backed key store for production

### C12. Global State Manipulation Across Modules
- **Files:** All files using global instances (`_wasm_runtime`, `_pipeline`, `_event_bus`)
- **Issue:** Global instances can be replaced by any code with import access
- **Fix:** Use dependency injection pattern with immutable references

### C13. Hardcoded Credentials in Committed File
- **File:** `forge-cascade-v2/scripts/.seed_credentials`
- **Lines:** 5-14
- **Issue:** Plaintext production passwords committed to repository
- **Fix:**
  1. Rotate all credentials immediately
  2. Add to .gitignore
  3. Remove from git history using BFG Repo Cleaner

---

## HIGH SEVERITY

### H1. Default Trust Level for Missing Claims
- **File:** `forge-cascade-v2/forge/security/dependencies.py`
- **Lines:** 60-62
- **Issue:** Missing token claims default to trust_flame=60 (STANDARD) instead of rejection
- **Fix:** Reject tokens with missing required claims

### H2. Email Verification Token Not Validated
- **File:** `forge-cascade-v2/forge/security/auth_service.py`
- **Lines:** 630-648
- **Issue:** `verify_email()` accepts token but never validates it
- **Fix:** Implement proper token validation using hashed tokens

### H3. DNS Rebinding SSRF in Federation
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 249-282
- **Issue:** DNS resolution at validation time allows rebinding attack
- **Fix:** Implement DNS pinning or resolve at request time with blocking

### H4. No Certificate Pinning for Federation Peers
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 329-336
- **Issue:** MitM attackers with valid certificates can intercept federation traffic
- **Fix:** Add TLS certificate pinning for known peers

### H5. Legacy Peers Bypass Replay Protection
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 520-524, 763-765
- **Issue:** Handshakes without nonces accepted "for backward compatibility"
- **Fix:** Reject all messages without nonces - remove backward compatibility

### H6. Unbounded Sync Loop in Federation
- **File:** `forge-cascade-v2/forge/federation/sync.py`
- **Lines:** 193-222
- **Issue:** `while True` loop continues as long as `has_more=True` - malicious peer DoS
- **Fix:** Add maximum iteration limit

### H7. Content Hash Not Verified Against Actual Content
- **File:** `forge-cascade-v2/forge/federation/sync.py`
- **Lines:** 297-300
- **Issue:** Hash values compared but never verified against capsule content
- **Fix:** Compute and verify content hash before accepting

### H8. Private Keys Stored Without Encryption
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 403-409
- **Issue:** Federation private keys saved with `NoEncryption()`
- **Fix:** Encrypt private keys at rest using environment-provided passphrase

### H9. Trust Level Manipulation in Capsule Merge
- **File:** `forge-cascade-v2/forge/federation/sync.py`
- **Lines:** 430-432
- **Issue:** If remote trust is higher, it's adopted - attacker can claim high trust
- **Fix:** Never accept trust level from remote - recalculate locally

### H10. Unbounded Memory Caches (8 locations)
- **Files:**
  - `forge-cascade-v2/forge/overlays/governance.py` (Lines 356, 360) - `_active_proposals`, `_proposal_locks`
  - `forge-cascade-v2/forge/overlays/temporal_tracker.py` (Line 138) - `_version_counts`
  - `forge-cascade-v2/forge/overlays/graph_algorithms.py` (Line 126) - `_cache`
  - `forge-cascade-v2/forge/overlays/capsule_analyzer.py` (Lines 90-93) - `_analysis_cache`, `_topic_index`
  - `forge-cascade-v2/forge/repositories/graph_repository.py` (Lines 150-166) - `_cache`
  - `forge-cascade-v2/forge/services/agent_gateway.py` (Lines 109-113) - `_sessions`, `_access_logs`
- **Fix:** Add bounded LRU caches with size limits

### H11. Trust Score > 100 Amplifies Vote Weight
- **File:** `forge-cascade-v2/forge/overlays/governance.py`
- **Lines:** 845-857
- **Issue:** Trust values > 100 produce weights > 1.0
- **Fix:** Clamp trust values to 0-100 range in `_calculate_vote_weight()`

### H12. Circuit Breaker Race Condition
- **File:** `forge-cascade-v2/forge/kernel/overlay_manager.py`
- **Lines:** 625-636
- **Issue:** Non-atomic check-then-delete allows bypass
- **Fix:** Use atomic operations with proper locking

### H13. Event Bus Dead Letter Queue Unbounded
- **File:** `forge-cascade-v2/forge/kernel/event_system.py`
- **Lines:** 88-91
- **Issue:** Dead letter queue has no size limit - memory exhaustion DoS
- **Fix:** Add bounded queue with overflow handling

### H14. Tenant Filter Bypass via Query Manipulation
- **File:** `forge-cascade-v2/forge/resilience/security/tenant_isolation.py`
- **Lines:** 298-308
- **Issue:** String replacement allows SQL injection in tenant_id
- **Fix:** Use parameterized queries for tenant isolation

### H15. Cache Key Injection
- **File:** `forge-cascade-v2/forge/resilience/caching/query_cache.py`
- **Lines:** 305-308
- **Issue:** Cache keys constructed without sanitizing capsule_id
- **Fix:** Validate and sanitize all cache key components

### H16. Partition ID Collision via MD5
- **File:** `forge-cascade-v2/forge/resilience/partitioning/partition_manager.py`
- **Lines:** 196-197
- **Issue:** MD5 with only 8 hex chars (32 bits) has high collision probability
- **Fix:** Use SHA-256 with longer prefix

### H17. Cypher Injection in Migration Query
- **File:** `forge-cascade-v2/forge/resilience/migration/embedding_migration.py`
- **Lines:** 486-492
- **Issue:** `where_clause` built from filter conditions could include user input
- **Fix:** Validate filter keys, use parameterized queries for all values

### H18. Webhook Secret Stored in Plaintext
- **File:** `forge-cascade-v2/forge/services/notifications.py`
- **Lines:** 736-767
- **Issue:** Webhook secrets stored unencrypted in Neo4j
- **Fix:** Hash secrets with bcrypt before storage

### H19. ReDoS in Content Validator
- **File:** `forge-cascade-v2/forge/resilience/security/content_validator.py`
- **Lines:** 375-388
- **Issue:** Several patterns vulnerable to catastrophic backtracking
- **Fix:** Use RE2 or add regex timeouts

### H20. Vote Weight Not Verified
- **File:** `forge-cascade-v2/forge/repositories/governance_repository.py`
- **Lines:** 429-512
- **Issue:** `trust_weight` parameter accepted without verification against actual trust
- **Fix:** Fetch and verify voter's current trust level in repository

### H21. Timelock Bypass
- **File:** `forge-cascade-v2/forge/repositories/governance_repository.py`
- **Lines:** 360-389
- **Issue:** `mark_executed` doesn't verify timelock has expired
- **Fix:** Add check: `WHERE p.execution_allowed_after < datetime()`

### H22. Open Redirect via OAuth
- **File:** `marketplace/src/pages/Login.tsx`
- **Lines:** 57-61
- **Issue:** `VITE_CASCADE_API_URL` can redirect to malicious OAuth server
- **Fix:** Validate against allowlist of trusted domains

### H23. Client-Side Price Manipulation
- **File:** `marketplace/src/contexts/CartContext.tsx`
- **Lines:** 29-32
- **Issue:** Cart prices from localStorage can be manipulated
- **Fix:** Server MUST validate prices at checkout - never trust client prices

### H24. API Key Exposure Risk
- **File:** `forge-cascade-v2/forge/services/embedding.py`
- **Lines:** 42-43, 185
- **Issue:** API keys may appear in logs, error messages, memory dumps
- **Fix:** Use environment variables with redaction in logs

### H25. Cost Abuse - Unbounded Batch Sizes
- **File:** `forge-cascade-v2/forge/services/embedding.py`
- **Lines:** 487-564
- **Issue:** `embed_batch()` accepts arbitrary list sizes
- **Fix:** Add configurable maximum batch size limit (e.g., 10,000 items)

### H26. Unbounded max_depth in Graph Traversal
- **File:** `forge-cascade-v2/forge/repositories/capsule_repository.py`
- **Lines:** 449-479, 540-563
- **Issue:** `max_depth` interpolated without validation into Cypher
- **Fix:** Validate and cap: `max_depth = max(1, min(max_depth, 20))`

### H27. Missing Owner Authorization in Capsule Update
- **File:** `forge-cascade-v2/forge/repositories/capsule_repository.py`
- **Lines:** 179-230
- **Issue:** No verification caller owns the capsule
- **Fix:** Add: `MATCH (c:Capsule {id: $id, owner_id: $caller_id})`

### H28. No WASM Hash Verification
- **File:** `forge-cascade-v2/forge/repositories/overlay_repository.py`
- **Lines:** 74-147
- **Issue:** `wasm_hash` stored but never verified against actual WASM content
- **Fix:** Compute and verify hash before storing overlay

### H29. Sync Request Has No Nonce
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 660-671
- **Issue:** `send_sync_request()` signs but doesn't include nonce - replayable
- **Fix:** Add nonce to all signed requests

### H30. Arbitrary Code Execution via Pack Installation
- **File:** `forge-cascade-v2/forge/resilience/cold_start/starter_packs.py`
- **Lines:** 470-486
- **Issue:** Pack templates contain arbitrary content passed to capsule creation
- **Fix:** Validate pack content, verify sources, check for XSS payloads

---

## MEDIUM SEVERITY

### M1. Timing Attack in Token Comparison
- **File:** `forge-cascade-v2/forge/repositories/user_repository.py`
- **Lines:** 469-478
- **Issue:** Uses `==` instead of `secrets.compare_digest()`
- **Fix:** `return secrets.compare_digest(stored_token, token)`

### M2. Credential Stuffing Protection Gap
- **File:** `forge-cascade-v2/forge/security/auth_service.py`
- **Lines:** 153-287
- **Issue:** No IP-based rate limiting - attackers can try 5 passwords on each account
- **Fix:** Implement IP-based rate limiting across all accounts

### M3. MFA Lockout Time Calculation Error
- **File:** `forge-cascade-v2/forge/security/mfa.py`
- **Lines:** 308-310
- **Issue:** Incorrect datetime calculation using `replace(second=...)` instead of timedelta
- **Fix:** `datetime.now(timezone.utc) + timedelta(seconds=LOCKOUT_DURATION_SECONDS)`

### M4. Type Filter Injection in Semantic Neighbors
- **File:** `forge-cascade-v2/forge/repositories/capsule_repository.py`
- **Lines:** 908-983, 1107-1158
- **Issue:** `type_values` list directly interpolated into query
- **Fix:** Use parameterized queries for all values

### M5. Quorum Bypass When eligible_voters=0
- **File:** `forge-cascade-v2/forge/repositories/governance_repository.py`
- **Lines:** 255-331
- **Issue:** `quorum_met` stays True if `eligible_voters` is 0
- **Fix:** Add explicit check: `if eligible_voters == 0: return False`

### M6. Windows Key Permission Setting Silently Ignored
- **File:** `forge-cascade-v2/forge/federation/protocol.py`
- **Lines:** 411-415
- **Issue:** `os.chmod()` for private key protection fails silently on Windows
- **Fix:** Use Windows-specific ACL settings or document limitation

### M7. IP Spoofing in Security Dependencies
- **File:** `forge-cascade-v2/forge/security/dependencies.py`
- **Lines:** 322-337
- **Issue:** X-Forwarded-For trusted unconditionally
- **Fix:** Copy trusted proxy validation from api/dependencies.py

### M8. Threading Lock in Async Context
- **File:** `forge-cascade-v2/forge/overlays/security_validator.py`
- **Lines:** 144-176
- **Issue:** `threading.Lock` used in async code - blocks event loop
- **Fix:** Replace with `asyncio.Lock`

### M9. Blocked User Eviction Unblocks Attackers
- **File:** `forge-cascade-v2/forge/overlays/security_validator.py`
- **Lines:** 566-579
- **Issue:** Random eviction when limit reached could unblock attacker
- **Fix:** Implement LRU eviction or timeout-based cleanup

### M10. Recursive Depth Recalculation Stack Overflow
- **File:** `forge-cascade-v2/forge/overlays/lineage_tracker.py`
- **Lines:** 858-876
- **Issue:** `_recalculate_depth()` is recursive with no depth limit
- **Fix:** Add recursion depth limit or convert to iterative

### M11. No Nonce Verification for ACP Jobs
- **File:** `forge_virtuals_integration/forge/virtuals/acp/service.py`
- **Lines:** 216-276
- **Issue:** ACP job creation has no anti-replay mechanism
- **Fix:** Add nonce or idempotency key to job requests

### M12. Unlimited Token Approval Allowed
- **File:** `forge_virtuals_integration/forge/virtuals/chains/evm_client.py`
- **Lines:** 524-528
- **Issue:** `amount == float('inf')` sets max uint256 approval
- **Fix:** Warn users, implement bounded approvals, require explicit opt-in

### M13. Cart Data in localStorage Vulnerable to XSS
- **File:** `marketplace/src/contexts/CartContext.tsx`
- **Lines:** 26, 82, 99
- **Issue:** Cart including capsule data persisted in localStorage
- **Fix:** Encrypt sensitive data or clear on logout

### M14. Archive Label Injection
- **File:** `forge-cascade-v2/forge/repositories/audit_repository.py`
- **Lines:** 755-777
- **Issue:** `archive_label` parameter directly interpolated
- **Fix:** Validate against allowlist of labels

### M15. Trust History Unbounded Growth
- **File:** `forge-cascade-v2/forge/federation/trust.py`
- **Lines:** 497-501
- **Issue:** Trust history trimmed without locking - race condition
- **Fix:** Use lock during trim operation

### M16. Revenue Distribution No Integrity Check
- **File:** `forge-cascade-v2/forge/models/marketplace.py`
- **Lines:** 242-264
- **Issue:** No validation that shares sum to total_amount
- **Fix:** Add validator to verify integrity

### M17. VoteChoice Enum Alias Issue
- **File:** `forge-cascade-v2/forge/models/governance.py`
- **Lines:** 68-77
- **Issue:** Enum alias syntax doesn't work as expected in Python
- **Fix:** Remove aliases or implement proper alias mechanism

### M18. Permissive CORS in Standalone Services
- **Files:**
  - `forge-cascade-v2/run_compliance.py` (Lines 25-31)
  - `forge-cascade-v2/run_virtuals.py` (Lines 24-30)
- **Issue:** `allow_origins=["*"]` with `allow_credentials=True`
- **Fix:** Restrict CORS origins based on environment

### M19. Broadcast Function Abuse
- **File:** `forge-cascade-v2/forge/services/notifications.py`
- **Lines:** 247-280
- **Issue:** `broadcast()` can send to all users without proper authorization
- **Fix:** Require admin-level permissions

### M20. Regex Injection in Keyword Search
- **File:** `forge-cascade-v2/forge/services/search.py`
- **Lines:** 339-389
- **Issue:** User input used to build regex pattern without escaping
- **Fix:** Escape all regex metacharacters in user terms

---

## LOW SEVERITY

### L1. Lockout Duration Information Disclosure
- **File:** `forge-cascade-v2/forge/security/auth_service.py`
- **Lines:** 205-207
- **Issue:** Error message reveals exact lockout expiration time
- **Fix:** Use generic message

### L2. JTI Truncated in Logs
- **File:** `forge-cascade-v2/forge/security/tokens.py`
- **Lines:** 158, 173, 763-766
- **Issue:** JTI values truncated to 8 chars may be insufficient for debugging
- **Fix:** Log more characters or use hash for correlation

### L3. Password Max Length vs Bcrypt Limit
- **File:** `forge-cascade-v2/forge/models/user.py`
- **Lines:** 113-117
- **Issue:** Max 100 chars could be problematic with bcrypt (truncates at 72 bytes)
- **Fix:** Validate max 72 bytes or use password derivation

### L4. Embedding Vector No Dimension Validation
- **File:** `forge-cascade-v2/forge/models/capsule.py`
- **Lines:** 125-128
- **Issue:** No validation of embedding dimensions or value ranges
- **Fix:** Add dimension and range validation

### L5. Datetime Defaults to utcnow()
- **File:** `forge-cascade-v2/forge/models/base.py`
- **Lines:** 16-28
- **Issue:** `datetime.utcnow()` is deprecated
- **Fix:** Use `datetime.now(timezone.utc)`

### L6. WebSocket Stats Endpoint No Auth
- **File:** `forge-cascade-v2/forge/api/websocket/handlers.py`
- **Lines:** 809-812
- **Issue:** `/ws/stats` exposes connection statistics without authentication
- **Fix:** Add authentication requirement

### L7. Source Map Exposure
- **File:** `forge-cascade-v2/frontend/vite.config.ts`
- **Issue:** Missing explicit `build.sourcemap: false`
- **Fix:** Add `build: { sourcemap: false }` for production

### L8. Unsafe .env Parsing in Shell Scripts
- **File:** `scripts/backup/backup.sh`
- **Lines:** 26-28
- **Issue:** `export $(grep ... | xargs)` could execute shell metacharacters
- **Fix:** Use safer .env parsing

### L9. Common Password List Size
- **File:** `forge-cascade-v2/forge/security/password.py`
- **Lines:** 28-83
- **Issue:** Only ~100 common passwords checked
- **Fix:** Integrate with haveibeenpwned API (k-anonymity model)

### L10. Unicode Normalization Not Applied to Passwords
- **File:** `forge-cascade-v2/forge/security/password.py`
- **Lines:** 217-220
- **Issue:** Different Unicode representations could hash differently
- **Fix:** Apply NFKC normalization before hashing

---

## Implementation Priority Matrix

| Priority | Issues | Estimated Effort |
|----------|--------|------------------|
| P0 - Immediate | C1-C13 | 3-5 days |
| P1 - This Sprint | H1-H30 | 2-3 weeks |
| P2 - Next Sprint | M1-M20 | 2-3 weeks |
| P3 - Backlog | L1-L10 | 1 week |

---

## Verification Checklist

After implementing fixes, verify:

- [ ] All pickle usage replaced with JSON
- [ ] WASM runtime provides actual isolation
- [ ] LLM prompts sanitized and outputs validated
- [ ] All Cypher queries use parameterization
- [ ] MFA secrets persisted to encrypted database
- [ ] Virtuals API has proper authentication
- [ ] Wallet keys securely stored/returned
- [ ] ACP signatures cryptographically valid
- [ ] Audit logs persisted to tamper-proof storage
- [ ] User queries never return password_hash
- [ ] Credentials removed from git history
- [ ] All caches have size limits
- [ ] Federation endpoints enforce nonces
- [ ] Tenant isolation uses parameterized queries

---

## References

- **Agent a2aa507:** forge/api module analysis
- **Agent adc24af:** forge/security module analysis
- **Agent a53ea1e:** forge/federation module analysis
- **Agent a5296fe:** forge/services module analysis
- **Agent ac64e9e:** forge/overlays module analysis
- **Agent ab6b01b:** forge/repositories module analysis
- **Agent a36b2c0:** forge/database and models analysis
- **Agent ab7264c:** forge/kernel and resilience analysis
- **Agent ab138de:** frontend code analysis
- **Agent a545780:** configuration and deployment analysis
- **Agent ac7f5ea:** tests and scripts analysis
- **Agent aea0988:** compliance and virtuals analysis
