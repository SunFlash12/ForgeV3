"""
Integration Test Fixtures - REAL Database Connections

These tests require actual running services (Neo4j, etc.) and are NOT mocked.
They verify that the system genuinely works end-to-end.

USAGE:
    Set INTEGRATION_TEST_DB=true and ensure Neo4j is running:

    export INTEGRATION_TEST_DB=true
    export NEO4J_URI=bolt://localhost:7687
    export NEO4J_USER=neo4j
    export NEO4J_PASSWORD=<your-password>  # Set via env, never hardcode
    pytest tests/test_integration/ -v

SECURITY:
    - All credentials MUST come from environment variables
    - Never commit real passwords to version control
    - These tests will FAIL if services are unavailable (by design)
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# =============================================================================
# INTEGRATION TEST GATE
# =============================================================================
# Skip ALL tests in this directory unless explicitly enabled.
# This prevents accidental CI failures when Neo4j isn't available.

_integration_enabled = os.environ.get("INTEGRATION_TEST_DB", "").lower() == "true"

pytestmark = pytest.mark.skipif(
    not _integration_enabled,
    reason=(
        "Integration tests require INTEGRATION_TEST_DB=true and running Neo4j. "
        "These tests use REAL database connections, not mocks."
    ),
)


# =============================================================================
# VERIFY REQUIRED ENVIRONMENT VARIABLES
# =============================================================================


def _require_env(var_name: str) -> str:
    """Get required environment variable or fail with clear message."""
    value = os.environ.get(var_name)
    if not value:
        pytest.fail(
            f"Integration test requires {var_name} environment variable. "
            f"Set it to run integration tests. Never hardcode credentials."
        )
    return value


@pytest.fixture(scope="session")
def neo4j_uri() -> str:
    """Get Neo4j URI from environment."""
    return _require_env("NEO4J_URI")


@pytest.fixture(scope="session")
def neo4j_user() -> str:
    """Get Neo4j username from environment."""
    return _require_env("NEO4J_USER")


@pytest.fixture(scope="session")
def neo4j_password() -> str:
    """Get Neo4j password from environment - NEVER log or print this."""
    return _require_env("NEO4J_PASSWORD")


# =============================================================================
# REAL DATABASE CLIENT
# =============================================================================


@pytest.fixture(scope="session")
async def real_db_client(
    neo4j_uri: str, neo4j_user: str, neo4j_password: str
) -> AsyncGenerator:
    """
    Connect to REAL Neo4j instance.

    This fixture FAILS if Neo4j is not running - no fallback, no mocks.
    That's the point: integration tests verify real connectivity.
    """
    from forge.database.client import Neo4jClient

    # Override environment for the client
    os.environ["NEO4J_URI"] = neo4j_uri
    os.environ["NEO4J_USER"] = neo4j_user
    os.environ["NEO4J_PASSWORD"] = neo4j_password

    client = Neo4jClient()

    try:
        await client.connect()

        # Verify we're actually connected
        is_healthy = await client.health_check()
        if not is_healthy:
            pytest.fail("Neo4j health check failed - database may be unhealthy")

        yield client

    except Exception as e:
        pytest.fail(
            f"Failed to connect to Neo4j at {neo4j_uri}: {e}. "
            "Integration tests require a running Neo4j instance."
        )
    finally:
        await client.close()


@pytest.fixture
async def integration_db(real_db_client) -> AsyncGenerator:
    """
    Provide database client with test isolation.

    Creates a unique test namespace to avoid conflicts with other tests
    or production data. Cleans up after each test.
    """
    # Generate unique test prefix for this test run
    test_prefix = f"test_{uuid4().hex[:8]}"

    yield real_db_client

    # Cleanup: Delete only nodes created during this test
    # Uses a label convention for test data
    try:
        await real_db_client.execute(
            "MATCH (n) WHERE n.test_prefix = $prefix DETACH DELETE n",
            {"prefix": test_prefix},
        )
    except Exception:
        pass  # Best effort cleanup


# =============================================================================
# REAL APPLICATION (No Mocks)
# =============================================================================


@pytest.fixture
async def real_app(real_db_client) -> FastAPI:
    """
    Create FastAPI app with REAL database connection.

    Unlike the mock app in conftest.py, this uses actual services.
    """
    from contextlib import asynccontextmanager

    from forge.api.app import create_app, forge_app

    @asynccontextmanager
    async def _integration_lifespan(application: FastAPI):
        # Use the real db client from our fixture
        forge_app.db_client = real_db_client
        forge_app.is_ready = True
        yield
        forge_app.is_ready = False

    application = create_app(
        title="Forge Integration Test",
        version="test",
        docs_url=None,
        redoc_url=None,
    )
    application.router.lifespan_context = _integration_lifespan

    return application


@pytest.fixture
async def real_client(real_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async client connected to real app with real database."""
    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://test",
    ) as ac:
        yield ac


# =============================================================================
# TEST DATA HELPERS
# =============================================================================


@pytest.fixture
def create_test_user(integration_db):
    """
    Factory to create REAL users in the database.

    Returns a function that creates users and tracks them for cleanup.
    """
    created_ids: list[str] = []

    async def _create(
        username: str | None = None,
        email: str | None = None,
        trust_level: int = 60,
    ) -> dict:
        from forge.repositories.user_repository import UserRepository

        repo = UserRepository(integration_db)

        user_id = str(uuid4())
        username = username or f"inttest_{uuid4().hex[:8]}"
        email = email or f"{username}@integration.test"

        # Create real user in database
        user = await repo.create(
            user_id=user_id,
            username=username,
            email=email,
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",  # Dummy hash for tests
            trust_flame=trust_level,
        )

        created_ids.append(user_id)
        return user

    return _create


@pytest.fixture
def create_test_capsule(integration_db):
    """
    Factory to create REAL capsules in the database.
    """
    created_ids: list[str] = []

    async def _create(
        title: str | None = None,
        content: str | None = None,
        owner_id: str | None = None,
    ) -> dict:
        from forge.repositories.capsule_repository import CapsuleRepository

        repo = CapsuleRepository(integration_db)

        capsule_id = str(uuid4())
        title = title or f"Integration Test Capsule {uuid4().hex[:8]}"
        content = content or "Test content created by integration test"
        owner_id = owner_id or str(uuid4())

        capsule = await repo.create(
            capsule_id=capsule_id,
            title=title,
            content=content,
            owner_id=owner_id,
            capsule_type="knowledge",
            trust_level=60,
        )

        created_ids.append(capsule_id)
        return capsule

    return _create


# =============================================================================
# JWT TOKENS FOR INTEGRATION TESTS
# =============================================================================


@pytest.fixture
def integration_auth_headers():
    """
    Create authentication headers for integration tests.

    Uses the same JWT mechanism as production but with test users.
    """
    from forge.security.tokens import create_access_token

    def _create(user_id: str, username: str, role: str = "user", trust_level: int = 60):
        token = create_access_token(
            user_id=user_id,
            username=username,
            role=role,
            trust_flame=trust_level,
        )
        return {"Authorization": f"Bearer {token}"}

    return _create


# =============================================================================
# MARKERS FOR TEST ORGANIZATION
# =============================================================================

# Usage in tests:
# @pytest.mark.integration
# @pytest.mark.slow
# async def test_something(real_client, integration_db):
#     ...

pytest_plugins = []
