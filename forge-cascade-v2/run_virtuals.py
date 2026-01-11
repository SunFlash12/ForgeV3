"""
Forge Virtuals Integration - Standalone Server

Runs the Virtuals Protocol API as a standalone service on port 8003.
This server uses a simplified in-memory implementation for the Virtuals endpoints.
"""

import os
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

# ═══════════════════════════════════════════════════════════════════════════
# IN-MEMORY STORAGE
# ═══════════════════════════════════════════════════════════════════════════

agents: dict[str, dict] = {}
tokenized_entities: dict[str, dict] = {}
proposals: dict[str, dict] = {}
offerings: dict[str, dict] = {}
jobs: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaginatedResponse(APIResponse):
    total: int = 0
    page: int = 1
    per_page: int = 20
    has_more: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════

class AgentCreateRequest(BaseModel):
    name: str
    description: str | None = None
    agent_type: str | None = "knowledge"
    personality: dict | None = None
    tokenization_enabled: bool = False


class TokenizationRequest(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    symbol: str
    initial_stake: float = 100.0
    owner_wallet: str | None = None


class ProposalCreateRequest(BaseModel):
    title: str
    description: str
    proposal_type: str
    proposed_changes: dict


class OfferingRequest(BaseModel):
    service_type: str
    description: str
    pricing: dict | None = None


class JobCreateRequest(BaseModel):
    offering_id: str
    requirements: dict | None = None
    max_fee: float = 100.0


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "virtuals"}


# ═══════════════════════════════════════════════════════════════════════════
# AGENT ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/agents/", status_code=201)
async def create_agent(request: AgentCreateRequest):
    agent_id = str(uuid4())
    agent = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "agent_type": request.agent_type,
        "personality": request.personality,
        "tokenization_enabled": request.tokenization_enabled,
        "status": "active",
        "created_at": datetime.now(UTC).isoformat(),
    }
    agents[agent_id] = agent
    return APIResponse(data=agent)


@app.get("/api/v1/agents/")
async def list_agents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
):
    result = list(agents.values())
    if status:
        result = [a for a in result if a.get("status") == status]

    total = len(result)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = result[start:end]

    return PaginatedResponse(
        data=paginated,
        total=total,
        page=page,
        per_page=per_page,
        has_more=end < total,
    )


@app.get("/api/v1/agents/{agent_id}")
async def get_agent(agent_id: str):
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return APIResponse(data=agents[agent_id])


@app.post("/api/v1/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    context: str = Query(..., description="Context or query for the agent"),
    max_iterations: int = Query(10, ge=1, le=50),
):
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Simulate agent execution
    return APIResponse(data={
        "agent_id": agent_id,
        "context": context,
        "iterations": max_iterations,
        "results": [
            {"action": "analyze", "output": "Analysis complete"},
            {"action": "respond", "output": "Response generated"},
        ],
        "completed_at": datetime.now(UTC).isoformat(),
    })


# ═══════════════════════════════════════════════════════════════════════════
# TOKENIZATION ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/tokenization/", status_code=201)
async def request_tokenization(request: TokenizationRequest):
    entity = {
        "entity_id": request.entity_id,
        "entity_type": request.entity_type,
        "name": request.name,
        "symbol": request.symbol,
        "initial_stake": request.initial_stake,
        "owner_wallet": request.owner_wallet or "0x0000000000000000000000000000000000000000",
        "phase": "bonding_curve",
        "total_contributions": request.initial_stake,
        "token_supply": request.initial_stake * 1000,
        "created_at": datetime.now(UTC).isoformat(),
    }
    tokenized_entities[request.entity_id] = entity
    return APIResponse(data=entity)


@app.get("/api/v1/tokenization/{entity_id}")
async def get_tokenized_entity(entity_id: str):
    if entity_id not in tokenized_entities:
        raise HTTPException(status_code=404, detail="Entity not found")
    return APIResponse(data=tokenized_entities[entity_id])


@app.post("/api/v1/tokenization/{entity_id}/contribute")
async def contribute_to_bonding_curve(
    entity_id: str,
    amount_virtual: float = Query(..., gt=0),
):
    if entity_id not in tokenized_entities:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity = tokenized_entities[entity_id]
    entity["total_contributions"] += amount_virtual
    entity["token_supply"] += amount_virtual * 1000

    contribution = {
        "entity_id": entity_id,
        "amount_virtual": amount_virtual,
        "tokens_received": amount_virtual * 1000,
        "contributed_at": datetime.now(UTC).isoformat(),
    }

    return APIResponse(data={
        "entity": entity,
        "contribution": contribution,
    })


