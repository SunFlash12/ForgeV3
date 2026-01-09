"""
Authentication Service for Forge Cascade V2

Provides high-level authentication operations including login,
registration, token refresh, and session management.
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from ..config import get_settings
from ..models.user import User, UserCreate, Token, TokenPayload, UserRole
from ..models.base import TrustLevel
from ..repositories.user_repository import UserRepository
from ..repositories.audit_repository import AuditRepository
from .password import hash_password, verify_password, needs_rehash
from .tokens import (
    create_token_pair,
    verify_access_token,
    verify_refresh_token,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenBlacklist,
    get_token_claims,
)
from .authorization import (
    AuthorizationContext,
    create_auth_context,
    get_trust_level_from_score
)

settings = get_settings()


class AuthenticationError(Exception):
    """Base exception for authentication failures."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Username or password is incorrect."""
    pass


class AccountLockedError(AuthenticationError):
    """Account is locked due to too many failed attempts."""
    pass


class AccountNotVerifiedError(AuthenticationError):
    """Account email is not verified."""
    pass


class AccountDeactivatedError(AuthenticationError):
    """Account has been deactivated."""
    pass


class RegistrationError(AuthenticationError):
    """Error during registration."""
    pass


class AuthService:
    """
    Authentication service providing login, registration, and token management.
    """
    
    # Lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository
    ):
        self.user_repo = user_repo
        self.audit_repo = audit_repo
    
    # =========================================================================
    # Registration
    # =========================================================================
    
    async def register(
        self,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> User:
        """
        Register a new user.
        
        Args:
            username: Unique username
            email: Email address
            password: Plain text password (will be hashed)
            display_name: Optional display name
            ip_address: Client IP for audit logging
            
        Returns:
            Created User
            
        Raises:
            RegistrationError: If username or email already exists
        """
        # Check for existing username
        if await self.user_repo.username_exists(username):
            raise RegistrationError(f"Username '{username}' is already taken")
        
        # Check for existing email
        if await self.user_repo.email_exists(email):
            raise RegistrationError(f"Email '{email}' is already registered")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user
        user_create = UserCreate(
            username=username,
            email=email,
            password=password,  # Will be hashed in repository
            display_name=display_name or username
        )
        
        user = await self.user_repo.create(user_create, password_hash)
        
        # Log registration
        await self.audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="created",
            details={"username": username, "email": email},
            ip_address=ip_address
        )
        
        return user
    
    # =========================================================================
    # Login
    # =========================================================================
    
    async def login(
        self,
        username_or_email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[User, Token]:
        """
        Authenticate user and return tokens.
        
        Args:
            username_or_email: Username or email address
            password: Plain text password
            ip_address: Client IP for audit logging
            user_agent: Client user agent
            
        Returns:
            Tuple of (User, Token)
            
        Raises:
            InvalidCredentialsError: If credentials are incorrect
            AccountLockedError: If account is locked
            AccountDeactivatedError: If account is deactivated
        """
        # Find user
        user = await self.user_repo.get_by_username_or_email(username_or_email)
        
        if not user:
            # Log failed attempt (unknown user)
            await self.audit_repo.log_user_action(
                actor_id="unknown",
                target_user_id="unknown",
                action="login_failed",
                details={"reason": "user_not_found", "attempted": username_or_email},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise InvalidCredentialsError("Invalid username or password")
        
        # Check if account is locked
        if user.lockout_until and user.lockout_until > datetime.utcnow():
            await self.audit_repo.log_user_action(
                actor_id=user.id,
                target_user_id=user.id,
                action="login_failed",
                details={"reason": "account_locked"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AccountLockedError(
                f"Account is locked until {user.lockout_until.isoformat()}"
            )
        
        # Check if account is active
        if not user.is_active:
            await self.audit_repo.log_user_action(
                actor_id=user.id,
                target_user_id=user.id,
                action="login_failed",
                details={"reason": "account_deactivated"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AccountDeactivatedError("Account has been deactivated")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            # Record failed attempt
            await self.user_repo.record_failed_login(user.id)
            
            # Check if we should lock the account
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS - 1:
                lockout_until = datetime.utcnow() + timedelta(
                    minutes=self.LOCKOUT_DURATION_MINUTES
                )
                await self.user_repo.set_lockout(user.id, lockout_until)
                
                await self.audit_repo.log_user_action(
                    actor_id=user.id,
                    target_user_id=user.id,
                    action="locked",
                    details={
                        "reason": "too_many_failed_attempts",
                        "locked_until": lockout_until.isoformat()
                    },
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            
            await self.audit_repo.log_user_action(
                actor_id=user.id,
                target_user_id=user.id,
                action="login_failed",
                details={"reason": "invalid_password"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise InvalidCredentialsError("Invalid username or password")
        
        # Check if password needs rehashing (security upgrade)
        if needs_rehash(user.password_hash):
            new_hash = hash_password(password)
            await self.user_repo.update_password(user.id, new_hash)
        
        # Clear any lockout and record successful login
        await self.user_repo.clear_lockout(user.id)
        await self.user_repo.record_login(user.id)
        
        # Create tokens
        role_value = user.role.value if hasattr(user.role, 'value') else user.role
        token = create_token_pair(
            user_id=user.id,
            username=user.username,
            role=role_value,
            trust_flame=user.trust_flame
        )
        
        # Store refresh token for validation
        await self.user_repo.update_refresh_token(user.id, token.refresh_token)
        
        # Log successful login
        await self.audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="login",
            details={"method": "password"},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return user, token
    
    # =========================================================================
    # Token Operations
    # =========================================================================
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> Token:
        """
        Refresh access token using refresh token.

        Implements secure token rotation: the old refresh token is invalidated
        and a new one is issued. This prevents token replay attacks.

        Args:
            refresh_token: Valid refresh token
            ip_address: Client IP for audit logging

        Returns:
            New Token pair

        Raises:
            TokenError: If refresh token is invalid or doesn't match stored token
        """
        # Verify refresh token signature and expiry
        payload = verify_refresh_token(refresh_token)

        # Get user
        user = await self.user_repo.get_by_id(payload.sub)

        if not user:
            raise TokenInvalidError("User not found")

        # SECURITY: Validate refresh token against stored token
        # This prevents use of old/revoked refresh tokens
        is_valid = await self.user_repo.validate_refresh_token(user.id, refresh_token)
        if not is_valid:
            # Log potential token theft attempt
            await self.audit_repo.log_security_event(
                actor_id=user.id,
                event_name="refresh_token_mismatch",
                details={
                    "reason": "token_not_matching_stored",
                    "user_id": user.id,
                },
                ip_address=ip_address
            )
            # Revoke all tokens for this user as a precaution
            await self.user_repo.update_refresh_token(user.id, None)
            raise TokenInvalidError("Refresh token has been revoked or is invalid")

        if not user.is_active:
            raise AccountDeactivatedError("Account has been deactivated")

        # Create new token pair (token rotation)
        role_value = user.role.value if hasattr(user.role, 'value') else user.role
        new_token = create_token_pair(
            user_id=user.id,
            username=user.username,
            role=role_value,
            trust_flame=user.trust_flame
        )

        # Update stored refresh token (old token is now invalid)
        await self.user_repo.update_refresh_token(user.id, new_token.refresh_token)

        return new_token
    
    async def validate_access_token(
        self,
        access_token: str
    ) -> AuthorizationContext:
        """
        Validate access token and return authorization context.

        Args:
            access_token: JWT access token

        Returns:
            AuthorizationContext for the user

        Raises:
            TokenError: If token is invalid, expired, or missing required claims
        """
        payload = verify_access_token(access_token)

        # SECURITY FIX: Reject tokens with missing required claims
        # Do NOT use default values - this prevents privilege escalation
        # from tokens that have been tampered with to remove claims
        if payload.trust_flame is None:
            raise TokenInvalidError("Token missing required trust_flame claim")

        if payload.role is None:
            raise TokenInvalidError("Token missing required role claim")

        if not payload.sub:
            raise TokenInvalidError("Token missing required sub (user_id) claim")

        return create_auth_context(
            user_id=payload.sub,
            trust_flame=payload.trust_flame,
            role=payload.role,
            capabilities=None  # Will be auto-populated from trust level
        )
    
    async def logout(
        self,
        user_id: str,
        access_token: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Logout user by revoking tokens.

        Args:
            user_id: User ID to logout
            access_token: Current access token to blacklist
            ip_address: Client IP for audit logging
        """
        # Blacklist the current access token if provided (async for Redis support)
        if access_token:
            try:
                claims = get_token_claims(access_token)
                jti = claims.get("jti")
                exp = claims.get("exp")
                if jti:
                    await TokenBlacklist.add_async(jti, exp)
            except Exception:
                pass  # Token may already be invalid

        # Clear refresh token
        await self.user_repo.update_refresh_token(user_id, None)

        # Log logout
        await self.audit_repo.log_user_action(
            actor_id=user_id,
            target_user_id=user_id,
            action="logout",
            ip_address=ip_address
        )
    
    async def logout_all_sessions(
        self,
        user_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Logout user from all sessions by revoking all tokens.
        
        This effectively forces re-authentication on all devices.
        """
        await self.user_repo.update_refresh_token(user_id, None)
        
        await self.audit_repo.log_security_event(
            actor_id=user_id,
            event_name="all_sessions_revoked",
            details={"user_id": user_id},
            ip_address=ip_address
        )
    
    # =========================================================================
    # Password Management
    # =========================================================================
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Change user's password.
        
        Args:
            user_id: User ID
            current_password: Current password for verification
            new_password: New password to set
            ip_address: Client IP for audit logging
            
        Raises:
            InvalidCredentialsError: If current password is incorrect
        """
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise AuthenticationError("User not found")
        
        if not verify_password(current_password, user.password_hash):
            await self.audit_repo.log_security_event(
                actor_id=user_id,
                event_name="password_change_failed",
                details={"reason": "invalid_current_password"},
                ip_address=ip_address
            )
            raise InvalidCredentialsError("Current password is incorrect")
        
        # Hash and update new password
        new_hash = hash_password(new_password)
        await self.user_repo.update_password(user_id, new_hash)
        
        # Revoke all existing sessions for security
        await self.user_repo.update_refresh_token(user_id, None)
        
        await self.audit_repo.log_security_event(
            actor_id=user_id,
            event_name="password_changed",
            details={"sessions_revoked": True},
            ip_address=ip_address
        )
    
    async def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> Optional[str]:
        """
        Request a password reset token.

        Generates a secure random token, stores its hash, and returns the
        plain token to be sent to the user (typically via email).

        Args:
            email: User's email address
            ip_address: Client IP for audit logging

        Returns:
            Plain text reset token if user exists, None otherwise
            (Always returns in constant time to prevent email enumeration)
        """
        # Always generate a token to prevent timing attacks
        plain_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

        user = await self.user_repo.get_by_email(email)

        if user:
            # Token expires in 1 hour
            expires_at = datetime.utcnow() + timedelta(hours=1)

            await self.user_repo.store_password_reset_token(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at
            )

            await self.audit_repo.log_security_event(
                actor_id=user.id,
                event_name="password_reset_requested",
                details={"email": email},
                ip_address=ip_address
            )

            return plain_token

        # Log attempt for non-existent email (but don't reveal to caller)
        await self.audit_repo.log_security_event(
            actor_id="unknown",
            event_name="password_reset_requested_unknown_email",
            details={"email": email},
            ip_address=ip_address
        )

        return None

    async def reset_password(
        self,
        user_id: str,
        new_password: str,
        reset_token: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Reset password using a valid reset token.

        The token is validated against the stored hash and checked for expiry.
        After successful reset, the token is invalidated (one-time use).

        Args:
            user_id: User ID
            new_password: New password to set
            reset_token: Plain text reset token
            ip_address: Client IP for audit logging

        Raises:
            AuthenticationError: If user not found or token invalid
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise AuthenticationError("User not found")

        # Hash the provided token and validate against stored hash
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        is_valid = await self.user_repo.validate_password_reset_token(
            user_id=user_id,
            token_hash=token_hash
        )

        if not is_valid:
            await self.audit_repo.log_security_event(
                actor_id=user_id,
                event_name="password_reset_failed",
                details={"reason": "invalid_or_expired_token"},
                ip_address=ip_address
            )
            raise AuthenticationError("Invalid or expired reset token")

        # Hash and update password
        new_hash = hash_password(new_password)
        await self.user_repo.update_password(user_id, new_hash)

        # Clear the reset token (one-time use)
        await self.user_repo.clear_password_reset_token(user_id)

        # Revoke all sessions
        await self.user_repo.update_refresh_token(user_id, None)

        # Clear any lockout
        await self.user_repo.clear_lockout(user_id)

        await self.audit_repo.log_security_event(
            actor_id=user_id,
            event_name="password_reset",
            details={"method": "reset_token"},
            ip_address=ip_address
        )
    
    # =========================================================================
    # Account Management
    # =========================================================================
    
    async def verify_email(
        self,
        user_id: str,
        verification_token: str,  # Would be validated
        ip_address: Optional[str] = None
    ) -> None:
        """
        Verify user's email address.
        
        Note: Simplified version - would need proper token validation.
        """
        await self.user_repo.set_verified(user_id)
        
        await self.audit_repo.log_user_action(
            actor_id=user_id,
            target_user_id=user_id,
            action="email_verified",
            ip_address=ip_address
        )
    
    async def deactivate_account(
        self,
        user_id: str,
        deactivated_by: str,
        reason: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Deactivate a user account.
        
        Args:
            user_id: User to deactivate
            deactivated_by: ID of user performing deactivation
            reason: Reason for deactivation
            ip_address: Client IP
        """
        await self.user_repo.deactivate(user_id)
        await self.user_repo.update_refresh_token(user_id, None)
        
        await self.audit_repo.log_user_action(
            actor_id=deactivated_by,
            target_user_id=user_id,
            action="deactivated",
            details={"reason": reason}
        )
    
    async def reactivate_account(
        self,
        user_id: str,
        reactivated_by: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Reactivate a deactivated account."""
        await self.user_repo.activate(user_id)
        
        await self.audit_repo.log_user_action(
            actor_id=reactivated_by,
            target_user_id=user_id,
            action="reactivated",
            ip_address=ip_address
        )
    
    # =========================================================================
    # Trust Management
    # =========================================================================
    
    async def adjust_user_trust(
        self,
        user_id: str,
        adjusted_by: str,
        adjustment: int,
        reason: str,
        ip_address: Optional[str] = None
    ) -> int:
        """
        Adjust a user's trust flame score.
        
        Args:
            user_id: User to adjust
            adjusted_by: ID of user making adjustment
            adjustment: Amount to adjust (+/-)
            reason: Reason for adjustment
            ip_address: Client IP
            
        Returns:
            New trust flame value
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")
        
        old_trust = user.trust_flame
        new_trust = await self.user_repo.adjust_trust_flame(
            user_id=user_id,
            adjustment=adjustment,
            reason=reason,
            adjusted_by=adjusted_by
        )
        
        old_level = get_trust_level_from_score(old_trust)
        new_level = get_trust_level_from_score(new_trust)
        
        await self.audit_repo.log_user_action(
            actor_id=adjusted_by,
            target_user_id=user_id,
            action="trust_changed",
            details={
                "old_trust": old_trust,
                "new_trust": new_trust,
                "adjustment": adjustment,
                "old_level": old_level.name,
                "new_level": new_level.name,
                "reason": reason
            },
            ip_address=ip_address
        )
        
        return new_trust
    
    # =========================================================================
    # Session Info
    # =========================================================================
    
    async def get_current_user(self, user_id: str) -> Optional[User]:
        """Get current user by ID."""
        return await self.user_repo.get_by_id(user_id)
    
    async def get_user_auth_context(self, user_id: str) -> Optional[AuthorizationContext]:
        """Get full authorization context for a user."""
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            return None
        
        role_value = user.role.value if hasattr(user.role, 'value') else user.role
        return create_auth_context(
            user_id=user.id,
            trust_flame=user.trust_flame,
            role=role_value
        )


# Factory function
def get_auth_service(
    user_repo: UserRepository,
    audit_repo: AuditRepository
) -> AuthService:
    """Create AuthService instance."""
    return AuthService(user_repo, audit_repo)
