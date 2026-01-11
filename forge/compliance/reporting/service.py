"""
Forge Compliance Framework - Reporting Service

Automated compliance report generation:
- Executive summaries
- Framework-specific reports (SOC 2, ISO 27001, GDPR)
- Gap analysis
- Control evidence collection
- Audit-ready documentation

Supports formats: PDF, HTML, JSON, Excel
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import (
    ComplianceFramework,
    Jurisdiction,
    RiskLevel,
)
from forge.compliance.core.models import ComplianceReport

logger = structlog.get_logger(__name__)


class ReportType(str, Enum):
    """Types of compliance reports."""
    EXECUTIVE_SUMMARY = "executive_summary"
    FULL_ASSESSMENT = "full_assessment"
    GAP_ANALYSIS = "gap_analysis"
    CONTROL_EVIDENCE = "control_evidence"
    AUDIT_READINESS = "audit_readiness"
    DSAR_SUMMARY = "dsar_summary"
    BREACH_SUMMARY = "breach_summary"
    AI_GOVERNANCE = "ai_governance"
    PRIVACY_IMPACT = "privacy_impact"
    VENDOR_DUE_DILIGENCE = "vendor_due_diligence"


class ReportFormat(str, Enum):
    """Output formats for reports."""
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    EXCEL = "excel"
    MARKDOWN = "markdown"


@dataclass
class ReportSection:
    """Section of a compliance report."""
    section_id: str
    title: str
    order: int
    content: dict[str, Any]
    charts: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class ReportTemplate:
    """Template for compliance reports."""
    template_id: str
    name: str
    report_type: ReportType
    framework: ComplianceFramework | None
    sections: list[str]
    required_data: list[str]
    output_formats: list[ReportFormat]


@dataclass
class GeneratedReport:
    """Generated compliance report."""
    report_id: str = field(default_factory=lambda: str(uuid4()))
    report_type: ReportType = ReportType.FULL_ASSESSMENT
    title: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    generated_by: str = ""
    
    # Scope
    frameworks: list[ComplianceFramework] = field(default_factory=list)
    jurisdictions: list[Jurisdiction] = field(default_factory=list)
    period_start: datetime | None = None
    period_end: datetime | None = None
    
    # Content
    executive_summary: str = ""
    sections: list[ReportSection] = field(default_factory=list)
    
    # Metrics
    overall_score: float = 0.0
    total_controls: int = 0
    compliant_controls: int = 0
    gaps_critical: int = 0
    gaps_high: int = 0
    gaps_medium: int = 0
    gaps_low: int = 0
    
    # Status
    status: str = "draft"  # draft, final, archived
    approved_by: str | None = None
    approved_at: datetime | None = None


class ComplianceReportingService:
    """
    Automated compliance reporting service.
    
    Generates comprehensive compliance reports for various frameworks
    and regulatory requirements.
    """
    
    def __init__(self):
        self._templates = self._initialize_templates()
        self._generated_reports: dict[str, GeneratedReport] = {}
    
    def _initialize_templates(self) -> dict[str, ReportTemplate]:
        """Initialize report templates."""
        return {
            "soc2_type2": ReportTemplate(
                template_id="soc2_type2",
                name="SOC 2 Type II Report",
                report_type=ReportType.FULL_ASSESSMENT,
                framework=ComplianceFramework.SOC2,
                sections=[
                    "independent_opinion",
                    "management_assertion",
                    "system_description",
                    "trust_services_criteria",
                    "control_activities",
                    "tests_of_controls",
                    "results_of_tests",
                ],
                required_data=[
                    "control_status",
                    "audit_evidence",
                    "test_results",
                    "exceptions",
                ],
                output_formats=[ReportFormat.PDF, ReportFormat.HTML],
            ),
            "iso27001_soa": ReportTemplate(
                template_id="iso27001_soa",
                name="ISO 27001 Statement of Applicability",
                report_type=ReportType.FULL_ASSESSMENT,
                framework=ComplianceFramework.ISO27001,
                sections=[
                    "scope",
                    "risk_assessment",
                    "control_objectives",
                    "control_implementation",
                    "justification",
                ],
                required_data=[
                    "control_status",
                    "risk_assessment",
                    "exclusions",
                ],
                output_formats=[ReportFormat.PDF, ReportFormat.EXCEL],
            ),
            "gdpr_ropa": ReportTemplate(
                template_id="gdpr_ropa",
                name="GDPR Records of Processing Activities",
                report_type=ReportType.FULL_ASSESSMENT,
                framework=ComplianceFramework.GDPR,
                sections=[
                    "controller_details",
                    "processing_activities",
                    "legal_bases",
                    "data_categories",
                    "recipients",
                    "transfers",
                    "retention",
                    "security_measures",
                ],
                required_data=[
                    "processing_activities",
                    "data_flows",
                    "retention_policies",
                ],
                output_formats=[ReportFormat.PDF, ReportFormat.EXCEL, ReportFormat.JSON],
            ),
            "executive_summary": ReportTemplate(
                template_id="executive_summary",
                name="Executive Compliance Summary",
                report_type=ReportType.EXECUTIVE_SUMMARY,
                framework=None,
                sections=[
                    "overall_status",
                    "key_metrics",
                    "critical_gaps",
                    "upcoming_deadlines",
                    "recommendations",
                ],
                required_data=[
                    "control_status",
                    "dsar_metrics",
                    "breach_metrics",
                ],
                output_formats=[ReportFormat.PDF, ReportFormat.HTML],
            ),
            "gap_analysis": ReportTemplate(
                template_id="gap_analysis",
                name="Compliance Gap Analysis",
                report_type=ReportType.GAP_ANALYSIS,
                framework=None,
                sections=[
                    "methodology",
                    "current_state",
                    "target_state",
                    "gap_identification",
                    "risk_assessment",
                    "remediation_plan",
                    "resource_requirements",
                ],
                required_data=[
                    "control_status",
                    "target_framework",
                ],
                output_formats=[ReportFormat.PDF, ReportFormat.EXCEL],
            ),
        }
    
    async def generate_report(
        self,
        report_type: ReportType,
        frameworks: list[ComplianceFramework] | None = None,
        jurisdictions: list[Jurisdiction] | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        generated_by: str = "system",
        data_sources: dict[str, Any] | None = None,
    ) -> GeneratedReport:
        """
        Generate a compliance report.
        
        Args:
            report_type: Type of report to generate
            frameworks: Frameworks to include (None = all active)
            jurisdictions: Jurisdictions to include (None = all active)
            period_start: Reporting period start
            period_end: Reporting period end
            generated_by: User/system generating the report
            data_sources: Additional data sources for the report
        
        Returns:
            Generated report
        """
        report = GeneratedReport(
            report_type=report_type,
            generated_by=generated_by,
            frameworks=frameworks or [],
            jurisdictions=jurisdictions or [],
            period_start=period_start or (datetime.now(UTC) - timedelta(days=365)),
            period_end=period_end or datetime.now(UTC),
        )
        
        # Set title based on type
        report.title = self._generate_title(report_type, frameworks)
        
        # Generate sections based on report type
        if report_type == ReportType.EXECUTIVE_SUMMARY:
            report = await self._generate_executive_summary(report, data_sources)
        elif report_type == ReportType.FULL_ASSESSMENT:
            report = await self._generate_full_assessment(report, data_sources)
        elif report_type == ReportType.GAP_ANALYSIS:
            report = await self._generate_gap_analysis(report, data_sources)
        elif report_type == ReportType.DSAR_SUMMARY:
            report = await self._generate_dsar_summary(report, data_sources)
        elif report_type == ReportType.AI_GOVERNANCE:
            report = await self._generate_ai_governance_report(report, data_sources)
        
        # Store report
        self._generated_reports[report.report_id] = report
        
        logger.info(
            "compliance_report_generated",
            report_id=report.report_id,
            report_type=report_type.value,
        )
        
        return report
    
    def _generate_title(
        self,
        report_type: ReportType,
        frameworks: list[ComplianceFramework] | None,
    ) -> str:
        """Generate report title."""
        type_titles = {
            ReportType.EXECUTIVE_SUMMARY: "Executive Compliance Summary",
            ReportType.FULL_ASSESSMENT: "Compliance Assessment Report",
            ReportType.GAP_ANALYSIS: "Compliance Gap Analysis",
            ReportType.CONTROL_EVIDENCE: "Control Evidence Package",
            ReportType.AUDIT_READINESS: "Audit Readiness Assessment",
            ReportType.DSAR_SUMMARY: "Data Subject Rights Summary",
            ReportType.BREACH_SUMMARY: "Security Incident Summary",
            ReportType.AI_GOVERNANCE: "AI Governance Report",
            ReportType.PRIVACY_IMPACT: "Privacy Impact Assessment",
            ReportType.VENDOR_DUE_DILIGENCE: "Vendor Due Diligence Report",
        }
        
        title = type_titles.get(report_type, "Compliance Report")
        
        if frameworks and len(frameworks) == 1:
            title = f"{frameworks[0].value.upper()} {title}"
        
        return title
    
    async def _generate_executive_summary(
        self,
        report: GeneratedReport,
        data_sources: dict[str, Any] | None,
    ) -> GeneratedReport:
        """Generate executive summary report."""
        data = data_sources or {}
        
        # Overall status section
        overall_section = ReportSection(
            section_id="overall_status",
            title="Overall Compliance Status",
            order=1,
            content={
                "compliance_score": data.get("overall_score", 0),
                "status": self._score_to_status(data.get("overall_score", 0)),
                "trend": data.get("trend", "stable"),
            },
            charts=[
                {
                    "type": "gauge",
                    "title": "Overall Compliance Score",
                    "value": data.get("overall_score", 0),
                },
            ],
        )
        
        # Key metrics section
        metrics_section = ReportSection(
            section_id="key_metrics",
            title="Key Compliance Metrics",
            order=2,
            content={
                "total_controls": data.get("total_controls", 0),
                "compliant_controls": data.get("compliant_controls", 0),
                "dsars_received": data.get("dsars_received", 0),
                "dsars_completed": data.get("dsars_completed", 0),
                "breaches_ytd": data.get("breaches_ytd", 0),
                "ai_systems_registered": data.get("ai_systems", 0),
            },
            tables=[
                {
                    "title": "Control Status by Framework",
                    "headers": ["Framework", "Total", "Compliant", "Gaps", "Score"],
                    "rows": data.get("framework_status", []),
                },
            ],
        )
        
        # Critical gaps section
        gaps_section = ReportSection(
            section_id="critical_gaps",
            title="Critical Compliance Gaps",
            order=3,
            content={},
            findings=data.get("critical_gaps", []),
            recommendations=[
                "Address critical gaps within 30 days",
                "Assign remediation owners",
                "Implement compensating controls",
            ],
        )
        
        # Deadlines section
        deadlines_section = ReportSection(
            section_id="upcoming_deadlines",
            title="Upcoming Compliance Deadlines",
            order=4,
            content={},
            tables=[
                {
                    "title": "Regulatory Deadlines",
                    "headers": ["Deadline", "Regulation", "Requirement", "Status"],
                    "rows": data.get("deadlines", []),
                },
            ],
        )
        
        report.sections = [
            overall_section,
            metrics_section,
            gaps_section,
            deadlines_section,
        ]
        
        # Calculate metrics
        report.overall_score = data.get("overall_score", 0)
        report.total_controls = data.get("total_controls", 0)
        report.compliant_controls = data.get("compliant_controls", 0)
        report.gaps_critical = len([g for g in data.get("critical_gaps", []) if g.get("risk") == "critical"])
        report.gaps_high = len([g for g in data.get("critical_gaps", []) if g.get("risk") == "high"])
        
        # Generate executive summary text
        report.executive_summary = self._generate_executive_text(report)
        
        return report
    
    async def _generate_full_assessment(
        self,
        report: GeneratedReport,
        data_sources: dict[str, Any] | None,
    ) -> GeneratedReport:
        """Generate full compliance assessment report."""
        data = data_sources or {}
        
        # Methodology section
        methodology = ReportSection(
            section_id="methodology",
            title="Assessment Methodology",
            order=1,
            content={
                "approach": "Control-based assessment with automated verification",
                "scope": f"{len(report.frameworks)} frameworks, {len(report.jurisdictions)} jurisdictions",
                "period": f"{report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}",
            },
        )
        
        # Control assessment sections (one per framework)
        control_sections = []
        for i, framework in enumerate(report.frameworks):
            section = ReportSection(
                section_id=f"controls_{framework.value}",
                title=f"{framework.value.upper()} Control Assessment",
                order=10 + i,
                content={
                    "framework": framework.value,
                    "total_controls": data.get(f"{framework.value}_total", 0),
                    "implemented": data.get(f"{framework.value}_implemented", 0),
                    "verified": data.get(f"{framework.value}_verified", 0),
                },
                tables=[
                    {
                        "title": f"{framework.value.upper()} Control Status",
                        "headers": ["Control ID", "Description", "Status", "Evidence", "Last Verified"],
                        "rows": data.get(f"{framework.value}_controls", []),
                    },
                ],
                findings=data.get(f"{framework.value}_findings", []),
            )
            control_sections.append(section)
        
        # Risk assessment section
        risk_section = ReportSection(
            section_id="risk_assessment",
            title="Risk Assessment",
            order=100,
            content={
                "risk_level": data.get("overall_risk", "medium"),
                "risk_factors": data.get("risk_factors", []),
            },
            charts=[
                {
                    "type": "heatmap",
                    "title": "Risk Heat Map",
                    "data": data.get("risk_heatmap", {}),
                },
            ],
        )
        
        # Recommendations section
        recommendations_section = ReportSection(
            section_id="recommendations",
            title="Recommendations",
            order=200,
            content={},
            recommendations=data.get("recommendations", [
                "Implement automated control monitoring",
                "Conduct quarterly access reviews",
                "Enhance encryption key management",
                "Update incident response procedures",
            ]),
        )
        
        report.sections = [methodology] + control_sections + [risk_section, recommendations_section]
        
        return report
    
    async def _generate_gap_analysis(
        self,
        report: GeneratedReport,
        data_sources: dict[str, Any] | None,
    ) -> GeneratedReport:
        """Generate compliance gap analysis report."""
        data = data_sources or {}
        
        # Current state
        current_state = ReportSection(
            section_id="current_state",
            title="Current Compliance State",
            order=1,
            content={
                "implemented_controls": data.get("implemented_controls", 0),
                "verified_controls": data.get("verified_controls", 0),
                "automation_level": data.get("automation_level", "low"),
            },
        )
        
        # Target state
        target_state = ReportSection(
            section_id="target_state",
            title="Target Compliance State",
            order=2,
            content={
                "target_frameworks": [f.value for f in report.frameworks],
                "required_controls": data.get("required_controls", 0),
                "target_automation": "high",
            },
        )
        
        # Gap identification
        gap_section = ReportSection(
            section_id="gaps",
            title="Identified Gaps",
            order=3,
            content={},
            tables=[
                {
                    "title": "Compliance Gaps by Priority",
                    "headers": ["Gap ID", "Control", "Framework", "Risk", "Effort", "Priority"],
                    "rows": data.get("gaps", []),
                },
            ],
            findings=[
                {
                    "id": f"GAP-{i+1}",
                    "description": gap.get("description", ""),
                    "risk_level": gap.get("risk", "medium"),
                    "remediation": gap.get("remediation", ""),
                }
                for i, gap in enumerate(data.get("gaps", []))
            ],
        )
        
        # Remediation plan
        remediation = ReportSection(
            section_id="remediation",
            title="Remediation Plan",
            order=4,
            content={
                "total_gaps": len(data.get("gaps", [])),
                "estimated_effort_days": data.get("effort_days", 0),
                "target_completion": data.get("target_date", ""),
            },
            tables=[
                {
                    "title": "Remediation Timeline",
                    "headers": ["Phase", "Start", "End", "Gaps Addressed", "Resources"],
                    "rows": data.get("remediation_phases", []),
                },
            ],
        )
        
        report.sections = [current_state, target_state, gap_section, remediation]
        report.gaps_critical = len([g for g in data.get("gaps", []) if g.get("risk") == "critical"])
        report.gaps_high = len([g for g in data.get("gaps", []) if g.get("risk") == "high"])
        report.gaps_medium = len([g for g in data.get("gaps", []) if g.get("risk") == "medium"])
        report.gaps_low = len([g for g in data.get("gaps", []) if g.get("risk") == "low"])
        
        return report
    
    async def _generate_dsar_summary(
        self,
        report: GeneratedReport,
        data_sources: dict[str, Any] | None,
    ) -> GeneratedReport:
        """Generate DSAR summary report."""
        data = data_sources or {}
        
        # Overview
        overview = ReportSection(
            section_id="overview",
            title="DSAR Overview",
            order=1,
            content={
                "total_received": data.get("total_received", 0),
                "completed": data.get("completed", 0),
                "in_progress": data.get("in_progress", 0),
                "overdue": data.get("overdue", 0),
                "average_response_days": data.get("avg_days", 0),
            },
            charts=[
                {
                    "type": "pie",
                    "title": "DSAR Status Distribution",
                    "data": data.get("status_distribution", {}),
                },
            ],
        )
        
        # By type
        by_type = ReportSection(
            section_id="by_type",
            title="Requests by Type",
            order=2,
            content={},
            tables=[
                {
                    "title": "DSAR Breakdown by Type",
                    "headers": ["Type", "Count", "Avg Days", "Overdue"],
                    "rows": data.get("by_type", []),
                },
            ],
        )
        
        # Trends
        trends = ReportSection(
            section_id="trends",
            title="DSAR Trends",
            order=3,
            content={
                "month_over_month": data.get("mom_change", 0),
                "year_over_year": data.get("yoy_change", 0),
            },
            charts=[
                {
                    "type": "line",
                    "title": "Monthly DSAR Volume",
                    "data": data.get("monthly_trend", []),
                },
            ],
        )
        
        report.sections = [overview, by_type, trends]
        
        return report
    
    async def _generate_ai_governance_report(
        self,
        report: GeneratedReport,
        data_sources: dict[str, Any] | None,
    ) -> GeneratedReport:
        """Generate AI governance report."""
        data = data_sources or {}
        
        # AI inventory
        inventory = ReportSection(
            section_id="inventory",
            title="AI System Inventory",
            order=1,
            content={
                "total_systems": data.get("total_systems", 0),
                "high_risk": data.get("high_risk", 0),
                "gpai": data.get("gpai", 0),
            },
            tables=[
                {
                    "title": "Registered AI Systems",
                    "headers": ["System", "Risk Level", "Use Cases", "Conformity Status"],
                    "rows": data.get("systems", []),
                },
            ],
        )
        
        # Decisions
        decisions = ReportSection(
            section_id="decisions",
            title="AI Decision Summary",
            order=2,
            content={
                "total_decisions": data.get("total_decisions", 0),
                "human_reviewed": data.get("human_reviewed", 0),
                "overrides": data.get("overrides", 0),
            },
            charts=[
                {
                    "type": "bar",
                    "title": "Decisions by System",
                    "data": data.get("decisions_by_system", {}),
                },
            ],
        )
        
        # Bias assessments
        bias = ReportSection(
            section_id="bias",
            title="Bias Assessment Results",
            order=3,
            content={
                "assessments_completed": data.get("bias_assessments", 0),
                "bias_detected": data.get("bias_detected", 0),
            },
            findings=data.get("bias_findings", []),
        )
        
        report.sections = [inventory, decisions, bias]
        
        return report
    
    def _score_to_status(self, score: float) -> str:
        """Convert compliance score to status label."""
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Satisfactory"
        elif score >= 40:
            return "Needs Improvement"
        else:
            return "Critical"
    
    def _generate_executive_text(self, report: GeneratedReport) -> str:
        """Generate executive summary text."""
        status = self._score_to_status(report.overall_score)
        
        return f"""
