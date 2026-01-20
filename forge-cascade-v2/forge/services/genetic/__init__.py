"""
Genetic Data Handling Module

Provides genetic data processing for the differential diagnosis engine:
- VCF file parsing and variant extraction
- Gene-disease association lookups
- Variant pathogenicity assessment
- ClinVar and OMIM integration
"""

from .models import (
    GeneticVariant,
    VariantType,
    VariantPathogenicity,
    VariantAnnotation,
    GeneInfo,
    GeneticTestResult,
)
from .parser import VCFParser, create_vcf_parser
from .association import GeneAssociationService, create_gene_association_service
from .annotator import VariantAnnotator, create_variant_annotator

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
