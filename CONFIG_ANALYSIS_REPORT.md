# Forge V3 Configuration Analysis Report

**Generated:** January 2026
**Project:** Forge Cascade V3
**Domains:** forgecascade.org, forgeshop.org

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Docker Compose Files](#docker-compose-files)
3. [Dockerfiles](#dockerfiles)
4. [GitHub Actions CI/CD](#github-actions-cicd)
5. [Nginx Configurations](#nginx-configurations)
6. [Infrastructure Configurations](#infrastructure-configurations)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [Recommendations Summary](#recommendations-summary)

---

## Executive Summary

The Forge V3 project has a well-architected configuration setup supporting:
- **Multi-environment deployment** (development, production, Cloudflare tunnel)
- **Microservices architecture** with 3 backend APIs (Cascade, Compliance, Virtuals)
- **Two frontend applications** (Forge Cascade, Forge Shop/Marketplace)
- **Full observability stack** (Jaeger, Prometheus, Grafana, Loki)
- **Automated CI/CD** with GitHub Actions

**Overall Assessment:** The configuration is production-ready with good security practices, but has some placeholder code, duplicate configurations, and opportunities for optimization.

---

## Docker Compose Files

### 1. Root `docker-compose.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\docker-compose.yml`

#### What It Does
Main development/production compose file that orchestrates the core Forge services including 3 APIs, 2 frontends, Redis cache, and Jaeger tracing.

#### Why It Does It
- Provides a single command deployment (`docker-compose up`)
- Manages inter-service dependencies and networking
- Configures health checks for reliability

#### How It Does It
- Uses a bridge network (`forge-network`) for service discovery
- Environment variables from `.env` file for configuration
- Health checks ensure services start in correct order
- Resource limits prevent runaway containers

#### Key Components
```yaml
Services:
  - cascade-api (port 8001) - Main API
  - compliance-api (port 8002) - Compliance checking
  - virtuals-api (port 8003) - Blockchain integration
  - frontend (port 80) - Main Forge Cascade UI
  - marketplace (port 3001) - Forge Shop UI
  - redis (port 6379) - Cache/session store
  - jaeger (port 16686) - Distributed tracing
  - db-setup, db-seed (profile: setup) - One-time database initialization
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Hardcoded production URLs | Medium | `VITE_API_URL=https://forgecascade.org/api/v1` baked into build args |
| Exposed Redis port | Medium | Port 6379 exposed externally - should only be internal |
| Default Redis password | Low | `forge_redis_secret` as default is weak |
| Mock LLM default | Info | `LLM_PROVIDER=${LLM_PROVIDER:-mock}` good for dev, but confusing |

#### Improvement Opportunities
1. Remove external port mapping for Redis (`ports: - "6379:6379"`)
2. Use stronger default passwords or require them
3. Add labels for container organization
4. Consider using Docker secrets for sensitive values

#### Possibilities Opened
- Easy local development setup
- Horizontal scaling potential with `--scale` flag
- Service mesh ready architecture

---

### 2. `docker-compose.prod.yml` (Root)

**Location:** `C:\Users\idean\Downloads\Forge V3\docker-compose.prod.yml`

#### What It Does
Production deployment with nginx reverse proxy, SSL termination via certbot, and pre-built images from GitHub Container Registry.

#### Why It Does It
- Adds SSL/TLS layer for security
- Uses pre-built images for faster deployment
- Provides automatic certificate renewal

#### How It Does It
```yaml
Key Features:
- nginx: Reverse proxy with SSL termination
- certbot: Automatic Let's Encrypt certificate renewal (every 12h check)
- Images from ghcr.io/${GITHUB_REPO:-forgecascade/forge}/*:${VERSION:-latest}
- Internal-only service exposure (expose vs ports)
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Redis no password | High | Production Redis has no authentication: `redis://redis:6379` |
| Jaeger UI exposed | Medium | Port 16686 publicly accessible - should be internal only |
| Missing resource limits | Medium | Services don't have memory/CPU limits except Redis |

#### Placeholder/Non-Functioning Code
- **None found** - This file appears complete and functional

#### Improvement Opportunities
1. Add `requirepass` to Redis command
2. Remove public port for Jaeger or add authentication
3. Add resource limits to all services
4. Consider adding Prometheus/Grafana for monitoring

---

### 3. `docker-compose.cloudflare.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\docker-compose.cloudflare.yml`

#### What It Does
Zero-cost hosting solution using Cloudflare Tunnel to expose services without a dedicated IP or VPS.

#### Why It Does It
- Eliminates need for VPS hosting costs
- No SSL certificate management needed (Cloudflare handles it)
- DDoS protection built-in

#### How It Does It
```yaml
cloudflared:
  image: cloudflare/cloudflared:latest
  command: tunnel --no-autoupdate run
  environment:
    - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Missing tunnel config | Info | Requires external Cloudflare dashboard configuration |

#### Improvement Opportunities
1. Add tunnel configuration file for reproducibility
2. Document Cloudflare dashboard setup requirements

#### Possibilities Opened
- **Free hosting** for small deployments
- Global CDN and DDoS protection
- No need to manage SSL certificates

---

### 4. `docker-compose.backup.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\docker-compose.backup.yml`

#### What It Does
Automated Neo4j database backup system with scheduling and optional S3 upload.

#### Why It Does It
- Data protection and disaster recovery
- Configurable retention policy
- Both full and incremental backup support

#### How It Does It
```yaml
Key Features:
- Cron-based scheduling (default: full at 2AM, incremental every 6h)
- 30-day retention policy
- Optional S3 upload for offsite backup
- Docker profile ensures it only runs when explicitly requested
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| External network dependency | Medium | Uses `external: true` network - may fail if main stack not running |
| Missing health check | Low | No health check defined |

#### Improvement Opportunities
1. Add health check endpoint
2. Add notification on backup success/failure (webhook, email)
3. Add backup verification step

---

### 5. `forge-cascade-v2/docker/docker-compose.prod.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\docker\docker-compose.prod.yml`

#### What It Does
**Most comprehensive** production setup including:
- Full Neo4j database
- Complete observability stack (Prometheus, Grafana, Loki, Promtail)
- Nginx reverse proxy with production config

#### Why It Does It
- Self-hosted production environment with all dependencies
- Full monitoring and logging capabilities
- Enterprise-grade setup

#### Key Differences from Root Compose
```yaml
Additions:
- neo4j: Enterprise database with APOC and GDS plugins
- prometheus: Metrics collection
- grafana: Visualization dashboards
- loki + promtail: Log aggregation
- Custom network subnet (172.28.0.0/16)
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Duplicate compose files | Medium | Similar functionality split across multiple files |
| Neo4j Enterprise license | Info | Requires accepting license agreement |
| Missing promtail config | High | References `./promtail.yml` which may not exist |
| Missing grafana dashboards | Medium | References `./grafana/dashboards` directory |

#### Placeholder/Non-Functioning Code
```yaml
# These configuration files are referenced but may not exist:
- ./prometheus.yml (exists, but incomplete)
- ./promtail.yml (NOT FOUND)
- ./grafana/provisioning (NOT FOUND)
- ./grafana/dashboards (NOT FOUND)
```

#### Improvement Opportunities
1. Create missing configuration files
2. Consolidate with root docker-compose.prod.yml
3. Add alertmanager for Prometheus alerts

---

### 6. `deploy/docker-compose.prod.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\deploy\docker-compose.prod.yml`

#### What It Does
Simplified production deployment using pre-built images with version pinning.

#### Key Features
```yaml
- Uses specific image versions: ghcr.io/sunflash12/forgev3/cascade-api:1.0.2
- Nginx auto-reload every 6 hours
- Certbot with automatic renewal
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Hardcoded username | Low | `sunflash12` in image path should be variable |
| Placeholder domain | High | `CORS_ORIGINS=${CORS_ORIGINS:-https://your-domain.com}` |

---

## Dockerfiles

### 1. `forge-cascade-v2/Dockerfile` (Main Backend)

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\Dockerfile`

#### What It Does
Builds the Python FastAPI backend for Cascade API.

#### How It Does It
```dockerfile
FROM python:3.11-slim
# Install gcc, libpq-dev, curl for dependencies
# Copy and install requirements first (layer caching)
# Create non-root user 'forge' (UID 1000)
# Run uvicorn on port 8001
```

#### Security Features
- Non-root user execution
- Minimal base image (slim)
- No cache pip install

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Single-stage build | Low | Could use multi-stage to reduce image size |
| No .dockerignore check | Info | May include unnecessary files |

#### Improvement Opportunities
1. Use multi-stage build (see `docker/Dockerfile.backend` for example)
2. Pin system package versions
3. Add security scanning step

---

### 2. `forge-cascade-v2/docker/Dockerfile.backend` (Advanced Backend)

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\docker\Dockerfile.backend`

#### What It Does
**Production-optimized** multi-stage build with advanced features.

#### How It Does It
```dockerfile
# Stage 1: Builder - Install dependencies in virtual environment
FROM python:${PYTHON_VERSION}-slim as builder
RUN python -m venv /opt/venv
RUN pip install -r requirements.txt

# Stage 2: Runtime - Minimal production image
FROM python:${PYTHON_VERSION}-slim as runtime
COPY --from=builder /opt/venv /opt/venv
# Uses dumb-init for proper signal handling
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["uvicorn", "forge.api.app:app", "--workers", "4"]
```

#### Superior Features
- **Multi-stage build** - Smaller final image
- **dumb-init** - Proper PID 1 signal handling
- **4 worker processes** - Better concurrency
- **OCI labels** - Container metadata
- **Virtual environment** - Clean dependency isolation

#### Issues Found
| Issue | Severity | Description |
|-------|----------|-------------|
| Port mismatch | Medium | Uses port 8000, but main compose expects 8001 |
| Not used by default | Info | Main docker-compose uses simpler Dockerfile |

---

### 3. Frontend Dockerfiles

**Locations:**
- `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\frontend\Dockerfile`
- `C:\Users\idean\Downloads\Forge V3\marketplace\Dockerfile`

#### What They Do
Multi-stage builds for React/Vite applications served via nginx.

#### How They Do It
```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
RUN npm ci  # or npm install --legacy-peer-deps for marketplace
RUN npm run build

# Stage 2: Production
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
RUN echo "healthy" > /usr/share/nginx/html/health
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Marketplace uses `npm install` | Low | Should use `npm ci` for reproducibility |
| Missing package-lock.json | Low | Marketplace Dockerfile copies only package.json |
| No non-root user | Medium | nginx runs as root in marketplace Dockerfile |

---

### 4. Backup Service Dockerfile

**Location:** `C:\Users\idean\Downloads\Forge V3\scripts\backup\Dockerfile`

#### What It Does
Python-based Neo4j backup service with cron scheduling.

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Missing entrypoint.sh | High | References file that may not exist |
| Missing backup scripts | High | References neo4j_backup.py, neo4j_restore.py |

---

## GitHub Actions CI/CD

### 1. `.github/workflows/ci.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\.github\workflows\ci.yml`

#### What It Does
Comprehensive CI/CD pipeline with:
1. Lint & Type Check
2. Backend Tests
3. Frontend Build
4. Docker Image Build & Push
5. Security Scan (Trivy)
6. Deployment

#### Workflow Triggers
```yaml
on:
  push:
    branches: [master, main, develop]
  pull_request:
    branches: [master, main]
  workflow_dispatch:
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Lint failures ignored | Medium | `ruff check ... \|\| true` - errors don't fail build |
| ESLint failures ignored | Medium | `npm run lint \|\| true` - errors don't fail build |
| Test failures soft | Medium | `python test_ui_integration.py \|\| true` |
| Security scan non-blocking | Low | `exit-code: '0'` means vulnerabilities don't fail build |

#### Placeholder Code
```yaml
# Deployment section is placeholder:
deploy:
  steps:
    - name: Deploy notification
      run: |
        echo "Deployment triggered..."
        # Add your deployment steps here (COMMENTED OUT)
        # - name: Deploy to server
        #   uses: appleboy/ssh-action@v1.0.0
```

#### Improvement Opportunities
1. Remove `|| true` from critical checks
2. Make security scan blocking for CRITICAL vulnerabilities
3. Implement actual deployment steps
4. Add Slack/Discord notifications
5. Add branch protection requiring CI pass

---

### 2. `.github/workflows/release.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\.github\workflows\release.yml`

#### What It Does
Creates GitHub releases when version tags (v*) are pushed.

#### Features
- Builds and pushes versioned Docker images
- Auto-generates changelog from commits
- Creates GitHub release with download instructions
- Marks alpha/beta/rc as pre-releases

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| No tests before release | High | Builds and releases without running tests |
| Hardcoded localhost URL | Low | `VITE_API_URL=http://localhost:8001/api/v1` in build args |

#### Improvement Opportunities
1. Add test job as dependency
2. Use production URL for release builds
3. Add release notes template

---

### 3. `.github/workflows/pr-check.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\.github\workflows\pr-check.yml`

#### What It Does
Quick validation for pull requests - faster than full CI.

#### Features
- Python syntax check
- TypeScript check
- Frontend build verification
- Docker build verification (no push)

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Duplicate with ci.yml | Medium | PRs trigger both workflows |
| No tests | Medium | Only syntax/build checks, no actual tests |

---

### 4. `.github/dependabot.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\.github\dependabot.yml`

#### What It Does
Automated dependency updates for:
- Python (pip)
- JavaScript (npm)
- Docker base images
- GitHub Actions

**Configuration:** Weekly updates on Monday, max 5 PRs per ecosystem

**Assessment:** Well configured, no issues found.

---

### 5. `forge-cascade-v2/.github/workflows/ci-cd.yml`

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\.github\workflows\ci-cd.yml`

#### What It Does
**Duplicate/Alternative** CI/CD pipeline within the forge-cascade-v2 subdirectory.

#### Differences from Root CI
- Uses actions/checkout@v4 (root uses v6)
- Uses docker/build-push-action@v5 (root uses v6)
- Includes Black formatter check
- Has staging environment deployment
- Integration tests with Neo4j service container

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Duplicate workflow | High | Confusing to have two CI/CD configurations |
| Won't trigger | High | Located in subdirectory, GitHub won't detect it |
| Placeholder deployment | Medium | Deploy steps just echo messages |

---

## Nginx Configurations

### 1. Main Nginx Config (`deploy/nginx/nginx.conf`)

**Location:** `C:\Users\idean\Downloads\Forge V3\deploy\nginx\nginx.conf`

#### What It Does
Main nginx.conf for production reverse proxy.

#### Security Features
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

#### Performance Features
```nginx
# Optimizations
sendfile on;
tcp_nopush on;
tcp_nodelay on;
gzip on;
gzip_comp_level 6;
```

**Assessment:** Good production configuration.

---

### 2. Site Configurations

#### `deploy/nginx/sites/forgecascade.org.conf`

**What It Does:** Domain-specific configuration for main Forge Cascade site.

**Key Features:**
- Let's Encrypt SSL with OCSP stapling
- HTTP/2 support
- Strict CSP headers
- Rate limiting per endpoint type (auth: 10r/s, api: 100r/s)
- WebSocket support with 7-day timeout
- Request ID tracing
- www to non-www redirect

#### `deploy/nginx/sites/forgeshop.org.conf`

**What It Does:** Configuration for Forge Shop marketplace.

**Key Features:**
- Shares auth backend with main site
- Custom `X-Origin-Domain` header for multi-tenant support
- Routes to marketplace frontend

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| CSP allows unsafe-inline/eval | Medium | `'unsafe-inline' 'unsafe-eval'` weakens security |
| Missing CORS headers | Low | May need explicit CORS for API routes |

---

### 3. Frontend Nginx Configs

**Locations:**
- `forge-cascade-v2/frontend/nginx.conf`
- `marketplace/nginx.conf`

#### What They Do
SPA routing configuration for React applications.

#### Key Features
```nginx
# SPA routing - serve index.html for all routes
location / {
    try_files $uri $uri/ /index.html;
}

# API proxy to backend (forge-cascade-v2/frontend only)
location /api/ {
    proxy_pass http://cascade-api:8001/api/;
}

# Don't cache index.html
location = /index.html {
    add_header Cache-Control "no-cache, no-store, must-revalidate";
}
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| X-XSS-Protection deprecated | Info | Modern browsers ignore this header |

---

### 4. Advanced Nginx Config (`forge-cascade-v2/docker/nginx.prod.conf`)

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\docker\nginx.prod.conf`

#### What It Does
**Most comprehensive** nginx configuration with enterprise features.

#### Advanced Features
```nginx
# JSON logging for log aggregation
log_format json escape=json '{...}';

# Upstream with load balancing
upstream api_backend {
    least_conn;
    server api:8000 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

# Metrics endpoint restricted to internal networks
location /metrics {
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 192.168.0.0/16;
    deny all;
}
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Placeholder SSL paths | High | References `/etc/nginx/ssl/` but certs may not exist |
| HTTP redirect loop | Medium | Line 132: `return 301 http://$host$request_uri;` - should redirect to HTTPS |

---

## Infrastructure Configurations

### 1. Prometheus Configuration

**Location:** `C:\Users\idean\Downloads\Forge V3\forge-cascade-v2\docker\prometheus.yml`

#### What It Does
Metrics collection configuration for Prometheus.

#### Configured Targets
```yaml
- prometheus (self)
- forge-api:8000/metrics
- neo4j:2004/metrics (if enabled)
# Commented out:
# - redis-exporter:9121
# - nginx-exporter:9113
# - node-exporter:9100
```

#### Issues Found

| Issue | Severity | Description |
|-------|----------|-------------|
| Empty alertmanager | Medium | Alerting not configured |
| Commented exporters | Info | Redis, nginx, node metrics not collected |

---

## Cross-Cutting Concerns

### Environment Variables

**Required Secrets (Must be configured):**
```bash
# Database
NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD

# Security
JWT_SECRET_KEY

# AI Services
LLM_API_KEY
EMBEDDING_API_KEY

# Optional
SENTRY_DSN
CLOUDFLARE_TUNNEL_TOKEN
AWS_ACCESS_KEY_ID (for S3 backup)
```

### Duplicate Configurations

| Category | Files | Recommendation |
|----------|-------|----------------|
| Docker Compose | 6 files | Consolidate to 3: dev, prod, cloudflare |
| Dockerfiles | 6 files | Keep specialized ones, document purpose |
| CI/CD | 4 workflows + 1 orphan | Remove orphan, consolidate where possible |
| Nginx | 5 configs | Keep - different purposes |

### Missing Files (Referenced but not found)

1. `promtail.yml` - Log shipper configuration
2. `grafana/provisioning/*` - Grafana data sources
3. `grafana/dashboards/*` - Pre-configured dashboards
4. `scripts/backup/neo4j_backup.py` - Backup script
5. `scripts/backup/neo4j_restore.py` - Restore script
6. `scripts/backup/entrypoint.sh` - Backup entrypoint

---

## Recommendations Summary

### Critical (Fix Immediately)

1. **Add Redis authentication** in production compose files
2. **Remove `|| true`** from CI lint/test steps or document why failures are acceptable
3. **Create missing backup scripts** or remove backup compose file
4. **Fix HTTP redirect loop** in nginx.prod.conf line 132

### High Priority

1. **Consolidate Docker compose files** - reduce from 6 to 3
2. **Move orphaned CI/CD file** from forge-cascade-v2/.github to root
3. **Add tests to release workflow** - don't release untested code
4. **Create missing observability configs** (promtail, grafana dashboards)

### Medium Priority

1. **Remove exposed Redis port** (6379) from development compose
2. **Restrict Jaeger UI access** - internal only or add auth
3. **Use multi-stage Dockerfile** as default backend build
4. **Strengthen CSP headers** - remove unsafe-inline where possible

### Low Priority / Nice to Have

1. Add Docker secrets support
2. Implement actual deployment in CI/CD
3. Add Slack/Discord notifications
4. Add backup success/failure webhooks
5. Pin all action versions to SHA

---

## Possibilities This Configuration Opens

### Deployment Options
1. **Self-hosted VPS** - Full control with docker-compose.prod.yml
2. **Free Cloudflare** - Zero-cost hosting for small deployments
3. **Kubernetes-ready** - Service architecture maps well to K8s
4. **Hybrid cloud** - Database on managed service, compute self-hosted

### Scaling Capabilities
1. **Horizontal API scaling** - `docker-compose up --scale cascade-api=4`
2. **Load balancing** - nginx upstream configuration ready
3. **Read replicas** - Neo4j Enterprise supports clustering

### Monitoring & Observability
1. **Distributed tracing** - Jaeger with OpenTelemetry
2. **Metrics** - Prometheus with custom API metrics
3. **Log aggregation** - Loki + Promtail (needs config)
4. **Dashboards** - Grafana (needs dashboards)

### Security Features
1. **SSL/TLS** - Let's Encrypt auto-renewal
2. **Rate limiting** - Per-endpoint rate limits
3. **WAF-ready** - Cloudflare tunnel provides basic protection
4. **Audit logging** - JSON log format for analysis

---

## File Reference

| File | Status | Purpose |
|------|--------|---------|
| `docker-compose.yml` | Active | Main development/production |
| `docker-compose.prod.yml` | Active | Production with nginx/certbot |
| `docker-compose.cloudflare.yml` | Active | Free Cloudflare hosting |
| `docker-compose.backup.yml` | Incomplete | Backup service |
| `forge-cascade-v2/docker/docker-compose.yml` | Legacy | Old compose file |
| `forge-cascade-v2/docker/docker-compose.prod.yml` | Legacy | Old production with Neo4j |
| `deploy/docker-compose.prod.yml` | Active | VPS deployment |
| `.github/workflows/ci.yml` | Active | Main CI/CD |
| `.github/workflows/release.yml` | Active | Release automation |
| `.github/workflows/pr-check.yml` | Active | PR validation |
| `forge-cascade-v2/.github/workflows/ci-cd.yml` | Orphan | Won't trigger |

---

*This report was generated by analyzing all configuration files in the Forge V3 project. For questions or clarifications, please refer to the specific file paths noted throughout this document.*
