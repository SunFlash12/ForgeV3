# FORGE CASCADE V2 - Build Plan

**Created:** 2026-01-01  
**Updated:** 2026-01-02
**Approach:** Foundation-First Development  
**Goal:** Production-ready Institutional Memory Engine

---

## Build Philosophy

This plan follows a **foundational-first** approach where each layer provides stable building blocks for subsequent layers. We build "from the ground up" ensuring each component is solid before building on top of it.

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 7: Frontend (React Dashboard)              [PHASE 5] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 6: API Layer (FastAPI + WebSockets)        [PHASE 4] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 5: Immune System (Health + Recovery)       [PHASE 4] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 4: Pipeline (7-Phase Coordination)         [PHASE 3] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: Kernel (Overlay Manager + Events)       [PHASE 3] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: Security (Auth + Trust + Capabilities)  [PHASE 2] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 1: Data Layer (Neo4j + Repositories)       [PHASE 1] │ ✅
├─────────────────────────────────────────────────────────────┤
│  LAYER 0: Foundation (Config + Models + Schema)   [PHASE 1] │ ✅
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation & Data Layer ✅

### 1.1 Tasks - Foundation

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| F1 | `pyproject.toml`, `requirements.txt` | Project dependencies | ✅ |
| F2 | `forge/config.py` | Environment config with Neo4j credentials | ✅ |
| F3 | `forge/models/*.py` | All Pydantic models | ✅ |
| F4 | `forge/database/client.py` | Async Neo4j client wrapper | ✅ |
| F5 | `forge/database/schema.py` | Schema setup (constraints, vector index) | ✅ |
| F6 | `scripts/setup_db.py` | Database initialization script | ⬜ |

### 1.2 Tasks - Repositories

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| R1 | `forge/repositories/base.py` | Base repository pattern | ✅ |
| R2 | `forge/repositories/capsule_repository.py` | Capsule CRUD + lineage queries | ✅ |
| R3 | `forge/repositories/user_repository.py` | User management | ✅ |
| R4 | `forge/repositories/overlay_repository.py` | Overlay state tracking | ✅ |
| R5 | `forge/repositories/governance_repository.py` | Proposals, voting | ✅ |
| R6 | `forge/repositories/audit_repository.py` | Audit trail | ✅ |

---

## Phase 2: Security Layer ✅

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| S1 | `forge/security/password.py` | Bcrypt password hashing | ✅ |
| S2 | `forge/security/tokens.py` | JWT token creation/validation | ✅ |
| S3 | `forge/security/authorization.py` | Trust hierarchy + Role-based access | ✅ |
| S4 | `forge/security/dependencies.py` | FastAPI security dependencies | ✅ |
| S5 | `forge/security/auth_service.py` | High-level auth service | ✅ |

---

## Phase 3: Kernel Layer ✅

### 3.1 Tasks - Event System

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| K1 | `forge/kernel/event_system.py` | Async pub/sub event system | ✅ |

### 3.2 Tasks - Overlay Manager

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| K2 | `forge/overlays/base.py` | Base overlay class | ✅ |
| K3 | `forge/kernel/overlay_manager.py` | Overlay lifecycle management | ✅ |
| K4 | `forge/overlays/ml_intelligence.py` | ML pattern recognition overlay | ✅ |
| K5 | `forge/overlays/security_validator.py` | Security validation overlay | ✅ |
| K6 | `forge/overlays/governance.py` | Governance overlay | ✅ |
| K7 | `forge/overlays/lineage_tracker.py` | Lineage tracking overlay | ✅ |

### 3.3 Tasks - Pipeline

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| K8 | `forge/kernel/pipeline.py` | Optimized 7-phase pipeline | ✅ |

---

## Phase 4: Immune System & API ✅

### 4.1 Tasks - Immune System

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| I1 | `forge/immune/circuit_breaker.py` | Circuit breaker pattern | ✅ |
| I2 | `forge/immune/health_checker.py` | Hierarchical health checks | ✅ |
| I3 | `forge/immune/canary.py` | Canary deployment manager | ✅ |
| I4 | `forge/immune/anomaly.py` | Anomaly detection (IsolationForest) | ✅ |

### 4.2 Tasks - API

