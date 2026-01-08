# Forge V3 - Institutional Memory Engine

A cognitive architecture platform for persistent organizational knowledge with AI-powered governance, compliance frameworks, and blockchain integration.

## Architecture

Forge V3 consists of three API services and a React frontend:

| Service | Port | Description |
|---------|------|-------------|
| **Cascade API** | 8001 | Core engine - capsules, governance, overlays, system monitoring |
| **Compliance API** | 8002 | GDPR/privacy compliance - DSARs, consent, breach notification, AI governance |
| **Virtuals API** | 8003 | Blockchain integration - agents, tokenization, ACP, revenue tracking |
| **Frontend** | 5173 | React 19 + TypeScript + Tailwind v4 dashboard |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Neo4j Database** (cloud or local)
- **Redis** (optional, for caching)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/SunFlash12/ForgeV3.git
cd "Forge V3"
```

### 2. Set Up Python Environment

```bash
cd forge-cascade-v2
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in `forge-cascade-v2/`:

```env
# Neo4j Database
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Security
JWT_SECRET_KEY=your-secure-secret-key-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Admin seed password
SEED_ADMIN_PASSWORD=your-secure-admin-password
```

### 4. Initialize Database

```bash
# Set up database schema
python scripts/setup_db.py

# Seed initial data (admin user, sample data)
SEED_ADMIN_PASSWORD="your-password" python scripts/seed_data.py
```

### 5. Start the Servers

**Option A: Start all servers (recommended)**

```bash
# Python (cross-platform)
python start_all_servers.py

# Windows
start_servers.bat

# Linux/Mac
./start_servers.sh
```

**Option B: Start individually**

```bash
# Terminal 1 - Cascade API
python -m uvicorn forge.api.app:app --host 0.0.0.0 --port 8001

# Terminal 2 - Compliance API
python run_compliance.py

# Terminal 3 - Virtuals API
python run_virtuals.py
```

### 6. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Start development server
npm run dev
```

The frontend will be available at http://localhost:5173

## Production Deployment

### Build Frontend

```bash
cd forge-cascade-v2/frontend
npm run build
```

Production files will be in `dist/`. Deploy to any static hosting.

### Run API in Production

```bash
# With Gunicorn (Linux/Mac)
gunicorn forge.api.app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8001

# With Uvicorn
uvicorn forge.api.app:app --host 0.0.0.0 --port 8001 --workers 4
```

## API Documentation

Once running, interactive API docs are available at:

- **Cascade API**: http://localhost:8001/docs
- **Compliance API**: http://localhost:8002/docs
- **Virtuals API**: http://localhost:8003/docs

## Running Tests

### Full Test Suite (195 tests)

```bash
cd "Forge V3"
SEED_ADMIN_PASSWORD="your-password" python test_forge_v3_comprehensive.py
```

### UI Integration Tests (39 tests)

```bash
cd forge-cascade-v2
SEED_ADMIN_PASSWORD="your-password" python test_ui_integration.py
```

## Project Structure

```
Forge V3/
├── forge-cascade-v2/           # Main application
│   ├── forge/                  # Core Python package
│   │   ├── api/               # FastAPI routes
│   │   │   ├── routes/        # API endpoints
│   │   │   ├── app.py         # Main FastAPI app
│   │   │   └── middleware.py  # Auth, CORS, rate limiting
│   │   ├── database/          # Neo4j client
│   │   ├── immune/            # Circuit breakers, anomaly detection
│   │   ├── kernel/            # Event system, pipeline, overlays
│   │   ├── models/            # Pydantic models
│   │   ├── overlays/          # Governance, ML, security overlays
│   │   ├── repositories/      # Data access layer
│   │   ├── security/          # Auth, tokens, passwords
│   │   └── services/          # Business logic
│   ├── frontend/              # React frontend
│   │   ├── src/
│   │   │   ├── api/          # API client
│   │   │   ├── components/   # React components
│   │   │   ├── pages/        # Page components
│   │   │   ├── stores/       # Zustand stores
│   │   │   └── types/        # TypeScript types
│   │   └── dist/             # Production build
│   ├── scripts/               # Setup and utility scripts
│   ├── run_compliance.py      # Standalone compliance server
│   ├── run_virtuals.py        # Standalone virtuals server
│   └── start_all_servers.py   # Multi-server launcher
├── forge_virtuals_integration/ # Virtuals Protocol SDK
├── Documentation/              # Project documentation
└── test_forge_v3_comprehensive.py  # Full test suite
```

## Key Features

### Core Engine (Cascade API)
- **Knowledge Capsules**: Versioned, typed knowledge units with lineage tracking
- **7-Phase Pipeline**: Validation → Enrichment → Classification → Security → Governance → Storage → Indexing
- **Overlay System**: Pluggable processing modules (ML, security, governance)
- **Event System**: Pub/sub for system-wide event handling
- **Ghost Council**: AI ethics committee for governance decisions

### Compliance Framework
- **DSAR Management**: Data Subject Access Requests (GDPR Article 15-22)
- **Consent Tracking**: Granular consent management with GPC support
- **Breach Notification**: 72-hour breach reporting workflow
- **AI Governance**: EU AI Act compliance, human-in-the-loop reviews

### Virtuals Integration
- **Agent Management**: Create and run AI agents
- **Tokenization**: Bonding curves, governance tokens
- **ACP Protocol**: Agent Commerce Protocol for service offerings
- **Revenue Tracking**: DCF valuation, revenue analytics

### Security
- **JWT Authentication**: Access + refresh tokens in httpOnly cookies
- **CSRF Protection**: Token-based CSRF prevention
- **Trust Hierarchy**: Role-based access with trust levels
- **Rate Limiting**: Redis-backed request throttling
- **Circuit Breakers**: Automatic failure isolation

## Default Credentials

After running `seed_data.py`:

| Username | Role | Description |
|----------|------|-------------|
| admin | admin | System administrator |
| oracle | user | High-trust user |
| developer | user | Standard user |
| analyst | user | Standard user |

Passwords are set via `SEED_ADMIN_PASSWORD` environment variable.

## Troubleshooting

### Neo4j Connection Issues
- Verify `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` in `.env`
- Check Neo4j instance is running and accessible
- For cloud instances, ensure IP is whitelisted

### Port Already in Use
```bash
# Find and kill process on port (Windows)
netstat -ano | findstr :8001
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8001
kill -9 <pid>
```

### Frontend Can't Connect to API
- Ensure `.env` has correct `VITE_API_URL=http://localhost:8001/api/v1`
- Restart frontend dev server after changing `.env`
- Check CORS settings in backend

## License

Proprietary - All rights reserved.

## Support

For issues and feature requests, visit: https://github.com/SunFlash12/ForgeV3/issues
