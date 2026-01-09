"""
Agent Knowledge Gateway Models

Data structures for AI agent interactions with the knowledge graph.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import Field
from forge.models.base import ForgeModel, generate_id


class AgentCapability(str, Enum):
    """Capabilities an agent can request."""
    READ_CAPSULES = "read_capsules"           # Read capsule content
    QUERY_GRAPH = "query_graph"               # Execute graph queries
    SEMANTIC_SEARCH = "semantic_search"       # Vector similarity search
    CREATE_CAPSULES = "create_capsules"       # Create new capsules
    UPDATE_CAPSULES = "update_capsules"       # Update owned capsules
    EXECUTE_CASCADE = "execute_cascade"       # Trigger cascade effects
    ACCESS_LINEAGE = "access_lineage"         # View capsule lineage
    VIEW_GOVERNANCE = "view_governance"       # View governance state


class AgentTrustLevel(str, Enum):
    """Trust levels for agent access."""
    UNTRUSTED = "untrusted"         # Read-only, rate limited
    BASIC = "basic"                 # Standard read access
    VERIFIED = "verified"           # Extended access, can create
    TRUSTED = "trusted"             # Full access, higher limits
    SYSTEM = "system"               # Internal system agents


class QueryType(str, Enum):
    """Types of agent queries."""
    NATURAL_LANGUAGE = "natural_language"     # NL to Cypher
    SEMANTIC_SEARCH = "semantic_search"       # Vector similarity
    GRAPH_TRAVERSE = "graph_traverse"         # Path/neighbor queries
    DIRECT_CYPHER = "direct_cypher"           # Raw Cypher (trusted only)
    AGGREGATION = "aggregation"               # Stats and metrics


class ResponseFormat(str, Enum):
    """Response format options."""
    JSON = "json"                   # Structured JSON
    MARKDOWN = "markdown"           # Formatted markdown
    PLAIN = "plain"                 # Plain text
    STREAMING = "streaming"         # Server-sent events


class AgentSession(ForgeModel):
    """
    An active agent session with the gateway.
    """

    id: str = Field(default_factory=generate_id)
    agent_id: str = Field(description="Unique identifier for the agent")
    agent_name: str = Field(description="Human-readable agent name")

    # Authentication
    api_key_hash: str = Field(description="Hashed API key")
    owner_user_id: str = Field(description="User who owns this agent")

    # Trust and permissions
    trust_level: AgentTrustLevel = Field(default=AgentTrustLevel.BASIC)
    capabilities: list[AgentCapability] = Field(default_factory=list)
    allowed_capsule_types: list[str] = Field(
        default_factory=list,
        description="Empty = all types allowed"
    )

    # Rate limiting
    requests_per_minute: int = Field(default=60)
    requests_per_hour: int = Field(default=1000)
    max_tokens_per_request: int = Field(default=4096)

    # Usage tracking
    total_requests: int = Field(default=0)
    total_tokens: int = Field(default=0)
    last_request_at: datetime | None = None

    # Session state
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentQuery(ForgeModel):
    """
    A query from an agent to the knowledge gateway.
    """

    id: str = Field(default_factory=generate_id)
    session_id: str
    agent_id: str

    # Query specification
    query_type: QueryType
    query_text: str = Field(description="The query in natural language or Cypher")

    # Optional parameters
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for query processing"
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply (trust_level, type, date, etc.)"
    )

    # Response preferences
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)
    max_results: int = Field(default=10, ge=1, le=100)
    include_metadata: bool = Field(default=True)
    include_lineage: bool = Field(default=False)

    # Execution
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class QueryResult(ForgeModel):
    """
    Result of an agent query.
    """

    query_id: str
    session_id: str

    # Results
    success: bool
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = Field(default=0)

    # For NL queries, include the generated Cypher
    generated_cypher: str | None = None
    cypher_explanation: str | None = None

    # Synthesized answer (for NL queries)
    answer: str | None = Field(
        default=None,
        description="Natural language answer synthesized from results"
    )

    # Citations and sources
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Capsule sources cited in the answer"
    )

    # Metrics
    execution_time_ms: int = Field(default=0)
    tokens_used: int = Field(default=0)
    cache_hit: bool = Field(default=False)

    # Errors
    error: str | None = None
    error_code: str | None = None

    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccessType(str, Enum):
    """Types of capsule access."""
    READ = "read"
    WRITE = "write"
    DERIVE = "derive"


class CapsuleAccess(ForgeModel):
    """
    Record of agent access to a capsule.
    """

    id: str = Field(default_factory=generate_id)
    session_id: str
    agent_id: str
    capsule_id: str

    access_type: AccessType = Field(description="Type of access requested")
    query_id: str | None = None

    # Trust verification
    capsule_trust_level: int
    agent_trust_level: AgentTrustLevel
    access_granted: bool
    denial_reason: str | None = None

    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentCapsuleCreation(ForgeModel):
    """
    Request for an agent to create a capsule.
    """

    id: str = Field(default_factory=generate_id)
    session_id: str
    agent_id: str

    # Capsule details
    capsule_type: str
    title: str
    content: str

    # Provenance
    source_capsule_ids: list[str] = Field(
        default_factory=list,
        description="Capsules this was derived from"
    )
    reasoning: str | None = Field(
        default=None,
        description="Agent's reasoning for creating this capsule"
    )

    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Governance
    requires_approval: bool = Field(
        default=True,
        description="Whether capsule needs human approval"
    )


class GatewayStats(ForgeModel):
    """
    Statistics for the agent gateway.
    """

    # Active sessions
    active_sessions: int = 0
    total_sessions: int = 0

    # Query stats
    queries_today: int = 0
    queries_this_hour: int = 0
    avg_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0

    # By query type
    queries_by_type: dict[str, int] = Field(default_factory=dict)

    # By trust level
    queries_by_trust: dict[str, int] = Field(default_factory=dict)

    # Capsule interactions
    capsules_read: int = 0
    capsules_created: int = 0
    cascades_triggered: int = 0

    # Errors
    error_count: int = 0
    error_rate: float = 0.0

    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StreamChunk(ForgeModel):
    """
    A chunk of streaming response data.
    """

    chunk_id: int
    query_id: str

    # Content
    content_type: str = Field(description="text, result, metadata, done")
    content: str | dict[str, Any]

    # Progress
    is_final: bool = Field(default=False)
    progress_percent: int | None = None

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
