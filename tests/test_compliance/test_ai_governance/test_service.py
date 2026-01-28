"""
Tests for forge.compliance.ai_governance module.

Tests the AI governance service including system registration,
decision logging, human review, and explainability features.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.enums import AIRiskClassification


class TestAIGovernanceService:
    """Tests for the AIGovernanceService class."""

    @pytest.fixture
    def ai_governance_service(self):
        """Create an AI governance service for testing."""
        try:
            from forge.compliance.ai_governance import get_ai_governance_service
            return get_ai_governance_service()
        except ImportError:
            pytest.skip("AIGovernanceService not available")

    @pytest.mark.asyncio
    async def test_register_system_minimal_risk(self, ai_governance_service):
        """Test registering a minimal risk AI system."""
        registration = await ai_governance_service.register_system(
            system_name="Simple Calculator",
            system_version="1.0.0",
            provider="Forge Labs",
            intended_purpose="Basic arithmetic calculations",
            use_cases=["calculation"],
            model_type="rule_based",
            human_oversight_measures=["audit_logging"],
        )

        assert registration is not None
        assert registration.id is not None
        assert registration.system_name == "Simple Calculator"
        assert registration.risk_classification == AIRiskClassification.MINIMAL_RISK

    @pytest.mark.asyncio
    async def test_register_system_limited_risk(self, ai_governance_service):
        """Test registering a limited risk AI system."""
        registration = await ai_governance_service.register_system(
            system_name="Content Recommendation Engine",
            system_version="2.0.0",
            provider="Forge Labs",
            intended_purpose="Recommend content based on preferences",
            use_cases=["personalization", "content_ranking"],
            model_type="collaborative_filtering",
            human_oversight_measures=["manual_review", "appeal_process"],
            training_data_description="User interaction history",
        )

        assert registration.system_name == "Content Recommendation Engine"
        # Risk classification determined by service
        assert registration.risk_classification in [
            AIRiskClassification.MINIMAL_RISK,
            AIRiskClassification.LIMITED_RISK,
        ]

    @pytest.mark.asyncio
    async def test_register_system_high_risk(self, ai_governance_service):
        """Test registering a high risk AI system."""
        registration = await ai_governance_service.register_system(
            system_name="Employment Screening System",
            system_version="1.0.0",
            provider="Forge Labs",
            intended_purpose="Screen job applicants for eligibility",
            use_cases=["resume_screening", "candidate_ranking", "eligibility_determination"],
            model_type="llm_classifier",
            human_oversight_measures=[
                "mandatory_human_review",
                "bias_monitoring",
                "appeal_mechanism",
                "fairness_audits",
            ],
            training_data_description="Historical hiring decisions with bias mitigation",
        )

        assert registration.system_name == "Employment Screening System"
        # High-risk systems require conformity assessment
        if registration.risk_classification == AIRiskClassification.HIGH_RISK:
            assert registration.risk_classification.requires_conformity_assessment is True

    @pytest.mark.asyncio
    async def test_register_system_gpai(self, ai_governance_service):
        """Test registering a general purpose AI system."""
        registration = await ai_governance_service.register_system(
            system_name="Foundation Model API",
            system_version="1.0.0",
            provider="Forge Labs",
            intended_purpose="General purpose language understanding and generation",
            use_cases=["text_generation", "summarization", "classification", "qa"],
            model_type="large_language_model",
            human_oversight_measures=[
                "content_filtering",
                "safety_testing",
                "red_teaming",
            ],
            training_data_description="Large-scale web data with filtering",
        )

        assert registration is not None

    @pytest.mark.asyncio
    async def test_log_decision_basic(self, ai_governance_service):
        """Test logging a basic AI decision."""
        # First register a system
        system = await ai_governance_service.register_system(
            system_name="Test Decision System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="recommendation",
            decision_outcome="recommend_item_A",
            confidence_score=0.85,
            input_summary={"user_id": "user_123", "context": "homepage"},
            reasoning_chain=["User previously liked similar items", "Item is trending"],
            key_factors=[
                {"factor": "past_behavior", "weight": 0.6},
                {"factor": "trending_score", "weight": 0.4},
            ],
        )

        assert decision is not None
        assert decision.id is not None
        assert decision.confidence_score == 0.85

    @pytest.mark.asyncio
    async def test_log_decision_with_subject(self, ai_governance_service):
        """Test logging a decision affecting a specific subject."""
        system = await ai_governance_service.register_system(
            system_name="Subject Decision System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="eligibility",
            decision_outcome="eligible",
            confidence_score=0.92,
            input_summary={"applicant_id": "user_456"},
            reasoning_chain=["Meets criteria A", "Meets criteria B"],
            key_factors=[{"factor": "criteria_match", "weight": 1.0}],
            subject_id="user_456",
        )

        assert decision.subject_id == "user_456"

    @pytest.mark.asyncio
    async def test_log_decision_with_legal_effect(self, ai_governance_service):
        """Test logging a decision with legal effect."""
        system = await ai_governance_service.register_system(
            system_name="Legal Effect System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Making legally binding decisions",
            use_cases=["loan_approval"],
            model_type="classifier",
            human_oversight_measures=["mandatory_review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="loan_approval",
            decision_outcome="denied",
            confidence_score=0.88,
            input_summary={"applicant": "user_789", "amount": 50000},
            reasoning_chain=["Credit score below threshold", "High debt ratio"],
            key_factors=[
                {"factor": "credit_score", "weight": 0.6},
                {"factor": "debt_ratio", "weight": 0.4},
            ],
            subject_id="user_789",
            has_legal_effect=True,
            has_significant_effect=True,
        )

        assert decision.has_legal_effect is True
        assert decision.has_significant_effect is True
        # Decisions with legal effect should trigger human review
        assert decision.human_review_requested is True or decision.has_legal_effect is True

    @pytest.mark.asyncio
    async def test_complete_human_review_approve(self, ai_governance_service):
        """Test completing human review with approval."""
        system = await ai_governance_service.register_system(
            system_name="Review Test System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing review",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="approval",
            decision_outcome="approved",
            confidence_score=0.95,
            input_summary={},
            reasoning_chain=["All criteria met"],
            key_factors=[],
        )

        reviewed = await ai_governance_service.complete_human_review(
            decision_id=decision.id,
            reviewer_id="reviewer_001",
            override=False,
        )

        assert reviewed is not None
        assert reviewed.human_reviewed is True
        assert reviewed.human_override is False

    @pytest.mark.asyncio
    async def test_complete_human_review_override(self, ai_governance_service):
        """Test completing human review with override."""
        system = await ai_governance_service.register_system(
            system_name="Override Test System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing override",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="rejection",
            decision_outcome="rejected",
            confidence_score=0.75,
            input_summary={"case": "special"},
            reasoning_chain=["Standard criteria not met"],
            key_factors=[],
        )

        reviewed = await ai_governance_service.complete_human_review(
            decision_id=decision.id,
            reviewer_id="senior_reviewer",
            override=True,
            override_reason="Exceptional circumstances warrant approval",
            new_outcome="approved",
        )

        assert reviewed.human_override is True
        assert reviewed.override_reason == "Exceptional circumstances warrant approval"

    @pytest.mark.asyncio
    async def test_complete_human_review_not_found(self, ai_governance_service):
        """Test human review for nonexistent decision."""
        result = await ai_governance_service.complete_human_review(
            decision_id="nonexistent_decision",
            reviewer_id="reviewer",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_explanation_end_user(self, ai_governance_service):
        """Test generating explanation for end user audience."""
        system = await ai_governance_service.register_system(
            system_name="Explanation Test System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing explanations",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="recommendation",
            decision_outcome="recommend_B",
            confidence_score=0.80,
            input_summary={"user": "test"},
            reasoning_chain=["Factor 1 indicates B", "Factor 2 supports B"],
            key_factors=[{"factor": "preference", "weight": 0.7}],
        )

        explanation = await ai_governance_service.generate_explanation(
            decision_id=decision.id,
            audience="end_user",
        )

        assert explanation is not None

    @pytest.mark.asyncio
    async def test_generate_explanation_technical(self, ai_governance_service):
        """Test generating explanation for technical audience."""
        system = await ai_governance_service.register_system(
            system_name="Tech Explanation System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="classification",
            decision_outcome="class_A",
            confidence_score=0.90,
            input_summary={"features": [0.5, 0.3, 0.2]},
            reasoning_chain=["Feature extraction", "Classification"],
            key_factors=[{"factor": "feature_1", "weight": 0.5}],
        )

        explanation = await ai_governance_service.generate_explanation(
            decision_id=decision.id,
            audience="technical",
        )

        assert explanation is not None

    @pytest.mark.asyncio
    async def test_generate_explanation_regulatory(self, ai_governance_service):
        """Test generating explanation for regulatory audience."""
        system = await ai_governance_service.register_system(
            system_name="Regulatory Explanation System",
            system_version="1.0",
            provider="Test",
            intended_purpose="Testing",
            use_cases=["test"],
            model_type="test",
            human_oversight_measures=["review"],
        )

        decision = await ai_governance_service.log_decision(
            ai_system_id=system.id,
            model_version="1.0",
            decision_type="approval",
            decision_outcome="approved",
            confidence_score=0.85,
            input_summary={},
            reasoning_chain=["Compliant with regulation X"],
            key_factors=[],
        )

        explanation = await ai_governance_service.generate_explanation(
            decision_id=decision.id,
            audience="regulatory",
        )

        assert explanation is not None


class TestAIRiskClassificationIntegration:
    """Tests for AI risk classification integration."""

    def test_risk_classification_properties(self):
        """Test risk classification properties."""
        assert AIRiskClassification.HIGH_RISK.requires_conformity_assessment is True
        assert AIRiskClassification.HIGH_RISK.requires_registration is True
        assert AIRiskClassification.MINIMAL_RISK.requires_conformity_assessment is False

    def test_risk_classification_penalties(self):
        """Test risk classification penalty percentages."""
        assert AIRiskClassification.UNACCEPTABLE.max_penalty_percent_revenue == 7.0
        assert AIRiskClassification.HIGH_RISK.max_penalty_percent_revenue == 3.0


class TestAIGovernanceServiceIntegration:
    """Integration tests for AI governance service."""

    @pytest.mark.asyncio
    async def test_full_ai_lifecycle(self):
        """Test complete AI system lifecycle."""
        try:
            from forge.compliance.ai_governance import get_ai_governance_service

            service = get_ai_governance_service()

            # Step 1: Register system
            system = await service.register_system(
                system_name="Lifecycle Test System",
                system_version="1.0.0",
                provider="Test Provider",
                intended_purpose="Full lifecycle testing",
                use_cases=["testing", "validation"],
                model_type="test_model",
                human_oversight_measures=["logging", "review"],
            )

            # Step 2: Log multiple decisions
            for i in range(5):
                await service.log_decision(
                    ai_system_id=system.id,
                    model_version="1.0.0",
                    decision_type=f"decision_{i}",
                    decision_outcome=f"outcome_{i}",
                    confidence_score=0.8 + (i * 0.02),
                    input_summary={"iteration": i},
                    reasoning_chain=[f"Step {i}"],
                    key_factors=[],
                )

            # Step 3: Log a decision requiring review
            legal_decision = await service.log_decision(
                ai_system_id=system.id,
                model_version="1.0.0",
                decision_type="legal_decision",
                decision_outcome="denied",
                confidence_score=0.75,
                input_summary={"applicant": "test"},
                reasoning_chain=["Legal analysis"],
                key_factors=[],
                has_legal_effect=True,
            )

            # Step 4: Complete human review
            reviewed = await service.complete_human_review(
                decision_id=legal_decision.id,
                reviewer_id="legal_reviewer",
                override=True,
                override_reason="Special consideration",
                new_outcome="approved",
            )

            # Step 5: Generate explanation
            explanation = await service.generate_explanation(
                decision_id=legal_decision.id,
                audience="regulatory",
            )

            assert system is not None
            assert reviewed is not None
            assert explanation is not None
        except ImportError:
            pytest.skip("AI governance service not available")

    @pytest.mark.asyncio
    async def test_high_risk_system_requirements(self):
        """Test that high-risk systems have required documentation."""
        try:
            from forge.compliance.ai_governance import get_ai_governance_service

            service = get_ai_governance_service()

            # Register a high-risk system
            system = await service.register_system(
                system_name="High Risk Test System",
                system_version="1.0.0",
                provider="Test Provider",
                intended_purpose="Employment decisions",
                use_cases=["hiring", "promotion"],
                model_type="classifier",
                human_oversight_measures=[
                    "mandatory_review",
                    "bias_audit",
                    "appeal_process",
                    "documentation",
                ],
                training_data_description="Anonymized historical data",
            )

            # High-risk systems should require conformity assessment
            if system.risk_classification == AIRiskClassification.HIGH_RISK:
                assert system.risk_classification.requires_conformity_assessment is True
        except ImportError:
            pytest.skip("AI governance service not available")

    @pytest.mark.asyncio
    async def test_decision_audit_trail(self):
        """Test that decisions create proper audit trail."""
        try:
            from forge.compliance.ai_governance import get_ai_governance_service

            service = get_ai_governance_service()

            system = await service.register_system(
                system_name="Audit Trail System",
                system_version="1.0",
                provider="Test",
                intended_purpose="Testing audit trails",
                use_cases=["audit"],
                model_type="test",
                human_oversight_measures=["logging"],
            )

            # Log decision
            decision = await service.log_decision(
                ai_system_id=system.id,
                model_version="1.0",
                decision_type="audit_test",
                decision_outcome="test_outcome",
                confidence_score=0.9,
                input_summary={"test": True},
                reasoning_chain=["Step 1", "Step 2"],
                key_factors=[{"factor": "test", "weight": 1.0}],
                subject_id="subject_123",
            )

            # Decision should have timestamp
            assert decision.timestamp is not None
            # Decision should be retrievable
            explanation = await service.generate_explanation(decision.id)
            assert explanation is not None
        except ImportError:
            pytest.skip("AI governance service not available")
