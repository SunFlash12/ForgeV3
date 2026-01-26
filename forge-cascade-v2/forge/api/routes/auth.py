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

import logging
import secrets
from typing import Any, Literal

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from neo4j.exceptions import ConstraintError
from pydantic import BaseModel, EmailStr, Field, field_validator

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    AuthServiceDep,
    ClientInfoDep,
    CorrelationIdDep,
    SettingsDep,
    UserRepoDep,
)
from forge.models.base import TrustLevel
from forge.models.user import AuthProvider, User, UserUpdate

# Resilience integration - validation and metrics
from forge.resilience.integration import (
    check_content_validation,
    record_login_attempt,
    record_logout,
    record_password_change,
    record_registration,
    record_token_refresh,
    validate_capsule_content,
)
from forge.security.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_password,
)

router = APIRouter()


# =============================================================================
# Cookie Configuration
# =============================================================================

from forge.config import get_settings


def get_cookie_settings() -> dict[str, Any]:
    """
    Get cookie settings based on environment.

    In development, secure=False allows cookies over HTTP.
    In production, secure=True requires HTTPS.
    """
    settings = get_settings()
    is_production = settings.app_env == "production"

    return {
        "httponly": True,      # Prevent JavaScript access (XSS protection)
        "secure": is_production,  # Only require HTTPS in production
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
    cookie_settings = get_cookie_settings()

    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_expires_seconds,
        **cookie_settings,
    )

    # Refresh token cookie (longer lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_expires_days * 24 * 60 * 60,
        **cookie_settings,
    )

    # CSRF token - NOT httpOnly so JavaScript can read it
    # This implements the Double Submit Cookie pattern
    if csrf_token:
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            max_age=access_expires_seconds,
            httponly=False,  # JavaScript needs to read this
            secure=cookie_settings["secure"],  # Match environment setting
            samesite="lax",
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    """Clear all authentication cookies on logout."""
    cookie_settings = get_cookie_settings()
    for cookie_name in ["access_token", "refresh_token", "csrf_token"]:
        response.delete_cookie(
            key=cookie_name,
            path="/",
            secure=cookie_settings["secure"],
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
    # SECURITY FIX (Audit 4 - M): Bcrypt truncates at 72 bytes, so limit max_length
    password: str = Field(..., min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""
    # SECURITY FIX (Audit 2): Add length limits to prevent DoS
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""
    # SECURITY FIX (Audit 2): Add max_length to prevent DoS
    refresh_token: str = Field(..., max_length=1024)


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    # Current password can be longer in case user previously set a long password
    current_password: str = Field(..., min_length=1, max_length=128)
    # SECURITY FIX (Audit 4 - M): Bcrypt truncates at 72 bytes, so limit new password
    new_password: str = Field(..., min_length=8, max_length=72)


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
    def from_user(cls, user: User) -> UserResponse:
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

    # SECURITY FIX: Validate username and display_name separately to avoid
    # false positives from concatenation (e.g., valid "test" + "user" = "test user")
    validation_result = await validate_capsule_content(request.username)
    check_content_validation(validation_result)
    if request.display_name:
        validation_result = await validate_capsule_content(request.display_name)
        check_content_validation(validation_result)

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

        # Resilience: Record registration metric
        record_registration()

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
        # Registration errors are user-facing (username/email taken)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except PasswordValidationError as e:
        # Password validation errors are user-facing (tells user what to fix)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        # SECURITY FIX (Audit 3): Generic message for unexpected validation errors
        import logging
        logging.getLogger(__name__).warning(f"registration_validation_error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid registration data",
        )


class LoginResponse(BaseModel):
    """Login response with CSRF token (tokens are in httpOnly cookies)."""
    csrf_token: str
    expires_in: int
    user: UserResponse


class LoginMFARequiredResponse(BaseModel):
    """
    Response when MFA verification is required to complete login.

    SECURITY FIX (Audit 6 - Session 3): Two-step login flow for MFA users.
    Password was verified, but user must now provide TOTP/backup code.
    """
    mfa_required: Literal[True] = True
    mfa_token: str  # Temporary token for MFA verification (5 min expiry)
    expires_in: int  # Token expiry in seconds
    message: str = "MFA verification required"


class MFALoginVerifyRequest(BaseModel):
    """Request to complete MFA login verification."""
    mfa_token: str = Field(..., max_length=2048, description="MFA pending token from login response")
    code: str = Field(..., min_length=6, max_length=12, description="TOTP code (6 digits) or backup code (XXXX-XXXX)")


@router.post("/login", response_model=LoginResponse | LoginMFARequiredResponse)
async def login(
    request: LoginRequest,
    response: Response,
    auth_service: AuthServiceDep,
    audit_repo: AuditRepoDep,
    settings: SettingsDep,
    correlation_id: CorrelationIdDep,
    client_info: ClientInfoDep,
) -> LoginResponse | LoginMFARequiredResponse:
    """
    Authenticate and receive JWT tokens.

    Tokens are set as httpOnly cookies for security.
    Returns a CSRF token that must be included in X-CSRF-Token header
    for all state-changing requests (POST, PUT, PATCH, DELETE).

    SECURITY FIX (Audit 6 - Session 3): If MFA is enabled for the user,
    returns LoginMFARequiredResponse with an mfa_token instead of full
    authentication. User must then call /auth/mfa/verify with the code.
    """
    from forge.security.auth_service import MFARequiredError
    from forge.security.tokens import create_mfa_pending_token

    try:
        user, tokens = await auth_service.login(
            username_or_email=request.username,
            password=request.password,
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
        )

        # Resilience: Record successful login
        record_login_attempt(success=True)

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

    except MFARequiredError as e:
        # SECURITY FIX (Audit 6 - Session 3): MFA enabled, return pending token
        # Password was correct but user needs to verify with TOTP/backup code
        mfa_token = create_mfa_pending_token(
            user_id=e.user_id,
            username=e.username,
            ip_address=client_info.ip_address,
        )

        return LoginMFARequiredResponse(
            mfa_required=True,
            mfa_token=mfa_token,
            expires_in=settings.mfa_pending_token_expire_seconds,
            message="MFA verification required",
        )

    except (ValueError, KeyError, OSError, RuntimeError):
        # Resilience: Record failed login
        record_login_attempt(success=False, reason="invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/mfa/verify", response_model=LoginResponse)
async def verify_mfa_login(
    request: MFALoginVerifyRequest,
    response: Response,
    auth_service: AuthServiceDep,
    audit_repo: AuditRepoDep,
    settings: SettingsDep,
    correlation_id: CorrelationIdDep,
    client_info: ClientInfoDep,
) -> LoginResponse:
    """
    Complete MFA login verification.

    SECURITY FIX (Audit 6 - Session 3): Second step of two-step login flow.
    Exchanges an MFA pending token + TOTP/backup code for full authentication.

    Args:
        mfa_token: Temporary token from /login response (5 min expiry)
        code: TOTP code (6 digits) or backup code (XXXX-XXXX format)

    Returns:
        LoginResponse with full authentication (tokens in cookies)
    """
    from forge.security.auth_service import (
        AccountDeactivatedError,
        AuthenticationError,
        InvalidCredentialsError,
    )
    from forge.security.tokens import TokenInvalidError, verify_mfa_pending_token

    try:
        # Step 1: Verify the MFA pending token
        payload = verify_mfa_pending_token(
            request.mfa_token,
            ip_address=client_info.ip_address,
        )

        # Step 2: Complete MFA verification and get full tokens
        user, tokens = await auth_service.verify_mfa_login(
            user_id=payload.sub,
            code=request.code,
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
        )

        # Resilience: Record successful MFA login
        record_login_attempt(success=True)

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

    except TokenInvalidError as e:
        # MFA pending token is invalid or expired
        logger.warning(
            "mfa_verify_token_invalid: error=%s ip=%s",
            str(e),
            client_info.ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA token is invalid or expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InvalidCredentialsError:
        # Invalid MFA code
        record_login_attempt(success=False, reason="invalid_mfa_code")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except AccountDeactivatedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except AuthenticationError as e:
        logger.warning(
            "mfa_verify_auth_error: error=%s ip=%s",
            str(e),
            client_info.ip_address,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
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
        except (ValueError, KeyError, RuntimeError):
            pass

    if not token_to_use:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        tokens = await auth_service.refresh_tokens(token_to_use)

        # Resilience: Record successful token refresh
        record_token_refresh(success=True)

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

    except ValueError:
        # Resilience: Record failed token refresh
        record_token_refresh(success=False)
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
                # Blacklist with expiry matching token expiry (async for Redis support)
                expires_at = claims.get("exp")
                await TokenBlacklist.add_async(claims["jti"], expires_at)
        except (ValueError, KeyError, OSError, RuntimeError):
            pass  # Token parsing failed, but still clear cookies

    # Resilience: Record logout metric
    record_logout()

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
    # Resilience: Content validation for display_name
    if request.display_name:
        validation_result = await validate_capsule_content(request.display_name)
        check_content_validation(validation_result)

    # Build update data
    update_data = UserUpdate(
        display_name=request.display_name,
        email=request.email,
    )

    if request.email is not None:
        # Check if email already exists
        existing = await user_repo.get_by_email(request.email)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

    # Check if there are any updates to make
    has_updates = request.display_name is not None or request.email is not None

    if has_updates:
        # SECURITY FIX (Audit 6 - H1): Wrap update in try-except to handle race condition.
        # The pre-check above provides a friendly error message, but the database
        # constraint (user_email_unique) is the authoritative enforcement.
        # Between the check and update, another request could insert the same email.
        try:
            updated_user = await user_repo.update(user.id, update_data)
        except ConstraintError as e:
            # Database constraint violated - email already taken by concurrent request
            logger.warning(
                "email_constraint_violation: user_id=%s email=%s error=%s",
                user.id,
                request.email,
                str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            ) from None

        if updated_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        await audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="profile_updated",
            details={"fields": [f for f in ["display_name", "email"] if getattr(request, f) is not None]},
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
    # Fetch user with password_hash from database
    user_in_db = await user_repo.get_by_username(user.username)
    if user_in_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not verify_password(request.current_password, user_in_db.password_hash):
        # SECURITY FIX (Audit 2): Log failed password change attempts for security monitoring
        await audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="password_change_failed",
            details={"reason": "incorrect_current_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Update password
    new_hash = hash_password(request.new_password)
    await user_repo.update_password(user.id, new_hash)

    # Resilience: Record password change metric
    record_password_change()

    await audit_repo.log_user_action(
        actor_id=user.id,
        target_user_id=user.id,
        action="password_changed",
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/trust")
async def get_trust_info(
    user: ActiveUserDep,
) -> dict[str, Any]:
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


# =============================================================================
# SECURITY FIX (Audit 3): MFA Endpoints
# =============================================================================

from forge.security.mfa import get_mfa_service


class MFASetupResponse(BaseModel):
    """Response for MFA setup."""
    secret: str
    provisioning_uri: str
    qr_code: str  # Alias for provisioning_uri (frontend compatibility)
    backup_codes: list[str]


class MFAVerifyRequest(BaseModel):
    """Request to verify MFA code."""
    code: str = Field(..., min_length=6, max_length=8, description="TOTP or backup code")


class MFAStatusResponse(BaseModel):
    """MFA status response."""
    enabled: bool
    verified: bool
    backup_codes_remaining: int


@router.post("/me/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
) -> MFASetupResponse:
    """
    Initialize MFA setup for the current user.

    Returns the TOTP secret, QR code URI, and backup codes.
    User must verify setup by calling /me/mfa/verify with a valid code.

    SECURITY: Backup codes are shown only once - user must save them.
    """
    mfa = get_mfa_service()

    # Check if MFA already enabled
    mfa_status = await mfa.get_status(user.id)
    if mfa_status.enabled and mfa_status.verified:
        # SECURITY FIX (Audit 7 - Session 3): Use 409 CONFLICT, not 400 BAD_REQUEST.
        # MFA already being enabled is a resource conflict, not a malformed request.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled. Disable it first to reconfigure."
        )

    result = await mfa.setup_mfa(user.id, user.email)

    await audit_repo.log_security_event(
        actor_id=user.id,
        event_name="mfa_setup_initiated",
        details={},
    )

    return MFASetupResponse(
        secret=result.secret,
        provisioning_uri=result.provisioning_uri,
        qr_code=result.provisioning_uri,  # Alias for frontend compatibility
        backup_codes=result.backup_codes,
    )


@router.post("/me/mfa/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_mfa_setup(
    request: MFAVerifyRequest,
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
) -> Response:
    """
    Verify MFA setup with a TOTP code from authenticator app.

    This completes the MFA setup process.
    """
    mfa = get_mfa_service()

    if await mfa.verify_setup(user.id, request.code):
        await audit_repo.log_security_event(
            actor_id=user.id,
            event_name="mfa_enabled",
            details={},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid verification code. Please try again."
    )


@router.get("/me/mfa/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    user: ActiveUserDep,
) -> MFAStatusResponse:
    """
    Get MFA status for the current user.
    """
    mfa = get_mfa_service()
    mfa_status = await mfa.get_status(user.id)

    return MFAStatusResponse(
        enabled=mfa_status.enabled,
        verified=mfa_status.verified,
        backup_codes_remaining=mfa_status.backup_codes_remaining,
    )


@router.delete("/me/mfa", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    request: MFAVerifyRequest,
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
) -> Response:
    """
    Disable MFA for the current user.

    Requires a valid TOTP code or backup code for security.
    """
    mfa = get_mfa_service()

    # Verify code before disabling
    code = request.code

    # Try TOTP first, then backup code
    verified = await mfa.verify_totp(user.id, code)
    if not verified:
        # Try as backup code (format: XXXX-XXXX)
        verified = await mfa.verify_backup_code(user.id, code)

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. MFA cannot be disabled."
        )

    await mfa.disable_mfa(user.id)

    await audit_repo.log_security_event(
        actor_id=user.id,
        event_name="mfa_disabled",
        details={},
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/mfa/backup-codes", response_model=list[str])
async def regenerate_backup_codes(
    request: MFAVerifyRequest,
    user: ActiveUserDep,
    audit_repo: AuditRepoDep,
) -> list[str]:
    """
    Regenerate backup codes.

    Requires a valid TOTP code. All previous backup codes are invalidated.

    SECURITY: New codes are shown only once - user must save them.
    """
    mfa = get_mfa_service()

    # Must provide valid TOTP to regenerate backup codes
    if not await mfa.verify_totp(user.id, request.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code. Cannot regenerate backup codes."
        )

    try:
        new_codes = await mfa.regenerate_backup_codes(user.id)

        await audit_repo.log_security_event(
            actor_id=user.id,
            event_name="mfa_backup_codes_regenerated",
            details={},
        )

        return new_codes
    except ValueError:
        # SECURITY FIX (Audit 3): Generic message for MFA errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account"
        )


# =============================================================================
# GOOGLE OAUTH Endpoints
# =============================================================================

from forge.security.google_oauth import (
    GoogleOAuthError,
    get_google_oauth_service,
)


class GoogleAuthRequest(BaseModel):
    """Request for Google OAuth authentication."""
    credential: str = Field(..., description="Google ID token from Sign-In")
    client_type: Literal["cascade", "shop"] = Field(
        default="cascade",
        description="Client type for redirect URI selection"
    )


class GoogleAuthResponse(BaseModel):
    """Response after Google OAuth authentication."""
    csrf_token: str
    expires_in: int
    user: UserResponse
    is_new_user: bool


class GoogleLinkResponse(BaseModel):
    """Response after linking Google account."""
    linked: bool
    google_email: str


@router.post("/google", response_model=GoogleAuthResponse)
async def google_auth(
    request: GoogleAuthRequest,
    response: Response,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
) -> GoogleAuthResponse:
    """
    Authenticate via Google OAuth.

    Accepts a Google ID token from the frontend Sign-In.
    Creates a new user account if one doesn't exist,
    or logs in the existing user linked to this Google account.
    """
    google_service = get_google_oauth_service()

    if not google_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured"
        )

    try:
        # Verify the Google token
        google_user = await google_service.verify_id_token(request.credential)

        # Get or create user
        user, is_new_user = await google_service.get_or_create_user(
            google_user, user_repo
        )

        # Generate tokens
        from forge.config import get_settings
        from forge.security.tokens import (
            create_access_token,
            create_refresh_token,
        )

        settings = get_settings()

        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
            trust_flame=user.trust_flame,
        )
        refresh_token = create_refresh_token(user_id=user.id, username=user.username)
        csrf_token = generate_csrf_token()

        # Store refresh token hash
        await user_repo.update_refresh_token(user.id, refresh_token)

        # Record login
        await user_repo.record_login(user.id)

        # Audit log
        await audit_repo.log_security_event(
            actor_id=user.id,
            event_name="google_auth_success",
            details={"is_new_user": is_new_user, "client_type": request.client_type},
        )

        # Set cookies
        set_auth_cookies(
            response=response,
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_seconds=settings.jwt_access_token_expire_minutes * 60,
            csrf_token=csrf_token,
        )

        return GoogleAuthResponse(
            csrf_token=csrf_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserResponse.from_user(user_repo.to_safe_user(user)),
            is_new_user=is_new_user,
        )

    except GoogleOAuthError as e:
        logger.warning(f"Google OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed"
        )


@router.post("/google/link", response_model=GoogleLinkResponse)
async def link_google_account(
    request: GoogleAuthRequest,
    user: ActiveUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
) -> GoogleLinkResponse:
    """
    Link a Google account to the current user.

    Allows users who signed up with email/password to add Google Sign-In.
    """
    google_service = get_google_oauth_service()

    if not google_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured"
        )

    try:
        # Verify the Google token
        google_user = await google_service.verify_id_token(request.credential)

        # Check if this Google account is already linked to another user
        existing = await user_repo.get_by_google_id(google_user.sub)
        if existing and existing.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another user"
            )

        # Link the account
        success = await user_repo.link_google_account(
            user_id=user.id,
            google_id=google_user.sub,
            google_email=google_user.email,
        )

        if not success:
            # SECURITY FIX (Audit 7 - Session 3): Generic error message, don't hint at internals
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred. Please try again later."
            )

        # Audit log
        await audit_repo.log_security_event(
            actor_id=user.id,
            event_name="google_account_linked",
            details={"google_id": google_user.sub},
        )

        return GoogleLinkResponse(
            linked=True,
            google_email=google_user.email,
        )

    except GoogleOAuthError as e:
        logger.warning(f"Google OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed"
        )


@router.delete("/google/unlink", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_google_account(
    user: ActiveUserDep,
    user_repo: UserRepoDep,
    audit_repo: AuditRepoDep,
) -> Response:
    """
    Unlink Google account from the current user.

    User must have a password set to unlink Google (to prevent lockout).
    """
    # Get full user data to check auth provider
    full_user = await user_repo.get_by_id(user.id)

    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has Google linked
    user_db = await user_repo.get_by_username(full_user.username)
    if not user_db or not user_db.google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Google account is linked"
        )

    # Prevent lockout: if auth_provider is GOOGLE, user needs password
    if user_db.auth_provider == AuthProvider.GOOGLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink Google - this is your only sign-in method. "
                   "Please set a password first."
        )

    # Unlink
    success = await user_repo.unlink_google_account(user.id)

    if not success:
        # SECURITY FIX (Audit 7 - Session 3): Generic error message, don't hint at internals
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )

    # Audit log
    await audit_repo.log_security_event(
        actor_id=user.id,
        event_name="google_account_unlinked",
        details={},
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
