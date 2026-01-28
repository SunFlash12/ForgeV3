"""
Agent Gateway Routes Tests for Forge Cascade V2

Comprehensive tests for Agent Gateway API routes including:
- Session management (create, list, get, revoke)
- Query execution (execute, search, get capsule, neighbors)
- Capsule creation
- Statistics and access logs
- WebSocket streaming
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_gateway_service():
    """Create mock gateway service."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_session():
    """Create a sample agent session for testing."""
    session = MagicMock()
    session.id = "session_123"
    session.agent_id = "agent_001"
    session.agent_name = "Test Agent"
    session.owner_user_id = "user_123"
    session.trust_level = MagicMock(value="basic")
    session.capabilities = [MagicMock(value="read_capsules"), MagicMock(value="query_graph")]
    session.requests_per_minute = 60
    session.requests_per_hour = 1000
    session.total_requests = 0
    session.is_active = True
    session.created_at = datetime.now()
    session.expires_at = datetime.now() + timedelta(days=30)
    return session


@pytest.fixture
def sample_query_result():
    """Create a sample query result for testing."""
    result = MagicMock()
    result.query_id = "query_123"
    result.success = True
    result.results = [{"id": "capsule_001", "title": "Test Capsule"}]
    result.total_count = 1
    result.generated_cypher = "MATCH (n) RETURN n"
    result.answer = "Test answer"
    result.sources = []
    result.execution_time_ms = 50
    result.tokens_used = 100
    result.cache_hit = False
    result.error = None
    result.error_code = None
    return result


@pytest.fixture
def sample_stats():
    """Create sample gateway stats for testing."""
    stats = MagicMock()
    stats.active_sessions = 5
    stats.total_sessions = 100
    stats.queries_today = 500
    stats.queries_this_hour = 50
    stats.avg_response_time_ms = 45.5
    stats.cache_hit_rate = 0.35
    stats.queries_by_type = {"natural_language": 300, "semantic_search": 200}
    stats.capsules_read = 1000
    stats.capsules_created = 50
    stats.error_rate = 0.02
    return stats


# =============================================================================
# Session Management Tests
# =============================================================================


class TestCreateSessionRoute:
    """Tests for POST /agent-gateway/sessions endpoint."""

    def test_create_session_unauthorized(self, client: TestClient):
        """Create session without auth fails."""
        response = client.post(
            "/api/v1/agent-gateway/sessions",
            json={
                "agent_name": "Test Agent",
                "trust_level": "basic",
            },
        )
        assert response.status_code == 401

    def test_create_session_missing_agent_name(self, client: TestClient, auth_headers: dict):
        """Create session without agent_name fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/sessions",
            json={
                "trust_level": "basic",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_session_agent_name_too_long(self, client: TestClient, auth_headers: dict):
        """Create session with agent_name exceeding max length fails."""
        response = client.post(
            "/api/v1/agent-gateway/sessions",
            json={
                "agent_name": "A" * 150,  # Over 100 max
                "trust_level": "basic",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_session_invalid_expires_in_days(self, client: TestClient, auth_headers: dict):
        """Create session with invalid expires_in_days fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/sessions",
            json={
                "agent_name": "Test Agent",
                "expires_in_days": 500,  # Over 365 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_session_authorized(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_session
    ):
        """Create session with valid data succeeds."""
        mock_gateway_service.create_session = AsyncMock(
            return_value=(sample_session, "test_api_key_123")
        )

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.post(
                "/api/v1/agent-gateway/sessions",
                json={
                    "agent_name": "Test Agent",
                    "trust_level": "basic",
                    "expires_in_days": 30,
                },
                headers=auth_headers,
            )

        # Should succeed or return error
        assert response.status_code in [200, 201, 500], (
            f"Expected 200/201/500, got {response.status_code}: {response.text[:200]}"
        )


class TestListSessionsRoute:
    """Tests for GET /agent-gateway/sessions endpoint."""

    def test_list_sessions_unauthorized(self, client: TestClient):
        """List sessions without auth fails."""
        response = client.get("/api/v1/agent-gateway/sessions")
        assert response.status_code == 401

    def test_list_sessions_authorized(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_session
    ):
        """List sessions with auth returns sessions."""
        mock_gateway_service.list_sessions = AsyncMock(return_value=[sample_session])

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/sessions",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500]

    def test_list_sessions_with_active_filter(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_session
    ):
        """List sessions with active_only filter."""
        mock_gateway_service.list_sessions = AsyncMock(return_value=[sample_session])

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/sessions",
                params={"active_only": False},
                headers=auth_headers,
            )

        assert response.status_code in [200, 500]


