"""
Tests for Chat Service

Tests cover:
- Room operations (create, get, update, delete)
- Access control (visibility, roles, permissions)
- Membership operations (join, leave, add, remove members)
- Message operations (save, get, delete)
- Invite code operations
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.chat import (
    ChatMessage,
    ChatRoom,
    RoomAccessCheck,
    RoomCreate,
    RoomMember,
    RoomRole,
    RoomUpdate,
    RoomVisibility,
)
from forge.services.chat_service import (
    ChatAccessDeniedError,
    ChatPermissionError,
    ChatService,
    get_chat_service,
    set_chat_service,
)


class TestChatServiceInit:
    """Tests for ChatService initialization."""

    def test_init_with_repo(self):
        """Test initialization with chat repository."""
        mock_repo = MagicMock()
        service = ChatService(chat_repo=mock_repo)

        assert service._chat_repo is mock_repo
        assert service._audit_repo is None

    def test_init_with_audit_repo(self):
        """Test initialization with both repositories."""
        mock_chat_repo = MagicMock()
        mock_audit_repo = MagicMock()

        service = ChatService(chat_repo=mock_chat_repo, audit_repo=mock_audit_repo)

        assert service._chat_repo is mock_chat_repo
        assert service._audit_repo is mock_audit_repo


class TestRoomOperations:
    """Tests for room operations."""

    @pytest.fixture
    def mock_chat_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_chat_repo, mock_audit_repo):
        return ChatService(chat_repo=mock_chat_repo, audit_repo=mock_audit_repo)

    @pytest.mark.asyncio
    async def test_create_room(self, service, mock_chat_repo, mock_audit_repo):
        """Test creating a new room."""
        mock_room = ChatRoom(
            id="room-123",
            name="Test Room",
            owner_id="user-1",
            visibility=RoomVisibility.PUBLIC,
        )
        mock_chat_repo.create_room.return_value = mock_room

        result = await service.create_room(
            owner_id="user-1",
            name="Test Room",
            description="A test room",
            visibility=RoomVisibility.PUBLIC,
            max_members=50,
        )

        assert result.id == "room-123"
        assert result.name == "Test Room"
        mock_chat_repo.create_room.assert_called_once()
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_room_no_audit(self, mock_chat_repo):
        """Test creating a room without audit repo."""
        service = ChatService(chat_repo=mock_chat_repo)
        mock_room = ChatRoom(
            id="room-456",
            name="No Audit Room",
            owner_id="user-2",
        )
        mock_chat_repo.create_room.return_value = mock_room

        result = await service.create_room(
            owner_id="user-2",
            name="No Audit Room",
        )

        assert result.id == "room-456"
        mock_chat_repo.create_room.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_room_existing(self, service, mock_chat_repo):
        """Test getting an existing room."""
        existing_room = ChatRoom(
            id="existing-room",
            name="Existing Room",
            owner_id="user-1",
        )
        mock_chat_repo.get_room.return_value = existing_room

        result = await service.get_or_create_room("existing-room", "user-2")

        assert result.id == "existing-room"
        mock_chat_repo.create_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_create_room_new(self, service, mock_chat_repo):
        """Test creating a new room on-demand."""
        mock_chat_repo.get_room.return_value = None
        new_room = ChatRoom(
            id="new-room",
            name="Room new-room",
            owner_id="user-1",
        )
        mock_chat_repo.create_room.return_value = new_room

        result = await service.get_or_create_room("new-room", "user-1")

        assert result.id == "new-room"
        mock_chat_repo.create_room.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_room_as_owner(self, service, mock_chat_repo, mock_audit_repo):
        """Test updating a room as owner."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER
        updated_room = ChatRoom(
            id="room-1",
            name="Updated Room",
            owner_id="user-1",
        )
        mock_chat_repo.update_room.return_value = updated_room

        update_data = RoomUpdate(name="Updated Room")
        result = await service.update_room("room-1", "user-1", update_data)

        assert result.name == "Updated Room"
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_room_as_admin(self, service, mock_chat_repo):
        """Test updating a room as admin."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN
        updated_room = ChatRoom(
            id="room-1",
            name="Admin Updated",
            owner_id="user-1",
        )
        mock_chat_repo.update_room.return_value = updated_room

        update_data = RoomUpdate(name="Admin Updated")
        result = await service.update_room("room-1", "admin-user", update_data)

        assert result.name == "Admin Updated"

    @pytest.mark.asyncio
    async def test_update_room_permission_denied(self, service, mock_chat_repo):
        """Test updating a room without permission."""
        mock_chat_repo.get_user_role.return_value = RoomRole.MEMBER

        update_data = RoomUpdate(name="Should Fail")

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.update_room("room-1", "member-user", update_data)

        assert "owner or admin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_room_no_role(self, service, mock_chat_repo):
        """Test updating a room when user has no role."""
        mock_chat_repo.get_user_role.return_value = None

        update_data = RoomUpdate(name="Should Fail")

        with pytest.raises(ChatPermissionError):
            await service.update_room("room-1", "no-role-user", update_data)

    @pytest.mark.asyncio
    async def test_update_room_not_found(self, service, mock_chat_repo):
        """Test updating a non-existent room."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER
        mock_chat_repo.update_room.return_value = None

        update_data = RoomUpdate(name="Should Fail")

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.update_room("nonexistent", "user-1", update_data)

        assert "room not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_room_as_owner(self, service, mock_chat_repo, mock_audit_repo):
        """Test deleting a room as owner."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER
        mock_chat_repo.delete_room.return_value = True

        result = await service.delete_room("room-1", "owner-user")

        assert result is True
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_room_as_admin(self, service, mock_chat_repo):
        """Test deleting a room as admin (should fail)."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.delete_room("room-1", "admin-user")

        assert "owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_room(self, service, mock_chat_repo):
        """Test getting a room by ID."""
        room = ChatRoom(id="room-1", name="Test Room", owner_id="user-1")
        mock_chat_repo.get_room.return_value = room

        result = await service.get_room("room-1")

        assert result.id == "room-1"
        mock_chat_repo.get_room.assert_called_with("room-1")

    @pytest.mark.asyncio
    async def test_get_user_rooms(self, service, mock_chat_repo):
        """Test getting rooms for a user."""
        rooms = [
            (ChatRoom(id="room-1", name="Room 1", owner_id="user-1"), RoomRole.OWNER),
            (ChatRoom(id="room-2", name="Room 2", owner_id="user-2"), RoomRole.MEMBER),
        ]
        mock_chat_repo.get_user_rooms.return_value = rooms

        result = await service.get_user_rooms("user-1", include_public=True, limit=50)

        assert len(result) == 2
        mock_chat_repo.get_user_rooms.assert_called_with("user-1", True, 50)


