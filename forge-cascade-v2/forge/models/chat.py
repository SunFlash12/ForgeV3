"""
Chat Room Models

Chat room, membership, and message entities for the collaborative chat system.
Implements room access control with visibility and role-based permissions
(Audit 6 - Session 4).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum

from pydantic import Field, field_validator

from forge.models.base import ForgeModel, TimestampMixin


class RoomVisibility(str, Enum):
    """Room visibility/access level."""

    PUBLIC = "public"           # Anyone can join
    PRIVATE = "private"         # Members only (must be added by admin/owner)
    INVITE_ONLY = "invite_only" # Requires invite code to join


class RoomRole(str, Enum):
    """Member role within a room."""

    OWNER = "owner"     # Full control: delete room, manage all members
    ADMIN = "admin"     # Can manage members (except owner), moderate messages
    MEMBER = "member"   # Can read/write messages

    @classmethod
    def can_manage_members(cls, role: RoomRole) -> bool:
        """Check if role can manage (add/remove/promote) members."""
        return role in (cls.OWNER, cls.ADMIN)

    @classmethod
    def can_delete_room(cls, role: RoomRole) -> bool:
        """Check if role can delete the room."""
        return role == cls.OWNER

    @classmethod
    def can_moderate(cls, role: RoomRole) -> bool:
        """Check if role can moderate messages (delete others' messages)."""
        return role in (cls.OWNER, cls.ADMIN)

    @classmethod
    def hierarchy_value(cls, role: RoomRole) -> int:
        """Get numeric hierarchy value for role comparison."""
        hierarchy = {cls.OWNER: 100, cls.ADMIN: 50, cls.MEMBER: 10}
        return hierarchy.get(role, 0)


# =============================================================================
# Room Models
# =============================================================================


class RoomCreate(ForgeModel):
    """Schema for creating a new room."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Room display name"
    )
    description: str | None = Field(
        default=None, max_length=500, description="Room description"
    )
    visibility: RoomVisibility = Field(
        default=RoomVisibility.PUBLIC, description="Room visibility level"
    )
    max_members: int = Field(
        default=100, ge=2, le=1000, description="Maximum number of members"
    )


class RoomUpdate(ForgeModel):
    """Schema for updating a room."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    visibility: RoomVisibility | None = None
    max_members: int | None = Field(default=None, ge=2, le=1000)
    is_archived: bool | None = None


class ChatRoom(ForgeModel, TimestampMixin):
    """Complete room entity."""

    id: str = Field(description="Room UUID")
    name: str = Field(description="Room display name")
    description: str | None = Field(default=None, description="Room description")
    visibility: RoomVisibility = Field(
        default=RoomVisibility.PUBLIC, description="Room visibility level"
    )
    owner_id: str = Field(description="User ID of room owner")
    max_members: int = Field(default=100, description="Maximum members allowed")
    member_count: int = Field(default=1, description="Current member count")
    is_archived: bool = Field(default=False, description="Whether room is archived")

    # Invite code for invite-only rooms
    invite_code: str | None = Field(
        default=None, description="Invite code for invite-only rooms"
    )
    invite_code_expires_at: datetime | None = Field(
        default=None, description="When the invite code expires"
    )

    @staticmethod
    def generate_invite_code(length: int = 12) -> str:
        """Generate a cryptographically random invite code."""
        return secrets.token_urlsafe(length)[:length]


class RoomResponse(ForgeModel):
    """Public room info for API responses."""

    id: str
    name: str
    description: str | None
    visibility: RoomVisibility
    owner_id: str
    member_count: int
    max_members: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    # User's role in this room (if member)
    user_role: RoomRole | None = Field(
        default=None, description="Current user's role in this room"
    )

    @classmethod
    def from_room(
        cls, room: ChatRoom, user_role: RoomRole | None = None
    ) -> RoomResponse:
        """Create response from room entity."""
        return cls(
            id=room.id,
            name=room.name,
            description=room.description,
            visibility=room.visibility,
            owner_id=room.owner_id,
            member_count=room.member_count,
            max_members=room.max_members,
            is_archived=room.is_archived,
            created_at=room.created_at,
            updated_at=room.updated_at,
            user_role=user_role,
        )


class RoomListResponse(ForgeModel):
    """Response schema for listing rooms."""

    rooms: list[RoomResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of accessible rooms")


# =============================================================================
# Membership Models
# =============================================================================


class MemberCreate(ForgeModel):
    """Schema for adding a member to a room."""

    user_id: str = Field(description="User ID to add")
    role: RoomRole = Field(
        default=RoomRole.MEMBER, description="Role to assign"
    )


class MemberUpdate(ForgeModel):
    """Schema for updating a member's role."""

    role: RoomRole = Field(description="New role to assign")


class RoomMember(ForgeModel):
    """Room membership entity."""

    room_id: str = Field(description="Room ID")
    user_id: str = Field(description="User ID")
    role: RoomRole = Field(description="Member's role in the room")
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the user joined"
    )
    invited_by: str | None = Field(
        default=None, description="User ID who invited this member"
    )

    @property
    def can_manage_members(self) -> bool:
        """Check if this member can manage other members."""
        return RoomRole.can_manage_members(self.role)

    @property
    def can_moderate(self) -> bool:
        """Check if this member can moderate messages."""
        return RoomRole.can_moderate(self.role)


class MemberResponse(ForgeModel):
    """Public member info for API responses."""

    user_id: str
    username: str | None = None
    display_name: str | None = None
    role: RoomRole
    joined_at: datetime


class MemberListResponse(ForgeModel):
    """Response schema for listing room members."""

    members: list[MemberResponse] = Field(default_factory=list)
    total: int = Field(default=0)


# =============================================================================
# Message Models
# =============================================================================


class MessageCreate(ForgeModel):
    """Schema for creating a message."""

    content: str = Field(
        ..., min_length=1, max_length=4096, description="Message content"
    )

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        """Strip whitespace from content."""
        return v.strip()


class ChatMessage(ForgeModel):
    """Chat message entity."""

    id: str = Field(description="Message UUID")
    room_id: str = Field(description="Room ID this message belongs to")
    sender_id: str = Field(description="User ID who sent the message")
    content: str = Field(description="Message content")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the message was sent"
    )
    edited_at: datetime | None = Field(
        default=None, description="When the message was last edited"
    )
    is_deleted: bool = Field(
        default=False, description="Whether the message is soft-deleted"
    )
    deleted_by: str | None = Field(
        default=None, description="User ID who deleted the message"
    )


