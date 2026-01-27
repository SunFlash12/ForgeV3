"""
Forge Compliance Framework - Accessibility Compliance

Implements accessibility requirements per:
- WCAG 2.2 Level AA
- European Accessibility Act (EAA)
- EN 301 549
- Section 508 (US)
- ADA Title III

Provides:
- Automated accessibility testing
- VPAT generation
- Accessibility statement generation
- Issue tracking and remediation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class WCAGLevel(str, Enum):
    """WCAG conformance levels."""

    A = "A"
    AA = "AA"
    AAA = "AAA"


class WCAGPrinciple(str, Enum):
    """WCAG POUR principles."""

    PERCEIVABLE = "perceivable"
    OPERABLE = "operable"
    UNDERSTANDABLE = "understandable"
    ROBUST = "robust"


class AccessibilityStandard(str, Enum):
    """Accessibility standards."""

    WCAG_21 = "wcag_2_1"
    WCAG_22 = "wcag_2_2"
    EN_301_549 = "en_301_549"
    SECTION_508 = "section_508"
    EAA = "european_accessibility_act"


class IssueImpact(str, Enum):
    """Accessibility issue impact levels."""

    CRITICAL = "critical"  # Blocks access entirely
    SERIOUS = "serious"  # Significantly impacts
    MODERATE = "moderate"  # Some impact
    MINOR = "minor"  # Minimal impact


@dataclass
class WCAGCriterion:
    """WCAG success criterion definition."""

    criterion_id: str  # e.g., "1.1.1"
    name: str
    level: WCAGLevel
    principle: WCAGPrinciple
    description: str
    techniques: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class AccessibilityIssue:
    """Accessibility issue found during testing."""

    issue_id: str = field(default_factory=lambda: str(uuid4()))

    # Location
    url: str = ""
    component: str = ""
    element_selector: str = ""

    # Classification
    criterion_id: str = ""
    standard: AccessibilityStandard = AccessibilityStandard.WCAG_22
    impact: IssueImpact = IssueImpact.MODERATE

    # Details
    description: str = ""
    remediation: str = ""
    code_snippet: str = ""

    # Status
    status: str = "open"  # open, in_progress, resolved, wont_fix
    found_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    # Testing
    test_method: str = ""  # automated, manual, user_testing
    tester: str = ""


@dataclass
class AccessibilityAudit:
    """Accessibility audit results."""

    audit_id: str = field(default_factory=lambda: str(uuid4()))

    # Scope
    audit_name: str = ""
    target_url: str = ""
    standard: AccessibilityStandard = AccessibilityStandard.WCAG_22
    target_level: WCAGLevel = WCAGLevel.AA

    # Metadata
    audited_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    auditor: str = ""
    methodology: str = ""

    # Results
    pages_tested: int = 0
    issues_found: int = 0
    issues_critical: int = 0
    issues_serious: int = 0
    issues_moderate: int = 0
    issues_minor: int = 0

    # Conformance
    conformance_level: WCAGLevel | None = None
    partial_conformance: bool = False

    # Issues
    issues: list[AccessibilityIssue] = field(default_factory=list)


@dataclass
class VPATEntry:
    """VPAT (Voluntary Product Accessibility Template) entry."""

    criterion: str
    conformance_level: str  # Supports, Partially Supports, Does Not Support, Not Applicable
    remarks: str


@dataclass
class VPAT:
    """VPAT document for product accessibility."""

    vpat_id: str = field(default_factory=lambda: str(uuid4()))

    # Product info
    product_name: str = ""
    product_version: str = ""
    vendor_name: str = ""

    # Document info
    report_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    standard: AccessibilityStandard = AccessibilityStandard.WCAG_22
    target_level: WCAGLevel = WCAGLevel.AA

    # Evaluation
    evaluation_methods: list[str] = field(default_factory=list)

    # Entries
    entries: list[VPATEntry] = field(default_factory=list)

    # Summary
    notes: str = ""


class AccessibilityComplianceService:
    """
    Accessibility compliance service.

    Manages accessibility testing, issue tracking, and documentation
    for WCAG 2.2, EAA, and Section 508 compliance.
    """

    def __init__(self):
        self._criteria = self._initialize_wcag_criteria()
        self._audits: dict[str, AccessibilityAudit] = {}
        self._issues: dict[str, AccessibilityIssue] = {}
        self._vpats: dict[str, VPAT] = {}

    def _initialize_wcag_criteria(self) -> dict[str, WCAGCriterion]:
        """Initialize WCAG 2.2 success criteria."""
        criteria = {
            # Principle 1: Perceivable
            "1.1.1": WCAGCriterion(
                criterion_id="1.1.1",
                name="Non-text Content",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="All non-text content has a text alternative",
                techniques=["G94", "G95", "H37"],
                failures=["F3", "F20", "F30"],
            ),
            "1.2.1": WCAGCriterion(
                criterion_id="1.2.1",
                name="Audio-only and Video-only",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Alternatives for time-based media",
            ),
            "1.2.2": WCAGCriterion(
                criterion_id="1.2.2",
                name="Captions (Prerecorded)",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Captions for prerecorded audio content",
            ),
            "1.3.1": WCAGCriterion(
                criterion_id="1.3.1",
                name="Info and Relationships",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Information structure is programmatically determinable",
            ),
            "1.4.1": WCAGCriterion(
                criterion_id="1.4.1",
                name="Use of Color",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Color is not the only visual means of conveying information",
            ),
            "1.4.3": WCAGCriterion(
                criterion_id="1.4.3",
                name="Contrast (Minimum)",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Text has contrast ratio of at least 4.5:1",
            ),
            "1.4.4": WCAGCriterion(
                criterion_id="1.4.4",
                name="Resize Text",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="Text can be resized up to 200% without loss",
            ),
            "1.4.11": WCAGCriterion(
                criterion_id="1.4.11",
                name="Non-text Contrast",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.PERCEIVABLE,
                description="UI components have 3:1 contrast ratio",
            ),
            # Principle 2: Operable
            "2.1.1": WCAGCriterion(
                criterion_id="2.1.1",
                name="Keyboard",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="All functionality available from keyboard",
            ),
            "2.1.2": WCAGCriterion(
                criterion_id="2.1.2",
                name="No Keyboard Trap",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="Focus can be moved away using keyboard",
            ),
            "2.4.1": WCAGCriterion(
                criterion_id="2.4.1",
                name="Bypass Blocks",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="Mechanism to bypass repeated content",
            ),
            "2.4.2": WCAGCriterion(
                criterion_id="2.4.2",
                name="Page Titled",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="Web pages have descriptive titles",
            ),
            "2.4.3": WCAGCriterion(
                criterion_id="2.4.3",
                name="Focus Order",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="Focus order preserves meaning",
            ),
            "2.4.7": WCAGCriterion(
                criterion_id="2.4.7",
                name="Focus Visible",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.OPERABLE,
                description="Keyboard focus indicator is visible",
            ),
            "2.5.3": WCAGCriterion(
                criterion_id="2.5.3",
                name="Label in Name",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.OPERABLE,
                description="Visible label is part of accessible name",
            ),
            # WCAG 2.2 New criteria
            "2.4.11": WCAGCriterion(
                criterion_id="2.4.11",
                name="Focus Not Obscured (Minimum)",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.OPERABLE,
                description="Focused component is not entirely hidden",
            ),
            "2.5.7": WCAGCriterion(
                criterion_id="2.5.7",
                name="Dragging Movements",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.OPERABLE,
                description="Drag operations have single-pointer alternative",
            ),
            "2.5.8": WCAGCriterion(
                criterion_id="2.5.8",
                name="Target Size (Minimum)",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.OPERABLE,
                description="Target size is at least 24x24 CSS pixels",
            ),
            # Principle 3: Understandable
            "3.1.1": WCAGCriterion(
                criterion_id="3.1.1",
                name="Language of Page",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Default language is programmatically determinable",
            ),
            "3.2.1": WCAGCriterion(
                criterion_id="3.2.1",
                name="On Focus",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Focus does not cause unexpected context change",
            ),
            "3.2.2": WCAGCriterion(
                criterion_id="3.2.2",
                name="On Input",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Input does not cause unexpected context change",
            ),
            "3.3.1": WCAGCriterion(
                criterion_id="3.3.1",
                name="Error Identification",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Input errors are identified and described",
            ),
            "3.3.2": WCAGCriterion(
                criterion_id="3.3.2",
                name="Labels or Instructions",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Labels or instructions are provided for input",
            ),
            "3.3.7": WCAGCriterion(
                criterion_id="3.3.7",
                name="Redundant Entry",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="Previously entered info is auto-populated or selectable",
            ),
            "3.3.8": WCAGCriterion(
                criterion_id="3.3.8",
                name="Accessible Authentication (Minimum)",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.UNDERSTANDABLE,
                description="No cognitive function test required for authentication",
            ),
            # Principle 4: Robust
            "4.1.2": WCAGCriterion(
                criterion_id="4.1.2",
                name="Name, Role, Value",
                level=WCAGLevel.A,
                principle=WCAGPrinciple.ROBUST,
                description="UI components have programmatically determinable name/role",
            ),
            "4.1.3": WCAGCriterion(
                criterion_id="4.1.3",
                name="Status Messages",
                level=WCAGLevel.AA,
                principle=WCAGPrinciple.ROBUST,
                description="Status messages can be presented via assistive technology",
            ),
        }

        return criteria

    async def create_audit(
        self,
        audit_name: str,
        target_url: str,
        standard: AccessibilityStandard = AccessibilityStandard.WCAG_22,
        target_level: WCAGLevel = WCAGLevel.AA,
        auditor: str = "",
    ) -> AccessibilityAudit:
        """Create a new accessibility audit."""
        audit = AccessibilityAudit(
            audit_name=audit_name,
            target_url=target_url,
            standard=standard,
            target_level=target_level,
            auditor=auditor,
        )

        self._audits[audit.audit_id] = audit

        logger.info(
            "accessibility_audit_created",
            audit_id=audit.audit_id,
            target_url=target_url,
        )

        return audit

    async def log_issue(
        self,
        audit_id: str,
        url: str,
        criterion_id: str,
        impact: IssueImpact,
        description: str,
        remediation: str,
        element_selector: str = "",
        component: str = "",
        test_method: str = "automated",
        tester: str = "",
    ) -> AccessibilityIssue:
        """Log an accessibility issue found during audit."""
        audit = self._audits.get(audit_id)
        if not audit:
            raise ValueError(f"Audit not found: {audit_id}")

        issue = AccessibilityIssue(
            url=url,
            component=component,
            element_selector=element_selector,
            criterion_id=criterion_id,
            standard=audit.standard,
            impact=impact,
            description=description,
            remediation=remediation,
            test_method=test_method,
            tester=tester,
        )

        self._issues[issue.issue_id] = issue
        audit.issues.append(issue)

        # Update audit counts
        audit.issues_found += 1
        if impact == IssueImpact.CRITICAL:
            audit.issues_critical += 1
        elif impact == IssueImpact.SERIOUS:
            audit.issues_serious += 1
        elif impact == IssueImpact.MODERATE:
            audit.issues_moderate += 1
        else:
            audit.issues_minor += 1

        logger.info(
            "accessibility_issue_logged",
            issue_id=issue.issue_id,
            criterion=criterion_id,
            impact=impact.value,
        )

        return issue

    async def resolve_issue(
        self,
        issue_id: str,
        resolution_notes: str = "",
    ) -> AccessibilityIssue:
        """Mark an accessibility issue as resolved."""
        issue = self._issues.get(issue_id)
        if not issue:
            raise ValueError(f"Issue not found: {issue_id}")

        issue.status = "resolved"
        issue.resolved_at = datetime.now(UTC)

        logger.info(
            "accessibility_issue_resolved",
            issue_id=issue_id,
        )

        return issue

    def determine_conformance(
        self,
        audit_id: str,
    ) -> tuple[WCAGLevel | None, bool]:
        """
        Determine WCAG conformance level for an audit.

        Returns (conformance_level, is_partial).
        """
        audit = self._audits.get(audit_id)
        if not audit:
            return None, False

        open_issues = [i for i in audit.issues if i.status == "open"]

        # Check Level A issues
        level_a_criteria = {
            c.criterion_id for c in self._criteria.values() if c.level == WCAGLevel.A
        }
        level_a_failures = {
            i.criterion_id for i in open_issues if i.criterion_id in level_a_criteria
        }

        if level_a_failures:
            # Does not conform to Level A
            return None, True

        # Check Level AA issues
        level_aa_criteria = {
            c.criterion_id
            for c in self._criteria.values()
            if c.level in {WCAGLevel.A, WCAGLevel.AA}
        }
        level_aa_failures = {
            i.criterion_id for i in open_issues if i.criterion_id in level_aa_criteria
        }

        if not level_aa_failures:
            return WCAGLevel.AA, False
        elif not level_a_failures:
            return WCAGLevel.A, True

        return None, True

    async def generate_vpat(
        self,
        product_name: str,
        product_version: str,
        vendor_name: str,
        audit_id: str | None = None,
        standard: AccessibilityStandard = AccessibilityStandard.WCAG_22,
        target_level: WCAGLevel = WCAGLevel.AA,
    ) -> VPAT:
        """
        Generate a VPAT document.

        Per Section 508/EN 301 549 requirements.
        """
        vpat = VPAT(
            product_name=product_name,
            product_version=product_version,
            vendor_name=vendor_name,
            standard=standard,
            target_level=target_level,
            evaluation_methods=["Automated testing", "Manual testing", "Screen reader testing"],
        )

        # Get issues from audit if provided
        issue_criteria = set()
        if audit_id:
            audit = self._audits.get(audit_id)
            if audit:
                issue_criteria = {i.criterion_id for i in audit.issues if i.status == "open"}

        # Generate entries for relevant criteria
        criteria_for_level = {
            c
            for c in self._criteria.values()
            if (target_level == WCAGLevel.A and c.level == WCAGLevel.A)
            or (target_level == WCAGLevel.AA and c.level in {WCAGLevel.A, WCAGLevel.AA})
            or (target_level == WCAGLevel.AAA)
        }

        for criterion in sorted(criteria_for_level, key=lambda c: c.criterion_id):
            if criterion.criterion_id in issue_criteria:
                conformance = "Does Not Support"
                remarks = "Issues identified during testing"
            else:
                conformance = "Supports"
                remarks = "No issues identified"

            vpat.entries.append(
                VPATEntry(
                    criterion=f"{criterion.criterion_id} {criterion.name}",
                    conformance_level=conformance,
                    remarks=remarks,
                )
            )

        self._vpats[vpat.vpat_id] = vpat

        logger.info(
            "vpat_generated",
            vpat_id=vpat.vpat_id,
            product=product_name,
        )

        return vpat

    def generate_accessibility_statement(
        self,
        organization_name: str,
        website_url: str,
        conformance_level: WCAGLevel,
        standard: AccessibilityStandard,
        known_issues: list[str] | None = None,
        contact_email: str = "",
    ) -> str:
        """
        Generate an accessibility statement.

        Per EAA/WCAG requirements.
        """
        known_issues = known_issues or []

        statement = f"""
