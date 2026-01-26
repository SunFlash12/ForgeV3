"""
Chat Repository

Repository for ChatRoom, RoomMember, and ChatMessage CRUD operations.
Implements room access control for the WebSocket chat system
(Audit 6 - Session 4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from forge.config import get_settings
from forge.database.client import Neo4jClient
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

settings = get_settings()
logger = structlog.get_logger(__name__)


class ChatRepository:
    """
    Repository for chat room entities.

    Provides CRUD operations for rooms, members, and messages
    with access control validation.
    """

    def __init__(self, client: Neo4jClient):
        """Initialize repository with database client."""
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    def _generate_id(self) -> str:
        """Generate a new unique ID."""
        return str(uuid4())

    def _now(self) -> datetime:
        """Get current UTC timestamp (timezone-aware)."""
        return datetime.now(UTC)

    # =========================================================================
    # Room Operations
    # =========================================================================

    async def create_room(
        self,
        data: RoomCreate,
        owner_id: str,
        room_id: str | None = None,
    ) -> ChatRoom:
        """
        Create a new chat room.

        Args:
            data: Room creation data
            owner_id: User ID of room owner
            room_id: Optional room ID (for on-demand creation)

        Returns:
            Created room
        """
        now = self._now()
        rid = room_id or self._generate_id()

        # Generate invite code for invite-only rooms
        invite_code = None
        invite_expires = None
        if data.visibility == RoomVisibility.INVITE_ONLY:
            invite_code = ChatRoom.generate_invite_code(settings.chat_invite_code_length)
            invite_expires = now

        query = """
        CREATE (r:ChatRoom {
            id: $id,
            name: $name,
            description: $description,
            visibility: $visibility,
            owner_id: $owner_id,
            max_members: $max_members,
            member_count: 1,
            is_archived: false,
            invite_code: $invite_code,
            invite_code_expires_at: $invite_expires,
            created_at: $now,
            updated_at: $now
        })
        WITH r
        CREATE (m:RoomMember {
            room_id: r.id,
            user_id: $owner_id,
            role: $owner_role,
            joined_at: $now,
            invited_by: null
        })
        RETURN r {.*} AS room
        """

        params = {
            "id": rid,
            "name": data.name,
            "description": data.description,
            "visibility": data.visibility.value,
            "owner_id": owner_id,
            "max_members": data.max_members,
            "invite_code": invite_code,
            "invite_expires": invite_expires.isoformat() if invite_expires else None,
            "now": now.isoformat(),
            "owner_role": RoomRole.OWNER.value,
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("room"):
            room = ChatRoom.model_validate(result["room"])
            self.logger.info(
                "room_created",
                room_id=rid,
                owner_id=owner_id,
                visibility=data.visibility.value,
            )
            return room

        raise RuntimeError(f"Failed to create room for owner {owner_id}")

    async def get_room(self, room_id: str) -> ChatRoom | None:
        """
        Get a room by ID.

        Args:
            room_id: Room ID

        Returns:
            Room if found, None otherwise
        """
        query = """
        MATCH (r:ChatRoom {id: $room_id})
        RETURN r {.*} AS room
        """

        result = await self.client.execute_single(query, {"room_id": room_id})

        if result and result.get("room"):
            return ChatRoom.model_validate(result["room"])

        return None

    async def get_room_by_invite_code(self, invite_code: str) -> ChatRoom | None:
        """
        Get a room by invite code.

        Args:
            invite_code: Invite code

        Returns:
            Room if found and code is valid, None otherwise
        """
        query = """
        MATCH (r:ChatRoom {invite_code: $invite_code})
        WHERE r.is_archived = false
        RETURN r {.*} AS room
        """

        result = await self.client.execute_single(query, {"invite_code": invite_code})

        if result and result.get("room"):
            return ChatRoom.model_validate(result["room"])

        return None

    async def update_room(
        self,
        room_id: str,
        data: RoomUpdate,
    ) -> ChatRoom | None:
        """
        Update a room.

        Args:
            room_id: Room ID
            data: Update data

        Returns:
            Updated room if found
        """
        now = self._now()

        # Build dynamic SET clause
        set_parts = ["r.updated_at = $now"]
        params: dict[str, Any] = {"room_id": room_id, "now": now.isoformat()}

        if data.name is not None:
            set_parts.append("r.name = $name")
            params["name"] = data.name
        if data.description is not None:
            set_parts.append("r.description = $description")
            params["description"] = data.description
        if data.visibility is not None:
            set_parts.append("r.visibility = $visibility")
            params["visibility"] = data.visibility.value
        if data.max_members is not None:
            set_parts.append("r.max_members = $max_members")
            params["max_members"] = data.max_members
        if data.is_archived is not None:
            set_parts.append("r.is_archived = $is_archived")
            params["is_archived"] = data.is_archived

        query = f"""
        MATCH (r:ChatRoom {{id: $room_id}})
        SET {', '.join(set_parts)}
        RETURN r {{.*}} AS room
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("room"):
            return ChatRoom.model_validate(result["room"])

        return None

    async def delete_room(self, room_id: str) -> bool:
        """
        Delete a room and all related data.

        Args:
            room_id: Room ID

        Returns:
            True if deleted
        """
        query = """
        MATCH (r:ChatRoom {id: $room_id})
        OPTIONAL MATCH (m:RoomMember {room_id: $room_id})
        OPTIONAL MATCH (msg:ChatMessage {room_id: $room_id})
        DETACH DELETE r, m, msg
        RETURN count(r) > 0 AS deleted
        """

        result = await self.client.execute_single(query, {"room_id": room_id})

        if result and result.get("deleted"):
            self.logger.info("room_deleted", room_id=room_id)
            return True

        return False

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
        if include_public:
            query = """
            MATCH (r:ChatRoom)
            WHERE r.is_archived = false
              AND (r.visibility = 'public' OR EXISTS {
                  MATCH (m:RoomMember {room_id: r.id, user_id: $user_id})
              })
            OPTIONAL MATCH (m:RoomMember {room_id: r.id, user_id: $user_id})
            RETURN r {.*} AS room, m.role AS role
            ORDER BY r.updated_at DESC
            LIMIT $limit
            """
        else:
            query = """
            MATCH (m:RoomMember {user_id: $user_id})
            MATCH (r:ChatRoom {id: m.room_id})
            WHERE r.is_archived = false
            RETURN r {.*} AS room, m.role AS role
            ORDER BY r.updated_at DESC
            LIMIT $limit
            """

        params = {"user_id": user_id, "limit": min(limit, 100)}
        results = await self.client.execute(query, params)

        rooms = []
        for r in results:
            if r.get("room"):
                room = ChatRoom.model_validate(r["room"])
                role = RoomRole(r["role"]) if r.get("role") else None
                rooms.append((room, role))

        return rooms

    # =========================================================================
    # Membership Operations
    # =========================================================================

    async def add_member(
        self,
        room_id: str,
        user_id: str,
        role: RoomRole = RoomRole.MEMBER,
        invited_by: str | None = None,
    ) -> RoomMember | None:
        """
        Add a member to a room.

        Args:
            room_id: Room ID
            user_id: User ID to add
            role: Role to assign
            invited_by: User ID who invited them

        Returns:
            Created member if successful
        """
        now = self._now()

        query = """
        MATCH (r:ChatRoom {id: $room_id})
        WHERE r.is_archived = false
          AND r.member_count < r.max_members
          AND NOT EXISTS {
              MATCH (existing:RoomMember {room_id: $room_id, user_id: $user_id})
          }
        CREATE (m:RoomMember {
            room_id: $room_id,
            user_id: $user_id,
            role: $role,
            joined_at: $now,
            invited_by: $invited_by
        })
        SET r.member_count = r.member_count + 1,
            r.updated_at = $now
        RETURN m {.*} AS member
        """

        params = {
            "room_id": room_id,
            "user_id": user_id,
            "role": role.value,
            "now": now.isoformat(),
            "invited_by": invited_by,
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("member"):
            self.logger.info(
                "member_added",
                room_id=room_id,
                user_id=user_id,
                role=role.value,
            )
            return RoomMember.model_validate(result["member"])

        return None

    async def remove_member(self, room_id: str, user_id: str) -> bool:
        """
        Remove a member from a room.

        Args:
            room_id: Room ID
            user_id: User ID to remove

        Returns:
            True if removed
        """
        now = self._now()

        query = """
        MATCH (m:RoomMember {room_id: $room_id, user_id: $user_id})
        MATCH (r:ChatRoom {id: $room_id})
        DELETE m
        SET r.member_count = r.member_count - 1,
            r.updated_at = $now
        RETURN count(m) > 0 AS removed
        """

        result = await self.client.execute_single(query, {
            "room_id": room_id,
            "user_id": user_id,
            "now": now.isoformat(),
        })

        if result and result.get("removed"):
            self.logger.info("member_removed", room_id=room_id, user_id=user_id)
            return True

        return False

    async def get_member(self, room_id: str, user_id: str) -> RoomMember | None:
        """
        Get a specific member's info.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            Member if found
        """
        query = """
        MATCH (m:RoomMember {room_id: $room_id, user_id: $user_id})
        RETURN m {.*} AS member
        """

        result = await self.client.execute_single(query, {
            "room_id": room_id,
            "user_id": user_id,
        })

        if result and result.get("member"):
            return RoomMember.model_validate(result["member"])

        return None

    async def get_room_members(
        self,
        room_id: str,
        limit: int = 100,
    ) -> list[RoomMember]:
        """
        Get all members of a room.

        Args:
            room_id: Room ID
            limit: Maximum members to return

        Returns:
            List of members
        """
        query = """
        MATCH (m:RoomMember {room_id: $room_id})
        RETURN m {.*} AS member
        ORDER BY m.joined_at ASC
        LIMIT $limit
        """

        results = await self.client.execute(query, {
            "room_id": room_id,
            "limit": min(limit, 1000),
        })

        members = []
        for r in results:
            if r.get("member"):
                members.append(RoomMember.model_validate(r["member"]))

        return members

    async def update_member_role(
        self,
        room_id: str,
        user_id: str,
        new_role: RoomRole,
    ) -> bool:
        """
        Update a member's role.

        Args:
            room_id: Room ID
            user_id: User ID
            new_role: New role to assign

        Returns:
            True if updated
        """
        query = """
        MATCH (m:RoomMember {room_id: $room_id, user_id: $user_id})
        WHERE m.role <> 'owner'
        SET m.role = $role
        RETURN count(m) > 0 AS updated
        """

        result = await self.client.execute_single(query, {
            "room_id": room_id,
            "user_id": user_id,
            "role": new_role.value,
        })

        if result and result.get("updated"):
            self.logger.info(
                "member_role_updated",
                room_id=room_id,
                user_id=user_id,
                new_role=new_role.value,
            )
            return True

        return False

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
            Access check result with reason if denied
        """
        query = """
        OPTIONAL MATCH (r:ChatRoom {id: $room_id})
        OPTIONAL MATCH (m:RoomMember {room_id: $room_id, user_id: $user_id})
        RETURN r {.*} AS room, m.role AS role
        """

        result = await self.client.execute_single(query, {
            "room_id": room_id,
            "user_id": user_id,
        })

        if not result or not result.get("room"):
            # Room doesn't exist - allow creation on-demand
            return RoomAccessCheck(
                can_access=True,
                role=None,
                reason="room_not_found"
            )

        room_data = result["room"]
        role_str = result.get("role")
        visibility = room_data.get("visibility", "public")
        is_archived = room_data.get("is_archived", False)

        if is_archived:
            return RoomAccessCheck(
                can_access=False,
                role=None,
                reason="Room is archived"
            )

        # If user is a member, they have access
        if role_str:
            return RoomAccessCheck(
                can_access=True,
                role=RoomRole(role_str),
                reason=None
            )

        # Check visibility
        if visibility == RoomVisibility.PUBLIC.value:
            # Public rooms allow anyone to join
            return RoomAccessCheck(
                can_access=True,
                role=None,
                reason=None
            )

        # Private or invite-only - no access
        return RoomAccessCheck(
            can_access=False,
            role=None,
            reason="Room is private. You must be invited to join."
        )

    async def get_user_role(
        self,
        room_id: str,
        user_id: str,
    ) -> RoomRole | None:
        """
        Get a user's role in a room.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            Role if member, None otherwise
        """
        member = await self.get_member(room_id, user_id)
        return member.role if member else None

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
        now = self._now()
        msg_id = self._generate_id()

        query = """
        CREATE (m:ChatMessage {
            id: $id,
            room_id: $room_id,
            sender_id: $sender_id,
            content: $content,
            created_at: $now,
            edited_at: null,
            is_deleted: false,
            deleted_by: null
        })
        RETURN m {.*} AS message
        """

        params = {
            "id": msg_id,
            "room_id": room_id,
            "sender_id": sender_id,
            "content": content,
            "now": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("message"):
            return ChatMessage.model_validate(result["message"])

        raise RuntimeError(f"Failed to save message in room {room_id}")

    async def get_room_messages(
        self,
        room_id: str,
        limit: int = 50,
        before: datetime | None = None,
    ) -> tuple[list[ChatMessage], bool]:
        """
        Get messages in a room.

        Args:
            room_id: Room ID
            limit: Maximum messages to return
            before: Only get messages before this timestamp

        Returns:
            Tuple of (messages, has_more)
        """
        # Get one extra to check if there are more
        actual_limit = min(limit, 500) + 1

        if before:
            query = """
            MATCH (m:ChatMessage {room_id: $room_id})
            WHERE m.created_at < $before
            RETURN m {.*} AS message
            ORDER BY m.created_at DESC
            LIMIT $limit
            """
            params = {
                "room_id": room_id,
                "before": before.isoformat(),
                "limit": actual_limit,
            }
        else:
            query = """
            MATCH (m:ChatMessage {room_id: $room_id})
            RETURN m {.*} AS message
            ORDER BY m.created_at DESC
            LIMIT $limit
            """
            params = {
                "room_id": room_id,
                "limit": actual_limit,
            }

        results = await self.client.execute(query, params)

        messages = []
        for r in results:
            if r.get("message"):
                messages.append(ChatMessage.model_validate(r["message"]))

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # Reverse to get chronological order
        messages.reverse()

        return messages, has_more

    async def delete_message(
        self,
        message_id: str,
        deleted_by: str,
    ) -> bool:
        """
        Soft-delete a message.

        Args:
            message_id: Message ID
            deleted_by: User ID who deleted it

        Returns:
            True if deleted
        """
        now = self._now()

        query = """
        MATCH (m:ChatMessage {id: $message_id})
        WHERE m.is_deleted = false
        SET m.is_deleted = true,
            m.deleted_by = $deleted_by,
            m.edited_at = $now
        RETURN count(m) > 0 AS deleted
        """

        result = await self.client.execute_single(query, {
            "message_id": message_id,
            "deleted_by": deleted_by,
            "now": now.isoformat(),
        })

        if result and result.get("deleted"):
            self.logger.info(
                "message_deleted",
                message_id=message_id,
                deleted_by=deleted_by,
            )
            return True

        return False

    async def get_message(self, message_id: str) -> ChatMessage | None:
        """
        Get a message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message if found
        """
        query = """
        MATCH (m:ChatMessage {id: $message_id})
        RETURN m {.*} AS message
        """

        result = await self.client.execute_single(query, {"message_id": message_id})

        if result and result.get("message"):
            return ChatMessage.model_validate(result["message"])

        return None

    # =========================================================================
    # Invite Code Operations
    # =========================================================================

    async def regenerate_invite_code(
        self,
        room_id: str,
        expires_hours: int | None = None,
    ) -> str | None:
        """
        Regenerate the invite code for a room.

        Args:
            room_id: Room ID
            expires_hours: Hours until expiry (None for no expiry)

        Returns:
            New invite code if successful
        """
        now = self._now()
        new_code = ChatRoom.generate_invite_code(settings.chat_invite_code_length)

        expires_at = None
        if expires_hours:
            from datetime import timedelta
            expires_at = now + timedelta(hours=expires_hours)

        query = """
        MATCH (r:ChatRoom {id: $room_id})
        SET r.invite_code = $invite_code,
            r.invite_code_expires_at = $expires_at,
            r.updated_at = $now
        RETURN r.invite_code AS code
        """

        result = await self.client.execute_single(query, {
            "room_id": room_id,
            "invite_code": new_code,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "now": now.isoformat(),
        })

        if result and result.get("code"):
            self.logger.info("invite_code_regenerated", room_id=room_id)
            code: str = result["code"]
            return code

        return None
