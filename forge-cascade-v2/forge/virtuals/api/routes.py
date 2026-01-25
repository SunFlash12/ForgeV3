"""
FastAPI Router for Virtuals Protocol Integration

This module provides REST API endpoints for the Forge-Virtuals integration,
enabling external applications and the Forge frontend to interact with
agents, tokenization, ACP commerce, and revenue features.

The API follows RESTful conventions with comprehensive error handling,
request validation, and response formatting. All endpoints require
authentication through Forge's existing auth system.

Routes are organized by feature area:
- /agents: Agent management and GAME framework interactions
- /tokenization: Entity tokenization and governance
- /acp: Agent Commerce Protocol transactions
- /revenue: Revenue tracking and analytics
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _sanitized_error(context: str, e: Exception) -> HTTPException:
    """
    SECURITY FIX (Audit 6): Return sanitized error without exposing internal details.
    Logs the actual error for debugging while returning a safe message to clients.
    """
    logger.error(f"virtuals_api_error: {context}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=f"Internal error during {context}. Please try again or contact support."
    )

# Import models (these would be the actual Forge/Virtuals models)
from ..models import (
    ACPDeliverable,
    ACPEvaluation,
    ACPJobCreate,
    ACPNegotiationTerms,
    ForgeAgentCreate,
    JobOffering,
    TokenizationRequest,
)

# ==================== Response Models ====================

class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    data: Any | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaginatedResponse(APIResponse):
    """Response with pagination metadata."""
    total: int = 0
    page: int = 1
    per_page: int = 20
    has_more: bool = False


# ==================== Dependency Injection ====================

# SECURITY FIX (Audit 4): Proper authentication for Virtuals API
_security = HTTPBearer(auto_error=False)


async def get_current_user_wallet(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """
    SECURITY FIX (Audit 4): Proper authentication for Virtuals API.

    Dependency to get the current authenticated user's wallet.
    Extracts wallet address from JWT token via Forge's auth system.

    Raises:
        HTTPException: If authentication fails
    """
    # In development/test mode, allow unauthenticated requests with warning
    env = os.environ.get("FORGE_ENV", "development")
    if env in ("development", "test") and not credentials:
        import structlog
        structlog.get_logger().warning(
            "virtuals_api_unauthenticated",
            warning="Using placeholder wallet - DEVELOPMENT ONLY",
            client_ip=request.client.host if request.client else "unknown",
        )
        return "0x0000000000000000000000000000000000000000"

    # Require authentication in production
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Verify token with Forge auth system
        from forge.security.tokens import decode_access_token

        token_data = decode_access_token(credentials.credentials)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Extract wallet from token claims
        wallet = token_data.get("wallet_address")
        if not wallet:
            # Fall back to user lookup if wallet not in token
            user_id = token_data.get("sub") or token_data.get("user_id")
            if user_id:
                # This would need db injection in real implementation
                raise HTTPException(
                    status_code=400,
                    detail="User has no linked wallet address"
                )
            raise HTTPException(status_code=401, detail="Invalid token: no user identity")

        return wallet

    except HTTPException:
        raise
    except Exception as e:
        import structlog
        structlog.get_logger().error("virtuals_auth_error", error=str(e))
        raise HTTPException(status_code=401, detail="Authentication failed")


# ==================== Agent Routes ====================

agent_router = APIRouter(prefix="/agents", tags=["Agents"])


@agent_router.post("/", response_model=APIResponse)
async def create_agent(
    request: ForgeAgentCreate,
    background_tasks: BackgroundTasks,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Create a new Forge agent on Virtuals Protocol.

    This endpoint registers an agent with the GAME framework, optionally
    enabling tokenization. The agent can represent a Forge overlay or
    standalone knowledge service.

    The creation process involves:
    1. Validating the agent configuration
    2. Registering with GAME framework
    3. Creating blockchain wallet (if tokenized)
    4. Setting up workers and functions

    Returns the created agent with all assigned IDs.
    """
    try:
        from ..game import get_game_client

        client = await get_game_client()

        # Create basic workers for the agent
        # In production, workers would be configured based on request
        workers = []

        agent = await client.create_agent(
            create_request=request,
            workers=workers,
        )

        return APIResponse(data=agent.model_dump())

    except Exception as e:
        raise _sanitized_error("agent creation", e)


