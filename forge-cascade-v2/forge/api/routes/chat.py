"""
Chat API Routes

REST endpoints for chat room management, membership, and message history.
Implements room access control with visibility and role-based permissions
(Audit 6 - Session 4).

Endpoints:
- Room Management: CRUD operations for chat rooms
- Membership: Add/remove/update room members
- Invites: Generate and use invite codes
- Messages: Retrieve message history
"""

from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from forge.api.dependencies import ActiveUserDep, AuditRepoDep
from forge.models.chat import (
    InviteCodeResponse,
    JoinRoomResponse,
    MemberCreate,
    MemberListResponse,
    MemberResponse,
    MemberUpdate,
    MessageListResponse,
    RoomCreate,
    RoomListResponse,
    RoomResponse,
    RoomRole,
    RoomUpdate,
    RoomVisibility,
)
from forge.services.chat_service import (
    ChatAccessDeniedError,
    ChatPermissionError,
    get_chat_service,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Dependencies
# =============================================================================


async def get_chat_service_dep():
    """Dependency to get chat service."""
    return get_chat_service()


ChatServiceDep = Annotated[Any, Depends(get_chat_service_dep)]


# =============================================================================
# Room Management Endpoints
# =============================================================================


@router.post(
    "/rooms",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chat room",
    description="Create a new chat room. The creating user becomes the room owner.",
)
async def create_room(
    data: RoomCreate,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> RoomResponse:
    """Create a new chat room."""
    try:
        room = await chat_service.create_room(
            owner_id=current_user.id,
            name=data.name,
            description=data.description,
            visibility=data.visibility,
            max_members=data.max_members,
        )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_room_created",
            entity_type="chat_room",
            entity_id=room.id,
            details={
                "name": room.name,
                "visibility": room.visibility.value,
            },
        )

        logger.info(
            "chat_room_created",
            room_id=room.id,
            owner_id=current_user.id,
            visibility=room.visibility.value,
        )

        return RoomResponse.from_room(room, user_role=RoomRole.OWNER)

    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_room_create_failed",
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat room",
        )


@router.get(
    "/rooms",
    response_model=RoomListResponse,
    summary="List accessible rooms",
    description="List all rooms the current user can access (public rooms and rooms they're members of).",
)
async def list_rooms(
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    include_public: bool = Query(default=True, description="Include public rooms"),
    visibility: RoomVisibility | None = Query(default=None, description="Filter by visibility"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RoomListResponse:
    """List accessible chat rooms."""
    try:
        rooms, total = await chat_service.get_user_accessible_rooms(
            user_id=current_user.id,
            include_public=include_public,
            visibility_filter=visibility,
            limit=limit,
            offset=offset,
        )

        # Get user's role in each room
        room_responses = []
        for room in rooms:
            role = await chat_service.get_user_role(room.id, current_user.id)
            room_responses.append(RoomResponse.from_room(room, user_role=role))

        return RoomListResponse(rooms=room_responses, total=total)

    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_rooms_list_failed",
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list chat rooms",
        )


@router.get(
    "/rooms/{room_id}",
    response_model=RoomResponse,
    summary="Get room details",
    description="Get details of a specific room. User must have access to the room.",
)
async def get_room(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
) -> RoomResponse:
    """Get chat room details."""
    try:
        # Verify access
        role = await chat_service.verify_access(room_id, current_user.id)

        room = await chat_service.get_room(room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found",
            )

        return RoomResponse.from_room(room, user_role=role)

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_room_get_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get chat room",
        )


@router.patch(
    "/rooms/{room_id}",
    response_model=RoomResponse,
    summary="Update room",
    description="Update room settings. Requires owner or admin role.",
)
async def update_room(
    room_id: str,
    data: RoomUpdate,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> RoomResponse:
    """Update chat room settings."""
    try:
        # Verify user has permission to update
        role = await chat_service.verify_access(room_id, current_user.id)
        if not RoomRole.can_manage_members(role):
            raise ChatPermissionError("update_room", "admin")

        room = await chat_service.update_room(room_id, data)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_room_updated",
            entity_type="chat_room",
            entity_id=room_id,
            details=data.model_dump(exclude_none=True),
        )

        return RoomResponse.from_room(room, user_role=role)

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_room_update_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chat room",
        )


