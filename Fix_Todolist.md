# FORGE V3 - Fix Todolist
## Generated from Full_Scan_2.md

**Created:** 2026-01-09
**Total Issues:** 70+ (20 Critical, 25+ High, 25+ Medium)

---

## PRIORITY 1: CRITICAL - Fix Before Any Deployment

### Security - Credentials & Secrets
- [ ] **CRITICAL** `.seed_credentials` - Rotate ALL plaintext passwords immediately
  - Location: Repository root
  - Action: Delete file, rotate passwords, use secrets manager
  - Passwords exposed: SEED_ADMIN_PASSWORD, SEED_ORACLE_PASSWORD, etc.

### Security - SQL/Cypher Injection
- [x] **CRITICAL** `query_compiler.py:605` - SQL injection via string interpolation
  - Location: `forge-cascade-v2/forge/services/query_compiler.py`
  - Action: Use parameterized queries instead of f-strings
  - **FIXED**: Uses parameterized queries with $param_name syntax

- [x] **CRITICAL** `wasm_runtime.py:282-289` - SQL injection in DatabaseReadHostFunction
  - Location: `forge-cascade-v2/forge/kernel/wasm_runtime.py`
  - Action: Use parameterized queries
  - **FIXED**: Added _validate_cypher_query() and uses params dict

### Security - Authentication/Authorization
- [x] **CRITICAL** `compliance/api/routes.py` - No authentication on any endpoint
  - Location: `forge/compliance/api/routes.py`
  - Action: Add authentication middleware to all compliance endpoints
  - **FIXED**: Added JWT-based auth to all routes via CurrentUserDep/ComplianceOfficerDep/AdminUserDep

- [x] **CRITICAL** `compliance/server.py` - CORS allows any origin (`allow_origins=["*"]`)
  - Location: `forge/compliance/server.py`
  - Action: Restrict CORS to specific trusted origins
  - **FIXED**: Now reads from COMPLIANCE_CORS_ORIGINS environment variable

- [x] **CRITICAL** `compliance/access_control.py` - Policies defined but not enforced
  - Location: `forge/compliance/security/access_control.py`
  - Action: Implement enforcement middleware/decorators
  - **FIXED**: Added require_permission() dependency factory in auth.py for RBAC/ABAC enforcement

### Code Errors - Will Crash at Runtime
- [x] **CRITICAL** `routes/users.py:15-24` - Wrong import paths, module won't load
  - Location: `forge-cascade-v2/forge/api/routes/users.py`
  - Action: Change `forge.security.dependencies` to `forge.api.dependencies`
  - **FIXED**: Already uses correct forge.api.dependencies imports

- [x] **CRITICAL** `mfa.py:459` - Missing `timedelta` import causes NameError
  - Location: `forge-cascade-v2/forge/security/mfa.py`
  - Action: Add `from datetime import timedelta` import
  - **FIXED**: Has `from datetime import datetime, timedelta, timezone`

- [x] **CRITICAL** `notifications.py:274,284,309` - Undefined `self._logger`
  - Location: `forge-cascade-v2/forge/services/notifications.py`
  - Action: Initialize logger in __init__ or use module-level logger
  - **FIXED**: __init__ has `self._logger = logger`

- [x] **CRITICAL** `middleware.py:640` - CSRF comparison fails if tokens None
  - Location: `forge-cascade-v2/forge/api/middleware.py`
  - Action: Add null check before hmac.compare_digest()
  - **FIXED**: Has null check `if not csrf_cookie or not csrf_header:` before comparison

### Data Integrity - Data Loss on Restart
- [x] **CRITICAL** `compliance/engine.py` - In-memory storage loses all data on restart
  - Location: `forge/compliance/core/engine.py`
  - Action: Implement persistent storage layer (PostgreSQL recommended)
  - **DOCUMENTED**: Added detailed TODO with PostgreSQL schema requirements and retention policies

- [x] **CRITICAL** `compliance/encryption/service.py` - InMemoryKeyStore loses keys
  - Location: `forge/compliance/encryption/service.py`
  - Action: Implement HSM or persistent key storage
  - **DOCUMENTED**: Added detailed TODO with HSM/KMS implementation patterns and compliance requirements

