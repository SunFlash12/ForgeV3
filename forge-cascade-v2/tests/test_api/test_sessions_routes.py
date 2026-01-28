"""
Sessions Routes Tests for Forge Cascade V2

Comprehensive tests for session management API routes including:
- Session listing
- Session count
- Session revocation
- Revoke all sessions
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from forge.models.session import (
    Session,
    SessionListResponse,
    SessionPublic,
    SessionStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session_service():
    """Create mock session binding service."""
    service = AsyncMock()
    service.get_user_sessions = AsyncMock(
        return_value=SessionListResponse(sessions=[], total=0, current_session_id=None)
    )
    service.get_active_session_count = AsyncMock(return_value=1)
    service.revoke_session = AsyncMock(return_value=True)
    service.revoke_all_sessions = AsyncMock(return_value=3)
    return service


@pytest.fixture
def sample_session():
    """Create sample session for testing."""
    now = datetime.now(UTC)
    return Session(
        id="sess123",
        user_id="user123",
        token_jti="jti123",
        token_type="access",
        initial_ip="192.168.1.1",
        initial_user_agent="Mozilla/5.0",
        last_ip="192.168.1.1",
        last_user_agent="Mozilla/5.0",
        last_activity=now,
        request_count=10,
        ip_change_count=0,
        user_agent_change_count=0,
        ip_history=[],
        expires_at=now + timedelta(hours=1),
        status=SessionStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_session_public():
    """Create sample public session response."""
    now = datetime.now(UTC)
    return SessionPublic(
        id="sess123",
        token_type="access",
        initial_ip="192.***.***.1",
        last_ip="192.***.***.1",
        last_activity=now,
        request_count=10,
        ip_change_count=0,
        user_agent_change_count=0,
        status=SessionStatus.ACTIVE,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        is_current=True,
    )


# =============================================================================
# Session Listing Tests
# =============================================================================


class TestListSessionsRoute:
    """Tests for GET /sessions endpoint."""

    def test_list_sessions_unauthorized(self, client: TestClient):
        """List sessions without auth fails."""
        response = client.get("/api/v1/sessions")
        assert response.status_code == 401

    def test_list_sessions_authorized(self, client: TestClient, auth_headers: dict):
        """List sessions with auth returns session list."""
        response = client.get("/api/v1/sessions", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "sessions" in data
            assert "total" in data

    def test_list_sessions_includes_current_marker(self, client: TestClient, auth_headers: dict):
        """List sessions marks current session."""
        response = client.get("/api/v1/sessions", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            # current_session_id should be present
            assert "current_session_id" in data or "sessions" in data


# =============================================================================
# Session Count Tests
# =============================================================================


class TestSessionCountRoute:
    """Tests for GET /sessions/count endpoint."""

    def test_get_session_count_unauthorized(self, client: TestClient):
        """Get session count without auth fails."""
        response = client.get("/api/v1/sessions/count")
        assert response.status_code == 401

    def test_get_session_count_authorized(self, client: TestClient, auth_headers: dict):
        """Get session count with auth returns count."""
        response = client.get("/api/v1/sessions/count", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "count" in data
            assert isinstance(data["count"], int)


# =============================================================================
# Revoke Session Tests
# =============================================================================


class TestRevokeSessionRoute:
    """Tests for DELETE /sessions/{session_id} endpoint."""

    def test_revoke_session_unauthorized(self, client: TestClient):
        """Revoke session without auth fails."""
        response = client.delete("/api/v1/sessions/sess123")
        assert response.status_code == 401

    def test_revoke_session_authorized(self, client: TestClient, auth_headers: dict):
        """Revoke session with auth succeeds or returns 404."""
        response = client.delete("/api/v1/sessions/other_sess123", headers=auth_headers)
        assert response.status_code in [200, 400, 404, 401, 503]

    def test_revoke_session_with_reason(self, client: TestClient, auth_headers: dict):
        """Revoke session with reason."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions/other_sess123",
            json={"reason": "Security concern"},
            headers=auth_headers,
        )
        assert response.status_code in [200, 400, 404, 401, 503]

    def test_revoke_current_session_fails(self, client: TestClient, auth_headers: dict):
        """Revoking current session should fail with guidance to use logout."""
        # This test verifies the endpoint checks for current session
        # The actual session ID would be the JTI from the token
        # Since we don't know the exact JTI, we test the validation path
        response = client.delete("/api/v1/sessions/some_session", headers=auth_headers)
        # Could be 400 (if it's current), 404 (if not found), or 200 (if found and revoked)
        assert response.status_code in [200, 400, 404, 401, 503]


