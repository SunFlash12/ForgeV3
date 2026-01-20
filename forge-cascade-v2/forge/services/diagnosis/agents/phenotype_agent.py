"""
Phenotype Analysis Agent

Specialist agent for analyzing phenotypic evidence using HPO ontology.
"""

from dataclasses import dataclass
from typing import Any

import structlog

from .base import DiagnosticAgent, AgentConfig, AgentRole, AgentMessage, MessageType

logger = structlog.get_logger(__name__)


@dataclass
class PhenotypeAgentConfig(AgentConfig):
    """Configuration for phenotype agent."""
    # HPO matching thresholds
    min_semantic_similarity: float = 0.7
    include_parent_terms: bool = True
    max_hierarchy_depth: int = 5

    # Frequency weights
    core_phenotype_weight: float = 0.8
    common_phenotype_weight: float = 0.5
    rare_phenotype_weight: float = 0.3

    # Analysis settings
    consider_negated: bool = True
    adjust_for_age: bool = True


class PhenotypeAgent(DiagnosticAgent):
    """
    Agent specialized in phenotype analysis.

    Capabilities:
    - HPO term matching and normalization
    - Semantic similarity calculation
    - Phenotype-disease association scoring
    - Missing phenotype identification
    - Discriminating phenotype suggestions
    """

    def __init__(
        self,
        config: PhenotypeAgentConfig | None = None,
        hpo_service=None,
        primekg_overlay=None,
        neo4j_client=None,
    ):
        """
        Initialize the phenotype agent.

        Args:
            config: Agent configuration
            hpo_service: HPO ontology service
            primekg_overlay: PrimeKG overlay for queries
            neo4j_client: Neo4j client
        """
        super().__init__(
            role=AgentRole.PHENOTYPE_EXPERT,
            config=config or PhenotypeAgentConfig(),
        )
        self.config: PhenotypeAgentConfig = self.config

        self._hpo = hpo_service
        self._primekg = primekg_overlay
        self._neo4j = neo4j_client

        # Analysis cache
        self._phenotype_cache: dict[str, dict] = {}

    async def analyze(
        self,
        patient_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze patient phenotypes.

        Performs:
        1. Phenotype normalization to HPO
        2. Semantic expansion (parents/children)
        3. Frequency analysis
        4. Pattern recognition

        Args:
            patient_data: Patient information with phenotypes
            context: Additional context

        Returns:
            Phenotype analysis results
        """
        phenotypes = patient_data.get("phenotypes", [])
        negated_phenotypes = patient_data.get("negated_phenotypes", [])
        age = patient_data.get("age")
        age_of_onset = patient_data.get("age_of_onset")

        # Normalize phenotypes
        normalized = await self._normalize_phenotypes(phenotypes)
        normalized_negated = await self._normalize_phenotypes(negated_phenotypes)

        # Expand with related terms
        expanded = await self._expand_phenotypes(normalized)

        # Categorize by system
        by_system = self._categorize_by_system(normalized)

        # Get phenotype-disease associations
        disease_associations = await self._get_disease_associations(normalized)

        # Find phenotype patterns
        patterns = self._identify_patterns(normalized, negated_phenotypes)

        # Calculate phenotype profile
        profile = {
            "normalized_phenotypes": normalized,
            "negated_phenotypes": normalized_negated,
            "expanded_phenotypes": expanded,
            "systems_affected": list(by_system.keys()),
            "phenotypes_by_system": by_system,
            "disease_associations": disease_associations[:20],
            "patterns": patterns,
            "phenotype_count": len(normalized),
            "negated_count": len(normalized_negated),
        }

        # Age-based adjustments
        if self.config.adjust_for_age and age_of_onset is not None:
            profile["age_onset_notes"] = self._assess_age_onset(
                normalized, age_of_onset
            )

        logger.info(
            "phenotype_analysis_complete",
            agent_id=self.agent_id,
            phenotype_count=len(normalized),
            systems=len(by_system),
        )

        return profile

    async def generate_hypotheses(
        self,
        evidence: list[dict[str, Any]],
        existing_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate disease hypotheses from phenotype evidence.

        Args:
            evidence: Phenotype evidence items
            existing_hypotheses: Current hypotheses to refine

        Returns:
            List of phenotype-based hypotheses
        """
        # Extract HPO codes from evidence
        hpo_codes = []
        for e in evidence:
            if e.get("evidence_type") == "phenotype" and e.get("code"):
                if not e.get("negated"):
                    hpo_codes.append(e["code"])

        if not hpo_codes:
            return existing_hypotheses or []

        # Query diseases matching phenotypes
        hypotheses = []

        if self._neo4j:
            query = """
            MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
            WHERE p.hpo_id IN $phenotypes
            WITH d, collect(DISTINCT p.hpo_id) as matched, count(DISTINCT p) as match_count
            OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(all_p:PrimeKGPhenotype)
            WITH d, matched, match_count, count(DISTINCT all_p) as total_phenotypes
            WHERE match_count >= $min_matches
            RETURN d.mondo_id as disease_id,
                   d.name as disease_name,
                   matched,
                   match_count,
                   total_phenotypes,
                   toFloat(match_count) / toFloat($input_count) as recall,
                   toFloat(match_count) / toFloat(total_phenotypes + 0.001) as precision
            ORDER BY match_count DESC, precision DESC
            LIMIT $limit
            """

            try:
                results = await self._neo4j.run(query, {
                    "phenotypes": hpo_codes,
                    "min_matches": max(1, len(hpo_codes) // 3),
                    "input_count": len(hpo_codes),
                    "limit": self.config.max_hypotheses,
                })

                for r in (results or []):
                    hypothesis = {
                        "disease_id": r["disease_id"],
                        "disease_name": r["disease_name"],
                        "matched_phenotypes": r["matched"],
                        "match_count": r["match_count"],
                        "total_expected": r["total_phenotypes"],
                        "phenotype_recall": r["recall"],
                        "phenotype_precision": r["precision"],
                        "phenotype_score": (r["recall"] + r["precision"]) / 2,
                        "source": "phenotype_agent",
                    }
                    hypotheses.append(hypothesis)

            except Exception as e:
                logger.error("hypothesis_query_failed", error=str(e))

        # Merge with existing hypotheses
        if existing_hypotheses:
            existing_ids = {h["disease_id"] for h in hypotheses}
            for eh in existing_hypotheses:
                if eh["disease_id"] not in existing_ids:
                    hypotheses.append(eh)

        return hypotheses

    async def evaluate_hypothesis(
        self,
        hypothesis: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Evaluate a hypothesis from a phenotype perspective.

        Args:
            hypothesis: Hypothesis to evaluate
            evidence: Evidence items

        Returns:
            Phenotype-based evaluation
        """
        disease_id = hypothesis.get("disease_id")
        if not disease_id:
            return {"score": 0.0, "reasoning": "No disease ID"}

        # Get patient phenotypes
        patient_hpo = []
        patient_negated = []
        for e in evidence:
            if e.get("evidence_type") == "phenotype" and e.get("code"):
                if e.get("negated"):
                    patient_negated.append(e["code"])
                else:
                    patient_hpo.append(e["code"])

        # Get expected phenotypes for disease
        expected = await self._get_disease_phenotypes(disease_id)

        if not expected:
            return {
                "score": 0.5,
                "reasoning": "No expected phenotypes found for disease",
                "matched": [],
                "missing": [],
            }

        # Calculate matches
        matched = [p for p in patient_hpo if p in expected]
        missing = [p for p in expected if p not in patient_hpo]
        contradicted = [p for p in patient_negated if p in expected]

        # Score calculation
        recall = len(matched) / len(patient_hpo) if patient_hpo else 0
        precision = len(matched) / len(expected) if expected else 0
        contradiction_penalty = len(contradicted) * 0.1

        score = (recall * 0.6 + precision * 0.4) - contradiction_penalty
        score = max(0.0, min(1.0, score))

        # Build reasoning
        reasoning_parts = []
        if matched:
            reasoning_parts.append(f"Matched {len(matched)}/{len(patient_hpo)} patient phenotypes")
        if missing:
            reasoning_parts.append(f"Missing {len(missing)} expected phenotypes")
        if contradicted:
            reasoning_parts.append(f"Warning: {len(contradicted)} negated phenotypes are expected for this disease")

        return {
            "score": score,
            "reasoning": ". ".join(reasoning_parts) if reasoning_parts else "No specific matches",
            "matched_phenotypes": matched,
            "missing_phenotypes": missing[:10],
            "contradicted_phenotypes": contradicted,
            "recall": recall,
            "precision": precision,
        }

    async def suggest_discriminating_phenotypes(
        self,
        hypotheses: list[dict[str, Any]],
        known_phenotypes: list[str],
    ) -> list[dict[str, Any]]:
        """
        Suggest phenotypes that would discriminate between hypotheses.

        Args:
            hypotheses: Current hypotheses
            known_phenotypes: Already known phenotypes

        Returns:
            List of discriminating phenotype suggestions
        """
        if len(hypotheses) < 2:
            return []

        suggestions = []
        known_set = set(known_phenotypes)

        # Get phenotypes for each hypothesis
        hypothesis_phenotypes = {}
        for h in hypotheses[:5]:  # Top 5 hypotheses
            disease_id = h.get("disease_id")
            if disease_id:
                phenotypes = await self._get_disease_phenotypes(disease_id)
                hypothesis_phenotypes[disease_id] = set(phenotypes)

        # Find phenotypes that discriminate
        all_phenotypes = set()
        for phenos in hypothesis_phenotypes.values():
            all_phenotypes.update(phenos)

        for hpo_id in all_phenotypes - known_set:
            # Count how many hypotheses have this phenotype
            present_count = sum(
                1 for phenos in hypothesis_phenotypes.values()
                if hpo_id in phenos
            )

            # Best discriminators are present in roughly half
            discrimination_score = 1 - abs(present_count / len(hypotheses) - 0.5) * 2

            if discrimination_score > 0.3:
                # Get phenotype name
                name = hpo_id
                if self._hpo:
                    try:
                        term = self._hpo.get_term(hpo_id)
                        if term:
                            name = term.name
                    except Exception:
                        pass

                suggestions.append({
                    "hpo_id": hpo_id,
                    "name": name,
                    "discrimination_score": discrimination_score,
                    "present_in_hypotheses": present_count,
                    "hypotheses_affected": [
                        h["disease_id"] for h in hypotheses[:5]
                        if h["disease_id"] in hypothesis_phenotypes
                        and hpo_id in hypothesis_phenotypes[h["disease_id"]]
                    ],
                })

        # Sort by discrimination score
        suggestions.sort(key=lambda x: x["discrimination_score"], reverse=True)
        return suggestions[:10]

    async def _normalize_phenotypes(
        self,
        phenotypes: list[str | dict],
    ) -> list[dict[str, Any]]:
        """Normalize phenotype inputs to HPO terms."""
        normalized = []

        for phenotype in phenotypes:
            if isinstance(phenotype, dict):
                hpo_id = phenotype.get("code") or phenotype.get("hpo_id")
                name = phenotype.get("name") or phenotype.get("value")
            elif isinstance(phenotype, str):
                if phenotype.startswith("HP:"):
                    hpo_id = phenotype
                    name = phenotype
                else:
                    # Text - try to match
                    hpo_id = None
                    name = phenotype
                    if self._hpo:
                        try:
                            # search_terms is synchronous
                            matches = self._hpo.search_terms(phenotype, limit=1)
                            if matches:
                                hpo_id = matches[0].hpo_id
                                name = matches[0].name
                        except Exception:
                            pass
            else:
                continue

            normalized.append({
                "hpo_id": hpo_id,
                "name": name,
                "original": phenotype,
            })

        return normalized

    async def _expand_phenotypes(
        self,
        phenotypes: list[dict[str, Any]],
    ) -> list[str]:
        """Expand phenotypes with parent terms."""
        expanded = set()

        for p in phenotypes:
            hpo_id = p.get("hpo_id")
            if hpo_id:
                expanded.add(hpo_id)

                if self.config.include_parent_terms and self._hpo:
                    try:
                        # Get ancestors up to max depth
                        ancestors = self._hpo.get_ancestors(
                            hpo_id,
                            max_depth=self.config.max_hierarchy_depth,
                        )
                        expanded.update(ancestors)
                    except Exception:
                        pass

        return list(expanded)

    def _categorize_by_system(
        self,
        phenotypes: list[dict[str, Any]],
    ) -> dict[str, list[str]]:
        """Categorize phenotypes by body system."""
        # HPO top-level categories
        system_prefixes = {
            "HP:0000152": "Head and neck",
            "HP:0000478": "Eye",
            "HP:0000598": "Ear",
            "HP:0001626": "Cardiovascular",
            "HP:0002086": "Respiratory",
            "HP:0001871": "Hematologic",
            "HP:0000119": "Genitourinary",
            "HP:0001939": "Metabolic",
            "HP:0003011": "Musculoskeletal",
            "HP:0000707": "Nervous system",
            "HP:0001574": "Integument",
            "HP:0025031": "Digestive",
            "HP:0000818": "Endocrine",
            "HP:0001197": "Prenatal/Birth",
            "HP:0040064": "Limbs",
        }

        by_system: dict[str, list[str]] = {}

        for p in phenotypes:
            hpo_id = p.get("hpo_id")
            if not hpo_id:
                continue

            # Determine system (simplified - would use HPO hierarchy in production)
            assigned = False
            if self._hpo:
                try:
                    ancestors = self._hpo.get_ancestors(hpo_id, max_depth=10)
                    for sys_id, sys_name in system_prefixes.items():
                        if sys_id in ancestors:
                            if sys_name not in by_system:
                                by_system[sys_name] = []
                            by_system[sys_name].append(hpo_id)
                            assigned = True
                            break
                except Exception:
                    pass

            if not assigned:
                if "Other" not in by_system:
                    by_system["Other"] = []
                by_system["Other"].append(hpo_id)

        return by_system

    async def _get_disease_associations(
        self,
        phenotypes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Get diseases associated with phenotypes."""
        hpo_codes = [p["hpo_id"] for p in phenotypes if p.get("hpo_id")]

        if not hpo_codes or not self._neo4j:
            return []

        query = """
        MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WHERE p.hpo_id IN $phenotypes
        WITH d, count(DISTINCT p) as match_count
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               match_count
        ORDER BY match_count DESC
        LIMIT 30
        """

        try:
            results = await self._neo4j.run(query, {"phenotypes": hpo_codes})
            return [
                {
                    "disease_id": r["disease_id"],
                    "disease_name": r["disease_name"],
                    "phenotype_matches": r["match_count"],
                }
                for r in (results or [])
            ]
        except Exception:
            return []

    def _identify_patterns(
        self,
        phenotypes: list[dict[str, Any]],
        negated: list[str],
    ) -> list[str]:
        """Identify phenotype patterns."""
        patterns = []

        # Check for syndromic patterns
        hpo_ids = {p["hpo_id"] for p in phenotypes if p.get("hpo_id")}

        # Example pattern detection (would be more sophisticated in production)
        if len(hpo_ids) > 5:
            patterns.append("Multi-system involvement")

        if any("HP:0001250" in str(p) for p in hpo_ids):  # Seizures
            patterns.append("Epilepsy phenotype")

        if any("HP:0001249" in str(p) for p in hpo_ids):  # Intellectual disability
            patterns.append("Neurodevelopmental phenotype")

        if negated:
            patterns.append(f"Explicitly negated: {len(negated)} phenotypes")

        return patterns

    def _assess_age_onset(
        self,
        phenotypes: list[dict[str, Any]],
        age_of_onset: int,
    ) -> list[str]:
        """Assess phenotypes relative to age of onset."""
        notes = []

        if age_of_onset < 1:
            notes.append("Neonatal/infantile onset - consider congenital conditions")
        elif age_of_onset < 5:
            notes.append("Early childhood onset - consider developmental disorders")
        elif age_of_onset < 18:
            notes.append("Pediatric onset")
        else:
            notes.append("Adult onset - may indicate later-onset genetic conditions")

        return notes

    async def _get_disease_phenotypes(
        self,
        disease_id: str,
    ) -> list[str]:
        """Get expected phenotypes for a disease."""
        cache_key = f"disease_phenotypes_{disease_id}"
        if cache_key in self._phenotype_cache:
            return self._phenotype_cache[cache_key].get("phenotypes", [])

        if not self._neo4j:
            return []

        query = """
        MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WHERE d.mondo_id = $disease_id
        RETURN p.hpo_id as hpo_id
        """

        try:
            results = await self._neo4j.run(query, {"disease_id": disease_id})
            phenotypes = [r["hpo_id"] for r in (results or []) if r.get("hpo_id")]
            self._phenotype_cache[cache_key] = {"phenotypes": phenotypes}
            return phenotypes
        except Exception:
            return []


# =============================================================================
# Factory Function
# =============================================================================

def create_phenotype_agent(
    config: PhenotypeAgentConfig | None = None,
    hpo_service=None,
    primekg_overlay=None,
    neo4j_client=None,
) -> PhenotypeAgent:
    """Create a phenotype agent instance."""
    return PhenotypeAgent(
        config=config,
        hpo_service=hpo_service,
        primekg_overlay=primekg_overlay,
        neo4j_client=neo4j_client,
    )
