"""
PrimeKG CSV Parser

Parses PrimeKG CSV files (nodes.csv, edges.csv, kg.csv) into
structured data models for import into Neo4j.

Handles:
- Large file streaming (4M+ edges)
- Data validation
- Progress tracking
- Memory-efficient batch processing
"""

import csv
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from .models import (
    PrimeKGDisease,
    PrimeKGDrug,
    PrimeKGEdge,
    PrimeKGGene,
    PrimeKGNode,
    PrimeKGNodeType,
    PrimeKGPhenotype,
    PrimeKGStats,
)

logger = structlog.get_logger(__name__)


@dataclass
class ParseProgress:
    """Progress information for parsing operations."""

    file_name: str
    total_lines: int = 0
    processed_lines: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def progress_percent(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return (self.processed_lines / self.total_lines) * 100

    @property
    def error_rate(self) -> float:
        total = self.valid_records + self.invalid_records
        if total == 0:
            return 0.0
        return self.invalid_records / total


class PrimeKGParser:
    """
    Parser for PrimeKG CSV files.

    Supports streaming for memory-efficient processing of large files.
    """

    # Column mappings for nodes.csv
    NODE_COLUMNS = {
        "node_index": "node_index",
        "node_id": "node_id",
        "node_type": "node_type",
        "node_name": "node_name",
        "node_source": "node_source",
    }

    # Column mappings for edges.csv (full format)
    EDGE_COLUMNS = {
        "relation": "relation",
        "display_relation": "display_relation",
        "x_index": "x_index",
        "x_id": "x_id",
        "x_type": "x_type",
        "x_name": "x_name",
        "x_source": "x_source",
        "y_index": "y_index",
        "y_id": "y_id",
        "y_type": "y_type",
        "y_name": "y_name",
        "y_source": "y_source",
    }

    # Node type mapping from PrimeKG strings to enum
    NODE_TYPE_MAP = {
        "disease": PrimeKGNodeType.DISEASE,
        "gene/protein": PrimeKGNodeType.GENE_PROTEIN,
        "drug": PrimeKGNodeType.DRUG,
        "effect/phenotype": PrimeKGNodeType.PHENOTYPE,
        "anatomy": PrimeKGNodeType.ANATOMY,
        "pathway": PrimeKGNodeType.PATHWAY,
        "biological_process": PrimeKGNodeType.BIOLOGICAL_PROCESS,
        "molecular_function": PrimeKGNodeType.MOLECULAR_FUNCTION,
        "cellular_component": PrimeKGNodeType.CELLULAR_COMPONENT,
        "exposure": PrimeKGNodeType.EXPOSURE,
    }

    def __init__(
        self,
        batch_size: int = 1000,
        max_errors: int = 100,
    ):
        """
        Initialize the parser.

        Args:
            batch_size: Number of records per batch for streaming
            max_errors: Maximum errors before aborting
        """
        self.batch_size = batch_size
        self.max_errors = max_errors
        self._progress_callbacks: list[Callable[[ParseProgress], None]] = []

    def add_progress_callback(self, callback: Callable[[ParseProgress], None]) -> None:
        """Add a callback to receive progress updates."""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, progress: ParseProgress) -> None:
        """Notify all callbacks of progress update."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:  # Intentional broad catch: callback error must not crash parser
                logger.warning("parser_callback_error", error=str(e))

    def count_lines(self, file_path: Path) -> int:
        """Count lines in a file efficiently."""
        count = 0
        with open(file_path, "rb") as f:
            for _ in f:
                count += 1
        return count - 1  # Subtract header

    # =========================================================================
    # Node Parsing
    # =========================================================================

    def parse_nodes(
        self,
        file_path: Path | str,
        progress_callback: Callable[[ParseProgress], None] | None = None,
    ) -> Iterator[PrimeKGNode]:
        """
        Parse nodes.csv and yield PrimeKGNode objects.

        Args:
            file_path: Path to nodes.csv
            progress_callback: Optional callback for progress updates

        Yields:
            PrimeKGNode objects
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Nodes file not found: {file_path}")

        progress = ParseProgress(
            file_name=file_path.name,
            started_at=datetime.now(UTC),
        )

        # Count total lines for progress
        progress.total_lines = self.count_lines(file_path)
        logger.info("primekg_parsing_nodes", total_lines=progress.total_lines)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                progress.processed_lines += 1

                try:
                    node = self._parse_node_row(row)
                    progress.valid_records += 1
                    yield node

                except (ValueError, KeyError, TypeError) as e:
                    progress.invalid_records += 1
                    error_msg = f"Line {progress.processed_lines}: {str(e)}"
                    progress.errors.append(error_msg)

                    if len(progress.errors) >= self.max_errors:
                        logger.error("primekg_max_errors_reached", errors=len(progress.errors))
                        break

                # Progress update every 10000 records
                if progress.processed_lines % 10000 == 0:
                    if progress_callback:
                        progress_callback(progress)
                    self._notify_progress(progress)

        progress.completed_at = datetime.now(UTC)
        if progress_callback:
            progress_callback(progress)
        self._notify_progress(progress)

        if progress.started_at is not None:
            duration = progress.completed_at - progress.started_at
        else:
            duration = timedelta()
        logger.info(
            "primekg_nodes_parsed",
            valid=progress.valid_records,
            invalid=progress.invalid_records,
            duration_seconds=duration.total_seconds(),
        )

    def _parse_node_row(self, row: dict[str, Any]) -> PrimeKGNode:
        """Parse a single node row into a PrimeKGNode."""
        # Normalize column names (handle variations)
        node_index = int(row.get("node_index", row.get("index", 0)))
        node_id = row.get("node_id", row.get("id", ""))
        node_type_str = row.get("node_type", row.get("type", "")).lower()
        node_name = row.get("node_name", row.get("name", ""))
        node_source = row.get("node_source", row.get("source", ""))

        # Map node type
        node_type = self.NODE_TYPE_MAP.get(node_type_str)
        if node_type is None:
            raise ValueError(f"Unknown node type: {node_type_str}")

        return PrimeKGNode(
            node_index=node_index,
            node_id=node_id,
            node_type=node_type,
            node_name=node_name,
            node_source=node_source,
        )

    def parse_nodes_batch(
        self,
        file_path: Path | str,
        batch_size: int | None = None,
    ) -> Iterator[list[PrimeKGNode]]:
        """
        Parse nodes in batches for efficient database import.

        Args:
            file_path: Path to nodes.csv
            batch_size: Override default batch size

        Yields:
            Lists of PrimeKGNode objects (batches)
        """
        batch_size = batch_size or self.batch_size
        batch: list[PrimeKGNode] = []

        for node in self.parse_nodes(file_path):
            batch.append(node)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        # Yield remaining
        if batch:
            yield batch

    # =========================================================================
    # Edge Parsing
    # =========================================================================

    def parse_edges(
        self,
        file_path: Path | str,
        progress_callback: Callable[[ParseProgress], None] | None = None,
    ) -> Iterator[PrimeKGEdge]:
        """
        Parse edges.csv and yield PrimeKGEdge objects.

        Args:
            file_path: Path to edges.csv
            progress_callback: Optional callback for progress updates

        Yields:
            PrimeKGEdge objects
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Edges file not found: {file_path}")

        progress = ParseProgress(
            file_name=file_path.name,
            started_at=datetime.now(UTC),
        )

        # Count total lines for progress
        progress.total_lines = self.count_lines(file_path)
        logger.info("primekg_parsing_edges", total_lines=progress.total_lines)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                progress.processed_lines += 1

                try:
                    edge = self._parse_edge_row(row)
                    progress.valid_records += 1
                    yield edge

                except (ValueError, KeyError, TypeError) as e:
                    progress.invalid_records += 1
                    error_msg = f"Line {progress.processed_lines}: {str(e)}"
                    progress.errors.append(error_msg)

                    if len(progress.errors) >= self.max_errors:
                        logger.error("primekg_max_errors_reached", errors=len(progress.errors))
                        break

                # Progress update every 100000 records (edges are large)
                if progress.processed_lines % 100000 == 0:
                    if progress_callback:
                        progress_callback(progress)
                    self._notify_progress(progress)

        progress.completed_at = datetime.now(UTC)
        if progress_callback:
            progress_callback(progress)
        self._notify_progress(progress)

        if progress.started_at is not None:
            duration = progress.completed_at - progress.started_at
        else:
            duration = timedelta()
        logger.info(
            "primekg_edges_parsed",
            valid=progress.valid_records,
            invalid=progress.invalid_records,
            duration_seconds=duration.total_seconds(),
        )

    def _parse_edge_row(self, row: dict[str, Any]) -> PrimeKGEdge:
        """Parse a single edge row into a PrimeKGEdge."""
        return PrimeKGEdge(
            relation=row.get("relation", row.get("display_relation", "")),
            x_index=int(row.get("x_index", 0)),
            y_index=int(row.get("y_index", 0)),
            x_id=row.get("x_id", ""),
            x_type=row.get("x_type", ""),
            x_name=row.get("x_name", ""),
            x_source=row.get("x_source", ""),
            y_id=row.get("y_id", ""),
            y_type=row.get("y_type", ""),
            y_name=row.get("y_name", ""),
            y_source=row.get("y_source", ""),
        )

    def parse_edges_batch(
        self,
        file_path: Path | str,
        batch_size: int | None = None,
    ) -> Iterator[list[PrimeKGEdge]]:
        """
        Parse edges in batches for efficient database import.

        Args:
            file_path: Path to edges.csv
            batch_size: Override default batch size

        Yields:
            Lists of PrimeKGEdge objects (batches)
        """
        batch_size = batch_size or self.batch_size
        batch: list[PrimeKGEdge] = []

        for edge in self.parse_edges(file_path):
            batch.append(edge)

            if len(batch) >= batch_size:
                yield batch
                batch = []

        # Yield remaining
        if batch:
            yield batch

    # =========================================================================
    # KG.csv Parsing (Alternative Format)
    # =========================================================================

    def parse_kg_triplets(
        self,
        file_path: Path | str,
        progress_callback: Callable[[ParseProgress], None] | None = None,
    ) -> Iterator[tuple[str, str, str]]:
        """
        Parse kg.csv (triplet format: head, relation, tail).

        This is an alternative to nodes.csv + edges.csv.

        Args:
            file_path: Path to kg.csv

        Yields:
            Tuples of (head_id, relation, tail_id)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"KG file not found: {file_path}")

        progress = ParseProgress(
            file_name=file_path.name,
            started_at=datetime.now(UTC),
        )

        progress.total_lines = self.count_lines(file_path)
        logger.info("primekg_parsing_kg", total_lines=progress.total_lines)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header

            for row in reader:
                progress.processed_lines += 1

                try:
                    if len(row) >= 3:
                        head, relation, tail = row[0], row[1], row[2]
                        progress.valid_records += 1
                        yield (head, relation, tail)
                    else:
                        raise ValueError(f"Invalid row format: {row}")

                except (ValueError, KeyError, TypeError, IndexError) as e:
                    progress.invalid_records += 1
                    progress.errors.append(str(e))

                if progress.processed_lines % 500000 == 0:
                    if progress_callback:
                        progress_callback(progress)
                    self._notify_progress(progress)

        progress.completed_at = datetime.now(UTC)
        if progress_callback:
            progress_callback(progress)
        self._notify_progress(progress)

    # =========================================================================
    # Statistics and Validation
    # =========================================================================

    def compute_statistics(
        self,
        nodes_file: Path | str,
        edges_file: Path | str,
    ) -> PrimeKGStats:
        """
        Compute statistics about the PrimeKG data.

        Args:
            nodes_file: Path to nodes.csv
            edges_file: Path to edges.csv

        Returns:
            PrimeKGStats with counts and metadata
        """
        stats = PrimeKGStats(
            import_timestamp=datetime.now(UTC),
        )

        # Count nodes by type
        node_type_counts: defaultdict[str, int] = defaultdict(int)
        for node in self.parse_nodes(nodes_file):
            stats.total_nodes += 1
            node_type_counts[node.node_type.value] += 1

        stats.disease_count = node_type_counts.get("disease", 0)
        stats.gene_count = node_type_counts.get("gene/protein", 0)
        stats.drug_count = node_type_counts.get("drug", 0)
        stats.phenotype_count = node_type_counts.get("effect/phenotype", 0)
        stats.anatomy_count = node_type_counts.get("anatomy", 0)
        stats.pathway_count = node_type_counts.get("pathway", 0)
        stats.bioprocess_count = node_type_counts.get("biological_process", 0)
        stats.molfunction_count = node_type_counts.get("molecular_function", 0)
        stats.cellcomponent_count = node_type_counts.get("cellular_component", 0)
        stats.exposure_count = node_type_counts.get("exposure", 0)

        # Count edges by type
        edge_type_counts: defaultdict[str, int] = defaultdict(int)
        for edge in self.parse_edges(edges_file):
            stats.total_edges += 1
            edge_type_counts[edge.relation] += 1

        stats.edge_counts_by_type = dict(edge_type_counts)

        logger.info(
            "primekg_statistics_computed",
            total_nodes=stats.total_nodes,
            total_edges=stats.total_edges,
            node_types=len(node_type_counts),
            edge_types=len(edge_type_counts),
        )

        return stats

    def validate_referential_integrity(
        self,
        nodes_file: Path | str,
        edges_file: Path | str,
    ) -> dict[str, Any]:
        """
        Validate that all edge references point to valid nodes.

        Args:
            nodes_file: Path to nodes.csv
            edges_file: Path to edges.csv

        Returns:
            Validation results
        """
        # Build set of valid node indices
        valid_indices = set()
        for node in self.parse_nodes(nodes_file):
            valid_indices.add(node.node_index)

        logger.info("primekg_validation_nodes_loaded", count=len(valid_indices))

        # Check edge references
        invalid_edges = []
        total_edges = 0

        for edge in self.parse_edges(edges_file):
            total_edges += 1

            if edge.x_index not in valid_indices:
                invalid_edges.append(
                    {
                        "edge": f"{edge.x_index} -> {edge.y_index}",
                        "error": f"Invalid x_index: {edge.x_index}",
                    }
                )

            if edge.y_index not in valid_indices:
                invalid_edges.append(
                    {
                        "edge": f"{edge.x_index} -> {edge.y_index}",
                        "error": f"Invalid y_index: {edge.y_index}",
                    }
                )

            if len(invalid_edges) >= 100:
                break  # Limit error collection

        is_valid = len(invalid_edges) == 0

        result = {
            "is_valid": is_valid,
            "total_nodes": len(valid_indices),
            "total_edges": total_edges,
            "invalid_edge_count": len(invalid_edges),
            "sample_errors": invalid_edges[:10],
        }

        if is_valid:
            logger.info("primekg_validation_passed", **result)
        else:
            logger.warning("primekg_validation_failed", **result)

        return result


