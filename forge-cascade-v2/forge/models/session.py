"""
Session Models

Session entities for tracking user sessions with IP and User-Agent binding.
Used for security monitoring and forensics (Audit 6 - Session 2).
"""

from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import Any

from pydantic import Field, field_validator

from forge.models.base import ForgeModel, TimestampMixin


class SessionBindingMode(str, Enum):
    """Session binding enforcement modes."""

    DISABLED = "disabled"  # No binding enforcement
    LOG_ONLY = "log_only"  # Log changes only (audit trail)
    WARN = "warn"  # Log warnings but allow access
    FLEXIBLE = "flexible"  # Block after threshold changes
    STRICT = "strict"  # Block any change immediately


class SessionStatus(str, Enum):
    """Session status states."""

    ACTIVE = "active"  # Normal active session
    EXPIRED = "expired"  # Session has expired
    REVOKED = "revoked"  # Explicitly revoked
    SUSPICIOUS = "suspicious"  # Flagged as suspicious but still active


class SessionCreate(ForgeModel):
    """Schema for creating a new session."""

    user_id: str = Field(description="User ID who owns this session")
    token_jti: str = Field(description="JWT ID (jti) linked to this session")
    token_type: str = Field(default="access", description="Token type: access or refresh")
    ip_address: str = Field(description="Initial IP address")
    user_agent: str | None = Field(default=None, description="Initial User-Agent string")
    expires_at: datetime = Field(description="When the session expires")


class SessionUpdate(ForgeModel):
    """Schema for updating session activity."""

    last_ip: str | None = None
    last_user_agent: str | None = None
    last_activity: datetime | None = None
    request_count: int | None = None
    ip_change_count: int | None = None
    user_agent_change_count: int | None = None
    ip_history: list[dict[str, Any]] | None = None
    status: SessionStatus | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = None


class Session(ForgeModel, TimestampMixin):
    """Complete session schema for API responses and internal use."""

    id: str = Field(description="Session ID (same as token JTI)")
    user_id: str = Field(description="User ID who owns this session")
    token_jti: str = Field(description="JWT ID (jti) linked to this session")
    token_type: str = Field(default="access", description="Token type: access or refresh")

    # Initial binding values (captured at session creation)
    initial_ip: str = Field(description="IP address at session creation")
    initial_user_agent: str | None = Field(default=None, description="User-Agent at creation")
    initial_user_agent_hash: str | None = Field(
        default=None, description="SHA-256 hash of initial User-Agent"
    )

    # Current/last values (updated on each request)
    last_ip: str = Field(description="Most recent IP address")
    last_user_agent: str | None = Field(default=None, description="Most recent User-Agent")
    last_user_agent_hash: str | None = Field(
        default=None, description="SHA-256 hash of last User-Agent"
    )
    last_activity: datetime = Field(description="Timestamp of last activity")

    # Activity tracking
    request_count: int = Field(default=1, ge=0, description="Total requests in this session")
    ip_change_count: int = Field(default=0, ge=0, description="Number of IP changes detected")
    user_agent_change_count: int = Field(
        default=0, ge=0, description="Number of User-Agent changes"
    )

    # IP history for forensics (most recent first)
    ip_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of IP changes with timestamps [{ip, timestamp, geo?}]",
    )

    # Session lifecycle
    expires_at: datetime = Field(description="When the session expires")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    revoked_at: datetime | None = Field(default=None, description="When session was revoked")
    revoked_reason: str | None = Field(default=None, description="Reason for revocation")

    @field_validator("ip_history", mode="before")
    @classmethod
    def validate_ip_history(cls, v: object) -> list[dict[str, Any]]:
        """Convert None to empty list."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

    @staticmethod
    def hash_user_agent(user_agent: str | None) -> str | None:
        """Create SHA-256 hash of User-Agent for comparison."""
        if not user_agent:
            return None
        return sha256(user_agent.encode("utf-8")).hexdigest()

    @property
    def is_active(self) -> bool:
        """Check if session is active and not expired."""
        if self.status in (SessionStatus.EXPIRED, SessionStatus.REVOKED):
            return False
        return datetime.now(UTC) < self.expires_at

    @property
    def is_suspicious(self) -> bool:
        """Check if session has been flagged as suspicious."""
        return self.status == SessionStatus.SUSPICIOUS


class SessionInDB(Session):
    """Session with database-specific fields."""

    pass  # Currently same as Session, but allows for future DB-specific additions


class SessionPublic(ForgeModel):
    """Public session info for API responses (redacted sensitive data)."""

    id: str
    token_type: str
    initial_ip: str = Field(description="Masked/truncated IP for display")
    last_ip: str = Field(description="Masked/truncated IP for display")
    last_activity: datetime
    request_count: int
    ip_change_count: int
    user_agent_change_count: int
    status: SessionStatus
    expires_at: datetime
    created_at: datetime
    is_current: bool = Field(default=False, description="Whether this is the current session")

    @staticmethod
    def mask_ip(ip: str) -> str:
        """Mask IP address for privacy (show first and last octet only)."""
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.***.***.{parts[3]}"
        # IPv6 or invalid - truncate
        if len(ip) > 10:
            return f"{ip[:6]}...{ip[-4:]}"
        return ip


class SessionListResponse(ForgeModel):
    """Response schema for listing user sessions."""

    sessions: list[SessionPublic] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of active sessions")
    current_session_id: str | None = Field(
        default=None, description="ID of the current session (from request)"
    )


class SessionBindingWarning(ForgeModel):
    """Warning event when session binding detects changes."""

    session_id: str
    user_id: str
    warning_type: str = Field(description="Type: ip_change, user_agent_change, suspicious")
    old_value: str | None
    new_value: str | None
    binding_mode: SessionBindingMode
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_count: int = Field(description="Request count when change detected")
    additional_info: dict[str, Any] = Field(default_factory=dict)


class SessionRevokeRequest(ForgeModel):
    """Request schema for revoking a session."""

    reason: str | None = Field(default=None, max_length=500, description="Reason for revocation")


class SessionRevokeAllRequest(ForgeModel):
    """Request schema for revoking all sessions."""

    except_current: bool = Field(default=True, description="Keep the current session active")
    reason: str | None = Field(default=None, max_length=500, description="Reason for revocation")