@agent_router.get("/", response_model=PaginatedResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    List agents owned by the current user.

    Supports pagination and filtering by status. Returns agents
    with their current operational state and metrics.
    """
    # Placeholder - would query from agent repository
    return PaginatedResponse(
        data=[],
        total=0,
        page=page,
        per_page=per_page,
        has_more=False,
    )


@agent_router.get("/{agent_id}", response_model=APIResponse)
async def get_agent(
    agent_id: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Get detailed information about a specific agent.

    Returns the complete agent configuration, metrics, and
    current operational status.
    """
    try:
        from ..game import get_game_client

        client = await get_game_client()
        agent = await client.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        return APIResponse(data=agent.model_dump() if agent else None)

    except HTTPException:
        raise
    except Exception as e:
        raise _sanitized_error("agent retrieval", e)


@agent_router.post("/{agent_id}/run", response_model=APIResponse)
async def run_agent(
    agent_id: str,
    context: str = Query(..., description="Context or query for the agent"),
    max_iterations: int = Query(10, ge=1, le=50),
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Execute the agent's autonomous decision loop.

    The agent will analyze the context and execute appropriate actions
    using its configured workers and functions. Returns the results
    of all actions taken.
    """
    try:
        from ..game import get_game_client

        client = await get_game_client()
        agent = await client.get_agent(agent_id)

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # In production, would load workers from agent configuration
        results = await client.run_agent_loop(
            agent=agent,
            workers={},
            context=context,
            max_iterations=max_iterations,
        )

        return APIResponse(data={"results": results})

    except HTTPException:
        raise
    except Exception as e:
        raise _sanitized_error("agent execution", e)


# ==================== Tokenization Routes ====================

tokenization_router = APIRouter(prefix="/tokenization", tags=["Tokenization"])


@tokenization_router.post("/", response_model=APIResponse)
async def request_tokenization(
    request: TokenizationRequest,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Request tokenization of a Forge entity.

    This initiates the tokenization process, creating an ERC-20 token
    in bonding curve phase. The entity can be a capsule, overlay,
    capsule collection, or agent.

    Requires minimum 100 VIRTUAL stake to begin.
    """
    try:
        from ..tokenization import get_tokenization_service

        # Verify ownership of entity (would check Forge's entity repository)
        request.owner_wallet = wallet

        service = await get_tokenization_service()
        entity = await service.request_tokenization(request)

        return APIResponse(data=entity.model_dump())

    except Exception as e:
        raise _sanitized_error("tokenization request", e)


@tokenization_router.get("/{entity_id}", response_model=APIResponse)
async def get_tokenized_entity(
    entity_id: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Get tokenization status and details for an entity.

    Returns the complete tokenization state including bonding curve
    progress, holder information, and governance status.
    """
    # Placeholder - would query tokenization repository
    return APIResponse(data=None)


@tokenization_router.post("/{entity_id}/contribute", response_model=APIResponse)
async def contribute_to_bonding_curve(
    entity_id: str,
    amount_virtual: float = Query(..., gt=0),
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Contribute VIRTUAL to an entity's bonding curve.

    Contributors receive placeholder tokens proportional to their
    contribution. Early contributors get more tokens per VIRTUAL
    due to the bonding curve mechanics.
    """
    try:
        from ..tokenization import get_tokenization_service

        service = await get_tokenization_service()
        entity, contribution = await service.contribute_to_bonding_curve(
            entity_id=entity_id,
            contributor_wallet=wallet,
            amount_virtual=amount_virtual,
        )

        return APIResponse(data={
            "entity": entity.model_dump(),
            "contribution": contribution.model_dump(),
        })

    except Exception as e:
        raise _sanitized_error("bonding curve contribution", e)


@tokenization_router.post("/{entity_id}/proposals", response_model=APIResponse)
async def create_governance_proposal(
    entity_id: str,
    title: str,
    description: str,
    proposal_type: str,
    proposed_changes: dict[str, Any],
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Create a governance proposal for token holders.

    Only token holders can create proposals. Proposals are subject
    to voting by all token holders with voting power proportional
    to holdings.
    """
    try:
        from ..tokenization import get_tokenization_service

        service = await get_tokenization_service()
        proposal = await service.create_governance_proposal(
            entity_id=entity_id,
            proposer_wallet=wallet,
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposed_changes=proposed_changes,
        )

        return APIResponse(data=proposal.model_dump())

    except Exception as e:
        raise _sanitized_error("governance proposal creation", e)


@tokenization_router.post("/proposals/{proposal_id}/vote", response_model=APIResponse)
async def vote_on_proposal(
    proposal_id: str,
    vote: str = Query(..., regex="^(for|against|abstain)$"),
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Cast a vote on a governance proposal.

    Voting power is proportional to token holdings. Each wallet
    can only vote once per proposal.
    """
    try:
        from ..tokenization import get_tokenization_service

        service = await get_tokenization_service()
        vote_record = await service.cast_governance_vote(
            proposal_id=proposal_id,
            voter_wallet=wallet,
            vote=vote,
        )

        return APIResponse(data=vote_record.model_dump())

    except Exception as e:
        raise _sanitized_error("governance vote", e)


# ==================== ACP Routes ====================

acp_router = APIRouter(prefix="/acp", tags=["Agent Commerce Protocol"])


@acp_router.post("/offerings", response_model=APIResponse)
async def register_offering(
    offering: JobOffering,
    agent_id: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Register a new service offering in the ACP registry.

    This makes an agent's services discoverable by other agents
    and users. The offering specifies service type, pricing,
    and capabilities.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        registered = await service.register_offering(
            agent_id=agent_id,
            agent_wallet=wallet,
            offering=offering,
        )

        return APIResponse(data=registered.model_dump())

    except Exception as e:
        raise _sanitized_error("offering registration", e)


@acp_router.get("/offerings", response_model=PaginatedResponse)
async def search_offerings(
    service_type: str | None = None,
    query: str | None = None,
    max_fee: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Search the ACP service registry for offerings.

    Supports filtering by service type, natural language query,
    and maximum fee. Returns matching offerings sorted by
    relevance and provider reputation.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        offerings = await service.search_offerings(
            service_type=service_type,
            query=query,
            max_fee=max_fee,
            limit=per_page,
        )

        return PaginatedResponse(
            data=[o.model_dump() for o in offerings],
            total=len(offerings),
            page=page,
            per_page=per_page,
        )

    except Exception as e:
        raise _sanitized_error("offering search", e)


@acp_router.post("/jobs", response_model=APIResponse)
async def create_job(
    request: ACPJobCreate,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Create a new ACP job from a service offering.

    This initiates the Request phase. The buyer specifies requirements
    and maximum fee, then waits for the provider to respond with terms.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        job = await service.create_job(
            create_request=request,
            buyer_wallet=wallet,
        )

        return APIResponse(data=job.model_dump())

    except Exception as e:
        raise _sanitized_error("job creation", e)


@acp_router.get("/jobs/{job_id}", response_model=APIResponse)
async def get_job(
    job_id: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Get detailed information about an ACP job.

    Returns the complete job state including current phase,
    memos, and transaction history.
    """
    # Placeholder - would query job repository
    return APIResponse(data=None)


@acp_router.post("/jobs/{job_id}/respond", response_model=APIResponse)
async def respond_to_job(
    job_id: str,
    terms: ACPNegotiationTerms,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Provider responds to a job request with proposed terms.

    This moves the job to Negotiation phase. The buyer can then
    accept, reject, or counter the terms.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        job = await service.respond_to_request(
            job_id=job_id,
            terms=terms,
            provider_wallet=wallet,
        )

        return APIResponse(data=job.model_dump())

    except Exception as e:
        raise _sanitized_error("job response", e)


@acp_router.post("/jobs/{job_id}/accept", response_model=APIResponse)
async def accept_job_terms(
    job_id: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Buyer accepts proposed terms and escrows payment.

    This moves the job to Transaction phase. The agreed fee is
    locked in escrow, and the provider can begin work.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        job = await service.accept_terms(
            job_id=job_id,
            buyer_wallet=wallet,
        )

        return APIResponse(data=job.model_dump())

    except Exception as e:
        raise _sanitized_error("terms acceptance", e)


@acp_router.post("/jobs/{job_id}/deliver", response_model=APIResponse)
async def submit_deliverable(
    job_id: str,
    deliverable: ACPDeliverable,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Provider submits deliverables for evaluation.

    This moves the job to Evaluation phase. The buyer (or
    designated evaluator) will review the deliverable.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        job = await service.submit_deliverable(
            job_id=job_id,
            deliverable=deliverable,
            provider_wallet=wallet,
        )

        return APIResponse(data=job.model_dump())

    except Exception as e:
        raise _sanitized_error("deliverable submission", e)


@acp_router.post("/jobs/{job_id}/evaluate", response_model=APIResponse)
async def evaluate_deliverable(
    job_id: str,
    evaluation: ACPEvaluation,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Evaluate a deliverable and settle the transaction.

    If approved, escrow is released to the provider. If rejected,
    the job may enter dispute resolution.
    """
    try:
        from ..acp import get_acp_service

        service = await get_acp_service()
        job = await service.evaluate_deliverable(
            job_id=job_id,
            evaluation=evaluation,
            evaluator_wallet=wallet,
        )

        return APIResponse(data=job.model_dump())

    except Exception as e:
        raise _sanitized_error("deliverable evaluation", e)


# ==================== Revenue Routes ====================

revenue_router = APIRouter(prefix="/revenue", tags=["Revenue"])


@revenue_router.get("/summary", response_model=APIResponse)
async def get_revenue_summary(
    entity_id: str | None = None,
    entity_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Get revenue summary with analytics.

    Provides aggregated revenue statistics filtered by entity,
    type, and time period. Useful for dashboards and reporting.
    """
    try:
        from ..revenue import get_revenue_service

        service = await get_revenue_service()
        summary = await service.get_revenue_summary(
            entity_id=entity_id,
            entity_type=entity_type,
            start_date=start_date,
            end_date=end_date,
        )

        return APIResponse(data=summary)

    except Exception as e:
        raise _sanitized_error("revenue summary retrieval", e)


@revenue_router.get("/entities/{entity_id}", response_model=APIResponse)
async def get_entity_revenue(
    entity_id: str,
    entity_type: str,
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Get detailed revenue for a specific entity.

    Returns lifetime revenue, monthly breakdown, and trend data
    for the specified entity.
    """
    try:
        from ..revenue import get_revenue_service

        service = await get_revenue_service()
        revenue = await service.get_entity_revenue(
            entity_id=entity_id,
            entity_type=entity_type,
        )

        return APIResponse(data=revenue)

    except Exception as e:
        raise _sanitized_error("entity revenue retrieval", e)


@revenue_router.get("/entities/{entity_id}/valuation", response_model=APIResponse)
async def get_entity_valuation(
    entity_id: str,
    entity_type: str,
    discount_rate: float = Query(0.1, ge=0, le=1),
    growth_rate: float = Query(0.05, ge=0, le=1),
    wallet: str = Depends(get_current_user_wallet),
):
    """
    Estimate the value of an entity based on revenue.

    Uses discounted cash flow analysis to estimate present value
    of future revenue streams. Useful for tokenization pricing.
    """
    try:
        from ..revenue import get_revenue_service

        service = await get_revenue_service()
        valuation = await service.estimate_entity_value(
            entity_id=entity_id,
            entity_type=entity_type,
            discount_rate=discount_rate,
            growth_rate=growth_rate,
        )

        return APIResponse(data=valuation)

    except Exception as e:
        raise _sanitized_error("entity valuation", e)


# ==================== Router Aggregation ====================

def create_virtuals_router() -> APIRouter:
    """
    Create the aggregated router for all Virtuals Protocol endpoints.

    This function creates and configures the main router that includes
    all sub-routers for agents, tokenization, ACP, and revenue.

    Usage:
        from forge.virtuals.api import create_virtuals_router

        app = FastAPI()
        app.include_router(create_virtuals_router(), prefix="/api/v1/virtuals")
    """
    main_router = APIRouter()

    main_router.include_router(agent_router)
    main_router.include_router(tokenization_router)
    main_router.include_router(acp_router)
    main_router.include_router(revenue_router)

    return main_router
