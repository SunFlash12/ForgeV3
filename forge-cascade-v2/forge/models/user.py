"""
User Models

User entities with authentication, trust scoring (Trust Flame),
and role-based access control.
"""

from datetime import datetime
from enum import Enum

from pydantic import EmailStr, Field, field_validator

from forge.models.base import (
    ForgeModel,
    TimestampMixin,
    TrustLevel,
    generate_id,
)


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
        description="Avatar image URL",
    )


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        min_length=8,
        max_length=100,
        description="User password",
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
    username: str
    role: UserRole
    trust_flame: int
    exp: datetime = Field(description="Expiration timestamp")
    iat: datetime = Field(description="Issued at timestamp")
    type: str = Field(description="Token type: access or refresh")


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
