"""
PrimeKG Data Models

Defines the data structures for PrimeKG nodes and edges,
aligned with the Precision Medicine Knowledge Graph schema.

Reference: https://github.com/mims-harvard/PrimeKG
Paper: Chandak et al. "Building a knowledge graph to enable precision medicine"
       Scientific Data, 2023
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from forge.models.base import ForgeModel, TimestampMixin


class PrimeKGNodeType(str, Enum):
    """
    PrimeKG node types (10 total).

    Each node type represents a distinct biological/clinical entity class.
    """
    DISEASE = "disease"              # MONDO ontology
    GENE_PROTEIN = "gene/protein"    # Entrez Gene / UniProt
    DRUG = "drug"                    # DrugBank
    PHENOTYPE = "effect/phenotype"   # HPO / SIDER
    ANATOMY = "anatomy"              # UBERON
    PATHWAY = "pathway"              # Reactome
    BIOLOGICAL_PROCESS = "biological_process"  # GO:BP
    MOLECULAR_FUNCTION = "molecular_function"  # GO:MF
    CELLULAR_COMPONENT = "cellular_component"  # GO:CC
    EXPOSURE = "exposure"            # Environmental/clinical


class PrimeKGEdgeType(str, Enum):
    """
    PrimeKG edge types (30 total).

    Represents relationships between nodes in the knowledge graph.
    """
    # Drug-Disease relationships
    INDICATION = "indication"
    CONTRAINDICATION = "contraindication"
    OFF_LABEL_USE = "off-label use"

    # Drug-Gene relationships
    DRUG_TARGET = "target"
    DRUG_ENZYME = "enzyme"
    DRUG_CARRIER = "carrier"
    DRUG_TRANSPORTER = "transporter"

    # Gene-Disease relationships
    GENE_ASSOCIATED_WITH_DISEASE = "associated with"

    # Disease-Phenotype relationships
    DISEASE_PHENOTYPE_POSITIVE = "phenotype present"
    DISEASE_PHENOTYPE_NEGATIVE = "phenotype absent"

    # Drug-Phenotype (side effects)
    DRUG_SIDE_EFFECT = "side effect"

    # Gene-Gene relationships
    PROTEIN_PROTEIN_INTERACTION = "ppi"
    GENE_COEXPRESSION = "coexpression"

    # Pathway relationships
    PATHWAY_PROTEIN = "pathway"

    # GO relationships
    GO_ANNOTATION = "annotation"

    # Anatomy relationships
    ANATOMY_PROTEIN_EXPRESSION = "expression present"
    ANATOMY_PROTEIN_ABSENT = "expression absent"

    # Exposure relationships
    EXPOSURE_DISEASE = "exposure"
    EXPOSURE_GENE = "exposure_gene"

    # Ontology relationships
    PARENT_CHILD = "parent-child"

    # Additional relationship types from PrimeKG
    INTERACTS = "interacts"
    REGULATES = "regulates"
    PARTICIPATES = "participates"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"
    HAS_COMPONENT = "has_component"
    CATALYZES = "catalyzes"
    INHIBITS = "inhibits"
    ACTIVATES = "activates"


class PrimeKGNode(ForgeModel):
    """
    Base model for all PrimeKG nodes.

    CSV columns: node_index, node_id, node_type, node_name, node_source
    """
    node_index: int = Field(description="Unique integer index in PrimeKG")
    node_id: str = Field(description="Ontology ID (e.g., MONDO:0005015, HP:0001945)")
    node_type: PrimeKGNodeType = Field(description="Type of node")
    node_name: str = Field(description="Human-readable name")
    node_source: str = Field(description="Source database (e.g., MONDO, DrugBank)")

    # Optional enrichment fields
    description: str | None = Field(default=None, description="Clinical description")
    synonyms: list[str] = Field(default_factory=list, description="Alternative names")
    external_ids: dict[str, str] = Field(default_factory=dict, description="Cross-references")

    # Embedding for semantic search
    embedding: list[float] | None = Field(default=None, description="Vector embedding")


class PrimeKGEdge(ForgeModel):
    """
    Model for PrimeKG edges/relationships.

    CSV columns: relation, x_index, y_index, x_id, x_type, x_name, x_source,
                 y_id, y_type, y_name, y_source
    """
    relation: str = Field(description="Relationship type")
    x_index: int = Field(description="Source node index")
    y_index: int = Field(description="Target node index")

    # Source node info
    x_id: str = Field(description="Source node ontology ID")
    x_type: str = Field(description="Source node type")
    x_name: str = Field(description="Source node name")
    x_source: str = Field(description="Source node database")

    # Target node info
    y_id: str = Field(description="Target node ontology ID")
    y_type: str = Field(description="Target node type")
    y_name: str = Field(description="Target node name")
    y_source: str = Field(description="Target node database")

    # Optional metadata
    confidence: float | None = Field(default=None, description="Edge confidence score")
    evidence: str | None = Field(default=None, description="Supporting evidence")
    source_database: str | None = Field(default=None, description="Original data source")


# =============================================================================
# Specialized Node Models
# =============================================================================

class PrimeKGDisease(PrimeKGNode):
    """Disease node with MONDO ontology ID."""
    mondo_id: str = Field(description="MONDO disease ID")
    icd10_codes: list[str] = Field(default_factory=list, description="ICD-10 codes")
    omim_ids: list[str] = Field(default_factory=list, description="OMIM IDs")
    orphanet_id: str | None = Field(default=None, description="Orphanet ID for rare diseases")

    # Clinical info
    clinical_description: str | None = Field(default=None)
    prevalence: str | None = Field(default=None)
    inheritance_pattern: str | None = Field(default=None)
    age_of_onset: str | None = Field(default=None)

    # Associated phenotypes (HPO IDs)
    associated_phenotypes: list[str] = Field(default_factory=list)

    # Associated genes
    associated_genes: list[str] = Field(default_factory=list)


class PrimeKGGene(PrimeKGNode):
    """Gene/Protein node with Entrez Gene ID."""
    entrez_id: str = Field(description="NCBI Entrez Gene ID")
    symbol: str = Field(description="Gene symbol (e.g., BRCA1)")
    uniprot_ids: list[str] = Field(default_factory=list, description="UniProt accessions")
    ensembl_id: str | None = Field(default=None, description="Ensembl gene ID")

    # Gene info
    chromosome: str | None = Field(default=None)
    gene_type: str | None = Field(default=None, description="protein_coding, ncRNA, etc.")

    # Associated diseases
    associated_diseases: list[str] = Field(default_factory=list)

    # GO annotations
    go_bp: list[str] = Field(default_factory=list, description="Biological Process GO terms")
    go_mf: list[str] = Field(default_factory=list, description="Molecular Function GO terms")
    go_cc: list[str] = Field(default_factory=list, description="Cellular Component GO terms")


class PrimeKGDrug(PrimeKGNode):
    """Drug node with DrugBank ID."""
    drugbank_id: str = Field(description="DrugBank ID")
    rxnorm_id: str | None = Field(default=None, description="RxNorm ID")
    chembl_id: str | None = Field(default=None, description="ChEMBL ID")

    # Drug info
    drug_type: str | None = Field(default=None, description="small molecule, biologic, etc.")
    mechanism_of_action: str | None = Field(default=None)
    pharmacodynamics: str | None = Field(default=None)

    # Clinical
    indications: list[str] = Field(default_factory=list, description="MONDO disease IDs")
    contraindications: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list, description="HPO IDs")

    # Targets
    targets: list[str] = Field(default_factory=list, description="Gene/Protein targets")


class PrimeKGPhenotype(PrimeKGNode):
    """Phenotype node with HPO ID."""
    hpo_id: str = Field(description="Human Phenotype Ontology ID")

    # HPO hierarchy
    parent_terms: list[str] = Field(default_factory=list, description="Parent HPO IDs")
    child_terms: list[str] = Field(default_factory=list, description="Child HPO IDs")

    # Phenotype info
    definition: str | None = Field(default=None)
    comment: str | None = Field(default=None)

    # Information content (specificity)
    information_content: float | None = Field(default=None)

    # Associated diseases
    associated_diseases: list[str] = Field(default_factory=list)


class PrimeKGAnatomy(PrimeKGNode):
    """Anatomy node with UBERON ID."""
    uberon_id: str = Field(description="UBERON anatomy ID")

    # Anatomy hierarchy
    parent_structures: list[str] = Field(default_factory=list)
    child_structures: list[str] = Field(default_factory=list)

    # Related info
    definition: str | None = Field(default=None)

    # Expressed genes
    expressed_genes: list[str] = Field(default_factory=list)


class PrimeKGPathway(PrimeKGNode):
    """Pathway node with Reactome ID."""
    reactome_id: str = Field(description="Reactome pathway ID")

    # Pathway info
    pathway_category: str | None = Field(default=None)

    # Member genes/proteins
    member_genes: list[str] = Field(default_factory=list)

    # Related pathways
    parent_pathways: list[str] = Field(default_factory=list)
    child_pathways: list[str] = Field(default_factory=list)


# =============================================================================
# Import/Export Statistics
# =============================================================================

class PrimeKGStats(ForgeModel):
    """Statistics about loaded PrimeKG data."""
    total_nodes: int = 0
    total_edges: int = 0

    # Node counts by type
    disease_count: int = 0
    gene_count: int = 0
    drug_count: int = 0
    phenotype_count: int = 0
    anatomy_count: int = 0
    pathway_count: int = 0
    bioprocess_count: int = 0
    molfunction_count: int = 0
    cellcomponent_count: int = 0
    exposure_count: int = 0

    # Edge counts by type
    edge_counts_by_type: dict[str, int] = Field(default_factory=dict)

    # Data quality
    nodes_with_embeddings: int = 0
    nodes_with_descriptions: int = 0

    # Import metadata
    import_timestamp: datetime | None = None
    primekg_version: str | None = None
    source_url: str | None = None
