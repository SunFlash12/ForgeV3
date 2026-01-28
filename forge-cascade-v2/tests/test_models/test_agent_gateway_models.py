"""
Agent Gateway Model Tests for Forge Cascade V2

Comprehensive tests for agent gateway models including:
- AgentCapability, AgentTrustLevel, QueryType, ResponseFormat enums
- AccessType enum
- AgentSession model
- AgentQuery model with security validation
- QueryResult model
- CapsuleAccess model
- AgentCapsuleCreation model with security validation
- GatewayStats model
- StreamChunk model
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

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
    ResponseFormat,
    StreamChunk,
)


# =============================================================================
# AgentCapability Enum Tests
# =============================================================================


class TestAgentCapability:
    """Tests for AgentCapability enum."""

    def test_agent_capability_values(self):
        """AgentCapability has expected values."""
        assert AgentCapability.READ_CAPSULES.value == "read_capsules"
        assert AgentCapability.QUERY_GRAPH.value == "query_graph"
        assert AgentCapability.SEMANTIC_SEARCH.value == "semantic_search"
        assert AgentCapability.CREATE_CAPSULES.value == "create_capsules"
        assert AgentCapability.UPDATE_CAPSULES.value == "update_capsules"
        assert AgentCapability.EXECUTE_CASCADE.value == "execute_cascade"
        assert AgentCapability.ACCESS_LINEAGE.value == "access_lineage"
        assert AgentCapability.VIEW_GOVERNANCE.value == "view_governance"

    def test_agent_capability_count(self):
        """AgentCapability has expected number of values."""
        assert len(AgentCapability) == 8


# =============================================================================
# AgentTrustLevel Enum Tests
# =============================================================================


class TestAgentTrustLevel:
    """Tests for AgentTrustLevel enum."""

    def test_agent_trust_level_values(self):
        """AgentTrustLevel has expected values."""
        assert AgentTrustLevel.UNTRUSTED.value == "untrusted"
        assert AgentTrustLevel.BASIC.value == "basic"
        assert AgentTrustLevel.VERIFIED.value == "verified"
        assert AgentTrustLevel.TRUSTED.value == "trusted"
        assert AgentTrustLevel.SYSTEM.value == "system"

    def test_agent_trust_level_count(self):
        """AgentTrustLevel has expected number of values."""
        assert len(AgentTrustLevel) == 5


# =============================================================================
# QueryType Enum Tests
# =============================================================================


class TestQueryType:
    """Tests for QueryType enum."""

    def test_query_type_values(self):
        """QueryType has expected values."""
        assert QueryType.NATURAL_LANGUAGE.value == "natural_language"
        assert QueryType.SEMANTIC_SEARCH.value == "semantic_search"
        assert QueryType.GRAPH_TRAVERSE.value == "graph_traverse"
        assert QueryType.DIRECT_CYPHER.value == "direct_cypher"
        assert QueryType.AGGREGATION.value == "aggregation"

    def test_query_type_count(self):
        """QueryType has expected number of values."""
        assert len(QueryType) == 5


# =============================================================================
# ResponseFormat Enum Tests
# =============================================================================


class TestResponseFormat:
    """Tests for ResponseFormat enum."""

    def test_response_format_values(self):
        """ResponseFormat has expected values."""
        assert ResponseFormat.JSON.value == "json"
        assert ResponseFormat.MARKDOWN.value == "markdown"
        assert ResponseFormat.PLAIN.value == "plain"
        assert ResponseFormat.STREAMING.value == "streaming"

    def test_response_format_count(self):
        """ResponseFormat has expected number of values."""
        assert len(ResponseFormat) == 4


# =============================================================================
# AccessType Enum Tests
# =============================================================================


class TestAccessType:
    """Tests for AccessType enum."""

    def test_access_type_values(self):
        """AccessType has expected values."""
        assert AccessType.READ.value == "read"
        assert AccessType.WRITE.value == "write"
        assert AccessType.DERIVE.value == "derive"

    def test_access_type_count(self):
        """AccessType has expected number of values."""
        assert len(AccessType) == 3


# =============================================================================
# AgentSession Tests
# =============================================================================


class TestAgentSession:
    """Tests for AgentSession model."""

    def test_valid_agent_session(self):
        """Valid AgentSession data creates model."""
        session = AgentSession(
            agent_id="agent123",
            agent_name="Test Agent",
            api_key_hash="$2b$12$hashedapikey",
            owner_user_id="user456",
        )

        assert session.agent_id == "agent123"
        assert session.agent_name == "Test Agent"
        assert session.api_key_hash == "$2b$12$hashedapikey"
        assert session.owner_user_id == "user456"
        assert session.id is not None  # auto-generated

    def test_agent_session_defaults(self):
        """AgentSession has sensible defaults."""
        session = AgentSession(
            agent_id="agent123",
            agent_name="Test Agent",
            api_key_hash="hash",
            owner_user_id="user456",
        )

        assert session.trust_level == AgentTrustLevel.BASIC.value
        assert session.capabilities == []
        assert session.allowed_capsule_types == []
        assert session.requests_per_minute == 60
        assert session.requests_per_hour == 1000
        assert session.max_tokens_per_request == 4096
        assert session.total_requests == 0
        assert session.total_tokens == 0
        assert session.last_request_at is None
        assert session.is_active is True
        assert session.created_at is not None
        assert session.expires_at is None
        assert session.metadata == {}

    def test_agent_session_with_capabilities(self):
        """AgentSession with capabilities."""
        session = AgentSession(
            agent_id="agent123",
            agent_name="Advanced Agent",
            api_key_hash="hash",
            owner_user_id="user456",
            trust_level=AgentTrustLevel.TRUSTED,
            capabilities=[
                AgentCapability.READ_CAPSULES,
                AgentCapability.CREATE_CAPSULES,
                AgentCapability.SEMANTIC_SEARCH,
            ],
            allowed_capsule_types=["INSIGHT", "KNOWLEDGE"],
        )

        assert session.trust_level == AgentTrustLevel.TRUSTED.value
        assert len(session.capabilities) == 3

    def test_agent_session_with_expiration(self):
        """AgentSession with expiration time."""
        expires = datetime.now(UTC) + timedelta(hours=24)
        session = AgentSession(
            agent_id="agent123",
            agent_name="Test Agent",
            api_key_hash="hash",
            owner_user_id="user456",
            expires_at=expires,
        )

        assert session.expires_at is not None

    def test_agent_session_with_usage_tracking(self):
        """AgentSession with usage tracking."""
        session = AgentSession(
            agent_id="agent123",
            agent_name="Test Agent",
            api_key_hash="hash",
            owner_user_id="user456",
            total_requests=150,
            total_tokens=50000,
            last_request_at=datetime.now(UTC),
        )

        assert session.total_requests == 150
        assert session.total_tokens == 50000
        assert session.last_request_at is not None


# =============================================================================
# AgentQuery Tests
# =============================================================================


class TestAgentQuery:
    """Tests for AgentQuery model."""

    def test_valid_agent_query(self):
        """Valid AgentQuery data creates model."""
        query = AgentQuery(
            session_id="session123",
            agent_id="agent456",
            query_type=QueryType.NATURAL_LANGUAGE,
            query_text="Find all capsules about machine learning",
        )

        assert query.session_id == "session123"
        assert query.agent_id == "agent456"
        assert query.query_type == QueryType.NATURAL_LANGUAGE.value
        assert query.query_text == "Find all capsules about machine learning"
        assert query.id is not None  # auto-generated

    def test_agent_query_defaults(self):
        """AgentQuery has sensible defaults."""
        query = AgentQuery(
            session_id="s1",
            agent_id="a1",
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="test query",
        )

        assert query.context == {}
        assert query.filters == {}
        assert query.response_format == ResponseFormat.JSON.value
        assert query.max_results == 10
        assert query.include_metadata is True
        assert query.include_lineage is False
        assert query.submitted_at is not None
        assert query.timeout_seconds == 30

    def test_agent_query_with_filters(self):
        """AgentQuery with filters and context."""
        query = AgentQuery(
            session_id="s1",
            agent_id="a1",
            query_type=QueryType.GRAPH_TRAVERSE,
            query_text="Find related capsules",
            context={"source_capsule": "c123"},
            filters={"trust_level": 60, "capsule_type": "INSIGHT"},
        )

        assert query.context["source_capsule"] == "c123"
        assert query.filters["trust_level"] == 60

    def test_agent_query_max_results_bounds(self):
        """max_results must be between 1 and 100."""
        with pytest.raises(ValidationError):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                max_results=0,
            )

        with pytest.raises(ValidationError):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                max_results=101,
            )

    def test_agent_query_timeout_bounds(self):
        """timeout_seconds must be between 1 and 300."""
        with pytest.raises(ValidationError):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                timeout_seconds=0,
            )

        with pytest.raises(ValidationError):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                timeout_seconds=301,
            )

    def test_agent_query_security_validation_context(self):
        """context dict is validated for security concerns."""
        # Forbidden keys should be rejected
        with pytest.raises(ValidationError, match="Forbidden keys"):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                context={"__proto__": "malicious"},
            )

    def test_agent_query_security_validation_filters(self):
        """filters dict is validated for security concerns."""
        # Forbidden keys should be rejected
        with pytest.raises(ValidationError, match="Forbidden keys"):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                filters={"constructor": "malicious"},
            )

    def test_agent_query_security_nested_forbidden_keys(self):
        """Nested forbidden keys are detected."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            AgentQuery(
                session_id="s1",
                agent_id="a1",
                query_type=QueryType.NATURAL_LANGUAGE,
                query_text="test",
                context={"nested": {"__class__": "attack"}},
            )


