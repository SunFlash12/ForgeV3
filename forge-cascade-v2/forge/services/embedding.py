"""
Forge Cascade V2 - Embedding Service

Generates vector embeddings for semantic search on capsules.
Supports multiple embedding providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large, ada-002)
- Local sentence-transformers (all-MiniLM-L6-v2, etc.)

The default dimension is 1536 to match Neo4j vector index configuration.

IMPORTANT: A real embedding provider is REQUIRED for Forge to function.
Set OPENAI_API_KEY for cloud embeddings, or install sentence-transformers for local.
"""

from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    import httpx

logger = structlog.get_logger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    MOCK = "mock"  # For testing and fallback when no real provider available


class EmbeddingConfigurationError(Exception):
    """Raised when embedding provider is not properly configured."""

    pass


@dataclass
class EmbeddingConfig:
    """
    Configuration for embedding service.

    SECURITY FIX (Audit 4 - H24): API keys are loaded from environment
    variables and are redacted in logs/repr to prevent exposure.
    """

    provider: EmbeddingProvider = EmbeddingProvider.SENTENCE_TRANSFORMERS
    model: str = "all-MiniLM-L6-v2"  # Default to local model
    dimensions: int = 1536
    api_key: str | None = None  # SECURITY: Load from env, redact in logs
    api_base: str | None = None
    batch_size: int = 100
    max_retries: int = 3
    timeout_seconds: float = 30.0
    cache_enabled: bool = True
    normalize: bool = True
    # Cost optimization: Configurable cache size (default 50000 for better hit rates)
    cache_size: int = 50000

    def __repr__(self) -> str:
        """SECURITY FIX: Redact API key in repr/logs."""
        return (
            f"EmbeddingConfig(provider={self.provider}, model={self.model}, "
            f"dimensions={self.dimensions}, api_key={'[REDACTED]' if self.api_key else None}, "
            f"batch_size={self.batch_size})"
        )

    def to_safe_dict(self) -> dict[str, Any]:
        """Return config dict with sensitive values redacted."""
        return {
            "provider": self.provider.value
            if hasattr(self.provider, "value")
            else str(self.provider),
            "model": self.model,
            "dimensions": self.dimensions,
            "api_key": "[REDACTED]" if self.api_key else None,
            "api_base": self.api_base,
            "batch_size": self.batch_size,
            "cache_enabled": self.cache_enabled,
        }


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    embedding: list[float]
    model: str
    dimensions: int
    tokens_used: int = 0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "embedding": self.embedding,
            "model": self.model,
            "dimensions": self.dimensions,
            "tokens_used": self.tokens_used,
            "cached": self.cached,
        }


class EmbeddingProviderBase(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts."""
        pass

    @abstractmethod
    def get_dimensions(self) -> int:
        """Get the embedding dimensions."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    """
    OpenAI embedding provider.

    Supports:
    - text-embedding-3-small (1536 dimensions)
    - text-embedding-3-large (3072 dimensions, configurable)
    - text-embedding-ada-002 (1536 dimensions, legacy)
    """

    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
        api_base: str | None = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._model = model
        self._api_base = api_base or "https://api.openai.com/v1"
        self._timeout = timeout
        # SECURITY FIX (Audit 3): Reuse HTTP client instead of creating new one per request
        self._http_client: httpx.AsyncClient | None = None

        # Determine dimensions
        if dimensions:
            self._dimensions = dimensions
        else:
            self._dimensions = self.MODEL_DIMENSIONS.get(model, 1536)

    def get_dimensions(self) -> int:
        return self._dimensions

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client (lazy initialization)."""
        import httpx

        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._timeout)
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding via OpenAI API."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for batch via OpenAI API."""
        url = f"{self._api_base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "input": texts,
            "model": self._model,
        }

        # For text-embedding-3-* models, dimensions can be specified
        if self._model.startswith("text-embedding-3"):
            payload["dimensions"] = self._dimensions  # type: ignore[assignment]

        # SECURITY FIX (Audit 3): Reuse HTTP client
        client = self._get_client()
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        results = []
        for _i, item in enumerate(data.get("data", [])):
            embedding = item["embedding"]

            # Normalize if needed
            magnitude = sum(x**2 for x in embedding) ** 0.5
            if magnitude > 0:
                embedding = [x / magnitude for x in embedding]

            results.append(
                EmbeddingResult(
                    embedding=embedding,
                    model=self._model,
                    dimensions=len(embedding),
                    tokens_used=data.get("usage", {}).get("total_tokens", 0) // len(texts),
                    cached=False,
                )
            )

        return results


