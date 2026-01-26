"""
Chat Service

Business logic layer for chat room operations including
access control, membership management, and message handling
(Audit 6 - Session 4).
"""

from __future__ import annotations

from datetime import datetime

import structlog

from forge.config import get_settings
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
from forge.repositories.audit_repository import AuditRepository
from forge.repositories.chat_repository import ChatRepository

settings = get_settings()
logger = structlog.get_logger(__name__)


class ChatAccessDeniedError(Exception):
    """User does not have access to the room."""

    def __init__(self, room_id: str, reason: str):
        self.room_id = room_id
        self.reason = reason
        super().__init__(f"Access denied to room {room_id}: {reason}")


class ChatPermissionError(Exception):
    """User does not have permission for this action."""

    def __init__(self, action: str, required_role: str):
        self.action = action
        self.required_role = required_role
        super().__init__(f"Permission denied: {action} requires {required_role} role")


class ChatService:
    """
    Service for chat room operations.

    Handles room creation, membership, access control, and messaging
    with proper authorization checks.
    """

    def __init__(
        self,
        chat_repo: ChatRepository,
        audit_repo: AuditRepository | None = None,
    ):
        """
        Initialize chat service.

        Args:
            chat_repo: Chat repository for database operations
            audit_repo: Audit repository for logging (optional)
        """
        self._chat_repo = chat_repo
        self._audit_repo = audit_repo
        self.logger = structlog.get_logger(self.__class__.__name__)

    # =========================================================================
    # Room Operations
    # =========================================================================

    async def create_room(
        self,
        owner_id: str,
        name: str,
        description: str | None = None,
        visibility: RoomVisibility = RoomVisibility.PUBLIC,
        max_members: int = 100,
    ) -> ChatRoom:
        """
        Create a new chat room.

        Args:
            owner_id: User ID of room creator/owner
            name: Room display name
            description: Room description
            visibility: Room visibility level
            max_members: Maximum members allowed

        Returns:
            Created room
        """
        data = RoomCreate(
            name=name,
            description=description,
            visibility=visibility,
            max_members=max_members,
        )

        room = await self._chat_repo.create_room(data, owner_id)

        # Audit log
        if self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=owner_id,
                target_user_id=owner_id,
                action="room_created",
                details={
                    "room_id": room.id,
                    "room_name": name,
                    "visibility": visibility.value,
                },
            )

        return room

    async def get_or_create_room(
        self,
        room_id: str,
        user_id: str,
    ) -> ChatRoom:
        """
        Get a room or create it on-demand.

        Used for backwards compatibility - first user to access
        a non-existent room becomes the owner.

        Args:
            room_id: Room ID to get or create
            user_id: User ID requesting access

        Returns:
            Existing or newly created room
        """
        room = await self._chat_repo.get_room(room_id)

        if room:
            return room

        # Create room on-demand with default settings
        # First user becomes owner, room is PUBLIC by default
        self.logger.info(
            "room_created_on_demand",
            room_id=room_id,
            owner_id=user_id,
        )

        data = RoomCreate(
            name=f"Room {room_id[:8]}",  # Default name from ID
            description=None,
            visibility=RoomVisibility.PUBLIC,
            max_members=settings.chat_max_room_members,
        )

        return await self._chat_repo.create_room(data, user_id, room_id=room_id)

    async def update_room(
        self,
        room_id: str,
        user_id: str,
        data: RoomUpdate,
    ) -> ChatRoom:
        """
        Update a room.

        Args:
            room_id: Room ID
            user_id: User ID making the update
            data: Update data

        Returns:
            Updated room

        Raises:
            ChatPermissionError: If user is not owner/admin
        """
        # Check permission
        role = await self._chat_repo.get_user_role(room_id, user_id)

        if not role or role not in (RoomRole.OWNER, RoomRole.ADMIN):
            raise ChatPermissionError("update_room", "owner or admin")

        room = await self._chat_repo.update_room(room_id, data)

        if room and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=user_id,
                action="room_updated",
                details={
                    "room_id": room_id,
                    "changes": data.model_dump(exclude_none=True),
                },
            )

        return room

    async def delete_room(
        self,
        room_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a room.

        Args:
            room_id: Room ID
            user_id: User ID requesting deletion

        Returns:
            True if deleted

        Raises:
            ChatPermissionError: If user is not owner
        """
        # Only owner can delete
        role = await self._chat_repo.get_user_role(room_id, user_id)

        if role != RoomRole.OWNER:
            raise ChatPermissionError("delete_room", "owner")

        deleted: bool = await self._chat_repo.delete_room(room_id)

        if deleted and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=user_id,
                action="room_deleted",
                details={"room_id": room_id},
            )

        return deleted

    async def get_room(self, room_id: str) -> ChatRoom | None:
        """Get a room by ID."""
        return await self._chat_repo.get_room(room_id)

    async def get_user_rooms(
        self,
        user_id: str,
        include_public: bool = True,
        limit: int = 50,
    ) -> list[tuple[ChatRoom, RoomRole | None]]:
        """
        Get rooms accessible to a user.

        Args:
            user_id: User ID
            include_public: Whether to include public rooms
            limit: Maximum rooms to return

        Returns:
            List of (room, user_role) tuples
        """
        rooms: list[tuple[ChatRoom, RoomRole | None]] = await self._chat_repo.get_user_rooms(
            user_id, include_public, limit
        )
        return rooms

    # =========================================================================
    # Access Control
    # =========================================================================

    async def check_access(
        self,
        room_id: str,
        user_id: str,
    ) -> RoomAccessCheck:
        """
        Check if a user can access a room.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            Access check result
        """
        return await self._chat_repo.check_access(room_id, user_id)

    async def verify_access(
        self,
        room_id: str,
        user_id: str,
    ) -> RoomRole | None:
        """
        Verify user has access and return their role.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            User's role (or None for public room access)

        Raises:
            ChatAccessDeniedError: If access is denied
        """
        access = await self.check_access(room_id, user_id)

        if not access.can_access:
            raise ChatAccessDeniedError(room_id, access.reason or "Access denied")

        return access.role

    # =========================================================================
    # Membership Operations
    # =========================================================================

    async def join_room(
        self,
        room_id: str,
        user_id: str,
        invite_code: str | None = None,
    ) -> RoomMember | None:
        """
        Join a room.

        Args:
            room_id: Room ID
            user_id: User ID joining
            invite_code: Invite code for invite-only rooms

        Returns:
            Member record if joined

        Raises:
            ChatAccessDeniedError: If cannot join
        """
        room = await self._chat_repo.get_room(room_id)

        if not room:
            raise ChatAccessDeniedError(room_id, "Room not found")

        if room.is_archived:
            raise ChatAccessDeniedError(room_id, "Room is archived")

        # Check if already a member
        existing = await self._chat_repo.get_member(room_id, user_id)
        if existing:
            return existing  # Already a member

        # Check visibility rules
        if room.visibility == RoomVisibility.PRIVATE:
            raise ChatAccessDeniedError(
                room_id, "Private room - must be added by admin"
            )

        if room.visibility == RoomVisibility.INVITE_ONLY:
            if not invite_code:
                raise ChatAccessDeniedError(
                    room_id, "Invite code required"
                )
            if room.invite_code != invite_code:
                raise ChatAccessDeniedError(
                    room_id, "Invalid invite code"
                )

        # Add as member
        member = await self._chat_repo.add_member(
            room_id, user_id, RoomRole.MEMBER
        )

        if member and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=user_id,
                action="room_joined",
                details={"room_id": room_id},
            )

        return member

    async def join_with_invite(
        self,
        invite_code: str,
        user_id: str,
    ) -> tuple[ChatRoom, RoomMember] | None:
        """
        Join a room using an invite code.

        Args:
            invite_code: Invite code
            user_id: User ID joining

        Returns:
            Tuple of (room, member) if joined

        Raises:
            ChatAccessDeniedError: If invite is invalid
        """
        room = await self._chat_repo.get_room_by_invite_code(invite_code)

        if not room:
            raise ChatAccessDeniedError("", "Invalid invite code")

        member = await self.join_room(room.id, user_id, invite_code)

        return (room, member) if member else None

    async def leave_room(
        self,
        room_id: str,
        user_id: str,
    ) -> bool:
        """
        Leave a room.

        Args:
            room_id: Room ID
            user_id: User ID leaving

        Returns:
            True if left

        Note:
            Owner cannot leave - must transfer ownership or delete room
        """
        role = await self._chat_repo.get_user_role(room_id, user_id)

        if role == RoomRole.OWNER:
            raise ChatPermissionError(
                "leave_room",
                "Owner cannot leave. Transfer ownership or delete the room."
            )

        removed: bool = await self._chat_repo.remove_member(room_id, user_id)

        if removed and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=user_id,
                action="room_left",
                details={"room_id": room_id},
            )

        return removed

    async def add_member(
        self,
        room_id: str,
        admin_id: str,
        user_id: str,
        role: RoomRole = RoomRole.MEMBER,
    ) -> RoomMember | None:
        """
        Add a member to a room.

        Args:
            room_id: Room ID
            admin_id: User ID of admin adding the member
            user_id: User ID to add
            role: Role to assign (cannot assign OWNER)

        Returns:
            Member record if added

        Raises:
            ChatPermissionError: If admin lacks permission
        """
        # Check admin permission
        admin_role = await self._chat_repo.get_user_role(room_id, admin_id)

        if not admin_role or not RoomRole.can_manage_members(admin_role):
            raise ChatPermissionError("add_member", "admin or owner")

        # Cannot assign owner role
        if role == RoomRole.OWNER:
            raise ChatPermissionError("add_member", "Cannot assign owner role")

        # Admin cannot add another admin unless they're owner
        if role == RoomRole.ADMIN and admin_role != RoomRole.OWNER:
            raise ChatPermissionError("add_admin", "owner")

        member = await self._chat_repo.add_member(
            room_id, user_id, role, invited_by=admin_id
        )

        if member and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=admin_id,
                target_user_id=user_id,
                action="member_added",
                details={
                    "room_id": room_id,
                    "role": role.value,
                },
            )

        return member

    async def remove_member(
        self,
        room_id: str,
        admin_id: str,
        user_id: str,
    ) -> bool:
        """
        Remove a member from a room (kick).

        Args:
            room_id: Room ID
            admin_id: User ID of admin removing the member
            user_id: User ID to remove

        Returns:
            True if removed

        Raises:
            ChatPermissionError: If admin lacks permission
        """
        # Check admin permission
        admin_role = await self._chat_repo.get_user_role(room_id, admin_id)

        if not admin_role or not RoomRole.can_manage_members(admin_role):
            raise ChatPermissionError("remove_member", "admin or owner")

        # Check target's role
        target_role = await self._chat_repo.get_user_role(room_id, user_id)

        if not target_role:
            return False  # Not a member

        # Cannot remove owner
        if target_role == RoomRole.OWNER:
            raise ChatPermissionError("remove_owner", "Cannot remove owner")

        # Admin cannot remove another admin unless they're owner
        if target_role == RoomRole.ADMIN and admin_role != RoomRole.OWNER:
            raise ChatPermissionError("remove_admin", "owner")

        removed: bool = await self._chat_repo.remove_member(room_id, user_id)

        if removed and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=admin_id,
                target_user_id=user_id,
                action="member_removed",
                details={"room_id": room_id},
            )

        return removed

    async def update_member_role(
        self,
        room_id: str,
        owner_id: str,
        user_id: str,
        new_role: RoomRole,
    ) -> bool:
        """
        Update a member's role.

        Args:
            room_id: Room ID
            owner_id: User ID of owner making the change
            user_id: User ID to update
            new_role: New role to assign

        Returns:
            True if updated

        Raises:
            ChatPermissionError: If requester is not owner
        """
        # Only owner can change roles
        requester_role = await self._chat_repo.get_user_role(room_id, owner_id)

        if requester_role != RoomRole.OWNER:
            raise ChatPermissionError("update_role", "owner")

        # Cannot change to owner
        if new_role == RoomRole.OWNER:
            raise ChatPermissionError("transfer_ownership", "Use transfer_ownership()")

        updated: bool = await self._chat_repo.update_member_role(room_id, user_id, new_role)

        if updated and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=owner_id,
                target_user_id=user_id,
                action="member_role_changed",
                details={
                    "room_id": room_id,
                    "new_role": new_role.value,
                },
            )

        return updated

    async def get_room_members(
        self,
        room_id: str,
        limit: int = 100,
    ) -> list[RoomMember]:
        """Get all members of a room."""
        members: list[RoomMember] = await self._chat_repo.get_room_members(room_id, limit)
        return members

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def save_message(
        self,
        room_id: str,
        sender_id: str,
        content: str,
    ) -> ChatMessage:
        """
        Save a chat message.

        Args:
            room_id: Room ID
            sender_id: Sender user ID
            content: Message content

        Returns:
            Saved message
        """
        # Truncate if too long
        max_len = settings.chat_message_max_length
        if len(content) > max_len:
            content = content[:max_len]

        return await self._chat_repo.save_message(room_id, sender_id, content)

    async def get_room_messages(
        self,
        room_id: str,
        user_id: str,
        limit: int = 50,
        before: datetime | None = None,
    ) -> tuple[list[ChatMessage], bool]:
        """
        Get messages in a room.

        Args:
            room_id: Room ID
            user_id: User ID requesting (for access check)
            limit: Maximum messages to return
            before: Only get messages before this timestamp

        Returns:
            Tuple of (messages, has_more)

        Raises:
            ChatAccessDeniedError: If user cannot access room
        """
        await self.verify_access(room_id, user_id)

        limit = min(limit, settings.chat_history_default_limit)
        messages: tuple[list[ChatMessage], bool] = await self._chat_repo.get_room_messages(room_id, limit, before)
        return messages

    async def delete_message(
        self,
        message_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a message.

        Args:
            message_id: Message ID
            user_id: User ID requesting deletion

        Returns:
            True if deleted

        Raises:
            ChatPermissionError: If user cannot delete the message
        """
        message = await self._chat_repo.get_message(message_id)

        if not message:
            return False

        # Check if user can delete
        if message.sender_id == user_id:
            # Author can delete their own messages
            pass
        else:
            # Check if user is admin/owner of the room
            role = await self._chat_repo.get_user_role(message.room_id, user_id)
            if not role or not RoomRole.can_moderate(role):
                raise ChatPermissionError(
                    "delete_message", "message author, admin, or owner"
                )

        deleted: bool = await self._chat_repo.delete_message(message_id, user_id)

        if deleted and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=message.sender_id,
                action="message_deleted",
                details={
                    "message_id": message_id,
                    "room_id": message.room_id,
                },
            )

        return deleted

    # =========================================================================
    # Invite Code Operations
    # =========================================================================

    async def generate_invite_code(
        self,
        room_id: str,
        user_id: str,
        expires_hours: int | None = None,
    ) -> str | None:
        """
        Generate a new invite code for a room.

        Args:
            room_id: Room ID
            user_id: User ID requesting (must be admin/owner)
            expires_hours: Hours until expiry

        Returns:
            New invite code

        Raises:
            ChatPermissionError: If user lacks permission
        """
        role = await self._chat_repo.get_user_role(room_id, user_id)

        if not role or not RoomRole.can_manage_members(role):
            raise ChatPermissionError("generate_invite", "admin or owner")

        expires = expires_hours or settings.chat_invite_expiry_hours
        invite_code: str | None = await self._chat_repo.regenerate_invite_code(room_id, expires)

        if invite_code and self._audit_repo:
            await self._audit_repo.log_user_action(
                actor_id=user_id,
                target_user_id=user_id,
                action="invite_code_generated",
                details={
                    "room_id": room_id,
                    "expires_hours": expires,
                },
            )

        return invite_code


# Global service instance
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Get the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        # Lazy initialization - will be properly set by dependency injection
        raise RuntimeError("Chat service not initialized. Use dependency injection.")
    return _chat_service


def set_chat_service(service: ChatService) -> None:
    """Set the global chat service instance."""
    global _chat_service
    _chat_service = service
