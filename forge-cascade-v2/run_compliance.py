"""
Forge Compliance Framework - Standalone Server

Runs the compliance API as a standalone service on port 8002.
Uses the real compliance module with engine, auth, and persistence.
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.compliance.api.routes import router as compliance_router
from forge.compliance.api.extended_routes import extended_router
from forge.compliance.core.engine import get_compliance_engine

app = FastAPI(
    title="Forge Compliance Framework",
    description="Global compliance infrastructure with 400+ controls across 25+ frameworks",
    version="1.0.0",
)

# SECURITY FIX (Audit 4 - M18): Environment-based CORS configuration
# Don't use allow_origins=["*"] with allow_credentials=True in production
_environment = os.environ.get("ENVIRONMENT", "development")
_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
if not _allowed_origins or _allowed_origins == [""]:
    # Default origins based on environment
    if _environment == "production":
        _allowed_origins = [
            "https://forgecascade.org",
            "https://app.forgecascade.org",
        ]
    else:
        _allowed_origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
)

# Mount real compliance routes (prefix /compliance is already in router)
app.include_router(compliance_router, prefix="/api/v1")
# Mount extended routes under /api/v1/compliance
app.include_router(extended_router, prefix="/api/v1/compliance")


@app.on_event("startup")
async def startup():
    """Initialize compliance engine on startup."""
    engine = get_compliance_engine()
    await engine.initialize()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "compliance"}


@app.get("/api/v1/compliance/frameworks")
async def list_frameworks():
    """List all supported compliance frameworks (backward-compatible endpoint)."""
    engine = get_compliance_engine()
    frameworks = engine.config.frameworks_list

    return {
        "items": [
            {
                "id": fw.value,
                "name": fw.value.replace("_", " ").title(),
                "controls": len(engine.registry.get_controls_by_framework(fw)),
            }
            for fw in frameworks
        ],
        "total": len(frameworks),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