# =============================================================================
# QueryResult Tests
# =============================================================================


class TestQueryResult:
    """Tests for QueryResult model."""

    def test_valid_query_result(self):
        """Valid QueryResult data creates model."""
        result = QueryResult(
            query_id="query123",
            session_id="session456",
            success=True,
            results=[{"id": "c1", "title": "Capsule 1"}, {"id": "c2", "title": "Capsule 2"}],
            total_count=2,
        )

        assert result.query_id == "query123"
        assert result.success is True
        assert len(result.results) == 2

    def test_query_result_defaults(self):
        """QueryResult has sensible defaults."""
        result = QueryResult(
            query_id="q1",
            session_id="s1",
            success=True,
        )

        assert result.results == []
        assert result.total_count == 0
        assert result.generated_cypher is None
        assert result.cypher_explanation is None
        assert result.answer is None
        assert result.sources == []
        assert result.execution_time_ms == 0
        assert result.tokens_used == 0
        assert result.cache_hit is False
        assert result.error is None
        assert result.error_code is None
        assert result.completed_at is not None

    def test_query_result_with_nl_details(self):
        """QueryResult with natural language query details."""
        result = QueryResult(
            query_id="q1",
            session_id="s1",
            success=True,
            results=[{"id": "c1"}],
            total_count=1,
            generated_cypher="MATCH (n:Capsule) RETURN n LIMIT 10",
            cypher_explanation="Query to find all capsules limited to 10 results",
            answer="I found 1 capsule matching your query.",
            sources=[{"id": "c1", "title": "Source Capsule"}],
        )

        assert result.generated_cypher is not None
        assert result.answer is not None
        assert len(result.sources) == 1

    def test_query_result_with_error(self):
        """QueryResult with error."""
        result = QueryResult(
            query_id="q1",
            session_id="s1",
            success=False,
            error="Query timeout exceeded",
            error_code="TIMEOUT",
        )

        assert result.success is False
        assert result.error == "Query timeout exceeded"
        assert result.error_code == "TIMEOUT"


