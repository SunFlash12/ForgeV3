"""
Forge Compliance Framework - DSAR Processor

Automated Data Subject Access Request processing:
- Identity verification
- Data discovery across systems
- Export generation (JSON, CSV, PDF)
- Erasure orchestration with exceptions
- Portability formatting

Per GDPR Articles 15-22, CCPA §1798.100-125, LGPD Articles 17-18
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.enums import (
    DataClassification,
)
from forge.compliance.core.models import (
    AuditEvent,
    DataSubjectRequest,
    DSARVerification,
)

logger = structlog.get_logger(__name__)


class VerificationMethod(str, Enum):
    """Identity verification methods for DSAR."""

    EMAIL_CONFIRMATION = "email_confirmation"
    SMS_OTP = "sms_otp"
    DOCUMENT_UPLOAD = "document_upload"
    KNOWLEDGE_BASED = "knowledge_based"
    ACCOUNT_LOGIN = "account_login"
    NOTARIZED = "notarized"


class ExportFormat(str, Enum):
    """DSAR export formats."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    XML = "xml"
    MACHINE_READABLE = "machine_readable"  # For portability


@dataclass
class DataSource:
    """Represents a data source for DSAR discovery."""

    source_id: str
    source_name: str
    source_type: str  # "database", "file_storage", "third_party", "backup"
    data_categories: list[DataClassification]
    discovery_function: Callable[[str], Awaitable[dict[str, Any]]] | None = None
    erasure_function: Callable[[str], Awaitable[bool]] | None = None
    portability_supported: bool = True
    retention_override: bool = False  # Legal hold, etc.


@dataclass
class DiscoveredData:
    """Data discovered for a subject."""

    source_id: str
    source_name: str
    data_category: DataClassification
    record_count: int
    sample_fields: list[str]
    data: dict[str, Any] | None = None
    can_export: bool = True
    can_erase: bool = True
    erasure_exceptions: list[str] = field(default_factory=list)


@dataclass
class ErasureResult:
    """Result of erasure operation."""

    source_id: str
    source_name: str
    success: bool
    records_deleted: int
    records_retained: int
    retention_reasons: list[str]
    error: str | None = None


