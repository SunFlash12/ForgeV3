# Forge V3 - Phase 8: DevOps & Deployment

**Purpose:** Production deployment with containers, orchestration, CI/CD, and monitoring.

**Estimated Effort:** 3-4 days
**Dependencies:** Phase 0-7 (all application code complete)
**Outputs:** Production-ready deployment infrastructure

---

## 1. Overview

This phase covers everything needed to run Forge in production, including containerization, Kubernetes deployment, CI/CD pipelines, and observability.

---

## 2. Docker Configuration

### 2.1 Application Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels .

# Production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r forge && useradd -r -g forge forge

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy application code
COPY forge/ ./forge/

# Switch to non-root user
USER forge

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Docker Compose for Local Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DEBUG=true
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=development
      - REDIS_URL=redis://redis:6379/0
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - JWT_SECRET=dev-secret-change-in-production
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./forge:/app/forge  # Hot reload in dev

  neo4j:
    image: neo4j:5.15-enterprise
    environment:
      NEO4J_AUTH: neo4j/development
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

volumes:
  neo4j_data:
  redis_data:
```

---

## 3. Kubernetes Deployment

### 3.1 Namespace and Config

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: forge
  labels:
    app: forge
---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: forge-config
  namespace: forge
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "INFO"
  NEO4J_DATABASE: "neo4j"
  EMBEDDING_PROVIDER: "openai"
  EMBEDDING_MODEL: "text-embedding-3-small"
```

### 3.2 Secrets (use external secret manager in production)

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: forge-secrets
  namespace: forge
type: Opaque
stringData:
  NEO4J_PASSWORD: "REPLACE_WITH_REAL_PASSWORD"
  JWT_SECRET: "REPLACE_WITH_REAL_SECRET"
  OPENAI_API_KEY: "REPLACE_WITH_REAL_KEY"
```

### 3.3 API Deployment

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: forge-api
  namespace: forge
  labels:
    app: forge
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: forge
      component: api
  template:
    metadata:
      labels:
        app: forge
        component: api
    spec:
      serviceAccountName: forge-api
      containers:
        - name: api
          image: forge/api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: forge-config
          env:
            - name: NEO4J_URI
              value: "bolt://neo4j.forge.svc.cluster.local:7687"
            - name: REDIS_URL
              value: "redis://redis.forge.svc.cluster.local:6379/0"
            - name: NEO4J_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: NEO4J_PASSWORD
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: JWT_SECRET
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: forge-secrets
                  key: OPENAI_API_KEY
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: forge-api
  namespace: forge
spec:
  selector:
    app: forge
    component: api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

### 3.4 Ingress with TLS

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: forge-ingress
  namespace: forge
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
    - hosts:
        - api.forge.example.com
      secretName: forge-tls
  rules:
    - host: api.forge.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: forge-api
                port:
                  number: 80
```

### 3.5 Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: forge-api-hpa
  namespace: forge
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: forge-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

---

## 4. CI/CD Pipeline

### 4.1 GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5.15-enterprise
        env:
          NEO4J_AUTH: neo4j/test
          NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
        ports:
          - 7687:7687
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run linting
        run: |
          ruff check .
          black --check .
          mypy forge/

      - name: Run tests
        env:
          NEO4J_URI: bolt://localhost:7687
          NEO4J_USER: neo4j
          NEO4J_PASSWORD: test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET: test-secret
        run: |
          pytest tests/ -v --cov=forge --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push'

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        uses: azure/k8s-deploy@v4
        with:
          namespace: forge-staging
          manifests: |
            k8s/api-deployment.yaml
            k8s/ingress.yaml
          images: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        uses: azure/k8s-deploy@v4
        with:
          namespace: forge
          manifests: |
            k8s/api-deployment.yaml
            k8s/ingress.yaml
          images: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

---

## 5. Monitoring & Observability

### 5.1 Prometheus ServiceMonitor

```yaml
# k8s/monitoring/servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: forge-api
  namespace: forge
spec:
  selector:
    matchLabels:
      app: forge
      component: api
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### 5.2 Grafana Dashboard ConfigMap

```yaml
# k8s/monitoring/dashboard.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: forge-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "true"
data:
  forge-dashboard.json: |
    {
      "dashboard": {
        "title": "Forge Operations",
        "panels": [
          {
            "title": "Request Rate",
            "type": "graph",
            "targets": [
              {
                "expr": "sum(rate(http_requests_total{service=\"forge-api\"}[5m]))",
                "legendFormat": "Requests/s"
              }
            ]
          },
          {
            "title": "Latency P95",
            "type": "graph",
            "targets": [
              {
                "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service=\"forge-api\"}[5m])) by (le))",
                "legendFormat": "P95 Latency"
              }
            ]
          },
          {
            "title": "Error Rate",
            "type": "singlestat",
            "targets": [
              {
                "expr": "sum(rate(http_requests_total{service=\"forge-api\",status=~\"5..\"}[5m])) / sum(rate(http_requests_total{service=\"forge-api\"}[5m])) * 100",
                "legendFormat": "Error %"
              }
            ]
          }
        ]
      }
    }
```

### 5.3 Alert Rules

```yaml
# k8s/monitoring/alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: forge-alerts
  namespace: forge
spec:
  groups:
    - name: forge
      rules:
        - alert: HighErrorRate
          expr: |
            sum(rate(http_requests_total{service="forge-api",status=~"5.."}[5m])) 
            / sum(rate(http_requests_total{service="forge-api"}[5m])) > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "High error rate detected"
            description: "Error rate is above 5% for 5 minutes"

        - alert: HighLatency
          expr: |
            histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{service="forge-api"}[5m])) by (le)) > 2
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High API latency"
            description: "P95 latency is above 2 seconds"

        - alert: PodNotReady
          expr: |
            kube_pod_status_ready{namespace="forge",condition="true"} == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Pod not ready"
            description: "Pod {{ $labels.pod }} has been not ready for 5 minutes"
```

---

## 6. Production Checklist

Before going to production, verify these items:

**Security:**
- All secrets in external secret manager (not K8s secrets)
- TLS certificates configured and auto-renewed
- Network policies restricting pod-to-pod traffic
- RBAC configured with least privilege
- Security scanning in CI pipeline

**Performance:**
- Load testing completed (target: 1000 RPS)
- Database indexes verified
- Connection pooling configured
- CDN for static assets

**Reliability:**
- Multi-AZ deployment
- Database backups automated and tested
- Disaster recovery plan documented
- Runbooks for common incidents

**Observability:**
- Metrics, logs, and traces connected
- Alerts configured for SLOs
- On-call rotation established
- Dashboards for key metrics

**Compliance:**
- Audit logging enabled
- GDPR data flows documented
- Data retention policies configured
- Penetration test completed

---

## 7. Summary

You now have all 8 phases to build Forge V3:

| Phase | Focus | Effort |
|-------|-------|--------|
| 0 | Foundations & Shared | 1-2 days |
| 1 | Data Layer (Neo4j) | 3-4 days |
| 2 | Knowledge Engine | 3-4 days |
| 3 | Overlay Runtime | 4-5 days |
| 4 | Governance System | 4-5 days |
| 5 | Security & Compliance | 4-5 days |
| 6 | API Layer | 3-4 days |
| 7 | User Interfaces | 5-7 days |
| 8 | DevOps & Deployment | 3-4 days |

**Total Estimated Effort: 30-40 days**

Each phase is self-contained and can be given to an AI coding assistant independently. Start with Phase 0, then work through phases sequentially as each builds on the previous.
