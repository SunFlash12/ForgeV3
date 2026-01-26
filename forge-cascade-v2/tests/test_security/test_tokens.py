"""
Token Management Tests for Forge Cascade V2

Comprehensive tests for JWT token handling including:
- Token creation (access and refresh)
- Token validation and verification
- Token blacklisting
- Key rotation
- Token hashing utilities
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from forge.security.tokens import (
    ALLOWED_JWT_ALGORITHMS,
    KeyRotationManager,
    TokenBlacklist,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenService,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    extract_token_from_header,
    get_token_claims,
    get_token_expiry,
    hash_refresh_token,
    is_token_expired,
    verify_access_token,
    verify_refresh_token,
    verify_refresh_token_hash,
    verify_token,
)


# =============================================================================
# Token Creation Tests
# =============================================================================


class TestTokenCreation:
    """Tests for token creation functions."""

    def test_create_access_token_basic(self):
        """Access token creation with basic parameters."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert token
        assert isinstance(token, str)
        # JWT has three parts separated by dots
        assert len(token.split(".")) == 3

    def test_create_access_token_with_claims(self):
        """Access token with additional claims."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="admin",
            trust_flame=80,
            additional_claims={"custom": "value"},
        )

        payload = decode_token(token)
        assert payload.sub == "user123"
        assert str(payload.role) == "admin"
        assert payload.trust_flame == 80

    def test_create_refresh_token(self):
        """Refresh token creation."""
        token = create_refresh_token(
            user_id="user123",
            username="testuser",
        )

        assert token
        payload = decode_token(token)
        assert payload.sub == "user123"
        assert payload.type == "refresh"

    def test_create_token_pair(self):
        """Token pair creation."""
        token_pair = create_token_pair(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert token_pair.access_token
        assert token_pair.refresh_token
        assert token_pair.token_type == "bearer"
        assert token_pair.expires_in > 0

    def test_access_token_includes_jti(self):
        """Access token includes JTI for revocation."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        payload = decode_token(token)
        assert payload.jti is not None
        assert len(payload.jti) > 0

    def test_refresh_token_includes_jti(self):
        """Refresh token includes JTI."""
        token = create_refresh_token(
            user_id="user123",
            username="testuser",
        )

        payload = decode_token(token)
        assert payload.jti is not None


# =============================================================================
# Token Validation Tests
# =============================================================================


class TestTokenValidation:
    """Tests for token validation functions."""

    def test_verify_access_token_valid(self):
        """Valid access token passes verification."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        payload = verify_access_token(token)
        assert payload.sub == "user123"
        assert payload.type == "access"

    def test_verify_access_token_wrong_type(self):
        """Refresh token fails access token verification."""
        token = create_refresh_token(
            user_id="user123",
            username="testuser",
        )

        with pytest.raises(TokenInvalidError, match="Not an access token"):
            verify_access_token(token)

    def test_verify_refresh_token_valid(self):
        """Valid refresh token passes verification."""
        token = create_refresh_token(
            user_id="user123",
            username="testuser",
        )

        payload = verify_refresh_token(token)
        assert payload.sub == "user123"
        assert payload.type == "refresh"

    def test_verify_refresh_token_wrong_type(self):
        """Access token fails refresh token verification."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        with pytest.raises(TokenInvalidError, match="Not a refresh token"):
            verify_refresh_token(token)

    def test_decode_token_invalid(self):
        """Invalid token raises error."""
        with pytest.raises(TokenInvalidError):
            decode_token("invalid.token.here")

    def test_decode_token_malformed(self):
        """Malformed token raises error."""
        with pytest.raises(TokenInvalidError):
            decode_token("not-even-a-jwt")

    def test_verify_token_expected_type(self):
        """Token verification with expected type."""
        access = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )
        refresh = create_refresh_token(
            user_id="user123",
            username="testuser",
        )

        # Access token with access type
        verify_token(access, expected_type="access")

        # Refresh token with refresh type
        verify_token(refresh, expected_type="refresh")

        # Wrong type should fail
        with pytest.raises(TokenInvalidError):
            verify_token(access, expected_type="refresh")

    def test_access_token_requires_trust_flame(self):
        """Access token verification requires trust_flame claim."""
        # Clean up any cached/singleton state
        TokenBlacklist.clear()

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        # This should pass
        payload = verify_access_token(token)
        assert payload.trust_flame == 60

    def test_access_token_validates_trust_flame_range(self):
        """Access token validation checks trust_flame bounds."""
        # Create a token with invalid trust_flame by manipulating the payload
        import jwt as pyjwt
        from forge.config import get_settings

        settings = get_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": "user123",
            "username": "testuser",
            "role": "user",
            "trust_flame": 150,  # Invalid - exceeds 100
            "exp": now + timedelta(hours=1),
            "iat": now,
            "nbf": now,
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }

        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        with pytest.raises(TokenInvalidError, match="Invalid trust_flame"):
            verify_access_token(token)


# =============================================================================
# Token Blacklist Tests
# =============================================================================


class TestTokenBlacklist:
    """Tests for token blacklist functionality."""

    def setup_method(self):
        """Clear blacklist before each test."""
        TokenBlacklist.clear()

    def teardown_method(self):
        """Clear blacklist after each test."""
        TokenBlacklist.clear()

    def test_add_and_check_blacklist(self):
        """Token can be added and checked in blacklist."""
        jti = "test-jti-123"
        expires_at = time.time() + 3600

        TokenBlacklist.add(jti, expires_at)
        assert TokenBlacklist.is_blacklisted(jti) is True

    def test_non_blacklisted_token(self):
        """Non-blacklisted token returns False."""
        assert TokenBlacklist.is_blacklisted("not-in-list") is False

    def test_blacklist_with_none_jti(self):
        """None JTI returns False."""
        assert TokenBlacklist.is_blacklisted(None) is False

    def test_remove_from_blacklist(self):
        """Token can be removed from blacklist."""
        jti = "test-jti-456"
        TokenBlacklist.add(jti, time.time() + 3600)
        TokenBlacklist.remove(jti)

        assert TokenBlacklist.is_blacklisted(jti) is False

    def test_blacklist_adds_all(self):
        """Blacklist adds all tokens (security > memory)."""
        # Add many tokens
        for i in range(TokenBlacklist._MAX_BLACKLIST_SIZE + 100):
            TokenBlacklist.add(f"jti_{i}", time.time() + 3600)

        # Security > memory: all tokens are added even beyond max size
        assert len(TokenBlacklist._blacklist) >= TokenBlacklist._MAX_BLACKLIST_SIZE
        # Verify last token is blacklisted
        assert TokenBlacklist.is_blacklisted(f"jti_{TokenBlacklist._MAX_BLACKLIST_SIZE + 99}")

    @pytest.mark.asyncio
    async def test_async_add_and_check(self):
        """Async blacklist operations work."""
        jti = "async-test-jti"
        expires_at = time.time() + 3600

        await TokenBlacklist.add_async(jti, expires_at)
        is_blacklisted = await TokenBlacklist.is_blacklisted_async(jti)

        assert is_blacklisted is True

    @pytest.mark.asyncio
    async def test_async_remove(self):
        """Async remove works."""
        jti = "async-remove-jti"
        await TokenBlacklist.add_async(jti, time.time() + 3600)
        await TokenBlacklist.remove_async(jti)

        is_blacklisted = await TokenBlacklist.is_blacklisted_async(jti)
        assert is_blacklisted is False

    def test_blacklisted_token_rejected(self):
        """Blacklisted token fails verification."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        payload = decode_token(token)
        TokenBlacklist.add(payload.jti, time.time() + 3600)

        with pytest.raises(TokenInvalidError, match="revoked"):
            verify_access_token(token)


# =============================================================================
# Token Utility Tests
# =============================================================================


class TestTokenUtilities:
    """Tests for token utility functions."""

    def test_extract_token_from_header_valid(self):
        """Extract token from valid Authorization header."""
        token = "valid.jwt.token"
        header = f"Bearer {token}"

        extracted = extract_token_from_header(header)
        assert extracted == token

    def test_extract_token_from_header_invalid_format(self):
        """Invalid header format raises error."""
        with pytest.raises(TokenInvalidError, match="Invalid authorization header"):
            extract_token_from_header("InvalidFormat")

    def test_extract_token_from_header_wrong_scheme(self):
        """Wrong auth scheme raises error."""
        with pytest.raises(TokenInvalidError, match="Invalid authentication scheme"):
            extract_token_from_header("Basic sometoken")

    def test_get_token_expiry(self):
        """Get token expiry time."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        expiry = get_token_expiry(token)
        assert expiry is not None
        assert expiry > datetime.now(UTC)

    def test_is_token_expired_valid(self):
        """Valid token is not expired."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert is_token_expired(token) is False

    def test_is_token_expired_invalid(self):
        """Invalid token is considered expired."""
        assert is_token_expired("invalid.token") is True

    def test_get_token_claims(self):
        """Extract claims from token."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        claims = get_token_claims(token)
        assert claims["sub"] == "user123"
        assert claims["username"] == "testuser"
        assert "jti" in claims


