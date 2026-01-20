"""
Forge Cascade V2 - PrimeKG Biomedical Knowledge Graph Routes

Provides endpoints for:
- Differential diagnosis generation
- Phenotype-to-disease mapping
- Drug-disease interactions
- Gene-disease associations
- Semantic search on clinical descriptions
- PrimeKG data management
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from forge.api.dependencies import (
    ActiveUserDep,
    AuditRepoDep,
    CorrelationIdDep,
    DbClientDep,
    OverlayManagerDep,
    TrustedUserDep,
)
from forge.overlays.base import OverlayContext

router = APIRouter()


# =============================================================================
# Request/Response Models - Diagnosis
# =============================================================================

class DifferentialDiagnosisRequest(BaseModel):
    """Request for differential diagnosis generation."""
    phenotypes: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of HPO term IDs (e.g., HP:0001250)"
    )
    genes: list[str] = Field(
        default=[],
        max_length=20,
        description="Optional list of gene symbols or Entrez IDs"
    )
    medications: list[str] = Field(
        default=[],
        max_length=30,
        description="Optional list of current medications (DrugBank IDs or names)"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Max diagnoses to return")


class DiagnosisCandidate(BaseModel):
    """A candidate diagnosis with supporting evidence."""
    disease_id: str
    disease_name: str
    mondo_id: str | None
    description: str | None
    matched_phenotypes: list[str]
    match_count: int
    total_phenotypes: int
    recall: float
    precision: float
    score: float
    gene_support: bool = False


class DifferentialDiagnosisResponse(BaseModel):
    """Differential diagnosis response."""
    input_phenotypes: list[str]
    input_genes: list[str]
    input_medications: list[str]
    differential: list[DiagnosisCandidate]
    total_candidates: int
    execution_time_ms: float


# =============================================================================
# Request/Response Models - Phenotype Search
# =============================================================================

class PhenotypeSearchRequest(BaseModel):
    """Request for phenotype-to-disease mapping."""
    phenotypes: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of HPO term IDs"
    )
    limit: int = Field(default=20, ge=1, le=100)


class PhenotypeSearchResponse(BaseModel):
    """Phenotype search response."""
    input_phenotypes: list[str]
    results: list[DiagnosisCandidate]
    execution_time_ms: float


# =============================================================================
# Request/Response Models - Drug Information
# =============================================================================

class DrugDiseaseRequest(BaseModel):
    """Request for drug-disease relationship lookup."""
    disease_id: str = Field(..., description="MONDO ID or PrimeKG node ID")


class DrugInfo(BaseModel):
    """Drug information."""
    drug_id: str
    name: str
    relation: str


class DrugDiseaseResponse(BaseModel):
    """Drug-disease relationship response."""
    disease_id: str
    disease_name: str | None
    indications: list[DrugInfo]
    contraindications: list[DrugInfo]
    off_label: list[DrugInfo]


# =============================================================================
# Request/Response Models - Gene Association
# =============================================================================

class GeneAssociationRequest(BaseModel):
    """Request for gene-disease association lookup."""
    gene_id: str | None = Field(default=None, description="Entrez ID or gene symbol")
    disease_id: str | None = Field(default=None, description="MONDO ID")
    limit: int = Field(default=50, ge=1, le=200)


class GeneAssociation(BaseModel):
    """Gene-disease association."""
    gene_symbol: str
    gene_id: str
    disease_name: str
    disease_id: str
    relation: str


class GeneAssociationResponse(BaseModel):
    """Gene association response."""
    query: dict[str, str | None]
    associations: list[GeneAssociation]


# =============================================================================
# Request/Response Models - Semantic Search
# =============================================================================

class SemanticSearchRequest(BaseModel):
    """Request for semantic search on clinical descriptions."""
    query: str = Field(..., min_length=3, max_length=500, description="Search query text")
    node_type: str | None = Field(
        default=None,
        description="Filter by node type: disease, gene/protein, drug, effect/phenotype"
    )
    limit: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.7, ge=0.0, le=1.0)


class SemanticSearchResult(BaseModel):
    """Semantic search result."""
    node_id: str
    name: str
    type: str
    description: str | None
    score: float


class SemanticSearchResponse(BaseModel):
    """Semantic search response."""
    query: str
    results: list[SemanticSearchResult]
    execution_time_ms: float


# =============================================================================
# Request/Response Models - Discriminating Phenotypes
# =============================================================================

class DiscriminatingPhenotypesRequest(BaseModel):
    """Request for phenotypes that distinguish between diseases."""
    disease_a: str = Field(..., description="First disease MONDO ID")
    disease_b: str = Field(..., description="Second disease MONDO ID")
    already_present: list[str] = Field(
        default=[],
        description="HPO IDs of phenotypes already known to be present"
    )


class DiscriminatingPhenotype(BaseModel):
    """A phenotype that discriminates between diseases."""
    hpo_id: str
    name: str
    discriminates: str  # 'supports_a' or 'supports_b'
    question: str  # Natural language question to ask patient


class DiscriminatingPhenotypesResponse(BaseModel):
    """Discriminating phenotypes response."""
    disease_a: str
    disease_b: str
    phenotypes: list[DiscriminatingPhenotype]


# =============================================================================
# Request/Response Models - Disease Details
# =============================================================================

class DiseaseDetailsResponse(BaseModel):
    """Complete disease information."""
    node_id: str
    mondo_id: str | None
    name: str
    description: str | None
    phenotypes: list[dict[str, str]]
    genes: list[dict[str, str]]
    treatments: list[dict[str, str]]


# =============================================================================
# Request/Response Models - Drug Interactions
# =============================================================================

class DrugInteractionRequest(BaseModel):
    """Request to check drug-disease interactions."""
    drugs: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of DrugBank IDs or drug names"
    )
    diseases: list[str] = Field(
        default=[],
        description="List of MONDO IDs to check against"
    )


class DrugInteraction(BaseModel):
    """Drug interaction information."""
    drug_name: str
    drug_id: str
    contraindications: list[dict[str, str]]


class DrugInteractionResponse(BaseModel):
    """Drug interaction check response."""
    drugs: list[str]
    diseases: list[str]
    interactions: list[DrugInteraction]
    has_contraindications: bool


# =============================================================================
# Request/Response Models - PrimeKG Stats
# =============================================================================

class PrimeKGStatsResponse(BaseModel):
    """PrimeKG data statistics."""
    disease_count: int
    gene_count: int
    drug_count: int
    phenotype_count: int
    pathway_count: int
    total_nodes: int
    total_edges: int
    last_import: str | None


# =============================================================================
# Diagnosis Endpoints
# =============================================================================

@router.post("/diagnosis/differential", response_model=DifferentialDiagnosisResponse)
async def generate_differential_diagnosis(
    request: DifferentialDiagnosisRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
) -> DifferentialDiagnosisResponse:
    """
    Generate a differential diagnosis from phenotypes.

    Combines phenotype matching with optional genetic and medication data
    to produce a ranked list of candidate diagnoses.

    Examples:
    - Phenotypes: ["HP:0001250", "HP:0001251"] (seizures, ataxia)
    - Genes: ["SCN1A", "KCNQ2"]
    - Medications: ["valproic acid"]
    """
    start = time.time()

    # Get PrimeKG overlay
    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    # Create execution context
    context = OverlayContext(
        execution_id=correlation_id,
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    # Execute differential diagnosis
    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "differential_diagnosis",
            "phenotypes": request.phenotypes,
            "genes": request.genes,
            "medications": request.medications,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnosis failed: {result.error}"
        )

    execution_time = (time.time() - start) * 1000

    # Audit log for medical query
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id="primekg_diagnosis",
        action="differential_diagnosis_generated",
        details={
            "phenotype_count": len(request.phenotypes),
            "gene_count": len(request.genes),
            "result_count": len(result.data.get("differential", [])),
        },
        correlation_id=correlation_id,
    )

    return DifferentialDiagnosisResponse(
        input_phenotypes=request.phenotypes,
        input_genes=request.genes,
        input_medications=request.medications,
        differential=[
            DiagnosisCandidate(**d)
            for d in result.data.get("differential", [])
        ],
        total_candidates=result.data.get("total_candidates", 0),
        execution_time_ms=execution_time,
    )


@router.post("/diagnosis/phenotype-search", response_model=PhenotypeSearchResponse)
async def search_by_phenotypes(
    request: PhenotypeSearchRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> PhenotypeSearchResponse:
    """
    Find diseases matching a set of phenotypes.

    Uses HPO phenotype-disease relationships from PrimeKG
    to find candidate diseases.
    """
    start = time.time()

    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"phenotype_search_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "phenotype_to_disease",
            "phenotypes": request.phenotypes,
            "limit": request.limit,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {result.error}"
        )

    execution_time = (time.time() - start) * 1000

    return PhenotypeSearchResponse(
        input_phenotypes=request.phenotypes,
        results=[
            DiagnosisCandidate(**r)
            for r in result.data.get("results", [])
        ],
        execution_time_ms=execution_time,
    )


# =============================================================================
# Drug Endpoints
# =============================================================================

@router.post("/drugs/by-disease", response_model=DrugDiseaseResponse)
async def get_drugs_for_disease(
    request: DrugDiseaseRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> DrugDiseaseResponse:
    """
    Get drugs related to a disease.

    Returns:
    - Indications: Drugs approved for this disease
    - Contraindications: Drugs contraindicated for this disease
    - Off-label: Drugs used off-label for this disease
    """
    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"drug_disease_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "disease_to_drugs",
            "disease_id": request.disease_id,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {result.error}"
        )

    data = result.data
    return DrugDiseaseResponse(
        disease_id=data.get("disease_id", request.disease_id),
        disease_name=data.get("disease_name"),
        indications=[DrugInfo(**d) for d in data.get("indications", [])],
        contraindications=[DrugInfo(**d) for d in data.get("contraindications", [])],
        off_label=[DrugInfo(**d) for d in data.get("off_label", [])],
    )


@router.post("/drugs/interactions", response_model=DrugInteractionResponse)
async def check_drug_interactions(
    request: DrugInteractionRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> DrugInteractionResponse:
    """
    Check for drug-disease interactions and contraindications.

    Useful for medication safety checking in diagnosis workflows.
    """
    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"drug_interaction_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "check_drug_interactions",
            "drugs": request.drugs,
            "diseases": request.diseases,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {result.error}"
        )

    data = result.data
    return DrugInteractionResponse(
        drugs=data.get("drugs", request.drugs),
        diseases=data.get("diseases", request.diseases),
        interactions=[
            DrugInteraction(**i)
            for i in data.get("interactions", [])
        ],
        has_contraindications=data.get("has_contraindications", False),
    )


# =============================================================================
# Gene Endpoints
# =============================================================================

@router.post("/genes/associations", response_model=GeneAssociationResponse)
async def get_gene_disease_associations(
    request: GeneAssociationRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> GeneAssociationResponse:
    """
    Get gene-disease associations.

    Can query by gene (to find associated diseases) or by disease
    (to find associated genes).
    """
    if not request.gene_id and not request.disease_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either gene_id or disease_id must be provided"
        )

    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"gene_assoc_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "gene_disease_association",
            "gene_id": request.gene_id,
            "disease_id": request.disease_id,
            "limit": request.limit,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {result.error}"
        )

    data = result.data
    return GeneAssociationResponse(
        query=data.get("query", {"gene_id": request.gene_id, "disease_id": request.disease_id}),
        associations=[
            GeneAssociation(**a)
            for a in data.get("associations", [])
        ],
    )


# =============================================================================
# Search Endpoints
# =============================================================================

@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> SemanticSearchResponse:
    """
    Semantic search on PrimeKG clinical descriptions.

    Uses embedding-based similarity to find relevant diseases,
    genes, drugs, or phenotypes.
    """
    start = time.time()

    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"semantic_search_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "semantic_search",
            "query": request.query,
            "node_type": request.node_type,
            "limit": request.limit,
            "min_score": request.min_score,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {result.error}"
        )

    execution_time = (time.time() - start) * 1000

    return SemanticSearchResponse(
        query=request.query,
        results=[
            SemanticSearchResult(**r)
            for r in result.data.get("results", [])
        ],
        execution_time_ms=execution_time,
    )


# =============================================================================
# Discriminating Phenotypes Endpoints
# =============================================================================

@router.post("/diagnosis/discriminating-phenotypes", response_model=DiscriminatingPhenotypesResponse)
async def get_discriminating_phenotypes(
    request: DiscriminatingPhenotypesRequest,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> DiscriminatingPhenotypesResponse:
    """
    Find phenotypes that discriminate between two diseases.

    Used to generate follow-up questions that help narrow down
    the differential diagnosis.
    """
    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"discrim_pheno_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "find_discriminating_phenotypes",
            "disease_a": request.disease_a,
            "disease_b": request.disease_b,
            "already_present": request.already_present,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {result.error}"
        )

    data = result.data
    return DiscriminatingPhenotypesResponse(
        disease_a=data.get("disease_a", request.disease_a),
        disease_b=data.get("disease_b", request.disease_b),
        phenotypes=[
            DiscriminatingPhenotype(
                hpo_id=p["hpo_id"],
                name=p["name"],
                discriminates=p["discriminates"],
                question=p.get("description", f"Do you experience {p['name']}?"),
            )
            for p in data.get("phenotypes", [])
        ],
    )


# =============================================================================
# Disease Details Endpoints
# =============================================================================

@router.get("/diseases/{disease_id}", response_model=DiseaseDetailsResponse)
async def get_disease_details(
    disease_id: str,
    user: ActiveUserDep,
    overlay_manager: OverlayManagerDep,
) -> DiseaseDetailsResponse:
    """
    Get complete details for a disease.

    Returns phenotypes, associated genes, and available treatments.
    """
    primekg_overlay = overlay_manager.get_overlay("primekg")
    if not primekg_overlay:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PrimeKG overlay not available"
        )

    context = OverlayContext(
        execution_id=f"disease_details_{int(time.time())}",
        user_id=user.id,
        trust_level=user.trust_level.value if hasattr(user.trust_level, 'value') else user.trust_level,
    )

    result = await primekg_overlay.execute(
        context=context,
        input_data={
            "operation": "get_disease_details",
            "disease_id": disease_id,
        }
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {result.error}"
        )

    if result.data.get("error"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.data["error"]
        )

    disease = result.data.get("disease", {})
    return DiseaseDetailsResponse(
        node_id=disease.get("node_id", disease_id),
        mondo_id=disease.get("mondo_id"),
        name=disease.get("name", "Unknown"),
        description=disease.get("description"),
        phenotypes=disease.get("phenotypes", []),
        genes=disease.get("genes", []),
        treatments=disease.get("treatments", []),
    )


# =============================================================================
# Stats & Admin Endpoints
# =============================================================================

@router.get("/stats", response_model=PrimeKGStatsResponse)
async def get_primekg_stats(
    user: ActiveUserDep,
    db: DbClientDep,
) -> PrimeKGStatsResponse:
    """
    Get PrimeKG data statistics.

    Returns counts of nodes and edges by type.
    """
    query = """
    MATCH (n:PrimeKGNode)
    WITH n.node_type as type, count(n) as count
    RETURN type, count
    """
    results = await db.execute(query)

    counts = {r["type"]: r["count"] for r in results}

    # Get edge count
    edge_query = """
    MATCH ()-[r:PRIMEKG_EDGE]->()
    RETURN count(r) as edge_count
    """
    edge_result = await db.execute_single(edge_query)
    total_edges = edge_result.get("edge_count", 0) if edge_result else 0

    # Get last import time
    import_query = """
    MATCH (m:PrimeKGMetadata)
    RETURN m.last_import as last_import
    ORDER BY m.last_import DESC
    LIMIT 1
    """
    import_result = await db.execute_single(import_query)
    last_import = import_result.get("last_import") if import_result else None

    return PrimeKGStatsResponse(
        disease_count=counts.get("disease", 0),
        gene_count=counts.get("gene/protein", 0),
        drug_count=counts.get("drug", 0),
        phenotype_count=counts.get("effect/phenotype", 0),
        pathway_count=counts.get("biological_process", 0) + counts.get("pathway", 0),
        total_nodes=sum(counts.values()),
        total_edges=total_edges,
        last_import=last_import.isoformat() if last_import else None,
    )


@router.post("/admin/refresh-embeddings", status_code=status.HTTP_202_ACCEPTED)
async def refresh_embeddings(
    user: TrustedUserDep,
    overlay_manager: OverlayManagerDep,
    audit_repo: AuditRepoDep,
    correlation_id: CorrelationIdDep,
    node_type: str | None = Query(default=None, description="Node type to refresh"),
) -> dict[str, Any]:
    """
    Trigger embedding refresh for PrimeKG nodes.

    Requires TRUSTED trust level.
    """
    # This would typically trigger a background job
    await audit_repo.log_capsule_action(
        actor_id=user.id,
        capsule_id="primekg_admin",
        action="embedding_refresh_requested",
        details={"node_type": node_type},
        correlation_id=correlation_id,
    )

    return {
        "status": "accepted",
        "message": "Embedding refresh queued",
        "node_type": node_type or "all",
        "requested_at": datetime.now(UTC).isoformat(),
    }


@router.get("/health")
async def primekg_health_check(
    db: DbClientDep,
) -> dict[str, Any]:
    """
    Check PrimeKG data health.

    Verifies that PrimeKG data is loaded and accessible.
    """
    try:
        # Quick node count check
        query = """
        MATCH (n:PrimeKGNode)
        RETURN count(n) as count
        LIMIT 1
        """
        result = await db.execute_single(query)
        node_count = result.get("count", 0) if result else 0

        healthy = node_count > 10000  # Expect at least 10k nodes

        return {
            "healthy": healthy,
            "node_count": node_count,
            "min_expected": 10000,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "checked_at": datetime.now(UTC).isoformat(),
        }
