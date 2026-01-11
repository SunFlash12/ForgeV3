"""
Forge Compliance Framework - Security Controls Service

Implements security controls per:
- SOC 2 Trust Services Criteria (CC6, CC7, CC8)
- ISO 27001 Annex A
- NIST 800-53 (AC, AU, IA, SC families)
- PCI-DSS 4.0.1 Requirements 7-8
- HIPAA Security Rule

Controls include:
- Access Control (RBAC/ABAC)
- Multi-Factor Authentication
- Session Management
- Privileged Access Management
- Security Event Monitoring
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

import structlog

from forge.compliance.core.config import get_compliance_config
from forge.compliance.core.enums import (
    AccessControlModel,
    AuditEventCategory,
    DataClassification,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ACCESS CONTROL
# ═══════════════════════════════════════════════════════════════════════════


class Permission(str, Enum):
    """System permissions."""
    # Data permissions
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXPORT = "export"
    
    # Admin permissions
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    VIEW_AUDIT = "view_audit"
    
    # Compliance permissions
    PROCESS_DSAR = "process_dsar"
    MANAGE_CONSENT = "manage_consent"
    BREACH_RESPONSE = "breach_response"
    COMPLIANCE_ADMIN = "compliance_admin"
    
    # AI permissions
    AI_REVIEW = "ai_review"
    AI_OVERRIDE = "ai_override"
    AI_ADMIN = "ai_admin"


class ResourceType(str, Enum):
    """Resource types for access control."""
    CAPSULE = "capsule"
    USER = "user"
    OVERLAY = "overlay"
    PROPOSAL = "proposal"
    AUDIT_LOG = "audit_log"
    CONSENT = "consent"
    DSAR = "dsar"
    BREACH = "breach"
    AI_SYSTEM = "ai_system"
    AI_DECISION = "ai_decision"
    SYSTEM_CONFIG = "system_config"


@dataclass
class Role:
    """Role definition for RBAC."""
    role_id: str
    name: str
    description: str
    permissions: set[Permission]
    resource_types: set[ResourceType]
    data_classifications: set[DataClassification]
    is_privileged: bool = False
    max_session_duration: timedelta = field(default_factory=lambda: timedelta(hours=8))
    requires_mfa: bool = True
    
    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions
    
    def can_access_resource(self, resource_type: ResourceType) -> bool:
        return resource_type in self.resource_types
    
    def can_access_classification(self, classification: DataClassification) -> bool:
        return classification in self.data_classifications


@dataclass
class AttributePolicy:
    """Attribute-based access control policy."""
    policy_id: str
    name: str
    description: str
    
    # Conditions
    subject_attributes: dict[str, Any]  # e.g., {"department": "engineering"}
    resource_attributes: dict[str, Any]  # e.g., {"classification": "internal"}
    environment_attributes: dict[str, Any]  # e.g., {"time_of_day": "business_hours"}
    
    # Effect
    effect: str  # "allow" or "deny"
    permissions: set[Permission]
    
    def evaluate(
        self,
        subject: dict[str, Any],
        resource: dict[str, Any],
        environment: dict[str, Any],
    ) -> bool:
        """Evaluate policy against request context."""
        # Check subject attributes
        for attr, value in self.subject_attributes.items():
            if subject.get(attr) != value:
                return False
        
        # Check resource attributes
        for attr, value in self.resource_attributes.items():
            if resource.get(attr) != value:
                return False
        
        # Check environment attributes
        for attr, value in self.environment_attributes.items():
            if attr == "time_of_day":
                # Special handling for time-based policies
                current_hour = datetime.now(UTC).hour
                if value == "business_hours" and not (9 <= current_hour <= 17):
                    return False
            elif environment.get(attr) != value:
                return False
        
        return True


@dataclass
class AccessDecision:
    """Result of access control evaluation."""
    allowed: bool
    reason: str
    policy_id: str | None = None
    role_id: str | None = None
    requires_mfa: bool = False
    requires_justification: bool = False
    audit_required: bool = True


class AccessControlService:
    """
    Comprehensive access control service.
    
    Supports both RBAC and ABAC models per SOC 2 CC6.1, ISO 27001 A.9.
    """
    
    def __init__(self):
        self.config = get_compliance_config()
        
        # RBAC
        self._roles: dict[str, Role] = {}
        self._user_roles: dict[str, set[str]] = {}  # user_id -> role_ids
        
        # ABAC
        self._policies: dict[str, AttributePolicy] = {}
        
        # Session tracking
        self._active_sessions: dict[str, "Session"] = {}
        
        # Initialize default roles
        self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> None:
        """Create default role hierarchy."""
        # Basic user
        self._roles["user"] = Role(
            role_id="user",
            name="User",
            description="Standard user with basic access",
            permissions={Permission.READ},
            resource_types={ResourceType.CAPSULE, ResourceType.PROPOSAL},
            data_classifications={DataClassification.PUBLIC, DataClassification.INTERNAL},
            is_privileged=False,
        )
        
        # Data steward
        self._roles["data_steward"] = Role(
            role_id="data_steward",
            name="Data Steward",
            description="Manages data quality and governance",
            permissions={
                Permission.READ, Permission.WRITE,
                Permission.PROCESS_DSAR, Permission.MANAGE_CONSENT,
            },
            resource_types={
                ResourceType.CAPSULE, ResourceType.CONSENT,
                ResourceType.DSAR, ResourceType.USER,
            },
            data_classifications={
                DataClassification.PUBLIC, DataClassification.INTERNAL,
                DataClassification.CONFIDENTIAL, DataClassification.PERSONAL_DATA,
            },
            is_privileged=False,
        )
        
        # Compliance officer
        self._roles["compliance_officer"] = Role(
            role_id="compliance_officer",
            name="Compliance Officer",
            description="Full compliance management access",
            permissions={
                Permission.READ, Permission.WRITE, Permission.EXPORT,
                Permission.PROCESS_DSAR, Permission.MANAGE_CONSENT,
                Permission.BREACH_RESPONSE, Permission.COMPLIANCE_ADMIN,
                Permission.VIEW_AUDIT,
            },
            resource_types=set(ResourceType),
            data_classifications=set(DataClassification),
            is_privileged=True,
            requires_mfa=True,
        )
        
        # AI reviewer
        self._roles["ai_reviewer"] = Role(
            role_id="ai_reviewer",
            name="AI Reviewer",
            description="Reviews and overrides AI decisions",
            permissions={
                Permission.READ, Permission.AI_REVIEW, Permission.AI_OVERRIDE,
            },
            resource_types={
                ResourceType.AI_SYSTEM, ResourceType.AI_DECISION,
                ResourceType.CAPSULE,
            },
            data_classifications={
                DataClassification.PUBLIC, DataClassification.INTERNAL,
                DataClassification.CONFIDENTIAL,
            },
            is_privileged=False,
            requires_mfa=True,
        )
        
        # System administrator
        self._roles["admin"] = Role(
            role_id="admin",
            name="Administrator",
            description="Full system access",
            permissions=set(Permission),
            resource_types=set(ResourceType),
            data_classifications=set(DataClassification),
            is_privileged=True,
            requires_mfa=True,
            max_session_duration=timedelta(hours=4),
        )
    
    # ───────────────────────────────────────────────────────────────
    # RBAC OPERATIONS
    # ───────────────────────────────────────────────────────────────
    
    def assign_role(
        self,
        user_id: str,
        role_id: str,
        assigned_by: str,
    ) -> bool:
        """Assign a role to a user."""
        if role_id not in self._roles:
            logger.warning("role_not_found", role_id=role_id)
            return False
        
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role_id)
        
        logger.info(
            "role_assigned",
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
        )
        
        return True
    
    def revoke_role(
        self,
        user_id: str,
        role_id: str,
        revoked_by: str,
    ) -> bool:
        """Revoke a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role_id)
            
            logger.info(
                "role_revoked",
                user_id=user_id,
                role_id=role_id,
                revoked_by=revoked_by,
            )
            return True
        return False
    
    def get_user_roles(self, user_id: str) -> list[Role]:
        """Get all roles assigned to a user."""
        role_ids = self._user_roles.get(user_id, set())
        return [self._roles[rid] for rid in role_ids if rid in self._roles]
    
    def get_effective_permissions(self, user_id: str) -> set[Permission]:
        """Get combined permissions from all user roles."""
        permissions = set()
        for role in self.get_user_roles(user_id):
            permissions.update(role.permissions)
        return permissions
    
    # ───────────────────────────────────────────────────────────────
    # ACCESS DECISIONS
    # ───────────────────────────────────────────────────────────────
    
    def check_access(
        self,
        user_id: str,
        permission: Permission,
        resource_type: ResourceType,
        resource_id: str | None = None,
        data_classification: DataClassification | None = None,
        context: dict[str, Any] | None = None,
    ) -> AccessDecision:
        """
        Evaluate access request.
        
        Per SOC 2 CC6.1 - Logical and physical access controls.
        """
        context = context or {}
        
        # Get user roles
        roles = self.get_user_roles(user_id)
        
        if not roles:
            return AccessDecision(
                allowed=False,
                reason="No roles assigned to user",
                audit_required=True,
            )
        
        # Check RBAC first
        for role in roles:
            if not role.has_permission(permission):
                continue
            
            if not role.can_access_resource(resource_type):
                continue
            
            if data_classification and not role.can_access_classification(data_classification):
                continue
            
            # Role grants access
            return AccessDecision(
                allowed=True,
                reason=f"Access granted by role: {role.name}",
                role_id=role.role_id,
                requires_mfa=role.requires_mfa,
                audit_required=role.is_privileged or data_classification in {
                    DataClassification.SENSITIVE_PERSONAL,
                    DataClassification.PHI,
                    DataClassification.PCI,
                },
            )
        
        # Check ABAC policies if RBAC didn't grant access
        if self.config.access_control_model in {
            AccessControlModel.ABAC,
            AccessControlModel.HYBRID,
        }:
            for policy in self._policies.values():
                if permission not in policy.permissions:
                    continue
                
                subject = {"user_id": user_id, **context.get("subject", {})}
                resource = {
                    "type": resource_type.value,
                    "id": resource_id,
                    "classification": data_classification.value if data_classification else None,
                    **context.get("resource", {}),
                }
                environment = context.get("environment", {})
                
                if policy.evaluate(subject, resource, environment):
                    if policy.effect == "allow":
                        return AccessDecision(
                            allowed=True,
                            reason=f"Access granted by policy: {policy.name}",
                            policy_id=policy.policy_id,
                            audit_required=True,
                        )
        
        return AccessDecision(
            allowed=False,
            reason="No role or policy grants required access",
            audit_required=True,
        )
    
    # ───────────────────────────────────────────────────────────────
    # PRIVILEGED ACCESS MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    def is_privileged_user(self, user_id: str) -> bool:
        """Check if user has any privileged roles."""
        return any(role.is_privileged for role in self.get_user_roles(user_id))
    
    def require_justification(
        self,
        user_id: str,
        resource_type: ResourceType,
        action: str,
    ) -> bool:
        """Determine if action requires justification (break-glass)."""
        # Privileged access to sensitive resources requires justification
        sensitive_resources = {
            ResourceType.AUDIT_LOG,
            ResourceType.SYSTEM_CONFIG,
            ResourceType.BREACH,
        }
        
        return (
            resource_type in sensitive_resources
            and self.is_privileged_user(user_id)
        )


