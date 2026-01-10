"""
Forge Cascade V2 - FastAPI Application Factory
Main entry point for the Forge API.

This creates and configures the FastAPI application with:
- All routes (auth, capsules, governance, overlays, system)
- WebSocket handlers (events, chat, dashboard)
- Middleware (correlation ID, logging, authentication)
- Error handlers
- OpenAPI documentation
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.immune import create_immune_system
from forge.kernel.event_system import EventSystem
from forge.kernel.overlay_manager import OverlayManager
from forge.kernel.pipeline import CascadePipeline
from forge.monitoring import (
    add_metrics_middleware,
    configure_logging,
    create_metrics_endpoint,
)
from forge.resilience.integration import (
    ObservabilityMiddleware,
)

# Configure logging early - before any other logging occurs
_settings = get_settings()
configure_logging(
    level=_settings.log_level if hasattr(_settings, 'log_level') else "INFO",
    json_output=_settings.app_env == "production",
    include_timestamps=True,
    include_service_info=True,
    sanitize_logs=True,
)

logger = structlog.get_logger(__name__)


class ForgeApp:
    """
    Forge application container.

    Holds references to all core components for dependency injection.
    """

    def __init__(self):
        self.settings = get_settings()

        # Core components (initialized in lifespan)
        self.db_client: Neo4jClient | None = None
        self.event_system: EventSystem | None = None
        self.overlay_manager: OverlayManager | None = None
        self.pipeline: CascadePipeline | None = None

        # Immune system components
        self.circuit_registry = None
        self.health_checker = None
        self.anomaly_system = None
        self.canary_manager = None

        # Resilience components
        self.resilience_initialized: bool = False

        # State
        self.started_at: datetime | None = None
        self.is_ready: bool = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("forge_initializing")

        # SECURITY FIX (Audit 4): Add error recovery for core service initialization
        # Database - critical, app cannot run without it
        try:
            self.db_client = Neo4jClient()
            await self.db_client.connect()
            logger.info("database_connected")
        except Exception as e:
            logger.critical("database_connection_failed", error=str(e))
            raise RuntimeError(f"Cannot start: Database connection failed - {e}") from e

        # Kernel - critical for core functionality
        try:
            self.event_system = EventSystem()
            self.overlay_manager = OverlayManager(self.event_system)
            await self.overlay_manager.start()

            self.pipeline = CascadePipeline(
                overlay_manager=self.overlay_manager,
                event_bus=self.event_system,
            )
            logger.info("kernel_initialized")
        except Exception as e:
            logger.critical("kernel_initialization_failed", error=str(e))
            # Clean up database connection before failing
            if self.db_client:
                await self.db_client.close()
            raise RuntimeError(f"Cannot start: Kernel initialization failed - {e}") from e

        # Immune system - important but app can run in degraded mode
        try:
            immune = create_immune_system(
                db_client=self.db_client,
                overlay_manager=self.overlay_manager,
                event_system=self.event_system,
            )
            self.circuit_registry = immune["circuit_registry"]
            self.health_checker = immune["health_checker"]
            self.anomaly_system = immune["anomaly_system"]
            self.canary_manager = immune["canary_manager"]
            logger.info("immune_system_initialized")
        except Exception as e:
            logger.error("immune_system_init_failed", error=str(e))
            # Continue without immune system - degraded mode
            self.circuit_registry = None
            self.health_checker = None
            self.anomaly_system = None
            self.canary_manager = None

        # Initialize services (embedding, LLM, search) - important but degradable
        try:
            from forge.repositories.capsule_repository import CapsuleRepository
            from forge.services.init import init_all_services

            capsule_repo = CapsuleRepository(self.db_client)
            init_all_services(
                db_client=self.db_client,
                capsule_repo=capsule_repo,
                event_bus=self.event_system,
            )
            logger.info("services_initialized")
        except Exception as e:
            logger.error("services_init_failed", error=str(e))
            # Continue - some features may not work

        # Register core overlays
        try:
            await self._register_core_overlays()
            logger.info("core_overlays_registered")
        except Exception as e:
            logger.error("overlay_registration_failed", error=str(e))

        # Initialize resilience layer (caching, observability, validation)
        try:
            from forge.resilience.integration import get_resilience_state
            resilience_state = await get_resilience_state()
            self.resilience_initialized = resilience_state.initialized
            logger.info("resilience_layer_initialized")
        except Exception as e:
            logger.warning("resilience_init_failed", error=str(e))
            self.resilience_initialized = False

        # Initialize token blacklist with Redis for distributed deployments
        try:
            from forge.security.tokens import TokenBlacklist
            redis_connected = await TokenBlacklist.initialize(self.settings.redis_url)
            logger.info("token_blacklist_initialized", redis_enabled=redis_connected)
        except Exception as e:
            logger.warning("token_blacklist_init_failed", error=str(e))

        # Initialize query cache (Redis or in-memory fallback)
        try:
            from forge.services.query_cache import init_query_cache
            self.query_cache = await init_query_cache()
            logger.info("query_cache_initialized")
        except Exception as e:
            logger.warning("query_cache_init_failed", error=str(e))
            self.query_cache = None

        # Initialize and start background scheduler
        try:
            from forge.services.scheduler import setup_scheduler
            self.scheduler = await setup_scheduler()
            await self.scheduler.start()
            logger.info(
                "scheduler_started",
                tasks=self.scheduler.get_stats().get("tasks_registered", 0),
            )
        except Exception as e:
            logger.warning("scheduler_init_failed", error=str(e))
            self.scheduler = None

        self.started_at = datetime.now(UTC)
        self.is_ready = True

        logger.info(
            "forge_initialized",
            # FIX: Use public method instead of accessing private _registry attribute
            overlays=self.overlay_manager.get_overlay_count() if self.overlay_manager else 0,
            resilience=self.resilience_initialized,
            scheduler=self.scheduler is not None,
        )

    async def _register_core_overlays(self) -> None:
        """Register the core overlay set."""
        from forge.overlays import (
            create_governance_overlay,
            create_graph_algorithms_overlay,
            create_knowledge_query_overlay,
            create_lineage_tracker,
            create_ml_intelligence,
            create_security_validator,
            create_temporal_tracker_overlay,
        )

        # Use environment-based configuration for overlay strict mode
        is_production = self.settings.app_env == "production"

        # Create overlays - enable strict mode in production
        security = create_security_validator(strict_mode=is_production)

        # ML overlay needs embedding provider in production mode
        ml_kwargs = {}
        if is_production:
            ml_kwargs["embedding_provider"] = self.settings.embedding_provider
        ml = create_ml_intelligence(production_mode=is_production, **ml_kwargs)

        governance = create_governance_overlay(strict_mode=is_production)
        lineage = create_lineage_tracker(strict_mode=is_production)

        # Graph extension overlays
        # These are created without repositories initially - they'll be wired via dependency injection
        graph_algorithms = create_graph_algorithms_overlay()
        knowledge_query = create_knowledge_query_overlay()
        temporal_tracker = create_temporal_tracker_overlay()

        # Register with manager (auto-initializes by default)
        if self.overlay_manager:
            await self.overlay_manager.register_instance(security)
            await self.overlay_manager.register_instance(ml)
            await self.overlay_manager.register_instance(governance)
            await self.overlay_manager.register_instance(lineage)
            await self.overlay_manager.register_instance(graph_algorithms)
            await self.overlay_manager.register_instance(knowledge_query)
            await self.overlay_manager.register_instance(temporal_tracker)

    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        logger.info("forge_shutting_down")

        self.is_ready = False

        # Stop scheduler first (prevents new background tasks)
        if hasattr(self, 'scheduler') and self.scheduler:
            try:
                await self.scheduler.stop()
                logger.info("scheduler_shutdown")
            except Exception as e:
                logger.warning("scheduler_shutdown_failed", error=str(e))

        # Shutdown query cache
        if hasattr(self, 'query_cache') and self.query_cache:
            try:
                from forge.services.query_cache import close_query_cache
                await close_query_cache()
                logger.info("query_cache_shutdown")
            except Exception as e:
                logger.warning("query_cache_shutdown_failed", error=str(e))

        # Shutdown resilience layer
        if self.resilience_initialized:
            try:
                from forge.resilience.integration import get_resilience_state
                resilience_state = await get_resilience_state()
                await resilience_state.close()
                logger.info("resilience_layer_shutdown")
            except Exception as e:
                logger.warning("resilience_shutdown_failed", error=str(e))

        # Shutdown services
        from forge.services.init import shutdown_all_services
        shutdown_all_services()

        if self.overlay_manager:
            await self.overlay_manager.stop()

        if self.db_client:
            await self.db_client.close()

        logger.info("forge_shutdown_complete")

    def get_status(self) -> dict[str, Any]:
        """Get current application status."""
        return {
            "status": "ready" if self.is_ready else "starting",
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "uptime_seconds": (
                (datetime.now(UTC) - self.started_at).total_seconds()
                if self.started_at else 0
            ),
            "database": "connected" if self.db_client and self.db_client._driver else "disconnected",
            "overlays": (
                len(self.overlay_manager._registry.instances)
                if self.overlay_manager else 0
            ),
        }


# Global app instance
forge_app = ForgeApp()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Initializes and shuts down all components.
    """
    # Startup
    try:
        await forge_app.initialize()
        yield
    finally:
        # Shutdown
        await forge_app.shutdown()


