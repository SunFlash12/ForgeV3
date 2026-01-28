"""
Tests for Knowledge Query Compiler Service

Tests cover:
- CypherSecurityError exception
- CypherValidator security validation
- QueryCompiler intent extraction and Cypher generation
- KnowledgeQueryService query execution
- Security validation for injection attacks
- Fallback intent creation
- Query complexity estimation
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.query import (
    Aggregation,
    AggregationType,
    CompiledQuery,
    Constraint,
    EntityRef,
    GraphSchema,
    OrderBy,
    PathPattern,
    QueryComplexity,
    QueryIntent,
    QueryOperator,
    QueryResult,
    QueryResultRow,
    RelationshipRef,
    SortDirection,
    get_default_schema,
)
from forge.services.query_compiler import (
    CypherSecurityError,
    CypherValidator,
    KnowledgeQueryService,
    QueryCompiler,
)


class TestCypherSecurityError:
    """Tests for CypherSecurityError exception."""

    def test_exception_message(self):
        """Test exception has correct message."""
        error = CypherSecurityError("Injection detected")
        assert str(error) == "Injection detected"

    def test_exception_is_exception(self):
        """Test CypherSecurityError is an Exception."""
        assert issubclass(CypherSecurityError, Exception)


class TestCypherValidator:
    """Tests for CypherValidator security validation."""

    # =========================================================================
    # Empty Query Tests
    # =========================================================================

    def test_validate_empty_query(self):
        """Test validation rejects empty query."""
        with pytest.raises(CypherSecurityError, match="Empty query"):
            CypherValidator.validate("")

    def test_validate_whitespace_only_query(self):
        """Test validation rejects whitespace-only query."""
        with pytest.raises(CypherSecurityError, match="Empty query"):
            CypherValidator.validate("   \n\t  ")

    # =========================================================================
    # Forbidden Keyword Tests
    # =========================================================================

    def test_validate_delete_forbidden(self):
        """Test DELETE is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("MATCH (n) DELETE n")

    def test_validate_detach_delete_forbidden(self):
        """Test DETACH DELETE is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("MATCH (n) DETACH DELETE n")

    def test_validate_remove_forbidden(self):
        """Test REMOVE is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("MATCH (n) REMOVE n.property")

    def test_validate_drop_forbidden(self):
        """Test DROP is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("DROP INDEX my_index")

    def test_validate_create_index_forbidden(self):
        """Test CREATE INDEX is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CREATE INDEX ON :Person(name)")

    def test_validate_create_constraint_forbidden(self):
        """Test CREATE CONSTRAINT is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CREATE CONSTRAINT ON (p:Person) ASSERT p.id IS UNIQUE")

    def test_validate_apoc_calls_forbidden(self):
        """Test APOC procedure calls are forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CALL apoc.export.json.all('file.json', {})")

    def test_validate_db_calls_forbidden(self):
        """Test db.* calls are forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CALL db.indexes()")

    def test_validate_dbms_calls_forbidden(self):
        """Test dbms.* calls are forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CALL dbms.showCurrentUser()")

    def test_validate_apoc_load_json_forbidden(self):
        """Test apoc.load.json is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CALL apoc.load.json('http://evil.com/data.json')")

    def test_validate_apoc_cypher_run_forbidden(self):
        """Test apoc.cypher.run is forbidden."""
        with pytest.raises(CypherSecurityError, match="Forbidden"):
            CypherValidator.validate("CALL apoc.cypher.run('DELETE (n)', {})")

    # =========================================================================
    # Injection Pattern Tests
    # =========================================================================

    def test_validate_comment_injection_delete(self):
        """Test comment injection to hide DELETE."""
        with pytest.raises(CypherSecurityError, match="injection"):
            CypherValidator.validate("MATCH (n) // DELETE n \nRETURN n")

    def test_validate_multiline_comment_injection(self):
        """Test multiline comment injection."""
        with pytest.raises(CypherSecurityError, match="injection"):
            CypherValidator.validate("MATCH (n) /* DELETE n */ RETURN n")

    def test_validate_hex_escape_injection(self):
        """Test hex escape injection."""
        with pytest.raises(CypherSecurityError, match="injection"):
            CypherValidator.validate("MATCH (n {name: '\\x44ELETE'}) RETURN n")

    def test_validate_unicode_escape_injection(self):
        """Test unicode escape injection."""
        with pytest.raises(CypherSecurityError, match="injection"):
            CypherValidator.validate("MATCH (n {name: '\\u0044ELETE'}) RETURN n")

    def test_validate_multiple_statement_injection(self):
        """Test multiple statement injection via semicolon."""
        with pytest.raises(CypherSecurityError, match="injection|Multiple"):
            CypherValidator.validate("MATCH (n) RETURN n; DELETE (n)")

    def test_validate_string_concatenation_injection(self):
        """Test string concatenation injection."""
        with pytest.raises(CypherSecurityError, match="injection"):
            CypherValidator.validate("MATCH (n) WHERE n.name = 'x' + 'DELETE' RETURN n")

    # =========================================================================
    # Write Operation Tests
    # =========================================================================

    def test_validate_create_without_permission(self):
        """Test CREATE is blocked without allow_writes."""
        with pytest.raises(CypherSecurityError, match="Write operations not allowed"):
            CypherValidator.validate("CREATE (n:Person {name: 'John'})")

    def test_validate_merge_without_permission(self):
        """Test MERGE is blocked without allow_writes."""
        with pytest.raises(CypherSecurityError, match="Write operations not allowed"):
            CypherValidator.validate("MERGE (n:Person {name: 'John'})")

    def test_validate_set_without_permission(self):
        """Test SET is blocked without allow_writes."""
        with pytest.raises(CypherSecurityError, match="Write operations not allowed"):
            CypherValidator.validate("MATCH (n) SET n.updated = true RETURN n")

    def test_validate_create_with_permission(self):
        """Test CREATE is allowed with allow_writes=True."""
        # Should not raise
        CypherValidator.validate(
            "CREATE (n:Capsule {id: 'test'})",
            allow_writes=True,
            allowed_labels=frozenset({"Capsule"}),
        )

    def test_validate_create_wrong_label(self):
        """Test CREATE with wrong label is blocked."""
        with pytest.raises(CypherSecurityError, match="not allowed"):
            CypherValidator.validate(
                "CREATE (n:Admin {id: 'test'})",
                allow_writes=True,
                allowed_labels=frozenset({"Capsule", "User"}),
            )

    # =========================================================================
    # Multiple Statement Tests
    # =========================================================================

    def test_validate_multiple_statements_forbidden(self):
        """Test multiple statements are forbidden."""
        with pytest.raises(CypherSecurityError, match="Multiple statements"):
            CypherValidator.validate("MATCH (n) RETURN n; MATCH (m) RETURN m")

    def test_validate_semicolon_in_string_allowed(self):
        """Test semicolon in string is allowed."""
        # Should not raise
        CypherValidator.validate("MATCH (n {name: 'Hello; World'}) RETURN n")

    # =========================================================================
    # Unbalanced Quote Tests
    # =========================================================================

    def test_validate_unbalanced_single_quotes(self):
        """Test unbalanced single quotes detected."""
        with pytest.raises(CypherSecurityError, match="Unbalanced quotes"):
            CypherValidator.validate("MATCH (n {name: 'test}) RETURN n")

    def test_validate_unbalanced_double_quotes(self):
        """Test unbalanced double quotes detected."""
        with pytest.raises(CypherSecurityError, match="Unbalanced quotes"):
            CypherValidator.validate('MATCH (n {name: "test}) RETURN n')

    # =========================================================================
    # Valid Query Tests
    # =========================================================================

    def test_validate_simple_read_query(self):
        """Test simple read query passes validation."""
        CypherValidator.validate("MATCH (n:Capsule) RETURN n")

    def test_validate_query_with_where(self):
        """Test query with WHERE passes validation."""
        CypherValidator.validate("MATCH (n:Capsule) WHERE n.trust_level > 50 RETURN n")

    def test_validate_query_with_parameters(self):
        """Test query with parameters passes validation."""
        CypherValidator.validate("MATCH (n:Capsule {id: $id}) RETURN n")

    def test_validate_query_with_aggregation(self):
        """Test query with aggregation passes validation."""
        CypherValidator.validate("MATCH (n:Capsule) RETURN count(n)")

    def test_validate_query_with_relationship(self):
        """Test query with relationship passes validation."""
        CypherValidator.validate(
            "MATCH (c:Capsule)-[:DERIVED_FROM]->(parent:Capsule) RETURN c, parent"
        )

    def test_validate_query_with_variable_length_path(self):
        """Test query with variable length path passes validation."""
        CypherValidator.validate(
            "MATCH path = (c:Capsule)-[:DERIVED_FROM*1..5]->(root) RETURN path"
        )

    # =========================================================================
    # Parameter Validation Tests
    # =========================================================================

    def test_validate_parameters_valid(self):
        """Test valid parameters pass validation."""
        CypherValidator.validate_parameters({
            "id": "capsule-123",
            "trust_level": 60,
            "limit": 10,
        })

    def test_validate_parameters_invalid_key(self):
        """Test invalid parameter key is rejected."""
        with pytest.raises(CypherSecurityError, match="Invalid parameter name"):
            CypherValidator.validate_parameters({
                "123invalid": "value",
            })

    def test_validate_parameters_injection_in_value(self):
        """Test injection attempt in parameter value is rejected."""
        with pytest.raises(CypherSecurityError, match="Suspicious content"):
            CypherValidator.validate_parameters({
                "name": "test } ) DELETE",
            })

    def test_validate_parameters_procedure_call_in_value(self):
        """Test procedure call in parameter value is rejected."""
        with pytest.raises(CypherSecurityError, match="Suspicious content"):
            CypherValidator.validate_parameters({
                "query": "CALL db.indexes()",
            })

    # =========================================================================
    # is_read_only Tests
    # =========================================================================

    def test_is_read_only_true(self):
        """Test is_read_only returns True for read queries."""
        assert CypherValidator.is_read_only("MATCH (n) RETURN n") is True

    def test_is_read_only_false_create(self):
        """Test is_read_only returns False for CREATE."""
        assert CypherValidator.is_read_only("CREATE (n:Test)") is False

    def test_is_read_only_false_merge(self):
        """Test is_read_only returns False for MERGE."""
        assert CypherValidator.is_read_only("MERGE (n:Test)") is False

    def test_is_read_only_false_set(self):
        """Test is_read_only returns False for SET."""
        assert CypherValidator.is_read_only("MATCH (n) SET n.x = 1") is False

    def test_is_read_only_false_delete(self):
        """Test is_read_only returns False for DELETE."""
        assert CypherValidator.is_read_only("MATCH (n) DELETE n") is False


class TestQueryCompiler:
    """Tests for QueryCompiler."""

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        service = AsyncMock()
        service.complete = AsyncMock()
        return service

    @pytest.fixture
    def compiler(self, mock_llm_service):
        """Create a QueryCompiler with mock LLM."""
        return QueryCompiler(mock_llm_service)

    # =========================================================================
    # Schema Tests
    # =========================================================================

    def test_compiler_uses_default_schema(self, mock_llm_service):
        """Test compiler uses default schema if none provided."""
        compiler = QueryCompiler(mock_llm_service)
        assert compiler.schema is not None
        assert len(compiler.schema.nodes) > 0

    def test_compiler_uses_custom_schema(self, mock_llm_service):
        """Test compiler uses custom schema when provided."""
        custom_schema = GraphSchema(nodes=[], relationships=[])
        compiler = QueryCompiler(mock_llm_service, schema=custom_schema)
        assert compiler.schema is custom_schema

    # =========================================================================
    # JSON Response Parsing Tests
    # =========================================================================

    def test_parse_json_response_plain(self, compiler):
        """Test parsing plain JSON response."""
        content = '{"entities": [], "constraints": [], "limit": 10}'
        result = compiler._parse_json_response(content)
        assert result["limit"] == 10

    def test_parse_json_response_with_markdown(self, compiler):
        """Test parsing JSON with markdown code blocks."""
        content = '```json\n{"entities": [], "limit": 5}\n```'
        result = compiler._parse_json_response(content)
        assert result["limit"] == 5

    def test_parse_json_response_extract_from_text(self, compiler):
        """Test extracting JSON from surrounding text."""
        content = 'Here is the result: {"entities": [], "limit": 20} Done.'
        result = compiler._parse_json_response(content)
        assert result["limit"] == 20

    def test_parse_json_response_invalid(self, compiler):
        """Test parsing invalid JSON raises error."""
        content = 'This is not JSON at all'
        with pytest.raises(ValueError, match="Could not parse JSON"):
            compiler._parse_json_response(content)

    # =========================================================================
    # Query Intent Conversion Tests
    # =========================================================================

    def test_to_query_intent_entities(self, compiler):
        """Test converting entities to QueryIntent."""
        data = {
            "entities": [
                {"alias": "c", "label": "Capsule", "properties": {"type": "KNOWLEDGE"}}
            ],
            "constraints": [],
            "return_fields": ["c.id"],
        }

        intent = compiler._to_query_intent(data)

        assert len(intent.entities) == 1
        assert intent.entities[0].alias == "c"
        assert intent.entities[0].label == "Capsule"
        assert intent.entities[0].properties == {"type": "KNOWLEDGE"}

    def test_to_query_intent_paths(self, compiler):
        """Test converting paths to QueryIntent."""
        data = {
            "entities": [],
            "paths": [
                {
                    "source": {"alias": "c", "label": "Capsule"},
                    "relationship": {
                        "type": "DERIVED_FROM",
                        "direction": "out",
                        "min_hops": 1,
                        "max_hops": 5,
                    },
                    "target": {"alias": "parent", "label": "Capsule"},
                }
            ],
            "constraints": [],
        }

        intent = compiler._to_query_intent(data)

        assert len(intent.paths) == 1
        assert intent.paths[0].relationship.type == "DERIVED_FROM"
        assert intent.paths[0].relationship.max_hops == 5

    def test_to_query_intent_constraints(self, compiler):
        """Test converting constraints to QueryIntent."""
        data = {
            "entities": [],
            "constraints": [
                {"field": "c.trust_level", "operator": ">=", "value": 60},
                {"field": "c.content", "operator": "CONTAINS", "value": "AI"},
            ],
        }

        intent = compiler._to_query_intent(data)

        assert len(intent.constraints) == 2
        assert intent.constraints[0].operator == QueryOperator.GREATER_EQUAL
        assert intent.constraints[1].operator == QueryOperator.CONTAINS

    def test_to_query_intent_aggregations(self, compiler):
        """Test converting aggregations to QueryIntent."""
        data = {
            "entities": [],
            "constraints": [],
            "aggregations": [
                {"function": "count", "field": "c", "alias": "total"},
            ],
            "is_count_query": True,
        }

        intent = compiler._to_query_intent(data)

        assert len(intent.aggregations) == 1
        assert intent.aggregations[0].function == AggregationType.COUNT
        assert intent.is_count_query is True
        assert intent.is_aggregation_query is True

    def test_to_query_intent_order_by(self, compiler):
        """Test converting order_by to QueryIntent."""
        data = {
            "entities": [],
            "constraints": [],
            "order_by": [
                {"field": "c.created_at", "direction": "DESC"},
            ],
        }

        intent = compiler._to_query_intent(data)

        assert len(intent.order_by) == 1
        assert intent.order_by[0].field == "c.created_at"
        assert intent.order_by[0].direction == SortDirection.DESC

    # =========================================================================
    # Fallback Intent Tests
    # =========================================================================

    def test_create_fallback_intent_who_created(self, compiler):
        """Test fallback intent for 'who created' question."""
        intent = compiler._create_fallback_intent("Who created the AI capsule?")

        assert len(intent.return_fields) >= 1
        assert "owner_id" in str(intent.return_fields)

    def test_create_fallback_intent_count(self, compiler):
        """Test fallback intent for count question."""
        intent = compiler._create_fallback_intent("How many capsules exist?")

        assert intent.is_count_query is True
        assert len(intent.aggregations) == 1
        assert intent.aggregations[0].function == AggregationType.COUNT

    def test_create_fallback_intent_search(self, compiler):
        """Test fallback intent for search question."""
        intent = compiler._create_fallback_intent("Find capsules about machine learning")

        assert len(intent.constraints) == 1
        assert intent.constraints[0].operator == QueryOperator.CONTAINS

    # =========================================================================
    # Extract Topic Tests
    # =========================================================================

    def test_extract_topic_removes_stopwords(self, compiler):
        """Test topic extraction removes stopwords."""
        topic = compiler._extract_topic("What is the best AI framework?")

        assert "what" not in topic
        assert "is" not in topic
        assert "the" not in topic
        assert "best" in topic or "ai" in topic or "framework" in topic

    def test_extract_topic_limits_words(self, compiler):
        """Test topic extraction limits to 5 words."""
        topic = compiler._extract_topic(
            "What is the most advanced artificial intelligence machine learning deep neural network?"
        )

        words = topic.split()
        assert len(words) <= 5

    # =========================================================================
    # Cypher Generation Tests
    # =========================================================================

    def test_generate_cypher_simple_entity(self, compiler):
        """Test generating Cypher for simple entity query."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            return_fields=["c.id", "c.title"],
            limit=10,
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=60)

        assert "MATCH (c:Capsule)" in cypher
        assert "RETURN c.id, c.title" in cypher
        assert "LIMIT $limit" in cypher
        assert params["limit"] == 10

    def test_generate_cypher_with_properties(self, compiler):
        """Test generating Cypher with entity properties."""
        intent = QueryIntent(
            entities=[
                EntityRef(alias="c", label="Capsule", properties={"type": "KNOWLEDGE"})
            ],
            return_fields=["c.id"],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=60)

        assert "type: $p0" in cypher
        assert params["p0"] == "KNOWLEDGE"

    def test_generate_cypher_with_constraints(self, compiler):
        """Test generating Cypher with WHERE constraints."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            constraints=[
                Constraint(field="c.trust_level", operator=QueryOperator.GREATER_EQUAL, value=60),
            ],
            return_fields=["c.id"],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=100)

        assert "WHERE" in cypher
        assert "c.trust_level >=" in cypher

    def test_generate_cypher_trust_filter(self, compiler):
        """Test trust filter is added for non-admin users."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            return_fields=["c.id"],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=60)

        assert "c.trust_level <= $user_trust_level" in cypher
        assert params["user_trust_level"] == 60

    def test_generate_cypher_no_trust_filter_for_admin(self, compiler):
        """Test no trust filter for admin users."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            return_fields=["c.id"],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=100)

        assert "user_trust_level" not in params

    def test_generate_cypher_with_path(self, compiler):
        """Test generating Cypher with path pattern."""
        intent = QueryIntent(
            paths=[
                PathPattern(
                    source=EntityRef(alias="c", label="Capsule"),
                    relationship=RelationshipRef(
                        type="DERIVED_FROM",
                        direction="out",
                        min_hops=1,
                        max_hops=3,
                    ),
                    target=EntityRef(alias="parent", label="Capsule"),
                )
            ],
            return_fields=["c.id", "parent.id"],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=100)

        assert "DERIVED_FROM" in cypher
        assert "*1..3" in cypher
        assert "->" in cypher

    def test_generate_cypher_with_aggregation(self, compiler):
        """Test generating Cypher with aggregation."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            aggregations=[
                Aggregation(function=AggregationType.COUNT, field="c", alias="total")
            ],
            is_count_query=True,
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=100)

        assert "count(c) AS total" in cypher

    def test_generate_cypher_with_order_by(self, compiler):
        """Test generating Cypher with ORDER BY."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            return_fields=["c.id"],
            order_by=[OrderBy(field="c.created_at", direction=SortDirection.DESC)],
        )

        cypher, params = compiler._generate_cypher(intent, user_trust=100)

        assert "ORDER BY c.created_at DESC" in cypher

    # =========================================================================
    # Complexity Estimation Tests
    # =========================================================================

    def test_estimate_complexity_simple(self, compiler):
        """Test complexity estimation for simple query."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            is_count_query=True,
        )

        complexity = compiler._estimate_complexity(intent)
        assert complexity == QueryComplexity.SIMPLE

    def test_estimate_complexity_moderate(self, compiler):
        """Test complexity estimation for moderate query."""
        intent = QueryIntent(
            entities=[
                EntityRef(alias="c", label="Capsule"),
                EntityRef(alias="u", label="User"),
                EntityRef(alias="p", label="Proposal"),
            ],
        )

        complexity = compiler._estimate_complexity(intent)
        assert complexity == QueryComplexity.MODERATE

    def test_estimate_complexity_complex_path(self, compiler):
        """Test complexity estimation for path query."""
        intent = QueryIntent(
            paths=[
                PathPattern(
                    source=EntityRef(alias="c", label="Capsule"),
                    relationship=RelationshipRef(type="DERIVED_FROM", max_hops=3),
                    target=EntityRef(alias="p", label="Capsule"),
                )
            ],
        )

        complexity = compiler._estimate_complexity(intent)
        assert complexity == QueryComplexity.COMPLEX

    def test_estimate_complexity_expensive(self, compiler):
        """Test complexity estimation for expensive query."""
        intent = QueryIntent(
            paths=[
                PathPattern(
                    source=EntityRef(alias="c", label="Capsule"),
                    relationship=RelationshipRef(type="DERIVED_FROM", max_hops=10),
                    target=EntityRef(alias="p", label="Capsule"),
                )
            ],
        )

        complexity = compiler._estimate_complexity(intent)
        assert complexity == QueryComplexity.EXPENSIVE

    # =========================================================================
    # Explanation Generation Tests
    # =========================================================================

    def test_generate_explanation_find(self, compiler):
        """Test explanation generation for find query."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
        )

        explanation = compiler._generate_explanation(intent)
        assert "Find" in explanation
        assert "Capsule" in explanation

    def test_generate_explanation_count(self, compiler):
        """Test explanation generation for count query."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            is_count_query=True,
        )

        explanation = compiler._generate_explanation(intent)
        assert "Count" in explanation

    def test_generate_explanation_with_path(self, compiler):
        """Test explanation with relationship."""
        intent = QueryIntent(
            paths=[
                PathPattern(
                    source=EntityRef(alias="c", label="Capsule"),
                    relationship=RelationshipRef(type="DERIVED_FROM", max_hops=5),
                    target=EntityRef(alias="p", label="Capsule"),
                )
            ],
        )

        explanation = compiler._generate_explanation(intent)
        assert "DERIVED_FROM" in explanation
        assert "5 hops" in explanation

    # =========================================================================
    # Compile Integration Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_compile_success(self, compiler, mock_llm_service):
        """Test successful query compilation."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id", "c.title"],
                "limit": 10,
            })
        )

        result = await compiler.compile("Find all capsules", user_trust=60)

        assert isinstance(result, CompiledQuery)
        assert "MATCH" in result.cypher
        assert result.trust_filtered is True
        assert result.read_only is True

    @pytest.mark.asyncio
    async def test_compile_with_fallback(self, compiler, mock_llm_service):
        """Test compilation falls back on LLM error."""
        mock_llm_service.complete.side_effect = RuntimeError("LLM unavailable")

        with patch.object(compiler, '_create_fallback_intent') as mock_fallback:
            mock_fallback.return_value = QueryIntent(
                entities=[EntityRef(alias="c", label="Capsule")],
                return_fields=["c.id"],
            )

            result = await compiler.compile("Find capsules", user_trust=60)

            assert isinstance(result, CompiledQuery)
            mock_fallback.assert_called_once()


class TestKnowledgeQueryService:
    """Tests for KnowledgeQueryService."""

    @pytest.fixture
    def mock_db_client(self):
        """Create a mock Neo4j client."""
        client = AsyncMock()
        client.execute = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        service = AsyncMock()
        service.complete = AsyncMock()
        return service

    @pytest.fixture
    def service(self, mock_db_client, mock_llm_service):
        """Create a KnowledgeQueryService with mocks."""
        return KnowledgeQueryService(
            db_client=mock_db_client,
            llm_service=mock_llm_service,
        )

    # =========================================================================
    # Query Execution Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_success(self, service, mock_db_client, mock_llm_service):
        """Test successful query execution."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
                "limit": 10,
            })
        )
        mock_db_client.execute.return_value = [
            {"c.id": "cap-1"},
            {"c.id": "cap-2"},
        ]

        result = await service.query("Find capsules", synthesize_answer=False)

        assert isinstance(result, QueryResult)
        assert len(result.rows) == 2
        assert result.total_count == 2
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_query_with_truncation(self, service, mock_db_client, mock_llm_service):
        """Test query with truncated results."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        # Return more than max_results
        mock_db_client.execute.return_value = [{"c.id": f"cap-{i}"} for i in range(150)]

        result = await service.query(
            "Find capsules",
            synthesize_answer=False,
            max_results=100,
        )

        assert result.total_count == 150
        assert len(result.rows) == 100
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_query_security_validation(self, service, mock_db_client, mock_llm_service):
        """Test query fails security validation."""
        # Mock LLM to return dangerous query
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [],
                "constraints": [],
            })
        )

        # Mock compiler to return a query that will fail validation
        with patch.object(
            service.compiler,
            'compile',
            return_value=CompiledQuery(
                cypher="MATCH (n) DELETE n",  # Dangerous!
                parameters={},
                explanation="Delete all nodes",
            ),
        ):
            result = await service.query("Dangerous query", synthesize_answer=False)

            # Should fail with security message
            assert "rejected" in result.answer.lower()
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_query_database_error(self, service, mock_db_client, mock_llm_service):
        """Test query handles database errors."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        mock_db_client.execute.side_effect = ConnectionError("Database unavailable")

        result = await service.query("Find capsules", synthesize_answer=False)

        assert "failed" in result.answer.lower()
        assert len(result.rows) == 0

    # =========================================================================
    # Answer Synthesis Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_with_synthesis(self, service, mock_db_client, mock_llm_service):
        """Test query with answer synthesis."""
        mock_llm_service.complete.side_effect = [
            MagicMock(content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id", "c.title"],
            })),
            MagicMock(content="There are 2 capsules about AI."),
        ]
        mock_db_client.execute.return_value = [
            {"c.id": "cap-1", "c.title": "AI Intro"},
            {"c.id": "cap-2", "c.title": "AI Advanced"},
        ]

        result = await service.query("Find AI capsules", synthesize_answer=True)

        assert result.answer is not None
        assert "capsules" in result.answer.lower()
        assert result.synthesis_time_ms > 0

    @pytest.mark.asyncio
    async def test_query_no_synthesis_for_empty_results(self, service, mock_db_client, mock_llm_service):
        """Test no synthesis when results are empty."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        mock_db_client.execute.return_value = []

        result = await service.query("Find nonexistent", synthesize_answer=True)

        assert result.answer is None
        # LLM complete should only be called once (for compilation)
        assert mock_llm_service.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_synthesize_answer_error_handling(self, service, mock_db_client, mock_llm_service):
        """Test synthesis handles errors gracefully."""
        mock_llm_service.complete.side_effect = [
            MagicMock(content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })),
            RuntimeError("Synthesis failed"),
        ]
        mock_db_client.execute.return_value = [{"c.id": "cap-1"}]

        result = await service.query("Find capsules", synthesize_answer=True)

        # Should return fallback message
        assert "1 results" in result.answer
        assert "synthesis failed" in result.answer.lower()

    # =========================================================================
    # Trust Level Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_query_respects_trust_level(self, service, mock_db_client, mock_llm_service):
        """Test query includes trust filtering."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        mock_db_client.execute.return_value = []

        await service.query("Find capsules", user_trust=50, synthesize_answer=False)

        # Verify trust level was passed to compiler
        call_args = mock_db_client.execute.call_args
        cypher = call_args[0][0]
        assert "trust_level" in cypher

    @pytest.mark.asyncio
    async def test_query_confidence_high_with_results(self, service, mock_db_client, mock_llm_service):
        """Test confidence is high when results found."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        mock_db_client.execute.return_value = [{"c.id": "cap-1"}]

        result = await service.query("Find capsules", synthesize_answer=False)

        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_query_confidence_low_without_results(self, service, mock_db_client, mock_llm_service):
        """Test confidence is lower when no results found."""
        mock_llm_service.complete.return_value = MagicMock(
            content=json.dumps({
                "entities": [{"alias": "c", "label": "Capsule"}],
                "constraints": [],
                "return_fields": ["c.id"],
            })
        )
        mock_db_client.execute.return_value = []

        result = await service.query("Find capsules", synthesize_answer=False)

        assert result.confidence == 0.5
