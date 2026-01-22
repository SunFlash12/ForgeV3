"""
Genetic Data Handling Module

Provides genetic data processing for the differential diagnosis engine:
- VCF file parsing and variant extraction
- Gene-disease association lookups
- Variant pathogenicity assessment
- ClinVar and OMIM integration
"""

from .annotator import VariantAnnotator, create_variant_annotator
from .association import GeneAssociationService, create_gene_association_service
from .models import (
    GeneInfo,
    GeneticTestResult,
    GeneticVariant,
    VariantAnnotation,
    VariantPathogenicity,
    VariantType,
)
from .parser import VCFParser, create_vcf_parser

__all__ = [
    # Models
    "GeneticVariant",
    "VariantType",
    "VariantPathogenicity",
    "VariantAnnotation",
    "GeneInfo",
    "GeneticTestResult",
    # Parser
    "VCFParser",
    "create_vcf_parser",
    # Association
    "GeneAssociationService",
    "create_gene_association_service",
    # Annotator
    "VariantAnnotator",
    "create_variant_annotator",
]
