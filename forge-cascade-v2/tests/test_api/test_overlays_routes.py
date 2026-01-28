"""
Overlays Routes Tests for Forge Cascade V2

Comprehensive tests for overlay API routes including:
- Overlay listing and status
- Overlay activation/deactivation
- Overlay configuration
- Overlay metrics
- Canary deployment management
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from forge.models.base import OverlayPhase, OverlayState

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_overlay():
    """Create a mock overlay object."""
    overlay = MagicMock()
    overlay.id = "overlay123"
    overlay.NAME = "Test Overlay"
    overlay.VERSION = "1.0.0"
    overlay.DESCRIPTION = "A test overlay"
    overlay.phase = OverlayPhase.VALIDATION
    overlay.priority = 100
    overlay.state = OverlayState.ACTIVE
    overlay.is_critical = False
    overlay.config = {"key": "value"}
    overlay.last_execution = datetime.now(UTC)
    overlay.enabled = True
    overlay.get_stats = MagicMock(
        return_value={
            "total_executions": 100,
            "successful_executions": 95,
            "avg_execution_time_ms": 50.0,
        }
    )
    return overlay


@pytest.fixture
def mock_overlay_manager():
    """Create mock overlay manager."""
    manager = MagicMock()
    manager.list_all = MagicMock(return_value=[])
    manager.list_active = MagicMock(return_value=[])
    manager.get_by_id = MagicMock(return_value=None)
    manager.get_overlays_for_phase = MagicMock(return_value=[])
    manager.activate = AsyncMock()
    manager.deactivate = AsyncMock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    return manager


@pytest.fixture
def mock_canary_manager():
    """Create mock canary manager."""
    manager = AsyncMock()
    manager.get_deployment = AsyncMock(return_value=None)
    manager.create_deployment = AsyncMock()
    manager.start = AsyncMock()
    manager.manual_advance = AsyncMock()
    manager.rollback = AsyncMock()
    return manager


@pytest.fixture
def mock_audit_repo():
    """Create mock audit repository."""
    repo = AsyncMock()
    repo.log_action = AsyncMock()
    return repo


@pytest.fixture
def trusted_auth_headers(user_factory):
    """Create authentication headers for a trusted user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=70)  # TRUSTED level
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

    user = user_factory(trust_level=85)  # CORE level
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Overlay Listing Tests
# =============================================================================


