"""
Forge Cascade V2 - Graph Extension Routes

Provides endpoints for:
- Graph algorithms (PageRank, centrality, community detection)
- Natural language knowledge queries
- Temporal operations (versions, trust timeline)
- Semantic edge management
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

# SECURITY FIX (Audit 4): Make query limits configurable via environment
# These can be adjusted based on server capacity and security requirements
GRAPH_MAX_NODES = int(os.getenv("GRAPH_MAX_NODES", "1000"))
GRAPH_MAX_NEIGHBORS = int(os.getenv("GRAPH_MAX_NEIGHBORS", "100"))
GRAPH_MAX_PATHS = int(os.getenv("GRAPH_MAX_PATHS", "20"))
GRAPH_MAX_VERSIONS = int(os.getenv("GRAPH_MAX_VERSIONS", "200"))

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    CapsuleRepoDep,
    CorrelationIdDep,
    EventSystemDep,
    GraphRepoDep,
    OverlayManagerDep,
    StandardUserDep,
    TemporalRepoDep,
    TrustedUserDep,
)
from forge.models.base import generate_id
from forge.models.events import Event, EventPriority, EventType

router = APIRouter()


# =============================================================================
# Request/Response Models - Graph Algorithms
# =============================================================================

class PageRankRequest(BaseModel):
    """Request for PageRank computation."""
    node_label: str = Field(default="Capsule", description="Node type to rank")
    relationship_type: str = Field(default="DERIVED_FROM", description="Edge type to follow")
    damping_factor: float = Field(default=0.85, ge=0.0, le=1.0)
    max_iterations: int = Field(default=20, ge=1, le=100)
    limit: int = Field(default=50, ge=1, le=500)


class CentralityRequest(BaseModel):
    """Request for centrality computation."""
    centrality_type: str = Field(default="degree", description="Type: degree, betweenness, closeness")
    node_label: str = Field(default="Capsule")
    relationship_type: str = Field(default="DERIVED_FROM")
    limit: int = Field(default=50, ge=1, le=500)


class CommunityDetectionRequest(BaseModel):
    """Request for community detection."""
    algorithm: str = Field(default="louvain", description="Algorithm: louvain, label_propagation")
    node_label: str = Field(default="Capsule")
    relationship_type: str = Field(default="DERIVED_FROM")
    min_community_size: int = Field(default=2, ge=2)
    limit: int = Field(default=20, ge=1, le=100)


class TrustTransitivityRequest(BaseModel):
    """Request for trust transitivity calculation."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    max_hops: int = Field(default=5, ge=1, le=10)
    decay_factor: float = Field(default=0.9, ge=0.0, le=1.0)


class NodeRankingResponse(BaseModel):
    """A node with its ranking score."""
    node_id: str
    node_type: str
    score: float
    rank: int


class CommunityResponse(BaseModel):
    """A detected community."""
    community_id: int
    size: int
    density: float
    dominant_type: str | None
    node_ids: list[str]


class GraphMetricsResponse(BaseModel):
    """Overall graph metrics."""
    total_nodes: int
    total_edges: int
    density: float
    avg_clustering: float
    connected_components: int
    diameter: int | None
    node_distribution: dict[str, int]
    edge_distribution: dict[str, int]


# =============================================================================
# Request/Response Models - Knowledge Query
# =============================================================================

class KnowledgeQueryRequest(BaseModel):
    """Natural language query request."""
    question: str = Field(..., min_length=5, max_length=2000, description="Question in natural language")
    limit: int = Field(default=20, ge=1, le=100)
    include_results: bool = Field(default=True, description="Include raw results")
    debug: bool = Field(default=False, description="Include Cypher query in response")


class KnowledgeQueryResponse(BaseModel):
    """Knowledge query response."""
    question: str
    answer: str | None
    result_count: int
    execution_time_ms: float
    complexity: str
    explanation: str | None = None
    cypher: str | None = None
    results: list[dict[str, Any]] | None = None


# =============================================================================
# Request/Response Models - Temporal
# =============================================================================

class VersionResponse(BaseModel):
    """Capsule version information."""
    version_id: str
    capsule_id: str
    version_number: str
    snapshot_type: str
    change_type: str
    created_by: str | None
    created_at: str
    content: str | None = None


class TrustSnapshotResponse(BaseModel):
    """Trust snapshot information."""
    trust_value: int
    timestamp: str
    change_type: str
    reason: str | None


class TrustTimelineResponse(BaseModel):
    """Trust evolution timeline."""
    entity_id: str
    entity_type: str
    start: str
    end: str
    snapshot_count: int
    timeline: list[TrustSnapshotResponse]
    trust_min: int | None
    trust_max: int | None
    trust_current: int | None


# =============================================================================
# Request/Response Models - Semantic Edges
# =============================================================================

class CreateSemanticEdgeRequest(BaseModel):
    """Request to create a semantic edge."""
    source_id: str = Field(..., description="Source capsule ID")
    target_id: str = Field(..., description="Target capsule ID")
    relationship_type: str = Field(..., description="Type: SUPPORTS, CONTRADICTS, ELABORATES, SUPERSEDES, REFERENCES, RELATED_TO")
    properties: dict[str, Any] = Field(default_factory=dict)
    bidirectional: bool = Field(default=False)


