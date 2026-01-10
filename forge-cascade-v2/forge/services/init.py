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
from forge.services.ghost_council import (
    get_ghost_council_service,
    init_ghost_council_service,
    shutdown_ghost_council_service,
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

    # SECURITY FIX (Audit 4 - M): Warn when falling back to mock provider
    configured_embedding = settings.embedding_provider
    embedding_provider = embedding_provider_map.get(configured_embedding)
    if embedding_provider is None:
        logger.warning(
            "embedding_provider_not_recognized",
            configured=configured_embedding,
            valid_providers=list(embedding_provider_map.keys()),
            fallback="mock",
        )
        embedding_provider = EmbeddingProvider.MOCK

    embedding_config = EmbeddingConfig(
        provider=embedding_provider,
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

    # SECURITY FIX (Audit 4 - M): Warn when falling back to mock provider
    configured_llm = settings.llm_provider
    llm_provider = llm_provider_map.get(configured_llm)
    if llm_provider is None:
        logger.warning(
            "llm_provider_not_recognized",
            configured=configured_llm,
            valid_providers=list(llm_provider_map.keys()),
            fallback="mock",
        )
        llm_provider = LLMProvider.MOCK

    llm_config = LLMConfig(
        provider=llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )

    init_llm_service(llm_config)
    logger.info(
        "llm_service_ready",
        provider=settings.llm_provider,
        model=settings.llm_model,
    )

    # Initialize search service
    init_search_service(
        embedding_service=embedding_service,
        capsule_repo=capsule_repo,
        db_client=db_client,
    )
    logger.info("search_service_ready")

    # Initialize Ghost Council service with config from settings
    from forge.services.ghost_council import GhostCouncilConfig
    ghost_council_config = GhostCouncilConfig(
        profile=settings.ghost_council_profile,
        cache_enabled=settings.ghost_council_cache_enabled,
        cache_ttl_days=settings.ghost_council_cache_ttl_days,
    )
    ghost_council = init_ghost_council_service(config=ghost_council_config)
    logger.info(
        "ghost_council_service_ready",
        members=len(ghost_council.members),
        profile=settings.ghost_council_profile,
    )

    # Set up serious issue detection if event_bus is available
    if event_bus:
        _setup_ghost_council_event_handlers(ghost_council, event_bus)

    logger.info("all_services_initialized")


def _setup_ghost_council_event_handlers(ghost_council, event_bus) -> None:
    """
    Set up event handlers for Ghost Council serious issue detection.

    Args:
        ghost_council: The Ghost Council service instance
        event_bus: The event system to subscribe to
    """
    import asyncio

    from forge.models.events import EventType

    # Events that may indicate serious issues
    serious_event_types = {
        EventType.SECURITY_ALERT,
        EventType.SECURITY_THREAT,
        EventType.TRUST_UPDATED,
        EventType.GOVERNANCE_ACTION,
        EventType.SYSTEM_ERROR,
        EventType.PIPELINE_ERROR,
        EventType.IMMUNE_ALERT,
    }

    async def handle_potential_serious_issue(event):
        """Handle events that might be serious issues."""
        try:
            issue = ghost_council.detect_serious_issue(
                event_type=event.event_type,
                payload=event.payload or {},
                source=event.source or "unknown",
            )

            if issue:
                # Automatically respond to serious issues
                logger.warning(
                    "ghost_council_auto_responding",
                    issue_id=issue.id,
                    category=issue.category.value,
                    severity=issue.severity.value,
                )

                # SECURITY FIX (Audit 3): Track background task and handle exceptions
                async def _safe_respond(gc, iss):
                    try:
                        await gc.respond_to_issue(iss)
                    except Exception as e:
                        logger.error(
                            "ghost_council_response_error",
                            issue_id=iss.id,
                            error=str(e)
                        )

                # Run deliberation in background to not block event processing
                task = asyncio.create_task(_safe_respond(ghost_council, issue))
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        except Exception as e:
            logger.error(
                "ghost_council_event_handler_error",
                error=str(e),
                event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
            )

    # Subscribe to serious event types using correct EventBus API
    subscription_id = event_bus.subscribe(
        handler=handle_potential_serious_issue,
        event_types=serious_event_types,
    )

    logger.info(
        "ghost_council_event_handlers_registered",
        subscription_id=subscription_id,
        event_types=[e.value for e in serious_event_types],
    )


def shutdown_all_services() -> None:
    """
    Shutdown all services gracefully.

    Called during application shutdown.
    """
    logger.info("shutting_down_services")

    shutdown_search_service()
    shutdown_llm_service()
    shutdown_embedding_service()
    shutdown_ghost_council_service()

    logger.info("all_services_shutdown")


__all__ = [
    "init_all_services",
    "shutdown_all_services",
]
