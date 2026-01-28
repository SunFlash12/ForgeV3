"""
Tests for Agent Gateway Service

Tests cover:
- Session management (create, authenticate, revoke, list)
- Rate limiting
- Query execution (NL, semantic search, graph traverse, direct Cypher, aggregation)
- Capsule creation
- Streaming responses
- ACP integration
- Trust-based access control
- Cache management
- Statistics
"""

import hashlib
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.agent_gateway import (
    AccessType,
    AgentCapability,
    AgentCapsuleCreation,
    AgentQuery,
    AgentSession,
    AgentTrustLevel,
    CapsuleAccess,
    GatewayStats,
    QueryResult,
    QueryType,
)
from forge.models.base import CapsuleType, TrustLevel
from forge.services.agent_gateway import AgentGatewayService, get_gateway_service


class TestAgentGatewayInit:
    """Tests for AgentGatewayService initialization."""

    def test_init_default(self):
        """Test default initialization."""
        service = AgentGatewayService()

        assert service.db is None
        assert service.capsule_repo is None
        assert service.query_compiler is None
        assert service.event_system is None
        assert isinstance(service._sessions, dict)
        assert isinstance(service._api_keys, dict)
        assert isinstance(service._rate_limits, dict)
        assert isinstance(service._query_cache, OrderedDict)
        assert isinstance(service._access_logs, list)
        assert isinstance(service._stats, GatewayStats)

    def test_init_with_dependencies(self):
        """Test initialization with dependencies."""
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_compiler = MagicMock()
        mock_events = MagicMock()

        service = AgentGatewayService(
            db_client=mock_db,
            capsule_repo=mock_repo,
            query_compiler=mock_compiler,
            event_system=mock_events,
        )

        assert service.db is mock_db
        assert service.capsule_repo is mock_repo
        assert service.query_compiler is mock_compiler
        assert service.event_system is mock_events

    def test_trust_level_values(self):
        """Test trust level value mappings."""
        service = AgentGatewayService()

        assert service.TRUST_LEVEL_VALUES[AgentTrustLevel.UNTRUSTED] == 0
        assert service.TRUST_LEVEL_VALUES[AgentTrustLevel.BASIC] == 1
        assert service.TRUST_LEVEL_VALUES[AgentTrustLevel.VERIFIED] == 2
        assert service.TRUST_LEVEL_VALUES[AgentTrustLevel.TRUSTED] == 3
        assert service.TRUST_LEVEL_VALUES[AgentTrustLevel.SYSTEM] == 4

    def test_default_capabilities_by_trust(self):
        """Test default capabilities for each trust level."""
        service = AgentGatewayService()

        # UNTRUSTED only has read
        assert AgentCapability.READ_CAPSULES in service.DEFAULT_CAPABILITIES[AgentTrustLevel.UNTRUSTED]
        assert AgentCapability.QUERY_GRAPH not in service.DEFAULT_CAPABILITIES[AgentTrustLevel.UNTRUSTED]

        # BASIC has query capabilities
        assert AgentCapability.QUERY_GRAPH in service.DEFAULT_CAPABILITIES[AgentTrustLevel.BASIC]

        # VERIFIED can create
        assert AgentCapability.CREATE_CAPSULES in service.DEFAULT_CAPABILITIES[AgentTrustLevel.VERIFIED]

        # TRUSTED can update and execute
        assert AgentCapability.UPDATE_CAPSULES in service.DEFAULT_CAPABILITIES[AgentTrustLevel.TRUSTED]
        assert AgentCapability.EXECUTE_CASCADE in service.DEFAULT_CAPABILITIES[AgentTrustLevel.TRUSTED]

        # SYSTEM has all capabilities
        assert len(service.DEFAULT_CAPABILITIES[AgentTrustLevel.SYSTEM]) == len(AgentCapability)

    def test_rate_limits_by_trust(self):
        """Test rate limits for each trust level."""
        service = AgentGatewayService()

        assert service.RATE_LIMITS[AgentTrustLevel.UNTRUSTED] == (10, 100)
        assert service.RATE_LIMITS[AgentTrustLevel.BASIC] == (60, 1000)
        assert service.RATE_LIMITS[AgentTrustLevel.SYSTEM] == (1000, 50000)


