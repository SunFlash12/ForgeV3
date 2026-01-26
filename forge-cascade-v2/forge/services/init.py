"""
Forge Cascade V2 - Service Initialization

Initializes all services based on application configuration.
Called during application startup in the FastAPI app.
"""

from __future__ import annotations

from typing import Any

import structlog

from forge.config import settings
from forge.services.embedding import (
    EmbeddingConfig,
    EmbeddingProvider,
    init_embedding_service,
    shutdown_embedding_service,
)
from forge.services.ghost_council import (
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
    db_client: Any = None,
    capsule_repo: Any = None,
    event_bus: Any = None,
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

    # Initialize embedding service with smart provider selection
    embedding_provider_map = {
        "openai": EmbeddingProvider.OPENAI,
        "sentence_transformers": EmbeddingProvider.SENTENCE_TRANSFORMERS,
        "mock": EmbeddingProvider.MOCK,
    }

    # Smart provider selection: Use configured provider if API key available,
    # otherwise auto-detect based on available keys, or fall back to mock
    configured_embedding = settings.embedding_provider
    embedding_api_key = settings.embedding_api_key
    selected_embedding_provider = None
    selected_embedding_model = settings.embedding_model

    if configured_embedding != "mock" and (
        embedding_api_key or configured_embedding == "sentence_transformers"
    ):
        # User configured a specific provider - use it
        selected_embedding_provider = embedding_provider_map.get(configured_embedding)
        if selected_embedding_provider is None:
            logger.warning(
                "embedding_provider_not_recognized",
                configured=configured_embedding,
                valid_providers=list(embedding_provider_map.keys()),
            )
    elif configured_embedding == "mock":
        # Explicitly configured mock
        selected_embedding_provider = EmbeddingProvider.MOCK

    # Auto-detect if no explicit config or missing API key
    if selected_embedding_provider is None:
        import os
        openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMBEDDING_API_KEY")

        if openai_key:
            # Prefer OpenAI embeddings when API key is available
            selected_embedding_provider = EmbeddingProvider.OPENAI
            embedding_api_key = openai_key
            selected_embedding_model = "text-embedding-3-small"
            logger.info("embedding_auto_detected_openai", hint="Found OPENAI_API_KEY")
        else:
            # Fall back to local sentence-transformers (no API needed)
            try:
                import sentence_transformers  # noqa: F401
                selected_embedding_provider = EmbeddingProvider.SENTENCE_TRANSFORMERS
                selected_embedding_model = "all-MiniLM-L6-v2"
                logger.info(
                    "embedding_using_sentence_transformers",
                    hint="No OPENAI_API_KEY found, using local model",
                )
            except ImportError:
                # No sentence-transformers available - fall back to mock
                selected_embedding_provider = EmbeddingProvider.MOCK
                if settings.app_env != "testing":
                    logger.warning(
                        "embedding_using_mock_provider",
                        reason="No embedding API key or sentence-transformers available",
                        hint="Set OPENAI_API_KEY or install sentence-transformers",
                    )

    embedding_config = EmbeddingConfig(
        provider=selected_embedding_provider,
        model=selected_embedding_model,
        dimensions=settings.embedding_dimensions,
        api_key=embedding_api_key,
        cache_enabled=settings.embedding_cache_enabled,
        batch_size=settings.embedding_batch_size,
    )

    embedding_service = init_embedding_service(embedding_config)
    logger.info(
        "embedding_service_ready",
        provider=selected_embedding_provider.value,
        model=selected_embedding_model,
        dimensions=settings.embedding_dimensions,
        auto_detected=selected_embedding_provider != embedding_provider_map.get(settings.embedding_provider),
    )

    # Initialize LLM service with smart provider selection
    llm_provider_map = {
        "anthropic": LLMProvider.ANTHROPIC,
        "openai": LLMProvider.OPENAI,
        "ollama": LLMProvider.OLLAMA,
        "mock": LLMProvider.MOCK,
    }

    # Smart provider selection: Use configured provider if API key available,
    # otherwise auto-detect based on available keys, or fall back to mock
    configured_llm = settings.llm_provider
    llm_api_key = settings.llm_api_key
    selected_provider = None
    selected_model = settings.llm_model

    if configured_llm != "mock" and llm_api_key:
        # User configured a specific provider with API key - use it
        selected_provider = llm_provider_map.get(configured_llm)
        if selected_provider is None:
            logger.warning(
                "llm_provider_not_recognized",
                configured=configured_llm,
                valid_providers=list(llm_provider_map.keys()),
            )
    elif configured_llm == "mock":
        # Explicitly configured mock
        selected_provider = LLMProvider.MOCK

    # Auto-detect if no explicit config or missing API key
    if selected_provider is None:
        import os
        openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if openai_key:
            # Prefer OpenAI as default when API key is available
            selected_provider = LLMProvider.OPENAI
            llm_api_key = openai_key
            selected_model = "gpt-4-turbo-preview"
            logger.info("llm_auto_detected_openai", hint="Found OPENAI_API_KEY")
        elif anthropic_key:
            selected_provider = LLMProvider.ANTHROPIC
            llm_api_key = anthropic_key
            selected_model = "claude-sonnet-4-20250514"
            logger.info("llm_auto_detected_anthropic", hint="Found ANTHROPIC_API_KEY")
        else:
            # No API keys available - fall back to mock
            selected_provider = LLMProvider.MOCK
            if settings.app_env != "testing":
                logger.warning(
                    "llm_using_mock_provider",
                    reason="No LLM API key configured",
                    hint="Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or LLM_API_KEY",
                )

    llm_config = LLMConfig(
        provider=selected_provider,
        model=selected_model,
        api_key=llm_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )

    init_llm_service(llm_config)
    logger.info(
        "llm_service_ready",
        provider=selected_provider.value,
        model=selected_model,
        auto_detected=selected_provider != llm_provider_map.get(settings.llm_provider),
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


def _setup_ghost_council_event_handlers(ghost_council: Any, event_bus: Any) -> None:
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

    async def handle_potential_serious_issue(event: Any) -> None:
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
                async def _safe_respond(gc: Any, iss: Any) -> None:
                    try:
                        await gc.respond_to_issue(iss)
                    except (RuntimeError, ValueError, ConnectionError, OSError) as e:
                        logger.error(
                            "ghost_council_response_error",
                            issue_id=iss.id,
                            error=str(e)
                        )

                # Run deliberation in background to not block event processing
                task = asyncio.create_task(_safe_respond(ghost_council, issue))
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        except (RuntimeError, ValueError, ConnectionError, OSError) as e:
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

    Called during application shutdown (sync version).
    For async shutdown, use shutdown_all_services_async().
    """
    logger.info("shutting_down_services")

    shutdown_search_service()
    # Note: shutdown_llm_service is async; sync shutdown just clears references
    # For proper cleanup, use shutdown_all_services_async() in async contexts
    shutdown_embedding_service()
    shutdown_ghost_council_service()

    logger.info("all_services_shutdown")


async def shutdown_all_services_async() -> None:
    """
    Shutdown all services gracefully (async version).

    Called during application shutdown in async contexts.
    """
    logger.info("shutting_down_services")

    shutdown_search_service()
    await shutdown_llm_service()
    shutdown_embedding_service()
    shutdown_ghost_council_service()

    logger.info("all_services_shutdown")


__all__ = [
    "init_all_services",
    "shutdown_all_services",
    "shutdown_all_services_async",
]
