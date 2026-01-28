"""
FastAPI Security Dependencies Tests for Forge Cascade V2

Comprehensive tests for security dependency injection including:
- Token extraction from requests
- Authorization context creation
- Trust level enforcement
- Role-based access control
- Capability-based access control
- Resource access checking
- IP address extraction
- Authenticated request composite
"""

import ipaddress
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from forge.models.base import TrustLevel
from forge.models.overlay import Capability
from forge.models.user import UserRole
from forge.security.authorization import create_auth_context
from forge.security.dependencies import (
    TRUSTED_PROXY_RANGES,
    AuthenticatedRequest,
    ResourceAccessChecker,
    _is_trusted_proxy,
    _is_valid_ip,
    get_auth_context,
    get_client_ip,
    get_current_user_id,
    get_optional_auth_context,
    get_token,
    get_user_agent,
    require_all_capabilities_dep,
    require_any_capability_dep,
    require_capability_dep,
    require_role_dep,
    require_trust,
)

# =============================================================================
# Token Extraction Tests
# =============================================================================


class TestGetToken:
    """Tests for token extraction from HTTP credentials."""

    @pytest.mark.asyncio
    async def test_get_token_with_credentials(self):
        """Token is extracted when credentials are provided."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "test-token-123"

        token = await get_token(mock_credentials)
        assert token == "test-token-123"

    @pytest.mark.asyncio
    async def test_get_token_without_credentials(self):
        """Returns None when no credentials provided."""
        token = await get_token(None)
        assert token is None


# =============================================================================
# Optional Auth Context Tests
# =============================================================================


class TestGetOptionalAuthContext:
    """Tests for optional authorization context extraction."""

    @pytest.mark.asyncio
    async def test_returns_none_without_token(self):
        """Returns None when no token is provided."""
        context = await get_optional_auth_context(None)
        assert context is None

    @pytest.mark.asyncio
    async def test_returns_context_with_valid_token(self):
        """Returns auth context with valid token."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        context = await get_optional_auth_context(token)
        assert context is not None
        assert context.user_id == "user123"
        assert context.trust_flame == 60

    @pytest.mark.asyncio
    async def test_returns_none_with_invalid_token(self):
        """Returns None with invalid token."""
        context = await get_optional_auth_context("invalid.token.here")
        assert context is None

    @pytest.mark.asyncio
    async def test_returns_none_with_expired_token(self):
        """Returns None with expired token."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from forge.config import get_settings

        settings = get_settings()
        past_time = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "sub": "user123",
            "username": "testuser",
            "role": "user",
            "trust_flame": 60,
            "exp": past_time,
            "iat": past_time - timedelta(hours=1),
            "nbf": past_time - timedelta(hours=1),
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        context = await get_optional_auth_context(token)
        assert context is None

    @pytest.mark.asyncio
    async def test_rejects_token_missing_trust_flame(self):
        """SECURITY FIX: Rejects tokens missing trust_flame claim."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from forge.config import get_settings

        settings = get_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": "user123",
            "username": "testuser",
            "role": "user",
            # Missing trust_flame claim
            "exp": now + timedelta(hours=1),
            "iat": now,
            "nbf": now,
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        context = await get_optional_auth_context(token)
        assert context is None

    @pytest.mark.asyncio
    async def test_rejects_token_missing_role(self):
        """SECURITY FIX: Rejects tokens missing role claim."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from forge.config import get_settings

        settings = get_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": "user123",
            "username": "testuser",
            # Missing role claim
            "trust_flame": 60,
            "exp": now + timedelta(hours=1),
            "iat": now,
            "nbf": now,
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        context = await get_optional_auth_context(token)
        assert context is None


# =============================================================================
# Required Auth Context Tests
# =============================================================================


class TestGetAuthContext:
    """Tests for required authorization context extraction."""

    @pytest.mark.asyncio
    async def test_raises_401_without_token(self):
        """Raises 401 when no token is provided."""
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_returns_context_with_valid_token(self):
        """Returns auth context with valid token."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        context = await get_auth_context(token)
        assert context.user_id == "user123"

    @pytest.mark.asyncio
    async def test_raises_401_with_invalid_token(self):
        """Raises 401 with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context("invalid.token.here")

        assert exc_info.value.status_code == 401
        assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.asyncio
    async def test_raises_401_with_expired_token(self):
        """Raises 401 with expired token."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from forge.config import get_settings

        settings = get_settings()
        past_time = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "sub": "user123",
            "username": "testuser",
            "role": "user",
            "trust_flame": 60,
            "exp": past_time,
            "iat": past_time - timedelta(hours=1),
            "nbf": past_time - timedelta(hours=1),
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_with_missing_trust_flame(self):
        """SECURITY FIX: Raises 401 for tokens missing trust_flame claim."""
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from forge.config import get_settings

        settings = get_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": "user123",
            "username": "testuser",
            "role": "user",
            # Missing trust_flame claim
            "exp": now + timedelta(hours=1),
            "iat": now,
            "nbf": now,
            "jti": "test-jti",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_generic_error_message_for_invalid_token(self):
        """SECURITY FIX: Generic error message prevents token format leakage."""
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context("invalid-but-looks-like-jwt")

        # Should not reveal details about why token was invalid
        assert "Invalid authentication token" in exc_info.value.detail


