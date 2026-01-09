"""
Agent Knowledge Gateway API Routes

REST and WebSocket endpoints for AI agent access to the knowledge graph.
"""

import logging
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from forge.models.agent_gateway import (
    AgentSession,
    AgentQuery,
    QueryResult,
    QueryType,
    ResponseFormat,
    AgentCapability,
    AgentTrustLevel,
    AgentCapsuleCreation,
    GatewayStats,
)
from forge.services.agent_gateway import get_gateway_service, AgentGatewayService
from forge.api.dependencies import ActiveUserDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-gateway", tags=["Agent Gateway"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create an agent session."""
    agent_name: str = Field(max_length=100)
    trust_level: AgentTrustLevel = Field(default=AgentTrustLevel.BASIC)
    capabilities: list[AgentCapability] | None = None
    allowed_capsule_types: list[str] | None = None
    expires_in_days: int = Field(default=30, ge=1, le=365)


class SessionResponse(BaseModel):
    """Agent session information."""
    id: str
    agent_id: str
    agent_name: str
    owner_user_id: str
    trust_level: str
    capabilities: list[str]
    requests_per_minute: int
    requests_per_hour: int
    total_requests: int
    is_active: bool
    created_at: datetime
    expires_at: datetime | None
    # API key only included on creation
    api_key: str | None = None


class QueryRequest(BaseModel):
    """Request to execute a query."""
    query_type: QueryType = Field(default=QueryType.NATURAL_LANGUAGE)
    query_text: str = Field(min_length=1, max_length=4096)
    context: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)
    max_results: int = Field(default=10, ge=1, le=100)
    include_metadata: bool = Field(default=True)
    include_lineage: bool = Field(default=False)


class QueryResponse(BaseModel):
    """Query result response."""
    query_id: str
    success: bool
    results: list[dict[str, Any]]
    total_count: int
    generated_cypher: str | None
    answer: str | None
    sources: list[dict[str, Any]]
    execution_time_ms: int
    tokens_used: int
    cache_hit: bool
    error: str | None
    error_code: str | None


class CreateCapsuleRequest(BaseModel):
    """Request for agent to create a capsule."""
    capsule_type: str
    title: str = Field(max_length=200)
    content: str = Field(min_length=1)
    source_capsule_ids: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = Field(default=True)


class StatsResponse(BaseModel):
    """Gateway statistics response."""
    active_sessions: int
    total_sessions: int
    queries_today: int
    queries_this_hour: int
    avg_response_time_ms: float
    cache_hit_rate: float
    queries_by_type: dict[str, int]
    capsules_read: int
    capsules_created: int
    error_rate: float


# ============================================================================
# Dependencies
# ============================================================================

async def get_gateway() -> AgentGatewayService:
    """Get gateway service dependency."""
    return await get_gateway_service()


GatewayDep = Depends(get_gateway)


async def get_agent_session(
    api_key: str = Query(..., alias="api_key", description="Agent API key"),
    gateway: AgentGatewayService = GatewayDep,
) -> AgentSession:
    """Authenticate and get agent session from API key."""
    session = await gateway.authenticate(api_key)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
        )
    return session


AgentSessionDep = Depends(get_agent_session)


