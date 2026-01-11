"""
Forge Compliance Framework - AI Governance Service

Implements AI governance requirements per:
- EU AI Act (2024) - Risk classification, conformity assessment
- Colorado AI Act (SB21-169) - Consequential decision disclosure
- NYC Local Law 144 - Automated employment decision tools
- NIST AI RMF - Risk management
- ISO 42001 - AI Management System

Key capabilities:
- AI System Registration and Inventory
- Risk Classification (per EU AI Act Annex III)
- Bias Detection and Fairness Metrics
- Explainability and Transparency
- Human Oversight Mechanisms
- Conformity Assessment Support
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable, Awaitable
from uuid import uuid4

import structlog

from forge.compliance.core.enums import AIRiskClassification, Jurisdiction
from forge.compliance.core.models import AISystemRegistration, AIDecisionLog

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# AI SYSTEM TYPES AND CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════


class AIUseCase(str, Enum):
    """AI use case categories per EU AI Act Annex III."""
    # Prohibited (Article 5)
    SOCIAL_SCORING = "social_scoring"
    SUBLIMINAL_MANIPULATION = "subliminal_manipulation"
    EXPLOITATION_VULNERABILITY = "exploitation_vulnerability"
    REAL_TIME_BIOMETRIC_PUBLIC = "real_time_biometric_public"
    
    # High-Risk (Annex III)
    BIOMETRIC_IDENTIFICATION = "biometric_identification"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    EDUCATION_ASSESSMENT = "education_assessment"
    EMPLOYMENT_RECRUITMENT = "employment_recruitment"
    EMPLOYMENT_MANAGEMENT = "employment_management"
    ESSENTIAL_SERVICES = "essential_services"
    CREDIT_SCORING = "credit_scoring"
    LAW_ENFORCEMENT = "law_enforcement"
    MIGRATION_ASYLUM = "migration_asylum"
    JUSTICE_DEMOCRACY = "justice_democracy"
    
    # GPAI
    GENERAL_PURPOSE = "general_purpose"
    GENERAL_PURPOSE_SYSTEMIC = "general_purpose_systemic"
    
    # Limited Risk
    CHATBOT = "chatbot"
    EMOTION_RECOGNITION = "emotion_recognition"
    DEEPFAKE_GENERATION = "deepfake_generation"
    
    # Minimal Risk
    RECOMMENDATION = "recommendation"
    CONTENT_GENERATION = "content_generation"
    SEARCH = "search"
    TRANSLATION = "translation"


class BiasMetric(str, Enum):
    """Fairness metrics for bias detection."""
    DEMOGRAPHIC_PARITY = "demographic_parity"
    EQUALIZED_ODDS = "equalized_odds"
    EQUAL_OPPORTUNITY = "equal_opportunity"
    PREDICTIVE_PARITY = "predictive_parity"
    CALIBRATION = "calibration"
    INDIVIDUAL_FAIRNESS = "individual_fairness"
    COUNTERFACTUAL_FAIRNESS = "counterfactual_fairness"


class ExplainabilityMethod(str, Enum):
    """Explainability methods for AI decisions."""
    FEATURE_IMPORTANCE = "feature_importance"
    SHAP = "shap"
    LIME = "lime"
    ATTENTION_WEIGHTS = "attention_weights"
    COUNTERFACTUAL = "counterfactual"
    RULE_EXTRACTION = "rule_extraction"
    PROTOTYPE = "prototype"
    NATURAL_LANGUAGE = "natural_language"


# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BiasAssessment:
    """Bias assessment results for an AI system."""
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    ai_system_id: str = ""
    
    # Assessment details
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    assessed_by: str = ""
    assessment_type: str = "automated"  # automated, manual, third_party
    
    # Protected attributes evaluated
    protected_attributes: list[str] = field(default_factory=list)
    # e.g., ["race", "gender", "age", "disability"]
    
    # Metrics per attribute
    metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    # e.g., {"gender": {"demographic_parity": 0.95, "equalized_odds": 0.87}}
    
    # Thresholds
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "demographic_parity": 0.8,
        "equalized_odds": 0.8,
        "equal_opportunity": 0.8,
    })
    
    # Results
    bias_detected: bool = False
    affected_groups: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    # Remediation
    remediation_required: bool = False
    remediation_deadline: datetime | None = None
    remediation_completed: bool = False
    
    def check_thresholds(self) -> list[str]:
        """Check which metrics fail thresholds."""
        failures = []
        for attr, attr_metrics in self.metrics.items():
            for metric, value in attr_metrics.items():
                threshold = self.thresholds.get(metric, 0.8)
                if value < threshold:
                    failures.append(f"{attr}:{metric}={value:.2f}<{threshold}")
        return failures


@dataclass
class ConformityAssessment:
    """EU AI Act conformity assessment record."""
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    ai_system_id: str = ""
    
    # Assessment metadata
    initiated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    assessor: str = ""  # Self, notified body, or third party
    notified_body_id: str | None = None
    
    # Requirements checklist (per EU AI Act Article 9-15)
    risk_management_system: bool = False  # Article 9
    data_governance: bool = False  # Article 10
    technical_documentation: bool = False  # Article 11
    record_keeping: bool = False  # Article 12
    transparency: bool = False  # Article 13
    human_oversight: bool = False  # Article 14
    accuracy_robustness: bool = False  # Article 15
    cybersecurity: bool = False  # Article 15
    
    # Documentation references
    technical_doc_reference: str | None = None
    risk_assessment_reference: str | None = None
    test_results_reference: str | None = None
    
    # Declaration
    eu_declaration_issued: bool = False
    eu_declaration_reference: str | None = None
    ce_marking_affixed: bool = False
    
    # Database registration
    eu_database_registered: bool = False
    eu_database_reference: str | None = None
    
    @property
    def is_complete(self) -> bool:
        """Check if all requirements are met."""
        return all([
            self.risk_management_system,
            self.data_governance,
            self.technical_documentation,
            self.record_keeping,
            self.transparency,
            self.human_oversight,
            self.accuracy_robustness,
            self.cybersecurity,
        ])


@dataclass
class HumanOversightMechanism:
    """Human oversight mechanism for AI system."""
    mechanism_id: str = field(default_factory=lambda: str(uuid4()))
    ai_system_id: str = ""
    
    # Oversight type
    mechanism_type: str = ""  # override, review, intervention, shutdown
    description: str = ""
    
    # Trigger conditions
    automatic_trigger: bool = False
    trigger_conditions: list[str] = field(default_factory=list)
    # e.g., ["confidence < 0.7", "high_risk_decision", "user_request"]
    
    # Reviewer requirements
    required_role: str | None = None
    required_training: list[str] = field(default_factory=list)
    
    # SLA
    response_time_hours: int = 24
    escalation_path: list[str] = field(default_factory=list)
    
    # Statistics
    total_invocations: int = 0
    average_response_time: float = 0.0
    override_rate: float = 0.0


@dataclass 
class ImpactAssessment:
    """Algorithmic Impact Assessment per Colorado AI Act."""
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    ai_system_id: str = ""
    
    # Assessment metadata
    conducted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    conducted_by: str = ""
    review_frequency: str = "annual"  # annual, semi_annual, quarterly
    next_review: datetime | None = None
    
    # System description
    system_purpose: str = ""
    decision_types: list[str] = field(default_factory=list)
    affected_populations: list[str] = field(default_factory=list)
    
    # Data assessment
    training_data_sources: list[str] = field(default_factory=list)
    data_quality_measures: list[str] = field(default_factory=list)
    data_bias_assessment: str | None = None
    
    # Impact analysis
    potential_harms: list[str] = field(default_factory=list)
    mitigation_measures: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)
    
    # Stakeholder engagement
    stakeholders_consulted: list[str] = field(default_factory=list)
    public_input_received: bool = False
    
    # Conclusions
    risk_level: str = "low"  # low, medium, high, unacceptable
    deployment_recommendation: str = "proceed"  # proceed, modify, halt
    conditions: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# AI GOVERNANCE SERVICE
# ═══════════════════════════════════════════════════════════════════════════


class AIGovernanceService:
    """
    Comprehensive AI governance service.
    
    Manages AI system lifecycle, risk assessment, bias detection,
    explainability, and regulatory compliance.
    """
    
    def __init__(self):
        # AI system inventory
        self._systems: dict[str, AISystemRegistration] = {}
        
        # Decision logs (with retention)
        self._decisions: dict[str, AIDecisionLog] = {}
        
        # Assessments
        self._bias_assessments: dict[str, BiasAssessment] = {}
        self._conformity_assessments: dict[str, ConformityAssessment] = {}
        self._impact_assessments: dict[str, ImpactAssessment] = {}
        
        # Human oversight mechanisms
        self._oversight_mechanisms: dict[str, list[HumanOversightMechanism]] = {}
        
        # Explainability handlers
        self._explainers: dict[str, Callable[[AIDecisionLog], Awaitable[dict]]] = {}
        
        # Prohibited use case patterns
        self._prohibited_patterns = self._initialize_prohibited_patterns()
    
    def _initialize_prohibited_patterns(self) -> dict[str, list[str]]:
        """Initialize patterns for prohibited AI uses."""
        return {
            AIUseCase.SOCIAL_SCORING.value: [
                "social_credit", "citizen_score", "trustworthiness_rating",
                "behavior_scoring", "social_ranking",
            ],
            AIUseCase.SUBLIMINAL_MANIPULATION.value: [
                "subliminal", "manipulation", "dark_pattern", "unconscious_influence",
            ],
            AIUseCase.EXPLOITATION_VULNERABILITY.value: [
                "target_vulnerable", "exploit_disability", "exploit_minor",
                "exploit_economic", "predatory",
            ],
        }
    
    # ───────────────────────────────────────────────────────────────
    # AI SYSTEM REGISTRATION
    # ───────────────────────────────────────────────────────────────
    
    async def register_system(
        self,
        system_name: str,
        system_version: str,
        provider: str,
        intended_purpose: str,
        use_cases: list[str],
        model_type: str,
        human_oversight_measures: list[str],
        training_data_description: str | None = None,
        risk_classification: AIRiskClassification | None = None,
    ) -> AISystemRegistration:
        """
        Register an AI system in the inventory.
        
        Per EU AI Act Article 49 - Registration requirements.
        """
        # Auto-classify risk if not provided
        if risk_classification is None:
            risk_classification = self._classify_risk(use_cases, intended_purpose)
        
        # Check for prohibited uses
        prohibited_check = self._check_prohibited_uses(use_cases, intended_purpose)
        if prohibited_check:
            logger.error(
                "prohibited_ai_use_detected",
                system_name=system_name,
                prohibited_uses=prohibited_check,
            )
            raise ValueError(f"Prohibited AI use detected: {prohibited_check}")
        
        registration = AISystemRegistration(
            system_name=system_name,
            system_version=system_version,
            provider=provider,
            risk_classification=risk_classification,
            intended_purpose=intended_purpose,
            use_cases=use_cases,
            model_type=model_type,
            human_oversight_measures=human_oversight_measures,
            training_data_description=training_data_description,
        )
        
        self._systems[registration.id] = registration
        
        # Initialize oversight mechanisms for high-risk systems
        if risk_classification in {AIRiskClassification.HIGH_RISK, AIRiskClassification.GPAI_SYSTEMIC}:
            await self._initialize_oversight_mechanisms(registration)
        
        logger.info(
            "ai_system_registered",
            system_id=registration.id,
            system_name=system_name,
            risk_classification=risk_classification.value,
        )
        
        return registration
    
    def _classify_risk(
        self,
        use_cases: list[str],
        intended_purpose: str,
    ) -> AIRiskClassification:
        """
        Classify AI system risk per EU AI Act Annex III.
        """
        purpose_lower = intended_purpose.lower()
        
        # Check for prohibited uses
        for prohibited_case in [
            AIUseCase.SOCIAL_SCORING,
            AIUseCase.SUBLIMINAL_MANIPULATION,
            AIUseCase.EXPLOITATION_VULNERABILITY,
            AIUseCase.REAL_TIME_BIOMETRIC_PUBLIC,
        ]:
            if prohibited_case.value in use_cases:
                return AIRiskClassification.UNACCEPTABLE
        
        # Check for high-risk (Annex III)
        high_risk_cases = {
            AIUseCase.BIOMETRIC_IDENTIFICATION,
            AIUseCase.CRITICAL_INFRASTRUCTURE,
            AIUseCase.EDUCATION_ASSESSMENT,
            AIUseCase.EMPLOYMENT_RECRUITMENT,
            AIUseCase.EMPLOYMENT_MANAGEMENT,
            AIUseCase.ESSENTIAL_SERVICES,
            AIUseCase.CREDIT_SCORING,
            AIUseCase.LAW_ENFORCEMENT,
            AIUseCase.MIGRATION_ASYLUM,
            AIUseCase.JUSTICE_DEMOCRACY,
        }
        
        for case in use_cases:
            if case in {c.value for c in high_risk_cases}:
                return AIRiskClassification.HIGH_RISK
        
        # Check keywords in purpose
        high_risk_keywords = [
            "employment", "hiring", "recruitment", "credit", "loan",
            "education", "grading", "biometric", "law enforcement",
            "critical infrastructure", "healthcare diagnosis",
        ]
        
        if any(kw in purpose_lower for kw in high_risk_keywords):
            return AIRiskClassification.HIGH_RISK
        
        # Check for GPAI
        if AIUseCase.GENERAL_PURPOSE_SYSTEMIC.value in use_cases:
            return AIRiskClassification.GPAI_SYSTEMIC
        if AIUseCase.GENERAL_PURPOSE.value in use_cases:
            return AIRiskClassification.GPAI
        
        # Check for limited risk
        limited_risk_cases = {
            AIUseCase.CHATBOT,
            AIUseCase.EMOTION_RECOGNITION,
            AIUseCase.DEEPFAKE_GENERATION,
        }
        
        for case in use_cases:
            if case in {c.value for c in limited_risk_cases}:
                return AIRiskClassification.LIMITED_RISK
        
        return AIRiskClassification.MINIMAL_RISK
    
    def _check_prohibited_uses(
        self,
        use_cases: list[str],
        intended_purpose: str,
    ) -> list[str]:
        """Check for prohibited AI uses."""
        prohibited = []
        purpose_lower = intended_purpose.lower()
        
        for category, patterns in self._prohibited_patterns.items():
            if category in use_cases:
                prohibited.append(category)
            elif any(p in purpose_lower for p in patterns):
                prohibited.append(category)
        
        return prohibited
    
    async def _initialize_oversight_mechanisms(
        self,
        registration: AISystemRegistration,
    ) -> None:
        """Initialize human oversight mechanisms for high-risk AI."""
        mechanisms = [
            HumanOversightMechanism(
                ai_system_id=registration.id,
                mechanism_type="review",
                description="Manual review of AI decisions",
                automatic_trigger=True,
                trigger_conditions=["confidence < 0.7", "high_impact_decision"],
                required_role="ai_reviewer",
                response_time_hours=24,
            ),
            HumanOversightMechanism(
                ai_system_id=registration.id,
                mechanism_type="override",
                description="Human can override AI decision",
                automatic_trigger=False,
                trigger_conditions=["user_request", "reviewer_escalation"],
                required_role="ai_reviewer",
                response_time_hours=4,
            ),
            HumanOversightMechanism(
                ai_system_id=registration.id,
                mechanism_type="shutdown",
                description="Emergency AI shutdown capability",
                automatic_trigger=True,
                trigger_conditions=["critical_error", "safety_violation"],
                required_role="admin",
                response_time_hours=1,
            ),
        ]
        
        self._oversight_mechanisms[registration.id] = mechanisms
    
    # ───────────────────────────────────────────────────────────────
    # DECISION LOGGING
    # ───────────────────────────────────────────────────────────────
    
    async def log_decision(
        self,
        ai_system_id: str,
        model_version: str,
        decision_type: str,
        decision_outcome: str,
        confidence_score: float,
        input_summary: dict[str, Any],
        reasoning_chain: list[str],
        key_factors: list[dict[str, Any]],
        subject_id: str | None = None,
        has_legal_effect: bool = False,
        has_significant_effect: bool = False,
    ) -> AIDecisionLog:
        """
        Log an AI decision for transparency and accountability.
        
        Per EU AI Act Article 12 - Record-keeping.
        """
        system = self._systems.get(ai_system_id)
        if not system:
            raise ValueError(f"AI system not registered: {ai_system_id}")
        
        decision = AIDecisionLog(
            ai_system_id=ai_system_id,
            model_version=model_version,
            decision_type=decision_type,
            decision_outcome=decision_outcome,
            confidence_score=confidence_score,
            input_summary=input_summary,
            reasoning_chain=reasoning_chain,
            key_factors=key_factors,
            subject_id=subject_id,
            has_legal_effect=has_legal_effect,
            has_significant_effect=has_significant_effect,
        )
        
        self._decisions[decision.id] = decision
        
        # Check if human review required
        if self._requires_human_review(decision, system):
            decision.human_review_requested = True
            decision.human_review_requested_at = datetime.now(UTC)
            
            logger.info(
                "ai_decision_review_required",
                decision_id=decision.id,
                reason="policy_trigger",
            )
        
        logger.info(
            "ai_decision_logged",
            decision_id=decision.id,
            system_id=ai_system_id,
            decision_type=decision_type,
        )
        
        return decision
    
    def _requires_human_review(
        self,
        decision: AIDecisionLog,
        system: AISystemRegistration,
    ) -> bool:
        """Determine if decision requires human review."""
        # Always review for high-risk systems with legal/significant effect
        if system.risk_classification in {
            AIRiskClassification.HIGH_RISK,
            AIRiskClassification.GPAI_SYSTEMIC,
        }:
            if decision.has_legal_effect or decision.has_significant_effect:
                return True
        
        # Low confidence requires review
        if decision.confidence_score < 0.7:
            return True
        
        # Check oversight mechanism triggers
        mechanisms = self._oversight_mechanisms.get(system.id, [])
        for mechanism in mechanisms:
            if mechanism.automatic_trigger:
                for condition in mechanism.trigger_conditions:
                    if condition == "high_impact_decision" and (
                        decision.has_legal_effect or decision.has_significant_effect
                    ):
                        return True
                    if condition.startswith("confidence <"):
                        threshold = float(condition.split("<")[1].strip())
                        if decision.confidence_score < threshold:
                            return True
        
        return False
    
    async def complete_human_review(
        self,
        decision_id: str,
        reviewer_id: str,
        override: bool = False,
        override_reason: str | None = None,
        new_outcome: str | None = None,
    ) -> AIDecisionLog | None:
        """
        Complete human review of an AI decision.
        
        Per GDPR Article 22 - Right to human intervention.
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            return None
        
        decision.human_reviewed = True
        decision.human_reviewer_id = reviewer_id
        decision.human_review_completed_at = datetime.now(UTC)
        decision.human_override = override
        
        if override:
            decision.human_override_reason = override_reason
            if new_outcome:
                decision.decision_outcome = new_outcome
            
            logger.info(
                "ai_decision_overridden",
                decision_id=decision_id,
                reviewer_id=reviewer_id,
                reason=override_reason,
            )
        
        return decision
    
    # ───────────────────────────────────────────────────────────────
    # EXPLAINABILITY
    # ───────────────────────────────────────────────────────────────
    
    async def generate_explanation(
        self,
        decision_id: str,
        method: ExplainabilityMethod = ExplainabilityMethod.NATURAL_LANGUAGE,
        audience: str = "end_user",
    ) -> dict[str, Any]:
        """
        Generate explanation for an AI decision.
        
        Per EU AI Act Article 13 - Transparency requirements.
        
        Args:
            decision_id: ID of the decision to explain
            method: Explanation method to use
            audience: Target audience (end_user, technical, regulatory)
        
        Returns:
            Explanation with appropriate detail level
        """
        decision = self._decisions.get(decision_id)
        if not decision:
            return {"error": "Decision not found"}
        
        system = self._systems.get(decision.ai_system_id)
        if not system:
            return {"error": "System not found"}
        
        # Build explanation based on audience
        if audience == "end_user":
            explanation = self._generate_user_explanation(decision, system)
        elif audience == "technical":
            explanation = self._generate_technical_explanation(decision, system)
        else:
            explanation = self._generate_regulatory_explanation(decision, system)
        
        return explanation
    
    def _generate_user_explanation(
        self,
        decision: AIDecisionLog,
        system: AISystemRegistration,
    ) -> dict[str, Any]:
        """Generate end-user friendly explanation."""
        # Build natural language explanation
        factor_explanations = []
        for factor in decision.key_factors:
            factor_explanations.append(
                f"• {factor.get('factor', 'Factor')}: {factor.get('explanation', 'Contributed to the decision')}"
            )
        
        return {
            "summary": f"The {system.system_name} made this decision based on the information provided.",
            "outcome": decision.decision_outcome,
            "confidence": f"{decision.confidence_score:.0%} confident",
            "key_factors": factor_explanations,
            "what_this_means": decision.reasoning_chain[-1] if decision.reasoning_chain else "",
            "your_rights": [
                "You can request a human review of this decision",
                "You can ask for more details about how this decision was made",
                "You can provide additional information for reconsideration",
            ],
            "how_to_contest": "Contact support to request a human review",
        }
    
    def _generate_technical_explanation(
        self,
        decision: AIDecisionLog,
        system: AISystemRegistration,
    ) -> dict[str, Any]:
        """Generate technical explanation."""
        return {
            "system": {
                "id": system.id,
                "name": system.system_name,
                "version": system.system_version,
                "model_type": system.model_type,
                "risk_classification": system.risk_classification.value,
            },
            "decision": {
                "id": decision.id,
                "type": decision.decision_type,
                "outcome": decision.decision_outcome,
                "confidence": decision.confidence_score,
                "timestamp": decision.timestamp.isoformat(),
            },
            "reasoning": {
                "chain": decision.reasoning_chain,
                "key_factors": decision.key_factors,
            },
            "input_summary": decision.input_summary,
            "model_version": decision.model_version,
        }
    
    def _generate_regulatory_explanation(
        self,
        decision: AIDecisionLog,
        system: AISystemRegistration,
    ) -> dict[str, Any]:
        """Generate regulatory-compliant explanation."""
        return {
            "system_registration": {
                "id": system.id,
                "name": system.system_name,
                "provider": system.provider,
                "risk_classification": system.risk_classification.value,
                "eu_database_registered": system.eu_database_registered,
                "conformity_assessment_completed": system.conformity_assessment_completed,
            },
            "decision_record": {
                "id": decision.id,
                "timestamp": decision.timestamp.isoformat(),
                "decision_type": decision.decision_type,
                "outcome": decision.decision_outcome,
                "has_legal_effect": decision.has_legal_effect,
                "has_significant_effect": decision.has_significant_effect,
            },
            "transparency_information": {
                "input_summary": decision.input_summary,
                "reasoning_chain": decision.reasoning_chain,
                "key_factors": decision.key_factors,
                "confidence_score": decision.confidence_score,
            },
            "human_oversight": {
                "review_requested": decision.human_review_requested,
                "reviewed": decision.human_reviewed,
                "reviewer_id": decision.human_reviewer_id,
                "override": decision.human_override,
                "override_reason": decision.human_override_reason,
            },
            "subject_information": {
                "subject_id": decision.subject_id,
            },
        }
    
    # ───────────────────────────────────────────────────────────────
    # BIAS ASSESSMENT
    # ───────────────────────────────────────────────────────────────
    
    async def assess_bias(
        self,
        ai_system_id: str,
        protected_attributes: list[str],
        test_data: list[dict[str, Any]],
        predictions: list[Any],
        ground_truth: list[Any] | None = None,
    ) -> BiasAssessment:
        """
        Assess AI system for bias across protected attributes.

        Per NYC Local Law 144, Colorado AI Act requirements.

        Calculates fairness metrics:
        - Demographic Parity: P(ŷ=1|G=g) should be equal across groups
        - Equalized Odds: TPR and FPR should be equal across groups
        - Equal Opportunity: TPR should be equal across groups
        """
        assessment = BiasAssessment(
            ai_system_id=ai_system_id,
            protected_attributes=protected_attributes,
        )

        # Calculate metrics for each protected attribute
        for attr in protected_attributes:
            attr_metrics = {}

            # Group data by protected attribute value
            groups = {}
            for i, data in enumerate(test_data):
                group_value = data.get(attr, "unknown")
                if group_value not in groups:
                    groups[group_value] = {"predictions": [], "ground_truth": []}
                groups[group_value]["predictions"].append(predictions[i])
                if ground_truth:
                    groups[group_value]["ground_truth"].append(ground_truth[i])

            # Calculate demographic parity: P(ŷ=1|G=g)
            positive_rates = {}
            for group, values in groups.items():
                positive_count = sum(1 for p in values["predictions"] if p)
                positive_rates[group] = positive_count / len(values["predictions"]) if values["predictions"] else 0

            if positive_rates:
                min_rate = min(positive_rates.values())
                max_rate = max(positive_rates.values())
                attr_metrics["demographic_parity"] = min_rate / max_rate if max_rate > 0 else 1.0

            # Calculate equalized odds and equal opportunity if ground truth available
            if ground_truth:
                tpr_per_group = {}  # True Positive Rate per group
                fpr_per_group = {}  # False Positive Rate per group

                for group, values in groups.items():
                    preds = values["predictions"]
                    truths = values["ground_truth"]

                    # Count true positives, false positives, etc.
                    tp = sum(1 for p, t in zip(preds, truths) if p and t)
                    fp = sum(1 for p, t in zip(preds, truths) if p and not t)
                    tn = sum(1 for p, t in zip(preds, truths) if not p and not t)
                    fn = sum(1 for p, t in zip(preds, truths) if not p and t)

                    # True Positive Rate (Recall/Sensitivity): TP / (TP + FN)
                    positives = tp + fn
                    tpr_per_group[group] = tp / positives if positives > 0 else 0.0

                    # False Positive Rate: FP / (FP + TN)
                    negatives = fp + tn
                    fpr_per_group[group] = fp / negatives if negatives > 0 else 0.0

                # Equal Opportunity: min(TPR) / max(TPR) across groups
                if tpr_per_group:
                    min_tpr = min(tpr_per_group.values())
                    max_tpr = max(tpr_per_group.values())
                    attr_metrics["equal_opportunity"] = min_tpr / max_tpr if max_tpr > 0 else 1.0

                # Equalized Odds: min of TPR ratio and FPR ratio across groups
                # Both TPR and FPR should be equal across groups
                if tpr_per_group and fpr_per_group:
                    # TPR ratio
                    min_tpr = min(tpr_per_group.values())
                    max_tpr = max(tpr_per_group.values())
                    tpr_ratio = min_tpr / max_tpr if max_tpr > 0 else 1.0

                    # FPR ratio (we want FPRs to be equal, so check disparity)
                    # For FPR, lower is better but we want equality
                    min_fpr = min(fpr_per_group.values())
                    max_fpr = max(fpr_per_group.values())
                    # Handle edge case where all FPRs are 0 (perfect)
                    if max_fpr == 0:
                        fpr_ratio = 1.0
                    else:
                        fpr_ratio = min_fpr / max_fpr if max_fpr > 0 else 1.0

                    # Equalized odds is the minimum of TPR and FPR equality
                    attr_metrics["equalized_odds"] = min(tpr_ratio, fpr_ratio)

            assessment.metrics[attr] = attr_metrics

        # Check for bias
        failures = assessment.check_thresholds()
        if failures:
            assessment.bias_detected = True
            assessment.affected_groups = list(set(f.split(":")[0] for f in failures))
            assessment.remediation_required = True
            assessment.remediation_deadline = datetime.now(UTC) + timedelta(days=30)
            assessment.recommendations = self._generate_bias_recommendations(failures, assessment.metrics)

        self._bias_assessments[assessment.assessment_id] = assessment

        logger.info(
            "bias_assessment_completed",
            assessment_id=assessment.assessment_id,
            system_id=ai_system_id,
            bias_detected=assessment.bias_detected,
            failures=failures if failures else None,
        )

        return assessment

    def _generate_bias_recommendations(
        self,
        failures: list[str],
        metrics: dict[str, dict[str, float]],
    ) -> list[str]:
        """Generate specific recommendations based on detected bias."""
        recommendations = []

        # Analyze failure types
        has_demographic_parity_issue = any("demographic_parity" in f for f in failures)
        has_equal_opportunity_issue = any("equal_opportunity" in f for f in failures)
        has_equalized_odds_issue = any("equalized_odds" in f for f in failures)

        if has_demographic_parity_issue:
            recommendations.extend([
                "Review training data distribution across protected groups",
                "Consider resampling or reweighting to balance representation",
                "Evaluate whether demographic parity is the appropriate fairness criterion for this use case",
            ])

        if has_equal_opportunity_issue:
            recommendations.extend([
                "Investigate why true positive rates differ across groups",
                "Check for label quality issues in underperforming groups",
                "Consider threshold adjustment per group (with appropriate documentation)",
            ])

        if has_equalized_odds_issue:
            recommendations.extend([
                "Review both true positive and false positive rates across groups",
                "Implement fairness constraints during model training",
                "Consider post-processing calibration methods",
            ])

        # General recommendations
        recommendations.extend([
            "Conduct disparate impact analysis with domain experts",
            "Document bias findings and mitigation efforts for compliance",
        ])

        return recommendations
    
    # ───────────────────────────────────────────────────────────────
    # CONFORMITY ASSESSMENT
    # ───────────────────────────────────────────────────────────────
    
    async def initiate_conformity_assessment(
        self,
        ai_system_id: str,
        assessor: str,
        notified_body_id: str | None = None,
    ) -> ConformityAssessment:
        """
        Initiate EU AI Act conformity assessment.
        
        Per EU AI Act Article 43.
        """
        system = self._systems.get(ai_system_id)
        if not system:
            raise ValueError(f"AI system not registered: {ai_system_id}")
        
        if not system.risk_classification.requires_conformity_assessment:
            logger.warning(
                "conformity_assessment_not_required",
                system_id=ai_system_id,
                risk_classification=system.risk_classification.value,
            )
        
        assessment = ConformityAssessment(
            ai_system_id=ai_system_id,
            assessor=assessor,
            notified_body_id=notified_body_id,
        )
        
        self._conformity_assessments[assessment.assessment_id] = assessment
        
        logger.info(
            "conformity_assessment_initiated",
            assessment_id=assessment.assessment_id,
            system_id=ai_system_id,
        )
        
        return assessment
    
    async def update_conformity_requirement(
        self,
        assessment_id: str,
        requirement: str,
        met: bool,
        evidence_reference: str | None = None,
    ) -> ConformityAssessment | None:
        """Update a conformity assessment requirement."""
        assessment = self._conformity_assessments.get(assessment_id)
        if not assessment:
            return None
        
        if hasattr(assessment, requirement):
            setattr(assessment, requirement, met)
        
        # Check if complete
        if assessment.is_complete and not assessment.completed_at:
            assessment.completed_at = datetime.now(UTC)
            
            # Update system registration
            system = self._systems.get(assessment.ai_system_id)
            if system:
                system.conformity_assessment_completed = True
        
        return assessment


# Global service instance
_ai_governance: AIGovernanceService | None = None


def get_ai_governance_service() -> AIGovernanceService:
    """Get the global AI governance service."""
    global _ai_governance
    if _ai_governance is None:
        _ai_governance = AIGovernanceService()
    return _ai_governance
