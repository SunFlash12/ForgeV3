"""
Session Model Tests for Forge Cascade V2

Comprehensive tests for session models including:
- SessionBindingMode and SessionStatus enums
- SessionCreate and SessionUpdate models
- Session model with validators and properties
- SessionInDB model
- SessionPublic model with IP masking
- SessionListResponse model
- SessionBindingWarning model
- SessionRevokeRequest and SessionRevokeAllRequest models
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from forge.models.session import (
    Session,
    SessionBindingMode,
    SessionBindingWarning,
    SessionCreate,
    SessionInDB,
    SessionListResponse,
    SessionPublic,
    SessionRevokeAllRequest,
    SessionRevokeRequest,
    SessionStatus,
    SessionUpdate,
)

# =============================================================================
# SessionBindingMode Enum Tests
# =============================================================================


class TestSessionBindingMode:
    """Tests for SessionBindingMode enum."""

    def test_binding_mode_values(self):
        """SessionBindingMode has expected values."""
        assert SessionBindingMode.DISABLED.value == "disabled"
        assert SessionBindingMode.LOG_ONLY.value == "log_only"
        assert SessionBindingMode.WARN.value == "warn"
        assert SessionBindingMode.FLEXIBLE.value == "flexible"
        assert SessionBindingMode.STRICT.value == "strict"

    def test_binding_mode_count(self):
        """SessionBindingMode has exactly five modes."""
        assert len(SessionBindingMode) == 5

    def test_binding_mode_from_string(self):
        """Binding mode can be created from string values."""
        assert SessionBindingMode("disabled") == SessionBindingMode.DISABLED
        assert SessionBindingMode("strict") == SessionBindingMode.STRICT

    def test_binding_mode_invalid(self):
        """Invalid binding mode string raises ValueError."""
        with pytest.raises(ValueError):
            SessionBindingMode("invalid_mode")


# =============================================================================
# SessionStatus Enum Tests
# =============================================================================


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_status_values(self):
        """SessionStatus has expected values."""
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.EXPIRED.value == "expired"
        assert SessionStatus.REVOKED.value == "revoked"
        assert SessionStatus.SUSPICIOUS.value == "suspicious"

    def test_status_count(self):
        """SessionStatus has exactly four statuses."""
        assert len(SessionStatus) == 4

    def test_status_from_string(self):
        """Status can be created from string values."""
        assert SessionStatus("active") == SessionStatus.ACTIVE
        assert SessionStatus("revoked") == SessionStatus.REVOKED


# =============================================================================
# SessionCreate Tests
# =============================================================================


class TestSessionCreate:
    """Tests for SessionCreate model."""

    def test_valid_session_create(self):
        """Valid session creation."""
        expires = datetime.now(UTC) + timedelta(hours=1)
        session = SessionCreate(
            user_id="user123",
            token_jti="jti-abc-123",
            ip_address="192.168.1.1",
            expires_at=expires,
        )
        assert session.user_id == "user123"
        assert session.token_jti == "jti-abc-123"
        assert session.ip_address == "192.168.1.1"
        assert session.expires_at == expires

    def test_session_create_defaults(self):
        """Session create has default token_type."""
        expires = datetime.now(UTC) + timedelta(hours=1)
        session = SessionCreate(
            user_id="user123",
            token_jti="jti-abc-123",
            ip_address="192.168.1.1",
            expires_at=expires,
        )
        assert session.token_type == "access"
        assert session.user_agent is None

    def test_session_create_with_user_agent(self):
        """Session create with user agent."""
        expires = datetime.now(UTC) + timedelta(hours=1)
        session = SessionCreate(
            user_id="user123",
            token_jti="jti-abc-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            expires_at=expires,
        )
        assert session.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    def test_session_create_refresh_token(self):
        """Session create for refresh token."""
        expires = datetime.now(UTC) + timedelta(days=7)
        session = SessionCreate(
            user_id="user123",
            token_jti="refresh-jti-456",
            token_type="refresh",
            ip_address="10.0.0.1",
            expires_at=expires,
        )
        assert session.token_type == "refresh"

    def test_session_create_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            SessionCreate(
                user_id="user123",
                token_jti="jti",
                # Missing ip_address and expires_at
            )


# =============================================================================
# SessionUpdate Tests
# =============================================================================


class TestSessionUpdate:
    """Tests for SessionUpdate model."""

    def test_all_fields_optional(self):
        """All fields in SessionUpdate are optional."""
        update = SessionUpdate()
        assert update.last_ip is None
        assert update.last_user_agent is None
        assert update.last_activity is None
        assert update.request_count is None
        assert update.ip_change_count is None
        assert update.user_agent_change_count is None
        assert update.ip_history is None
        assert update.status is None
        assert update.revoked_at is None
        assert update.revoked_reason is None

    def test_partial_update(self):
        """Can update individual fields."""
        now = datetime.now(UTC)
        update = SessionUpdate(
            last_ip="192.168.1.100",
            last_activity=now,
            request_count=50,
        )
        assert update.last_ip == "192.168.1.100"
        assert update.last_activity == now
        assert update.request_count == 50

    def test_update_status(self):
        """Can update session status."""
        update = SessionUpdate(status=SessionStatus.SUSPICIOUS)
        assert update.status == SessionStatus.SUSPICIOUS

    def test_update_revocation(self):
        """Can update revocation fields."""
        now = datetime.now(UTC)
        update = SessionUpdate(
            status=SessionStatus.REVOKED,
            revoked_at=now,
            revoked_reason="Security concern",
        )
        assert update.status == SessionStatus.REVOKED
        assert update.revoked_at == now
        assert update.revoked_reason == "Security concern"

    def test_update_ip_history(self):
        """Can update IP history."""
        history: list[dict[str, Any]] = [
            {"ip": "192.168.1.1", "timestamp": "2024-01-01T00:00:00Z"},
            {"ip": "192.168.1.2", "timestamp": "2024-01-01T01:00:00Z"},
        ]
        update = SessionUpdate(ip_history=history)
        assert len(update.ip_history) == 2


# =============================================================================
# Session Tests
# =============================================================================


class TestSession:
    """Tests for Session model."""

    def test_valid_session(self):
        """Valid session creation."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            created_at=now,
            updated_at=now,
        )
        assert session.id == "session123"
        assert session.user_id == "user123"
        assert session.initial_ip == "192.168.1.1"
        assert session.last_ip == "192.168.1.1"

    def test_session_defaults(self):
        """Session has sensible defaults."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            created_at=now,
            updated_at=now,
        )
        assert session.token_type == "access"
        assert session.initial_user_agent is None
        assert session.initial_user_agent_hash is None
        assert session.last_user_agent is None
        assert session.last_user_agent_hash is None
        assert session.request_count == 1
        assert session.ip_change_count == 0
        assert session.user_agent_change_count == 0
        assert session.ip_history == []
        assert session.status == SessionStatus.ACTIVE
        assert session.revoked_at is None
        assert session.revoked_reason is None

    def test_session_with_user_agent(self):
        """Session with user agent tracking."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
        ua_hash = Session.hash_user_agent(ua)

        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            initial_user_agent=ua,
            initial_user_agent_hash=ua_hash,
            last_ip="192.168.1.1",
            last_user_agent=ua,
            last_user_agent_hash=ua_hash,
            last_activity=now,
            expires_at=expires,
            created_at=now,
            updated_at=now,
        )
        assert session.initial_user_agent == ua
        assert session.initial_user_agent_hash is not None
        assert len(session.initial_user_agent_hash) == 64  # SHA-256 hex

    def test_session_request_count_min(self):
        """Request count has minimum value."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        with pytest.raises(ValidationError):
            Session(
                id="session123",
                user_id="user123",
                token_jti="jti-abc-123",
                initial_ip="192.168.1.1",
                last_ip="192.168.1.1",
                last_activity=now,
                expires_at=expires,
                request_count=-1,
                created_at=now,
                updated_at=now,
            )

    def test_session_ip_change_count_min(self):
        """IP change count has minimum value."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        with pytest.raises(ValidationError):
            Session(
                id="session123",
                user_id="user123",
                token_jti="jti-abc-123",
                initial_ip="192.168.1.1",
                last_ip="192.168.1.1",
                last_activity=now,
                expires_at=expires,
                ip_change_count=-1,
                created_at=now,
                updated_at=now,
            )

    def test_session_ip_history_with_entries(self):
        """Session with IP history entries."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        history: list[dict[str, Any]] = [
            {"ip": "192.168.1.2", "timestamp": now.isoformat(), "geo": "US"},
            {"ip": "10.0.0.1", "timestamp": (now - timedelta(hours=1)).isoformat()},
        ]
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.2",
            last_activity=now,
            expires_at=expires,
            ip_history=history,
            ip_change_count=2,
            created_at=now,
            updated_at=now,
        )
        assert len(session.ip_history) == 2
        assert session.ip_history[0]["ip"] == "192.168.1.2"

    def test_validate_ip_history_none(self):
        """IP history validator converts None to empty list."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            ip_history=None,
            created_at=now,
            updated_at=now,
        )
        assert session.ip_history == []

    def test_hash_user_agent(self):
        """hash_user_agent produces consistent SHA-256 hash."""
        ua = "Mozilla/5.0 Test Browser"
        hash1 = Session.hash_user_agent(ua)
        hash2 = Session.hash_user_agent(ua)

        assert hash1 == hash2
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_hash_user_agent_none(self):
        """hash_user_agent returns None for None input."""
        assert Session.hash_user_agent(None) is None

    def test_hash_user_agent_empty(self):
        """hash_user_agent returns None for empty string."""
        assert Session.hash_user_agent("") is None

    def test_is_active_property_active(self):
        """is_active returns True for active, non-expired session."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert session.is_active is True

    def test_is_active_property_expired_status(self):
        """is_active returns False for expired status."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.EXPIRED,
            created_at=now,
            updated_at=now,
        )
        assert session.is_active is False

    def test_is_active_property_revoked_status(self):
        """is_active returns False for revoked status."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.REVOKED,
            created_at=now,
            updated_at=now,
        )
        assert session.is_active is False

    def test_is_active_property_past_expiry(self):
        """is_active returns False when expires_at is in the past."""
        now = datetime.now(UTC)
        expires = now - timedelta(hours=1)  # Already expired
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.ACTIVE,
            created_at=now - timedelta(hours=2),
            updated_at=now,
        )
        assert session.is_active is False

    def test_is_suspicious_property_true(self):
        """is_suspicious returns True for suspicious status."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.SUSPICIOUS,
            created_at=now,
            updated_at=now,
        )
        assert session.is_suspicious is True

    def test_is_suspicious_property_false(self):
        """is_suspicious returns False for active status."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = Session(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert session.is_suspicious is False


# =============================================================================
# SessionInDB Tests
# =============================================================================


class TestSessionInDB:
    """Tests for SessionInDB model."""

    def test_session_in_db_inherits_session(self):
        """SessionInDB inherits all Session fields."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        session = SessionInDB(
            id="session123",
            user_id="user123",
            token_jti="jti-abc-123",
            initial_ip="192.168.1.1",
            last_ip="192.168.1.1",
            last_activity=now,
            expires_at=expires,
            created_at=now,
            updated_at=now,
        )
        assert session.id == "session123"
        assert session.is_active is True


