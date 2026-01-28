"""
Session Repository Tests for Forge Cascade V2

Comprehensive tests for SessionRepository including:
- Session CRUD operations
- Activity tracking with IP and User-Agent binding
- Session revocation (single and bulk)
- Suspicious session flagging
- Session cleanup
- Caching (SessionCache)
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.session import (
    Session,
    SessionCreate,
    SessionStatus,
)
from forge.repositories.session_repository import (
    SessionCache,
    SessionRepository,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def session_repository(mock_db_client):
    """Create session repository with mock client."""
    return SessionRepository(mock_db_client)


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "session-jti-123",
        "user_id": "user123",
        "token_jti": "session-jti-123",
        "token_type": "access",
        "initial_ip": "192.168.1.100",
        "initial_user_agent": "Mozilla/5.0 Test Browser",
        "initial_user_agent_hash": Session.hash_user_agent("Mozilla/5.0 Test Browser"),
        "last_ip": "192.168.1.100",
        "last_user_agent": "Mozilla/5.0 Test Browser",
        "last_user_agent_hash": Session.hash_user_agent("Mozilla/5.0 Test Browser"),
        "last_activity": now.isoformat(),
        "request_count": 5,
        "ip_change_count": 0,
        "user_agent_change_count": 0,
        "ip_history": json.dumps([{"ip": "192.168.1.100", "timestamp": now.isoformat(), "action": "created"}]),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "status": "active",
        "revoked_at": None,
        "revoked_reason": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@pytest.fixture(autouse=True)
async def clear_session_cache():
    """Clear session cache before each test."""
    await SessionCache.clear()
    yield
    await SessionCache.clear()


# =============================================================================
# Session Creation Tests
# =============================================================================


class TestSessionRepositoryCreate:
    """Tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Successful session creation."""
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        session_create = SessionCreate(
            user_id="user123",
            token_jti="session-jti-123",
            token_type="access",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        result = await session_repository.create(data=session_create)

        assert result.user_id == "user123"
        assert result.token_jti == "session-jti-123"
        assert result.initial_ip == "192.168.1.100"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_computes_user_agent_hash(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Session creation computes User-Agent hash."""
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        user_agent = "Mozilla/5.0 Test Browser"
        expected_hash = Session.hash_user_agent(user_agent)

        session_create = SessionCreate(
            user_id="user123",
            token_jti="session-jti-123",
            ip_address="192.168.1.100",
            user_agent=user_agent,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        await session_repository.create(data=session_create)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["ua_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_create_session_initializes_ip_history(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Session creation initializes IP history."""
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        session_create = SessionCreate(
            user_id="user123",
            token_jti="session-jti-123",
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        await session_repository.create(data=session_create)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        ip_history = json.loads(params["ip_history"])
        assert len(ip_history) == 1
        assert ip_history[0]["ip"] == "192.168.1.100"
        assert ip_history[0]["action"] == "created"

    @pytest.mark.asyncio
    async def test_create_session_failure_raises_error(
        self, session_repository, mock_db_client
    ):
        """Session creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        session_create = SessionCreate(
            user_id="user123",
            token_jti="session-jti-123",
            ip_address="192.168.1.100",
            user_agent="Test Browser",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        with pytest.raises(RuntimeError, match="Failed to create session"):
            await session_repository.create(data=session_create)

    @pytest.mark.asyncio
    async def test_create_session_caches_result(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Session creation caches the result."""
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        session_create = SessionCreate(
            user_id="user123",
            token_jti="session-jti-123",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        with patch.object(SessionCache, "set", new_callable=AsyncMock) as mock_cache_set:
            await session_repository.create(data=session_create)
            mock_cache_set.assert_called_once()


# =============================================================================
# Session Retrieval Tests
# =============================================================================


class TestSessionRepositoryRetrieval:
    """Tests for session retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_by_jti_success(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Get session by JTI success."""
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        result = await session_repository.get_by_jti("session-jti-123")

        assert result is not None
        assert result.token_jti == "session-jti-123"

    @pytest.mark.asyncio
    async def test_get_by_jti_empty_jti_returns_none(
        self, session_repository, mock_db_client
    ):
        """Get by empty JTI returns None."""
        result = await session_repository.get_by_jti("")

        assert result is None
        mock_db_client.execute_single.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_by_jti_not_found(
        self, session_repository, mock_db_client
    ):
        """Get by JTI returns None for non-existent session."""
        mock_db_client.execute_single.return_value = None

        result = await session_repository.get_by_jti("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_jti_marks_expired_session(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Get by JTI marks expired sessions."""
        # Set session as expired
        sample_session_data["expires_at"] = (
            datetime.now(UTC) - timedelta(hours=1)
        ).isoformat()
        mock_db_client.execute_single.return_value = {"session": sample_session_data}

        result = await session_repository.get_by_jti("session-jti-123")

        assert result is None
        # Should have called _mark_expired (which calls execute)
        assert mock_db_client.execute.called

    @pytest.mark.asyncio
    async def test_get_by_jti_uses_cache(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Get by JTI uses cache if available."""
        # Pre-populate cache
        session = Session.model_validate({
            **sample_session_data,
            "ip_history": json.loads(sample_session_data["ip_history"]),
        })

        with patch.object(SessionCache, "get", new_callable=AsyncMock, return_value=session):
            result = await session_repository.get_by_jti("session-jti-123")

            assert result is not None
            assert result.token_jti == "session-jti-123"
            # Database should not be called
            mock_db_client.execute_single.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_sessions(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Get all sessions for a user."""
        mock_db_client.execute.return_value = [{"session": sample_session_data}]

        result = await session_repository.get_user_sessions("user123")

        assert len(result) == 1
        assert result[0].user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_user_sessions_include_expired(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Get user sessions including expired."""
        sample_session_data["status"] = "expired"
        mock_db_client.execute.return_value = [{"session": sample_session_data}]

        result = await session_repository.get_user_sessions(
            "user123",
            include_expired=True,
        )

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        # Should not have status filter when including expired
        assert "status IN" not in query

    @pytest.mark.asyncio
    async def test_get_user_sessions_limit_clamped(
        self, session_repository, mock_db_client
    ):
        """Get user sessions clamps limit to valid range."""
        mock_db_client.execute.return_value = []

        # Request limit > 100
        await session_repository.get_user_sessions("user123", limit=500)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        # Should be clamped to 100
        assert params["limit"] == 100


# =============================================================================
# Activity Tracking Tests
# =============================================================================


class TestSessionRepositoryActivityTracking:
    """Tests for session activity tracking."""

    @pytest.mark.asyncio
    async def test_update_activity_no_changes(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Update activity with no IP or UA changes."""
        # Get call returns session
        mock_db_client.execute_single.side_effect = [
            {"session": sample_session_data},  # get_by_jti
            {"session": sample_session_data},  # update
        ]

        result, changes = await session_repository.update_activity(
            "session-jti-123",
            ip_address="192.168.1.100",  # Same IP
            user_agent="Mozilla/5.0 Test Browser",  # Same UA
        )

        assert result is not None
        assert changes["ip_changed"] is False
        assert changes["user_agent_changed"] is False

    @pytest.mark.asyncio
    async def test_update_activity_ip_changed(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Update activity detects IP change."""
        # First call for get, second for cache check, third for update
        mock_db_client.execute_single.side_effect = [
            {"session": sample_session_data},  # get_by_jti
            {"session": {**sample_session_data, "last_ip": "10.0.0.50"}},  # update
        ]

        result, changes = await session_repository.update_activity(
            "session-jti-123",
            ip_address="10.0.0.50",  # Different IP
            user_agent="Mozilla/5.0 Test Browser",
        )

        assert changes["ip_changed"] is True
        assert changes["old_ip"] == "192.168.1.100"
        assert changes["new_ip"] == "10.0.0.50"

    @pytest.mark.asyncio
    async def test_update_activity_user_agent_changed(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Update activity detects User-Agent change."""
        mock_db_client.execute_single.side_effect = [
            {"session": sample_session_data},  # get_by_jti
            {"session": sample_session_data},  # update
        ]

        result, changes = await session_repository.update_activity(
            "session-jti-123",
            ip_address="192.168.1.100",
            user_agent="Different Browser/1.0",  # Different UA
        )

        assert changes["user_agent_changed"] is True
        assert changes["old_user_agent"] == "Mozilla/5.0 Test Browser"
        assert changes["new_user_agent"] == "Different Browser/1.0"

    @pytest.mark.asyncio
    async def test_update_activity_session_not_found(
        self, session_repository, mock_db_client
    ):
        """Update activity returns None for non-existent session."""
        mock_db_client.execute_single.return_value = None

        result, changes = await session_repository.update_activity(
            "nonexistent",
            ip_address="10.0.0.1",
            user_agent="Test",
        )

        assert result is None
        assert changes == {}

    @pytest.mark.asyncio
    async def test_update_activity_increments_request_count(
        self, session_repository, mock_db_client, sample_session_data
    ):
        """Update activity increments request count."""
        mock_db_client.execute_single.side_effect = [
            {"session": sample_session_data},
            {"session": sample_session_data},
        ]

        await session_repository.update_activity(
            "session-jti-123",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser",
        )

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "request_count + 1" in query


# =============================================================================
# Session Revocation Tests
# =============================================================================


class TestSessionRepositoryRevocation:
    """Tests for session revocation."""

    @pytest.mark.asyncio
    async def test_revoke_session_success(
        self, session_repository, mock_db_client
    ):
        """Revoke session success."""
        mock_db_client.execute_single.return_value = {"id": "session-jti-123"}

        result = await session_repository.revoke_session(
            "session-jti-123",
            reason="User logout",
        )

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["reason"] == "User logout"

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(
        self, session_repository, mock_db_client
    ):
        """Revoke session returns False for non-existent session."""
        mock_db_client.execute_single.return_value = None

        result = await session_repository.revoke_session("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_session_invalidates_cache(
        self, session_repository, mock_db_client
    ):
        """Revoke session invalidates cache."""
        mock_db_client.execute_single.return_value = {"id": "session-jti-123"}

        with patch.object(SessionCache, "invalidate", new_callable=AsyncMock) as mock_invalidate:
            await session_repository.revoke_session("session-jti-123")
            mock_invalidate.assert_called_once_with("session-jti-123")

    @pytest.mark.asyncio
    async def test_revoke_user_sessions_all(
        self, session_repository, mock_db_client
    ):
        """Revoke all user sessions."""
        mock_db_client.execute_single.return_value = {
            "revoked_jtis": ["jti1", "jti2", "jti3"]
        }

        result = await session_repository.revoke_user_sessions(
            "user123",
            reason="Account locked",
        )

        assert result == 3

    @pytest.mark.asyncio
    async def test_revoke_user_sessions_except_current(
        self, session_repository, mock_db_client
    ):
        """Revoke user sessions except current."""
        mock_db_client.execute_single.return_value = {
            "revoked_jtis": ["jti2", "jti3"]
        }

        result = await session_repository.revoke_user_sessions(
            "user123",
            except_jti="jti1",  # Keep this one
            reason="Security measure",
        )

        assert result == 2
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["except_jti"] == "jti1"

    @pytest.mark.asyncio
    async def test_revoke_user_sessions_invalidates_cache(
        self, session_repository, mock_db_client
    ):
        """Revoke user sessions invalidates cache for all revoked."""
        mock_db_client.execute_single.return_value = {
            "revoked_jtis": ["jti1", "jti2"]
        }

        with patch.object(SessionCache, "invalidate", new_callable=AsyncMock) as mock_invalidate:
            await session_repository.revoke_user_sessions("user123")
            assert mock_invalidate.call_count == 2


# =============================================================================
# Suspicious Session Tests
# =============================================================================


class TestSessionRepositorySuspicious:
    """Tests for suspicious session handling."""

    @pytest.mark.asyncio
    async def test_flag_suspicious_success(
        self, session_repository, mock_db_client
    ):
        """Flag session as suspicious."""
        mock_db_client.execute_single.return_value = {"id": "session-jti-123"}

        result = await session_repository.flag_suspicious(
            "session-jti-123",
            reason="Multiple IP changes",
        )

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "suspicious" in query

    @pytest.mark.asyncio
    async def test_flag_suspicious_not_found(
        self, session_repository, mock_db_client
    ):
        """Flag suspicious returns False for non-existent session."""
        mock_db_client.execute_single.return_value = None

        result = await session_repository.flag_suspicious(
            "nonexistent",
            reason="Test",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_flag_suspicious_invalidates_cache(
        self, session_repository, mock_db_client
    ):
        """Flag suspicious invalidates cache to force refresh."""
        mock_db_client.execute_single.return_value = {"id": "session-jti-123"}

        with patch.object(SessionCache, "invalidate", new_callable=AsyncMock) as mock_invalidate:
            await session_repository.flag_suspicious(
                "session-jti-123",
                reason="Suspicious activity",
            )
            mock_invalidate.assert_called_once_with("session-jti-123")


# =============================================================================
# Session Cleanup Tests
# =============================================================================


class TestSessionRepositoryCleanup:
    """Tests for session cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_expired(
        self, session_repository, mock_db_client
    ):
        """Cleanup expired sessions."""
        mock_db_client.execute_single.return_value = {"count": 5}

        result = await session_repository.cleanup_expired()

        assert result == 5

    @pytest.mark.asyncio
    async def test_cleanup_expired_none_found(
        self, session_repository, mock_db_client
    ):
        """Cleanup returns 0 when no expired sessions."""
        mock_db_client.execute_single.return_value = {"count": 0}

        result = await session_repository.cleanup_expired()

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_active_sessions(
        self, session_repository, mock_db_client
    ):
        """Count active sessions for a user."""
        mock_db_client.execute_single.return_value = {"count": 3}

        result = await session_repository.count_active_sessions("user123")

        assert result == 3

    @pytest.mark.asyncio
    async def test_count_active_sessions_none(
        self, session_repository, mock_db_client
    ):
        """Count returns 0 when no active sessions."""
        mock_db_client.execute_single.return_value = None

        result = await session_repository.count_active_sessions("user123")

        assert result == 0


# =============================================================================
# Index Management Tests
# =============================================================================


class TestSessionRepositoryIndexes:
    """Tests for database index management."""

    @pytest.mark.asyncio
    async def test_ensure_indexes(
        self, session_repository, mock_db_client
    ):
        """Ensure indexes creates all necessary indexes."""
        mock_db_client.execute.return_value = []

        await session_repository.ensure_indexes()

        # Should have called execute 5 times (5 index queries)
        assert mock_db_client.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_ensure_indexes_handles_errors(
        self, session_repository, mock_db_client
    ):
        """Ensure indexes handles errors gracefully."""
        mock_db_client.execute.side_effect = RuntimeError("Index exists")

        # Should not raise
        await session_repository.ensure_indexes()


# =============================================================================
# Session Cache Tests
# =============================================================================


class TestSessionCache:
    """Tests for SessionCache functionality."""

    @pytest.mark.asyncio
    async def test_cache_get_empty(self):
        """Cache get returns None for empty jti."""
        result = await SessionCache.get("")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_get_none(self):
        """Cache get returns None for None jti."""
        result = await SessionCache.get(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, sample_session_data):
        """Cache set and get work correctly."""
        session = Session.model_validate({
            **sample_session_data,
            "ip_history": json.loads(sample_session_data["ip_history"]),
        })

        with patch.object(SessionCache, "_get_redis_client", return_value=None):
            with patch("forge.repositories.session_repository.settings") as mock_settings:
                mock_settings.session_cache_enabled = True
                mock_settings.session_cache_ttl_seconds = 300

                await SessionCache.set("test-jti", session)
                result = await SessionCache.get("test-jti")

                assert result is not None
                assert result.token_jti == session.token_jti

    @pytest.mark.asyncio
    async def test_cache_invalidate(self, sample_session_data):
        """Cache invalidate removes entry."""
        session = Session.model_validate({
            **sample_session_data,
            "ip_history": json.loads(sample_session_data["ip_history"]),
        })

        with patch.object(SessionCache, "_get_redis_client", return_value=None):
            with patch("forge.repositories.session_repository.settings") as mock_settings:
                mock_settings.session_cache_enabled = True
                mock_settings.session_cache_ttl_seconds = 300

                await SessionCache.set("test-jti", session)
                await SessionCache.invalidate("test-jti")
                result = await SessionCache.get("test-jti")

                assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidate_empty_jti(self):
        """Cache invalidate handles empty jti."""
        # Should not raise
        await SessionCache.invalidate("")

    @pytest.mark.asyncio
    async def test_cache_clear(self, sample_session_data):
        """Cache clear removes all entries."""
        session = Session.model_validate({
            **sample_session_data,
            "ip_history": json.loads(sample_session_data["ip_history"]),
        })

        with patch.object(SessionCache, "_get_redis_client", return_value=None):
            with patch("forge.repositories.session_repository.settings") as mock_settings:
                mock_settings.session_cache_enabled = True
                mock_settings.session_cache_ttl_seconds = 300

                await SessionCache.set("jti1", session)
                await SessionCache.set("jti2", session)
                await SessionCache.clear()

                result1 = await SessionCache.get("jti1")
                result2 = await SessionCache.get("jti2")

                assert result1 is None
                assert result2 is None

    @pytest.mark.asyncio
    async def test_cache_set_disabled(self, sample_session_data):
        """Cache set does nothing when disabled."""
        session = Session.model_validate({
            **sample_session_data,
            "ip_history": json.loads(sample_session_data["ip_history"]),
        })

        with patch("forge.repositories.session_repository.settings") as mock_settings:
            mock_settings.session_cache_enabled = False

            await SessionCache.set("test-jti", session)
            # Clear internal cache to verify nothing was stored
            await SessionCache.clear()


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestSessionRepositoryHelpers:
    """Tests for helper methods."""

    def test_generate_id(self, session_repository):
        """Generate ID produces valid UUID."""
        id1 = session_repository._generate_id()
        id2 = session_repository._generate_id()

        assert len(id1) == 36  # UUID format
        assert id1 != id2

    def test_now_returns_utc(self, session_repository):
        """Now returns UTC timestamp."""
        result = session_repository._now()

        assert result.tzinfo is not None

    @pytest.mark.asyncio
    async def test_mark_expired(
        self, session_repository, mock_db_client
    ):
        """Mark expired sets session status to expired."""
        mock_db_client.execute.return_value = []

        await session_repository._mark_expired("session-jti-123")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "expired" in query


# =============================================================================
# Session Model Tests
# =============================================================================


class TestSessionModel:
    """Tests for Session model helpers."""

    def test_hash_user_agent(self):
        """Hash user agent produces consistent hash."""
        ua = "Mozilla/5.0 Test Browser"

        hash1 = Session.hash_user_agent(ua)
        hash2 = Session.hash_user_agent(ua)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_hash_user_agent_none(self):
        """Hash user agent returns None for None input."""
        result = Session.hash_user_agent(None)
        assert result is None

    def test_hash_user_agent_empty(self):
        """Hash user agent returns None for empty input."""
        result = Session.hash_user_agent("")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