class TestAccessControl:
    """Tests for access control."""

    @pytest.fixture
    def mock_chat_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_chat_repo):
        return ChatService(chat_repo=mock_chat_repo)

    @pytest.mark.asyncio
    async def test_check_access(self, service, mock_chat_repo):
        """Test checking room access."""
        access_check = RoomAccessCheck(can_access=True, role=RoomRole.MEMBER)
        mock_chat_repo.check_access.return_value = access_check

        result = await service.check_access("room-1", "user-1")

        assert result.can_access is True
        assert result.role == RoomRole.MEMBER

    @pytest.mark.asyncio
    async def test_verify_access_allowed(self, service, mock_chat_repo):
        """Test verifying access when allowed."""
        access_check = RoomAccessCheck(can_access=True, role=RoomRole.ADMIN)
        mock_chat_repo.check_access.return_value = access_check

        role = await service.verify_access("room-1", "user-1")

        assert role == RoomRole.ADMIN

    @pytest.mark.asyncio
    async def test_verify_access_denied(self, service, mock_chat_repo):
        """Test verifying access when denied."""
        access_check = RoomAccessCheck(can_access=False, reason="Private room")
        mock_chat_repo.check_access.return_value = access_check

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.verify_access("room-1", "user-1")

        assert "Private room" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_access_denied_no_reason(self, service, mock_chat_repo):
        """Test verifying access when denied without reason."""
        access_check = RoomAccessCheck(can_access=False, reason=None)
        mock_chat_repo.check_access.return_value = access_check

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.verify_access("room-1", "user-1")

        assert "Access denied" in str(exc_info.value)


