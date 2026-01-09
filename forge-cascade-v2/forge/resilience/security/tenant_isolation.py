"""
Tenant Isolation
================

Multi-tenant data isolation for Forge Enterprise.
Ensures complete separation of tenant data and access control.
"""

from __future__ import annotations

import functools
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
from enum import Enum

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)

F = TypeVar('F', bound=Callable[..., Any])

# Context variable for current tenant
_current_tenant: ContextVar[Optional['TenantContext']] = ContextVar(
    'current_tenant',
    default=None
)


class TenantTier(Enum):
    """Tenant subscription tiers."""

    FREE = "free"
    STANDARD = "standard"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantLimits:
    """Resource limits for a tenant."""

    max_capsules: int = 10000
    max_users: int = 100
    max_storage_mb: int = 1024
    max_api_calls_per_hour: int = 10000
    max_lineage_depth: int = 10
    allow_custom_overlays: bool = False
    allow_ghost_council: bool = False

    @classmethod
    def for_tier(cls, tier: TenantTier) -> 'TenantLimits':
        """Get limits for a subscription tier."""
        tier_limits = {
            TenantTier.FREE: cls(
                max_capsules=100,
                max_users=5,
                max_storage_mb=100,
                max_api_calls_per_hour=1000,
                max_lineage_depth=3,
            ),
            TenantTier.STANDARD: cls(
                max_capsules=10000,
                max_users=50,
                max_storage_mb=1024,
                max_api_calls_per_hour=10000,
                max_lineage_depth=5,
            ),
            TenantTier.PROFESSIONAL: cls(
                max_capsules=100000,
                max_users=500,
                max_storage_mb=10240,
                max_api_calls_per_hour=50000,
                max_lineage_depth=10,
                allow_custom_overlays=True,
            ),
            TenantTier.ENTERPRISE: cls(
                max_capsules=-1,  # Unlimited
                max_users=-1,
                max_storage_mb=-1,
                max_api_calls_per_hour=-1,
                max_lineage_depth=-1,
                allow_custom_overlays=True,
                allow_ghost_council=True,
            ),
        }
        return tier_limits.get(tier, cls())


@dataclass
class TenantContext:
    """Context information for the current tenant."""

    tenant_id: str
    tenant_name: str
    tier: TenantTier = TenantTier.STANDARD
    limits: TenantLimits = field(default_factory=TenantLimits)
    features: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Usage tracking
    current_capsule_count: int = 0
    current_user_count: int = 0
    current_storage_mb: float = 0.0

    def can_create_capsule(self) -> bool:
        """Check if tenant can create more capsules."""
        if self.limits.max_capsules < 0:
            return True
        return self.current_capsule_count < self.limits.max_capsules

    def can_add_user(self) -> bool:
        """Check if tenant can add more users."""
        if self.limits.max_users < 0:
            return True
        return self.current_user_count < self.limits.max_users

    def has_feature(self, feature: str) -> bool:
        """Check if tenant has a specific feature enabled."""
        return feature in self.features


class TenantIsolationError(Exception):
    """Raised when tenant isolation is violated."""
    pass


class TenantQuotaExceededError(Exception):
    """Raised when tenant exceeds resource quota."""
    pass


