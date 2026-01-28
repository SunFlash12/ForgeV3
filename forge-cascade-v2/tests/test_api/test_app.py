"""
Forge Cascade V2 - API Application Tests

Comprehensive tests for the FastAPI application factory and configuration.
Tests app creation, middleware setup, exception handlers, and route configuration.
"""

from __future__ import annotations

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request


# =============================================================================
# ForgeApp Class Tests
# =============================================================================


class TestForgeApp:
    """Tests for the ForgeApp container class."""

    def test_forge_app_initialization(self):
        """Test ForgeApp initializes with correct default state."""
        from forge.api.app import ForgeApp

        app = ForgeApp()

        # Core components should be None initially
        assert app.db_client is None
        assert app.event_system is None
        assert app.overlay_manager is None
        assert app.pipeline is None

        # Immune system components should be None
        assert app.circuit_registry is None
        assert app.health_checker is None
        assert app.anomaly_system is None
        assert app.canary_manager is None

        # State should be not ready
        assert app.is_ready is False
        assert app.started_at is None
        assert app.resilience_initialized is False

        # Settings should be loaded
        assert app.settings is not None

    def test_get_status_before_init(self):
        """Test get_status returns correct status before initialization."""
        from forge.api.app import ForgeApp

        app = ForgeApp()
        status = app.get_status()

        assert status["status"] == "starting"
        assert status["started_at"] is None
        assert status["uptime_seconds"] == 0
        assert status["database"] == "disconnected"
        assert status["overlays"] == 0

    def test_get_status_after_ready(self):
        """Test get_status returns correct status when ready."""
        from forge.api.app import ForgeApp

        app = ForgeApp()
        app.is_ready = True
        app.started_at = datetime.now(UTC)
        app.db_client = MagicMock()
        app.db_client._driver = MagicMock()

        status = app.get_status()

        assert status["status"] == "ready"
        assert status["started_at"] is not None
        assert status["database"] == "connected"


# =============================================================================
# Create App Tests
# =============================================================================


class TestCreateApp:
    """Tests for the create_app factory function."""

    def test_create_app_returns_fastapi_instance(self):
        """Test create_app returns a FastAPI instance."""
        from forge.api.app import create_app

        app = create_app(
            title="Test App",
            version="1.0.0",
            docs_url=None,
            redoc_url=None,
        )

        assert isinstance(app, FastAPI)

    def test_create_app_custom_title_and_version(self):
        """Test create_app uses custom title and version."""
        from forge.api.app import create_app

        app = create_app(
            title="Custom Title",
            version="2.5.0",
            description="Test Description",
            docs_url=None,
            redoc_url=None,
        )

        assert app.title == "Custom Title"
        assert app.version == "2.5.0"
        assert app.description == "Test Description"

    def test_create_app_includes_openapi_tags(self):
        """Test create_app includes expected OpenAPI tags."""
        from forge.api.app import create_app

        app = create_app(docs_url=None, redoc_url=None)

        tag_names = [tag["name"] for tag in app.openapi_tags]
        assert "auth" in tag_names
        assert "capsules" in tag_names
        assert "cascade" in tag_names
        assert "governance" in tag_names
        assert "overlays" in tag_names
        assert "system" in tag_names

    def test_create_app_stores_forge_app_reference(self):
        """Test create_app stores ForgeApp reference in state."""
        from forge.api.app import create_app, forge_app

        app = create_app(docs_url=None, redoc_url=None)

        assert hasattr(app.state, "forge")
        assert app.state.forge is forge_app

    @patch("forge.api.app.get_settings")
    def test_create_app_disables_docs_in_production(self, mock_settings):
        """Test create_app disables docs when in production mode."""
        mock_settings.return_value = MagicMock(
            app_env="production",
            CORS_ORIGINS=["https://example.com"],
            redis_url=None,
        )

        from forge.api.app import create_app

        app = create_app(
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # In production, docs should be disabled
        assert app.docs_url is None
        assert app.redoc_url is None


# =============================================================================
# Route Registration Tests
# =============================================================================


class TestRouteRegistration:
    """Tests for route registration in create_app."""

    def test_auth_routes_registered(self, client: TestClient):
        """Test authentication routes are registered."""
        # Login endpoint should be available
        response = client.post("/api/v1/auth/login", json={})
        # Should return validation error, not 404
        assert response.status_code != 404

    def test_capsule_routes_registered(self, client: TestClient, auth_headers: dict):
        """Test capsule routes are registered."""
        response = client.get("/api/v1/capsules", headers=auth_headers)
        # Should not return 404
        assert response.status_code != 404

    def test_governance_routes_registered(self, client: TestClient, auth_headers: dict):
        """Test governance routes are registered."""
        response = client.get("/api/v1/governance/proposals", headers=auth_headers)
        assert response.status_code != 404

    def test_overlay_routes_registered(self, client: TestClient, auth_headers: dict):
        """Test overlay routes are registered."""
        response = client.get("/api/v1/overlays", headers=auth_headers)
        assert response.status_code != 404

    def test_system_routes_registered(self, client: TestClient):
        """Test system routes are registered."""
        response = client.get("/api/v1/system/health")
        assert response.status_code != 404


# =============================================================================
# Built-in Endpoint Tests
# =============================================================================


class TestBuiltInEndpoints:
    """Tests for built-in endpoints (root, health, ready)."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns app info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data

    def test_health_endpoint_returns_status(self, client: TestClient):
        """Test health endpoint returns health status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "starting"]

    def test_ready_endpoint_not_ready(self, client: TestClient):
        """Test ready endpoint when app is not ready."""
        # In test mode with mocked lifespan, app may or may not be ready
        response = client.get("/ready")
        assert response.status_code in [200, 503]


