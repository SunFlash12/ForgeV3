"""
Forge Compliance Framework - Accessibility Module

Implements accessibility requirements:
- WCAG 2.2 Level AA
- European Accessibility Act (EAA)
- EN 301 549
- Section 508 (US)
"""

from forge.compliance.accessibility.service import (
    VPAT,
    AccessibilityAudit,
    AccessibilityComplianceService,
    AccessibilityIssue,
    AccessibilityStandard,
    IssueImpact,
    VPATEntry,
    WCAGCriterion,
    WCAGLevel,
    WCAGPrinciple,
    get_accessibility_service,
)

__all__ = [
    "AccessibilityComplianceService",
    "get_accessibility_service",
    "WCAGLevel",
    "WCAGPrinciple",
    "AccessibilityStandard",
    "IssueImpact",
    "WCAGCriterion",
    "AccessibilityIssue",
    "AccessibilityAudit",
    "VPATEntry",
    "VPAT",
]
