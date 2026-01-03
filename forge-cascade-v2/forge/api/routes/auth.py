"""
Forge Cascade V2 - Authentication Routes
Endpoints for user authentication and authorization.

Provides:
- User registration
- Login (token generation)
- Token refresh
- Password change
- Profile management
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status, Response
from pydantic import BaseModel, EmailStr, Field

from forge.api.dependencies import (
    AuthServiceDep,
    UserRepoDep,
    CurrentUserDep,
    ActiveUserDep,
    AuditRepoDep,
    SettingsDep,
    CorrelationIdDep,
)
from forge.models.user import User, TrustLevel
from forge.security.password import verify_password, hash_password


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: str | None = None


class LoginRequest(BaseModel):
    """User login request."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class UpdateProfileRequest(BaseModel):
    """Profile update request."""
    display_name: str | None = None
    email: EmailStr | None = None
    metadata: dict[str, Any] | None = None


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    username: str
    email: str
    display_name: str | None
    trust_level: str
    trust_score: float
    roles: list[str]
    is_active: bool
    created_at: str
    
    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            trust_level=user.trust_level.name,
            trust_score=float(user.trust_flame),
            roles=list(user.roles),
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else "",
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    auth_service: AuthServiceDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> UserResponse:
    """
    Register a new user account.
    
    New users start at SANDBOX trust level.
    """
    try:
        user = await auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password,
            display_name=request.display_name,
        )
        
        # Audit log
        await audit_repo.log_action(
            action="user_registered",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            details={"username": user.username},
            correlation_id=correlation_id,
        )
        
        return UserResponse.from_user(user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
    audit_repo: AuditRepoDep,
    settings: SettingsDep,
    correlation_id: CorrelationIdDep,
) -> TokenResponse:
    """
    Authenticate and receive JWT tokens.
    
    Returns access and refresh tokens.
    """
    try:
        tokens = await auth_service.authenticate(
            username=request.username,
            password=request.password,
        )
        
        # Audit log (get user for ID)
        user = await auth_service.user_repo.get_by_username(request.username)
        if user:
            await audit_repo.log_action(
                action="user_login",
                entity_type="user",
                entity_id=user.id,
                user_id=user.id,
                details={"username": user.username},
                correlation_id=correlation_id,
            )
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    """
    try:
        tokens = await auth_service.refresh_tokens(request.refresh_token)
        
        return TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> Response:
    """
    Logout current user.
    
    Note: In a stateless JWT system, this is primarily for audit purposes.
    The client should discard tokens. For true logout, implement token blacklist.
    """
    await audit_repo.log_action(
        action="user_logout",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    user: ActiveUserDep,
) -> UserResponse:
    """
    Get current authenticated user's profile.
    """
    return UserResponse.from_user(user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    user: ActiveUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> UserResponse:
    """
    Update current user's profile.
    """
    updates = {}
    
    if request.display_name is not None:
        updates["display_name"] = request.display_name
    
    if request.email is not None:
        # Check if email already exists
        existing = await user_repo.get_by_email(request.email)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        updates["email"] = request.email
    
    if request.metadata is not None:
        updates["metadata"] = {**user.metadata, **request.metadata}
    
    if updates:
        updated_user = await user_repo.update(user.id, updates)
        
        await audit_repo.log_action(
            action="profile_updated",
            entity_type="user",
            entity_id=user.id,
            user_id=user.id,
            details={"fields": list(updates.keys())},
            correlation_id=correlation_id,
        )
        
        return UserResponse.from_user(updated_user)
    
    return UserResponse.from_user(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    user: ActiveUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> Response:
    """
    Change current user's password.
    """
    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # Update password
    new_hash = hash_password(request.new_password)
    await user_repo.update(user.id, {"password_hash": new_hash})
    
    await audit_repo.log_action(
        action="password_changed",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        correlation_id=correlation_id,
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/trust")
async def get_trust_info(
    user: ActiveUserDep,
) -> dict:
    """
    Get current user's trust information.
    """
    return {
        "trust_level": user.trust_level.name,
        "trust_score": float(user.trust_flame),
        "level_thresholds": {
            "UNTRUSTED": 0,
            "SANDBOX": 40,
            "STANDARD": 60,
            "TRUSTED": 80,
            "CORE": 100,
        },
        "next_level": _get_next_level(user.trust_level),
        "score_to_next": _score_to_next_level(user.trust_flame, user.trust_level),
    }


def _get_next_level(current: TrustLevel) -> str | None:
    """Get the next trust level."""
    levels = list(TrustLevel)
    idx = levels.index(current)
    if idx < len(levels) - 1:
        return levels[idx + 1].name
    return None


def _score_to_next_level(score: float, current: TrustLevel) -> float | None:
    """Calculate score needed for next level."""
    thresholds = {
        TrustLevel.UNTRUSTED: 40,
        TrustLevel.SANDBOX: 60,
        TrustLevel.STANDARD: 80,
        TrustLevel.TRUSTED: 100,
        TrustLevel.CORE: None,
    }
    
    next_threshold = thresholds.get(current)
    if next_threshold is None:
        return None
    
    return max(0, next_threshold - score)
