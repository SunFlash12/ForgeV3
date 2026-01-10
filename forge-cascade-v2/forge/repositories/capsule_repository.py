"""
Capsule Repository

Repository for Capsule CRUD operations, symbolic inheritance (lineage),
and semantic search using vector embeddings.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog

from forge.models.base import CapsuleType, TrustLevel, generate_id
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleSearchResult,
    CapsuleUpdate,
    CapsuleWithLineage,
    LineageNode,
)
from forge.models.semantic_edges import (
    ContradictionCluster,
    ContradictionSeverity,
    ContradictionStatus,
    SemanticEdge,
    SemanticEdgeCreate,
    SemanticNeighbor,
    SemanticRelationType,
)
from forge.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class CapsuleRepository(BaseRepository[Capsule, CapsuleCreate, CapsuleUpdate]):
    """
    Repository for Capsule entities.

    Provides CRUD operations, symbolic inheritance (lineage tracking),
    and semantic search capabilities.
    """

    @property
    def node_label(self) -> str:
        return "Capsule"

    @property
    def model_class(self) -> type[Capsule]:
        return Capsule

    def _to_model(self, record: dict[str, Any]) -> Capsule | None:
        """
        Convert a Neo4j record to a Capsule model.

        Handles deserialization of metadata from JSON string.
        """
        if not record:
            return None

        # Deserialize metadata from JSON string if needed
        if "metadata" in record and isinstance(record["metadata"], str):
            try:
                record["metadata"] = json.loads(record["metadata"])
            except json.JSONDecodeError:
                record["metadata"] = {}

        return super()._to_model(record)

    async def create(
        self,
        data: CapsuleCreate,
        owner_id: str,
        embedding: list[float] | None = None,
    ) -> Capsule:
        """
        Create a new capsule with optional symbolic inheritance.

        Args:
            data: Capsule creation data
            owner_id: ID of the owner user
            embedding: Vector embedding for semantic search

        Returns:
            Created capsule
        """
        capsule_id = self._generate_id()
        now = self._now()

        # Build the query based on whether we have a parent
        if data.parent_id:
            query = """
            MATCH (parent:Capsule {id: $parent_id})
            CREATE (c:Capsule {
                id: $id,
                content: $content,
                type: $type,
                title: $title,
                summary: $summary,
                tags: $tags,
                metadata: $metadata,
                version: '1.0.0',
                owner_id: $owner_id,
                trust_level: $trust_level,
                parent_id: $parent_id,
                embedding: $embedding,
                is_archived: false,
                view_count: 0,
                fork_count: 0,
                created_at: $now,
                updated_at: $now
            })
            CREATE (c)-[:DERIVED_FROM {
                reason: $evolution_reason,
                timestamp: $now
            }]->(parent)
            WITH c, parent
            SET parent.fork_count = parent.fork_count + 1
            RETURN c {.*} AS capsule
            """
        else:
            query = """
            CREATE (c:Capsule {
                id: $id,
                content: $content,
                type: $type,
                title: $title,
                summary: $summary,
                tags: $tags,
                metadata: $metadata,
                version: '1.0.0',
                owner_id: $owner_id,
                trust_level: $trust_level,
                parent_id: null,
                embedding: $embedding,
                is_archived: false,
                view_count: 0,
                fork_count: 0,
                created_at: $now,
                updated_at: $now
            })
            RETURN c {.*} AS capsule
            """

        params = {
            "id": capsule_id,
            "content": data.content,
            "type": data.type.value if isinstance(data.type, CapsuleType) else data.type,
            "title": data.title,
            "summary": data.summary,
            "tags": data.tags,
            "metadata": json.dumps(data.metadata) if data.metadata else "{}",
            "owner_id": owner_id,
            "trust_level": TrustLevel.STANDARD.value,
            "parent_id": data.parent_id,
            "evolution_reason": data.evolution_reason,
            "embedding": embedding,
            "now": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("capsule"):
            self.logger.info(
                "Created capsule",
                capsule_id=capsule_id,
                parent_id=data.parent_id,
                owner_id=owner_id,
            )
            return self._to_model(result["capsule"])

        raise RuntimeError("Failed to create capsule")

    async def update(
        self,
        entity_id: str,
        data: CapsuleUpdate,
        caller_id: str | None = None
    ) -> Capsule | None:
        """
        Update an existing capsule.

        SECURITY FIX (Audit 4 - H27): Now verifies caller owns the capsule
        before allowing updates.

        Note: This creates a new version rather than modifying in place
        for audit trail purposes.

        Args:
            entity_id: Capsule ID
            data: Update data
            caller_id: ID of the user attempting the update (for authorization)

        Returns:
            Updated capsule or None if not found or not authorized
        """
        # Build SET clauses for non-None fields
        set_clauses = ["c.updated_at = $now"]
        params: dict[str, Any] = {
            "id": entity_id,
            "now": self._now().isoformat(),
        }

        # SECURITY FIX (Audit 4 - H27): Add owner verification if caller_id provided
        owner_check = ""
        if caller_id:
            params["caller_id"] = caller_id
            owner_check = " AND c.owner_id = $caller_id"

        if data.content is not None:
            set_clauses.append("c.content = $content")
            params["content"] = data.content

        if data.title is not None:
            set_clauses.append("c.title = $title")
            params["title"] = data.title

        if data.summary is not None:
            set_clauses.append("c.summary = $summary")
            params["summary"] = data.summary

        if data.tags is not None:
            set_clauses.append("c.tags = $tags")
            params["tags"] = data.tags

        if data.metadata is not None:
            set_clauses.append("c.metadata = $metadata")
            params["metadata"] = data.metadata

        # SECURITY FIX (Audit 4 - H27): Include owner check in WHERE clause
        query = f"""
        MATCH (c:Capsule {{id: $id}})
        WHERE c.is_archived = false{owner_check}
        SET {', '.join(set_clauses)}
        RETURN c {{.*}} AS capsule
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("capsule"):
            return self._to_model(result["capsule"])

        # SECURITY FIX: Log if update failed due to authorization
        if caller_id:
            # Check if capsule exists but caller doesn't own it
            check_query = """
            MATCH (c:Capsule {id: $id})
            RETURN c.owner_id AS owner_id
            """
            check_result = await self.client.execute_single(check_query, {"id": entity_id})
            if check_result and check_result.get("owner_id") != caller_id:
                logger.warning(
                    "capsule_update_unauthorized",
                    capsule_id=entity_id,
                    caller_id=caller_id,
                    owner_id=check_result.get("owner_id")
                )

        return None

    async def get_lineage(self, capsule_id: str) -> CapsuleWithLineage | None:
        """
        Get a capsule with its full lineage (ancestry chain).

        This traces the DERIVED_FROM relationships back to the
        original ancestor (the "Isnad" - chain of transmission).

        Args:
            capsule_id: Capsule ID

        Returns:
            Capsule with lineage information
        """
        query = """
        MATCH (c:Capsule {id: $id})
        OPTIONAL MATCH path = (c)-[:DERIVED_FROM*0..]->(ancestor:Capsule)
        WHERE NOT (ancestor)-[:DERIVED_FROM]->()
        WITH c, collect(DISTINCT {
            id: ancestor.id,
            version: ancestor.version,
            title: ancestor.title,
            type: ancestor.type,
            created_at: ancestor.created_at,
            trust_level: ancestor.trust_level,
            depth: length(path)
        }) AS lineage
        OPTIONAL MATCH (child:Capsule)-[:DERIVED_FROM]->(c)
        WITH c, lineage, collect(DISTINCT {
            id: child.id,
            version: child.version,
            title: child.title,
            type: child.type,
            created_at: child.created_at,
            trust_level: child.trust_level,
            depth: 1
        }) AS children
        RETURN c {.*} AS capsule,
               lineage,
               children,
               size([x IN lineage WHERE x.id IS NOT NULL]) AS lineage_depth
        """

        result = await self.client.execute_single(query, {"id": capsule_id})

        if not result or not result.get("capsule"):
            return None

        capsule_data = result["capsule"]
        lineage_data = result.get("lineage", [])
        children_data = result.get("children", [])

        # Convert to models
        lineage = [
            LineageNode(
                id=l["id"],
                version=l["version"],
                title=l.get("title"),
                type=l["type"],
                created_at=l["created_at"],
                trust_level=l["trust_level"],
                depth=l["depth"],
            )
            for l in lineage_data
            if l.get("id")
        ]

        children = [
            LineageNode(
                id=c["id"],
                version=c["version"],
                title=c.get("title"),
                type=c["type"],
                created_at=c["created_at"],
                trust_level=c["trust_level"],
                depth=c["depth"],
            )
            for c in children_data
            if c.get("id")
        ]

        # Sort lineage by depth (oldest first)
        lineage.sort(key=lambda x: x.depth, reverse=True)

        return CapsuleWithLineage(
            **capsule_data,
            lineage=lineage,
            children=children,
            lineage_depth=result.get("lineage_depth", 0),
        )

    async def semantic_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_trust: int = 40,
        capsule_type: CapsuleType | None = None,
        owner_id: str | None = None,
    ) -> list[CapsuleSearchResult]:
        """
        Search capsules by semantic similarity using vector index.

        Args:
            query_embedding: Query vector embedding
            limit: Maximum results
            min_trust: Minimum trust level
            capsule_type: Filter by type
            owner_id: Filter by owner

        Returns:
            List of search results with scores
        """
        # Build optional filters
        where_clauses = ["capsule.trust_level >= $min_trust"]
        params: dict[str, Any] = {
            "embedding": query_embedding,
            "limit": limit,
            "min_trust": min_trust,
        }

        if capsule_type:
            where_clauses.append("capsule.type = $type")
            params["type"] = capsule_type.value

        if owner_id:
            where_clauses.append("capsule.owner_id = $owner_id")
            params["owner_id"] = owner_id

        where_clause = " AND ".join(where_clauses)

        query = f"""
        CALL db.index.vector.queryNodes('capsule_embeddings', $limit, $embedding)
        YIELD node AS capsule, score
        WHERE {where_clause}
        RETURN capsule {{.*}} AS capsule, score
        ORDER BY score DESC
        """

        try:
            results = await self.client.execute(query, params)

            return [
                CapsuleSearchResult(
                    capsule=self._to_model(r["capsule"]),
                    score=r["score"],
                    highlights=[],  # Would need text search for highlights
                )
                for r in results
                if r.get("capsule")
            ]
        except Exception as e:
            self.logger.error(
                "Semantic search failed",
                error=str(e),
                hint="Vector index may not be available",
            )
            return []

    async def get_by_owner(
        self,
        owner_id: str,
        skip: int = 0,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[Capsule]:
        """
        Get capsules owned by a user.

        Args:
            owner_id: Owner user ID
            skip: Pagination offset
            limit: Maximum results
            include_archived: Include archived capsules

        Returns:
            List of capsules
        """
        archive_filter = "" if include_archived else "AND c.is_archived = false"

        query = f"""
        MATCH (c:Capsule {{owner_id: $owner_id}})
        WHERE true {archive_filter}
        RETURN c {{.*}} AS capsule
        ORDER BY c.created_at DESC
        SKIP $skip
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"owner_id": owner_id, "skip": skip, "limit": limit},
        )

        return self._to_models([r["capsule"] for r in results if r.get("capsule")])

    async def archive(self, capsule_id: str) -> Capsule | None:
        """Archive a capsule (soft delete)."""
        return await self.update_field(capsule_id, "is_archived", True)

    async def increment_view_count(self, capsule_id: str) -> None:
        """Increment the view counter for a capsule."""
        query = """
        MATCH (c:Capsule {id: $id})
        SET c.view_count = c.view_count + 1
        """
        await self.client.execute(query, {"id": capsule_id})

    async def get_children(self, capsule_id: str) -> list[Capsule]:
        """Get direct children (forks) of a capsule."""
        query = """
        MATCH (child:Capsule)-[:DERIVED_FROM]->(parent:Capsule {id: $id})
        RETURN child {.*} AS capsule
        ORDER BY child.created_at DESC
        """

        results = await self.client.execute(query, {"id": capsule_id})
        return self._to_models([r["capsule"] for r in results if r.get("capsule")])

    # SECURITY FIX (Audit 4 - H26): Maximum depth for graph traversals
    MAX_GRAPH_DEPTH = 20  # Prevent DoS via deep traversal

    async def get_descendants(
        self,
        capsule_id: str,
        max_depth: int = 10,
    ) -> list[LineageNode]:
        """
        Get all descendants of a capsule up to max depth.

        SECURITY FIX (Audit 4 - H26): Validates and caps max_depth to prevent
        DoS via unbounded graph traversal.
        """
        # SECURITY FIX: Validate and clamp max_depth to safe range
        safe_depth = max(1, min(int(max_depth), self.MAX_GRAPH_DEPTH))
        if max_depth != safe_depth:
            logger.warning(
                "max_depth_clamped",
                requested=max_depth,
                clamped_to=safe_depth,
                capsule_id=capsule_id
            )

        query = f"""
        MATCH path = (root:Capsule {{id: $id}})<-[:DERIVED_FROM*1..{safe_depth}]-(descendant:Capsule)
        WITH DISTINCT descendant, length(path) as depth
        RETURN {{
            id: descendant.id,
            version: descendant.version,
            title: descendant.title,
            type: descendant.type,
            created_at: descendant.created_at,
            trust_level: descendant.trust_level,
            depth: depth
        }} AS node
        ORDER BY depth ASC
        """

        results = await self.client.execute(
            query,
            {"id": capsule_id},
        )

        return [
            LineageNode(**r["node"])
            for r in results
            if r.get("node") and r["node"].get("id")
        ]

    async def list(
        self,
        offset: int = 0,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[Capsule], int]:
        """
        List capsules with pagination and filters.

        Args:
            offset: Number of records to skip
            limit: Maximum records to return
            filters: Optional filters (type, owner_id, tag)

        Returns:
            Tuple of (capsules, total_count)
        """
        filters = filters or {}
        conditions = ["c.is_archived = false"]
        params: dict[str, Any] = {"offset": offset, "limit": limit}

        if filters.get("type"):
            conditions.append("c.type = $type")
            params["type"] = filters["type"]

        if filters.get("owner_id"):
            conditions.append("c.owner_id = $owner_id")
            params["owner_id"] = filters["owner_id"]

        if filters.get("tag"):
            conditions.append("$tag IN c.tags")
            params["tag"] = filters["tag"]

        where_clause = " AND ".join(conditions)

        # Get count
        count_query = f"""
        MATCH (c:Capsule)
        WHERE {where_clause}
        RETURN count(c) AS total
        """
        count_result = await self.client.execute_single(count_query, params)
        total = count_result["total"] if count_result else 0

        # Get capsules
        query = f"""
        MATCH (c:Capsule)
        WHERE {where_clause}
        RETURN c {{.*}} AS capsule
        ORDER BY c.created_at DESC
        SKIP $offset
        LIMIT $limit
        """

        results = await self.client.execute(query, params)
        capsules = self._to_models([r["capsule"] for r in results if r.get("capsule")])

        return capsules, total

    async def get_ancestors(
        self,
        capsule_id: str,
        max_depth: int = 10,
    ) -> list[Capsule]:
        """
        Get all ancestors of a capsule up to max depth.

        SECURITY FIX (Audit 4 - H26): Validates and caps max_depth to prevent
        DoS via unbounded graph traversal.

        Args:
            capsule_id: Capsule ID
            max_depth: Maximum depth to traverse

        Returns:
            List of ancestor capsules
        """
        # SECURITY FIX: Validate and clamp max_depth to safe range
        safe_depth = max(1, min(int(max_depth), self.MAX_GRAPH_DEPTH))
        if max_depth != safe_depth:
            logger.warning(
                "max_depth_clamped",
                requested=max_depth,
                clamped_to=safe_depth,
                capsule_id=capsule_id
            )

        query = f"""
        MATCH (c:Capsule {{id: $id}})-[:DERIVED_FROM*1..{safe_depth}]->(ancestor:Capsule)
        WITH DISTINCT ancestor
        ORDER BY ancestor.created_at ASC
        RETURN ancestor {{.*}} AS capsule
        """

        results = await self.client.execute(query, {"id": capsule_id})
        return self._to_models([r["capsule"] for r in results if r.get("capsule")])

    async def add_parent(
        self,
        capsule_id: str,
        parent_id: str,
    ) -> Capsule | None:
        """
        Add a parent relationship to a capsule.

        Args:
            capsule_id: Child capsule ID
            parent_id: Parent capsule ID

        Returns:
            Updated capsule or None
        """
        query = """
        MATCH (child:Capsule {id: $capsule_id})
        MATCH (parent:Capsule {id: $parent_id})
        CREATE (child)-[:DERIVED_FROM {timestamp: $now}]->(parent)
        SET child.parent_id = $parent_id,
            parent.fork_count = parent.fork_count + 1
        RETURN child {.*} AS capsule
        """

        result = await self.client.execute_single(query, {
            "capsule_id": capsule_id,
            "parent_id": parent_id,
            "now": self._now().isoformat(),
        })

        if result and result.get("capsule"):
            return self._to_model(result["capsule"])
        return None

    async def get_recent(self, limit: int = 10) -> list[Capsule]:
        """
        Get most recently created capsules.

        Args:
            limit: Maximum number of capsules to return

        Returns:
            List of recent capsules
        """
        query = """
        MATCH (c:Capsule)
        WHERE c.is_archived = false
        RETURN c {.*} AS capsule
        ORDER BY c.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(query, {"limit": limit})
        return self._to_models([r["capsule"] for r in results if r.get("capsule")])

    async def get_changes_since(
        self,
        since: datetime | None,
        types: list[str] | None = None,
        min_trust: int = 0,
        limit: int = 100,
    ) -> tuple[list[Capsule], list[str]]:
        """
        Get capsules that changed since a timestamp (for federation sync).

        Args:
            since: Get changes after this timestamp (None = all)
            types: Filter by capsule types
            min_trust: Minimum trust level
            limit: Maximum results

        Returns:
            Tuple of (changed capsules, deleted capsule IDs)
        """
        conditions = [
            "c.is_archived = false",
            "c.trust_level >= $min_trust",
        ]
        params: dict[str, Any] = {"min_trust": min_trust, "limit": limit}

        if since:
            conditions.append("c.updated_at > $since")
            params["since"] = since.isoformat()

        if types:
            conditions.append("c.type IN $types")
            params["types"] = types

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (c:Capsule)
        WHERE {where_clause}
        RETURN c {{.*}} AS capsule
        ORDER BY c.updated_at ASC
        LIMIT $limit
        """

        results = await self.client.execute(query, params)
        capsules = self._to_models([r["capsule"] for r in results if r.get("capsule")])

        # Get deleted capsules since timestamp
        deleted_ids: list[str] = []
        if since:
            # Check for archived capsules that were archived after the since timestamp
            archive_query = """
            MATCH (c:Capsule)
            WHERE c.is_archived = true AND c.updated_at > $since
            RETURN c.id AS id
            LIMIT $limit
            """
            archive_results = await self.client.execute(
                archive_query,
                {"since": since.isoformat(), "limit": limit},
            )
            deleted_ids = [r["id"] for r in archive_results if r.get("id")]

        return capsules, deleted_ids

    async def get_edges_since(
        self,
        since: datetime | None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get edges (relationships) that changed since a timestamp.

        Args:
            since: Get changes after this timestamp (None = all)
            limit: Maximum results

        Returns:
            List of edge dictionaries
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if since:
            conditions.append("r.timestamp > $since")
            params["since"] = since.isoformat()

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
        MATCH (source:Capsule)-[r:DERIVED_FROM]->(target:Capsule)
        {where_clause}
        RETURN {{
            id: source.id + '->' + target.id,
            source_id: source.id,
            target_id: target.id,
            relationship_type: 'DERIVED_FROM',
            timestamp: r.timestamp,
            reason: r.reason
        }} AS edge
        ORDER BY r.timestamp ASC
        LIMIT $limit
        """

        results = await self.client.execute(query, params)
        return [r["edge"] for r in results if r.get("edge")]

    async def find_similar_by_embedding(
        self,
        embedding: list[float],
        limit: int = 20,
        min_similarity: float = 0.7,
        exclude_ids: list[str] | None = None,
    ) -> list[tuple[Capsule, float]]:
        """
        Find capsules similar to the given embedding vector.

        Args:
            embedding: Query embedding vector
            limit: Maximum results
            min_similarity: Minimum similarity score (0-1)
            exclude_ids: Capsule IDs to exclude from results

        Returns:
            List of (Capsule, similarity_score) tuples
        """
        exclude_ids = exclude_ids or []

        query = """
        CALL db.index.vector.queryNodes('capsule_embeddings', $limit, $embedding)
        YIELD node AS capsule, score
        WHERE capsule.is_archived = false
          AND NOT capsule.id IN $exclude_ids
          AND score >= $min_similarity
        RETURN capsule {.*} AS capsule, score
        ORDER BY score DESC
        """

        try:
            results = await self.client.execute(
                query,
                {
                    "embedding": embedding,
                    "limit": limit + len(exclude_ids),  # Account for exclusions
                    "min_similarity": min_similarity,
                    "exclude_ids": exclude_ids,
                },
            )

            return [
                (self._to_model(r["capsule"]), r["score"])
                for r in results[:limit]
                if r.get("capsule")
            ]
        except Exception as e:
            self.logger.warning(
                "find_similar_by_embedding failed",
                error=str(e),
                hint="Vector index may not be available",
            )
            return []

    async def get_semantic_edge(self, edge_id: str) -> SemanticEdge | None:
        """
        Get a semantic edge by ID.

        Args:
            edge_id: Edge ID

        Returns:
            SemanticEdge or None
        """
        query = """
        MATCH (c1)-[r:SEMANTIC_EDGE {id: $id}]->(c2)
        RETURN r {
            .*,
            source_id: c1.id,
            target_id: c2.id,
            source_title: c1.title,
            target_title: c2.title
        } AS edge
        """

        result = await self.client.execute_single(query, {"id": edge_id})

        if result and result.get("edge"):
            return self._to_semantic_edge(result["edge"])
        return None

    # ═══════════════════════════════════════════════════════════════
    # SEMANTIC EDGES
    # ═══════════════════════════════════════════════════════════════

    async def create_semantic_edge(
        self,
        data: SemanticEdgeCreate,
        created_by: str,
    ) -> SemanticEdge:
        """
        Create a semantic relationship between two capsules.

        For bidirectional relationships (RELATED_TO, CONTRADICTS),
        a single edge is created but can be traversed in both directions.

        Args:
            data: Semantic edge creation data
            created_by: User creating the edge

        Returns:
            Created semantic edge
        """
        edge_id = generate_id()
        now = self._now()

        # Determine if bidirectional
        is_bidirectional = data.relationship_type.is_bidirectional

        # For bidirectional edges, store in canonical order (lower ID first)
        if is_bidirectional:
            source_id = min(data.source_id, data.target_id)
            target_id = max(data.source_id, data.target_id)
        else:
            source_id = data.source_id
            target_id = data.target_id

        # Check if edge already exists
        existing = await self._get_semantic_edge(
            source_id, target_id, data.relationship_type
        )
        if existing:
            self.logger.warning(
                "Semantic edge already exists",
                source_id=source_id,
                target_id=target_id,
                relationship_type=data.relationship_type.value,
            )
            return existing

        # Create the edge as a relationship with properties
        query = """
        MATCH (source:Capsule {id: $source_id})
        MATCH (target:Capsule {id: $target_id})
        CREATE (source)-[r:SEMANTIC_EDGE {
            id: $id,
            relationship_type: $rel_type,
            confidence: $confidence,
            reason: $reason,
            auto_detected: $auto_detected,
            properties: $properties,
            bidirectional: $bidirectional,
            created_by: $created_by,
            created_at: $now,
            updated_at: $now
        }]->(target)
        RETURN r {
            .*,
            source_id: source.id,
            target_id: target.id
        } AS edge
        """

        params = {
            "id": edge_id,
            "source_id": source_id,
            "target_id": target_id,
            "rel_type": data.relationship_type.value,
            "confidence": data.confidence,
            "reason": data.reason,
            "auto_detected": data.auto_detected,
            "properties": json.dumps(data.properties),
            "bidirectional": is_bidirectional,
            "created_by": created_by,
            "now": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("edge"):
            self.logger.info(
                "Created semantic edge",
                edge_id=edge_id,
                relationship_type=data.relationship_type.value,
                source_id=source_id,
                target_id=target_id,
            )
            return self._to_semantic_edge(result["edge"])

        raise RuntimeError("Failed to create semantic edge")

    async def get_semantic_neighbors(
        self,
        capsule_id: str,
        rel_types: list[SemanticRelationType] | None = None,
        direction: str = "both",
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[SemanticNeighbor]:
        """
        Get semantically connected neighbor capsules.

        Args:
            capsule_id: Source capsule ID
            rel_types: Filter by relationship types (None = all)
            direction: "in", "out", or "both"
            min_confidence: Minimum confidence score
            limit: Maximum results

        Returns:
            List of semantic neighbors with relationship info
        """
        # SECURITY FIX (Audit 4 - M4): Use parameterized query for type filter
        # Don't format values directly into the query string
        type_filter = ""
        type_values: list[str] = []
        if rel_types:
            type_values = [rt.value for rt in rel_types]
            type_filter = "AND r.relationship_type IN $type_values"

        # Build direction-specific query
        if direction == "out":
            match_clause = "(c:Capsule {id: $id})-[r:SEMANTIC_EDGE]->(neighbor:Capsule)"
            dir_label = "outgoing"
        elif direction == "in":
            match_clause = "(c:Capsule {id: $id})<-[r:SEMANTIC_EDGE]-(neighbor:Capsule)"
            dir_label = "incoming"
        else:
            # Both directions
            match_clause = "(c:Capsule {id: $id})-[r:SEMANTIC_EDGE]-(neighbor:Capsule)"
            dir_label = "both"

        query = f"""
        MATCH {match_clause}
        WHERE r.confidence >= $min_confidence {type_filter}
        RETURN neighbor.id AS capsule_id,
               neighbor.title AS title,
               neighbor.type AS capsule_type,
               neighbor.trust_level AS trust_level,
               r.relationship_type AS relationship_type,
               r.confidence AS confidence,
               r.id AS edge_id,
               CASE WHEN startNode(r).id = $id THEN 'outgoing' ELSE 'incoming' END AS direction
        ORDER BY r.confidence DESC
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {
                "id": capsule_id,
                "min_confidence": min_confidence,
                "limit": limit,
                "type_values": type_values,  # SECURITY FIX (M4): Parameterized
            },
        )

        return [
            SemanticNeighbor(
                capsule_id=r["capsule_id"],
                title=r.get("title"),
                capsule_type=r.get("capsule_type"),
                trust_level=r.get("trust_level"),
                relationship_type=SemanticRelationType(r["relationship_type"]),
                direction=r.get("direction", dir_label),
                confidence=r.get("confidence", 1.0),
                edge_id=r["edge_id"],
            )
            for r in results
            if r.get("capsule_id")
        ]

    async def find_contradictions(
        self,
        capsule_id: str | None = None,
        tags: list[str] | None = None,
        min_severity: ContradictionSeverity = ContradictionSeverity.LOW,
        include_resolved: bool = False,
        limit: int = 50,
    ) -> list[tuple[Capsule, Capsule, SemanticEdge]]:
        """
        Find contradiction relationships.

        Args:
            capsule_id: Filter to contradictions involving this capsule
            tags: Filter to capsules with these tags
            min_severity: Minimum severity level
            include_resolved: Include resolved contradictions
            limit: Maximum results

        Returns:
            List of (capsule1, capsule2, edge) tuples
        """
        conditions = ["r.relationship_type = 'CONTRADICTS'"]
        params: dict[str, Any] = {"limit": limit}

        if capsule_id:
            conditions.append("(c1.id = $capsule_id OR c2.id = $capsule_id)")
            params["capsule_id"] = capsule_id

        if tags:
            conditions.append(
                "(any(tag IN c1.tags WHERE tag IN $tags) OR any(tag IN c2.tags WHERE tag IN $tags))"
            )
            params["tags"] = tags

        if not include_resolved:
            conditions.append(
                "(r.properties IS NULL OR NOT r.properties CONTAINS 'resolved')"
            )

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (c1:Capsule)-[r:SEMANTIC_EDGE]->(c2:Capsule)
        WHERE {where_clause}
        RETURN c1 {{.*}} AS capsule1,
               c2 {{.*}} AS capsule2,
               r {{
                   .*,
                   source_id: c1.id,
                   target_id: c2.id
               }} AS edge
        ORDER BY r.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(query, params)

        return [
            (
                self._to_model(r["capsule1"]),
                self._to_model(r["capsule2"]),
                self._to_semantic_edge(r["edge"]),
            )
            for r in results
            if r.get("capsule1") and r.get("capsule2") and r.get("edge")
        ]

    async def find_contradiction_clusters(
        self,
        min_size: int = 2,
        limit: int = 20,
    ) -> list[ContradictionCluster]:
        """
        Find clusters of mutually contradicting capsules.

        Uses connected component analysis on CONTRADICTS edges.

        Args:
            min_size: Minimum cluster size
            limit: Maximum clusters to return

        Returns:
            List of contradiction clusters
        """
        query = """
        MATCH (c1:Capsule)-[r:SEMANTIC_EDGE {relationship_type: 'CONTRADICTS'}]-(c2:Capsule)
        WITH collect(DISTINCT c1) + collect(DISTINCT c2) AS all_nodes,
             collect(r) AS all_edges
        WITH [n IN all_nodes | n.id] AS node_ids,
             [e IN all_edges | {
                 id: e.id,
                 source: startNode(e).id,
                 target: endNode(e).id,
                 severity: e.properties
             }] AS edges
        WHERE size(node_ids) >= $min_size
        RETURN node_ids, edges
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"min_size": min_size, "limit": limit},
        )

        clusters = []
        for _i, r in enumerate(results):
            node_ids = r.get("node_ids", [])
            r.get("edges", [])

            if len(node_ids) >= min_size:
                cluster = ContradictionCluster(
                    cluster_id=generate_id(),
                    capsule_ids=node_ids,
                    edges=[],  # Would need separate query to fully hydrate
                    overall_severity=ContradictionSeverity.MEDIUM,
                    resolution_status=ContradictionStatus.UNRESOLVED,
                )
                clusters.append(cluster)

        return clusters

    async def get_semantic_edges(
        self,
        capsule_id: str,
        rel_types: list[SemanticRelationType] | None = None,
        include_auto_detected: bool = True,
        limit: int = 100,
    ) -> list[SemanticEdge]:
        """
        Get all semantic edges for a capsule.

        Args:
            capsule_id: Capsule ID
            rel_types: Filter by relationship types
            include_auto_detected: Include auto-detected edges
            limit: Maximum results

        Returns:
            List of semantic edges
        """
        conditions = ["(c1.id = $id OR c2.id = $id)"]
        params: dict[str, Any] = {"id": capsule_id, "limit": limit}

        if rel_types:
            type_values = [rt.value for rt in rel_types]
            conditions.append(f"r.relationship_type IN {type_values}")

        if not include_auto_detected:
            conditions.append("r.auto_detected = false")

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (c1:Capsule)-[r:SEMANTIC_EDGE]->(c2:Capsule)
        WHERE {where_clause}
        RETURN r {{
            .*,
            source_id: c1.id,
            target_id: c2.id,
            source_title: c1.title,
            target_title: c2.title
        }} AS edge
        ORDER BY r.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(query, params)

        return [
            self._to_semantic_edge(r["edge"])
            for r in results
            if r.get("edge")
        ]

    async def delete_semantic_edge(self, edge_id: str) -> bool:
        """
        Delete a semantic edge by ID.

        Args:
            edge_id: Edge ID to delete

        Returns:
            True if deleted
        """
        query = """
        MATCH ()-[r:SEMANTIC_EDGE {id: $id}]->()
        DELETE r
        RETURN count(r) AS deleted
        """

        result = await self.client.execute_single(query, {"id": edge_id})
        deleted = result.get("deleted", 0) if result else 0

        if deleted > 0:
            self.logger.info("Deleted semantic edge", edge_id=edge_id)

        return deleted > 0

    async def update_semantic_edge(
        self,
        edge_id: str,
        confidence: float | None = None,
        properties: dict | None = None,
    ) -> SemanticEdge | None:
        """
        Update a semantic edge.

        Args:
            edge_id: Edge ID
            confidence: New confidence value
            properties: Properties to merge

        Returns:
            Updated edge or None
        """
        set_clauses = ["r.updated_at = $now"]
        params: dict[str, Any] = {
            "id": edge_id,
            "now": self._now().isoformat(),
        }

        if confidence is not None:
            set_clauses.append("r.confidence = $confidence")
            params["confidence"] = confidence

        if properties is not None:
            set_clauses.append("r.properties = $properties")
            params["properties"] = json.dumps(properties)

        query = f"""
        MATCH (c1)-[r:SEMANTIC_EDGE {{id: $id}}]->(c2)
        SET {', '.join(set_clauses)}
        RETURN r {{
            .*,
            source_id: c1.id,
            target_id: c2.id
        }} AS edge
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("edge"):
            return self._to_semantic_edge(result["edge"])
        return None

    async def _get_semantic_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: SemanticRelationType,
    ) -> SemanticEdge | None:
        """Check if a semantic edge already exists."""
        query = """
        MATCH (c1:Capsule {id: $source_id})-[r:SEMANTIC_EDGE {relationship_type: $rel_type}]->(c2:Capsule {id: $target_id})
        RETURN r {
            .*,
            source_id: c1.id,
            target_id: c2.id
        } AS edge
        """

        result = await self.client.execute_single(
            query,
            {
                "source_id": source_id,
                "target_id": target_id,
                "rel_type": rel_type.value,
            },
        )

        if result and result.get("edge"):
            return self._to_semantic_edge(result["edge"])
        return None

    def _to_semantic_edge(self, record: dict) -> SemanticEdge:
        """Convert a Neo4j record to SemanticEdge."""
        properties = record.get("properties", "{}")
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                properties = {}

        return SemanticEdge(
            id=record["id"],
            source_id=record["source_id"],
            target_id=record["target_id"],
            relationship_type=SemanticRelationType(record["relationship_type"]),
            confidence=record.get("confidence", 1.0),
            reason=record.get("reason"),
            auto_detected=record.get("auto_detected", False),
            properties=properties,
            bidirectional=record.get("bidirectional", False),
            created_by=record.get("created_by", ""),
            created_at=self._parse_datetime(record.get("created_at")),
            updated_at=self._parse_datetime(record.get("updated_at")),
        )

    def _parse_datetime(self, value: Any) -> datetime:
        """Parse a datetime from various formats."""
        if value is None:
            return self._now()
        if isinstance(value, datetime):
            return value
        if hasattr(value, "to_native"):
            return value.to_native()
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self._now()
