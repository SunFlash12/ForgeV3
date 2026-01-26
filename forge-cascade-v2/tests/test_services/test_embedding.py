"""
Tests for Embedding Service

Tests cover:
- Mock provider functionality
- Embedding generation
- Batch embedding
- Caching behavior
- Similarity calculations
"""

import pytest

from forge.services.embedding import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
    cosine_similarity,
    euclidean_distance,
)


class TestEmbeddingConfig:
    """Tests for embedding configuration."""

    def test_default_config(self):
        config = EmbeddingConfig()
        assert config.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS
        assert config.dimensions == 1536
        assert config.cache_enabled is True

    def test_custom_config(self):
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-large",
            dimensions=3072,
            api_key="test-key",
        )
        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == "text-embedding-3-large"
        assert config.dimensions == 3072


class TestMockEmbeddingProvider:
    """Tests for mock embedding provider."""

    @pytest.fixture
    def service(self):
        config = EmbeddingConfig(provider=EmbeddingProvider.MOCK)
        return EmbeddingService(config)

    @pytest.mark.asyncio
    async def test_embed_single(self, service):
        result = await service.embed("Hello, world!")

        assert isinstance(result, EmbeddingResult)
        assert len(result.embedding) == 1536
        assert result.model == "mock"
        assert result.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_deterministic(self, service):
        """Same text should produce same embedding."""
        text = "Test content for embedding"

        result1 = await service.embed(text)
        result2 = await service.embed(text)

        assert result1.embedding == result2.embedding

    @pytest.mark.asyncio
    async def test_embed_different_text(self, service):
        """Different text should produce different embeddings."""
        result1 = await service.embed("First text")
        result2 = await service.embed("Second text")

        assert result1.embedding != result2.embedding

    @pytest.mark.asyncio
    async def test_embed_normalized(self, service):
        """Embeddings should be L2 normalized."""
        result = await service.embed("Normalize me")

        # L2 norm should be approximately 1
        magnitude = sum(x**2 for x in result.embedding) ** 0.5
        assert abs(magnitude - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_embed_batch(self, service):
        texts = [
            "First document",
            "Second document",
            "Third document",
        ]

        results = await service.embed_batch(texts)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert len(result.embedding) == 1536

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, service):
        results = await service.embed_batch([])
        assert results == []


class TestEmbeddingCache:
    """Tests for embedding cache."""

    @pytest.fixture
    def service_with_cache(self):
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            cache_enabled=True,
        )
        return EmbeddingService(config)

    @pytest.fixture
    def service_without_cache(self):
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            cache_enabled=False,
        )
        return EmbeddingService(config)

    @pytest.mark.asyncio
    async def test_cache_hit(self, service_with_cache):
        text = "Cache this text"

        # First call - cache miss
        result1 = await service_with_cache.embed(text)
        assert result1.cached is False

        # Second call - cache hit
        result2 = await service_with_cache.embed(text)
        assert result2.cached is True

        # Results should be identical
        assert result1.embedding == result2.embedding

    @pytest.mark.asyncio
    async def test_cache_stats(self, service_with_cache):
        await service_with_cache.embed("text1")
        await service_with_cache.embed("text2")
        await service_with_cache.embed("text1")  # Cache hit

        stats = service_with_cache.cache_stats()

        assert stats["size"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 2

    @pytest.mark.asyncio
    async def test_cache_disabled(self, service_without_cache):
        text = "Not cached"

        result1 = await service_without_cache.embed(text)
        result2 = await service_without_cache.embed(text)

        # Both should be cache misses
        assert result1.cached is False
        assert result2.cached is False

        stats = service_without_cache.cache_stats()
        assert stats["cache_enabled"] is False

    @pytest.mark.asyncio
    async def test_cache_clear(self, service_with_cache):
        await service_with_cache.embed("text1")
        await service_with_cache.embed("text2")

        assert service_with_cache.cache_stats()["size"] == 2

        service_with_cache.clear_cache()

        assert service_with_cache.cache_stats()["size"] == 0


class TestSimilarityFunctions:
    """Tests for similarity utility functions."""

    def test_cosine_similarity_identical(self):
        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        similarity = cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 0.001

    def test_cosine_similarity_opposite(self):
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = cosine_similarity(vec1, vec2)
        assert abs(similarity - (-1.0)) < 0.001

    def test_cosine_similarity_mismatched_dims(self):
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0]
        with pytest.raises(ValueError):
            cosine_similarity(vec1, vec2)

    def test_euclidean_distance_same_point(self):
        vec = [1.0, 2.0, 3.0]
        distance = euclidean_distance(vec, vec)
        assert abs(distance - 0.0) < 0.001

    def test_euclidean_distance_unit_vectors(self):
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        distance = euclidean_distance(vec1, vec2)
        assert abs(distance - 1.0) < 0.001


class TestSemanticSimilarity:
    """Tests for semantic similarity using mock embeddings."""

    @pytest.fixture
    def service(self):
        config = EmbeddingConfig(provider=EmbeddingProvider.MOCK)
        return EmbeddingService(config)

    @pytest.mark.asyncio
    async def test_similar_text_higher_similarity(self, service):
        """Similar texts should have higher cosine similarity."""
        # These won't actually be semantically similar with mock,
        # but we test the pipeline
        text1 = "Machine learning algorithms"
        text2 = "Machine learning algorithms"  # Identical
        text3 = "Completely different topic about cooking"

        emb1 = await service.embed(text1)
        emb2 = await service.embed(text2)
        emb3 = await service.embed(text3)

        sim_same = cosine_similarity(emb1.embedding, emb2.embedding)
        sim_diff = cosine_similarity(emb1.embedding, emb3.embedding)

        # Identical texts should have similarity of 1.0
        assert abs(sim_same - 1.0) < 0.001
        # Different texts should have lower similarity
        assert sim_diff < sim_same
