# =============================================================================
# FORGE MARKETPLACE - PRODUCTION DOCKERFILE
# Multi-stage build for optimized React/Vite frontend
# =============================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Build arguments for environment variables
ARG VITE_CASCADE_API_URL=https://forgecascade.org/api/v1
ARG VITE_WS_URL=wss://forgeshop.org/ws
ARG VITE_APP_NAME="Forge Shop"
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_WALLETCONNECT_PROJECT_ID=
ARG VITE_USE_TESTNET=false
ARG VITE_MARKETPLACE_CONTRACT_MAINNET=
ARG VITE_MARKETPLACE_CONTRACT_TESTNET=
ARG VITE_SENTRY_DSN=

# Set environment variables for build
ENV VITE_CASCADE_API_URL=$VITE_CASCADE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_WALLETCONNECT_PROJECT_ID=$VITE_WALLETCONNECT_PROJECT_ID
ENV VITE_USE_TESTNET=$VITE_USE_TESTNET
ENV VITE_MARKETPLACE_CONTRACT_MAINNET=$VITE_MARKETPLACE_CONTRACT_MAINNET
ENV VITE_MARKETPLACE_CONTRACT_TESTNET=$VITE_MARKETPLACE_CONTRACT_TESTNET
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# SECURITY FIX (Audit 3): Create non-root user
RUN addgroup -g 101 -S nginx || true && \
    adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx || true

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Add health check endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# SECURITY FIX (Audit 3): Set proper ownership and permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Expose port
EXPOSE 80

# Add Docker HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/health || exit 1

# SECURITY FIX (Audit 3): Run as non-root user
USER nginx

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
