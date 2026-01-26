"""
Graph Analysis Models

Data structures for graph algorithm results including PageRank,
centrality metrics, community detection, and trust analysis.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from forge.models.base import ForgeModel


class GraphBackend(str, Enum):
    """Available backends for graph algorithms."""

    GDS = "gds"  # Neo4j Graph Data Science
    CYPHER = "cypher"  # Pure Cypher queries
    NETWORKX = "networkx"  # In-memory NetworkX


class AlgorithmType(str, Enum):
    """Types of graph algorithms."""

    PAGERANK = "pagerank"
    BETWEENNESS_CENTRALITY = "betweenness_centrality"
    CLOSENESS_CENTRALITY = "closeness_centrality"
    DEGREE_CENTRALITY = "degree_centrality"
    EIGENVECTOR_CENTRALITY = "eigenvector_centrality"
    COMMUNITY_LOUVAIN = "community_louvain"
    COMMUNITY_LABEL_PROPAGATION = "community_label_propagation"
    TRUST_TRANSITIVITY = "trust_transitivity"
    SHORTEST_PATH = "shortest_path"


# ═══════════════════════════════════════════════════════════════
# NODE RANKING RESULTS
# ═══════════════════════════════════════════════════════════════


class NodeRanking(ForgeModel):
    """
    A ranked node from a graph algorithm.

    Used for PageRank, centrality measures, and other
    node-scoring algorithms.
    """

    node_id: str = Field(description="Unique identifier of the node")
    node_type: str = Field(description="Node label (Capsule, User, etc.)")
    score: float = Field(ge=0.0, description="Algorithm-computed score")
    rank: int = Field(ge=1, description="Position in ranking (1 = highest)")

    # Optional context
    title: str | None = Field(default=None, description="Node title if available")
    trust_level: int | None = Field(default=None, description="Trust level if applicable")
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeRankingResult(ForgeModel):
    """Complete result from a ranking algorithm."""

    algorithm: AlgorithmType
    backend_used: GraphBackend
    rankings: list[NodeRanking] = Field(default_factory=list)
    total_nodes: int = Field(ge=0)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    computation_time_ms: float = Field(ge=0.0)
    parameters: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# COMMUNITY DETECTION
# ═══════════════════════════════════════════════════════════════


class CommunityMember(ForgeModel):
    """A node within a community."""

    node_id: str
    node_type: str
    centrality_in_community: float = Field(
        default=0.0,
        ge=0.0,
        description="How central this node is within its community",
    )


class Community(ForgeModel):
    """
    A detected community (cluster) of nodes.

    Communities represent groups of closely connected nodes,
    often indicating knowledge domains or user groups.
    """

    community_id: int = Field(ge=0, description="Unique community identifier")
    members: list[CommunityMember] = Field(default_factory=list)
    size: int = Field(ge=0, description="Number of nodes in community")
    density: float = Field(
        ge=0.0,
        le=1.0,
        description="Internal edge density (0-1)",
    )
    modularity_contribution: float = Field(
        default=0.0,
        description="Contribution to overall modularity score",
    )

    # Characterization
    dominant_type: str | None = Field(
        default=None,
        description="Most common node type in community",
    )
    dominant_tags: list[str] = Field(
        default_factory=list,
        description="Most common tags in community",
    )
    avg_trust_level: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Average trust level of community members",
    )


class CommunityDetectionResult(ForgeModel):
    """Complete result from community detection."""

    algorithm: AlgorithmType
    backend_used: GraphBackend
    communities: list[Community] = Field(default_factory=list)
    total_communities: int = Field(ge=0)
    modularity: float = Field(
        ge=-1.0,
        le=1.0,
        description="Overall modularity score",
    )
    coverage: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of nodes assigned to communities",
    )
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    computation_time_ms: float = Field(ge=0.0)
    parameters: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# TRUST ANALYSIS
# ═══════════════════════════════════════════════════════════════


class TrustPath(ForgeModel):
    """A path through the graph used for trust computation."""

    path_nodes: list[str] = Field(description="Ordered list of node IDs")
    path_length: int = Field(ge=1)
    trust_at_each_hop: list[float] = Field(
        default_factory=list,
        description="Trust value at each hop in the path",
    )
    cumulative_trust: float = Field(
        ge=0.0,
        le=1.0,
        description="Final trust after all decay applied",
    )
    decay_applied: float = Field(
        ge=0.0,
        le=1.0,
        description="Total decay factor applied",
    )


class TrustTransitivityResult(ForgeModel):
    """
    Result of computing transitive trust between two nodes.

    Finds all paths and computes trust propagation with decay.
    """

    source_id: str
    target_id: str
    transitive_trust: float = Field(
        ge=0.0,
        le=1.0,
        description="Computed trust score",
    )
    paths_found: int = Field(ge=0, description="Number of connecting paths")
    best_path: TrustPath | None = Field(
        default=None,
        description="Highest trust path",
    )
    all_paths: list[TrustPath] = Field(
        default_factory=list,
        description="All discovered paths",
    )
    max_hops_searched: int = Field(ge=1)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrustInfluence(ForgeModel):
    """A node's influence on trust propagation."""

    node_id: str
    node_type: str
    influence_score: float = Field(
        ge=0.0,
        description="How much this node affects trust in the network",
    )
    downstream_reach: int = Field(
        ge=0,
        description="Number of nodes influenced downstream",
    )
    upstream_sources: int = Field(
        ge=0,
        description="Number of nodes that influence this one",
    )
    trust_amplification: float = Field(
        default=1.0,
        description="Trust multiplier effect (>1 = amplifies, <1 = diminishes)",
    )