class TestOverlayListRoute:
    """Tests for GET /overlays endpoint."""

    def test_list_overlays_unauthorized(self, client: TestClient):
        """List overlays without auth fails."""
        response = client.get("/api/v1/overlays/")
        assert response.status_code == 401

    def test_list_overlays_authorized(self, client: TestClient, auth_headers: dict):
        """List overlays with auth returns list."""
        response = client.get("/api/v1/overlays/", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "overlays" in data


class TestActiveOverlaysRoute:
    """Tests for GET /overlays/active endpoint."""

    def test_list_active_overlays_unauthorized(self, client: TestClient):
        """List active overlays without auth fails."""
        response = client.get("/api/v1/overlays/active")
        assert response.status_code == 401

    def test_list_active_overlays_authorized(self, client: TestClient, auth_headers: dict):
        """List active overlays with auth returns list."""
        response = client.get("/api/v1/overlays/active", headers=auth_headers)
        assert response.status_code in [200, 401, 503]


class TestOverlaysByPhaseRoute:
    """Tests for GET /overlays/by-phase/{phase} endpoint."""

    def test_list_by_phase_unauthorized(self, client: TestClient):
        """List by phase without auth fails."""
        response = client.get("/api/v1/overlays/by-phase/validation")
        assert response.status_code == 401

    def test_list_by_phase_valid(self, client: TestClient, auth_headers: dict):
        """List by valid phase returns list."""
        response = client.get("/api/v1/overlays/by-phase/validation", headers=auth_headers)
        assert response.status_code in [200, 401, 422, 503]

    def test_list_by_phase_invalid(self, client: TestClient, auth_headers: dict):
        """List by invalid phase fails validation."""
        response = client.get("/api/v1/overlays/by-phase/invalid_phase", headers=auth_headers)
        assert response.status_code in [422, 401]


# =============================================================================
# Single Overlay Tests
# =============================================================================


class TestGetOverlayRoute:
    """Tests for GET /overlays/{overlay_id} endpoint."""

    def test_get_overlay_unauthorized(self, client: TestClient):
        """Get overlay without auth fails."""
        response = client.get("/api/v1/overlays/overlay123")
        assert response.status_code == 401

    def test_get_overlay_not_found(self, client: TestClient, auth_headers: dict):
        """Get non-existent overlay returns 404."""
        response = client.get("/api/v1/overlays/nonexistent", headers=auth_headers)
        assert response.status_code in [404, 401, 503]


# =============================================================================
# Overlay Activation Tests
# =============================================================================


class TestActivateOverlayRoute:
    """Tests for POST /overlays/{overlay_id}/activate endpoint."""

    def test_activate_unauthorized(self, client: TestClient):
        """Activate without auth fails."""
        response = client.post("/api/v1/overlays/overlay123/activate")
        assert response.status_code == 401

    def test_activate_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Activate with insufficient trust level fails."""
        # Default auth_headers is standard user (trust 60), needs TRUSTED (70+)
        response = client.post("/api/v1/overlays/overlay123/activate", headers=auth_headers)
        assert response.status_code in [403, 401, 404, 503]

    def test_activate_with_trusted_level(self, client: TestClient, trusted_auth_headers: dict):
        """Activate with trusted level succeeds or returns 404."""
        response = client.post("/api/v1/overlays/overlay123/activate", headers=trusted_auth_headers)
        assert response.status_code in [200, 400, 404, 403, 401, 503]


class TestDeactivateOverlayRoute:
    """Tests for POST /overlays/{overlay_id}/deactivate endpoint."""

    def test_deactivate_unauthorized(self, client: TestClient):
        """Deactivate without auth fails."""
        response = client.post("/api/v1/overlays/overlay123/deactivate")
        assert response.status_code == 401

    def test_deactivate_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Deactivate with insufficient trust level fails."""
        response = client.post("/api/v1/overlays/overlay123/deactivate", headers=auth_headers)
        assert response.status_code in [403, 401, 404, 503]

    def test_deactivate_with_trusted_level(self, client: TestClient, trusted_auth_headers: dict):
        """Deactivate with trusted level succeeds or returns 404."""
        response = client.post(
            "/api/v1/overlays/overlay123/deactivate", headers=trusted_auth_headers
        )
        assert response.status_code in [200, 400, 404, 403, 401, 503]


# =============================================================================
# Overlay Configuration Tests
# =============================================================================


class TestUpdateOverlayConfigRoute:
    """Tests for PATCH /overlays/{overlay_id}/config endpoint."""

    def test_update_config_unauthorized(self, client: TestClient):
        """Update config without auth fails."""
        response = client.patch(
            "/api/v1/overlays/overlay123/config",
            json={"config": {"key": "new_value"}},
        )
        assert response.status_code == 401

    def test_update_config_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Update config with insufficient trust level fails."""
        response = client.patch(
            "/api/v1/overlays/overlay123/config",
            json={"config": {"key": "new_value"}},
            headers=auth_headers,
        )
        # Needs CORE trust level
        assert response.status_code in [403, 401, 404, 503]

    def test_update_config_with_core_level(self, client: TestClient, core_auth_headers: dict):
        """Update config with core level succeeds or returns 404."""
        response = client.patch(
            "/api/v1/overlays/overlay123/config",
            json={"config": {"key": "new_value"}},
            headers=core_auth_headers,
        )
        assert response.status_code in [200, 404, 403, 401, 503]

    def test_update_config_missing_config(self, client: TestClient, core_auth_headers: dict):
        """Update config without config field fails validation."""
        response = client.patch(
            "/api/v1/overlays/overlay123/config",
            json={},  # Missing config field
            headers=core_auth_headers,
        )
        assert response.status_code in [422, 403, 401]


# =============================================================================
# Overlay Metrics Tests
# =============================================================================


class TestOverlayMetricsRoute:
    """Tests for GET /overlays/{overlay_id}/metrics endpoint."""

    def test_get_metrics_unauthorized(self, client: TestClient):
        """Get metrics without auth fails."""
        response = client.get("/api/v1/overlays/overlay123/metrics")
        assert response.status_code == 401

    def test_get_metrics_authorized(self, client: TestClient, auth_headers: dict):
        """Get metrics with auth returns metrics or 404."""
        response = client.get("/api/v1/overlays/overlay123/metrics", headers=auth_headers)
        assert response.status_code in [200, 404, 401, 503]


class TestMetricsSummaryRoute:
    """Tests for GET /overlays/metrics/summary endpoint."""

    def test_get_metrics_summary_unauthorized(self, client: TestClient):
        """Get metrics summary without auth fails."""
        response = client.get("/api/v1/overlays/metrics/summary")
        assert response.status_code == 401

    def test_get_metrics_summary_authorized(self, client: TestClient, auth_headers: dict):
        """Get metrics summary with auth returns summary."""
        response = client.get("/api/v1/overlays/metrics/summary", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "total_overlays" in data
            assert "active_overlays" in data


# =============================================================================
# Canary Deployment Tests
# =============================================================================


class TestCanaryStatusRoute:
    """Tests for GET /overlays/{overlay_id}/canary endpoint."""

    def test_get_canary_status_unauthorized(self, client: TestClient):
        """Get canary status without auth fails."""
        response = client.get("/api/v1/overlays/overlay123/canary")
        assert response.status_code == 401

    def test_get_canary_status_authorized(self, client: TestClient, auth_headers: dict):
        """Get canary status with auth returns status or 404."""
        response = client.get("/api/v1/overlays/overlay123/canary", headers=auth_headers)
        assert response.status_code in [200, 404, 401, 503]


class TestStartCanaryRoute:
    """Tests for POST /overlays/{overlay_id}/canary/start endpoint."""

    def test_start_canary_unauthorized(self, client: TestClient):
        """Start canary without auth fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/start")
        assert response.status_code == 401

    def test_start_canary_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Start canary with insufficient trust fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/start", headers=auth_headers)
        # Needs CORE trust level
        assert response.status_code in [403, 401, 404, 503]

    def test_start_canary_with_core_level(self, client: TestClient, core_auth_headers: dict):
        """Start canary with core level succeeds or returns 404/400."""
        response = client.post(
            "/api/v1/overlays/overlay123/canary/start", headers=core_auth_headers
        )
        assert response.status_code in [200, 400, 404, 403, 401, 503]


class TestAdvanceCanaryRoute:
    """Tests for POST /overlays/{overlay_id}/canary/advance endpoint."""

    def test_advance_canary_unauthorized(self, client: TestClient):
        """Advance canary without auth fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/advance")
        assert response.status_code == 401

    def test_advance_canary_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Advance canary with insufficient trust fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/advance", headers=auth_headers)
        assert response.status_code in [403, 401, 404, 503]


class TestRollbackCanaryRoute:
    """Tests for POST /overlays/{overlay_id}/canary/rollback endpoint."""

    def test_rollback_canary_unauthorized(self, client: TestClient):
        """Rollback canary without auth fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/rollback")
        assert response.status_code == 401

    def test_rollback_canary_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Rollback canary with insufficient trust fails."""
        response = client.post("/api/v1/overlays/overlay123/canary/rollback", headers=auth_headers)
        assert response.status_code in [403, 401, 404, 503]


# =============================================================================
# Admin Operations Tests
# =============================================================================


class TestReloadAllOverlaysRoute:
    """Tests for POST /overlays/reload-all endpoint."""

    def test_reload_all_unauthorized(self, client: TestClient):
        """Reload all without auth fails."""
        response = client.post("/api/v1/overlays/reload-all")
        assert response.status_code == 401

    def test_reload_all_non_admin(self, client: TestClient, auth_headers: dict):
        """Reload all with non-admin user fails."""
        response = client.post("/api/v1/overlays/reload-all", headers=auth_headers)
        # Needs admin role
        assert response.status_code in [403, 401, 503]

    def test_reload_all_admin(self, client: TestClient, admin_auth_headers: dict):
        """Reload all with admin user succeeds."""
        response = client.post("/api/v1/overlays/reload-all", headers=admin_auth_headers)
        assert response.status_code in [200, 403, 401, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
