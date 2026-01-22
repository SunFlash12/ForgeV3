"""
Tests for PrimeKG Service

Tests cover:
- PrimeKG data models (nodes, edges, specialized types)
- Node type validation
- Edge type validation
- Data model serialization
- Clinical data structure validation
"""

import pytest
from datetime import datetime

from forge.services.primekg.models import (
    PrimeKGNodeType,
    PrimeKGEdgeType,
    PrimeKGNode,
    PrimeKGEdge,
    PrimeKGDisease,
    PrimeKGGene,
    PrimeKGDrug,
    PrimeKGPhenotype,
    PrimeKGAnatomy,
    PrimeKGPathway,
    PrimeKGStats,
)


class TestPrimeKGNodeTypes:
    """Tests for PrimeKG node type enumeration."""

    def test_all_node_types_defined(self):
        """Verify all 10 node types are defined."""
        expected_types = [
            "disease",
            "gene/protein",
            "drug",
            "effect/phenotype",
            "anatomy",
            "pathway",
            "biological_process",
            "molecular_function",
            "cellular_component",
            "exposure",
        ]

        actual_types = [t.value for t in PrimeKGNodeType]
        assert len(actual_types) == 10

        for expected in expected_types:
            assert expected in actual_types, f"Missing node type: {expected}"

    def test_node_type_enum_values(self):
        assert PrimeKGNodeType.DISEASE.value == "disease"
        assert PrimeKGNodeType.GENE_PROTEIN.value == "gene/protein"
        assert PrimeKGNodeType.PHENOTYPE.value == "effect/phenotype"


class TestPrimeKGEdgeTypes:
    """Tests for PrimeKG edge type enumeration."""

    def test_key_edge_types_defined(self):
        """Verify key relationship types are defined."""
        key_types = [
            "indication",
            "contraindication",
            "target",
            "associated with",
            "phenotype present",
            "side effect",
            "ppi",  # protein-protein interaction
            "pathway",
        ]

        actual_types = [t.value for t in PrimeKGEdgeType]

        for key in key_types:
            assert key in actual_types, f"Missing edge type: {key}"

    def test_drug_relationships(self):
        assert PrimeKGEdgeType.INDICATION.value == "indication"
        assert PrimeKGEdgeType.CONTRAINDICATION.value == "contraindication"
        assert PrimeKGEdgeType.DRUG_TARGET.value == "target"
        assert PrimeKGEdgeType.DRUG_SIDE_EFFECT.value == "side effect"


class TestPrimeKGNode:
    """Tests for base PrimeKG node model."""

    def test_create_node(self):
        node = PrimeKGNode(
            node_index=12345,
            node_id="MONDO:0005015",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Diabetes mellitus",
            node_source="MONDO",
        )

        assert node.node_index == 12345
        assert node.node_id == "MONDO:0005015"
        assert node.node_type == PrimeKGNodeType.DISEASE
        assert node.node_name == "Diabetes mellitus"

    def test_node_with_optional_fields(self):
        node = PrimeKGNode(
            node_index=1,
            node_id="HP:0001234",
            node_type=PrimeKGNodeType.PHENOTYPE,
            node_name="Test Phenotype",
            node_source="HPO",
            description="A test phenotype description",
            synonyms=["Synonym A", "Synonym B"],
            external_ids={"OMIM": "123456"},
        )

        assert node.description == "A test phenotype description"
        assert len(node.synonyms) == 2
        assert node.external_ids["OMIM"] == "123456"

    def test_node_with_embedding(self):
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        node = PrimeKGNode(
            node_index=1,
            node_id="TEST:001",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Test",
            node_source="TEST",
            embedding=embedding,
        )

        assert node.embedding == embedding
        assert len(node.embedding) == 5


class TestPrimeKGEdge:
    """Tests for PrimeKG edge model."""

    def test_create_edge(self):
        edge = PrimeKGEdge(
            relation="indication",
            x_index=100,
            y_index=200,
            x_id="DB00001",
            x_type="drug",
            x_name="Lepirudin",
            x_source="DrugBank",
            y_id="MONDO:0005015",
            y_type="disease",
            y_name="Diabetes mellitus",
            y_source="MONDO",
        )

        assert edge.relation == "indication"
        assert edge.x_index == 100
        assert edge.y_index == 200
        assert edge.x_id == "DB00001"
        assert edge.y_id == "MONDO:0005015"

    def test_edge_with_confidence(self):
        edge = PrimeKGEdge(
            relation="associated with",
            x_index=1,
            y_index=2,
            x_id="GENE:123",
            x_type="gene/protein",
            x_name="BRCA1",
            x_source="Entrez",
            y_id="MONDO:0007254",
            y_type="disease",
            y_name="Breast cancer",
            y_source="MONDO",
            confidence=0.95,
            evidence="PMID:12345678",
        )

        assert edge.confidence == 0.95
        assert edge.evidence == "PMID:12345678"