# ═══════════════════════════════════════════════════════════════
# GRAPH METRICS
# ═══════════════════════════════════════════════════════════════


class GraphMetrics(ForgeModel):
    """
    Comprehensive metrics about the knowledge graph.

    Provides overall graph statistics and health indicators.
    """

    # Size metrics
    total_nodes: int = Field(ge=0)
    total_edges: int = Field(ge=0)
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_type: dict[str, int] = Field(default_factory=dict)

    # Structure metrics
    density: float = Field(
        ge=0.0,
        le=1.0,
        description="Graph density (edges / possible edges)",
    )
    avg_degree: float = Field(ge=0.0, description="Average node degree")
    max_degree: int = Field(ge=0, description="Maximum node degree")
    avg_clustering: float = Field(
        ge=0.0,
        le=1.0,
        description="Average clustering coefficient",
    )

    # Connectivity metrics
    connected_components: int = Field(ge=0)
    largest_component_size: int = Field(ge=0)
    diameter: int | None = Field(
        default=None,
        ge=0,
        description="Graph diameter (None if disconnected)",
    )
    avg_path_length: float | None = Field(
        default=None,
        ge=0.0,
        description="Average shortest path length",
    )

    # Trust metrics
    avg_trust_level: float = Field(ge=0.0, le=100.0)
    trust_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of nodes by trust level bucket",
    )

    # Temporal
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    computation_time_ms: float = Field(ge=0.0)


# ═══════════════════════════════════════════════════════════════
# ALGORITHM REQUESTS
# ═══════════════════════════════════════════════════════════════


class PageRankRequest(ForgeModel):
    """Parameters for PageRank computation."""

    node_label: str = Field(default="Capsule", description="Node type to rank")
    relationship_type: str = Field(
        default="DERIVED_FROM",
        description="Relationship to follow",
    )
    damping_factor: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="PageRank damping factor",
    )
    max_iterations: int = Field(default=20, ge=1, le=100)
    tolerance: float = Field(default=1e-7, gt=0.0)
    # SECURITY FIX (Audit 5): Reduce pagination limit from 1000 to 100
    limit: int = Field(default=100, ge=1, le=100, description="Max results")
    include_trust_weighting: bool = Field(
        default=True,
        description="Weight edges by trust level",
    )


class CentralityRequest(ForgeModel):
    """Parameters for centrality computation."""

    algorithm: AlgorithmType = Field(default=AlgorithmType.BETWEENNESS_CENTRALITY)
    node_label: str = Field(default="Capsule")
    relationship_type: str | None = Field(default=None, description="All if None")
    normalized: bool = Field(default=True)
    # SECURITY FIX (Audit 5): Reduce pagination limit from 1000 to 100
    limit: int = Field(default=100, ge=1, le=100)