# ============================================================================
# Session Management Endpoints (User-facing)
# ============================================================================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: ActiveUserDep,
    gateway: AgentGatewayService = GatewayDep,
) -> SessionResponse:
    """
    Create a new agent session.

    Returns the session with API key (shown only once - store securely!).
    """
    session, api_key = await gateway.create_session(
        agent_name=request.agent_name,
        owner_user_id=user.id,
        trust_level=request.trust_level,
        capabilities=request.capabilities,
        allowed_capsule_types=request.allowed_capsule_types,
        expires_in_days=request.expires_in_days,
    )

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        agent_name=session.agent_name,
        owner_user_id=session.owner_user_id,
        trust_level=session.trust_level.value,
        capabilities=[c.value for c in session.capabilities],
        requests_per_minute=session.requests_per_minute,
        requests_per_hour=session.requests_per_hour,
        total_requests=session.total_requests,
        is_active=session.is_active,
        created_at=session.created_at,
        expires_at=session.expires_at,
        api_key=api_key,  # Only returned on creation!
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: ActiveUserDep,
    active_only: bool = Query(default=True),
    gateway: AgentGatewayService = GatewayDep,
) -> list[SessionResponse]:
    """List agent sessions owned by the current user."""
    sessions = await gateway.list_sessions(
        owner_user_id=user.id,
        active_only=active_only,
    )

    return [
        SessionResponse(
            id=s.id,
            agent_id=s.agent_id,
            agent_name=s.agent_name,
            owner_user_id=s.owner_user_id,
            trust_level=s.trust_level.value,
            capabilities=[c.value for c in s.capabilities],
            requests_per_minute=s.requests_per_minute,
            requests_per_hour=s.requests_per_hour,
            total_requests=s.total_requests,
            is_active=s.is_active,
            created_at=s.created_at,
            expires_at=s.expires_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: ActiveUserDep,
    gateway: AgentGatewayService = GatewayDep,
) -> SessionResponse:
    """Get details for a specific session."""
    session = await gateway.get_session(session_id)

    if not session or session.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        agent_name=session.agent_name,
        owner_user_id=session.owner_user_id,
        trust_level=session.trust_level.value,
        capabilities=[c.value for c in session.capabilities],
        requests_per_minute=session.requests_per_minute,
        requests_per_hour=session.requests_per_hour,
        total_requests=session.total_requests,
        is_active=session.is_active,
        created_at=session.created_at,
        expires_at=session.expires_at,
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user: ActiveUserDep,
    gateway: AgentGatewayService = GatewayDep,
) -> dict[str, bool]:
    """Revoke an agent session."""
    session = await gateway.get_session(session_id)

    if not session or session.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    success = await gateway.revoke_session(session_id)
    return {"revoked": success}


# ============================================================================
# Query Endpoints (Agent-facing)
# ============================================================================

@router.post("/query", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    session: AgentSession = AgentSessionDep,
    gateway: AgentGatewayService = GatewayDep,
) -> QueryResponse:
    """
    Execute a knowledge query.

    Supports natural language, semantic search, graph traversal, and more.
    """
    query = AgentQuery(
        session_id=session.id,
        agent_id=session.agent_id,
        query_type=request.query_type,
        query_text=request.query_text,
        context=request.context,
        filters=request.filters,
        response_format=request.response_format,
        max_results=request.max_results,
        include_metadata=request.include_metadata,
        include_lineage=request.include_lineage,
    )

    result = await gateway.execute_query(session, query)

    return QueryResponse(
        query_id=result.query_id,
        success=result.success,
        results=result.results,
        total_count=result.total_count,
        generated_cypher=result.generated_cypher,
        answer=result.answer,
        sources=result.sources,
        execution_time_ms=result.execution_time_ms,
        tokens_used=result.tokens_used,
        cache_hit=result.cache_hit,
        error=result.error,
        error_code=result.error_code,
    )


@router.post("/search")
async def semantic_search(
    query: str = Query(..., min_length=1, max_length=1000),
    max_results: int = Query(default=10, ge=1, le=50),
    capsule_types: str | None = Query(default=None, description="Comma-separated types"),
    session: AgentSession = AgentSessionDep,
    gateway: AgentGatewayService = GatewayDep,
) -> QueryResponse:
    """
    Quick semantic search endpoint.

    Shorthand for execute_query with SEMANTIC_SEARCH type.
    """
    type_list = capsule_types.split(",") if capsule_types else []

    agent_query = AgentQuery(
        session_id=session.id,
        agent_id=session.agent_id,
        query_type=QueryType.SEMANTIC_SEARCH,
        query_text=query,
        filters={"capsule_types": type_list} if type_list else {},
        max_results=max_results,
    )

    result = await gateway.execute_query(session, agent_query)

    return QueryResponse(
        query_id=result.query_id,
        success=result.success,
        results=result.results,
        total_count=result.total_count,
        generated_cypher=result.generated_cypher,
        answer=result.answer,
        sources=result.sources,
        execution_time_ms=result.execution_time_ms,
        tokens_used=result.tokens_used,
        cache_hit=result.cache_hit,
        error=result.error,
        error_code=result.error_code,
    )


