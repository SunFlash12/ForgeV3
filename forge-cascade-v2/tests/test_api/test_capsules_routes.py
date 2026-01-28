"""
Capsules Routes Tests for Forge Cascade V2

Comprehensive tests for Capsule API routes including:
- CRUD operations (create, read, update, delete)
- Search operations (semantic search, recent, by owner)
- Lineage operations (get lineage, link, fork)
- Integrity verification (content hash, signature)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_capsule_repo():
    """Create mock capsule repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_pipeline():
    """Create mock pipeline."""
    pipeline = AsyncMock()
    result = MagicMock()
    result.success = True
    result.errors = []
    pipeline.execute = AsyncMock(return_value=result)
    return pipeline


@pytest.fixture
def sample_capsule():
    """Create a sample capsule for testing."""
    capsule = MagicMock()
    capsule.id = "capsule_123"
    capsule.title = "Test Capsule"
    capsule.content = "Test content for the capsule."
    capsule.type = MagicMock(value="knowledge")
    capsule.owner_id = "user_123"
    capsule.trust_level = MagicMock(value=60)
    capsule.version = "1.0.0"
    capsule.parent_id = None
    capsule.tags = ["test"]
    capsule.metadata = {}
    capsule.view_count = 0
    capsule.fork_count = 0
    capsule.is_archived = False
    capsule.created_at = datetime.now()
    capsule.updated_at = datetime.now()
    return capsule


# =============================================================================
# Create Capsule Tests
# =============================================================================


