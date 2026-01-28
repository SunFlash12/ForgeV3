"""
Query Model Tests for Forge Cascade V2

Comprehensive tests for knowledge query models including:
- Query operator and aggregation enums
- Entity and relationship references
- Query intent parsing models
- Compiled query models
- Query execution result models
- Schema models
- Query request models
- Default schema generation
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.query import (
    Aggregation,
    AggregationType,
    CompiledQuery,
    Constraint,
    DirectCypherRequest,
    EntityRef,
    GraphSchema,
    NaturalLanguageQueryRequest,
    OrderBy,
    PathPattern,
    QueryComplexity,
    QueryError,
    QueryHistoryEntry,
    QueryIntent,
    QueryOperator,
    QueryResult,
    QueryResultRow,
    QuerySuggestion,
    QueryValidation,
    RelationshipRef,
    SchemaNodeLabel,
    SchemaProperty,
    SchemaRelationship,
    SortDirection,
    get_default_schema,
)

# =============================================================================
# QueryOperator Enum Tests
# =============================================================================


class TestQueryOperator:
    """Tests for QueryOperator enum."""

    def test_query_operator_values(self):
        """QueryOperator has expected values."""
        assert QueryOperator.EQUALS.value == "="
        assert QueryOperator.NOT_EQUALS.value == "<>"
        assert QueryOperator.GREATER_THAN.value == ">"
        assert QueryOperator.LESS_THAN.value == "<"
        assert QueryOperator.GREATER_EQUAL.value == ">="
        assert QueryOperator.LESS_EQUAL.value == "<="
        assert QueryOperator.CONTAINS.value == "CONTAINS"
        assert QueryOperator.STARTS_WITH.value == "STARTS WITH"
        assert QueryOperator.ENDS_WITH.value == "ENDS WITH"
        assert QueryOperator.REGEX.value == "=~"
        assert QueryOperator.IN.value == "IN"
        assert QueryOperator.NOT_IN.value == "NOT IN"
        assert QueryOperator.IS_NULL.value == "IS NULL"
        assert QueryOperator.IS_NOT_NULL.value == "IS NOT NULL"

    def test_query_operator_count(self):
        """QueryOperator has 14 members."""
        assert len(QueryOperator) == 14


# =============================================================================
# AggregationType Enum Tests
# =============================================================================


class TestAggregationType:
    """Tests for AggregationType enum."""

    def test_aggregation_type_values(self):
        """AggregationType has expected values."""
        assert AggregationType.COUNT.value == "count"
        assert AggregationType.SUM.value == "sum"
        assert AggregationType.AVG.value == "avg"
        assert AggregationType.MIN.value == "min"
        assert AggregationType.MAX.value == "max"
        assert AggregationType.COLLECT.value == "collect"
        assert AggregationType.COUNT_DISTINCT.value == "count_distinct"

    def test_aggregation_type_count(self):
        """AggregationType has 7 members."""
        assert len(AggregationType) == 7


# =============================================================================
# SortDirection Enum Tests
# =============================================================================


class TestSortDirection:
    """Tests for SortDirection enum."""

    def test_sort_direction_values(self):
        """SortDirection has expected values."""
        assert SortDirection.ASC.value == "ASC"
        assert SortDirection.DESC.value == "DESC"

    def test_sort_direction_count(self):
        """SortDirection has 2 members."""
        assert len(SortDirection) == 2


# =============================================================================
# QueryComplexity Enum Tests
# =============================================================================


class TestQueryComplexity:
    """Tests for QueryComplexity enum."""

    def test_query_complexity_values(self):
        """QueryComplexity has expected values."""
        assert QueryComplexity.SIMPLE.value == "simple"
        assert QueryComplexity.MODERATE.value == "moderate"
        assert QueryComplexity.COMPLEX.value == "complex"
        assert QueryComplexity.EXPENSIVE.value == "expensive"

    def test_query_complexity_count(self):
        """QueryComplexity has 4 members."""
        assert len(QueryComplexity) == 4


# =============================================================================
# EntityRef Tests
# =============================================================================


class TestEntityRef:
    """Tests for EntityRef model."""

    def test_valid_entity_ref(self):
        """Valid entity ref creates model."""
        entity = EntityRef(
            alias="c",
            label="Capsule",
            properties={"type": "KNOWLEDGE"},
        )
        assert entity.alias == "c"
        assert entity.label == "Capsule"
        assert entity.properties == {"type": "KNOWLEDGE"}

    def test_entity_ref_defaults(self):
        """EntityRef has sensible defaults."""
        entity = EntityRef(alias="u", label="User")
        assert entity.properties == {}
        assert entity.is_optional is False

    def test_entity_ref_optional(self):
        """EntityRef can be marked optional."""
        entity = EntityRef(
            alias="c",
            label="Capsule",
            is_optional=True,
        )
        assert entity.is_optional is True


# =============================================================================
# RelationshipRef Tests
# =============================================================================


class TestRelationshipRef:
    """Tests for RelationshipRef model."""

    def test_valid_relationship_ref(self):
        """Valid relationship ref creates model."""
        rel = RelationshipRef(
            alias="r",
            type="DERIVED_FROM",
            direction="out",
            min_hops=1,
            max_hops=5,
        )
        assert rel.alias == "r"
        assert rel.type == "DERIVED_FROM"
        assert rel.direction == "out"

    def test_relationship_ref_defaults(self):
        """RelationshipRef has sensible defaults."""
        rel = RelationshipRef()
        assert rel.alias is None
        assert rel.type is None
        assert rel.types is None
        assert rel.direction == "out"
        assert rel.min_hops == 1
        assert rel.max_hops == 1
        assert rel.properties == {}

    def test_relationship_ref_direction_pattern(self):
        """Direction must be in/out/both."""
        RelationshipRef(direction="in")
        RelationshipRef(direction="out")
        RelationshipRef(direction="both")

        with pytest.raises(ValidationError, match="String should match pattern"):
            RelationshipRef(direction="left")

    def test_relationship_ref_min_hops_bounds(self):
        """min_hops must be >= 0."""
        with pytest.raises(ValidationError):
            RelationshipRef(min_hops=-1)

    def test_relationship_ref_max_hops_bounds(self):
        """max_hops must be >= 1."""
        with pytest.raises(ValidationError):
            RelationshipRef(max_hops=0)

    def test_relationship_ref_multiple_types(self):
        """RelationshipRef can have multiple types."""
        rel = RelationshipRef(types=["DERIVED_FROM", "RELATED_TO"])
        assert rel.types == ["DERIVED_FROM", "RELATED_TO"]


# =============================================================================
# PathPattern Tests
# =============================================================================


class TestPathPattern:
    """Tests for PathPattern model."""

    def test_valid_path_pattern(self):
        """Valid path pattern creates model."""
        source = EntityRef(alias="c1", label="Capsule")
        rel = RelationshipRef(type="DERIVED_FROM")
        target = EntityRef(alias="c2", label="Capsule")

        path = PathPattern(source=source, relationship=rel, target=target)
        assert path.source.alias == "c1"
        assert path.target.alias == "c2"


# =============================================================================
# Constraint Tests
# =============================================================================


class TestConstraint:
    """Tests for Constraint model."""

    def test_valid_constraint(self):
        """Valid constraint creates model."""
        constraint = Constraint(
            field="c.trust_level",
            operator=QueryOperator.GREATER_EQUAL,
            value=60,
        )
        assert constraint.field == "c.trust_level"
        assert constraint.operator == QueryOperator.GREATER_EQUAL
        assert constraint.value == 60

    def test_constraint_defaults(self):
        """Constraint has sensible defaults."""
        constraint = Constraint(
            field="c.type",
            operator=QueryOperator.EQUALS,
            value="KNOWLEDGE",
        )
        assert constraint.is_parameter is False
        assert constraint.parameter_name is None

    def test_constraint_with_parameter(self):
        """Constraint can use parameter."""
        constraint = Constraint(
            field="c.owner_id",
            operator=QueryOperator.EQUALS,
            value="$userId",
            is_parameter=True,
            parameter_name="userId",
        )
        assert constraint.is_parameter is True
        assert constraint.parameter_name == "userId"


# =============================================================================
# Aggregation Tests
# =============================================================================


class TestAggregation:
    """Tests for Aggregation model."""

    def test_valid_aggregation(self):
        """Valid aggregation creates model."""
        agg = Aggregation(
            function=AggregationType.COUNT,
            field="c",
            alias="capsule_count",
        )
        assert agg.function == AggregationType.COUNT
        assert agg.alias == "capsule_count"

    def test_aggregation_defaults(self):
        """Aggregation has sensible defaults."""
        agg = Aggregation(
            function=AggregationType.AVG,
            field="c.trust_level",
            alias="avg_trust",
        )
        assert agg.distinct is False

    def test_aggregation_distinct(self):
        """Aggregation can be distinct."""
        agg = Aggregation(
            function=AggregationType.COUNT,
            field="c.owner_id",
            alias="unique_owners",
            distinct=True,
        )
        assert agg.distinct is True


# =============================================================================
# OrderBy Tests
# =============================================================================


class TestOrderBy:
    """Tests for OrderBy model."""

    def test_valid_order_by(self):
        """Valid order by creates model."""
        order = OrderBy(field="c.created_at", direction=SortDirection.DESC)
        assert order.field == "c.created_at"
        assert order.direction == SortDirection.DESC

    def test_order_by_default_direction(self):
        """Default direction is DESC."""
        order = OrderBy(field="c.trust_level")
        assert order.direction == SortDirection.DESC


# =============================================================================
# QueryIntent Tests
# =============================================================================


class TestQueryIntent:
    """Tests for QueryIntent model."""

    def test_valid_query_intent(self):
        """Valid query intent creates model."""
        intent = QueryIntent(
            entities=[EntityRef(alias="c", label="Capsule")],
            constraints=[
                Constraint(
                    field="c.type",
                    operator=QueryOperator.EQUALS,
                    value="KNOWLEDGE",
                )
            ],
            return_fields=["c.id", "c.title"],
            limit=10,
        )
        assert len(intent.entities) == 1
        assert len(intent.constraints) == 1
        assert intent.limit == 10

    def test_query_intent_defaults(self):
        """QueryIntent has sensible defaults."""
        intent = QueryIntent()
        assert intent.entities == []
        assert intent.paths == []
        assert intent.constraints == []
        assert intent.trust_filter is None
        assert intent.return_fields == []
        assert intent.aggregations == []
        assert intent.order_by == []
        assert intent.limit is None
        assert intent.skip is None
        assert intent.is_count_query is False
        assert intent.is_path_query is False
        assert intent.is_aggregation_query is False

    def test_query_intent_trust_filter_bounds(self):
        """Trust filter must be 0-100."""
        QueryIntent(trust_filter=0)
        QueryIntent(trust_filter=100)

        with pytest.raises(ValidationError):
            QueryIntent(trust_filter=-1)
        with pytest.raises(ValidationError):
            QueryIntent(trust_filter=101)

    def test_query_intent_limit_bounds(self):
        """Limit must be 1-100 (security fix)."""
        QueryIntent(limit=1)
        QueryIntent(limit=100)

        with pytest.raises(ValidationError):
            QueryIntent(limit=0)
        with pytest.raises(ValidationError):
            QueryIntent(limit=101)

    def test_query_intent_skip_bounds(self):
        """Skip must be >= 0."""
        QueryIntent(skip=0)
        QueryIntent(skip=1000)

        with pytest.raises(ValidationError):
            QueryIntent(skip=-1)


# =============================================================================
# CompiledQuery Tests
# =============================================================================


class TestCompiledQuery:
    """Tests for CompiledQuery model."""

    def test_valid_compiled_query(self):
        """Valid compiled query creates model."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c LIMIT 10",
            parameters={},
            explanation="Find all capsules",
        )
        assert "MATCH" in query.cypher
        assert query.explanation == "Find all capsules"

    def test_compiled_query_defaults(self):
        """CompiledQuery has sensible defaults."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        assert query.parameters == {}
        assert query.estimated_complexity == QueryComplexity.SIMPLE
        assert query.trust_filtered is False
        assert query.read_only is True

    def test_compiled_query_with_parameters(self):
        """CompiledQuery can have parameters."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule {type: $type}) RETURN c",
            parameters={"type": "KNOWLEDGE"},
            explanation="Find capsules by type",
        )
        assert query.parameters == {"type": "KNOWLEDGE"}


