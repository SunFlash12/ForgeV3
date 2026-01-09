"""
Forge Cascade V2 - Search Service

High-level search service that integrates:
- Embedding generation for semantic search
- Capsule repository queries
- Full-text search fallback
- Search result ranking and filtering

This service provides a unified interface for all search operations
in the Forge system.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum

import structlog

from forge.services.embedding import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingProvider,
    get_embedding_service,
    cosine_similarity,
)
from forge.models.capsule import (
    Capsule,
    CapsuleSearchResult,
    CapsuleType,
)
from forge.models.base import TrustLevel

logger = structlog.get_logger(__name__)


class SearchMode(str, Enum):
    """Search modes available."""
    SEMANTIC = "semantic"      # Vector similarity search
    KEYWORD = "keyword"        # Keyword/full-text search
    HYBRID = "hybrid"          # Combined semantic + keyword
    EXACT = "exact"           # Exact content match


@dataclass
class SearchFilters:
    """Filters for search queries."""
    capsule_types: list[CapsuleType] | None = None
    owner_ids: list[str] | None = None
    min_trust: int = 40
    max_trust: int = 100
    tags: list[str] | None = None
    include_archived: bool = False
    created_after: datetime | None = None
    created_before: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule_types": [t.value for t in self.capsule_types] if self.capsule_types else None,
            "owner_ids": self.owner_ids,
            "min_trust": self.min_trust,
            "max_trust": self.max_trust,
            "tags": self.tags,
            "include_archived": self.include_archived,
            "created_after": self.created_after.isoformat() if self.created_after else None,
            "created_before": self.created_before.isoformat() if self.created_before else None,
        }


@dataclass
class SearchRequest:
    """Search request configuration."""
    query: str
    mode: SearchMode = SearchMode.SEMANTIC
    limit: int = 10
    offset: int = 0
    filters: SearchFilters = field(default_factory=SearchFilters)
    min_score: float = 0.5  # Minimum similarity score
    boost_recent: bool = True  # Boost recently created capsules
    boost_popular: bool = True  # Boost high view/fork count capsules


@dataclass
class SearchResultItem:
    """A single search result."""
    capsule: Capsule
    score: float
    highlights: list[str] = field(default_factory=list)
    match_type: str = "semantic"  # semantic, keyword, exact
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "capsule": {
                "id": self.capsule.id,
                "title": self.capsule.title,
                "content": self.capsule.content[:500] if len(self.capsule.content) > 500 else self.capsule.content,
                "type": self.capsule.type.value if hasattr(self.capsule.type, 'value') else str(self.capsule.type),
                "owner_id": self.capsule.owner_id,
                "tags": self.capsule.tags,
                "created_at": self.capsule.created_at.isoformat() if self.capsule.created_at else None,
            },
            "score": self.score,
            "highlights": self.highlights,
            "match_type": self.match_type,
        }


@dataclass
class SearchResponse:
    """Search response with results and metadata."""
    query: str
    mode: str
    results: list[SearchResultItem]
    total: int
    took_ms: float
    filters_applied: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "took_ms": self.took_ms,
            "filters_applied": self.filters_applied,
        }


class SearchService:
    """
    Search service for Forge capsules.
    
    Provides semantic search using vector embeddings with support for:
    - Semantic similarity search (primary mode)
    - Keyword fallback for when semantic search returns few results
    - Hybrid mode combining both approaches
    - Result ranking with recency and popularity boosts
    
    Usage:
        service = SearchService(
            embedding_service=get_embedding_service(),
            capsule_repo=capsule_repo,
        )
        
        results = await service.search(SearchRequest(
            query="Python best practices for async code",
            mode=SearchMode.SEMANTIC,
            limit=10,
        ))
    """
    
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        capsule_repo: Optional[Any] = None,  # CapsuleRepository
        db_client: Optional[Any] = None,  # Neo4jClient for direct queries
    ):
        self._embedding_service = embedding_service or get_embedding_service()
        self._capsule_repo = capsule_repo
        self._db = db_client
        
        logger.info(
            "search_service_initialized",
            embedding_dimensions=self._embedding_service.dimensions,
        )
    
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute a search query.
        
        Args:
            request: Search request configuration
            
        Returns:
            SearchResponse with results
        """
        import time
        start_time = time.monotonic()
        
        results: list[SearchResultItem] = []
        
        try:
            if request.mode == SearchMode.SEMANTIC:
                results = await self._semantic_search(request)
            elif request.mode == SearchMode.KEYWORD:
                results = await self._keyword_search(request)
            elif request.mode == SearchMode.HYBRID:
                results = await self._hybrid_search(request)
            elif request.mode == SearchMode.EXACT:
                results = await self._exact_search(request)
            else:
                results = await self._semantic_search(request)
            
            # Apply post-processing
            results = self._apply_boosts(results, request)
            results = self._filter_by_score(results, request.min_score)
            results = results[request.offset:request.offset + request.limit]
            
        except Exception as e:
            # SECURITY FIX (Audit 3): Truncate search query in error logs to prevent sensitive data leakage
            logger.error("search_failed", error=str(e), query=request.query[:50] + ("..." if len(request.query) > 50 else ""))
            results = []
        
        took_ms = (time.monotonic() - start_time) * 1000
        
        logger.info(
            "search_complete",
            query=request.query[:50],
            mode=request.mode.value,
            results=len(results),
            took_ms=round(took_ms, 2),
        )
        
        return SearchResponse(
            query=request.query,
            mode=request.mode.value,
            results=results,
            total=len(results),
            took_ms=took_ms,
            filters_applied=request.filters.to_dict(),
        )
    
    async def _semantic_search(self, request: SearchRequest) -> list[SearchResultItem]:
        """Perform semantic search using vector similarity."""
        # Generate embedding for query
        embedding_result = await self._embedding_service.embed(request.query)
        query_embedding = embedding_result.embedding
        
        # Search via repository if available
        if self._capsule_repo:
            search_results = await self._capsule_repo.semantic_search(
                query_embedding=query_embedding,
                limit=request.limit * 2,  # Get more for filtering
                min_trust=request.filters.min_trust,
                capsule_type=request.filters.capsule_types[0] if request.filters.capsule_types else None,
                owner_id=request.filters.owner_ids[0] if request.filters.owner_ids else None,
            )
            
            return [
                SearchResultItem(
                    capsule=r.capsule,
                    score=r.score,
                    highlights=r.highlights,
                    match_type="semantic",
                )
                for r in search_results
            ]
        
        # Direct database query if no repo
        if self._db:
            return await self._semantic_search_direct(query_embedding, request)
        
        return []
    
    async def _semantic_search_direct(
        self,
        query_embedding: list[float],
        request: SearchRequest,
    ) -> list[SearchResultItem]:
        """Direct semantic search via Neo4j vector index."""
        # Build filter conditions
        where_clauses = [
            "capsule.trust_level >= $min_trust",
            "capsule.trust_level <= $max_trust",
        ]
        params: dict[str, Any] = {
            "embedding": query_embedding,
            "limit": request.limit * 2,
            "min_trust": request.filters.min_trust,
            "max_trust": request.filters.max_trust,
        }
        
        if not request.filters.include_archived:
            where_clauses.append("capsule.is_archived = false")
        
        if request.filters.capsule_types:
            where_clauses.append("capsule.type IN $types")
            params["types"] = [t.value for t in request.filters.capsule_types]
        
        if request.filters.owner_ids:
            where_clauses.append("capsule.owner_id IN $owner_ids")
            params["owner_ids"] = request.filters.owner_ids
        
        if request.filters.tags:
            # Match any tag
            where_clauses.append("ANY(tag IN $tags WHERE tag IN capsule.tags)")
            params["tags"] = request.filters.tags
        
        where_clause = " AND ".join(where_clauses)
        
        query = f"""
        CALL db.index.vector.queryNodes('capsule_embeddings', $limit, $embedding)
        YIELD node AS capsule, score
        WHERE {where_clause}
        RETURN capsule {{
            id: capsule.id,
            title: capsule.title,
            content: capsule.content,
            type: capsule.type,
            owner_id: capsule.owner_id,
            trust_level: capsule.trust_level,
            version: capsule.version,
            tags: capsule.tags,
            metadata: capsule.metadata,
            view_count: capsule.view_count,
            fork_count: capsule.fork_count,
            is_archived: capsule.is_archived,
            created_at: capsule.created_at,
            updated_at: capsule.updated_at
        }} AS capsule, score
        ORDER BY score DESC
        """
        
        try:
            results = await self._db.execute(query, params)
            
            return [
                SearchResultItem(
                    capsule=self._dict_to_capsule(r["capsule"]),
                    score=r["score"],
                    highlights=[],
                    match_type="semantic",
                )
                for r in results
                if r.get("capsule")
            ]
        except Exception as e:
            logger.warning(
                "semantic_search_direct_failed",
                error=str(e),
                hint="Vector index may not be available",
            )
            return []
    
    async def _keyword_search(self, request: SearchRequest) -> list[SearchResultItem]:
        """Perform keyword/full-text search."""
        if not self._db:
            return []
        
        # Build search pattern
        search_terms = request.query.split()
        search_pattern = "|".join(f"(?i).*{term}.*" for term in search_terms)
        
        where_clauses = [
            "(capsule.content =~ $pattern OR capsule.title =~ $pattern)",
            "capsule.trust_level >= $min_trust",
        ]
        params: dict[str, Any] = {
            "pattern": search_pattern,
            "limit": request.limit,
            "min_trust": request.filters.min_trust,
        }
        
        if not request.filters.include_archived:
            where_clauses.append("capsule.is_archived = false")
        
        where_clause = " AND ".join(where_clauses)
        
        query = f"""
        MATCH (capsule:Capsule)
        WHERE {where_clause}
        RETURN capsule {{.*}} AS capsule
        ORDER BY capsule.view_count DESC, capsule.created_at DESC
        LIMIT $limit
        """
        
        try:
            results = await self._db.execute(query, params)
            
            return [
                SearchResultItem(
                    capsule=self._dict_to_capsule(r["capsule"]),
                    score=0.8,  # Fixed score for keyword matches
                    highlights=self._extract_highlights(
                        r["capsule"].get("content", ""),
                        search_terms,
                    ),
                    match_type="keyword",
                )
                for r in results
                if r.get("capsule")
            ]
        except Exception as e:
            logger.warning("keyword_search_failed", error=str(e))
            return []
    
    async def _hybrid_search(self, request: SearchRequest) -> list[SearchResultItem]:
        """Combine semantic and keyword search."""
        # Run both searches in parallel
        semantic_task = self._semantic_search(request)
        keyword_task = self._keyword_search(request)
        
        semantic_results, keyword_results = await asyncio.gather(
            semantic_task, keyword_task
        )
        
        # Merge results, preferring semantic matches
        seen_ids = set()
        merged = []
        
        # Add semantic results first
        for result in semantic_results:
            if result.capsule.id not in seen_ids:
                seen_ids.add(result.capsule.id)
                merged.append(result)
        
        # Add keyword results that weren't in semantic
        for result in keyword_results:
            if result.capsule.id not in seen_ids:
                seen_ids.add(result.capsule.id)
                # Slightly lower score for keyword-only matches
                result.score *= 0.9
                merged.append(result)
        
        # Re-sort by score
        merged.sort(key=lambda r: r.score, reverse=True)
        
        return merged
    
    async def _exact_search(self, request: SearchRequest) -> list[SearchResultItem]:
        """Search for exact content match."""
        if not self._db:
            return []
        
        query = """
        MATCH (capsule:Capsule)
        WHERE capsule.content CONTAINS $query
           OR capsule.title CONTAINS $query
        RETURN capsule {.*} AS capsule
        ORDER BY capsule.created_at DESC
        LIMIT $limit
        """
        
        try:
            results = await self._db.execute(
                query,
                {"query": request.query, "limit": request.limit},
            )
            
            return [
                SearchResultItem(
                    capsule=self._dict_to_capsule(r["capsule"]),
                    score=1.0,  # Exact match
                    highlights=[request.query],
                    match_type="exact",
                )
                for r in results
                if r.get("capsule")
            ]
        except Exception as e:
            logger.warning("exact_search_failed", error=str(e))
            return []
    
    def _apply_boosts(
        self,
        results: list[SearchResultItem],
        request: SearchRequest,
    ) -> list[SearchResultItem]:
        """Apply recency and popularity boosts to scores."""
        now = datetime.now(timezone.utc)
        
        for result in results:
            if request.boost_recent and result.capsule.created_at:
                # Boost recent capsules (within last 30 days)
                age_days = (now - result.capsule.created_at).days
                if age_days < 30:
                    recency_boost = 1.0 + (0.1 * (30 - age_days) / 30)
                    result.score *= recency_boost
            
            if request.boost_popular:
                # Boost popular capsules (high views/forks)
                views = result.capsule.view_count or 0
                forks = result.capsule.fork_count or 0
                
                if views > 100 or forks > 10:
                    popularity_boost = 1.0 + min(0.2, (views / 1000) + (forks / 50))
                    result.score *= popularity_boost
        
        # Re-sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        
        # Normalize scores to max 1.0
        if results and results[0].score > 1.0:
            max_score = results[0].score
            for result in results:
                result.score = result.score / max_score
        
        return results
    
    def _filter_by_score(
        self,
        results: list[SearchResultItem],
        min_score: float,
    ) -> list[SearchResultItem]:
        """Filter results by minimum score."""
        return [r for r in results if r.score >= min_score]
    
    def _extract_highlights(
        self,
        content: str,
        terms: list[str],
        context_chars: int = 100,
    ) -> list[str]:
        """Extract highlighted snippets around matching terms."""
        highlights = []
        content_lower = content.lower()
        
        for term in terms:
            term_lower = term.lower()
            pos = content_lower.find(term_lower)
            
            if pos != -1:
                start = max(0, pos - context_chars)
                end = min(len(content), pos + len(term) + context_chars)
                
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                
                highlights.append(snippet)
                
                if len(highlights) >= 3:  # Max 3 highlights
                    break
        
        return highlights
    
    def _dict_to_capsule(self, data: dict) -> Capsule:
        """Convert dict to Capsule model."""
        from forge.models.capsule import Capsule
        from forge.models.base import TrustLevel, CapsuleType
        
        # Handle trust level
        trust_value = data.get("trust_level", 60)
        if isinstance(trust_value, str):
            try:
                trust_level = TrustLevel[trust_value.upper()]
            except KeyError:
                trust_level = TrustLevel.STANDARD
        elif isinstance(trust_value, int):
            trust_level = TrustLevel.from_value(trust_value)
        else:
            trust_level = TrustLevel.STANDARD
        
        # Handle capsule type
        type_value = data.get("type", "knowledge")
        if isinstance(type_value, str):
            try:
                capsule_type = CapsuleType[type_value.upper()]
            except KeyError:
                capsule_type = CapsuleType.KNOWLEDGE
        else:
            capsule_type = CapsuleType.KNOWLEDGE
        
        return Capsule(
            id=data.get("id", ""),
            content=data.get("content", ""),
            type=capsule_type,
            title=data.get("title"),
            summary=data.get("summary"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            version=data.get("version", "1.0.0"),
            owner_id=data.get("owner_id", ""),
            trust_level=trust_level,
            parent_id=data.get("parent_id"),
            is_archived=data.get("is_archived", False),
            view_count=data.get("view_count", 0),
            fork_count=data.get("fork_count", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


# =============================================================================
# Global Instance
# =============================================================================

_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get the global search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


def init_search_service(
    embedding_service: Optional[EmbeddingService] = None,
    capsule_repo: Optional[Any] = None,
    db_client: Optional[Any] = None,
) -> SearchService:
    """Initialize the global search service."""
    global _search_service
    _search_service = SearchService(
        embedding_service=embedding_service,
        capsule_repo=capsule_repo,
        db_client=db_client,
    )
    return _search_service


def shutdown_search_service() -> None:
    """Shutdown the global search service."""
    global _search_service
    _search_service = None


__all__ = [
    "SearchMode",
    "SearchFilters",
    "SearchRequest",
    "SearchResultItem",
    "SearchResponse",
    "SearchService",
    "get_search_service",
    "init_search_service",
    "shutdown_search_service",
]
