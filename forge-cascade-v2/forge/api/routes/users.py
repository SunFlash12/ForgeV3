"""
Users API Routes

Endpoints for user management, activity tracking, and admin operations.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    ActiveUserDep,
    AdminUserDep,
    AuditRepoDep,
    CapsuleRepoDep,
    CorrelationIdDep,
    GovernanceRepoDep,
    UserRepoDep,
)
from forge.api.routes.auth import UserResponse
from forge.models.user import UserRole

router = APIRouter(prefix="/users", tags=["users"])


# =============================================================================
# Response Models
# =============================================================================


class UserListResponse(BaseModel):
    """Paginated user list response."""

    users: list[UserResponse]
    total: int
    page: int
    per_page: int


class UserSearchResult(BaseModel):
    """User search result item."""

    id: str
    username: str
    display_name: str | None
    trust_level: str
    created_at: str


class UserSearchResponse(BaseModel):
    """User search response."""

    users: list[UserSearchResult]


class UserActivityItem(BaseModel):
    """Single activity item."""

    id: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    timestamp: str


class UserActivityResponse(BaseModel):
    """User activity timeline."""

    user_id: str
    activities: list[UserActivityItem]
    total: int


class UserCapsulesResponse(BaseModel):
    """User's capsules summary."""

    user_id: str
    capsule_count: int
    recent_capsules: list[dict[str, Any]]


class UserGovernanceResponse(BaseModel):
    """User's governance participation."""

    user_id: str
    proposals_created: int
    votes_cast: int
    recent_proposals: list[dict[str, Any]]
    recent_votes: list[dict[str, Any]]


class UpdateTrustRequest(BaseModel):
    """Request to update user trust level."""

    trust_flame: int = Field(..., ge=0, le=100)
    reason: str = Field(..., min_length=5)


class AdminUpdateUserRequest(BaseModel):
    """Admin request to update user."""

    role: UserRole | None = None
    is_active: bool | None = None
    trust_flame: int | None = Field(None, ge=0, le=100)


# =============================================================================
# User Endpoints
# =============================================================================


