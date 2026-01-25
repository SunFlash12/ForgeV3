"""
Authentication Service for Forge Cascade V2

Provides high-level authentication operations including login,
registration, token refresh, and session management.

SECURITY FIX (Audit 4 - M2): Added IP-based rate limiting to prevent
credential stuffing attacks across multiple accounts.

SECURITY FIX (Audit 5): IP rate limiting now uses Redis for distributed
deployments, falling back to in-memory when Redis unavailable.
"""

import hashlib
import secrets
import threading
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)

# Try to import redis for distributed rate limiting
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False
from ..models.user import Token, User, UserCreate
from ..repositories.audit_repository import AuditRepository
from ..repositories.user_repository import UserRepository
from .authorization import AuthorizationContext, create_auth_context, get_trust_level_from_score
from .password import (
    check_password_history,
    hash_password,
    needs_rehash,
    update_password_history,
    verify_password,
)
from .tokens import (
    TokenBlacklist,
    TokenInvalidError,
    create_token_pair,
    get_token_claims,
    verify_access_token,
    verify_refresh_token,
    verify_refresh_token_async,
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


class IPRateLimitExceededError(AuthenticationError):
    """Too many login attempts from this IP address."""
    pass


class IPRateLimiter:
    """
    SECURITY FIX (Audit 4 - M2): IP-based rate limiting to prevent credential stuffing.

    Tracks failed login attempts per IP address (not per account) to prevent
    attackers from trying different passwords across many accounts from the same IP.

    This complements per-account lockout by also limiting the total number of
    failed attempts from a single IP address across ALL accounts.

    SECURITY FIX (Audit 5): Now uses Redis for distributed deployments.
    In multi-instance deployments, all instances share rate limit data via Redis.
    Falls back to in-memory storage when Redis is unavailable.
    """

    # Rate limit settings
    MAX_ATTEMPTS_PER_WINDOW = 20  # Max failed attempts per IP per window
    WINDOW_SECONDS = 300  # 5 minute window
    LOCKOUT_SECONDS = 900  # 15 minute lockout after exceeding limit
    MAX_IPS = 50000  # Max tracked IPs (memory limit for fallback)

    # Redis key prefixes
    _REDIS_ATTEMPTS_PREFIX = "forge:ratelimit:ip:attempts:"
    _REDIS_LOCKOUT_PREFIX = "forge:ratelimit:ip:lockout:"

    def __init__(self):
        # In-memory fallback storage
        self._attempts: OrderedDict[str, list[datetime]] = OrderedDict()
        self._lockouts: dict[str, datetime] = {}
        self._lock = threading.Lock()
        # Redis client (initialized lazily)
        self._redis_client = None
        self._redis_initialized = False

    async def _get_redis(self):
        """Get or initialize Redis client."""
        if self._redis_initialized:
            return self._redis_client

        if not REDIS_AVAILABLE:
            logger.info("ip_rate_limiter_memory_mode", reason="redis library not installed")
            self._redis_initialized = True
            return None

        redis_url = settings.redis_url
        if not redis_url:
            logger.info("ip_rate_limiter_memory_mode", reason="no redis URL configured")
            self._redis_initialized = True
            return None

        try:
            self._redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            await self._redis_client.ping()
            self._redis_initialized = True
            logger.info("ip_rate_limiter_redis_connected")
            return self._redis_client
        except Exception as e:
            logger.warning("ip_rate_limiter_redis_failed", error=str(e))
            self._redis_client = None
            self._redis_initialized = True
            return None

    def _cleanup_old_entries(self) -> None:
        """Remove expired entries (must hold lock). For in-memory fallback only."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)

        # Clean up old attempts
        to_remove = []
        for ip, attempts in self._attempts.items():
            # Remove old attempts within each IP
            self._attempts[ip] = [a for a in attempts if a > cutoff]
            if not self._attempts[ip]:
                to_remove.append(ip)

        for ip in to_remove:
            del self._attempts[ip]

        # Clean up expired lockouts
        expired_lockouts = [ip for ip, exp in self._lockouts.items() if exp < now]
        for ip in expired_lockouts:
            del self._lockouts[ip]

    async def check_rate_limit_async(self, ip_address: str) -> tuple[bool, int]:
        """
        Check if IP is rate limited (async version with Redis support).

        SECURITY FIX (Audit 5): Now checks Redis for distributed rate limiting.

        Returns:
            Tuple of (is_allowed, seconds_until_allowed)
        """
        if not ip_address:
            return (True, 0)

        redis = await self._get_redis()
        if redis:
            try:
                # Check lockout in Redis
                lockout_key = f"{self._REDIS_LOCKOUT_PREFIX}{ip_address}"
                lockout_ttl = await redis.ttl(lockout_key)
                if lockout_ttl > 0:
                    return (False, lockout_ttl)

                # Count attempts in Redis using a sorted set with timestamps
                attempts_key = f"{self._REDIS_ATTEMPTS_PREFIX}{ip_address}"
                now = datetime.now(UTC).timestamp()
                cutoff = now - self.WINDOW_SECONDS

                # Remove old entries and count remaining
                await redis.zremrangebyscore(attempts_key, "-inf", cutoff)
                attempt_count = await redis.zcard(attempts_key)

                if attempt_count >= self.MAX_ATTEMPTS_PER_WINDOW:
                    # Trigger lockout
                    await redis.setex(lockout_key, self.LOCKOUT_SECONDS, "1")
                    logger.warning(
                        "ip_rate_limit_triggered",
                        ip_hash=hashlib.sha256(ip_address.encode()).hexdigest()[:16],
                        attempts=attempt_count
                    )
                    return (False, self.LOCKOUT_SECONDS)

                return (True, 0)
            except Exception as e:
                logger.warning("ip_rate_limiter_redis_error", error=str(e), operation="check")
                # Fall through to in-memory

        # In-memory fallback
        return self.check_rate_limit(ip_address)

    def check_rate_limit(self, ip_address: str) -> tuple[bool, int]:
        """
        Check if IP is rate limited (sync version, in-memory only).

        Returns:
            Tuple of (is_allowed, seconds_until_allowed)
        """
        if not ip_address:
            return (True, 0)  # No IP means we can't rate limit

        with self._lock:
            now = datetime.now(UTC)

            # Check if IP is in lockout
            lockout_until = self._lockouts.get(ip_address)
            if lockout_until and lockout_until > now:
                seconds_remaining = int((lockout_until - now).total_seconds())
                return (False, seconds_remaining)

            # Count recent attempts
            attempts = self._attempts.get(ip_address, [])
            cutoff = now - timedelta(seconds=self.WINDOW_SECONDS)
            recent_attempts = [a for a in attempts if a > cutoff]

            if len(recent_attempts) >= self.MAX_ATTEMPTS_PER_WINDOW:
                # Trigger lockout
                self._lockouts[ip_address] = now + timedelta(seconds=self.LOCKOUT_SECONDS)
                return (False, self.LOCKOUT_SECONDS)

            return (True, 0)

    async def record_attempt_async(self, ip_address: str, success: bool) -> None:
        """
        Record a login attempt (async version with Redis support).

        SECURITY FIX (Audit 5): Now records to Redis for distributed rate limiting.

        Only failed attempts count against the rate limit.
        Successful logins reset the counter for that IP.
        """
        if not ip_address:
            return

        redis = await self._get_redis()
        if redis:
            try:
                attempts_key = f"{self._REDIS_ATTEMPTS_PREFIX}{ip_address}"
                lockout_key = f"{self._REDIS_LOCKOUT_PREFIX}{ip_address}"

                if success:
                    # Successful login - clear failed attempts for this IP
                    await redis.delete(attempts_key, lockout_key)
                else:
                    # Failed login - record attempt with timestamp as score
                    now = datetime.now(UTC).timestamp()
                    await redis.zadd(attempts_key, {str(now): now})
                    # Set expiry on the attempts set
                    await redis.expire(attempts_key, self.WINDOW_SECONDS + 60)
                return
            except Exception as e:
                logger.warning("ip_rate_limiter_redis_error", error=str(e), operation="record")
                # Fall through to in-memory

        # In-memory fallback
        self.record_attempt(ip_address, success)

    def record_attempt(self, ip_address: str, success: bool) -> None:
        """
        Record a login attempt (sync version, in-memory only).

        Only failed attempts count against the rate limit.
        Successful logins reset the counter for that IP.
        """
        if not ip_address:
            return

        with self._lock:
            self._cleanup_old_entries()

            if success:
                # Successful login - clear failed attempts for this IP
                self._attempts.pop(ip_address, None)
                self._lockouts.pop(ip_address, None)
            else:
                # Failed login - record attempt
                if ip_address not in self._attempts:
                    # Enforce max IPs limit
                    if len(self._attempts) >= self.MAX_IPS:
                        # Remove oldest 10%
                        to_remove = self.MAX_IPS // 10
                        for _ in range(to_remove):
                            if self._attempts:
                                self._attempts.popitem(last=False)

                    self._attempts[ip_address] = []

                self._attempts[ip_address].append(datetime.now(UTC))


# Global IP rate limiter instance
_ip_rate_limiter = IPRateLimiter()


def get_ip_rate_limiter() -> IPRateLimiter:
    """Get the global IP rate limiter."""
    return _ip_rate_limiter


class AuthService:
    """
    Authentication service providing login, registration, and token management.

    SECURITY FIX (Audit 4 - M2): Now includes IP-based rate limiting to prevent
    credential stuffing attacks across multiple accounts.
    """

    # Lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    def __init__(
        self,
        user_repo: UserRepository,
        audit_repo: AuditRepository,
        ip_rate_limiter: IPRateLimiter | None = None,
    ):
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        # SECURITY FIX (Audit 4 - M2): IP-based rate limiting
        self._ip_rate_limiter = ip_rate_limiter or get_ip_rate_limiter()

    # =========================================================================
    # Registration
    # =========================================================================

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        display_name: str | None = None,
        ip_address: str | None = None
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
        # Pre-check for better error messages (user-friendly)
        # Note: Database unique constraints are the authoritative check
        if await self.user_repo.username_exists(username):
            raise RegistrationError(f"Username '{username}' is already taken")

        if await self.user_repo.email_exists(email):
            raise RegistrationError(f"Email '{email}' is already registered")

        # Hash password (with context-aware validation)
        # SECURITY FIX (Audit 3): Pass username/email for context-aware password validation
        password_hash = hash_password(password, username=username, email=email)

        # Create user
        user_create = UserCreate(
            username=username,
            email=email,
            password=password,  # Will be hashed in repository
            display_name=display_name or username
        )

        # SECURITY FIX (Audit 6): Handle TOCTOU race condition with DB constraints
        # The pre-checks above are for user-friendly errors; DB constraints are authoritative
        try:
            user = await self.user_repo.create(user_create, password_hash)
        except Exception as e:
            # Handle database constraint violations from race conditions
            error_msg = str(e).lower()
            if "username" in error_msg and ("unique" in error_msg or "duplicate" in error_msg or "exists" in error_msg):
                raise RegistrationError(f"Username '{username}' is already taken")
            if "email" in error_msg and ("unique" in error_msg or "duplicate" in error_msg or "exists" in error_msg):
                raise RegistrationError(f"Email '{email}' is already registered")
            # Re-raise unexpected errors
            raise

        # Log registration
        # SECURITY FIX (Audit 3): Hash email in audit logs to prevent PII exposure
        import hashlib
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
        await self.audit_repo.log_user_action(
            actor_id=user.id,
            target_user_id=user.id,
            action="created",
            details={"username": username, "email_hash": email_hash},
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
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> tuple[User, Token]:
        """
        Authenticate user and return tokens.

        SECURITY FIX (Audit 4 - M2): Now checks IP-based rate limiting before
        processing login to prevent credential stuffing attacks.

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
            IPRateLimitExceededError: If too many failed attempts from this IP
        """
        # SECURITY FIX (Audit 4 - M2): Check IP-based rate limit FIRST
        # This prevents credential stuffing across multiple accounts
        # SECURITY FIX (Audit 5): Now uses Redis for distributed rate limiting
        if ip_address:
            is_allowed, seconds_remaining = await self._ip_rate_limiter.check_rate_limit_async(ip_address)
            if not is_allowed:
                await self.audit_repo.log_user_action(
                    actor_id="unknown",
                    target_user_id="unknown",
                    action="login_blocked",
                    details={
                        "reason": "ip_rate_limited",
                        "seconds_remaining": seconds_remaining,
                    },
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                raise IPRateLimitExceededError(
                    f"Too many login attempts. Please wait {seconds_remaining} seconds."
                )

        # Find user
        user = await self.user_repo.get_by_username_or_email(username_or_email)

        if not user:
            # SECURITY FIX (Audit 4 - M2): Record failed attempt for IP rate limiting
            # SECURITY FIX (Audit 5): Now uses Redis for distributed rate limiting
            if ip_address:
                await self._ip_rate_limiter.record_attempt_async(ip_address, success=False)

            # SECURITY FIX (Audit 3): Don't log the attempted username/email to prevent
            # user enumeration via log analysis. Hash it for correlation if needed.
            masked_identifier = hashlib.sha256(username_or_email.encode()).hexdigest()[:16]
            await self.audit_repo.log_user_action(
                actor_id="unknown",
                target_user_id="unknown",
                action="login_failed",
                details={"reason": "user_not_found", "identifier_hash": masked_identifier},
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise InvalidCredentialsError("Invalid username or password")

        # Check if account is locked
        if user.lockout_until and user.lockout_until > datetime.now(UTC):
            await self.audit_repo.log_user_action(
                actor_id=user.id,
                target_user_id=user.id,
                action="login_failed",
                details={"reason": "account_locked"},
                ip_address=ip_address,
                user_agent=user_agent
            )
            # SECURITY FIX (Audit 4 - L1): Use generic message to avoid revealing lockout duration
            raise AccountLockedError(
                "Account is temporarily locked due to too many failed login attempts. "
                "Please try again later or contact support."
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
            # SECURITY FIX (Audit 4 - M2): Record failed attempt for IP rate limiting
            # SECURITY FIX (Audit 5): Now uses Redis for distributed rate limiting
            if ip_address:
                await self._ip_rate_limiter.record_attempt_async(ip_address, success=False)

            # Record failed attempt
            await self.user_repo.record_failed_login(user.id)

            # Check if we should lock the account
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS - 1:
                lockout_until = datetime.now(UTC) + timedelta(
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
            # Skip validation - password was already validated when originally created
            new_hash = hash_password(password, validate=False)
            await self.user_repo.update_password(user.id, new_hash)

        # Clear any lockout and record successful login
        await self.user_repo.clear_lockout(user.id)
        await self.user_repo.record_login(user.id)

        # SECURITY FIX (Audit 4 - M2): Record successful login to clear IP rate limit
        # SECURITY FIX (Audit 5): Now uses Redis for distributed rate limiting
        if ip_address:
            await self._ip_rate_limiter.record_attempt_async(ip_address, success=True)

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
        ip_address: str | None = None
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
        # SECURITY FIX (Audit 5): Use async version for full Redis blacklist support
        payload = await verify_refresh_token_async(refresh_token)

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

        # SECURITY FIX (Audit 5): Blacklist the old refresh token before issuing new one
        # This prevents token replay even if the stored token validation is bypassed
        await TokenBlacklist.add_async(
            jti=payload.jti,
            expires_at=payload.exp  # Use original expiry time - FIXED: was 'exp='
        )
        logger.debug(
            "refresh_token_blacklisted",
            user_id=user.id,
            old_jti=payload.jti[:16] + "..." if payload.jti else None,
        )

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
        access_token: str | None = None,
        ip_address: str | None = None
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
        ip_address: str | None = None
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
        ip_address: str | None = None
    ) -> None:
        """
        Change user's password.

        SECURITY FIX (Audit 6): Added password history check to prevent
        reusing recently used passwords.

        Args:
            user_id: User ID
            current_password: Current password for verification
            new_password: New password to set
            ip_address: Client IP for audit logging

        Raises:
            InvalidCredentialsError: If current password is incorrect
            PasswordValidationError: If new password was recently used
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

        # SECURITY FIX (Audit 6): Check password history to prevent reuse
        # Get password history from user (may be empty for older accounts)
        password_history = getattr(user, 'password_history', []) or []
        # Also check against current password hash
        all_history = [user.password_hash] + password_history
        check_password_history(new_password, all_history)

        # Hash and update new password (with context-aware validation)
        # SECURITY FIX (Audit 3): Pass username/email for context-aware password validation
        new_hash = hash_password(new_password, username=user.username, email=user.email)

        # SECURITY FIX (Audit 6): Update password history before changing password
        new_history = update_password_history(user.password_hash, password_history)
        await self.user_repo.update_password_with_history(user_id, new_hash, new_history)

        # Revoke all existing sessions for security
        await self.user_repo.update_refresh_token(user_id, None)

        await self.audit_repo.log_security_event(
            actor_id=user_id,
            event_name="password_changed",
            details={"sessions_revoked": True, "history_updated": True},
            ip_address=ip_address
        )

    async def request_password_reset(
        self,
        email: str,
        ip_address: str | None = None
    ) -> str | None:
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
            expires_at = datetime.now(UTC) + timedelta(hours=1)

            await self.user_repo.store_password_reset_token(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at
            )

            # SECURITY FIX (Audit 3): Hash email in audit logs
            import hashlib
            email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
            await self.audit_repo.log_security_event(
                actor_id=user.id,
                event_name="password_reset_requested",
                details={"email_hash": email_hash},
                ip_address=ip_address
            )

            return plain_token

        # Log attempt for non-existent email (but don't reveal to caller)
        # SECURITY FIX (Audit 3): Hash email in audit logs
        import hashlib
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
        await self.audit_repo.log_security_event(
            actor_id="unknown",
            event_name="password_reset_requested_unknown_email",
            details={"email_hash": email_hash},
            ip_address=ip_address
        )

        return None

    async def reset_password(
        self,
        user_id: str,
        new_password: str,
        reset_token: str,
        ip_address: str | None = None
    ) -> None:
        """
        Reset password using a valid reset token.

        The token is validated against the stored hash and checked for expiry.
        After successful reset, the token is invalidated (one-time use).

        SECURITY FIX (Audit 6): Added password history check to prevent
        reusing recently used passwords.

        Args:
            user_id: User ID
            new_password: New password to set
            reset_token: Plain text reset token
            ip_address: Client IP for audit logging

        Raises:
            AuthenticationError: If user not found or token invalid
            PasswordValidationError: If new password was recently used
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

        # SECURITY FIX (Audit 6): Check password history to prevent reuse
        password_history = getattr(user, 'password_history', []) or []
        all_history = [user.password_hash] + password_history
        check_password_history(new_password, all_history)

        # Hash and update password (with context-aware validation)
        # SECURITY FIX (Audit 3): Pass username/email for context-aware password validation
        new_hash = hash_password(new_password, username=user.username, email=user.email)

        # SECURITY FIX (Audit 6): Update password history
        new_history = update_password_history(user.password_hash, password_history)
        await self.user_repo.update_password_with_history(user_id, new_hash, new_history)

        # Clear the reset token (one-time use)
        await self.user_repo.clear_password_reset_token(user_id)

        # Revoke all sessions
        await self.user_repo.update_refresh_token(user_id, None)

        # Clear any lockout
        await self.user_repo.clear_lockout(user_id)

        await self.audit_repo.log_security_event(
            actor_id=user_id,
            event_name="password_reset",
            details={"method": "reset_token", "history_updated": True},
            ip_address=ip_address
        )

    # =========================================================================
    # Account Management
    # =========================================================================

    async def verify_email(
        self,
        user_id: str,
        verification_token: str,
        ip_address: str | None = None
    ) -> None:
        """
        Verify user's email address using a verification token.

        SECURITY FIX (Audit 4 - H2): Now properly validates the verification token
        against a stored hash before marking the email as verified.

        Args:
            user_id: User ID
            verification_token: Plain text verification token
            ip_address: Client IP for audit logging

        Raises:
            AuthenticationError: If user not found or token invalid
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise AuthenticationError("User not found")

        # SECURITY FIX: Hash the provided token and validate against stored hash
        token_hash = hashlib.sha256(verification_token.encode()).hexdigest()
        is_valid = await self.user_repo.validate_email_verification_token(
            user_id=user_id,
            token_hash=token_hash
        )

        if not is_valid:
            await self.audit_repo.log_security_event(
                actor_id=user_id,
                event_name="email_verification_failed",
                details={"reason": "invalid_or_expired_token"},
                ip_address=ip_address
            )
            raise AuthenticationError("Invalid or expired verification token")

        # Mark email as verified
        await self.user_repo.set_verified(user_id)

        # Clear the verification token (one-time use)
        await self.user_repo.clear_email_verification_token(user_id)

        await self.audit_repo.log_user_action(
            actor_id=user_id,
            target_user_id=user_id,
            action="email_verified",
            ip_address=ip_address
        )

    async def request_email_verification(
        self,
        user_id: str,
        ip_address: str | None = None
    ) -> str | None:
        """
        Generate and store an email verification token.

        SECURITY FIX (Audit 4 - H2): Added this method to properly generate
        verification tokens with hashed storage.

        Args:
            user_id: User ID
            ip_address: Client IP for audit logging

        Returns:
            Plain text verification token to send to user via email
        """
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise AuthenticationError("User not found")

        if user.is_verified:
            return None  # Already verified

        # Generate secure token
        plain_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plain_token.encode()).hexdigest()

        # Token expires in 24 hours
        expires_at = datetime.now(UTC) + timedelta(hours=24)

        await self.user_repo.store_email_verification_token(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        await self.audit_repo.log_user_action(
            actor_id=user_id,
            target_user_id=user_id,
            action="email_verification_requested",
            ip_address=ip_address
        )

        return plain_token

    async def deactivate_account(
        self,
        user_id: str,
        deactivated_by: str,
        reason: str,
        ip_address: str | None = None
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
        ip_address: str | None = None
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
        ip_address: str | None = None
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

    async def get_current_user(self, user_id: str) -> User | None:
        """Get current user by ID."""
        return await self.user_repo.get_by_id(user_id)

    async def get_user_auth_context(self, user_id: str) -> AuthorizationContext | None:
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
