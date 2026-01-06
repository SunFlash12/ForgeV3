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

from forge.database.client import Neo4jClient
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    CapsuleInDB,
    CapsuleWithLineage,
    CapsuleSearchResult,
    LineageNode,
)
from forge.models.base import TrustLevel, CapsuleType
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

    async def update(self, entity_id: str, data: CapsuleUpdate) -> Capsule | None:
        """
        Update an existing capsule.
        
        Note: This creates a new version rather than modifying in place
        for audit trail purposes.
        
        Args:
            entity_id: Capsule ID
            data: Update data
            
        Returns:
            Updated capsule or None
        """
        # Build SET clauses for non-None fields
        set_clauses = ["c.updated_at = $now"]
        params: dict[str, Any] = {
            "id": entity_id,
            "now": self._now().isoformat(),
        }
        
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
        
        query = f"""
        MATCH (c:Capsule {{id: $id}})
        SET {', '.join(set_clauses)}
        RETURN c {{.*}} AS capsule
        """
        
        result = await self.client.execute_single(query, params)
        
        if result and result.get("capsule"):
            return self._to_model(result["capsule"])
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

    async def get_descendants(
        self,
        capsule_id: str,
        max_depth: int = 10,
    ) -> list[LineageNode]:
        """Get all descendants of a capsule up to max depth."""
        query = f"""
        MATCH path = (root:Capsule {{id: $id}})<-[:DERIVED_FROM*1..{max_depth}]-(descendant:Capsule)
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

        Args:
            capsule_id: Capsule ID
            max_depth: Maximum depth to traverse

        Returns:
            List of ancestor capsules
        """
        query = f"""
        MATCH (c:Capsule {{id: $id}})-[:DERIVED_FROM*1..{max_depth}]->(ancestor:Capsule)
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
