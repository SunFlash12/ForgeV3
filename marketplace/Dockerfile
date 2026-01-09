# =============================================================================
# FORGE MARKETPLACE - PRODUCTION DOCKERFILE
# Multi-stage build for optimized React/Vite frontend
# =============================================================================

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Build arguments for environment variables
ARG VITE_API_URL=https://forgeshop.org/api
ARG VITE_CASCADE_API_URL=https://forgecascade.org/api/v1
ARG VITE_WS_URL=wss://forgeshop.org/ws
ARG VITE_APP_NAME="Forge Shop"

# Set environment variables for build
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_CASCADE_API_URL=$VITE_CASCADE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_APP_NAME=$VITE_APP_NAME

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

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

# SECURITY FIX (Audit 3): Run as non-root user
USER nginx

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
