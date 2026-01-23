"""
User Model Tests for Forge Cascade V2

Comprehensive tests for user models including:
- User creation validation
- Password validation
- Avatar URL validation
- Trust level computation
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.base import TrustLevel
from forge.models.user import (
    AuthProvider,
    Capability,
    KeyStorageStrategy,
    LoginRequest,
    Token,
    TokenPayload,
    TrustFlameAdjustment,
    TrustFlameReason,
    User,
    UserBase,
    UserCreate,
    UserInDB,
    UserPasswordChange,
    UserPublic,
    UserRole,
    UserStats,
    UserUpdate,
)


# =============================================================================
# UserBase Tests
# =============================================================================

class TestUserBase:
    """Tests for UserBase model."""

    def test_valid_user_base(self):
        """Valid user base data creates model."""
        user = UserBase(
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            bio="A test user",
            avatar_url="https://example.com/avatar.jpg",
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"

    def test_username_min_length(self):
        """Username must be at least 3 characters."""
        with pytest.raises(ValidationError, match="String should have at least 3"):
            UserBase(username="ab", email="test@example.com")

    def test_username_max_length(self):
        """Username must be at most 50 characters."""
        with pytest.raises(ValidationError):
            UserBase(username="a" * 51, email="test@example.com")

    def test_username_pattern(self):
        """Username must match pattern."""
        # Valid patterns
        UserBase(username="test_user-123", email="test@example.com")
        UserBase(username="TestUser", email="test@example.com")

        # Invalid patterns
        with pytest.raises(ValidationError):
            UserBase(username="test@user", email="test@example.com")

        with pytest.raises(ValidationError):
            UserBase(username="test user", email="test@example.com")

    def test_email_validation(self):
        """Email must be valid format."""
        with pytest.raises(ValidationError):
            UserBase(username="testuser", email="not-an-email")

    def test_avatar_url_validation_valid(self):
        """Valid HTTP/HTTPS avatar URLs pass validation."""
        user = UserBase(
            username="testuser",
            email="test@example.com",
            avatar_url="https://example.com/avatar.jpg",
        )
        assert user.avatar_url == "https://example.com/avatar.jpg"

        user2 = UserBase(
            username="testuser",
            email="test@example.com",
            avatar_url="http://example.com/avatar.jpg",
        )
        assert user2.avatar_url == "http://example.com/avatar.jpg"

    def test_avatar_url_validation_invalid_scheme(self):
        """Invalid URL schemes are rejected."""
        with pytest.raises(ValidationError, match="http or https"):
            UserBase(
                username="testuser",
                email="test@example.com",
                avatar_url="javascript:alert('xss')",
            )

        with pytest.raises(ValidationError, match="http or https"):
            UserBase(
                username="testuser",
                email="test@example.com",
                avatar_url="data:image/png;base64,xxx",
            )

    def test_avatar_url_none_allowed(self):
        """None avatar URL is allowed."""
        user = UserBase(
            username="testuser",
            email="test@example.com",
            avatar_url=None,
        )
        assert user.avatar_url is None

    def test_avatar_url_empty_becomes_none(self):
        """Empty avatar URL becomes None."""
        user = UserBase(
            username="testuser",
            email="test@example.com",
            avatar_url="   ",
        )
        assert user.avatar_url is None


# =============================================================================
# UserCreate Tests
# =============================================================================

class TestUserCreate:
    """Tests for UserCreate model."""

    def test_valid_user_create(self):
        """Valid user create data."""
        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecureP@ss123!",
        )
        assert user.password == "SecureP@ss123!"

    def test_password_min_length(self):
        """Password must be at least 8 characters."""
        with pytest.raises(ValidationError, match="at least 8"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="Short1!",
            )

    def test_password_max_length(self):
        """Password must be at most 72 characters (bcrypt limit)."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="A" * 80,
            )

    def test_password_requires_uppercase(self):
        """Password must have uppercase letter."""
        with pytest.raises(ValidationError, match="uppercase"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="lowercase123!",
            )

    def test_password_requires_lowercase(self):
        """Password must have lowercase letter."""
        with pytest.raises(ValidationError, match="lowercase"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="UPPERCASE123!",
            )

    def test_password_requires_digit(self):
        """Password must have digit."""
        with pytest.raises(ValidationError, match="digit"):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="NoDigitsHere!",
            )


# =============================================================================
# User Model Tests
# =============================================================================

