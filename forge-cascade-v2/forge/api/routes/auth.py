"""
Forge Cascade V2 - Authentication Routes
Endpoints for user authentication and authorization.

Provides:
- User registration
- Login (token generation)
- Token refresh
- Password change
- Profile management

Security Features:
- HttpOnly cookies for token storage (XSS protection)
- CSRF token validation for state-changing requests
- Secure cookie flags (Secure, SameSite=Lax)
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status, Response, Request, Cookie
from pydantic import BaseModel, EmailStr, Field, field_validator

from forge.api.dependencies import (
    AuthServiceDep,
    UserRepoDep,
    CurrentUserDep,
    ActiveUserDep,
    AuditRepoDep,
    SettingsDep,
    CorrelationIdDep,
    ClientInfoDep,
)
from forge.models.user import User, TrustLevel
from forge.security.password import verify_password, hash_password, PasswordValidationError, validate_password_strength


router = APIRouter()


# =============================================================================
# Cookie Configuration
# =============================================================================

# Cookie settings for secure token storage
COOKIE_SETTINGS = {
    "httponly": True,      # Prevent JavaScript access (XSS protection)
    "secure": True,        # Only send over HTTPS
    "samesite": "lax",     # CSRF protection (allows top-level navigation)
    "path": "/",           # Available for all paths
}


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_expires_seconds: int,
    refresh_expires_days: int = 7,
    csrf_token: str | None = None,
) -> None:
    """
    Set secure httpOnly cookies for authentication tokens.

    Also sets a non-httpOnly CSRF token that JavaScript can read
    and include in request headers.
    """
    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_expires_seconds,
        **COOKIE_SETTINGS,
    )

    # Refresh token cookie (longer lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_expires_days * 24 * 60 * 60,
        **COOKIE_SETTINGS,
    )

    # CSRF token - NOT httpOnly so JavaScript can read it
    # This implements the Double Submit Cookie pattern
    if csrf_token:
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            max_age=access_expires_seconds,
            httponly=False,  # JavaScript needs to read this
            secure=True,
            samesite="lax",
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    """Clear all authentication cookies on logout."""
    for cookie_name in ["access_token", "refresh_token", "csrf_token"]:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=True,
            samesite="lax",
        )


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


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


# Reserved metadata keys that could cause security issues (prototype pollution, etc.)
RESERVED_METADATA_KEYS = {
    "__proto__",
    "constructor",
    "prototype",
    "__class__",
    "__bases__",
    "__mro__",
    "__subclasses__",
    "__init__",
    "__new__",
    "__call__",
    "__getattr__",
    "__setattr__",
    "__delattr__",
}


def validate_metadata_size(v: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate metadata size limits and filter dangerous keys."""
    if v is None:
        return v
    if len(v) > 10:
        raise ValueError("Metadata cannot have more than 10 keys")
    import json
    for key, value in v.items():
        # SECURITY: Reject reserved/dangerous keys to prevent prototype pollution
        if key in RESERVED_METADATA_KEYS or key.startswith("__"):
            raise ValueError(f"Metadata key '{key}' is reserved and not allowed")
        if len(key) > 64:
            raise ValueError(f"Metadata key '{key[:20]}...' too long (max 64 chars)")
        try:
            value_str = json.dumps(value)
            if len(value_str) > 1024:
                raise ValueError(f"Metadata value for '{key}' too large (max 1KB)")
        except (TypeError, ValueError):
            raise ValueError(f"Metadata value for '{key}' is not JSON serializable")
    return v