# =============================================================================
# Specialized Node Parsers
# =============================================================================


class SpecializedNodeParser:
    """
    Parser that creates specialized node types (Disease, Gene, Drug, etc.)
    from generic PrimeKGNode objects.
    """

    @staticmethod
    def to_disease(node: PrimeKGNode) -> PrimeKGDisease:
        """Convert generic node to Disease node."""
        if node.node_type != PrimeKGNodeType.DISEASE:
            raise ValueError(f"Node is not a disease: {node.node_type}")

        return PrimeKGDisease(
            node_index=node.node_index,
            node_id=node.node_id,
            node_type=node.node_type,
            node_name=node.node_name,
            node_source=node.node_source,
            mondo_id=node.node_id,  # MONDO ID is the node_id
        )

    @staticmethod
    def to_gene(node: PrimeKGNode) -> PrimeKGGene:
        """Convert generic node to Gene node."""
        if node.node_type != PrimeKGNodeType.GENE_PROTEIN:
            raise ValueError(f"Node is not a gene/protein: {node.node_type}")

        return PrimeKGGene(
            node_index=node.node_index,
            node_id=node.node_id,
            node_type=node.node_type,
            node_name=node.node_name,
            node_source=node.node_source,
            entrez_id=node.node_id,
            symbol=node.node_name,
        )

    @staticmethod
    def to_drug(node: PrimeKGNode) -> PrimeKGDrug:
        """Convert generic node to Drug node."""
        if node.node_type != PrimeKGNodeType.DRUG:
            raise ValueError(f"Node is not a drug: {node.node_type}")

        return PrimeKGDrug(
            node_index=node.node_index,
            node_id=node.node_id,
            node_type=node.node_type,
            node_name=node.node_name,
            node_source=node.node_source,
            drugbank_id=node.node_id,
        )

    @staticmethod
    def to_phenotype(node: PrimeKGNode) -> PrimeKGPhenotype:
        """Convert generic node to Phenotype node."""
        if node.node_type != PrimeKGNodeType.PHENOTYPE:
            raise ValueError(f"Node is not a phenotype: {node.node_type}")

        return PrimeKGPhenotype(
            node_index=node.node_index,
            node_id=node.node_id,
            node_type=node.node_type,
            node_name=node.node_name,
            node_source=node.node_source,
            hpo_id=node.node_id,
        )