# ═══════════════════════════════════════════════════════════════════════════
# AUTHENTICATION / MFA
# ═══════════════════════════════════════════════════════════════════════════


class MFAMethod(str, Enum):
    """Multi-factor authentication methods."""
    TOTP = "totp"              # Time-based OTP (Authenticator apps)
    SMS = "sms"                # SMS OTP (less secure, PCI may restrict)
    EMAIL = "email"            # Email OTP
    PUSH = "push"              # Push notification
    HARDWARE_KEY = "hardware"  # FIDO2/WebAuthn
    BIOMETRIC = "biometric"    # Fingerprint, face


@dataclass
class MFAChallenge:
    """MFA challenge for user authentication."""
    challenge_id: str
    user_id: str
    method: MFAMethod
    created_at: datetime
    expires_at: datetime
    secret: str | None = None
    verified: bool = False
    attempts: int = 0
    max_attempts: int = 3


@dataclass
class Session:
    """User session with security attributes."""
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    mfa_verified: bool = False
    mfa_method: MFAMethod | None = None
    is_privileged: bool = False
    
    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at
    
    @property
    def is_idle(self) -> bool:
        # 15-minute idle timeout per PCI-DSS
        idle_threshold = timedelta(minutes=15)
        return datetime.now(UTC) - self.last_activity > idle_threshold


