"""
Session Management API Routes

Endpoints for managing user sessions with IP and User-Agent binding.
SECURITY FIX (Audit 6 - Session 2).
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from forge.api.dependencies import ActiveUserDep, SessionServiceDep
from forge.models.session import (
    SessionListResponse,
    SessionRevokeAllRequest,
    SessionRevokeRequest,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# =============================================================================
# Response Models
# =============================================================================


class SessionRevokeResponse(BaseModel):
    """Response for session revocation."""

    success: bool
    message: str


class SessionRevokeAllResponse(BaseModel):
    """Response for revoking all sessions."""

    success: bool
    message: str
    revoked_count: int


class SessionCountResponse(BaseModel):
    """Response for session count."""

    count: int


# =============================================================================
# Session Management Endpoints
# =============================================================================


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List user sessions",
    description="Get all active sessions for the current user.",
)
async def list_sessions(
    request: Request,
    current_user: ActiveUserDep,
    session_service: SessionServiceDep,
) -> SessionListResponse:
    """
    List all active sessions for the current user.

    Returns session information including:
    - Session ID
    - Initial and last IP addresses (masked for privacy)
    - Last activity timestamp
    - Request count
    - IP and User-Agent change counts
    - Session status
    - Whether this is the current session
    """
    # Get current session JTI from request state
    token_payload = getattr(request.state, 'token_payload', None)
    current_jti = getattr(token_payload, 'jti', None) if token_payload else None

    return await session_service.get_user_sessions(
        user_id=current_user.id,
        current_jti=current_jti,
    )


@router.get(
    "/count",
    response_model=SessionCountResponse,
    summary="Get active session count",
    description="Get the number of active sessions for the current user.",
)
async def get_session_count(
    current_user: ActiveUserDep,
    session_service: SessionServiceDep,
) -> SessionCountResponse:
    """Get the number of active sessions for the current user."""
    count = await session_service.get_active_session_count(current_user.id)
    return SessionCountResponse(count=count)


@router.delete(
    "/{session_id}",
    response_model=SessionRevokeResponse,
    summary="Revoke a session",
    description="Revoke a specific session by ID. The session will be invalidated immediately.",
)
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: ActiveUserDep,
    session_service: SessionServiceDep,
    body: SessionRevokeRequest | None = None,
) -> SessionRevokeResponse:
    """
    Revoke a specific session.

    The session will be immediately invalidated. Any tokens associated
    with this session will no longer be accepted.

    You cannot revoke your current session through this endpoint.
    Use the logout endpoint instead.
    """
    # Check if trying to revoke current session
    token_payload = getattr(request.state, 'token_payload', None)
    current_jti = getattr(token_payload, 'jti', None) if token_payload else None

    if session_id == current_jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke current session. Use logout instead.",
        )

    reason = body.reason if body else None
    success = await session_service.revoke_session(
        user_id=current_user.id,
        session_jti=session_id,
        reason=reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked.",
        )

    return SessionRevokeResponse(
        success=True,
        message="Session revoked successfully.",
    )


@router.delete(
    "",
    response_model=SessionRevokeAllResponse,
    summary="Revoke all sessions",
    description="Revoke all sessions except optionally the current one.",
)
async def revoke_all_sessions(
    request: Request,
    current_user: ActiveUserDep,
    session_service: SessionServiceDep,
    body: SessionRevokeAllRequest | None = None,
) -> SessionRevokeAllResponse:
    """
    Revoke all sessions for the current user.

    By default, keeps the current session active (except_current=true).
    Set except_current=false to revoke ALL sessions including current.
    """
    # Get current session JTI
    token_payload = getattr(request.state, 'token_payload', None)
    current_jti = getattr(token_payload, 'jti', None) if token_payload else None

    # Default to keeping current session
    except_current = body.except_current if body else True
    reason = body.reason if body else None

    revoked_count = await session_service.revoke_all_sessions(
        user_id=current_user.id,
        except_current_jti=current_jti if except_current else None,
        reason=reason,
    )

    if except_current:
        message = f"Revoked {revoked_count} other session(s). Current session preserved."
    else:
        message = f"Revoked all {revoked_count} session(s)."

    return SessionRevokeAllResponse(
        success=True,
        message=message,
        revoked_count=revoked_count,
    )
