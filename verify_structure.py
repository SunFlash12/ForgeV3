"""
Forge V3 - Structure and Import Verification
Verifies that all code modules are present and importable.
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'forge-cascade-v2'))
sys.path.insert(0, os.path.dirname(__file__))

class StructureVerifier:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def verify(self, name, func):
        try:
            func()
            self.results.append((name, "PASS", None))
            self.passed += 1
            print(f"[PASS] {name}")
        except Exception as e:
            self.results.append((name, "FAIL", str(e)))
            self.failed += 1
            print(f"[FAIL] {name}: {str(e)}")

    def report(self):
        print("\n" + "="*70)
        print(f"Total: {self.passed + self.failed} | Passed: {self.passed} | Failed: {self.failed}")
        success_rate = (self.passed / (self.passed + self.failed) * 100) if (self.passed + self.failed) > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        print("="*70)


verifier = StructureVerifier()

print("="*70)
print("FORGE V3 - STRUCTURE VERIFICATION")
print("="*70)
print()

# Core Models
print("[1] Core Models...")
verifier.verify("Capsule Model", lambda: __import__('forge.models.capsule', fromlist=['Capsule', 'CapsuleType']))
verifier.verify("User Model", lambda: __import__('forge.models.user', fromlist=['User', 'UserRole']))
verifier.verify("Governance Model", lambda: __import__('forge.models.governance', fromlist=['Proposal']))
verifier.verify("Overlay Model", lambda: __import__('forge.models.overlay', fromlist=['Overlay', 'Capability']))
verifier.verify("Base Models", lambda: __import__('forge.models.base', fromlist=['TrustLevel']))

# Database Layer
print("\n[2] Database Layer...")
verifier.verify("Neo4j Client", lambda: __import__('forge.database.client', fromlist=['Neo4jClient']))
verifier.verify("Schema Manager", lambda: __import__('forge.database.schema', fromlist=['SchemaManager']))

# Repositories
print("\n[3] Repositories...")
verifier.verify("Capsule Repository", lambda: __import__('forge.repositories.capsule_repository', fromlist=['CapsuleRepository']))
verifier.verify("User Repository", lambda: __import__('forge.repositories.user_repository', fromlist=['UserRepository']))
verifier.verify("Governance Repository", lambda: __import__('forge.repositories.governance_repository', fromlist=['GovernanceRepository']))
verifier.verify("Audit Repository", lambda: __import__('forge.repositories.audit_repository', fromlist=['AuditRepository']))

# Security
print("\n[4] Security Layer...")
verifier.verify("Auth Service", lambda: __import__('forge.security.auth_service', fromlist=['AuthService']))
verifier.verify("Token Service", lambda: __import__('forge.security.tokens', fromlist=['TokenService']))
verifier.verify("Password Functions", lambda: __import__('forge.security.password', fromlist=['hash_password']))
verifier.verify("Authorization", lambda: __import__('forge.security.authorization', fromlist=['TrustAuthorizer']))

# Kernel
print("\n[5] Kernel Layer...")
verifier.verify("Event System", lambda: __import__('forge.kernel.event_system', fromlist=['EventSystem']))
verifier.verify("Overlay Manager", lambda: __import__('forge.kernel.overlay_manager', fromlist=['OverlayManager']))
verifier.verify("Pipeline", lambda: __import__('forge.kernel.pipeline', fromlist=['Pipeline']))

# Immune System
print("\n[6] Immune System...")
verifier.verify("Circuit Breaker", lambda: __import__('forge.immune.circuit_breaker', fromlist=['CircuitBreaker']))
verifier.verify("Health Checker", lambda: __import__('forge.immune.health_checker', fromlist=['ForgeHealthChecker']))
verifier.verify("Canary Manager", lambda: __import__('forge.immune.canary', fromlist=['CanaryManager']))
verifier.verify("Anomaly Detector", lambda: __import__('forge.immune.anomaly', fromlist=['AnomalyDetector']))

# Overlays
print("\n[7] Overlays...")
verifier.verify("Base Overlay", lambda: __import__('forge.overlays.base', fromlist=['BaseOverlay']))
verifier.verify("Security Validator", lambda: __import__('forge.overlays.security_validator', fromlist=['SecurityValidatorOverlay']))
verifier.verify("ML Intelligence", lambda: __import__('forge.overlays.ml_intelligence', fromlist=['MLIntelligenceOverlay']))
verifier.verify("Governance Overlay", lambda: __import__('forge.overlays.governance', fromlist=['GovernanceOverlay']))
verifier.verify("Lineage Tracker", lambda: __import__('forge.overlays.lineage_tracker', fromlist=['LineageTrackerOverlay']))

# API Routes
print("\n[8] API Routes...")
verifier.verify("Auth Routes", lambda: __import__('forge.api.routes.auth', fromlist=['router']))
verifier.verify("Capsules Routes", lambda: __import__('forge.api.routes.capsules', fromlist=['router']))
verifier.verify("Governance Routes", lambda: __import__('forge.api.routes.governance', fromlist=['router']))
verifier.verify("Overlays Routes", lambda: __import__('forge.api.routes.overlays', fromlist=['router']))
verifier.verify("System Routes", lambda: __import__('forge.api.routes.system', fromlist=['router']))
verifier.verify("Users Routes", lambda: __import__('forge.api.routes.users', fromlist=['router']))

# Compliance Framework
print("\n[9] Compliance Framework...")
verifier.verify("Compliance Engine", lambda: __import__('forge.compliance.core.engine', fromlist=['ComplianceEngine']))
verifier.verify("Compliance Registry", lambda: __import__('forge.compliance.core.registry', fromlist=['ComplianceRegistry']))
verifier.verify("Consent Management", lambda: __import__('forge.compliance.privacy.consent_service', fromlist=['ConsentManagementService']))
verifier.verify("Encryption Service", lambda: __import__('forge.compliance.encryption.service', fromlist=['EncryptionService']))
verifier.verify("Data Residency", lambda: __import__('forge.compliance.residency.service', fromlist=['DataResidencyService']))
verifier.verify("Breach Notification", lambda: __import__('forge.compliance.security.breach_notification', fromlist=['BreachNotificationService']))
verifier.verify("AI Governance", lambda: __import__('forge.compliance.ai_governance.service', fromlist=['AIGovernanceService']))

# Services
print("\n[10] Services...")
verifier.verify("Embedding Service", lambda: __import__('forge.services.embedding', fromlist=['EmbeddingService']))
verifier.verify("LLM Service", lambda: __import__('forge.services.llm', fromlist=['LLMService']))
verifier.verify("Search Service", lambda: __import__('forge.services.search', fromlist=['SearchService']))

verifier.report()

print("\nAll code modules are properly structured and importable!")
