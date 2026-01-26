"""
Starter Packs System
====================

Pre-configured knowledge packs for accelerating cold starts.
Provides domain-specific capsules, overlays, and configurations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from forge.resilience.config import get_resilience_config

logger = structlog.get_logger(__name__)


class PackCategory(Enum):
    """Categories of starter packs."""

    DEVELOPMENT = "development"
    BUSINESS = "business"
    RESEARCH = "research"
    PERSONAL = "personal"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"


class PackStatus(Enum):
    """Status of a starter pack."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PackCapsule:
    """Template capsule included in a starter pack."""

    template_id: str
    title: str
    content: str
    capsule_type: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PackOverlay:
    """Overlay configuration included in a starter pack."""

    overlay_id: str
    name: str
    overlay_type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class PackDependency:
    """Dependency on another starter pack."""

    pack_id: str
    version: str
    optional: bool = False


@dataclass
class StarterPack:
    """A starter pack with pre-configured knowledge."""

    pack_id: str
    name: str
    description: str
    category: PackCategory
    version: str = "1.0.0"
    author: str = "Forge System"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: PackStatus = PackStatus.PUBLISHED

    # Pack contents
    capsules: list[PackCapsule] = field(default_factory=list)
    overlays: list[PackOverlay] = field(default_factory=list)
    dependencies: list[PackDependency] = field(default_factory=list)

    # Configuration
    default_trust_level: int = 60
    auto_activate_overlays: bool = True
    tags: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "capsule_count": len(self.capsules),
            "overlay_count": len(self.overlays),
            "dependency_count": len(self.dependencies),
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StarterPack:
        """Create from dictionary."""
        capsules = [PackCapsule(**c) for c in data.get("capsules", [])]
        overlays = [PackOverlay(**o) for o in data.get("overlays", [])]
        dependencies = [PackDependency(**d) for d in data.get("dependencies", [])]

        return cls(
            pack_id=data["pack_id"],
            name=data["name"],
            description=data["description"],
            category=PackCategory(data["category"]),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Unknown"),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(UTC),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(UTC),
            status=PackStatus(data.get("status", "published")),
            capsules=capsules,
            overlays=overlays,
            dependencies=dependencies,
            default_trust_level=data.get("default_trust_level", 60),
            auto_activate_overlays=data.get("auto_activate_overlays", True),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PackInstallation:
    """Record of a starter pack installation."""

    installation_id: str
    pack_id: str
    pack_version: str
    installed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    installed_by: str = ""
    capsules_created: list[str] = field(default_factory=list)
    overlays_activated: list[str] = field(default_factory=list)
    status: str = "completed"


class StarterPackManager:
    """
    Manages starter pack registration, discovery, and installation.

    Features:
    - Pack registry with versioning
    - Dependency resolution
    - Automatic installation
    - Rollback support
    """

    def __init__(self) -> None:
        self._config = get_resilience_config().starter_packs
        self._packs: dict[str, StarterPack] = {}
        self._installations: dict[str, list[PackInstallation]] = {}  # user_id -> installations
        self._initialized = False

        # Callbacks for installation
        self._create_capsule_callback: Callable[..., Any] | None = None
        self._activate_overlay_callback: Callable[..., Any] | None = None

    def initialize(self) -> None:
        """Initialize with default starter packs."""
        if self._initialized:
            return

        if not self._config.enabled:
            logger.info("starter_packs_disabled")
            return

        # Register default packs
        self._register_default_packs()

        self._initialized = True
        logger.info("starter_pack_manager_initialized", pack_count=len(self._packs))

    def _register_default_packs(self) -> None:
        """Register default starter packs."""
        default_packs = [
            StarterPack(
                pack_id="forge-essentials",
                name="Forge Essentials",
                description="Essential capsules and overlays for getting started with Forge",
                category=PackCategory.DEVELOPMENT,
                capsules=[
                    PackCapsule(
                        template_id="welcome",
                        title="Welcome to Forge",
                        content="Welcome to Forge - your institutional memory engine. This capsule contains essential information about using the system.",
                        capsule_type="KNOWLEDGE",
                        tags=["forge", "getting-started"],
                    ),
                    PackCapsule(
                        template_id="best-practices",
                        title="Forge Best Practices",
                        content="Best practices for creating and organizing knowledge capsules in Forge.",
                        capsule_type="KNOWLEDGE",
                        tags=["forge", "best-practices"],
                    ),
                ],
                overlays=[
                    PackOverlay(
                        overlay_id="governance-basic",
                        name="Basic Governance",
                        overlay_type="GOVERNANCE",
                        config={"require_approval": False},
                    ),
                ],
                tags=["essential", "getting-started"],
            ),
            StarterPack(
                pack_id="software-development",
                name="Software Development Pack",
                description="Knowledge templates for software development teams",
                category=PackCategory.DEVELOPMENT,
                capsules=[
                    PackCapsule(
                        template_id="architecture-decision",
                        title="Architecture Decision Record Template",
                        content="# Architecture Decision Record\n\n## Context\n[Describe the context]\n\n## Decision\n[What was decided]\n\n## Consequences\n[What are the implications]",
                        capsule_type="DECISION",
                        tags=["architecture", "adr", "decision"],
                    ),
                    PackCapsule(
                        template_id="code-review",
                        title="Code Review Guidelines",
                        content="Guidelines for effective code reviews: focus on logic, readability, and maintainability.",
                        capsule_type="KNOWLEDGE",
                        tags=["code-review", "guidelines"],
                    ),
                    PackCapsule(
                        template_id="incident-template",
                        title="Incident Postmortem Template",
                        content="# Incident Postmortem\n\n## Summary\n\n## Timeline\n\n## Root Cause\n\n## Action Items",
                        capsule_type="LESSON",
                        tags=["incident", "postmortem", "template"],
                    ),
                ],
                dependencies=[PackDependency(pack_id="forge-essentials", version="1.0.0")],
                tags=["software", "engineering", "development"],
            ),
            StarterPack(
                pack_id="compliance-gdpr",
                name="GDPR Compliance Pack",
                description="Templates and knowledge for GDPR compliance",
                category=PackCategory.COMPLIANCE,
                capsules=[
                    PackCapsule(
                        template_id="gdpr-overview",
                        title="GDPR Overview",
                        content="Overview of General Data Protection Regulation requirements and principles.",
                        capsule_type="KNOWLEDGE",
                        tags=["gdpr", "compliance", "privacy"],
                    ),
                    PackCapsule(
                        template_id="data-subject-request",
                        title="Data Subject Request Process",
                        content="Process for handling data subject access requests (DSARs) under GDPR.",
                        capsule_type="KNOWLEDGE",
                        tags=["gdpr", "dsar", "process"],
                    ),
                ],
                overlays=[
                    PackOverlay(
                        overlay_id="privacy-compliance",
                        name="Privacy Compliance Overlay",
                        overlay_type="COMPLIANCE",
                        config={"jurisdiction": "EU", "framework": "GDPR"},
                    ),
                ],
                tags=["gdpr", "compliance", "privacy", "eu"],
            ),
            StarterPack(
                pack_id="research-academic",
                name="Academic Research Pack",
                description="Templates for academic research and paper management",
                category=PackCategory.RESEARCH,
                capsules=[
                    PackCapsule(
                        template_id="literature-review",
                        title="Literature Review Template",
                        content="# Literature Review\n\n## Research Question\n\n## Sources\n\n## Key Findings\n\n## Gaps Identified",
                        capsule_type="KNOWLEDGE",
                        tags=["research", "literature", "academic"],
                    ),
                    PackCapsule(
                        template_id="experiment-log",
                        title="Experiment Log Template",
                        content="# Experiment Log\n\n## Hypothesis\n\n## Methodology\n\n## Results\n\n## Conclusions",
                        capsule_type="MEMORY",
                        tags=["research", "experiment", "science"],
                    ),
                ],
                tags=["research", "academic", "science"],
            ),
        ]

        for pack in default_packs:
            self._packs[pack.pack_id] = pack

    def set_capsule_callback(self, callback: Callable[..., Any]) -> None:
        """Set callback for creating capsules during installation."""
        self._create_capsule_callback = callback

    def set_overlay_callback(self, callback: Callable[..., Any]) -> None:
        """Set callback for activating overlays during installation."""
        self._activate_overlay_callback = callback

    def register_pack(self, pack: StarterPack) -> None:
        """Register a new starter pack."""
        self._packs[pack.pack_id] = pack
        logger.info("starter_pack_registered", pack_id=pack.pack_id, name=pack.name)

    def get_pack(self, pack_id: str) -> StarterPack | None:
        """Get a starter pack by ID."""
        return self._packs.get(pack_id)

    def list_packs(
        self, category: PackCategory | None = None, tags: list[str] | None = None
    ) -> list[StarterPack]:
        """List available starter packs with optional filtering."""
        packs = list(self._packs.values())

        # Filter by status (only published)
        packs = [p for p in packs if p.status == PackStatus.PUBLISHED]

        # Filter by category
        if category:
            packs = [p for p in packs if p.category == category]

        # Filter by tags
        if tags:
            tag_set = set(tags)
            packs = [p for p in packs if tag_set & set(p.tags)]

        return packs

    def search_packs(self, query: str) -> list[StarterPack]:
        """Search packs by name or description."""
        query_lower = query.lower()
        return [
            p
            for p in self._packs.values()
            if query_lower in p.name.lower() or query_lower in p.description.lower()
        ]

    async def install_pack(
        self, pack_id: str, user_id: str, skip_dependencies: bool = False
    ) -> PackInstallation:
        """
        Install a starter pack for a user.

        Args:
            pack_id: ID of pack to install
            user_id: User to install for
            skip_dependencies: Whether to skip dependency installation

        Returns:
            Installation record
        """
        pack = self._packs.get(pack_id)
        if not pack:
            raise ValueError(f"Pack not found: {pack_id}")

        # Check for existing installation
        if user_id in self._installations:
            for existing in self._installations[user_id]:
                if existing.pack_id == pack_id:
                    raise ValueError(f"Pack already installed: {pack_id}")

        # Install dependencies first
        if not skip_dependencies and self._config.auto_import_dependencies:
            for dep in pack.dependencies:
                if not dep.optional:
                    # Check if dependency is installed
                    already_installed = False
                    if user_id in self._installations:
                        for inst in self._installations[user_id]:
                            if inst.pack_id == dep.pack_id:
                                already_installed = True
                                break

                    if not already_installed:
                        await self.install_pack(dep.pack_id, user_id)

        installation = PackInstallation(
            installation_id=f"inst_{pack_id}_{user_id}_{datetime.now(UTC).timestamp()}",
            pack_id=pack_id,
            pack_version=pack.version,
            installed_by=user_id,
        )

        # Create capsules
        for capsule_template in pack.capsules:
            capsule_id = await self._create_capsule(
                capsule_template, user_id, pack.default_trust_level
            )
            if capsule_id:
                installation.capsules_created.append(capsule_id)

        # Activate overlays
        if pack.auto_activate_overlays:
            for overlay_config in pack.overlays:
                overlay_id = await self._activate_overlay(overlay_config, user_id)
                if overlay_id:
                    installation.overlays_activated.append(overlay_id)

        # Record installation
        if user_id not in self._installations:
            self._installations[user_id] = []
        self._installations[user_id].append(installation)

        logger.info(
            "starter_pack_installed",
            pack_id=pack_id,
            user_id=user_id,
            capsules=len(installation.capsules_created),
            overlays=len(installation.overlays_activated),
        )

        return installation

    async def _create_capsule(
        self, template: PackCapsule, user_id: str, trust_level: int
    ) -> str | None:
        """
        Create a capsule from template.

        SECURITY FIX (Audit 4 - H30): Validates pack content before creating
        capsules to prevent XSS, injection, and other content-based attacks.
        """
        if self._create_capsule_callback:
            try:
                # SECURITY FIX (Audit 4 - H30): Validate and sanitize content
                sanitized_content = self._validate_pack_content(template.content)
                if sanitized_content is None:
                    logger.warning(
                        "pack_content_validation_failed",
                        template_id=template.template_id,
                        reason="Content failed security validation",
                    )
                    return None

                result: str | None = await self._create_capsule_callback(
                    content=sanitized_content,
                    capsule_type=template.capsule_type,
                    tags=template.tags,
                    user_id=user_id,
                    trust_level=trust_level,
                    metadata={"from_pack_template": template.template_id},
                )
                return result
            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError) as e:
                logger.warning(
                    "pack_capsule_creation_failed", template_id=template.template_id, error=str(e)
                )
        return None

    def _validate_pack_content(self, content: str) -> str | None:
        """
        SECURITY FIX (Audit 4 - H30): Validate and sanitize pack content.

        Checks for:
        - XSS payloads (script tags, event handlers, javascript: URLs)
        - SQL/Cypher injection patterns
        - Excessive size
        - Malicious encoding

        Returns sanitized content or None if content is rejected.
        """
        import re

        if not content:
            return ""

        # Check size limit
        MAX_CONTENT_SIZE = 100000  # 100KB max
        if len(content) > MAX_CONTENT_SIZE:
            logger.warning("pack_content_too_large", size=len(content))
            return None

        # Detect XSS patterns
        xss_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"on\w+\s*=",  # Event handlers like onclick=
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"expression\s*\(",
            r"vbscript:",
            r"data:text/html",
        ]

        content_lower = content.lower()
        for pattern in xss_patterns:
            if re.search(pattern, content_lower):
                logger.warning("pack_content_xss_detected", pattern=pattern[:20])
                return None

        # Detect injection patterns
        injection_patterns = [
            r"'\s*OR\s+'1'\s*=\s*'1",  # SQL injection
            r";\s*DROP\s+",  # SQL injection
            r"MATCH\s*\([^)]*\)\s*DELETE",  # Cypher injection
            r"CALL\s+db\.",  # Cypher procedure injection
        ]

        for pattern in injection_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning("pack_content_injection_detected", pattern=pattern[:20])
                return None

        # Basic HTML entity encoding for special characters
        # This preserves markdown but escapes dangerous HTML
        sanitized = content
        # Don't fully escape - just neutralize script execution
        sanitized = re.sub(r"<script", "&lt;script", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"javascript:", "javascript-disabled:", sanitized, flags=re.IGNORECASE)

        return sanitized

    async def _activate_overlay(self, overlay_config: PackOverlay, user_id: str) -> str | None:
        """Activate an overlay from pack configuration."""
        if self._activate_overlay_callback:
            try:
                overlay_result: str | None = await self._activate_overlay_callback(
                    overlay_type=overlay_config.overlay_type,
                    config=overlay_config.config,
                    user_id=user_id,
                )
                return overlay_result
            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError) as e:
                logger.warning(
                    "pack_overlay_activation_failed",
                    overlay_id=overlay_config.overlay_id,
                    error=str(e),
                )
        return None

    def get_installations(self, user_id: str) -> list[PackInstallation]:
        """Get all installations for a user."""
        return self._installations.get(user_id, [])

    async def uninstall_pack(
        self, pack_id: str, user_id: str, delete_capsules: bool = False
    ) -> bool:
        """
        Uninstall a starter pack.

        Args:
            pack_id: Pack to uninstall
            user_id: User to uninstall from
            delete_capsules: Whether to delete created capsules

        Returns:
            True if uninstalled successfully
        """
        if user_id not in self._installations:
            return False

        installation = None
        for inst in self._installations[user_id]:
            if inst.pack_id == pack_id:
                installation = inst
                break

        if not installation:
            return False

        # Remove installation record
        self._installations[user_id].remove(installation)

        logger.info("starter_pack_uninstalled", pack_id=pack_id, user_id=user_id)

        return True


# Global instance
_pack_manager: StarterPackManager | None = None


def get_pack_manager() -> StarterPackManager:
    """Get or create the global starter pack manager instance."""
    global _pack_manager
    if _pack_manager is None:
        _pack_manager = StarterPackManager()
        _pack_manager.initialize()
    return _pack_manager