# =============================================================================
# SessionPublic Tests
# =============================================================================


class TestSessionPublic:
    """Tests for SessionPublic model."""

    def test_valid_session_public(self):
        """Valid public session creation."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        public = SessionPublic(
            id="session123",
            token_type="access",
            initial_ip="192.***.***.1",
            last_ip="192.***.***.1",
            last_activity=now,
            request_count=50,
            ip_change_count=2,
            user_agent_change_count=0,
            status=SessionStatus.ACTIVE,
            expires_at=expires,
            created_at=now,
        )
        assert public.id == "session123"
        assert public.is_current is False  # Default

    def test_session_public_is_current(self):
        """SessionPublic can mark current session."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        public = SessionPublic(
            id="session123",
            token_type="access",
            initial_ip="192.***.***.1",
            last_ip="192.***.***.1",
            last_activity=now,
            request_count=50,
            ip_change_count=0,
            user_agent_change_count=0,
            status=SessionStatus.ACTIVE,
            expires_at=expires,
            created_at=now,
            is_current=True,
        )
        assert public.is_current is True

    def test_mask_ip_ipv4(self):
        """mask_ip correctly masks IPv4 addresses."""
        masked = SessionPublic.mask_ip("192.168.1.100")
        assert masked == "192.***.***.100"

    def test_mask_ip_ipv4_different(self):
        """mask_ip works with different IPv4 addresses."""
        masked = SessionPublic.mask_ip("10.0.0.1")
        assert masked == "10.***.***.1"

        masked = SessionPublic.mask_ip("172.16.254.1")
        assert masked == "172.***.***.1"

    def test_mask_ip_ipv6(self):
        """mask_ip truncates IPv6 addresses."""
        masked = SessionPublic.mask_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert masked == "2001:0...7334"

    def test_mask_ip_short_string(self):
        """mask_ip returns short strings unchanged."""
        masked = SessionPublic.mask_ip("localhost")
        assert masked == "localhost"

        masked = SessionPublic.mask_ip("1.2.3.4")
        assert masked == "1.***.***.4"


