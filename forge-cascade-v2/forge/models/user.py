"""
User Models

User entities with authentication, trust scoring (Trust Flame),
and role-based access control.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import EmailStr, Field, field_validator

from forge.models.base import (
    ForgeModel,
    TimestampMixin,
    TrustLevel,
    generate_id,
)


class Capability(str, Enum):
    """User capabilities for fine-grained access control."""

    # Capsule capabilities
    CREATE_CAPSULE = "create_capsule"
    EDIT_CAPSULE = "edit_capsule"
    DELETE_CAPSULE = "delete_capsule"
    ARCHIVE_CAPSULE = "archive_capsule"
    VIEW_PRIVATE_CAPSULE = "view_private_capsule"

    # Governance capabilities
    CREATE_PROPOSAL = "create_proposal"
    VOTE = "vote"
    EXECUTE_PROPOSAL = "execute_proposal"

    # Overlay capabilities
    MANAGE_OVERLAYS = "manage_overlays"
    CONFIGURE_OVERLAYS = "configure_overlays"

    # Admin capabilities
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT_LOG = "view_audit_log"
    MANAGE_SYSTEM = "manage_system"

    # Ghost Council
    GHOST_COUNCIL_ACCESS = "ghost_council_access"


class UserRole(str, Enum):
    """User roles for authorization."""

    USER = "user"           # Standard user
    MODERATOR = "moderator"  # Can moderate content
    ADMIN = "admin"         # Full administrative access
    SYSTEM = "system"       # System-level access (for overlays)


class AuthProvider(str, Enum):
    """Authentication providers."""

    LOCAL = "local"         # Email/password
    GOOGLE = "google"       # Google OAuth
    GITHUB = "github"       # GitHub OAuth
    DISCORD = "discord"     # Discord OAuth
    WEB3 = "web3"           # Wallet-based auth


class UserBase(ForgeModel):
    """Base fields shared across user schemas."""

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username",
    )
    email: EmailStr = Field(description="User email address")
    display_name: str | None = Field(
        default=None,
        max_length=100,
        description="Display name",
    )
    bio: str | None = Field(
        default=None,
        max_length=500,
        description="User biography",
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=500,
        description="Avatar image URL (must be http or https)",
    )

    # SECURITY FIX (Audit 2): Validate avatar_url to prevent XSS via javascript:/data: URIs
    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        # Only allow http and https schemes
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("Avatar URL must use http or https scheme")
        return v


class UserCreate(UserBase):
    """Schema for creating a new user."""

    # SECURITY FIX (Audit 4 - L3): Bcrypt truncates at 72 bytes, so limit max_length
    password: str = Field(
        min_length=8,
        max_length=72,
        description="User password (max 72 bytes due to bcrypt limit)",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(ForgeModel):
    """Schema for updating an existing user."""

    display_name: str | None = Field(default=None, max_length=100)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None


class UserPasswordChange(ForgeModel):
    """Schema for changing password."""

    current_password: str
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class User(UserBase, TimestampMixin):
    """Complete user schema for API responses."""

    id: str = Field(description="Unique identifier")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    trust_flame: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Trust score (0-100)",
    )
    is_active: bool = Field(default=True, description="Account active status")
    is_verified: bool = Field(default=False, description="Email verified")
    auth_provider: AuthProvider = Field(
        default=AuthProvider.LOCAL,
        description="Authentication provider",
    )
    last_login: datetime | None = Field(
        default=None,
        description="Last login timestamp",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="User metadata for extensible properties",
    )

    @property
    def trust_level(self) -> TrustLevel:
        """Get trust level from trust flame score."""
        return TrustLevel.from_value(self.trust_flame)


class UserInDB(User):
    """User with database-specific fields."""

    password_hash: str = Field(description="Hashed password")
    refresh_token: str | None = Field(
        default=None,
        description="Current refresh token",
    )
    failed_login_attempts: int = Field(
        default=0,
        ge=0,
        description="Failed login counter",
    )
    lockout_until: datetime | None = Field(
        default=None,
        description="Account lockout timestamp",
    )


class UserPublic(ForgeModel):
    """Public user profile (no sensitive data)."""

    id: str
    username: str
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    trust_flame: int
    created_at: datetime

    @property
    def trust_level(self) -> TrustLevel:
        """Get trust level from trust flame score."""
        return TrustLevel.from_value(self.trust_flame)


# ═══════════════════════════════════════════════════════════════
# AUTHENTICATION MODELS
# ═══════════════════════════════════════════════════════════════


class LoginRequest(ForgeModel):
    """Login request schema."""

    username_or_email: str = Field(description="Username or email")
    password: str = Field(description="Password")


class Token(ForgeModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiry in seconds")


class TokenPayload(ForgeModel):
    """JWT token payload (claims)."""

    sub: str = Field(description="Subject (user ID)")
    username: str | None = None
    role: UserRole | None = None  # Optional for refresh tokens
    trust_flame: int | None = None  # Optional for refresh tokens
    exp: datetime | None = Field(default=None, description="Expiration timestamp")
    iat: datetime | None = Field(default=None, description="Issued at timestamp")
    jti: str | None = Field(default=None, description="JWT ID for token blacklisting")
    type: str = Field(default="access", description="Token type: access or refresh")


class RefreshTokenRequest(ForgeModel):
    """Refresh token request."""

    refresh_token: str


# ═══════════════════════════════════════════════════════════════
# TRUST FLAME MODELS
# ═══════════════════════════════════════════════════════════════


class TrustFlameAdjustment(ForgeModel):
    """Record of trust flame adjustment."""

    user_id: str
    old_value: int
    new_value: int
    reason: str
    adjusted_by: str | None = None  # User or system ID
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrustFlameReason(str, Enum):
    """Reasons for trust flame adjustments."""

    SUCCESSFUL_OPERATION = "successful_operation"
    FAILED_OPERATION = "failed_operation"
    POSITIVE_VOTE = "positive_vote"
    NEGATIVE_VOTE = "negative_vote"
    SECURITY_INCIDENT = "security_incident"
    TIME_IN_SERVICE = "time_in_service"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    VERIFICATION_COMPLETE = "verification_complete"


class UserStats(ForgeModel):
    """User statistics."""

    user_id: str
    capsules_created: int = 0
    capsules_forked: int = 0
    proposals_created: int = 0
    votes_cast: int = 0
    total_views_received: int = 0
    trust_flame_history: list[TrustFlameAdjustment] = Field(default_factory=list)