class UpdateProfileRequest(BaseModel):
    """Profile update request."""
    display_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    metadata: dict[str, Any] | None = Field(default=None, description="User metadata (max 10 keys, 1KB value limit)")

    @field_validator("metadata")
    @classmethod
    def check_metadata(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_metadata_size(v)


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
            roles=[user.role.value] if hasattr(user.role, 'value') else [user.role],
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
    client_info: ClientInfoDep,
) -> UserResponse:
    """
    Register a new user account.

    New users start at SANDBOX trust level.
    """
    from forge.security.auth_service import RegistrationError

    # Validate password strength on backend
    try:
        validate_password_strength(request.password)
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        user = await auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password,
            display_name=request.display_name,
            ip_address=client_info.ip_address,
        )

        # Audit log with IP and user agent
        await audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="registered",
            details={"username": user.username},
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
        )

        return UserResponse.from_user(user)

    except RegistrationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class LoginResponse(BaseModel):
    """Login response with CSRF token (tokens are in httpOnly cookies)."""
    csrf_token: str
    expires_in: int
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    auth_service: AuthServiceDep,
    audit_repo: AuditRepoDep,
    settings: SettingsDep,
    correlation_id: CorrelationIdDep,
    client_info: ClientInfoDep,
) -> LoginResponse:
    """
    Authenticate and receive JWT tokens.

    Tokens are set as httpOnly cookies for security.
    Returns a CSRF token that must be included in X-CSRF-Token header
    for all state-changing requests (POST, PUT, PATCH, DELETE).
    """
    try:
        user, tokens = await auth_service.login(
            username_or_email=request.username,
            password=request.password,
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
        )

        # Audit log with IP and user agent
        await audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="login",
            details={"username": user.username},
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
        )

        # Generate CSRF token
        csrf_token = generate_csrf_token()
        expires_in = settings.jwt_access_token_expire_minutes * 60

        # Set secure httpOnly cookies
        set_auth_cookies(
            response=response,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            access_expires_seconds=expires_in,
            refresh_expires_days=settings.jwt_refresh_token_expire_days,
            csrf_token=csrf_token,
        )

        return LoginResponse(
            csrf_token=csrf_token,
            expires_in=expires_in,
            user=UserResponse.from_user(user),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RefreshResponse(BaseModel):
    """Refresh response with new CSRF token."""
    csrf_token: str
    expires_in: int


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    http_request: Request,
    response: Response,
    auth_service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
) -> RefreshResponse:
    """
    Refresh access token using refresh token from cookie.

    Returns new CSRF token. New tokens are set as httpOnly cookies.
    """
    # Try cookie first, then fall back to request body for backwards compatibility
    token_to_use = refresh_token_cookie

    if not token_to_use:
        # Check for body-based refresh (backwards compatibility)
        try:
            body = await http_request.json()
            token_to_use = body.get("refresh_token")
        except Exception:
            pass

    if not token_to_use:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        tokens = await auth_service.refresh_tokens(token_to_use)

        # Generate new CSRF token
        csrf_token = generate_csrf_token()
        expires_in = settings.jwt_access_token_expire_minutes * 60

        # Set new cookies
        set_auth_cookies(
            response=response,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            access_expires_seconds=expires_in,
            refresh_expires_days=settings.jwt_refresh_token_expire_days,
            csrf_token=csrf_token,
        )

        return RefreshResponse(
            csrf_token=csrf_token,
            expires_in=expires_in,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    http_request: Request,
    response: Response,
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> Response:
    """
    Logout current user.

    Clears authentication cookies and blacklists the current token.
    """
    from forge.security.tokens import TokenBlacklist, get_token_claims

    # Blacklist the current access token if available
    token_to_blacklist = access_token_cookie
    if not token_to_blacklist:
        # Try Authorization header as fallback
        auth_header = http_request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token_to_blacklist = auth_header[7:]

    if token_to_blacklist:
        try:
            claims = get_token_claims(token_to_blacklist)
            if claims.get("jti"):
                # Blacklist with expiry matching token expiry
                expires_at = claims.get("exp")
                TokenBlacklist.add(claims["jti"], expires_at)
        except Exception:
            pass  # Token parsing failed, but still clear cookies

    await audit_repo.log_user_action(
        actor_id=user.id,
        target_user_id=user.id,
        action="logout",
    )

    # Clear all auth cookies
    clear_auth_cookies(response)

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
        
        await audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="profile_updated",
            details={"fields": list(updates.keys())},
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
    
    await audit_repo.log_user_action(
        actor_id=user.id,
        target_user_id=user.id,
        action="password_changed",
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
        "current_level": user.trust_level.name,  # Frontend expects current_level
        "trust_score": float(user.trust_flame),
        "thresholds": {  # Frontend expects thresholds, not level_thresholds
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
        TrustLevel.QUARANTINE: 40,
        TrustLevel.SANDBOX: 60,
        TrustLevel.STANDARD: 80,
        TrustLevel.TRUSTED: 100,
        TrustLevel.CORE: None,
    }

    next_threshold = thresholds.get(current)
    if next_threshold is None:
        return None

    return max(0, next_threshold - score)
