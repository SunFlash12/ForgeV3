# Forge Cascade V2 - Docker Deployment

This guide covers deploying Forge Cascade V2 using Docker.

## Prerequisites

- Docker 24.0+
- Docker Compose 2.20+
- Neo4j Aura account (or self-hosted Neo4j 5.x)

## Quick Start

### 1. Configure Environment

Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your Neo4j credentials and generate a JWT secret:

```bash
# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Build and Start

```bash
cd docker
docker compose up -d --build
```

### 3. Initialize Database

```bash
# Run database setup
docker compose exec backend python scripts/setup_db.py

# Seed initial data (optional)
docker compose exec backend python scripts/seed_data.py
```

### 4. Access the Application

- **Frontend**: http://localhost
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Services

| Service | Port | Description |
|---------|------|-------------|
| frontend | 80 | React SPA served by Nginx |
| backend | 8000 | FastAPI application |
| redis | 6379 | Cache and pub/sub |

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `NEO4J_URI` | Neo4j connection URI | Yes |
| `NEO4J_USERNAME` | Neo4j username | Yes |
| `NEO4J_PASSWORD` | Neo4j password | Yes |
| `JWT_SECRET_KEY` | Secret for JWT signing | Yes |
| `REDIS_URL` | Redis connection URL | No (defaults to redis://redis:6379/0) |
| `LOG_LEVEL` | Logging level | No (defaults to INFO) |

### Resource Limits

To add resource limits, edit `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Operations

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
```

### Health Checks

```bash
# Check all services
docker compose ps

# Run health check script
docker compose exec backend python scripts/health_check.py

# Check specific endpoints
curl http://localhost:8000/api/v1/system/health
curl http://localhost/health
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart backend
```

### Update Deployment

```bash
# Pull latest changes and rebuild
git pull
docker compose up -d --build
```

### Stop Services

```bash
# Stop but keep volumes
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Troubleshooting

### Backend won't start

1. Check Neo4j connectivity:
   ```bash
   docker compose exec backend python -c "
   from forge.database.client import Neo4jClient
   from forge.config import get_settings
   import asyncio
   
   async def test():
       s = get_settings()
       c = Neo4jClient(s.neo4j_uri, s.neo4j_username, s.neo4j_password)
       await c.connect()
       print('Connected!')
       await c.disconnect()
   
   asyncio.run(test())
   "
   ```

2. Check logs for errors:
   ```bash
   docker compose logs backend
   ```

### Frontend shows blank page

1. Check if backend is healthy:
   ```bash
   curl http://localhost:8000/api/v1/system/health
   ```

2. Check nginx logs:
   ```bash
   docker compose logs frontend
   ```

### Database connection issues

1. Verify Neo4j Aura is accessible
2. Check firewall/security group rules
3. Verify credentials in `.env`

## Production Considerations

### SSL/TLS

For production, add SSL termination via a reverse proxy (Traefik, Nginx, Caddy) or use a cloud load balancer.

### Scaling

The backend is stateless and can be scaled horizontally:

```yaml
services:
  backend:
    deploy:
      replicas: 3
```

### Monitoring

Consider adding:
- Prometheus for metrics
- Grafana for dashboards
- ELK stack for log aggregation

### Backup

Neo4j Aura handles backups automatically. For Redis data persistence, the `appendonly yes` flag is enabled.

## Development

### Local Development

For local development without Docker:

```bash
# Backend
cd forge-cascade-v2
pip install -e .
uvicorn forge.api.app:create_app --factory --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Building Images Locally

```bash
# Build backend
docker build -f docker/Dockerfile.backend -t forge-backend .

# Build frontend
docker build -f docker/Dockerfile.frontend -t forge-frontend .
```

## Support

For issues, check:
1. Logs: `docker compose logs`
2. Health: `scripts/health_check.py`
3. Documentation: `BUILD_PLAN.md`