class TestSessionManagement:
    """Tests for session management."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.mark.asyncio
    async def test_create_session_default(self, service):
        """Test creating a session with defaults."""
        session, api_key = await service.create_session(
            agent_name="TestAgent",
            owner_user_id="user-123",
        )

        assert session.agent_name == "TestAgent"
        assert session.owner_user_id == "user-123"
        assert session.trust_level == AgentTrustLevel.BASIC
        assert session.is_active is True
        assert api_key.startswith("forge_agent_")
        assert session.id in service._sessions

    @pytest.mark.asyncio
    async def test_create_session_custom_trust(self, service):
        """Test creating a session with custom trust level."""
        session, api_key = await service.create_session(
            agent_name="TrustedAgent",
            owner_user_id="user-456",
            trust_level=AgentTrustLevel.TRUSTED,
        )

        assert session.trust_level == AgentTrustLevel.TRUSTED
        assert session.requests_per_minute == 300  # TRUSTED rate limit
        assert session.requests_per_hour == 10000
        assert AgentCapability.UPDATE_CAPSULES in session.capabilities

    @pytest.mark.asyncio
    async def test_create_session_custom_capabilities(self, service):
        """Test creating a session with custom capabilities."""
        capabilities = [AgentCapability.READ_CAPSULES, AgentCapability.SEMANTIC_SEARCH]

        session, _ = await service.create_session(
            agent_name="LimitedAgent",
            owner_user_id="user-789",
            capabilities=capabilities,
        )

        assert session.capabilities == capabilities

    @pytest.mark.asyncio
    async def test_create_session_with_expiry(self, service):
        """Test creating a session with custom expiry."""
        session, _ = await service.create_session(
            agent_name="ShortLivedAgent",
            owner_user_id="user-abc",
            expires_in_days=7,
        )

        expected_expiry = datetime.now(UTC) + timedelta(days=7)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 2

    @pytest.mark.asyncio
    async def test_authenticate_valid_key(self, service):
        """Test authentication with valid API key."""
        session, api_key = await service.create_session(
            agent_name="AuthAgent",
            owner_user_id="user-auth",
        )

        authenticated_session = await service.authenticate(api_key)

        assert authenticated_session is not None
        assert authenticated_session.id == session.id

    @pytest.mark.asyncio
    async def test_authenticate_invalid_key(self, service):
        """Test authentication with invalid API key."""
        result = await service.authenticate("invalid_key_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_expired_session(self, service):
        """Test authentication with expired session."""
        session, api_key = await service.create_session(
            agent_name="ExpiredAgent",
            owner_user_id="user-exp",
            expires_in_days=1,
        )

        # Manually expire the session
        session.expires_at = datetime.now(UTC) - timedelta(days=1)

        result = await service.authenticate(api_key)
        assert result is None
        assert session.is_active is False

    @pytest.mark.asyncio
    async def test_authenticate_inactive_session(self, service):
        """Test authentication with inactive session."""
        session, api_key = await service.create_session(
            agent_name="InactiveAgent",
            owner_user_id="user-inactive",
        )

        session.is_active = False

        result = await service.authenticate(api_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session(self, service):
        """Test getting session by ID."""
        session, _ = await service.create_session(
            agent_name="GetAgent",
            owner_user_id="user-get",
        )

        retrieved = await service.get_session(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service):
        """Test getting non-existent session."""
        result = await service.get_session("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_session(self, service):
        """Test revoking a session."""
        session, api_key = await service.create_session(
            agent_name="RevokeAgent",
            owner_user_id="user-revoke",
        )

        result = await service.revoke_session(session.id)

        assert result is True
        assert session.is_active is False
        # API key should be removed
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        assert api_key_hash not in service._api_keys

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self, service):
        """Test revoking non-existent session."""
        result = await service.revoke_session("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_sessions(self, service):
        """Test listing sessions."""
        await service.create_session(agent_name="Agent1", owner_user_id="user-1")
        await service.create_session(agent_name="Agent2", owner_user_id="user-1")
        await service.create_session(agent_name="Agent3", owner_user_id="user-2")

        all_sessions = await service.list_sessions()
        assert len(all_sessions) == 3

        user1_sessions = await service.list_sessions(owner_user_id="user-1")
        assert len(user1_sessions) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_active_only(self, service):
        """Test listing active sessions only."""
        session1, _ = await service.create_session(agent_name="Active", owner_user_id="user-a")
        session2, _ = await service.create_session(agent_name="Inactive", owner_user_id="user-a")
        session2.is_active = False

        active_sessions = await service.list_sessions(active_only=True)
        assert len(active_sessions) == 1
        assert active_sessions[0].id == session1.id


class TestRateLimiting:
    """Tests for rate limiting."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.mark.asyncio
    async def test_rate_limit_allowed(self, service):
        """Test rate limit allows requests under limit."""
        session, _ = await service.create_session(
            agent_name="RateLimitAgent",
            owner_user_id="user-rl",
        )

        allowed, reason = await service.check_rate_limit(session)

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_per_minute(self, service):
        """Test rate limit blocks when per-minute limit exceeded."""
        session, _ = await service.create_session(
            agent_name="RateLimitAgent",
            owner_user_id="user-rl",
            trust_level=AgentTrustLevel.UNTRUSTED,  # 10/min limit
        )

        # Make 10 requests to hit the limit
        for _ in range(10):
            await service.check_rate_limit(session)

        # 11th request should be blocked
        allowed, reason = await service.check_rate_limit(session)

        assert allowed is False
        assert "10/minute" in reason

    @pytest.mark.asyncio
    async def test_rate_limit_cleans_old_entries(self, service):
        """Test rate limit cleans old entries."""
        session, _ = await service.create_session(
            agent_name="CleanAgent",
            owner_user_id="user-clean",
        )

        # Add old entry manually
        old_time = datetime.now(UTC) - timedelta(hours=2)
        service._rate_limits[session.id] = [old_time]

        await service.check_rate_limit(session)

        # Old entry should be cleaned
        assert len(service._rate_limits[session.id]) == 1  # Only the new entry


