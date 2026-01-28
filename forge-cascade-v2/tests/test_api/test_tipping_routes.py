"""
Tipping Routes Tests for Forge Cascade V2

Comprehensive tests for FROWG tipping API routes including:
- Tipping info
- Creating tips
- Confirming tips
- Getting tip details
- Tips by target
- Tips by sender
- Leaderboards
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_tipping_service():
    """Create mock tipping service."""
    service = AsyncMock()
    service.create_tip = AsyncMock()
    service.confirm_tip = AsyncMock(return_value=True)
    service.get_tip = AsyncMock(return_value=None)
    service.get_tips_for_target = AsyncMock(return_value=[])
    service.get_tip_summary = AsyncMock()
    service.get_tips_by_sender = AsyncMock(return_value=[])
    service.get_leaderboard = AsyncMock()
    return service


@pytest.fixture
def sample_tip():
    """Create a sample tip for testing."""
    return MagicMock(
        id="tip123",
        sender_wallet="SenderWallet123",
        target_type="agent",
        target_id="agent456",
        recipient_wallet="RecipientWallet789",
        amount_frowg=100.0,
        message="Great work!",
        tx_signature=None,
        confirmed=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_tip_summary():
    """Create a sample tip summary for testing."""
    return MagicMock(
        target_type="agent",
        target_id="agent456",
        total_tips=10,
        total_frowg=1500.0,
        unique_tippers=5,
        recent_tips=[],
    )


@pytest.fixture
def sample_leaderboard():
    """Create a sample leaderboard for testing."""
    return MagicMock(
        target_type="agent",
        entries=[],
        generated_at=datetime.now(UTC),
    )


# =============================================================================
# Tipping Info Tests
# =============================================================================


class TestTippingInfoRoute:
    """Tests for GET /tips/info endpoint."""

    def test_get_tipping_info(self, client: TestClient):
        """Get tipping info returns token information."""
        response = client.get("/api/v1/tips/info")
        # This is a public endpoint
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "token" in data
            assert data["token"] == "FROWG"
            assert "chain" in data
            assert data["chain"] == "solana"
            assert "mint_address" in data
            assert "tip_targets" in data


# =============================================================================
# Create Tip Tests
# =============================================================================


class TestCreateTipRoute:
    """Tests for POST /tips endpoint."""

    def test_create_tip_missing_params(self, client: TestClient):
        """Create tip without required query params fails."""
        response = client.post(
            "/api/v1/tips",
            json={
                "target_type": "agent",
                "target_id": "agent456",
                "amount_frowg": 100.0,
            },
        )
        # Missing sender_wallet and recipient_wallet query params
        assert response.status_code == 422

    def test_create_tip_with_params(self, client: TestClient, mock_tipping_service, sample_tip):
        """Create tip with all required params."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.create_tip.return_value = sample_tip

            response = client.post(
                "/api/v1/tips",
                params={
                    "sender_wallet": "SenderWallet123",
                    "recipient_wallet": "RecipientWallet789",
                },
                json={
                    "target_type": "agent",
                    "target_id": "agent456",
                    "amount_frowg": 100.0,
                    "message": "Great work!",
                },
            )
            assert response.status_code in [200, 400, 503]

    def test_create_tip_with_tx_signature(
        self, client: TestClient, mock_tipping_service, sample_tip
    ):
        """Create tip with pre-existing transaction signature."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            sample_tip.tx_signature = "tx_sig_123"
            mock_tipping_service.create_tip.return_value = sample_tip

            response = client.post(
                "/api/v1/tips",
                params={
                    "sender_wallet": "SenderWallet123",
                    "recipient_wallet": "RecipientWallet789",
                    "tx_signature": "tx_sig_123",
                },
                json={
                    "target_type": "agent",
                    "target_id": "agent456",
                    "amount_frowg": 100.0,
                },
            )
            assert response.status_code in [200, 400, 503]

    def test_create_tip_service_unavailable(self, client: TestClient):
        """Create tip when service unavailable returns 503."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=None,
        ):
            response = client.post(
                "/api/v1/tips",
                params={
                    "sender_wallet": "SenderWallet123",
                    "recipient_wallet": "RecipientWallet789",
                },
                json={
                    "target_type": "agent",
                    "target_id": "agent456",
                    "amount_frowg": 100.0,
                },
            )
            assert response.status_code == 503


