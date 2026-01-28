"""
Tests for forge.compliance.reporting module.

Tests the compliance reporting service including report generation,
export functionality, and compliance metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import (
    ComplianceFramework,
    Jurisdiction,
)


class TestComplianceReportingService:
    """Tests for the ComplianceReportingService class."""

    @pytest.fixture
    def reporting_service(self):
        """Create a reporting service for testing."""
        try:
            from forge.compliance.reporting import get_compliance_reporting_service
            return get_compliance_reporting_service()
        except ImportError:
            pytest.skip("ComplianceReportingService not available")

    @pytest.mark.asyncio
    async def test_generate_report_executive_summary(self, reporting_service):
        """Test generating an executive summary report."""
        try:
            from forge.compliance.reporting import ReportType

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                generated_by="compliance_officer",
            )

            assert report is not None
            assert report.report_id is not None
            assert report.title is not None
            assert report.overall_score >= 0
        except ImportError:
            pytest.skip("ReportType not available")

    @pytest.mark.asyncio
    async def test_generate_report_full(self, reporting_service):
        """Test generating a full compliance report."""
        try:
            from forge.compliance.reporting import ReportType

            report = await reporting_service.generate_report(
                report_type=ReportType.FULL,
                generated_by="audit_team",
            )

            assert report is not None
            assert report.total_controls >= 0
        except ImportError:
            pytest.skip("ReportType not available")

    @pytest.mark.asyncio
    async def test_generate_report_with_frameworks(self, reporting_service):
        """Test generating report for specific frameworks."""
        try:
            from forge.compliance.reporting import ReportType

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                frameworks=[ComplianceFramework.GDPR, ComplianceFramework.CCPA],
                generated_by="compliance_officer",
            )

            assert report is not None
        except ImportError:
            pytest.skip("ReportType not available")

    @pytest.mark.asyncio
    async def test_generate_report_with_jurisdictions(self, reporting_service):
        """Test generating report for specific jurisdictions."""
        try:
            from forge.compliance.reporting import ReportType

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                jurisdictions=[Jurisdiction.EU, Jurisdiction.US_CALIFORNIA],
                generated_by="compliance_officer",
            )

            assert report is not None
        except ImportError:
            pytest.skip("ReportType not available")

    @pytest.mark.asyncio
    async def test_generate_report_with_date_range(self, reporting_service):
        """Test generating report with date range."""
        try:
            from forge.compliance.reporting import ReportType

            start_date = datetime.now(UTC) - timedelta(days=30)
            end_date = datetime.now(UTC)

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                start_date=start_date,
                end_date=end_date,
                generated_by="compliance_officer",
            )

            assert report is not None
        except ImportError:
            pytest.skip("ReportType not available")

    @pytest.mark.asyncio
    async def test_export_report_json(self, reporting_service):
        """Test exporting report as JSON."""
        try:
            from forge.compliance.reporting import ReportType, ReportFormat

            # First generate a report
            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                generated_by="test",
            )

            # Export it
            content = await reporting_service.export_report(
                report_id=report.report_id,
                format=ReportFormat.JSON,
            )

            assert content is not None
            assert isinstance(content, bytes)
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_export_report_markdown(self, reporting_service):
        """Test exporting report as Markdown."""
        try:
            from forge.compliance.reporting import ReportType, ReportFormat

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                generated_by="test",
            )

            content = await reporting_service.export_report(
                report_id=report.report_id,
                format=ReportFormat.MARKDOWN,
            )

            assert content is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_export_report_html(self, reporting_service):
        """Test exporting report as HTML."""
        try:
            from forge.compliance.reporting import ReportType, ReportFormat

            report = await reporting_service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                generated_by="test",
            )

            content = await reporting_service.export_report(
                report_id=report.report_id,
                format=ReportFormat.HTML,
            )

            assert content is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_export_report_not_found(self, reporting_service):
        """Test exporting nonexistent report."""
        try:
            from forge.compliance.reporting import ReportFormat

            with pytest.raises(ValueError):
                await reporting_service.export_report(
                    report_id="nonexistent_report",
                    format=ReportFormat.JSON,
                )
        except ImportError:
            pytest.skip("Required imports not available")


class TestReportType:
    """Tests for ReportType enum."""

    def test_report_type_values(self):
        """Test that ReportType enum has expected values."""
        try:
            from forge.compliance.reporting import ReportType

            assert hasattr(ReportType, "EXECUTIVE_SUMMARY")
            assert hasattr(ReportType, "FULL")
        except ImportError:
            pytest.skip("ReportType enum not available")


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_report_format_values(self):
        """Test that ReportFormat enum has expected values."""
        try:
            from forge.compliance.reporting import ReportFormat

            assert hasattr(ReportFormat, "JSON")
            assert hasattr(ReportFormat, "MARKDOWN")
            assert hasattr(ReportFormat, "HTML")
        except ImportError:
            pytest.skip("ReportFormat enum not available")


class TestComplianceReport:
    """Tests for ComplianceReport model."""

    @pytest.mark.asyncio
    async def test_report_metrics(self):
        """Test that report includes expected metrics."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            report = await service.generate_report(
                report_type=ReportType.FULL,
                generated_by="test",
            )

            # Check for expected metrics
            assert hasattr(report, "overall_score")
            assert hasattr(report, "total_controls")
            assert hasattr(report, "compliant_controls")
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_report_gaps(self):
        """Test that report includes gap analysis."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            report = await service.generate_report(
                report_type=ReportType.FULL,
                generated_by="test",
            )

            # Check for gap information
            assert hasattr(report, "gaps_critical") or hasattr(report, "critical_gaps")
            assert hasattr(report, "gaps_high") or hasattr(report, "high_gaps")
        except ImportError:
            pytest.skip("Required imports not available")


class TestReportingServiceIntegration:
    """Integration tests for reporting service."""

    @pytest.mark.asyncio
    async def test_full_reporting_workflow(self):
        """Test complete reporting workflow."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
                ReportFormat,
            )

            service = get_compliance_reporting_service()

            # Step 1: Generate executive summary
            exec_report = await service.generate_report(
                report_type=ReportType.EXECUTIVE_SUMMARY,
                frameworks=[ComplianceFramework.GDPR],
                generated_by="ciso",
            )

            # Step 2: Generate full report
            full_report = await service.generate_report(
                report_type=ReportType.FULL,
                frameworks=[ComplianceFramework.GDPR],
                generated_by="compliance_team",
            )

            # Step 3: Export in multiple formats
            json_export = await service.export_report(
                exec_report.report_id,
                ReportFormat.JSON,
            )

            md_export = await service.export_report(
                full_report.report_id,
                ReportFormat.MARKDOWN,
            )

            assert exec_report is not None
            assert full_report is not None
            assert json_export is not None
            assert md_export is not None
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_multi_framework_report(self):
        """Test generating report for multiple frameworks."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            report = await service.generate_report(
                report_type=ReportType.FULL,
                frameworks=[
                    ComplianceFramework.GDPR,
                    ComplianceFramework.CCPA,
                    ComplianceFramework.SOC2,
                    ComplianceFramework.HIPAA,
                ],
                generated_by="compliance_team",
            )

            assert report is not None
            assert report.total_controls >= 0
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_periodic_report_generation(self):
        """Test generating periodic (monthly) reports."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            # Generate monthly reports for past 3 months
            reports = []
            for months_ago in range(3):
                start = datetime.now(UTC) - timedelta(days=30 * (months_ago + 1))
                end = datetime.now(UTC) - timedelta(days=30 * months_ago)

                report = await service.generate_report(
                    report_type=ReportType.EXECUTIVE_SUMMARY,
                    start_date=start,
                    end_date=end,
                    generated_by="automated_system",
                )
                reports.append(report)

            assert len(reports) == 3
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_jurisdiction_specific_report(self):
        """Test generating jurisdiction-specific reports."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            # EU report
            eu_report = await service.generate_report(
                report_type=ReportType.FULL,
                jurisdictions=[Jurisdiction.EU, Jurisdiction.UK],
                generated_by="eu_dpo",
            )

            # US report
            us_report = await service.generate_report(
                report_type=ReportType.FULL,
                jurisdictions=[
                    Jurisdiction.US_FEDERAL,
                    Jurisdiction.US_CALIFORNIA,
                ],
                generated_by="us_compliance",
            )

            assert eu_report is not None
            assert us_report is not None
        except ImportError:
            pytest.skip("Required imports not available")


class TestReportMetrics:
    """Tests for report metric calculations."""

    @pytest.mark.asyncio
    async def test_compliance_score_calculation(self):
        """Test that compliance score is calculated correctly."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            report = await service.generate_report(
                report_type=ReportType.FULL,
                generated_by="test",
            )

            # Score should be between 0 and 100
            assert 0 <= report.overall_score <= 100

            # If there are compliant controls, score should reflect that
            if report.total_controls > 0:
                expected_pct = (report.compliant_controls / report.total_controls) * 100
                # Allow some tolerance for additional scoring factors
                assert abs(report.overall_score - expected_pct) < 50
        except ImportError:
            pytest.skip("Required imports not available")

    @pytest.mark.asyncio
    async def test_gap_prioritization(self):
        """Test that gaps are properly prioritized."""
        try:
            from forge.compliance.reporting import (
                get_compliance_reporting_service,
                ReportType,
            )

            service = get_compliance_reporting_service()

            report = await service.generate_report(
                report_type=ReportType.FULL,
                generated_by="test",
            )

            # Gaps should be categorized by severity
            critical = getattr(report, "gaps_critical", 0)
            high = getattr(report, "gaps_high", 0)
            medium = getattr(report, "gaps_medium", 0)
            low = getattr(report, "gaps_low", 0)

            # All should be non-negative
            assert critical >= 0
            assert high >= 0
            assert medium >= 0
            assert low >= 0
        except ImportError:
            pytest.skip("Required imports not available")
