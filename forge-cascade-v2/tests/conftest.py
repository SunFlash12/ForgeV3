"""
Forge Cascade V2 - Test Fixtures

Shared pytest fixtures for all test modules.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# =============================================================================
# TEST ENVIRONMENT SETUP
# =============================================================================
# SECURITY NOTE (Audit 3): These are TEST-ONLY credentials for pytest fixtures.
# The APP_ENV="testing" flag ensures these cannot be used in production.
# Production deployments MUST use environment variables from secure sources.

# Safety check: Prevent accidental production use
_current_env = os.environ.get("APP_ENV", "")
if _current_env == "production":
    raise RuntimeError(
        "SECURITY ERROR: Test fixtures cannot be loaded in production environment. "
        "Do not import conftest.py in production code."
    )

os.environ["APP_ENV"] = "testing"

# TEST-ONLY database credentials (not valid for production)
# Use setdefault to allow CI/integration tests to override with their own values
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "testpassword")  # TEST ONLY - not a real password
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-key-at-least-32-characters-long-for-testing"
)  # TEST ONLY
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")


# =============================================================================
# Event Loop Fixture
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Mock Database Client
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create a mock Neo4j client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client._driver = MagicMock()
    return client


# =============================================================================
# Mock Services
# =============================================================================


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    from forge.services.embedding import EmbeddingConfig, EmbeddingProvider, EmbeddingService

    config = EmbeddingConfig(provider=EmbeddingProvider.MOCK)
    return EmbeddingService(config)


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    from forge.services.llm import LLMConfig, LLMProvider, LLMService

    config = LLMConfig(provider=LLMProvider.MOCK)
    return LLMService(config)


@pytest.fixture
def mock_search_service(mock_embedding_service, mock_db_client):
    """Create a mock search service."""
    from forge.services.search import SearchService

    return SearchService(
        embedding_service=mock_embedding_service,
        db_client=mock_db_client,
    )


# =============================================================================
# Mock Event System
# =============================================================================


@pytest.fixture
def mock_event_system():
    """Create a mock event system."""
    system = AsyncMock()
    system.publish = AsyncMock()
    system.subscribe = MagicMock()
    system.unsubscribe = MagicMock()
    return system


# =============================================================================
# Test Data Generators
# =============================================================================


@pytest.fixture
def user_factory():
    """Factory for creating test users."""

    def _create_user(
        user_id: str | None = None,
        username: str | None = None,
        email: str | None = None,
        trust_level: int = 60,
    ):
        return {
            "id": user_id or str(uuid4()),
            "username": username or f"testuser_{uuid4().hex[:8]}",
            "email": email or f"test_{uuid4().hex[:8]}@example.com",
            "trust_level": trust_level,
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
        }

    return _create_user


@pytest.fixture
def capsule_factory():
    """Factory for creating test capsules."""

    def _create_capsule(
        capsule_id: str | None = None,
        title: str | None = None,
        content: str | None = None,
        owner_id: str | None = None,
        capsule_type: str = "knowledge",
    ):
        return {
            "id": capsule_id or str(uuid4()),
            "title": title or f"Test Capsule {uuid4().hex[:8]}",
            "content": content or "This is test content for the capsule.",
            "type": capsule_type,
            "owner_id": owner_id or str(uuid4()),
            "trust_level": 60,
            "version": "1.0.0",
            "tags": ["test"],
            "metadata": {},
            "view_count": 0,
            "fork_count": 0,
            "is_archived": False,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

    return _create_capsule


@pytest.fixture
def proposal_factory():
    """Factory for creating test proposals."""

    def _create_proposal(
        proposal_id: str | None = None,
        title: str | None = None,
        proposer_id: str | None = None,
    ):
        return {
            "id": proposal_id or str(uuid4()),
            "title": title or f"Test Proposal {uuid4().hex[:8]}",
            "description": "This is a test proposal for governance.",
            "type": "policy",
            "status": "active",
            "proposer_id": proposer_id or str(uuid4()),
            "votes_for": 0,
            "votes_against": 0,
            "votes_abstain": 0,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": None,
        }

    return _create_proposal


# =============================================================================
# JWT Token Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(user_factory):
    """Create authentication headers with a valid JWT token."""
    from forge.security.tokens import create_access_token

    user = user_factory()
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(user_factory):
    """Create authentication headers for an admin user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=90)
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="admin",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# FastAPI Test Client
# =============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application.

    Creates the app WITHOUT the production lifespan (which requires Neo4j).
    Overrides auth dependencies so JWT-authenticated requests work without a
    real database: the user is synthesized from the JWT token claims.
    """
    from contextlib import asynccontextmanager

    from forge.api.app import create_app, forge_app

    # Create a no-op lifespan that marks the app as "ready" without connecting
    # to Neo4j or initializing heavy services.
    @asynccontextmanager
    async def _test_lifespan(application: FastAPI):
        forge_app.is_ready = True
        yield
        forge_app.is_ready = False

    application = create_app(
        title="Forge Test",
        version="test",
        docs_url=None,
        redoc_url=None,
    )

    # Swap the lifespan to the lightweight test version
    application.router.lifespan_context = _test_lifespan

    # ── Override DB dependency so routes don't need a live Neo4j ──
    from forge.api.dependencies import get_db_client

    _mock_db = AsyncMock()
    _mock_db.execute = AsyncMock(return_value=[])
    _mock_db.execute_single = AsyncMock(return_value=None)
    _mock_db.connect = AsyncMock()
    _mock_db.close = AsyncMock()
    _mock_db._driver = MagicMock()

    async def _test_get_db_client() -> object:
        return _mock_db

    application.dependency_overrides[get_db_client] = _test_get_db_client

    # ── Override auth dependencies so tests don't need Neo4j ──
    #
    # The production auth chain is:
    #   get_token_payload  (JWT verify + blacklist check via DB)
    #   -> get_current_user_optional  (DB lookup by user id)
    #   -> get_current_user           (raises 401 if None)
    #   -> get_current_active_user    (raises 403 if inactive)
    #
    # In tests we replace every level so no database is needed.
    # A valid JWT token is still required; the user is synthesized
    # from the token claims.
    from forge.api.dependencies import (
        get_current_active_user,
        get_current_user,
        get_current_user_optional,
    )
    from forge.models.user import AuthProvider, User, UserRole
    from forge.security.tokens import TokenError, verify_token

    def _user_from_request(request: Request) -> User | None:
        """Extract + verify JWT from request, return User or None."""
        token_str: str | None = None

        # Cookie first (mirrors production priority)
        access_cookie = request.cookies.get("access_token")
        if access_cookie:
            token_str = access_cookie

        # Authorization header fallback
        if not token_str:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:]

        if not token_str:
            return None

        try:
            payload = verify_token(token_str)
        except TokenError:
            return None

        role_map = {
            "user": UserRole.USER,
            "admin": UserRole.ADMIN,
            "moderator": UserRole.MODERATOR,
            "system": UserRole.SYSTEM,
        }
        return User(
            id=payload.sub,
            username=payload.username or "testuser",
            email=f"{payload.username or 'testuser'}@test.example.com",
            role=role_map.get(payload.role or "user", UserRole.USER),
            trust_flame=(payload.trust_flame if payload.trust_flame is not None else 60),
            is_active=True,
            is_verified=True,
            auth_provider=AuthProvider.LOCAL,
        )

    async def _test_get_current_user_optional(request: Request) -> User | None:
        return _user_from_request(request)

    async def _test_get_current_user(request: Request) -> User:
        user = _user_from_request(request)
        if not user:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    async def _test_get_current_active_user(request: Request) -> User:
        user = _user_from_request(request)
        if not user:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )
        return user

    application.dependency_overrides[get_current_user_optional] = _test_get_current_user_optional
    application.dependency_overrides[get_current_user] = _test_get_current_user
    application.dependency_overrides[get_current_active_user] = _test_get_current_active_user

    return application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# Database Fixtures (for integration tests)
# =============================================================================


@pytest.fixture
async def db_client():
    """
    Create a real database client for integration tests.

    Requires Neo4j to be running.
    """
    from forge.database.client import Neo4jClient

    client = Neo4jClient()

    try:
        await client.connect()
        yield client
    finally:
        await client.close()


@pytest.fixture
async def clean_db(db_client):
    """
    Clean the database before and after tests.

    WARNING: This deletes all data!
    """
    # Clean before test
    await db_client.execute("MATCH (n) DETACH DELETE n", {})

    yield db_client

    # Clean after test
    await db_client.execute("MATCH (n) DETACH DELETE n", {})


# =============================================================================
# Repository Fixtures
# =============================================================================


@pytest.fixture
def capsule_repository(mock_db_client):
    """Create a capsule repository with mock client."""
    from forge.repositories.capsule_repository import CapsuleRepository

    return CapsuleRepository(mock_db_client)


@pytest.fixture
def user_repository(mock_db_client):
    """Create a user repository with mock client."""
    from forge.repositories.user_repository import UserRepository

    return UserRepository(mock_db_client)


@pytest.fixture
def governance_repository(mock_db_client):
    """Create a governance repository with mock client."""
    from forge.repositories.governance_repository import GovernanceRepository

    return GovernanceRepository(mock_db_client)


# =============================================================================
# Overlay Fixtures
# =============================================================================


@pytest.fixture
def overlay_manager(mock_event_system):
    """Create an overlay manager."""
    from forge.kernel.overlay_manager import OverlayManager

    return OverlayManager(mock_event_system)


@pytest.fixture
async def security_overlay():
    """Create a security validator overlay."""
    from forge.overlays import create_security_validator

    return create_security_validator(strict_mode=False)


@pytest.fixture
async def governance_overlay():
    """Create a governance overlay."""
    from forge.overlays import create_governance_overlay

    return create_governance_overlay(strict_mode=False)


# =============================================================================
# Immune System Fixtures
# =============================================================================


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker."""
    from forge.immune.circuit_breaker import CircuitBreaker

    return CircuitBreaker(
        name="test_circuit",
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30,
    )


@pytest.fixture
def health_checker(mock_db_client, mock_event_system):
    """Create a health checker."""
    from forge.immune.health_checker import HealthChecker

    return HealthChecker(
        db_client=mock_db_client,
        event_system=mock_event_system,
    )


# =============================================================================
# Cleanup
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    yield

    # Reset service singletons
    from forge.services import embedding, llm, search

    embedding._embedding_service = None
    llm._llm_service = None
    search._search_service = None

    # Reset TokenBlacklist async lock to avoid "Event loop is closed" errors
    # when pytest-asyncio creates a new event loop per test
    from forge.security.tokens import TokenBlacklist

    TokenBlacklist._async_lock = None

    # Reset diagnosis services singleton
    try:
        from forge.api.routes.diagnosis import _DiagnosisServices

        _DiagnosisServices._instance = None
    except ImportError:
        pass

    # Reset copilot agent global and lock
    try:
        import forge.api.routes.copilot as copilot_module

        copilot_module._agent = None
        copilot_module._agent_lock = None
    except ImportError:
        pass
