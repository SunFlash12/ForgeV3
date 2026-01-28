# Forge V3 - Pitch Deck Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# SECURITY FIX: Patch all OS-level vulnerabilities
RUN apk update && apk upgrade --no-cache && rm -rf /var/cache/apk/*

# SECURITY FIX: Create non-root user
RUN addgroup -g 101 -S nginx || true && \
    adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx || true

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files into /deck/ subdirectory so root-based serving works
COPY --from=builder /app/dist /usr/share/nginx/html/deck

# Add health check endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# SECURITY FIX: Set proper ownership and permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/health || exit 1

EXPOSE 80

# SECURITY FIX: Run as non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
