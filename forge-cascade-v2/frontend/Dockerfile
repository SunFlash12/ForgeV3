# Forge V3 - Frontend Dockerfile
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

# Build arguments for environment variables
ARG VITE_API_URL=http://localhost:8001/api/v1
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_SENTRY_DSN=
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

# Build for production
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# SECURITY FIX (Audit 3): Create non-root user
RUN addgroup -g 101 -S nginx || true && \
    adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx || true

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Add health check endpoint
RUN echo "healthy" > /usr/share/nginx/html/health

# SECURITY FIX (Audit 3): Set proper ownership and permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:80/health || exit 1

EXPOSE 80

# SECURITY FIX (Audit 3): Run as non-root user
USER nginx

CMD ["nginx", "-g", "daemon off;"]
