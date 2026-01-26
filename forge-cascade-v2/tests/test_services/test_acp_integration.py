"""
Integration Tests for Agent Commerce Protocol (ACP) Service

These tests verify the complete ACP lifecycle including:
- Service registration with Agent Gateway
- Job creation and negotiation
- Deliverable submission and evaluation
- Escrow and payment flows
- Agent Gateway ↔ ACP bridge functionality
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from forge.virtuals.acp.nonce_store import NonceStore
from forge.virtuals.acp.service import ACPService
from forge.virtuals.models.acp import (
    ACPDeliverable,
    ACPDispute,
    ACPEvaluation,
    ACPJob,
    ACPJobCreate,
    ACPJobStatus,
    ACPMemo,
    ACPNegotiationTerms,
    ACPPhase,
    JobOffering,
)


class MockJobRepository:
    """Mock repository for ACP jobs."""

    def __init__(self):
        self._jobs: dict[str, ACPJob] = {}

    async def create(self, job: ACPJob) -> ACPJob:
        self._jobs[job.id] = job
        return job

    async def get_by_id(self, job_id: str) -> ACPJob | None:
        return self._jobs.get(job_id)

    async def update(self, job: ACPJob) -> ACPJob:
        self._jobs[job.id] = job
        return job

    async def search(self, **kwargs) -> list[ACPJob]:
        return list(self._jobs.values())


class MockOfferingRepository:
    """Mock repository for job offerings."""

    def __init__(self):
        self._offerings: dict[str, JobOffering] = {}

    async def create(self, offering: JobOffering) -> JobOffering:
        self._offerings[offering.id] = offering
        return offering

    async def get_by_id(self, offering_id: str) -> JobOffering | None:
        return self._offerings.get(offering_id)

    async def get_by_provider(self, provider_address: str) -> list[JobOffering]:
        return [o for o in self._offerings.values() if o.provider_wallet == provider_address]

    async def search(self, **kwargs) -> list[JobOffering]:
        return list(self._offerings.values())


class MockChainManager:
    """Mock chain manager for testing without blockchain."""

    def __init__(self):
        self.primary_client = MockChainClient()


class MockChainClient:
    """Mock chain client for testing."""

    def __init__(self):
        self.chain = MagicMock()
        self.chain.value = "base"
        self._w3 = MagicMock()
        self._operator_account = MagicMock()
        self._operator_account.address = "0xOperator123"

    async def transfer_tokens(self, token_address: str, to_address: str, amount: float):
        return MagicMock(tx_hash="0xmocktx", status="success")

    async def wait_for_transaction(self, tx_hash: str, timeout_seconds: int = 60):
        return MagicMock(tx_hash=tx_hash, status="success")


@pytest.fixture
def nonce_store():
    """Create a fresh nonce store for each test."""
    return NonceStore()


@pytest.fixture
def job_repo():
    """Create a mock job repository."""
    return MockJobRepository()


@pytest.fixture
def offering_repo():
    """Create a mock offering repository."""
    return MockOfferingRepository()


@pytest.fixture
def acp_service(job_repo, offering_repo, nonce_store):
    """Create an ACP service with mock dependencies."""
    service = ACPService(
        job_repository=job_repo,
        offering_repository=offering_repo,
        nonce_store=nonce_store,
    )
    service._chain_manager = MockChainManager()
    return service


@pytest.fixture
def sample_offering():
    """Create a sample job offering."""
    return JobOffering(
        id=str(uuid4()),
        provider_agent_id="agent_123",
        provider_wallet="0xProvider123",
        service_type="knowledge_query",
        title="Knowledge Graph Query Service",
        description="Execute queries against the Forge knowledge graph",
        base_fee_virtual=10.0,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
    )


@pytest.fixture
def sample_job_create():
    """Create a sample job creation request."""
    return ACPJobCreate(
        offering_id=str(uuid4()),
        buyer_agent_id="agent_buyer_123",
        provider_agent_id="agent_provider_456",
        requirements="Query for all capsules about AI safety",
        proposed_payment=Decimal("50.0"),
        input_data={"query": "Find all AI safety related capsules"},
    )


class TestACPServiceInitialization:
    """Tests for ACP service initialization."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, acp_service):
        """Service should initialize correctly."""
        assert acp_service is not None
        assert acp_service._job_repo is not None
        assert acp_service._offering_repo is not None

    @pytest.mark.asyncio
    async def test_nonce_store_integration(self, acp_service):
        """Nonce store should be properly initialized."""
        assert acp_service._nonce_store is not None

        wallet = "0xTestWallet"
        nonce1 = acp_service._nonce_store.get_next_nonce(wallet)
        nonce2 = acp_service._nonce_store.get_next_nonce(wallet)

        assert nonce1 == 0
        assert nonce2 == 1