# =============================================================================
# QueryValidation Tests
# =============================================================================


class TestQueryValidation:
    """Tests for QueryValidation model."""

    def test_valid_query_validation(self):
        """Valid query validation creates model."""
        validation = QueryValidation(
            is_valid=True,
            errors=[],
            warnings=["Consider adding index"],
        )
        assert validation.is_valid is True
        assert len(validation.warnings) == 1

    def test_query_validation_defaults(self):
        """QueryValidation has sensible defaults."""
        validation = QueryValidation(is_valid=False)
        assert validation.errors == []
        assert validation.warnings == []
        assert validation.estimated_cost is None
        assert validation.may_timeout is False

    def test_query_validation_with_errors(self):
        """QueryValidation can have errors."""
        validation = QueryValidation(
            is_valid=False,
            errors=["Invalid syntax", "Unknown label"],
            may_timeout=True,
            estimated_cost=100.5,
        )
        assert len(validation.errors) == 2
        assert validation.may_timeout is True


# =============================================================================
# QueryResultRow Tests
# =============================================================================


class TestQueryResultRow:
    """Tests for QueryResultRow model."""

    def test_valid_query_result_row(self):
        """Valid result row creates model."""
        row = QueryResultRow(data={"id": "c123", "title": "Test"})
        assert row.data["id"] == "c123"

    def test_query_result_row_defaults(self):
        """QueryResultRow has empty data by default."""
        row = QueryResultRow()
        assert row.data == {}


