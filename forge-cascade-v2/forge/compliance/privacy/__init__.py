"""
Forge Compliance Framework - Privacy Module

Implements privacy rights and consent management:
- DSAR processing (access, erasure, portability, rectification)
- Consent management with IAB TCF 2.2 support
- GPC/Do Not Sell signal handling
"""

from forge.compliance.privacy.dsar_processor import (
    DSARProcessor,
    get_dsar_processor,
    VerificationMethod,
    ExportFormat,
    DataSource,
    DiscoveredData,
    ErasureResult,
)

from forge.compliance.privacy.consent_service import (
    ConsentManagementService,
    get_consent_service,
    ConsentPurpose,
    ConsentStatus,
    ConsentSource,
    ConsentRecord,
    ConsentPreferences,
)

__all__ = [
    # DSAR Processing
    "DSARProcessor",
    "get_dsar_processor",
    "VerificationMethod",
    "ExportFormat",
    "DataSource",
    "DiscoveredData",
    "ErasureResult",
    # Consent Management
    "ConsentManagementService",
    "get_consent_service",
    "ConsentPurpose",
    "ConsentStatus",
    "ConsentSource",
    "ConsentRecord",
    "ConsentPreferences",
]
