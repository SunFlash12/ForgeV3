"""
Chat Model Tests for Forge Cascade V2

Comprehensive tests for chat models including:
- Room creation, update, and response models
- Room visibility and role enums
- Membership models
- Message models with validators
- Invite and access control models
"""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from forge.models.chat import (
    ChatMessage,
    ChatRoom,
    InviteCodeResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    RoomAccessCheck,
    RoomAccessDenied,
    RoomCreate,
    RoomListResponse,
    RoomMember,
    RoomResponse,
    RoomRole,
    RoomUpdate,
    RoomVisibility,
)

# =============================================================================
# RoomVisibility Enum Tests
# =============================================================================


class TestRoomVisibility:
    """Tests for RoomVisibility enum."""

    def test_visibility_values(self):
        """RoomVisibility has expected values."""
        assert RoomVisibility.PUBLIC.value == "public"
        assert RoomVisibility.PRIVATE.value == "private"
        assert RoomVisibility.INVITE_ONLY.value == "invite_only"

    def test_visibility_members(self):
        """RoomVisibility has exactly three members."""
        assert len(RoomVisibility) == 3

    def test_visibility_from_string(self):
        """RoomVisibility can be created from string values."""
        assert RoomVisibility("public") == RoomVisibility.PUBLIC
        assert RoomVisibility("private") == RoomVisibility.PRIVATE
        assert RoomVisibility("invite_only") == RoomVisibility.INVITE_ONLY

    def test_visibility_invalid_value(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError):
            RoomVisibility("invalid")


# =============================================================================
# RoomRole Enum Tests
# =============================================================================


class TestRoomRole:
    """Tests for RoomRole enum."""

    def test_role_values(self):
        """RoomRole has expected values."""
        assert RoomRole.OWNER.value == "owner"
        assert RoomRole.ADMIN.value == "admin"
        assert RoomRole.MEMBER.value == "member"

    def test_role_members(self):
        """RoomRole has exactly three members."""
        assert len(RoomRole) == 3

    def test_can_manage_members_owner(self):
        """Owner can manage members."""
        assert RoomRole.can_manage_members(RoomRole.OWNER) is True

    def test_can_manage_members_admin(self):
        """Admin can manage members."""
        assert RoomRole.can_manage_members(RoomRole.ADMIN) is True

    def test_can_manage_members_member(self):
        """Regular member cannot manage members."""
        assert RoomRole.can_manage_members(RoomRole.MEMBER) is False

    def test_can_delete_room_owner(self):
        """Only owner can delete room."""
        assert RoomRole.can_delete_room(RoomRole.OWNER) is True

    def test_can_delete_room_admin(self):
        """Admin cannot delete room."""
        assert RoomRole.can_delete_room(RoomRole.ADMIN) is False

    def test_can_delete_room_member(self):
        """Member cannot delete room."""
        assert RoomRole.can_delete_room(RoomRole.MEMBER) is False

    def test_can_moderate_owner(self):
        """Owner can moderate messages."""
        assert RoomRole.can_moderate(RoomRole.OWNER) is True

    def test_can_moderate_admin(self):
        """Admin can moderate messages."""
        assert RoomRole.can_moderate(RoomRole.ADMIN) is True

    def test_can_moderate_member(self):
        """Regular member cannot moderate."""
        assert RoomRole.can_moderate(RoomRole.MEMBER) is False

    def test_hierarchy_value_owner(self):
        """Owner has highest hierarchy value."""
        assert RoomRole.hierarchy_value(RoomRole.OWNER) == 100

    def test_hierarchy_value_admin(self):
        """Admin has middle hierarchy value."""
        assert RoomRole.hierarchy_value(RoomRole.ADMIN) == 50

    def test_hierarchy_value_member(self):
        """Member has lowest hierarchy value."""
        assert RoomRole.hierarchy_value(RoomRole.MEMBER) == 10

    def test_hierarchy_ordering(self):
        """Hierarchy values are properly ordered."""
        owner_val = RoomRole.hierarchy_value(RoomRole.OWNER)
        admin_val = RoomRole.hierarchy_value(RoomRole.ADMIN)
        member_val = RoomRole.hierarchy_value(RoomRole.MEMBER)

        assert owner_val > admin_val > member_val


# =============================================================================
# RoomCreate Tests
# =============================================================================