class TestOfferingRegistration:
    """Tests for service offering registration."""

    @pytest.mark.asyncio
    async def test_register_offering(self, acp_service, sample_offering):
        """Should successfully register a new offering."""
        registered = await acp_service.register_offering(
            agent_id="agent_123",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )

        assert registered.id is not None
        assert registered.provider_wallet == "0xProvider123"
        assert registered.service_type == "knowledge_query"

    @pytest.mark.asyncio
    async def test_register_multiple_offerings(self, acp_service):
        """Provider can register multiple offerings."""
        offerings = []
        for i, service_type in enumerate(
            ["knowledge_query", "semantic_search", "capsule_generation"]
        ):
            offering = JobOffering(
                id=str(uuid4()),
                provider_agent_id="agent_123",
                provider_wallet="0xProvider123",
                service_type=service_type,
                title=f"Service {i}",
                description=f"Description {i}",
                base_fee_virtual=10.0,
            )
            registered = await acp_service.register_offering(
                agent_id="agent_123",
                agent_wallet="0xProvider123",
                offering=offering,
            )
            offerings.append(registered)

        assert len(offerings) == 3

        # Verify all offerings are retrievable
        provider_offerings = await acp_service._offering_repo.get_by_provider("0xProvider123")
        assert len(provider_offerings) == 3


class TestJobCreation:
    """Tests for ACP job creation."""

    @pytest.mark.asyncio
    async def test_create_job(self, acp_service, sample_offering, sample_job_create):
        """Should successfully create a new job."""
        # First register the offering
        await acp_service.register_offering(
            agent_id="agent_provider_456",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )

        # Create the job
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(
            create_request=sample_job_create,
            buyer_wallet="0xBuyer123",
        )

        assert job.id is not None
        assert job.phase == ACPPhase.NEGOTIATION
        assert job.status == ACPJobStatus.PENDING
        assert job.buyer_address == "0xBuyer123"

    @pytest.mark.asyncio
    async def test_create_job_stores_requirements(
        self, acp_service, sample_offering, sample_job_create
    ):
        """Job should store the buyer's requirements."""
        await acp_service.register_offering(
            agent_id="agent_provider_456",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )

        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(
            create_request=sample_job_create,
            buyer_wallet="0xBuyer123",
        )

        assert job.requirements == "Query for all capsules about AI safety"
        assert job.input_data == {"query": "Find all AI safety related capsules"}