class TestMembershipOperations:
    """Tests for membership operations."""

    @pytest.fixture
    def mock_chat_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_chat_repo, mock_audit_repo):
        return ChatService(chat_repo=mock_chat_repo, audit_repo=mock_audit_repo)

    @pytest.mark.asyncio
    async def test_join_public_room(self, service, mock_chat_repo, mock_audit_repo):
        """Test joining a public room."""
        room = ChatRoom(
            id="public-room",
            name="Public Room",
            owner_id="owner",
            visibility=RoomVisibility.PUBLIC,
            is_archived=False,
        )
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        member = RoomMember(room_id="public-room", user_id="user-1", role=RoomRole.MEMBER)
        mock_chat_repo.add_member.return_value = member

        result = await service.join_room("public-room", "user-1")

        assert result.user_id == "user-1"
        assert result.role == RoomRole.MEMBER
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_join_room_already_member(self, service, mock_chat_repo):
        """Test joining a room when already a member."""
        room = ChatRoom(
            id="room-1",
            name="Room",
            owner_id="owner",
            visibility=RoomVisibility.PUBLIC,
        )
        mock_chat_repo.get_room.return_value = room

        existing_member = RoomMember(room_id="room-1", user_id="user-1", role=RoomRole.MEMBER)
        mock_chat_repo.get_member.return_value = existing_member

        result = await service.join_room("room-1", "user-1")

        assert result == existing_member
        mock_chat_repo.add_member.assert_not_called()

    @pytest.mark.asyncio
    async def test_join_room_not_found(self, service, mock_chat_repo):
        """Test joining a non-existent room."""
        mock_chat_repo.get_room.return_value = None

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_room("nonexistent", "user-1")

        assert "Room not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_archived_room(self, service, mock_chat_repo):
        """Test joining an archived room."""
        room = ChatRoom(
            id="archived-room",
            name="Archived Room",
            owner_id="owner",
            is_archived=True,
        )
        mock_chat_repo.get_room.return_value = room

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_room("archived-room", "user-1")

        assert "archived" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_private_room(self, service, mock_chat_repo):
        """Test joining a private room."""
        room = ChatRoom(
            id="private-room",
            name="Private Room",
            owner_id="owner",
            visibility=RoomVisibility.PRIVATE,
        )
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_room("private-room", "user-1")

        assert "Private room" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_invite_only_room_with_code(self, service, mock_chat_repo):
        """Test joining an invite-only room with valid code."""
        room = ChatRoom(
            id="invite-room",
            name="Invite Room",
            owner_id="owner",
            visibility=RoomVisibility.INVITE_ONLY,
            invite_code="valid-code",
        )
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        member = RoomMember(room_id="invite-room", user_id="user-1", role=RoomRole.MEMBER)
        mock_chat_repo.add_member.return_value = member

        result = await service.join_room("invite-room", "user-1", invite_code="valid-code")

        assert result.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_join_invite_only_room_no_code(self, service, mock_chat_repo):
        """Test joining an invite-only room without code."""
        room = ChatRoom(
            id="invite-room",
            name="Invite Room",
            owner_id="owner",
            visibility=RoomVisibility.INVITE_ONLY,
        )
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_room("invite-room", "user-1")

        assert "Invite code required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_invite_only_room_invalid_code(self, service, mock_chat_repo):
        """Test joining an invite-only room with invalid code."""
        room = ChatRoom(
            id="invite-room",
            name="Invite Room",
            owner_id="owner",
            visibility=RoomVisibility.INVITE_ONLY,
            invite_code="valid-code",
        )
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_room("invite-room", "user-1", invite_code="wrong-code")

        assert "Invalid invite code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_with_invite(self, service, mock_chat_repo):
        """Test joining a room via invite code."""
        room = ChatRoom(
            id="room-with-invite",
            name="Room",
            owner_id="owner",
            visibility=RoomVisibility.INVITE_ONLY,
            invite_code="test-code",
        )
        mock_chat_repo.get_room_by_invite_code.return_value = room
        mock_chat_repo.get_room.return_value = room
        mock_chat_repo.get_member.return_value = None

        member = RoomMember(room_id="room-with-invite", user_id="user-1", role=RoomRole.MEMBER)
        mock_chat_repo.add_member.return_value = member

        result = await service.join_with_invite("test-code", "user-1")

        assert result is not None
        assert result[0].id == "room-with-invite"
        assert result[1].user_id == "user-1"

    @pytest.mark.asyncio
    async def test_join_with_invite_invalid(self, service, mock_chat_repo):
        """Test joining with invalid invite code."""
        mock_chat_repo.get_room_by_invite_code.return_value = None

        with pytest.raises(ChatAccessDeniedError) as exc_info:
            await service.join_with_invite("invalid-code", "user-1")

        assert "Invalid invite code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_leave_room(self, service, mock_chat_repo, mock_audit_repo):
        """Test leaving a room."""
        mock_chat_repo.get_user_role.return_value = RoomRole.MEMBER
        mock_chat_repo.remove_member.return_value = True

        result = await service.leave_room("room-1", "user-1")

        assert result is True
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_leave_room_owner_cannot_leave(self, service, mock_chat_repo):
        """Test that owner cannot leave room."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.leave_room("room-1", "owner")

        assert "Owner cannot leave" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_member_as_admin(self, service, mock_chat_repo, mock_audit_repo):
        """Test adding a member as admin."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN

        member = RoomMember(room_id="room-1", user_id="new-user", role=RoomRole.MEMBER)
        mock_chat_repo.add_member.return_value = member

        result = await service.add_member("room-1", "admin-user", "new-user")

        assert result.user_id == "new-user"
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_member_without_permission(self, service, mock_chat_repo):
        """Test adding a member without permission."""
        mock_chat_repo.get_user_role.return_value = RoomRole.MEMBER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.add_member("room-1", "member-user", "new-user")

        assert "admin or owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_member_cannot_assign_owner(self, service, mock_chat_repo):
        """Test that owner role cannot be assigned."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.add_member("room-1", "owner", "new-user", role=RoomRole.OWNER)

        assert "Cannot assign owner role" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_member_admin_cannot_add_admin(self, service, mock_chat_repo):
        """Test that admin cannot add another admin."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.add_member("room-1", "admin", "new-user", role=RoomRole.ADMIN)

        assert "owner" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_owner_can_add_admin(self, service, mock_chat_repo):
        """Test that owner can add admin."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER

        member = RoomMember(room_id="room-1", user_id="new-admin", role=RoomRole.ADMIN)
        mock_chat_repo.add_member.return_value = member

        result = await service.add_member("room-1", "owner", "new-admin", role=RoomRole.ADMIN)

        assert result.role == RoomRole.ADMIN

    @pytest.mark.asyncio
    async def test_remove_member_as_admin(self, service, mock_chat_repo, mock_audit_repo):
        """Test removing a member as admin."""
        mock_chat_repo.get_user_role.side_effect = [RoomRole.ADMIN, RoomRole.MEMBER]
        mock_chat_repo.remove_member.return_value = True

        result = await service.remove_member("room-1", "admin", "member-to-remove")

        assert result is True
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_member_target_not_member(self, service, mock_chat_repo):
        """Test removing a non-member."""
        mock_chat_repo.get_user_role.side_effect = [RoomRole.ADMIN, None]

        result = await service.remove_member("room-1", "admin", "non-member")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_member_cannot_remove_owner(self, service, mock_chat_repo):
        """Test that owner cannot be removed."""
        mock_chat_repo.get_user_role.side_effect = [RoomRole.ADMIN, RoomRole.OWNER]

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.remove_member("room-1", "admin", "owner")

        assert "Cannot remove owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_member_admin_cannot_remove_admin(self, service, mock_chat_repo):
        """Test that admin cannot remove another admin."""
        mock_chat_repo.get_user_role.side_effect = [RoomRole.ADMIN, RoomRole.ADMIN]

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.remove_member("room-1", "admin1", "admin2")

        assert "owner" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_member_role(self, service, mock_chat_repo, mock_audit_repo):
        """Test updating a member's role."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER
        mock_chat_repo.update_member_role.return_value = True

        result = await service.update_member_role("room-1", "owner", "member", RoomRole.ADMIN)

        assert result is True
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member_role_only_owner(self, service, mock_chat_repo):
        """Test that only owner can update roles."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.update_member_role("room-1", "admin", "member", RoomRole.ADMIN)

        assert "owner" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_update_member_role_cannot_assign_owner(self, service, mock_chat_repo):
        """Test that owner role cannot be assigned via update."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.update_member_role("room-1", "owner", "member", RoomRole.OWNER)

        assert "transfer_ownership" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_room_members(self, service, mock_chat_repo):
        """Test getting room members."""
        members = [
            RoomMember(room_id="room-1", user_id="user-1", role=RoomRole.OWNER),
            RoomMember(room_id="room-1", user_id="user-2", role=RoomRole.MEMBER),
        ]
        mock_chat_repo.get_room_members.return_value = members

        result = await service.get_room_members("room-1")

        assert len(result) == 2
        mock_chat_repo.get_room_members.assert_called_with("room-1", 100)