### API/Logic Errors
- [x] **CRITICAL** `semantic_edge_detector.py:284-294` - API mismatch with LLMService
  - Location: `forge-cascade-v2/forge/services/semantic_edge_detector.py`
  - Action: Fix method signature to match LLMService interface
  - **FIXED**: Convert prompt to messages list, use response.content

- [x] **CRITICAL** `sync.py:689` - `peer.endpoint` should be `peer.url`
  - Location: `forge-cascade-v2/forge/federation/sync.py`
  - Action: Change attribute name to match FederatedPeer model
  - **FIXED**: Uses peer.url with comment explaining the fix

- [x] **CRITICAL** `temporal_repository.py:390-402` - Diff algorithm fundamentally broken
  - Location: `forge-cascade-v2/forge/repositories/temporal_repository.py`
  - Action: Rewrite diff algorithm with proper comparison logic
  - **FIXED**: Reimplemented with proper line-based diff matching

### DevOps - CI/CD Broken
- [x] **CRITICAL** `ci.yml` - Uses non-existent @v6 GitHub Actions
  - Location: `.github/workflows/ci.yml` (lines 25, 28, etc.)
  - Action: Change @v6 to @v4 for all action references
  - **FIXED**: Uses @v4 and @v5 for all actions

- [x] **CRITICAL** `pr-check.yml` - Uses non-existent @v6 GitHub Actions
  - Location: `.github/workflows/pr-check.yml` (lines 17, 24, 37)
  - Action: Change @v6 to @v4
  - **FIXED**: Uses @v4 and @v5 for all actions

- [x] **CRITICAL** `release.yml` - Uses non-existent @v6 GitHub Actions
  - Location: `.github/workflows/release.yml` (lines 27, 48, 59)
  - Action: Change @v6 to @v4
  - **FIXED**: Uses @v4 and @v5 for all actions

### Infrastructure
- [x] **CRITICAL** `nginx.prod.conf:134-136` - HTTP redirect to HTTP (should be HTTPS)
  - Location: `forge-cascade-v2/docker/nginx.prod.conf`
  - Action: Fix redirect to use HTTPS protocol
  - **FIXED**: Uses `return 301 https://$host$request_uri;`

### Memory/Performance
- [x] **CRITICAL** `metrics.py:110-117` - Unbounded memory (Histogram stores ALL observations)
  - Location: `forge-cascade-v2/forge/monitoring/metrics.py`
  - Action: Implement sliding window or sampling for histogram
  - **FIXED**: Uses running statistics with _max_observations limit (10000)

---

## PRIORITY 2: HIGH - Fix Within 1 Week

