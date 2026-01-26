"""
E2E Test Fixtures

Provides in-memory Virtuals Protocol repositories and pre-configured
service instances for end-to-end testing of the Forge + Virtuals lifecycle.

IMPORTANT: All mock chain infrastructure has been removed. Services use
VirtualsEnvironment.LOCAL simulation mode, which returns simulated
TransactionRecords without touching any blockchain. The EscrowService
operates in simulated mode when no escrow contract is deployed.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT (must be set before importing Forge modules)
# ═══════════════════════════════════════════════════════════════════════════════

os.environ.setdefault("APP_ENV", "testing")
os.environ["VIRTUALS_ENVIRONMENT"] = "local"
os.environ["VIRTUALS_ENABLE_TOKENIZATION"] = "true"
os.environ["VIRTUALS_ENABLE_ACP"] = "true"
os.environ["VIRTUALS_API_KEY"] = "test-key"

# ═══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY VIRTUALS PROTOCOL REPOSITORIES
#
# These exist because the Virtuals Protocol data models (TokenizedEntity,
# BondingCurveContribution, ACPJob, etc.) have no Neo4j implementations —
# they are protocol-layer objects stored in-memory by their services.
# This is NOT mock infrastructure; it is the correct storage layer for
# these models in LOCAL and TESTNET environments.
# ═══════════════════════════════════════════════════════════════════════════════


class InMemoryRepository:
    """Generic in-memory repository backed by a dict."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def create(self, entity: Any) -> Any:
        key = getattr(entity, "id", str(uuid4()))
        self._store[key] = entity
        return entity

    async def get_by_id(self, entity_id: str) -> Any | None:
        return self._store.get(entity_id)

    async def update(self, entity: Any) -> Any:
        key = getattr(entity, "id", None)
        if key:
            self._store[key] = entity
        return entity

    async def delete(self, entity_id: str) -> bool:
        return self._store.pop(entity_id, None) is not None


class TokenizedEntityRepository(InMemoryRepository):
    """In-memory repository for TokenizedEntity records."""

    async def get_by_entity_id(self, entity_type: str, entity_id: str) -> Any | None:
        for entity in self._store.values():
            if (
                getattr(entity, "entity_type", None) == entity_type
                and getattr(entity, "entity_id", None) == entity_id
            ):
                return entity
        return None


class ContributionRepository(InMemoryRepository):
    """In-memory repository for ContributionRecord / BondingCurveContribution."""

    async def get_by_entity(self, entity_id: str) -> list[Any]:
        return [
            c for c in self._store.values() if getattr(c, "tokenized_entity_id", None) == entity_id
        ]


class ProposalRepository(InMemoryRepository):
    """In-memory repository for TokenHolderProposal."""


class JobRepository(InMemoryRepository):
    """In-memory repository for ACPJob."""

    async def count_by_provider(self, agent_id: str) -> int:
        return sum(
            1 for j in self._store.values() if getattr(j, "provider_agent_id", None) == agent_id
        )

    async def sum_revenue_by_provider(self, agent_id: str) -> float:
        return sum(
            getattr(j, "agreed_fee_virtual", 0)
            for j in self._store.values()
            if getattr(j, "provider_agent_id", None) == agent_id
            and getattr(j, "status", None) == "completed"
        )

    async def average_rating_by_provider(self, agent_id: str) -> float | None:
        scores = [
            getattr(j, "evaluation_score", None)
            for j in self._store.values()
            if getattr(j, "provider_agent_id", None) == agent_id
            and getattr(j, "evaluation_score", None) is not None
        ]
        if not scores:
            return None
        return sum(scores) / len(scores)


