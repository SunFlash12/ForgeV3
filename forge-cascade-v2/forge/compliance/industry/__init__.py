"""
Forge Compliance Framework - Industry-Specific Module

Implements industry-specific compliance:
- HIPAA/HITECH (Healthcare)
- PCI-DSS 4.0.1 (Payment Card)
- COPPA (Children's Privacy)
- SOX, GLBA, FERPA
"""

from forge.compliance.industry.services import (
    HIPAAComplianceService,
    get_hipaa_service,
    PHIIdentifier,
    HIPAAAuthorizationPurpose,
    HIPAAAuthorization,
    PHIAccessLog,
    PCIDSSComplianceService,
    get_pci_service,
    CardDataElement,
    PCIScope,
    PCIScanResult,
    COPPAComplianceService,
    get_coppa_service,
    ParentalConsentMethod,
    ChildProfile,
)

__all__ = [
    # HIPAA
    "HIPAAComplianceService",
    "get_hipaa_service",
    "PHIIdentifier",
    "HIPAAAuthorizationPurpose",
    "HIPAAAuthorization",
    "PHIAccessLog",
    # PCI-DSS
    "PCIDSSComplianceService",
    "get_pci_service",
    "CardDataElement",
    "PCIScope",
    "PCIScanResult",
    # COPPA
    "COPPAComplianceService",
    "get_coppa_service",
    "ParentalConsentMethod",
    "ChildProfile",
]
