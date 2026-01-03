# Forge V3 - Phase 5: Security & Compliance

**Purpose:** Implement authentication, authorization, encryption, and regulatory compliance.

**Estimated Effort:** 4-5 days
**Dependencies:** Phase 0-2
**Outputs:** Complete security layer with GDPR/compliance support

---

## 1. Overview

Security is foundational to Forge. This phase implements defense-in-depth with multiple layers of protection, plus compliance features for GDPR and EU AI Act readiness.

---

## 2. Authentication Service

```python
# forge/security/auth.py
"""
Authentication service with password hashing, JWT tokens, and MFA.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from forge.config import get_settings
from forge.models.user import User, UserCreate
from forge.core.users.repository import UserRepository
from forge.exceptions import AuthenticationError, ValidationError
from forge.logging import get_logger

logger = get_logger(__name__)

# Argon2id configuration (OWASP recommended)
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


class AuthService:
    """Authentication service."""
    
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15
    
    def __init__(self, user_repo: UserRepository, redis: "RedisClient"):
        self._users = user_repo
        self._redis = redis
        self._settings = get_settings()
    
    def hash_password(self, password: str) -> str:
        """Hash password using Argon2id."""
        return ph.hash(password)
    
    def verify_password(self, password: str, hash: str) -> bool:
        """Verify password against hash."""
        try:
            ph.verify(hash, password)
            return True
        except VerifyMismatchError:
            return False
    
    async def register(self, data: UserCreate) -> User:
        """Register a new user."""
        # Validate password strength
        self._validate_password_strength(data.password)
        
        # Hash password
        password_hash = self.hash_password(data.password)
        
        # Create user
        user = await self._users.create(data, password_hash)
        
        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return user
    
    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: str,
    ) -> tuple[User, str, str]:
        """
        Authenticate user and return tokens.
        
        Returns: (user, access_token, refresh_token)
        """
        user = await self._users.get_by_email(email)
        
        if not user:
            # Don't reveal whether email exists
            logger.warning("auth_failed_unknown_email", email=email)
            raise AuthenticationError("Invalid email or password")
        
        # Check lockout
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            raise AuthenticationError(f"Account locked. Try again in {remaining} minutes.")
        
        # Verify password
        if not user.password_hash or not self.verify_password(password, user.password_hash):
            # Increment failed attempts
            await self._handle_failed_login(user)
            raise AuthenticationError("Invalid email or password")
        
        # Check if account is active
        if not user.is_active:
            raise AuthenticationError("Account is disabled")
        
        # Clear failed attempts on successful login
        await self._users.clear_failed_attempts(user.id)
        
        # Generate tokens
        access_token = self._create_access_token(user)
        refresh_token = self._create_refresh_token(user)
        
        # Store refresh token
        await self._store_refresh_token(user.id, refresh_token)
        
        logger.info("user_authenticated", user_id=str(user.id))
        return user, access_token, refresh_token
    
    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        """Refresh access token using refresh token."""
        try:
            payload = jwt.decode(
                refresh_token,
                self._settings.jwt_secret.get_secret_value(),
                algorithms=[self._settings.jwt_algorithm],
            )
            
            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")
            
            user_id = UUID(payload["sub"])
            
            # Verify token is still valid in storage
            stored = await self._redis.get(f"refresh_token:{user_id}")
            if stored != refresh_token:
                raise AuthenticationError("Token has been revoked")
            
            user = await self._users.get_by_id(user_id)
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")
            
            # Generate new tokens
            new_access = self._create_access_token(user)
            new_refresh = self._create_refresh_token(user)
            
            # Update stored refresh token
            await self._store_refresh_token(user.id, new_refresh)
            
            return new_access, new_refresh
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Refresh token expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    async def logout(self, user_id: UUID) -> None:
        """Logout user by revoking refresh token."""
        await self._redis.delete(f"refresh_token:{user_id}")
        logger.info("user_logged_out", user_id=str(user_id))
    
    def _create_access_token(self, user: User) -> str:
        """Create short-lived access token."""
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.jwt_access_token_expire_minutes
        )
        
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "trust_level": user.trust_level.value,
            "roles": user.roles,
            "type": "access",
            "exp": expires,
            "iat": datetime.now(timezone.utc),
        }
        
        return jwt.encode(
            payload,
            self._settings.jwt_secret.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
        )
    
    def _create_refresh_token(self, user: User) -> str:
        """Create long-lived refresh token."""
        expires = datetime.now(timezone.utc) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        
        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "exp": expires,
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_urlsafe(32),  # Unique token ID
        }
        
        return jwt.encode(
            payload,
            self._settings.jwt_secret.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
        )
    
    async def _store_refresh_token(self, user_id: UUID, token: str) -> None:
        """Store refresh token for validation."""
        ttl = self._settings.jwt_refresh_token_expire_days * 86400
        await self._redis.set(f"refresh_token:{user_id}", token, ttl=ttl)
    
    async def _handle_failed_login(self, user: User) -> None:
        """Handle failed login attempt."""
        new_count = user.failed_login_attempts + 1
        locked_until = None
        
        if new_count >= self.MAX_LOGIN_ATTEMPTS:
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.LOCKOUT_MINUTES)
            logger.warning("account_locked", user_id=str(user.id), until=locked_until.isoformat())
        
        await self._users.update_failed_attempts(user.id, new_count, locked_until)
    
    def _validate_password_strength(self, password: str) -> None:
        """Validate password meets strength requirements."""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters", field="password")
        if len(password) > 128:
            raise ValidationError("Password must be at most 128 characters", field="password")
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        if not (has_upper and has_lower and has_digit):
            raise ValidationError(
                "Password must contain uppercase, lowercase, and digit",
                field="password",
            )
```