class TestRoomCreate:
    """Tests for RoomCreate model."""

    def test_valid_room_create_minimal(self):
        """Minimal valid room creation."""
        room = RoomCreate(name="Test Room")
        assert room.name == "Test Room"
        assert room.description is None
        assert room.visibility == RoomVisibility.PUBLIC
        assert room.max_members == 100

    def test_valid_room_create_full(self):
        """Full room creation with all fields."""
        room = RoomCreate(
            name="Test Room",
            description="A test room",
            visibility=RoomVisibility.PRIVATE,
            max_members=50,
        )
        assert room.name == "Test Room"
        assert room.description == "A test room"
        assert room.visibility == RoomVisibility.PRIVATE
        assert room.max_members == 50

    def test_name_required(self):
        """Name field is required."""
        with pytest.raises(ValidationError):
            RoomCreate()

    def test_name_min_length(self):
        """Name must be at least 1 character."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            RoomCreate(name="")

    def test_name_max_length(self):
        """Name must be at most 100 characters."""
        with pytest.raises(ValidationError):
            RoomCreate(name="a" * 101)

    def test_description_max_length(self):
        """Description must be at most 500 characters."""
        with pytest.raises(ValidationError):
            RoomCreate(name="Test", description="a" * 501)

    def test_max_members_min_value(self):
        """Max members must be at least 2."""
        with pytest.raises(ValidationError):
            RoomCreate(name="Test", max_members=1)

    def test_max_members_max_value(self):
        """Max members must be at most 1000."""
        with pytest.raises(ValidationError):
            RoomCreate(name="Test", max_members=1001)

    def test_visibility_enum_string(self):
        """Visibility accepts string value."""
        room = RoomCreate(name="Test", visibility="private")
        assert room.visibility == RoomVisibility.PRIVATE


# =============================================================================
# RoomUpdate Tests
# =============================================================================


class TestRoomUpdate:
    """Tests for RoomUpdate model."""

    def test_all_fields_optional(self):
        """All fields are optional."""
        update = RoomUpdate()
        assert update.name is None
        assert update.description is None
        assert update.visibility is None
        assert update.max_members is None
        assert update.is_archived is None

    def test_partial_update(self):
        """Can update individual fields."""
        update = RoomUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.description is None

    def test_name_constraints(self):
        """Name follows same constraints as RoomCreate."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            RoomUpdate(name="")

        with pytest.raises(ValidationError):
            RoomUpdate(name="a" * 101)

    def test_description_constraint(self):
        """Description follows same constraints."""
        with pytest.raises(ValidationError):
            RoomUpdate(description="a" * 501)

    def test_max_members_constraints(self):
        """Max members follows same constraints."""
        with pytest.raises(ValidationError):
            RoomUpdate(max_members=1)

        with pytest.raises(ValidationError):
            RoomUpdate(max_members=1001)

    def test_is_archived_boolean(self):
        """is_archived accepts boolean values."""
        update = RoomUpdate(is_archived=True)
        assert update.is_archived is True

        update = RoomUpdate(is_archived=False)
        assert update.is_archived is False


# =============================================================================
# ChatRoom Tests
# =============================================================================


class TestChatRoom:
    """Tests for ChatRoom model."""

    def test_valid_chat_room(self):
        """Valid chat room creation."""
        now = datetime.now(UTC)
        room = ChatRoom(
            id="room123",
            name="Test Room",
            owner_id="user123",
            created_at=now,
            updated_at=now,
        )
        assert room.id == "room123"
        assert room.name == "Test Room"
        assert room.owner_id == "user123"

    def test_defaults(self):
        """ChatRoom has sensible defaults."""
        now = datetime.now(UTC)
        room = ChatRoom(
            id="room123",
            name="Test Room",
            owner_id="user123",
            created_at=now,
            updated_at=now,
        )
        assert room.description is None
        assert room.visibility == RoomVisibility.PUBLIC
        assert room.max_members == 100
        assert room.member_count == 1
        assert room.is_archived is False
        assert room.invite_code is None
        assert room.invite_code_expires_at is None

    def test_generate_invite_code_length(self):
        """Invite code has correct length."""
        code = ChatRoom.generate_invite_code()
        assert len(code) == 12

    def test_generate_invite_code_custom_length(self):
        """Invite code respects custom length."""
        code = ChatRoom.generate_invite_code(length=8)
        assert len(code) == 8

        code = ChatRoom.generate_invite_code(length=20)
        assert len(code) == 20

    def test_generate_invite_code_uniqueness(self):
        """Generated codes are unique."""
        codes = [ChatRoom.generate_invite_code() for _ in range(100)]
        assert len(set(codes)) == 100

    def test_invite_only_room(self):
        """Invite-only room with invite code."""
        now = datetime.now(UTC)
        expires = now + timedelta(days=7)
        room = ChatRoom(
            id="room123",
            name="Private Room",
            owner_id="user123",
            visibility=RoomVisibility.INVITE_ONLY,
            invite_code="ABC123XYZ456",
            invite_code_expires_at=expires,
            created_at=now,
            updated_at=now,
        )
        assert room.visibility == RoomVisibility.INVITE_ONLY
        assert room.invite_code == "ABC123XYZ456"
        assert room.invite_code_expires_at == expires


