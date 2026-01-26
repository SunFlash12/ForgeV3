"""
User Repository Tests for Forge Cascade V2

Comprehensive tests for UserRepository including:
- User CRUD operations
- Authentication helpers
- Trust flame management
- Password reset tokens
- OAuth operations
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import hashlib

import pytest

from forge.models.base import TrustLevel
from forge.models.user import (
    AuthProvider,
    TrustFlameAdjustment,
    User,
    UserCreate,
    UserInDB,
    UserPublic,
    UserRole,
    UserUpdate,
)
from forge.repositories.user_repository import UserRepository


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
def user_repository(mock_db_client):
    """Create user repository with mock client."""
    return UserRepository(mock_db_client)


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "id": "user123",
        "username": "testuser",
        "email": "test@example.com",
        "display_name": "Test User",
        "bio": "A test user",
        "avatar_url": "https://example.com/avatar.jpg",
        "role": "user",
        "trust_flame": 60,
        "is_active": True,
        "is_verified": True,
        "auth_provider": "local",
        "last_login": None,
        "metadata": {},
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sample_user_in_db_data(sample_user_data):
    """Sample user in DB data with password hash."""
    return {
        **sample_user_data,
        "password_hash": "$2b$12$hashedpassword123456789012345678901234567890",
        "refresh_token": None,
        "failed_login_attempts": 0,
        "lockout_until": None,
    }


# =============================================================================
# User Creation Tests
# =============================================================================


class TestUserRepositoryCreate:
    """Tests for user creation."""

    @pytest.mark.asyncio
    async def test_create_user_success(
        self, user_repository, mock_db_client, sample_user_in_db_data
    ):
        """Successful user creation returns UserInDB."""
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        user_create = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecureP@ss123!",
            display_name="Test User",
        )

        result = await user_repository.create(
            user_create,
            password_hash="$2b$12$hashedpassword",
        )

        assert result.username == "testuser"
        assert result.email == "test@example.com"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_with_role(
        self, user_repository, mock_db_client, sample_user_in_db_data
    ):
        """User creation with specific role."""
        sample_user_in_db_data["role"] = "admin"
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        user_create = UserCreate(
            username="adminuser",
            email="admin@example.com",
            password="SecureP@ss123!",
        )

        result = await user_repository.create(
            user_create,
            password_hash="$2b$12$hashedpassword",
            role=UserRole.ADMIN,
        )

        # Verify the query parameters include the role
        call_args = mock_db_client.execute_single.call_args
        assert call_args[0][1]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_create_user_failure(self, user_repository, mock_db_client):
        """User creation failure raises error."""
        mock_db_client.execute_single.return_value = None

        user_create = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecureP@ss123!",
        )

        with pytest.raises(RuntimeError, match="Failed to create user"):
            await user_repository.create(
                user_create,
                password_hash="$2b$12$hashedpassword",
            )


# =============================================================================
# User Retrieval Tests
# =============================================================================


class TestUserRepositoryRetrieval:
    """Tests for user retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, user_repository, mock_db_client, sample_user_data):
        """Get user by ID returns User model."""
        mock_db_client.execute_single.return_value = {"user": sample_user_data}

        result = await user_repository.get_by_id("user123")

        assert result is not None
        assert result.id == "user123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, user_repository, mock_db_client):
        """Get non-existent user returns None."""
        mock_db_client.execute_single.return_value = None

        result = await user_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_username(self, user_repository, mock_db_client, sample_user_in_db_data):
        """Get user by username returns UserInDB."""
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        result = await user_repository.get_by_username("testuser")

        assert result is not None
        assert result.username == "testuser"
        assert hasattr(result, "password_hash")

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repository, mock_db_client, sample_user_in_db_data):
        """Get user by email returns UserInDB."""
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        result = await user_repository.get_by_email("test@example.com")

        assert result is not None
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_by_username_or_email(
        self, user_repository, mock_db_client, sample_user_in_db_data
    ):
        """Get user by username or email."""
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        result = await user_repository.get_by_username_or_email("testuser")

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_trust_level(self, user_repository, mock_db_client, sample_user_data):
        """Get users by minimum trust level."""
        mock_db_client.execute.return_value = [{"user": sample_user_data}]

        result = await user_repository.get_by_trust_level(min_trust=50)

        assert len(result) == 1


# =============================================================================
# User Update Tests
# =============================================================================