class TestQueryExecution:
    """Tests for query execution."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.fixture
    def mock_session(self):
        return AgentSession(
            agent_id="agent-test",
            agent_name="TestAgent",
            api_key_hash="hash",
            owner_user_id="user-test",
            trust_level=AgentTrustLevel.TRUSTED,
            capabilities=list(AgentCapability),
            requests_per_minute=1000,
            requests_per_hour=50000,
        )

    @pytest.mark.asyncio
    async def test_execute_query_rate_limited(self, service, mock_session):
        """Test query execution returns error when rate limited."""
        # Exhaust rate limit
        service._rate_limits[mock_session.id] = [
            datetime.now(UTC) for _ in range(mock_session.requests_per_minute + 1)
        ]

        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.NATURAL_LANGUAGE,
            query_text="test query",
        )

        result = await service.execute_query(mock_session, query)

        assert result.success is False
        assert result.error_code == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_execute_query_missing_capability(self, service):
        """Test query execution returns error when capability missing."""
        session = AgentSession(
            agent_id="agent-limited",
            agent_name="LimitedAgent",
            api_key_hash="hash",
            owner_user_id="user-limited",
            trust_level=AgentTrustLevel.UNTRUSTED,
            capabilities=[AgentCapability.READ_CAPSULES],  # No QUERY_GRAPH
            requests_per_minute=100,
            requests_per_hour=1000,
        )

        query = AgentQuery(
            session_id=session.id,
            agent_id=session.agent_id,
            query_type=QueryType.NATURAL_LANGUAGE,
            query_text="test query",
        )

        result = await service.execute_query(session, query)

        assert result.success is False
        assert result.error_code == "FORBIDDEN"
        assert "Missing capability" in result.error

    @pytest.mark.asyncio
    async def test_execute_query_cache_hit(self, service, mock_session):
        """Test query execution returns cached result."""
        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="cached query",
        )

        # Pre-cache a result
        cache_key = service._get_cache_key(query)
        cached_result = QueryResult(
            query_id=query.id,
            session_id=mock_session.id,
            success=True,
            results=[{"cached": True}],
        )
        service._query_cache[cache_key] = cached_result

        result = await service.execute_query(mock_session, query)

        assert result.cache_hit is True

    @pytest.mark.asyncio
    async def test_execute_semantic_search_no_repo(self, service, mock_session):
        """Test semantic search without capsule repo."""
        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="search query",
        )

        result = await service.execute_query(mock_session, query)

        assert result.success is True
        assert result.results == []

    @pytest.mark.asyncio
    async def test_execute_semantic_search_with_repo(self, service, mock_session):
        """Test semantic search with capsule repo."""
        mock_capsule = MagicMock()
        mock_capsule.id = "capsule-1"
        mock_capsule.title = "Test Capsule"
        mock_capsule.type = CapsuleType.CLAIM
        mock_capsule.content = "Test content"
        mock_capsule.trust_level = 3
        mock_capsule.created_at = datetime.now(UTC)

        mock_repo = AsyncMock()
        mock_repo.search_by_text = AsyncMock(return_value=[mock_capsule])

        service.capsule_repo = mock_repo
        service._can_access_capsule = AsyncMock(return_value=True)

        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="search query",
        )

        result = await service.execute_query(mock_session, query)

        assert result.success is True
        assert len(result.results) > 0
        assert result.results[0]["capsule_id"] == "capsule-1"

    @pytest.mark.asyncio
    async def test_execute_direct_cypher_untrusted(self, service):
        """Test direct Cypher query fails for untrusted agents."""
        session = AgentSession(
            agent_id="agent-basic",
            agent_name="BasicAgent",
            api_key_hash="hash",
            owner_user_id="user-basic",
            trust_level=AgentTrustLevel.BASIC,
            capabilities=list(AgentCapability),
            requests_per_minute=100,
            requests_per_hour=1000,
        )

        query = AgentQuery(
            session_id=session.id,
            agent_id=session.agent_id,
            query_type=QueryType.DIRECT_CYPHER,
            query_text="MATCH (n) RETURN n LIMIT 10",
        )

        result = await service.execute_query(session, query)

        assert result.success is False
        assert "TRUSTED trust level" in result.error

    @pytest.mark.asyncio
    async def test_execute_unknown_query_type(self, service, mock_session):
        """Test handling of invalid query type."""
        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.NATURAL_LANGUAGE,
            query_text="test query",
        )
        # Force an invalid query type
        query.query_type = MagicMock(value="unknown")

        result = await service.execute_query(mock_session, query)

        assert result.success is False
        assert "Unknown query type" in result.error

    @pytest.mark.asyncio
    async def test_execute_query_updates_stats(self, service, mock_session):
        """Test query execution updates statistics."""
        initial_queries = service._stats.queries_today

        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="stats query",
        )

        await service.execute_query(mock_session, query)

        assert service._stats.queries_today == initial_queries + 1
        assert QueryType.SEMANTIC_SEARCH.value in service._stats.queries_by_type

    @pytest.mark.asyncio
    async def test_execute_query_updates_session(self, service, mock_session):
        """Test query execution updates session stats."""
        initial_requests = mock_session.total_requests

        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="session stats query",
        )

        await service.execute_query(mock_session, query)

        assert mock_session.total_requests == initial_requests + 1
        assert mock_session.last_request_at is not None


class TestCypherValidation:
    """Tests for Cypher query validation."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    def test_validate_read_only_query(self, service):
        """Test validation allows read-only queries."""
        valid_queries = [
            "MATCH (n) RETURN n LIMIT 10",
            "MATCH (a)-[r]->(b) RETURN a, r, b",
            "OPTIONAL MATCH (n:Capsule) RETURN n.title",
            "WITH 1 as num RETURN num",
            "UNWIND [1, 2, 3] as x RETURN x",
        ]

        for query in valid_queries:
            is_valid, error = service._validate_cypher_read_only(query)
            assert is_valid, f"Query should be valid: {query}, got error: {error}"

    def test_validate_blocks_mutations(self, service):
        """Test validation blocks mutation operations."""
        invalid_queries = [
            "CREATE (n:Node {name: 'test'})",
            "MERGE (n:Node {name: 'test'})",
            "MATCH (n) DELETE n",
            "MATCH (n) DETACH DELETE n",
            "MATCH (n) SET n.name = 'new'",
            "MATCH (n) REMOVE n.property",
        ]

        for query in invalid_queries:
            is_valid, error = service._validate_cypher_read_only(query)
            assert not is_valid, f"Query should be invalid: {query}"

    def test_validate_blocks_schema_operations(self, service):
        """Test validation blocks schema operations."""
        invalid_queries = [
            "DROP CONSTRAINT constraint_name",
            "CREATE INDEX FOR (n:Node) ON (n.name)",
        ]

        for query in invalid_queries:
            is_valid, error = service._validate_cypher_read_only(query)
            assert not is_valid, f"Query should be invalid: {query}"

    def test_validate_blocks_call_operations(self, service):
        """Test validation blocks CALL operations."""
        invalid_queries = [
            "CALL db.schema.nodeTypeProperties()",
            "CALL { CREATE (n:Node) }",
        ]

        for query in invalid_queries:
            is_valid, error = service._validate_cypher_read_only(query)
            assert not is_valid, f"Query should be invalid: {query}"

    def test_validate_requires_allowed_start(self, service):
        """Test validation requires allowed starting clause."""
        is_valid, error = service._validate_cypher_read_only("SOME_RANDOM_CLAUSE")
        assert not is_valid
        assert "must start with" in error.lower()


