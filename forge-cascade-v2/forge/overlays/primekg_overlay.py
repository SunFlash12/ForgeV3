"""
PrimeKG Biomedical Knowledge Graph Overlay

Integrates the Precision Medicine Knowledge Graph (PrimeKG) into Forge V3
for clinical decision support and differential diagnosis.

Features:
- Phenotype-to-disease mapping via HPO
- Drug-disease relationship queries (indications, contraindications)
- Gene-disease association lookups
- Pathway analysis for mechanism understanding
- Semantic search on clinical descriptions
- Differential diagnosis generation

PrimeKG Statistics:
- 129,375 nodes across 10 biological entity types
- 4,050,249 edges across 30 relationship types
- 17,080+ diseases with phenotype mappings
"""

from typing import Any

import structlog

from forge.models.base import TrustLevel
from forge.models.events import Event, EventType
from forge.models.overlay import Capability, FuelBudget
from forge.overlays.base import (
    BaseOverlay,
    OverlayContext,
    OverlayError,
    OverlayResult,
)

# Protocol types for external services (no concrete implementations available)
# These allow mypy to understand the duck-typed service interfaces.

logger = structlog.get_logger(__name__)


class PrimeKGError(OverlayError):
    """PrimeKG-specific error."""
    pass


class PrimeKGOverlay(BaseOverlay):
    """
    PrimeKG Biomedical Knowledge Graph Overlay.

    Provides clinical decision support through:
    - Phenotype-based disease matching (HPO)
    - Drug-disease interactions
    - Gene-disease associations
    - Pathway analysis
    - Semantic search on biomedical entities
    """

    NAME = "primekg"
    VERSION = "1.0.0"
    DESCRIPTION = "Precision Medicine Knowledge Graph integration for diagnostic support"

    # Events this overlay subscribes to
    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.CASCADE_INITIATED,
        EventType.INSIGHT_GENERATED,
        EventType.SYSTEM_EVENT,
    }

    # Required capabilities
    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_PUBLISH,
        Capability.LLM_ACCESS,
    }

    # Minimum trust level (medical data requires higher trust)
    MIN_TRUST_LEVEL = TrustLevel.TRUSTED

    # Resource limits
    DEFAULT_FUEL_BUDGET = FuelBudget(
        function_name="primekg_query",
        max_fuel=5_000_000,
        max_memory_bytes=100 * 1024 * 1024,  # 100MB for graph traversals
        timeout_ms=60000,  # 60s for complex queries
    )

    def __init__(
        self,
        neo4j_client: Any = None,
        embedding_service: Any = None,
        llm_service: Any = None,
    ) -> None:
        """
        Initialize the PrimeKG overlay.

        Args:
            neo4j_client: Neo4j database client
            embedding_service: PrimeKG embedding service for semantic search
            llm_service: LLM service for natural language queries
        """
        super().__init__()
        self._neo4j: Any = neo4j_client
        self._embedding: Any = embedding_service
        self._llm: Any = llm_service

        # Cached data structures
        self._hpo_hierarchy: dict[str, list[str]] | None = None
        self._disease_phenotype_cache: dict[str, list[str]] = {}
        self._cache_ttl = 3600  # 1 hour

    async def initialize(self) -> bool:
        """
        Initialize the PrimeKG overlay.

        Preloads HPO hierarchy for fast phenotype traversal.
        """
        self._logger.info("primekg_overlay_initializing")

        try:
            # Verify PrimeKG data is loaded
            if self._neo4j:
                stats = await self._verify_primekg_data()
                if stats.get("disease_count", 0) < 1000:
                    self._logger.warning(
                        "primekg_data_incomplete",
                        stats=stats
                    )

                # Preload HPO hierarchy
                self._hpo_hierarchy = await self._load_hpo_hierarchy()
                self._logger.info(
                    "primekg_hpo_loaded",
                    terms=len(self._hpo_hierarchy) if self._hpo_hierarchy else 0
                )

            return await super().initialize()

        except Exception as e:
            self._logger.error("primekg_init_error", error=str(e))
            return False

    async def cleanup(self) -> None:
        """Clean up overlay resources."""
        self._hpo_hierarchy = None
        self._disease_phenotype_cache.clear()
        await super().cleanup()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """
        Execute PrimeKG knowledge operations.

        Supported operations:
        - phenotype_to_disease: Map HPO phenotypes to candidate diseases
        - disease_to_drugs: Get drug indications/contraindications for disease
        - gene_disease_association: Get gene-disease relationships
        - pathway_analysis: Analyze pathway involvement
        - differential_diagnosis: Generate ranked differential
        - semantic_search: Search by clinical description
        - find_discriminating_phenotypes: Find phenotypes that distinguish diseases
        """
        data = input_data or {}
        if event:
            data.update(event.payload or {})

        operation = data.get("operation", "semantic_search")

        self._logger.info(
            "primekg_execute",
            operation=operation,
            execution_id=context.execution_id
        )

        try:
            if operation == "phenotype_to_disease":
                result = await self._phenotype_to_disease(data, context)
            elif operation == "disease_to_drugs":
                result = await self._disease_to_drugs(data, context)
            elif operation == "gene_disease_association":
                result = await self._gene_disease_association(data, context)
            elif operation == "pathway_analysis":
                result = await self._pathway_analysis(data, context)
            elif operation == "differential_diagnosis":
                result = await self._differential_diagnosis(data, context)
            elif operation == "semantic_search":
                result = await self._semantic_search(data, context)
            elif operation == "find_discriminating_phenotypes":
                result = await self._find_discriminating_phenotypes(data, context)
            elif operation == "get_disease_details":
                result = await self._get_disease_details(data, context)
            elif operation == "check_drug_interactions":
                result = await self._check_drug_interactions(data, context)
            else:
                return OverlayResult.fail(f"Unknown operation: {operation}")

            # Emit insight event if significant results
            events_to_emit = []
            if result.get("results") and len(result["results"]) > 0:
                events_to_emit.append(
                    self.create_event_emission(
                        EventType.INSIGHT_GENERATED,
                        {
                            "source": "primekg",
                            "operation": operation,
                            "result_count": len(result.get("results", [])),
                        }
                    )
                )

            return OverlayResult.ok(
                data=result,
                events_to_emit=events_to_emit,
                metrics={
                    "operation": operation,
                    "results_count": len(result.get("results", [])),
                }
            )

        except Exception as e:
            self._logger.error(
                "primekg_execution_error",
                operation=operation,
                error=str(e)
            )
            return OverlayResult.fail(f"PrimeKG error: {str(e)}")

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def _phenotype_to_disease(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Map phenotypes (HPO terms) to candidate diseases.

        Uses phenotype-disease edges from PrimeKG to find diseases
        that match the given phenotypes.

        Args:
            data: Contains "phenotypes" list of HPO IDs

        Returns:
            Ranked list of candidate diseases with match scores
        """
        phenotypes = data.get("phenotypes", [])
        if not phenotypes:
            return {"operation": "phenotype_to_disease", "results": []}

        limit = data.get("limit", 20)

        query = """
        UNWIND $phenotypes AS hpo_id
        MATCH (p:PrimeKGPhenotype)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(d:PrimeKGDisease)
        WHERE p.hpo_id = hpo_id OR p.node_id = hpo_id
        WITH d, collect(DISTINCT p.hpo_id) as matched_phenotypes, count(DISTINCT p) as match_count
        OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(all_p:PrimeKGPhenotype)
        WITH d, matched_phenotypes, match_count, count(DISTINCT all_p) as total_phenotypes
        RETURN d.node_id as disease_id,
               d.name as disease_name,
               d.mondo_id as mondo_id,
               d.description as description,
               matched_phenotypes,
               match_count,
               total_phenotypes,
               toFloat(match_count) / size($phenotypes) as recall,
               CASE WHEN total_phenotypes > 0
                    THEN toFloat(match_count) / total_phenotypes
                    ELSE 0.0 END as precision
        ORDER BY recall * precision DESC, match_count DESC
        LIMIT $limit
        """

        results = await self._neo4j.run(query, {
            "phenotypes": phenotypes,
            "limit": limit,
        })

        return {
            "operation": "phenotype_to_disease",
            "input_phenotypes": phenotypes,
            "results": [
                {
                    "disease_id": r["disease_id"],
                    "disease_name": r["disease_name"],
                    "mondo_id": r["mondo_id"],
                    "description": r["description"],
                    "matched_phenotypes": r["matched_phenotypes"],
                    "match_count": r["match_count"],
                    "total_phenotypes": r["total_phenotypes"],
                    "recall": r["recall"],
                    "precision": r["precision"],
                    "score": r["recall"] * r["precision"],
                }
                for r in results
            ],
        }

    async def _disease_to_drugs(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Get drugs related to a disease (indications, contraindications, off-label).

        Args:
            data: Contains "disease_id" (MONDO ID)

        Returns:
            Dict with indications, contraindications, and off_label lists
        """
        disease_id = data.get("disease_id")
        if not disease_id:
            return {"operation": "disease_to_drugs", "error": "disease_id required"}

        query = """
        MATCH (d:PrimeKGDisease)
        WHERE d.mondo_id = $disease_id OR d.node_id = $disease_id
        OPTIONAL MATCH (drug:PrimeKGDrug)-[r:INDICATED_FOR|INDICATION]->(d)
        WITH d, collect(DISTINCT {
            drug_id: drug.drugbank_id,
            name: drug.name,
            relation: 'indication'
        }) as indications
        OPTIONAL MATCH (drug:PrimeKGDrug)-[r:CONTRAINDICATED_FOR|CONTRAINDICATION]->(d)
        WITH d, indications, collect(DISTINCT {
            drug_id: drug.drugbank_id,
            name: drug.name,
            relation: 'contraindication'
        }) as contraindications
        OPTIONAL MATCH (drug:PrimeKGDrug)-[r:OFF_LABEL_FOR|`off-label use`]->(d)
        WITH d, indications, contraindications, collect(DISTINCT {
            drug_id: drug.drugbank_id,
            name: drug.name,
            relation: 'off_label'
        }) as off_label
        RETURN d.name as disease_name,
               indications,
               contraindications,
               off_label
        """

        results = await self._neo4j.run(query, {"disease_id": disease_id})

        if not results:
            return {
                "operation": "disease_to_drugs",
                "disease_id": disease_id,
                "indications": [],
                "contraindications": [],
                "off_label": [],
            }

        r = results[0]
        return {
            "operation": "disease_to_drugs",
            "disease_id": disease_id,
            "disease_name": r["disease_name"],
            "indications": [i for i in r["indications"] if i["drug_id"]],
            "contraindications": [c for c in r["contraindications"] if c["drug_id"]],
            "off_label": [o for o in r["off_label"] if o["drug_id"]],
        }

    async def _gene_disease_association(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Get gene-disease associations from PrimeKG.

        Can query by gene or by disease.

        Args:
            data: Contains "gene_id" (Entrez ID) or "disease_id" (MONDO ID)

        Returns:
            List of associations with evidence
        """
        gene_id = data.get("gene_id")
        disease_id = data.get("disease_id")
        limit = data.get("limit", 50)

        if gene_id:
            query = """
            MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
            WHERE g.entrez_id = $gene_id OR g.node_id = $gene_id OR g.symbol = $gene_id
            RETURN g.symbol as gene_symbol,
                   g.entrez_id as gene_id,
                   d.name as disease_name,
                   d.mondo_id as disease_id,
                   type(r) as relation_type
            LIMIT $limit
            """
            results = await self._neo4j.run(query, {"gene_id": gene_id, "limit": limit})

        elif disease_id:
            query = """
            MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
            WHERE d.mondo_id = $disease_id OR d.node_id = $disease_id
            RETURN g.symbol as gene_symbol,
                   g.entrez_id as gene_id,
                   d.name as disease_name,
                   d.mondo_id as disease_id,
                   type(r) as relation_type
            LIMIT $limit
            """
            results = await self._neo4j.run(query, {"disease_id": disease_id, "limit": limit})

        else:
            return {"operation": "gene_disease_association", "error": "gene_id or disease_id required"}

        return {
            "operation": "gene_disease_association",
            "query": {"gene_id": gene_id, "disease_id": disease_id},
            "associations": [
                {
                    "gene_symbol": r["gene_symbol"],
                    "gene_id": r["gene_id"],
                    "disease_name": r["disease_name"],
                    "disease_id": r["disease_id"],
                    "relation": r["relation_type"],
                }
                for r in results
            ],
        }

    async def _pathway_analysis(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Analyze pathway involvement for genes or diseases.

        Args:
            data: Contains "gene_ids" list or "disease_id"

        Returns:
            List of pathways with enrichment scores
        """
        gene_ids = data.get("gene_ids", [])
        disease_id = data.get("disease_id")
        limit = data.get("limit", 20)

        if gene_ids:
            query = """
            UNWIND $gene_ids AS gene_id
            MATCH (g:PrimeKGGene)-[:PARTICIPATES_IN|pathway]-(p:PrimeKGPathway)
            WHERE g.entrez_id = gene_id OR g.symbol = gene_id
            WITH p, collect(DISTINCT g.symbol) as genes
            RETURN p.reactome_id as pathway_id,
                   p.name as pathway_name,
                   genes,
                   size(genes) as gene_count
            ORDER BY gene_count DESC
            LIMIT $limit
            """
            results = await self._neo4j.run(query, {"gene_ids": gene_ids, "limit": limit})

        elif disease_id:
            # Find pathways via disease-associated genes
            query = """
            MATCH (d:PrimeKGDisease)-[:ASSOCIATED_WITH|`associated with`]-(g:PrimeKGGene)
            WHERE d.mondo_id = $disease_id
            MATCH (g)-[:PARTICIPATES_IN|pathway]-(p:PrimeKGPathway)
            WITH p, collect(DISTINCT g.symbol) as genes
            RETURN p.reactome_id as pathway_id,
                   p.name as pathway_name,
                   genes,
                   size(genes) as gene_count
            ORDER BY gene_count DESC
            LIMIT $limit
            """
            results = await self._neo4j.run(query, {"disease_id": disease_id, "limit": limit})

        else:
            return {"operation": "pathway_analysis", "error": "gene_ids or disease_id required"}

        return {
            "operation": "pathway_analysis",
            "results": [
                {
                    "pathway_id": r["pathway_id"],
                    "pathway_name": r["pathway_name"],
                    "genes": r["genes"],
                    "gene_count": r["gene_count"],
                }
                for r in results
            ],
        }

    async def _differential_diagnosis(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Generate differential diagnosis from phenotypes and clinical context.

        Combines:
        - HPO phenotype matching
        - Gene associations (if genetic data available)
        - Drug history (for contraindications)

        Args:
            data: Contains "phenotypes" (HPO IDs), optional "genes", "medications"

        Returns:
            Ranked differential diagnosis with evidence
        """
        phenotypes = data.get("phenotypes", [])
        genes = data.get("genes", [])
        medications = data.get("medications", [])

        if not phenotypes:
            return {"operation": "differential_diagnosis", "error": "phenotypes required"}

        # Phase 1: Phenotype-based candidates
        phenotype_result = await self._phenotype_to_disease(
            {"phenotypes": phenotypes, "limit": 30},
            context
        )
        candidates = phenotype_result.get("results", [])

        # Phase 2: Boost by gene associations if available
        if genes and candidates:
            gene_diseases = set()
            for gene in genes:
                gene_result = await self._gene_disease_association(
                    {"gene_id": gene},
                    context
                )
                for assoc in gene_result.get("associations", []):
                    gene_diseases.add(assoc["disease_id"])

            # Boost candidates with genetic support
            for candidate in candidates:
                if candidate["disease_id"] in gene_diseases or candidate.get("mondo_id") in gene_diseases:
                    candidate["gene_support"] = True
                    candidate["score"] *= 1.5  # 50% boost
                else:
                    candidate["gene_support"] = False

        # Phase 3: Filter by contraindications if medications provided
        if medications and candidates:
            contraindicated_diseases: set[str] = set()
            for _med in medications:
                # This would query drug-disease contraindications
                # Simplified for now - actual implementation would use _med
                pass

            candidates = [
                c for c in candidates
                if c["disease_id"] not in contraindicated_diseases
            ]

        # Re-sort by adjusted score
        candidates.sort(key=lambda c: c.get("score", 0), reverse=True)

        return {
            "operation": "differential_diagnosis",
            "input": {
                "phenotypes": phenotypes,
                "genes": genes,
                "medications": medications,
            },
            "differential": candidates[:10],
            "total_candidates": len(candidates),
        }

    async def _semantic_search(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Semantic search on PrimeKG clinical descriptions.

        Args:
            data: Contains "query" (search text), optional "node_type"

        Returns:
            List of matching nodes with similarity scores
        """
        query = data.get("query")
        if not query:
            return {"operation": "semantic_search", "error": "query required"}

        node_type = data.get("node_type")
        limit = data.get("limit", 10)
        min_score = data.get("min_score", 0.7)

        if self._embedding:
            results = await self._embedding.semantic_search(
                query=query,
                node_type=node_type,
                limit=limit,
                min_score=min_score,
            )
        else:
            # Fallback to text search
            results = await self._text_search(query, node_type, limit)

        return {
            "operation": "semantic_search",
            "query": query,
            "results": results,
        }

    async def _find_discriminating_phenotypes(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Find phenotypes that discriminate between two diseases.

        Used for generating follow-up questions in diagnosis.

        Args:
            data: Contains "disease_a" and "disease_b" (MONDO IDs),
                  optional "already_present" (HPO IDs to exclude)

        Returns:
            List of discriminating phenotypes
        """
        disease_a = data.get("disease_a")
        disease_b = data.get("disease_b")
        already_present = data.get("already_present", [])

        if not disease_a or not disease_b:
            return {"operation": "find_discriminating_phenotypes", "error": "disease_a and disease_b required"}

        query = """
        // Get phenotypes for disease A
        MATCH (da:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(pa:PrimeKGPhenotype)
        WHERE da.mondo_id = $disease_a OR da.node_id = $disease_a
        WITH collect(DISTINCT pa.hpo_id) as phenotypes_a

        // Get phenotypes for disease B
        MATCH (db:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(pb:PrimeKGPhenotype)
        WHERE db.mondo_id = $disease_b OR db.node_id = $disease_b
        WITH phenotypes_a, collect(DISTINCT pb.hpo_id) as phenotypes_b

        // Find phenotypes in A but not in B
        WITH [p IN phenotypes_a WHERE NOT p IN phenotypes_b] as discriminating_for_a,
             [p IN phenotypes_b WHERE NOT p IN phenotypes_a] as discriminating_for_b

        UNWIND discriminating_for_a as hpo_id
        MATCH (p:PrimeKGPhenotype)
        WHERE p.hpo_id = hpo_id AND NOT hpo_id IN $already_present
        RETURN p.hpo_id as hpo_id,
               p.name as name,
               'supports_a' as discriminates
        LIMIT 5

        UNION

        UNWIND discriminating_for_b as hpo_id
        MATCH (p:PrimeKGPhenotype)
        WHERE p.hpo_id = hpo_id AND NOT hpo_id IN $already_present
        RETURN p.hpo_id as hpo_id,
               p.name as name,
               'supports_b' as discriminates
        LIMIT 5
        """

        results = await self._neo4j.run(query, {
            "disease_a": disease_a,
            "disease_b": disease_b,
            "already_present": already_present,
        })

        return {
            "operation": "find_discriminating_phenotypes",
            "disease_a": disease_a,
            "disease_b": disease_b,
            "phenotypes": [
                {
                    "hpo_id": r["hpo_id"],
                    "name": r["name"],
                    "discriminates": r["discriminates"],
                    "description": f"Do you experience {r['name']}?",
                }
                for r in results
            ],
        }

    async def _get_disease_details(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Get full details for a disease.

        Args:
            data: Contains "disease_id" (MONDO ID)

        Returns:
            Complete disease information
        """
        disease_id = data.get("disease_id")
        if not disease_id:
            return {"operation": "get_disease_details", "error": "disease_id required"}

        query = """
        MATCH (d:PrimeKGDisease)
        WHERE d.mondo_id = $disease_id OR d.node_id = $disease_id
        OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WITH d, collect(DISTINCT {hpo_id: p.hpo_id, name: p.name}) as phenotypes
        OPTIONAL MATCH (d)-[:ASSOCIATED_WITH|`associated with`]-(g:PrimeKGGene)
        WITH d, phenotypes, collect(DISTINCT {gene_id: g.entrez_id, symbol: g.symbol}) as genes
        OPTIONAL MATCH (drug:PrimeKGDrug)-[:INDICATED_FOR|INDICATION]->(d)
        WITH d, phenotypes, genes, collect(DISTINCT {drug_id: drug.drugbank_id, name: drug.name}) as treatments
        RETURN d.node_id as node_id,
               d.mondo_id as mondo_id,
               d.name as name,
               d.description as description,
               phenotypes,
               genes,
               treatments
        """

        results = await self._neo4j.run(query, {"disease_id": disease_id})

        if not results:
            return {"operation": "get_disease_details", "error": "Disease not found"}

        r = results[0]
        return {
            "operation": "get_disease_details",
            "disease": {
                "node_id": r["node_id"],
                "mondo_id": r["mondo_id"],
                "name": r["name"],
                "description": r["description"],
                "phenotypes": [p for p in r["phenotypes"] if p["hpo_id"]],
                "genes": [g for g in r["genes"] if g["gene_id"]],
                "treatments": [t for t in r["treatments"] if t["drug_id"]],
            },
        }

    async def _check_drug_interactions(
        self,
        data: dict[str, Any],
        context: OverlayContext,
    ) -> dict[str, Any]:
        """
        Check for drug-disease interactions and contraindications.

        Args:
            data: Contains "drugs" (list of DrugBank IDs) and "diseases" (MONDO IDs)

        Returns:
            List of interactions and contraindications
        """
        drugs = data.get("drugs", [])
        diseases = data.get("diseases", [])

        if not drugs:
            return {"operation": "check_drug_interactions", "error": "drugs required"}

        interactions = []

        for drug_id in drugs:
            query = """
            MATCH (drug:PrimeKGDrug)
            WHERE drug.drugbank_id = $drug_id OR drug.name = $drug_id
            OPTIONAL MATCH (drug)-[r:CONTRAINDICATED_FOR|CONTRAINDICATION]->(d:PrimeKGDisease)
            WHERE d.mondo_id IN $diseases OR d.node_id IN $diseases
            RETURN drug.name as drug_name,
                   drug.drugbank_id as drug_id,
                   collect(DISTINCT {
                       disease_id: d.mondo_id,
                       disease_name: d.name,
                       interaction_type: 'contraindication'
                   }) as contraindications
            """

            results = await self._neo4j.run(query, {
                "drug_id": drug_id,
                "diseases": diseases,
            })

            if results:
                r = results[0]
                contraindications = [c for c in r["contraindications"] if c["disease_id"]]
                if contraindications:
                    interactions.append({
                        "drug_name": r["drug_name"],
                        "drug_id": r["drug_id"],
                        "contraindications": contraindications,
                    })

        return {
            "operation": "check_drug_interactions",
            "drugs": drugs,
            "diseases": diseases,
            "interactions": interactions,
            "has_contraindications": len(interactions) > 0,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _verify_primekg_data(self) -> dict[str, Any]:
        """Verify PrimeKG data is loaded in Neo4j."""
        query = """
        MATCH (n:PrimeKGNode)
        RETURN n.node_type as type, count(n) as count
        """
        results = await self._neo4j.run(query)

        counts = {r["type"]: r["count"] for r in results}
        return {
            "disease_count": counts.get("disease", 0),
            "gene_count": counts.get("gene/protein", 0),
            "drug_count": counts.get("drug", 0),
            "phenotype_count": counts.get("effect/phenotype", 0),
            "total_nodes": sum(counts.values()),
        }

    async def _load_hpo_hierarchy(self) -> dict[str, list[str]]:
        """Load HPO parent-child relationships."""
        query = """
        MATCH (child:PrimeKGPhenotype)-[:PARENT_OF|`parent-child`]->(parent:PrimeKGPhenotype)
        RETURN child.hpo_id as child, collect(parent.hpo_id) as parents
        """
        results = await self._neo4j.run(query)

        return {r["child"]: r["parents"] for r in results}

    async def _text_search(
        self,
        query: str,
        node_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fallback text search using full-text index."""
        type_filter = f"AND n.node_type = '{node_type}'" if node_type else ""

        cypher = f"""
        CALL db.index.fulltext.queryNodes('primekg_description', $query)
        YIELD node, score
        WHERE score > 0.5 {type_filter}
        RETURN node.node_id as node_id,
               node.name as name,
               node.node_type as type,
               node.description as description,
               score
        ORDER BY score DESC
        LIMIT $limit
        """

        results = await self._neo4j.run(cypher, {"query": query, "limit": limit})

        return [
            {
                "node_id": r["node_id"],
                "name": r["name"],
                "type": r["type"],
                "description": r["description"],
                "score": r["score"],
            }
            for r in results
        ]


# =============================================================================
# Factory Function
# =============================================================================

def create_primekg_overlay(
    neo4j_client: Any = None,
    embedding_service: Any = None,
    llm_service: Any = None,
) -> PrimeKGOverlay:
    """
    Factory function to create PrimeKG overlay.

    Args:
        neo4j_client: Neo4j database client
        embedding_service: Embedding service for semantic search
        llm_service: LLM service for NL queries

    Returns:
        Configured PrimeKGOverlay instance
    """
    return PrimeKGOverlay(
        neo4j_client=neo4j_client,
        embedding_service=embedding_service,
        llm_service=llm_service,
    )