class TestPrimeKGDisease:
    """Tests for disease node model."""

    def test_create_disease_node(self):
        disease = PrimeKGDisease(
            node_index=1000,
            node_id="MONDO:0005015",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Diabetes mellitus",
            node_source="MONDO",
            mondo_id="MONDO:0005015",
            icd10_codes=["E08", "E09", "E10", "E11", "E13"],
            omim_ids=["222100", "125853"],
        )

        assert disease.mondo_id == "MONDO:0005015"
        assert "E10" in disease.icd10_codes
        assert len(disease.omim_ids) == 2

    def test_disease_with_clinical_info(self):
        disease = PrimeKGDisease(
            node_index=1,
            node_id="MONDO:0000001",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Test Disease",
            node_source="MONDO",
            mondo_id="MONDO:0000001",
            clinical_description="A hereditary disorder affecting...",
            prevalence="1-5 / 10,000",
            inheritance_pattern="autosomal recessive",
            age_of_onset="childhood",
            associated_phenotypes=["HP:0001250", "HP:0001263"],
            associated_genes=["GENE1", "GENE2"],
        )

        assert disease.inheritance_pattern == "autosomal recessive"
        assert len(disease.associated_phenotypes) == 2
        assert len(disease.associated_genes) == 2


class TestPrimeKGGene:
    """Tests for gene/protein node model."""

    def test_create_gene_node(self):
        gene = PrimeKGGene(
            node_index=5000,
            node_id="672",  # Entrez Gene ID for BRCA1
            node_type=PrimeKGNodeType.GENE_PROTEIN,
            node_name="BRCA1",
            node_source="Entrez",
            entrez_id="672",
            symbol="BRCA1",
            uniprot_ids=["P38398"],
            ensembl_id="ENSG00000012048",
        )

        assert gene.entrez_id == "672"
        assert gene.symbol == "BRCA1"
        assert "P38398" in gene.uniprot_ids

    def test_gene_with_go_annotations(self):
        gene = PrimeKGGene(
            node_index=1,
            node_id="1234",
            node_type=PrimeKGNodeType.GENE_PROTEIN,
            node_name="TEST",
            node_source="Entrez",
            entrez_id="1234",
            symbol="TEST",
            chromosome="17",
            gene_type="protein_coding",
            go_bp=["GO:0006281", "GO:0006974"],  # DNA repair
            go_mf=["GO:0003684"],  # DNA binding
            go_cc=["GO:0005634"],  # nucleus
        )

        assert gene.chromosome == "17"
        assert len(gene.go_bp) == 2
        assert "GO:0003684" in gene.go_mf


class TestPrimeKGDrug:
    """Tests for drug node model."""

    def test_create_drug_node(self):
        drug = PrimeKGDrug(
            node_index=3000,
            node_id="DB00001",
            node_type=PrimeKGNodeType.DRUG,
            node_name="Lepirudin",
            node_source="DrugBank",
            drugbank_id="DB00001",
            rxnorm_id="12345",
            drug_type="small molecule",
        )

        assert drug.drugbank_id == "DB00001"
        assert drug.drug_type == "small molecule"

    def test_drug_with_clinical_info(self):
        drug = PrimeKGDrug(
            node_index=1,
            node_id="DB00000",
            node_type=PrimeKGNodeType.DRUG,
            node_name="Test Drug",
            node_source="DrugBank",
            drugbank_id="DB00000",
            mechanism_of_action="Inhibits enzyme X",
            indications=["MONDO:0005015", "MONDO:0000001"],
            contraindications=["MONDO:0005148"],
            side_effects=["HP:0002013", "HP:0002017"],
            targets=["GENE1", "GENE2"],
        )

        assert len(drug.indications) == 2
        assert len(drug.side_effects) == 2
        assert len(drug.targets) == 2


class TestPrimeKGPhenotype:
    """Tests for phenotype node model."""

    def test_create_phenotype_node(self):
        phenotype = PrimeKGPhenotype(
            node_index=7000,
            node_id="HP:0001250",
            node_type=PrimeKGNodeType.PHENOTYPE,
            node_name="Seizures",
            node_source="HPO",
            hpo_id="HP:0001250",
            parent_terms=["HP:0012638"],  # Abnormal nervous system physiology
            definition="Seizures are an abnormal...",
        )

        assert phenotype.hpo_id == "HP:0001250"
        assert phenotype.node_name == "Seizures"
        assert len(phenotype.parent_terms) == 1

    def test_phenotype_with_information_content(self):
        phenotype = PrimeKGPhenotype(
            node_index=1,
            node_id="HP:0000001",
            node_type=PrimeKGNodeType.PHENOTYPE,
            node_name="Test Phenotype",
            node_source="HPO",
            hpo_id="HP:0000001",
            information_content=5.23,  # Higher = more specific
            associated_diseases=["MONDO:0000001", "MONDO:0000002"],
        )

        assert phenotype.information_content == 5.23
        assert len(phenotype.associated_diseases) == 2


