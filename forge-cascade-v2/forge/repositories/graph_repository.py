"""
Graph Algorithm Repository

Provides graph algorithm computations with a layered backend approach:
1. Neo4j GDS (Graph Data Science) - Best performance
2. Pure Cypher - Works everywhere
3. NetworkX - Full algorithm support, in-memory fallback
"""

import re
from datetime import UTC, datetime
from typing import Any

import structlog

# SECURITY FIX: Pattern for validating Neo4j identifiers (labels, relationship types, graph names)
# Only allows alphanumeric characters and underscores to prevent Cypher injection
_SAFE_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


def validate_neo4j_identifier(value: str, identifier_type: str = "identifier") -> str:
    """
    Validate a Neo4j identifier (label, relationship type, or graph name).

    SECURITY: Prevents Cypher/GDS injection attacks by ensuring identifiers
    only contain safe characters (alphanumeric + underscore, starting with letter).

    Args:
        value: The identifier value to validate
        identifier_type: Description for error messages (e.g., "node_label", "relationship_type")

    Returns:
        The validated value

    Raises:
        ValueError: If the identifier contains unsafe characters
    """
    if not value:
        raise ValueError(f"{identifier_type} cannot be empty")

    if len(value) > 128:
        raise ValueError(f"{identifier_type} exceeds maximum length of 128 characters")

    if not _SAFE_IDENTIFIER_PATTERN.match(value):
        raise ValueError(
            f"Invalid {identifier_type}: '{value}'. "
            f"Must start with a letter and contain only alphanumeric characters and underscores."
        )

    return value


def validate_relationship_pattern(rel_types: list[str]) -> str:
    """
    Validate and join multiple relationship types into a safe pattern.

    SECURITY: Validates each type before joining with | for Cypher patterns.

    Args:
        rel_types: List of relationship type names

    Returns:
        Safe pattern string like "TYPE1|TYPE2|TYPE3"

    Raises:
        ValueError: If any relationship type is invalid
    """
    if not rel_types:
        raise ValueError("At least one relationship type must be provided")

    validated = [validate_neo4j_identifier(rt, "relationship_type") for rt in rel_types]
    return "|".join(validated)

from forge.database.client import Neo4jClient
from forge.models.graph_analysis import (
    AlgorithmType,
    CentralityRequest,
    Community,
    CommunityDetectionRequest,
    CommunityDetectionResult,
    CommunityMember,
    GraphAlgorithmConfig,
    GraphBackend,
    GraphMetrics,
    NodeRanking,
    NodeRankingResult,
    NodeSimilarityRequest,
    NodeSimilarityResult,
    PageRankRequest,
    PathNode,
    ShortestPathRequest,
    ShortestPathResult,
    SimilarNode,
    TrustInfluence,
    TrustPath,
    TrustTransitivityRequest,
    TrustTransitivityResult,
)

logger = structlog.get_logger(__name__)


