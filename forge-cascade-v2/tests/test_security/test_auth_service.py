"""
Authentication Service Tests for Forge Cascade V2

Comprehensive tests for the AuthService including:
- User registration
- Login/logout flows
- Token operations
- Password management
- Account lockout and IP rate limiting
- Trust management
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib
import pytest

from forge.models.user import AuthProvider, Token, User, UserCreate, UserInDB, UserRole
from forge.security.auth_service import (
    AccountDeactivatedError,
    AccountLockedError,
    AuthenticationError,
    AuthService,
    InvalidCredentialsError,
    IPRateLimitExceededError,
    IPRateLimiter,
    RegistrationError,
)


# =============================================================================
# IP Rate Limiter Tests
# =============================================================================


class TestIPRateLimiter:
    """Tests for IP-based rate limiting."""

    def test_initial_request_allowed(self):
        """First request from an IP should be allowed."""
        limiter = IPRateLimiter()
        is_allowed, seconds_remaining = limiter.check_rate_limit("192.168.1.1")
        assert is_allowed is True
        assert seconds_remaining == 0

    def test_empty_ip_allowed(self):
        """Empty/None IP should be allowed (can't rate limit)."""
        limiter = IPRateLimiter()
        is_allowed, _ = limiter.check_rate_limit("")
        assert is_allowed is True

        is_allowed, _ = limiter.check_rate_limit(None)
        assert is_allowed is True

    def test_failed_attempts_recorded(self):
        """Failed login attempts should be recorded."""
        limiter = IPRateLimiter()
        ip = "10.0.0.1"

        # Record some failed attempts
        for _ in range(5):
            limiter.record_attempt(ip, success=False)

        # Check that attempts are tracked
        with limiter._lock:
            assert ip in limiter._attempts
            assert len(limiter._attempts[ip]) == 5

    def test_successful_login_clears_attempts(self):
        """Successful login should clear failed attempt counter."""
        limiter = IPRateLimiter()
        ip = "10.0.0.2"

        # Record failed attempts
        for _ in range(3):
            limiter.record_attempt(ip, success=False)

        # Successful login
        limiter.record_attempt(ip, success=True)

        # Check that attempts are cleared
        with limiter._lock:
            assert ip not in limiter._attempts
            assert ip not in limiter._lockouts

    def test_lockout_after_max_attempts(self):
        """IP should be locked out after exceeding max attempts."""
        limiter = IPRateLimiter()
        ip = "10.0.0.3"

        # Record max attempts
        for _ in range(limiter.MAX_ATTEMPTS_PER_WINDOW):
            limiter.record_attempt(ip, success=False)

        # Check rate limit - should be blocked
        is_allowed, seconds_remaining = limiter.check_rate_limit(ip)
        assert is_allowed is False
        assert seconds_remaining > 0
        assert seconds_remaining <= limiter.LOCKOUT_SECONDS

    def test_lockout_clears_after_time(self):
        """Lockout should clear after the lockout period."""
        limiter = IPRateLimiter()
        ip = "10.0.0.4"

        # Set a lockout that has already expired
        with limiter._lock:
            limiter._lockouts[ip] = datetime.now(UTC) - timedelta(seconds=10)

        # Should be allowed now
        is_allowed, _ = limiter.check_rate_limit(ip)
        assert is_allowed is True


# =============================================================================
# AuthService Registration Tests
# =============================================================================


class TestAuthServiceRegistration:
    """Tests for user registration."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        repo = AsyncMock()
        repo.username_exists = AsyncMock(return_value=False)
        repo.email_exists = AsyncMock(return_value=False)
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def mock_audit_repo(self):
        """Create mock audit repository."""
        repo = AsyncMock()
        repo.log_user_action = AsyncMock()
        repo.log_security_event = AsyncMock()
        return repo

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_audit_repo):
        """Create auth service with mocked dependencies."""
        return AuthService(mock_user_repo, mock_audit_repo)

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, mock_user_repo):
        """Successful registration creates user and logs action."""
        # Setup mock to return created user
        created_user = User(
            id="user123",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=False,
            auth_provider=AuthProvider.LOCAL,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_user_repo.create.return_value = created_user

        # Register user
        result = await auth_service.register(
            username="testuser",
            email="test@example.com",
            password="SecureP@ss123!",
            display_name="Test User",
        )

        assert result.username == "testuser"
        mock_user_repo.username_exists.assert_called_once()
        mock_user_repo.email_exists.assert_called_once()
        mock_user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, auth_service, mock_user_repo):
        """Registration fails with duplicate username."""
        mock_user_repo.username_exists.return_value = True

        with pytest.raises(RegistrationError, match="already taken"):
            await auth_service.register(
                username="existing",
                email="new@example.com",
                password="SecureP@ss123!",
            )

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_service, mock_user_repo):
        """Registration fails with duplicate email."""
        mock_user_repo.email_exists.return_value = True

        with pytest.raises(RegistrationError, match="already registered"):
            await auth_service.register(
                username="newuser",
                email="existing@example.com",
                password="SecureP@ss123!",
            )


# =============================================================================
# AuthService Login Tests
# =============================================================================


class TestAuthServiceLogin:
    """Tests for user login."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        repo = AsyncMock()
        repo.get_by_username_or_email = AsyncMock()
        repo.record_failed_login = AsyncMock()
        repo.set_lockout = AsyncMock()
        repo.clear_lockout = AsyncMock()
        repo.record_login = AsyncMock()
        repo.update_refresh_token = AsyncMock()
        repo.update_password = AsyncMock()
        return repo

    @pytest.fixture
    def mock_audit_repo(self):
        """Create mock audit repository."""
        repo = AsyncMock()
        repo.log_user_action = AsyncMock()
        repo.log_security_event = AsyncMock()
        return repo

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_audit_repo):
        """Create auth service with mocked dependencies."""
        return AuthService(mock_user_repo, mock_audit_repo)

    @pytest.fixture
    def valid_user(self):
        """Create a valid user for testing."""
        from forge.security.password import hash_password

        return UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            password_hash=hash_password("SecureP@ss123!", validate=False),
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=True,
            auth_provider=AuthProvider.LOCAL,
            failed_login_attempts=0,
            lockout_until=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, mock_user_repo, mock_audit_repo, valid_user):
        """Successful login returns user and tokens."""
        mock_user_repo.get_by_username_or_email.return_value = valid_user

        user, token = await auth_service.login(
            username_or_email="testuser",
            password="SecureP@ss123!",
        )

        assert user.id == "user123"
        assert token.access_token
        assert token.refresh_token
        mock_user_repo.clear_lockout.assert_called_once()
        mock_user_repo.record_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_service, mock_user_repo, mock_audit_repo):
        """Login fails when user doesn't exist."""
        mock_user_repo.get_by_username_or_email.return_value = None

        with pytest.raises(InvalidCredentialsError, match="Invalid"):
            await auth_service.login(
                username_or_email="nonexistent",
                password="AnyPassword1!",
            )

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, auth_service, mock_user_repo, mock_audit_repo, valid_user
    ):
        """Login fails with wrong password."""
        mock_user_repo.get_by_username_or_email.return_value = valid_user

        with pytest.raises(InvalidCredentialsError, match="Invalid"):
            await auth_service.login(
                username_or_email="testuser",
                password="WrongPassword1!",
            )

        mock_user_repo.record_failed_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_locked_account(
        self, auth_service, mock_user_repo, mock_audit_repo, valid_user
    ):
        """Login fails when account is locked."""
        valid_user.lockout_until = datetime.now(UTC) + timedelta(minutes=30)
        mock_user_repo.get_by_username_or_email.return_value = valid_user

        with pytest.raises(AccountLockedError, match="temporarily locked"):
            await auth_service.login(
                username_or_email="testuser",
                password="SecureP@ss123!",
            )

    @pytest.mark.asyncio
    async def test_login_deactivated_account(
        self, auth_service, mock_user_repo, mock_audit_repo, valid_user
    ):
        """Login fails when account is deactivated."""
        valid_user.is_active = False
        mock_user_repo.get_by_username_or_email.return_value = valid_user

        with pytest.raises(AccountDeactivatedError, match="deactivated"):
            await auth_service.login(
                username_or_email="testuser",
                password="SecureP@ss123!",
            )

    @pytest.mark.asyncio
    async def test_login_ip_rate_limited(self, auth_service, mock_user_repo, mock_audit_repo):
        """Login fails when IP is rate limited."""
        # Create a rate limiter that will block the IP
        limiter = IPRateLimiter()
        ip = "10.0.0.5"

        # Force a lockout
        with limiter._lock:
            limiter._lockouts[ip] = datetime.now(UTC) + timedelta(minutes=15)

        auth_service._ip_rate_limiter = limiter

        with pytest.raises(IPRateLimitExceededError, match="Too many login attempts"):
            await auth_service.login(
                username_or_email="testuser",
                password="AnyPassword1!",
                ip_address=ip,
            )


