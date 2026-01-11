"""
Forge Compliance Framework - Core Module

Core components for the compliance framework including:
- Configuration
- Enumerations
- Models
- Registry
- Engine
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
    EncryptionStandard,
    KeyRotationPolicy,
    AccessControlModel,
)
from forge.compliance.core.models import (
    ComplianceStatus,
    ControlStatus,
    AuditEvent,
    AuditChain,
    DataSubjectRequest,
    DSARVerification,
    ConsentRecord,
    BreachNotification,
    AffectedIndividual,
    RegulatoryNotification,
    AISystemRegistration,
    AIDecisionLog,
    ComplianceReport,
)
from forge.compliance.core.registry import (
    ControlDefinition,
    ComplianceRegistry,
    get_compliance_registry,
)
from forge.compliance.core.engine import (
    ComplianceEngine,
    get_compliance_engine,
)
from forge.compliance.core.repository import (
    ComplianceRepository,
    get_compliance_repository,
    initialize_compliance_repository,
)

__all__ = [
    # Config
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
    "EncryptionStandard",
    "KeyRotationPolicy",
    "AccessControlModel",
    # Models
    "ComplianceStatus",
    "ControlStatus",
    "AuditEvent",
    "AuditChain",
    "DataSubjectRequest",
    "DSARVerification",
    "ConsentRecord",
    "BreachNotification",
    "AffectedIndividual",
    "RegulatoryNotification",
    "AISystemRegistration",
    "AIDecisionLog",
    "ComplianceReport",
    # Registry
    "ControlDefinition",
    "ComplianceRegistry",
    "get_compliance_registry",
    # Engine
    "ComplianceEngine",
    "get_compliance_engine",
    # Repository
    "ComplianceRepository",
    "get_compliance_repository",
    "initialize_compliance_repository",
]
