"""
Forge Compliance Framework - Data Residency Service

Handles data residency requirements across jurisdictions:
- Regional data pod routing
- Cross-border transfer controls
- Data localization enforcement (China PIPL, Russia FZ-152)
- Transfer Impact Assessments
- SCCs/BCRs management

Per GDPR Article 44-49, PIPL Chapter III, Russia FZ-152
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

from forge.compliance.core.config import get_compliance_config
from forge.compliance.core.enums import Jurisdiction, DataClassification

logger = structlog.get_logger(__name__)


class TransferMechanism(str, Enum):
    """Legal mechanisms for cross-border data transfer."""
    ADEQUACY = "adequacy"               # Adequacy decision
    SCCS = "sccs"                       # Standard Contractual Clauses
    BCRS = "bcrs"                       # Binding Corporate Rules
    CERTIFICATION = "certification"      # Approved certification
    CODE_OF_CONDUCT = "code_of_conduct" # Approved code of conduct
    DEROGATION = "derogation"           # Specific derogation (Art. 49)
    CAC_ASSESSMENT = "cac_assessment"   # China CAC Security Assessment
    PROHIBITED = "prohibited"           # Transfer not permitted


class DataRegion(str, Enum):
    """Data storage regions."""
    # North America
    US_EAST = "us-east-1"
    US_WEST = "us-west-2"
    CA_CENTRAL = "ca-central-1"
    
    # Europe
    EU_WEST = "eu-west-1"          # Ireland
    EU_CENTRAL = "eu-central-1"    # Frankfurt
    EU_NORTH = "eu-north-1"        # Stockholm
    
    # Asia Pacific
    AP_SOUTHEAST = "ap-southeast-1"  # Singapore
    AP_NORTHEAST = "ap-northeast-1"  # Tokyo
    AP_SOUTH = "ap-south-1"          # Mumbai
    
    # China (isolated)
    CN_NORTH = "cn-north-1"          # Beijing
    CN_NORTHWEST = "cn-northwest-1"  # Ningxia
    
    # Other
    SA_EAST = "sa-east-1"            # São Paulo
    ME_SOUTH = "me-south-1"          # Bahrain
    AF_SOUTH = "af-south-1"          # Cape Town


@dataclass
class RegionMapping:
    """Mapping of jurisdictions to allowed data regions."""
    jurisdiction: Jurisdiction
    primary_region: DataRegion
    allowed_regions: list[DataRegion]
    requires_localization: bool = False
    transfer_mechanisms: list[TransferMechanism] = field(default_factory=list)


@dataclass
class TransferRequest:
    """Request to transfer data across regions."""
    source_region: DataRegion
    target_region: DataRegion
    data_classification: DataClassification
    data_subject_jurisdiction: Jurisdiction
    purpose: str
    legal_basis: str
    
    # ID with default
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Approval
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    
    # Transfer mechanism
    mechanism: TransferMechanism | None = None
    mechanism_reference: str | None = None  # SCC reference, etc.
    
    # TIA (Transfer Impact Assessment)
    tia_required: bool = False
    tia_completed: bool = False
    tia_reference: str | None = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    entity_id: str | None = None
    entity_type: str | None = None


@dataclass
class TransferImpactAssessment:
    """Transfer Impact Assessment per GDPR/Schrems II."""
    transfer_request_id: str
    
    # Assessment details
    destination_country: str
    destination_region: DataRegion
    data_categories: list[DataClassification]
    
    # ID with default
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Third country assessment
    surveillance_laws_assessed: bool = False
    government_access_risk: str = "unknown"  # low, medium, high, unknown
    
    # Supplementary measures
    supplementary_measures: list[str] = field(default_factory=list)
    technical_measures: list[str] = field(default_factory=list)
    organizational_measures: list[str] = field(default_factory=list)
    
    # Conclusion
    transfer_permitted: bool = False
    conditions: list[str] = field(default_factory=list)
    
    # Audit
    assessed_by: str | None = None
    assessed_at: datetime | None = None
    valid_until: datetime | None = None


class DataResidencyService:
    """
    Service for managing data residency and cross-border transfers.
    
    Enforces data localization requirements and manages transfer mechanisms.
    """
    
    def __init__(self):
        self.config = get_compliance_config()
        
        # Region mappings by jurisdiction
        self._region_mappings = self._initialize_region_mappings()
        
        # Transfer requests
        self._transfer_requests: dict[str, TransferRequest] = {}
        self._tias: dict[str, TransferImpactAssessment] = {}
        
        # Adequacy decisions (EU)
        self._adequacy_countries = {
            "ad", "ar", "ca", "fo", "gg", "il", "im", "jp", "je",
            "nz", "kr", "ch", "uk", "uy",  # Plus EU/EEA
        }
    
    def _initialize_region_mappings(self) -> dict[Jurisdiction, RegionMapping]:
        """Initialize jurisdiction to region mappings."""
        return {
            Jurisdiction.EU: RegionMapping(
                jurisdiction=Jurisdiction.EU,
                primary_region=DataRegion.EU_WEST,
                allowed_regions=[DataRegion.EU_WEST, DataRegion.EU_CENTRAL, DataRegion.EU_NORTH],
                requires_localization=False,
                transfer_mechanisms=[
                    TransferMechanism.ADEQUACY,
                    TransferMechanism.SCCS,
                    TransferMechanism.BCRS,
                ],
            ),
            Jurisdiction.UK: RegionMapping(
                jurisdiction=Jurisdiction.UK,
                primary_region=DataRegion.EU_WEST,  # Ireland for UK
                allowed_regions=[DataRegion.EU_WEST, DataRegion.EU_CENTRAL],
                requires_localization=False,
                transfer_mechanisms=[
                    TransferMechanism.ADEQUACY,
                    TransferMechanism.SCCS,
                ],
            ),
            Jurisdiction.US_FEDERAL: RegionMapping(
                jurisdiction=Jurisdiction.US_FEDERAL,
                primary_region=DataRegion.US_EAST,
                allowed_regions=[DataRegion.US_EAST, DataRegion.US_WEST],
                requires_localization=False,
            ),
            Jurisdiction.US_CALIFORNIA: RegionMapping(
                jurisdiction=Jurisdiction.US_CALIFORNIA,
                primary_region=DataRegion.US_WEST,
                allowed_regions=[DataRegion.US_EAST, DataRegion.US_WEST],
                requires_localization=False,
            ),
            Jurisdiction.CHINA: RegionMapping(
                jurisdiction=Jurisdiction.CHINA,
                primary_region=DataRegion.CN_NORTH,
                allowed_regions=[DataRegion.CN_NORTH, DataRegion.CN_NORTHWEST],
                requires_localization=True,  # PIPL requires localization
                transfer_mechanisms=[TransferMechanism.CAC_ASSESSMENT],
            ),
            Jurisdiction.RUSSIA: RegionMapping(
                jurisdiction=Jurisdiction.RUSSIA,
                primary_region=DataRegion.EU_CENTRAL,  # Closest, but problematic
                allowed_regions=[],  # Must be in Russia
                requires_localization=True,  # FZ-152
                transfer_mechanisms=[TransferMechanism.PROHIBITED],
            ),
            Jurisdiction.BRAZIL: RegionMapping(
                jurisdiction=Jurisdiction.BRAZIL,
                primary_region=DataRegion.SA_EAST,
                allowed_regions=[DataRegion.SA_EAST, DataRegion.US_EAST],
                requires_localization=False,
                transfer_mechanisms=[TransferMechanism.SCCS],
            ),
            Jurisdiction.SINGAPORE: RegionMapping(
                jurisdiction=Jurisdiction.SINGAPORE,
                primary_region=DataRegion.AP_SOUTHEAST,
                allowed_regions=[DataRegion.AP_SOUTHEAST, DataRegion.AP_NORTHEAST],
                requires_localization=False,
            ),
            Jurisdiction.INDIA: RegionMapping(
                jurisdiction=Jurisdiction.INDIA,
                primary_region=DataRegion.AP_SOUTH,
                allowed_regions=[DataRegion.AP_SOUTH, DataRegion.AP_SOUTHEAST],
                requires_localization=False,  # DPDP has whitelist approach
            ),
            Jurisdiction.AUSTRALIA: RegionMapping(
                jurisdiction=Jurisdiction.AUSTRALIA,
                primary_region=DataRegion.AP_SOUTHEAST,
                allowed_regions=[DataRegion.AP_SOUTHEAST, DataRegion.AP_NORTHEAST],
                requires_localization=False,
            ),
            Jurisdiction.JAPAN: RegionMapping(
                jurisdiction=Jurisdiction.JAPAN,
                primary_region=DataRegion.AP_NORTHEAST,
                allowed_regions=[DataRegion.AP_NORTHEAST, DataRegion.AP_SOUTHEAST],
                requires_localization=False,
            ),
            Jurisdiction.GLOBAL: RegionMapping(
                jurisdiction=Jurisdiction.GLOBAL,
                primary_region=DataRegion.US_EAST,
                allowed_regions=list(DataRegion),
                requires_localization=False,
            ),
        }
    
    # ───────────────────────────────────────────────────────────────
    # REGION ROUTING
    # ───────────────────────────────────────────────────────────────
    
    def get_primary_region(
        self,
        jurisdiction: Jurisdiction,
    ) -> DataRegion:
        """Get the primary data region for a jurisdiction."""
        mapping = self._region_mappings.get(
            jurisdiction,
            self._region_mappings[Jurisdiction.GLOBAL],
        )
        return mapping.primary_region
    
    def get_allowed_regions(
        self,
        jurisdiction: Jurisdiction,
    ) -> list[DataRegion]:
        """Get allowed data regions for a jurisdiction."""
        mapping = self._region_mappings.get(
            jurisdiction,
            self._region_mappings[Jurisdiction.GLOBAL],
        )
        return mapping.allowed_regions
    
    def is_region_allowed(
        self,
        jurisdiction: Jurisdiction,
        region: DataRegion,
    ) -> bool:
        """Check if a region is allowed for a jurisdiction."""
        allowed = self.get_allowed_regions(jurisdiction)
        return region in allowed
    
    def requires_localization(
        self,
        jurisdiction: Jurisdiction,
    ) -> bool:
        """Check if jurisdiction requires data localization."""
        mapping = self._region_mappings.get(jurisdiction)
        return mapping.requires_localization if mapping else False
    
    def route_data(
        self,
        user_jurisdiction: Jurisdiction,
        data_classification: DataClassification,
        preferred_region: DataRegion | None = None,
    ) -> DataRegion:
        """
        Determine the appropriate data region for storage.
        
        Args:
            user_jurisdiction: User's jurisdiction
            data_classification: Classification of the data
            preferred_region: Preferred region (if allowed)
        
        Returns:
            Appropriate DataRegion for storage
        """
        # Get allowed regions
        allowed = self.get_allowed_regions(user_jurisdiction)
        
        # Check if preferred region is allowed
        if preferred_region and preferred_region in allowed:
            return preferred_region
        
        # Check for localization requirements
        if self.requires_localization(user_jurisdiction):
            # Must use primary region for localized data
            return self.get_primary_region(user_jurisdiction)
        
        # For sensitive data, prefer primary region
        if data_classification in {
            DataClassification.SENSITIVE_PERSONAL,
            DataClassification.PHI,
            DataClassification.PCI,
            DataClassification.CHILDREN,
        }:
            return self.get_primary_region(user_jurisdiction)
        
        # Use default or preferred
        return preferred_region if preferred_region in allowed else self.get_primary_region(user_jurisdiction)
    
    # ───────────────────────────────────────────────────────────────
    # TRANSFER CONTROLS
    # ───────────────────────────────────────────────────────────────
    
    async def request_transfer(
        self,
        source_region: DataRegion,
        target_region: DataRegion,
        data_classification: DataClassification,
        data_subject_jurisdiction: Jurisdiction,
        purpose: str,
        legal_basis: str,
        entity_id: str | None = None,
        entity_type: str | None = None,
    ) -> TransferRequest:
        """
        Request approval for cross-border data transfer.
        
        Evaluates the transfer against applicable regulations and
        determines required mechanisms/assessments.
        """
        request = TransferRequest(
            source_region=source_region,
            target_region=target_region,
            data_classification=data_classification,
            data_subject_jurisdiction=data_subject_jurisdiction,
            purpose=purpose,
            legal_basis=legal_basis,
            entity_id=entity_id,
            entity_type=entity_type,
        )
        
        # Check if transfer is within allowed regions
        allowed = self.get_allowed_regions(data_subject_jurisdiction)
        
        if target_region in allowed:
            # Transfer within allowed regions - auto-approve
            request.approved = True
            request.approved_at = datetime.now(UTC)
            request.mechanism = TransferMechanism.ADEQUACY
            logger.info(
                "transfer_auto_approved",
                request_id=request.id,
                reason="target_in_allowed_regions",
            )
        else:
            # Cross-border transfer - evaluate mechanism
            mechanism = self._determine_transfer_mechanism(
                data_subject_jurisdiction,
                target_region,
            )
            request.mechanism = mechanism
            
            if mechanism == TransferMechanism.PROHIBITED:
                request.approved = False
                logger.warning(
                    "transfer_prohibited",
                    request_id=request.id,
                    jurisdiction=data_subject_jurisdiction.value,
                    target_region=target_region.value,
                )
            elif mechanism in {TransferMechanism.SCCS, TransferMechanism.BCRS}:
                # Requires TIA per Schrems II
                request.tia_required = True
                logger.info(
                    "transfer_requires_tia",
                    request_id=request.id,
                    mechanism=mechanism.value,
                )
            elif mechanism == TransferMechanism.CAC_ASSESSMENT:
                # China CAC assessment required
                request.tia_required = True
                logger.info(
                    "transfer_requires_cac",
                    request_id=request.id,
                )
        
        self._transfer_requests[request.id] = request
        return request
    
    def _determine_transfer_mechanism(
        self,
        source_jurisdiction: Jurisdiction,
        target_region: DataRegion,
    ) -> TransferMechanism:
        """Determine the appropriate transfer mechanism."""
        # Get target country code from region
        target_country = self._get_country_from_region(target_region)
        
        # Check for localization requirement
        if self.requires_localization(source_jurisdiction):
            if source_jurisdiction == Jurisdiction.RUSSIA:
                return TransferMechanism.PROHIBITED
            elif source_jurisdiction == Jurisdiction.CHINA:
                return TransferMechanism.CAC_ASSESSMENT
        
        # EU transfers
        if source_jurisdiction in {Jurisdiction.EU, Jurisdiction.UK}:
            if target_country in self._adequacy_countries:
                return TransferMechanism.ADEQUACY
            else:
                return TransferMechanism.SCCS
        
        # LGPD transfers
        if source_jurisdiction == Jurisdiction.BRAZIL:
            return TransferMechanism.SCCS
        
        # Default - allow with SCCs
        return TransferMechanism.SCCS
    
    def _get_country_from_region(self, region: DataRegion) -> str:
        """Extract country code from region."""
        region_countries = {
            DataRegion.US_EAST: "us",
            DataRegion.US_WEST: "us",
            DataRegion.CA_CENTRAL: "ca",
            DataRegion.EU_WEST: "ie",
            DataRegion.EU_CENTRAL: "de",
            DataRegion.EU_NORTH: "se",
            DataRegion.AP_SOUTHEAST: "sg",
            DataRegion.AP_NORTHEAST: "jp",
            DataRegion.AP_SOUTH: "in",
            DataRegion.CN_NORTH: "cn",
            DataRegion.CN_NORTHWEST: "cn",
            DataRegion.SA_EAST: "br",
            DataRegion.ME_SOUTH: "bh",
            DataRegion.AF_SOUTH: "za",
        }
        return region_countries.get(region, "unknown")
    
    async def approve_transfer(
        self,
        request_id: str,
        approver_id: str,
        mechanism_reference: str | None = None,
    ) -> TransferRequest:
        """Manually approve a transfer request."""
        request = self._transfer_requests.get(request_id)
        if not request:
            raise ValueError(f"Transfer request not found: {request_id}")
        
        if request.tia_required and not request.tia_completed:
            raise ValueError("TIA must be completed before approval")
        
        request.approved = True
        request.approved_by = approver_id
        request.approved_at = datetime.now(UTC)
        request.mechanism_reference = mechanism_reference
        
        logger.info(
            "transfer_approved",
            request_id=request_id,
            approver=approver_id,
        )
        
        return request
    
    async def complete_tia(
        self,
        request_id: str,
        destination_country: str,
        surveillance_laws_assessed: bool,
        government_access_risk: str,
        supplementary_measures: list[str],
        technical_measures: list[str],
        organizational_measures: list[str],
        transfer_permitted: bool,
        conditions: list[str],
        assessor_id: str,
    ) -> TransferImpactAssessment:
        """
        Complete a Transfer Impact Assessment.
        
        Per Schrems II requirements for transfers to third countries.
        """
        request = self._transfer_requests.get(request_id)
        if not request:
            raise ValueError(f"Transfer request not found: {request_id}")
        
        tia = TransferImpactAssessment(
            transfer_request_id=request_id,
            destination_country=destination_country,
            destination_region=request.target_region,
            data_categories=[request.data_classification],
            surveillance_laws_assessed=surveillance_laws_assessed,
            government_access_risk=government_access_risk,
            supplementary_measures=supplementary_measures,
            technical_measures=technical_measures,
            organizational_measures=organizational_measures,
            transfer_permitted=transfer_permitted,
            conditions=conditions,
            assessed_by=assessor_id,
            assessed_at=datetime.now(UTC),
        )
        
        # Update transfer request
        request.tia_completed = True
        request.tia_reference = tia.id
        
        self._tias[tia.id] = tia
        
        logger.info(
            "tia_completed",
            tia_id=tia.id,
            request_id=request_id,
            transfer_permitted=transfer_permitted,
        )
        
        return tia
    
    # ───────────────────────────────────────────────────────────────
    # SCC MANAGEMENT
    # ───────────────────────────────────────────────────────────────
    
    def get_scc_template(
        self,
        transfer_type: str,
    ) -> dict[str, Any]:
        """
        Get appropriate SCC template.
        
        Per EU 2021/914 Commission Implementing Decision.
        """
        templates = {
            "controller_to_controller": {
                "module": "Module One",
                "clauses": [
                    "Clause 1: Purpose and scope",
                    "Clause 2: Invariability of the Clauses",
                    "Clause 3: Third-party beneficiaries",
                    "Clause 4: Interpretation",
                    "Clause 5: Hierarchy",
                    "Clause 6: Description of the transfer(s)",
                    "Clause 7: Docking clause",
                    "Clause 8: Data protection safeguards",
                    "Clause 9: Use of sub-processors",
                    "Clause 10: Data subject rights",
                    "Clause 11: Redress",
                    "Clause 12: Liability",
                    "Clause 13: Supervision",
                    "Clause 14: Local laws and practices",
                    "Clause 15: Obligations of the data importer",
                    "Clause 16: Non-compliance and termination",
                    "Clause 17: Governing law",
                    "Clause 18: Choice of forum and jurisdiction",
                ],
                "annexes": [
                    "Annex I: List of parties",
                    "Annex II: Technical and organisational measures",
                ],
            },
            "controller_to_processor": {
                "module": "Module Two",
                "clauses": [
                    # Similar structure with processor-specific clauses
                ],
            },
            "processor_to_processor": {
                "module": "Module Three",
                "clauses": [],
            },
            "processor_to_controller": {
                "module": "Module Four",
                "clauses": [],
            },
        }
        
        return templates.get(transfer_type, templates["controller_to_processor"])


# Global service instance
_residency_service: DataResidencyService | None = None


def get_data_residency_service() -> DataResidencyService:
    """Get the global data residency service instance."""
    global _residency_service
    if _residency_service is None:
        _residency_service = DataResidencyService()
    return _residency_service