class AuthenticationService:
    """
    Authentication service with MFA support.
    
    Per PCI-DSS 4.0.1 Requirement 8, SOC 2 CC6.1.
    """
    
    def __init__(self):
        self.config = get_compliance_config()
        self._challenges: dict[str, MFAChallenge] = {}
        self._sessions: dict[str, Session] = {}
        
        # Rate limiting
        self._failed_attempts: dict[str, list[datetime]] = {}
        self._lockouts: dict[str, datetime] = {}
    
    def create_mfa_challenge(
        self,
        user_id: str,
        method: MFAMethod,
    ) -> MFAChallenge:
        """Create an MFA challenge for a user."""
        challenge = MFAChallenge(
            challenge_id=str(uuid4()),
            user_id=user_id,
            method=method,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            secret=secrets.token_hex(16) if method in {MFAMethod.TOTP, MFAMethod.SMS, MFAMethod.EMAIL} else None,
        )
        
        self._challenges[challenge.challenge_id] = challenge
        
        logger.info(
            "mfa_challenge_created",
            user_id=user_id,
            method=method.value,
        )
        
        return challenge
    
    def verify_mfa(
        self,
        challenge_id: str,
        code: str,
    ) -> bool:
        """
        Verify MFA response.
        
        Per PCI-DSS 8.4.2 - MFA for all CDE access.
        """
        challenge = self._challenges.get(challenge_id)
        
        if not challenge:
            return False
        
        if challenge.verified:
            return False
        
        if datetime.now(UTC) > challenge.expires_at:
            logger.warning("mfa_challenge_expired", challenge_id=challenge_id)
            return False
        
        challenge.attempts += 1
        
        if challenge.attempts > challenge.max_attempts:
            logger.warning(
                "mfa_max_attempts_exceeded",
                user_id=challenge.user_id,
            )
            return False
        
        # Verify code (simplified - production would use pyotp, etc.)
        expected = challenge.secret[:6] if challenge.secret else ""
        
        if secrets.compare_digest(code, expected):
            challenge.verified = True
            logger.info(
                "mfa_verified",
                user_id=challenge.user_id,
                method=challenge.method.value,
            )
            return True
        
        return False
    
    def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        mfa_verified: bool = False,
        mfa_method: MFAMethod | None = None,
        is_privileged: bool = False,
    ) -> Session:
        """Create an authenticated session."""
        # Session duration per role/privilege
        duration = timedelta(hours=8)
        if is_privileged:
            duration = timedelta(hours=4)  # Shorter for privileged
        
        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user_id,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + duration,
            last_activity=datetime.now(UTC),
            ip_address=ip_address,
            user_agent=user_agent,
            mfa_verified=mfa_verified,
            mfa_method=mfa_method,
            is_privileged=is_privileged,
        )
        
        self._sessions[session.session_id] = session
        
        logger.info(
            "session_created",
            user_id=user_id,
            is_privileged=is_privileged,
            mfa_verified=mfa_verified,
        )
        
        return session
    
    def validate_session(
        self,
        session_id: str,
    ) -> Session | None:
        """Validate and refresh a session."""
        session = self._sessions.get(session_id)
        
        if not session:
            return None
        
        if session.is_expired:
            self.invalidate_session(session_id)
            return None
        
        if session.is_idle:
            logger.info(
                "session_idle_timeout",
                session_id=session_id,
                user_id=session.user_id,
            )
            self.invalidate_session(session_id)
            return None
        
        # Refresh activity
        session.last_activity = datetime.now(UTC)
        
        return session
    
    def invalidate_session(self, session_id: str) -> None:
        """Invalidate a session."""
        if session_id in self._sessions:
            session = self._sessions.pop(session_id)
            logger.info(
                "session_invalidated",
                session_id=session_id,
                user_id=session.user_id,
            )
    
    def check_account_lockout(self, user_id: str) -> bool:
        """Check if account is locked out."""
        lockout_until = self._lockouts.get(user_id)
        if lockout_until and datetime.now(UTC) < lockout_until:
            return True
        return False
    
    def record_failed_attempt(self, user_id: str) -> None:
        """Record a failed authentication attempt."""
        now = datetime.now(UTC)
        
        if user_id not in self._failed_attempts:
            self._failed_attempts[user_id] = []
        
        # Remove old attempts (30-minute window)
        cutoff = now - timedelta(minutes=30)
        self._failed_attempts[user_id] = [
            t for t in self._failed_attempts[user_id] if t > cutoff
        ]
        
        self._failed_attempts[user_id].append(now)
        
        # Lock after 5 failed attempts per PCI-DSS 8.3.4
        if len(self._failed_attempts[user_id]) >= 5:
            self._lockouts[user_id] = now + timedelta(minutes=30)
            logger.warning(
                "account_locked",
                user_id=user_id,
                duration_minutes=30,
            )