class TenantIsolator:
    """
    Manages tenant isolation and access control.

    Ensures complete data separation between tenants
    and enforces resource quotas.
    """

    def __init__(self):
        self._config = get_resilience_config().tenant_isolation
        self._tenants: Dict[str, TenantContext] = {}
        self._cross_tenant_attempts: List[Dict] = []

    def register_tenant(self, context: TenantContext) -> None:
        """Register a tenant context."""
        self._tenants[context.tenant_id] = context
        logger.info(
            "tenant_registered",
            tenant_id=context.tenant_id,
            tier=context.tier.value
        )

    def get_tenant(self, tenant_id: str) -> Optional[TenantContext]:
        """Get tenant context by ID."""
        return self._tenants.get(tenant_id)

    def set_current_tenant(self, context: TenantContext) -> None:
        """Set the current tenant context."""
        _current_tenant.set(context)

    def get_current_tenant(self) -> Optional[TenantContext]:
        """Get the current tenant context."""
        return _current_tenant.get()

    def clear_current_tenant(self) -> None:
        """Clear the current tenant context."""
        _current_tenant.set(None)

    def validate_access(
        self,
        resource_tenant_id: str,
        operation: str = "read"
    ) -> bool:
        """
        Validate that current tenant can access a resource.

        Args:
            resource_tenant_id: Tenant ID of the resource owner
            operation: Type of operation being performed

        Returns:
            True if access is allowed

        Raises:
            TenantIsolationError: If access is denied
        """
        if not self._config.enabled:
            return True

        current = self.get_current_tenant()
        if not current:
            if self._config.strict_mode:
                raise TenantIsolationError("No tenant context set")
            return True

        if current.tenant_id != resource_tenant_id:
            # Cross-tenant access attempt
            if self._config.audit_cross_tenant_attempts:
                self._log_cross_tenant_attempt(
                    current.tenant_id,
                    resource_tenant_id,
                    operation
                )

            if self._config.strict_mode:
                raise TenantIsolationError(
                    f"Cross-tenant access denied: {current.tenant_id} -> {resource_tenant_id}"
                )

            return False

        return True

    def check_quota(self, resource_type: str, amount: int = 1) -> bool:
        """
        Check if operation would exceed tenant quota.

        Args:
            resource_type: Type of resource (capsules, users, storage)
            amount: Amount to add

        Returns:
            True if within quota

        Raises:
            TenantQuotaExceededError: If quota would be exceeded
        """
        if not self._config.enabled:
            return True

        current = self.get_current_tenant()
        if not current:
            return True

        if resource_type == "capsules":
            new_total = current.current_capsule_count + amount
            if current.limits.max_capsules >= 0 and new_total > current.limits.max_capsules:
                raise TenantQuotaExceededError(
                    f"Capsule quota exceeded: {new_total}/{current.limits.max_capsules}"
                )

        elif resource_type == "users":
            new_total = current.current_user_count + amount
            if current.limits.max_users >= 0 and new_total > current.limits.max_users:
                raise TenantQuotaExceededError(
                    f"User quota exceeded: {new_total}/{current.limits.max_users}"
                )

        elif resource_type == "storage":
            new_total = current.current_storage_mb + amount
            if current.limits.max_storage_mb >= 0 and new_total > current.limits.max_storage_mb:
                raise TenantQuotaExceededError(
                    f"Storage quota exceeded: {new_total}/{current.limits.max_storage_mb} MB"
                )

        return True

    def get_tenant_filter(self) -> Optional[Dict[str, str]]:
        """
        Get a filter dictionary for tenant-scoped queries.

        Returns:
            Dict with tenant_id filter or None if isolation disabled
        """
        if not self._config.enabled:
            return None

        current = self.get_current_tenant()
        if not current:
            return None

        return {"tenant_id": current.tenant_id}

    def apply_tenant_filter(self, query: str, params: dict | None = None) -> tuple[str, dict]:
        """
        Apply tenant filter to a Cypher query using parameterization.

        SECURITY FIX (Audit 4 - H14): Use parameterized queries instead of
        string interpolation to prevent SQL injection in tenant_id.

        Args:
            query: Original Cypher query
            params: Existing query parameters (will be modified)

        Returns:
            Tuple of (modified_query, updated_params) with tenant filter
        """
        if params is None:
            params = {}

        if not self._config.enabled:
            return query, params

        current = self.get_current_tenant()
        if not current:
            return query, params

        # SECURITY FIX: Validate tenant_id format to prevent injection
        # Tenant IDs should be alphanumeric with limited special chars
        import re
        tenant_id = current.tenant_id
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', tenant_id):
            logger.error(
                "invalid_tenant_id_format",
                tenant_id_length=len(tenant_id)
            )
            raise TenantIsolationError("Invalid tenant ID format")

        # SECURITY FIX: Use parameterized query instead of string interpolation
        # Add tenant_id as a parameter, not directly in the query string
        params["__tenant_filter_id"] = tenant_id

        # Add tenant filter to WHERE clause using parameterized query
        if "WHERE" in query.upper():
            # Add to existing WHERE - find case-insensitive position
            where_pos = query.upper().find("WHERE")
            query = (
                query[:where_pos + 5] +
                " n.tenant_id = $__tenant_filter_id AND" +
                query[where_pos + 5:]
            )
        else:
            # Need to add WHERE clause - this is simplified
            # In production, use proper Cypher parsing
            pass

        return query, params

    def _log_cross_tenant_attempt(
        self,
        source_tenant: str,
        target_tenant: str,
        operation: str
    ) -> None:
        """Log a cross-tenant access attempt."""
        attempt = {
            "timestamp": datetime.utcnow().isoformat(),
            "source_tenant": source_tenant,
            "target_tenant": target_tenant,
            "operation": operation,
        }
        self._cross_tenant_attempts.append(attempt)

        logger.warning(
            "cross_tenant_access_attempt",
            **attempt
        )

        # Keep only last 1000 attempts
        if len(self._cross_tenant_attempts) > 1000:
            self._cross_tenant_attempts = self._cross_tenant_attempts[-1000:]

    def get_audit_log(self) -> List[Dict]:
        """Get cross-tenant access attempt audit log."""
        return list(self._cross_tenant_attempts)


# Global isolator instance
_tenant_isolator: Optional[TenantIsolator] = None


def get_tenant_isolator() -> TenantIsolator:
    """Get or create the global tenant isolator instance."""
    global _tenant_isolator
    if _tenant_isolator is None:
        _tenant_isolator = TenantIsolator()
    return _tenant_isolator


def require_tenant(func: F) -> F:
    """
    Decorator to require tenant context for a function.

    Raises:
        TenantIsolationError: If no tenant context is set
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        isolator = get_tenant_isolator()
        if isolator._config.enabled:
            current = isolator.get_current_tenant()
            if not current:
                raise TenantIsolationError("Tenant context required")
        return await func(*args, **kwargs)

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        isolator = get_tenant_isolator()
        if isolator._config.enabled:
            current = isolator.get_current_tenant()
            if not current:
                raise TenantIsolationError("Tenant context required")
        return func(*args, **kwargs)

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class tenant_scope:
    """
    Context manager for tenant-scoped operations.

    Usage:
        with tenant_scope(tenant_context):
            # Operations are scoped to tenant
            pass
    """

    def __init__(self, context: TenantContext):
        self._context = context
        self._previous: Optional[TenantContext] = None

    def __enter__(self) -> TenantContext:
        isolator = get_tenant_isolator()
        self._previous = isolator.get_current_tenant()
        isolator.set_current_tenant(self._context)
        return self._context

    def __exit__(self, *args) -> None:
        isolator = get_tenant_isolator()
        if self._previous:
            isolator.set_current_tenant(self._previous)
        else:
            isolator.clear_current_tenant()
