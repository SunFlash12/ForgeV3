"""
Google OAuth Service Tests for Forge Cascade V2

Comprehensive tests for Google OAuth authentication including:
- Token verification
- User info extraction
- User creation and linking
- Username generation
- Configuration validation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.security.google_oauth import (
    GoogleOAuthError,
    GoogleOAuthService,
    GoogleUserInfo,
    get_google_oauth_service,
)


# =============================================================================
# GoogleUserInfo Model Tests
# =============================================================================


class TestGoogleUserInfo:
    """Tests for GoogleUserInfo model."""

    def test_creates_user_info_with_required_fields(self):
        """Creates user info with required fields."""
        user_info = GoogleUserInfo(
            sub="google-user-123",
            email="test@example.com",
        )

        assert user_info.sub == "google-user-123"
        assert user_info.email == "test@example.com"
        assert user_info.email_verified is False

    def test_creates_user_info_with_all_fields(self):
        """Creates user info with all fields."""
        user_info = GoogleUserInfo(
            sub="google-user-123",
            email="test@example.com",
            email_verified=True,
            name="Test User",
            given_name="Test",
            family_name="User",
            picture="https://example.com/photo.jpg",
            locale="en-US",
        )

        assert user_info.sub == "google-user-123"
        assert user_info.email == "test@example.com"
        assert user_info.email_verified is True
        assert user_info.name == "Test User"
        assert user_info.given_name == "Test"
        assert user_info.family_name == "User"
        assert user_info.picture == "https://example.com/photo.jpg"
        assert user_info.locale == "en-US"

    def test_optional_fields_default_to_none(self):
        """Optional fields default to None."""
        user_info = GoogleUserInfo(
            sub="google-user-123",
            email="test@example.com",
        )

        assert user_info.name is None
        assert user_info.given_name is None
        assert user_info.family_name is None
        assert user_info.picture is None
        assert user_info.locale is None

    def test_email_validation(self):
        """Email field validates email format."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoogleUserInfo(
                sub="google-user-123",
                email="not-an-email",
            )


# =============================================================================
# GoogleOAuthService Configuration Tests
# =============================================================================


class TestGoogleOAuthServiceConfiguration:
    """Tests for GoogleOAuthService configuration."""

    def test_is_configured_with_client_id(self):
        """Service is configured when client_id is set."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()
            assert service.is_configured is True

    def test_is_not_configured_without_client_id(self):
        """Service is not configured when client_id is not set."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = None
            mock_settings.return_value.google_client_secret = None

            service = GoogleOAuthService()
            assert service.is_configured is False

    def test_logs_warning_when_not_configured(self):
        """Logs warning when Google OAuth is not configured."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            with patch("forge.security.google_oauth.logger") as mock_logger:
                mock_settings.return_value.google_client_id = None
                mock_settings.return_value.google_client_secret = None

                GoogleOAuthService()
                mock_logger.warning.assert_called()


# =============================================================================
# Token Verification Tests
# =============================================================================


class TestVerifyIdToken:
    """Tests for ID token verification."""

    @pytest.mark.asyncio
    async def test_raises_error_when_not_configured(self):
        """Raises error when Google OAuth is not configured."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = None
            mock_settings.return_value.google_client_secret = None

            service = GoogleOAuthService()

            with pytest.raises(GoogleOAuthError, match="not configured"):
                await service.verify_id_token("test-token")

    @pytest.mark.asyncio
    async def test_verifies_valid_token(self):
        """Verifies valid token and returns user info."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            # Mock the HTTP response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sub": "google-user-123",
                "email": "test@example.com",
                "email_verified": "true",
                "name": "Test User",
                "given_name": "Test",
                "family_name": "User",
                "picture": "https://example.com/photo.jpg",
                "aud": "test-client-id",
                "exp": str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp())),
            }

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                result = await service.verify_id_token("valid-token")

                assert result.sub == "google-user-123"
                assert result.email == "test@example.com"
                assert result.email_verified is True
                assert result.name == "Test User"

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_token(self):
        """Raises error for invalid token (non-200 response)."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid token"

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                with pytest.raises(GoogleOAuthError, match="Invalid or expired"):
                    await service.verify_id_token("invalid-token")

    @pytest.mark.asyncio
    async def test_raises_error_for_audience_mismatch(self):
        """Raises error when token audience doesn't match client ID."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sub": "google-user-123",
                "email": "test@example.com",
                "aud": "different-client-id",  # Mismatch
                "exp": str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp())),
            }

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                with pytest.raises(GoogleOAuthError, match="not issued for this application"):
                    await service.verify_id_token("token-wrong-audience")

    @pytest.mark.asyncio
    async def test_raises_error_for_expired_token(self):
        """Raises error when token is expired."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sub": "google-user-123",
                "email": "test@example.com",
                "aud": "test-client-id",
                "exp": str(int((datetime.now(UTC) - timedelta(hours=1)).timestamp())),  # Expired
            }

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                with pytest.raises(GoogleOAuthError, match="expired"):
                    await service.verify_id_token("expired-token")


