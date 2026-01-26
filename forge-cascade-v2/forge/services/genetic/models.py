"""
Genetic Data Models

Models for genetic variants, genes, and disease associations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VariantType(str, Enum):
    """Type of genetic variant."""

    SNV = "snv"  # Single Nucleotide Variant
    INSERTION = "insertion"
    DELETION = "deletion"
    INDEL = "indel"  # Insertion/Deletion
    CNV = "cnv"  # Copy Number Variant
    SV = "sv"  # Structural Variant
    TRANSLOCATION = "translocation"
    INVERSION = "inversion"
    DUPLICATION = "duplication"
    UNKNOWN = "unknown"


class VariantPathogenicity(str, Enum):
    """ACMG pathogenicity classification."""

    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    UNCERTAIN_SIGNIFICANCE = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"
    NOT_PROVIDED = "not_provided"


class InheritancePattern(str, Enum):
    """Inheritance pattern for genetic conditions."""

    AUTOSOMAL_DOMINANT = "autosomal_dominant"
    AUTOSOMAL_RECESSIVE = "autosomal_recessive"
    X_LINKED_DOMINANT = "x_linked_dominant"
    X_LINKED_RECESSIVE = "x_linked_recessive"
    Y_LINKED = "y_linked"
    MITOCHONDRIAL = "mitochondrial"
    MULTIFACTORIAL = "multifactorial"
    UNKNOWN = "unknown"


class Zygosity(str, Enum):
    """Zygosity of a variant."""

    HOMOZYGOUS = "homozygous"
    HETEROZYGOUS = "heterozygous"
    HEMIZYGOUS = "hemizygous"
    COMPOUND_HETEROZYGOUS = "compound_heterozygous"
    UNKNOWN = "unknown"


@dataclass
class GeneticVariant:
    """
    A genetic variant identified in sequencing data.

    Follows VCF format conventions.
    """

    # Core identifiers
    chromosome: str  # e.g., "chr1", "1", "chrX"
    position: int  # 1-based position
    ref_allele: str  # Reference allele
    alt_allele: str  # Alternative allele

    # Optional identifiers
    variant_id: str | None = None  # dbSNP ID (rs...)
    gene_symbol: str | None = None
    gene_id: str | None = None  # Entrez or Ensembl ID
    transcript_id: str | None = None

    # Variant characteristics
    variant_type: VariantType = VariantType.UNKNOWN
    zygosity: Zygosity = Zygosity.UNKNOWN

    # Quality metrics
    quality_score: float | None = None
    read_depth: int | None = None
    allele_frequency: float | None = None  # Population frequency

    # Clinical annotations
    pathogenicity: VariantPathogenicity = VariantPathogenicity.NOT_PROVIDED
    clinvar_id: str | None = None
    hgvs_c: str | None = None  # cDNA notation
    hgvs_p: str | None = None  # Protein notation

    # Functional impact
    consequence: str | None = None  # e.g., "missense_variant", "frameshift"
    impact: str | None = None  # e.g., "HIGH", "MODERATE", "LOW"
    sift_score: float | None = None
    polyphen_score: float | None = None

    @property
    def genomic_position(self) -> str:
        """Get standard genomic position string."""
        return f"{self.chromosome}:{self.position}"

    @property
    def notation(self) -> str:
        """Get variant notation string."""
        return f"{self.chromosome}:{self.position}:{self.ref_allele}>{self.alt_allele}"

    def is_pathogenic_or_likely(self) -> bool:
        """Check if variant is pathogenic or likely pathogenic."""
        return self.pathogenicity in {
            VariantPathogenicity.PATHOGENIC,
            VariantPathogenicity.LIKELY_PATHOGENIC,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "chromosome": self.chromosome,
            "position": self.position,
            "ref_allele": self.ref_allele,
            "alt_allele": self.alt_allele,
            "variant_id": self.variant_id,
            "gene_symbol": self.gene_symbol,
            "variant_type": self.variant_type.value,
            "zygosity": self.zygosity.value,
            "pathogenicity": self.pathogenicity.value,
            "hgvs_c": self.hgvs_c,
            "hgvs_p": self.hgvs_p,
            "consequence": self.consequence,
            "impact": self.impact,
        }


@dataclass
class VariantAnnotation:
    """
    Additional annotations for a genetic variant.

    From databases like ClinVar, OMIM, gnomAD.
    """

    variant: GeneticVariant
    source: str  # e.g., "clinvar", "omim", "gnomad"

    # Clinical significance
    clinical_significance: str | None = None
    review_status: str | None = None
    conditions: list[str] = field(default_factory=list)

    # Population frequencies
    gnomad_af: float | None = None  # gnomAD allele frequency
    gnomad_af_popmax: float | None = None

    # Literature
    pubmed_ids: list[str] = field(default_factory=list)

    # Prediction scores
    cadd_score: float | None = None
    revel_score: float | None = None

    # Timestamps
    last_evaluated: datetime | None = None


@dataclass
class GeneInfo:
    """
    Information about a gene.

    Includes disease associations and functional annotations.
    """

    gene_symbol: str  # e.g., "BRCA1"
    gene_id: str  # Entrez ID
    ensembl_id: str | None = None
    full_name: str | None = None

    # Chromosome location
    chromosome: str | None = None
    start_position: int | None = None
    end_position: int | None = None
    strand: str | None = None

    # Associated diseases
    associated_diseases: list[dict[str, Any]] = field(default_factory=list)
    inheritance_patterns: list[InheritancePattern] = field(default_factory=list)

    # OMIM entries
    omim_id: str | None = None
    omim_phenotypes: list[str] = field(default_factory=list)

    # Functional info
    gene_ontology: list[str] = field(default_factory=list)
    pathways: list[str] = field(default_factory=list)

    # Clinical significance
    is_disease_gene: bool = False
    clinical_actionability: str | None = None  # ClinGen

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gene_symbol": self.gene_symbol,
            "gene_id": self.gene_id,
            "ensembl_id": self.ensembl_id,
            "full_name": self.full_name,
            "chromosome": self.chromosome,
            "associated_diseases": self.associated_diseases,
            "inheritance_patterns": [p.value for p in self.inheritance_patterns],
            "omim_id": self.omim_id,
            "is_disease_gene": self.is_disease_gene,
        }


@dataclass
class GeneticTestResult:
    """
    Complete genetic test result.

    Contains all variants found and overall interpretation.
    """

    test_id: str
    patient_id: str | None = None
    test_type: str = "wes"  # wes, wgs, panel, single_gene

    # Variants found
    variants: list[GeneticVariant] = field(default_factory=list)
    pathogenic_variants: list[GeneticVariant] = field(default_factory=list)
    vous_variants: list[GeneticVariant] = field(default_factory=list)

    # Genes analyzed
    genes_tested: list[str] = field(default_factory=list)
    coverage_metrics: dict[str, float] = field(default_factory=dict)

    # Interpretation
    overall_interpretation: str | None = None
    candidate_diagnoses: list[str] = field(default_factory=list)

    # Metadata
    lab_name: str | None = None
    report_date: datetime | None = None
    platform: str | None = None  # Sequencing platform

    @property
    def total_variants(self) -> int:
        """Get total number of variants."""
        return len(self.variants)

    @property
    def pathogenic_count(self) -> int:
        """Get number of pathogenic/likely pathogenic variants."""
        return len(self.pathogenic_variants)

    def get_affected_genes(self) -> list[str]:
        """Get list of genes with pathogenic variants."""
        genes = set()
        for var in self.pathogenic_variants:
            if var.gene_symbol:
                genes.add(var.gene_symbol)
        return list(genes)


@dataclass
class GeneDiseaseAssociation:
    """
    Association between a gene and a disease.

    From sources like OMIM, ClinGen, DisGeNET.
    """

    gene_symbol: str
    gene_id: str
    disease_id: str  # MONDO, OMIM, or ORPHA ID
    disease_name: str

    # Association details
    inheritance: InheritancePattern = InheritancePattern.UNKNOWN
    evidence_level: str | None = None  # ClinGen: Definitive, Strong, Moderate, Limited
    source: str | None = None

    # Phenotype info
    associated_phenotypes: list[str] = field(default_factory=list)  # HPO IDs

    # Scores
    association_score: float | None = None  # DisGeNET score
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gene_symbol": self.gene_symbol,
            "gene_id": self.gene_id,
            "disease_id": self.disease_id,
            "disease_name": self.disease_name,
            "inheritance": self.inheritance.value,
            "evidence_level": self.evidence_level,
            "source": self.source,
            "associated_phenotypes": self.associated_phenotypes,
            "association_score": self.association_score,
            "confidence": self.confidence,
        }