# =============================================================================
# RoomResponse Tests
# =============================================================================


class TestRoomResponse:
    """Tests for RoomResponse model."""

    def test_room_response_fields(self):
        """RoomResponse has expected fields."""
        now = datetime.now(UTC)
        response = RoomResponse(
            id="room123",
            name="Test Room",
            description="A room",
            visibility=RoomVisibility.PUBLIC,
            owner_id="user123",
            member_count=5,
            max_members=100,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        assert response.id == "room123"
        assert response.user_role is None

    def test_room_response_with_user_role(self):
        """RoomResponse includes user role when provided."""
        now = datetime.now(UTC)
        response = RoomResponse(
            id="room123",
            name="Test Room",
            description=None,
            visibility=RoomVisibility.PUBLIC,
            owner_id="user123",
            member_count=5,
            max_members=100,
            is_archived=False,
            created_at=now,
            updated_at=now,
            user_role=RoomRole.ADMIN,
        )
        assert response.user_role == RoomRole.ADMIN

    def test_from_room_method(self):
        """from_room creates response from ChatRoom."""
        now = datetime.now(UTC)
        room = ChatRoom(
            id="room123",
            name="Test Room",
            description="A test room",
            visibility=RoomVisibility.PRIVATE,
            owner_id="user123",
            member_count=10,
            max_members=50,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )

        response = RoomResponse.from_room(room, user_role=RoomRole.MEMBER)

        assert response.id == room.id
        assert response.name == room.name
        assert response.description == room.description
        assert response.visibility == room.visibility
        assert response.owner_id == room.owner_id
        assert response.member_count == room.member_count
        assert response.max_members == room.max_members
        assert response.is_archived == room.is_archived
        assert response.user_role == RoomRole.MEMBER


# =============================================================================
# RoomListResponse Tests
# =============================================================================


class TestRoomListResponse:
    """Tests for RoomListResponse model."""

    def test_empty_list_response(self):
        """Empty list response with defaults."""
        response = RoomListResponse()
        assert response.rooms == []
        assert response.total == 0

    def test_list_response_with_rooms(self):
        """List response with rooms."""
        now = datetime.now(UTC)
        room_response = RoomResponse(
            id="room123",
            name="Test Room",
            description=None,
            visibility=RoomVisibility.PUBLIC,
            owner_id="user123",
            member_count=5,
            max_members=100,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        response = RoomListResponse(rooms=[room_response], total=1)
        assert len(response.rooms) == 1
        assert response.total == 1


# =============================================================================
# MemberCreate Tests
# =============================================================================


class TestMemberCreate:
    """Tests for MemberCreate model."""

    def test_valid_member_create(self):
        """Valid member creation."""
        member = MemberCreate(user_id="user123")
        assert member.user_id == "user123"
        assert member.role == RoomRole.MEMBER

    def test_member_create_with_role(self):
        """Member creation with specified role."""
        member = MemberCreate(user_id="user123", role=RoomRole.ADMIN)
        assert member.role == RoomRole.ADMIN

    def test_user_id_required(self):
        """user_id is required."""
        with pytest.raises(ValidationError):
            MemberCreate()


# =============================================================================
# MemberUpdate Tests
# =============================================================================


class TestMemberUpdate:
    """Tests for MemberUpdate model."""

    def test_valid_member_update(self):
        """Valid member update."""
        update = MemberUpdate(role=RoomRole.ADMIN)
        assert update.role == RoomRole.ADMIN

    def test_role_required(self):
        """role is required."""
        with pytest.raises(ValidationError):
            MemberUpdate()


# =============================================================================
# RoomMember Tests
# =============================================================================


class TestRoomMember:
    """Tests for RoomMember model."""

    def test_valid_room_member(self):
        """Valid room member creation."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.MEMBER,
        )
        assert member.room_id == "room123"
        assert member.user_id == "user123"
        assert member.role == RoomRole.MEMBER
        assert member.joined_at is not None
        assert member.invited_by is None

    def test_member_with_invited_by(self):
        """Member with invited_by set."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.MEMBER,
            invited_by="admin456",
        )
        assert member.invited_by == "admin456"

    def test_can_manage_members_property_owner(self):
        """Owner can manage members property."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.OWNER,
        )
        assert member.can_manage_members is True

    def test_can_manage_members_property_admin(self):
        """Admin can manage members property."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.ADMIN,
        )
        assert member.can_manage_members is True

    def test_can_manage_members_property_member(self):
        """Regular member cannot manage members."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.MEMBER,
        )
        assert member.can_manage_members is False

    def test_can_moderate_property_owner(self):
        """Owner can moderate property."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.OWNER,
        )
        assert member.can_moderate is True

    def test_can_moderate_property_member(self):
        """Regular member cannot moderate."""
        member = RoomMember(
            room_id="room123",
            user_id="user123",
            role=RoomRole.MEMBER,
        )
        assert member.can_moderate is False


# =============================================================================
# MemberResponse Tests
# =============================================================================


class TestMemberResponse:
    """Tests for MemberResponse model."""

    def test_member_response(self):
        """Valid member response."""
        now = datetime.now(UTC)
        response = MemberResponse(
            user_id="user123",
            username="testuser",
            display_name="Test User",
            role=RoomRole.MEMBER,
            joined_at=now,
        )
        assert response.user_id == "user123"
        assert response.username == "testuser"
        assert response.display_name == "Test User"

    def test_member_response_optional_fields(self):
        """Optional fields default to None."""
        now = datetime.now(UTC)
        response = MemberResponse(
            user_id="user123",
            role=RoomRole.MEMBER,
            joined_at=now,
        )
        assert response.username is None
        assert response.display_name is None


# =============================================================================
# MemberListResponse Tests
# =============================================================================


class TestMemberListResponse:
    """Tests for MemberListResponse model."""

    def test_empty_member_list(self):
        """Empty member list response."""
        response = MemberListResponse()
        assert response.members == []
        assert response.total == 0


# =============================================================================
# MessageCreate Tests
# =============================================================================


class TestMessageCreate:
    """Tests for MessageCreate model."""

    def test_valid_message_create(self):
        """Valid message creation."""
        message = MessageCreate(content="Hello, world!")
        assert message.content == "Hello, world!"

    def test_content_required(self):
        """Content is required."""
        with pytest.raises(ValidationError):
            MessageCreate()

    def test_content_min_length(self):
        """Content must be at least 1 character."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            MessageCreate(content="")

    def test_content_max_length(self):
        """Content must be at most 4096 characters."""
        with pytest.raises(ValidationError):
            MessageCreate(content="a" * 4097)

    def test_content_stripped(self):
        """Content is stripped of whitespace."""
        message = MessageCreate(content="  Hello, world!  ")
        assert message.content == "Hello, world!"

    def test_content_only_whitespace_fails(self):
        """Content with only whitespace fails validation after stripping."""
        with pytest.raises(ValidationError):
            MessageCreate(content="   ")


# =============================================================================
# ChatMessage Tests
# =============================================================================


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_valid_chat_message(self):
        """Valid chat message creation."""
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Hello, world!",
        )
        assert message.id == "msg123"
        assert message.room_id == "room123"
        assert message.sender_id == "user123"
        assert message.content == "Hello, world!"

    def test_message_defaults(self):
        """Message has sensible defaults."""
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Hello!",
        )
        assert message.created_at is not None
        assert message.edited_at is None
        assert message.is_deleted is False
        assert message.deleted_by is None

    def test_edited_message(self):
        """Message with edit timestamp."""
        now = datetime.now(UTC)
        edited = now + timedelta(minutes=5)
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Edited content",
            created_at=now,
            edited_at=edited,
        )
        assert message.edited_at == edited

    def test_deleted_message(self):
        """Soft-deleted message."""
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Original content",
            is_deleted=True,
            deleted_by="mod456",
        )
        assert message.is_deleted is True
        assert message.deleted_by == "mod456"


# =============================================================================
# MessageResponse Tests
# =============================================================================


class TestMessageResponse:
    """Tests for MessageResponse model."""

    def test_message_response(self):
        """Valid message response."""
        now = datetime.now(UTC)
        response = MessageResponse(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            sender_username="testuser",
            sender_display_name="Test User",
            content="Hello!",
            created_at=now,
        )
        assert response.id == "msg123"
        assert response.sender_username == "testuser"

    def test_message_response_defaults(self):
        """Message response has defaults."""
        now = datetime.now(UTC)
        response = MessageResponse(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Hello!",
            created_at=now,
        )
        assert response.sender_username is None
        assert response.sender_display_name is None
        assert response.edited_at is None
        assert response.is_deleted is False

    def test_from_message_normal(self):
        """from_message creates response from normal message."""
        now = datetime.now(UTC)
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Hello, world!",
            created_at=now,
        )

        response = MessageResponse.from_message(
            message,
            sender_username="testuser",
            sender_display_name="Test User",
        )

        assert response.id == message.id
        assert response.content == "Hello, world!"
        assert response.sender_username == "testuser"
        assert response.is_deleted is False

    def test_from_message_deleted(self):
        """from_message replaces content for deleted messages."""
        now = datetime.now(UTC)
        message = ChatMessage(
            id="msg123",
            room_id="room123",
            sender_id="user123",
            content="Original secret content",
            created_at=now,
            is_deleted=True,
            deleted_by="mod456",
        )

        response = MessageResponse.from_message(message)

        assert response.content == "[deleted]"
        assert response.is_deleted is True


# =============================================================================
# MessageListResponse Tests
# =============================================================================


class TestMessageListResponse:
    """Tests for MessageListResponse model."""

    def test_empty_message_list(self):
        """Empty message list response."""
        response = MessageListResponse()
        assert response.messages == []
        assert response.total == 0
        assert response.has_more is False

    def test_message_list_with_more(self):
        """Message list with has_more flag."""
        response = MessageListResponse(messages=[], total=100, has_more=True)
        assert response.has_more is True


# =============================================================================
# InviteCodeResponse Tests
# =============================================================================


class TestInviteCodeResponse:
    """Tests for InviteCodeResponse model."""

    def test_invite_code_response(self):
        """Valid invite code response."""
        expires = datetime.now(UTC) + timedelta(days=7)
        response = InviteCodeResponse(
            invite_code="ABC123XYZ456",
            expires_at=expires,
            room_id="room123",
            room_name="Test Room",
        )
        assert response.invite_code == "ABC123XYZ456"
        assert response.expires_at == expires

    def test_invite_code_no_expiry(self):
        """Invite code without expiry."""
        response = InviteCodeResponse(
            invite_code="ABC123XYZ456",
            room_id="room123",
            room_name="Test Room",
        )
        assert response.expires_at is None


# =============================================================================
# JoinRoomRequest Tests
# =============================================================================


class TestJoinRoomRequest:
    """Tests for JoinRoomRequest model."""

    def test_valid_join_request(self):
        """Valid join room request."""
        request = JoinRoomRequest(invite_code="ABC123XYZ456")
        assert request.invite_code == "ABC123XYZ456"

    def test_invite_code_min_length(self):
        """Invite code must be at least 8 characters."""
        with pytest.raises(ValidationError, match="String should have at least 8"):
            JoinRoomRequest(invite_code="SHORT")

    def test_invite_code_max_length(self):
        """Invite code must be at most 32 characters."""
        with pytest.raises(ValidationError):
            JoinRoomRequest(invite_code="a" * 33)


# =============================================================================
# JoinRoomResponse Tests
# =============================================================================


class TestJoinRoomResponse:
    """Tests for JoinRoomResponse model."""

    def test_join_room_response(self):
        """Valid join room response."""
        now = datetime.now(UTC)
        room_response = RoomResponse(
            id="room123",
            name="Test Room",
            description=None,
            visibility=RoomVisibility.INVITE_ONLY,
            owner_id="user123",
            member_count=6,
            max_members=100,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        response = JoinRoomResponse(joined=True, room=room_response)
        assert response.joined is True
        assert response.room.id == "room123"


# =============================================================================
# RoomAccessCheck Tests
# =============================================================================


class TestRoomAccessCheck:
    """Tests for RoomAccessCheck model."""

    def test_access_granted(self):
        """Access check when granted."""
        check = RoomAccessCheck(
            can_access=True,
            role=RoomRole.MEMBER,
        )
        assert check.can_access is True
        assert check.role == RoomRole.MEMBER
        assert check.reason is None

    def test_access_denied(self):
        """Access check when denied."""
        check = RoomAccessCheck(
            can_access=False,
            reason="Room is private and user is not a member",
        )
        assert check.can_access is False
        assert check.role is None
        assert check.reason == "Room is private and user is not a member"


# =============================================================================
# RoomAccessDenied Tests
# =============================================================================


class TestRoomAccessDenied:
    """Tests for RoomAccessDenied model."""

    def test_access_denied_response(self):
        """Access denied response."""
        denied = RoomAccessDenied(
            room_id="room123",
            reason="You are not a member of this room",
        )
        assert denied.error == "access_denied"
        assert denied.room_id == "room123"
        assert denied.reason == "You are not a member of this room"

    def test_access_denied_default_error(self):
        """Access denied has default error value."""
        denied = RoomAccessDenied(room_id="room123", reason="Not allowed")
        assert denied.error == "access_denied"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
