#!/bin/bash
# =============================================================================
# Forge V3 Production Deployment Script
# =============================================================================
# Usage: ./deploy.sh [command]
# Commands:
#   setup     - Initial server setup (run once)
#   ssl       - Obtain SSL certificates
#   start     - Start all services
#   stop      - Stop all services
#   restart   - Restart all services
#   update    - Pull latest images and restart
#   logs      - View logs
#   status    - Check service status
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        log_info "Copy .env.example to .env and configure it first"
        exit 1
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
}

docker_compose() {
    if docker compose version &> /dev/null 2>&1; then
        docker compose -f "$COMPOSE_FILE" "$@"
    else
        docker-compose -f "$COMPOSE_FILE" "$@"
    fi
}

# =============================================================================
# Commands
# =============================================================================

cmd_setup() {
    log_info "Setting up Forge V3 production environment..."

    # Check for .env file
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating .env file from template..."
        cp .env.example .env
        log_warn "Please edit .env with your configuration before continuing"
        exit 0
    fi

    # Create required directories
    log_info "Creating directories..."
    mkdir -p certbot/conf certbot/www
    mkdir -p nginx/conf.d

    # Use initial HTTP-only config
    log_info "Setting up initial nginx config (HTTP only)..."
    cp nginx/conf.d/forge-init.conf nginx/conf.d/default.conf

    log_info "Setup complete! Next steps:"
    echo "  1. Edit .env with your configuration"
    echo "  2. Run: ./deploy.sh start"
    echo "  3. Run: ./deploy.sh ssl"
}

cmd_ssl() {
    check_env
    source "$ENV_FILE"

    if [ -z "$DOMAIN" ]; then
        log_error "DOMAIN not set in .env file"
        exit 1
    fi

    if [ -z "$SSL_EMAIL" ]; then
        log_error "SSL_EMAIL not set in .env file"
        exit 1
    fi

    log_info "Obtaining SSL certificate for $DOMAIN..."

    # Stop nginx temporarily if running
    docker_compose stop nginx 2>/dev/null || true

    # Get certificates
    docker run --rm \
        -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
        -v "$(pwd)/certbot/www:/var/www/certbot" \
        -p 80:80 \
        certbot/certbot certonly \
        --standalone \
        --preferred-challenges http \
        --email "$SSL_EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"

    # Update nginx config with actual domain
    log_info "Updating nginx configuration with SSL..."
    sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" nginx/conf.d/forge.conf > nginx/conf.d/default.conf

    # Restart nginx
    docker_compose up -d nginx

    log_info "SSL certificate obtained and configured!"
    log_info "Your site is now available at https://$DOMAIN"
}

cmd_start() {
    check_env
    check_docker

    log_info "Starting Forge V3 services..."
    docker_compose up -d

    log_info "Waiting for services to be healthy..."
    sleep 10

    cmd_status
}

cmd_stop() {
    log_info "Stopping Forge V3 services..."
    docker_compose down
    log_info "All services stopped"
}

cmd_restart() {
    log_info "Restarting Forge V3 services..."
    docker_compose restart
    cmd_status
}

cmd_update() {
    check_env
    check_docker

    log_info "Pulling latest images..."
    docker_compose pull

    log_info "Restarting services with new images..."
    docker_compose up -d

    log_info "Cleaning up old images..."
    docker image prune -f

    cmd_status
}

cmd_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker_compose logs -f "$service"
    else
        docker_compose logs -f
    fi
}

cmd_status() {
    log_info "Service Status:"
    docker_compose ps

    echo ""
    log_info "Health Checks:"

    # Check each service
    services=("cascade-api" "frontend" "redis" "nginx")
    for svc in "${services[@]}"; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "forge-$svc" 2>/dev/null || echo "no healthcheck")
        running=$(docker inspect --format='{{.State.Running}}' "forge-$svc" 2>/dev/null || echo "false")

        if [ "$running" = "true" ]; then
            if [ "$status" = "healthy" ] || [ "$status" = "no healthcheck" ]; then
                echo -e "  ${GREEN}✓${NC} $svc: running"
            else
                echo -e "  ${YELLOW}○${NC} $svc: $status"
            fi
        else
            echo -e "  ${RED}✗${NC} $svc: stopped"
        fi
    done
}

cmd_backup() {
    log_info "Creating backup..."
    backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup Redis data
    docker_compose exec -T redis redis-cli BGSAVE
    sleep 2
    docker cp forge-redis:/data/dump.rdb "$backup_dir/redis-dump.rdb"

    # Backup environment
    cp .env "$backup_dir/.env"

    log_info "Backup created at: $backup_dir"
}

cmd_help() {
    echo "Forge V3 Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup     Initial server setup (run once)"
    echo "  ssl       Obtain SSL certificates"
    echo "  start     Start all services"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  update    Pull latest images and restart"
    echo "  logs      View logs (optionally specify service)"
    echo "  status    Check service status"
    echo "  backup    Backup Redis data and config"
    echo "  help      Show this help message"
}

# =============================================================================
# Main
# =============================================================================

case "${1:-help}" in
    setup)   cmd_setup ;;
    ssl)     cmd_ssl ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    update)  cmd_update ;;
    logs)    cmd_logs "$2" ;;
    status)  cmd_status ;;
    backup)  cmd_backup ;;
    help)    cmd_help ;;
    *)
        log_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