class SemanticEdgeResponse(BaseModel):
    """Semantic edge information."""
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any]
    created_by: str
    created_at: str
    bidirectional: bool


class SemanticNeighborsResponse(BaseModel):
    """Semantic neighbors of a capsule."""
    capsule_id: str
    neighbors: list[dict[str, Any]]
    total: int


class ContradictionResponse(BaseModel):
    """Contradiction between capsules."""
    capsule_a: dict[str, Any]
    capsule_b: dict[str, Any]
    edge: SemanticEdgeResponse
    severity: str | None


# =============================================================================
# Graph Explorer Endpoints
# =============================================================================


class GraphExplorerResponse(BaseModel):
    """Response for graph exploration."""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    communities: list[dict[str, Any]]
    metrics: dict[str, Any]


@router.get("/explore", response_model=GraphExplorerResponse)
async def explore_graph(
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
    type: str | None = Query(default=None, description="Filter by capsule type"),
    community: int | None = Query(default=None, description="Filter by community ID"),
    min_trust: int = Query(default=0, ge=0, le=100, description="Minimum trust level"),
    limit: int = Query(default=200, ge=10, le=1000, description="Max nodes to return"),
) -> GraphExplorerResponse:
    """
    Get graph data for interactive visualization.

    Returns nodes with their PageRank scores, community assignments,
    and edges with relationship types.
    """
    # Build filter query
    filters = []
    params: dict[str, Any] = {"limit": limit}

    if type:
        filters.append("c.type = $type")
        params["type"] = type
    if community is not None:
        filters.append("c.community_id = $community")
        params["community"] = community
    if min_trust > 0:
        filters.append("c.trust_level >= $min_trust")
        params["min_trust"] = min_trust

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    # Get nodes with metrics
    node_query = f"""
    MATCH (c:Capsule)
    {where_clause}
    OPTIONAL MATCH (c)-[r]-()
    WITH c, count(r) as connection_count
    RETURN c.id AS id,
           c.title AS label,
           c.type AS type,
           COALESCE(c.trust_level, 50) AS trust_level,
           COALESCE(c.pagerank_score, 0.0) AS pagerank_score,
           COALESCE(c.community_id, 0) AS community_id,
           c.created_at AS created_at,
           LEFT(c.content, 200) AS content_preview,
           connection_count
    ORDER BY c.pagerank_score DESC
    LIMIT $limit
    """

    nodes = await graph_repo.client.execute(node_query, params)

    # Get node IDs for edge query
    node_ids = [n["id"] for n in nodes]

    # Get edges between these nodes
    edge_query = """
    MATCH (a:Capsule)-[r]->(b:Capsule)
    WHERE a.id IN $node_ids AND b.id IN $node_ids
    RETURN id(r) AS id,
           a.id AS source,
           b.id AS target,
           type(r) AS relationship_type,
           COALESCE(r.weight, 1.0) AS weight
    """

    edges = await graph_repo.client.execute(edge_query, {"node_ids": node_ids})

    # Get communities
    community_query = """
    MATCH (c:Capsule)
    WHERE c.id IN $node_ids
    WITH c.community_id AS cid, collect(c) AS members
    RETURN cid AS id,
           size(members) AS size,
           [m IN members | m.type][0] AS dominant_type,
           1.0 AS density
    ORDER BY size DESC
    """

    communities = await graph_repo.client.execute(community_query, {"node_ids": node_ids})

    # Get metrics
    metrics = await graph_repo.get_graph_metrics()

    return GraphExplorerResponse(
        nodes=[dict(n) for n in nodes],
        edges=[dict(e) for e in edges],
        communities=[dict(c) for c in communities if c["id"] is not None],
        metrics={
            "total_nodes": metrics.total_nodes,
            "total_edges": metrics.total_edges,
            "density": metrics.density,
            "connected_components": metrics.connected_components,
        }
    )


