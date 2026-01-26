"""
Bayesian Scoring Module

Implements Bayesian hypothesis scoring for differential diagnosis.
Uses phenotype-disease frequencies, genetic evidence, and clinical context.
"""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from .models import (
    DiagnosisHypothesis,
    EvidenceItem,
    EvidencePolarity,
    EvidenceType,
    PatientProfile,
)

logger = structlog.get_logger(__name__)


@dataclass
class ScoringConfig:
    """Configuration for Bayesian scoring."""
    # Evidence weights
    phenotype_weight: float = 0.4
    genetic_weight: float = 0.35
    history_weight: float = 0.15
    laboratory_weight: float = 0.1

    # Likelihood ratios for different evidence types
    phenotype_present_lr: float = 5.0    # Phenotype present
    phenotype_absent_lr: float = 0.3     # Phenotype absent
    pathogenic_variant_lr: float = 50.0  # Pathogenic variant found
    vous_variant_lr: float = 2.0         # VUS found
    family_history_lr: float = 3.0       # Positive family history

    # Prior adjustments
    use_prevalence: bool = True
    default_prevalence: float = 1e-5     # 1 in 100,000
    max_posterior: float = 0.99
    min_posterior: float = 0.001

    # Phenotype scoring
    require_core_phenotypes: bool = True
    missing_phenotype_penalty: float = 0.8