class TestMessageOperations:
    """Tests for message operations."""

    @pytest.fixture
    def mock_chat_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_chat_repo, mock_audit_repo):
        return ChatService(chat_repo=mock_chat_repo, audit_repo=mock_audit_repo)

    @pytest.mark.asyncio
    async def test_save_message(self, service, mock_chat_repo):
        """Test saving a message."""
        message = ChatMessage(
            id="msg-1",
            room_id="room-1",
            sender_id="user-1",
            content="Hello, world!",
        )
        mock_chat_repo.save_message.return_value = message

        result = await service.save_message("room-1", "user-1", "Hello, world!")

        assert result.content == "Hello, world!"
        mock_chat_repo.save_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_message_truncates_long_content(self, service, mock_chat_repo):
        """Test that long messages are truncated."""
        with patch("forge.services.chat_service.settings") as mock_settings:
            mock_settings.chat_message_max_length = 100

            message = ChatMessage(
                id="msg-1",
                room_id="room-1",
                sender_id="user-1",
                content="A" * 100,
            )
            mock_chat_repo.save_message.return_value = message

            long_content = "A" * 200
            await service.save_message("room-1", "user-1", long_content)

            # Check that save was called with truncated content
            call_args = mock_chat_repo.save_message.call_args
            assert len(call_args[0][2]) == 100

    @pytest.mark.asyncio
    async def test_get_room_messages(self, service, mock_chat_repo):
        """Test getting room messages."""
        messages = [
            ChatMessage(id="msg-1", room_id="room-1", sender_id="user-1", content="Hello"),
            ChatMessage(id="msg-2", room_id="room-1", sender_id="user-2", content="Hi"),
        ]
        access_check = RoomAccessCheck(can_access=True, role=RoomRole.MEMBER)
        mock_chat_repo.check_access.return_value = access_check
        mock_chat_repo.get_room_messages.return_value = (messages, False)

        with patch("forge.services.chat_service.settings") as mock_settings:
            mock_settings.chat_history_default_limit = 100

            result, has_more = await service.get_room_messages("room-1", "user-1")

            assert len(result) == 2
            assert has_more is False

    @pytest.mark.asyncio
    async def test_get_room_messages_access_denied(self, service, mock_chat_repo):
        """Test getting messages when access denied."""
        access_check = RoomAccessCheck(can_access=False, reason="Not a member")
        mock_chat_repo.check_access.return_value = access_check

        with pytest.raises(ChatAccessDeniedError):
            await service.get_room_messages("room-1", "user-1")

    @pytest.mark.asyncio
    async def test_delete_message_by_author(self, service, mock_chat_repo, mock_audit_repo):
        """Test deleting a message by its author."""
        message = ChatMessage(
            id="msg-1",
            room_id="room-1",
            sender_id="author-user",
            content="To be deleted",
        )
        mock_chat_repo.get_message.return_value = message
        mock_chat_repo.delete_message.return_value = True

        result = await service.delete_message("msg-1", "author-user")

        assert result is True
        mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_message_by_admin(self, service, mock_chat_repo):
        """Test deleting a message by admin."""
        message = ChatMessage(
            id="msg-1",
            room_id="room-1",
            sender_id="other-user",
            content="Deleted by admin",
        )
        mock_chat_repo.get_message.return_value = message
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN
        mock_chat_repo.delete_message.return_value = True

        result = await service.delete_message("msg-1", "admin-user")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_message_permission_denied(self, service, mock_chat_repo):
        """Test deleting a message without permission."""
        message = ChatMessage(
            id="msg-1",
            room_id="room-1",
            sender_id="other-user",
            content="Cannot delete",
        )
        mock_chat_repo.get_message.return_value = message
        mock_chat_repo.get_user_role.return_value = RoomRole.MEMBER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.delete_message("msg-1", "member-user")

        assert "message author, admin, or owner" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, service, mock_chat_repo):
        """Test deleting a non-existent message."""
        mock_chat_repo.get_message.return_value = None

        result = await service.delete_message("nonexistent", "user-1")

        assert result is False


