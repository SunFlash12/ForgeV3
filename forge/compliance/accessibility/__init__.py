"""
Forge Compliance Framework - Accessibility Module

Implements accessibility requirements:
- WCAG 2.2 Level AA
- European Accessibility Act (EAA)
- EN 301 549
- Section 508 (US)
"""

from forge.compliance.accessibility.service import (
    AccessibilityComplianceService,
    get_accessibility_service,
    WCAGLevel,
    WCAGPrinciple,
    AccessibilityStandard,
    IssueImpact,
    WCAGCriterion,
    AccessibilityIssue,
    AccessibilityAudit,
    VPATEntry,
    VPAT,
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