# =============================================================================
# Refresh Token Hashing Tests
# =============================================================================


class TestRefreshTokenHashing:
    """Tests for refresh token hash utilities."""

    def test_hash_refresh_token(self):
        """Refresh token hashing produces consistent hash."""
        token = "test-refresh-token-123"

        hash1 = hash_refresh_token(token)
        hash2 = hash_refresh_token(token)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_verify_refresh_token_hash_valid(self):
        """Valid token verifies against its hash."""
        token = "test-refresh-token-456"
        token_hash = hash_refresh_token(token)

        assert verify_refresh_token_hash(token, token_hash) is True

    def test_verify_refresh_token_hash_invalid(self):
        """Invalid token fails hash verification."""
        token = "test-refresh-token-789"
        token_hash = hash_refresh_token(token)

        assert verify_refresh_token_hash("different-token", token_hash) is False

    def test_hash_different_tokens_different_hashes(self):
        """Different tokens produce different hashes."""
        hash1 = hash_refresh_token("token-a")
        hash2 = hash_refresh_token("token-b")

        assert hash1 != hash2


# =============================================================================
# Key Rotation Tests
# =============================================================================


class TestKeyRotation:
    """Tests for JWT key rotation functionality."""

    def setup_method(self):
        """Reset key rotation manager before each test."""
        KeyRotationManager._keys.clear()
        KeyRotationManager._key_created_at.clear()
        KeyRotationManager._current_key_id = "default"

    def test_initialize_creates_default_key(self):
        """Initialization creates default key from settings."""
        KeyRotationManager.initialize()

        assert len(KeyRotationManager._keys) >= 1
        assert KeyRotationManager._current_key_id in KeyRotationManager._keys

    def test_get_current_key(self):
        """Get current key returns key ID and secret."""
        key_id, secret = KeyRotationManager.get_current_key()

        assert key_id is not None
        assert secret is not None
        assert len(secret) >= 32

    def test_get_all_keys(self):
        """Get all keys returns list of secrets."""
        keys = KeyRotationManager.get_all_keys()

        assert len(keys) >= 1
        assert all(isinstance(k, str) for k in keys)

    @pytest.mark.asyncio
    async def test_rotate_key(self):
        """Key rotation adds new key and updates current."""
        KeyRotationManager.initialize()
        old_key_id = KeyRotationManager._current_key_id

        new_secret = "new-secret-key-at-least-32-characters-long"
        new_key_id = await KeyRotationManager.rotate_key(new_secret)

        assert new_key_id != old_key_id
        assert KeyRotationManager._current_key_id == new_key_id
        assert new_secret in KeyRotationManager.get_all_keys()

    @pytest.mark.asyncio
    async def test_rotate_key_short_secret_fails(self):
        """Key rotation fails with short secret."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            await KeyRotationManager.rotate_key("short")

    def test_decode_with_rotation_current_key(self):
        """Decode works with current key."""
        from forge.config import get_settings

        settings = get_settings()
        KeyRotationManager.initialize()

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        payload = KeyRotationManager.decode_with_rotation(
            token,
            algorithms=ALLOWED_JWT_ALGORITHMS,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )

        assert payload["sub"] == "user123"

    def test_get_rotation_status(self):
        """Get rotation status returns info dict."""
        KeyRotationManager.initialize()
        status = KeyRotationManager.get_rotation_status()

        assert "current_key_id" in status
        assert "total_keys" in status
        assert "key_ids" in status
        assert "key_ages" in status


# =============================================================================
# Token Service Class Tests
# =============================================================================


class TestTokenService:
    """Tests for TokenService class interface."""

    def test_service_create_access_token(self):
        """TokenService creates access token."""
        token = TokenService.create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert token
        payload = decode_token(token)
        assert payload.sub == "user123"

    def test_service_create_token_pair(self):
        """TokenService creates token pair."""
        token = TokenService.create_token_pair(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert token.access_token
        assert token.refresh_token

    def test_service_verify_access_token(self):
        """TokenService verifies access token."""
        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        # Clear any blacklist entries
        TokenBlacklist.clear()

        payload = TokenService.verify_access_token(token)
        assert payload.sub == "user123"

    def test_service_is_expired(self):
        """TokenService checks expiration."""
        valid_token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        assert TokenService.is_expired(valid_token) is False
        assert TokenService.is_expired("invalid.token") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
