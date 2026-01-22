"""
Agent Commerce Protocol (ACP) API Routes

Endpoints for managing ACP service offerings and job lifecycle.
Enables agent-to-agent commerce through the Virtuals Protocol.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from forge.api.dependencies import ActiveUserDep
from forge.services.virtuals_integration import get_virtuals_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/acp", tags=["Agent Commerce Protocol"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateOfferingRequest(BaseModel):
    """Request to create a service offering."""
    agent_id: str = Field(description="ID of the agent offering the service")
    wallet_address: str = Field(description="Agent's wallet address")
    service_type: str = Field(description="Type of service (knowledge_query, semantic_search, etc.)")
    title: str = Field(max_length=200, description="Human-readable title")
    description: str = Field(max_length=2000, description="Detailed description")
    base_fee_virtual: float = Field(ge=0, description="Base fee in VIRTUAL tokens")
    fee_per_unit: float = Field(default=0.0, ge=0, description="Fee per unit (tokens, queries)")
    unit_type: str | None = Field(default=None, description="Unit type for per-unit fees")
    max_execution_time_seconds: int = Field(default=300, ge=1, description="Max execution time")
    tags: list[str] = Field(default_factory=list, description="Tags for discovery")
    input_schema: dict = Field(default_factory=dict, description="Expected input JSON schema")
    output_schema: dict = Field(default_factory=dict, description="Output JSON schema")


class OfferingResponse(BaseModel):
    """Service offering response."""
    id: str
    provider_agent_id: str
    provider_wallet: str
    service_type: str
    title: str
    description: str
    base_fee_virtual: float
    fee_per_unit: float
    unit_type: str | None
    max_execution_time_seconds: int
    is_active: bool
    available_capacity: int
    tags: list[str]
    registry_id: str | None
    created_at: datetime


class CreateJobRequest(BaseModel):
    """Request to create an ACP job."""
    job_offering_id: str = Field(description="ID of the offering to use")
    buyer_agent_id: str = Field(description="ID of the buying agent")
    requirements: str = Field(max_length=5000, description="Detailed requirements")
    max_fee_virtual: float = Field(ge=0, description="Maximum fee willing to pay")
    preferred_deadline: datetime | None = None
    additional_context: dict = Field(default_factory=dict)


class NegotiationTermsRequest(BaseModel):
    """Provider's proposed terms."""
    proposed_fee_virtual: float = Field(ge=0)
    proposed_deadline: datetime
    deliverable_format: str
    deliverable_description: str
    special_conditions: list[str] = Field(default_factory=list)
    requires_evaluator: bool = False
    suggested_evaluator_id: str | None = None


class DeliverableRequest(BaseModel):
    """Deliverable submission."""
    content_type: str = Field(description="Type: json, text, url, file_reference")
    content: dict = Field(description="Deliverable content or reference")
    notes: str = Field(default="", max_length=1000)


class EvaluationRequest(BaseModel):
    """Evaluation result."""
    evaluator_agent_id: str
    result: str = Field(description="approved, rejected, or needs_revision")
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(max_length=2000)
    met_requirements: list[str] = Field(default_factory=list)
    unmet_requirements: list[str] = Field(default_factory=list)
    suggested_improvements: list[str] = Field(default_factory=list)


class DisputeRequest(BaseModel):
    """Dispute filing."""
    filed_by: str = Field(description="buyer or provider")
    reason: str = Field(max_length=2000)
    evidence: list[dict] = Field(default_factory=list)
    requested_resolution: str = Field(description="full_refund, partial_refund, renegotiate, arbitration")


class JobResponse(BaseModel):
    """ACP job response."""
    id: str
    job_offering_id: str
    buyer_agent_id: str
    buyer_wallet: str
    provider_agent_id: str
    provider_wallet: str
    current_phase: str
    status: str
    requirements: str
    agreed_fee_virtual: float
    agreed_deadline: datetime | None
    escrow_amount_virtual: float
    escrow_released: bool
    is_disputed: bool
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """List of jobs response."""
    jobs: list[JobResponse]
    total: int


# ============================================================================
# Offerings Endpoints
# ============================================================================

