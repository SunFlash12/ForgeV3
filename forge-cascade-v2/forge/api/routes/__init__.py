"""
Forge API Routes Module

Exports all API routers for inclusion in the main FastAPI application.
"""

from forge.api.routes.acp import router as acp_router
from forge.api.routes.auth import router as auth_router
from forge.api.routes.capsules import router as capsules_router
from forge.api.routes.cascade import router as cascade_router
from forge.api.routes.copilot import router as copilot_router
from forge.api.routes.diagnosis import router as diagnosis_router
from forge.api.routes.game import router as game_router
from forge.api.routes.governance import router as governance_router
from forge.api.routes.graph import router as graph_router
from forge.api.routes.overlays import router as overlays_router
from forge.api.routes.primekg import router as primekg_router
from forge.api.routes.sessions import router as sessions_router
from forge.api.routes.system import router as system_router
from forge.api.routes.tipping import router as tipping_router

__all__ = [
    "acp_router",
    "auth_router",
    "capsules_router",
    "cascade_router",
    "copilot_router",
    "diagnosis_router",
    "game_router",
    "governance_router",
    "overlays_router",
    "sessions_router",
    "system_router",
    "graph_router",
    "primekg_router",
    "tipping_router",
]
