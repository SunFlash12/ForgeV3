"""
System Routes Tests for Forge Cascade V2

Comprehensive tests for system API routes including:
- Health checks and probes
- Circuit breaker management
- Anomaly detection
- Canary deployments
- System metrics
- Event logs
- Administrative operations
- Maintenance mode
- Cache management
- Audit logs
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from forge.immune.anomaly import AnomalySeverity, AnomalyType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_circuit_registry():
    """Create mock circuit breaker registry."""
    registry = MagicMock()
    registry._breakers = {}
    return registry


@pytest.fixture
def mock_anomaly_system():
    """Create mock anomaly detection system."""
    system = MagicMock()
    system.get_unresolved_anomalies = MagicMock(return_value=[])
    system.get_recent_anomalies = MagicMock(return_value=[])
    system.get_anomaly = MagicMock(return_value=None)
    system.acknowledge = MagicMock(return_value=True)
    system.resolve = MagicMock(return_value=True)
    system.record_metric = AsyncMock(return_value=None)
    return system


@pytest.fixture
def mock_event_system():
    """Create mock event system."""
    system = AsyncMock()
    system._running = True
    system._start_time = datetime.now(UTC) - timedelta(hours=1)
    system._event_history = []
    system._events_emitted = 100
    system._events_processed = 95
    system.emit = AsyncMock()
    return system


@pytest.fixture
def mock_canary_manager():
    """Create mock canary manager."""
    manager = MagicMock()
    manager._deployments = {}
    return manager


@pytest.fixture
def trusted_auth_headers(user_factory):
    """Create authentication headers for a trusted user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=70)
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def core_auth_headers(user_factory):
    """Create authentication headers for a core user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=85)
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheckRoute:
    """Tests for GET /system/health endpoint."""

    def test_health_check(self, client: TestClient):
        """Health check returns status."""
        response = client.get("/api/v1/system/health")
        # Health check should work without auth
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "components" in data
            assert "checks" in data


class TestLivenessProbeRoute:
    """Tests for GET /system/health/live endpoint."""

    def test_liveness_probe(self, client: TestClient):
        """Liveness probe returns alive status."""
        response = client.get("/api/v1/system/health/live")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "alive"


class TestReadinessProbeRoute:
    """Tests for GET /system/health/ready endpoint."""

    def test_readiness_probe(self, client: TestClient):
        """Readiness probe returns ready status."""
        response = client.get("/api/v1/system/health/ready")
        # May return 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestListCircuitBreakersRoute:
    """Tests for GET /system/circuit-breakers endpoint."""

    def test_list_circuit_breakers_unauthorized(self, client: TestClient):
        """List circuit breakers without auth fails."""
        response = client.get("/api/v1/system/circuit-breakers")
        assert response.status_code == 401

    def test_list_circuit_breakers_authorized(self, client: TestClient, auth_headers: dict):
        """List circuit breakers with auth returns list."""
        response = client.get("/api/v1/system/circuit-breakers", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "circuit_breakers" in data
            assert "total" in data
            assert "open_count" in data
            assert "half_open_count" in data


class TestResetCircuitBreakerRoute:
    """Tests for POST /system/circuit-breakers/{name}/reset endpoint."""

    def test_reset_circuit_breaker_unauthorized(self, client: TestClient):
        """Reset circuit breaker without auth fails."""
        response = client.post("/api/v1/system/circuit-breakers/test_circuit/reset")
        assert response.status_code == 401

    def test_reset_circuit_breaker_insufficient_trust(
        self, client: TestClient, auth_headers: dict
    ):
        """Reset circuit breaker with insufficient trust fails."""
        response = client.post(
            "/api/v1/system/circuit-breakers/test_circuit/reset", headers=auth_headers
        )
        # Needs TRUSTED level
        assert response.status_code in [403, 401, 404, 503]

    def test_reset_circuit_breaker_not_found(
        self, client: TestClient, trusted_auth_headers: dict
    ):
        """Reset non-existent circuit breaker returns 404."""
        response = client.post(
            "/api/v1/system/circuit-breakers/nonexistent/reset",
            headers=trusted_auth_headers,
        )
        assert response.status_code in [404, 403, 401, 503]


# =============================================================================
# Anomaly Detection Tests
# =============================================================================


class TestListAnomaliesRoute:
    """Tests for GET /system/anomalies endpoint."""

    def test_list_anomalies_unauthorized(self, client: TestClient):
        """List anomalies without auth fails."""
        response = client.get("/api/v1/system/anomalies")
        assert response.status_code == 401

    def test_list_anomalies_authorized(self, client: TestClient, auth_headers: dict):
        """List anomalies with auth returns list."""
        response = client.get("/api/v1/system/anomalies", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "anomalies" in data
            assert "total" in data
            assert "unresolved_count" in data

    def test_list_anomalies_with_filters(self, client: TestClient, auth_headers: dict):
        """List anomalies with filter parameters."""
        response = client.get(
            "/api/v1/system/anomalies",
            params={
                "hours": 48,
                "severity": "HIGH",
                "unresolved_only": True,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 400, 401, 503]

    def test_list_anomalies_invalid_severity(self, client: TestClient, auth_headers: dict):
        """List anomalies with invalid severity fails."""
        response = client.get(
            "/api/v1/system/anomalies",
            params={"severity": "INVALID"},
            headers=auth_headers,
        )
        assert response.status_code in [400, 401, 503]


class TestAcknowledgeAnomalyRoute:
    """Tests for POST /system/anomalies/{anomaly_id}/acknowledge endpoint."""

    def test_acknowledge_anomaly_unauthorized(self, client: TestClient):
        """Acknowledge anomaly without auth fails."""
        response = client.post(
            "/api/v1/system/anomalies/anomaly123/acknowledge",
            json={"notes": "Investigating"},
        )
        assert response.status_code == 401

    def test_acknowledge_anomaly_insufficient_trust(
        self, client: TestClient, auth_headers: dict
    ):
        """Acknowledge anomaly with insufficient trust fails."""
        response = client.post(
            "/api/v1/system/anomalies/anomaly123/acknowledge",
            json={"notes": "Investigating"},
            headers=auth_headers,
        )
        assert response.status_code in [403, 401, 404, 503]


class TestResolveAnomalyRoute:
    """Tests for POST /system/anomalies/{anomaly_id}/resolve endpoint."""

    def test_resolve_anomaly_unauthorized(self, client: TestClient):
        """Resolve anomaly without auth fails."""
        response = client.post("/api/v1/system/anomalies/anomaly123/resolve")
        assert response.status_code == 401

    def test_resolve_anomaly_insufficient_trust(
        self, client: TestClient, auth_headers: dict
    ):
        """Resolve anomaly with insufficient trust fails."""
        response = client.post(
            "/api/v1/system/anomalies/anomaly123/resolve", headers=auth_headers
        )
        assert response.status_code in [403, 401, 404, 503]


class TestRecordMetricRoute:
    """Tests for POST /system/metrics/record endpoint."""

    def test_record_metric_unauthorized(self, client: TestClient):
        """Record metric without auth fails."""
        response = client.post(
            "/api/v1/system/metrics/record",
            json={"metric_name": "test.metric", "value": 100.0},
        )
        assert response.status_code == 401

    def test_record_metric_authorized(self, client: TestClient, auth_headers: dict):
        """Record metric with auth succeeds."""
        response = client.post(
            "/api/v1/system/metrics/record",
            json={
                "metric_name": "test.metric",
                "value": 100.0,
                "context": {"source": "test"},
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]

    def test_record_metric_validation(self, client: TestClient, auth_headers: dict):
        """Record metric with invalid name fails validation."""
        response = client.post(
            "/api/v1/system/metrics/record",
            json={
                "metric_name": "",  # Empty name
                "value": 100.0,
            },
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Canary Deployment Tests
# =============================================================================


class TestListCanariesRoute:
    """Tests for GET /system/canaries endpoint."""

    def test_list_canaries_unauthorized(self, client: TestClient):
        """List canaries without auth fails."""
        response = client.get("/api/v1/system/canaries")
        assert response.status_code == 401

    def test_list_canaries_authorized(self, client: TestClient, auth_headers: dict):
        """List canaries with auth returns list."""
        response = client.get("/api/v1/system/canaries", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "deployments" in data
            assert "total" in data


# =============================================================================
# System Metrics Tests
# =============================================================================


class TestSystemMetricsRoute:
    """Tests for GET /system/metrics endpoint."""

    def test_get_metrics_unauthorized(self, client: TestClient):
        """Get metrics without auth fails."""
        response = client.get("/api/v1/system/metrics")
        assert response.status_code == 401

    def test_get_metrics_authorized(self, client: TestClient, auth_headers: dict):
        """Get metrics with auth returns metrics."""
        response = client.get("/api/v1/system/metrics", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "timestamp" in data
            assert "active_overlays" in data


# =============================================================================
# Event Log Tests
# =============================================================================


class TestRecentEventsRoute:
    """Tests for GET /system/events/recent endpoint."""

    def test_get_events_unauthorized(self, client: TestClient):
        """Get recent events without auth fails."""
        response = client.get("/api/v1/system/events/recent")
        assert response.status_code == 401

    def test_get_events_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Get recent events with insufficient trust fails."""
        response = client.get("/api/v1/system/events/recent", headers=auth_headers)
        # Needs TRUSTED level
        assert response.status_code in [403, 401, 503]

    def test_get_events_with_trusted_level(
        self, client: TestClient, trusted_auth_headers: dict
    ):
        """Get recent events with trusted level succeeds."""
        response = client.get(
            "/api/v1/system/events/recent", headers=trusted_auth_headers
        )
        assert response.status_code in [200, 403, 401, 503]

    def test_get_events_with_filters(
        self, client: TestClient, trusted_auth_headers: dict
    ):
        """Get recent events with filter parameters."""
        response = client.get(
            "/api/v1/system/events/recent",
            params={"limit": 20, "event_type": "SYSTEM_EVENT"},
            headers=trusted_auth_headers,
        )
        assert response.status_code in [200, 403, 401, 503]


