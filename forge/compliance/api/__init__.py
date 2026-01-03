"""
Forge Compliance Framework - API Module

REST API endpoints for all compliance services.
"""

from fastapi import APIRouter

from forge.compliance.api.routes import router as compliance_router
from forge.compliance.api.extended_routes import extended_router

# Combine all routers
api_router = APIRouter()
api_router.include_router(compliance_router, tags=["compliance"])
api_router.include_router(extended_router, prefix="/compliance", tags=["compliance-extended"])

__all__ = [
    "compliance_router",
    "extended_router",
    "api_router",
]
