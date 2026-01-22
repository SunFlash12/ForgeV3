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
    APIResponse,
    PaginatedResponse,
    acp_router,
    agent_router,
    create_virtuals_router,
    revenue_router,
    tokenization_router,
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