# =============================================================================
# User Creation and Linking Tests
# =============================================================================


class TestGetOrCreateUser:
    """Tests for get_or_create_user functionality."""

    @pytest.mark.asyncio
    async def test_returns_existing_user_by_google_id(self):
        """Returns existing user when found by Google ID."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="test@example.com",
                email_verified=True,
            )

            mock_repo = AsyncMock()
            existing_user = MagicMock()
            existing_user.id = "user-123"
            mock_repo.get_by_google_id.return_value = existing_user

            user, is_new = await service.get_or_create_user(google_user, mock_repo)

            assert user.id == "user-123"
            assert is_new is False
            mock_repo.get_by_google_id.assert_called_once_with("google-user-123")

    @pytest.mark.asyncio
    async def test_links_account_for_existing_user_by_email(self):
        """Links Google account to existing user found by email."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="test@example.com",
                email_verified=True,  # Must be verified for auto-link
            )

            mock_repo = AsyncMock()
            mock_repo.get_by_google_id.return_value = None

            existing_user = MagicMock()
            existing_user.id = "user-456"
            mock_repo.get_by_email.return_value = existing_user

            updated_user = MagicMock()
            updated_user.id = "user-456"
            mock_repo.get_by_id.return_value = updated_user

            user, is_new = await service.get_or_create_user(google_user, mock_repo)

            assert user.id == "user-456"
            assert is_new is False
            mock_repo.link_google_account.assert_called_once_with(
                user_id="user-456",
                google_id="google-user-123",
                google_email="test@example.com",
            )

    @pytest.mark.asyncio
    async def test_raises_error_for_unverified_email_link(self):
        """Raises error when trying to link unverified Google email."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="test@example.com",
                email_verified=False,  # Not verified
            )

            mock_repo = AsyncMock()
            mock_repo.get_by_google_id.return_value = None

            existing_user = MagicMock()
            mock_repo.get_by_email.return_value = existing_user

            with pytest.raises(GoogleOAuthError, match="already exists"):
                await service.get_or_create_user(google_user, mock_repo)

    @pytest.mark.asyncio
    async def test_creates_new_user_when_not_found(self):
        """Creates new user when not found by Google ID or email."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="test@example.com",
                email_verified=True,
                name="Test User",
                picture="https://example.com/photo.jpg",
            )

            mock_repo = AsyncMock()
            mock_repo.get_by_google_id.return_value = None
            mock_repo.get_by_email.return_value = None
            mock_repo.username_exists.return_value = False

            new_user = MagicMock()
            new_user.id = "new-user-789"
            mock_repo.create_google_user.return_value = new_user

            user, is_new = await service.get_or_create_user(google_user, mock_repo)

            assert user.id == "new-user-789"
            assert is_new is True
            mock_repo.create_google_user.assert_called_once()


# =============================================================================
# Username Generation Tests
# =============================================================================


