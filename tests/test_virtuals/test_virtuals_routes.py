"""
Tests for the FastAPI Router for Virtuals Protocol Integration.

This module tests the REST API endpoints for agents, tokenization,
ACP commerce, and revenue features.
"""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from forge.virtuals.api.routes import (
    APIResponse,
    PaginatedResponse,
    acp_router,
    agent_router,
    create_virtuals_router,
    get_current_user_wallet,
    revenue_router,
    tokenization_router,
)


# ==================== Fixtures ====================


@pytest.fixture
def app():
    """Create a FastAPI test application."""
    app = FastAPI()
    app.include_router(create_virtuals_router(), prefix="/api/v1/virtuals")
    return app


@pytest.fixture
def client(app):
    """Create a synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def set_dev_environment():
    """Set development environment for testing."""
    original = os.environ.get("FORGE_ENV")
    os.environ["FORGE_ENV"] = "development"
    yield
    if original is not None:
        os.environ["FORGE_ENV"] = original
    elif "FORGE_ENV" in os.environ:
        del os.environ["FORGE_ENV"]


# ==================== Response Model Tests ====================


class TestResponseModels:
    """Tests for API response models."""

    def test_api_response_defaults(self):
        """Test APIResponse default values."""
        response = APIResponse()

        assert response.success is True
        assert response.data is None
        assert response.error is None
        assert response.timestamp is not None

    def test_api_response_with_data(self):
        """Test APIResponse with data."""
        response = APIResponse(data={"key": "value"})

        assert response.data == {"key": "value"}

    def test_api_response_with_error(self):
        """Test APIResponse with error."""
        response = APIResponse(success=False, error="Something went wrong")

        assert response.success is False
        assert response.error == "Something went wrong"

    def test_paginated_response_defaults(self):
        """Test PaginatedResponse default values."""
        response = PaginatedResponse()

        assert response.total == 0
        assert response.page == 1
        assert response.per_page == 20
        assert response.has_more is False

    def test_paginated_response_with_pagination(self):
        """Test PaginatedResponse with pagination data."""
        response = PaginatedResponse(
            data=[1, 2, 3],
            total=100,
            page=2,
            per_page=3,
            has_more=True,
        )

        assert response.data == [1, 2, 3]
        assert response.total == 100
        assert response.page == 2
        assert response.per_page == 3
        assert response.has_more is True


# ==================== Authentication Tests ====================


class TestAuthentication:
    """Tests for authentication dependency."""

    @pytest.mark.asyncio
    async def test_dev_mode_no_credentials(self):
        """Test that dev mode allows unauthenticated requests."""
        os.environ["FORGE_ENV"] = "development"
        mock_request = MagicMock()
        mock_request.client = MagicMock(host="127.0.0.1")

        with patch("forge.virtuals.api.routes.structlog") as mock_structlog:
            mock_logger = MagicMock()
            mock_structlog.get_logger.return_value = mock_logger

            wallet = await get_current_user_wallet(mock_request, None)

            assert wallet == "0x0000000000000000000000000000000000000000"
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_mode_no_credentials(self):
        """Test that test mode allows unauthenticated requests."""
        os.environ["FORGE_ENV"] = "test"
        mock_request = MagicMock()
        mock_request.client = MagicMock(host="127.0.0.1")

        with patch("forge.virtuals.api.routes.structlog"):
            wallet = await get_current_user_wallet(mock_request, None)

            assert wallet == "0x0000000000000000000000000000000000000000"

    @pytest.mark.asyncio
    async def test_production_requires_credentials(self):
        """Test that production mode requires authentication."""
        os.environ["FORGE_ENV"] = "production"
        mock_request = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_wallet(mock_request, None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_valid_token_extracts_wallet(self):
        """Test that valid token extracts wallet address."""
        os.environ["FORGE_ENV"] = "production"
        mock_request = MagicMock()
        mock_credentials = MagicMock(credentials="valid_token")

        with patch("forge.virtuals.api.routes.decode_token") as mock_decode:
            mock_token_data = MagicMock()
            mock_token_data.wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
            mock_decode.return_value = mock_token_data

            wallet = await get_current_user_wallet(mock_request, mock_credentials)

            assert wallet == "0x1234567890abcdef1234567890abcdef12345678"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Test that invalid token raises 401."""
        os.environ["FORGE_ENV"] = "production"
        mock_request = MagicMock()
        mock_credentials = MagicMock(credentials="invalid_token")

        with patch("forge.virtuals.api.routes.decode_token") as mock_decode:
            mock_decode.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_wallet(mock_request, mock_credentials)

            assert exc_info.value.status_code == 401


