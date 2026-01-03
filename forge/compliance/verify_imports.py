#!/usr/bin/env python3
"""
Forge Compliance Framework - Import Verification Script

Verifies all modules can be imported successfully.
"""

import sys
from typing import Tuple


def test_import(module_path: str, items: list[str] = None) -> Tuple[bool, str]:
    """Test importing a module and optionally specific items."""
    try:
        module = __import__(module_path, fromlist=items or [''])
        if items:
            for item in items:
                getattr(module, item)
        return True, f"✓ {module_path}"
    except Exception as e:
        return False, f"✗ {module_path}: {e}"


def main():
    """Run all import tests."""
    print("=" * 60)
    print("Forge Compliance Framework - Import Verification")
    print("=" * 60)
    print()
    
    results = []
    
    # Core imports
    print("Testing Core Imports...")
    results.append(test_import("forge.compliance.core.config", ["ComplianceConfig", "get_compliance_config"]))
    results.append(test_import("forge.compliance.core.enums", [
        "Jurisdiction", "ComplianceFramework", "DataClassification",
        "AIRiskClassification", "BreachSeverity"
    ]))
    results.append(test_import("forge.compliance.core.models", [
        "DataSubjectRequest", "ConsentRecord", "BreachNotification",
        "ComplianceReport", "AuditEvent"
    ]))
    results.append(test_import("forge.compliance.core.registry", ["ComplianceRegistry", "get_compliance_registry"]))
    results.append(test_import("forge.compliance.core.engine", ["ComplianceEngine", "get_compliance_engine"]))
    print()
    
    # Encryption
    print("Testing Encryption Module...")
    results.append(test_import("forge.compliance.encryption", [
        "EncryptionService", "get_encryption_service"
    ]))
    print()
    
    # Residency
    print("Testing Data Residency Module...")
    results.append(test_import("forge.compliance.residency", [
        "DataResidencyService", "get_data_residency_service"
    ]))
    print()
    
    # Privacy
    print("Testing Privacy Module...")
    results.append(test_import("forge.compliance.privacy", [
        "get_dsar_processor", "get_consent_service"
    ]))
    print()
    
    # Security
    print("Testing Security Module...")
    results.append(test_import("forge.compliance.security", [
        "get_access_control_service", "get_authentication_service",
        "get_breach_notification_service", "get_vendor_management_service"
    ]))
    print()
    
    # AI Governance
    print("Testing AI Governance Module...")
    results.append(test_import("forge.compliance.ai_governance", [
        "AIGovernanceService", "get_ai_governance_service"
    ]))
    print()
    
    # Industry
    print("Testing Industry Module...")
    results.append(test_import("forge.compliance.industry", [
        "get_hipaa_service", "get_pci_service", "get_coppa_service"
    ]))
    print()
    
    # Reporting
    print("Testing Reporting Module...")
    results.append(test_import("forge.compliance.reporting", [
        "ComplianceReportingService", "get_compliance_reporting_service"
    ]))
    print()
    
    # Accessibility
    print("Testing Accessibility Module...")
    results.append(test_import("forge.compliance.accessibility", [
        "AccessibilityComplianceService", "get_accessibility_service"
    ]))
    print()
    
    # API
    print("Testing API Module...")
    results.append(test_import("forge.compliance.api", [
        "compliance_router", "extended_router"
    ]))
    print()
    
    # Main module
    print("Testing Main Module...")
    results.append(test_import("forge.compliance", [
        "get_compliance_engine", "get_compliance_config"
    ]))
    print()
    
    # Print results
    print("=" * 60)
    print("Results:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for success, message in results:
        print(message)
        if success:
            passed += 1
        else:
            failed += 1
    
    print()
    print("=" * 60)
    print(f"Total: {passed + failed} tests, {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
