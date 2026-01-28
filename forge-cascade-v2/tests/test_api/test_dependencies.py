"""
Forge Cascade V2 - Dependency Injection Tests

Comprehensive tests for FastAPI dependency injection:
- Settings dependencies
- Database client injection
- Repository dependencies
- Kernel component access
- Immune system access
- Authentication/Authorization dependencies
- Pagination
- Client info extraction
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from forge.models.base import TrustLevel
from forge.models.user import AuthProvider, User, UserRole

# =============================================================================
# Settings Dependency Tests
# =============================================================================


class TestSettingsDependency:
    """Tests for settings dependency injection."""

    def test_get_app_settings_returns_settings(self):
        """Test get_app_settings returns settings object."""
        from forge.api.dependencies import get_app_settings

        settings = get_app_settings()
        assert settings is not None

    def test_settings_has_expected_attributes(self):
        """Test settings has expected attributes."""
        from forge.api.dependencies import get_app_settings

        settings = get_app_settings()
        assert hasattr(settings, "app_env")
        assert hasattr(settings, "jwt_secret_key")


# =============================================================================
# ForgeApp Access Tests
# =============================================================================


class TestForgeAppAccess:
    """Tests for ForgeApp access dependency."""

    def test_get_forge_app_returns_forge_instance(self, app):
        """Test get_forge_app returns ForgeApp from state."""
        from forge.api.dependencies import get_forge_app

        mock_request = MagicMock(spec=Request)
        mock_request.app = app

        result = get_forge_app(mock_request)
        assert result is not None

    def test_get_forge_app_raises_503_when_not_initialized(self):
        """Test get_forge_app raises 503 when not initialized."""
        from forge.api.dependencies import get_forge_app

        mock_request = MagicMock(spec=Request)
        mock_request.app.state = MagicMock(spec=[])  # No 'forge' attribute

        with pytest.raises(HTTPException) as exc_info:
            get_forge_app(mock_request)

        assert exc_info.value.status_code == 503


# =============================================================================
# Database Client Tests
# =============================================================================


class TestDatabaseClientDependency:
    """Tests for database client dependency injection."""

    @pytest.mark.asyncio
    async def test_get_db_client_returns_client(self, app):
        """Test get_db_client returns database client."""
        from forge.api.dependencies import get_db_client

        mock_request = MagicMock(spec=Request)
        mock_request.app = app

        # Set up mock ForgeApp with db_client
        app.state.forge.db_client = AsyncMock()

        result = await get_db_client(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_db_client_raises_503_when_not_connected(self, app):
        """Test get_db_client raises 503 when not connected."""
        from forge.api.dependencies import get_db_client

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.db_client = None

        with pytest.raises(HTTPException) as exc_info:
            await get_db_client(mock_request)

        assert exc_info.value.status_code == 503


# =============================================================================
# Repository Dependencies Tests
# =============================================================================


class TestRepositoryDependencies:
    """Tests for repository dependency injection."""

    @pytest.mark.asyncio
    async def test_get_capsule_repository(self, mock_db_client):
        """Test get_capsule_repository returns repository."""
        from forge.api.dependencies import get_capsule_repository
        from forge.repositories.capsule_repository import CapsuleRepository

        result = await get_capsule_repository(mock_db_client)
        assert isinstance(result, CapsuleRepository)

    @pytest.mark.asyncio
    async def test_get_user_repository(self, mock_db_client):
        """Test get_user_repository returns repository."""
        from forge.api.dependencies import get_user_repository
        from forge.repositories.user_repository import UserRepository

        result = await get_user_repository(mock_db_client)
        assert isinstance(result, UserRepository)

    @pytest.mark.asyncio
    async def test_get_governance_repository(self, mock_db_client):
        """Test get_governance_repository returns repository."""
        from forge.api.dependencies import get_governance_repository
        from forge.repositories.governance_repository import GovernanceRepository

        result = await get_governance_repository(mock_db_client)
        assert isinstance(result, GovernanceRepository)

    @pytest.mark.asyncio
    async def test_get_overlay_repository(self, mock_db_client):
        """Test get_overlay_repository returns repository."""
        from forge.api.dependencies import get_overlay_repository
        from forge.repositories.overlay_repository import OverlayRepository

        result = await get_overlay_repository(mock_db_client)
        assert isinstance(result, OverlayRepository)

    @pytest.mark.asyncio
    async def test_get_audit_repository(self, mock_db_client):
        """Test get_audit_repository returns repository."""
        from forge.api.dependencies import get_audit_repository
        from forge.repositories.audit_repository import AuditRepository

        result = await get_audit_repository(mock_db_client)
        assert isinstance(result, AuditRepository)

    @pytest.mark.asyncio
    async def test_get_graph_repository(self, mock_db_client):
        """Test get_graph_repository returns repository."""
        from forge.api.dependencies import get_graph_repository
        from forge.repositories.graph_repository import GraphRepository

        result = await get_graph_repository(mock_db_client)
        assert isinstance(result, GraphRepository)

    @pytest.mark.asyncio
    async def test_get_temporal_repository(self, mock_db_client):
        """Test get_temporal_repository returns repository."""
        from forge.api.dependencies import get_temporal_repository
        from forge.repositories.temporal_repository import TemporalRepository

        result = await get_temporal_repository(mock_db_client)
        assert isinstance(result, TemporalRepository)

    @pytest.mark.asyncio
    async def test_get_session_repository(self, mock_db_client):
        """Test get_session_repository returns repository."""
        from forge.api.dependencies import get_session_repository
        from forge.repositories.session_repository import SessionRepository

        result = await get_session_repository(mock_db_client)
        assert isinstance(result, SessionRepository)


# =============================================================================
# Kernel Component Tests
# =============================================================================


class TestKernelComponentDependencies:
    """Tests for kernel component dependency injection."""

    @pytest.mark.asyncio
    async def test_get_event_system(self, app):
        """Test get_event_system returns event system."""
        from forge.api.dependencies import get_event_system

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.event_system = AsyncMock()

        result = await get_event_system(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_event_system_raises_503_when_not_initialized(self, app):
        """Test get_event_system raises 503 when not initialized."""
        from forge.api.dependencies import get_event_system

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.event_system = None

        with pytest.raises(HTTPException) as exc_info:
            await get_event_system(mock_request)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_overlay_manager(self, app):
        """Test get_overlay_manager returns overlay manager."""
        from forge.api.dependencies import get_overlay_manager

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.overlay_manager = AsyncMock()

        result = await get_overlay_manager(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_pipeline(self, app):
        """Test get_pipeline returns cascade pipeline."""
        from forge.api.dependencies import get_pipeline

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.pipeline = AsyncMock()

        result = await get_pipeline(mock_request)
        assert result is not None


# =============================================================================
# Immune System Component Tests
# =============================================================================


class TestImmuneSystemDependencies:
    """Tests for immune system component dependency injection."""

    @pytest.mark.asyncio
    async def test_get_circuit_registry(self, app):
        """Test get_circuit_registry returns circuit registry."""
        from forge.api.dependencies import get_circuit_registry

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.circuit_registry = MagicMock()

        result = await get_circuit_registry(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_circuit_registry_raises_503_when_not_initialized(self, app):
        """Test get_circuit_registry raises 503 when not initialized."""
        from forge.api.dependencies import get_circuit_registry

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.circuit_registry = None

        with pytest.raises(HTTPException) as exc_info:
            await get_circuit_registry(mock_request)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_health_checker(self, app):
        """Test get_health_checker returns health checker."""
        from forge.api.dependencies import get_health_checker

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.health_checker = MagicMock()

        result = await get_health_checker(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_anomaly_system(self, app):
        """Test get_anomaly_system returns anomaly system."""
        from forge.api.dependencies import get_anomaly_system

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.anomaly_system = MagicMock()

        result = await get_anomaly_system(mock_request)
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_canary_manager(self, app):
        """Test get_canary_manager returns canary manager."""
        from forge.api.dependencies import get_canary_manager

        mock_request = MagicMock(spec=Request)
        mock_request.app = app
        app.state.forge.canary_manager = MagicMock()

        result = await get_canary_manager(mock_request)
        assert result is not None


# =============================================================================
# Authentication Dependencies Tests
# =============================================================================


class TestAuthenticationDependencies:
    """Tests for authentication dependency injection."""

    @pytest.mark.asyncio
    async def test_get_token_payload_from_header(self):
        """Test get_token_payload extracts token from Authorization header."""
        from fastapi.security import HTTPAuthorizationCredentials

        from forge.api.dependencies import get_app_settings, get_token_payload
        from forge.security.tokens import create_access_token

        settings = get_app_settings()
        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_request = MagicMock(spec=Request)
        mock_request.cookies.get.return_value = None

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("forge.security.tokens.TokenBlacklist.is_blacklisted_async", return_value=False):
            payload = await get_token_payload(mock_request, credentials, settings)

        assert payload is not None
        assert payload.sub == "user-123"

    @pytest.mark.asyncio
    async def test_get_token_payload_from_cookie(self):
        """Test get_token_payload prefers cookie over header."""
        from forge.api.dependencies import get_app_settings, get_token_payload
        from forge.security.tokens import create_access_token

        settings = get_app_settings()
        token = create_access_token(
            user_id="cookie-user",
            username="cookieuser",
            role="user",
            trust_flame=60,
        )

        mock_request = MagicMock(spec=Request)
        mock_request.cookies.get.return_value = token

        with patch("forge.security.tokens.TokenBlacklist.is_blacklisted_async", return_value=False):
            payload = await get_token_payload(mock_request, None, settings)

        assert payload is not None
        assert payload.sub == "cookie-user"

    @pytest.mark.asyncio
    async def test_get_token_payload_returns_none_without_token(self):
        """Test get_token_payload returns None when no token."""
        from forge.api.dependencies import get_app_settings, get_token_payload

        settings = get_app_settings()
        mock_request = MagicMock(spec=Request)
        mock_request.cookies.get.return_value = None

        payload = await get_token_payload(mock_request, None, settings)
        assert payload is None

    @pytest.mark.asyncio
    async def test_get_token_payload_returns_none_for_blacklisted(self):
        """Test get_token_payload returns None for blacklisted token."""
        from fastapi.security import HTTPAuthorizationCredentials

        from forge.api.dependencies import get_app_settings, get_token_payload
        from forge.security.tokens import create_access_token

        settings = get_app_settings()
        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="user",
            trust_flame=60,
        )

        mock_request = MagicMock(spec=Request)
        mock_request.cookies.get.return_value = None

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("forge.security.tokens.TokenBlacklist.is_blacklisted_async", return_value=True):
            payload = await get_token_payload(mock_request, credentials, settings)

        assert payload is None


class TestCurrentUserDependencies:
    """Tests for current user dependency injection."""

    @pytest.mark.asyncio
    async def test_get_current_user_optional_returns_none_without_token(self):
        """Test get_current_user_optional returns None without token."""
        from forge.api.dependencies import get_current_user_optional

        mock_user_repo = AsyncMock()
        result = await get_current_user_optional(None, mock_user_repo)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_raises_401_without_user(self):
        """Test get_current_user raises 401 when no user."""
        from forge.api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_active_user_raises_403_if_inactive(self):
        """Test get_current_active_user raises 403 for inactive user."""
        from forge.api.dependencies import get_current_active_user

        inactive_user = User(
            id="user-123",
            username="inactive",
            email="inactive@test.com",
            role=UserRole.USER,
            trust_flame=60,
            is_active=False,
            auth_provider=AuthProvider.LOCAL,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(inactive_user)

        assert exc_info.value.status_code == 403


# =============================================================================
# Authorization Dependencies Tests
# =============================================================================


class TestAuthorizationDependencies:
    """Tests for authorization dependency factories."""

    @pytest.mark.asyncio
    async def test_require_trust_level_allows_sufficient_trust(self):
        """Test require_trust_level allows users with sufficient trust."""
        from forge.api.dependencies import require_trust_level

        user = User(
            id="user-123",
            username="trusted",
            email="trusted@test.com",
            role=UserRole.USER,
            trust_flame=70,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        dependency = require_trust_level(TrustLevel.STANDARD)
        result = await dependency(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_require_trust_level_rejects_insufficient_trust(self):
        """Test require_trust_level rejects users with insufficient trust."""
        from forge.api.dependencies import require_trust_level

        user = User(
            id="user-123",
            username="untrusted",
            email="untrusted@test.com",
            role=UserRole.USER,
            trust_flame=20,  # Below STANDARD threshold
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        dependency = require_trust_level(TrustLevel.TRUSTED)

        with pytest.raises(HTTPException) as exc_info:
            await dependency(user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_roles_allows_matching_role(self):
        """Test require_roles allows users with matching role."""
        from forge.api.dependencies import require_roles

        user = User(
            id="admin-123",
            username="admin",
            email="admin@test.com",
            role=UserRole.ADMIN,
            trust_flame=90,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        dependency = require_roles("admin")
        result = await dependency(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_require_roles_rejects_non_matching_role(self):
        """Test require_roles rejects users without matching role."""
        from forge.api.dependencies import require_roles

        user = User(
            id="user-123",
            username="user",
            email="user@test.com",
            role=UserRole.USER,
            trust_flame=60,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        dependency = require_roles("admin")

        with pytest.raises(HTTPException) as exc_info:
            await dependency(user)

        assert exc_info.value.status_code == 403


# =============================================================================
# Pagination Tests
# =============================================================================


class TestPaginationParams:
    """Tests for PaginationParams class."""

    def test_default_pagination(self):
        """Test default pagination values."""
        from forge.api.dependencies import PaginationParams

        params = PaginationParams()
        assert params.page == 1
        assert params.per_page == 20
        assert params.offset == 0

    def test_custom_pagination(self):
        """Test custom pagination values."""
        from forge.api.dependencies import PaginationParams

        params = PaginationParams(page=3, per_page=50)
        assert params.page == 3
        assert params.per_page == 50
        assert params.offset == 100  # (3-1) * 50

    def test_pagination_bounds_page_minimum(self):
        """Test pagination bounds page to minimum 1."""
        from forge.api.dependencies import PaginationParams

        params = PaginationParams(page=0)
        assert params.page == 1

        params = PaginationParams(page=-5)
        assert params.page == 1

    def test_pagination_bounds_page_maximum(self):
        """Test pagination bounds page to maximum."""
        from forge.api.dependencies import PaginationParams

        params = PaginationParams(page=999999)
        assert params.page == PaginationParams.MAX_PAGE

    def test_pagination_bounds_per_page(self):
        """Test pagination bounds per_page to max_per_page."""
        from forge.api.dependencies import PaginationParams

        params = PaginationParams(per_page=500, max_per_page=100)
        assert params.per_page == 100


class TestGetPagination:
    """Tests for get_pagination dependency."""

    def test_get_pagination_defaults(self):
        """Test get_pagination returns defaults."""
        from forge.api.dependencies import get_pagination

        params = get_pagination()
        assert params.page == 1
        assert params.per_page == 20

    def test_get_pagination_with_per_page(self):
        """Test get_pagination with per_page parameter."""
        from forge.api.dependencies import get_pagination

        params = get_pagination(page=2, per_page=30)
        assert params.page == 2
        assert params.per_page == 30

    def test_get_pagination_page_size_alias(self):
        """Test get_pagination accepts page_size alias."""
        from forge.api.dependencies import get_pagination

        params = get_pagination(page=1, page_size=25)
        assert params.per_page == 25

    def test_get_pagination_page_size_takes_precedence(self):
        """Test page_size takes precedence over per_page."""
        from forge.api.dependencies import get_pagination

        params = get_pagination(page=1, per_page=10, page_size=50)
        assert params.per_page == 50


# =============================================================================
# Client Info Tests
# =============================================================================


class TestClientInfo:
    """Tests for ClientInfo class."""

    def test_client_info_creation(self):
        """Test ClientInfo can be created."""
        from forge.api.dependencies import ClientInfo

        info = ClientInfo(ip_address="192.168.1.1", user_agent="TestAgent/1.0")
        assert info.ip_address == "192.168.1.1"
        assert info.user_agent == "TestAgent/1.0"


class TestClientIpExtraction:
    """Tests for client IP extraction."""

    def test_is_valid_ip_valid_ipv4(self):
        """Test _is_valid_ip returns True for valid IPv4."""
        from forge.api.dependencies import _is_valid_ip

        assert _is_valid_ip("192.168.1.1") is True
        assert _is_valid_ip("10.0.0.1") is True
        assert _is_valid_ip("127.0.0.1") is True

    def test_is_valid_ip_valid_ipv6(self):
        """Test _is_valid_ip returns True for valid IPv6."""
        from forge.api.dependencies import _is_valid_ip

        assert _is_valid_ip("::1") is True
        assert _is_valid_ip("2001:db8::1") is True

    def test_is_valid_ip_invalid(self):
        """Test _is_valid_ip returns False for invalid IPs."""
        from forge.api.dependencies import _is_valid_ip

        assert _is_valid_ip("invalid") is False
        assert _is_valid_ip("999.999.999.999") is False
        assert _is_valid_ip("") is False
        assert _is_valid_ip(None) is False

    def test_is_trusted_proxy_private_ranges(self):
        """Test _is_trusted_proxy returns True for private ranges."""
        from forge.api.dependencies import _is_trusted_proxy

        assert _is_trusted_proxy("127.0.0.1") is True
        assert _is_trusted_proxy("10.0.0.1") is True
        assert _is_trusted_proxy("172.16.0.1") is True
        assert _is_trusted_proxy("192.168.1.1") is True

    def test_is_trusted_proxy_public_ips(self):
        """Test _is_trusted_proxy returns False for public IPs."""
        from forge.api.dependencies import _is_trusted_proxy

        assert _is_trusted_proxy("8.8.8.8") is False
        assert _is_trusted_proxy("1.2.3.4") is False


class TestGetRealClientIp:
    """Tests for _get_real_client_ip function."""

    def test_direct_ip_from_untrusted_source(self):
        """Test returns direct IP when not from trusted proxy."""
        from forge.api.dependencies import _get_real_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "8.8.8.8"  # Public IP, not a proxy
        mock_request.headers.get.return_value = "spoofed.ip"

        ip = _get_real_client_ip(mock_request)
        assert ip == "8.8.8.8"

    def test_x_forwarded_for_from_trusted_proxy(self):
        """Test extracts from X-Forwarded-For when from trusted proxy."""
        from forge.api.dependencies import _get_real_client_ip

        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "127.0.0.1"  # Localhost proxy
        mock_request.headers.get.side_effect = lambda h: (
            "203.0.113.1, 10.0.0.1" if h == "X-Forwarded-For" else None
        )

        ip = _get_real_client_ip(mock_request)
        # Should return the first non-proxy IP from the right
        assert ip == "203.0.113.1"


# =============================================================================
# Correlation ID Tests
# =============================================================================


class TestCorrelationIdDependency:
    """Tests for correlation ID dependency."""

    @pytest.mark.asyncio
    async def test_get_correlation_id_returns_from_state(self):
        """Test get_correlation_id returns ID from request state."""
        from forge.api.dependencies import get_correlation_id

        mock_request = MagicMock(spec=Request)
        mock_request.state.correlation_id = "test-correlation-123"

        result = await get_correlation_id(mock_request)
        assert result == "test-correlation-123"

    @pytest.mark.asyncio
    async def test_get_correlation_id_returns_unknown_when_missing(self):
        """Test get_correlation_id returns 'unknown' when not set."""
        from forge.api.dependencies import get_correlation_id

        mock_request = MagicMock(spec=Request)
        # Remove correlation_id attribute
        delattr(mock_request.state, "correlation_id")

        result = await get_correlation_id(mock_request)
        assert result == "unknown"


# =============================================================================
# Services Dependencies Tests
# =============================================================================


class TestServicesDependencies:
    """Tests for service dependency injection."""

    @pytest.mark.asyncio
    async def test_get_auth_service(self, mock_db_client):
        """Test get_auth_service returns AuthService."""
        from forge.api.dependencies import get_auth_service
        from forge.repositories.audit_repository import AuditRepository
        from forge.repositories.user_repository import UserRepository
        from forge.security.auth_service import AuthService

        user_repo = UserRepository(mock_db_client)
        audit_repo = AuditRepository(mock_db_client)

        result = await get_auth_service(user_repo, audit_repo)
        assert isinstance(result, AuthService)

    @pytest.mark.asyncio
    async def test_get_session_service(self, mock_db_client):
        """Test get_session_service returns SessionBindingService."""
        from forge.api.dependencies import get_session_service
        from forge.repositories.session_repository import SessionRepository
        from forge.security.session_binding import SessionBindingService

        session_repo = SessionRepository(mock_db_client)

        result = await get_session_service(session_repo)
        assert isinstance(result, SessionBindingService)


# =============================================================================
# Embedding Service Tests
# =============================================================================


class TestEmbeddingServiceDependency:
    """Tests for embedding service dependency."""

    def test_get_embedding_svc_returns_service(self):
        """Test get_embedding_svc returns embedding service."""
        from forge.api.dependencies import get_embedding_svc
        from forge.services.embedding import EmbeddingService

        result = get_embedding_svc()
        assert isinstance(result, EmbeddingService)


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestDependencyExports:
    """Tests for dependency module exports."""

    def test_all_dependencies_exported(self):
        """Test all dependency types are exported."""
        from forge.api.dependencies import __all__

        expected = [
            "SettingsDep",
            "DbClientDep",
            "CapsuleRepoDep",
            "UserRepoDep",
            "GovernanceRepoDep",
            "OverlayRepoDep",
            "AuditRepoDep",
            "GraphRepoDep",
            "TemporalRepoDep",
            "SessionRepoDep",
            "EventSystemDep",
            "OverlayManagerDep",
            "PipelineDep",
            "CircuitRegistryDep",
            "HealthCheckerDep",
            "AnomalySystemDep",
            "CanaryManagerDep",
            "OptionalUserDep",
            "CurrentUserDep",
            "ActiveUserDep",
            "SandboxUserDep",
            "StandardUserDep",
            "TrustedUserDep",
            "CoreUserDep",
            "AdminUserDep",
            "ModeratorUserDep",
            "require_trust_level",
            "require_roles",
            "require_capabilities",
            "AuthServiceDep",
            "SessionServiceDep",
            "PaginationParams",
            "PaginationDep",
            "CorrelationIdDep",
            "ClientInfo",
            "ClientInfoDep",
        ]

        for name in expected:
            assert name in __all__


# =============================================================================
# Security Scheme Tests
# =============================================================================


class TestSecurityScheme:
    """Tests for the security scheme configuration."""

    def test_security_scheme_configured(self):
        """Test HTTP Bearer security scheme is configured."""
        from forge.api.dependencies import security

        assert security is not None
        # auto_error should be False for optional auth
        assert security.auto_error is False


# =============================================================================
# Trusted Proxy Configuration Tests
# =============================================================================


class TestTrustedProxyConfiguration:
    """Tests for trusted proxy configuration."""

    def test_trusted_proxy_ranges_defined(self):
        """Test trusted proxy ranges are defined."""
        from forge.api.dependencies import TRUSTED_PROXY_RANGES

        assert TRUSTED_PROXY_RANGES is not None
        assert len(TRUSTED_PROXY_RANGES) > 0

    def test_default_proxy_ranges_include_private(self):
        """Test default proxy ranges include private networks."""
        from forge.api.dependencies import TRUSTED_PROXY_RANGES

        # Should include common private ranges
        range_str = ",".join(TRUSTED_PROXY_RANGES)
        assert "127.0.0.0" in range_str or "10.0.0.0" in range_str