class TestCapsuleCreation:
    """Tests for capsule creation."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.fixture
    def mock_session(self):
        return AgentSession(
            agent_id="agent-creator",
            agent_name="CreatorAgent",
            api_key_hash="hash",
            owner_user_id="user-creator",
            trust_level=AgentTrustLevel.VERIFIED,
            capabilities=[AgentCapability.CREATE_CAPSULES, AgentCapability.READ_CAPSULES],
            requests_per_minute=100,
            requests_per_hour=1000,
        )

    @pytest.mark.asyncio
    async def test_create_capsule_missing_capability(self, service):
        """Test capsule creation fails without capability."""
        session = AgentSession(
            agent_id="agent-nocreate",
            agent_name="NoCreateAgent",
            api_key_hash="hash",
            owner_user_id="user-nocreate",
            trust_level=AgentTrustLevel.BASIC,
            capabilities=[AgentCapability.READ_CAPSULES],
            requests_per_minute=100,
            requests_per_hour=1000,
        )

        request = AgentCapsuleCreation(
            session_id=session.id,
            agent_id=session.agent_id,
            capsule_type="claim",
            title="Test Capsule",
            content="Test content",
        )

        with pytest.raises(ValueError, match="CREATE_CAPSULES capability"):
            await service.create_capsule(session, request)

    @pytest.mark.asyncio
    async def test_create_capsule_no_repo(self, service, mock_session):
        """Test capsule creation without repo returns error."""
        request = AgentCapsuleCreation(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            capsule_type="claim",
            title="Test Capsule",
            content="Test content",
        )

        result = await service.create_capsule(mock_session, request)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_capsule_with_repo(self, service, mock_session):
        """Test capsule creation with repo."""
        mock_capsule = MagicMock()
        mock_capsule.id = "new-capsule-id"
        mock_capsule.trust_level = 2

        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=mock_capsule)

        service.capsule_repo = mock_repo

        request = AgentCapsuleCreation(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            capsule_type="claim",
            title="Test Capsule",
            content="Test content",
            requires_approval=False,
        )

        result = await service.create_capsule(mock_session, request)

        assert result["capsule_id"] == "new-capsule-id"
        assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_create_capsule_requires_approval(self, service, mock_session):
        """Test capsule creation with approval required."""
        mock_capsule = MagicMock()
        mock_capsule.id = "approval-capsule-id"
        mock_capsule.trust_level = 2

        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(return_value=mock_capsule)

        service.capsule_repo = mock_repo

        request = AgentCapsuleCreation(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            capsule_type="claim",
            title="Needs Approval",
            content="Content needs approval",
            requires_approval=True,
        )

        result = await service.create_capsule(mock_session, request)

        assert result["status"] == "pending_approval"


class TestStreamQuery:
    """Tests for streaming query responses."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.fixture
    def mock_session(self):
        return AgentSession(
            agent_id="agent-stream",
            agent_name="StreamAgent",
            api_key_hash="hash",
            owner_user_id="user-stream",
            trust_level=AgentTrustLevel.TRUSTED,
            capabilities=list(AgentCapability),
            requests_per_minute=100,
            requests_per_hour=1000,
        )

    @pytest.mark.asyncio
    async def test_stream_query(self, service, mock_session):
        """Test streaming query execution."""
        query = AgentQuery(
            session_id=mock_session.id,
            agent_id=mock_session.agent_id,
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="stream query",
        )

        chunks = []
        async for chunk in service.stream_query(mock_session, query):
            chunks.append(chunk)

        assert len(chunks) >= 2  # At least start and done
        assert chunks[0].content == "Processing query..."
        assert chunks[-1].is_final is True
        assert chunks[-1].content_type == "done"


