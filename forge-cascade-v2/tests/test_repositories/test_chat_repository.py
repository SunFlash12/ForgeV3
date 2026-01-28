"""
Chat Repository Tests for Forge Cascade V2

Comprehensive tests for ChatRepository including:
- Room CRUD operations
- Member management
- Message operations
- Access control
- Invite code handling
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from forge.models.chat import (
    RoomCreate,
    RoomRole,
    RoomUpdate,
    RoomVisibility,
)
from forge.repositories.chat_repository import ChatRepository

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def chat_repository(mock_db_client):
    """Create chat repository with mock client."""
    return ChatRepository(mock_db_client)


@pytest.fixture
def sample_room_data():
    """Sample room data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "room123",
        "name": "Test Room",
        "description": "A test chat room",
        "visibility": "public",
        "owner_id": "user123",
        "max_members": 100,
        "member_count": 1,
        "is_archived": False,
        "invite_code": None,
        "invite_code_expires_at": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


@pytest.fixture
def sample_member_data():
    """Sample room member data for testing."""
    now = datetime.now(UTC)
    return {
        "room_id": "room123",
        "user_id": "user123",
        "role": "owner",
        "joined_at": now.isoformat(),
        "invited_by": None,
    }


@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    now = datetime.now(UTC)
    return {
        "id": "msg123",
        "room_id": "room123",
        "sender_id": "user123",
        "content": "Hello, world!",
        "created_at": now.isoformat(),
        "edited_at": None,
        "is_deleted": False,
        "deleted_by": None,
    }


# =============================================================================
# Room Creation Tests
# =============================================================================


