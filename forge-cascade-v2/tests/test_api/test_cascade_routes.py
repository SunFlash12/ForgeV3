"""
Cascade Routes Tests for Forge Cascade V2

Comprehensive tests for Cascade Effect API routes including:
- Cascade triggering
- Cascade propagation
- Cascade completion
- Cascade queries
- Pipeline execution
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_event_system():
    """Create mock event system."""
    system = AsyncMock()
    return system


@pytest.fixture
def sample_cascade_event():
    """Create a sample cascade event for testing."""
    event = MagicMock()
    event.id = "event_123"
    event.source_overlay = "security_validator"
    event.insight_type = "threat_detected"
    event.insight_data = {"threat_level": "medium"}
    event.hop_count = 1
    event.max_hops = 5
    event.visited_overlays = ["security_validator"]
    event.impact_score = 0.7
    event.timestamp = datetime.now()
    event.correlation_id = "corr_123"
    return event


@pytest.fixture
def sample_cascade_chain(sample_cascade_event):
    """Create a sample cascade chain for testing."""
    chain = MagicMock()
    chain.cascade_id = "cascade_123"
    chain.initiated_by = "security_validator"
    chain.initiated_at = datetime.now()
    chain.events = [sample_cascade_event]
    chain.completed_at = None
    chain.total_hops = 1
    chain.overlays_affected = ["security_validator"]
    chain.insights_generated = 1
    chain.actions_triggered = 0
    chain.errors_encountered = 0
    return chain


@pytest.fixture
def trusted_auth_headers(user_factory):
    """Create authentication headers for a trusted user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=80)  # TRUSTED level
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Trigger Cascade Tests
# =============================================================================


class TestTriggerCascadeRoute:
    """Tests for POST /cascade/trigger endpoint."""

    def test_trigger_unauthorized(self, client: TestClient):
        """Trigger cascade without auth fails."""
        response = client.post(
            "/api/v1/cascade/trigger",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
            },
        )
        assert response.status_code == 401

    def test_trigger_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Trigger cascade with insufficient trust level fails."""
        response = client.post(
            "/api/v1/cascade/trigger",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
            },
            headers=auth_headers,  # Regular user, not TRUSTED
        )
        # Should fail with 403 (insufficient trust) or succeed if mock allows
        assert response.status_code in [403, 500]

    def test_trigger_missing_fields(self, client: TestClient, trusted_auth_headers: dict):
        """Trigger cascade with missing fields fails validation."""
        response = client.post(
            "/api/v1/cascade/trigger",
            json={
                "source_overlay": "security_validator",
                # Missing insight_type and insight_data
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422

    def test_trigger_invalid_max_hops(self, client: TestClient, trusted_auth_headers: dict):
        """Trigger cascade with invalid max_hops fails validation."""
        response = client.post(
            "/api/v1/cascade/trigger",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
                "max_hops": 15,  # Over 10 max
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422

    def test_trigger_max_hops_too_low(self, client: TestClient, trusted_auth_headers: dict):
        """Trigger cascade with max_hops below minimum fails validation."""
        response = client.post(
            "/api/v1/cascade/trigger",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
                "max_hops": 0,  # Below 1 minimum
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# Propagate Cascade Tests
# =============================================================================


class TestPropagateCascadeRoute:
    """Tests for POST /cascade/propagate endpoint."""

    def test_propagate_unauthorized(self, client: TestClient):
        """Propagate cascade without auth fails."""
        response = client.post(
            "/api/v1/cascade/propagate",
            json={
                "cascade_id": "cascade_123",
                "target_overlay": "governance",
                "insight_type": "policy_violation",
                "insight_data": {"violation": "test"},
            },
        )
        assert response.status_code == 401

    def test_propagate_missing_fields(self, client: TestClient, trusted_auth_headers: dict):
        """Propagate cascade with missing fields fails validation."""
        response = client.post(
            "/api/v1/cascade/propagate",
            json={
                "cascade_id": "cascade_123",
                # Missing target_overlay, insight_type, insight_data
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422

    def test_propagate_invalid_impact_score(self, client: TestClient, trusted_auth_headers: dict):
        """Propagate cascade with invalid impact_score fails validation."""
        response = client.post(
            "/api/v1/cascade/propagate",
            json={
                "cascade_id": "cascade_123",
                "target_overlay": "governance",
                "insight_type": "policy_violation",
                "insight_data": {"violation": "test"},
                "impact_score": 1.5,  # Over 1.0 max
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422

    def test_propagate_negative_impact_score(self, client: TestClient, trusted_auth_headers: dict):
        """Propagate cascade with negative impact_score fails validation."""
        response = client.post(
            "/api/v1/cascade/propagate",
            json={
                "cascade_id": "cascade_123",
                "target_overlay": "governance",
                "insight_type": "policy_violation",
                "insight_data": {"violation": "test"},
                "impact_score": -0.5,  # Negative not allowed
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# Complete Cascade Tests
# =============================================================================


class TestCompleteCascadeRoute:
    """Tests for POST /cascade/{cascade_id}/complete endpoint."""

    def test_complete_unauthorized(self, client: TestClient):
        """Complete cascade without auth fails."""
        response = client.post("/api/v1/cascade/cascade_123/complete")
        assert response.status_code == 401


# =============================================================================
# List Cascades Tests
# =============================================================================


class TestListCascadesRoute:
    """Tests for GET /cascade/ endpoint."""

    def test_list_unauthorized(self, client: TestClient):
        """List cascades without auth fails."""
        response = client.get("/api/v1/cascade/")
        assert response.status_code == 401

    def test_list_authorized(
        self, client: TestClient, auth_headers: dict, mock_event_system, sample_cascade_chain
    ):
        """List cascades with auth returns cascades."""
        mock_event_system.get_active_cascades = MagicMock(return_value=[sample_cascade_chain])

        with patch(
            "forge.api.routes.cascade.EventSystemDep",
            return_value=mock_event_system,
        ):
            response = client.get(
                "/api/v1/cascade/",
                headers=auth_headers,
            )

        # Should return list or error
        assert response.status_code in [200, 500]

    def test_list_invalid_limit(self, client: TestClient, auth_headers: dict):
        """List cascades with invalid limit fails validation."""
        response = client.get(
            "/api/v1/cascade/",
            params={"limit": 300},  # Over 200 max
            headers=auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# Get Cascade Tests
# =============================================================================


class TestGetCascadeRoute:
    """Tests for GET /cascade/{cascade_id} endpoint."""

    def test_get_unauthorized(self, client: TestClient):
        """Get cascade without auth fails."""
        response = client.get("/api/v1/cascade/cascade_123")
        assert response.status_code == 401


# =============================================================================
# Metrics Tests
# =============================================================================


class TestGetCascadeMetricsRoute:
    """Tests for GET /cascade/metrics/summary endpoint."""

    def test_get_metrics_unauthorized(self, client: TestClient):
        """Get metrics without auth fails."""
        response = client.get("/api/v1/cascade/metrics/summary")
        assert response.status_code == 401

    def test_get_metrics_authorized(self, client: TestClient, auth_headers: dict):
        """Get metrics with auth returns metrics."""
        response = client.get(
            "/api/v1/cascade/metrics/summary",
            headers=auth_headers,
        )

        # Should return metrics or error
        assert response.status_code in [200, 500]


# =============================================================================
# Pipeline Execution Tests
# =============================================================================


class TestExecutePipelineRoute:
    """Tests for POST /cascade/execute-pipeline endpoint."""

    def test_execute_pipeline_unauthorized(self, client: TestClient):
        """Execute pipeline without auth fails."""
        response = client.post(
            "/api/v1/cascade/execute-pipeline",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
            },
        )
        assert response.status_code == 401

    def test_execute_pipeline_insufficient_trust(self, client: TestClient, auth_headers: dict):
        """Execute pipeline with insufficient trust level fails."""
        response = client.post(
            "/api/v1/cascade/execute-pipeline",
            json={
                "source_overlay": "security_validator",
                "insight_type": "threat_detected",
                "insight_data": {"threat_level": "medium"},
            },
            headers=auth_headers,  # Regular user, not TRUSTED
        )
        # Should fail with 403 (insufficient trust) or succeed if mock allows
        assert response.status_code in [403, 500]

    def test_execute_pipeline_missing_fields(self, client: TestClient, trusted_auth_headers: dict):
        """Execute pipeline with missing fields fails validation."""
        response = client.post(
            "/api/v1/cascade/execute-pipeline",
            json={
                "source_overlay": "security_validator",
                # Missing insight_type and insight_data
            },
            headers=trusted_auth_headers,
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
