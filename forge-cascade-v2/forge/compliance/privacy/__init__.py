"""
Forge Compliance Framework - Privacy Module

Implements privacy rights and consent management:
- DSAR processing (access, erasure, portability, rectification)
- Consent management with IAB TCF 2.2 support
- GPC/Do Not Sell signal handling
"""

from forge.compliance.privacy.consent_service import (
    ConsentManagementService,
    ConsentPreferences,
    ConsentPurpose,
    ConsentRecord,
    ConsentSource,
    ConsentStatus,
    get_consent_service,
)
from forge.compliance.privacy.dsar_processor import (
    DataSource,
    DiscoveredData,
    DSARProcessor,
    ErasureResult,
    ExportFormat,
    VerificationMethod,
    get_dsar_processor,
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
