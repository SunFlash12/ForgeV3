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

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from collections import defaultdict
import re
import hashlib
import structlog

from ..models.events import Event, EventType
from ..models.overlay import Capability, FuelBudget
from ..models.base import TrustLevel
from .base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
    OverlayError
)

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
    
    def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        """
        Validate data against this rule.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        raise NotImplementedError


@dataclass
class ContentPolicyRule(ValidationRule):
    """Content policy validation rule."""
    blocked_patterns: list[str] = field(default_factory=list)
    max_content_length: int = 100000  # 100KB
    
    def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        content = data.get("content", "")
        if isinstance(content, dict):
            content = str(content)
        
        # Check length
        if len(content) > self.max_content_length:
            return False, f"Content exceeds maximum length ({self.max_content_length})"
        
        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, f"Content contains blocked pattern: {pattern[:20]}..."
        
        return True, None


@dataclass
class TrustRule(ValidationRule):
    """Trust level validation rule."""
    min_trust_level: int = 0
    action_trust_requirements: dict[str, int] = field(default_factory=dict)
    
    def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        user_trust = data.get("trust_flame", 0)
        action = data.get("action", "default")
        
        required = self.action_trust_requirements.get(action, self.min_trust_level)
        
        if user_trust < required:
            return False, f"Insufficient trust level ({user_trust} < {required}) for action: {action}"
        
        return True, None


@dataclass
class RateLimitRule(ValidationRule):
    """Rate limiting validation rule."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    
    # These get populated by the overlay
    minute_counts: dict = field(default_factory=lambda: defaultdict(int))
    hour_counts: dict = field(default_factory=lambda: defaultdict(int))
    minute_reset: datetime = field(default_factory=datetime.utcnow)
    hour_reset: datetime = field(default_factory=datetime.utcnow)
    
    def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        user_id = data.get("user_id", "anonymous")
        now = datetime.utcnow()
        
        # Reset counters if needed
        if now - self.minute_reset > timedelta(minutes=1):
            self.minute_counts.clear()
            self.minute_reset = now
        
        if now - self.hour_reset > timedelta(hours=1):
            self.hour_counts.clear()
            self.hour_reset = now
        
        # Check limits
        if self.minute_counts[user_id] >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute}/min"
        
        if self.hour_counts[user_id] >= self.requests_per_hour:
            return False, f"Rate limit exceeded: {self.requests_per_hour}/hour"
        
        # Increment counters
        self.minute_counts[user_id] += 1
        self.hour_counts[user_id] += 1
        
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
    
    def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        content = str(data.get("content", ""))
        
        # Check for SQL injection
        for pattern in self.sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Potential SQL injection detected"
        
        # Check for XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Potential XSS attack detected"
        
        return True, None


@dataclass
class ValidationResult:
    """Result of security validation."""
    valid: bool
    rule_results: dict[str, tuple[bool, Optional[str]]] = field(default_factory=dict)
    threats_detected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_data: Optional[dict] = None
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
        custom_rules: Optional[list[ValidationRule]] = None
    ):
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
        self._threat_cache: dict[str, list[datetime]] = defaultdict(list)
        self._blocked_users: set[str] = set()
        
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
        event: Optional[Event] = None,
        input_data: Optional[dict[str, Any]] = None
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
            data["event_type"] = event.event_type.value
        
        # Add context data
        data["user_id"] = context.user_id
        data["trust_flame"] = context.trust_flame
        
        # Check if user is blocked
        if context.user_id and context.user_id in self._blocked_users:
            return OverlayResult(
                overlay_id=self.id,
                overlay_name=self.NAME,
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
            overlay_id=self.id,
            overlay_name=self.NAME,
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
        data: dict,
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
                valid, error = rule.validate(data)
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
    
    def _sanitize_data(self, data: dict) -> dict:
        """Sanitize data for safe processing."""
        sanitized = {}
        
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
        user_id: Optional[str],
        threats: list[str]
    ) -> None:
        """Track threats and potentially block users."""
        if not user_id:
            return
        
        now = datetime.utcnow()
        
        # Add threats to cache
        self._threat_cache[user_id].extend([now] * len(threats))
        
        # Clean old threats (last hour)
        cutoff = now - timedelta(hours=1)
        self._threat_cache[user_id] = [
            t for t in self._threat_cache[user_id] if t > cutoff
        ]
        
        # Block user if too many threats
        if len(self._threat_cache[user_id]) >= 10:
            self._blocked_users.add(user_id)
            self._logger.warning(
                "user_blocked_for_threats",
                user_id=user_id,
                threat_count=len(self._threat_cache[user_id])
            )
    
    def unblock_user(self, user_id: str) -> None:
        """Manually unblock a user."""
        self._blocked_users.discard(user_id)
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
    
    def get_rules(self) -> list[dict]:
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
        return self._blocked_users.copy()
    
    def get_threat_summary(self) -> dict:
        """Get threat summary statistics."""
        now = datetime.utcnow()
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
    **kwargs
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
