"""
Forge Compliance Framework - Security Module

Implements security controls per SOC 2, ISO 27001, NIST:
- Access Control (RBAC/ABAC)
- Authentication and MFA
- Breach Notification
- Vendor Management
"""

from forge.compliance.security.access_control import (
    AccessControlService,
    AccessDecision,
    AttributePolicy,
    AuthenticationService,
    MFAChallenge,
    MFAMethod,
    PasswordPolicy,
    PasswordService,
    Permission,
    ResourceType,
    Role,
    Session,
    get_access_control_service,
    get_authentication_service,
)
from forge.compliance.security.breach_notification import (
    BreachIncident,
    BreachNotificationService,
    BreachStatus,
    BreachType,
    JurisdictionDeadline,
    NotificationRecipient,
    NotificationRecord,
    NotificationStatus,
    get_breach_notification_service,
)
from forge.compliance.security.vendor_management import (
    AssessmentStatus,
    SecurityAssessment,
    VendorCategory,
    VendorContract,
    VendorIncident,
    VendorProfile,
    VendorRiskLevel,
    VendorRiskManagementService,
    VendorStatus,
    get_vendor_risk_service,
)

# Aliases for consistency
VendorManagementService = VendorRiskManagementService
get_vendor_management_service = get_vendor_risk_service
VendorRiskTier = VendorRiskLevel  # Alias
VendorAssessment = SecurityAssessment  # Alias
Vendor = VendorProfile  # Alias
DPARecord = VendorContract  # Alias

__all__ = [
    # Access Control
    "AccessControlService",
    "get_access_control_service",
    "AuthenticationService",
    "get_authentication_service",
    "Permission",
    "ResourceType",
    "Role",
    "AttributePolicy",
    "AccessDecision",
    "MFAMethod",
    "MFAChallenge",
    "Session",
    "PasswordPolicy",
    "PasswordService",
    # Breach Notification
    "BreachNotificationService",
    "get_breach_notification_service",
    "BreachType",
    "BreachStatus",
    "NotificationStatus",
    "NotificationRecipient",
    "BreachIncident",
    "NotificationRecord",
    "JurisdictionDeadline",
    # Vendor Management
    "VendorRiskManagementService",
    "VendorManagementService",
    "get_vendor_risk_service",
    "get_vendor_management_service",
    "VendorRiskLevel",
    "VendorRiskTier",
    "VendorStatus",
    "VendorCategory",
    "AssessmentStatus",
    "VendorProfile",
    "Vendor",
    "VendorContract",
    "DPARecord",
    "SecurityAssessment",
    "VendorAssessment",
    "VendorIncident",
]