# =============================================================================
# Get Current User ID Tests
# =============================================================================


class TestGetCurrentUserId:
    """Tests for current user ID extraction."""

    @pytest.mark.asyncio
    async def test_returns_user_id(self):
        """Returns user ID from auth context."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
        )

        user_id = await get_current_user_id(auth_context)
        assert user_id == "user123"


# =============================================================================
# Trust Level Dependency Tests
# =============================================================================


class TestRequireTrust:
    """Tests for trust level enforcement dependency."""

    @pytest.mark.asyncio
    async def test_passes_with_sufficient_trust(self):
        """Passes when user has sufficient trust level."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,  # STANDARD level
        )

        # Create the dependency
        dependency = require_trust(TrustLevel.STANDARD)

        # Get auth context
        auth_context = await get_auth_context(token)

        # Call dependency
        result = await dependency(auth_context)
        assert result.user_id == "user123"

    @pytest.mark.asyncio
    async def test_passes_with_higher_trust(self):
        """Passes when user has higher trust level than required."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=80,  # TRUSTED level
        )

        dependency = require_trust(TrustLevel.STANDARD)
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_with_insufficient_trust(self):
        """Raises 403 when trust level is insufficient."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=40,  # SANDBOX level
        )

        dependency = require_trust(TrustLevel.TRUSTED)
        auth_context = await get_auth_context(token)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(auth_context)

        assert exc_info.value.status_code == 403
        assert "TRUSTED" in exc_info.value.detail


# =============================================================================
# Role Dependency Tests
# =============================================================================


