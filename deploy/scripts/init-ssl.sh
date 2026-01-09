#!/bin/bash
# =============================================================================
# FORGE CASCADE - SSL CERTIFICATE INITIALIZATION
# Sets up Let's Encrypt certificates for forgecascade.org and forgeshop.org
# =============================================================================

set -e

# Configuration
DOMAINS=(forgecascade.org www.forgecascade.org forgeshop.org www.forgeshop.org)
EMAIL="${SSL_EMAIL:-admin@forgecascade.org}"
STAGING="${SSL_STAGING:-0}"  # Set to 1 for testing
DATA_PATH="./deploy/certbot"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}FORGE CASCADE - SSL Certificate Setup${NC}"
echo -e "${GREEN}==============================================================================${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Create directories
echo -e "${YELLOW}Creating certificate directories...${NC}"
mkdir -p "$DATA_PATH/conf"
mkdir -p "$DATA_PATH/www"

# Check for existing certificates
if [ -d "$DATA_PATH/conf/live/forgecascade.org" ]; then
    echo -e "${YELLOW}Existing certificates found. Do you want to replace them? (y/N)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

# Download recommended TLS parameters
if [ ! -e "$DATA_PATH/conf/options-ssl-nginx.conf" ]; then
    echo -e "${YELLOW}Downloading recommended TLS parameters...${NC}"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$DATA_PATH/conf/options-ssl-nginx.conf"
fi

if [ ! -e "$DATA_PATH/conf/ssl-dhparams.pem" ]; then
    echo -e "${YELLOW}Downloading DH parameters...${NC}"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$DATA_PATH/conf/ssl-dhparams.pem"
fi

# Create dummy certificates for initial nginx startup
echo -e "${YELLOW}Creating dummy certificates...${NC}"

for domain in forgecascade.org forgeshop.org; do
    path="$DATA_PATH/conf/live/$domain"
    mkdir -p "$path"

    # Generate self-signed certificate
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$path/privkey.pem" \
        -out "$path/fullchain.pem" \
        -subj "/CN=$domain" 2>/dev/null

    # Create chain.pem (copy of fullchain for OCSP stapling)
    cp "$path/fullchain.pem" "$path/chain.pem"

    echo "  Created dummy certificate for $domain"
done

# Start nginx with dummy certificates
echo -e "${YELLOW}Starting nginx...${NC}"
docker compose -f docker-compose.prod.yml up -d nginx

# Wait for nginx to start
echo "Waiting for nginx to start..."
sleep 5

# Delete dummy certificates
echo -e "${YELLOW}Removing dummy certificates...${NC}"
for domain in forgecascade.org forgeshop.org; do
    rm -rf "$DATA_PATH/conf/live/$domain"
done

# Request certificates
echo -e "${YELLOW}Requesting Let's Encrypt certificates...${NC}"

# Build domain arguments
domain_args=""
for domain in "${DOMAINS[@]}"; do
    domain_args="$domain_args -d $domain"
done

# Set staging flag
staging_arg=""
if [ "$STAGING" = "1" ]; then
    staging_arg="--staging"
    echo -e "${YELLOW}Using staging environment (for testing)${NC}"
fi

# Request certificate for forgecascade.org
echo -e "${GREEN}Requesting certificate for forgecascade.org...${NC}"
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    $staging_arg \
    -d forgecascade.org \
    -d www.forgecascade.org

# Request certificate for forgeshop.org
echo -e "${GREEN}Requesting certificate for forgeshop.org...${NC}"
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    $staging_arg \
    -d forgeshop.org \
    -d www.forgeshop.org

# Reload nginx
echo -e "${YELLOW}Reloading nginx with real certificates...${NC}"
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}SSL certificates installed successfully!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo "Your sites are now available at:"
echo "  - https://forgecascade.org"
echo "  - https://forgeshop.org"
echo ""
echo "Certificates will auto-renew via the certbot container."
echo ""
