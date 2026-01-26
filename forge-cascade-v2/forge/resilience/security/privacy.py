"""
Privacy Management
==================

GDPR-compliant privacy management for Forge.
Handles data retention, anonymization, and right-to-erasure requests.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

from forge.resilience.config import get_resilience_config

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AnonymizationLevel(Enum):
    """Levels of data anonymization."""

    NONE = "none"  # No anonymization
    PSEUDONYMIZE = "pseudonymize"  # Replace with consistent pseudonyms
    MASK = "mask"  # Partially mask sensitive data
    REDACT = "redact"  # Completely remove sensitive data
    HASH = "hash"  # One-way hash


class PIIType(Enum):
    """Types of Personally Identifiable Information."""

    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


@dataclass
class PIIPattern:
    """Pattern for detecting PII in content."""

    pii_type: PIIType
    pattern: str
    description: str
    default_action: AnonymizationLevel = AnonymizationLevel.REDACT


@dataclass
class PrivacyRequest:
    """Represents a privacy-related request."""

    request_id: str
    request_type: str  # erasure, export, access
    subject_id: str  # User/entity making the request
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionPolicy:
    """Data retention policy configuration."""

    default_retention_days: int = 365 * 7  # 7 years
    min_retention_days: int = 30
    max_retention_days: int = 365 * 10  # 10 years

    # Type-specific retention
    capsule_retention_days: int = 365 * 7
    audit_log_retention_days: int = 365 * 3
    session_retention_days: int = 30
    export_retention_days: int = 7


class PrivacyManager:
    """
    Manages privacy compliance for Forge.

    Provides:
    - PII detection and anonymization
    - Data retention management
    - Right to erasure (GDPR Article 17)
    - Data export (GDPR Article 20)
    """

    def __init__(self) -> None:
        self._config = get_resilience_config().privacy
        self._patterns: list[PIIPattern] = []
        self._pseudonym_map: dict[str, str] = {}
        self._retention = RetentionPolicy()
        self._pending_requests: dict[str, PrivacyRequest] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the privacy manager with default patterns."""
        if self._initialized:
            return

        self._init_default_patterns()
        self._initialized = True
        logger.info("privacy_manager_initialized")

    def _init_default_patterns(self) -> None:
        """Initialize default PII detection patterns."""
        patterns = [
            PIIPattern(
                pii_type=PIIType.EMAIL,
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                description="Email address",
                default_action=AnonymizationLevel.MASK,
            ),
            PIIPattern(
                pii_type=PIIType.PHONE,
                pattern=r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
                description="Phone number",
                default_action=AnonymizationLevel.REDACT,
            ),
            PIIPattern(
                pii_type=PIIType.SSN,
                pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                description="Social Security Number",
                default_action=AnonymizationLevel.REDACT,
            ),
            PIIPattern(
                pii_type=PIIType.CREDIT_CARD,
                pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
                description="Credit card number",
                default_action=AnonymizationLevel.REDACT,
            ),
            PIIPattern(
                pii_type=PIIType.IP_ADDRESS,
                pattern=r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
                description="IP address",
                default_action=AnonymizationLevel.HASH,
            ),
        ]

        self._patterns.extend(patterns)

    def add_pattern(self, pattern: PIIPattern) -> None:
        """Add a custom PII detection pattern."""
        self._patterns.append(pattern)

    def detect_pii(self, content: str) -> list[dict[str, Any]]:
        """
        Detect PII in content.

        Args:
            content: Content to scan

        Returns:
            List of detected PII with types and locations
        """
        if not self._initialized:
            self.initialize()

        if not self._config.enabled:
            return []

        findings = []

        for pattern in self._patterns:
            matches = list(re.finditer(pattern.pattern, content, re.IGNORECASE))
            for match in matches:
                findings.append(
                    {
                        "type": pattern.pii_type.value,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                        "description": pattern.description,
                        "default_action": pattern.default_action.value,
                    }
                )

        return findings

    def anonymize(
        self,
        content: str,
        level: AnonymizationLevel = AnonymizationLevel.MASK,
        pii_types: set[PIIType] | None = None,
    ) -> str:
        """
        Anonymize PII in content.

        Args:
            content: Content to anonymize
            level: Level of anonymization to apply
            pii_types: Specific PII types to target (None = all)

        Returns:
            Anonymized content
        """
        if not self._initialized:
            self.initialize()

        if not self._config.enabled or not self._config.anonymization_enabled:
            return content

        if level == AnonymizationLevel.NONE:
            return content

        result = content

        for pattern in self._patterns:
            # Skip if filtering by type and this type not included
            if pii_types and pattern.pii_type not in pii_types:
                continue

            matches = list(re.finditer(pattern.pattern, result, re.IGNORECASE))

            # Process matches in reverse order to preserve positions
            for match in reversed(matches):
                original = match.group()
                replacement = self._get_replacement(original, level, pattern.pii_type)
                result = result[: match.start()] + replacement + result[match.end() :]

        return result

    def _get_replacement(self, original: str, level: AnonymizationLevel, pii_type: PIIType) -> str:
        """Get replacement value for PII."""
        if level == AnonymizationLevel.REDACT:
            return "[REDACTED]"

        elif level == AnonymizationLevel.MASK:
            # Show partial data
            if pii_type == PIIType.EMAIL:
                parts = original.split("@")
                if len(parts) == 2:
                    local = parts[0]
                    masked_local = (
                        local[0] + "*" * (len(local) - 2) + local[-1]
                        if len(local) > 2
                        else "*" * len(local)
                    )
                    return f"{masked_local}@{parts[1]}"
            elif pii_type == PIIType.PHONE:
                digits = re.sub(r"\D", "", original)
                return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"
            elif pii_type == PIIType.CREDIT_CARD:
                digits = re.sub(r"\D", "", original)
                return (
                    f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****-****-****-****"
                )
            elif pii_type == PIIType.SSN:
                return "***-**-****"
            elif pii_type == PIIType.IP_ADDRESS:
                parts = original.split(".")
                return f"{parts[0]}.{parts[1]}.xxx.xxx" if len(parts) == 4 else "xxx.xxx.xxx.xxx"
            return "*" * len(original)

        elif level == AnonymizationLevel.PSEUDONYMIZE:
            # Return consistent pseudonym
            if original not in self._pseudonym_map:
                self._pseudonym_map[original] = self._generate_pseudonym(pii_type)
            return self._pseudonym_map[original]

        elif level == AnonymizationLevel.HASH:
            # One-way hash
            return hashlib.sha256(original.encode()).hexdigest()[:12]

        return original

    def _generate_pseudonym(self, pii_type: PIIType) -> str:
        """Generate a pseudonym for a PII type."""
        random_id = secrets.token_hex(4)

        if pii_type == PIIType.EMAIL:
            return f"user_{random_id}@example.com"
        elif pii_type == PIIType.NAME:
            return f"User_{random_id}"
        elif pii_type == PIIType.PHONE:
            return f"+1-555-{random_id[:3]}-{random_id[3:7]}"
        else:
            return f"[PSEUDONYM_{random_id}]"

    async def process_erasure_request(
        self, subject_id: str, scope: list[str] | None = None
    ) -> PrivacyRequest:
        """
        Process a right-to-erasure request (GDPR Article 17).

        Args:
            subject_id: ID of the data subject requesting erasure
            scope: Optional list of specific data types to erase

        Returns:
            PrivacyRequest tracking the erasure
        """
        request = PrivacyRequest(
            request_id=secrets.token_urlsafe(16),
            request_type="erasure",
            subject_id=subject_id,
            metadata={"scope": scope or ["all"]},
        )

        self._pending_requests[request.request_id] = request

        logger.info("erasure_request_created", request_id=request.request_id, subject_id=subject_id)

        # In production, this would trigger async processing
        # For now, we just create the request

        return request

    async def process_export_request(self, subject_id: str, format: str = "json") -> PrivacyRequest:
        """
        Process a data portability request (GDPR Article 20).

        Args:
            subject_id: ID of the data subject
            format: Export format (json, csv)

        Returns:
            PrivacyRequest tracking the export
        """
        request = PrivacyRequest(
            request_id=secrets.token_urlsafe(16),
            request_type="export",
            subject_id=subject_id,
            metadata={"format": format},
        )

        self._pending_requests[request.request_id] = request

        logger.info("export_request_created", request_id=request.request_id, subject_id=subject_id)

        return request

    def get_request_status(self, request_id: str) -> PrivacyRequest | None:
        """Get the status of a privacy request."""
        return self._pending_requests.get(request_id)

    def get_retention_policy(self) -> RetentionPolicy:
        """Get current data retention policy."""
        return self._retention

    def set_retention_policy(self, policy: RetentionPolicy) -> None:
        """Update data retention policy."""
        self._retention = policy
        logger.info("retention_policy_updated", default_days=policy.default_retention_days)

    def calculate_expiry_date(self, data_type: str, created_at: datetime | None = None) -> datetime:
        """
        Calculate expiry date for data based on retention policy.

        Args:
            data_type: Type of data (capsule, audit_log, session, etc.)
            created_at: Creation date (defaults to now)

        Returns:
            Datetime when data should expire
        """
        if created_at is None:
            created_at = datetime.now(UTC)

        retention_map = {
            "capsule": self._retention.capsule_retention_days,
            "audit_log": self._retention.audit_log_retention_days,
            "session": self._retention.session_retention_days,
            "export": self._retention.export_retention_days,
        }

        days = retention_map.get(data_type, self._retention.default_retention_days)
        return created_at + timedelta(days=days)

    def is_expired(self, data_type: str, created_at: datetime) -> bool:
        """Check if data has exceeded retention period."""
        expiry = self.calculate_expiry_date(data_type, created_at)
        return datetime.now(UTC) > expiry


# Global privacy manager instance
_privacy_manager: PrivacyManager | None = None


def get_privacy_manager() -> PrivacyManager:
    """Get or create the global privacy manager instance."""
    global _privacy_manager
    if _privacy_manager is None:
        _privacy_manager = PrivacyManager()
        _privacy_manager.initialize()
    return _privacy_manager