# =============================================================================
# CapsuleAccess Tests
# =============================================================================


class TestCapsuleAccess:
    """Tests for CapsuleAccess model."""

    def test_valid_capsule_access(self):
        """Valid CapsuleAccess data creates model."""
        access = CapsuleAccess(
            session_id="session123",
            agent_id="agent456",
            capsule_id="capsule789",
            access_type=AccessType.READ,
            capsule_trust_level=80,
            agent_trust_level=AgentTrustLevel.VERIFIED,
            access_granted=True,
        )

        assert access.session_id == "session123"
        assert access.access_type == AccessType.READ.value
        assert access.access_granted is True
        assert access.id is not None  # auto-generated

    def test_capsule_access_defaults(self):
        """CapsuleAccess has sensible defaults."""
        access = CapsuleAccess(
            session_id="s1",
            agent_id="a1",
            capsule_id="c1",
            access_type=AccessType.DERIVE,
            capsule_trust_level=60,
            agent_trust_level=AgentTrustLevel.BASIC,
            access_granted=False,
        )

        assert access.query_id is None
        assert access.denial_reason is None
        assert access.accessed_at is not None

    def test_capsule_access_denied_with_reason(self):
        """CapsuleAccess with denial reason."""
        access = CapsuleAccess(
            session_id="s1",
            agent_id="a1",
            capsule_id="c1",
            access_type=AccessType.WRITE,
            capsule_trust_level=80,
            agent_trust_level=AgentTrustLevel.BASIC,
            access_granted=False,
            denial_reason="Insufficient trust level for write access",
        )

        assert access.access_granted is False
        assert access.denial_reason == "Insufficient trust level for write access"