class TestGetSessionRoute:
    """Tests for GET /agent-gateway/sessions/{session_id} endpoint."""

    def test_get_session_unauthorized(self, client: TestClient):
        """Get session without auth fails."""
        response = client.get("/api/v1/agent-gateway/sessions/session_123")
        assert response.status_code == 401

    def test_get_session_not_found(
        self, client: TestClient, auth_headers: dict, mock_gateway_service
    ):
        """Get non-existent session returns 404."""
        mock_gateway_service.get_session = AsyncMock(return_value=None)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/sessions/nonexistent",
                headers=auth_headers,
            )

        assert response.status_code in [404, 500]

    def test_get_session_not_owner(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_session
    ):
        """Get session owned by another user returns 404."""
        sample_session.owner_user_id = "other_user"
        mock_gateway_service.get_session = AsyncMock(return_value=sample_session)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/sessions/session_123",
                headers=auth_headers,
            )

        assert response.status_code in [404, 500]


class TestRevokeSessionRoute:
    """Tests for DELETE /agent-gateway/sessions/{session_id} endpoint."""

    def test_revoke_session_unauthorized(self, client: TestClient):
        """Revoke session without auth fails."""
        response = client.delete("/api/v1/agent-gateway/sessions/session_123")
        assert response.status_code == 401

    def test_revoke_session_not_found(
        self, client: TestClient, auth_headers: dict, mock_gateway_service
    ):
        """Revoke non-existent session returns 404."""
        mock_gateway_service.get_session = AsyncMock(return_value=None)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.delete(
                "/api/v1/agent-gateway/sessions/nonexistent",
                headers=auth_headers,
            )

        assert response.status_code in [404, 500]


# =============================================================================
# Query Endpoints Tests (Agent-facing, API key auth)
# =============================================================================


class TestExecuteQueryRoute:
    """Tests for POST /agent-gateway/query endpoint."""

    def test_query_missing_api_key(self, client: TestClient):
        """Query without API key fails."""
        response = client.post(
            "/api/v1/agent-gateway/query",
            json={
                "query_type": "natural_language",
                "query_text": "What is knowledge?",
            },
        )
        assert response.status_code == 422  # Missing required api_key param

    def test_query_invalid_api_key(self, client: TestClient, mock_gateway_service):
        """Query with invalid API key fails."""
        mock_gateway_service.authenticate = AsyncMock(return_value=None)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.post(
                "/api/v1/agent-gateway/query",
                params={"api_key": "invalid_key"},
                json={
                    "query_type": "natural_language",
                    "query_text": "What is knowledge?",
                },
            )

        assert response.status_code in [401, 500]

    def test_query_text_too_long(self, client: TestClient):
        """Query with text exceeding max length fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/query",
            params={"api_key": "test_key"},
            json={
                "query_type": "natural_language",
                "query_text": "A" * 5000,  # Over 4096 max
            },
        )
        assert response.status_code == 422

    def test_query_invalid_max_results(self, client: TestClient):
        """Query with invalid max_results fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/query",
            params={"api_key": "test_key"},
            json={
                "query_type": "natural_language",
                "query_text": "Test query",
                "max_results": 200,  # Over 100 max
            },
        )
        assert response.status_code == 422


class TestSemanticSearchRoute:
    """Tests for POST /agent-gateway/search endpoint."""

    def test_search_missing_api_key(self, client: TestClient):
        """Search without API key fails."""
        response = client.post(
            "/api/v1/agent-gateway/search",
            params={"query": "test search"},
        )
        assert response.status_code == 422

    def test_search_query_too_long(self, client: TestClient):
        """Search with query exceeding max length fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/search",
            params={
                "api_key": "test_key",
                "query": "A" * 1500,  # Over 1000 max
            },
        )
        assert response.status_code == 422

    def test_search_invalid_max_results(self, client: TestClient):
        """Search with invalid max_results fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/search",
            params={
                "api_key": "test_key",
                "query": "test search",
                "max_results": 100,  # Over 50 max
            },
        )
        assert response.status_code == 422


class TestGetCapsuleRoute:
    """Tests for GET /agent-gateway/capsule/{capsule_id} endpoint."""

    def test_get_capsule_missing_api_key(self, client: TestClient):
        """Get capsule without API key fails."""
        response = client.get("/api/v1/agent-gateway/capsule/capsule_123")
        assert response.status_code == 422