# =============================================================================
# QueryResult Tests
# =============================================================================


class TestQueryResult:
    """Tests for QueryResult model."""

    def test_valid_query_result(self):
        """Valid query result creates model."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        result = QueryResult(
            query=query,
            original_question="Find all capsules",
            rows=[QueryResultRow(data={"id": "c1"})],
            total_count=1,
            execution_time_ms=15.5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert result.total_count == 1
        assert result.execution_time_ms == 15.5

    def test_query_result_defaults(self):
        """QueryResult has sensible defaults."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        result = QueryResult(
            query=query,
            original_question="Find capsules",
            total_count=0,
            execution_time_ms=10.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert result.rows == []
        assert result.truncated is False
        assert result.answer is None
        assert result.confidence == 1.0
        assert result.synthesis_time_ms == 0.0

    def test_query_result_auto_generates_id(self):
        """QueryResult auto-generates ID."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        result = QueryResult(
            query=query,
            original_question="Test",
            total_count=0,
            execution_time_ms=10.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert result.id is not None
        assert len(result.id) > 0

    def test_query_result_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        with pytest.raises(ValidationError):
            QueryResult(
                query=query,
                original_question="Test",
                total_count=0,
                execution_time_ms=10.0,
                confidence=1.5,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_query_result_total_count_bounds(self):
        """Total count must be >= 0."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        with pytest.raises(ValidationError):
            QueryResult(
                query=query,
                original_question="Test",
                total_count=-1,
                execution_time_ms=10.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_query_result_execution_time_bounds(self):
        """Execution time must be >= 0."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        with pytest.raises(ValidationError):
            QueryResult(
                query=query,
                original_question="Test",
                total_count=0,
                execution_time_ms=-1.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )


# =============================================================================
# QueryError Tests
# =============================================================================


class TestQueryError:
    """Tests for QueryError model."""

    def test_valid_query_error(self):
        """Valid query error creates model."""
        error = QueryError(
            error_type="syntax",
            message="Invalid Cypher syntax",
            details={"line": 1, "column": 5},
            suggestion="Check for missing parenthesis",
        )
        assert error.error_type == "syntax"
        assert error.message == "Invalid Cypher syntax"

    def test_query_error_defaults(self):
        """QueryError has sensible defaults."""
        error = QueryError(
            error_type="execution",
            message="Query timed out",
        )
        assert error.details == {}
        assert error.suggestion is None


# =============================================================================
# SchemaProperty Tests
# =============================================================================


class TestSchemaProperty:
    """Tests for SchemaProperty model."""

    def test_valid_schema_property(self):
        """Valid schema property creates model."""
        prop = SchemaProperty(
            name="trust_level",
            type="int",
            description="Trust score 0-100",
            example=60,
            indexed=True,
        )
        assert prop.name == "trust_level"
        assert prop.indexed is True

    def test_schema_property_defaults(self):
        """SchemaProperty has sensible defaults."""
        prop = SchemaProperty(name="id", type="string")
        assert prop.description is None
        assert prop.example is None
        assert prop.indexed is False


# =============================================================================
# SchemaNodeLabel Tests
# =============================================================================


class TestSchemaNodeLabel:
    """Tests for SchemaNodeLabel model."""

    def test_valid_schema_node_label(self):
        """Valid schema node label creates model."""
        node = SchemaNodeLabel(
            label="Capsule",
            description="Knowledge unit",
            properties=[
                SchemaProperty(name="id", type="string"),
                SchemaProperty(name="title", type="string"),
            ],
        )
        assert node.label == "Capsule"
        assert len(node.properties) == 2

    def test_schema_node_label_defaults(self):
        """SchemaNodeLabel has sensible defaults."""
        node = SchemaNodeLabel(label="User", description="User account")
        assert node.properties == []
        assert node.example_query is None


# =============================================================================
# SchemaRelationship Tests
# =============================================================================


class TestSchemaRelationship:
    """Tests for SchemaRelationship model."""

    def test_valid_schema_relationship(self):
        """Valid schema relationship creates model."""
        rel = SchemaRelationship(
            type="DERIVED_FROM",
            description="Capsule lineage",
            source_labels=["Capsule"],
            target_labels=["Capsule"],
        )
        assert rel.type == "DERIVED_FROM"
        assert rel.source_labels == ["Capsule"]

    def test_schema_relationship_defaults(self):
        """SchemaRelationship has sensible defaults."""
        rel = SchemaRelationship(
            type="OWNS",
            description="Ownership",
        )
        assert rel.source_labels == []
        assert rel.target_labels == []
        assert rel.properties == []
        assert rel.bidirectional is False


# =============================================================================
# GraphSchema Tests
# =============================================================================


class TestGraphSchema:
    """Tests for GraphSchema model."""

    def test_valid_graph_schema(self):
        """Valid graph schema creates model."""
        schema = GraphSchema(
            nodes=[
                SchemaNodeLabel(label="Capsule", description="Knowledge unit"),
                SchemaNodeLabel(label="User", description="User account"),
            ],
            relationships=[
                SchemaRelationship(
                    type="OWNS",
                    description="Ownership",
                    source_labels=["User"],
                    target_labels=["Capsule"],
                ),
            ],
        )
        assert len(schema.nodes) == 2
        assert len(schema.relationships) == 1

    def test_graph_schema_defaults(self):
        """GraphSchema has empty defaults."""
        schema = GraphSchema()
        assert schema.nodes == []
        assert schema.relationships == []

    def test_get_node_found(self):
        """get_node returns node when found."""
        schema = GraphSchema(
            nodes=[
                SchemaNodeLabel(label="Capsule", description="Knowledge unit"),
            ],
        )
        node = schema.get_node("Capsule")
        assert node is not None
        assert node.label == "Capsule"

    def test_get_node_not_found(self):
        """get_node returns None when not found."""
        schema = GraphSchema()
        assert schema.get_node("Unknown") is None

    def test_get_relationship_found(self):
        """get_relationship returns relationship when found."""
        schema = GraphSchema(
            relationships=[
                SchemaRelationship(type="OWNS", description="Ownership"),
            ],
        )
        rel = schema.get_relationship("OWNS")
        assert rel is not None
        assert rel.type == "OWNS"

    def test_get_relationship_not_found(self):
        """get_relationship returns None when not found."""
        schema = GraphSchema()
        assert schema.get_relationship("UNKNOWN") is None

    def test_to_context_string(self):
        """to_context_string generates readable output."""
        schema = GraphSchema(
            nodes=[
                SchemaNodeLabel(
                    label="Capsule",
                    description="Knowledge unit",
                    properties=[
                        SchemaProperty(name="id", type="string"),
                        SchemaProperty(name="title", type="string"),
                    ],
                ),
            ],
            relationships=[
                SchemaRelationship(
                    type="DERIVED_FROM",
                    description="Lineage",
                    source_labels=["Capsule"],
                    target_labels=["Capsule"],
                ),
            ],
        )
        context = schema.to_context_string()
        assert "Knowledge Graph Schema" in context
        assert "Capsule" in context
        assert "DERIVED_FROM" in context
        assert "id, title" in context


# =============================================================================
# NaturalLanguageQueryRequest Tests
# =============================================================================


class TestNaturalLanguageQueryRequest:
    """Tests for NaturalLanguageQueryRequest model."""

    def test_valid_nl_query_request(self):
        """Valid NL query request creates model."""
        request = NaturalLanguageQueryRequest(
            question="Find all capsules about Python",
            user_trust=80,
        )
        assert request.question == "Find all capsules about Python"
        assert request.user_trust == 80

    def test_nl_query_request_defaults(self):
        """NL query request has sensible defaults."""
        request = NaturalLanguageQueryRequest(question="Find capsules")
        assert request.user_trust == 60
        assert request.include_explanation is True
        assert request.include_cypher is False
        assert request.synthesize_answer is True
        assert request.max_results == 100

    def test_question_min_length(self):
        """Question must be at least 3 characters."""
        with pytest.raises(ValidationError, match="String should have at least 3"):
            NaturalLanguageQueryRequest(question="Hi")

    def test_question_max_length(self):
        """Question must be at most 1000 characters."""
        with pytest.raises(ValidationError):
            NaturalLanguageQueryRequest(question="Q" * 1001)

    def test_user_trust_bounds(self):
        """User trust must be 0-100."""
        NaturalLanguageQueryRequest(question="Find capsules", user_trust=0)
        NaturalLanguageQueryRequest(question="Find capsules", user_trust=100)

        with pytest.raises(ValidationError):
            NaturalLanguageQueryRequest(question="Find capsules", user_trust=-1)
        with pytest.raises(ValidationError):
            NaturalLanguageQueryRequest(question="Find capsules", user_trust=101)

    def test_max_results_bounds(self):
        """Max results must be 1-100 (security fix)."""
        NaturalLanguageQueryRequest(question="Find capsules", max_results=1)
        NaturalLanguageQueryRequest(question="Find capsules", max_results=100)

        with pytest.raises(ValidationError):
            NaturalLanguageQueryRequest(question="Find capsules", max_results=0)
        with pytest.raises(ValidationError):
            NaturalLanguageQueryRequest(question="Find capsules", max_results=101)


# =============================================================================
# DirectCypherRequest Tests
# =============================================================================


class TestDirectCypherRequest:
    """Tests for DirectCypherRequest model."""

    def test_valid_direct_cypher_request(self):
        """Valid direct Cypher request creates model."""
        request = DirectCypherRequest(
            cypher="MATCH (c:Capsule) RETURN c LIMIT 10",
            parameters={"limit": 10},
        )
        assert "MATCH" in request.cypher
        assert request.parameters == {"limit": 10}

    def test_direct_cypher_request_defaults(self):
        """Direct Cypher request has sensible defaults."""
        request = DirectCypherRequest(cypher="MATCH (c:Capsule) RETURN c")
        assert request.parameters == {}
        assert request.read_only is True
        assert request.timeout_ms == 30000

    def test_cypher_min_length(self):
        """Cypher must be at least 5 characters."""
        with pytest.raises(ValidationError, match="String should have at least 5"):
            DirectCypherRequest(cypher="MATC")

    def test_cypher_max_length(self):
        """Cypher must be at most 5000 characters."""
        with pytest.raises(ValidationError):
            DirectCypherRequest(cypher="M" * 5001)

    def test_timeout_bounds(self):
        """Timeout must be 1000-120000ms (security fix)."""
        DirectCypherRequest(
            cypher="MATCH (c:Capsule) RETURN c",
            timeout_ms=1000,
        )
        DirectCypherRequest(
            cypher="MATCH (c:Capsule) RETURN c",
            timeout_ms=120000,
        )

        with pytest.raises(ValidationError):
            DirectCypherRequest(
                cypher="MATCH (c:Capsule) RETURN c",
                timeout_ms=999,
            )
        with pytest.raises(ValidationError):
            DirectCypherRequest(
                cypher="MATCH (c:Capsule) RETURN c",
                timeout_ms=120001,
            )


# =============================================================================
# QueryHistoryEntry Tests
# =============================================================================


class TestQueryHistoryEntry:
    """Tests for QueryHistoryEntry model."""

    def test_valid_query_history_entry(self):
        """Valid query history entry creates model."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        entry = QueryHistoryEntry(
            user_id="user-123",
            original_question="Find all capsules",
            compiled_query=query,
            result_count=10,
            execution_time_ms=15.5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert entry.user_id == "user-123"
        assert entry.result_count == 10

    def test_query_history_entry_defaults(self):
        """QueryHistoryEntry has sensible defaults."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        entry = QueryHistoryEntry(
            user_id="user-123",
            original_question="Find capsules",
            compiled_query=query,
            result_count=0,
            execution_time_ms=10.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert entry.was_successful is True
        assert entry.error is None
        assert entry.user_feedback is None
        assert entry.feedback_score is None

    def test_query_history_entry_feedback_score_bounds(self):
        """Feedback score must be 1-5."""
        query = CompiledQuery(
            cypher="MATCH (c:Capsule) RETURN c",
            explanation="Find capsules",
        )
        QueryHistoryEntry(
            user_id="user-123",
            original_question="Find capsules",
            compiled_query=query,
            result_count=0,
            execution_time_ms=10.0,
            feedback_score=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        QueryHistoryEntry(
            user_id="user-123",
            original_question="Find capsules",
            compiled_query=query,
            result_count=0,
            execution_time_ms=10.0,
            feedback_score=5,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        with pytest.raises(ValidationError):
            QueryHistoryEntry(
                user_id="user-123",
                original_question="Find capsules",
                compiled_query=query,
                result_count=0,
                execution_time_ms=10.0,
                feedback_score=0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        with pytest.raises(ValidationError):
            QueryHistoryEntry(
                user_id="user-123",
                original_question="Find capsules",
                compiled_query=query,
                result_count=0,
                execution_time_ms=10.0,
                feedback_score=6,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )


# =============================================================================
# QuerySuggestion Tests
# =============================================================================


class TestQuerySuggestion:
    """Tests for QuerySuggestion model."""

    def test_valid_query_suggestion(self):
        """Valid query suggestion creates model."""
        suggestion = QuerySuggestion(
            question="Find most trusted capsules",
            description="Returns capsules with highest trust levels",
            category="trust",
            popularity=100,
        )
        assert suggestion.question == "Find most trusted capsules"
        assert suggestion.popularity == 100

    def test_query_suggestion_defaults(self):
        """QuerySuggestion has sensible defaults."""
        suggestion = QuerySuggestion(
            question="Find capsules",
            description="Find all capsules",
        )
        assert suggestion.category is None
        assert suggestion.popularity == 0

    def test_query_suggestion_popularity_bounds(self):
        """Popularity must be >= 0."""
        QuerySuggestion(
            question="Test",
            description="Test",
            popularity=0,
        )
        with pytest.raises(ValidationError):
            QuerySuggestion(
                question="Test",
                description="Test",
                popularity=-1,
            )


# =============================================================================
# get_default_schema Tests
# =============================================================================


class TestGetDefaultSchema:
    """Tests for get_default_schema function."""

    def test_returns_graph_schema(self):
        """get_default_schema returns a GraphSchema."""
        schema = get_default_schema()
        assert isinstance(schema, GraphSchema)

    def test_has_capsule_node(self):
        """Default schema has Capsule node."""
        schema = get_default_schema()
        capsule = schema.get_node("Capsule")
        assert capsule is not None
        assert "id" in [p.name for p in capsule.properties]
        assert "trust_level" in [p.name for p in capsule.properties]

    def test_has_user_node(self):
        """Default schema has User node."""
        schema = get_default_schema()
        user = schema.get_node("User")
        assert user is not None

    def test_has_proposal_node(self):
        """Default schema has Proposal node."""
        schema = get_default_schema()
        proposal = schema.get_node("Proposal")
        assert proposal is not None

    def test_has_vote_node(self):
        """Default schema has Vote node."""
        schema = get_default_schema()
        vote = schema.get_node("Vote")
        assert vote is not None

    def test_has_derived_from_relationship(self):
        """Default schema has DERIVED_FROM relationship."""
        schema = get_default_schema()
        rel = schema.get_relationship("DERIVED_FROM")
        assert rel is not None
        assert "Capsule" in rel.source_labels

    def test_has_related_to_relationship(self):
        """Default schema has RELATED_TO relationship."""
        schema = get_default_schema()
        rel = schema.get_relationship("RELATED_TO")
        assert rel is not None
        assert rel.bidirectional is True

    def test_has_owns_relationship(self):
        """Default schema has OWNS relationship."""
        schema = get_default_schema()
        rel = schema.get_relationship("OWNS")
        assert rel is not None
        assert "User" in rel.source_labels
        assert "Capsule" in rel.target_labels


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