# =============================================================================
# AgentCapsuleCreation Tests
# =============================================================================


class TestAgentCapsuleCreation:
    """Tests for AgentCapsuleCreation model."""

    def test_valid_agent_capsule_creation(self):
        """Valid AgentCapsuleCreation data creates model."""
        creation = AgentCapsuleCreation(
            session_id="session123",
            agent_id="agent456",
            capsule_type="INSIGHT",
            title="New Insight",
            content="This is the content of the new insight.",
        )

        assert creation.session_id == "session123"
        assert creation.capsule_type == "INSIGHT"
        assert creation.title == "New Insight"
        assert creation.id is not None  # auto-generated

    def test_agent_capsule_creation_defaults(self):
        """AgentCapsuleCreation has sensible defaults."""
        creation = AgentCapsuleCreation(
            session_id="s1",
            agent_id="a1",
            capsule_type="KNOWLEDGE",
            title="Test",
            content="Content",
        )

        assert creation.source_capsule_ids == []
        assert creation.reasoning is None
        assert creation.tags == []
        assert creation.metadata == {}
        assert creation.requires_approval is True

    def test_agent_capsule_creation_with_provenance(self):
        """AgentCapsuleCreation with provenance information."""
        creation = AgentCapsuleCreation(
            session_id="s1",
            agent_id="a1",
            capsule_type="INSIGHT",
            title="Derived Insight",
            content="Content derived from sources",
            source_capsule_ids=["c1", "c2", "c3"],
            reasoning="Synthesized from multiple source capsules",
            tags=["machine-learning", "summary"],
            requires_approval=False,
        )

        assert len(creation.source_capsule_ids) == 3
        assert creation.reasoning is not None
        assert "machine-learning" in creation.tags
        assert creation.requires_approval is False

    def test_agent_capsule_creation_security_validation(self):
        """metadata dict is validated for security concerns."""
        # Forbidden keys should be rejected
        with pytest.raises(ValidationError, match="Forbidden keys"):
            AgentCapsuleCreation(
                session_id="s1",
                agent_id="a1",
                capsule_type="KNOWLEDGE",
                title="Test",
                content="Content",
                metadata={"__proto__": "malicious"},
            )

    def test_agent_capsule_creation_nested_security_validation(self):
        """Nested forbidden keys in metadata are detected."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            AgentCapsuleCreation(
                session_id="s1",
                agent_id="a1",
                capsule_type="KNOWLEDGE",
                title="Test",
                content="Content",
                metadata={"nested": {"__class__": "attack"}},
            )


# =============================================================================
# GatewayStats Tests
# =============================================================================


class TestGatewayStats:
    """Tests for GatewayStats model."""

    def test_valid_gateway_stats(self):
        """Valid GatewayStats data creates model."""
        stats = GatewayStats(
            active_sessions=10,
            total_sessions=100,
            queries_today=500,
            queries_this_hour=50,
            avg_response_time_ms=150.5,
            cache_hit_rate=0.65,
        )

        assert stats.active_sessions == 10
        assert stats.queries_today == 500
        assert stats.cache_hit_rate == 0.65

    def test_gateway_stats_defaults(self):
        """GatewayStats has sensible defaults."""
        stats = GatewayStats()

        assert stats.active_sessions == 0
        assert stats.total_sessions == 0
        assert stats.queries_today == 0
        assert stats.queries_this_hour == 0
        assert stats.avg_response_time_ms == 0.0
        assert stats.cache_hit_rate == 0.0
        assert stats.queries_by_type == {}
        assert stats.queries_by_trust == {}
        assert stats.capsules_read == 0
        assert stats.capsules_created == 0
        assert stats.cascades_triggered == 0
        assert stats.error_count == 0
        assert stats.error_rate == 0.0
        assert stats.calculated_at is not None

    def test_gateway_stats_with_distributions(self):
        """GatewayStats with distribution data."""
        stats = GatewayStats(
            active_sessions=15,
            total_sessions=200,
            queries_today=1000,
            queries_this_hour=100,
            avg_response_time_ms=200.0,
            cache_hit_rate=0.75,
            queries_by_type={
                "natural_language": 500,
                "semantic_search": 300,
                "graph_traverse": 150,
                "direct_cypher": 50,
            },
            queries_by_trust={
                "basic": 400,
                "verified": 350,
                "trusted": 200,
                "system": 50,
            },
            capsules_read=800,
            capsules_created=50,
            cascades_triggered=10,
            error_count=20,
            error_rate=0.02,
        )

        assert stats.queries_by_type["natural_language"] == 500
        assert stats.queries_by_trust["basic"] == 400
        assert stats.error_rate == 0.02


# =============================================================================
# StreamChunk Tests
# =============================================================================


class TestStreamChunk:
    """Tests for StreamChunk model."""

    def test_valid_stream_chunk_text(self):
        """Valid StreamChunk with text content creates model."""
        chunk = StreamChunk(
            chunk_id=1,
            query_id="query123",
            content_type="text",
            content="This is streaming text content",
        )

        assert chunk.chunk_id == 1
        assert chunk.query_id == "query123"
        assert chunk.content_type == "text"
        assert chunk.content == "This is streaming text content"

    def test_valid_stream_chunk_dict(self):
        """Valid StreamChunk with dict content creates model."""
        chunk = StreamChunk(
            chunk_id=2,
            query_id="query123",
            content_type="result",
            content={"id": "c1", "title": "Capsule 1"},
        )

        assert chunk.content_type == "result"
        assert isinstance(chunk.content, dict)
        assert chunk.content["id"] == "c1"

    def test_stream_chunk_defaults(self):
        """StreamChunk has sensible defaults."""
        chunk = StreamChunk(
            chunk_id=0,
            query_id="q1",
            content_type="text",
            content="Hello",
        )

        assert chunk.is_final is False
        assert chunk.progress_percent is None
        assert chunk.timestamp is not None

    def test_stream_chunk_final(self):
        """StreamChunk with final flag."""
        chunk = StreamChunk(
            chunk_id=10,
            query_id="q1",
            content_type="done",
            content="Completed",
            is_final=True,
            progress_percent=100,
        )

        assert chunk.is_final is True
        assert chunk.progress_percent == 100

    def test_stream_chunk_with_progress(self):
        """StreamChunk with progress tracking."""
        chunk = StreamChunk(
            chunk_id=5,
            query_id="q1",
            content_type="text",
            content="Processing...",
            progress_percent=50,
        )

        assert chunk.progress_percent == 50


# =============================================================================
# Integration Tests
# =============================================================================


class TestAgentGatewayIntegration:
    """Integration tests for agent gateway models."""

    def test_full_agent_session_lifecycle(self):
        """Test creating a complete agent session with all fields."""
        session = AgentSession(
            agent_id="agent-ml-001",
            agent_name="ML Analysis Agent",
            api_key_hash="$2b$12$securehashedkey",
            owner_user_id="user-admin-001",
            trust_level=AgentTrustLevel.TRUSTED,
            capabilities=[
                AgentCapability.READ_CAPSULES,
                AgentCapability.QUERY_GRAPH,
                AgentCapability.SEMANTIC_SEARCH,
                AgentCapability.CREATE_CAPSULES,
                AgentCapability.ACCESS_LINEAGE,
            ],
            allowed_capsule_types=["INSIGHT", "KNOWLEDGE", "CODE"],
            requests_per_minute=120,
            requests_per_hour=2000,
            max_tokens_per_request=8192,
            metadata={"model_version": "1.0", "department": "research"},
        )

        # Execute query
        query = AgentQuery(
            session_id=session.id,
            agent_id=session.agent_id,
            query_type=QueryType.NATURAL_LANGUAGE,
            query_text="Find all machine learning insights created this month",
            context={"topic": "machine_learning"},
            filters={"capsule_type": "INSIGHT", "min_trust": 60},
            response_format=ResponseFormat.JSON,
            max_results=20,
        )

        # Get result
        result = QueryResult(
            query_id=query.id,
            session_id=session.id,
            success=True,
            results=[{"id": "c1", "title": "ML Best Practices"}],
            total_count=1,
            generated_cypher="MATCH (c:Capsule) WHERE c.type='INSIGHT' RETURN c",
            answer="Found 1 insight about machine learning.",
            execution_time_ms=125,
            tokens_used=500,
        )

        # Record access
        access = CapsuleAccess(
            session_id=session.id,
            agent_id=session.agent_id,
            capsule_id="c1",
            access_type=AccessType.READ,
            query_id=query.id,
            capsule_trust_level=80,
            agent_trust_level=AgentTrustLevel.TRUSTED,
            access_granted=True,
        )

        assert session.id is not None
        assert query.session_id == session.id
        assert result.query_id == query.id
        assert access.query_id == query.id

    def test_agent_creates_capsule(self):
        """Test agent creating a capsule with full provenance."""
        creation = AgentCapsuleCreation(
            session_id="session-001",
            agent_id="agent-synthesis-001",
            capsule_type="INSIGHT",
            title="Synthesized Analysis of ML Trends",
            content="Based on analysis of 5 source capsules, the key trends are...",
            source_capsule_ids=["c1", "c2", "c3", "c4", "c5"],
            reasoning="Aggregated and synthesized insights from multiple sources to identify trends",
            tags=["machine-learning", "synthesis", "trends", "2024"],
            metadata={"synthesis_method": "semantic_clustering", "confidence": 0.92},
            requires_approval=True,
        )

        assert len(creation.source_capsule_ids) == 5
        assert creation.requires_approval is True
        assert creation.metadata["confidence"] == 0.92


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