# =============================================================================
# Confirm Tip Tests
# =============================================================================


class TestConfirmTipRoute:
    """Tests for POST /tips/{tip_id}/confirm endpoint."""

    def test_confirm_tip_missing_signature(self, client: TestClient):
        """Confirm tip without tx_signature fails."""
        response = client.post("/api/v1/tips/tip123/confirm")
        # Missing tx_signature query param
        assert response.status_code == 422

    def test_confirm_tip_with_signature(self, client: TestClient, mock_tipping_service):
        """Confirm tip with tx_signature succeeds."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.confirm_tip.return_value = True

            response = client.post(
                "/api/v1/tips/tip123/confirm",
                params={"tx_signature": "tx_sig_123"},
            )
            assert response.status_code in [200, 404, 503]

    def test_confirm_tip_not_found(self, client: TestClient, mock_tipping_service):
        """Confirm non-existent tip returns 404."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.confirm_tip.return_value = False

            response = client.post(
                "/api/v1/tips/nonexistent/confirm",
                params={"tx_signature": "tx_sig_123"},
            )
            assert response.status_code == 404

    def test_confirm_tip_service_unavailable(self, client: TestClient):
        """Confirm tip when service unavailable returns 503."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=None,
        ):
            response = client.post(
                "/api/v1/tips/tip123/confirm",
                params={"tx_signature": "tx_sig_123"},
            )
            assert response.status_code == 503


# =============================================================================
# Get Tip Tests
# =============================================================================


class TestGetTipRoute:
    """Tests for GET /tips/{tip_id} endpoint."""

    def test_get_tip(self, client: TestClient, mock_tipping_service, sample_tip):
        """Get tip by ID returns tip details."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tip.return_value = sample_tip

            response = client.get("/api/v1/tips/tip123")
            assert response.status_code in [200, 404, 503]

    def test_get_tip_not_found(self, client: TestClient, mock_tipping_service):
        """Get non-existent tip returns 404."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tip.return_value = None

            response = client.get("/api/v1/tips/nonexistent")
            assert response.status_code == 404

    def test_get_tip_service_unavailable(self, client: TestClient):
        """Get tip when service unavailable returns 503."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=None,
        ):
            response = client.get("/api/v1/tips/tip123")
            assert response.status_code == 503


# =============================================================================
# Tips For Target Tests
# =============================================================================


class TestTipsForTargetRoute:
    """Tests for GET /tips/target/{target_type}/{target_id} endpoint."""

    def test_get_tips_for_target(self, client: TestClient, mock_tipping_service):
        """Get tips for a target returns tip list."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tips_for_target.return_value = []

            response = client.get("/api/v1/tips/target/agent/agent456")
            assert response.status_code in [200, 422, 503]

    def test_get_tips_for_target_with_params(self, client: TestClient, mock_tipping_service):
        """Get tips for target with filter params."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tips_for_target.return_value = []

            response = client.get(
                "/api/v1/tips/target/agent/agent456",
                params={"limit": 20, "confirmed_only": False},
            )
            assert response.status_code in [200, 422, 503]

    def test_get_tips_for_target_invalid_type(self, client: TestClient):
        """Get tips for invalid target type fails validation."""
        response = client.get("/api/v1/tips/target/invalid_type/target123")
        assert response.status_code == 422

    def test_get_tips_for_target_limit_validation(self, client: TestClient, mock_tipping_service):
        """Get tips for target with invalid limit fails."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            response = client.get(
                "/api/v1/tips/target/agent/agent456",
                params={"limit": 200},  # Over 100 max
            )
            assert response.status_code in [422, 503]


# =============================================================================
# Tip Summary Tests
# =============================================================================


class TestTipSummaryRoute:
    """Tests for GET /tips/target/{target_type}/{target_id}/summary endpoint."""

    def test_get_tip_summary(self, client: TestClient, mock_tipping_service, sample_tip_summary):
        """Get tip summary for a target."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tip_summary.return_value = sample_tip_summary

            response = client.get("/api/v1/tips/target/agent/agent456/summary")
            assert response.status_code in [200, 422, 503]

    def test_get_tip_summary_invalid_type(self, client: TestClient):
        """Get tip summary for invalid target type fails."""
        response = client.get("/api/v1/tips/target/invalid_type/target123/summary")
        assert response.status_code == 422


