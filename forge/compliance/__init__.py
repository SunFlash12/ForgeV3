"""
Forge Global Compliance Framework

Comprehensive compliance infrastructure implementing 400+ technical controls
across 25+ regulatory frameworks for global operation.

Frameworks Covered:
- Privacy: GDPR, CCPA/CPRA, LGPD, PIPL, PDPA, Quebec Law 25, DPDP, etc.
- Security: SOC 2, ISO 27001, NIST 800-53, CIS Controls, FedRAMP
- Industry: HIPAA, PCI-DSS 4.0.1, COPPA, FERPA, GLBA
- AI Governance: EU AI Act, Colorado AI Act, NYC Local Law 144
- Accessibility: WCAG 2.2, EAA, EN 301 549, ADA

Usage:
    from forge.compliance import get_compliance_engine
    
    engine = get_compliance_engine()
    await engine.initialize()
    
Services:
    # Core
    from forge.compliance import get_compliance_engine, get_compliance_config
    
    # Encryption & Data
    from forge.compliance.encryption import get_encryption_service
    from forge.compliance.residency import get_data_residency_service
    
    # Privacy
    from forge.compliance.privacy import get_consent_service, get_dsar_processor
    
    # Security
    from forge.compliance.security import (
        get_access_control_service,
        get_authentication_service,
        get_breach_notification_service,
        get_vendor_management_service,
    )
    
    # AI Governance
    from forge.compliance.ai_governance import get_ai_governance_service
    
    # Industry
    from forge.compliance.industry import get_hipaa_service, get_pci_service, get_coppa_service
    
    # Reporting & Accessibility
    from forge.compliance.reporting import get_compliance_reporting_service
    from forge.compliance.accessibility import get_accessibility_service
"""

from forge.compliance.core.config import ComplianceConfig, get_compliance_config
from forge.compliance.core.enums import (
    Jurisdiction,
    ComplianceFramework,
    DataClassification,
    RiskLevel,
    ConsentType,
    DSARType,
    BreachSeverity,
    AIRiskClassification,
    AuditEventCategory,
    AccessControlModel,
)
from forge.compliance.core.models import (
    ComplianceStatus,
    ControlStatus,
    AuditEvent,
    DataSubjectRequest,
    ConsentRecord,
    BreachNotification,
    ComplianceReport,
    AISystemRegistration,
    AIDecisionLog,
)
from forge.compliance.core.registry import ComplianceRegistry, get_compliance_registry
from forge.compliance.core.engine import ComplianceEngine, get_compliance_engine

# Service imports
from forge.compliance.encryption import get_encryption_service
from forge.compliance.residency import get_data_residency_service
from forge.compliance.privacy import get_consent_service, get_dsar_processor
from forge.compliance.security import (
    get_access_control_service,
    get_authentication_service,
    get_breach_notification_service,
    get_vendor_management_service,
)
from forge.compliance.ai_governance import get_ai_governance_service
from forge.compliance.industry import get_hipaa_service, get_pci_service, get_coppa_service
from forge.compliance.reporting import get_compliance_reporting_service
from forge.compliance.accessibility import get_accessibility_service

__all__ = [
    # Configuration
    "ComplianceConfig",
    "get_compliance_config",
    # Enums
    "Jurisdiction",
    "ComplianceFramework", 
    "DataClassification",
    "RiskLevel",
    "ConsentType",
    "DSARType",
    "BreachSeverity",
    "AIRiskClassification",
    "AuditEventCategory",
    "AccessControlModel",
    # Models
    "ComplianceStatus",
    "ControlStatus",
    "AuditEvent",
    "DataSubjectRequest",
    "ConsentRecord",
    "BreachNotification",
    "ComplianceReport",
    "AISystemRegistration",
    "AIDecisionLog",
    # Core
    "ComplianceRegistry",
    "get_compliance_registry",
    "ComplianceEngine",
    "get_compliance_engine",
    # Services
    "get_encryption_service",
    "get_data_residency_service",
    "get_consent_service",
    "get_dsar_processor",
    "get_access_control_service",
    "get_authentication_service",
    "get_breach_notification_service",
    "get_vendor_management_service",
    "get_ai_governance_service",
    "get_hipaa_service",
    "get_pci_service",
    "get_coppa_service",
    "get_compliance_reporting_service",
    "get_accessibility_service",
]

__version__ = "1.0.0"