# ═══════════════════════════════════════════════════════════════════════════
# PASSWORD POLICY
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PasswordPolicy:
    """Password requirements per PCI-DSS 4.0.1 Req 8.3."""
    min_length: int = 12  # PCI-DSS 4.0.1 increased to 12
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    max_age_days: int = 90
    history_count: int = 4  # Cannot reuse last 4 passwords
    min_age_days: int = 1  # Prevent rapid changes


class PasswordService:
    """Password management with policy enforcement."""
    
    def __init__(self, policy: PasswordPolicy | None = None):
        self.policy = policy or PasswordPolicy()
        self._password_history: dict[str, list[str]] = {}
    
    def validate_password(self, password: str) -> tuple[bool, list[str]]:
        """
        Validate password against policy.
        
        Returns (is_valid, list of violations).
        """
        violations = []
        
        if len(password) < self.policy.min_length:
            violations.append(
                f"Password must be at least {self.policy.min_length} characters"
            )
        
        if self.policy.require_uppercase and not any(c.isupper() for c in password):
            violations.append("Password must contain uppercase letter")
        
        if self.policy.require_lowercase and not any(c.islower() for c in password):
            violations.append("Password must contain lowercase letter")
        
        if self.policy.require_digit and not any(c.isdigit() for c in password):
            violations.append("Password must contain digit")
        
        if self.policy.require_special:
            special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
            if not any(c in special_chars for c in password):
                violations.append("Password must contain special character")
        
        return len(violations) == 0, violations
    
    def check_history(
        self,
        user_id: str,
        password_hash: str,
    ) -> bool:
        """Check if password was recently used."""
        history = self._password_history.get(user_id, [])
        return password_hash not in history[:self.policy.history_count]
    
    def record_password(
        self,
        user_id: str,
        password_hash: str,
    ) -> None:
        """Record password in history."""
        if user_id not in self._password_history:
            self._password_history[user_id] = []
        
        self._password_history[user_id].insert(0, password_hash)
        
        # Keep only required history
        self._password_history[user_id] = self._password_history[user_id][
            :self.policy.history_count + 1
        ]


# Global service instances
_access_control: AccessControlService | None = None
_auth_service: AuthenticationService | None = None


def get_access_control_service() -> AccessControlService:
    """Get the global access control service."""
    global _access_control
    if _access_control is None:
        _access_control = AccessControlService()
    return _access_control


def get_authentication_service() -> AuthenticationService:
    """Get the global authentication service."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthenticationService()
    return _auth_service
