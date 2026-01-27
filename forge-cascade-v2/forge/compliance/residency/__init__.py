"""
Forge Compliance Framework - Data Residency Module

Handles data residency requirements per:
- GDPR Article 44-49 (cross-border transfers)
- China PIPL Chapter III (data localization)
- Russia FZ-152 (data localization)
- LGPD (Brazil transfers)
"""

from forge.compliance.residency.service import (
    TransferMechanism,
    DataRegion,
    RegionMapping,
    TransferRequest,
    TransferImpactAssessment,
    DataResidencyService,
    get_data_residency_service,
)

__all__ = [
    "TransferMechanism",
    "DataRegion",
    "RegionMapping",
    "TransferRequest",
    "TransferImpactAssessment",
    "DataResidencyService",
    "get_data_residency_service",
]