# Accessibility Statement for {organization_name}

**Website:** {website_url}
**Standard:** {standard.value.replace("_", " ").upper()}
**Conformance Level:** {conformance_level.value}
**Statement Date:** {datetime.now(UTC).strftime("%Y-%m-%d")}

## Our Commitment

{organization_name} is committed to ensuring digital accessibility for people with
disabilities. We are continually improving the user experience for everyone and
applying the relevant accessibility standards.

## Conformance Status

This website conforms to {standard.value.replace("_", " ").upper()} Level {conformance_level.value}.

## Known Accessibility Issues

"""

        if known_issues:
            for issue in known_issues:
                statement += f"- {issue}\n"
        else:
            statement += "No known issues at this time.\n"

        statement += f"""
## Feedback

We welcome your feedback on the accessibility of this website.
Please contact us at: {contact_email}

## Enforcement Procedure

In case of unsatisfactory response, you may contact the relevant
regulatory authority in your jurisdiction.

## Technical Specifications

This website relies on the following technologies to work with the
particular combination of web browser and any assistive technologies
or plugins installed on your computer:

- HTML5
- WAI-ARIA
- CSS
- JavaScript

These technologies are relied upon for conformance with the accessibility
standards used.

## Limitations

Despite our best efforts to ensure accessibility, there may be some
limitations. Please contact us if you encounter issues.