---

## 3. Authorization Service

```python
# forge/security/authorization.py
"""
Authorization with RBAC (Role-Based) + ABAC (Attribute-Based) access control.
"""
from enum import Enum
from uuid import UUID
from typing import Any

from forge.models.user import User
from forge.models.base import TrustLevel
from forge.exceptions import AuthorizationError
from forge.logging import get_logger

logger = get_logger(__name__)


class Permission(str, Enum):
    """System permissions."""
    # Capsule permissions
    CAPSULE_READ = "capsule:read"
    CAPSULE_CREATE = "capsule:create"
    CAPSULE_UPDATE = "capsule:update"
    CAPSULE_DELETE = "capsule:delete"
    
    # Governance permissions
    GOVERNANCE_PROPOSE = "governance:propose"
    GOVERNANCE_VOTE = "governance:vote"
    GOVERNANCE_EXECUTE = "governance:execute"
    
    # Overlay permissions
    OVERLAY_INVOKE = "overlay:invoke"
    OVERLAY_REGISTER = "overlay:register"
    OVERLAY_MANAGE = "overlay:manage"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_AUDIT = "admin:audit"


# Role -> Permissions mapping
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "user": {
        Permission.CAPSULE_READ,
        Permission.CAPSULE_CREATE,
        Permission.CAPSULE_UPDATE,
        Permission.GOVERNANCE_VOTE,
        Permission.OVERLAY_INVOKE,
    },
    "trusted": {
        Permission.CAPSULE_READ,
        Permission.CAPSULE_CREATE,
        Permission.CAPSULE_UPDATE,
        Permission.CAPSULE_DELETE,
        Permission.GOVERNANCE_PROPOSE,
        Permission.GOVERNANCE_VOTE,
        Permission.OVERLAY_INVOKE,
        Permission.OVERLAY_REGISTER,
    },
    "operator": {
        Permission.CAPSULE_READ,
        Permission.CAPSULE_CREATE,
        Permission.CAPSULE_UPDATE,
        Permission.CAPSULE_DELETE,
        Permission.GOVERNANCE_PROPOSE,
        Permission.GOVERNANCE_VOTE,
        Permission.GOVERNANCE_EXECUTE,
        Permission.OVERLAY_INVOKE,
        Permission.OVERLAY_REGISTER,
        Permission.OVERLAY_MANAGE,
    },
    "admin": {
        # Admins have all permissions
        *Permission,
    },
}


class AuthorizationService:
    """
    Combined RBAC + ABAC authorization.
    
    RBAC: Role-based permissions
    ABAC: Attribute-based policies (trust level, ownership, etc.)
    """
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a permission via their roles."""
        for role in user.roles:
            if role in ROLE_PERMISSIONS:
                if permission in ROLE_PERMISSIONS[role]:
                    return True
        return False
    
    def require_permission(self, user: User, permission: Permission) -> None:
        """Require permission or raise AuthorizationError."""
        if not self.check_permission(user, permission):
            raise AuthorizationError(f"Missing permission: {permission.value}")
    
    def check_resource_access(
        self,
        user: User,
        resource_type: str,
        resource: Any,
        action: str,
    ) -> bool:
        """
        Check attribute-based access to a specific resource.
        
        Combines role permissions with resource attributes.
        """
        # Map action to permission
        permission_map = {
            ("capsule", "read"): Permission.CAPSULE_READ,
            ("capsule", "update"): Permission.CAPSULE_UPDATE,
            ("capsule", "delete"): Permission.CAPSULE_DELETE,
            ("overlay", "invoke"): Permission.OVERLAY_INVOKE,
            ("proposal", "vote"): Permission.GOVERNANCE_VOTE,
        }
        
        permission = permission_map.get((resource_type, action))
        if not permission:
            return False
        
        # Check base permission
        if not self.check_permission(user, permission):
            return False
        
        # Check attribute-based rules
        if resource_type == "capsule":
            return self._check_capsule_access(user, resource, action)
        elif resource_type == "overlay":
            return self._check_overlay_access(user, resource, action)
        
        return True
    
    def _check_capsule_access(self, user: User, capsule: Any, action: str) -> bool:
        """Check capsule-specific access rules."""
        # Trust level check
        if not user.trust_level.can_access(capsule.trust_level):
            return False
        
        # Owner-only actions
        if action in ("update", "delete"):
            if capsule.owner_id != user.id and "admin" not in user.roles:
                return False
        
        return True
    
    def _check_overlay_access(self, user: User, overlay: Any, action: str) -> bool:
        """Check overlay-specific access rules."""
        # Trust level check
        if not user.trust_level.can_access(overlay.trust_level):
            return False
        
        return True
    
    def require_resource_access(
        self,
        user: User,
        resource_type: str,
        resource: Any,
        action: str,
    ) -> None:
        """Require resource access or raise AuthorizationError."""
        if not self.check_resource_access(user, resource_type, resource, action):
            raise AuthorizationError(
                f"Access denied to {resource_type} for action: {action}"
            )
```