@router.get("/capsule/{capsule_id}")
async def get_capsule(
    capsule_id: str,
    session: AgentSession = AgentSessionDep,
    gateway: AgentGatewayService = GatewayDep,
) -> dict[str, Any]:
    """
    Get a specific capsule by ID.

    Subject to trust-level access controls.
    """
    # Use graph traverse to get capsule
    query = AgentQuery(
        session_id=session.id,
        agent_id=session.agent_id,
        query_type=QueryType.GRAPH_TRAVERSE,
        query_text="",
        context={"start_node": capsule_id, "max_depth": 0},
        max_results=1,
    )

    result = await gateway.execute_query(session, query)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    if not result.results:
        raise HTTPException(status_code=404, detail="Capsule not found or access denied")

    return result.results[0]


@router.get("/capsule/{capsule_id}/neighbors")
async def get_capsule_neighbors(
    capsule_id: str,
    relationship_types: str | None = Query(default=None, description="Comma-separated"),
    direction: str = Query(default="both", pattern="^(in|out|both)$"),
    max_depth: int = Query(default=1, ge=1, le=5),
    max_results: int = Query(default=20, ge=1, le=100),
    session: AgentSession = AgentSessionDep,
    gateway: AgentGatewayService = GatewayDep,
) -> QueryResponse:
    """Get neighboring capsules in the knowledge graph."""
    rel_types = relationship_types.split(",") if relationship_types else []

    query = AgentQuery(
        session_id=session.id,
        agent_id=session.agent_id,
        query_type=QueryType.GRAPH_TRAVERSE,
        query_text="",
        context={
            "start_node": capsule_id,
            "relationship_types": rel_types,
            "direction": direction,
            "max_depth": max_depth,
        },
        max_results=max_results,
    )

    result = await gateway.execute_query(session, query)

    return QueryResponse(
        query_id=result.query_id,
        success=result.success,
        results=result.results,
        total_count=result.total_count,
        generated_cypher=result.generated_cypher,
        answer=result.answer,
        sources=result.sources,
        execution_time_ms=result.execution_time_ms,
        tokens_used=result.tokens_used,
        cache_hit=result.cache_hit,
        error=result.error,
        error_code=result.error_code,
    )


# ============================================================================
# Capsule Creation Endpoints
# ============================================================================

