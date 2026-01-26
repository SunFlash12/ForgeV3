"""
ACP (Agent Commerce Protocol) Repository

Repository for managing ACP jobs and offerings in Neo4j.
Handles the complete lifecycle of agent-to-agent commerce transactions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog

from forge.database.client import Neo4jClient
from forge.virtuals.models.acp import (
    ACPJob,
    ACPJobStatus,
    ACPPhase,
    JobOffering,
)

logger = structlog.get_logger(__name__)


class OfferingRepository:
    """
    Repository for ACP Job Offerings.

    Manages service offerings that agents advertise for discovery
    by other agents and users.
    """

    def __init__(self, client: Neo4jClient):
        """Initialize with database client."""
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def create(self, offering: JobOffering) -> JobOffering:
        """
        Create a new job offering.

        Args:
            offering: The offering to create

        Returns:
            Created offering with ID
        """
        now = datetime.now(UTC)

        query = """
        CREATE (o:JobOffering {
            id: $id,
            provider_agent_id: $provider_agent_id,
            provider_wallet: $provider_wallet,
            service_type: $service_type,
            title: $title,
            description: $description,
            input_schema: $input_schema,
            output_schema: $output_schema,
            supported_formats: $supported_formats,
            base_fee_virtual: $base_fee_virtual,
            fee_per_unit: $fee_per_unit,
            unit_type: $unit_type,
            max_execution_time_seconds: $max_execution_time_seconds,
            requires_escrow: $requires_escrow,
            min_buyer_trust_score: $min_buyer_trust_score,
            is_active: $is_active,
            available_capacity: $available_capacity,
            tags: $tags,
            registry_id: $registry_id,
            registration_tx_hash: $registration_tx_hash,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN o
        """

        params = {
            "id": offering.id,
            "provider_agent_id": offering.provider_agent_id,
            "provider_wallet": offering.provider_wallet,
            "service_type": offering.service_type,
            "title": offering.title,
            "description": offering.description,
            "input_schema": json.dumps(offering.input_schema),
            "output_schema": json.dumps(offering.output_schema),
            "supported_formats": offering.supported_formats,
            "base_fee_virtual": offering.base_fee_virtual,
            "fee_per_unit": offering.fee_per_unit,
            "unit_type": offering.unit_type,
            "max_execution_time_seconds": offering.max_execution_time_seconds,
            "requires_escrow": offering.requires_escrow,
            "min_buyer_trust_score": offering.min_buyer_trust_score,
            "is_active": offering.is_active,
            "available_capacity": offering.available_capacity,
            "tags": offering.tags,
            "registry_id": offering.registry_id,
            "registration_tx_hash": offering.registration_tx_hash,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        await self.client.execute_write(query, params)

        self.logger.info(
            "offering_created",
            offering_id=offering.id,
            service_type=offering.service_type,
        )

        return offering

    async def get_by_id(self, offering_id: str) -> JobOffering | None:
        """Get an offering by ID."""
        query = """
        MATCH (o:JobOffering {id: $id})
        RETURN o
        """

        result = await self.client.execute_single(query, {"id": offering_id})

        if not result:
            return None

        return self._to_model(result.get("o", result))

    async def get_by_agent(self, agent_id: str) -> list[JobOffering]:
        """Get all offerings for a specific agent."""
        query = """
        MATCH (o:JobOffering {provider_agent_id: $agent_id})
        WHERE o.is_active = true
        RETURN o
        ORDER BY o.created_at DESC
        """

        results = await self.client.execute_read(query, {"agent_id": agent_id})

        return [self._to_model(r.get("o", r)) for r in results if r]

    async def search(
        self,
        service_type: str | None = None,
        query: str | None = None,
        max_fee: float | None = None,
        min_provider_reputation: float = 0.0,
        limit: int = 20,
    ) -> list[JobOffering]:
        """
        Search offerings with filters.

        Args:
            service_type: Filter by service type
            query: Text search in title/description
            max_fee: Maximum base fee
            min_provider_reputation: Minimum provider reputation
            limit: Max results

        Returns:
            List of matching offerings
        """
        conditions = ["o.is_active = true"]
        params: dict[str, Any] = {"limit": limit}

        if service_type:
            conditions.append("o.service_type = $service_type")
            params["service_type"] = service_type

        if max_fee is not None:
            conditions.append("o.base_fee_virtual <= $max_fee")
            params["max_fee"] = max_fee

        if query:
            conditions.append(
                "(toLower(o.title) CONTAINS toLower($query) OR "
                "toLower(o.description) CONTAINS toLower($query))"
            )
            params["query"] = query

        where_clause = " AND ".join(conditions)

        cypher = f"""
        MATCH (o:JobOffering)
        WHERE {where_clause}
        RETURN o
        ORDER BY o.base_fee_virtual ASC, o.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_read(cypher, params)

        return [self._to_model(r.get("o", r)) for r in results if r]

    async def update(self, offering: JobOffering) -> JobOffering:
        """Update an offering."""
        now = datetime.now(UTC)

        query = """
        MATCH (o:JobOffering {id: $id})
        SET o.title = $title,
            o.description = $description,
            o.base_fee_virtual = $base_fee_virtual,
            o.fee_per_unit = $fee_per_unit,
            o.is_active = $is_active,
            o.available_capacity = $available_capacity,
            o.tags = $tags,
            o.updated_at = $updated_at
        RETURN o
        """

        params = {
            "id": offering.id,
            "title": offering.title,
            "description": offering.description,
            "base_fee_virtual": offering.base_fee_virtual,
            "fee_per_unit": offering.fee_per_unit,
            "is_active": offering.is_active,
            "available_capacity": offering.available_capacity,
            "tags": offering.tags,
            "updated_at": now.isoformat(),
        }

        await self.client.execute_write(query, params)
        offering.updated_at = now

        return offering

    async def delete(self, offering_id: str) -> bool:
        """Soft delete an offering (set inactive)."""
        query = """
        MATCH (o:JobOffering {id: $id})
        SET o.is_active = false, o.updated_at = $updated_at
        RETURN o.id AS id
        """

        result = await self.client.execute_single(
            query,
            {"id": offering_id, "updated_at": datetime.now(UTC).isoformat()}
        )

        return result is not None

    def _to_model(self, record: dict[str, Any]) -> JobOffering:
        """Convert Neo4j record to JobOffering model."""
        # Parse JSON fields
        if isinstance(record.get("input_schema"), str):
            record["input_schema"] = json.loads(record["input_schema"])
        if isinstance(record.get("output_schema"), str):
            record["output_schema"] = json.loads(record["output_schema"])

        # Parse datetime fields
        for field in ["created_at", "updated_at"]:
            if isinstance(record.get(field), str):
                record[field] = datetime.fromisoformat(record[field])

        return JobOffering(**record)


class ACPJobRepository:
    """
    Repository for ACP Jobs.

    Manages the complete lifecycle of agent-to-agent commerce
    transactions from request through settlement.
    """

    def __init__(self, client: Neo4jClient):
        """Initialize with database client."""
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def create(self, job: ACPJob) -> ACPJob:
        """
        Create a new ACP job.

        Args:
            job: The job to create

        Returns:
            Created job
        """
        now = datetime.now(UTC)

        query = """
        CREATE (j:ACPJob {
            id: $id,
            job_offering_id: $job_offering_id,
            buyer_agent_id: $buyer_agent_id,
            buyer_wallet: $buyer_wallet,
            provider_agent_id: $provider_agent_id,
            provider_wallet: $provider_wallet,
            evaluator_agent_id: $evaluator_agent_id,
            current_phase: $current_phase,
            status: $status,
            requirements: $requirements,
            request_memo: $request_memo,
            requirement_memo: $requirement_memo,
            agreement_memo: $agreement_memo,
            transaction_memo: $transaction_memo,
            deliverable_memo: $deliverable_memo,
            evaluation_memo: $evaluation_memo,
            negotiated_terms: $negotiated_terms,
            agreed_fee_virtual: $agreed_fee_virtual,
            agreed_deadline: $agreed_deadline,
            escrow_tx_hash: $escrow_tx_hash,
            escrow_amount_virtual: $escrow_amount_virtual,
            escrow_released: $escrow_released,
            deliverable_content: $deliverable_content,
            deliverable_url: $deliverable_url,
            delivered_at: $delivered_at,
            evaluation_result: $evaluation_result,
            evaluation_score: $evaluation_score,
            evaluation_feedback: $evaluation_feedback,
            evaluated_at: $evaluated_at,
            completed_at: $completed_at,
            settlement_tx_hash: $settlement_tx_hash,
            is_disputed: $is_disputed,
            dispute_reason: $dispute_reason,
            dispute_resolution: $dispute_resolution,
            request_timeout: $request_timeout,
            negotiation_timeout: $negotiation_timeout,
            execution_timeout: $execution_timeout,
            evaluation_timeout: $evaluation_timeout,
            created_at: $created_at,
            updated_at: $updated_at
        })
        // Create relationship to offering
        WITH j
        MATCH (o:JobOffering {id: $job_offering_id})
        CREATE (j)-[:FOR_OFFERING]->(o)
        RETURN j
        """

        # Serialize memos to JSON
        def serialize_memo(memo: object) -> str | None:
            if memo is None:
                return None
            if hasattr(memo, "model_dump"):
                return json.dumps(memo.model_dump(), default=str)
            return None

        params = {
            "id": job.id,
            "job_offering_id": job.job_offering_id,
            "buyer_agent_id": job.buyer_agent_id,
            "buyer_wallet": job.buyer_wallet,
            "provider_agent_id": job.provider_agent_id,
            "provider_wallet": job.provider_wallet,
            "evaluator_agent_id": job.evaluator_agent_id,
            "current_phase": job.current_phase.value,
            "status": job.status.value,
            "requirements": job.requirements,
            "request_memo": serialize_memo(job.request_memo),
            "requirement_memo": serialize_memo(job.requirement_memo),
            "agreement_memo": serialize_memo(job.agreement_memo),
            "transaction_memo": serialize_memo(job.transaction_memo),
            "deliverable_memo": serialize_memo(job.deliverable_memo),
            "evaluation_memo": serialize_memo(job.evaluation_memo),
            "negotiated_terms": json.dumps(job.negotiated_terms),
            "agreed_fee_virtual": job.agreed_fee_virtual,
            "agreed_deadline": job.agreed_deadline.isoformat() if job.agreed_deadline else None,
            "escrow_tx_hash": job.escrow_tx_hash,
            "escrow_amount_virtual": job.escrow_amount_virtual,
            "escrow_released": job.escrow_released,
            "deliverable_content": json.dumps(job.deliverable_content) if job.deliverable_content else None,
            "deliverable_url": job.deliverable_url,
            "delivered_at": job.delivered_at.isoformat() if job.delivered_at else None,
            "evaluation_result": job.evaluation_result,
            "evaluation_score": job.evaluation_score,
            "evaluation_feedback": job.evaluation_feedback,
            "evaluated_at": job.evaluated_at.isoformat() if job.evaluated_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "settlement_tx_hash": job.settlement_tx_hash,
            "is_disputed": job.is_disputed,
            "dispute_reason": job.dispute_reason,
            "dispute_resolution": job.dispute_resolution,
            "request_timeout": job.request_timeout.isoformat(),
            "negotiation_timeout": job.negotiation_timeout.isoformat(),
            "execution_timeout": job.execution_timeout.isoformat() if job.execution_timeout else None,
            "evaluation_timeout": job.evaluation_timeout.isoformat() if job.evaluation_timeout else None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        await self.client.execute_write(query, params)

        self.logger.info(
            "acp_job_created",
            job_id=job.id,
            offering_id=job.job_offering_id,
            buyer=job.buyer_agent_id,
            provider=job.provider_agent_id,
        )

        return job

    async def get_by_id(self, job_id: str) -> ACPJob | None:
        """Get a job by ID."""
        query = """
        MATCH (j:ACPJob {id: $id})
        RETURN j
        """

        result = await self.client.execute_single(query, {"id": job_id})

        if not result:
            return None

        return self._to_model(result.get("j", result))

    async def update(self, job: ACPJob) -> ACPJob:
        """Update a job."""
        now = datetime.now(UTC)

        def serialize_memo(memo: object) -> str | None:
            if memo is None:
                return None
            if hasattr(memo, "model_dump"):
                return json.dumps(memo.model_dump(), default=str)
            return None

        query = """
        MATCH (j:ACPJob {id: $id})
        SET j.current_phase = $current_phase,
            j.status = $status,
            j.requirements = $requirements,
            j.request_memo = $request_memo,
            j.requirement_memo = $requirement_memo,
            j.agreement_memo = $agreement_memo,
            j.transaction_memo = $transaction_memo,
            j.deliverable_memo = $deliverable_memo,
            j.evaluation_memo = $evaluation_memo,
            j.negotiated_terms = $negotiated_terms,
            j.agreed_fee_virtual = $agreed_fee_virtual,
            j.agreed_deadline = $agreed_deadline,
            j.escrow_tx_hash = $escrow_tx_hash,
            j.escrow_amount_virtual = $escrow_amount_virtual,
            j.escrow_released = $escrow_released,
            j.deliverable_content = $deliverable_content,
            j.deliverable_url = $deliverable_url,
            j.delivered_at = $delivered_at,
            j.evaluation_result = $evaluation_result,
            j.evaluation_score = $evaluation_score,
            j.evaluation_feedback = $evaluation_feedback,
            j.evaluated_at = $evaluated_at,
            j.completed_at = $completed_at,
            j.settlement_tx_hash = $settlement_tx_hash,
            j.is_disputed = $is_disputed,
            j.dispute_reason = $dispute_reason,
            j.dispute_resolution = $dispute_resolution,
            j.execution_timeout = $execution_timeout,
            j.evaluation_timeout = $evaluation_timeout,
            j.updated_at = $updated_at
        RETURN j
        """

        params = {
            "id": job.id,
            "current_phase": job.current_phase.value,
            "status": job.status.value,
            "requirements": job.requirements,
            "request_memo": serialize_memo(job.request_memo),
            "requirement_memo": serialize_memo(job.requirement_memo),
            "agreement_memo": serialize_memo(job.agreement_memo),
            "transaction_memo": serialize_memo(job.transaction_memo),
            "deliverable_memo": serialize_memo(job.deliverable_memo),
            "evaluation_memo": serialize_memo(job.evaluation_memo),
            "negotiated_terms": json.dumps(job.negotiated_terms),
            "agreed_fee_virtual": job.agreed_fee_virtual,
            "agreed_deadline": job.agreed_deadline.isoformat() if job.agreed_deadline else None,
            "escrow_tx_hash": job.escrow_tx_hash,
            "escrow_amount_virtual": job.escrow_amount_virtual,
            "escrow_released": job.escrow_released,
            "deliverable_content": json.dumps(job.deliverable_content) if job.deliverable_content else None,
            "deliverable_url": job.deliverable_url,
            "delivered_at": job.delivered_at.isoformat() if job.delivered_at else None,
            "evaluation_result": job.evaluation_result,
            "evaluation_score": job.evaluation_score,
            "evaluation_feedback": job.evaluation_feedback,
            "evaluated_at": job.evaluated_at.isoformat() if job.evaluated_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "settlement_tx_hash": job.settlement_tx_hash,
            "is_disputed": job.is_disputed,
            "dispute_reason": job.dispute_reason,
            "dispute_resolution": job.dispute_resolution,
            "execution_timeout": job.execution_timeout.isoformat() if job.execution_timeout else None,
            "evaluation_timeout": job.evaluation_timeout.isoformat() if job.evaluation_timeout else None,
            "updated_at": now.isoformat(),
        }

        await self.client.execute_write(query, params)
        job.updated_at = now

        return job

    async def list_by_buyer(
        self,
        buyer_agent_id: str,
        status: ACPJobStatus | None = None,
        limit: int = 50,
    ) -> list[ACPJob]:
        """Get jobs where agent is the buyer."""
        conditions = ["j.buyer_agent_id = $buyer_agent_id"]
        params: dict[str, Any] = {"buyer_agent_id": buyer_agent_id, "limit": limit}

        if status:
            conditions.append("j.status = $status")
            params["status"] = status.value

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (j:ACPJob)
        WHERE {where_clause}
        RETURN j
        ORDER BY j.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_read(query, params)

        return [self._to_model(r.get("j", r)) for r in results if r]

    async def list_by_provider(
        self,
        provider_agent_id: str,
        status: ACPJobStatus | None = None,
        limit: int = 50,
    ) -> list[ACPJob]:
        """Get jobs where agent is the provider."""
        conditions = ["j.provider_agent_id = $provider_agent_id"]
        params: dict[str, Any] = {"provider_agent_id": provider_agent_id, "limit": limit}

        if status:
            conditions.append("j.status = $status")
            params["status"] = status.value

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (j:ACPJob)
        WHERE {where_clause}
        RETURN j
        ORDER BY j.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute_read(query, params)

        return [self._to_model(r.get("j", r)) for r in results if r]

    async def count_by_provider(self, provider_agent_id: str) -> int:
        """Count completed jobs for a provider."""
        query = """
        MATCH (j:ACPJob {provider_agent_id: $provider_agent_id, status: 'completed'})
        RETURN count(j) AS count
        """

        result = await self.client.execute_single(
            query, {"provider_agent_id": provider_agent_id}
        )

        return result.get("count", 0) if result else 0

    async def sum_revenue_by_provider(self, provider_agent_id: str) -> float:
        """Sum total revenue earned by a provider."""
        query = """
        MATCH (j:ACPJob {provider_agent_id: $provider_agent_id, status: 'completed'})
        WHERE j.escrow_released = true
        RETURN sum(j.agreed_fee_virtual) AS total
        """

        result = await self.client.execute_single(
            query, {"provider_agent_id": provider_agent_id}
        )

        return result.get("total", 0.0) if result else 0.0

    async def average_rating_by_provider(
        self, provider_agent_id: str
    ) -> float | None:
        """Get average evaluation score for a provider."""
        query = """
        MATCH (j:ACPJob {provider_agent_id: $provider_agent_id, status: 'completed'})
        WHERE j.evaluation_score IS NOT NULL
        RETURN avg(j.evaluation_score) AS avg_score
        """

        result = await self.client.execute_single(
            query, {"provider_agent_id": provider_agent_id}
        )

        if result and result.get("avg_score") is not None:
            return float(result["avg_score"])
        return None

    async def get_pending_jobs(self, agent_id: str) -> list[ACPJob]:
        """Get jobs pending action by an agent (as buyer or provider)."""
        query = """
        MATCH (j:ACPJob)
        WHERE (j.buyer_agent_id = $agent_id OR j.provider_agent_id = $agent_id)
        AND j.status IN ['open', 'negotiating', 'in_progress', 'delivered', 'evaluating']
        RETURN j
        ORDER BY j.updated_at DESC
        """

        results = await self.client.execute_read(query, {"agent_id": agent_id})

        return [self._to_model(r.get("j", r)) for r in results if r]

    async def get_timed_out_jobs(self) -> list[ACPJob]:
        """Get jobs that have timed out in their current phase."""
        now = datetime.now(UTC).isoformat()

        query = """
        MATCH (j:ACPJob)
        WHERE j.status NOT IN ['completed', 'cancelled', 'disputed']
        AND (
            (j.current_phase = 'request' AND j.request_timeout < $now) OR
            (j.current_phase = 'negotiation' AND j.negotiation_timeout < $now) OR
            (j.current_phase = 'transaction' AND j.execution_timeout IS NOT NULL AND j.execution_timeout < $now) OR
            (j.current_phase = 'evaluation' AND j.evaluation_timeout IS NOT NULL AND j.evaluation_timeout < $now)
        )
        RETURN j
        """

        results = await self.client.execute_read(query, {"now": now})

        return [self._to_model(r.get("j", r)) for r in results if r]

    def _to_model(self, record: dict[str, Any]) -> ACPJob:
        """Convert Neo4j record to ACPJob model."""
        from forge.virtuals.models.acp import ACPMemo

        # Parse JSON fields
        for field in ["negotiated_terms", "deliverable_content"]:
            if isinstance(record.get(field), str):
                try:
                    record[field] = json.loads(record[field])
                except json.JSONDecodeError:
                    record[field] = {}

        # Parse memo fields
        for field in [
            "request_memo", "requirement_memo", "agreement_memo",
            "transaction_memo", "deliverable_memo", "evaluation_memo"
        ]:
            if isinstance(record.get(field), str):
                try:
                    memo_data = json.loads(record[field])
                    record[field] = ACPMemo(**memo_data)
                except (json.JSONDecodeError, Exception):
                    record[field] = None

        # Parse datetime fields
        datetime_fields = [
            "agreed_deadline", "delivered_at", "evaluated_at", "completed_at",
            "request_timeout", "negotiation_timeout", "execution_timeout",
            "evaluation_timeout", "created_at", "updated_at"
        ]
        for field in datetime_fields:
            if isinstance(record.get(field), str):
                try:
                    record[field] = datetime.fromisoformat(record[field])
                except ValueError:
                    record[field] = None

        # Parse enums
        if isinstance(record.get("current_phase"), str):
            record["current_phase"] = ACPPhase(record["current_phase"])
        if isinstance(record.get("status"), str):
            record["status"] = ACPJobStatus(record["status"])

        return ACPJob(**record)


# Global repository instances
_offering_repository: OfferingRepository | None = None
_job_repository: ACPJobRepository | None = None


def get_offering_repository(client: Neo4jClient) -> OfferingRepository:
    """Get or create the offering repository instance."""
    global _offering_repository
    if _offering_repository is None:
        _offering_repository = OfferingRepository(client)
    return _offering_repository


def get_job_repository(client: Neo4jClient) -> ACPJobRepository:
    """Get or create the job repository instance."""
    global _job_repository
    if _job_repository is None:
        _job_repository = ACPJobRepository(client)
    return _job_repository