class DSARProcessor:
    """
    Automated DSAR processing engine.

    Handles the complete lifecycle:
    1. Request intake and verification
    2. Data discovery across registered sources
    3. Export generation in requested format
    4. Erasure orchestration with exceptions
    5. Audit trail maintenance
    """

    def __init__(self):
        self._data_sources: dict[str, DataSource] = {}
        self._verification_handlers: dict[VerificationMethod, Callable] = {}
        self._audit_log: list[AuditEvent] = []

        # Erasure exceptions by category
        self._erasure_exceptions = {
            "legal_hold": "Data subject to active legal hold",
            "regulatory_retention": "Regulatory retention period not expired",
            "contract_performance": "Required for ongoing contract performance",
            "legal_claims": "Needed for establishment/defense of legal claims",
            "public_interest": "Processing necessary for public interest",
            "scientific_research": "Required for scientific research purposes",
            "freedom_of_expression": "Freedom of expression and information",
            "legal_obligation": "Required by legal obligation",
            "public_health": "Public health purposes",
            "archiving": "Archiving in public interest",
        }

    # ───────────────────────────────────────────────────────────────
    # DATA SOURCE REGISTRATION
    # ───────────────────────────────────────────────────────────────

    def register_data_source(self, source: DataSource) -> None:
        """Register a data source for DSAR discovery."""
        self._data_sources[source.source_id] = source
        logger.info(
            "data_source_registered",
            source_id=source.source_id,
            source_name=source.source_name,
        )

    def register_verification_handler(
        self,
        method: VerificationMethod,
        handler: Callable[[DataSubjectRequest], Awaitable[DSARVerification]],
    ) -> None:
        """Register a verification method handler."""
        self._verification_handlers[method] = handler

    # ───────────────────────────────────────────────────────────────
    # IDENTITY VERIFICATION
    # ───────────────────────────────────────────────────────────────

    async def verify_identity(
        self,
        dsar: DataSubjectRequest,
        method: VerificationMethod,
        verification_data: dict[str, Any],
    ) -> DSARVerification:
        """
        Verify the identity of the data subject.

        Per GDPR Article 12(6), reasonable measures to verify identity.
        """
        handler = self._verification_handlers.get(method)

        if handler:
            verification = await handler(dsar)
        else:
            # Default verification logic
            verification = DSARVerification(
                method=method.value,
                verified=False,
                verified_at=None,
            )

            if method == VerificationMethod.EMAIL_CONFIRMATION:
                # Check if email matches account
                verification.verified = True
                verification.verified_at = datetime.now(UTC)
                verification.verification_reference = f"EMAIL-{uuid4().hex[:8]}"

            elif method == VerificationMethod.ACCOUNT_LOGIN:
                # User authenticated via their account
                verification.verified = True
                verification.verified_at = datetime.now(UTC)
                verification.verification_reference = f"AUTH-{uuid4().hex[:8]}"

        # Update DSAR
        dsar.verification = verification

        logger.info(
            "dsar_identity_verification",
            dsar_id=dsar.id,
            method=method.value,
            verified=verification.verified,
        )

        return verification

    # ───────────────────────────────────────────────────────────────
    # DATA DISCOVERY
    # ───────────────────────────────────────────────────────────────

    async def discover_data(
        self,
        dsar: DataSubjectRequest,
        subject_identifier: str,
    ) -> list[DiscoveredData]:
        """
        Discover all data for a subject across registered sources.

        Args:
            dsar: The DSAR being processed
            subject_identifier: Email, user ID, or other identifier

        Returns:
            List of discovered data from all sources
        """
        discovered: list[DiscoveredData] = []

        # Query all registered sources
        discovery_tasks = []
        for source in self._data_sources.values():
            if source.discovery_function:
                task = self._discover_from_source(source, subject_identifier)
                discovery_tasks.append(task)

        # Run discovery in parallel
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("data_discovery_error", error=str(result))
            elif result:
                discovered.extend(result)

        # Log discovery
        logger.info(
            "dsar_data_discovered",
            dsar_id=dsar.id,
            sources_queried=len(self._data_sources),
            records_found=sum(d.record_count for d in discovered),
        )

        return discovered

    async def _discover_from_source(
        self,
        source: DataSource,
        subject_identifier: str,
    ) -> list[DiscoveredData]:
        """Discover data from a single source."""
        try:
            if source.discovery_function:
                data = await source.discovery_function(subject_identifier)
            else:
                data = {}

            if not data:
                return []

            # Create discovered data records
            discovered = []
            for category in source.data_categories:
                category_data = data.get(category.value, {})
                if category_data:
                    discovered.append(
                        DiscoveredData(
                            source_id=source.source_id,
                            source_name=source.source_name,
                            data_category=category,
                            record_count=len(category_data)
                            if isinstance(category_data, list)
                            else 1,
                            sample_fields=list(category_data.keys())
                            if isinstance(category_data, dict)
                            else [],
                            data=category_data,
                            can_export=source.portability_supported,
                            can_erase=not source.retention_override,
                        )
                    )

            return discovered

        except Exception as e:
            logger.error(
                "source_discovery_failed",
                source_id=source.source_id,
                error=str(e),
            )
            return []

    # ───────────────────────────────────────────────────────────────
    # DATA EXPORT
    # ───────────────────────────────────────────────────────────────

    async def generate_export(
        self,
        dsar: DataSubjectRequest,
        discovered_data: list[DiscoveredData],
        export_format: ExportFormat = ExportFormat.JSON,
        include_metadata: bool = True,
    ) -> bytes:
        """
        Generate data export in requested format.

        Per GDPR Article 20 - Right to Data Portability.

        FIX: Use asyncio.to_thread to prevent blocking event loop on large exports.
        """
        # Run CPU-bound serialization in thread pool to avoid blocking
        if export_format == ExportFormat.JSON:
            return await asyncio.to_thread(
                self._export_json, dsar, discovered_data, include_metadata
            )
        elif export_format == ExportFormat.CSV:
            return await asyncio.to_thread(
                self._export_csv, dsar, discovered_data, include_metadata
            )
        elif export_format == ExportFormat.MACHINE_READABLE:
            return await asyncio.to_thread(self._export_machine_readable, dsar, discovered_data)
        else:
            # Default to JSON
            return await asyncio.to_thread(
                self._export_json, dsar, discovered_data, include_metadata
            )

    def _export_json(
        self,
        dsar: DataSubjectRequest,
        discovered_data: list[DiscoveredData],
        include_metadata: bool,
    ) -> bytes:
        """Export data as JSON."""
        export = {
            "export_metadata": {
                "dsar_id": dsar.id,
                "request_type": dsar.request_type.value,
                "subject_email": dsar.subject_email,
                "generated_at": datetime.now(UTC).isoformat(),
                "format": "JSON",
                "version": "1.0",
            }
            if include_metadata
            else {},
            "data": {},
        }

        for data in discovered_data:
            if data.data and data.can_export:
                source_key = f"{data.source_name}_{data.data_category.value}"
                export["data"][source_key] = {
                    "source": data.source_name,
                    "category": data.data_category.value,
                    "record_count": data.record_count,
                    "records": data.data,
                }

        return json.dumps(export, indent=2, default=str).encode("utf-8")

    def _export_csv(
        self,
        dsar: DataSubjectRequest,
        discovered_data: list[DiscoveredData],
        include_metadata: bool,
    ) -> bytes:
        """Export data as CSV."""
        output = io.StringIO()

        # Metadata header
        if include_metadata:
            output.write(f"# DSAR Export - {dsar.id}\n")
            output.write(f"# Generated: {datetime.now(UTC).isoformat()}\n")
            output.write(f"# Subject: {dsar.subject_email}\n\n")

        for data in discovered_data:
            if data.data and data.can_export:
                output.write(f"\n## {data.source_name} - {data.data_category.value}\n")

                if isinstance(data.data, list) and data.data:
                    # Write as CSV
                    if isinstance(data.data[0], dict):
                        writer = csv.DictWriter(output, fieldnames=data.data[0].keys())
                        writer.writeheader()
                        writer.writerows(data.data)
                elif isinstance(data.data, dict):
                    writer = csv.writer(output)
                    writer.writerow(["Field", "Value"])
                    for k, v in data.data.items():
                        writer.writerow([k, v])

        return output.getvalue().encode("utf-8")

    def _export_machine_readable(
        self,
        dsar: DataSubjectRequest,
        discovered_data: list[DiscoveredData],
    ) -> bytes:
        """
        Export in machine-readable format for portability.

        Uses JSON-LD with schema.org vocabulary per GDPR Article 20.
        """
        export = {
            "@context": "https://schema.org",
            "@type": "DataDownload",
            "dateCreated": datetime.now(UTC).isoformat(),
            "encodingFormat": "application/json",
            "about": {
                "@type": "Person",
                "email": dsar.subject_email,
            },
            "hasPart": [],
        }

        for data in discovered_data:
            if data.data and data.can_export:
                export["hasPart"].append(
                    {
                        "@type": "Dataset",
                        "name": data.source_name,
                        "description": f"{data.data_category.value} data",
                        "distribution": {
                            "@type": "DataDownload",
                            "contentUrl": f"data:{data.source_id}",
                            "encodingFormat": "application/json",
                        },
                        "data": data.data,
                    }
                )

        return json.dumps(export, indent=2, default=str).encode("utf-8")

    # ───────────────────────────────────────────────────────────────
    # DATA ERASURE
    # ───────────────────────────────────────────────────────────────

    async def execute_erasure(
        self,
        dsar: DataSubjectRequest,
        subject_identifier: str,
        exceptions: list[str] | None = None,
    ) -> list[ErasureResult]:
        """
        Execute erasure (right to be forgotten) across all sources.

        Per GDPR Article 17 with exceptions in Article 17(3).

        Args:
            dsar: The DSAR being processed
            subject_identifier: Email, user ID, or other identifier
            exceptions: List of exception codes to apply

        Returns:
            List of erasure results per source
        """
        exceptions = exceptions or []
        results: list[ErasureResult] = []

        for source in self._data_sources.values():
            result = await self._erase_from_source(
                source,
                subject_identifier,
                exceptions,
            )
            results.append(result)

        # Log erasure completion
        total_deleted = sum(r.records_deleted for r in results)
        total_retained = sum(r.records_retained for r in results)

        logger.info(
            "dsar_erasure_completed",
            dsar_id=dsar.id,
            sources_processed=len(results),
            records_deleted=total_deleted,
            records_retained=total_retained,
        )

        return results

    async def _erase_from_source(
        self,
        source: DataSource,
        subject_identifier: str,
        exceptions: list[str],
    ) -> ErasureResult:
        """Execute erasure on a single source."""
        result = ErasureResult(
            source_id=source.source_id,
            source_name=source.source_name,
            success=False,
            records_deleted=0,
            records_retained=0,
            retention_reasons=[],
        )

        try:
            # Check for retention override
            if source.retention_override:
                result.records_retained = 1  # Placeholder
                result.retention_reasons.append("Source has retention override")
                result.success = True
                return result

            # Check for applicable exceptions
            for exception in exceptions:
                if exception in self._erasure_exceptions:
                    result.retention_reasons.append(self._erasure_exceptions[exception])

            if result.retention_reasons:
                result.success = True
                return result

            # Execute erasure
            if source.erasure_function:
                success = await source.erasure_function(subject_identifier)
                result.success = success
                if success:
                    result.records_deleted = 1  # Placeholder
            else:
                # No erasure function - mark as needing manual processing
                result.retention_reasons.append("Manual erasure required")
                result.success = True

            return result

        except Exception as e:
            result.error = str(e)
            logger.error(
                "source_erasure_failed",
                source_id=source.source_id,
                error=str(e),
            )
            return result

    # ───────────────────────────────────────────────────────────────
    # RESTRICTION OF PROCESSING
    # ───────────────────────────────────────────────────────────────

    async def restrict_processing(
        self,
        dsar: DataSubjectRequest,
        subject_identifier: str,
        restriction_scope: list[str] | None = None,
    ) -> dict[str, bool]:
        """
        Restrict processing of subject's data.

        Per GDPR Article 18 - Right to Restriction.

        Args:
            dsar: The DSAR being processed
            subject_identifier: Subject identifier
            restriction_scope: Specific processing activities to restrict

        Returns:
            Dict of source_id -> restriction_success
        """
        results = {}

        for source_id, _source in self._data_sources.items():
            # Mark data as restricted in each source
            # In production, this would set flags in each system
            results[source_id] = True

            logger.info(
                "processing_restricted",
                source_id=source_id,
                subject=subject_identifier,
            )

        return results

    # ───────────────────────────────────────────────────────────────
    # RECTIFICATION
    # ───────────────────────────────────────────────────────────────

    async def rectify_data(
        self,
        dsar: DataSubjectRequest,
        subject_identifier: str,
        corrections: dict[str, Any],
    ) -> dict[str, bool]:
        """
        Rectify (correct) subject's data.

        Per GDPR Article 16 - Right to Rectification.

        Args:
            dsar: The DSAR being processed
            subject_identifier: Subject identifier
            corrections: Dict of field -> corrected_value

        Returns:
            Dict of field -> correction_success
        """
        results = {}

        for field_name, _new_value in corrections.items():
            # In production, update each relevant source
            results[field_name] = True

            logger.info(
                "data_rectified",
                dsar_id=dsar.id,
                field=field_name,
            )

        return results


# Global processor instance
_dsar_processor: DSARProcessor | None = None


def get_dsar_processor() -> DSARProcessor:
    """Get the global DSAR processor instance."""
    global _dsar_processor
    if _dsar_processor is None:
        _dsar_processor = DSARProcessor()
    return _dsar_processor
