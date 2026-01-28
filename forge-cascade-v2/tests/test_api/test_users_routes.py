"""
Users Routes Tests for Forge Cascade V2

Comprehensive tests for users API routes including:
- User search
- User listing (admin)
- User profile retrieval
- User capsules and activity
- Trust level management
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from forge.models.user import AuthProvider, User, UserRole

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return User(
        id="user123",
        username="testuser",
        email="test@example.com",
        display_name="Test User",
        role=UserRole.USER,
        trust_flame=60,
        is_active=True,
        is_verified=True,
        auth_provider=AuthProvider.LOCAL,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def admin_user():
    """Create admin user for testing."""
    return User(
        id="admin123",
        username="adminuser",
        email="admin@example.com",
        display_name="Admin User",
        role=UserRole.ADMIN,
        trust_flame=100,
        is_active=True,
        is_verified=True,
        auth_provider=AuthProvider.LOCAL,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


# =============================================================================
# User Search Tests
# =============================================================================


class TestUserSearchRoute:
    """Tests for GET /users/search endpoint."""

    def test_search_unauthorized(self, client: TestClient):
        """Search without auth fails."""
        response = client.get("/api/v1/users/search", params={"q": "test"})

        assert response.status_code == 401

    def test_search_missing_query(self, client: TestClient, auth_headers: dict):
        """Search without query fails validation."""
        response = client.get("/api/v1/users/search", headers=auth_headers)

        assert response.status_code == 422

    def test_search_empty_query(self, client: TestClient, auth_headers: dict):
        """Search with empty query fails validation."""
        response = client.get("/api/v1/users/search", params={"q": ""}, headers=auth_headers)

        assert response.status_code == 422

    def test_search_query_too_long(self, client: TestClient, auth_headers: dict):
        """Search with too long query fails validation."""
        response = client.get(
            "/api/v1/users/search",
            params={"q": "a" * 150},  # Over 100 max
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_search_valid_query(self, client: TestClient, auth_headers: dict):
        """Search with valid query succeeds (mocked DB returns empty)."""
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test"},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text[:200]}"
        )

        data = response.json()
        assert "users" in data

    def test_search_with_limit(self, client: TestClient, auth_headers: dict):
        """Search with custom limit succeeds."""
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test", "limit": 5},
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text[:200]}"
        )

    def test_search_limit_too_high(self, client: TestClient, auth_headers: dict):
        """Search with limit exceeding max fails."""
        response = client.get(
            "/api/v1/users/search",
            params={"q": "test", "limit": 200},  # Over 100 max
            headers=auth_headers,
        )

        assert response.status_code == 422


# =============================================================================
# User List Tests (Admin)
# =============================================================================


class TestUserListRoute:
    """Tests for GET /users endpoint (admin only)."""

    def test_list_unauthorized(self, client: TestClient):
        """List users without auth fails."""
        response = client.get("/api/v1/users/")

        assert response.status_code == 401

    def test_list_non_admin(self, client: TestClient, auth_headers: dict):
        """List users as non-admin - depends on implementation."""
        response = client.get("/api/v1/users/", headers=auth_headers)

        # Non-admin may get 200 (allowed) or 403 (forbidden) depending on policy
        assert response.status_code in [200, 403], (
            f"Expected 200 or 403, got {response.status_code}: {response.text[:200]}"
        )

    def test_list_pagination(self, client: TestClient, auth_headers: dict):
        """List users with pagination parameters."""
        response = client.get(
            "/api/v1/users/",
            params={"page": 1, "per_page": 10},
            headers=auth_headers,
        )

        assert response.status_code in [200, 403], (
            f"Expected 200 or 403, got {response.status_code}: {response.text[:200]}"
        )

    def test_list_page_too_high(self, client: TestClient, auth_headers: dict):
        """List users with page exceeding max fails."""
        response = client.get(
            "/api/v1/users/",
            params={"page": 20000},  # Over 10000 max
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]

    def test_list_per_page_too_high(self, client: TestClient, auth_headers: dict):
        """List users with per_page exceeding max fails."""
        response = client.get(
            "/api/v1/users/",
            params={"per_page": 200},  # Over 100 max
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]

    def test_list_filter_by_role(self, client: TestClient, auth_headers: dict):
        """List users filtered by role parameter."""
        response = client.get(
            "/api/v1/users/",
            params={"role": "user"},
            headers=auth_headers,
        )

        assert response.status_code in [200, 403], (
            f"Expected 200 or 403, got {response.status_code}: {response.text[:200]}"
        )


# =============================================================================
# Get User By ID Tests
# =============================================================================


class TestGetUserRoute:
    """Tests for GET /users/{user_id} endpoint."""

    def test_get_user_unauthorized(self, client: TestClient):
        """Get user without auth fails."""
        response = client.get("/api/v1/users/user123")

        assert response.status_code == 401

    def test_get_nonexistent_user(self, client: TestClient, auth_headers: dict):
        """Get nonexistent user returns 403 or 404."""
        response = client.get(
            "/api/v1/users/nonexistent123",
            headers=auth_headers,
        )

        # 403 (access denied) or 404 (not found) are valid responses
        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_get_other_user_as_regular(self, client: TestClient, auth_headers: dict):
        """Regular user cannot view other user's profile - IDOR protection."""
        response = client.get(
            "/api/v1/users/other_user_id",
            headers=auth_headers,
        )

        # Regular users should get 403 (forbidden) or 404 (not found)
        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )


# =============================================================================
# User Capsules Tests
# =============================================================================


class TestUserCapsulesRoute:
    """Tests for GET /users/{user_id}/capsules endpoint."""

    def test_get_capsules_unauthorized(self, client: TestClient):
        """Get user capsules without auth fails."""
        response = client.get("/api/v1/users/user123/capsules")

        assert response.status_code == 401

    def test_get_capsules_other_user(self, client: TestClient, auth_headers: dict):
        """Regular user cannot view other user's capsules - IDOR protection."""
        response = client.get(
            "/api/v1/users/other_user_id/capsules",
            headers=auth_headers,
        )

        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_get_capsules_with_limit(self, client: TestClient, auth_headers: dict):
        """Get capsules with custom limit parameter."""
        response = client.get(
            "/api/v1/users/user123/capsules",
            params={"limit": 5},
            headers=auth_headers,
        )

        assert response.status_code in [200, 403, 404], (
            f"Expected 200, 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_get_capsules_limit_too_high(self, client: TestClient, auth_headers: dict):
        """Get capsules with limit exceeding max fails."""
        response = client.get(
            "/api/v1/users/user123/capsules",
            params={"limit": 100},  # Over 50 max
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]


# =============================================================================
# User Activity Tests
# =============================================================================


class TestUserActivityRoute:
    """Tests for GET /users/{user_id}/activity endpoint."""

    def test_get_activity_unauthorized(self, client: TestClient):
        """Get user activity without auth fails."""
        response = client.get("/api/v1/users/user123/activity")

        assert response.status_code == 401

    def test_get_activity_other_user(self, client: TestClient, auth_headers: dict):
        """Regular user cannot view other user's activity - IDOR protection."""
        response = client.get(
            "/api/v1/users/other_user_id/activity",
            headers=auth_headers,
        )

        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_get_activity_with_limit(self, client: TestClient, auth_headers: dict):
        """Get activity with custom limit parameter."""
        response = client.get(
            "/api/v1/users/user123/activity",
            params={"limit": 10},
            headers=auth_headers,
        )

        assert response.status_code in [200, 403, 404], (
            f"Expected 200, 403 or 404, got {response.status_code}: {response.text[:200]}"
        )


# =============================================================================
# User Governance Tests
# =============================================================================


class TestUserGovernanceRoute:
    """Tests for GET /users/{user_id}/governance endpoint."""

    def test_get_governance_unauthorized(self, client: TestClient):
        """Get user governance without auth fails."""
        response = client.get("/api/v1/users/user123/governance")

        assert response.status_code == 401

    def test_get_governance_other_user(self, client: TestClient, auth_headers: dict):
        """Regular user cannot view other user's governance - IDOR protection."""
        response = client.get(
            "/api/v1/users/other_user_id/governance",
            headers=auth_headers,
        )

        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )


# =============================================================================
# Admin Update User Tests
# =============================================================================