@router.get("/node/{node_id}/neighbors")
async def get_node_neighbors(
    node_id: str,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Get detailed information about a node and its neighbors.
    """
    # Get node details
    node_query = """
    MATCH (c:Capsule {id: $node_id})
    RETURN c.id AS id,
           c.title AS title,
           c.type AS type,
           c.content AS content,
           COALESCE(c.trust_level, 50) AS trust_level,
           COALESCE(c.pagerank_score, 0.0) AS pagerank_score,
           COALESCE(c.community_id, 0) AS community_id,
           c.created_at AS created_at
    """

    node = await graph_repo.client.execute_single(node_query, {"node_id": node_id})
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Get neighbors
    neighbor_query = """
    MATCH (c:Capsule {id: $node_id})-[r]-(n:Capsule)
    RETURN n.id AS id,
           n.title AS label,
           n.type AS type,
           COALESCE(n.trust_level, 50) AS trust_level,
           COALESCE(n.pagerank_score, 0.0) AS pagerank_score,
           COALESCE(n.community_id, 0) AS community_id,
           type(r) AS relationship,
           CASE WHEN startNode(r) = c THEN 'out' ELSE 'in' END AS direction
    LIMIT $limit
    """

    neighbors = await graph_repo.client.execute(
        neighbor_query, {"node_id": node_id, "limit": limit}
    )

    return {
        "id": node["id"],
        "title": node["title"],
        "type": node["type"],
        "content": node["content"],
        "trust_level": node["trust_level"],
        "pagerank_score": node["pagerank_score"],
        "community_id": node["community_id"],
        "neighbors": [
            {
                "node": {
                    "id": n["id"],
                    "label": n["label"],
                    "type": n["type"],
                    "trust_level": n["trust_level"],
                    "pagerank_score": n["pagerank_score"],
                    "community_id": n["community_id"],
                },
                "relationship": n["relationship"],
                "direction": n["direction"],
            }
            for n in neighbors
        ],
    }


@router.get("/paths/{source_id}/{target_id}")
async def find_paths(
    source_id: str,
    target_id: str,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
    max_hops: int = Query(default=5, ge=1, le=10),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """
    Find shortest paths between two nodes.
    """
    # SECURITY FIX: Neo4j doesn't support parameterizing path length bounds.
    # max_hops is validated by FastAPI (int between 1-10), so safe to use in f-string.
    path_query = f"""
    MATCH path = shortestPath(
        (source:Capsule {{id: $source_id}})-[*1..{max_hops}]-(target:Capsule {{id: $target_id}})
    )
    RETURN [n IN nodes(path) | {{id: n.id, title: n.title, type: n.type}}] AS nodes,
           [r IN relationships(path) | {{type: type(r)}}] AS relationships,
           length(path) AS path_length
    LIMIT $limit
    """

    paths = await graph_repo.client.execute(
        path_query,
        {"source_id": source_id, "target_id": target_id, "limit": limit}
    )

    return {
        "source_id": source_id,
        "target_id": target_id,
        "paths_found": len(paths),
        "paths": [
            {
                "nodes": p["nodes"],
                "relationships": p["relationships"],
                "length": p["path_length"],
            }
            for p in paths
        ],
    }


# =============================================================================
# Graph Algorithm Endpoints
# =============================================================================

@router.post("/algorithms/pagerank", response_model=list[NodeRankingResponse])
async def compute_pagerank(
    request: PageRankRequest,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
) -> list[NodeRankingResponse]:
    """
    Compute PageRank scores for nodes in the graph.

    PageRank measures the importance/influence of nodes based on
    their connections. Useful for identifying key capsules or users.
    """
    rankings = await graph_repo.compute_pagerank(
        node_label=request.node_label,
        relationship_type=request.relationship_type,
        damping_factor=request.damping_factor,
        max_iterations=request.max_iterations,
        limit=request.limit,
    )
    return [
        NodeRankingResponse(
            node_id=r.node_id,
            node_type=r.node_type,
            score=r.score,
            rank=r.rank,
        )
        for r in rankings
    ]


@router.post("/algorithms/centrality", response_model=list[NodeRankingResponse])
async def compute_centrality(
    request: CentralityRequest,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
) -> list[NodeRankingResponse]:
    """
    Compute centrality metrics for nodes.

    Types:
    - degree: Number of connections
    - betweenness: Bridge nodes between communities
    - closeness: Average distance to all other nodes
    """
    rankings = await graph_repo.compute_centrality(
        centrality_type=request.centrality_type,
        node_label=request.node_label,
        relationship_type=request.relationship_type,
        limit=request.limit,
    )
    return [
        NodeRankingResponse(
            node_id=r.node_id,
            node_type=r.node_type,
            score=r.score,
            rank=r.rank,
        )
        for r in rankings
    ]


@router.post("/algorithms/communities", response_model=list[CommunityResponse])
async def detect_communities(
    request: CommunityDetectionRequest,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
) -> list[CommunityResponse]:
    """
    Detect communities in the knowledge graph.

    Uses Louvain or label propagation algorithm to find
    clusters of closely related capsules.
    """
    communities = await graph_repo.detect_communities(
        algorithm=request.algorithm,
        node_label=request.node_label,
        relationship_type=request.relationship_type,
        min_community_size=request.min_community_size,
        limit=request.limit,
    )
    return [
        CommunityResponse(
            community_id=c.community_id,
            size=c.size,
            density=c.density,
            dominant_type=c.dominant_type,
            node_ids=c.node_ids,
        )
        for c in communities
    ]


@router.post("/algorithms/trust-transitivity")
async def compute_trust_transitivity(
    request: TrustTransitivityRequest,
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
) -> dict[str, Any]:
    """
    Compute transitive trust between two nodes.

    Calculates trust through graph paths, with decay
    over distance.
    """
    result = await graph_repo.compute_trust_transitivity(
        source_id=request.source_id,
        target_id=request.target_id,
        max_hops=request.max_hops,
        decay_factor=request.decay_factor,
    )
    return {
        "source_id": request.source_id,
        "target_id": request.target_id,
        "trust_score": result.trust_score,
        "path_count": result.path_count,
        "best_path": result.best_path,
        "best_path_length": result.best_path_length,
    }


@router.get("/metrics", response_model=GraphMetricsResponse)
async def get_graph_metrics(
    user: ActiveUserDep,
    graph_repo: GraphRepoDep,
) -> GraphMetricsResponse:
    """
    Get overall graph statistics and metrics.
    """
    metrics = await graph_repo.get_graph_metrics()
    return GraphMetricsResponse(
        total_nodes=metrics.total_nodes,
        total_edges=metrics.total_edges,
        density=metrics.density,
        avg_clustering=metrics.avg_clustering,
        connected_components=metrics.connected_components,
        diameter=metrics.diameter,
        node_distribution=metrics.node_distribution,
        edge_distribution=metrics.edge_distribution,
    )


# =============================================================================
# Knowledge Query Endpoints
# =============================================================================

@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    request: KnowledgeQueryRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
    graph_repo: GraphRepoDep,
) -> KnowledgeQueryResponse:
    """
    Query the knowledge graph using natural language.

    Examples:
    - "What influenced the rate limiting decision?"
    - "Who contributed most to security knowledge?"
    - "Find contradictions in authentication docs"
    """
    import time
    start = time.time()

    # Get the knowledge query overlay
    knowledge_overlay = overlay_manager.get_overlay("knowledge_query")
    if not knowledge_overlay:
        return KnowledgeQueryResponse(
            question=request.question,
            answer="Knowledge query overlay not available",
            result_count=0,
            execution_time_ms=0.0,
            complexity="unknown",
        )

    try:
        # Use the overlay to compile and execute the query
        from forge.overlays.knowledge_query import QueryContext
        context = QueryContext(
            question=request.question,
            user_trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
            limit=request.limit,
            include_debug=request.debug,
        )
        result = await knowledge_overlay.execute_query(context, graph_repo)

        execution_time = (time.time() - start) * 1000

        return KnowledgeQueryResponse(
            question=request.question,
            answer=result.answer,
            result_count=result.result_count,
            execution_time_ms=execution_time,
            complexity=result.complexity,
            explanation=result.explanation if request.debug else None,
            cypher=result.cypher if request.debug else None,
            results=result.results if request.include_results else None,
        )
    except Exception as e:
        execution_time = (time.time() - start) * 1000
        return KnowledgeQueryResponse(
            question=request.question,
            answer=f"Error processing query: {str(e)}",
            result_count=0,
            execution_time_ms=execution_time,
            complexity="error",
        )


@router.get("/query/suggestions")
async def get_query_suggestions(
    user: ActiveUserDep,
) -> dict[str, list[str]]:
    """
    Get example queries to help users understand capabilities.
    """
    return {
        "examples": [
            "What are the most influential capsules?",
            "Who created the most knowledge this month?",
            "Find all decisions about authentication",
            "What capsules contradict each other?",
            "Show the lineage of capsule X",
            "What knowledge is related to security?",
            "Who has the highest trust flame?",
            "Find all proposals pending approval",
        ]
    }


@router.get("/query/schema")
async def get_queryable_schema(
    user: ActiveUserDep,
) -> dict[str, Any]:
    """
    Get information about the queryable graph schema.
    """
    return {
        "node_labels": ["Capsule", "User", "Overlay", "Proposal", "Vote"],
        "relationship_types": [
            "DERIVED_FROM", "RELATED_TO", "SUPPORTS", "CONTRADICTS",
            "ELABORATES", "SUPERSEDES", "REFERENCES", "OWNS", "VOTED"
        ],
        "queryable_properties": {
            "Capsule": ["id", "title", "content", "type", "trust_level", "created_at", "tags"],
            "User": ["id", "username", "trust_flame", "role"],
            "Proposal": ["id", "title", "status", "proposer_id"],
        }
    }


# =============================================================================
# Temporal Endpoints - Version History
# =============================================================================

@router.get("/capsules/{capsule_id}/versions", response_model=list[VersionResponse])
async def get_capsule_versions(
    capsule_id: str,
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
    capsule_repo: CapsuleRepoDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VersionResponse]:
    """
    Get version history for a capsule.
    """
    # Verify capsule exists
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    versions = await temporal_repo.get_version_history(capsule_id=capsule_id, limit=limit)
    return [
        VersionResponse(
            version_id=v.version_id,
            capsule_id=v.capsule_id,
            version_number=v.version_number,
            snapshot_type=v.snapshot_type,
            change_type=v.change_type,
            created_by=v.created_by,
            created_at=v.created_at.isoformat() if v.created_at else "",
            content=None,  # Don't include full content in list
        )
        for v in versions
    ]


@router.get("/capsules/{capsule_id}/versions/{version_id}", response_model=VersionResponse)
async def get_capsule_version(
    capsule_id: str,
    version_id: str,
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
) -> VersionResponse:
    """
    Get a specific version with full content.
    """
    version = await temporal_repo.get_version(version_id)
    if not version or version.capsule_id != capsule_id:
        raise HTTPException(status_code=404, detail="Version not found")

    return VersionResponse(
        version_id=version.version_id,
        capsule_id=version.capsule_id,
        version_number=version.version_number,
        snapshot_type=version.snapshot_type,
        change_type=version.change_type,
        created_by=version.created_by,
        created_at=version.created_at.isoformat() if version.created_at else "",
        content=version.content,
    )


@router.get("/capsules/{capsule_id}/at-time")
async def get_capsule_at_time(
    capsule_id: str,
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
    timestamp: str = Query(..., description="ISO timestamp"),
) -> dict[str, Any]:
    """
    Get capsule state at a specific point in time.
    """
    from datetime import UTC, datetime as dt

    try:
        target_time = dt.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")

    version = await temporal_repo.get_capsule_at_time(capsule_id, target_time)
    if not version:
        return {
            "capsule_id": capsule_id,
            "timestamp": timestamp,
            "found": False,
        }

    return {
        "capsule_id": capsule_id,
        "timestamp": timestamp,
        "found": True,
        "version": {
            "version_id": version.version_id,
            "version_number": version.version_number,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "content": version.content,
        }
    }


@router.get("/capsules/{capsule_id}/versions/diff")
async def diff_capsule_versions(
    capsule_id: str,
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
    version_a: str = Query(..., description="First version ID"),
    version_b: str = Query(..., description="Second version ID"),
) -> dict[str, Any]:
    """
    Compare two versions of a capsule.
    """
    # Get both versions
    va = await temporal_repo.get_version(version_a)
    vb = await temporal_repo.get_version(version_b)

    if not va or va.capsule_id != capsule_id:
        raise HTTPException(status_code=404, detail=f"Version {version_a} not found")
    if not vb or vb.capsule_id != capsule_id:
        raise HTTPException(status_code=404, detail=f"Version {version_b} not found")

    diff = await temporal_repo.diff_versions(version_a, version_b)

    return {
        "version_a": {
            "version_id": va.version_id,
            "version_number": va.version_number,
            "created_at": va.created_at.isoformat() if va.created_at else None,
        },
        "version_b": {
            "version_id": vb.version_id,
            "version_number": vb.version_number,
            "created_at": vb.created_at.isoformat() if vb.created_at else None,
        },
        "diff": diff,
    }


# =============================================================================
# Temporal Endpoints - Trust Timeline
# =============================================================================

@router.get("/trust/{entity_type}/{entity_id}/timeline", response_model=TrustTimelineResponse)
async def get_trust_timeline(
    entity_type: str,
    entity_id: str,
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
    start: str | None = Query(default=None, description="Start date ISO"),
    end: str | None = Query(default=None, description="End date ISO"),
) -> TrustTimelineResponse:
    """
    Get trust evolution timeline for a user or capsule.

    entity_type: "User" or "Capsule"
    """
    from datetime import UTC, datetime as dt
    from datetime import timedelta

    # Validate entity type
    if entity_type not in ["User", "Capsule"]:
        raise HTTPException(status_code=400, detail="entity_type must be 'User' or 'Capsule'")

    # Parse dates or use defaults
    try:
        start_dt = dt.fromisoformat(start.replace("Z", "+00:00")) if start else (dt.utcnow() - timedelta(days=30))
        end_dt = dt.fromisoformat(end.replace("Z", "+00:00")) if end else dt.utcnow()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    timeline = await temporal_repo.get_trust_timeline(
        entity_id=entity_id,
        entity_type=entity_type,
        start=start_dt,
        end=end_dt,
    )

    trust_values = [s.trust_value for s in timeline]

    return TrustTimelineResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        snapshot_count=len(timeline),
        timeline=[
            TrustSnapshotResponse(
                trust_value=s.trust_value,
                timestamp=s.timestamp.isoformat() if s.timestamp else "",
                change_type=s.change_type,
                reason=s.reason,
            )
            for s in timeline
        ],
        trust_min=min(trust_values) if trust_values else None,
        trust_max=max(trust_values) if trust_values else None,
        trust_current=trust_values[-1] if trust_values else None,
    )


@router.post("/snapshots/graph")
async def create_graph_snapshot(
    user: TrustedUserDep,
    temporal_repo: TemporalRepoDep,
    graph_repo: GraphRepoDep,
) -> dict[str, Any]:
    """
    Create a point-in-time snapshot of the graph.

    Requires TRUSTED trust level.
    """
    # Get current graph metrics
    metrics = await graph_repo.get_graph_metrics()

    # Create snapshot with all metrics
    snapshot = await temporal_repo.create_graph_snapshot(
        metrics={
            "total_nodes": metrics.total_nodes,
            "total_edges": metrics.total_edges,
            "density": metrics.density,
            "avg_degree": metrics.avg_degree if hasattr(metrics, 'avg_degree') else 0.0,
            "connected_components": metrics.connected_components,
            "nodes_by_type": metrics.node_distribution,
            "edges_by_type": metrics.edge_distribution,
        },
        created_by=user.id,
    )

    return {
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else datetime.now(UTC).isoformat(),
        "metrics": {
            "total_nodes": snapshot.total_nodes,
            "total_edges": snapshot.total_edges,
            "density": snapshot.density,
            "avg_degree": snapshot.avg_degree,
            "connected_components": snapshot.connected_components,
            "nodes_by_type": snapshot.nodes_by_type,
            "edges_by_type": snapshot.edges_by_type,
        },
    }


@router.get("/snapshots/graph/latest")
async def get_latest_graph_snapshot(
    user: ActiveUserDep,
    temporal_repo: TemporalRepoDep,
) -> dict[str, Any]:
    """
    Get the most recent graph snapshot.
    """
    snapshot = await temporal_repo.get_latest_graph_snapshot()
    if not snapshot:
        return {
            "snapshot_id": None,
            "found": False,
        }

    return {
        "snapshot_id": snapshot.id,
        "found": True,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "metrics": {
            "total_nodes": snapshot.total_nodes,
            "total_edges": snapshot.total_edges,
            "density": snapshot.density,
            "avg_degree": snapshot.avg_degree,
            "connected_components": snapshot.connected_components,
            "nodes_by_type": snapshot.nodes_by_type,
            "edges_by_type": snapshot.edges_by_type,
            "avg_trust": snapshot.avg_trust,
            "community_count": snapshot.community_count,
            "active_anomalies": snapshot.active_anomalies,
        },
    }


# =============================================================================
# Semantic Edge Endpoints
# =============================================================================

@router.post("/edges", response_model=SemanticEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_semantic_edge(
    request: CreateSemanticEdgeRequest,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    event_system: EventSystemDep,
    correlation_id: CorrelationIdDep,
) -> SemanticEdgeResponse:
    """
    Create a semantic relationship between capsules.

    Relationship types:
    - SUPPORTS: A supports B's claims
    - CONTRADICTS: A contradicts B
    - ELABORATES: A provides detail on B
    - SUPERSEDES: A replaces B
    - REFERENCES: A cites B
    - RELATED_TO: Generic association
    """
    from forge.models.semantic_edges import SemanticEdgeCreate, SemanticRelationType

    # Verify both capsules exist
    source = await capsule_repo.get_by_id(request.source_id)
    target = await capsule_repo.get_by_id(request.target_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source capsule not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target capsule not found")

    # Validate relationship type
    valid_types = {"SUPPORTS", "CONTRADICTS", "ELABORATES", "SUPERSEDES", "REFERENCES", "RELATED_TO"}
    if request.relationship_type.upper() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relationship type. Must be one of: {valid_types}"
        )

    # Create edge using proper model
    edge_data = SemanticEdgeCreate(
        source_id=request.source_id,
        target_id=request.target_id,
        relationship_type=SemanticRelationType(request.relationship_type.upper()),
        properties=request.properties,
    )
    edge = await capsule_repo.create_semantic_edge(
        data=edge_data,
        created_by=user.id,
    )

    # Emit event for lineage tracker and other overlays
    await event_system.publish(Event(
        id=generate_id(),
        type=EventType.SEMANTIC_EDGE_CREATED,
        source="api.graph",
        payload={
            "edge_id": edge.id,
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "relationship_type": edge.relationship_type.value,
            "confidence": edge.confidence,
            "bidirectional": edge.bidirectional,
            "created_by": user.id,
        },
        correlation_id=correlation_id,
        priority=EventPriority.NORMAL,
    ))

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=request.source_id,
        action="semantic_edge_created",
        details={
            "target_id": request.target_id,
            "relationship_type": request.relationship_type,
            "bidirectional": request.bidirectional
        },
        correlation_id=correlation_id,
    )

    return SemanticEdgeResponse(
        id=edge.id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        relationship_type=edge.relationship_type.value,
        properties=edge.properties,
        created_by=edge.created_by,
        created_at=edge.created_at.isoformat(),
        bidirectional=edge.bidirectional
    )


@router.get("/capsules/{capsule_id}/edges", response_model=list[SemanticEdgeResponse])
async def get_capsule_edges(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    direction: str = Query(default="both", description="in, out, or both"),
    relationship_type: str | None = Query(default=None, description="Filter by type"),
) -> list[SemanticEdgeResponse]:
    """
    Get semantic edges for a capsule.
    """
    # Verify capsule exists
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    rel_types = [relationship_type.upper()] if relationship_type else None
    edges = await capsule_repo.get_semantic_edges(
        capsule_id=capsule_id,
        direction=direction,
        rel_types=rel_types
    )

    return [
        SemanticEdgeResponse(
            id=e.id,
            source_id=e.source_id,
            target_id=e.target_id,
            relationship_type=e.relationship_type.value,
            properties=e.properties,
            created_by=e.created_by,
            created_at=e.created_at.isoformat(),
            bidirectional=e.bidirectional
        )
        for e in edges
    ]


@router.get("/capsules/{capsule_id}/neighbors", response_model=SemanticNeighborsResponse)
async def get_semantic_neighbors(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    relationship_type: str | None = Query(default=None),
    direction: str = Query(default="both"),
    limit: int = Query(default=50, ge=1, le=200),
) -> SemanticNeighborsResponse:
    """
    Get semantically connected neighbors of a capsule.
    """
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    rel_types = [relationship_type.upper()] if relationship_type else None
    neighbors = await capsule_repo.get_semantic_neighbors(
        capsule_id=capsule_id,
        rel_types=rel_types,
        direction=direction
    )

    return SemanticNeighborsResponse(
        capsule_id=capsule_id,
        neighbors=[
            {
                "capsule": {
                    "id": n.capsule.id,
                    "title": n.capsule.title,
                    "type": n.capsule.type.value if hasattr(n.capsule.type, 'value') else str(n.capsule.type),
                },
                "edge": {
                    "relationship_type": n.edge.relationship_type.value,
                    "direction": n.direction,
                    "properties": n.edge.properties
                }
            }
            for n in neighbors[:limit]
        ],
        total=len(neighbors)
    )


@router.get("/capsules/{capsule_id}/contradictions", response_model=list[ContradictionResponse])
async def get_contradictions(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
) -> list[ContradictionResponse]:
    """
    Find contradictions involving a capsule.
    """
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    contradictions = await capsule_repo.find_contradictions(capsule_id)

    return [
        ContradictionResponse(
            capsule_a={
                "id": c[0].id,
                "title": c[0].title,
                "type": c[0].type.value if hasattr(c[0].type, 'value') else str(c[0].type),
            },
            capsule_b={
                "id": c[1].id,
                "title": c[1].title,
                "type": c[1].type.value if hasattr(c[1].type, 'value') else str(c[1].type),
            },
            edge=SemanticEdgeResponse(
                id=c[2].id,
                source_id=c[2].source_id,
                target_id=c[2].target_id,
                relationship_type=c[2].relationship_type.value,
                properties=c[2].properties,
                created_by=c[2].created_by,
                created_at=c[2].created_at.isoformat(),
                bidirectional=c[2].bidirectional
            ),
            severity=c[2].properties.get("severity")
        )
        for c in contradictions
    ]


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_semantic_edge(
    edge_id: str,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
):
    """
    Delete a semantic edge.

    Only the edge creator or admin can delete.
    """
    # Get edge first to check permissions
    edge = await capsule_repo.get_semantic_edge(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")

    from forge.security.authorization import is_admin
    if edge.created_by != user.id and not is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Only the edge creator can delete this edge"
        )

    await capsule_repo.delete_semantic_edge(edge_id)

    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=edge.source_id,
        action="semantic_edge_deleted",
        details={"edge_id": edge_id, "target_id": edge.target_id},
        correlation_id=correlation_id,
    )


# =============================================================================
# Analysis Endpoints
# =============================================================================

@router.get("/analysis/contradiction-clusters")
async def get_contradiction_clusters(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    min_size: int = Query(default=2, ge=2, le=20),
) -> dict[str, Any]:
    """
    Find clusters of contradicting capsules.

    Useful for identifying areas of knowledge conflict.
    """
    clusters = await capsule_repo.find_contradiction_clusters(min_size=min_size)

    return {
        "cluster_count": len(clusters),
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "size": c.size,
                "capsule_ids": c.capsule_ids,
                "contradiction_count": c.contradiction_count,
                "topics": c.topics
            }
            for c in clusters
        ]
    }


@router.post("/analysis/refresh")
async def refresh_graph_analysis(
    user: TrustedUserDep,
    overlay_manager: OverlayManagerDep,
) -> dict[str, Any]:
    """
    Refresh all cached graph analysis results.

    Requires TRUSTED trust level.
    """
    # Clear caches in graph algorithms overlay
    graph_overlay = overlay_manager.get_overlay("graph_algorithms")
    if graph_overlay:
        await graph_overlay.clear_cache()

    return {
        "refreshed": True,
        "refreshed_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Contradiction Resolution Endpoints
# =============================================================================


class ContradictionResolution(BaseModel):
    """Request to resolve a contradiction."""

    resolution_type: str = Field(
        description="How to resolve: 'keep_both', 'supersede', 'merge', 'dismiss'"
    )
    winning_capsule_id: str | None = Field(
        default=None,
        description="ID of the capsule that should be kept (for supersede)",
    )
    notes: str | None = Field(default=None, description="Resolution notes")


@router.get("/contradictions/unresolved")
async def get_unresolved_contradictions(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """
    Get all unresolved contradictions across the knowledge base.

    Returns contradictions ordered by severity.
    """
    # Get all CONTRADICTS edges that don't have resolution_status=resolved
    query = """
    MATCH (a:Capsule)-[e:CONTRADICTS]->(b:Capsule)
    WHERE e.resolution_status IS NULL OR e.resolution_status <> 'resolved'
    OPTIONAL MATCH (a)-[:HAS_TAG]->(t1:Tag)
    OPTIONAL MATCH (b)-[:HAS_TAG]->(t2:Tag)
    WITH a, b, e, collect(DISTINCT t1.name) + collect(DISTINCT t2.name) AS all_tags
    RETURN a.id AS capsule_a_id,
           a.title AS capsule_a_title,
           a.type AS capsule_a_type,
           a.trust_level AS capsule_a_trust,
           b.id AS capsule_b_id,
           b.title AS capsule_b_title,
           b.type AS capsule_b_type,
           b.trust_level AS capsule_b_trust,
           e.id AS edge_id,
           e.created_at AS created_at,
           e.properties AS properties,
           all_tags AS tags
    ORDER BY COALESCE(e.properties.severity, 'medium') DESC, e.created_at DESC
    SKIP $offset
    LIMIT $limit
    """

    results = await capsule_repo.client.execute(
        query, {"limit": limit, "offset": offset}
    )

    # Count total
    count_query = """
    MATCH (a:Capsule)-[e:CONTRADICTS]->(b:Capsule)
    WHERE e.resolution_status IS NULL OR e.resolution_status <> 'resolved'
    RETURN count(e) AS total
    """
    count_result = await capsule_repo.client.execute_single(count_query, {})
    total = count_result.get("total", 0) if count_result else 0

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "contradictions": [
            {
                "edge_id": r.get("edge_id"),
                "capsule_a": {
                    "id": r.get("capsule_a_id"),
                    "title": r.get("capsule_a_title"),
                    "type": r.get("capsule_a_type"),
                    "trust_level": r.get("capsule_a_trust"),
                },
                "capsule_b": {
                    "id": r.get("capsule_b_id"),
                    "title": r.get("capsule_b_title"),
                    "type": r.get("capsule_b_type"),
                    "trust_level": r.get("capsule_b_trust"),
                },
                "severity": (r.get("properties") or {}).get("severity", "medium"),
                "tags": list(set(r.get("tags", []))),
                "created_at": r.get("created_at"),
            }
            for r in results
        ],
    }


@router.post("/contradictions/{edge_id}/resolve")
async def resolve_contradiction(
    edge_id: str,
    resolution: ContradictionResolution,
    user: TrustedUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> dict[str, Any]:
    """
    Resolve a contradiction.

    Resolution types:
    - keep_both: Mark as acknowledged but keep both capsules
    - supersede: One capsule supersedes the other
    - merge: Merge both capsules (future feature)
    - dismiss: Dismiss as not a real contradiction

    Requires TRUSTED trust level.
    """
    # Get the edge
    edge = await capsule_repo.get_semantic_edge(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Contradiction edge not found")

    if edge.relationship_type.value != "CONTRADICTS":
        raise HTTPException(status_code=400, detail="Edge is not a contradiction")

    # Update edge with resolution
    query = """
    MATCH ()-[e:CONTRADICTS {id: $edge_id}]->()
    SET e.resolution_status = 'resolved',
        e.resolution_type = $resolution_type,
        e.resolved_by = $resolved_by,
        e.resolved_at = datetime(),
        e.resolution_notes = $notes
    RETURN e.id AS id
    """

    await capsule_repo.client.execute(
        query,
        {
            "edge_id": edge_id,
            "resolution_type": resolution.resolution_type,
            "resolved_by": user.id,
            "notes": resolution.notes,
        },
    )

    # Handle supersede case
    if resolution.resolution_type == "supersede" and resolution.winning_capsule_id:
        losing_id = (
            edge.target_id
            if resolution.winning_capsule_id == edge.source_id
            else edge.source_id
        )

        # Create SUPERSEDES relationship
        supersede_query = """
        MATCH (winner:Capsule {id: $winner_id}), (loser:Capsule {id: $loser_id})
        MERGE (winner)-[s:SUPERSEDES]->(loser)
        SET s.created_at = datetime(),
            s.created_by = $created_by,
            s.reason = $notes
        RETURN s
        """
        await capsule_repo.client.execute(
            supersede_query,
            {
                "winner_id": resolution.winning_capsule_id,
                "loser_id": losing_id,
                "created_by": user.id,
                "notes": resolution.notes or "Contradiction resolution",
            },
        )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=edge.source_id,
        action="contradiction_resolved",
        details={
            "edge_id": edge_id,
            "resolution_type": resolution.resolution_type,
            "winning_capsule_id": resolution.winning_capsule_id,
            "notes": resolution.notes,
        },
        correlation_id=correlation_id,
    )

    return {
        "resolved": True,
        "edge_id": edge_id,
        "resolution_type": resolution.resolution_type,
        "resolved_by": user.id,
        "resolved_at": datetime.now(UTC).isoformat(),
    }


@router.get("/contradictions/stats")
async def get_contradiction_stats(
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
) -> dict[str, Any]:
    """
    Get statistics about contradictions in the knowledge base.
    """
    query = """
    MATCH (a:Capsule)-[e:CONTRADICTS]->(b:Capsule)
    WITH e,
         CASE WHEN e.resolution_status = 'resolved' THEN 1 ELSE 0 END AS is_resolved
    RETURN count(e) AS total,
           sum(is_resolved) AS resolved,
           count(e) - sum(is_resolved) AS unresolved
    """

    result = await capsule_repo.client.execute_single(query, {})

    # Get by severity
    severity_query = """
    MATCH ()-[e:CONTRADICTS]->()
    WHERE e.resolution_status IS NULL OR e.resolution_status <> 'resolved'
    RETURN COALESCE(e.properties.severity, 'medium') AS severity, count(*) AS count
    """
    severity_results = await capsule_repo.client.execute(severity_query, {})

    return {
        "total": result.get("total", 0) if result else 0,
        "resolved": result.get("resolved", 0) if result else 0,
        "unresolved": result.get("unresolved", 0) if result else 0,
        "by_severity": {
            r.get("severity", "medium"): r.get("count", 0)
            for r in severity_results
        },
    }
