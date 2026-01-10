"""
Forge Services Module

Contains external service integrations:
- EmbeddingService: Vector embeddings for semantic search
- LLMService: Language model integration for Ghost Council and Constitutional AI
- SearchService: Semantic and hybrid search across capsules
"""

from .embedding import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
    get_embedding_service,
    init_embedding_service,
)
from .ghost_council import (
    DEFAULT_COUNCIL_MEMBERS,
    GhostCouncilConfig,
    GhostCouncilService,
    IssueCategory,
    IssueSeverity,
    SeriousIssue,
    get_ghost_council_service,
    init_ghost_council_service,
)
from .llm import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMService,
    get_llm_service,
    init_llm_service,
)
from .query_cache import (
    CachedQueryResult,
    InMemoryQueryCache,
    QueryCache,
    close_query_cache,
    get_query_cache,
    init_query_cache,
)
from .scheduler import (
    BackgroundScheduler,
    ScheduledTask,
    SchedulerStats,
    get_scheduler,
    setup_scheduler,
)
from .search import (
    SearchFilters,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchService,
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
    # Ghost Council
    "GhostCouncilService",
    "GhostCouncilConfig",
    "SeriousIssue",
    "IssueSeverity",
    "IssueCategory",
    "get_ghost_council_service",
    "init_ghost_council_service",
    "DEFAULT_COUNCIL_MEMBERS",
    # Scheduler
    "BackgroundScheduler",
    "ScheduledTask",
    "SchedulerStats",
    "get_scheduler",
    "setup_scheduler",
    # Query Cache
    "QueryCache",
    "InMemoryQueryCache",
    "CachedQueryResult",
    "get_query_cache",
    "init_query_cache",
    "close_query_cache",
]