class TestAdminUpdateUserRoute:
    """Tests for PATCH /users/{user_id} endpoint (admin only)."""

    def test_update_unauthorized(self, client: TestClient):
        """Update user without auth fails."""
        response = client.patch(
            "/api/v1/users/user123",
            json={
                "trust_flame": 80,
            },
        )

        assert response.status_code == 401

    def test_update_non_admin(self, client: TestClient, auth_headers: dict):
        """Update user as non-admin fails with 403."""
        response = client.patch(
            "/api/v1/users/user123",
            json={"trust_flame": 80},
            headers=auth_headers,
        )

        assert response.status_code == 403, (
            f"Expected 403, got {response.status_code}: {response.text[:200]}"
        )

    def test_update_no_changes(self, client: TestClient, auth_headers: dict):
        """Update user with empty payload fails."""
        response = client.patch(
            "/api/v1/users/user123",
            json={},
            headers=auth_headers,
        )

        # 400 (bad request - no changes) or 403 (non-admin)
        assert response.status_code in [400, 403], (
            f"Expected 400 or 403, got {response.status_code}: {response.text[:200]}"
        )

    def test_update_invalid_trust_flame(self, client: TestClient, auth_headers: dict):
        """Update user with invalid trust_flame fails."""
        response = client.patch(
            "/api/v1/users/user123",
            json={"trust_flame": 150},  # Over 100 max
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]


# =============================================================================
# Update Trust Level Tests
# =============================================================================


class TestUpdateTrustRoute:
    """Tests for PUT /users/{user_id}/trust endpoint (admin only)."""

    def test_update_trust_unauthorized(self, client: TestClient):
        """Update trust without auth fails."""
        response = client.put(
            "/api/v1/users/user123/trust",
            json={
                "trust_flame": 80,
                "reason": "Good behavior in the community",
            },
        )

        assert response.status_code == 401

    def test_update_trust_non_admin(self, client: TestClient, auth_headers: dict):
        """Update trust as non-admin fails with 403."""
        response = client.put(
            "/api/v1/users/user123/trust",
            json={"trust_flame": 80, "reason": "Good behavior"},
            headers=auth_headers,
        )

        assert response.status_code == 403, (
            f"Expected 403, got {response.status_code}: {response.text[:200]}"
        )

    def test_update_trust_missing_reason(self, client: TestClient, auth_headers: dict):
        """Update trust without reason fails."""
        response = client.put(
            "/api/v1/users/user123/trust",
            json={"trust_flame": 80},
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]

    def test_update_trust_reason_too_short(self, client: TestClient, auth_headers: dict):
        """Update trust with too short reason fails."""
        response = client.put(
            "/api/v1/users/user123/trust",
            json={"trust_flame": 80, "reason": "Hi"},  # Under 5 min
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]

    def test_update_trust_invalid_value(self, client: TestClient, auth_headers: dict):
        """Update trust with invalid value fails."""
        response = client.put(
            "/api/v1/users/user123/trust",
            json={"trust_flame": -10, "reason": "Some reason here"},
            headers=auth_headers,
        )

        assert response.status_code in [403, 422]


# =============================================================================
# IDOR Protection Tests
# =============================================================================


class TestIDORProtection:
    """Tests for IDOR (Insecure Direct Object Reference) protection."""

    def test_cannot_access_other_user_capsules(self, client: TestClient, auth_headers: dict):
        """User cannot access another user's capsules - IDOR protection."""
        response = client.get(
            "/api/v1/users/different_user_id/capsules",
            headers=auth_headers,
        )

        # Must be 403 (forbidden) or 404 (not found), never 200
        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_cannot_access_other_user_activity(self, client: TestClient, auth_headers: dict):
        """User cannot access another user's activity - IDOR protection."""
        response = client.get(
            "/api/v1/users/different_user_id/activity",
            headers=auth_headers,
        )

        # Must be 403 (forbidden) or 404 (not found), never 200
        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )

    def test_cannot_access_other_user_governance(self, client: TestClient, auth_headers: dict):
        """User cannot access another user's governance data - IDOR protection."""
        response = client.get(
            "/api/v1/users/different_user_id/governance",
            headers=auth_headers,
        )

        # Must be 403 (forbidden) or 404 (not found), never 200
        assert response.status_code in [403, 404], (
            f"Expected 403 or 404, got {response.status_code}: {response.text[:200]}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
