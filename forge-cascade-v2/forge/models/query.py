"""
Knowledge Query Models

Data structures for the natural language to Cypher query compiler,
enabling users to query the knowledge graph with plain English.
"""

from enum import Enum
from typing import Any

from pydantic import Field

from forge.models.base import ForgeModel, TimestampMixin, generate_id


class QueryOperator(str, Enum):
    """Comparison operators for constraints."""

    EQUALS = "="
    NOT_EQUALS = "<>"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CONTAINS = "CONTAINS"
    STARTS_WITH = "STARTS WITH"
    ENDS_WITH = "ENDS WITH"
    REGEX = "=~"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class AggregationType(str, Enum):
    """Aggregation functions."""

    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COLLECT = "collect"
    COUNT_DISTINCT = "count_distinct"


class SortDirection(str, Enum):
    """Sort order."""

    ASC = "ASC"
    DESC = "DESC"


class QueryComplexity(str, Enum):
    """Estimated query complexity."""

    SIMPLE = "simple"          # Single node lookup
    MODERATE = "moderate"      # Single relationship traversal
    COMPLEX = "complex"        # Multi-hop traversal
    EXPENSIVE = "expensive"    # Graph-wide operations


# ═══════════════════════════════════════════════════════════════
# QUERY INTENT PARSING
# ═══════════════════════════════════════════════════════════════


class EntityRef(ForgeModel):
    """
    Reference to a node in the query.

    Represents a node pattern like (c:Capsule {type: 'KNOWLEDGE'}).
    """

    alias: str = Field(description="Variable name in query (e.g., 'c', 'u')")
    label: str = Field(description="Node label (e.g., 'Capsule', 'User')")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Property filters (e.g., {type: 'KNOWLEDGE'})",
    )
    is_optional: bool = Field(
        default=False,
        description="Whether this node is optional (OPTIONAL MATCH)",
    )


class RelationshipRef(ForgeModel):
    """
    Reference to a relationship in the query.

    Represents a relationship pattern like -[:DERIVED_FROM*1..5]->.
    """

    alias: str | None = Field(default=None, description="Optional variable name")
    type: str | None = Field(
        default=None,
        description="Relationship type (None = any)",
    )
    types: list[str] | None = Field(
        default=None,
        description="Multiple relationship types (OR)",
    )
    direction: str = Field(
        default="out",
        pattern="^(in|out|both)$",
    )
    min_hops: int = Field(default=1, ge=0)
    max_hops: int | None = Field(default=1, ge=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class PathPattern(ForgeModel):
    """A path pattern connecting entities through relationships."""

    source: EntityRef
    relationship: RelationshipRef
    target: EntityRef


class Constraint(ForgeModel):
    """
    A WHERE clause constraint.

    Represents conditions like "c.trust_level >= 60".
    """

    field: str = Field(description="Property path (e.g., 'c.trust_level')")
    operator: QueryOperator
    value: Any = Field(description="Comparison value")
    is_parameter: bool = Field(
        default=False,
        description="Whether value is a query parameter",
    )
    parameter_name: str | None = None


class Aggregation(ForgeModel):
    """An aggregation in the RETURN clause."""

    function: AggregationType
    field: str = Field(description="Field to aggregate")
    alias: str = Field(description="Result alias")
    distinct: bool = Field(default=False)


class OrderBy(ForgeModel):
    """Ordering specification."""

    field: str
    direction: SortDirection = SortDirection.DESC


class QueryIntent(ForgeModel):
    """
    Parsed intent from a natural language question.

    This is the intermediate representation between natural language
    and Cypher, capturing what the user is trying to find.
    """

    # What to find
    entities: list[EntityRef] = Field(
        default_factory=list,
        description="Nodes to match",
    )
    paths: list[PathPattern] = Field(
        default_factory=list,
        description="Relationship patterns to traverse",
    )

    # How to filter
    constraints: list[Constraint] = Field(
        default_factory=list,
        description="WHERE conditions",
    )
    trust_filter: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum trust level filter",
    )

    # What to return
    return_fields: list[str] = Field(
        default_factory=list,
        description="Fields to return",
    )
    aggregations: list[Aggregation] = Field(
        default_factory=list,
        description="Aggregation functions",
    )

    # How to order/limit
    order_by: list[OrderBy] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=1000)
    skip: int | None = Field(default=None, ge=0)

    # Query classification
    is_count_query: bool = Field(default=False)
    is_path_query: bool = Field(default=False)
    is_aggregation_query: bool = Field(default=False)


# ═══════════════════════════════════════════════════════════════
# COMPILED QUERIES
# ═══════════════════════════════════════════════════════════════


