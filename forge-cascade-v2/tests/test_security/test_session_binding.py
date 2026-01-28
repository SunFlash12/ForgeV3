"""
Comprehensive Tests for Session Binding Module

Tests for session binding service that tracks IP and User-Agent changes
for security monitoring and suspicious activity detection.

SECURITY FIX (Audit 6 - Session 2): Testing session binding validation mechanisms.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_session_repository():
    """Create a mock session repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update_activity = AsyncMock()
    repo.get_user_sessions = AsyncMock(return_value=[])
    repo.get_by_jti = AsyncMock()
    repo.revoke_session = AsyncMock()
    repo.revoke_user_sessions = AsyncMock()
    repo.count_active_sessions = AsyncMock(return_value=0)
    repo.flag_suspicious = AsyncMock()
    return repo


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.session_ip_binding_mode = "warn"
    settings.session_user_agent_binding_mode = "warn"
    settings.session_ip_change_threshold = 3
    return settings


@pytest.fixture
def session_binding_service(mock_session_repository, mock_settings):
    """Create a SessionBindingService with mocked dependencies."""
    with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
        from forge.security.session_binding import SessionBindingService

        return SessionBindingService(mock_session_repository)


class TestSessionBindingServiceInit:
    """Tests for SessionBindingService initialization."""

    def test_init_with_repository(self, mock_session_repository, mock_settings):
        """Service initializes with repository."""
        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)
            assert service._repo is mock_session_repository

    def test_init_loads_binding_modes(self, mock_session_repository, mock_settings):
        """Service loads binding modes from settings."""
        mock_settings.session_ip_binding_mode = "strict"
        mock_settings.session_user_agent_binding_mode = "flexible"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import SessionBindingMode
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)
            assert service._ip_binding_mode == SessionBindingMode.STRICT
            assert service._ua_binding_mode == SessionBindingMode.FLEXIBLE

    def test_init_loads_ip_change_threshold(self, mock_session_repository, mock_settings):
        """Service loads IP change threshold from settings."""
        mock_settings.session_ip_change_threshold = 5

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)
            assert service._ip_change_threshold == 5