# =============================================================================
# AuthService Token Tests
# =============================================================================


class TestAuthServiceTokens:
    """Tests for token operations."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.validate_refresh_token = AsyncMock(return_value=True)
        repo.update_refresh_token = AsyncMock()
        return repo

    @pytest.fixture
    def mock_audit_repo(self):
        """Create mock audit repository."""
        repo = AsyncMock()
        repo.log_user_action = AsyncMock()
        repo.log_security_event = AsyncMock()
        return repo

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_audit_repo):
        """Create auth service with mocked dependencies."""
        return AuthService(mock_user_repo, mock_audit_repo)

    @pytest.fixture
    def valid_user(self):
        """Create a valid user for testing."""
        from forge.security.password import hash_password

        return UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("SecureP@ss123!", validate=False),
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=True,
            auth_provider=AuthProvider.LOCAL,
            failed_login_attempts=0,
            lockout_until=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(self, auth_service, mock_user_repo, valid_user):
        """Token refresh returns new token pair."""
        from forge.security.tokens import create_refresh_token

        mock_user_repo.get_by_id.return_value = valid_user
        refresh_token = create_refresh_token(valid_user.id, valid_user.username)

        new_token = await auth_service.refresh_tokens(refresh_token)

        assert new_token.access_token
        assert new_token.refresh_token
        mock_user_repo.update_refresh_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid_token(self, auth_service, mock_user_repo):
        """Token refresh fails with invalid token."""
        from forge.security.tokens import TokenInvalidError

        with pytest.raises(TokenInvalidError):
            await auth_service.refresh_tokens("invalid_token")

    @pytest.mark.asyncio
    async def test_refresh_tokens_deactivated_user(self, auth_service, mock_user_repo, valid_user):
        """Token refresh fails for deactivated user."""
        from forge.security.tokens import create_refresh_token

        valid_user.is_active = False
        mock_user_repo.get_by_id.return_value = valid_user
        refresh_token = create_refresh_token(valid_user.id, valid_user.username)

        with pytest.raises(AccountDeactivatedError):
            await auth_service.refresh_tokens(refresh_token)

    @pytest.mark.asyncio
    async def test_validate_access_token_success(self, auth_service):
        """Valid access token returns auth context."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        context = await auth_service.validate_access_token(token)

        assert context.user_id == "user123"
        assert context.trust_flame == 60
        assert context.role.value == "user"

    @pytest.mark.asyncio
    async def test_validate_access_token_expired(self, auth_service):
        """Expired access token raises error."""
        from forge.security.tokens import TokenExpiredError

        # Create expired token by manipulating settings temporarily
        with patch("forge.security.tokens.settings") as mock_settings:
            mock_settings.jwt_access_token_expire_minutes = -1
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_secret_key = "test-secret-key-at-least-32-characters-long-for-testing"

            from forge.security.tokens import create_access_token

            expired_token = create_access_token(
                user_id="user123",
                username="testuser",
                role="user",
                trust_flame=60,
            )

        with pytest.raises(TokenExpiredError):
            await auth_service.validate_access_token(expired_token)


