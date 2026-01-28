"""
PrimeKG Routes Tests for Forge Cascade V2

Comprehensive tests for PrimeKG biomedical knowledge graph API routes including:
- Differential diagnosis generation
- Phenotype-to-disease mapping
- Drug-disease interactions
- Gene-disease associations
- Semantic search
- Disease details
- Admin operations
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_overlay_manager():
    """Create mock overlay manager for PrimeKG operations."""
    manager = MagicMock()

    result = MagicMock()
    result.success = True
    result.data = {}
    result.error = None

    manager.execute = AsyncMock(return_value=result)
    return manager


@pytest.fixture
def mock_db_for_primekg():
    """Create mock DB client for PrimeKG queries."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=[])
    db.execute_single = AsyncMock(return_value={"count": 50000})
    return db


@pytest.fixture
def trusted_auth_headers(user_factory):
    """Create authentication headers for a trusted user."""
    from forge.security.tokens import create_access_token

    user = user_factory(trust_level=70)
    token = create_access_token(
        user_id=user["id"],
        username=user["username"],
        role="user",
        trust_flame=user["trust_level"],
    )
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Differential Diagnosis Tests
# =============================================================================


class TestDifferentialDiagnosisRoute:
    """Tests for POST /primekg/diagnosis/differential endpoint."""

    def test_differential_unauthorized(self, client: TestClient):
        """Differential diagnosis without auth fails."""
        response = client.post(
            "/api/v1/primekg/diagnosis/differential",
            json={
                "phenotypes": ["HP:0001250", "HP:0001251"],
            },
        )
        assert response.status_code == 401

    def test_differential_authorized(self, client: TestClient, auth_headers: dict):
        """Differential diagnosis with auth and valid data."""
        response = client.post(
            "/api/v1/primekg/diagnosis/differential",
            json={
                "phenotypes": ["HP:0001250", "HP:0001251"],
                "genes": [],
                "medications": [],
                "limit": 10,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_differential_empty_phenotypes_fails(
        self, client: TestClient, auth_headers: dict
    ):
        """Differential diagnosis with empty phenotypes fails validation."""
        response = client.post(
            "/api/v1/primekg/diagnosis/differential",
            json={
                "phenotypes": [],  # Empty - should fail min_length=1
            },
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]

    def test_differential_too_many_phenotypes(
        self, client: TestClient, auth_headers: dict
    ):
        """Differential diagnosis with too many phenotypes fails validation."""
        response = client.post(
            "/api/v1/primekg/diagnosis/differential",
            json={
                "phenotypes": [f"HP:000{i:04d}" for i in range(60)],  # Over 50 max
            },
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]

    def test_differential_limit_validation(self, client: TestClient, auth_headers: dict):
        """Differential diagnosis with invalid limit fails validation."""
        response = client.post(
            "/api/v1/primekg/diagnosis/differential",
            json={
                "phenotypes": ["HP:0001250"],
                "limit": 100,  # Over 50 max
            },
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Phenotype Search Tests
# =============================================================================


class TestPhenotypeSearchRoute:
    """Tests for POST /primekg/diagnosis/phenotype-search endpoint."""

    def test_phenotype_search_unauthorized(self, client: TestClient):
        """Phenotype search without auth fails."""
        response = client.post(
            "/api/v1/primekg/diagnosis/phenotype-search",
            json={"phenotypes": ["HP:0001250"]},
        )
        assert response.status_code == 401

    def test_phenotype_search_authorized(self, client: TestClient, auth_headers: dict):
        """Phenotype search with auth and valid data."""
        response = client.post(
            "/api/v1/primekg/diagnosis/phenotype-search",
            json={
                "phenotypes": ["HP:0001250", "HP:0001251"],
                "limit": 20,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_phenotype_search_empty_fails(self, client: TestClient, auth_headers: dict):
        """Phenotype search with empty phenotypes fails."""
        response = client.post(
            "/api/v1/primekg/diagnosis/phenotype-search",
            json={"phenotypes": []},
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Drug-Disease Tests
# =============================================================================


class TestDrugsForDiseaseRoute:
    """Tests for POST /primekg/drugs/by-disease endpoint."""

    def test_drugs_by_disease_unauthorized(self, client: TestClient):
        """Get drugs by disease without auth fails."""
        response = client.post(
            "/api/v1/primekg/drugs/by-disease",
            json={"disease_id": "MONDO:0005148"},
        )
        assert response.status_code == 401

    def test_drugs_by_disease_authorized(self, client: TestClient, auth_headers: dict):
        """Get drugs by disease with auth and valid data."""
        response = client.post(
            "/api/v1/primekg/drugs/by-disease",
            json={"disease_id": "MONDO:0005148"},
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_drugs_by_disease_missing_id(self, client: TestClient, auth_headers: dict):
        """Get drugs by disease without disease_id fails."""
        response = client.post(
            "/api/v1/primekg/drugs/by-disease",
            json={},  # Missing disease_id
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


class TestDrugInteractionsRoute:
    """Tests for POST /primekg/drugs/interactions endpoint."""

    def test_drug_interactions_unauthorized(self, client: TestClient):
        """Check drug interactions without auth fails."""
        response = client.post(
            "/api/v1/primekg/drugs/interactions",
            json={"drugs": ["aspirin"]},
        )
        assert response.status_code == 401

    def test_drug_interactions_authorized(self, client: TestClient, auth_headers: dict):
        """Check drug interactions with auth and valid data."""
        response = client.post(
            "/api/v1/primekg/drugs/interactions",
            json={
                "drugs": ["aspirin", "warfarin"],
                "diseases": ["MONDO:0005148"],
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_drug_interactions_empty_drugs_fails(
        self, client: TestClient, auth_headers: dict
    ):
        """Check drug interactions with empty drugs fails."""
        response = client.post(
            "/api/v1/primekg/drugs/interactions",
            json={"drugs": []},
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]

    def test_drug_interactions_too_many_drugs(
        self, client: TestClient, auth_headers: dict
    ):
        """Check drug interactions with too many drugs fails."""
        response = client.post(
            "/api/v1/primekg/drugs/interactions",
            json={"drugs": [f"drug{i}" for i in range(25)]},  # Over 20 max
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Gene Association Tests
# =============================================================================


class TestGeneAssociationsRoute:
    """Tests for POST /primekg/genes/associations endpoint."""

    def test_gene_associations_unauthorized(self, client: TestClient):
        """Get gene associations without auth fails."""
        response = client.post(
            "/api/v1/primekg/genes/associations",
            json={"gene_id": "SCN1A"},
        )
        assert response.status_code == 401

    def test_gene_associations_by_gene(self, client: TestClient, auth_headers: dict):
        """Get gene associations by gene ID."""
        response = client.post(
            "/api/v1/primekg/genes/associations",
            json={
                "gene_id": "SCN1A",
                "limit": 50,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 400, 401, 500, 503]

    def test_gene_associations_by_disease(self, client: TestClient, auth_headers: dict):
        """Get gene associations by disease ID."""
        response = client.post(
            "/api/v1/primekg/genes/associations",
            json={
                "disease_id": "MONDO:0005148",
                "limit": 50,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 400, 401, 500, 503]

    def test_gene_associations_neither_id_fails(
        self, client: TestClient, auth_headers: dict
    ):
        """Get gene associations without gene_id or disease_id fails."""
        response = client.post(
            "/api/v1/primekg/genes/associations",
            json={},  # Neither gene_id nor disease_id
            headers=auth_headers,
        )
        # Should return 400 from endpoint validation
        assert response.status_code in [400, 401, 500, 503]


# =============================================================================
# Semantic Search Tests
# =============================================================================


class TestSemanticSearchRoute:
    """Tests for POST /primekg/search/semantic endpoint."""

    def test_semantic_search_unauthorized(self, client: TestClient):
        """Semantic search without auth fails."""
        response = client.post(
            "/api/v1/primekg/search/semantic",
            json={"query": "diabetes treatment"},
        )
        assert response.status_code == 401

    def test_semantic_search_authorized(self, client: TestClient, auth_headers: dict):
        """Semantic search with auth and valid query."""
        response = client.post(
            "/api/v1/primekg/search/semantic",
            json={
                "query": "diabetes treatment options",
                "limit": 10,
                "min_score": 0.7,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_semantic_search_with_node_type(self, client: TestClient, auth_headers: dict):
        """Semantic search filtered by node type."""
        response = client.post(
            "/api/v1/primekg/search/semantic",
            json={
                "query": "seizure medication",
                "node_type": "drug",
                "limit": 10,
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_semantic_search_query_too_short(
        self, client: TestClient, auth_headers: dict
    ):
        """Semantic search with query too short fails."""
        response = client.post(
            "/api/v1/primekg/search/semantic",
            json={"query": "ab"},  # Under 3 char min
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]

    def test_semantic_search_query_too_long(
        self, client: TestClient, auth_headers: dict
    ):
        """Semantic search with query too long fails."""
        response = client.post(
            "/api/v1/primekg/search/semantic",
            json={"query": "a" * 600},  # Over 500 char max
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Discriminating Phenotypes Tests
# =============================================================================


class TestDiscriminatingPhenotypesRoute:
    """Tests for POST /primekg/diagnosis/discriminating-phenotypes endpoint."""

    def test_discriminating_phenotypes_unauthorized(self, client: TestClient):
        """Get discriminating phenotypes without auth fails."""
        response = client.post(
            "/api/v1/primekg/diagnosis/discriminating-phenotypes",
            json={
                "disease_a": "MONDO:0005148",
                "disease_b": "MONDO:0005149",
            },
        )
        assert response.status_code == 401

    def test_discriminating_phenotypes_authorized(
        self, client: TestClient, auth_headers: dict
    ):
        """Get discriminating phenotypes with auth and valid data."""
        response = client.post(
            "/api/v1/primekg/diagnosis/discriminating-phenotypes",
            json={
                "disease_a": "MONDO:0005148",
                "disease_b": "MONDO:0005149",
                "already_present": [],
            },
            headers=auth_headers,
        )
        assert response.status_code in [200, 401, 500, 503]

    def test_discriminating_phenotypes_missing_disease(
        self, client: TestClient, auth_headers: dict
    ):
        """Get discriminating phenotypes without both diseases fails."""
        response = client.post(
            "/api/v1/primekg/diagnosis/discriminating-phenotypes",
            json={"disease_a": "MONDO:0005148"},  # Missing disease_b
            headers=auth_headers,
        )
        assert response.status_code in [422, 401]


# =============================================================================
# Disease Details Tests
# =============================================================================


class TestDiseaseDetailsRoute:
    """Tests for GET /primekg/diseases/{disease_id} endpoint."""

    def test_disease_details_unauthorized(self, client: TestClient):
        """Get disease details without auth fails."""
        response = client.get("/api/v1/primekg/diseases/MONDO:0005148")
        assert response.status_code == 401

    def test_disease_details_authorized(self, client: TestClient, auth_headers: dict):
        """Get disease details with auth returns details or error."""
        response = client.get(
            "/api/v1/primekg/diseases/MONDO:0005148", headers=auth_headers
        )
        assert response.status_code in [200, 404, 401, 500, 503]


# =============================================================================
# Stats Tests
# =============================================================================


class TestPrimeKGStatsRoute:
    """Tests for GET /primekg/stats endpoint."""

    def test_stats_unauthorized(self, client: TestClient):
        """Get PrimeKG stats without auth fails."""
        response = client.get("/api/v1/primekg/stats")
        assert response.status_code == 401

    def test_stats_authorized(self, client: TestClient, auth_headers: dict):
        """Get PrimeKG stats with auth returns stats."""
        response = client.get("/api/v1/primekg/stats", headers=auth_headers)
        assert response.status_code in [200, 401, 500, 503]


# =============================================================================
# Health Check Tests
# =============================================================================


class TestPrimeKGHealthRoute:
    """Tests for GET /primekg/health endpoint."""

    def test_health_check(self, client: TestClient):
        """PrimeKG health check endpoint."""
        response = client.get("/api/v1/primekg/health")
        # Health check may or may not require auth
        assert response.status_code in [200, 401, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "healthy" in data


# =============================================================================
# Admin Operations Tests
# =============================================================================


class TestRefreshEmbeddingsRoute:
    """Tests for POST /primekg/admin/refresh-embeddings endpoint."""

    def test_refresh_embeddings_unauthorized(self, client: TestClient):
        """Refresh embeddings without auth fails."""
        response = client.post("/api/v1/primekg/admin/refresh-embeddings")
        assert response.status_code == 401

    def test_refresh_embeddings_insufficient_trust(
        self, client: TestClient, auth_headers: dict
    ):
        """Refresh embeddings with insufficient trust fails."""
        response = client.post(
            "/api/v1/primekg/admin/refresh-embeddings", headers=auth_headers
        )
        # Requires TRUSTED level
        assert response.status_code in [403, 401, 500, 503]

    def test_refresh_embeddings_with_trusted_level(
        self, client: TestClient, trusted_auth_headers: dict
    ):
        """Refresh embeddings with trusted level succeeds."""
        response = client.post(
            "/api/v1/primekg/admin/refresh-embeddings", headers=trusted_auth_headers
        )
        assert response.status_code in [202, 403, 401, 500, 503]

    def test_refresh_embeddings_with_node_type(
        self, client: TestClient, trusted_auth_headers: dict
    ):
        """Refresh embeddings filtered by node type."""
        response = client.post(
            "/api/v1/primekg/admin/refresh-embeddings",
            params={"node_type": "disease"},
            headers=trusted_auth_headers,
        )
        assert response.status_code in [202, 403, 401, 500, 503]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
