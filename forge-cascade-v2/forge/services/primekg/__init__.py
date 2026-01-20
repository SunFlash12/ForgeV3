"""
PrimeKG Integration Services

This module provides services for integrating the Precision Medicine
Knowledge Graph (PrimeKG) into Forge V3.

Components:
- download: Data download from Harvard Dataverse
- parser: CSV parsing for nodes and edges
- import_service: Neo4j batch import
- embedding_service: Clinical description embeddings
- query_service: PrimeKG-specific queries

PrimeKG Statistics:
- 129,375 nodes across 10 types
- 4,050,249 edges across 30 relationship types
- 17,080+ diseases with HPO phenotype mappings
- 20 integrated biomedical data sources
"""

from .download import PrimeKGDownloader, PrimeKGDataFiles
from .parser import PrimeKGParser, PrimeKGNode, PrimeKGEdge
from .import_service import PrimeKGImportService, ImportProgress, ImportResult
from .models import (
    PrimeKGNodeType,
    PrimeKGEdgeType,
    PrimeKGDisease,
    PrimeKGGene,
    PrimeKGDrug,
    PrimeKGPhenotype,
)

__all__ = [
    # Download
    "PrimeKGDownloader",
    "PrimeKGDataFiles",
    # Parser
    "PrimeKGParser",
    "PrimeKGNode",
    "PrimeKGEdge",
    # Import
    "PrimeKGImportService",
    "ImportProgress",
    "ImportResult",
    # Models
    "PrimeKGNodeType",
    "PrimeKGEdgeType",
    "PrimeKGDisease",
    "PrimeKGGene",
    "PrimeKGDrug",
    "PrimeKGPhenotype",
]
