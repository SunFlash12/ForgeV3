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

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.kernel.event_system import EventSystem
from forge.kernel.overlay_manager import OverlayManager
from forge.kernel.pipeline import CascadePipeline
from forge.immune import create_immune_system, get_circuit_registry

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
        
        # State
        self.started_at: datetime | None = None
        self.is_ready: bool = False
    
    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("forge_initializing")
        
        # Database
        self.db_client = Neo4jClient()
        await self.db_client.connect()
        
        # Kernel
        self.event_system = EventSystem()
        self.overlay_manager = OverlayManager(self.event_system)
        await self.overlay_manager.start()
        
        self.pipeline = CascadePipeline(
            overlay_manager=self.overlay_manager,
            event_system=self.event_system,
        )
        
        # Immune system
        immune = create_immune_system(
            db_client=self.db_client,
            overlay_manager=self.overlay_manager,
            event_system=self.event_system,
        )
        self.circuit_registry = immune["circuit_registry"]
        self.health_checker = immune["health_checker"]
        self.anomaly_system = immune["anomaly_system"]
        self.canary_manager = immune["canary_manager"]
        
        # Initialize services (embedding, LLM, search)
        from forge.services.init import init_all_services
        from forge.repositories.capsule_repository import CapsuleRepository
        
        capsule_repo = CapsuleRepository(self.db_client)
        init_all_services(
            db_client=self.db_client,
            capsule_repo=capsule_repo,
            event_bus=self.event_system,
        )
        
        # Register core overlays
        await self._register_core_overlays()
        
        self.started_at = datetime.now(timezone.utc)
        self.is_ready = True
        
        logger.info(
            "forge_initialized",
            overlays=len(self.overlay_manager._overlays) if self.overlay_manager else 0,
        )
    
    async def _register_core_overlays(self) -> None:
        """Register the core overlay set."""
        from forge.overlays import (
            create_security_validator,
            create_ml_intelligence,
            create_governance_overlay,
            create_lineage_tracker,
        )
        
        # Create overlays
        security = create_security_validator(strict_mode=False)
        ml = create_ml_intelligence(production_mode=False)
        governance = create_governance_overlay(strict_mode=False)
        lineage = create_lineage_tracker(strict_mode=False)
        
        # Register with manager
        if self.overlay_manager:
            await self.overlay_manager.register(security)
            await self.overlay_manager.register(ml)
            await self.overlay_manager.register(governance)
            await self.overlay_manager.register(lineage)
            
            # Activate all
            await self.overlay_manager.activate(security.overlay_id)
            await self.overlay_manager.activate(ml.overlay_id)
            await self.overlay_manager.activate(governance.overlay_id)
            await self.overlay_manager.activate(lineage.overlay_id)
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all components."""
        logger.info("forge_shutting_down")
        
        self.is_ready = False
        
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
                (datetime.now(timezone.utc) - self.started_at).total_seconds()
                if self.started_at else 0
            ),
            "database": "connected" if self.db_client and self.db_client._driver else "disconnected",
            "overlays": (
                len(self.overlay_manager._overlays)
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
        ],
    )
    
    # Store forge_app reference
    app.state.forge = forge_app
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if hasattr(settings, 'CORS_ORIGINS') else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    from forge.api.middleware import (
        CorrelationIdMiddleware,
        RequestLoggingMiddleware,
        AuthenticationMiddleware,
        RateLimitMiddleware,
    )
    
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
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
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "details": exc.errors(),
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
    from forge.api.routes import auth, capsules, governance, overlays, system
    
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(capsules.router, prefix="/api/v1/capsules", tags=["capsules"])
    app.include_router(governance.router, prefix="/api/v1/governance", tags=["governance"])
    app.include_router(overlays.router, prefix="/api/v1/overlays", tags=["overlays"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
    
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
    
    logger.info(
        "fastapi_app_created",
        title=title,
        version=version,
        docs_url=docs_url,
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