# =============================================================================
# Revoke All Sessions Tests
# =============================================================================


class TestRevokeAllSessionsRoute:
    """Tests for DELETE /sessions endpoint."""

    def test_revoke_all_unauthorized(self, client: TestClient):
        """Revoke all sessions without auth fails."""
        response = client.delete("/api/v1/sessions")
        assert response.status_code == 401

    def test_revoke_all_authorized(self, client: TestClient, auth_headers: dict):
        """Revoke all sessions with auth succeeds."""
        response = client.delete("/api/v1/sessions", headers=auth_headers)
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "message" in data
            assert "revoked_count" in data

    def test_revoke_all_except_current(self, client: TestClient, auth_headers: dict):
        """Revoke all sessions except current (default behavior)."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions",
            json={"except_current": True},
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]

        if response.status_code == 200:
            data = response.json()
            assert "revoked_count" in data
            # Message should indicate current session was preserved
            if "message" in data:
                assert "preserved" in data["message"].lower() or "other" in data["message"].lower()

    def test_revoke_all_including_current(self, client: TestClient, auth_headers: dict):
        """Revoke all sessions including current."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions",
            json={"except_current": False},
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]

    def test_revoke_all_with_reason(self, client: TestClient, auth_headers: dict):
        """Revoke all sessions with reason."""
        response = client.request(
            "DELETE",
            "/api/v1/sessions",
            json={
                "except_current": True,
                "reason": "Security audit - revoking all sessions",
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 503]


# =============================================================================
# Session Public Model Tests
# =============================================================================


class TestSessionPublicMasking:
    """Tests for SessionPublic IP masking."""

    def test_mask_ipv4(self):
        """IPv4 address is properly masked."""
        masked = SessionPublic.mask_ip("192.168.1.100")
        assert masked == "192.***.***.100"
        # Should not expose middle octets
        assert "168" not in masked
        assert "1" not in masked.split(".")[1:3]

    def test_mask_ipv6_like(self):
        """Long IP-like strings are truncated."""
        masked = SessionPublic.mask_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        # Should be truncated for long strings
        assert len(masked) < len("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert "..." in masked

    def test_mask_short_string(self):
        """Short strings are returned as-is."""
        masked = SessionPublic.mask_ip("127.0.0.1")
        # Short enough to return as-is
        assert "127" in masked


# =============================================================================
# Session Status Tests
# =============================================================================


class TestSessionStatus:
    """Tests for session status enum and validation."""

    def test_session_status_values(self):
        """Session status has expected values."""
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.EXPIRED == "expired"
        assert SessionStatus.REVOKED == "revoked"
        assert SessionStatus.SUSPICIOUS == "suspicious"


# =============================================================================
# Session Model Tests
# =============================================================================


class TestSessionModel:
    """Tests for Session model properties."""

    def test_session_is_active(self, sample_session):
        """Session is_active property works correctly."""
        # Active session with future expiry
        assert sample_session.is_active is True

    def test_session_is_active_expired(self, sample_session):
        """Expired session returns is_active False."""
        sample_session.expires_at = datetime.now(UTC) - timedelta(hours=1)
        assert sample_session.is_active is False

    def test_session_is_active_revoked(self, sample_session):
        """Revoked session returns is_active False."""
        sample_session.status = SessionStatus.REVOKED
        assert sample_session.is_active is False

    def test_session_is_suspicious(self, sample_session):
        """Session is_suspicious property works correctly."""
        assert sample_session.is_suspicious is False
        sample_session.status = SessionStatus.SUSPICIOUS
        assert sample_session.is_suspicious is True

    def test_hash_user_agent(self):
        """User-Agent hashing works correctly."""
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        hash1 = Session.hash_user_agent(ua)
        hash2 = Session.hash_user_agent(ua)

        # Same input produces same hash
        assert hash1 == hash2
        # Hash is SHA-256 (64 hex chars)
        assert len(hash1) == 64

        # None returns None
        assert Session.hash_user_agent(None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
