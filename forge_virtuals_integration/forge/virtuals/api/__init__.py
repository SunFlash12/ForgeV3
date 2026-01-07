"""
API Package for Virtuals Protocol Integration

This package provides FastAPI routes for the Forge-Virtuals integration,
enabling REST API access to all Virtuals Protocol features.

Usage:
    from fastapi import FastAPI
    from forge.virtuals.api import create_virtuals_router
    
    app = FastAPI()
    app.include_router(
        create_virtuals_router(),
        prefix="/api/v1/virtuals"
    )
"""

from .routes import (
    create_virtuals_router,
    agent_router,
    tokenization_router,
    acp_router,
    revenue_router,
    APIResponse,
    PaginatedResponse,
)

__all__ = [
    "create_virtuals_router",
    "agent_router",
    "tokenization_router",
    "acp_router",
    "revenue_router",
    "APIResponse",
    "PaginatedResponse",
]