@app.post("/api/v1/tokenization/{entity_id}/proposals", status_code=201)
async def create_governance_proposal(entity_id: str, request: ProposalCreateRequest):
    if entity_id not in tokenized_entities:
        raise HTTPException(status_code=404, detail="Entity not found")

    proposal_id = str(uuid4())
    proposal = {
        "id": proposal_id,
        "entity_id": entity_id,
        "title": request.title,
        "description": request.description,
        "proposal_type": request.proposal_type,
        "proposed_changes": request.proposed_changes,
        "status": "active",
        "votes_for": 0,
        "votes_against": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    proposals[proposal_id] = proposal
    return APIResponse(data=proposal)


@app.post("/api/v1/tokenization/proposals/{proposal_id}/vote")
async def vote_on_proposal(
    proposal_id: str,
    vote: str = Query(..., regex="^(for|against|abstain)$"),
):
    if proposal_id not in proposals:
        raise HTTPException(status_code=404, detail="Proposal not found")

    proposal = proposals[proposal_id]
    if vote == "for":
        proposal["votes_for"] += 1
    elif vote == "against":
        proposal["votes_against"] += 1

    vote_record = {
        "proposal_id": proposal_id,
        "vote": vote,
        "voting_power": 1.0,
        "voted_at": datetime.now(UTC).isoformat(),
    }
    return APIResponse(data=vote_record)


# ═══════════════════════════════════════════════════════════════════════════
# ACP ROUTES (Agent Commerce Protocol)
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/acp/offerings", status_code=201)
async def register_offering(
    request: OfferingRequest,
    agent_id: str = Query(...),
):
    offering_id = str(uuid4())
    offering = {
        "id": offering_id,
        "agent_id": agent_id,
        "service_type": request.service_type,
        "description": request.description,
        "pricing": request.pricing or {"base_fee": 10.0},
        "status": "active",
        "created_at": datetime.now(UTC).isoformat(),
    }
    offerings[offering_id] = offering
    return APIResponse(data=offering)


@app.get("/api/v1/acp/offerings")
async def search_offerings(
    service_type: str | None = None,
    query: str | None = None,
    max_fee: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    result = list(offerings.values())

    if service_type:
        result = [o for o in result if o.get("service_type") == service_type]
    if max_fee is not None:
        result = [o for o in result if o.get("pricing", {}).get("base_fee", 0) <= max_fee]

    return PaginatedResponse(
        data=result,
        total=len(result),
        page=page,
        per_page=per_page,
    )


@app.post("/api/v1/acp/jobs", status_code=201)
async def create_job(request: JobCreateRequest):
    job_id = str(uuid4())
    job = {
        "job_id": job_id,
        "offering_id": request.offering_id,
        "requirements": request.requirements,
        "max_fee": request.max_fee,
        "status": "requested",
        "phase": "request",
        "created_at": datetime.now(UTC).isoformat(),
    }
    jobs[job_id] = job
    return APIResponse(data=job)


@app.get("/api/v1/acp/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return APIResponse(data=jobs[job_id])


@app.post("/api/v1/acp/jobs/{job_id}/respond")
async def respond_to_job(job_id: str, terms: dict = None):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["status"] = "negotiating"
    jobs[job_id]["phase"] = "negotiation"
    jobs[job_id]["terms"] = terms
    return APIResponse(data=jobs[job_id])


@app.post("/api/v1/acp/jobs/{job_id}/accept")
async def accept_job_terms(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["status"] = "in_progress"
    jobs[job_id]["phase"] = "transaction"
    jobs[job_id]["accepted_at"] = datetime.now(UTC).isoformat()
    return APIResponse(data=jobs[job_id])


@app.post("/api/v1/acp/jobs/{job_id}/deliver")
async def submit_deliverable(job_id: str, deliverable: dict = None):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["status"] = "delivered"
    jobs[job_id]["phase"] = "evaluation"
    jobs[job_id]["deliverable"] = deliverable
    jobs[job_id]["delivered_at"] = datetime.now(UTC).isoformat()
    return APIResponse(data=jobs[job_id])


@app.post("/api/v1/acp/jobs/{job_id}/evaluate")
async def evaluate_deliverable(job_id: str, evaluation: dict = None):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    jobs[job_id]["status"] = "completed"
    jobs[job_id]["phase"] = "settlement"
    jobs[job_id]["evaluation"] = evaluation
    jobs[job_id]["completed_at"] = datetime.now(UTC).isoformat()
    return APIResponse(data=jobs[job_id])


# ═══════════════════════════════════════════════════════════════════════════
# REVENUE ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/revenue/summary")
async def get_revenue_summary(
    entity_id: str | None = None,
    entity_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    # Simulated revenue summary
    return APIResponse(data={
        "total_revenue": 15000.0,
        "period_revenue": 2500.0,
        "revenue_by_type": {
            "acp_fees": 5000.0,
            "tokenization_fees": 3000.0,
            "subscription": 7000.0,
        },
        "entity_count": len(tokenized_entities),
        "active_agents": len(agents),
        "generated_at": datetime.now(UTC).isoformat(),
    })


@app.get("/api/v1/revenue/entities/{entity_id}")
async def get_entity_revenue(
    entity_id: str,
    entity_type: str = Query(...),
):
    # Simulated entity revenue
    return APIResponse(data={
        "entity_id": entity_id,
        "entity_type": entity_type,
        "lifetime_revenue": 1250.0,
        "monthly_revenue": [
            {"month": "2024-01", "revenue": 100.0},
            {"month": "2024-02", "revenue": 150.0},
            {"month": "2024-03", "revenue": 200.0},
        ],
        "revenue_trend": "increasing",
    })


@app.get("/api/v1/revenue/entities/{entity_id}/valuation")
async def get_entity_valuation(
    entity_id: str,
    entity_type: str = Query(...),
    discount_rate: float = Query(0.1, ge=0, le=1),
    growth_rate: float = Query(0.05, ge=0, le=1),
):
    # Simulated DCF valuation
    return APIResponse(data={
        "entity_id": entity_id,
        "entity_type": entity_type,
        "estimated_value": 12500.0,
        "discount_rate": discount_rate,
        "growth_rate": growth_rate,
        "valuation_method": "dcf",
        "projected_revenue_5y": 7500.0,
        "calculated_at": datetime.now(UTC).isoformat(),
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