@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    current_user: ActiveUserDep,
    user_repo: UserRepoDep,
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
) -> UserSearchResponse:
    """
    Search for users by username or display name.

    Available to all authenticated users for features like delegation,
    mentions, and collaboration. Returns public user information only.
    """
    from forge.models.base import TrustLevel

    users = await user_repo.search(query_str=q, limit=limit)

    return UserSearchResponse(
        users=[
            UserSearchResult(
                id=u.id,
                username=u.username,
                display_name=u.display_name,
                trust_level=TrustLevel.from_value(u.trust_flame).name
                if u.trust_flame is not None
                else "UNKNOWN",
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in users
        ]
    )


@router.get("/", response_model=UserListResponse)
async def list_users(
    admin: AdminUserDep,
    user_repo: UserRepoDep,
    page: int = Query(default=1, ge=1, le=10000),  # Max page limit to prevent DoS
    per_page: int = Query(default=20, ge=1, le=100),
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> UserListResponse:
    """
    List all users (admin only).

    Supports filtering by role and active status.
    """
    offset = (page - 1) * per_page

    filters: dict[str, str | bool] = {}
    if role:
        filters["role"] = role.value
    if is_active is not None:
        filters["is_active"] = is_active

    users, total = await user_repo.list_users(offset=offset, limit=per_page, filters=filters)

    return UserListResponse(
        users=[UserResponse.from_user(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: ActiveUserDep,
    user_repo: UserRepoDep,
) -> UserResponse:
    """
    Get user by ID.

    Regular users can only view their own profile.
    Admins can view any user.
    """
    from forge.security.authorization import is_admin

    # Check permissions - use consistent role comparison
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own profile",
        )

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.from_user(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    request: AdminUpdateUserRequest,
    admin: AdminUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> UserResponse:
    """
    Update user (admin only).

    Can update role, active status, and trust level.
    """
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Build updates dict for audit logging and track if anything changed
    updates: dict[str, Any] = {}
    if request.role is not None:
        updates["role"] = request.role.value
    if request.is_active is not None:
        updates["is_active"] = request.is_active
    if request.trust_flame is not None:
        updates["trust_flame"] = request.trust_flame

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided",
        )

    # Apply individual field updates since UserUpdate only covers profile fields
    updated_user = user
    for field_name, field_value in updates.items():
        result = await user_repo.update_field(user_id, field_name, field_value)
        if result is not None:
            updated_user = result

    # Audit log
    await audit_repo.log_action(
        action="admin_update_user",
        entity_type="user",
        entity_id=user_id,
        user_id=admin.id,
        details={"updates": updates},
        correlation_id=correlation_id,
    )

    return UserResponse.from_user(updated_user)


@router.get("/{user_id}/capsules", response_model=UserCapsulesResponse)
async def get_user_capsules(
    user_id: str,
    current_user: ActiveUserDep,
    user_repo: UserRepoDep,
    capsule_repo: CapsuleRepoDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> UserCapsulesResponse:
    """
    Get user's capsules.

    Regular users can only view their own capsules.
    Admins can view any user's capsules.
    """
    from forge.security.authorization import is_admin

    # SECURITY FIX (Audit 2): Add IDOR protection
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own capsules",
        )

    # Verify user exists
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get capsules
    capsules, total = await capsule_repo.list_capsules(
        offset=0,
        limit=limit,
        filters={"owner_id": user_id},
    )

    return UserCapsulesResponse(
        user_id=user_id,
        capsule_count=total,
        recent_capsules=[
            {
                "id": c.id,
                "title": c.title,
                "type": c.type.value if hasattr(c.type, "value") else c.type,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in capsules
        ],
    )


@router.get("/{user_id}/activity", response_model=UserActivityResponse)
async def get_user_activity(
    user_id: str,
    current_user: ActiveUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> UserActivityResponse:
    """
    Get user's activity timeline.

    Regular users can only view their own activity.
    """
    from forge.security.authorization import is_admin

    # Check permissions - use consistent role comparison
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own activity",
        )

    # Verify user exists
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get activity from audit log
    audit_events = await audit_repo.get_by_actor(actor_id=user_id, limit=limit)

    return UserActivityResponse(
        user_id=user_id,
        activities=[
            UserActivityItem(
                id=a.id,
                action=a.action,
                entity_type=a.resource_type,
                entity_id=a.resource_id,
                details=a.details,
                timestamp=a.timestamp.isoformat() if a.timestamp else "",
            )
            for a in audit_events
        ],
        total=len(audit_events),
    )


@router.get("/{user_id}/governance", response_model=UserGovernanceResponse)
async def get_user_governance(
    user_id: str,
    current_user: ActiveUserDep,
    user_repo: UserRepoDep,
    governance_repo: GovernanceRepoDep,
    limit: int = Query(default=10, ge=1, le=50),
) -> UserGovernanceResponse:
    """
    Get user's governance participation.

    Regular users can only view their own governance participation.
    Admins can view any user's governance participation.

    Note: For full transparency, governance proposals and votes are
    publicly visible through the /governance endpoints.
    """
    from forge.security.authorization import is_admin

    # SECURITY FIX (Audit 2): Add IDOR protection
    if current_user.id != user_id and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own governance participation",
        )

    # Verify user exists
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get proposals created by user
    proposals = await governance_repo.get_by_proposer(proposer_id=user_id, limit=limit)

    # Get votes cast by user
    votes = await governance_repo.get_voter_history(voter_id=user_id, limit=limit)

    return UserGovernanceResponse(
        user_id=user_id,
        proposals_created=len(proposals),
        votes_cast=len(votes),
        recent_proposals=[
            {
                "id": p.id,
                "title": p.title,
                "status": p.status.value if hasattr(p.status, "value") else p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in proposals[:5]
        ],
        recent_votes=[
            {
                "proposal_id": v.proposal_id,
                "choice": v.choice.value if hasattr(v.choice, "value") else v.choice,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in votes[:5]
        ],
    )


@router.put("/{user_id}/trust", response_model=UserResponse)
async def update_user_trust(
    user_id: str,
    request: UpdateTrustRequest,
    admin: AdminUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> UserResponse:
    """
    Update user's trust level (admin only).

    Requires a reason for the change.
    """
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    old_trust = user.trust_flame

    # Update trust
    adjustment = await user_repo.adjust_trust_flame(
        user_id,
        request.trust_flame - old_trust,  # Adjustment amount
        reason=request.reason,
    )

    if adjustment is None:
        # SECURITY FIX (Audit 7 - Session 3): Generic error message, don't leak internal details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        )

    # Re-fetch user to get the updated state
    updated_user = await user_repo.get_by_id(user_id)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found after trust update",
        )

    # Audit log
    await audit_repo.log_action(
        action="update_trust",
        entity_type="user",
        entity_id=user_id,
        user_id=admin.id,
        details={
            "old_trust": old_trust,
            "new_trust": request.trust_flame,
            "reason": request.reason,
        },
        correlation_id=correlation_id,
    )

    return UserResponse.from_user(updated_user)