class MessageResponse(ForgeModel):
    """Public message info for API responses."""

    id: str
    room_id: str
    sender_id: str
    sender_username: str | None = None
    sender_display_name: str | None = None
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    is_deleted: bool = False

    @classmethod
    def from_message(
        cls,
        message: ChatMessage,
        sender_username: str | None = None,
        sender_display_name: str | None = None,
    ) -> MessageResponse:
        """Create response from message entity."""
        # If deleted, replace content
        content = message.content if not message.is_deleted else "[deleted]"
        return cls(
            id=message.id,
            room_id=message.room_id,
            sender_id=message.sender_id,
            sender_username=sender_username,
            sender_display_name=sender_display_name,
            content=content,
            created_at=message.created_at,
            edited_at=message.edited_at,
            is_deleted=message.is_deleted,
        )


class MessageListResponse(ForgeModel):
    """Response schema for listing messages."""

    messages: list[MessageResponse] = Field(default_factory=list)
    total: int = Field(default=0)
    has_more: bool = Field(default=False, description="Whether there are older messages")


# =============================================================================
# Invite Models
# =============================================================================


class InviteCodeResponse(ForgeModel):
    """Response when generating an invite code."""

    invite_code: str
    expires_at: datetime | None = None
    room_id: str
    room_name: str


class JoinRoomRequest(ForgeModel):
    """Request to join a room via invite code."""

    invite_code: str = Field(
        ..., min_length=8, max_length=32, description="Invite code"
    )


class JoinRoomResponse(ForgeModel):
    """Response after joining a room."""

    joined: bool
    room: RoomResponse


# =============================================================================
# Access Control Models
# =============================================================================


class RoomAccessCheck(ForgeModel):
    """Result of checking room access for a user."""

    can_access: bool = Field(description="Whether user can access the room")
    role: RoomRole | None = Field(
        default=None, description="User's role if they have access"
    )
    reason: str | None = Field(
        default=None, description="Reason for denial if can_access is False"
    )


class RoomAccessDenied(ForgeModel):
    """Error response when room access is denied."""

    error: str = "access_denied"
    room_id: str
    reason: str