class TestCacheLimits:
    """Tests for cache limit enforcement."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    def test_enforce_cache_limits_sessions(self, service):
        """Test session cache limit enforcement."""
        service.MAX_SESSIONS = 5

        # Add more sessions than limit
        for i in range(10):
            service._sessions[f"session-{i}"] = MagicMock()

        service._enforce_cache_limits()

        assert len(service._sessions) <= service.MAX_SESSIONS

    def test_enforce_cache_limits_api_keys(self, service):
        """Test API key cache limit enforcement."""
        service.MAX_API_KEYS = 5

        for i in range(10):
            service._api_keys[f"key-{i}"] = f"session-{i}"

        service._enforce_cache_limits()

        assert len(service._api_keys) <= service.MAX_API_KEYS

    def test_enforce_cache_limits_query_cache(self, service):
        """Test query cache limit enforcement."""
        service.MAX_QUERY_CACHE = 5

        for i in range(10):
            service._query_cache[f"query-{i}"] = MagicMock()

        service._enforce_cache_limits()

        assert len(service._query_cache) <= service.MAX_QUERY_CACHE

    def test_enforce_cache_limits_access_logs(self, service):
        """Test access logs limit enforcement."""
        service.MAX_ACCESS_LOGS = 5

        for i in range(10):
            service._access_logs.append(MagicMock())

        service._enforce_cache_limits()

        assert len(service._access_logs) <= service.MAX_ACCESS_LOGS


class TestTrustFiltering:
    """Tests for trust-based access filtering."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.mark.asyncio
    async def test_filter_by_trust_untrusted(self, service):
        """Test filtering for UNTRUSTED agent."""
        session = AgentSession(
            agent_id="agent-untrusted",
            agent_name="UntrustedAgent",
            api_key_hash="hash",
            owner_user_id="user-untrusted",
            trust_level=AgentTrustLevel.UNTRUSTED,
            capabilities=[],
            requests_per_minute=10,
            requests_per_hour=100,
        )

        records = [
            {"id": "1", "trust_level": TrustLevel.TRUSTED.value},  # Should pass
            {"id": "2", "trust_level": TrustLevel.STANDARD.value},  # Should fail
            {"id": "3", "trust_level": TrustLevel.QUARANTINE.value},  # Should fail
        ]

        filtered = await service._filter_by_trust(session, records)

        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_filter_by_trust_system(self, service):
        """Test filtering for SYSTEM agent (should see all)."""
        session = AgentSession(
            agent_id="agent-system",
            agent_name="SystemAgent",
            api_key_hash="hash",
            owner_user_id="user-system",
            trust_level=AgentTrustLevel.SYSTEM,
            capabilities=list(AgentCapability),
            requests_per_minute=1000,
            requests_per_hour=50000,
        )

        records = [
            {"id": "1", "trust_level": TrustLevel.QUARANTINE.value},
            {"id": "2", "trust_level": TrustLevel.SANDBOX.value},
            {"id": "3", "trust_level": TrustLevel.TRUSTED.value},
        ]

        filtered = await service._filter_by_trust(session, records)

        assert len(filtered) == 3

    @pytest.mark.asyncio
    async def test_can_access_by_trust_level(self, service):
        """Test trust level access check."""
        session = AgentSession(
            agent_id="agent-trusted",
            agent_name="TrustedAgent",
            api_key_hash="hash",
            owner_user_id="user-trusted",
            trust_level=AgentTrustLevel.TRUSTED,
            capabilities=list(AgentCapability),
            requests_per_minute=300,
            requests_per_hour=10000,
        )

        # TRUSTED agents can access all trust levels
        assert await service._can_access_by_trust_level(session, 0) is True
        assert await service._can_access_by_trust_level(session, 1) is True
        assert await service._can_access_by_trust_level(session, 5) is True