class CommunityDetectionRequest(ForgeModel):
    """Parameters for community detection."""

    algorithm: AlgorithmType = Field(default=AlgorithmType.COMMUNITY_LOUVAIN)
    node_label: str | None = Field(default=None, description="All if None")
    relationship_type: str | None = Field(default=None)
    min_community_size: int = Field(default=2, ge=1)
    max_communities: int = Field(default=100, ge=1)
    include_characterization: bool = Field(
        default=True,
        description="Compute community characteristics",
    )


class TrustTransitivityRequest(ForgeModel):
    """Parameters for trust transitivity computation."""

    source_id: str = Field(description="Starting node")
    target_id: str = Field(description="Target node")
    max_hops: int = Field(default=5, ge=1, le=10)
    decay_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Trust decay per hop",
    )
    relationship_types: list[str] = Field(
        default_factory=lambda: ["DERIVED_FROM", "RELATED_TO"],
        description="Relationships to traverse",
    )
    return_all_paths: bool = Field(default=False)


class NodeSimilarityRequest(ForgeModel):
    """Parameters for node similarity computation using GDS."""

    node_label: str = Field(default="Capsule")
    relationship_type: str = Field(default="DERIVED_FROM")
    similarity_metric: str = Field(
        default="jaccard",
        description="jaccard, overlap, or cosine",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Similar nodes per source")
    similarity_cutoff: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold",
    )
    source_node_id: str | None = Field(
        default=None,
        description="Specific node to find similar nodes for (None = all)",
    )


class SimilarNode(ForgeModel):
    """A similar node with similarity score."""

    node_id: str
    node_type: str
    title: str | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)
    shared_neighbors: int = Field(default=0, ge=0)


class NodeSimilarityResult(ForgeModel):
    """Result of node similarity computation."""

    source_id: str | None = Field(default=None, description="Source node if specific")
    similar_nodes: list[SimilarNode] = Field(default_factory=list)
    similarity_metric: str
    top_k: int
    computation_time_ms: float = Field(ge=0.0)
    backend_used: GraphBackend = Field(default=GraphBackend.CYPHER)


class ShortestPathRequest(ForgeModel):
    """Parameters for shortest path computation."""

    source_id: str = Field(description="Starting node")
    target_id: str = Field(description="Target node")
    relationship_types: list[str] = Field(
        default_factory=lambda: ["DERIVED_FROM", "RELATED_TO", "SUPPORTS"],
        description="Relationships to traverse",
    )
    max_depth: int = Field(default=10, ge=1, le=50)
    weighted: bool = Field(
        default=False,
        description="Use trust-weighted path finding",
    )


class PathNode(ForgeModel):
    """A node in a path."""

    node_id: str
    node_type: str
    title: str | None = None
    trust_level: int | None = None


class ShortestPathResult(ForgeModel):
    """Result of shortest path computation."""

    source_id: str
    target_id: str
    path_found: bool = Field(default=False)
    path_length: int = Field(default=0, ge=0)
    path_nodes: list[PathNode] = Field(default_factory=list)
    path_relationships: list[str] = Field(
        default_factory=list,
        description="Relationship types along the path",
    )
    total_trust: float | None = Field(
        default=None,
        description="Product of trust levels along path (if weighted)",
    )
    computation_time_ms: float = Field(ge=0.0)
    backend_used: GraphBackend = Field(default=GraphBackend.CYPHER)


# ═══════════════════════════════════════════════════════════════
# ALGORITHM PROVIDER CONFIG
# ═══════════════════════════════════════════════════════════════


class GraphAlgorithmConfig(ForgeModel):
    """Configuration for the graph algorithm provider."""

    preferred_backend: GraphBackend = Field(
        default=GraphBackend.GDS,
        description="Preferred backend (falls back if unavailable)",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        description="How long to cache algorithm results",
    )
    max_nodes_for_networkx: int = Field(
        default=10000,
        ge=100,
        description="Max nodes to load into NetworkX",
    )
    gds_graph_name: str = Field(
        default="forge_graph",
        description="Name for GDS graph projection",
    )
    enable_caching: bool = Field(default=True)