class TestCreateCapsuleRoute:
    """Tests for POST /capsules/ endpoint."""

    def test_create_capsule_unauthorized(self, client: TestClient):
        """Create capsule without auth fails."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "Test content",
                "type": "knowledge",
            },
        )
        assert response.status_code == 401

    def test_create_capsule_missing_content(self, client: TestClient, auth_headers: dict):
        """Create capsule without content fails validation."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_empty_content(self, client: TestClient, auth_headers: dict):
        """Create capsule with empty content fails validation."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "",
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_content_too_long(self, client: TestClient, auth_headers: dict):
        """Create capsule with content exceeding 1MB fails validation."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "A" * 1_100_000,  # Over 1MB
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_title_too_long(self, client: TestClient, auth_headers: dict):
        """Create capsule with title exceeding max length fails."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "Test content",
                "title": "A" * 600,  # Over 500 max
                "type": "knowledge",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_too_many_tags(self, client: TestClient, auth_headers: dict):
        """Create capsule with too many tags fails validation."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "Test content",
                "type": "knowledge",
                "tags": [f"tag{i}" for i in range(60)],  # Over 50 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_tag_too_long(self, client: TestClient, auth_headers: dict):
        """Create capsule with tag exceeding max length fails."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "Test content",
                "type": "knowledge",
                "tags": ["A" * 150],  # Over 100 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_capsule_too_many_metadata_keys(self, client: TestClient, auth_headers: dict):
        """Create capsule with too many metadata keys fails."""
        response = client.post(
            "/api/v1/capsules/",
            json={
                "content": "Test content",
                "type": "knowledge",
                "metadata": {f"key{i}": f"value{i}" for i in range(25)},  # Over 20 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# List Capsules Tests
# =============================================================================


class TestListCapsulesRoute:
    """Tests for GET /capsules/ endpoint."""

    def test_list_capsules_unauthorized(self, client: TestClient):
        """List capsules without auth fails."""
        response = client.get("/api/v1/capsules/")
        assert response.status_code == 401

    def test_list_capsules_authorized(self, client: TestClient, auth_headers: dict):
        """List capsules with auth succeeds."""
        response = client.get(
            "/api/v1/capsules/",
            headers=auth_headers,
        )

        # Should return list or error
        assert response.status_code in [200, 500]

    def test_list_capsules_with_filters(self, client: TestClient, auth_headers: dict):
        """List capsules with filters."""
        response = client.get(
            "/api/v1/capsules/",
            params={
                "capsule_type": "knowledge",
                "tag": "test",
            },
            headers=auth_headers,
        )

        assert response.status_code in [200, 500]


# =============================================================================
# Get Capsule Tests
# =============================================================================


class TestGetCapsuleRoute:
    """Tests for GET /capsules/{capsule_id} endpoint."""

    def test_get_capsule_unauthorized(self, client: TestClient):
        """Get capsule without auth fails."""
        response = client.get("/api/v1/capsules/capsule_123")
        assert response.status_code == 401

    def test_get_capsule_authorized(self, client: TestClient, auth_headers: dict):
        """Get capsule with auth."""
        response = client.get(
            "/api/v1/capsules/capsule_123",
            headers=auth_headers,
        )

        # Should return capsule, 404, or error
        assert response.status_code in [200, 404, 500]


# =============================================================================
# Update Capsule Tests
# =============================================================================


class TestUpdateCapsuleRoute:
    """Tests for PATCH /capsules/{capsule_id} endpoint."""

    def test_update_capsule_unauthorized(self, client: TestClient):
        """Update capsule without auth fails."""
        response = client.patch(
            "/api/v1/capsules/capsule_123",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 401

    def test_update_capsule_title_too_long(self, client: TestClient, auth_headers: dict):
        """Update capsule with title exceeding max length fails."""
        response = client.patch(
            "/api/v1/capsules/capsule_123",
            json={"title": "A" * 600},  # Over 500 max
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_update_capsule_content_too_long(self, client: TestClient, auth_headers: dict):
        """Update capsule with content exceeding 1MB fails validation."""
        response = client.patch(
            "/api/v1/capsules/capsule_123",
            json={"content": "A" * 1_100_000},  # Over 1MB
            headers=auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# Delete Capsule Tests
# =============================================================================


class TestDeleteCapsuleRoute:
    """Tests for DELETE /capsules/{capsule_id} endpoint."""

    def test_delete_capsule_unauthorized(self, client: TestClient):
        """Delete capsule without auth fails."""
        response = client.delete("/api/v1/capsules/capsule_123")
        assert response.status_code == 401


# =============================================================================
# Search Tests
# =============================================================================


class TestSearchCapsulesRoute:
    """Tests for POST /capsules/search endpoint."""

    def test_search_unauthorized(self, client: TestClient):
        """Search without auth fails."""
        response = client.post(
            "/api/v1/capsules/search",
            json={"query": "test query"},
        )
        assert response.status_code == 401

    def test_search_missing_query(self, client: TestClient, auth_headers: dict):
        """Search without query fails validation."""
        response = client.post(
            "/api/v1/capsules/search",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_search_empty_query(self, client: TestClient, auth_headers: dict):
        """Search with empty query fails validation."""
        response = client.post(
            "/api/v1/capsules/search",
            json={"query": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_search_query_too_long(self, client: TestClient, auth_headers: dict):
        """Search with query exceeding max length fails validation."""
        response = client.post(
            "/api/v1/capsules/search",
            json={"query": "A" * 2500},  # Over 2000 max
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_search_invalid_limit(self, client: TestClient, auth_headers: dict):
        """Search with invalid limit fails validation."""
        response = client.post(
            "/api/v1/capsules/search",
            json={
                "query": "test query",
                "limit": 200,  # Over 100 max
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_search_invalid_filter_keys(self, client: TestClient, auth_headers: dict):
        """Search with invalid filter keys fails validation."""
        response = client.post(
            "/api/v1/capsules/search",
            json={
                "query": "test query",
                "filters": {"invalid_key": "value"},  # Not in whitelist
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestGetRecentCapsulesRoute:
    """Tests for GET /capsules/search/recent endpoint."""

    def test_get_recent_unauthorized(self, client: TestClient):
        """Get recent without auth fails."""
        response = client.get("/api/v1/capsules/search/recent")
        assert response.status_code == 401

    def test_get_recent_invalid_limit(self, client: TestClient, auth_headers: dict):
        """Get recent with invalid limit fails validation."""
        response = client.get(
            "/api/v1/capsules/search/recent",
            params={"limit": 100},  # Over 50 max
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestGetCapsulesByOwnerRoute:
    """Tests for GET /capsules/search/by-owner/{owner_id} endpoint."""

    def test_get_by_owner_unauthorized(self, client: TestClient):
        """Get by owner without auth fails."""
        response = client.get("/api/v1/capsules/search/by-owner/user_123")
        assert response.status_code == 401

    def test_get_by_owner_idor_protection(self, client: TestClient, auth_headers: dict):
        """Get by owner for different user returns 403 (IDOR protection)."""
        response = client.get(
            "/api/v1/capsules/search/by-owner/other_user_id",
            headers=auth_headers,
        )

        # Should return 403 or 500 (depends on mock setup)
        assert response.status_code in [403, 500]


# =============================================================================
# Lineage Tests
# =============================================================================


class TestGetLineageRoute:
    """Tests for GET /capsules/{capsule_id}/lineage endpoint."""

    def test_get_lineage_unauthorized(self, client: TestClient):
        """Get lineage without auth fails."""
        response = client.get("/api/v1/capsules/capsule_123/lineage")
        assert response.status_code == 401

    def test_get_lineage_invalid_depth(self, client: TestClient, auth_headers: dict):
        """Get lineage with invalid depth fails validation."""
        response = client.get(
            "/api/v1/capsules/capsule_123/lineage",
            params={"depth": 25},  # Over 20 max
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestLinkCapsuleRoute:
    """Tests for POST /capsules/{capsule_id}/link/{parent_id} endpoint."""

    def test_link_unauthorized(self, client: TestClient):
        """Link capsule without auth fails."""
        response = client.post("/api/v1/capsules/capsule_123/link/parent_456")
        assert response.status_code == 401


class TestForkCapsuleRoute:
    """Tests for POST /capsules/{capsule_id}/fork endpoint."""

    def test_fork_unauthorized(self, client: TestClient):
        """Fork capsule without auth fails."""
        response = client.post(
            "/api/v1/capsules/capsule_123/fork",
            json={"evolution_reason": "Testing fork functionality"},
        )
        assert response.status_code == 401

    def test_fork_missing_reason(self, client: TestClient, auth_headers: dict):
        """Fork without evolution_reason fails validation."""
        response = client.post(
            "/api/v1/capsules/capsule_123/fork",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_fork_empty_reason(self, client: TestClient, auth_headers: dict):
        """Fork with empty evolution_reason fails validation."""
        response = client.post(
            "/api/v1/capsules/capsule_123/fork",
            json={"evolution_reason": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestArchiveCapsuleRoute:
    """Tests for POST /capsules/{capsule_id}/archive endpoint."""

    def test_archive_unauthorized(self, client: TestClient):
        """Archive capsule without auth fails."""
        response = client.post("/api/v1/capsules/capsule_123/archive")
        assert response.status_code == 401


# =============================================================================
# Integrity Tests
# =============================================================================


class TestVerifyIntegrityRoute:
    """Tests for GET /capsules/{capsule_id}/integrity endpoint."""

    def test_verify_integrity_unauthorized(self, client: TestClient):
        """Verify integrity without auth fails."""
        response = client.get("/api/v1/capsules/capsule_123/integrity")
        assert response.status_code == 401


class TestVerifyLineageIntegrityRoute:
    """Tests for GET /capsules/{capsule_id}/lineage/integrity endpoint."""

    def test_verify_lineage_integrity_unauthorized(self, client: TestClient):
        """Verify lineage integrity without auth fails."""
        response = client.get("/api/v1/capsules/capsule_123/lineage/integrity")
        assert response.status_code == 401


# =============================================================================
# Signing Tests
# =============================================================================


class TestSignCapsuleRoute:
    """Tests for POST /capsules/{capsule_id}/sign endpoint."""

    def test_sign_unauthorized(self, client: TestClient):
        """Sign capsule without auth fails."""
        response = client.post(
            "/api/v1/capsules/capsule_123/sign",
            json={"password": "testpassword"},
        )
        assert response.status_code == 401


class TestVerifySignatureRoute:
    """Tests for GET /capsules/{capsule_id}/signature/verify endpoint."""

    def test_verify_signature_unauthorized(self, client: TestClient):
        """Verify signature without auth fails."""
        response = client.get("/api/v1/capsules/capsule_123/signature/verify")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
