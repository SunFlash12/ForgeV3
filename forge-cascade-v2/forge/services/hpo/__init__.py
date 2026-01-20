"""
HPO (Human Phenotype Ontology) Service Module

Provides phenotype processing for the differential diagnosis engine:
- HPO ontology parsing and hierarchy management
- Natural language phenotype extraction
- Phenotype normalization and mapping
- Semantic similarity between phenotypes
"""

from .models import (
    HPOTerm,
    HPOAnnotation,
    PhenotypeMatch,
    PhenotypeSeverity,
    PhenotypeOccurrence,
    ExtractedPhenotype,
)
from .ontology import HPOOntologyService, create_hpo_ontology_service
from .extractor import PhenotypeExtractor, create_phenotype_extractor
from .normalizer import PhenotypeNormalizer, create_phenotype_normalizer

__all__ = [
    # Models
    "HPOTerm",
    "HPOAnnotation",
    "PhenotypeMatch",
    "PhenotypeSeverity",
    "PhenotypeOccurrence",
    "ExtractedPhenotype",
    # Ontology Service
    "HPOOntologyService",
    "create_hpo_ontology_service",
    # Extractor
    "PhenotypeExtractor",
    "create_phenotype_extractor",
    # Normalizer
    "PhenotypeNormalizer",
    "create_phenotype_normalizer",
]