@router.post("/capsules")
async def create_capsule(
    request: CreateCapsuleRequest,
    session: AgentSession = AgentSessionDep,
    gateway: AgentGatewayService = GatewayDep,
) -> dict[str, Any]:
    """
    Create a new capsule.

    Requires CREATE_CAPSULES capability.
    """
    creation_request = AgentCapsuleCreation(
        session_id=session.id,
        agent_id=session.agent_id,
        capsule_type=request.capsule_type,
        title=request.title,
        content=request.content,
        source_capsule_ids=request.source_capsule_ids,
        reasoning=request.reasoning,
        tags=request.tags,
        metadata=request.metadata,
        requires_approval=request.requires_approval,
    )

    try:
        result = await gateway.create_capsule(session, creation_request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_gateway_stats(
    gateway: AgentGatewayService = GatewayDep,
) -> StatsResponse:
    """Get gateway usage statistics."""
    stats = await gateway.get_stats()

    return StatsResponse(
        active_sessions=stats.active_sessions,
        total_sessions=stats.total_sessions,
        queries_today=stats.queries_today,
        queries_this_hour=stats.queries_this_hour,
        avg_response_time_ms=stats.avg_response_time_ms,
        cache_hit_rate=stats.cache_hit_rate,
        queries_by_type=stats.queries_by_type,
        capsules_read=stats.capsules_read,
        capsules_created=stats.capsules_created,
        error_rate=stats.error_rate,
    )


@router.get("/sessions/{session_id}/access-logs")
async def get_access_logs(
    session_id: str,
    user: ActiveUserDep,
    limit: int = Query(default=100, ge=1, le=1000),
    gateway: AgentGatewayService = GatewayDep,
) -> list[dict[str, Any]]:
    """Get access logs for a session."""
    session = await gateway.get_session(session_id)

    if not session or session.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    logs = await gateway.get_access_logs(session_id, limit)

    return [
        {
            "id": log.id,
            "capsule_id": log.capsule_id,
            "access_type": log.access_type,
            "capsule_trust_level": log.capsule_trust_level,
            "access_granted": log.access_granted,
            "denial_reason": log.denial_reason,
            "accessed_at": log.accessed_at.isoformat(),
        }
        for log in logs
    ]


# ============================================================================
# WebSocket Streaming Endpoint
# ============================================================================

@router.websocket("/stream")
async def websocket_stream(
    websocket: WebSocket,
    api_key: str = Query(...),
    gateway: AgentGatewayService = GatewayDep,
):
    """
    WebSocket endpoint for streaming query responses.

    Connect with API key, then send JSON query messages.
    Receives streaming chunks as results become available.
    """
    # Authenticate
    session = await gateway.authenticate(api_key)
    if not session:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await websocket.accept()

    try:
        while True:
            # Receive query
            data = await websocket.receive_json()

            # Parse query
            try:
                query = AgentQuery(
                    session_id=session.id,
                    agent_id=session.agent_id,
                    query_type=QueryType(data.get("query_type", "natural_language")),
                    query_text=data.get("query_text", ""),
                    context=data.get("context", {}),
                    filters=data.get("filters", {}),
                    response_format=ResponseFormat.STREAMING,
                    max_results=data.get("max_results", 10),
                )
            except Exception as e:
                await websocket.send_json({
                    "error": f"Invalid query: {str(e)}",
                    "error_code": "INVALID_QUERY",
                })
                continue

            # Stream results
            async for chunk in gateway.stream_query(session, query):
                await websocket.send_json({
                    "chunk_id": chunk.chunk_id,
                    "query_id": chunk.query_id,
                    "content_type": chunk.content_type,
                    "content": chunk.content,
                    "is_final": chunk.is_final,
                    "progress_percent": chunk.progress_percent,
                    "timestamp": chunk.timestamp.isoformat(),
                })

    except WebSocketDisconnect:
        logger.info("agent_websocket_disconnected", session_id=session.id)
    except Exception as e:
        logger.exception("agent_websocket_error", session_id=session.id)
        await websocket.close(code=4000, reason=str(e))


# ============================================================================
# Capability Reference Endpoint
# ============================================================================

@router.get("/capabilities")
async def list_capabilities() -> dict[str, Any]:
    """Get available capabilities and query types."""
    return {
        "capabilities": [
            {
                "name": c.value,
                "description": _get_capability_description(c),
            }
            for c in AgentCapability
        ],
        "query_types": [
            {
                "name": qt.value,
                "description": _get_query_type_description(qt),
            }
            for qt in QueryType
        ],
        "trust_levels": [
            {
                "name": tl.value,
                "description": _get_trust_level_description(tl),
            }
            for tl in AgentTrustLevel
        ],
    }


def _get_capability_description(cap: AgentCapability) -> str:
    """Get description for a capability."""
    descriptions = {
        AgentCapability.READ_CAPSULES: "Read capsule content and metadata",
        AgentCapability.QUERY_GRAPH: "Execute graph queries (NL or Cypher)",
        AgentCapability.SEMANTIC_SEARCH: "Perform vector similarity searches",
        AgentCapability.CREATE_CAPSULES: "Create new knowledge capsules",
        AgentCapability.UPDATE_CAPSULES: "Update capsules owned by the agent's user",
        AgentCapability.EXECUTE_CASCADE: "Trigger cascade effects across overlays",
        AgentCapability.ACCESS_LINEAGE: "View capsule derivation lineage",
        AgentCapability.VIEW_GOVERNANCE: "View governance proposals and votes",
    }
    return descriptions.get(cap, cap.value)


def _get_query_type_description(qt: QueryType) -> str:
    """Get description for a query type."""
    descriptions = {
        QueryType.NATURAL_LANGUAGE: "Natural language question converted to Cypher",
        QueryType.SEMANTIC_SEARCH: "Vector similarity search across capsules",
        QueryType.GRAPH_TRAVERSE: "Traverse graph relationships from a starting node",
        QueryType.DIRECT_CYPHER: "Direct Cypher query (TRUSTED+ only, read-only)",
        QueryType.AGGREGATION: "Aggregation queries (counts, distributions)",
    }
    return descriptions.get(qt, qt.value)


def _get_trust_level_description(tl: AgentTrustLevel) -> str:
    """Get description for a trust level."""
    descriptions = {
        AgentTrustLevel.UNTRUSTED: "Read-only access, strict rate limits",
        AgentTrustLevel.BASIC: "Standard read access with moderate limits",
        AgentTrustLevel.VERIFIED: "Extended access, can create capsules",
        AgentTrustLevel.TRUSTED: "Full access, higher rate limits, direct Cypher",
        AgentTrustLevel.SYSTEM: "Internal system agents with all capabilities",
    }
    return descriptions.get(tl, tl.value)
