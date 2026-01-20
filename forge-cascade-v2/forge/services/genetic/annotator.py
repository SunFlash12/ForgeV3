"""
Variant Annotator Service

Annotates genetic variants with clinical significance, population frequencies,
and functional predictions.
"""

from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from .models import (
    GeneticVariant,
    VariantAnnotation,
    VariantPathogenicity,
)

logger = structlog.get_logger(__name__)


@dataclass
class AnnotationConfig:
    """Configuration for variant annotation."""
    use_clinvar: bool = True
    use_gnomad: bool = True
    use_ensembl_vep: bool = False
    clinvar_api_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    gnomad_api_url: str = "https://gnomad.broadinstitute.org/api"
    vep_api_url: str = "https://rest.ensembl.org"
    cache_results: bool = True
    timeout: float = 30.0


class VariantAnnotator:
    """
    Service for annotating genetic variants.

    Integrates with:
    - ClinVar for clinical significance
    - gnomAD for population frequencies
    - Ensembl VEP for functional predictions
    """

    def __init__(
        self,
        config: AnnotationConfig | None = None,
    ):
        """
        Initialize the variant annotator.

        Args:
            config: Annotation configuration
        """
        self.config = config or AnnotationConfig()

        # Annotation cache
        self._cache: dict[str, VariantAnnotation] = {}

    async def annotate(
        self,
        variant: GeneticVariant,
    ) -> VariantAnnotation:
        """
        Annotate a single variant.

        Args:
            variant: Genetic variant to annotate

        Returns:
            VariantAnnotation with all available annotations
        """
        cache_key = variant.notation

        # Check cache
        if self.config.cache_results and cache_key in self._cache:
            return self._cache[cache_key]

        annotation = VariantAnnotation(
            variant=variant,
            source="combined",
        )

        # Query ClinVar
        if self.config.use_clinvar:
            clinvar_data = await self._query_clinvar(variant)
            if clinvar_data:
                annotation.clinical_significance = clinvar_data.get("clinical_significance")
                annotation.review_status = clinvar_data.get("review_status")
                annotation.conditions = clinvar_data.get("conditions", [])
                annotation.pubmed_ids = clinvar_data.get("pubmed_ids", [])

        # Query gnomAD
        if self.config.use_gnomad:
            gnomad_data = await self._query_gnomad(variant)
            if gnomad_data:
                annotation.gnomad_af = gnomad_data.get("af")
                annotation.gnomad_af_popmax = gnomad_data.get("af_popmax")

        # Query VEP
        if self.config.use_ensembl_vep:
            vep_data = await self._query_vep(variant)
            if vep_data:
                annotation.cadd_score = vep_data.get("cadd_phred")
                if not variant.consequence:
                    variant.consequence = vep_data.get("consequence")
                if not variant.impact:
                    variant.impact = vep_data.get("impact")

        # Cache result
        if self.config.cache_results:
            self._cache[cache_key] = annotation

        return annotation

    async def annotate_batch(
        self,
        variants: list[GeneticVariant],
    ) -> list[VariantAnnotation]:
        """
        Annotate multiple variants.

        Args:
            variants: List of variants to annotate

        Returns:
            List of annotations
        """
        annotations = []
        for variant in variants:
            annotation = await self.annotate(variant)
            annotations.append(annotation)
        return annotations

    async def _query_clinvar(
        self,
        variant: GeneticVariant,
    ) -> dict[str, Any] | None:
        """Query ClinVar for clinical significance."""
        if variant.clinvar_id:
            # Use ClinVar ID if available
            search_term = variant.clinvar_id
        elif variant.variant_id and variant.variant_id.startswith("rs"):
            # Use dbSNP rsID
            search_term = variant.variant_id
        else:
            # Use genomic coordinates
            search_term = f"{variant.chromosome}[CHR] AND {variant.position}[POS]"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                # Search for variant
                search_url = f"{self.config.clinvar_api_url}/esearch.fcgi"
                search_params = {
                    "db": "clinvar",
                    "term": search_term,
                    "retmode": "json",
                }
                response = await client.get(search_url, params=search_params)

                if response.status_code != 200:
                    return None

                data = response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])

                if not id_list:
                    return None

                # Fetch details
                fetch_url = f"{self.config.clinvar_api_url}/esummary.fcgi"
                fetch_params = {
                    "db": "clinvar",
                    "id": ",".join(id_list[:5]),  # Limit to first 5
                    "retmode": "json",
                }
                response = await client.get(fetch_url, params=fetch_params)

                if response.status_code != 200:
                    return None

                summary = response.json()
                results = summary.get("result", {})

                # Parse first result
                for uid in id_list[:1]:
                    record = results.get(uid, {})
                    if record:
                        return {
                            "clinical_significance": record.get("clinical_significance", {}).get("description"),
                            "review_status": record.get("clinical_significance", {}).get("review_status"),
                            "conditions": [
                                t.get("trait_name") for t in record.get("trait_set", [])
                                if t.get("trait_name")
                            ],
                            "pubmed_ids": record.get("supporting_submissions", {}).get("pmids", []),
                        }

        except Exception as e:
            logger.warning("clinvar_query_failed", variant=variant.notation, error=str(e))

        return None

    async def _query_gnomad(
        self,
        variant: GeneticVariant,
    ) -> dict[str, Any] | None:
        """Query gnomAD for population frequencies."""
        # Note: gnomAD GraphQL API requires special handling
        # This is a simplified implementation

        # Normalize chromosome
        chrom = variant.chromosome.replace("chr", "")

        # Build GraphQL query
        query = """
        query gnomad_variant($dataset: DatasetId!, $variantId: String!) {
            variant(dataset: $dataset, variantId: $variantId) {
                variant_id
                genome {
                    af
                    af_popmax
                    populations {
                        id
                        af
                    }
                }
            }
        }
        """

        variant_id = f"{chrom}-{variant.position}-{variant.ref_allele}-{variant.alt_allele}"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    self.config.gnomad_api_url,
                    json={
                        "query": query,
                        "variables": {
                            "dataset": "gnomad_r3",
                            "variantId": variant_id,
                        },
                    },
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                variant_data = data.get("data", {}).get("variant")

                if not variant_data:
                    return None

                genome = variant_data.get("genome", {})
                return {
                    "af": genome.get("af"),
                    "af_popmax": genome.get("af_popmax"),
                }

        except Exception as e:
            logger.debug("gnomad_query_failed", variant=variant.notation, error=str(e))

        return None

    async def _query_vep(
        self,
        variant: GeneticVariant,
    ) -> dict[str, Any] | None:
        """Query Ensembl VEP for functional predictions."""
        # Normalize chromosome
        chrom = variant.chromosome.replace("chr", "")

        # Build VEP notation: chr:pos:ref/alt
        vep_notation = f"{chrom}:{variant.position}:{variant.ref_allele}/{variant.alt_allele}"

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                url = f"{self.config.vep_api_url}/vep/human/hgvs/{vep_notation}"
                headers = {"Content-Type": "application/json"}

                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return None

                data = response.json()
                if not data or not isinstance(data, list):
                    return None

                result = data[0]
                transcript_consequences = result.get("transcript_consequences", [])

                if not transcript_consequences:
                    return None

                # Get most severe consequence
                tc = transcript_consequences[0]

                return {
                    "consequence": tc.get("consequence_terms", [None])[0],
                    "impact": tc.get("impact"),
                    "gene_symbol": tc.get("gene_symbol"),
                    "cadd_phred": tc.get("cadd_phred"),
                    "sift_prediction": tc.get("sift_prediction"),
                    "polyphen_prediction": tc.get("polyphen_prediction"),
                }

        except Exception as e:
            logger.debug("vep_query_failed", variant=variant.notation, error=str(e))

        return None

    def assess_pathogenicity(
        self,
        variant: GeneticVariant,
        annotation: VariantAnnotation,
    ) -> VariantPathogenicity:
        """
        Assess pathogenicity using ACMG-like criteria.

        Considers:
        - ClinVar classification
        - Population frequency (gnomAD)
        - Functional impact (consequence, CADD)
        - Computational predictions (SIFT, PolyPhen)

        Args:
            variant: Genetic variant
            annotation: Variant annotation

        Returns:
            Assessed pathogenicity
        """
        # Start with ClinVar if available
        if annotation.clinical_significance:
            clinsig = annotation.clinical_significance.lower()
            if "pathogenic" in clinsig:
                if "likely" in clinsig:
                    return VariantPathogenicity.LIKELY_PATHOGENIC
                return VariantPathogenicity.PATHOGENIC
            elif "benign" in clinsig:
                if "likely" in clinsig:
                    return VariantPathogenicity.LIKELY_BENIGN
                return VariantPathogenicity.BENIGN

        # Score-based assessment
        pathogenic_evidence = 0
        benign_evidence = 0

        # Population frequency (benign if common)
        if annotation.gnomad_af:
            if annotation.gnomad_af > 0.05:  # >5% = likely benign
                benign_evidence += 2
            elif annotation.gnomad_af > 0.01:  # >1% = evidence for benign
                benign_evidence += 1
            elif annotation.gnomad_af < 0.0001:  # <0.01% = rare
                pathogenic_evidence += 1

        # Functional impact
        high_impact = ["frameshift", "stop_gained", "splice_donor", "splice_acceptor"]
        moderate_impact = ["missense", "inframe_deletion", "inframe_insertion"]

        if variant.consequence:
            consequence_lower = variant.consequence.lower()
            if any(hi in consequence_lower for hi in high_impact):
                pathogenic_evidence += 2
            elif any(mi in consequence_lower for mi in moderate_impact):
                pathogenic_evidence += 1

        # CADD score
        if annotation.cadd_score:
            if annotation.cadd_score >= 25:  # Highly deleterious
                pathogenic_evidence += 2
            elif annotation.cadd_score >= 15:  # Likely deleterious
                pathogenic_evidence += 1

        # Computational predictions
        if variant.sift_score is not None and variant.sift_score < 0.05:
            pathogenic_evidence += 1
        if variant.polyphen_score is not None and variant.polyphen_score > 0.85:
            pathogenic_evidence += 1

        # Make decision
        if benign_evidence >= 3:
            return VariantPathogenicity.BENIGN
        elif benign_evidence >= 2:
            return VariantPathogenicity.LIKELY_BENIGN
        elif pathogenic_evidence >= 4:
            return VariantPathogenicity.PATHOGENIC
        elif pathogenic_evidence >= 2:
            return VariantPathogenicity.LIKELY_PATHOGENIC
        else:
            return VariantPathogenicity.UNCERTAIN_SIGNIFICANCE

    def clear_cache(self) -> None:
        """Clear the annotation cache."""
        self._cache.clear()


# =============================================================================
# Factory Function
# =============================================================================

def create_variant_annotator(
    config: AnnotationConfig | None = None,
) -> VariantAnnotator:
    """Create a variant annotator instance."""
    return VariantAnnotator(config=config)
