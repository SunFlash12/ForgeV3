"""
PrimeKG Neo4j Import Service

Imports PrimeKG data into Neo4j with:
- Batch processing for efficiency
- Progress tracking and resume capability
- Transaction management
- Error handling and retry logic
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

from .models import PrimeKGEdge, PrimeKGNode, PrimeKGNodeType, PrimeKGStats
from .parser import PrimeKGParser

logger = structlog.get_logger(__name__)


@dataclass
class ImportProgress:
    """Progress tracking for import operations."""
    phase: str  # "nodes" or "edges"
    total_records: int = 0
    imported_records: int = 0
    failed_records: int = 0
    current_batch: int = 0
    total_batches: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    is_resuming: bool = False
    resume_from_batch: int = 0

    @property
    def progress_percent(self) -> float:
        if self.total_records == 0:
            return 0.0
        return (self.imported_records / self.total_records) * 100

    @property
    def is_complete(self) -> bool:
        return self.imported_records >= self.total_records


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    nodes_imported: int = 0
    edges_imported: int = 0
    nodes_failed: int = 0
    edges_failed: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    stats: PrimeKGStats | None = None


class PrimeKGImportService:
    """
    Service for importing PrimeKG data into Neo4j.

    Features:
    - Batch imports (configurable size)
    - Resume from last successful batch
    - Progress persistence
    - Transaction management
    - Concurrent batch processing
    """

    # Node labels by type
    NODE_LABELS = {
        PrimeKGNodeType.DISEASE: "PrimeKGDisease",
        PrimeKGNodeType.GENE_PROTEIN: "PrimeKGGene",
        PrimeKGNodeType.DRUG: "PrimeKGDrug",
        PrimeKGNodeType.PHENOTYPE: "PrimeKGPhenotype",
        PrimeKGNodeType.ANATOMY: "PrimeKGAnatomy",
        PrimeKGNodeType.PATHWAY: "PrimeKGPathway",
        PrimeKGNodeType.BIOLOGICAL_PROCESS: "PrimeKGBioProcess",
        PrimeKGNodeType.MOLECULAR_FUNCTION: "PrimeKGMolFunction",
        PrimeKGNodeType.CELLULAR_COMPONENT: "PrimeKGCellComponent",
        PrimeKGNodeType.EXPOSURE: "PrimeKGExposure",
    }

    # Relationship type mapping (normalize to Neo4j conventions)
    RELATIONSHIP_MAP = {
        "indication": "INDICATED_FOR",
        "contraindication": "CONTRAINDICATED_FOR",
        "off-label use": "OFF_LABEL_FOR",
        "target": "TARGETS",
        "enzyme": "ENZYME_OF",
        "carrier": "CARRIER_OF",
        "transporter": "TRANSPORTER_OF",
        "associated with": "ASSOCIATED_WITH",
        "phenotype present": "HAS_PHENOTYPE",
        "phenotype absent": "LACKS_PHENOTYPE",
        "side effect": "CAUSES_SIDE_EFFECT",
        "ppi": "INTERACTS_WITH",
        "coexpression": "COEXPRESSED_WITH",
        "pathway": "PARTICIPATES_IN",
        "annotation": "ANNOTATED_WITH",
        "expression present": "EXPRESSED_IN",
        "expression absent": "NOT_EXPRESSED_IN",
        "exposure": "EXPOSURE_LINKED",
        "parent-child": "PARENT_OF",
    }

    def __init__(
        self,
        neo4j_client,
        batch_size: int = 1000,
        edge_batch_size: int = 5000,
        max_retries: int = 3,
        progress_file: Path | None = None,
    ):
        """
        Initialize the import service.

        Args:
            neo4j_client: Neo4j database client
            batch_size: Nodes per batch
            edge_batch_size: Edges per batch
            max_retries: Max retries per batch
            progress_file: File to persist import progress
        """
        self.neo4j = neo4j_client
        self.batch_size = batch_size
        self.edge_batch_size = edge_batch_size
        self.max_retries = max_retries
        self.progress_file = progress_file or Path("./data/primekg/import_progress.json")

        self.parser = PrimeKGParser(batch_size=batch_size)
        self._progress_callbacks: list[Callable[[ImportProgress], None]] = []
        self._cancelled = False

    def add_progress_callback(
        self,
        callback: Callable[[ImportProgress], None]
    ) -> None:
        """Add a callback to receive progress updates."""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, progress: ImportProgress) -> None:
        """Notify all callbacks of progress update."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning("import_callback_error", error=str(e))

    def cancel(self) -> None:
        """Cancel ongoing import."""
        self._cancelled = True
        logger.info("primekg_import_cancel_requested")

    # =========================================================================
    # Schema Setup
    # =========================================================================

    async def setup_schema(self) -> bool:
        """
        Create Neo4j constraints and indexes for PrimeKG data.

        Should be called before importing data.
        """
        logger.info("primekg_setting_up_schema")

        schema_queries = [
            # Node constraints (unique identifiers)
            "CREATE CONSTRAINT primekg_node_index IF NOT EXISTS FOR (n:PrimeKGNode) REQUIRE n.node_index IS UNIQUE",
            "CREATE CONSTRAINT primekg_disease_id IF NOT EXISTS FOR (n:PrimeKGDisease) REQUIRE n.mondo_id IS UNIQUE",
            "CREATE CONSTRAINT primekg_gene_id IF NOT EXISTS FOR (n:PrimeKGGene) REQUIRE n.entrez_id IS UNIQUE",
            "CREATE CONSTRAINT primekg_drug_id IF NOT EXISTS FOR (n:PrimeKGDrug) REQUIRE n.drugbank_id IS UNIQUE",
            "CREATE CONSTRAINT primekg_phenotype_id IF NOT EXISTS FOR (n:PrimeKGPhenotype) REQUIRE n.hpo_id IS UNIQUE",
            "CREATE CONSTRAINT primekg_anatomy_id IF NOT EXISTS FOR (n:PrimeKGAnatomy) REQUIRE n.uberon_id IS UNIQUE",
            "CREATE CONSTRAINT primekg_pathway_id IF NOT EXISTS FOR (n:PrimeKGPathway) REQUIRE n.reactome_id IS UNIQUE",

            # Indexes for common queries
            "CREATE INDEX primekg_node_type IF NOT EXISTS FOR (n:PrimeKGNode) ON (n.node_type)",
            "CREATE INDEX primekg_node_name IF NOT EXISTS FOR (n:PrimeKGNode) ON (n.node_name)",
            "CREATE INDEX primekg_disease_name IF NOT EXISTS FOR (n:PrimeKGDisease) ON (n.name)",
            "CREATE INDEX primekg_gene_symbol IF NOT EXISTS FOR (n:PrimeKGGene) ON (n.symbol)",
            "CREATE INDEX primekg_drug_name IF NOT EXISTS FOR (n:PrimeKGDrug) ON (n.name)",

            # Full-text index for clinical descriptions
            """
            CREATE FULLTEXT INDEX primekg_description IF NOT EXISTS
            FOR (n:PrimeKGNode)
            ON EACH [n.description, n.clinical_description, n.name]
            """,
        ]

        try:
            for query in schema_queries:
                await self.neo4j.run(query.strip())

            logger.info("primekg_schema_created")
            return True

        except Exception as e:
            logger.error("primekg_schema_error", error=str(e))
            return False

    async def setup_vector_index(self, dimensions: int = 1536) -> bool:
        """
        Create vector index for PrimeKG embeddings.

        Args:
            dimensions: Embedding dimensions (1536 for OpenAI)
        """
        query = f"""
        CREATE VECTOR INDEX primekg_embedding IF NOT EXISTS
        FOR (n:PrimeKGNode)
        ON n.embedding
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """

        try:
            await self.neo4j.run(query)
            logger.info("primekg_vector_index_created", dimensions=dimensions)
            return True
        except Exception as e:
            logger.error("primekg_vector_index_error", error=str(e))
            return False

    # =========================================================================
    # Node Import
    # =========================================================================

    async def import_nodes(
        self,
        nodes_file: Path | str,
        resume: bool = True,
    ) -> ImportProgress:
        """
        Import nodes from CSV into Neo4j.

        Args:
            nodes_file: Path to nodes.csv
            resume: Whether to resume from last checkpoint

        Returns:
            ImportProgress with results
        """
        self._cancelled = False
        nodes_file = Path(nodes_file)

        # Initialize progress
        progress = ImportProgress(
            phase="nodes",
            started_at=datetime.now(UTC),
        )

        # Count total records
        progress.total_records = self.parser.count_lines(nodes_file)
        progress.total_batches = (progress.total_records + self.batch_size - 1) // self.batch_size

        # Check for resume
        if resume:
            saved_progress = self._load_progress()
            if saved_progress and saved_progress.get("phase") == "nodes":
                progress.resume_from_batch = saved_progress.get("current_batch", 0)
                progress.imported_records = saved_progress.get("imported_records", 0)
                progress.is_resuming = True
                logger.info(
                    "primekg_resuming_nodes",
                    from_batch=progress.resume_from_batch
                )

        logger.info(
            "primekg_importing_nodes",
            total=progress.total_records,
            batches=progress.total_batches,
            resuming=progress.is_resuming
        )

        batch_num = 0
        for batch in self.parser.parse_nodes_batch(nodes_file, self.batch_size):
            batch_num += 1

            # Skip already imported batches if resuming
            if progress.is_resuming and batch_num <= progress.resume_from_batch:
                continue

            if self._cancelled:
                logger.info("primekg_import_cancelled")
                break

            progress.current_batch = batch_num

            # Import batch with retry
            success = await self._import_node_batch(batch, retries=self.max_retries)

            if success:
                progress.imported_records += len(batch)
            else:
                progress.failed_records += len(batch)
                progress.last_error = f"Batch {batch_num} failed after {self.max_retries} retries"

            # Save progress checkpoint
            self._save_progress(progress)
            self._notify_progress(progress)

        progress.completed_at = datetime.now(UTC)
        logger.info(
            "primekg_nodes_imported",
            imported=progress.imported_records,
            failed=progress.failed_records,
            duration_seconds=(progress.completed_at - progress.started_at).total_seconds()
        )

        return progress

    async def _import_node_batch(
        self,
        nodes: list[PrimeKGNode],
        retries: int = 3,
    ) -> bool:
        """Import a batch of nodes into Neo4j."""
        query = """
        UNWIND $nodes AS node
        MERGE (n:PrimeKGNode {node_index: node.node_index})
        SET n.node_id = node.node_id,
            n.node_type = node.node_type,
            n.name = node.node_name,
            n.source = node.node_source,
            n.imported_at = datetime()

        WITH n, node
        CALL apoc.do.case([
            node.node_type = 'disease',
            'SET n:PrimeKGDisease SET n.mondo_id = node.node_id',

            node.node_type = 'gene/protein',
            'SET n:PrimeKGGene SET n.entrez_id = node.node_id SET n.symbol = node.node_name',

            node.node_type = 'drug',
            'SET n:PrimeKGDrug SET n.drugbank_id = node.node_id',

            node.node_type = 'effect/phenotype',
            'SET n:PrimeKGPhenotype SET n.hpo_id = node.node_id',

            node.node_type = 'anatomy',
            'SET n:PrimeKGAnatomy SET n.uberon_id = node.node_id',

            node.node_type = 'pathway',
            'SET n:PrimeKGPathway SET n.reactome_id = node.node_id',

            node.node_type = 'biological_process',
            'SET n:PrimeKGBioProcess SET n.go_id = node.node_id',

            node.node_type = 'molecular_function',
            'SET n:PrimeKGMolFunction SET n.go_id = node.node_id',

            node.node_type = 'cellular_component',
            'SET n:PrimeKGCellComponent SET n.go_id = node.node_id',

            node.node_type = 'exposure',
            'SET n:PrimeKGExposure SET n.exposure_id = node.node_id'
        ],
        '', {n: n, node: node}) YIELD value
        RETURN count(n) as count
        """

        # Fallback query without APOC (simpler but requires multiple passes)
        simple_query = """
        UNWIND $nodes AS node
        MERGE (n:PrimeKGNode {node_index: node.node_index})
        SET n.node_id = node.node_id,
            n.node_type = node.node_type,
            n.name = node.node_name,
            n.source = node.node_source,
            n.imported_at = datetime()
        RETURN count(n) as count
        """

        # Convert to dicts for Neo4j
        node_dicts = [
            {
                "node_index": n.node_index,
                "node_id": n.node_id,
                "node_type": n.node_type.value,
                "node_name": n.node_name,
                "node_source": n.node_source,
            }
            for n in nodes
        ]

        for attempt in range(retries):
            try:
                # Try with APOC first, fallback to simple query
                try:
                    await self.neo4j.run(query, {"nodes": node_dicts})
                except Exception:
                    await self.neo4j.run(simple_query, {"nodes": node_dicts})

                # Add specialized labels in separate query
                await self._add_specialized_labels(node_dicts)

                return True

            except Exception as e:
                logger.warning(
                    "primekg_node_batch_retry",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return False

    async def _add_specialized_labels(self, nodes: list[dict]) -> None:
        """Add specialized labels based on node type."""
        label_queries = {
            "disease": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGDisease",
            "gene/protein": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGGene",
            "drug": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGDrug",
            "effect/phenotype": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGPhenotype",
            "anatomy": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGAnatomy",
            "pathway": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGPathway",
            "biological_process": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGBioProcess",
            "molecular_function": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGMolFunction",
            "cellular_component": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGCellComponent",
            "exposure": "MATCH (n:PrimeKGNode) WHERE n.node_index IN $indices SET n:PrimeKGExposure",
        }

        # Group nodes by type
        by_type: dict[str, list[int]] = {}
        for node in nodes:
            node_type = node["node_type"]
            if node_type not in by_type:
                by_type[node_type] = []
            by_type[node_type].append(node["node_index"])

        # Execute label queries
        for node_type, indices in by_type.items():
            if node_type in label_queries:
                await self.neo4j.run(label_queries[node_type], {"indices": indices})

    # =========================================================================
    # Edge Import
    # =========================================================================

    async def import_edges(
        self,
        edges_file: Path | str,
        resume: bool = True,
    ) -> ImportProgress:
        """
        Import edges from CSV into Neo4j.

        Args:
            edges_file: Path to edges.csv
            resume: Whether to resume from last checkpoint

        Returns:
            ImportProgress with results
        """
        self._cancelled = False
        edges_file = Path(edges_file)

        progress = ImportProgress(
            phase="edges",
            started_at=datetime.now(UTC),
        )

        # Count total records
        progress.total_records = self.parser.count_lines(edges_file)
        progress.total_batches = (progress.total_records + self.edge_batch_size - 1) // self.edge_batch_size

        # Check for resume
        if resume:
            saved_progress = self._load_progress()
            if saved_progress and saved_progress.get("phase") == "edges":
                progress.resume_from_batch = saved_progress.get("current_batch", 0)
                progress.imported_records = saved_progress.get("imported_records", 0)
                progress.is_resuming = True

        logger.info(
            "primekg_importing_edges",
            total=progress.total_records,
            batches=progress.total_batches
        )

        batch_num = 0
        for batch in self.parser.parse_edges_batch(edges_file, self.edge_batch_size):
            batch_num += 1

            if progress.is_resuming and batch_num <= progress.resume_from_batch:
                continue

            if self._cancelled:
                break

            progress.current_batch = batch_num

            success = await self._import_edge_batch(batch, retries=self.max_retries)

            if success:
                progress.imported_records += len(batch)
            else:
                progress.failed_records += len(batch)
                progress.last_error = f"Batch {batch_num} failed"

            self._save_progress(progress)
            self._notify_progress(progress)

        progress.completed_at = datetime.now(UTC)
        logger.info(
            "primekg_edges_imported",
            imported=progress.imported_records,
            failed=progress.failed_records
        )

        return progress

    async def _import_edge_batch(
        self,
        edges: list[PrimeKGEdge],
        retries: int = 3,
    ) -> bool:
        """Import a batch of edges into Neo4j."""
        query = """
        UNWIND $edges AS edge
        MATCH (source:PrimeKGNode {node_index: edge.x_index})
        MATCH (target:PrimeKGNode {node_index: edge.y_index})
        CALL apoc.merge.relationship(
            source,
            edge.rel_type,
            {relation: edge.relation},
            {created_at: datetime()},
            target,
            {}
        ) YIELD rel
        RETURN count(rel) as count
        """

        # Simple fallback without APOC (uses generic RELATED_TO)
        simple_query = """
        UNWIND $edges AS edge
        MATCH (source:PrimeKGNode {node_index: edge.x_index})
        MATCH (target:PrimeKGNode {node_index: edge.y_index})
        MERGE (source)-[r:PRIMEKG_RELATION {relation: edge.relation}]->(target)
        SET r.created_at = datetime()
        RETURN count(r) as count
        """

        # Convert edges to dicts with normalized relationship types
        edge_dicts = [
            {
                "x_index": e.x_index,
                "y_index": e.y_index,
                "relation": e.relation,
                "rel_type": self.RELATIONSHIP_MAP.get(e.relation.lower(), "RELATED_TO"),
            }
            for e in edges
        ]

        for attempt in range(retries):
            try:
                try:
                    await self.neo4j.run(query, {"edges": edge_dicts})
                except Exception:
                    await self.neo4j.run(simple_query, {"edges": edge_dicts})
                return True

            except Exception as e:
                logger.warning(
                    "primekg_edge_batch_retry",
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return False

    # =========================================================================
    # Full Import
    # =========================================================================

    async def import_all(
        self,
        nodes_file: Path | str,
        edges_file: Path | str,
        setup_schema: bool = True,
    ) -> ImportResult:
        """
        Import all PrimeKG data (nodes and edges).

        Args:
            nodes_file: Path to nodes.csv
            edges_file: Path to edges.csv
            setup_schema: Whether to create schema first

        Returns:
            ImportResult with summary
        """
        start_time = datetime.now(UTC)
        result = ImportResult(success=True)

        try:
            # Setup schema
            if setup_schema:
                if not await self.setup_schema():
                    result.success = False
                    result.errors.append("Schema setup failed")
                    return result

            # Import nodes
            nodes_progress = await self.import_nodes(nodes_file)
            result.nodes_imported = nodes_progress.imported_records
            result.nodes_failed = nodes_progress.failed_records

            if nodes_progress.failed_records > 0:
                result.errors.append(f"Node import failures: {nodes_progress.failed_records}")

            # Import edges
            edges_progress = await self.import_edges(edges_file)
            result.edges_imported = edges_progress.imported_records
            result.edges_failed = edges_progress.failed_records

            if edges_progress.failed_records > 0:
                result.errors.append(f"Edge import failures: {edges_progress.failed_records}")

            # Compute final statistics
            result.stats = await self._compute_import_stats()

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error("primekg_import_error", error=str(e))

        result.duration_seconds = (datetime.now(UTC) - start_time).total_seconds()

        logger.info(
            "primekg_import_complete",
            nodes_imported=result.nodes_imported,
            edges_imported=result.edges_imported,
            duration_seconds=result.duration_seconds
        )

        return result

    async def _compute_import_stats(self) -> PrimeKGStats:
        """Compute statistics from imported data."""
        stats = PrimeKGStats(import_timestamp=datetime.now(UTC))

        # Count nodes
        count_query = """
        MATCH (n:PrimeKGNode)
        RETURN n.node_type as type, count(n) as count
        """
        results = await self.neo4j.run(count_query)

        for record in results:
            node_type = record["type"]
            count = record["count"]
            stats.total_nodes += count

            if node_type == "disease":
                stats.disease_count = count
            elif node_type == "gene/protein":
                stats.gene_count = count
            elif node_type == "drug":
                stats.drug_count = count
            elif node_type == "effect/phenotype":
                stats.phenotype_count = count

        # Count edges
        edge_count_query = """
        MATCH ()-[r]->()
        WHERE r.relation IS NOT NULL
        RETURN r.relation as type, count(r) as count
        """
        edge_results = await self.neo4j.run(edge_count_query)

        for record in edge_results:
            rel_type = record["type"]
            count = record["count"]
            stats.total_edges += count
            stats.edge_counts_by_type[rel_type] = count

        return stats

    # =========================================================================
    # Progress Persistence
    # =========================================================================

    def _save_progress(self, progress: ImportProgress) -> None:
        """Save progress to file for resume capability."""
        try:
            self.progress_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "phase": progress.phase,
                "current_batch": progress.current_batch,
                "imported_records": progress.imported_records,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            with open(self.progress_file, "w") as f:
                json.dump(data, f)

        except Exception as e:
            logger.warning("primekg_progress_save_error", error=str(e))

    def _load_progress(self) -> dict | None:
        """Load saved progress for resume."""
        try:
            if self.progress_file.exists():
                with open(self.progress_file) as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("primekg_progress_load_error", error=str(e))
        return None

    def clear_progress(self) -> None:
        """Clear saved progress (start fresh)."""
        try:
            if self.progress_file.exists():
                self.progress_file.unlink()
        except Exception as e:
            logger.warning("primekg_progress_clear_error", error=str(e))
