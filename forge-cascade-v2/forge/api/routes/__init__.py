"""
Forge API Routes Module

Exports all API routers for inclusion in the main FastAPI application.
"""

from forge.api.routes.auth import router as auth_router
from forge.api.routes.capsules import router as capsules_router
from forge.api.routes.cascade import router as cascade_router
from forge.api.routes.governance import router as governance_router
from forge.api.routes.graph import router as graph_router
from forge.api.routes.overlays import router as overlays_router
from forge.api.routes.system import router as system_router

__all__ = [
    "auth_router",
    "capsules_router",
    "cascade_router",
    "governance_router",
    "overlays_router",
    "system_router",
    "graph_router",
]