class TestUsernameGeneration:
    """Tests for username generation from Google user info."""

    def test_generates_username_from_email(self):
        """Generates username from email prefix."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="john.doe@example.com",
            )

            username = service._generate_username(google_user)
            assert username == "johndoe"

    def test_removes_special_characters(self):
        """Removes special characters from username."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="john+test!@example.com",
            )

            username = service._generate_username(google_user)
            # Only alphanumeric, underscore, and hyphen allowed
            assert username == "johntest"

    def test_uses_given_name_for_short_email(self):
        """Uses given_name when email prefix is too short."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="ab@example.com",  # Too short after cleaning
                given_name="Alexander",
            )

            username = service._generate_username(google_user)
            assert username == "alexander"

    def test_fallback_to_user_for_very_short_names(self):
        """Falls back to 'user' when all names are too short."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="ab@example.com",
                given_name="AB",  # Too short
            )

            username = service._generate_username(google_user)
            assert username == "user"

    def test_truncates_long_usernames(self):
        """Truncates usernames to 50 characters."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            google_user = GoogleUserInfo(
                sub="google-user-123",
                email="a" * 100 + "@example.com",
            )

            username = service._generate_username(google_user)
            assert len(username) <= 50


class TestEnsureUniqueUsername:
    """Tests for unique username generation."""

    @pytest.mark.asyncio
    async def test_returns_base_username_if_unique(self):
        """Returns base username when it's already unique."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_repo = AsyncMock()
            mock_repo.username_exists.return_value = False

            username = await service._ensure_unique_username("testuser", mock_repo)
            assert username == "testuser"

    @pytest.mark.asyncio
    async def test_appends_number_for_duplicate(self):
        """Appends number when base username exists."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_repo = AsyncMock()
            # First call: base username exists, second: with number doesn't
            mock_repo.username_exists.side_effect = [True, False]

            username = await service._ensure_unique_username("testuser", mock_repo)
            assert username == "testuser1"

    @pytest.mark.asyncio
    async def test_increments_number_until_unique(self):
        """Increments number until finding unique username."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_repo = AsyncMock()
            # testuser, testuser1, testuser2 all exist, testuser3 doesn't
            mock_repo.username_exists.side_effect = [True, True, True, False]

            username = await service._ensure_unique_username("testuser", mock_repo)
            assert username == "testuser3"

    @pytest.mark.asyncio
    async def test_uses_random_suffix_after_many_attempts(self):
        """Uses random suffix after 1000+ attempts."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            mock_repo = AsyncMock()
            # All numbered usernames exist
            mock_repo.username_exists.return_value = True

            with patch("secrets.token_hex", return_value="abcd1234"):
                username = await service._ensure_unique_username("testuser", mock_repo)
                assert username == "testuser_abcd1234"


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestGetGoogleOAuthService:
    """Tests for singleton service getter."""

    def test_returns_same_instance(self):
        """Returns the same service instance."""
        # Reset singleton
        import forge.security.google_oauth as module

        module._google_oauth_service = None

        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service1 = get_google_oauth_service()
            service2 = get_google_oauth_service()

            assert service1 is service2

        # Clean up
        module._google_oauth_service = None

    def test_creates_new_instance_when_none(self):
        """Creates new instance when singleton is None."""
        import forge.security.google_oauth as module

        module._google_oauth_service = None

        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = get_google_oauth_service()

            assert service is not None
            assert isinstance(service, GoogleOAuthService)

        # Clean up
        module._google_oauth_service = None


# =============================================================================
# Integration Tests
# =============================================================================


class TestGoogleOAuthIntegration:
    """Integration tests for complete OAuth flows."""

    @pytest.mark.asyncio
    async def test_complete_new_user_flow(self):
        """Tests complete flow for new user creation."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            # Setup mock responses for token verification
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sub": "google-user-new",
                "email": "newuser@example.com",
                "email_verified": "true",
                "name": "New User",
                "given_name": "New",
                "family_name": "User",
                "picture": "https://example.com/newphoto.jpg",
                "aud": "test-client-id",
                "exp": str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp())),
            }

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                # Verify token
                user_info = await service.verify_id_token("new-user-token")

                assert user_info.sub == "google-user-new"
                assert user_info.email == "newuser@example.com"

                # Create user
                mock_repo = AsyncMock()
                mock_repo.get_by_google_id.return_value = None
                mock_repo.get_by_email.return_value = None
                mock_repo.username_exists.return_value = False

                new_user = MagicMock()
                new_user.id = "created-user-123"
                mock_repo.create_google_user.return_value = new_user

                user, is_new = await service.get_or_create_user(user_info, mock_repo)

                assert is_new is True
                assert user.id == "created-user-123"
                mock_repo.create_google_user.assert_called_once_with(
                    username="newuser",
                    email="newuser@example.com",
                    display_name="New User",
                    avatar_url="https://example.com/newphoto.jpg",
                    google_id="google-user-new",
                    google_email="newuser@example.com",
                    is_verified=True,
                )

    @pytest.mark.asyncio
    async def test_complete_existing_user_flow(self):
        """Tests complete flow for existing user login."""
        with patch("forge.security.google_oauth.get_settings") as mock_settings:
            mock_settings.return_value.google_client_id = "test-client-id"
            mock_settings.return_value.google_client_secret = "test-client-secret"

            service = GoogleOAuthService()

            # Setup mock responses for token verification
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "sub": "google-user-existing",
                "email": "existing@example.com",
                "email_verified": "true",
                "name": "Existing User",
                "aud": "test-client-id",
                "exp": str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp())),
            }

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_async_client
                mock_async_client.get.return_value = mock_response

                # Verify token
                user_info = await service.verify_id_token("existing-user-token")

                # Find existing user
                mock_repo = AsyncMock()
                existing_user = MagicMock()
                existing_user.id = "existing-user-456"
                mock_repo.get_by_google_id.return_value = existing_user

                user, is_new = await service.get_or_create_user(user_info, mock_repo)

                assert is_new is False
                assert user.id == "existing-user-456"
                # Should not call create or link
                mock_repo.create_google_user.assert_not_called()
                mock_repo.link_google_account.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