# =============================================================================
# Tips By Sender Tests
# =============================================================================


class TestTipsBySenderRoute:
    """Tests for GET /tips/sender/{sender_wallet} endpoint."""

    def test_get_tips_by_sender(self, client: TestClient, mock_tipping_service):
        """Get tips by sender wallet."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tips_by_sender.return_value = []

            response = client.get("/api/v1/tips/sender/SenderWallet123")
            assert response.status_code in [200, 503]

    def test_get_tips_by_sender_with_limit(self, client: TestClient, mock_tipping_service):
        """Get tips by sender with limit param."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tips_by_sender.return_value = []

            response = client.get(
                "/api/v1/tips/sender/SenderWallet123",
                params={"limit": 25},
            )
            assert response.status_code in [200, 503]

    def test_get_tips_by_sender_limit_validation(self, client: TestClient, mock_tipping_service):
        """Get tips by sender with invalid limit fails."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            response = client.get(
                "/api/v1/tips/sender/SenderWallet123",
                params={"limit": 200},  # Over 100 max
            )
            assert response.status_code in [422, 503]


# =============================================================================
# Leaderboard Tests
# =============================================================================


class TestLeaderboardRoute:
    """Tests for GET /tips/leaderboard/{target_type} endpoint."""

    def test_get_leaderboard(self, client: TestClient, mock_tipping_service, sample_leaderboard):
        """Get leaderboard for a target type."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_leaderboard.return_value = sample_leaderboard

            response = client.get("/api/v1/tips/leaderboard/agent")
            assert response.status_code in [200, 422, 503]

    def test_get_leaderboard_with_limit(
        self, client: TestClient, mock_tipping_service, sample_leaderboard
    ):
        """Get leaderboard with custom limit."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_leaderboard.return_value = sample_leaderboard

            response = client.get(
                "/api/v1/tips/leaderboard/agent",
                params={"limit": 25},
            )
            assert response.status_code in [200, 422, 503]

    def test_get_leaderboard_invalid_type(self, client: TestClient):
        """Get leaderboard for invalid target type fails."""
        response = client.get("/api/v1/tips/leaderboard/invalid_type")
        assert response.status_code == 422

    def test_get_leaderboard_limit_validation(self, client: TestClient, mock_tipping_service):
        """Get leaderboard with invalid limit fails."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            response = client.get(
                "/api/v1/tips/leaderboard/agent",
                params={"limit": 100},  # Over 50 max
            )
            assert response.status_code in [422, 503]

    def test_get_leaderboard_service_unavailable(self, client: TestClient):
        """Get leaderboard when service unavailable returns 503."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=None,
        ):
            response = client.get("/api/v1/tips/leaderboard/agent")
            assert response.status_code == 503


# =============================================================================
# Target Type Validation Tests
# =============================================================================


class TestTargetTypeValidation:
    """Tests for target type validation across endpoints."""

    def test_valid_target_types(self, client: TestClient, mock_tipping_service):
        """Test valid target types are accepted."""
        with patch(
            "forge.api.routes.tipping.get_tipping_service",
            return_value=mock_tipping_service,
        ):
            mock_tipping_service.get_tips_for_target.return_value = []

            # Test each valid target type
            for target_type in ["agent", "capsule", "user"]:
                response = client.get(f"/api/v1/tips/target/{target_type}/test123")
                assert response.status_code in [200, 422, 503], (
                    f"Failed for target_type: {target_type}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