class SentenceTransformersProvider(EmbeddingProviderBase):
    """
    Local sentence-transformers embedding provider.

    Runs locally without API calls. Good for:
    - Development/testing
    - Privacy-sensitive deployments
    - Cost optimization

    Recommended models:
    - all-MiniLM-L6-v2 (384 dims, fast)
    - all-mpnet-base-v2 (768 dims, better quality)
    - all-MiniLM-L12-v2 (384 dims, balanced)
    """

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model
        self._model: Any = None
        self._dimensions: int | None = None

    def _load_model(self) -> None:
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
                # Get dimensions from a test embedding
                test = self._model.encode(["test"])
                self._dimensions = int(len(test[0]))
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

    def get_dimensions(self) -> int:
        self._load_model()
        return self._dimensions or 384

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding locally."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings locally."""
        self._load_model()

        # Run in thread pool to not block async loop
        # SECURITY FIX (Audit 4): Use get_running_loop() instead of deprecated get_event_loop()
        loop = asyncio.get_running_loop()
        model = self._model
        embeddings = await loop.run_in_executor(
            None, lambda: model.encode(texts, normalize_embeddings=True)
        )

        results = []
        for embedding in embeddings:
            results.append(
                EmbeddingResult(
                    embedding=embedding.tolist(),
                    model=self._model_name,
                    dimensions=len(embedding),
                    tokens_used=0,  # Local, no token counting
                    cached=False,
                )
            )

        return results


class MockEmbeddingProvider(EmbeddingProviderBase):
    """
    Mock embedding provider for testing and fallback.

    Generates deterministic pseudo-embeddings based on text hash.
    This allows basic functionality when no real embedding provider
    is available, though semantic search quality will be poor.

    NOT RECOMMENDED FOR PRODUCTION USE.
    Install sentence-transformers for proper local embeddings.
    """

    def __init__(self, dimensions: int = 1536):
        self._dimensions = dimensions
        logger.warning(
            "mock_embedding_provider_initialized",
            warning="Using mock embeddings. Semantic search will not work properly.",
            hint="Install sentence-transformers or set OPENAI_API_KEY for real embeddings.",
        )

    def get_dimensions(self) -> int:
        return self._dimensions

    def _generate_mock_embedding(self, text: str) -> list[float]:
        """Generate a deterministic pseudo-embedding from text hash."""
        import random

        # Use text hash as seed for reproducibility
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
        seed = int(text_hash[:8], 16)
        rng = random.Random(seed)

        # Generate normalized random vector
        embedding = [rng.gauss(0, 1) for _ in range(self._dimensions)]
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate mock embedding."""
        return EmbeddingResult(
            embedding=self._generate_mock_embedding(text),
            model="mock",
            dimensions=self._dimensions,
            tokens_used=0,
            cached=False,
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate mock embeddings for batch."""
        return [
            EmbeddingResult(
                embedding=self._generate_mock_embedding(text),
                model="mock",
                dimensions=self._dimensions,
                tokens_used=0,
                cached=False,
            )
            for text in texts
        ]


