"""
Differential Diagnosis Agent

Specialist agent for synthesizing evidence into ranked differential diagnoses.
"""

from dataclasses import dataclass
from typing import Any

import structlog

from .base import AgentConfig, AgentRole, DiagnosticAgent

logger = structlog.get_logger(__name__)


@dataclass
class DifferentialAgentConfig(AgentConfig):
    """Configuration for differential diagnosis agent."""
    # Scoring weights
    phenotype_weight: float = 0.40
    genetic_weight: float = 0.35
    history_weight: float = 0.15
    wearable_weight: float = 0.10

    # Ranking settings
    max_differential: int = 15
    min_score_threshold: float = 0.1
    confidence_required_for_primary: float = 0.7

    # Evidence requirements
    require_supporting_evidence: bool = True
    penalize_contradictions: float = 0.2

    # Uncertainty handling
    express_uncertainty: bool = True
    uncertainty_threshold: float = 0.15  # Min gap between top diagnoses


class DifferentialAgent(DiagnosticAgent):
    """
    Agent specialized in synthesizing differential diagnoses.

    Capabilities:
    - Evidence integration from all sources
    - Bayesian hypothesis ranking
    - Confidence assessment
    - Uncertainty quantification
    - Differential explanation generation
    """

    def __init__(
        self,
        config: DifferentialAgentConfig | None = None,
        bayesian_scorer=None,
        primekg_overlay=None,
        neo4j_client=None,
    ):
        """
        Initialize the differential diagnosis agent.

        Args:
            config: Agent configuration
            bayesian_scorer: Bayesian scoring service
            primekg_overlay: PrimeKG overlay
            neo4j_client: Neo4j client
        """
        super().__init__(
            role=AgentRole.DIFFERENTIAL_EXPERT,
            config=config or DifferentialAgentConfig(),
        )
        self.config: DifferentialAgentConfig = self.config

        self._scorer = bayesian_scorer
        self._primekg = primekg_overlay
        self._neo4j = neo4j_client

        # Working state
        self._current_hypotheses: list[dict] = []
        self._evidence_summary: dict[str, Any] = {}

    async def analyze(
        self,
        patient_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze all evidence and generate differential diagnosis.

        Integrates:
        - Phenotype analysis
        - Genetic findings
        - Medical history
        - Wearable data
        - Other agents' analyses

        Args:
            patient_data: Complete patient data
            context: Context including other agents' analyses

        Returns:
            Comprehensive differential diagnosis
        """
        context = context or {}

        # Extract evidence
        phenotypes = patient_data.get("phenotypes", [])
        genetic = patient_data.get("genetic_variants", [])
        history = patient_data.get("medical_history", [])
        family_history = patient_data.get("family_history", [])
        wearable = patient_data.get("wearable_data", [])

        # Get analyses from other agents if available
        phenotype_analysis = context.get("phenotype_analysis", {})
        genetic_analysis = context.get("genetic_analysis", {})
        _history_analysis = context.get("history_analysis", {})  # Reserved for future use

        # Generate candidate hypotheses
        hypotheses = await self._generate_candidates(
            phenotypes=phenotypes,
            genetic=genetic,
            phenotype_analysis=phenotype_analysis,
            genetic_analysis=genetic_analysis,
        )

        # Score hypotheses
        scored = await self._score_hypotheses(
            hypotheses,
            phenotypes=phenotypes,
            genetic=genetic,
            history=history,
            family_history=family_history,
            wearable=wearable,
            phenotype_analysis=phenotype_analysis,
            genetic_analysis=genetic_analysis,
        )

        # Rank and select differential
        differential = self._rank_differential(scored)

        # Assess confidence
        confidence_assessment = self._assess_confidence(differential)

        # Generate explanations
        explanations = self._generate_explanations(
            differential,
            phenotype_analysis=phenotype_analysis,
            genetic_analysis=genetic_analysis,
        )

        result = {
            "differential": differential[:self.config.max_differential],
            "primary_diagnosis": differential[0] if differential else None,
            "confidence_assessment": confidence_assessment,
            "explanations": explanations,
            "evidence_summary": {
                "phenotype_count": len(phenotypes),
                "genetic_variant_count": len(genetic),
                "history_items": len(history),
                "family_history_items": len(family_history),
                "wearable_data_points": len(wearable),
            },
            "hypotheses_considered": len(hypotheses),
            "hypotheses_ranked": len(differential),
        }

        self._current_hypotheses = differential
        self._evidence_summary = result["evidence_summary"]

        logger.info(
            "differential_analysis_complete",
            agent_id=self.agent_id,
            hypotheses=len(differential),
            top_confidence=differential[0]["combined_score"] if differential else 0,
        )

        return result

    async def generate_hypotheses(
        self,
        evidence: list[dict[str, Any]],
        existing_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate or refine differential hypotheses.

        Args:
            evidence: All evidence items
            existing_hypotheses: Current hypotheses

        Returns:
            Refined hypothesis list
        """
        # Separate evidence by type
        phenotypes = [e for e in evidence if e.get("evidence_type") == "phenotype"]
        genetic = [e for e in evidence if e.get("evidence_type") == "genetic"]

        # Start with existing hypotheses if available
        hypotheses = existing_hypotheses or []

        # Add new candidates from evidence
        new_candidates = await self._generate_candidates(
            phenotypes=phenotypes,
            genetic=genetic,
        )

        # Merge avoiding duplicates
        existing_ids = {h.get("disease_id") for h in hypotheses}
        for candidate in new_candidates:
            if candidate.get("disease_id") not in existing_ids:
                hypotheses.append(candidate)
                existing_ids.add(candidate.get("disease_id"))

        # Re-score all
        scored = await self._score_hypotheses(
            hypotheses,
            phenotypes=phenotypes,
            genetic=genetic,
        )

        return self._rank_differential(scored)

    async def evaluate_hypothesis(
        self,
        hypothesis: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Provide comprehensive evaluation of a hypothesis.

        Args:
            hypothesis: Hypothesis to evaluate
            evidence: All evidence

        Returns:
            Multi-factor evaluation
        """
        # Separate evidence
        phenotypes = [e for e in evidence if e.get("evidence_type") == "phenotype"]
        genetic = [e for e in evidence if e.get("evidence_type") == "genetic"]
        history = [e for e in evidence if e.get("evidence_type") == "history"]
        family = [e for e in evidence if e.get("evidence_type") == "family"]

        # Score individual components
        phenotype_score = await self._score_phenotype_match(hypothesis, phenotypes)
        genetic_score = await self._score_genetic_match(hypothesis, genetic)
        history_score = self._score_history_match(hypothesis, history, family)

        # Combined score
        combined = (
            phenotype_score * self.config.phenotype_weight +
            genetic_score * self.config.genetic_weight +
            history_score * self.config.history_weight
        )

        # Identify supporting and refuting evidence
        supporting = []
        refuting = []

        for e in evidence:
            relevance = self._assess_evidence_relevance(hypothesis, e)
            if relevance > 0.5:
                supporting.append({
                    "evidence": e.get("value"),
                    "type": e.get("evidence_type"),
                    "relevance": relevance,
                })
            elif relevance < -0.5:
                refuting.append({
                    "evidence": e.get("value"),
                    "type": e.get("evidence_type"),
                    "relevance": relevance,
                })

        return {
            "combined_score": combined,
            "phenotype_score": phenotype_score,
            "genetic_score": genetic_score,
            "history_score": history_score,
            "supporting_evidence": supporting,
            "refuting_evidence": refuting,
            "confidence": self._calculate_confidence(combined, supporting, refuting),
            "reasoning": self._generate_hypothesis_reasoning(
                hypothesis, phenotype_score, genetic_score, history_score
            ),
        }

    async def _generate_candidates(
        self,
        phenotypes: list[dict] | None = None,
        genetic: list[dict] | None = None,
        phenotype_analysis: dict | None = None,
        genetic_analysis: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Generate candidate hypotheses from evidence."""
        candidates = []
        seen_ids = set()

        # From phenotype analysis
        if phenotype_analysis:
            for assoc in phenotype_analysis.get("disease_associations", []):
                disease_id = assoc.get("disease_id")
                if disease_id and disease_id not in seen_ids:
                    candidates.append({
                        "disease_id": disease_id,
                        "disease_name": assoc.get("disease_name"),
                        "source": "phenotype",
                        "initial_score": assoc.get("phenotype_matches", 0) / 10,
                    })
                    seen_ids.add(disease_id)

        # From genetic analysis
        if genetic_analysis:
            for gene_info in genetic_analysis.get("candidate_genes", []):
                for disease in gene_info.get("top_diseases", []):
                    disease_name = disease.get("disease_name") or disease.get("name")
                    disease_id = disease.get("disease_id") or disease.get("mondo_id")

                    # Query by name if ID not available
                    if disease_name and not disease_id and self._neo4j:
                        try:
                            results = await self._neo4j.run("""
                                MATCH (d:PrimeKGDisease)
                                WHERE toLower(d.name) = toLower($name)
                                RETURN d.mondo_id as disease_id, d.name as disease_name
                                LIMIT 1
                            """, {"name": disease_name})
                            if results:
                                disease_id = results[0].get("disease_id")
                        except Exception as e:
                            logger.warning("disease_lookup_failed", name=disease_name, error=str(e))

                    if disease_id and disease_id not in seen_ids:
                        candidates.append({
                            "disease_id": disease_id,
                            "disease_name": disease_name,
                            "source": "genetic",
                            "gene_symbol": gene_info.get("gene_symbol"),
                            "initial_score": gene_info.get("pathogenicity_score", 0.5),
                        })
                        seen_ids.add(disease_id)

        # Direct query if we have phenotypes
        if phenotypes and self._neo4j:
            hpo_codes = [
                p.get("code") or p.get("hpo_id")
                for p in phenotypes
                if (p.get("code") or p.get("hpo_id")) and not p.get("negated")
            ]

            if hpo_codes:
                query = """
                MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
                WHERE p.hpo_id IN $phenotypes
                WITH d, count(DISTINCT p) as matches
                WHERE matches >= $min_matches
                OPTIONAL MATCH (d)-[:ASSOCIATED_WITH|`associated with`]-(g:PrimeKGGene)
                WITH d, matches, collect(DISTINCT g.symbol) as genes
                RETURN d.mondo_id as disease_id,
                       d.name as disease_name,
                       matches,
                       genes,
                       d.prevalence as prevalence
                ORDER BY matches DESC
                LIMIT $limit
                """

                try:
                    results = await self._neo4j.run(query, {
                        "phenotypes": hpo_codes,
                        "min_matches": max(1, len(hpo_codes) // 4),
                        "limit": self.config.max_hypotheses * 2,
                    })

                    for r in (results or []):
                        disease_id = r.get("disease_id")
                        if disease_id and disease_id not in seen_ids:
                            candidates.append({
                                "disease_id": disease_id,
                                "disease_name": r.get("disease_name"),
                                "matched_phenotypes_count": r.get("matches"),
                                "associated_genes": r.get("genes", []),
                                "prevalence": r.get("prevalence"),
                                "source": "direct_query",
                            })
                            seen_ids.add(disease_id)

                except Exception as e:
                    logger.error("candidate_query_failed", error=str(e))

        return candidates

    async def _score_hypotheses(
        self,
        hypotheses: list[dict[str, Any]],
        phenotypes: list[dict] | None = None,
        genetic: list[dict] | None = None,
        history: list[dict] | None = None,
        family_history: list[dict] | None = None,
        wearable: list[dict] | None = None,
        phenotype_analysis: dict | None = None,
        genetic_analysis: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Score all hypotheses."""
        scored = []

        for h in hypotheses:
            # Phenotype score
            phenotype_score = await self._score_phenotype_match(
                h, phenotypes or [], phenotype_analysis
            )

            # Genetic score
            genetic_score = await self._score_genetic_match(
                h, genetic or [], genetic_analysis
            )

            # History score
            history_score = self._score_history_match(
                h, history or [], family_history or []
            )

            # Wearable score (bonus)
            wearable_score = self._score_wearable_match(h, wearable or [])

            # Combined weighted score
            combined = (
                phenotype_score * self.config.phenotype_weight +
                genetic_score * self.config.genetic_weight +
                history_score * self.config.history_weight +
                wearable_score * self.config.wearable_weight
            )

            h_scored = dict(h)
            h_scored.update({
                "phenotype_score": phenotype_score,
                "genetic_score": genetic_score,
                "history_score": history_score,
                "wearable_score": wearable_score,
                "combined_score": combined,
            })

            scored.append(h_scored)

        return scored

    async def _score_phenotype_match(
        self,
        hypothesis: dict[str, Any],
        phenotypes: list[dict],
        phenotype_analysis: dict | None = None,
    ) -> float:
        """Score phenotype match for hypothesis."""
        disease_id = hypothesis.get("disease_id")
        if not disease_id:
            return 0.0

        # Use pre-computed score if available
        if phenotype_analysis:
            for assoc in phenotype_analysis.get("disease_associations", []):
                if assoc.get("disease_id") == disease_id:
                    # Normalize to 0-1
                    matches = assoc.get("phenotype_matches", 0)
                    total = phenotype_analysis.get("phenotype_count", 1) or 1
                    return min(1.0, matches / total)

        # Compute directly
        patient_hpo = [
            p.get("code") or p.get("hpo_id")
            for p in phenotypes
            if (p.get("code") or p.get("hpo_id")) and not p.get("negated")
        ]

        if not patient_hpo or not self._neo4j:
            return 0.5

        # Get disease phenotypes
        query = """
        MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WHERE d.mondo_id = $disease_id
        RETURN collect(p.hpo_id) as phenotypes
        """

        try:
            results = await self._neo4j.run(query, {"disease_id": disease_id})
            if results:
                expected = set(results[0].get("phenotypes", []))
                if expected:
                    matched = len(set(patient_hpo) & expected)
                    recall = matched / len(patient_hpo) if patient_hpo else 0
                    precision = matched / len(expected) if expected else 0
                    return (recall + precision) / 2
        except Exception:
            pass

        return 0.5

    async def _score_genetic_match(
        self,
        hypothesis: dict[str, Any],
        genetic: list[dict],
        genetic_analysis: dict | None = None,
    ) -> float:
        """Score genetic match for hypothesis."""
        if not genetic:
            return 0.5  # No data, neutral

        disease_id = hypothesis.get("disease_id")
        if not disease_id:
            return 0.0

        # Get disease genes
        disease_genes = hypothesis.get("associated_genes", [])
        if not disease_genes and self._neo4j:
            try:
                results = await self._neo4j.run("""
                    MATCH (g:PrimeKGGene)-[:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
                    WHERE d.mondo_id = $disease_id
                    RETURN collect(g.symbol) as genes
                """, {"disease_id": disease_id})
                if results:
                    disease_genes = results[0].get("genes", [])
            except Exception as e:
                logger.debug("disease_genes_query_failed", disease_id=disease_id, error=str(e))

        if not disease_genes:
            return 0.5

        # Check for variants in disease genes
        patient_genes = [
            g.get("code") or g.get("gene_symbol") or g.get("gene")
            for g in genetic
            if g.get("code") or g.get("gene_symbol") or g.get("gene")
        ]

        matching_genes = set(patient_genes) & set(disease_genes)
        if not matching_genes:
            return 0.3

        # Score based on pathogenicity of matching variants
        score = 0.5
        for g in genetic:
            gene = g.get("code") or g.get("gene_symbol") or g.get("gene")
            if gene in matching_genes:
                pathogenicity = str(g.get("severity", "")).lower()
                if "pathogenic" in pathogenicity and "likely" not in pathogenicity:
                    score = max(score, 0.95)
                elif "likely_pathogenic" in pathogenicity or "likely pathogenic" in pathogenicity:
                    score = max(score, 0.85)
                elif "vus" in pathogenicity or "uncertain" in pathogenicity:
                    score = max(score, 0.6)

        return score

    def _score_history_match(
        self,
        hypothesis: dict[str, Any],
        history: list[dict],
        family_history: list[dict],
    ) -> float:
        """Score history match for hypothesis."""
        if not history and not family_history:
            return 0.5  # Neutral

        disease_name = (hypothesis.get("disease_name") or "").lower()
        score = 0.5

        # Check family history
        for fh in family_history:
            fh_value = (fh.get("value") or "").lower()
            if disease_name and disease_name in fh_value:
                score = max(score, 0.8)
            # Check for related terms
            for gene in hypothesis.get("associated_genes", []):
                if gene.lower() in fh_value:
                    score = max(score, 0.7)

        # Check medical history
        for h in history:
            h_value = (h.get("value") or "").lower()
            if h.get("negated") and disease_name in h_value:
                score = min(score, 0.2)  # Contradicting history

        return score

    def _score_wearable_match(
        self,
        hypothesis: dict[str, Any],
        wearable: list[dict],
    ) -> float:
        """Score wearable data match for hypothesis."""
        if not wearable:
            return 0.5  # Neutral, no data

        # This would be disease-specific logic
        # For now, return neutral
        return 0.5

    def _rank_differential(
        self,
        scored: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank hypotheses into differential diagnosis."""
        # Filter by minimum score
        filtered = [
            h for h in scored
            if h.get("combined_score", 0) >= self.config.min_score_threshold
        ]

        # Sort by combined score
        ranked = sorted(
            filtered,
            key=lambda x: x.get("combined_score", 0),
            reverse=True,
        )

        # Assign ranks
        for i, h in enumerate(ranked):
            h["rank"] = i + 1

        return ranked[:self.config.max_differential]

    def _assess_confidence(
        self,
        differential: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Assess confidence in the differential diagnosis."""
        if not differential:
            return {
                "level": "insufficient_data",
                "primary_confidence": 0.0,
                "message": "Insufficient evidence to generate differential",
            }

        top_score = differential[0].get("combined_score", 0)
        second_score = differential[1].get("combined_score", 0) if len(differential) > 1 else 0

        gap = top_score - second_score

        if top_score >= self.config.confidence_required_for_primary and gap >= self.config.uncertainty_threshold:
            level = "high"
            message = "Strong evidence supporting primary diagnosis"
        elif top_score >= 0.5 and gap >= 0.1:
            level = "moderate"
            message = "Moderate confidence, consider additional testing"
        elif top_score >= 0.3:
            level = "low"
            message = "Low confidence, multiple diagnoses equally likely"
        else:
            level = "uncertain"
            message = "Highly uncertain, more evidence needed"

        return {
            "level": level,
            "primary_confidence": top_score,
            "differential_uncertainty": 1 - gap if len(differential) > 1 else 0,
            "message": message,
            "top_diagnoses_gap": gap,
        }

    def _generate_explanations(
        self,
        differential: list[dict[str, Any]],
        phenotype_analysis: dict | None = None,
        genetic_analysis: dict | None = None,
    ) -> dict[str, str]:
        """Generate explanations for top diagnoses."""
        explanations = {}

        for h in differential[:5]:
            disease_name = h.get("disease_name", "Unknown")
            parts = []

            # Phenotype explanation
            pheno_score = h.get("phenotype_score", 0)
            if pheno_score >= 0.7:
                parts.append("Strong phenotypic match")
            elif pheno_score >= 0.5:
                parts.append("Moderate phenotypic overlap")
            elif pheno_score < 0.3:
                parts.append("Limited phenotypic evidence")

            # Genetic explanation
            gen_score = h.get("genetic_score", 0.5)
            if gen_score >= 0.8:
                parts.append("pathogenic variant in disease gene")
            elif gen_score >= 0.6:
                parts.append("variant of uncertain significance in disease gene")
            elif gen_score < 0.5 and h.get("associated_genes"):
                parts.append("no variants found in associated genes")

            # History explanation
            hist_score = h.get("history_score", 0.5)
            if hist_score >= 0.7:
                parts.append("consistent with family history")
            elif hist_score < 0.3:
                parts.append("potentially conflicting history")

            explanations[disease_name] = "; ".join(parts) if parts else "Based on combined evidence"

        return explanations

    def _assess_evidence_relevance(
        self,
        hypothesis: dict[str, Any],
        evidence: dict[str, Any],
    ) -> float:
        """Assess how relevant an evidence item is to a hypothesis."""
        # Returns -1 to 1: negative = refuting, positive = supporting
        evidence_type = evidence.get("evidence_type")
        is_negated = evidence.get("negated", False)

        disease_name = (hypothesis.get("disease_name") or "").lower()
        evidence_value = (evidence.get("value") or "").lower()

        if evidence_type == "phenotype":
            # Check if phenotype is expected for disease
            # Simplified - would check against disease phenotypes
            if is_negated:
                return -0.3  # Absent phenotype weakly refutes
            return 0.3  # Present phenotype weakly supports

        elif evidence_type == "genetic":
            gene = evidence.get("code") or evidence.get("gene_symbol")
            if gene and gene in hypothesis.get("associated_genes", []):
                pathogenicity = str(evidence.get("severity", "")).lower()
                if "pathogenic" in pathogenicity:
                    return 0.9
                elif "benign" in pathogenicity:
                    return -0.5
                return 0.3
            return 0.0

        elif evidence_type == "family":
            if disease_name in evidence_value:
                return 0.7 if not is_negated else -0.5

        return 0.0

    def _calculate_confidence(
        self,
        combined_score: float,
        supporting: list[dict],
        refuting: list[dict],
    ) -> float:
        """Calculate confidence based on evidence balance."""
        base = combined_score

        # Boost for supporting evidence
        support_boost = min(0.1, len(supporting) * 0.02)

        # Penalty for refuting evidence
        refute_penalty = min(0.2, len(refuting) * 0.05)

        return max(0, min(1, base + support_boost - refute_penalty))

    def _generate_hypothesis_reasoning(
        self,
        hypothesis: dict[str, Any],
        pheno_score: float,
        genetic_score: float,
        history_score: float,
    ) -> str:
        """Generate reasoning text for a hypothesis."""
        parts = []
        disease = hypothesis.get("disease_name", "This diagnosis")

        if pheno_score >= 0.7:
            parts.append(f"{disease} matches the phenotypic presentation well")
        elif pheno_score >= 0.5:
            parts.append(f"{disease} shows partial phenotypic overlap")
        else:
            parts.append(f"{disease} has limited phenotypic support")

        if genetic_score >= 0.8:
            parts.append("supported by pathogenic genetic findings")
        elif genetic_score >= 0.6:
            parts.append("genetic findings are suggestive")
        elif genetic_score < 0.4:
            parts.append("no supporting genetic evidence")

        if history_score >= 0.7:
            parts.append("consistent with patient/family history")
        elif history_score < 0.3:
            parts.append("some historical factors may argue against")

        return ". ".join(parts) + "."


# =============================================================================
# Factory Function
# =============================================================================

def create_differential_agent(
    config: DifferentialAgentConfig | None = None,
    bayesian_scorer=None,
    primekg_overlay=None,
    neo4j_client=None,
) -> DifferentialAgent:
    """Create a differential diagnosis agent instance."""
    return DifferentialAgent(
        config=config,
        bayesian_scorer=bayesian_scorer,
        primekg_overlay=primekg_overlay,
        neo4j_client=neo4j_client,
    )