# =============================================================================
# SessionListResponse Tests
# =============================================================================


class TestSessionListResponse:
    """Tests for SessionListResponse model."""

    def test_empty_session_list(self):
        """Empty session list response."""
        response = SessionListResponse()
        assert response.sessions == []
        assert response.total == 0
        assert response.current_session_id is None

    def test_session_list_with_sessions(self):
        """Session list with sessions."""
        now = datetime.now(UTC)
        expires = now + timedelta(hours=1)
        public_session = SessionPublic(
            id="session123",
            token_type="access",
            initial_ip="192.***.***.1",
            last_ip="192.***.***.1",
            last_activity=now,
            request_count=10,
            ip_change_count=0,
            user_agent_change_count=0,
            status=SessionStatus.ACTIVE,
            expires_at=expires,
            created_at=now,
            is_current=True,
        )
        response = SessionListResponse(
            sessions=[public_session],
            total=1,
            current_session_id="session123",
        )
        assert len(response.sessions) == 1
        assert response.total == 1
        assert response.current_session_id == "session123"


# =============================================================================
# SessionBindingWarning Tests
# =============================================================================


class TestSessionBindingWarning:
    """Tests for SessionBindingWarning model."""

    def test_valid_binding_warning(self):
        """Valid session binding warning."""
        warning = SessionBindingWarning(
            session_id="session123",
            user_id="user123",
            warning_type="ip_change",
            old_value="192.168.1.1",
            new_value="10.0.0.1",
            binding_mode=SessionBindingMode.WARN,
            request_count=100,
        )
        assert warning.session_id == "session123"
        assert warning.warning_type == "ip_change"
        assert warning.old_value == "192.168.1.1"
        assert warning.new_value == "10.0.0.1"

    def test_binding_warning_defaults(self):
        """Binding warning has sensible defaults."""
        warning = SessionBindingWarning(
            session_id="session123",
            user_id="user123",
            warning_type="user_agent_change",
            old_value="Browser A",
            new_value="Browser B",
            binding_mode=SessionBindingMode.LOG_ONLY,
            request_count=50,
        )
        assert warning.timestamp is not None
        assert warning.additional_info == {}

    def test_binding_warning_with_additional_info(self):
        """Binding warning with additional info."""
        additional: dict[str, Any] = {
            "geo_old": {"country": "US", "city": "New York"},
            "geo_new": {"country": "RU", "city": "Moscow"},
            "risk_score": 0.95,
        }
        warning = SessionBindingWarning(
            session_id="session123",
            user_id="user123",
            warning_type="suspicious",
            old_value=None,
            new_value=None,
            binding_mode=SessionBindingMode.STRICT,
            request_count=200,
            additional_info=additional,
        )
        assert warning.additional_info["risk_score"] == 0.95
        assert warning.additional_info["geo_new"]["country"] == "RU"

    def test_binding_warning_null_values(self):
        """Binding warning with null old/new values."""
        warning = SessionBindingWarning(
            session_id="session123",
            user_id="user123",
            warning_type="suspicious",
            old_value=None,
            new_value=None,
            binding_mode=SessionBindingMode.FLEXIBLE,
            request_count=75,
        )
        assert warning.old_value is None
        assert warning.new_value is None


