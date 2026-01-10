"""
User Repository

Repository for User CRUD operations, authentication,
and trust flame management.
"""

from datetime import datetime
from typing import Any

import structlog

from forge.models.base import TrustLevel
from forge.models.user import (
    AuthProvider,
    TrustFlameAdjustment,
    User,
    UserCreate,
    UserInDB,
    UserPublic,
    UserRole,
    UserUpdate,
)
from forge.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)

# SECURITY FIX (Audit 3): Define explicit field lists to prevent password_hash leakage
# Fields safe for User model (no password_hash, refresh_token, etc.)
USER_SAFE_FIELDS = """
    .id, .username, .email, .display_name, .bio, .avatar_url,
    .role, .trust_flame, .is_active, .is_verified, .auth_provider,
    .last_login, .metadata, .created_at, .updated_at
""".strip()

# Fields for UserPublic model (public profile)
USER_PUBLIC_FIELDS = ".id, .username, .display_name, .bio, .avatar_url, .trust_flame, .created_at"


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """
    Repository for User entities.

    Provides CRUD operations, authentication helpers,
    and trust flame management.
    """

    @property
    def node_label(self) -> str:
        return "User"

    @property
    def model_class(self) -> type[User]:
        return User

    async def create(
        self,
        data: UserCreate,
        password_hash: str,
        role: UserRole = UserRole.USER,
    ) -> UserInDB:
        """
        Create a new user.

        Args:
            data: User creation data
            password_hash: Hashed password
            role: User role

        Returns:
            Created user with DB fields
        """
        user_id = self._generate_id()
        now = self._now()

        query = """
        CREATE (u:User {
            id: $id,
            username: $username,
            email: $email,
            display_name: $display_name,
            bio: $bio,
            avatar_url: $avatar_url,
            password_hash: $password_hash,
            role: $role,
            trust_flame: $trust_flame,
            is_active: true,
            is_verified: false,
            auth_provider: $auth_provider,
            last_login: null,
            refresh_token: null,
            failed_login_attempts: 0,
            lockout_until: null,
            created_at: $now,
            updated_at: $now
        })
        RETURN u {.*} AS user
        """

        params = {
            "id": user_id,
            "username": data.username,
            "email": data.email,
            "display_name": data.display_name,
            "bio": data.bio,
            "avatar_url": data.avatar_url,
            "password_hash": password_hash,
            "role": role.value,
            "trust_flame": TrustLevel.STANDARD.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "now": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("user"):
            self.logger.info(
                "Created user",
                user_id=user_id,
                username=data.username,
            )
            return UserInDB.model_validate(result["user"])

        raise RuntimeError("Failed to create user")

    async def get_by_id(self, entity_id: str) -> User | None:
        """
        Get user by ID with safe field list.

        SECURITY FIX (Audit 3): Override base implementation to use explicit
        field list, excluding password_hash and other sensitive fields.

        Args:
            entity_id: User ID

        Returns:
            User model or None if not found
        """
        query = f"""
        MATCH (u:User {{id: $id}})
        RETURN u {{{USER_SAFE_FIELDS}}} AS user
        """

        result = await self.client.execute_single(query, {"id": entity_id})

        if result and result.get("user"):
            return self._to_model(result["user"])
        return None

    async def update(self, entity_id: str, data: UserUpdate) -> User | None:
        """
        Update user profile.

        Args:
            entity_id: User ID
            data: Update data

        Returns:
            Updated user or None
        """
        set_clauses = ["u.updated_at = $now"]
        params: dict[str, Any] = {
            "id": entity_id,
            "now": self._now().isoformat(),
        }

        if data.display_name is not None:
            set_clauses.append("u.display_name = $display_name")
            params["display_name"] = data.display_name

        if data.bio is not None:
            set_clauses.append("u.bio = $bio")
            params["bio"] = data.bio

        if data.avatar_url is not None:
            set_clauses.append("u.avatar_url = $avatar_url")
            params["avatar_url"] = data.avatar_url

        if data.email is not None:
            set_clauses.append("u.email = $email")
            params["email"] = data.email

        # SECURITY FIX (Audit 3): Use explicit field list to exclude password_hash
        query = f"""
        MATCH (u:User {{id: $id}})
        SET {', '.join(set_clauses)}
        RETURN u {{{USER_SAFE_FIELDS}}} AS user
        """

        result = await self.client.execute_single(query, params)

        if result and result.get("user"):
            return self._to_model(result["user"])
        return None

    async def get_by_username(self, username: str) -> UserInDB | None:
        """
        Get user by username (case-insensitive).

        SECURITY NOTE (Audit 4): This is an INTERNAL method for authentication.
        Returns UserInDB which includes password_hash - needed for password verification.
        DO NOT expose UserInDB directly to API responses - use User model instead.
        """
        query = """
        MATCH (u:User)
        WHERE toLower(u.username) = toLower($username)
        RETURN u {.*} AS user
        """

        result = await self.client.execute_single(query, {"username": username})

        if result and result.get("user"):
            return UserInDB.model_validate(result["user"])
        return None

    async def get_by_email(self, email: str) -> UserInDB | None:
        """
        Get user by email (case-insensitive).

        SECURITY NOTE (Audit 4): This is an INTERNAL method for authentication.
        Returns UserInDB which includes password_hash - needed for password verification.
        DO NOT expose UserInDB directly to API responses - use User model instead.
        """
        query = """
        MATCH (u:User)
        WHERE toLower(u.email) = toLower($email)
        RETURN u {.*} AS user
        """

        result = await self.client.execute_single(query, {"email": email})

        if result and result.get("user"):
            return UserInDB.model_validate(result["user"])
        return None

    async def get_by_username_or_email(self, identifier: str) -> UserInDB | None:
        """
        Get user by username or email.

        SECURITY NOTE (Audit 4): This is an INTERNAL method for authentication.
        Returns UserInDB which includes password_hash - needed for password verification.
        DO NOT expose UserInDB directly to API responses - use User model instead.
        """
        query = """
        MATCH (u:User)
        WHERE toLower(u.username) = toLower($identifier)
           OR toLower(u.email) = toLower($identifier)
        RETURN u {.*} AS user
        """

        result = await self.client.execute_single(query, {"identifier": identifier})

        if result and result.get("user"):
            return UserInDB.model_validate(result["user"])
        return None

    def to_safe_user(self, user_in_db: UserInDB) -> User:
        """
        SECURITY FIX (Audit 4): Convert UserInDB to safe User model.

        Strips password_hash and other sensitive fields before exposing to API.
        Always use this when returning user data to external callers.
        """
        return User(
            id=user_in_db.id,
            username=user_in_db.username,
            email=user_in_db.email,
            display_name=user_in_db.display_name,
            bio=user_in_db.bio,
            avatar_url=user_in_db.avatar_url,
            role=user_in_db.role,
            trust_flame=user_in_db.trust_flame,
            is_active=user_in_db.is_active,
            is_verified=user_in_db.is_verified,
            auth_provider=user_in_db.auth_provider,
            created_at=user_in_db.created_at,
            updated_at=user_in_db.updated_at,
        )

    async def update_password(
        self,
        user_id: str,
        password_hash: str,
    ) -> bool:
        """Update user's password hash."""
        query = """
        MATCH (u:User {id: $id})
        SET u.password_hash = $password_hash, u.updated_at = $now
        RETURN u.id AS id
        """

        result = await self.client.execute_single(
            query,
            {
                "id": user_id,
                "password_hash": password_hash,
                "now": self._now().isoformat(),
            },
        )

        return result is not None and result.get("id") == user_id

    async def update_refresh_token(
        self,
        user_id: str,
        refresh_token: str | None,
    ) -> bool:
        """Update user's refresh token."""
        query = """
        MATCH (u:User {id: $id})
        SET u.refresh_token = $refresh_token
        RETURN u.id AS id
        """

        result = await self.client.execute_single(
            query,
            {"id": user_id, "refresh_token": refresh_token},
        )

        return result is not None and result.get("id") == user_id

    async def record_login(self, user_id: str) -> None:
        """Record successful login."""
        query = """
        MATCH (u:User {id: $id})
        SET u.last_login = $now, u.failed_login_attempts = 0
        """

        await self.client.execute(
            query,
            {"id": user_id, "now": self._now().isoformat()},
        )

    async def record_failed_login(self, user_id: str) -> int:
        """
        Record failed login attempt.

        Returns:
            New failed attempt count
        """
        query = """
        MATCH (u:User {id: $id})
        SET u.failed_login_attempts = u.failed_login_attempts + 1
        RETURN u.failed_login_attempts AS attempts
        """

        result = await self.client.execute_single(query, {"id": user_id})
        return result.get("attempts", 0) if result else 0

    async def set_lockout(self, user_id: str, until: datetime) -> None:
        """Lock user account until specified time."""
        query = """
        MATCH (u:User {id: $id})
        SET u.lockout_until = $until
        """

        await self.client.execute(
            query,
            {"id": user_id, "until": until.isoformat()},
        )

    async def clear_lockout(self, user_id: str) -> None:
        """Clear user account lockout."""
        query = """
        MATCH (u:User {id: $id})
        SET u.lockout_until = null, u.failed_login_attempts = 0
        """

        await self.client.execute(query, {"id": user_id})

    async def set_verified(self, user_id: str, verified: bool = True) -> None:
        """Set email verification status."""
        query = """
        MATCH (u:User {id: $id})
        SET u.is_verified = $verified
        """

        await self.client.execute(
            query,
            {"id": user_id, "verified": verified},
        )

    async def adjust_trust_flame(
        self,
        user_id: str,
        adjustment: int,
        reason: str,
        adjusted_by: str | None = None,
    ) -> TrustFlameAdjustment | None:
        """
        Adjust user's trust flame score.

        Args:
            user_id: User ID
            adjustment: Amount to adjust (+/-)
            reason: Reason for adjustment
            adjusted_by: ID of user/system making adjustment

        Returns:
            Adjustment record or None
        """
        query = """
        MATCH (u:User {id: $id})
        WITH u, u.trust_flame AS old_value
        SET u.trust_flame = CASE
            WHEN u.trust_flame + $adjustment < 0 THEN 0
            WHEN u.trust_flame + $adjustment > 100 THEN 100
            ELSE u.trust_flame + $adjustment
        END
        RETURN old_value, u.trust_flame AS new_value, u.id AS user_id
        """

        result = await self.client.execute_single(
            query,
            {"id": user_id, "adjustment": adjustment},
        )

        if not result:
            return None

        adjustment_record = TrustFlameAdjustment(
            user_id=user_id,
            old_value=result["old_value"],
            new_value=result["new_value"],
            reason=reason,
            adjusted_by=adjusted_by,
        )

        self.logger.info(
            "Trust flame adjusted",
            user_id=user_id,
            old_value=adjustment_record.old_value,
            new_value=adjustment_record.new_value,
            reason=reason,
        )

        return adjustment_record

    async def get_by_trust_level(
        self,
        min_trust: int,
        limit: int = 100,
    ) -> list[UserPublic]:
        """Get users with minimum trust level."""
        query = """
        MATCH (u:User)
        WHERE u.trust_flame >= $min_trust AND u.is_active = true
        RETURN u {
            .id, .username, .display_name, .bio, .avatar_url,
            .trust_flame, .created_at
        } AS user
        ORDER BY u.trust_flame DESC
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"min_trust": min_trust, "limit": limit},
        )

        return [
            UserPublic.model_validate(r["user"])
            for r in results
            if r.get("user")
        ]

    async def deactivate(self, user_id: str) -> bool:
        """Deactivate a user account."""
        result = await self.update_field(user_id, "is_active", False)
        return result is not None

    async def activate(self, user_id: str) -> bool:
        """Activate a user account."""
        result = await self.update_field(user_id, "is_active", True)
        return result is not None

    async def username_exists(self, username: str) -> bool:
        """Check if username is taken."""
        query = """
        MATCH (u:User)
        WHERE toLower(u.username) = toLower($username)
        RETURN count(u) > 0 AS exists
        """

        result = await self.client.execute_single(query, {"username": username})
        return result.get("exists", False) if result else False

    async def email_exists(self, email: str) -> bool:
        """Check if email is taken."""
        query = """
        MATCH (u:User)
        WHERE toLower(u.email) = toLower($email)
        RETURN count(u) > 0 AS exists
        """

        result = await self.client.execute_single(query, {"email": email})
        return result.get("exists", False) if result else False

    async def get_refresh_token(self, user_id: str) -> str | None:
        """Get the stored refresh token for a user."""
        query = """
        MATCH (u:User {id: $id})
        RETURN u.refresh_token AS refresh_token
        """

        result = await self.client.execute_single(query, {"id": user_id})
        return result.get("refresh_token") if result else None

    async def validate_refresh_token(self, user_id: str, token: str) -> bool:
        """
        Validate that the provided refresh token matches the stored one.

        This prevents use of old/revoked refresh tokens.

        SECURITY FIX (Audit 4 - M1): Uses constant-time comparison to prevent
        timing attacks that could leak information about valid token prefixes.
        """
        import secrets

        stored_token = await self.get_refresh_token(user_id)
        if stored_token is None:
            return False

        # SECURITY FIX: Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(stored_token, token)

    # =========================================================================
    # Password Reset Token Management
    # =========================================================================

    async def store_password_reset_token(
        self,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> bool:
        """
        Store a hashed password reset token for a user.

        Args:
            user_id: User ID
            token_hash: SHA-256 hash of the reset token
            expires_at: When the token expires

        Returns:
            True if stored successfully
        """
        query = """
        MATCH (u:User {id: $id})
        SET u.password_reset_token = $token_hash,
            u.password_reset_expires = $expires_at,
            u.updated_at = $now
        RETURN u.id AS id
        """

        result = await self.client.execute_single(
            query,
            {
                "id": user_id,
                "token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
                "now": self._now().isoformat(),
            },
        )

        return result is not None and result.get("id") == user_id

    async def validate_password_reset_token(
        self,
        user_id: str,
        token_hash: str,
    ) -> bool:
        """
        Validate a password reset token.

        Args:
            user_id: User ID
            token_hash: SHA-256 hash of the provided token

        Returns:
            True if token is valid and not expired
        """
        query = """
        MATCH (u:User {id: $id})
        WHERE u.password_reset_token = $token_hash
          AND u.password_reset_expires > $now
        RETURN u.id AS id
        """

        result = await self.client.execute_single(
            query,
            {
                "id": user_id,
                "token_hash": token_hash,
                "now": self._now().isoformat(),
            },
        )

        return result is not None and result.get("id") == user_id

    async def clear_password_reset_token(self, user_id: str) -> None:
        """Clear password reset token after use or expiry."""
        query = """
        MATCH (u:User {id: $id})
        SET u.password_reset_token = null,
            u.password_reset_expires = null
        """

        await self.client.execute(query, {"id": user_id})