| Task | File(s) | Description | Status |
|------|---------|-------------|--------|
| A1 | `forge/api/app.py` | FastAPI application factory | ✅ |
| A2 | `forge/api/dependencies.py` | Dependency injection | ✅ |
| A3 | `forge/api/middleware.py` | Correlation ID, logging, auth | ✅ |
| A4 | `forge/api/routes/auth.py` | Auth endpoints | ✅ |
| A5 | `forge/api/routes/capsules.py` | Capsule endpoints | ✅ |
| A6 | `forge/api/routes/governance.py` | Governance endpoints | ✅ |
| A7 | `forge/api/routes/overlays.py` | Overlay endpoints | ✅ |
| A8 | `forge/api/routes/system.py` | System/health endpoints | ✅ |
| A9 | `forge/api/websocket/handlers.py` | WebSocket handlers | ✅ |

---

## Phase 5: Frontend ✅

| Task | Description | Status |
|------|-------------|--------|
| FE1 | React app setup with Vite | ✅ |
| FE2 | TailwindCSS v4 styling | ✅ |
| FE3 | Dashboard layout | ✅ |
| FE4 | Capsule management UI | ✅ |
| FE5 | Governance UI | ✅ |
| FE6 | Ghost Council Chat interface | ✅ |
| FE7 | System monitoring UI | ✅ |
| FE8 | Settings page | ✅ |
| FE9 | Overlays management | ✅ |

### Frontend Pages
- `LoginPage.tsx` - Authentication
- `DashboardPage.tsx` - System overview with charts
- `CapsulesPage.tsx` - Knowledge capsule management
- `GovernancePage.tsx` - Proposal voting
- `GhostCouncilPage.tsx` - AI wisdom chat
- `OverlaysPage.tsx` - Overlay management & canary
- `SystemPage.tsx` - Health monitoring & circuit breakers
- `SettingsPage.tsx` - User preferences

---

## Phase 6: Deployment & Polish (Current)

| Task | Description | Status |
|------|-------------|--------|
| D1 | Docker configuration | ⬜ |
| D2 | Docker Compose for full stack | ⬜ |
| D3 | Database seed data script | ⬜ |
| D4 | Environment configuration | ⬜ |
| D5 | Production optimizations | ⬜ |
| D6 | Health check endpoints | ⬜ |

---

## Phase 7: Testing & Documentation (Future)

| Task | Description | Status |
|------|-------------|--------|
| T1 | Unit tests for repositories | ⬜ |
| T2 | Integration tests for API | ⬜ |
| T3 | E2E tests with Playwright | ⬜ |
| T4 | API documentation | ⬜ |
| T5 | User guide | ⬜ |

---

## Project Structure

```
forge-cascade-v2/
├── BUILD_PLAN.md               # This file
├── README.md                   # Project documentation
├── pyproject.toml              # Python project config
├── requirements.txt            # Dependencies
│
├── forge/                      # Backend package
│   ├── config.py               # Configuration
│   ├── models/                 # Pydantic models
│   ├── database/               # Neo4j integration
│   ├── repositories/           # Data access layer
│   ├── security/               # Auth & trust
│   ├── kernel/                 # Event system & pipeline
│   ├── immune/                 # Circuit breakers & health
│   ├── overlays/               # Overlay implementations
│   └── api/                    # FastAPI application
│       ├── routes/             # REST endpoints
│       └── websocket/          # WebSocket handlers
│
├── frontend/                   # React application
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── components/         # UI components
│   │   ├── pages/              # Page components
│   │   ├── stores/             # Zustand state
│   │   └── types/              # TypeScript types
│   └── dist/                   # Production build
│
├── tests/                      # Test suite
├── scripts/                    # Utility scripts
└── docker/                     # Docker configuration
```

---

## Running the Application

### Backend
```bash
cd forge-cascade-v2
pip install -e .
uvicorn forge.api.app:create_app --factory --reload
```

### Frontend
```bash
cd forge-cascade-v2/frontend
npm install
npm run dev      # Development
npm run build    # Production
```

---

## Neo4j Configuration

```
# Set these in your .env file
NEO4J_URI=neo4j+s://your-instance-id.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
NEO4J_DATABASE=neo4j
```

---

## Success Criteria ✅

- [x] Database connection established and schema created
- [x] All CRUD operations working for Capsules, Users, Overlays
- [x] JWT authentication functional
- [x] Trust hierarchy operational
- [x] Event system delivering messages
- [x] Pipeline executing all 7 phases
- [x] Health checks returning valid status
- [x] All API endpoints returning correct responses
- [x] WebSocket handlers implemented
- [x] Frontend build successful
- [ ] Docker deployment ready
- [ ] End-to-end testing complete

---

**Document Status:** Living Document  
**Last Updated:** 2026-01-02