class TestPrimeKGAnatomy:
    """Tests for anatomy node model."""

    def test_create_anatomy_node(self):
        anatomy = PrimeKGAnatomy(
            node_index=8000,
            node_id="UBERON:0000955",
            node_type=PrimeKGNodeType.ANATOMY,
            node_name="Brain",
            node_source="UBERON",
            uberon_id="UBERON:0000955",
            parent_structures=["UBERON:0001016"],  # Nervous system
        )

        assert anatomy.uberon_id == "UBERON:0000955"
        assert anatomy.node_name == "Brain"


class TestPrimeKGPathway:
    """Tests for pathway node model."""

    def test_create_pathway_node(self):
        pathway = PrimeKGPathway(
            node_index=9000,
            node_id="R-HSA-109581",
            node_type=PrimeKGNodeType.PATHWAY,
            node_name="Apoptosis",
            node_source="Reactome",
            reactome_id="R-HSA-109581",
            pathway_category="Cell Death",
            member_genes=["GENE1", "GENE2", "GENE3"],
        )

        assert pathway.reactome_id == "R-HSA-109581"
        assert pathway.pathway_category == "Cell Death"
        assert len(pathway.member_genes) == 3


class TestPrimeKGStats:
    """Tests for PrimeKG statistics model."""

    def test_create_empty_stats(self):
        stats = PrimeKGStats()

        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert stats.disease_count == 0

    def test_stats_with_data(self):
        stats = PrimeKGStats(
            total_nodes=129375,
            total_edges=8100498,
            disease_count=17080,
            gene_count=27671,
            drug_count=7957,
            phenotype_count=15311,
            anatomy_count=14035,
            pathway_count=2516,
            bioprocess_count=28642,
            molfunction_count=11169,
            cellcomponent_count=4176,
            exposure_count=818,
            nodes_with_embeddings=125000,
            nodes_with_descriptions=100000,
            import_timestamp=datetime.utcnow(),
            primekg_version="1.0",
        )

        assert stats.total_nodes == 129375
        assert stats.total_edges == 8100498
        assert stats.disease_count == 17080
        assert stats.nodes_with_embeddings == 125000


class TestNodeTypeCoverage:
    """Tests verifying all node types are properly modeled."""

    def test_disease_type_mapping(self):
        disease = PrimeKGDisease(
            node_index=1,
            node_id="MONDO:0000001",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Test",
            node_source="MONDO",
            mondo_id="MONDO:0000001",
        )
        assert disease.node_type == PrimeKGNodeType.DISEASE

    def test_gene_type_mapping(self):
        gene = PrimeKGGene(
            node_index=1,
            node_id="1",
            node_type=PrimeKGNodeType.GENE_PROTEIN,
            node_name="Test",
            node_source="Entrez",
            entrez_id="1",
            symbol="TEST",
        )
        assert gene.node_type == PrimeKGNodeType.GENE_PROTEIN

    def test_phenotype_type_mapping(self):
        phenotype = PrimeKGPhenotype(
            node_index=1,
            node_id="HP:0000001",
            node_type=PrimeKGNodeType.PHENOTYPE,
            node_name="Test",
            node_source="HPO",
            hpo_id="HP:0000001",
        )
        assert phenotype.node_type == PrimeKGNodeType.PHENOTYPE


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_node_to_dict(self):
        node = PrimeKGNode(
            node_index=1,
            node_id="TEST:001",
            node_type=PrimeKGNodeType.DISEASE,
            node_name="Test Node",
            node_source="TEST",
        )

        data = node.model_dump()

        assert data["node_index"] == 1
        assert data["node_id"] == "TEST:001"
        assert data["node_name"] == "Test Node"

    def test_edge_to_dict(self):
        edge = PrimeKGEdge(
            relation="test",
            x_index=1,
            y_index=2,
            x_id="A",
            x_type="test",
            x_name="NodeA",
            x_source="TEST",
            y_id="B",
            y_type="test",
            y_name="NodeB",
            y_source="TEST",
        )

        data = edge.model_dump()

        assert data["relation"] == "test"
        assert data["x_id"] == "A"
        assert data["y_id"] == "B"