# ==================== Agent Routes Tests ====================


class TestAgentRoutes:
    """Tests for agent API routes."""

    def test_list_agents_empty(self, client):
        """Test listing agents when empty."""
        response = client.get("/api/v1/virtuals/agents/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["total"] == 0

    def test_list_agents_pagination(self, client):
        """Test listing agents with pagination parameters."""
        response = client.get("/api/v1/virtuals/agents/?page=2&per_page=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["per_page"] == 10

    def test_list_agents_invalid_pagination(self, client):
        """Test listing agents with invalid pagination."""
        # per_page exceeds max (100)
        response = client.get("/api/v1/virtuals/agents/?per_page=200")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_agent(self, async_client):
        """Test creating an agent."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_client = MagicMock()
            mock_agent = MagicMock()
            mock_agent.model_dump.return_value = {
                "id": "agent-123",
                "name": "Test Agent",
            }
            mock_client.create_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = await async_client.post(
                "/api/v1/virtuals/agents/",
                json={
                    "name": "Test Agent",
                    "description": "A test agent",
                    "overlay_id": "overlay-123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["id"] == "agent-123"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, async_client):
        """Test getting a non-existent agent."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_agent = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = await async_client.get("/api/v1/virtuals/agents/nonexistent")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_agent_success(self, async_client):
        """Test getting an existing agent."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_client = MagicMock()
            mock_agent = MagicMock()
            mock_agent.model_dump.return_value = {"id": "agent-123", "name": "Test"}
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_get_client.return_value = mock_client

            response = await async_client.get("/api/v1/virtuals/agents/agent-123")

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["id"] == "agent-123"

    @pytest.mark.asyncio
    async def test_run_agent(self, async_client):
        """Test running an agent."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_client = MagicMock()
            mock_agent = MagicMock()
            mock_client.get_agent = AsyncMock(return_value=mock_agent)
            mock_client.run_agent_loop = AsyncMock(return_value=["result1", "result2"])
            mock_get_client.return_value = mock_client

            response = await async_client.post(
                "/api/v1/virtuals/agents/agent-123/run?context=test%20context"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["results"] == ["result1", "result2"]


# ==================== Tokenization Routes Tests ====================


class TestTokenizationRoutes:
    """Tests for tokenization API routes."""

    @pytest.mark.asyncio
    async def test_request_tokenization(self, async_client):
        """Test requesting tokenization."""
        with patch("forge.virtuals.api.routes.get_tokenization_service") as mock_get_service:
            mock_service = MagicMock()
            mock_entity = MagicMock()
            mock_entity.model_dump.return_value = {
                "id": "token-123",
                "status": "pending",
            }
            mock_service.request_tokenization = AsyncMock(return_value=mock_entity)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/tokenization/",
                json={
                    "entity_type": "capsule",
                    "entity_id": "capsule-123",
                    "token_name": "Test Token",
                    "token_symbol": "TEST",
                    "initial_stake_virtual": 100.0,
                    "owner_wallet": "0x123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_get_tokenized_entity_placeholder(self, client):
        """Test getting tokenized entity (placeholder)."""
        response = client.get("/api/v1/virtuals/tokenization/entity-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_contribute_to_bonding_curve(self, async_client):
        """Test contributing to bonding curve."""
        with patch("forge.virtuals.api.routes.get_tokenization_service") as mock_get_service:
            mock_service = MagicMock()
            mock_entity = MagicMock()
            mock_entity.model_dump.return_value = {"id": "entity-123"}
            mock_contribution = MagicMock()
            mock_contribution.model_dump.return_value = {"amount": 100.0}
            mock_service.contribute_to_bonding_curve = AsyncMock(
                return_value=(mock_entity, mock_contribution)
            )
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/tokenization/entity-123/contribute?amount_virtual=100.0"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["contribution"]["amount"] == 100.0

    @pytest.mark.asyncio
    async def test_contribute_invalid_amount(self, async_client):
        """Test contributing with invalid amount."""
        response = await async_client.post(
            "/api/v1/virtuals/tokenization/entity-123/contribute?amount_virtual=-10"
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_governance_proposal(self, async_client):
        """Test creating a governance proposal."""
        with patch("forge.virtuals.api.routes.get_tokenization_service") as mock_get_service:
            mock_service = MagicMock()
            mock_proposal = MagicMock()
            mock_proposal.model_dump.return_value = {
                "id": "proposal-123",
                "title": "Test Proposal",
            }
            mock_service.create_governance_proposal = AsyncMock(return_value=mock_proposal)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/tokenization/entity-123/proposals",
                params={
                    "title": "Test Proposal",
                    "description": "A test proposal",
                    "proposal_type": "parameter_change",
                },
                json={"param": "value"},
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_vote_on_proposal(self, async_client):
        """Test voting on a proposal."""
        with patch("forge.virtuals.api.routes.get_tokenization_service") as mock_get_service:
            mock_service = MagicMock()
            mock_vote = MagicMock()
            mock_vote.model_dump.return_value = {
                "vote": "for",
                "voting_power": 1000,
            }
            mock_service.cast_governance_vote = AsyncMock(return_value=mock_vote)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/tokenization/proposals/proposal-123/vote?vote=for"
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_vote_invalid_vote(self, async_client):
        """Test voting with invalid vote value."""
        response = await async_client.post(
            "/api/v1/virtuals/tokenization/proposals/proposal-123/vote?vote=invalid"
        )

        assert response.status_code == 422


# ==================== ACP Routes Tests ====================


class TestACPRoutes:
    """Tests for ACP API routes."""

    @pytest.mark.asyncio
    async def test_register_offering(self, async_client):
        """Test registering a service offering."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_offering = MagicMock()
            mock_offering.model_dump.return_value = {
                "id": "offering-123",
                "service_type": "knowledge_query",
            }
            mock_service.register_offering = AsyncMock(return_value=mock_offering)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/offerings?agent_id=agent-123",
                json={
                    "service_type": "knowledge_query",
                    "description": "Test offering",
                    "fee_virtual": 1.0,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["service_type"] == "knowledge_query"

    @pytest.mark.asyncio
    async def test_search_offerings(self, async_client):
        """Test searching offerings."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_offering = MagicMock()
            mock_offering.model_dump.return_value = {"id": "offering-1"}
            mock_service.search_offerings = AsyncMock(return_value=[mock_offering])
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/virtuals/acp/offerings?service_type=knowledge_query"
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_create_job(self, async_client):
        """Test creating an ACP job."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_job = MagicMock()
            mock_job.model_dump.return_value = {
                "id": "job-123",
                "status": "request",
            }
            mock_service.create_job = AsyncMock(return_value=mock_job)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/jobs",
                json={
                    "offering_id": "offering-123",
                    "requirements": "Test requirements",
                    "max_fee_virtual": 10.0,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["status"] == "request"

    def test_get_job_placeholder(self, client):
        """Test getting a job (placeholder)."""
        response = client.get("/api/v1/virtuals/acp/jobs/job-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_respond_to_job(self, async_client):
        """Test provider responding to a job."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_job = MagicMock()
            mock_job.model_dump.return_value = {
                "id": "job-123",
                "status": "negotiation",
            }
            mock_service.respond_to_request = AsyncMock(return_value=mock_job)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/jobs/job-123/respond",
                json={
                    "proposed_fee_virtual": 5.0,
                    "estimated_delivery_hours": 24,
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accept_job_terms(self, async_client):
        """Test buyer accepting job terms."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_job = MagicMock()
            mock_job.model_dump.return_value = {
                "id": "job-123",
                "status": "transaction",
            }
            mock_service.accept_terms = AsyncMock(return_value=mock_job)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/jobs/job-123/accept"
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_deliverable(self, async_client):
        """Test provider submitting deliverable."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_job = MagicMock()
            mock_job.model_dump.return_value = {
                "id": "job-123",
                "status": "evaluation",
            }
            mock_service.submit_deliverable = AsyncMock(return_value=mock_job)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/jobs/job-123/deliver",
                json={
                    "content": "Deliverable content",
                    "content_type": "text",
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_evaluate_deliverable(self, async_client):
        """Test evaluating a deliverable."""
        with patch("forge.virtuals.api.routes.get_acp_service") as mock_get_service:
            mock_service = MagicMock()
            mock_job = MagicMock()
            mock_job.model_dump.return_value = {
                "id": "job-123",
                "status": "completed",
            }
            mock_service.evaluate_deliverable = AsyncMock(return_value=mock_job)
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/v1/virtuals/acp/jobs/job-123/evaluate",
                json={
                    "approved": True,
                    "score": 5,
                    "feedback": "Great work!",
                },
            )

            assert response.status_code == 200


# ==================== Revenue Routes Tests ====================


class TestRevenueRoutes:
    """Tests for revenue API routes."""

    @pytest.mark.asyncio
    async def test_get_revenue_summary(self, async_client):
        """Test getting revenue summary."""
        with patch("forge.virtuals.api.routes.get_revenue_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_revenue_summary = AsyncMock(
                return_value={
                    "total_revenue_virtual": 1000.0,
                    "by_type": {"inference_fee": 500.0, "service_fee": 500.0},
                }
            )
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/v1/virtuals/revenue/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["total_revenue_virtual"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_revenue_summary_with_filters(self, async_client):
        """Test getting revenue summary with filters."""
        with patch("forge.virtuals.api.routes.get_revenue_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_revenue_summary = AsyncMock(return_value={"total": 500})
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/virtuals/revenue/summary?entity_type=capsule"
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_entity_revenue(self, async_client):
        """Test getting entity revenue."""
        with patch("forge.virtuals.api.routes.get_revenue_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_entity_revenue = AsyncMock(
                return_value={
                    "entity_id": "entity-123",
                    "total_revenue": 500.0,
                }
            )
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/virtuals/revenue/entities/entity-123?entity_type=capsule"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["total_revenue"] == 500.0

    @pytest.mark.asyncio
    async def test_get_entity_valuation(self, async_client):
        """Test getting entity valuation."""
        with patch("forge.virtuals.api.routes.get_revenue_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.estimate_entity_value = AsyncMock(
                return_value={
                    "entity_id": "entity-123",
                    "estimated_value_virtual": 10000.0,
                    "method": "dcf_perpetuity",
                }
            )
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/virtuals/revenue/entities/entity-123/valuation?entity_type=capsule"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["estimated_value_virtual"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_entity_valuation_custom_rates(self, async_client):
        """Test getting entity valuation with custom rates."""
        with patch("forge.virtuals.api.routes.get_revenue_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.estimate_entity_value = AsyncMock(return_value={"value": 5000})
            mock_get_service.return_value = mock_service

            response = await async_client.get(
                "/api/v1/virtuals/revenue/entities/entity-123/valuation"
                "?entity_type=capsule&discount_rate=0.15&growth_rate=0.08"
            )

            assert response.status_code == 200
            mock_service.estimate_entity_value.assert_called_once()


# ==================== Router Creation Tests ====================


class TestRouterCreation:
    """Tests for router creation and configuration."""

    def test_create_virtuals_router(self):
        """Test creating the main virtuals router."""
        router = create_virtuals_router()

        assert router is not None
        # Check that sub-routers are included
        routes = [route.path for route in router.routes]
        assert any("/agents" in route for route in routes)
        assert any("/tokenization" in route for route in routes)
        assert any("/acp" in route for route in routes)
        assert any("/revenue" in route for route in routes)

    def test_router_prefixes(self):
        """Test that routers have correct prefixes."""
        assert agent_router.prefix == "/agents"
        assert tokenization_router.prefix == "/tokenization"
        assert acp_router.prefix == "/acp"
        assert revenue_router.prefix == "/revenue"

    def test_router_tags(self):
        """Test that routers have correct tags."""
        assert "Agents" in agent_router.tags
        assert "Tokenization" in tokenization_router.tags
        assert "Agent Commerce Protocol" in acp_router.tags
        assert "Revenue" in revenue_router.tags


# ==================== Error Handling Tests ====================


class TestErrorHandling:
    """Tests for error handling in routes."""

    @pytest.mark.asyncio
    async def test_sanitized_error_response(self, async_client):
        """Test that errors are sanitized in responses."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_get_client.side_effect = RuntimeError("Internal database error")

            response = await async_client.post(
                "/api/v1/virtuals/agents/",
                json={
                    "name": "Test Agent",
                    "description": "Test",
                    "overlay_id": "test",
                },
            )

            assert response.status_code == 500
            data = response.json()
            # Should not expose internal error details
            assert "Internal error" in data["detail"]
            assert "database" not in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_404_error_preserved(self, async_client):
        """Test that 404 errors are preserved (not sanitized)."""
        with patch("forge.virtuals.api.routes.get_game_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_agent = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = await async_client.get("/api/v1/virtuals/agents/nonexistent")

            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "Agent not found"