class EmbeddingCache:
    """Simple in-memory cache for embeddings with thread-safe operations."""

    # Cost optimization: Increased default from 10000 to 50000 for better hit rates
    def __init__(self, max_size: int = 50000):
        self._cache: dict[str, EmbeddingResult] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        # SECURITY FIX (Audit 3): Add lock to prevent race conditions in cache operations
        import asyncio

        self._lock = asyncio.Lock()

    def _make_key(self, text: str, model: str) -> str:
        """Create cache key from text and model."""
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()

    async def get(self, text: str, model: str) -> EmbeddingResult | None:
        """Get cached embedding if exists (thread-safe)."""
        key = self._make_key(text, model)
        # SECURITY FIX (Audit 3): Use lock for thread-safe cache access
        async with self._lock:
            if key in self._cache:
                self._hits += 1
                result = self._cache[key]
                result.cached = True
                return result
            self._misses += 1
            return None

    async def set(self, text: str, model: str, result: EmbeddingResult) -> None:
        """Cache an embedding result (thread-safe)."""
        # SECURITY FIX (Audit 3): Use lock for thread-safe cache modification
        async with self._lock:
            if len(self._cache) >= self._max_size:
                # Simple eviction: remove oldest 10%
                keys_to_remove = list(self._cache.keys())[: self._max_size // 10]
                for key in keys_to_remove:
                    del self._cache[key]

            key = self._make_key(text, model)
            self._cache[key] = result

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics (thread-safe)."""
        async with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0,
            }

    async def clear(self) -> None:
        """Clear the cache (thread-safe)."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


class EmbeddingService:
    """
    Main embedding service for Forge.

    Provides a unified interface for generating embeddings
    across different providers with caching support.

    Usage:
        service = EmbeddingService(EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            api_key="sk-..."
        ))

        result = await service.embed("Knowledge about Python")
        # result.embedding is a 1536-dimensional vector

        # Batch embedding
        results = await service.embed_batch([
            "First capsule content",
            "Second capsule content",
        ])
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        self._config = config or EmbeddingConfig()
        self._provider = self._create_provider()
        # Use configurable cache size for cost optimization
        self._cache = (
            EmbeddingCache(max_size=self._config.cache_size) if self._config.cache_enabled else None
        )

        logger.info(
            "embedding_service_initialized",
            provider=self._config.provider.value,
            model=self._config.model,
            dimensions=self._config.dimensions,
            cache_enabled=self._config.cache_enabled,
        )

    def _create_provider(self) -> EmbeddingProviderBase:
        """Create the appropriate provider based on config."""
        if self._config.provider == EmbeddingProvider.OPENAI:
            if not self._config.api_key:
                raise ValueError("OpenAI API key required for OpenAI provider")
            return OpenAIEmbeddingProvider(
                api_key=self._config.api_key,
                model=self._config.model,
                dimensions=self._config.dimensions,
                api_base=self._config.api_base,
                timeout=self._config.timeout_seconds,
            )

        elif self._config.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
            return SentenceTransformersProvider(model=self._config.model)

        elif self._config.provider == EmbeddingProvider.MOCK:
            return MockEmbeddingProvider(dimensions=self._config.dimensions)

        else:
            raise EmbeddingConfigurationError(
                f"Unsupported embedding provider: {self._config.provider}. "
                "Supported providers: openai, sentence_transformers, mock. "
                "Set OPENAI_API_KEY for cloud embeddings, or install sentence-transformers for local."
            )

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return self._provider.get_dimensions()

    async def embed(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            EmbeddingResult with the embedding vector
        """
        # Check cache
        if self._cache:
            cached = await self._cache.get(text, self._config.model)
            if cached:
                logger.debug("embedding_cache_hit", text_length=len(text))
                return cached

        # Generate embedding
        result = await self._provider.embed(text)

        # Cache result
        if self._cache:
            await self._cache.set(text, self._config.model, result)

        logger.debug(
            "embedding_generated",
            text_length=len(text),
            dimensions=result.dimensions,
            tokens=result.tokens_used,
        )

        return result

    # SECURITY FIX (Audit 4 - H25): Maximum batch size to prevent cost abuse
    MAX_BATCH_SIZE = 10000

    async def embed_batch(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.

        SECURITY FIX (Audit 4 - H25): Now limits batch size to prevent
        cost abuse via unbounded embedding requests.

        Args:
            texts: List of texts to embed (max 10,000)
            show_progress: Whether to log progress

        Returns:
            List of EmbeddingResults in same order as input

        Raises:
            ValueError: If batch size exceeds MAX_BATCH_SIZE
        """
        if not texts:
            return []

        # SECURITY FIX (Audit 4 - H25): Enforce maximum batch size
        if len(texts) > self.MAX_BATCH_SIZE:
            logger.warning(
                "embedding_batch_size_exceeded",
                requested=len(texts),
                max_allowed=self.MAX_BATCH_SIZE,
            )
            raise ValueError(
                f"Batch size {len(texts)} exceeds maximum of {self.MAX_BATCH_SIZE}. "
                "Please split your request into smaller batches."
            )

        results: list[EmbeddingResult | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        # Check cache for each text
        for i, text in enumerate(texts):
            if self._cache:
                cached = await self._cache.get(text, self._config.model)
                if cached:
                    results[i] = cached
                    continue
            texts_to_embed.append((i, text))

        cache_hits = len(texts) - len(texts_to_embed)
        if cache_hits > 0:
            logger.debug("embedding_batch_cache_hits", hits=cache_hits, total=len(texts))

        # Batch embed remaining texts
        if texts_to_embed:
            batch_size = self._config.batch_size

            for batch_start in range(0, len(texts_to_embed), batch_size):
                batch = texts_to_embed[batch_start : batch_start + batch_size]
                batch_texts = [t for _, t in batch]

                if show_progress:
                    logger.info(
                        "embedding_batch_progress",
                        batch=batch_start // batch_size + 1,
                        total_batches=(len(texts_to_embed) + batch_size - 1) // batch_size,
                    )

                # Retry logic
                for attempt in range(self._config.max_retries):
                    try:
                        batch_results = await self._provider.embed_batch(batch_texts)
                        break
                    except (ConnectionError, TimeoutError, ValueError, OSError) as e:
                        if attempt == self._config.max_retries - 1:
                            raise
                        logger.warning(
                            "embedding_batch_retry",
                            attempt=attempt + 1,
                            error=str(e),
                        )
                        await asyncio.sleep(2**attempt)

                # Store results and cache
                for (original_idx, text), result in zip(batch, batch_results, strict=False):
                    results[original_idx] = result
                    if self._cache:
                        await self._cache.set(text, self._config.model, result)

        logger.info(
            "embedding_batch_complete",
            total=len(texts),
            cache_hits=cache_hits,
            generated=len(texts_to_embed),
        )

        return results  # type: ignore

    async def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        if self._cache:
            return await self._cache.stats()
        return {"cache_enabled": False}

    async def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self._cache:
            await self._cache.clear()

    async def close(self) -> None:
        """
        SECURITY FIX (Audit 5): Properly close HTTP client to prevent resource leaks.

        Close the embedding service and release resources.
        This should be called during application shutdown.
        """
        if hasattr(self._provider, "close"):
            await self._provider.close()
        if self._cache:
            await self._cache.clear()
        logger.info("embedding_service_closed")


# =============================================================================
# Global Instance
# =============================================================================

_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def init_embedding_service(config: EmbeddingConfig) -> EmbeddingService:
    """Initialize the global embedding service with config."""
    global _embedding_service
    _embedding_service = EmbeddingService(config)
    return _embedding_service


def shutdown_embedding_service() -> None:
    """
    Shutdown the global embedding service (sync version).

    NOTE: This doesn't properly close async resources.
    Use shutdown_embedding_service_async() in async contexts.
    """
    global _embedding_service
    _embedding_service = None


async def shutdown_embedding_service_async() -> None:
    """
    SECURITY FIX (Audit 5): Properly shutdown the embedding service.

    This async version properly closes the HTTP client to prevent resource leaks.
    Should be called during application shutdown in async contexts.
    """
    global _embedding_service
    if _embedding_service is not None:
        await _embedding_service.close()
        _embedding_service = None


# =============================================================================
# Utility Functions
# =============================================================================


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimensions")

    dot_product: float = sum(x * y for x, y in zip(a, b, strict=False))
    magnitude_a: float = sum(x**2 for x in a) ** 0.5
    magnitude_b: float = sum(x**2 for x in b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return float(dot_product / (magnitude_a * magnitude_b))


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimensions")

    result: float = sum((x - y) ** 2 for x, y in zip(a, b, strict=False)) ** 0.5
    return float(result)


__all__ = [
    "EmbeddingProvider",
    "EmbeddingConfig",
    "EmbeddingConfigurationError",
    "EmbeddingResult",
    "EmbeddingService",
    "get_embedding_service",
    "init_embedding_service",
    "shutdown_embedding_service",
    "shutdown_embedding_service_async",
    "cosine_similarity",
    "euclidean_distance",
]