# =============================================================================
# AuthService Password Management Tests
# =============================================================================


class TestAuthServicePasswordManagement:
    """Tests for password operations."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.get_by_email = AsyncMock()
        repo.update_password = AsyncMock()
        repo.update_refresh_token = AsyncMock()
        repo.store_password_reset_token = AsyncMock(return_value=True)
        repo.validate_password_reset_token = AsyncMock(return_value=True)
        repo.clear_password_reset_token = AsyncMock()
        repo.clear_lockout = AsyncMock()
        return repo

    @pytest.fixture
    def mock_audit_repo(self):
        """Create mock audit repository."""
        repo = AsyncMock()
        repo.log_user_action = AsyncMock()
        repo.log_security_event = AsyncMock()
        return repo

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_audit_repo):
        """Create auth service with mocked dependencies."""
        return AuthService(mock_user_repo, mock_audit_repo)

    @pytest.fixture
    def valid_user(self):
        """Create a valid user for testing."""
        from forge.security.password import hash_password

        return UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("OldSecureP@ss1!", validate=False),
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=True,
            auth_provider=AuthProvider.LOCAL,
            failed_login_attempts=0,
            lockout_until=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_change_password_success(
        self, auth_service, mock_user_repo, mock_audit_repo, valid_user
    ):
        """Password change succeeds with correct current password."""
        mock_user_repo.get_by_id.return_value = valid_user

        await auth_service.change_password(
            user_id="user123",
            current_password="OldSecureP@ss1!",
            new_password="NewSecureP@ss2!",
        )

        mock_user_repo.update_password.assert_called_once()
        mock_user_repo.update_refresh_token.assert_called_once_with("user123", None)
        mock_audit_repo.log_security_event.assert_called()

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, auth_service, mock_user_repo, valid_user):
        """Password change fails with wrong current password."""
        mock_user_repo.get_by_id.return_value = valid_user

        with pytest.raises(InvalidCredentialsError, match="Current password is incorrect"):
            await auth_service.change_password(
                user_id="user123",
                current_password="WrongPassword1!",
                new_password="NewSecureP@ss2!",
            )

    @pytest.mark.asyncio
    async def test_request_password_reset_existing_user(
        self, auth_service, mock_user_repo, valid_user
    ):
        """Password reset request returns token for existing user."""
        mock_user_repo.get_by_email.return_value = valid_user

        token = await auth_service.request_password_reset("test@example.com")

        assert token is not None
        mock_user_repo.store_password_reset_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_password_reset_nonexistent_user(self, auth_service, mock_user_repo):
        """Password reset request returns None for nonexistent user."""
        mock_user_repo.get_by_email.return_value = None

        token = await auth_service.request_password_reset("nonexistent@example.com")

        assert token is None
        mock_user_repo.store_password_reset_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_password_success(self, auth_service, mock_user_repo, valid_user):
        """Password reset succeeds with valid token."""
        mock_user_repo.get_by_id.return_value = valid_user

        await auth_service.reset_password(
            user_id="user123",
            new_password="NewSecureP@ss3!",
            reset_token="valid_token_here",
        )

        mock_user_repo.update_password.assert_called_once()
        mock_user_repo.clear_password_reset_token.assert_called_once()
        mock_user_repo.clear_lockout.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, auth_service, mock_user_repo, valid_user):
        """Password reset fails with invalid token."""
        mock_user_repo.get_by_id.return_value = valid_user
        mock_user_repo.validate_password_reset_token.return_value = False

        with pytest.raises(AuthenticationError, match="Invalid or expired"):
            await auth_service.reset_password(
                user_id="user123",
                new_password="NewSecureP@ss3!",
                reset_token="invalid_token",
            )


# =============================================================================
# AuthService Account Management Tests
# =============================================================================


class TestAuthServiceAccountManagement:
    """Tests for account management operations."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.deactivate = AsyncMock()
        repo.activate = AsyncMock()
        repo.update_refresh_token = AsyncMock()
        repo.adjust_trust_flame = AsyncMock()
        repo.set_verified = AsyncMock()
        repo.store_email_verification_token = AsyncMock()
        repo.validate_email_verification_token = AsyncMock(return_value=True)
        repo.clear_email_verification_token = AsyncMock()
        return repo

    @pytest.fixture
    def mock_audit_repo(self):
        """Create mock audit repository."""
        repo = AsyncMock()
        repo.log_user_action = AsyncMock()
        repo.log_security_event = AsyncMock()
        return repo

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_audit_repo):
        """Create auth service with mocked dependencies."""
        return AuthService(mock_user_repo, mock_audit_repo)

    @pytest.fixture
    def valid_user(self):
        """Create a valid user for testing."""
        from forge.security.password import hash_password

        return UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            password_hash=hash_password("SecureP@ss123!", validate=False),
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=False,
            auth_provider=AuthProvider.LOCAL,
            failed_login_attempts=0,
            lockout_until=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_deactivate_account(self, auth_service, mock_user_repo, mock_audit_repo):
        """Account deactivation works correctly."""
        await auth_service.deactivate_account(
            user_id="user123",
            deactivated_by="admin456",
            reason="Violated terms of service",
        )

        mock_user_repo.deactivate.assert_called_once_with("user123")
        mock_user_repo.update_refresh_token.assert_called_once_with("user123", None)
        mock_audit_repo.log_user_action.assert_called()

    @pytest.mark.asyncio
    async def test_reactivate_account(self, auth_service, mock_user_repo, mock_audit_repo):
        """Account reactivation works correctly."""
        await auth_service.reactivate_account(
            user_id="user123",
            reactivated_by="admin456",
        )

        mock_user_repo.activate.assert_called_once_with("user123")
        mock_audit_repo.log_user_action.assert_called()

    @pytest.mark.asyncio
    async def test_verify_email_success(self, auth_service, mock_user_repo, valid_user):
        """Email verification succeeds with valid token."""
        mock_user_repo.get_by_id.return_value = valid_user

        await auth_service.verify_email(
            user_id="user123",
            verification_token="valid_token_here",
        )

        mock_user_repo.set_verified.assert_called_once_with("user123")
        mock_user_repo.clear_email_verification_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, auth_service, mock_user_repo, valid_user):
        """Email verification fails with invalid token."""
        mock_user_repo.get_by_id.return_value = valid_user
        mock_user_repo.validate_email_verification_token.return_value = False

        with pytest.raises(AuthenticationError, match="Invalid or expired"):
            await auth_service.verify_email(
                user_id="user123",
                verification_token="invalid_token",
            )

    @pytest.mark.asyncio
    async def test_adjust_user_trust(
        self, auth_service, mock_user_repo, mock_audit_repo, valid_user
    ):
        """Trust adjustment works correctly."""
        mock_user_repo.get_by_id.return_value = valid_user
        mock_user_repo.adjust_trust_flame.return_value = 70

        new_trust = await auth_service.adjust_user_trust(
            user_id="user123",
            adjusted_by="admin456",
            adjustment=10,
            reason="Good contributions",
        )

        assert new_trust == 70
        mock_user_repo.adjust_trust_flame.assert_called_once()
        mock_audit_repo.log_user_action.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
