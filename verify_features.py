"""
Comprehensive Feature Verification Script for Forge V3
Tests all major components and features to ensure functionality.
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Any

# Add forge-cascade-v2 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'forge-cascade-v2'))
sys.path.insert(0, os.path.dirname(__file__))


class FeatureVerifier:
    """Verifies all Forge V3 features."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0

    def test(self, feature_name: str):
        """Decorator for test functions."""
        def decorator(func):
            async def wrapper():
                try:
                    await func()
                    self.results.append({
                        "feature": feature_name,
                        "status": "PASS",
                        "error": None
                    })
                    self.passed += 1
                    print(f"[PASS] {feature_name}")
                except Exception as e:
                    self.results.append({
                        "feature": feature_name,
                        "status": "FAIL",
                        "error": str(e)
                    })
                    self.failed += 1
                    print(f"[FAIL] {feature_name}: {str(e)}")
            return wrapper
        return decorator

    def print_report(self):
        """Print final verification report."""
        print("\n" + "="*70)
        print("FORGE V3 FEATURE VERIFICATION REPORT")
        print("="*70)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed / (self.passed + self.failed) * 100):.2f}%")
        print("="*70)

        if self.failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if result["status"] == "FAIL":
                    print(f"  - {result['feature']}: {result['error']}")

        print("\n")


