# Monitoring & Alerting

## Metrics Collection

Forge uses Prometheus-compatible metrics via `forge/monitoring/metrics.py`. All metrics are exposed at `/metrics` endpoint.

## Key Metrics & Alert Thresholds

### API Health

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| HTTP error rate (5xx) | > 5% over 5min | Critical |
| HTTP error rate (4xx) | > 25% over 5min | Warning |
| Response latency p99 | > 2s | High |
| Response latency p50 | > 500ms | Warning |
| Request rate | < 1 rps (unexpected drop) | Warning |

### Authentication

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| Failed login attempts | > 50/min (global) | Critical |
| Account lockouts | > 10/hour | High |
| JWT validation failures | > 100/min | Critical |
| Token refresh failures | > 10% error rate | High |

### Database (Neo4j)

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| Connection pool utilization | > 80% | High |
| Connection pool exhausted | Any occurrence | Critical |
| Query latency p99 | > 5s | High |
| Query timeout | Any occurrence | Warning |
| Transaction failures | > 1% error rate | High |

### Cache (Redis)

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| Cache hit ratio | < 50% | Warning |
| Connection failures | Any occurrence | High |
| Memory usage | > 80% of max | Warning |
| Eviction rate | > 100/s | Warning |

### Blockchain

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| Transaction failures | Any occurrence | High |
| Transaction confirmation time | > 60s | Warning |
| RPC endpoint errors | > 3 consecutive | Critical |
| Gas price spike | > 10x baseline | Warning |
| Wallet balance low | < 0.01 ETH | Critical |

### Infrastructure

| Metric | Alert Threshold | Severity |
|--------|----------------|----------|
| Container restart count | > 3 in 10min | Critical |
| CPU utilization | > 85% sustained 5min | High |
| Memory utilization | > 90% | Critical |
| Disk usage | > 85% | High |
| WebSocket connections | > 500 concurrent | Warning |

## Dashboards

Recommended Grafana dashboards:
1. **API Overview**: Request rate, error rate, latency percentiles
2. **Authentication**: Login attempts, lockouts, token operations
3. **Database**: Query performance, connection pool, transaction rates
4. **Blockchain**: Transaction status, gas costs, wallet balances
5. **Infrastructure**: Container health, resource utilization

## Log Levels

| Level | Usage |
|-------|-------|
| ERROR | Unrecoverable failures, security incidents |
| WARNING | Degraded performance, retry-able failures |
| INFO | Normal operations, API requests, state changes |
| DEBUG | Detailed diagnostics (disabled in production) |

Structured logging via `structlog` — all log entries include `timestamp`, `level`, `event`, `request_id`.
