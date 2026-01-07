"""
Forge Compliance Framework - Standalone Server

Runs the compliance API as a standalone service on port 8002.
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.compliance.api.routes import router as compliance_router
from forge.compliance.core.engine import get_compliance_engine

app = FastAPI(
    title="Forge Compliance Framework",
    description="Global compliance infrastructure with 400+ controls across 25+ frameworks",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount compliance routes at /api/v1
app.include_router(compliance_router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    """Initialize compliance engine on startup."""
    engine = get_compliance_engine()
    await engine.initialize()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "compliance"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