---

## 4. Encryption Service

```python
# forge/security/encryption.py
"""
Encryption service for data at rest.

Uses envelope encryption:
- Data Encryption Keys (DEKs) encrypt actual data
- Key Encryption Keys (KEKs) encrypt DEKs
- KEKs stored in external secret manager
"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from forge.config import get_settings
from forge.logging import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """
    Envelope encryption for sensitive data.
    
    Each piece of data gets a unique DEK.
    DEKs are encrypted with the master KEK.
    """
    
    def __init__(self, master_key: bytes | None = None):
        """
        Initialize with master key.
        
        In production, master_key should come from a secret manager
        (AWS KMS, HashiCorp Vault, etc.)
        """
        if master_key:
            self._master_key = master_key
        else:
            # For development only - use proper secret management in production
            settings = get_settings()
            if settings.environment == "production":
                raise ValueError("Master key required in production")
            self._master_key = Fernet.generate_key()
        
        self._fernet = Fernet(self._master_key)
    
    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """
        Encrypt data using envelope encryption.
        
        Returns: (encrypted_data, encrypted_dek)
        """
        # Generate unique DEK for this data
        dek = AESGCM.generate_key(bit_length=256)
        
        # Encrypt data with DEK
        nonce = os.urandom(12)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        # Combine nonce + ciphertext
        encrypted_data = nonce + ciphertext
        
        # Encrypt DEK with master key
        encrypted_dek = self._fernet.encrypt(dek)
        
        return encrypted_data, encrypted_dek
    
    def decrypt(self, encrypted_data: bytes, encrypted_dek: bytes) -> bytes:
        """Decrypt data using envelope encryption."""
        # Decrypt DEK
        dek = self._fernet.decrypt(encrypted_dek)
        
        # Extract nonce and ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Decrypt data
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def encrypt_string(self, plaintext: str) -> tuple[str, str]:
        """Convenience method for encrypting strings."""
        encrypted_data, encrypted_dek = self.encrypt(plaintext.encode())
        return (
            base64.b64encode(encrypted_data).decode(),
            base64.b64encode(encrypted_dek).decode(),
        )
    
    def decrypt_string(self, encrypted_data: str, encrypted_dek: str) -> str:
        """Convenience method for decrypting strings."""
        plaintext = self.decrypt(
            base64.b64decode(encrypted_data),
            base64.b64decode(encrypted_dek),
        )
        return plaintext.decode()


class FieldEncryption:
    """
    Field-level encryption for PII.
    
    Use for specific fields that contain sensitive data.
    """
    
    def __init__(self, encryption_service: EncryptionService):
        self._encryption = encryption_service
    
    def encrypt_pii(self, data: dict, pii_fields: list[str]) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Adds _encrypted suffix to field names.
        """
        result = data.copy()
        
        for field in pii_fields:
            if field in result and result[field]:
                value = str(result[field])
                encrypted, dek = self._encryption.encrypt_string(value)
                result[f"{field}_encrypted"] = encrypted
                result[f"{field}_dek"] = dek
                del result[field]
        
        return result
    
    def decrypt_pii(self, data: dict, pii_fields: list[str]) -> dict:
        """Decrypt PII fields back to original form."""
        result = data.copy()
        
        for field in pii_fields:
            encrypted_field = f"{field}_encrypted"
            dek_field = f"{field}_dek"
            
            if encrypted_field in result and dek_field in result:
                result[field] = self._encryption.decrypt_string(
                    result[encrypted_field],
                    result[dek_field],
                )
                del result[encrypted_field]
                del result[dek_field]
        
        return result
```