class TestRequireRole:
    """Tests for role-based access control dependency."""

    @pytest.mark.asyncio
    async def test_passes_with_required_role(self):
        """Passes when user has the required role."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="admin123",
            username="adminuser",
            role="admin",
            trust_flame=60,
        )

        dependency = require_role_dep(UserRole.ADMIN)
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_passes_with_higher_role(self):
        """Passes when user has a higher role than required."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="admin123",
            username="adminuser",
            role="admin",
            trust_flame=60,
        )

        dependency = require_role_dep(UserRole.MODERATOR)
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_with_insufficient_role(self):
        """Raises 403 when role is insufficient."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        dependency = require_role_dep(UserRole.ADMIN)
        auth_context = await get_auth_context(token)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(auth_context)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail


# =============================================================================
# Capability Dependency Tests
# =============================================================================


class TestRequireCapability:
    """Tests for capability-based access control dependency."""

    @pytest.mark.asyncio
    async def test_passes_with_required_capability(self):
        """Passes when user has required capability."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,  # STANDARD has CAPSULE_READ and CAPSULE_WRITE
        )

        dependency = require_capability_dep(Capability.CAPSULE_READ)
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_without_capability(self):
        """Raises 403 without required capability."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=40,  # SANDBOX doesn't have GOVERNANCE_EXECUTE
        )

        dependency = require_capability_dep(Capability.GOVERNANCE_EXECUTE)
        auth_context = await get_auth_context(token)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(auth_context)

        assert exc_info.value.status_code == 403


class TestRequireAnyCapability:
    """Tests for any-capability dependency."""

    @pytest.mark.asyncio
    async def test_passes_with_one_matching_capability(self):
        """Passes when user has at least one required capability."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,  # Has CAPSULE_READ
        )

        dependency = require_any_capability_dep(
            Capability.CAPSULE_READ, Capability.GOVERNANCE_EXECUTE
        )
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_without_any_capability(self):
        """Raises 403 without any required capability."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=40,  # SANDBOX - limited capabilities
        )

        dependency = require_any_capability_dep(
            Capability.GOVERNANCE_EXECUTE, Capability.CAPSULE_DELETE
        )
        auth_context = await get_auth_context(token)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(auth_context)

        assert exc_info.value.status_code == 403


class TestRequireAllCapabilities:
    """Tests for all-capabilities dependency."""

    @pytest.mark.asyncio
    async def test_passes_with_all_capabilities(self):
        """Passes when user has all required capabilities."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,  # STANDARD has CAPSULE_READ, CAPSULE_WRITE, DATABASE_READ
        )

        dependency = require_all_capabilities_dep(Capability.CAPSULE_READ, Capability.CAPSULE_WRITE)
        auth_context = await get_auth_context(token)

        result = await dependency(auth_context)
        assert result is not None

    @pytest.mark.asyncio
    async def test_raises_403_missing_some_capabilities(self):
        """Raises 403 when missing some required capabilities."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        dependency = require_all_capabilities_dep(
            Capability.CAPSULE_READ, Capability.GOVERNANCE_EXECUTE
        )
        auth_context = await get_auth_context(token)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(auth_context)

        assert exc_info.value.status_code == 403
        assert "Missing capabilities" in exc_info.value.detail


# =============================================================================
# Resource Access Checker Tests
# =============================================================================


class TestResourceAccessChecker:
    """Tests for resource access checking."""

    @pytest.mark.asyncio
    async def test_owner_can_access_own_resource(self):
        """Owner can access their own resource."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )
        auth_context = await get_auth_context(token)

        resource = MagicMock()
        resource.owner_id = "user123"

        checker = ResourceAccessChecker(get_owner_id=lambda r: r.owner_id, require_ownership=True)

        result = await checker(resource, auth_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_non_owner_blocked_with_ownership_required(self):
        """Non-owner blocked when ownership is required."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,
        )
        auth_context = await get_auth_context(token)

        resource = MagicMock()
        resource.owner_id = "other456"

        checker = ResourceAccessChecker(get_owner_id=lambda r: r.owner_id, require_ownership=True)

        with pytest.raises(HTTPException) as exc_info:
            await checker(resource, auth_context)

        assert exc_info.value.status_code == 403
        assert "don't own" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_can_access_any_resource_with_ownership_required(self):
        """Admin can access any resource even with ownership required."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="admin123",
            username="adminuser",
            role="admin",
            trust_flame=60,
        )
        auth_context = await get_auth_context(token)

        resource = MagicMock()
        resource.owner_id = "other456"

        checker = ResourceAccessChecker(get_owner_id=lambda r: r.owner_id, require_ownership=True)

        result = await checker(resource, auth_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_access_by_trust_level(self):
        """User can access resource by trust level."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=80,  # TRUSTED
        )
        auth_context = await get_auth_context(token)

        resource = MagicMock()
        resource.owner_id = "other456"
        resource.trust_level = TrustLevel.TRUSTED

        checker = ResourceAccessChecker(
            get_owner_id=lambda r: r.owner_id,
            get_trust_level=lambda r: r.trust_level,
        )

        result = await checker(resource, auth_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocked_by_insufficient_trust(self):
        """User blocked by insufficient trust level."""
        from forge.security.tokens import create_access_token

        token = create_access_token(
            user_id="user123",
            username="testuser",
            role="user",
            trust_flame=60,  # STANDARD
        )
        auth_context = await get_auth_context(token)

        resource = MagicMock()
        resource.owner_id = "other456"
        resource.trust_level = TrustLevel.CORE

        checker = ResourceAccessChecker(
            get_owner_id=lambda r: r.owner_id,
            get_trust_level=lambda r: r.trust_level,
        )

        with pytest.raises(HTTPException) as exc_info:
            await checker(resource, auth_context)

        assert exc_info.value.status_code == 403
        assert "Insufficient access" in exc_info.value.detail


# =============================================================================
# IP Address Validation Tests
# =============================================================================


class TestIPValidation:
    """Tests for IP address validation utilities."""

    @pytest.mark.parametrize(
        "ip,expected",
        [
            ("192.168.1.1", True),
            ("10.0.0.1", True),
            ("172.16.0.1", True),
            ("8.8.8.8", True),
            ("::1", True),
            ("2001:db8::1", True),
            ("invalid", False),
            ("256.256.256.256", False),
            ("", False),
            ("not.an.ip", False),
        ],
    )
    def test_is_valid_ip(self, ip, expected):
        """Tests IP address validation."""
        assert _is_valid_ip(ip) == expected

    @pytest.mark.parametrize(
        "ip,expected",
        [
            ("10.0.0.1", True),  # Private class A
            ("10.255.255.255", True),
            ("172.16.0.1", True),  # Private class B
            ("172.31.255.255", True),
            ("192.168.1.1", True),  # Private class C
            ("192.168.255.255", True),
            ("127.0.0.1", True),  # Loopback
            ("::1", True),  # IPv6 loopback
            ("8.8.8.8", False),  # Public
            ("1.1.1.1", False),  # Public
            ("172.32.0.1", False),  # Outside private class B range
            ("invalid", False),  # Invalid IP
        ],
    )
    def test_is_trusted_proxy(self, ip, expected):
        """Tests trusted proxy range checking."""
        assert _is_trusted_proxy(ip) == expected


class TestGetClientIP:
    """Tests for client IP extraction."""

    @pytest.mark.asyncio
    async def test_direct_ip_from_untrusted_source(self):
        """Uses direct IP when connection is from untrusted source."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "203.0.113.1"  # Public IP
        request.headers = {"X-Forwarded-For": "10.0.0.1"}  # Spoofed header

        ip = await get_client_ip(request)
        assert ip == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_forwarded_ip_from_trusted_proxy(self):
        """Uses X-Forwarded-For when connection is from trusted proxy."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda h, d=None: {"X-Forwarded-For": "203.0.113.50"}.get(h, d)
        )

        ip = await get_client_ip(request)
        assert ip == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_chain_processing(self):
        """Processes X-Forwarded-For chain to find first non-proxy IP."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda h, d=None: {
                "X-Forwarded-For": "203.0.113.50, 10.0.0.5, 10.0.0.1"
            }.get(h, d)
        )

        ip = await get_client_ip(request)
        # Should return the first non-proxy IP from the right
        assert ip == "203.0.113.50"

    @pytest.mark.asyncio
    async def test_x_real_ip_fallback(self):
        """Falls back to X-Real-IP when X-Forwarded-For is missing."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "10.0.0.1"  # Trusted proxy
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda h, d=None: {"X-Real-IP": "203.0.113.75"}.get(h, d)
        )

        ip = await get_client_ip(request)
        assert ip == "203.0.113.75"

    @pytest.mark.asyncio
    async def test_no_client_returns_none(self):
        """Returns None when no client info available."""
        request = MagicMock()
        request.client = None
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        ip = await get_client_ip(request)
        assert ip is None


# =============================================================================
# User Agent Extraction Tests
# =============================================================================


class TestGetUserAgent:
    """Tests for user agent extraction."""

    @pytest.mark.asyncio
    async def test_extracts_user_agent(self):
        """Extracts User-Agent header."""
        request = MagicMock()
        request.headers = {"User-Agent": "Mozilla/5.0 TestBrowser"}

        ua = await get_user_agent(request)
        assert ua == "Mozilla/5.0 TestBrowser"

    @pytest.mark.asyncio
    async def test_returns_none_without_user_agent(self):
        """Returns None when User-Agent is missing."""
        request = MagicMock()
        request.headers = {}

        ua = await get_user_agent(request)
        assert ua is None


# =============================================================================
# Authenticated Request Composite Tests
# =============================================================================


class TestAuthenticatedRequest:
    """Tests for the AuthenticatedRequest composite dependency."""

    def test_creates_authenticated_request(self):
        """AuthenticatedRequest contains all required fields."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address="192.168.1.100",
            user_agent="TestBrowser/1.0",
        )

        assert req.user_id == "user123"
        assert req.trust_flame == 60
        assert req.trust_level == TrustLevel.STANDARD
        assert req.role == UserRole.USER
        assert req.ip_address == "192.168.1.100"
        assert req.user_agent == "TestBrowser/1.0"

    def test_has_trust_method(self):
        """has_trust method delegates to auth context."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=80,  # TRUSTED
            role="user",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address=None,
            user_agent=None,
        )

        assert req.has_trust(TrustLevel.STANDARD) is True
        assert req.has_trust(TrustLevel.TRUSTED) is True
        assert req.has_trust(TrustLevel.CORE) is False

    def test_has_role_method(self):
        """has_role method delegates to auth context."""
        auth_context = create_auth_context(
            user_id="mod123",
            trust_flame=60,
            role="moderator",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address=None,
            user_agent=None,
        )

        assert req.has_role(UserRole.USER) is True
        assert req.has_role(UserRole.MODERATOR) is True
        assert req.has_role(UserRole.ADMIN) is False

    def test_has_capability_method(self):
        """has_capability method delegates to auth context."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=60,  # STANDARD
            role="user",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address=None,
            user_agent=None,
        )

        assert req.has_capability(Capability.CAPSULE_READ) is True
        assert req.has_capability(Capability.GOVERNANCE_EXECUTE) is False

    def test_can_access_resource_method(self):
        """can_access_resource method delegates to auth context."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address=None,
            user_agent=None,
        )

        # Can access own resource
        assert req.can_access_resource(TrustLevel.CORE, "user123") is True
        # Cannot access CORE resource owned by others
        assert req.can_access_resource(TrustLevel.CORE, "other456") is False

    def test_can_modify_resource_method(self):
        """can_modify_resource method delegates to auth context."""
        auth_context = create_auth_context(
            user_id="user123",
            trust_flame=60,
            role="user",
        )

        req = AuthenticatedRequest(
            auth=auth_context,
            ip_address=None,
            user_agent=None,
        )

        assert req.can_modify_resource("user123") is True
        assert req.can_modify_resource("other456") is False


# =============================================================================
# Trusted Proxy Ranges Tests
# =============================================================================


class TestTrustedProxyRanges:
    """Tests for trusted proxy range configuration."""

    def test_trusted_proxy_ranges_contain_private_ranges(self):
        """Trusted proxy ranges contain standard private IP ranges."""
        assert "10.0.0.0/8" in TRUSTED_PROXY_RANGES
        assert "172.16.0.0/12" in TRUSTED_PROXY_RANGES
        assert "192.168.0.0/16" in TRUSTED_PROXY_RANGES
        assert "127.0.0.0/8" in TRUSTED_PROXY_RANGES

    def test_trusted_proxy_ranges_contain_ipv6(self):
        """Trusted proxy ranges contain IPv6 loopback and private."""
        assert "::1/128" in TRUSTED_PROXY_RANGES
        assert "fd00::/8" in TRUSTED_PROXY_RANGES

    def test_all_ranges_are_valid(self):
        """All trusted proxy ranges are valid IP networks."""
        for range_str in TRUSTED_PROXY_RANGES:
            network = ipaddress.ip_network(range_str, strict=False)
            assert network is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
