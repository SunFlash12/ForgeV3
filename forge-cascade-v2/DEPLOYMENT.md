# Forge Cascade V2 - Production Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Deployment Options](#deployment-options)
5. [SSL/TLS Setup](#ssltls-setup)
6. [Monitoring & Observability](#monitoring--observability)
7. [Scaling](#scaling)
8. [Backup & Recovery](#backup--recovery)
9. [Security Hardening](#security-hardening)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| CPU | 2 cores | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB | 32+ GB |
| Storage | 50 GB SSD | 100 GB SSD | 500+ GB NVMe |
| Network | 100 Mbps | 1 Gbps | 10 Gbps |

### Software Requirements

- Docker 24.0+
- Docker Compose 2.20+
- Git
- OpenSSL (for certificate generation)

### API Keys Required

1. **LLM Provider** (one of):
   - Anthropic API key (recommended)
   - OpenAI API key

2. **Embedding Provider** (one of):
   - OpenAI API key
   - Local (no key needed, but requires more RAM)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/forge-cascade.git
cd forge-cascade
```

### 2. Configure Environment

```bash
# Copy production template
cp .env.production.example .env.production

# Edit with your values
nano .env.production
```

**Critical values to set:**
- `NEO4J_PASSWORD` - Strong database password
- `REDIS_PASSWORD` - Cache password
- `JWT_SECRET_KEY` - Generate with: `openssl rand -hex 64`
- `LLM_API_KEY` - Your Anthropic or OpenAI key
- `EMBEDDING_API_KEY` - Your OpenAI key (if using OpenAI embeddings)

### 3. Deploy

```bash
cd docker

# Start all services
docker-compose -f docker-compose.prod.yml --env-file ../.env.production up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### 4. Initialize Database

```bash
# Run schema setup
docker-compose -f docker-compose.prod.yml exec api python -m forge.scripts.setup_db

# (Optional) Seed initial data
docker-compose -f docker-compose.prod.yml exec api python -m forge.scripts.seed_data
```

### 5. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

---

## Configuration

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development, staging, production) | production |
| `DEBUG` | Enable debug mode | false |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `NEO4J_URI` | Neo4j connection URI | bolt://neo4j:7687 |
| `REDIS_URL` | Redis connection URL | redis://redis:6379 |
| `JWT_SECRET_KEY` | JWT signing key (min 32 chars) | **required** |
| `LLM_PROVIDER` | LLM provider (anthropic, openai, mock) | anthropic |
| `EMBEDDING_PROVIDER` | Embedding provider (openai, sentence_transformers, mock) | openai |

### Service Ports

| Service | Internal Port | External Port | Protocol |
|---------|--------------|---------------|----------|
| API | 8000 | 8000 | HTTP |
| Frontend | 80 | 3000 | HTTP |
| Neo4j Browser | 7474 | 7474 | HTTP |
| Neo4j Bolt | 7687 | 7687 | Bolt |
| Redis | 6379 | 6379 | Redis |
| Prometheus | 9090 | 9090 | HTTP |
| Grafana | 3000 | 3001 | HTTP |

---

## Deployment Options

### Option 1: Docker Compose (Single Server)

Best for: Development, small deployments

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Docker Swarm (Multi-Server)

Best for: High availability, medium scale

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.prod.yml forge

# Scale API
docker service scale forge_api=4
```

### Option 3: Kubernetes

Best for: Large scale, enterprise

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n forge
```

See `k8s/` directory for Kubernetes manifests.

---

## SSL/TLS Setup

### Option 1: Let's Encrypt (Recommended)

```bash
# Create certificate directory
mkdir -p docker/ssl

# Generate certificate with certbot
docker run -it --rm \
  -v ./docker/ssl:/etc/letsencrypt \
  -p 80:80 \
  certbot/certbot certonly \
  --standalone \
  -d forge.example.com \
  -d api.forge.example.com

# Link certificates
ln -s /etc/letsencrypt/live/forge.example.com/fullchain.pem docker/ssl/fullchain.pem
ln -s /etc/letsencrypt/live/forge.example.com/privkey.pem docker/ssl/privkey.pem
```

### Option 2: Self-Signed (Development Only)

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/privkey.pem \
  -out docker/ssl/fullchain.pem \
  -subj "/CN=forge.local"
```

### Enable HTTPS in Nginx

1. Uncomment HTTPS server block in `nginx.prod.conf`
2. Update `API_URL` and `FRONTEND_URL` to use `https://`
3. Restart nginx: `docker-compose restart nginx`

---

## Monitoring & Observability

### Prometheus Metrics

Access Prometheus at: `http://localhost:9090`

Key metrics to monitor:
- `forge_http_requests_total` - Request count by endpoint
- `forge_http_request_duration_seconds` - Request latency
- `forge_db_query_duration_seconds` - Database query time
- `forge_pipeline_executions_total` - Pipeline execution count
- `forge_overlay_invocations_total` - Overlay usage

### Grafana Dashboards

Access Grafana at: `http://localhost:3001`

Default credentials:
- Username: `admin`
- Password: (value of `GRAFANA_PASSWORD`)

Pre-built dashboards:
1. **System Overview** - CPU, memory, disk
2. **API Performance** - Requests, latency, errors
3. **Database Health** - Neo4j connections, queries
4. **AI Services** - LLM calls, embeddings, search

### Log Aggregation

Logs are shipped to Loki via Promtail.

Query logs in Grafana:
```
{job="forge-api"} |= "error"
```

### Alerting

Configure alerts in Prometheus Alertmanager:

```yaml
# docker/alertmanager.yml
route:
  receiver: 'slack'
  
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/...'
        channel: '#forge-alerts'
```

---

## Scaling

### Horizontal Scaling (API)

```bash
# Scale to 4 API instances
docker-compose -f docker-compose.prod.yml up -d --scale api=4

# Or with Docker Swarm
docker service scale forge_api=4
```

### Vertical Scaling

Update resource limits in `docker-compose.prod.yml`:

```yaml
api:
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: "4"
```

### Database Scaling

For high-traffic deployments:

1. **Neo4j Cluster** - Use Neo4j Enterprise for clustering
2. **Read Replicas** - Configure read-only replicas for queries
3. **Connection Pooling** - Increase `NEO4J_MAX_CONNECTION_POOL_SIZE`

---

## Backup & Recovery

### Database Backup

```bash
# Backup Neo4j
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups/

# Copy backup to host
docker cp forge-neo4j:/backups/neo4j.dump ./backups/

# Schedule daily backups (crontab)
0 2 * * * /path/to/backup-script.sh
```

### Restore Database

```bash
# Stop API
docker-compose stop api

# Restore Neo4j
docker cp ./backups/neo4j.dump forge-neo4j:/backups/
docker-compose exec neo4j neo4j-admin database load neo4j --from-path=/backups/neo4j.dump --overwrite-destination

# Start API
docker-compose start api
```

### Redis Backup

Redis uses append-only file (AOF) for persistence. Files are in the `redis_data` volume.

```bash
# Backup Redis
docker-compose exec redis redis-cli -a $REDIS_PASSWORD BGSAVE
docker cp forge-redis:/data/dump.rdb ./backups/
```

---

## Security Hardening

### 1. Network Security

```bash
# Restrict Neo4j to internal network only
# In docker-compose.prod.yml:
neo4j:
  ports:
    - "127.0.0.1:7474:7474"  # Only localhost
```

### 2. Secret Management

For production, use a secrets manager:

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name forge/production/jwt-secret \
  --secret-string "your-jwt-secret"

# HashiCorp Vault
vault kv put secret/forge/jwt-secret value="your-jwt-secret"
```

### 3. API Rate Limiting

Configure in `nginx.prod.conf`:

```nginx
# Strict rate limiting for auth endpoints
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/s;
```

### 4. Security Headers

Already configured in nginx:
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`

### 5. Container Security

```bash
# Scan images for vulnerabilities
docker scan forge-cascade-api:latest

# Use read-only containers where possible
docker run --read-only ...
```

---

## Troubleshooting

### Common Issues

#### 1. API won't start

```bash
# Check logs
docker-compose logs api

# Common causes:
# - Database not ready: Wait for Neo4j health check
# - Missing env vars: Verify .env.production
# - Port conflict: Check if 8000 is in use
```

#### 2. Database connection failed

```bash
# Test Neo4j connection
docker-compose exec api python -c "
from forge.database.client import Neo4jClient
import asyncio
async def test():
    client = Neo4jClient()
    await client.connect()
    print('Connected!')
asyncio.run(test())
"
```

#### 3. High memory usage

```bash
# Check memory per container
docker stats

# Reduce Neo4j memory
NEO4J_server_memory_heap_max__size: "2G"
```

#### 4. Slow queries

```bash
# Enable Neo4j query logging
NEO4J_dbms_logs_query_enabled: "true"
NEO4J_dbms_logs_query_threshold: "1s"

# Check slow query log
docker-compose exec neo4j cat /logs/query.log
```

### Health Check Commands

```bash
# Overall system health
curl http://localhost:8000/health

# Detailed readiness
curl http://localhost:8000/ready

# Metrics
curl http://localhost:8000/metrics

# Neo4j status
curl http://localhost:7474

# Redis ping
docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping
```

### Getting Help

- **Documentation**: https://docs.forge.example.com
- **Issues**: https://github.com/your-org/forge-cascade/issues
- **Discord**: https://discord.gg/forge-cascade

---

## Appendix: Production Checklist

### Before Going Live

- [ ] All passwords changed from defaults
- [ ] JWT secret is unique and secure (64+ chars)
- [ ] SSL/TLS configured with valid certificate
- [ ] Backup strategy tested
- [ ] Monitoring and alerting configured
- [ ] Rate limiting enabled
- [ ] Security scan passed
- [ ] Load testing completed
- [ ] Disaster recovery plan documented

### Post-Deployment

- [ ] Health checks passing
- [ ] Metrics flowing to Prometheus
- [ ] Logs aggregating to Loki
- [ ] Alerts configured in Alertmanager
- [ ] Documentation updated
- [ ] Team trained on operations
