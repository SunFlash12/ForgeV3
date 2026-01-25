"""
Session Binding Service

Service for managing session binding with IP and User-Agent tracking.
Implements security monitoring for detecting suspicious session activity
(Audit 6 - Session 2).
"""

from datetime import datetime

import structlog

from forge.config import get_settings
from forge.models.session import (
    Session,
    SessionBindingMode,
    SessionBindingWarning,
    SessionCreate,
    SessionListResponse,
    SessionPublic,
    SessionStatus,
)
from forge.repositories.session_repository import SessionRepository

settings = get_settings()
logger = structlog.get_logger(__name__)


class SessionBindingService:
    """
    Service for session binding validation and management.

    Handles:
    - Session creation on login
    - IP and User-Agent binding validation per request
    - Session listing and revocation
    - Suspicious activity detection and logging
    """

    def __init__(self, session_repository: SessionRepository):
        """
        Initialize session binding service.

        Args:
            session_repository: Repository for session CRUD operations
        """
        self._repo = session_repository
        self._ip_binding_mode = SessionBindingMode(settings.session_ip_binding_mode)
        self._ua_binding_mode = SessionBindingMode(settings.session_user_agent_binding_mode)
        self._ip_change_threshold = settings.session_ip_change_threshold
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def create_session(
        self,
        user_id: str,
        token_jti: str,
        token_type: str,
        ip_address: str,
        user_agent: str | None,
        expires_at: datetime,
    ) -> Session:
        """
        Create a new session on login.

        Args:
            user_id: User ID
            token_jti: JWT ID from the access token
            token_type: Token type (access/refresh)
            ip_address: Client IP address
            user_agent: Client User-Agent string
            expires_at: When the session expires

        Returns:
            Created session
        """
        session_data = SessionCreate(
            user_id=user_id,
            token_jti=token_jti,
            token_type=token_type,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )

        session = await self._repo.create(session_data)

        self.logger.info(
            "session_created",
            user_id=user_id,
            session_id=session.id,
            ip=ip_address[:16] + "..." if len(ip_address) > 16 else ip_address,
            binding_modes=f"ip={self._ip_binding_mode.value}, ua={self._ua_binding_mode.value}",
        )

        return session

    async def validate_and_update(
        self,
        token_jti: str,
        ip_address: str,
        user_agent: str | None,
    ) -> tuple[bool, Session | None, str | None]:
        """
        Validate session binding and update activity.

        This is called on each authenticated request to:
        1. Check if session exists and is active
        2. Detect IP and User-Agent changes
        3. Log warnings/audit events based on binding mode
        4. Potentially block access in strict mode

        Args:
            token_jti: JWT ID from the request token
            ip_address: Current request IP
            user_agent: Current request User-Agent

        Returns:
            Tuple of (is_allowed, session, block_reason)
            - is_allowed: True if request should proceed
            - session: The session object (or None if not found)
            - block_reason: Reason if blocked (or None)
        """
        # Get and update session
        session, changes = await self._repo.update_activity(
            token_jti, ip_address, user_agent
        )

        if not session:
            # Session not found - could be pre-existing token without session
            # or expired session. Allow for backwards compatibility.
            self.logger.debug(
                "session_not_found",
                jti=token_jti[:16] + "..." if token_jti else "none",
            )
            return True, None, None

        # Check if session is revoked
        if session.status == SessionStatus.REVOKED:
            self.logger.warning(
                "revoked_session_access_attempt",
                session_id=session.id,
                user_id=session.user_id,
            )
            return False, session, "Session has been revoked"

        # Handle IP change
        ip_blocked = False
        ip_block_reason = None
        if changes.get("ip_changed"):
            ip_blocked, ip_block_reason = await self._handle_ip_change(
                session, changes["old_ip"], changes["new_ip"]
            )

        # Handle User-Agent change
        ua_blocked = False
        ua_block_reason = None
        if changes.get("user_agent_changed"):
            ua_blocked, ua_block_reason = await self._handle_user_agent_change(
                session, changes.get("old_user_agent"), changes.get("new_user_agent")
            )

        # Determine if access is blocked
        if ip_blocked:
            return False, session, ip_block_reason
        if ua_blocked:
            return False, session, ua_block_reason

        return True, session, None

    async def _handle_ip_change(
        self,
        session: Session,
        old_ip: str,
        new_ip: str,
    ) -> tuple[bool, str | None]:
        """
        Handle IP address change based on binding mode.

        Args:
            session: The session
            old_ip: Previous IP address
            new_ip: New IP address

        Returns:
            Tuple of (is_blocked, block_reason)
        """
        # Handle based on binding mode
        if self._ip_binding_mode == SessionBindingMode.DISABLED:
            return False, None

        elif self._ip_binding_mode == SessionBindingMode.LOG_ONLY:
            # Just log for audit trail
            self.logger.info(
                "session_ip_change_logged",
                session_id=session.id,
                user_id=session.user_id,
                old_ip=old_ip[:16] + "..." if len(old_ip) > 16 else old_ip,
                new_ip=new_ip[:16] + "..." if len(new_ip) > 16 else new_ip,
                change_count=session.ip_change_count,
            )
            return False, None

        elif self._ip_binding_mode == SessionBindingMode.WARN:
            # Log warning but allow
            self.logger.warning(
                "session_ip_change_warning",
                session_id=session.id,
                user_id=session.user_id,
                old_ip=old_ip[:16] + "..." if len(old_ip) > 16 else old_ip,
                new_ip=new_ip[:16] + "..." if len(new_ip) > 16 else new_ip,
                change_count=session.ip_change_count,
                threshold=self._ip_change_threshold,
            )

            # Flag as suspicious if threshold exceeded
            if session.ip_change_count >= self._ip_change_threshold:
                await self._repo.flag_suspicious(
                    session.token_jti,
                    f"IP changed {session.ip_change_count} times (threshold: {self._ip_change_threshold})"
                )

            return False, None

        elif self._ip_binding_mode == SessionBindingMode.FLEXIBLE:
            # Block only if threshold exceeded
            if session.ip_change_count >= self._ip_change_threshold:
                self.logger.warning(
                    "session_ip_change_blocked_threshold",
                    session_id=session.id,
                    user_id=session.user_id,
                    change_count=session.ip_change_count,
                    threshold=self._ip_change_threshold,
                )
                await self._repo.flag_suspicious(
                    session.token_jti,
                    f"IP changed {session.ip_change_count} times (exceeded threshold)"
                )
                return True, f"Too many IP changes detected ({session.ip_change_count})"

            self.logger.warning(
                "session_ip_change_allowed_under_threshold",
                session_id=session.id,
                user_id=session.user_id,
                change_count=session.ip_change_count,
                threshold=self._ip_change_threshold,
            )
            return False, None

        elif self._ip_binding_mode == SessionBindingMode.STRICT:
            # Block any IP change
            self.logger.warning(
                "session_ip_change_blocked_strict",
                session_id=session.id,
                user_id=session.user_id,
                old_ip=old_ip[:16] + "..." if len(old_ip) > 16 else old_ip,
                new_ip=new_ip[:16] + "..." if len(new_ip) > 16 else new_ip,
            )
            await self._repo.flag_suspicious(
                session.token_jti,
                f"IP changed from {old_ip} to {new_ip} (strict mode)"
            )
            return True, "IP address change not allowed"

        return False, None

    async def _handle_user_agent_change(
        self,
        session: Session,
        old_ua: str | None,
        new_ua: str | None,
    ) -> tuple[bool, str | None]:
        """
        Handle User-Agent change based on binding mode.

        Args:
            session: The session
            old_ua: Previous User-Agent
            new_ua: New User-Agent

        Returns:
            Tuple of (is_blocked, block_reason)
        """
        # Handle based on binding mode
        if self._ua_binding_mode == SessionBindingMode.DISABLED:
            return False, None

        elif self._ua_binding_mode == SessionBindingMode.LOG_ONLY:
            # Just log for audit trail
            self.logger.info(
                "session_user_agent_change_logged",
                session_id=session.id,
                user_id=session.user_id,
                change_count=session.user_agent_change_count,
            )
            return False, None

        elif self._ua_binding_mode == SessionBindingMode.WARN:
            # Log warning but allow
            self.logger.warning(
                "session_user_agent_change_warning",
                session_id=session.id,
                user_id=session.user_id,
                change_count=session.user_agent_change_count,
            )
            return False, None

        elif self._ua_binding_mode == SessionBindingMode.FLEXIBLE:
            # Allow User-Agent changes up to threshold
            # (Browser updates are common, so this is lenient)
            if session.user_agent_change_count >= 5:  # Higher threshold for UA
                self.logger.warning(
                    "session_user_agent_change_suspicious",
                    session_id=session.id,
                    user_id=session.user_id,
                    change_count=session.user_agent_change_count,
                )
                await self._repo.flag_suspicious(
                    session.token_jti,
                    f"User-Agent changed {session.user_agent_change_count} times"
                )
            return False, None

        elif self._ua_binding_mode == SessionBindingMode.STRICT:
            # Block any User-Agent change
            self.logger.warning(
                "session_user_agent_change_blocked_strict",
                session_id=session.id,
                user_id=session.user_id,
            )
            await self._repo.flag_suspicious(
                session.token_jti,
                "User-Agent changed (strict mode)"
            )
            return True, "User-Agent change not allowed"

        return False, None

    async def get_user_sessions(
        self,
        user_id: str,
        current_jti: str | None = None,
    ) -> SessionListResponse:
        """
        Get list of user's active sessions.

        Args:
            user_id: User ID
            current_jti: JTI of current session (to mark as current)

        Returns:
            SessionListResponse with public session data
        """
        sessions = await self._repo.get_user_sessions(user_id)

        public_sessions = []
        for session in sessions:
            public = SessionPublic(
                id=session.id,
                token_type=session.token_type,
                initial_ip=SessionPublic.mask_ip(session.initial_ip),
                last_ip=SessionPublic.mask_ip(session.last_ip),
                last_activity=session.last_activity,
                request_count=session.request_count,
                ip_change_count=session.ip_change_count,
                user_agent_change_count=session.user_agent_change_count,
                status=session.status,
                expires_at=session.expires_at,
                created_at=session.created_at,
                is_current=(session.token_jti == current_jti) if current_jti else False,
            )
            public_sessions.append(public)

        return SessionListResponse(
            sessions=public_sessions,
            total=len(public_sessions),
            current_session_id=current_jti,
        )

    async def revoke_session(
        self,
        user_id: str,
        session_jti: str,
        reason: str | None = None,
    ) -> bool:
        """
        Revoke a specific session.

        Args:
            user_id: User ID (for authorization check)
            session_jti: JTI of session to revoke
            reason: Reason for revocation

        Returns:
            True if revoked
        """
        # Verify session belongs to user
        session = await self._repo.get_by_jti(session_jti)
        if not session or session.user_id != user_id:
            return False

        success = await self._repo.revoke_session(session_jti, reason)

        if success:
            self.logger.info(
                "session_revoked_by_user",
                session_id=session_jti[:16] + "...",
                user_id=user_id,
                reason=reason,
            )

        return success

    async def revoke_all_sessions(
        self,
        user_id: str,
        except_current_jti: str | None = None,
        reason: str | None = None,
    ) -> int:
        """
        Revoke all sessions for a user.

        Args:
            user_id: User ID
            except_current_jti: JTI of current session to keep (optional)
            reason: Reason for revocation

        Returns:
            Number of sessions revoked
        """
        count = await self._repo.revoke_user_sessions(
            user_id, except_current_jti, reason
        )

        if count > 0:
            self.logger.info(
                "all_sessions_revoked_by_user",
                user_id=user_id,
                count=count,
                except_current=except_current_jti is not None,
                reason=reason,
            )

        return count

    async def get_active_session_count(self, user_id: str) -> int:
        """Get count of active sessions for a user."""
        return await self._repo.count_active_sessions(user_id)
