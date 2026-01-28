"""
ACP Repository Tests for Forge Cascade V2

Comprehensive tests for the ACP (Agent Commerce Protocol) repositories:
- OfferingRepository: Job offering CRUD and search
- ACPJobRepository: Job lifecycle management

Tests cover:
- CRUD operations
- Search and filtering
- Status transitions
- Aggregation queries
- Error handling
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.database.client import Neo4jClient
from forge.repositories.acp_repository import (
    ACPJobRepository,
    OfferingRepository,
    get_job_repository,
    get_offering_repository,
)
from forge.virtuals.models.acp import (
    ACPJob,
    ACPMemo,
    JobOffering,
)
from forge.virtuals.models.base import ACPJobStatus, ACPPhase


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock(spec=Neo4jClient)
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    client.execute_write = AsyncMock(return_value=None)
    return client


@pytest.fixture
def offering_repository(mock_db_client):
    """Create OfferingRepository with mock client."""
    return OfferingRepository(mock_db_client)


@pytest.fixture
def job_repository(mock_db_client):
    """Create ACPJobRepository with mock client."""
    return ACPJobRepository(mock_db_client)


@pytest.fixture
def sample_offering_data():
    """Sample offering data for testing."""
    return {
        "id": "offering-123",
        "provider_agent_id": "agent-001",
        "provider_wallet": "0x1234567890123456789012345678901234567890",
        "service_type": "knowledge_query",
        "title": "Knowledge Query Service",
        "description": "Provides knowledge queries from the capsule database",
        "input_schema": json.dumps({"query": "string"}),
        "output_schema": json.dumps({"result": "string"}),
        "supported_formats": ["json", "text"],
        "base_fee_virtual": 10.0,
        "fee_per_unit": 0.1,
        "unit_type": "tokens",
        "max_execution_time_seconds": 300,
        "requires_escrow": True,
        "min_buyer_trust_score": 0.5,
        "is_active": True,
        "available_capacity": 100,
        "tags": ["knowledge", "query"],
        "registry_id": "reg-001",
        "registration_tx_hash": "0xabc123",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "job-123",
        "job_offering_id": "offering-123",
        "buyer_agent_id": "agent-buyer-001",
        "buyer_wallet": "0xbuyer12345678901234567890123456789012",
        "provider_agent_id": "agent-provider-001",
        "provider_wallet": "0xprovider1234567890123456789012345678",
        "evaluator_agent_id": None,
        "current_phase": "request",
        "status": "open",
        "requirements": "Query for capsule insights",
        "request_memo": None,
        "requirement_memo": None,
        "agreement_memo": None,
        "transaction_memo": None,
        "deliverable_memo": None,
        "evaluation_memo": None,
        "negotiated_terms": json.dumps({}),
        "agreed_fee_virtual": 0.0,
        "agreed_deadline": None,
        "escrow_tx_hash": None,
        "escrow_amount_virtual": 0.0,
        "escrow_released": False,
        "deliverable_content": None,
        "deliverable_url": None,
        "delivered_at": None,
        "evaluation_result": None,
        "evaluation_score": None,
        "evaluation_feedback": None,
        "evaluated_at": None,
        "completed_at": None,
        "settlement_tx_hash": None,
        "is_disputed": False,
        "dispute_reason": None,
        "dispute_resolution": None,
        "request_timeout": (now + timedelta(hours=24)).isoformat(),
        "negotiation_timeout": (now + timedelta(hours=48)).isoformat(),
        "execution_timeout": None,
        "evaluation_timeout": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@pytest.fixture
def sample_offering():
    """Create a sample JobOffering instance."""
    return JobOffering(
        id="offering-123",
        provider_agent_id="agent-001",
        provider_wallet="0x1234567890123456789012345678901234567890",
        service_type="knowledge_query",
        title="Knowledge Query Service",
        description="Provides knowledge queries",
        input_schema={"query": "string"},
        output_schema={"result": "string"},
        base_fee_virtual=10.0,
    )


@pytest.fixture
def sample_job():
    """Create a sample ACPJob instance."""
    now = datetime.now(UTC)
    return ACPJob(
        id="job-123",
        job_offering_id="offering-123",
        buyer_agent_id="agent-buyer-001",
        buyer_wallet="0xbuyer12345678901234567890123456789012",
        provider_agent_id="agent-provider-001",
        provider_wallet="0xprovider1234567890123456789012345678",
        current_phase=ACPPhase.REQUEST,
        status=ACPJobStatus.OPEN,
        requirements="Query for capsule insights",
        request_timeout=now + timedelta(hours=24),
        negotiation_timeout=now + timedelta(hours=48),
    )


# =============================================================================
# OfferingRepository Tests - Create
# =============================================================================


class TestOfferingRepositoryCreate:
    """Tests for OfferingRepository create operations."""

    @pytest.mark.asyncio
    async def test_create_offering_success(
        self, offering_repository, mock_db_client, sample_offering
    ):
        """Create offering successfully."""
        mock_db_client.execute_write.return_value = None

        result = await offering_repository.create(sample_offering)

        assert result.id == "offering-123"
        assert result.service_type == "knowledge_query"
        mock_db_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_offering_serializes_schemas(
        self, offering_repository, mock_db_client, sample_offering
    ):
        """Create offering serializes input/output schemas to JSON."""
        mock_db_client.execute_write.return_value = None

        await offering_repository.create(sample_offering)

        call_args = mock_db_client.execute_write.call_args
        params = call_args[0][1]
        assert isinstance(params["input_schema"], str)
        assert isinstance(params["output_schema"], str)
        assert json.loads(params["input_schema"]) == {"query": "string"}

    @pytest.mark.asyncio
    async def test_create_offering_sets_timestamps(
        self, offering_repository, mock_db_client, sample_offering
    ):
        """Create offering sets created_at and updated_at."""
        mock_db_client.execute_write.return_value = None

        await offering_repository.create(sample_offering)

        call_args = mock_db_client.execute_write.call_args
        params = call_args[0][1]
        assert "created_at" in params
        assert "updated_at" in params


# =============================================================================
# OfferingRepository Tests - Read
# =============================================================================


class TestOfferingRepositoryRead:
    """Tests for OfferingRepository read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Get offering by ID when found."""
        mock_db_client.execute_single.return_value = {"o": sample_offering_data}

        result = await offering_repository.get_by_id("offering-123")

        assert result is not None
        assert result.id == "offering-123"
        assert result.service_type == "knowledge_query"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, offering_repository, mock_db_client):
        """Get offering by ID returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await offering_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_parses_json_schemas(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Get offering parses JSON schemas."""
        mock_db_client.execute_single.return_value = {"o": sample_offering_data}

        result = await offering_repository.get_by_id("offering-123")

        assert result is not None
        assert isinstance(result.input_schema, dict)
        assert result.input_schema == {"query": "string"}

    @pytest.mark.asyncio
    async def test_get_by_agent(self, offering_repository, mock_db_client, sample_offering_data):
        """Get offerings by agent ID."""
        mock_db_client.execute.return_value = [
            {"o": sample_offering_data},
            {"o": {**sample_offering_data, "id": "offering-456"}},
        ]

        result = await offering_repository.get_by_agent("agent-001")

        assert len(result) == 2
        assert result[0].provider_agent_id == "agent-001"

    @pytest.mark.asyncio
    async def test_get_by_agent_respects_limit(self, offering_repository, mock_db_client):
        """Get by agent respects limit parameter."""
        mock_db_client.execute.return_value = []

        await offering_repository.get_by_agent("agent-001", limit=50)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_get_by_agent_caps_limit(self, offering_repository, mock_db_client):
        """Get by agent caps limit at 200."""
        mock_db_client.execute.return_value = []

        await offering_repository.get_by_agent("agent-001", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 200


# =============================================================================
# OfferingRepository Tests - Search
# =============================================================================


class TestOfferingRepositorySearch:
    """Tests for OfferingRepository search operations."""

    @pytest.mark.asyncio
    async def test_search_basic(self, offering_repository, mock_db_client, sample_offering_data):
        """Basic search returns active offerings."""
        mock_db_client.execute.return_value = [{"o": sample_offering_data}]

        result = await offering_repository.search()

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "o.is_active = true" in query

    @pytest.mark.asyncio
    async def test_search_by_service_type(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Search by service type."""
        mock_db_client.execute.return_value = [{"o": sample_offering_data}]

        await offering_repository.search(service_type="knowledge_query")

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["service_type"] == "knowledge_query"

    @pytest.mark.asyncio
    async def test_search_by_query_text(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Search by text query."""
        mock_db_client.execute.return_value = [{"o": sample_offering_data}]

        await offering_repository.search(query="knowledge")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "toLower(o.title) CONTAINS toLower($query)" in query
        assert params["query"] == "knowledge"

    @pytest.mark.asyncio
    async def test_search_by_max_fee(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Search by maximum fee."""
        mock_db_client.execute.return_value = [{"o": sample_offering_data}]

        await offering_repository.search(max_fee=20.0)

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "o.base_fee_virtual <= $max_fee" in query
        assert params["max_fee"] == 20.0

    @pytest.mark.asyncio
    async def test_search_caps_limit(self, offering_repository, mock_db_client):
        """Search caps limit at 100."""
        mock_db_client.execute.return_value = []

        await offering_repository.search(limit=500)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_search_combined_filters(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """Search with combined filters."""
        mock_db_client.execute.return_value = [{"o": sample_offering_data}]

        await offering_repository.search(
            service_type="knowledge_query",
            query="capsule",
            max_fee=50.0,
            limit=10,
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["service_type"] == "knowledge_query"
        assert params["query"] == "capsule"
        assert params["max_fee"] == 50.0
        assert params["limit"] == 10


# =============================================================================
# OfferingRepository Tests - Update and Delete
# =============================================================================


class TestOfferingRepositoryUpdateDelete:
    """Tests for OfferingRepository update and delete operations."""

    @pytest.mark.asyncio
    async def test_update_offering(
        self, offering_repository, mock_db_client, sample_offering
    ):
        """Update offering successfully."""
        mock_db_client.execute_write.return_value = None

        sample_offering.title = "Updated Title"
        result = await offering_repository.update(sample_offering)

        assert result.title == "Updated Title"
        mock_db_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_offering_sets_updated_at(
        self, offering_repository, mock_db_client, sample_offering
    ):
        """Update offering sets updated_at timestamp."""
        mock_db_client.execute_write.return_value = None
        original_updated_at = sample_offering.updated_at

        result = await offering_repository.update(sample_offering)

        assert result.updated_at >= original_updated_at

    @pytest.mark.asyncio
    async def test_delete_offering_success(self, offering_repository, mock_db_client):
        """Delete (soft delete) offering successfully."""
        mock_db_client.execute_single.return_value = {"id": "offering-123"}

        result = await offering_repository.delete("offering-123")

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "o.is_active = false" in query

    @pytest.mark.asyncio
    async def test_delete_offering_not_found(self, offering_repository, mock_db_client):
        """Delete returns False when not found."""
        mock_db_client.execute_single.return_value = None

        result = await offering_repository.delete("nonexistent")

        assert result is False


# =============================================================================
# ACPJobRepository Tests - Create
# =============================================================================


class TestACPJobRepositoryCreate:
    """Tests for ACPJobRepository create operations."""

    @pytest.mark.asyncio
    async def test_create_job_success(self, job_repository, mock_db_client, sample_job):
        """Create job successfully."""
        mock_db_client.execute_write.return_value = None

        result = await job_repository.create(sample_job)

        assert result.id == "job-123"
        assert result.status == ACPJobStatus.OPEN
        mock_db_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_serializes_memos(
        self, job_repository, mock_db_client, sample_job
    ):
        """Create job serializes memo fields."""
        mock_db_client.execute_write.return_value = None

        # Add a memo
        sample_job.request_memo = ACPMemo(
            memo_type="request",
            job_id="job-123",
            content={"query": "test"},
            content_hash="abc123",
            nonce=1,
            sender_address="0xtest",
            sender_signature="sig123",
        )

        await job_repository.create(sample_job)

        call_args = mock_db_client.execute_write.call_args
        params = call_args[0][1]
        assert isinstance(params["request_memo"], str)
        memo_data = json.loads(params["request_memo"])
        assert memo_data["memo_type"] == "request"

    @pytest.mark.asyncio
    async def test_create_job_creates_offering_relationship(
        self, job_repository, mock_db_client, sample_job
    ):
        """Create job creates relationship to offering."""
        mock_db_client.execute_write.return_value = None

        await job_repository.create(sample_job)

        call_args = mock_db_client.execute_write.call_args
        query = call_args[0][0]
        assert "[:FOR_OFFERING]" in query


# =============================================================================
# ACPJobRepository Tests - Read
# =============================================================================


class TestACPJobRepositoryRead:
    """Tests for ACPJobRepository read operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, job_repository, mock_db_client, sample_job_data):
        """Get job by ID when found."""
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert result.id == "job-123"
        assert result.current_phase == ACPPhase.REQUEST

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, job_repository, mock_db_client):
        """Get job by ID returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await job_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_parses_enums(self, job_repository, mock_db_client, sample_job_data):
        """Get job parses phase and status enums."""
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert isinstance(result.current_phase, ACPPhase)
        assert isinstance(result.status, ACPJobStatus)

    @pytest.mark.asyncio
    async def test_list_by_buyer(self, job_repository, mock_db_client, sample_job_data):
        """List jobs by buyer agent ID."""
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        result = await job_repository.list_by_buyer("agent-buyer-001")

        assert len(result) == 1
        assert result[0].buyer_agent_id == "agent-buyer-001"

    @pytest.mark.asyncio
    async def test_list_by_buyer_with_status(self, job_repository, mock_db_client, sample_job_data):
        """List jobs by buyer with status filter."""
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        await job_repository.list_by_buyer("agent-buyer-001", status=ACPJobStatus.OPEN)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["status"] == "open"

    @pytest.mark.asyncio
    async def test_list_by_buyer_caps_limit(self, job_repository, mock_db_client):
        """List by buyer caps limit at 200."""
        mock_db_client.execute.return_value = []

        await job_repository.list_by_buyer("agent-001", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 200

    @pytest.mark.asyncio
    async def test_list_by_provider(self, job_repository, mock_db_client, sample_job_data):
        """List jobs by provider agent ID."""
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        result = await job_repository.list_by_provider("agent-provider-001")

        assert len(result) == 1
        assert result[0].provider_agent_id == "agent-provider-001"

    @pytest.mark.asyncio
    async def test_list_by_provider_with_status(
        self, job_repository, mock_db_client, sample_job_data
    ):
        """List jobs by provider with status filter."""
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        await job_repository.list_by_provider(
            "agent-provider-001", status=ACPJobStatus.IN_PROGRESS
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["status"] == "in_progress"


# =============================================================================
# ACPJobRepository Tests - Update
# =============================================================================


class TestACPJobRepositoryUpdate:
    """Tests for ACPJobRepository update operations."""

    @pytest.mark.asyncio
    async def test_update_job(self, job_repository, mock_db_client, sample_job):
        """Update job successfully."""
        mock_db_client.execute_write.return_value = None

        sample_job.status = ACPJobStatus.NEGOTIATING
        sample_job.current_phase = ACPPhase.NEGOTIATION
        result = await job_repository.update(sample_job)

        assert result.status == ACPJobStatus.NEGOTIATING
        mock_db_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_job_sets_updated_at(
        self, job_repository, mock_db_client, sample_job
    ):
        """Update job sets updated_at timestamp."""
        mock_db_client.execute_write.return_value = None
        original_updated_at = sample_job.updated_at

        result = await job_repository.update(sample_job)

        assert result.updated_at >= original_updated_at


# =============================================================================
# ACPJobRepository Tests - Aggregations
# =============================================================================


class TestACPJobRepositoryAggregations:
    """Tests for ACPJobRepository aggregation queries."""

    @pytest.mark.asyncio
    async def test_count_by_provider(self, job_repository, mock_db_client):
        """Count completed jobs for a provider."""
        mock_db_client.execute_single.return_value = {"count": 42}

        result = await job_repository.count_by_provider("agent-provider-001")

        assert result == 42
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "status: 'completed'" in query

    @pytest.mark.asyncio
    async def test_count_by_provider_returns_zero(self, job_repository, mock_db_client):
        """Count returns 0 when no results."""
        mock_db_client.execute_single.return_value = None

        result = await job_repository.count_by_provider("agent-001")

        assert result == 0

    @pytest.mark.asyncio
    async def test_sum_revenue_by_provider(self, job_repository, mock_db_client):
        """Sum revenue for a provider."""
        mock_db_client.execute_single.return_value = {"total": 1234.56}

        result = await job_repository.sum_revenue_by_provider("agent-provider-001")

        assert result == 1234.56
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "escrow_released = true" in query

    @pytest.mark.asyncio
    async def test_sum_revenue_returns_zero(self, job_repository, mock_db_client):
        """Sum revenue returns 0 when no results."""
        mock_db_client.execute_single.return_value = None

        result = await job_repository.sum_revenue_by_provider("agent-001")

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_average_rating_by_provider(self, job_repository, mock_db_client):
        """Get average rating for a provider."""
        mock_db_client.execute_single.return_value = {"avg_score": 0.85}

        result = await job_repository.average_rating_by_provider("agent-provider-001")

        assert result == 0.85

    @pytest.mark.asyncio
    async def test_average_rating_returns_none(self, job_repository, mock_db_client):
        """Average rating returns None when no ratings."""
        mock_db_client.execute_single.return_value = {"avg_score": None}

        result = await job_repository.average_rating_by_provider("agent-001")

        assert result is None


# =============================================================================
# ACPJobRepository Tests - Pending and Timed Out Jobs
# =============================================================================


class TestACPJobRepositoryPendingTimedOut:
    """Tests for pending and timed out job queries."""

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, job_repository, mock_db_client, sample_job_data):
        """Get pending jobs for an agent."""
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        result = await job_repository.get_pending_jobs("agent-001")

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "status IN" in query

    @pytest.mark.asyncio
    async def test_get_pending_jobs_caps_limit(self, job_repository, mock_db_client):
        """Get pending jobs caps limit at 200."""
        mock_db_client.execute.return_value = []

        await job_repository.get_pending_jobs("agent-001", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 200

    @pytest.mark.asyncio
    async def test_get_timed_out_jobs(self, job_repository, mock_db_client, sample_job_data):
        """Get timed out jobs."""
        # Set job as timed out in request phase
        sample_job_data["request_timeout"] = (
            datetime.now(UTC) - timedelta(hours=1)
        ).isoformat()
        mock_db_client.execute.return_value = [{"j": sample_job_data}]

        result = await job_repository.get_timed_out_jobs()

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "status NOT IN" in query
        assert "request_timeout" in query

    @pytest.mark.asyncio
    async def test_get_timed_out_jobs_caps_limit(self, job_repository, mock_db_client):
        """Get timed out jobs caps limit at 1000."""
        mock_db_client.execute.return_value = []

        await job_repository.get_timed_out_jobs(limit=5000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 1000


# =============================================================================
# Model Conversion Tests
# =============================================================================


class TestOfferingModelConversion:
    """Tests for OfferingRepository model conversion."""

    @pytest.mark.asyncio
    async def test_to_model_parses_json_strings(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """_to_model parses JSON string fields."""
        mock_db_client.execute_single.return_value = {"o": sample_offering_data}

        result = await offering_repository.get_by_id("offering-123")

        assert result is not None
        assert isinstance(result.input_schema, dict)
        assert isinstance(result.output_schema, dict)

    @pytest.mark.asyncio
    async def test_to_model_parses_datetime_strings(
        self, offering_repository, mock_db_client, sample_offering_data
    ):
        """_to_model parses datetime strings."""
        mock_db_client.execute_single.return_value = {"o": sample_offering_data}

        result = await offering_repository.get_by_id("offering-123")

        assert result is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)


class TestJobModelConversion:
    """Tests for ACPJobRepository model conversion."""

    @pytest.mark.asyncio
    async def test_to_model_parses_negotiated_terms(
        self, job_repository, mock_db_client, sample_job_data
    ):
        """_to_model parses negotiated_terms JSON."""
        sample_job_data["negotiated_terms"] = json.dumps({"price": 100})
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert isinstance(result.negotiated_terms, dict)
        assert result.negotiated_terms.get("price") == 100

    @pytest.mark.asyncio
    async def test_to_model_handles_invalid_json(
        self, job_repository, mock_db_client, sample_job_data
    ):
        """_to_model handles invalid JSON gracefully."""
        sample_job_data["negotiated_terms"] = "invalid json{"
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert result.negotiated_terms == {}

    @pytest.mark.asyncio
    async def test_to_model_parses_memo_fields(
        self, job_repository, mock_db_client, sample_job_data
    ):
        """_to_model parses memo JSON fields."""
        memo_data = {
            "id": "memo-123",
            "memo_type": "request",
            "job_id": "job-123",
            "content": {"query": "test"},
            "content_hash": "abc123",
            "nonce": 1,
            "sender_address": "0xtest",
            "sender_signature": "sig123",
            "created_at": datetime.now(UTC).isoformat(),
        }
        sample_job_data["request_memo"] = json.dumps(memo_data)
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert result.request_memo is not None
        assert result.request_memo.memo_type == "request"

    @pytest.mark.asyncio
    async def test_to_model_parses_datetime_fields(
        self, job_repository, mock_db_client, sample_job_data
    ):
        """_to_model parses all datetime fields."""
        sample_job_data["agreed_deadline"] = datetime.now(UTC).isoformat()
        sample_job_data["delivered_at"] = datetime.now(UTC).isoformat()
        mock_db_client.execute_single.return_value = {"j": sample_job_data}

        result = await job_repository.get_by_id("job-123")

        assert result is not None
        assert isinstance(result.agreed_deadline, datetime)
        assert isinstance(result.delivered_at, datetime)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for repository factory functions."""

    def test_get_offering_repository_creates_instance(self, mock_db_client):
        """get_offering_repository creates repository instance."""
        # Reset global state
        import forge.repositories.acp_repository as acp_module

        acp_module._offering_repository = None

        repo = get_offering_repository(mock_db_client)

        assert isinstance(repo, OfferingRepository)

    def test_get_offering_repository_returns_same_instance(self, mock_db_client):
        """get_offering_repository returns same instance on subsequent calls."""
        import forge.repositories.acp_repository as acp_module

        acp_module._offering_repository = None

        repo1 = get_offering_repository(mock_db_client)
        repo2 = get_offering_repository(mock_db_client)

        assert repo1 is repo2

    def test_get_job_repository_creates_instance(self, mock_db_client):
        """get_job_repository creates repository instance."""
        import forge.repositories.acp_repository as acp_module

        acp_module._job_repository = None

        repo = get_job_repository(mock_db_client)

        assert isinstance(repo, ACPJobRepository)

    def test_get_job_repository_returns_same_instance(self, mock_db_client):
        """get_job_repository returns same instance on subsequent calls."""
        import forge.repositories.acp_repository as acp_module

        acp_module._job_repository = None

        repo1 = get_job_repository(mock_db_client)
        repo2 = get_job_repository(mock_db_client)

        assert repo1 is repo2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