# =============================================================================
# SessionRevokeRequest Tests
# =============================================================================


class TestSessionRevokeRequest:
    """Tests for SessionRevokeRequest model."""

    def test_revoke_request_no_reason(self):
        """Revoke request without reason."""
        request = SessionRevokeRequest()
        assert request.reason is None

    def test_revoke_request_with_reason(self):
        """Revoke request with reason."""
        request = SessionRevokeRequest(reason="User requested logout")
        assert request.reason == "User requested logout"

    def test_revoke_request_reason_max_length(self):
        """Reason has maximum length constraint."""
        with pytest.raises(ValidationError):
            SessionRevokeRequest(reason="a" * 501)

    def test_revoke_request_reason_at_max_length(self):
        """Reason at exactly max length is valid."""
        request = SessionRevokeRequest(reason="a" * 500)
        assert len(request.reason) == 500


# =============================================================================
# SessionRevokeAllRequest Tests
# =============================================================================


class TestSessionRevokeAllRequest:
    """Tests for SessionRevokeAllRequest model."""

    def test_revoke_all_defaults(self):
        """Revoke all request has sensible defaults."""
        request = SessionRevokeAllRequest()
        assert request.except_current is True
        assert request.reason is None

    def test_revoke_all_include_current(self):
        """Revoke all including current session."""
        request = SessionRevokeAllRequest(except_current=False)
        assert request.except_current is False

    def test_revoke_all_with_reason(self):
        """Revoke all with reason."""
        request = SessionRevokeAllRequest(
            except_current=True,
            reason="Security audit - revoking all old sessions",
        )
        assert request.reason == "Security audit - revoking all old sessions"

    def test_revoke_all_reason_max_length(self):
        """Reason has maximum length constraint."""
        with pytest.raises(ValidationError):
            SessionRevokeAllRequest(reason="a" * 501)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
