# Forge Cascade - Disaster Recovery Procedures

This document outlines disaster recovery procedures for the Forge Cascade platform.

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Procedures](#recovery-procedures)
4. [Contact Information](#contact-information)

---

## Overview

### Critical Components

| Component | Data Type | Backup Frequency | Recovery Priority |
|-----------|-----------|------------------|-------------------|
| Neo4j Database | User data, capsules, relationships | Daily full + 6-hour incremental | P1 - Critical |
| Redis | Session data, token blacklist | Persistent (AOF) | P2 - High |
| Application Configs | Environment variables, secrets | Manual/version controlled | P1 - Critical |

### Recovery Time Objectives (RTO)

- **Critical Services**: < 1 hour
- **Full Platform**: < 4 hours

### Recovery Point Objectives (RPO)

- **Database**: < 6 hours (incremental backup frequency)
- **Session Data**: < 15 minutes (Redis AOF)

---

## Backup Strategy

### Neo4j Database Backups

Backups are managed by the automated backup scripts in `scripts/backup/`.

#### Backup Schedule

- **Full Backup**: Daily at 2:00 AM UTC
- **Incremental Backup**: Every 6 hours
- **Retention**: 30 days

#### Manual Backup

```bash
# Full backup
cd /path/to/forge-v3
python scripts/backup/neo4j_backup.py --backup-dir ./backups/neo4j

# Incremental backup
python scripts/backup/neo4j_backup.py --incremental --backup-dir ./backups/neo4j
```

#### Docker-based Backup

```bash
# One-shot backup
docker compose -f docker-compose.yml -f docker-compose.backup.yml run --rm backup backup full

# Start automated backup service
docker compose -f docker-compose.yml -f docker-compose.backup.yml --profile backup up -d backup
```

### Backup File Locations

```
/backups/neo4j/
├── neo4j_backup_full_20240108_020000.json.gz      # Full backup
├── neo4j_backup_incremental_20240108_080000.json.gz
├── neo4j_backup_incremental_20240108_140000.json.gz
└── neo4j_backup_incremental_20240108_200000.json.gz
```

### Redis Data Persistence

Redis uses Append-Only File (AOF) persistence with data stored in the `redis-data` Docker volume.

```bash
# Backup Redis data
docker cp forge-redis:/data/appendonly.aof ./backups/redis/
```

---

## Recovery Procedures

### Scenario 1: Database Corruption or Data Loss

#### Steps

1. **Identify the issue**
   ```bash
   docker logs forge-cascade-api --tail 100
   ```

2. **Stop the affected services**
   ```bash
   docker compose stop cascade-api
   ```

3. **List available backups**
   ```bash
   ls -la backups/neo4j/
   ```

4. **Select the most recent valid backup**
   ```bash
   # Dry run to validate backup
   python scripts/backup/neo4j_restore.py backups/neo4j/neo4j_backup_full_YYYYMMDD_HHMMSS.json.gz --dry-run
   ```

5. **Restore the database**
   ```bash
   # For a fresh restore (clears existing data)
   python scripts/backup/neo4j_restore.py backups/neo4j/neo4j_backup_full_YYYYMMDD_HHMMSS.json.gz --clear-first --force

   # For adding data back (no clear)
   python scripts/backup/neo4j_restore.py backups/neo4j/neo4j_backup_full_YYYYMMDD_HHMMSS.json.gz --force
   ```

6. **Apply incremental backups if needed**
   ```bash
   python scripts/backup/neo4j_restore.py backups/neo4j/neo4j_backup_incremental_YYYYMMDD_HHMMSS.json.gz --force
   ```

7. **Restart services**
   ```bash
   docker compose up -d cascade-api
   ```

8. **Verify recovery**
   ```bash
   curl https://forgecascade.org/api/v1/system/health
   ```

### Scenario 2: Complete Server Failure

#### Prerequisites
- Access to new server with Docker installed
- Latest backup files
- Environment configuration (.env file)
- Cloudflare tunnel token

#### Steps

1. **Provision new server**
   - Install Docker and Docker Compose
   - Clone the repository or copy project files

2. **Restore configuration**
   ```bash
   # Copy .env file with secrets
   cp /backup/location/.env .env

   # Or recreate from template
   cp .env.example .env
   # Edit with production values
   ```

3. **Restore database backup**
   ```bash
   # Set environment variables
   export $(grep -v '^#' .env | xargs)

   # Restore from backup
   python scripts/backup/neo4j_restore.py /backup/neo4j/latest.json.gz --clear-first --force
   ```

4. **Start services**
   ```bash
   docker compose up -d
   ```

5. **Verify Cloudflare tunnel connection**
   ```bash
   docker logs forge-cloudflared
   # Look for "Registered tunnel connection"
   ```

6. **Test all endpoints**
   ```bash
   # Health check
   curl https://forgecascade.org/health
   curl https://forgecascade.org/api/v1/system/health

   # Test authentication
   curl -X POST https://forgecascade.org/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test"}'
   ```

### Scenario 3: Redis Failure

#### Steps

1. **Check Redis status**
   ```bash
   docker logs forge-redis --tail 50
   docker exec forge-redis redis-cli ping
   ```

2. **If Redis is unresponsive, restart it**
   ```bash
   docker compose restart redis
   ```

3. **If data is corrupted, restore from backup**
   ```bash
   docker compose stop redis
   docker cp ./backups/redis/appendonly.aof forge-redis:/data/
   docker compose start redis
   ```

4. **Verify Redis recovery**
   ```bash
   docker exec forge-redis redis-cli -a $REDIS_PASSWORD ping
   ```

Note: Session data loss will require users to re-authenticate.

### Scenario 4: Container/Image Issues

#### Steps

1. **Rebuild containers**
   ```bash
   docker compose build --no-cache
   ```

2. **Remove and recreate containers**
   ```bash
   docker compose down
   docker compose up -d
   ```

3. **If images are corrupted, pull fresh base images**
   ```bash
   docker pull python:3.11-slim
   docker pull nginx:alpine
   docker pull redis:7-alpine
   docker compose build --no-cache
   ```

### Scenario 5: Cloudflare Tunnel Disconnection

#### Steps

1. **Check tunnel status**
   ```bash
   docker logs forge-cloudflared --tail 30
   ```

2. **Restart tunnel container**
   ```bash
   docker compose restart cloudflared
   ```

3. **If token is invalid, regenerate in Cloudflare dashboard**
   - Go to Cloudflare Zero Trust > Access > Tunnels
   - Select your tunnel
   - Generate new token
   - Update CLOUDFLARE_TOKEN in .env
   - Restart: `docker compose restart cloudflared`

---

## Monitoring & Alerts

### Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Frontend | `https://forgecascade.org/health` | `healthy` |
| API | `https://forgecascade.org/api/v1/system/health` | JSON with status |
| Marketplace | `https://forgeshop.org/health` | `healthy` |

### Log Locations

```bash
# View all logs
docker compose logs -f

# Specific service logs
docker logs forge-cascade-api -f
docker logs forge-frontend -f
docker logs forge-redis -f
```

### Container Status

```bash
# Check all container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Expected: All services should show (healthy)
```

---

## Emergency Contacts

| Role | Contact | Responsibility |
|------|---------|----------------|
| System Admin | [Add contact] | Infrastructure |
| Database Admin | [Add contact] | Neo4j issues |
| On-call Engineer | [Add contact] | 24/7 incidents |

---

## Checklist for Recovery

### Pre-Recovery

- [ ] Identify the scope of the incident
- [ ] Notify stakeholders
- [ ] Document the timeline
- [ ] Identify the most recent valid backup

### During Recovery

- [ ] Stop affected services
- [ ] Create backup of current state (if possible)
- [ ] Execute recovery procedure
- [ ] Verify data integrity
- [ ] Test critical functionality

### Post-Recovery

- [ ] Monitor for errors for 24 hours
- [ ] Document lessons learned
- [ ] Update procedures if needed
- [ ] Notify stakeholders of resolution

---

## Testing Recovery Procedures

Recovery procedures should be tested quarterly:

1. **Backup Verification**
   ```bash
   # Verify backup integrity
   python scripts/backup/neo4j_restore.py latest_backup.json.gz --dry-run
   ```

2. **Full Recovery Test** (staging environment)
   - Provision test server
   - Perform full recovery
   - Verify all functionality

3. **Document Results**
   - Recovery time achieved
   - Issues encountered
   - Updates needed

---

## Version History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-01-08 | 1.0 | Claude Code | Initial document |
