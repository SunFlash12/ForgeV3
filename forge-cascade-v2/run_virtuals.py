"""
Forge Virtuals Integration - Standalone Server

Runs the Virtuals Protocol API as a standalone service on port 8003.
Uses the real virtuals module with GAME framework, ACP, and tokenization.
"""

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.virtuals.api import create_virtuals_router

app = FastAPI(
    title="Forge Virtuals Integration",
    description="Virtuals Protocol integration for agents, tokenization, ACP, and revenue",
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
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Mount real Virtuals Protocol routes (agents, tokenization, ACP, revenue)
app.include_router(create_virtuals_router(), prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "virtuals"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
