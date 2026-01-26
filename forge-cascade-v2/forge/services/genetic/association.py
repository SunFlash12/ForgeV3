"""
Gene Association Service

Provides gene-disease association lookups using PrimeKG and external databases.
"""

from typing import Any

import structlog

from .models import (
    GeneDiseaseAssociation,
    GeneInfo,
    GeneticVariant,
    InheritancePattern,
)

logger = structlog.get_logger(__name__)


class GeneAssociationService:
    """
    Service for gene-disease association lookups.

    Integrates with:
    - PrimeKG for gene-disease relationships
    - OMIM for Mendelian disease associations
    - ClinGen for gene-disease validity
    """

    def __init__(
        self,
        neo4j_client: Any = None,
        primekg_overlay: Any = None,
    ) -> None:
        """
        Initialize the gene association service.

        Args:
            neo4j_client: Neo4j database client
            primekg_overlay: PrimeKG overlay for queries
        """
        self._neo4j = neo4j_client
        self._primekg = primekg_overlay

        # Cache for gene info
        self._gene_cache: dict[str, GeneInfo] = {}
        self._association_cache: dict[str, list[GeneDiseaseAssociation]] = {}

    async def get_gene_info(self, gene_symbol: str) -> GeneInfo | None:
        """
        Get information about a gene.

        Args:
            gene_symbol: Gene symbol (e.g., "BRCA1")

        Returns:
            GeneInfo or None if not found
        """
        # Check cache
        if gene_symbol in self._gene_cache:
            return self._gene_cache[gene_symbol]

        if not self._neo4j:
            return None

        # Query PrimeKG for gene info
        query = """
        MATCH (g:PrimeKGGene)
        WHERE g.symbol = $symbol OR g.name CONTAINS $symbol
        OPTIONAL MATCH (g)-[:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        OPTIONAL MATCH (g)-[:PARTICIPATES_IN|pathway]-(p:PrimeKGPathway)
        WITH g, collect(DISTINCT {
            disease_id: d.mondo_id,
            disease_name: d.name
        }) as diseases,
        collect(DISTINCT p.name) as pathways
        RETURN g.symbol as symbol,
               g.entrez_id as entrez_id,
               g.ensembl_id as ensembl_id,
               g.full_name as full_name,
               g.description as description,
               diseases,
               pathways
        LIMIT 1
        """

        try:
            results = await self._neo4j.run(query, {"symbol": gene_symbol})

            if not results:
                return None

            r = results[0]
            gene_info = GeneInfo(
                gene_symbol=r["symbol"] or gene_symbol,
                gene_id=r["entrez_id"] or "",
                ensembl_id=r.get("ensembl_id"),
                full_name=r.get("full_name"),
                associated_diseases=[
                    d for d in r.get("diseases", [])
                    if d.get("disease_id")
                ],
                pathways=r.get("pathways", []),
                is_disease_gene=len([d for d in r.get("diseases", []) if d.get("disease_id")]) > 0,
            )

            self._gene_cache[gene_symbol] = gene_info
            return gene_info

        except (RuntimeError, ValueError, ConnectionError, OSError) as e:
            logger.error("gene_info_query_failed", gene=gene_symbol, error=str(e))
            return None

    async def get_disease_associations(
        self,
        gene_symbol: str,
        min_confidence: float = 0.0,
    ) -> list[GeneDiseaseAssociation]:
        """
        Get disease associations for a gene.

        Args:
            gene_symbol: Gene symbol
            min_confidence: Minimum confidence score

        Returns:
            List of gene-disease associations
        """
        # Check cache
        cache_key = f"{gene_symbol}_{min_confidence}"
        if cache_key in self._association_cache:
            return self._association_cache[cache_key]

        if not self._neo4j:
            return []

        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE g.symbol = $symbol
        OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WITH g, d, r, collect(DISTINCT p.hpo_id) as phenotypes
        RETURN g.symbol as gene_symbol,
               g.entrez_id as gene_id,
               d.mondo_id as disease_id,
               d.name as disease_name,
               phenotypes,
               r.score as score,
               r.source as source
        """

        try:
            results = await self._neo4j.run(query, {"symbol": gene_symbol})

            associations = []
            for r in results:
                score = r.get("score") or 0.5
                if score >= min_confidence:
                    associations.append(GeneDiseaseAssociation(
                        gene_symbol=r["gene_symbol"],
                        gene_id=r["gene_id"] or "",
                        disease_id=r["disease_id"] or "",
                        disease_name=r["disease_name"] or "",
                        associated_phenotypes=r.get("phenotypes", []),
                        association_score=score,
                        source=r.get("source"),
                        confidence=score,
                    ))

            # Sort by confidence
            associations.sort(key=lambda a: a.confidence, reverse=True)

            self._association_cache[cache_key] = associations
            return associations

        except (RuntimeError, ValueError, ConnectionError, OSError) as e:
            logger.error("disease_association_query_failed", gene=gene_symbol, error=str(e))
            return []

    async def get_genes_for_disease(
        self,
        disease_id: str,
        limit: int = 50,
    ) -> list[GeneDiseaseAssociation]:
        """
        Get genes associated with a disease.

        Args:
            disease_id: MONDO disease ID
            limit: Maximum genes to return

        Returns:
            List of gene-disease associations
        """
        if not self._neo4j:
            return []

        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE d.mondo_id = $disease_id OR d.node_id = $disease_id
        RETURN g.symbol as gene_symbol,
               g.entrez_id as gene_id,
               d.mondo_id as disease_id,
               d.name as disease_name,
               r.score as score,
               r.source as source
        ORDER BY r.score DESC
        LIMIT $limit
        """

        try:
            results = await self._neo4j.run(query, {
                "disease_id": disease_id,
                "limit": limit,
            })

            return [
                GeneDiseaseAssociation(
                    gene_symbol=r["gene_symbol"],
                    gene_id=r["gene_id"] or "",
                    disease_id=r["disease_id"] or disease_id,
                    disease_name=r["disease_name"] or "",
                    association_score=r.get("score") or 0.5,
                    source=r.get("source"),
                    confidence=r.get("score") or 0.5,
                )
                for r in results
            ]

        except (RuntimeError, ValueError, ConnectionError, OSError) as e:
            logger.error("genes_for_disease_query_failed", disease=disease_id, error=str(e))
            return []

    async def find_diseases_by_variants(
        self,
        variants: list[GeneticVariant],
        require_pathogenic: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Find diseases potentially caused by the given variants.

        Args:
            variants: List of genetic variants
            require_pathogenic: Only consider pathogenic/likely pathogenic variants

        Returns:
            List of disease candidates with supporting evidence
        """
        # Filter variants
        if require_pathogenic:
            variants = [v for v in variants if v.is_pathogenic_or_likely()]

        # Get unique genes
        genes = list({v.gene_symbol for v in variants if v.gene_symbol})

        if not genes:
            return []

        disease_evidence: dict[str, dict[str, Any]] = {}

        # Get associations for each gene
        for gene in genes:
            associations = await self.get_disease_associations(gene)

            for assoc in associations:
                disease_id = assoc.disease_id
                if disease_id not in disease_evidence:
                    disease_evidence[disease_id] = {
                        "disease_id": disease_id,
                        "disease_name": assoc.disease_name,
                        "supporting_genes": [],
                        "supporting_variants": [],
                        "phenotypes": set(),
                        "total_score": 0.0,
                    }

                disease_evidence[disease_id]["supporting_genes"].append(gene)
                disease_evidence[disease_id]["total_score"] += assoc.confidence

                # Add supporting variants
                gene_variants = [v for v in variants if v.gene_symbol == gene]
                for var in gene_variants:
                    disease_evidence[disease_id]["supporting_variants"].append({
                        "variant": var.notation,
                        "gene": var.gene_symbol,
                        "pathogenicity": var.pathogenicity.value,
                    })

                # Add phenotypes
                disease_evidence[disease_id]["phenotypes"].update(assoc.associated_phenotypes)

        # Convert to list and sort by score
        results = []
        for _disease_id, evidence in disease_evidence.items():
            evidence["phenotypes"] = list(evidence["phenotypes"])
            evidence["gene_count"] = len(evidence["supporting_genes"])
            evidence["variant_count"] = len(evidence["supporting_variants"])
            results.append(evidence)

        results.sort(key=lambda x: x["total_score"], reverse=True)
        return results

    async def get_inheritance_pattern(
        self,
        gene_symbol: str,
        disease_id: str | None = None,
    ) -> InheritancePattern:
        """
        Get inheritance pattern for a gene-disease relationship.

        Args:
            gene_symbol: Gene symbol
            disease_id: Optional specific disease

        Returns:
            Inheritance pattern
        """
        if not self._neo4j:
            return InheritancePattern.UNKNOWN

        # Query OMIM or other sources for inheritance pattern
        # This is simplified - real implementation would query OMIM API
        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH]-(d:PrimeKGDisease)
        WHERE g.symbol = $symbol
        AND ($disease_id IS NULL OR d.mondo_id = $disease_id)
        RETURN r.inheritance as inheritance
        LIMIT 1
        """

        try:
            results = await self._neo4j.run(query, {
                "symbol": gene_symbol,
                "disease_id": disease_id,
            })

            if results:
                inheritance = results[0].get("inheritance", "").lower()
                if "dominant" in inheritance:
                    if "x" in inheritance:
                        return InheritancePattern.X_LINKED_DOMINANT
                    return InheritancePattern.AUTOSOMAL_DOMINANT
                elif "recessive" in inheritance:
                    if "x" in inheritance:
                        return InheritancePattern.X_LINKED_RECESSIVE
                    return InheritancePattern.AUTOSOMAL_RECESSIVE

        except (RuntimeError, ValueError, ConnectionError, OSError) as e:
            logger.warning("inheritance_query_failed", gene=gene_symbol, error=str(e))

        return InheritancePattern.UNKNOWN

    async def check_variant_gene_disease_link(
        self,
        variant: GeneticVariant,
        disease_id: str,
    ) -> dict[str, Any]:
        """
        Check if a variant's gene is associated with a specific disease.

        Args:
            variant: Genetic variant
            disease_id: MONDO disease ID

        Returns:
            Link information with confidence
        """
        if not variant.gene_symbol:
            return {"linked": False, "reason": "No gene symbol"}

        associations = await self.get_disease_associations(variant.gene_symbol)

        for assoc in associations:
            if assoc.disease_id == disease_id:
                return {
                    "linked": True,
                    "gene_symbol": variant.gene_symbol,
                    "disease_id": disease_id,
                    "disease_name": assoc.disease_name,
                    "association_score": assoc.association_score,
                    "inheritance": assoc.inheritance.value,
                    "evidence_level": assoc.evidence_level,
                }

        return {
            "linked": False,
            "gene_symbol": variant.gene_symbol,
            "disease_id": disease_id,
            "reason": "No association found",
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_gene_association_service(
    neo4j_client: Any = None,
    primekg_overlay: Any = None,
) -> GeneAssociationService:
    """Create a gene association service instance."""
    return GeneAssociationService(
        neo4j_client=neo4j_client,
        primekg_overlay=primekg_overlay,
    )