---
*This statement was last updated on {datetime.now(UTC).strftime("%Y-%m-%d")}.*
"""

        return statement

    def get_compliance_summary(
        self,
        target_level: WCAGLevel = WCAGLevel.AA,
    ) -> dict[str, Any]:
        """Get accessibility compliance summary."""
        all_issues = list(self._issues.values())
        open_issues = [i for i in all_issues if i.status == "open"]

        return {
            "target_level": target_level.value,
            "total_issues": len(all_issues),
            "open_issues": len(open_issues),
            "resolved_issues": len([i for i in all_issues if i.status == "resolved"]),
            "issues_by_impact": {
                "critical": len([i for i in open_issues if i.impact == IssueImpact.CRITICAL]),
                "serious": len([i for i in open_issues if i.impact == IssueImpact.SERIOUS]),
                "moderate": len([i for i in open_issues if i.impact == IssueImpact.MODERATE]),
                "minor": len([i for i in open_issues if i.impact == IssueImpact.MINOR]),
            },
            "issues_by_principle": {
                "perceivable": len([i for i in open_issues if i.criterion_id.startswith("1.")]),
                "operable": len([i for i in open_issues if i.criterion_id.startswith("2.")]),
                "understandable": len([i for i in open_issues if i.criterion_id.startswith("3.")]),
                "robust": len([i for i in open_issues if i.criterion_id.startswith("4.")]),
            },
            "audits_completed": len(self._audits),
            "vpats_generated": len(self._vpats),
        }


# Global service instance
_accessibility_service: AccessibilityComplianceService | None = None


def get_accessibility_service() -> AccessibilityComplianceService:
    """Get the global accessibility compliance service."""
    global _accessibility_service
    if _accessibility_service is None:
        _accessibility_service = AccessibilityComplianceService()
    return _accessibility_service
