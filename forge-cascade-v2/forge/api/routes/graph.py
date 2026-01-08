"""
Forge Cascade V2 - Graph Extension Routes

Provides endpoints for:
- Graph algorithms (PageRank, centrality, community detection)
- Natural language knowledge queries
- Temporal operations (versions, trust timeline)
- Semantic edge management
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    ActiveUserDep,
    StandardUserDep,
    TrustedUserDep,
    PaginationDep,
    CorrelationIdDep,
    CapsuleRepoDep,
    AuditRepoDep,
)
from forge.models.base import TrustLevel

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
# Graph Algorithm Endpoints
# =============================================================================

@router.post("/algorithms/pagerank", response_model=list[NodeRankingResponse])
async def compute_pagerank(
    request: PageRankRequest,
    user: ActiveUserDep,
) -> list[NodeRankingResponse]:
    """
    Compute PageRank scores for nodes in the graph.

    PageRank measures the importance/influence of nodes based on
    their connections. Useful for identifying key capsules or users.
    """
    # This would be wired to the graph algorithms overlay
    # For now, return placeholder until wiring is complete
    return []


@router.post("/algorithms/centrality", response_model=list[NodeRankingResponse])
async def compute_centrality(
    request: CentralityRequest,
    user: ActiveUserDep,
) -> list[NodeRankingResponse]:
    """
    Compute centrality metrics for nodes.

    Types:
    - degree: Number of connections
    - betweenness: Bridge nodes between communities
    - closeness: Average distance to all other nodes
    """
    return []


@router.post("/algorithms/communities", response_model=list[CommunityResponse])
async def detect_communities(
    request: CommunityDetectionRequest,
    user: ActiveUserDep,
) -> list[CommunityResponse]:
    """
    Detect communities in the knowledge graph.

    Uses Louvain or label propagation algorithm to find
    clusters of closely related capsules.
    """
    return []


@router.post("/algorithms/trust-transitivity")
async def compute_trust_transitivity(
    request: TrustTransitivityRequest,
    user: ActiveUserDep,
) -> dict[str, Any]:
    """
    Compute transitive trust between two nodes.

    Calculates trust through graph paths, with decay
    over distance.
    """
    return {
        "source_id": request.source_id,
        "target_id": request.target_id,
        "trust_score": 0.0,
        "path_count": 0,
        "best_path": [],
        "best_path_length": 0
    }


@router.get("/metrics", response_model=GraphMetricsResponse)
async def get_graph_metrics(
    user: ActiveUserDep,
) -> GraphMetricsResponse:
    """
    Get overall graph statistics and metrics.
    """
    return GraphMetricsResponse(
        total_nodes=0,
        total_edges=0,
        density=0.0,
        avg_clustering=0.0,
        connected_components=0,
        diameter=None,
        node_distribution={},
        edge_distribution={}
    )


# =============================================================================
# Knowledge Query Endpoints
# =============================================================================

@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(
    request: KnowledgeQueryRequest,
    user: ActiveUserDep,
) -> KnowledgeQueryResponse:
    """
    Query the knowledge graph using natural language.

    Examples:
    - "What influenced the rate limiting decision?"
    - "Who contributed most to security knowledge?"
    - "Find contradictions in authentication docs"
    """
    return KnowledgeQueryResponse(
        question=request.question,
        answer="Query service not yet configured",
        result_count=0,
        execution_time_ms=0.0,
        complexity="unknown"
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
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VersionResponse]:
    """
    Get version history for a capsule.
    """
    return []


@router.get("/capsules/{capsule_id}/versions/{version_id}", response_model=VersionResponse)
async def get_capsule_version(
    capsule_id: str,
    version_id: str,
    user: ActiveUserDep,
) -> VersionResponse:
    """
    Get a specific version with full content.
    """
    raise HTTPException(status_code=404, detail="Version not found")


@router.get("/capsules/{capsule_id}/at-time")
async def get_capsule_at_time(
    capsule_id: str,
    timestamp: str = Query(..., description="ISO timestamp"),
    user: ActiveUserDep = None,
) -> dict[str, Any]:
    """
    Get capsule state at a specific point in time.
    """
    return {
        "capsule_id": capsule_id,
        "timestamp": timestamp,
        "found": False
    }


@router.get("/capsules/{capsule_id}/versions/diff")
async def diff_capsule_versions(
    capsule_id: str,
    version_a: str = Query(..., description="First version ID"),
    version_b: str = Query(..., description="Second version ID"),
    user: ActiveUserDep = None,
) -> dict[str, Any]:
    """
    Compare two versions of a capsule.
    """
    return {
        "version_a": version_a,
        "version_b": version_b,
        "diff": {}
    }


# =============================================================================
# Temporal Endpoints - Trust Timeline
# =============================================================================

@router.get("/trust/{entity_type}/{entity_id}/timeline", response_model=TrustTimelineResponse)
async def get_trust_timeline(
    entity_type: str,
    entity_id: str,
    user: ActiveUserDep,
    start: str | None = Query(default=None, description="Start date ISO"),
    end: str | None = Query(default=None, description="End date ISO"),
) -> TrustTimelineResponse:
    """
    Get trust evolution timeline for a user or capsule.

    entity_type: "User" or "Capsule"
    """
    return TrustTimelineResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        start=start or "",
        end=end or "",
        snapshot_count=0,
        timeline=[],
        trust_min=None,
        trust_max=None,
        trust_current=None
    )


@router.post("/snapshots/graph")
async def create_graph_snapshot(
    user: TrustedUserDep,
) -> dict[str, Any]:
    """
    Create a point-in-time snapshot of the graph.

    Requires TRUSTED trust level.
    """
    return {
        "snapshot_id": "",
        "created_at": datetime.utcnow().isoformat(),
        "metrics": {}
    }


@router.get("/snapshots/graph/latest")
async def get_latest_graph_snapshot(
    user: ActiveUserDep,
) -> dict[str, Any]:
    """
    Get the most recent graph snapshot.
    """
    return {
        "snapshot_id": None,
        "found": False
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

    # Create edge
    edge = await capsule_repo.create_semantic_edge(
        source_id=request.source_id,
        target_id=request.target_id,
        rel_type=request.relationship_type.upper(),
        properties=request.properties,
        created_by=user.id,
        bidirectional=request.bidirectional
    )

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
) -> dict[str, Any]:
    """
    Refresh all cached graph analysis results.

    Requires TRUSTED trust level.
    """
    return {
        "refreshed": True,
        "refreshed_at": datetime.utcnow().isoformat()
    }