class TestCreateSession:
    """Tests for create_session method."""

    @pytest.mark.asyncio
    async def test_create_session_returns_session(
        self, session_binding_service, mock_session_repository
    ):
        """create_session returns created session."""
        from forge.models.session import Session, SessionStatus

        expected_session = Session(
            id="session-123",
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent="Mozilla/5.0",
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )
        mock_session_repository.create.return_value = expected_session

        result = await session_binding_service.create_session(
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        assert result == expected_session
        mock_session_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_passes_correct_data(
        self, session_binding_service, mock_session_repository
    ):
        """create_session passes correct data to repository."""
        from forge.models.session import Session, SessionStatus

        mock_session_repository.create.return_value = Session(
            id="session-123",
            user_id="user-456",
            token_jti="jti-789",
            token_type="refresh",
            initial_ip="10.0.0.1",
            initial_user_agent="Chrome",
            last_ip="10.0.0.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )

        expires = datetime.now(UTC) + timedelta(hours=24)

        await session_binding_service.create_session(
            user_id="user-456",
            token_jti="jti-789",
            token_type="refresh",
            ip_address="10.0.0.1",
            user_agent="Chrome",
            expires_at=expires,
        )

        call_args = mock_session_repository.create.call_args[0][0]
        assert call_args.user_id == "user-456"
        assert call_args.token_jti == "jti-789"
        assert call_args.token_type == "refresh"
        assert call_args.ip_address == "10.0.0.1"
        assert call_args.user_agent == "Chrome"

    @pytest.mark.asyncio
    async def test_create_session_with_none_user_agent(
        self, session_binding_service, mock_session_repository
    ):
        """create_session handles None user agent."""
        from forge.models.session import Session, SessionStatus

        mock_session_repository.create.return_value = Session(
            id="session-123",
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent=None,
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )

        result = await session_binding_service.create_session(
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            ip_address="192.168.1.1",
            user_agent=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        assert result is not None


class TestValidateAndUpdate:
    """Tests for validate_and_update method."""

    @pytest.mark.asyncio
    async def test_session_not_found_returns_allowed(
        self, session_binding_service, mock_session_repository
    ):
        """Session not found returns allowed for backwards compatibility."""
        mock_session_repository.update_activity.return_value = (None, {})

        is_allowed, session, reason = await session_binding_service.validate_and_update(
            token_jti="unknown-jti",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert is_allowed is True
        assert session is None
        assert reason is None

    @pytest.mark.asyncio
    async def test_revoked_session_returns_blocked(
        self, session_binding_service, mock_session_repository
    ):
        """Revoked session returns blocked."""
        from forge.models.session import Session, SessionStatus

        revoked_session = Session(
            id="session-123",
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent="Mozilla/5.0",
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.REVOKED,
        )
        mock_session_repository.update_activity.return_value = (revoked_session, {})

        is_allowed, session, reason = await session_binding_service.validate_and_update(
            token_jti="jti-789",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert is_allowed is False
        assert session == revoked_session
        assert "revoked" in reason.lower()

    @pytest.mark.asyncio
    async def test_active_session_no_changes_returns_allowed(
        self, session_binding_service, mock_session_repository
    ):
        """Active session with no changes returns allowed."""
        from forge.models.session import Session, SessionStatus

        active_session = Session(
            id="session-123",
            user_id="user-456",
            token_jti="jti-789",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent="Mozilla/5.0",
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )
        mock_session_repository.update_activity.return_value = (active_session, {})

        is_allowed, session, reason = await session_binding_service.validate_and_update(
            token_jti="jti-789",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert is_allowed is True
        assert session == active_session
        assert reason is None


class TestIPChangeHandling:
    """Tests for IP change handling based on binding mode."""

    @pytest.mark.asyncio
    async def test_ip_change_disabled_mode_allows(self, mock_session_repository, mock_settings):
        """IP change with disabled mode allows access."""
        mock_settings.session_ip_binding_mode = "disabled"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=0,
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_ip_change_log_only_mode_allows(self, mock_session_repository, mock_settings):
        """IP change with log_only mode allows access."""
        mock_settings.session_ip_binding_mode = "log_only"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=1,
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_ip_change_warn_mode_allows_and_flags(
        self, mock_session_repository, mock_settings
    ):
        """IP change with warn mode allows but flags when threshold exceeded."""
        mock_settings.session_ip_binding_mode = "warn"
        mock_settings.session_ip_change_threshold = 2

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=3,  # Exceeds threshold
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is True
            mock_session_repository.flag_suspicious.assert_called_once()

    @pytest.mark.asyncio
    async def test_ip_change_flexible_mode_blocks_on_threshold(
        self, mock_session_repository, mock_settings
    ):
        """IP change with flexible mode blocks when threshold exceeded."""
        mock_settings.session_ip_binding_mode = "flexible"
        mock_settings.session_ip_change_threshold = 2

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=3,  # Exceeds threshold
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is False
            assert "IP changes" in reason

    @pytest.mark.asyncio
    async def test_ip_change_flexible_mode_allows_under_threshold(
        self, mock_session_repository, mock_settings
    ):
        """IP change with flexible mode allows under threshold."""
        mock_settings.session_ip_binding_mode = "flexible"
        mock_settings.session_ip_change_threshold = 5

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=2,  # Under threshold
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_ip_change_strict_mode_blocks_any_change(
        self, mock_session_repository, mock_settings
    ):
        """IP change with strict mode blocks any change."""
        mock_settings.session_ip_binding_mode = "strict"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                ip_change_count=1,
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {"ip_changed": True, "old_ip": "192.168.1.1", "new_ip": "10.0.0.1"},
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="10.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert is_allowed is False
            assert "IP address change not allowed" in reason
            mock_session_repository.flag_suspicious.assert_called_once()


class TestUserAgentChangeHandling:
    """Tests for User-Agent change handling based on binding mode."""

    @pytest.mark.asyncio
    async def test_ua_change_disabled_mode_allows(self, mock_session_repository, mock_settings):
        """UA change with disabled mode allows access."""
        mock_settings.session_user_agent_binding_mode = "disabled"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                user_agent_change_count=0,
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {
                    "user_agent_changed": True,
                    "old_user_agent": "Mozilla/5.0",
                    "new_user_agent": "Chrome/120.0",
                },
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="192.168.1.1",
                user_agent="Chrome/120.0",
            )

            assert is_allowed is True

    @pytest.mark.asyncio
    async def test_ua_change_strict_mode_blocks(self, mock_session_repository, mock_settings):
        """UA change with strict mode blocks access."""
        mock_settings.session_user_agent_binding_mode = "strict"
        mock_settings.session_ip_binding_mode = "disabled"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                user_agent_change_count=1,
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {
                    "user_agent_changed": True,
                    "old_user_agent": "Mozilla/5.0",
                    "new_user_agent": "Chrome/120.0",
                },
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="192.168.1.1",
                user_agent="Chrome/120.0",
            )

            assert is_allowed is False
            assert "User-Agent change not allowed" in reason

    @pytest.mark.asyncio
    async def test_ua_change_flexible_mode_flags_high_count(
        self, mock_session_repository, mock_settings
    ):
        """UA change with flexible mode flags suspicious activity at high count."""
        mock_settings.session_user_agent_binding_mode = "flexible"
        mock_settings.session_ip_binding_mode = "disabled"

        with patch("forge.security.session_binding.get_settings", return_value=mock_settings):
            from forge.models.session import Session, SessionStatus
            from forge.security.session_binding import SessionBindingService

            service = SessionBindingService(mock_session_repository)

            active_session = Session(
                id="session-123",
                user_id="user-456",
                token_jti="jti-789",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
                user_agent_change_count=6,  # >= 5 triggers flag
            )
            mock_session_repository.update_activity.return_value = (
                active_session,
                {
                    "user_agent_changed": True,
                    "old_user_agent": "Mozilla/5.0",
                    "new_user_agent": "Chrome/120.0",
                },
            )

            is_allowed, session, reason = await service.validate_and_update(
                token_jti="jti-789",
                ip_address="192.168.1.1",
                user_agent="Chrome/120.0",
            )

            assert is_allowed is True  # Flexible mode allows
            mock_session_repository.flag_suspicious.assert_called_once()


class TestGetUserSessions:
    """Tests for get_user_sessions method."""

    @pytest.mark.asyncio
    async def test_get_user_sessions_returns_response(
        self, session_binding_service, mock_session_repository
    ):
        """get_user_sessions returns SessionListResponse."""
        from forge.models.session import Session, SessionListResponse, SessionStatus

        sessions = [
            Session(
                id="session-1",
                user_id="user-456",
                token_jti="jti-1",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
            ),
            Session(
                id="session-2",
                user_id="user-456",
                token_jti="jti-2",
                token_type="access",
                initial_ip="10.0.0.1",
                initial_user_agent="Chrome",
                last_ip="10.0.0.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
            ),
        ]
        mock_session_repository.get_user_sessions.return_value = sessions

        result = await session_binding_service.get_user_sessions("user-456")

        assert isinstance(result, SessionListResponse)
        assert result.total == 2
        assert len(result.sessions) == 2

    @pytest.mark.asyncio
    async def test_get_user_sessions_marks_current(
        self, session_binding_service, mock_session_repository
    ):
        """get_user_sessions marks current session."""
        from forge.models.session import Session, SessionStatus

        sessions = [
            Session(
                id="session-1",
                user_id="user-456",
                token_jti="current-jti",
                token_type="access",
                initial_ip="192.168.1.1",
                initial_user_agent="Mozilla/5.0",
                last_ip="192.168.1.1",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
            ),
        ]
        mock_session_repository.get_user_sessions.return_value = sessions

        result = await session_binding_service.get_user_sessions(
            "user-456", current_jti="current-jti"
        )

        assert result.sessions[0].is_current is True

    @pytest.mark.asyncio
    async def test_get_user_sessions_masks_ips(
        self, session_binding_service, mock_session_repository
    ):
        """get_user_sessions masks IP addresses for privacy."""
        from forge.models.session import Session, SessionStatus

        sessions = [
            Session(
                id="session-1",
                user_id="user-456",
                token_jti="jti-1",
                token_type="access",
                initial_ip="192.168.1.100",
                initial_user_agent="Mozilla/5.0",
                last_ip="10.20.30.40",
                last_activity=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                status=SessionStatus.ACTIVE,
            ),
        ]
        mock_session_repository.get_user_sessions.return_value = sessions

        result = await session_binding_service.get_user_sessions("user-456")

        # IPs should be masked (e.g., "192.***.***.100")
        assert "***" in result.sessions[0].initial_ip
        assert "***" in result.sessions[0].last_ip


class TestRevokeSession:
    """Tests for revoke_session method."""

    @pytest.mark.asyncio
    async def test_revoke_session_success(self, session_binding_service, mock_session_repository):
        """revoke_session returns True on success."""
        from forge.models.session import Session, SessionStatus

        session = Session(
            id="session-1",
            user_id="user-456",
            token_jti="jti-to-revoke",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent="Mozilla/5.0",
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )
        mock_session_repository.get_by_jti.return_value = session
        mock_session_repository.revoke_session.return_value = True

        result = await session_binding_service.revoke_session(
            user_id="user-456", session_jti="jti-to-revoke", reason="User requested"
        )

        assert result is True
        mock_session_repository.revoke_session.assert_called_once_with(
            "jti-to-revoke", "User requested"
        )

    @pytest.mark.asyncio
    async def test_revoke_session_fails_wrong_user(
        self, session_binding_service, mock_session_repository
    ):
        """revoke_session fails if session belongs to different user."""
        from forge.models.session import Session, SessionStatus

        session = Session(
            id="session-1",
            user_id="other-user",  # Different user
            token_jti="jti-to-revoke",
            token_type="access",
            initial_ip="192.168.1.1",
            initial_user_agent="Mozilla/5.0",
            last_ip="192.168.1.1",
            last_activity=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            status=SessionStatus.ACTIVE,
        )
        mock_session_repository.get_by_jti.return_value = session

        result = await session_binding_service.revoke_session(
            user_id="user-456", session_jti="jti-to-revoke"
        )

        assert result is False
        mock_session_repository.revoke_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_session_fails_not_found(
        self, session_binding_service, mock_session_repository
    ):
        """revoke_session fails if session not found."""
        mock_session_repository.get_by_jti.return_value = None

        result = await session_binding_service.revoke_session(
            user_id="user-456", session_jti="nonexistent-jti"
        )

        assert result is False


class TestRevokeAllSessions:
    """Tests for revoke_all_sessions method."""

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_returns_count(
        self, session_binding_service, mock_session_repository
    ):
        """revoke_all_sessions returns number of revoked sessions."""
        mock_session_repository.revoke_user_sessions.return_value = 5

        result = await session_binding_service.revoke_all_sessions(
            user_id="user-456", reason="Security breach"
        )

        assert result == 5

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_except_current(
        self, session_binding_service, mock_session_repository
    ):
        """revoke_all_sessions can exclude current session."""
        mock_session_repository.revoke_user_sessions.return_value = 3

        result = await session_binding_service.revoke_all_sessions(
            user_id="user-456", except_current_jti="keep-this-jti", reason="Password changed"
        )

        assert result == 3
        mock_session_repository.revoke_user_sessions.assert_called_once_with(
            "user-456", "keep-this-jti", "Password changed"
        )


class TestGetActiveSessionCount:
    """Tests for get_active_session_count method."""

    @pytest.mark.asyncio
    async def test_get_active_session_count(self, session_binding_service, mock_session_repository):
        """get_active_session_count returns correct count."""
        mock_session_repository.count_active_sessions.return_value = 7

        result = await session_binding_service.get_active_session_count("user-456")

        assert result == 7
        mock_session_repository.count_active_sessions.assert_called_once_with("user-456")


class TestSessionBindingModeEnum:
    """Tests for SessionBindingMode enum."""

    def test_all_binding_modes_exist(self):
        """All binding modes are defined."""
        from forge.models.session import SessionBindingMode

        assert SessionBindingMode.DISABLED.value == "disabled"
        assert SessionBindingMode.LOG_ONLY.value == "log_only"
        assert SessionBindingMode.WARN.value == "warn"
        assert SessionBindingMode.FLEXIBLE.value == "flexible"
        assert SessionBindingMode.STRICT.value == "strict"


class TestSessionStatusEnum:
    """Tests for SessionStatus enum."""

    def test_all_session_statuses_exist(self):
        """All session statuses are defined."""
        from forge.models.session import SessionStatus

        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.EXPIRED.value == "expired"
        assert SessionStatus.REVOKED.value == "revoked"
        assert SessionStatus.SUSPICIOUS.value == "suspicious"


class TestSessionPublicMaskIP:
    """Tests for SessionPublic.mask_ip method."""

    def test_mask_ipv4_address(self):
        """IPv4 address is properly masked."""
        from forge.models.session import SessionPublic

        masked = SessionPublic.mask_ip("192.168.1.100")
        assert masked == "192.***.***.100"

    def test_mask_short_ip(self):
        """Short IP address is not modified."""
        from forge.models.session import SessionPublic

        masked = SessionPublic.mask_ip("10.0.0.1")
        assert masked == "10.***.***.1"

    def test_mask_ipv6_or_long(self):
        """IPv6 or long address is truncated."""
        from forge.models.session import SessionPublic

        masked = SessionPublic.mask_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert "..." in masked
        assert len(masked) < len("2001:0db8:85a3:0000:0000:8a2e:0370:7334")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
