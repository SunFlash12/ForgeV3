"""
HPO Ontology Service

Parses and manages the Human Phenotype Ontology hierarchy.
Supports loading from OBO files, JSON, or database.
"""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import structlog

from .models import HPOHierarchy, HPOTerm

logger = structlog.get_logger(__name__)


@dataclass
class HPODownloadProgress:
    """Progress tracking for HPO data download."""
    file_name: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    status: str = "pending"
    error: str | None = None


class HPOOntologyService:
    """
    Service for HPO ontology management.

    Features:
    - Load HPO from OBO format or JSON
    - Build and cache hierarchy
    - Term lookup and search
    - Semantic similarity calculations
    """

    # Official HPO download URLs
    HPO_OBO_URL = "http://purl.obolibrary.org/obo/hp.obo"
    HPO_JSON_URL = "https://raw.githubusercontent.com/obophenotype/human-phenotype-ontology/master/hp.json"
    HPO_ANNOTATIONS_URL = "http://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa"

    def __init__(
        self,
        data_dir: Path | str = "./data/hpo",
        neo4j_client=None,
    ):
        """
        Initialize the HPO ontology service.

        Args:
            data_dir: Directory for HPO data files
            neo4j_client: Optional Neo4j client for database storage
        """
        self.data_dir = Path(data_dir)
        self.neo4j = neo4j_client

        # In-memory cache
        self._hierarchy: HPOHierarchy | None = None
        self._term_index: dict[str, HPOTerm] = {}
        self._name_index: dict[str, str] = {}  # name -> hpo_id
        self._synonym_index: dict[str, str] = {}  # synonym -> hpo_id
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if ontology is loaded."""
        return self._loaded

    @property
    def term_count(self) -> int:
        """Get number of loaded terms."""
        return len(self._term_index)

    async def load(self, force_download: bool = False) -> bool:
        """
        Load HPO ontology data.

        Args:
            force_download: Force re-download even if files exist

        Returns:
            True if loaded successfully
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Try to load from local files first
        obo_file = self.data_dir / "hp.obo"
        json_file = self.data_dir / "hp.json"

        if json_file.exists() and not force_download:
            logger.info("hpo_loading_from_json", path=str(json_file))
            return await self._load_from_json(json_file)

        if obo_file.exists() and not force_download:
            logger.info("hpo_loading_from_obo", path=str(obo_file))
            return await self._load_from_obo(obo_file)

        # Download if not available
        logger.info("hpo_downloading")
        try:
            await self._download_hpo_files()
            if json_file.exists():
                return await self._load_from_json(json_file)
            elif obo_file.exists():
                return await self._load_from_obo(obo_file)
        except Exception as e:
            logger.error("hpo_download_failed", error=str(e))

        return False

    async def _download_hpo_files(self) -> None:
        """Download HPO data files."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Try JSON first (faster to parse)
            try:
                response = await client.get(self.HPO_JSON_URL, follow_redirects=True)
                if response.status_code == 200:
                    json_file = self.data_dir / "hp.json"
                    json_file.write_bytes(response.content)
                    logger.info("hpo_json_downloaded", size=len(response.content))
                    return
            except Exception as e:
                logger.warning("hpo_json_download_failed", error=str(e))

            # Fall back to OBO
            response = await client.get(self.HPO_OBO_URL, follow_redirects=True)
            if response.status_code == 200:
                obo_file = self.data_dir / "hp.obo"
                obo_file.write_bytes(response.content)
                logger.info("hpo_obo_downloaded", size=len(response.content))

    async def _load_from_json(self, path: Path) -> bool:
        """Load HPO from JSON format."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # Parse JSON-LD format
            terms = {}
            graphs = data.get("graphs", [data])

            for graph in graphs:
                nodes = graph.get("nodes", [])
                for node in nodes:
                    term = self._parse_json_node(node)
                    if term:
                        terms[term.hpo_id] = term

                # Parse edges for hierarchy
                edges = graph.get("edges", [])
                for edge in edges:
                    self._process_json_edge(edge, terms)

            self._term_index = terms
            self._build_indices()
            self._build_hierarchy()
            self._loaded = True

            logger.info("hpo_loaded_from_json", term_count=len(terms))
            return True

        except Exception as e:
            logger.error("hpo_json_parse_error", error=str(e))
            return False

    def _parse_json_node(self, node: dict) -> HPOTerm | None:
        """Parse a JSON node into an HPOTerm."""
        node_id = node.get("id", "")
        if not node_id.startswith("http://purl.obolibrary.org/obo/HP_"):
            return None

        # Extract HPO ID (HP:0001234 format)
        hpo_id = node_id.replace("http://purl.obolibrary.org/obo/HP_", "HP:")

        # Get metadata
        meta = node.get("meta", {})
        is_obsolete = meta.get("deprecated", False)

        # Get synonyms
        synonyms = []
        for syn in meta.get("synonyms", []):
            if isinstance(syn, dict):
                synonyms.append(syn.get("val", ""))
            elif isinstance(syn, str):
                synonyms.append(syn)

        return HPOTerm(
            hpo_id=hpo_id,
            name=node.get("lbl", "Unknown"),
            definition=meta.get("definition", {}).get("val") if isinstance(meta.get("definition"), dict) else None,
            synonyms=[s for s in synonyms if s],
            is_obsolete=is_obsolete,
            xrefs=meta.get("xrefs", []) if isinstance(meta.get("xrefs"), list) else [],
        )

    def _process_json_edge(self, edge: dict, terms: dict[str, HPOTerm]) -> None:
        """Process a JSON edge to build hierarchy."""
        subj = edge.get("sub", "")
        obj = edge.get("obj", "")
        pred = edge.get("pred", "")

        if pred != "is_a":
            return

        # Convert to HPO IDs
        if "HP_" in subj:
            child_id = "HP:" + subj.split("HP_")[-1]
        else:
            return
        if "HP_" in obj:
            parent_id = "HP:" + obj.split("HP_")[-1]
        else:
            return

        # Update parent-child relationships
        if child_id in terms:
            terms[child_id].parents.append(parent_id)
        if parent_id in terms:
            terms[parent_id].children.append(child_id)

    async def _load_from_obo(self, path: Path) -> bool:
        """Load HPO from OBO format."""
        try:
            content = path.read_text(encoding="utf-8")
            terms = {}

            # Parse OBO format
            current_term: dict[str, Any] | None = None

            for line in content.split("\n"):
                line = line.strip()

                if line == "[Term]":
                    if current_term and current_term.get("id"):
                        term = self._obo_dict_to_term(current_term)
                        if term:
                            terms[term.hpo_id] = term
                    current_term = {}

                elif line == "[Typedef]":
                    if current_term and current_term.get("id"):
                        term = self._obo_dict_to_term(current_term)
                        if term:
                            terms[term.hpo_id] = term
                    current_term = None

                elif current_term is not None and ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip()

                    if key == "id":
                        current_term["id"] = value
                    elif key == "name":
                        current_term["name"] = value
                    elif key == "def":
                        # Parse definition (may have quotes and xrefs)
                        match = re.match(r'"([^"]*)"', value)
                        if match:
                            current_term["def"] = match.group(1)
                    elif key == "synonym":
                        if "synonyms" not in current_term:
                            current_term["synonyms"] = []
                        match = re.match(r'"([^"]*)"', value)
                        if match:
                            current_term["synonyms"].append(match.group(1))
                    elif key == "is_a":
                        if "parents" not in current_term:
                            current_term["parents"] = []
                        # Extract just the HPO ID
                        parent_id = value.split("!")[0].strip()
                        current_term["parents"].append(parent_id)
                    elif key == "is_obsolete":
                        current_term["is_obsolete"] = value.lower() == "true"
                    elif key == "replaced_by":
                        current_term["replaced_by"] = value
                    elif key == "xref":
                        if "xrefs" not in current_term:
                            current_term["xrefs"] = []
                        current_term["xrefs"].append(value)

            # Don't forget the last term
            if current_term and current_term.get("id"):
                term = self._obo_dict_to_term(current_term)
                if term:
                    terms[term.hpo_id] = term

            # Build child relationships from parent relationships
            for term in terms.values():
                for parent_id in term.parents:
                    if parent_id in terms:
                        terms[parent_id].children.append(term.hpo_id)

            self._term_index = terms
            self._build_indices()
            self._build_hierarchy()
            self._loaded = True

            logger.info("hpo_loaded_from_obo", term_count=len(terms))
            return True

        except Exception as e:
            logger.error("hpo_obo_parse_error", error=str(e))
            return False

    def _obo_dict_to_term(self, data: dict) -> HPOTerm | None:
        """Convert parsed OBO dict to HPOTerm."""
        hpo_id = data.get("id", "")
        if not hpo_id.startswith("HP:"):
            return None

        return HPOTerm(
            hpo_id=hpo_id,
            name=data.get("name", "Unknown"),
            definition=data.get("def"),
            synonyms=data.get("synonyms", []),
            parents=data.get("parents", []),
            is_obsolete=data.get("is_obsolete", False),
            replaced_by=data.get("replaced_by"),
            xrefs=data.get("xrefs", []),
        )

    def _build_indices(self) -> None:
        """Build lookup indices for fast search."""
        self._name_index.clear()
        self._synonym_index.clear()

        for term in self._term_index.values():
            # Index by lowercase name
            name_lower = term.name.lower()
            self._name_index[name_lower] = term.hpo_id

            # Index by synonyms
            for syn in term.synonyms:
                syn_lower = syn.lower()
                if syn_lower not in self._synonym_index:
                    self._synonym_index[syn_lower] = term.hpo_id

    def _build_hierarchy(self) -> None:
        """Build HPOHierarchy for efficient traversal."""
        hierarchy = HPOHierarchy()
        hierarchy.terms = self._term_index

        for term in self._term_index.values():
            # Parent map
            if term.hpo_id not in hierarchy.parent_map:
                hierarchy.parent_map[term.hpo_id] = set()
            hierarchy.parent_map[term.hpo_id].update(term.parents)

            # Child map
            if term.hpo_id not in hierarchy.child_map:
                hierarchy.child_map[term.hpo_id] = set()
            hierarchy.child_map[term.hpo_id].update(term.children)

        self._hierarchy = hierarchy

    # =========================================================================
    # Public API
    # =========================================================================

    def get_term(self, hpo_id: str) -> HPOTerm | None:
        """Get an HPO term by ID."""
        return self._term_index.get(hpo_id)

    def get_term_by_name(self, name: str) -> HPOTerm | None:
        """Get an HPO term by exact name match."""
        hpo_id = self._name_index.get(name.lower())
        if hpo_id:
            return self._term_index.get(hpo_id)
        return None

    def search_terms(
        self,
        query: str,
        limit: int = 20,
        include_obsolete: bool = False,
    ) -> list[HPOTerm]:
        """
        Search HPO terms by name or synonym.

        Args:
            query: Search query
            limit: Maximum results
            include_obsolete: Include obsolete terms

        Returns:
            List of matching terms, sorted by relevance
        """
        query_lower = query.lower()
        results = []

        # Exact match has highest priority
        exact_id = self._name_index.get(query_lower)
        if exact_id:
            term = self._term_index.get(exact_id)
            if term and (include_obsolete or not term.is_obsolete):
                results.append((term, 1.0))

        # Check synonyms
        syn_id = self._synonym_index.get(query_lower)
        if syn_id and syn_id != exact_id:
            term = self._term_index.get(syn_id)
            if term and (include_obsolete or not term.is_obsolete):
                results.append((term, 0.95))

        # Partial matches
        for _hpo_id, term in self._term_index.items():
            if not include_obsolete and term.is_obsolete:
                continue

            # Skip if already matched
            if term in [r[0] for r in results]:
                continue

            # Name contains query
            if query_lower in term.name.lower():
                score = len(query_lower) / len(term.name)
                results.append((term, score * 0.9))
                continue

            # Synonym contains query
            for syn in term.synonyms:
                if query_lower in syn.lower():
                    score = len(query_lower) / len(syn)
                    results.append((term, score * 0.85))
                    break

        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return [term for term, _ in results[:limit]]

    def get_ancestors(
        self,
        hpo_id: str,
        include_self: bool = False,
    ) -> set[str]:
        """Get all ancestor HPO IDs."""
        if not self._hierarchy:
            return set()
        return self._hierarchy.get_ancestors(hpo_id, include_self)

    def get_descendants(
        self,
        hpo_id: str,
        include_self: bool = False,
    ) -> set[str]:
        """Get all descendant HPO IDs."""
        if not self._hierarchy:
            return set()
        return self._hierarchy.get_descendants(hpo_id, include_self)

    def get_semantic_similarity(self, term1: str, term2: str) -> float:
        """Calculate semantic similarity between two HPO terms."""
        if not self._hierarchy:
            return 0.0
        return self._hierarchy.semantic_similarity(term1, term2)

    def get_category(self, hpo_id: str) -> str | None:
        """
        Get the top-level category for an HPO term.

        Returns one of the main HPO categories like:
        - Abnormality of the nervous system
        - Abnormality of the cardiovascular system
        - etc.
        """
        if not self._hierarchy:
            return None

        # Walk up to find the term just below the root
        ancestors = self.get_ancestors(hpo_id)
        if not ancestors:
            return None

        # Find the ancestor with the root as parent
        root = "HP:0000001"  # Phenotypic abnormality
        for ancestor in ancestors:
            term = self.get_term(ancestor)
            if term and root in term.parents:
                return term.name

        return None

    def iter_terms(self) -> Iterator[HPOTerm]:
        """Iterate over all HPO terms."""
        yield from self._term_index.values()


# =============================================================================
# Factory Function
# =============================================================================

def create_hpo_ontology_service(
    data_dir: str = "./data/hpo",
    neo4j_client=None,
) -> HPOOntologyService:
    """Create an HPO ontology service instance."""
    return HPOOntologyService(
        data_dir=data_dir,
        neo4j_client=neo4j_client,
    )
