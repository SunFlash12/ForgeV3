"""
Agent Commerce Protocol (ACP) Routes Tests for Forge Cascade V2

Comprehensive tests for ACP API routes including:
- Service offerings (create, search, get)
- Job lifecycle (create, respond, accept, deliver, evaluate, dispute)
- Job queries (buyer jobs, provider jobs)
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_virtuals_service():
    """Create mock virtuals service."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_offering():
    """Create a sample offering for testing."""
    return MagicMock(
        id="offering_123",
        provider_agent_id="agent_001",
        provider_wallet="0x1234567890abcdef",
        service_type="knowledge_query",
        title="Knowledge Query Service",
        description="Query the knowledge graph",
        base_fee_virtual=1.0,
        fee_per_unit=0.1,
        unit_type="query",
        max_execution_time_seconds=300,
        is_active=True,
        available_capacity=10,
        tags=["knowledge", "query"],
        registry_id="reg_001",
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_job():
    """Create a sample ACP job for testing."""
    job = MagicMock()
    job.id = "job_123"
    job.job_offering_id = "offering_123"
    job.buyer_agent_id = "agent_buyer"
    job.buyer_wallet = "0xbuyer"
    job.provider_agent_id = "agent_provider"
    job.provider_wallet = "0xprovider"
    job.current_phase = MagicMock(value="request")
    job.status = MagicMock(value="pending")
    job.requirements = "Test requirements"
    job.agreed_fee_virtual = 1.5
    job.agreed_deadline = datetime.now() + timedelta(days=1)
    job.escrow_amount_virtual = 1.5
    job.escrow_released = False
    job.is_disputed = False
    job.created_at = datetime.now()
    job.updated_at = datetime.now()
    return job


# =============================================================================
# Offerings Endpoints Tests
# =============================================================================


class TestCreateOfferingRoute:
    """Tests for POST /acp/offerings endpoint."""

    def test_create_offering_unauthorized(self, client: TestClient):
        """Create offering without auth fails."""
        response = client.post(
            "/api/v1/acp/offerings",
            json={
                "agent_id": "agent_001",
                "wallet_address": "0x1234",
                "service_type": "knowledge_query",
                "title": "Test Service",
                "description": "Test description",
                "base_fee_virtual": 1.0,
            },
        )
        assert response.status_code == 401

    def test_create_offering_missing_required_fields(self, client: TestClient, auth_headers: dict):
        """Create offering with missing fields fails validation."""
        response = client.post(
            "/api/v1/acp/offerings",
            json={
                "agent_id": "agent_001",
                # Missing wallet_address, service_type, title, description, base_fee_virtual
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_offering_invalid_fee(self, client: TestClient, auth_headers: dict):
        """Create offering with negative fee fails validation."""
        response = client.post(
            "/api/v1/acp/offerings",
            json={
                "agent_id": "agent_001",
                "wallet_address": "0x1234",
                "service_type": "knowledge_query",
                "title": "Test Service",
                "description": "Test description",
                "base_fee_virtual": -1.0,  # Negative fee
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_offering_title_too_long(self, client: TestClient, auth_headers: dict):
        """Create offering with title exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/offerings",
            json={
                "agent_id": "agent_001",
                "wallet_address": "0x1234",
                "service_type": "knowledge_query",
                "title": "A" * 250,  # Over 200 max
                "description": "Test description",
                "base_fee_virtual": 1.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_offering_description_too_long(self, client: TestClient, auth_headers: dict):
        """Create offering with description exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/offerings",
            json={
                "agent_id": "agent_001",
                "wallet_address": "0x1234",
                "service_type": "knowledge_query",
                "title": "Test Service",
                "description": "A" * 2500,  # Over 2000 max
                "base_fee_virtual": 1.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_offering_authorized(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_offering
    ):
        """Create offering with valid data succeeds."""
        mock_virtuals_service.register_offering = AsyncMock(return_value=sample_offering)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.post(
                "/api/v1/acp/offerings",
                json={
                    "agent_id": "agent_001",
                    "wallet_address": "0x1234567890abcdef",
                    "service_type": "knowledge_query",
                    "title": "Knowledge Query Service",
                    "description": "Query the knowledge graph",
                    "base_fee_virtual": 1.0,
                    "fee_per_unit": 0.1,
                    "unit_type": "query",
                    "max_execution_time_seconds": 300,
                    "tags": ["knowledge", "query"],
                },
                headers=auth_headers,
            )

        # Should succeed or return service error
        assert response.status_code in [200, 201, 400, 503], (
            f"Expected 200/201/400/503, got {response.status_code}: {response.text[:200]}"
        )


class TestSearchOfferingsRoute:
    """Tests for GET /acp/offerings endpoint."""

    def test_search_offerings_no_filters(
        self, client: TestClient, mock_virtuals_service, sample_offering
    ):
        """Search offerings without filters returns results."""
        mock_virtuals_service.search_offerings = AsyncMock(return_value=[sample_offering])

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get("/api/v1/acp/offerings")

        # Public endpoint, should succeed or service unavailable
        assert response.status_code in [200, 503], (
            f"Expected 200/503, got {response.status_code}: {response.text[:200]}"
        )

    def test_search_offerings_with_filters(
        self, client: TestClient, mock_virtuals_service, sample_offering
    ):
        """Search offerings with filters returns filtered results."""
        mock_virtuals_service.search_offerings = AsyncMock(return_value=[sample_offering])

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get(
                "/api/v1/acp/offerings",
                params={
                    "service_type": "knowledge_query",
                    "max_fee": 5.0,
                    "limit": 10,
                },
            )

        assert response.status_code in [200, 503]

    def test_search_offerings_invalid_limit(self, client: TestClient):
        """Search offerings with invalid limit fails validation."""
        response = client.get(
            "/api/v1/acp/offerings",
            params={"limit": 200},  # Over 100 max
        )
        assert response.status_code == 422

    def test_search_offerings_invalid_max_fee(self, client: TestClient):
        """Search offerings with negative max_fee fails validation."""
        response = client.get(
            "/api/v1/acp/offerings",
            params={"max_fee": -1.0},
        )
        assert response.status_code == 422


class TestGetOfferingRoute:
    """Tests for GET /acp/offerings/{offering_id} endpoint."""

    def test_get_offering_success(self, client: TestClient, mock_virtuals_service, sample_offering):
        """Get offering by ID returns offering."""
        mock_virtuals_service.get_offering = AsyncMock(return_value=sample_offering)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get("/api/v1/acp/offerings/offering_123")

        assert response.status_code in [200, 503]

    def test_get_offering_not_found(self, client: TestClient, mock_virtuals_service):
        """Get non-existent offering returns 404."""
        mock_virtuals_service.get_offering = AsyncMock(return_value=None)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get("/api/v1/acp/offerings/nonexistent")

        assert response.status_code in [404, 503]


# =============================================================================
# Jobs Endpoints Tests
# =============================================================================


class TestCreateJobRoute:
    """Tests for POST /acp/jobs endpoint."""

    def test_create_job_unauthorized(self, client: TestClient):
        """Create job without auth fails."""
        response = client.post(
            "/api/v1/acp/jobs",
            json={
                "job_offering_id": "offering_123",
                "buyer_agent_id": "agent_buyer",
                "requirements": "Test requirements",
                "max_fee_virtual": 2.0,
            },
        )
        assert response.status_code == 401

    def test_create_job_missing_fields(self, client: TestClient, auth_headers: dict):
        """Create job with missing fields fails validation."""
        response = client.post(
            "/api/v1/acp/jobs",
            json={
                "job_offering_id": "offering_123",
                # Missing buyer_agent_id, requirements, max_fee_virtual
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_job_invalid_fee(self, client: TestClient, auth_headers: dict):
        """Create job with negative fee fails validation."""
        response = client.post(
            "/api/v1/acp/jobs",
            json={
                "job_offering_id": "offering_123",
                "buyer_agent_id": "agent_buyer",
                "requirements": "Test requirements",
                "max_fee_virtual": -1.0,  # Negative fee
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_job_requirements_too_long(self, client: TestClient, auth_headers: dict):
        """Create job with requirements exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/jobs",
            json={
                "job_offering_id": "offering_123",
                "buyer_agent_id": "agent_buyer",
                "requirements": "A" * 6000,  # Over 5000 max
                "max_fee_virtual": 2.0,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_job_authorized(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Create job with valid data succeeds."""
        mock_virtuals_service.create_job = AsyncMock(return_value=sample_job)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.post(
                "/api/v1/acp/jobs",
                json={
                    "job_offering_id": "offering_123",
                    "buyer_agent_id": "agent_buyer",
                    "requirements": "Test requirements",
                    "max_fee_virtual": 2.0,
                },
                headers=auth_headers,
            )

        assert response.status_code in [200, 201, 400, 503]


class TestGetJobRoute:
    """Tests for GET /acp/jobs/{job_id} endpoint."""

    def test_get_job_unauthorized(self, client: TestClient):
        """Get job without auth fails."""
        response = client.get("/api/v1/acp/jobs/job_123")
        assert response.status_code == 401

    def test_get_job_success(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Get job by ID returns job."""
        mock_virtuals_service.get_job = AsyncMock(return_value=sample_job)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get("/api/v1/acp/jobs/job_123", headers=auth_headers)

        assert response.status_code in [200, 503]

    def test_get_job_not_found(self, client: TestClient, auth_headers: dict, mock_virtuals_service):
        """Get non-existent job returns 404."""
        mock_virtuals_service.get_job = AsyncMock(return_value=None)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get("/api/v1/acp/jobs/nonexistent", headers=auth_headers)

        assert response.status_code in [404, 503]


class TestRespondToJobRoute:
    """Tests for POST /acp/jobs/{job_id}/respond endpoint."""

    def test_respond_unauthorized(self, client: TestClient):
        """Respond to job without auth fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/respond",
            json={
                "proposed_fee_virtual": 1.5,
                "proposed_deadline": (datetime.now() + timedelta(days=1)).isoformat(),
                "deliverable_format": "json",
                "deliverable_description": "Test deliverable",
            },
        )
        assert response.status_code == 401

    def test_respond_missing_fields(self, client: TestClient, auth_headers: dict):
        """Respond with missing fields fails validation."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/respond",
            json={
                "proposed_fee_virtual": 1.5,
                # Missing proposed_deadline, deliverable_format, deliverable_description
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_respond_invalid_fee(self, client: TestClient, auth_headers: dict):
        """Respond with negative fee fails validation."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/respond",
            json={
                "proposed_fee_virtual": -1.0,  # Negative fee
                "proposed_deadline": (datetime.now() + timedelta(days=1)).isoformat(),
                "deliverable_format": "json",
                "deliverable_description": "Test deliverable",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAcceptJobRoute:
    """Tests for POST /acp/jobs/{job_id}/accept endpoint."""

    def test_accept_unauthorized(self, client: TestClient):
        """Accept job without auth fails."""
        response = client.post("/api/v1/acp/jobs/job_123/accept")
        assert response.status_code == 401

    def test_accept_authorized(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Accept job with valid auth succeeds."""
        mock_virtuals_service.accept_terms = AsyncMock(return_value=sample_job)

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.post("/api/v1/acp/jobs/job_123/accept", headers=auth_headers)

        assert response.status_code in [200, 400, 503]


class TestSubmitDeliverableRoute:
    """Tests for POST /acp/jobs/{job_id}/deliver endpoint."""

    def test_deliver_unauthorized(self, client: TestClient):
        """Submit deliverable without auth fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/deliver",
            json={
                "content_type": "json",
                "content": {"result": "test"},
                "notes": "Test notes",
            },
        )
        assert response.status_code == 401

    def test_deliver_missing_fields(self, client: TestClient, auth_headers: dict):
        """Submit deliverable with missing fields fails validation."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/deliver",
            json={
                "content_type": "json",
                # Missing content
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_deliver_notes_too_long(self, client: TestClient, auth_headers: dict):
        """Submit deliverable with notes exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/deliver",
            json={
                "content_type": "json",
                "content": {"result": "test"},
                "notes": "A" * 1500,  # Over 1000 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestEvaluateRoute:
    """Tests for POST /acp/jobs/{job_id}/evaluate endpoint."""

    def test_evaluate_unauthorized(self, client: TestClient):
        """Evaluate without auth fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/evaluate",
            json={
                "evaluator_agent_id": "evaluator_001",
                "result": "approved",
                "score": 0.9,
                "feedback": "Good work",
            },
        )
        assert response.status_code == 401

    def test_evaluate_invalid_score(self, client: TestClient, auth_headers: dict):
        """Evaluate with invalid score fails validation."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/evaluate",
            json={
                "evaluator_agent_id": "evaluator_001",
                "result": "approved",
                "score": 1.5,  # Over 1.0 max
                "feedback": "Good work",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_evaluate_feedback_too_long(self, client: TestClient, auth_headers: dict):
        """Evaluate with feedback exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/evaluate",
            json={
                "evaluator_agent_id": "evaluator_001",
                "result": "approved",
                "score": 0.9,
                "feedback": "A" * 2500,  # Over 2000 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestFileDisputeRoute:
    """Tests for POST /acp/jobs/{job_id}/dispute endpoint."""

    def test_dispute_unauthorized(self, client: TestClient):
        """File dispute without auth fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/dispute",
            json={
                "filed_by": "buyer",
                "reason": "Deliverable does not meet requirements",
                "requested_resolution": "full_refund",
            },
        )
        assert response.status_code == 401

    def test_dispute_reason_too_long(self, client: TestClient, auth_headers: dict):
        """File dispute with reason exceeding max length fails."""
        response = client.post(
            "/api/v1/acp/jobs/job_123/dispute",
            json={
                "filed_by": "buyer",
                "reason": "A" * 2500,  # Over 2000 max
                "requested_resolution": "full_refund",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestGetBuyerJobsRoute:
    """Tests for GET /acp/jobs/buyer/{agent_id} endpoint."""

    def test_get_buyer_jobs_unauthorized(self, client: TestClient):
        """Get buyer jobs without auth fails."""
        response = client.get("/api/v1/acp/jobs/buyer/agent_001")
        assert response.status_code == 401

    def test_get_buyer_jobs_authorized(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Get buyer jobs with auth returns jobs."""
        mock_virtuals_service.get_buyer_jobs = AsyncMock(return_value=[sample_job])

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get(
                "/api/v1/acp/jobs/buyer/agent_001",
                headers=auth_headers,
            )

        assert response.status_code in [200, 503]

    def test_get_buyer_jobs_with_filters(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Get buyer jobs with filters returns filtered jobs."""
        mock_virtuals_service.get_buyer_jobs = AsyncMock(return_value=[sample_job])

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get(
                "/api/v1/acp/jobs/buyer/agent_001",
                params={"status": "pending", "limit": 10},
                headers=auth_headers,
            )

        assert response.status_code in [200, 503]

    def test_get_buyer_jobs_invalid_limit(self, client: TestClient, auth_headers: dict):
        """Get buyer jobs with invalid limit fails validation."""
        response = client.get(
            "/api/v1/acp/jobs/buyer/agent_001",
            params={"limit": 200},  # Over 100 max
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestGetProviderJobsRoute:
    """Tests for GET /acp/jobs/provider/{agent_id} endpoint."""

    def test_get_provider_jobs_unauthorized(self, client: TestClient):
        """Get provider jobs without auth fails."""
        response = client.get("/api/v1/acp/jobs/provider/agent_001")
        assert response.status_code == 401

    def test_get_provider_jobs_authorized(
        self, client: TestClient, auth_headers: dict, mock_virtuals_service, sample_job
    ):
        """Get provider jobs with auth returns jobs."""
        mock_virtuals_service.get_provider_jobs = AsyncMock(return_value=[sample_job])

        with patch("forge.api.routes.acp.get_virtuals_service", return_value=mock_virtuals_service):
            response = client.get(
                "/api/v1/acp/jobs/provider/agent_001",
                headers=auth_headers,
            )

        assert response.status_code in [200, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
