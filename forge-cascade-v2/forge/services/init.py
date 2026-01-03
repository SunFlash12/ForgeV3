"""
Forge Cascade V2 - Service Initialization

Initializes all services based on application configuration.
Called during application startup in the FastAPI app.
"""

from __future__ import annotations

import structlog

from forge.config import settings
from forge.services.embedding import (
    EmbeddingConfig,
    EmbeddingProvider,
    init_embedding_service,
    shutdown_embedding_service,
)
from forge.services.llm import (
    LLMConfig,
    LLMProvider,
    init_llm_service,
    shutdown_llm_service,
)
from forge.services.search import (
    init_search_service,
    shutdown_search_service,
)

logger = structlog.get_logger(__name__)


def init_all_services(
    db_client=None,
    capsule_repo=None,
    event_bus=None,
) -> None:
    """
    Initialize all services based on configuration.
    
    Called during application startup.
    
    Args:
        db_client: Neo4j client for direct database access
        capsule_repo: Capsule repository for search
        event_bus: Event bus for service events
    """
    logger.info("initializing_services")
    
    # Initialize embedding service
    embedding_provider_map = {
        "openai": EmbeddingProvider.OPENAI,
        "sentence_transformers": EmbeddingProvider.SENTENCE_TRANSFORMERS,
        "mock": EmbeddingProvider.MOCK,
    }
    
    embedding_config = EmbeddingConfig(
        provider=embedding_provider_map.get(
            settings.embedding_provider, 
            EmbeddingProvider.MOCK
        ),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        api_key=settings.embedding_api_key,
        cache_enabled=settings.embedding_cache_enabled,
        batch_size=settings.embedding_batch_size,
    )
    
    embedding_service = init_embedding_service(embedding_config)
    logger.info(
        "embedding_service_ready",
        provider=settings.embedding_provider,
        dimensions=settings.embedding_dimensions,
    )
    
    # Initialize LLM service
    llm_provider_map = {
        "anthropic": LLMProvider.ANTHROPIC,
        "openai": LLMProvider.OPENAI,
        "ollama": LLMProvider.OLLAMA,
        "mock": LLMProvider.MOCK,
    }
    
    llm_config = LLMConfig(
        provider=llm_provider_map.get(settings.llm_provider, LLMProvider.MOCK),
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )
    
    llm_service = init_llm_service(llm_config)
    logger.info(
        "llm_service_ready",
        provider=settings.llm_provider,
        model=settings.llm_model,
    )
    
    # Initialize search service
    search_service = init_search_service(
        embedding_service=embedding_service,
        capsule_repo=capsule_repo,
        db_client=db_client,
    )
    logger.info("search_service_ready")
    
    logger.info("all_services_initialized")


def shutdown_all_services() -> None:
    """
    Shutdown all services gracefully.
    
    Called during application shutdown.
    """
    logger.info("shutting_down_services")
    
    shutdown_search_service()
    shutdown_llm_service()
    shutdown_embedding_service()
    
    logger.info("all_services_shutdown")


__all__ = [
    "init_all_services",
    "shutdown_all_services",
]