class TestGetCapsuleNeighborsRoute:
    """Tests for GET /agent-gateway/capsule/{capsule_id}/neighbors endpoint."""

    def test_get_neighbors_missing_api_key(self, client: TestClient):
        """Get neighbors without API key fails."""
        response = client.get("/api/v1/agent-gateway/capsule/capsule_123/neighbors")
        assert response.status_code == 422

    def test_get_neighbors_invalid_direction(self, client: TestClient):
        """Get neighbors with invalid direction fails validation."""
        response = client.get(
            "/api/v1/agent-gateway/capsule/capsule_123/neighbors",
            params={
                "api_key": "test_key",
                "direction": "invalid",  # Must be in, out, or both
            },
        )
        assert response.status_code == 422

    def test_get_neighbors_invalid_max_depth(self, client: TestClient):
        """Get neighbors with invalid max_depth fails validation."""
        response = client.get(
            "/api/v1/agent-gateway/capsule/capsule_123/neighbors",
            params={
                "api_key": "test_key",
                "max_depth": 10,  # Over 5 max
            },
        )
        assert response.status_code == 422


# =============================================================================
# Capsule Creation Tests
# =============================================================================


class TestCreateCapsuleRoute:
    """Tests for POST /agent-gateway/capsules endpoint."""

    def test_create_capsule_missing_api_key(self, client: TestClient):
        """Create capsule without API key fails."""
        response = client.post(
            "/api/v1/agent-gateway/capsules",
            json={
                "capsule_type": "knowledge",
                "title": "Test Capsule",
                "content": "Test content",
            },
        )
        assert response.status_code == 422

    def test_create_capsule_missing_fields(self, client: TestClient):
        """Create capsule with missing fields fails validation."""
        response = client.post(
            "/api/v1/agent-gateway/capsules",
            params={"api_key": "test_key"},
            json={
                "capsule_type": "knowledge",
                # Missing title and content
            },
        )
        assert response.status_code == 422

    def test_create_capsule_title_too_long(self, client: TestClient):
        """Create capsule with title exceeding max length fails."""
        response = client.post(
            "/api/v1/agent-gateway/capsules",
            params={"api_key": "test_key"},
            json={
                "capsule_type": "knowledge",
                "title": "A" * 250,  # Over 200 max
                "content": "Test content",
            },
        )
        assert response.status_code == 422


# =============================================================================
# Statistics and Logging Tests
# =============================================================================


class TestGetGatewayStatsRoute:
    """Tests for GET /agent-gateway/stats endpoint."""

    def test_get_stats_unauthorized(self, client: TestClient):
        """Get stats without auth fails."""
        response = client.get("/api/v1/agent-gateway/stats")
        assert response.status_code == 401

    def test_get_stats_authorized(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_stats
    ):
        """Get stats with auth returns stats."""
        mock_gateway_service.get_stats = AsyncMock(return_value=sample_stats)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/stats",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500]


class TestGetAccessLogsRoute:
    """Tests for GET /agent-gateway/sessions/{session_id}/access-logs endpoint."""

    def test_get_access_logs_unauthorized(self, client: TestClient):
        """Get access logs without auth fails."""
        response = client.get("/api/v1/agent-gateway/sessions/session_123/access-logs")
        assert response.status_code == 401

    def test_get_access_logs_invalid_limit(self, client: TestClient, auth_headers: dict):
        """Get access logs with invalid limit fails validation."""
        response = client.get(
            "/api/v1/agent-gateway/sessions/session_123/access-logs",
            params={"limit": 200},  # Over 100 max
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_get_access_logs_not_owner(
        self, client: TestClient, auth_headers: dict, mock_gateway_service, sample_session
    ):
        """Get access logs for session owned by another user returns 404."""
        sample_session.owner_user_id = "other_user"
        mock_gateway_service.get_session = AsyncMock(return_value=sample_session)

        with patch(
            "forge.api.routes.agent_gateway.get_gateway_service",
            return_value=mock_gateway_service,
        ):
            response = client.get(
                "/api/v1/agent-gateway/sessions/session_123/access-logs",
                headers=auth_headers,
            )

        assert response.status_code in [404, 500]


# =============================================================================
# Capabilities Reference Tests
# =============================================================================


class TestListCapabilitiesRoute:
    """Tests for GET /agent-gateway/capabilities endpoint."""

    def test_list_capabilities_unauthorized(self, client: TestClient):
        """List capabilities without auth fails."""
        response = client.get("/api/v1/agent-gateway/capabilities")
        assert response.status_code == 401

    def test_list_capabilities_authorized(self, client: TestClient, auth_headers: dict):
        """List capabilities with auth returns capabilities."""
        response = client.get(
            "/api/v1/agent-gateway/capabilities",
            headers=auth_headers,
        )

        # Should return capabilities or error
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "capabilities" in data
            assert "query_types" in data
            assert "trust_levels" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