@router.post("/offerings", response_model=OfferingResponse)
async def create_offering(
    request: CreateOfferingRequest,
    current_user: ActiveUserDep,
) -> OfferingResponse:
    """
    Register a new service offering.

    Makes the agent's service discoverable by other agents.
    Requires user authentication to verify agent ownership.
    """
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import JobOffering

        offering = JobOffering(
            provider_agent_id=request.agent_id,
            provider_wallet=request.wallet_address,
            service_type=request.service_type,
            title=request.title,
            description=request.description,
            base_fee_virtual=request.base_fee_virtual,
            fee_per_unit=request.fee_per_unit,
            unit_type=request.unit_type,
            max_execution_time_seconds=request.max_execution_time_seconds,
            tags=request.tags,
            input_schema=request.input_schema,
            output_schema=request.output_schema,
        )

        result = await service.register_offering(
            agent_id=request.agent_id,
            agent_wallet=request.wallet_address,
            offering=offering,
        )

        return OfferingResponse(
            id=result.id,
            provider_agent_id=result.provider_agent_id,
            provider_wallet=result.provider_wallet,
            service_type=result.service_type,
            title=result.title,
            description=result.description,
            base_fee_virtual=result.base_fee_virtual,
            fee_per_unit=result.fee_per_unit,
            unit_type=result.unit_type,
            max_execution_time_seconds=result.max_execution_time_seconds,
            is_active=result.is_active,
            available_capacity=result.available_capacity,
            tags=result.tags,
            registry_id=result.registry_id,
            created_at=result.created_at,
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create offering: {e}")
        raise HTTPException(status_code=400, detail="Failed to create offering")


@router.get("/offerings", response_model=list[OfferingResponse])
async def search_offerings(
    service_type: str | None = Query(None, description="Filter by service type"),
    query: str | None = Query(None, description="Search in title/description"),
    max_fee: float | None = Query(None, ge=0, description="Maximum base fee"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
) -> list[OfferingResponse]:
    """
    Search available service offerings.

    Find providers that can fulfill specific service needs.
    """
    try:
        service = get_virtuals_service()

        results = await service.search_offerings(
            service_type=service_type,
            query=query,
            max_fee=max_fee,
            limit=limit,
        )

        return [
            OfferingResponse(
                id=o.id,
                provider_agent_id=o.provider_agent_id,
                provider_wallet=o.provider_wallet,
                service_type=o.service_type,
                title=o.title,
                description=o.description,
                base_fee_virtual=o.base_fee_virtual,
                fee_per_unit=o.fee_per_unit,
                unit_type=o.unit_type,
                max_execution_time_seconds=o.max_execution_time_seconds,
                is_active=o.is_active,
                available_capacity=o.available_capacity,
                tags=o.tags,
                registry_id=o.registry_id,
                created_at=o.created_at,
            )
            for o in results
        ]

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search offerings: {e}")
        raise HTTPException(status_code=500, detail="Failed to search offerings")


@router.get("/offerings/{offering_id}", response_model=OfferingResponse)
async def get_offering(offering_id: str) -> OfferingResponse:
    """Get a specific offering by ID."""
    try:
        service = get_virtuals_service()
        offering = await service.get_offering(offering_id)

        if not offering:
            raise HTTPException(status_code=404, detail="Offering not found")

        return OfferingResponse(
            id=offering.id,
            provider_agent_id=offering.provider_agent_id,
            provider_wallet=offering.provider_wallet,
            service_type=offering.service_type,
            title=offering.title,
            description=offering.description,
            base_fee_virtual=offering.base_fee_virtual,
            fee_per_unit=offering.fee_per_unit,
            unit_type=offering.unit_type,
            max_execution_time_seconds=offering.max_execution_time_seconds,
            is_active=offering.is_active,
            available_capacity=offering.available_capacity,
            tags=offering.tags,
            registry_id=offering.registry_id,
            created_at=offering.created_at,
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get offering: {e}")
        raise HTTPException(status_code=500, detail="Failed to get offering")


# ============================================================================
# Jobs Endpoints
# ============================================================================

@router.post("/jobs", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    current_user: ActiveUserDep,
) -> JobResponse:
    """
    Create a new ACP job from an offering.

    Initiates the Request phase of the ACP protocol.
    """
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import ACPJobCreate

        create_request = ACPJobCreate(
            job_offering_id=request.job_offering_id,
            buyer_agent_id=request.buyer_agent_id,
            requirements=request.requirements,
            max_fee_virtual=request.max_fee_virtual,
            preferred_deadline=request.preferred_deadline,
            additional_context=request.additional_context,
        )

        # For now, use user ID as buyer wallet (would be actual wallet in production)
        buyer_wallet = f"0x{current_user.id[:40]}"

        job = await service.create_job(
            create_request=create_request,
            buyer_wallet=buyer_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job")


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get a job by ID."""
    try:
        service = get_virtuals_service()
        job = await service.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return _job_to_response(job)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get job: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job")


@router.post("/jobs/{job_id}/respond", response_model=JobResponse)
async def respond_to_job(
    job_id: str,
    request: NegotiationTermsRequest,
    current_user: ActiveUserDep,
) -> JobResponse:
    """
    Provider responds to a job request with proposed terms.

    Transitions job from REQUEST to NEGOTIATION phase.
    """
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import ACPNegotiationTerms

        terms = ACPNegotiationTerms(
            job_id=job_id,
            proposed_fee_virtual=request.proposed_fee_virtual,
            proposed_deadline=request.proposed_deadline,
            deliverable_format=request.deliverable_format,
            deliverable_description=request.deliverable_description,
            special_conditions=request.special_conditions,
            requires_evaluator=request.requires_evaluator,
            suggested_evaluator_id=request.suggested_evaluator_id,
        )

        provider_wallet = f"0x{current_user.id[:40]}"

        job = await service.respond_to_job(
            job_id=job_id,
            terms=terms,
            provider_wallet=provider_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to respond to job: {e}")
        raise HTTPException(status_code=500, detail="Failed to respond to job")


@router.post("/jobs/{job_id}/accept", response_model=JobResponse)
async def accept_job_terms(
    job_id: str,
    current_user: ActiveUserDep,
) -> JobResponse:
    """
    Buyer accepts proposed terms and initiates escrow.

    Transitions job from NEGOTIATION to TRANSACTION phase.
    Locks funds in escrow on-chain.
    """
    try:
        service = get_virtuals_service()

        buyer_wallet = f"0x{current_user.id[:40]}"

        job = await service.accept_terms(
            job_id=job_id,
            buyer_wallet=buyer_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to accept terms: {e}")
        raise HTTPException(status_code=500, detail="Failed to accept terms")


@router.post("/jobs/{job_id}/deliver", response_model=JobResponse)
async def submit_deliverable(
    job_id: str,
    request: DeliverableRequest,
    current_user: ActiveUserDep,
) -> JobResponse:
    """
    Provider submits deliverables for the job.

    Transitions job to EVALUATION phase.
    """
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import ACPDeliverable

        deliverable = ACPDeliverable(
            job_id=job_id,
            content_type=request.content_type,
            content=request.content,
            notes=request.notes,
        )

        provider_wallet = f"0x{current_user.id[:40]}"

        job = await service.submit_deliverable(
            job_id=job_id,
            deliverable=deliverable,
            provider_wallet=provider_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit deliverable: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit deliverable")


@router.post("/jobs/{job_id}/evaluate", response_model=JobResponse)
async def evaluate_deliverable(
    job_id: str,
    request: EvaluationRequest,
    current_user: ActiveUserDep,
) -> JobResponse:
    """
    Evaluate deliverable and settle transaction.

    Approval releases escrow to provider.
    Rejection initiates dispute process.
    """
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import ACPEvaluation

        evaluation = ACPEvaluation(
            job_id=job_id,
            evaluator_agent_id=request.evaluator_agent_id,
            result=request.result,
            score=request.score,
            feedback=request.feedback,
            met_requirements=request.met_requirements,
            unmet_requirements=request.unmet_requirements,
            suggested_improvements=request.suggested_improvements,
        )

        evaluator_wallet = f"0x{current_user.id[:40]}"

        job = await service.evaluate_deliverable(
            job_id=job_id,
            evaluation=evaluation,
            evaluator_wallet=evaluator_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to evaluate: {e}")
        raise HTTPException(status_code=500, detail="Failed to evaluate deliverable")


@router.post("/jobs/{job_id}/dispute", response_model=JobResponse)
async def file_dispute(
    job_id: str,
    request: DisputeRequest,
    current_user: ActiveUserDep,
) -> JobResponse:
    """File a dispute for a job."""
    try:
        service = get_virtuals_service()

        from forge.virtuals.models.acp import ACPDispute

        dispute = ACPDispute(
            job_id=job_id,
            filed_by=request.filed_by,
            reason=request.reason,
            evidence=request.evidence,
            requested_resolution=request.requested_resolution,
        )

        filer_wallet = f"0x{current_user.id[:40]}"

        job = await service.file_dispute(
            job_id=job_id,
            dispute=dispute,
            filer_wallet=filer_wallet,
        )

        return _job_to_response(job)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to file dispute: {e}")
        raise HTTPException(status_code=500, detail="Failed to file dispute")


@router.get("/jobs/buyer/{agent_id}", response_model=JobListResponse)
async def get_buyer_jobs(
    agent_id: str,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
) -> JobListResponse:
    """Get jobs where agent is the buyer."""
    try:
        service = get_virtuals_service()

        jobs = await service.get_buyer_jobs(
            buyer_agent_id=agent_id,
            status=status,
            limit=limit,
        )

        return JobListResponse(
            jobs=[_job_to_response(j) for j in jobs],
            total=len(jobs),
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get buyer jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get jobs")


@router.get("/jobs/provider/{agent_id}", response_model=JobListResponse)
async def get_provider_jobs(
    agent_id: str,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
) -> JobListResponse:
    """Get jobs where agent is the provider."""
    try:
        service = get_virtuals_service()

        jobs = await service.get_provider_jobs(
            provider_agent_id=agent_id,
            status=status,
            limit=limit,
        )

        return JobListResponse(
            jobs=[_job_to_response(j) for j in jobs],
            total=len(jobs),
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get provider jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get jobs")


# ============================================================================
# Helper Functions
# ============================================================================

def _job_to_response(job) -> JobResponse:
    """Convert ACPJob to JobResponse."""
    return JobResponse(
        id=job.id,
        job_offering_id=job.job_offering_id,
        buyer_agent_id=job.buyer_agent_id,
        buyer_wallet=job.buyer_wallet,
        provider_agent_id=job.provider_agent_id,
        provider_wallet=job.provider_wallet,
        current_phase=job.current_phase.value if hasattr(job.current_phase, 'value') else str(job.current_phase),
        status=job.status.value if hasattr(job.status, 'value') else str(job.status),
        requirements=job.requirements,
        agreed_fee_virtual=job.agreed_fee_virtual,
        agreed_deadline=job.agreed_deadline,
        escrow_amount_virtual=job.escrow_amount_virtual,
        escrow_released=job.escrow_released,
        is_disputed=job.is_disputed,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
