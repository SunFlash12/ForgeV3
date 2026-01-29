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

    # ── Override kernel/service dependencies that check ForgeApp ──
    from forge.api.dependencies import (
        get_anomaly_system,
        get_canary_manager,
        get_circuit_registry,
        get_embedding_svc,
        get_event_system,
        get_forge_app,
        get_health_checker,
        get_overlay_manager,
        get_pipeline,
    )

    # Create a mock ForgeApp with all services
    _mock_forge_app = MagicMock()
    _mock_forge_app.is_ready = True
    _mock_forge_app.db_client = _mock_db
    _mock_forge_app.event_system = AsyncMock()
    _mock_forge_app.event_system.publish = AsyncMock()
    _mock_forge_app.overlay_manager = AsyncMock()
    _mock_forge_app.pipeline = AsyncMock()
    _mock_forge_app.circuit_registry = MagicMock()
    _mock_forge_app.health_checker = AsyncMock()
    _mock_forge_app.anomaly_system = AsyncMock()
    _mock_forge_app.canary_manager = AsyncMock()

    def _test_get_forge_app(request: Request) -> object:
        return _mock_forge_app

    application.dependency_overrides[get_forge_app] = _test_get_forge_app

    # Individual service overrides (for routes that use them directly)
    async def _test_get_event_system() -> object:
        return _mock_forge_app.event_system

    async def _test_get_overlay_manager() -> object:
        return _mock_forge_app.overlay_manager

    async def _test_get_pipeline() -> object:
        return _mock_forge_app.pipeline

    async def _test_get_circuit_registry() -> object:
        return _mock_forge_app.circuit_registry

    async def _test_get_health_checker() -> object:
        return _mock_forge_app.health_checker

    async def _test_get_anomaly_system() -> object:
        return _mock_forge_app.anomaly_system

    async def _test_get_canary_manager() -> object:
        return _mock_forge_app.canary_manager

    def _test_get_embedding_svc() -> object:
        mock_embedding = MagicMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 384)
        mock_embedding.embed_batch = AsyncMock(return_value=[[0.1] * 384])
        return mock_embedding

    application.dependency_overrides[get_event_system] = _test_get_event_system
    application.dependency_overrides[get_overlay_manager] = _test_get_overlay_manager
    application.dependency_overrides[get_pipeline] = _test_get_pipeline
    application.dependency_overrides[get_circuit_registry] = _test_get_circuit_registry
    application.dependency_overrides[get_health_checker] = _test_get_health_checker
    application.dependency_overrides[get_anomaly_system] = _test_get_anomaly_system
    application.dependency_overrides[get_canary_manager] = _test_get_canary_manager
    application.dependency_overrides[get_embedding_svc] = _test_get_embedding_svc

    # ══════════════════════════════════════════════════════════════════════
    # Route-specific dependency overrides
    # ══════════════════════════════════════════════════════════════════════

    # 1. Chat Service Override
    try:
        from forge.api.routes.chat import get_chat_service_dep

        _mock_chat_service = AsyncMock()
        _mock_chat_service.create_room = AsyncMock(
            return_value=MagicMock(id="room-123", name="Test Room", created_by="user-123")
        )
        _mock_chat_service.get_user_accessible_rooms = AsyncMock(return_value=([], 0))
        _mock_chat_service.get_room = AsyncMock(
            return_value=MagicMock(id="room-123", name="Test Room")
        )
        _mock_chat_service.get_room_members = AsyncMock(return_value=[])
        _mock_chat_service.add_member = AsyncMock(return_value=True)
        _mock_chat_service.remove_member = AsyncMock(return_value=True)
        _mock_chat_service.update_member_role = AsyncMock(return_value=True)
        _mock_chat_service.send_message = AsyncMock(
            return_value=MagicMock(id="msg-123", content="Test message")
        )
        _mock_chat_service.get_messages = AsyncMock(return_value=([], 0))
        _mock_chat_service.create_invite = AsyncMock(return_value=MagicMock(code="invite-123"))
        _mock_chat_service.join_via_invite = AsyncMock(return_value=True)

        application.dependency_overrides[get_chat_service_dep] = lambda: _mock_chat_service
    except ImportError:
        pass

    # 2. Audit Repository Override
    try:
        from forge.api.dependencies import AuditRepoDep

        _mock_audit_repo = AsyncMock()
        _mock_audit_repo.log_action = AsyncMock(return_value=None)
        _mock_audit_repo.get_audit_trail = AsyncMock(return_value=[])
        _mock_audit_repo.get_user_actions = AsyncMock(return_value=[])

        application.dependency_overrides[AuditRepoDep] = lambda: _mock_audit_repo
    except ImportError:
        pass

    # 3. Game Client Override
    try:
        from forge.virtuals.game.sdk_client import get_game_client

        _mock_game_client = AsyncMock()
        _mock_game_client.create_agent = AsyncMock(
            return_value=MagicMock(id="agent-123", name="Test Agent")
        )
        _mock_game_client.get_agent = AsyncMock(
            return_value=MagicMock(id="agent-123", name="Test Agent")
        )
        _mock_game_client.delete_agent = AsyncMock(return_value=True)
        _mock_game_client.run_agent_loop = AsyncMock(
            return_value={"action": "test", "result": "success"}
        )
        _mock_game_client.get_next_action = AsyncMock(
            return_value={"action": "idle", "context": {}}
        )
        _mock_game_client.store_memory = AsyncMock(return_value="memory-123")
        _mock_game_client.search_memories = AsyncMock(return_value=[])

        async def _test_get_game_client():
            return _mock_game_client

        application.dependency_overrides[get_game_client] = _test_get_game_client
    except ImportError:
        pass

    # 4. Governance Dependencies Override
    try:
        from forge.api.dependencies import GovernanceRepoDep, UserRepoDep

        _mock_governance_repo = AsyncMock()
        _mock_governance_repo.create_proposal = AsyncMock(
            return_value=MagicMock(id="prop-123", title="Test Proposal")
        )
        _mock_governance_repo.get_proposal = AsyncMock(return_value=None)
        _mock_governance_repo.list_proposals = AsyncMock(return_value=([], 0))
        _mock_governance_repo.cast_vote = AsyncMock(return_value=True)
        _mock_governance_repo.get_votes = AsyncMock(return_value=[])
        _mock_governance_repo.update_proposal_status = AsyncMock(return_value=True)

        _mock_user_repo = AsyncMock()
        _mock_user_repo.get_by_id = AsyncMock(
            return_value=MagicMock(id="user-123", trust_flame=60, username="testuser")
        )
        _mock_user_repo.get_by_username = AsyncMock(return_value=None)
        _mock_user_repo.create = AsyncMock(
            return_value=MagicMock(id="user-123", username="testuser")
        )
        _mock_user_repo.update = AsyncMock(return_value=True)

        application.dependency_overrides[GovernanceRepoDep] = lambda: _mock_governance_repo
        application.dependency_overrides[UserRepoDep] = lambda: _mock_user_repo
    except ImportError:
        pass

    # 5. Copilot Agent Override
    try:
        from forge.api.routes.copilot import get_agent

        _mock_copilot_agent = AsyncMock()
        _mock_copilot_agent.chat = AsyncMock(return_value="Test response from copilot")
        _mock_copilot_agent.stream_chat = AsyncMock(
            return_value=iter(["chunk1", "chunk2", "chunk3"])
        )
        _mock_copilot_agent.start = AsyncMock()
        _mock_copilot_agent.stop = AsyncMock()

        async def _test_get_agent():
            return _mock_copilot_agent

        application.dependency_overrides[get_agent] = _test_get_agent
    except ImportError:
        pass

    # 6. Ghost Council Service Override
    try:
        from forge.api.routes.governance import get_ghost_council_service

        _mock_ghost_council = AsyncMock()
        _mock_ghost_council.deliberate_proposal = AsyncMock(
            return_value=MagicMock(
                consensus_vote="APPROVE",
                member_votes=[],
                recommendation="Approved by council",
            )
        )
        _mock_ghost_council.respond_to_issue = AsyncMock(return_value=MagicMock())

        async def _test_get_ghost_council():
            return _mock_ghost_council

        application.dependency_overrides[get_ghost_council_service] = _test_get_ghost_council
    except ImportError:
        pass

    # 7. Notification Service Override
    try:
        from forge.api.routes.notifications import get_notification_svc

        _mock_notification_service = AsyncMock()
        _mock_notification_service.get_notifications = AsyncMock(return_value=[])
        _mock_notification_service.get_unread_count = AsyncMock(return_value=0)
        _mock_notification_service.mark_as_read = AsyncMock(return_value=True)
        _mock_notification_service.mark_all_read = AsyncMock(return_value=True)
        _mock_notification_service.delete_notification = AsyncMock(return_value=True)
        _mock_notification_service.create_webhook = AsyncMock(
            return_value=MagicMock(id="webhook-123", url="https://test.webhook.com")
        )
        _mock_notification_service.get_webhooks = AsyncMock(return_value=[])
        _mock_notification_service.delete_webhook = AsyncMock(return_value=True)
        _mock_notification_service.get_user_preferences = AsyncMock(
            return_value=MagicMock(
                user_id="user-123",
                email_enabled=True,
                push_enabled=True,
                webhook_enabled=False,
            )
        )
        _mock_notification_service.update_user_preferences = AsyncMock(
            return_value=MagicMock(user_id="user-123")
        )

        async def _test_get_notification_svc():
            return _mock_notification_service

        application.dependency_overrides[get_notification_svc] = _test_get_notification_svc
    except ImportError:
        pass

    # 8. Fix OverlayManager - use MagicMock for sync methods, AsyncMock for async
    _mock_forge_app.overlay_manager = MagicMock()
    _mock_forge_app.overlay_manager.list_all = MagicMock(return_value=[])
    _mock_forge_app.overlay_manager.list_active = MagicMock(return_value=[])
    _mock_forge_app.overlay_manager.get_by_id = MagicMock(return_value=None)
    _mock_forge_app.overlay_manager.get_by_name = MagicMock(return_value=None)
    _mock_forge_app.overlay_manager.get_overlays_for_phase = MagicMock(return_value=[])
    _mock_forge_app.overlay_manager.activate = AsyncMock()
    _mock_forge_app.overlay_manager.deactivate = AsyncMock()
    _mock_forge_app.overlay_manager.register = MagicMock()

    # 9. Fix CanaryManager with all required methods
    _mock_forge_app.canary_manager = AsyncMock()
    _mock_forge_app.canary_manager.get_deployment = AsyncMock(return_value=None)
    _mock_forge_app.canary_manager.get_all_deployments = AsyncMock(return_value=[])
    _mock_forge_app.canary_manager.create_deployment = AsyncMock(
        return_value=MagicMock(
            id="deployment-123",
            overlay_id="overlay-123",
            status="pending",
            current_phase=0,
            phases=[],
        )
    )
    _mock_forge_app.canary_manager.start = AsyncMock()
    _mock_forge_app.canary_manager.manual_advance = AsyncMock()
    _mock_forge_app.canary_manager.rollback = AsyncMock()
    _mock_forge_app.canary_manager.complete = AsyncMock()

    # 10. Graph Repository Override
    try:
        from forge.api.dependencies import get_graph_repository

        _mock_graph_repo = AsyncMock()
        _mock_graph_repo.client = AsyncMock()
        _mock_graph_repo.client.execute = AsyncMock(return_value=[])
        _mock_graph_repo.client.execute_single = AsyncMock(return_value=None)
        _mock_graph_repo.get_graph_metrics = AsyncMock(
            return_value=MagicMock(
                total_nodes=100,
                total_edges=200,
                density=0.02,
                avg_clustering=0.3,
                connected_components=5,
                diameter=10,
            )
        )
        _mock_graph_repo.compute_pagerank = AsyncMock(return_value=[])

        async def _test_get_graph_repo():
            return _mock_graph_repo

        application.dependency_overrides[get_graph_repository] = _test_get_graph_repo
    except ImportError:
        pass

    # 11. Temporal Repository Override
    try:
        from forge.api.dependencies import get_temporal_repository

        _mock_temporal_repo = AsyncMock()
        _mock_temporal_repo.get_version_history = AsyncMock(
            return_value=MagicMock(versions=[])
        )
        _mock_temporal_repo.get_capsule_at_time = AsyncMock(return_value=None)
        _mock_temporal_repo.diff_versions = AsyncMock(return_value=None)
        _mock_temporal_repo.get_trust_timeline = AsyncMock(
            return_value=MagicMock(snapshots=[])
        )
        _mock_temporal_repo.create_graph_snapshot = AsyncMock(
            return_value=MagicMock(id="snapshot-123")
        )
        _mock_temporal_repo.get_latest_graph_snapshot = AsyncMock(return_value=None)

        async def _test_get_temporal_repo():
            return _mock_temporal_repo

        application.dependency_overrides[get_temporal_repository] = _test_get_temporal_repo
    except ImportError:
        pass

    # 12. Capsule Repository Override
    try:
        from forge.api.dependencies import get_capsule_repository

        _mock_capsule_repo = AsyncMock()
        _mock_capsule_repo.get_by_id = AsyncMock(return_value=None)
        _mock_capsule_repo.create = AsyncMock(
            return_value=MagicMock(id="capsule-123", title="Test Capsule")
        )
        _mock_capsule_repo.update = AsyncMock(return_value=True)
        _mock_capsule_repo.delete = AsyncMock(return_value=True)
        _mock_capsule_repo.list_capsules = AsyncMock(return_value=([], 0))
        _mock_capsule_repo.create_semantic_edge = AsyncMock(
            return_value=MagicMock(id="edge-123")
        )
        _mock_capsule_repo.get_semantic_edge = AsyncMock(return_value=None)
        _mock_capsule_repo.get_semantic_edges = AsyncMock(return_value=[])
        _mock_capsule_repo.delete_semantic_edge = AsyncMock()
        _mock_capsule_repo.get_semantic_neighbors = AsyncMock(return_value=[])
        _mock_capsule_repo.find_contradictions = AsyncMock(return_value=[])
        _mock_capsule_repo.find_contradiction_clusters = AsyncMock(return_value=[])

        async def _test_get_capsule_repo():
            return _mock_capsule_repo

        application.dependency_overrides[get_capsule_repository] = _test_get_capsule_repo
    except ImportError:
        pass

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