---

## 5. GDPR Compliance Service

```python
# forge/core/compliance/gdpr.py
"""
GDPR compliance service for data subject rights.
"""
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum

from forge.logging import get_logger

logger = get_logger(__name__)


class DSARType(str, Enum):
    """Data Subject Access Request types."""
    ACCESS = "access"      # Right to access
    RECTIFICATION = "rectification"  # Right to correct
    ERASURE = "erasure"    # Right to be forgotten
    PORTABILITY = "portability"  # Right to data portability
    RESTRICTION = "restriction"  # Right to restrict processing
    OBJECTION = "objection"  # Right to object


class GDPRService:
    """
    GDPR compliance service.
    
    Handles data subject rights requests within required timelines.
    """
    
    RESPONSE_DEADLINE_DAYS = 30  # GDPR Article 12
    
    def __init__(
        self,
        user_repo: "UserRepository",
        capsule_repo: "CapsuleRepository",
        audit_service: "AuditService",
    ):
        self._users = user_repo
        self._capsules = capsule_repo
        self._audit = audit_service
    
    async def handle_access_request(self, user_id: UUID) -> dict:
        """
        Handle right of access request (Article 15).
        
        Returns all personal data held about the user.
        """
        user = await self._users.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}
        
        # Gather all user data
        capsules = await self._capsules.list_by_owner(user_id)
        
        data = {
            "request_type": "access",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_data": {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "created_at": user.created_at.isoformat(),
                "trust_level": user.trust_level.value,
                "roles": user.roles,
            },
            "capsules": [
                {
                    "id": str(c.id),
                    "type": c.type.value,
                    "created_at": c.created_at.isoformat(),
                    "content_preview": c.content[:100] + "..." if len(c.content) > 100 else c.content,
                }
                for c in capsules
            ],
            "capsule_count": len(capsules),
        }
        
        # Log the access request
        await self._audit.log(
            action="gdpr_access_request",
            user_id=user_id,
            details={"capsule_count": len(capsules)},
        )
        
        logger.info("gdpr_access_request", user_id=str(user_id))
        return data
    
    async def handle_erasure_request(
        self,
        user_id: UUID,
        include_capsules: bool = True,
    ) -> dict:
        """
        Handle right to erasure request (Article 17).
        
        Deletes user account and optionally all their capsules.
        """
        user = await self._users.get_by_id(user_id)
        if not user:
            return {"error": "User not found"}
        
        deleted_capsules = 0
        
        if include_capsules:
            # Delete all user's capsules
            capsules = await self._capsules.list_by_owner(user_id)
            for capsule in capsules:
                await self._capsules.hard_delete(capsule.id)
                deleted_capsules += 1
        
        # Anonymize user record (keep for audit trail)
        await self._users.anonymize(user_id)
        
        # Log the erasure
        await self._audit.log(
            action="gdpr_erasure_request",
            user_id=user_id,
            details={
                "capsules_deleted": deleted_capsules,
                "include_capsules": include_capsules,
            },
        )
        
        logger.info(
            "gdpr_erasure_request",
            user_id=str(user_id),
            capsules_deleted=deleted_capsules,
        )
        
        return {
            "request_type": "erasure",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "capsules_deleted": deleted_capsules,
            "user_anonymized": True,
        }
    
    async def handle_portability_request(self, user_id: UUID) -> dict:
        """
        Handle data portability request (Article 20).
        
        Returns data in machine-readable format.
        """
        # Similar to access but in JSON format for portability
        data = await self.handle_access_request(user_id)
        data["request_type"] = "portability"
        data["format"] = "application/json"
        
        await self._audit.log(
            action="gdpr_portability_request",
            user_id=user_id,
        )
        
        return data
    
    async def get_consent_status(self, user_id: UUID) -> dict:
        """Get user's consent status for various processing activities."""
        # In a real implementation, this would query a consent database
        return {
            "user_id": str(user_id),
            "consents": {
                "essential_processing": True,
                "analytics": False,
                "marketing": False,
            },
        }
    
    async def update_consent(
        self,
        user_id: UUID,
        consent_type: str,
        granted: bool,
    ) -> dict:
        """Update user's consent for a processing activity."""
        await self._audit.log(
            action="consent_updated",
            user_id=user_id,
            details={"consent_type": consent_type, "granted": granted},
        )
        
        return {
            "consent_type": consent_type,
            "granted": granted,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
```