This report provides an executive summary of the organization's compliance status 
for the period {report.period_start.strftime('%B %Y')} to {report.period_end.strftime('%B %Y')}.

**Overall Status: {status}** (Score: {report.overall_score:.1f}%)

The organization has implemented {report.compliant_controls} of {report.total_controls} 
required controls across the assessed frameworks.

**Critical Findings:**
- {report.gaps_critical} critical gaps requiring immediate attention
- {report.gaps_high} high-priority gaps requiring action within 30 days

**Recommendations:**
1. Prioritize remediation of critical gaps
2. Conduct regular control effectiveness reviews
3. Enhance automation for continuous compliance monitoring
"""
    
    async def export_report(
        self,
        report_id: str,
        format: ReportFormat,
    ) -> bytes:
        """Export report in specified format."""
        report = self._generated_reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")
        
        if format == ReportFormat.JSON:
            return self._export_json(report)
        elif format == ReportFormat.MARKDOWN:
            return self._export_markdown(report)
        elif format == ReportFormat.HTML:
            return self._export_html(report)
        else:
            # Default to JSON
            return self._export_json(report)
    
    def _export_json(self, report: GeneratedReport) -> bytes:
        """Export report as JSON."""
        data = {
            "report_id": report.report_id,
            "title": report.title,
            "type": report.report_type.value,
            "generated_at": report.generated_at.isoformat(),
            "generated_by": report.generated_by,
            "period": {
                "start": report.period_start.isoformat() if report.period_start else None,
                "end": report.period_end.isoformat() if report.period_end else None,
            },
            "metrics": {
                "overall_score": report.overall_score,
                "total_controls": report.total_controls,
                "compliant_controls": report.compliant_controls,
                "gaps": {
                    "critical": report.gaps_critical,
                    "high": report.gaps_high,
                    "medium": report.gaps_medium,
                    "low": report.gaps_low,
                },
            },
            "executive_summary": report.executive_summary,
            "sections": [
                {
                    "id": s.section_id,
                    "title": s.title,
                    "content": s.content,
                    "findings": s.findings,
                    "recommendations": s.recommendations,
                }
                for s in report.sections
            ],
        }
        return json.dumps(data, indent=2, default=str).encode("utf-8")
    
    def _export_markdown(self, report: GeneratedReport) -> bytes:
        """Export report as Markdown."""
        lines = [
            f"# {report.title}",
            "",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Type:** {report.report_type.value}",
            f"**Period:** {report.period_start.strftime('%Y-%m-%d')} to {report.period_end.strftime('%Y-%m-%d')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            report.executive_summary,
            "",
            "---",
            "",
        ]
        
        for section in sorted(report.sections, key=lambda s: s.order):
            lines.append(f"## {section.title}")
            lines.append("")
            
            if section.content:
                for key, value in section.content.items():
                    lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
                lines.append("")
            
            if section.findings:
                lines.append("### Findings")
                for finding in section.findings:
                    lines.append(f"- {finding.get('description', finding)}")
                lines.append("")
            
            if section.recommendations:
                lines.append("### Recommendations")
                for rec in section.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines).encode("utf-8")
    
    def _export_html(self, report: GeneratedReport) -> bytes:
        """Export report as HTML."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{report.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 1px solid #ccc; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .finding {{ padding: 10px; margin: 5px 0; background: #fff3cd; border-left: 3px solid #ffc107; }}
        .recommendation {{ padding: 10px; margin: 5px 0; background: #d4edda; border-left: 3px solid #28a745; }}
    </style>
</head>
<body>
    <h1>{report.title}</h1>
    <p><strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
    
    <h2>Key Metrics</h2>
    <div class="metric">
        <div class="metric-value">{report.overall_score:.1f}%</div>
        <div>Compliance Score</div>
    </div>
    <div class="metric">
        <div class="metric-value">{report.compliant_controls}/{report.total_controls}</div>
        <div>Controls Compliant</div>
    </div>
    <div class="metric">
        <div class="metric-value">{report.gaps_critical}</div>
        <div>Critical Gaps</div>
    </div>
    
    <h2>Executive Summary</h2>
    <p>{report.executive_summary.replace(chr(10), '<br>')}</p>
"""
        
        for section in sorted(report.sections, key=lambda s: s.order):
            html += f"<h2>{section.title}</h2>"
            
            if section.findings:
                html += "<h3>Findings</h3>"
                for finding in section.findings:
                    desc = finding.get('description', str(finding))
                    html += f'<div class="finding">{desc}</div>'
            
            if section.recommendations:
                html += "<h3>Recommendations</h3>"
                for rec in section.recommendations:
                    html += f'<div class="recommendation">{rec}</div>'
        
        html += "</body></html>"
        
        return html.encode("utf-8")


# Global service instance
_reporting_service: ComplianceReportingService | None = None


def get_compliance_reporting_service() -> ComplianceReportingService:
    """Get the global compliance reporting service."""
    global _reporting_service
    if _reporting_service is None:
        _reporting_service = ComplianceReportingService()
    return _reporting_service
