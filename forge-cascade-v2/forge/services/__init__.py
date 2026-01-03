"""
Forge Services Module

Contains external service integrations:
- EmbeddingService: Vector embeddings for semantic search
- LLMService: Language model integration for Ghost Council and Constitutional AI
- SearchService: Semantic and hybrid search across capsules
"""

from .embedding import (
    EmbeddingService,
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    get_embedding_service,
    init_embedding_service,
)
from .llm import (
    LLMService,
    LLMConfig,
    LLMProvider,
    LLMMessage,
    LLMResponse,
    get_llm_service,
    init_llm_service,
)
from .search import (
    SearchService,
    SearchMode,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    get_search_service,
    init_search_service,
)

__all__ = [
    # Embedding
    "EmbeddingService",
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "get_embedding_service",
    "init_embedding_service",
    # LLM
    "LLMService",
    "LLMConfig",
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "get_llm_service",
    "init_llm_service",
    # Search
    "SearchService",
    "SearchMode",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "get_search_service",
    "init_search_service",
]