class BayesianScorer:
    """
    Bayesian hypothesis scorer for differential diagnosis.

    Uses Bayes' theorem to update disease probabilities based on:
    - Prior probability (disease prevalence)
    - Phenotype likelihood ratios
    - Genetic evidence
    - Clinical history

    P(Disease|Evidence) = P(Evidence|Disease) * P(Disease) / P(Evidence)
    """

    def __init__(
        self,
        config: ScoringConfig | None = None,
        primekg_overlay: Any = None,
    ) -> None:
        """
        Initialize the Bayesian scorer.

        Args:
            config: Scoring configuration
            primekg_overlay: PrimeKG overlay for phenotype frequencies
        """
        self.config = config or ScoringConfig()
        self._primekg = primekg_overlay

        # Cached phenotype frequencies
        self._phenotype_freq_cache: dict[str, dict[str, float]] = {}

    async def score_hypothesis(
        self,
        hypothesis: DiagnosisHypothesis,
        patient: PatientProfile,
    ) -> DiagnosisHypothesis:
        """
        Score a single hypothesis against patient evidence.

        Args:
            hypothesis: Diagnosis hypothesis to score
            patient: Patient profile with evidence

        Returns:
            Updated hypothesis with scores
        """
        # Start with prior - ensure it's in valid range (0, 1) exclusive
        prior = hypothesis.prior_probability
        if self.config.use_prevalence and prior <= 0:
            prior = self.config.default_prevalence
        # Clamp prior to valid range for Bayesian calculation
        prior = max(self.config.min_posterior, min(self.config.max_posterior, prior))

        # Calculate likelihood ratio from all evidence
        combined_lr = 1.0

        # Phenotype evidence
        phenotype_lr = await self._calculate_phenotype_likelihood(
            hypothesis.disease_id,
            patient.phenotype_codes,
            patient.negated_phenotype_codes,
        )
        hypothesis.phenotype_score = self._lr_to_score(phenotype_lr)

        # Genetic evidence
        genetic_lr = self._calculate_genetic_likelihood(
            hypothesis.associated_genes,
            list(patient.genetic_variants),
        )
        hypothesis.genetic_score = self._lr_to_score(genetic_lr)

        # History evidence
        history_lr = self._calculate_history_likelihood(
            hypothesis,
            patient.medical_history,
            patient.family_history,
        )
        hypothesis.history_score = self._lr_to_score(history_lr)

        # Combine likelihood ratios (weighted geometric mean)
        combined_lr = (
            (phenotype_lr ** self.config.phenotype_weight) *
            (genetic_lr ** self.config.genetic_weight) *
            (history_lr ** self.config.history_weight)
        )

        # Apply Bayes' theorem
        posterior_odds = (prior / (1 - prior)) * combined_lr
        posterior = posterior_odds / (1 + posterior_odds)

        # Clamp to valid range
        posterior = max(self.config.min_posterior, min(self.config.max_posterior, posterior))

        hypothesis.posterior_probability = posterior

        # Calculate combined score (weighted average of component scores)
        hypothesis.combined_score = (
            hypothesis.phenotype_score * self.config.phenotype_weight +
            hypothesis.genetic_score * self.config.genetic_weight +
            hypothesis.history_score * self.config.history_weight
        )

        # Classify evidence
        self._classify_evidence(hypothesis, patient)

        hypothesis.updated_at = datetime.now(UTC)
        return hypothesis

    async def score_all_hypotheses(
        self,
        hypotheses: list[DiagnosisHypothesis],
        patient: PatientProfile,
    ) -> list[DiagnosisHypothesis]:
        """
        Score and rank all hypotheses.

        Args:
            hypotheses: List of hypotheses to score
            patient: Patient profile

        Returns:
            Sorted list of hypotheses (highest score first)
        """
        scored = []
        for hypothesis in hypotheses:
            scored_h = await self.score_hypothesis(hypothesis, patient)
            scored.append(scored_h)

        # Sort by combined score
        scored.sort(key=lambda h: h.combined_score, reverse=True)

        # Assign ranks
        for i, h in enumerate(scored):
            h.rank = i + 1

        return scored

    async def _calculate_phenotype_likelihood(
        self,
        disease_id: str,
        present_phenotypes: list[str],
        absent_phenotypes: list[str],
    ) -> float:
        """
        Calculate phenotype likelihood ratio.

        Uses phenotype-disease frequencies from PrimeKG.
        """
        if not present_phenotypes and not absent_phenotypes:
            return 1.0

        lr = 1.0

        # Get phenotype frequencies for this disease
        frequencies = await self._get_phenotype_frequencies(disease_id)

        # For each present phenotype
        for hpo_id in present_phenotypes:
            freq = frequencies.get(hpo_id, 0.1)  # Default 10% if unknown

            # Likelihood ratio for present phenotype
            # LR = P(phenotype|disease) / P(phenotype|no_disease)
            # Approximate P(phenotype|no_disease) as background rate
            background = 0.01  # Assume 1% background rate
            phenotype_lr = freq / background

            # Clamp to reasonable range
            phenotype_lr = max(0.1, min(100, phenotype_lr))
            lr *= phenotype_lr

        # For each absent phenotype
        for hpo_id in absent_phenotypes:
            freq = frequencies.get(hpo_id, 0.1)

            if freq > 0.5:  # Core phenotype absent
                # Strong evidence against
                lr *= self.config.phenotype_absent_lr
            elif freq > 0.2:  # Common phenotype absent
                lr *= 0.6

        return lr

    def _calculate_genetic_likelihood(
        self,
        disease_genes: list[str],
        genetic_evidence: list[EvidenceItem],
    ) -> float:
        """
        Calculate genetic evidence likelihood ratio.
        """
        if not disease_genes or not genetic_evidence:
            return 1.0

        lr = 1.0

        for evidence in genetic_evidence:
            # Check if variant is in a disease-associated gene
            # Get gene symbol from code (preferred) or extract from value (fallback)
            gene_symbol = evidence.code
            if not gene_symbol and evidence.value:
                gene_symbol = evidence.value.split(":")[0] if ":" in evidence.value else evidence.value

            if gene_symbol and gene_symbol in disease_genes:
                # Check pathogenicity
                if "pathogenic" in str(evidence.severity).lower():
                    lr *= self.config.pathogenic_variant_lr
                elif "likely_pathogenic" in str(evidence.severity).lower():
                    lr *= self.config.pathogenic_variant_lr * 0.5
                elif "vous" in str(evidence.severity).lower() or "uncertain" in str(evidence.severity).lower():
                    lr *= self.config.vous_variant_lr
                else:
                    lr *= 1.5  # Unknown significance in disease gene

        return lr

    def _calculate_history_likelihood(
        self,
        hypothesis: DiagnosisHypothesis,
        medical_history: list[EvidenceItem],
        family_history: list[EvidenceItem],
    ) -> float:
        """
        Calculate likelihood ratio from medical and family history.
        """
        lr = 1.0

        # Family history
        for fh in family_history:
            # Check if family history matches this disease
            if hypothesis.disease_name.lower() in fh.value.lower():
                lr *= self.config.family_history_lr
            elif any(gene in fh.value for gene in hypothesis.associated_genes):
                lr *= self.config.family_history_lr * 0.7

        # Medical history (could reduce LR if conflicting conditions)
        for mh in medical_history:
            # Check for conditions that might rule out this diagnosis
            if mh.negated and hypothesis.disease_name.lower() in mh.value.lower():
                lr *= 0.1  # Strong evidence against

        return lr

    async def _get_phenotype_frequencies(self, disease_id: str) -> dict[str, float]:
        """
        Get phenotype frequencies for a disease from PrimeKG.

        Returns a dict mapping HPO IDs to their frequency in the disease.
        Frequency represents how often this phenotype appears in patients
        with the disease (0.0 to 1.0).

        Frequencies are estimated based on:
        - "frequency" property if available in the relationship
        - Number of edges (more edges = more commonly reported)
        - Default to 0.5 for unknown
        """
        if disease_id in self._phenotype_freq_cache:
            return self._phenotype_freq_cache[disease_id]

        frequencies = {}

        if self._primekg:
            try:
                # Query PrimeKG for disease phenotypes with frequencies
                # Uses relationship properties if available, otherwise estimates
                query = """
                MATCH (d:PrimeKGDisease)-[r:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
                WHERE d.mondo_id = $disease_id OR d.node_id = $disease_id
                WITH p.hpo_id as hpo_id,
                     p.name as name,
                     // Use frequency if available, otherwise estimate from edge weight
                     CASE
                         WHEN r.frequency IS NOT NULL THEN r.frequency
                         WHEN r.weight IS NOT NULL THEN r.weight
                         ELSE 0.5
                     END as freq
                RETURN hpo_id, name, freq
                ORDER BY freq DESC
                """

                # Access Neo4j through the overlay's client
                neo4j = getattr(self._primekg, '_neo4j', None)
                if neo4j:
                    results = await neo4j.run(query, {"disease_id": disease_id})

                    for r in (results or []):
                        hpo_id = r.get("hpo_id")
                        if hpo_id:
                            # Clamp frequency to valid range
                            freq = float(r.get("freq", 0.5))
                            frequencies[hpo_id] = max(0.01, min(1.0, freq))

                    logger.debug(
                        "phenotype_frequencies_loaded",
                        disease_id=disease_id,
                        count=len(frequencies),
                    )

            except Exception as e:
                logger.warning(
                    "phenotype_freq_query_failed",
                    disease=disease_id,
                    error=str(e),
                )

        self._phenotype_freq_cache[disease_id] = frequencies
        return frequencies

    def _classify_evidence(
        self,
        hypothesis: DiagnosisHypothesis,
        patient: PatientProfile,
    ) -> None:
        """Classify patient evidence as supporting, refuting, or neutral."""
        hypothesis.supporting_evidence.clear()
        hypothesis.refuting_evidence.clear()
        hypothesis.neutral_evidence.clear()

        for evidence in patient.all_evidence:
            polarity = self._determine_evidence_polarity(hypothesis, evidence)

            if polarity == EvidencePolarity.SUPPORTS:
                hypothesis.supporting_evidence.append(evidence)
            elif polarity == EvidencePolarity.REFUTES:
                hypothesis.refuting_evidence.append(evidence)
            else:
                hypothesis.neutral_evidence.append(evidence)

    def _determine_evidence_polarity(
        self,
        hypothesis: DiagnosisHypothesis,
        evidence: EvidenceItem,
    ) -> EvidencePolarity:
        """Determine if evidence supports or refutes a hypothesis."""
        if evidence.evidence_type == EvidenceType.PHENOTYPE:
            if evidence.code in hypothesis.matched_phenotypes:
                return EvidencePolarity.REFUTES if evidence.negated else EvidencePolarity.SUPPORTS
            if evidence.code in hypothesis.expected_phenotypes:
                return EvidencePolarity.REFUTES if evidence.negated else EvidencePolarity.SUPPORTS

        elif evidence.evidence_type == EvidenceType.GENETIC:
            # Get gene from code (preferred) or extract from value (fallback)
            gene = evidence.code
            if not gene and evidence.value:
                gene = evidence.value.split(":")[0] if ":" in evidence.value else evidence.value
            if gene and gene in hypothesis.associated_genes:
                if "pathogenic" in str(evidence.severity).lower():
                    return EvidencePolarity.SUPPORTS
                elif "benign" in str(evidence.severity).lower():
                    return EvidencePolarity.REFUTES

        elif evidence.evidence_type == EvidenceType.FAMILY:
            if hypothesis.disease_name.lower() in evidence.value.lower():
                return EvidencePolarity.SUPPORTS

        return EvidencePolarity.NEUTRAL

    def _lr_to_score(self, lr: float) -> float:
        """Convert likelihood ratio to a 0-1 score."""
        if lr <= 0:
            return 0.0
        # Use logistic transformation
        log_lr = math.log(lr)
        score = 1.0 / (1.0 + math.exp(-log_lr / 2))
        return score

    def calculate_information_gain(
        self,
        hypotheses: list[DiagnosisHypothesis],
        phenotype_hpo_id: str,
    ) -> float:
        """
        Calculate expected information gain from asking about a phenotype.

        Uses entropy reduction to estimate how much a phenotype question
        would discriminate between hypotheses.
        """
        if len(hypotheses) <= 1:
            return 0.0

        # Current entropy
        probs = [h.combined_score for h in hypotheses]
        total = sum(probs)
        if total == 0:
            return 0.0

        probs = [p / total for p in probs]
        current_entropy = -sum(p * math.log(p + 1e-10) for p in probs)

        # Expected entropy if phenotype is present
        present_probs = []
        for h in hypotheses:
            freq = 0.5  # Default frequency
            if phenotype_hpo_id in h.expected_phenotypes:
                freq = 0.7
            elif phenotype_hpo_id in h.missing_phenotypes:
                freq = 0.3
            present_probs.append(h.combined_score * freq)

        # Expected entropy if phenotype is absent
        absent_probs = []
        for h in hypotheses:
            freq = 0.5
            if phenotype_hpo_id in h.expected_phenotypes:
                freq = 0.3
            elif phenotype_hpo_id in h.missing_phenotypes:
                freq = 0.7
            absent_probs.append(h.combined_score * freq)

        # Calculate expected post-question entropy
        p_present = sum(present_probs) / (sum(present_probs) + sum(absent_probs) + 1e-10)
        p_absent = 1 - p_present

        if sum(present_probs) > 0:
            present_probs = [p / sum(present_probs) for p in present_probs]
            entropy_present = -sum(p * math.log(p + 1e-10) for p in present_probs)
        else:
            entropy_present = current_entropy

        if sum(absent_probs) > 0:
            absent_probs = [p / sum(absent_probs) for p in absent_probs]
            entropy_absent = -sum(p * math.log(p + 1e-10) for p in absent_probs)
        else:
            entropy_absent = current_entropy

        expected_entropy = p_present * entropy_present + p_absent * entropy_absent

        # Information gain = reduction in entropy
        return max(0.0, current_entropy - expected_entropy)


# =============================================================================
# Factory Function
# =============================================================================

def create_bayesian_scorer(
    config: ScoringConfig | None = None,
    primekg_overlay: Any = None,
) -> BayesianScorer:
    """Create a Bayesian scorer instance."""
    return BayesianScorer(
        config=config,
        primekg_overlay=primekg_overlay,
    )