class TestUser:
    """Tests for User model."""

    def test_user_trust_level_property(self):
        """Trust level is computed from trust flame."""
        user = User(
            id="user123",
            username="testuser",
            email="test@example.com",
            trust_flame=60,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert user.trust_level == TrustLevel.STANDARD

    def test_user_trust_flame_bounds(self):
        """Trust flame must be 0-100."""
        with pytest.raises(ValidationError):
            User(
                id="user123",
                username="testuser",
                email="test@example.com",
                trust_flame=-10,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

        with pytest.raises(ValidationError):
            User(
                id="user123",
                username="testuser",
                email="test@example.com",
                trust_flame=150,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_user_defaults(self):
        """User has sensible defaults."""
        user = User(
            id="user123",
            username="testuser",
            email="test@example.com",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert user.role == UserRole.USER
        assert user.trust_flame == 60
        assert user.is_active is True
        assert user.is_verified is False
        assert user.auth_provider == AuthProvider.LOCAL
        assert user.metadata == {}

    def test_user_metadata_none_converts_to_dict(self):
        """None metadata converts to empty dict."""
        user = User(
            id="user123",
            username="testuser",
            email="test@example.com",
            metadata=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert user.metadata == {}


# =============================================================================
# UserInDB Tests
# =============================================================================

class TestUserInDB:
    """Tests for UserInDB model."""

    def test_user_in_db_fields(self):
        """UserInDB has database-specific fields."""
        user = UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$hashedpassword",
            refresh_token="token_hash",
            failed_login_attempts=3,
            lockout_until=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert user.password_hash.startswith("$2b$")
        assert user.refresh_token == "token_hash"
        assert user.failed_login_attempts == 3

    def test_user_in_db_signing_keys(self):
        """UserInDB supports signing key fields."""
        user = UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$hash",
            key_storage_strategy=KeyStorageStrategy.SERVER_CUSTODY,
            signing_public_key="base64publickey",
            encrypted_private_key="encrypted",
            signing_key_created_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        assert user.key_storage_strategy == KeyStorageStrategy.SERVER_CUSTODY


# =============================================================================
# TokenPayload Tests
# =============================================================================

class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_access_token_requires_role(self):
        """Access token must have role claim."""
        with pytest.raises(ValidationError, match="role"):
            TokenPayload(
                sub="user123",
                username="testuser",
                role=None,  # Missing role
                trust_flame=60,
                type="access",
            )

    def test_access_token_requires_trust_flame(self):
        """Access token must have trust_flame claim."""
        with pytest.raises(ValidationError, match="trust_flame"):
            TokenPayload(
                sub="user123",
                username="testuser",
                role=UserRole.USER,
                trust_flame=None,  # Missing trust_flame
                type="access",
            )

    def test_access_token_trust_flame_bounds(self):
        """Access token trust_flame must be 0-100."""
        with pytest.raises(ValidationError, match="trust_flame"):
            TokenPayload(
                sub="user123",
                username="testuser",
                role=UserRole.USER,
                trust_flame=150,  # Invalid
                type="access",
            )

    def test_refresh_token_no_role_required(self):
        """Refresh token doesn't require role."""
        payload = TokenPayload(
            sub="user123",
            username="testuser",
            type="refresh",
        )

        assert payload.role is None
        assert payload.trust_flame is None


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Tests for user-related enums."""

    def test_user_role_values(self):
        """UserRole has expected values."""
        assert UserRole.USER.value == "user"
        assert UserRole.MODERATOR.value == "moderator"
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.SYSTEM.value == "system"

    def test_auth_provider_values(self):
        """AuthProvider has expected values."""
        assert AuthProvider.LOCAL.value == "local"
        assert AuthProvider.GOOGLE.value == "google"
        assert AuthProvider.GITHUB.value == "github"
        assert AuthProvider.WEB3.value == "web3"

    def test_capability_values(self):
        """Capability enum has expected values."""
        assert Capability.CREATE_CAPSULE.value == "create_capsule"
        assert Capability.VOTE.value == "vote"
        assert Capability.MANAGE_USERS.value == "manage_users"

    def test_key_storage_strategy_values(self):
        """KeyStorageStrategy has expected values."""
        assert KeyStorageStrategy.SERVER_CUSTODY.value == "server_custody"
        assert KeyStorageStrategy.CLIENT_ONLY.value == "client_only"
        assert KeyStorageStrategy.PASSWORD_DERIVED.value == "password_derived"
        assert KeyStorageStrategy.NONE.value == "none"


# =============================================================================
# UserPublic Tests
# =============================================================================

class TestUserPublic:
    """Tests for UserPublic model (no sensitive data)."""

    def test_user_public_fields(self):
        """UserPublic has only public fields."""
        public = UserPublic(
            id="user123",
            username="testuser",
            display_name="Test User",
            trust_flame=60,
            created_at=datetime.now(UTC),
        )

        assert public.id == "user123"
        assert public.trust_level == TrustLevel.STANDARD

        # Should NOT have sensitive fields
        assert not hasattr(public, "email")
        assert not hasattr(public, "password_hash")


# =============================================================================
# TrustFlameAdjustment Tests
# =============================================================================

class TestTrustFlameAdjustment:
    """Tests for TrustFlameAdjustment model."""

    def test_adjustment_record(self):
        """TrustFlameAdjustment records adjustment details."""
        adjustment = TrustFlameAdjustment(
            user_id="user123",
            old_value=60,
            new_value=70,
            reason="Good contributions",
            adjusted_by="admin456",
        )

        assert adjustment.old_value == 60
        assert adjustment.new_value == 70
        assert adjustment.timestamp is not None


# =============================================================================
# UserUpdate Tests
# =============================================================================

class TestUserUpdate:
    """Tests for UserUpdate model."""

    def test_user_update_optional_fields(self):
        """UserUpdate has all optional fields."""
        update = UserUpdate()
        assert update.display_name is None
        assert update.bio is None
        assert update.avatar_url is None
        assert update.email is None

    def test_user_update_partial(self):
        """UserUpdate allows partial updates."""
        update = UserUpdate(display_name="New Name")
        assert update.display_name == "New Name"
        assert update.email is None


# =============================================================================
# UserPasswordChange Tests
# =============================================================================

class TestUserPasswordChange:
    """Tests for UserPasswordChange model."""

    def test_password_change_validation(self):
        """Password change validates new password."""
        with pytest.raises(ValidationError, match="uppercase"):
            UserPasswordChange(
                current_password="CurrentP@ss1!",
                new_password="alllowercase1!",
            )

    def test_password_change_max_length(self):
        """New password has max length (bcrypt limit)."""
        with pytest.raises(ValidationError):
            UserPasswordChange(
                current_password="CurrentP@ss1!",
                new_password="A" * 80,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
