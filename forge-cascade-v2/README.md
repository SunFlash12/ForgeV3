# Forge Cascade V2

**Institutional Memory Engine** - A cognitive architecture platform designed to solve ephemeral wisdom in AI systems.

## Overview

Forge Cascade enables AI systems to maintain persistent memory across generations, preventing the loss of learned knowledge when systems are upgraded, retrained, or restarted.

### Core Features

- **🧠 Persistent Memory**: Knowledge survives across system generations via Capsules
- **🔗 Symbolic Inheritance**: Traceable lineage (Isnad) linking new knowledge to ancestors
- **🗳️ Self-Governance**: Democratic processes and ethical guardrails via Ghost Council
- **🛡️ Self-Healing**: Immune system detects, quarantines, and repairs issues
- **⚡ Optimized Pipeline**: Parallelized 7-phase coordination (~1.2s latency)

### Architecture Highlights (V2)

| Component | Technology | Benefit |
|-----------|------------|---------|
| Database | Neo4j 5.x (Aura) | Unified graph + vector + properties |
| Backend | FastAPI + Python 3.12 | Async, type-safe, WebSocket support |
| Frontend | React 19 + Vite + Tailwind v4 | Modern, responsive dashboard |
| Pipeline | Parallelized phases | 3x latency improvement |
| Immune System | Canary + Circuit Breaker | Prevents autoimmune failures |

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and configure
cd forge-cascade-v2
cp .env.example .env
# Edit .env with your Neo4j credentials and JWT secret

# Start all services
cd docker
docker compose up -d --build

# Initialize database
docker compose exec backend python scripts/setup_db.py
docker compose exec backend python scripts/seed_data.py

# Access the application
# Frontend: http://localhost
# API Docs: http://localhost:8000/docs
```

### Option 2: Local Development

```bash
# Backend
cd forge-cascade-v2
python -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env  # Configure your settings
python scripts/setup_db.py
python scripts/seed_data.py
uvicorn forge.api.app:create_app --factory --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev  # http://localhost:5173
```

## Project Structure

```
forge-cascade-v2/
├── forge/                    # Backend package
│   ├── api/                 # FastAPI routes & WebSockets
│   ├── database/            # Neo4j integration
│   ├── immune/              # Circuit breakers, anomaly detection
│   ├── kernel/              # Event system, pipeline
│   ├── models/              # Pydantic models
│   ├── overlays/            # ML, security, governance, lineage
│   ├── repositories/        # Data access layer
│   └── security/            # Auth, trust, capabilities
├── frontend/                # React dashboard
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # UI components
│   │   ├── pages/          # Route pages
│   │   └── stores/         # Zustand state
│   └── dist/               # Production build
├── docker/                  # Docker deployment
├── scripts/                 # Utility scripts
└── tests/                   # Test suite
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login, get JWT
- `POST /api/v1/auth/refresh` - Refresh access token

### Capsules (Knowledge)
- `GET /api/v1/capsules` - List capsules
- `POST /api/v1/capsules` - Create capsule
- `GET /api/v1/capsules/{id}` - Get capsule
- `GET /api/v1/capsules/{id}/lineage` - Get ancestry tree
- `GET /api/v1/capsules/search` - Semantic search

### Governance
- `GET /api/v1/governance/proposals` - List proposals
- `POST /api/v1/governance/proposals` - Create proposal
- `POST /api/v1/governance/proposals/{id}/vote` - Cast vote
- `POST /api/v1/governance/ghost-council/{id}` - Get AI recommendation

### Overlays
- `GET /api/v1/overlays` - List overlays
- `POST /api/v1/overlays/{id}/activate` - Activate overlay
- `GET /api/v1/overlays/{id}/metrics` - Overlay performance

### System
- `GET /api/v1/system/health` - Health check
- `GET /api/v1/system/metrics` - System metrics
- `GET /api/v1/system/anomalies` - Active anomalies

### WebSocket
- `WS /ws/events` - Real-time event stream
- `WS /ws/dashboard` - Dashboard metrics
- `WS /ws/chat` - Ghost Council chat

## Core Concepts

### Capsule
The atomic unit of knowledge. Capsules are versioned, owned, and can inherit from parent capsules.

```json
{
  "id": "uuid",
  "title": "System Architecture",
  "content": "Knowledge content...",
  "domain": "architecture",
  "visibility": "public",
  "trust_level": "STANDARD"
}
```

### Overlay
Specialized modules providing functionality:
- **Security Validator**: Content security checks
- **ML Intelligence**: Pattern recognition
- **Governance**: Policy enforcement
- **Lineage Tracker**: Ancestry tracking

### Trust Hierarchy
```
CORE (100) → TRUSTED (80) → STANDARD (60) → SANDBOX (40) → UNTRUSTED (20)
```

### Ghost Council
AI-powered governance mechanism providing wisdom on proposals.

## Default Credentials

After running `seed_data.py`:
- Admin: `admin` / `AdminPass123!`
- Developer: `developer` / `DevPass123!`
- Analyst: `analyst` / `AnalystPass123!`

## Configuration

See `.env.example` for all options. Key settings:

| Variable | Description |
|----------|-------------|
| `NEO4J_URI` | Neo4j Aura connection URI |
| `NEO4J_USERNAME` | Database username |
| `NEO4J_PASSWORD` | Database password |
| `JWT_SECRET_KEY` | Secret for JWT signing |
| `REDIS_URL` | Redis connection (optional) |

## Development

```bash
# Run tests
pytest

# Type checking
mypy forge

# Linting
ruff check forge

# Format code
black forge

# Frontend build
cd frontend && npm run build
```

## Health Check

```bash
# Script
python scripts/health_check.py

# API endpoint
curl http://localhost:8000/api/v1/system/health
```

## License

MIT License

## Author

Created by Idean as part of the Forge project.

---

**Build Plan**: See `BUILD_PLAN.md` for detailed development status.