class TestInviteCodeOperations:
    """Tests for invite code operations."""

    @pytest.fixture
    def mock_chat_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_repo(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_chat_repo, mock_audit_repo):
        return ChatService(chat_repo=mock_chat_repo, audit_repo=mock_audit_repo)

    @pytest.mark.asyncio
    async def test_generate_invite_code(self, service, mock_chat_repo, mock_audit_repo):
        """Test generating an invite code."""
        mock_chat_repo.get_user_role.return_value = RoomRole.ADMIN
        mock_chat_repo.regenerate_invite_code.return_value = "new-invite-code"

        with patch("forge.services.chat_service.settings") as mock_settings:
            mock_settings.chat_invite_expiry_hours = 24

            result = await service.generate_invite_code("room-1", "admin-user")

            assert result == "new-invite-code"
            mock_audit_repo.log_user_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_invite_code_custom_expiry(self, service, mock_chat_repo):
        """Test generating an invite code with custom expiry."""
        mock_chat_repo.get_user_role.return_value = RoomRole.OWNER
        mock_chat_repo.regenerate_invite_code.return_value = "custom-code"

        result = await service.generate_invite_code("room-1", "owner", expires_hours=48)

        assert result == "custom-code"
        mock_chat_repo.regenerate_invite_code.assert_called_with("room-1", 48)

    @pytest.mark.asyncio
    async def test_generate_invite_code_permission_denied(self, service, mock_chat_repo):
        """Test generating invite code without permission."""
        mock_chat_repo.get_user_role.return_value = RoomRole.MEMBER

        with pytest.raises(ChatPermissionError) as exc_info:
            await service.generate_invite_code("room-1", "member")

        assert "admin or owner" in str(exc_info.value)