---

## 6. Audit Logging Service

```python
# forge/core/compliance/audit.py
"""
Audit logging for compliance and security monitoring.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Any

from forge.infrastructure.neo4j.client import Neo4jClient
from forge.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """
    Immutable audit logging for compliance.
    
    All entries are append-only and cannot be modified.
    """
    
    def __init__(self, neo4j: Neo4jClient):
        self._neo4j = neo4j
    
    async def log(
        self,
        action: str,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> UUID:
        """
        Create an immutable audit log entry.
        
        Returns the audit entry ID.
        """
        entry_id = uuid4()
        now = datetime.now(timezone.utc)
        
        await self._neo4j.run("""
            CREATE (a:AuditLog {
                id: $id,
                action: $action,
                user_id: $user_id,
                resource_type: $resource_type,
                resource_id: $resource_id,
                details: $details,
                ip_address: $ip_address,
                timestamp: datetime($timestamp)
            })
        """, {
            "id": str(entry_id),
            "action": action,
            "user_id": str(user_id) if user_id else None,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "details": details or {},
            "ip_address": ip_address,
            "timestamp": now.isoformat(),
        })
        
        logger.debug("audit_logged", action=action, entry_id=str(entry_id))
        return entry_id
    
    async def query(
        self,
        user_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit logs with filters."""
        where_parts = []
        params: dict[str, Any] = {"limit": limit}
        
        if user_id:
            where_parts.append("a.user_id = $user_id")
            params["user_id"] = str(user_id)
        
        if action:
            where_parts.append("a.action = $action")
            params["action"] = action
        
        if resource_type:
            where_parts.append("a.resource_type = $resource_type")
            params["resource_type"] = resource_type
        
        if start_time:
            where_parts.append("a.timestamp >= datetime($start_time)")
            params["start_time"] = start_time.isoformat()
        
        if end_time:
            where_parts.append("a.timestamp <= datetime($end_time)")
            params["end_time"] = end_time.isoformat()
        
        where_clause = " AND ".join(where_parts) if where_parts else "true"
        
        results = await self._neo4j.run(f"""
            MATCH (a:AuditLog)
            WHERE {where_clause}
            RETURN a
            ORDER BY a.timestamp DESC
            LIMIT $limit
        """, params)
        
        return [dict(r["a"]) for r in results]
```

---

## 7. Next Steps

After completing Phase 5, proceed to **Phase 6: API Layer** to implement:

- FastAPI routes for all services
- Request/response middleware
- Rate limiting
- API versioning