@router.delete(
    "/rooms/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete room",
    description="Delete a chat room. Requires owner role.",
)
async def delete_room(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> None:
    """Delete a chat room."""
    try:
        # Verify user is owner
        role = await chat_service.verify_access(room_id, current_user.id)
        if not RoomRole.can_delete_room(role):
            raise ChatPermissionError("delete_room", "owner")

        deleted = await chat_service.delete_room(room_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_room_deleted",
            entity_type="chat_room",
            entity_id=room_id,
            details={},
        )

        logger.info(
            "chat_room_deleted",
            room_id=room_id,
            deleted_by=current_user.id,
        )

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_room_delete_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat room",
        )


# =============================================================================
# Membership Endpoints
# =============================================================================


@router.get(
    "/rooms/{room_id}/members",
    response_model=MemberListResponse,
    summary="List room members",
    description="List all members of a room. Requires room access.",
)
async def list_members(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MemberListResponse:
    """List room members."""
    try:
        # Verify access
        await chat_service.verify_access(room_id, current_user.id)

        members, total = await chat_service.get_room_members(
            room_id=room_id,
            limit=limit,
            offset=offset,
        )

        return MemberListResponse(members=members, total=total)

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_members_list_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list room members",
        )


@router.post(
    "/rooms/{room_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add member",
    description="Add a user to the room. Requires admin or owner role.",
)
async def add_member(
    room_id: str,
    data: MemberCreate,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> MemberResponse:
    """Add a member to a room."""
    try:
        member = await chat_service.add_member(
            room_id=room_id,
            admin_id=current_user.id,
            user_id=data.user_id,
            role=data.role,
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add member. User may already be a member or room is full.",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_member_added",
            entity_type="chat_room",
            entity_id=room_id,
            details={
                "added_user_id": data.user_id,
                "role": data.role.value,
            },
        )

        return MemberResponse(
            user_id=member.user_id,
            role=member.role,
            joined_at=member.joined_at,
        )

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_member_add_failed",
            room_id=room_id,
            user_id=current_user.id,
            target_user_id=data.user_id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member",
        )


@router.delete(
    "/rooms/{room_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member",
    description="Remove a member from the room. Admins can remove members, owners can remove anyone except themselves.",
)
async def remove_member(
    room_id: str,
    user_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> None:
    """Remove a member from a room."""
    try:
        # Self-removal (leaving) is always allowed
        if user_id == current_user.id:
            removed = await chat_service.leave_room(room_id, current_user.id)
        else:
            removed = await chat_service.remove_member(
                room_id=room_id,
                admin_id=current_user.id,
                user_id=user_id,
            )

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found or cannot be removed",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_member_removed",
            entity_type="chat_room",
            entity_id=room_id,
            details={
                "removed_user_id": user_id,
                "self_removal": user_id == current_user.id,
            },
        )

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_member_remove_failed",
            room_id=room_id,
            user_id=current_user.id,
            target_user_id=user_id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )


@router.patch(
    "/rooms/{room_id}/members/{user_id}",
    response_model=MemberResponse,
    summary="Update member role",
    description="Update a member's role. Only owners can promote to admin or demote admins.",
)
async def update_member_role(
    room_id: str,
    user_id: str,
    data: MemberUpdate,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> MemberResponse:
    """Update a member's role."""
    try:
        member = await chat_service.update_member_role(
            room_id=room_id,
            admin_id=current_user.id,
            user_id=user_id,
            new_role=data.role,
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_member_role_updated",
            entity_type="chat_room",
            entity_id=room_id,
            details={
                "updated_user_id": user_id,
                "new_role": data.role.value,
            },
        )

        return MemberResponse(
            user_id=member.user_id,
            role=member.role,
            joined_at=member.joined_at,
        )

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_member_role_update_failed",
            room_id=room_id,
            user_id=current_user.id,
            target_user_id=user_id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member role",
        )