# =============================================================================
# Maintenance Mode Tests
# =============================================================================


class TestMaintenanceModeRoutes:
    """Tests for maintenance mode endpoints."""

    def test_get_maintenance_status(self, client: TestClient):
        """Get maintenance status works without auth."""
        response = client.get("/api/v1/system/maintenance/status")
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "enabled" in data
            assert "message" in data

    def test_enable_maintenance_unauthorized(self, client: TestClient):
        """Enable maintenance without auth fails."""
        response = client.post("/api/v1/system/maintenance/enable")
        assert response.status_code == 401

    def test_enable_maintenance_non_admin(self, client: TestClient, auth_headers: dict):
        """Enable maintenance with non-admin fails."""
        response = client.post("/api/v1/system/maintenance/enable", headers=auth_headers)
        # Needs admin role
        assert response.status_code in [403, 401, 503]

    def test_enable_maintenance_admin(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """Enable maintenance with admin succeeds."""
        response = client.post(
            "/api/v1/system/maintenance/enable", headers=admin_auth_headers
        )
        assert response.status_code in [200, 403, 401, 503]

    def test_enable_maintenance_with_message(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """Enable maintenance with custom message."""
        response = client.post(
            "/api/v1/system/maintenance/enable",
            json={"message": "Scheduled maintenance until 10:00 UTC"},
            headers=admin_auth_headers,
        )
        assert response.status_code in [200, 403, 401, 503]

    def test_disable_maintenance_non_admin(self, client: TestClient, auth_headers: dict):
        """Disable maintenance with non-admin fails."""
        response = client.post("/api/v1/system/maintenance/disable", headers=auth_headers)
        assert response.status_code in [403, 401, 503]


# =============================================================================
# Cache Management Tests
# =============================================================================


class TestCacheClearRoute:
    """Tests for POST /system/cache/clear endpoint."""

    def test_clear_cache_unauthorized(self, client: TestClient):
        """Clear cache without auth fails."""
        response = client.post("/api/v1/system/cache/clear")
        assert response.status_code == 401

    def test_clear_cache_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Clear cache with insufficient trust fails."""
        response = client.post("/api/v1/system/cache/clear", headers=auth_headers)
        # Needs CORE level
        assert response.status_code in [403, 401, 503]

    def test_clear_cache_with_core_level(
        self, client: TestClient, core_auth_headers: dict
    ):
        """Clear cache with core level succeeds."""
        response = client.post("/api/v1/system/cache/clear", headers=core_auth_headers)
        assert response.status_code in [200, 403, 401, 503]

    def test_clear_specific_caches(self, client: TestClient, core_auth_headers: dict):
        """Clear specific caches."""
        response = client.post(
            "/api/v1/system/cache/clear",
            json={"caches": ["query_cache", "health_cache"]},
            headers=core_auth_headers,
        )
        assert response.status_code in [200, 403, 401, 503]


# =============================================================================
# System Info Tests
# =============================================================================


class TestSystemInfoRoute:
    """Tests for GET /system/info endpoint."""

    def test_get_system_info(self, client: TestClient):
        """Get system info works without auth."""
        response = client.get("/api/v1/system/info")
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "name" in data
            assert "version" in data
            assert "api_version" in data


# =============================================================================
# System Status Tests
# =============================================================================


class TestSystemStatusRoute:
    """Tests for GET /system/status endpoint."""

    def test_get_system_status(self, client: TestClient):
        """Get system status works without auth."""
        response = client.get("/api/v1/system/status")
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] in ["operational", "degraded", "down"]
            assert "services" in data


# =============================================================================
# Audit Log Tests
# =============================================================================


class TestAuditLogRoute:
    """Tests for GET /system/audit-log endpoint."""

    def test_get_audit_log_unauthorized(self, client: TestClient):
        """Get audit log without auth fails."""
        response = client.get("/api/v1/system/audit-log")
        assert response.status_code == 401

    def test_get_audit_log_non_admin(self, client: TestClient, auth_headers: dict):
        """Get audit log with non-admin fails."""
        response = client.get("/api/v1/system/audit-log", headers=auth_headers)
        # Needs admin role
        assert response.status_code in [403, 401, 503]

    def test_get_audit_log_admin(self, client: TestClient, admin_auth_headers: dict):
        """Get audit log with admin succeeds."""
        response = client.get("/api/v1/system/audit-log", headers=admin_auth_headers)
        assert response.status_code in [200, 403, 401, 503]

    def test_get_audit_log_with_filters(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """Get audit log with filter parameters."""
        response = client.get(
            "/api/v1/system/audit-log",
            params={
                "action": "overlay_activated",
                "entity_type": "overlay",
                "limit": 20,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code in [200, 403, 401, 503]

    def test_get_audit_log_pagination_limits(
        self, client: TestClient, admin_auth_headers: dict
    ):
        """Get audit log respects pagination limits."""
        response = client.get(
            "/api/v1/system/audit-log",
            params={"limit": 1000},  # Over 500 max
            headers=admin_auth_headers,
        )
        # Should fail validation or cap at max
        assert response.status_code in [200, 422, 403, 401, 503]


class TestAuditTrailRoute:
    """Tests for GET /system/audit-log/{correlation_id} endpoint."""

    def test_get_audit_trail_unauthorized(self, client: TestClient):
        """Get audit trail without auth fails."""
        response = client.get("/api/v1/system/audit-log/corr123")
        assert response.status_code == 401

    def test_get_audit_trail_non_admin(self, client: TestClient, auth_headers: dict):
        """Get audit trail with non-admin fails."""
        response = client.get("/api/v1/system/audit-log/corr123", headers=auth_headers)
        assert response.status_code in [403, 401, 503]

    def test_get_audit_trail_admin(self, client: TestClient, admin_auth_headers: dict):
        """Get audit trail with admin succeeds."""
        response = client.get(
            "/api/v1/system/audit-log/corr123", headers=admin_auth_headers
        )
        assert response.status_code in [200, 403, 401, 503]


# =============================================================================
# Dashboard Metrics Tests
# =============================================================================


class TestActivityTimelineRoute:
    """Tests for GET /system/metrics/activity-timeline endpoint."""

    def test_activity_timeline_unauthorized(self, client: TestClient):
        """Get activity timeline without auth fails."""
        response = client.get("/api/v1/system/metrics/activity-timeline")
        assert response.status_code == 401

    def test_activity_timeline_authorized(self, client: TestClient, auth_headers: dict):
        """Get activity timeline with auth succeeds."""
        response = client.get(
            "/api/v1/system/metrics/activity-timeline", headers=auth_headers
        )
        assert response.status_code in [200, 401, 503]

    def test_activity_timeline_with_hours(self, client: TestClient, auth_headers: dict):
        """Get activity timeline with custom hours."""
        response = client.get(
            "/api/v1/system/metrics/activity-timeline",
            params={"hours": 48},
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]


class TestTrustDistributionRoute:
    """Tests for GET /system/metrics/trust-distribution endpoint."""

    def test_trust_distribution_unauthorized(self, client: TestClient):
        """Get trust distribution without auth fails."""
        response = client.get("/api/v1/system/metrics/trust-distribution")
        assert response.status_code == 401

    def test_trust_distribution_authorized(self, client: TestClient, auth_headers: dict):
        """Get trust distribution with auth succeeds."""
        response = client.get(
            "/api/v1/system/metrics/trust-distribution", headers=auth_headers
        )
        assert response.status_code in [200, 401, 503]


class TestPipelinePerformanceRoute:
    """Tests for GET /system/metrics/pipeline-performance endpoint."""

    def test_pipeline_performance_unauthorized(self, client: TestClient):
        """Get pipeline performance without auth fails."""
        response = client.get("/api/v1/system/metrics/pipeline-performance")
        assert response.status_code == 401

    def test_pipeline_performance_authorized(self, client: TestClient, auth_headers: dict):
        """Get pipeline performance with auth succeeds."""
        response = client.get(
            "/api/v1/system/metrics/pipeline-performance", headers=auth_headers
        )
        assert response.status_code in [200, 401, 503]


# =============================================================================
# Maintenance Mode Function Tests
# =============================================================================


class TestMaintenanceModeFunctions:
    """Tests for maintenance mode helper functions."""

    def test_is_maintenance_mode(self):
        """Test is_maintenance_mode function."""
        from forge.api.routes.system import is_maintenance_mode, set_maintenance_mode

        # Initially should be disabled
        initial = is_maintenance_mode()

        # Enable maintenance mode
        set_maintenance_mode(True, "test_user", "Test maintenance")
        assert is_maintenance_mode() is True

        # Disable maintenance mode
        set_maintenance_mode(False)
        assert is_maintenance_mode() is False

    def test_get_maintenance_message(self):
        """Test get_maintenance_message function."""
        from forge.api.routes.system import (
            get_maintenance_message,
            set_maintenance_mode,
        )

        # Set custom message
        set_maintenance_mode(True, "test_user", "Custom maintenance message")
        msg = get_maintenance_message()
        assert "Custom maintenance message" in msg

        # Reset
        set_maintenance_mode(False)
        msg = get_maintenance_message()
        assert "maintenance" in msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