class TestChatRepositoryRoomCreate:
    """Tests for room creation."""

    @pytest.mark.asyncio
    async def test_create_room_success(self, chat_repository, mock_db_client, sample_room_data):
        """Successful room creation."""
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        room_create = RoomCreate(
            name="Test Room",
            description="A test chat room",
            visibility=RoomVisibility.PUBLIC,
        )

        result = await chat_repository.create_room(
            data=room_create,
            owner_id="user123",
        )

        assert result.name == "Test Room"
        assert result.owner_id == "user123"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_room_with_custom_id(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Room creation with custom room ID."""
        sample_room_data["id"] = "custom_room_id"
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        room_create = RoomCreate(
            name="Custom Room",
            visibility=RoomVisibility.PUBLIC,
        )

        result = await chat_repository.create_room(
            data=room_create,
            owner_id="user123",
            room_id="custom_room_id",
        )

        assert result.id == "custom_room_id"
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["id"] == "custom_room_id"

    @pytest.mark.asyncio
    async def test_create_invite_only_room_generates_invite_code(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Invite-only room generates invite code."""
        sample_room_data["visibility"] = "invite_only"
        sample_room_data["invite_code"] = "ABC123"
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        room_create = RoomCreate(
            name="Private Room",
            visibility=RoomVisibility.INVITE_ONLY,
        )

        await chat_repository.create_room(
            data=room_create,
            owner_id="user123",
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["invite_code"] is not None

    @pytest.mark.asyncio
    async def test_create_room_failure_raises_error(self, chat_repository, mock_db_client):
        """Room creation failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        room_create = RoomCreate(
            name="Test Room",
            visibility=RoomVisibility.PUBLIC,
        )

        with pytest.raises(RuntimeError, match="Failed to create room"):
            await chat_repository.create_room(
                data=room_create,
                owner_id="user123",
            )


# =============================================================================
# Room Retrieval Tests
# =============================================================================


class TestChatRepositoryRoomRetrieval:
    """Tests for room retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_room_success(self, chat_repository, mock_db_client, sample_room_data):
        """Get room by ID."""
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        result = await chat_repository.get_room("room123")

        assert result is not None
        assert result.id == "room123"
        assert result.name == "Test Room"

    @pytest.mark.asyncio
    async def test_get_room_not_found(self, chat_repository, mock_db_client):
        """Get room returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await chat_repository.get_room("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_room_by_invite_code(self, chat_repository, mock_db_client, sample_room_data):
        """Get room by invite code."""
        sample_room_data["invite_code"] = "ABC123"
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        result = await chat_repository.get_room_by_invite_code("ABC123")

        assert result is not None
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["invite_code"] == "ABC123"

    @pytest.mark.asyncio
    async def test_get_user_rooms_with_public(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Get user rooms including public rooms."""
        mock_db_client.execute.return_value = [{"room": sample_room_data, "role": "owner"}]

        result = await chat_repository.get_user_rooms("user123", include_public=True)

        assert len(result) == 1
        room, role = result[0]
        assert room.id == "room123"
        assert role == RoomRole.OWNER

    @pytest.mark.asyncio
    async def test_get_user_rooms_without_public(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Get user rooms excluding public rooms."""
        mock_db_client.execute.return_value = [{"room": sample_room_data, "role": "member"}]

        result = await chat_repository.get_user_rooms("user123", include_public=False)

        assert len(result) == 1
        room, role = result[0]
        assert role == RoomRole.MEMBER

    @pytest.mark.asyncio
    async def test_get_user_rooms_limit_capped(self, chat_repository, mock_db_client):
        """Get user rooms respects limit cap."""
        mock_db_client.execute.return_value = []

        await chat_repository.get_user_rooms("user123", limit=200)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100  # Capped at 100


# =============================================================================
# Room Update Tests
# =============================================================================


class TestChatRepositoryRoomUpdate:
    """Tests for room update operations."""

    @pytest.mark.asyncio
    async def test_update_room_name(self, chat_repository, mock_db_client, sample_room_data):
        """Update room name."""
        sample_room_data["name"] = "Updated Room"
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        update = RoomUpdate(name="Updated Room")
        result = await chat_repository.update_room("room123", update)

        assert result is not None
        assert result.name == "Updated Room"

    @pytest.mark.asyncio
    async def test_update_room_multiple_fields(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Update multiple room fields."""
        sample_room_data["name"] = "New Name"
        sample_room_data["description"] = "New Description"
        sample_room_data["max_members"] = 50
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        update = RoomUpdate(
            name="New Name",
            description="New Description",
            max_members=50,
        )
        result = await chat_repository.update_room("room123", update)

        assert result is not None
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["name"] == "New Name"
        assert params["description"] == "New Description"
        assert params["max_members"] == 50

    @pytest.mark.asyncio
    async def test_update_room_archive(self, chat_repository, mock_db_client, sample_room_data):
        """Archive room via update."""
        sample_room_data["is_archived"] = True
        mock_db_client.execute_single.return_value = {"room": sample_room_data}

        update = RoomUpdate(is_archived=True)
        result = await chat_repository.update_room("room123", update)

        assert result.is_archived is True

    @pytest.mark.asyncio
    async def test_update_room_not_found(self, chat_repository, mock_db_client):
        """Update returns None when room not found."""
        mock_db_client.execute_single.return_value = None

        update = RoomUpdate(name="New Name")
        result = await chat_repository.update_room("nonexistent", update)

        assert result is None


# =============================================================================
# Room Deletion Tests
# =============================================================================


class TestChatRepositoryRoomDelete:
    """Tests for room deletion operations."""

    @pytest.mark.asyncio
    async def test_delete_room_success(self, chat_repository, mock_db_client):
        """Successfully delete room."""
        mock_db_client.execute_single.return_value = {"deleted": True}

        result = await chat_repository.delete_room("room123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_room_not_found(self, chat_repository, mock_db_client):
        """Delete returns False when room not found."""
        mock_db_client.execute_single.return_value = {"deleted": False}

        result = await chat_repository.delete_room("nonexistent")

        assert result is False


# =============================================================================
# Member Management Tests
# =============================================================================


class TestChatRepositoryMemberManagement:
    """Tests for member management operations."""

    @pytest.mark.asyncio
    async def test_add_member_success(self, chat_repository, mock_db_client, sample_member_data):
        """Successfully add member to room."""
        sample_member_data["role"] = "member"
        mock_db_client.execute_single.return_value = {"member": sample_member_data}

        result = await chat_repository.add_member(
            room_id="room123",
            user_id="user456",
            role=RoomRole.MEMBER,
        )

        assert result is not None
        assert result.role == RoomRole.MEMBER

    @pytest.mark.asyncio
    async def test_add_member_with_inviter(
        self, chat_repository, mock_db_client, sample_member_data
    ):
        """Add member with inviter tracking."""
        sample_member_data["invited_by"] = "user123"
        mock_db_client.execute_single.return_value = {"member": sample_member_data}

        await chat_repository.add_member(
            room_id="room123",
            user_id="user456",
            invited_by="user123",
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["invited_by"] == "user123"

    @pytest.mark.asyncio
    async def test_add_member_room_full_or_archived(self, chat_repository, mock_db_client):
        """Add member returns None when room is full or archived."""
        mock_db_client.execute_single.return_value = None

        result = await chat_repository.add_member(
            room_id="room123",
            user_id="user456",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_remove_member_success(self, chat_repository, mock_db_client):
        """Successfully remove member from room."""
        mock_db_client.execute_single.return_value = {"removed": True}

        result = await chat_repository.remove_member("room123", "user456")

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self, chat_repository, mock_db_client):
        """Remove member returns False when not found."""
        mock_db_client.execute_single.return_value = {"removed": False}

        result = await chat_repository.remove_member("room123", "nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_member_success(self, chat_repository, mock_db_client, sample_member_data):
        """Get specific member info."""
        mock_db_client.execute_single.return_value = {"member": sample_member_data}

        result = await chat_repository.get_member("room123", "user123")

        assert result is not None
        assert result.user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_room_members(self, chat_repository, mock_db_client, sample_member_data):
        """Get all room members."""
        mock_db_client.execute.return_value = [{"member": sample_member_data}]

        result = await chat_repository.get_room_members("room123")

        assert len(result) == 1
        assert result[0].user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_room_members_limit_capped(self, chat_repository, mock_db_client):
        """Get room members respects limit cap at 500."""
        mock_db_client.execute.return_value = []

        await chat_repository.get_room_members("room123", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 500  # Capped at 500

    @pytest.mark.asyncio
    async def test_update_member_role(self, chat_repository, mock_db_client):
        """Update member role."""
        mock_db_client.execute_single.return_value = {"updated": True}

        result = await chat_repository.update_member_role("room123", "user456", RoomRole.MODERATOR)

        assert result is True
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "role <> 'owner'" in query  # Cannot change owner role

    @pytest.mark.asyncio
    async def test_update_member_role_owner_protected(self, chat_repository, mock_db_client):
        """Cannot update owner's role."""
        mock_db_client.execute_single.return_value = {"updated": False}

        result = await chat_repository.update_member_role("room123", "owner_user", RoomRole.MEMBER)

        assert result is False


# =============================================================================
# Access Control Tests
# =============================================================================


class TestChatRepositoryAccessControl:
    """Tests for access control operations."""

    @pytest.mark.asyncio
    async def test_check_access_room_not_found(self, chat_repository, mock_db_client):
        """Access check allows creation when room not found."""
        mock_db_client.execute_single.return_value = {"room": None, "role": None}

        result = await chat_repository.check_access("room123", "user123")

        assert result.can_access is True
        assert result.reason == "room_not_found"

    @pytest.mark.asyncio
    async def test_check_access_archived_room(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Access denied for archived room."""
        sample_room_data["is_archived"] = True
        mock_db_client.execute_single.return_value = {
            "room": sample_room_data,
            "role": None,
        }

        result = await chat_repository.check_access("room123", "user123")

        assert result.can_access is False
        assert "archived" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_access_member_has_access(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Member has access to room."""
        mock_db_client.execute_single.return_value = {
            "room": sample_room_data,
            "role": "member",
        }

        result = await chat_repository.check_access("room123", "user123")

        assert result.can_access is True
        assert result.role == RoomRole.MEMBER

    @pytest.mark.asyncio
    async def test_check_access_public_room_non_member(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Non-member can access public room."""
        sample_room_data["visibility"] = "public"
        mock_db_client.execute_single.return_value = {
            "room": sample_room_data,
            "role": None,
        }

        result = await chat_repository.check_access("room123", "user456")

        assert result.can_access is True
        assert result.role is None

    @pytest.mark.asyncio
    async def test_check_access_private_room_non_member(
        self, chat_repository, mock_db_client, sample_room_data
    ):
        """Non-member cannot access private room."""
        sample_room_data["visibility"] = "private"
        mock_db_client.execute_single.return_value = {
            "room": sample_room_data,
            "role": None,
        }

        result = await chat_repository.check_access("room123", "user456")

        assert result.can_access is False
        assert "private" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_get_user_role(self, chat_repository, mock_db_client, sample_member_data):
        """Get user role in room."""
        mock_db_client.execute_single.return_value = {"member": sample_member_data}

        result = await chat_repository.get_user_role("room123", "user123")

        assert result == RoomRole.OWNER

    @pytest.mark.asyncio
    async def test_get_user_role_not_member(self, chat_repository, mock_db_client):
        """Get user role returns None for non-member."""
        mock_db_client.execute_single.return_value = None

        result = await chat_repository.get_user_role("room123", "nonmember")

        assert result is None


# =============================================================================
# Message Operations Tests
# =============================================================================


class TestChatRepositoryMessages:
    """Tests for message operations."""

    @pytest.mark.asyncio
    async def test_save_message_success(self, chat_repository, mock_db_client, sample_message_data):
        """Successfully save message."""
        mock_db_client.execute_single.return_value = {"message": sample_message_data}

        result = await chat_repository.save_message(
            room_id="room123",
            sender_id="user123",
            content="Hello, world!",
        )

        assert result.content == "Hello, world!"
        assert result.room_id == "room123"

    @pytest.mark.asyncio
    async def test_save_message_failure_raises_error(self, chat_repository, mock_db_client):
        """Save message failure raises RuntimeError."""
        mock_db_client.execute_single.return_value = None

        with pytest.raises(RuntimeError, match="Failed to save message"):
            await chat_repository.save_message(
                room_id="room123",
                sender_id="user123",
                content="Hello!",
            )

    @pytest.mark.asyncio
    async def test_get_room_messages(self, chat_repository, mock_db_client, sample_message_data):
        """Get messages in room."""
        mock_db_client.execute.return_value = [{"message": sample_message_data}]

        messages, has_more = await chat_repository.get_room_messages(
            room_id="room123",
            limit=50,
        )

        assert len(messages) == 1
        assert has_more is False

    @pytest.mark.asyncio
    async def test_get_room_messages_with_pagination(
        self, chat_repository, mock_db_client, sample_message_data
    ):
        """Get messages with pagination indicator."""
        # Return more than limit to trigger has_more
        messages = [{"message": sample_message_data} for _ in range(51)]
        mock_db_client.execute.return_value = messages

        result_messages, has_more = await chat_repository.get_room_messages(
            room_id="room123",
            limit=50,
        )

        assert len(result_messages) == 50
        assert has_more is True

    @pytest.mark.asyncio
    async def test_get_room_messages_before_timestamp(
        self, chat_repository, mock_db_client, sample_message_data
    ):
        """Get messages before specific timestamp."""
        mock_db_client.execute.return_value = [{"message": sample_message_data}]
        before = datetime.now(UTC)

        await chat_repository.get_room_messages(
            room_id="room123",
            before=before,
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert "before" in params

    @pytest.mark.asyncio
    async def test_delete_message_success(self, chat_repository, mock_db_client):
        """Successfully soft-delete message."""
        mock_db_client.execute_single.return_value = {"deleted": True}

        result = await chat_repository.delete_message("msg123", "user123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, chat_repository, mock_db_client):
        """Delete message returns False when not found."""
        mock_db_client.execute_single.return_value = {"deleted": False}

        result = await chat_repository.delete_message("nonexistent", "user123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_message_success(self, chat_repository, mock_db_client, sample_message_data):
        """Get message by ID."""
        mock_db_client.execute_single.return_value = {"message": sample_message_data}

        result = await chat_repository.get_message("msg123")

        assert result is not None
        assert result.id == "msg123"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, chat_repository, mock_db_client):
        """Get message returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await chat_repository.get_message("nonexistent")

        assert result is None


# =============================================================================
# Invite Code Tests
# =============================================================================


class TestChatRepositoryInviteCodes:
    """Tests for invite code operations."""

    @pytest.mark.asyncio
    async def test_regenerate_invite_code_success(self, chat_repository, mock_db_client):
        """Successfully regenerate invite code."""
        mock_db_client.execute_single.return_value = {"code": "NEW123"}

        result = await chat_repository.regenerate_invite_code("room123")

        assert result == "NEW123"

    @pytest.mark.asyncio
    async def test_regenerate_invite_code_with_expiry(self, chat_repository, mock_db_client):
        """Regenerate invite code with expiry hours."""
        mock_db_client.execute_single.return_value = {"code": "EXP456"}

        await chat_repository.regenerate_invite_code("room123", expires_hours=24)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_regenerate_invite_code_no_expiry(self, chat_repository, mock_db_client):
        """Regenerate invite code without expiry."""
        mock_db_client.execute_single.return_value = {"code": "PERM789"}

        await chat_repository.regenerate_invite_code("room123")

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["expires_at"] is None

    @pytest.mark.asyncio
    async def test_regenerate_invite_code_room_not_found(self, chat_repository, mock_db_client):
        """Regenerate invite code returns None for nonexistent room."""
        mock_db_client.execute_single.return_value = None

        result = await chat_repository.regenerate_invite_code("nonexistent")

        assert result is None


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestChatRepositoryHelpers:
    """Tests for helper methods."""

    def test_generate_id(self, chat_repository):
        """Generate ID returns valid UUID string."""
        id1 = chat_repository._generate_id()
        id2 = chat_repository._generate_id()

        assert isinstance(id1, str)
        assert len(id1) > 0
        assert id1 != id2  # UUIDs should be unique

    def test_now_returns_utc_datetime(self, chat_repository):
        """_now returns timezone-aware UTC datetime."""
        result = chat_repository._now()

        assert result.tzinfo is not None
        assert result.tzinfo == UTC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