# =============================================================================
# Invite Endpoints
# =============================================================================


@router.post(
    "/rooms/{room_id}/invite",
    response_model=InviteCodeResponse,
    summary="Generate invite code",
    description="Generate an invite code for an invite-only room. Requires admin or owner role.",
)
async def generate_invite_code(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
    expires_in_hours: int | None = Query(default=168, ge=1, le=720, description="Hours until expiry (1-720)"),
) -> InviteCodeResponse:
    """Generate an invite code for a room."""
    try:
        invite = await chat_service.generate_invite_code(
            room_id=room_id,
            admin_id=current_user.id,
            expires_in_hours=expires_in_hours,
        )

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate invite code. Room may not be invite-only.",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_invite_generated",
            entity_type="chat_room",
            entity_id=room_id,
            details={
                "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            },
        )

        return invite

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except ChatPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {e.action} requires {e.required_role} role",
        )
    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_invite_generate_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invite code",
        )


@router.post(
    "/join/{invite_code}",
    response_model=JoinRoomResponse,
    summary="Join room via invite",
    description="Join a room using an invite code.",
)
async def join_via_invite(
    invite_code: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> JoinRoomResponse:
    """Join a room via invite code."""
    try:
        room, member = await chat_service.join_via_invite_code(
            invite_code=invite_code,
            user_id=current_user.id,
        )

        if not room or not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite code, or you're already a member.",
            )

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_room_joined_via_invite",
            entity_type="chat_room",
            entity_id=room.id,
            details={},
        )

        return JoinRoomResponse(
            joined=True,
            room=RoomResponse.from_room(room, user_role=member.role),
        )

    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_join_via_invite_failed",
            invite_code=invite_code[:8] + "...",
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join room",
        )


@router.post(
    "/rooms/{room_id}/join",
    response_model=JoinRoomResponse,
    summary="Join public room",
    description="Join a public room directly.",
)
async def join_public_room(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    audit_repo: AuditRepoDep,
) -> JoinRoomResponse:
    """Join a public room."""
    try:
        member = await chat_service.join_room(
            room_id=room_id,
            user_id=current_user.id,
            invite_code=None,
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot join room. It may be private, full, or you're already a member.",
            )

        room = await chat_service.get_room(room_id)

        # Audit log
        await audit_repo.log_action(
            user_id=current_user.id,
            action="chat_room_joined",
            entity_type="chat_room",
            entity_id=room_id,
            details={},
        )

        return JoinRoomResponse(
            joined=True,
            room=RoomResponse.from_room(room, user_role=member.role),
        )

    except HTTPException:
        raise
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_join_public_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join room",
        )


# =============================================================================
# Message History Endpoints
# =============================================================================


@router.get(
    "/rooms/{room_id}/messages",
    response_model=MessageListResponse,
    summary="Get message history",
    description="Get message history for a room. Requires room access.",
)
async def get_messages(
    room_id: str,
    current_user: ActiveUserDep,
    chat_service: ChatServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = Query(default=None, description="Get messages before this timestamp"),
) -> MessageListResponse:
    """Get message history for a room."""
    try:
        # Verify access
        await chat_service.verify_access(room_id, current_user.id)

        messages, has_more = await chat_service.get_room_messages(
            room_id=room_id,
            limit=limit,
            before=before,
        )

        return MessageListResponse(
            messages=messages,
            total=len(messages),
            has_more=has_more,
        )

    except ChatAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {e.reason}",
        )
    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        logger.error(
            "chat_messages_get_failed",
            room_id=room_id,
            user_id=current_user.id,
            error=str(e)[:200],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )
