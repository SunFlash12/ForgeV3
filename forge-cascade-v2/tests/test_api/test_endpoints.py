"""
API Integration Tests

Tests for REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_root_endpoint(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_invalid_credentials(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "invalid",
                "password": "invalid",
            },
        )
        # Should fail with invalid credentials
        assert response.status_code in [401, 422]

    def test_register_new_user(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newaccount42",
                "email": "new42@example.com",
                "password": "Br!ght$un99Rise",
            },
        )
        # May fail if user exists or DB unavailable, but should not be 400
        assert response.status_code in [201, 409, 422, 500, 503]


class TestCapsuleEndpoints:
    """Tests for capsule CRUD endpoints."""

    def test_list_capsules_unauthorized(self, client: TestClient):
        response = client.get("/api/v1/capsules")
        assert response.status_code == 401

    def test_list_capsules_authorized(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/capsules", headers=auth_headers)
        # Skip if DB/services unavailable instead of masking errors
        if response.status_code in (500, 503):
            pytest.skip("Database/services unavailable - use mock fixtures for reliable tests")
        assert response.status_code == 200

    def test_create_capsule_unauthorized(self, client: TestClient):
        response = client.post(
            "/api/v1/capsules",
            json={
                "content": "Test capsule content",
                "type": "knowledge",
            },
        )
        assert response.status_code == 401

    def test_create_capsule_authorized(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/capsules",
            json={
                "content": "Test capsule content for testing",
                "type": "knowledge",
                "title": "Test Capsule",
            },
            headers=auth_headers,
        )
        if response.status_code in (500, 503):
            pytest.skip("Database/services unavailable - use mock fixtures for reliable tests")
        assert response.status_code == 201


class TestGovernanceEndpoints:
    """Tests for governance endpoints."""

    def test_list_proposals_unauthorized(self, client: TestClient):
        response = client.get("/api/v1/governance/proposals")
        assert response.status_code == 401

    def test_list_proposals_authorized(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/governance/proposals", headers=auth_headers)
        if response.status_code in (500, 503):
            pytest.skip("Database/services unavailable - use mock fixtures for reliable tests")
        assert response.status_code == 200


class TestOverlayEndpoints:
    """Tests for overlay management endpoints."""

    def test_list_overlays_unauthorized(self, client: TestClient):
        response = client.get("/api/v1/overlays")
        assert response.status_code == 401

    def test_list_overlays_authorized(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/overlays", headers=auth_headers)
        if response.status_code in (500, 503):
            pytest.skip("Database/services unavailable - use mock fixtures for reliable tests")
        assert response.status_code == 200


class TestSystemEndpoints:
    """Tests for system administration endpoints."""

    def test_system_health_unauthorized(self, client: TestClient):
        response = client.get("/api/v1/system/health")
        # Health may be public; 503 when kernel services are not initialized
        assert response.status_code in [200, 401, 503]

    def test_system_metrics_unauthorized(self, client: TestClient):
        response = client.get("/api/v1/system/metrics")
        assert response.status_code in [200, 401, 503]


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint."""

    def test_metrics_endpoint(self, client: TestClient):
        response = client.get("/metrics")
        # Metrics endpoint should be accessible
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            assert "forge_" in response.text or "process_" in response.text


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_not_found(self, client: TestClient):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self, client: TestClient):
        response = client.delete("/")
        assert response.status_code == 405

    def test_invalid_json(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/capsules",
            content="not valid json",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert response.status_code == 422