class TestACPIntegration:
    """Tests for ACP (Agent Commerce Protocol) integration."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.mark.asyncio
    async def test_get_acp_capabilities(self, service):
        """Test getting ACP service types for session."""
        session, _ = await service.create_session(
            agent_name="ACPAgent",
            owner_user_id="user-acp",
            capabilities=[
                AgentCapability.QUERY_GRAPH,
                AgentCapability.SEMANTIC_SEARCH,
            ],
        )

        capabilities = await service.get_acp_capabilities(session.id)

        assert "knowledge_query" in capabilities
        assert "semantic_search" in capabilities

    @pytest.mark.asyncio
    async def test_get_acp_capabilities_not_found(self, service):
        """Test getting ACP capabilities for non-existent session."""
        capabilities = await service.get_acp_capabilities("nonexistent-id")
        assert capabilities == []

    @pytest.mark.asyncio
    async def test_to_acp_offering(self, service):
        """Test converting session to ACP offering."""
        session, _ = await service.create_session(
            agent_name="OfferingAgent",
            owner_user_id="user-offering",
            capabilities=[AgentCapability.QUERY_GRAPH, AgentCapability.SEMANTIC_SEARCH],
        )

        offering = await service.to_acp_offering(
            session_id=session.id,
            service_type="knowledge_query",
            title="Knowledge Query Service",
            description="Query the knowledge graph",
            base_fee_virtual=0.5,
        )

        assert offering["provider_agent_id"] == session.agent_id
        assert offering["service_type"] == "knowledge_query"
        assert offering["title"] == "Knowledge Query Service"
        assert offering["base_fee_virtual"] == 0.5
        assert "input_schema" in offering
        assert "output_schema" in offering

    @pytest.mark.asyncio
    async def test_to_acp_offering_not_found(self, service):
        """Test ACP offering for non-existent session."""
        with pytest.raises(ValueError, match="not found"):
            await service.to_acp_offering(
                session_id="nonexistent",
                service_type="knowledge_query",
                title="Test",
                description="Test",
                base_fee_virtual=0.1,
            )

    @pytest.mark.asyncio
    async def test_execute_acp_job(self, service):
        """Test executing an ACP job."""
        session, _ = await service.create_session(
            agent_name="JobAgent",
            owner_user_id="user-job",
            trust_level=AgentTrustLevel.TRUSTED,
        )

        result = await service.execute_acp_job(
            session_id=session.id,
            job_requirements="Find information about AI",
            input_data={"query_text": "artificial intelligence", "query_type": "semantic_search"},
        )

        assert "success" in result
        assert "results" in result

    @pytest.mark.asyncio
    async def test_execute_acp_job_not_found(self, service):
        """Test ACP job execution for non-existent session."""
        with pytest.raises(ValueError, match="not found"):
            await service.execute_acp_job(
                session_id="nonexistent",
                job_requirements="test",
                input_data={},
            )


class TestStatistics:
    """Tests for statistics."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    @pytest.mark.asyncio
    async def test_get_stats(self, service):
        """Test getting gateway statistics."""
        # Create some sessions
        await service.create_session(agent_name="Agent1", owner_user_id="user-1")
        await service.create_session(agent_name="Agent2", owner_user_id="user-2")

        stats = await service.get_stats()

        assert stats.total_sessions >= 2
        assert stats.active_sessions >= 2
        assert stats.calculated_at is not None

    @pytest.mark.asyncio
    async def test_get_stats_error_rate(self, service):
        """Test error rate calculation in stats."""
        service._stats.queries_today = 100
        service._stats.error_count = 5

        stats = await service.get_stats()

        assert stats.error_rate == 0.05

    @pytest.mark.asyncio
    async def test_get_access_logs(self, service):
        """Test getting access logs."""
        # Add some logs
        for i in range(5):
            service._access_logs.append(
                CapsuleAccess(
                    session_id=f"session-{i}",
                    agent_id=f"agent-{i}",
                    capsule_id=f"capsule-{i}",
                    access_type=AccessType.READ,
                    capsule_trust_level=3,
                    agent_trust_level=AgentTrustLevel.BASIC,
                    access_granted=True,
                )
            )

        logs = await service.get_access_logs()
        assert len(logs) == 5

        # Test filtering
        logs_filtered = await service.get_access_logs(session_id="session-0")
        assert len(logs_filtered) == 1

    @pytest.mark.asyncio
    async def test_get_access_logs_limit(self, service):
        """Test access logs limit."""
        for i in range(10):
            service._access_logs.append(
                CapsuleAccess(
                    session_id=f"session-{i}",
                    agent_id=f"agent-{i}",
                    capsule_id=f"capsule-{i}",
                    access_type=AccessType.READ,
                    capsule_trust_level=3,
                    agent_trust_level=AgentTrustLevel.BASIC,
                    access_granted=True,
                )
            )

        logs = await service.get_access_logs(limit=5)
        assert len(logs) == 5


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def service(self):
        return AgentGatewayService()

    def test_get_required_capability(self, service):
        """Test getting required capability for query type."""
        assert service._get_required_capability(QueryType.NATURAL_LANGUAGE) == AgentCapability.QUERY_GRAPH
        assert service._get_required_capability(QueryType.SEMANTIC_SEARCH) == AgentCapability.SEMANTIC_SEARCH
        assert service._get_required_capability(QueryType.GRAPH_TRAVERSE) == AgentCapability.QUERY_GRAPH

    def test_get_cache_key(self, service):
        """Test cache key generation."""
        query = AgentQuery(
            session_id="session-1",
            agent_id="agent-1",
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="test query",
            max_results=10,
        )

        key = service._get_cache_key(query)

        assert key is not None
        assert len(key) == 32  # MD5 hex length

    def test_get_cache_key_direct_cypher_returns_none(self, service):
        """Test direct Cypher queries are not cached."""
        query = AgentQuery(
            session_id="session-1",
            agent_id="agent-1",
            query_type=QueryType.DIRECT_CYPHER,
            query_text="MATCH (n) RETURN n",
        )

        key = service._get_cache_key(query)

        assert key is None

    @pytest.mark.asyncio
    async def test_synthesize_answer_no_results(self, service):
        """Test answer synthesis with no results."""
        answer = await service._synthesize_answer("test question", [])
        assert "No relevant information" in answer

    @pytest.mark.asyncio
    async def test_synthesize_answer_with_results(self, service):
        """Test answer synthesis with results."""
        results = [
            {"type": "claim", "content_preview": "This is test content"},
            {"type": "evidence", "content_preview": "More content"},
        ]

        answer = await service._synthesize_answer("test question", results)

        assert "2 relevant capsule" in answer
        assert "claim" in answer

    def test_extract_sources(self, service):
        """Test source extraction from results."""
        results = [
            {"capsule_id": "cap-1", "title": "Title 1", "type": "claim"},
            {"capsule_id": "cap-2", "title": "Title 2", "type": "evidence"},
            {"no_id": True},  # Should be skipped
        ]

        sources = service._extract_sources(results)

        assert len(sources) == 2
        assert sources[0]["capsule_id"] == "cap-1"


class TestSingletonGetter:
    """Tests for the singleton getter."""

    @pytest.mark.asyncio
    async def test_get_gateway_service(self):
        """Test getting the singleton instance."""
        # Clear any existing instance
        import forge.services.agent_gateway as module
        module._gateway_service = None

        service = await get_gateway_service()

        assert service is not None
        assert isinstance(service, AgentGatewayService)

        # Should return same instance
        service2 = await get_gateway_service()
        assert service is service2