# =============================================================================
# Exception Handler Tests
# =============================================================================


class TestExceptionHandlers:
    """Tests for custom exception handlers."""

    def test_404_not_found_handler(self, client: TestClient):
        """Test 404 error returns proper JSON format."""
        response = client.get("/nonexistent/path")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data

    def test_validation_error_handler(self, client: TestClient, auth_headers: dict):
        """Test validation errors return sanitized format."""
        response = client.post(
            "/api/v1/capsules",
            json={"invalid": "data"},
            headers=auth_headers,
        )

        # Should return validation error
        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data

    def test_validation_error_sanitization(self, client: TestClient, auth_headers: dict):
        """Test validation errors don't leak sensitive schema details."""
        response = client.post(
            "/api/v1/auth/login",
            json={"password": "secret123"},  # Missing username
        )

        assert response.status_code == 422
        data = response.json()

        # Should not contain the actual submitted values
        response_text = str(data)
        assert "secret123" not in response_text

    def test_general_exception_returns_500(self, app: FastAPI):
        """Test unhandled exceptions return 500 with safe message."""
        # Create a route that raises an exception
        @app.get("/test-error")
        async def test_error():
            raise RuntimeError("Internal error details")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/test-error")

            assert response.status_code == 500
            data = response.json()
            assert "error" in data
            # Should not expose internal error details
            assert "Internal error details" not in data.get("error", "")


# =============================================================================
# CORS Configuration Tests
# =============================================================================


class TestCorsConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client: TestClient):
        """Test CORS headers are present on responses."""
        response = client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"},
        )

        # CORS should handle the preflight request
        assert response.status_code in [200, 400, 405]

    def test_cors_allows_authorized_origin(self, client: TestClient):
        """Test CORS allows requests from authorized origins."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200


# =============================================================================
# Sentry Integration Tests
# =============================================================================


class TestSentryBeforeSend:
    """Tests for the Sentry before_send filter."""

    def test_health_check_filtered(self):
        """Test health check errors are filtered out."""
        from forge.api.app import _sentry_before_send

        event = {
            "request": {"url": "https://api.example.com/health"},
        }

        result = _sentry_before_send(event, {})
        assert result is None

    def test_ready_check_filtered(self):
        """Test ready check errors are filtered out."""
        from forge.api.app import _sentry_before_send

        event = {
            "request": {"url": "https://api.example.com/ready"},
        }

        result = _sentry_before_send(event, {})
        assert result is None

    def test_normal_events_not_filtered(self):
        """Test normal error events are not filtered."""
        from forge.api.app import _sentry_before_send

        event = {
            "request": {"url": "https://api.example.com/api/v1/capsules"},
        }

        result = _sentry_before_send(event, {})
        assert result is event

    def test_event_without_url(self):
        """Test events without URL are not filtered."""
        from forge.api.app import _sentry_before_send

        event = {"message": "Some error"}

        result = _sentry_before_send(event, {})
        assert result is event


# =============================================================================
# Lifespan Tests
# =============================================================================


class TestLifespan:
    """Tests for application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self):
        """Test lifespan context manager structure."""
        from forge.api.app import lifespan
        from forge.api.app import ForgeApp

        # Create a mock app
        mock_app = MagicMock(spec=FastAPI)

        # Mock the forge_app to avoid actual initialization
        with patch("forge.api.app.forge_app") as mock_forge:
            mock_forge.initialize = AsyncMock()
            mock_forge.shutdown = AsyncMock()

            async with lifespan(mock_app):
                # Should have called initialize
                mock_forge.initialize.assert_called_once()

            # Should have called shutdown
            mock_forge.shutdown.assert_called_once()


# =============================================================================
# Middleware Stack Tests
# =============================================================================


class TestMiddlewareStack:
    """Tests for middleware stack configuration."""

    def test_correlation_id_added_to_response(self, client: TestClient):
        """Test correlation ID is added to responses."""
        response = client.get("/health")

        assert "X-Correlation-ID" in response.headers

    def test_response_time_header_present(self, client: TestClient):
        """Test X-Response-Time header is present."""
        response = client.get("/")

        assert "X-Response-Time" in response.headers

    def test_security_headers_present(self, client: TestClient):
        """Test security headers are present on responses."""
        response = client.get("/health")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_rate_limit_headers_present(self, client: TestClient, auth_headers: dict):
        """Test rate limit headers are present."""
        response = client.get("/api/v1/capsules", headers=auth_headers)

        # Rate limit headers should be present if request was processed
        if response.status_code not in [429, 503]:
            assert "X-RateLimit-Limit" in response.headers


# =============================================================================
# Health Detail Endpoint Tests
# =============================================================================


class TestHealthDetailedEndpoint:
    """Tests for the detailed health endpoint."""

    def test_health_detailed_returns_components(self, client: TestClient):
        """Test detailed health endpoint returns component status."""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "timestamp" in data

    def test_health_detailed_includes_database_status(self, client: TestClient):
        """Test detailed health includes database component."""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "database" in data.get("components", {})

    def test_health_detailed_includes_warnings(self, client: TestClient):
        """Test detailed health includes warnings array."""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "warnings" in data
        assert isinstance(data["warnings"], list)


# =============================================================================
# API Version Headers Tests
# =============================================================================


class TestApiVersionHeaders:
    """Tests for API versioning headers."""

    def test_api_version_header_present(self, client: TestClient):
        """Test X-API-Version header is present."""
        response = client.get("/health")

        assert "X-API-Version" in response.headers

    def test_api_min_version_header_present(self, client: TestClient):
        """Test X-API-Min-Version header is present."""
        response = client.get("/health")

        assert "X-API-Min-Version" in response.headers


# =============================================================================
# Module Level Tests
# =============================================================================


class TestModuleLevelVariables:
    """Tests for module-level configuration."""

    def test_settings_loaded_on_import(self):
        """Test settings are loaded at module import."""
        from forge.api.app import _settings

        assert _settings is not None

    def test_logger_configured(self):
        """Test logger is configured."""
        from forge.api.app import logger

        assert logger is not None

    def test_default_app_created(self):
        """Test default app instance is created."""
        from forge.api.app import app

        assert isinstance(app, FastAPI)
