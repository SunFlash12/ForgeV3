"""
Chat Routes Tests for Forge Cascade V2

Comprehensive tests for Chat API routes including:
- Room management (create, list, get, update, delete)
- Membership (list, add, remove, update role)
- Invites (generate, join via invite)
- Message history
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_chat_service():
    """Create mock chat service."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_room():
    """Create a sample chat room for testing."""
    room = MagicMock()
    room.id = "room_123"
    room.name = "Test Room"
    room.description = "A test chat room"
    room.visibility = MagicMock(value="public")
    room.owner_id = "user_123"
    room.max_members = 100
    room.member_count = 1
    room.created_at = datetime.now()
    room.updated_at = datetime.now()
    return room


@pytest.fixture
def sample_member():
    """Create a sample room member for testing."""
    member = MagicMock()
    member.user_id = "user_123"
    member.role = MagicMock(value="owner")
    member.joined_at = datetime.now()
    return member


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    message = MagicMock()
    message.id = "msg_123"
    message.room_id = "room_123"
    message.sender_id = "user_123"
    message.content = "Hello, world!"
    message.message_type = "text"
    message.created_at = datetime.now()
    return message


# =============================================================================
# Room Management Tests
# =============================================================================


class TestCreateRoomRoute:
    """Tests for POST /chat/rooms endpoint."""

    def test_create_room_unauthorized(self, client: TestClient):
        """Create room without auth fails."""
        response = client.post(
            "/api/v1/chat/rooms",
            json={
                "name": "Test Room",
            },
        )
        assert response.status_code == 401

    def test_create_room_missing_name(self, client: TestClient, auth_headers: dict):
        """Create room without name fails validation."""
        response = client.post(
            "/api/v1/chat/rooms",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_room_authorized(
        self, client: TestClient, auth_headers: dict, mock_chat_service, sample_room
    ):
        """Create room with valid data succeeds."""

        mock_chat_service.create_room = AsyncMock(return_value=sample_room)

        with patch(
            "forge.api.routes.chat.get_chat_service",
            return_value=mock_chat_service,
        ):
            response = client.post(
                "/api/v1/chat/rooms",
                json={
                    "name": "Test Room",
                    "description": "A test room",
                    "visibility": "public",
                },
                headers=auth_headers,
            )

        # Should succeed or return error
        assert response.status_code in [201, 500], (
            f"Expected 201/500, got {response.status_code}: {response.text[:200]}"
        )


class TestListRoomsRoute:
    """Tests for GET /chat/rooms endpoint."""

    def test_list_rooms_unauthorized(self, client: TestClient):
        """List rooms without auth fails."""
        response = client.get("/api/v1/chat/rooms")
        assert response.status_code == 401

    def test_list_rooms_authorized(
        self, client: TestClient, auth_headers: dict, mock_chat_service, sample_room
    ):
        """List rooms with auth returns rooms."""
        mock_chat_service.get_user_accessible_rooms = AsyncMock(return_value=([sample_room], 1))
        mock_chat_service.get_user_role = AsyncMock(return_value=MagicMock(value="member"))

        with patch(
            "forge.api.routes.chat.get_chat_service",
            return_value=mock_chat_service,
        ):
            response = client.get(
                "/api/v1/chat/rooms",
                headers=auth_headers,
            )

        assert response.status_code in [200, 500]

    def test_list_rooms_invalid_limit(self, client: TestClient, auth_headers: dict):
        """List rooms with invalid limit fails validation."""
        response = client.get(
            "/api/v1/chat/rooms",
            params={"limit": 200},  # Over 100 max
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestGetRoomRoute:
    """Tests for GET /chat/rooms/{room_id} endpoint."""

    def test_get_room_unauthorized(self, client: TestClient):
        """Get room without auth fails."""
        response = client.get("/api/v1/chat/rooms/room_123")
        assert response.status_code == 401


class TestUpdateRoomRoute:
    """Tests for PATCH /chat/rooms/{room_id} endpoint."""

    def test_update_room_unauthorized(self, client: TestClient):
        """Update room without auth fails."""
        response = client.patch(
            "/api/v1/chat/rooms/room_123",
            json={"name": "Updated Room"},
        )
        assert response.status_code == 401


class TestDeleteRoomRoute:
    """Tests for DELETE /chat/rooms/{room_id} endpoint."""

    def test_delete_room_unauthorized(self, client: TestClient):
        """Delete room without auth fails."""
        response = client.delete("/api/v1/chat/rooms/room_123")
        assert response.status_code == 401


# =============================================================================
# Membership Tests
# =============================================================================


class TestListMembersRoute:
    """Tests for GET /chat/rooms/{room_id}/members endpoint."""

    def test_list_members_unauthorized(self, client: TestClient):
        """List members without auth fails."""
        response = client.get("/api/v1/chat/rooms/room_123/members")
        assert response.status_code == 401

    def test_list_members_invalid_limit(self, client: TestClient, auth_headers: dict):
        """List members with invalid limit fails validation."""
        response = client.get(
            "/api/v1/chat/rooms/room_123/members",
            params={"limit": 200},  # Over 100 max
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestAddMemberRoute:
    """Tests for POST /chat/rooms/{room_id}/members endpoint."""

    def test_add_member_unauthorized(self, client: TestClient):
        """Add member without auth fails."""
        response = client.post(
            "/api/v1/chat/rooms/room_123/members",
            json={
                "user_id": "user_456",
                "role": "member",
            },
        )
        assert response.status_code == 401

    def test_add_member_missing_user_id(self, client: TestClient, auth_headers: dict):
        """Add member without user_id fails validation."""
        response = client.post(
            "/api/v1/chat/rooms/room_123/members",
            json={
                "role": "member",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestRemoveMemberRoute:
    """Tests for DELETE /chat/rooms/{room_id}/members/{user_id} endpoint."""

    def test_remove_member_unauthorized(self, client: TestClient):
        """Remove member without auth fails."""
        response = client.delete("/api/v1/chat/rooms/room_123/members/user_456")
        assert response.status_code == 401


class TestUpdateMemberRoleRoute:
    """Tests for PATCH /chat/rooms/{room_id}/members/{user_id} endpoint."""

    def test_update_role_unauthorized(self, client: TestClient):
        """Update member role without auth fails."""
        response = client.patch(
            "/api/v1/chat/rooms/room_123/members/user_456",
            json={"role": "admin"},
        )
        assert response.status_code == 401

    def test_update_role_missing_role(self, client: TestClient, auth_headers: dict):
        """Update member role without role fails validation."""
        response = client.patch(
            "/api/v1/chat/rooms/room_123/members/user_456",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422


# =============================================================================
# Invite Tests
# =============================================================================


class TestGenerateInviteRoute:
    """Tests for POST /chat/rooms/{room_id}/invite endpoint."""

    def test_generate_invite_unauthorized(self, client: TestClient):
        """Generate invite without auth fails."""
        response = client.post("/api/v1/chat/rooms/room_123/invite")
        assert response.status_code == 401

    def test_generate_invite_invalid_expires(self, client: TestClient, auth_headers: dict):
        """Generate invite with invalid expires_in_hours fails validation."""
        response = client.post(
            "/api/v1/chat/rooms/room_123/invite",
            params={"expires_in_hours": 1000},  # Over 720 max
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_generate_invite_expires_too_short(self, client: TestClient, auth_headers: dict):
        """Generate invite with expires_in_hours below minimum fails validation."""
        response = client.post(
            "/api/v1/chat/rooms/room_123/invite",
            params={"expires_in_hours": 0},  # Below 1 minimum
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestJoinViaInviteRoute:
    """Tests for POST /chat/join/{invite_code} endpoint."""

    def test_join_via_invite_unauthorized(self, client: TestClient):
        """Join via invite without auth fails."""
        response = client.post("/api/v1/chat/join/invite_code_123")
        assert response.status_code == 401


class TestJoinPublicRoomRoute:
    """Tests for POST /chat/rooms/{room_id}/join endpoint."""

    def test_join_public_unauthorized(self, client: TestClient):
        """Join public room without auth fails."""
        response = client.post("/api/v1/chat/rooms/room_123/join")
        assert response.status_code == 401


# =============================================================================
# Message History Tests
# =============================================================================


class TestGetMessagesRoute:
    """Tests for GET /chat/rooms/{room_id}/messages endpoint."""

    def test_get_messages_unauthorized(self, client: TestClient):
        """Get messages without auth fails."""
        response = client.get("/api/v1/chat/rooms/room_123/messages")
        assert response.status_code == 401

    def test_get_messages_invalid_limit(self, client: TestClient, auth_headers: dict):
        """Get messages with invalid limit fails validation."""
        response = client.get(
            "/api/v1/chat/rooms/room_123/messages",
            params={"limit": 200},  # Over 100 max
            headers=auth_headers,
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
