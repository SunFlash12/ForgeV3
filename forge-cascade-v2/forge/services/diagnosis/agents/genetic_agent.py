"""
Genetic Analysis Agent

Specialist agent for analyzing genetic evidence and variant interpretation.
"""

import math
from dataclasses import dataclass
from typing import Any

import structlog

from .base import AgentConfig, AgentRole, DiagnosticAgent

logger = structlog.get_logger(__name__)


@dataclass
class GeneticAgentConfig(AgentConfig):
    """Configuration for genetic agent."""
    # Pathogenicity thresholds
    pathogenic_lr: float = 50.0
    likely_pathogenic_lr: float = 10.0
    vous_lr: float = 2.0
    likely_benign_lr: float = 0.2
    benign_lr: float = 0.1

    # Population frequency thresholds
    rare_af_threshold: float = 0.001  # 0.1%
    ultra_rare_af_threshold: float = 0.0001  # 0.01%

    # Gene-disease evidence
    require_disease_association: bool = True
    min_association_score: float = 0.3

    # Inheritance pattern matching
    check_inheritance: bool = True
    require_segregation: bool = False


class GeneticAgent(DiagnosticAgent):
    """
    Agent specialized in genetic evidence analysis.

    Capabilities:
    - Variant pathogenicity assessment
    - Gene-disease association lookup
    - Inheritance pattern matching
    - Compound heterozygosity detection
    - Genetic evidence scoring
    """

    def __init__(
        self,
        config: GeneticAgentConfig | None = None,
        genetic_service: Any = None,
        variant_annotator: Any = None,
        primekg_overlay: Any = None,
        neo4j_client: Any = None,
    ) -> None:
        """
        Initialize the genetic agent.

        Args:
            config: Agent configuration
            genetic_service: Genetic association service
            variant_annotator: Variant annotation service
            primekg_overlay: PrimeKG overlay
            neo4j_client: Neo4j client
        """
        super().__init__(
            role=AgentRole.GENETIC_EXPERT,
            config=config or GeneticAgentConfig(),
        )
        self.config: GeneticAgentConfig = self.config

        self._genetic = genetic_service
        self._annotator = variant_annotator
        self._primekg = primekg_overlay
        self._neo4j = neo4j_client

        # Analysis cache
        self._gene_cache: dict[str, dict[str, Any]] = {}
        self._variant_cache: dict[str, dict[str, Any]] = {}

    async def analyze(
        self,
        patient_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze genetic evidence.

        Performs:
        1. Variant classification
        2. Gene-disease association lookup
        3. Inheritance pattern assessment
        4. Compound heterozygosity check

        Args:
            patient_data: Patient information with genetic data
            context: Additional context

        Returns:
            Genetic analysis results
        """
        variants = patient_data.get("genetic_variants", [])
        family_history = patient_data.get("family_history", [])

        if not variants:
            return {
                "has_genetic_data": False,
                "variants_analyzed": 0,
                "message": "No genetic variants provided",
            }

        # Classify variants
        classified = await self._classify_variants(variants)

        # Get unique genes
        genes = list({v.get("gene_symbol") for v in variants if v.get("gene_symbol")})

        # Get gene-disease associations
        gene_associations = {}
        for gene in genes:
            associations = await self._get_gene_associations(gene)
            if associations:
                gene_associations[gene] = associations

        # Check for compound heterozygosity
        compound_het = self._check_compound_heterozygosity(classified, gene_associations)

        # Infer inheritance patterns
        inheritance_notes = self._analyze_inheritance(classified, family_history)

        # Identify candidate genes
        candidate_genes = self._identify_candidate_genes(classified, gene_associations)

        profile = {
            "has_genetic_data": True,
            "variants_analyzed": len(variants),
            "variants": classified,
            "pathogenic_count": sum(1 for v in classified if v.get("is_pathogenic")),
            "vous_count": sum(1 for v in classified if v.get("is_vous")),
            "genes_affected": genes,
            "gene_associations": gene_associations,
            "compound_heterozygosity": compound_het,
            "inheritance_notes": inheritance_notes,
            "candidate_genes": candidate_genes,
        }

        logger.info(
            "genetic_analysis_complete",
            agent_id=self.agent_id,
            variants=len(variants),
            pathogenic=profile["pathogenic_count"],
            genes=len(genes),
        )

        return profile

    async def generate_hypotheses(
        self,
        evidence: list[dict[str, Any]],
        existing_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate disease hypotheses from genetic evidence.

        Args:
            evidence: Genetic evidence items
            existing_hypotheses: Current hypotheses

        Returns:
            List of gene-based hypotheses
        """
        hypotheses = []

        # Extract variants
        variants = [e for e in evidence if e.get("evidence_type") == "genetic"]

        if not variants:
            return existing_hypotheses or []

        # Get pathogenic/likely pathogenic variants
        significant_variants = [
            v for v in variants
            if "pathogenic" in str(v.get("severity", "")).lower()
            or v.get("is_pathogenic")
        ]

        # Get genes
        genes = list({v.get("code") or v.get("gene_symbol") for v in significant_variants if v.get("code") or v.get("gene_symbol")})

        if not genes or not self._neo4j:
            return existing_hypotheses or []

        # Query diseases for these genes
        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE g.symbol IN $genes
        OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WITH d, g, r, collect(DISTINCT p.hpo_id) as phenotypes
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               g.symbol as gene_symbol,
               r.score as association_score,
               phenotypes,
               d.inheritance as inheritance
        ORDER BY r.score DESC
        LIMIT $limit
        """

        try:
            results = await self._neo4j.run(query, {
                "genes": genes,
                "limit": self.config.max_hypotheses,
            })

            for r in (results or []):
                gene = r["gene_symbol"]
                # Find variant for this gene
                gene_variants = [
                    v for v in significant_variants
                    if (v.get("code") or v.get("gene_symbol")) == gene
                ]

                hypothesis = {
                    "disease_id": r["disease_id"],
                    "disease_name": r["disease_name"],
                    "supporting_gene": gene,
                    "supporting_variants": [
                        v.get("value") or v.get("notation") for v in gene_variants
                    ],
                    "association_score": r.get("association_score") or 0.5,
                    "expected_phenotypes": r.get("phenotypes", []),
                    "inheritance": r.get("inheritance"),
                    "genetic_score": self._calculate_genetic_score(gene_variants),
                    "source": "genetic_agent",
                }
                hypotheses.append(hypothesis)

        except Exception as e:
            logger.error("genetic_hypothesis_query_failed", error=str(e))

        # Merge with existing
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
        Evaluate a hypothesis from a genetic perspective.

        Args:
            hypothesis: Hypothesis to evaluate
            evidence: Evidence items

        Returns:
            Genetic evaluation
        """
        disease_id = hypothesis.get("disease_id")
        if not disease_id:
            return {"score": 0.5, "reasoning": "No disease ID"}

        # Get genetic variants from evidence
        variants = [e for e in evidence if e.get("evidence_type") == "genetic"]

        if not variants:
            return {
                "score": 0.5,
                "reasoning": "No genetic evidence available",
                "has_genetic_data": False,
            }

        # Get genes associated with the disease
        disease_genes = await self._get_disease_genes(disease_id)

        if not disease_genes:
            return {
                "score": 0.5,
                "reasoning": "No known genes for this disease",
                "disease_genes": [],
            }

        # Check for variants in disease genes
        matching_variants = []
        for v in variants:
            gene = v.get("code") or v.get("gene_symbol")
            if gene and gene in disease_genes:
                matching_variants.append(v)

        if not matching_variants:
            return {
                "score": 0.3,
                "reasoning": f"No variants found in disease-associated genes ({', '.join(disease_genes[:5])})",
                "disease_genes": disease_genes[:10],
                "has_matching_variants": False,
            }

        # Score based on pathogenicity
        genetic_score = self._calculate_genetic_score(matching_variants)

        # Build reasoning
        reasoning_parts = []
        pathogenic_count = sum(
            1 for v in matching_variants
            if "pathogenic" in str(v.get("severity", "")).lower()
        )

        if pathogenic_count:
            reasoning_parts.append(
                f"Found {pathogenic_count} pathogenic variant(s) in disease-associated genes"
            )
        else:
            reasoning_parts.append(
                f"Found {len(matching_variants)} variant(s) of uncertain significance in disease genes"
            )

        return {
            "score": genetic_score,
            "reasoning": ". ".join(reasoning_parts),
            "disease_genes": disease_genes[:10],
            "matching_variants": [
                {
                    "gene": v.get("code") or v.get("gene_symbol"),
                    "variant": v.get("value") or v.get("notation"),
                    "pathogenicity": v.get("severity"),
                }
                for v in matching_variants
            ],
            "has_matching_variants": True,
            "pathogenic_count": pathogenic_count,
        }

    async def _classify_variants(
        self,
        variants: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Classify variants by pathogenicity."""
        classified = []

        for v in variants:
            variant_data = dict(v)

            # Determine pathogenicity
            severity = str(v.get("severity", "") or v.get("pathogenicity", "")).lower()

            if "pathogenic" in severity and "likely" not in severity:
                variant_data["pathogenicity_class"] = "pathogenic"
                variant_data["is_pathogenic"] = True
                variant_data["likelihood_ratio"] = self.config.pathogenic_lr
            elif "likely_pathogenic" in severity or "likely pathogenic" in severity:
                variant_data["pathogenicity_class"] = "likely_pathogenic"
                variant_data["is_pathogenic"] = True
                variant_data["likelihood_ratio"] = self.config.likely_pathogenic_lr
            elif "benign" in severity and "likely" not in severity:
                variant_data["pathogenicity_class"] = "benign"
                variant_data["is_pathogenic"] = False
                variant_data["likelihood_ratio"] = self.config.benign_lr
            elif "likely_benign" in severity or "likely benign" in severity:
                variant_data["pathogenicity_class"] = "likely_benign"
                variant_data["is_pathogenic"] = False
                variant_data["likelihood_ratio"] = self.config.likely_benign_lr
            else:
                variant_data["pathogenicity_class"] = "vous"
                variant_data["is_pathogenic"] = False
                variant_data["is_vous"] = True
                variant_data["likelihood_ratio"] = self.config.vous_lr

            classified.append(variant_data)

        return classified

    async def _get_gene_associations(
        self,
        gene_symbol: str,
    ) -> list[dict[str, Any]]:
        """Get disease associations for a gene."""
        cache_key = f"gene_assoc_{gene_symbol}"
        if cache_key in self._gene_cache:
            cached: list[dict[str, Any]] = self._gene_cache[cache_key].get("associations", [])
            return cached

        if not self._neo4j:
            return []

        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE g.symbol = $gene
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               r.score as score,
               r.inheritance as inheritance
        ORDER BY r.score DESC
        LIMIT 20
        """

        try:
            results = await self._neo4j.run(query, {"gene": gene_symbol})
            associations = [
                {
                    "disease_id": r["disease_id"],
                    "disease_name": r["disease_name"],
                    "score": r.get("score") or 0.5,
                    "inheritance": r.get("inheritance"),
                }
                for r in (results or [])
            ]
            self._gene_cache[cache_key] = {"associations": associations}
            return associations
        except Exception:
            return []

    async def _get_disease_genes(
        self,
        disease_id: str,
    ) -> list[str]:
        """Get genes associated with a disease."""
        cache_key = f"disease_genes_{disease_id}"
        if cache_key in self._gene_cache:
            cached_genes: list[str] = self._gene_cache[cache_key].get("genes", [])
            return cached_genes

        if not self._neo4j:
            return []

        query = """
        MATCH (g:PrimeKGGene)-[:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE d.mondo_id = $disease_id
        RETURN g.symbol as gene_symbol
        """

        try:
            results = await self._neo4j.run(query, {"disease_id": disease_id})
            genes = [r["gene_symbol"] for r in (results or []) if r.get("gene_symbol")]
            self._gene_cache[cache_key] = {"genes": genes}
            return genes
        except Exception:
            return []

    def _check_compound_heterozygosity(
        self,
        variants: list[dict[str, Any]],
        gene_associations: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Check for potential compound heterozygosity."""
        compound_het = []

        # Group variants by gene
        by_gene: dict[str, list[dict[str, Any]]] = {}
        for v in variants:
            gene = v.get("code") or v.get("gene_symbol") or v.get("gene")
            if gene:
                if gene not in by_gene:
                    by_gene[gene] = []
                by_gene[gene].append(v)

        # Check genes with multiple variants
        for gene, gene_variants in by_gene.items():
            if len(gene_variants) >= 2:
                # Check if gene is associated with recessive disease
                associations = gene_associations.get(gene, [])
                recessive_diseases = [
                    a for a in associations
                    if a.get("inheritance") and "recessive" in str(a["inheritance"]).lower()
                ]

                if recessive_diseases:
                    compound_het.append({
                        "gene": gene,
                        "variant_count": len(gene_variants),
                        "variants": [
                            v.get("value") or v.get("notation") for v in gene_variants
                        ],
                        "potential_diseases": [d["disease_name"] for d in recessive_diseases[:3]],
                    })

        return compound_het

    def _analyze_inheritance(
        self,
        variants: list[dict[str, Any]],
        family_history: list[dict[str, Any]],
    ) -> list[str]:
        """Analyze inheritance patterns."""
        notes = []

        # Check zygosity
        homozygous = [v for v in variants if v.get("zygosity") == "homozygous"]
        if homozygous:
            notes.append(f"Found {len(homozygous)} homozygous variant(s) - consider recessive conditions")

        # Check family history
        if family_history:
            notes.append("Family history present - inheritance pattern analysis may help")

        # De novo consideration
        pathogenic = [v for v in variants if v.get("is_pathogenic")]
        if pathogenic and not family_history:
            notes.append("Consider de novo variants if parents unaffected")

        return notes

    def _identify_candidate_genes(
        self,
        variants: list[dict[str, Any]],
        gene_associations: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Identify candidate genes for disease."""
        candidates = []

        for v in variants:
            gene = v.get("code") or v.get("gene_symbol") or v.get("gene")
            if not gene:
                continue

            associations = gene_associations.get(gene, [])
            if associations and (v.get("is_pathogenic") or v.get("is_vous")):
                candidates.append({
                    "gene": gene,
                    "variant": v.get("value") or v.get("notation"),
                    "pathogenicity": v.get("pathogenicity_class", "unknown"),
                    "disease_associations": len(associations),
                    "top_diseases": [a["disease_name"] for a in associations[:3]],
                })

        # Sort by pathogenicity and association count
        candidates.sort(
            key=lambda x: (
                x["pathogenicity"] in ["pathogenic", "likely_pathogenic"],
                x["disease_associations"],
            ),
            reverse=True,
        )

        return candidates[:10]

    def _calculate_genetic_score(
        self,
        variants: list[dict[str, Any]],
    ) -> float:
        """Calculate combined genetic score from variants."""
        if not variants:
            return 0.5

        # Use product of likelihood ratios, capped
        combined_lr = 1.0
        for v in variants:
            lr = v.get("likelihood_ratio", 1.0)
            combined_lr *= lr

        # Convert LR to probability-like score
        # LR of 100 -> ~0.99, LR of 0.1 -> ~0.09
        if combined_lr <= 0:
            return 0.0
        log_lr = math.log(combined_lr)
        score = 1.0 / (1.0 + math.exp(-log_lr / 3))

        return min(0.99, max(0.01, score))


# =============================================================================
# Factory Function
# =============================================================================

def create_genetic_agent(
    config: GeneticAgentConfig | None = None,
    genetic_service: Any = None,
    variant_annotator: Any = None,
    primekg_overlay: Any = None,
    neo4j_client: Any = None,
) -> GeneticAgent:
    """Create a genetic agent instance."""
    return GeneticAgent(
        config=config,
        genetic_service=genetic_service,
        variant_annotator=variant_annotator,
        primekg_overlay=primekg_overlay,
        neo4j_client=neo4j_client,
    )
