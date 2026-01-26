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
from datetime import UTC, datetime, timedelta
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
from forge.models.events import EventPriority, EventType

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

    centrality_type: str = Field(
        default="degree", description="Type: degree, betweenness, closeness"
    )
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

    question: str = Field(
        ..., min_length=5, max_length=2000, description="Question in natural language"
    )
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
    relationship_type: str = Field(
        ...,
        description="Type: SUPPORTS, CONTRADICTS, ELABORATES, SUPERSEDES, REFERENCES, RELATED_TO",
    )
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
    limit: int = Query(
        default=100, ge=10, le=100, description="Max nodes to return"
    ),  # SECURITY FIX (Audit 5): Reduced from 1000
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

    # SECURITY FIX (Audit 7 - Session 3): Cypher query uses f-string for WHERE clause,
    # but this is safe because filter conditions are hardcoded strings ("c.type = $type", etc.)
    # and all user-supplied values are passed via Neo4j parameterized query ($type, $community, $min_trust).
    # Neo4j does not support parameterized WHERE clauses, so this pattern is the standard approach.
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
        },
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
        path_query, {"source_id": source_id, "target_id": target_id, "limit": limit}
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
    # The GraphRepository only has compute_betweenness_centrality method
    # Use the provider's compute_centrality for more options
    from forge.models.graph_analysis import AlgorithmType
    from forge.models.graph_analysis import CentralityRequest as CentralityReq

    # Map centrality type string to AlgorithmType
    algorithm_map = {
        "degree": AlgorithmType.DEGREE_CENTRALITY,
        "betweenness": AlgorithmType.BETWEENNESS_CENTRALITY,
        "closeness": AlgorithmType.CLOSENESS_CENTRALITY,
        "eigenvector": AlgorithmType.EIGENVECTOR_CENTRALITY,
    }
    algorithm = algorithm_map.get(request.centrality_type, AlgorithmType.DEGREE_CENTRALITY)

    centrality_request = CentralityReq(
        algorithm=algorithm,
        node_label=request.node_label,
        relationship_type=request.relationship_type,
        limit=request.limit,
    )
    result = await graph_repo.provider.compute_centrality(centrality_request)
    rankings = result.rankings

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
    # GraphRepository.detect_communities only takes algorithm and min_size
    # Use the provider for more detailed control
    from forge.models.graph_analysis import (
        AlgorithmType,
    )
    from forge.models.graph_analysis import (
        CommunityDetectionRequest as CommunityReq,
    )

    algo = (
        AlgorithmType.COMMUNITY_LOUVAIN
        if request.algorithm == "louvain"
        else AlgorithmType.COMMUNITY_LABEL_PROPAGATION
    )

    community_request = CommunityReq(
        algorithm=algo,
        node_label=request.node_label,
        relationship_type=request.relationship_type,
        min_community_size=request.min_community_size,
        max_communities=request.limit,
    )
    result = await graph_repo.provider.detect_communities(community_request)
    communities = result.communities

    return [
        CommunityResponse(
            community_id=c.community_id,
            size=c.size,
            density=c.density,
            dominant_type=c.dominant_type,
            # Community model has 'members' not 'node_ids'
            node_ids=[m.node_id for m in c.members],
        )
        for c in communities[: request.limit]
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
    # Use the provider directly to get full result with paths
    from forge.models.graph_analysis import TrustTransitivityRequest as TrustReq

    trust_request = TrustReq(
        source_id=request.source_id,
        target_id=request.target_id,
        max_hops=request.max_hops,
        decay_rate=request.decay_factor,
        return_all_paths=True,
    )
    result = await graph_repo.provider.compute_trust_transitivity(trust_request)

    # Get best path info
    best_path_nodes = result.best_path.path_nodes if result.best_path else []
    best_path_length = result.best_path.path_length if result.best_path else 0

    return {
        "source_id": request.source_id,
        "target_id": request.target_id,
        "trust_score": result.transitive_trust,
        "path_count": result.paths_found,
        "best_path": best_path_nodes,
        "best_path_length": best_path_length,
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
        node_distribution=metrics.nodes_by_type,
        edge_distribution=metrics.edges_by_type,
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
    # Use get_by_name method which returns a list of overlays
    knowledge_overlays = overlay_manager.get_by_name("knowledge_query")
    knowledge_overlay = knowledge_overlays[0] if knowledge_overlays else None
    if not knowledge_overlay:
        return KnowledgeQueryResponse(
            question=request.question,
            answer="Knowledge query overlay not available",
            result_count=0,
            execution_time_ms=0.0,
            complexity="unknown",
        )

    try:
        # Use the overlay's execute method with proper context
        from forge.overlays.base import OverlayContext

        context = OverlayContext(
            overlay_id=knowledge_overlay.id,
            overlay_name=knowledge_overlay.NAME,
            execution_id=generate_id(),
            triggered_by="api.graph.query",
            correlation_id=generate_id(),
            user_id=user.id,
            trust_flame=user.trust_level.value
            if hasattr(user.trust_level, "value")
            else user.trust_level,
        )
        # Execute through the overlay's run method
        overlay_result = await knowledge_overlay.run(
            context,
            event=None,
            input_data={
                "question": request.question,
                "limit": request.limit,
                "debug": request.debug,
                "include_results": request.include_results,
            },
        )

        if not overlay_result.success:
            raise Exception(overlay_result.error or "Query failed")

        execution_time = (time.time() - start) * 1000

        # Extract results from overlay_result.data
        result_data = overlay_result.data or {}
        return KnowledgeQueryResponse(
            question=request.question,
            answer=result_data.get("answer"),
            result_count=result_data.get("result_count", 0),
            execution_time_ms=execution_time,
            complexity=result_data.get("complexity", "unknown"),
            explanation=result_data.get("explanation") if request.debug else None,
            cypher=result_data.get("cypher") if request.debug else None,
            results=result_data.get("results") if request.include_results else None,
        )
    except (ValueError, TypeError, KeyError, RuntimeError, OSError):
        execution_time = (time.time() - start) * 1000
        return KnowledgeQueryResponse(
            question=request.question,
            # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details to client
            answer="Error processing query. Please try rephrasing your question.",
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
            "DERIVED_FROM",
            "RELATED_TO",
            "SUPPORTS",
            "CONTRADICTS",
            "ELABORATES",
            "SUPERSEDES",
            "REFERENCES",
            "OWNS",
            "VOTED",
        ],
        "queryable_properties": {
            "Capsule": ["id", "title", "content", "type", "trust_level", "created_at", "tags"],
            "User": ["id", "username", "trust_flame", "role"],
            "Proposal": ["id", "title", "status", "proposer_id"],
        },
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

    # get_version_history returns VersionHistory, access .versions for the list
    version_history = await temporal_repo.get_version_history(capsule_id=capsule_id, limit=limit)
    return [
        VersionResponse(
            # CapsuleVersion uses 'id' not 'version_id'
            version_id=v.id,
            capsule_id=v.capsule_id,
            version_number=v.version_number,
            # snapshot_type is SnapshotType enum, access .value
            snapshot_type=v.snapshot_type.value
            if hasattr(v.snapshot_type, "value")
            else str(v.snapshot_type),
            # change_type is ChangeType enum, access .value
            change_type=v.change_type.value
            if hasattr(v.change_type, "value")
            else str(v.change_type),
            created_by=v.created_by,
            created_at=v.created_at.isoformat() if v.created_at else "",
            content=None,  # Don't include full content in list
        )
        for v in version_history.versions
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
    # No get_version method exists - query directly through client
    query = """
    MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion {id: $version_id})
    RETURN v {.*} AS version
    """
    result = await temporal_repo.client.execute_single(
        query, {"capsule_id": capsule_id, "version_id": version_id}
    )

    if not result or not result.get("version"):
        raise HTTPException(status_code=404, detail="Version not found")

    v = result["version"]
    return VersionResponse(
        version_id=v.get("id", version_id),
        capsule_id=v.get("capsule_id", capsule_id),
        version_number=v.get("version_number", "1.0.0"),
        snapshot_type=v.get("snapshot_type", "full"),
        change_type=v.get("change_type", "update"),
        created_by=v.get("created_by"),
        created_at=v.get("created_at", ""),
        # CapsuleVersion uses content_snapshot, not content
        content=v.get("content_snapshot"),
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
    try:
        target_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
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
            # CapsuleVersion uses 'id' not 'version_id', and 'content_snapshot' not 'content'
            "version_id": version.id,
            "version_number": version.version_number,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "content": version.content_snapshot,
        },
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
    # diff_versions returns a VersionComparison object that already contains version info
    try:
        comparison = await temporal_repo.diff_versions(version_a, version_b)
    except ValueError:
        # SECURITY FIX (Audit 7 - Session 3): Do not leak internal error details to client
        raise HTTPException(status_code=404, detail="Version not found")

    # Verify capsule_id matches
    if comparison.capsule_id != capsule_id:
        raise HTTPException(status_code=404, detail="Version not found for this capsule")

    return {
        "version_a": {
            "version_id": comparison.version_a_id,
            "version_number": comparison.version_a_number,
            "created_at": None,  # VersionComparison doesn't have created_at
        },
        "version_b": {
            "version_id": comparison.version_b_id,
            "version_number": comparison.version_b_number,
            "created_at": None,  # VersionComparison doesn't have created_at
        },
        "diff": {
            # VersionComparison.diff is a VersionDiff object
            "added_lines": comparison.diff.added_lines,
            "removed_lines": comparison.diff.removed_lines,
            "modified_sections": comparison.diff.modified_sections,
            "summary": comparison.diff.summary,
        },
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
    # Validate entity type
    if entity_type not in ["User", "Capsule"]:
        raise HTTPException(status_code=400, detail="entity_type must be 'User' or 'Capsule'")

    # Parse dates or use defaults
    try:
        start_dt = (
            datetime.fromisoformat(start.replace("Z", "+00:00"))
            if start
            else (datetime.now(UTC) - timedelta(days=30))
        )
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else datetime.now(UTC)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    timeline = await temporal_repo.get_trust_timeline(
        entity_id=entity_id,
        entity_type=entity_type,
        start=start_dt,
        end=end_dt,
    )

    # TrustTimeline object has snapshots list, not the object itself
    trust_values = [s.trust_value for s in timeline.snapshots]

    return TrustTimelineResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        snapshot_count=len(timeline.snapshots),
        timeline=[
            TrustSnapshotResponse(
                trust_value=s.trust_value,
                # TrustSnapshot uses created_at from TimestampMixin, not timestamp
                timestamp=s.created_at.isoformat() if s.created_at else "",
                # change_type is TrustChangeType enum, access .value
                change_type=s.change_type.value
                if hasattr(s.change_type, "value")
                else str(s.change_type),
                reason=s.reason,
            )
            for s in timeline.snapshots
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
            "avg_degree": metrics.avg_degree if hasattr(metrics, "avg_degree") else 0.0,
            "connected_components": metrics.connected_components,
            "nodes_by_type": metrics.nodes_by_type,
            "edges_by_type": metrics.edges_by_type,
        },
        created_by=user.id,
    )

    return {
        "snapshot_id": snapshot.id,
        "created_at": snapshot.created_at.isoformat()
        if snapshot.created_at
        else datetime.now(UTC).isoformat(),
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
    valid_types = {
        "SUPPORTS",
        "CONTRADICTS",
        "ELABORATES",
        "SUPERSEDES",
        "REFERENCES",
        "RELATED_TO",
    }
    if request.relationship_type.upper() not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Invalid relationship type. Must be one of: {valid_types}"
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
    await event_system.publish(
        event_type=EventType.SEMANTIC_EDGE_CREATED,
        payload={
            "edge_id": edge.id,
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "relationship_type": edge.relationship_type.value,
            "confidence": edge.confidence,
            "bidirectional": edge.bidirectional,
            "created_by": user.id,
        },
        source="api.graph",
        correlation_id=correlation_id,
        priority=EventPriority.NORMAL,
    )

    # Audit log
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id=request.source_id,
        action="semantic_edge_created",
        details={
            "target_id": request.target_id,
            "relationship_type": request.relationship_type,
            "bidirectional": request.bidirectional,
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
        bidirectional=edge.bidirectional,
    )


@router.get("/capsules/{capsule_id}/edges", response_model=list[SemanticEdgeResponse])
async def get_capsule_edges(
    capsule_id: str,
    user: ActiveUserDep,
    capsule_repo: CapsuleRepoDep,
    direction: str = Query(
        default="both",
        description="in, out, or both (for API compatibility, filtering done post-query)",
    ),
    relationship_type: str | None = Query(default=None, description="Filter by type"),
) -> list[SemanticEdgeResponse]:
    """
    Get semantic edges for a capsule.
    """
    # Verify capsule exists
    capsule = await capsule_repo.get_by_id(capsule_id)
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    # Convert string to SemanticRelationType enum list
    from forge.models.semantic_edges import SemanticRelationType as SRT

    rel_type_enums: list[SRT] | None = None
    if relationship_type:
        try:
            rel_type_enums = [SRT(relationship_type.upper())]
        except ValueError:
            pass

    # get_semantic_edges doesn't have direction parameter - filter in post-processing
    edges = await capsule_repo.get_semantic_edges(
        capsule_id=capsule_id,
        rel_types=rel_type_enums,
    )

    # Filter by direction if specified (the repository returns all edges)
    if direction == "in":
        edges = [e for e in edges if e.target_id == capsule_id]
    elif direction == "out":
        edges = [e for e in edges if e.source_id == capsule_id]

    return [
        SemanticEdgeResponse(
            id=e.id,
            source_id=e.source_id,
            target_id=e.target_id,
            relationship_type=e.relationship_type.value,
            properties=e.properties,
            created_by=e.created_by,
            created_at=e.created_at.isoformat(),
            bidirectional=e.bidirectional,
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

    # Convert string to SemanticRelationType enum list
    from forge.models.semantic_edges import SemanticRelationType

    rel_type_enums: list[SemanticRelationType] | None = None
    if relationship_type:
        try:
            rel_type_enums = [SemanticRelationType(relationship_type.upper())]
        except ValueError:
            # Invalid relationship type - let it be None to get all types
            pass

    neighbors = await capsule_repo.get_semantic_neighbors(
        capsule_id=capsule_id,
        rel_types=rel_type_enums,
        direction=direction,
        limit=limit,
    )

    # SemanticNeighbor has capsule_id, title, capsule_type, etc. (not a nested capsule object)
    return SemanticNeighborsResponse(
        capsule_id=capsule_id,
        neighbors=[
            {
                "capsule": {
                    "id": n.capsule_id,
                    "title": n.title,
                    "type": n.capsule_type,
                },
                "edge": {
                    "relationship_type": n.relationship_type.value
                    if hasattr(n.relationship_type, "value")
                    else str(n.relationship_type),
                    "direction": n.direction,
                    "confidence": n.confidence,
                },
            }
            for n in neighbors[:limit]
        ],
        total=len(neighbors),
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
                "type": c[0].type.value if hasattr(c[0].type, "value") else str(c[0].type),
            },
            capsule_b={
                "id": c[1].id,
                "title": c[1].title,
                "type": c[1].type.value if hasattr(c[1].type, "value") else str(c[1].type),
            },
            edge=SemanticEdgeResponse(
                id=c[2].id,
                source_id=c[2].source_id,
                target_id=c[2].target_id,
                relationship_type=c[2].relationship_type.value,
                properties=c[2].properties,
                created_by=c[2].created_by,
                created_at=c[2].created_at.isoformat(),
                bidirectional=c[2].bidirectional,
            ),
            severity=c[2].properties.get("severity"),
        )
        for c in contradictions
    ]


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_semantic_edge(
    edge_id: str,
    user: StandardUserDep,
    capsule_repo: CapsuleRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> None:
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
        raise HTTPException(status_code=403, detail="Only the edge creator can delete this edge")

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
                # size is a property computed from capsule_ids
                "size": c.size,
                "capsule_ids": c.capsule_ids,
                # ContradictionCluster uses edges list, derive count
                "edge_count": len(c.edges),
                "overall_severity": c.overall_severity.value
                if hasattr(c.overall_severity, "value")
                else str(c.overall_severity),
                "resolution_status": c.resolution_status.value
                if hasattr(c.resolution_status, "value")
                else str(c.resolution_status),
            }
            for c in clusters
        ],
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
    # Use get_by_name which returns a list
    graph_overlays = overlay_manager.get_by_name("graph_algorithms")
    graph_overlay = graph_overlays[0] if graph_overlays else None
    if graph_overlay and hasattr(graph_overlay, "clear_cache"):
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
    # SECURITY FIX (Audit 7 - Session 3): Add upper bound to offset to prevent abuse
    offset: int = Query(default=0, ge=0, le=10000),
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

    results = await capsule_repo.client.execute(query, {"limit": limit, "offset": offset})

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
            edge.target_id if resolution.winning_capsule_id == edge.source_id else edge.source_id
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
        "by_severity": {r.get("severity", "medium"): r.get("count", 0) for r in severity_results},
    }