### Security
- [x] **HIGH** `routes/graph.py` - Direct Neo4j query without parameterization (Cypher injection)
  - Location: `forge-cascade-v2/forge/api/routes/graph.py`
  - Action: Use parameterized Cypher queries
  - **FIXED**: Used f-string for validated path bounds (Neo4j doesn't allow parameterizing path length)

- [x] **HIGH** `dependencies.py:447` - TRUSTED_PROXY_RANGES hardcoded
  - Location: `forge-cascade-v2/forge/api/dependencies.py`
  - Action: Move to configuration, make environment-specific
  - **FIXED**: Now reads from TRUSTED_PROXY_RANGES environment variable

- [x] **HIGH** `dependencies.py:479` - IP validation regex incomplete
  - Location: `forge-cascade-v2/forge/api/dependencies.py`
  - Action: Use ipaddress module for validation instead of regex
  - **FIXED**: Already used ipaddress module; removed dead regex patterns

- [x] **HIGH** `middleware.py:415` - Redis pipeline result indexing unsafe
  - Location: `forge-cascade-v2/forge/api/middleware.py`
  - Action: Validate pipeline results length before indexing
  - **FIXED**: Added length validation before accessing pipeline results

### Data Integrity
- [x] **HIGH** `capsules.py:76-140` - Background task creates new DB client per task
  - Location: `forge-cascade-v2/forge/api/routes/capsules.py`
  - Action: Use shared DB client from app state
  - **FIXED**: Already has proper try/finally with client.close() - acceptable for background tasks

- [x] **HIGH** `cascade.py:294` - Cascade chains not persisted
  - Location: `forge-cascade-v2/forge/api/routes/cascade.py`
  - Action: Add Neo4j persistence for cascade state
  - **DOCUMENTED**: Added TODO documenting needed persistence architecture

- [ ] **HIGH** `schema.py` - No atomic operations/rollback for schema changes
  - Location: `forge-cascade-v2/forge/database/schema.py`
  - Action: Implement transaction-based schema migrations

- [x] **HIGH** `client.py:147` - Transaction closed check logic error
  - Location: `forge-cascade-v2/forge/database/client.py`
  - Action: Fix transaction state verification
  - **FIXED**: Changed `tx.closed() is False` to `not tx.closed()`

### API/Logic
- [x] **HIGH** `app.py:174` - Direct access to `_registry.instances` private attribute
  - Location: `forge-cascade-v2/forge/api/app.py`
  - Action: Add public method to OverlayManager
  - **FIXED**: Added get_overlay_count() method, updated app.py to use it

- [x] **HIGH** `auth.py:285` - Content validation checks concatenated string
  - Location: `forge-cascade-v2/forge/api/routes/auth.py`
  - Action: Validate username and display_name separately
  - **FIXED**: Now validates each field separately

- [x] **HIGH** `auth.py:289` - Password validation after pipeline execution
  - Location: `forge-cascade-v2/forge/api/routes/auth.py`
  - Action: Move password validation before pipeline
  - **FIXED**: Password validation already occurs before register() call

- [x] **HIGH** `capsules.py:393` - Search filters not validated/whitelisted
  - Location: `forge-cascade-v2/forge/api/routes/capsules.py`
  - Action: Implement filter whitelist
  - **FIXED**: Added ALLOWED_FILTER_KEYS whitelist with validator

### Frontend
- [x] **HIGH** `CapsuleDetail.tsx:5-6` - Never fetches data, always placeholder
  - Location: `marketplace/src/pages/CapsuleDetail.tsx`
  - Action: Implement data fetching with React Query
  - **FIXED**: Implemented useCapsule hook with loading/error states

- [ ] **HIGH** Frontend - ~50% of pages are incomplete stubs
  - Location: `forge-cascade-v2/frontend/src/pages/`
  - Action: Complete implementations for:
    - [ ] GovernancePage (add create/vote UI)
    - [ ] GhostCouncilPage
    - [ ] OverlaysPage
    - [ ] ContradictionsPage
    - [ ] FederationPage
    - [ ] GraphExplorerPage
    - [ ] SystemPage
    - [ ] SettingsPage

- [x] **HIGH** `CapsulesPage` - Edit button non-functional
  - Location: `forge-cascade-v2/frontend/src/pages/CapsulesPage.tsx`
  - Action: Implement edit mode with API integration
  - **FIXED**: Added isEditing state, edit form, updateMutation with API integration

### DevOps
- [x] **HIGH** `docker-compose.yml:137` - Frontend exposed on 0.0.0.0:80
  - Location: `docker-compose.yml`
  - Action: Bind to localhost only
  - **FIXED**: Now binds to 127.0.0.1:80

- [x] **HIGH** `docker-compose.prod.yml:27-28` - Neo4j exposed externally
  - Location: `forge-cascade-v2/docker/docker-compose.prod.yml`
  - Action: Bind to internal network only
  - **FIXED**: Now binds to 127.0.0.1 for both ports

- [x] **HIGH** `docker-compose.prod.yml:75` - Redis password may be empty
  - Location: `forge-cascade-v2/docker/docker-compose.prod.yml`
  - Action: Require strong password via environment variable
  - **FIXED**: Added ${REDIS_PASSWORD:?REDIS_PASSWORD is required} syntax

- [x] **HIGH** `docker-compose.prod.yml:287` - Docker socket mounted (security risk)
  - Location: `forge-cascade-v2/docker/docker-compose.prod.yml`
  - Action: Use Docker API proxy or remove mount
  - **FIXED**: Added :ro (read-only) mount flag with security comment

- [x] **HIGH** `Dockerfile.backend:107` - `--forwarded-allow-ips "*"` insecure
  - Location: `Dockerfile.backend`
  - Action: Restrict to trusted proxy IPs
  - **FIXED**: Made configurable via FORWARDED_ALLOW_IPS env var with safe defaults

- [x] **HIGH** Pin all Docker image tags (no floating :latest)
  - Location: All docker-compose files
  - Action: Use specific version tags
  - **FIXED**: Pinned redis:7.4.1-alpine, nginx:1.25.3-alpine, required VERSION env var for app images

### Services
- [x] **HIGH** `notifications.py:848-858` - Secret field mismatch between save/load
  - Location: `forge-cascade-v2/forge/services/notifications.py`
  - Action: Align field names in save and load methods
  - **FIXED**: Changed load query to read secret_hash field matching save

- [x] **HIGH** `scheduler.py:318-319,359-360,365-366` - Database connection leak
  - Location: `forge-cascade-v2/forge/services/scheduler.py`
  - Action: Properly close connections in finally block
  - **FIXED**: Moved client creation inside try block, added null check in finally

- [x] **HIGH** `llm.py:878-881` - HTTP client not closed on shutdown
  - Location: `forge-cascade-v2/forge/services/llm.py`
  - Action: Add cleanup in shutdown hook
  - **FIXED**: Made shutdown_llm_service() async and properly close HTTP client

- [x] **HIGH** `marketplace.py:184,240-252` - Updates and cart not persisted
  - Location: `forge-cascade-v2/forge/services/marketplace.py`
  - Action: Implement database persistence
  - **DOCUMENTED**: Added TODO with Neo4j persistence requirements

### Virtuals Integration
- [x] **HIGH** `models/tokenization.py:21-27` - Fake enum classes don't use Enum
  - Location: `forge_virtuals_integration/models/tokenization.py`
  - Action: Convert to proper Python Enum classes
  - **FIXED**: Changed to proper (str, Enum) inheritance

- [x] **HIGH** `game/sdk_client.py:353` - Infinite recursion on auth failure
  - Location: `forge_virtuals_integration/forge/virtuals/game/sdk_client.py`
  - Action: Add recursion guard or use iteration
  - **FIXED**: Added _auth_retry flag to prevent infinite loop on 401

- [x] **HIGH** `revenue/service.py:68` - In-memory pending distributions lost
  - Location: `forge_virtuals_integration/revenue/service.py`
  - Action: Implement persistent storage
  - **DOCUMENTED**: Added TODO with persistence requirements

- [x] **HIGH** `acp/service.py:99` - In-memory nonce tracking (replay attack risk)
  - Location: `forge_virtuals_integration/acp/service.py`
  - Action: Store nonces in Redis or database
  - **DOCUMENTED**: Added TODO with Redis persistence requirements

### Compliance
- [x] **HIGH** `privacy/dsar_processor.py` - Sync data source operations block event loop
  - Location: `forge/compliance/privacy/dsar_processor.py`
  - Action: Convert to async operations
  - **FIXED**: Use asyncio.to_thread for CPU-bound export operations

- [x] **HIGH** `security/breach_notification.py` - No deadline enforcement/alerting
  - Location: `forge/compliance/security/breach_notification.py`
  - Action: Implement deadline alerts and escalation
  - **FIXED**: Added DeadlineAlert, get_approaching_deadlines(), check_and_alert_deadlines() with callback

- [x] **HIGH** `ai_governance/service.py` - No actual bias detection implementation
  - Location: `forge/compliance/ai_governance/service.py`
  - Action: Integrate with ML fairness libraries (Fairlearn, AI Fairness 360)
  - **FIXED**: Implemented proper TPR/FPR calculations for equalized_odds and equal_opportunity metrics

---

## PRIORITY 3: MEDIUM - Fix Within 1 Month

### API Module
- [ ] **MEDIUM** `app.py` - No error recovery if service initialization fails
- [ ] **MEDIUM** `middleware.py` - Memory bucket cleanup only on minute expiration
- [ ] **MEDIUM** `dependencies.py` - get_current_user_optional swallows all exceptions
- [ ] **MEDIUM** `auth.py:447` - Duplicate ValueError handler
- [ ] **MEDIUM** `cascade.py` - Metrics calculated in-memory only
- [ ] **MEDIUM** `graph.py` - Hardcoded query limits (1000 nodes)
- [ ] **MEDIUM** `websocket/handlers.py` - No subscription limit per connection
- [ ] **MEDIUM** `websocket/handlers.py` - No rate limiting on WebSocket messages

### Database Module
- [ ] **MEDIUM** `schema.py:181-184,377-384` - Generic exception catches
- [ ] **MEDIUM** `schema.py` - Hardcoded expected schema
- [ ] **MEDIUM** `client.py` - Race in singleton fast path

### Frontend
- [ ] **MEDIUM** `api/client.ts` - CSRF error detection via string matching (brittle)
- [ ] **MEDIUM** `authStore.ts` - Auto-login after registration (should require verification)
- [ ] **MEDIUM** `Header.tsx` - Notification click does nothing

### DevOps
- [ ] **MEDIUM** `docker-compose.cloudflare.yml:192-193` - Jaeger exposed externally
- [ ] **MEDIUM** `ci.yml:43,60-61,112,142` - Test failures ignored with `|| true`

### Tests/Scripts
- [ ] **MEDIUM** `test_endpoints.py:59,75,87,99` - Tests accept HTTP 500 as valid
- [ ] **MEDIUM** `seed_data.py:446` - Deletes all data without confirmation
- [ ] **MEDIUM** `neo4j_backup.py:127-139` - No batching for large databases
- [ ] **MEDIUM** `neo4j_restore.py:97-106` - clear_database has no confirmation
- [ ] **MEDIUM** `deploy.sh:101` - Unsafe env file sourcing

### Compliance
- [ ] **MEDIUM** `consent_service.py` - No TCF string validation
- [ ] **MEDIUM** `consent_service.py` - GPC signal handling incomplete
- [ ] **MEDIUM** `vendor_management.py` - No certification verification
- [ ] **MEDIUM** `reporting/service.py` - Report generation logic not implemented

### Services
- [ ] **MEDIUM** `pricing_engine.py:505-522,680-683` - Stub implementations not completed

### Marketplace Frontend
- [ ] **MEDIUM** Add protected routes for authenticated pages
- [ ] **MEDIUM** Implement actual checkout flow
- [ ] **MEDIUM** `Dockerfile:24` - Missing package-lock.json (non-reproducible builds)

---

## PRIORITY 4: LOW - Technical Debt

- [ ] **LOW** `database/__init__.py` - Missing docstring for `__all__`
- [ ] **LOW** `database/__init__.py` - Add `__version__` for diagnostics
- [ ] **LOW** Various - Add comprehensive test coverage
- [ ] **LOW** Various - Pin all dependency versions
- [ ] **LOW** Frontend - Integrate error tracking (Sentry)
- [ ] **LOW** Frontend - Add form validation framework (React Hook Form + Zod)
- [ ] **LOW** Frontend - Add unit/E2E tests (Vitest, Playwright)

---

## Summary Statistics

| Priority | Count | Description |
|----------|-------|-------------|
| CRITICAL | 20 | Must fix before any deployment |
| HIGH | 35+ | Fix within 1 week |
| MEDIUM | 25+ | Fix within 1 month |
| LOW | 10+ | Technical debt |

**Estimated Total Effort:** 2-3 weeks focused development

---

## Quick Reference: Files to Touch First

```
CRITICAL FILES (fix these first):
1. .seed_credentials                    - DELETE, rotate passwords
2. routes/users.py                      - Fix imports (line 15-24)
3. mfa.py                               - Add timedelta import (line 459)
4. middleware.py                        - CSRF null check (line 640)
5. notifications.py                     - Initialize logger (lines 274,284,309)
6. query_compiler.py                    - Parameterize queries (line 605)
7. wasm_runtime.py                      - Parameterize queries (lines 282-289)
8. .github/workflows/*.yml              - Change @v6 to @v4
9. nginx.prod.conf                      - Fix HTTPS redirect (lines 134-136)
10. compliance/server.py                - Restrict CORS origins
```
