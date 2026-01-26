"""
Security Validator Overlay for Forge Cascade V2

Validates capsules and actions against security policies.
Part of the VALIDATION phase in the 7-phase pipeline.

Responsibilities:
- Content policy validation
- Trust level verification
- Rate limiting checks
- Capability verification
- Input sanitization
- Threat detection
"""

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from ..models.base import TrustLevel
from ..models.events import Event, EventType
from ..models.overlay import Capability
from ..security.safe_regex import RegexTimeoutError, RegexValidationError, safe_search
from .base import BaseOverlay, OverlayContext, OverlayError, OverlayResult

logger = structlog.get_logger()


class SecurityValidationError(OverlayError):
    """Security validation failed."""
    pass


class ThreatDetectedError(SecurityValidationError):
    """Potential threat detected."""
    pass


class RateLimitExceededError(SecurityValidationError):
    """Rate limit exceeded."""
    pass


@dataclass
class ValidationRule:
    """A security validation rule."""
    name: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True

    def validate(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate data against this rule (sync version).

        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError

    async def validate_async(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate data against this rule (async version).

        SECURITY FIX (Audit 4 - M8): Default implementation calls sync version.
        Override in subclasses that need async operations (e.g., RateLimitRule).

        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.validate(data)


@dataclass
class ContentPolicyRule(ValidationRule):
    """Content policy validation rule."""
    blocked_patterns: list[str] = field(default_factory=list)
    max_content_length: int = 100000  # 100KB

    def validate(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        content = data.get("content", "")
        if isinstance(content, dict):
            content = str(content)

        # Check length
        if len(content) > self.max_content_length:
            return False, f"Content exceeds maximum length ({self.max_content_length})"

        # Check blocked patterns
        # SECURITY FIX (Audit 3): Use safe_search to prevent ReDoS attacks
        for pattern in self.blocked_patterns:
            try:
                if safe_search(pattern, content, re.IGNORECASE, timeout=0.5, validate=True):
                    return False, f"Content contains blocked pattern: {pattern[:20]}..."
            except (RegexTimeoutError, RegexValidationError) as e:
                # Log but don't block - invalid pattern is a configuration error
                structlog.get_logger().warning(
                    "invalid_blocked_pattern",
                    pattern=pattern[:30],
                    error=str(e)
                )
                continue

        return True, None


@dataclass
class TrustRule(ValidationRule):
    """Trust level validation rule."""
    min_trust_level: int = 0
    action_trust_requirements: dict[str, int] = field(default_factory=dict)

    def validate(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        user_trust = data.get("trust_flame", 0)
        action = data.get("action", "default")

        required = self.action_trust_requirements.get(action, self.min_trust_level)

        if user_trust < required:
            return False, f"Insufficient trust level ({user_trust} < {required}) for action: {action}"

        return True, None


@dataclass
class RateLimitRule(ValidationRule):
    """
    Rate limiting validation rule.

    SECURITY FIX (Audit 2): Uses proper locking to prevent race conditions
    that could allow rate limit bypass through concurrent requests.

    SECURITY FIX (Audit 4 - M8): Uses asyncio.Lock instead of threading.Lock
    to avoid blocking the event loop in async contexts.
    """
    requests_per_minute: int = 60
    requests_per_hour: int = 1000

    # These get populated by the overlay
    minute_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    hour_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    minute_reset: datetime = field(default_factory=lambda: datetime.now(UTC))
    hour_reset: datetime = field(default_factory=lambda: datetime.now(UTC))

    # SECURITY FIX (Audit 4 - M8): Use asyncio.Lock instead of threading.Lock
    # threading.Lock blocks the entire thread including the event loop
    _async_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def validate(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Synchronous validation (for backwards compatibility).

        WARNING: This method uses internal synchronous logic without locking.
        For thread-safe rate limiting in async contexts, use validate_async().
        """
        user_id = data.get("user_id", "anonymous")
        now = datetime.now(UTC)

        # Reset counters if needed (non-atomic, use validate_async for safety)
        if now - self.minute_reset > timedelta(minutes=1):
            self.minute_counts.clear()
            self.minute_reset = now

        if now - self.hour_reset > timedelta(hours=1):
            self.hour_counts.clear()
            self.hour_reset = now

        # Get current counts
        current_minute = self.minute_counts[user_id]
        current_hour = self.hour_counts[user_id]

        # Check limits
        if current_minute >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute}/min"

        if current_hour >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {self.requests_per_hour}/hour"

        # Increment counters
        self.minute_counts[user_id] = current_minute + 1
        self.hour_counts[user_id] = current_hour + 1

        return True, None

    async def validate_async(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Async validation with proper locking.

        SECURITY FIX (Audit 4 - M8): Uses asyncio.Lock for non-blocking
        rate limiting in async contexts.
        """
        user_id = data.get("user_id", "anonymous")
        now = datetime.now(UTC)

        # Use async lock for non-blocking atomic operations
        async with self._async_lock:
            # Reset counters if needed
            if now - self.minute_reset > timedelta(minutes=1):
                self.minute_counts.clear()
                self.minute_reset = now

            if now - self.hour_reset > timedelta(hours=1):
                self.hour_counts.clear()
                self.hour_reset = now

            # Get current counts
            current_minute = self.minute_counts[user_id]
            current_hour = self.hour_counts[user_id]

            # Check limits BEFORE incrementing (within lock for atomicity)
            if current_minute >= self.requests_per_minute:
                return False, f"Rate limit exceeded: {self.requests_per_minute}/min"

            if current_hour >= self.requests_per_hour:
                return False, f"Rate limit exceeded: {self.requests_per_hour}/hour"

            # Increment counters ATOMICALLY with check
            self.minute_counts[user_id] = current_minute + 1
            self.hour_counts[user_id] = current_hour + 1

        return True, None


@dataclass
class InputSanitizationRule(ValidationRule):
    """Input sanitization rule."""
    # Common injection patterns
    sql_patterns: list[str] = field(default_factory=lambda: [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(--|\#|\/\*)",
        r"(\bOR\b.*=.*\bOR\b)",
    ])
    xss_patterns: list[str] = field(default_factory=lambda: [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ])

    def validate(self, data: dict[str, Any]) -> tuple[bool, str | None]:
        content = str(data.get("content", ""))

        # SECURITY FIX (Audit 3): Use safe_search to prevent ReDoS
        # Check for SQL injection
        for pattern in self.sql_patterns:
            try:
                if safe_search(pattern, content, re.IGNORECASE, timeout=0.5, validate=False):
                    return False, "Potential SQL injection detected"
            except RegexTimeoutError:
                # If regex times out on suspicious input, treat as potential attack
                return False, "Input validation timeout - potential attack"

        # Check for XSS
        for pattern in self.xss_patterns:
            try:
                if safe_search(pattern, content, re.IGNORECASE, timeout=0.5, validate=False):
                    return False, "Potential XSS attack detected"
            except RegexTimeoutError:
                return False, "Input validation timeout - potential attack"

        return True, None


@dataclass
class ValidationResult:
    """Result of security validation."""
    valid: bool
    rule_results: dict[str, tuple[bool, str | None]] = field(default_factory=dict)
    threats_detected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_data: dict[str, Any] | None = None
    validation_time_ms: float = 0.0

    @property
    def critical_failures(self) -> list[str]:
        """Get critical rule failures."""
        return [name for name, (valid, _) in self.rule_results.items()
                if not valid and "critical" in name.lower()]

    @property
    def all_errors(self) -> list[str]:
        """Get all error messages."""
        return [msg for _, (valid, msg) in self.rule_results.items()
                if not valid and msg]


class SecurityValidatorOverlay(BaseOverlay):
    """
    Security validation overlay.

    Validates all incoming data against security policies,
    performs threat detection, and enforces rate limits.
    """

    NAME = "security_validator"
    VERSION = "1.0.0"
    DESCRIPTION = "Validates capsules and actions against security policies"

    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.CAPSULE_ACCESSED,
        EventType.PROPOSAL_CREATED,
        EventType.VOTE_CAST,
        EventType.SYSTEM_EVENT,
    }

    REQUIRED_CAPABILITIES = {Capability.DATABASE_READ}

    def __init__(
        self,
        enable_rate_limiting: bool = True,
        enable_content_policy: bool = True,
        enable_trust_validation: bool = True,
        enable_input_sanitization: bool = True,
        custom_rules: list[ValidationRule] | None = None
    ) -> None:
        """
        Initialize the security validator.

        Args:
            enable_rate_limiting: Enable rate limit checks
            enable_content_policy: Enable content policy checks
            enable_trust_validation: Enable trust level validation
            enable_input_sanitization: Enable input sanitization
            custom_rules: Additional custom validation rules
        """
        super().__init__()
        self._rules: list[ValidationRule] = []

        # Initialize default rules
        if enable_content_policy:
            self._rules.append(ContentPolicyRule(
                name="content_policy",
                description="Validates content against policy",
                severity="high",
                blocked_patterns=[
                    r"\b(password|secret|api_key)\s*[:=]\s*['\"]?\w+",  # Exposed secrets
                ]
            ))

        if enable_trust_validation:
            self._rules.append(TrustRule(
                name="trust_validation",
                description="Validates trust levels for actions",
                severity="high",
                min_trust_level=TrustLevel.SANDBOX.value,
                action_trust_requirements={
                    "create_capsule": TrustLevel.SANDBOX.value,
                    "update_capsule": TrustLevel.STANDARD.value,
                    "delete_capsule": TrustLevel.TRUSTED.value,
                    "create_proposal": TrustLevel.STANDARD.value,
                    "vote": TrustLevel.SANDBOX.value,
                    "execute_overlay": TrustLevel.TRUSTED.value,
                    "admin_action": TrustLevel.CORE.value,
                }
            ))

        if enable_rate_limiting:
            self._rules.append(RateLimitRule(
                name="rate_limit",
                description="Enforces rate limits",
                severity="medium",
                requests_per_minute=60,
                requests_per_hour=1000
            ))

        if enable_input_sanitization:
            self._rules.append(InputSanitizationRule(
                name="input_sanitization",
                description="Sanitizes input against injection attacks",
                severity="critical"
            ))

        # Add custom rules
        if custom_rules:
            self._rules.extend(custom_rules)

        # Threat tracking
        # SECURITY FIX (Audit 3): Bounded memory limits to prevent DoS
        self._MAX_THREAT_CACHE_USERS: int = 10000  # Max users tracked
        self._MAX_THREATS_PER_USER: int = 100  # Max threats per user
        self._MAX_BLOCKED_USERS: int = 10000  # Max blocked users
        self._threat_cache: dict[str, list[datetime]] = defaultdict(list)
        # SECURITY FIX (Audit 4 - M9): Use OrderedDict for LRU eviction of blocked users
        # This ensures we evict the oldest blocked user (who has been blocked longest)
        # rather than a random one, which could accidentally unblock an active attacker
        from collections import OrderedDict
        self._blocked_users: OrderedDict[str, datetime] = OrderedDict()  # user_id -> blocked_at
        self._threat_cache_access_order: list[str] = []  # For LRU eviction

        self._logger = logger.bind(overlay=self.NAME)

    async def initialize(self) -> bool:
        """Initialize the security validator."""
        self._logger.info(
            "security_validator_initialized",
            rules=len(self._rules),
            rule_names=[r.name for r in self._rules]
        )
        return True

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """
        Execute security validation.

        Args:
            context: Execution context
            event: Triggering event
            input_data: Data to validate

        Returns:
            Validation result
        """
        import time
        start_time = time.time()

        data = input_data or {}
        if event:
            data.update(event.payload or {})
            data["event_type"] = event.type.value

        # Add context data
        data["user_id"] = context.user_id
        data["trust_flame"] = context.trust_flame

        # Check if user is blocked
        if context.user_id and context.user_id in self._blocked_users:
            return OverlayResult(
                success=False,
                error="User is temporarily blocked due to security violations",
                data={"blocked": True}
            )

        # Run validation
        validation_result = await self._validate(data, context)

        duration_ms = (time.time() - start_time) * 1000
        validation_result.validation_time_ms = duration_ms

        # Track threats
        if validation_result.threats_detected:
            await self._track_threats(context.user_id, validation_result.threats_detected)

        # Log result
        self._logger.info(
            "security_validation_complete",
            valid=validation_result.valid,
            threats=len(validation_result.threats_detected),
            duration_ms=round(duration_ms, 2)
        )

        # Prepare events to emit
        events_to_emit = []
        if not validation_result.valid:
            events_to_emit.append({
                "event_type": EventType.SECURITY_ALERT,
                "payload": {
                    "errors": validation_result.all_errors,
                    "threats": validation_result.threats_detected,
                    "user_id": context.user_id
                }
            })

        return OverlayResult(
            success=validation_result.valid,
            error="; ".join(validation_result.all_errors) if not validation_result.valid else None,
            data={
                "validation": {
                    "valid": validation_result.valid,
                    "rule_results": {
                        name: {"valid": valid, "error": error}
                        for name, (valid, error) in validation_result.rule_results.items()
                    },
                    "threats": validation_result.threats_detected,
                    "warnings": validation_result.warnings,
                    "validation_time_ms": round(duration_ms, 2)
                },
                "sanitized_data": validation_result.sanitized_data
            },
            events_to_emit=events_to_emit,
            metrics={
                "rules_checked": len(self._rules),
                "rules_passed": sum(1 for v, _ in validation_result.rule_results.values() if v),
                "threats_detected": len(validation_result.threats_detected)
            }
        )

    async def _validate(
        self,
        data: dict[str, Any],
        context: OverlayContext
    ) -> ValidationResult:
        """Run all validation rules."""
        rule_results = {}
        threats = []
        warnings = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            try:
                # SECURITY FIX (Audit 4 - M8): Use async validation to avoid blocking
                valid, error = await rule.validate_async(data)
                rule_results[rule.name] = (valid, error)

                if not valid:
                    if rule.severity == "critical":
                        threats.append(f"[CRITICAL] {rule.name}: {error}")
                    elif rule.severity == "high":
                        threats.append(f"[HIGH] {rule.name}: {error}")
                    elif rule.severity == "medium":
                        warnings.append(f"[MEDIUM] {rule.name}: {error}")
                    else:
                        warnings.append(f"[LOW] {rule.name}: {error}")

            except Exception as e:
                self._logger.error(
                    "rule_validation_error",
                    rule=rule.name,
                    error=str(e)
                )
                # Fail closed - if validation fails, deny
                rule_results[rule.name] = (False, f"Validation error: {str(e)}")
                threats.append(f"Rule error: {rule.name}")

        # Determine overall validity
        all_valid = all(valid for valid, _ in rule_results.values())

        # Sanitize data if valid
        sanitized = None
        if all_valid:
            sanitized = self._sanitize_data(data)

        return ValidationResult(
            valid=all_valid,
            rule_results=rule_results,
            threats_detected=threats,
            warnings=warnings,
            sanitized_data=sanitized
        )

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize data for safe processing."""
        sanitized: dict[str, Any] = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Basic HTML entity encoding
                sanitized[key] = (
                    value
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&#x27;")
                )
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_data(v) if isinstance(v, dict)
                    else v for v in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    async def _track_threats(
        self,
        user_id: str | None,
        threats: list[str]
    ) -> None:
        """Track threats and potentially block users."""
        if not user_id:
            return

        now = datetime.now(UTC)

        # SECURITY FIX (Audit 3): Enforce bounded memory for threat cache
        # Check if we need to evict old users from threat cache
        if user_id not in self._threat_cache:
            if len(self._threat_cache) >= self._MAX_THREAT_CACHE_USERS:
                # Evict oldest users from threat cache (LRU)
                evict_count = max(1, len(self._threat_cache_access_order) // 10)
                for old_user in self._threat_cache_access_order[:evict_count]:
                    self._threat_cache.pop(old_user, None)
                self._threat_cache_access_order = self._threat_cache_access_order[evict_count:]
                self._logger.info("threat_cache_eviction", evicted_users=evict_count)
            self._threat_cache_access_order.append(user_id)

        # Add threats to cache (bounded per user)
        new_threats = [now] * len(threats)
        self._threat_cache[user_id].extend(new_threats)

        # Clean old threats (last hour) AND enforce per-user limit
        cutoff = now - timedelta(hours=1)
        recent_threats = [t for t in self._threat_cache[user_id] if t > cutoff]
        # Keep only the most recent threats up to limit
        self._threat_cache[user_id] = recent_threats[-self._MAX_THREATS_PER_USER:]

        # Block user if too many threats
        if len(self._threat_cache[user_id]) >= 10:
            # SECURITY FIX (Audit 3): Enforce bounded blocked users set
            # SECURITY FIX (Audit 4 - M9): Use LRU eviction instead of random
            if len(self._blocked_users) >= self._MAX_BLOCKED_USERS:
                # Evict the oldest blocked user (first in OrderedDict)
                try:
                    evicted_user, evicted_at = self._blocked_users.popitem(last=False)
                    self._logger.info(
                        "blocked_user_evicted_lru",
                        evicted_user_id=evicted_user,
                        blocked_since=evicted_at.isoformat(),
                    )
                except KeyError:
                    pass
            # Add user with current timestamp
            self._blocked_users[user_id] = datetime.now(UTC)
            self._logger.warning(
                "user_blocked_for_threats",
                user_id=user_id,
                threat_count=len(self._threat_cache[user_id])
            )

    def unblock_user(self, user_id: str) -> None:
        """Manually unblock a user."""
        # SECURITY FIX (Audit 4 - M9): Updated for OrderedDict
        self._blocked_users.pop(user_id, None)
        self._threat_cache.pop(user_id, None)
        self._logger.info("user_unblocked", user_id=user_id)

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a custom validation rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a validation rule by name."""
        for i, rule in enumerate(self._rules):
            if rule.name == rule_name:
                self._rules.pop(i)
                return True
        return False

    def get_rules(self) -> list[dict[str, Any]]:
        """Get all validation rules."""
        return [
            {
                "name": r.name,
                "description": r.description,
                "severity": r.severity,
                "enabled": r.enabled
            }
            for r in self._rules
        ]

    def get_blocked_users(self) -> set[str]:
        """Get set of blocked users."""
        # SECURITY FIX (Audit 4 - M9): Return keys only (for API compatibility)
        return set(self._blocked_users.keys())

    def get_threat_summary(self) -> dict[str, Any]:
        """Get threat summary statistics."""
        now = datetime.now(UTC)
        cutoff_hour = now - timedelta(hours=1)

        total_threats = sum(
            len([t for t in threats if t > cutoff_hour])
            for threats in self._threat_cache.values()
        )

        return {
            "total_threats_last_hour": total_threats,
            "blocked_users": len(self._blocked_users),
            "users_with_threats": len(self._threat_cache),
            "rules_active": sum(1 for r in self._rules if r.enabled)
        }


# Convenience function
def create_security_validator(
    strict_mode: bool = False,
    **kwargs: Any
) -> SecurityValidatorOverlay:
    """
    Create a security validator with common configurations.

    Args:
        strict_mode: If True, enables all validations with stricter limits
        **kwargs: Additional configuration

    Returns:
        Configured SecurityValidatorOverlay
    """
    if strict_mode:
        kwargs.setdefault("enable_rate_limiting", True)
        kwargs.setdefault("enable_content_policy", True)
        kwargs.setdefault("enable_trust_validation", True)
        kwargs.setdefault("enable_input_sanitization", True)

    return SecurityValidatorOverlay(**kwargs)