class TestUserRepositoryUpdate:
    """Tests for user update operations."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_repository, mock_db_client, sample_user_data):
        """Successful user update returns updated user."""
        sample_user_data["display_name"] = "Updated Name"
        mock_db_client.execute_single.return_value = {"user": sample_user_data}

        update = UserUpdate(display_name="Updated Name")
        result = await user_repository.update("user123", update)

        assert result is not None
        assert result.display_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_user_partial(self, user_repository, mock_db_client, sample_user_data):
        """Partial update only changes specified fields."""
        sample_user_data["bio"] = "New bio"
        mock_db_client.execute_single.return_value = {"user": sample_user_data}

        update = UserUpdate(bio="New bio")
        result = await user_repository.update("user123", update)

        assert result.bio == "New bio"

    @pytest.mark.asyncio
    async def test_update_password(self, user_repository, mock_db_client):
        """Password update works correctly."""
        mock_db_client.execute_single.return_value = {"id": "user123"}

        result = await user_repository.update_password("user123", "$2b$12$newpasswordhash")

        assert result is True
        mock_db_client.execute_single.assert_called_once()


# =============================================================================
# Authentication Helper Tests
# =============================================================================


class TestUserRepositoryAuthHelpers:
    """Tests for authentication helper methods."""

    @pytest.mark.asyncio
    async def test_record_login(self, user_repository, mock_db_client):
        """Record login updates last_login and clears failed attempts."""
        await user_repository.record_login("user123")

        mock_db_client.execute.assert_called_once()
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "last_login" in query
        assert "failed_login_attempts = 0" in query

    @pytest.mark.asyncio
    async def test_record_failed_login(self, user_repository, mock_db_client):
        """Record failed login increments counter."""
        mock_db_client.execute_single.return_value = {"attempts": 3}

        result = await user_repository.record_failed_login("user123")

        assert result == 3
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "failed_login_attempts + 1" in query

    @pytest.mark.asyncio
    async def test_set_lockout(self, user_repository, mock_db_client):
        """Set lockout updates lockout_until."""
        lockout_until = datetime.now(UTC) + timedelta(minutes=30)

        await user_repository.set_lockout("user123", lockout_until)

        mock_db_client.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_lockout(self, user_repository, mock_db_client):
        """Clear lockout resets lockout and failed attempts."""
        await user_repository.clear_lockout("user123")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "lockout_until = null" in query
        assert "failed_login_attempts = 0" in query

    @pytest.mark.asyncio
    async def test_username_exists_true(self, user_repository, mock_db_client):
        """Username exists returns True when found."""
        mock_db_client.execute_single.return_value = {"exists": True}

        result = await user_repository.username_exists("testuser")

        assert result is True

    @pytest.mark.asyncio
    async def test_username_exists_false(self, user_repository, mock_db_client):
        """Username exists returns False when not found."""
        mock_db_client.execute_single.return_value = {"exists": False}

        result = await user_repository.username_exists("newuser")

        assert result is False

    @pytest.mark.asyncio
    async def test_email_exists(self, user_repository, mock_db_client):
        """Email exists check works correctly."""
        mock_db_client.execute_single.return_value = {"exists": True}

        result = await user_repository.email_exists("test@example.com")

        assert result is True


# =============================================================================
# Refresh Token Tests
# =============================================================================


class TestUserRepositoryRefreshToken:
    """Tests for refresh token operations."""

    @pytest.mark.asyncio
    async def test_update_refresh_token_stores_hash(self, user_repository, mock_db_client):
        """Refresh token is stored as hash, not plain text."""
        mock_db_client.execute_single.return_value = {"id": "user123"}

        await user_repository.update_refresh_token("user123", "plain_refresh_token")

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]

        # Should be a hash, not the plain token
        assert params["refresh_token"] != "plain_refresh_token"
        assert len(params["refresh_token"]) == 64  # SHA-256 hex digest

    @pytest.mark.asyncio
    async def test_update_refresh_token_clear(self, user_repository, mock_db_client):
        """Clearing refresh token sets it to None."""
        mock_db_client.execute_single.return_value = {"id": "user123"}

        await user_repository.update_refresh_token("user123", None)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["refresh_token"] is None

    @pytest.mark.asyncio
    async def test_get_refresh_token(self, user_repository, mock_db_client):
        """Get stored refresh token hash."""
        stored_hash = "a" * 64
        mock_db_client.execute_single.return_value = {"refresh_token": stored_hash}

        result = await user_repository.get_refresh_token("user123")

        assert result == stored_hash

    @pytest.mark.asyncio
    async def test_validate_refresh_token_valid(self, user_repository, mock_db_client):
        """Valid refresh token validates successfully."""
        from forge.security.tokens import hash_refresh_token

        token = "valid_refresh_token"
        stored_hash = hash_refresh_token(token)
        mock_db_client.execute_single.return_value = {"refresh_token": stored_hash}

        result = await user_repository.validate_refresh_token("user123", token)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_refresh_token_invalid(self, user_repository, mock_db_client):
        """Invalid refresh token fails validation."""
        from forge.security.tokens import hash_refresh_token

        stored_hash = hash_refresh_token("original_token")
        mock_db_client.execute_single.return_value = {"refresh_token": stored_hash}

        result = await user_repository.validate_refresh_token("user123", "different_token")

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_refresh_token_no_stored_token(self, user_repository, mock_db_client):
        """No stored token fails validation."""
        mock_db_client.execute_single.return_value = {"refresh_token": None}

        result = await user_repository.validate_refresh_token("user123", "any_token")

        assert result is False


# =============================================================================
# Password Reset Token Tests
# =============================================================================


class TestUserRepositoryPasswordReset:
    """Tests for password reset token operations."""

    @pytest.mark.asyncio
    async def test_store_password_reset_token(self, user_repository, mock_db_client):
        """Store password reset token with hash."""
        mock_db_client.execute_single.return_value = {"id": "user123"}

        token_hash = hashlib.sha256("reset_token".encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        result = await user_repository.store_password_reset_token("user123", token_hash, expires_at)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "password_reset_token" in query
        assert "password_reset_expires" in query

    @pytest.mark.asyncio
    async def test_validate_password_reset_token_valid(self, user_repository, mock_db_client):
        """Valid reset token passes validation."""
        mock_db_client.execute_single.return_value = {"id": "user123"}

        token_hash = hashlib.sha256("reset_token".encode()).hexdigest()

        result = await user_repository.validate_password_reset_token("user123", token_hash)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_password_reset_token_invalid(self, user_repository, mock_db_client):
        """Invalid reset token fails validation."""
        mock_db_client.execute_single.return_value = None

        result = await user_repository.validate_password_reset_token("user123", "invalid_hash")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear_password_reset_token(self, user_repository, mock_db_client):
        """Clear password reset token."""
        await user_repository.clear_password_reset_token("user123")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "password_reset_token = null" in query
        assert "password_reset_expires = null" in query


# =============================================================================
# Trust Flame Tests
# =============================================================================


class TestUserRepositoryTrustFlame:
    """Tests for trust flame operations."""

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_increase(self, user_repository, mock_db_client):
        """Trust flame increase works correctly."""
        mock_db_client.execute_single.return_value = {
            "old_value": 60,
            "new_value": 70,
            "user_id": "user123",
        }

        result = await user_repository.adjust_trust_flame(
            user_id="user123",
            adjustment=10,
            reason="Good behavior",
            adjusted_by="admin456",
        )

        assert result is not None
        assert result.old_value == 60
        assert result.new_value == 70
        assert result.reason == "Good behavior"

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_decrease(self, user_repository, mock_db_client):
        """Trust flame decrease works correctly."""
        mock_db_client.execute_single.return_value = {
            "old_value": 60,
            "new_value": 50,
            "user_id": "user123",
        }

        result = await user_repository.adjust_trust_flame(
            user_id="user123",
            adjustment=-10,
            reason="Violation",
        )

        assert result.new_value == 50

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_clamped_min(self, user_repository, mock_db_client):
        """Trust flame doesn't go below 0."""
        mock_db_client.execute_single.return_value = {
            "old_value": 10,
            "new_value": 0,  # Clamped from -10
            "user_id": "user123",
        }

        result = await user_repository.adjust_trust_flame(
            user_id="user123",
            adjustment=-20,
            reason="Major violation",
        )

        # The query clamps to 0, so expect 0 from mock
        assert result.new_value >= 0

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_clamped_max(self, user_repository, mock_db_client):
        """Trust flame doesn't go above 100."""
        mock_db_client.execute_single.return_value = {
            "old_value": 95,
            "new_value": 100,  # Clamped from 105
            "user_id": "user123",
        }

        result = await user_repository.adjust_trust_flame(
            user_id="user123",
            adjustment=10,
            reason="Exceptional contribution",
        )

        assert result.new_value <= 100

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_not_found(self, user_repository, mock_db_client):
        """Adjustment returns None for non-existent user."""
        mock_db_client.execute_single.return_value = None

        result = await user_repository.adjust_trust_flame(
            user_id="nonexistent",
            adjustment=10,
            reason="Test",
        )

        assert result is None