class TestExceptions:
    """Tests for custom exceptions."""

    def test_chat_access_denied_error(self):
        """Test ChatAccessDeniedError."""
        error = ChatAccessDeniedError("room-123", "Not a member")

        assert error.room_id == "room-123"
        assert error.reason == "Not a member"
        assert "room-123" in str(error)
        assert "Not a member" in str(error)

    def test_chat_permission_error(self):
        """Test ChatPermissionError."""
        error = ChatPermissionError("delete_room", "owner")

        assert error.action == "delete_room"
        assert error.required_role == "owner"
        assert "delete_room" in str(error)
        assert "owner" in str(error)


class TestGlobalServiceFunctions:
    """Tests for global service functions."""

    def test_get_chat_service_uninitialized(self):
        """Test getting uninitialized chat service raises error."""
        # Clear global service
        import forge.services.chat_service as module
        module._chat_service = None

        with pytest.raises(RuntimeError, match="not initialized"):
            get_chat_service()

    def test_set_and_get_chat_service(self):
        """Test setting and getting global chat service."""
        mock_repo = MagicMock()
        service = ChatService(chat_repo=mock_repo)

        set_chat_service(service)

        retrieved = get_chat_service()
        assert retrieved is service

        # Clean up
        import forge.services.chat_service as module
        module._chat_service = None
