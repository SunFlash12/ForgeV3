# Forge V3 Production Deployment

This guide covers deploying Forge V3 to a VPS with Docker, Nginx, and SSL.

## Prerequisites

- A VPS with Ubuntu 22.04+ (4GB RAM minimum)
- A domain name pointed to your server's IP
- Neo4j Aura account (recommended) or self-hosted Neo4j

## Quick Start

### 1. Server Setup

SSH into your server and install Docker:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Logout and login again for group changes
exit
```

### 2. Deploy Forge V3

```bash
# Create deployment directory
mkdir -p /opt/forge && cd /opt/forge

# Download deployment files (or copy from your machine)
# Option A: Clone from GitHub
git clone https://github.com/SunFlash12/ForgeV3.git .
cd deploy

# Option B: Copy files directly via SCP
# scp -r deploy/* user@your-server:/opt/forge/
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

**Required Configuration:**

| Variable | Description | Example |
|----------|-------------|---------|
| `DOMAIN` | Your domain name | `forge.example.com` |
| `SSL_EMAIL` | Email for Let's Encrypt | `admin@example.com` |
| `NEO4J_URI` | Neo4j connection string | `neo4j+s://xxx.databases.neo4j.io` |
| `NEO4J_USERNAME` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `your-password` |
| `JWT_SECRET_KEY` | JWT signing key (32+ chars) | Generate with `openssl rand -hex 32` |

### 4. Initial Setup

```bash
# Make deploy script executable
chmod +x deploy.sh

# Run initial setup
./deploy.sh setup

# Start services (HTTP only initially)
./deploy.sh start

# Verify services are running
./deploy.sh status
```

### 5. Enable SSL

```bash
# Obtain SSL certificate
./deploy.sh ssl

# Verify HTTPS is working
curl -I https://your-domain.com
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `./deploy.sh setup` | Initial server setup |
| `./deploy.sh start` | Start all services |
| `./deploy.sh stop` | Stop all services |
| `./deploy.sh restart` | Restart all services |
| `./deploy.sh update` | Pull latest images and restart |
| `./deploy.sh logs` | View all logs |
| `./deploy.sh logs cascade-api` | View specific service logs |
| `./deploy.sh status` | Check service health |
| `./deploy.sh ssl` | Obtain/renew SSL certificate |
| `./deploy.sh backup` | Backup Redis data |

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │              VPS Server                  │
                    │                                          │
    Internet ──────►│  ┌──────────────────────────────────┐   │
                    │  │      Nginx (SSL + Reverse Proxy)  │   │
                    │  │           Port 80, 443            │   │
                    │  └──────────────────────────────────┘   │
                    │              │           │               │
                    │      ┌───────┘           └───────┐       │
                    │      ▼                           ▼       │
                    │  ┌──────────┐             ┌──────────┐   │
                    │  │ Frontend │             │ Cascade  │   │
                    │  │  (React) │             │   API    │   │
                    │  │ Port 80  │             │ Port 8001│   │
                    │  └──────────┘             └──────────┘   │
                    │                                  │       │
                    │                                  ▼       │
                    │                           ┌──────────┐   │
                    │                           │  Redis   │   │
                    │                           │Port 6379 │   │
                    │                           └──────────┘   │
                    └─────────────────────────────────────────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │  Neo4j Aura    │
                              │ (Cloud Database)│
                              └────────────────┘
```

## Neo4j Aura Setup

1. Go to [Neo4j Aura](https://neo4j.com/cloud/aura/)
2. Create a free instance
3. Copy the connection URI, username, and password
4. Add to your `.env` file

## Firewall Configuration

```bash
# Allow SSH, HTTP, and HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Monitoring

### View Logs
```bash
# All services
./deploy.sh logs

# Specific service
./deploy.sh logs cascade-api
./deploy.sh logs nginx
```

### Check Health
```bash
# Service status
./deploy.sh status

# API health check
curl https://your-domain.com/health
```

## Updating

To update to a new version:

```bash
# Pull latest images and restart
./deploy.sh update
```

Or update to a specific version by editing `docker-compose.prod.yml`:

```yaml
cascade-api:
  image: ghcr.io/sunflash12/forgev3/cascade-api:1.0.2  # Change version
```

Then run:
```bash
./deploy.sh update
```

## Backup & Recovery

### Create Backup
```bash
./deploy.sh backup
```

### Restore from Backup
```bash
# Stop services
./deploy.sh stop

# Restore Redis data
docker cp backups/TIMESTAMP/redis-dump.rdb forge-redis:/data/dump.rdb

# Start services
./deploy.sh start
```

## Troubleshooting

### Services not starting
```bash
# Check logs for errors
./deploy.sh logs

# Check Docker status
docker ps -a
```

### SSL certificate issues
```bash
# Check certificate status
sudo certbot certificates

# Force renewal
./deploy.sh ssl
```

### Database connection issues
```bash
# Test Neo4j connection
curl -u neo4j:YOUR_PASSWORD https://YOUR_NEO4J_URI:7473
```

## Security Checklist

- [ ] Strong JWT_SECRET_KEY (32+ characters)
- [ ] Strong admin password
- [ ] Firewall configured (only ports 22, 80, 443)
- [ ] SSL certificate installed
- [ ] Neo4j password is secure
- [ ] Regular backups scheduled

## Support

- GitHub Issues: https://github.com/SunFlash12/ForgeV3/issues
- Documentation: https://github.com/SunFlash12/ForgeV3