def create_app(
    title: str = "Forge Cascade V2",
    description: str = "Institutional Memory Engine for Digital Societies",
    version: str = "2.0.0",
    docs_url: str | None = "/docs",
    redoc_url: str | None = "/redoc",
    debug: bool = False,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for documentation
        description: API description
        version: API version string
        docs_url: Swagger UI URL (None to disable)
        redoc_url: ReDoc URL (None to disable)
        debug: Enable debug mode

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        debug=debug,
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "auth",
                "description": "Authentication and authorization endpoints",
            },
            {
                "name": "capsules",
                "description": "Knowledge capsule management",
            },
            {
                "name": "cascade",
                "description": "Cascade Effect - insight propagation across overlays",
            },
            {
                "name": "governance",
                "description": "Symbolic governance and voting",
            },
            {
                "name": "overlays",
                "description": "Overlay management and status",
            },
            {
                "name": "system",
                "description": "System health and metrics",
            },
            {
                "name": "graph",
                "description": "Graph analysis, queries, and temporal operations",
            },
            {
                "name": "Federation",
                "description": "Federated knowledge sharing between Forge instances",
            },
            {
                "name": "Notifications",
                "description": "In-app notifications and webhook subscriptions",
            },
            {
                "name": "Marketplace",
                "description": "Knowledge capsule marketplace for buying and selling capsules",
            },
            {
                "name": "Agent Gateway",
                "description": "AI agent access to the knowledge graph",
            },
        ],
    )

    # Store forge_app reference
    app.state.forge = forge_app

    # CORS - Use explicit origins, never allow wildcard with credentials
    cors_origins = settings.CORS_ORIGINS
    if not cors_origins:
        # Default to localhost only, never wildcard
        cors_origins = ["http://localhost:3000", "http://localhost:8000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Idempotency-Key", "X-CSRF-Token"],
    )

    # Add custom middleware
    from forge.api.middleware import (
        APILimitsMiddleware,  # SECURITY FIX (Audit 3)
        AuthenticationMiddleware,
        CorrelationIdMiddleware,
        CSRFProtectionMiddleware,
        IdempotencyMiddleware,
        RateLimitMiddleware,
        RequestLoggingMiddleware,
        RequestSizeLimitMiddleware,
        RequestTimeoutMiddleware,
        SecurityHeadersMiddleware,
    )

    # Order matters: outer middleware runs first
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=(settings.app_env == "production"))
    app.add_middleware(RequestTimeoutMiddleware, default_timeout=30.0, extended_timeout=120.0)  # Request timeout (Audit 2)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Resilience: Observability middleware for tracing and metrics
    app.add_middleware(ObservabilityMiddleware)

    # Prometheus metrics collection middleware
    add_metrics_middleware(app)

    app.add_middleware(RequestSizeLimitMiddleware, max_content_length=10 * 1024 * 1024)  # 10MB limit
    # SECURITY FIX (Audit 3): Add API limits for JSON depth and query params
    app.add_middleware(APILimitsMiddleware, max_json_depth=20, max_query_params=50, max_array_length=1000)
    app.add_middleware(CSRFProtectionMiddleware, enabled=(settings.app_env != "development"))  # CSRF protection
    app.add_middleware(IdempotencyMiddleware)  # Idempotency support
    app.add_middleware(AuthenticationMiddleware)
    # Rate limiting - use environment-based configuration
    # Production: stricter limits. Development: relaxed for testing
    is_dev = settings.app_env == "development"
    app.add_middleware(
        RateLimitMiddleware,
        redis_url=settings.redis_url,
        auth_requests_per_minute=30 if is_dev else 10,  # Stricter in production
        auth_requests_per_hour=200 if is_dev else 50,   # Stricter in production
    )

    # Exception handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # SECURITY FIX (Audit 2): Sanitize validation errors to not leak schema details
        # Only return field location and generic error type, not attempted values
        sanitized_errors = []
        for error in exc.errors():
            sanitized_error = {
                "loc": error.get("loc", []),
                "type": error.get("type", "unknown"),
                "msg": error.get("msg", "Validation failed"),
            }
            # Omit 'input' field (contains user-submitted values)
            # Omit 'ctx' field (may contain internal details)
            sanitized_errors.append(sanitized_error)

        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "details": sanitized_errors,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled_exception",
            path=str(request.url.path),
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "path": str(request.url.path),
            },
        )

    # Include routers
    from forge.api.routes import (
        agent_gateway,
        auth,
        capsules,
        cascade,
        federation,
        governance,
        graph,
        marketplace,
        notifications,
        overlays,
        system,
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(capsules.router, prefix="/api/v1/capsules", tags=["capsules"])
    app.include_router(cascade.router, prefix="/api/v1/cascade", tags=["cascade"])
    app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])
    app.include_router(overlays.router, prefix="/api/v1/overlays", tags=["overlays"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
    app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
    app.include_router(federation.router, prefix="/api/v1", tags=["Federation"])
    app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
    app.include_router(marketplace.router, prefix="/api/v1", tags=["Marketplace"])
    app.include_router(agent_gateway.router, prefix="/api/v1", tags=["Agent Gateway"])

    # WebSocket endpoints
    from forge.api.websocket import websocket_router

    app.include_router(websocket_router)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": title,
            "version": version,
            "status": forge_app.get_status(),
        }

    # Health check (lightweight)
    @app.get("/health", include_in_schema=False)
    async def health():
        return {
            "status": "healthy" if forge_app.is_ready else "starting",
        }

    # Readiness check (full check)
    @app.get("/ready", include_in_schema=False)
    async def ready():
        if not forge_app.is_ready:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready"},
            )
        return {"status": "ready"}

    # Prometheus metrics endpoint
    # Returns metrics in Prometheus text format for scraping
    metrics_response = create_metrics_endpoint()

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """
        Prometheus metrics endpoint.

        Returns all collected metrics in Prometheus text format.
        Configure your prometheus.yml to scrape this endpoint:

            scrape_configs:
              - job_name: 'forge-cascade'
                static_configs:
                  - targets: ['localhost:8000']
                metrics_path: '/metrics'
        """
        return Response(
            content=metrics_response(),
            media_type="text/plain; charset=utf-8",
        )

    logger.info(
        "fastapi_app_created",
        title=title,
        version=version,
        docs_url=docs_url,
        metrics_enabled=True,
    )

    return app


# Default app for uvicorn
app = create_app()


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    workers: int = 1,
) -> None:
    """
    Run the Forge server.

    For development use:
        python -m forge.api.app

    For production use:
        uvicorn forge.api.app:app --host 0.0.0.0 --port 8000 --workers 4
    """
    import uvicorn

    uvicorn.run(
        "forge.api.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    run_server(reload=True)
