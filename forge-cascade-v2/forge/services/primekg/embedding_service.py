"""
PrimeKG Embedding Service

Generates and manages vector embeddings for PrimeKG clinical descriptions.
Used for semantic search and similarity-based disease matching.

Supports:
- OpenAI embeddings (text-embedding-3-small/large)
- Local embeddings (sentence-transformers)
- Batch processing with rate limiting
- Caching to avoid re-computation
"""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        ...


@dataclass
class EmbeddingProgress:
    """Progress tracking for embedding generation."""
    total_items: int = 0
    processed_items: int = 0
    cached_items: int = 0
    failed_items: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def progress_percent(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100


class OpenAIEmbeddingProvider:
    """
    OpenAI embedding provider.

    Uses text-embedding-3-small by default (1536 dimensions).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package required for OpenAI embeddings")

        self._model = model
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimensions,
        )
        embedding: list[float] = list(response.data[0].embedding)
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (max 2048 per request)."""
        if not texts:
            return []

        batch_size = 2048
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
                dimensions=self._dimensions,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings


class LocalEmbeddingProvider:
    """
    Local embedding provider using sentence-transformers.

    Uses all-MiniLM-L6-v2 by default (384 dimensions).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        try:
            from sentence_transformers import SentenceTransformer
            self._model: Any = SentenceTransformer(model_name)
            dim = self._model.get_sentence_embedding_dimension()
            self._dimensions: int = int(dim) if dim is not None else 384
        except ImportError:
            raise ImportError("sentence-transformers package required for local embeddings")

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        # Run in executor since sentence-transformers is sync
        loop = asyncio.get_event_loop()
        embedding: list[float] = await loop.run_in_executor(
            None,
            lambda: list(self._model.encode(text).tolist())
        )
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        loop = asyncio.get_event_loop()
        embeddings: list[list[float]] = await loop.run_in_executor(
            None,
            lambda: [list(e) for e in self._model.encode(texts).tolist()]
        )
        return embeddings


class PrimeKGEmbeddingService:
    """
    Service for generating and managing PrimeKG embeddings.

    Features:
    - Batch embedding generation
    - LRU caching by content hash
    - Rate limiting for API providers
    - Progress tracking
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        neo4j_client: Any = None,
        cache_dir: Path | None = None,
        batch_size: int = 100,
        rate_limit_per_minute: int = 3000,
    ):
        """
        Initialize the embedding service.

        Args:
            provider: Embedding provider (OpenAI or local)
            neo4j_client: Optional Neo4j client for storing embeddings
            cache_dir: Directory for caching embeddings
            batch_size: Items per batch
            rate_limit_per_minute: Max requests per minute
        """
        self.provider = provider
        self.neo4j = neo4j_client
        self.cache_dir = cache_dir
        self.batch_size = batch_size
        self.rate_limit = rate_limit_per_minute

        # In-memory cache (LRU)
        self._cache: dict[str, list[float]] = {}
        self._cache_max_size = 10000

        # Rate limiting
        self._request_times: list[datetime] = []

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return self.provider.dimensions

    def _cache_key(self, text: str) -> str:
        """Generate cache key from text content."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = datetime.now(UTC)
        minute_ago = now.timestamp() - 60

        # Remove old request times
        self._request_times = [
            t for t in self._request_times
            if t.timestamp() > minute_ago
        ]

        # Wait if at limit
        if len(self._request_times) >= self.rate_limit:
            wait_time = 60 - (now.timestamp() - self._request_times[0].timestamp())
            if wait_time > 0:
                logger.debug("primekg_rate_limit_wait", seconds=wait_time)
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Uses cache if available.
        """
        cache_key = self._cache_key(text)

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Rate limit
        await self._wait_for_rate_limit()

        # Generate embedding
        embedding = await self.provider.embed(text)

        # Cache result
        self._add_to_cache(cache_key, embedding)

        return embedding

    async def embed_texts(
        self,
        texts: list[str],
        progress_callback: Callable[[EmbeddingProgress], None] | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            progress_callback: Optional callback for progress updates

        Returns:
            List of embeddings in same order as inputs
        """
        progress = EmbeddingProgress(
            total_items=len(texts),
            started_at=datetime.now(UTC),
        )

        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
                progress.cached_items += 1
            else:
                texts_to_embed.append((i, text))

        logger.info(
            "primekg_embedding_cache_hits",
            total=len(texts),
            cached=progress.cached_items,
            to_embed=len(texts_to_embed)
        )

        # Batch embed remaining texts
        for batch_start in range(0, len(texts_to_embed), self.batch_size):
            batch = texts_to_embed[batch_start:batch_start + self.batch_size]
            batch_texts = [text for _, text in batch]

            await self._wait_for_rate_limit()

            try:
                embeddings = await self.provider.embed_batch(batch_texts)

                for (idx, text), embedding in zip(batch, embeddings, strict=False):
                    results[idx] = embedding
                    self._add_to_cache(self._cache_key(text), embedding)
                    progress.processed_items += 1

            except Exception as e:
                logger.error("primekg_embedding_batch_error", error=str(e))
                progress.failed_items += len(batch)

            if progress_callback:
                progress_callback(progress)

        progress.completed_at = datetime.now(UTC)

        # Filter out None values (should not happen if no errors)
        return [e if e is not None else [] for e in results]

    def _add_to_cache(self, key: str, embedding: list[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO, not true LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = embedding

    async def embed_primekg_nodes(
        self,
        node_type: str | None = None,
        batch_size: int = 100,
        progress_callback: Callable[[EmbeddingProgress], None] | None = None,
    ) -> int:
        """
        Generate embeddings for PrimeKG nodes and store in Neo4j.

        Args:
            node_type: Optional filter by node type (e.g., 'disease')
            batch_size: Nodes per batch
            progress_callback: Progress callback

        Returns:
            Number of nodes embedded
        """
        if not self.neo4j:
            raise ValueError("Neo4j client required for node embedding")

        # Query nodes without embeddings
        where_clause = "WHERE n.embedding IS NULL"
        if node_type:
            where_clause += f" AND n.node_type = '{node_type}'"

        count_query = f"""
        MATCH (n:PrimeKGNode)
        {where_clause}
        RETURN count(n) as count
        """
        count_result = await self.neo4j.run(count_query)
        total_nodes = count_result[0]["count"] if count_result else 0

        if total_nodes == 0:
            logger.info("primekg_no_nodes_to_embed")
            return 0

        logger.info("primekg_embedding_nodes", total=total_nodes, type=node_type)

        progress = EmbeddingProgress(
            total_items=total_nodes,
            started_at=datetime.now(UTC),
        )

        embedded_count = 0
        skip = 0

        while skip < total_nodes:
            # Fetch batch of nodes
            fetch_query = f"""
            MATCH (n:PrimeKGNode)
            {where_clause}
            RETURN n.node_index as node_index,
                   n.name as name,
                   n.node_type as type,
                   n.description as description
            SKIP {skip}
            LIMIT {batch_size}
            """
            nodes = await self.neo4j.run(fetch_query)

            if not nodes:
                break

            # Generate text for embedding
            texts = []
            node_indices = []
            for node in nodes:
                # Combine name and description for richer embedding
                text_parts = [node["name"]]
                if node.get("description"):
                    text_parts.append(node["description"])
                text = " - ".join(text_parts)

                texts.append(text)
                node_indices.append(node["node_index"])

            # Generate embeddings
            await self._wait_for_rate_limit()

            try:
                embeddings = await self.provider.embed_batch(texts)

                # Store embeddings in Neo4j
                update_query = """
                UNWIND $updates AS update
                MATCH (n:PrimeKGNode {node_index: update.node_index})
                SET n.embedding = update.embedding,
                    n.embedded_at = datetime()
                """
                updates = [
                    {"node_index": idx, "embedding": emb}
                    for idx, emb in zip(node_indices, embeddings, strict=False)
                ]
                await self.neo4j.run(update_query, {"updates": updates})

                embedded_count += len(embeddings)
                progress.processed_items += len(embeddings)

            except Exception as e:
                logger.error("primekg_node_embedding_error", error=str(e))
                progress.failed_items += len(texts)

            skip += batch_size

            if progress_callback:
                progress_callback(progress)

        progress.completed_at = datetime.now(UTC)
        if progress.completed_at is not None and progress.started_at is not None:
            duration = (progress.completed_at - progress.started_at).total_seconds()
        else:
            duration = 0.0
        logger.info(
            "primekg_nodes_embedded",
            count=embedded_count,
            duration_seconds=duration
        )

        return embedded_count

    async def semantic_search(
        self,
        query: str,
        node_type: str | None = None,
        limit: int = 10,
        min_score: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search on PrimeKG nodes.

        Args:
            query: Search query text
            node_type: Optional filter by node type
            limit: Maximum results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of matching nodes with scores
        """
        if not self.neo4j:
            raise ValueError("Neo4j client required for semantic search")

        # Generate query embedding
        query_embedding = await self.embed_text(query)

        # Build search query
        type_filter = ""
        if node_type:
            type_filter = f"AND n.node_type = '{node_type}'"

        search_query = f"""
        CALL db.index.vector.queryNodes(
            'primekg_embedding',
            {limit * 2},
            $embedding
        ) YIELD node, score
        WHERE score >= {min_score} {type_filter}
        RETURN node.node_index as node_index,
               node.node_id as node_id,
               node.name as name,
               node.node_type as type,
               node.description as description,
               score
        ORDER BY score DESC
        LIMIT {limit}
        """

        results = await self.neo4j.run(search_query, {"embedding": query_embedding})

        return [
            {
                "node_index": r["node_index"],
                "node_id": r["node_id"],
                "name": r["name"],
                "type": r["type"],
                "description": r["description"],
                "score": r["score"],
            }
            for r in results
        ]

    async def find_similar_nodes(
        self,
        node_index: int,
        limit: int = 10,
        same_type_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Find nodes similar to a given node.

        Args:
            node_index: Source node index
            limit: Maximum results
            same_type_only: Only return nodes of same type

        Returns:
            List of similar nodes with scores
        """
        if not self.neo4j:
            raise ValueError("Neo4j client required")

        # Get source node embedding
        source_query = """
        MATCH (n:PrimeKGNode {node_index: $node_index})
        RETURN n.embedding as embedding, n.node_type as type
        """
        source = await self.neo4j.run(source_query, {"node_index": node_index})

        if not source or not source[0].get("embedding"):
            return []

        source_embedding = source[0]["embedding"]
        source_type = source[0]["type"]

        # Find similar nodes
        type_filter = f"AND n.node_type = '{source_type}'" if same_type_only else ""

        search_query = f"""
        CALL db.index.vector.queryNodes(
            'primekg_embedding',
            {limit + 1},
            $embedding
        ) YIELD node, score
        WHERE node.node_index <> $node_index {type_filter}
        RETURN node.node_index as node_index,
               node.node_id as node_id,
               node.name as name,
               node.node_type as type,
               score
        ORDER BY score DESC
        LIMIT {limit}
        """

        results = await self.neo4j.run(
            search_query,
            {"embedding": source_embedding, "node_index": node_index}
        )

        return [
            {
                "node_index": r["node_index"],
                "node_id": r["node_id"],
                "name": r["name"],
                "type": r["type"],
                "score": r["score"],
            }
            for r in results
        ]


# =============================================================================
# Factory Functions
# =============================================================================

def create_openai_embedding_service(
    api_key: str,
    neo4j_client: Any = None,
    model: str = "text-embedding-3-small",
) -> PrimeKGEmbeddingService:
    """Create embedding service with OpenAI provider."""
    provider = OpenAIEmbeddingProvider(api_key=api_key, model=model)
    return PrimeKGEmbeddingService(provider=provider, neo4j_client=neo4j_client)


def create_local_embedding_service(
    neo4j_client: Any = None,
    model_name: str = "all-MiniLM-L6-v2",
) -> PrimeKGEmbeddingService:
    """Create embedding service with local provider."""
    provider = LocalEmbeddingProvider(model_name=model_name)
    return PrimeKGEmbeddingService(provider=provider, neo4j_client=neo4j_client)