class GraphAlgorithmProvider:
    """
    Provides graph algorithms with automatic backend selection.

    Tries backends in order of preference:
    1. Neo4j GDS (if available)
    2. Pure Cypher (always available)
    3. NetworkX (for algorithms not available in Cypher)
    """

    def __init__(
        self,
        client: Neo4jClient,
        config: GraphAlgorithmConfig | None = None,
    ):
        self.client = client
        self.config = config or GraphAlgorithmConfig()
        self._gds_available: bool | None = None
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def detect_backend(self) -> GraphBackend:
        """Detect the best available backend."""
        if self._gds_available is None:
            self._gds_available = await self._check_gds_available()

        if self._gds_available:
            return GraphBackend.GDS
        return GraphBackend.CYPHER

    async def _check_gds_available(self) -> bool:
        """Check if Neo4j GDS plugin is available."""
        try:
            result = await self.client.execute_single(
                "RETURN gds.version() AS version"
            )
            if result and result.get("version"):
                self.logger.info(
                    "GDS plugin detected",
                    version=result["version"],
                )
                return True
        except (RuntimeError, OSError, ValueError):
            self.logger.debug("GDS plugin not available, using Cypher fallback")
        return False

    def _get_cached(self, cache_key: str) -> Any | None:
        """Get cached result if still valid."""
        if not self.config.enable_caching:
            return None

        if cache_key in self._cache:
            value, cached_at = self._cache[cache_key]
            age = (datetime.now(UTC) - cached_at).total_seconds()
            if age < self.config.cache_ttl_seconds:
                return value
            del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, value: Any) -> None:
        """Cache a result."""
        if self.config.enable_caching:
            self._cache[cache_key] = (value, datetime.now(UTC))

    # ═══════════════════════════════════════════════════════════════
    # PAGERANK
    # ═══════════════════════════════════════════════════════════════

    async def compute_pagerank(
        self,
        request: PageRankRequest | None = None,
    ) -> NodeRankingResult:
        """
        Compute PageRank for nodes.

        Uses GDS if available, falls back to iterative Cypher implementation.
        """
        request = request or PageRankRequest()
        cache_key = f"pagerank:{request.node_label}:{request.relationship_type}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            cached_result: NodeRankingResult = cached
            return cached_result

        start_time = datetime.now(UTC)
        backend = await self.detect_backend()

        if backend == GraphBackend.GDS:
            result = await self._gds_pagerank(request)
        else:
            result = await self._cypher_pagerank(request)

        result.backend_used = backend
        result.computation_time_ms = (
            datetime.now(UTC) - start_time
        ).total_seconds() * 1000

        self._set_cached(cache_key, result)
        return result

    async def _gds_pagerank(self, request: PageRankRequest) -> NodeRankingResult:
        """Compute PageRank using Neo4j GDS."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        relationship_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")
        graph_name = f"pagerank_{node_label}_{relationship_type}"

        try:
            # Project the graph
            await self.client.execute(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    '{node_label}',
                    '{relationship_type}'
                )
                """
            )

            # Run PageRank
            results = await self.client.execute(
                f"""
                CALL gds.pageRank.stream('{graph_name}', {{
                    maxIterations: $max_iterations,
                    dampingFactor: $damping_factor,
                    tolerance: $tolerance
                }})
                YIELD nodeId, score
                WITH nodeId, score
                ORDER BY score DESC
                LIMIT $limit
                MATCH (n:{node_label}) WHERE id(n) = nodeId
                RETURN n.id AS node_id, n.title AS title, n.trust_level AS trust_level, score
                """,
                {
                    "max_iterations": request.max_iterations,
                    "damping_factor": request.damping_factor,
                    "tolerance": request.tolerance,
                    "limit": request.limit,
                },
            )

            rankings = [
                NodeRanking(
                    node_id=r["node_id"],
                    node_type=node_label,
                    score=r["score"],
                    rank=i + 1,
                    title=r.get("title"),
                    trust_level=r.get("trust_level"),
                )
                for i, r in enumerate(results)
            ]

            # Get total node count
            count_result = await self.client.execute_single(
                f"MATCH (n:{node_label}) RETURN count(n) AS count"
            )
            total_nodes = count_result.get("count", 0) if count_result else 0

            return NodeRankingResult(
                algorithm=AlgorithmType.PAGERANK,
                backend_used=GraphBackend.GDS,
                rankings=rankings,
                total_nodes=total_nodes,
                computation_time_ms=0.0,
                parameters={
                    "damping_factor": request.damping_factor,
                    "max_iterations": request.max_iterations,
                },
            )

        finally:
            # Clean up projected graph
            try:
                await self.client.execute(
                    f"CALL gds.graph.drop('{graph_name}', false)"
                )
            except (RuntimeError, OSError, ValueError):
                pass  # Best-effort GDS graph cleanup

    async def _cypher_pagerank(self, request: PageRankRequest) -> NodeRankingResult:
        """
        Compute PageRank using iterative Cypher.

        This is a simplified approximation suitable for smaller graphs.
        """
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        relationship_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")

        # Get all nodes with their relationships
        results = await self.client.execute(
            f"""
            MATCH (n:{node_label})
            OPTIONAL MATCH (n)<-[:{relationship_type}]-(incoming)
            OPTIONAL MATCH (n)-[:{relationship_type}]->(outgoing)
            WITH n,
                 count(DISTINCT incoming) AS in_degree,
                 count(DISTINCT outgoing) AS out_degree
            // Simple degree-based PageRank approximation
            WITH n, in_degree, out_degree,
                 (in_degree * 1.0 + 1) / (out_degree + 1) AS raw_score
            WITH n, raw_score,
                 (raw_score * $damping + (1 - $damping)) AS score
            ORDER BY score DESC
            LIMIT $limit
            RETURN n.id AS node_id,
                   n.title AS title,
                   n.trust_level AS trust_level,
                   score
            """,
            {
                "damping": request.damping_factor,
                "limit": request.limit,
            },
        )

        rankings = [
            NodeRanking(
                node_id=r["node_id"],
                node_type=node_label,
                score=r["score"],
                rank=i + 1,
                title=r.get("title"),
                trust_level=r.get("trust_level"),
            )
            for i, r in enumerate(results)
        ]

        count_result = await self.client.execute_single(
            f"MATCH (n:{node_label}) RETURN count(n) AS count"
        )
        total_nodes = count_result.get("count", 0) if count_result else 0

        return NodeRankingResult(
            algorithm=AlgorithmType.PAGERANK,
            backend_used=GraphBackend.CYPHER,
            rankings=rankings,
            total_nodes=total_nodes,
            computation_time_ms=0.0,
            parameters={
                "damping_factor": request.damping_factor,
                "note": "Cypher approximation based on in/out degree ratio",
            },
        )

    # ═══════════════════════════════════════════════════════════════
    # CENTRALITY
    # ═══════════════════════════════════════════════════════════════

    async def compute_centrality(
        self,
        request: CentralityRequest | None = None,
    ) -> NodeRankingResult:
        """Compute centrality measures for nodes."""
        request = request or CentralityRequest()
        cache_key = f"centrality:{request.algorithm}:{request.node_label}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            cached_result: NodeRankingResult = cached
            return cached_result

        start_time = datetime.now(UTC)
        backend = await self.detect_backend()

        if request.algorithm == AlgorithmType.DEGREE_CENTRALITY:
            result = await self._degree_centrality(request)
        elif backend == GraphBackend.GDS:
            result = await self._gds_centrality(request)
        else:
            result = await self._cypher_centrality(request)

        result.backend_used = backend
        result.computation_time_ms = (
            datetime.now(UTC) - start_time
        ).total_seconds() * 1000

        self._set_cached(cache_key, result)
        return result

    async def _degree_centrality(
        self,
        request: CentralityRequest,
    ) -> NodeRankingResult:
        """Compute degree centrality (works with pure Cypher)."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        rel_clause = ""
        if request.relationship_type:
            relationship_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")
            rel_clause = f":{relationship_type}"

        results = await self.client.execute(
            f"""
            MATCH (n:{node_label})
            OPTIONAL MATCH (n)-[r{rel_clause}]-()
            WITH n, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN n.id AS node_id,
                   n.title AS title,
                   n.trust_level AS trust_level,
                   degree AS score
            """,
            {"limit": request.limit},
        )

        # Normalize if requested
        max_score = max((r["score"] for r in results), default=1) or 1

        rankings = [
            NodeRanking(
                node_id=r["node_id"],
                node_type=node_label,
                score=r["score"] / max_score if request.normalized else r["score"],
                rank=i + 1,
                title=r.get("title"),
                trust_level=r.get("trust_level"),
            )
            for i, r in enumerate(results)
        ]

        count_result = await self.client.execute_single(
            f"MATCH (n:{node_label}) RETURN count(n) AS count"
        )

        return NodeRankingResult(
            algorithm=AlgorithmType.DEGREE_CENTRALITY,
            backend_used=GraphBackend.CYPHER,
            rankings=rankings,
            total_nodes=count_result.get("count", 0) if count_result else 0,
            computation_time_ms=0.0,
            parameters={"normalized": request.normalized},
        )

    async def _gds_centrality(self, request: CentralityRequest) -> NodeRankingResult:
        """Compute centrality using GDS."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        rel_type = "*"
        if request.relationship_type:
            rel_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")
        graph_name = f"centrality_{node_label}"

        algo_map = {
            AlgorithmType.BETWEENNESS_CENTRALITY: "gds.betweenness.stream",
            AlgorithmType.CLOSENESS_CENTRALITY: "gds.closeness.stream",
            AlgorithmType.EIGENVECTOR_CENTRALITY: "gds.eigenvector.stream",
        }

        algo = algo_map.get(request.algorithm, "gds.betweenness.stream")

        try:
            await self.client.execute(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    '{node_label}',
                    '{rel_type}'
                )
                """
            )

            results = await self.client.execute(
                f"""
                CALL {algo}('{graph_name}')
                YIELD nodeId, score
                WITH nodeId, score
                ORDER BY score DESC
                LIMIT $limit
                MATCH (n:{node_label}) WHERE id(n) = nodeId
                RETURN n.id AS node_id, n.title AS title, n.trust_level AS trust_level, score
                """,
                {"limit": request.limit},
            )

            rankings = [
                NodeRanking(
                    node_id=r["node_id"],
                    node_type=node_label,
                    score=r["score"],
                    rank=i + 1,
                    title=r.get("title"),
                    trust_level=r.get("trust_level"),
                )
                for i, r in enumerate(results)
            ]

            count_result = await self.client.execute_single(
                f"MATCH (n:{node_label}) RETURN count(n) AS count"
            )

            return NodeRankingResult(
                algorithm=request.algorithm,
                backend_used=GraphBackend.GDS,
                rankings=rankings,
                total_nodes=count_result.get("count", 0) if count_result else 0,
                computation_time_ms=0.0,
                parameters={},
            )

        finally:
            try:
                await self.client.execute(
                    f"CALL gds.graph.drop('{graph_name}', false)"
                )
            except (RuntimeError, OSError, ValueError):
                pass  # Best-effort GDS graph cleanup

    async def _cypher_centrality(
        self,
        request: CentralityRequest,
    ) -> NodeRankingResult:
        """Fallback centrality using degree (other algorithms need GDS/NetworkX)."""
        self.logger.warning(
            "Centrality algorithm not available without GDS, falling back to degree",
            requested=request.algorithm,
        )
        request.algorithm = AlgorithmType.DEGREE_CENTRALITY
        return await self._degree_centrality(request)

    # ═══════════════════════════════════════════════════════════════
    # COMMUNITY DETECTION
    # ═══════════════════════════════════════════════════════════════

    async def detect_communities(
        self,
        request: CommunityDetectionRequest | None = None,
    ) -> CommunityDetectionResult:
        """Detect communities in the graph."""
        request = request or CommunityDetectionRequest()
        cache_key = f"communities:{request.algorithm}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            cached_result: CommunityDetectionResult = cached
            return cached_result

        start_time = datetime.now(UTC)
        backend = await self.detect_backend()

        if backend == GraphBackend.GDS:
            result = await self._gds_communities(request)
        else:
            result = await self._cypher_communities(request)

        result.backend_used = backend
        result.computation_time_ms = (
            datetime.now(UTC) - start_time
        ).total_seconds() * 1000

        self._set_cached(cache_key, result)
        return result

    async def _gds_communities(
        self,
        request: CommunityDetectionRequest,
    ) -> CommunityDetectionResult:
        """Detect communities using GDS Louvain."""
        graph_name = "community_detection"
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label or "Capsule", "node_label")
        rel_type = validate_neo4j_identifier(request.relationship_type or "DERIVED_FROM", "relationship_type")

        try:
            await self.client.execute(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    '{node_label}',
                    {{
                        {rel_type}: {{
                            orientation: 'UNDIRECTED'
                        }}
                    }}
                )
                """
            )

            # Run Louvain
            results = await self.client.execute(
                f"""
                CALL gds.louvain.stream('{graph_name}')
                YIELD nodeId, communityId
                MATCH (n:{node_label}) WHERE id(n) = nodeId
                RETURN n.id AS node_id, n.type AS node_type, n.trust_level AS trust_level,
                       communityId AS community_id
                ORDER BY community_id
                """
            )

            # Group by community
            communities_map: dict[int, list[dict[str, Any]]] = {}
            for r in results:
                cid = r["community_id"]
                if cid not in communities_map:
                    communities_map[cid] = []
                communities_map[cid].append(r)

            communities = []
            for cid, members in list(communities_map.items())[: request.max_communities]:
                if len(members) < request.min_community_size:
                    continue

                # Compute community stats
                types = [m.get("node_type") for m in members if m.get("node_type")]
                trusts = [m.get("trust_level", 60) for m in members]

                dominant_type = max(set(types), key=types.count) if types else None
                avg_trust = sum(trusts) / len(trusts) if trusts else 60.0

                community = Community(
                    community_id=cid,
                    members=[
                        CommunityMember(
                            node_id=m["node_id"],
                            node_type=m.get("node_type", node_label),
                        )
                        for m in members
                    ],
                    size=len(members),
                    density=0.0,  # Would need additional query to compute
                    dominant_type=dominant_type,
                    avg_trust_level=avg_trust,
                )
                communities.append(community)

            return CommunityDetectionResult(
                algorithm=AlgorithmType.COMMUNITY_LOUVAIN,
                backend_used=GraphBackend.GDS,
                communities=communities,
                total_communities=len(communities),
                modularity=0.0,  # GDS doesn't return this directly in stream mode
                coverage=len(results) / max(len(results), 1),
                computation_time_ms=0.0,
                parameters={},
            )

        finally:
            try:
                await self.client.execute(
                    f"CALL gds.graph.drop('{graph_name}', false)"
                )
            except (RuntimeError, OSError, ValueError):
                pass  # Best-effort GDS graph cleanup

    async def _cypher_communities(
        self,
        request: CommunityDetectionRequest,
    ) -> CommunityDetectionResult:
        """
        Simple community detection using connected components.

        This is a fallback when GDS is not available.
        """
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label or "Capsule", "node_label")
        rel_type = validate_neo4j_identifier(request.relationship_type or "DERIVED_FROM", "relationship_type")

        # Find connected components using path traversal
        results = await self.client.execute(
            f"""
            MATCH (n:{node_label})
            WHERE NOT EXISTS {{ MATCH (n)-[:{rel_type}]->() }}
            // Start from root nodes
            OPTIONAL MATCH path = (n)<-[:{rel_type}*0..10]-(descendant:{node_label})
            WITH n AS root, collect(DISTINCT descendant) + [n] AS members
            WHERE size(members) >= $min_size
            RETURN id(root) AS community_id,
                   [m IN members | m.id] AS member_ids,
                   [m IN members | m.type] AS member_types,
                   [m IN members | m.trust_level] AS member_trusts
            LIMIT $max_communities
            """,
            {
                "min_size": request.min_community_size,
                "max_communities": request.max_communities,
            },
        )

        communities = []
        for i, r in enumerate(results):
            member_ids = r.get("member_ids", [])
            member_types = r.get("member_types", [])
            member_trusts = r.get("member_trusts", [])

            types = [t for t in member_types if t]
            trusts = [t for t in member_trusts if t is not None]

            dominant_type = max(set(types), key=types.count) if types else None
            avg_trust = sum(trusts) / len(trusts) if trusts else 60.0

            community = Community(
                community_id=i,
                members=[
                    CommunityMember(node_id=mid, node_type=node_label)
                    for mid in member_ids
                    if mid
                ],
                size=len(member_ids),
                density=0.0,
                dominant_type=dominant_type,
                avg_trust_level=avg_trust,
            )
            communities.append(community)

        return CommunityDetectionResult(
            algorithm=AlgorithmType.COMMUNITY_LABEL_PROPAGATION,
            backend_used=GraphBackend.CYPHER,
            communities=communities,
            total_communities=len(communities),
            modularity=0.0,
            coverage=1.0,
            computation_time_ms=0.0,
            parameters={"note": "Connected component approximation"},
        )

    # ═══════════════════════════════════════════════════════════════
    # TRUST TRANSITIVITY
    # ═══════════════════════════════════════════════════════════════

    async def compute_trust_transitivity(
        self,
        request: TrustTransitivityRequest,
    ) -> TrustTransitivityResult:
        """
        Compute transitive trust between two nodes.

        Finds all paths and computes trust with decay.
        """
        datetime.now(UTC)

        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        rel_types = validate_relationship_pattern(request.relationship_types)

        # SECURITY FIX: Validate max_hops is a safe integer value
        max_hops = max(1, min(int(request.max_hops), 20))  # Clamp between 1 and 20

        results = await self.client.execute(
            f"""
            MATCH path = (source:Capsule {{id: $source_id}})-[:{rel_types}*1..{max_hops}]-(target:Capsule {{id: $target_id}})
            WITH path,
                 [n IN nodes(path) | n.trust_level] AS trusts,
                 length(path) AS path_length
            // Compute trust decay along path
            WITH path, trusts, path_length,
                 reduce(trust = 1.0, i IN range(0, size(trusts)-2) |
                        trust * (1 - $decay) * (trusts[i+1] / 100.0)
                 ) AS cumulative_trust
            RETURN [n IN nodes(path) | n.id] AS path_nodes,
                   trusts,
                   path_length,
                   cumulative_trust
            ORDER BY cumulative_trust DESC
            LIMIT 10
            """,
            {
                "source_id": request.source_id,
                "target_id": request.target_id,
                "decay": request.decay_rate,
            },
        )

        paths = []
        for r in results:
            path = TrustPath(
                path_nodes=r.get("path_nodes", []),
                path_length=r.get("path_length", 0),
                trust_at_each_hop=[t / 100.0 for t in r.get("trusts", [])],
                cumulative_trust=r.get("cumulative_trust", 0.0),
                decay_applied=request.decay_rate * r.get("path_length", 0),
            )
            paths.append(path)

        best_path = paths[0] if paths else None
        transitive_trust = best_path.cumulative_trust if best_path else 0.0

        return TrustTransitivityResult(
            source_id=request.source_id,
            target_id=request.target_id,
            transitive_trust=transitive_trust,
            paths_found=len(paths),
            best_path=best_path,
            all_paths=paths if request.return_all_paths else [],
            max_hops_searched=request.max_hops,
            computed_at=datetime.now(UTC),
        )

    # ═══════════════════════════════════════════════════════════════
    # GRAPH METRICS
    # ═══════════════════════════════════════════════════════════════

    async def get_graph_metrics(self) -> GraphMetrics:
        """Get comprehensive metrics about the knowledge graph."""
        start_time = datetime.now(UTC)

        # Node counts by type
        node_results = await self.client.execute(
            """
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS count
            RETURN label, count
            """
        )
        nodes_by_type = {r["label"]: r["count"] for r in node_results}
        total_nodes = sum(nodes_by_type.values())

        # Edge counts by type
        edge_results = await self.client.execute(
            """
            MATCH ()-[r]->()
            WITH type(r) AS rel_type, count(r) AS count
            RETURN rel_type, count
            """
        )
        edges_by_type = {r["rel_type"]: r["count"] for r in edge_results}
        total_edges = sum(edges_by_type.values())

        # Density and degree
        stats_result = await self.client.execute_single(
            """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS degree
            RETURN avg(degree) AS avg_degree,
                   max(degree) AS max_degree,
                   count(n) AS node_count
            """
        )

        avg_degree = stats_result.get("avg_degree", 0) if stats_result else 0
        max_degree = stats_result.get("max_degree", 0) if stats_result else 0

        # Density calculation
        possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 1
        density = total_edges / possible_edges if possible_edges > 0 else 0

        # Trust distribution
        trust_result = await self.client.execute(
            """
            MATCH (c:Capsule)
            WITH c.trust_level AS trust
            RETURN
                CASE
                    WHEN trust < 40 THEN 'QUARANTINE'
                    WHEN trust < 60 THEN 'SANDBOX'
                    WHEN trust < 80 THEN 'STANDARD'
                    WHEN trust < 100 THEN 'TRUSTED'
                    ELSE 'CORE'
                END AS bucket,
                count(*) AS count
            """
        )
        trust_distribution = {r["bucket"]: r["count"] for r in trust_result}

        # Average trust
        avg_trust_result = await self.client.execute_single(
            "MATCH (c:Capsule) RETURN avg(c.trust_level) AS avg_trust"
        )
        avg_trust = avg_trust_result.get("avg_trust", 60) if avg_trust_result else 60

        computation_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

        return GraphMetrics(
            total_nodes=total_nodes,
            total_edges=total_edges,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            density=min(density, 1.0),
            avg_degree=avg_degree or 0.0,
            max_degree=max_degree or 0,
            avg_clustering=0.0,  # Requires GDS or NetworkX
            connected_components=0,  # Requires GDS
            largest_component_size=0,
            diameter=None,
            avg_path_length=None,
            avg_trust_level=avg_trust or 60.0,
            trust_distribution=trust_distribution,
            computed_at=datetime.now(UTC),
            computation_time_ms=computation_time,
        )

    async def get_trust_influences(
        self,
        node_label: str = "Capsule",
        limit: int = 50,
    ) -> list[TrustInfluence]:
        """Get nodes ranked by their influence on trust propagation."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        validated_node_label = validate_neo4j_identifier(node_label, "node_label")

        results = await self.client.execute(
            f"""
            MATCH (n:{validated_node_label})
            OPTIONAL MATCH (n)<-[:DERIVED_FROM*1..5]-(downstream)
            OPTIONAL MATCH (n)-[:DERIVED_FROM*1..5]->(upstream)
            WITH n,
                 count(DISTINCT downstream) AS downstream_count,
                 count(DISTINCT upstream) AS upstream_count,
                 n.trust_level AS trust
            WITH n, downstream_count, upstream_count, trust,
                 (downstream_count * trust / 100.0) AS influence_score
            ORDER BY influence_score DESC
            LIMIT $limit
            RETURN n.id AS node_id,
                   influence_score,
                   downstream_count,
                   upstream_count,
                   trust
            """,
            {"limit": limit},
        )

        return [
            TrustInfluence(
                node_id=r["node_id"],
                node_type=node_label,
                influence_score=r.get("influence_score", 0),
                downstream_reach=r.get("downstream_count", 0),
                upstream_sources=r.get("upstream_count", 0),
                trust_amplification=r.get("trust", 60) / 60.0,
            )
            for r in results
        ]

    # ═══════════════════════════════════════════════════════════════
    # NODE SIMILARITY
    # ═══════════════════════════════════════════════════════════════

    async def compute_node_similarity(
        self,
        request: NodeSimilarityRequest | None = None,
    ) -> NodeSimilarityResult:
        """
        Compute node similarity using GDS or Cypher fallback.

        Finds similar nodes based on shared neighbors (Jaccard similarity).
        """
        request = request or NodeSimilarityRequest()
        start_time = datetime.now(UTC)
        backend = await self.detect_backend()

        if backend == GraphBackend.GDS:
            result = await self._gds_node_similarity(request)
        else:
            result = await self._cypher_node_similarity(request)

        result.computation_time_ms = (
            datetime.now(UTC) - start_time
        ).total_seconds() * 1000
        return result

    async def _gds_node_similarity(
        self,
        request: NodeSimilarityRequest,
    ) -> NodeSimilarityResult:
        """Compute node similarity using GDS."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        relationship_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")
        graph_name = f"similarity_{node_label}"

        try:
            # Project the graph
            await self.client.execute(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    '{node_label}',
                    '{relationship_type}'
                )
                """
            )

            # Run node similarity
            algo = "gds.nodeSimilarity.stream"
            if request.source_node_id:
                # Similarity for a specific node
                results = await self.client.execute(
                    f"""
                    MATCH (source:{node_label} {{id: $source_id}})
                    CALL {algo}('{graph_name}', {{
                        topK: $top_k,
                        similarityCutoff: $cutoff
                    }})
                    YIELD node1, node2, similarity
                    WHERE id(source) = node1
                    WITH node2, similarity
                    MATCH (n:{node_label}) WHERE id(n) = node2
                    RETURN n.id AS node_id, n.title AS title, n.type AS node_type, similarity
                    ORDER BY similarity DESC
                    LIMIT $top_k
                    """,
                    {
                        "source_id": request.source_node_id,
                        "top_k": request.top_k,
                        "cutoff": request.similarity_cutoff,
                    },
                )
            else:
                results = await self.client.execute(
                    f"""
                    CALL {algo}('{graph_name}', {{
                        topK: $top_k,
                        similarityCutoff: $cutoff
                    }})
                    YIELD node1, node2, similarity
                    WITH node2, similarity
                    MATCH (n:{node_label}) WHERE id(n) = node2
                    RETURN n.id AS node_id, n.title AS title, n.type AS node_type, similarity
                    ORDER BY similarity DESC
                    LIMIT $top_k
                    """,
                    {
                        "top_k": request.top_k,
                        "cutoff": request.similarity_cutoff,
                    },
                )

            similar_nodes = [
                SimilarNode(
                    node_id=r["node_id"],
                    node_type=r.get("node_type", node_label),
                    title=r.get("title"),
                    similarity_score=r["similarity"],
                )
                for r in results
            ]

            return NodeSimilarityResult(
                source_id=request.source_node_id,
                similar_nodes=similar_nodes,
                similarity_metric=request.similarity_metric,
                top_k=request.top_k,
                computation_time_ms=0.0,
                backend_used=GraphBackend.GDS,
            )

        finally:
            try:
                await self.client.execute(
                    f"CALL gds.graph.drop('{graph_name}', false)"
                )
            except (RuntimeError, OSError, ValueError):
                pass  # Best-effort GDS graph cleanup

    async def _cypher_node_similarity(
        self,
        request: NodeSimilarityRequest,
    ) -> NodeSimilarityResult:
        """
        Compute Jaccard similarity using Cypher.

        Fallback when GDS is not available.
        """
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        node_label = validate_neo4j_identifier(request.node_label, "node_label")
        relationship_type = validate_neo4j_identifier(request.relationship_type, "relationship_type")

        if request.source_node_id:
            # Similarity for a specific node
            results = await self.client.execute(
                f"""
                MATCH (source:{node_label} {{id: $source_id}})-[:{relationship_type}]-(neighbor)
                WITH source, collect(DISTINCT neighbor) AS source_neighbors
                MATCH (other:{node_label})-[:{relationship_type}]-(neighbor)
                WHERE other <> source
                WITH source, source_neighbors, other, collect(DISTINCT neighbor) AS other_neighbors
                WITH other,
                     [n IN source_neighbors WHERE n IN other_neighbors] AS intersection,
                     source_neighbors + [n IN other_neighbors WHERE NOT n IN source_neighbors] AS union_set
                WITH other,
                     size(intersection) AS shared,
                     toFloat(size(intersection)) / size(union_set) AS similarity
                WHERE similarity >= $cutoff
                ORDER BY similarity DESC
                LIMIT $top_k
                MATCH (other)
                RETURN other.id AS node_id, other.title AS title, other.type AS node_type,
                       similarity, shared AS shared_neighbors
                """,
                {
                    "source_id": request.source_node_id,
                    "cutoff": request.similarity_cutoff,
                    "top_k": request.top_k,
                },
            )
        else:
            results = await self.client.execute(
                f"""
                MATCH (n1:{node_label})-[:{relationship_type}]-(neighbor)
                WITH n1, collect(DISTINCT neighbor) AS n1_neighbors
                MATCH (n2:{node_label})-[:{relationship_type}]-(neighbor)
                WHERE id(n1) < id(n2)
                WITH n1, n2, n1_neighbors, collect(DISTINCT neighbor) AS n2_neighbors
                WITH n1, n2,
                     [n IN n1_neighbors WHERE n IN n2_neighbors] AS intersection,
                     n1_neighbors + [n IN n2_neighbors WHERE NOT n IN n1_neighbors] AS union_set
                WITH n1, n2,
                     size(intersection) AS shared,
                     toFloat(size(intersection)) / size(union_set) AS similarity
                WHERE similarity >= $cutoff
                ORDER BY similarity DESC
                LIMIT $top_k
                RETURN n2.id AS node_id, n2.title AS title, n2.type AS node_type,
                       similarity, shared AS shared_neighbors
                """,
                {
                    "cutoff": request.similarity_cutoff,
                    "top_k": request.top_k,
                },
            )

        similar_nodes = [
            SimilarNode(
                node_id=r["node_id"],
                node_type=r.get("node_type", node_label),
                title=r.get("title"),
                similarity_score=r["similarity"],
                shared_neighbors=r.get("shared_neighbors", 0),
            )
            for r in results
        ]

        return NodeSimilarityResult(
            source_id=request.source_node_id,
            similar_nodes=similar_nodes,
            similarity_metric="jaccard",
            top_k=request.top_k,
            computation_time_ms=0.0,
            backend_used=GraphBackend.CYPHER,
        )

    # ═══════════════════════════════════════════════════════════════
    # SHORTEST PATH
    # ═══════════════════════════════════════════════════════════════

    async def compute_shortest_path(
        self,
        request: ShortestPathRequest,
    ) -> ShortestPathResult:
        """
        Compute shortest path between two nodes.

        Uses GDS if available for weighted paths, otherwise Cypher.
        """
        start_time = datetime.now(UTC)
        backend = await self.detect_backend()

        if request.weighted and backend == GraphBackend.GDS:
            result = await self._gds_shortest_path(request)
        else:
            result = await self._cypher_shortest_path(request)

        result.computation_time_ms = (
            datetime.now(UTC) - start_time
        ).total_seconds() * 1000
        return result

    async def _gds_shortest_path(
        self,
        request: ShortestPathRequest,
    ) -> ShortestPathResult:
        """Compute weighted shortest path using GDS Dijkstra."""
        graph_name = "shortest_path_graph"
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        rel_types_list = [validate_neo4j_identifier(rt, "relationship_type") for rt in request.relationship_types]
        rel_types_for_projection = ", ".join(rel_types_list)

        try:
            # Project with trust as weight
            await self.client.execute(
                f"""
                CALL gds.graph.project(
                    '{graph_name}',
                    'Capsule',
                    {{
                        {rel_types_for_projection}
                    }},
                    {{
                        relationshipProperties: 'trust_weight'
                    }}
                )
                """
            )

            result = await self.client.execute_single(
                f"""
                MATCH (source:Capsule {{id: $source_id}}), (target:Capsule {{id: $target_id}})
                CALL gds.shortestPath.dijkstra.stream('{graph_name}', {{
                    sourceNode: source,
                    targetNode: target,
                    relationshipWeightProperty: 'trust_weight'
                }})
                YIELD path, totalCost
                WITH [n IN nodes(path) | n] AS pathNodes, totalCost
                RETURN [n IN pathNodes | n.id] AS node_ids,
                       [n IN pathNodes | n.title] AS titles,
                       [n IN pathNodes | n.trust_level] AS trusts,
                       size(pathNodes) - 1 AS path_length,
                       totalCost
                """,
                {
                    "source_id": request.source_id,
                    "target_id": request.target_id,
                },
            )

            if result:
                node_ids = result.get("node_ids", [])
                titles = result.get("titles", [])
                trusts = result.get("trusts", [])

                path_nodes = [
                    PathNode(
                        node_id=nid,
                        node_type="Capsule",
                        title=titles[i] if i < len(titles) else None,
                        trust_level=trusts[i] if i < len(trusts) else None,
                    )
                    for i, nid in enumerate(node_ids)
                ]

                return ShortestPathResult(
                    source_id=request.source_id,
                    target_id=request.target_id,
                    path_found=True,
                    path_length=result.get("path_length", len(node_ids) - 1),
                    path_nodes=path_nodes,
                    total_trust=result.get("totalCost"),
                    computation_time_ms=0.0,
                    backend_used=GraphBackend.GDS,
                )
            else:
                return ShortestPathResult(
                    source_id=request.source_id,
                    target_id=request.target_id,
                    path_found=False,
                    computation_time_ms=0.0,
                    backend_used=GraphBackend.GDS,
                )

        finally:
            try:
                await self.client.execute(
                    f"CALL gds.graph.drop('{graph_name}', false)"
                )
            except (RuntimeError, OSError, ValueError):
                pass  # Best-effort GDS graph cleanup

    async def _cypher_shortest_path(
        self,
        request: ShortestPathRequest,
    ) -> ShortestPathResult:
        """Compute shortest path using native Cypher."""
        # SECURITY FIX: Validate all user-controlled identifiers to prevent Cypher injection
        rel_types = validate_relationship_pattern(request.relationship_types)

        # SECURITY FIX: Validate max_depth is a safe integer value
        max_depth = max(1, min(int(request.max_depth), 20))  # Clamp between 1 and 20

        result = await self.client.execute_single(
            f"""
            MATCH path = shortestPath(
                (source:Capsule {{id: $source_id}})-[:{rel_types}*1..{max_depth}]-(target:Capsule {{id: $target_id}})
            )
            WITH path,
                 [n IN nodes(path) | n] AS pathNodes,
                 [r IN relationships(path) | type(r)] AS relTypes
            RETURN [n IN pathNodes | n.id] AS node_ids,
                   [n IN pathNodes | n.title] AS titles,
                   [n IN pathNodes | n.trust_level] AS trusts,
                   [n IN pathNodes | labels(n)[0]] AS types,
                   relTypes,
                   length(path) AS path_length
            """,
            {
                "source_id": request.source_id,
                "target_id": request.target_id,
            },
        )

        if result:
            node_ids = result.get("node_ids", [])
            titles = result.get("titles", [])
            trusts = result.get("trusts", [])
            types = result.get("types", [])
            rel_types = result.get("relTypes", [])

            path_nodes = [
                PathNode(
                    node_id=nid,
                    node_type=types[i] if i < len(types) else "Capsule",
                    title=titles[i] if i < len(titles) else None,
                    trust_level=trusts[i] if i < len(trusts) else None,
                )
                for i, nid in enumerate(node_ids)
            ]

            # Compute total trust if weighted
            total_trust = None
            if request.weighted and trusts:
                valid_trusts = [t for t in trusts if t is not None]
                if valid_trusts:
                    total_trust = 1.0
                    for t in valid_trusts:
                        total_trust *= (t / 100.0)

            return ShortestPathResult(
                source_id=request.source_id,
                target_id=request.target_id,
                path_found=True,
                path_length=result.get("path_length", len(node_ids) - 1),
                path_nodes=path_nodes,
                path_relationships=rel_types,
                total_trust=total_trust,
                computation_time_ms=0.0,
                backend_used=GraphBackend.CYPHER,
            )
        else:
            return ShortestPathResult(
                source_id=request.source_id,
                target_id=request.target_id,
                path_found=False,
                computation_time_ms=0.0,
                backend_used=GraphBackend.CYPHER,
            )


class GraphRepository:
    """
    High-level repository for graph algorithm operations.

    Wraps GraphAlgorithmProvider with repository patterns.
    """

    def __init__(self, client: Neo4jClient):
        self.client = client
        self.provider = GraphAlgorithmProvider(client)
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def compute_pagerank(
        self,
        node_label: str = "Capsule",
        relationship_type: str = "DERIVED_FROM",
        damping_factor: float = 0.85,
        max_iterations: int = 20,
        limit: int = 100,
    ) -> list[NodeRanking]:
        """Compute PageRank and return rankings."""
        request = PageRankRequest(
            node_label=node_label,
            relationship_type=relationship_type,
            damping_factor=damping_factor,
            max_iterations=max_iterations,
            limit=limit,
        )
        result: NodeRankingResult = await self.provider.compute_pagerank(request)
        rankings: list[NodeRanking] = result.rankings
        return rankings

    async def compute_betweenness_centrality(
        self,
        node_label: str = "Capsule",
        limit: int = 100,
    ) -> list[NodeRanking]:
        """Compute betweenness centrality."""
        request = CentralityRequest(
            algorithm=AlgorithmType.BETWEENNESS_CENTRALITY,
            node_label=node_label,
            limit=limit,
        )
        result: NodeRankingResult = await self.provider.compute_centrality(request)
        rankings: list[NodeRanking] = result.rankings
        return rankings

    async def detect_communities(
        self,
        algorithm: str = "louvain",
        min_size: int = 2,
    ) -> list[Community]:
        """Detect communities in the graph."""
        algo = (
            AlgorithmType.COMMUNITY_LOUVAIN
            if algorithm == "louvain"
            else AlgorithmType.COMMUNITY_LABEL_PROPAGATION
        )
        request = CommunityDetectionRequest(
            algorithm=algo,
            min_community_size=min_size,
        )
        result: CommunityDetectionResult = await self.provider.detect_communities(request)
        communities: list[Community] = result.communities
        return communities

    async def compute_trust_transitivity(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 5,
    ) -> float:
        """Compute transitive trust between two nodes."""
        request = TrustTransitivityRequest(
            source_id=source_id,
            target_id=target_id,
            max_hops=max_hops,
        )
        result: TrustTransitivityResult = await self.provider.compute_trust_transitivity(request)
        trust: float = result.transitive_trust
        return trust

    async def get_metrics(self) -> GraphMetrics:
        """Get comprehensive graph metrics."""
        return await self.provider.get_graph_metrics()

    async def get_graph_metrics(self) -> GraphMetrics:
        """Alias for get_metrics() - used by scheduler."""
        return await self.provider.get_graph_metrics()

    async def find_similar_nodes(
        self,
        source_id: str | None = None,
        top_k: int = 10,
        min_similarity: float = 0.1,
    ) -> list[SimilarNode]:
        """Find nodes similar to the source node."""
        request = NodeSimilarityRequest(
            source_node_id=source_id,
            top_k=top_k,
            similarity_cutoff=min_similarity,
        )
        result: NodeSimilarityResult = await self.provider.compute_node_similarity(request)
        similar: list[SimilarNode] = result.similar_nodes
        return similar

    async def find_shortest_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 10,
        weighted: bool = False,
    ) -> ShortestPathResult:
        """Find the shortest path between two nodes."""
        request = ShortestPathRequest(
            source_id=source_id,
            target_id=target_id,
            max_depth=max_depth,
            weighted=weighted,
        )
        return await self.provider.compute_shortest_path(request)

    async def get_gds_status(self) -> dict[str, Any]:
        """Check if GDS is available and return status."""
        backend = await self.provider.detect_backend()
        return {
            "gds_available": backend == GraphBackend.GDS,
            "active_backend": backend.value,
            "cache_enabled": self.provider.config.enable_caching,
            "cache_entries": len(self.provider._cache),
        }