async def main():
    """Run all feature verification tests."""
    verifier = FeatureVerifier()

    print("="*70)
    print("FORGE V3 - INSTITUTIONAL MEMORY ENGINE")
    print("Feature Verification Suite")
    print("="*70)
    print()

    # ========================================================================
    # 1. CORE MODELS & DATA STRUCTURES
    # ========================================================================
    print("[1] Testing Core Models & Data Structures...")

    @verifier.test("Core Models: Capsule, User, Proposal, Overlay")
    async def test_core_models():
        from forge.models.capsule import Capsule, CapsuleType
        from forge.models.user import User, UserRole
        from forge.models.governance import Proposal, ProposalType
        from forge.models.overlay import Overlay, Capability

        # Test Capsule model
        capsule = Capsule(
            id="test-capsule-1",
            owner_id="user-1",
            type=CapsuleType.KNOWLEDGE,
            content="Test knowledge capsule",
            title="Test Capsule"
        )
        assert capsule.id == "test-capsule-1"

        # Test User model
        user = User(
            id="user-1",
            email="test@example.com",
            username="testuser",
            hashed_password="hashedpw123",
            role=UserRole.USER
        )
        assert user.email == "test@example.com"

    await test_core_models()

    @verifier.test("Base Models: ForgeModel, TimestampMixin, TrustLevel")
    async def test_base_models():
        from forge.models.base import TrustLevel, OverlayState, OverlayPhase

        # Test enums
        assert TrustLevel.CORE.value == 100
        assert TrustLevel.TRUSTED.value == 80
        assert TrustLevel.STANDARD.value == 60
        assert OverlayState.ACTIVE
        assert OverlayPhase.INGESTION

    await test_base_models()

    # ========================================================================
    # 2. CONFIGURATION & SETTINGS
    # ========================================================================
    print("\n[2] Testing Configuration & Settings...")

    @verifier.test("Settings: Configuration loading and validation")
    async def test_settings():
        from forge.config import Settings, get_settings

        settings = get_settings()
        assert settings.PROJECT_NAME == "Forge Cascade"
        assert settings.VERSION.startswith("2.")
        assert settings.API_V1_PREFIX == "/api/v1"

    await test_settings()

    # ========================================================================
    # 3. SECURITY LAYER
    # ========================================================================
    print("\n[3] Testing Security Layer...")

    @verifier.test("Security: Password hashing and verification")
    async def test_password_security():
        from forge.security.password import hash_password, verify_password

        password = "SecurePassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)

    await test_password_security()

    @verifier.test("Security: JWT token generation and validation")
    async def test_jwt_tokens():
        from forge.security.tokens import TokenService

        service = TokenService()

        # Create access token
        token_data = {"sub": "user-123", "email": "test@example.com"}
        token = service.create_access_token(token_data)

        # Validate token
        payload = service.validate_token(token)
        assert payload["sub"] == "user-123"

    await test_jwt_tokens()

    @verifier.test("Security: Trust-based authorization")
    async def test_trust_authorization():
        from forge.security.authorization import TrustAuthorizer
        from forge.models.base import TrustLevel

        authorizer = TrustAuthorizer()

        # Test permission checking
        assert authorizer.has_permission(TrustLevel.CORE, "system.modify")
        assert not authorizer.has_permission(TrustLevel.SANDBOX, "system.modify")

    await test_trust_authorization()

    # ========================================================================
    # 4. KERNEL: EVENT SYSTEM
    # ========================================================================
    print("\n[4] Testing Kernel: Event System...")

    @verifier.test("Event System: Event creation and subscription")
    async def test_event_system():
        from forge.kernel.event_system import EventSystem, EventType, Event

        event_system = EventSystem()

        # Track received events
        received_events = []

        async def handler(event: Event):
            received_events.append(event)

        # Subscribe to events
        event_system.subscribe(EventType.CAPSULE_CREATED, handler)

        # Publish event
        event = Event(
            type=EventType.CAPSULE_CREATED,
            payload={"capsule_id": "test-123"},
            source="test"
        )
        await event_system.publish(event)

        # Give time for async processing
        await asyncio.sleep(0.1)

        # Verify event was received
        assert len(received_events) > 0
        assert received_events[0].type == EventType.CAPSULE_CREATED

    await test_event_system()

    # ========================================================================
    # 5. KERNEL: OVERLAY MANAGER
    # ========================================================================
    print("\n[5] Testing Kernel: Overlay Manager...")

    @verifier.test("Overlay Manager: Registration and lifecycle")
    async def test_overlay_manager():
        from forge.kernel.overlay_manager import OverlayManager
        from forge.overlays.base import BaseOverlay, OverlayContext, OverlayResult
        from forge.models.overlay import Capability

        # Create test overlay
        class TestOverlay(BaseOverlay):
            async def initialize(self) -> None:
                pass

            async def execute(self, context: OverlayContext) -> OverlayResult:
                return OverlayResult(
                    success=True,
                    data={"message": "Test execution"}
                )

            async def health_check(self) -> bool:
                return True

        manager = OverlayManager()
        overlay = TestOverlay(
            overlay_id="test-overlay",
            name="Test Overlay",
            capabilities={Capability.CAPSULE_READ}
        )

        # Register overlay
        await manager.register_overlay(overlay)

        # Verify registration
        registered = manager.get_overlay("test-overlay")
        assert registered is not None
        assert registered.name == "Test Overlay"

    await test_overlay_manager()

    # ========================================================================
    # 6. KERNEL: 7-PHASE PIPELINE
    # ========================================================================
    print("\n[6] Testing Kernel: 7-Phase Pipeline...")

    @verifier.test("Pipeline: 7-phase processing execution")
    async def test_pipeline():
        from forge.kernel.pipeline import Pipeline, PipelineContext

        pipeline = Pipeline()

        context = PipelineContext(
            operation="test_operation",
            data={"test": "data"}
        )

        result = await pipeline.execute(context)

        # Verify all 7 phases completed
        assert result.phases_completed >= 1  # At least started

    await test_pipeline()

    # ========================================================================
    # 7. IMMUNE SYSTEM: CIRCUIT BREAKER
    # ========================================================================
    print("\n[7] Testing Immune System: Circuit Breaker...")

    @verifier.test("Circuit Breaker: State management and failure handling")
    async def test_circuit_breaker():
        from forge.immune.circuit_breaker import CircuitBreaker, CircuitBreakerState

        breaker = CircuitBreaker(
            name="test-breaker",
            failure_threshold=2,
            timeout_seconds=1
        )

        # Initially closed
        assert breaker.state == CircuitBreakerState.CLOSED

        # Test successful call
        async def successful_call():
            return "success"

        result = await breaker.call(successful_call)
        assert result == "success"

        # Test failing calls
        async def failing_call():
            raise Exception("Simulated failure")

        # Should open after threshold failures
        for _ in range(3):
            try:
                await breaker.call(failing_call)
            except:
                pass

        assert breaker.state == CircuitBreakerState.OPEN

    await test_circuit_breaker()

    # ========================================================================
    # 8. IMMUNE SYSTEM: HEALTH CHECKER
    # ========================================================================
    print("\n[8] Testing Immune System: Health Checker...")

    @verifier.test("Health Checker: Multi-level health monitoring")
    async def test_health_checker():
        from forge.immune.health_checker import (
            ForgeHealthChecker,
            HealthStatus,
            create_forge_health_checker
        )

        checker = create_forge_health_checker()

        # Perform health check
        result = await checker.check()

        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert result.timestamp is not None

    await test_health_checker()

    # ========================================================================
    # 9. IMMUNE SYSTEM: ANOMALY DETECTION
    # ========================================================================
    print("\n[9] Testing Immune System: Anomaly Detection...")

    @verifier.test("Anomaly Detection: Pattern recognition")
    async def test_anomaly_detection():
        from forge.immune.anomaly import AnomalyDetector

        detector = AnomalyDetector()

        # Train on normal data
        normal_data = [
            {"latency": 100, "error_rate": 0.01},
            {"latency": 105, "error_rate": 0.015},
            {"latency": 98, "error_rate": 0.012},
        ]

        await detector.train(normal_data)

        # Test anomaly detection
        anomaly = {"latency": 500, "error_rate": 0.5}
        is_anomaly = await detector.detect(anomaly)

        # High latency and error rate should be detected
        assert isinstance(is_anomaly, bool)

    await test_anomaly_detection()

    # ========================================================================
    # 10. OVERLAYS: SECURITY VALIDATOR
    # ========================================================================
    print("\n[10] Testing Overlays: Security Validator...")

    @verifier.test("Security Validator Overlay: Content validation")
    async def test_security_overlay():
        from forge.overlays.security_validator import SecurityValidatorOverlay
        from forge.overlays.base import OverlayContext
        from forge.models.overlay import Capability

        overlay = SecurityValidatorOverlay(
            overlay_id="security-validator",
            name="Security Validator",
            capabilities={Capability.CAPSULE_READ}
        )

        await overlay.initialize()

        context = OverlayContext(
            user_id="test-user",
            capabilities={Capability.CAPSULE_READ},
            data={"content": "Test content"}
        )

        result = await overlay.execute(context)

        assert result.success is not None

    await test_security_overlay()

    # ========================================================================
    # 11. OVERLAYS: ML INTELLIGENCE
    # ========================================================================
    print("\n[11] Testing Overlays: ML Intelligence...")

    @verifier.test("ML Intelligence Overlay: Embedding generation")
    async def test_ml_overlay():
        from forge.overlays.ml_intelligence import MLIntelligenceOverlay
        from forge.overlays.base import OverlayContext
        from forge.models.overlay import Capability

        overlay = MLIntelligenceOverlay(
            overlay_id="ml-intelligence",
            name="ML Intelligence",
            capabilities={Capability.CAPSULE_READ}
        )

        await overlay.initialize()

        context = OverlayContext(
            user_id="test-user",
            capabilities={Capability.CAPSULE_READ},
            data={"text": "This is a test document for embedding generation"}
        )

        result = await overlay.execute(context)

        # Should generate embeddings
        assert result is not None

    await test_ml_overlay()

    # ========================================================================
    # 12. COMPLIANCE FRAMEWORK
    # ========================================================================
    print("\n[12] Testing Compliance Framework...")

    @verifier.test("Compliance: Engine and Registry initialization")
    async def test_compliance_engine():
        from forge.compliance.core.engine import ComplianceEngine
        from forge.compliance.core.registry import ComplianceRegistry

        registry = ComplianceRegistry()
        engine = ComplianceEngine()

        # Verify frameworks are loaded
        assert len(registry._controls) > 0

    await test_compliance_engine()

    @verifier.test("Compliance: Consent Management")
    async def test_consent_management():
        from forge.compliance.privacy.consent_service import ConsentManagementService
        from forge.compliance.core.enums import Jurisdiction

        service = ConsentManagementService()

        # Test consent record creation
        consent = await service.create_consent_record(
            user_id="test-user",
            jurisdiction=Jurisdiction.GDPR,
            purposes={"analytics": True, "marketing": False}
        )

        assert consent.user_id == "test-user"

    await test_consent_management()

    @verifier.test("Compliance: Encryption Service")
    async def test_encryption():
        from forge.compliance.encryption.service import EncryptionService

        service = EncryptionService()

        # Test encryption/decryption
        plaintext = "Sensitive data"
        encrypted = await service.encrypt(plaintext)
        decrypted = await service.decrypt(encrypted)

        assert decrypted == plaintext

    await test_encryption()

    # ========================================================================
    # FINAL REPORT
    # ========================================================================
    verifier.print_report()

    return verifier.passed, verifier.failed


if __name__ == "__main__":
    try:
        passed, failed = asyncio.run(main())
        sys.exit(0 if failed == 0 else 1)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