class OfferingRepository(InMemoryRepository):
    """In-memory repository for JobOffering."""

    async def search(
        self,
        service_type: str | None = None,
        query: str | None = None,
        max_fee: float | None = None,
        min_provider_reputation: float = 0.0,
        limit: int = 20,
    ) -> list[Any]:
        results = list(self._store.values())
        if service_type:
            results = [o for o in results if getattr(o, "service_type", None) == service_type]
        if max_fee is not None:
            results = [o for o in results if getattr(o, "base_fee_virtual", 0) <= max_fee]
        return results[:limit]

    async def get_by_agent(self, agent_id: str) -> list[Any]:
        return [
            o for o in self._store.values() if getattr(o, "provider_agent_id", None) == agent_id
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# PYTEST FIXTURES — Virtuals Protocol Repositories
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def entity_repo() -> TokenizedEntityRepository:
    return TokenizedEntityRepository()


@pytest.fixture()
def contribution_repo() -> ContributionRepository:
    return ContributionRepository()


@pytest.fixture()
def proposal_repo() -> ProposalRepository:
    return ProposalRepository()


@pytest.fixture()
def job_repo() -> JobRepository:
    return JobRepository()


@pytest.fixture()
def offering_repo() -> OfferingRepository:
    return OfferingRepository()


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE FIXTURES — Real Code Paths, LOCAL Simulation Mode
#
# All services run their real production code. The VirtualsEnvironment.LOCAL
# setting causes blockchain methods to return simulated TransactionRecords
# instead of calling real chains. No AsyncMock patches are used.
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def tokenization_service(
    entity_repo: TokenizedEntityRepository,
    contribution_repo: ContributionRepository,
    proposal_repo: ProposalRepository,
) -> Any:
    """TokenizationService with LOCAL simulation — no mock patches."""
    from forge.virtuals.config import VirtualsConfig, configure_virtuals

    test_config = VirtualsConfig(
        environment="local",
        enable_tokenization=True,
        enable_acp=True,
        enable_revenue_sharing=True,
        enable_cross_chain=False,
        api_key="test-key",
        agent_creation_fee=100,
    )
    configure_virtuals(test_config)

    from forge.virtuals.tokenization.service import TokenizationService

    svc = TokenizationService(entity_repo, contribution_repo, proposal_repo)
    svc.config = test_config
    # No AsyncMock patches — LOCAL simulation handles blockchain methods
    return svc


@pytest.fixture()
async def acp_service(
    job_repo: JobRepository,
    offering_repo: OfferingRepository,
) -> Any:
    """ACPService with real EscrowService (simulated mode) and in-memory NonceStore."""
    from forge.virtuals.acp.escrow import EscrowService
    from forge.virtuals.acp.nonce_store import NonceStore
    from forge.virtuals.acp.service import ACPService
    from forge.virtuals.config import VirtualsConfig, configure_virtuals

    test_config = VirtualsConfig(
        environment="local",
        enable_acp=True,
        enable_tokenization=True,
        api_key="test-key",
    )
    configure_virtuals(test_config)

    # Real NonceStore with in-memory fallback (redis_client=None uses dict backend)
    nonce_store = NonceStore(redis_client=None, ttl_seconds=600)

    # Real EscrowService in simulated mode (no contract = simulated)
    escrow_svc = EscrowService()
    await escrow_svc.initialize()

    svc = ACPService(
        job_repo, offering_repo, nonce_store=nonce_store, escrow_service=escrow_svc
    )
    svc.config = test_config
    return svc


@pytest.fixture()
async def tipping_service() -> Any:
    """FrowgTippingService with LOCAL simulation — real initialize()."""
    from forge.virtuals.config import VirtualsConfig, configure_virtuals

    test_config = VirtualsConfig(
        environment="local",
        enable_acp=True,
        enable_tokenization=True,
        api_key="test-key",
    )
    configure_virtuals(test_config)

    from forge.virtuals.tipping.service import FrowgTippingService

    svc = FrowgTippingService()
    await svc.initialize()  # LOCAL mode skips chain manager setup
    return svc


# ═══════════════════════════════════════════════════════════════════════════════
# TEST USERS
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_USER = {
    "id": str(uuid4()),
    "username": "admin_genomics",
    "email": "admin@forge-genomics.io",
    "trust_level": 90,
    "wallet": f"0x{'a1' * 20}",
}

RESEARCHER_USER = {
    "id": str(uuid4()),
    "username": "researcher_wu",
    "email": "wu@forge-genomics.io",
    "trust_level": 60,
    "wallet": f"0x{'b2' * 20}",
}

CONTRIBUTOR_USER = {
    "id": str(uuid4()),
    "username": "contributor_lee",
    "email": "lee@forge-genomics.io",
    "trust_level": 60,
    "wallet": f"0x{'c3' * 20}",
}

SOLANA_SENDER = "7B8xLj1111111111111111111111111111111111111"
SOLANA_RECIPIENT = "9Y3kMn2222222222222222222222222222222222222"


@pytest.fixture()
def users() -> dict[str, dict[str, Any]]:
    """Return a dict of test users keyed by role."""
    return {
        "admin": ADMIN_USER,
        "researcher": RESEARCHER_USER,
        "contributor": CONTRIBUTOR_USER,
    }