class CompiledQuery(ForgeModel):
    """
    A fully compiled Cypher query ready for execution.

    Generated from QueryIntent by the query compiler.
    """

    cypher: str = Field(description="The Cypher query string")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters",
    )
    explanation: str = Field(
        description="Human-readable explanation of what the query does",
    )

    # Metadata
    estimated_complexity: QueryComplexity = QueryComplexity.SIMPLE
    trust_filtered: bool = Field(
        default=False,
        description="Whether trust filtering was applied",
    )
    read_only: bool = Field(
        default=True,
        description="Whether this is a read-only query",
    )


class QueryValidation(ForgeModel):
    """Validation result for a compiled query."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    estimated_cost: float | None = None
    may_timeout: bool = False


# ═══════════════════════════════════════════════════════════════
# QUERY EXECUTION
# ═══════════════════════════════════════════════════════════════


class QueryResultRow(ForgeModel):
    """A single row from query results."""

    data: dict[str, Any] = Field(default_factory=dict)


class QueryResult(ForgeModel, TimestampMixin):
    """
    Complete result from executing a knowledge query.

    Includes both raw results and synthesized answer.
    """

    id: str = Field(default_factory=generate_id)
    query: CompiledQuery
    original_question: str

    # Results
    rows: list[QueryResultRow] = Field(default_factory=list)
    total_count: int = Field(ge=0)
    truncated: bool = Field(
        default=False,
        description="Whether results were truncated",
    )

    # Synthesized answer
    answer: str | None = Field(
        default=None,
        description="LLM-synthesized human-readable answer",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the answer",
    )

    # Performance
    execution_time_ms: float = Field(ge=0.0)
    synthesis_time_ms: float = Field(default=0.0, ge=0.0)


class QueryError(ForgeModel):
    """Error from query compilation or execution."""

    error_type: str = Field(description="Error category")
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    suggestion: str | None = Field(
        default=None,
        description="Suggested fix or alternative",
    )


# ═══════════════════════════════════════════════════════════════
# SCHEMA CONTEXT
# ═══════════════════════════════════════════════════════════════


class SchemaProperty(ForgeModel):
    """A property in the schema."""

    name: str
    type: str  # string, int, float, datetime, list, etc.
    description: str | None = None
    example: Any | None = None
    indexed: bool = False


class SchemaNodeLabel(ForgeModel):
    """A node label in the schema."""

    label: str
    description: str
    properties: list[SchemaProperty] = Field(default_factory=list)
    example_query: str | None = None


class SchemaRelationship(ForgeModel):
    """A relationship type in the schema."""

    type: str
    description: str
    source_labels: list[str] = Field(default_factory=list)
    target_labels: list[str] = Field(default_factory=list)
    properties: list[SchemaProperty] = Field(default_factory=list)
    bidirectional: bool = False


class GraphSchema(ForgeModel):
    """
    Complete schema of the knowledge graph.

    Used by the query compiler to validate and generate Cypher.
    """

    nodes: list[SchemaNodeLabel] = Field(default_factory=list)
    relationships: list[SchemaRelationship] = Field(default_factory=list)

    def get_node(self, label: str) -> SchemaNodeLabel | None:
        for node in self.nodes:
            if node.label == label:
                return node
        return None

    def get_relationship(self, rel_type: str) -> SchemaRelationship | None:
        for rel in self.relationships:
            if rel.type == rel_type:
                return rel
        return None

    def to_context_string(self) -> str:
        """Generate a context string for LLM prompts."""
        lines = ["# Knowledge Graph Schema\n"]

        lines.append("## Node Labels")
        for node in self.nodes:
            props = ", ".join(p.name for p in node.properties)
            lines.append(f"- {node.label}: {node.description}")
            lines.append(f"  Properties: {props}")

        lines.append("\n## Relationships")
        for rel in self.relationships:
            direction = "<->" if rel.bidirectional else "->"
            lines.append(
                f"- {rel.type}: ({', '.join(rel.source_labels)}) "
                f"{direction} ({', '.join(rel.target_labels)})"
            )
            lines.append(f"  {rel.description}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# QUERY REQUESTS
# ═══════════════════════════════════════════════════════════════


class NaturalLanguageQueryRequest(ForgeModel):
    """Request to query the knowledge graph in natural language."""

    question: str = Field(
        min_length=3,
        max_length=1000,
        description="Natural language question",
    )
    user_trust: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Trust level of requesting user",
    )
    include_explanation: bool = Field(
        default=True,
        description="Include query explanation in response",
    )
    include_cypher: bool = Field(
        default=False,
        description="Include generated Cypher in response",
    )
    synthesize_answer: bool = Field(
        default=True,
        description="Generate human-readable answer",
    )
    max_results: int = Field(default=100, ge=1, le=1000)


class DirectCypherRequest(ForgeModel):
    """Request to execute a Cypher query directly (advanced users)."""

    cypher: str = Field(min_length=5, max_length=5000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    read_only: bool = Field(default=True)
    # SECURITY FIX (Audit 4 - M): Reduce max timeout from 5min to 2min
    timeout_ms: int = Field(default=30000, ge=1000, le=120000)


# ═══════════════════════════════════════════════════════════════
# QUERY HISTORY
# ═══════════════════════════════════════════════════════════════


class QueryHistoryEntry(ForgeModel, TimestampMixin):
    """A record of a past query for learning and caching."""

    id: str = Field(default_factory=generate_id)
    user_id: str
    original_question: str
    compiled_query: CompiledQuery
    result_count: int = Field(ge=0)
    execution_time_ms: float = Field(ge=0.0)
    was_successful: bool = True
    error: str | None = None

    # For learning
    user_feedback: str | None = Field(
        default=None,
        description="User feedback on result quality",
    )
    feedback_score: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="1-5 rating from user",
    )


class QuerySuggestion(ForgeModel):
    """A suggested query based on history or context."""

    question: str
    description: str
    category: str | None = None
    popularity: int = Field(default=0, ge=0)


# ═══════════════════════════════════════════════════════════════
# DEFAULT SCHEMA
# ═══════════════════════════════════════════════════════════════


def get_default_schema() -> GraphSchema:
    """Get the default Forge knowledge graph schema."""
    return GraphSchema(
        nodes=[
            SchemaNodeLabel(
                label="Capsule",
                description="Knowledge unit containing insights, decisions, lessons, etc.",
                properties=[
                    SchemaProperty(name="id", type="string", description="Unique identifier"),
                    SchemaProperty(name="type", type="string", description="INSIGHT, DECISION, LESSON, WARNING, PRINCIPLE, MEMORY, KNOWLEDGE, CODE, CONFIG, TEMPLATE, DOCUMENT"),
                    SchemaProperty(name="title", type="string", description="Optional title"),
                    SchemaProperty(name="content", type="string", description="Main content"),
                    SchemaProperty(name="trust_level", type="int", description="0-100 trust score"),
                    SchemaProperty(name="owner_id", type="string", description="Creator user ID"),
                    SchemaProperty(name="tags", type="list[string]", description="Categorization tags"),
                    SchemaProperty(name="created_at", type="datetime", indexed=True),
                ],
            ),
            SchemaNodeLabel(
                label="User",
                description="User account in the system",
                properties=[
                    SchemaProperty(name="id", type="string"),
                    SchemaProperty(name="username", type="string"),
                    SchemaProperty(name="trust_flame", type="int", description="0-100 trust score"),
                    SchemaProperty(name="role", type="string", description="USER, ADMIN, MODERATOR"),
                ],
            ),
            SchemaNodeLabel(
                label="Proposal",
                description="Governance proposal for changes",
                properties=[
                    SchemaProperty(name="id", type="string"),
                    SchemaProperty(name="title", type="string"),
                    SchemaProperty(name="status", type="string", description="DRAFT, ACTIVE, VOTING, PASSED, REJECTED"),
                    SchemaProperty(name="created_by", type="string"),
                ],
            ),
            SchemaNodeLabel(
                label="Vote",
                description="Vote on a proposal",
                properties=[
                    SchemaProperty(name="id", type="string"),
                    SchemaProperty(name="choice", type="string", description="for, against, abstain"),
                    SchemaProperty(name="weight", type="float"),
                ],
            ),
        ],
        relationships=[
            SchemaRelationship(
                type="DERIVED_FROM",
                description="Capsule lineage - child derived from parent",
                source_labels=["Capsule"],
                target_labels=["Capsule"],
            ),
            SchemaRelationship(
                type="RELATED_TO",
                description="Semantic relationship between capsules",
                source_labels=["Capsule"],
                target_labels=["Capsule"],
                bidirectional=True,
                properties=[
                    SchemaProperty(name="strength", type="float"),
                    SchemaProperty(name="confidence", type="float"),
                ],
            ),
            SchemaRelationship(
                type="SUPPORTS",
                description="Source capsule supports target's claims",
                source_labels=["Capsule"],
                target_labels=["Capsule"],
            ),
            SchemaRelationship(
                type="CONTRADICTS",
                description="Conflicting information between capsules",
                source_labels=["Capsule"],
                target_labels=["Capsule"],
                bidirectional=True,
            ),
            SchemaRelationship(
                type="OWNS",
                description="User owns/created capsule",
                source_labels=["User"],
                target_labels=["Capsule"],
            ),
            SchemaRelationship(
                type="VOTED",
                description="Vote cast on proposal",
                source_labels=["Vote"],
                target_labels=["Proposal"],
            ),
            SchemaRelationship(
                type="CAST_BY",
                description="User who cast the vote",
                source_labels=["Vote"],
                target_labels=["User"],
            ),
        ],
    )