class TestNegotiationPhase:
    """Tests for the negotiation phase."""

    @pytest.mark.asyncio
    async def test_provider_responds_with_terms(
        self, acp_service, sample_offering, sample_job_create
    ):
        """Provider should be able to respond with terms."""
        # Setup
        await acp_service.register_offering(
            agent_id="agent_provider_456",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(
            create_request=sample_job_create,
            buyer_wallet="0xBuyer123",
        )

        # Provider responds
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
            requirements=["High accuracy required"],
            acceptance_criteria=["95% accuracy threshold"],
        )

        updated_job = await acp_service.respond_with_terms(
            job_id=job.id,
            terms=terms,
            provider_wallet="0xProvider123",
        )

        assert updated_job.negotiation_terms is not None
        assert updated_job.negotiation_terms.proposed_price == Decimal("50.0")

    @pytest.mark.asyncio
    async def test_buyer_accepts_terms(self, acp_service, sample_offering, sample_job_create):
        """Buyer accepting terms should move job to execution phase."""
        # Setup
        await acp_service.register_offering(
            agent_id="agent_provider_456",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(
            create_request=sample_job_create,
            buyer_wallet="0xBuyer123",
        )

        # Provider responds
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(
            job_id=job.id,
            terms=terms,
            provider_wallet="0xProvider123",
        )

        # Buyer accepts
        updated_job = await acp_service.accept_terms(
            job_id=job.id,
            buyer_wallet="0xBuyer123",
        )

        assert updated_job.phase == ACPPhase.EXECUTION
        assert updated_job.status == ACPJobStatus.IN_PROGRESS


class TestDeliverableSubmission:
    """Tests for deliverable submission."""

    @pytest.mark.asyncio
    async def test_submit_deliverable(self, acp_service, sample_offering, sample_job_create):
        """Provider should be able to submit a deliverable."""
        # Setup - go through negotiation
        await acp_service.register_offering(
            agent_id="agent_provider_456",
            agent_wallet="0xProvider123",
            offering=sample_offering,
        )
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(
            create_request=sample_job_create,
            buyer_wallet="0xBuyer123",
        )
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider123")
        await acp_service.accept_terms(job.id, "0xBuyer123")

        # Submit deliverable
        deliverable_content = {
            "results": [
                {"capsule_id": "cap_1", "title": "AI Safety Overview"},
                {"capsule_id": "cap_2", "title": "AI Alignment Research"},
            ],
            "query_time_ms": 150,
        }

        deliverable = ACPDeliverable(
            job_id=job.id,
            content=deliverable_content,
            content_hash=hashlib.sha256(
                json.dumps(deliverable_content, sort_keys=True).encode()
            ).hexdigest(),
            mime_type="application/json",
        )

        updated_job = await acp_service.submit_deliverable(
            job_id=job.id,
            deliverable=deliverable,
            provider_wallet="0xProvider123",
        )

        assert updated_job.phase == ACPPhase.EVALUATION
        assert updated_job.deliverable is not None


class TestEvaluationPhase:
    """Tests for the evaluation phase."""

    @pytest.mark.asyncio
    async def test_positive_evaluation(self, acp_service, sample_offering, sample_job_create):
        """Positive evaluation should complete the job."""
        # Full setup through delivery
        await acp_service.register_offering("agent_provider_456", "0xProvider123", sample_offering)
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(sample_job_create, "0xBuyer123")
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider123")
        await acp_service.accept_terms(job.id, "0xBuyer123")
        deliverable = ACPDeliverable(
            job_id=job.id,
            content={"result": "success"},
            content_hash="abc123",
            mime_type="application/json",
        )
        await acp_service.submit_deliverable(job.id, deliverable, "0xProvider123")

        # Evaluate
        evaluation = ACPEvaluation(
            job_id=job.id,
            evaluator_address="0xBuyer123",
            rating=5,
            passed=True,
            feedback="Excellent work, results are accurate.",
        )

        completed_job = await acp_service.evaluate_deliverable(
            job_id=job.id,
            evaluation=evaluation,
            buyer_wallet="0xBuyer123",
        )

        assert completed_job.phase == ACPPhase.COMPLETED
        assert completed_job.status == ACPJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failed_evaluation_triggers_dispute(
        self, acp_service, sample_offering, sample_job_create
    ):
        """Failed evaluation with dispute should move to dispute phase."""
        # Full setup through delivery
        await acp_service.register_offering("agent_provider_456", "0xProvider123", sample_offering)
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(sample_job_create, "0xBuyer123")
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider123")
        await acp_service.accept_terms(job.id, "0xBuyer123")
        deliverable = ACPDeliverable(
            job_id=job.id,
            content={"result": "failure"},
            content_hash="def456",
            mime_type="application/json",
        )
        await acp_service.submit_deliverable(job.id, deliverable, "0xProvider123")

        # Negative evaluation
        evaluation = ACPEvaluation(
            job_id=job.id,
            evaluator_address="0xBuyer123",
            rating=1,
            passed=False,
            feedback="Results are inaccurate, not what was requested.",
        )

        evaluated_job = await acp_service.evaluate_deliverable(
            job_id=job.id,
            evaluation=evaluation,
            buyer_wallet="0xBuyer123",
        )

        # Job should be completed but marked as failed
        assert (
            evaluated_job.status == ACPJobStatus.FAILED or evaluated_job.phase == ACPPhase.DISPUTE
        )


class TestDisputeResolution:
    """Tests for dispute resolution."""

    @pytest.mark.asyncio
    async def test_file_dispute(self, acp_service, sample_offering, sample_job_create):
        """Should be able to file a dispute."""
        # Setup through evaluation
        await acp_service.register_offering("agent_provider_456", "0xProvider123", sample_offering)
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(sample_job_create, "0xBuyer123")
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider123")
        await acp_service.accept_terms(job.id, "0xBuyer123")
        deliverable = ACPDeliverable(
            job_id=job.id,
            content={"result": "disputed"},
            content_hash="ghi789",
            mime_type="application/json",
        )
        await acp_service.submit_deliverable(job.id, deliverable, "0xProvider123")

        # File dispute
        dispute = ACPDispute(
            job_id=job.id,
            initiator_address="0xBuyer123",
            reason="Deliverable does not meet requirements",
            evidence=["Screenshot showing incorrect results"],
        )

        disputed_job = await acp_service.file_dispute(
            job_id=job.id,
            dispute=dispute,
            initiator_wallet="0xBuyer123",
        )

        assert disputed_job.phase == ACPPhase.DISPUTE
        assert disputed_job.status == ACPJobStatus.DISPUTED


class TestMemoExchange:
    """Tests for memo/message exchange."""

    @pytest.mark.asyncio
    async def test_send_memo(self, acp_service, sample_offering, sample_job_create):
        """Parties should be able to exchange memos."""
        # Setup
        await acp_service.register_offering("agent_provider_456", "0xProvider123", sample_offering)
        sample_job_create.offering_id = sample_offering.id
        job = await acp_service.create_job(sample_job_create, "0xBuyer123")

        # Send memo
        memo = ACPMemo(
            job_id=job.id,
            sender_address="0xBuyer123",
            content="Can you clarify the query parameters?",
            memo_type="question",
        )

        result = await acp_service.send_memo(
            job_id=job.id,
            memo=memo,
            sender_wallet="0xBuyer123",
        )

        assert result is not None
        # Verify memo is stored
        job_with_memos = await acp_service.get_job(job.id)
        assert job_with_memos.memos is not None


class TestAgentGatewayBridge:
    """Tests for Agent Gateway ↔ ACP integration."""

    @pytest.mark.asyncio
    async def test_gateway_capability_mapping(self):
        """Agent capabilities should map to ACP service types."""
        from forge.models.agent_gateway import AgentCapability
        from forge.services.agent_gateway import AgentGatewayService

        # Verify mapping exists
        expected_mappings = {
            AgentCapability.QUERY_GRAPH: "knowledge_query",
            AgentCapability.SEMANTIC_SEARCH: "semantic_search",
            AgentCapability.CREATE_CAPSULES: "capsule_generation",
            AgentCapability.EXECUTE_CASCADE: "overlay_execution",
        }

        for cap, service_type in expected_mappings.items():
            assert cap in AgentGatewayService.CAPABILITY_SERVICE_MAP
            assert AgentGatewayService.CAPABILITY_SERVICE_MAP[cap] == service_type

    @pytest.mark.asyncio
    async def test_to_acp_offering_generates_schema(self):
        """to_acp_offering should generate proper input/output schemas."""
        from forge.models.agent_gateway import AgentCapability, AgentSession, AgentTrustLevel
        from forge.services.agent_gateway import AgentGatewayService

        gateway = AgentGatewayService()

        # Create a mock session
        session = AgentSession(
            session_id="test_session_123",
            agent_id="agent_123",
            api_key_hash="hash123",
            trust_level=AgentTrustLevel.VERIFIED,
            capabilities=[
                AgentCapability.QUERY_GRAPH,
                AgentCapability.SEMANTIC_SEARCH,
            ],
        )
        gateway._sessions["test_session_123"] = session

        # Generate offering data
        offering_data = await gateway.to_acp_offering(
            session_id="test_session_123",
            service_type="knowledge_query",
            title="Test Knowledge Service",
            description="Test description",
            base_fee_virtual=10.0,
        )

        assert offering_data["service_type"] == "knowledge_query"
        assert "input_schema" in offering_data
        assert "output_schema" in offering_data
        assert offering_data["input_schema"]["type"] == "object"


class TestEndToEndJobLifecycle:
    """End-to-end tests for complete job lifecycle."""

    @pytest.mark.asyncio
    async def test_complete_successful_job(self, acp_service, sample_offering):
        """Test a complete job from creation to completion."""
        # 1. Register offering
        await acp_service.register_offering(
            agent_id="provider_agent",
            agent_wallet="0xProvider",
            offering=sample_offering,
        )

        # 2. Create job
        create_request = ACPJobCreate(
            offering_id=sample_offering.id,
            buyer_agent_id="buyer_agent",
            provider_agent_id="provider_agent",
            requirements="Find all documents about climate change",
            proposed_payment=Decimal("50.0"),
            input_data={"query": "climate change documents"},
        )
        job = await acp_service.create_job(create_request, "0xBuyer")
        assert job.phase == ACPPhase.NEGOTIATION

        # 3. Negotiate
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("50.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=48),
            requirements=["Include metadata"],
            acceptance_criteria=["At least 10 relevant results"],
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider")
        job = await acp_service.accept_terms(job.id, "0xBuyer")
        assert job.phase == ACPPhase.EXECUTION

        # 4. Deliver
        result_content = {
            "documents": [{"id": f"doc_{i}", "title": f"Climate Document {i}"} for i in range(15)],
            "total_found": 15,
        }
        deliverable = ACPDeliverable(
            job_id=job.id,
            content=result_content,
            content_hash=hashlib.sha256(
                json.dumps(result_content, sort_keys=True).encode()
            ).hexdigest(),
            mime_type="application/json",
        )
        job = await acp_service.submit_deliverable(job.id, deliverable, "0xProvider")
        assert job.phase == ACPPhase.EVALUATION

        # 5. Evaluate
        evaluation = ACPEvaluation(
            job_id=job.id,
            evaluator_address="0xBuyer",
            rating=5,
            passed=True,
            feedback="Excellent results, exceeded expectations!",
        )
        job = await acp_service.evaluate_deliverable(job.id, evaluation, "0xBuyer")
        assert job.phase == ACPPhase.COMPLETED
        assert job.status == ACPJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_complete_disputed_job(self, acp_service, sample_offering):
        """Test a job that ends in dispute."""
        # Setup through delivery
        await acp_service.register_offering("provider", "0xProvider", sample_offering)
        create_request = ACPJobCreate(
            offering_id=sample_offering.id,
            buyer_agent_id="buyer",
            provider_agent_id="provider",
            requirements="Find quantum computing papers",
            proposed_payment=Decimal("100.0"),
        )
        job = await acp_service.create_job(create_request, "0xBuyer")
        terms = ACPNegotiationTerms(
            proposed_price=Decimal("100.0"),
            proposed_deadline=datetime.now(UTC) + timedelta(hours=24),
        )
        await acp_service.respond_with_terms(job.id, terms, "0xProvider")
        job = await acp_service.accept_terms(job.id, "0xBuyer")

        # Deliver poor quality
        deliverable = ACPDeliverable(
            job_id=job.id,
            content={"documents": []},  # Empty results
            content_hash="empty123",
            mime_type="application/json",
        )
        job = await acp_service.submit_deliverable(job.id, deliverable, "0xProvider")

        # Buyer disputes
        dispute = ACPDispute(
            job_id=job.id,
            initiator_address="0xBuyer",
            reason="No results returned despite many papers existing",
            evidence=["Manual search found 50+ papers"],
        )
        job = await acp_service.file_dispute(job.id, dispute, "0xBuyer")

        assert job.phase == ACPPhase.DISPUTE
        assert job.status == ACPJobStatus.DISPUTED


class TestConcurrentJobs:
    """Tests for handling multiple concurrent jobs."""

    @pytest.mark.asyncio
    async def test_provider_handles_multiple_jobs(self, acp_service, sample_offering):
        """Provider should be able to handle multiple concurrent jobs."""
        await acp_service.register_offering("provider", "0xProvider", sample_offering)

        # Create 5 concurrent jobs
        jobs = []
        for i in range(5):
            create_request = ACPJobCreate(
                offering_id=sample_offering.id,
                buyer_agent_id=f"buyer_{i}",
                provider_agent_id="provider",
                requirements=f"Query {i}",
                proposed_payment=Decimal("20.0"),
            )
            job = await acp_service.create_job(create_request, f"0xBuyer{i}")
            jobs.append(job)

        assert len(jobs) == 5
        assert all(j.status == ACPJobStatus.PENDING for j in jobs)

        # All jobs should have unique IDs
        job_ids = [j.id for j in jobs]
        assert len(job_ids) == len(set(job_ids))
