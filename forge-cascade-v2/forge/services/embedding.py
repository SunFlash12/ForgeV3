"""
Forge Cascade V2 - Embedding Service

Generates vector embeddings for semantic search on capsules.
Supports multiple embedding providers:
- OpenAI (text-embedding-3-small, text-embedding-3-large, ada-002)
- Local sentence-transformers (all-MiniLM-L6-v2, etc.)
- Mock embeddings for testing

The default dimension is 1536 to match Neo4j vector index configuration.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import struct

import structlog

logger = structlog.get_logger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    MOCK = "mock"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding service."""
    provider: EmbeddingProvider = EmbeddingProvider.MOCK
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3
    timeout_seconds: float = 30.0
    cache_enabled: bool = True
    normalize: bool = True
    # Cost optimization: Configurable cache size (default 50000 for better hit rates)
    cache_size: int = 50000


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


class MockEmbeddingProvider(EmbeddingProviderBase):
    """
    Mock embedding provider for testing.
    
    Generates deterministic embeddings based on text hash.
    This allows consistent results for testing while
    maintaining semantic similarity properties (same text = same embedding).
    """
    
    def __init__(self, dimensions: int = 1536):
        self._dimensions = dimensions
    
    def get_dimensions(self) -> int:
        return self._dimensions
    
    def _hash_to_embedding(self, text: str) -> list[float]:
        """Convert text hash to normalized embedding vector."""
        # Use SHA-256 to get deterministic bytes
        text_bytes = text.encode('utf-8')
        hash_bytes = hashlib.sha256(text_bytes).digest()
        
        # Extend hash to fill dimensions
        extended = bytearray()
        counter = 0
        while len(extended) < self._dimensions * 4:
            combined = text_bytes + counter.to_bytes(4, 'big')
            extended.extend(hashlib.sha256(combined).digest())
            counter += 1
        
        # Convert to floats in range [-1, 1]
        embedding = []
        for i in range(self._dimensions):
            # Take 4 bytes and convert to float
            chunk = bytes(extended[i*4:(i+1)*4])
            # Convert to unsigned int, then scale to [-1, 1]
            value = struct.unpack('>I', chunk)[0]
            normalized = (value / (2**32 - 1)) * 2 - 1
            embedding.append(normalized)
        
        # L2 normalize
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding
    
    async def embed(self, text: str) -> EmbeddingResult:
        """Generate mock embedding."""
        # Simulate small delay
        await asyncio.sleep(0.001)
        
        embedding = self._hash_to_embedding(text)
        
        return EmbeddingResult(
            embedding=embedding,
            model="mock-embedding",
            dimensions=self._dimensions,
            tokens_used=len(text.split()),
            cached=False,
        )
    
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate mock embeddings for batch."""
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
        return results


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
        dimensions: Optional[int] = None,
        api_base: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._model = model
        self._api_base = api_base or "https://api.openai.com/v1"
        self._timeout = timeout
        # SECURITY FIX (Audit 3): Reuse HTTP client instead of creating new one per request
        self._http_client: Optional["httpx.AsyncClient"] = None

        # Determine dimensions
        if dimensions:
            self._dimensions = dimensions
        else:
            self._dimensions = self.MODEL_DIMENSIONS.get(model, 1536)
    
    def get_dimensions(self) -> int:
        return self._dimensions

    def _get_client(self) -> "httpx.AsyncClient":
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
            payload["dimensions"] = self._dimensions

        # SECURITY FIX (Audit 3): Reuse HTTP client
        client = self._get_client()
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for i, item in enumerate(data.get("data", [])):
            embedding = item["embedding"]
            
            # Normalize if needed
            magnitude = sum(x**2 for x in embedding) ** 0.5
            if magnitude > 0:
                embedding = [x / magnitude for x in embedding]
            
            results.append(EmbeddingResult(
                embedding=embedding,
                model=self._model,
                dimensions=len(embedding),
                tokens_used=data.get("usage", {}).get("total_tokens", 0) // len(texts),
                cached=False,
            ))
        
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
    
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self._model_name = model
        self._model = None
        self._dimensions = None
    
    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                # Get dimensions from a test embedding
                test = self._model.encode(["test"])
                self._dimensions = len(test[0])
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
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self._model.encode(texts, normalize_embeddings=True)
        )
        
        results = []
        for embedding in embeddings:
            results.append(EmbeddingResult(
                embedding=embedding.tolist(),
                model=self._model_name,
                dimensions=len(embedding),
                tokens_used=0,  # Local, no token counting
                cached=False,
            ))
        
        return results


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

    async def get(self, text: str, model: str) -> Optional[EmbeddingResult]:
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
                keys_to_remove = list(self._cache.keys())[:self._max_size // 10]
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
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self._config = config or EmbeddingConfig()
        self._provider = self._create_provider()
        # Use configurable cache size for cost optimization
        self._cache = EmbeddingCache(max_size=self._config.cache_size) if self._config.cache_enabled else None
        
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
        
        else:  # MOCK
            return MockEmbeddingProvider(dimensions=self._config.dimensions)
    
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
    
    async def embed_batch(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to log progress
            
        Returns:
            List of EmbeddingResults in same order as input
        """
        if not texts:
            return []
        
        results: list[Optional[EmbeddingResult]] = [None] * len(texts)
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
                batch = texts_to_embed[batch_start:batch_start + batch_size]
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
                    except Exception as e:
                        if attempt == self._config.max_retries - 1:
                            raise
                        logger.warning(
                            "embedding_batch_retry",
                            attempt=attempt + 1,
                            error=str(e),
                        )
                        await asyncio.sleep(2 ** attempt)
                
                # Store results and cache
                for (original_idx, text), result in zip(batch, batch_results):
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


# =============================================================================
# Global Instance
# =============================================================================

_embedding_service: Optional[EmbeddingService] = None


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
    """Shutdown the global embedding service."""
    global _embedding_service
    _embedding_service = None


# =============================================================================
# Utility Functions
# =============================================================================

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimensions")
    
    dot_product = sum(x * y for x, y in zip(a, b))
    magnitude_a = sum(x ** 2 for x in a) ** 0.5
    magnitude_b = sum(x ** 2 for x in b) ** 0.5
    
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    
    return dot_product / (magnitude_a * magnitude_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Calculate Euclidean distance between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimensions")
    
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


__all__ = [
    "EmbeddingProvider",
    "EmbeddingConfig",
    "EmbeddingResult",
    "EmbeddingService",
    "get_embedding_service",
    "init_embedding_service",
    "shutdown_embedding_service",
    "cosine_similarity",
    "euclidean_distance",
]