# =============================================================================
# Account Status Tests
# =============================================================================


class TestUserRepositoryAccountStatus:
    """Tests for account status operations."""

    @pytest.mark.asyncio
    async def test_deactivate_user(self, user_repository, mock_db_client, sample_user_data):
        """Deactivate user sets is_active to False."""
        sample_user_data["is_active"] = False
        mock_db_client.execute_single.return_value = {"entity": sample_user_data}

        result = await user_repository.deactivate("user123")

        assert result is True

    @pytest.mark.asyncio
    async def test_activate_user(self, user_repository, mock_db_client, sample_user_data):
        """Activate user sets is_active to True."""
        sample_user_data["is_active"] = True
        mock_db_client.execute_single.return_value = {"entity": sample_user_data}

        result = await user_repository.activate("user123")

        assert result is True

    @pytest.mark.asyncio
    async def test_set_verified(self, user_repository, mock_db_client):
        """Set email verification status."""
        await user_repository.set_verified("user123", True)

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "is_verified" in query


# =============================================================================
# Safe User Model Tests
# =============================================================================


class TestUserRepositorySafeUser:
    """Tests for safe user model conversion."""

    def test_to_safe_user(self, user_repository):
        """Convert UserInDB to safe User model."""
        user_in_db = UserInDB(
            id="user123",
            username="testuser",
            email="test@example.com",
            display_name="Test User",
            password_hash="$2b$12$hash",
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            is_verified=True,
            auth_provider=AuthProvider.LOCAL,
            failed_login_attempts=0,
            lockout_until=None,
            refresh_token="token_hash",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        safe_user = user_repository.to_safe_user(user_in_db)

        assert safe_user.id == "user123"
        assert safe_user.username == "testuser"
        assert not hasattr(safe_user, "password_hash")
        assert not hasattr(safe_user, "refresh_token")


# =============================================================================
# Search Tests
# =============================================================================


class TestUserRepositorySearch:
    """Tests for user search operations."""

    @pytest.mark.asyncio
    async def test_search_by_username(self, user_repository, mock_db_client, sample_user_data):
        """Search finds users by username."""
        mock_db_client.execute.return_value = [{"user": sample_user_data}]

        result = await user_repository.search("test")

        assert len(result) == 1
        assert result[0].username == "testuser"

    @pytest.mark.asyncio
    async def test_search_with_limit(self, user_repository, mock_db_client, sample_user_data):
        """Search respects limit parameter."""
        mock_db_client.execute.return_value = [{"user": sample_user_data}]

        await user_repository.search("test", limit=5)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 5


# =============================================================================
# Cypher Injection Prevention Tests
# =============================================================================


class TestCypherInjectionPrevention:
    """
    SECURITY TESTS: Verify that user input is properly parameterized
    to prevent Cypher injection attacks.

    These tests ensure that malicious input cannot escape parameter context
    and execute arbitrary Cypher queries.
    """

    # Common injection payloads
    INJECTION_PAYLOADS = [
        # Basic injection attempts
        "'; DROP (n) //",
        "' OR '1'='1",
        "admin'--",
        "' UNION MATCH (n) RETURN n //",
        # Cypher-specific attacks
        "}) RETURN n // ",
        "', injection: 'value'}) RETURN n //",
        "test' OR 1=1 //",
        "'] MATCH (m) DETACH DELETE m //",
        # Property access attacks
        "test']})-[r]-() DELETE r //",
        "{{injection}}",
        "${injection}",
        # Unicode and encoding attacks
        "test\u0027; DROP (n)",
        "test%27; DROP (n)",
        # Comment attacks
        "test /* comment */ OR '1'='1",
        "test // comment",
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    async def test_get_by_username_injection(self, user_repository, mock_db_client, payload):
        """
        Verify get_by_username uses parameterized queries for username input.
        Injection payloads should be treated as literal string values, not Cypher.
        """
        mock_db_client.execute_single.return_value = None

        # This should NOT raise an error - payload should be safely parameterized
        result = await user_repository.get_by_username(payload)

        # Verify the call was made (not blocked/errored)
        mock_db_client.execute_single.assert_called_once()

        # Verify payload is passed as a parameter, not embedded in query
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # The payload should be in params, not directly in the query string
        assert payload not in query, (
            f"Payload '{payload[:20]}...' should not appear directly in query"
        )
        assert params.get("username") == payload, "Payload should be passed as a parameter"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    async def test_get_by_email_injection(self, user_repository, mock_db_client, payload):
        """
        Verify get_by_email uses parameterized queries for email input.
        """
        mock_db_client.execute_single.return_value = None

        # Convert payload to look like an email if it doesn't contain @
        email_payload = f"{payload}@test.com" if "@" not in payload else payload

        result = await user_repository.get_by_email(email_payload)

        mock_db_client.execute_single.assert_called_once()
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Injection payload should be parameterized, not in query
        assert payload not in query, f"Payload should not appear directly in query"
        assert email_payload in str(params.values()), "Email should be passed as a parameter"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    async def test_search_injection(self, user_repository, mock_db_client, payload):
        """
        Verify search uses parameterized queries for search term.
        """
        mock_db_client.execute.return_value = []

        result = await user_repository.search(payload)

        mock_db_client.execute.assert_called_once()
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Payload should not appear directly in query
        # Note: CONTAINS is used with parameter, not string interpolation
        assert payload not in query, "Search term should not be embedded in query"

    @pytest.mark.asyncio
    async def test_create_user_injection_in_username(
        self, user_repository, mock_db_client, sample_user_in_db_data
    ):
        """
        Verify user creation sanitizes username input.
        """
        mock_db_client.execute_single.return_value = {"user": sample_user_in_db_data}

        malicious_username = "admin'--; DROP (n)"

        try:
            user_create = UserCreate(
                username=malicious_username,
                email="test@example.com",
                password="SecureP@ss123!",
            )

            result = await user_repository.create(user_create, password_hash="$2b$12$hash")
        except Exception:
            pass  # Pydantic validation or DB layer might reject the username, which is fine

        # If called, verify parameterization
        if mock_db_client.execute_single.called:
            call_args = mock_db_client.execute_single.call_args
            query = call_args[0][0]

            # Malicious payload should not be in query
            assert "DROP" not in query.upper() or "DROP" in str(
                mock_db_client.execute_single.call_args[0][1].values()
            )

    @pytest.mark.asyncio
    async def test_adjust_trust_flame_injection_in_reason(self, user_repository, mock_db_client):
        """
        Verify trust flame adjustment sanitizes reason parameter.
        """
        mock_db_client.execute_single.return_value = {
            "old_value": 60,
            "new_value": 70,
            "user_id": "user123",
        }

        malicious_reason = "Good behavior'); MATCH (n) DETACH DELETE n //"

        result = await user_repository.adjust_trust_flame(
            user_id="user123",
            adjustment=10,
            reason=malicious_reason,
        )

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]

        # DELETE should not appear in query (it should be in params)
        assert "DETACH DELETE" not in query, "Injection attempt should be parameterized"

    @pytest.mark.asyncio
    async def test_get_by_id_uuid_injection(self, user_repository, mock_db_client):
        """
        Verify get_by_id handles malicious ID input safely.
        """
        mock_db_client.execute_single.return_value = None

        malicious_id = "user123'}) MATCH (n) DETACH DELETE n //"

        result = await user_repository.get_by_id(malicious_id)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify ID is parameterized
        assert "DETACH DELETE" not in query
        assert params.get("id") == malicious_id or params.get("user_id") == malicious_id

    @pytest.mark.asyncio
    async def test_update_user_injection_in_display_name(
        self, user_repository, mock_db_client, sample_user_data
    ):
        """
        Verify update sanitizes display_name input.
        """
        sample_user_data["display_name"] = "Injected Name"
        mock_db_client.execute_single.return_value = {"user": sample_user_data}

        malicious_name = "Name'}) MATCH (n) SET n.role='admin' //"

        update = UserUpdate(display_name=malicious_name)
        result = await user_repository.update("user123", update)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]

        # SET n.role='admin' should not appear in query
        assert "n.role='admin'" not in query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
